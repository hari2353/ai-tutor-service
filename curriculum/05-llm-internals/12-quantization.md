# GPTQ/AWQ/GGUF/FP8/INT4 and Quality-vs-Cost Curves

> **Track:** T05 LLM Internals · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T05-quantization` · **Tags:** inference

## The 30-second version

Quantization shrinks a model's numeric representation — fp16's 2 bytes/parameter down to INT8's 1 byte or INT4/NF4's 0.5 bytes — to cut memory footprint and, more importantly, memory *bandwidth*, because decode is memory-bandwidth-bound, not compute-bound: generating one token at batch size 1 reads the entire weight matrix once for roughly one FLOP per byte read, landing over a hundred times below the compute/bandwidth ridge point on modern GPUs, so a smaller weight representation speeds up decode almost directly. Weight-only methods (GPTQ, AWQ, GGUF's k-quants, bitsandbytes NF4) quantize just the weights and dequantize on the fly, which is what memory-bound decode needs; weight-and-activation methods (SmoothQuant-style INT8) additionally quantize activations to unlock actual INT8 tensor-core throughput, which matters for compute-bound regimes like large-batch prefill, but activations carry systematic outlier channels 20-100x larger than the rest that naive INT8 clips and destroys — SmoothQuant's fix is an offline, mathematically equivalent rescaling that migrates the outlier difficulty from activations into weights before quantizing either. Quality degrades unevenly, not uniformly: general chat and summarization tolerate 4-bit weight-only quantization with well under a few points of loss, while math, code, long-context retrieval, and multilingual output degrade first and hardest, especially once you push past INT8 into INT4 or quantize the KV cache aggressively. The practical rule: quantize weights to 4-bit by default with a properly calibrated method (AWQ or a GGUF k-quant), keep KV cache at INT8 or FP8 rather than INT4 unless you've measured the task-specific hit, and never skip validating quantized quality on the *hardest* task category you actually serve, not just an aggregate perplexity number.

## Why this gets asked

The interviewer has shipped a quantized model that looked fine on an internal chat eval and then watched code-generation accuracy or long-context retrieval quietly fall off a cliff in production, because nobody checked task-specific degradation before the aggregate perplexity number said "looks good." They want to know whether you understand quantization as a bandwidth optimization first and a memory optimization second — the two goals point at different techniques — and whether you can explain *why* activations are harder to quantize than weights, which is the detail that separates someone who's read a blog post from someone who's actually debugged a broken INT8 deployment.

---

## Lineage: past → present → future

**What came before.** Early LLM deployment simply ran models at their native training precision (fp32, then fp16/bf16 once mixed-precision training became standard), which meant memory footprint scaled linearly with parameter count and nothing else — a 70B model needed roughly 140 GB just to hold weights in fp16, forcing multi-GPU serving even for inference-only workloads. Post-training quantization for vision/CNN models (INT8 with simple per-tensor calibration) worked well and was assumed to transfer directly to transformers; it didn't. Dettmers et al.'s LLM.int8() (2022) was the paper that diagnosed why: LLMs develop systematic activation outliers — specific feature dimensions that are consistently 20-100x larger than the rest, appearing across nearly all tokens once a model crosses roughly 6-7B parameters — and naive INT8 quantization, which sets its scale from the tensor's max value, either clips those outliers (destroying the information they carry) or wastes nearly all its precision budget accommodating them (crushing the resolution available to every normal-magnitude value). This was the pain that killed naive INT8-everywhere as a strategy and forced a split between weight-only and weight+activation quantization as genuinely different problems.

**Where it stands now.** Weight-only PTQ is the settled default for GPU-served open-weight models: GPTQ (Frantar et al., 2022) uses layer-wise, Hessian-informed error correction to quantize weights with minimal calibration data, and AWQ (Lin et al., 2023) instead identifies the small fraction of "salient" weight channels via activation magnitude and protects them with a per-channel scaling transform rather than mixed precision — AWQ has become the more common default for new production GPU deployments in 2026 because it typically holds quality better at 4-bit, particularly on instruction-tuned models [AWQ vs GGUF vs GPTQ — Index.dev](https://www.index.dev/skill-vs-skill/ai-gptq-vs-awq-vs-gguf) — accessed 2026-08-01. GGUF (llama.cpp's format) dominates CPU and edge/consumer-GPU serving with its k-quant family (Q2_K through Q8_0, mixing precision per block), and bitsandbytes' NF4 underlies QLoRA-style fine-tuning rather than pure-inference serving. For activation quantization, SmoothQuant (Xiao et al., 2022) remains the reference technique for enabling W8A8 (INT8 weights and activations) by migrating quantization difficulty from activations to weights via a mathematically equivalent offline rescaling. FP8 (E4M3/E5M2) is natively supported on Hopper-generation (H100) and newer GPUs and has become the practical default for the highest-value tradeoff point — roughly 50% memory savings with quality close enough to fp16 that most teams don't bother measuring the gap before shipping it. The live disagreement is over INT4 and aggressive KV-cache quantization: they're clearly worth it for memory-constrained general chat and summarization workloads, and clearly risky for math, code, and long-context reasoning workloads, and there is no single accepted threshold — teams are expected to measure per-task-category, not trust a vendor's aggregate benchmark.

**Where it's heading.** High confidence: FP8 keeps displacing INT8 as the "safe default beyond fp16" on any GPU generation that supports it natively, because it needs less calibration fuss than INT8 while delivering similar memory savings. Moderate confidence: KV-cache quantization research (variance-normalized and distribution-aware schemes specifically targeting the accumulation error that compounds over long reasoning chains) is actively improving the INT4-KV quality story for exactly the reasoning-heavy workloads where it currently degrades hardest — treat any single 2026 paper's specific numbers here as provisional, the field is moving quickly. Speculative: sub-4-bit weight quantization (2-3 bit) combined with error-correction schemes is being published with promising numbers on some benchmarks, but hasn't demonstrated the same task-uniform reliability 4-bit methods have earned over several years of production use — don't treat a benchmark table claiming near-lossless 2-bit quantization as validated for your workload without testing it yourself on your hardest task category.

---

## Mental model

```
                    COMPUTE-BOUND                    MEMORY-BOUND
                    (large batch, prefill)            (decode, batch=1-ish)

