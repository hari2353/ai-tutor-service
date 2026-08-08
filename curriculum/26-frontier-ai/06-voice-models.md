# Voice Models: Whisper, TTS, Realtime Speech-to-Speech, Latency Budgets, VAD

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T26-speech-processing`, T05 (attention, inference serving)
> **Updated:** 2026-08-08
> **Module id:** `T26-voice-models` · **Tags:** voice, realtime, latency, vad, barge-in, critical

## The 30-second version

A voice agent is not a text agent with a microphone bolted on: it is a full-duplex, latency-constrained system where the product IS the timing. `T26-speech-processing` covers the ASR pipeline (MFCC → Whisper) as an offline transcription problem; this module is about what changes when transcription has to happen live, in a loop with generation and synthesis, under a human's patience for silence. The 2026 architecture split is cascaded (VAD → streaming ASR → LLM → streaming TTS, each stage independently swappable and debuggable) versus unified speech-to-speech (a single model that consumes audio tokens and emits audio tokens, like OpenAI's `gpt-realtime` or Gemini's native-audio Live API, which cuts a full serialize-to-text-and-back round trip out of the loop and gets voice-to-voice latency to roughly **800ms** end to end, down from the 1.5-2.5s a naive cascaded pipeline produces). The reason voice is a harder engineering problem than chat is that the interaction is **full-duplex**: the user can speak while the agent is speaking, silence does not reliably mean "I am done," and once audio has left the speaker the user has already heard it, so there is no equivalent of editing the last message. That forces four subsystems text agents don't need: a voice activity detector deciding, in under a second, whether a pause is a breath or a turn boundary; a barge-in path that can cancel an in-flight LLM generation and flush in-flight TTS audio in under **~60ms** or the interruption feels ignored; an endpointing policy that trades false interruptions against perceived sluggishness; and a latency budget where every stage from mic capture to first audio sample out is on the critical path of a number a human perceives directly, with **~300ms** the rough line between "conversational" and "noticeably robotic." Get any one of VAD, barge-in, or the latency budget wrong and the product feels broken in a way no amount of LLM quality fixes.

## Why this gets asked

The interviewer wants to know if you have actually shipped a voice product, because the failure modes are invisible until you put a phone in front of a real, impatient human. The classic production failure: an agent that works flawlessly in a demo with polite, turn-taking testers falls apart the moment a real caller says "um" mid-sentence and the VAD fires an early endpoint, or a real caller interrupts to correct themselves and the agent talks over them for 400ms before yielding, or a call center floor's background noise trips the energy gate constantly and the agent never stops "listening" long enough to respond. None of these show up in a text-agent architecture review. They show up as a support ticket that says "the AI kept cutting me off" or "it took forever to respond and then didn't even hear what I said." At staff/principal level, the follow-up is whether you can decompose a latency complaint into the specific stage responsible (ASR partial-hypothesis lag versus LLM time-to-first-token versus TTS time-to-first-audio versus jitter buffer), because "it's slow" is not an actionable bug report and a candidate who cannot break it apart has operated a demo, not a production line.

---

## Lineage: past → present → future

**What came before.** Voice interfaces before 2023 were built as strictly sequential pipelines glued together by application code: a wake-word detector, a cloud ASR call (often batch-oriented, waiting for a full utterance before returning a transcript), a rule-based or intent-classifier NLU stage, a templated or slot-filling dialogue manager, and a separately-hosted TTS engine, each a different vendor with a different latency profile and no shared sense of "the conversation." The specific pain that killed this generation for anything beyond IVR menus and smart-speaker command-and-control was that every hop added latency and lost information: ASR discarded prosody before the NLU stage ever saw it, so a raised, urgent "I need help NOW" and a flat "I need help now" produced the identical downstream string; dialogue was scripted and could not hold an open-domain conversation; and the round-trip through several independently-scaled cloud services routinely put voice-to-voice latency above 2-3 seconds, which is well past the point where a human perceives the system as attentive. Alexa- and Siri-era assistants optimized narrow command recognition extremely well and open-ended conversation not at all.

**Where it stands now.** Two architectures are both genuinely deployed at scale in 2026, and the live disagreement is about where the tradeoff line sits, not which one is "correct." The **cascaded pipeline** — streaming VAD, streaming ASR (partial hypotheses emitted continuously, not batch), an LLM consuming the growing transcript, and streaming TTS beginning to synthesize before the LLM has finished generating — remains the default for most builders because every stage is independently observable, swappable, and correctable: you can log the exact transcript the LLM saw, insert business logic between ASR and generation, and switch TTS vendors without retraining anything. The **unified speech-to-speech model** — OpenAI's `gpt-realtime` (successor to the original GPT-4o Realtime API) and Google's Gemini Live API with native audio — instead consumes and emits audio directly through one model over a persistent WebSocket/WebRTC session, with no intermediate text transcript required for the audio-to-audio path, which removes a full serialize/deserialize hop and gets `gpt-realtime` to roughly **800ms** voice-to-voice "wired right," with the newer `gpt-realtime-2.1` cutting **p95 latency by at least 25%** again on top of that ([OpenAI, Introducing gpt-realtime](https://openai.com/index/introducing-gpt-realtime/), accessed 2026-08-08). Gemini's native-audio Live API makes the same bet, additionally shipping "affective dialog" (tone adapts to the emotion it hears) and "proactive audio," where the model decides whether a detected voice segment warrants a response at all rather than firing generation on every VAD trigger — an explicit attempt to reduce false-positive interruptions at the model level rather than purely in the VAD threshold ([Google Cloud, Gemini Live API on Vertex AI](https://cloud.google.com/blog/products/ai-machine-learning/gemini-live-api-available-on-vertex-ai), accessed 2026-08-08; general availability reached Vertex AI at Google I/O 2026). The live disagreement: unified models produce more natural turn-taking and prosody and shave a real round trip off latency, but you lose the clean, auditable text transcript as an intermediate artifact, which matters enormously for anything regulated, anything requiring deterministic business-logic injection (a payment confirmation step that must not be paraphrased), or anything that needs a debuggable log of exactly what the model "read." Most production voice agents handling anything beyond casual conversation in 2026 are still cascaded for this reason, even though the unified path is faster.

**Where it's heading.** High confidence: the unified speech-to-speech path keeps improving and keeps taking share in consumer and casual-conversation use cases (companion apps, casual assistants) where the auditability tradeoff doesn't bite; `gpt-realtime-2.1`'s 25%+ p95 improvement over its predecessor in a matter of months is the shape of that trend. Medium-high confidence: enterprise and regulated voice agents (support, sales, healthcare intake) stay cascaded for another product cycle at minimum, because the ability to inject deterministic logic between "what was said" and "what the agent decides" is a hard requirement, not a nice-to-have, and unified models don't yet offer an equivalent hook. Speculative, flagged as such: whether VAD as a separate component disappears entirely, folded into the generation model's own judgment of when to speak (Gemini's "proactive audio" is the first visible step in that direction) — if it works reliably, it removes an entire class of false-barge-in bugs that today are handled by tuning thresholds rather than by the model actually understanding conversational structure; this is unproven at scale as of August 2026 and the honest position is "promising direction, not yet the safe default for a production system you don't want to debug via vibes."

---

## Mental model

```
CASCADED PIPELINE                          UNIFIED SPEECH-TO-SPEECH
(each box independently swappable)         (single model, one session)

 mic  ->  VAD  ->  streaming ASR             mic --> audio tokens --> model
          |          |  (partial                                       |
          | silence  |   hypotheses,                                   | audio tokens out,
          | = maybe   |   updated every                                | streamed
          | turn end  |   ~100-300ms)                                  v
          v          v                                              speaker
      endpoint    transcript
      decision       |
          |          v
          |    LLM (streaming, TTFT ~200-500ms)
          |          |
          |          v
          |    streaming TTS (TTFA ~90-300ms,
          |     starts before LLM finishes)
          v          |
      BARGE-IN <-----+---- if VAD fires WHILE TTS is playing:
      CONTROLLER            cancel LLM generation, flush TTS buffer
                             (<60ms), roll back turn state, re-listen

