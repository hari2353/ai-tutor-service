# Data & Concept Drift: PSI/KS/KL Detection, Shift Types, Retraining Triggers

> **Track:** T09 MLOps / LLMOps · **Time:** 2.5h · **Prereqs:** T08 · **Updated:** 2026-08-01
> **Module id:** `T09-data-drift` · **Tags:** production,critical

## The 30-second version

There are exactly three kinds of distributional shift and only one of them necessarily hurts you: covariate shift is P(X) changing while P(Y|X) holds, prior/label shift is P(Y) changing while P(X|Y) holds, and concept drift is P(Y|X) itself changing — the relationship the model learned is no longer true. Only concept drift necessarily degrades accuracy; covariate and label shift can leave a well-calibrated model just as accurate on the new distribution, which is why "drift detected" is not the same claim as "model broken." Detection is a toolbox, not one test: PSI for a fast, interpretable scalar per feature with standard thresholds (0.1 investigate, 0.25 act), KS for a nonparametric two-sample comparison that becomes uselessly oversensitive at large sample sizes, KL/JS divergence for a full distributional comparison, Wasserstein for a metric that respects the actual distance between values rather than just their shape, and a domain classifier for multivariate drift no univariate test can see. None of these tells you to retrain by themselves — retraining triggers should combine a drift signal with either a scheduled cadence or an observed performance drop, because retraining on statistical noise from an oversized sample is a real, recurring waste of compute and a real, recurring source of unnecessary model churn.

## Why this gets asked

The interviewer has been burned twice: once by a KS test that fired constantly once traffic grew past a few hundred thousand samples a day, because at that scale every distribution differs from every other distribution by a p-value indistinguishable from zero — and once by a retraining pipeline that fired on drift alone and produced a model that was measurably worse, because it retrained on three days of anomalous but ultimately reverted traffic. They want to know if you understand the taxonomy well enough to know *which kind of shift you're looking at* before reaching for a fix, and whether you know that a statistically significant drift signal and a business-significant one are different claims.

---

## Lineage: past → present → future

**What came before.** Early production ML (pre-2015 or so) had essentially no formal drift detection; the operating assumption was that a model trained once would keep working, and the failure mode was discovered via a slow decline in a business metric someone happened to be watching, often months after the underlying shift began. The academic vocabulary — covariate shift, concept drift — predates production ML tooling by a decade (Shimodaira's 2000 covariate shift correction paper, Gama et al.'s 2004/2014 surveys on concept drift in streaming data), but it lived in the data-mining/streaming-ML literature and had almost no bridge to industry practice until MLOps tooling matured. The pain that forced the bridge: teams running models at real scale (ad ranking, fraud, recommendations) kept discovering that model performance degraded on a timescale of weeks to months for reasons that had nothing to do with a bug — the world the model was trained on had simply moved.

**Where it stands now.** PSI, originally a credit-risk/banking statistic for monitoring score-distribution stability, has become the de facto standard for feature and prediction drift because it's cheap, interpretable, and the industry has converged on the 0.1/0.25 action thresholds even though they were never derived from first principles — they're a convention, not a law. KS tests remain common for continuous features but the field is aware, and increasingly vocal, that KS p-values are close to meaningless above a few thousand samples because statistical significance and practical significance diverge completely at scale: with enough samples, any two distributions that differ at all will reject the null. The live disagreement is exactly here — some practitioners (and tools like NannyML) now argue for **dropping p-value-based tests almost entirely in favor of effect-size measures (PSI, Wasserstein, or a domain-calibrated distance) with a fixed threshold**, precisely because sample size shouldn't determine whether you get paged [PSI or not PSI, that is the question — NannyML](https://nannymlnewsletter.substack.com/p/psi-or-not-psi-that-is-the-question) — accessed 2026-08-01. Multivariate drift detection via a domain classifier (train a classifier to distinguish "reference window" from "current window" samples; if it can, above chance, you have multivariate drift even if every individual feature's univariate test passes) is now standard practice in mature stacks, because univariate tests miss the common case where individual feature marginals look stable but their joint relationship has changed.

