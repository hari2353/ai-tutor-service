# Attention: QKV, √dk, MHA→MQA→GQA→MLA, FlashAttention

> **Track:** T05 LLM Internals · **Time:** 3h · **Prereqs:** T05-autoregression, T05-tokenization · **Updated:** 2026-07-26
> **Module id:** `T05-attention` · **Tags:** sprint, internals, critical

## The 30-second version

Attention is a soft, differentiable dictionary lookup: a query is compared against every key via dot product, the scores are scaled by `1/√d_k` to cancel out variance growth with dimensionality, softmax turns them into a probability distribution, and that distribution weights a sum over the values. The naive implementation costs O(n²) in both compute and memory because it materializes the full n×n score matrix — that quadratic memory is the actual bottleneck at long context, not the FLOPs. The KV-cache side of this is solved by cutting how many key/value heads you store — MHA gives every query head its own KV head, MQA collapses all of them to one, GQA groups them, and MLA compresses K and V into a shared low-rank latent, in that order of increasingly aggressive but increasingly clever compression. The compute side is solved by FlashAttention, which never materializes the n×n matrix at all — it tiles the computation and keeps a running (online) softmax so the *exact* same output comes out, just without ever writing O(n²) elements to HBM.

## Why this gets asked

Because nearly everyone can say "queries, keys, values" and nobody can derive why the scale factor is `√d_k` specifically, or explain that FlashAttention is an exact algorithm, not an approximation — a genuinely common misconception. The interviewer has hit the KV cache wall in production: a model that fit fine at 2k context OOMs at 32k, and they want to know whether you understand that the fix is architectural (GQA/MLA, chosen at pretraining time) versus operational (paging the cache, done at serving time). Staff-level follow-ups probe whether you can do the actual memory arithmetic for a real model, not just name the pattern.

## Lineage: past → present → future

**What came before.** Pre-2014 sequence models (RNN/LSTM encoder-decoder for translation) compressed an entire input sequence into one fixed-size hidden vector, and everything downstream had to be reconstructed from that bottleneck — Bahdanau et al. (2014) introduced additive attention specifically to let the decoder look back at all encoder states instead of trusting one vector, fixing the "long sentences degrade" failure that plagued Seq2Seq. Vaswani et al.'s "Attention Is All You Need" (2017) then deleted the recurrence entirely: scaled dot-product self-attention plus positional encodings matched and then exceeded RNN-based translation quality while being fully parallelizable across the sequence dimension at training time — the RNN's sequential dependency was the pain that killed it, since it made training unparallelizable across time steps.

