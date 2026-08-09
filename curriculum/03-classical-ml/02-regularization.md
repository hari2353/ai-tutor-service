# Regularization: L1/L2 Derived Geometrically, Bias-Variance, and Learning Curves

> **Track:** T03 Classical ML · **Time:** 1.5h · **Prereqs:** T03-linear-models · **Updated:** 2026-08-03
> **Module id:** `T03-regularization` · **Tags:** fundamentals
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Regularization adds a penalty on model complexity to the loss so the optimizer trades a little training-set fit for a model that generalizes better; L2 (ridge) adds `lambda * ||w||_2^2` and shrinks all coefficients smoothly toward zero without forcing any to exactly zero, while L1 (lasso) adds `lambda * ||w||_1` and, because the L1 ball has corners on the coordinate axes, the loss contour typically first touches the constraint region exactly at a corner — producing sparse solutions where some coefficients are *exactly* zero, which is why lasso is used for feature selection and ridge is not. Both are special cases of the bias-variance tradeoff: an unregularized model with enough capacity fits training noise (low bias, high variance — the gap between train and validation error is large and validation error is worse than a simpler model's), while a heavily regularized model underfits (high bias, low variance — both train and validation error are high and close together). A learning curve (error vs. training-set size, model complexity held fixed) is the single fastest diagnostic for which regime you're in: if train and validation error have converged to a similar, unsatisfactory value with more data added, you have a bias problem regularization won't fix — you need a more expressive model or better features; if train error is low and validation error is high and the gap is stable or widening as training-set size grows, you have a variance problem, and stronger regularization (or more data) is exactly the right lever.

## Why this gets asked

Because "your model does great on training data and mediocre in production" is the single most common real-world ML failure, and an interviewer wants to know whether you diagnose it by staring at hyperparameters and guessing, or by plotting a learning curve and reading off the regime. It's also asked because most candidates can define L1 and L2 as formulas but can't explain the *geometric* reason L1 produces sparsity — that's the part that separates "read a blog post" from "actually understands constrained optimization."

---

## Lineage: past → present → future

**What came before.** Before explicit regularization, the only lever against overfitting in linear models was controlling model complexity directly — feature selection by hand, stepwise regression (add/remove features by a significance test), or simply keeping the model small enough that `n >> d` held comfortably. This worked when data was scarce and features were few, but stepwise selection has known statistical pathologies (it doesn't account for the multiple-comparisons problem across the many features tested, inflating false-positive feature inclusion) and doesn't scale to the hundreds or thousands of features common in modern tabular problems. Ridge regression (Hoerl & Kennard, 1970) was introduced specifically to fix the numerical instability of the normal equation under multicollinearity — the regularization-as-generalization-tool framing came slightly later and is now the dominant lens, but ridge's original motivation was linear algebra (a singular or near-singular `X^T X`), not statistics.

**Where it stands now.** L1 (lasso, Tibshirani 1996) and L2 (ridge) are both standard, well-understood, and frequently combined (elastic net, Zou & Hastie 2005, `alpha * L1 + (1-alpha) * L2`) to get sparsity with more stable coefficient selection under correlated features than pure lasso provides (lasso arbitrarily picks one of several correlated features and zeroes the rest, which is unstable across resamples; elastic net tends to keep or drop correlated groups together). For tree ensembles, regularization looks different — depth limits, minimum samples per leaf, subsampling (both row and column), and explicit L1/L2 penalties on leaf weights (XGBoost) — but the underlying bias-variance logic is identical. The live disagreement is less about the mechanics (settled) and more about *when to regularize versus when to just get more data or better features*: regularization can only trade variance for bias, it cannot fix a genuine bias problem, and a persistent industry failure mode is over-indexing on regularization tuning when the actual fix needed is better features or more representative training data.

**Where it's heading.** For classical linear/tree models this area is mature and stable — expect no structural change, only continued refinement of automated hyperparameter search (which value of `lambda`/`alpha` to pick) via cross-validation, which is itself well-settled. In deep learning, the regularization toolkit has partly shifted away from explicit weight penalties toward architectural and procedural regularization (dropout, data augmentation, early stopping, weight decay as used in AdamW) whose interactions with each other and with model scale remain an active area of empirical study — the honest statement is that "double descent" (test error can *decrease* again past the interpolation threshold as model capacity keeps growing, Belkin et al. 2019) complicates the classical bias-variance U-shape at very high capacity, and this interacts with regularization choices in ways still being characterized as of 2026.

---

## Mental model

```
GEOMETRIC PICTURE: why L1 gives sparsity and L2 doesn't (2D case, axes = w1, w2)

  L2 constraint region: a CIRCLE                L1 constraint region: a DIAMOND
  (no corners on axes)                          (corners exactly ON the axes)

        w2                                            w2
         |                                             |
      .--+--.        loss contours                  ,--+--.
     /   |   \       (ellipses) expanding             \.  |
    |    |    |      outward from the                   \.|      touches a
    |    o----|--    unconstrained optimum          ------o------  CORNER first
    |    |    |      until first touching                  /|
     \   |   /       the constraint region                / |
      '--+--'        -- generically touches                '-+-'
         |            the circle at a point                  |
                       with BOTH coords nonzero          one coordinate is
                                                          EXACTLY ZERO at the touch point

BIAS-VARIANCE, as a function of model complexity:
  error
    |      \                                    ,----  <- high-complexity: low bias,
    |       \  bias^2 (shrinks with complexity)/         high variance (overfits)
    |        \                                /
    |         \____total error (U-shaped)____/
    |         /                              \
    |        /  variance (grows w/ complexity) 
    |_______/________________________________\____ complexity
         underfit    "just right"      overfit
```

The one-line mental model: **L1's constraint region has corners exactly on the coordinate axes, so the expanding loss contour generically hits a corner first (sparsity); L2's constraint region is smooth everywhere, so it hits a point with all coordinates nonzero (shrinkage, not sparsity).**

---

## How it actually works

### Deriving the ridge (L2) closed form and why it's numerically stabilizing

Ridge minimizes `J(w) = ||Xw - y||^2 + lambda ||w||^2`. Setting the gradient to zero: `2X^T(Xw-y) + 2*lambda*w = 0` → `w = (X^T X + lambda*I)^-1 X^T y`. Compare to OLS's `(X^T X)^-1 X^T y` — adding `lambda*I` before inverting adds `lambda` to every eigenvalue of `X^T X`, which directly improves the condition number (ratio of largest to smallest eigenvalue) whenever `X^T X` has a near-zero eigenvalue (the multicollinearity case) — this is why ridge is simultaneously a regularizer (biases the estimate, trading variance for bias) and a numerical fix (makes the matrix invertible and well-conditioned even when `X^T X` alone is singular).

### The constrained-optimization view and why L1 produces exact zeros

Lagrangian duality connects `min J(w) + lambda*penalty(w)` to the equivalent constrained problem `min J(w) subject to penalty(w) <= t` for some `t` corresponding to that `lambda`. Picture the unconstrained loss's elliptical contours (from `J(w)` alone) expanding outward from the unconstrained optimum until they first touch the constraint region's boundary — that touching point is the constrained solution. For L2, the constraint region `{w : ||w||_2^2 <= t}` is a ball/circle, smooth everywhere, so the expanding ellipse generically touches it at a point with every coordinate nonzero (a smooth boundary has no preferred coordinate). For L1, the constraint region `{w : ||w||_1 <= t}` is a diamond (in 2D) or cross-polytope (higher dimensions) whose corners lie exactly on the coordinate axes — an expanding ellipse very commonly touches the region first at one of these corners, precisely because a corner is a lower-dimensional feature (a single point) that a randomly-oriented ellipse is disproportionately likely to hit compared to the full-dimensional smooth faces. At a corner, one or more coordinates are exactly zero by construction — this is the entire mechanism, and it is purely geometric, not statistical: no amount of L2 regularization strength produces exact zeros for a generic loss, because a circle simply has no corners to hit.

### Bias-variance decomposition, stated precisely

For squared-error loss, the expected test error at a point decomposes exactly as `E[(y - f_hat(x))^2] = Bias(f_hat(x))^2 + Var(f_hat(x)) + sigma^2` (irreducible noise). `Bias` is the systematic error from the model class being unable to represent the true function even with infinite data (e.g., fitting a line to a quadratic relationship). `Variance` is how much the fitted function would change across different training sets drawn from the same distribution (a high-capacity model fit to a small dataset varies wildly depending on which particular noise happened to be in that sample). Regularization moves along this tradeoff: it deliberately introduces bias (shrinking coefficients away from their unconstrained-optimal values, which are unbiased for OLS) in exchange for reduced variance, and the `lambda` that minimizes *total* test error is generally nonzero whenever variance reduction outweighs the bias introduced — which is essentially always true for `d` comparable to or larger than `n`, or under meaningful multicollinearity.

### Reading a learning curve correctly

A learning curve plots training and validation error against training-set size, holding model complexity fixed. Three archetypal shapes:
- **High bias:** both curves converge to a similarly poor error as training size grows, with a small gap between them. More data will not help — this model class cannot represent the underlying function well enough, or the features don't carry the signal needed. The fix is more expressive features/model, not more data or more regularization.
- **High variance:** training error stays low, validation error stays notably higher, and the gap is large and doesn't close (or closes only very slowly) as training size grows. More data helps here, and so does regularization (or simplifying the model).
- **Well-fit:** both curves converge to a similar, low error with only a modest gap. Little further gain available from regularization changes alone in this regime — you're closer to the achievable error floor.

The critical, often-missed detail: you must vary training-set size *while holding the model and its hyperparameters fixed*, or the curve conflates two different effects (data quantity and model complexity) and becomes uninterpretable.

---

## Build it from scratch

```python
import numpy as np

def ridge_closed_form(X, y, lam):
    n, d = X.shape
    return np.linalg.solve(X.T @ X + lam * np.eye(d), X.T @ y)

def lasso_coordinate_descent(X, y, lam, n_iter=1000, tol=1e-6):
    """Coordinate descent for lasso -- soft-thresholding is the exact-zero mechanism,
    made explicit rather than left implicit in a generic gradient step."""
    n, d = X.shape
    w = np.zeros(d)
    for _ in range(n_iter):
        w_old = w.copy()
        for j in range(d):
            # partial residual excluding feature j's current contribution
            r_j = y - X @ w + X[:, j] * w[j]
            rho = X[:, j] @ r_j
            z = (X[:, j] ** 2).sum()
            # soft-thresholding operator -- THIS is where exact zeros come from
            if rho < -lam * n / 2:
                w[j] = (rho + lam * n / 2) / z
            elif rho > lam * n / 2:
                w[j] = (rho - lam * n / 2) / z
            else:
                w[j] = 0.0                      # <-- exact zero, not "small"
        if np.max(np.abs(w - w_old)) < tol:
            break
    return w
```
The `else: w[j] = 0.0` branch is the entire sparsity mechanism made concrete: whenever the correlation between feature `j` and the residual (`rho`) falls inside a band of width `lambda*n` around zero, coordinate descent sets that coefficient to *exactly* zero rather than shrinking it toward zero — this soft-thresholding operator is the algorithmic manifestation of the geometric corner-touching argument above. Verify by comparing against `sklearn.linear_model.Lasso(alpha=lam/(2*n))` (note scikit-learn's `alpha` parameterization differs by a factor from this derivation's `lambda` — always check a library's exact loss normalization before comparing coefficients numerically).

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Training accuracy near-perfect, validation accuracy noticeably worse, gap doesn't close with more data | High variance / overfitting | Increase regularization strength (`lambda`/`alpha`/`C` in sklearn is inverse-strength), simplify model, or get more diverse training data |
| Both training and validation accuracy are mediocre and close together, more data doesn't help | High bias / underfitting | Reduce regularization, add features, or switch to a more expressive model class — regularization tuning cannot fix this |
| Lasso selects a seemingly arbitrary one of several highly-correlated features and zeroes the rest, unstable across resamples | Lasso's sparsity mechanism picks one representative among correlated features somewhat arbitrarily near the corner-touching point | Switch to elastic net (`alpha` between pure L1 and L2), which tends to retain or drop correlated groups together rather than picking one arbitrarily |
| Regularization strength tuned via a single train/validation split gives inconsistent "best lambda" across reruns | Single-split validation error is itself a noisy estimate, especially with limited data | Use k-fold cross-validation to select `lambda` (e.g., `LassoCV`/`RidgeCV`), averaging the noisy per-fold estimate |
| Ridge coefficients shrink but never reach exactly zero even at very high `lambda`, confusing engineers expecting feature selection | This is expected behavior, not a bug — L2's constraint region has no corners | Use L1 or elastic net specifically when exact feature elimination (not just shrinkage) is the goal |

---

## Tradeoffs & when NOT to use it

- **Don't use lasso for feature selection when features are highly correlated and you need stable, reproducible selection across data refreshes.** Lasso's arbitrary pick-one-of-correlated-group behavior means the exact set of selected features can shift meaningfully between similar datasets or resamples — elastic net or domain-driven feature grouping is more robust when stability matters as much as sparsity.
- **Don't tune regularization strength as your first response to a validation-gap problem without first confirming (via a learning curve) that you're actually in a high-variance regime.** If the learning curve shows converged, high train/validation error, more regularization will make things worse, not better — you need better features or a more expressive model.
- **Don't regularize reflexively on small, low-dimensional, well-understood datasets where `n >> d` and features are already vetted.** Regularization trades some bias for variance reduction; when variance is already low (large `n`, small `d`, clean features), added regularization mostly just adds unhelpful bias — always validate `lambda=0` as a baseline before assuming regularization helps.
- **Don't compare `lambda` values across libraries or loss normalizations without checking the exact formula.** scikit-learn's `Lasso(alpha=...)` and `Ridge(alpha=...)` use different implicit scalings (division by `n` or not, factor-of-2 conventions) than a raw textbook derivation or a different library — a "sensible" `lambda` in one context can be silently wrong by an order of magnitude in another.

---

## Interview questions

### Q1 — Geometrically, why does L1 regularization produce exactly-zero coefficients while L2 only shrinks them?
**Testing:** the actual geometric mechanism, not a memorized fact.
**Answer:** The constrained-optimization view: expanding elliptical loss contours from the unconstrained optimum until they first touch the constraint region `{penalty(w) <= t}`. L1's region (a diamond/cross-polytope) has corners exactly on the coordinate axes; an expanding ellipse generically touches a lower-dimensional corner before a full-dimensional face, and at a corner one or more coordinates are exactly zero. L2's region (a ball) is smooth everywhere with no corners, so the generic touching point has every coordinate nonzero.
**Follow-up trap:** *"Does this argument still hold in very high dimensions, or is it a 2D artifact?"* — it holds in general; the cross-polytope (L1 ball) in `d` dimensions has `2d` vertices and many lower-dimensional faces on the axes, and the same "corners are lower-dimensional and disproportionately likely to be hit first" argument generalizes, which is exactly why lasso produces sparse solutions at any dimensionality, not just 2D toy examples.

### Q2 — Derive the closed-form solution for ridge regression and explain why it always exists even when the OLS solution doesn't.
**Testing:** connecting the derivation to the numerical-stability motivation.
**Answer:** `J(w) = ||Xw-y||^2 + lambda||w||^2`. `dJ/dw = 2X^T(Xw-y) + 2*lambda*w = 0` → `w = (X^T X + lambda*I)^-1 X^T y`. Adding `lambda*I` (`lambda > 0`) adds `lambda` to every eigenvalue of `X^T X`, so even if `X^T X` is singular (zero eigenvalue, e.g., perfect collinearity or more features than samples), `X^T X + lambda*I` has all-positive eigenvalues and is invertible.
**Follow-up trap:** *"What happens to the ridge solution as lambda approaches infinity?"* — `w` approaches the zero vector (the penalty completely dominates the loss term), which is the fully-biased, zero-variance extreme of the bias-variance tradeoff — a useless but well-defined limiting case, useful for sanity-checking an implementation.

### Q3 — State the bias-variance decomposition precisely and explain what "irreducible error" means in it.
**Testing:** whether the decomposition is known exactly, not paraphrased loosely.
**Answer:** `E[(y-f_hat(x))^2] = Bias(f_hat(x))^2 + Var(f_hat(x)) + sigma^2`. Irreducible error `sigma^2` is the variance of the true label given the features (label noise, or genuinely unpredictable variation) — no model, however good, can reduce this term; it's a property of the data-generating process, not the model.
**Follow-up trap:** *"If your model's test error is exactly equal to a reasonable estimate of sigma^2, what does that tell you, and what's the risk of over-interpreting it?"* — it suggests you're near the achievable error floor for this problem given current features, so further regularization tuning or model complexity changes are unlikely to help much; the risk is that your estimate of `sigma^2` is itself uncertain (often not directly measurable), so concluding "we've hit the floor" from a single noisy comparison is overconfident — corroborate with a learning curve showing convergence, not just one error number.

### Q4 — A learning curve shows training and validation error both plateauing at 15% error as training-set size grows from 10k to 200k examples, with only a small gap between them. What do you do next, and what would NOT help?
**Testing:** correctly diagnosing bias vs. variance from the curve shape and picking an appropriate response.
**Answer:** This is a high-bias signature (converged, small gap, more data isn't closing it) — the fix is more expressive features, more expressive model class, or fixing a fundamental data/labeling issue, not more data and not more regularization (which would only make bias worse).
**Follow-up trap:** *"What if you're only allowed to add more training data — no new features, no model change? Would that plateau ever break?"* — no, not meaningfully; if the curve has already converged with the current feature set, adding more of the same-distribution data cannot supply information the current features/model can't represent — this is precisely what "high bias" means, and it's why "get more data" is not a universal fix for poor model performance.

### Q5 — Why is elastic net used instead of pure lasso when features are correlated, mechanically?
**Testing:** understanding the specific instability elastic net addresses.
**Answer:** Pure lasso's corner-touching mechanism, applied to a group of highly correlated features, tends to arbitrarily select one member of the group (near-zero effective difference in loss between "credit feature A" and "credit feature B, C, D") and zero the rest, and which one gets selected can be unstable across resamples/noise. Elastic net's combined penalty (`alpha*L1 + (1-alpha)*L2`) retains L2's "grouping effect" (correlated features get similar, nonzero coefficients) while still permitting some coefficients to hit exactly zero, giving more stable feature selection under correlation.
**Follow-up trap:** *"Does elastic net still give exact zeros, or does the L2 component prevent that?"* — yes, it still produces exact zeros, because the L1 component's corner-based mechanism is still present in the combined penalty's geometry (the combined constraint region still has corners, just less sharply than pure L1) — elastic net is a tradeoff of sparsity sharpness for grouping stability, not a loss of sparsity altogether.

### Q6 — What's the actual difference between what regularization can fix and what it can't, in bias-variance terms?
**Testing:** the single most consequential distinction in this module.
**Answer:** Regularization can only trade variance for bias (or vice versa, moving along the tradeoff curve) — it cannot reduce total error below what's achievable by the best point on that curve for the given model class and features. If the irreducible bias (model class fundamentally can't represent the true function, or features don't carry the necessary signal) is the dominant error source, no amount of regularization tuning fixes it; you need a different model class or better features.
**Follow-up trap:** *"Concretely, how would you convince a skeptical teammate that more regularization won't help, before spending a week trying it?"* — show a learning curve with training error itself already high and converged with validation error at a similar level and small gap — if training error alone is high, the model isn't even fitting the training data well, which regularization (a tool for reducing overfitting, i.e., the gap) cannot address, since regularization only ever increases training error further while trying to close a gap that isn't the problem.

### Q7 — In scikit-learn, `LogisticRegression`'s regularization strength is `C`, not `lambda`. What's the relationship, and why does this matter practically?
**Testing:** attentiveness to a very common practical gotcha.
**Answer:** `C` is the *inverse* of regularization strength (`C = 1/lambda`, roughly, up to the library's exact loss normalization) — small `C` means strong regularization, large `C` means weak regularization, which is the opposite intuition from `lambda`. Practically, this matters because a hyperparameter search grid built assuming "bigger number = more regularization" (as with `lambda`) will be silently inverted if applied to `C` without noticing, producing a search that looks reasonable but is testing the wrong direction of the tradeoff.
**Follow-up trap:** *"How would you notice this mistake had happened, if you didn't catch it up front?"* — a hyperparameter sweep over `C` where the "least regularized" end of your intended search shows underfitting behavior (or vice versa) relative to what you expected is the tell — always sanity-check the direction of a regularization sweep against a known baseline (e.g., confirm the smallest `C` in your grid visibly underfits) before trusting the sweep's conclusions.

### Q8 — Why does ridge regression's `lambda*I` addition improve the condition number of `X^T X`, specifically (not just "it makes the matrix invertible")?
**Testing:** the eigenvalue-level mechanism, one level deeper than "it fixes invertibility."
**Answer:** Condition number is the ratio of the largest to smallest eigenvalue. Adding `lambda*I` shifts every eigenvalue of `X^T X` up by exactly `lambda` (since `I` shares eigenvectors with `X^T X` and adds `lambda` to each corresponding eigenvalue). This raises the smallest eigenvalue proportionally more (in relative terms) than the largest, shrinking the ratio — a near-zero smallest eigenvalue (huge condition number, the collinearity case) benefits the most from even a modest `lambda`.
**Follow-up trap:** *"Does this mean an arbitrarily large lambda always keeps improving conditioning, with no downside beyond bias?"* — conditioning keeps improving, yes, but the bias introduced grows unboundedly too (the solution collapses toward zero), so there's a real tradeoff even though conditioning alone monotonically improves — "better conditioning" isn't a free win once `lambda` is large enough to distort the fit substantially.

### Q9 — Design question: you're asked to add L1 regularization to a production XGBoost model that's currently unregularized and slightly overfitting on a 500-feature tabular dataset. Is L1 the right lever here, and what would you check first?
**Testing:** recognizing that regularization mechanics for tree ensembles differ from linear models even though the bias-variance logic is the same.
**Answer:** XGBoost's L1 term (`reg_alpha`) penalizes leaf weights, not feature coefficients directly (trees don't have per-feature linear coefficients) — it can still induce sparsity in leaf weights and indirectly discourage splits that don't earn their complexity cost, but it's a different mechanism than lasso's feature-level sparsity. Before tuning `reg_alpha` specifically, check the more commonly load-bearing tree-ensemble regularization knobs first: `max_depth`, `min_child_weight`, subsampling (`subsample`, `colsample_bytree`) — these usually have larger, more predictable effects on overfitting for tree ensembles than the L1/L2 leaf-weight penalties.
**Follow-up trap:** *"If a teammate says 'L1 regularization gives feature selection in XGBoost the same way it does in lasso,' what's wrong with that statement?"* — it conflates two different sparsity mechanisms: lasso's L1 zeros out entire feature *coefficients* (removing the feature from the linear model entirely), while XGBoost's `reg_alpha` penalizes leaf *weights* within trees that already chose their splits via a different criterion (gain) — a feature can still be used in many splits with `reg_alpha` active; it doesn't get "selected out" the way a zeroed lasso coefficient does. True feature-importance-based selection in tree ensembles requires a separate step (e.g., SHAP-based pruning, covered in the feature-selection module), not just turning up `reg_alpha`.

### Q10 — What does "double descent" complicate about the classical bias-variance U-shape, and how confident should you be stating it in an interview?
**Testing:** awareness of a genuinely unsettled, actively-researched nuance, stated with appropriate confidence calibration.
**Answer:** The classical picture says test error is U-shaped in model complexity (underfitting, then a sweet spot, then overfitting as complexity keeps growing). Belkin et al. (2019) and related work showed that past the "interpolation threshold" (where the model can perfectly fit training data), test error for some model classes can *decrease again* as capacity keeps growing further — a second descent the classical picture doesn't predict. State this as a real, empirically documented phenomenon primarily observed in high-capacity models (deep nets, and some kernel/tree settings), not as something that overturns the classical bias-variance framework for typical classical-ML-scale linear/tree models, where the U-shape remains the practically relevant picture.
**Follow-up trap:** *"Does double descent mean you should always prefer the largest possible model, then?"* — no; double descent describes a specific, not-fully-general phenomenon under specific conditions (interpolation regime, particular training procedures), and doesn't imply arbitrarily large models are always better in practice — compute cost, latency, and the fact that not every setting exhibits a clean second descent all argue against treating it as a blanket "bigger is always eventually better" rule.

### Q11 — What's the practical difference between choosing `lambda` via a single held-out validation split versus k-fold cross-validation, and when does it actually matter?
**Testing:** understanding that regularization-strength selection is itself subject to estimation noise.
**Answer:** A single split gives one noisy estimate of validation error per candidate `lambda`; the "best" `lambda` chosen this way can shift meaningfully on a rerun with a different split, especially with limited data. K-fold cross-validation averages the estimate over multiple splits, reducing this selection noise. It matters most when data is limited (small `n` relative to variance in the error estimate) or when candidate `lambda` values are close enough in expected performance that a noisy single estimate could plausibly rank them in the wrong order.
**Follow-up trap:** *"Does more folds always give a more reliable lambda choice?"* — not unconditionally; more folds (up to leave-one-out) reduces bias in the error estimate but increases its variance and computational cost, and for very large `n` the single-split estimate is often already low-variance enough that additional folds add cost without meaningfully changing the selected `lambda` — the right number of folds (commonly 5 or 10) is itself a bias-variance tradeoff on the *estimation procedure*, not a "more is always better" knob.

---

## Red flags that fail you

- Cannot explain geometrically why L1 gives sparsity and L2 doesn't — recites the formulas but not the corner/smooth-boundary argument.
- Confuses `C` (scikit-learn, inverse strength) with `lambda` (direct strength) and gets the tuning direction backwards without noticing.
- Recommends "add more regularization" for a validation gap without first checking a learning curve to confirm it's a variance problem, not a bias problem.
- Believes tree-ensemble L1/L2 penalties perform feature selection the same way lasso does.
- States the bias-variance decomposition informally ("it's a tradeoff") without being able to write `Bias^2 + Variance + irreducible error`.
- Treats "more data always helps" as universally true, ignoring the high-bias learning-curve case where it doesn't.

---

## Cheat card

```
RIDGE (L2): w = (X^T X + lambda*I)^-1 X^T y   -- shrinks all coefs, NEVER exactly zero
  lambda*I shifts every eigenvalue of X^T X up by lambda -> fixes condition number too
LASSO (L1): no closed form -- coordinate descent w/ soft-thresholding gives EXACT zeros
  geometric reason: L1 ball has corners ON axes; expanding loss ellipse hits corner first
  L2 ball is smooth everywhere -> generic touch point has all coords nonzero
ELASTIC NET: alpha*L1 + (1-alpha)*L2 -- sparsity + grouping effect for correlated features
  (pure lasso arbitrarily zeros all-but-one of a correlated group -> unstable across resamples)

BIAS-VARIANCE: E[(y-f_hat)^2] = Bias^2 + Variance + sigma^2 (irreducible)
  regularization: trades variance down, bias up (or vice versa) -- moves ALONG the curve,
  cannot fix irreducible bias / cannot beat the achievable floor

LEARNING CURVE (train vs val error vs training-set size, model fixed):
  HIGH BIAS: both curves converge to similarly poor error, small gap -> more data/regularization
             WON'T help; need better features / more expressive model
  HIGH VARIANCE: train low, val high, gap doesn't close -> MORE regularization or more data helps

sklearn: C = 1/lambda (INVERSE strength) for LogisticRegression/SVM -- small C = MORE regularization
XGBoost reg_alpha/reg_lambda: penalize LEAF WEIGHTS, not feature coefficients -- not lasso-style
  feature selection; max_depth/min_child_weight/subsample usually larger-effect levers first

double descent (Belkin 2019): test error can fall again PAST interpolation threshold in
  high-capacity models -- real but not a reason to always prefer bigger models in classical ML
```

## Sources

- [Ridge Regression: Biased Estimation for Nonorthogonal Problems — Hoerl & Kennard, Technometrics (1970)](https://www.tandfonline.com/doi/abs/10.1080/00401706.1970.10488634) — accessed 2026-08-03
- [Regression Shrinkage and Selection via the Lasso — Tibshirani, JRSS-B (1996)](https://www.jstor.org/stable/2346178) — accessed 2026-08-03
- [Regularization and Variable Selection via the Elastic Net — Zou & Hastie, JRSS-B (2005)](https://web.stanford.edu/~hastie/Papers/B67.2%20(2005)%20301-320%20Zou%20&%20Hastie.pdf) — accessed 2026-08-03
- [Reconciling modern machine learning practice and the bias-variance trade-off (double descent) — Belkin et al., PNAS (2019)](https://www.pnas.org/doi/10.1073/pnas.1903070116) — accessed 2026-08-03
- [scikit-learn: Linear Models documentation](https://scikit-learn.org/stable/modules/linear_model.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
