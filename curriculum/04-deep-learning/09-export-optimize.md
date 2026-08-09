# Export and Optimize: ONNX, TensorRT, PTQ vs QAT, Pruning, and Distillation

> **Track:** T04 Deep Learning · **Time:** 2.5h · **Prereqs:** T04-compile-cuda · **Updated:** 2026-08-03
> **Module id:** `T04-export-optimize` · **Tags:** deployment
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Deploying a trained model is a separate optimization problem from training it, and four techniques dominate: **ONNX** is a framework-agnostic intermediate graph representation (current release 1.22.0, opset 27 as of mid-2026) that lets a model trained in one framework run in a different runtime — PyTorch 2.9 defaults `torch.onnx.export` to a Dynamo-based exporter, recommended for opset ≥18, precisely because it reuses the same graph-capture machinery as `torch.compile` (`T04-compile-cuda`) rather than PyTorch's older, more fragile tracing-based exporter. **TensorRT** (and TensorRT-LLM for language models specifically) takes that graph and compiles a hardware-specific, fused, precision-calibrated inference engine for a *particular* GPU, applying layer fusion (the same motivation as Inductor's fusion in the previous module) plus kernel auto-tuning and quantization. **Quantization** reduces numeric precision for inference specifically, and comes in two flavors with a real, quantifiable accuracy tradeoff: **PTQ** (post-training quantization) quantizes an already-trained model's weights (and often activations) using a small calibration dataset to pick scale factors, with no retraining — for symmetric INT8 quantization of a weight range `[-2.0, 2.0]` (`scale = 2.0/127 ≈ 0.015748`), quantizing `w=1.3` gives `q=round(1.3/0.015748)=83`, dequantizing to `1.307` (error `≈0.0071`); the identical value quantized to INT4 (`scale=2.0/7≈0.2857`) gives `q=5`, dequantizing to `1.429` (error `≈0.1286`) — roughly **18x more error** at 4 bits than 8 bits for the same value, which is exactly why aggressive low-bit PTQ frequently needs additional tricks (SmoothQuant-style activation-outlier handling, AWQ-style activation-aware weight scaling) to hold accuracy. **QAT** (quantization-aware training) instead simulates quantization *during* training or fine-tuning (fake-quantizing the forward pass while using a straight-through estimator — approximating the rounding function's true, almost-everywhere-zero gradient as an identity pass-through — for the backward pass), letting the model's weights adapt to be robust to quantization noise, at the cost of requiring actual retraining/fine-tuning compute, but recovering meaningfully more accuracy at aggressive bit-widths than PTQ alone. **Pruning** removes parameters entirely — structured pruning (whole channels/filters/attention heads) gives real speedup on any hardware since the resulting model is genuinely smaller and dense; unstructured pruning (individual weights zeroed anywhere in a tensor) gives no speedup at all without specialized sparse-matmul hardware/kernels; semi-structured N:M sparsity (e.g. 2-of-every-4 weights zeroed) is the practical middle ground natively accelerated by NVIDIA Ampere-and-newer sparse Tensor Cores. **Distillation** (Hinton et al., 2015) trains a smaller student model to match a larger teacher's *soft*, temperature-softened output distribution rather than only the hard labels — softening with temperature `T=4` turns a peaked teacher distribution like `[0.858, 0.116, 0.026]` (at `T=1`) into a much more informative `[0.494, 0.300, 0.206]`, transferring the teacher's relative confidence across *wrong* answers ("dark knowledge") that hard labels alone discard. In practice, these compose: a 2025 study on compression ordering found pruning, then distillation-based retraining, then quantization (in that order) gives the best accuracy-preservation balance among tested sequences.

## Why this gets asked

Because training a good model and deploying it cost-effectively at inference scale are genuinely different problems with different constraints (latency SLAs, cost-per-token, hardware footprint), and interviewers want to know whether a candidate has actually shipped an optimized model to production or has only ever run `model.eval()` on the same hardware and precision it trained on. It's also a fast way to test quantitative reasoning under a specific, checkable constraint: can you actually compute a quantization scale factor and its resulting error, or do you only know "quantization makes models smaller" as a slogan — and do you understand *why* PTQ sometimes isn't good enough (forcing the more expensive QAT path), rather than treating all "make the model smaller" techniques as interchangeable.

---

## Lineage: past → present → future

**What came before.** Early deployment of trained neural networks typically meant running the exact same framework, precision, and hardware used for training directly in production — functionally simple, but leaving substantial performance and cost on the table, since training-time precision (fp32, later fp16/bf16) and training-time frameworks (optimized for flexibility and gradient computation) are not the same thing a latency- and cost-sensitive inference deployment actually needs. The pain this created as models grew: serving a model at the same precision and framework overhead it trained with became measurably too slow and too expensive at real production request volumes, especially once models scaled into the billions of parameters — a gap that motivated purpose-built inference optimization (ONNX for portability, TensorRT for hardware-specific compilation, quantization/pruning/distillation for actually shrinking the compute and memory footprint) as a distinct engineering discipline from training.

