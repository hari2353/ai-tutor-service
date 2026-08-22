# Feature Selection: Filter, Wrapper, Embedded, SHAP-Based, Why More Features Hurt

> **Track:** T03 Classical ML · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T03-feature-selection` · **Tags:** practice,critical

## The 30-second version

Feature selection is bias-variance management applied to the input space, not the model. Filter methods (correlation, chi2, mutual information) score each feature against the target independent of any model, are cheap, and miss interactions. Wrapper methods (RFE, forward/backward selection) use a real model's performance as the scoring function, are expensive, and overfit to the CV folds if you're not careful. Embedded methods (L1 regularization, tree `feature_importances_`) select as a side effect of training, which is cheap and interaction-aware but inherits whatever bias the model has — and tree importance is structurally biased toward high-cardinality and continuous features because they offer more candidate split points. Permutation importance and SHAP fix the direction of the bias question by measuring impact on held-out predictions rather than training-time split gain, at the cost of compute. The one rule that overrides all of this: any selection step that looks at the target must live inside the cross-validation fold, or you leak label information into features the model then gets validated on, and your CV score becomes fiction.

## Why this gets asked

Because "how do you pick features" sounds like a beginner question and the answer that gets asked back separates people who've shipped a model from people who've only fit one in a notebook. The interviewer has watched a model post a beautiful 0.95 AUC in validation and then fail in production, traced it back three weeks later, and found that feature selection ran on the full dataset *before* the train/test split. They are also checking whether you understand that `feature_importances_` from a random forest is not ground truth about the world — it's an artifact of how CART trees pick splits, and it lies in a specific, well-documented direction.

---

## Lineage: past → present → future

**What came before.** Early applied statistics treated variable selection as stepwise regression: forward selection, backward elimination, and their combination, all wrapped around p-value or AIC/BIC thresholds on a linear model (Efroymson, 1960). It worked when you had 10-30 candidate predictors and a linear model that could tolerate collinearity. It broke down as feature counts grew past what stepwise search could explore in reasonable time (the search space of a forward-selection wrapper over `p` features is exponential in the worst case) and as nonlinear models made "the coefficient's p-value" meaningless as a selection criterion. The next wave was tree-based importance: Breiman's Random Forest paper (2001) came with `Gini importance` for free as a byproduct of training, and it looked like it solved variable selection painlessly — until Strobl et al. (2007), *"Bias in random forest variable importance measures,"* showed rigorously that Gini/MDI importance is inflated for features with more distinct values or wider numeric ranges, because more candidate split points mean more chances to find a locally good (possibly spurious) split.

**Where it stands now.** Consensus splits selection into what it's for. For understanding *what the model actually uses*, permutation importance (shuffle a column, measure the drop in held-out score) and SHAP (Lundberg & Lee, 2017, game-theoretic attribution satisfying local accuracy and consistency) are the accepted answers, because both operate on held-out predictions rather than training-time split statistics, sidestepping the Strobl bias — though SHAP TreeExplainer inherits a milder version of the same high-cardinality bias when the underlying tree structure itself is biased, which is a live nuance most practitioners don't know. For actually *reducing* the feature set for a production model, embedded methods (L1/Lasso, tree importance with a CV-validated threshold) dominate industry practice because wrapper methods like RFE do not scale past a few hundred features when each step retrains a model — RFE on 500 features with 5-fold CV and a gradient boosted tree can mean thousands of tree fits. The live disagreement is whether feature selection should exist at all when using regularized/tree ensembles that are natively robust to irrelevant features — many practitioners now argue that for XGBoost/LightGBM with proper `min_child_weight` and L1/L2 regularization, explicit feature selection buys little beyond faster inference and interpretability, and the real value has shifted from "improve accuracy" to "reduce serving cost and latency" and "make the model auditable."

**Where it's heading.** SHAP-based selection is becoming the default for regulated domains (credit, healthcare) because it doubles as required model documentation — one artifact serves both selection and compliance, and this is already deployed, not speculative. More speculative: automated feature selection as part of AutoML/AutoFE pipelines (using SHAP or permutation importance inside a Bayesian optimization loop over feature subsets) is moving from research to some managed platforms (Vertex AI, SageMaker Autopilot), but hand-tuned selection by a practitioner who understands the target domain still outperforms most automated pipelines on messy real-world data as of this writing — treat "AutoML replaces manual feature selection" as aspirational, not settled.

---

## Mental model

```
                          FEATURE SELECTION DECISION TREE
                          ────────────────────────────────

  Do you need to select the target's information       Filter (fast, model-free)
  content BEFORE touching any model?          ────────▶ correlation / chi2 / mutual info
        │
        │ no, I have a model family already
        ▼
  Can you afford O(p) to O(p²) retrains?
        │                              │
       yes                             no
        │                              │
        ▼                              ▼
    Wrapper (RFE / RFECV)        Embedded (L1, tree importance)
    best accuracy, slowest       trains once, selection is a byproduct
        │                              │
        └──────────────┬───────────────┘
                        ▼
        Want to know WHY, not just WHICH, post-hoc,
        on a model you're not retraining?
                        │
                        ▼
        Permutation importance (any model, held-out data)
        SHAP (any model, per-prediction + global, game-theoretic)

  EVERY PATH: if any step looks at y, it goes INSIDE the CV fold.
