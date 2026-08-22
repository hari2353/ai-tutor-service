# Distributed Training: DDP, FSDP, DeepSpeed ZeRO Stages, Tensor/Pipeline Parallel, and Communication Cost Arithmetic

> **Track:** T04 Deep Learning · **Time:** 3h · **Prereqs:** T04-training-engineering · **Updated:** 2026-08-03
> **Module id:** `T04-distributed-training` · **Tags:** scaling, critical
> **Lab:** `labs/python/07-distributed-training/`

## The 30-second version

Every distributed training strategy is a different answer to one question — which of {parameters, gradients, optimizer state, activations} do you replicate in full on every GPU, and which do you shard — and the answer determines both memory footprint and communication pattern. DDP (DistributedDataParallel) replicates everything and shards only the *data*: each GPU computes a full forward/backward on its own data shard, then a ring all-reduce averages gradients across GPUs, whose communication cost is `2·(N-1)/N · Ψ·bytes_per_param` and, critically, becomes *independent of GPU count `N`* as `N` grows large (the ratio `(N-1)/N → 1`), which is why DDP scales remarkably well but still requires the *full model* to fit in each GPU's memory. ZeRO (Rajbhandari et al., 2020) instead shards optimizer state, gradients, and eventually parameters themselves across GPUs, trading some extra communication for dramatically less memory: for a `Ψ=7.5B`-parameter model on `Nd=64` GPUs in mixed precision (`16Ψ` bytes total: `2Ψ` fp16 params, `2Ψ` fp16 grads, `4Ψ` fp32 master params, `4Ψ` momentum, `4Ψ` variance), baseline per-GPU memory is `120GB`; ZeRO Stage 1 (shard optimizer state only) cuts this to `31.4GB`; Stage 2 (also shard gradients) to `16.6GB`; Stage 3 (also shard parameters, all-gathering each layer's shard just before it's needed and freeing it right after) to `1.9GB` — a 64x memory reduction at the cost of roughly 1.5x DDP's communication volume. FSDP is PyTorch's native, more deeply-integrated equivalent of ZeRO Stage 3, with FSDP2's per-parameter (rather than flattened) sharding composing more cleanly with `torch.compile` and mixed dtypes, and is reported to reach up to roughly 5x DeepSpeed ZeRO-3's per-iteration throughput in the regime where both fit memory — the default recommendation for new training code in 2026. Tensor parallelism (splitting individual weight matrices across GPUs, Megatron-style) and pipeline parallelism (splitting *layers* across GPUs, with micro-batches flowing through pipeline stages) attack a different problem entirely — when even one layer, or one full model replica, doesn't fit on a single GPU — at the cost of much more frequent (tensor-parallel, communicating every layer) or bubble-inducing (pipeline-parallel, with idle time fraction `≈(stages-1)/microbatches`, e.g. `37.5%` idle at 4 stages with only 8 micro-batches, dropping to `9.4%` idle at 32 micro-batches) communication patterns that real large-scale training combines (data + tensor + pipeline + ZeRO/FSDP sharding, all simultaneously) rather than choosing just one.

## Why this gets asked

Because every serious production model beyond a few hundred million parameters requires multiple GPUs to train, and the choice among DDP/FSDP/DeepSpeed/tensor-parallel/pipeline-parallel is a real, high-stakes engineering decision with actual dollar and wall-clock consequences, not a framework preference. Interviewers ask this because it's one of the clearest ways to distinguish someone who has run (or debugged) a real multi-GPU training job from someone who has only ever trained on a single GPU or used a managed platform that hides all of this — and because the communication-cost arithmetic (why does an all-reduce not get proportionally slower with more GPUs, why does pipeline parallelism leave GPUs idle, why does sharding parameters cost extra communication) is exactly the kind of quantitative reasoning that separates "I used DeepSpeed" from "I understand why DeepSpeed's config knobs trade off the way they do."

---

## Lineage: past → present → future

