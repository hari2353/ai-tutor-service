# Voice: Whisper, TTS, Realtime Speech-to-Speech, Latency Budgets, VAD

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** T05, T26-speech-processing · **Updated:** 2026-08-23
> **Module id:** `T26-voice-models` · **Tags:** voice, critical

## The 30-second version

A realtime voice product is a latency-engineering problem wearing a conversational costume. The perceptual budget is fixed by human turn-taking — natural gaps between speakers average around **200 ms**, so a voice agent that answers in under **~800 ms** feels responsive and one that drifts past **~1500 ms** feels broken. Hitting that budget is not about picking a "fast model"; it's about decomposing the round trip — VAD/endpointing (~100-500 ms), streaming ASR partials (<250 ms), LLM time-to-first-token (100-600 ms), TTS time-to-first-audio (90-313 ms), plus 50-200 ms of network hops — and then *overlapping* the stages instead of running them sequentially: a naive serial pipeline costs ~1400 ms, a fully streamed one 500-700 ms. The two architectural forks are cascaded (ASR→LLM→TTS, debuggable, per-stage transcripts) versus speech-to-speech (one model does everything at ~600-900 ms end-to-end, but you lose auditability). And underneath it all sits VAD — the deceptively small problem of deciding whether a human has finished talking — which is where most voice products actually break.

## Why this gets asked

Because almost every team that ships a voice agent ships one that feels laggy first, and the diagnosis is never "use a faster LLM." The interviewer wants to see whether you can decompose felt latency into named, budgeted stages; whether you know that what matters for the LLM stage is *first token*, not total generation; whether you understand why endpointing is the single largest and most fragile line item; and whether you can reason about the cascaded-vs-speech-to-speech fork as a real tradeoff (traceability and cost predictability versus latency and prosody) rather than "new thing wins." At senior levels they're also probing whether you know the VAD/endpointing distinction — frame-level speech detection versus turn-end decision — because conflating them is exactly the bug that makes agents interrupt users mid-sentence or leave awkward dead air after every utterance. Finally, this module is the boundary-check against **T26-speech-processing**: that module covers making transcripts accurate; this one covers making conversation feel alive. A system can win on WER and still be unusable as a voice assistant.

---

## Lineage: past → present → future

**What came before.** Telephony solved turn-taking with fixed engineering: half-duplex links, echo suppressors, and IVR systems using simple energy-threshold VAD descended from telecom standards work (the G.729-era detectors of the late 1990s already documented that pure energy thresholding fails wherever background noise is high — loud non-speech reads as speech, a failure mode that hasn't aged). The first generation of voice assistants (2010s Siri/Alexa era) ran a rigid cascade: wake word → cloud ASR → intent classifier → templated response → TTS, with round trips measured in seconds but masked by a "boop" sound design convention that told users to expect waiting. Each stage was separately engineered, separately deployed, and separately slow; latency was treated as an infrastructure cost amortized into the experience, and nobody talked about budgets because the interaction pattern (command → acknowledgment) didn't require sub-second conversational rhythm.

**Where it stands now.** Two architectures coexist as of 2026. The **cascaded** stack — streaming STT (Deepgram Nova-3-class, Whisper derivatives) → LLM streamed token-by-token → streaming TTS (Cartesia Sonic-3 at ~188 ms median TTFA, ElevenLabs Turbo v2.5 ~264 ms, Deepgram Aura-2 ~313 ms) — is the default production choice because each stage is independently replaceable, benchmarkable, and debuggable from per-stage transcripts, with total per-minute costs around $0.0095-$0.17 depending on vendor tier. The **speech-to-speech** stack — OpenAI's Realtime API family, Google's Gemini Live API, ElevenLabs' conversational endpoints — collapses ASR+LLM+TTS into one multimodal model emitting audio directly, hitting ~600-900 ms end-to-end with more natural prosody and native interruption handling, at a cost spread across providers of roughly **182x** per minute (a real pricing lottery as of 2026). Under both stacks sit the same primitives: neural VAD (Silero, MIT-licensed, trained on data spanning 6,000+ languages, supporting 8 kHz and 16 kHz) feeding endpointing logic that increasingly adds **semantic** signals (OpenAI's Realtime API exposes a `semantic_vad` mode with low/medium/high/auto eagerness) because acoustic silence alone cannot distinguish a hesitation from a completed thought.

**Where it's heading.** Speech-to-speech keeps eating use cases where conversational feel dominates auditability, high confidence over the next few years — but cascaded persists anywhere compliance requires per-stage transcripts, custom model choice, or VPC-resident deployment, which is most enterprise voice. Semantic/turn-detection models layered over acoustic VAD become standard (LiveKit already ships Silero-plus-turn-detector as its recommended pairing); full-duplex models that listen while talking shrink the interruption problem architecturally rather than heuristically. The open problems are evaluation-shaped, not architecture-shaped: audio-level quality regression (a TTS provider silently rotating a model behind your back can degrade CSAT for a week before anyone notices), accent-cohort fairness under load, and p99 latency discipline — because averages hide exactly the outlier turns that make callers hang up.

---

## Mental model

