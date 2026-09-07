# Production notes — nanoGPT-class models

## Lineage

Karpathy's nanoGPT is the canonical from-scratch decoder-only transformer
(~300 lines reproducing GPT-2 training). Your lab model has every structural
piece of a modern LLM minus scale: token+position embeddings, pre-LN residual
blocks, manual causal MHA, GELU MLP, tied-or-untied head.

## What production adds

| Concern | Production answer |
|---|---|
| Scale | d_model 4096-12288, layers 32-120+ → billions of params: 12·d²·L dominates |
| Attention cost | FlashAttention (fused, memory-bound, never materializes T×T scores); GQA/MLA shrink KV cache |
| Training | mixed precision bf16, gradient accumulation, ZeRO/FSDP sharding, LR warmup+cosine |
| Positional | RoPE replaces learned positions (extrapolates); ALiBi/YaRN variants |
| Norm | RMSNorm instead of LayerNorm (fewer ops, no bias); SwiGLU instead of GELU MLP |
| Sampling | vLLM/SGLang serving: paged KV, continuous batching |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Loss NaN | LR too high for depth, fp16 overflow | Grad clip, bf16, lower LR |
| Loss plateaus instantly | Bad init / no warmup | GPT-2 init (0.02 std), warmup |
| Memorizes instead of generalizing | Model too big for data | More data or smaller model |
| Causal test fails | Mask off by one (triu diagonal) | Mask STRICT upper triangle |
