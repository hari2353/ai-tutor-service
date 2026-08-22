# Missing & Corrupt Data: MCAR/MAR/MNAR, Imputation Strategies, When to Drop

> **Track:** T03 Classical ML · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T03-missing-data` · **Tags:** practice,critical

## The 30-second version

The mechanism behind why data is missing determines which fix is valid, not the amount of missingness. MCAR (missing completely at random) means dropping rows or mean-imputing is unbiased, just lossy. MAR (missingness depends on other observed columns) means you need a model-based imputer — KNN or MICE — that uses those columns, or dropping/mean-imputing introduces bias. MNAR (missingness depends on the missing value itself, like high earners not reporting income) means no imputation method fixes it without an explicit model of the missingness process, and the honest move is often to encode "was this missing" as its own feature rather than pretend you recovered the true value. Tree ensembles like XGBoost and LightGBM sidestep most of this by learning an optimal default split direction for missing values directly from training data, which is why in practice a lot of production pipelines skip explicit imputation entirely for tree models and reserve careful imputation for linear/distance-based models that can't handle NaN natively. Corrupt data is a different problem from missing data — silently wrong values disguised as valid ones — and it fails you harder because nothing flags it for review.

## Why this gets asked

Because almost every real dataset has both problems and almost every candidate reaches for `df.fillna(df.mean())` without asking why the values are missing in the first place. The interviewer has debugged a model that looked fine in CV and then systematically underperformed on a subpopulation in production, and traced it to mean-imputing a MAR column — imputing "average income" for everyone with missing income silently erases the exact signal (income correlates with employment status, which correlates with why it's missing) that made the feature useful. They're also testing whether you treat "-999" or "1900-01-01" in a date column as data rather than noticing it's an unlabeled sentinel from an upstream system, because that bug ships to production constantly and looks like real data until someone plots a histogram.

---

## Lineage: past → present → future

**What came before.** Early statistical practice (pre-1970s) mostly used complete-case analysis: drop any row with a missing value and proceed as if the remaining data were the whole story. This is only valid under MCAR, and nobody was checking that assumption. Donald Rubin's 1976 paper *"Inference and Missing Data"* formalized the taxonomy still in use — MCAR, MAR, MNAR — and proved the crucial result that under MAR, a "proper" imputation method conditioning on the observed data produces unbiased estimates, while under MNAR, no observed-data-only method can, because the fix requires modeling exactly the thing you don't have. Single mean/mode imputation became the default applied practice through the 1980s-90s because it was cheap, despite Rubin's own work showing it systematically understates variance — every imputed value is treated by downstream models as if it were observed with certainty, deflating standard errors and overstating confidence.

**Where it stands now.** Multiple Imputation by Chained Equations (MICE, van Buuren & Groothuis-Oudshoorn, 2011) is the accepted statistical answer for MAR data requiring valid inference — impute multiple times, analyze each completed dataset, pool results with Rubin's rules to recover honest variance. In applied ML, the picture has split further: for tree ensembles (XGBoost, LightGBM, CatBoost), the field has largely converged on *not* imputing at all and letting the model's native missing-value handling learn an optimal default direction per split during training, because empirically it performs as well or better than upstream imputation while avoiding the risk of imputation bias entirely. For linear models, neural nets, and distance-based methods that require complete numeric input, KNNImputer and IterativeImputer (scikit-learn's MICE implementation, still gated behind an `enable_iterative_imputer` experimental flag) are the standard tools. The live disagreement is over **missingness-as-signal**: many practitioners now argue the single highest-value move is adding a binary `was_missing` indicator column alongside whatever imputed value you use, since in real operational data (credit applications, medical records, ad conversion logs) the *fact* that a field is missing is often more predictive than any value you could impute for it — this is now common practice but still absent from a lot of textbook treatments that focus only on point-estimate accuracy of the imputed value.

**Where it's heading.** Deep learning-based imputation (denoising autoencoders, GAIN — Generative Adversarial Imputation Nets, diffusion-based tabular imputers) is an active research area and shows gains on benchmark datasets, but is not yet standard production practice outside of a few large tabular-data-heavy shops; treat it as promising, not deployed-by-default. What is more settled and already shipping: automated data-quality monitoring (Great Expectations, whylogs, TFX Data Validation) that flags missingness *rate changes* and corrupt-value patterns (sentinel spikes, encoding shifts) as part of CI/CD for data pipelines, shifting the problem from "clean it in the notebook" to "catch it before it reaches training." The direction of travel is treating missingness as a monitored production signal rather than a one-time cleaning step, and that shift is real, not speculative.

---

## Mental model

```
                     WHY is it missing?  (the only question that matters)
                     ──────────────────────────────────────────────────

  MCAR                        MAR                          MNAR
  missing ⟂ everything        missing depends on           missing depends on
  (sensor randomly dropped    OTHER observed columns       the missing VALUE itself
   a reading)                 (income missing more often   (high earners refuse
                               for self-employed —          to report income)
                               observable from job_type)
     │                            │                              │
     ▼                            ▼                              ▼
  drop rows OR                model-based impute            no imputation method
  mean/median impute          (KNN, MICE) using the          fixes this on its own —
  — unbiased, just            columns missingness            explicitly model the
  loses information            depends on                     missingness mechanism,
                                                                or encode "was_missing"
                                                                as a feature and let the
                                                                model use that signal
