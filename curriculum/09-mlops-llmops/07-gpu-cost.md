# GPU Capacity & Cost Engineering, Autoscaling, Spot

> **Track:** T09 MLOps / LLMOps · **Time:** 2.0h · **Prereqs:** T05-inference-serving, T09-serving, T09-bedrock-vs-sagemaker · **Updated:** 2026-08-05
> **Module id:** `T09-gpu-cost` · **Tags:** cost,gpu,autoscaling,spot,capacity,critical
> **Lab:** `labs/python/07-gpu-cost/`

## The 30-second version

Every GPU cost question reduces to one identity: `$/1M tokens = (instance $/hr) / (tokens/hr) / utilisation`, and the third term is the one people never measure. VRAM is not "model size" but weights + KV cache + activation workspace, and for anything past a couple of thousand tokens of context the KV cache is the term that decides your batch size: Llama 3.1 8B in BF16 is 15.0 GiB of weights and 128 KiB of KV *per token*, so a single 128k-context request costs 16 GiB, more than the weights. Tokens/sec on the decode path is a memory-bandwidth division, not a mystery: reading 16.06 GB of BF16 weights across an H100's 3.35 TB/s takes 4.8 ms, which caps you at ~209 decode steps/sec and makes batch size the only throughput lever you have. That arithmetic produces the counter-intuitive result that a $12.29/hr H100 is roughly 3.7x *cheaper per token* than a $1.21/hr A10G, and the further one that a 3-year reserved `p5.48xlarge` at $43.16/hr is cheaper than the same instance on spot at $57.76/hr, so spot is a tool for capacity *above* your committed baseline and not a replacement for it. Autoscale on `vllm:num_requests_waiting` and TTFT rather than GPU utilisation, size your steady-state headroom to the scale-out latency (3-8 minutes for a cold GPU replica, which forces you to run at 40-60% and not the 90% the unit-cost math wants), and treat quantisation as the cheapest capacity you can buy: FP8 W8A8 is empirically lossless on the Llama-3.1 family and halves both weight and KV footprint.

## Why this gets asked

The interviewer has signed off on a GPU budget that turned out to be wrong by a factor of three, in one of two directions, and both scars produce the same question.

The over-spend scar: someone sized a fleet from "the model is 8B, so 16 GB, so an A10G is fine", shipped, then discovered that at 4k context and eight concurrent users the KV cache had eaten everything left on the card, vLLM was logging `Sequence group N is preempted by PreemptionMode.RECOMPUTE`, throughput had collapsed to something worse than batch-of-one, and the fix was a 4x more expensive instance class. The under-spend scar is the mirror image: a fleet sized for the peak, running at 18% average utilisation, invoiced at $60k/month, where the honest post-mortem is that nobody ever computed dollars per million tokens and compared it to the hosted API they had rejected.

What they are actually probing is whether you can *do the arithmetic in the room*. Not "spot is cheaper" but how much cheaper against a 3-year commit, and what the interruption exposure costs. Not "we autoscale" but on which signal, with what lag, and how much headroom that lag forces you to keep permanently idle. At principal level the strongest single tell is whether you distinguish the prefill and decode phases when you talk about throughput, because a candidate who quotes one "tokens/sec" number for a workload has not run one.

This module owns the numbers. The control-plane argument (which platform schedules the replicas, and what its cold-start contract with your caller is) belongs to `T09-serving`; the managed-versus-self-hosted decision framing belongs to `T09-bedrock-vs-sagemaker`. Neither of those does the sizing math, and this one does nothing else.

---

## Lineage: past → present → future

**What came before.** Capacity planning for deep-learning inference before 2023 was a batch-size-times-latency table, and it worked because the models were stateless per request. You measured p99 for batch sizes 1, 8, 32, picked the largest batch that met your SLO, divided your QPS by it, and provisioned. Static batching (the TensorFlow Serving and TorchServe model) assembled a batch, ran it, returned it, and started over. The pain that killed this was structural, not incremental: autoregressive decoding makes request durations vary by two orders of magnitude in the same batch, so a static batch runs at the speed of its longest member and every other slot sits idle burning GPU-seconds. A batch of 32 where 31 requests finish at 50 tokens and one runs to 2,000 wastes roughly 97% of the slot-time. The second failure was memory: pre-2023 servers pre-allocated a contiguous KV buffer per sequence sized to `max_model_len`, so a request that generated 100 tokens against a 4,096-token limit reserved and wasted 4,000 tokens' worth of VRAM. The vLLM paper (Kwon et al., *Efficient Memory Management for Large Language Model Serving with PagedAttention*, SOSP 2023) measured that existing systems wasted 60-80% of KV cache memory to this internal and external fragmentation. Those two wastes compounded: fragmentation shrank the batch, and static batching wasted the batch you had left.

Orsi Yu et al.'s Orca (OSDI 2022) supplied the scheduling half of the fix (iteration-level, now universally called continuous batching), and PagedAttention supplied the memory half by allocating KV in fixed blocks (vLLM's default `block_size` is 16 tokens) from a shared pool, exactly the way an OS pages virtual memory. Together they took the wasted fraction from 60-80% down to under a block per sequence, and turned throughput from a batch-size table into a function of how many tokens of KV you can hold.

**Where it stands now.** The settled consensus: continuous batching and paged KV are table stakes, prefix caching is on by default in vLLM V1, chunked prefill is on by default in V1 whenever the model supports it, and the correct autoscaling signal is engine queue depth rather than any hardware counter. What is genuinely contested, and where interviews get interesting:

*(1) What utilisation target is honest.* The unit-economics argument says drive GPUs to 85-90% and your cost per token falls proportionally. The availability argument says a cold GPU replica takes 3-8 minutes to serve traffic, so a fleet at 90% cannot absorb any ramp faster than that, and the only real defence is idle headroom. Both are correct and they contradict; the number you pick is a stated SLO decision, not a best practice. Teams that claim 85% steady-state either have very smooth traffic or are quietly shedding load.

*(2) Whether spot belongs under interactive inference at all.* One camp runs 60-80% spot behind a drain-on-notice handler and treats a lost replica as a routine event. The other observes that spot interruptions are *correlated* (a capacity pool disappears, not an instance) and that on the largest accelerators the 3-year reserved rate is now below the spot rate, making the risk unpaid. As of today the second position has arithmetic behind it for `p5.48xlarge` and `g5.2xlarge` in us-east-1, which is a checkable claim and not an opinion.

