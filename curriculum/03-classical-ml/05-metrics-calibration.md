# Calibration, Imbalance, Metric Selection, and Why AUC Lies

> **Track:** T03 Classical ML · **Time:** 2h · **Prereqs:** T03-linear-models, T03-classic-models · **Updated:** 2026-08-03
> **Module id:** `T03-metrics-calibration` · **Tags:** evaluation, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A model's predicted probability being "calibrated" means that among all the times it predicts `p=0.7`, the true outcome happens roughly 70% of the time — this is a distinct property from accuracy or ranking quality, and most models (especially tree ensembles and Naive Bayes) are *not* calibrated out of the box even when their argmax classification is accurate, because their training objective (log-loss, Gini impurity, an independence-violating likelihood) doesn't directly target calibration. Platt scaling fits a one-dimensional logistic regression (`p = 1/(1+exp(A*f + B))`) on top of a model's raw scores using a held-out calibration set, works well when the miscalibration is roughly sigmoid-shaped, and needs little data; isotonic regression fits an arbitrary monotonic (non-decreasing) mapping via pool-adjacent-violators, is more flexible and can correct any shape of miscalibration, but needs more calibration data and can overfit with too little. Class imbalance breaks accuracy as a metric outright (a 99.9%-negative dataset gets 99.9% accuracy by predicting all-negative) and partially breaks AUC-ROC too, which is why AUC "lies": AUC-ROC is computed over the false-positive rate, which is normalized by the (huge) negative class count, so a model can have a stellar AUC-ROC while its precision at any operationally realistic threshold is terrible, because a small absolute number of false positives is a tiny fraction of a huge negative class but can dwarf the small number of true positives — precision-recall AUC, which is not normalized against the negative class size, is the metric that actually reflects this and is the correct default for meaningfully imbalanced problems. Metric selection is not a menu to pick the best-looking number from; it should be derived from the actual cost asymmetry of the business decision the model feeds (a missed fraud case costs differently than a false fraud alert), and getting this wrong is a more common and more damaging failure than any modeling choice in this module.

## Why this gets asked

Because "the model has 99% accuracy" or "we got 0.95 AUC" are the two most common misleading claims made about a shipped model, and an interviewer who has personally had to explain to a business stakeholder why a "99% accurate" fraud model was useless wants to know whether you'd catch that failure before it reaches production. It's also asked because calibration is the piece candidates most reliably skip — everyone can define precision and recall, far fewer can explain why a model's probabilities being wrong is a distinct, separately-fixable problem from its ranking or classification being wrong, or can name a concrete case where AUC looked great while the model was operationally useless.

---

## Lineage: past → present → future

**What came before.** Early classifier evaluation leaned almost entirely on accuracy, inherited from a statistics tradition where class balance was often reasonable by design (balanced experimental groups) — this broke down hard as ML moved into naturally imbalanced production domains (fraud, rare disease detection, ad click prediction, churn), where accuracy became not just unhelpful but actively misleading, since a trivial always-predict-majority-class model can post accuracy numbers that look impressive to a non-technical stakeholder. Precision, recall, and F1 (drawing on information retrieval, where the "relevant vs. retrieved" framing predates modern ML by decades) addressed the class-imbalance-blindness of accuracy directly, and ROC analysis (originally from WWII-era signal detection theory, adapted to ML) gave a threshold-independent way to compare classifiers' ranking ability — but ROC/AUC inherited its own blind spot from being normalized against a possibly-huge negative class, which is exactly the "AUC lies" failure this module centers on.

**Where it stands now.** The current consensus is that metric choice must be derived from the deployment context — cost-sensitive analysis (what does a false positive actually cost versus a false negative, in real business terms) rather than picking whichever standard metric looks most favorable, and precision-recall curves/AUC-PR as the accepted correction for AUC-ROC's imbalance blind spot on meaningfully skewed problems. Calibration has moved from a niche statistical concern to a standard production checklist item, particularly wherever a model's raw probability (not just its ranking) feeds a downstream decision directly — risk-based pricing, resource allocation under a budget constraint, or any system where probabilities from multiple models get combined or compared. The live disagreement is less about mechanics (Platt scaling versus isotonic regression is a well-understood tradeoff) and more about process: how much of metric/threshold selection should be automated (optimize a single objective function directly) versus deliberately kept as a human business decision informed by an explicit cost matrix, since automating past that point risks quietly encoding an implicit, unexamined value judgment about which error type matters more.

