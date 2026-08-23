# Stationarity, ACF/PACF, ARIMA/SARIMA, Decomposition — From Scratch

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 3.0h · **Prereqs:** T03-linear-models · **Updated:** 2026-08-23
> **Module id:** `T24-time-series-core` · **Tags:** timeseries, critical

## The 30-second version

Classical forecasting rests on one assumption you must earn before anything else works: *stationarity* — the series' distributional rules (mean, variance, autocovariance) don't drift over time. Raw prices fail this almost by construction (they accumulate shocks — a random walk never forgets), so the craft is transforming to stationary form: difference out trends, seasonally difference out cycles, log away multiplicative growth. You diagnose the result with two curves: the ACF (autocorrelation vs lag), which decays geometrically for an AR process and cuts off after q lags for an MA, and the PACF, its mirror twin. Those signatures let you pick ARIMA orders by eye, then refine with AIC/BIC. The machinery itself dates to Yule (1927) and was codified in Box-Jenkins (1970): fit ARMA(p,q) to differenced data, check residuals look like white noise (Ljung-Box), iterate. The trap that separates practitioners from tourists: a regression between two independent trending series looks overwhelmingly significant (Granger-Newbold 1974 found nominal-5% tests rejecting most of the time between independent random walks), which is why every serious pipeline runs a unit-root test (ADF, 1979) before trusting any level relationship. Decomposition (classical, then STL 1990, then Census X-13) splits a series into trend + seasonal + remainder so each component can be modeled or removed separately. Everything modern — Prophet, state space, deep forecasters (T24-time-series-modern), honest backtests (T24-ts-validation) — sits on this substrate.

## Why this gets asked

Because it is simultaneously the cheapest way to screen for statistical literacy and the fastest way to expose someone who has only ever called `auto_arima`. Interviewers at quant funds and bank risk desks open here because the failure modes are diagnostic: a candidate who fits ARIMA directly to price levels has just demonstrated spurious-regression blindness; one who differences *and* keeps the intercept interpretation straight shows they understand what integration means economically (returns vs prices — the single most common transformation in finance). The ACF/PACF reading drill tests whether you internalized the duality between time-domain equations and correlation signatures. And "why must residuals be white noise?" probes whether you see the whole apparatus as *extracting structure until nothing structured remains* — a mental model that transfers to every forecasting stack. At D.E. Shaw-class shops expect follow-ons into cointegration ("what if neither series is stationary but a linear combination is?"), fractional differencing (López de Prado's fixed-width window fracdiff preserving memory while achieving stationarity), and how differencing interacts with backtest leakage. If you cannot run this loop by hand, none of those conversations are reachable.

## Lineage

**What came before.** Time series analysis began as astronomy and economics fighting periodicity in noisy records: Schuster's periodogram (1898) hunted hidden cycles; Yule (1927) invented the autoregressive model to explain sunspot wiggles as a pendulum driven by irregular impulses — literally "disturbed harmonic motion." Slutsky (1927) showed the converse: moving averages of pure noise generate smooth pseudo-cycles, proving simple filters create structure. Wold (1938) supplied the load-bearing theorem: any weakly stationary process decomposes exactly into a deterministic part plus an infinite moving average of uncorrelated innovations — which licenses ARMA models as universal approximators of stationary series. Mann and Wald (1943) proved AR coefficient asymptotics; Hurwicz (1950) quantified the small-sample downward bias of AR(1) estimates, roughly −(1+3φ)/T — about −0.04 for φ=0.9 with T=100 observations. Quenouille (1949) characterized partial autocorrelation, giving the PACF its cutoff property.

**Where it stands now.** Box and Jenkins' 1970 monograph (*Time Series Analysis: Forecasting and Control*) industrialized the workflow — identify (ACF/PACF), estimate (MLE/Yule-Walker), diagnose (residual whiteness) — and remains the operating system of classical practice. Dickey and Fuller (1979) turned the unit-root question into a formal hypothesis test with non-standard critical values: −3.43/−2.86/−2.57 at the 1%/5%/10% levels for the constant-only case; Said-Dickey (1984) added augmentation lags to absorb serial correlation; Phillips-Perron (1988) made it nonparametric; KPSS (1992) inverted the hypotheses so confirmation requires *both* tests to agree (classify stationary only when ADF rejects and KPSS fails to reject). Granger and Newbold (1974) documented spurious regression between independent random walks and Phillips (1986) derived why: the usual t/F distributions diverge under the null. Seasonal adjustment became government infrastructure (Census X-11 → X-12 → X-13ARIMA-SEATS; the "airline model" ARIMA(0,1,1)(0,1,1)₁₂ from Box-Jenkins is still the default baseline for monthly data). STL (Cleveland et al., 1990) replaced rigid classical decomposition with locally-weighted loess components robust to outliers and evolving seasonality.

**Where it's heading.** Three directions. First, memory-preserving stationarity: López de Prado popularized fractional differencing (the ARFIMA idea of Granger-Joyeux 1980 / Hosking 1981, d typically 0.1–0.45 for financial returns) precisely because integer differencing deletes the long-memory signal quants get paid to find. Second, structural absorption: every ARIMA-with-dummies problem got reframed as state space (Kalman-filter trend + seasonal + cycle, the backbone of statsmodels UnobservedComponents and Prophet's internals) where parameters can drift — see T24-time-series-modern. Third, benchmark humility: M4 (2018, 100,000 series) showed combinations of classical/statistical methods still beat most fancy ML on aggregate, while M5 (2020, Walmart-scale retail data) crowned gradient-boosted trees with careful features — meaning ARIMA fluency is less about producing forecasts and more about being able to *audit* whatever produced them, and knowing exactly when the classical assumptions quietly break (heteroskedasticity → GARCH; regime shifts → switching models; long memory → fractionality).