*(3) How far quantisation goes before it costs you.* The largest empirical study to date (over 500,000 evaluations across the Llama-3.1 family) reports FP8 W8A8 "effectively lossless across all model scales", well-tuned INT8 W8A8 at 1-3% degradation, and INT4 weight-only (W4A16) "rivaling 8-bit" [*"Give Me BF16 or Give Me Death"? Accuracy-Performance Trade-Offs in LLM Quantization*, Kurtic et al., ACL 2025, arXiv:2411.02355v4](https://arxiv.org/abs/2411.02355) — accessed 2026-08-05. The dissent is that academic benchmarks are exactly where quantisation damage hides, and that long-context and agentic multi-turn workloads degrade more than MMLU suggests; there is published work specifically asking whether quantisation hurts long-context tasks ([arXiv:2505.20276](https://arxiv.org/abs/2505.20276)). The safe production statement: FP8 weights and FP8 KV cache are close to free, INT4 needs a task-specific eval before you ship it.

*(4) Whether disaggregated prefill/decode is worth its complexity yet.* Prefill is compute-bound and decode is bandwidth-bound; running both on one GPU underuses whichever resource the other phase needs. Separating them is unambiguously right in theory and is production at a handful of very large shops. Below a few dozen GPUs the routing and KV-transfer overhead eats the win.

**Where it's heading.** *High confidence:* KV cache moves off the accelerator. FP8 KV cache is already mainstream, and offloading cold prefixes to host DRAM and NVMe is the next lever, because the ratio of "prefix I might reuse" to "VRAM I can afford" only gets worse as context windows grow. *High confidence:* per-token cost keeps falling faster than per-GPU-hour cost rises, because most of the improvement comes from software (scheduler, cache-aware routing, quantisation) rather than silicon, and software improvements land on hardware you already own. *Medium confidence:* purchase-mode arbitrage narrows. Spot rates on the newest accelerators have already crossed above multi-year reserved rates in some regions, and if that persists, spot returns to what it originally was, an overflow tier, rather than a primary capacity strategy. *Medium confidence:* reasoning models make capacity planning harder in a specific way that most teams have not yet budgeted for: hidden reasoning tokens are decode tokens, they consume KV cache, and a workload that switches on extended thinking can multiply its decode load by 10x with no change in request rate. *Speculative:* GPU capacity becomes something you buy in fixed reserved blocks with a scheduler on top rather than as elastic instances, which is already the direction AWS Capacity Blocks and the various GPU-cloud reservation products point; AWS raised EC2 Capacity Block prices roughly 20% effective 2026-07-01, which is a demand signal, not a cost signal (secondary-sourced, see Sources).

---

## Mental model

One identity, three levers, and everything in this module is one of them.

```
                     instance $/hr
  $ per 1M tokens = ─────────────────────  ÷  utilisation
                     tokens/hr at full batch

          │                    │                     │
          │                    │                     └── SCHEDULING & TRAFFIC
          │                    │                         continuous batching,
          │                    │                         chunked prefill, prefix
          │                    │                         cache, autoscaling lag,
          │                    │                         headroom you must waste
          │                    │
          │                    └── PHYSICS
          │                        decode ≈ memory-bandwidth-bound
          │                        prefill ≈ compute-bound
          │                        batch size gated by VRAM left after
          │                        weights + activations
          │
          └── PROCUREMENT
              on-demand vs 1yr RI vs 3yr RI vs spot vs serverless vs managed markup
```

Most engineers optimise the first term (pick a cheaper instance), which is the *weakest* of the three. Utilisation is a pure multiplier with a 3-5x range in practice. Scheduling is worth 5-10x against a naive server. Procurement is worth about 2x. Instance class is worth well under 2x once you compute per-token rather than per-hour, and often points the *opposite* way from intuition.

The second model you need is the VRAM budget, because it is what actually decides your batch size and therefore your denominator:

```
 ┌─ physical VRAM on the card (H100 SXM 80GB → nvidia-smi 81,559 MiB ≈ 79.6 GiB)
 │
 ├─ × gpu_memory_utilization        vLLM default 0.92  → 73.2 GiB usable
 │
 │   ┌──────────────────────────────────────────────┐
 │   │ MODEL WEIGHTS         params × bytes/param   │  8B BF16 → 15.0 GiB
 │   │                       fixed, never grows     │  70B BF16 → 131.5 GiB
 │   ├──────────────────────────────────────────────┤
 │   │ ACTIVATION WORKSPACE  scales with            │  ~2-4 GiB at
 │   │                       max_num_batched_tokens │  8192 token budget
 │   │                       + CUDA graph capture   │
 │   ├──────────────────────────────────────────────┤
 │   │ KV CACHE POOL         everything left over   │  ← THIS is your
 │   │                       = your concurrency     │    batch size
 │   └──────────────────────────────────────────────┘
 │
 └─ fragmentation: paged, block_size=16 tokens
    internal waste ≤ 15 tokens per sequence (was 60-80% pre-PagedAttention)
```

The corollary people miss: **weights are a fixed cost, KV is the variable cost, and the variable cost is per token of context, not per request.** Doubling your average context halves your concurrency at constant VRAM, which doubles your cost per token, and nothing in your dashboards will say "context length" unless you put it there.

And the third model, for autoscaling, because the identity above assumes you can actually reach the utilisation you planned:

```
 traffic step change
   │
   ├─ t+0s     requests queue in the engine (vllm:num_requests_waiting rises)
   ├─ t+15-30s Prometheus scrapes the metric
   ├─ t+30s    KEDA polls (pollingInterval default 30s)
   ├─ t+15s    HPA sync loop notices the changed target
   ├─ t+0s     scale-up stabilizationWindowSeconds (default 0 up, 300 down)
   ├─ t+60-180s node provisioning: EC2 launch + GPU driver + device plugin
   ├─ t+60-200s image pull, 8-15 GB CUDA image, if not pre-staged
   ├─ t+20-140s weight fetch from S3/HF (16 GB @ ~1 GB/s … 140 GB)
   └─ t+20-90s  engine init, KV pool alloc, torch.compile, CUDA graph capture
                                                    ─────────────────────────
                                       realistic new GPU replica: 3-8 minutes
```

Compare that to how fast traffic moves and you get the headroom equation directly. If your traffic can double in `T` seconds and a replica takes `L` seconds to arrive, you must hold at least `L/T` of your current capacity idle or you will shed load. Traffic that doubles over 5 minutes with a 5-minute scale-out means 100% headroom, meaning a steady-state utilisation ceiling of 50%. That is the honest reason production GPU fleets run at 40-60% and not the 90% the cost model wants, and saying it out loud is a stronger answer than any autoscaler configuration.

---

## How it actually works

### VRAM, derived from the config file

Everything starts from `config.json`. Nothing here needs a calculator website. Convention for this whole module: **GiB = 2^30 bytes** (what `nvidia-smi` reports), **GB = 10^9 bytes** (what bandwidth specs use). Mixing them is a 7% error and it is the single most common arithmetic slip in this interview.

Take Llama 3.1 8B Instruct. From its published config: `num_hidden_layers=32`, `num_attention_heads=32`, `num_key_value_heads=8`, `hidden_size=4096`, `head_dim=128`, `max_position_embeddings=131072`, `torch_dtype=bfloat16`.

**Term 1, weights.** 8.03B parameters × 2 bytes/param = 1.606 × 10^10 bytes = **14.96 GiB**. Round to 15.0. This term is constant. It does not care about batch size, context, or traffic.

**Term 2, KV cache.** Per token, per sequence:

```
kv_bytes_per_token = 2 (K and V) × n_layers × n_kv_heads × head_dim × dtype_bytes
                   = 2 × 32 × 8 × 128 × 2
                   = 131,072 bytes
                   = 128 KiB per token
```

Note `n_kv_heads = 8`, not `n_attention_heads = 32`. Grouped-query attention is a 4x KV reduction on this model and using the wrong head count is the second most common slip. On Llama 3.3 70B (`n_layers=80`, `n_kv_heads=8`, `head_dim=128`) the same formula gives 2 × 80 × 8 × 128 × 2 = 327,680 bytes = **0.3125 MiB per token**, so GQA is doing even more work there: 64 attention heads collapse to 8 KV heads, an 8x saving.

Now the numbers that matter:

| Model | KV/token | 4k ctx | 32k ctx | 128k ctx |
|---|---|---|---|---|
| Llama 3.1 8B BF16 | 128 KiB | 0.5 GiB | 4.0 GiB | 16.0 GiB |
| Llama 3.3 70B BF16 | 320 KiB | 1.25 GiB | 10.0 GiB | 40.0 GiB |
| Llama 3.1 8B, FP8 KV | 64 KiB | 0.25 GiB | 2.0 GiB | 8.0 GiB |

**One 128k-context request against the 8B model costs 16.0 GiB of KV, which is more than the 15.0 GiB of weights.** That single line is worth memorising because it reframes the whole problem: past a certain context, you are not serving a model, you are serving a cache.

**Term 3, activation workspace.** vLLM measures this at startup by running a profiling forward pass at the configured token budget, then sizes the KV pool with what is left. It scales with `max_num_batched_tokens` and with CUDA graph capture. For an 8B at an 8,192-token budget it lands around 2-4 GiB. You do not compute this analytically in an interview; you say "vLLM profiles it, it's a few GiB, and it grows if I raise `max_num_batched_tokens`", which is both true and the right level of detail.

**Term 4, fragmentation.** PagedAttention allocates KV in blocks; vLLM's `DEFAULT_BLOCK_SIZE` is **16 tokens** (`vllm/config/cache.py`, main branch). Internal fragmentation is therefore at most 15 tokens per sequence, or ~1.9 MiB on the 8B model. At 256 concurrent sequences that is under 500 MiB, well under 1% of the pool. Compare the 60-80% waste the vLLM paper measured in pre-paged systems and you have the entire justification for the design in one comparison.

### Putting it together: how many concurrent requests fit

H100 SXM 80GB. `nvidia-smi` reports 81,559 MiB, so 79.6 GiB physical.

```
usable          = 79.6 × 0.92 (gpu_memory_utilization default) = 73.2 GiB
- weights                                                      = 15.0 GiB
- activations + CUDA graphs (measured)                         ≈  3.0 GiB
────────────────────────────────────────────────────────────────────────
KV pool                                                        = 55.2 GiB
                                                               = 452,800 tokens
```

That pool is your concurrency budget, and it is spent in tokens, not requests:

| Avg context | Concurrent sequences |
|---|---|
| 2,048 | 221 |
| 4,096 | 110 |
| 8,192 | 55 |
| 32,768 | 13 |
| 131,072 | 3 |

Two consequences to state out loud. First, `max_num_seqs` on an H100-class card defaults to **1024** for the OpenAI API server path (vLLM sets 16384/8192 token budgets and 1024 sequences when the device has ≥70 GiB and is not an A100; otherwise 8192/2048 and 256 — see `EngineArgs.get_batch_defaults` in `vllm/engine/arg_utils.py`, main branch). At 8k average context you can only physically hold 55, so the sequence limit is not what is binding you, the KV pool is. Second, the same card running the same model has a 70x concurrency range depending purely on context length. Any capacity plan that does not carry a context-length distribution is not a plan.

Now the small card, because this is where the interesting result lives. A10G, 24 GB (22.5 GiB reported):

```
usable   = 22.5 × 0.92 = 20.7 GiB
- weights              = 15.0 GiB
- activations          ≈  1.5 GiB
───────────────────────────────────
KV pool                =  4.2 GiB = 34,700 tokens
```

At 4k context that is **8 concurrent sequences**. The model "fits" and the deployment is functionally useless for throughput. Every request beyond eight queues, and if you raised `max_num_seqs` past the pool's capacity, vLLM preempts and recomputes instead, which is worse than queueing.

### Tokens/sec, derived from bandwidth not benchmarks

Decode and prefill are different machines. Treat them separately or your numbers will be nonsense.

**Decode is memory-bandwidth-bound.** To emit one token for one sequence you must read every weight once. Batching amortises that read across the whole batch, which is the entire reason batching works. On an H100 SXM (3.35 TB/s HBM3):

```
t_step ≥ weight_bytes / bandwidth = 1.606e10 / 3.35e12 = 4.79 ms
max decode steps/sec               = 209
throughput at batch B              = 209 × B tokens/sec   (weight-read limit only)
```

But the KV cache also has to be read every step, and at large batch it dominates. Per step you read `B × avg_ctx × kv_bytes_per_token`. At B=256 and 1,800 tokens of average context that is 256 × 1800 × 131072 = 60.4 GB, nearly four times the weights. Total 76.5 GB per step at 3.35 TB/s = 22.8 ms, giving 256 / 0.0228 = **11,200 output tokens/sec**.

That is worth checking against a measured number, and it lands: published vLLM benchmarks put Llama 3.1 8B on a single H100 at roughly 11,200 output tokens/sec aggregate at concurrency 256 (secondary-sourced, [aimultiple LLM inference engine comparison](https://aimultiple.com/inference-engines) — accessed 2026-08-05). The roofline and the benchmark agree to within the precision either deserves, which is the point: **you can derive this to one significant figure without running anything**, and in an interview that is far more persuasive than a memorised benchmark.

Run the same derivation on the other cards. Weight-read floor for the 8B model:

| GPU | HBM bandwidth | Weight-read step | Max steps/s | Realistic aggregate decode |
|---|---|---|---|---|
| A10G (24 GB) | 600 GB/s | 26.8 ms | 37 | ~300 tok/s at B=8 |
| L40S (48 GB) | 864 GB/s | 18.6 ms | 54 | ~1,400 tok/s at B=32 |
| H100 SXM (80 GB) | 3.35 TB/s | 4.79 ms | 209 | ~11,200 tok/s at B=256 |
| H200 SXM (141 GB) | ~4.8 TB/s | 3.35 ms | 299 | higher, and holds far more KV |

The A10G's problem is not just that it is slow per step, it is that its tiny KV pool caps `B` at 8, and throughput is `steps/s × B`. It loses on both factors simultaneously. That compounding is what makes the per-token result so lopsided.

**Prefill is compute-bound.** FLOPs for a forward pass ≈ 2 × params × tokens, so 2 × 8.03e9 = 16.06 GFLOP per prompt token. An H100's dense BF16 tensor-core throughput is ~989 TFLOP/s; real serving MFU on prefill is 35-50%, so call it 400 TFLOP/s:

```
prefill tokens/sec = 4.0e14 / 1.606e10 = ~24,900 prompt tokens/sec
TTFT floor for a 2,000-token prompt = 2000 / 24900 = 80 ms
```

So on the same GPU, prefill runs at roughly 25k tok/s and decode at roughly 11k tok/s, and they contend for the same silicon. This is why a long-prompt/short-answer workload (RAG, classification) and a short-prompt/long-answer workload (chat, agents) have completely different cost curves on identical hardware, and why quoting one tokens/sec figure for "the model" is a red flag.

### Dollars per million tokens

Now divide. `p5.48xlarge` is 8× H100 80GB at $98.32/hr on-demand in us-east-1, $57.76/hr spot, $43.157/hr on a 3-year standard reserved [ec2.shop pricing API](https://ec2.shop) — accessed 2026-08-05. Per H100-hour: $12.29 on-demand, $7.22 spot, $5.39 reserved.

At 11,200 output tok/s a fully loaded H100 produces 11,200 × 3600 = 40.32M tokens/hour.

```
$/1M output tokens = ($ per GPU-hour) / 40.32

  on-demand   12.29 / 40.32 = $0.305
  spot         7.22 / 40.32 = $0.179
  3yr reserved 5.39 / 40.32 = $0.134
```

Do the same for the other instances, using their derived throughputs:

| Instance | GPU | $/hr | $/GPU-hr | Derived tok/s | $/1M tokens @ 100% util |
|---|---|---|---|---|---|
| `g5.2xlarge` | 1× A10G 24GB | $1.212 | $1.212 | ~300 | **$1.12** |
| `g6e.2xlarge` | 1× L40S 48GB | $2.242 | $2.242 | ~1,400 | **$0.445** |
| `p5.48xlarge` | 8× H100 80GB | $98.32 | $12.29 | ~11,200 | **$0.305** |
| `p5.48xlarge` spot | 8× H100 80GB | $57.76 | $7.22 | ~11,200 | **$0.179** |
| `p5.48xlarge` 3yr RI | 8× H100 80GB | $43.16 | $5.39 | ~11,200 | **$0.134** |

Hourly rates from [ec2.shop](https://ec2.shop) — accessed 2026-08-05; throughputs derived above, not vendor-published. Note that ec2.shop labels the `g6e` family's accelerator as an L4; the 48 GB per-GPU figure it also reports identifies it as an L40S, and I have used L40S specs. `p5en.48xlarge` (8× H200 141GB) lists at $84.80/hr on-demand with no spot or reserved price published, which is itself informative: the newest capacity is sold, not discounted.

**The headline result: the $12.29/hr H100 is 3.7x cheaper per token than the $1.21/hr A10G.** The cheap instance is the expensive one. This inverts most engineers' intuition and it is the single most useful thing in this module, because it generalises: on bandwidth-bound decode workloads, per-token cost tracks `$/hr ÷ bandwidth ÷ achievable batch`, and the big card wins on both denominators at once.

The caveat that keeps it honest, and that a good interviewer will push on: this table assumes you can *fill* the batch. An H100 at concurrency 8 instead of 256 produces roughly 209 × 8 = 1,670 tok/s, and $12.29 / (1670 × 3600 / 1e6) = **$2.04 per 1M tokens**, which is now worse than the A10G. The big GPU is only cheaper if you have the traffic to saturate it. That is the utilisation term, and it is the subject of the next section.

### Utilisation is the lever, and it has three sub-levers

Divide any number in that table by your utilisation. A fleet at 25% pays $1.22/1M on hardware whose floor is $0.305. Moving from 25% to 70% is a **2.8x cost reduction**, larger than the entire spread between an A10G and an H100 on the same table, and it costs no capital.

Utilisation for an LLM server is not one number. It decomposes into three, and each has a specific mechanism:

**(a) Slot utilisation: continuous batching.** Under static batching a batch runs until its slowest member finishes and every completed slot idles. With decode lengths distributed roughly log-normally (which they are, in every chat workload I have measured), the mean-to-max ratio inside a batch of 32 is commonly 5-15x, so static batching wastes 80-93% of slot-time. Continuous batching evicts finished sequences and admits waiting ones at every scheduler iteration, so a slot is refilled within one decode step (~5 ms on an H100 rather than the ~30 s the longest member would take). This is the single largest software win available and it is on by default in every current engine, which means the interview question is not "would you use it" but "what does it cost you", and the answer is that per-iteration scheduling has a CPU cost, which is why a slow tokenizer or an overloaded API process can starve the GPU (see the failure table).

**(b) Phase utilisation: chunked prefill.** Prefill saturates compute; decode saturates bandwidth. Run them in separate iterations and each phase leaves the other resource idle. Worse, a 4,000-token prefill occupies the GPU for ~160 ms, during which every in-flight decode stalls, showing up as an inter-token-latency spike, not a throughput number. Chunked prefill splits a long prefill into pieces that fit the remaining `max_num_batched_tokens` budget and co-schedules them with decodes. vLLM V1 enables it by default whenever the model supports it, and prioritises decode: it batches all pending decodes first, then fills the remaining token budget with prefill chunks [vLLM Optimization and Tuning](https://github.com/vllm-project/vllm/blob/main/docs/configuration/optimization.md) — accessed 2026-08-05. The tuning dial is `max_num_batched_tokens`, and it is a direct ITL-versus-TTFT trade: smaller values (2048) give better ITL because less prefill interrupts decode; larger values give better TTFT; the docs recommend >8192 for throughput, especially small models on large GPUs. Defaults are 8192 for the OpenAI API server on a ≥70 GiB non-A100 device and 2048 otherwise.

**(c) Compute utilisation: prefix caching.** If 800 tokens of system prompt are shared across every request, recomputing them per request is pure waste. APC hashes KV blocks and reuses them; it is on by default in V1 for models that support it. The observable is `vllm:prefix_cache_hits / vllm:prefix_cache_queries`, and on a RAG or agent workload with a fat system prompt a hit rate of 0.6-0.9 is normal. The arithmetic: at 2,000 prompt tokens of which 800 are a shared prefix, a 100% prefix hit removes 40% of your prefill FLOPs, which on a prefill-heavy workload is a 40% capacity increase for free. The catch is that it only works if the *same replica* sees the *same prefix*, which is why round-robin load balancing in front of a multi-replica vLLM fleet actively destroys this and prefix-aware routing recovers it. That routing mechanism belongs to `T09-serving`; the cost consequence belongs here.

There is a fourth lever that is not really about utilisation but shows up in the same conversation: **speculative decoding**. It trades compute for latency, verifying several draft tokens per target-model step. It raises tokens/sec per *sequence* but at high batch it often lowers aggregate throughput, because the extra verification FLOPs come out of the same budget. Use it for low-concurrency latency-sensitive serving, not for a saturated fleet.

### Autoscaling: the right signal, and why the lag forces headroom

**GPU utilisation is the wrong signal and it is worth being precise about why.** During decode, the SMs are busy waiting on memory the entire time; `nvidia-smi` reports near-100% utilisation for a batch of 1 and for a batch of 256 alike, because the metric is "fraction of time at least one kernel was resident", not "fraction of peak FLOPs". A vLLM replica at 98% GPU utilisation with an empty queue is healthy and must not scale out. A replica at 45% GPU utilisation with 200 requests waiting is saturated on KV cache and must. The metric cannot distinguish them. CPU utilisation is worse: it tells you about your tokenizer.

The signals that do work, with their real names in current vLLM (note the rename: the old `vllm:gpu_cache_usage_perc` is now **`vllm:kv_cache_usage_perc`**, verified in `vllm/v1/metrics/loggers.py` on main):

| Metric | What it means | Use it for |
|---|---|---|
| `vllm:num_requests_waiting` | requests admitted to the server but not yet running | primary scale-out trigger |
| `vllm:num_requests_running` | sequences currently in the batch | denominator for saturation |
| `vllm:kv_cache_usage_perc` | fraction of the KV pool allocated | early warning; >0.85 sustained means preemption is imminent |
| `vllm:num_preemptions` | cumulative RECOMPUTE preemptions | this should be **zero**; any sustained rise is a sizing bug |
| `vllm:time_to_first_token_seconds` | TTFT histogram | SLO-facing scale trigger, p95 |
| `vllm:request_queue_time_seconds` | time spent waiting before first schedule | isolates queueing from engine slowness |
| `vllm:prefix_cache_hits` / `_queries` | APC effectiveness | routing quality, not scaling |

A defensible policy, with derivations rather than magic numbers:

```yaml
# untested sketch — KEDA ScaledObject shape, values derived below
triggers:
  - type: prometheus
    metadata:
      query: sum(rate(vllm:num_requests_waiting[1m])) / sum(vllm:num_requests_running)
      threshold: "0.10"          # queue = 10% of running set
  - type: prometheus
    metadata:
      query: |
        histogram_quantile(0.95,
          sum by (le) (rate(vllm:time_to_first_token_seconds_bucket[2m])))
      threshold: "0.8"           # your TTFT SLO, in seconds
```

Why 10% and not 50%: Little's Law. If `L` requests are in the system and each takes `W` seconds, arrival rate `λ = L/W`. A queue that is 10% of the running set means roughly 10% of a request's latency is queueing, which for a 3-second generation is 300 ms of added TTFT. If your SLO has 800 ms of TTFT budget and prefill already spends 80-150 ms of it, 300 ms of queueing is the point where you are eating the margin. Pick the threshold from your SLO, not from a blog.

**Scale-down needs a different, slower rule than scale-up,** because the cost of a wrong scale-down is a cold start. Use a long stabilization window (Kubernetes HPA defaults to 300 s down, 0 s up, which is the right shape) and gate on the queue being empty *and* `kv_cache_usage_perc` being low for the whole window.

**The lag, and the headroom it forces.** Walk the chain from the mental model: 15-30 s metric scrape, 30 s KEDA poll (default `pollingInterval`), 15 s HPA sync, then 60-180 s to get a GPU node (EC2 launch plus NVIDIA driver plus device-plugin registration), 60-200 s to pull an 8-15 GB CUDA image cold, 20-140 s to fetch weights, and 20-90 s of engine init, KV pool allocation, `torch.compile` and CUDA graph capture. Three to eight minutes, and the *detection* portion alone is a minute before a single instance is even requested.

So the headroom equation is not optional:

```
required_headroom ≥ (expected traffic growth rate) × (scale-out latency)

  example: traffic doubles over 5 min  → growth = 100% / 300 s
           scale-out latency L         = 300 s
           headroom                    ≥ 100%
           ⇒ steady-state utilisation ceiling = 50%
```

Halve `L` and you halve the headroom, which is why the highest-leverage cost work on a GPU fleet is usually **cold-start reduction, not autoscaler tuning**. Pre-pulling the container image via a DaemonSet, staging weights on node-local NVMe, and persisting the `torch.compile` cache (vLLM writes it under `VLLM_CACHE_ROOT`, default `~/.cache/vllm`, and it can be baked into the image; `VLLM_FORCE_AOT_LOAD=1` makes a cache miss fail loudly instead of silently recompiling) can take 5 minutes down to 60-90 seconds, which converts directly into a higher permissible utilisation and therefore a lower cost per token. A warm pool of pre-provisioned nodes is the blunt version of the same idea: you pay for idle nodes so you can run the rest of the fleet hotter, and it is worth it exactly when `headroom_saved × $/GPU-hr > warm_pool_cost`.

### Spot and preemption: the notice windows, and what they actually buy you

The interruption contract differs per cloud and the numbers are the whole answer:

| Cloud | Warning | Earlier signal | Max lifetime | Notes |
|---|---|---|---|---|
| AWS EC2 Spot | **2 minutes** | rebalance recommendation, typically 10-20 min earlier, but "can arrive along with the two-minute notice" | none | [Spot Instance interruption notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html), [rebalance recommendations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/rebalance-recommendations.html) — accessed 2026-08-05 |
| GCP Spot VM | **30 seconds**, best effort | none | none | [Spot VMs, Compute Engine](https://docs.cloud.google.com/compute/docs/instances/spot) — accessed 2026-08-05 |
| GCP Preemptible VM | **30 seconds** | none | **24 hours** | the legacy SKU; the 24 h cap is the only real difference |
| Azure Spot VM | **30 seconds minimum**, via Scheduled Events `Preempt` at 169.254.169.254 | none | none | immediate eviction is possible with no notice at all [About Azure Spot Virtual Machines](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms) — accessed 2026-08-05 |

Two design consequences fall straight out of the table. AWS's 120 seconds is enough to drain an inference replica gracefully: stop accepting new requests, let in-flight generations finish (a p99 generation is usually under 60 s), deregister from the load balancer, exit. GCP and Azure's 30 seconds is *not* enough for a long generation, so on those clouds you either cap `max_tokens` such that p99 generation fits in the window, or you accept that some in-flight requests die and make the client retry. Saying "we drain on the notice" without knowing which window you are working with is the trap.

The second consequence is that Azure explicitly documents that "immediate eviction is possible before the notice", so the notice is an optimisation, not a contract, and the correctness of your system cannot depend on it.

**Checkpointing is a training concern, not an inference one, and conflating them is a tell.** For training, the pattern is fully managed on AWS: SageMaker Managed Spot Training claims up to 90% savings versus on-demand, handles interruption and resumption for you, and requires you to configure `MaxWaitTimeInSeconds > MaxRuntimeInSeconds`; jobs without checkpointing are capped at `MaxWaitTimeInSeconds` of 3600 s [Managed Spot Training in Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/model-managed-spot-training.html) — accessed 2026-08-05. For inference there is no state to checkpoint except the KV cache, which is derivable and therefore cheaper to recompute than to persist. Note also that SageMaker Real-Time inference endpoints do not offer spot at all, which is a live constraint on the student's own production experience and is the cost argument covered in `T09-bedrock-vs-sagemaker`.

**What kills you is correlation, not rate.** Spot interruption *frequency* on GPU instances is often low: `p5.48xlarge` sits in the `<5%` bucket and `g5.2xlarge` in the `15-20%` bucket per the Spot Instance Advisor data surfaced by ec2.shop (accessed 2026-08-05). But a spot interruption is a *capacity pool* event, not a per-instance coin flip: when `p5.48xlarge` capacity in `us-east-1a` is reclaimed, it takes every replica you have in that pool, not one. A fleet of 10 replicas all in one instance type and one AZ can go to zero in two minutes. The mitigations are diversification (multiple instance types across multiple AZs, which for scarce GPU SKUs is often not available), an on-demand or reserved floor sized to your minimum viable capacity, and an overflow valve. Karpenter handles the mechanics: on receiving the interruption notification it cordons and drains the node while provisioning a replacement in parallel [Karpenter disruption docs](https://karpenter.sh/docs/concepts/disruption/) — accessed 2026-08-05. What Karpenter cannot do is conjure GPU capacity that the pool does not have.

### Purchase mode: the breakeven arithmetic, and the surprise

Reserved instances are a utilisation bet. Commit if the fraction of the term you will actually run the instance exceeds the rate ratio:

```
breakeven_utilisation = reserved_hourly_rate / on_demand_hourly_rate
```

Using current us-east-1 rates from [ec2.shop](https://ec2.shop) — accessed 2026-08-05:

| Instance | On-demand | 1yr std RI | 3yr std RI | Spot | 1yr breakeven | 3yr breakeven |
|---|---|---|---|---|---|---|
| `g5.2xlarge` | $1.212 | $0.7636 | $0.5236 | $0.5954 | **63.0%** | **43.2%** |
| `g5.12xlarge` | $5.672 | $3.5734 | $2.4503 | $2.4685 | 63.0% | 43.2% |
| `p4d.24xlarge` | $32.77 | $20.176 | $12.499 | $13.067 | 61.6% | 38.1% |
| `p5.48xlarge` | $98.32 | n/a | $43.157 | $57.762 | — | **43.9%** |

So a 1-year standard RI on `g5.2xlarge` pays for itself if you run the instance more than **63% of the hours in the year** (about 5,520 of 8,760). A 3-year commit pays off above **43%**. Those are hard numbers you can quote and they are trivially re-derivable from any pricing page, which is exactly the sort of thing that reads as competence.

**Now the surprise, and it is the best single fact in this module.** Look at the last two columns for `g5.2xlarge`: 3-year reserved is **$0.5236** and spot is **$0.5954**. Reserved is *cheaper than spot*, with no interruption risk. The same holds on `p4d.24xlarge` ($12.499 reserved vs $13.067 spot) and on `p5.48xlarge` ($43.157 vs $57.762, a 34% gap). On these GPU SKUs, in this region, at this moment, **spot is a worse deal than a multi-year commitment for any capacity you are confident you will use**.

That produces a clean, derived capacity policy rather than a slogan:

```
  ┌──────────────────────────────────────────────────────────────┐
  │ tier 3  SPOT / overflow           bursty, interruption-safe  │
  │         above your confident line; also the right place      │
  │         for batch scoring and eval runs                      │
  ├──────────────────────────────────────────────────────────────┤
  │ tier 2  ON-DEMAND                 the band between your 3yr  │
  │         confidence and your 1yr confidence                   │
  ├──────────────────────────────────────────────────────────────┤
  │ tier 1  RESERVED / Savings Plan   sized to p50 traffic, i.e. │
  │         the capacity you are >43% (3yr) or >63% (1yr) sure   │
  │         you will keep running                                │
  └──────────────────────────────────────────────────────────────┘
```

Worked blend on `p5.48xlarge`, ten node-equivalents of demand, 60% reserved / 40% spot:

```
  all on-demand:            10 × 98.32                    = $983.20/hr
  6 reserved + 4 spot:      6 × 43.157 + 4 × 57.762       = $490.99/hr   (-50.1%)
  all spot (if you dared):  10 × 57.762                   = $577.62/hr   (-41.2%)
```

The blend beats all-spot *and* carries less risk, which is not the answer most candidates give.

Serverless GPU is the fourth mode and the honest position is that on AWS it does not exist for this workload: SageMaker Serverless Inference explicitly excludes GPUs. Its Provisioned Concurrency breakeven (~59% utilisation) is derived in `T09-serving` and applies only to CPU models. Third-party serverless GPU platforms bill per GPU-second with cold starts in the tens of seconds; they win for genuinely spiky sub-hourly workloads and lose badly for anything steady, for the same step-function-versus-linear reason developed in `T09-bedrock-vs-sagemaker`.

### Quantisation as a cost lever, and what it actually costs

Quantisation buys capacity three ways at once, and only the first is usually mentioned:

1. **Smaller weights** → more VRAM left for KV → bigger batch. 8B BF16 is 15.0 GiB; FP8 is 7.5 GiB; W4A16 is ~4.2 GiB (weights only, activations stay 16-bit). On a 24 GiB A10G, going BF16 → W4A16 takes the KV pool from 4.2 GiB to ~15.0 GiB, a **3.6x concurrency increase** on hardware you already own.
2. **Fewer bytes read per decode step** → higher steps/sec, because decode is bandwidth-bound. FP8 weights halve the weight-read term: 8.03e9 bytes / 3.35e12 = 2.4 ms instead of 4.79 ms.
3. **FP8 KV cache** (`--kv-cache-dtype fp8`) halves the *per-token* KV cost, which is the term that actually binds at long context. On the 8B model it goes from 128 KiB to 64 KiB per token, doubling concurrency at fixed context.

The quality cost, from the largest study available (>500,000 evaluations across the full Llama-3.1 family): **FP8 W8A8 is effectively lossless at all model scales; well-tuned INT8 W8A8 loses 1-3%; INT4 weight-only (W4A16) is competitive with 8-bit.** The same paper's deployment guidance is the part people skip and it matters here: **W4A16 is most cost-efficient for synchronous (low-concurrency, latency-bound) setups, while W8A8 dominates in asynchronous continuous batching** [Kurtic et al., ACL 2025, arXiv:2411.02355](https://arxiv.org/abs/2411.02355) — accessed 2026-08-05. The mechanism is that W4A16 dequantises to 16-bit for the matmul, so it saves bandwidth but not compute; at high batch you are no longer bandwidth-bound and the dequantisation overhead is pure loss.

Two caveats to state so you do not sound like you are reading marketing copy. First, benchmark-lossless is not workload-lossless: there is published work specifically probing whether quantisation damages long-context tasks ([arXiv:2505.20276](https://arxiv.org/abs/2505.20276) — accessed 2026-08-05), and structured-output, tool-calling, and multi-turn agentic workloads are exactly where small degradations compound across turns. Run your own eval on your own task before shipping INT4. Second, FP8 requires hardware support (Hopper and later, or Ada); on an A10G or A100 you get INT8 and INT4 and no FP8 fast path, which is another reason the older cards look worse per token than their hourly rate suggests.

---

## Build it from scratch

The point of building this is that the entire capacity model is about 60 lines, it runs from a `config.json`, and being able to produce it live is the difference between a candidate who has *heard about* KV cache and one who has sized a fleet. Reference lab: `labs/python/07-gpu-cost/`.

### A GPU sizing calculator that runs

```python
"""Capacity and cost model for a transformer served with paged KV.
Verified against the worked numbers in this module. Python 3.10+, no deps."""
from dataclasses import dataclass

GiB = 2 ** 30
GB = 10 ** 9
BYTES = {"bf16": 2, "fp16": 2, "fp8": 1, "int8": 1, "int4": 0.5}


@dataclass
class Model:
    params: float            # e.g. 8.03e9
    n_layers: int
    n_kv_heads: int          # NOT n_attention_heads -- GQA is the whole point
    head_dim: int

    def weight_bytes(self, dtype: str = "bf16") -> float:
        return self.params * BYTES[dtype]

    def kv_bytes_per_token(self, kv_dtype: str = "bf16") -> float:
        # 2 = one K tensor + one V tensor
        return 2 * self.n_layers * self.n_kv_heads * self.head_dim * BYTES[kv_dtype]


@dataclass
class GPU:
    vram_gib: float          # what nvidia-smi reports, not the marketing number
    bandwidth_gbps: float    # GB/s, decimal
    dense_bf16_tflops: float


def kv_pool_gib(m: Model, g: GPU, *, util=0.92, activation_gib=3.0,
                w_dtype="bf16") -> float:
    """vLLM: pool = vram*gpu_memory_utilization - weights - profiled activations."""
    return g.vram_gib * util - m.weight_bytes(w_dtype) / GiB - activation_gib


def concurrency(m: Model, g: GPU, avg_ctx: int, *, kv_dtype="bf16", **kw) -> int:
    pool = kv_pool_gib(m, g, **kw) * GiB
    return int(pool / (m.kv_bytes_per_token(kv_dtype) * avg_ctx))


def decode_tokens_per_sec(m: Model, g: GPU, batch: int, avg_ctx: int,
                          *, w_dtype="bf16", kv_dtype="bf16") -> float:
    """Roofline: every decode step reads all weights + the whole live KV cache."""
    per_step = m.weight_bytes(w_dtype) + batch * avg_ctx * m.kv_bytes_per_token(kv_dtype)
    step_s = per_step / (g.bandwidth_gbps * GB)
    return batch / step_s


def prefill_tokens_per_sec(m: Model, g: GPU, mfu: float = 0.40) -> float:
    """Prefill is compute-bound: ~2*params FLOPs per prompt token."""
    return (g.dense_bf16_tflops * 1e12 * mfu) / (2 * m.params)


def cost_per_million(hourly_usd: float, tokens_per_sec: float,
                     utilisation: float = 1.0) -> float:
    return hourly_usd / (tokens_per_sec * 3600 / 1e6) / utilisation


if __name__ == "__main__":
    llama8b = Model(params=8.03e9, n_layers=32, n_kv_heads=8, head_dim=128)
    h100 = GPU(vram_gib=79.6, bandwidth_gbps=3350, dense_bf16_tflops=989)
    a10g = GPU(vram_gib=22.5, bandwidth_gbps=600, dense_bf16_tflops=125)

    print(f"KV per token: {llama8b.kv_bytes_per_token()/1024:.0f} KiB")
    print(f"H100 KV pool: {kv_pool_gib(llama8b, h100):.1f} GiB")
    print(f"  concurrency @ 8k ctx: {concurrency(llama8b, h100, 8192)}")
    print(f"  concurrency @ 8k ctx, fp8 kv: "
          f"{concurrency(llama8b, h100, 8192, kv_dtype='fp8')}")

    tps = decode_tokens_per_sec(llama8b, h100, batch=256, avg_ctx=1800)
    print(f"H100 decode @ B=256, ctx 1800: {tps:,.0f} tok/s")
    print(f"  $/1M on-demand (p5 @ $12.29/GPU-hr): "
          f"${cost_per_million(12.29, tps):.3f}")
    print(f"  $/1M at 35% utilisation:            "
          f"${cost_per_million(12.29, tps, 0.35):.3f}")

    tps_a10 = decode_tokens_per_sec(llama8b, a10g, batch=8, avg_ctx=4096)
    print(f"A10G decode @ B=8, ctx 4096: {tps_a10:,.0f} tok/s")
    print(f"  $/1M (g5.2xlarge @ $1.212/hr): ${cost_per_million(1.212, tps_a10):.3f}")
```

Expected output (this is the arithmetic used throughout the module):

```
KV per token: 128 KiB
H100 KV pool: 55.3 GiB
  concurrency @ 8k ctx: 55
  concurrency @ 8k ctx, fp8 kv: 110
H100 decode @ B=256, ctx 1800: 11,217 tok/s
  $/1M on-demand (p5 @ $12.29/GPU-hr): $0.304
  $/1M at 35% utilisation:            $0.870
A10G decode @ B=8, ctx 4096: 236 tok/s
  $/1M (g5.2xlarge @ $1.212/hr): $1.428
```

Note the A10G line: 236 tok/s, not the ~300 quoted in the earlier table. The table used the weight-read floor (37 steps/s × 8), while this includes the KV read (8 × 4096 × 131,072 = 4.3 GB per step on top of 16.1 GB of weights), which stretches the step from 26.8 ms to 34.0 ms. Both are defensible depending on the context you assume; the KV-inclusive number is the honest one at 4k, and it makes the A10G's per-token cost $1.43 rather than $1.12, which only sharpens the conclusion. **Say which assumption you are using when you quote a throughput number.**

Three things this makes undeniable that a spreadsheet hides. **KV dtype is a concurrency multiplier**, not a footnote: one flag doubles the batch. **Utilisation is a division**, so 35% turns a $0.30 workload into a $0.87 one, which dwarfs any instance-class choice. And **the A10G loses on both terms simultaneously**, because its small pool caps the batch that its low bandwidth was already going to punish.

### An autoscaling simulator that shows why headroom is mandatory

```python
"""Why GPU autoscaling can't be your first line of defence. Untested sketch,
but the arithmetic is the point, not the API."""
from collections import deque


def simulate(rps_series, *, capacity_per_replica, cold_start_s,
             detect_s, min_replicas, target_util):
    """Returns (replica_count, shed_requests) per second."""
    running, starting = min_replicas, deque()   # deque of seconds-remaining
    detected_at, shed = -1, []
    counts = []
    for t, rps in enumerate(rps_series):
        for _ in range(len(starting)):
            starting.append(starting.popleft() - 1)
        while starting and starting[0] <= 0:
            starting.popleft()
            running += 1

        served = running * capacity_per_replica
        shed.append(max(0, rps - served))

        # scale decision is only visible after the detection pipeline delay
        want = -(-rps // (capacity_per_replica * target_util))   # ceil
        if want > running + len(starting) and t - detected_at >= detect_s:
            for _ in range(int(want - running - len(starting))):
                starting.append(cold_start_s)
            detected_at = t
        counts.append(running + len(starting))
    return counts, shed


# A 2x step at t=60s. 10 replicas at 100 rps each. 60s detection, 240s cold start.
flat = [500] * 60 + [1000] * 600
_, shed = simulate(flat, capacity_per_replica=100, cold_start_s=240,
                   detect_s=60, min_replicas=10, target_util=1.0)
print(f"requests shed: {sum(shed):,}")     # ~150,000 -- 300 s at 500 rps deficit
```

Run it and the conclusion is arithmetic, not opinion: with a 60-second detection window and a 240-second cold start, a 2x step change sheds five minutes' worth of the excess *no matter how the autoscaler is configured*, because the capacity does not exist yet. Set `target_util=0.5` (i.e. run at 50% and keep 100% headroom) and `shed` goes to zero. **The autoscaler does not protect you from the spike; the headroom does. The autoscaler protects you from paying for the headroom forever.** That reframing is the staff-level answer.

### A drain handler for spot, in the shape that actually works

```python
# untested sketch -- the control flow is the content
import asyncio, httpx, os

IMDS = "http://169.254.169.254/latest/meta-data/spot/instance-action"  # AWS
# GCP:   http://metadata.google.internal/computeMetadata/v1/instance/preempted
# Azure: http://169.254.169.254/metadata/scheduledevents?api-version=2020-07-01

async def watch_for_interruption(engine, poll_s: float = 5.0):
    async with httpx.AsyncClient(timeout=2.0) as c:
        while True:
            try:
                r = await c.get(IMDS, headers={"X-aws-ec2-metadata-token": token()})
                if r.status_code == 200:          # 404 until the notice fires
                    await drain(engine)
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(poll_s)

async def drain(engine, budget_s: float = 100.0):
    # 1. FAIL READINESS FIRST. The LB must stop sending work before anything else.
    engine.ready = False
    # 2. Let the LB notice. This is the part everyone forgets: deregistration is
    #    not instant, and a k8s readiness probe with periodSeconds=10 and
    #    failureThreshold=3 takes up to 30 s to take the pod out of the Endpoints.
    await asyncio.sleep(readiness_propagation_seconds())      # ~15-30 s on k8s
    # 3. Drain in-flight generations against the remaining budget.
    deadline = asyncio.get_event_loop().time() + budget_s
    while engine.num_running() and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
    # 4. Anything still running gets aborted; the client retries elsewhere.
    engine.abort_all()
```

The load-bearing detail is step 2. On AWS you have 120 seconds, and a Kubernetes readiness probe at the default cadence can consume 30 of them before traffic actually stops arriving. That leaves ~90 seconds to finish in-flight generations, which is fine for chat and not fine for a 4,000-token agentic response. On GCP and Azure the entire budget is 30 seconds, which is less than the readiness propagation alone unless you also proactively deregister from the load balancer. Any spot strategy that has not measured its own readiness-propagation time has an unbounded error in its drain budget.

---

## How it's done in production

### The capacity plan, as an actual document

A real GPU capacity plan is six numbers and one distribution, and if any of them is missing the plan is a guess:

| Input | Where it comes from | Why it binds |
|---|---|---|
| Peak sustained RPS | traffic telemetry, p99 of 5-min buckets | sizes the fleet |
| Peak-to-average ratio | same data | sizes the *waste*; 10:1 kills self-hosting economics |
| Input token distribution (p50/p95) | tokenize your real logs, not your prompts | drives prefill FLOPs and TTFT |
| Output token distribution (p50/p95) | production logs | drives decode seconds per request, the dominant term |
| Context length distribution | p95, not mean | decides KV pool concurrency, which is the batch size |
| Scale-out latency, measured | stopwatch on a real cold replica | sets mandatory headroom |
| TTFT / ITL SLO | product | decides `max_num_batched_tokens` and the scaling threshold |

The single most common planning error is using *means*. Decode length is heavy-tailed; a mean of 300 output tokens with a p95 of 2,000 means your GPU-seconds are dominated by requests you did not budget for. Plan on `p95 × rate`, then validate against measured GPU-seconds per request.

Second most common: forgetting that **reasoning/extended-thinking tokens are decode tokens**. A workload that enables extended thinking generates hidden tokens that consume both decode time and KV cache and never appear in the visible response. A 10x multiplier on decode load with zero change in request rate is entirely possible, and no dashboard keyed on requests-per-second will show it. Track `vllm:generation_tokens` (or the provider's output-token counter), never request count, as your capacity driver.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `torch.OutOfMemoryError` at engine startup, but only when `--max-model-len` is raised | vLLM sizes the KV pool from `gpu_memory_utilization` after weights and profiled activations; raising `max_model_len` raises the profiling forward pass and the CUDA-graph capture footprint, so the pool that fit at 8k does not fit at 32k | Lower `max_model_len` to the p99 you actually serve, or lower `max_num_batched_tokens` (activation workspace scales with it), or set `--kv-cache-dtype fp8`. Do not raise `gpu_memory_utilization` past ~0.95; you will trade a startup OOM for a mid-traffic one |
| Requests fail with a 400 at exactly one sequence length and succeed below it | The request's prompt exceeds `max_model_len`, or `max_num_batched_tokens < max_model_len` with chunked prefill disabled, which vLLM rejects at startup or truncates at admission | Keep chunked prefill on (V1 default); if you disabled it, `max_num_batched_tokens` must exceed `max_model_len` or the server crashes at boot |
| Throughput halves and `vllm:num_preemptions` climbs steadily; latency is bimodal | KV pool cannot hold the running set, so vLLM preempts with `PreemptionMode.RECOMPUTE` and re-runs prefill for evicted sequences. Log line: `Sequence group N is preempted by PreemptionMode.RECOMPUTE mode because there is not enough KV cache space` | Raise `gpu_memory_utilization`, lower `max_num_seqs` or `max_num_batched_tokens`, raise `tensor_parallel_size`, or switch KV to FP8. `vllm:num_preemptions` should sit at zero in a correctly sized deployment; treat any sustained rise as a sizing bug, not a tuning opportunity |
| Aggregate throughput collapses ~40% after moving the fleet to spot; per-replica throughput unchanged | Preemption thrash: replicas are drained and replaced faster than they warm, so a growing fraction of the fleet is in cold start rather than serving. With a 4-minute warm-up and a 20-minute mean replica lifetime, 20% of your fleet is permanently useless | Diversify instance types and AZs; keep a reserved/on-demand floor at minimum viable capacity; measure mean replica lifetime and require `lifetime > 10 × warmup` before spot is defensible; pre-stage weights and image to cut warm-up |
| Deploy or scale event causes a multi-minute latency spike across *all* replicas, then recovers | Cold-start stampede: N replicas simultaneously pull the same 8-15 GB image and the same 16-140 GB of weights, saturating registry and S3 egress and the node's NIC; and readiness passed before CUDA-graph capture finished, so the LB sent traffic to replicas that were still compiling | `maxSurge: 1` on rollout; DaemonSet pre-pull of the runtime image; node-local weight cache; readiness probe that issues a real 1-token generation, not a TCP check; bake the `torch.compile` cache into the image and set `VLLM_FORCE_AOT_LOAD=1` so a cache miss fails loudly |
| `vllm:num_requests_waiting` > 0 while `vllm:kv_cache_usage_perc` < 0.3 and GPU SM utilisation is ~20%; one CPU core pinned at 100% | Idle GPU behind a slow tokenizer: HTTP parsing, tokenization and detokenization are starving the engine. vLLM V1 already splits the API server and engine core into separate processes, but a single API server process is still a bottleneck at high request rates, especially with large data-parallel sizes | Scale the front end with `--api-server-count=N`; verify the fast (Rust) tokenizer is loaded rather than the Python fallback; never construct a tokenizer per request; check that request logging is not doing per-token string work |
| Bill is flat but tokens served dropped 30% | Utilisation fell without the fleet shrinking: traffic shape changed, or scale-down is blocked by a long stabilization window, or a `PodDisruptionBudget`/`do-not-disrupt` annotation is pinning nodes Karpenter wants to consolidate | Alert on **$ per 1M tokens**, computed as (fleet cost / `vllm:generation_tokens`), not on total spend. Total spend is a lagging, uninformative metric |
| p99 TTFT triples after a prompt-template change; token counts look "about the same" | Prefix cache hit rate collapsed because the shared prefix now contains a per-request element (timestamp, user id, retrieved chunk) near the front, so nothing hashes to a cached block | Check `vllm:prefix_cache_hits / vllm:prefix_cache_queries` before and after; move all variable content *after* the stable prefix; templates are a cost surface and belong under change control |
| Autoscaler oscillates: adds replicas, removes them 5 minutes later, repeats | Scaling on a signal that responds to the scaling action faster than the replicas arrive, with symmetric up/down windows. Queue drains the instant the first new replica warms, so scale-down fires before the rest are useful | Asymmetric windows: fast up, slow down (HPA `stabilizationWindowSeconds` 0 up / 300+ down); scale down only when queue is empty *and* `kv_cache_usage_perc` is low for the whole window |
| Cost per token doubles with no config, model, or traffic-volume change | Average context length grew: longer RAG chunks, more retained chat history, or larger tool outputs. KV per token is fixed, so context is a linear multiplier on VRAM and therefore an inverse multiplier on batch size | Chart p50/p95 context length as a first-class capacity metric next to RPS; cap retained history; trim retrieved chunks. This is the most common silent cost regression in RAG systems |
| Spot fleet loses every replica at once despite a "low" interruption rate | Interruptions are pool-scoped, not instance-scoped. One instance type in one AZ is one failure domain, regardless of how many replicas you run in it | Diversify across instance types and AZs; keep on-demand/reserved capacity ≥ your minimum viable fleet; treat "interruption frequency" as a per-pool hazard rate, not an independent per-instance probability |
| Cheaper instance class made the bill go up | Per-hour thinking. The smaller card has less VRAM (smaller batch) and less bandwidth (slower steps), and throughput is the product of the two | Always compute $/1M tokens, never $/hr. Re-derive with the sizing calculator before every instance-class change |

### What a mature deployment adds

- **A cost metric on the same dashboard as latency.** `sum(fleet_hourly_cost) / (rate(vllm:generation_tokens[1h]) * 3600) * 1e6` is dollars per million output tokens, live. Alert on it. Almost nobody has this, and it catches template regressions, context creep, and utilisation drops that no other single metric catches.
- **Two-tier capacity with an explicit overflow valve.** Reserved base sized to p50, spot or on-demand burst, and a managed API (Bedrock, or a hosted open-weight endpoint) as the last resort when the GPU fleet cannot scale in time. The overflow path costs 10-50x per token and that is fine, because it runs for minutes per month. The selection logic for that valve is in `T09-bedrock-vs-sagemaker`.
- **Load-shedding before queue-blowout.** An unbounded queue converts a capacity problem into a latency problem and then into a timeout storm. Cap admission (`max_num_seqs` plus a front-door concurrency limit), return 429 with `Retry-After`, and let the caller's backoff do the smoothing. A 429 at 50 ms is a better product outcome than a 200 at 90 seconds.
- **Batch/offline separation.** Evaluation runs, embedding backfills, and nightly re-scoring have no latency SLO and belong on spot with a completely different scaling policy. Mixing them onto the interactive fleet is the fastest way to blow a TTFT SLO, and separating them is usually the largest single cost win available in the first month.
- **Right-sizing reviewed on a schedule.** GPU pricing, instance availability, and engine throughput all move quarterly. A capacity decision made 12 months ago against vLLM v0.6 and A10G pricing is very likely wrong now, in both directions.

---

## Tradeoffs & when NOT to use it

**Do not self-host at all below roughly 40% sustained GPU utilisation.** Everything in this module is arithmetic for converting GPU-hours into tokens, and it stops paying at low duty cycle. At 20% utilisation an H100 costs $1.52/1M output tokens, which is worse than most hosted open-weight APIs and carries an on-call rotation. Do the division before you do the migration. The framing for that decision lives in `T09-bedrock-vs-sagemaker`; this module supplies the numerator.

**Do not put interactive inference on spot without a reserved floor.** The failure mode is not "some requests are slow", it is "the pool disappeared and we have zero capacity for four minutes". If you cannot state your minimum viable replica count and show that it is running on non-interruptible capacity, spot is a liability. And on `g5.2xlarge`, `p4d.24xlarge` and `p5.48xlarge` in us-east-1 today, a 3-year reserved rate is *lower* than the spot rate, so for capacity you are confident about, spot is strictly worse on both price and risk.

**Do not commit to reserved capacity before you have a measured utilisation history.** The breakeven is 63% of hours for a 1-year `g5` commit and 43% for 3 years. A team that has been live for six weeks does not know its annual duty cycle, and a 3-year commit against a workload that gets deprecated in month eight is a pure loss. Savings Plans (compute-flexible) are the hedge: slightly worse rate, no instance-type lock.

**Do not chase 90% utilisation on a latency-SLO workload.** The headroom equation is not negotiable. If your traffic can double in five minutes and your replicas take four minutes, running at 85% means you will shed load during every ramp. Either accept 50-60% and stop apologising for it, or attack the cold start until the headroom requirement shrinks. Anyone quoting 90% either has flat traffic, a warm pool they are not counting, or an SLO they are quietly missing.

**Do not quantise to INT4 for an agentic or structured-output workload without a task eval.** The published evidence for W4A16 competitiveness is on academic benchmarks. Multi-turn tool-calling compounds small degradations across turns, and the failure is a malformed JSON argument on turn seven, not a lower MMLU score. FP8 is the default you should reach for; INT4 needs evidence.

**Do not autoscale a GPU fleet on GPU utilisation, CPU, or request rate.** GPU utilisation cannot distinguish a healthy saturated engine from an idle one. CPU tells you about your tokenizer. Request rate ignores the 100x variance in decode length that actually determines load. Queue depth and TTFT are the only signals that mean what you think they mean.

**Do not optimise the instance class first.** It is the weakest of the three terms. Before you compare GPUs, check that prefix caching is on and hitting, that chunked prefill is on, that `vllm:num_preemptions` is zero, that context length has not crept, and that your fleet is not 40% idle. Those five checks routinely find 2-5x. An instance-class change finds 1.5x and costs you a migration.

**Do not use this module's numbers as constants.** Every dollar figure here is a us-east-1 rate on 2026-08-05, every throughput figure is a roofline derivation for one model on one GPU, and both move. What transfers is the *method*: read `config.json`, compute KV per token, subtract from the VRAM budget, divide bandwidth by weight bytes, multiply by batch, divide the hourly rate. Re-derive rather than recall.

**The genuine counter-argument to the whole module.** Everything here optimises unit cost, and at small scale unit cost is not the binding constraint. If your total GPU spend is $8,000/month, a heroic 2x optimisation saves $4,000/month, which is under one engineer-week per month at loaded cost. Doing this work at that scale is a negative-return activity, and the senior answer to "how would you cut our GPU bill" when the bill is small is "I wouldn't, yet; here is the spend level at which I would". Below roughly $30-50k/month of GPU spend, the highest-leverage cost lever is usually deleting a workload or shortening a prompt, not tuning a scheduler.

---

## Interview questions

### Q1 — How much GPU memory does it take to serve Llama 3.1 8B?
**Testing:** whether you answer "16 GB" (wrong, and the most common answer) or decompose the budget.
**Answer:** Weights are 8.03B × 2 bytes = 14.96 GiB in BF16, and that is the *fixed* term. The variable term is KV cache: 2 × 32 layers × 8 KV heads × 128 head_dim × 2 bytes = 131,072 bytes = 128 KiB per token, per sequence. So the real answer is a function: 15 GiB plus 128 KiB times total live context tokens, plus 2-4 GiB of activation workspace that scales with `max_num_batched_tokens` and CUDA-graph capture. On an 80 GB H100 with vLLM's default `gpu_memory_utilization=0.92`, that leaves about 55 GiB of KV pool, which is 452,000 tokens, which is 55 concurrent sequences at 8k context or 221 at 2k.
**Follow-up trap:** *"It fits on a 24 GB A10G then, right?"* — it fits and it is nearly useless. 20.7 GiB usable minus 15.0 weights minus ~1.5 activations leaves a 4.2 GiB pool, about 34,700 tokens, which is **8 concurrent sequences at 4k context**. Throughput is `steps/sec × batch`, and the A10G loses on both: 26.8 ms per decode step at 600 GB/s, and a batch capped at 8. That is ~300 tok/s versus ~11,200 on an H100. The card fits the model and cannot serve it.

### Q2 — Compute the cost per million tokens for that deployment, both cards.
**Testing:** whether you can carry the arithmetic through to a business number.
**Answer:** `p5.48xlarge` is $98.32/hr for 8× H100, so $12.29 per H100-hour. At 11,200 output tok/s that is 40.32M tokens/hour, so $12.29 / 40.32 = **$0.305 per 1M output tokens**. `g5.2xlarge` is $1.212/hr for one A10G at ~300 tok/s = 1.08M tokens/hour, so **$1.12 per 1M**. The $12.29/hr GPU is 3.7x cheaper per token than the $1.21/hr one. Per-hour intuition is inverted from per-token reality on bandwidth-bound decode.
**Follow-up trap:** *"So we should move everything to H100s."* — only if you can fill the batch. The H100 number assumes concurrency 256. At concurrency 8 the H100 does 209 × 8 ≈ 1,670 tok/s, which is $2.04/1M, now *worse* than the A10G. The big card is cheaper only at high utilisation, so the real prerequisite is enough steady traffic to saturate it, and if you do not have that, consolidating several models or tenants onto one large card via LoRA is the move, not buying more small cards.

### Q3 — Where does the 11,200 tokens/sec number come from? Derive it.
**Testing:** whether you understand decode as a bandwidth problem rather than a benchmark you memorised.
**Answer:** Decode reads all weights once per step plus the entire live KV cache. Weights are 1.606e10 bytes. At batch 256 with ~1,800 tokens of average live context, the KV read is 256 × 1800 × 131,072 = 6.04e10 bytes. Total 7.65e10 bytes per step. H100 SXM HBM3 is 3.35 TB/s, so the step takes 22.8 ms, and 256 tokens / 0.0228 s = 11,200 tok/s. The weight term alone would give a 4.79 ms floor and 209 steps/sec, so at this batch and context the KV cache is doing 79% of the bandwidth work.
**Follow-up trap:** *"What happens at 32k context instead of 1.8k?"* — two things compound. The KV pool only holds 13 sequences at 32k instead of 55 at 8k, so batch collapses; and each step reads 13 × 32768 × 131072 = 5.6e10 bytes of KV plus weights, so step time is ~22 ms for 13 tokens, roughly 590 tok/s. Long context costs you **~19x aggregate throughput**, which is why context length belongs on your capacity dashboard next to RPS.

### Q4 — Your GPUs are at 95% utilisation according to `nvidia-smi`. Should you scale out?
**Testing:** whether you know what the metric measures.
**Answer:** You cannot tell from that metric, and it is the wrong one. `nvidia-smi` utilisation is the fraction of time at least one kernel was resident, not the fraction of peak FLOPs or bandwidth. During decode the SMs are stalled on memory the whole time, so a batch of 1 and a batch of 256 both read ~100%. Scale on `vllm:num_requests_waiting` relative to `vllm:num_requests_running`, with `vllm:time_to_first_token_seconds` p95 as the SLO-facing trigger, and `vllm:kv_cache_usage_perc` as the early warning. A replica at 95% GPU with an empty queue is healthy; one at 45% GPU with 200 waiting is saturated on KV pool and must scale.
**Follow-up trap:** *"Then just scale on `kv_cache_usage_perc`."* — it is a leading indicator, not a trigger. It saturates near 1.0 and stays there while the engine happily preempts and recomputes, so by the time it is your alarm you are already in a throughput collapse. Use it to alert (`> 0.85` sustained) and watch `vllm:num_preemptions`, which should be exactly zero; scale on the queue.

### Q5 — Design the autoscaling policy for a vLLM fleet with an 800 ms p95 TTFT SLO.
**Testing:** whether you account for lag, and whether you derive thresholds from the SLO.
**Answer:** Scale out when 1-minute-averaged `vllm:num_requests_waiting / vllm:num_requests_running` exceeds ~0.10, which by Little's Law adds roughly 10% of request latency as queueing; against an 800 ms TTFT budget of which prefill already spends 80-150 ms, that keeps queueing under ~300 ms. Scale down only when the queue is empty and `kv_cache_usage_perc` is low for a full 300-second stabilization window. Asymmetric windows: 0 s up, 300+ s down. But the policy is secondary to the headroom, because scale-out latency is 3-8 minutes end to end: 15-30 s scrape, 30 s KEDA poll, 15 s HPA sync, 60-180 s node provisioning, 60-200 s image pull, 20-140 s weight fetch, 20-90 s engine init and CUDA-graph capture. If traffic can double in five minutes, you need 100% headroom, so steady-state utilisation is capped near 50%.
**Follow-up trap:** *"Finance says 50% utilisation is unacceptable. Fix it."* — you do not fix it with the autoscaler, you fix it by shrinking `L`. Pre-pull the image with a DaemonSet, stage weights on node-local NVMe, bake the `torch.compile` cache into the image, and keep a small warm node pool. Taking the cold start from 300 s to 90 s takes required headroom from 100% to 30% and the utilisation ceiling from 50% to ~77%, which is a 1.5x cost reduction with no hardware change. If that is still not enough, the remaining option is an explicit overflow to a managed API during ramps, which trades a 10-50x per-token rate for minutes per month.

### Q6 — Would you run production LLM inference on spot instances?
**Testing:** whether "spot is cheaper" survives contact with the numbers.
**Answer:** Only above a non-interruptible floor, and on some SKUs not at all. The arithmetic first: on `p5.48xlarge` in us-east-1, on-demand is $98.32/hr, spot is $57.76, and a 3-year standard reserved is $43.16. Spot is 34% *more expensive* than reserved with strictly more risk. The same holds on `g5.2xlarge` ($0.5954 spot vs $0.5236 3-year RI) and `p4d.24xlarge` ($13.07 vs $12.50). So for capacity you are confident you will use, reserve it; use spot only above that line, for burst and for batch work. Second, the notice windows differ and they determine whether draining is even possible: AWS gives 2 minutes, GCP and Azure give 30 seconds, and Azure documents that immediate eviction with no notice is possible.
**Follow-up trap:** *"Interruption frequency on p5 is under 5%. That's a rounding error."* — the rate is not the risk, the correlation is. Spot interruptions are pool-scoped: when capacity in one instance type in one AZ is reclaimed, every replica you have there goes at once. A ten-replica fleet in one pool can go to zero in 120 seconds regardless of a "5%" number, because that 5% is a per-pool hazard rate, not ten independent coin flips. The mitigations are instance-type and AZ diversification plus a reserved floor at minimum viable capacity, and on scarce GPU SKUs diversification is frequently not available, which is itself the answer.

### Q7 — When does a 3-year reserved instance make sense, and how do you know?
**Testing:** whether you can derive a breakeven rather than repeat a discount percentage.
**Answer:** Breakeven utilisation is `reserved_rate / on_demand_rate`. For `g5.2xlarge`, 1-year standard is $0.7636 against $1.212 on-demand, so **63.0%** of the hours in the year (about 5,520 of 8,760). The 3-year at $0.5236 breaks even at **43.2%**. For `p5.48xlarge`, 3-year at $43.157 against $98.32 is **43.9%**. So the question is not "do we want a discount", it is "will this instance run more than 43% of the next three years", and if you have been live for six weeks you do not know that.
**Follow-up trap:** *"We're at 70% utilisation, so commit for three years?"* — 70% today over six weeks is not 43% averaged over 156 weeks. The risks are workload deprecation, model replacement (a better open-weight model with different VRAM needs), and instance-type obsolescence, all of which are live on a 3-year horizon in this field. Compute-flexible Savings Plans are the hedge: a slightly worse rate for no instance-family lock. And note that a standard RI is instance-type-locked, so committing three years to `p4d` in 2023 meant paying for A100s while H100s got 45% cheaper.

### Q8 — Your GPU bill doubled month over month. Request volume is flat. Diagnose.
**Testing:** whether you know which term in the cost identity actually moved.
**Answer:** Request count is not the cost driver; output tokens and context length are. Check in this order. (1) **Average context length** — longer RAG chunks or more retained chat history is a linear multiplier on KV per sequence and therefore an inverse multiplier on batch size, so cost per token rises with no other change. (2) **Output token distribution** — a prompt change or an extended-thinking/reasoning mode being switched on multiplies decode load by up to 10x with zero change in request rate, and hidden reasoning tokens never show up in the visible response. (3) **Prefix cache hit rate** — if a template change moved a timestamp or user id to the front of the prompt, `vllm:prefix_cache_hits / _queries` collapses and every request pays full prefill again. (4) **Utilisation** — did scale-down stop working, or did a `PodDisruptionBudget` pin nodes Karpenter wanted to consolidate?
**Follow-up trap:** *"How would you have caught this before the invoice?"* — a live dollars-per-million-tokens metric: `fleet_hourly_cost / (rate(vllm:generation_tokens[1h]) * 3600) * 1e6`, alerted on. Total spend is a lagging aggregate that tells you nothing about which term moved; unit cost isolates it immediately, and it is the one metric almost no team has.

### Q9 — Would you quantise, and to what?
**Testing:** whether you know the quality evidence and the deployment-mode nuance.
**Answer:** FP8 first, essentially always, on Hopper or Ada. The largest study available, over 500,000 evaluations across the whole Llama-3.1 family, reports FP8 W8A8 effectively lossless at all scales, well-tuned INT8 W8A8 at 1-3% degradation, and INT4 weight-only competitive with 8-bit. FP8 buys three things at once: half the weight footprint (more KV pool, bigger batch), half the weight bytes read per decode step (2.4 ms instead of 4.79 ms on an H100), and with `--kv-cache-dtype fp8` half the KV per token, which doubles concurrency at fixed context. The deployment nuance from that same paper matters: **W4A16 is most cost-efficient for synchronous, low-concurrency setups, while W8A8 dominates in asynchronous continuous batching**, because W4A16 dequantises to 16-bit for the matmul, so it saves bandwidth but not compute and stops paying once you are compute-bound at high batch.
**Follow-up trap:** *"The paper says INT4 is fine, so use INT4 and save more."* — benchmark-lossless is not workload-lossless. Academic benchmarks are single-turn and forgiving; agentic multi-turn tool calling compounds small degradations, and the failure shows up as a malformed JSON argument on turn seven, not as a lower MMLU. There is published work specifically asking whether quantisation damages long-context tasks. Ship FP8 by default; ship INT4 only with a task-specific eval on your own traffic, and re-run it when the model changes.

### Q10 — A deploy causes a multi-minute latency spike across the whole fleet, then it recovers. What happened?
**Testing:** cold-start stampede, and whether readiness means what you think.
**Answer:** Two things happening together. First, every new replica pulls the same 8-15 GB CUDA image and the same 16-140 GB of weights simultaneously, saturating registry egress, S3 egress, and node NICs, so the pull that takes 60 s for one replica takes several minutes for twenty. Second, and worse, the readiness probe passed before the engine was actually ready: a TCP or `/health` check succeeds once the HTTP server binds, but `torch.compile` and CUDA-graph capture can still have 20-90 seconds to run, so the load balancer sends real traffic to replicas that are still compiling.
**Follow-up trap:** *"You pre-pulled the image and it still spikes."* — then it is the second cause, not the first. Make readiness issue an actual 1-token generation against the loaded model, not a socket check, so the pod does not enter the Endpoints list until the engine can serve. Then add `maxSurge: 1` so replicas warm serially, stage weights on node-local NVMe, and persist the `torch.compile` cache into the image with `VLLM_FORCE_AOT_LOAD=1` so a silent recompile becomes a loud failure instead of a latency mystery.

### Q11 — `vllm:num_preemptions` is climbing and throughput has halved. Walk me through it.
**Testing:** whether you recognise the KV-pool-exhaustion signature and know the four levers.
**Answer:** The KV pool cannot hold the running set, so the scheduler evicts sequences and re-runs their prefill later. In V1 the default preemption mode is RECOMPUTE rather than SWAP, because recomputation is cheaper than PCIe round-trips in the V1 architecture, and the log line names it explicitly: `Sequence group N is preempted by PreemptionMode.RECOMPUTE mode because there is not enough KV cache space`. The observable signature is bimodal latency (preempted requests pay prefill twice) with throughput below what the same fleet did at lower load, which is the tell that you are past the knee rather than merely busy. Four levers, in the order I would try them: raise `gpu_memory_utilization` toward but not past ~0.95; set `--kv-cache-dtype fp8` to halve KV per token; lower `max_num_seqs` or `max_num_batched_tokens` so admission stops overcommitting the pool; raise `tensor_parallel_size` so weights are sharded and each GPU has more room for KV.
**Follow-up trap:** *"Just raise `gpu_memory_utilization` to 0.98 then."* — you trade a mid-traffic preemption for a startup or mid-traffic OOM. That headroom is not slack, it is holding the activation workspace, CUDA graph pools, and allocator fragmentation, and the profiling pass that sized your KV pool did not account for a co-tenant process or a driver-version change. The right lever at 0.92 is usually FP8 KV or a lower `max_num_seqs`, not squeezing the last 6%.

### Q12 — Size the fleet: 500,000 requests/day, 1,200 input tokens, 400 output tokens, p95 TTFT 900 ms, 3:1 peak-to-average.
**Testing:** end-to-end capacity arithmetic under time pressure.
**Answer:** Average rate is 500,000/86,400 = 5.8 rps; peak is 17.4 rps. Decode load at peak: 17.4 × 400 = **6,960 output tok/s**. Prefill load: 17.4 × 1,200 = 20,880 prompt tok/s, against a derived H100 prefill capacity of ~24,900 tok/s at 40% MFU, so prefill alone would nearly saturate one H100 and the two phases contend. Decode alone needs 6,960 / 11,200 = 0.62 of an H100. Adding prefill, one H100 is right at the edge, so call it 2 H100s at peak for the work itself. Now headroom: at a 4-minute cold start against traffic that can move on a five-minute scale, hold ~100%, so **4 H100s**, i.e. half a `p5.48xlarge`, and since you cannot buy half, one `p5.48xlarge` with the spare capacity given to batch work. Cost check: 6,960 tok/s sustained at peak, average 2,320 tok/s → 200M output tokens/day → at $0.305/1M that is **$61/day of *useful* work** against a $2,360/day on-demand `p5` bill. That gap is the entire story: the workload is far too small for a `p5` and belongs on 2-3 L40S (`g6e.2xlarge`) or on a hosted API.
**Follow-up trap:** *"Leadership already bought the p5. Make it work."* — fill it. Consolidate other models onto it (one base model plus LoRA adapters rather than separate cards), move batch and eval workloads onto the idle capacity with a lower scheduling priority, and use the spare GPUs as the warm pool that lets the interactive slice run hotter. If none of that applies, the honest recommendation is to say the utilisation will be ~10% and quantify the waste in dollars per month rather than quietly absorbing it.

### Q13 — Staff level: your fleet is 40 GPUs, spend is $180k/month, leadership wants 40% off in a quarter. Where do you start and in what order?
**Testing:** prioritisation by expected value, not by what is technically interesting.
**Answer:** In descending order of (savings × confidence) / effort. **(1) Measure unit cost per workload first** — dollars per 1M tokens by model and by endpoint. This takes a week and it is the only way to know whether you have a utilisation problem or a workload problem; teams routinely find that one experimental endpoint holds 8 GPUs at 3% utilisation. **(2) Kill or consolidate the low-utilisation tail** — typically 15-30% of spend, near-zero risk, no engineering. **(3) Separate batch from interactive** and move batch to spot with its own scaling policy, often 10-15%. **(4) FP8 weights plus FP8 KV cache** on anything not already quantised, which raises batch and steps/sec together, typically 1.5-2x throughput for a week of eval work. **(5) Purchase mode** — reserve the p50 baseline once you have a utilisation history; 43-57% off the reserved portion. **(6) Cold-start reduction**, which converts directly into a higher utilisation ceiling. Instance-class changes and exotic scheduling come last, because they cost migrations and pay less.
**Follow-up trap:** *"Which of those could backfire, and how would you know before it does?"* — quantisation and utilisation-raising both can. Quantisation degrades quality silently, so it needs a task-level eval gate and a canary comparing refusal rate, structured-output validity, and task success against the BF16 baseline before full rollout. Raising utilisation eats the headroom that protects your TTFT SLO, so it must be gated on p95 TTFT and shed rate, not just on the cost graph. State the rollback trigger for each before you start; the staff-level failure is delivering 40% and a quiet SLO regression.

### Q14 — Someone proposes autoscaling to zero for the GPU fleet overnight. Respond.
**Testing:** whether you price all the links in the chain rather than the idea.
**Answer:** Compute the saving and the cost separately. Saving: 8 hours × 730/24 days ≈ 243 idle hours/month per node, at $12.29/GPU-hr that is real money on a large fleet. Cost: every scale-from-zero pays the full cold path, and for a 70B at 131.5 GiB of weights over a cold node with a cold image that is 8-15 minutes during which requests either fail or hang, depending on your control plane's contract with the caller (Knative's activator buffers; SageMaker's scale-from-zero fires on a CloudWatch alarm counting requests that already failed, which is covered in `T09-serving`). So scale-to-zero is correct for internal, dev, and batch endpoints, and wrong for anything with a user-facing SLO unless you have proven the traffic gap distribution actually has 8-hour holes.
**Follow-up trap:** *"We enabled it and the bill didn't change."* — the idle timeout is longer than the inter-arrival gap, so the fleet never actually reaches zero. Plot the inter-arrival-gap distribution: if p50 gap is 4 minutes and your cooldown is 300 s, you scale to zero approximately never and have bought the complexity for nothing. Either set the timeout below the gap you actually see, or accept that the right answer is a smaller always-on floor rather than zero.

### Q15 — Your queue is backing up but `kv_cache_usage_perc` is 0.25 and GPU SM utilisation is 20%. What is wrong?
**Testing:** the non-GPU bottleneck, which most candidates never consider.
**Answer:** The GPU is starved by the front end. Look for one CPU core pinned at 100% while the rest idle: that is HTTP parsing, tokenization, or detokenization on a single process. vLLM V1 already runs the API server and the engine core in separate processes, but a single API server process is still a bottleneck at high request rates and especially at large data-parallel sizes; the fix is `--api-server-count=N`. Also verify the fast Rust tokenizer is actually loaded rather than the slow Python fallback (a `use_fast=False` or a tokenizer without a `tokenizer.json` silently costs an order of magnitude), and that nothing constructs a tokenizer per request. Request logging that does per-token string work is another common culprit.
**Follow-up trap:** *"Would adding GPUs help?"* — no, it makes the ratio worse and doubles the bill for zero throughput. This is the general lesson: `num_requests_waiting > 0` is necessary but not sufficient evidence for scaling out. Always pair it with a saturation signal (`kv_cache_usage_perc` or running-sequence count); a queue with an *idle* engine is a front-end or admission problem, and scaling GPUs on it is how fleets end up at 20% utilisation with a growing bill.

---

## Red flags that fail you

- Saying a model's memory requirement is "params × bytes" with no KV cache term.
- Using `num_attention_heads` instead of `num_key_value_heads` in the KV formula, which overstates GQA models by 4-8x.
- Quoting one "tokens/sec" for a model without separating prefill from decode.
- Comparing GPUs on dollars per hour rather than dollars per million tokens.
- Proposing autoscaling on GPU utilisation, CPU, or request rate for an LLM endpoint.
- Claiming spot saves ~70% without checking it against the reserved rate for the same SKU, where it is currently *more* expensive on several GPU families.
- Treating spot interruption frequency as an independent per-instance probability rather than a pool-scoped correlated event.
- Planning capacity from mean output length when the distribution is heavy-tailed, or from request rate when reasoning tokens are in play.
- Asserting a utilisation target of 85-90% for a latency-SLO workload with no mention of cold-start latency or headroom.
- "We quantised to INT4 and benchmarks were fine" with no task-level eval on the actual workload.
- Reciting cloud pricing from memory with no acknowledgment that it moves quarterly, or mixing GiB and GB in the same calculation.
- Optimising instance class before checking prefix cache hit rate, preemption count, and fleet utilisation.

## Cheat card

```
VRAM BUDGET (vLLM)   usable = vram × gpu_memory_utilization (default 0.92)
                     KV pool = usable − weights − profiled activations (2-4 GiB)
  weights            params × bytes/param   8B bf16 = 14.96 GiB · 70B = 131.5 GiB
  KV per token       2 × n_layers × n_KV_heads × head_dim × dtype_bytes
                     Llama 8B  = 128 KiB/tok   ·  Llama 70B = 320 KiB/tok
                     fp8 KV halves it. USE n_key_value_heads, NOT n_attention_heads
  block_size         16 tokens (default) → internal frag ≤ 15 tok/seq, was 60-80%
  H100 80GB @ 8B     pool 55.2 GiB = 452k tok = 55 seqs @8k ctx, 221 @2k
  A10G 24GB @ 8B     pool 4.2 GiB = 34.7k tok = 8 seqs @4k ctx  ← fits ≠ serves

THROUGHPUT           decode = BANDWIDTH bound · prefill = COMPUTE bound
  decode step ≥ (weight_bytes + B×ctx×kv_per_tok) / HBM_bandwidth
  H100 3.35 TB/s → 4.79 ms weight floor → 209 steps/s → 11.2k tok/s @ B=256
  A10G 600 GB/s → 26.8 ms → 37 steps/s → ~300 tok/s @ B=8
  prefill tok/s ≈ TFLOPS × MFU(0.35-0.5) / (2 × params); H100 8B ≈ 24.9k tok/s

COST                 $/1M tok = ($/hr ÷ (tok/s × 3600 / 1e6)) ÷ utilisation
  p5.48xl 8×H100  OD $98.32/hr = $12.29/GPU-hr → $0.305/1M @ 100% util
                  spot $57.76 → $0.179 · 3yr RI $43.16 → $0.134
  g6e.2xl 1×L40S  $2.242/hr → ~$0.445/1M   g5.2xl 1×A10G $1.212 → ~$1.12/1M
  → the $12/hr GPU is 3.7x CHEAPER PER TOKEN than the $1.21/hr one

PURCHASE MODE        breakeven util = reserved_rate / on_demand_rate
  g5.2xlarge  1yr $0.7636/$1.212 = 63.0% · 3yr $0.5236 = 43.2%
  p5.48xlarge 3yr $43.157/$98.32 = 43.9%
  SURPRISE: 3yr RI < SPOT on g5.2xl, p4d.24xl, p5.48xl (us-east-1, 2026-08-05)
  → reserve the confident baseline; spot only ABOVE it

SPOT NOTICE          AWS 2 min (+ rebalance rec 10-20 min, not guaranteed)
                     GCP Spot/Preemptible 30 s (Preemptible also capped at 24 h)
                     Azure 30 s min via Scheduled Events; immediate eviction possible
  risk is CORRELATION not rate: one instance type × one AZ = one failure domain

AUTOSCALE SIGNAL     vllm:num_requests_waiting  ← scale on this
                     vllm:time_to_first_token_seconds p95 ← SLO trigger
                     vllm:kv_cache_usage_perc (renamed from gpu_cache_usage_perc)
                     vllm:num_preemptions ← must be ZERO; rising = sizing bug
  NEVER: GPU util (100% at B=1 and B=256 alike), CPU, or request rate

LAG & HEADROOM       cold GPU replica = 3-8 min (scrape 15-30s + KEDA 30s + HPA 15s
                     + node 60-180s + image 60-200s + weights 20-140s + init 20-90s)
  headroom ≥ growth_rate × scale_out_latency
  2x in 5 min with 5 min cold start ⇒ 100% headroom ⇒ util ceiling 50%
  → cut cold start, not autoscaler config. 300s→90s lifts ceiling 50%→77%

VLLM DEFAULTS (V1)   gpu_memory_utilization 0.92 · block_size 16
  max_num_batched_tokens / max_num_seqs: 8192 / 1024 (OpenAI server, ≥70 GiB
    non-A100 device); 2048 / 256 otherwise. LLM class: 16384 / 1024 and 8192 / 256
  chunked prefill ON by default · prefix caching ON by default
  preemption mode RECOMPUTE (not SWAP) · smaller max_num_batched_tokens → better
    ITL; larger → better TTFT; docs suggest >8192 for throughput

QUANTISATION         FP8 W8A8 effectively lossless (Llama-3.1 family, 500k evals)
  INT8 W8A8 1-3% degradation · INT4 W4A16 rivals 8-bit on benchmarks
  W4A16 wins SYNCHRONOUS/low-concurrency · W8A8 wins CONTINUOUS BATCHING
  FP8 needs Hopper/Ada. Always task-eval INT4 before shipping agentic workloads

WHEN NOT TO          <40% sustained utilisation → don't self-host
                     spot with no reserved floor → don't
                     <$30-50k/mo GPU spend → optimise the workload, not the fleet
```

## Sources

- [vLLM Optimization and Tuning (docs/configuration/optimization.md, main)](https://github.com/vllm-project/vllm/blob/main/docs/configuration/optimization.md) — accessed 2026-08-05
- [vLLM `CacheConfig` source: `gpu_memory_utilization=0.92`, `DEFAULT_BLOCK_SIZE=16`](https://github.com/vllm-project/vllm/blob/main/vllm/config/cache.py) — accessed 2026-08-05
- [vLLM `SchedulerConfig` and `EngineArgs.get_batch_defaults`: usage-context and device-dependent token/sequence budgets](https://github.com/vllm-project/vllm/blob/main/vllm/engine/arg_utils.py) — accessed 2026-08-05
- [vLLM V1 Prometheus metric names (`vllm/v1/metrics/loggers.py`)](https://github.com/vllm-project/vllm/blob/main/vllm/v1/metrics/loggers.py) — accessed 2026-08-05
- [vLLM Production Metrics](https://github.com/vllm-project/vllm/blob/main/docs/usage/metrics.md) — accessed 2026-08-05
- [vLLM data-parallel deployment: `--api-server-count`](https://github.com/vllm-project/vllm/blob/main/docs/serving/data_parallel_deployment.md) — accessed 2026-08-05
- [Kwon et al., *Efficient Memory Management for Large Language Model Serving with PagedAttention*, SOSP 2023 (arXiv:2309.06180)](https://arxiv.org/abs/2309.06180) — accessed 2026-08-05
- [Kurtic et al., *"Give Me BF16 or Give Me Death"? Accuracy-Performance Trade-Offs in LLM Quantization*, ACL 2025 (arXiv:2411.02355v4)](https://arxiv.org/abs/2411.02355) — accessed 2026-08-05
- [*Does quantization affect models' performance on long-context tasks?* (arXiv:2505.20276)](https://arxiv.org/abs/2505.20276) — accessed 2026-08-05
- [Agrawal et al., *Taming Throughput-Latency Tradeoff in LLM Inference with Sarathi-Serve* (arXiv:2403.02310); chunked prefill origin (arXiv:2308.16369)](https://arxiv.org/abs/2308.16369) — accessed 2026-08-05
- [ec2.shop pricing API — us-east-1 on-demand, spot, and reserved rates](https://ec2.shop) — accessed 2026-08-05
- [Amazon EC2 Spot Instance interruption notices (2-minute warning)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html) — accessed 2026-08-05
- [Amazon EC2 instance rebalance recommendations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/rebalance-recommendations.html) — accessed 2026-08-05
- [Google Cloud Spot VMs (Compute Engine) — 30-second best-effort shutdown](https://docs.cloud.google.com/compute/docs/instances/spot) — accessed 2026-08-05
- [GKE preemptible VMs — 24-hour maximum lifetime](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/preemptible-vms) — accessed 2026-08-05
- [About Azure Spot Virtual Machines — 30-second minimum notice via Scheduled Events](https://learn.microsoft.com/en-us/azure/virtual-machines/spot-vms) — accessed 2026-08-05
- [Build workloads with Azure Spot Virtual Machines (eviction design guidance)](https://learn.microsoft.com/en-us/azure/architecture/guide/spot/spot-eviction) — accessed 2026-08-05
- [Managed Spot Training in Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/model-managed-spot-training.html) — accessed 2026-08-05
- [Karpenter disruption and interruption handling](https://karpenter.sh/docs/concepts/disruption/) — accessed 2026-08-05
- [LLM inference engine throughput comparison (secondary source for the 11.2k tok/s H100 cross-check)](https://aimultiple.com/inference-engines) — accessed 2026-08-05
- [AWS EC2 Capacity Block price increase, July 2026 (secondary source, vendor blog)](https://www.spheron.network/blog/aws-capacity-blocks-pricing-2026-b200-b300-hike/) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