**Where it's heading.** Expect continued growth in calibration-under-distribution-shift as a distinct area of concern — a model calibrated well on today's data can silently decalibrate as the underlying population shifts (a well-documented production failure mode, distinct from ordinary concept drift affecting accuracy), and monitoring calibration drift specifically (not just accuracy/AUC drift) is becoming a more standard part of production ML monitoring stacks. For imbalanced-data evaluation, the direction is toward more standardized reporting of precision-recall-based metrics alongside ROC-based ones by default in tooling (rather than requiring a practitioner to know to ask for them), reducing how often "we only looked at AUC-ROC" becomes a root cause of a production surprise.

---

## Mental model

```
CALIBRATION vs DISCRIMINATION -- two DIFFERENT properties, a model can have either without the other

  well-calibrated, poor discrimination:      poor calibration, great discrimination:
  predicts ~0.5 for almost everything,       correctly RANKS positives above negatives,
  and the base rate really IS ~0.5           but predicted numbers are systematically
  (technically "calibrated" but useless      too extreme (e.g. always near 0 or 1)
  for ranking/decisions)                     -- correct ORDER, wrong MAGNITUDE

RELIABILITY DIAGRAM (the tool for seeing calibration):
  predicted probability (x-axis, binned) vs observed frequency (y-axis)
    1.0 |                                    .·
        |                              .·´
        |                        .·´              <- perfectly calibrated = diagonal
        |                  .·´
        |            .·´         x  x  x           <- model's actual curve (e.g., a tree
        |      .·´          x  x                       ensemble systematically overconfident
    0.0 |x  x                                          near the extremes)
        0.0 ---------------------------------- 1.0

AUC-ROC vs AUC-PR under imbalance (99% negative, 1% positive):
  ROC's x-axis (FPR = FP / (FP+TN)) is normalized by the HUGE negative class
    -> a small ABSOLUTE number of false positives is a TINY FPR -> AUC-ROC looks great
  PR's x-axis (recall) and y-axis (precision = TP/(TP+FP)) are NOT normalized this way
    -> the same false positives, compared against a SMALL number of true positives,
       tank precision -> AUC-PR reveals what AUC-ROC hid
```

The one-line mental model: **calibration asks "are the numbers right," discrimination/ranking asks "is the order right," and metric selection under imbalance is entirely about which axis your chosen metric normalizes against — normalizing against a huge negative class (as ROC's FPR does) hides exactly the failure that matters for a rare positive class.**

---

## How it actually works

### Why tree ensembles and Naive Bayes are poorly calibrated by default, mechanically

A random forest's predicted "probability" for a class is typically the fraction of trees voting for that class — this is a discrete, coarse-grained quantity (bounded by the number of trees) that has no reason to match the *true* conditional probability, since the training objective (impurity reduction per split) never directly optimizes the output to be a calibrated probability, only to separate classes well. Gradient boosting's log-loss objective is somewhat better-aligned with calibration in principle, but regularization (shrinkage, depth limits) and the additive-tree structure still commonly produce probabilities that are systematically compressed toward the middle or pushed toward extremes depending on the specific loss and regularization settings. Naive Bayes, as derived in the previous module, multiplies per-feature likelihoods as if independent, which compounds evidence more aggressively than warranted when features are correlated, systematically pushing posteriors toward 0 or 1 more than the true probability justifies.

### Platt scaling: fitting a sigmoid on top of raw scores

Platt scaling (Platt, 1999) fits `p = 1/(1 + exp(A*f + B))` where `f` is the model's raw, uncalibrated score (e.g., an SVM's signed distance from the margin, or an uncalibrated classifier's raw log-odds) and `A, B` are fit by maximum likelihood on a **held-out calibration set** (never the same data the base model was trained on, or the calibration will inherit the base model's own overfitting). This is a simple, low-variance fix — only two parameters to estimate — but assumes the miscalibration has a specific sigmoid shape, which works well in practice for many models (particularly SVMs, which is what Platt scaling was originally designed for) but can systematically fail to correct miscalibration with a different functional shape.