```

The four families aren't competing answers to the same question — they answer different questions. Filter asks "does this feature correlate with the target at all." Wrapper asks "does removing this feature hurt *this specific model's* held-out performance." Embedded asks "did the model, while fitting for accuracy, end up ignoring this feature." SHAP/permutation ask "how much does *this exact trained model* actually rely on this feature for its predictions." Picking the wrong question for your goal is the actual mistake, not picking the wrong algorithm.

---

## How it actually works

### Filter methods

Score each feature against the target independently, rank, cut a threshold or take top-k. No model involved.

| Method | Feature type | Target type | Captures |
|---|---|---|---|
| Pearson correlation | continuous | continuous | linear relationship only |
| Spearman correlation | continuous/ordinal | continuous/ordinal | monotonic, not just linear |
| Chi-squared (`chi2`) | categorical/non-negative | categorical | statistical independence |
| ANOVA F-test (`f_classif`) | continuous | categorical | linear separability between classes |
| Mutual information (`mutual_info_classif`/`_regression`) | any | any | any statistical dependence, linear or not |

```python
from sklearn.feature_selection import mutual_info_classif, SelectKBest

# mutual_info_classif defaults: discrete_features='auto', n_neighbors=3, random_state=None
# n_neighbors=3 controls the k-NN density estimator used for continuous features —
# small k means noisier, higher-variance MI estimates on small samples
mi_scores = mutual_info_classif(X_train, y_train, random_state=0)
selector = SelectKBest(score_func=lambda X, y: mutual_info_classif(X, y, random_state=0), k=20)
X_selected = selector.fit_transform(X_train, y_train)
```
[mutual_info_classif — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.mutual_info_classif.html) — accessed 2026-08-01

**Filter's blind spot, concretely.** Two features, `X1` and `X2`, each individually uncorrelated with `y` (Pearson r ≈ 0.02), but `y = X1 XOR X2`. Filter methods discard both. A tree model splitting on both recovers the signal perfectly. This is the textbook argument for wrapper/embedded methods when interactions matter, and it is a real trap in interviews: someone will ask "would filter methods catch an XOR relationship" and the answer is no, categorically, because filter methods are marginal by construction.

### Wrapper methods — RFE

RFE fits the full model, ranks features by the model's own importance/coefficient attribute, drops the worst, and repeats until the target count is reached.

```python
from sklearn.feature_selection import RFECV
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

