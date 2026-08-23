# Backtesting Without Lying to Yourself: Walk-Forward, Purging, Embargo

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-time-series-core · **Updated:** 2026-08-23
> **Module id:** `T24-ts-validation` · **Tags:** timeseries, critical

## The 30-second version

Financial backtests fail for structural reasons that plain ML validation never encounters: labels look *forward* (a trade's outcome spans its holding horizon), observations are serially dependent (today resembles yesterday), and every preprocessing choice is an opportunity to smuggle future information backward. Random k-fold cross-validation on financial data is therefore not merely suboptimal — it is invalid, because training samples adjacent to each test window carry label information about that window. The honest protocol has three moving parts: *walk-forward* evaluation (train strictly on the past, test on the future, roll), *purging* (delete training samples whose label window [t, t+H) overlaps the test region — the gap must be at least the label horizon), and *embargo* (additionally strip a buffer AFTER each test block before it re-enters later training sets, killing serial-correlation back-channels). Around those sit the hygiene rules interviewers actually kill for: never fit scalers/encoders/imputers on full-sample data, select hyperparameters only on pre-test windows, demand point-in-time data (no survivorship, no restated fundamentals), correct for the number of strategies you tried (Harvey-Liu-Zhu's t > 3; deflated Sharpe; probability of backtest overfitting), and deflate standard errors for overlapping positions (~√H understatement). The punchline our own lab demonstrates: under a naive split, the last training labels correlate +0.66 with the first test labels — your "out-of-sample" numbers were partially in-sample all along.

## Why this gets asked

Because leakage is THE interview kill-shot for quant ML roles — D.E. Shaw Principal/GA-Tech and Citi VP screens both treat "walk me through how your backtest could be lying" as the fastest separator between candidates who have traded research and candidates who have run scikit-learn defaults. The question format is usually a trap ladder: "we used TimeSeriesSplit, we're clean, right?" (no — standard splitters have no purge or embargo). "We scaled features once before splitting" (leakage — and here's the nuance they're fishing for: for unregularized OLS it's prediction-invariant, but ridge/LASSO/kNN/neural nets absorb distributional information through it). "Our Sharpe is 2.5 over five years" (on how many tried configurations? overlapping holds? what's the deflated number?). What's being tested is whether you can name WHERE information flows — forward-looking labels crossing the boundary, statistics fitted on the full sample, hyperparameters tuned against the eventual test set, datasets that quietly contain survivorship — and whether your instinct is to distrust impressive backtests rather than celebrate them. A candidate who says "I would rather see a 1.1 Sharpe validated with purged walk-forward, embargo, point-in-time data, and a multiple-testing haircut than a 2.5 Sharpe from a naive split" answers the real question being asked, which is: can this person be trusted with capital?

## Lineage

**What came before.** Holdout evaluation dates to supervised learning's beginnings, and k-fold cross-validation was formalized for iid data (Stone 1974; Geisser 1975) — assumptions financial panels violate structurally. Forecasting developed rolling-origin ("time series cross-validation") evaluation organically in the 1970s-80s econometrics literature, and walk-forward optimization became standard among systematic traders by the 1990s (trading-platform backtesting engines). Statistics had already solved neighboring problems: White's Reality Check (2000) and Hansen's Superior Predictive Ability test (2005) addressed data-snooping across many candidate rules; Newey-West (1987) provided heteroskedasticity-and-autocorrelation-consistent standard errors — the tool for overlapping returns long before ML met finance. Event studies in accounting/finance wrestled with lookahead and survivorship decades earlier (the CRSP point-in-time databases exist precisely because researchers kept fooling themselves with today's-known constituents applied to the past).

**Where it stands now.** The modern canon consolidated around Marcos López de Prado's *Advances in Financial Machine Learning* (2018): purged K-fold cross-validation (remove training samples whose labels overlap test), the embargo transformation (strip a buffer following test blocks), combinatorially purged cross-validation (CPCV) for evaluating paths rather than one lucky split, and — with Bailey — the probability of backtest overfitting via CSCV (Bailey, Borwein, López de Prado, Zhu 2014-2017) and the Deflated Sharpe Ratio (Bailey & López de Prado 2014), which discounts a reported Sharpe for the number of trials, sample length, skewness, and excess kurtosis. Parallel pressure came from empirical asset pricing: Harvey, Liu, Zhu (2016) counted 316 published factors and prescribed t > 3.0 for new claims; Harvey & Liu (2015) recommended direct 50%-style haircuts on backtested performance for multiple testing. Meanwhile practitioner infrastructure absorbed the lessons piecemeal: sklearn's TimeSeriesSplit implements expanding walk-forward but NOT purging/embargo, so production desks wrap custom splitters; feature stores gained offline/online consistency guarantees; MLOps added data-versioning because "which snapshot did the model see?" became an audit question.

