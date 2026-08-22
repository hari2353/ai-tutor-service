# GPU Architecture: SMs, Warps, Occupancy, and Why Batching Dominates LLM Inference Economics

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2h · **Prereqs:** T16-cpu-microarch, T16-memory-hierarchy · **Updated:** 2026-08-03
> **Module id:** `T16-gpu-arch` · **Tags:** hardware

## The 30-second version

A GPU is a throughput machine, not a latency machine: instead of a handful of powerful out-of-order cores each racing one instruction stream, an NVIDIA GPU packs over a hundred Streaming Multiprocessors (SMs) — 132 on an H100 SXM — each of which executes threads in fixed groups of 32 called a **warp**, where every thread in the warp runs the *same instruction* in lockstep (SIMT — single instruction, multiple thread), so divergent branches within a warp serialize both paths and burn cycles on the path each thread doesn't take. **Occupancy** — the ratio of warps actually resident on an SM to the maximum it can host (64 warps/SM on H100, i.e. 2048 threads) — is the primary lever for hiding memory latency: while one warp stalls waiting on a slow global-memory load, the SM's scheduler switches to another resident warp with zero-cost context switching (unlike a CPU, warp state lives permanently in the register file, no save/restore), so enough occupancy keeps the SM's execution units busy instead of idle. Launching a GPU kernel from the CPU costs real, fixed overhead — commonly cited around 3-10 microseconds per launch even for a null kernel — which is small in isolation but becomes the dominant cost when a workload issues many tiny kernels instead of a few large ones, exactly the failure mode that motivates kernel fusion. For LLM inference specifically, this economics compounds directly into batching: a single request's forward pass is memory-bandwidth-bound (loading billions of weight bytes to compute relatively few FLOPs per token), so GPU compute sits mostly idle serving one request at a time — batching multiple requests' token generation together amortizes that same weight-loading cost across many outputs, which is why continuous batching (dynamically swapping completed requests out and new ones in at the token-step level rather than batching statically) is reported to deliver up to roughly 23x throughput improvement over naive per-request serving, and is the single biggest lever in LLM serving cost per token.

## Why this gets asked

Because "why is my GPU utilization only 20%" and "why does batching matter so much for LLM serving cost" are two of the most common real production questions in any ML infrastructure role today, and both trace back to the same underlying mechanical fact: GPUs are throughput-optimized, latency-hiding machines, and getting good utilization requires enough independent work in flight to keep thousands of ALUs fed while memory latency is hidden behind warp-switching. The interviewer wants to know whether you understand *why* small batch sizes waste GPU compute (not just that they do), whether you can reason about a workload as compute-bound versus memory-bandwidth-bound (the single most useful mental model for any GPU performance question), and whether you've actually reasoned about the batching-vs-latency tradeoff that dominates LLM inference serving cost economics — not just used vLLM as a black box.

---

## Lineage: past → present → future

**What came before.** Early GPUs (1990s-early 2000s) were fixed-function graphics pipelines — dedicated hardware for vertex transformation, rasterization, and texturing, with no general programmability at all; you could not run arbitrary computation on them. The pain that changed this: researchers and engineers wanted the GPU's massive parallel arithmetic throughput for general computation (physics simulation, early machine learning), but the only way in was disguising your computation as a graphics operation (encoding data as textures, computation as shader programs) — a genuinely painful, indirect programming model. NVIDIA's CUDA (2007) was the direct response: a general-purpose programming model exposing the GPU's parallel execution units as directly programmable compute cores, which is the point general-purpose GPU computing (GPGPU) actually became practical rather than a research curiosity.

**Where it stands now.** The SIMT execution model (warps of 32 threads executing in lockstep, hundreds of SMs per chip, a deep memory hierarchy of registers/shared-memory/L2/HBM) has been stable in its fundamentals since CUDA's introduction, with each hardware generation (Kepler, Pascal, Volta, Ampere, Hopper, Blackwell) primarily adding more SMs, more memory bandwidth, and specialized hardware units — most consequentially, **Tensor Cores** (introduced Volta, 2017), dedicated matrix-multiply-accumulate hardware that made mixed-precision (fp16/bf16, now fp8) deep learning training and inference dramatically faster than using general-purpose ALUs for the same matrix math. The current live disagreement/consensus split is squarely in LLM serving: the field has converged hard on continuous/iteration-level batching (Orca, 2022; adopted and refined by vLLM and effectively every serving framework since) as *the* dominant lever for inference throughput, because LLM inference's memory-bandwidth-bound nature (loading model weights dwarfs the actual FLOPs per token at low batch sizes) makes single-request serving throw away the vast majority of available compute — this is now production consensus, not a live debate, evidenced by essentially every serving framework (vLLM, TensorRT-LLM, Hugging Face TGI) implementing some form of it. What remains genuinely contested is the batching-vs-latency tradeoff's right operating point for a given product's SLA, and how aggressively to push techniques like speculative decoding and chunked prefill that trade implementation complexity for further throughput gains.