# RFECV picks the number of features automatically via CV, rather than you guessing k
rfecv = RFECV(
    estimator=RandomForestClassifier(n_estimators=200, random_state=0),
    step=1,                      # remove 1 feature per iteration; use step=0.1 (10%) for speed on wide data
    cv=StratifiedKFold(5),
    scoring="roc_auc",
    min_features_to_select=5,
    n_jobs=-1,
)
rfecv.fit(X_train, y_train)
```
[RFECV — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.RFECV.html) — accessed 2026-08-01

**Cost, concretely.** With `p=200` features, `step=1`, and 5-fold CV, RFECV trains roughly `200 × 5 = 1000` models before it converges. Swap in a gradient boosted tree with 500 trees each and this is not a "run it and wait" operation, it's an overnight job. `step=0.1` (drop 10% of remaining features per round) reduces this to `~log-ish` iterations but coarsens the ranking.

### Embedded methods

**L1 (Lasso) regularization** drives coefficients of uninformative features exactly to zero as a side effect of the optimization — the L1 penalty's non-differentiable corner at zero is what produces exact sparsity, unlike L2 which shrinks toward but never reaches zero.

```python
from sklearn.linear_model import LogisticRegression

# C is inverse regularization strength; smaller C = stronger penalty = fewer surviving features
clf = LogisticRegression(penalty="l1", solver="liblinear", C=0.1)
clf.fit(X_train_scaled, y_train)   # L1 requires scaled features — penalty is scale-dependent
selected = X_train.columns[clf.coef_[0] != 0]
```

**Tree `feature_importances_`** (Gini/MDI importance) is the default most people reach for and the one with the documented bias.

**Why it's biased toward high-cardinality features, mechanically.** At each split, CART evaluates every possible threshold on every feature and picks the one giving the largest impurity decrease. A continuous feature with 10,000 unique values offers ~10,000 candidate thresholds; a binary feature offers exactly 1. Pure noise, given enough candidate thresholds, will eventually produce a locally good-looking split by chance — this is a multiple-comparisons problem hiding inside tree construction. Strobl et al. (2007) demonstrated this with simulated data: a completely random, uninformative feature with 20 categories was ranked as *more important* than a genuinely predictive binary feature, purely from having more candidate splits. The practical consequence: an ID-like or high-cardinality categorical column (user ID hash, zip+4, a poorly-binned continuous feature) can dominate a `feature_importances_` ranking while contributing nothing predictive out-of-sample.

**Fix:** use permutation importance or SHAP instead of Gini importance when cardinality varies across features, or use `max_features` and require importance to be validated against a held-out set, never the training set.

### Permutation importance and SHAP

```python
from sklearn.inspection import permutation_importance

# Shuffle one column at a time on HELD-OUT data, measure the drop in score.
# This is model-agnostic and immune to the Gini-importance cardinality bias,
# because it's driven by predictive contribution, not split-count opportunity.
result = permutation_importance(
    model, X_test, y_test, n_repeats=10, random_state=0, scoring="roc_auc", n_jobs=-1
)
```
Caveat documented by sklearn itself: permutation importance is unreliable under correlated features — shuffling one of two highly correlated columns barely hurts the score because the model still has the other one, so both get scored as "unimportant" even though the pair together matters. [Permutation feature importance — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/permutation_importance.html) — accessed 2026-08-01

```python
import shap
explainer = shap.TreeExplainer(model)          # exact, polynomial-time for tree ensembles
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test)         # global ranking by mean |SHAP value|
```
SHAP satisfies **local accuracy** (attributions sum to the difference between the prediction and the baseline) and **consistency** (if a model changes so a feature's marginal contribution increases, its attribution can't decrease) — Gini importance satisfies neither, which is the formal reason SHAP is preferred for anything audited. `TreeExplainer` computes exact Shapley values for tree ensembles in `O(TLD²)` (trees × leaves × depth²) rather than the naive exponential-in-features cost of general Shapley computation. [Are SHAP Values Biased Towards High-Entropy Features? — Springer](https://link.springer.com/chapter/10.1007/978-3-031-23618-1_28) — accessed 2026-08-01, showing SHAP inherits a milder version of the same high-cardinality bias when the underlying trees are biased — SHAP fixes the *axioms*, not the *input* it's explaining.

### The curse of dimensionality, with numbers

Distance-based methods (kNN, clustering, LOF) degrade as dimensionality grows because in high dimensions, distances concentrate: the ratio of the farthest point's distance to the nearest point's distance tends toward 1. Concretely, to keep the same *density* of training points per unit volume as you had in 1D with `N` samples, you need `N^d` samples in `d` dimensions — 100 samples covering a 1D interval need `100^10 = 10^20` samples to cover a 10-dimensional space at equivalent density. That number is why "just add more features, the model will figure out what's useless" is not free: past some point, added dimensions add more sparsity than signal, and models that rely on distance or density (kNN, LOF, kernel methods) degrade measurably while tree ensembles degrade more gracefully but still pay in variance and training time.

### Selection inside the fold — the leak that inflates every number

```python
# WRONG — feature selection sees the test set's target before the split is "final"
selector = SelectKBest(f_classif, k=20).fit(X, y)          # fit on ALL data, including test
X_sel = selector.transform(X)
X_train, X_test, y_train, y_test = train_test_split(X_sel, y)
model.fit(X_train, y_train)
# test score is now optimistic: the 20 "best" features were chosen partly by looking at
# the labels of rows that are now sitting in X_test.