Arithmetic          high FLOPs per byte moved         ~1 FLOP per byte moved
intensity           (reuse weights across tokens)     (read full weight, do ~1 matmul)

What helps          more FLOPs/sec (bigger GPU,       fewer BYTES moved
                    better kernels, W8A8 for real      (weight-only quant: read a
                    INT8 tensor-core throughput)       smaller representation,
                                                        even if dequantized to fp16
                                                        just before the matmul)

Roofline:  throughput
              ^
   compute    |_______________________  <- compute ceiling (peak FLOPs/s)
   ceiling    |                    /
              |                  /
              |                /   <- memory ceiling (bandwidth x arithmetic intensity)
              |              /
              |            /
              |__________/________________> arithmetic intensity (FLOP/byte)
                    ^
              decode sits WAY out here (~1 FLOP/byte, ~100x+ below the ridge point)
              -> decode speed is bounded by how many BYTES you move, not FLOPs
```

This is the one fact that explains every quantization decision below: decode reads the entire weight matrix from HBM to produce roughly one FLOP of useful work per byte read, which is orders of magnitude below the ratio a GPU needs to be compute-bound. Shrinking the weight representation shrinks the bytes moved, which speeds up decode almost linearly — this is true even if you dequantize back to fp16 right before the matmul, because the bottleneck was never the matmul, it was the trip from HBM.

---

## How it actually works

### Precision costs, in bytes per parameter

| Format | Bytes/param | 7B model weights | 70B model weights |
|---|---|---|---|
| FP32 | 4 | 28 GB | 280 GB |
| FP16 / BF16 | 2 | 14 GB | 140 GB |
| FP8 (E4M3/E5M2) | 1 | 7 GB | 70 GB |
| INT8 | 1 | 7 GB | 70 GB |
| INT4 / NF4 | 0.5 | 3.5 GB | 35 GB |

Weights-only numbers; add KV cache and activation memory on top, which scale with sequence length and batch size independently (see `T05-attention` for the KV-cache-bytes-per-token derivation).

### Why memory bandwidth, not FLOPs, bounds decode

For autoregressive decode at batch size 1, each step reads the full weight set from HBM once and performs on the order of one FLOP of work per byte read — a 70B model in fp16 (140 GB of weights) doing roughly 140 GFLOPs of matmul work per token is an arithmetic intensity near 1 FLOP/byte, roughly 100-200x below the ridge point (the FLOPs/byte ratio at which a GPU's compute ceiling and memory-bandwidth ceiling cross) on H100-class hardware [Mind the Memory Gap — arXiv:2503.08311](https://arxiv.org/html/2503.08311v2) — accessed 2026-08-01. This means decode throughput tracks memory bandwidth almost directly: halve the bytes you need to move (fp16 → INT8), and decode gets roughly twice as fast, independent of how much faster the GPU's compute units could theoretically go — the compute units are sitting idle waiting for weights to arrive. Prefill is the opposite regime: it processes the whole prompt in one parallel pass, reuses the same weights across every token in the batch, and is compute-bound, which is why prefill benefits more from raw FLOPs (and from W8A8 activation quantization that actually engages INT8 tensor cores) while decode benefits more from just shrinking bytes moved.

### PTQ vs QAT

**Post-training quantization (PTQ)** quantizes an already-trained model, usually with a small calibration set (128-512 representative samples) used to compute per-channel or per-block scale factors — cheap (minutes to hours), no retraining, and the default for nearly all LLM serving because retraining a frontier-scale model just to quantize it is rarely worth the cost. **Quantization-aware training (QAT)** simulates quantization noise during training or fine-tuning so the model's weights adapt to tolerate it, recovering quality PTQ can't at very aggressive bit widths — worth it when you're already fine-tuning and targeting sub-4-bit, but adds real training cost and is not the default for "just ship a quantized version of an existing model."

### GPTQ, AWQ, GGUF, bitsandbytes: what each actually does

| Method | Mechanism | Scope | Where it's used |
|---|---|---|---|
| **GPTQ** (2022) | Layer-by-layer weight quantization using second-order (Hessian) error correction — quantize one weight, then adjust the remaining unquantized weights in that layer to compensate for the error just introduced | Weight-only | GPU serving; superseded by AWQ for most new deployments but still common on older exported checkpoints |
| **AWQ** (2023) | Identifies the small fraction of weight channels that matter most by looking at *activation* magnitude (not weight magnitude), then protects those salient channels with a per-channel scaling transform rather than mixed precision | Weight-only | Default for production GPU serving in 2026; typically better quality at 4-bit than GPTQ, especially on instruction-tuned models |
| **GGUF k-quants** | A file format (successor to GGML) with multiple quantization levels per tensor (Q2_K through Q8_0), where "k-quants" mix precision within a block — most values at the target bit width, a minority of "important" values (by heuristic) kept at higher precision | Weight-only | CPU inference, edge devices, consumer GPUs via llama.cpp; Q4_K_M is the common quality/size default |
| **bitsandbytes NF4** | 4-bit NormalFloat quantization with bins at standard-normal quantiles, plus double quantization of the block scale constants | Weight-only, typically paired with a trained LoRA adapter | QLoRA-style fine-tuning (see `T05-finetuning`) more than pure-inference serving |
| **FP8 (E4M3/E5M2)** | Native 8-bit floating-point format on Hopper+ GPUs — no separate scale/zero-point bookkeeping the way integer formats need | Weight and/or activation | Default "safe beyond fp16" choice on H100-class hardware; ~50% memory savings, quality close to fp16 |

**Measured degradation, HumanEval (code generation) at 4-bit**: AWQ and GGUF both land around 51.8% versus an fp16 baseline of 56.1% (roughly 4 points), while GPTQ trails at roughly 46% (roughly 10 points) on the same benchmark [GPTQ vs AWQ vs GGUF — TheAIEngineer](https://theaiengineer.substack.com/p/quantization-in-practice-gptq-vs) — accessed 2026-08-01. This is exactly the kind of task-specific degradation number a general perplexity metric hides — code degrades measurably more than the aggregate "looks fine" number would suggest, and the gap between quantization *methods* (not just bit widths) is itself several points.

### Outlier features: why naive INT8 fails specifically on activations

Weight distributions in a trained transformer are close to uniform and well-behaved — quantizing weights to INT8, or even INT4, causes little accuracy loss because there's nothing structurally unusual to accommodate. Activations are different: once models cross roughly 6-7B parameters, specific feature dimensions consistently produce values 20-100x larger than the rest, across nearly every token, concentrated in a small number of fixed channels [SmoothQuant — arXiv:2211.10438](https://arxiv.org/abs/2211.10438) — accessed 2026-08-01. A quantization scheme that sets its scale from the tensor's max value either clips those outlier channels (destroying the signal they carry — and empirically they carry a disproportionate share of a model's expressive information) or, if it avoids clipping, wastes nearly all its 8-bit resolution accommodating a handful of huge values, crushing the precision available to every normal-magnitude activation. Two fixes emerged:

- **LLM.int8() mixed-precision decomposition**: identify the small set of outlier feature dimensions per forward pass, compute those specific columns in fp16 and everything else in INT8, then recombine — correct, but the fp16 path adds overhead proportional to how many outlier dimensions show up.
- **SmoothQuant**: instead of handling outliers at runtime, migrate the *difficulty* offline. Since `Y = (X · s) · (W / s)` for any per-channel scale `s`, you can divide activation channel `i` by a per-channel smoothing factor and multiply the corresponding weight channel by the same factor — this is mathematically exact, not an approximation — chosen so the rescaled activations are smooth enough to quantize well in INT8 while the rescaled weights (which were easy to quantize to begin with) absorb the extra dynamic range and remain quantizable. This is what enables W8A8 (both weights and activations in INT8) across models including Llama, Mistral, and Falcon families with an offline calibration pass, no retraining.

### Weight-only vs weight-and-activation: different jobs

Weight-only quantization (GPTQ/AWQ/GGUF/NF4) shrinks the bytes read from HBM, which is exactly what memory-bound decode needs, and it's simpler to get right because weight distributions don't have the outlier problem. It does *not* by itself unlock INT8 tensor-core throughput, because the matmul still happens in a higher-precision format after dequantizing weights on the fly — the win is bandwidth, not raw compute. Weight-and-activation quantization (SmoothQuant-style W8A8) is necessary to actually engage INT8 (or FP8) tensor cores for the matmul itself, which matters in compute-bound regimes — large-batch serving, prefill on long prompts — where bandwidth was never the bottleneck and you need real throughput, not just a smaller memory footprint.

### The quality-vs-cost curve: which tasks degrade first

Degradation is not uniform across task types, and this is the single most commonly missed fact in production quantization decisions:

1. **General chat, summarization, simple QA** — most tolerant. 4-bit weight-only quantization typically costs well under a few points on standard chat benchmarks; this is why "4-bit is basically free" becomes the team's mental model, which is exactly the trap.
2. **Long-context retrieval** — moderately sensitive, especially once you also quantize the KV cache aggressively; FP8 KV cache typically costs under 0.5 percentage points on standard long-context retrieval benchmarks, but INT4 KV cache shows measurable loss especially as context length grows and errors compound across many decode steps.
3. **Multilingual, especially low-resource languages** — degrades earlier than English-centric general chat, because quantization error concentrates precision loss where the base model already has less capacity margin to spare.
4. **Math and code** — degrades first and hardest. These tasks require precise, compounding multi-step reasoning where a single quantization-induced error early in a chain propagates and invalidates the rest of the output, unlike open-ended chat where a locally-imprecise word choice rarely invalidates the whole response. Reported cases include quantization schemes causing dramatic HumanEval pass-rate drops on smaller models specifically, with smaller models generally shown to be more vulnerable to quantization-induced degradation than larger ones at the same bit width [Systematic Characterization of LLM Quantization — arXiv:2508.16712](https://arxiv.org/pdf/2508.16712) — accessed 2026-08-01.

The operational consequence: validate quantized quality on your hardest task category, not an aggregate benchmark, and if your product includes code generation or multi-step math, budget more conservatively (INT8 over INT4, FP8 KV over INT4 KV) than a general-chat-only product would need to.

### KV-cache quantization specifically

The KV cache is a separate memory pool from weights and quantizes independently. INT8 KV cache typically holds accuracy well across most task types, including code generation benchmarks like HumanEval and MBPP, where naive INT8/INT4 KV quantization shows almost no degradation on straightforward code-completion tasks. INT4 KV cache shows a small but real quality loss that grows with context length and with tasks requiring long reasoning chains, because per-step quantization error in K/V compounds across every subsequent attention computation that reads it — this is the "reasoning-heavy workloads degrade first" pattern showing up specifically in the cache rather than the weights. FP8 KV cache is close to free on retrieval-heavy long-context benchmarks (under 0.5 points typically) and is the safer aggressive default versus INT4 when you need the memory back.

### Calibration data matters more than expected

GPTQ and AWQ both compute their quantization parameters from a calibration set — typically 128-512 samples run through the model to observe realistic activation statistics. Calibrating on a generic corpus (e.g., a slice of C4 web text) when your actual deployment distribution is domain-specific (legal documents, code, a non-English language) means the salient-channel detection (AWQ) or Hessian statistics (GPTQ) reflect the wrong distribution — the quantized model can look fine on general benchmarks while degrading specifically on your domain, because the calibration pass never saw the activation patterns your real traffic produces. Calibrate on data that resembles production traffic, not a convenient public dataset, especially if your workload skews toward one of the fragile categories above (code, math, a specific non-English language).

---

## Build it from scratch

Minimal weight-only quantize/dequantize round trip (illustrates the block-scale mechanism GPTQ/AWQ/GGUF all build on):

```python
import numpy as np

