# Speech Processing: MFCC → Kaldi → Wav2Vec2 → Whisper, ASR Pipelines, Diarization

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** T05 · **Updated:** 2026-08-01
> **Module id:** `T26-speech-processing` · **Tags:** voice, critical

## Why this gets asked

Nearly everyone who has integrated speech into a product has called `openai.audio.transcriptions.create()` and never opened the box. The interviewer wants to know if you understand what's happening between a waveform and a token stream — not to reimplement Kaldi, but because that understanding is what lets you diagnose why your transcripts hallucinate on silence, why WER looks great in your eval but the downstream agent still gets confused, or why streaming latency and accuracy are fundamentally in tension rather than a config knob you haven't found yet. At staff/principal level, they're also checking whether you know the difference between the ASR-pipeline engineering problem (this module) and the realtime-voice-product problem (VAD, turn-taking, latency budgets under 300ms — covered in **T26-voice-models**), because conflating them is a tell that you've used these systems but not built with them.

---

## Lineage: past → present → future

**What came before.** Classical ASR (1980s-2010s) decomposed speech recognition into independently-trained, independently-tunable stages: an **acoustic model** (what sound corresponds to what phoneme), a **pronunciation lexicon** (what phonemes make up what words), and a **language model** (what word sequences are probable), combined via a **Hidden Markov Model** — first paired with Gaussian Mixture Models (HMM-GMM) for the acoustic model, later replaced by deep neural networks (HMM-DNN, the "hybrid" approach) once DNNs proved better at modeling the acoustic-to-phoneme mapping around 2010-2012. **Kaldi** (Povey et al., 2011) became the dominant open-source toolkit for building these systems, using **Weighted Finite State Transducers (WFSTs)** to compose the lexicon, language model, and HMM topology into a single searchable decoding graph. The specific pain that killed this approach for most teams: building a competitive Kaldi system for a new language required deep, specialized expertise across phonetics, an actual pronunciation lexicon for that language (often requiring linguists), careful HMM topology design, and a multi-stage training pipeline (GMM bootstrap → alignment → DNN fine-tune) that took real engineering-months per language, none of it transferring cleanly to the next language. Kaldi systems perform well on narrow, matched domains with enough per-language investment, but the investment doesn't scale — the industry needed one model, not one pipeline per language.

**Where it stands now.** End-to-end neural approaches replaced the multi-stage pipeline with a single model trained directly from audio to text (or to intermediate units), eliminating the separate lexicon/acoustic-model/language-model decomposition entirely. **Wav2Vec2** (Baevski et al., 2020) proved that self-supervised pretraining on large amounts of *unlabeled* audio, followed by lightweight fine-tuning with a **CTC loss** on a small amount of labeled data, could match or approach systems trained on far more labeled data — a genuinely important result for low-resource languages where labeled speech data is scarce but raw audio is not. **Whisper** (Radford et al., OpenAI, 2022) took a different bet: rather than self-supervised pretraining plus fine-tuning, train directly on 680,000 hours of *weakly-supervised* multilingual, multitask audio-transcript pairs scraped from the internet, producing one model that does transcription, translation, and language identification without per-language fine-tuning. Both are now genuinely deployed at scale — Wav2Vec2-family models remain the standard building block for low-resource and specialized-domain ASR fine-tuning, while Whisper (and its distilled/optimized derivatives) dominates general-purpose transcription products. The live disagreement is speed versus robustness: Whisper's larger models are notably more robust to accents, noise, and code-switching, but its 30-second processing window and autoregressive decoding make it slower and more failure-prone (hallucination, repetition) than purpose-built streaming systems, which is why real-time voice products (see **T26-voice-models**) often use different architectures entirely, not Whisper directly.

**Where it's heading.** Distillation and inference optimization are the dominant, already-shipping direction — `distil-whisper` and `faster-whisper`/`whisper-large-v3-turbo` deliver large-v3-class accuracy at a fraction of the latency and compute, and this is where most production deployments have already moved, high confidence. Diarization is converging toward end-to-end neural approaches (pyannote 3.x's Powerset architecture) that handle overlapping speech natively rather than as a post-hoc correction, moderate-to-high confidence this keeps improving. More speculative: unified speech-to-speech models that skip the intermediate text representation entirely for conversational use cases, trading transcription accuracy (and auditability) for latency — promising for voice assistants, actively researched, but not yet the right choice when you need an auditable, correctable text transcript as an artifact, which most enterprise ASR use cases still do.

---

## Mental model

```
raw audio (16kHz, 16-bit PCM)
        │
        ▼
┌───────────────┐
│  FRAMING /     │  chop into ~25ms frames, 10ms stride (overlapping)
│  WINDOWING     │  Hamming window each frame to reduce spectral leakage
└───────┬───────┘
        ▼
┌───────────────┐
│      FFT       │  time domain → frequency domain, per frame
└───────┬───────┘
        ▼
┌───────────────┐
│  MEL FILTER-   │  ~26-40 triangular filters, mel-spaced (nonlinear,
│  BANK          │  matches human pitch perception — see derivation below)
└───────┬───────┘
        ▼
┌───────────────┐
│  LOG + DCT     │  log(energy) then Discrete Cosine Transform →
│                │  decorrelates filterbank outputs → MFCCs (~13 coeffs/frame)
└───────┬───────┘
        ▼
   MFCC FEATURE SEQUENCE  ──────────────────┐
        │                                    │
        ▼ (classical)                        ▼ (modern, end-to-end)
┌───────────────┐                    ┌───────────────────────┐
│  HMM-GMM/DNN   │                    │  Transformer encoder-  │
│  + lexicon +   │                    │  decoder or CTC head,  │
│  LM via WFST   │                    │  trained end-to-end    │
│  (Kaldi)       │                    │  (Wav2Vec2, Whisper)   │
└───────┬───────┘                    └──────────┬────────────┘
        │                                        │
        └──────────────┬─────────────────────────┘
                        ▼
                   text transcript
```

The classical pipeline is a chain of independently-optimized modules; the modern pipeline is one model trained end-to-end from (roughly) the same MFCC-equivalent features straight to text, which is exactly why it doesn't need a per-language lexicon or separately-trained language model.

