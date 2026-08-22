# EDA: Distributions, Correlation Heatmaps, Outliers, the Questions to Ask First

> **Track:** T03 Classical ML · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T03-eda` · **Tags:** practice,critical

## The 30-second version

EDA is not "make some plots," it's an ordered set of falsifiable questions asked in a specific sequence, because each answer changes what the next question should be: shape and grain of the data first, then per-column distributions and missingness, then relationships between columns, then relationship to the target, then a deliberate hunt for leakage and imbalance last, because you now know enough to recognize when a feature is suspiciously good. Skewed distributions break mean/std-based methods (z-score outlier detection, some correlation assumptions) silently. Pearson correlation only measures linear relationship strength and reports near-zero on a real, strong, monotonic-but-curved relationship — Spearman (rank correlation) catches that. Outlier detection via z-score inherits skew's damage because both the mean and standard deviation it depends on are themselves dragged by outliers; IQR is the robust default because it's built from the median and quartiles. Class imbalance and target leakage are both things EDA is supposed to catch before you ever fit a model, and both are still routinely caught only in a postmortem instead.

## Why this gets asked

Because EDA is where the entire modeling project quietly succeeds or fails, and it's the part senior engineers actually spend the most time on while junior engineers rush through it to get to "the real work" of model fitting. The interviewer has personally shipped a model that looked implausibly good in offline validation — a 0.99 AUC nobody questioned hard enough — and found weeks later that a feature encoded information from after the label was determined, something a five-minute correlation check during EDA would have flagged immediately. They are also checking whether you know that "just look at the data" has actual statistical content: which correlation coefficient, which outlier definition, which order of investigation, and whether you can justify each choice rather than running `df.describe()` and calling it done.

---

## Lineage: past → present → future

**What came before.** John Tukey's *Exploratory Data Analysis* (1977) is the origin of the discipline as a formal practice — Tukey argued, against the prevailing confirmatory-statistics culture of his era, that you should look at data with an open mind *before* committing to a hypothesis test, using robust, resistant summaries (the five-number summary, the boxplot, which he invented specifically for this purpose) that don't get wrecked by the outliers you're trying to find. Pre-Tukey practice tended to go straight to a parametric test and trust its assumptions; the pain this caused was models and inferences built on distributions that were never actually checked, producing confident, wrong conclusions from data that had a skew, a bimodal split, or a handful of corrupt values nobody looked at.

**Where it stands now.** The tooling has consolidated around pandas-profiling/ydata-profiling and `sweetviz` for automated first-pass summaries, but the consensus among senior practitioners is that automated EDA reports are a starting point, not a substitute — they surface univariate statistics reliably but miss target leakage, miss most interaction effects, and can't apply domain judgment about which correlation is suspicious versus expected. The live disagreement is about *sequencing*: some practitioners front-load target-relationship analysis (plot everything against `y` immediately) to focus effort on what matters for the model; others insist on understanding the data's own structure first (grain, distributions, missingness) before ever looking at the target, on the argument that premature target-focus is exactly how you end up overfitting your *analysis* to noise in a single dataset, then hardcoding that noise into features. Both are defensible; the honest answer names the tradeoff. What's settled: correlation-only EDA is insufficient, because Anscombe's Quartet (1973) and, more recently, the Datasaurus Dozen (Matejka & Fitzmaurice, 2017) are the standard demonstrations that wildly different-looking scatterplots can share identical means, variances, and Pearson correlations — you cannot skip actually looking at the plot.

**Where it's heading.** LLM-assisted EDA — natural-language-driven profiling and hypothesis generation over a dataframe (e.g., asking an LLM agent to "find anything suspicious about this dataset") — is an active area with real early tooling (PandasAI-style agents, notebook copilots), and it can genuinely speed up the mechanical parts (generating the fifteen standard plots, computing standard statistics). It has not replaced the judgment calls: recognizing that a feature correlating at 0.98 with the target is leakage rather than a great predictor still requires domain knowledge the tool doesn't have, and treating current LLM-assisted EDA as a faster typist rather than a replacement for domain judgment is the accurate, non-speculative framing as of this writing.

---

## Mental model

```
   THE ORDER MATTERS -- each stage changes what you look for in the next

   1. GRAIN & SHAPE        what is one row? how many rows/cols? duplicated grain?
          │
          ▼
   2. PER-COLUMN           dtype correct? missingness per column? distribution shape
      (univariate)         (skew, multimodal, bounded)? cardinality of categoricals?
          │
          ▼
   3. RELATIONSHIPS        correlation heatmap (Pearson AND Spearman) · pairplots on
      (bivariate, X-X)     a sample · categorical-vs-categorical (crosstabs, Cramér's V)
          │
          ▼
   4. RELATIONSHIP TO Y    per-feature vs target (boxplots for categorical X, scatter/
      (X-to-target)        binned-mean for continuous X) · class balance in y itself
          │
          ▼
   5. THE HUNT             NOW you know enough to be suspicious: any single feature or
      (leakage, imbalance) small feature set that predicts y implausibly well? any feature
                            that couldn't have been known at prediction time? minority
                            class share, and does your metric choice account for it?
```

**Why last, not first:** you cannot recognize "implausibly well" without first knowing the ordinary distribution of correlations in this dataset — the leakage hunt is a search for outliers *in the space of feature-target relationships*, and you need stages 1-4 to know what "normal" looks like here before stage 5's search means anything.

---

## How it actually works

### Stage 1-2: grain, shape, and per-column distributions

```python
df.shape                                  # rows, columns — sanity check against expectation
df.duplicated(subset=key_columns).sum()   # is the grain what you think it is?
df.dtypes                                 # catches numeric-as-string, wrong-dtype dates early
df.isna().mean().sort_values(ascending=False)   # missingness rate per column
df.nunique()                              # cardinality — catches near-constant and near-unique columns
```

For every numeric column, plot the distribution, don't just read `.describe()`. Skewness matters concretely: a right-skewed distribution (income, transaction amounts, latencies — anything bounded at zero with a long tail) has `mean > median`, and models or statistics assuming symmetry (z-score outlier rules, some linear model residual assumptions) misbehave on it. `scipy.stats.skew` gives a number; as a rule of thumb, `|skew| > 1` is commonly flagged as substantially skewed and a candidate for a log or Box-Cox transform before applying anything that assumes near-normality.

```python
from scipy.stats import skew
skew(df["transaction_amount"].dropna())   # > 1 -> right-skewed, consider log1p transform
```

### Stage 3: correlation, and why Pearson misses monotone-nonlinear relationships

**Pearson's r measures the strength of a *linear* relationship only.** It's computed from standardized covariance, which is a measure of how well a straight line fits the data — a real, strong, purely monotonic-but-curved relationship (e.g., `y = x³`, or `y = log(x)`) can report a Pearson r near zero at certain ranges even though `x` perfectly determines `y`. **Spearman's ρ replaces raw values with their ranks before computing correlation**, so it measures the strength of any monotonic relationship — linear or not — because rank-transforming a strictly increasing curve leaves it strictly increasing.

```python
from scipy.stats import pearsonr, spearmanr

# On y = x**3 + noise, Pearson will UNDERSTATE the relationship strength versus Spearman,
# because Pearson is measuring linear fit, not the true monotonic dependency
x = np.linspace(-3, 3, 200)
y = x**3 + np.random.normal(0, 2, 200)
pearsonr(x, y)    # moderate r, understating the near-perfect monotonic dependency
spearmanr(x, y)   # much higher rho, correctly capturing the monotonic relationship
```
[A comparison of the Pearson and Spearman correlation methods — Minitab](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/supporting-topics/correlation-and-covariance/a-comparison-of-the-pearson-and-spearman-correlation-methods/) — accessed 2026-08-01

**A correlation heatmap built only on Pearson systematically under-reports real relationships that are nonlinear-but-monotonic.** The fix in practice is to compute both and flag any pair where Spearman is meaningfully higher than Pearson — that gap is itself diagnostic of nonlinearity worth a scatterplot.

```python
corr_pearson = df.corr(method="pearson")
corr_spearman = df.corr(method="spearman")
gap = (corr_spearman - corr_pearson).abs()
# pairs with a large gap are exactly where "eyeball the scatterplot" pays off
```

**Anscombe's Quartet / the Datasaurus Dozen are the standard proof that summary statistics lie by omission.** Four datasets (Anscombe, 1973) or a whole family of datasets shaped like a dinosaur, a star, and other figures (Matejka & Fitzmaurice, 2017) can share identical mean, variance, and Pearson correlation to two decimal places while looking nothing alike when plotted — one has a clean linear fit, one has an obvious outlier driving the whole correlation, one is a perfect curve, one is two clusters. **The practical rule this produces: never trust a correlation coefficient without plotting the underlying scatter, at least for the small number of feature pairs your heatmap flags as noteworthy.**

### Stage 4: relationship to target, and class imbalance

```python
# continuous feature vs binary target
df.groupby(pd.qcut(df["feature"], 10))["target"].mean().plot()   # binned mean — reveals nonlinearity a
                                                                    # single correlation number would hide

# class balance — the number that determines your entire metric strategy downstream
df["target"].value_counts(normalize=True)
```
A 99:1 class imbalance discovered here means accuracy is meaningless as a metric before you've fit a single model (a constant "always predict majority" classifier scores 99% accuracy), and it means your train/test split needs stratification (`stratify=y` in `train_test_split`) or a fold with too few minority examples will produce a metric that's noise, not signal.

### Stage 5: outlier detection, and why z-score fails on skewed data

**Z-score** flags a point as an outlier if `|x - mean| / std > threshold` (commonly 3). This assumes the data is roughly symmetric and that mean/std are stable, representative summaries. Both assumptions break under skew: **the mean itself is pulled toward the long tail, and the standard deviation is inflated by the very extreme values you're trying to detect**, which means a genuinely large-but-normal value in a skewed distribution's tail can fail to trigger the threshold (the std is already so inflated by other tail values that nothing looks like "3 std away" anymore), while legitimate smaller-magnitude anomalies on the short side get flagged as false positives.

**IQR-based detection** (`Q1 - 1.5×IQR`, `Q3 + 1.5×IQR` where `IQR = Q3 - Q1`) uses the median and quartiles, which are far more resistant to extreme values — moving the single largest point in a dataset arbitrarily far out doesn't move the median or the quartiles at all, whereas it moves the mean and std substantially. This is why IQR is the standard default for skewed real-world data (transaction amounts, latencies, income) where z-score is documented to under- and over-flag simultaneously. [Outlier Detection and Treatment: Z-score, IQR, and Robust Methods](https://medium.com/@aakash013/outlier-detection-treatment-z-score-iqr-and-robust-methods-398c99450ff3) — accessed 2026-08-01

```python
q1, q3 = df["amount"].quantile([0.25, 0.75])
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
outliers = df[(df["amount"] < lower) | (df["amount"] > upper)]
```

**Modified z-score** (using median and MAD — median absolute deviation — instead of mean/std) is the middle ground: `0.6745 × (x - median) / MAD`, commonly thresholded at 3.5. It gives you a z-score-shaped statistic without the sensitivity to the outliers it's trying to find, because both the median and MAD are themselves robust statistics.

### Target leakage — the thing stage 5 is really for

Target leakage is when a feature contains information that would not actually be available at prediction time, usually because it was computed using data from after the label was determined, or is a direct proxy/derivative of the label itself.

**Concrete example.** Predicting loan default; a feature `days_since_last_payment` is populated only for accounts that eventually missed a payment (it's null for accounts in good standing) — this is leakage because the feature's *existence* encodes the outcome. Another classic: predicting hospital readmission with a feature `discharge_disposition = "transferred to hospice"` — this is recorded at the same event that determines readmission status and effectively encodes it. Both slip past a correlation check that only looks for high correlation with `y`, because sometimes the leak shows up as high correlation with an *intermediate* variable, not `y` directly, and only domain knowledge catches it.

**The mechanical checks that catch some of it:**
```python
# a feature suspiciously close to perfectly predicting y is worth investigating even if
# it's not proof of leakage on its own
suspiciously_good = df.corrwith(df["target"]).abs().sort_values(ascending=False)

# does the feature's availability pattern correlate with the target? (the days_since_last_payment case)
df.groupby(df["feature"].isna())["target"].mean()
```
Neither check *proves* leakage — a feature can be legitimately, powerfully predictive without leaking (a great model feature and a leaked feature can look statistically identical). The only real test is asking, for every top feature, "could this value have existed, in this exact form, at the moment I need to make the prediction, using only information available then?" That question has to be asked by a human with domain knowledge; no automated EDA tool asks it for you.

---

## Build it from scratch

A minimal, from-scratch EDA driver that runs the five stages in order and surfaces exactly the things automated profilers tend to bury in noise:

```python
import numpy as np
import pandas as pd
from scipy.stats import skew, pearsonr, spearmanr

def eda_report(df: pd.DataFrame, target: str, key_columns: list[str] | None = None) -> dict:
    report = {}

    # Stage 1: grain & shape
    report["shape"] = df.shape
    if key_columns:
        report["duplicate_grain"] = int(df.duplicated(subset=key_columns).sum())

    # Stage 2: per-column
    report["missingness"] = df.isna().mean().sort_values(ascending=False).to_dict()
    numeric_cols = df.select_dtypes("number").columns.drop(target, errors="ignore")
    report["skew"] = {c: float(skew(df[c].dropna())) for c in numeric_cols}

    # Stage 3: relationships — the Pearson/Spearman gap flags nonlinear-monotonic pairs
    pearson_corr = df[numeric_cols].corr(method="pearson")
    spearman_corr = df[numeric_cols].corr(method="spearman")
    gap = (spearman_corr - pearson_corr).abs()
    np.fill_diagonal(gap.values, 0)
    report["nonlinear_candidates"] = gap.stack().sort_values(ascending=False).head(10).to_dict()

    # Stage 4: relationship to target + class balance
    if df[target].nunique() <= 20:
        report["class_balance"] = df[target].value_counts(normalize=True).to_dict()
    report["target_corr"] = df[numeric_cols].corrwith(df[target]).abs().sort_values(ascending=False).to_dict()

    # Stage 5: outliers via IQR (robust to the skew already measured in stage 2) + leakage flags
    outlier_rates = {}
    for c in numeric_cols:
        q1, q3 = df[c].quantile([0.25, 0.75])
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_rates[c] = float(((df[c] < lower) | (df[c] > upper)).mean())
    report["outlier_rate"] = outlier_rates
    report["leakage_suspects"] = {
        c: v for c, v in report["target_corr"].items() if v > 0.95   # tune threshold per domain
    }
    return report
```

This is a real, runnable starting point, not a replacement for looking at plots — it surfaces *where* to look (which pairs, which columns) so the human time goes to the handful of scatterplots and domain questions that actually matter instead of scrolling through fifty auto-generated charts. Reference lab: `(lab pending)` (build if not present) — includes a synthetic dataset with a deliberately planted leakage feature and a deliberately skewed column, with assertions that the report above catches both.

---

## How it's done in production

| Tool | What it adds |
|---|---|
| `ydata-profiling` (formerly pandas-profiling) | One-command univariate + correlation report with warnings for high cardinality, high correlation, skew, zeros/missing — good first pass, not a leakage detector |
| `sweetviz` | Side-by-side comparison reports, useful specifically for comparing train vs test distributions to catch train-serve skew before it becomes a production incident |
| Great Expectations / whylogs | Turns EDA findings into enforced data contracts — the skew you found manually becomes an automated assertion that fails a pipeline if the distribution shifts unexpectedly later |
| `seaborn.pairplot` / `plotly` | Interactive scatterplot matrices for the handful of feature pairs your correlation-gap analysis flagged as worth a human look |
| Notebook + version control on the EDA notebook itself | Findings from EDA (leakage suspects excluded, transforms applied, imbalance handling chosen) should be reproducible and reviewable, not a one-time interactive session whose conclusions live only in someone's memory |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Model has implausibly high offline AUC (0.98+) that doesn't hold up online | Target leakage never caught because EDA jumped straight to modeling without stage 5's suspicion pass | Explicitly check every top-correlated feature against "could this exist at prediction time" before trusting the metric |
| A correlation heatmap shows weak relationships everywhere, but a specific feature turns out to matter a lot once modeled | Pearson-only heatmap missed a monotonic-nonlinear relationship | Compute Spearman alongside Pearson; flag and plot large gaps |
| Outlier removal step deletes 15% of a legitimately right-skewed column (revenue, latency) | Z-score threshold applied to skewed data — inflated std hides real anomalies and mean-based flagging over-triggers on the long tail | Switch to IQR or modified z-score (MAD-based); check skew first, choose the outlier method accordingly |
| Model's minority-class recall is near zero, but accuracy looked fine in early EDA-driven sanity checks | Class imbalance noted but not acted on — no stratified split, no calibrated metric choice | Stratify splits, choose PR-AUC/F1/recall over accuracy, address imbalance explicitly at training time |
| A "great" new feature added post-EDA silently degrades the model in production three months later | The feature was a leaking proxy that happened to still be available at training time historically, but its relationship to the label was coincidental to how the historical data was collected, not causal | Re-run stage 5's leakage question specifically for any new feature before shipping, regardless of how good its offline correlation looks |
| Automated EDA profiling report (ydata-profiling) runs for 40 minutes and produces 300 pages nobody reads | Ran full profiling on a wide (thousands of columns) or very large dataset without sampling or column filtering first | Sample rows for the report, restrict to a feature shortlist for correlation-heavy sections, treat the tool as a first-pass filter, not the final analysis |

---

## Tradeoffs & when NOT to use it

- **Don't run automated EDA profiling and call it done.** It reliably computes univariate statistics and pairwise correlations; it does not know your domain, cannot ask "could this feature exist at prediction time," and Anscombe's Quartet is proof that summary statistics alone can be dangerously misleading without a plot.
- **Don't trust a Pearson-only correlation heatmap when you suspect nonlinear relationships (latencies, price elasticity, most physical and economic quantities involving diminishing returns or thresholds).** Compute Spearman too; the gap is the signal.
- **Don't apply z-score outlier detection to a distribution you haven't checked for skew.** Check `skew()` first; if `|skew| > 1`, default to IQR or MAD-based detection instead.
- **Don't do the leakage hunt first, before understanding the data's own structure.** You need a sense of what "normal" correlation strength looks like in this specific dataset before "implausibly high" means anything — searching for leakage without that baseline produces false alarms and missed real leaks in roughly equal measure.
- **When NOT to spend much time on EDA at all:** a well-understood, previously-modeled dataset where the schema, distributions, and known leakage traps are already documented from a prior project — re-running the full five-stage process from scratch on every retrain of an established pipeline is wasted effort; targeted checks for distributional drift since the last EDA pass are the better use of time.
- **Outlier removal itself is not automatically correct.** In fraud, medical, and safety-critical domains, the "outliers" your IQR filter flags are frequently the exact minority-class examples you most need to keep. Never blindly drop IQR/z-score-flagged points without checking their relationship to the target first.

---

## Interview questions

### Q1 — Walk me through your EDA process on a new dataset.
**Testing:** whether you have an actual ordered process or just a list of things you sometimes do.
**Answer:** Grain and shape first (what's one row, how many rows/columns, is the grain what I expect), then per-column univariate checks (dtypes, missingness, distribution shape and skew, cardinality), then relationships between features (correlation, both Pearson and Spearman, plus a sample of scatterplots), then relationship to the target (binned means for continuous features, class balance for the target itself), and only last, once I know what "normal" looks like in this dataset, a deliberate hunt for leakage and imbalance.
**Follow-up trap:** *"Why not check for leakage first, since it's the highest-value catch?"* — because you can't recognize "implausibly good" without a baseline for what correlation strength is typical in this data; jumping to the leakage hunt first produces both false alarms (flagging a legitimately strong, non-leaked feature) and misses (a leak that's not the single top-correlated feature but shows up as a suspicious pattern only visible after you've seen the whole correlation structure).

### Q2 — Why does Pearson correlation miss some real relationships that Spearman catches?
**Answer:** Pearson's r is computed from standardized covariance and specifically measures the strength of a *linear* fit. A relationship that is strictly monotonic but curved — like `y = x³` — can produce a low Pearson r in some ranges even though `x` fully determines `y`, because a straight line is a poor fit to a cubic curve even when the direction of the relationship never reverses. Spearman replaces raw values with ranks before correlating, so any monotonic transform of `x` leaves the rank order unchanged and Spearman reports the true strength of the monotonic dependency.
**Follow-up trap:** *"Would Spearman catch a U-shaped (non-monotonic) relationship?"* — no. Spearman only helps with monotonic-but-nonlinear relationships; a U-shape isn't monotonic at all (it decreases then increases, or vice versa), so both Pearson and Spearman will report weak correlation despite a strong relationship. That case needs a scatterplot or a nonlinear/binned analysis, not a different correlation coefficient.

### Q3 — Why does z-score outlier detection fail on skewed data specifically?
**Answer:** Z-score flags points based on `|x - mean| / std`, and both the mean and standard deviation are themselves sensitive to extreme values and to skew — a right-skewed distribution pulls the mean toward the tail and inflates the std because the tail values contribute large squared deviations. The result is two-directional failure: legitimate large values in the already-long tail can fail to register as "far enough" in std units because the std is already inflated by other tail values, while smaller-magnitude points on the short side of the distribution get over-flagged relative to a mean that's shifted away from them.
**Follow-up trap:** *"What would you use instead, and why is it more robust?"* — IQR-based detection (`Q1 - 1.5×IQR` to `Q3 + 1.5×IQR`) or modified z-score using median and MAD. Both use the median and quantiles/median-absolute-deviation instead of mean/std, and moving the single most extreme point in a dataset arbitrarily far doesn't move the median or quartiles at all, whereas it moves the mean and std substantially — that's the formal definition of a robust statistic (bounded influence function), which is why IQR resists exactly the corruption z-score is vulnerable to.

### Q4 — What is target leakage, with a concrete example, and how do you catch it in EDA?
**Answer:** Target leakage is when a feature contains information that wouldn't actually be available at prediction time, often because it's computed from data generated after the label, or is a near-direct encoding of the label. Example: predicting loan default with a feature `days_since_last_payment` that's null for accounts in good standing — its *existence pattern* alone encodes the outcome. In EDA, you catch some of it by flagging features with implausibly high correlation to the target and by checking whether a feature's missingness pattern correlates with the target, but neither check *proves* leakage — the only real test is asking, for each top feature, whether that exact value could have existed at prediction time using only information available then.
**Follow-up trap:** *"Your top feature has a correlation of 0.6 with the target, not 0.99. Are you safe from leakage?"* — no, a moderate correlation doesn't rule out leakage; a leak can be partial (the feature encodes some but not all of the outcome, or encodes an intermediate variable rather than the label directly) and still meaningfully inflate offline metrics without triggering a "too good to be true" correlation threshold. The domain question — could this exist at prediction time — has to be asked regardless of the correlation magnitude.

### Q5 — Anscombe's Quartet / the Datasaurus Dozen — what do they actually prove and why does it matter for your process?
**Answer:** Multiple, visually completely different datasets can share identical mean, variance, and Pearson correlation to several decimal places. It proves that summary statistics are a lossy compression of the data that can hide the exact structural facts (an outlier driving a correlation, a nonlinear relationship, two separate clusters) that matter most for modeling decisions. Practically it means you can never trust a correlation heatmap or a `.describe()` table as the final word — you need to actually plot the pairs your summary statistics flag as noteworthy.
**Follow-up trap:** *"Doesn't this just mean 'always plot everything'? Isn't that infeasible with 500 features?"* — right, which is why the practical answer isn't "plot everything," it's "use the summary statistics (correlation, the Pearson/Spearman gap, skew) to *rank* which pairs are worth a human look, then plot only the shortlist" — the summary stats aren't useless, they're a triage mechanism, not a final verdict.

### Q6 — A dataset has 99.5% negative class and 0.5% positive class. What does this change about your EDA and downstream evaluation plan?
**Answer:** It means accuracy is dead on arrival as a metric — a constant "always predict negative" classifier scores 99.5%. It means train/test/CV splits need stratification or a fold can end up with a handful or zero positive examples, making any per-fold metric noise. It means the outlier-detection lens itself might be pointed at exactly the wrong thing, since some of what IQR/z-score would flag as "outliers" in a feature might actually be your minority class's characteristic signature, not noise to remove.
**Follow-up trap:** *"Does stratification alone fix the evaluation problem?"* — no, it fixes the *split* problem (each fold gets a representative share of the minority class) but not the *metric* problem — you still need PR-AUC, F1, recall-at-fixed-precision, or a cost-weighted metric instead of accuracy or even plain ROC-AUC, because ROC-AUC can also look deceptively good under extreme imbalance.

### Q7 — Would you run automated EDA profiling (ydata-profiling, sweetviz) as your primary analysis, or as a supplement?
**Answer:** Supplement, always. It's excellent for the mechanical first pass — univariate distributions, missingness, obvious high-correlation pairs, cardinality warnings — done consistently and fast. It cannot ask "could this feature exist at prediction time," doesn't know your domain well enough to flag a suspicious-but-not-statistically-extreme relationship, and Anscombe's Quartet is the standing proof that identical summary statistics can hide completely different underlying structure that only a human-directed plot would catch.
**Follow-up trap:** *"Where specifically does an automated tool most often miss something that costs a project real time later?"* — target leakage, almost always. Automated profilers report correlation and importance scores, not causal plausibility, and the single most expensive EDA mistake (a leaked feature inflating offline metrics) requires exactly the domain judgment these tools don't have.

### Q8 — You compute both Pearson and Spearman correlation for every feature pair and find one pair where Spearman is 0.85 and Pearson is 0.15. What's your next step, and what does this gap tell you?
**Answer:** Plot the scatterplot for that pair immediately — a large Spearman-minus-Pearson gap is close to a direct signature of a monotonic-but-nonlinear relationship (a curve, a threshold effect, a log-like or power-like relationship) that a linear correlation summary is hiding. Depending on the shape you see, this often means the feature needs a transform (log, polynomial term, or binning) before a linear model can use it well, whereas a tree-based model would likely have picked up the relationship without any transform since trees don't assume linearity.
**Follow-up trap:** *"What if you see this gap and the scatterplot looks like pure noise with one influential outlier?"* — that's the other common cause of a Pearson/Spearman gap: Pearson is sensitive to a single extreme point dragging the linear fit, while Spearman (rank-based) is robust to that same point's magnitude. In that case the "relationship" is an artifact of one row, not a real nonlinear pattern, and the fix is investigating that single point (is it a sentinel value, a data error, a legitimate rare event) rather than transforming the whole feature.

### Q9 — Design the EDA plan for a 500-column, 50-million-row dataset where full profiling would take hours. What do you actually do?
**Testing:** whether you'll blindly run the standard tool at a scale where it doesn't work, or reason about the tradeoff.
**Answer:** Sample rows (a few hundred thousand is usually enough for distributional and correlation estimates to stabilize) before running any profiling tool, since row count drives compute cost far more than it drives statistical precision past a certain sample size. Use domain knowledge and a quick missingness/cardinality pass to cut 500 columns down to a shortlist of plausible predictors before running expensive pairwise correlation (which is O(p²) in column count) on the full set. Run the five-stage process on the shortlist with full rigor, and treat anything outside the shortlist as "revisit only if the shortlisted-feature model underperforms and I need to look further."
**Follow-up trap:** *"What if the signal is in a feature outside your shortlist — a rare, previously-unknown-important interaction?"* — that's the real cost of the shortcut, and it's a legitimate risk, not a solved problem — sampling and shortlisting trade thoroughness for tractability. Mitigate by using a computationally cheap, full-column pass first (e.g. a single tree model's feature importances, or per-column mutual information against the target computed at scale) purely to catch anything wildly informative before finalizing the shortlist, rather than relying on domain knowledge alone to pick it.

### Q10 — What's the difference between an outlier that should be removed and one that shouldn't, and how does EDA help you tell them apart?
**Answer:** A removable outlier is typically a data error (a sentinel value, a unit-conversion mistake, a duplicated or corrupted row) that doesn't represent a real underlying phenomenon. A keepable "outlier" is a legitimate extreme value that's part of the real data-generating process — in fraud, medical, and safety domains, these are frequently the exact minority-class examples the model exists to catch. EDA helps by cross-referencing flagged outliers against the target: if IQR-flagged points are disproportionately the positive class, they're signal, not noise, and removing them would gut the model's ability to learn the thing you're trying to detect.
**Follow-up trap:** *"Your IQR filter flags 2% of rows as outliers, and none of them correlate with the target at all. Safe to drop?"* — safer, but check one more thing: whether those rows are outliers on a feature you were planning to use, versus outliers that would only matter for a feature you haven't engineered yet. A currently-uncorrelated-looking extreme value can become meaningful once you build the right derived feature (a ratio, an interaction) — dropping early can foreclose feature engineering you haven't done yet. This is a judgment call, not a mechanical one.

### Q11 — How would you EDA a dataset for train-serving skew before you've even trained a model?
**Answer:** Compare the distribution of every feature between the training snapshot and the most recent production data you can access (a tool like `sweetviz`'s comparison report does this directly) — differences in mean, skew, missingness rate, or category vocabulary between train and current-production data predict exactly the kind of silent degradation that shows up weeks after deployment. This is EDA applied to the *pipeline*, not just the dataset, and it's the check most commonly skipped because it requires access to live data before a model even exists to evaluate.
**Follow-up trap:** *"What's the specific failure this catches that a normal offline train/test split evaluation misses?"* — a train/test split from the same historical snapshot can't detect that the world has moved on since that snapshot was collected; a model can have excellent, honest offline test performance and still degrade in production purely because the feature distributions shifted between when the training data was collected and when the model actually serves traffic. Comparing training data against current production data is the only way to catch that before it costs you in production.

---

## Red flags that fail you

- Running `df.corr()` (Pearson only) and treating a low correlation as "no relationship."
- Applying z-score outlier detection without checking skew first.
- Doing the leakage hunt as an afterthought, or not at all.
- Treating an automated profiling report as a complete EDA.
- Not knowing accuracy is meaningless under severe class imbalance.
- Dropping every IQR-flagged point without checking its relationship to the target.
- Citing Anscombe's Quartet or the Datasaurus Dozen incorrectly, or not being able to explain what they demonstrate.
- No answer for how to scale EDA down when the dataset is too large to profile in full.

---

## Cheat card

```
ORDER    1 grain/shape -> 2 per-column (dtype, missingness, skew, cardinality) ->
         3 relationships (Pearson AND Spearman) -> 4 vs target (binned mean, class balance) ->
         5 leakage + imbalance hunt LAST (need stages 1-4 to know what "suspicious" means)

SKEW     scipy.stats.skew(); |skew| > 1 ~ substantially skewed -> consider log1p / Box-Cox
         mean > median = right-skewed (income, latency, transaction amount — bounded at 0, long tail)

CORRELATION
  Pearson    measures LINEAR fit strength only. y=x^3 can show near-zero Pearson r.
  Spearman   rank-based -> captures any MONOTONIC relationship, linear or not
  large Spearman - Pearson gap -> plot the scatter; usually nonlinear-monotonic OR one outlier

ANSCOMBE / DATASAURUS   identical mean/var/Pearson r, wildly different scatter shapes
  -> NEVER trust a correlation number without plotting the flagged pairs

OUTLIERS
  z-score      |x-mean|/std > 3. FAILS on skew: mean pulled by tail, std inflated by
               the very points you're hunting -> under- AND over-flags simultaneously
  IQR          Q1-1.5*IQR to Q3+1.5*IQR. Robust default for skewed real-world data (median/
               quartiles have bounded influence — one extreme point can't move them much)
  modified z   0.6745*(x-median)/MAD, threshold ~3.5 — robust z-score alternative

CLASS IMBALANCE   99:1 -> accuracy meaningless (constant classifier scores 99%). Stratify
                  splits. Use PR-AUC/F1/recall, not accuracy or plain ROC-AUC.

LEAKAGE CHECK    corrwith(target) for implausibly high correlation (not proof alone) +
                 groupby(feature.isna())[target].mean() (does missingness pattern leak) +
                 the ONLY real test: "could this value exist, in this form, at prediction time?"

OUTLIER JUDGMENT    cross-reference flagged outliers against target — in fraud/medical/safety
                    domains, "outliers" are often exactly the minority class you need to keep

SCALE DOWN    500 cols x 50M rows -> sample rows first (compute scales with rows more than
              precision does), shortlist columns via cheap full-pass importance/MI before
              full O(p^2) correlation on everything
```

## Sources

- [A comparison of the Pearson and Spearman correlation methods — Minitab](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/supporting-topics/correlation-and-covariance/a-comparison-of-the-pearson-and-spearman-correlation-methods/) — accessed 2026-08-01
- [Myths About Linear and Monotonic Associations: Pearson's r, Spearman's ρ, and Kendall's τ](https://www.tandfonline.com/doi/full/10.1080/00031305.2021.2004922) — accessed 2026-08-01
- [Outlier Detection and Treatment: Z-score, IQR, and Robust Methods](https://medium.com/@aakash013/outlier-detection-treatment-z-score-iqr-and-robust-methods-398c99450ff3) — accessed 2026-08-01
- [3 Simple Statistical Methods for Outlier Detection — Towards Data Science](https://towardsdatascience.com/3-simple-statistical-methods-for-outlier-detection-db762e86cd9d/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