```
            THE ROUND TRIP (user stops speaking → user hears reply)

  ┌─────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
  │ uplink + │   │ VAD/endpoint │   │ STT      │   │ LLM      │   │ TTS     │
  │ jitter  │ → │ "done        │ → │ partials │ → │ FIRST    │ → │ FIRST   │
  │ buffer  │   │ talking?"    │   │ <250ms   │   │ TOKEN    │   │ AUDIO   │
  │ 50-100ms│   │ 100-500ms    │   │          │   │ 100-600ms│   │ 90-313ms│
  └─────────┘   └──────────────┘   └──────────┘   └──────────┘   └─────────┘
       └────────────── plus 50-200ms inter-vendor network hops ─────────────┘

  SEQUENTIAL (naive):  sum of all stages ≈ 1,400 ms  → feels broken-ish
  STREAMED (overlapped): stages overlap; only the critical path counts
                         ≈ 500-700 ms               → feels responsive

  PERCEPTION LADDER:
     <200 ms   = human turn-taking gap; indistinguishable from a person
     <800 ms   = responsive; pauses barely registered
     >800 ms   = noticeable; agent starts feeling "slow"
     >1500 ms  = broken; users repeat themselves / talk over / hang up
```

The key mental shift: **latency is a budget you allocate, not a property you observe.** Every stage gets a line item; every line item is negotiable by spending something else (accuracy, cost, complexity). And the unit that matters is never "how long does the model take" — it's *time to first output*: first transcript partial for STT, first token for the LLM, first audio chunk for TTS. Total generation time is irrelevant if the first sentence is already playing while the rest streams.

---

## How it actually works

### The 800 ms budget, decomposed

Start from the perception numbers. In natural human conversation the gap between one person stopping and the next starting averages roughly **200 ms**, frequently less, sometimes overlapping. Humans are exquisitely tuned to this rhythm; a longer silence is read unconsciously as hesitation, confusion, or a bad line. Hence the working thresholds: sub-800 ms round trip reads as responsive, past ~800 ms pauses become consciously noticeable, past ~1500 ms the conversation functionally breaks down (users repeat themselves, talk over the agent, assume the line dropped).

Now allocate the budget. A representative 2026 decomposition for a cascaded agent:

| Stage | Typical budget | Notes |
|---|---|---|
| Uplink + jitter buffer | 50-100 ms | Mic capture, WebRTC transport, client-side playout buffer |
| Endpointing (end-of-turn detect) | 100-500 ms | Dominated by silence threshold; the biggest single lever |
| Streaming STT to usable partial | <250 ms | Deepgram Nova-3-class; ElevenLabs Scribe v2 Realtime reports sub-150 ms |
| LLM time-to-first-token | 100-600 ms | Small/fast models 100-200 ms; large models with long prompts worse |
| TTS time-to-first-audio | 90-313 ms | Gradium ~155 ms P50, Cartesia Sonic-3 ~188 ms, ElevenLabs Turbo v2.5 ~264 ms, Aura-2 ~313 ms |
| Inter-vendor network hops | 50-200 ms | Multiplies with every distinct vendor region |

Summed naively that's ~600-1900 ms — which is precisely the point. Whether you land at 650 ms or 1600 ms is determined not by any single component choice but by **overlap**: streaming every stage so that TTS starts speaking the LLM's first complete sentence while the LLM is still generating, and STT partials feed context while the user is still talking. Sequential execution of the same components costs roughly **1400 ms**; fully-streamed execution lands **500-700 ms**. Overlap, not raw speed, is the difference between feeling broken and feeling natural.

Two disciplines follow. First, measure **time-to-first-audio (TTFA)** end to end, at p50 *and* p95/p99 — an average of 400 ms routinely hides a p99 of 2.5 s, and the outlier turns are the ones callers remember. Second, treat the LLM stage's contribution as *first-token* latency only: a model that generates for 20 s but starts in 150 ms is fine for voice; a model that takes 2 s to think before saying anything is unusable regardless of quality. This is why reasoning-style models need explicit handling in voice (either a "let me check..." spoken filler while thinking, or routing hard queries off the voice path).

### VAD: the smallest component with the biggest blast radius

Voice Activity Detection classifies short audio frames (typically ~20-30 ms) as speech or non-speech. Three generations:

1. **Energy thresholding** — loud frame = speech. Cheap, and fails in exactly the conditions phone agents live in: traffic, keyboards, babble noise, HVAC. Loud non-speech misclassifies as speech; this was documented in the G.729 standardization work back in 1997 and remains true. Also broken by any noise floor asymmetry between training/tuning environment and deployment.
2. **GMM-based spectral VAD** — WebRTC VAD is the canonical implementation: Gaussian Mixture Models over energy, spectral shape, zero-crossing rate, pitch features. Extremely lightweight (pure C, no dependencies), battle-tested in millions of browser sessions, but low accuracy in noise — struggles specifically with babble, music, non-stationary noise.
3. **Neural VAD** — Silero VAD is the open-source default: a compact neural net outputting a speech probability per frame, MIT-licensed, no telemetry, runs via PyTorch or ONNX runtime (including ONNX Runtime Web in the browser and ExecutEtorch on device), supports 8 kHz and 16 kHz (that dual support matters more than it sounds: lab recordings are 16 kHz, phone calls are not). Picovoice's Cobra is the commercial lightweight alternative optimized for microcontrollers.

