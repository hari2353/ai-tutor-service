# Feature Engineering, Leakage, and CV Strategies for Time-Series and Grouped Data

> **Track:** T03 Classical ML · **Time:** 2h · **Prereqs:** T03-regularization, T03-metrics-calibration · **Updated:** 2026-08-03
> **Module id:** `T03-feature-eng` · **Tags:** practice
> **Lab:** `labs/python/06-feature-eng/`

## The 30-second version

Feature engineering is the highest-leverage lever in classical ML — a well-constructed feature routinely beats a fancier model on the same raw data, because it directly encodes domain knowledge the model would otherwise have to discover from data alone (interaction terms, ratios, domain-specific aggregates, time-since-last-event). Leakage is the single most common and most damaging feature-engineering bug: any information that would not actually be available at prediction time, but is available at training time because of how the dataset was constructed, silently inflates validation metrics while doing nothing for production performance — the canonical example is a "days since account closure" feature predicting churn, where the feature's existence at all already reveals the label. Standard k-fold cross-validation itself is a leakage vector, not just a diagnostic tool, whenever rows are not independent and identically distributed: for time-series data, a random k-fold split lets the model train on future rows and validate on past ones, giving a look-ahead advantage no production system will ever have, which is why time-series CV uses only strictly-past folds for training (`TimeSeriesSplit` or a rolling/expanding window); for grouped data (multiple rows per user, per patient, per store), a random split can put some of a group's rows in train and others in validation, letting the model implicitly memorize group-identity-correlated signal rather than genuinely generalizing, which is why grouped data requires `GroupKFold` (entire groups assigned wholly to one fold). Both failures share the same signature: validation metrics that look excellent and production metrics that don't, discovered only after the model ships.

## Why this gets asked

Because leakage is the single most common reason a model performs beautifully in every offline evaluation and then embarrassingly in production, and every senior interviewer has either personally shipped a leaky model or caught one before it shipped — this question separates people who've internalized "how would this feature/split behave on data from tomorrow, which doesn't exist yet at training time" as a reflexive check, from people who only think about model architecture and never interrogate where their features and folds actually came from. It's also asked because it's cheap to probe with a story format ("here's a churn model with 98% AUC that failed completely in production, what happened") that reveals genuine debugging instinct rather than memorized facts.

---

## Lineage: past → present → future

**What came before.** Early tabular ML practice largely treated cross-validation as a single, universal recipe — random k-fold, applied uniformly regardless of the data's actual dependency structure — because the theoretical justification for k-fold CV (an unbiased-ish estimate of out-of-sample error) implicitly assumes rows are exchangeable, an assumption that genuinely holds for many classic statistical datasets but silently fails for the two structures (temporal, grouped) that dominate real production tabular data. The pain this created was invisible until deployment: a model validated with standard k-fold CV on time-series or grouped data can show excellent, reproducible cross-validation scores while being fundamentally unable to generalize the way production requires, because the CV procedure itself was answering a different (easier) question than "how will this model perform on genuinely new future data or genuinely new entities."

**Where it stands now.** `TimeSeriesSplit`, `GroupKFold`, and their variants (rolling-origin evaluation, nested CV for hyperparameter tuning combined with either) are now standard, well-documented tooling in every major ML library, and "what CV strategy did you use and why" is treated as a first-class question alongside model choice in serious production ML review — the consensus is that CV strategy must match the actual deployment scenario's dependency structure, not a generic default. Feature engineering itself has partly been automated (automated feature engineering tools, embeddings from pretrained models substituting for hand-crafted features in some domains) but for structured tabular data, hand-engineered domain features (ratios, time-windowed aggregates, interaction terms informed by actual business logic) remain highly competitive and often outperform what automated feature generation discovers, because domain knowledge about *which* interactions and aggregates are causally or mechanistically meaningful is exactly the kind of prior information automated search doesn't have.