def quantize_int4_blockwise(weights: np.ndarray, block_size: int = 64):
    """Per-block symmetric INT4 quantization. weights: 1D array."""
    n = weights.shape[0]
    n_blocks = (n + block_size - 1) // block_size
    quantized = np.zeros(n, dtype=np.int8)
    scales = np.zeros(n_blocks, dtype=np.float32)

    for b in range(n_blocks):
        start, end = b * block_size, min((b + 1) * block_size, n)
        block = weights[start:end]
        scale = np.max(np.abs(block)) / 7.0          # INT4 signed range: [-8, 7], use 7 for symmetry
        scales[b] = scale if scale > 0 else 1.0
        quantized[start:end] = np.clip(np.round(block / scales[b]), -8, 7).astype(np.int8)

    return quantized, scales

def dequantize_int4_blockwise(quantized: np.ndarray, scales: np.ndarray, block_size: int = 64):
    n = quantized.shape[0]
    out = np.zeros(n, dtype=np.float32)
    for b, scale in enumerate(scales):
        start, end = b * block_size, min((b + 1) * block_size, n)
        out[start:end] = quantized[start:end].astype(np.float32) * scale
    return out

# Round-trip error check
w = np.random.randn(1024).astype(np.float32)
q, s = quantize_int4_blockwise(w)
w_hat = dequantize_int4_blockwise(q, s)
print("mean abs error:", np.mean(np.abs(w - w_hat)))   # should be small relative to weight std
```

A sketch of the SmoothQuant rescaling (the mathematically-exact part, before quantizing either side):

```python
# untested sketch -- illustrates the offline rescaling, not a full quantization pipeline
def smoothquant_rescale(activations, weights, alpha=0.5):
    """
    activations: (n_tokens, d) observed over a calibration set
    weights: (d, d_out)
    alpha: migration strength, 0 = all difficulty stays on activations, 1 = all moves to weights
    """
    act_scale = np.abs(activations).max(axis=0)          # per-channel activation max, shape (d,)
    weight_scale = np.abs(weights).max(axis=1)            # per-channel weight max, shape (d,)
    s = (act_scale ** alpha) / (weight_scale ** (1 - alpha))
    s = np.clip(s, 1e-5, None)
    smoothed_activations = activations / s                 # divide activations by s
    smoothed_weights = weights * s[:, None]                 # multiply weights by s (mathematically exact: (X/s)(sW) = XW)
    return smoothed_activations, smoothed_weights