But the deeper point interviewers probe: **VAD answers the wrong question for turn-taking.** "Is there a voice in this 20 ms window?" is not "has the user finished their turn?" A breath and a finished thought look identical acoustically. Real speech is discontinuous — one sentence like "It's for, uh, the eighth" produces four separate speech regions from a naive detector (drop on the comma-pause, spike on "uh", drop, spike again). The gap between VAD and turn-taking is filled by **endpointing**:

- **Fixed silence timer** (classic): declare end-of-turn after N ms of VAD-detected silence. Simple. But there is no correct N: set it low (say 300 ms) and you cut people off mid-sentence constantly; set it high (800 ms) and every single turn carries a half second of dead air. Silence duration alone contains zero information distinguishing hesitation from completion.
- **Hangover/pre-roll framing** (telecom heritage): extend speech regions with trailing "hangover" frames so low-amplitude mid-speech isn't clipped — G.729 used fifteen 10 ms frames of overhang versus five in the GSM detector. Same idea survives today inside every VAD wrapper as configurable `speech_pad_ms` / `silence_duration_ms`.
- **Semantic endpointing** (2024-2026 mainstream): score whether the utterance is *meaningfully complete* using lexical content, syntax, intonation, fillers. OpenAI's Realtime API exposes `semantic_vad` with an eagerness dial (low/medium/high/auto) that adjusts how long the model waits when the caller trails off with "ummm" versus stops on a definitive statement. Dedicated turn-detection models (LiveKit's turn detector, Deepgram Flux posting sub-300 ms median end-of-turn) sit on top of VAD + streaming transcript and make the actual respond-or-wait decision. Semantic layering adds effectively zero marginal latency when folded into the same forward pass as transcription.

Production practice is layered: acoustic VAD gates the mic and rejects noise; semantic/turn-detection decides when to respond; a calibrated hangover smooths both. The four canonical error modes pull against each other with no global optimum: front-end clipping (start of speech lost), mid-speech clipping (hangover too short), end-pointing delay (hangover too long → sluggish), and noise-detected-as-speech (agent responds to a cough). Tuning takes an afternoon; *proving* the tuning works across thousands of messy calls is the actual job.

### Streaming ASR partials

The STT stage must emit **partial hypotheses incrementally** — final-quality text is not needed until the LLM commits, and waiting for finals wastes budget. Purpose-built streaming engines (Deepgram Nova-3, AssemblyAI Universal-2, ElevenLabs Scribe v2 Realtime, NVIDIA Riva) return partials under ~200 ms over WebSocket. Whisper derivatives require the sliding-window workaround described in **T26-speech-processing** — workable for near-real-time transcription, wrong tool for sub-800 ms turns. Two details that matter in practice: (1) feed partials into the LLM's context as they arrive so the model can begin formulating before the utterance ends; (2) on end-of-turn, flush the trailing transcript segment explicitly (semantic-VAD implementations expose exactly this as a `send_flush()`-style call) so the final words aren't stranded in a lookahead buffer.

### LLM stage: first token is the whole game

Time-to-first-token dominates perceived responsiveness because nothing downstream can start without it. Levers, in order of impact: choose a fast-inference model class (small/frontier-lite tiers stream first tokens in 100-200 ms vs 250-600 ms for larger ones); keep system prompts short and cache them provider-side (prompt caching eliminates re-processing of static context); colocate inference regionally with the telephony leg; and design tools so the model can speak a filler ("Let me check that for you") while executing a lookup asynchronously rather than blocking silently for 1-2 s. Tool calls are the classic hidden latency bomb: a synchronous tool call mid-conversation adds its full round trip to TTFA unless the interaction is designed to bridge the gap with speech.

### TTS and chunking

Streaming TTS engines synthesize from text increments; the engineering question is **where to chunk**. Sentence-boundary chunking is the default — pushing arbitrary token fragments causes mid-phoneme glitches, while waiting for paragraphs blows the budget. Chunk at punctuation boundaries (clause or sentence level), tune chunk size against TTFA, and keep the client jitter buffer around **200-300 ms** to absorb network jitter without adding audible delay. Vendor choice moves the budget materially: the spread between fastest (~155 ms Gradium) and slowest (~313 ms Aura-2) medians exceeds an entire barge-in allowance. Median isn't the whole story either — some vendors trade a slower median for much tighter variance (ElevenLabs Turbo v2.5's ~28 ms interquartile range means fewer ugly outlier turns), and on phone lines predictable-beats-jittery. Quality is tracked separately via blind ELO leaderboards (Artificial Analysis TTS leaderboard, top models scoring ~1164-1208 ELO in 2026) rather than MOS alone.

### Barge-in (interruption handling)

Users talk over machines the way they talk over people; an agent that can't handle it feels rude, and it's the number-one beginner failure. The mechanics are a hard loop with a deadline: on detecting user speech during agent playback (VAD on the return channel), **stop playback within ~150 ms**, flush/cancel the TTS buffer and any queued audio, cancel the in-flight LLM generation (`response.cancel` in OpenAI Realtime terms), clear client-side queues, and reroute the incoming audio to STT so the new utterance is captured cleanly. Echo leakage matters here: if the agent hears its own TTS through the user's speakerphone, it will barge in on itself — hence acoustic echo cancellation (AEC) as a prerequisite, and why raw audio paths through telephony bridges need careful half-duplex/full-duplex handling.

### Cascaded vs speech-to-speech