**Where it's heading.** High confidence: performance-estimation-without-labels (NannyML's CBPE — Confidence-Based Performance Estimation — and similar methods that estimate accuracy/AUC changes directly from prediction confidence and drift, without waiting for ground truth) becomes standard, because it closes the biggest practical gap in this module: knowing you have drift versus knowing whether it matters. Medium confidence: drift detection for LLM systems moves from ad hoc (watching output length, refusal rate) to embedding-space drift as a first-class signal — comparing the distribution of prompt/response embeddings over time, which generalizes PSI/KS-style univariate methods to unstructured text. Speculative: fully automated retraining triggered purely by combined drift+performance-estimate signals with no human review; the industry consensus for now is that a human gates the retrain decision even when the signal is high-confidence, because the cost of retraining on the wrong data (a legitimate but temporary shift, an upstream bug masquerading as drift) is asymmetric and expensive.

---

## Mental model

The three-way taxonomy, drawn as what changes and what stays fixed:

```
                    P(X)              P(Y|X)             Does accuracy
                    (input dist.)     (model relationship) necessarily drop?
                    ─────────────     ──────────────────  ──────────────────
COVARIATE SHIFT     CHANGES           fixed                NO — model can still
                                                            be correct on new X
                                                            (if it generalizes)

PRIOR/LABEL SHIFT   P(Y) changes,     fixed (P(X|Y) fixed) NO — base rates moved,
                    class balance                          decision boundary
                    shifts                                 can still be valid

CONCEPT DRIFT       (X may or may     CHANGES               YES, necessarily —
                    not change)                             the thing the model
                                                             learned is no longer
                                                             true
```

**The one-sentence test the interviewer wants:** "did the *relationship* the model learned change, or just the population it's being asked about?" Only the former is concept drift, and only concept drift is *guaranteed* to hurt you — the other two might hurt you if your model doesn't generalize well to the new region of input space, but they don't hurt you by definition.

Temporal shape of drift — the four patterns you must be able to name and distinguish:

```
SUDDEN        ──────┐
              value  └──────────────────  (step function — a pipeline change,
                                            a new product launch, a schema fix)

GRADUAL       ──────╲___
                         ╲____             (slow linear-ish trend — user
                              ╲___          behavior evolving over months)

INCREMENTAL   ──╱‾╲_╱‾╲_╱‾╲_╱‾            (many small changes accumulating,
                                            noisier than gradual, trend less clean)

RECURRING /   ──╱╲──╱╲──╱╲──╱╲──          (seasonal — weekday/weekend,
SEASONAL                                   holiday shopping, back-to-school)
```

---

## How it actually works

### PSI — Population Stability Index

The workhorse. Bucket both the reference and current distributions into the same bins (standard practice: 10 buckets via reference-distribution deciles, or equal-width bins for scores already bounded like [0,1] probabilities), then:

```
PSI = Σ (current_pct_i - reference_pct_i) × ln(current_pct_i / reference_pct_i)
```

```python
import numpy as np

def psi(reference: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
    # bucket edges from the REFERENCE distribution's quantiles — this is the
    # standard convention; bucketing on current data instead silently hides drift
    edges = np.quantile(reference, np.linspace(0, 1, buckets + 1))
    edges[0], edges[-1] = -np.inf, np.inf   # catch any current values outside ref range

    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    ref_pct = np.clip(ref_counts / len(reference), 1e-6, None)  # avoid log(0)
    cur_pct = np.clip(cur_counts / len(current), 1e-6, None)

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
```

