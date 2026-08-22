# Training Engineering: Mixed Precision, Gradient Accumulation and Clipping, Checkpointing, Determinism, and Debugging NaNs

> **Track:** T04 Deep Learning · **Time:** 2.5h · **Prereqs:** T04-optimization · **Updated:** 2026-08-03
> **Module id:** `T04-training-engineering` · **Tags:** training, critical
> **Lab:** `labs/python/06-training-engineering/`

## The 30-second version

Mixed precision training runs the forward/backward pass in a 16-bit format (bf16 or fp16) while keeping a full-precision fp32 copy of the weights for the optimizer update, buying roughly 2x memory reduction and 2-4x compute throughput on tensor-core hardware; bf16 (8 exponent bits, matching fp32's dynamic range of roughly `1.2e-38` to `3.4e38`, but only 7 mantissa bits) needs no loss scaling and is the default on Ampere-or-newer GPUs, while fp16 (5 exponent bits, a much narrower range of roughly `6.1e-5` to `65504`, but 10 mantissa bits) requires dynamic loss scaling — multiplying the loss by a large factor before backward so small gradients don't underflow to zero in fp16's narrow range, then dividing the resulting gradients back down before the optimizer step, with the scale factor increased when no overflow occurs and immediately halved when one does. Gradient accumulation splits one large logical batch into `N` smaller micro-batches, running forward/backward on each without an optimizer step, dividing the loss by `N` before each backward so the accumulated gradient equals the true average over the full logical batch, then calling `optimizer.step()` once every `N` micro-batches — forgetting the division by `N` is the single most common bug, silently scaling the effective learning rate by `N`. Gradient clipping (typically clip-by-norm at a threshold around `1.0`-`5.0`: if `‖g‖ > max_norm`, rescale `g ← g · max_norm/‖g‖`) is a purely reactive safety net against exploding gradients, applied after the full gradient is computed and before the optimizer step. "Checkpointing" means two different things that are frequently confused: model/optimizer-state checkpointing to disk (for fault-tolerant resume after a crash — checkpoint frequency trades wasted recompute-on-failure against I/O overhead) and *activation* (gradient) checkpointing, which discards intermediate activations during the forward pass and recomputes them during backward instead of storing them, cutting peak activation memory from `O(L)` to roughly `O(√L)` for an `L`-layer network at the cost of about one extra forward pass's worth of compute. Determinism (bit-for-bit reproducible runs) requires fixing every source of randomness (Python's, NumPy's, PyTorch's CPU and CUDA RNGs) *and* disabling nondeterministic GPU kernels (some cuDNN algorithms and atomic-add-based reductions have run-to-run nondeterministic floating-point summation order), which is a genuine speed-versus-reproducibility tradeoff, not a free correctness fix. Debugging a `nan` loss means finding the *first* operation that produced it (via `torch.autograd.set_detect_anomaly(True)` during debugging, never in production, since it's substantially slower) among the standard suspects: fp16 overflow without loss scaling, `log(0)` from an unstabilized softmax, or a learning rate too high combined with the exploding-gradient mechanics derived in `T04-backprop-derivation` — and once a `nan` exists anywhere in a computation, it propagates through essentially every subsequent arithmetic operation, so gradient clipping applied *after* a `nan` has already appeared cannot fix it; clipping only prevents a *finite* gradient from being too large, it cannot rescale an already-infinite or `nan` one.

## Why this gets asked

Because these are the exact skills that separate "can write a training loop" from "can actually run a multi-day, multi-GPU training job to completion without it silently corrupting itself or crashing at 2am with no idea why," and every one of them is something a production ML engineer has personally been paged for. Interviewers ask this because tutorial-level PyTorch code almost never demonstrates gradient accumulation, clipping, or determinism controls, so whether a candidate has actually operated real training infrastructure (versus only ever running short, single-GPU, small-batch experiments) shows up immediately in how specifically they can answer "your loss just went to nan at step 4000, walk me through what you check first."

---

## Lineage: past → present → future

**What came before.** Early deep learning training ran entirely in fp32, the default numeric format with no special handling — straightforward, but memory- and compute-expensive relative to what became possible once GPU hardware added dedicated low-precision matrix-multiply hardware (Tensor Cores, introduced with Volta in 2017, covered in `T16-gpu-arch`). Early attempts at reduced-precision training used fp16 directly and ran into a specific, well-documented failure: many real gradients are small in magnitude and simply underflow to exactly zero in fp16's narrow dynamic range (`~6e-5` to `65504`), silently discarding a meaningful fraction of the gradient signal with no visible error — this is the exact pain that loss scaling (multiply the loss by a large constant before backward, so small gradients get shifted into fp16's representable range, then divide the resulting gradients back down before the optimizer step) was invented to solve, first as a manually-tuned static scale factor, then as an automatically-adjusted dynamic one.