---

## How it actually works

### Audio capture and why 16 kHz

By Nyquist's theorem, a sample rate of `f` Hz can represent frequencies up to `f/2` Hz. Human speech's intelligibility-critical energy (formants, most consonant information) sits below roughly **8 kHz**, so a **16 kHz** sample rate (giving an 8 kHz Nyquist limit) captures essentially all speech-relevant information — this is why 16 kHz is the near-universal ASR standard, versus 44.1 kHz/48 kHz for music, which needs to represent the full human hearing range up to ~20 kHz. Telephony historically used 8 kHz (a 4 kHz Nyquist limit, "narrowband"), which is enough for intelligibility but loses some of the higher-frequency consonant detail (like the distinction between "s" and "f" sounds) that full 16 kHz captures — a real, measurable accuracy cost that shows up whenever you feed phone-call audio into a model trained on 16 kHz data without accounting for the mismatch.

### MFCC, derived properly

Mel-Frequency Cepstral Coefficients are the classical feature representation, still worth deriving because the same DSP building blocks (FFT, filterbanks) underpin how you'd reason about any audio preprocessing pipeline, even end-to-end neural ones that skip explicit MFCCs in favor of raw waveform or spectrogram input.

1. **Framing.** Speech is non-stationary (its spectral content changes over time), but stationary enough within a short window — split into ~25ms frames with 10ms stride (60% overlap), so each frame is short enough to treat as quasi-stationary.
2. **Windowing.** Multiply each frame by a Hamming (or Hann) window before the FFT, tapering the frame edges to zero. Without this, the abrupt edges of a rectangular frame introduce spectral leakage — spurious frequency content that isn't in the original signal, an artifact of the FFT assuming the frame repeats periodically.
3. **FFT.** Converts each windowed frame from the time domain to the frequency domain, giving a power spectrum per frame.
4. **Mel filterbank.** Apply ~26-40 overlapping triangular filters spaced on the **mel scale**, not linear Hz. The mel scale is logarithmic above roughly 1 kHz (`mel = 2595 · log10(1 + f/700)`), which mirrors human auditory perception: we discriminate pitch differences much more finely at low frequencies than at high ones — the difference between 100 Hz and 200 Hz is perceptually huge, while 8000 Hz and 8100 Hz is imperceptible. Mel spacing allocates more filters (more resolution) to the low-frequency range where speech carries the most phonetically distinctive information, matching what the human ear actually resolves.
5. **Log.** Take the log of each filterbank energy — again mirroring perception (loudness is perceived logarithmically, per the Weber-Fechner law) and compressing the dynamic range.
6. **DCT.** Apply a Discrete Cosine Transform to the log filterbank energies, which decorrelates them (adjacent mel filters have overlapping, correlated energy) and compacts the information into a small number of coefficients — typically the first **12-13 MFCCs** per frame capture most of the useful information, discarding higher coefficients that mostly encode fine spectral detail (pitch harmonics) rather than phonetic content.

The result is a compact (~13-dimensional, often extended with delta and delta-delta coefficients to capture rate of change) feature vector per ~10ms frame — small enough to make the classical HMM-GMM approach computationally tractable in an era before GPUs made raw-waveform or high-dimensional spectrogram modeling practical.

### The classical era: Kaldi, HMM-GMM/DNN, WFST decoding

Kaldi's architecture decomposes recognition into three independently-trained components composed at decode time:

- **Acoustic model** — maps audio features (MFCCs or filterbank energies) to phoneme (or sub-phoneme, "senone") probabilities. HMM-GMM initially, replaced by HMM-DNN (a DNN estimates the emission probabilities the GMM used to) once deep learning matured.
- **Pronunciation lexicon** — maps words to phoneme sequences (e.g., "cat" → /k/ /æ/ /t/), typically requiring either hand-built linguistic resources or a grapheme-to-phoneme model, per language.
- **Language model** — an n-gram (or neural) model of word-sequence probability, trained on text, that biases the decoder toward plausible word sequences over acoustically-similar-but-implausible ones.