---

## Mental model

```
A FORECAST IS A FILTERED PAST. Stationarity = the filter has a stable lens.

  WEAK STATIONARITY (the practical kind):
    E[x_t] = mu              <- same mean everywhere
    Var(x_t) = sigma^2       <- same variance everywhere
    Cov(x_t, x_s) = g(|t-s|) <- covariance depends ONLY on gap, not clock

  THE FAMILY TREE:
    White noise e_t
      -> MA(q):   x_t = e_t + th_1 e_{t-1} + ... + th_q e_{t-q}   [finite echo]
      -> AR(p):   x_t = phi_1 x_{t-1} + ... + phi_p x_{t-p} + e_t [infinite echo]
      -> ARMA(p,q): both
      -> ARIMA(p,d,q): difference d times first  (d=1 turns prices into returns)
      -> SARIMA:  + seasonal copies of everything at lag m

  SIGNATURES (the fingerprint pair):
                 ACF                    PACF
    AR(p)        decays/exponential     CUTS OFF after p
    MA(q)        CUTS OFF after q       decays
    ARMA         mixed decay            mixed decay

  WHY DIFFERENCING WORKS: random walk x_t = x_{t-1} + e_t has
    dx_t = e_t -- differencing converts accumulation into pure innovation.
```

Deeper framing: an AR process is a linear system repeatedly struck by randomness; its ACF shape is the system's impulse response, and stationarity is the condition that strikes eventually wash out rather than accumulate. Differencing asks "is this series accumulating?" — the question behind every price-vs-return decision in finance.

---

## How it actually works

### Stationarity and why levels lie

Weak (covariance) stationarity requires constant mean, constant variance, and autocovariance depending only on lag. An AR(1) x_t = φx_{t−1} + e_t satisfies it iff |φ| < 1; at φ = 1 it becomes a random walk whose variance grows linearly with time (Var after n steps = nσ²_e) and whose sample ACF looks sticky at every lag. Fit a regression of one random walk on another unrelated random walk and OLS reports t-statistics whose null distribution diverges — Granger-Newbold measured rejection rates around 70-76% at the nominal 5% level, and offered a famous field heuristic: when R² exceeds the Durbin-Watson statistic, suspect spuriousness. The fix list hasn't changed since 1974: test for unit roots first; difference or error-correct before regressing; never quote a level-regression R² as evidence.

Two flavors of nonstationarity demand different surgery. A *stochastic* trend (random walk, unit root) needs differencing: subtracting removes accumulated shocks permanently. A *deterministic* trend (x_t = a + bt + stationary noise) needs detrending; differencing it overcorrects, inducing an MA unit root — the overdifferencing pathology (variance inflates, lag-1 autocorrelation lands near −0.5, forecasts oscillate). Nelson-Plosser (1982) applied unit-root logic to 14 US macro annual series and found most behave like unit-root processes — the paper that moved macroeconomics to working in differences. Practical protocol: plot first; test with ADF (H₀: unit root) AND KPSS (H₀: stationary); disagreement means borderline cases needing judgment, not a p-value shrug.

### ADF mechanics without hand-waving

Augmented Dickey-Fuller regresses Δx_t on a constant, the *lagged level* x_{t−1}, and enough lagged differences to mop up serial correlation: Δx_t = α + γx_{t−1} + ΣᵢβᵢΔx_{t−i} + ε_t. H₀ is γ = 0; H₁ is γ < 0 (mean reversion). Under H₀ the regressor x_{t−1} is itself nonstationary, so the t-statistic doesn't follow Student-t — it follows the Dickey-Fuller distribution, compared against tabulated critical values (−2.86 at 5%, constant-only), never t-tables. Augmentation order matters: too few lags leaves residual correlation inflating test size; too many saps power. Schwert's rule of thumb caps lags near ⌊12(T/100)^{1/4}⌋ (≈16 lags at T=500); AIC/BIC selection and Ng-Perron (1995/2001) refinements are standard alternatives. Know the power critique: against persistent-but-stationary alternatives (an AR with φ ≈ 0.97 over T=250), ADF frequently fails to reject even though the series is technically mean-reverting. In finance terms "highly persistent but not quite a walk" gets misclassified — which is why pairs desks demand economic rationale plus cointegration evidence rather than trusting one printout.

