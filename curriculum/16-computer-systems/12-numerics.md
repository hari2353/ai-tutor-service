# IEEE-754, Float Pitfalls, and bf16/fp16/fp8 in ML

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 1.5h · **Prereqs:** T16-assembly · **Updated:** 2026-08-03
> **Module id:** `T16-numerics` · **Tags:** numerics

## The 30-second version

IEEE-754 represents a float as sign, exponent, and mantissa (fp32: 1+8+23 bits), storing numbers as `(-1)^sign × 1.mantissa × 2^(exponent-bias)` — this means fractions like 0.1 that are exact in decimal are *not* exact in binary (0.1 is a repeating binary fraction, like 1/3 in decimal), which is why `0.1 + 0.2 == 0.30000000000000004` in every IEEE-754 language: both operands are already rounded to the nearest representable float before addition even happens, and the sum rounds again. The much more dangerous failure mode is **catastrophic cancellation** — subtracting two nearly-equal floats destroys most of the significant digits, amplifying whatever rounding error was already present in the inputs by orders of magnitude, and it happens regardless of whether the numbers are large or small; a documented example computed a graphics cross-product in `float32` and got integers off by nearly 20% from the `float64` answer purely from this effect. In ML, the industry has converged on trading mantissa precision for dynamic range at training time: `bf16` (1+8+7 bits) matches fp32's exponent range exactly (so it can't overflow/underflow the way fp16 does) but only gives ~2-3 decimal digits of precision, while `fp16` (1+5+10 bits) has more mantissa precision but a much smaller exponent range (max ~65,504) that routinely overflows large-model gradients, which is exactly why fp16 training needs explicit loss scaling and bf16 usually doesn't. `fp8` (two flavors: E4M3 for weights/activations needing precision, E5M2 for gradients needing range) pushes this further for inference and increasingly training, halving memory and bandwidth again versus bf16 at the cost of needing per-tensor scaling factors instead of one global scale factor, because 2-3 mantissa bits leaves almost no margin for error.

## Why this gets asked

Because floating point is the single most common source of "this bug only happens in production, with real data, and I can't reproduce it locally" reports, and because the ML industry's entire cost/throughput story for training and serving large models is built on choosing the right numeric format for the right tensor — getting this wrong either silently corrupts a model (NaN loss halfway through a multi-week training run, a catastrophic and expensive failure) or leaves real throughput on the table by using a higher-precision format than the workload needs. An interviewer testing this wants to know you understand *why* `0.1 + 0.2 != 0.3` at the representation level (not just that it's true), that you can reason about when floating-point error actually matters (accumulating sums, ill-conditioned subtraction) versus when it's irrelevant noise, and that you know the concrete tradeoffs behind bf16 vs fp16 vs fp8 rather than treating them as interchangeable "smaller float" options.

---

## Lineage: past → present → future

**What came before.** Before IEEE-754 (1985), floating-point implementations were vendor-specific and mutually incompatible — different exponent widths, different rounding behaviors, different (or absent) handling of overflow and division by zero, meaning a numerical program's results could differ meaningfully across machines from different manufacturers, and there was no standard way to reason about how much error a computation had accumulated. The pain this caused was concrete: numerical software couldn't be trusted to be portable, and there was no shared vocabulary (or hardware-guaranteed behavior) for edge cases like "what happens at overflow" or "how does the hardware round a result that doesn't fit exactly." William Kahan led the effort (largely at Intel, for the 8087 coprocessor) to standardize this, and IEEE-754-1985 defined exact bit layouts for single (32-bit) and double (64-bit) precision, a single required rounding mode (round-to-nearest-even) as default, and crucially, well-defined special values (`+inf`, `-inf`, `NaN`, signed zero) so that operations like `1.0/0.0` had one universally agreed-upon, non-crashing answer instead of undefined or platform-specific behavior.