LATENCY BUDGET, cascaded, rough p50 stage costs:
  mic buffering/jitter .......... 20-50ms
  VAD endpoint wait .............. 200-300ms  (the part users FEEL as "listening")
  ASR final-hypothesis lag ....... 100-300ms  (streaming, not batch)
  LLM time-to-first-token ........ 200-500ms
  TTS time-to-first-audio ........ 90-300ms
  network + jitter buffer ........ 20-100ms
  ---------------------------------------------------------------
  TOTAL, cascaded p50 ............ ~800ms-1.5s   (worse under load)
  TOTAL, unified S2S (gpt-realtime) ~800ms wired right, sub-500ms with -2.1

WHY <300ms MATTERS: human turn-taking gaps in natural conversation
average ~200ms; response gaps under ~300ms read as "attentive,"
gaps beyond ~500ms read as the system having to "think," and gaps
beyond 1s read as broken, independent of transcript accuracy.
```

The single fact that explains most voice-agent bugs: **the VAD's silence timeout and the barge-in detector are answering two different questions on the same audio stream** — "has the user finished their turn?" versus "has the user started talking while I'm talking?" — and tuning one to be more patient (fewer false endpoints on hesitant speakers) directly makes the other slower to react (later barge-in detection), because both keys off the same "sustained voice for N ms" heuristic on the same microphone signal.

---

## How it actually works

### Whisper as the ASR component, and where it stops being enough

`T26-speech-processing` derives the MFCC pipeline and Whisper's encoder-decoder architecture in depth; the piece specific to a voice agent is that **Whisper was not designed for streaming**. Whisper processes fixed **30-second** windows: 16kHz mono audio is chopped into non-overlapping 30-second chunks, each converted to an 80-channel (128-channel in `large-v3`) log-mel spectrogram at a 25ms window / 10ms hop, fed through a transformer encoder, and decoded autoregressively token-by-token until an end-of-segment token ([Whisper architecture reference](https://mbrenndoerfer.com/writing/whisper-architecture-encoder-decoder-multilingual-asr), accessed 2026-08-08). That is a batch-shaped design retrofitted for live use by running it on a rolling short window (commonly 2-6 seconds) with overlap-and-stitch logic, which is why most production voice stacks use `faster-whisper`/`large-v3-turbo` rather than the reference implementation: Turbo prunes the decoder from **32 layers to 4** and the parameter count from **1.55B to 809M**, running **2-5x faster** with a small accuracy cost, reporting **7.7% WER** on the LibriSpeech benchmark and roughly **8-12% WER** on real-world meeting/phone audio ([saytowords.com Whisper Turbo benchmark, March 2026](https://www.saytowords.com/blogs/whisper-large-v3-turbo-english-interview-benchmark-2026-03-28/), accessed 2026-08-08). The autoregressive decoder is also the source of Whisper's best-known production failure: it hallucinates confidently on silence and non-speech audio (background music, breathing, dead air), because the model was trained to always emit *something* plausible, and a wrong segment poisons the decoder's own conditioning context for the next window, producing repeated phrases or invented sentences that never occurred. Research in 2025 traced **over 75%** of these non-speech hallucinations to three specific decoder self-attention heads, and targeted fine-tuning of just those heads ("Calm-Whisper") cut the hallucination rate from **99.97% to 15.51%** on the UrbanSound8K non-speech benchmark with **under 0.1%** WER degradation elsewhere ([arXiv 2506.16174, Whisper hallucination study](https://arxiv.org/pdf/2506.16174), accessed 2026-08-08) — the practical takeaway is that a naive Whisper deployment left running on an open mic during silence will eventually transcribe something that was never said, and you need either a VAD gate in front of it or a hallucination-hardened checkpoint, not both belt and no suspenders.

### VAD: the gate that decides whether ASR/LLM ever run

Voice Activity Detection is the cheapest, most load-bearing component in the stack, and it is usually the most under-engineered. Silero VAD, the de facto production default, is a small (**1-2MB**) model that classifies a **30ms**+ audio chunk in under a millisecond on a single CPU thread. A realistic production configuration: an energy gate at roughly **-40 dBFS** to cheaply reject silence before invoking the classifier at all, a classifier confidence threshold around **0.75**, and a **minimum sustained-voice duration of 200-300ms** above that confidence before the VAD commits to "voice detected" rather than firing on a single noisy frame ([Silero VAD production configuration](https://rajatpandit.com/agentic-ai/real-time-audio-vad/), accessed 2026-08-08). That minimum-duration guard is a direct latency-vs-false-positive trade: requiring 200-300ms of sustained voice before triggering **drops the false-barge-in rate by 60-80%**, at the direct cost of adding that same 200-300ms to every legitimate barge-in's reaction time — there is no way to have both a hair-trigger interruption response and immunity to a cough or a keyboard click, and the number you pick is a product decision, not an engineering default.

### The barge-in path, mechanically

Barge-in is not "detect voice and stop talking" — it's a small state machine that has to touch every layer of the stack atomically:

1. VAD fires on the **caller's** audio track while the **agent's** TTS is actively streaming to the speaker.
2. The TTS stream must be **flushed** (stop sending new audio chunks, and ideally fade rather than hard-cut to avoid an audible click) — production target is **under 60ms**, because latency beyond that reads as the agent ignoring the interruption entirely rather than yielding to it.
3. The in-flight LLM generation that was producing the text the TTS was speaking must be **cancelled** server-side, not merely muted client-side, or the model keeps burning tokens and money on a response nobody will hear.
4. The conversation state must be **rolled back** to reflect that the agent's turn was cut short — if the agent had said "Your total is $47.—" before being cut off, the transcript fed to the next LLM call needs to reflect the truncated utterance, not the full sentence the agent intended to say, or the model will confidently continue a sentence the user never heard the end of.
5. The system re-enters listening state for the new, interrupting utterance.

A representative 2026 production instrumentation set: barge-in success rate **97.8%**, false-barge-in rate **1.4%**, TTS-flush **p95 54ms**, LLM-cancel **p95 38ms**, total barge-in handle **p95 142ms**, turn-taking gap **p95 310ms** ([futureagi.com, Voice AI Barge-In 2026 guide](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/), accessed 2026-08-08). Those five numbers, logged per call, are what you'd actually look at to debug a "the AI keeps talking over me" ticket: a healthy false-barge-in rate with a slow TTS-flush p95 means the VAD is fine and your audio pipeline has a buffering problem; a rising false-barge-in rate with fast flush times means the VAD threshold is too sensitive for that caller's environment (background noise, other speakers, a TV on in the room).

### TTS: streaming architecture and the 300ms line

Streaming TTS begins emitting audio before it has synthesized the full response, chunked at sentence or clause boundaries so the agent starts speaking while the LLM is still generating the rest of the answer — this overlap is most of why unified pipelines and well-built cascaded ones can hit sub-second responses despite the LLM's own time-to-first-token being 200-500ms in isolation. Time-to-first-audio (TTFA) is the metric that matters, not total synthesis time: **roughly 300ms is the commonly cited line between "conversational" and "robotic"** ([Gradium, Low-Latency TTS APIs 2026](https://gradium.ai/content/best-low-latency-tts-apis-2026), accessed 2026-08-08). Architecture matters here in a way it usually doesn't for text generation: Cartesia built its Sonic TTS line on **state-space models (SSMs)** rather than a standard transformer specifically to flatten the latency curve — Sonic 3.5 reports **75-90ms** TTFA over WebSocket, and the Sonic Turbo variant claims **sub-40ms**, with the SSM architecture's main selling point being *consistent* latency at p99, not just a good median, which is the number that actually determines your worst-case caller experience ([futureagi.com, ElevenLabs vs Cartesia 2026](https://futureagi.com/blog/elevenlabs-vs-cartesia-tts-2026/), accessed 2026-08-08). ElevenLabs, by contrast, optimizes primarily for voice realism and cloning quality with its Flash v2.5 model trading some of that latency headroom away, reporting **~288ms p50** TTFA against Cartesia Sonic-3's **~188ms p50** in independent comparisons ([codesota.com, ElevenLabs vs Cartesia 2026](https://www.codesota.com/speech/elevenlabs-vs-cartesia), accessed 2026-08-08). The practical decision is quality-vs-latency, and it is a real tradeoff, not a solved problem: a customer-support IVR replacement cares more about the 300ms line than voice realism; a narration or dubbing product cares much less about TTFA and much more about prosody and naturalness.

---

## Build it from scratch

The minimal thing that is genuinely a voice agent and not a toy: a VAD-gated audio ring buffer feeding a streaming ASR client, a barge-in controller that owns cancellation of both the LLM stream and the TTS stream, and instrumentation on every stage boundary from the first call. No lab folder exists for this module yet; the sketch below is the shape to build one from.

```python
# untested sketch -- minimal voice-agent turn loop, cascaded architecture.
# Illustrates the state machine, not a production-grade audio pipeline.
import asyncio
import time

