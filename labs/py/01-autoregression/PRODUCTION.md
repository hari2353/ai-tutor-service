# Production notes — autoregression, teacher forcing, exposure bias

## Where this actually runs

LLM training is AR modeling at scale: every token is predicted from its prefix,
loss is cross-entropy over next tokens, and the entire training corpus is
teacher-forced (the true prefix is fed at every step) so positions can be
computed in parallel. Inference is the opposite regime: free-running, where the
model consumes its own outputs. The exposure-bias gap you demonstrated is why
long generations can drift even when per-position accuracy is high.

## What production adds

| Concern | Production answer |
|---|---|
| Parallel training | Causal masking + teacher forcing: one forward pass per corpus window |
| Drift on long generations | Decoding-time mitigations (beam, repetition penalties), RAG-style grounding, or RL against sequence-level reward (RLHF optimizes the free-running distribution directly) |
| Scheduled sampling | Bengio et al. 2015: mix teacher-forced and self-fed targets with p rising over training — rarely used in LLM pretraining (parallelism wins) |
| Sequence-level objectives | RLHF / GRPO close the train/test loop mismatch at cost of stability |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Model great on ppl, poor at long generation | Exposure bias + error accumulation | Beam/grounded decode; sequence-level eval, not just ppl |
| Generated text repeats a token forever | Argmax(T=0) on a peaky distribution | Temperature > 0, repetition penalty |
| NLL improves but human eval doesn't | NLL is per-position teacher-forced | Evaluate free-running: end-to-end task metrics |