```

**The test you actually run:** you cannot directly prove MAR (it requires knowing about the missing values themselves, which you don't have), but you *can* test the MCAR null hypothesis with Little's MCAR test (1988) — if it rejects, you know you're in MAR or MNAR territory and plain drop/mean-impute is biased. In practice most engineers skip the formal test and instead check whether missingness in column A correlates with the observed values of column B (a groupby on `A.isna()` against B's distribution) — if it does, you're not in MCAR, full stop.

---

## How it actually works

### Diagnosing the mechanism

```python
import pandas as pd

# Does missingness in `income` depend on an OBSERVED column? This is the practical
# MAR check most engineers actually run instead of a formal Little's test.
df.groupby(df["income"].isna())["employment_type"].value_counts(normalize=True)
# If self-employed rows are missing income at a much higher rate than salaried rows,
# missingness is NOT independent of an observed variable -> not MCAR, likely MAR
# (or MNAR if it's actually driven by the income value itself, which you can't observe directly)
```

Little's test formalizes this across all variables jointly: a chi-square statistic comparing observed-variable means across missingness patterns; a low p-value rejects MCAR. [Little's Test of Missing Completely at Random — Little (1988)](https://journals.sagepub.com/doi/pdf/10.1177/1536867X1301300407) — accessed 2026-08-01. It cannot distinguish MAR from MNAR — that distinction is fundamentally untestable from observed data alone, because it hinges on the unobserved values.

### Imputation strategies, ranked by assumption strength

| Method | Assumes | Cost | Failure mode |
|---|---|---|---|
| Listwise deletion (drop rows) | MCAR | Free, but loses `n` | Under MAR/MNAR, systematically removes a non-random subpopulation, biasing every downstream estimate |
| Mean/median/mode | MCAR (weak validity even then) | Free | Collapses variance — every imputed value is identical, deflating standard errors and killing the imputed column's correlation with anything else |
| KNN imputation | MAR, local smoothness in feature space | O(n²) naive, or O(n log n) with a tree index | Distorted by the curse of dimensionality — "nearest" neighbors stop being meaningfully close past a few dozen features; sensitive to unscaled features dominating distance |
| MICE / IterativeImputer | MAR | O(iterations × features × per-model fit cost); scikit's docs cite `O(knp³·min(n,p))` in the worst case | Convergence isn't guaranteed on non-monotone missingness patterns with weird conditional distributions; expensive on wide data |
| Model-native (XGBoost/LightGBM default-direction) | Nothing about the mechanism — it just optimizes the direction that minimizes loss given the missingness pattern present in training | Free — built into training | Only works within the model itself; you can't easily extract "the imputed value" for auditing or for a different downstream model |
| Missingness-as-feature (`was_missing` flag) | Nothing — always valid to compute | Free | Doesn't recover the value at all, deliberately; must be combined with *some* value fill (often 0 or median) for the numeric column itself since most models still need a real number |

```python
from sklearn.experimental import enable_iterative_imputer  # noqa — required to unlock IterativeImputer
from sklearn.impute import IterativeImputer, KNNImputer
from sklearn.ensemble import ExtraTreesRegressor