# RIGHT — selection is part of the pipeline, refit per fold
from sklearn.pipeline import Pipeline
pipe = Pipeline([
    ("select", SelectKBest(f_classif, k=20)),
    ("model", RandomForestClassifier(random_state=0)),
])
cross_val_score(pipe, X, y, cv=5)   # selection refit fresh inside each of the 5 folds
```
The magnitude of the leak scales with how many candidate features you started with relative to sample size — selecting the "best" 20 of 20 candidates leaks almost nothing; selecting the best 20 of 10,000 candidates on 500 rows can produce a CV AUC north of 0.85 on **pure noise**, because with 10,000 random features and only 500 labels, some noise features will correlate with the label by chance alone, and picking the top-scoring ones systematically harvests that chance correlation.

---

## Build it from scratch

Minimal permutation importance, to show what the sklearn function is actually doing:

```python
import numpy as np
from sklearn.metrics import roc_auc_score

def permutation_importance_from_scratch(model, X_test, y_test, n_repeats=10, seed=0):
    rng = np.random.default_rng(seed)
    baseline = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    importances = {}
    for col in X_test.columns:
        drops = []
        for _ in range(n_repeats):
            X_shuffled = X_test.copy()
            X_shuffled[col] = rng.permutation(X_shuffled[col].values)   # break the col-target link only
            shuffled_score = roc_auc_score(y_test, model.predict_proba(X_shuffled)[:, 1])
            drops.append(baseline - shuffled_score)
        importances[col] = (np.mean(drops), np.std(drops))
    return importances   # (mean_drop, std_drop) per feature; std tells you if n_repeats was enough
