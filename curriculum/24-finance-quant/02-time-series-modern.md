# Prophet, GARCH, State Space, and Deep Forecasters (N-BEATS, TFT, TimesFM)

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 3.0h · **Prereqs:** T24-time-series-core · **Updated:** 2026-08-23
> **Module id:** `T24-time-series-modern` · **Tags:** timeseries, critical

## The 30-second version

Classical ARIMA freezes two things modern data refuses to freeze: parameters and variance. The modern stack splits the problem three ways. *State space* models (Kalman 1960; Harvey's structural models) let coefficients themselves be hidden random walks estimated by filtering — every ARIMA and exponential-smoothing method has an equivalent state-space form, so this is the superset framework. *GARCH* (Engle's ARCH 1982; Bollerslev's GARCH 1986) attacks variance dynamics directly: financial returns show volatility clustering (calm breeds calm, panic breeds panic), and GARCH(1,1) captures it with three parameters so well it remains the risk-desk default forty years on — RiskMetrics' EWMA with λ=0.94 (1996) is its degenerate cousin. *Prophet* (Facebook, 2017) industrializes decomposable business forecasting — piecewise trends with automatic changepoints, Fourier seasonalities, holiday regressors — optimized for thousands of series and analyst override, though its uncertainty intervals are simulation artifacts rather than calibrated probabilities. *Deep forecasters* win when you have many related series: N-BEATS took the M4 crown (2018 competition, 100,000 series) with a doubly-residual pure architecture; Temporal Fusion Transformer (2021) added interpretability and static covariates; and foundation models like TimesFM (~200M parameters pretrained on roughly 100 billion timepoints, Google 2024) now do zero-shot forecasting. Choosing among them is the interview skill: mean dynamics → state space/ARIMA; variance dynamics → GARCH; decomposable business series → Prophet or ETS; many cross-correlated series with metadata → deep learning.

## Why this gets asked

Because each tool here is a trap-rich production system, and interviewers want evidence you've been burned — or would notice the burns before signing off. The classic probes: "Prophet gave me beautiful intervals, can we ship them?" (they're drawn from simulated trend-shift paths, not posterior predictive distributions — a known criticism since release). "Your GARCH says tomorrow's vol is 12% annualized — what does the bank do with that?" (feeds VaR via filtered historical simulation — connects straight to T24-risk-metrics and T24-mrm). "Why did a gradient-boosted tree beat your fancy transformer on M5?" (cross-series learning vs tabular features; M5's 42,840 retail series favored LightGBM hybrids). At D.E. Shaw/Citi-tier desks expect the vol-clustering conversation to go deep: leverage effects, half-lives of shocks, why EWMA λ=0.94 survived Basel usage, and where realized-volatility measures (HAR-RV) displaced GARCH entirely. The modern-forecasting layer tests whether you read past benchmarks: N-BEATS' M4 win was an architecture story, M5's win was a feature-engineering story, and TimesFM changes the cold-start economics — candidates who conflate these three eras sound like they skimmed one blog post.

## Lineage

**What came before.** Exponential smoothing came first: Brown (1956) for inventory control, Holt (1957) adding trend, Winters (1960) adding seasonality — all later unified as state-space ETS. Kalman's 1960 filter, built for Apollo orbit estimation, supplied the recursive optimal update for linear-Gaussian hidden states; Harrison and Stevens (1976) brought discount-factor Bayesian forecasting into statistics, and Harvey's 1989 textbook codified structural time series (trend + seasonal + cycle as latent states). Engle (1982) won a Nobel for ARCH — modeling conditional variance as a function of squared shocks — after noticing that residuals of mean models clustered in magnitude; Bollerslev (1986) generalized to GARCH with lagged variance terms; Nelson (1991) added asymmetry (EGARCH) because bad news raises vol more than good news. RiskMetrics Group published the λ=0.94 daily EWMA recipe in 1996 and banks standardized on it for overnight VaR inputs.

**Where it stands now.** Prophet (Taylor & Letham, 2017, released as Facebook's forecasting tool with a Stan backend) became the most-cited applied forecaster of its decade — curve-fitting with automatic changepoints (default 25 candidates spread over the first 80% of history), Fourier seasonalities (order 10 yearly, 3 weekly by default), and multiplicative/additive modes. On the research side: DeepAR (Amazon, 2019) made probabilistic RNN forecasting practical; N-BEATS (ICLR 2020) won M4 with pure fully-connected doubly-residual blocks beating every ensemble of classical methods; N-HiTS (2022) added multi-rate sampling for efficiency; Temporal Fusion Transformer (Lim et al., 2021) fused LSTMs, variable-selection networks, and interpretable attention for heterogeneous covariates. Volatility research matured toward realized measures: Corsi's HAR-RV (2009) regresses daily/weekly/monthly realized volatility components and often outperforms GARCH out-of-sample where high-frequency data exists. The 2023-24 wave brought pretrained foundation models — TimesFM (decoder-only, patched input, ~200M params, trained on ~100B timepoints from Google Trends/Wikipedia/synthetic data), Chronos (Amazon, T5-family tokenization, 8M-710M params), Moirai, Lag-Llama — delivering usable zero-shot baselines.

**Where it's heading.** Three currents. First, foundation-model commoditization of the cold start: zero-shot curves for new SKUs/new markets, fine-tuned or ensembled with local models where data accumulates — the open question is calibration of their intervals, which lags point accuracy. Second, honest uncertainty: conformal prediction wrappers and quantile-loss training displacing Gaussian likelihoods, because risk applications need tail coverage, not RMSE bragging rights. Third, convergence with causality and decision-making: forecasts as inputs to optimization (inventory, capital, hedging) means the loss function migrates from MSE toward task-specific economic cost — visible in hierarchical reconciliation and in M5's move to quantile/pinball-style scoring over 28-day horizons. Classical tools don't die inside any of this: the M4 organizers' own combination benchmark stayed competitive against neural entries, and every serious deep pipeline still ships naive/ETS benchmarks alongside.

---

## Mental model

```
THREE ORTHOGONAL PROBLEMS, THREE TOOL FAMILIES:

  1. WHERE IS THE MEAN GOING?        -> state space / ETS / Prophet
     hidden states drift; filters track them
     y_t = Z*alpha_t + e ; alpha_t = T*alpha_{t-1} + w

  2. HOW LOUD IS THE NOISE TODAY?    -> GARCH family / EWMA / HAR-RV
     variance is autocorrelated even when returns are not
     sigma2_t = omega + a*e2_{t-1} + b*sigma2_{t-1}

  3. DO MANY SERIES SHARE STRUCTURE? -> deep forecasters / global models
     learn ONE function across thousands of related series
     N-BEATS (pure blocks) | TFT (attention+covariates) |
     TimesFM (pretrained, zero-shot)

  KALMAN GAIN INTUITION:  K = P_pred/(P_pred+R)
     trust the model when P small, trust the observation when R small

  VOLATILITY HALF-LIFE of a shock under persistence rho = a+b:
     h = ln(0.5)/ln(rho)   e.g. rho=0.97 -> 22.8 periods
```

The unifying lens: everything here is a bet on what persists. State space bets the *structure* persists but drifts slowly; GARCH bets *volatility regimes* persist; global deep models bet *relationships between series* persist. When the bet fails — regime breaks, vol crashes, new products with no siblings — that's exactly when each tool embarrasses its user.

---


## How it actually works

### State space and the Kalman filter — the superset framework

Write any structural model as two equations: observation y_t = Zα_t + ε_t and state transition α_t = Tα_t + Rη_t (local level: T=1, Z=1; local linear trend adds a slope state; seasonal dummies or trigonometric states add cycles). The filter recurses predict-then-update: predict α̂_{t|t−1} = Tα̂_{t−1|t−1}, P_{t|t−1} = TP_{t−1}P' + Q; then update with gain K_t = P_{t|t−1}Z'(ZPZ'+V)⁻¹ pulling the state toward the new observation. The one-step-ahead prediction errors e_t are Gaussian with computable variances, so log-likelihood decomposes as a sum over prediction errors (prediction-error decomposition) — you maximize it over variance parameters (Q, V ratios) by numerical MLE; the state path never needs explicit estimation. Smoothing (RTS) re-runs backward for the best estimate given ALL data — right for retrospective analysis, wrong for online systems. Key interview distinction: *filtered* estimates use data up to t; *smoothed* use the future too; using smoothed series anywhere near a live forecast pipeline is leakage in slow motion.

Why it matters: ARIMA(p,d,q) has an exact state-space representation, so SARIMAX with regressors/missing data/interventions all route through the same filter; exponential smoothing's E³ taxonomy (error/trend/seasonality each additive-or-multiplicative, 30 combos) is likewise a set of state-space models with known likelihoods — this unification is Hyndman et al.'s 2002-08 contribution that made ETS competitive on information criteria.

### GARCH — modeling the noise, not the signal

Daily equity returns have near-zero predictable mean but strongly autocorrelated *squared* returns: |r_t| correlates with |r_{t−h}| for weeks. GARCH(1,1): σ²_t = ω + αε²_{t−1} + βσ²_{t−1}, fit by quasi-maximum likelihood on standardized residuals; unconditional variance is ω/(1−α−β), requiring α+β < 1 (else IGARCH/nonstationary variance). Typical daily equity fits: α ≈ 0.05–0.12, β ≈ 0.85–0.93, persistence 0.97–0.99 ⇒ a shock's half-life ln(0.5)/ln(0.98) ≈ 34 days at β+α=0.98. The leverage effect — negative returns spike vol harder than positive ones of equal size — motivated EGARCH (log-variance, Nelson 1991) and GJR-GARCH (threshold term γ·ε²I(ε<0); typical γ ≈ 0.05–0.15). RiskMetrics EWMA σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1} with λ=0.94 is GARCH(1,1) with ω=0, α=0.06, β=0.94: simple, no stationarity constraint needed, deliberately non-mean-reverting. Forecast behavior matters for risk: GARCH forecasts converge to unconditional variance at rate α+β, so 10-day VaR uses √10 scaling only under independence — with persistence 0.98 the square-root rule misprices horizon risk badly.

Where GARCH loses: when intraday data exists, realized volatility from 5-minute returns summed daily measures today's vol directly, and Corsi's HAR-RV (daily + weekly + monthly components, OLS!) often beats GARCH forecasts out-of-sample. GARCH remains king when only daily closes exist — which is most books, most assets, most of history.

### Prophet — curve fitting engineered for scale and override

Prophet regresses y on: piecewise-linear (or logistic-growth) trend with changepoints selected via L1-sparse deviations (default 25 candidate changepoints over first 80% of data, regularization δ=0.05); Fourier-series seasonalities (yearly order 10, weekly order 3 defaults); user-supplied holiday dummies with configurable windows; optional regressors. Fit through Stan (MAP by default; full posterior optional). Its celebrated flexibility is analyst ergonomics: adjust changepoint_prior_scale to fight under/overfitting, inspect component plots, add domain holidays. The notorious weakness: default uncertainty intervals simulate future trend shifts drawn from the historical changepoint rate — a heuristic, NOT predictive posterior coverage; empirical interval coverage can be far below nominal. Also: no volatility model, no autoregressive term by default (residual autocorrelation goes unmodeled), and trend extrapolation past the last changepoint regime is where it embarrasses people. Right use: thousands of business series needing interpretable baselines with holiday logic; wrong use: price forecasting, anything with feedback loops, anything audited for interval honesty without recalibration.

### Deep forecasters — global models and pretraining

The paradigm shift: instead of fitting per-series models, train ONE network across many related series ("global model"). N-BEATS: stacks of fully-connected blocks, each outputting a partial forecast plus backcast that is subtracted from the input (doubly residual); basis-constrained variants project onto interpretable trend/seasonality bases; won M4 (2018, 100k series) with ~0.821 OWA... more precisely it beat the combination benchmark by ~3% with pure architecture, no exogenous features. TFT: LSTM encoder-decoder plus three attention/selection mechanisms — variable selection networks (per-input feature importance gates), static covariate encoders (entity metadata conditioning), and interpretable multi-head attention over lookback — trained with quantile loss for probabilistic multi-horizon outputs; strong when heterogeneous covariates and static metadata matter (retail demand, energy load). DeepAR: autoregressive RNN emitting distribution parameters (student-t/likelihood choice), pioneering the "one model, thousands of series" probabilistic recipe at Amazon scale. TimesFM/Chronos/Moirai (2024): decoder-only transformers pretrained on enormous heterogeneous corpora (TimesFM: ~100B timepoints across Google Trends/Wikipedia/synthetic), consuming patched inputs like tokens; they forecast zero-shot and serve as instant baselines or cold-start solutions, fine-tunable downstream. Honest benchmark context: on M5-style tabular problems gradient-boosted trees with lag features still beat most neural entries; deep nets dominate where cross-series transfer, covariates, or cold starts dominate.

---

## Build it from scratch

Runnable numpy-only lab: a Kalman filter tracking a drifting hidden level (with ML estimation of the noise ratio), and a GARCH(1,1) recovered by grid-searched Gaussian likelihood:

```python
import numpy as np

rng = np.random.default_rng(11)

# ============ Part 1: Kalman filter, local-level model ============
# y_t = mu_t + v_t   (v ~ N(0, R))      observation
# mu_t = mu_{t-1} + w_t (w ~ N(0, Q))   hidden random-walk signal

def kalman_local_level(y, R, Q):
    n = len(y)
    a = np.empty(n); P = np.empty(n)          # filtered mean/var of mu_t
    a_pred = np.empty(n); P_pred = np.empty(n)
    loglik = 0.0
    a_prev, P_prev = y[0], R                  # init at first observation
    for t in range(n):
        a_p = a_prev; P_p = P_prev + Q        # predict
        a_pred[t], P_pred[t] = a_p, P_p
        K = P_p / (P_p + R)                   # Kalman gain
        a[t] = a_p + K * (y[t] - a_p)         # update
        P[t] = (1 - K) * P_p
        if t > 0:
            loglik += -0.5 * (np.log(2*np.pi*(P_p+R)) + (y[t]-a_p)**2/(P_p+R))
        a_prev, P_prev = a[t], P[t]
    return a, P, a_pred, P_pred, float(loglik)

# synthetic truth: signal-to-noise ratio Q/R = 0.16
n_true = 500
mu_true = np.cumsum(rng.normal(0, 0.8, n_true))
y = mu_true + rng.normal(0, 2.0, n_true)

a_f, P_f, _, _, ll = kalman_local_level(y, R=4.0, Q=0.64)
rmse_raw  = float(np.sqrt(np.mean((y - mu_true)**2)))
rmse_filt = float(np.sqrt(np.mean((a_f - mu_true)**2)))

_, _, a_pred, P_pred, _ = kalman_local_level(y, R=4.0, Q=0.64)
rmse_naive = float(np.sqrt(np.mean((y[1:] - y[:-1])**2)))
rmse_os    = float(np.sqrt(np.mean((y[1:] - a_pred[1:])**2)))

print(f"[Kalman] RMSE raw obs      : {rmse_raw:.3f}")
print(f"[Kalman] RMSE filtered mean: {rmse_filt:.3f}")
print(f"[Kalman] 1-step RMSE naive : {rmse_naive:.3f}")
print(f"[Kalman] 1-step RMSE filter: {rmse_os:.3f}")

best = None                                   # ML via prediction-error decomposition
for q in [0.04, 0.09, 0.16, 0.25, 0.36, 0.64, 1.00]:
    _, _, _, _, llq = kalman_local_level(y, R=4.0, Q=q)
    tag = " <-- best" if best is None or llq > best[1] else ""
    if best is None or llq > best[1]: best = (q, llq)
    print(f"[Kalman] Q={q:.2f}  loglik={llq:9.1f}{tag}")
print(f"[Kalman] ML picks Q={best[0]:.2f} (truth 0.64)")

# ============ Part 2: GARCH(1,1) fit by likelihood grid ============
# r_t = sigma_t * z_t ; sigma2_t = omega + alpha*r^2_{t-1} + beta*sigma2_{t-1}
omega_t, alpha_t, beta_t = 0.05, 0.10, 0.85   # persistence = 0.95
Tg = 3000
z = rng.normal(0, 1, Tg)
r = np.empty(Tg); sig2 = np.empty(Tg)
sig2[0] = omega_t / (1 - alpha_t - beta_t)
r[0] = np.sqrt(sig2[0]) * z[0]
for t in range(1, Tg):
    sig2[t] = omega_t + alpha_t * r[t-1]**2 + beta_t * sig2[t-1]
    r[t] = np.sqrt(sig2[t]) * z[t]

def garch_nll(r, alpha, beta):
    s2 = float(np.var(r))                     # implied long-run variance
    om = max(s2 * (1 - alpha - beta), 1e-10)  # omega pinned by moment condition
    v = np.empty_like(r); v[0] = s2
    for t in range(1, len(r)):
        v[t] = om + alpha * r[t-1]**2 + beta * v[t-1]
    return float(np.sum(np.log(v) + r**2 / v))

grid = [(a, b) for a in np.arange(0.02, 0.30, 0.01)
               for b in np.arange(0.50, 0.98, 0.01) if a + b < 1.0]
lls  = np.array([garch_nll(r, a, b) for a, b in grid])
amin = int(np.argmin(lls))
a_hat, b_hat = grid[amin]
print(f"\n[GARCH] true (alpha,beta)=({alpha_t},{beta_t}) persistence {alpha_t+beta_t}")
print(f"[GARCH] grid-fit (alpha,beta)=({a_hat:.2f},{b_hat:.2f}) persistence {a_hat+b_hat:.2f}")
print(f"[GARCH] implied daily vol now: {np.sqrt(sig2[-1]):.4f} vs long-run {np.sqrt(np.var(r)):.4f}")
```

Actual output (executed before embedding):

```text
[Kalman] RMSE raw obs      : 2.063
[Kalman] RMSE filtered mean: 1.128
[Kalman] 1-step RMSE naive : 2.992
[Kalman] 1-step RMSE filter: 2.460
[Kalman] Q=0.04  loglik=  -1216.3 <-- best
[Kalman] Q=0.09  loglik=  -1187.5 <-- best
[Kalman] Q=0.16  loglik=  -1172.3 <-- best
[Kalman] Q=0.25  loglik=  -1163.9 <-- best
[Kalman] Q=0.36  loglik=  -1159.4 <-- best
[Kalman] Q=0.64  loglik=  -1157.4 <-- best
[Kalman] Q=1.00  loglik=  -1160.7
[Kalman] ML picks Q=0.64 (truth 0.64)

[GARCH] true (alpha,beta)=(0.1,0.85) persistence 0.95
[GARCH] grid-fit (alpha,beta)=(0.10,0.84) persistence 0.94
[GARCH] implied daily vol now: 0.8324 vs long-run 0.9910
```

Reading the output: filtering nearly halves reconstruction error (1.128 vs raw 2.063) because the gain optimally blends prediction against noisy observation; the 1-step forecast beats naive by ~18% (2.460 vs 2.992) even though the underlying level is a pure random walk — the win comes from denoising, not from predicting drift. Profile likelihood peaks exactly at the true noise ratio (Q=0.64), demonstrating prediction-error-decomposition MLE. The GARCH grid recovers (0.10, 0.84) versus truth (0.10, 0.85) on 3,000 simulated points with omega pinned by the moment condition — note current conditional vol (0.832) sitting below long-run vol (0.991): the process was mid-calm-regime at sample end, which is precisely why horizon-VaR must not assume independence. Replace the grid with scipy.optimize.minimize around the winner for production speed; the grid exists to keep this lab dependency-free.

---

## How it's done in production

**Volatility for risk systems.** Banks run GARCH(1,1)/EWMA pipelines producing conditional vols feeding filtered historical simulation VaR (rescale historical scenarios by today's GARCH/EWMA vol before reading off quantiles — see T24-risk-metrics). Parameters refit on rolling windows (often 250-1000 days), validated under SR 11-7 discipline (T24-mrm), monitored via Kupiec/Christoffersen tests on violations. Where intraday feeds exist, HAR-RV on realized variance displaces GARCH; where they don't, GARCH stays because it needs only closes. Expected shortfall at 97.5% under FRTB makes accurate tail-vol forecasts capital-relevant, not academic.

**Structural/business forecasting at scale.** Prophet-class systems (or Spark-fitted ETS/state-space equivalents) handle SKU-count portfolios with holiday calendars, hierarchical reconciliation (MinT), and fallback ladders ending at seasonal-naive; statsmodels UnobservedComponents/SARIMAX covers single-series governed models. Every automated pick logs its AIC table and diagnostics for model-risk review. Refits are deployments: versioned, tested, approved — not cron jobs nobody reads.

**Deep stacks.** GluonTS/PyTorch Forecasting/Darts implement DeepAR/N-BEATS/TFT patterns behind shared APIs; training uses global windows across series with quantile losses; serving distinguishes cold-start (zero-shot foundation model or cross-learning) from warm-start (fine-tuned or hybrid). Feature stores supply covariates; monitoring tracks quantile coverage calibration, not just point error. Compute budgets decide architecture: N-HiTS/TimesFM-scale efficiency work exists because thousands-of-series × hourly-frequency inference is real money.

**Governance reality check.** Any of these inside pricing/capital becomes an SR 11-7-governed model: documented assumptions, independent validation, benchmark floors, challenger models, and kill criteria. The fanciest transformer ships with a seasonal-naive shadow and gets compared weekly.

## Tradeoffs & when NOT to use it

- **Don't use Prophet for financial prices/returns**: no volatility dynamics, no autoregression, intervals that aren't calibrated, and trend extrapolation that will happily project a bubble. It answers "how much will we sell," not "where will this trade."
- **GARCH doesn't forecast direction** — pairing it with a mean model is mandatory; alone it's half a model. And its Gaussian-QMLE standard errors understate uncertainty under fat tails.
- **State space/Kalman assumes linearity-Gaussianity**; heavy-tail innovations or switching dynamics need particle filters/regime models. Over-parameterized hidden states silently absorb noise.
- **Deep forecasters need breadth, not length**: hundreds/thousands of related series minimum; a single 200-point series belongs to ETS/ARIMA. Quantile coverage requires explicit calibration checks — quantile loss ≠ calibrated quantiles out of sample.
- **Foundation models are baselines, not oracles**: zero-shot quality varies wildly by domain (finance microstructure ≠ web traffic), intervals undertrained for tails, and licensing/reproducibility questions remain for audit-heavy contexts.
- **EWMA/GARCH horizon scaling**: √t aggregation under independence is wrong under persistence — using it for multi-day VaR understates tail risk systematically (see T24-ts-validation for honest evaluation).

## Interview questions

### Q1 — What stylized fact does GARCH exist to capture, and how?
**Testing:** motivation before mechanics.
**Answer:** Volatility clustering: squared/absolute returns are positively autocorrelated for days-to-weeks while returns themselves are nearly unpredictable (Mandelbrot 1963 observed it; Engle formalized 1982). GARCH(1,1) makes conditional variance a recursive function of last shock and last variance: σ²_t = ω + αε²_{t−1} + βσ²_{t−1}; typical daily equities α≈0.05-0.12, β≈0.85-0.93, persistence 0.97-0.99 — shocks decay slowly (half-life ≈ ln0.5/ln0.98 ≈ 34 days).
**Follow-up trap:** *"So returns are autocorrelated?"* — No: levels barely are (that's market efficiency); their MAGNITUDES are. Conflating the two is the tell of someone who hasn't looked at acf(r²) plots.

### Q2 — Your GARCH persistence is 0.995. What breaks and what do you do?
**Testing:** boundary-condition literacy.
**Answer:** Near-IGARCH: variance forecasts barely mean-revert; unconditional variance ω/(1−α−β) explodes numerically (0.995 → multiplier 200); 10-day VaR under √10-scaling badly understates risk since shocks persist across the horizon; estimation becomes fragile. Responses: check for structural breaks/regime change inflating persistence (split-sample fits), consider EGARCH/GJR for asymmetry, use heavier tails (t-innovations), or move to realized-vol methods with intraday data.
**Follow-up trap:** *"Persistence >1 then?"* — Nonstationary variance (unit root in variance); either genuinely explosive regime (COVID onset) or misspecified mean model leaking into variance; don't just clip it — diagnose.

### Q3 — Explain the Kalman gain to a product manager.
**Testing:** can you compress math without lying?
**Answer:** It's the optimal blend weight between your prediction and the new measurement: K = P_prediction/(P_prediction + R_noise). When your internal estimate is confident (small P), K→0 and you mostly ignore noisy data; when measurements are precise (small R), K→1 and you snap to them. Every step costs one multiply — which is why it ran on Apollo guidance hardware in 1960 and runs on every GPS chip now.
**Follow-up trap:** *"What if my noise isn't Gaussian?"* — The recursion stays the optimal LINEAR filter (MMSE among linear updates) but stops being globally optimal; particle filters or robust variants take over for heavy tails/multimodality.

### Q4 — Filtered vs smoothed estimates: which goes where in a live system, and what's the leakage angle?
**Testing:** operational discipline (the JD's core theme).
**Answer:** Filtered (data ≤ t) feed live decisions and any feature used for next-period predictions; smoothed (all data, including future) is for retrospective analysis only. Leakage trap: backtesting features computed from smoothed states (or full-sample fitted parameters, or full-sample scalers) smuggles future information into each historical decision — inflating backtests exactly like scaler-fit-on-full-data does in supervised ML. Rule: everything touching time t must be recomputable from data ≤ t.
**Follow-up trap:** *"Even for exploratory research?"* — Research can explore smoothed views, but validation numbers must come from the filtered pipeline; mixing them is how desks ship strategies whose Sharpe evaporates live.

### Q5 — Why are Prophet's default uncertainty intervals criticized? What would you ship instead?
**Testing:** tool skepticism beyond marketing.
**Answer:** They're generated by simulating future trend pivots from the historical changepoint frequency and blending residual noise — a heuristic that ignores parameter uncertainty, seasonality uncertainty, and autoregressive structure; empirical coverage routinely misses nominal rates (e.g., nominal 80% bands covering far less in volatile regimes). Ship instead: conformal-calibrated residuals (empirical quantiles of rolling one-step errors), quantile-loss models, or bootstrap simulation respecting residual autocorrelation — then verify coverage empirically on holdouts.
**Follow-up trap:** *"Just crank interval width until coverage passes?"* — That fixes marginal coverage but destroys sharpness and can still be miscalibrated conditionally (coverage varying by season/regime); conformal variants (weighted/adaptive) target conditional validity more honestly.

### Q6 — Compare N-BEATS and TFT: what problem shape favors each?
**Testing:** architecture literacy tied to use cases.
**Answer:** N-BEATS: univariate-friendly, doubly-residual fully-connected blocks, optionally constrained to trend/seasonality bases — wins on pure pattern extrapolation with many related series (M4), minimal covariate machinery, fast. TFT: built for heterogeneity — variable-selection networks rank covariates, static encoders condition on entity metadata, interpretable attention spans lookback windows, quantile outputs — favored when rich covariates/static attributes exist (retail with promos/prices, energy with weather). If your data is basically a matrix of series: N-BEATS/N-HiTS. If it's series × dozens of mixed-type features: TFT.
**Follow-up trap:** *"Which is SOTA?"* — Wrong frame: M5 showed LightGBM with lag features beating most neural nets on tabular retail; "SOTA" is dataset-shaped. Benchmarks must include boosted trees and seasonal-naive floors, always.

### Q7 — What changes with pretrained time-series foundation models like TimesFM?
**Testing:** currency on the 2024+ landscape with judgment.
**Answer:** Zero-shot forecasting from ~100B pretrained timepoints (Google Trends/Wikipedia/synthetic; TimesFM ~200M params, decoder-only, patched inputs) collapses cold-start cost: new products/markets get instant baselines without per-series fitting. Realistic role: floor-setter and ensemble member, fine-tuned where data accumulates. Limits: interval calibration lags point accuracy, domain shift hurts (microstructure ≠ web traffic), and auditability/licensing complicate bank deployment.
**Follow-up trap:** *"So classical forecasting is dead?"* — No: governed single-series models (state space/GARCH) still own interpretability, tiny-data regimes, and regulatory contexts; foundation models enter as challengers, and the honest answer is ensemble-with-monitoring, not replacement.

### Q8 — Walk through building tomorrow's 1-day VaR input from a GARCH model.
**Testing:** finance wiring beyond textbook fitting.
**Answer:** Estimate GARCH(1,1)-t on return history; compute today's σ̂²_{t+1} = ω + αε²_t + βσ²_t; run filtered historical simulation: rescale each historical shock z_i = r_i/σ_i by σ̂_{t+1}/σ_t to form tomorrow's scenario set; read the 1% quantile → VaR. Multi-day: iterate the variance recursion forward (no naive √t scaling under persistence 0.98). Then the whole thing enters backtesting: Kupiec unconditional-coverage and Christoffersen independence tests on violation counts/clustering (see T24-risk-metrics).
**Follow-up trap:** *"Why t-innovations?"* — Daily equity residuals are fat-tailed (kurtosis ~3-6 after GARCH); Gaussian QMLE underestimates tail quantiles precisely where VaR lives. Student-t (ν≈5-8 estimated) or skewed-t fixes quantile bias at trivial cost.

### Q9 — State space subsumes ARIMA and ETS. Why does anyone still fit ARIMA directly?
**Testing:** understanding equivalence vs convenience.
**Answer:** Mathematically interchangeable — ARIMA(p,d,q) has exact state-space form, and every ETS combo maps to a structural model with known likelihood (Hyndman et al.). Practitioners keep direct forms because: identification rituals (ACF/PACF, differencing tests) map cleanly onto ARIMA orders; Box-Jenkins diagnostics are standardized in validation documents; closed-form forecast variance formulas are simpler to explain to committees; and libraries make the classical path the lowest-friction governed baseline. State space earns its complexity when regressors, missingness, time-varying parameters, or interventions enter.
**Follow-up trap:** *"Then learn only state space?"* — Interviews and audits speak ARIMA/ETS; production extensibility speaks state space; you'll be asked both languages, and translating between them IS the seniority signal.

### Q10 — Volatility forecast evaluation: why is RMSE on σ̂ vs realized r² misleading?
**Testing:** evaluation methodology depth.
**Answer:** Squared returns are a super-noisy proxy of latent variance (noise variance dominates signal — unbiased but R² near zero even for perfect forecasts); rankings flip with proxy noise. Better: QLIKE loss (robust to proxy noise, penalizes under-forecasting asymmetrically), or evaluate against realized variance from intraday sums when available; test economic value via VaR-violation statistics rather than point accuracy. Also compare against the EWMA λ=0.94 floor — beating it out-of-sample is harder than papers imply.
**Follow-up trap:** *"Use realized vol from 5-min bars everywhere then?"* — Microstructure noise contaminates high-frequency estimators below ~5-min sampling (bid-ask bounce); kernel/noise-robust estimators help, but illiquid names lack enough trades — daily-close GARCH persists where liquidity doesn't.

### Q11 — Design the fallback ladder for a 50,000-SKU daily demand system.
**Testing:** production architecture judgment.
**Answer:** Tier by value/volatility: top SKUs get global deep model (TFT/N-BEATS-style with price/promo covariates) + Prophet/ETS challenger; middle gets automated ETS/ARIMA grid with AIC selection; tail gets seasonal-naive/Croston for intermittent demand. All tiers reconciled hierarchically (MinT), monitored by weighted pinball + coverage per tier, with automatic demotion to the benchmark when a tier underperforms its floor for K consecutive weeks. Cold-start SKUs start at foundation-model/attribute-similar pooling until history accrues.
**Follow-up trap:** *"Why keep benchmarks if the fancy tier usually wins?"* — Because regimes rotate: the ladder is your circuit breaker, proving value continuously and capping damage when the deep tier's assumptions break; also regulators/auditors ask what the simple answer would have been.

### Q12 — How do leverage effects show up statistically, and which model catches them?
**Testing:** asymmetry literacy.
**Answer:** Return-vol correlation: negative returns precede larger vol increases than positive returns of equal magnitude (Black 1976 observation; mechanisms: operating leverage/debt-equity ratio rising as equity falls, plus volatility-feedback). Tests: sign-bias regressions of squared standardized residuals on lagged signed returns; in-model: GJR-GARCH threshold γ on negative shocks (typical daily γ≈0.05-0.15) or EGARCH's asymmetric log-variance response. Ignoring it biases down tail forecasts after crashes — exactly when risk models get stress-tested.
**Follow-up trap:** *"Does leverage exist in FX/commodities?"* — Much weaker/absent (no equity-debt channel); gold sometimes shows reverse asymmetry. Model families should follow asset class mechanics, not habit.

## Red flags

- Quoting Prophet intervals as statistical confidence bounds.
- Fitting GARCH and calling the mean forecast done (GARCH predicts variance, not direction).
- Using smoothed Kalman states or full-sample-fitted parameters in walk-forward features.
- Scaling multi-day VaR by √t while quoting 0.98+ persistence.
- Claiming deep forecasters beat classical on a single short series.
- No benchmark ladder: no seasonal-naive/ETS floor beneath the transformer.
- Treating EWMA and GARCH as unrelated (EWMA λ=0.94 IS GARCH(1,1) with ω=0).
- Evaluating vol forecasts by R² against squared returns.

## Cheat card

```
STATE SPACE  y=Za+e ; a=Ta'+w ; Kalman K=P/(P+R)
             filtered<=t (live) vs smoothed all-data (retro ONLY)
             PE-decomposition loglik -> MLE on variances
             ARIMA & ETS both embed exactly -> superset framework
GARCH(1,1)   s2_t=w+a*e2_{t-1}+b*s2_{t-1}; uncond w/(1-a-b); a+b<1
             equities daily: a~0.05-0.12 b~0.85-0.93 pers~0.97-0.99
             half-life ln(.5)/ln(.98)~34d ; leverage: GJR gamma~0.05-0.15
             EWMA lam=.94 == GARCH(1,1) w=0,a=.06,b=.94 (RiskMetrics '96)
             eval: QLIKE not R^2(vs r^2 noise); HAR-RV wins w/ intraday
PROPHET      piecewise trend+L1 changepoints (25 @ first 80%), Fourier
             seas (10 yearly/3 weekly), Stan MAP; intervals SIMULATED,
             not calibrated -> wrap w/ conformal; no vol, no AR terms
DEEP         global models across many series; N-BEATS doubly-residual
             (M4 winner) ; TFT=var-select+static enc+interp attention,
             quantile loss ; DeepAR probabilistic RNN ; M5: GBM+lags
             beat most nets on tabular
FOUNDATION   TimesFM ~200M params/~100B timepoints zero-shot (2024);
             Chronos T5-tokenized; cold-start baselines, calibrate!
VAR WIRING   GARCH->filtered hist sim->quantile; multi-day: iterate
             recursion, NOT sqrt(t) at pers~0.99 ; Kupiec/Christoff tests
```

## Sources

- [Taylor, Letham (2018). Forecasting at Scale (Prophet). PeerJ Preprints](https://peerj.com/preprints/3190/); accessed 2026-08-23
- [Engle (1982). Autoregressive Conditional Heteroscedasticity… Econometrica 50(4)](https://www.jstor.org/stable/1912773); accessed 2026-08-23
- [Bollerslev (1986). Generalized Autoregressive Conditional Heteroskedasticity. J. Econometrics 31](https://www.sciencedirect.com/science/article/abs/pii/0304407686900631); accessed 2026-08-23
- [J.P.Morgan/Reuters (1996). RiskMetrics Technical Document, 4th ed. (EWMA λ=0.94)](https://www.msci.com/documents/10199/59156538/JPMORGAN-RiskMetrics-TechnicalDocument-46b9e6a8-6613-4d1f-8c5b-4dc4ce733310.pdf); accessed 2026-08-23
- [Oreshkin et al. (2019). N-BEATS: Neural Basis Expansion Analysis for Interpretable Time Series Forecasting (M4 winner)](https://arxiv.org/abs/1905.10437); accessed 2026-08-23
- [Lim, Arik, Loeff, Pfister (2021). Temporal Fusion Transformers](https://arxiv.org/abs/1912.09363); accessed 2026-08-23
- [Das et al. (2024). A Decoder-Only Foundation Model for Time-Series Forecasting (TimesFM)](https://arxiv.org/abs/2310.10688); accessed 2026-08-23
- [Corsi (2009). A Simple Approximate Long-Memory Model of Realized Volatility (HAR)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1415168); accessed 2026-08-23
- [Hyndman & Athanasopoulos. FPP3, ch. Exponential smoothing & dynamic harmonic regression](https://otexts.com/fpp3/expsmooth.html); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