**Cascaded** (STT→LLM→TTS): per-stage transcripts (debuggable — you can reconstruct exactly what the caller said, what the model heard, what it replied), independent vendor/model swaps, predictable per-minute cost ($0.0095-$0.17/min across common stacks), works self-hosted/VPC. Costs: three network legs, three vendors to monitor, compounding errors (bad transcript → confident answer to a question nobody asked).

**Speech-to-speech** (OpenAI Realtime/gpt-realtime family, Gemini Live, ElevenLabs conversational): one model consumes audio and emits audio; ~600-900 ms end-to-end typical; prosody and interruption handling are native because the model "thinks in voice." Costs: the transcript is a derived artifact (auditability weaker), model choice is the vendor's, cost spread across S2S providers is enormous (~182x per minute from cheapest to priciest in 2026), and observability must be rebuilt around events rather than clean per-stage spans. Server-side VAD ships by default (`turn_detection.type = "server_vad"` with tunable threshold and silence duration), semantic mode available.

Decision heuristic: default to cascaded unless conversational feel is the *product*; go S2S when latency/prosody dominate and traceability requirements are light; enterprise/compliance contexts usually force cascaded or hybrid (S2S for conversation, parallel STT for the audit transcript).

---

## Build it from scratch

**Exercise 1: an energy-based VAD state machine.** Deliberately the *naive* baseline — build it once so you understand viscerally why everyone uses Silero, and where every knob (threshold, hangover, pre-roll) lives:

```python
# untested sketch — illustrative state machine, not production-hardened.
# Real deployments swap the energy gate for Silero/Cobra neural VAD but keep
# exactly this state-machine skeleton (pre-roll, hangover, hysteresis).
import collections
import math

class EnergyVAD:
    """Energy-threshold VAD with pre-roll capture and hangover release.

    States: IDLE -> SPEAKING -> (hangover) -> IDLE
    Emits: ('speech_start', ts), ('speech_end', ts, audio_with_preroll)
    """
    def __init__(self, sample_rate: int = 16000,
                 frame_ms: int = 30,              # classic frame size
                 energy_thresh_db: float = -40.0, # the naive knob
                 preroll_ms: int = 200,           # audio BEFORE trigger kept
                 hangover_ms: int = 400):         # silence before declaring end
        self.frame_len = sample_rate * frame_ms // 1000
        self.preroll_frames = max(1, sample_rate * preroll_ms // 1000 // self.frame_len)
        self.hangover_frames = sample_rate * hangover_ms // 1000 // self.frame_len
        self.thresh = 10 ** (energy_thresh_db / 20)  # dBFS -> linear amplitude
        self.preroll = collections.deque(maxlen=self.preroll_frames)
        self.reset()

    def reset(self):
        self.state = "IDLE"
        self.silence_run = 0
        self.speech_frames: list[bytes] = []

    def _rms(self, frame: bytes) -> float:
        n = len(frame) // 2
        if n == 0:
            return 0.0
        samples = [int.from_bytes(frame[2*i:2*i+2], "little", signed=True) / 32768.0
                   for i in range(n)]
        return math.sqrt(sum(s*s for s in samples) / n)

    def process(self, frame: bytes):
        """Feed one PCM16 frame; returns events or None."""
        events = []
        self.preroll.append(frame)
        speaking = self._rms(frame) > self.thresh   # <- the entire 'model'

        if self.state == "IDLE":
            if speaking:
                self.state = "SPEAKING"
                self.speech_frames = list(self.preroll)   # include pre-roll!
                self.silence_run = 0
                events.append(("speech_start", None))
        elif self.state == "SPEAKING":
            self.speech_frames.append(frame)
            if speaking:
                self.silence_run = 0                      # hysteresis: any
            else:                                         # voiced frame resets
                self.silence_run += 1                     # the hangover counter
                if self.silence_run >= self.hangover_frames:
                    self.state = "IDLE"
                    events.append(("speech_end", bytes().join(self.speech_frames)))
                    self.reset()
        return events or None
```

Things this sketch teaches that transfer directly to production: pre-roll exists because your trigger always fires late (you only know speech started after it started); hangover is hysteresis, converting a noisy binary signal into a stable region decision; and the energy gate itself is trivially defeated by noise — swap `_rms` for a neural probability and keep the machinery. Note the four-way tension from the text maps onto exactly two knobs here (`energy_thresh_db`, `hangover_ms`).

**Exercise 2: a streaming-latency budget calculator.** The tool that turns "our agent feels slow" into a ranked list of fixes:

```python
# untested sketch — budget calculator: sequential vs overlapped critical path.
from dataclasses import dataclass

@dataclass
class Stage:
    name: str
    p50_ms: float
    p99_ms: float
    overlaps_next: bool = False   # True if this stage's OUTPUT streams into
                                  # the next (partial transcript -> LLM stream)

BUDGET = [
    Stage("uplink+jitter",   75, 150),
    Stage("endpointing",    300, 500),   # silence threshold dominates p99
    Stage("stt_partial",    180, 400,  overlaps_next=True),
    Stage("llm_first_token",180, 600,  overlaps_next=True),
    Stage("tts_first_audio",188, 350,  overlaps_next=True),
    Stage("downlink",        60, 120),
]

def roundtrip(stages=BUDGET, percentile="p50"):
    key = {"p50": "p50_ms", "p99": "p99_ms"}[percentile]
    seq = sum(getattr(s, key) for s in stages)
    # overlapped: a streaming stage only pays ITS OWN latency on the critical
    # path; the next stage starts as soon as the first chunk arrives, so the
    # stage's TOTAL duration hides under the downstream stage's generation.
    crit = 0.0
    for i, s in enumerate(stages):
        v = getattr(s, key)
        crit += v if i == 0 else min(v, 0) if s.overlaps_next else v
        # simplified: overlap hides the *tail* of upstream stages, modeled here
        # by charging streaming stages only their first-chunk latency
    return seq, crit

if __name__ == "__main__":
    for pct in ("p50", "p99"):
        s, c = roundtrip(percentile=pct)
        print(f"{pct}: sequential={s:.0f}ms  streamed≈{c:.0f}ms")
```