### ACF, PACF, and the identification ritual

Sample ACF at lag k divides the lagged cross-product by total squared deviation, judged against ±2/√T bands (the ~95% white-noise envelope). PACF(k) is the last coefficient of an AR(k) fit — correlation between t and t+k *after removing* intermediate lags — computable via the Durbin-Levinson recursion or by solving the Yule-Walker Toeplitz system. Identification folklore: AR(p) ⇒ PACF cuts off at p while ACF tails off geometrically; MA(q) ⇒ mirror image; ARMA mixes both. Reality blurs cutoffs: sampling noise, seasonal spikes at m, 2m, 3m..., and near-cancellation of AR and MA roots make plots misleadingly quiet. Hence Box-Jenkins is a *loop*: propose orders → estimate → check residual whiteness with Ljung-Box Q → adjust. Modern practice delegates the search to information criteria over a grid — AIC = −2logL + 2k, BIC = −2logL + k·ln(T) — where BIC's heavier complexity tax prefers parsimony as T grows. Two caveats worth saying out loud in an interview: Ljung-Box p-values on residuals are optimistic if you selected the model using the same data (degrees of freedom shrink by the number of estimated parameters — use T − p − q), and AIC ranks forecasts but BIC ranks "true order recovery"; they can disagree.

### Estimation: three ways to solve the same AR

For a pure AR(p), Yule-Walker equates theoretical and sample moment conditions: Γ_p φ = γ, a Toeplitz system built from sample autocovariances — cheap and closed-form-ish, but inheriting small-sample bias (Hurwicz: E[φ̂₁] ≈ φ − (1+3φ)/T for AR(1)). Ordinary least squares of x_t on [x_{t−1..t−p}] does slightly better (conditional least squares). Maximum likelihood dominates in short samples and generalizes cleanly to ARMA and missing data; conditional Gaussian MLE reduces to minimizing sum-of-squared one-step-ahead residuals, which is why OLS and conditional MLE coincide for pure AR models. Interviewers care that you know *when* they differ (short samples, near-unit roots, MA terms present) and that Yule-Walker's estimates always satisfy the stationarity region by construction — sometimes a feature, sometimes a lie about data that isn't stationary.

### SARIMA: seasonality as arithmetic

SARIMA(p,d,q)(P,D,Q)_m applies the whole ARIMA apparatus twice: non-seasonal polynomials at lags 1..p,q and seasonal polynomials at multiples of m (12 for monthly, 52 weekly, 7 daily-of-week). Multiplicative notation means products of polynomials, e.g. (1−φB)(1−ΦB¹²)x_t — a shock echoes at lag 1 AND at lags 12, 13, 24... The canonical airline model ARIMA(0,1,1)(0,1,1)₁₂ — log-levels differenced once for trend and once seasonally, each leaving a single MA term — fits an enormous share of real monthly series and should be your reflex baseline before anything fancier. Diagnostic shortcut: after proper D, residual seasonal spikes at lags m, 2m tell you whether you need the Q side.

### Decomposition: separate, then conquer

Classical decomposition writes y_t = m_t + s_t + r_t (additive) or multiplicative (⇒ log-transform to additivity). Moving-average classical versions are rigid: identical seasonal shape every year, no outlier robustness. STL (loess-based, Cleveland et al. 1990) lets trend bend and seasonality evolve, controls smoothness with explicit window parameters, and handles missing values natively in modern implementations; Census X-13ARIMA-SEATS wraps RegARIMA pre-adjustment (calendar effects, outliers) around ARIMA-model-based extraction and remains the statutory standard for official statistics. In quant work decomposition is usually a *diagnostic*, not the deliverable: adjusting first risks double-counting seasonality your downstream model could learn jointly; adjustment filters also distort variance, and X-13 outputs factors rather than honest confidence intervals.

---

## Build it from scratch

Runnable numpy-only lab: ADF-style unit-root check, differencing ladder on a trend+seasonal series, and AR(2) recovery via Yule-Walker:

