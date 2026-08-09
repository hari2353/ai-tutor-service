# Init Schemes, Normalization, and the Optimizer Lineage: SGD → Adam → AdamW → Lion → Muon, Derived

> **Track:** T04 Deep Learning · **Time:** 2.5h · **Prereqs:** T04-architectures · **Updated:** 2026-08-03
> **Module id:** `T04-optimization` · **Tags:** training
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Weight initialization exists to solve one specific problem derived in `T04-backprop-derivation`: keep the per-layer signal-and-gradient scaling factor near `1` at the *start* of training, before anything else (normalization, residuals) has a chance to help — Xavier/Glorot init (2010) sets weight variance to `2/(fan_in+fan_out)` to keep activation variance roughly constant forward and gradient variance roughly constant backward under a linear/tanh assumption, while He init (2015) doubles that to `2/fan_in` specifically because ReLU zeroes out roughly half its inputs, halving variance unless compensated. Normalization layers (BatchNorm 2015, LayerNorm 2016, RMSNorm 2019) recenter and/or rescale activations at every layer so the *rest* of training stays in that same well-behaved regime rather than drifting — BatchNorm normalizes across the batch dimension per feature (a dependency that breaks at batch size 1 and complicates recurrent/generative models), LayerNorm normalizes across the feature dimension per example (batch-size-independent, the default in transformers), and RMSNorm drops LayerNorm's mean-centering entirely and normalizes only by root-mean-square (cheaper, and empirically just as good for the transformer stacks it's now standard in, e.g. LLaMA-family models). The optimizer lineage is a sequence of fixes to genuinely observed problems: plain SGD updates by the raw gradient and is scale-blind across parameters; SGD+momentum smooths the update with an exponential moving average of past gradients to dampen oscillation; Adam (2014) adds a *second* exponential moving average (of squared gradients) to adapt the step size per-parameter, plus bias correction to fix the fact that both moving averages start at zero and are biased toward it early in training — a concrete illustration: with a constant gradient of `1.0`, `beta1=0.9`, `beta2=0.999`, the raw (uncorrected) first-moment/second-moment ratio drifts from `3.16x` too large at step 1 toward the true value only after hundreds of steps (since `beta2=0.999` takes roughly `1/(1-0.999)=1000` steps to "fill up"), while the bias-corrected ratio is exactly correct from step 1; AdamW (2017) fixes a genuine bug in how most implementations combined Adam with L2 regularization (folding weight decay into the gradient interacts badly with Adam's adaptive per-parameter scaling) by decoupling weight decay into a direct, separate shrinkage of the weights; Lion (2023) discards the second moment entirely and updates by the *sign* of a momentum term, trading adaptivity for memory savings and different (typically smaller) effective learning rates; and Muon (2024-2025) applies momentum, then orthogonalizes the resulting update matrix via a few Newton-Schulz iterations before applying it — reported at roughly 2x the compute efficiency of AdamW and adopted in training trillion-parameter production models (Kimi K2, DeepSeek V4) as of 2026. Learning rate schedules (warmup, then cosine or step decay) exist because early training gradients and Adam's own moment estimates are the least reliable they'll ever be (fresh, unwarmed-up initialization plus the same early-step bias-correction instability above), so a short linear warmup avoids a large, badly-calibrated first step, while decay later in training lets the optimizer settle into a sharper minimum than a constant learning rate would find.

## Why this gets asked

Because "why do you initialize weights that specific way" and "walk me through why Adam needs bias correction" are exactly the kind of question that separates someone who calls `torch.nn.init.kaiming_normal_()` because a tutorial did, from someone who can derive why that specific formula exists and what breaks without it. Interviewers ask this because these are exactly the defaults every framework silently sets for you — most engineers never think about them until a training run mysteriously diverges or plateaus, and the ability to reason from first principles about *which* of these (initialization scale, missing normalization, wrong optimizer/schedule) is the actual cause is a direct, high-frequency, on-the-job debugging skill, not academic trivia.

---

## Lineage: past → present → future

**What came before.** Early neural network training (pre-2010) used ad-hoc initialization — small random weights, uniform in some arbitrary range — with no principled connection to network depth or width, and no normalization layers at all. The pain this produced was exactly the vanishing/exploding gradient problem derived in `T04-backprop-derivation`: without a deliberate choice of initial weight scale, the per-layer signal/gradient factor had no reason to be anywhere near `1`, and deep networks (even moderately deep ones, by modern standards) were simply very hard to train reliably. Plain SGD, similarly, updates every parameter by the same learning rate scaled by its raw gradient, with no memory of past updates and no per-parameter adaptivity — workable for shallow, well-conditioned problems, but slow and unstable (oscillating across narrow valleys in the loss landscape, crawling across flat regions) for the ill-conditioned, high-dimensional loss surfaces deep networks actually present.

**Where it stands now.** Xavier/Glorot (2010) and He (2015) initialization are both still the standard defaults baked into every framework's layer constructors, chosen automatically based on the layer's declared activation function — this is genuinely settled, not a live debate. Normalization has converged on architecture-specific defaults rather than one universal winner: BatchNorm remains standard in convolutional vision architectures, while LayerNorm (and increasingly RMSNorm) dominates transformer-based architectures specifically because those process variable-length sequences and often small/streaming batch sizes where BatchNorm's cross-batch dependency is a liability, not merely a stylistic preference. AdamW is the default optimizer for the overwhelming majority of deep learning training as of 2026, precisely because SGD+momentum's per-parameter-uniform learning rate under-performs badly conditioned, high-dimensional, non-convex problems like transformer training, while Adam's decoupled-weight-decay bug (now understood and fixed as AdamW) made adaptive optimization actually competitive with well-tuned SGD+momentum for generalization, not just optimization speed. The genuinely live frontier is what comes *after* AdamW for large-scale pretraining: Lion is used in some production settings for its memory savings (no second moment to store, meaningful at billion-plus parameter scale), while Muon has moved from a promising 2024 optimizer paper to demonstrated production adoption in 2025-2026 at the largest training runs reported publicly (Kimi K2/2.5, GLM-4.5/4.7, and DeepSeek's own reporting that Muon is used in most modules of DeepSeek-V4), with NVIDIA integrating Muon support directly into Megatron Core as of April 2026 — this is a genuine, currently-unsettled transition, not yet a universal replacement for AdamW.