**Where it's heading.** The direction of travel is toward CV-strategy selection and leakage auditing becoming more automated and standardized in ML tooling and platform-level guardrails (e.g., automatically flagging a feature that has zero variance before a certain date, or a temporal split boundary violation), reducing reliance on an individual practitioner remembering to check — but the underlying judgment (does this feature encode information genuinely available at prediction time, does this CV split reflect genuinely unseen future/entities) remains a durable, non-automatable skill, since automated leakage detection tools can catch known patterns but not novel, business-logic-specific leakage paths a domain expert would recognize.

---

## Mental model

```
LEAKAGE: information present at TRAINING time that would NOT be present at PREDICTION time

  training-time snapshot:                    prediction-time reality:
  [all historical data, including            [only data that existed
   information from AFTER the                 BEFORE the prediction
   prediction point in time]                  moment, nothing later]
        |                                            |
        v                                            v
  model learns to exploit the                model has NO access to
  "from-the-future" signal                   that signal in production
  -> GREAT validation metric                 -> feature is silently
                                                 missing/meaningless
                                                 -> metric collapses

RANDOM K-FOLD ON DEPENDENT DATA: rows leak information across the fold boundary

  TIME SERIES (random fold):        GROUPED DATA (random fold):
  train: Jan, Mar, May               train: user_42's rows 1,3,5
  val:   Feb, Apr, Jun                val:   user_42's rows 2,4,6
  -> model trained on "future"        -> model can memorize
     relative to some val rows           user_42-specific quirks,
     -- impossible in production        not generalize to NEW users

  FIX: TimeSeriesSplit                FIX: GroupKFold
  train: Jan-Mar | val: Apr           train: users A,B,C | val: users D,E
  train: Jan-Apr | val: May           (a user's rows NEVER split across folds)
  (only strictly PAST folds train)
```

The one-line mental model: **every feature and every CV split should be interrogated with the same question — "would this exact piece of information be available, in this exact form, at the moment a real production prediction is made" — and if the answer is no, it's leakage regardless of how it entered the pipeline.**

---

## How it actually works

### The taxonomy of feature engineering techniques, and what each buys

- **Ratios and rates** (e.g., `clicks / impressions` rather than raw `clicks`) normalize away a confounding scale factor (total exposure) that a raw count conflates with genuine propensity — a linear model given the raw count alone has to *learn* this normalization from data, while a ratio feature hands it the normalization directly, often with far less data needed to reach the same performance.
- **Time-windowed aggregates** (rolling 7-day/30-day sums, means, counts) encode recent behavioral trend in a form a model can use without needing to see the full raw event history — critically, these must be computed using **only data available strictly before the prediction timestamp** for each row, or they become a leakage vector (see below).
- **Interaction/cross features** (e.g., `is_weekend * hour_of_day`, or a concatenated categorical combining two raw categoricals) directly hand a model a nonlinear relationship that a purely additive linear model cannot represent on its own, though tree ensembles can discover many interactions automatically via sequential splits — interaction features remain valuable even for tree models when the interaction is a specific, high-value one the model might otherwise need many splits or a lot of data to discover reliably.
- **Target encoding** (replacing a categorical value with a statistic of the target conditioned on that category) is powerful for high-cardinality categoricals a one-hot encoding would explode into thousands of sparse columns, but is a well-documented leakage vector itself unless computed with strict CV-fold isolation (or CatBoost's ordered target statistics from the trees-boosting module) — encoding a category using the *same rows* whose target you're trying to predict leaks the label into the feature directly.
- **Domain-derived features** (a specific business ratio, a known risk score formula, a physically meaningful derived quantity) routinely outperform generic automated feature construction precisely because they encode causal or mechanistic knowledge no amount of automated combination-search can discover from data alone without an impractically large sample.

### Leakage, taxonomized by how it enters the pipeline

**Target leakage** occurs when a feature is, directly or through a near-deterministic proxy, a restatement or consequence of the label rather than a genuine predictor of it — the canonical example is a "number of days account has been marked for closure" feature predicting churn, where the feature's very existence in the row already encodes that churn happened; a more subtle version is a feature computed *after* the outcome in the real-world timeline but stored in the same row without a timestamp check (e.g., a "support ticket resolution code" feature when predicting whether a support ticket will be escalated — the resolution code may only exist once escalation status is already known).

**Train/test contamination** occurs when a preprocessing step (imputation using the full dataset's mean, feature scaling using the full dataset's statistics, target encoding using the full dataset) is fit on data that includes rows that will later be used for validation or test — the fix is always to fit any such transformation exclusively on the training fold and only *apply* (not re-fit) it to validation/test, inside the cross-validation loop, not before it.

**Temporal leakage** occurs when a feature's value at the time it's used for training reflects information from after the prediction point it's meant to inform — a rolling aggregate computed over "the full dataset" rather than "strictly prior to this row's timestamp" is the most common concrete instance, and it's easy to introduce accidentally with a naive `groupby().rolling()` call that doesn't explicitly exclude the current and future rows.

**Group leakage** occurs when multiple rows share a latent grouping (the same user, patient, store, or device) and a random split puts some of that group's rows in training and others in validation — the model can then implicitly learn group-identity-specific patterns (this particular user's idiosyncratic behavior) that inflate validation performance without reflecting genuine generalization to a new, previously-unseen group member, which is what production actually requires when a new user/patient/store shows up.

