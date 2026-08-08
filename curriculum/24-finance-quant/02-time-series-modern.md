# Time Series Modern: Prophet, GARCH, State-Space/Kalman, and Deep Forecasters

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 3h · **Prereqs:** T24-time-series-core
> **Module id:** `T24-time-series-modern` · **Tags:** timeseries, critical
> **Lab:** `labs/python/02-time-series-modern/`

## The 30-second version

ARIMA models the conditional *mean* and assumes constant variance; the moment you need to model the *variance itself* (volatility clustering — big moves cluster with big moves, regardless of sign), you fit GARCH on the ARIMA residuals, not instead of ARIMA. GARCH(1,1), `σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}`, is literally an exponentially-weighted average of all past squared shocks (expand the recursion and it's `σ²_t = ω/(1-β) + α·Σ β^{i-1}r²_{t-i}`) — with typical equity-index fits like `α=0.08, β=0.90` (persistence `α+β=0.98`), a volatility shock has a half-life of `ln(0.5)/ln(0.98) ≈ 34 trading days`, which is the mechanical reason a single -4% day keeps elevated volatility in the forecast for over a month. State-space models generalize further: any process with a hidden, evolving state observed through noise (`x_t = x_{t-1} + w_t`, `y_t = x_t + v_t`) is estimated by the Kalman filter, whose update is a precision-weighted average of your prediction and the new observation — Kalman gain `K = P_pred/(P_pred+R)` is exactly "how much do I trust the new data versus my prior," and it falls out of straightforward variance minimization, not magic. Prophet decomposes a series additively (`y(t)=g(t)+s(t)+h(t)+ε`: piecewise-linear or logistic trend with changepoints, Fourier-series seasonality, holiday effects) and is easy for a non-specialist to configure with strong domain priors (known holidays, known capacity limits) — genuinely useful for business dashboards, rarely the most accurate option in a head-to-head. Deep forecasters (N-BEATS's pure basis-expansion stacks, the Temporal Fusion Transformer's attention-plus-gating architecture, TimesFM's pretrained decoder-only foundation model) win when you have thousands of related series to share statistical strength across; they are not automatically better on any single series, and the single most important fact for an interview is that gradient-boosted trees (LightGBM), not deep nets, won the M5 competition's top spots in both accuracy and uncertainty tracks — "just use a deep model" is the wrong reflex for most real forecasting problems.

## Why this gets asked

Because production forecasting and risk systems have to answer three questions ARIMA alone can't: how volatile will things be, not just what's the expected level (GARCH); how do I track a state I can't observe directly and that changes over time, possibly with missing or irregularly-spaced data (state-space/Kalman); and when I have thousands of related series (SKUs, accounts, sensors), do I fit one model per series or share strength across them (deep/global models)? Interviewers who've run a real forecasting or risk pipeline ask this because they've personally watched a team reach for a transformer-based forecaster on a problem with 200 data points and one series, get worse results than a properly-tuned ARIMA+GARCH combination, and burn a sprint discovering it. The honest, model-agnostic judgment about *when* each tool actually wins is the signal; reciting architecture diagrams from memory is not.

---

## Lineage: past → present → future

**What came before.** Classical Box-Jenkins ARIMA (previous module) models the conditional mean and implicitly assumes homoskedastic (constant-variance) residuals — a reasonable simplification for many series but badly wrong for financial returns, where Mandelbrot (1963) had already observed "large changes tend to be followed by large changes... and small changes tend to be followed by small changes" decades before anyone had a model that captured it. The specific pain: an ARIMA model fit on returns produces correctly-centered point forecasts but confidence intervals of constant width, which are far too narrow during a volatile regime (VaR and options pricing built on them would be dangerously wrong) and unnecessarily wide during a calm one. Separately, classical decomposition and ARIMA both assume you fit one model per series by hand — fine for a handful of important series, operationally impossible for a retailer forecasting demand for 100,000 SKUs.

**Where it stands now.** Engle's ARCH (1982, Nobel Prize 2003) and Bollerslev's GARCH generalization (1986) remain the standard way to model conditional variance in production risk and derivatives-pricing systems as of 2026 — every major risk engine fits some GARCH variant on return residuals. Kalman filtering (1960) and its state-space generalization remain the standard for tracking a hidden, time-varying state (a security's "true" beta, a term-structure factor, a sensor's true position under noisy readings) and are foundational to modern portfolio-tracking and macro nowcasting. Prophet (Meta, 2017) had a moment as the default "easy business forecasting" tool, especially for people without a statistics background, but is now in low-activity community maintenance rather than active development, and practitioners increasingly reach for gradient-boosted trees (LightGBM) or the newer global deep forecasters instead — the live disagreement in the field is precisely how much of "modern" forecasting should be deep-learning-based versus tree-based versus classical, and the honest answer, confirmed empirically by the M5 competition (2020) where LightGBM-based approaches swept the top ranks in both the accuracy and uncertainty tracks, is "it depends heavily on how many related series you have and how much exogenous/covariate information there is to exploit" — not "deep learning has won."