```

Full GPTQ-style Hessian error-correction loop and an AWQ salient-channel search: **`(lab pending)`** (create if not present — not yet in this repo).

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| GPU serving, weight-only | AWQ or GPTQ checkpoints loaded via vLLM/TensorRT-LLM/Hugging Face `transformers` | 4-bit weights, dequantized on the fly per matmul, targets memory-bound decode |
| GPU serving, W8A8 | SmoothQuant-quantized checkpoints, TensorRT-LLM INT8/FP8 kernels | Real INT8/FP8 tensor-core throughput, targets compute-bound prefill/large-batch |
| Edge / CPU / consumer GPU | GGUF via llama.cpp, `Q4_K_M` or `Q5_K_M` as the common quality/size default | Single-file format, runs without a Python/CUDA stack, mixed per-block precision |
| KV cache | vLLM/TensorRT-LLM FP8 or INT8 KV cache flags | Frees serving memory for more concurrent long-context sequences |
| Fine-tuning | bitsandbytes NF4 + LoRA adapters (QLoRA) | Trains on top of a quantized frozen base — see `T05-finetuning` |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Quantized model passes general chat eval but code/math accuracy craters in production | Aggregate perplexity or a general benchmark hid task-specific degradation; math/code degrade first under quantization | Validate on the hardest task category you actually serve, not an aggregate score; prefer INT8 or AWQ-4bit over GPTQ/naive INT4 for code-heavy workloads |
| Naive INT8-everywhere quantization produces garbage output or repeated tokens | Activation outlier channels got clipped by a max-based INT8 scale, or the scale was set so wide that normal-magnitude values lost all resolution | Use SmoothQuant-style rescaling or mixed-precision (LLM.int8()) for activations; don't naively apply weight-quantization intuition to activations |
| Long-running agentic/reasoning session degrades in quality the longer it runs | INT4 KV-cache quantization error compounds across many decode steps reading an increasingly-degraded cache | Use INT8 or FP8 KV cache for long, reasoning-heavy sessions; reserve INT4 KV for short-context or non-reasoning workloads |
| Quantized model looks fine on public benchmarks, degrades specifically on your domain traffic | Calibration set (for GPTQ/AWQ) didn't represent production distribution | Recalibrate on a sample of real production traffic, not a generic public corpus |
| Weight-only quantization gives disappointing throughput gains at large batch size | Weight-only quantization targets memory-bandwidth-bound decode; large-batch prefill is compute-bound and doesn't benefit the same way | Use W8A8 (SmoothQuant-style) or FP8 activations to actually engage faster tensor-core paths for the compute-bound regime |
| Smaller model (e.g., a distilled or already-small checkpoint) shows much worse quantization degradation than a larger model at the same bit width | Smaller models have less redundant capacity to absorb quantization error | Use a higher bit width or a gentler method (AWQ over GPTQ, INT8 over INT4) specifically for smaller models; don't assume degradation numbers from a 70B model transfer to a 7B one |

---

## Tradeoffs & when NOT to use it

- **Don't quantize the KV cache to INT4 for long, reasoning-heavy, or agentic workloads** without measuring on your own long-context/multi-step task — the compounding-error failure mode is real and the "it was fine on my quick test" trap is exactly how it ships broken.
- **Don't trust an aggregate perplexity or general-chat benchmark to clear a quantization decision for a code or math product.** Math and code are the tasks that degrade first and hardest; validate specifically on them.
- **Don't apply weight-only quantization when you need real compute-bound throughput gains** (large-batch serving, long-prompt prefill at scale) — you need weight-and-activation (W8A8/FP8) quantization to actually engage faster matmul paths; weight-only mainly buys you memory and decode-bandwidth relief.
- **Don't naively INT8-quantize activations without an outlier-handling strategy** (SmoothQuant-style rescaling or mixed precision) — this is the single most reliable way to produce a silently-broken deployment, since the failure often doesn't show up as an error, just degraded quality that's easy to attribute to something else.
- **Don't calibrate GPTQ/AWQ on a convenient generic dataset when your deployment is domain-specific.** The calibration set determines which channels get protected; mismatched calibration data is invisible until you specifically test the domain it was blind to.
- **Skip quantization entirely** when you have ample GPU memory headroom, your workload is latency-insensitive at the batch sizes you actually run, or you're doing research where reproducibility and comparability against a known fp16 baseline matter more than the memory savings — the engineering and validation cost of doing quantization *correctly* (calibration, task-specific eval, KV-cache-specific testing) is real, and "we had the VRAM anyway" is a legitimate reason not to pay it.
- **QAT is usually not worth it** unless you're already running a fine-tuning pipeline and specifically need sub-4-bit quality that PTQ methods can't deliver; for the common case of "quantize an existing checkpoint for serving," PTQ (AWQ/GPTQ/GGUF) is the right default and QAT's added training cost buys little.

---

## Interview questions

### Q1 — Why does quantization speed up LLM decode specifically, in terms of the actual bottleneck?
**Testing:** whether the candidate understands the mechanism, not just "smaller is faster."
**Answer:** Decode at low batch size is memory-bandwidth-bound: each step reads the full weight set from HBM and does roughly one FLOP of work per byte read, which is far below the arithmetic-intensity ridge point where a GPU's compute ceiling would actually matter. Shrinking the byte representation of weights (fp16 to INT8 or INT4) shrinks the bytes moved per step, so decode speeds up roughly in proportion, independent of the GPU's raw FLOPs headroom, which is sitting idle waiting on memory anyway.
**Follow-up trap:** *"So does quantization help prefill the same way?"* — no, prefill processes the whole prompt in parallel and reuses the same weights across many tokens in a batch, making it compute-bound; prefill benefits more from actually engaging faster INT8/FP8 tensor-core paths (weight-and-activation quantization), not just from smaller weight bytes.

### Q2 — Why are activations harder to quantize than weights in LLMs specifically?
**Answer:** Weight distributions are close to uniform and well-behaved, so quantizing them causes little accuracy loss. Activations develop systematic outlier channels, consistently 20-100x larger than the rest, in specific fixed feature dimensions across nearly every token, once models cross roughly 6-7B parameters. A max-based quantization scale either clips those outliers (losing disproportionately important signal) or wastes nearly all its precision budget accommodating them, crushing resolution for everything else.
**Follow-up trap:** *"If outliers are the problem, why not just clip them?"* — the outlier channels carry a disproportionate share of the model's expressive information; clipping them measurably degrades quality rather than just discarding noise, which is why SmoothQuant migrates the difficulty instead of discarding it.

### Q3 — Explain SmoothQuant's rescaling trick and why it's exact, not an approximation.
**Answer:** For any per-channel scale `s`, `(X/s) \cdot (sW) = XW` — dividing an activation channel by `s` and multiplying the corresponding weight channel by the same `s` leaves the matmul output unchanged. SmoothQuant picks `s` per channel (via a calibration pass) to smooth the activation distribution enough to quantize well in INT8, at the cost of giving weights (which were easy to quantize already) slightly more dynamic range to absorb. It's exact because it's an algebraic identity applied before quantization, not a lossy approximation of the function being computed.
**Follow-up trap:** *"Doesn't shifting difficulty onto weights just move the problem?"* — no, because weights don't have the same outlier structure activations do; weights can absorb a moderate amount of extra dynamic range without hitting the pathological outlier problem, which is exactly why the migration direction (activations → weights) works and the reverse wouldn't.

### Q4 — GPTQ versus AWQ: what's mechanically different, and which do you pick by default in 2026?
**Answer:** GPTQ uses layer-by-layer Hessian-informed error correction — quantize one weight, adjust the rest of that layer's unquantized weights to compensate for the introduced error. AWQ instead identifies salient weight channels by observing *activation* magnitude (not weight magnitude) and protects those channels with a per-channel scaling transform rather than mixed precision. AWQ is the more common 2026 default for GPU serving because it typically holds quality better at 4-bit, especially on instruction-tuned models; on HumanEval, AWQ/GGUF land around 51.8% versus GPTQ's roughly 46% against an fp16 baseline of 56.1%.
**Follow-up trap:** *"If AWQ is generally better, why does GPTQ still show up in production?"* — plenty of already-quantized checkpoints in the wild were exported as GPTQ before AWQ became the default, and re-quantizing isn't always worth the effort if the existing checkpoint already meets the bar for its use case — "better on average" doesn't mean "worth migrating every existing deployment."

### Q5 — What does GGUF actually add beyond being "another 4-bit format"?
**Answer:** GGUF is a self-contained file format (successor to GGML) built for llama.cpp, supporting multiple quantization levels per tensor (Q2_K through Q8_0), with "k-quants" mixing precision within a block — most values at the target bit width, a minority of heuristically-important values kept at higher precision. It's the dominant format for CPU, edge, and consumer-GPU inference because it doesn't require a CUDA/Python serving stack, unlike GPTQ/AWQ checkpoints which are typically loaded through `transformers` or a GPU-specific serving engine.
**Follow-up trap:** *"Would you pick GGUF for a high-throughput GPU serving cluster?"* — no, GPTQ/AWQ checkpoints through vLLM/TensorRT-LLM are the right choice there; GGUF's strength is portability and CPU/edge deployment, not maximizing GPU serving throughput.

### Q6 — Which task categories degrade first under aggressive quantization, and why?
**Testing:** the central quality-vs-cost-curve fact this module is built around.
**Answer:** Math and code degrade first and hardest, because they require precise multi-step reasoning where one quantization-induced error early in a chain invalidates everything downstream, unlike open-ended chat where a locally imprecise choice rarely wrecks the whole response. Long-context retrieval and multilingual (especially low-resource languages) degrade next, followed by general chat and summarization, which tolerate 4-bit weight-only quantization with well under a few points of loss.
**Follow-up trap:** *"Your aggregate eval looks great after quantizing to 4-bit. Ship it?"* — not on that basis alone; check specifically on whichever of these fragile categories your product actually serves, because a strong aggregate number is exactly what hides a code- or math-specific regression.

### Q7 — When would you quantize the KV cache to INT4 versus INT8 versus FP8?
**Answer:** INT8 KV cache holds accuracy well across most workloads including code-completion-style tasks. FP8 KV cache is close to free on long-context retrieval benchmarks, typically under 0.5 percentage points of loss, and is the safer aggressive default when you need the memory back. INT4 KV cache shows real, growing degradation with context length and reasoning-heavy tasks, because per-step quantization error compounds across every subsequent attention read of that cache — reserve it for short-context or non-reasoning workloads where you've specifically validated it.
**Follow-up trap:** *"You need to quantize KV cache for a long-running agentic coding assistant. What do you pick?"* — INT8 or FP8, not INT4; agentic coding sessions are exactly the long, reasoning-heavy, error-compounding profile where INT4 KV degradation is worst, and this is a workload you should explicitly measure rather than assume is fine because a general benchmark said INT4 KV was "almost lossless."

### Q8 — Why does calibration data choice matter for GPTQ/AWQ, mechanically?
**Answer:** Both methods derive their quantization parameters from activation statistics observed on a calibration set (typically 128-512 samples) — GPTQ's Hessian-based error correction and AWQ's salient-channel identification both depend on what activation patterns they actually see during calibration. Calibrating on a generic corpus when production traffic is domain-specific (code, a non-English language, legal text) means the protected channels and computed scales reflect the wrong distribution, and the quantized model can look fine on general benchmarks while silently underperforming on the actual deployment traffic.
**Follow-up trap:** *"Your calibration set is 500 samples of English customer support chat, and you're deploying a multilingual assistant. What breaks?"* — the salient channels AWQ protects, and the Hessian statistics GPTQ uses, are tuned to English text patterns; non-English (especially low-resource-language) inputs may activate different channels that weren't protected, producing degradation invisible in an English-only eval — recalibrate on a multilingual sample matching your actual traffic mix.

### Q9 — Weight-only versus weight-and-activation quantization: when does each actually matter?
**Answer:** Weight-only (GPTQ/AWQ/GGUF/NF4) shrinks bytes read from HBM, which is what memory-bound decode needs, and it's simpler because weights lack the outlier problem — but it doesn't unlock faster matmul throughput since the matmul still runs at higher precision after on-the-fly dequantization. Weight-and-activation (SmoothQuant-style W8A8, or FP8 both sides) is needed when the bottleneck is actually compute — large-batch serving, prefill on long prompts — because it engages real INT8/FP8 tensor-core throughput instead of just reducing memory traffic.
**Follow-up trap:** *"You quantized weights to 4-bit and throughput barely improved at batch size 64. What's the likely cause?"* — batch size 64 prefill or large-batch decode is likely compute-bound already, not memory-bound, so weight-only quantization's bandwidth win doesn't translate into much throughput gain there; you'd need activation quantization to actually move the needle in that regime.

### Q10 — A colleague claims "quantization always costs less than 1% quality, it's basically free." How do you respond?
**Testing:** pushing back on an oversimplified claim with the actual nuance.
**Answer:** That's true for some task/method/bit-width combinations (INT8 weight-only on general chat, FP8 on most things) and false for others (INT4 on math/code/long-reasoning, naive INT8 activation quantization without outlier handling, INT4 KV cache on long agentic sessions) — the "basically free" framing is exactly the trap that lets a code-generation regression ship silently behind a green aggregate benchmark. The honest claim is task- and method-specific, not universal.
**Follow-up trap:** *"Give me a concrete number where it's clearly not free."* — GPTQ 4-bit on HumanEval trails fp16 by roughly 10 points (46% vs 56.1%), and some reported aggressive/naive quantization schemes have shown HumanEval pass-rate drops as severe as 92% on smaller (e.g., 13B-class) models specifically — smaller models have less redundant capacity to absorb quantization error than larger ones at the same bit width.

### Q11 — Design the quantization strategy for a coding-assistant product serving both interactive (low-batch, latency-sensitive) and batch-review (high-batch, throughput-sensitive) workloads.
**Testing:** synthesis across memory-vs-compute-bound reasoning and task-specific degradation.
**Answer:** For the interactive path (memory-bound decode), use AWQ 4-bit weight-only quantization plus INT8 or FP8 KV cache — code is a fragile task category, so avoid INT4 KV and validate specifically on a HumanEval-style held-out set before shipping, not just a general chat benchmark. For the batch-review path (compute-bound, large-batch prefill), weight-only quantization alone won't move throughput much; add W8A8 (SmoothQuant-style) or FP8 activations to actually engage faster tensor-core paths, calibrated on a sample of real code from the target domain, not a generic web-text corpus.
**Follow-up trap:** *"Your interactive path passes code eval but a customer reports subtly wrong logic only after long multi-file sessions."* — check the KV-cache precision first; that's the classic error-compounding signature of aggressive KV quantization on a long reasoning/agentic chain, and it can slip past a short-session eval that never exercises enough decode steps for the error to accumulate visibly.

### Q12 — Rank GPTQ, AWQ, GGUF Q4_K_M, naive INT8 (no outlier handling), and FP8 by "risk of silently shipping degraded quality," and justify it.
**Answer:** 1) **Naive INT8 activation quantization with no outlier handling** — the highest risk, because it can produce garbage or badly degraded output from a mechanism (outlier clipping) that's easy to miss if you only check perplexity on typical inputs rather than specifically probing the channels most affected. 2) **INT4 via GPTQ on a fragile task category (code/math) without task-specific validation** — real, measurable risk (roughly 10-point HumanEval gap), likely to ship if only a general benchmark is checked. 3) **INT4 via AWQ or GGUF k-quants** — real but smaller risk (roughly 4-point HumanEval gap), and lower risk because AWQ's activation-aware protection specifically targets what naive quantization misses. 4) **FP8** — lowest risk among the aggressive options, typically close to fp16 quality without heavy calibration effort, on hardware that supports it natively.
**Follow-up trap:** *"Doesn't this ranking argue for just always using FP8 and skipping the others?"* — only where the hardware supports it (Hopper+) and the memory savings target (roughly 50%) is sufficient; if you need the 4x savings INT4 provides and have H100-class memory constraints that FP8 alone doesn't solve, you're back to choosing carefully among AWQ/GPTQ/GGUF with task-specific validation, which is the actual point: there's no universally correct choice independent of your hardware and workload.

---

## Red flags that fail you

- Saying "quantization is basically free" without naming which task categories degrade first.
- Not knowing that decode is memory-bandwidth-bound while prefill is compute-bound, or why that distinction determines which quantization approach helps.
- Treating weight-only and weight-and-activation quantization as interchangeable.
- Applying weight-quantization intuition ("weights survive INT8/INT4 fine") to activations without knowing about outlier channels.
- Recommending INT4 KV cache for a long-context or agentic workload without flagging the error-compounding risk.
- Validating a quantization decision against only an aggregate benchmark, with no task-specific check.
- Not knowing calibration data choice affects GPTQ/AWQ quality on domain-specific traffic.

---

## Cheat card

```
BYTES/PARAM      fp32=4  fp16/bf16=2  fp8=1  int8=1  int4/nf4=0.5
DECODE BOUND     memory bandwidth, NOT flops -- ~1 FLOP/byte at batch=1,
                 ~100-200x below the compute/bandwidth ridge point on H100-class GPUs
                 -> shrink bytes moved, decode speeds up ~proportionally
