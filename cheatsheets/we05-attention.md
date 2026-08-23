# Attention: QKV, √dk, MHA→MQA→GQA→MLA, FlashAttention

> Sprint weekend 5 · source: `curriculum/05-llm-internals/03-attention.md`

```
ATTENTION       softmax(QK^T / sqrt(d_k)) V
SCALE PROOF     Var(q.k) = d_k (sum of d_k iid unit-variance products) -> std = sqrt(d_k)
                divide by sqrt(d_k) restores unit variance; /d_k over-shrinks -> near-uniform softmax
COST            O(n^2 d_k) time, O(n^2) memory per head (naive) -- memory is the real limiter
                n=8192, fp16, 1 head: ~128MB just for the score matrix
KV CACHE/TOKEN  2 * n_kv_heads * d_head * bytes_per_elem  (2 = K and V)
WORKED EX       70B, 80 layers, GQA-8, d_head=128, bf16: 0.32 MB/token; 4k ctx=1.3GB; 128k ctx=42GB/seq
MHA->MQA->GQA   MQA: cache / h (h = query heads); GQA: cache / (h/g); Llama 70B: h=64, g=8 -> 8x
MLA             low-rank latent for K,V, not discrete heads; DeepSeek-V3 ~70KB/tok vs 192-328KB/tok GQA
                K up-projection foldable into Q proj (linear composition) -- no extra decode compute
FLASHATTN       exact, not approximate -- tiling + online softmax, never materializes n x n in HBM
FA2             ~2x over FA1, 50-73% peak FLOPs on A100
FA3 (H100)      1.5-2.0x over FA2 fp16; ~740 TFLOPs/s fp16 (75%); 840 BF16 (85%); ~1.2-1.3 PFLOPs/s fp8
FA3 TECHNIQUES  warp-specialized async TMA overlap, interleaved matmul/softmax, fp8 incoherent processing
NEVER RETROFIT  GQA/MLA are pretraining-time architecture decisions, not inference-time config flags
```