**Where it stands now.** ONNX and TensorRT are mature, standard, production-proven tools — ONNX 1.22 (opset 27) as of mid-2026, with PyTorch's own exporter defaulting to the more robust Dynamo-based path since version 2.9, and TensorRT-LLM specifically focused on state-of-the-art PTQ for LLM serving (INT8 via SmoothQuant, FP8 on H100-and-newer, INT4 via AWQ), with NVIDIA's ModelOpt unifying PTQ, QAT, sparsity, and pruning under one API as the current recommended quantization framework for TensorRT-LLM deployment. The live, practically-important tension is PTQ versus QAT at increasingly aggressive precision: PTQ remains the default first attempt (cheap, no retraining) for INT8 and even FP8, but as deployments push toward INT4 and below, the accuracy gap between PTQ and QAT widens (as the quantization-error arithmetic above quantifies), making QAT — despite its real retraining cost — increasingly necessary rather than optional at the most aggressive compression targets. Structured versus semi-structured (N:M) pruning is similarly settled in favor of whichever pattern the target hardware actually accelerates — unstructured pruning's appeal (maximum theoretical flexibility) is real but moot without matching sparse-compute hardware support, which is exactly why 2:4 semi-structured sparsity (natively supported since Ampere) sees much more real production use than fully unstructured pruning despite the latter's larger nominal parameter reduction.

**Where it's heading.** The 2025-2026 research and production consensus increasingly treats pruning, distillation, and quantization as a *composed pipeline* rather than independent, competing techniques — a documented finding that a pruning-then-distillation-then-quantization ordering ("P-KD-Q") yields the best balance among tested sequences, and NVIDIA's own MINITRON work explicitly combines depth/width/attention/MLP pruning with knowledge-distillation-based retraining as a single integrated recipe. What's actively evolving: sub-INT4 quantization schemes remain a genuine research frontier (with real accuracy tradeoffs still being actively characterized), and the specific ordering/combination of compression techniques that best preserves quality for a given target compression ratio is still being refined empirically rather than settled by one universally-agreed-upon recipe — teams should expect to validate a specific compression pipeline's accuracy on their own task rather than assume any published recipe transfers unchanged.

---

## Mental model

```
TRAINED MODEL (fp32/bf16, framework-specific, all parameters intact)
     |
     v   ONNX EXPORT: framework-agnostic graph IR (opset version = feature/op set)
  ONNX GRAPH  --portable across runtimes/frameworks--
     |
     v   TensorRT (or equivalent): HARDWARE-SPECIFIC compiled engine
  FUSED, KERNEL-TUNED, PRECISION-CALIBRATED inference engine (for THIS GPU model)

THREE INDEPENDENT SHRINKING LEVERS (compose, don't compete):

QUANTIZATION (reduce numeric precision):
  PTQ: quantize AFTER training, calibration data picks scale -- NO retraining
    symmetric INT8, range [-2,2]: scale=2/127=0.01575
      w=1.3 -> q=round(1.3/0.01575)=83 -> dequant=1.307 (error 0.0071)
    same w at INT4: scale=2/7=0.2857 -> q=5 -> dequant=1.429 (error 0.1286)
      ~18x MORE error at 4 bits -- PTQ alone struggles here
  QAT: FAKE-quantize during training/fine-tuning, straight-through estimator
    for the backward pass (round() has ~0 gradient almost everywhere --
    approximate its gradient as identity) -- model LEARNS to be robust
    -> better accuracy at aggressive bit-widths, costs retraining compute

PRUNING (remove parameters):
  structured (whole channels/heads): dense result -> speedup on ANY hardware
  unstructured (individual weights): NO speedup without sparse-matmul hardware
  semi-structured N:M (e.g. 2:4): speedup on Ampere+ sparse Tensor Cores

DISTILLATION (train a SMALLER student to match a LARGER teacher):
  soft, temperature-softened teacher output carries "dark knowledge"
    T=1 (peaked): [0.858, 0.116, 0.026]
    T=4 (softened): [0.494, 0.300, 0.206]  <- reveals relative confidence
                                              across WRONG answers too

BEST-KNOWN ORDER (2025 study): PRUNE -> DISTILL (retrain) -> QUANTIZE
```

The one-line mental model: **inference optimization is a separate engineering discipline from training, built on portability (ONNX), hardware-specific compilation (TensorRT), and three independently-composable shrinking levers (quantization, pruning, distillation) — and every one of them trades some measurable accuracy for some measurable efficiency gain, never for free.**

---

## How it actually works

### ONNX: what an opset actually is, and why the Dynamo exporter matters