VAD_MIN_VOICE_MS = 250          # sustained-voice guard before committing
ENDPOINT_SILENCE_MS = 700       # silence duration that ends a user turn
BARGE_IN_FLUSH_DEADLINE_MS = 60 # TTS must stop within this after VAD fires

class TurnState:
    IDLE, USER_SPEAKING, AGENT_THINKING, AGENT_SPEAKING = range(4)

class VoiceAgentLoop:
    def __init__(self, vad, asr_stream, llm_stream, tts_stream):
        self.vad, self.asr, self.llm, self.tts = vad, asr_stream, llm_stream, tts_stream
        self.state = TurnState.IDLE
        self.voice_ms = 0.0
        self.silence_ms = 0.0
        self._llm_task: asyncio.Task | None = None
        self._tts_task: asyncio.Task | None = None

    async def on_audio_frame(self, frame_bytes: bytes, frame_ms: float, t_recv: float):
        is_voice, conf = self.vad.classify(frame_bytes)   # <1ms, Silero-class model

        if self.state == TurnState.AGENT_SPEAKING and is_voice and conf > 0.75:
            self.voice_ms += frame_ms
            if self.voice_ms >= VAD_MIN_VOICE_MS:
                await self._barge_in(t_recv)               # <-- the critical path
            return

        if is_voice and conf > 0.75:
            self.voice_ms += frame_ms
            self.silence_ms = 0.0
            if self.state == TurnState.IDLE:
                self.state = TurnState.USER_SPEAKING
            await self.asr.push(frame_bytes)                # streaming partials
        else:
            self.silence_ms += frame_ms
            self.voice_ms = 0.0
            if self.state == TurnState.USER_SPEAKING and self.silence_ms >= ENDPOINT_SILENCE_MS:
                await self._end_user_turn()                 # endpoint decision

    async def _barge_in(self, t_fired: float):
        t0 = time.monotonic()
        if self._tts_task:
            self._tts_task.cancel()                         # must land <60ms
        if self._llm_task:
            self._llm_task.cancel()                          # stop paying for it
        self.state = TurnState.USER_SPEAKING
        self.voice_ms = 0.0
        flush_ms = (time.monotonic() - t0) * 1000
        assert flush_ms < BARGE_IN_FLUSH_DEADLINE_MS, f"flush too slow: {flush_ms:.0f}ms"

    async def _end_user_turn(self):
        transcript = await self.asr.finalize()               # last partial -> final
        self.state = TurnState.AGENT_THINKING
        self._llm_task = asyncio.create_task(self._respond(transcript))

    async def _respond(self, transcript: str):
        self.state = TurnState.AGENT_SPEAKING
        self._tts_task = asyncio.create_task(
            self.tts.stream(self.llm.stream(transcript)))    # TTS starts on first
        await self._tts_task                                 # LLM chunk, not full text
        self.state = TurnState.IDLE