**Where it's heading.** The clearest trend is toward optimizers that exploit more structure than a per-parameter scalar adaptive rate (Adam's approach) — Muon's per-weight-matrix orthogonalization is explicitly exploiting the 2D matrix structure of most deep learning parameters rather than treating every parameter as an independent scalar, and this "structure-aware" direction (as opposed to purely per-parameter-adaptive) looks like the more active research frontier heading into the rest of the decade. Normalization is trending toward RMSNorm as the default for new large transformer architectures specifically because it's measurably cheaper (skips mean-centering) with no measured quality cost at that scale, though BatchNorm remains entrenched and appropriate for convolutional vision workloads where large batch sizes are the norm and its inter-example dependency is a non-issue. What's speculative: whether Muon-style approaches fully displace AdamW as the default for pretraining broadly (as of 2026 this is a genuine, live transition, not a settled fact), and how much further optimizer research can push training efficiency before other bottlenecks (data, communication cost in distributed training, covered in `T04-distributed-training`) dominate instead.

---

## Mental model

```
INITIALIZATION: get the per-layer signal/gradient SCALING FACTOR near 1 at t=0
  Xavier/Glorot (linear/tanh):  Var(W) = 2/(fan_in+fan_out)
  He (ReLU):                    Var(W) = 2/fan_in          <- 2x Xavier: ReLU
                                                                zeroes ~half the
                                                                units, halving
                                                                variance otherwise

NORMALIZATION: keep the REST of training in that same well-behaved regime
  BatchNorm: normalize ACROSS the batch, PER feature  (depends on batch size/stats)
  LayerNorm: normalize ACROSS features, PER example    (batch-independent)
  RMSNorm:   like LayerNorm but SKIP mean-centering, only rescale by RMS

OPTIMIZER LINEAGE (each fixes ONE specific, real problem in the previous one):
  SGD:        theta -= lr * g                        (no memory, scale-blind)
    |  fix: smooth noisy/oscillating gradients
    v
  SGD+Momentum: m = beta*m + g; theta -= lr*m         (EMA of gradient direction)
    |  fix: per-parameter step-size ADAPTIVITY
    v
  Adam:  m=EMA(g), v=EMA(g^2), bias-correct both, theta -= lr*m_hat/(sqrt(v_hat)+eps)
    |  fix: weight decay was WRONGLY coupled into the adaptive gradient term
    v
  AdamW: theta -= lr*(m_hat/(sqrt(v_hat)+eps) + wd*theta)   <- wd applied DIRECTLY
    |  fix (alt. branch): memory cost of storing v (2nd moment) at scale
    v
  Lion:  c=beta1*m+(1-beta1)*g; update=sign(c); m=beta2*m+(1-beta2)*g   (no v at all)
    |  fix (alt. branch): exploit 2D WEIGHT-MATRIX structure, not just per-scalar
    v
  Muon:  momentum update, then ORTHOGONALIZE the update matrix (Newton-Schulz)
         before applying -- ~2x compute efficiency vs AdamW, 2025-2026 production use

LR SCHEDULE: warmup (early steps are the LEAST reliable) -> decay (settle into
  a sharper minimum than constant LR would find)
```

The one-line mental model: **initialization sets the starting scale so the network is trainable at all, normalization keeps that scale healthy throughout training, and the optimizer lineage is a chain of fixes to specific, real, historically-documented problems — not an arbitrary sequence of fancier names.**

---

## How it actually works

### Initialization: the variance-preservation derivation, with real numbers

The goal is to choose the initial weight distribution so that, at initialization, the *variance* of activations doesn't shrink toward zero or blow up as signal passes through layers (this is precisely the initialization-time instance of the vanishing/exploding product from `T04-backprop-derivation`, before any training has even started). For a linear layer `z = Wx+b` with `x` having variance `σx²` and `W`'s entries drawn i.i.d. with variance `σw²`, `Var(z) ≈ fan_in · σw² · σx²` (summing `fan_in` independent terms). To keep `Var(z) ≈ Var(x)` forward, you need `σw² = 1/fan_in`; a symmetric argument for the backward pass (keeping gradient variance stable) wants `σw² = 1/fan_out`; **Xavier/Glorot initialization (2010)** splits the difference: `σw² = 2/(fan_in+fan_out)`. For a `784→256` linear layer, this gives `σw = sqrt(2/(784+256)) = sqrt(2/1040) ≈ 0.04385` (or, for the uniform-distribution variant, bound `±sqrt(6/(fan_in+fan_out)) ≈ ±0.0760`). **He initialization (2015)** addresses a specific gap Xavier doesn't cover: ReLU zeroes out roughly half its inputs (everything negative), which *halves* the variance passing through compared to a linear or symmetric activation like tanh — compensating requires doubling the variance target, giving `σw² = 2/fan_in` (using `fan_in` alone, matching the forward-pass-only derivation above, common in practice for ReLU networks). For the same `784→256` layer, He gives `σw = sqrt(2/784) ≈ 0.05051` — noticeably larger than Xavier's `0.04385`, which is exactly the compensation ReLU's variance-halving requires.