**Standard action thresholds** (banking/credit-risk convention, now general practice): PSI < 0.1 — no significant shift, no action. 0.1 ≤ PSI < 0.25 — moderate shift, investigate. PSI ≥ 0.25 — significant shift, action needed (typically: escalate toward a performance check or retraining review) [Measuring Data Drift with PSI — Fiddler AI](https://www.fiddler.ai/blog/measuring-data-drift-population-stability-index) — accessed 2026-08-01. These thresholds are a convention inherited from credit scoring, not a statistically derived boundary — know this when an interviewer pushes on "why 0.25 specifically."

**Why 10 buckets from reference deciles, and why it matters:** binning on the *reference* distribution's quantiles means each reference bucket starts with exactly 10% of the mass by construction; the current distribution's departure from that even split is what PSI measures. Binning on the current distribution instead defeats the whole point — it would always look approximately uniform since you built the bins around it.

### KS test — and why it's sensitive to sample size in a way that bites at scale

The Kolmogorov-Smirnov two-sample test compares the maximum distance between two empirical CDFs and returns a p-value against the null hypothesis "these two samples come from the same distribution."

```python
from scipy.stats import ks_2samp
statistic, p_value = ks_2samp(reference_sample, current_sample)
```

**The sample-size trap, stated precisely:** the KS statistic (the max CDF distance) is a genuine effect-size measure and is fine at any sample size. The **p-value is not** — statistical power scales with sample size, so with n in the hundreds of thousands (routine in production), even a trivial, practically meaningless difference between distributions produces a p-value of essentially zero. A team alerting on "p < 0.05" at production scale is functionally alerting on every single window, because two independently-drawn samples from the *same* distribution will still show detectable differences given enough data. The fix isn't a different test, it's **switching the decision rule from p-value to the KS statistic itself with a fixed threshold** (analogous to using PSI's effect size instead of a significance test), or subsampling to a fixed size before running the test so the test's sensitivity doesn't scale with traffic.

### KL divergence, JS divergence, and Wasserstein

**KL divergence** — asymmetric, measures how much information is lost approximating current with reference: `KL(P||Q) = Σ P(x) log(P(x)/Q(x))`. Undefined where Q(x)=0 and P(x)>0, which is a real practical problem with sparse categorical features — you have to smooth. Asymmetry means `KL(ref||cur) ≠ KL(cur||ref)`, and picking the wrong direction changes what the number means, which is a common source of confusion in interviews and in real dashboards.

**JS divergence** — the symmetrized, smoothed version: `JS(P,Q) = 0.5·KL(P||M) + 0.5·KL(Q||M)` where `M = 0.5(P+Q)`. Always finite (no division-by-zero issue), bounded between 0 and 1 (with log base 2), and symmetric — generally the more practically usable of the two for drift dashboards.

**Wasserstein distance (earth mover's distance)** — the cost of literally moving probability mass from one distribution to match the other, respecting the actual numeric distance between values, not just their frequency shape. This matters concretely: PSI and KL treat a bucket shift from [0,10] to [10,20] the same as a shift to [90,100] as long as the *proportions* moved are equal, but Wasserstein correctly reports the second as a much larger drift. For continuous, ordinally meaningful features (age, price, latency) Wasserstein is often the more honest metric; for unordered categoricals it isn't well-defined in the same way.

```python
from scipy.stats import wasserstein_distance
w = wasserstein_distance(reference_sample, current_sample)
```

### Multivariate drift — the domain classifier trick

Every method above is univariate: run it per feature, get one number per feature. This misses the common real case where each feature's marginal distribution looks fine but the *joint* relationship between features has shifted — e.g., `age` and `income` each look individually stable, but their correlation has flipped.

**The domain classifier method:** label all reference-window rows `0` and all current-window rows `1`, train a simple classifier (gradient-boosted trees work well) to distinguish them using the full feature set, and evaluate its AUC on held-out data from both windows. AUC ≈ 0.5 means the classifier can't tell the windows apart — no detectable multivariate drift. AUC significantly above 0.5 (0.7+ is a common practical trigger) means there's a learnable, real difference between the two populations, and the classifier's feature importances tell you *which* features are driving the separation — turning "there's drift" into "there's drift, and it's mostly in features X and Y," which is what someone can actually act on.

```python
# untested sketch
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

def domain_classifier_drift(reference_df, current_df, feature_cols):
    X = np.vstack([reference_df[feature_cols].values, current_df[feature_cols].values])
    y = np.array([0] * len(reference_df) + [1] * len(current_df))
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=0
    )
    clf = GradientBoostingClassifier(max_depth=3, n_estimators=100)
    clf.fit(X_train, y_train)
    auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])
    importances = dict(zip(feature_cols, clf.feature_importances_))
    return {"drift_auc": auc, "top_features": sorted(
        importances.items(), key=lambda kv: -kv[1])[:5]}
```

### Reference-window selection — and why a rolling reference hides slow drift

Two designs, with very different failure modes:

- **Fixed reference** (e.g., the training-set distribution, frozen at deploy time): correctly detects *any* cumulative drift away from what the model was trained on, including slow gradual drift — because the comparison point never moves.
- **Rolling reference** (e.g., "last 7 days" compared to "this week"): adapts to legitimate slow change (useful for genuinely evolving seasonality) but has a serious blind spot — **gradual drift that moves slower than the window length becomes invisible**, because each window looks only mildly different from the one just before it, even though the cumulative drift from the original training distribution may be enormous. This is the same failure class as the sliding-reference bug flagged in `T09-model-monitoring`'s build-from-scratch sketch: a monitor whose baseline absorbs the drift stops seeing it.

**Practical resolution used in mature stacks:** keep the training-time distribution as a permanent, never-updated reference for long-horizon drift detection, *and* run a rolling short-window comparison for fast operational alerting — they answer different questions and neither substitutes for the other.

### Retraining triggers: scheduled vs threshold vs performance-based

| Trigger type | Mechanism | Failure mode if used alone |
|---|---|---|
| **Scheduled** (e.g., retrain weekly/monthly regardless of signal) | Simple, predictable compute budget, no monitoring dependency | Wastes compute on stable periods; misses fast drift between scheduled runs |
| **Threshold-based** (PSI/KS/domain-classifier crosses a fixed bar) | Reactive, catches drift as it happens | Retrains on statistical noise at high sample sizes, or on benign covariate/label shift that doesn't hurt accuracy — churns the model for no gain and burns real compute and validation cost each time |
| **Performance-based** (accuracy/AUC drop, or NannyML-style estimated performance drop without labels) | Most directly tied to the thing you actually care about | Requires either fast-arriving labels or a trustworthy performance-estimation method; without either, this trigger simply never fires in time |

**The honest answer, and what most mature teams actually run:** a scheduled cadence as the floor (so staleness has a hard ceiling regardless of monitoring gaps), gated by a threshold-based drift check to skip unnecessary scheduled retrains on genuinely stable periods, escalated to an out-of-cycle retrain only when drift *and* a performance signal (real or estimated) agree. Retraining on drift alone, with no performance corroboration, is the single most common way teams waste compute and introduce unnecessary model churn — a model that changes behavior every week because it's retrained on noise is worse for downstream consumers (anything depending on stable model behavior, from cached recommendations to compliance sign-off) than one that's mildly stale.

### A concrete numeric example tying it together

Say a fraud model has PSI = 0.31 on the `transaction_amount` feature this week (above the 0.25 action threshold), and a domain classifier trained on all features gets AUC = 0.58 (barely above chance — most of the multivariate signal is *not* there). Labels lag 45 days, so no real accuracy read exists yet. The correct call: this looks like a univariate covariate shift concentrated in one feature (maybe a promotional pricing change shifted the transaction-amount distribution), not broad concept drift — investigate the single feature, check whether the shift correlates with a known business event, and do **not** trigger an emergency retrain on this signal alone. Escalate to retraining only if a fast proxy (e.g., manual-review disagreement rate, `T09-model-monitoring`'s proxy list) also moves, or once real labels confirm an actual accuracy drop.

---

## Build it from scratch

A compact drift-check runner that combines PSI (per feature) with the domain-classifier multivariate check, the two techniques that catch what the other misses.

```python
# untested sketch
import numpy as np
import pandas as pd

def psi(reference: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
    edges = np.quantile(reference, np.linspace(0, 1, buckets + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    ref_pct = np.clip(np.histogram(reference, bins=edges)[0] / len(reference), 1e-6, None)
    cur_pct = np.clip(np.histogram(current, bins=edges)[0] / len(current), 1e-6, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))

def drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame,
                  numeric_cols: list[str]) -> dict:
    report = {"per_feature_psi": {}, "flags": []}
    for col in numeric_cols:
        score = psi(reference_df[col].values, current_df[col].values)
        report["per_feature_psi"][col] = round(score, 4)
        if score >= 0.25:
            report["flags"].append(f"{col}: PSI={score:.3f} (ACTION)")
        elif score >= 0.10:
            report["flags"].append(f"{col}: PSI={score:.3f} (investigate)")

    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score

    X = pd.concat([reference_df[numeric_cols], current_df[numeric_cols]]).values
    y = np.array([0] * len(reference_df) + [1] * len(current_df))
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, stratify=y, random_state=0)
    clf = GradientBoostingClassifier(max_depth=3, n_estimators=100).fit(X_tr, y_tr)
    auc = roc_auc_score(y_te, clf.predict_proba(X_te)[:, 1])
    report["multivariate_drift_auc"] = round(auc, 4)
    if auc >= 0.7:
        report["flags"].append(f"multivariate drift AUC={auc:.3f} (joint relationship changed)")

    return report
```

This is the shape of what Evidently/NannyML compute internally; the value in building it yourself is understanding exactly what "PSI = 0.31" and "drift AUC = 0.58" each do and don't tell you, which is precisely the distinction the interview questions below probe.

---

## How it's done in production

| Tool | What it adds over the sketch above |
|---|---|
| **Evidently AI** | Pre-built reports (data drift, target drift, data quality), supports PSI/KS/Wasserstein/JS out of the box, works as a library over batches or a hosted service, good visual reporting |
| **NannyML** | Performance-estimation-without-labels (CBPE, DLE) as the headline feature — closes the "is this drift actionable" gap directly rather than relying on drift-as-proxy; increasingly the second tool paired with Evidently in mature stacks |
| **Alibi Detect** | Broadest algorithm coverage (MMD, learned kernels, various concept-drift detectors like ADWIN/DDM for streaming), more research-oriented, used when the standard PSI/KS toolkit isn't sufficient |
| **WhyLabs (whylogs)** | Lightweight statistical profiling computed at the edge/source, ships compact profiles rather than raw data — relevant when data can't leave a boundary (privacy, cost of transfer) |
| **River (streaming ML)** | Implements classic streaming concept-drift detectors (ADWIN, DDM, EDDM, Page-Hinkley) for true online/incremental settings, distinct from the batch-window comparison approach used elsewhere in this module |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Drift alert fires on every single window at high traffic | KS p-value used as the decision rule; power scales with n | Switch to KS statistic or PSI with a fixed effect-size threshold, not a p-value |
| PSI stays low despite an obviously different-looking distribution | Wrong bucketing (bucketed on current data, or too few buckets for the feature's real range) | Bucket on reference-distribution quantiles; use enough buckets (10 is standard) to resolve the shape |
| Drift detected, retrain triggered, new model performs worse | Retrained on threshold alone during a benign or temporary covariate shift, not corroborated by a performance signal | Require drift + performance signal (real or estimated) to agree before an out-of-cycle retrain |
| All univariate tests pass, model still degrading | Multivariate drift — feature marginals stable, joint relationship changed | Add a domain-classifier check across the full feature set |
| Rolling-reference drift monitor never alerts despite years of model staleness | Reference window slides forward and absorbs gradual drift into its own baseline | Keep a frozen training-time reference for long-horizon detection alongside the rolling window |
| KL divergence returns infinity | Zero-probability bucket in reference but nonzero in current (or vice versa), common with sparse categoricals | Smooth both distributions (Laplace/additive smoothing) or switch to JS divergence, which is always finite |
| Team retrains weekly on schedule, cost balloons, no measurable improvement | Scheduled-only trigger with no drift/performance gate | Gate scheduled retrains behind a drift or performance check; skip when both are quiet |
| Model flagged as drifted but business metric hasn't moved at all | Covariate or label shift without concept drift — the model still generalizes | Confirm via a performance-estimation method (or wait for labels) before treating this as an incident |

---

## Tradeoffs & when NOT to use it

- **Don't run p-value-based hypothesis tests (KS, chi-square) as your primary alerting mechanism at high sample sizes.** They will alert constantly and correctly-but-uselessly on trivial differences. Use effect-size measures (PSI, Wasserstein, KS statistic itself) with fixed, calibrated thresholds instead.
- **Don't treat any drift signal as sufficient justification to retrain on its own.** Covariate and label shift are explicitly *not* guaranteed to hurt accuracy; retraining reflexively on drift alone is a common, real source of wasted compute and unnecessary model churn.
- **Don't run heavyweight multivariate drift detection (domain classifier) on every feature update in real time if traffic and feature count make it expensive.** It's valuable as a periodic (daily/weekly) diagnostic layered on top of cheap univariate checks (PSI) that run continuously, not as a replacement for them.
- **Don't use a purely rolling reference window if you need to detect slow, cumulative drift.** It will structurally hide exactly that pattern. Pair it with a frozen long-horizon reference.
- **Don't bother with formal drift detection at all for a model retrained on every batch run from fresh data** (e.g., a daily-refreshed ranking model trained on that day's data) — there's no meaningful "reference" distribution to compare against when the training data itself rolls forward every cycle; monitor output/business metrics directly instead.
- **KL divergence is the wrong choice for sparse categorical features with many rare values** — division by (near-)zero probabilities makes it numerically unstable; use JS divergence or a chi-square-style test with pooled rare categories instead.

---

## Interview questions

### Q1 — Define covariate shift, label shift, and concept drift precisely.
**Testing:** whether the taxonomy is memorized correctly, not approximately.
**Answer:** Covariate shift: P(X) changes, P(Y|X) stays fixed. Label/prior shift: P(Y) changes, P(X|Y) stays fixed. Concept drift: P(Y|X) itself changes — the model's learned relationship is no longer true.
**Follow-up trap:** *"Which one is guaranteed to hurt accuracy?"* — only concept drift, by definition. The other two can leave a well-generalizing model just as accurate; they only hurt if the model doesn't generalize well to the new region of input space or new class balance.

### Q2 — Why does a KS test become useless at large sample sizes?
**Testing:** statistical maturity beyond "I know the test exists."
**Answer:** Statistical power scales with n. At production scale (hundreds of thousands of samples), even a trivially small, practically meaningless difference between two distributions produces a near-zero p-value, because with enough data any two non-identical distributions are distinguishable. The KS *statistic* (max CDF distance) is still a valid effect size; it's specifically the p-value-based decision rule that breaks.
**Follow-up trap:** *"So how do you fix it without abandoning KS?"* — use the statistic itself against a fixed, calibrated threshold instead of the p-value, or subsample both windows to a constant size before testing so sensitivity doesn't scale with traffic.

### Q3 — Walk through PSI's formula and explain why buckets come from the reference distribution.
**Answer:** `PSI = Σ(cur_pct - ref_pct) × ln(cur_pct/ref_pct)`, summed over buckets. Bucketing on the reference distribution's quantiles (typically deciles) means each reference bucket starts at exactly 10% by construction, so any departure from an even split in the *current* data is the actual drift signal. Bucketing on current data instead would make the current distribution look artificially uniform against itself.
**Follow-up trap:** *"What breaks the formula, numerically?"* — a bucket with zero count in either window produces log(0) or division by zero; production implementations clip percentages to a small epsilon floor before the log.

### Q4 — PSI = 0.31 on one feature. What do you do?
**Answer:** 0.31 is above the standard 0.25 action threshold, so it warrants investigation and likely escalation — but PSI alone doesn't tell you whether this is concept drift or a benign covariate shift. Check whether it correlates with a known event (promotion, seasonality, upstream pipeline change), and check a multivariate/domain-classifier signal and any available performance proxy before deciding to retrain.
**Follow-up trap:** *"The business metric hasn't moved at all. Do you still retrain?"* — not on this signal alone. A high PSI with a flat business metric is consistent with covariate shift that the model handles fine; corroborate with a performance signal before spending the retraining and validation budget.

### Q5 — What does a domain classifier catch that per-feature PSI cannot?
**Answer:** Multivariate drift — cases where every individual feature's marginal distribution looks stable (each univariate test passes) but the joint relationship between features has changed. Training a classifier to distinguish reference-window rows from current-window rows and checking its AUC against 0.5 detects this directly, and its feature importances localize which features are driving the separation.
**Follow-up trap:** *"Your domain classifier gets AUC 0.9. Is that definitely concept drift?"* — no, it's definitely multivariate *distributional* drift (P(X) has changed in a way univariate tests missed); it says nothing about whether P(Y|X) changed. You still need a performance signal to confirm actual concept drift.

### Q6 — Explain the difference between KL divergence, JS divergence, and Wasserstein distance, and when you'd pick each.
**Answer:** KL is asymmetric and undefined where the reference has zero probability but current doesn't — a real problem for sparse categoricals. JS symmetrizes and bounds KL via a midpoint distribution, always finite, generally more usable for dashboards. Wasserstein respects the actual numeric distance between values, not just how probability mass is shaped, so it correctly distinguishes "mass moved a little" from "mass moved a lot" in a way PSI/KL/JS (which only look at proportions per bucket) cannot.
**Follow-up trap:** *"Give a case where PSI and Wasserstein disagree on severity."* — a feature shift from bucket [0,10] to [10,20] versus a shift to [90,100], with equal proportion of mass moved in both cases: PSI/KL/JS report identical drift magnitude because they only see proportions per bucket, while Wasserstein correctly reports the second as far more severe because the values themselves moved farther.

### Q7 — Why does a rolling reference window hide slow drift?
**Answer:** If each comparison window is measured against the window immediately before it, gradual drift that moves slower than the window length looks like a series of small, individually-insignificant changes, even though the cumulative drift from the original training distribution can be enormous. The reference itself is drifting along with the data.
**Follow-up trap:** *"How do you fix this without losing the benefit of a rolling window for fast, operational signals?"* — run both: a frozen training-time reference for long-horizon cumulative drift detection, and a rolling short window for fast operational alerting. They answer different questions.

### Q8 — Design a retraining trigger policy. Don't just say "retrain on drift."
**Testing:** whether the candidate understands the cost side of the tradeoff, not just detection.
**Answer:** A scheduled floor cadence (so staleness has a hard ceiling), gated by a cheap threshold check (skip the scheduled retrain if drift is quiet), escalated to an out-of-cycle retrain only when drift and a performance signal (actual accuracy or an estimation method like CBPE) agree. Retraining on drift alone churns the model on noise and burns real compute and validation cost.
**Follow-up trap:** *"Your fraud model has a 60-day label lag. How do you get a performance signal fast enough to gate retraining?"* — you don't get a real one in time; use a faster proxy (manual-review disagreement, a cheap heuristic model's agreement rate) as the corroborating signal instead of blocking on true labels, same pattern as `T09-model-monitoring`'s ground-truth-delay proxies.

### Q9 — What does performance-estimation-without-labels (CBPE-style) actually do, and why does it matter?
**Answer:** It estimates a model's accuracy/AUC on unlabeled production data using the model's own confidence/probability outputs combined with observed drift, calibrated against the labeled distribution seen during training or validation. It matters because it directly answers "did performance actually drop," which is the thing drift detection can only proxy for — closing the gap between "drift detected" and "should we act."
**Follow-up trap:** *"What's the failure mode of trusting this blindly?"* — it's an estimate, not ground truth, and it degrades in accuracy itself under severe or novel drift (exactly the situations where you'd most want to trust it). Validate it periodically against real labels once they arrive, the same way you'd validate an LLM-as-judge score.

### Q10 — A model's accuracy on a fixed holdout stays constant, but PSI on three input features has been climbing for two months. Is this a problem?
**Testing:** whether the candidate can separate "drift exists" from "drift matters," using the taxonomy from Q1.
**Answer:** This is the textbook signature of covariate shift without concept drift: the input population is moving but the model's learned relationship still holds well enough that accuracy on labeled data hasn't dropped. It's worth continued monitoring (the model may eventually see input regions it generalizes poorly to) but it is not, on its own, justification for an emergency retrain.
**Follow-up trap:** *"When would rising PSI with flat accuracy still worry you?"* — if the fixed holdout no longer represents the current input population (it's stale itself), so "flat accuracy on holdout" is measuring the wrong thing. Refresh the holdout's own distribution periodically, or you're evaluating against a population that no longer exists in production.

### Q11 — Distinguish sudden, gradual, incremental, and recurring drift, and give a retraining implication for each.
**Answer:** Sudden — a step function, usually a pipeline/schema/product change; needs fast detection and often an emergency retrain or rollback. Gradual — a slow, roughly monotonic trend (evolving user behavior); a scheduled retraining cadence usually keeps pace without needing threshold-based urgency. Incremental — many small changes accumulating noisily, harder to distinguish from gradual, needs a longer observation window before acting to avoid retraining on noise. Recurring/seasonal — cyclical (weekday/weekend, holidays); the correct response is often *not* retraining at all but training a model that explicitly conditions on the seasonal signal, or maintaining season-specific models.
**Follow-up trap:** *"How do you tell gradual drift from a very slow-moving seasonal cycle from a single window?"* — you often can't from one window; you need history spanning at least a full seasonal cycle before concluding "gradual" rather than "recurring," which is a real reason short-lived monitoring deployments misdiagnose seasonal drift as a trend.

### Q12 — At staff/principal level: your retraining pipeline has a 30% compute cost increase and stakeholders ask if it's worth it. How do you answer with this module's concepts?
**Answer:** Audit what's actually triggering retrains — if it's threshold-based drift alone without a performance gate, a meaningful fraction of those retrains are likely responding to covariate/label shift that doesn't affect accuracy, i.e., paying full retraining cost for shifts that were never going to hurt. Adding a performance-corroboration gate (real or estimated) before escalating from "detected" to "retrain" directly reduces unnecessary retrains without reducing detection coverage.
**Follow-up trap:** *"What if leadership wants a single number: how much of that 30% was wasted?"* — instrument retroactively: for each historical retrain, check whether it was preceded by both a drift signal and a performance signal, or drift alone; the fraction triggered by drift alone with no subsequent accuracy improvement in the new model is a defensible estimate of wasted spend.

---

## Red flags that fail you

- Using "drift" as a single undifferentiated concept without naming covariate/label/concept shift separately.
- Claiming any drift necessarily degrades accuracy.
- Proposing KS p-values as an alerting mechanism without mentioning the sample-size problem.
- Treating PSI ≥ 0.25 as automatic justification to retrain, with no performance corroboration.
- Not knowing that PSI bucketing must come from the reference distribution.
- Proposing only univariate checks with no awareness that joint/multivariate drift can hide from them.
- Using a rolling reference window with no discussion of what it structurally cannot detect.
- No cost-awareness of retraining — treating compute as free.

---

## Cheat card

```
TAXONOMY   covariate shift: P(X) changes, P(Y|X) fixed        → may NOT hurt accuracy
           label/prior shift: P(Y) changes, P(X|Y) fixed      → may NOT hurt accuracy
           concept drift: P(Y|X) changes                       → DOES hurt accuracy

PSI        Σ(cur%-ref%)·ln(cur%/ref%), 10 buckets from REFERENCE deciles
           <0.10 none · 0.10-0.25 investigate · ≥0.25 action (banking convention)

KS TEST    statistic = max CDF distance (valid effect size, any n)
           p-value BREAKS at large n — everything "significant" past ~10^4-10^5 samples
           fix: threshold the statistic, not the p-value; or fix sample size

KL / JS    KL asymmetric, undefined at P>0,Q=0 (sparse categoricals break it)
           JS = symmetrized, bounded [0,1] (log2), always finite → prefer for dashboards

WASSERSTEIN   respects actual value distance, not just bucket proportions
           use for ordinal/continuous (age, price, latency); not for unordered categoricals

MULTIVARIATE   train classifier: reference=0, current=1, check AUC
           AUC≈0.5 no joint drift · AUC≥0.7 real multivariate drift
           feature_importances_ → localizes which features drive it

REFERENCE WINDOW   fixed (training-time) = catches all cumulative drift, never blind
           rolling = adapts to seasonality but HIDES slow drift < window length
           → run both

DRIFT PATTERNS   sudden (step, pipeline break) · gradual (slow trend)
           incremental (noisy accumulation) · recurring/seasonal (cyclical)

RETRAIN TRIGGER   scheduled (floor, wastes compute alone)
           + threshold (reactive, retrains on noise alone)
           + performance (real or CBPE-estimated) ← the gate that matters
           mature stacks: schedule as floor, drift gates it, perf corroborates escalation

DRIFT ≠ RETRAIN JUSTIFICATION on its own — corroborate with performance signal first
```

## Sources
- [PSI or not PSI, that is the question — NannyML](https://nannymlnewsletter.substack.com/p/psi-or-not-psi-that-is-the-question) — accessed 2026-08-01
- [Measuring Data Drift with the Population Stability Index (PSI) — Fiddler AI](https://www.fiddler.ai/blog/measuring-data-drift-population-stability-index) — accessed 2026-08-01
- [Customize Data Drift — Evidently AI Documentation](https://docs.evidentlyai.com/metrics/customize_data_drift) — accessed 2026-08-01
- [Python Data Drift Detection Guide 2026 — Python Data Bench](https://pythondatabench.com/article/data-drift-detection-python-evidently-nannyml-alibi-detect-2026) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
