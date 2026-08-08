# Activations: Sigmoid, Tanh, ReLU vs Leaky/GELU/SwiGLU, and Sigmoid vs Softmax

> **Track:** T04 Deep Learning · **Time:** 2.0h · **Prereqs:** T03 · **Updated:** 2026-08-01
> **Module id:** `T04-activations` · **Tags:** fundamentals,critical

## The 30-second version

Sigmoid and tanh saturate: their gradients top out at 0.25 and 1.0 respectively and decay to zero away from the origin, which is why deep sigmoid networks stop learning in their early layers — that's the vanishing gradient problem, and it's why ReLU replaced them in hidden layers. ReLU itself dies: a unit whose pre-activation is permanently negative outputs zero forever and gets zero gradient, so it never recovers. Leaky ReLU, PReLU, ELU, and GELU each patch this by keeping a small or smooth gradient for negative inputs, at a small compute cost; GELU and SwiGLU are what actually shipped in production transformers (BERT, GPT, PaLM, LLaMA) because they benchmark better than ReLU on transfer tasks, not because of a single clean theoretical argument. Sigmoid and softmax are not interchangeable: sigmoid gives independent per-class probabilities for multi-label problems and pairs with binary cross-entropy, softmax gives one normalized distribution over mutually exclusive classes and pairs with categorical cross-entropy — swapping them silently breaks the semantics of your loss.

## Why this gets asked

Because "what activation would you use and why" is the fastest way to check whether a candidate actually understands backprop or is pattern-matching from a table they memorized. The interviewer has debugged a network that stopped learning after adding depth, traced it to saturated sigmoids or a layer of dead ReLUs, and wants to know if you'd have caught it before it cost a training run. The sigmoid-vs-softmax question specifically catches people who ship a softmax on a multi-label problem (or vice versa) and get confidently wrong probabilities that still "look" fine in a spot check.

---

## Lineage: past → present → future

**What came before.** Early neural nets (1980s–2000s) used sigmoid and tanh almost exclusively because they were the biologically-motivated, smoothly differentiable choice and because backprop's chain rule needed a nonzero derivative everywhere. The pain showed up once networks got deeper than 2-3 layers: the sigmoid derivative is at most 0.25, so a gradient passing back through even four sigmoid layers is attenuated by at least 0.25⁴ ≈ 1/256 before accounting for weight magnitudes, and real weights push it further toward zero. Hochreiter's 1991 thesis and Bengio et al. (1994) formalized this as the vanishing gradient problem, and it is the direct reason plain deep MLPs and vanilla RNNs were considered untrainable past a handful of layers for two decades.