**What came before.** Before any of these techniques existed, "distributed training" typically meant either training on a single, increasingly large GPU (bounded hard by that GPU's memory and compute, a wall reached quickly once model sizes crossed a few hundred million to a few billion parameters) or naive data parallelism with no memory-sharing at all (every GPU holds a full replica of parameters, gradients, *and* optimizer state — the "baseline" `16Ψ` bytes/parameter figure above) — which works fine while the model fits comfortably in one GPU's memory, but hits a hard wall the moment it doesn't, regardless of how many additional GPUs you add, since replication doesn't reduce any single GPU's memory requirement. The specific pain that motivated ZeRO (2020): teams wanted to train models whose *parameters and optimizer state alone* exceeded single-GPU memory, and adding more GPUs under naive data parallelism didn't help at all, because every GPU still needed to hold the complete `16Ψ` bytes regardless of how many GPUs participated — real memory reduction required actually *sharding* state across GPUs, not just replicating compute.

**Where it stands now.** ZeRO's three stages and PyTorch's FSDP (a native reimplementation of the same core idea, with FSDP2 as the current, more deeply-integrated iteration) are both mainstream, production-proven techniques as of 2026 for scaling data-parallel training up to the point where even a single parameter shard's associated activations become the bottleneck. The live, genuinely-debated choice is DeepSpeed versus FSDP2 specifically: DeepSpeed's configuration-file-driven interface is easier to adopt without deep PyTorch-internals knowledge, while FSDP2's all-Python-API, per-parameter (not flattened) sharding composes more cleanly with `torch.compile`, mixed per-layer dtypes, and partial-parameter-freezing (e.g. for LoRA-style fine-tuning) — reported benchmarks (Hugging Face's own comparison) show FSDP2 reaching up to roughly 5x DeepSpeed ZeRO-3's per-iteration throughput in the regime where both fit in memory, driving a real, current recommendation that most new training code in 2026 should reach for FSDP2 first. Tensor and pipeline parallelism remain necessary, not optional, once a model exceeds what data-parallel-plus-sharding alone can handle (specifically: when even the *activations* for a single layer, or the parameters of a single layer, don't fit on one GPU) — Megatron-Core (NVIDIA's tensor/pipeline-parallel training framework) and its equivalents remain the standard tool for the very largest training runs, typically combined with data parallelism and ZeRO/FSDP-style sharding simultaneously (this combination is usually called "3D parallelism" or similar), not used as a standalone alternative.

**Where it's heading.** Communication cost, not raw compute, is an increasingly binding constraint as model and cluster sizes grow — active 2025-2026 work on reducing communication volume (better overlap of communication with compute, compression of gradients/activations communicated between stages, smarter sharding strategies that minimize cross-GPU traffic) is a genuine, ongoing engineering frontier rather than a solved problem, and multi-node network topology (which GPUs are connected via fast NVLink versus slower inter-node networking) increasingly dictates which parallelism strategy is even feasible at a given scale (tensor parallelism in particular is highly bandwidth-sensitive and is typically kept within a single high-bandwidth node, while pipeline and data parallelism tolerate slower inter-node links better). What's stable: the fundamental memory-versus-communication tradeoff this module derives — sharding more aggressively always reduces memory at the cost of more communication — will remain true regardless of which specific framework or technique wins in a given year, because it follows directly from the arithmetic of moving data between physically separate GPUs.

---

## Mental model

```
WHAT GETS REPLICATED vs SHARDED across N GPUs -- this single choice IS the strategy:

DDP:            params: REPLICATED | grads: REPLICATED | optim state: REPLICATED
  each GPU: full forward+backward on its OWN data shard -> gradients differ per GPU
  -> ALL-REDUCE (average) gradients across GPUs -> every GPU applies IDENTICAL update
  memory: full 16*Psi bytes/GPU regardless of N        <- the wall ZeRO exists to break

ZeRO STAGE 1 (Pos): optim state SHARDED, params+grads still replicated
ZeRO STAGE 2 (Pos+g): optim state + grads SHARDED, params still replicated
ZeRO STAGE 3 (Pos+g+p): EVERYTHING sharded -- all-gather each shard JUST BEFORE
  it's needed for compute, free it right after -- max memory savings, most comm

FSDP = PyTorch-native equivalent of ZeRO-3 (FSDP2: per-parameter, not flattened,
  sharding -- composes with torch.compile, mixed dtypes, partial freezing/LoRA)

TENSOR PARALLEL: split ONE WEIGHT MATRIX across GPUs (Megatron-style)
  every layer needs a communication op (all-reduce/all-gather) -- HIGH FREQUENCY,
  bandwidth-sensitive -> usually kept WITHIN one fast-interconnect node

PIPELINE PARALLEL: split LAYERS (stages) across GPUs, micro-batches flow through
  GPU0[layers 1-8] -> GPU1[layers 9-16] -> GPU2[layers 17-24] -> ...
  naive: GPUs downstream sit IDLE until upstream stage produces first output
  BUBBLE FRACTION ~= (num_stages - 1) / num_microbatches
    4 stages, 8 microbatches:  37.5% idle
    4 stages, 32 microbatches:  9.4% idle   <- more microbatches shrinks the bubble

REAL LARGE-SCALE TRAINING = ALL of these combined simultaneously (3D/4D parallelism):
  data-parallel groups (DDP/ZeRO/FSDP across replicas) x
  tensor-parallel groups (within a node) x
  pipeline-parallel stages (across the depth of the model)
```

The one-line mental model: **distributed training is a menu of which state to replicate versus shard, and every "advanced" technique in this module is what you reach for specifically when the previous, simpler choice's memory or per-GPU-model-size ceiling has been hit — not a universally-better default to reach for regardless of scale.**

---

## How it actually works

### DDP and the ring all-reduce: why communication cost doesn't grow with GPU count

DDP replicates the full model on every GPU; each GPU runs forward and backward on its own shard of the current batch, producing a locally-computed gradient that differs across GPUs (different data, same model). Before the optimizer step, every GPU's gradient must be averaged together so all replicas apply the *identical* update (otherwise the replicas would drift apart) — this is a **ring all-reduce**: `N` GPUs arranged in a logical ring, each passing a chunk of its gradient to its neighbor over `N-1` reduce-scatter steps (combining chunks as they pass) followed by `N-1` all-gather steps (distributing the fully-reduced chunks back to everyone). The total data moved *per GPU* across this whole process is `2·(N-1)/N · S` where `S` is the total message size (e.g., `4Ψ` bytes for `Ψ` fp32 parameters) — as `N` grows large, `(N-1)/N → 1`, so the *bandwidth* cost per GPU approaches a constant (`≈2S`) **independent of how many GPUs participate**, which is the specific, checkable reason DDP scales as well as it does: adding more GPUs doesn't proportionally increase each GPU's communication burden, only the (much smaller, per-step) latency cost grows with `N`. This overlap-friendly, near-N-independent communication cost is why DDP remains the simplest, most robust choice whenever the model actually fits in a single GPU's memory.

### ZeRO: the exact memory arithmetic, verified against the paper's own numbers

Mixed-precision training with Adam stores, per parameter (using the ZeRO paper's own accounting): fp16 parameters (`2Ψ` bytes), fp16 gradients (`2Ψ` bytes), and — for numerically stable optimizer updates — fp32 master parameters (`4Ψ`), fp32 first-moment (`4Ψ`), fp32 second-moment (`4Ψ`), totaling `16Ψ` bytes, of which the optimizer state alone (`12Ψ` of the `16Ψ`) is **75% of total memory**. For `Ψ=7.5` billion parameters on `Nd=64` GPUs (the paper's own worked example): baseline (full replication) is `16Ψ/1e9 = 120GB` per GPU. **ZeRO Stage 1 (`Pos`, shard optimizer state only)**: each GPU keeps its full `4Ψ` bytes of params+gradients, but only `1/Nd` of the `12Ψ` bytes of optimizer state: `4Ψ + 12Ψ/Nd = 30GB + 1.4GB = 31.4GB`. **Stage 2 (`Pos+g`, also shard gradients)**: `2Ψ + (2Ψ+12Ψ)/Nd = 15GB + 1.64GB = 16.6GB`. **Stage 3 (`Pos+g+p`, also shard parameters)**: `16Ψ/Nd = 1.875GB` — a **64x** memory reduction relative to the `120GB` baseline. Every one of these numbers matches the original ZeRO paper's reported figures exactly, and the pattern generalizes: each additional stage of sharding divides one more term by `Nd`, at the cost of needing to communicate (all-gather) that sharded state back into a full copy at the moment it's actually needed for compute, then discard it again afterward — Stage 3's extra communication (parameters must be all-gathered per-layer during *both* forward and backward, since they're never held in full) brings total communication volume to roughly 1.5x plain DDP's, the concrete price of the additional memory savings.