**Where it's heading.** Disaggregated serving (separating the compute-bound "prefill" phase from the memory-bandwidth-bound "decode" phase onto different hardware pools, so each phase can be batched and scaled according to its own bottleneck) is an active, real direction in 2025-2026 serving system research and increasingly production deployment at the largest LLM providers, though it adds real operational complexity (routing, KV cache transfer between pools) that smaller deployments may not find worthwhile yet. Sub-8-bit quantization for inference (covered in the numerics module) continues pushing memory-bandwidth-bound serving further, since less data to move per token directly reduces the bottleneck this module identifies as dominant. What's genuinely speculative: how much further batching/quantization/hardware co-design can push inference cost-per-token down before hitting fundamentally different bottlenecks (network bandwidth between GPUs for the largest models, power/cooling limits at the datacenter level) — real engineering teams are actively working all of these fronts simultaneously rather than one clearly winning direction.

---

## Mental model

```
GPU (H100 SXM example)
├── 132 SMs (Streaming Multiprocessors), each independently scheduled
│     └── SM internals:
│           ├── up to 64 resident WARPS (2048 threads) at once
│           ├── warp = 32 threads, SIMT lockstep (same instruction, all threads)
│           ├── large register file (256KB/SM) -- warp state lives here PERMANENTLY,
│           │     switching warps costs ~0 cycles (no save/restore, unlike a CPU)
│           ├── shared memory (228KB/SM on H100) -- fast, programmer-managed cache
│           │     shared across all threads in one block
│           └── Tensor Cores -- dedicated matrix-multiply-accumulate hardware
│
├── L2 cache (shared across all SMs, tens of MB)
└── HBM (High Bandwidth Memory) -- ~3TB/s on H100, the actual bottleneck for
      most LLM inference (loading weights >> compute per token at low batch)

DIVERGENCE:  if (thread_id % 2 == 0) { A } else { B }
  -> warp executes BOTH branches serially, masking off the threads that
     don't apply to each -- costs roughly 2x for a 2-way branch, not free

OCCUPANCY = active_warps_on_SM / max_warps_on_SM (64 on H100)
  low occupancy -> not enough warps to hide memory latency -> SM sits idle
  waiting on HBM loads instead of computing -- THIS is why "GPU utilization
  20%" happens even though the SM is technically "busy" scheduling
```

The one-line mental model: **a GPU hides latency by having so much independent work available that some warp is always ready to run while others wait on memory — your job as a GPU programmer (or as someone choosing an LLM serving batch size) is making sure there's always enough independent work queued up to keep that promise true.**

---

## How it actually works

### SIMT execution and why divergence costs real cycles

A warp's 32 threads share one instruction fetch/decode unit and execute in lockstep — every thread in the warp is either executing the *same* instruction or masked off (idle) for that cycle. When threads in a warp take different branches of an `if`/`else` (data-dependent divergence), the hardware doesn't run them in parallel down different paths — it serializes: first all 32 lanes execute the `if` path with the `else`-taking threads masked off (doing no useful work but still occupying that cycle), then all 32 lanes execute the `else` path with the `if`-taking threads masked off. A 2-way divergence costs roughly double the cycles of no divergence at all for that code region — the practical consequence is that GPU kernels are written to avoid data-dependent branching within a warp wherever possible, restructuring conditional logic into branchless arithmetic (multiply-by-mask patterns) when the divergence would otherwise be frequent and costly.

### Occupancy: the mechanism that hides memory latency

