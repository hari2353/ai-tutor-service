# KV Cache Math, PagedAttention, Continuous Batching, vLLM/SGLang

> **Track:** T05 LLM Internals · **Time:** 3h · **Prereqs:** T05-attention, T05-sampling · **Updated:** 2026-07-26
> **Module id:** `T05-inference-serving` · **Tags:** sprint, inference, critical

## The 30-second version

Serving an LLM has two phases with opposite bottlenecks: prefill processes the whole prompt in one parallel pass and is compute-bound, decode generates one token at a time re-reading the entire KV cache and is memory-bandwidth-bound. The KV cache itself grows linearly with sequence length and batch size and is usually the thing that runs out before compute does, so serving engines exist mainly to manage that memory well: PagedAttention (vLLM) allocates it in fixed-size blocks like OS virtual memory to kill fragmentation, continuous batching keeps the GPU fed by inserting new requests the instant a slot frees up instead of waiting for a whole batch to finish, chunked prefill breaks up long prompts so they don't block other requests' decode steps, and prefix caching reuses KV cache across requests that share a prompt prefix — SGLang's RadixAttention makes that reuse automatic and global via a radix tree instead of an exact-match cache. Every one of these knobs trades against the same three numbers: time-to-first-token, time-per-output-token, and aggregate throughput, and batch size is the dial that moves all three at once.

## Why this gets asked

Because "add more GPUs" is not a serving strategy and every interviewer here has watched a naive deployment either OOM under real traffic or serve at 10% of achievable throughput because nobody understood that prefill and decode compete for the same GPU with opposite resource profiles. They want to see you reason about the KV cache as a first-class, budgeted resource — not an afterthought — and to know whether "vLLM" is a name you can use or a system you can actually explain the internals of.

## Lineage: past → present → future

**What came before.** Early transformer serving (2020-2022) recomputed the KV cache from scratch on every generated token or, at best, cached it per-request in one contiguous memory allocation sized to the maximum possible sequence length. That contiguous-allocation approach wasted 60-80% of allocated KV-cache memory to internal fragmentation (allocations sized for the worst case but rarely used fully) and external fragmentation (variable-length outputs leaving unusable gaps), and it also served requests in static, fixed-size batches — the whole batch waited for its slowest (longest) member before any slot could be reused, leaving the GPU idle once shorter sequences finished. Orca (OSDI 2022) introduced iteration-level scheduling — what's now called continuous or in-flight batching — showing you could swap requests in and out of a batch every decode step rather than every full generation. The Efficient Memory Management for Large Language Model Serving paper (arXiv:2309.06180, the vLLM/PagedAttention paper) then applied OS virtual-memory ideas directly: page the KV cache into fixed-size blocks addressable via a block table, exactly like paging physical memory behind a process's virtual address space.

**Where it stands now.** PagedAttention plus continuous batching is the accepted baseline — vLLM's own reporting puts fragmentation waste under 4% versus 60-80% for naive contiguous allocation, and the combination of continuous batching, paged KV cache, and chunked prefill is cited as delivering 3-5x more served traffic than a naive PyTorch generation loop on the same hardware. The live disagreement is at the next layer up: SGLang's RadixAttention structures the entire KV-cache pool as a shared radix tree so that *any* two requests with a common prefix — not just turns within one conversation — automatically share cache, which measurably wins on workloads with heavy prefix reuse (structured agent/RAG traffic, shared system prompts): one 8B-model ShareGPT benchmark shows SGLang at roughly 16,200 tok/s versus vLLM's 12,500 (about 29% higher), though that gap narrows to 3-5% at 70B scale where compute rather than cache-reuse dominates. vLLM has since added its own automatic prefix caching via block-hashing, so the two engines are converging on capability even as their internal data structures (block table vs. radix tree) remain different. As of mid-2026, vLLM has shipped past v0.23 with a rewritten "Model Runner V2" execution path and a multi-tier KV-cache offloading framework (adding an object-store tier beyond GPU/CPU), while SGLang has added support for newer model families and continues to lead on prefix-heavy, lower-parameter-count workloads.

**Where it's heading.** Disaggregated serving — running prefill and decode on physically separate hardware pools tuned to their opposite bottlenecks (compute-dense accelerators for prefill, memory-bandwidth-optimized hardware for decode) — is a real, shipping direction: NVIDIA and several inference-hardware vendors have announced disaggregated prefill/decode architectures through 2026. This is a reasonably confident direction because it follows directly from the compute-bound/memory-bound split described below. More speculatively: adaptive, workload-aware admission control and scheduling (deciding per-request whether to admit, queue, or reject based on live KV-cache pressure, not static batch limits) is an active research area without a single dominant, settled approach yet — treat any specific claimed number here as provisional.