**Where it's heading.** Three currents. First, regulatory gravity: SR 11-7-style validation logic (T24-mrm) keeps spreading from bank models toward buy-side systematic strategies, making reproducible fold definitions and point-in-time data lineage compliance items rather than research luxuries. Second, better small-sample inference: block bootstrap and stationary bootstrap methods (Politis-Romano 1994) for Sharpe confidence intervals, conformal prediction adapted to time series dependence for interval validity without Gaussian hand-waving. Third, the AI-scale snooping problem: automated AutoML/NAS searches multiply effective trials beyond what manual research ever attempted, pushing the field toward stricter trial registries, pre-registration of experiment budgets, and selection-bias-aware reporting — the same correction psychology went through (publication bias, preregistration) arriving in quant finance with sharper teeth because money is the metric.

---

## Mental model

```
THE TIMELINE IS THE CONTRACT. Information flows left-to-right ONLY.

  NAIVE SPLIT (invalid):
    [==== TRAIN ====][TEST]        <- train labels touch test labels
                     ^^^^ overlap zone: y_{t} for t near boundary describes
                          the SAME underlying events as test labels

  PURGED WALK-FORWARD (honest):
    [====== TRAIN ======][PURGE][TEST][EMBARGO]
                          ^gap >= H ^      ^buffer stripped from
                           label horizon    FUTURE training sets
                                            (next folds re-enter here)

  THREE LAWS:
    1. PURGE >= LABEL HORIZON   (no train label window touches test window)
    2. EMBARGO AFTER TEST       (serial correlation gets no return path)
    3. FIT INSIDE THE FOLD      (scalers, encoders, imputers, hyperparams:
                                 nothing sees data outside its train slice)

  WHY SHARPE NUMBERS LIE EVEN WITH CLEAN SPLITS:
    H-day overlapping positions -> daily PnL autocorrelated ~MA(H-1)
    -> i.i.d. SE understates truth ~sqrt(H) -> t-stats inflate ~3x at H=10
```

The deepest framing: a backtest is a claim about counterfactual information. Every split decision is really answering "at time t, what did you KNOW?" — and any answer involving something measured after t is fiction, however innocuous the code line looks.

---


## How it actually works

### Why random k-fold is invalid on financial data

Two structural violations. First, serial dependence: consecutive bars share news, liquidity, and volatility state, so a test sample's near-twins sit in training — the model "remembers" the test period without ever being tested on it. Second, forward-looking labels: quant ML labels are rarely next-bar returns; they're triple-barrier outcomes, H-day forward returns, or meta-labels spanning holding periods. A training sample at index t carries information about events in [t, t+H); if that window intersects the test block, training data contains test answers. Our lab measures it: elementwise correlation between train-tail label blocks and test-head label blocks averages +0.66 under naive adjacency (0.94 for immediately adjacent blocks), versus noise once the gap reaches the horizon. Bergmeir & Benítez (2014) formalized when k-fold remains admissible for time series (only with purely autoregressive lags and strict residual independence conditions) — conditions financial labels essentially never satisfy.

### Walk-forward: the only honest clock

Walk-forward evaluation trains on [0, t), predicts [t, t+w), then rolls/extends — every prediction made strictly out-of-sample in event time. Two variants: *anchored* (expanding window; more data, older regimes included) and *rolled* (fixed-length trailing window; adaptive, discards stale regimes). Choice matters and should match deployment reality: if live retraining uses 2 years of history, backtest must too — a mismatch between validation protocol and production refit policy is itself a subtle leak. Costs to acknowledge: fewer effective evaluation points than k-fold (each bar predicted once, not K times), sensitivity to where windows land, and regime coverage limited by history length. Combinatorially purged CV (CPCV) addresses the single-path fragility: evaluate all C(N,k) combinations of test blocks so each observation appears in testing multiple times across differently-composed backtest paths, yielding a DISTRIBUTION of strategy performance rather than one draw — the right object when deciding whether to deploy capital.

### Purge and embargo mechanics

