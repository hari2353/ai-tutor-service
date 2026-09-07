# Production notes — decoding

## Where this actually runs

Every knob here is a `SamplingParams` field in vLLM/SGLang, a `LogitsProcessor`
in HuggingFace `generate()`, or a server-side default in an LLM gateway.
Production inference servers run this exact code path per token, per request.

## What production adds

| Feature | Real mechanism |
|---|---|
| Batching | One decode loop for hundreds of concurrent requests (continuous batching) |
| Biases | logit_bias, presence/frequency penalties — additive logits-proc adjustments |
| Constrained decoding | grammar/JSON masking (outlines, xgrammar) fused with top-p |
| Speculative decoding | Real: draft model proposes k tokens; target verifies ALL in one forward pass — the accept math is exactly this lab's per-token rule, amortized across the block |
| Seeding | Deterministic per-request rng seeded from request id — reproducible runs |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Temperature 0 not deterministic in prod | Batched kernels + float non-associativity | Accept, or per-request serial decode |
| top_p + top_k both set | They compose (k first, then p) — surprisingly many bugs | Set one, know the order |
| Model loops on a phrase | Argmax on a peaky head | Repetition penalty or top_p |
| Speculative "no speedup" | Draft disagrees too much / short blocks | Bigger agreement or longer draft blocks; measure accept rate |