**Where it stands now.** bf16 (Google's "Brain Floating Point," matching fp32's exponent range but with fewer mantissa bits) has displaced fp16 as the default the moment hardware support landed broadly (Ampere generation, 2020) precisely because it needs no loss scaling at all — its dynamic range matches fp32's, so the underflow problem that motivated loss scaling in the first place doesn't occur, at the cost of somewhat less precision per value (7 mantissa bits versus fp16's 10) which has not shown a measurable quality regression in modern training recipes. Gradient accumulation and clipping are both now completely standard, near-universal practice, not a live debate — every serious training framework (PyTorch's native loop, Hugging Face `Trainer`, DeepSpeed, Megatron) implements both by default or as a one-line configuration option. FP8 training (further reduced precision, requiring more careful per-tensor/per-channel scaling recipes) is real and increasingly used for the largest 2025-2026 training runs on newer hardware, but is a meaningfully more delicate recipe than bf16 and not yet the default the way bf16 is. Activation/gradient checkpointing is universal practice for any model whose activations don't comfortably fit in available GPU memory at the desired batch size — the tradeoff (recompute cost for memory savings) is well understood and tunable per-layer in most frameworks.

**Where it's heading.** Precision continues to push downward for the largest training runs (fp8 today, active research into sub-8-bit formats), with the driving cost function unchanged from bf16's own story: memory and compute savings, with the *complexity of the numerics recipe needed to make it safe* (scaling strategies, calibration, which operations can tolerate the reduced precision and which cannot) rising correspondingly. Determinism and debuggability tooling continues to mature alongside larger and larger distributed training runs (`T04-distributed-training`), where a nondeterministic or silently-corrupting failure becomes proportionally more expensive to diagnose the more GPU-hours are burned before it's noticed — better anomaly detection, automatic checkpoint-and-resume infrastructure, and more granular activation/gradient inspection tooling are all active, ongoing engineering investment areas rather than a solved problem, precisely because failures at the largest scales (multi-thousand-GPU runs) are enormously expensive per hour of undetected corruption.

---

## Mental model

```
MIXED PRECISION:
  fp32 MASTER weights (kept for optimizer precision)
    |  cast down
    v
  bf16/fp16 forward + backward (2x less memory, 2-4x tensor-core throughput)
    |
    v  (fp16 ONLY: multiply loss by scale S before backward, so small
    |   gradients don't underflow fp16's narrow range; divide grads by S after)
  gradients -> cast back to fp32 -> optimizer step updates the fp32 MASTER copy

  bf16 range ~= fp32 range (8 exponent bits) -> NO loss scaling needed
  fp16 range MUCH narrower (5 exponent bits: ~6e-5 to 65504) -> loss scaling REQUIRED

GRADIENT ACCUMULATION (simulate a big batch from small micro-batches):
  micro-batch 1 -> loss/N -> backward (accumulate, no step)
  micro-batch 2 -> loss/N -> backward (accumulate, no step)
       ...
  micro-batch N -> loss/N -> backward (accumulate) -> optimizer.step() -> zero_grad()
  FORGET the /N  ==  effective learning rate silently multiplied by N

GRADIENT CLIPPING (reactive safety net, AFTER full gradient computed):
  if ||g|| > max_norm:  g <- g * (max_norm / ||g||)      <- rescale, don't zero

CHECKPOINTING -- TWO DIFFERENT THINGS:
  (1) MODEL checkpointing: save weights+optimizer state to DISK periodically
      for fault-tolerant resume after a crash
  (2) ACTIVATION (gradient) checkpointing: DON'T store all activations in
      MEMORY during forward -- recompute them during backward instead
      L layers, all stored: O(L) memory
      sqrt(L) checkpoints kept, rest recomputed: O(sqrt(L)) memory,
        ~1 extra forward pass of compute

DETERMINISM: fix EVERY RNG (python, numpy, torch CPU+CUDA) AND disable
  nondeterministic GPU kernels (some cuDNN algorithms, atomic-add reduction
  order) -- genuine speed/reproducibility TRADEOFF, not a free fix

NAN DEBUGGING: nan PROPAGATES through nearly all arithmetic once it exists
  -> clipping AFTER a nan exists does nothing (can't rescale infinity/nan)
  -> find the FIRST op that produced it (set_detect_anomaly, DEBUG ONLY)
```

The one-line mental model: **training engineering is entirely about making the mathematically-correct algorithm from the previous modules survive contact with finite-precision hardware, distributed/interrupted execution, and multi-day wall-clock runtimes — none of it changes what the model computes, all of it changes whether the run finishes correctly at all.**

---

## How it actually works

### Mixed precision: the actual number formats, and why loss scaling is fp16-specific