### BatchNorm, LayerNorm, RMSNorm: the actual formulas, with a worked numeric example

All three normalize some slice of the activation tensor to (roughly) zero mean and unit variance, then apply a learned affine rescaling (`γ, β`) so the network can undo the normalization if that's actually what's optimal — the difference between them is *which dimension* they normalize across.

**BatchNorm** (Ioffe & Szegedy, 2015): for a feature, normalize across the **batch dimension** — `x̂ᵢ = (xᵢ - μ_batch)/sqrt(σ²_batch + ε)`, where `μ_batch, σ²_batch` are computed per-feature, across all examples in the current mini-batch. This makes BatchNorm's behavior depend on batch composition (statistics differ meaningfully at batch size 1, or across very different batches), and it requires tracking running statistics for inference (since a single test-time example has no "batch" to normalize across) — both real, structural complications.

**LayerNorm** (Ba, Kiros, Hinton, 2016): normalize across the **feature dimension**, per individual example — `x̂ᵢ = (xᵢ - μ_example)/sqrt(σ²_example + ε)`, with `μ_example, σ²_example` computed across the features of one example, independent of every other example in the batch. Worked example, `x=[1.0, 2.0, 3.0, 4.0]` (four features of one example): `μ=2.5`, `σ²=1.25`, `std=sqrt(1.25+ε)≈1.11804`, giving normalized output `[-1.34164, -0.44721, 0.44721, 1.34164]`. Being batch-independent is exactly why LayerNorm (not BatchNorm) is the default in transformers, which routinely process variable-length sequences and, especially at inference, batch size 1.

**RMSNorm** (Zhang & Sennrich, 2019): keeps LayerNorm's per-example, per-feature-dimension normalization, but **skips mean-centering entirely** and normalizes only by root-mean-square: `x̂ᵢ = xᵢ / sqrt(mean(x²) + ε)`. Same example, `x=[1.0,2.0,3.0,4.0]`: `mean(x²) = (1+4+9+16)/4 = 7.5`, `rms = sqrt(7.5+ε) ≈ 2.73861`, giving `[0.36515, 0.73030, 1.09544, 1.46059]` — a different, un-recentered output from LayerNorm's, cheaper to compute (no mean subtraction, no need to track/subtract that separate statistic), and empirically matching LayerNorm's quality in the large transformer stacks it's now standard in (used in LLaMA-family and many other modern open-weight LLM architectures as of 2026). The core empirical justification for dropping mean-centering: transformer activations at scale tend not to rely heavily on absolute mean-shift information the way some smaller/earlier architectures might, so the extra normalization work buys measurably little at real model scale.

### SGD, momentum, and why momentum alone isn't enough