```python
import numpy as np

rng = np.random.default_rng(42)

# ---------- ACF / sample autocorrelation ----------
def acf(x, k):
    x = np.asarray(x, float); x = x - x.mean()
    c0 = float(x @ x)
    return np.array([1.0] + [float(np.sum(x[t:] * x[:-t])) / c0 for t in range(1, k+1)])

# ---------- ADF-style stationarity check ----------
def adf(x, lags=4):
    """Augmented Dickey-Fuller style regression:
    dx_t = a + b*x_{t-1} + sum_i g_i dx_{t-i} + e_t
    H0: b = 0 (unit root). Return t-stat of b_hat.
    DF critical values (~250 obs, constant): -3.43 (1%), -2.86 (5%), -2.57 (10%)."""
    x = np.asarray(x, float)
    dx = np.diff(x)
    T = len(dx) - lags
    y = np.empty(T); X = np.empty((T, lags + 2))
    for i in range(T):
        j = i + lags                      # index of dx_t
        y[i] = dx[j]
        X[i, 0] = 1.0
        X[i, 1] = x[j]                    # lagged LEVEL (the DF term)
        X[i, 2:] = dx[j-lags:j][::-1]     # lagged differences ('augmented' part)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = float(resid @ resid) / (T - X.shape[1])
    se_b = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    return float(beta[1]), float(beta[1]) / se_b

CRIT = {0.10: -2.57, 0.05: -2.86, 0.01: -3.43}
def adf_verdict(x, lags=4):
    b, t = adf(x, lags)
    levels = [a for a, c in CRIT.items() if t <= c]
    if levels:
        best = min(levels)                # most stringent rejection level
        print(f"ADF b_hat={b:+.4f} t={t:6.2f} -> reject unit root at {best*100:.0f}% level")
    else:
        print(f"ADF b_hat={b:+.4f} t={t:6.2f} -> FAIL to reject unit root (nonstationary)")

# ---------- synthetic series ----------
T = 300
t_idx = np.arange(T)

rw    = np.cumsum(rng.normal(0, 1, T))                      # random walk (nonstationary)
white = rng.normal(0, 1, T)                                 # stationary baseline

# ---------- differencing demo on a trend+seasonal series ----------
season_amp, slope = 4.0, 0.08
y = 50 + slope*t_idx + season_amp*np.sin(2*np.pi*t_idx/12) + rng.normal(0, 1, T)

d1  = np.diff(y, 1)                 # removes trend, leaves seasonal cycle
d12 = y[12:] - y[:-12]              # seasonal difference removes the cycle
dd  = d12[1:] - d12[:-1]            # both -> stationary-ish noise

for name, s in [("level y", y), ("diff-1", d1), ("seas-diff-12", d12), ("both", dd)]:
    a = acf(s, 12)
    print(f"{name:14s} acf[1]={a[1]:+.2f}  acf[12]={a[11]:+.2f}  |acf|>2/sqrt(N) at lags:",
          [i+1 for i, v in enumerate(a) if abs(v) > 2/np.sqrt(len(s))][:8])

adf_verdict(y); adf_verdict(d1); adf_verdict(dd); adf_verdict(rw); adf_verdict(white)

# ---------- AR(2) fit via Yule-Walker ----------
phi_true = np.array([0.75, -0.25])
x = np.empty(4000); x[:2] = rng.normal(0, 1, 2)
e = rng.normal(0, 1, 4000)
for tt in range(2, 4000):
    x[tt] = phi_true @ x[tt-2:tt][::-1] + e[tt]
x = x[200:]                                  # burn-in

g = acf(x, 2)
R = np.array([[1.0, g[1]], [g[1], 1.0]])     # Toeplitz correlation matrix
r = g[1:]
phi = np.linalg.solve(R, r)
resid = x[2:] - phi[0]*x[1:-1] - phi[1]*x[:-2]
sigma2_e = float(resid @ resid) / len(resid)
print("Yule-Walker AR(2): phi =", np.round(phi, 3), " true =", phi_true,
      " sigma_e =", round(np.sqrt(sigma2_e), 3), "(true 1.0)")
roots = np.roots([1, -phi[0], -phi[1]])
print("characteristic roots:", np.round(roots, 3),
      "-> stationarity holds iff both |root| > 1")
```

Actual output (executed before embedding):

```text
level y        acf[1]=+0.96  acf[12]=+0.87  |acf|>2/sqrt(N) at lags: [1, 2, 3, 4, 5, 6, 7, 8]
diff-1         acf[1]=+0.31  acf[12]=+0.44  |acf|>2/sqrt(N) at lags: [1, 2, 3, 5, 6, 7, 8, 9]
seas-diff-12   acf[1]=+0.09  acf[12]=-0.07  |acf|>2/sqrt(N) at lags: [1, 3, 13]
both           acf[1]=-0.37  acf[12]=+0.13  |acf|>2/sqrt(N) at lags: [1, 2, 3, 11, 12, 13]
ADF b_hat=-0.0431 t= -2.78 -> reject unit root at 10% level
ADF b_hat=-1.2210 t=-14.14 -> reject unit root at 1% level
ADF b_hat=-3.6794 t=-13.98 -> reject unit root at 1% level
ADF b_hat=-0.0139 t= -1.32 -> FAIL to reject unit root (nonstationary)
ADF b_hat=-0.9653 t= -7.89 -> reject unit root at 1% level
Yule-Walker AR(2): phi = [ 0.758 -0.261]  true = [ 0.75 -0.25]  sigma_e = 1.005 (true 1.0)
characteristic roots: [0.379+0.342j 0.379-0.342j] -> stationarity holds iff both |root| > 1
```