```

This is a complete, runnable implementation — the only thing sklearn's version adds is parallelism and multi-metric support. Running it makes the correlated-feature caveat concrete: duplicate a column in `X_test`, rerun, and watch both copies' importance roughly halve versus the single-column version, even though together they still carry all the original signal.

Reference lab for the full filter → wrapper → embedded → SHAP pipeline with a leakage test: `labs/py/09-feature-selection/` (build if not present).

---

## How it's done in production

| Stage | Tool | What it adds |
|---|---|---|
| Filter | `sklearn.feature_selection` (`chi2`, `f_classif`, `mutual_info_*`) | Cheap first pass to cut obviously useless features before expensive steps |
| Wrapper | `RFECV`, `mlxtend.SequentialFeatureSelector` | Model-aware ranking; only viable on hundreds, not tens of thousands, of features |
| Embedded | XGBoost/LightGBM native `feature_importances_` (gain-based, not just split-count) + L1 on linear baselines | Free byproduct of training you're already doing |
| Explanation/audit | `shap.TreeExplainer`, `shap.LinearExplainer` | Per-prediction and global attribution; doubles as compliance documentation in regulated domains |
| Pipeline glue | `sklearn.pipeline.Pipeline` + `cross_val_score`/`cross_validate` | The only reliable guard against selection leakage |

**Gain vs split-count vs cover, a detail that trips people up:** XGBoost's `feature_importances_` defaults to `"gain"` (average loss reduction from splits on that feature), while `"weight"` counts how many times a feature was split on, and `"cover"` measures the average number of samples affected. `"weight"` inherits the cardinality bias hardest since it's literally a split count; `"gain"` is somewhat more robust but not immune — a spurious split on a high-cardinality noise feature that happens to reduce loss slightly still counts toward gain.

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| CV AUC 0.90, production AUC 0.65 | Feature selection ran outside the CV loop / on the full dataset before splitting | Move selection into the `Pipeline`, refit per fold |
| A user-ID-like column tops the importance ranking | Gini/MDI bias toward high-cardinality features (Strobl et al.) | Switch to permutation importance or SHAP; drop obvious identifier columns before ranking |
| Two nearly-identical features both rank "unimportant" | Permutation/SHAP importance splits credit across correlated features | Cluster correlated features first (e.g. hierarchical clustering on `1 - |corr|`) and select a representative per cluster |
| RFECV takes 14 hours on a nightly retrain job | `step=1` with a heavy estimator and hundreds of features | `step=0.1`, or switch to embedded selection with a CV-validated threshold |
| Model trained on 3,000 features degrades in prod after a schema change | One upstream column changed dtype/encoding silently, breaking a filter threshold tuned on the old distribution | Pin the selected feature list explicitly at training time; validate incoming schema before inference, don't recompute importance live |
| New categorical column with a huge cardinality tanks inference latency | Embedded selection let it through because gain looked good on training data | Cap or bucket cardinality before selection, not after |

---

## Tradeoffs & when NOT to use it

- **Don't run wrapper methods (RFE) on more than a few hundred features with an expensive estimator.** The retrain cost is `O(p)` to `O(p²)` model fits; on 50,000 features it simply doesn't finish in a useful timeframe. Use filter or embedded first to cut to a few hundred candidates, then wrap.
- **Don't trust Gini/MDI `feature_importances_` when feature cardinality varies widely.** This is the single most common misdiagnosis in practice — treat it as a hypothesis to verify with permutation importance or SHAP, not a conclusion.
- **Don't do feature selection at all if you're using a well-regularized gradient boosted tree or deep net and inference cost/interpretability don't matter.** XGBoost with proper `reg_alpha`/`reg_lambda` and `min_child_weight` is already fairly robust to irrelevant features; explicit selection buys latency and auditability, not necessarily accuracy, and can occasionally *hurt* accuracy by removing a feature that only mattered in combination with another (the XOR case).
- **Don't use filter methods as the final answer when you suspect interactions.** They are marginal by construction and will silently discard XOR-like signal.
- **Don't select on the full dataset before splitting.** This is the leak, not a stylistic preference — treat it as a correctness bug, not a hygiene suggestion.
- **When NOT to select at all:** in an experimentation-stage model where the feature set is still churning weekly and interpretability is not yet required — locking in a selected feature set too early can hide the fact that a not-yet-selected feature would have mattered once the real distribution shift shows up.

---

## Interview questions

### Q1 — What's the difference between filter, wrapper, and embedded feature selection?
**Testing:** baseline vocabulary and whether you know the cost/accuracy tradeoff, not just the definitions.
**Answer:** Filter scores each feature against the target independent of any model (correlation, chi2, mutual information) — cheap, fast, misses interactions. Wrapper uses a model's actual held-out performance as the scoring function (RFE) — most accurate for that specific model, most expensive because it retrains repeatedly. Embedded selects as a byproduct of training a single model (L1 coefficients going to zero, tree importances) — cheap like filter, interaction-aware like wrapper, but inherits the model's own biases.
**Follow-up trap:** *"Which would you use with 50,000 features and one hour of compute?"* — filter first to cut to a few hundred, then embedded on what remains. Wrapper at 50,000 features doesn't finish.

### Q2 — Why is tree-based `feature_importances_` biased?
**Testing:** whether you actually understand CART mechanics or just memorized "trees can be biased."
**Answer:** Because at every split, CART evaluates every candidate threshold on every feature and keeps whichever gives the largest impurity reduction. A high-cardinality or continuous feature offers vastly more candidate thresholds than a binary one, so purely by chance it's more likely to produce a locally good-looking split — this is a multiple-comparisons effect baked into split search. Strobl et al. (2007) showed a purely random 20-category feature outranking a genuinely predictive binary feature in simulation.
**Follow-up trap:** *"Does SHAP fix this?"* — it fixes the *axioms* (local accuracy, consistency) but not the underlying tree structure it's explaining; recent work shows SHAP inherits a milder version of the same bias when the trees themselves are biased. Say both parts or you've only answered half.

### Q3 — Walk me through the CV leakage bug in feature selection and how it inflates scores.
**Testing:** the single most common real bug in this space.
**Answer:** If selection (e.g. `SelectKBest(k=20)`) is fit on the full dataset before the train/test split, the chosen features were picked partly using label information from rows now sitting in the "held-out" set. The fix is to put selection inside a `Pipeline` and let `cross_val_score` refit it fresh per fold, so each fold's selection only ever sees that fold's training labels.
**Follow-up trap:** *"How bad can it get, roughly?"* — magnitude scales with (candidate features) / (sample size). Selecting the top 20 of 10,000 candidate columns on 500 rows can produce a CV AUC over 0.85 on features that are pure noise, because with that many candidates some will correlate with the label by chance and selection systematically harvests that chance correlation.

### Q4 — Would a filter method catch an XOR-style interaction (y = X1 XOR X2, each individually uncorrelated with y)?
**Testing:** whether "filter methods are marginal" is understood as a hard limitation, not a vague weakness.
**Answer:** No. Filter methods score each feature against the target in isolation; both X1 and X2 have ~zero marginal correlation with y in this construction, so both get discarded regardless of threshold. A tree splitting jointly on both, or a wrapper method scoring the pair together, recovers the signal.
**Follow-up trap:** *"So do you ever recommend filter methods?"* — yes, as a cheap first pass to cut obviously irrelevant columns (constant features, near-zero variance, extremely high missingness) before a more expensive wrapper or embedded step, never as the sole selection method when interactions are plausible.

### Q5 — What's the difference between permutation importance and Gini/MDI importance, and when does permutation importance itself mislead you?
**Answer:** Gini/MDI is computed from training-time impurity decrease and inherits the cardinality bias above. Permutation importance shuffles one column on *held-out* data and measures the drop in a real metric — model-agnostic, immune to the split-count bias. It misleads under correlated features: shuffling one of two highly correlated columns barely hurts the score because the model still has the redundant other one, so both get scored as unimportant even though the pair matters.
**Follow-up trap:** *"How would you detect that failure mode before it burns you?"* — cluster features by correlation first (hierarchical clustering on `1 - |corr|`), inspect within-cluster importance sums rather than individual members, or drop one of a highly correlated pair before running importance at all.

### Q6 — Your RFECV job on 300 features with 5-fold CV and a 500-tree gradient boosted model has been running for 10 hours. What do you change?
**Answer:** `step=1` means roughly 300 × 5 = 1500 full model fits at 500 trees each — that's the arithmetic causing the runtime, not a bug. Increase `step` to remove features in batches (e.g. `step=0.1`, 10% per round), reduce `n_estimators` during the search and refit the final model at full size once the feature set is fixed, or replace RFECV with embedded selection (native gain-based importance with a CV-validated threshold) which trains once instead of hundreds of times.
**Follow-up trap:** *"Does coarser stepping change the answer, not just the speed?"* — yes, it coarsens the ranking, since features get evaluated and dropped in batches rather than one at a time, so a borderline feature might be cut alongside genuinely weak ones. State that as an explicit accuracy-for-speed tradeoff, not a free lunch.

### Q7 — SHAP summary plot shows a `customer_id_hash`-derived feature near the top of global importance. What do you do?
**Testing:** whether you'll ship an obviously wrong signal because a library said so.
**Answer:** Investigate before trusting it — a near-identifier feature ranking high is the textbook symptom of the cardinality bias carrying through into SHAP via the underlying tree structure, or of target leakage (the ID correlates with something that happened *after* the label was determined, like a sign-up cohort that determines both the ID range and the outcome). Drop clearly identifier-like columns before training regardless of what the ranking says, and check for leakage on any surprising top feature before accepting the ranking.
**Follow-up trap:** *"What if it turns out to be real signal, not an artifact — say the ID range does encode signup cohort, which genuinely predicts churn?"* — then encode the actual construct (signup date, cohort) as an explicit feature instead of leaving a raw ID hash in the model, because the ID itself won't generalize to new customers outside the training ID range and will silently degrade over time.

### Q8 — Explain the curse of dimensionality to someone who thinks "more features can only help."
**Answer:** Distance-based and density-based methods degrade because in high dimensions distances concentrate — the ratio between the nearest and farthest neighbor's distance tends toward 1, so "nearest neighbor" stops being meaningful. Quantitatively, matching the sample density you had with `N` points in 1D requires `N^d` points in `d` dimensions; 100 points at 10 dimensions would need `10^20` points to match 1D density. Every added feature that isn't predictive adds sparsity and variance without adding signal, which is why models overfit as `p` grows relative to `n`.
**Follow-up trap:** *"Does this apply to a 500-tree XGBoost model the same way it applies to kNN?"* — no, and saying it does is the trap. Tree ensembles partition axis-by-axis and are considerably more robust to irrelevant high-dimensional features than distance/density methods (kNN, LOF, kernel SVMs); they still pay a variance and training-time cost, but they degrade more gracefully.

### Q9 — L1 vs L2 regularization for feature selection — why does L1 zero out coefficients and L2 doesn't?
**Answer:** L1's penalty (`|coefficient|`) has a non-differentiable corner exactly at zero, and the geometry of constrained optimization (the L1 ball has corners on the axes) means the optimum frequently lands exactly at a coefficient of zero. L2's penalty (`coefficient²`) is smooth everywhere and its constraint region is a sphere with no corners, so it shrinks coefficients toward zero but essentially never lands exactly on it. L1 gives you selection for free; L2 gives you shrinkage without selection.
**Follow-up trap:** *"Does L1 selection require feature scaling?"* — yes, and forgetting this is a common bug: the penalty is applied to the raw coefficient magnitude, so an unscaled feature measured in the thousands gets penalized far more heavily per unit of predictive contribution than a feature measured in single digits, biasing selection toward large-scale features for reasons that have nothing to do with predictive value.

### Q10 — Design a feature selection pipeline for a 10,000-feature fraud dataset with a 3-week SLA and a requirement that the final model be explainable to a regulator.
**Testing:** synthesis under real constraints, not recitation.
**Answer:** Stage it. Week 1: filter pass (variance threshold + mutual information) to cut 10,000 to a few hundred, cheaply, plus manual review to drop obvious identifiers and post-outcome leakage candidates. Week 2: embedded selection via a gradient boosted tree's native gain importance with a threshold validated by nested CV, cutting to 30-60 features. Week 3: SHAP on the final model for both the accuracy story and the compliance documentation, since SHAP's local-accuracy and consistency properties are what regulators actually want to see, not a Gini ranking. Every selection step lives inside the CV loop, and the final selected feature list is pinned and versioned, not recomputed at serve time.
**Follow-up trap:** *"The regulator asks why a feature with low SHAP importance is still in the model."* — you keep some low-importance-but-domain-required features intentionally (e.g. a mandated fairness/compliance feature, or one required by a specific regulation to be present or absent), and that decision needs to be documented separately from the statistical importance ranking — statistical importance and regulatory requirement are different axes, and conflating them is the actual failure mode here.

### Q11 — You add 200 new features to an existing model and offline AUC goes up 0.03, but online A/B test shows no lift. What's your hypothesis?
**Answer:** Most likely training-serving skew introduced by the new features specifically — offline features often use information not actually available or correctly computed at serve time (a batch-computed aggregate that's stale online, or a feature engineered with a leak from a downstream event). Second most likely: the offline evaluation leaked through feature selection or hyperparameter tuning being done on the same data used to report the 0.03 lift. Check feature parity between training and serving pipelines before questioning the online experiment's power.
**Follow-up trap:** *"What if the features are computed identically online and offline and there's no leak?"* — then the offline metric (AUC) may not track the online business metric (conversion, fraud caught net of false-positive cost), which is a metric-choice problem, not a feature-selection problem — a common and separate failure from leakage.

---

## Red flags that fail you

- Fitting `SelectKBest`, `RFECV`, or any selector on the full dataset before splitting.
- Treating `feature_importances_` as ground truth without mentioning the cardinality bias.
- Claiming filter methods catch interaction effects.
- Not knowing that L1 requires scaled features.
- Saying "SHAP is unbiased" without qualification.
- Recommending RFE on tens of thousands of features without acknowledging the retrain cost.
- No answer for what happens to correlated features under permutation importance.

---

## Cheat card

```
FAMILIES        filter (fast, marginal, no interactions) · wrapper (RFE/RFECV, model-in-the-loop,
                O(p) to O(p^2) retrains) · embedded (L1, tree importance, byproduct of one fit)
                permutation / SHAP (post-hoc, on held-out predictions, model-agnostic)