**Where it's heading.** Zero-shot time-series foundation models (Google's TimesFM, released February 2024; Amazon's Chronos; Salesforce's Moirai) — pretrained on enormous cross-domain corpora of series and applied to a new series with no fine-tuning — are the most active research direction as of 2026, promising to remove the "not enough data for a good deep model" objection entirely. Confidence is moderate-to-high that foundation-model forecasting keeps improving and becomes a serious out-of-the-box baseline; confidence is low-to-speculative that it displaces GARCH-family volatility modeling or Kalman-family state tracking any time soon, since those solve a structurally different problem (explicit, interpretable variance/state dynamics that a risk committee can audit) that a black-box zero-shot point/quantile forecaster doesn't directly address. Expect continued convergence: GARCH-in-mean and regime-switching extensions absorbing some deep-learning-style flexibility, and foundation models absorbing more classical structure (explicit trend/seasonality decomposition inside the architecture) rather than either fully replacing the other.

---

## Mental model

```
ARIMA:  models E[y_t | past]              -- the WHERE
GARCH:  models Var[y_t | past]            -- the HOW MUCH UNCERTAINTY, fit on ARIMA's residuals
KALMAN: models a HIDDEN, time-varying state observed through noise -- the WHAT'S TRUE UNDERNEATH
PROPHET: y(t) = trend(t) + seasonality(t) + holidays(t) + noise -- additive, interpretable, business-friendly
DEEP (N-BEATS/TFT/TimesFM): learn shared structure ACROSS many related series at once

     ARIMA residuals
          |
          v
   +--------------+        +----------------------+
   |   GARCH(1,1) |        |  Kalman filter        |
   |  sigma^2_t =  |        |  predict: x-, P-      |
   |  w + a*r^2   |        |  update:  K = P-/(P-+R)|
   |    + b*sig^2  |        |  x = x- + K(z - x-)   |
   +--------------+        +----------------------+
   variance forecast          hidden-state estimate

   ONE series, hand-tuned        MANY related series, shared model
   ARIMA / GARCH / Kalman  <---------------------->  N-BEATS / TFT / TimesFM / LightGBM
   (interpretable, cheap,                            (needs volume to beat classical,
    audit-friendly)                                   wins at scale / with rich covariates)
```

The one-line mental model: **GARCH answers "how uncertain," Kalman answers "what's the true hidden state right now," Prophet answers "give me an interpretable decomposition fast," and deep/global models answer "I have thousands of series and want to share what they have in common" — picking the wrong one for the actual question is the most common practical mistake.**

---

## How it actually works

### GARCH, derived from ARCH

Engle's ARCH(q) (1982) models conditional variance as `σ²_t = ω + Σ(i=1..q) α_i·r²_{t-i}` — variance today depends on a weighted sum of the last `q` squared shocks. The practical problem: capturing realistic, slowly-decaying volatility persistence with pure ARCH requires a large `q` (many lags, many parameters, noisy estimates). Bollerslev's GARCH(1,1) (1986) fixes this by adding the *previous variance forecast itself* as a regressor: `σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}`.

**Why this is an infinite ARCH in disguise.** Substitute the definition of `σ²_{t-1}` into itself recursively:
```
σ²_t = ω + α·r²_{t-1} + β·(ω + α·r²_{t-2} + β·σ²_{t-2})
     = ω(1+β) + α·r²_{t-1} + αβ·r²_{t-2} + β²·σ²_{t-2}
     = ... (continue substituting) ...
     = ω/(1-β) + α·Σ(i=1..∞) β^{i-1}·r²_{t-i}
```
GARCH(1,1) is exactly an ARCH(∞) with exponentially decaying weights `α·β^{i-1}` on past squared shocks — a two-parameter model (`α,β`) achieves what would otherwise need infinitely many ARCH coefficients, because the geometric weighting is baked in structurally rather than estimated freely lag by lag.

**Stationarity and the unconditional variance.** GARCH(1,1) is covariance-stationary (finite, constant unconditional variance) iff `α+β<1`. When that holds, taking unconditional expectations of the recursion (`E[σ²_t]=E[σ²_{t-1}]=σ̄²` in steady state) gives `σ̄² = ω/(1-α-β)`. **Persistence** is `α+β` — how slowly a shock decays — and the **half-life** of a volatility shock (periods until half its effect has dissipated) is `ln(0.5)/ln(α+β)`.

**Worked example.** Fitted parameters typical of a real equity index (`ω=0.00001, α=0.08, β=0.90`, so persistence `=0.98`): unconditional daily variance `σ̄² = 0.00001/(1-0.98) = 0.0005`, i.e. unconditional daily vol `√0.0005 ≈ 2.236%`. Half-life `= ln(0.5)/ln(0.98) ≈ 34.3 trading days` — a large shock today is still roughly half as impactful on variance a month and a half from now. Recursing `σ²_t = ω+α r²_{t-1}+β σ²_{t-1}` starting from the unconditional variance, through a 10-day return series that includes one large shock (`r=-4%` on day 4, `r=+3%` on day 5, everything else small):