A global memory load from HBM takes hundreds of cycles to complete — if an SM only had one warp resident and that warp issued a memory load, the SM would sit completely idle for those hundreds of cycles waiting for the data. With many warps resident (high occupancy), the SM's warp scheduler simply switches to a *different* ready warp the instant the current one stalls on a memory access, and switches back once the data arrives — this context switch costs essentially zero cycles because, unlike a CPU thread switch (registers must be saved/restored to memory, see os-internals), every resident warp's full register state lives permanently in the SM's register file simultaneously; there's nothing to save or restore, just a scheduling decision about which already-resident warp's registers to read from next. This is *the* mechanism that makes GPUs throughput machines: instead of avoiding latency (a CPU's approach — branch prediction, speculative execution, deep caches, covered in the cpu-microarch module), a GPU embraces latency and *hides* it behind an abundance of independent, switchable work. Low occupancy — not enough warps resident to always have a ready one available when the current one stalls — is the single most common reason a GPU kernel shows "busy" scheduling activity while its actual compute throughput is far below peak, and it's the mechanical reason kernels launched with too few threads/blocks per SM underperform regardless of how well-optimized their per-thread code is.

### Kernel launch overhead: why it matters for real workloads

Every GPU kernel launch from the host (CPU) side pays fixed overhead — driver-level work to set up the kernel's grid/block configuration, queue the launch, and synchronize as needed — commonly measured in the low single-digit microseconds for a minimal ("null") kernel, with some reported measurements up to roughly 10μs depending on launch configuration and synchronization requirements. This sounds negligible for a single launch, and it is — but a workload issuing thousands of small, sequentially-dependent kernel launches (common in naive implementations of multi-step algorithms, or un-fused sequences of elementwise operations in a naively-written model forward pass) pays this overhead thousands of times, and if each individual kernel's actual compute time is comparable to or smaller than the launch overhead itself, the overhead becomes the dominant cost rather than a rounding error. This is the direct mechanical motivation for **kernel fusion** — combining multiple small operations into one larger kernel (either by hand, or automatically via a compiler like `torch.compile`/XLA/TVM) — which both amortizes the fixed launch cost across more actual work and avoids redundant round trips of intermediate results through HBM between separate kernel launches (each separate kernel must write its output to HBM and the next kernel must read it back, real bandwidth cost a fused kernel avoids by keeping intermediate values in registers/shared memory).

### Compute-bound vs memory-bandwidth-bound: the mental model that explains LLM inference economics