```

The pieces this sketch elides but a real build must not: jitter-buffer handling for network audio, a proper fade instead of a hard cut on TTS flush, cancellation actually reaching the LLM provider (not just stopping local consumption of a stream you're still being billed for), and separating the VAD's two jobs (endpointing vs. barge-in detection) into differently-tuned instances rather than one threshold serving both.

---

## How it's done in production

Nobody hand-rolls the state machine above at scale; the managed layer is what most teams actually build on. **LiveKit Agents** and **Pipecat** are the dominant open frameworks for wiring VAD, streaming ASR, an LLM, and streaming TTS into a managed WebRTC session with barge-in handling built in, letting you swap any one component (say, Deepgram for Whisper, or Cartesia for ElevenLabs) without rewriting the turn-taking logic. **Twilio** and **Vonage** remain the dominant telephony bridges for PSTN calls, where the 8kHz narrowband constraint from `T26-speech-processing` still applies and materially raises ASR WER versus 16kHz audio. The unified alternative is calling `gpt-realtime` or the Gemini Live API directly over a persistent WebSocket/WebRTC session and letting the provider own VAD, turn-taking, and barge-in internally — less integration work, less observability, and (as of August 2026) still the harder path for regulated flows that need a deterministic, auditable transcript.

| Symptom | Cause | Fix |
|---|---|---|
| Agent frequently cuts users off mid-sentence, especially on hesitant or non-native speakers | Endpoint silence threshold too short (commonly under 500ms) for speakers who pause mid-thought; VAD confidence threshold too low, firing on breath noise | Raise `ENDPOINT_SILENCE_MS` to 700-900ms for general use; consider a semantic endpointer (a lightweight classifier judging whether the transcript-so-far is a complete thought) layered on top of the pure-silence VAD rather than silence duration alone |
| Users report the agent "talks over me" or ignores interruptions | TTS flush latency exceeds ~60-100ms, or the LLM generation isn't actually cancelled server-side so tokens keep streaming into a TTS buffer that was supposedly stopped | Instrument and alert on TTS-flush p95 and LLM-cancel p95 separately; verify cancellation is server-acknowledged, not just client-side stream abandonment, which leaves the provider still generating (and billing) |
| Transcripts contain sentences that were never spoken, especially during silence or hold music | Whisper (or any autoregressive ASR) hallucinating on non-speech audio; a bad segment poisoning the decoder's conditioning context for subsequent windows | Gate ASR invocation behind VAD so it never runs on confirmed silence; use a hallucination-hardened checkpoint (Calm-Whisper-style head fine-tuning) or a confidence-threshold discard on segments the decoder itself scores low |
| p50 latency looks fine in dashboards but real callers report the agent feels slow | p50 hides tail behavior; a stage with a fat right tail (cold model load, TTS provider regional failover, ASR retry on a dropped partial) dominates perceived experience even though it rarely shows in an average | Track p95/p99 per stage, not just p50, and specifically watch TTFA and LLM TTFT tails; a jitter buffer sized for p50 network conditions will starve audio on every p90+ network hiccup |
| False-barge-in rate spikes in specific deployments (call centers, homes with TVs on) | VAD tuned in a quiet test environment; production acoustic environment has sustained background voice/noise the energy gate and classifier weren't validated against | Re-tune VAD thresholds per deployment acoustic profile, not globally; add an explicit "agent's own TTS audio echo-cancelled out of the input" check, since acoustic echo leaking back into the mic is a common false-barge-in source distinct from ambient noise |

---

## Tradeoffs & when NOT to use it

**When the interaction doesn't need real-time turn-taking at all.** Voicemail transcription, meeting notes, podcast indexing — none of this needs VAD-gated streaming, barge-in handling, or a sub-second latency budget. Reach for batch Whisper (or a managed batch ASR API) and skip the entire real-time stack; building a full-duplex voice agent architecture for an offline transcription job is pure overhead.

**When you need an auditable, deterministic transcript as a compliance artifact.** Unified speech-to-speech models are faster and more natural, but the "no intermediate text" property that buys the latency also removes the clean, injectable checkpoint where you'd assert "read this exact confirmation string verbatim" or log "this exact sentence was presented to the caller." Regulated flows (financial disclosures, medical intake, anything requiring a callback-verifiable record of what was said) should stay cascaded specifically so the transcript is a first-class, auditable object.

**When your product is genuinely text-first with voice as an accessibility layer.** If most sessions are typed and voice is an occasional input mode, the ROI on tuning VAD thresholds, barge-in latency, and TTS provider selection per acoustic environment is low; a simpler push-to-talk (no continuous VAD, no barge-in state machine, the user explicitly signals start/stop) removes an entire category of endpointing bugs at the cost of a less "natural" feel that a low-volume use case usually doesn't need.

**When latency truly doesn't matter and quality does.** Audiobook narration, dubbing, voice cloning for media production — none of this is on a human's real-time patience clock, so trade the low-TTFA models (Cartesia-class) for the highest-fidelity, slowest ones, and skip streaming entirely in favor of full-utterance synthesis with more context for prosody.

**Be honest about accented and code-switched speech.** Every latency number above assumes clean, single-speaker, single-language audio close to a microphone. Real deployments see accented English, code-switching mid-sentence, overlapping speakers, and phone-quality 8kHz audio, all of which raise WER well above the clean-benchmark numbers and directly increase both false endpoints (ASR is less confident, takes longer to stabilize a partial) and false barge-ins (VAD classifiers trained predominantly on clean data misfire more on unfamiliar acoustic patterns). If your user base is not the demo's user base, budget real time to re-tune thresholds against your actual traffic, not the vendor's benchmark.

---

## Interview questions

### Q1 — Walk me through the latency budget of a cascaded voice agent, stage by stage.
**Testing:** whether you actually understand where the milliseconds go, or just know the product is "fast" or "slow."
**Answer:** Roughly: mic buffering/jitter 20-50ms, VAD endpoint wait 200-300ms (the silence duration the system waits before deciding the user is done), streaming ASR final-hypothesis lag 100-300ms, LLM time-to-first-token 200-500ms, TTS time-to-first-audio 90-300ms, network/jitter buffer 20-100ms, summing to roughly 800ms-1.5s at p50 for a well-built cascaded stack, worse under load. Unified speech-to-speech models like `gpt-realtime` remove the ASR-finalize-then-serialize-to-text hop and land around 800ms wired right, with `gpt-realtime-2.1` cutting p95 by at least 25% further.
**Follow-up trap:** "So just use the unified model, it's faster." Not always the right call — unified models remove the intermediate text transcript as an auditable, injectable checkpoint, which many regulated or business-logic-heavy flows need. Faster isn't free; you're trading observability and deterministic control for latency.

### Q2 — What's the difference between the VAD's job in endpointing versus its job in barge-in detection?
**Testing:** whether you understand that these are two different questions on the same signal, not one feature.
**Answer:** Endpointing asks "has the user finished their turn?" — it fires on sustained silence after voice, and a longer wait (700-900ms) reduces false early cutoffs at the cost of added latency. Barge-in asks "has the user started talking while the agent is talking?" — it fires on sustained voice detected on the input track during agent playback, and needs to be fast (a 200-300ms minimum-duration guard is typical) because a slow reaction reads as the agent ignoring the interruption.
**Follow-up trap:** "So tune the VAD to be more sensitive for better barge-in." That directly worsens false-positive endpointing and vice versa — both are reading the same sustained-voice signal with the same underlying classifier, so making the system more eager to detect a barge-in (shorter minimum duration, lower confidence threshold) also makes it more prone to firing on a cough during normal listening. Production systems commonly run the VAD with different thresholds/instances for the two jobs rather than sharing one setting.

### Q3 — A caller says the agent "keeps talking over me." How do you debug it?
**Testing:** operational instinct — can you decompose a vague complaint into instrumented, per-stage numbers.
**Answer:** Pull per-call barge-in metrics, not aggregate averages: TTS-flush p95, LLM-cancel p95, total barge-in-handle p95, and false-barge-in rate. If flush/cancel times are healthy but false-barge-in rate is low and the complaint persists, the issue is likely endpointing (agent starting to respond too early, before the user actually finished) rather than barge-in at all. If flush p95 is elevated, the TTS pipeline isn't actually stopping audio output fast enough — check whether cancellation is server-acknowledged or just client-side stream abandonment, since the latter leaves the provider still generating.
**Follow-up trap:** "The dashboard p50 for everything looks fine." p50 hides exactly this kind of complaint — a caller experiencing a bad interaction is very likely to be in the tail, not the median. Ask for p95/p99 per stage before concluding anything is healthy.

### Q4 — Why does Whisper hallucinate on silence, and what would you do about it in production?
**Testing:** depth on ASR failure modes beyond "sometimes it's wrong."
**Answer:** Whisper's decoder is autoregressive and trained to always produce plausible tokens; on silence or non-speech audio (background music, dead air) there's no genuine speech signal to condition on, so the model emits a fluent but invented transcript, and because each 30-second window's decoding conditions partly on prior context, one bad segment can poison the next, producing loops or invented sentences. 2025 research traced over 75% of these hallucinations to three specific decoder self-attention heads; targeted fine-tuning of those heads cut the hallucination rate from 99.97% to 15.51% on a non-speech benchmark with under 0.1% WER cost elsewhere. In production, the cheap fix that matters most is gating ASR invocation behind VAD so it simply never runs on confirmed silence, which prevents the majority of real-world instances without touching the model at all.
**Follow-up trap:** "Can't you just filter hallucinated transcripts with a confidence threshold?" Partially — low-confidence segments can be discarded, but hallucinations are sometimes emitted with high model confidence precisely because the model is fluently continuing a poisoned context, so confidence filtering alone is not a complete fix; VAD gating and/or a hallucination-hardened checkpoint are the more reliable layers.

### Q5 — Compare a unified speech-to-speech model with a cascaded pipeline. When would you choose each?
**Testing:** architectural judgment, not brand preference.
**Answer:** Unified (gpt-realtime, Gemini Live native audio) processes audio-in to audio-out through one model over a persistent session, removing the serialize-to-text-and-back hop, producing more natural prosody and turn-taking and lower end-to-end latency (~800ms and improving). Cascaded (VAD → streaming ASR → LLM → streaming TTS) keeps an explicit text transcript as an intermediate, auditable artifact, lets you swap any component independently, and lets you inject deterministic business logic (confirmation strings, compliance checks) between what was heard and what the agent decides to say. Choose unified for casual, latency-sensitive, low-compliance-risk conversation; choose cascaded when you need an auditable transcript, deterministic control points, or component-level debuggability.
**Follow-up trap:** "Unified is strictly better since it's faster and more natural." No — the missing intermediate transcript is a real capability loss for anything regulated or anything needing precise control over exactly what gets said, not just a stylistic preference.

### Q6 — Why is 300ms treated as a meaningful threshold for voice UX?
**Testing:** whether the number is understood or just memorized.
**Answer:** Natural human conversational turn-taking gaps average around 200ms; response latency under roughly 300ms reads to a listener as "attentive," latency beyond ~500ms reads as the system "thinking," and latency beyond a second or so reads as broken, independent of how accurate or well-written the response actually is — this is a perceptual/psycholinguistic threshold, not an engineering convention, which is why TTS providers specifically report and compete on time-to-first-audio rather than total synthesis time.
**Follow-up trap:** "So every stage needs to individually be under 300ms?" No — it's the end-to-end perceived gap that matters, and streaming (TTS starting before the LLM finishes generating, ASR emitting partials before the utterance ends) is precisely the technique that lets a pipeline whose individual stages each take 200-500ms still feel responsive, because the stages overlap rather than execute strictly sequentially.

### Q7 — Design the VAD configuration for a call center voice agent, and justify the numbers.
**Testing:** whether you can make and defend a concrete tuning decision, not just cite a framework.
**Answer:** Start from Silero-class defaults (energy gate ~-40dBFS, classifier confidence 0.75, minimum sustained voice 250ms) but re-tune for the actual acoustic environment: call center audio typically has more background noise and cross-talk than a demo environment, so I'd raise the minimum-duration guard for endpointing to reduce false triggers from ambient chatter, while keeping barge-in's minimum duration tighter to avoid the agent talking over legitimate interruptions — accepting a higher false-barge-in rate there is usually the safer failure mode for a support context than making callers feel ignored. I'd also validate against recorded production audio from that specific center, not the vendor's clean benchmark, since accented and phone-quality (8kHz) audio measurably raises both ASR WER and VAD misfire rates.
**Follow-up trap:** "Isn't 8kHz phone audio a Whisper problem, not a VAD problem?" Both — narrowband telephony loses high-frequency consonant detail that hurts ASR accuracy, but it also changes the spectral profile the VAD's energy gate and classifier were tuned against, so a VAD threshold validated on 16kHz clean audio can misbehave on 8kHz telephony independent of what happens downstream in ASR.

### Q8 — A voice agent's LLM-cancel p95 is fast (38ms) but users still perceive slow interruption handling. What's your hypothesis?
**Testing:** whether you understand that barge-in handling is a chain, and a fast link doesn't guarantee a fast chain.
**Answer:** LLM-cancel being fast only means the model stops generating quickly — it says nothing about whether the TTS buffer already holding previously-generated audio actually stops playing quickly, or whether the client-side audio player has its own buffer that continues playing already-downloaded chunks after the server-side cancellation lands. I'd check TTS-flush p95 specifically (target under ~60ms) and separately check client-side playback buffer depth, since a several-hundred-millisecond client buffer would make the interruption feel slow even with instant server-side cancellation.
**Follow-up trap:** "So just make the client buffer as small as possible." That trades interruption responsiveness for playback robustness — an undersized client buffer starves and produces audible glitches on any network jitter, so the real fix is usually an explicit flush signal that clears the client buffer on barge-in rather than shrinking the buffer's steady-state size.

### Q9 — Why can't you just lower the VAD's minimum-duration threshold to near zero to make barge-in instant?
**Testing:** whether you grasp the false-positive tradeoff as a hard constraint, not a tuning knob you can zero out.
**Answer:** A minimum-duration guard of roughly 200-300ms exists specifically because single-frame or very-short voice detections are dominated by non-speech transients — coughs, keyboard clicks, breath, acoustic echo of the agent's own TTS leaking back into the mic. Removing the guard directly raises the false-barge-in rate (empirically, requiring the sustained-duration guard drops false-barge-in by 60-80% relative to firing on any single positive frame), and a system that stops talking every time the caller breathes audibly is a worse experience than one with a slightly slower but reliable interruption response.
**Follow-up trap:** "What about echo cancellation — doesn't that solve the agent's-own-voice problem?" Acoustic echo cancellation reduces but doesn't eliminate the agent's own TTS output leaking into the barge-in detector's input, especially on speakerphone or poor hardware; production systems still need the duration/confidence guard as a second line of defense even with AEC in the pipeline.

### Q10 — Your voice agent works well in testing but callers on older phones report constant transcription errors. Diagnose it.
**Testing:** whether you connect an acoustic/telephony fact to a downstream symptom, rather than assuming a model bug.
**Answer:** Most likely a bandwidth mismatch: PSTN and older phone audio is frequently 8kHz narrowband (4kHz Nyquist limit), which loses the higher-frequency consonant detail (distinguishing sounds like "s" versus "f") that a 16kHz-trained ASR model relies on, producing measurably higher WER on that traffic even though nothing in the model itself changed. I'd confirm by comparing WER segmented by inbound audio sample rate/codec rather than assuming a general model regression, and if narrowband traffic is a meaningful fraction of calls, either upsample with awareness that it doesn't recover lost information, or evaluate an ASR model/checkpoint specifically validated on telephony-band audio.
**Follow-up trap:** "Can't you just upsample 8kHz to 16kHz before feeding Whisper?" Upsampling changes the sample rate but cannot recreate frequency content that was never captured — it will stop the model from erroring on a rate mismatch but will not recover the lost accuracy; the WER gap versus true 16kHz audio remains.

### Q11 — Staff-level: you're deciding whether to migrate a mature cascaded voice product to a unified speech-to-speech model. What's your evaluation plan?
**Testing:** judgment under a real bet-sizing decision, not enthusiasm for the newer architecture.
**Answer:** I'd frame it as: what does the migration buy (latency, naturalness) against what it costs (loss of the auditable text transcript, loss of independent per-stage swappability and observability, loss of deterministic injection points for compliance-critical utterances). Concretely: run both architectures in shadow mode against a sample of real traffic, compare end-to-end p50/p95/p99 latency and barge-in metrics, and separately audit whether any current business logic depends on inspecting or modifying the transcript before the agent speaks — if it does, that's either a hard blocker or requires the unified provider to expose an equivalent hook, which as of August 2026 is inconsistent across providers. I would not migrate a compliance-sensitive flow purely on a latency win without that audit.
**Follow-up trap:** "What if the unified model is just strictly faster and sounds better in every test?" Faster and more natural in aggregate testing doesn't address the specific compliance/auditability requirement directly — a staff-level answer names the actual blocking constraint (deterministic transcript control) rather than treating this as a pure quality-vs-quality comparison.

### Q12 — Why is voice a harder agent-engineering problem than text, structurally?
**Testing:** whether you can articulate the structural reasons rather than just "it's real-time."
**Answer:** Four structural differences. First, full-duplex: unlike a text chat where turns are unambiguous (a submitted message ends a turn), voice has no hard boundary, so the system must infer turn completion probabilistically from silence, with real cost either way it's wrong. Second, no undo: once audio has played through a speaker, the user has already heard it, so there's no equivalent of a text UI silently correcting or retracting a partial response — a mistake is public and instant. Third, barge-in requires actively interrupting and rolling back in-flight generation and synthesis under a tight deadline, which text agents never need to do since a user simply keeps typing while the previous response sits there unread. Fourth, latency is perceived directly and continuously rather than tolerated the way it is in a chat UI with a visible "typing" indicator — a human's patience for silence on a phone call is measured in a few hundred milliseconds, not the several seconds a chat interface can comfortably absorb with a loading spinner.
**Follow-up trap:** "Isn't that just a UX problem, not an architecture problem?" No — each of those four properties forces a specific architectural component that text agents simply don't need (VAD, a barge-in controller with cancellation across every stage, streaming synthesis overlapped with generation), so it's a genuine systems difference, not a surface-level UI difference layered on the same underlying agent loop.

---

## Red flags that fail you

- Saying "voice agents are just chat agents with speech-to-text and text-to-speech bolted on." That ignores full-duplex interaction, barge-in, and the perceptual latency constraint entirely.
- Treating p50 latency as sufficient evidence a voice pipeline is healthy. Voice UX complaints live in the tail; p95/p99 per stage is the minimum bar.
- Not knowing the difference between endpointing (turn-end detection) and barge-in detection (mid-agent-speech interruption detection) as distinct problems on the same VAD signal.
- Claiming Whisper is streaming-native. It processes fixed 30-second windows and has to be retrofitted with rolling-window logic for live use.
- Proposing to zero out the VAD's minimum-duration guard "for faster barge-in" without acknowledging the false-positive cost.
- Recommending a unified speech-to-speech model for a compliance-sensitive flow without flagging the loss of an auditable text transcript.
- Not knowing that TTS quality/latency is a real architectural tradeoff (SSM-based low-latency models like Cartesia versus higher-fidelity, higher-latency models like ElevenLabs), and picking one without asking what the product actually needs.
- Attributing all ASR errors to "the model is bad" without checking sample rate/telephony bandwidth as a first-class variable.

## Cheat card

```
CASCADED       VAD -> streaming ASR -> LLM -> streaming TTS. Auditable
               transcript, independently swappable stages.