ONNX represents a model as a graph of standardized operations; the **opset version** is the specific, versioned set of operation definitions the graph is allowed to use — a model exported at opset 18 uses only operations defined by opset 18 or earlier, and an ONNX Runtime (or any other ONNX-consuming runtime) must support that opset version to run it. ONNX Runtime supports every opset from ONNX's very early releases (opset 7+) through the latest (opset 27 as of ONNX 1.22, June 2026), so opset compatibility is rarely the practical constraint it once was — the more consequential recent change is *how* PyTorch produces the ONNX graph in the first place: PyTorch 2.9 defaults `torch.onnx.export` to the **Dynamo-based** exporter (recommended specifically for opset ≥18), which traces the model using the same Dynamo graph-capture machinery `T04-compile-cuda` covers, rather than PyTorch's older tracing/scripting-based exporter — this matters because it inherits Dynamo's more robust handling of real, dynamic Python control flow, the exact same reliability improvement that made `torch.compile` itself more broadly adoptable than TorchScript was.

### TensorRT: fusion and calibration, hardware-specific by design

TensorRT compiles an ONNX (or native-framework) graph into an inference engine specifically optimized for a *particular* GPU architecture — it performs layer fusion (combining sequences of operations into fewer, larger kernels, precisely the same motivation as Inductor's fusion in the previous module, just applied ahead-of-time for a fixed inference graph rather than dynamically during a compiled training/inference call) and kernel auto-tuning (selecting the best-performing kernel implementation for the specific GPU it's compiling for, from among several candidate implementations). TensorRT-LLM applies this specifically to language model serving, with its current (2026) focus on state-of-the-art **post-training** quantization: INT8 via SmoothQuant (which specifically addresses the observation that LLM activations, unlike weights, have significant outlier values that naive per-tensor INT8 quantization handles poorly — SmoothQuant migrates some of that quantization difficulty from activations to weights via a mathematically-equivalent rescaling), FP8 on Hopper-and-newer GPUs (near-FP16 accuracy at half the memory/bandwidth cost), and INT4 via AWQ (activation-aware weight quantization, which identifies and preserves the small fraction of weights most sensitive to quantization error based on their corresponding activation magnitudes, rather than quantizing every weight identically). NVIDIA's **ModelOpt** unifies PTQ, QAT, sparsity, and pruning configuration under one API, the current recommended path for preparing a model for TensorRT-LLM deployment.

### The quantization arithmetic, worked precisely

Symmetric quantization to `b` bits maps a real-valued weight range `[-max_abs, max_abs]` onto integers `[-(2^(b-1)-1), 2^(b-1)-1]` via a scale factor `scale = max_abs / (2^(b-1)-1)`; quantizing a value `w` computes `q = round(w/scale)` (an integer), and dequantizing recovers an approximation `w' = q·scale`. For a weight range `max_abs=2.0` at **INT8** (`b=8`): `scale = 2.0/127 ≈ 0.015748`; quantizing `w=1.3`: `q=round(1.3/0.015748)=round(82.55)=83`, dequantizing: `83×0.015748≈1.307`, an error of `≈0.0071`. The identical value at **INT4** (`b=4`): `scale=2.0/7≈0.2857`; `q=round(1.3/0.2857)=round(4.55)=5`, dequantizing: `5×0.2857≈1.429`, an error of `≈0.1286` — roughly **18x larger** than the INT8 error for the exact same original value, purely because INT4 has only 15 representable levels across the same range versus INT8's 255. This concrete error-scaling is *why* naive PTQ becomes progressively harder to apply without accuracy loss as target bit-width drops, and why lower-bit deployments increasingly reach for either more sophisticated calibration (AWQ, SmoothQuant, addressing *which* weights/activations are most quantization-sensitive rather than treating them uniformly) or QAT (letting the model's weights themselves adapt around the quantization noise) rather than plain uniform PTQ.

### QAT and the straight-through estimator: how you train through a non-differentiable rounding function

QAT simulates quantization during training by inserting a "fake quantize" operation in the forward pass — computing `w' = round(w/scale)·scale` exactly as inference would, so the *forward* pass sees quantization's actual effect — but `round()` is a step function whose true derivative is exactly zero almost everywhere (and undefined at the step boundaries), which would make ordinary backpropagation (per `T04-autograd`'s reliance on well-defined local derivatives) report zero gradient for every weight, making the model untrainable through this operation. The **straight-through estimator** (STE) sidesteps this by defining a custom backward pass (exactly the `torch.autograd.Function` forward/backward pairing from `T04-autograd`) that simply passes the incoming gradient through unchanged (optionally zeroing it where the input was clipped outside the representable range), *pretending* the forward pass's rounding was actually an identity function for gradient purposes — a deliberate, principled approximation (not the "true" gradient, which is genuinely useless at zero almost everywhere) that in practice lets gradient descent successfully push weights toward configurations that are more robust to the real, applied quantization, which is exactly the mechanism that gives QAT its accuracy advantage over PTQ at aggressive bit-widths.

### Pruning: structured versus unstructured versus semi-structured, and why hardware determines which one pays off