### FSDP: the same idea, PyTorch-native, and why FSDP2's sharding granularity matters

FSDP (Fully Sharded Data Parallel) implements the same core idea as ZeRO Stage 3 — shard parameters, gradients, and optimizer state across data-parallel workers, all-gathering each shard just-in-time for the layer that needs it and freeing it immediately after — as a PyTorch-native module rather than a separate library with its own configuration format. **FSDP2**, the current generation, shards at **per-parameter** granularity rather than FSDP1's flattened-and-concatenated sharding (which grouped many parameters into single large shards) — this composes more cleanly with mixing dtypes per layer (some layers in bf16, others left in fp32), freezing individual parameters without rewriting sharding logic (directly relevant to LoRA-style fine-tuning, where most parameters are frozen and only a small adapter is trained), and end-to-end `torch.compile` integration. Reported benchmarks show FSDP2 achieving up to roughly 5x DeepSpeed ZeRO-3's per-iteration throughput in the regime where both configurations fit in memory, largely attributed to fewer copy steps in the gradient all-reduce path and cleaner `torch.compile` composition — which is the concrete, current (2026) basis for recommending FSDP2 as the default starting point for new large-scale training code, with DeepSpeed remaining a reasonable choice specifically when its configuration-file-driven ergonomics or specific features not yet matched in FSDP2 are the deciding factor.

### Tensor parallelism: splitting a single weight matrix, and why it's communication-frequent

Tensor parallelism (Megatron-style) splits an individual weight matrix's computation across GPUs — for example, a feedforward layer's first matrix multiply can be split *column-wise* across GPUs (each GPU computes a slice of the output independently, no communication needed for that step), while the second matrix multiply is split *row-wise*, requiring an all-reduce to sum the partial results from every GPU before the layer's true output is complete. This means tensor parallelism requires a communication operation **at every tensor-parallel-split layer**, far more frequently than DDP's once-per-backward-pass all-reduce — the payoff is that it reduces *per-GPU* memory and compute for a single layer that might otherwise not fit at all, but the communication frequency makes it highly latency- and bandwidth-sensitive, which is exactly why tensor-parallel groups are conventionally kept within a single node connected by fast interconnect (NVLink), rather than spread across nodes connected by comparatively slower networking.