UNIFIED S2S    gpt-realtime, Gemini Live native audio. Audio-in/audio-out,
               one model, no intermediate transcript. ~800ms voice-to-voice.
LATENCY BUDGET mic 20-50ms | VAD endpoint wait 200-300ms | ASR lag 100-300ms
               | LLM TTFT 200-500ms | TTS TTFA 90-300ms | net 20-100ms.
300ms LINE     rough threshold: conversational vs. robotic-feeling response.
WHISPER        encoder-decoder, 30s FIXED window, 80/128-ch log-mel,
               25ms/10ms hop. Autoregressive decoder -> hallucinates on
               silence (poisons next-window context).
LARGE-V3-TURBO decoder 32->4 layers, 1.55B->809M params, 2-5x faster,
               7.7% WER (LibriSpeech), 8-12% real-world.
HALLUCINATION  75%+ traced to 3 decoder attn heads. Targeted fine-tune
               (Calm-Whisper): 99.97%->15.51% on non-speech, <0.1% WER cost.
SILERO VAD     ~1-2MB, <1ms per 30ms chunk. Gate -40dBFS, conf 0.75,
               min duration 200-300ms (drops false-positive 60-80%).
BARGE-IN       VAD fires during TTS playback -> flush TTS (<60ms) ->
               cancel LLM server-side -> roll back turn state -> re-listen.
               Prod target: flush p95 54ms, cancel p95 38ms, handle p95 142ms.