**Where it stands now.** IEEE-754 (revised 2008, 2019) is essentially universal — every mainstream CPU's hardware floating-point unit implements it, and "the same arithmetic expression can give bit-different results on different hardware" is now a much narrower concern (mostly about fused-multiply-add availability and compiler reassociation under aggressive optimization flags, not the base representation). The live disagreement in 2026 is not about IEEE-754's correctness but about *which reduced-precision format* is the right default for which part of an ML pipeline: `fp16` was NVIDIA's first mainstream reduced-precision training format (Volta-era Tensor Cores, ~2017) but its narrow exponent range caused real production pain (gradient overflow requiring manual loss-scaling tuning), which is exactly the problem Google's `bfloat16` (matching fp32's exponent range, truncating mantissa instead) was designed to solve for TPU training and has since become the de facto default for large-model training across most modern accelerators. `fp8` (two IEEE-adjacent variants, E4M3 and E5M2, standardized jointly by NVIDIA/ARM/Intel in 2022) is the current frontier for both inference and increasingly training on the newest hardware generations (Hopper/Blackwell-class GPUs), and its real deployment story is that it needs per-tensor or even per-block scaling factors (not one global loss scale) because 2-3 mantissa bits leave far less margin for representation error than bf16's already-thin 7 bits.

**Where it's heading.** Sub-8-bit formats (fp4, various microscaling/block-floating-point schemes like MX formats standardized by the Open Compute Project) are actively being explored for both training and inference on the newest accelerator generations, with real but still-maturing production adoption — the open engineering question is how much accuracy degradation is recoverable through better scaling/calibration techniques (per-block scale factors, stochastic rounding) versus fundamental representation limits, and this is genuinely unresolved for training (versus inference, where sub-8-bit quantization is comparatively mature and widely deployed today). Expect continued format proliferation at the hardware level for the next several years rather than convergence on one "final" reduced-precision standard, because training and inference have different accuracy/throughput tradeoff curves and different parts of a model (weights vs. activations vs. gradients vs. optimizer state) tolerate precision loss differently.

---

## Mental model

```
IEEE-754 float32 layout (32 bits total):

 [S][ E E E E E E E E ][ M M M M M M M M M M M M M M M M M M M M M M M ]
  1        8 bits                        23 bits
 sign    exponent                        mantissa (fraction)
         (biased by 127)

value = (-1)^S x 1.M x 2^(E - 127)      (for "normal" numbers)

Compare formats by exponent/mantissa split -- this split IS the whole story:

format   sign  exp  mantissa   range                    precision
-------------------------------------------------------------------------
fp32       1    8      23      ~1e-38 to 1e38            ~7 decimal digits
fp64       1   11      52      ~1e-308 to 1e308           ~15-17 decimal digits
bf16       1    8       7      SAME range as fp32         ~2-3 decimal digits
fp16       1    5      10      ~6e-5 to 65504 (narrow!)   ~3-4 decimal digits
fp8 E4M3   1    4       3      narrow, more precision     ~1 decimal digit
fp8 E5M2   1    5       2      wider range, less prec.    <1 decimal digit

bf16 = fp32's exponent, chopped mantissa -> same RANGE, less PRECISION
fp16 = balanced differently -> more PRECISION, much less RANGE (overflows!)
```

The one-line mental model: **exponent bits buy you range (how big/small a number can be), mantissa bits buy you precision (how many significant digits within that range) — every reduced-precision format is a specific bet about which of those two a given tensor (weights, activations, gradients) actually needs more of.**

---

## How it actually works

### Why 0.1 + 0.2 != 0.3, in bits

0.1 in binary is `0.0001100110011...` repeating, exactly analogous to 1/3 being `0.3333...` repeating in decimal — it cannot be represented exactly in a finite number of bits. So the literal `0.1` in your source code is already rounded to the nearest representable fp64 value the moment it's parsed (approximately `0.1000000000000000055511151231257827021181583404541015625`), and `0.2` is similarly rounded. Adding these two *already-imprecise* values produces a sum that, when rounded to the nearest representable float, happens to land on `0.30000000000000004` rather than the exact mathematical `0.3` (which itself isn't exactly representable either). This is not a bug, not a language-specific quirk (Python, JavaScript, Java, C — every IEEE-754 language shows this identically), and not fixable by "just rounding more carefully" — it's the direct, unavoidable consequence of representing a base-10 fraction in a finite base-2 format. `Decimal`/`BigDecimal` types exist specifically to sidestep this by representing numbers in base 10 internally (at a real performance cost), which is why financial systems use them for currency instead of raw floats.

### Catastrophic cancellation: the dangerous one