PREFILL BOUND    compute -- benefits from real INT8/FP8 tensor-core throughput
                 (weight+activation quant), not just smaller weight bytes

PTQ vs QAT       PTQ: quantize trained model, small calib set (128-512 samples),
                 cheap, the default. QAT: simulate quant noise during training,
                 only worth it for sub-4-bit + already fine-tuning

WEIGHT METHODS   GPTQ: layer-wise Hessian error correction (2022)
                 AWQ: protect salient channels via ACTIVATION magnitude (2023),
                   2026 GPU-serving default, better at 4-bit than GPTQ
                 GGUF k-quants: file format, Q2_K-Q8_0, mixed precision per block,
                   CPU/edge/llama.cpp default (Q4_K_M common)
                 NF4 (bitsandbytes): normal-quantile bins + double quant, QLoRA

MEASURED GAP     HumanEval @ 4bit: fp16=56.1%, AWQ/GGUF~51.8% (-4pt), GPTQ~46% (-10pt)

OUTLIERS         activation channels 20-100x larger than rest, fixed dims, ~6-7B+
                 params -- weights DON'T have this, activations DO
                 fix: LLM.int8() mixed precision, OR SmoothQuant offline rescale:
                 (X/s)(sW) = XW  -- exact, migrates difficulty activations->weights