**Where it stands now.** Scaled dot-product multi-head attention is the settled mechanism inside essentially every production LLM; the live argument has moved entirely to the KV-cache side. GQA (Ainslie et al., 2023) is the default in most open weights shipped 2023-2025 — Llama 2/3 70B ships 64 query heads over 8 KV heads. DeepSeek's Multi-head Latent Attention (DeepSeek-V2, 2024) pushed further by compressing K and V into a shared low-rank latent vector rather than merely sharing full-size heads across groups, and DeepSeek-V3 reports roughly 70 KB/token versus 192-328 KB/token for comparable GQA configurations — 2.7-4.7x lower than GQA on top of GQA's own reduction over MHA ([DeepSeek MLA KV cache analysis](https://medium.com/foundation-models-deep-dive/deepseeks-multi-head-latent-attention-mla-is-shrinking-the-kv-cache-27328f7dda27), accessed 2026-07-26). On the compute side, FlashAttention displaced the naive O(n²)-memory implementation everywhere it's available; FlashAttention-3 (2024), tuned for Hopper's async Tensor Cores and TMA, is the current production kernel on H100-class hardware. The live disagreement is whether further KV-cache compression (MLA-style, or the newer sparse/latent hybrids being published through 2026) is worth the added architectural complexity and retraining cost versus just doing more aggressive quantization or offloading of a GQA cache.

**Where it's heading.** Two things with reasonable confidence: latent/compressed KV representations (MLA and its 2025-2026 successors, e.g. compressed convolutional attention) are the direction serious labs are pretraining toward, because they buy quality *and* memory simultaneously rather than trading one for the other the way MQA did. Sub-quadratic attention replacements (linear attention, state-space models, sliding-window-plus-global hybrids) remain a live research direction but have not displaced quadratic attention in any frontier general-purpose model as of mid-2026 — treat "attention is going away" as speculative. More speculatively: hardware and kernels are co-evolving (FP8/FP4 attention, warp-specialized async kernels), so expect the *quality cost* of aggressive KV compression to keep shrinking as compression is co-designed with pretraining rather than retrofitted onto a frozen architecture.

---

## Mental model

Query = "what am I looking for." Keys = "what does each item advertise." Values = "what each item actually contains." Attention finds how well the query matches each key, turns that into weights, and returns a weighted blend of values — a fuzzy version of a hash-map lookup where instead of one exact match you get a similarity-weighted average of all entries.

```
Q (1×d_k)   K^T (d_k×n)                     scores (1×n)
  [q] ───────────────· ───────────────▶ [s1 s2 s3 ... sn]
                                              │  ÷ √d_k
                                              ▼
                                        [scaled scores]
                                              │  softmax
                                              ▼
                                        [w1 w2 w3 ... wn]   (sums to 1)
                                              │
                                              ▼  weighted sum over V rows
                              output = Σ wi · V[i]   (1×d_v)
```

For self-attention, Q, K, V are all linear projections of the same input sequence, so every position produces a query and every position also offers a key/value — every token looks at every other token, including itself, which is exactly what makes the score matrix n×n.

---

## How it actually works

### Scaled dot-product attention, derived

$$\text{Attention}(Q,K,V) = \text{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right)V$$

**Why √d_k, derived, not asserted.** Assume each component of `q` and `k` is drawn independently with mean 0 and variance 1 (true after LayerNorm/initialization keeps activations roughly standardized). The raw dot product is:

$$q \cdot k = \sum_{i=1}^{d_k} q_i k_i$$

Each term `q_i k_i` is a product of two independent, zero-mean, unit-variance random variables. For independent zero-mean X, Y: `Var(XY) = E[X²]E[Y²] − (E[X]E[Y])² = 1·1 − 0 = 1`. The sum of `d_k` such independent terms has variance that adds:

$$\text{Var}(q \cdot k) = \sum_{i=1}^{d_k} \text{Var}(q_i k_i) = d_k$$

So the standard deviation of the raw dot product grows as `√d_k`. As `d_k` grows (64, 128 in real models), the raw scores spread out further and further. Feed a wide-spread score vector into softmax and it saturates: one logit dominates, `softmax` output approaches a one-hot vector, and the *gradient* of softmax w.r.t. its inputs — `softmax_i(1-softmax_i)` — collapses toward zero everywhere except the winner. That is a vanishing-gradient trap at exactly the layer you need signal to flow through. Dividing every score by `√d_k` rescales the variance back down to 1 regardless of `d_k`, which is what actually licenses treating scores at `d_k=64` and `d_k=128` the same way. Note it must be `√d_k`, not `d_k`: dividing by `d_k` overcorrects, driving variance below 1, which pushes softmax toward a near-uniform distribution and destroys the model's ability to sharply prefer one key over another.

### Cost: O(n²) in time *and* memory

For sequence length `n` and head dimension `d_k`, `QK^T` is an `n × n` matrix — computing it is `O(n² d_k)` FLOPs, and naively *storing* it (to run softmax and then multiply by V) is `O(n²)` memory, per head, per layer. Concretely: at `n = 8192`, one `n×n` matrix in FP16 is `8192² × 2 bytes ≈ 128 MB` — for a single head, single layer. A 32-head, 32-layer model materializing this naively needs `128 MB × 32 × 32 ≈ 128 GB` just for attention-matrix scratch space at that one context length — this is the number that makes long-context naive attention physically impossible, and it is the reason FlashAttention exists (below).

### MHA → MQA → GQA → MLA: what's actually being cut

The number of query heads (`h`) is fixed by model quality requirements — it's how many independent "search patterns" the model runs in parallel. What varies across these four is **how many independent key/value heads back those query heads**, because the KV cache — not the weights — is what you re-read on every single decode step and what you must store per active sequence.

KV cache size per token: `2 × n_kv_heads × d_head × bytes_per_element` (the leading 2 is for storing both K and V). Multiply by `n_layers × seq_len × batch` for total cache size.

| Variant | KV heads | KV cache vs MHA | Quality cost |
|---|---|---|---|
| **MHA** (2017) | `h` (one per query head) | baseline | none — the reference point |
| **MQA** (Shazeer, 2019) | 1 (shared by all query heads) | ÷h | measurable — degrades summarization and long-context retrieval quality |
| **GQA** (Ainslie et al., 2023) | `g` groups, `g < h` | ÷(h/g) | small — 4-8 groups recovers most of MHA quality |
| **MLA** (DeepSeek-V2/V3, 2024) | compressed low-rank latent, not discrete heads | further 2.7-4.7x beyond GQA (DeepSeek-V3: ~70 KB/token vs 192-328 KB/token for comparable GQA models) | reported as quality-neutral to slightly positive vs GQA at equal parameter budget |

**Worked example — Llama-family 70B, 80 layers, `d_head = 128`, BF16 (2 bytes), no batching:**

- MHA hypothetical (64 KV heads): `2 × 80 × 64 × 128 × 2 = 2,621,440 bytes/token ≈ 2.5 MB/token` → at 4,096 tokens ≈ **10 GB** for one sequence.
- GQA, actual shipped config (8 KV heads, group size 8): `2 × 80 × 8 × 128 × 2 = 327,680 bytes/token ≈ 0.32 MB/token` → 4,096 tokens ≈ **1.3 GB**; at 128k context ≈ **42 GB** for a single sequence ([KV cache memory arithmetic](https://pub.towardsai.net/llama-2-70b-has-64-query-heads-and-8-kv-heads-here-is-the-memory-arithmetic-nobody-shows-you-eb154f2b65e9), accessed 2026-07-26).
- MQA hypothetical (1 KV head): `2 × 80 × 1 × 128 × 2 = 40,960 bytes/token ≈ 40 KB/token` — 8x smaller than this GQA config, 64x smaller than MHA.

This is why GQA with 8 heads was the practical default through 2023-2025: an 8x reduction from MHA recovers essentially all of the throughput benefit of MQA while keeping enough independent KV subspaces that long-context and summarization quality don't visibly regress.

**MLA mechanically.** Instead of storing full-size K and V per head, MLA projects the input down to a much smaller shared latent vector (rank far below `h × d_head`), caches *that*, and reconstructs per-head K/V from it via learned up-projection matrices at attention time. Because the down-projection and up-projection are both linear, the up-projection for K can be algebraically absorbed into the query projection (and correspondingly for V into the output projection), so decode-time compute doesn't pay for materializing full-size K/V — only the compressed latent is cached and read. This is a genuinely different compression axis than GQA: GQA reduces *how many* KV heads exist, MLA reduces *how large* the representation each cached vector needs to be.

### FlashAttention: same output, radically less memory traffic

**Why it's exact, not approximate.** FlashAttention (Dao et al., 2022) computes the mathematically identical `softmax(QK^T/√d_k)V` — it changes the *order of operations and memory access pattern*, not what is computed. It never writes the full `n×n` score matrix to HBM (GPU high-bandwidth memory, off-chip and comparatively slow). Instead it tiles Q, K, V into blocks that fit in on-chip SRAM, computes partial attention outputs block by block, and maintains a **running (online) softmax**: since softmax needs a normalization constant computed over the whole row, but you're only looking at one block at a time, you keep a running max and running sum and *rescale* previously-accumulated output whenever a new block reveals a larger max — algebraically exact, just computed incrementally. This is why it is IO-aware rather than approximate: the approximation-based alternatives (Linformer, Performer, sparse/local attention) change *what* gets computed (a different, cheaper function); FlashAttention computes the *same* function faster by minimizing reads/writes between HBM and SRAM, which is the actual bottleneck on modern GPUs where compute throughput has grown much faster than memory bandwidth.

**FlashAttention-2 (2023).** Improved parallelization across the sequence dimension and warps and cut non-matmul FLOPs, reaching roughly 2x the throughput of FlashAttention-1 and 50-73% of theoretical peak FLOPs on A100.

**FlashAttention-3 (2024), tuned for H100/Hopper.** Three techniques stack: (1) warp-specialization that overlaps Tensor Core matmuls with the asynchronous Tensor Memory Accelerator (TMA) data movement so compute and memory transfer happen concurrently instead of stalling each other; (2) interleaving block-wise matmul and softmax so the (non-matmul) softmax work hides behind matmul latency; (3) FP8 support with incoherent processing to keep low-precision error down. Reported numbers: **1.5-2.0x faster than FlashAttention-2 in FP16**, reaching up to **740 TFLOPs/s (~75% of H100's theoretical peak) in FP16**, **840 TFLOPs/s (~85%) in BF16**, and up to **~1.2-1.3 PFLOPs/s in FP8**, with FP8 error roughly 2.6x lower than a naive FP8 baseline ([FlashAttention-3, Together AI](https://www.together.ai/blog/flashattention-3), accessed 2026-07-26; [PyTorch blog](https://pytorch.org/blog/flashattention-3/), accessed 2026-07-26).

---

## Build it from scratch

Minimal scaled dot-product attention (naive, O(n²) memory — for understanding, not for long context):

```python
import numpy as np

def softmax(x, axis=-1):
    x = x - np.max(x, axis=axis, keepdims=True)   # numerical stability
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)

def attention(Q, K, V):
    """Q: (n, d_k), K: (n, d_k), V: (n, d_v) -> (n, d_v)"""
    d_k = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(d_k)      # (n, n) -- this is the O(n^2) matrix
    weights = softmax(scores, axis=-1)   # (n, n), each row sums to 1
    return weights @ V                    # (n, d_v)

def multi_head_attention(Q, K, V, n_heads):
    """Q,K,V: (n, d_model). Splits into heads, runs attention per head, concatenates."""
    n, d_model = Q.shape
    d_head = d_model // n_heads
    out = np.zeros_like(Q)
    for h in range(n_heads):
        sl = slice(h * d_head, (h + 1) * d_head)
        out[:, sl] = attention(Q[:, sl], K[:, sl], V[:, sl])
    return out
```

A minimal **online-softmax** sketch (the core FlashAttention trick, block size `B`, for one query block against all key/value blocks):

```python
# untested sketch -- illustrates the running-max/running-sum rescaling, not a real kernel
def online_softmax_attention(q_block, K, V, B):
    d_k = q_block.shape[-1]
    n = K.shape[0]
    m = np.full((q_block.shape[0], 1), -np.inf)   # running row max
    l = np.zeros((q_block.shape[0], 1))            # running row sum of exp
    acc = np.zeros((q_block.shape[0], V.shape[1])) # running weighted-V accumulator
    for start in range(0, n, B):
        k_blk, v_blk = K[start:start+B], V[start:start+B]
        s = q_block @ k_blk.T / np.sqrt(d_k)        # (qblock, B) -- small, stays in SRAM
        m_new = np.maximum(m, s.max(axis=-1, keepdims=True))
        p = np.exp(s - m_new)
        correction = np.exp(m - m_new)               # rescale old accumulator for new max
        l = l * correction + p.sum(axis=-1, keepdims=True)
        acc = acc * correction + p @ v_blk
        m = m_new
    return acc / l   # final normalization, done once at the end
```

Full derivation + a from-scratch GQA/MQA head-sharing implementation with KV-cache byte counting: **`labs/py/03-attention/`** (create if not present — not yet in this repo).

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Kernel | FlashAttention-2/3 (via PyTorch SDPA, `flash-attn` package, or FlashInfer) | Exact attention without materializing the n×n matrix; 2-4x speedup over naive |
| Architecture | GQA (most open weights) or MLA (DeepSeek family) | Determined at pretraining time — you cannot bolt GQA/MLA onto a pretrained MHA checkpoint without retraining or a head-merging conversion step |
| Serving | vLLM / SGLang / TensorRT-LLM manage the *cache*, not the attention math itself | PagedAttention block allocation, prefix caching, batching — covered in `T05-inference-serving` |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| OOM only at long context, fine at short context | KV cache growth is linear in seq_len but was sized for a short-context test | Compute KV cache bytes/token up front; budget against it, not against weights-only VRAM |
| Model quality regresses specifically on long documents after switching to MQA | 1 shared KV head loses positional/semantic diversity needed for long-context retrieval | Move to GQA with 4-8 groups; retraining/continued-pretraining required, not a free lunch |
| Training loss spikes or stalls in early layers of a from-scratch model | Missing or wrong attention scaling (using `d_k` instead of `√d_k`, or omitting it) | Scale by `1/√d_k` exactly; verify with a unit test on random Q/K at increasing `d_k` |
| Attention kernel silently falls back to a much slower path | Unsupported head_dim, dtype, or missing causal-mask fast path for the installed FlashAttention version | Pin FlashAttention version to what your head_dim/dtype/GPU combination actually supports; check kernel selection logs |

---

## Tradeoffs & when NOT to use it

- **MQA is rarely the right default today.** It buys the largest KV-cache win but the quality cost is the least favorable point on the curve; GQA with a small number of groups captures most of the memory win with much less quality risk, which is why almost nobody ships pure MQA anymore.
- **MLA is not a drop-in retrofit.** It requires the model be pretrained (or at least substantially continued-pretrained) with the compressed latent scheme; you cannot convert an existing GQA checkpoint into an MLA one by a config change.
- **FlashAttention needs the right kernel/hardware/dtype combination.** On unsupported head dimensions, unusual masking patterns, or older GPUs, you may silently get a slower fallback path — always verify which kernel actually ran, not just which one you requested.
- **For short sequences and small batches, the O(n²) cost is irrelevant.** At `n = 128`, worrying about attention memory is solving a problem you don't have; spend the engineering effort on serving-level batching instead.
- **Full attention is the wrong tool for genuinely unbounded-length streaming.** Sliding-window/local-attention hybrids or state-space models are more appropriate when you need bounded per-step memory regardless of how long the stream runs; that's a different mechanism than anything in this catalogue, and swapping to it is an architecture decision, not a serving-layer one.

---

## Interview questions

### Q1 — Walk me through the attention formula and explain every term.
**Testing:** baseline fluency.
**Answer:** `softmax(QK^T/√d_k)V`. `Q` and `K` are linear projections of the input into query/key space; `QK^T` scores how well each query matches each key; dividing by `√d_k` controls variance so softmax doesn't saturate; softmax turns each row of scores into a probability distribution over positions; multiplying by `V` produces a weighted average of the value vectors, weighted by that distribution.
**Follow-up trap:** *"Why is it a row-wise softmax and not a column-wise one?"* — each **query** (row) needs its own distribution over all keys (columns) that sums to 1; a column-wise softmax would instead normalize each key's influence across all queries, which answers a different (and not useful) question.

### Q2 — Derive why we scale by √d_k specifically, not d_k or nothing.
**Testing:** whether you can actually derive it, not recite "prevents saturation."
**Answer:** If Q, K components are i.i.d. mean-0, variance-1, the dot product `Σ q_i k_i` over `d_k` terms has variance `d_k` (sum of `d_k` independent unit-variance products), so its standard deviation grows as `√d_k`. Dividing by `√d_k` restores unit variance regardless of `d_k`. Dividing by `d_k` instead over-shrinks variance below 1, pushing softmax toward uniform and destroying its ability to sharply prefer a key.
**Follow-up trap:** *"What actually breaks if you skip scaling entirely at large d_k?"* — softmax saturates (near one-hot), and `softmax_i(1-softmax_i)` — its own gradient factor — collapses toward zero almost everywhere, stalling gradient flow through that layer specifically at large head dimensions, which is exactly when you'd otherwise want more capacity.

### Q3 — What's the time and memory cost of self-attention, and which one actually limits you in practice?
**Answer:** `O(n²d_k)` time, `O(n²)` memory per head for the naive implementation, since `QK^T` is `n×n`. Memory is the practical limiter: at `n=8192`, one FP16 `n×n` matrix is ~128 MB *per head, per layer* — a 32-layer, 32-head model naively needs on the order of 128 GB of scratch just for score matrices at that context length, which is why nobody runs the naive version past a few thousand tokens.
**Follow-up trap:** *"Does FlashAttention change the O(n²) time complexity?"* — no. It changes the *memory* profile from O(n²) to O(n) (never materializing the full matrix) and improves the *constant factor* on time via better hardware utilization; the asymptotic FLOP count for full attention is still quadratic. Only a different mechanism (sparse/linear attention) changes the asymptotic complexity.

### Q4 — Explain MHA, MQA, and GQA, and give the KV-cache reduction factor for each.
**Answer:** MHA: every query head has its own K/V head — baseline cache size. MQA: all query heads share one K/V head — cache divided by `h` (number of query heads). GQA: query heads are split into `g` groups, each group shares one K/V head — cache divided by `h/g`. Llama-family 70B ships 64 query heads over 8 KV heads: an 8x reduction versus a hypothetical full-MHA config.
**Follow-up trap:** *"Why not just always use MQA since it's the cheapest?"* — MQA measurably degrades quality on summarization and long-context retrieval because collapsing to one shared KV head removes representational diversity the model needs to distinguish different kinds of context; GQA with a small number of groups recovers nearly all of that quality at most of the memory saving.

### Q5 — Do the KV-cache arithmetic for a 70B model, 80 layers, GQA with 8 KV heads, head_dim 128, BF16, at 4096 tokens.
**Answer:** `2 × 80 layers × 8 KV heads × 128 head_dim × 2 bytes = 327,680 bytes/token ≈ 0.32 MB/token`. At 4,096 tokens: `0.32 MB × 4,096 ≈ 1.3 GB` for one sequence, before counting batch size.
**Follow-up trap:** *"Now do it at 128k context and tell me if that changes anything about serving."* — `0.32 MB × 128,000 ≈ 42 GB` for a *single* sequence — this alone can exceed a GPU's spare VRAM after model weights are loaded, which is why long-context serving is a batching/admission-control problem, not just a "buy a bigger GPU" problem.

### Q6 — What is MLA and how is it different from GQA mechanically?
**Answer:** MLA (DeepSeek-V2/V3) compresses K and V into a shared low-rank latent vector via a learned down-projection, caches only that compressed latent, and reconstructs per-head K/V via up-projection at attention time; because both projections are linear, the K up-projection can be absorbed into the query projection algebraically, so decode-time compute doesn't pay extra for it. GQA reduces the *count* of distinct KV heads; MLA reduces the *dimensionality* of what's stored per cached position. DeepSeek-V3 reports roughly 70 KB/token versus 192-328 KB/token for comparable GQA setups.
**Follow-up trap:** *"Can I add MLA to an existing GQA checkpoint as a serving-time optimization?"* — no. MLA's compression is learned during pretraining; it's an architecture choice baked into the weights, not something you retrofit at inference time the way you can add PagedAttention or quantization.

### Q7 — Why is FlashAttention described as "exact" — isn't tiling an approximation?
**Testing:** the most common misconception on this topic.
**Answer:** No — tiling changes memory access order, not the math. FlashAttention computes the identical `softmax(QK^T/√d_k)V` by processing Q/K/V in blocks that fit in SRAM and maintaining a running max and running sum to renormalize the softmax incrementally (online softmax) — algebraically equivalent to computing the full softmax at once. Approximate methods (Linformer's low-rank projection, sparse/local attention) change *what function* is computed; FlashAttention only changes *how* the same function is computed.
**Follow-up trap:** *"Then why is it faster if it's not approximating anything?"* — because the bottleneck was never FLOPs, it was HBM bandwidth: naive attention writes the full n×n matrix to slow off-chip memory and reads it back for softmax and the second matmul. FlashAttention keeps everything in on-chip SRAM per tile and only writes the final output, cutting memory traffic dramatically even though the FLOP count is essentially unchanged.

### Q8 — What's actually new in FlashAttention-3 versus 2, and why does it need Hopper specifically?
**Answer:** Warp-specialized producer/consumer pipelining that overlaps Tensor Core matmuls with the asynchronous TMA (Tensor Memory Accelerator) data movement, interleaved block-wise matmul/softmax scheduling to hide non-matmul latency, and FP8 support with incoherent processing to control quantization error. These specifically exploit Hopper (H100)-generation hardware features (async TMA, faster Tensor Cores) that didn't exist on Ampere (A100), which is why FA3's gains are H100-specific rather than a pure algorithm change portable to older GPUs. Reported: 1.5-2.0x over FA2 in FP16, up to ~740 TFLOPs/s FP16 (~75% of peak), ~840 TFLOPs/s BF16, ~1.2-1.3 PFLOPs/s FP8.
**Follow-up trap:** *"So does FA3 help at all on an A100?"* — the async-TMA and warp-specialization gains don't apply; you'd run FA2 (or FA3's non-Hopper-specific code path if the library provides a fallback), and the speedup versus naive attention comes mostly from the tiling/IO-awareness that both versions share, not the Hopper-specific tricks.

### Q9 — A colleague says "we should just use sparse attention everywhere, it's strictly better than FlashAttention." Do you agree?
**Answer:** No — different axis entirely. FlashAttention is exact and changes only the memory-access pattern; sparse attention changes the computed function, restricting which position pairs attend to each other, which is a real approximation with a real quality cost (it needs empirical validation per task, not just a benchmark FLOP count). They aren't mutually exclusive either — you can run a sparse attention pattern with a FlashAttention-style IO-aware kernel underneath it.
**Follow-up trap:** *"When would sparse attention actually be the right call?"* — genuinely long, mostly-local-dependency sequences (e.g. very long documents where most relevant context is nearby, plus a few global tokens) where the quality cost of ignoring distant, unneeded pairs is smaller than the compute you save — and only after measuring that cost on your actual task, not assuming it from a paper on a different domain.

### Q10 — Design the attention configuration for a new 30B model you're pretraining, targeting 128k context on a fixed GPU memory budget.
**Testing:** synthesis under a real constraint.
**Answer:** Start from the KV-cache budget backward: decide max concurrent sequences at 128k context, compute bytes/token needed to fit that in the memory left after weights + activations, then pick `n_kv_heads` (via GQA group count, or MLA's latent rank) to hit that number — e.g. if MHA would need 42 GB/sequence at 128k (per the worked Q5 example scaled up), and you need to serve 4 concurrent long-context sequences, you need roughly a 4x-or-more reduction from that baseline just from the head/latent design, before any serving-side paging or quantization. Pair with FlashAttention-3 (or whatever the current SOTA IO-aware kernel is at training time) for the compute side, since that's a training-time cost too, not just inference.
**Follow-up trap:** *"What's the risk of being too aggressive on the KV-cache side at pretraining time?"* — you can't get quality back cheaply afterward; if 128k-context retrieval quality regresses because you over-compressed (too few KV heads or too-low MLA rank), the fix is another pretraining/continued-pretraining run, not a config change — which is why this decision should be validated on long-context evals *during* architecture search, not discovered after the model ships.

### Q11 — A user reports the model "forgets" information from early in a very long conversation. Is that an attention problem?
**Answer:** Not directly an attention *mechanism* problem — full attention still computes exact scores over the whole context. It's more likely (a) the conversation exceeded the context window and got truncated, (b) positional encoding degrades at lengths beyond what was seen in training (a RoPE/ALiBi extrapolation issue, not attention itself), or (c) KV-cache eviction/compression (aggressive quantization, sliding-window truncation at the serving layer) dropped those tokens' cached state. Diagnose by checking whether the tokens are still inside the window and whether the serving stack is doing any cache eviction.
**Follow-up trap:** *"What would make you suspect the positional encoding rather than attention itself?"* — if the same tokens, closer to the start of a *shorter* prompt, are recalled correctly but fail only once total length passes some threshold — that's a length-extrapolation signature, which points at positional encoding, covered in `T05-positional`, not the attention formula.

### Q12 — Rank MHA, MQA, GQA, MLA by "how much production pain each one's absence causes," and justify it.
**Answer:** 1) **No KV-head reduction at all (pure MHA at scale)** — the most common root cause of "fits fine in dev, OOMs in prod at real context lengths," because nobody budgets 2.5 MB/token against thousands of concurrent long-context sequences. 2) **MQA where quality actually mattered** — the cheapest cache but the failure shows up subtly, as silently worse long-document quality that's easy to miss in short-context evals. 3) **GQA misconfigured (too few groups for the workload)** — a smaller version of the same quality risk. 4) **Missing MLA specifically** — real, but it's an efficiency ceiling, not a correctness or OOM risk the way the first two are; you're leaving throughput on the table, not breaking.
**Follow-up trap:** *"Isn't this ranking backwards from how much each is discussed?"* — yes, deliberately: MLA gets disproportionate attention in 2024-2026 discourse because it's novel, but plain "we didn't do the KV-cache arithmetic before shipping long context" is still the most common real incident.

---

## Red flags that fail you

- Saying attention scaling is "just to keep numbers small" without the variance derivation.
- Calling FlashAttention an approximation.
- Not knowing FlashAttention keeps time complexity O(n²) and only fixes memory.
- Describing MQA as strictly better than GQA because it's cheaper, with no quality caveat.
- Confusing MLA with GQA ("MLA is just GQA with more groups").
- Being unable to produce the KV-cache bytes/token formula on request.
- Claiming a serving-layer trick (paging, quantization) can substitute for an architectural KV-head decision made at pretraining time.

---

## Cheat card

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

## Sources

- [DeepSeek's Multi-Head Latent Attention (MLA) is Shrinking the KV Cache](https://medium.com/foundation-models-deep-dive/deepseeks-multi-head-latent-attention-mla-is-shrinking-the-kv-cache-27328f7dda27) — accessed 2026-07-26
- [Multi-Head Latent Attention (MLA) — Sebastian Raschka](https://sebastianraschka.com/llm-architecture-gallery/mla/) — accessed 2026-07-26
- [LLaMA-2 70B KV cache memory arithmetic](https://pub.towardsai.net/llama-2-70b-has-64-query-heads-and-8-kv-heads-here-is-the-memory-arithmetic-nobody-shows-you-eb154f2b65e9) — accessed 2026-07-26
- [FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision — PyTorch blog](https://pytorch.org/blog/flashattention-3/) — accessed 2026-07-26
- [FlashAttention-3 — Together AI](https://www.together.ai/blog/flashattention-3) — accessed 2026-07-26
- [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness (arXiv:2205.14135)](https://arxiv.org/pdf/2205.14135) — accessed 2026-07-26
- [KV Cache Optimization for LLMs 2026: Engineering Guide](https://www.digitalapplied.com/blog/kv-cache-optimization-techniques-2026-engineering-guide) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