### Pipeline parallelism: splitting layers, and the bubble-fraction arithmetic

Pipeline parallelism splits a model's *layers* (not individual weight matrices) across GPUs into sequential stages — GPU 0 holds layers 1-8, GPU 1 holds layers 9-16, and so on — with each micro-batch flowing forward through the stages in sequence, then backward in reverse. Naively, this leaves later-stage GPUs idle while waiting for the first micro-batch to arrive from earlier stages, and earlier-stage GPUs idle after they've finished processing all micro-batches' forward passes while waiting for the corresponding backward passes to arrive back — this idle time is the **pipeline bubble**, and for the simplest (GPipe-style) schedule, the bubble fraction is `≈(P-1)/M`, where `P` is the number of pipeline stages and `M` is the number of micro-batches per batch. With `P=4` stages and only `M=8` micro-batches: `(4-1)/8 = 0.375` — **37.5% of total GPU-time is idle bubble**, a substantial efficiency loss. Increasing to `M=32` micro-batches with the same `P=4` stages: `(4-1)/32 ≈ 0.094` — **9.4%** idle, a dramatically better utilization simply from using more, smaller micro-batches per logical batch (spreading the fixed pipeline-fill/drain cost over more useful work). More sophisticated schedules (1F1B/PipeDream-style interleaving, where a stage alternates forward and backward work for different micro-batches rather than completing all forwards before any backwards) reduce the bubble further and reduce peak activation memory, at the cost of more complex scheduling logic — but the underlying `(P-1)/M` arithmetic is the concrete number to reach for when asked "why does pipeline parallelism need enough micro-batches to be efficient."

### Combining strategies: why real large-scale training uses all of them at once

None of DDP/ZeRO/FSDP/tensor-parallel/pipeline-parallel is mutually exclusive with the others — the largest real training runs combine data parallelism (replicated groups, each internally using ZeRO/FSDP-style sharding) with tensor parallelism (within each node, splitting individual layers' matrices) and pipeline parallelism (across nodes, splitting depth) simultaneously, because each technique solves a *different* specific bottleneck: data parallelism scales throughput across more GPUs processing more data in parallel; tensor parallelism lets a single layer that doesn't fit on one GPU's memory/compute be split; pipeline parallelism lets a model whose *total* depth doesn't fit be split across GPUs without needing every layer itself to be split. Choosing among them is not "pick the best one" but "identify which specific ceiling (single-GPU model memory, single-layer memory/compute, single-GPU communication bandwidth) you've actually hit, and apply the corresponding technique on top of what you already have," which is precisely why frameworks like Megatron-Core and DeepSpeed expose all of these as independently configurable, composable dimensions rather than one flag choosing between them.

---

## Build it from scratch

A from-scratch ring all-reduce simulation (in plain Python, simulating `N` "GPUs" as separate arrays and implementing the reduce-scatter-then-all-gather steps explicitly to reproduce the `2·(N-1)/N·S` communication-volume arithmetic) and a from-scratch pipeline-parallel bubble-fraction simulator (schedule `M` micro-batches through `P` sequential "stages," each with a fixed processing time, and measure actual idle GPU-time as a fraction of total wall-clock time to confirm it matches `(P-1)/M`) are the lab exercises in `labs/python/07-distributed-training/`; the ZeRO memory-arithmetic table above is directly reproducible by writing a small calculator function taking `Ψ` and `Nd` as inputs and returning all four memory figures, then confirming it against the paper's own reported `120/31.4/16.6/1.9 GB` figures at `Ψ=7.5e9, Nd=64`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Multi-GPU DDP training OOMs on a model that fit (barely) on a single GPU in earlier, smaller-scale experiments | Every GPU under DDP still holds the *full* model, gradients, and optimizer state — DDP shards data, not model state, so adding GPUs doesn't reduce any single GPU's memory footprint | Switch to ZeRO Stage 2/3 or FSDP2 to actually shard optimizer state/gradients/parameters across GPUs, rather than adding more DDP replicas expecting memory relief |
| Training throughput scales poorly (far below linear) when adding more GPUs to a tensor-parallel configuration | Tensor-parallel communication happens at every split layer and is bandwidth/latency-sensitive; spreading a tensor-parallel group across multiple nodes (slower inter-node network) rather than keeping it within one fast-interconnect node | Keep tensor-parallel groups within a single node (NVLink-connected GPUs); use pipeline or data parallelism, not tensor parallelism, to scale across nodes |
| Pipeline-parallel training shows large amounts of idle GPU time in profiling despite a seemingly reasonable number of pipeline stages | Too few micro-batches relative to the number of pipeline stages, producing a large bubble fraction (`(P-1)/M`) | Increase the number of micro-batches per logical batch (reduce micro-batch size if needed to fit more of them), or switch to an interleaved (1F1B-style) pipeline schedule that reduces the bubble further |
| FSDP2 training is noticeably slower than expected, or memory savings are smaller than ZeRO Stage 3's equivalent configuration would suggest | Sharding granularity or wrapping policy misconfigured — e.g. wrapping too coarsely (large modules sharded as one unit, reducing all-gather/free granularity benefits) or not marking frozen parameters appropriately for a fine-tuning workload | Review the FSDP wrapping policy to shard at a granularity matching actual memory/compute bottlenecks, and confirm frozen parameters (e.g. in LoRA-style fine-tuning) are configured to avoid unnecessary gradient/optimizer-state allocation |
| A large model can't be trained even with the maximum affordable GPU count using data-parallel sharding (ZeRO-3/FSDP2) alone | A single layer's parameters/activations, not just the whole model's total size, exceed what one GPU can hold — a ceiling data-parallel sharding alone can't address, since it still requires materializing full layers during compute | Add tensor parallelism (splitting individual large layers across GPUs) and/or pipeline parallelism (splitting depth across GPUs) on top of the existing data-parallel/ZeRO setup |

---

## Tradeoffs & when NOT to use it

- **Don't reach for ZeRO Stage 3/FSDP2 by default if the model comfortably fits under plain DDP.** The additional communication (all-gathering sharded state just-in-time) is a real cost with no benefit if memory was never the binding constraint — use the simplest strategy (plain DDP) that fits, and only add sharding stages as memory pressure actually requires it.
- **Don't use tensor parallelism across multiple nodes without a very good reason.** Its high communication frequency makes it acutely sensitive to inter-node bandwidth/latency, which is typically far worse than intra-node NVLink — spreading it across nodes anyway tends to produce poor scaling that looks like "tensor parallelism doesn't work well" when the actual issue is topology mismatch.
- **Don't set pipeline-parallel micro-batch count too low.** As the bubble-fraction arithmetic shows, too few micro-batches relative to pipeline-stage count wastes a large fraction of total GPU-time on idle bubble — but don't over-correct by making micro-batches so small that per-micro-batch overhead (kernel launch, communication latency) starts to dominate instead; there's a real sweet spot to tune empirically.
- **Don't assume combining every parallelism strategy simultaneously is always better.** Each additional dimension of parallelism (tensor, pipeline, ZeRO/FSDP sharding) adds real configuration and debugging complexity, and combining strategies you don't actually need for your model's scale adds overhead and failure surface for no benefit — apply each dimension specifically to address a concrete, identified ceiling (a specific memory or compute wall you've actually hit), not preemptively.