Every floating-point format trades off *range* (how large/small a magnitude it can represent, controlled by exponent bits) against *precision* (how finely it distinguishes values within that range, controlled by mantissa bits). `fp32`: 8 exponent bits, 23 mantissa bits, range roughly `1.2e-38` to `3.4e38`. `fp16`: 5 exponent bits, 10 mantissa bits, range roughly `6.1e-5` to `65504` — a dramatically narrower range than fp32, meaning gradients that are small in magnitude (common, especially with the vanishing-gradient dynamics from `T04-backprop-derivation`) can underflow to exactly zero. `bf16`: 8 exponent bits (identical to fp32), only 7 mantissa bits, range matching fp32's roughly `1.2e-38` to `3.4e38` — because its exponent range matches fp32, the same values that would underflow in fp16 remain representable (just at reduced precision) in bf16, which is exactly why bf16 needs no loss scaling while fp16 does. **Dynamic loss scaling**: multiply the loss by a scale factor `S` (commonly starting around `2^16` or higher) before calling `.backward()` — every gradient in the resulting backward pass is proportionally scaled up by the same `S`, shifting small gradients into fp16's representable range — then divide the actual gradients by `S` before the optimizer step (recovering the correct, unscaled gradient magnitude). The scale factor is adjusted dynamically: increased (e.g., doubled) after a run of steps with no overflow (to use as much of fp16's range as safely possible), and immediately decreased (e.g., halved) the moment an overflow (`inf`/`nan` in the scaled gradients) is detected, with that step's update skipped entirely.

### Gradient accumulation: the division that must not be forgotten

To simulate a logical batch size of `micro_batch_size × N` using `N` micro-batches (e.g., because the full batch doesn't fit in GPU memory at once): for each of the `N` micro-batches, compute the loss, **divide it by `N`**, and call `.backward()` (accumulating gradients via the `+=` rule from `T04-autograd`, without calling `optimizer.step()` or `zero_grad()` yet) — only after all `N` micro-batches have contributed does `optimizer.step()` run, followed by `zero_grad()`. The division by `N` is what makes the accumulated gradient equal the *average* gradient over the full logical batch (matching what a single true large-batch forward/backward would have produced), rather than the *sum* over `N` micro-batches, which would be `N` times too large — and since gradient magnitude directly determines the size of the optimizer step, an accidentally `N`-times-too-large gradient behaves exactly like training with a learning rate multiplied by `N`, a subtle, easy-to-miss bug that doesn't crash but silently changes training dynamics (often destabilizing training or converging to a worse result, depending on how large `N` is).

### Gradient clipping: rescaling, not zeroing, and why it's purely reactive

Clip-by-norm computes the global norm of the *entire* gradient vector (concatenating every parameter's gradient into one conceptual vector and computing its L2 norm), and if that norm exceeds a threshold `max_norm` (commonly `1.0` for transformer training, sometimes higher), rescales **every** component of the gradient by the same factor `max_norm/‖g‖` — this preserves the gradient's *direction* exactly, only shrinking its magnitude, which is why it's clipping (a rescale) rather than truncation (which would distort direction by capping individual components independently). Because it operates on the *already-computed* full gradient, right before the optimizer step, clipping is purely reactive: it cannot influence why a gradient got large in the first place (bad initialization, too-high learning rate, an architectural instability), it only prevents that one step's update from being astronomically large — which is exactly why it's standard practice for RNN/LSTM and transformer training in particular (both prone to occasional large gradient spikes) but is not, by itself, a substitute for addressing the root cause of persistent instability.

### Model checkpointing versus activation checkpointing: two unrelated uses of the same word

**Model checkpointing** means periodically saving the model's weights, optimizer state, and training progress (step count, learning-rate-schedule state, RNG state for determinism) to persistent storage, so a crashed or preempted training run can resume from the last checkpoint instead of restarting from scratch — the design tradeoff is checkpoint frequency: more frequent checkpoints bound the amount of wasted compute on failure (less recomputation needed) but cost more I/O time and storage; the choice depends on expected failure rate (spot/preemptible instances need much more frequent checkpointing than reliable dedicated hardware) and the cost of a checkpoint write relative to a training step's cost.

**Activation checkpointing** (also called "gradient checkpointing," an unfortunately overloaded term with the previous concept) is an entirely different, memory-versus-compute tradeoff *within* a single training step: normally, every layer's activations must be kept in memory from the forward pass until that layer's backward pass runs (per the outer-product weight-gradient formula from `T04-backprop-derivation`, which needs the layer's input) — for an `L`-layer network, this is `O(L)` memory. Activation checkpointing instead stores only a subset of activations (commonly at roughly `√L` evenly-spaced points, following Chen et al.'s 2016 "sublinear memory cost" analysis), and *recomputes* the discarded activations by re-running the forward pass for that segment during backward, when they're actually needed — this reduces peak activation memory to roughly `O(√L)` at the cost of an extra forward pass's worth of compute for the recomputed segments (informally, roughly one additional forward pass on top of the normal one-forward-plus-one-backward cost, so total compute for that portion increases by something in the neighborhood of 30-50% depending on exactly which segments are recomputed) — a very favorable trade when memory, not compute, is the binding constraint, which is the common case for large models on fixed GPU memory.

### Determinism: what actually has to be controlled

Bit-for-bit reproducible training requires controlling every independent source of randomness and every source of run-to-run floating-point variation: (1) seed Python's own `random`, NumPy's RNG, and PyTorch's CPU *and* CUDA RNGs separately (they are independent generators, and missing any one leaves that piece nondeterministic); (2) disable nondeterministic GPU algorithm selection — some cuDNN convolution algorithms are chosen based on a runtime benchmark of what's fastest on the current hardware/input shape (`cudnn.benchmark=True`, which is itself nondeterministic across runs since it can pick different algorithms), and some GPU reduction operations (e.g., certain atomic-add-based accumulation patterns) sum floating-point values in a run-to-run-varying order, and floating-point addition is not associative (`(a+b)+c` is not always bit-identical to `a+(b+c)`) so the result can differ in the last bits run to run; `torch.use_deterministic_algorithms(True)` forces PyTorch to use only deterministic kernel implementations where available (raising an error for operations with no deterministic implementation), typically at some real performance cost; (3) fix data loading order (disable multi-worker `DataLoader` shuffling nondeterminism, or seed each worker deterministically). This is a genuine, real tradeoff — deterministic kernels are frequently measurably slower than their nondeterministic, more-optimized counterparts — which is why determinism is turned on deliberately for debugging/compliance/reproducibility-critical work, not left on by default for maximum-throughput production training.

### Debugging a `nan` loss: the propagation property and the standard suspects

Once a `nan` exists anywhere in a computation, it propagates through nearly every subsequent arithmetic operation (`nan + x = nan`, `nan * x = nan` for any `x`, including `x=0`) — this is exactly why gradient clipping cannot fix a `nan` gradient: clipping computes `max_norm/‖g‖`, but `‖g‖` is itself `nan` if any component is, and any rescaling of a `nan` value is still `nan`. The standard, checkable causes, in rough order of frequency: **fp16 overflow** (a gradient or activation exceeded fp16's `65504` maximum, producing `inf`, then `inf - inf` or similar producing `nan` somewhere downstream) — check whether loss scaling is enabled and functioning, or switch to bf16 if hardware supports it; **unstabilized softmax/log** (`log(0)` from a probability that rounded to exactly zero, most commonly from a hand-rolled softmax without the max-subtraction trick from `T04-neural-net-math`) — verify any custom probability/log computation uses a numerically stable formulation; **learning rate too high combined with exploding gradients** (per `T04-backprop-derivation`'s derivation) producing an update so large the resulting weights themselves become `inf` or `nan` on the very next forward pass; and **bad input data** (an `inf` or `nan` already present in the input batch, from a data pipeline bug, silently poisoning everything downstream from the first forward pass). `torch.autograd.set_detect_anomaly(True)` makes PyTorch raise an error at the exact backward operation that first produces a `nan`/`inf` gradient (rather than letting it silently propagate and surface many operations later, far from its actual origin), which is invaluable for localizing the bug but adds substantial overhead — enable it only while actively debugging, never in a production training run.

---

## Build it from scratch

```python
# untested sketch -- illustrates the gradient-accumulation division and clip-by-norm,
# the two mechanics most commonly implemented (or broken) by hand
def train_step_with_accumulation(model, optimizer, micro_batches, clip_norm=1.0):
    optimizer.zero_grad()
    N = len(micro_batches)
    for x, y in micro_batches:
        loss = compute_loss(model(x), y) / N     # <-- the division that must not be forgotten
        loss.backward()                           # accumulates via autograd's += rule
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=clip_norm)  # rescale, not zero
    optimizer.step()

def manual_clip_by_norm(grads, max_norm=1.0):
    total_norm = sum((g ** 2).sum() for g in grads) ** 0.5
    if total_norm > max_norm:
        scale = max_norm / total_norm
        grads = [g * scale for g in grads]        # SAME scale applied to every gradient
    return grads
```
Reproducing dynamic loss scaling's increase-on-success/halve-on-overflow logic from scratch, and instrumenting a deliberately-broken training loop (a hand-rolled unstabilized softmax, or a forgotten `/N` in accumulation) to observe exactly how and where it produces `nan`, using `torch.autograd.set_detect_anomaly(True)` to localize it, is the lab exercise in `labs/python/06-training-engineering/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Loss becomes `nan` within the first few hundred steps, model was working in an earlier fp32 run | Switched to fp16 without loss scaling, or loss scaling isn't actually engaging (e.g. a custom training loop that forgot to check the scaler's `.step()`/overflow logic) | Confirm dynamic loss scaling is active and its scale factor is being reduced on overflow (visible in most framework logs); consider switching to bf16 if hardware supports it, removing the need for loss scaling entirely |
| Training behaves as if the learning rate is much higher than configured after enabling gradient accumulation | Forgot to divide the loss by the number of accumulation micro-batches before `.backward()` | Divide loss by the accumulation step count before every backward call, or use a framework's built-in accumulation helper (e.g. Hugging Face `Trainer`'s `gradient_accumulation_steps`) which handles this correctly |
| Training run crashes on a preemptible/spot instance and loses several hours of progress | Model checkpointing interval too infrequent relative to the instance's actual preemption/failure rate | Increase checkpoint frequency (balanced against I/O cost) to match observed failure rate; on genuinely unreliable hardware, more frequent, cheaper checkpoints usually beat rare, expensive ones |
| Model runs out of GPU memory at a batch size that should comfortably fit based on parameter count alone | Activation memory (not parameter or optimizer-state memory) dominates at that batch size/sequence length, and no activation checkpointing is in use | Enable activation/gradient checkpointing (commonly `torch.utils.checkpoint` or a framework-level flag) to trade the extra recompute cost for the memory headroom needed |
| Two runs with identical code and hyperparameters produce measurably different final metrics | An uncontrolled source of nondeterminism (unseeded RNG, `cudnn.benchmark=True` picking different algorithms, nondeterministic reduction order) | Set all RNG seeds explicitly, call `torch.use_deterministic_algorithms(True)`, disable `cudnn.benchmark`, and fix data loading order — accepting the resulting performance cost as the price of genuine reproducibility |

---

## Tradeoffs & when NOT to use it

- **Don't default to fp16 over bf16 on hardware that supports bf16.** fp16's extra mantissa precision (10 bits vs bf16's 7) is rarely the deciding factor in practice, while its narrow dynamic range's loss-scaling requirement adds real operational complexity (tuning/monitoring the scale factor, occasional skipped steps on overflow) that bf16 simply doesn't need — reach for fp16 specifically when targeting older hardware (Volta/Turing) without bf16 support.
- **Don't enable activation checkpointing everywhere reflexively.** It's a real compute-for-memory trade — applying it to layers whose activations are cheap to store anyway wastes compute for no benefit; apply it selectively to the memory-dominant portions of a model (commonly the largest/most repeated blocks) rather than blanket-wrapping every layer.
- **Don't leave `torch.autograd.set_detect_anomaly(True)` enabled in production training.** It adds substantial per-step overhead by tracking additional bookkeeping to localize exactly which operation produces a `nan`/`inf` — invaluable for a debugging session, a real and unnecessary tax on every step of a healthy production run.
- **Don't treat gradient clipping as sufficient protection against training instability on its own.** It's a real, cheap safety net against occasional large gradient spikes, but persistent, repeated clipping at nearly every step is a symptom that the actual root cause (learning rate, initialization, architecture) needs fixing, not evidence that clipping is "handling it" — check how often clipping actually triggers, not just whether it's enabled.
- **Don't insist on full bit-for-bit determinism for routine, non-compliance-critical training runs.** The performance cost of deterministic kernels is real and, for most day-to-day experimentation, not worth paying — reserve strict determinism for the specific runs where exact reproducibility (regulatory compliance, precise A/B comparison, debugging a suspected numerics bug) is actually the point.

---

## Interview questions

### Q1 — Why does bf16 not need loss scaling while fp16 does?
**Testing:** the actual numeric-format reason, not "bf16 is just better."
**Answer:** fp16 has only 5 exponent bits, giving a narrow representable range (roughly `6.1e-5` to `65504`) that many real, legitimately-small gradients underflow below, silently becoming exactly zero. bf16 has 8 exponent bits — the same as fp32 — giving it fp32's dynamic range (roughly `1.2e-38` to `3.4e38`), so the same small gradient values that would underflow in fp16 remain representable (at reduced precision, since bf16 only has 7 mantissa bits) in bf16, removing the underflow problem loss scaling exists to work around.
**Follow-up trap:** *"If bf16 has fewer mantissa bits than fp16 (7 vs 10), doesn't that mean it's less precise, and shouldn't that hurt training quality?"* — in principle yes, less precision per value, but empirically modern training recipes show no measurable quality regression from bf16 versus fp32, because the *relative* precision loss (mantissa bits) matters less for training stability than avoiding *catastrophic* underflow (losing a gradient entirely to zero) — a small precision loss on many values is a much gentler failure mode than complete information loss on some values.

### Q2 — Walk through dynamic loss scaling: what does it do at each step, and why divide the gradient back down after backward rather than before?
**Testing:** the actual mechanics, not just "it scales the loss up."
**Answer:** Multiply the loss by scale factor `S` before `.backward()` — since gradients are linear in the loss, every resulting gradient is also scaled by `S`, shifting small gradients up into fp16's representable range before they'd otherwise underflow. After backward, divide the computed gradients by `S` to recover the true, correctly-scaled gradient before the optimizer step uses it. `S` is increased (e.g. doubled) after a run of overflow-free steps, and immediately halved (with that step's update skipped) the moment an overflow occurs.
**Follow-up trap:** *"What would happen if you scaled the loss but forgot to divide gradients back down before the optimizer step?"* — every parameter update would be `S` times too large, exactly equivalent to training with a learning rate multiplied by `S` (often an enormous, destabilizing factor, e.g. `2^16`), almost certainly diverging training immediately.

### Q3 — You enable gradient accumulation with 8 micro-batches but training seems to have become unstable at a much higher effective learning rate than before. What's the most likely bug?
**Testing:** the specific, common accumulation bug, not a vague "something about accumulation."
**Answer:** Forgetting to divide the loss by the number of micro-batches (8, here) before each `.backward()` call — without that division, the accumulated gradient is the *sum* over 8 micro-batches rather than their *average*, roughly 8x too large, which behaves exactly like training with an 8x higher learning rate.
**Follow-up trap:** *"Why does dividing the loss (rather than dividing the final accumulated gradient once, after all 8 micro-batches) achieve the same correct result?"* — gradients are linear in the loss (by the chain rule), so dividing each micro-batch's loss by 8 before backward divides that micro-batch's contribution to the accumulated gradient by 8 as well — summing 8 such already-divided contributions gives exactly the same result as summing the 8 undivided contributions and dividing the total by 8 once at the end; both are mathematically equivalent, and frameworks typically implement the per-micro-batch division for simplicity.

### Q4 — What does gradient clipping actually do to the gradient vector, and why is it described as "reactive"?
**Testing:** clip-by-norm's precise mechanism, not "clipping caps big gradients."
**Answer:** Clip-by-norm computes the L2 norm of the entire (concatenated, across all parameters) gradient vector, and if it exceeds `max_norm`, rescales *every component* of the gradient by the same factor `max_norm/‖g‖` — this preserves the gradient's direction exactly while shrinking only its magnitude. It's reactive because it operates on the already-fully-computed gradient right before the optimizer step, with no ability to influence or address why the gradient became large in the first place (a too-high learning rate, poor initialization, or an architectural instability from `T04-backprop-derivation`).
**Follow-up trap:** *"If a training run is clipping the gradient at nearly every single step, is that a healthy sign that clipping is 'doing its job'?"* — no, that's a red flag that something upstream (learning rate too high, an unstable architecture, insufficient normalization) needs fixing — clipping should be an occasional safety net for rare spikes, not a mechanism the run depends on at nearly every step to avoid diverging.

### Q5 — Distinguish model checkpointing from activation (gradient) checkpointing — same word, two unrelated concepts. What problem does each solve?
**Testing:** whether the overloaded terminology is correctly disambiguated, a very common point of confusion.
**Answer:** Model checkpointing periodically saves weights/optimizer state/training progress to disk, solving fault tolerance — so a crashed or preempted run can resume instead of restarting. Activation checkpointing is a within-single-step memory-versus-compute tradeoff: instead of keeping every layer's activations in memory from forward until that layer's backward runs (`O(L)` memory for `L` layers), it stores only a subset (roughly `√L` checkpoints) and recomputes the rest during backward, reducing peak memory to roughly `O(√L)` at the cost of an extra forward pass's worth of compute.
**Follow-up trap:** *"If you're running on reliable, non-preemptible hardware with plenty of GPU memory, do you still need either?"* — model checkpointing remains valuable for any run long enough that *some* failure (hardware, software, human error) becomes likely over its duration, regardless of preemption; activation checkpointing is genuinely optional if memory isn't the binding constraint — enabling it anyway would trade away compute for memory savings you don't need, a real (if usually small) unnecessary cost.

### Q6 — Why does `torch.autograd.set_detect_anomaly(True)` help localize a `nan`, and why shouldn't it be left on for production training?
**Testing:** understanding the propagation property and the debugging-vs-production tradeoff.
**Answer:** Once a `nan` exists, it propagates through nearly all subsequent arithmetic, so by the time a `nan` loss is observed, the operation that actually *produced* it may be many layers/operations upstream and non-obvious from the final symptom alone. `set_detect_anomaly(True)` makes PyTorch raise an error immediately at the exact backward operation that first produces a `nan`/`inf` gradient, precisely localizing the bug's origin instead of its downstream symptom. It shouldn't stay on in production because it adds substantial per-step tracking overhead to enable that localization, a real and unnecessary cost once the bug is found and fixed.
**Follow-up trap:** *"Why can't gradient clipping fix a nan gradient once one has appeared?"* — clipping computes `max_norm/‖g‖`, but `‖g‖` is itself `nan` if any component of `g` is `nan` (since `nan` propagates through the norm computation), and rescaling a `nan` value by any factor is still `nan` — clipping can only prevent a *finite* gradient from being disproportionately large, it has no mechanism to "repair" a value that's already `nan` or infinite.

### Q7 — What specifically makes floating-point reduction operations on GPU nondeterministic, and why can't you just "turn on determinism" for free?
**Testing:** the actual numerical-associativity argument, not "GPUs are just nondeterministic."
**Answer:** Some GPU reduction operations (summing many values, e.g. in certain atomic-add-based accumulation patterns) complete their additions in a run-to-run-varying order depending on which GPU threads finish first — and floating-point addition is not associative (`(a+b)+c` is not always bit-identical to `a+(b+c)` due to rounding at each step), so a different summation order can produce a bit-different (though numerically very close) result each run. Forcing determinism means using algorithm implementations with a fixed, guaranteed summation order, which are frequently less parallelizable/optimized than their nondeterministic counterparts, hence measurably slower — it's not "free" precisely because the nondeterministic versions are often nondeterministic *because* that flexibility in execution order is what makes them fast.
**Follow-up trap:** *"Besides GPU reduction order, name one other independent source of nondeterminism that must also be controlled for full reproducibility."* — any of: unseeded Python/NumPy/PyTorch-CPU/PyTorch-CUDA RNGs (four *separate* generators, all needing seeds), `cudnn.benchmark=True` selecting different convolution algorithms based on a runtime benchmark that can vary, or multi-worker `DataLoader` shuffling/ordering without a fixed, seeded per-worker RNG.

### Q8 — A model trains fine at batch size 8 but runs out of GPU memory at batch size 32, even though parameter count and optimizer state are obviously unaffected by batch size. What's the likely cause and fix?
**Testing:** connecting activation memory scaling directly to a concrete, common OOM scenario.
**Answer:** Activation memory (not parameter or optimizer-state memory, both of which are batch-size-independent) scales roughly linearly with batch size, since every layer's activations must be stored for every example in the batch until that layer's backward pass runs — at batch size 32, that's 4x the activation memory of batch size 8, which is very often the actual cause of an OOM that "should" fit based on parameter-count reasoning alone. The direct fix is enabling activation/gradient checkpointing to trade the extra recompute cost for reduced peak activation memory, or reducing batch size and compensating with gradient accumulation to reach the same effective logical batch size.
**Follow-up trap:** *"Why does gradient accumulation not have this same activation-memory problem, given it also processes more total examples per logical batch?"* — because each micro-batch's activations are stored, backpropagated, and then freed (their gradient contribution already accumulated into `.grad`) *before* the next micro-batch runs — at any given moment, only one micro-batch's worth of activation memory is live, regardless of how many micro-batches make up the full accumulation cycle, which is exactly why accumulation is the standard technique for simulating a large batch without paying that batch size's full activation-memory cost.

### Q9 — Why is "the loss randomly spiked to nan once at step 50,000 in an otherwise-healthy multi-day training run" a different debugging problem than "the loss goes to nan within the first 10 steps of every run"?
**Testing:** distinguishing systematic bugs from rare, tail-event instability, a real triage skill.
**Answer:** A `nan` within the first 10 steps of every run strongly suggests a systematic, reproducible bug — bad initialization scale, a genuinely broken custom operation (unstabilized softmax, a bug in a custom `autograd.Function`), or loss scaling not functioning at all — something wrong with the code or configuration itself, findable via `set_detect_anomaly` on a short reproduction. A single spike deep into an otherwise-healthy run is more consistent with a rare, tail-probability event: an unusually extreme batch of data (an outlier causing a momentarily huge gradient), a transient hardware issue, or the natural, occasional occurrence of gradient clipping's threshold being insufficient for one particular spike — the fix there is more often about resilience (checkpointing frequently enough to resume cleanly, possibly tightening gradient clipping or adding NaN-skipping logic to skip a single bad step) than about finding and fixing a single deterministic bug.
**Follow-up trap:** *"If you suspect the rare-spike case is caused by a specific bad batch of training data, how would you confirm that without re-running the entire multi-day job?"* — if a recent checkpoint and the exact data-loading order/seed are both available, resume from the last good checkpoint and replay just the batches leading up to the spike (a much shorter, targeted reproduction) rather than restarting the full run — this is exactly why deterministic data ordering and frequent-enough checkpointing both pay off specifically in this debugging scenario, beyond their fault-tolerance role.

### Q10 — Design question: you're training a large model on preemptible/spot GPU instances that can be reclaimed with only a few minutes' notice at any time. How does this change your checkpointing, precision, and determinism choices versus training on dedicated, reliable hardware?
**Testing:** staff-level synthesis connecting infrastructure constraints to the specific techniques in this module.
**Answer:** Checkpoint frequency should increase substantially relative to reliable hardware, since the expected time-to-preemption is much shorter and unpredictable — the cost of infrequent checkpoints (large recompute loss on preemption) is much higher here, favoring more frequent, ideally fast/incremental checkpoint writes even at some added I/O overhead. Precision choice (bf16 vs fp8) isn't directly changed by preemptibility itself, but the *speed* of resuming matters more, favoring fast checkpoint load as much as fast checkpoint save. Determinism (fixed seeds, deterministic data ordering) becomes more operationally valuable here specifically because it makes "resume from checkpoint N and verify you get the same trajectory as an uninterrupted run would have" a checkable property, which is a genuinely useful correctness check on a training pipeline that gets interrupted and resumed far more often than one running on stable hardware.
**Follow-up trap:** *"Would you enable torch.use_deterministic_algorithms(True) for this entire training run, given how much resume/interruption is happening?"* — probably not for the entire run by default, since its throughput cost compounds over the full training duration, which is likely still the dominant cost driver even with frequent interruptions — more targeted: use deterministic settings for a short validation run confirming resume-correctness after setting up the pipeline, then run the actual full-scale training with standard (faster, non-strictly-deterministic) settings, accepting that exact bit-for-bit resume verification isn't continuously checked during the real run, only validated once as a pipeline-correctness test.

---

## Red flags that fail you

- Doesn't know why bf16 needs no loss scaling while fp16 does, or can't state either format's exponent/mantissa bit split.
- Forgets (or doesn't know to check for) the loss-division-by-N bug in gradient accumulation.
- Describes gradient clipping as "preventing nan" rather than rescaling an already-finite, too-large gradient.
- Confuses model checkpointing (fault tolerance, disk) with activation checkpointing (memory-compute tradeoff, within one step).
- Thinks gradient clipping can fix a nan gradient after the fact.
- Believes "using a fixed random seed" alone is sufficient for full training-run determinism.

---

## Cheat card

```
PRECISION: fp32 (8exp,23mant, ~1.2e-38 to 3.4e38) MASTER weights kept always
  bf16 (8exp,7mant, SAME range as fp32) -> NO loss scaling needed, Ampere+ default
  fp16 (5exp,10mant, ~6.1e-5 to 65504, NARROW) -> loss scaling REQUIRED
  loss scaling: loss*S before backward -> grads/S after -> optimizer step
    S doubles on N clean steps, HALVES + skip step on overflow

GRAD ACCUMULATION: for N micro-batches: loss = compute_loss(...)/N; loss.backward()
  (accumulate via autograd += rule) ... after N: optimizer.step(); zero_grad()
  FORGET the /N -> gradient N-times too large -> effective LR x N (silent bug)

GRAD CLIPPING (reactive, AFTER full grad computed):
  if ||g|| > max_norm: g *= max_norm/||g||   <- rescales ALL components equally,
  preserves direction. Frequent clipping every step = root-cause problem, not
  "clipping doing its job"

CHECKPOINTING -- 2 UNRELATED MEANINGS:
  MODEL checkpoint: save weights+optimizer+step state to DISK -> fault tolerance
    on crash/preemption; more frequent = less wasted recompute, more I/O cost
  ACTIVATION checkpoint: DON'T store all L layers' activations (O(L) mem) ->
    keep ~sqrt(L) checkpoints, RECOMPUTE rest during backward -> O(sqrt(L)) mem,
    ~+1 extra forward pass of compute (Chen et al. 2016)

DETERMINISM: seed python+numpy+torch-CPU+torch-CUDA (4 SEPARATE RNGs) AND
  disable cudnn.benchmark, use_deterministic_algorithms(True), fix dataloader
  order -- floating point add is NOT associative -> GPU reduction order varies
  run-to-run -> real SPEED cost, not a free correctness fix

NAN DEBUGGING: nan PROPAGATES through nearly all arithmetic once it exists
  clipping CANNOT fix nan (||g|| itself becomes nan, any rescale of nan = nan)
  causes (freq order): fp16 overflow (no/broken loss scaling), unstabilized
    softmax log(0), LR too high -> exploding grads (T04-backprop-derivation),
    bad/inf input data
  set_detect_anomaly(True): finds FIRST op producing nan -- DEBUG ONLY, slow,
    never in production
```

## Sources

- [Mixed Precision Training — Micikevicius et al. (2017)](https://arxiv.org/abs/1710.03740) — accessed 2026-08-03
- [Training and inference of large language models using 8-bit floating point — arXiv (FP8)](https://arxiv.org/pdf/2309.17224) — accessed 2026-08-03
- [Training Deep Nets with Sublinear Memory Cost — Chen et al. (2016)](https://arxiv.org/abs/1604.06174) — accessed 2026-08-03
- [torch.utils.checkpoint — PyTorch documentation](https://docs.pytorch.org/docs/stable/checkpoint.html) — accessed 2026-08-03
- [Reproducibility — PyTorch documentation (determinism notes)](https://docs.pytorch.org/docs/stable/notes/randomness.html) — accessed 2026-08-03
- [Automatic Mixed Precision package — torch.amp documentation](https://docs.pytorch.org/docs/stable/amp.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