```
t:      0       1        2        3        4        5        6        7        8        9       10
r_t:    -     0.001   -0.002   0.0015   -0.040   0.030   -0.010   0.002   -0.001   0.0005  -0.0008
sig2:  0.000500 0.000460 0.000424 0.000392 0.000491 0.000524 0.000489 0.000451 0.000416 0.000384 0.000356
vol%:   2.236   2.145    2.060    1.980    2.216    2.289    2.212    2.123    2.039    1.960    1.887
```
Variance is *decaying toward its unconditional level* through days 1-3 (small returns, no new shocks), then jumps back up sharply at `t=4` and `t=5` (the -4% and +3% days) — **volatility clustering, mechanically reproduced**: variance stays elevated for several days after the shock even though returns immediately after the shock are small again, exactly matching what Mandelbrot observed and what an ARIMA-with-constant-variance model cannot represent at all.

**Asymmetry: GARCH's blind spot.** Plain GARCH treats a `-4%` day and a `+4%` day identically (`r²` loses the sign). Real equity volatility responds asymmetrically — a large *down* move raises future volatility more than an equally large *up* move (the "leverage effect": a falling stock price mechanically raises a firm's leverage ratio, and panic-selling volume itself begets more volatility). **EGARCH** (Nelson, 1991) and **GJR-GARCH** (Glosten-Jagannathan-Runkle, 1993) add an extra term that activates only for negative shocks (`+γ·r²_{t-1}·𝟙[r_{t-1}<0]` in the GJR form) to capture this; using plain symmetric GARCH on equity returns systematically underestimates downside volatility risk.

### State-space models and the Kalman filter, derived

A **state-space model** separates a **state equation** (how a hidden, unobserved state evolves) from an **observation equation** (how you actually measure it, with noise): for the simplest case, the local-level model, `x_t = x_{t-1} + w_t` (`w_t ~ N(0,Q)`, process noise) and `y_t = x_t + v_t` (`v_t ~ N(0,R)`, observation noise). The Kalman filter is the exact, closed-form Bayesian solution for the minimum-variance estimate of `x_t` given all observations up to `t`, computed recursively in two steps:

**Predict.** Before seeing `y_t`, propagate the state forward: `x̂_t^- = x̂_{t-1}` (for the local-level model, the best guess is unchanged) and `P_t^- = P_{t-1} + Q` (uncertainty grows by the process noise).