---

## Interview questions

### Q1 — Why does DDP's ring all-reduce communication cost not grow proportionally with the number of GPUs?
**Testing:** the actual `2(N-1)/N` arithmetic, not "GPUs communicate somehow."
**Answer:** A ring all-reduce moves total data per GPU of `2·(N-1)/N · S` (`S` = message size) across `N-1` reduce-scatter steps and `N-1` all-gather steps. As `N` grows large, `(N-1)/N → 1`, so the bandwidth cost per GPU approaches a constant `≈2S`, essentially independent of how many GPUs participate — only the (much smaller, fixed-per-step) latency cost scales with `N`.
**Follow-up trap:** *"Does this mean DDP scales to arbitrarily many GPUs with no downside?"* — no; the *bandwidth* term is near-constant, but the model still must fit in full on every single GPU (DDP replicates, doesn't shard, model state) — the actual ceiling DDP hits isn't communication cost growing with `N`, it's per-GPU memory capacity, which is exactly the problem ZeRO/FSDP exist to solve.

### Q2 — Walk through the exact memory arithmetic for ZeRO Stage 1 vs Stage 3, using the paper's own `Ψ=7.5B, Nd=64` example.
**Testing:** the specific, verifiable numbers, not a vague "ZeRO saves memory."
**Answer:** Mixed-precision Adam training needs `16Ψ` bytes total (`2Ψ` fp16 params, `2Ψ` fp16 grads, `4Ψ` fp32 master params, `4Ψ` momentum, `4Ψ` variance) — baseline `120GB` at `Ψ=7.5e9`. Stage 1 shards only the `12Ψ` bytes of optimizer state across `Nd=64`: `4Ψ + 12Ψ/64 = 30GB + 1.4GB = 31.4GB`. Stage 3 shards everything: `16Ψ/64 = 1.875GB` — a 64x reduction from baseline.
**Follow-up trap:** *"What's the price paid for Stage 3's extra memory savings over Stage 1?"* — additional communication: since parameters are never held in full on any GPU, they must be all-gathered per-layer during both forward and backward passes, then freed again — bringing total communication volume to roughly 1.5x plain DDP's, versus Stage 1/2's smaller communication overhead premium.

### Q3 — What specifically does FSDP2 change relative to FSDP1's sharding approach, and why does that matter?
**Testing:** a concrete, current (2026) framework distinction, not "FSDP2 is just a newer version."
**Answer:** FSDP1 shards at a flattened, concatenated-parameter granularity (grouping many parameters into large shards); FSDP2 shards at **per-parameter** granularity. This composes more cleanly with mixing dtypes per layer, freezing individual parameters without rewriting sharding logic (directly relevant to LoRA-style fine-tuning), and end-to-end `torch.compile` integration — practical benefits FSDP1's coarser sharding made harder to achieve cleanly.
**Follow-up trap:** *"Is FSDP2 strictly better than DeepSpeed ZeRO-3 in every case?"* — not universally; DeepSpeed's configuration-file-driven interface is easier to adopt without deep familiarity with PyTorch internals, and some DeepSpeed-specific features may not yet have exact FSDP2 equivalents — reported benchmarks show FSDP2 reaching up to roughly 5x ZeRO-3's per-iteration throughput in the regime where both fit memory, which is the strongest current argument for it as a default, not an absolute claim of universal superiority.

### Q4 — Why is tensor parallelism kept within a single node rather than spread across nodes, while pipeline parallelism tolerates cross-node communication better?
**Testing:** connecting communication frequency/pattern directly to network topology decisions.
**Answer:** Tensor parallelism requires a communication operation (all-reduce/all-gather) at *every* tensor-parallel-split layer — very high frequency, making it acutely sensitive to the bandwidth and latency of the interconnect between the participating GPUs; keeping it within one node (fast NVLink) avoids paying that cost at slower inter-node network speeds. Pipeline parallelism only communicates activations/gradients at *stage boundaries* — far less frequent, and each transfer is a large, coherent chunk (the activations for a full micro-batch), which tolerates comparatively slower inter-node links much better.
**Follow-up trap:** *"If you had to choose only one axis to scale across multiple nodes, would you pick tensor parallelism or pipeline parallelism?"* — pipeline parallelism, precisely because of this communication-frequency asymmetry — tensor parallelism spread across nodes tends to produce poor scaling dominated by inter-node communication latency, while pipeline parallelism's much less frequent stage-boundary communication is comparatively well-suited to crossing node boundaries.

### Q5 — Derive the pipeline bubble fraction for 4 pipeline stages with 8 micro-batches, and explain why increasing micro-batch count improves it.
**Testing:** the actual `(P-1)/M` arithmetic and the intuition behind it.
**Answer:** Bubble fraction `≈(P-1)/M = (4-1)/8 = 0.375` — 37.5% of total GPU-time is idle waiting for the pipeline to fill and drain. Increasing to `M=32` micro-batches with the same 4 stages: `(4-1)/32 ≈ 0.094`, or 9.4% idle — because the fixed pipeline fill/drain cost (`P-1` "slots" worth of unavoidable idle time) gets amortized over more total useful work (`M` micro-batches) as `M` grows, shrinking its *fraction* of total time even though its absolute duration is unchanged.
**Follow-up trap:** *"Is there a downside to making micro-batches arbitrarily small to maximize M?"* — yes; each micro-batch carries its own fixed per-step overhead (kernel launch cost, communication latency for passing activations between stages), and making micro-batches too small eventually makes that fixed overhead dominate total time instead of the bubble — there's a real, empirically-tuned sweet spot, not "more micro-batches is unconditionally better."

### Q6 — A team's model doesn't fit in memory even after applying ZeRO Stage 3/FSDP2 with the maximum affordable GPU count. What's the next lever, and why doesn't more data-parallel sharding help further?
**Testing:** recognizing the specific ceiling data-parallel sharding can't address.
**Answer:** ZeRO-3/FSDP2 shard state *across data-parallel replicas*, but still require materializing a *full layer's* parameters/activations on a single GPU at the moment that layer actually computes (via all-gather) — if a single layer itself is too large (or its activations too large) for one GPU, no amount of additional data-parallel sharding helps, since the bottleneck is per-layer, not aggregate-across-the-model. The next lever is tensor parallelism (splitting that oversized layer's matrices across GPUs) and/or pipeline parallelism (splitting model depth across GPUs so no single GPU needs every layer at once) layered on top of the existing data-parallel/ZeRO setup.
**Follow-up trap:** *"Why can't you just keep adding more GPUs to the ZeRO/FSDP data-parallel group instead?"* — because ZeRO/FSDP's sharding denominator is the data-parallel replica count, but the *numerator* (what must be materialized in full for one layer's compute) doesn't shrink no matter how many replicas exist — sharding more finely across more data-parallel replicas keeps reducing the *aggregate* per-GPU average, but the peak instantaneous requirement for one layer's full parameters/activations during its compute step is unchanged, which is exactly the ceiling only tensor/pipeline parallelism (splitting the layer or the depth itself) can address.