---

## Mental model

```
                         ┌─────────────── ONE GPU ───────────────┐
 New request  ──────────▶│  PREFILL                              │
 (long prompt)           │  process all N prompt tokens at once  │
                         │  compute-bound: dense matmuls,        │
                         │  high arithmetic intensity            │
                         └───────────────┬────────────────────────┘
                                         │ writes KV cache for all N tokens
                                         ▼
                         ┌─────────────── DECODE ─────────────────┐
                         │  generate 1 token, read the FULL       │
                         │  existing KV cache to do it            │
                         │  memory-bandwidth-bound: tiny compute, │
                         │  huge data movement per step           │
                         └───────────────┬────────────────────────┘
                                         │ repeat until EOS/max_tokens
                                         ▼
                                     output tokens

  KV CACHE = paged into fixed-size blocks, addressed via a block table
  (vLLM: PagedAttention)         or a radix tree keyed by token sequence
  (SGLang: RadixAttention) so identical prefixes across DIFFERENT
  requests reuse the same physical blocks instead of recomputing.
```

**Why the opposite bottlenecks matter operationally.** Mixing a compute-bound prefill chunk into the same GPU pass as several memory-bound decode steps actually raises utilization, because the GPU's compute units and its memory bus are being stressed simultaneously instead of one sitting idle while the other works — this is precisely what chunked prefill exploits.

---

## How it actually works

### KV cache size, derived from first principles

Per token, per layer: store one key vector and one value vector, each of size `n_kv_heads × head_dim`, in whatever dtype you're using:

$$\text{bytes/token} = 2 \times n_{layers} \times n_{kv\_heads} \times d_{head} \times \text{bytes\_per\_element}$$

Multiply by `seq_len × batch_size` for the total cache footprint at any point in time.

**Worked example: Llama-family 70B, 80 layers, GQA with 8 KV heads, `d_head=128`, BF16 (2 bytes):**

$$2 \times 80 \times 8 \times 128 \times 2 = 327{,}680 \text{ bytes/token} \approx 0.32\text{ MB/token}$$

- 1 sequence, 4,096 tokens: `0.32 MB × 4{,}096 ≈ 1.3 GB`
- 1 sequence, 128,000 tokens: `0.32 MB × 128{,}000 ≈ 42 GB` — larger than many single GPUs' *entire* VRAM, for one sequence
- Batch of 32 sequences at 4,096 tokens average: `1.3 GB × 32 ≈ 42 GB` — comparable order of magnitude to the single long-context sequence above, which is the point: **cache size is a product of sequence length and batch size, and either one alone can exhaust memory.**

This is why serving engines treat the KV cache as a scheduled, budgeted resource rather than something that "just uses whatever's left after weights."

### Prefill vs. decode: why the bottlenecks are opposite

**Prefill** processes every prompt token in one forward pass — effectively a batch of `N` positions running through dense matmuls simultaneously. Arithmetic intensity (FLOPs performed per byte of data moved) is high: you load a weight matrix once and reuse it across all `N` positions in the same pass, so the GPU's compute units stay busy — this is **compute-bound**.

**Decode** processes exactly one new token per step per sequence. You still load the *same* weight matrices and the *entire* accumulated KV cache from HBM, but now you only do one position's worth of compute with that data. The ratio of compute to memory traffic — arithmetic intensity — falls by roughly 5x moving from prefill to decode on typical workloads, and once arithmetic intensity drops below the GPU's compute-to-bandwidth ratio (its "roofline" balance point), you're waiting on memory bandwidth, not compute. This is **memory-bandwidth-bound**, and it's the reason decode throughput barely improves from a faster-FLOPs GPU if memory bandwidth doesn't also improve, and the reason batching multiple sequences together in decode helps: the same weight read now gets amortized across every sequence in the batch instead of just one.

### PagedAttention: the fragmentation problem, solved

Before PagedAttention, each request's KV cache was one contiguous allocation sized for the maximum possible output length — most requests finish well short of that, wasting the unused tail (internal fragmentation), and variable output lengths across requests leave unusable gaps between allocations (external fragmentation). Reported waste: **60-80%** of allocated KV-cache memory under naive contiguous allocation.