**Arithmetic intensity** — the ratio of floating-point operations performed per byte of data moved from memory — determines whether a workload is compute-bound (the GPU's ALUs/Tensor Cores are the bottleneck, memory bandwidth is not saturated) or memory-bandwidth-bound (the GPU spends most of its time waiting on data to arrive from HBM, and its compute units sit idle regardless of how fast they theoretically are). **LLM inference at low batch size (e.g. batch=1, generating one token at a time for one request) is severely memory-bandwidth-bound**: generating a single next-token requires loading the *entire* model's weights (potentially hundreds of gigabytes for a large model) from HBM once, but performs relatively few actual floating-point operations per token relative to that data volume — the arithmetic intensity is low, so the GPU spends the overwhelming majority of its time transferring weight bytes, and its compute units (capable of far higher FLOP throughput than the memory bandwidth can feed them) sit substantially idle. **Batching directly fixes this**: if instead of generating one token for one request, you generate one token *each* for 32 or 64 simultaneous requests in the same kernel launch, the model weights are loaded from HBM *once* and reused across all 32-64 requests' worth of computation — the same fixed memory-bandwidth cost now produces many times more useful output, pushing the workload's arithmetic intensity up and utilizing the GPU's compute capacity far better. This is not a minor optimization; it's the central economic lever of LLM serving, because GPU-hours are the dominant cost of serving at scale and batching is the most direct way to extract more useful tokens per GPU-hour without any change to model quality.

### Continuous batching: why static batching leaves throughput on the table

Naive ("static") batching groups a fixed set of requests together and processes them as a batch until *every* request in the batch finishes generating — but LLM outputs have wildly variable lengths, so a batch containing one long-generating request and several short ones wastes GPU cycles: once the short requests finish, their batch slots sit idle (or worse, are padded and processed as wasted work) while the GPU waits for the longest request in the batch to complete before the next batch can start. **Continuous batching** (also called iteration-level or in-flight batching; introduced by the Orca paper, 2022, and implemented in vLLM and effectively every modern serving framework) instead operates at the level of individual decode *steps*: after each single token-generation step, any request that has finished is immediately removed from the batch and a new waiting request is immediately added in its place, keeping the batch continuously full of active work rather than gated by the slowest member of a fixed cohort. Reported results: the Orca paper demonstrated up to roughly 36.9x throughput improvement over naive request-level batching in its benchmarks, and vLLM (which pairs continuous batching with PagedAttention — a memory-management technique for the KV cache that reduces fragmentation and enables more requests to fit in GPU memory simultaneously) is reported to deliver up to roughly 23x higher throughput with reduced p50 latency compared to naive serving baselines. Both numbers are workload- and configuration-dependent, but the direction and rough magnitude — an order of magnitude or more — is consistent and well-documented across the serving-systems literature, which is why virtually no serious LLM serving deployment uses naive static batching today.

---

## Build it from scratch

A from-scratch GPU kernel is out of scope for a conceptual module, but the mental model — memory-bandwidth-bound vs compute-bound reasoning, and the batching effect — is directly demonstrable with a minimal, runnable PyTorch example showing the actual throughput difference batch size makes:

```python
# untested sketch — demonstrates memory-bandwidth-bound behavior and batching's effect
import torch, time

device = "cuda"
# a stand-in for "loading model weights": a large matrix multiply-heavy layer
weight = torch.randn(4096, 4096, device=device, dtype=torch.float16)

def benchmark(batch_size, n_iters=50):
    x = torch.randn(batch_size, 4096, device=device, dtype=torch.float16)
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(n_iters):
        y = x @ weight                     # the same weight loaded from HBM each call
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    tokens_per_sec = (batch_size * n_iters) / elapsed
    return tokens_per_sec

for bs in [1, 8, 32, 128]:
    tput = benchmark(bs)
    print(f"batch_size={bs:4d}  throughput={tput:,.0f} rows/sec")

# Expect throughput per-row to increase substantially from batch_size=1 to
# batch_size=32-128, then plateau once compute (not memory bandwidth) becomes
# the bottleneck -- the exact point where this plateaus is a direct, measurable
# demonstration of crossing from memory-bandwidth-bound to compute-bound.
```

Running this and plotting throughput-per-row against batch size directly reproduces, at small scale, exactly the effect that makes continuous batching the dominant lever in production LLM serving: the marginal cost of serving one more request in the same batch is far smaller than the fixed cost of loading the weights at all. A fuller lab comparing static vs. simulated continuous batching against variable-length synthetic generation workloads belongs in `labs/python/13-gpu-arch/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| `nvidia-smi` shows GPU "utilization" near 100% but actual throughput/tokens-per-second is far below the hardware's theoretical peak | Misleading metric: `nvidia-smi` utilization reports whether *any* kernel is running, not how efficiently it's using compute — a memory-bandwidth-bound kernel can show 100% "utilization" while compute units are substantially idle waiting on HBM | Profile with `nsight-compute`/`nsys` to check actual achieved occupancy and memory-bandwidth utilization, not just the coarse utilization percentage |
| Single-request (batch=1) LLM inference latency is fine, but GPU cost-per-token at scale is far higher than expected | Batch=1 serving is severely memory-bandwidth-bound — model weights are reloaded from HBM per request with almost no compute-work amortization | Deploy continuous batching (vLLM, TGI, TensorRT-LLM) to amortize weight-loading cost across many concurrent requests' token generation |
| A batch of variable-length generation requests shows GPU utilization dropping over the batch's lifetime | Static/request-level batching: short requests finish early and their slots sit idle/padded while the batch waits for the longest request | Switch to continuous/iteration-level batching, which replaces finished requests with new ones at every decode step rather than waiting for the whole batch to finish |
| A custom CUDA kernel's profile shows large amounts of time in launch/synchronization overhead relative to actual compute time | Many small, sequentially-dependent kernel launches, each paying fixed launch overhead (~3-10μs) that dominates when per-kernel compute time is comparably small | Fuse operations into fewer, larger kernels (`torch.compile`, hand-written fusion, or a kernel-fusion compiler like XLA/TVM) to amortize launch overhead and avoid redundant HBM round trips between kernels |
| A kernel with seemingly reasonable thread/block configuration still underperforms relative to theoretical peak | Low occupancy — not enough warps resident per SM to hide memory latency, often due to excessive per-thread register or shared-memory usage limiting how many warps/blocks can be resident simultaneously | Check achieved occupancy via profiler; reduce per-thread register/shared-memory pressure, or restructure the kernel's thread/block configuration to increase resident warp count |
| A kernel processing data-dependent conditional logic per-element shows lower-than-expected throughput despite low arithmetic complexity | Warp divergence — threads within a warp taking different branches serialize both paths | Restructure branching into branchless arithmetic (mask-and-multiply patterns) where the divergence is frequent/costly, or reorganize data so threads within a warp tend to take the same branch together |

---

## Tradeoffs & when NOT to use it

- **Don't assume larger batch sizes are free throughput with no downside.** Batching directly trades latency for throughput — a request added to a larger batch waits longer for its response even if the batch as a whole produces more total tokens/sec, so latency-SLA-sensitive applications (interactive chat with strict response-time requirements) need to pick a batch size/serving configuration that respects the SLA, not just maximize raw throughput.
- **Don't over-fuse kernels reflexively without profiling first.** Kernel fusion helps when launch overhead or intermediate HBM round-trips genuinely dominate; for already-large, already-compute-bound kernels, aggressive fusion can add compiler/scheduling complexity without meaningful benefit — profile to confirm the bottleneck before optimizing for it.
- **Don't chase 100% occupancy as an end in itself.** Maximum theoretical occupancy is not always the throughput-maximizing configuration — sometimes fewer, "fatter" resident warps with more registers/shared-memory per thread (lower occupancy but less register spilling, better per-thread performance) outperforms a configuration tuned purely to maximize warp count; measure actual achieved throughput, not occupancy as a proxy for it.
- **Don't deploy continuous batching complexity for workloads that don't need it.** For low-volume, latency-tolerant batch-processing use cases (offline scoring jobs with no interactive latency requirement), the operational complexity of a full continuous-batching serving stack may not be worth it versus simpler static batching at a comfortably large batch size chosen upfront.
- **Don't treat GPU utilization percentage as a proxy for efficiency.** As the production table above shows, a memory-bandwidth-bound kernel can report high utilization while wasting most of the hardware's compute capacity — always corroborate with an actual profiler (achieved occupancy, memory bandwidth utilization, roofline analysis) before concluding a workload is "well optimized."

---

## Interview questions

### Q1 — What is a warp, and why does divergent branching within one cost real cycles?
**Testing:** the foundational SIMT execution model.
**Answer:** A warp is a fixed group of 32 threads that execute the same instruction in lockstep on an SM, sharing one instruction fetch/decode unit. When threads in a warp take different branches of a conditional, the hardware serializes: it runs the `if` path with the `else`-taking threads masked off (idle for those cycles), then runs the `else` path with the `if`-taking threads masked off — a 2-way divergence costs roughly double the cycles of no divergence, because both paths execute sequentially rather than the threads genuinely running in parallel down different paths.
**Follow-up trap:** *"How would you avoid this cost in a kernel with frequent data-dependent branching?"* — restructure the logic into branchless arithmetic (e.g. multiply-by-boolean-mask patterns instead of an `if`/`else`), or reorganize the data/thread assignment so threads within the same warp tend to take the same branch together, reducing how often divergence actually occurs.

### Q2 — What is occupancy, and why does it matter more on a GPU than a similar-sounding metric would on a CPU?
**Testing:** the latency-hiding mechanism that's the core of the whole module.
**Answer:** Occupancy is the ratio of warps actually resident on an SM to the maximum it can host (64 warps/SM on H100). When a resident warp stalls on a slow memory load (hundreds of cycles from HBM), the SM's scheduler switches to a different ready, resident warp at essentially zero cost, because every resident warp's register state lives permanently and simultaneously in the SM's register file — there's nothing to save/restore, unlike a CPU thread switch. Low occupancy means there aren't enough warps resident to always have a ready one available when the current one stalls, so the SM sits idle waiting on memory instead of computing.
**Follow-up trap:** *"Is maximizing occupancy always the right goal?"* — no; sometimes a kernel configured for lower occupancy but more registers/shared-memory per thread (avoiding register spilling to slower memory) achieves higher actual throughput than a configuration tuned purely to maximize resident warp count — occupancy is a means to hiding latency, not the metric to directly maximize.

### Q3 — Why does `nvidia-smi` showing 100% GPU utilization not mean the GPU is being used efficiently?
**Testing:** a specific, commonly-misread production metric.
**Answer:** `nvidia-smi`'s utilization percentage reports whether *any* kernel is actively running on the GPU during the sampling window, not how efficiently that kernel is using the available compute throughput. A severely memory-bandwidth-bound kernel (e.g. batch=1 LLM inference) can show 100% utilization while its actual compute units sit substantially idle waiting on HBM data — the metric conflates "a kernel is running" with "the hardware's compute capacity is being used well."
**Follow-up trap:** *"What would you check instead to get the real picture?"* — a proper profiler (Nsight Compute/Nsight Systems) reporting achieved occupancy and memory-bandwidth utilization against the hardware's theoretical peaks, or a roofline analysis comparing the kernel's arithmetic intensity against the GPU's compute-vs-bandwidth balance point, to determine whether the workload is actually compute-bound or memory-bandwidth-bound.

### Q4 — Why is LLM inference at batch size 1 memory-bandwidth-bound rather than compute-bound?
**Testing:** the arithmetic-intensity mental model applied to the single most commercially relevant GPU workload today.
**Answer:** Generating one token requires loading the entire model's weights from HBM (potentially hundreds of GB for a large model) but performs relatively few floating-point operations per token relative to that data volume — low arithmetic intensity. The GPU's compute units are capable of far higher FLOP throughput than HBM bandwidth can feed them at this ratio, so the GPU spends the overwhelming majority of time transferring weight bytes rather than computing, leaving compute capacity substantially idle regardless of how fast the ALUs/Tensor Cores theoretically are.
**Follow-up trap:** *"How does batching change the arithmetic intensity?"* — batching multiple requests' token generation into one kernel launch loads the same model weights from HBM once but performs proportionally more compute across all requests sharing that load, directly raising arithmetic intensity and pushing the workload from memory-bandwidth-bound toward compute-bound as batch size increases, until it eventually plateaus once compute genuinely becomes the bottleneck.

### Q5 — Explain continuous batching and why it beats static/request-level batching.
**Testing:** the specific mechanism, not just "it's faster."
**Answer:** Static batching processes a fixed group of requests together until every request in the batch finishes — since LLM output lengths vary widely, short requests finish early and their batch slots sit idle/padded while the GPU waits for the longest request to complete before starting the next batch. Continuous (iteration-level) batching operates at the granularity of individual decode steps: after each token-generation step, any finished request is immediately removed and a new waiting request is immediately added, keeping the batch continuously full of active work rather than gated by its slowest member.
**Follow-up trap:** *"What's the actual reported throughput improvement, and does it come free?"* — vLLM reports up to roughly 23x throughput improvement with reduced p50 latency versus naive serving, and the Orca paper reported up to ~36.9x versus static batching in its benchmarks; it's not entirely free — it adds real scheduling/memory-management complexity (deciding which requests to admit/evict at each step, managing per-request KV cache) that a serving framework like vLLM handles, which is exactly why hand-rolling this yourself is rarely worth it versus using an established framework.

### Q6 — What does PagedAttention add on top of continuous batching, and what specific problem does it solve?
**Testing:** whether the candidate distinguishes the scheduling optimization (continuous batching) from the memory-management optimization (PagedAttention) that vLLM pairs together.
**Answer:** Continuous batching solves *scheduling* — keeping the GPU fed with active work across requests of varying length. PagedAttention solves a separate problem: the KV cache (the per-request memory storing attention keys/values for all previously generated tokens) was traditionally allocated as one large contiguous block sized for the maximum possible sequence length, wasting memory on unused capacity and fragmenting available GPU memory across requests. PagedAttention manages the KV cache in fixed-size, non-contiguous pages (analogous to OS virtual memory paging), reducing fragmentation and letting more requests' KV caches fit simultaneously in GPU memory, which directly enables larger effective batch sizes.
**Follow-up trap:** *"Would continuous batching work without PagedAttention?"* — yes, they're independently useful (continuous batching is a scheduling technique, PagedAttention is a memory-layout technique), but combining them is what lets vLLM sustain large effective batch sizes without running out of GPU memory to fragmentation, which is why the two are so often mentioned together despite solving different problems.

### Q7 — Why does kernel launch overhead matter for real workloads if it's only a few microseconds?
**Testing:** whether small, per-operation fixed costs are understood as compounding at scale, not dismissed as negligible.
**Answer:** A single kernel launch's fixed overhead (commonly cited around 3-10μs even for a minimal kernel) is negligible in isolation, but a workload issuing thousands of small, sequentially-dependent kernel launches — common in naive multi-step algorithms or un-fused elementwise operation sequences — pays this overhead thousands of times; if each individual kernel's actual compute time is comparable to or smaller than the launch overhead itself, the overhead becomes the dominant cost of the whole workload rather than a rounding error.
**Follow-up trap:** *"What's the fix, and does it have a cost of its own?"* — kernel fusion (combining multiple small operations into one larger kernel, by hand or via a compiler like `torch.compile`/XLA), which amortizes the fixed launch cost across more work and also avoids redundant intermediate-result round trips through HBM between separately-launched kernels; the cost is added compiler/implementation complexity, and over-fusing an already compute-bound kernel with genuinely large per-launch work provides diminishing returns.

### Q8 — What is arithmetic intensity, and how would you use it to decide whether a kernel needs more compute optimization or more memory-bandwidth optimization?
**Testing:** the roofline-model mental framework applied practically.
**Answer:** Arithmetic intensity is FLOPs performed per byte of data moved from memory. Comparing a kernel's arithmetic intensity against the GPU's own compute-to-bandwidth ratio (its "ridge point" on a roofline chart) tells you which resource is the actual bottleneck: below the ridge point, the kernel is memory-bandwidth-bound and optimizing compute (e.g. using Tensor Cores more aggressively) won't help until memory traffic is reduced; above it, the kernel is compute-bound and reducing memory traffic further won't help, more efficient compute utilization is the lever.
**Follow-up trap:** *"Where does typical LLM inference sit on this curve, and does it change with batch size?"* — at low batch size, well below the ridge point (severely memory-bandwidth-bound, per Q4); as batch size increases, arithmetic intensity rises (same weight load amortized across more compute) and the workload moves toward and potentially past the ridge point into compute-bound territory, which is exactly why there's a batch size beyond which further batching yields diminishing throughput returns — you've crossed from memory-bound to compute-bound and now compute is the real limit.

### Q9 — Tensor Cores: what do they actually add over general-purpose CUDA cores, and why does that matter for mixed-precision training/inference?
**Testing:** a specific hardware feature tied directly to the numerics module's bf16/fp16/fp8 discussion.
**Answer:** Tensor Cores (introduced Volta, 2017) are dedicated matrix-multiply-accumulate hardware units performing an entire small matrix multiply-and-accumulate operation per instruction, far more efficient per cycle for the matrix-multiplication-heavy workload of deep learning than composing the same operation from general-purpose scalar ALU instructions. They're specifically optimized for reduced-precision formats (fp16, bf16, and now fp8) — using them at these lower precisions is what actually delivers the throughput gains reduced-precision training/inference promise; running the same reduced-precision data through general CUDA cores instead would leave much of that potential speedup unrealized.
**Follow-up trap:** *"Does using Tensor Cores automatically happen when you use fp16/bf16 tensors in PyTorch?"* — not automatically in all cases; it typically requires the operation shapes and code path to actually route through a Tensor-Core-eligible kernel (e.g. via `torch.autocast`/AMP, or explicit use of libraries/kernels that target them), and profiling (checking Tensor Core utilization specifically, not just overall GPU utilization) is the way to confirm they're actually being exercised rather than assumed.

### Q10 — Design question: you're serving an LLM with a strict p99 latency SLA (say, 200ms per token) alongside a desire to minimize GPU cost per token. How do you reason about the batch size decision?
**Testing:** staff-level judgment on the batching-vs-latency tradeoff, applied to a concrete constraint.
**Answer:** Larger batches amortize the memory-bandwidth cost of loading weights across more requests, directly reducing cost-per-token — but every request in a batch waits for that batch's full decode step to complete, so larger batches add per-step latency. The right approach is to measure the actual per-step latency at increasing batch sizes on the real hardware/model (not assume linearly), find the largest batch size where per-step latency still comfortably clears the 200ms p99 budget with margin for real-world request-arrival variance, and use continuous batching (not static) so the system can dynamically adjust the actual concurrent batch size within that ceiling based on real-time request load rather than committing to one fixed batch size upfront.
**Follow-up trap:** *"What would you do if even a batch size of 1 already threatens the p99 SLA?"* — that points to a different bottleneck than batching can fix — likely the model itself is too large/slow for the latency budget on the available hardware, and the actual levers become model-level (quantization to reduce weight-loading time, a smaller/distilled model, speculative decoding to generate more tokens per forward pass) rather than a serving-batching decision; naming that distinction — "this isn't a batching problem, it's a hardware/model-size problem" — is the senior-level signal here.

---

## Red flags that fail you

- Claiming a GPU is "just a CPU with more cores" with no mention of SIMT/warp-lockstep execution or the fundamentally different latency-hiding-via-occupancy model.
- Treating `nvidia-smi` utilization percentage as a reliable measure of compute efficiency.
- Not knowing why LLM inference at low batch size is memory-bandwidth-bound.
- Confusing continuous batching with simply "using a bigger batch size."
- Claiming batching is free throughput with no latency cost.
- Not knowing what warp divergence costs or why it happens.

---

## Cheat card

```
GPU = throughput machine (SIMT, latency-hidden via occupancy), not latency machine
H100 SXM: 132 SMs, 64 max resident warps/SM (2048 threads/SM), 256KB register
  file/SM, 228KB shared memory/SM, ~3TB/s HBM bandwidth

WARP = 32 threads, lockstep SIMT (same instruction or masked-off per cycle)
  DIVERGENCE: if/else within a warp -> serializes BOTH paths, ~2x cost/branch

OCCUPANCY = resident_warps / max_warps_per_SM
  hides memory latency: stalled warp -> scheduler switches to another resident
  warp at ~0 cost (full reg state lives permanently in reg file, no save/restore
  -- unlike a CPU context switch)
  low occupancy = SM idle waiting on HBM despite "busy" scheduler activity

KERNEL LAUNCH OVERHEAD: ~3-10us per launch (even null kernel) -- dominates
  when workload = many tiny sequential kernels -> FIX: kernel fusion
  (torch.compile/XLA/TVM), also avoids redundant intermediate HBM round-trips

ARITHMETIC INTENSITY = FLOPs / byte moved from memory -- determines compute-
  bound vs memory-bandwidth-bound (roofline model, "ridge point")
LLM inference @ batch=1: SEVERELY memory-bandwidth-bound (load full weights,
  few FLOPs/token) -> GPU compute mostly idle regardless of theoretical FLOPS
  BATCHING fixes this: same weight-load amortized across N requests ->
  arithmetic intensity rises -> better compute utilization -> lower $/token

STATIC BATCHING: waits for slowest request in fixed batch -> idle/padded slots
CONTINUOUS BATCHING (Orca 2022, vLLM+): swap requests in/out at EVERY decode
  step, not per-batch -- Orca: up to ~36.9x vs static; vLLM: up to ~23x
  throughput + lower p50 vs naive serving
PagedAttention (vLLM): pages the KV cache (like OS virtual memory) -> less
  fragmentation -> more requests' KV cache fit -> bigger effective batches
  (separate from continuous batching -- scheduling vs memory-layout fix)

TENSOR CORES (Volta 2017+): dedicated matmul-accumulate HW, optimized for
  fp16/bf16/fp8 -- the actual mechanism that delivers reduced-precision speedup
  (not automatic -- needs autocast/AMP or targeted kernels to engage)

BATCHING TRADEOFF: throughput UP, per-request latency UP -- pick batch size
  against the real p99 SLA, not just max throughput
```

## Sources

- [NVIDIA Hopper Tuning Guide — NVIDIA Docs](https://docs.nvidia.com/cuda/hopper-tuning-guide/index.html) — accessed 2026-08-03
- [GPU architecture fundamentals — LLM Inference Handbook, BentoML](https://bentoml.com/llm/kernel-optimization/gpu-architecture-fundamentals) — accessed 2026-08-03
- [Achieve 23x LLM Inference Throughput & Reduce p50 Latency — Anyscale](https://www.anyscale.com/blog/continuous-batching-llm-inference) — accessed 2026-08-03
- [LLM Serving Optimization: Continuous Batching, PagedAttention, and Chunked Prefill on H100 — Spheron](https://www.spheron.network/blog/llm-serving-optimization-continuous-batching-paged-attention/) — accessed 2026-08-03
- [Comparative Analysis of Large Language Model Inference Serving Systems: vLLM and HuggingFace TGI — arXiv](https://arxiv.org/pdf/2511.17593) — accessed 2026-08-03
- Orca: A Distributed Serving System for Transformer-Based Generative Models (OSDI 2022)

## Changelog
- 2026-08-03 — created