Run it, then ask: which line item moves p99 the most? (Endpointing — it's pure policy, no model required.) Which vendor swap buys the most? (TTFA spread: 155→313 ms.) Where does prompt caching show up? (LLM first token.) This calculator *is* the interview answer format: decompose, rank, fix the top line.

---

## How it's done in production

| Concern | Typical production choice | Why |
|---|---|---|
| Orchestrator framework | Pipecat, LiveKit Agents, Vapi, Retell | Handle the event plumbing (VAD↔STT↔LLM↔TTS wiring, cancellation, tracing) that's easy to get subtly wrong |
| VAD | Silero (open source) or platform built-in | MIT license, ONNX-runnable, 8/16 kHz; LiveKit pairs it with a dedicated turn-detection model |
| Turn detection | Semantic endpointing (provider-native or dedicated model) | Acoustic silence alone cannot distinguish hesitation from completion |
| STT | Deepgram Nova-3 / AssemblyAI Universal-2 / Scribe v2 Realtime class | Sub-250 ms partials; WebSocket/WebRTC streaming |
| LLM | Fast-tier model, prompt-cached, regional | First-token latency is the metric; verbosity capped in the system prompt |
| TTS | Cartesia/ElevenLabs/Gradium class streaming engines | TTFA 155-288 ms; chunk at punctuation boundaries |
| S2S alternative | OpenAI Realtime / Gemini Live for feel-first products | ~600-900 ms end-to-end, native interruption; accept weaker audit trail |
| Observability | Per-stage OTel spans (traceAI-livekit/pipecat) + TTFA p50/p95/p99 dashboards | An SRE story: TTS vendor rotates a model → flat-affect voice for a week → only caught because per-call audio quality was scored |

**What breaks in production**

| Symptom | Cause | Fix |
|---|---|---|
| Agent interrupts users constantly | Silence threshold too low / no hangover / semantic layer missing | Raise hangover, add semantic endpointing; track turn-error rate per cohort |
| Every reply has a half-second dead pause | Threshold raised too far to stop interruptions | Layer semantic VAD instead of trading one silence-timer evil for the other |
| Agent responds to coughs/TV voices | Noise-detected-as-speech on a cheap energy gate | Neural VAD + minimum-utterance-duration + confidence floor |
| p50 great (400 ms), users still complain | p99 outliers (2.5 s turns) dominate subjective experience | Instrument p95/p99 per stage; alert on tail, not mean |
| Agent talks over itself on speakerphone | TTS leaking into mic path triggers self-barge-in | Acoustic echo cancellation; suppress VAD during agent playback windows |
| Tool calls add silent 1-2 s freezes | Synchronous tool call blocking the response | Filler speech + async tool execution; fail tools gracefully |
| Voice quality quietly degraded last Tuesday | Provider rotated the TTS model behind a stable API name | Version-pin voices; nightly synthetic-call regression on naturalness metrics |
| Answers don't match what the user asked | STT error propagated confidently downstream | Score ASRAccuracy per cohort (accent/noise); confidence-gated repair loops ("did you mean...?") |

---

## Tradeoffs & when NOT to use it

- **Don't chase speech-to-speech for everything.** If the product needs per-stage audit trails, specific model choices (your fine-tuned domain LLM), VPC residency, or predictable per-minute economics, cascaded wins even though S2S feels better. The ~182x S2S cost spread also means "just use realtime API" is a budget decision requiring actual quotes.
- **Don't tune a single silence threshold and call it endpointing.** No silence value distinguishes hesitation from completion — the information isn't in the envelope. If interruptions and dead-air complaints are simultaneously present, the answer is a semantic layer, not another threshold pass.
- **Don't optimize the mean.** Latency work guided by averages systematically misses the p99 turns that drive hang-ups and bad reviews. Budget in percentiles from day one.
- **Don't use batch Whisper (or any batch ASR) as the STT of a sub-800 ms agent.** Architecturally wrong tool; sliding-window hacks inherit extra latency and stitching artifacts (see T26-speech-processing).
- **Don't skip barge-in design because the demo worked.** Demo conditions are quiet rooms and polite users; production is speakerphones and interrupts. Without a tested ≤150 ms stop-flush-reroute loop, the first real user call will feel rude.
- **Don't let the LLM free-associate length-wise.** Uncapped responses get monotone and blow turn budgets; cap verbosity in the system prompt and chunk TTS at punctuation boundaries.
- **When NOT to build realtime voice at all:** asynchronous use cases (voicemail-style transcription, meeting notes) don't need any of this — batch pipelines are cheaper, more accurate, and easier to evaluate. Reach for the 800 ms machinery only when true conversational rhythm is the requirement.

---

## Interview questions

### Q1 — Why is ~800 ms the magic number for voice-agent round-trip latency?
**Testing:** whether the candidate knows the perceptual basis or just repeats vendor marketing numbers.
**Answer:** It derives from human turn-taking rhythm: gaps between speakers in natural conversation average around 200 ms, and listeners unconsciously interpret longer silences as hesitation or a bad connection. Below ~800 ms a reply feels responsive and barely registers; past ~800 ms pauses become consciously noticeable; past ~1500 ms conversation functionally breaks — users repeat themselves, talk over the agent, or hang up. The number is biology-derived, so no amount of prompt engineering buys it back; it's a budget to engineer against.
**Follow-up trap:** *"So should we target 200 ms everywhere?"* — no; diminishing returns and cost explosion. Human gaps are ~200 ms partly due to biological production limits on our side too; matching sub-800 ms consistently at p99 beats chasing 200 ms at p50, because subjective experience is dominated by the worst turns, not the median one.

### Q2 — Decompose the round-trip latency budget for a cascaded voice agent.
**Answer:** Uplink + client jitter buffer ~50-100 ms; endpointing/end-of-turn detection ~100-500 ms (dominated by the silence threshold policy); streaming STT to a usable partial <250 ms; LLM time-to-first-token ~100-600 ms depending on model size and prompt caching; TTS time-to-first-audio ~90-313 ms depending on engine; plus 50-200 ms of inter-vendor network hops. Summed sequentially that's ~600-1900 ms — the actual differentiator is overlapping stages via streaming, which turns a ~1400 ms sequential pipeline into ~500-700 ms.
**Follow-up trap:** *"Which single stage should we optimize first?"* — measure before answering, but endpointing is statistically the usual culprit because it's pure policy (a silence threshold) rather than model-bound, and its p99 tail drives felt latency. Then TTS vendor choice (155 vs 313 ms median TTFA spread), then LLM first-token (prompt caching, smaller model tier).

### Q3 — Explain the difference between VAD and endpointing.
**Testing:** the conflation of these two is the classic tell of someone who's read about voice agents but hasn't built one.
**Answer:** VAD classifies individual short frames (~20-30 ms) as speech/non-speech — "is there a voice right now?" Endpointing decides whether the *turn* has ended — "should the agent respond now?" They're different layers: VAD is an input (with STT transcript finality and semantics) to the endpointing decision. A breath, a comma pause, and a completed thought are acoustically identical to VAD; only linguistic content separates them.
**Follow-up trap:** *"Why not just raise the silence threshold until interruptions stop?"* — because silence duration contains no information distinguishing hesitation from completion. Raising it trades premature interruptions for a guaranteed dead-air tax on every turn (e.g., 400→800 ms threshold = half a second added to every single reply). The correct fix is semantic endpointing, which scores completeness from content.

### Q4 — Compare energy-based, GMM-based, and neural VAD.
**Answer:** Energy thresholding (loud = speech) is essentially free and fails in any realistic noise — documented since the G.729-era work of 1997. GMM-based (WebRTC VAD) adds spectral features and zero-crossing rate; extremely lightweight pure C, battle-tested, but weak on babble/music/non-stationary noise. Neural VAD (Silero being the open-source default, MIT-licensed, trained across 6,000+ languages of data, ONNX-deployable including browsers; Cobra commercially for MCUs) learns the speech/noise boundary and is robust at low SNR, at modest compute cost. Production stacks overwhelmingly use neural VAD for gating plus a semantic layer for turn decisions.
**Follow-up trap:** *"If Silero is better, why does WebRTC VAD still exist?"* — footprint and ubiquity: pure C, no dependencies, runs anywhere including tiny MCUs where an ONNX runtime doesn't fit, and it's already embedded in millions of browser sessions. Right tool for constrained environments, wrong tool for noisy phone lines.

### Q5 — What is barge-in, and what's the mechanical loop that implements it?
**Answer:** User speech during agent playback, handled as a hard-deadline loop: detect user speech via VAD on the input channel; stop agent audio within ~150 ms; flush the TTS buffer and queued audio; cancel the in-flight LLM generation; reroute incoming audio to STT cleanly. Prerequisite is acoustic echo cancellation so the agent doesn't hear its own TTS via the user's speakerphone and interrupt itself.
**Follow-up trap:** *"Your agent keeps cutting itself off on speakerphone devices — where do you look?"* — the echo path first: TTS output leaking into mic input registers as user speech. Check AEC availability/enabling on the device pipeline, add a playback-state-aware VAD suppression window, and test specifically on speakerphone hardware, because headset-only testing never exposes it.

### Q6 — Cascaded vs speech-to-speech: walk me through choosing for an enterprise support line.
**Answer:** Default cascaded for enterprise support: per-stage transcripts are the audit artifact (what did the caller actually say vs what did the model hear vs what did it answer), model choice stays yours (domain fine-tunes), deployment can be VPC-resident, and cost is predictable ($0.0095-$0.17/min across common stacks vs a ~182x spread across S2S providers). S2S earns the switch when conversational feel is the product differentiator — its ~600-900 ms end-to-end, native prosody, and built-in interruption handling genuinely move satisfaction. Hybrid is legitimate: S2S for conversation with a parallel STT producing the compliance transcript.
**Follow-up trap:** *"S2S gives you transcripts too, so what's really lost?"* — the transcript becomes a derived, vendor-controlled artifact rather than ground truth from a dedicated ASR stage: you can't independently verify it, can't swap the recognizer, and error analysis conflates perception and generation failures into one black box. For regulated conversations that distinction is disqualifying, not cosmetic.

### Q7 — Why do we say the LLM stage's latency is 'first token', and how do you reduce it?
**Answer:** Nothing downstream (sentence chunking, TTS) can begin until the first generated token arrives, so TTFT is the LLM's entire contribution to the latency budget; total generation length affects conversation flow but not initial responsiveness — audio plays while tokens continue streaming. Reduction levers: fast model tier (100-200 ms TTFT vs 250-600 ms), provider-side prompt caching for static system context, regional colocation with the telephony leg, shorter prompts, and async tool design so the model speaks filler ("let me check") while looking things up.
**Follow-up trap:** *"A reasoning model thinks for 8 seconds before answering — usable in voice?"* — only with explicit design: either spoken filler + progress sounds while thinking, or routing such queries off the voice path entirely ("I'll follow up by email"). Silent 8 s dead air guarantees the user talks over the thinking and corrupts the turn; this is a genuine architectural constraint, not a tuning detail.

### Q8 — How does TTS chunking work, and what breaks if you get it wrong?
**Answer:** Streaming TTS synthesizes incrementally, so the orchestrator feeds it text in chunks; the standard is punctuation/sentence boundaries — big enough to preserve prosody, small enough to keep TTFA low. Too-small chunks cause mid-phoneme glitches (audio starting on fragmentary words); too-large chunks (waiting for whole paragraphs) inflate time-to-first-audio directly. Client side, a ~200-300 ms jitter buffer absorbs network variance.
**Follow-up trap:** *"Doesn't sentence-level chunking hurt prosody at chunk seams?"* — somewhat, yes; seam smoothing and SSML-aware splitting mitigate it, and this is one of the genuine (smaller) arguments for S2S, whose prosody is generated globally. It's a real tradeoff, just heavily outweighed by the auditability and flexibility of cascaded in most products.

### Q9 — Your agent's median response is 400 ms but users say it 'feels slow.' Diagnose.
**Answer:** Classic percentile masking: p50 hides the tail, and subjective experience is anchored on worst turns — an average of 400 ms routinely coexists with p99 of 2.5 s. Instrument per-stage latency at p95/p99 (per-stage OTel spans), find the tail source — commonly endpointing policy on hesitant speakers, cold-started connections, uncached prompts, or TTS vendor variance — and alert on tails. Also verify the measurement is true TTFA (user-perceived), not internal stage sums.
**Follow-up trap:** *"After fixing p99, it still feels slightly robotic. Now what?"* — latency is no longer the bottleneck; the residue is interaction dynamics: monotone delivery from over-long responses, missing backchannels, or slightly-off prosody at TTS seams. Cap verbosity, vary pacing, consider S2S/hybrid if feel is the core product metric — and run blind listening tests (ELO-style) rather than trusting internal opinion.

### Q10 — Design the evaluation suite for a production voice agent.
**Testing:** whether evaluation thinking extends beyond text chat evals.
**Answer:** Layered: per-stage metrics (ASR accuracy per accent/noise cohort — e.g., WER moving 4%→9% on one cohort; turn-error rate for endpointing; TTFA p50/p95/p99 end-to-end), task metrics (task-completion rate, intent accuracy), and audio-level quality (naturalness scored via blind ELO comparisons, since a vendor model rotation can flatten affect invisibly). Critically, run it continuously against synthetic calls: nightly simulated personas exercising interruption, background noise, packet loss, code-switching, and hold behavior, gating deploys in CI — catching regressions there instead of via Friday-evening CSAT dips.
**Follow-up trap:** *"We already eval the LLM's answers with an LLM judge — why isn't that enough?"* — because the majority of voice-specific failures happen before or after generation: wrong transcripts confidently answered, clipped digits in dates, flat TTS, rude interruptions. Transcript-level judging is structurally blind to all of them; the compliance owner who "cannot prove HIPAA-sensitive content was handled correctly because there is no audio-level evaluation" is the cautionary version of this exact gap.

### Q11 — Walk through the economics: is a voice agent cheaper than a human agent, and where does it flip?
**Answer:** Representative 2026 numbers: 1,000 calls × 3 min = 3,000 minutes/month at $0.0095-$0.17/min ≈ $29-$510/month in model/API costs versus $4,000+ for human coverage of the same volume — orders-of-magnitude favorable even at premium tiers. It flips when: S2S premium tiers are chosen carelessly (the 182x spread matters at scale), telephony legs and multi-vendor regions add per-hop costs, or quality issues inflate transfer-to-human rates (every escalated call pays twice).
**Follow-up trap:** *"So cost per minute is the number to optimize?"* — no; cost per *resolved* task is. A cheap stack that mis-transcribes SKUs and escalates 30% of calls is dearer than a pricier accurate one; and the tail risk of a compliance incident dwarfs per-minute savings. Optimize resolution rate and containment honestly before shaving milliseconds or cents.

### Q12 — Why does 8 kHz vs 16 kHz audio matter for the latency/quality budget?
**Answer:** Telephony audio is narrowband (8 kHz sampling, 4 kHz Nyquist), losing high-frequency consonant detail; models and VADs trained/exposed at 16 kHz degrade on it (Silero explicitly supports both rates because the mismatch is common). Narrowband raises WER, which cascades into more repair loops and longer effective conversations — so the audio codec choice is part of the quality budget, not just a transport detail. Upsampling narrowband to 16 kHz doesn't recover lost information.
**Follow-up trap:** *"Does narrowband audio at least help latency?"* — marginally (fewer bytes on the wire, negligible next to model latencies) and irrelevantly — bandwidth isn't the constraint in 2026 pipelines; paying an accuracy tax to save microseconds of transport is a bad trade. The real reason telephony stays narrowband is PSTN compatibility, not optimization.

---

## Red flags that fail you

- Quoting "sub-second latency" as a single undifferentiated number with no stage decomposition.
- Using "VAD" and "endpointing" interchangeably — they're different layers answering different questions.
- Proposing a bigger/faster LLM as the fix for a slow-feeling agent (the model is often ~a third of the budget, and only first-token time matters).
- No awareness that streaming/overlap — not raw component speed — is what turns 1400 ms into 600 ms.
- Treating barge-in as an optional nicety rather than a hard-deadline loop with an echo-cancellation prerequisite.
- Recommending speech-to-speech reflexively without weighing auditability, model choice, VPC constraints, or the cost spread.
- Optimizing/reporting latency as a mean with no p95/p99 discipline.
- Conflating this module's realtime-conversation scope with the ASR-accuracy scope of T26-speech-processing.

---

## Cheat card

```
PERCEPTION      human turn gap ~200ms · <800ms feels natural ·
                >1500ms feels broken · optimize p99, not mean

BUDGET (cascaded, 2026)
  uplink+jitter    50-100ms
  endpointing     100-500ms  ← biggest lever, pure policy
  STT partial      <250ms    (Scribe v2 <150ms)
  LLM FIRST TOKEN 100-600ms  ← caching/model tier; total gen ≠ relevant
  TTS FIRST AUDIO  90-313ms  (Gradium 155 · Sonic-3 188 · Turbo v2.5 264 ·
                              Aura-2 313 ms medians)
  network hops     50-200ms  × every vendor leg
  SEQUENTIAL ≈1400ms → STREAMED ≈500-700ms  (overlap is the fix)

VAD             frame-level "is there voice?" — NOT turn-end.
  energy (fails in noise, 1997-documented) → GMM (WebRTC VAD, tiny C) →
  neural (Silero: MIT, 6k+ langs, 8/16kHz, ONNX/browser)
ENDPOINTING     silence timer has NO correct value (hesitation vs done
                is invisible acoustically) → semantic endpointing
                (OpenAI semantic_vad: eagerness low/med/high/auto);
                hangover = hysteresis (G.729: 15×10ms frames overhang)
BARGE-IN        detect → stop ≤150ms → flush TTS + cancel LLM → reroute
                to STT. Needs AEC or agent hears itself.
TTS CHUNKING    punctuation/sentence boundaries; jitter buffer 200-300ms;
                TTFA spread (155 vs 313ms) ≥ a whole barge-in budget
CASCADE vs S2S  cascaded: transcripts, your model, $0.0095-0.17/min, VPC
                S2S: 600-900ms e2e, native prosody/interrupt, ~182x cost
                spread, derived-only transcript → enterprise defaults cascade
LLM IN VOICE    TTFT only matters · filler-speak during tools · cap verbosity
EVAL            per-stage p50/p95/p99 + cohort ASR accuracy + audio-level
                naturalness + nightly synthetic-call regression in CI
```

## Sources

- [The voice agent latency budget: where your 800ms goes — Soniox Voice AI Wiki](https://soniox.com/wiki/voice-agent-latency-budget) — accessed 2026-08-23
- [Building Realtime Voice Agents: Sub-800ms Latency Budget and Barge-In — AI Tech Connect](https://aitechconnect.in/tips/realtime-voice-agents-latency-budget-barge-in-2026) — accessed 2026-08-23
- [Voice Agents and Realtime LLM APIs in 2026 — blog.rajpoot.dev](https://blog.rajpoot.dev/posts/ai/voice-agents-realtime-llm-2026/) — accessed 2026-08-23
- [Semantic VAD for Voice Agents: Turn Detection 2026 — Gradium](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026) — accessed 2026-08-23
- [What Is Voice Activity Detection (VAD)? A 2026 Guide — Cekura](https://www.cekura.ai/blogs/voice-activity-detection) — accessed 2026-08-23
- [Best Voice Activity Detection 2026: Cobra vs Silero vs WebRTC VAD — Picovoice](https://picovoice.ai/blog/best-voice-activity-detection-vad) — accessed 2026-08-23
- [snakers4/silero-vad — GitHub](https://github.com/snakers4/silero-vad) — accessed 2026-08-23
- [Testing Voice Agents: Methods, Metrics, and Tools — Softcery](https://softcery.com/lab/ai-voice-agents-quality-assurance-metrics-testing-tools) — accessed 2026-08-23
- [Real-Time Voice Cloning Technology: A 2026 Build Guide — Forasoft](https://www.forasoft.com/blog/article/real-time-voice-cloning-technology) — accessed 2026-08-23
- [Silero VAD plugin — LiveKit docs](https://docs.livekit.io/agents/logic/turns/vad) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created
