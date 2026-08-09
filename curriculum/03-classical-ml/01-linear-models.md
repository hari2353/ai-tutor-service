# Linear & Logistic Regression From Scratch: GD, SGD, Momentum, and Adam Derived

> **Track:** T03 Classical ML · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-08-03
> **Module id:** `T03-linear-models` · **Tags:** fundamentals
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Linear regression fits `y_hat = Xw + b` by minimizing mean squared error, which has a closed-form solution (`w = (X^T X)^-1 X^T y`, the normal equation) but that's `O(d^3)` to invert and numerically unstable when `X^T X` is ill-conditioned, so in practice you minimize the same convex quadratic with gradient descent instead. Logistic regression swaps the squared-error loss for binary cross-entropy on top of a sigmoid, and the beautiful fact everyone should have memorized cold is that its gradient is `X^T(sigmoid(Xw) - y)` — structurally identical to linear regression's gradient `X^T(Xw - y)`, just with `sigmoid` inserted, because cross-entropy's derivative and sigmoid's derivative cancel algebraically. Batch gradient descent uses the full dataset per step (correct direction, expensive, one step per epoch); SGD uses one example (noisy, cheap, many steps per epoch); mini-batch is the practical middle ground everyone actually uses. Momentum, RMSprop, and Adam are not competing algorithms so much as a layered set of fixes to plain SGD's two failures — it oscillates across narrow valleys and it uses one learning rate for all parameters regardless of how differently scaled their gradients are — and Adam is just momentum (first moment) plus RMSprop (second moment, per-parameter scaling) plus a bias correction term for the first few steps when both moment estimates are still near zero.

## Why this gets asked

Because it's the fastest filter for "can this person derive a gradient, or do they only know `model.fit()`." An interviewer who has debugged a training run that diverged because the learning rate was too high, or one that took 10x longer to converge than it should have because of an un-normalized feature with a huge dynamic range, asks this to see whether you can look at a loss curve and reason about *why*, not just retry with a smaller learning rate and hope. It's also the question that reveals whether you understand Adam as an engineered fix for two specific, nameable pathologies of vanilla SGD, or as a magic incantation you always reach for.

---

## Lineage: past → present → future

**What came before.** Ordinary least squares predates machine learning as a field by two centuries (Gauss/Legendre, ~1805) and its closed-form solution via the normal equations was the entire story for linear regression until data sizes made `O(d^3)` matrix inversion (or even `O(nd^2 + d^3)` for computing `X^T X` first) impractical, and until `X^T X` being singular or near-singular (perfectly or near-perfectly collinear features) made the inverse numerically garbage even when it existed in theory. Logistic regression (Cox, 1958, building on earlier probit work) had no closed form at all — the log-likelihood's gradient with respect to `w` is transcendental in `w`, so from day one it required iterative optimization (originally Newton-Raphson / iteratively reweighted least squares). The pain that killed "just solve it exactly" for both was the same: real datasets have more features, more collinearity, and more rows than a direct linear-algebra solve tolerates well, and iterative first-order methods scale far better in both dimensions.