TTS TTFA       Cartesia Sonic 3.5: 75-90ms. Sonic Turbo: <40ms.
               ElevenLabs Flash v2.5: ~288ms p50 (quality-optimized).
WHY HARDER     full-duplex (no clean turn boundary) + no undo (audio
               already heard) + barge-in requires cross-stack cancellation
               + latency perceived directly, no "typing..." buffer.
TELEPHONY      8kHz narrowband (4kHz Nyquist) loses consonant detail vs
               16kHz standard. Upsampling does NOT recover lost accuracy.
```

## Sources

- [Introducing gpt-realtime and Realtime API updates for production voice agents (OpenAI)](https://openai.com/index/introducing-gpt-realtime/) — accessed 2026-08-08
- [New Realtime models on the API: gpt-realtime-2.1 and gpt-realtime-2.1-mini (OpenAI Developer Community)](https://community.openai.com/t/new-realtime-models-on-the-api-gpt-realtime-2-1-and-gpt-realtime-2-1-mini/1385896) — accessed 2026-08-08
- [Gemini Live API available on Vertex AI (Google Cloud Blog)](https://cloud.google.com/blog/products/ai-machine-learning/gemini-live-api-available-on-vertex-ai) — accessed 2026-08-08
- [Whisper Large v3 Turbo on an English Interview — 2026 Benchmark (saytowords.com)](https://www.saytowords.com/blogs/whisper-large-v3-turbo-english-interview-benchmark-2026-03-28/) — accessed 2026-08-08
- [Whisper Architecture: Encoder-Decoder Speech Recognition (Michael Brenndoerfer)](https://mbrenndoerfer.com/writing/whisper-architecture-encoder-decoder-multilingual-asr) — accessed 2026-08-08
- [Hallucination Level of Whisper: non-speech attention-head study (arXiv 2506.16174)](https://arxiv.org/pdf/2506.16174) — accessed 2026-08-08
- [How to Use Silero VAD: Real-Time Voice Activity Detection in Python](https://rajatpandit.com/agentic-ai/real-time-audio-vad/) — accessed 2026-08-08
- [Voice AI Barge-In and Turn-Taking: A 2026 Implementation Guide (futureagi.com)](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/) — accessed 2026-08-08
- [Best Low-Latency TTS APIs in 2026: TTFA, P99 and Pipeline Impact (Gradium)](https://gradium.ai/content/best-low-latency-tts-apis-2026) — accessed 2026-08-08
- [ElevenLabs vs Cartesia: 2026 Streaming TTS Deep Comparison (futureagi.com)](https://futureagi.com/blog/elevenlabs-vs-cartesia-tts-2026/) — accessed 2026-08-08
- [ElevenLabs vs Cartesia Sonic (2026): Quality vs Latency Showdown (CodeSOTA)](https://www.codesota.com/speech/elevenlabs-vs-cartesia) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