# MICE via scikit-learn: models each column with missing values as a function of the
# others, iterating until estimates stabilize. max_iter default is 10; increase for
# slow-converging patterns and check via imputer.n_iter_ how many it actually took.
mice = IterativeImputer(
    estimator=ExtraTreesRegressor(n_estimators=50, random_state=0),  # non-linear conditional model
    max_iter=10,
    random_state=0,
    n_nearest_features=10,   # cap features used per column to control the O(p^3)-ish blowup on wide data
)
X_imputed = mice.fit_transform(X)

# KNN imputation: fills each missing value from the mean of its k nearest neighbors'
# observed values on that column, using Euclidean distance computed over jointly-observed
# features only (nan_euclidean_distances handles the missing-in-both-rows case).
knn = KNNImputer(n_neighbors=5, weights="uniform")   # sklearn default n_neighbors=5
X_imputed_knn = knn.fit_transform(X)
```
[8.4. Imputation of missing values — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/impute.html) — accessed 2026-08-01

### Model-native missing value handling — the mechanism, precisely

XGBoost and LightGBM both learn, per split, which direction (left or right) missing values should default to, by trying both directions during training and keeping whichever minimizes loss. This is fundamentally different from imputing a fixed value: the "fill" is context-dependent on the split, can differ across different splits on the same feature, and is optimized jointly with the rest of the tree rather than computed upstream and frozen.

```python
import xgboost as xgb
# No imputation needed — XGBoost handles np.nan natively.
# The catch: if a feature has ZERO missing values during training, but a missing value
# shows up at inference time, XGBoost falls back to a fixed default direction (right
# branch) rather than a learned one, because it never saw an example to learn from.
dtrain = xgb.DMatrix(X_train, label=y_train, missing=np.nan)
```
[How XGBoost Handles Missing Values? — proof of concept](https://medium.com/@xwang222/how-xgboost-handles-missing-values-a-proof-of-concept-6aa7afcc8eb9) — accessed 2026-08-01. This is a real production trap: a feature that's always populated in training but starts having missing values in production (an upstream integration silently breaks) gets a fixed, unlearned default rather than the model's best guess — worth explicitly monitoring for.

### Missingness as a feature

```python
for col in ["income", "credit_score", "last_login_days_ago"]:
    df[f"{col}_was_missing"] = df[col].isna().astype(int)
    df[col] = df[col].fillna(df[col].median())   # or any imputation; the flag carries the real signal
```
This is the single highest-leverage move most textbooks underweight: in a credit or churn dataset, `income_was_missing=1` frequently carries more predictive power than any recoverable value of income itself, because *why someone didn't answer* is informative in a way the field's numeric content isn't.

### Corrupt-data taxonomy — a different problem from missingness

Corrupt data is worse than missing data because nothing flags it — the value is present, plausible-looking, and wrong.

| Type | Example | Why it's dangerous |
|---|---|---|
| Wrong dtype | A numeric ID column read as float64, `100234` becomes `100234.0`, later serialized as `1.00234e5` | Downstream joins silently fail; string-matching IDs across systems breaks without an error |
| Encoding mojibake | UTF-8 file read as Latin-1: `café` becomes `cafÃ©` | Text features get shredded into meaningless byte-garbage tokens; a categorical column silently multiplies its cardinality with corrupted duplicates of the same category |
| Sentinel values | `-999` for unknown age, `1900-01-01` or `9999-12-31` for unknown date, `-1` for unknown ID | Treated as real values, these become extreme outliers that wreck means, correlations, and any distance-based method; a "-999" age fed into a linear model with no cap produces a nonsensical coefficient direction |
| Duplicated rows | Same transaction ingested twice from a retry with no idempotency key | Inflates apparent sample size, double-counts rare classes, and in a train/test split can leak a duplicate of a test row into training |
| Silent truncation | A `VARCHAR(50)` column truncating a longer string with no error, or a float64 downcast to float32 losing precision silently | Categories that should match don't (`"International Business Machines Corpor"` vs the full name elsewhere), breaking joins and encoding |

**Detection pattern common to all of these:** they hide in aggregate statistics until you look at the actual value distribution. `df.describe()` showing a minimum of `-999` next to a 25th percentile of `22` is the signature of a sentinel; a categorical column's cardinality being far higher than domain knowledge suggests is the signature of encoding corruption or truncation-induced near-duplicates; an exact duplicate row count above what random chance would produce is the signature of retry-based duplication.

```python
# Cheap sentinel detector: look for suspiciously round or extreme values sitting far
# outside the rest of the distribution
for col in df.select_dtypes("number").columns:
    q1, q99 = df[col].quantile([0.01, 0.99])
    suspects = df[col][(df[col] < q1 - 100 * (q99 - q1)) | (df[col] > q99 + 100 * (q99 - q1))]
    if len(suspects) and suspects.nunique() < 5:      # a handful of REPEATED extreme values, not natural outliers
        print(col, suspects.value_counts())