Reading the output: the raw level's ACF sticks near +0.9 at every lag — the visual signature of accumulated shocks — yet ADF only rejects at 10%, illustrating the test's powerlessness against deterministic trends with constant-only specification (add `X[i,1] = t_idx[j]`-style columns for the trend-augmented variant). One ordinary difference drops acf[1] to +0.31 but leaves the seasonal spike (acf[12]=+0.44); seasonal differencing alone flattens the picture best here. The Yule-Walker estimates land within ~0.01-0.02 of truth on 3,800 post-burn-in points, and complex-conjugate roots inside the unit circle confirm stationarity (equivalently φ₁+φ₂<1, φ₂−φ₁<1, |φ₂|<1 — the stationarity triangle). Swap `phi_true` to `[1.0, 0.0]` and watch roots collapse onto the unit circle: that boundary is exactly what ADF polices.

---

## How it's done in production

**Libraries, not loops.** Python shops live in statsmodels (`ARIMA`, `SARIMAX`, `adfuller`, `kpss`, `STL`, `UnobservedComponents`) and pmdarima (`auto_arima`, stepwise AIC search per Hyndman-Khandakar 2008); R inherits the same lineage through forecast::auto.arima. Production wrappers pin versions, cache fitted parameters, and treat refits as deployments — a weekly-refit ARIMA inside a risk system is a governed model with change management (see T24-mrm), not a script.