Plain SGD: `θ ← θ - lr·g`, where `g` is the current minibatch gradient. This is scale-blind across parameters (every parameter gets the identical learning rate regardless of that parameter's typical gradient magnitude or curvature) and has no memory of past steps, which makes it slow to navigate loss landscapes with very different curvature in different directions (a classic ravine: SGD oscillates across the steep direction while crawling along the shallow one). **SGD with momentum**: `m ← β·m + g`, `θ ← θ - lr·m` — `m` is an exponential moving average of the gradient, which dampens oscillation (opposing components across successive noisy gradients partially cancel in the average) and accelerates consistent-direction movement (components that agree across steps accumulate). This is a real, substantial improvement, but still applies the *same* learning rate to every parameter — it doesn't address the fact that different parameters/directions may need very different effective step sizes.

### Adam: two moving averages, and why bias correction is not optional

Adam (Kingma & Ba, 2014) maintains **two** exponential moving averages per parameter: `m_t = β1·m_{t-1} + (1-β1)·g_t` (first moment, gradient mean — like momentum) and `v_t = β2·v_{t-1} + (1-β2)·g_t²` (second moment, squared-gradient mean — an estimate of gradient variance/magnitude), then updates `θ ← θ - lr · m̂_t/(sqrt(v̂_t)+ε)`, dividing by an estimate of each parameter's typical gradient magnitude to give parameters with small, consistent gradients a relatively larger effective step and parameters with large or noisy gradients a relatively smaller one. Both `m` and `v` are initialized to zero, which biases early estimates *toward zero* — bias correction (`m̂_t = m_t/(1-β1^t)`, `v̂_t = v_t/(1-β2^t)`) compensates exactly for this. **Concrete illustration** with a constant gradient `g=1.0`, `β1=0.9`, `β2=0.999`, `lr=0.001`:
```
t=1: raw m=0.100000  raw v=0.001000  ->  m_hat=1.000000  v_hat=1.000000  (bias-corrected: EXACT)
t=2: raw m=0.190000  raw v=0.001999  ->  m_hat=1.000000  v_hat=1.000000
t=3: raw m=0.271000  raw v=0.002997  ->  m_hat=1.000000  v_hat=1.000000

corrected update (every step):    lr * 1.000000/sqrt(1.000000) = 0.001000
UNcorrected update (raw m,v):      t=1: 0.003162   t=2: 0.004250   t=3: 0.004950  (drifting!)
```
With bias correction, the update is exactly `lr` at every single step (correctly reflecting that the true average gradient is exactly `1.0`, known immediately). Without it, the raw ratio `m/sqrt(v)` *drifts upward* over the first several hundred steps, because `β1=0.9` needs only about 10 steps to approach its steady-state average while `β2=0.999` needs roughly `1/(1-0.999)=1000` steps — the two moving averages "warm up" at very different rates, and without correction the resulting step size is an uncontrolled, time-varying artifact of that mismatch rather than a deliberate choice, exactly during the earliest (and often most consequential) steps of training.

### AdamW: decoupling weight decay from the adaptive gradient term

Classic L2 regularization adds `λθ` directly to the gradient before it's used: `g ← g + λθ`, then proceeds through Adam's ordinary `m`/`v` update. The problem: this couples weight decay's effective shrinkage to Adam's per-parameter adaptive scaling — a parameter with a large `v̂` (large recent gradient magnitude) has its *entire* update, including the weight-decay portion, shrunk by dividing through `sqrt(v̂)`, meaning parameters that are already receiving large gradients get *less* effective weight decay than parameters with small gradients, an arbitrary, unintended coupling with no principled justification. **AdamW** (Loshchilov & Hutter, 2017) decouples this: apply Adam's ordinary adaptive update to the raw gradient (no `λθ` folded in), then separately subtract `lr·λ·θ` directly: `θ ← θ - lr·(m̂_t/(sqrt(v̂_t)+ε) + λθ)` — weight decay now shrinks every parameter by the same proportional amount regardless of that parameter's current adaptive gradient scaling, matching what "weight decay" is actually supposed to mean. This is not a subtle theoretical nicety — empirically, AdamW measurably out-generalizes Adam-with-L2 on the same tasks, which is precisely why AdamW (not plain Adam) is the default optimizer choice in virtually all modern training code.

### Lion: sign-based updates, no second moment at all

Lion ("EvoLved Sign Momentum," Chen et al., 2023, discovered via program search over optimizer designs) maintains only a *single* momentum-like term but updates using its **sign**, not its magnitude: `c_t = β1·m_{t-1} + (1-β1)·g_t`, `θ ← θ - lr·sign(c_t)`, `m_t = β2·m_{t-1} + (1-β2)·g_t` (note `m` is updated *after* being used to form `c`, with its own separate decay rate). Every parameter's update has the *same* magnitude (`lr`, since `sign(·)∈{-1,+1}`) regardless of that parameter's actual gradient scale — a deliberately different tradeoff from Adam's magnitude-adaptive approach — and critically, Lion never needs to store a second moment (`v`) at all, roughly halving optimizer-state memory versus Adam/AdamW, which matters meaningfully at billion-plus parameter scale where optimizer state itself is a substantial fraction of total training memory. In practice, Lion typically needs a *smaller* learning rate and *larger* weight decay than AdamW to train stably, since a uniform-magnitude update is much more aggressive per-step than Adam's naturally-scaled one.

### Muon: orthogonalizing the update, exploiting matrix structure directly

Muon ("Momentum Orthogonalized by Newton-Schulz," Keller Jordan, 2024-2025) takes a structurally different approach: rather than treating each parameter as an independent scalar (as Adam, AdamW, and Lion all do), it exploits the fact that most deep learning parameters are genuinely **2D matrices** (weight matrices of linear/attention layers). Muon computes an ordinary SGD-momentum update, then applies a few iterations of the **Newton-Schulz iteration** to the resulting update matrix — an efficient, matrix-multiplication-only method that approximates replacing the update matrix with the nearest semi-orthogonal matrix (informally, "flattening" the update's singular values toward a common scale rather than letting a few dominant directions dominate the step). This is applied only to genuinely 2D parameters (weight matrices); embeddings, biases, and normalization parameters typically still use AdamW alongside it in practice. Reported results as of 2026: Muon achieves roughly 2x the compute efficiency of AdamW at compute-optimal training scale, and has moved from research paper to demonstrated production use in training trillion-parameter models (Kimi K2/2.5, GLM-4.5/4.7, and DeepSeek reporting Muon used in most modules of DeepSeek-V4, including its 1.6-trillion-parameter DeepSeek-V4-Pro model) — with NVIDIA integrating Muon support directly into the Megatron Core training framework as of an April 2026 release, reporting near-parity training throughput with AdamW while improving model quality at that scale.

### Learning rate schedules: why warmup, why decay

**Warmup** (a short linear ramp of the learning rate from near-zero up to its target value over the first few hundred to few thousand steps) exists because the earliest training steps are the *least* reliable signal available: weights are at their initialization-time scale (not yet adapted to the actual data), and — as shown numerically above — Adam's own moment estimates are the least accurate they'll ever be during exactly this window, before the moving averages have had enough steps to reflect the true gradient statistics well (even with bias correction handling the zero-initialization bias exactly, the moving averages are still built from very few actual samples early on, so their *variance* as estimators is high). Taking a large step based on this unreliable early signal risks a bad, hard-to-recover-from update; warmup avoids this by keeping early steps small until the signal has had time to stabilize. **Decay** (cosine or step-based reduction of the learning rate over the back half or more of training) exists because a large learning rate that finds a good general region of the loss landscape quickly is often too large to settle precisely into a sharp, low-loss minimum within that region — reducing the learning rate later in training lets the optimizer take smaller, more precise steps once it's already in a good neighborhood, generally converging to a measurably better final loss than holding the learning rate constant throughout.

---

## Build it from scratch

```python
# untested sketch -- illustrates the Adam update with bias correction, matching
# the numeric example above exactly when run with a constant gradient
def adam_step(theta, g, m, v, t, lr=0.001, beta1=0.9, beta2=0.999, eps=1e-8, wd=0.0):
    m = beta1 * m + (1 - beta1) * g
    v = beta2 * v + (1 - beta2) * g * g
    m_hat = m / (1 - beta1 ** t)
    v_hat = v / (1 - beta2 ** t)
    theta = theta - lr * (m_hat / (v_hat ** 0.5 + eps) + wd * theta)   # AdamW: wd applied directly
    return theta, m, v

def lion_step(theta, g, m, t, lr=1e-4, beta1=0.9, beta2=0.99, wd=0.01):
    c = beta1 * m + (1 - beta1) * g
    theta = theta - lr * ((1 if c > 0 else -1 if c < 0 else 0) + wd * theta)
    m = beta2 * m + (1 - beta2) * g
    return theta, m
```
A from-scratch Newton-Schulz orthogonalization step (the core of Muon) and a from-scratch cosine-with-warmup learning rate schedule are the lab exercises in `labs/python/05-optimization/`, alongside reproducing the bias-correction table above and confirming it against a from-scratch implementation run with a genuinely noisy (not constant) gradient sequence, to see the same warm-up-rate mismatch play out with realistic, non-degenerate data.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Loss diverges to `nan` in the very first few steps of training a new architecture | Initialization variance too large for the actual activation function/depth combination (e.g. using Xavier init with a ReLU network, or a custom architecture with no principled init at all) | Match initialization scheme to activation function (He for ReLU-family, Xavier for tanh/sigmoid/linear); check framework defaults are actually being applied to every custom layer, not just the standard ones |
| Model trains noticeably worse (generalizes worse) with Adam than an equally-tuned SGD+momentum baseline, on the same architecture | Using plain Adam with L2 regularization folded into the gradient, rather than AdamW's decoupled weight decay — the coupling arbitrarily reduces effective weight decay for parameters with large adaptive gradient scaling | Switch to AdamW (`torch.optim.AdamW`, not `torch.optim.Adam` with a `weight_decay` argument that some older implementations couple incorrectly) and re-tune weight decay separately from learning rate |
| Training loss is unstable / oscillates significantly during the first several hundred steps, then stabilizes | No learning-rate warmup, combined with Adam's moment estimates being high-variance during the earliest steps | Add a short linear (or similar) warmup period before the main learning rate schedule takes over |
| BatchNorm-using model performs noticeably worse at inference (batch size 1, or a very different batch composition than training) than validation metrics during training suggested | BatchNorm's running statistics (tracked during training for inference-time use) don't match the actual inference-time batch composition/distribution well, or the model was evaluated in training mode (using current-batch statistics) rather than eval mode (using tracked running statistics) | Confirm `model.eval()` (or equivalent) is set before inference, and that running statistics were tracked over a representative distribution of training data |
| Optimizer state memory dominates total training memory at large model scale, limiting achievable batch size or model size on available hardware | Adam/AdamW's second moment (`v`) doubles optimizer-state memory versus SGD+momentum, and both moments together can exceed the parameter memory itself at scale | Consider Lion (no second moment, roughly half the optimizer-state memory of AdamW) or 8-bit/low-precision optimizer state implementations if memory, not final quality, is the binding constraint |

---

## Tradeoffs & when NOT to use it

- **Don't assume He/Xavier init is a free, universal default regardless of architecture.** Very deep networks, unusual activation functions, or networks with significant custom structure (e.g. certain normalizing-flow or specific residual-scaling architectures) may need architecture-specific initialization derivations beyond the generic Xavier/He formulas — verify empirically (check early-training activation/gradient statistics) rather than assuming the generic formula transfers to every architecture.
- **Don't switch to Lion or Muon purely because they're newer.** AdamW remains an extremely strong, well-understood, well-tuned default; Lion's memory savings and Muon's compute efficiency are real but come with different, less-extensively-battle-tested hyperparameter sensitivities (Lion typically needs a notably smaller learning rate and larger weight decay than AdamW; Muon is applied only to 2D matrix parameters and requires a mixed setup with AdamW for the rest) — reach for them when the specific problem they solve (memory at scale for Lion, compute efficiency at very large pretraining scale for Muon) is actually your binding constraint, not by default.
- **Don't use BatchNorm in architectures/settings with small or highly variable batch sizes.** Its cross-batch-statistics dependency degrades meaningfully at small batch size and is awkward in streaming/online inference settings — LayerNorm or RMSNorm are the correct default whenever batch composition can't be relied upon to be large and representative.
- **Don't skip learning-rate warmup for adaptive optimizers (Adam/AdamW) on any large-scale or from-scratch training run.** The bias-correction-independent "moving averages built from very few samples early on" problem this module derives is real regardless of architecture; warmup is cheap insurance against a genuinely destabilizing early large-magnitude update, and skipping it to save a few hundred steps of wall-clock time is rarely a good trade at real training scale.

---

## Interview questions

### Q1 — Derive why He initialization uses double the variance of Xavier initialization.
**Testing:** whether the ReLU-specific correction is understood mechanically, not just memorized as "He is for ReLU."
**Answer:** Xavier's derivation assumes activations that don't systematically zero out inputs (roughly symmetric around zero, like tanh) — keeping `Var(z)≈Var(x)` forward requires `σw²=1/fan_in` (or the `2/(fan_in+fan_out)` compromise with the backward-pass argument). ReLU zeroes out roughly half its inputs (everything negative), which halves the variance passing through relative to that assumption — compensating for that halving requires doubling the variance target, giving `σw²=2/fan_in`.
**Follow-up trap:** *"Compute the actual std for a 784->256 layer under both schemes."* — Xavier: `sqrt(2/(784+256))≈0.04385`; He: `sqrt(2/784)≈0.05051` — He's is measurably larger, exactly reflecting the doubled variance target.

### Q2 — Why does BatchNorm behave differently at inference time than during training, and what specifically goes wrong if you forget to switch modes?
**Testing:** a concrete, common production bug tied directly to BatchNorm's mechanism.
**Answer:** During training, BatchNorm normalizes using the *current mini-batch's* statistics (mean/variance computed across the batch dimension), while also updating a running estimate of those statistics. At inference, it uses the *tracked running statistics* instead (since a single inference-time example, or a differently-composed batch, has no meaningful "batch statistics" of its own to normalize against). Forgetting to switch to eval mode means inference uses the current (possibly tiny, possibly single-example) batch's own statistics instead of the stable running estimate, producing inconsistent, batch-composition-dependent outputs at inference.
**Follow-up trap:** *"Why doesn't LayerNorm have this training/inference mode distinction?"* — LayerNorm normalizes per-example, across features, so its statistics never depend on other examples in the batch at all — there's no "batch statistics vs. running statistics" distinction to get wrong, which is one of the practical reasons it's a simpler default for architectures/settings with variable or small batch sizes.

### Q3 — Compute the LayerNorm output for a single example with features `[1.0, 2.0, 3.0, 4.0]` (ignore epsilon for the mental estimate, but include it in the precise answer).
**Testing:** actual arithmetic execution, not just the formula.
**Answer:** `μ=2.5`, `σ²=1.25`, `std=sqrt(1.25+ε)≈1.11804`, giving normalized output `[-1.34164, -0.44721, 0.44721, 1.34164]` (before applying any learned `γ, β` affine transform).
**Follow-up trap:** *"How would RMSNorm's output differ for the same input, and why?"* — RMSNorm skips mean-centering: `rms=sqrt(mean(x²)+ε)=sqrt(7.5+ε)≈2.73861`, giving `[0.36515, 0.73030, 1.09544, 1.46059]` — a different, non-zero-mean output, since nothing was subtracted before rescaling; the tradeoff is RMSNorm is cheaper (no mean computation/subtraction) and empirically matches LayerNorm's quality in large transformer stacks despite this simplification.

### Q4 — Why does Adam need bias correction, and what would go wrong without it, concretely?
**Testing:** the mechanical reason, illustrated with actual drift, not just "it's biased toward zero."
**Answer:** Both `m` and `v` are initialized to zero, and their exponential-moving-average updates are biased toward that zero initialization especially in early steps. With a constant gradient of `1.0`, `β1=0.9`, `β2=0.999`: bias-corrected `m_hat` and `v_hat` are exactly `1.0` at every single step (correctly reflecting the true average immediately), while the raw, uncorrected `m/sqrt(v)` ratio drifts from `3.16x` too large at step 1 upward over the following steps, because `β1=0.9` "warms up" to steady-state in roughly 10 steps while `β2=0.999` needs roughly 1000 steps — the mismatch in warm-up rates between the two moving averages produces an uncontrolled, time-varying effective step size without correction.
**Follow-up trap:** *"Does this matter much in practice, given training runs for many thousands of steps?"* — it matters disproportionately for exactly the first several hundred steps, which is also when learning-rate warmup is separately doing its own stabilizing work — the two mechanisms (bias correction, warmup) address related but distinct instabilities in that same early window, and skipping either one leaves a real, measurable early-training instability that a longer total training run doesn't retroactively fix.

### Q5 — What specific bug does AdamW fix relative to Adam-with-L2-regularization, and why does it matter for generalization, not just optimization speed?
**Testing:** the decoupling argument precisely, not a vague "AdamW is better."
**Answer:** Folding weight decay into the gradient (`g ← g+λθ`) before Adam's adaptive `m`/`v` update means the weight-decay portion of the update gets divided through by `sqrt(v̂)` along with the rest of the gradient — parameters with large recent gradient magnitude (large `v̂`) receive proportionally *less* effective weight decay than parameters with small gradients, an arbitrary, unintended coupling with no principled justification for why weight decay's shrinkage rate should depend on a parameter's gradient-magnitude history. AdamW instead applies `λθ` as a separate, direct term (`θ ← θ - lr·(m̂/(sqrt(v̂)+ε) + λθ)`), giving every parameter the same proportional shrinkage regardless of its adaptive gradient scaling — matching what weight decay as a regularizer is actually supposed to accomplish, which is why AdamW measurably out-generalizes Adam-with-L2 empirically, not merely trains faster.
**Follow-up trap:** *"Would this bug matter for a network trained with SGD+momentum instead of Adam?"* — no, or much less so — SGD+momentum has no per-parameter adaptive scaling term (`v̂`) to interact with weight decay in the first place, so folding L2 regularization into the gradient there doesn't create the same arbitrary coupling; the AdamW fix is specifically about interaction with *adaptive* per-parameter scaling, which only adaptive optimizers (Adam-family) have.

### Q6 — Explain what Lion trades away relative to Adam/AdamW, and when that tradeoff is actually worth it.
**Testing:** whether "Lion is more memory-efficient" is understood as a real, specific tradeoff rather than a strictly-better replacement.
**Answer:** Lion updates by `sign(momentum)` rather than a magnitude-adaptive term, so it never needs a second moment (`v`) at all — roughly halving optimizer-state memory versus Adam/AdamW, which matters meaningfully at billion-plus parameter scale where optimizer state is a substantial fraction of total training memory. The tradeoff: every parameter's update has identical magnitude (`lr`) regardless of that parameter's actual gradient scale, which is a much more aggressive per-step update than Adam's naturally-scaled one, typically requiring a smaller learning rate and larger weight decay to train stably.
**Follow-up trap:** *"If memory isn't your binding constraint, is there still a reason to prefer Lion over AdamW?"* — not obviously — Lion's primary, well-evidenced advantage is optimizer-state memory savings at scale; absent that specific constraint, AdamW remains the more extensively validated, better-understood default, and switching to Lion without the memory pressure that motivates it mostly just adds a different, less-familiar hyperparameter sensitivity profile for no corresponding benefit.

### Q7 — What structural idea does Muon exploit that Adam, AdamW, and Lion all miss, and what's the actual mechanism?
**Testing:** the specific technical content of Muon's innovation, not just "it's a new, faster optimizer."
**Answer:** Adam/AdamW/Lion all treat every parameter as an independent scalar, adapting or sign-thresholding each one separately with no awareness that most deep learning parameters are genuinely 2D matrices with their own structure (e.g. weight matrices of linear/attention layers). Muon computes an ordinary momentum update, then applies a few Newton-Schulz iterations to the resulting update *matrix*, approximating replacement with the nearest semi-orthogonal matrix — informally, flattening the update's singular value spectrum rather than letting a handful of dominant directions dominate the step, which is a genuinely matrix-structure-aware operation with no scalar-per-parameter analogue.
**Follow-up trap:** *"Is Muon applied to every parameter in a model?"* — no; it's applied specifically to genuinely 2D weight matrices, with embeddings, biases, and normalization parameters typically still handled by AdamW alongside it in the same training run — Muon is a targeted replacement for the specific parameter class its matrix-structure argument applies to, not a universal drop-in replacement for every parameter tensor in a model.

### Q8 — Why does learning-rate warmup matter specifically for Adam/AdamW, beyond the generic "early training is unstable" intuition?
**Testing:** connecting warmup directly to the bias-correction/moment-estimator-variance argument from earlier in this module, not treating it as an unrelated heuristic.
**Answer:** Even with bias correction exactly compensating for the zero-initialization bias (as shown numerically above), the moving averages `m` and `v` are still estimated from very few actual gradient samples during the earliest steps, giving them high *variance* as estimators regardless of the bias correction — a large learning rate applied to a high-variance, still-settling gradient-magnitude estimate risks a disproportionately large, badly-calibrated step exactly when the signal is least trustworthy. Warmup keeps the learning rate small during this specific window, independent of and complementary to bias correction, which fixes a different (mean-bias, not variance) part of the same early-training instability.
**Follow-up trap:** *"Would warmup matter as much for plain SGD without momentum?"* — less so — SGD without momentum or adaptive per-parameter scaling doesn't have moving-average estimators that need to "settle," so the specific instability warmup addresses for Adam (unreliable early moment estimates) doesn't apply in the same way; SGD-based training schedules still sometimes use warmup, but the strongest, most specific justification for it is tied to adaptive optimizers' moment-estimation behavior.

### Q9 — A colleague proposes using BatchNorm in a Transformer decoder used for streaming, token-by-token autoregressive generation. What's wrong with this, mechanically?
**Testing:** applying the BatchNorm-vs-LayerNorm distinction to a concrete architectural decision, not just reciting "transformers use LayerNorm."
**Answer:** Autoregressive, token-by-token generation processes one token (often batch size 1, or a small and highly variable batch across concurrent requests, per the batching discussion in `T16-gpu-arch`) at a time — BatchNorm's statistics, computed across the batch dimension, become meaningless or highly unstable at batch size 1, and would need to fall back on running statistics that may not represent the actual streaming input distribution well. LayerNorm/RMSNorm normalize per-example across the feature dimension, entirely independent of batch composition, which is exactly why they (not BatchNorm) are the standard choice for transformer architectures regardless of whether they're used in training (large batches) or streaming inference (batch size 1 or highly variable).
**Follow-up trap:** *"Is there any context where BatchNorm's cross-example dependency is actually a feature rather than a bug?"* — yes, in some specific settings (e.g. certain contrastive/self-supervised learning setups, or explicitly wanting batch statistics as a form of implicit regularization/information sharing across a training batch) the cross-example coupling has been used deliberately — but this is the exception, not the default reason to choose BatchNorm, and doesn't apply to the streaming-inference scenario in this question.

### Q10 — Design question: you're pretraining a new, from-scratch transformer architecture at a scale where optimizer-state memory is limiting your maximum batch size. Walk through your options and how you'd decide between them.
**Testing:** staff-level synthesis across the whole optimizer/memory tradeoff space covered in this module.
**Answer:** First quantify the actual constraint: AdamW's two moments (`m`, `v`) at full precision can together approach or exceed parameter memory itself at large scale — check whether reducing optimizer-state precision (8-bit optimizer states, a memory-engineering technique, distinct from the optimizer algorithm itself) alone resolves the constraint before changing the optimizer algorithm. If a genuinely smaller optimizer footprint is still needed, Lion removes the second moment entirely (roughly half of AdamW's optimizer-state memory) at the cost of needing to re-tune learning rate (smaller) and weight decay (larger) and re-validate final model quality, since Lion's aggressive uniform-magnitude update behaves differently than AdamW's. If compute efficiency at very large scale (not just memory) is also a goal and the architecture consists mostly of large 2D weight matrices, Muon is worth piloting on a smaller-scale run first (given it's a comparatively newer, less universally battle-tested choice as of 2026) before committing the full training budget to it.
**Follow-up trap:** *"What would make you NOT switch away from AdamW despite the memory pressure?"* — if the memory savings from 8-bit optimizer states alone already resolve the actual constraint, or if the team's tuned hyperparameters, monitoring, and debugging playbooks are all built around AdamW's well-understood behavior, switching optimizers introduces real re-validation cost and risk that may not be worth it unless the memory or compute pressure is severe enough that no lower-risk option resolves it — "well-understood and slightly less memory-efficient" is frequently the better production choice over "newer and less battle-tested," a genuinely senior-level judgment call, not a purely technical one.

---

## Red flags that fail you

- Cannot derive why He initialization is `2/fan_in` while Xavier is `2/(fan_in+fan_out)`, or can't compute either for a specific layer size.
- Confuses BatchNorm and LayerNorm's normalization axis, or doesn't know why transformers default to LayerNorm/RMSNorm over BatchNorm.
- Cannot explain why Adam needs bias correction beyond "it's biased," with no mechanism or numeric illustration.
- Believes AdamW is "just Adam with weight decay" rather than understanding the specific decoupling fix and why it matters for generalization.
- Cannot name what problem each step in the SGD → Momentum → Adam → AdamW → Lion → Muon lineage actually fixes.
- Recommends switching optimizers or normalization schemes without connecting the choice to an actual, identified constraint (memory, batch size, compute budget).

---

## Cheat card

```
INIT (keep per-layer signal/gradient factor ~1 at t=0):
  Xavier/Glorot (tanh/linear): Var(W)=2/(fan_in+fan_out); 784->256: std=0.04385
  He (ReLU):                  Var(W)=2/fan_in (2x Xavier: ReLU kills ~half units)
                               784->256: std=0.05051

NORM (keep training healthy afterward):
  BatchNorm: normalize across BATCH, per feature -- batch-size-dependent, needs
    running stats at inference (model.eval()!)
  LayerNorm: normalize across FEATURES, per example -- batch-independent, default
    for transformers. x=[1,2,3,4] -> mean=2.5,std=1.118 -> [-1.342,-0.447,0.447,1.342]
  RMSNorm: like LayerNorm, NO mean-centering, only RMS rescale -- cheaper, used in
    LLaMA-family. same x -> rms=2.7386 -> [0.365,0.730,1.095,1.461]

OPTIMIZER LINEAGE (each fixes ONE real problem):
  SGD: theta -= lr*g                              (scale-blind, no memory)
  +Momentum: m=beta*m+g; theta-=lr*m               (smooths oscillation)
  Adam: m=EMA(g), v=EMA(g^2), BIAS-CORRECT both, theta-=lr*m_hat/(sqrt(v_hat)+eps)
    bias correction: constant g=1, b1=0.9,b2=0.999 -> corrected update=lr EVERY
    step; UNcorrected drifts 3.16x too big at t=1 (b2 needs ~1000 steps to warm up
    vs b1's ~10) -- NOT optional
  AdamW: wd applied DIRECTLY (theta -= lr*(...+ wd*theta)), NOT folded into
    gradient -- fixes arbitrary large-v_hat params getting LESS effective decay
  Lion (2023): sign(momentum) update, NO second moment -> ~half AdamW's optimizer
    memory; needs smaller lr, bigger wd
  Muon (2024-25): momentum, then NEWTON-SCHULZ ORTHOGONALIZE the update matrix
    (2D weight matrices only, embeddings/bias still AdamW) -> ~2x AdamW compute
    efficiency; production: Kimi K2, GLM-4.5/4.7, DeepSeek-V4 (1.6T params)

LR SCHEDULE: WARMUP (early moment estimates high-variance regardless of bias
  correction) then cosine/step DECAY (settle into a sharper minimum than
  constant LR finds)
```

## Sources

- [Understanding the difficulty of training deep feedforward neural networks — Glorot & Bengio (2010)](https://proceedings.mlr.press/v9/glorot10a/glorot10a.pdf) — accessed 2026-08-03
- [Delving Deep into Rectifiers — He et al. (2015)](https://arxiv.org/abs/1502.01852) — accessed 2026-08-03
- [Adam: A Method for Stochastic Optimization — Kingma & Ba (2014)](https://arxiv.org/abs/1412.6980) — accessed 2026-08-03
- [Decoupled Weight Decay Regularization (AdamW) — Loshchilov & Hutter (2017)](https://arxiv.org/abs/1711.05101) — accessed 2026-08-03
- [Symbolic Discovery of Optimization Algorithms (Lion) — Chen et al. (2023)](https://arxiv.org/abs/2302.06675) — accessed 2026-08-03
- [Muon is Scalable for LLM Training — Liu, Su et al., arXiv](https://arxiv.org/pdf/2502.16982) — accessed 2026-08-03
- [Root Mean Square Layer Normalization — Zhang & Sennrich (2019)](https://arxiv.org/abs/1910.07467) — accessed 2026-08-03
- [NVIDIA Megatron Boosts LLM Training With Muon Optimizer — NVIDIA, April 2026](https://www.mexc.com/news/1047932) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