GINI/MDI BIAS   more candidate split thresholds → higher chance of a spuriously good split
                (Strobl et al. 2007). High-cardinality / continuous features inflated.
                Fix: permutation importance or SHAP, not raw feature_importances_.

MUTUAL INFO     sklearn mutual_info_classif defaults: n_neighbors=3, discrete_features='auto'
                small n_neighbors = noisier estimate on small samples

L1 vs L2        L1 |w| has a corner at 0 -> exact sparsity. L2 w^2 is smooth -> shrinks, never zero.
                L1 selection REQUIRES feature scaling (penalty is scale-dependent).

XOR TRAP        y = X1 XOR X2, both marginally uncorrelated with y -> filter methods miss it entirely

CURSE OF DIM    matching 1D density with N points needs N^d points in d dims
                N=100, d=10 -> 10^20 points needed. Distance/density methods (kNN, LOF) hit this hard;
                tree ensembles degrade more gracefully.

LEAK RULE       any step touching y (selection, scaling params, imputation stats) must be
                INSIDE the CV fold via Pipeline, refit per fold — not fit once on all data

PERMUTATION     shuffle 1 col on HELD-OUT data, measure score drop. Fails on correlated pairs:
                both get scored ~unimportant even though the pair matters together.

SHAP            TreeExplainer exact for trees, O(T*L*D^2). Satisfies local accuracy + consistency
                (Gini importance satisfies neither). Still inherits mild cardinality bias from trees.

RFECV COST      p=200, step=1, 5-fold -> ~1000 model fits. step=0.1 trades ranking granularity for speed.

WHEN TO SKIP    well-regularized XGBoost/LightGBM + no latency/audit requirement -> selection buys
                little; can even hurt if it drops an interaction-only feature (XOR case)
```

## Sources

- [Feature selection — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/feature_selection.html) — accessed 2026-08-01
- [mutual_info_classif — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.mutual_info_classif.html) — accessed 2026-08-01
- [RFECV — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_selection.RFECV.html) — accessed 2026-08-01
- [Permutation feature importance — scikit-learn 1.9 documentation](https://scikit-learn.org/stable/modules/permutation_importance.html) — accessed 2026-08-01
- [Are SHAP Values Biased Towards High-Entropy Features? — SpringerLink](https://link.springer.com/chapter/10.1007/978-3-031-23618-1_28) — accessed 2026-08-01
- [Importance measures derived from random forests: characterisation and extension (arXiv, discusses Strobl et al. 2007)](https://arxiv.org/pdf/2106.09473) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