### Isotonic regression: a flexible, assumption-light alternative

Isotonic regression fits an arbitrary non-decreasing (monotonic) step function mapping raw scores to calibrated probabilities, found via the pool-adjacent-violators (PAV) algorithm: start with each point as its own "block," and whenever an adjacent pair of blocks violates monotonicity (a later block's average outcome is lower than an earlier one's), merge them and average, repeating until the sequence is fully monotonic. This makes essentially no assumption about the *shape* of the miscalibration (only that a higher raw score should correspond to a probability that is no lower than a lower raw score's — a mild, generally safe assumption), so it can correct calibration errors Platt scaling's fixed sigmoid shape cannot. The cost is more effective parameters to estimate (each step boundary), meaning it needs meaningfully more calibration data to avoid overfitting the calibration mapping itself, especially in regions with few examples. scikit-learn's `CalibratedClassifierCV` implements both (`method='sigmoid'` for Platt, `method='isotonic'`), fitting the base classifier and the calibration mapping via cross-validation so the calibration is always evaluated on held-out folds relative to what trained it ([scikit-learn calibration documentation](https://scikit-learn.org/stable/modules/calibration.html) — accessed 2026-08-03).

### Measuring calibration quantitatively: reliability diagrams and Brier score

A reliability diagram bins predictions by predicted probability and plots the observed positive rate within each bin against the bin's average predicted probability — a perfectly calibrated model traces the diagonal exactly. The Brier score (`(1/n) * sum((p_i - y_i)^2)`, mean squared error between predicted probability and the binary outcome) decomposes into calibration and refinement (discrimination-related) components, making it a single number that rewards both good ranking *and* good calibration simultaneously — unlike accuracy, AUC, or log-loss alone, none of which cleanly separates these two properties in a way that's easy to reason about independently. Expected Calibration Error (ECE) — the weighted average absolute gap between predicted probability and observed frequency across bins — is the most commonly reported single-number calibration metric in practice, though it's sensitive to binning scheme choice, a real practical caveat when comparing ECE values across different reported analyses.

### Why AUC-ROC specifically lies under class imbalance

AUC-ROC integrates the ROC curve, which plots true positive rate (`TPR = TP/(TP+FN)`) against false positive rate (`FPR = FP/(FP+TN)`) across all thresholds. Under heavy imbalance (say 1% positive, 99% negative in a 100,000-row dataset — 1,000 positives, 99,000 negatives), `FPR`'s denominator (`FP+TN ≈ 99,000`) is enormous, so even a large absolute number of false positives (say 2,000) produces a modest-looking FPR (~2%), keeping the ROC curve looking good and AUC-ROC high. But precision (`TP/(TP+FP)`) at that same operating point, with say 800 true positives caught, is `800/(800+2000) ≈ 29%` — meaning more than 70% of everything flagged as positive is actually a false alarm, a genuinely bad operational outcome that AUC-ROC's aggregate, imbalance-insensitive summary completely hides. AUC-PR (area under the precision-recall curve), because precision's denominator is `TP+FP` rather than the full negative-class-inflated `FP+TN`, directly reflects this false-alarm burden and is the standard corrective metric for meaningfully imbalanced problems — the baseline AUC-PR to compare against is the positive class's prevalence (a random classifier achieves AUC-PR equal to the base rate, unlike AUC-ROC's fixed 0.5 baseline regardless of imbalance), which is itself a fact worth having memorized since "AUC-PR of 0.3" means something very different at 1% versus 30% prevalence.

### Deriving why accuracy fails, with actual numbers

For a dataset with 1,000 positives and 99,000 negatives, a model that predicts "negative" unconditionally for every row achieves `99,000/100,000 = 99%` accuracy while catching zero positives — a completely useless model by any reasonable business standard, yet outscoring many genuinely useful models on the single number most stakeholders instinctively ask for first. This is not a corner case; it's the generic behavior of accuracy on any meaningfully imbalanced problem, which is why accuracy should essentially never be reported as the headline metric for an imbalanced classification problem without prominent context about the base rate.

---

## Build it from scratch

```python
import numpy as np

def platt_scaling_fit(scores, y, lr=0.1, n_iter=1000):
    """Fit p = sigmoid(A*f + B) via gradient descent on log-loss (see linear-models module
    for the identical p-y gradient derivation -- this IS logistic regression on 1 feature)."""
    A, B = 0.0, 0.0
    for _ in range(n_iter):
        z = A * scores + B
        p = 1 / (1 + np.exp(-z))
        grad_A = np.mean((p - y) * scores)
        grad_B = np.mean(p - y)
        A -= lr * grad_A
        B -= lr * grad_B
    return A, B

def pav_isotonic(scores, y):
    """Pool-adjacent-violators: sort by score, merge adjacent blocks that violate monotonicity."""
    order = np.argsort(scores)
    y_sorted = y[order].astype(float)
    blocks = [[v] for v in y_sorted]                      # each point starts as its own block
    means = [v for v in y_sorted]
    i = 0
    while i < len(blocks) - 1:
        if means[i] > means[i + 1]:                       # violation: merge and average
            merged = blocks[i] + blocks[i + 1]
            blocks[i:i + 2] = [merged]
            means[i:i + 2] = [np.mean(merged)]
            i = max(i - 1, 0)                              # re-check the newly-formed boundary
        else:
            i += 1
    calibrated = np.concatenate([[m] * len(b) for m, b in zip(means, blocks)])
    inverse_order = np.argsort(order)
    return calibrated[inverse_order]

def expected_calibration_error(probs, y, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        bin_acc = y[mask].mean()
        bin_conf = probs[mask].mean()
        ece += (mask.sum() / len(probs)) * abs(bin_acc - bin_conf)
    return ece

def precision_recall_at_threshold(scores, y, threshold):
    pred = scores >= threshold
    tp = np.sum(pred & (y == 1))
    fp = np.sum(pred & (y == 0))
    fn = np.sum(~pred & (y == 1))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall
```
The lab exercise generates a synthetic imbalanced dataset (1% positive), deliberately trains an uncalibrated random forest, plots its reliability diagram before and after both calibration methods, and computes AUC-ROC versus AUC-PR side by side — the exercise is specifically designed so AUC-ROC looks acceptable while AUC-PR and a realistic-threshold precision number reveal the model is much weaker than AUC-ROC alone suggests, reproducing the "AUC lies" failure concretely rather than asserting it.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Model reports 99%+ accuracy and looks great in the initial review, then underperforms sharply once deployed against real business expectations | Severe class imbalance makes accuracy trivially high for a useless (majority-predicting) model | Report precision/recall/F1 and AUC-PR alongside or instead of accuracy for any meaningfully imbalanced problem; state the base rate explicitly next to any accuracy number |
| AUC-ROC looks strong (e.g., 0.90+) but the fraud/anomaly team reports the model generates far too many false alarms at any usable threshold | AUC-ROC's FPR is normalized against a huge negative class, hiding a large absolute false-positive count relative to the small positive class | Switch primary reporting to AUC-PR and precision at the operationally realistic threshold/budget, not AUC-ROC alone |
| A model's predicted probabilities, when averaged across a large batch, don't match the batch's true observed positive rate | Model's probabilities are uncalibrated (common for tree ensembles, Naive Bayes, raw SVM scores) | Apply Platt scaling or isotonic regression on a held-out calibration set; verify with a reliability diagram and ECE before and after |
| A previously well-calibrated model's probabilities silently become unreliable months after deployment, with no drop in overall accuracy or AUC | Calibration drift: the underlying population's base rate or feature distribution shifted in a way that specifically distorts probability magnitudes without necessarily hurting ranking/accuracy | Monitor calibration (reliability diagram, ECE) as a distinct production metric from accuracy/AUC, on a recurring schedule, not just at initial launch |
| Two models with very similar AUC-ROC are compared for a threshold-based production decision, and the "better" one by AUC-ROC performs worse in practice | AUC-ROC is a threshold-independent, aggregate ranking metric; it doesn't reflect performance at the *specific* operating threshold that matters for the actual decision | Compare models at the actual deployment threshold using precision/recall (or the real cost-weighted business metric) at that threshold, not an aggregate curve-area summary |

---

## Tradeoffs & when NOT to use it

- **Don't apply Platt scaling when the miscalibration is clearly non-sigmoid-shaped** (visible as a reliability diagram with multiple bends, not a single smooth S-curve deviation) — isotonic regression's flexibility will correct this while Platt scaling's rigid two-parameter sigmoid cannot, provided you have enough calibration data to support isotonic's larger effective parameter count.
- **Don't use isotonic regression with a small calibration set.** Its flexibility is a liability with too little data — it can overfit the calibration mapping itself, producing a jagged, unreliable step function; Platt scaling's low-variance two-parameter fit is the safer default when calibration data is limited (a commonly cited rough threshold is at least several hundred to low thousands of calibration examples per class before isotonic's flexibility reliably pays off over Platt's simplicity, though this depends on how non-sigmoid the true miscalibration shape is).
- **Don't report AUC-ROC as the sole metric for any meaningfully imbalanced classification problem.** It systematically understates the false-alarm burden by normalizing against a large negative class; always pair it with AUC-PR and/or precision/recall at the realistic operating threshold.
- **Don't treat metric selection as picking whichever number looks best.** Derive the metric (and threshold) from an explicit cost matrix reflecting the real asymmetry between false positive and false negative costs for the specific business decision — a fraud model and a medical screening model can have wildly different "correct" tradeoffs between precision and recall even with structurally identical class imbalance, because the costs of each error type differ.
- **Don't assume a model that was well-calibrated at launch stays calibrated indefinitely.** Recalibrate periodically or monitor calibration drift directly; a shift in the underlying population can silently break calibration well before it visibly breaks accuracy or ranking metrics.

---

## Interview questions

### Q1 — Define calibration precisely, and explain why a model can have excellent AUC-ROC while being badly miscalibrated.
**Testing:** whether calibration and discrimination are understood as genuinely separate properties, not synonyms for "the model is good."
**Answer:** Calibration means: among all instances where the model predicts probability `p`, the true positive rate among them is approximately `p`. AUC-ROC only measures whether positives are *ranked* above negatives on average across all thresholds — it says nothing about whether the specific numeric probability values are meaningful. A model can perfectly rank every positive above every negative (AUC-ROC = 1.0) while outputting wildly wrong probabilities (e.g., always predicting 0.99 for positives and 0.01 for negatives when the true rates are 0.6 and 0.1) — the ranking is flawless, the numbers are false.
**Follow-up trap:** *"Would recalibrating this hypothetical model change its AUC-ROC?"* — no; both Platt scaling and isotonic regression are monotonic transformations of the raw score, and a monotonic transformation cannot change the *ranking* of examples, only the numeric probability values assigned — so recalibration leaves AUC-ROC (a purely rank-based metric) exactly unchanged while potentially fixing calibration substantially.

### Q2 — Derive, with actual numbers, why AUC-ROC can look strong while precision at a realistic threshold is poor, on a 1% positive-rate dataset.
**Testing:** the concrete arithmetic behind "AUC lies," not just the conceptual claim.
**Answer:** With 1,000 positives and 99,000 negatives, suppose at some threshold the model catches 800 true positives (TPR = 80%) but also flags 2,000 false positives. `FPR = 2,000/99,000 ≈ 2.0%` — a small FPR that keeps the ROC curve looking favorable and contributes to a high AUC-ROC. But `Precision = 800/(800+2,000) ≈ 28.6%` — more than 7 in 10 flagged items are false alarms, an outcome that would likely be operationally unacceptable for most alerting/fraud use cases, and this failure is completely invisible if you only look at AUC-ROC.
**Follow-up trap:** *"What would the same scenario's AUC-PR baseline (random-classifier performance) be, and why does that matter for interpreting the number?"* — a random classifier's AUC-PR equals the positive class prevalence, here 1% — so an AUC-PR of, say, 0.3 on this dataset is meaningfully above a 0.01 random baseline (a large lift), whereas the same 0.3 AUC-PR on a 30%-prevalence dataset would be barely above random baseline — AUC-PR values are not comparable across datasets with different base rates without accounting for this, unlike AUC-ROC's fixed 0.5 random baseline regardless of imbalance.

### Q3 — What's the mechanical difference between Platt scaling and isotonic regression, and when would each fail?
**Testing:** the actual mechanism (parametric sigmoid vs. non-parametric monotonic step function) and each method's specific failure mode.
**Answer:** Platt scaling fits a two-parameter sigmoid `p=1/(1+exp(A*f+B))` via maximum likelihood on a held-out calibration set — low variance, but fails if the true miscalibration isn't sigmoid-shaped. Isotonic regression fits an arbitrary monotonic step function via pool-adjacent-violators, correcting any shape of miscalibration, but with many more effective parameters (one per step), it can overfit and produce an unreliable, jagged mapping when the calibration set is small.
**Follow-up trap:** *"If you only have 200 calibration examples with a 5% positive rate, which would you choose and why?"* — Platt scaling; with only ~10 positive examples in the calibration set, isotonic regression's flexible, many-parameter mapping would almost certainly overfit badly in the sparse positive-class region, while Platt scaling's two-parameter fit is far more robust to this little data, even though it makes a stronger shape assumption.

### Q4 — Why does accuracy fail as a metric on imbalanced data, with a concrete numeric example, and what should replace it?
**Testing:** the specific numeric failure, not a vague "accuracy is bad for imbalance" statement.
**Answer:** On a dataset with 1,000 positives and 99,000 negatives, predicting "negative" for every single row achieves 99% accuracy while catching zero true positives — a model with literally no discriminative value scores higher on accuracy than most genuinely useful models would. Replace accuracy with precision/recall/F1 (at a chosen threshold) and AUC-PR (threshold-independent), always reported alongside the base rate so the numbers have context.
**Follow-up trap:** *"Is there ANY situation where reporting accuracy alongside these is still useful for an imbalanced problem?"* — yes, as a sanity-check floor: if a candidate model's accuracy is *below* the trivial majority-class baseline (99% here), that's an immediate red flag regardless of how good its precision/recall look, since it suggests something is structurally wrong (e.g., a label-flipping bug) — accuracy is a bad *headline* metric for imbalance but a reasonable low-cost sanity check alongside the metrics that actually matter.

### Q5 — Explain the Brier score and what makes it different from reporting accuracy or AUC alone.
**Testing:** understanding that Brier score jointly captures calibration and discrimination in one number.
**Answer:** Brier score is `(1/n) * sum((p_i - y_i)^2)` — squared error between predicted probability and the binary outcome, averaged over all examples. It decomposes (via the standard Brier decomposition) into a calibration term and a refinement/discrimination term, meaning it penalizes both a model that ranks well but is miscalibrated, and a model that's calibrated but doesn't discriminate well (e.g., always predicting the base rate) — neither accuracy (ignores probability magnitude entirely) nor AUC (ignores probability magnitude, only cares about rank) captures both properties in a single number the way Brier score does.
**Follow-up trap:** *"If a model has a low (good) Brier score, does that guarantee it's both well-calibrated AND well-discriminating?"* — not necessarily in isolation; a low Brier score could in principle result from being good on one component and merely adequate on the other, since it's a sum of both terms — for a full picture you'd still want to inspect the calibration and discrimination components (or a reliability diagram plus AUC) separately rather than relying on the single aggregate Brier number alone for a complete diagnosis.

### Q6 — Design question: you're building a fraud detection model where the cost of missing a fraud case (false negative) is $500 average loss, and the cost of a false fraud alert (false positive, requiring manual review) is $15. How does this change your metric and threshold selection versus using a default 0.5 threshold?
**Testing:** connecting a concrete cost asymmetry directly to threshold selection, not just naming precision/recall.
**Answer:** The cost ratio (roughly 33:1 in favor of catching fraud) means the optimal decision threshold should favor recall heavily over precision relative to a naive 0.5 cutoff — the expected-cost-minimizing threshold can be derived directly from the cost matrix and the model's calibrated probability (flag as fraud whenever `p * $500 > (1-p) * $15`, i.e., `p > 15/515 ≈ 2.9%`), which requires the model's probabilities to actually be well-calibrated for this cost-weighted threshold derivation to be valid in the first place — this is a direct, concrete reason calibration isn't an academic nicety but a prerequisite for correct cost-sensitive decision-making.
**Follow-up trap:** *"What breaks in this cost-based threshold derivation if the model's probabilities are poorly calibrated?"* — the derived threshold (`p > 15/515`) assumes `p` genuinely reflects the probability of fraud; if the model is miscalibrated (e.g., systematically overconfident, predicting 0.5 when the true rate is 0.1), the derived cutoff will be applied to the wrong underlying probabilities, producing a threshold that doesn't actually minimize expected cost — this is exactly why calibration should be checked and fixed *before* deriving a cost-sensitive threshold, not after.

### Q7 — Why can calibration silently degrade in production even when accuracy and AUC-ROC remain stable?
**Testing:** understanding calibration drift as a distinct monitoring concern from ordinary accuracy/concept drift.
**Answer:** Calibration depends on the model's predicted probability magnitudes matching the *true* conditional probability of the outcome given the population's current feature distribution — if the underlying base rate shifts (e.g., fraud prevalence genuinely increases) while the relative ranking of who's more/less likely to be fraudulent stays largely intact, AUC-ROC (purely rank-based) and even accuracy (if the threshold happens to still separate classes reasonably) can look stable, while every predicted probability is now systematically off relative to the new true rate.
**Follow-up trap:** *"What monitoring signal would catch this before a stakeholder notices the model's outputs 'feel wrong'?"* — tracking the reliability diagram or ECE on a rolling window of recent production data with ground truth (once available, even with some lag), specifically watching for the calibration curve drifting away from the diagonal over time, independent of whether accuracy or AUC-ROC dashboards show any change — this requires deliberately monitoring calibration as its own metric, not inferring it's fine because other metrics look fine.

### Q8 — What's the actual mechanism by which the pool-adjacent-violators algorithm enforces monotonicity in isotonic regression?
**Testing:** the mechanical algorithm, not just "it makes it monotonic somehow."
**Answer:** PAV starts with each data point (sorted by raw score) as its own singleton block with that point's own outcome as its "average." It scans adjacent blocks; whenever an earlier block's average is greater than a later block's average (a monotonicity violation, since scores are sorted but outcomes aren't necessarily), it merges the two blocks into one and recomputes their combined average, then re-checks the newly formed boundary against its new neighbor (since a merge can create a new violation with the block before it). This repeats until no adjacent pair violates monotonicity, at which point every point within a merged block is assigned that block's average as its calibrated probability.
**Follow-up trap:** *"What does the resulting calibrated-probability function look like as a curve, and is that itself ever a problem?"* — it's a non-decreasing step function (flat within each merged block, jumping at block boundaries), not a smooth curve — this can be a problem when a smooth probability estimate is genuinely needed downstream (e.g., for a gradient-based optimization consuming the calibrated probability) or when the step boundaries fall in operationally important regions with few examples, producing an abrupt, poorly-estimated jump exactly where precision matters most.

### Q9 — A teammate reports "our new model has a higher AUC-ROC than the old one, so it's strictly better." What's the specific scenario where this conclusion is wrong?
**Testing:** recognizing that AUC-ROC comparisons can mislead for a threshold-based production decision even when technically correct as an aggregate statement.
**Answer:** AUC-ROC aggregates performance across *all* possible thresholds, but a production system almost always operates at one specific threshold (or a narrow realistic range). A model can have a higher AUC-ROC overall while performing *worse* than another model specifically at the threshold/operating region that matters in practice (e.g., one model might have a better curve at very low FPR — the region relevant to a fraud alert budget — while another has a better curve elsewhere but wins on average, inflating its overall AUC-ROC without winning where it counts).
**Follow-up trap:** *"How would you settle this disagreement concretely, without just repeating 'AUC-ROC isn't everything'?"* — plot both models' ROC (or better, precision-recall) curves and specifically compare them at the actual deployment operating point/threshold or budget constraint, rather than the aggregate area — if model B is better at the realistic operating region even with a lower overall AUC-ROC, that's the actionable, decision-relevant comparison, not the headline aggregate number.

### Q10 — Why is it important to calibrate on a held-out set separate from the data the base classifier was trained on, and what specifically goes wrong if you don't?
**Testing:** the overfitting-through-the-back-door failure mode of calibrating on training data.
**Answer:** A model's predictions on its own training data are systematically overconfident/optimistic relative to genuinely unseen data (it has, to varying degrees depending on model capacity and regularization, partially memorized the training set) — fitting a calibration mapping on these overly-optimistic scores would calibrate the model to match its own training-set overconfidence, not its true out-of-sample behavior, producing a calibration that looks good on paper but is wrong on real production data, which behaves like the base model's genuinely-held-out performance, not its training performance.
**Follow-up trap:** *"Does the same concern apply symmetrically if you calibrate on the SAME held-out set you'll later use to report the model's final performance metrics?"* — yes, and this is a related but distinct leakage risk: if the calibration set and the final evaluation set are the same data, your reported calibration quality (ECE, reliability diagram) is itself optimistically biased toward that specific held-out set, not a genuine third, independent test set — the clean setup uses three splits (train base model, calibrate, final-evaluate), not two, whenever the sample size allows it.

---

## Red flags that fail you

- Cannot state precisely what "calibrated" means, or conflates it with "accurate" or "good AUC."
- Reports accuracy as the headline metric on a clearly imbalanced problem without flagging the base rate.
- Cannot explain, with actual numbers, why AUC-ROC can look strong while precision at a realistic threshold is poor.
- Doesn't know that recalibration (Platt/isotonic) cannot change AUC-ROC, since both are monotonic transforms.
- Fits a calibration mapping on the same data used to train the base model.
- Picks a metric because it's the highest number rather than deriving it from the actual cost asymmetry of the business decision.

---

## Cheat card

```
CALIBRATION = "among predictions of p, true rate is ~p" -- DISTINCT from discrimination/ranking
  monotonic recalibration (Platt/isotonic) CANNOT change AUC-ROC (rank-based, unaffected by
  monotonic transforms) -- can only fix probability MAGNITUDE, never ranking

PLATT SCALING: p = 1/(1+exp(A*f+B)), 2 params, MLE on HELD-OUT calibration set
  low variance, fails if miscalibration isn't sigmoid-shaped; good with LITTLE calibration data
ISOTONIC: monotonic step function via pool-adjacent-violators (merge adjacent blocks
  violating order, average, repeat) -- fixes ANY shape, needs MORE calibration data or overfits
sklearn CalibratedClassifierCV: method='sigmoid' (Platt, default) | 'isotonic'

BRIER SCORE = mean((p-y)^2) -- decomposes into calibration + refinement terms,
  jointly penalizes bad ranking AND bad calibration (unlike accuracy/AUC alone)
ECE = weighted avg |predicted - observed| across bins -- sensitive to bin count choice

ACCURACY FAILS under imbalance: 1000 pos/99000 neg -> predict-all-negative = 99% accuracy,
  catches ZERO positives -- never report accuracy alone on imbalanced data

WHY AUC-ROC LIES: FPR = FP/(FP+TN) normalized by HUGE negative class
  -> 2000 false positives / 99000 negatives = 2% FPR (looks great)
  -> same 2000 FPs vs 800 TPs: precision = 800/2800 = 28.6% (actually bad)
  AUC-PR baseline (random classifier) = positive class PREVALENCE, not fixed 0.5 like ROC
  -> AUC-PR values NOT comparable across datasets with different base rates

COST-SENSITIVE THRESHOLD: flag positive when p*cost_FN > (1-p)*cost_FP
  -> threshold p* = cost_FP/(cost_FP+cost_FN) -- REQUIRES calibrated p to be valid

3-way split when sample size allows: train base model | calibrate | final-evaluate
  (calibrating on training data inherits the base model's own overconfidence)
```

## Sources

- [Probabilistic Outputs for Support Vector Machines — Platt (1999)](https://www.cs.colorado.edu/~mozer/Teaching/syllabi/6622/papers/Platt1999.pdf) — accessed 2026-08-03
- [Predicting Good Probabilities with Supervised Learning — Niculescu-Mizil & Caruana, ICML (2005)](https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf) — accessed 2026-08-03
- [scikit-learn: Probability calibration documentation](https://scikit-learn.org/stable/modules/calibration.html) — accessed 2026-08-03
- [The Relationship Between Precision-Recall and ROC Curves — Davis & Goadrich, ICML (2006)](https://www.biostat.wisc.edu/~page/rocpr.pdf) — accessed 2026-08-03
- [CalibratedClassifierCV — scikit-learn documentation](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