**Where it stands now.** ReLU (Nair & Hinton, 2010, popularized by AlexNet in 2012) is the default for CNNs and most non-transformer hidden layers because it's cheap (one comparison) and doesn't saturate on the positive side. But it introduced its own failure mode — dying ReLU — which the field patched with Leaky ReLU, PReLU, and ELU without any one of them becoming a universal default. Transformers took a different fork entirely: GELU (Hendrycks & Gimpel, 2016) became the BERT/GPT-2 default, and GLU-gated variants — SwiGLU specifically — became the modern LLM default after Shazeer's 2020 "GLU Variants Improve Transformer" showed better perplexity at equal compute. Sigmoid and tanh did not disappear; they moved to where you need a bounded gate or a bounded probability — LSTM/GRU gates, the output layer of a binary or multi-label classifier, and (in a different sense) the gating vector inside SwiGLU itself.
[GLU Variants Improve Transformer — alphaXiv](https://www.alphaxiv.org/overview/2002.05202v1) — accessed 2026-08-01

**Where it's heading.** SwiGLU-style gated FFNs are now the practical consensus for new large transformer pretraining (PaLM, LLaMA family, and most open frontier models use it), and that's shipped, not speculative. What's still unsettled: nobody has a first-principles proof that GELU or Swish is uniquely correct, activation choice keeps coming from large-scale empirical sweeps rather than theory, and the marginal quality gain from switching activations on an already-well-tuned architecture is small compared to data and scale. Expect continued search over gating and normalization jointly (activation choice is no longer discussed independent of RMSNorm/LayerNorm placement) rather than a wholesale replacement of the ReLU family in vision or the GELU/SwiGLU family in transformers.

---

## Mental model

```
Saturating (sigmoid/tanh):          Non-saturating, can die (ReLU):
                                     
  1 ┤        ______                   ┤           ___________
    │      /'                         │         /
    │    /'      gradient≈0            │       /   gradient=1
    │   |         out here             │     /
  0 ┤__/'________                    0 ┤___/_____________
    -6   0    6                        -6   0    6
                                       gradient = 0 for all x<0 — if a unit's
  max slope 0.25 (sigmoid)             pre-activation stays negative across
  or 1.0 (tanh) at x=0,                the whole batch, that gradient is 0
  decays to 0 either side.             and never recovers ("dead ReLU").

Smooth compromise (GELU/Swish/ELU): small negative gradient survives, no hard
cliff at zero, closer to a soft, input-dependent gate than a fixed threshold.
```

The one-line framing an interviewer wants: **saturating activations trade "bounded, interpretable as probability/gate" for "gradient dies at the extremes"; ReLU trades "gradient never dies on the active side" for "gradient is exactly zero, permanently, on the inactive side"; GELU/Swish/ELU are attempts to get a nonzero gradient everywhere without paying the saturation cost of sigmoid.**

---

## How it actually works

### Sigmoid

```
σ(x) = 1 / (1 + e^-x)          σ'(x) = σ(x)(1 - σ(x))
```

`σ'(x)` is maximized at `x=0` where `σ(x)=0.5`, giving `σ'(0) = 0.5 × 0.5 = 0.25`. That 0.25 ceiling is the number to know cold: it means every sigmoid layer you backprop through multiplies the incoming gradient by **at most** 0.25, and typically much less once you're a few units away from zero (at `x=±4`, `σ(x)≈0.982/0.018` and `σ'(x)≈0.018`, a 14x smaller gradient than at the peak). Stack 5 sigmoid layers and even at the best possible point the gradient has shrunk by `0.25⁵ ≈ 0.001` before weight magnitudes are even multiplied in — this is the vanishing gradient problem, quantitatively, not just a name.

Sigmoid is also not zero-centered: its output is always in `(0,1)`, strictly positive. That matters for what happens to the *next* layer's weight gradients, not this layer's — see tanh below.

### Tanh

```
tanh(x) = 2σ(2x) - 1           tanh'(x) = 1 - tanh(x)²
```

Same saturation shape, but zero-centered (`range (-1,1)`) and a steeper max derivative: `tanh'(0) = 1`. Zero-centering matters because if every activation feeding into a neuron is positive (as with sigmoid), the gradient with respect to that neuron's weights is forced to have the same sign in every component — all-positive or all-negative — which makes gradient descent zigzag instead of moving directly toward the optimum. Tanh's outputs straddle zero so the weight-update direction isn't artificially constrained. Tanh still saturates, so it doesn't fix vanishing gradients, only the zigzag problem — that's why LSTM gates use sigmoid (need a 0-1 gate) but the cell-state candidate uses tanh (need a zero-centered value to add).

### ReLU and the dying-neuron failure

```
ReLU(x) = max(0, x)            ReLU'(x) = 1 if x>0 else 0   (undefined at 0, taken as 0)
```

No saturation on the positive side — gradient is exactly 1, full stop, no decay with depth on the active path. This alone is most of why ReLU made 20+ layer networks trainable.

**The failure mode, named:** if a unit's weighted input is negative for every example in a batch (often from a large negative bias update or an unlucky init combined with a high learning rate), its output is 0 for all of them, its local gradient is 0, so no gradient flows back through it and its weights never update again. It is now permanently dead. **Observable symptom:** in a training-time activation histogram or a hook that logs `(activations == 0).float().mean(dim=0)` per unit, a dead unit shows exactly 100% zeros across an entire evaluation batch, indefinitely, not just "mostly zero." Reported dead-unit rates of 20-50% are common in poorly-tuned deep ReLU nets trained with an aggressive learning rate.

```python
# untested sketch — dead-ReLU detector
import torch

def dead_relu_fraction(model, loader, layer_name):
    acts = []
    def hook(_, __, out): acts.append(out.detach())
    h = dict(model.named_modules())[layer_name].register_forward_hook(hook)
    with torch.no_grad():
        for x, _ in loader:
            model(x)
    h.remove()
    all_acts = torch.cat(acts, dim=0)          # [N, C, ...]
    dead = (all_acts <= 0).all(dim=0).float().mean()
    return dead.item()                          # fraction of units dead on EVERY example
```

### The fixes, and what each costs

| Variant | Formula (x<0) | Fixes | Costs |
|---|---|---|---|
| **Leaky ReLU** | `αx`, α≈0.01 fixed | Small constant gradient (`α`) for negative inputs, so units can recover | One more hyperparameter; α is rarely tuned so the fix is weak |
| **PReLU** | `αx`, α learned per-channel | Lets the network pick the leak per channel instead of guessing | Extra learnable params (negligible count), can overfit on small data |
| **ELU** | `α(e^x - 1)` | Smooth, pushes mean activation toward 0 (helps like tanh's zero-centering), no hard kink | `exp()` is slower than a compare; still saturates to `-α` for very negative x |
| **GELU** | `x·Φ(x)` (Φ = standard normal CDF) | Smooth, non-monotonic dip just below 0, weights inputs by their probability of being "kept" rather than a hard 0/1 gate | More expensive than ReLU; usually approximated with tanh for speed |
| **SwiGLU** | gated: `Swish(xW)⊙(xV)` inside the FFN | Input-dependent multiplicative gate, not just an elementwise nonlinearity — empirically best perplexity/compute tradeoff for transformer FFNs | 50% more parameters in the FFN block for the same hidden width (two projections `W`,`V` instead of one), so implementations shrink `d_ff` to keep parameter count matched |

PyTorch's `nn.GELU(approximate='none')` is the exact erf-based formula by default; `approximate='tanh'` gives the faster tanh approximation used in the original GPT-2/BERT implementations.
[GELU — PyTorch documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.GELU.html) — accessed 2026-08-01

**Why GELU/SwiGLU in modern transformers specifically:** Hendrycks & Gimpel motivated GELU as a stochastic-regularization view (it's the expected value of `x` under a random Bernoulli-gate whose probability rises with `x`, giving a smooth version of ReLU-with-dropout). That's a reasonable story but not the actual reason transformers use it — the actual reason is empirical: BERT and GPT-2 benchmarked GELU above ReLU on their downstream tasks, and Shazeer's 2020 paper swept ReLU/GELU/Swish against their GLU-gated counterparts (ReGLU, GEGLU, SwiGLU) under a fixed compute budget and found the gated variants won consistently, with SwiGLU marginally ahead. PaLM and the LLaMA family adopted SwiGLU on that basis. No architecture paper claims a first-principles proof that this is optimal — it's the best of a systematic sweep, and that's the honest answer to give.
[GLU Variants Improve Transformer — alphaXiv](https://www.alphaxiv.org/overview/2002.05202v1) — accessed 2026-08-01

### Sigmoid vs softmax, precisely

```
sigmoid (per output, independent):        softmax (jointly normalized):
σ(z_i) = 1/(1+e^-z_i)                     softmax(z)_i = e^(z_i) / Σ_j e^(z_j)

Σ_i σ(z_i)  ≠ 1  in general               Σ_i softmax(z)_i = 1  always
```

- **Sigmoid** — one independent probability per output unit. Use for **multi-label** classification (an image can be "cat" AND "outdoor" AND "daytime" simultaneously) or a single binary decision. Pairs with **binary cross-entropy**, applied per-output-unit and summed/averaged.
- **Softmax** — outputs are coupled: raising one logit necessarily lowers every other output's probability, because they're forced to sum to 1. Use for **multi-class, mutually-exclusive** classification (exactly one of {cat, dog, bird}). Pairs with **categorical cross-entropy** (`-log(softmax(z)_true_class)`).

Getting this backwards is a real, observable bug: put softmax on a multi-label head and the model is mathematically prevented from being confident about two classes at once — pushing up "cat" necessarily pushes down "outdoor" even when both are true — and BCE loss on raw softmax outputs (or vice versa, CE loss on independent sigmoids) trains against a probability model that doesn't match the label structure, producing systematically miscalibrated confidence that often still "looks plausible" in a quick check.

**The max-subtraction trick, and why it's necessary, not just nice-to-have:**

```python
# untested sketch
import numpy as np

def softmax_naive(z):
    e = np.exp(z)                    # e^1000 -> inf in float64/float32
    return e / e.sum()

def softmax_stable(z):
    z = z - np.max(z)                # shifts largest logit to 0, rest <= 0
    e = np.exp(z)                    # e^0=1 max, no overflow; small values may underflow to 0, which is fine
    return e / e.sum()
```

`softmax(z) = softmax(z - c)` for any constant `c` — subtracting a constant from every logit doesn't change the ratio because it factors out of both numerator and denominator (`e^(z_i - c) = e^(z_i)·e^(-c)`, and `e^(-c)` cancels in the division). Subtracting the max makes the largest exponent argument exactly 0 (`e^0=1`, no overflow) and every other argument ≤ 0 (`e^x ≤ 1`, underflows to 0 at worst, which is numerically harmless). Without this, logits as small as ~89 overflow `float32`'s `exp()` (`e^89 ≈ 4.9e38`, right at `float32` max `~3.4e38`) and you get `NaN` from `inf/inf`. This is why every real framework's softmax and cross-entropy implementation (`torch.nn.functional.cross_entropy`, `torch.nn.LogSoftmax`) does the subtraction internally and why you should never re-implement softmax without it.

---

## Build it from scratch

```python
# untested sketch — forward + backward for the core activations, numpy only
import numpy as np

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_grad(x):
    s = sigmoid(x)
    return s * (1 - s)

def tanh_grad(x):
    t = np.tanh(x)
    return 1 - t**2

def relu(x):
    return np.maximum(0, x)

def relu_grad(x):
    return (x > 0).astype(x.dtype)

def leaky_relu(x, alpha=0.01):
    return np.where(x > 0, x, alpha * x)

def leaky_relu_grad(x, alpha=0.01):
    return np.where(x > 0, 1.0, alpha)

def gelu_exact(x):
    from scipy.special import erf
    return 0.5 * x * (1 + erf(x / np.sqrt(2)))

def gelu_tanh_approx(x):
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))

def softmax_stable(z, axis=-1):
    z = z - np.max(z, axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)

def bce_loss(probs, targets, eps=1e-12):
    p = np.clip(probs, eps, 1 - eps)
    return -np.mean(targets * np.log(p) + (1 - targets) * np.log(1 - p))

def cross_entropy_loss(probs, target_idx, eps=1e-12):
    # target_idx: integer class index per row
    n = probs.shape[0]
    p_true = np.clip(probs[np.arange(n), target_idx], eps, 1.0)
    return -np.mean(np.log(p_true))
```

Full derivations of the surrounding forward/backward pass and gradient checking live in `T04-neural-net-math` and `T04-backprop-derivation`; this module covers the activation functions and their gradients in isolation.

---

## How it's done in production

| Framework/Layer | Default activation | Notes |
|---|---|---|
| PyTorch CNN blocks | `nn.ReLU(inplace=True)` | `inplace=True` saves memory, breaks autograd if the input is needed elsewhere — a real bug source |
| PyTorch Transformer FFN (built-in `nn.TransformerEncoderLayer`) | `F.relu` by default, switchable to `F.gelu` | Most from-scratch LLM implementations override this to GELU or a SwiGLU FFN block |
| HuggingFace BERT/GPT-2 configs | GELU (`gelu` or `gelu_new`, the tanh approximation) | `gelu_new` matches the original TF implementation's approximation |
| LLaMA / PaLM style FFN | SwiGLU, `d_ff` shrunk to ~(2/3)×4d to hold parameter count roughly constant vs a ReLU FFN with `d_ff=4d` | Because SwiGLU needs two projection matrices (`W`, `V`) where a plain FFN needs one |
| LSTM/GRU gates | sigmoid for gates, tanh for candidate/cell values | Bounded gate semantics require sigmoid; tanh keeps the added value zero-centered |
| Multi-label image tagging heads | sigmoid + BCE per class | Independent probabilities are the point |
| ImageNet-style single-label classifier head | softmax + categorical cross-entropy | Mutually exclusive classes |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Loss plateaus early in a deep sigmoid/tanh MLP; earliest layers' weights barely move over many epochs | Vanishing gradient from saturated sigmoid/tanh compounding across depth | Switch hidden layers to ReLU/GELU; add batch norm/residual connections; keep sigmoid only at output for binary tasks |
| A growing fraction of ReLU units show 0 activation across an entire eval batch, permanently, and training accuracy stalls | Dying ReLU — large negative pre-activation with zero gradient, often from too-high a learning rate or a large negative bias update | Lower the learning rate, switch to Leaky ReLU/PReLU/ELU, use He initialization, add batch norm before the activation |
| Softmax output is `NaN` or all zeros | Logits overflow `exp()` because max-subtraction wasn't applied (custom softmax implementation) | Use the stable softmax (subtract row max) or the framework's fused `log_softmax`/`cross_entropy`, never `log(softmax(x))` computed separately |
| Multi-label model's confidences for co-occurring labels never both exceed ~0.5 even when both are clearly true | Softmax used instead of sigmoid on a multi-label head, forcing outputs to compete for a shared probability mass | Switch head to independent sigmoids + BCE loss |
| Model trained with BCE per-class, but eval code takes `argmax` and reports "accuracy" as if it were single-label | Loss/head function mismatch with eval logic | Align the eval metric (per-label F1/AUC for sigmoid heads) with the loss semantics |
| Training loss is fine but validation is oddly unstable early on, more so than a ReLU baseline at the same LR | ELU's `exp()` term and GELU's smoother curvature interact differently with LR/warmup than ReLU; needs re-tuned warmup | Use the LR schedule that ships with the reference implementation (e.g. GPT-2/BERT warmup schedules), don't reuse a ReLU-CNN LR blindly |

---

## Tradeoffs & when NOT to use it

- **Don't use sigmoid/tanh in the hidden layers of anything more than a handful of layers deep.** The saturating-gradient math above is not a corner case, it's the default outcome past ~4-5 layers without normalization or residual connections. Reserve them for output layers (sigmoid: binary/multi-label; nothing at output for softmax-with-CE since it's typically fused) and for gates inside LSTM/GRU cells where boundedness is the actual requirement.
- **Don't reach for GELU/SwiGLU by default outside transformers.** On CNNs, plain ReLU (or its cheap variants) is still standard and the marginal gain from GELU is usually not worth the extra compute; GELU's benefit is best evidenced inside transformer FFNs specifically, where the empirical sweeps were run.
- **Don't use Leaky ReLU/PReLU as a reflexive fix for a dying-ReLU problem without checking the actual cause.** If units are dying because the learning rate is too high or weights are badly initialized, fixing the optimizer/init is often the correct fix; swapping the activation treats a symptom and can mask a tuning bug.
- **Don't put softmax on a multi-label problem or independent sigmoids on a genuinely mutually-exclusive one.** This is a modeling error, not a hyperparameter choice — get the label structure right first, then pick the activation/loss pair that matches it.
- **ELU and GELU cost real compute at inference.** On latency-sensitive edge deployment, a ReLU/hardswish family activation can be a deliberate accuracy-for-speed tradeoff over GELU — this is exactly why mobile/edge CNN families (MobileNet, EfficientNet-lite) default to ReLU6/hardswish rather than GELU.

---

## Interview questions

### Q1 — Why does sigmoid cause vanishing gradients? Give me the number.
**Testing:** whether the "vanishing gradient" answer is memorized or derived.
**Answer:** `σ'(x) = σ(x)(1-σ(x))`, maximized at `x=0` where `σ=0.5`, giving `σ'(0)=0.25`. That's the best case. Backprop through `n` sigmoid layers multiplies by at most `0.25ⁿ` before weight magnitudes are even factored in — at 5 layers that's a ceiling of `0.25⁵ ≈ 0.001`, and typical pre-activations away from zero push the real derivative well below 0.25, so it's usually worse than the ceiling suggests.
**Follow-up trap:** *"Does batch norm fix this?"* — it helps, indirectly: normalizing pre-activations to roughly zero-mean unit-variance keeps more units near `x=0` where the sigmoid derivative is largest, but it doesn't change the 0.25 ceiling itself. The actual fix for depth is swapping to a non-saturating activation (ReLU family) plus residual connections, which give a gradient path that bypasses the activation's derivative entirely.

### Q2 — Why is tanh preferred over sigmoid in hidden layers when both saturate?
**Answer:** Zero-centering. Sigmoid outputs are always positive, which forces the gradient on the next layer's weights to share a sign pattern across all components, causing a zigzag optimization path. Tanh's `(-1,1)` range removes that constraint. It has a higher peak derivative too (`1.0` vs `0.25`), but it still saturates just as hard away from zero, so it doesn't solve vanishing gradients, only the zigzag issue.
**Follow-up trap:** *"So why do LSTM gates use sigmoid, not tanh?"* — because gates need to represent "how much to let through," a 0-1 fraction, which is exactly sigmoid's range; tanh's `(-1,1)` range is for the cell-state candidate, which needs to be able to add or subtract from the running cell state, i.e. needs to be signed.

### Q3 — Describe the dying ReLU problem and how you'd detect it in a running training job.
**Answer:** A unit whose pre-activation is negative across the entire input distribution outputs 0 everywhere and gets 0 gradient everywhere, so it can never come back to life — it's a permanent failure, not a transient low-activity phase. Detect it with a forward hook logging the fraction of units that are exactly 0 across a full batch (or better, across several batches); a genuinely dead unit shows 100% zeros indefinitely, whereas a merely quiet unit fluctuates.
**Follow-up trap:** *"What learning-rate change would make this worse?"* — a higher learning rate makes large, sign-flipping weight updates more likely, which is what pushes a unit's pre-activation permanently negative in the first place; lowering the LR (or using a warmup) reduces the odds without changing the architecture at all.

### Q4 — Leaky ReLU vs PReLU vs ELU: what do you actually trade?
**Answer:** Leaky ReLU fixes dying units with a small fixed slope (commonly 0.01) for `x<0`, essentially free compute-wise, but that slope is rarely tuned so it's a blunt instrument. PReLU makes the slope a per-channel learnable parameter, letting the network find a better leak, at the cost of a few more (usually negligible) parameters and a slightly higher overfitting risk on small datasets. ELU replaces the linear negative branch with `α(eˣ-1)`, giving a smooth curve and pushing the mean activation toward zero (similar benefit to batch norm/zero-centering), at the cost of an `exp()` call, which is measurably slower than ReLU's single comparison at scale.
**Follow-up trap:** *"If you could only tune one of the three on a real deadline, which?"* — Leaky ReLU. It's a one-line change with no new parameters and captures most of the benefit; PReLU and ELU are refinements you reach for after confirming the simple fix isn't enough.

### Q5 — Why do modern LLMs use SwiGLU instead of plain GELU or ReLU in the FFN?
**Answer:** Shazeer's 2020 "GLU Variants Improve Transformer" swept ReLU, GELU, Swish, and their GLU-gated counterparts (ReGLU, GEGLU, SwiGLU) at fixed compute and found the gated variants win on downstream perplexity, with SwiGLU narrowly best. PaLM and the LLaMA family adopted it on that empirical basis. There's no first-principles proof it's optimal, it's the best result of a systematic sweep — say that plainly rather than inventing a theoretical justification.
**Follow-up trap:** *"SwiGLU needs two projection matrices instead of one — doesn't that blow up parameter count?"* — yes, roughly 50% more FFN parameters at the same hidden width, which is why implementations shrink `d_ff` (commonly to about `2/3` of the `4d` a plain ReLU FFN would use) to hold total parameter count roughly constant across a fair comparison.

### Q6 — What's the difference between GELU's exact and tanh-approximate forms, and does it matter which you use?
**Answer:** Exact GELU is `x·Φ(x)` where `Φ` is the standard normal CDF (computed via `erf`); the tanh approximation swaps in `0.5x(1+tanh(√(2/π)(x+0.044715x³)))`, which is cheaper on hardware without a fast native `erf`. PyTorch's `nn.GELU` defaults to the exact form (`approximate='none'`) unless you explicitly request `approximate='tanh'`. In practice the numerical difference is small enough not to change training outcomes, but it does matter for reproducing a specific checkpoint exactly (BERT/GPT-2's original TF implementation used the tanh approximation, so `gelu_new` in HuggingFace configs matches that, not the exact form).
**Follow-up trap:** *"Would using the wrong variant break loading a pretrained checkpoint?"* — it won't break loading (weights are unaffected), but it can produce small numerical drift from the reference outputs, which matters if you're trying to bit-match a published eval number.

### Q7 — State the difference between sigmoid and softmax precisely, not just "one is for binary and one is for multi-class."
**Answer:** Sigmoid produces an independent probability per output unit; the outputs don't have to sum to 1, and raising one doesn't constrain the others. Softmax produces a normalized joint distribution that always sums to 1, so raising one output's probability necessarily lowers the others. Sigmoid is correct when classes can co-occur (multi-label) or for a single binary decision, and pairs with binary cross-entropy. Softmax is correct when classes are mutually exclusive, and pairs with categorical cross-entropy.
**Follow-up trap:** *"What actually breaks if I use softmax on a multi-label problem?"* — the model is mathematically prevented from expressing high confidence in two labels simultaneously, because the softmax constraint forces the outputs to compete for a shared unit of probability mass; you'll observe confidences for genuinely co-occurring labels that never both exceed ~0.5, which looks like underconfidence but is actually a modeling error.

### Q8 — Why do you subtract the max before exponentiating in softmax?
**Answer:** `softmax(z) = softmax(z - c)` for any constant `c`, because the constant factors out of numerator and denominator and cancels. Subtracting the max makes the largest exponent argument exactly 0 (`e^0=1`, no overflow) and every other argument non-positive (`e^x ≤ 1`, at worst underflows harmlessly to 0). Without it, logits above roughly 89 overflow `float32`'s `exp()` (`e^89` is near `float32`'s max representable value), producing `inf` and then `NaN` from `inf/inf`.
**Follow-up trap:** *"Does this trick change the result?"* — no, it's mathematically identical, purely a numerical-stability transform. If someone claims it changes the output distribution, that's the tell they don't understand why it's applied.

### Q9 — Derive why softmax pairs naturally with cross-entropy — what happens to the gradient?
**Answer:** For the true class `i`, `∂L/∂z_i = softmax(z)_i - 1`, and for any other class `j`, `∂L/∂z_j = softmax(z)_j`. In vector form the gradient of `CE(softmax(z), y)` with respect to the logits is simply `softmax(z) - y_onehot` — the messy chain-rule terms from softmax's own Jacobian and cross-entropy's log cancel almost entirely. This is why frameworks fuse `log_softmax` and `nll_loss` (or expose `cross_entropy` directly operating on logits): it's both more numerically stable and mechanically simpler than computing softmax and cross-entropy separately.
**Follow-up trap:** *"What if I call `log(softmax(x))` manually instead of using `log_softmax`?"* — you lose the numerical stability of the fused implementation; softmax can produce values that underflow to exactly 0 before the log is taken, giving `log(0) = -inf`. `log_softmax` computes the log directly without materializing intermediate probabilities that can underflow.

### Q10 — You inherit a model with training loss that decreases steadily but validation accuracy is stuck near random. The hidden layers use sigmoid, 6 layers deep, no batch norm. Diagnose.
**Testing:** connecting the abstract math to a debugging scenario.
**Answer:** Six sigmoid layers with no normalization is a textbook vanishing-gradient setup — gradients reaching the early layers are attenuated by up to `0.25⁶ ≈ 2.4e-4` before weight magnitudes are applied, so early layers are barely updating at all while later layers overfit to whatever the frozen-ish early representations happen to produce. Training loss can still decrease because the last layer or two are adapting, which is consistent with "training moves, validation doesn't." Fix: switch hidden activations to ReLU/GELU, add batch norm or residual connections, and verify with a per-layer gradient-norm log that early layers are actually receiving signal.
**Follow-up trap:** *"How would you confirm this diagnosis before changing anything?"* — log the L2 norm of the gradient at each layer during a few training steps. A vanishing-gradient case shows norms shrinking by orders of magnitude from the output layer back to the input layer; if the norms are roughly flat across depth, the bug is elsewhere (data leakage, label noise, wrong loss).

### Q11 — When would GELU or ELU actually hurt you compared to ReLU?
**Answer:** On latency-critical edge/mobile inference, where `exp()`/`erf()` calls cost real wall-clock time per activation and there's no accuracy headroom to spend — this is why mobile CNN families like MobileNet and EfficientNet-lite default to ReLU6 or hardswish rather than GELU. Also on small models/small data where the smoother activation's benefit (mostly evidenced in large transformer FFN sweeps) doesn't show up, but the extra compute still costs you.
**Follow-up trap:** *"Isn't the compute difference negligible on modern GPUs?"* — per-call yes, but it's not free at the scale of billions of activations per forward pass across a large model, and on CPU/edge/mobile targets the difference is not negligible at all. Give the concrete deployment context, don't just say "GPUs are fast."

### Q12 — Your multi-label image tagger's per-tag AUC looks fine in aggregate, but a specific pair of frequently co-occurring tags never both fire above 0.5 confidence. What's your first hypothesis?
**Testing:** staff-level debugging: connecting an observed symptom back to a modeling choice.
**Answer:** First hypothesis: the output head is softmax instead of independent sigmoids, so the two co-occurring tags are structurally competing for probability mass even when the underlying features support both being true. Confirm by checking whether the output layer sums to 1 across tags (a dead giveaway for softmax) and whether the loss function is categorical cross-entropy rather than per-tag BCE.
**Follow-up trap:** *"AUC per tag looked fine though — how did that not catch it?"* — AUC is a ranking metric computed per tag independently; it doesn't see joint confidence across tags at all, so a softmax-induced competition between co-occurring labels is invisible to it. You need a joint calibration check (e.g. look at the sum of predicted probabilities for known co-occurring examples) to catch this class of bug.

---

## Red flags that fail you

- Saying "ReLU fixes vanishing gradients" without knowing dying ReLU is a real, separate failure mode it introduces.
- Not being able to state the sigmoid derivative's maximum value (0.25) or derive it.
- Treating sigmoid and softmax as interchangeable, or not knowing which loss pairs with which.
- Claiming softmax "needs" the max-subtraction trick to be mathematically correct, rather than for numerical stability (it's exact either way).
- Recommending GELU/SwiGLU with a made-up theoretical justification instead of citing that it's an empirical result from a compute-matched sweep.
- Not knowing that a "dead" ReLU unit is permanently dead, not just temporarily quiet.
- Confusing zero-centering (tanh's actual advantage over sigmoid) with fixing vanishing gradients (it doesn't).

---

## Cheat card

```
SIGMOID    σ(x)=1/(1+e^-x)   σ'(x)=σ(x)(1-σ(x))   max σ'=0.25 at x=0
           not zero-centered; range (0,1); output-layer binary/multi-label + BCE
TANH       tanh(x)=2σ(2x)-1  max tanh'=1.0 at x=0  zero-centered, range (-1,1)
           still saturates -> doesn't fix vanishing gradient, fixes zigzag updates
VANISHING  n sigmoid layers -> gradient <= 0.25^n ceiling (before weights)
           5 layers: <=0.001 ceiling. Fix: ReLU family + residuals/norm, not more depth.
RELU       max(0,x), grad=1 (x>0) or 0 (x<=0). No saturation on active side.
DYING RELU symptom: unit outputs EXACTLY 0 for 100% of a batch, permanently.
           cause: pre-activation stuck negative (high LR / bad init). detect via forward hook.
LEAKY/PRELU/ELU  leaky: fixed slope ~0.01 for x<0, free. PReLU: learned slope per channel.
           ELU: alpha(e^x-1), smooth + zero-mean push, costs exp().
GELU       x*Phi(x), Phi=normal CDF. PyTorch default approximate='none' (exact, erf-based);
           'tanh' = GPT-2/BERT-style approx. Used because it benchmarks better, no clean proof.
SWIGLU     Swish(xW) (x) (xV) gated FFN. Shazeer 2020, compute-matched sweep winner.
           PaLM/LLaMA use it. ~50% more FFN params at same width -> shrink d_ff to compensate.
SIGMOID vs SOFTMAX
   sigmoid: independent probs, sum != 1, multi-label, pairs with BCE
   softmax: joint dist, sums to 1, mutually exclusive classes, pairs with categorical CE
   softmax+CE gradient simplifies to (softmax(z) - onehot(y)) — why frameworks fuse them
MAX-SUBTRACTION  softmax(z)=softmax(z-c) exactly (constant cancels). Prevents e^x overflow
   (float32 exp overflows near x~89). Numerical stability only, not a different answer.
```

## Sources

- [GLU Variants Improve Transformer — alphaXiv](https://www.alphaxiv.org/overview/2002.05202v1) — accessed 2026-08-01
- [SwiGLU: GLU Variants Improve Transformer (2020) — Naoki Shibuya](https://naokishibuya.github.io/blog/2023-04-30-swiglu-2020/index.html) — accessed 2026-08-01
- [GELU — PyTorch documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.GELU.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