**Structured pruning** removes entire structural units (channels, filters, attention heads, or whole layers), producing a genuinely smaller, still-fully-dense model — this gets real speedup on *any* hardware, since the resulting computation is just ordinary dense matrix multiplication at a smaller size, no special kernel support required. **Unstructured pruning** zeroes out individual weights anywhere within a tensor based on some importance criterion (e.g., magnitude), which can achieve a much higher nominal sparsity ratio for the same accuracy cost, but yields *zero* speedup on standard dense hardware/kernels — the zeroed weights still occupy the same memory layout and get multiplied (by zero, wastefully) in an ordinary dense matmul, unless the deployment target has genuine sparse-matrix compute support. **Semi-structured (N:M) sparsity** — e.g. exactly 2 of every 4 contiguous weights forced to zero — is the practical middle ground: a regular-enough pattern that NVIDIA's Ampere-and-newer GPUs accelerate natively via dedicated sparse Tensor Core support (roughly 2x throughput for a correctly-configured 2:4 sparse matmul versus the equivalent dense one), without requiring the fully-flexible (but hardware-unsupported) freedom of unstructured pruning. The practical lesson: pruning's benefit is entirely contingent on matching the sparsity *pattern* to what the target deployment hardware can actually accelerate — the theoretically-largest parameter reduction (unstructured) is frequently the practically-least-useful choice absent specialized hardware.

### Distillation: temperature softening and "dark knowledge"

Knowledge distillation (Hinton, Vinyals, Dean, 2015) trains a smaller student model not just on hard ground-truth labels, but to match a larger, already-trained teacher model's *soft* output distribution — computed with a **temperature** `T` applied inside the softmax (`softmax(z/T)`, per `T04-neural-net-math`'s softmax formula, with `T>1` flattening the distribution): at `T=1`, a confident teacher's output for a 3-class example might be `[0.858, 0.116, 0.026]`; at `T=4`, the *same underlying logits* soften to `[0.494, 0.300, 0.206]` — revealing that the teacher considers the second class meaningfully more plausible than the third, information a hard one-hot label (or even the unsoftened `T=1` distribution) largely discards. Training the student against this softened distribution (typically combined with a smaller-weighted hard-label loss term) transfers this "dark knowledge" — the teacher's *relative* confidence across wrong answers, which correlates with genuine similarity structure in the data — letting a meaningfully smaller student reach accuracy closer to the teacher's than training that same small student from scratch on hard labels alone would achieve.

### Why the composition order matters: prune, then distill, then quantize

A 2025 study on compression ordering found that applying **pruning, then distillation-based retraining, then quantization** (in that order) yields the best accuracy-preservation balance among the sequences tested — the intuition: pruning first removes now-provably-unnecessary capacity while the model can still be fully retrained/fine-tuned to recover from that removal (via distillation against the original, unpruned teacher); quantizing *before* that retraining step would instead ask a not-yet-adapted, still-being-pruned model to simultaneously absorb quantization noise, a harder joint optimization problem than handling each source of accuracy loss in sequence, letting each subsequent step's training recover from what the previous step's compression cost. NVIDIA's MINITRON work operationalizes exactly this idea at production scale, integrating depth/width/attention/MLP pruning with distillation-based retraining as a single, deliberately-ordered compression recipe rather than independently applying each technique.

---

## Build it from scratch