```

---

## Build it from scratch

Minimal single-pass MICE loop, to show what `IterativeImputer` does under the hood:

```python
import numpy as np
from sklearn.linear_model import BayesianRidge

def mice_from_scratch(X: np.ndarray, max_iter: int = 10, seed: int = 0) -> np.ndarray:
    """Simplified single-chain MICE: impute each missing column as a function of the others,
    iterating until stable. Real MICE also draws from the posterior predictive distribution
    (adds noise) to properly reflect imputation uncertainty; this version only produces
    point estimates, which is the key simplification versus a statistically 'proper' MICE."""
    rng = np.random.default_rng(seed)
    X = X.copy()
    missing_mask = np.isnan(X)
    # initialize with column means so every model below has a complete matrix to fit on
    col_means = np.nanmean(X, axis=0)
    for j in range(X.shape[1]):
        X[missing_mask[:, j], j] = col_means[j]

    for it in range(max_iter):
        for j in range(X.shape[1]):
            if not missing_mask[:, j].any():
                continue
            other_cols = [c for c in range(X.shape[1]) if c != j]
            train_rows = ~missing_mask[:, j]
            model = BayesianRidge()
            model.fit(X[train_rows][:, other_cols], X[train_rows, j])
            X[missing_mask[:, j], j] = model.predict(X[missing_mask[:, j]][:, other_cols])
    return X
