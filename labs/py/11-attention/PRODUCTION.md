# Production notes — attention at serving time

## What you'd actually use

| Concern | Naive (this lab) | Production |
|---|---|---|
| Kernel | materialised `n×n` scores, `softmax` then `@V` | FlashAttention-2/3 via PyTorch SDPA / `flash-attn` / FlashInfer |
| Masking | additive `-inf` matrix | kernel flags (`is_causal=True`) + block-level skip — masked tiles are never read |
| Heads | one `(h, n, d)` batch | fused QKV projection, head-dim pinned to what the kernel supports |
| KV cache | numpy `vstack` per step | paged blocks (vLLM PagedAttention), prefix reuse, per-layer tensors on device |

**Do not ship the naive version to a GPU path.** At `n = 8192`, one fp16 score matrix is ~128 MB *per head, per layer* — the O(n²) memory is the bottleneck, not FLOPs. FlashAttention computes the identical function without ever writing that matrix.

## What the real ones add over yours

- **Fused projections** — real stacks do one `(n, 3·d_model)` matmul and split, not three separate ones. Your single-matmul-per-projection MHA is the same idea one level down.
- **Kernel-aware masks** — causal is a fast-path flag; arbitrary additive masks can silently drop you to a slower kernel. Verify which kernel actually ran, not which you requested.
- **Paged KV caches** — appending with `vstack` copies every step. Serving engines allocate fixed-size pages and never move existing keys.
- **GQA/MLA before paging** — cutting cached heads (architecture, pretraining-time) beats cleverly storing full-MHA caches (serving-time). Llama-70B GQA-8: ~0.32 MB/token vs ~2.5 MB/token for hypothetical MHA.
- **Precision control** — production runs bf16/fp8; the softmax max-subtraction you implemented is exactly why that survives: exponents stay ≤ 0 in any precision.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| OOM only at long context | cache sized for short-context tests | budget bytes/token × seq_len × layers × batch up front |
| NaN attention output at inference | an all-masked row hit softmax (`-inf − -inf`) | keep ≥1 unmasked key per query (self always) or use large-negative finite bias |
| Quality cliff after switching to MQA | one shared KV head lost positional diversity | GQA with 4–8 groups; retraining required either way |
| Slower than expected decode | mask dtype/layout forced kernel fallback | pass `is_causal`, contiguous layouts, supported head_dim |
| Weights near-uniform, model can't focus | someone "fixed" instability by scaling by `d_k` instead of `√d_k` | variance must land back at ~1; `/d_k` overshoots toward uniform |

## Cost & latency

Decode-step cost is dominated by reading the cache, not computing the new row: each step re-reads `2 · n_kv_heads · t · d_head · bytes`. That linear-in-t read per token is why cache compression (GQA/MLA) and paging exist. Your lab's equivalence test — incremental step == full-recompute row ≤1e-5 — is precisely the invariant every serving engine's regression suite checks after touching cache layout.

## The 3 questions an interviewer asks after this

1. *"Your incremental step matches full recompute. Why is it still not free?"* — correctness ≠ cost: you skip recomputation but still re-read the whole cache per token; that's the bandwidth wall paging/compression attack.
2. *"Why subtract the max inside softmax rather than clamp logits?"* — clamping changes the function; shifting doesn't (softmax is shift-invariant). Same reason FlashAttention's online rescaling is exact, not approximate.
3. *"Where does causality actually live in serving?"* — nowhere in a mask: the cache physically contains only past+current keys, so the step cannot cheat. Masks are a training-time batching convenience.