```python
# untested sketch -- illustrates the quantization arithmetic and straight-through estimator
def quantize_symmetric(w, max_abs, bits):
    scale = max_abs / (2 ** (bits - 1) - 1)
    q = round(w / scale)
    return q, scale

def dequantize(q, scale):
    return q * scale

# straight-through estimator, as a custom autograd Function (pattern from T04-autograd)
class FakeQuantizeSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, w, scale, q_min, q_max):
        ctx.save_for_backward(w)
        ctx.q_min, ctx.q_max, ctx.scale = q_min, q_max, scale
        q = torch.clamp(torch.round(w / scale), q_min, q_max)
        return q * scale                                # fake-quantized forward value

    @staticmethod
    def backward(ctx, grad_output):
        w, = ctx.saved_tensors
        # STE: pass gradient straight through, EXCEPT where clipping occurred
        mask = (w / ctx.scale >= ctx.q_min) & (w / ctx.scale <= ctx.q_max)
        return grad_output * mask, None, None, None
```
Reproducing the INT8-vs-INT4 quantization error table above for a range of weight values, and training a tiny STE-based fake-quantized layer on a toy task to confirm it actually learns (versus a naive quantization-in-forward-with-no-STE version, which should fail to learn at all due to zero gradient) is the lab exercise in `labs/python/09-export-optimize/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| INT4-quantized model's accuracy drops far more than the same model quantized to INT8 | Quantization error scales with bit-width roughly as this module's arithmetic shows (~18x larger error per value at INT4 vs INT8 for the same range) — naive uniform PTQ struggles increasingly as bit-width drops | Use activation/weight-aware calibration (AWQ, SmoothQuant) instead of naive uniform PTQ, or move to QAT if PTQ-with-better-calibration still isn't sufficient at the target bit-width |
| Unstructured pruning achieves a high reported sparsity ratio but delivers no measured inference speedup | Target hardware/kernel has no sparse-matmul acceleration — zeroed weights still occupy full memory and get multiplied in ordinary dense compute | Switch to structured pruning (guaranteed speedup on any hardware) or semi-structured N:M sparsity if targeting Ampere-or-newer GPUs with native sparse Tensor Core support |
| A QAT-trained quantized model doesn't actually learn (loss doesn't improve) when a custom fake-quantization layer is added | Missing or incorrect straight-through estimator — using the rounding function's true (near-zero-everywhere) gradient instead of an STE approximation | Implement fake-quantization as a custom `autograd.Function` (per `T04-autograd`) with an STE backward pass that passes gradient through unchanged (except where clipped) |
| A distilled student model underperforms expectations despite training against the teacher's outputs | Distilling only against hard labels or an unsoftened (`T=1`) teacher distribution, discarding the "dark knowledge" in the teacher's relative confidence across wrong classes | Increase the distillation temperature `T` (commonly in the range of a few units above 1) when computing the teacher's soft targets, and confirm the student loss actually incorporates the soft-target term, not only the hard-label term |
| ONNX export of a PyTorch model with data-dependent control flow fails or produces an incorrect graph | Using the older, tracing-based ONNX exporter path, which (like TorchScript tracing) struggles with genuinely dynamic control flow | Use the Dynamo-based exporter (PyTorch 2.9's default for `torch.onnx.export`), which shares Dynamo's more robust dynamic-control-flow handling from `T04-compile-cuda` |

---

## Tradeoffs & when NOT to use it

- **Don't reach for QAT by default.** It requires real retraining/fine-tuning compute and engineering effort; PTQ (especially with modern calibration techniques like AWQ/SmoothQuant) is frequently sufficient at INT8 and even FP8, and is dramatically cheaper — reserve QAT for cases where PTQ, with reasonable calibration effort, measurably fails to hit the accuracy bar at your target bit-width (most commonly at INT4 and below).
- **Don't prune unstructured just because it achieves a higher nominal sparsity percentage.** That percentage is meaningless for actual inference speed on hardware without sparse-matmul support — always match the pruning pattern (structured, or the specific N:M ratio) to what your actual deployment target accelerates.
- **Don't distill without also validating the student's actual production task performance, not just its agreement with the teacher.** A student trained purely to mimic a teacher can end up faithfully reproducing the teacher's specific failure modes and biases as well as its strengths — validate on the real downstream task and data distribution, not only distillation loss.
- **Don't assume the same compression recipe (order, technique, target bit-width) that worked for one model/task transfers unchanged to another.** The prune-then-distill-then-quantize ordering is a strong, empirically-supported default, not a universal law — validate accuracy at each stage on your own task before committing to a full pipeline, especially at aggressive compression targets where headroom for error is smaller.

---

## Interview questions

### Q1 — What is an ONNX opset, and why does it matter for deployment compatibility?
**Testing:** the actual mechanics of ONNX versioning, not "ONNX makes models portable."
**Answer:** An opset is a specific, versioned set of operation definitions a graph is allowed to use — a model exported at a given opset version can only use operations defined by that version or earlier, and any runtime consuming that model must support that opset to run it correctly. Opset compatibility is largely a solved problem today since ONNX Runtime supports the full range from early opsets through the current latest (opset 27 as of ONNX 1.22), but exporting at an unnecessarily old opset can mean missing newer, more efficient operation definitions the exporting framework could otherwise use.
**Follow-up trap:** *"Why does PyTorch 2.9 recommend the Dynamo-based exporter specifically for opset >= 18, rather than the older exporter?"* — the Dynamo-based exporter reuses the same robust, real-Python-control-flow-tracing machinery `torch.compile` uses (per `T04-compile-cuda`), which handles dynamic control flow far more reliably than the older tracing/scripting-based exporter — this is a reliability improvement, not merely a newer default for its own sake.

### Q2 — Compute the quantization error for a weight value of 1.3 quantized symmetrically to INT8 versus INT4, given a weight range of [-2.0, 2.0], and explain why the difference is so large.
**Testing:** actual arithmetic execution, the module's central worked example.
**Answer:** INT8: `scale=2.0/127≈0.015748`, `q=round(1.3/0.015748)=83`, dequantized `≈1.307`, error `≈0.0071`. INT4: `scale=2.0/7≈0.2857`, `q=round(1.3/0.2857)=5`, dequantized `≈1.429`, error `≈0.1286` — roughly 18x larger. The difference is large because INT4 has only 15 representable levels across the same range versus INT8's 255, so each representable step corresponds to a much coarser real-valued gap.
**Follow-up trap:** *"Does this mean INT4 quantization is never viable in production?"* — no; it's viable but requires more sophistication than naive uniform PTQ to hold accuracy at that error scale — activation-aware calibration (AWQ) or QAT (letting the model's weights adapt around the quantization noise during training) are the standard mitigations that make INT4 practically viable despite this larger per-value error.

### Q3 — Why can't you train through a fake-quantization operation using ordinary backpropagation, and what does the straight-through estimator do about it?
**Testing:** the actual mechanical reason QAT needs a special gradient trick, connecting to the autograd module.
**Answer:** `round()` is a step function whose true derivative is exactly zero almost everywhere (and undefined at step boundaries) — ordinary backpropagation would report zero gradient through this operation for essentially every weight, making the model completely untrainable through it. The straight-through estimator defines a custom backward pass (via a custom `autograd.Function`, per `T04-autograd`) that passes the incoming gradient through unchanged instead of using round's true near-zero gradient — a deliberate approximation, not the mathematically "correct" gradient, but one that empirically lets the model successfully learn weights robust to the applied quantization.
**Follow-up trap:** *"Is the straight-through estimator's gradient 'wrong,' and does that matter?"* — yes, it's not the true gradient of the forward computation as actually written — but the true gradient (zero almost everywhere) is useless for learning, so STE is a pragmatic, working approximation rather than a mathematically rigorous derivative; its justification is empirical (it demonstrably lets QAT models learn and outperform PTQ at aggressive bit-widths), not a claim of gradient correctness.

### Q4 — Why does unstructured pruning frequently deliver no inference speedup despite achieving a higher nominal sparsity ratio than structured pruning?
**Testing:** the hardware-dependency of pruning's actual payoff, a commonly-missed practical point.
**Answer:** Unstructured pruning zeroes individual weights scattered arbitrarily throughout a tensor — without specialized sparse-matmul hardware/kernels, those zeroed weights still occupy the same memory layout and still get multiplied (wastefully, by zero) in an ordinary dense matrix multiply, yielding no actual compute or memory savings at inference. Structured pruning removes entire channels/filters/heads, producing a genuinely smaller, still fully dense model that gets real speedup on any hardware, since the resulting computation is just ordinary dense matmul at a smaller size.
**Follow-up trap:** *"Where does semi-structured (N:M) sparsity fit between these two, and what specific hardware makes it worthwhile?"* — it's the practical middle ground: a regular enough pattern (e.g. exactly 2 of every 4 contiguous weights zeroed) that NVIDIA's Ampere-and-newer GPUs accelerate natively via dedicated sparse Tensor Core support (roughly 2x throughput for a correctly-configured 2:4 sparse matmul versus dense), without needing unstructured pruning's full (but hardware-unsupported) flexibility.

### Q5 — What is "dark knowledge" in knowledge distillation, and how does temperature scaling reveal it?
**Testing:** the specific mechanism, not "distillation trains a smaller model."
**Answer:** A confidently-trained teacher's raw (`T=1`) output distribution is typically sharply peaked (e.g. `[0.858, 0.116, 0.026]`), discarding most information about relative plausibility among the non-predicted classes. Applying temperature `T>1` inside the softmax (`softmax(z/T)`) flattens the same underlying logits into a softer distribution (e.g. `[0.494, 0.300, 0.206]` at `T=4`), revealing the teacher's relative confidence across the wrong answers too — this "dark knowledge" (which wrong answers the teacher considers more versus less plausible) correlates with genuine similarity structure in the data and is exactly what training the student only on hard one-hot labels would discard entirely.
**Follow-up trap:** *"Why not just always use a very high temperature to reveal maximum dark knowledge?"* — an excessively high temperature over-flattens the distribution toward uniform, diluting the genuinely useful relative-confidence signal along with it — temperature is a real hyperparameter to tune (commonly a few units above 1), not something to maximize unconditionally, and distillation losses typically also retain some weight on the hard-label term specifically to avoid over-relying on an over-softened signal.

### Q6 — Why does the empirically-best compression ordering put pruning before quantization rather than the reverse?
**Testing:** the reasoning behind the prune-then-distill-then-quantize sequence, not just citing it as a fact.
**Answer:** Pruning first removes now-demonstrably-unnecessary capacity while the model can still be fully retrained/fine-tuned (via distillation against the original teacher) to recover from that structural change — handling one source of accuracy degradation (structural capacity loss) at a time, with a full recovery step in between. Quantizing before that retraining/recovery step would instead ask a model that's simultaneously being pruned *and* absorbing quantization noise to jointly recover from both forms of degradation at once, a harder combined optimization problem than resolving each source of accuracy loss in its own sequential step.
**Follow-up trap:** *"Is this ordering a universal law, or does it need re-validation per task?"* — it's a strong, empirically-supported default from a 2025 study across the sequences tested, not a proven-universal law — teams should validate accuracy at each stage of the pipeline on their own specific task and data distribution before committing fully, especially since aggressive compression targets leave less margin for an ordering choice that happens not to transfer perfectly to a new setting.

### Q7 — What specific problem does SmoothQuant address in LLM INT8 quantization that naive per-tensor PTQ handles poorly?
**Testing:** a specific, current (2026) LLM-serving quantization technique, not generic quantization knowledge.
**Answer:** LLM activations (unlike weights) frequently have significant outlier values concentrated in specific channels — naive uniform INT8 quantization of activations must set its scale factor wide enough to accommodate those rare outliers, wasting most of INT8's resolution on the much more common, smaller-magnitude values and producing large relative error for the typical case. SmoothQuant addresses this via a mathematically-equivalent rescaling that migrates some of this quantization difficulty from activations to weights (which don't have the same outlier problem), making both sides of the multiplication easier to quantize accurately.
**Follow-up trap:** *"Why does this rescaling not change the mathematical result of the computation, only its quantization-friendliness?"* — SmoothQuant applies a per-channel scaling factor to activations and the inverse scaling to the corresponding weights before the matrix multiply, which is an algebraic identity (`(x·s)(w/s) = x·w`) that leaves the exact, full-precision result unchanged while redistributing which operand carries the numerically-difficult-to-quantize outlier magnitude.

### Q8 — A model quantized to INT8 via PTQ shows acceptable accuracy, but the same recipe applied to INT4 shows unacceptable accuracy loss. Your team has limited compute budget for retraining. What do you try before committing to full QAT?
**Testing:** staff-level judgment about intermediate options between "naive PTQ" and "full QAT," not jumping straight to the most expensive fix.
**Answer:** Try more sophisticated calibration first, since it requires no retraining: activation-aware weight quantization (AWQ, which identifies and preserves the weights most sensitive to quantization error based on their corresponding activation magnitudes) or SmoothQuant-style rescaling if activation quantization is also in play — both are calibration-only techniques (using a small representative dataset, no gradient-based retraining) that frequently close much of the PTQ-to-QAT accuracy gap at a fraction of QAT's compute cost. Only escalate to full QAT if better calibration still doesn't reach the accuracy bar.
**Follow-up trap:** *"What would make you skip straight to QAT instead of trying better calibration first?"* — if the target bit-width is aggressive enough (e.g. INT4 or below) that published results and prior experience strongly suggest calibration alone rarely closes the gap for your model class/task, or if the accuracy requirement is unusually strict (leaving little room to discover mid-pipeline that calibration wasn't sufficient) — in those cases, budgeting for QAT from the start, rather than iterating through cheaper options first, can be the more efficient overall path despite its higher up-front cost.

### Q9 — Why is TensorRT's compiled engine specific to a particular GPU architecture, rather than being portable the way an ONNX graph is?
**Testing:** understanding the tradeoff between ONNX's portability and TensorRT's hardware-specific optimization.
**Answer:** TensorRT's kernel auto-tuning and fusion decisions are made specifically for the target GPU's actual hardware characteristics (available Tensor Core generations, memory bandwidth, specific kernel implementations known to perform well on that architecture) — this specificity is exactly what buys the performance gain over a portable-but-generic execution, but it means an engine compiled for one GPU generation is not guaranteed to run (or run optimally) on a different one, unlike an ONNX graph, which is deliberately hardware-agnostic at the cost of leaving hardware-specific optimization on the table until something like TensorRT compiles it further.
**Follow-up trap:** *"Does this mean you need a separate TensorRT compilation step for every GPU model you might deploy to?"* — yes, in general — this is a genuine operational cost of TensorRT's approach, and production deployments targeting multiple GPU generations typically need to maintain and select among multiple compiled engines (one per target hardware configuration) rather than a single portable artifact, which is a real tradeoff against ONNX's simpler, hardware-agnostic portability.

### Q10 — Design question: you need to deploy a large language model to a strict, low-latency, cost-sensitive serving environment, and you have a moderate compute budget for post-training optimization (not full retraining from scratch, but some fine-tuning is affordable). Walk through which of this module's techniques you'd apply, and in what order.
**Testing:** staff-level synthesis of the whole module into a coherent deployment plan.
**Answer:** Start with structured or semi-structured (N:M, if targeting Ampere-or-newer GPUs) pruning to remove clearly-unnecessary capacity, since it's the first step in the empirically-best-known ordering and produces real speedup independent of quantization. Follow with distillation-based fine-tuning (using the original unpruned model as teacher, temperature-softened targets) to recover accuracy lost to pruning — this is exactly the "moderate fine-tuning budget" this scenario allows for, rather than full pretraining-scale retraining. Finally, apply quantization — starting with PTQ using activation-aware calibration (AWQ/SmoothQuant) at INT8 or FP8 first, only escalating to QAT (if the moderate fine-tuning budget can additionally absorb it) if the target deployment specifically requires more aggressive (INT4-or-below) precision and calibration-only PTQ doesn't hit the required accuracy bar.
**Follow-up trap:** *"What would you check before committing to this full pipeline, given you only have a moderate fine-tuning budget to spend once?"* — validate each stage's accuracy impact incrementally (measure after pruning+distillation-recovery, before committing further compute to quantization choices) rather than running the entire pipeline once and only checking final accuracy — since compute is limited, catching an accuracy problem early (e.g., pruning was too aggressive) is far cheaper to correct than discovering it only after the full pipeline, including quantization, has already consumed the available budget.

---

## Red flags that fail you

- Cannot compute a quantization scale factor or the resulting dequantization error for a specific bit-width.
- Doesn't know the difference between PTQ and QAT, or thinks QAT is "just PTQ done more carefully" rather than requiring actual retraining with a straight-through estimator.
- Believes unstructured pruning always delivers inference speedup proportional to its sparsity ratio, regardless of hardware.
- Cannot explain what a straight-through estimator does or why round() needs one to be trainable at all.
- Describes distillation as "training a smaller model to copy a bigger one" with no mention of temperature softening or dark knowledge.
- Treats pruning, quantization, and distillation as interchangeable or mutually exclusive rather than composable, order-sensitive techniques.

---

## Cheat card

```
ONNX: framework-agnostic graph IR; opset = versioned op set (current: opset 27,
  ONNX 1.22, mid-2026). PyTorch 2.9 torch.onnx.export defaults to DYNAMO exporter
  for opset>=18 -- same robust graph capture as torch.compile (T04-compile-cuda)