```

This converges to roughly the same imputed values as `IterativeImputer(estimator=BayesianRidge())` on well-behaved data — the difference is production MICE also handles multiple imputation chains (run this whole loop several times with different random seeds, pool results with Rubin's rules) to give you an honest uncertainty estimate rather than one point value. Reference lab: `(lab pending)` (build if not present) — includes a test asserting the from-scratch and sklearn versions agree within tolerance on a synthetic MAR dataset.

---

## How it's done in production

| Tool | What it adds over the from-scratch version |
|---|---|
| `sklearn.impute.IterativeImputer` | Convergence tracking (`n_iter_`), `n_nearest_features` to control blowup on wide data, works with any sklearn-compatible estimator per column |
| `sklearn.impute.KNNImputer` | Handles missing-in-both-rows distance computation correctly (`nan_euclidean_distances`), vectorized |
| `missingno` | Visual missingness pattern analysis (matrix, heatmap, dendrogram) — the fastest way to *see* whether missingness clusters by row (suggesting a shared cause) or by column (suggesting a per-field collection issue) |
| Great Expectations / whylogs / TFX Data Validation | Production data-quality gates: assert missingness rate stays within an expected range, flag schema drift, catch sentinel-value spikes before they reach training — this is what turns "we noticed corrupt data in the postmortem" into "the pipeline failed the check and didn't train on garbage" |
| XGBoost/LightGBM native handling | Skips imputation for tree models entirely; the tradeoff table above still applies to anything that needs a complete matrix |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Model performs worse on a subpopulation after shipping | Mean-imputed a MAR column, erasing the exact within-subpopulation signal that made the feature predictive | Model-based imputation (KNN/MICE) using the columns missingness depends on, or a `was_missing` flag |
| Feature's correlation with target collapses after imputation, but the raw (pre-imputation) correlation was strong | Mean/median imputation deflates variance — every imputed value is identical, diluting whatever real signal existed in the observed subset | Model-based imputation, or explicitly keep the `was_missing` flag as a separate feature carrying the signal |
| A column's mean shifts sharply after a schema migration, model degrades silently | Upstream sentinel convention changed (e.g. `-999` replaced with `null`, or vice versa) without notifying the ML pipeline | Data contract / schema validation gate on ingestion; alert on distributional shift in min/max, not just missingness rate |
| Train/test split shows suspiciously good test performance | Duplicated rows from an ingestion retry placed some duplicates in train and their twins in test | Deduplicate before splitting; dedupe key should be a true business key, not just exact row equality (near-duplicates from truncation won't match exactly) |
| A tree model's predictions flip when a previously-always-populated feature starts having nulls in production | XGBoost/LightGBM never learned a direction for that feature's missing values (none existed in training), so it falls back to a fixed default direction that may be wrong for this data | Monitor per-feature missingness rate drift in production; retrain or explicitly impute once a feature that was complete in training starts showing nulls |
| Encoding-mojibake categorical column has 3x the expected cardinality | File read with the wrong encoding, corrupting non-ASCII characters into garbage byte sequences that don't match the correctly-encoded versions of the same category | Detect via unexpectedly high cardinality vs domain knowledge; fix at ingestion with `chardet`/`charset-normalizer` detection, not downstream |

---

## Tradeoffs & when NOT to use it

- **Don't mean/median-impute a column you suspect is MAR or MNAR without also adding a `was_missing` flag.** You are actively deleting the most predictive part of that feature otherwise.
- **Don't run KNNImputer on data with more than a few dozen relevant dimensions without dimensionality reduction first.** Distance-based imputation degrades exactly the way distance-based classification does under the curse of dimensionality — "nearest" neighbors in 200-dimensional space are not meaningfully close.
- **Don't run MICE/IterativeImputer as a blocking step in a low-latency online pipeline.** It's an offline, batch, training-time tool. For serving, either the model handles missing values natively (trees), or you use a frozen, precomputed imputation rule (a stored median, not a live model refit).
- **Don't impute at all before checking if the mechanism is MNAR.** If income is missing because high earners refuse to report it, no amount of clever imputation recovers the true value — you are, at best, imputing the *conditional mean given what you can observe*, which for MNAR data is a biased estimate of the true missing value by construction. The honest fix is often a `was_missing` flag plus explicit acknowledgment in any deployed model's documentation that this feature is unreliable for that subpopulation.
- **Don't trust `feature_importances_` or correlation coefficients computed after mean-imputation as if they reflect the true underlying relationship.** They reflect the relationship *after* you've deliberately flattened variance in the imputed rows.
- **When NOT to bother with sophisticated imputation:** if missingness is under ~1-2% and genuinely MCAR (validated, not assumed), the difference between listwise deletion, mean imputation, and MICE is usually noise-level on the final model metric, and the engineering cost of MICE in a production pipeline isn't justified. Spend the effort on the columns where missingness is high or clearly non-random instead.

---

## Interview questions

### Q1 — Define MCAR, MAR, and MNAR, each with a concrete example.
**Testing:** whether you actually understand the distinction or just recite the acronyms.
**Answer:** MCAR: missingness independent of everything, observed or not — a sensor randomly drops readings due to a transient hardware glitch unrelated to the true value or anything else measured. MAR: missingness depends on other *observed* variables — income is missing more often for self-employed respondents, and employment type is recorded, so you can condition on it. MNAR: missingness depends on the missing value itself — high earners disproportionately refuse to report income, so the very fact of non-disclosure is entangled with the unobserved value.
**Follow-up trap:** *"Can you test which one you're in?"* — you can test the MCAR null hypothesis (Little's test, or the practical proxy of checking whether missingness correlates with observed columns); rejecting it tells you you're in MAR-or-MNAR, but distinguishing MAR from MNAR is fundamentally untestable from the observed data alone, because it hinges on values you don't have.

### Q2 — Why is mean imputation dangerous even under MCAR, where it's technically "unbiased"?
**Answer:** It's unbiased for the mean of the column itself, but it collapses variance — every imputed value is identical, so the imputed rows contribute zero to any variance-based estimate (correlation, feature importance, regression coefficient) even if the true missing values would have varied like everything else. Under MCAR this dilutes signal proportionally to the missingness rate; under MAR or MNAR it's outright biased on top of that.
**Follow-up trap:** *"How would you detect this happened after the fact?"* — compare the imputed column's variance to the observed-only variance; a sharp drop post-imputation, especially at moderate-to-high missingness rates, is the signature.

### Q3 — Walk through what happens if you mean-impute a MAR column in a fraud model.
**Answer:** Say transaction amount is missing more often for a specific payment method that's disproportionately used in fraud. Mean-imputing amount erases exactly the signal that made "unusually large/small amount for this payment method" predictive for that subpopulation, because every imputed row now looks like the population average regardless of the method-specific pattern. The model's performance degrades specifically on that payment method's fraud cases, which may not show up in an aggregate CV metric if that subpopulation is a small share of the data.
**Follow-up trap:** *"Your aggregate AUC didn't move. Are you safe?"* — no. Aggregate metrics hide subpopulation degradation exactly like this; slice metrics by the column that predicts missingness (here, payment method) before declaring the fix safe.

### Q4 — How does XGBoost handle missing values, and where does that break?
**Answer:** During training, at each split XGBoost tries sending missing values both left and right and keeps whichever direction minimizes the loss — a learned, per-split default direction, not a fixed fill value. It breaks when a feature that was always populated during training starts having missing values at inference time: since XGBoost never saw a training example to learn a direction for that feature's missingness, it falls back to a fixed default (documented as the right branch), which may be arbitrarily wrong for the actual production distribution.
**Follow-up trap:** *"How would you catch this in production before it silently degrades predictions?"* — monitor per-feature missingness rate as a production data-quality metric, not just overall row completeness; a feature going from 0% to 5% missing between training and serving is a signal to retrain or add explicit imputation, not something you'd notice from aggregate model metrics alone.

### Q5 — KNNImputer vs IterativeImputer (MICE) — when do you pick each?
**Answer:** KNNImputer is simpler, faster on moderate-size data, and works well when the data has meaningful local structure (similar rows genuinely have similar missing-value fills) — but it degrades under the curse of dimensionality and is sensitive to unscaled features dominating the distance metric. MICE models each column with missing values as a function of all other columns using a real regression/classification model per column, iterating to convergence — better captures complex conditional relationships and is the standard when you need statistically valid inference (multiple imputation with pooled variance), at higher computational cost, roughly `O(iterations × features × per-model cost)`.
**Follow-up trap:** *"Does either of these produce valid standard errors for downstream inference?"* — not as commonly used (single-pass point-estimate imputation, which is what most ML pipelines do). Valid inference requires *multiple* imputation — running the MICE process several times with different random draws, fitting the downstream model on each completed dataset, and pooling estimates and variances via Rubin's rules. A single IterativeImputer call in a typical ML pipeline gives you one point estimate per missing value with no built-in uncertainty quantification.

### Q6 — What's the single highest-leverage feature engineering move for a MAR/MNAR column that most people skip?
**Answer:** A binary `was_missing` indicator alongside whatever value-fill you use. In real operational data, the fact that a field is missing is frequently more predictive than any value you could impute for it, precisely because missingness is often driven by something meaningful (a customer who abandoned a form, a self-employed applicant, a system that only logs certain event types).
**Follow-up trap:** *"Does this apply if the column is MCAR?"* — less so, by definition — if missingness is truly independent of everything, the `was_missing` flag carries no signal and is just noise for the model to potentially overfit on with enough capacity. It's the MAR/MNAR case where this move earns its keep, which is another reason diagnosing the mechanism first matters.

### Q7 — Someone hands you a dataset where `age` has a minimum of -999 and a 25th percentile of 24. What do you do?
**Testing:** whether you catch sentinel values by looking at the actual distribution rather than trusting `dtype` and `isna()` counts.
**Answer:** -999 is almost certainly an unlabeled sentinel for "unknown," not a real age. `df.isna().sum()` won't catch this because the value isn't null, it's a disguised missing value. Recode it to `NaN` explicitly (`df["age"].replace(-999, np.nan)`), then treat it as genuinely missing data and go through the MCAR/MAR/MNAR diagnosis, rather than letting -999 sit in the column, wrecking the mean, any distance-based method, and any model that doesn't explicitly special-case it.
**Follow-up trap:** *"How do you find sentinel values you don't already know to look for?"* — plot the distribution (`df[col].describe()`, a histogram) for every numeric column before modeling, specifically looking for suspicious round numbers or values sitting far outside the rest of the mass with unnaturally high repeat counts — a real outlier is rarely the exact same value repeated thousands of times; a sentinel is.

### Q8 — Explain silent truncation as a corrupt-data category and how it manifests in a real pipeline.
**Answer:** A field gets cut off at a fixed length limit (e.g. a legacy `VARCHAR(50)` column, or a fixed-width export format) without raising an error — the truncated value looks like valid data. It manifests as categorical values that should be identical failing to match across systems (`"International Business Machines Corpor"` from the truncated system vs `"International Business Machines Corporation"` from the source), silently inflating category cardinality and breaking joins or one-hot encodings that expect a consistent vocabulary.
**Follow-up trap:** *"How do you distinguish this from a genuine new category showing up in production (train-serve skew)?"* — check whether the "new" category is a prefix of an existing one in the training vocabulary; a systematic pattern of near-duplicate prefixes strongly suggests truncation rather than a genuinely novel value, whereas a genuinely new category won't cluster this way.

### Q9 — Your train/test split shows an unrealistically small generalization gap. You suspect duplicated rows. How do you check, and why can't you just use `df.duplicated()`?
**Answer:** `df.duplicated()` catches exact row equality, which misses near-duplicates from silent truncation, floating-point precision differences, or partial re-ingestion with a slightly different timestamp. Check for a true business key (e.g. transaction ID, or a hash of the immutable fields) rather than full-row equality, and specifically check for rows in the test set that are near-duplicates (by that key or by cosine similarity on features) of rows in the training set.
**Follow-up trap:** *"You find and remove the duplicates. Test performance drops sharply. What do you do?"* — that drop is the real, honest number; the previous score was inflated by test-set leakage. Report the corrected number and treat the earlier result as invalid rather than trying to recover the inflated metric some other way.

### Q10 — Design the missing-data handling for a production credit scoring pipeline with both a gradient boosted tree and a logistic regression baseline running in parallel.
**Testing:** synthesis — whether you'll apply one blanket policy or reason per model.
**Answer:** For the gradient boosted tree, no explicit imputation — let native missing-value handling learn default directions, but add data-quality monitoring on per-feature missingness rate so a newly-missing feature at inference doesn't silently hit an unlearned fallback. For the logistic regression baseline, which needs complete numeric input, fit MICE (or KNN for speed) on the training set only, freeze the fitted imputer, and apply it identically at serving time — never refit imputation live on serving data. For any column where missingness correlates with an observed field (checked via the groupby test), add a `was_missing` flag to both models' feature sets, since trees benefit from it too even though they handle NaN natively — the flag makes the "why missing" signal explicit rather than implicit in split-direction learning.
**Follow-up trap:** *"A regulator asks why you imputed rather than dropped rows with missing income."* — dropping is only defensible under MCAR, and income missingness in a credit context is very plausibly MAR (correlated with employment type) or MNAR (high earners under-reporting) — dropping those rows would systematically bias the training population away from exactly the applicants the model needs to score correctly, which is a fair-lending as well as a statistical concern.

### Q11 — When would you deliberately choose to drop rows instead of imputing?
**Answer:** When missingness is low (a rough rule of thumb is under 5%, though it depends on how much data you have to spare) and plausibly MCAR — verified, not assumed — dropping is simpler, avoids any imputation bias risk entirely, and the information loss is negligible. Also appropriate when the missing column itself isn't going to be used as a model feature (you're dropping rows missing a *label*, which is a different and usually mandatory case — you generally can't impute a missing target).
**Follow-up trap:** *"What if 5% missing is concentrated in your minority class?"* — then the *rate* is misleading; check missingness by class/subgroup, not just overall. 5% overall missingness that's actually 40% missingness within the minority class you care most about is a MAR-conditioned-on-label situation and dropping would gut your already-scarce positive examples.

---

## Red flags that fail you

- Reaching for `fillna(mean())` without asking why the value is missing.
- Not knowing that mean imputation deflates variance, not just "loses some information."
- Treating -999, 1900-01-01, or similar as real data because `isna()` returned 0.
- Claiming you can test whether data is MAR (it's untestable from observed data alone; only the MCAR null is testable).
- Running KNNImputer on hundreds of unscaled features without acknowledging the curse-of-dimensionality risk.
- Not knowing that XGBoost/LightGBM handle missing values natively.
- Treating corrupt data and missing data as the same problem with the same fix.
- No answer for what happens when a feature that's always complete in training starts showing nulls in production.

---

## Cheat card

```
MECHANISM (Rubin, 1976) determines the valid fix, not the missingness RATE
  MCAR  missing independent of everything      -> drop or mean-impute is unbiased (lossy)
  MAR   missing depends on OBSERVED columns    -> model-based impute (KNN/MICE) using those columns
  MNAR  missing depends on the MISSING value   -> no impute fixes it; was_missing flag + honest caveat