Rounding error from representation (like 0.1 + 0.2) is usually harmless — it's a fixed, tiny relative error that doesn't grow. Catastrophic cancellation is different and much more dangerous: when you subtract two floating-point numbers that are close to each other in value, the leading significant digits cancel out, and what remains is dominated by whatever rounding error was already present in the *inputs* — the relative error of the result can be enormous even though the operation itself (subtraction) is exact given its inputs. A concrete, documented example: computing the cross product of two nearly-parallel 3D vectors with float32 components produced a result vector `(1552, -1248, -128)`, while the same computation in float64 produced `(1556.0276, -1257.5151, -75.1656)` — the float32 answer is off by nearly 70% on the z-component. **The tell that you're looking at catastrophic cancellation specifically: getting suspiciously small, "clean-looking" (often near-integer) results from a computation that involved much larger input magnitudes** — that's the signature of most of the precision having been cancelled away. This is why numerically-aware algorithms restructure formulas to avoid subtracting nearly-equal quantities wherever possible (e.g., the quadratic formula's numerically stable variant avoids computing `-b - sqrt(b²-4ac)` when that difference is a near-cancellation, using an algebraically equivalent rearrangement instead).

### Kahan summation: compensating for accumulated rounding error

Summing a long list of floats naively accumulates rounding error at every single addition — each individual error is tiny, but summing millions of values (common in ML loss aggregation, scientific computing, financial totals) can accumulate a meaningfully large aggregate error, especially when adding small numbers to a already-large running sum (the small number's low-order bits simply get rounded away because they're below the running sum's representable precision at that magnitude). **Kahan summation** fixes this by tracking a separate compensation term `c` that captures the low-order bits lost on each addition and feeds them back in on the next step:

```python
def kahan_sum(values):
    total = 0.0
    c = 0.0                      # running compensation for lost low-order bits
    for x in values:
        y = x - c                # correct the next value by previously lost error
        t = total + y
        c = (t - total) - y      # (t - total) recovers what was actually added;
                                  # subtracting y reveals what got rounded away
        total = t
    return total
```

The naive sum's error grows roughly proportional to `n * epsilon` (machine epsilon) in the worst case; Kahan's compensated sum keeps error close to `epsilon` regardless of `n`, for `n` up to roughly `1/epsilon` — a dramatic, practically-relevant improvement for large reductions, which is why serious numerical libraries (NumPy's `pairwise` summation is a related but distinct technique with similar goals) don't do naive left-to-right summation for large arrays.

### bf16 vs fp16 vs fp8: the actual ML production decision

**fp16 (1 sign, 5 exponent, 10 mantissa bits):** max representable magnitude is roughly **65,504** — a real, frequently-hit ceiling, because gradients and intermediate activations in large models routinely produce values well outside that range during training, causing silent overflow to `inf` and then `NaN` propagation through the rest of the computation graph. The historical fix, and still necessary when using fp16, is **loss scaling**: multiply the loss by a large constant (e.g. 128 or 1024) before backpropagation so gradients get scaled up into fp16's representable range, then divide the resulting gradients back down before the optimizer step — this works but requires tuning the scale factor (too small: gradients still underflow; too large: gradients overflow the other direction) and dynamic loss scaling (auto-adjusting the scale factor based on whether overflow was detected) is standard practice specifically because manual tuning is fragile.

**bf16 (1 sign, 8 exponent, 7 mantissa bits):** matches fp32's exponent field exactly, so it has the *same dynamic range* as fp32 (~1e-38 to 1e38) — the overflow problem that plagues fp16 essentially doesn't happen with bf16 at typical training magnitudes, which is why bf16 training usually doesn't need loss scaling at all. The cost is precision: only 7 mantissa bits gives roughly 2-3 significant decimal digits, meaningfully coarser than fp16's 10 mantissa bits (~3-4 digits) — but empirically, large-model training tolerates this precision loss well (the "noise" from bf16 rounding turns out to be small relative to the noise already present from stochastic gradient descent, minibatch sampling, etc.), which is the practical reason bf16 has become the default training format across most current large-model training stacks despite having objectively fewer precision bits than fp16.

**fp8 (E4M3 and E5M2):** halves memory and bandwidth again versus bf16, which directly translates to larger batch sizes and higher throughput per accelerator — real, measured wins in both inference serving cost and (on newest-generation hardware) training throughput. E4M3 (4 exponent, 3 mantissa bits) trades range for precision, typically used for weights and activations where values are reasonably bounded and precision matters more; E5M2 (5 exponent, 2 mantissa bits) trades precision for range, typically used for gradients, which can span a much wider dynamic range during training. With only 2-3 mantissa bits, fp8 has essentially no margin for representation error, which is why fp8 training/inference requires **per-tensor or per-block scaling factors** (each tensor, or even each block within a tensor, gets its own scale to keep its value distribution centered in fp8's narrow useful range) rather than one single global loss-scale constant — a meaningfully more complex numerics engineering problem than bf16's comparatively simple "just switch the dtype" story.

---

## Build it from scratch

A small, runnable demonstration of the representation and cancellation issues, worth being able to reproduce cold:

```python
# untested sketch — reproduces the core numerics failure modes discussed above
import struct

def float_bits(f):
    """Show the actual IEEE-754 bit layout of a Python float (fp64)."""
    [bits] = struct.unpack('>Q', struct.pack('>d', f))
    sign = (bits >> 63) & 1
    exponent = (bits >> 52) & 0x7FF
    mantissa = bits & ((1 << 52) - 1)
    return f"sign={sign} exponent={exponent-1023} mantissa={mantissa:013x}"

print(0.1 + 0.2)                        # 0.30000000000000004
print(0.1 + 0.2 == 0.3)                 # False
print(float_bits(0.1))                  # 0.1 is NOT exact -- repeating binary fraction

# catastrophic cancellation: subtracting nearly-equal large numbers
a = 1234567.891
b = 1234567.890
print(a - b)                            # should be 0.001, watch precision degrade
print((a - b) - 0.001)                  # the residual error, not exactly zero

# Kahan summation vs naive summation error growth
def naive_sum(values):
    total = 0.0
    for x in values:
        total += x
    return total

def kahan_sum(values):
    total = c = 0.0
    for x in values:
        y = x - c
        t = total + y
        c = (t - total) - y
        total = t
    return total

values = [1e16] + [1.0] * 10000 + [-1e16]   # naive sum loses the 10000 additions entirely
print(naive_sum(values))    # likely 0.0 -- the 1.0s were below representable precision
print(kahan_sum(values))    # closer to the mathematically correct 10000.0
```

The `values = [1e16] + [1.0]*10000 + [-1e16]` case is the clearest possible demonstration: mathematically the answer is exactly 10000.0, but naive summation adds each `1.0` to a running total of `1e16`, where `1.0` is far below the precision fp64 can represent at that magnitude (fp64 has ~15-17 significant decimal digits, and `1e16` already consumes all of them), so every single `+1.0` is silently absorbed with zero effect — Kahan's compensation term recovers what naive summation loses. A fuller lab implementing bf16/fp16/fp8 simulation (truncating a fp32 value's bits to model reduced-precision rounding) belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Financial calculation totals are off by fractions of a cent after many transactions | Floats used for currency; repeated rounding error accumulates across many additions | Use a fixed-point/decimal type (`Decimal` in Python, `BigDecimal` in Java, integer cents) for any value that must be exact under addition |
| `a == b` comparison fails for values that "should" be equal after a computation | Direct equality comparison on floats that both carry independent rounding error from different computation paths | Compare with a tolerance (`abs(a - b) < epsilon`, scaled relative to magnitude) instead of exact equality |
| fp16 training run's loss suddenly becomes `NaN` partway through, run has to be restarted from a checkpoint | Gradient values overflowed fp16's ~65,504 max representable magnitude, propagating `inf`/`NaN` through the graph | Use bf16 instead (matches fp32's exponent range, no overflow at these magnitudes), or if fp16 is required for hardware reasons, use dynamic loss scaling that reduces the scale factor automatically on detected overflow |
| bf16-trained model shows unexpectedly poor convergence on a specific numerically sensitive layer (e.g. certain normalization or attention softmax computations) | bf16's 7 mantissa bits (2-3 decimal digits) are too coarse for that specific computation's precision requirement, even though the exponent range is fine | Selectively keep sensitive operations in fp32 (mixed-precision training, "master weights" pattern: fp32 optimizer state + bf16 forward/backward) rather than running the entire model in bf16 |
| fp8 inference deployment shows accuracy degradation that per-tensor scaling doesn't fully fix | A single tensor has a value distribution too wide for one scale factor to keep everything in fp8's narrow useful precision range | Move to per-block/per-channel scaling (finer-grained than per-tensor) or keep the specific problematic layer at higher precision |
| A large reduction/aggregation (sum over millions of rows) in a data pipeline shows drift versus a reference implementation | Naive left-to-right summation accumulating rounding error at scale, especially when adding small values to an already-large running total | Use pairwise/tree summation (NumPy's default for large arrays) or explicit Kahan summation for reductions where accumulated error is operationally significant |

---

## Tradeoffs & when NOT to use it

- **Don't use raw `float`/`double` for currency or any value requiring exact decimal arithmetic under addition.** The representation error is small per-operation but real and accumulates; use fixed-point integers (cents) or a decimal type. This is not a performance optimization question, it's a correctness requirement.
- **Don't default to fp16 for large-model training without loss scaling.** Its narrow exponent range (~65,504 max) is a real, frequently-hit ceiling for gradients in large models, not an edge case — bf16 sidesteps this class of failure entirely at the cost of coarser precision that most large-model training tolerates well.
- **Don't assume bf16/fp8 are safe defaults for every tensor in a model.** Some computations (certain normalization layers, loss computation itself, optimizer state) are more numerically sensitive and commonly kept at higher precision even in an otherwise low-precision training/inference pipeline — mixed precision, not uniform precision, is the actual production pattern.
- **Don't compare floats for exact equality**, ever, except in the narrow case of literal bit-identical values you constructed yourself (e.g. checking a sentinel value) — use a tolerance-based comparison for anything derived from computation.
- **Don't reach for Kahan summation reflexively on every reduction.** It roughly doubles the arithmetic operations per addition; for small arrays or cases where the accumulated error genuinely doesn't matter (most everyday aggregate reporting), naive summation (or NumPy's built-in pairwise summation) is simpler and fast enough — Kahan is for cases where accumulated error over very large or numerically adversarial reductions is operationally significant.

---

## Interview questions

### Q1 — Why does `0.1 + 0.2 != 0.3` in every mainstream language?
**Testing:** the baseline representation question, but wanting the *mechanism*, not just the fact.
**Answer:** 0.1 and 0.2 are both repeating fractions in binary (analogous to 1/3 repeating in decimal), so neither can be represented exactly in IEEE-754's finite bit layout — both are already rounded to the nearest representable float before the addition happens, and the sum rounds again, landing on `0.30000000000000004` rather than the mathematically exact `0.3` (which also isn't exactly representable). It's a direct, unavoidable consequence of representing base-10 fractions in a finite base-2 format, not a language bug.
**Follow-up trap:** *"Is this fixable by using a 'more precise' float type?"* — no; fp64, fp128, any binary floating-point format has the same fundamental issue for this specific value, because the problem is the base (2 vs 10), not the bit width. The actual fix is a decimal/fixed-point type that represents base-10 fractions natively, at a real performance cost.

### Q2 — What is catastrophic cancellation, and how is it different from ordinary rounding error?
**Testing:** whether the candidate distinguishes "small, harmless, constant error" from "error that gets amplified."
**Answer:** Catastrophic cancellation happens when subtracting two nearly-equal floating-point numbers — the leading significant digits cancel, and what remains is dominated by whatever rounding error was already present in the inputs, so the *relative* error of the result can be enormous even though the subtraction itself is computed exactly given its (already-imprecise) inputs. Ordinary rounding error is a small, roughly constant relative error per operation; cancellation amplifies existing error rather than introducing new error, but the amplification can be arbitrarily large depending on how close the two values are.
**Follow-up trap:** *"Does this depend on the numbers being very large or very small?"* — no, and this is the counterintuitive part: it depends only on how close the two operands are to each other and how much rounding error they already carry, not on their absolute magnitude — a documented cross-product example computing with values in the tens of thousands still produced a result off by nearly 70% from the float64 reference.

### Q3 — What's the tell that a numerical result is suffering from catastrophic cancellation?
**Testing:** practical debugging pattern recognition.
**Answer:** Getting a suspiciously small, "clean-looking" result (often near-integer) from a computation that involved much larger input magnitudes — that pattern is the signature of most of the meaningful digits having cancelled away, leaving mostly rounding noise.
**Follow-up trap:** *"How would you fix a formula once you've identified this?"* — algebraically restructure the computation to avoid subtracting nearly-equal quantities directly, e.g. the numerically stable form of the quadratic formula avoids `-b - sqrt(b²-4ac)` when that specific term is a near-cancellation, using a mathematically equivalent rearrangement that doesn't subtract two close values.

### Q4 — Explain what Kahan summation fixes and give a concrete case where naive summation visibly fails.
**Testing:** whether the compensation mechanism is understood, and whether a real failure case is known.
**Answer:** Naive summation accumulates rounding error at every addition, particularly bad when adding small values to an already-large running total, because the small value's low-order bits fall below what's representable at the running total's current magnitude and get silently dropped. Concrete failure: summing `[1e16] + [1.0]*10000 + [-1e16]` naively gives roughly 0.0 (the ten thousand 1.0 additions are individually invisible against 1e16's magnitude), while the mathematically correct answer is 10000.0; Kahan summation tracks a compensation term capturing what got rounded away each step and feeds it back in, recovering the correct result.
**Follow-up trap:** *"Should you use Kahan summation everywhere for safety?"* — no; it roughly doubles the arithmetic cost per addition, and for small arrays or cases where accumulated error genuinely doesn't matter, naive or library-default pairwise summation (NumPy's default for large arrays) is simpler and fast enough. Kahan is for cases where large-scale accumulated error is operationally significant.

### Q5 — Compare bf16 and fp16's bit layouts and explain why bf16 became the ML training default despite having fewer mantissa bits.
**Testing:** the actual production reasoning behind the industry's format choice, not just memorized bit counts.
**Answer:** bf16 uses 1 sign, 8 exponent, 7 mantissa bits (matching fp32's exponent field exactly); fp16 uses 1 sign, 5 exponent, 10 mantissa bits. bf16's 8-bit exponent gives it the same dynamic range as fp32 (~1e-38 to 1e38), while fp16's 5-bit exponent caps out around 65,504 — a range large-model gradients routinely exceed, causing overflow to inf/NaN. bf16 sacrifices precision (7 mantissa bits, ~2-3 decimal digits, versus fp16's 10 bits/~3-4 digits) but empirically large-model training tolerates that precision loss well, since it's small relative to the noise already present from stochastic gradient descent — so bf16 trades fp16's more frequent, more catastrophic overflow failures for a milder, more tolerable precision loss.
**Follow-up trap:** *"If fp16 has more precision, why would anyone still use it?"* — hardware support and historical inertia: fp16 was the first mainstream reduced-precision training format (NVIDIA Volta-era Tensor Cores) and remains supported and sometimes preferred where its precision matters more than range for a specific workload, provided loss scaling is correctly tuned to manage the overflow risk.

### Q6 — What is loss scaling in fp16 training, and why does bf16 usually not need it?
**Testing:** understanding the specific engineering workaround fp16's range limitation forces.
**Answer:** Loss scaling multiplies the loss by a large constant before backpropagation so that small gradient values get scaled up into fp16's representable range (avoiding underflow to zero), then the resulting gradients are divided back down before the optimizer step; dynamic loss scaling auto-adjusts the scale factor based on detected overflow, since manual tuning is fragile. bf16 doesn't need this because its exponent range already matches fp32's — gradients at typical training magnitudes simply don't overflow bf16's range the way they routinely overflow fp16's much narrower ~65,504 ceiling.
**Follow-up trap:** *"Does bf16 ever need scaling for anything?"* — bf16 can still suffer from precision loss (its 7 mantissa bits) even though range isn't the issue, so mixed-precision training patterns (fp32 master weights, bf16 forward/backward compute) are still standard practice — scaling addresses fp16's range problem specifically, not a general "never needs care" claim about bf16.

### Q7 — Why does fp8 training need per-tensor or per-block scaling factors rather than one global loss scale?
**Testing:** the deeper reasoning behind fp8's more complex numerics engineering versus bf16's comparatively simple story.
**Answer:** fp8 (E4M3: 4 exp/3 mantissa, or E5M2: 5 exp/2 mantissa) has only 2-3 mantissa bits, leaving almost no margin for representation error — a single global scale factor tuned for one tensor's value distribution is very likely wrong for another tensor (or even a different region within one tensor) whose values sit at a different magnitude, causing systematic under- or over-flow in that region. Per-tensor (or finer, per-block) scaling keeps each tensor's actual value distribution centered in fp8's narrow useful precision range individually.
**Follow-up trap:** *"Why not just always use the finest possible granularity (per-value scaling) to be safe?"* — finer-grained scaling costs more memory and compute overhead (storing and applying more scale factors), so production systems pick the coarsest granularity (per-tensor, then per-block if needed) that still keeps accuracy acceptable — it's an accuracy/overhead tradeoff tuned empirically per model/layer, not a "finer is always better with no cost" decision.

### Q8 — When would you use `Decimal`/`BigDecimal` instead of `float`/`double`, and what's the real cost?
**Testing:** knowing the correctness-critical use case and being honest about the tradeoff, not treating decimal types as strictly superior.
**Answer:** Use decimal/fixed-point types for any value requiring exact decimal arithmetic under addition where accumulated float rounding error is unacceptable — currency and financial calculations are the canonical case, since fractions-of-a-cent drift across many transactions is a real, auditable correctness bug, not a rounding curiosity. The cost is real: decimal arithmetic is meaningfully slower than native hardware floating-point (no dedicated FPU support for base-10 arithmetic), so it's reserved for correctness-critical paths, not used as a blanket default for all numeric code.
**Follow-up trap:** *"Would you use Decimal for scientific/ML computation too?"* — no; scientific and ML workloads generally care about relative precision and throughput at scale, not exact decimal representation, and the performance cost of decimal arithmetic would be prohibitive at the volumes those workloads operate at — floats (and reduced-precision formats) are the right tool there specifically because exactness isn't the requirement, throughput and adequate relative precision are.

### Q9 — Your training run's loss goes to `NaN` at step 40,000 of a multi-week fp16 run. Walk through the diagnosis.
**Testing:** applying the range/overflow understanding to a realistic, expensive production failure.
**Answer:** First suspect: gradient overflow in fp16 (values exceeding ~65,504, becoming inf, then NaN propagating through subsequent operations) — check whether loss scaling is enabled and whether the scale factor is appropriate, or whether dynamic loss scaling's overflow-detection/scale-reduction logic is actually functioning. If loss scaling seems correctly configured and NaN still occurs, the next hypothesis is a genuinely exploding gradient (a real training instability, not a numerics-format artifact) that would also need addressing at the model/optimizer level (gradient clipping, learning rate) regardless of numeric format.
**Follow-up trap:** *"Would switching to bf16 have prevented this, and would you recommend it going forward?"* — bf16's wider exponent range would likely have prevented the *overflow-driven* NaN specifically (the same magnitude gradient wouldn't have overflowed bf16's range), but if the underlying cause is a genuine training instability rather than a representable-range issue, switching formats treats a symptom, not the cause — the honest answer distinguishes "this specific failure mode" from "the training is fundamentally unstable," and recommends checkpointing/restart discipline plus root-causing which one this actually was.

### Q10 — Explain why float equality comparison (`a == b`) is unreliable, and how you'd fix a test asserting a floating-point result.
**Testing:** a very common but frequently mishandled real-world pattern.
**Answer:** Two floating-point values arrived at via different computation paths (even mathematically equivalent ones) can carry different accumulated rounding error, so exact bitwise equality is not a reliable test for "these are the same real number" — the fix is comparing with a tolerance, `abs(a - b) < epsilon`, ideally scaled relative to the magnitude of the values involved (an absolute epsilon that's fine for values near 1.0 may be meaninglessly tight or loose for values near 1e10 or 1e-10).
**Follow-up trap:** *"What tolerance would you pick, and does it depend on the operations involved?"* — yes; the appropriate epsilon depends on how many floating-point operations contributed to the result (more operations, more accumulated error, need a looser tolerance) and the magnitude of the values (relative rather than absolute tolerance is usually more robust across different magnitude ranges) — a single hardcoded epsilon used everywhere in a codebase is itself a common source of flaky numerical tests.

### Q11 — Design question: you're deploying an LLM for inference and need to pick a numeric format for weights, activations, and KV cache separately. How do you decide?
**Testing:** staff-level judgment applying the range/precision tradeoff to a realistic multi-component decision, not a single blanket format choice.
**Answer:** Weights are typically the least numerically sensitive at inference time (no gradient accumulation, values are fixed post-training) and are the best candidate for aggressive quantization (fp8, or even lower with calibration) since they dominate memory footprint and the accuracy cost is usually small and well-studied via post-training quantization techniques. Activations need more care — their dynamic range varies more per-input and per-layer, so per-tensor or per-channel scaling matters more, and some layers (attention softmax, layer norm) are known to be more numerically sensitive and may need to stay at higher precision (bf16 or fp16) even in an otherwise fp8 pipeline. KV cache is a major memory cost at long context lengths, making it a strong quantization target for throughput, but quantization error here directly affects attention outputs across the entire remaining generation, so it needs empirical accuracy validation specific to the model and expected context lengths rather than a blanket assumption that "it worked for weights so it'll work here too."
**Follow-up trap:** *"How would you validate the accuracy impact of this before shipping?"* — measure task-specific evaluation metrics (not just perplexity, which can look fine while specific capabilities degrade) on representative held-out data comparing full precision against the mixed-precision deployment configuration, and specifically stress-test long-context scenarios if KV cache is quantized, since that's where compounding quantization error across many attention steps is most likely to surface as a real quality regression.

---

## Red flags that fail you

- Claiming `0.1 + 0.2 != 0.3` is a bug in a specific language rather than a universal IEEE-754 representation consequence.
- Confusing catastrophic cancellation with ordinary rounding error, or claiming it only affects very large or very small numbers.
- Treating bf16, fp16, and fp8 as interchangeable "smaller floats" with no mention of the range-vs-precision tradeoff each one makes.
- Not knowing why fp16 needs loss scaling and bf16 usually doesn't.
- Recommending `float`/`double` for currency calculations.
- Comparing floats with `==` in code presented as correct.

---

## Cheat card

```
IEEE-754 fp32: 1 sign + 8 exponent + 23 mantissa bits
  value = (-1)^S x 1.M x 2^(E-bias)  -- exponent=RANGE, mantissa=PRECISION
fp64: 1+11+52 bits, ~15-17 decimal digits precision

0.1+0.2 != 0.3: BOTH operands already rounded (0.1 is a repeating binary
  fraction, like 1/3 in decimal) before addition even happens -- universal
  across every IEEE-754 language, not fixable by "more precision"

CATASTROPHIC CANCELLATION: subtracting near-equal floats destroys sig. digits,
  amplifies EXISTING input error -- happens at ANY magnitude, not just extremes
  TELL: suspiciously small/clean/near-integer result from large-magnitude inputs

KAHAN SUMMATION: tracks compensation term for lost low-order bits per addition
  naive sum error ~ O(n*eps); Kahan ~ O(eps) for n < 1/eps
  demo: sum([1e16]+[1.0]*10000+[-1e16]) naive=~0.0, Kahan=~10000.0 (correct)

FORMAT      SIGN EXP MANT   RANGE              PRECISION       ML USE
fp32          1   8   23    ~1e-38..1e38       ~7 digits       master weights
bf16          1   8    7    SAME as fp32       ~2-3 digits     training default
fp16          1   5   10    max ~65,504 (!)    ~3-4 digits     needs loss scaling
fp8 E4M3      1   4    3    narrow, precise    ~1 digit        weights/activations
fp8 E5M2      1   5    2    wide, imprecise    <1 digit        gradients

fp16 overflow -> inf -> NaN propagation -> LOSS SCALING required (dynamic,
  auto-adjusts scale on detected overflow)
bf16 = fp32's exponent (no overflow at typical magnitudes) -> usually NO
  loss scaling needed, but only 7 mantissa bits (coarser than fp16!)
fp8: needs PER-TENSOR/PER-BLOCK scaling (not 1 global scale) -- 2-3 mantissa
  bits leave almost no error margin

Use Decimal/BigDecimal/fixed-point (integer cents) for currency -- never raw
  float for exact-arithmetic-under-addition requirements
Never compare floats with == ; use abs(a-b) < eps (scaled to magnitude)
```

## Sources

- [FP8 Vs BF16: Choosing Mixed Precision On NVIDIA Tensor Cores — AceCloud](https://acecloud.ai/blog/fp8-vs-bf16-mixed-precision-tensor-cores/) — accessed 2026-08-03
- [A Study of BFLOAT16 for Deep Learning Training — arXiv](https://arxiv.org/pdf/1905.12322) — accessed 2026-08-03
- [Leveraging the bfloat16 Datatype For Higher-Precision Computations — arXiv](https://arxiv.org/pdf/1904.06376) — accessed 2026-08-03
- [Catastrophic cancellation — Wikipedia](https://en.wikipedia.org/wiki/Catastrophic_cancellation) — accessed 2026-08-03
- [Accurate Differences of Products with Kahan's Algorithm — Matt Pharr](https://pharr.org/matt/blog/2019/11/03/difference-of-floats) — accessed 2026-08-03
- IEEE 754-2019 — IEEE Standard for Floating-Point Arithmetic

## Changelog
- 2026-08-03 — created