**Scale changes the game.** Fitting 100,000 series (M4/M5 scale, or a bank's account-level panel) means auto-selection pipelines with fallbacks: try SARIMA grid → fall back to ETS/exponential smoothing → fall back to naive/seasonal-naive benchmarks; monitor per-series MASE against the seasonal-naive so you can prove the fancy layer earns its compute. Caches key on (series hash, frequency, window policy); failures degrade to the benchmark instead of emitting garbage.

**Finance-specific hygiene.** Prices get logged before differencing so differencing yields *returns* (interpretability plus variance stabilization); calendar effects get dummy variables or holiday regressors inside SARIMAX rather than manual patching; volatility clustering is explicitly out of scope for plain ARIMA — production equity-return models pair a thin mean model (often a constant) with GARCH variance (T24-time-series-modern) rather than pretending ARMA terms capture fat tails.

**Governance.** Every automated order-selection decision is logged (chosen orders, AIC table, residual diagnostics, Ljung-Box p-value) because SR 11-7-style validation (T24-mrm) demands reproducibility and effective challenge. Benchmarks ship alongside every model as the honesty floor; a model that cannot consistently beat seasonal-naive does not deploy.

## Tradeoffs & when NOT to use it

- **Structural breaks kill it.** ARIMA assumes the generating process is frozen; policy shifts, product launches, pandemics reset coefficients mid-sample. If breaks dominate, move to state-space with time-varying parameters, rolling refits, or regime-switching models — not bigger AR lags.
- **Nonlinearity is invisible to it.** Threshold effects, asymmetric responses, interactions — ARMA is linear in past values. Boosted trees with engineered features (the M5 winner) win when nonlinearity is real and data is plentiful.
- **Exogenous drivers beyond dummies get clumsy.** SARIMAX carries regressors, but intervention/causal questions are cleaner in interrupted-time-series or causal-impact frameworks built on state space.
- **Integer differencing destroys long memory.** If your edge lives in slow-decaying dependence (Hurst > 0.5), d=1 amputates it; use fractional differencing tuned so the final series passes ADF while retaining maximal memory, or model levels with cointegration/error-correction.
- **Small samples starve order selection.** With 60 observations, AIC grids overfit silently; constrain to low orders, prefer BIC, validate out-of-sample (walk-forward, per T24-ts-validation) rather than trusting in-sample criteria.
- **Forecast intervals understate reality.** Gaussian innovations plus ignored parameter uncertainty ⇒ bands too narrow; heteroskedasticity alone can halve effective coverage. Scale residuals with GARCH before quoting risk numbers.

## Interview questions

### Q1 — What is spurious regression and why should a quant care?
**Testing:** the foundational scar tissue of the field.
**Answer:** Regressing one integrated I(1) series on another independent I(1) series yields significant slopes far above nominal size — Granger-Newbold (1974) measured ~70-76% rejection at the 5% level between independent random walks, and Phillips (1986) showed the t/F statistics diverge under the true null. You "find" relationships that are accumulation artifacts; any factor study regressing price levels without unit-root treatment is suspect regardless of R².
**Follow-up trap:** *"So difference everything before regressing?"* — Not blindly: if two I(1) series share a stationary linear combination (cointegration), the right object is the error-correction model (Engle-Granger 1987), which keeps the long-run tie while modeling short-run dynamics. Careless differencing throws away exactly the equilibrium information pairs trades monetize.

### Q2 — Walk me through ADF's regression and its null. Why no t-tables?
**Testing:** mechanical correctness beneath the library call.
**Answer:** Δx_t = α + γx_{t−1} + ΣβᵢΔx_{t−i} + ε_t; H₀ γ=0 (unit root), H₁ γ<0 (mean reversion). Under H₀ the lagged level is nonstationary, so the OLS t-stat converges to a functional of Brownian motion — the Dickey-Fuller distribution — hence tabulated critical values (−2.86 at 5%, constant-only) replace t-tables. Augmentation lags whiten residuals so the test has correct size (Said-Dickey 1984).
**Follow-up trap:** *"My ADF p-value is 0.08 — nonstationary?"* — Unknowable from one printout: low power against persistent-stationary alternatives (φ≈0.9 ARs often fail to reject), specification choice (constant vs trend) moves critical values, and lag selection moves results. Pair with KPSS's reversed null, inspect ACF decay, decide with context.

### Q3 — How do you detect overdifferencing and what did you break?
**Testing:** transformations as tools vs rituals.
**Answer:** Signs: lag-1 autocorrelation pushed strongly negative (near −0.5), inflated variance versus once-differenced data, seasonal spikes flipping sign, fitted MA coefficients hugging −1 (non-invertible MA unit root; oscillating forecasts). Mechanically, differencing a trend-stationary series manufactures an MA(1) with θ→−1 and negatively correlates consecutive observations.
**Follow-up trap:** *"Doesn't more differencing always stabilize?"* — The opposite: each extra difference adds a zero at z=1 to the MA polynomial and inflates variance; beyond true integration order, forecast accuracy degrades monotonically.

### Q4 — Given only ACF/PACF plots, propose orders and defend them.
**Testing:** the Box-Jenkins identification ritual, live.
**Answer:** Count the signatures: PACF cutoff at p with geometrically decaying ACF ⇒ start AR(p); ACF cutoff at q with decaying PACF ⇒ MA(q); mixed decay ⇒ low-order ARMA. Check seasonal lags (m, 2m) for spikes demanding SARIMA terms; verify stationarity (slow ACF decay ⇒ difference first). Then confirm with AIC/BIC grid and residual diagnostics — plots propose, criteria dispose.
**Follow-up trap:** *"PACF cuts off exactly at 2, done?"* — Sampling noise makes exact cutoffs rare; near-cancellation can hide real structure; always fit the neighbor candidates (AR(1)/AR(3)) and compare AIC. Identification is a starting point, never a verdict.

### Q5 — Derive or explain Yule-Walker estimation and its bias.
**Testing:** do you know what the library actually solves?
**Answer:** Match theoretical AR(p) autocovariances to sample ones: Γ_p φ = γ where Γ_p is the Toeplitz matrix of γ(0..p−1); solve the banded system (Durbin-Levinson does it in O(p²)). Bias: sample autocorrelations of persistent series are biased downward, dragging coefficient estimates with them — Hurwicz's AR(1) result E[φ̂] ≈ φ − (1+3φ)/T means φ=0.9 with T=100 averages ~−0.037 off. MLE corrects much of this in small samples.
**Follow-up trap:** *"So Yule-Walker is useless?"* — No: it's O(p²)-fast, guarantees stationary estimates, and is the standard initializer inside MLE routines. Just don't quote its standard errors in tiny samples.

### Q6 — Why must ARIMA residuals be white noise? What do you do when they aren't?
**Testing:** whether you see the model's purpose, not just its syntax.
**Answer:** ARMA machinery works by absorbing all linear structure into the AR/MA polynomials; leftover autocorrelation in residuals means unmodeled structure — biased parameters, invalid prediction intervals, systematically exploitable patterns (in finance, that's alpha left on the table or unpriced risk). Remedies ladder up: raise orders, add seasonal terms, add exogenous regressors, then switch families (GARCH for variance structure, state space for drifting params, ML features for nonlinearity).
**Follow-up trap:** *"Ljung-Box p = 0.9, all good?"* — Beware double duty: LB on residuals of a model selected by minimizing autocorrelation-related criteria loses power and size calibration; supplement with ACF eyeballing, out-of-sample checks, and tests robust to selection (e.g., bootstrap).

### Q7 — Your monthly sales series trends and has December spikes. Full recipe?
**Testing:** end-to-end pipeline fluency.
**Answer:** Log-transform if amplitude scales with level; run ADF/KPSS on logs and on log-differences; typically take d=1 and D=1 (m=12); expect the airline model ARIMA(0,1,1)(0,1,1)₁₂ to be competitive; validate residual ACF at seasonal multiples; compare against seasonal-naive via MASE on a holdout year; produce prediction intervals and sanity-check their expansion over horizons.
**Follow-up trap:** *"Why log first rather than difference first?"* — Order matters: log-then-difference gives percentage changes (stable variance, interpretable); difference-then-log distorts and leaves heteroskedasticity. Also log of zero/negative values is undefined — offset or use Box-Cox with λ chosen from the data.

### Q8 — Explain the characteristic equation and the stationarity triangle for AR(2).
**Testing:** algebra-to-dynamics translation.
**Answer:** AR(2): x_t = φ₁x_{t−1} + φ₂x_{t−2} + ε_t has characteristic polynomial z² − φ₁z − φ₂; stationarity ⇔ both roots outside the unit circle ⇔ the three inequalities φ₁+φ₂ < 1, φ₂−φ₁ < 1, |φ₂| < 1 (the "triangle"). Roots can be real (two exponential decay modes) or complex conjugates (damped oscillation — the stochastic-cycle case; modulus governs decay rate, angle the pseudo-period).
**Follow-up trap:** *"Roots inside the circle then?"* — Inside means explosive/nonstationary; ON the circle means unit roots (ADF's territory); complex roots NEAR the circle give long-lived cycles that look like trends in short samples — a classic false-unit-root source.

### Q9 — When would you refuse to difference and model levels anyway?
**Testing:** knowing what differencing costs, not just what it fixes.
**Answer:** Three cases: deterministic-trend series (detrend instead; differencing overcorrects into overdifferencing); cointegrated systems (model levels jointly with error-correction so equilibrium relationships survive); fractional/long-memory series (integer d=1 deletes the slow hyperbolic ACF decay — use ARFIMA/fractional differencing with d≈0.1-0.45 chosen to just achieve stationarity). In quant practice the third is the money case: López de Prado's fracdiff exists because stationarity-by-amputation destroys predictive memory.
**Follow-up trap:** *"Isn't stationarity non-negotiable for modeling?"* — It's negotiable per-model: state-space methods handle some nonstationarity natively; tree models on engineered rolling features tolerate trending targets better than theory suggests; what's truly non-negotiable is that whatever you validate must match what you deploy (transform consistency across train/serve — see T24-ts-validation).

### Q10 — How do forecast intervals evolve with horizon for ARIMA, and why?
**Testing:** understanding of forecast-variance propagation.
**Answer:** For AR(1) with innovation variance σ², h-step forecast variance accumulates as σ²·Σⱼ₌₀^{h−1}φ^{2j}, saturating at σ²/(1−φ²): intervals widen fast initially then plateau at the unconditional variance — mean reversion caps uncertainty. For I(1) processes variance grows without bound (∝ h·σ²): random-walk bands fan out forever. MA(q) forecasts collapse to the mean after q steps with flat intervals thereafter.
**Follow-up trap:** *"Do these bands include parameter uncertainty?"* — Standard software intervals usually don't (they condition on estimated parameters); with short samples that omission materially narrows bands. Bootstrap or Bayesian posterior-predictive intervals fix it honestly.

### Q11 — What is the airline model and why does it deserve its fame?
**Testing:** pattern-library depth beyond textbook notation.
**Answer:** ARIMA(0,1,1)(0,1,1)₁₂ on log levels: one non-seasonal MA(1) after regular differencing, one MA(1) after seasonal differencing. Box-Jenkins found it fit airline passenger data — and since then an outsized share of monthly business series — remarkably well: log stabilizes multiplicative growth, d=1 removes stochastic trend, D=1 removes evolving seasonality, and the two MA terms capture smooth, locally-adjusted deviations. Its two parameters have direct interpretations (level-noise smoothing, seasonal-noise smoothing), making it robust where higher-order competitors overfit.
**Follow-up trap:** *"When does it fail?"* — Changing seasonal amplitude faster than D=1 tracks, calendar irregularities (Easter drift, trading-day effects — need RegARIMA dummies), structural breaks, or strong holiday pre-shifts; then X-13/STL preprocessing or explicit regressors enter.

### Q12 — Compare STL, X-13, and SARIMA for handling seasonality in a production pipeline.
**Testing:** tool-selection judgment with tradeoff awareness.
**Answer:** STL: flexible evolving seasonality, robust versions resist outliers, great for exploration and feature-building, but no native forecasting (combine with a trend forecaster like ARIMA-on-STL-remainder) and intervals need care. X-13ARIMA-SEATS: statutory-grade adjustment with calendar/regressor handling and model-based extraction; heavy, opinionated, audit-friendly. SARIMA: joint modeling keeps uncertainty coherent (intervals reflect everything) and forecasts directly, at the cost of fixed seasonal shape assumptions unless you go full state-space. Production answer usually: SARIMAX/state-space for forecasting systems; STL for monitoring dashboards; X-13 where regulatory comparability matters.
**Follow-up trap:** *"Why not adjust once centrally, then let everyone model adjusted data?"* — Adjustment choices embed assumptions downstream consumers inherit blindly; variance distortion and revision policies (X-13 revises factors as data arrives) leak inconsistency into dependent models. Central adjustment needs governance — same discipline as any shared feature store.

## Red flags

- Fitting ARMA directly to price/index levels without any stationarity discussion.
- Quoting R² or t-stats from a levels regression on trending series.
- Treating ADF p-values as binary truth with no mention of power or KPSS cross-check.
- "I always difference twice to be safe" — overdifferencing blindness.
- Reading ACF/PACF as exact order pickers with no mention of sampling noise.
- Forecast intervals presented as exact when parameter uncertainty and heteroskedasticity are ignored.
- No benchmark instinct: never comparing against naive/seasonal-naive baselines.
- Confusing deterministic and stochastic trends (detrend vs difference).
- Ljung-Box treated as proof of adequacy despite post-selection optimism.

## Cheat card

```
STATIONARY  E[x]=mu const · Var const · Cov depends only on |t-s|
            AR(1): |phi|<1 ; phi=1 => RW, Var_n = n*sigma^2
UNIT ROOT   ADF: dx_t = a + g*x_{t-1} + lagged dx + e ; H0 g=0
            crit vals (const-only): -3.43/-2.86/-2.57 @ 1/5/10%
            low power vs phi~0.95 -> pair with KPSS (reversed H0)
SPURIOUS    GN '74: indep RWs regressed -> ~70-76% "sig" at 5%
            heuristic: R^2 > DW  =>  worry
DIFFERENCING d=1 kills stochastic trend; D=1@m kills seasonal
            overdiff: acf[1] ~ -0.5, var up, MA theta -> -1
FINGERPRINT ACF geo-decay + PACF cut@p => AR(p) (mirror => MA(q))
ESTIMATION  YW: Gamma_p phi = gamma (Toeplitz, fast, biased
            ~-(1+3phi)/T) ; OLS=cond-MLE for pure AR ; MLE best small-T
ORDERS      AIC=-2L+2k ; BIC=-2L+k ln T (parsimony grows w/ T)
SARIMA      (p,d,q)(P,D,Q)_m ; airline (0,1,1)(0,1,1)_12 on logs
DECOMP      y = m+s+r ; STL loess-flexible ; X-13 statutory
FORECASTS   AR(1) var_h = s^2*(1-phi^2h)/(1-phi^2) -> plateaus
            RW var ~ h*s^2 -> fans forever ; MA(q) flat after q
FINANCE     log prices -> diff = returns ; vol clustering => GARCH
            long memory lost at d=1 -> fracdiff d~0.1-0.45
```

## Sources

- [Box, Jenkins et al. (2015). Time Series Analysis: Forecasting and Control, 5th ed. (Wiley)](https://www.wiley.com/en-us/Time+Series+Analysis%3A+Forecasting+and+Control%2C+5th+Edition-p-9781118675021); accessed 2026-08-23
- [Granger, Newbold (1974). Spurious Regressions in Econometrics. Journal of Econometrics 2(2)](https://ideas.repec.org/a/eee/econom/v2y1974i2p111-120.html); accessed 2026-08-23
- [Dickey, Fuller (1979). Distribution of the Estimators for Autoregressive Time Series with a Unit Root. JASA 74](https://www.tandfonline.com/doi/abs/10.1080/01621459.1979.10482531); accessed 2026-08-23
- [Kwiatkowski et al. (1992). Testing the Null Hypothesis of Stationarity Against the Alternative of a Unit Root (KPSS). J. Econometrics](https://www.sciencedirect.com/science/article/abs/pii/030440769290104Y); accessed 2026-08-23
- [Hyndman & Athanasopoulos. Forecasting: Principles and Practice (otexts), ch. Stationarity & ARIMA](https://otexts.com/fpp2/stationarity.html); accessed 2026-08-23
- [statsmodels documentation: adfuller / ARIMA / STL](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html); accessed 2026-08-23
- [NIST/SEMATECH e-Handbook: Box-Jenkins Model Identification](https://www.itl.nist.gov/div898/handbook/pmc/section4/pmc44.htm); accessed 2026-08-23
- [Cleveland, Cleveland, McRae, Terpenning (1990). STL: A Seasonal-Trend Decomposition Procedure Based on Loess. J. Official Statistics 6(1)](https://www.scb.se/contentassets/ca21efb41fee47d293b7505f6009876a/stl-a-seasonal-trend-decomposition-procedure-based-on-loess.pdf); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