These three are composed into a single search graph via **Weighted Finite State Transducers (WFSTs)**: the HMM topology, lexicon, and language model are each expressed as a weighted transducer, then composed (`H ∘ C ∘ L ∘ G` in Kaldi's standard notation) into one graph the decoder searches over using Viterbi-style beam search, finding the most probable word sequence given the acoustic evidence.

**The specific pain that killed it for most teams.** Every one of the three components needs its own training data and expertise: the lexicon needs either a linguist-built pronunciation dictionary or a working grapheme-to-phoneme system for that specific language (nontrivial for languages with irregular orthography), the acoustic model needs a substantial amount of *transcribed* audio in that language, and the language model needs a large text corpus. None of this transfers between languages — building a competitive Kaldi system for language #2 means redoing essentially all of it, with real per-language engineering-months of specialized effort. This is precisely the problem end-to-end neural models solve by learning the acoustic-to-text mapping directly, with no separate lexicon or hand-built HMM topology required.

### Wav2Vec2: self-supervised pretraining and CTC

Wav2Vec2 pretrains a transformer on raw audio with **no labels at all**, using a masked-prediction objective conceptually similar to BERT: it masks spans of the latent audio representation and trains the model to identify the correct quantized representation for the masked span from among distractors — learning general acoustic structure from audio alone. The pretrained model is then fine-tuned on a comparatively small amount of *labeled* (transcribed) audio using a **CTC (Connectionist Temporal Classification) loss**.

**CTC, explained properly.** The core problem CTC solves: you have an audio sequence of length T (many frames) and a target text sequence of length L (fewer characters/tokens), with no frame-level alignment given — you don't know which frames correspond to which characters. CTC solves this by having the model output a probability distribution over the vocabulary (plus a special **blank** token) at every one of the T frames, then summing over all possible **alignments** (sequences of length T that collapse to the target sequence of length L after removing blanks and merging repeated consecutive characters) to compute the total probability of the target sequence given the audio — trained by maximizing this probability via a dynamic-programming forward-backward algorithm (structurally similar to the HMM forward-backward algorithm CTC effectively generalizes). The blank token specifically handles the case of two consecutive identical characters needing to be represented as distinct (e.g., "ll" in "hello" needs a blank between the two L emissions, or the collapse operation would merge them into one).

**The result that made it matter.** Fine-tuning with only **10 minutes** of labeled data, on top of pretraining on 53,000 hours of unlabeled audio (Libri-light), achieved a WER of **4.8/8.2** (clean/other test sets) — demonstrating that the labeled-data bottleneck, which was the entire reason building Kaldi systems for new languages was so expensive, could be sidestepped by pretraining on abundant unlabeled audio and fine-tuning on a tiny labeled set. [wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations (arXiv 2006.11477)](https://arxiv.org/abs/2006.11477) — accessed 2026-08-01. This is the single most important number in this module to have cold: it's the concrete evidence for why self-supervised pretraining, not just "more labeled data," became the dominant paradigm for low-resource-language ASR.

### Whisper: weakly-supervised at scale

Whisper takes the opposite bet from Wav2Vec2: instead of self-supervised pretraining plus small-scale supervised fine-tuning, train directly on **680,000 hours** of weakly-labeled (audio, transcript) pairs scraped from the internet, spanning 96 languages plus translation pairs, in a single multitask, multilingual sequence-to-sequence transformer (encoder-decoder, not CTC) that jointly handles transcription, translation-to-English, language identification, and voice-activity-adjacent timestamp prediction, all specified via special tokens in the decoder's input rather than separate model heads.

**The 30-second window.** Whisper processes audio in fixed **30-second** chunks — audio is padded or truncated to exactly 30 seconds before being fed to the encoder. Longer audio is chunked into consecutive 30-second windows, decoded independently (or with a sliding-window/timestamp-conditioning trick to maintain some continuity), which is directly the source of several of its characteristic failure modes.

**Real failure modes, by name:**
- **Hallucinated text on silence or non-speech audio.** Because Whisper is a generative sequence model trained to always produce *something*, silence, background noise, or music in a 30-second window can produce fluent, plausible-sounding but entirely fabricated text — a genuinely dangerous failure mode for downstream systems that trust the transcript, because the hallucinated text is often grammatically well-formed and doesn't announce itself as wrong the way a garbled transcript would.
- **Timestamp drift**, especially over long audio — because chunking is done independently per 30-second window, small errors compound, and Whisper's built-in timestamp tokens are known to be less reliable than the text output itself, particularly across chunk boundaries.
- **Repetition loops**, where the autoregressive decoder gets stuck emitting the same phrase repeatedly — a known failure mode of greedy/beam decoding in sequence models generally, exacerbated by long silences or unclear audio within a chunk giving the decoder no strong signal to move on.

**Deployment path.** Running full Whisper large models in production at scale means confronting real latency and cost, which is why two derivatives dominate real deployments: **distil-whisper** (`distil-large-v3`) uses knowledge distillation to produce a **756M-parameter** model (versus large-v3's 1.54B) running roughly **6x faster** while staying within about **1% WER** of the full model on out-of-distribution audio; **whisper-large-v3-turbo** takes a different distillation approach, pruning the decoder from 32 layers to 4 (809M parameters), also delivering roughly **6x** faster inference (commonly cited around 8x real-time, with more aggressive optimized builds reported well beyond that) at a **0.3-0.7 percentage-point** WER cost versus large-v3. **faster-whisper** (the SYSTRAN reimplementation using the CTranslate2 C++ inference engine) is the standard way to actually run any Whisper variant efficiently on a GPU in production, independent of which model weights you choose. [Best open source speech-to-text (STT) model in 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) — accessed 2026-08-01; [Whisper Large-v3-Turbo vs Large-v3](https://gigagpu.com/whisper-large-v3-turbo-vs-large-v3-comparison/) — accessed 2026-08-01. Treat the exact speedup and real-time-factor multipliers as benchmark-hardware-dependent — they vary with batch size, GPU, and precision — but the order of magnitude (roughly 6-8x versus full large-v3, sub-1-point WER cost) is a solid, quotable range.

### WER, defined precisely, and why it's a poor downstream proxy

**Word Error Rate** is defined as:

```
WER = (Substitutions + Deletions + Insertions) / (Number of words in reference)
```

computed via the minimum edit distance (Levenshtein alignment) between the reference transcript and the hypothesis. A WER of 0.05 (5%) means, on average, 1 in 20 reference words was substituted, deleted, or wrongly inserted.

**Why it's a poor proxy for downstream task success.** WER treats every word error identically, but downstream impact is wildly uneven: substituting "not" for a missed negation ("the patient is not allergic" → "the patient is allergic") is one word error with potentially severe consequences, while mis-transcribing a filler word or a minor article ("a" vs "the") is one word error with essentially zero downstream impact. A voice-assistant intent classifier or a downstream LLM agent can often tolerate a surprisingly high WER on function words while being completely broken by a single wrong entity, number, or negation. This is exactly the gap between a model that "looks good on the eval" (low aggregate WER) and one that actually works for your use case — the fix is task-specific evaluation (intent accuracy, slot-filling accuracy, entity/number exact-match rate) layered on top of, not instead of, WER, and weighting errors by their actual downstream cost rather than treating a word as a word.

### Diarization: who spoke when

Diarization answers "who spoke when," independent of what was said — a separate problem from transcription, though often run alongside it and combined at the end (aligning transcript segments to speaker labels).

**The standard pipeline** (as implemented by **pyannote.audio**, the dominant open-source toolkit): a voice-activity-detection step isolates speech regions, a neural embedding model computes a fixed-size speaker-representation vector for short audio segments (conceptually similar to a face-recognition embedding, but for voice), and a clustering algorithm (commonly agglomerative hierarchical clustering) groups segments by embedding similarity into speaker clusters without knowing the number of speakers in advance.

**Overlapping speech is the hard problem.** Classical diarization systems assign each time segment to exactly one speaker, which is structurally wrong whenever two people talk simultaneously — a common occurrence in real conversation (interruptions, backchannel "mm-hmm"s overlapping the other speaker). The classical NIST **DER (Diarization Error Rate)** metric historically didn't even score overlap correctly, giving partial credit to systems that just picked the dominant speaker and ignored the second one entirely, which flattered systems that couldn't actually handle overlap. Modern architectures, notably pyannote 3.x's **Powerset** approach, treat overlapping-speaker combinations as their own output classes (rather than trying to assign one label per frame), producing a meaningful accuracy gain specifically on overlap-heavy audio. On standard benchmarks scored with overlap counted (the harder, more honest evaluation), pyannote 3.1 reports DER around **12-14% on AMI**, **9-11% on VoxConverse**, and **17-19% on DIHARD III** — worth knowing that these numbers are *higher* than older reported numbers for similar systems specifically because modern evaluation scores overlap, not because the systems got worse; always check whether a DER comparison is scoring overlap before treating it as apples-to-apples. [State of Speaker Diarization in 2026 — Picovoice](https://picovoice.ai/blog/state-of-speaker-diarization/) — accessed 2026-08-01.

### Streaming vs batch ASR

**Batch** (offline) ASR processes complete audio with full context available — highest accuracy, because the model can use future context and doesn't need to commit to a partial hypothesis before it has enough signal. **Streaming** ASR must emit partial results incrementally as audio arrives, with a hard latency budget (typically low hundreds of milliseconds for a usable voice UI), which forces architectural constraints: limited or no lookahead, chunk-based or frame-synchronous decoding, and often a separate, lighter-weight model than the batch equivalent. The tradeoff is direct and unavoidable: **more lookahead context improves accuracy but adds latency**, and every streaming ASR system is a specific point chosen on that curve, not a free lunch. Whisper, notably, is architecturally a batch model (30-second window, full attention over the chunk) — using it for "streaming" means running it repeatedly on a sliding, overlapping window and reconciling the overlapping outputs, which is a real engineering workaround, not native streaming support, and inherits both extra latency and extra hallucination-stitching complexity at the seams. Purpose-built streaming architectures (RNN-Transducer-family models, or Whisper-derivative streaming wrappers built specifically to manage this) are the right tool when sub-second latency is a hard product requirement — this is the boundary with **T26-voice-models**, which covers the realtime voice-product latency budget end to end.

### When to use a managed API instead of self-hosting

Use a managed transcription API (a cloud provider's STT service, or a hosted Whisper-API-compatible endpoint) when: transcription volume doesn't justify GPU infrastructure and its operational overhead, you need built-in diarization/language-detection/punctuation without assembling the pipeline yourself, or you need enterprise compliance features (data residency, retention controls) that are expensive to build in-house. Self-host when: you have sustained high volume where the per-minute cost of a managed API exceeds amortized GPU cost, you need on-premise/air-gapped operation for data sensitivity, you need latency guarantees a shared multi-tenant API can't commit to, or you need model customization (domain-specific fine-tuning, custom vocabulary injection) a managed API's black box doesn't expose.

---

## Build it from scratch

MFCC extraction from raw audio, using only NumPy, to make the DSP chain concrete:

```python
import numpy as np

def mfcc(signal: np.ndarray, sample_rate: int = 16000,
         frame_len_ms: float = 25, frame_stride_ms: float = 10,
         n_filters: int = 26, n_mfcc: int = 13) -> np.ndarray:
    """Minimal MFCC extraction: framing -> window -> FFT -> mel filterbank -> log -> DCT.
    # untested sketch — illustrative of the pipeline, not production-hardened
    (no pre-emphasis, no dithering, no delta/delta-delta coefficients)."""
    frame_len = int(sample_rate * frame_len_ms / 1000)
    frame_stride = int(sample_rate * frame_stride_ms / 1000)
    n_frames = 1 + (len(signal) - frame_len) // frame_stride

    # 1. Framing + 2. Windowing
    window = np.hamming(frame_len)
    frames = np.stack([
        signal[i * frame_stride: i * frame_stride + frame_len] * window
        for i in range(n_frames)
    ])

    # 3. FFT -> power spectrum
    n_fft = 512
    mag = np.abs(np.fft.rfft(frames, n=n_fft))
    power = (mag ** 2) / n_fft

    # 4. Mel filterbank
    def hz_to_mel(f): return 2595 * np.log10(1 + f / 700)
    def mel_to_hz(m): return 700 * (10 ** (m / 2595) - 1)

    low_mel, high_mel = hz_to_mel(0), hz_to_mel(sample_rate / 2)
    mel_points = np.linspace(low_mel, high_mel, n_filters + 2)
    hz_points = mel_to_hz(mel_points)
    bin_points = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)

    fbank = np.zeros((n_filters, n_fft // 2 + 1))
    for m in range(1, n_filters + 1):
        left, center, right = bin_points[m - 1], bin_points[m], bin_points[m + 1]
        for k in range(left, center):
            fbank[m - 1, k] = (k - left) / max(center - left, 1)
        for k in range(center, right):
            fbank[m - 1, k] = (right - k) / max(right - center, 1)

    filterbank_energy = power @ fbank.T
    filterbank_energy = np.where(filterbank_energy == 0, np.finfo(float).eps, filterbank_energy)

    # 5. Log  6. DCT (type-II, orthonormal, keep first n_mfcc coefficients)
    log_energy = np.log(filterbank_energy)
    from scipy.fftpack import dct
    mfccs = dct(log_energy, type=2, axis=1, norm="ortho")[:, :n_mfcc]
    return mfccs   # shape: (n_frames, n_mfcc)
```

CTC forward algorithm (the core alignment-summing computation, simplified to illustrate the mechanism rather than be numerically production-grade):

```python
import numpy as np

def ctc_forward_prob(log_probs: np.ndarray, target: list[int], blank: int = 0) -> float:
    """log_probs: (T, vocab_size) log-probabilities per frame.
    target: target label sequence (no blanks, no repeats needed in input).
    Returns log P(target | audio) summed over all valid alignments.
    # untested sketch — omits numerical stabilization tricks a real implementation needs."""
    T = log_probs.shape[0]
    # Expand target with blanks: b, t1, b, t2, b, ..., tn, b
    ext = [blank]
    for t in target:
        ext += [t, blank]
    S = len(ext)

    alpha = np.full((T, S), -np.inf)
    alpha[0, 0] = log_probs[0, ext[0]]
    if S > 1:
        alpha[0, 1] = log_probs[0, ext[1]]

    def logsumexp(*xs):
        m = max(xs)
        if m == -np.inf:
            return -np.inf
        return m + np.log(sum(np.exp(x - m) for x in xs))

    for t in range(1, T):
        for s in range(S):
            options = [alpha[t - 1, s]]
            if s > 0:
                options.append(alpha[t - 1, s - 1])
            # skip-connection: allowed if not a blank and doesn't repeat the label two back
            if s > 1 and ext[s] != blank and ext[s] != ext[s - 2]:
                options.append(alpha[t - 1, s - 2])
            alpha[t, s] = logsumexp(*options) + log_probs[t, ext[s]]

    return logsumexp(alpha[T - 1, S - 1], alpha[T - 1, S - 2])
```

For a runnable end-to-end lab (load `faster-whisper`, transcribe sample audio, measure WER against a reference, run `pyannote` diarization and align speaker labels to transcript segments), no lab exists yet for this module — a reasonable ask is `(lab pending)`.

---

## How it's done in production

| Concern | Typical production choice | What it adds |
|---|---|---|
| General transcription | `faster-whisper` (CTranslate2) running `large-v3-turbo` or `distil-large-v3` | GPU-efficient inference, 6-8x faster than naive Whisper, minimal WER cost |
| Low-resource/domain-specific ASR | Wav2Vec2 (or a newer self-supervised backbone) fine-tuned on domain-specific labeled audio | Adapts to accents/jargon/audio conditions Whisper wasn't trained on, without needing hundreds of hours of labeled data |
| Diarization | `pyannote.audio` 3.x pipeline | Speaker segmentation with native overlap handling (Powerset architecture) |
| Streaming/low-latency voice UI | Purpose-built streaming ASR (RNN-T family) or managed streaming APIs, not batch Whisper | Sub-second partial results; see **T26-voice-models** for the full realtime latency budget |
| Managed alternative | Cloud provider STT APIs, hosted Whisper-compatible endpoints | No GPU ops burden; built-in diarization/punctuation/language-ID; per-minute pricing |
| Evaluation | WER/CER plus task-specific metrics (entity exact-match, intent accuracy) | Catches the "low WER but broken downstream" gap |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Fluent, plausible-sounding text appears in the transcript during silence or non-speech segments | Whisper hallucination — generative decoder trained to always emit something | Run VAD before transcription to skip non-speech regions; post-filter segments with abnormally low confidence/high repetition |
| Transcript timestamps drift increasingly out of sync on long audio | Independent 30-second chunk decoding compounding small errors at each chunk boundary | Use timestamp-conditioning/sliding-window decoding, or a dedicated forced-alignment pass after transcription |
| Decoder repeats the same phrase in a loop | Autoregressive decoding stuck in a low-information region (silence, unclear audio) with no strong signal to advance | Cap repetition via generation constraints (no-repeat-ngram, repetition penalty), or beam search with length normalization tuned against this failure |
| Downstream agent/intent classifier fails despite a good WER score in the eval dashboard | WER treats all word errors equally; the errors that occurred happened to be entities/negations, not filler words | Add task-specific evaluation (entity exact-match, intent accuracy) alongside WER; don't ship on WER alone |
| Diarization assigns overlapping speech entirely to one speaker | Classical (non-Powerset) diarization architecture, or DER evaluation not scoring overlap so the gap wasn't visible in eval | Use a modern overlap-aware architecture (pyannote 3.x); make sure your own eval scores overlap, not just the legacy DER definition |
| New language launch takes months and needs a specialist | Still using a classical HMM/lexicon-based pipeline (Kaldi) requiring per-language lexicon + acoustic model + LM | Move to a pretrained multilingual end-to-end model (Whisper covers 96 languages out of the box) or self-supervised fine-tuning (Wav2Vec2) requiring far less per-language labeled data |
| Real-time voice UI feels laggy despite a "fast" ASR model | Using a batch-oriented model (Whisper) via a sliding-window hack instead of a genuinely streaming architecture | Switch to a purpose-built streaming ASR model, or accept the latency/accuracy tradeoff explicitly and communicate it as a product constraint |

---

## Tradeoffs & when NOT to use it

- **Don't build or maintain a Kaldi-style classical pipeline for a new product today** unless you have an unusual, narrow domain where a hand-tuned acoustic/language model genuinely outperforms a fine-tuned end-to-end model (rare, and shrinking) — the per-language engineering cost that killed Kaldi's dominance hasn't gotten any cheaper, while end-to-end alternatives have gotten dramatically better.
- **Don't use full Whisper large-v3 as your default production model without checking distil-whisper or large-v3-turbo first.** The 6-8x latency/cost improvement for roughly 0.3-1 point of WER is close to a free lunch for most use cases; only stick with the full model if your accuracy requirement is genuinely at the margin where that last fraction of a point matters.
- **Don't trust WER alone as a launch gate.** A model can hit your WER target while still failing on the specific error types (entities, negations, numbers) that break your downstream task; add task-specific evaluation before shipping.
- **Don't use Whisper for hard real-time, sub-second-latency voice UI without acknowledging you're working around its batch-oriented, 30-second-window design.** If the product genuinely needs sub-300ms turn-taking, that's a different architecture question — see **T26-voice-models**.
- **Don't self-host ASR infrastructure for low, sporadic volume.** The GPU idle cost and operational burden of running your own Whisper/faster-whisper deployment rarely beats a managed API until volume is sustained and significant; do the per-minute cost comparison before defaulting to self-hosting because it feels more "real engineering."
- **Don't assume diarization DER numbers are comparable across papers or vendors without checking whether overlap is scored** — an old DER number that ignores overlap will look artificially better than a modern, honestly-scored one, and comparing them directly is a real, common mistake.

---

## Interview questions

### Q1 — Why is 16 kHz the standard sample rate for ASR, and not the 44.1 kHz used for music?
**Testing:** baseline signal-processing literacy.
**Answer:** By Nyquist's theorem, a sample rate `f` captures frequencies up to `f/2`. Speech-intelligibility-critical energy sits below roughly 8 kHz, so 16 kHz (giving a 8 kHz Nyquist limit) captures essentially all of it; going to 44.1 kHz captures frequency content (up to ~20 kHz) that's relevant for music fidelity but adds no useful signal for recognizing speech, at the cost of more data to process for no accuracy benefit.
**Follow-up trap:** *"What about 8 kHz telephony audio — does that matter?"* — yes, telephony's 8 kHz sample rate (4 kHz Nyquist) loses higher-frequency consonant detail like the "s" vs "f" distinction, a real, measurable accuracy cost. Feeding narrowband phone audio into a model trained on 16 kHz data without accounting for the mismatch (upsampling doesn't recover lost information) is a common, avoidable mistake.

### Q2 — Derive MFCCs. Why mel spacing specifically, and why the DCT at the end?
**Testing:** whether "MFCC" is a memorized acronym or an understood pipeline.
**Answer:** Frame the signal into short (~25ms) overlapping windows (speech is non-stationary but quasi-stationary locally), apply a Hamming window to avoid spectral leakage from abrupt frame edges, FFT to get the power spectrum, apply a bank of triangular filters spaced on the mel scale (logarithmic above ~1kHz, matching human pitch discrimination — finer resolution at low frequencies where phonetic information concentrates), take the log of filterbank energies (matching perceived loudness's logarithmic scaling), and apply a DCT to decorrelate the filterbank outputs and compact the useful information into the first ~13 coefficients, discarding higher coefficients that mostly encode pitch harmonics rather than phonetic content.
**Follow-up trap:** *"Why decorrelate at all — what breaks if you skip the DCT and feed raw log-filterbank energies to a classifier?"* — adjacent mel filters have overlapping frequency ranges, so their energies are correlated; a GMM-based classifier (as in classical HMM-GMM systems) typically assumes diagonal covariance for tractability, and correlated features violate that assumption, hurting the acoustic model's accuracy. Modern neural acoustic models are less sensitive to this and increasingly skip MFCCs entirely in favor of raw filterbank energies or even raw waveform input, since a neural network can learn to decorrelate features itself.

### Q3 — Walk through why Kaldi-style systems fell out of favor for new product development.
**Answer:** Kaldi decomposes ASR into an acoustic model, a pronunciation lexicon, and a language model, composed via WFSTs into one decoding graph. Each of the three needs separate, language-specific resources and training data — a lexicon needs linguistic expertise or a working grapheme-to-phoneme system, the acoustic model needs substantial transcribed audio, the language model needs a large text corpus — and none of it transfers to a new language. Building a competitive system per language took real specialized engineering-months. End-to-end neural models (Wav2Vec2, Whisper) learn the acoustic-to-text mapping directly without a separate lexicon or hand-built HMM topology, and multilingual models like Whisper cover dozens of languages from one set of weights with no per-language pipeline at all.
**Follow-up trap:** *"Is Kaldi still ever the right choice today?"* — narrow, resource-constrained, or highly specialized domains where a hand-tuned classical system genuinely outperforms an available end-to-end model, or environments needing extremely low-latency on-device inference with a small footprint incompatible with a large transformer. This is a shrinking niche, not a common production answer, and should be stated as such rather than hedged.

### Q4 — Explain CTC loss and why it's needed instead of a normal cross-entropy loss for ASR.
**Testing:** the actual mechanics, not just the acronym.
**Answer:** ASR has no frame-level alignment between audio frames (many) and target text tokens (few) — you don't know which frames correspond to which characters. CTC solves this by having the model emit a distribution over the vocabulary plus a blank token at every frame, then summing the probability over every valid alignment (a length-T sequence that collapses to the target after removing blanks and merging consecutive repeats) via a dynamic-programming forward-backward algorithm, training the model to maximize the total probability of the target sequence without ever needing an explicit alignment as a training label.
**Follow-up trap:** *"Why do you need the blank token specifically — why not just merge repeated characters?"* — because some words genuinely have two consecutive identical characters that should NOT be merged into one (e.g., "ll" in "hello"). The blank token lets the alignment represent two separate emissions of the same character with a blank between them, which the collapse operation preserves as two characters instead of incorrectly merging them into one.

### Q5 — What is the concrete result that made Wav2Vec2 matter for low-resource languages?
**Answer:** Pretraining on 53,000 hours of unlabeled audio (Libri-light), then fine-tuning with CTC on just 10 minutes of labeled data, achieved a WER of 4.8/8.2 on clean/other test sets — showing that the labeled-data bottleneck, the entire reason classical per-language pipelines were so expensive to build, can be sidestepped by self-supervised pretraining on abundant unlabeled audio.
**Follow-up trap:** *"Does this mean Wav2Vec2 needs no labeled data at all for a brand new, unseen language?"* — no, it still needs some labeled data for fine-tuning (the 10-minute result is a floor demonstration, not zero), and the pretraining corpus's language coverage matters — a model pretrained only on English audio transfers acoustic structure less cleanly to a phonetically very different language than one pretrained multilingually. The result demonstrates dramatically reduced labeled-data requirements, not zero requirement.

### Q6 — What is Whisper's 30-second window, and what failure modes does it directly cause?
**Answer:** Whisper's encoder processes audio in fixed 30-second chunks (padded/truncated), with longer audio split into consecutive windows decoded largely independently. This directly causes timestamp drift on long audio (small per-chunk errors compound across chunk boundaries) and contributes to hallucination, because a chunk containing mostly silence or non-speech still gets fed through a generative decoder trained to always produce output, which can fabricate fluent but entirely invented text.
**Follow-up trap:** *"How would you mitigate hallucination on silence in a production pipeline without retraining the model?"* — run voice-activity detection (VAD) before transcription and skip non-speech segments entirely rather than feeding them to Whisper, and/or post-filter output segments with anomalous characteristics (very low average log-probability, high repetition) that correlate with hallucinated output.

### Q7 — Define WER precisely, and explain why a model can pass your WER bar and still fail in production.
**Answer:** WER = (Substitutions + Deletions + Insertions) / (words in reference), computed via minimum edit distance alignment between reference and hypothesis transcripts. It treats every word error identically in the aggregate score, but downstream impact is not uniform — a missed negation or a wrong entity/number is one word error with potentially severe consequences, while a mis-transcribed filler word is one word error with near-zero downstream impact. A model can hit an acceptable aggregate WER while concentrating its errors exactly on the small set of high-impact words (entities, negations, numbers) that break a downstream agent or intent classifier.
**Follow-up trap:** *"What would you add to a WER-only eval to catch this before shipping?"* — task-specific metrics layered on top: named-entity exact-match rate, numeric-value exact-match, intent/slot accuracy for a voice-assistant use case, or negation-preservation checks for a medical-transcription use case — anything that weights errors by actual downstream cost rather than treating every word equally.

### Q8 — How does speaker diarization actually work, and why is overlapping speech the hard part?
**Answer:** The standard pipeline: voice-activity detection isolates speech regions, a neural embedding model computes a fixed-size speaker representation per short audio segment, and clustering (commonly agglomerative hierarchical) groups segments into speaker clusters without knowing the speaker count in advance. Overlapping speech is hard because classical architectures assign one label per time segment, which is structurally wrong whenever two people talk simultaneously — a common real-conversation occurrence (interruptions, backchannel acknowledgments). Modern architectures like pyannote 3.x's Powerset approach treat overlapping-speaker combinations as their own output classes rather than forcing a single-speaker-per-frame assignment.
**Follow-up trap:** *"You compare a DER number from a 2018 paper against pyannote 3.1's reported DER and pyannote looks worse. What's actually going on?"* — check whether both numbers score overlapping speech. Older evaluations often didn't score overlap at all, giving partial credit to systems that simply picked the dominant speaker and ignored the rest, which flatters those older numbers. Comparing an overlap-unaware DER to an overlap-aware one directly is an apples-to-oranges mistake, not evidence the newer system regressed.

### Q9 — Design a streaming voice-assistant ASR pipeline. Why can't you just use Whisper directly?
**Testing:** whether the streaming/batch tradeoff is understood as architectural, not incidental.
**Answer:** Whisper is a batch model — full attention over a 30-second window, no native incremental/partial-output mode. Forcing it into "streaming" means running it repeatedly on overlapping sliding windows and reconciling the overlaps, which adds latency and hallucination-stitching complexity at every seam, and still can't reach the low-hundreds-of-milliseconds latency a responsive voice UI needs. A genuine streaming pipeline uses an architecture designed for incremental decoding (RNN-Transducer family, or a purpose-built streaming variant) that emits partial hypotheses as audio arrives, accepting a real accuracy cost from limited lookahead in exchange for the latency budget the product needs.
**Follow-up trap:** *"Quantify the tradeoff — more lookahead buys what, costs what?"* — more lookahead context improves accuracy (the model sees more of the utterance before committing to a hypothesis) but adds latency directly (you must wait for that future context to arrive before you can use it) — it's a direct dial, not separable knobs, and every streaming system sits at a specific chosen point on that curve rather than escaping the tradeoff. See **T26-voice-models** for how this interacts with end-to-end conversational latency budgets.

### Q10 — When would you recommend a managed transcription API instead of self-hosting Whisper/faster-whisper?
**Answer:** When volume is low or sporadic enough that GPU infrastructure's idle cost and operational burden exceed a managed API's per-minute pricing, when you need diarization/punctuation/language-ID assembled and maintained for you rather than built in-house, or when compliance requirements (data residency, retention controls) are more cheaply satisfied by a vendor's existing certifications than by building equivalent controls yourself. Self-host when volume is sustained and high enough that amortized GPU cost beats per-minute API pricing, when you need on-premise/air-gapped operation, or when you need domain-specific fine-tuning or custom vocabulary a managed black-box API doesn't expose.
**Follow-up trap:** *"Your self-hosted GPU cluster is idle 80% of the day — does that change the answer?"* — yes, and it's the actual point: self-hosting only wins on a genuine utilization and cost model, not a "we should own our infrastructure" instinct. Low, bursty utilization is exactly the profile where a managed API's pay-per-use pricing beats owning idle GPU capacity, and this is a calculation to actually run, not assume.

### Q11 — A team wants to fine-tune a speech model for a heavily-accented, domain-specific vocabulary (e.g., medical dictation). Wav2Vec2 or Whisper as the base?
**Answer:** Depends on labeled-data availability and whether you need fine-tuning at all. If labeled domain audio is scarce (tens of minutes to a few hours), Wav2Vec2's self-supervised-pretrain-plus-CTC-fine-tune path is specifically designed for exactly this regime and has direct published evidence of working with very little labeled data. If you have a moderate amount of labeled domain audio (tens of hours) and want to preserve Whisper's broader robustness and multilingual/multitask capability while nudging its vocabulary and accent handling, fine-tuning Whisper itself (or supplying a custom vocabulary/prompt-based bias) is a reasonable and increasingly common path. The wrong answer is assuming either works with zero domain data — both need some labeled examples of the target domain to actually shift performance.
**Follow-up trap:** *"The client refuses to allow the audio to leave their premises. Does that change your model choice?"* — it changes the deployment choice more than the model choice: this forces self-hosting regardless of which base model you fine-tune, ruling out any managed API path entirely, and should be surfaced as a constraint early rather than discovered after building a cloud-API-based prototype that can never ship.

### Q12 — What's the actual difference between the ASR-pipeline problem this module covers and the "voice product" problem?
**Testing:** whether the boundary between this module and T26-voice-models is understood, a common confusion at this level.
**Answer:** This module is about the mechanics of turning audio into accurate text: feature extraction, the acoustic/language modeling lineage, WER, diarization — largely offline or moderate-latency concerns. The voice-product problem (T26-voice-models) is about building a responsive conversational system: voice activity detection to know when someone stopped talking, turn-taking, end-to-end latency budgets typically under a few hundred milliseconds, and increasingly speech-to-speech models that skip the text intermediate representation entirely. A system can have excellent transcription accuracy (this module's concern) and still feel unusably laggy as a voice assistant (that module's concern), and the reverse — a system tuned purely for low-latency turn-taking can have loose enough transcription accuracy to actively hurt an intent classifier downstream.
**Follow-up trap:** *"Give a concrete example where optimizing one hurts the other."* — using full Whisper large-v3 (optimized for accuracy, batch-oriented, 30-second window) as the ASR backend of a realtime voice assistant: transcription quality is excellent, but the architecture cannot deliver the sub-second responsiveness the product needs, forcing an accuracy-for-latency tradeoff via a smaller/streaming model that a pure ASR-accuracy-focused evaluation would never have surfaced as necessary.

---

## Red flags that fail you

- Not knowing why 16 kHz is standard, or confusing it with telephony's 8 kHz.
- Describing MFCCs without being able to name the actual pipeline steps (framing, windowing, FFT, mel filterbank, log, DCT).
- Claiming Kaldi is obsolete without naming the specific pain (per-language pipeline cost) that actually killed its dominance.
- Explaining CTC without mentioning the blank token or why alignment-summing is needed at all.
- Treating WER as sufficient evidence a model is ready for production without task-specific evaluation.
- Not knowing Whisper's failure modes by name (hallucination on silence, timestamp drift, repetition loops).
- Comparing diarization DER numbers across systems without checking whether overlap is scored.
- Conflating this module's ASR-pipeline scope with the realtime voice-product latency problem.
- Recommending self-hosting or a managed API reflexively, with no cost/volume/compliance reasoning.

---

## Cheat card

```
SAMPLE RATE     16kHz standard (Nyquist → 8kHz, covers speech-critical energy)
                Telephony 8kHz (4kHz Nyquist) loses high-freq consonant detail
                Music 44.1/48kHz — overkill for speech, no ASR benefit

MFCC PIPELINE   frame (~25ms, 10ms stride) → Hamming window → FFT → mel
                filterbank (~26-40 filters, log-spaced >1kHz) → log → DCT
                → keep first 12-13 coeffs. Mel spacing mirrors human pitch
                perception (finer resolution at low freq).

KALDI ERA       HMM-GMM → HMM-DNN. Acoustic model + lexicon + LM, composed
                via WFST (H∘C∘L∘G). Killed by: per-language lexicon +
                acoustic model + LM = engineering-months per language,
                zero transfer.

WAV2VEC2        Self-supervised pretrain (masked latent prediction, no
                labels) + CTC fine-tune (small labeled set).
                KEY RESULT: 10 min labeled + 53k hrs unlabeled → 4.8/8.2 WER
                CTC: sums prob over all frame-to-label alignments via
                forward-backward DP; blank token separates repeated chars.

WHISPER         Weakly-supervised, 680k hrs scraped audio-transcript pairs,
                96 languages, multitask (transcribe/translate/lang-ID).
                30-SECOND WINDOW → source of failure modes:
                  - hallucination on silence (generative decoder)
                  - timestamp drift (independent chunk decoding)
                  - repetition loops (autoregressive decode stuck)
                large-v3-turbo: 809M params (32→4 decoder layers), ~6-8x
                faster, +0.3-0.7pt WER vs large-v3
                distil-large-v3: 756M params, ~6x faster, within ~1% WER
                faster-whisper (CTranslate2) = standard efficient runtime

WER             (Sub+Del+Ins)/reference_words, via edit distance.
                POOR proxy: treats "the"→"a" same as missing negation.
                Add: entity exact-match, intent accuracy, negation checks.

DIARIZATION     VAD → speaker embedding → clustering (agglomerative).
                Overlap = hard problem; old DER often didn't score it
                (inflates old numbers vs honest modern ones).
                pyannote 3.x Powerset: overlap combos as own classes.
                DER (overlap-scored): ~12-14% AMI, ~9-11% VoxConverse,
                ~17-19% DIHARD III.

STREAMING       lookahead ↑ accuracy ↑, latency ↑ — direct tradeoff, no
                free lunch. Whisper = batch-only; "streaming Whisper" =
                sliding-window hack, not native. RNN-T family = real
                streaming architecture.

MANAGED vs SELF  low/bursty volume, need diarization/compliance out of
                box → managed API. High sustained volume, on-prem, custom
                fine-tune → self-host.
```

## Sources

- [wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations (arXiv 2006.11477)](https://arxiv.org/abs/2006.11477) — accessed 2026-08-01
- [Best open source speech-to-text (STT) model in 2026 — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) — accessed 2026-08-01
- [Whisper Large-v3-Turbo vs Large-v3: When the Smaller Model Wins — GigaGPU](https://gigagpu.com/whisper-large-v3-turbo-vs-large-v3-comparison/) — accessed 2026-08-01
- [Distil-Whisper: Robust Knowledge Distillation via Large-Scale Pseudo Labelling (arXiv 2311.00430)](https://arxiv.org/pdf/2311.00430) — accessed 2026-08-01
- [State of Speaker Diarization in 2026: pyannote vs Falcon Benchmark — Picovoice](https://picovoice.ai/blog/state-of-speaker-diarization/) — accessed 2026-08-01
- [pyannote/speaker-diarization-3.1 — Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Speech recognition is one pipeline problem viewed through two eras: classical systems (Kaldi, HMM-GMM/DNN) decomposed it into a lexicon, an acoustic model, and a language model composed via WFSTs, and died because every one of those three needed separate per-language expertise and data that never transferred. End-to-end neural models replaced that with one model trained directly from audio to text — Wav2Vec2 proved self-supervised pretraining on unlabeled audio plus a CTC-loss fine-tune could hit 4.8/8.2 WER with just 10 minutes of labeled data, and Whisper proved weak supervision at massive scale (680k hours) could give one multilingual, multitask model, at the cost of a 30-second processing window that directly causes its three named failure modes: hallucination on silence, timestamp drift, and repetition loops. WER is the standard metric but a poor proxy for downstream success because it weighs a missed negation the same as a missed filler word. Diarization (who spoke when) is a separate embedding-plus-clustering problem where overlapping speech is the genuinely hard part, and streaming ASR is a direct, unavoidable latency-versus-accuracy tradeoff that batch-oriented Whisper wasn't built to solve natively.