TensorRT/TensorRT-LLM: compiles a HARDWARE-SPECIFIC fused+tuned inference engine
  (not portable across GPU generations, unlike ONNX). 2026 focus: PTQ --
  SmoothQuant (INT8, fixes activation outliers via equivalent x*s, w/s rescale),
  FP8 (Hopper+), AWQ (INT4, weights scaled by activation-sensitivity).
  ModelOpt = unified PTQ/QAT/sparsity/pruning API

QUANTIZATION ARITHMETIC (symmetric, range [-max_abs,max_abs], b bits):
  scale = max_abs/(2^(b-1)-1); q=round(w/scale); dequant w'=q*scale
  worked (max_abs=2.0, w=1.3): INT8 scale=0.01575, q=83, error=0.0071
                                INT4 scale=0.2857,  q=5,  error=0.1286 (~18x worse)
  -> lower bits = much bigger error for the SAME value -- naive PTQ struggles at INT4

PTQ: quantize AFTER training, calibration data picks scale, NO retraining -- cheap
QAT: FAKE-quantize in forward during training/fine-tune; round() has ~0 gradient
  almost everywhere -> STRAIGHT-THROUGH ESTIMATOR: custom backward passes
  gradient through UNCHANGED (mask clipped region) -- costs retraining compute,
  recovers accuracy PTQ alone loses at aggressive bit-widths

