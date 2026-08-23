# Weekend 5 — Distributed Systems Fundamentals and LLM Internals

This weekend decides interviews because CAP/PACELC and the attention/KV-cache math are the two topics interviewers use to test whether you actually understand the systems underneath your applications, versus having memorised the vocabulary — and both are scored on whether your numbers are exact, not approximate.

## CAP/PACELC, Consistency Models, Replication, Partitioning

**30-sec:** CAP is precise but narrow: when an actual partition occurs, choose consistency or availability — it says nothing about the 99.99% of the time there is no partition. PACELC is the useful framing: **if Partitioned, choose Availability or Consistency; Else, choose Latency or Consistency.** Underneath is a spectrum — linearizable, sequential, causal, eventual — each permitting more staleness for lower latency. Replication (single-leader, multi-leader, leaderless quorum) and partitioning (range vs hash) are the concrete levers. Real systems sit at deliberately different, nameable points.

**CAP precisely:** C = linearizability (not ACID's C). A = every non-failing node responds (not an SLA%). P = survives arbitrary partition — only forces the C-vs-A choice *during* a partition. "Pick 2 of 3" is a common misconception; P isn't optional.

**PACELC mapping:** Spanner = PC/EC. Dynamo/Cassandra = PA/EL (tunable). Postgres leader ≈ PC/EC path; replica reads ≈ EL.

**Consistency spectrum (strong→weak):** linearizable > sequential > causal > eventual.

**Leaderless quorum:** R+W>N guarantees read/write quorum overlap (not real-time recency). Cassandra QUORUM/QUORUM at N=3: R=2,W=2 (4>3). Dynamo's sloppy quorum + hinted handoff relaxes R+W>N during a partition — an explicit AP tradeoff.

**Partitioning failure modes:** range → hot partition on monotonic keys (timestamp/auto-increment concentrates on the tail). Hash → even load but kills range scans, and does not fix a single hot/celebrity key.

**Real systems:** Spanner — TrueTime bounded clock uncertainty, commit-wait ~5–8ms single-region. DynamoDB — leaderless lineage, defaults to eventual reads (R=1). Cassandra — per-query consistency level, hinted handoff + read repair. Postgres — `synchronous_commit` level *is* the L-vs-C PACELC knob, literally.

## Attention: QKV, √dk, MHA→MQA→GQA→MLA, FlashAttention

**30-sec:** Attention is a soft, differentiable dictionary lookup: query dotted against every key, scaled by 1/√dk to cancel variance growth, softmax to a distribution, weighted sum over values. Naive cost is O(n²) in both compute and memory — memory is the real bottleneck at long context, not FLOPs. The KV-cache side is solved by cutting stored KV heads: MHA gives every query head its own KV head, MQA collapses to one, GQA groups them, MLA compresses K/V into a shared low-rank latent — increasingly aggressive, increasingly clever. FlashAttention solves the compute side without approximation: tiles the computation with a running softmax, never materialising the n×n matrix in HBM.

**Scale proof:** Var(q·k) = dk (sum of dk iid unit-variance products) → std = √dk; dividing by √dk restores unit variance. Dividing by dk instead over-shrinks toward a near-uniform softmax.

**KV cache per token:** `2 × n_kv_heads × d_head × bytes_per_elem`. Worked example: 70B, 80 layers, GQA-8, d_head=128, bf16 → 0.32 MB/token; 4k context = 1.3GB; 128k context = 42GB/sequence.

**MHA→MQA→GQA:** MQA divides cache by h (query heads); GQA divides by h/g. Llama 70B: h=64, g=8 → 8× cache reduction.

**MLA:** low-rank latent, not discrete heads. DeepSeek-V3 ≈70KB/token vs 192–328KB/token for GQA. K up-projection is foldable into the Q projection — no extra decode compute.

**FlashAttention is exact, never approximate.** FA2 ≈2× over FA1, 50–73% peak FLOPs on A100. FA3 (H100): 1.5–2.0× over FA2 fp16, ~740 TFLOPs/s fp16 (75%), ~1.2–1.3 PFLOPs/s fp8.

**Never retrofit:** GQA/MLA are pretraining-time architecture decisions, not inference-time config flags.

## KV Cache Math, PagedAttention, Continuous Batching, vLLM/SGLang

**30-sec:** Serving has two phases with opposite bottlenecks — prefill is compute-bound (whole prompt, parallel), decode is memory-bandwidth-bound (one token at a time, re-reads the full KV cache). The KV cache usually runs out before compute does, so serving engines exist to manage that memory: PagedAttention allocates fixed-size blocks like OS virtual memory to kill fragmentation, continuous batching keeps the GPU fed by admitting new requests the instant a slot frees, chunked prefill breaks long prompts so they don't block others' decode, and prefix caching reuses KV cache across shared prefixes — SGLang's RadixAttention makes that automatic and global via a radix tree.

**Bottlenecks:** prefill compute-bound, decode memory-bandwidth-bound; arithmetic intensity drops ~5× prefill→decode.

**PagedAttention:** naive contiguous allocation wastes 60–80% of memory; paged wastes <4% → 2–4× throughput.

**Batching:** static waits for the slowest member and idles finished slots; continuous/in-flight batching evicts/admits every decode step → near-100% utilization.

**Prefix caching:** vLLM uses block-content hash matching; SGLang RadixAttention uses a whole-pool radix tree with automatic cross-request reuse. On an 8B ShareGPT benchmark, SGLang ~16.2k tok/s vs vLLM ~12.5k (~29% faster), narrowing to 3–5% at 70B.

**Three numbers that trade against each other:** TTFT (queueing + prefill), TPOT/ITL (memory-bandwidth-bound decode step), throughput (aggregate tok/s). Batch size up → throughput up, TPOT up, possible TTFT up for new arrivals — no free lunch.

## If you remember nothing else

1. PACELC, not CAP, is the useful framing: normal operation (99.99% of the time) is a latency-vs-consistency choice, not a partition-forced one.
2. R+W>N guarantees quorum overlap, not real-time recency of concurrent writes — don't conflate the two.
3. Hash partitioning fixes uneven load but never fixes a single hot/celebrity key.
4. KV cache per token = `2 × n_kv_heads × d_head × bytes` — GQA/MLA reduce this at pretraining time, never at inference time.
5. Attention's real bottleneck at long context is O(n²) memory, not FLOPs; FlashAttention removes it by never materialising the score matrix, and is exact.
6. Prefill is compute-bound, decode is memory-bandwidth-bound — different bottlenecks need different fixes.
7. PagedAttention cuts KV cache waste from 60–80% to <4%, giving 2–4× throughput — this is why vLLM exists.
8. Postgres `synchronous_commit` is a literal, nameable instance of the PACELC latency-vs-consistency knob.

## Numbers table

| Fact | Value |
|---|---|
| Spanner commit-wait | ~5–8ms single-region, 20ms+ multi-region |
| Cassandra QUORUM at N=3 | R=2, W=2 (4>3) |
| KV cache/token formula | 2 × n_kv_heads × d_head × bytes_per_elem |
| 70B GQA-8 bf16 KV cache | 0.32 MB/token; 1.3GB @ 4k ctx; 42GB @ 128k ctx |
| Llama-70B GQA cache reduction | 8× (h=64, g=8) |
| MLA vs GQA cache (DeepSeek-V3) | ~70KB/tok vs 192–328KB/tok |
| FlashAttention memory (naive, n=8192, fp16, 1 head) | ~128MB score matrix |
| FA3 on H100 (fp16 / fp8) | ~740 TFLOPs/s (75%) / ~1.2–1.3 PFLOPs/s |
| PagedAttention memory waste | naive 60–80% → paged <4% |
| PagedAttention throughput gain | 2–4× |
| SGLang vs vLLM throughput (8B) | ~16.2k vs ~12.5k tok/s (~29%), narrows to 3–5% at 70B |
| vLLM chunked prefill default | 2048 tokens |