### Q7 — Why does ZeRO Stage 3 need roughly 1.5x the communication volume of plain DDP, specifically?
**Testing:** the concrete reason behind the "more sharding costs more communication" tradeoff, not just the fact.
**Answer:** DDP's only communication is the gradient all-reduce, once per backward pass (`≈2Ψ` bytes worth of traffic, per the ring all-reduce arithmetic). ZeRO Stage 3 additionally never holds full parameters on any GPU, so it must all-gather each layer's parameter shard into a full copy immediately before that layer computes in the *forward* pass, and again before it computes in the *backward* pass (since the forward-pass all-gathered copy isn't kept around, to preserve the memory savings) — this adds roughly a full parameter-sized all-gather twice (forward and backward) on top of DDP's existing gradient all-reduce, landing at roughly 1.5x DDP's total communication volume.
**Follow-up trap:** *"Could you avoid the second (backward-pass) all-gather to reduce communication, at some other cost?"* — yes, by keeping the forward-pass all-gathered full parameters resident in memory until backward needs them too — but that reintroduces exactly the per-GPU full-parameter memory cost ZeRO-3 exists to eliminate; this is precisely the memory-versus-communication tradeoff the whole module is about, and there's no way to reduce one without increasing the other for a fixed sharding strategy.

### Q8 — Why do the largest real production training runs combine data parallelism, tensor parallelism, and pipeline parallelism simultaneously, rather than picking the single best one?
**Testing:** understanding that these solve different bottlenecks, not competing solutions to the same problem.
**Answer:** Each technique addresses a different specific ceiling: data parallelism (with ZeRO/FSDP sharding) scales throughput across more GPUs processing more data and reduces per-GPU aggregate memory; tensor parallelism addresses a single layer that doesn't fit on one GPU's memory/compute; pipeline parallelism addresses a model whose total depth doesn't fit, without requiring every individual layer to be split. A model large enough to need any of these typically needs all three simultaneously — no single axis of parallelism addresses every possible ceiling on its own.
**Follow-up trap:** *"How would you decide the degree (how many GPUs) to allocate to each of the three axes for a specific large model and cluster?"* — start from the concrete constraints each axis addresses: tensor-parallel degree sized to fit a single layer's compute/memory within one node's GPU count (bounded by intra-node interconnect, e.g. 8 GPUs on an NVLink-connected node); pipeline-parallel degree sized to fit total model depth across available nodes while keeping the micro-batch count high enough to keep the bubble fraction acceptable; data-parallel degree as whatever's left over to use all remaining available GPUs for throughput — this is real, empirically-tuned cluster-topology-aware engineering, not a formula with one right answer independent of the actual hardware available.

### Q9 — What's the practical difference in when you'd reach for ZeRO/FSDP versus tensor parallelism, given both reduce "memory per GPU"?
**Testing:** disambiguating two techniques that superficially sound like they solve the same problem.
**Answer:** ZeRO/FSDP reduce the *aggregate* memory footprint across a data-parallel group by sharding state across replicas that are otherwise doing independent, parallel work on different data — but at the moment any given layer actually computes, its full parameters must be materialized (all-gathered) on the GPU doing that computation. Tensor parallelism instead genuinely splits a single layer's *computation* across GPUs, so no single GPU ever needs that layer's full parameters materialized at all, even momentarily. The distinction matters precisely when a single layer alone (not the aggregate model) is too large for one GPU — ZeRO/FSDP alone cannot help there, since sharding a data-parallel group doesn't shrink what one GPU must temporarily hold for one layer's compute; only tensor parallelism (or reducing that layer's size) addresses that specific ceiling.
**Follow-up trap:** *"Could ZeRO/FSDP and tensor parallelism be combined, and would you ever need to?"* — yes, and real large-scale training frequently does exactly this — tensor parallelism handles the "one layer too large for one GPU" ceiling, while ZeRO/FSDP (applied across the data-parallel dimension, orthogonal to the tensor-parallel dimension) handles the aggregate memory/throughput scaling across many such tensor-parallel groups training on different data simultaneously.

### Q10 — Design question: you have a model whose full parameters and optimizer state fit comfortably within a single node's aggregate GPU memory (e.g. 8 GPUs), but training on a single GPU alone is far too slow. Would you reach for ZeRO/FSDP, tensor parallelism, pipeline parallelism, or plain DDP, and why?
**Testing:** staff-level judgment matching the actual constraint (throughput, not memory) to the right tool.
**Answer:** If the model already fits (even if tightly) on a single GPU and the actual goal is throughput (processing more data faster, not fitting a model that doesn't fit), plain DDP is the right starting point — it has the simplest failure modes, near-`N`-independent communication cost, and doesn't add sharding/all-gather communication overhead you don't need since memory was never the binding constraint. ZeRO/FSDP-style sharding would only be worth adding if memory pressure genuinely emerges (e.g., wanting a larger batch size than fits with full replication, or wanting headroom for activation memory) — introducing it preemptively for a model that already fits adds real communication overhead for no corresponding benefit.
**Follow-up trap:** *"What would change your answer if the model just barely fits on one GPU today, but the team plans to grow it 5x next quarter?"* — worth building the training pipeline with FSDP2 from the start even before it's strictly necessary, specifically because migrating an existing plain-DDP training setup to sharded training later is nontrivial engineering work, and if 5x growth is a known, near-term plan (not speculative), paying a small amount of avoidable-today communication overhead now buys meaningfully cheaper migration later — a real judgment call trading a known near-term engineering cost against a known near-term scaling need, not a purely technical question.

---

## Red flags that fail you

- Cannot explain why DDP's communication cost doesn't scale proportionally with GPU count, or doesn't know the `(N-1)/N` ring all-reduce arithmetic.
- Cannot state what specifically each ZeRO stage shards, or reproduce even an approximate memory calculation for a given stage.
- Confuses "more GPUs under DDP" with "more available memory per GPU" — doesn't know DDP replicates rather than shards model state.
- Doesn't know why tensor parallelism is communication-frequent and pipeline parallelism is bubble-prone, or can't compute a bubble fraction.
- Believes ZeRO/FSDP alone can solve a single-layer-too-large-for-one-GPU problem.
- Reaches for the most sophisticated parallelism strategy available regardless of whether the actual constraint (memory vs. throughput vs. single-layer size) calls for it.

---

## Cheat card

```
CHOICE = what's REPLICATED vs SHARDED across N GPUs (params/grads/optim state/activations)

DDP: everything replicated, only DATA sharded -> ring all-reduce gradients
  comm cost per GPU ~= 2*(N-1)/N * S -> APPROACHES CONSTANT as N grows (great scaling)
  ceiling: full model must fit on EVERY GPU

ZeRO (mixed precision Adam, 16*Psi bytes total: 2Psi fp16 params + 2Psi fp16
  grads + 4Psi fp32 master + 4Psi momentum + 4Psi variance; optim state=12Psi=75%)
  worked example Psi=7.5B, Nd=64:
    baseline (replicate all):        120 GB/GPU
    Stage1 Pos (shard optim only):   4Psi + 12Psi/Nd  = 31.4 GB
    Stage2 Pos+g (+ shard grads):    2Psi + 14Psi/Nd  = 16.6 GB
    Stage3 Pos+g+p (+ shard params): 16Psi/Nd         =  1.9 GB  (64x reduction)
  cost: Stage3 all-gathers full params per-layer, FWD and BWD -> ~1.5x DDP comm

FSDP = PyTorch-native ZeRO-3 equivalent. FSDP2: PER-PARAMETER sharding (not
  flattened like FSDP1) -> composes w/ torch.compile, mixed dtypes, LoRA-style
  frozen params. Reported up to ~5x ZeRO-3 throughput where both fit memory.
  2026 default recommendation for new training code.

TENSOR PARALLEL: split ONE weight matrix across GPUs (Megatron-style)
  comm EVERY split layer -> bandwidth/latency sensitive -> keep WITHIN one
  fast-interconnect node (NVLink), not across nodes

PIPELINE PARALLEL: split LAYERS (stages) across GPUs
  BUBBLE FRACTION ~= (P-1)/M   (P=stages, M=microbatches)
    P=4,M=8:  37.5% idle       P=4,M=32:  9.4% idle   <- more microbatches shrinks it
  interleaved (1F1B) schedules shrink bubble further, more scheduling complexity

REAL SCALE = ALL combined (3D parallelism): data-parallel groups (ZeRO/FSDP
  internally) x tensor-parallel (within node) x pipeline-parallel (across nodes)
  -- each axis fixes a DIFFERENT ceiling (throughput / one-layer-too-big /
  whole-model-too-deep), not competing choices for the same problem
```

## Sources

- [ZeRO: Memory Optimizations Toward Training Trillion Parameter Models — Rajbhandari et al. (2020)](https://arxiv.org/abs/1910.02054) — accessed 2026-08-03
- [Fully Sharded Data Parallel (FSDP2) — PyTorch documentation](https://docs.pytorch.org/docs/stable/fsdp.html) — accessed 2026-08-03
- [DeepSpeed vs PyTorch FSDP comparison, 2026 — VRLA Tech](https://vrlatech.com/deepspeed-vs-pytorch-fsdp-which-distributed-training-framework-in-2026/) — accessed 2026-08-03
- [GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism — Huang et al. (2019)](https://arxiv.org/abs/1811.06965) — accessed 2026-08-03
- [Megatron-LM: Training Multi-Billion Parameter Language Models Using Model Parallelism — Shoeybi et al. (2019)](https://arxiv.org/abs/1909.08053) — accessed 2026-08-03
- [Distributed LLM Training: FSDP, DeepSpeed ZeRO-3, Megatron-Core Multi-Node Setup Guide (2026) — Spheron Blog](https://www.spheron.network/blog/distributed-llm-training-fsdp-deepspeed-megatron-multi-node/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