**Where it stands now.** Plain gradient descent is essentially never used in production as originally formulated (full-batch, fixed learning rate); the consensus workhorse for anything beyond small convex problems is mini-batch SGD with an adaptive per-parameter method layered on top, almost always Adam or AdamW (Adam plus decoupled weight decay, Loshchilov & Hutter, 2017-2019) for anything resembling a neural network, while for genuinely convex problems like plain logistic regression, second-order or quasi-Newton methods (L-BFGS is scikit-learn's default solver for `LogisticRegression`) often converge in far fewer iterations than any first-order method because they use curvature information the gradient alone doesn't carry. The live disagreement is about generalization: there's a substantial body of empirical and theoretical work (Wilson et al., 2017, "The Marginal Value of Adaptive Gradient Methods") showing SGD with momentum can generalize *better* than Adam on some vision tasks despite converging slower, which is why "just use Adam" is a defensible default but not a universal law — plenty of well-tuned SGD+momentum recipes still beat Adam on final held-out performance, at the cost of far more learning-rate-schedule tuning effort.
 
**Where it's heading.** For convex problems (linear/logistic regression, GLMs) the direction of travel is toward more automatic curvature-aware solvers baked into libraries so almost nobody hand-tunes a learning rate for these anymore — L-BFGS and coordinate descent (used inside `glmnet`/scikit-learn's `liblinear`/`saga` solvers) already do this. For deep learning, second-order-ish approximations (Shampoo, K-FAC) and newer first-order variants (Lion, 2023; Sophia, 2023) continue to appear claiming faster wall-clock convergence than Adam at scale, but as of 2026 none has dislodged Adam/AdamW as the default in most training recipes — the honest, confidence-flagged claim is that Adam's dominance is more inertia-plus-genuinely-good-enough than a settled optimality result, and this is an area to expect continued churn rather than a stable endpoint.

---

## Mental model

```
LOSS SURFACE INTUITION (2 parameters, contour lines = equal loss)

  BATCH GD                    SGD                          MOMENTUM
  (one big accurate step)     (many noisy small steps)     (accumulates velocity,
                                                              damps oscillation)

    ___________               ___________                   ___________
   /     *     \             / *-.  .-*  \                 /      *     \
  |      |      |           |  `-**-`     |               |       \      |
  |      v      |           | *  * *  *   |               |        \     |
  |    (few,    |           |(many, noisy,|               |     (fewer   |
  |   smooth    |           | cheap steps)|               |   oscillations,
  |    steps)   |           |             |               |   faster net |
   \___________/             \___________/                 \  progress) /
                                                              \_________/

GRADIENT, ALWAYS THE SAME SHAPE for linear AND logistic regression:
  grad_w = X^T (y_hat - y) / n        <- MSE grad for linear (y_hat = Xw)
  grad_w = X^T (sigmoid(Xw) - y) / n  <- cross-entropy grad for logistic
  SAME formula, y_hat is just computed differently. This is not a coincidence --
  it falls out of both being generalized linear models with a "canonical link".
```

The one-line mental model: **every optimizer covered here answers "which direction, and how far" using only first-derivative information from data seen so far — GD/SGD/mini-batch differ in how much data informs one step, and momentum/RMSprop/Adam differ in how much *history* of past gradients gets folded into the current step.**

---

## How it actually works

### Linear regression: the normal equation and why it's avoided at scale

Minimizing `J(w) = (1/2n) ||Xw - y||^2` by setting its gradient to zero gives `X^T(Xw-y) = 0` → `w = (X^T X)^-1 X^T y`. This is exact and requires no learning rate, but costs `O(nd^2 + d^3)` (forming `X^T X` then inverting it), which is prohibitive past a few thousand features, and is numerically unstable when `X^T X` is ill-conditioned — near-collinear features make its condition number huge, so small floating-point errors in `X` produce large errors in `w` (this is exactly why ridge regression's `(X^T X + λI)^-1` is not just a regularizer but also a numerical stabilizer: adding `λI` improves the condition number directly).

### Logistic regression: deriving the gradient from scratch

Model: `p = sigmoid(z)`, `z = Xw + b`, `sigmoid(z) = 1/(1+e^-z)`. Loss (binary cross-entropy, single example): `L = -[y log(p) + (1-y) log(1-p)]`. Three chain-rule pieces:

1. `dL/dp = -y/p + (1-y)/(1-p)`
2. `dp/dz = p(1-p)` (the sigmoid derivative identity — same one used in the backprop module)
3. `dz/dw = x`

Multiplying steps 1 and 2 (`dL/dz = dL/dp · dp/dz`) and simplifying algebraically:
```
dL/dz = [-y/p + (1-y)/(1-p)] * p(1-p)
      = -y(1-p) + (1-y)p
      = -y + yp + p - yp
      = p - y
```
Every `p` term cancels except one — this is the "canonical link" simplification that makes logistic regression's gradient exactly `p - y` (the residual, same functional form as linear regression's `y_hat - y`), not some more complicated expression involving the sigmoid derivative explicitly. The full gradient over `n` examples is `grad_w = (1/n) X^T (sigmoid(Xw) - y)`, and this cancellation is precisely why logistic regression's cross-entropy loss is used instead of squared error on top of sigmoid — squared error's gradient would carry an *extra* `p(1-p)` factor that vanishes near `p=0` or `p=1`, causing severe gradient vanishing exactly where you'd want the strongest learning signal (a confidently wrong prediction).