**Update.** After seeing `y_t`, blend the prediction with the new observation, weighted by their relative certainty. The **Kalman gain** `K_t = P_t^- / (P_t^- + R)` is derived by minimizing the posterior variance `P_t = (1-K_t)P_t^-` over `K_t` (take the derivative of `Var[x_t - x̂_t]` with respect to `K_t`, set to zero — it's a straightforward weighted-least-squares argument, not an ad hoc rule): the update is `x̂_t = x̂_t^- + K_t(y_t - x̂_t^-)`. **`K_t` is exactly the fraction of the "surprise" (innovation, `y_t - x̂_t^-`) you should incorporate** — when observation noise `R` is large relative to prediction uncertainty `P_t^-`, `K_t→0` (trust your prior, ignore noisy readings); when `R` is small, `K_t→1` (trust the new data almost entirely).

**Worked example** (`Q=0.5, R=4.0`, prior `x̂_0=10, P_0=10`, observations `11.2, 9.8, 12.5, 10.1, 9.0`):

```
t   z(obs)  x_pred   P_pred   K       x_est    P
1   11.2    10.0000  10.5000  0.7241  10.8690  2.8966
2    9.8    10.8690   3.3966  0.4592  10.3781  1.8368
3   12.5    10.3781   2.3368  0.3688  11.1606  1.4751
4   10.1    11.1606   1.9751  0.3306  10.8100  1.3222
5    9.0    10.8100   1.8222  0.3130  10.2435  1.2519
```
Notice `K` starts high (`0.72` at `t=1`, prior is very uncertain, `R=4` is comparatively small so trust the observation heavily) and shrinks toward roughly `0.31` as `P` converges — the filter becomes progressively more confident in its own running estimate and weights each new noisy observation less, which is exactly the intuitive behavior "don't overreact to one more noisy data point once you have a well-established estimate," derived, not asserted. This is the mechanism behind tracking a time-varying beta, a smoothed macro nowcast, or fusing noisy sensor/price feeds — anywhere the "true" quantity moves slowly and each individual reading is noisy.

**Where this generalizes.** Nonlinear or non-Gaussian state-space models (the true dynamics aren't a linear-Gaussian update) need the **Extended Kalman Filter** (linearize around the current estimate via a first-order Taylor expansion — introduces linearization bias), the **Unscented Kalman Filter** (propagate a small set of deterministically-chosen sigma points through the true nonlinear function, avoiding explicit linearization), or a **particle filter** (represent the posterior with weighted samples, most general but computationally heaviest) — know which regime you're in before reaching for the plain linear-Gaussian Kalman filter.

### Prophet

Prophet's model is `y(t) = g(t) + s(t) + h(t) + ε_t` — an explicitly additive, interpretable decomposition rather than a fitted black box. `g(t)` is piecewise-linear (or logistic, for series with a known saturating capacity) trend with automatically- or manually-specified **changepoints** where the growth rate is allowed to shift; `s(t)` is seasonality represented as a **truncated Fourier series** (`s(t) = Σ(n=1..N) [a_n cos(2πnt/P) + b_n sin(2πnt/P)]`, letting the model fit an arbitrary smooth periodic shape with `2N` parameters rather than one parameter per seasonal position); `h(t)` is a regressor for known, irregularly-spaced holiday/event effects supplied by the analyst. This structure is Prophet's actual advantage: a business analyst can hand it a list of known future holidays and marketing-campaign dates and get sane, interpretable forecasts without understanding ARIMA identification at all — genuinely valuable for accessibility, not for beating a properly-tuned specialist model on raw accuracy.

### Deep forecasters: what each one actually adds

**N-BEATS** (Oreshkin et al., 2019) is a pure deep architecture with *no* recurrence or attention at all — stacked fully-connected blocks, each producing a forecast and a "backcast" (reconstruction of its own input) via learned or fixed **basis functions** (polynomial for trend, Fourier for seasonality, in the interpretable configuration), with residual connections passing the backcast error to the next block (a doubly-residual stacking pattern). It's notable because it beat the M4 competition's winning hybrid ES-RNN model (Slawek Smyl, Uber, itself a hybrid of exponential smoothing and an RNN) by about 3% using a comparatively simple, non-recurrent architecture.

**Temporal Fusion Transformer (TFT)** (Lim et al., Google, 2021) is built for the messier real-world case: multiple input types simultaneously — static metadata (a store's region), known future inputs (a scheduled promotion), and observed-past-only inputs (actual sales) — combined via variable-selection networks (learned, per-timestep feature gating) and an LSTM-plus-multi-head-attention encoder, producing quantile forecasts with attention weights that are directly inspectable for a rough interpretability story ("the model weighted last month heavily, and this promo flag").

**TimesFM** (Google Research, released February 2024) is a decoder-only transformer pretrained on a very large, diverse cross-domain corpus of time series and applied **zero-shot** to a new series with no fine-tuning — the foundation-model bet applied to forecasting: rather than training a bespoke model per problem, pretrain once on enough series that the model has learned general temporal patterns (trend, seasonality, typical noise structure) transferable to an unseen series. This trades per-series customization for near-zero setup cost, and is genuinely useful as a fast, no-tuning baseline; it is not automatically the most accurate option for a domain with strong, well-understood structure (e.g., known holiday calendars, known promotional dynamics) that a purpose-built model can exploit directly.

### Being honest about when classical still wins

The single most important, most frequently over-simplified fact in this space: **the M5 competition (2020, Walmart retail demand data, ~42,840 series) was won at the top of both the accuracy and uncertainty leaderboards by LightGBM-based gradient-boosted tree approaches, not by deep learning and not by classical ARIMA/exponential smoothing.** Nearly all top-50 finishers used LightGBM, some in hybrid combination with simpler statistical models; pure deep architectures (N-BEATS, seq2seq) placed but did not dominate. The lesson generalizes: gradient-boosted trees handle the messy reality of retail/business forecasting — many heterogeneous covariates (price, promotion flags, calendar effects, store/item hierarchies), missing data, non-Gaussian demand (integer counts, intermittent zeros) — better than either classical univariate time-series models (which mostly can't use covariates at all) or deep sequence models (which need more data and tuning than most business forecasting problems actually have). Reach for deep/foundation forecasters when you have genuinely many related series and want to share structure across them with minimal per-series tuning; reach for gradient-boosted trees when you have rich tabular covariates and a moderate number of series; reach for classical ARIMA/GARCH/Kalman when you have one or a few important series, need interpretability an auditor or risk committee can follow, or need well-calibrated variance/uncertainty estimates more than raw point-forecast accuracy.

---

## Build it from scratch

```python
# untested sketch -- structure verified against the worked numbers above
import numpy as np

def garch11_variance_path(returns, omega, alpha, beta, sigma2_0=None):
    if sigma2_0 is None:
        sigma2_0 = omega / (1 - alpha - beta)          # start at unconditional variance
    n = len(returns)
    sigma2 = np.zeros(n + 1)
    sigma2[0] = sigma2_0
    for t in range(1, n + 1):
        sigma2[t] = omega + alpha * returns[t - 1] ** 2 + beta * sigma2[t - 1]
    return sigma2

def kalman_local_level(observations, Q, R, x0, P0):
    x_est, P = x0, P0
    history = []
    for z in observations:
        x_pred, P_pred = x_est, P + Q                  # predict
        K = P_pred / (P_pred + R)                       # Kalman gain
        x_est = x_pred + K * (z - x_pred)                # update
        P = (1 - K) * P_pred
        history.append((x_pred, P_pred, K, x_est, P))
    return history

# GARCH persistence / half-life
def half_life(alpha, beta):
    return np.log(0.5) / np.log(alpha + beta)
```

Full runnable version, plus a diff against `arch.univariate.arch_model` (GARCH) and `pykalman.KalmanFilter` for numerical agreement to `1e-3`, is the lab exercise in `labs/python/02-time-series-modern/`. Also included: a toy N-BEATS basis-expansion block (polynomial trend basis only, a handful of lines) to make "basis expansion" concrete rather than a name to recite.

---

## How it's done in production

`arch` (Python) for GARCH-family models (`arch_model(returns, vol='GARCH', p=1, q=1)`, plus `EGARCH`/`GJR-GARCH` variants for asymmetry); `statsmodels.tsa.statespace` (`UnobservedComponents`, custom `MLEModel`) or `pykalman`/`filterpy` for Kalman filtering; `prophet` (PyPI, community-maintained) for business decomposition forecasting; `neuralforecast`/`pytorch-forecasting` for N-BEATS and TFT; `timesfm` (Google, Hugging Face) for zero-shot foundation-model forecasting; `lightgbm`/`xgboost` with hand-engineered lag/calendar/covariate features remains the pragmatic default for rich-covariate business forecasting at scale.

| Symptom | Cause | Fix |
|---|---|---|
| VaR/options-pricing model badly underestimates risk after a volatile week | Using a constant-variance (plain ARIMA or unconditional historical) volatility estimate instead of a conditional GARCH forecast that accounts for clustering | Fit GARCH(1,1) (or EGARCH for asymmetry) on return residuals and use the conditional, not unconditional, variance forecast for near-term risk |
| GARCH fits fine in-sample but underestimates volatility after large *down* moves specifically | Plain symmetric GARCH treats `+r` and `-r` shocks identically, missing the leverage effect | Switch to GJR-GARCH or EGARCH, which add an asymmetric term activated by the sign of the shock |
| Kalman-filtered estimate lags badly behind an actual regime shift (e.g., tracked beta doesn't adapt for weeks after a real change) | Process noise `Q` set too small relative to how fast the true state actually moves, so the filter over-trusts its own smooth prior | Increase `Q` (or use a time-varying/adaptive `Q`), re-derive from how much the state plausibly moves per period rather than an arbitrary default |
| Deep forecaster (N-BEATS/TFT) trained on a handful of series performs worse than a simple ARIMA/LightGBM baseline | Not enough series/data volume to justify the model's parameter count; deep global models need genuine cross-sectional scale to earn their complexity | Benchmark against LightGBM and classical baselines before committing; only prefer the deep model if it wins on a proper backtest, not by architecture prestige |
| Prophet forecast looks smooth and plausible but is measurably worse than a tuned SARIMA/LightGBM model on holdout accuracy | Prophet's additive decomposition is a strong, sometimes wrong, structural prior (e.g., doesn't easily capture multiplicative or interacting seasonal effects, or complex autocorrelation ARIMA would capture directly) | Use Prophet for fast interpretable exploration and when domain-holiday priors are the main lever; benchmark against SARIMA/LightGBM before shipping to production if accuracy, not interpretability, is the priority |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a deep forecaster as a reflex.** The empirical record (M5, 2020) shows gradient-boosted trees, not deep nets, won on real retail demand data with rich covariates; deep/global models earn their complexity specifically when you have many related series and want to share structure, not by default superiority.
- **Don't fit plain symmetric GARCH on equity-like returns and assume it captures the leverage effect.** It structurally cannot (`r²` discards sign); use GJR-GARCH/EGARCH when downside-volatility asymmetry matters, which for equities it usually does.
- **Don't use the plain linear-Gaussian Kalman filter on a genuinely nonlinear or heavy-tailed process** (e.g., regime-switching dynamics, non-Gaussian jump risk) without checking whether an Extended/Unscented Kalman filter or particle filter is actually required — the plain filter will converge to confident, wrong estimates rather than obviously failing.
- **Don't use Prophet where you need best-in-class point-forecast accuracy and have the expertise to tune a specialist model.** Its value is interpretability and low setup cost for non-specialists with strong holiday/capacity priors, not competition-winning accuracy; it is also now community- rather than actively-maintained, which matters for a production dependency decision.
- **Don't zero-shot a foundation model (TimesFM/Chronos) on a series with strong, well-understood domain structure (known promotional calendar, known capacity constraints) and skip building a model that can actually use that structure directly** — zero-shot is a fast, tuning-free baseline, not automatically an upper bound on achievable accuracy.

---

## Interview questions

### Q1 — Derive GARCH(1,1) as an infinite ARCH process. Why does this matter practically, not just theoretically?
**Testing:** whether GARCH is understood as a parsimonious reparameterization of ARCH, not a different idea.
**Answer:** Substituting `σ²_{t-1} = ω+αr²_{t-2}+βσ²_{t-2}` into `σ²_t=ω+αr²_{t-1}+βσ²_{t-1}` recursively gives `σ²_t = ω/(1-β) + α·Σ_{i=1}^∞ β^{i-1}r²_{t-i}` — an ARCH(∞) with exponentially decaying weights, achieved with only 2 free parameters (`α,β`) instead of estimating a separate coefficient for every lag. Practically: this is why GARCH(1,1) with two parameters routinely outperforms ARCH(q) with many lags — it imposes a sensible decay structure rather than estimating it noisily from data.
**Follow-up trap:** *"What does `α+β` control, and what happens if it's ≥1?"* — persistence/half-life of a shock; if `α+β≥1` the process is not covariance-stationary (unconditional variance `ω/(1-α-β)` is undefined or negative), meaning volatility shocks never decay and the model is misspecified for that series (a sign the mean equation or data itself needs re-examination, e.g., a structural break).

### Q2 — Given `ω=0.00001, α=0.08, β=0.90`, compute the unconditional daily volatility and the half-life of a shock.
**Testing:** actual arithmetic under the formula, not just stating it.
**Answer:** `σ̄² = ω/(1-α-β) = 0.00001/0.02 = 0.0005`, so unconditional daily vol `=√0.0005≈2.236%`. Half-life `=ln(0.5)/ln(α+β)=ln(0.5)/ln(0.98)≈34.3` trading days.
**Follow-up trap:** *"If a risk desk needs the shock to decay within two weeks for a specific product, what does that tell you about acceptable `α+β`?"* — solve `ln(0.5)/ln(persistence)=10` (roughly two trading weeks) → `persistence=0.5^{1/10}≈0.933`; a fitted `α+β` well above that (like the 0.98 here) means shocks persist far longer than that product's risk horizon assumes, a real mismatch worth flagging rather than silently using the fitted model.

### Q3 — Why does plain GARCH fail to capture the leverage effect, and what's the mechanical fix?
**Testing:** knowing the specific structural gap, not just naming "asymmetry" as a buzzword.
**Answer:** GARCH's variance equation depends on `r²_{t-1}`, which discards the sign of the shock — a `-4%` and `+4%` day produce identical variance updates. Real markets show downside shocks raising future volatility more (mechanically, a price drop raises a levered firm's debt-to-equity ratio, and panic-driven volume itself begets volatility). GJR-GARCH fixes this by adding `γ·r²_{t-1}·𝟙[r_{t-1}<0]`, an extra term that only activates on negative shocks; EGARCH models `log(σ²_t)` directly with a term responding asymmetrically to the sign of the standardized shock.
**Follow-up trap:** *"Would you always prefer GJR/EGARCH over plain GARCH for any return series?"* — no; for series without a clear economic leverage mechanism (e.g., some commodity or FX pairs), the asymmetric term may not be statistically significant and adds estimation noise for no gain — check significance of `γ` before committing to the more complex model, don't default to it reflexively.

### Q4 — Derive the Kalman gain for the local-level model by minimizing posterior variance.
**Testing:** whether the Kalman filter is understood as a derived optimum, not a memorized formula.
**Answer:** With `x̂_t = x̂_t^- + K(y_t - x̂_t^-)` and true state `x_t = x̂_t^- + (\text{true innovation})`, the posterior error variance is `P_t = Var[x_t - x̂_t] = (1-K)^2 P_t^- + K^2 R` (using independence of prediction error and observation noise). Taking `dP_t/dK = -2(1-K)P_t^- + 2KR = 0` and solving gives `K = P_t^-/(P_t^-+R)` — exactly the ratio of prediction uncertainty to total uncertainty (prediction + observation noise combined).
**Follow-up trap:** *"What does `K→0` versus `K→1` mean practically, and give a concrete scenario for each?"* — `K→0` when observation noise `R` is huge relative to prediction uncertainty (e.g., a very noisy sensor feeding a well-established estimate — mostly ignore each new reading); `K→1` when `R` is tiny relative to `P^-` (e.g., a precise price feed updating a highly uncertain initial guess — trust the new data almost fully).

### Q5 — In the worked Kalman example, `K` fell from 0.72 at t=1 to 0.31 by t=5 even though `R` never changed. Why?
**Testing:** connecting the abstract formula to the concrete worked numbers, catching a common confusion (assuming `K` is fixed).
**Answer:** `K_t = P_t^-/(P_t^-+R)` depends on `P_t^-`, which itself shrinks over time as the filter accumulates observations and becomes more confident (each update step's `P=(1-K)P^-` shrinks the posterior variance, and the next `P^- = P+Q` only grows it back by the fixed process noise `Q=0.5`, not enough to undo the shrinkage) — so `K` converges to a steady-state value determined by `Q` and `R` jointly, not a constant set once at initialization.
**Follow-up trap:** *"Does `K` converge to a fixed steady-state value here, and how would you find it without simulating?"* — yes, for a time-invariant linear-Gaussian model `P` converges to a fixed point solving the discrete algebraic Riccati equation `P=(P+Q)-(P+Q)^2/(P+Q+R)`; you can solve this directly rather than iterating, useful for knowing the filter's long-run behavior without running it out to convergence.

### Q6 — What's the actual difference between Prophet's `g(t)` (trend) with changepoints and a Kalman-filtered local-level-plus-trend model? Aren't they both "trend that can change"?
**Testing:** distinguishing a discrete-changepoint structural model from a continuously-evolving state-space model, a genuinely subtle point.
**Answer:** Prophet's trend is piecewise *linear* with a small, typically sparse set of discrete changepoints (the growth rate is constant between changepoints and jumps at them, regularized toward few actual changes) — a structural, interpretable "when did the regime change" story. A Kalman local-level-plus-trend model lets the trend evolve *continuously* every single period via process noise `Q`, with no notion of discrete "changepoints" at all — it's a smooth random walk in the trend/slope rather than a sparse set of jumps. They produce visually similar smoothed trends but encode different assumptions about *how* trend changes happen, which matters for how each extrapolates past the end of the data.
**Follow-up trap:** *"Which one would extrapolate more conservatively into the future, and why?"* — Prophet, generally, because its default changepoint prior regularizes toward *few* changes and the last-observed growth rate is extrapolated forward unless a new changepoint is detected; a Kalman model with meaningful process noise `Q` on the trend/slope keeps accumulating uncertainty into the future at every step, often producing wider (sometimes more honestly wide) forecast intervals further out.

### Q7 — The M5 competition's top finishers used LightGBM, not deep learning or classical ARIMA. What does this actually tell you, and what would change your recommendation?
**Testing:** whether "deep learning wins" is understood as a specific, falsifiable, context-dependent claim rather than a general truth.
**Answer:** It tells you that for retail demand forecasting with rich tabular covariates (price, promotions, calendar effects, hierarchical structure) across tens of thousands of series, gradient-boosted trees handled the heterogeneity and covariate-richness better than either univariate classical models (which mostly can't use covariates) or the deep sequence models entered (which didn't have enough relative data/tuning advantage to win). It does not mean GBTs always beat deep models — with far more series, less tabular covariate structure, and a genuinely shared temporal pattern to exploit (e.g., very large-scale cross-sectional forecasting with minimal per-series metadata), deep/foundation models close or reverse that gap.
**Follow-up trap:** *"Would you expect the same result on financial return series specifically, rather than retail demand?"* — not directly comparable; return series usually have far fewer useful covariates, much lower signal-to-noise, and different modeling goals (volatility/risk, not point demand) — this is exactly why GARCH/Kalman remain the default there rather than LightGBM, which has little to exploit without informative covariates.

### Q8 — Why is GARCH fit on ARIMA *residuals* rather than on the raw price or return series directly?
**Testing:** whether the two-stage mean-then-variance modeling pipeline is understood, a common practical confusion.
**Answer:** ARIMA (or even just demeaning) removes the predictable conditional-mean structure first; GARCH models the conditional variance of what's *left* (the innovations), because GARCH's own derivation assumes the input series has mean-zero, serially uncorrelated shocks — feeding it raw autocorrelated returns conflates mean-mispecification with genuine variance clustering and will misestimate both.
**Follow-up trap:** *"What would you see in your residual diagnostics if you skipped the ARIMA step and fit GARCH directly on raw autocorrelated returns?"* — the GARCH residuals (standardized by the fitted `σ_t`) would still show significant autocorrelation (Ljung-Box test on levels, not just squared levels, would reject), revealing that some of what GARCH is "explaining" as variance dynamics is actually unmodeled conditional-mean structure that ARIMA should have absorbed first.

### Q9 — What specifically does the Temporal Fusion Transformer add over N-BEATS, and when would that actually matter?
**Testing:** whether the two architectures' actual capabilities are distinguished, not just recalled as two names in a list.
**Answer:** N-BEATS is a pure univariate (or simple multi-series) point/basis-expansion forecaster with no native mechanism for heterogeneous inputs. TFT is explicitly built to combine three input types simultaneously — static metadata, known future covariates (a scheduled promotion), and observed-past-only covariates — via variable-selection gating, and outputs full quantile forecasts with attention weights offering rough interpretability. It matters when you have genuine heterogeneous, partially-known-in-advance covariates (retail promotions, staffing schedules); it's overkill for a single clean series with no exogenous structure, where N-BEATS or even ARIMA/GARCH is simpler and often just as accurate.
**Follow-up trap:** *"TFT's attention weights are described as offering interpretability — how reliable is that, really?"* — attention weights show what the model *attended to*, not necessarily a faithful causal explanation of *why* it produced a given forecast (a well-documented gap in the broader attention-as-explanation literature) — treat it as a debugging aid and a rough sanity check, not as an auditable causal account for a risk committee, which is a materially different bar than Prophet's explicit additive decomposition provides.

### Q10 — Design question: you're asked to add volatility forecasting to a risk pipeline for 5 major currency pairs (a handful of long, liquid daily series) versus separately being asked to forecast next-day demand for 80,000 SKUs at a retailer. Which modeling family would you reach for first in each case, and why?
**Testing:** staff-level judgment applying the "how many series, how much covariate richness" framework correctly to two contrasting real scenarios.
**Answer:** For 5 FX pairs: GARCH-family (likely GJR-GARCH given known FX volatility asymmetry around macro events) fit per series — few series, need interpretable, auditable variance dynamics for risk reporting, plenty of history per series, no rich covariate structure to exploit. For 80,000 SKUs: LightGBM with engineered lag/calendar/price/promotion features as the primary approach (matching M5's empirical result), with a global deep model (N-BEATS/TFT) as a secondary candidate to benchmark if there's meaningful shared structure across SKUs and the team has the tuning budget — plain per-SKU ARIMA/GARCH doesn't scale operationally to 80,000 hand-tuned models, and there's rich covariate/hierarchical structure GBTs are well-suited to exploit.
**Follow-up trap:** *"What would make you reconsider the LightGBM default for the SKU case?"* — if most SKUs have very short or sparse (intermittent, many-zero) histories where tree-based lag features are unreliable, and there's strong shared cross-SKU temporal structure (e.g., a common macro-driven trend across the whole category) — that combination favors a global deep or hierarchical Bayesian approach that pools information across series more directly than per-SKU feature engineering can.

### Q11 — What's the practical risk of using a foundation model (TimesFM) zero-shot on a financial return series without any fine-tuning or validation?
**Testing:** whether "foundation models are the future" enthusiasm is tempered with a concrete, specific risk.
**Answer:** Zero-shot foundation forecasters are pretrained predominantly on series with visible trend/seasonality structure (retail, web traffic, weather-like data); financial returns are close to a low-signal, near-random-walk process with fat tails and volatility clustering rather than seasonal/trend structure — a model whose pretraining distribution doesn't resemble that regime may produce confident-looking point forecasts with miscalibrated (often understated) uncertainty, since it has little basis in its training data for "what does a near-unpredictable, fat-tailed series actually look like." Any production use requires backtesting against the same walk-forward discipline as any other model (next module) before trusting it, not assuming foundation-model generality transfers automatically.
**Follow-up trap:** *"How would you specifically test whether TimesFM's uncertainty estimates are well-calibrated on your return series before trusting them?"* — run a proper backtest (walk-forward, per the next module) and check empirical coverage of its quantile forecasts (does the 90% interval actually contain the realized value ~90% of the time, out of sample) rather than trusting the point forecast alone — the same Kupiec-style coverage-testing logic used for VaR backtesting, covered in the risk-metrics module, applies directly here.

---

## Red flags that fail you

- Says "GARCH models volatility" without being able to write the recursion or explain why it's an infinite ARCH.
- Cannot state what the Kalman gain represents or derive it, even at a high level (variance-minimizing blend of prediction and observation).
- Claims deep learning "beats classical methods" without qualification, unaware that LightGBM won M5's top spots, not deep nets or classical ARIMA.
- Fits plain GARCH on equity returns and doesn't know it misses the leverage/asymmetry effect.
- Confuses Prophet's discrete-changepoint trend with a continuously-evolving Kalman/state-space trend, or can't articulate the difference.
- Recommends a deep or foundation forecaster for a single short series with no justification for why it would beat a simpler classical baseline.

---

## Cheat card

```
GARCH(1,1): sig2_t = w + a*r2_t-1 + b*sig2_t-1
  = infinite ARCH: sig2_t = w/(1-b) + a*sum(b^(i-1)*r2_t-i)   [derived by recursive substitution]
  stationary iff a+b<1; unconditional var = w/(1-a-b)
  persistence = a+b; half-life = ln(0.5)/ln(a+b)
  worked: w=1e-5,a=0.08,b=0.90 -> uncond vol 2.236%, half-life ~34.3 days
  ASYMMETRY BLIND SPOT: r^2 loses sign -> use GJR-GARCH / EGARCH for leverage effect

KALMAN (local level): x_t = x_t-1 + w_t (Q);  y_t = x_t + v_t (R)
  predict: x_pred = x_est, P_pred = P + Q
  update:  K = P_pred/(P_pred+R)   [derived: minimizes posterior variance]
           x_est = x_pred + K*(z - x_pred);  P = (1-K)*P_pred
  K->0 when R>>P_pred (noisy sensor, trust prior); K->1 when R<<P_pred (trust new data)
  nonlinear/non-Gaussian -> Extended KF (linearize) / Unscented KF (sigma points) / particle filter

PROPHET: y(t) = g(t)[piecewise linear/logistic, changepoints] + s(t)[Fourier seasonality]
                + h(t)[holidays] + noise. Interpretable, business-friendly, not SOTA accuracy.
                Community-maintained as of 2026, not actively developed by Meta.

DEEP FORECASTERS:
  N-BEATS (2019): pure FC stacks, basis expansion (poly/Fourier), no attention/RNN;
                   beat M4-winning hybrid ES-RNN by ~3%
  TFT (2021, Google): static + known-future + observed-past inputs, variable-selection
                   gating + LSTM + attention, quantile outputs, rough interpretability
  TimesFM (Feb 2024, Google): decoder-only, pretrained cross-domain, ZERO-SHOT forecasting

HONEST BENCHMARK FACT: M5 competition (2020) top ranks in BOTH accuracy and uncertainty
  tracks -> LightGBM-based approaches, NOT deep learning, NOT classical ARIMA.
  "Deep learning wins" is not a general truth -- depends on # series, covariate richness.
```

## Sources

- [Autoregressive Conditional Heteroskedasticity with Estimates of the Variance of United Kingdom Inflation — Engle, Econometrica (1982)](https://www.jstor.org/stable/1912773) — accessed 2026-08-08
- [Generalized Autoregressive Conditional Heteroskedasticity — Bollerslev, Journal of Econometrics (1986)](https://www.sciencedirect.com/science/article/abs/pii/0304407686900631) — accessed 2026-08-08
- [arch: Python package for ARCH/GARCH models](https://arch.readthedocs.io/en/latest/) — accessed 2026-08-08
- [N-BEATS: Neural basis expansion analysis for interpretable time series forecasting — Oreshkin et al., arXiv (2019)](https://arxiv.org/abs/1905.10437) — accessed 2026-08-08
- [Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting — Lim et al., arXiv (2021)](https://arxiv.org/abs/1912.09363) — accessed 2026-08-08
- [TimesFM: A decoder-only foundation model for time-series forecasting — Google Research (Feb 2024)](https://research.google/blog/a-decoder-only-foundation-model-for-time-series-forecasting/) — accessed 2026-08-08
- [The M5 Accuracy competition: Results, findings and conclusions — Makridakis et al., International Journal of Forecasting (2022)](https://www.sciencedirect.com/science/article/pii/S0169207021001874) — accessed 2026-08-08
- [Prophet: Forecasting at scale — Taylor & Letham, Meta Core Data Science (2017)](https://facebook.github.io/prophet/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