DEGRADE ORDER    chat/summarization (safest) < long-context/multilingual <
                 math/code (fails first -- compounding multi-step errors)

KV CACHE QUANT   INT8: safe most tasks | FP8: <0.5pt on long-context retrieval |
                 INT4: real loss, grows with context length + reasoning depth
                 (error compounds across every subsequent attention read)

CALIBRATION      GPTQ/AWQ scales come from calib set -- mismatched domain/language
                 calibration = invisible degradation on YOUR traffic

NEVER            INT4 KV on long agentic/reasoning sessions without measuring;
                 ship on aggregate benchmark alone for a code/math product;
                 naive INT8 activations with no outlier handling
```

## Sources

- [AWQ vs GGUF vs GPTQ: Quantization Methods Compared for AI 2026 — Index.dev](https://www.index.dev/skill-vs-skill/ai-gptq-vs-awq-vs-gguf) — accessed 2026-08-01
- [GPTQ vs AWQ vs GGUF: Which 4-Bit to Pick in 2026 — TheAIEngineer](https://theaiengineer.substack.com/p/quantization-in-practice-gptq-vs) — accessed 2026-08-01
- [SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models (arXiv:2211.10438)](https://arxiv.org/abs/2211.10438) — accessed 2026-08-01
- [Systematic Characterization of LLM Quantization: A Performance, Energy, and Quality Perspective (arXiv:2508.16712)](https://arxiv.org/pdf/2508.16712) — accessed 2026-08-01
- [Mind the Memory Gap: Unveiling GPU Bottlenecks in Large-Batch LLM Inference (arXiv:2503.08311)](https://arxiv.org/html/2503.08311v2) — accessed 2026-08-01
- [KV cache quantization: what FP8/INT8 K and V actually buy you, and where they break](https://dev.to/tech_nuggets/kv-cache-quantization-what-fp8int8-k-and-v-actually-buy-you-and-where-they-break-4fnl) — accessed 2026-08-01
- [Is KV Cache Quantization Sabotaging Your Context?](https://dasroot.net/posts/2026/05/kv-cache-quantization-agentic-coding-long-horizon/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