### Batch, stochastic, and mini-batch: the accuracy/cost tradeoff

- **Batch GD**: one step per full pass over `n` examples. Gradient estimate has zero variance (it's exact), but one step costs `O(nd)`, so for large `n` you get very few updates per unit compute.
- **SGD**: one step per single example. Gradient estimate has high variance (a single example is a noisy estimate of the true gradient), but you get `n` updates per pass instead of 1 — in practice this noise acts as a mild regularizer and lets you escape shallow local structure, at the cost of a noisy, oscillating loss curve that never fully converges to the exact minimum without a decaying learning rate.
- **Mini-batch** (typically 32-256 in deep learning, larger for simple convex models): averages the gradient over a small batch, trading off variance against per-step cost; it's the near-universal practical choice because it vectorizes well on hardware (GPU/SIMD) in a way single-example SGD does not.

### Momentum: fixing oscillation across narrow valleys

Plain SGD update: `w := w - eta * grad`. Momentum adds a velocity term that accumulates an exponentially-weighted moving average of past gradients:
```
v := beta * v + (1 - beta) * grad     (typically beta = 0.9)
w := w - eta * v
```
Why this helps: in a valley that's steep in one direction and shallow in another (a common shape near a minimum with correlated features), plain SGD's gradient has a large oscillating component perpendicular to the valley and a small consistent component along it. Averaging over time (momentum) cancels the oscillating component (it flips sign step to step, so it averages toward zero) while reinforcing the consistent component (it points the same direction every step, so it accumulates) — this is why momentum converges faster along narrow valleys without needing a smaller learning rate to tame the oscillation.

### RMSprop and Adam: per-parameter learning rates

Plain SGD and momentum use one global learning rate for every parameter, but different parameters can have gradients on wildly different scales (a feature measured in dollars vs. one measured in a 0-1 proportion). RMSprop tracks a per-parameter exponentially-weighted average of squared gradients and divides by its square root:
```
s := beta2 * s + (1 - beta2) * grad^2      (typically beta2 = 0.999)
w := w - eta * grad / (sqrt(s) + eps)       (eps ~1e-8, prevents div-by-zero)
```
Parameters with consistently large gradients get their effective step size shrunk; parameters with small, sparse gradients get theirs enlarged — this is what makes RMSprop/Adam-family methods far more forgiving of unnormalized or heterogeneously-scaled features than plain SGD.

**Adam** (Kingma & Ba, 2014) is literally momentum (`m`, the first moment) plus RMSprop (`v`, the second moment) plus bias correction:
```
m := beta1 * m + (1 - beta1) * grad          (beta1 = 0.9 default)
v := beta2 * v + (1 - beta2) * grad^2        (beta2 = 0.999 default)
m_hat := m / (1 - beta1^t)                    # bias correction
v_hat := v / (1 - beta2^t)                    # bias correction
w := w - eta * m_hat / (sqrt(v_hat) + eps)    (eta default 0.001, eps default 1e-8)
```
The bias correction exists because `m` and `v` are initialized to zero, so early in training (`t` small) they're both biased toward zero — dividing by `(1 - beta^t)` (which is close to `beta^t` when `t` is small, and approaches 1 as `t` grows) corrects for this systematically rather than letting the first several steps take artificially tiny effective steps. These default values (`lr=0.001, betas=(0.9, 0.999), eps=1e-8`) are PyTorch's `torch.optim.Adam` defaults and have been stable across recent versions ([PyTorch docs](https://docs.pytorch.org/docs/main/generated/torch.optim.adam.Adam_class.html) — accessed 2026-08-03).

---

## Build it from scratch

```python
import numpy as np

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def logistic_regression_adam(X, y, epochs=200, lr=0.05, batch_size=32,
                              beta1=0.9, beta2=0.999, eps=1e-8):
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0
    m_w, v_w, m_b, v_b = 0.0, 0.0, 0.0, 0.0
    t = 0
    for epoch in range(epochs):
        perm = np.random.permutation(n)
        for start in range(0, n, batch_size):
            idx = perm[start:start+batch_size]
            xb, yb = X[idx], y[idx]
            p = sigmoid(xb @ w + b)
            grad_w = xb.T @ (p - yb) / len(idx)      # the derived gradient: X^T(p-y)
            grad_b = np.mean(p - yb)

            t += 1
            m_w = beta1 * m_w + (1 - beta1) * grad_w
            v_w = beta2 * v_w + (1 - beta2) * grad_w**2
            m_w_hat = m_w / (1 - beta1**t)
            v_w_hat = v_w / (1 - beta2**t)
            w -= lr * m_w_hat / (np.sqrt(v_w_hat) + eps)

            m_b = beta1 * m_b + (1 - beta1) * grad_b
            v_b = beta2 * v_b + (1 - beta2) * grad_b**2
            m_b_hat = m_b / (1 - beta1**t)
            v_b_hat = v_b / (1 - beta2**t)
            b -= lr * m_b_hat / (np.sqrt(v_b_hat) + eps)
    return w, b
```
Verification approach (the lab exercise): generate a synthetic linearly-separable dataset, fit with this implementation, fit `sklearn.linear_model.LogisticRegression(solver='lbfgs')` on the same data, and confirm the decision boundary (`w` direction, not exact magnitude — L-BFGS and Adam converge to the same optimum for this convex problem but via different paths and without identical regularization defaults) agrees to within a few percent on held-out accuracy.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Loss oscillates wildly and never decreases, sometimes diverges to `nan` | Learning rate too high for the loss surface's curvature | Halve the learning rate and retry; for Adam, also check `eps` isn't too small relative to gradient scale (division blow-up) |
| Loss decreases far slower than expected, or plateaus early with SGD but not Adam on the same data | Unnormalized/heterogeneously-scaled features force a single global learning rate to be too small for some parameters and too large for others | Standardize features (zero mean, unit variance) before SGD; or switch to Adam, which per-parameter-scales the effective learning rate |
| `sklearn.linear_model.LogisticRegression` throws a `ConvergenceWarning` | Default `max_iter=100` for L-BFGS is too low for the dataset's conditioning, or features aren't scaled | Increase `max_iter`, standardize features, or switch `solver` (e.g., `saga` for very large sparse data) |
| Model trains fine on a held-out split but coefficients are wildly different across random seeds/subsamples | High multicollinearity — `X^T X` (or the logistic analogue) is near-singular, so many different `w` fit the data almost equally well | Regularize (L2/ridge, covered in the next module), or drop/combine collinear features |
| Adam converges fast on training loss but generalizes worse than SGD+momentum on the same architecture | Documented empirical pattern (Wilson et al. 2017) — adaptive per-parameter scaling can converge to sharper minima that generalize less well on some tasks | Try SGD+momentum with a tuned learning-rate schedule as a second full run before concluding Adam's speed advantage is worth taking at face value for that specific task |

---

## Tradeoffs & when NOT to use it

- **Don't reach for the normal equation past a few thousand features or with any meaningful collinearity.** The closed form is elegant but `O(d^3)` inversion and numerical instability under ill-conditioning make it a liability outside small, well-conditioned problems — gradient-based or regularized (ridge) approaches dominate in practice.
- **Don't default to Adam reflexively for a plain convex logistic regression.** A quasi-Newton method like L-BFGS (scikit-learn's default) typically converges in a few dozen iterations using curvature information that first-order Adam has to approximate crudely over hundreds of steps — for genuinely convex problems, second-order methods usually win outright.
- **Don't use plain SGD (no momentum, no per-parameter scaling) on unnormalized features and expect fast convergence.** It will technically converge (for convex problems, with a suitable decaying learning rate) but can take an order of magnitude longer than a scaled/adaptive method on badly-conditioned data — always standardize features first regardless of which optimizer you pick.
- **Don't assume Adam's faster training-loss convergence means better generalization.** On several documented vision benchmarks, well-tuned SGD+momentum has beaten Adam on held-out accuracy despite converging slower — treat "use Adam" as a strong, cheap default, not a proof of superiority, and validate on held-out data before locking in the choice for a final production model.

---

## Interview questions

### Q1 — Derive the gradient of binary cross-entropy loss with respect to the logit `z`, starting from the loss function.
**Testing:** whether the sigmoid+cross-entropy cancellation is genuinely understood, not memorized as "the answer is p-y."
**Answer:** `L = -[y log(p) + (1-y) log(1-p)]`, `p = sigmoid(z)`. `dL/dp = -y/p + (1-y)/(1-p)`, `dp/dz = p(1-p)`. Multiplying and expanding: `dL/dz = [-y/p+(1-y)/(1-p)]*p(1-p) = -y(1-p)+(1-y)p = p - y`. Every `p`-dependent term cancels.
**Follow-up trap:** *"Would this same clean cancellation happen if you used squared error instead of cross-entropy on top of sigmoid?"* — no; squared error's gradient through sigmoid carries an extra, uncancelled `p(1-p)` factor, which is near zero when `p` is near 0 or 1 — exactly where a confidently wrong prediction most needs a strong gradient. This is the actual reason cross-entropy is paired with sigmoid, not an arbitrary convention.

### Q2 — Why is the normal equation rarely used in production even though it gives the exact answer?
**Testing:** whether cost and numerical stability are both named, not just one.
**Answer:** Cost: forming `X^T X` and inverting it is `O(nd^2 + d^3)`, prohibitive for large `d`. Stability: if features are collinear, `X^T X` is near-singular, so its inverse amplifies floating-point error in `X` into large error in `w`.
**Follow-up trap:** *"How does ridge regression address the numerical-stability half of that, mechanically?"* — adding `λI` before inverting (`(X^T X + λI)^-1`) increases every eigenvalue of `X^T X` by `λ`, directly improving its condition number (ratio of largest to smallest eigenvalue), independent of whatever regularization/bias-variance benefit it provides.

### Q3 — What specifically breaks if you don't standardize features before running plain SGD (no momentum, no Adam) on linear regression?
**Testing:** connecting a single global learning rate to per-feature gradient scale.
**Answer:** A single `eta` must work for every coordinate of `w` simultaneously. If one feature has values in the thousands and another is 0-1, the gradient with respect to the large-scale feature's weight is proportionally huge, forcing `eta` low enough not to diverge on that coordinate — which makes progress on the small-scale feature's weight extremely slow. The loss surface becomes a long, narrow, poorly-conditioned ellipse rather than a well-behaved bowl.
**Follow-up trap:** *"Does Adam make standardization unnecessary?"* — no, it makes it *less critical*, not unnecessary. Adam's per-parameter second-moment scaling compensates for gradient-scale differences to a significant degree, but standardizing inputs is still cheap, still improves conditioning, and still speeds convergence — "Adam handles it" is not a reason to skip a near-free preprocessing step.

### Q4 — Walk through what momentum's velocity term does to a gradient that oscillates in sign every step versus one that's consistently positive.
**Testing:** the mechanical cancellation/reinforcement argument, not "it smooths things."
**Answer:** `v := beta*v + (1-beta)*grad`. For an oscillating gradient (`+g, -g, +g, -g, ...`), successive terms in the exponential moving average partially cancel, so `v`'s magnitude stays small relative to `g`. For a consistently-signed gradient, every term reinforces the same direction, so `v` grows toward roughly `g / (1-beta)` in the steady state — momentum amplifies consistent signal and damps oscillating noise, which is exactly the shape of the problem in a narrow valley (oscillation perpendicular to the valley, consistent signal along it).
**Follow-up trap:** *"What's the failure mode if beta is set too close to 1, e.g. 0.999, for momentum on a fast-changing loss landscape?"* — the velocity term averages over too long a window of past gradients, so the optimizer keeps moving in a previously-correct direction for many steps after the true gradient has changed direction — this manifests as overshoot and slow correction near a minimum, not divergence, but noticeably slower fine-grained convergence than a more reactive `beta` (0.9-0.95 is the typical practical range).

### Q5 — What does Adam's bias correction term actually correct for, and why only matters early in training?
**Testing:** whether "bias correction" is understood mechanically, not just recognized as a name in the formula.
**Answer:** `m` and `v` are initialized to 0, so their raw exponential moving averages are systematically biased toward 0 for the first several steps (`m` after one step is `(1-beta1)*grad`, far smaller than `grad` itself). Dividing by `(1-beta1^t)` (and the analogous `v` correction) rescales them back up; as `t` grows, `beta^t -> 0`, so `(1-beta^t) -> 1` and the correction fades to a no-op.
**Follow-up trap:** *"What would you actually observe in a loss curve if bias correction were removed from an Adam implementation?"* — abnormally tiny effective steps for the first several dozen iterations (because `m_hat`/`v_hat` would be their small, biased raw values), producing a training curve that looks like it's "warming up" more slowly than it should relative to the same run with correction — this is a real, reported bug pattern in from-scratch Adam implementations, not a theoretical curiosity.

### Q6 — Why does scikit-learn default `LogisticRegression` to L-BFGS rather than SGD, and when would you override that?
**Testing:** understanding that convexity changes which optimizer class is appropriate.
**Answer:** Logistic regression's negative log-likelihood is convex, and L-BFGS (a quasi-Newton method) approximates the Hessian (curvature) using recent gradient history, letting it take far more informed steps than a first-order method — it typically converges in tens of iterations rather than the hundreds-to-thousands SGD/Adam might need for the same convex problem. Override it for datasets too large to fit in memory for a batch solver, or with very high-dimensional sparse features, where `saga` (a variance-reduced SGD variant) scales better.
**Follow-up trap:** *"Would you ever prefer Adam over L-BFGS for logistic regression specifically?"* — rarely for the convex problem in isolation, but yes if logistic regression is one output head trained jointly inside a larger non-convex neural network, where the whole system is optimized with a single optimizer end-to-end — the "always convex, always L-BFGS" reasoning only applies when logistic regression is standalone.

### Q7 — Given a linear regression with two highly collinear features, what happens to the individual coefficient estimates, and how would you detect this in practice?
**Testing:** connecting multicollinearity to unstable, non-identifiable coefficients — a common real-data trap.
**Answer:** When two features are nearly linearly dependent, many different `(w_1, w_2)` combinations produce nearly the same predictions (their sum or a similar combination is what's actually identified, not each individually), so the coefficients become highly sensitive to noise — small data perturbations swing them by large amounts, sometimes flipping sign, even though the model's overall predictions barely change. Detect via variance inflation factor (VIF), or simply by refitting on bootstrap resamples and checking coefficient stability.
**Follow-up trap:** *"Does this mean the model's predictions are also unreliable?"* — not necessarily; predictions can remain stable and accurate even when individual coefficients are unstable, because it's specifically the *decomposition* of effect between the collinear features that's poorly identified, not the combined fit. This distinction (unstable coefficients vs. unstable predictions) is exactly what separates a candidate who understands multicollinearity from one who just says "it's bad."

### Q8 — You're training a model with Adam and the loss goes to `nan` after a few dozen steps. Diagnose, in order of what you'd check first.
**Testing:** staff-level triage, not a single guessed cause.
**Answer:** First check the learning rate is not simply too high for the loss surface (halve it and retry as a fast diagnostic). Second, check for a data issue producing `inf`/`nan` upstream (an unclipped log of zero, a division by a feature that's exactly zero for some rows, unnormalized target with extreme outliers). Third, check `eps` in the Adam denominator isn't effectively zero relative to gradient scale, which can blow up the update on a near-zero second-moment estimate. Fourth, consider gradient clipping as a stopgap while root-causing.
**Follow-up trap:** *"Would this same failure look different with plain SGD instead of Adam?"* — plain SGD diverging from too-high a learning rate typically shows escalating oscillation before `nan`, visible over several steps; Adam's adaptive per-parameter scaling can mask this early (each parameter's effective step is normalized by its own gradient history) and then fail more abruptly once the second-moment estimate itself becomes unstable — meaning Adam can hide a too-high learning rate for longer before the failure becomes visible.

### Q9 — What's the practical difference in the noise profile of the loss curve between batch size 1 (pure SGD) and batch size 256, all else equal, and why does it matter for early stopping?
**Testing:** connecting batch size to gradient variance and its downstream effect on monitoring/decisions.
**Answer:** Batch size 1's per-step gradient is a high-variance single-sample estimate of the true gradient, so the loss curve is visibly noisy step-to-step even while trending down on average; batch size 256 averages over more samples, reducing variance roughly by a factor related to `1/sqrt(batch_size)`, producing a visibly smoother curve. This matters for early stopping because a noisy per-step curve can look like it's plateaued or even regressing over a short window purely from variance, triggering a premature stop — early stopping criteria should be evaluated on a smoothed (e.g., epoch-level, not step-level) loss, especially at small batch sizes.
**Follow-up trap:** *"Does a smoother loss curve from a larger batch always mean better final generalization?"* — no, and this is a documented open question — some evidence suggests smaller batches' gradient noise acts as an implicit regularizer that improves generalization on some tasks, so "smoother curve" (a training-dynamics property) shouldn't be conflated with "better final held-out performance" (a generalization property); they can trade off against each other.

### Q10 — Explain why RMSprop's per-parameter scaling helps with sparse features specifically, using the update rule.
**Testing:** a concrete mechanism, not just "it adapts."
**Answer:** For a sparse feature (mostly zero, occasionally nonzero), its weight's gradient is zero most steps and only occasionally nonzero. Its running average of squared gradients `s` therefore stays small most of the time, so when a nonzero gradient does occur, dividing by `sqrt(s)+eps` produces a comparatively large effective step — the parameter "catches up" fast on its rare updates rather than being swamped by a global learning rate tuned for the average, dense-feature case.
**Follow-up trap:** *"Is this the same mechanism that gave rise to Adagrad, RMSprop's predecessor, and why did RMSprop replace it as the default?"* — Adagrad accumulates the *sum* (not exponential moving average) of squared gradients over all of training, so `s` only ever grows, monotonically shrinking the effective learning rate toward zero over a long training run regardless of recent gradient behavior — RMSprop's exponential moving average instead "forgets" old squared gradients at a controlled rate, so the effective learning rate can recover if recent gradients shrink, fixing Adagrad's premature-stalling failure mode on long training runs.

### Q11 — Design question: you inherit a logistic regression pipeline where training accuracy is high but a specific slice of production traffic (a particular customer segment) has systematically worse accuracy than the rest. Is this an optimizer problem? How do you find out?
**Testing:** staff-level ability to separate optimization issues from data/model-capacity issues.
**Answer:** Almost certainly not an optimizer problem — logistic regression's loss is convex, so a converged fit (check the training loss actually plateaued, gradient norm near zero) found *the* global optimum for that feature representation, meaning the segment-specific gap is a data or capacity issue: the segment may be underrepresented in training data, may need features that aren't currently in the model, or the linear decision boundary may genuinely not separate that segment well (logistic regression's core capacity limitation). Check training loss convergence first to rule out an optimization bug, then investigate segment-specific feature coverage and class balance before reaching for a more expressive model.
**Follow-up trap:** *"What would make you suspect it actually IS an optimization issue after all?"* — if the training loss itself hasn't converged (still decreasing when training stopped, or a `ConvergenceWarning` was silently ignored), or if different random seeds/solvers (L-BFGS vs. SGD) produce meaningfully different coefficients and segment-level accuracy — convex problems shouldn't be solver-sensitive at convergence, so solver-sensitivity is itself diagnostic evidence of an optimization problem, not a data problem.

---

## Red flags that fail you

- Cannot derive `p - y` as logistic regression's gradient from cross-entropy and sigmoid, or thinks it needs an explicit uncancelled `p(1-p)` term.
- Says "Adam is just better than SGD" without qualification or awareness of the generalization-gap literature.
- Cannot explain what problem momentum specifically fixes (oscillation) versus what RMSprop specifically fixes (per-parameter scale).
- Doesn't know why the normal equation is avoided at scale (names only cost, or only instability, not both).
- Treats batch size purely as a speed/memory knob with no acknowledgment of its effect on gradient noise and generalization.
- Can't diagnose a diverging loss curve past "lower the learning rate."

---

## Cheat card

```
NORMAL EQUATION: w = (X^T X)^-1 X^T y   -- O(nd^2+d^3), unstable if X^T X ill-conditioned
LOGISTIC GRADIENT: grad_w = X^T(sigmoid(Xw) - y)/n   <- p-y falls out of BCE+sigmoid cancellation
  squared-error-on-sigmoid gradient carries EXTRA p(1-p) factor -> vanishes near p=0/1 (why BCE is used)

GD vs SGD vs mini-batch: full pass/step vs 1 example/step vs batch (32-256 typical)
  more data per step = lower variance, higher cost per step

MOMENTUM:  v = beta*v + (1-beta)*grad         (beta~0.9)      w -= eta*v
  cancels oscillation (alternating sign), reinforces consistent direction
RMSPROP:   s = beta2*s + (1-beta2)*grad^2     (beta2~0.999)   w -= eta*grad/(sqrt(s)+eps)
  per-parameter scaling: big historical grad -> smaller step; sparse/small grad -> bigger step
ADAM = momentum(m) + RMSprop(v) + bias correction:
  m_hat = m/(1-beta1^t)   v_hat = v/(1-beta2^t)   w -= eta*m_hat/(sqrt(v_hat)+eps)
  defaults (PyTorch): lr=0.001, betas=(0.9,0.999), eps=1e-8

sklearn LogisticRegression: default solver='lbfgs' (since 0.22), max_iter=100
  convex problem -> quasi-Newton (curvature-aware) converges in ~10s of iters, beats Adam here

Adagrad flaw: accumulates sum (not EMA) of grad^2 -> monotonically shrinks lr -> stalls long runs
Adam not always better: SGD+momentum can generalize better despite slower convergence (Wilson 2017)
```

## Sources

- [Adam: A Method for Stochastic Optimization — Kingma & Ba, arXiv (2014)](https://arxiv.org/abs/1412.6980) — accessed 2026-08-03
- [Decoupled Weight Decay Regularization (AdamW) — Loshchilov & Hutter, arXiv (2017/2019)](https://arxiv.org/abs/1711.05101) — accessed 2026-08-03
- [The Marginal Value of Adaptive Gradient Methods in Machine Learning — Wilson et al., arXiv (2017)](https://arxiv.org/abs/1705.08292) — accessed 2026-08-03
- [Adam — PyTorch documentation](https://docs.pytorch.org/docs/main/generated/torch.optim.adam.Adam_class.html) — accessed 2026-08-03
- [LogisticRegression — scikit-learn documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