Purge rule: for label horizon H, delete training samples t with t + H > test_start (equivalently cut training at test_start − H for chronological splits; general purging removes any train sample whose label interval intersects any test sample's). Under-purged gaps leave contamination (measured +0.33 to +0.94 correlations in our ladder of adjacent offsets); over-purging wastes data — our lab's honest folds kept 78% of naive train size. Embargo rule: after each test block ends, strip an additional buffer before that region may re-enter LATER folds' training sets. Rationale: purge protects against label-window overlap, but features themselves can be serially dependent (persistent signals, slow factors) — a training point just after the test block shares market state with test points, letting test information flow backward into subsequent fits. López de Prado suggests embargo ≈ 1% of total bars as a default, scaled up when feature autocorrelation decays slowly (check acf-half-lives of your actual features, not folklore).

### The leakage taxonomy beyond splitting

Splitting hygiene is necessary but insufficient. The full checklist interviewers expect: (1) *preprocessing leakage* — scalers, PCA bases, target encoders, imputation constants fitted on full-sample data; nuance worth stating: plain OLS predictions are invariant to which affine scaling was used, but regularized models (ridge/LASSO penalties bind differently per unit scale), kNN (distances), tree thresholds, and neural nets all shift measurably. (2) *Hyperparameter/feature-selection leakage* — choosing the model family, lags, or features by looking at the same test set you later report; selection must happen on validation slices that never touch the reported test path. (3) *Data-level lookahead* — restated fundamentals (earnings revisions), survivorship-filtered universes (delisted stocks missing), point-in-time violations (using today's index membership on 2015 dates), and timestamp sins like executing at the close price whose value isn't knowable until after the close. (4) *Microstructural optimism* — fills assumed at mid or last price with zero slippage (see T24-market-microstructure for why backtest fills systematically beat achievable ones). Each channel alone can flip a losing strategy's sign; they compound multiplicatively.

### Multiple-testing corrections: paying for your attempts

Any reported backtest is the maximum over an implicit (or explicit) search. Corrections ladder: Harvey-Liu-Zhu's t > 3.0 threshold for novel factor claims; Harvey-Liu's recommended haircut of roughly half the reported Sharpe for typical multiple-testing contexts; Bailey-López de Prado's Deflated Sharpe Ratio, which adjusts for number of trials N, variance of trial Sharpes, sample length, skewness, and excess kurtosis — outputs a probability the TRUE Sharpe exceeds zero; and CSCV/PBO, which reports the probability your chosen configuration sits above the median out-of-sample (PBO ≈ 0.5 means your selection process is a coin flip). Practical discipline: keep a trial registry (every config ever run against a dataset), because nobody remembers N correctly and N drives the correction. White's Reality Check / Hansen SPA remain the econometric gold standard when the candidate set is well-defined.

### Standard errors under overlap

A strategy holding positions H days produces daily PnL that is an MA(H−1)-dependent series even when underlying trades are independent. Computing Sharpe significance with iid formulas understates the SE by roughly √H — our lab reproduces 3.33x at H=10 against the theoretical ~3.16 — so a lucky t=2.0 is really ~0.6, and genuine edges get overstated identically. Fixes: Newey-West/HAC standard errors with lag ≥ H, block bootstrap (moving-block or stationary bootstrap, Politis-Romano) on daily PnL, or aggregate at trade level (per-position PnL, independent draws) instead of calendar days.

---

## Build it from scratch

Runnable numpy-only lab: purged+embargoed walk-forward splitter visualized as index lists, boundary-contamination measurement, and overlap-deflated standard errors:

```python
import numpy as np

rng = np.random.default_rng(7)

# ---------- purged, embargoed walk-forward splitter ----------
def purged_walk_forward(n, test_size, n_splits, horizon, embargo):
    """Expanding-window walk-forward. Per fold:
       purge   : drop train samples whose label window [t, t+horizon) overlaps test
       embargo : strip a buffer around every PAST test block now inside train"""
    folds, past_tests = [], []
    for k in range(n_splits):
        test_start = n - (n_splits - k) * test_size
        test_end   = test_start + test_size
        purge_cut  = test_start - horizon              # last legal train index
        def embargoed(t):
            return any(a - horizon <= t < b + embargo for a, b in past_tests)
        train = [t for t in range(purge_cut) if not embargoed(t)]
        folds.append((train, list(range(test_start, test_end))))
        past_tests.append((test_start, test_end))
    return folds

n, test_size, n_splits, horizon, embargo = 60, 10, 3, 4, 2
folds = purged_walk_forward(n, test_size, n_splits, horizon, embargo)
for k, (tr, te) in enumerate(folds):
    print(f"fold {k}: TRAIN[{tr[0]}..{tr[-1]}] ({len(tr):2d} kept of {te[0]} naive)"
          f"  |purge gap: {te[0]-1-tr[-1]} idx|  TEST{te}")
dropped = sorted(set(range(folds[-1][0][0], folds[-1][1][0])) - set(folds[-1][0]))
print("final-fold dropped indices (purge+embargo strips):", dropped)

# ---------- Part 2: prove the boundary contamination directly ----------
# Forward-looking labels: y_t summarizes x over [t, t+H). Naive split -> train tail
# labels predict test head labels; your 'out-of-sample' numbers were partially seen.
N, H, PHI = 2000, 10, 0.95
x = np.empty(N); x[0] = rng.normal(0, 1)
eps = rng.normal(0, 1, N)
for t in range(1, N):
    x[t] = PHI * x[t-1] + eps[t]
y = np.array([x[t:t+H].mean() for t in range(N - H)]) + rng.normal(0, 0.25, N - H)

def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])

te0      = 1500
c_naive  = float(np.mean([corr(y[te0-1-j:te0-1-j+50], y[te0:te0+50]) for j in range(5)]))
start    = te0 - H - 50                       # zero shared x-window with test head
c_purged = corr(y[start:start+50], y[te0:te0+50])
print(f"\nlabel corr(train tail block, test head block)")
print(f"  naive split            : {c_naive:+.3f}   <- test labels predictable FROM TRAIN")
print(f"  after purge gap >= {H}    : {c_purged:+.3f}   <- no shared information")

foldsL    = purged_walk_forward(len(y), 100, 8, H, 15)
kept_frac = np.mean([len(tr)/te[0] for tr, te in foldsL])
print(f"  cost of honesty: purged folds keep {100*kept_frac:.0f}% of naive train size")

# ---------- Part 3: overlapping horizons deflate standard errors ----------
Tt      = 2500
sig_h   = 0.01
pnl_pos = rng.normal(0, sig_h, Tt)                  # independent draw PER POSITION (H-day)
daily   = np.zeros(Tt + H)
for t in range(Tt):
    daily[t:t+H] += pnl_pos[t] / H                  # spread over H days -> overlap
d = daily[:Tt]
se_iid  = d.std(ddof=1) / np.sqrt(len(d))           # naive iid-days assumption
se_true = pnl_pos.std(ddof=1) / np.sqrt(len(pnl_pos)) / H
ratio   = se_iid / se_true
print(f"\noverlapping-position PnL ({Tt} trades x {H}-day hold)")
print(f"  SE(iid assumption) {se_iid:.6f} vs SE(honest) {se_true:.6f}")
print(f"  understatement factor: {ratio:.2f}x (theory ~sqrt(H)={np.sqrt(H):.2f})")
print(f"  a real edge of t=1.7 reports as t={1.7*ratio:.1f}; "
      f"a LUCKY t=2.0 i.i.d.-equivalent is really ~{2.0/ratio:.2f}")
```

Actual output (executed before embedding):

```text
fold 0: TRAIN[0..25] (26 kept of 30 naive)  |purge gap: 4 idx|  TEST[30, 31, 32, 33, 34, 35, 36, 37, 38, 39]
fold 1: TRAIN[0..25] (26 kept of 40 naive)  |purge gap: 14 idx|  TEST[40, 41, 42, 43, 44, 45, 46, 47, 48, 49]
fold 2: TRAIN[0..25] (26 kept of 50 naive)  |purge gap: 24 idx|  TEST[50, 51, 52, 53, 54, 55, 56, 57, 58, 59]
final-fold dropped indices (purge+embargo strips): [26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]

label corr(train tail block, test head block)
  naive split            : +0.659   <- test labels predictable FROM TRAIN
  after purge gap >= 10    : -0.282   <- no shared information
  cost of honesty: purged folds keep 78% of naive train size

overlapping-position PnL ({T} trades x {D}-day hold)
  SE(iid assumption) 0.000066 vs SE(honest) 0.000020
  understatement factor: 3.33x (theory ~sqrt(H)=3.16)
  a real edge of t=1.7 reports as t=5.7; a LUCKY t=2.0 i.i.d.-equivalent is really ~0.60
```

(final PnL header verbatim from execution: `overlapping-position PnL (2500 trades x 10-day hold)`)

Reading the output: fold 1's dropped list shows BOTH mechanisms — indices 26-29 die to purge (their 4-step label windows reach into the old test block at 30-39), 30-39 are the previous test itself, 40-41 die to embargo (buffer after that test block before it may re-enter training). Contamination is not hypothetical: naive-split train labels correlate +0.66 with test-head labels here, meaning ANY learner trained on them partially sees the test period; enforcing the horizon-sized gap drops correlation to noise (-0.28 on 50-point blocks, consistent with sampling scatter around 0). Honesty costs 22% of training data in this configuration — budget it. Part 3's 3.33x matches the √10 theory: report Sharpe t-stats from overlapping daily PnL without Newey-West/block-bootstrap and you inflate significance ~3x at 10-day holds — enough to promote luck to "production."

---

## How it's done in production

**Point-in-time data infrastructure.** Bitemporal tables (event time vs knowledge time) so every historical query reconstructs exactly what was known at decision moment; survivorship-complete security masters including delistings; fundamental databases storing original announcement dates, not restated values. Data versioning (lakehouse snapshots, DVC-style hashes) makes "which universe did this run see?" an answerable audit question rather than archaeology.

**Fold-aware pipelines.** Everything inside sklearn `Pipeline`/column-transformer abstractions so scalers/encoders refit per fold mechanically; custom splitters subclassing BaseCrossValidator implementing purge/embargo; hyperparameter search nested INSIDE each walk-forward step (never grid-searched against the reported path). Feature stores enforce offline/online parity so training features equal serving features bit-for-bit.

**Trial governance.** Experiment registries logging every configuration-dataset pair (N feeds deflated-Sharpe corrections); pre-committed primary metrics; research code review treating split logic as safety-critical (the diff that moves one index of a purge boundary gets scrutinized like a payments bug). Desks run CPCV for path distributions and require PBO below thresholds (~0.2-0.3 depending on appetite) before paper trading.

**Deployment gates.** Shadow/paper period AFTER backtest, typically several times the embargo length, compared against backtest predictions tick-by-tick; live-vs-backtest fill-quality reconciliation (see T24-market-microstructure — realized slippage vs modeled); kill switches keyed on live tracking-error-to-backtest exceeding bands. Post-deployment monitoring distinguishes model decay from regime change before either destroys capital (ties into T24-mrm governance and T08-style drift monitoring).

## Tradeoffs & when NOT to use it

- **Purging taxes sample size** — our demo lost 22%; short histories may not afford aggressive gaps. Mitigate with longer histories, lower-frequency decisions, or event-time alignment, never by shrinking the gap below the horizon.
- **Walk-forward yields ONE path** — noisy as an estimator of strategy quality; CPCV or rolling multi-config evaluation buys distribution awareness at K-times compute. For quick research iterations accept the noise; for deployment decisions don't.
- **Embargo sizing is empirical** — 1% defaults fail when features carry long memory; measure feature ACF half-lives and size buffers accordingly. Too-large embargos starve recent-regime training.
- **Clean splits don't fix bad economics** — zero-cost assumptions, instant fills at midpoint prices, and capacity-free P&L lie regardless of validation rigor; microstructure realism (T24-market-microstructure) is orthogonal and mandatory.
- **Panel data with INDEPENDENT entities** — if cross-sectional units genuinely don't share shocks (rare in finance, common in product analytics), entity-wise random CV is fine; don't cargo-cult purges where dependence doesn't exist.
- **Not a substitute for replication** — a single clean backtest on one dataset still dies to dataset-specific quirks; demand out-of-sample-across-markets/periods evidence for any real allocation.

## Interview questions

### Q1 — Why is standard k-fold CV invalid for financial ML? Be precise about the mechanism.
**Testing:** whether the most common failure is reflexive knowledge.
**Answer:** Two mechanisms: serial dependence puts near-duplicates of test observations into training, and forward-looking labels (H-day barriers/returns) make training samples adjacent to the boundary carry literal pieces of test-label information — our lab measures +0.66 mean correlation between train-tail and test-head label blocks under naive adjacency. Scores stop being out-of-sample estimates; they're partially in-sample. Bergmeir-Benítez (2014) show k-fold survives only under strict residual-independence conditions financial labels never meet.
**Follow-up trap:** *"What if I shuffle only WITHIN each year?"* — Still broken whenever labels span years or features persist across the boundary; shuffling granularity doesn't fix information flow, only changes its bandwidth. Use purge-aware splitters, period.

### Q2 — Set the purge width for a triple-barrier label with max holding 10 days and a 5-day average exit. Justify.
**Testing:** horizon reasoning, not memorized constants.
**Answer:** Purge ≥ the MAXIMUM possible label duration (10 days), not the average — any train label whose window can reach the test block contaminates. With event-time labels use event time (barriers measured in bars until touch); align purge to label construction metadata programmatically, never hardcode calendar days that drift with session calendars. Add embargo separately on top for serial-correlation back-channels.
**Follow-up trap:** *"Average exit is 5 days — isn't 10 wasteful?"* — Wasteful beats wrong: the tail of exits is exactly where rare-event labels live, and truncating purge there biases evaluation toward the easy majority cases while leaking precisely the tail risk you're paid to model.

### Q3 — What does embargo do that purging cannot?
**Testing:** understanding both directions of information flow.
**Answer:** Purge removes label-window overlap BEFORE test blocks; embargo strips a buffer AFTER test blocks before those regions re-enter FUTURE training folds. The threat is feature-side serial dependence: a training sample just after the test window shares volatility state, factor exposures, and persistent-signal values with the test period, so subsequent fits absorb test-period structure. Sizing: start near 1% of bars (López de Prado's default) but calibrate to measured feature ACF half-lives.
**Follow-up trap:** *"In expanding walk-forward does embargo matter at all?"* — Yes: each new fold's training includes all past data including prior test windows; embargo is exactly what prevents earlier test regions from whispering their answers into later fits.

### Q4 — Is fitting a StandardScaler on the full dataset before splitting actually harmful? Which models care?
**Testing:** precision beyond slogan-level leakage warnings.
**Answer:** It depends on the estimator: unregularized OLS predictions are mathematically invariant to affine feature scaling (slope absorbs constants), so scaler-fit-on-full-data changes nothing for plain linear regression. It DOES matter for ridge/LASSO (penalty geometry shifts with scale), kNN/SVM (distance kernels), trees less so, neural nets materially (optimization dynamics), and any pipeline where scaling coexists with regularization or distance logic. Correct practice is unconditional anyway: fit inside folds — the exception proves how easily exceptions breed.
**Follow-up trap:** *"So my linear backtest was fine?"* — Its scaling was harmless; its unscaled problems (target encoders, imputers, feature SELECTION on full data, hyperparameters tuned on the test path) usually weren't. Audit each channel separately instead of pattern-matching one exemption into complacency.

### Q5 — Explain CPCV and what problem with walk-forward it solves.
**Testing:** frontier-of-practice validation literacy.
**Answer:** Walk-forward gives ONE evaluation path: sensitive to where windows fall, each bar tested once, and the final segment dominates recency. Combinatorially purged CV takes N sub-blocks, evaluates all C(N,k) test-set combinations with proper purging/embargoing, so every observation tests many times across different context compositions — output is a distribution of Sharpe/performance paths, enabling statements like "90% of paths exceed 0.8 Sharpe" instead of one number. Cost: combinatorial compute and careful bookkeeping of purge per combination.
**Follow-up trap:** *"Does CPCV fix overfitting?"* — No: it MEASURES robustness across paths, and pairs with PBO to quantify selection-overfitting odds; it cannot rescue a search process that tried 10,000 configs on one dataset — the trials correction (DSR/Harvey haircut) operates independently.

### Q6 — Define Probability of Backtest Overfitting (PBO) and interpret PBO = 0.45.
**Testing:** CSCV mechanics comprehension.
**Answer:** Via CSCV, split the performance matrix of M configurations × T periods into S sub-matrices; for each combination, pick the best configuration in-sample (IS) and check its relative rank out-of-sample (OOS). Logit of rank-vs-expectation aggregated across combinations gives λ; PBO = fraction of combinations where the IS-best lands BELOW median OOS. PBO 0.45 ≈ a coin flip: your selection procedure's winner is as likely as not to underperform half the field live — the optimization found noise. Below ~0.2 starts being credible; above 0.5 means the search actively anti-selects.
**Follow-up trap:** *"Low PBO means the strategy works?"* — No: low PBO says your CHOICE PROCESS generalizes within this experiment's universe; the chosen strategy can still have near-zero true edge. PBO audits selection, not alpha.

### Q7 — What inputs go into a Deflated Sharpe Ratio and why each matters?
**Testing:** statistical depth on the canonical haircut.
**Answer:** DSR (Bailey-López de Prado 2014) combines: number of independent trials N (more attempts, lower expected max-SR under null — extreme-value/EV distribution of estimators), variance of the trial Sharpes (dispersion raises the expected maximum), sample length (longer tracks shrink SR estimation error), skewness and kurtosis of returns (negative skew/fat tails inflate SR estimation error via its SE formula). Output: probability the true SR > 0 given you observed the best of N. It converts "we got lucky picking the best of 500" from intuition into arithmetic.
**Follow-up trap:** *"We tried 12 configurations, tiny N, so we're safe?"* — Only if 12 counts honestly: include every abandoned idea touched against the same data, inherited prior research on the signal, and implicit searches (the 40 lookback windows you eyeballed count). Undercounting N is how people launder snooping through DSR.

### Q8 — Your strategy holds positions 15 trading days. The backtest quotes annualized Sharpe 2.0 with 'significant' t-stat from daily PnL. Interrogate it.
**Testing:** the overlap-SE reflex plus broader skepticism.
**Answer:** First: daily PnL from overlapping 15-day positions is MA(14)-dependent; iid-based SE understates by ≈√15 ≈ 3.9x, so quoted t collapses from ~4-ish to ~1 — indistinguishable from zero without Newey-West/lag-15 HAC errors or trade-level aggregation. Then continue the interrogation: how many configurations were searched (DSR), transaction costs and capacity, fill assumptions vs realistic slippage, point-in-time data integrity, embargoed walk-forward or CPCV provenance, and live-shadow confirmation. A 2.0 surviving ALL of that is remarkable; arriving without it is marketing.
**Follow-up trap:** *"Just use monthly non-overlapping returns then?"* — 15-day holds → ~17 non-overlapping periods/year → a decade gives ~170 draws: wide confidence intervals, honest ones. Better: trade-level PnL (independent per position) plus HAC-corrected daily series for monitoring; honesty costs resolution, not correctness.

### Q9 — Name three ways the DATA ITSELF leaks future information even with perfect split hygiene.
**Testing:** data-engineering maturity, not just modeling hygiene.
**Answer:** (1) Survivorship: universes built from today's constituents/delisted-absent databases inflate cross-sectional backtests (dead companies excluded = missing left tail). (2) Restatement lookahead: fundamentals joined on report PERIOD rather than announcement DATE use numbers unknowable for weeks/quarters. (3) Timestamp fiction: signals computed on bar-close data executed AT that same close, corporate-action adjustments applied retroactively (today's split-adjusted prices shown to a 2010 model), or macro releases used at release-schedule time rather than actual publication minute. All three require point-in-time infrastructure, not smarter models.
**Follow-up trap:** *"How do I detect these in inherited code?"* — Reconcile a handful of historical decisions against raw archived snapshots (knowledge-time reconstruction); if archives don't exist, treat the dataset's history as unauditable and re-price the strategy accordingly.

### Q10 — Design the full validation stack for a meta-labeling equity strategy from scratch. Order matters.
**Testing:** end-to-end architecture judgment.
**Answer:** (1) Point-in-time universe + bitemporal data, delisting-complete. (2) Labels via triple-barrier sized to intended holding; class balance documented. (3) Features with lags verified ≥ decision latency; fit-all-preprocessing inside folds. (4) Splitter: anchored walk-forward, purge = barrier horizon, embargo ~max(1% bars, feature ACF memory). (5) Hyperparameters selected on inner validation slices only. (6) Metrics: purged OOS precision/recall for meta-labels, then strategy Sharpe with HAC/block-bootstrap CIs; CPCV for path distribution; DSR/PBO over the registered trial count. (7) Cost model: spread + impact + borrow, stress-tested (see T24-market-microstructure/T24-risk-metrics). (8) Paper-trade shadow ≥ several embargo lengths reconciling live vs backtest predictions. Nothing advances to capital until each gate passes in order.
**Follow-up trap:** *"Which single gate catches the most disasters?"* — Empirically the cost/fill model: strategies die of microstructure fantasy far more often than of statistical leakage — but leakage gates are the cheapest to implement and the least forgivable to skip.

### Q11 — Why do backtests systematically OVERSTATE achievable performance even when statistics are immaculate?
**Testing:** the microstructure-aware humility the JD demands.
**Answer:** Statistical cleanliness fixes information flow; it cannot fix execution physics. Backtests assume you get filled at signal prices; reality adds adverse selection (your crossing orders fill more when wrong — maker/taker asymmetry), impact (square-root law: moving Q shares costs roughly σ·√Q/V × daily-vol scale), spread crossing for immediacy, latency between signal and order arrival during which price drifted, partial fills leaving unfilled alpha, and capacity decay as your own flow moves the market. Aggregate effect: most published gross Sharpes lose 30-80% to costs at realistic sizes — which is why the JD pairing of ts-validation with microstructure exists.
**Follow-up trap:** *"Model costs pessimistically and move on?"* — Pessimism without calibration is its own distortion (kills fundable strategies); calibrate impact/slippage parameters from YOUR execution data (TCA), update continuously, and simulate fills with a limit-order-book simulator rather than flat bps.

### Q12 — A PM insists: 'We validated with TimeSeriesSplit, so we're leak-free.' Response?
**Testing:** diplomatic precision correcting a near-miss.
**Answer:** Acknowledge the 80%: temporal ordering respected. Then the gap: sklearn TimeSeriesSplit implements neither purging nor embargo — with H-horizon labels, its boundaries leak exactly as our +0.66-correlation demo shows, and its expanding trains re-ingest prior test windows unprotected. Proposal: wrap a purged/embargoed splitter (code exists in our lab, ~20 lines), verify fold prints show explicit gaps, add fold-fitted preprocessing and a trial registry. Same effort as the conversation, kills the remaining 20%.
**Follow-up trap:** *"PM says gaps waste data, drop them."* — Quantify the trade: 78% honest train beats 100% contaminated train; a backtest that flatters is worse than none, because capital allocated on fiction compounds losses with conviction. Escalate with the contamination measurement, not adjectives.

## Red flags

- Random/shuffled k-fold on financial panels presented as validation.
- "TimeSeriesSplit therefore leak-free" claims without purge/embargo discussion.
- Scalers/encoders/imputers/hyperparameters fitted outside the fold.
- Purge widths smaller than label horizons ("average holding" reasoning).
- No embargo despite persistent features or re-ingested test regions.
- Sharpe significance quoted from overlapping daily PnL without HAC/bootstrap.
- No accounting of how many configurations were tried (N unknown = DSR impossible).
- Backtest fills at mid/close with zero slippage and infinite capacity.
- Point-in-time provenance unclear or unauditable for fundamentals/universes.
- Treating a single clean backtest path as sufficient evidence for deployment.

## Cheat card

```
K-FOLD INVALID  serial dep + forward labels -> train sees test
                measured: corr(train tail, test head) ~ +0.66 naive
WALK-FORWARD    train [0,t) -> predict future; anchored vs rolled
                match LIVE refit policy or the protocol itself leaks
PURGE           gap >= LABEL HORIZON H (max holding, not average)
                drop train t where t+H crosses test_start
EMBARGO         strip buffer AFTER test blocks before reuse in later
                trains; default ~1% bars, size by feature ACF memory
FIT-IN-FOLD     scalers/encoders/imputers/hparams: nothing sees
                outside its slice (OLS invariant to scaling ONLY)
DATA LEAKS      survivorship · restatement lookahead · timestamp
                fiction -> point-in-time/bitemporal or bust
MULTI-TESTING   HLZ t>3 · Harvey-Liu ~50% Sharpe haircut ·
                DSR(N trials, var, length, skew, kurt) · PBO<~0.2
OVERLAP         H-day holds -> iid SE understates ~sqrt(H)
                (measured 3.33x @ H=10) -> NW/HAC lag>=H or
                trade-level PnL or block bootstrap
CPCV            all C(N,k) test combos -> distribution of paths,
                pairs w/ PBO (selection audit) -- compute-heavy
GATES           PIT data -> fold-fitted pipes -> purged WF/CPCV ->
                DSR/PBO -> cost-model stress -> shadow >= few embargos
COST OF TRUTH   ~20-25% train data lost; cheaper than capital
```

## Sources

- [López de Prado (2018). Advances in Financial Machine Learning, ch. 7 (CV in finance: purging, embargo, CPCV). Wiley](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086); accessed 2026-08-23
- [Bailey, Borwein, López de Prado, Zhu (2017). The Probability of Backtest Overfitting. Journal of Computational Finance](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253); accessed 2026-08-23
- [Bailey, López de Prado (2014). The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality. Journal of Portfolio Management 40(5)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551); accessed 2026-08-23
- [Harvey, Liu, Zhu (2016). …and the Cross-Section of Expected Returns. Review of Financial Studies 29(1)](https://academic.oup.com/rfs/article/29/1/5/1585459); accessed 2026-08-23
- [Harvey, Liu (2015). Backtesting. Journal of Portfolio Management 42(1)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2345489); accessed 2026-08-23
- [White (2000). A Reality Check for Data Snooping. Econometrica 68(5)](https://www.jstor.org/stable/2999444); accessed 2026-08-23
- [Bergmeir, Benítez (2012). On the Use of Cross-Validation for Time Series Predictor Evaluation. Information Sciences](https://www.sciencedirect.com/science/article/abs/pii/S0020025512003406); accessed 2026-08-23
- [Politis, Romano (1994). The Stationary Bootstrap. JASA 89](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870); accessed 2026-08-23
- [scikit-learn documentation: TimeSeriesSplit limitations](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