### Time-series cross-validation: why random k-fold is invalid and what replaces it

Random k-fold assumes exchangeability — that the order of rows carries no information relevant to the split, which is false by construction for time-series data, where autocorrelation and trend mean a row's "neighbors" in time are more similar to it than a randomly chosen row. `TimeSeriesSplit` (or equivalently, rolling/expanding-window backtesting) instead generates a sequence of folds where each fold's *training* set consists strictly of data before the *validation* set's time range — an expanding window uses all data up to a point (train: Jan-Mar, validate: Apr; train: Jan-Apr, validate: May; ...), while a rolling window uses a fixed-size trailing window instead of an ever-growing one, which better simulates a production system with limited effective "memory" of the past or where older data is genuinely less relevant due to distribution shift. The validation metric reported should be the *average across all folds*, not just the final fold, since a single fold's outcome can be an unrepresentative slice of the overall time period (e.g., one fold happening to coincide with an unusual seasonal event).

### Grouped-data cross-validation: why a group must never split across folds

When multiple rows share a group (patient visits, user sessions, store-level records), the actual generalization question in production is almost always "how will this model perform on a *new* patient/user/store it has never seen," not "how will it perform on more rows from patients it has already partially seen." `GroupKFold` assigns each entire group to exactly one fold, so no group ever appears partially in training and partially in validation — the resulting validation estimate honestly reflects generalization to unseen groups, at some statistical cost (fewer effective "independent" folds if group sizes are very unequal, since a fold's composition is constrained by which whole groups land in it, not by a free choice of individual rows).

### Nested cross-validation: when hyperparameter tuning and evaluation are combined

Using the same CV loop both to tune hyperparameters (picking the best `lambda`, `max_depth`, etc. by validation performance) and to report final performance introduces a subtle optimistic bias, because the hyperparameter search has effectively "seen" the validation folds' performance through the selection process, even though no individual row's label was used to fit the model directly — the fix, when compute allows, is **nested CV**: an outer loop provides the final, honest performance estimate, and within each outer training fold, a separate inner CV loop is used purely for hyperparameter selection, so the outer validation fold is never used, even indirectly through hyperparameter choice, before the final reported metric is computed on it.

---

## Build it from scratch

```python
import numpy as np
import pandas as pd

def rolling_feature_no_leakage(df, group_col, time_col, value_col, window_days):
    """Correct: only uses data strictly BEFORE each row's own timestamp."""
    df = df.sort_values([group_col, time_col]).copy()
    result = np.full(len(df), np.nan)
    for group, idx in df.groupby(group_col).groups.items():
        sub = df.loc[idx]
        times = sub[time_col].values
        values = sub[value_col].values
        for i in range(len(sub)):
            cutoff = times[i]
            mask = (times < cutoff) & (times >= cutoff - np.timedelta64(window_days, 'D'))
            result[df.index.get_indexer(sub.index[i:i+1])] = values[mask].mean() if mask.any() else 0.0
    return result

def target_encode_no_leakage(df, cat_col, target_col, cv_folds):
    """Correct: encode each fold using ONLY the OTHER folds' statistics."""
    encoded = np.full(len(df), np.nan)
    global_mean = df[target_col].mean()
    for train_idx, val_idx in cv_folds:
        fold_means = df.iloc[train_idx].groupby(cat_col)[target_col].mean()
        encoded[val_idx] = df.iloc[val_idx][cat_col].map(fold_means).fillna(global_mean).values
    return encoded

def time_series_split(n, n_splits, min_train_size):
    """Minimal TimeSeriesSplit: expanding window, strictly-past training folds only."""
    fold_size = (n - min_train_size) // n_splits
    for i in range(n_splits):
        train_end = min_train_size + i * fold_size
        val_end = train_end + fold_size
        yield np.arange(0, train_end), np.arange(train_end, val_end)

def group_k_fold(groups, n_splits, seed=0):
    """Minimal GroupKFold: whole groups assigned to folds, never split."""
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_groups)
    group_folds = np.array_split(unique_groups, n_splits)
    for i in range(n_splits):
        val_groups = set(group_folds[i])
        val_idx = np.where(np.isin(groups, list(val_groups)))[0]
        train_idx = np.where(~np.isin(groups, list(val_groups)))[0]
        yield train_idx, val_idx
```
The lab exercise builds a deliberately leaky churn-prediction pipeline (a rolling feature computed over the *full* dataset rather than strictly-past data, and a target encoding fit before the CV split) alongside the corrected versions above, showing the leaky pipeline reporting an implausibly high AUC (often 0.95+) that collapses to a realistic value (often 0.65-0.75, depending on the synthetic setup) once leakage is removed — the exercise is designed to make the "too good to be true" signal visceral rather than theoretical.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A model's cross-validation AUC/accuracy is dramatically higher than any comparable published benchmark or prior model on similar data | Target leakage — a feature is a near-restatement of the label, or CV itself leaks information across folds | Audit every feature for "would this exact value be known at prediction time," and audit the CV procedure for fold-boundary information leakage before trusting the number |
| A time-series forecasting model performs excellently in offline backtesting but poorly on live data from the week after deployment | Random k-fold CV was used instead of time-respecting CV, giving the model an implicit look-ahead advantage never available in production | Switch to `TimeSeriesSplit` or rolling-window backtesting, and re-evaluate; expect the "real" validation number to be meaningfully lower |
| A churn/fraud model trained on multiple rows per user performs far worse on genuinely new users than the validation metrics predicted | Random k-fold split let some of each user's rows land in training and others in validation, letting the model partially memorize per-user quirks | Switch to `GroupKFold` keyed on user ID, re-evaluate, and expect validation metrics to drop toward a more honest estimate of new-user generalization |
| A preprocessing step (imputation, scaling, target encoding) produces suspiciously stable statistics across folds that don't reflect the visible variability in the raw data | Preprocessing was fit on the full dataset (including validation/test rows) before the CV split, rather than being refit inside each fold | Move all fit-and-transform preprocessing steps inside the CV loop (fit only on the training fold, transform validation/test using those fitted parameters) — use a pipeline object that enforces this structurally rather than manual step ordering |
| Hyperparameter tuning consistently picks the same "best" configuration across many reruns, but production performance is a bit worse than the tuning process's reported best score | Optimistic bias from using the same CV loop for both hyperparameter selection and final performance reporting | Use nested CV: an outer fold provides the final honest estimate, with hyperparameter search confined to an inner CV loop within each outer training fold |

---

## Tradeoffs & when NOT to use it

- **Don't apply `GroupKFold` when there genuinely is no meaningful grouping structure in your data** (rows are truly independent) — it needlessly constrains fold composition (whole groups, not free row selection) and can reduce effective sample diversity per fold for no generalization benefit if the independence assumption actually holds.
- **Don't use a rolling (fixed-size) window for time-series CV when the underlying process is stable and more historical data is unambiguously helpful** — an expanding window that uses all available past data will usually give a better-trained model in that case; reach for a rolling window specifically when you have reason to believe older data is stale or the process has genuinely shifted (a documented regime change, not just a hunch).
- **Don't build every possible interaction/ratio feature reflexively "just in case."** Feature bloat without domain justification increases overfitting risk (more dimensions for a fixed sample size) and slows iteration; prioritize features with a specific, articulable hypothesis for why they'd carry signal, and validate each meaningfully via ablation rather than throwing hundreds of auto-generated combinations at the model.
- **Don't skip nested CV as "unnecessary overhead" when hyperparameter tuning is extensive and the reported final metric will be used for a high-stakes go/no-go decision.** The optimism from using one CV loop for both selection and evaluation is real and can be large enough to flip a marginal go/no-go call; reserve the simpler single-loop CV for early iteration where the exact final number matters less than relative comparisons between candidate approaches.

---

## Interview questions

### Q1 — Give a concrete example of target leakage that isn't the "obvious" case of literally including the label as a feature, and explain the mechanism.
**Testing:** whether leakage is understood as a broad category (information unavailable at prediction time) rather than a narrow, easily-spotted pattern.
**Answer:** A "days since account marked for closure" feature predicting churn — the feature only has a non-null, meaningful value *because* churn already happened, so its presence (or non-null-ness) is itself a near-perfect proxy for the label, even though it's not literally the label column. The mechanism: any feature whose value or existence is causally downstream of the outcome, rather than causally or temporally upstream of it, leaks the label back into the model regardless of how indirect the encoding is.
**Follow-up trap:** *"How would you detect this kind of leakage without already knowing the answer in advance?"* — check feature importance rankings for any single feature with an implausibly dominant importance score relative to domain expectations, and manually audit the top few features' actual data-generation timing against the prediction point — an implausibly high validation AUC combined with one dominant feature is the classic joint signal.

### Q2 — Why is random k-fold cross-validation invalid for time-series data, mechanically, and what specifically replaces it?
**Testing:** the exchangeability assumption and its violation, not just "you should use TimeSeriesSplit."
**Answer:** K-fold CV's validity as an unbiased-ish estimate of out-of-sample performance relies on rows being exchangeable — that a random subset is representative of "future, unseen data" in the same way any other subset would be. Time-series data violates this because of autocorrelation and trend: a row's temporal neighbors are systematically more similar to it than a randomly chosen row, and importantly, a production system will only ever have access to strictly past data when predicting a future point — random k-fold's occasional "train on May, validate on March" fold configuration is a scenario that can never occur in production, giving the model implicit access to future information. `TimeSeriesSplit` (or manual rolling/expanding window backtesting) replaces it by ensuring every validation fold's training data is strictly temporally prior.
**Follow-up trap:** *"Does using TimeSeriesSplit alone guarantee your features are leakage-free for time-series data?"* — no; the CV split being correct doesn't fix a *feature* that itself was computed using future information (e.g., a rolling aggregate computed over the entire dataset rather than strictly-prior rows) — CV strategy and feature construction are two separate places temporal leakage can enter, and fixing one doesn't fix the other.

### Q3 — Why must a target encoding be computed with fold isolation, and what exactly goes wrong if it isn't?
**Testing:** the specific mechanism of target-encoding leakage, connecting back to the trees-boosting module's CatBoost discussion.
**Answer:** Naive target encoding replaces a categorical value with a statistic (e.g., mean target) of that category computed across the *entire* training set, including the very row being encoded — so that row's own label contributes to its own feature value, an explicit (if subtle) form of leakage. The fix is to compute the encoding using strict CV-fold isolation: for each fold, encode using only the *other* folds' statistics, never the fold currently being predicted, ensuring no row's label ever influences its own encoded feature value.
**Follow-up trap:** *"If your target encoding is computed with proper fold isolation during cross-validation, is it automatically safe to use the SAME encoding logic in production on new incoming data?"* — the production encoding should be computed once using the *entire* training set (now legitimately "past" data relative to any genuinely new production row, which by definition wasn't part of that training set) — this is different from, and simpler than, the fold-isolated encoding used during CV, and conflating the two (e.g., accidentally deploying a fold-specific encoding rather than the full-training-set one) is a real, if less common, operational bug.

### Q4 — Explain why `GroupKFold` is necessary for a churn model trained on multiple historical snapshots per user, and what specifically would go wrong with plain k-fold.
**Testing:** the group-leakage mechanism and its concrete production consequence.
**Answer:** With multiple rows per user (e.g., monthly snapshots), plain random k-fold can place some of a given user's rows in training and others in validation. The model can then learn user-specific idiosyncrasies (this particular user's baseline usage pattern, quirks correlated with their identity) that happen to correlate with their churn outcome, inflating validation performance in a way that doesn't reflect genuine ability to predict churn for a *brand-new* user the model has never seen any row of — which is what production actually needs, since new users are exactly who the model must generalize to. `GroupKFold` assigns each user's entire set of rows to one fold, so validation performance genuinely reflects generalization to unseen users.
**Follow-up trap:** *"If your production system actually DOES continuously retrain on new snapshots of the same, already-known user base (not genuinely new users), does GroupKFold's stricter estimate still apply, or is it now overly conservative?"* — if the production use case is genuinely "predict the next snapshot for an already-partially-observed user," then plain k-fold's easier generalization target is arguably the more representative estimate for that specific deployment scenario, and GroupKFold could understate real achievable performance — the correct CV strategy must match the actual deployment scenario, and "always use GroupKFold for grouped data" is a strong default, not an unconditional law, when the true production task is closer to within-group prediction than cross-group generalization.

### Q5 — What's the difference between "train/test contamination" and "temporal leakage," and give an example of each that could coexist in the same pipeline.
**Testing:** distinguishing two related but mechanically distinct leakage taxonomies.
**Answer:** Train/test contamination is a *procedural* error — fitting a preprocessing step (scaler, imputer, target encoder) on data that includes rows later used for validation/test, regardless of whether the data itself has any temporal structure. Temporal leakage is a *feature-construction* error specific to time-ordered data — a feature's value reflects information from after the prediction timestamp it's meant to inform, independent of how the train/test split itself is performed. Both could coexist: a rolling-average feature computed over the full dataset (temporal leakage in the feature) that is then also fit/scaled using statistics from the full dataset before any CV split (train/test contamination in the preprocessing) — fixing only one leaves the other intact.
**Follow-up trap:** *"If you fix the CV split to use TimeSeriesSplit properly, does that also fix a scaler that was fit on the whole dataset before the split?"* — no; the CV split strategy and the preprocessing-fitting step are independent failure points — a correctly time-respecting split still leaks if the scaler/imputer/encoder was fit once on the full dataset *before* the split loop begins, rather than being refit inside each fold using only that fold's training data.

### Q6 — Why does nested cross-validation exist, and what specific optimistic bias does it remove that single-loop CV (used for both tuning and reporting) has?
**Testing:** the subtle "hyperparameter selection itself sees the validation data" bias, often missed even by careful practitioners.
**Answer:** When the same CV loop is used to both select hyperparameters (by comparing validation performance across candidate configurations) and report the final performance number, the selection process has effectively been informed by every fold's validation performance, even though no individual label was used to fit the model's *parameters* directly — the *hyperparameter* itself was chosen because it performed best on these specific validation folds, which is a form of information leakage into the final reported number. Nested CV removes this by using an outer loop exclusively for final, honest evaluation, with hyperparameter search confined to a separate inner CV loop within each outer training fold, so the outer validation fold's performance never influences any choice made before that final evaluation.
**Follow-up trap:** *"Given the added compute cost, when would you reasonably skip nested CV in practice?"* — during early-stage iteration where the goal is comparing relative approaches (does gradient boosting seem to beat linear regression on this problem, roughly) rather than reporting a final, precise number for a high-stakes go/no-go decision — the optimistic bias from single-loop CV is usually modest in magnitude and tolerable for relative comparisons, but should not be the basis for a final, precisely-quoted performance claim used in a high-stakes decision.

### Q7 — A colleague built a rolling 30-day feature using `df.groupby('user_id').rolling(30).mean()` directly on a sorted-by-date dataframe. Is this safe, and if not, what's the specific bug?
**Testing:** a very common, specific, easy-to-miss implementation bug in rolling feature construction.
**Answer:** It depends on whether pandas' rolling window is inclusive of the current row (by default, yes) — if the intent is "the average of the prior 30 days, not including today," a naive `.rolling(30).mean()` on a window that includes the current row's own value leaks that row's own (possibly label-correlated) value into its own feature. The fix is to explicitly shift the window by one row (`.shift(1).rolling(30).mean()`) or otherwise ensure the window strictly excludes the current row, depending on exactly what "as of this prediction moment" should mean for the specific feature.
**Follow-up trap:** *"If the feature being rolled is itself something that's only known with a reporting lag (e.g., revenue figures finalized 3 days after the fact), does shifting by 1 row fully fix the leakage?"* — no; if there's a genuine multi-day reporting lag on the underlying raw data, shifting by only 1 row still includes data that, in a real production prediction made on that date, would not yet have been finalized/available — the shift amount must match the *actual* real-world data-availability lag, not just "exclude the current row," which is a more common and more subtly wrong assumption than it first appears.

### Q8 — Design question: you're predicting hospital readmission risk using patient visit records, with multiple visits per patient spanning several years. What CV strategy do you use, and what's the single most important leakage check before trusting any result?
**Testing:** combining both grouped-data and temporal reasoning in a realistic, higher-stakes scenario.
**Answer:** This needs a combined strategy, not just one of GroupKFold or TimeSeriesSplit alone: split by patient (GroupKFold-style, so no patient's visits are split across train/validation) *and* respect temporal order where possible (don't let an earlier fold's training data include visits that occurred after a later fold's validation visits, if the deployment scenario involves predicting forward in time for new visits) — in practice this often means a combined "group + time" split: assign whole patients to folds while also ensuring the temporal ordering of visits used for training genuinely precedes what's being predicted, if the production system will be predicting readmission for new visits going forward. The single most important leakage check: audit every feature for whether it could only be known *after* the readmission outcome is already determined (e.g., a discharge summary field that's only finalized once it's known whether the patient was readmitery) before trusting any validation number, since medical records are a well-documented, high-risk domain for exactly this kind of leakage.
**Follow-up trap:** *"Your validation AUC after fixing the group split is a full 15 points lower than the ungrouped-split number the previous team reported. How do you communicate this to a stakeholder who's already excited about the higher number?"* — present both numbers with a clear, concrete explanation of what each one actually measures (the ungrouped number reflects a mix of learning genuine patterns and memorizing per-patient quirks, which doesn't generalize to a genuinely new patient; the grouped number is the honest estimate of new-patient generalization, which is what the deployed system will actually face) — the lower, honest number is the one that should drive the go/no-go decision, and explaining *why* the discrepancy exists (rather than just asserting the new number is "more correct") is what earns the stakeholder's trust in the revised process going forward.

### Q9 — What's a concrete example of an "obviously good" ratio or aggregate feature that could still introduce leakage if constructed carelessly?
**Testing:** recognizing that even sound feature-engineering techniques (ratios, aggregates) aren't automatically leakage-free.
**Answer:** A customer's "average order value" feature, if computed over the customer's *entire* order history including orders placed *after* the prediction point (e.g., after the churn-prediction date being modeled), leaks future behavior back into a feature meant to describe the customer's state *as of* the prediction moment — the ratio/aggregate technique itself is sound, but the time window it's computed over must be explicitly bounded to strictly-prior data, exactly like the rolling-feature leakage discussed above; "aggregate features" and "temporal leakage" are not mutually exclusive categories, and most real aggregate-feature leakage bugs are exactly this kind of unbounded-window mistake.
**Follow-up trap:** *"If the aggregate is computed correctly using only strictly-prior data, is the feature now guaranteed leakage-free?"* — not necessarily; if the aggregate is computed at training time using a batch process that has access to more complete/less-noisy historical data than what will actually be available in the live production serving path (e.g., a nightly batch job with a data completeness lag not present in the training pipeline's snapshot), there can still be a training/serving skew that behaves like leakage in the sense that validation performance won't be replicated in production — this is a distinct concern (training/serving skew) worth checking even after temporal leakage in the strict sense is ruled out.

### Q10 — Why does an implausibly high validation metric (relative to comparable published benchmarks or domain expectations) function as a leakage red flag on its own, without needing to already suspect a specific feature?
**Testing:** the practical, generalizable heuristic for catching leakage without prior knowledge of exactly where it is.
**Answer:** Genuine improvements in predictive performance on a well-studied problem tend to come in modest increments as feature quality and modeling sophistication improve incrementally — a sudden, large jump in validation performance relative to known benchmarks or reasonable domain-informed expectations is statistically more likely to indicate the model found an information shortcut (leakage) than a genuine breakthrough, simply because genuine breakthroughs of that magnitude on well-studied problems are rare events, while leakage bugs are common events, and base-rate reasoning favors investigating leakage first.
**Follow-up trap:** *"How would you distinguish a genuinely surprising, non-leakage-driven performance jump from a leakage-driven one, given that both look identical on paper (just 'higher than expected')?"* — investigate feature importances for an implausibly dominant single feature, manually trace that feature's real-world data-generation timing against the prediction point, and specifically try removing the single most suspicious feature to see if performance collapses back toward the expected range — a genuine breakthrough typically doesn't hinge entirely on one feature's removal, while a leakage-driven result very often does.

---

## Red flags that fail you

- Cannot name a concrete example of target leakage beyond "including the label as a feature" — doesn't recognize proxy/downstream-of-outcome features.
- Uses plain k-fold CV on time-series or grouped data without recognizing the exchangeability assumption is violated.
- Doesn't know that a target encoding must be computed with strict CV-fold isolation to avoid leaking the label into its own encoded value.
- Treats an implausibly high validation metric as good news rather than a leakage red flag worth investigating first.
- Fits preprocessing (scaling, imputation, encoding) on the full dataset before the CV split, rather than inside each fold.
- Cannot explain why nested CV exists or what specific bias it removes versus single-loop CV.

---

## Cheat card

```
LEAKAGE = info available at TRAINING time that would NOT be available at PREDICTION time
  TARGET LEAKAGE: feature is downstream-of/proxy-for the label (e.g. "days since account
    closed" predicting churn)
  TRAIN/TEST CONTAMINATION: preprocessing (scale/impute/encode) fit on FULL dataset before split
  TEMPORAL LEAKAGE: rolling/aggregate feature computed using data AFTER the row's own timestamp
  GROUP LEAKAGE: same entity's (user/patient/store) rows split across train AND validation

FEATURE TYPES: ratios/rates (normalize confound) | time-windowed aggregates (STRICTLY prior
  data only) | interaction/cross features (hand model a nonlinearity) | target encoding
  (high-cardinality categoricals, MUST be fold-isolated or leaks label into own encoding)

TIME-SERIES CV: random k-fold INVALID (violates exchangeability -- prod never sees future
  when predicting). TimeSeriesSplit: train on strictly-PAST folds only.
  expanding window: train grows (Jan-Mar->val Apr, Jan-Apr->val May...)
  rolling window: fixed trailing size -- use when older data is stale/distribution shifted
  report AVERAGE across folds, not just final fold

GROUPED CV: random k-fold INVALID if entity has multiple rows (model memorizes per-entity
  quirks). GroupKFold: whole group -> one fold, never split -- validates generalization
  to genuinely NEW entities (only use if that's actually what production needs)

NESTED CV: outer loop = honest final metric; inner loop (within each outer TRAIN fold) =
  hyperparameter selection. Fixes optimism from using ONE loop for both tuning AND reporting.

RED FLAG HEURISTIC: implausibly high metric vs published/domain benchmark -> suspect leakage
  FIRST, not a breakthrough. Check: one dominant feature in importances? Remove it -- does
  performance collapse? (genuine breakthroughs rarely hinge on one feature)
```

## Sources

- [scikit-learn: TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) — accessed 2026-08-03
- [scikit-learn: GroupKFold documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html) — accessed 2026-08-03
- [Leakage in data mining: Formulation, detection, and avoidance — Kaufman et al., KDD (2011)](https://dl.acm.org/doi/10.1145/2020408.2020496) — accessed 2026-08-03
- [Nested cross-validation — scikit-learn documentation](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