PagedAttention borrows the OS virtual-memory idea directly: partition the KV cache into fixed-size blocks (holding, e.g., 16 tokens' worth of K/V each), maintain a **block table** per sequence mapping logical token positions to physical block locations, and allocate blocks on demand as a sequence grows rather than up front. Blocks free immediately when a request finishes and can be reused by the next one. Reported waste under this scheme: **under 4%**, which directly translates into being able to fit more concurrent sequences (bigger batches) in the same VRAM — the 2-4x throughput improvement commonly cited for vLLM comes largely from this alone.

### Continuous (in-flight) batching vs. static batching

**Static/request-level batching**: form a batch of N requests, run decode steps together until every one of them finishes, only then form the next batch. The GPU is only as efficient as the *longest* sequence in the batch — every shorter sequence's slot sits idle after it finishes, until the whole batch drains.

**Continuous batching** (Orca's iteration-level scheduling, adopted as the default scheduling model in vLLM, SGLang, TGI, TensorRT-LLM): at every decode step, check which sequences finished, evict them, and admit new queued requests into the now-free slots — the batch composition changes every iteration instead of every full generation. This keeps GPU utilization high regardless of the variance in individual sequences' output lengths.

### Chunked prefill

A single very long prompt's prefill (say 32k tokens) run as one uninterrupted step can block the decode steps of every other in-flight request for that entire duration — a head-of-line blocking problem that directly hurts other users' time-per-output-token even though their requests have nothing to do with the long prompt. Chunked prefill splits a long prefill into fixed-size chunks (vLLM's default is **2,048 tokens**) and interleaves those chunks with ongoing decode steps from other sequences in the same batched iteration, so no single request's prefill can starve everyone else's decode for more than one chunk's worth of time. It also improves GPU utilization directly, since mixing a compute-bound prefill chunk with several memory-bound decode steps in the same pass keeps both compute units and memory bus busy concurrently.

### Prefix caching

If two requests share an identical prefix — a common system prompt, a shared few-shot block, or successive turns in one conversation — there's no reason to recompute (or even re-store separately) the KV cache for that shared portion. vLLM's Automatic Prefix Caching hashes each fixed-size block's token content and reuses the cached block across requests whenever the hash matches an existing one, with reference counting so a shared block is only evicted once no active sequence needs it. SGLang's **RadixAttention** generalizes this: the entire KV-cache pool is organized as a radix tree indexed by token sequence, so any prefix shared by *any* requests in the pool — not just requests explicitly grouped together — is automatically discovered and reused, with cache eviction implemented as an LRU policy over tree leaves. This is why SGLang tends to win specifically on workloads with heavy, irregular prefix reuse (multi-turn agent traffic, RAG pipelines re-sending similar retrieved context, shared long system prompts).

### TTFT, TPOT, throughput — and how they trade off

- **TTFT (time to first token)**: wall-clock time from request arrival to the first generated token reaching the client — dominated by queueing time plus prefill compute time, so it scales with prompt length and current server load.
- **TPOT (time per output token, also called inter-token latency, ITL)**: average time to produce each subsequent token — bound by memory bandwidth (reading weights + the growing KV cache on every step) and degrades as concurrency rises, since more concurrent sequences means more total KV cache to read per decode step and more contention for the same memory bus.
- **Throughput**: aggregate tokens/sec served across all concurrent requests — the number that determines cost per token.

**The tradeoff, concretely:** increasing batch size raises throughput, because the fixed cost of reading model weights from HBM gets amortized across more sequences per decode step (better arithmetic intensity, closer to the compute roofline). But it also raises TPOT for everyone in the batch, since each decode step now reads more total KV cache and competes for the same memory bandwidth — and it can raise TTFT for new arrivals if chunked-prefill chunks have to interleave with a now-larger decode batch. There is no batch size that simultaneously minimizes TTFT, minimizes TPOT, *and* maximizes throughput — it's a genuine three-way Pareto surface, and the "right" batch size is whichever point on that surface matches your actual SLO (a chat product typically prioritizes TTFT/TPOT over raw throughput; a batch-offline job does the reverse).

---

## Build it from scratch

A minimal, single-process illustration of continuous batching with a paged (block-based) KV cache — enough to see the mechanics, not a production scheduler:

```python
# untested sketch -- illustrates scheduling logic, not a real CUDA-backed KV cache
from dataclasses import dataclass, field

BLOCK_SIZE = 16

@dataclass
class Sequence:
    id: int
    tokens: list          # prompt + generated so far
    max_tokens: int
    block_table: list = field(default_factory=list)   # logical block idx -> physical block idx
    done: bool = False

class BlockAllocator:
    def __init__(self, n_blocks: int):
        self.free = list(range(n_blocks))
    def allocate(self) -> int:
        if not self.free:
            raise MemoryError("KV cache pool exhausted -- evict, offload, or reject")
        return self.free.pop()
    def free_block(self, idx: int):
        self.free.append(idx)

class ContinuousBatchScheduler:
    def __init__(self, allocator: BlockAllocator, max_batch: int):
        self.allocator = allocator
        self.max_batch = max_batch
        self.waiting: list[Sequence] = []
        self.running: list[Sequence] = []

    def submit(self, seq: Sequence):
        self.waiting.append(seq)

    def step(self):
        # 1. evict finished sequences, freeing their blocks
        still_running = []
        for seq in self.running:
            if seq.done:
                for b in seq.block_table:
                    self.allocator.free_block(b)
            else:
                still_running.append(seq)
        self.running = still_running

        # 2. admit new requests into now-free slots (this is the "continuous" part --
        #    happens every step, not only when the whole batch drains)
        while self.waiting and len(self.running) < self.max_batch:
            seq = self.waiting.pop(0)
            n_blocks_needed = (len(seq.tokens) + BLOCK_SIZE - 1) // BLOCK_SIZE
            try:
                seq.block_table = [self.allocator.allocate() for _ in range(n_blocks_needed)]
            except MemoryError:
                self.waiting.insert(0, seq)   # put it back, try next step
                break
            self.running.append(seq)

        # 3. run one decode step for every running sequence (model forward pass elided)
        for seq in self.running:
            next_tok = "..."  # model.forward(seq) in reality
            seq.tokens.append(next_tok)
            if len(seq.tokens) >= seq.max_tokens:
                seq.done = True
        return self.running
```

The three things a real engine adds on top of this sketch: prefix-hash lookup before allocating new blocks (prefix caching), splitting a too-long prompt's prefill across multiple `step()` calls (chunked prefill), and a real CUDA kernel that reads the block table to gather scattered physical blocks for attention (PagedAttention itself). Reference implementation for a from-scratch paged KV cache with prefix hashing: **`(lab pending)`** (create if not present — not yet in this repo).

---

## How it's done in production

| Engine | Cache structure | Prefix reuse | Notable internals |
|---|---|---|---|
| **vLLM** | PagedAttention: fixed-size blocks + per-sequence block table | Automatic Prefix Caching via block-content hashing | Continuous batching, chunked prefill (default chunk 2,048 tokens), speculative decoding, multi-tier KV-cache offloading (GPU→CPU→object store as of v0.23+), broad model/hardware backend support |
| **SGLang** | RadixAttention: shared radix tree over the whole KV-cache pool | Automatic and global — any shared prefix across any requests | Structured-output-aware scheduling (constrained/JSON decoding via compressed FSM, jump-forward decoding to skip forced tokens), its own frontend DSL for programmatic generation |

Both support chunked prefill and continuous batching; the architectural difference that actually matters in benchmarks is the cache data structure and how aggressively it discovers prefix sharing. On an 8B model against ShareGPT-style traffic, SGLang's RadixAttention reported roughly 16,200 tok/s versus vLLM's 12,500 (~29% higher); at 70B scale the gap narrows to 3-5%, because compute (not cache reuse) increasingly dominates at larger model sizes.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| OOM under real traffic despite plenty of free VRAM in dev testing | KV cache sized only for weights + a short-context smoke test; batch × seq_len wasn't budgeted | Compute bytes/token from first principles, multiply by target batch × max seq_len, size the cache pool explicitly |
| Throughput plateaus far below theoretical peak even with more GPUs | Static batching — GPU idles waiting for the longest sequence in each batch | Switch to continuous/in-flight batching |
| One long request tanks everyone else's inter-token latency | No chunked prefill — a 32k-token prefill runs uninterrupted, blocking decode steps for the whole batch | Enable chunked prefill; tune chunk size against your TTFT/TPOT targets |
| Repeated system-prompt-heavy traffic (agents, RAG) gets no speedup from caching | Naive engine recomputes KV cache per request even when prefixes are identical | Enable prefix caching (vLLM APC) or move to a radix-tree-native engine (SGLang) for irregular, cross-request prefix reuse |
| p99 latency spikes under load even though average latency looks fine | Requests preempted (evicted mid-generation) when the KV cache pool fills, then re-queued and re-run from scratch | Admission control / backpressure before accepting a request that can't be served without preempting others; monitor queue depth, not just averages |
| Adding a bigger GPU doesn't meaningfully improve decode throughput | Decode is memory-bandwidth-bound; the bottleneck is HBM bandwidth, not compute FLOPs | Increase batch size to amortize bandwidth cost across more sequences, or move to a GPU with genuinely higher memory bandwidth, not just more FLOPs |

---

## Tradeoffs & when NOT to use it

- **Don't reach for the biggest possible batch size by default.** It maximizes throughput but degrades TPOT for every request in it — fine for an offline batch-scoring job, wrong for an interactive chat product with a tight latency SLO.
- **Prefix caching isn't free memory.** Cached blocks still occupy pool space until evicted; on workloads with almost no prefix reuse (unique prompts every time), the hashing/lookup overhead buys nothing and the extra bookkeeping is pure cost.
- **Chunked prefill trades TTFT for other requests' TPOT stability.** A very small chunk size protects decode latency well but can slightly increase the *prefilling* request's own TTFT, since its prompt now takes more scheduler iterations to fully ingest.
- **SGLang's aggressive automatic prefix sharing is a mismatch for workloads with almost no shared prefixes** (e.g. fully unique, unrelated single-shot prompts) — you pay radix-tree bookkeeping overhead without the reuse benefit that justifies it; vLLM's simpler block-hash approach may be lower-overhead there.
- **KV-cache offloading to CPU/object storage trades capacity for latency.** It lets you serve more concurrent long-context sequences than GPU VRAM alone allows, but fetching an offloaded block back is orders of magnitude slower than reading GPU HBM — fine for cold, rarely-reused context; wrong for anything on the hot decode path.
- **None of this substitutes for the architectural KV-cache decision (GQA/MLA, `T05-attention`).** Serving-layer tricks manage a cache of whatever size the architecture produces; they can't shrink the fundamental bytes/token number.

---

## Interview questions

### Q1 — Why are prefill and decode described as having opposite bottlenecks?
**Testing:** baseline understanding of the core mechanical fact this whole topic rests on.
**Answer:** Prefill processes all prompt tokens in one parallel pass, so a weight matrix load is reused across many positions in the same pass — high arithmetic intensity, compute-bound. Decode processes one token per step but still reads the same weight matrices and the whole accumulated KV cache from HBM for that single position — arithmetic intensity falls roughly 5x from prefill to decode, so the GPU sits waiting on memory bandwidth rather than being FLOP-limited.
**Follow-up trap:** *"So would a GPU with more FLOPs but the same memory bandwidth make decode faster?"* — no, decode throughput is bandwidth-limited; you need more memory bandwidth (or a way to amortize the same bandwidth cost across more sequences via batching) to move that number, not more compute.

### Q2 — Derive the KV cache size for a request and do the arithmetic for a 70B model at 4k and 128k context.
**Answer:** `bytes/token = 2 × n_layers × n_kv_heads × d_head × bytes_per_element`. For 80 layers, 8 KV heads (GQA), `d_head=128`, BF16: `2×80×8×128×2 = 327,680 bytes/token ≈ 0.32 MB/token`. At 4,096 tokens: ~1.3 GB per sequence. At 128,000 tokens: ~42 GB per sequence — larger than a single GPU's total VRAM in many configurations, for one sequence alone.
**Follow-up trap:** *"Now factor in batch size of 16 at 4k context — does that change your serving strategy?"* — `1.3 GB × 16 ≈ 21 GB` just for KV cache, on top of model weights (which for a 70B model in BF16 alone is ~140 GB, meaning this specific example would need to be tensor-parallel across multiple GPUs regardless) — the point being cache size scales with *both* seq_len and batch, and either dimension alone can dominate depending on the workload.

### Q3 — What problem does PagedAttention solve, and what's the actual mechanism?
**Answer:** Fragmentation — contiguous per-request KV-cache allocations sized for worst-case length waste 60-80% of allocated memory to unused tail space and unusable gaps between variable-length allocations. PagedAttention partitions the cache into fixed-size blocks (e.g. 16 tokens each) with a per-sequence block table mapping logical positions to physical blocks, allocated on demand and freed immediately on completion — reported waste drops to under 4%.
**Follow-up trap:** *"Is this literally OS virtual memory?"* — the analogy is deliberate and close (fixed-size pages, a table for logical→physical translation, on-demand allocation) but it's application-level, not OS-level — there's no page fault / hardware MMU involvement, it's the serving framework's own memory manager mimicking the same idea for KV-cache blocks specifically.

### Q4 — Explain continuous batching and why static batching underperforms.
**Answer:** Static batching runs a fixed group of requests together until the *whole* batch finishes — every sequence that completes early leaves its slot idle until the longest sequence in the batch also finishes, wasting GPU capacity proportional to the variance in output lengths. Continuous (in-flight) batching evicts finished sequences and admits newly queued ones at every decode iteration, so slot occupancy stays near 100% regardless of individual sequence length variance.
**Follow-up trap:** *"Doesn't admitting new requests mid-batch mess up the KV cache layout?"* — this is exactly why continuous batching depends on PagedAttention-style memory management: block-based allocation lets you add/remove a sequence's blocks independently of every other sequence's layout, which a naive contiguous-allocation scheme can't do without expensive memory shuffling.

### Q5 — What is chunked prefill and what specific problem does it fix?
**Answer:** Splitting a long prompt's prefill into fixed-size chunks (vLLM defaults to 2,048 tokens) and interleaving those chunks with other sequences' decode steps in the same scheduling iteration, instead of running the entire prefill as one uninterrupted step. It fixes head-of-line blocking: without it, a 32k-token prefill can stall every other in-flight request's decode for the whole duration of that prefill, spiking their inter-token latency even though their requests have nothing to do with the long prompt.
**Follow-up trap:** *"What's the cost of making the chunk size very small?"* — the long-prompt request itself takes more scheduling iterations to fully ingest, slightly raising its own TTFT, and there's per-chunk scheduling overhead; chunk size is itself a TTFT-for-the-long-request vs. TPOT-for-everyone-else tradeoff, not a free fix.

### Q6 — Explain prefix caching and how SGLang's RadixAttention differs from vLLM's approach.
**Answer:** Prefix caching reuses already-computed KV cache for tokens shared across requests instead of recomputing them — critical for shared system prompts, few-shot templates, and multi-turn conversations. vLLM hashes fixed-size blocks by content and reuses a matching block whenever the hash matches, with reference counting for shared blocks. SGLang's RadixAttention organizes the *entire pool* as a radix tree keyed by token sequence, so any prefix shared by any requests — not just ones an application explicitly groups — is automatically discovered and shared, with LRU eviction over tree leaves.
**Follow-up trap:** *"When would vLLM's simpler hash-based approach actually be preferable?"* — workloads with little cross-request prefix structure, where radix-tree bookkeeping overhead buys nothing; also simpler to reason about operationally when your traffic pattern doesn't need automatic cross-request discovery.

### Q7 — Define TTFT and TPOT precisely, and explain how increasing batch size affects each plus throughput.
**Answer:** TTFT is wall-clock time from request arrival to first token — dominated by queueing plus prefill compute, scales with prompt length and load. TPOT (inter-token latency) is average time per subsequent token — memory-bandwidth-bound, scales with total KV cache being read per step across the whole batch. Increasing batch size raises throughput (amortizes weight-load cost across more sequences, better arithmetic intensity) but raises TPOT (more total KV cache read per decode step, more memory-bus contention) and can raise TTFT for new arrivals competing with a larger active batch for scheduling slots.
**Follow-up trap:** *"Give me a batch size that simultaneously minimizes all three."* — there isn't one; it's a genuine three-way tradeoff surface, and the correct answer is "the point on that surface that matches the SLO," e.g. a chat product weights TTFT/TPOT heavily and accepts lower throughput, while an offline scoring job does the reverse.

### Q8 — Walk through what happens end-to-end for one chat request in a modern serving stack.
**Answer:** Request queues; scheduler decides admission based on available KV-cache blocks; prefill runs (chunked if the prompt is long, interleaved with other sequences' decode steps), writing KV cache blocks (checking prefix cache first for any block whose content hash — or radix-tree path — already exists); first token returns (TTFT measured here); decode proceeds one token at a time, each step reading the full accumulated KV cache for every sequence currently in the batch (memory-bandwidth-bound, TPOT measured per step); sequence finishes on EOS or max_tokens, its blocks free immediately for the next queued request (continuous batching).
**Follow-up trap:** *"Where exactly would you add observability to debug a latency complaint?"* — separately instrument queueing time, prefill time, and per-decode-step time; a single end-to-end latency number can't distinguish "stuck behind another long prefill" from "genuinely memory-bandwidth-saturated," which need completely different fixes.

### Q9 — Your KV cache pool fills up under load. What are your options, and what does each cost?
**Answer:** Reject/queue new requests (safest, costs added latency for the rejected/queued request), preempt a running low-priority sequence and re-run it later (costs wasted compute and a latency spike for the preempted request), offload cold KV-cache blocks to CPU or object storage (costs fetch latency if that context becomes hot again), or reduce max batch size / max context length admitted (costs throughput or capability). Production systems generally combine admission control with offloading rather than relying on any single one.
**Follow-up trap:** *"Why not just always evict the oldest sequence?"* — "oldest" isn't the right signal — you want to evict based on priority, remaining expected output length, or SLA tier, not recency; naive LRU-by-sequence eviction can starve a low-throughput but high-priority request behind a burst of low-priority ones.

### Q10 — Do the cost-model arithmetic: given throughput and GPU hourly cost, compute dollars per million tokens, and explain how batch size moves this number.
**Answer:** `$/M tokens = (GPU $/hr) / (tokens/sec × 3600 sec/hr) × 1,000,000`. Illustrative example only (not a vendor quote): at $2.50/hr and 5,000 tokens/sec aggregate throughput, `2.50 / (5,000 × 3,600) × 1,000,000 ≈ $0.14 per million tokens`. Increasing batch size raises tokens/sec (better weight-load amortization), which directly lowers this number — up to the point where KV-cache capacity or memory bandwidth saturates and adding more concurrent sequences stops helping (or starts hurting, via preemption).
**Follow-up trap:** *"Does a bigger batch always lower cost per token?"* — only up to the memory-bandwidth or KV-cache-capacity ceiling; past that point, additional concurrency causes preemption/queueing that can *raise* effective cost by wasting recomputation, and it always raises TPOT, so the cost-minimizing batch size and the latency-SLO-respecting batch size are frequently different numbers — you optimize for whichever constraint binds first.

### Q11 — Why does vLLM's own automatic prefix caching not fully close the gap with SGLang on prefix-heavy workloads?
**Testing:** whether you understand the structural, not just marketing, difference.
**Answer:** vLLM's caching is block-hash-based — it reuses a block when its content hash exactly matches an already-cached block, which works well for exact, aligned prefix matches (like an identical system prompt at a fixed position) but is less naturally suited to discovering partial or irregularly-positioned shared prefixes across many different request shapes. RadixAttention's tree structure is built specifically to represent shared-prefix relationships across arbitrary request patterns as a first-class data structure, which is why the reported advantage is largest on exactly that kind of workload (agents, RAG) and shrinks where cache reuse isn't the bottleneck (larger models, compute-bound regimes).
**Follow-up trap:** *"So should everyone just use SGLang?"* — no — the advantage is workload-dependent and narrows sharply at larger model sizes (3-5% at 70B in the cited benchmark vs. ~29% at 8B), and engine choice also depends on ecosystem maturity, hardware backend support, and operational familiarity, all of which matter as much as a throughput number from one benchmark.

### Q12 — Design the serving strategy for a RAG chat product: mostly short-to-medium prompts, heavily shared system prompt and retrieved-context boilerplate, tight latency SLO.
**Testing:** synthesis — can you combine every mechanism in this module into one coherent design.
**Answer:** Prioritize prefix caching (or a radix-tree-native engine) since the shared system prompt and templated retrieval wrapper are exactly the high-reuse pattern that buys the most from it. Use continuous batching with a moderate max batch size chosen from the TPOT SLO, not maximized for throughput, since this is a latency-sensitive product. Enable chunked prefill with a modest chunk size to protect TPOT for in-flight conversations when a new long-context request (a big retrieved document) arrives. Size the KV-cache pool from measured p99 concurrent-sequence count × typical context length, with admission control (reject/queue, don't silently preempt) once the pool is near capacity, and monitor TTFT, TPOT, and queue depth separately, not just end-to-end latency.
**Follow-up trap:** *"What changes if this becomes an offline batch-scoring job instead?"* — invert almost every choice: maximize batch size and throughput, deprioritize TTFT/TPOT entirely (nobody's waiting interactively), disable admission-control-driven rejection in favor of a work queue, and prefix caching matters only if the offline corpus itself has shared prefixes.

---

## Red flags that fail you

- Saying "prefill and decode are basically the same, just more or fewer tokens" without naming the compute-bound/memory-bound split.
- Not being able to write the KV-cache bytes/token formula from memory.
- Claiming PagedAttention or continuous batching changes model quality — they don't; they're pure serving-efficiency mechanisms.
- Describing static batching as acceptable for an interactive product "as long as the batch size is small."
- Treating "just add prefix caching" as a free win with no cost model for low-reuse workloads.
- Confusing throughput-maximizing batch size with latency-SLO-respecting batch size, or claiming one number optimizes both.
- Not knowing that SGLang's advantage over vLLM is workload- and scale-dependent, not universal.

---

## Cheat card

```
BOTTLENECKS     prefill = compute-bound (parallel over prompt, high arithmetic intensity)
                decode  = memory-bandwidth-bound (1 token/step, reads full KV cache + weights)
                arithmetic intensity drops ~5x prefill -> decode

KV CACHE/TOKEN  2 * n_layers * n_kv_heads * d_head * bytes_per_elem
WORKED EX       70B, 80L, GQA-8, d_head=128, bf16: 0.32MB/tok; 4k ctx=1.3GB/seq; 128k ctx=42GB/seq

PAGEDATTENTION  fixed-size KV blocks (e.g. 16 tok) + per-seq block table, OS-paging analogy
                naive contiguous alloc wastes 60-80%; paged waste <4% -> 2-4x throughput

BATCHING        static: batch waits for slowest member, idles finished slots
                continuous/in-flight: evict/admit every decode step -> near-100% utilization

CHUNKED PREFILL splits long prompt prefill into chunks (vLLM default 2048 tok)
                interleaves with others' decode -> fixes head-of-line blocking on TPOT

PREFIX CACHING  vLLM: block-content hash match, reference counted
                SGLang RadixAttention: whole-pool radix tree, automatic cross-request reuse, LRU leaves
                8B ShareGPT bench: SGLang ~16.2k tok/s vs vLLM ~12.5k (~29%); narrows to 3-5% at 70B

TTFT            queueing + prefill time -> scales with prompt length + load
TPOT (ITL)      memory-bandwidth-bound decode step time -> scales with total KV cache read/step
THROUGHPUT      aggregate tok/s across all concurrent requests
TRADEOFF        batch size UP -> throughput UP, TPOT UP, possible TTFT UP for new arrivals -- no free lunch

COST MODEL      $/M tokens = (GPU $/hr) / (tok/s * 3600) * 1e6
                batch size lowers $/M tok up to bandwidth/capacity ceiling, then preemption can raise it

NEVER FORGET    serving tricks manage whatever KV cache size the ARCHITECTURE produces (see T05-attention)
                they cannot shrink bytes/token themselves
```

## Sources

- [Efficient Memory Management for Large Language Model Serving with PagedAttention (arXiv:2309.06180)](https://arxiv.org/pdf/2309.06180) — accessed 2026-07-26
- [How PagedAttention resolves memory waste of LLM systems — Red Hat Developer](https://developers.redhat.com/articles/2025/07/24/how-pagedattention-resolves-memory-waste-llm-systems) — accessed 2026-07-26
- [Prefill Is Compute-Bound. Decode Is Memory-Bound. — Towards Data Science](https://towardsdatascience.com/prefill-is-compute-bound-decode-is-memory-bound-why-your-gpu-shouldnt-do-both/) — accessed 2026-07-26
- [Chunked Prefill: Why One Long Prompt Freezes Your LLM Server](https://dev.to/ji_ai/chunked-prefill-why-one-long-prompt-freezes-your-llm-server-30e0) — accessed 2026-07-26
- [Optimization and Tuning — vLLM Documentation](https://docs.vllm.ai/en/stable/configuration/optimization/) — accessed 2026-07-26
- [vLLM vs SGLang vs TGI: 2026 Inference Engine Benchmark](https://llm-academy.dev/inference/vllm-vs-sglang/) — accessed 2026-07-26
- [SGLang vs vLLM in 2026: Benchmarks, Architecture, and When to Use Each](https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison) — accessed 2026-07-26
- [vLLM release notes / v0.23.0 changelog summary](https://fazm.ai/t/vllm-release-april-2026-release-notes) — accessed 2026-07-26
- [LLM Inference SLO Engineering: TTFT, ITL, and P99 Latency Budgets — Spheron Blog](https://www.spheron.network/blog/llm-inference-slo-ttft-itl-latency-budget-guide-2026/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