PRUNING:
  structured (channels/heads/filters): dense result -> speedup on ANY hardware
  unstructured (individual weights):   NO speedup w/o sparse-matmul hardware
  semi-structured N:M (e.g. 2:4):      ~2x speedup on Ampere+ sparse Tensor Cores

DISTILLATION (Hinton 2015): student learns TEMPERATURE-SOFTENED teacher output
  softmax(z/T): T=1 peaked [0.858,0.116,0.026] -> T=4 softened [0.494,0.300,0.206]
  reveals "dark knowledge" (relative confidence across WRONG classes)

BEST-KNOWN ORDER (2025 study): PRUNE -> DISTILL/retrain -> QUANTIZE
  (recover from structural loss BEFORE adding quantization noise on top)
```

## Sources

- [ONNX Runtime compatibility — onnxruntime.ai](https://onnxruntime.ai/docs/reference/compatibility.html) — accessed 2026-08-03
- [torch.onnx — PyTorch 2.9+ documentation (Dynamo exporter default)](https://docs.pytorch.org/docs/stable/onnx.html) — accessed 2026-08-03
- [Speed up inference with SOTA quantization techniques in TRT-LLM — NVIDIA TensorRT-LLM docs](https://nvidia.github.io/TensorRT-LLM/blogs/quantization-in-TRT-LLM.html) — accessed 2026-08-03
- [Distilling the Knowledge in a Neural Network — Hinton, Vinyals, Dean (2015)](https://arxiv.org/abs/1503.02531) — accessed 2026-08-03
- [SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models — Xiao et al. (2022)](https://arxiv.org/abs/2211.10438) — accessed 2026-08-03
- [AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration — Lin et al. (2023)](https://arxiv.org/abs/2306.00978) — accessed 2026-08-03
- [LLM Pruning and Distillation in Practice (MINITRON) — NVIDIA, OpenReview](https://openreview.net/forum?id=mMmzHS28ht) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