TESTABILITY   only MCAR is testable (Little's test, 1988, or groupby(isna()) vs observed cols)
              MAR vs MNAR is UNTESTABLE from observed data alone

IMPUTATION
  mean/median/mode     free, COLLAPSES VARIANCE -- every fill is identical, dilutes signal
  KNNImputer           sklearn default n_neighbors=5; degrades under curse of dimensionality
  IterativeImputer     = MICE; sklearn: enable_iterative_imputer flag required, max_iter default 10
                        worst case O(k*n*p^3 * min(n,p)); check imputer.n_iter_ for convergence
  model-native (XGB/LGBM)  learns default SPLIT DIRECTION per node from training data, not a fill value
                        BREAKS if a feature has 0% missing in train but nonzero at inference (unlearned fallback)

WAS_MISSING FLAG      highest-leverage move most people skip; the FACT of missingness is often
                      more predictive than any value you could impute (MAR/MNAR only, not MCAR)

CORRUPT DATA (≠ missing -- present, plausible-looking, WRONG)
  wrong dtype          numeric ID -> float64 -> scientific notation -> join breaks silently
  mojibake             wrong encoding on read; "café" -> "cafÃ©"; inflates categorical cardinality
  sentinel values       -999, 1900-01-01, 9999-12-31, -1 -- wreck means/distances if untreated
  duplicated rows       retry w/o idempotency key -> inflated n, possible train/test leak
  silent truncation     VARCHAR(50) cutoff, float64->float32 -- near-duplicate categories, broken joins
  DETECTION: plot the distribution. Repeated extreme values = sentinel. Cardinality > domain
             knowledge = mojibake/truncation. df.duplicated() misses near-dupes -- use a business key.

WHEN NOT TO BOTHER    missingness <~2%, verified MCAR -> drop/mean-impute is fine, MICE is overkill
WHEN NOT TO DROP       MAR/MNAR missingness correlated with the label/subgroup you care about
```

## Sources

- [Little's Test of Missing Completely at Random — SAGE](https://journals.sagepub.com/doi/pdf/10.1177/1536867X1301300407) — accessed 2026-08-01
- [8.4. Imputation of missing values — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/impute.html) — accessed 2026-08-01
- [IterativeImputer — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.impute.IterativeImputer.html) — accessed 2026-08-01
- [KNNImputer — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.impute.KNNImputer.html) — accessed 2026-08-01
- [How XGBoost Handles Missing Values? A Proof of Concept](https://medium.com/@xwang222/how-xgboost-handles-missing-values-a-proof-of-concept-6aa7afcc8eb9) — accessed 2026-08-01
- [How do XGBoost, LightGBM, and CatBoost Handle Missing Features?](https://coder-wang-uspsa.medium.com/how-do-xgboost-lightgbm-and-catboost-handle-missing-features-e541da94d528) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
