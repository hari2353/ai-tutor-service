# The Python Quant Stack: QuantLib, cvxpy, PyPortfolioOpt, arch, TA-Lib, Numba in Anger

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-derivatives, T24-portfolio, T24-time-series-core · **Updated:** 2026-09-04
> **Module id:** `T24-quant-python-stack` · **Tags:** finance,python,critical

## The 30-second version

T24's earlier modules teach the mathematics — Black-Scholes by replication, MVO by Lagrangian, GARCH by maximum likelihood. This module is the hands-on tier: the production Python library for each concept, what its API actually wants from you, and where each one lies. The core stack: **QuantLib** (pricing infrastructure: curves, vol surfaces, engines, calendars — a C++ library with a Python skin and API ergonomics to match), **cvxpy** (convex optimization as math notation: portfolio allocation as a `Problem(Minimize(risk), [weights >= 0, sum == 1])` you can read aloud), **PyPortfolioOpt** (the packaged MVO/Black-Litterman/HRP work Quant people actually ship), **arch** (ARCH/GARCH family estimation with proper likelihoods, not `numpy` regression hacks), **Statsmodels** (the econometrics backbone), **TA-Lib** (150+ technical indicator functions as a C library), and **Numba** (the JIT that makes Python Monte Carlo competitive). The interview divide this module targets: candidates who can derive Black-Scholes on the whiteboard but have never built a discount curve, versus those who can. The honest caveat, from the corpus's own best quant post: the mistake isn't using the "wrong" library — it's learning libraries instead of the mathematics underneath them.

## Why this gets asked

Because quant and quant-adjacent interviews (hedge funds, banks' model validation teams, fintech risk, prop shops' research-support roles) run a fixed practical probe: "how would you price this in code?", "how do you build the vol surface?", "write me a portfolio optimizer that handles no-short constraints" — and the failure mode is universal: the candidate who aces the derivation can't name the library, and the candidate who knows the library can't defend what it computes. The tier list itself is a depth signal: knowing that cvxpy (disciplined convex programming) is the right tool for constrained allocation, while SciPy's `minimize` with SLSQP is what people reach for first and what breaks silently on non-convex formulations, tells the interviewer you've actually optimized something under constraints. And the Numba question — "your Monte Carlo is 200x too slow, what now?" — is the classic Python-performance probe in a quant costume.

---

## Lineage: past → present → future

**What came before.** Quant computing was born on Wall Street mainframes, then moved to C++ (which still dominates pricing libraries) and Excel/VBA (which still dominates desks). R arrived with `quantmod` and `PerformanceAnalytics` for the research tier; Matlab held the derivatives crowd. Python was a scripting glue language for quants until ~2010-2015, when the ecosystem compressed into production-grade: NumPy/SciPy matured, pandas (2008, AQR's Wes McKinney — a hedge fund built it for exactly this) gave R a run for panel data, and the finance-specific libraries arrived: **QuantLib** (open-sourced 2000 by Ferdinando Ametrano and Luigi Ballabio at CERN of all places — the definitive pricing reference implementation), **TA-Lib** (1999, Mario Fortier — the C indicator library every charting platform wrapped), **arch** (Kevin Sheppard, Oxford — the GARCH workhorse), **cvxpy** (2013, Stanford Boyd's group — Disciplined Convex Programming), and **PyPortfolioOpt** (2020, Robert Andrew Martin, Oxford — the friendly MVO wrapper the community adopted).

**Where it stands now.** The tier structure the corpus post captures is real and worth memorizing as-is. Non-negotiable: NumPy, SciPy, Statsmodels, QuantLib, cvxpy. Extremely valuable: scikit-learn (model selection pipelines), Numba (JIT for numerical code), PyTorch/JAX (research-grade autodiff for ML-heavy desks), pyarrow/polars (big tick data instead of pandas). Powerful but situational: arch (FIGARCH/HAR/VAR), PyPortfolioOpt (allocation), TA-Lib (desk-driven technicals), yfinance (convenience data). Two structural facts about the current estate: QuantLib remains the only serious open-source pricing engine and its Python bindings (`quantlib` package, formerly QuantLib-Python) lag the C++ core by design; and pandas vs polars for tick data is a live desk-level decision (polars' columnar engine wins on multi-GB ticks; pandas wins on ergonomics and ecosystem).

**Where it's heading.** Three directions. First, JAX is becoming the research-desk autodiff standard for risk differentiation (Greeks by `grad` through the whole pricing graph) — replacing hand-derived adjoints in several shops. Second, QuantLib's slow modernization: more Pythonic wrappers are appearing community-side, but the C++ core remains the API of record — learn it on its own terms. Third, desk-to-cloud: pricing notebooks moving into orchestrated pipelines (the T09 stack), which makes the "library in a model, not a notebook" skill — caching, determinism, dependency pinning — a differentiator. Speculative flag: TA-Lib's indicator set is commoditized (every library has RSI now); its future is maintenance, not growth — but 25 years of desk habit means it's still in every interview.

---

## Mental model

```
 THE QUANT STACK, BY WHAT IT COMPUTES (not by popularity)

 data        ──▶ yfinance / pandas-datareader  (convenience, NOT production)
             ──▶ pyarrow / polars              (multi-GB tick panels)

 math core   ──▶ NumPy    arrays, linalg, RNG          (everything sits on this)
             ──▶ SciPy    optimize, interp, stats      (root finding, minimize)

 statistics  ──▶ Statsmodels   OLS/ARIMA/regression/econometrics
             ──▶ arch          GARCH family, HAR, realized vol (proper likelihoods)

 pricing     ──▶ QuantLib      curves, vols, calendars, engines, instruments
                               (the ONLY serious open pricing library)

 allocation  ──▶ cvxpy         convex optimization AS MATH NOTATION
             ──▶ PyPortfolioOpt  packaged MVO/Black-Litterman/HRP

 indicators  ──▶ TA-Lib        150+ technical functions, C speed

 speed       ──▶ Numba        @njit your Monte Carlo -> 100-500x
             ──▶ PyTorch/JAX  autodiff Greeks, GPU batches
```

The two sentences that unlock everything: **match the library to the mathematics, not to the task** (allocation with constraints is a convex program, so it belongs in cvxpy — not in `scipy.optimize.minimize` with a penalty hack that converges to whatever it feels like), and **QuantLib's API mirrors its C++ object model** (you build a curve object, a vol surface object, an instrument object, then attach a pricing engine — you don't call `price(option)`; if you fight this, QuantLib wins).

---

## How it actually works

### 1. QuantLib: the object graph, mechanically

The mental shift: QuantLib is declarative object composition, not function calls. A vanilla option price is five objects assembled: a `Quote` (spot handle), a flat or bootstrapped `YieldTermStructure` (the discount curve), a `BlackVolTermStructure` (the vol — flat or a surface built with `BlackVarianceSurface`), a process (`BlackScholesMertonProcess`) wrapping the three, then the instrument (`EuropeanOption` with a payoff + exercise) with an `AnalyticEuropeanEngine` attached via `setPricingEngine()`. Then `option.NPV()` and the Greeks (`delta()`, `gamma()`, `vega()`, `theta()`) come out — because the engine computes them. The gotchas interviews probe: **day counts and calendars** (`Actual365Fixed` vs `Thirty360` vs `ActualActual` — price a 3-month option with the wrong count and you're off by real money), **the `Settings.instance().evaluationDate` global** (QuantLib's evaluation date is global mutable state — set it explicitly at the top of every script, or your reproducibility is gone), and **Handles** (`QuoteHandle`/`YieldTermStructureHandle` — relinkable references so a curve can be rebuilt without rebuilding the instrument graph).

### 2. cvxpy: optimization you can read aloud

`cvxpy` expresses a convex program as math: `w = cp.Variable(n); risk = cp.quad_form(w, Sigma); prob = cp.Problem(cp.Minimize(risk), [cp.sum(w) == 1, w >= 0, w @ mu >= target_return]); prob.solve()`. The key value is **DCP (disciplined convex programming)**: cvxpy verifies the problem is convex before solving — `quad_form` with a non-PSD covariance raises an error instead of silently returning garbage (which is exactly what SciPy SLSQP does). Solver awareness matters: ECOS/OSQP/SCS ship by default; commercial-grade MOSEK for production scale; and the no-short + sum-to-one + max-weight-cap portfolio family is the canonical teachable example. The interviewer's probe: "why not `scipy.optimize.minimize`?" — the honest answer: fine for smooth unconstrained problems, but constraint handling via penalties is fragile, optimality isn't verified, and the failure mode is a silently-feasible-but-wrong answer.

### 3. PyPortfolioOpt: what to reach for, when

The layer above cvxpy: `EfficientFrontier(mu, S).max_sharpe()` / `.min_volatility()` / `.efficient_return(target)` — one line for what cvxpy took ten. Its extra batteries are the reason to know it: **Black-Litterman** (blend a prior with views — `BlackLittermanModel(S, pi="market", Q=views)`) and **HRP (Hierarchical Risk Parity)** — the covariance-inverse-free allocation that survives ill-conditioned matrices. The honest positioning (and the interview trap): PyPortfolioOpt is for the allocation step, not the research step — `mu` and `S` estimation is still your problem (shrinkage estimators, Ledoit-Wolf — the two-line `sklearn.covariance.LedoitWolf` call that keeps MVO from being garbage-in-garbage-out). It's the packaged version of what T24-portfolio derives; knowing both the API and the math underneath is the whole point.

### 4. arch and Statsmodels: the volatility/econometrics pair

`arch` (Kevin Sheppard's library) does GARCH-family estimation with correct likelihoods: `am = arch_model(returns, vol='GARCH', p=1, q=1, dist='t'); res = am.fit(disp='off'); res.conditional_volatility` — plus EGARCH, FIGARCH, GARCH-M, HAR-RV for realized vol, and (via `arch.univariate`) mean models. `Statsmodels` is the backbone: OLS with proper inference (`OLS(y, X).fit().summary()` — the table interviewers ask you to interpret), ARIMA/SARIMAX for the mean model, `tsa.stattools.adfuller` for stationarity, and the diagnostic battery (Ljung-Box on residuals). The division of labor: Statsmodels owns the conditional mean, arch owns the conditional variance — the pair IS the workhorse econometrics workflow, and the split between them is itself a quiz question ("where does GARCH live and why not Statsmodels?" — likelihood implementation; Statsmodels' GARCH support exists via `statsmodels.tsa` but arch's is deeper, faster, and the community standard).

### 5. TA-Lib, NumPy/SciPy base, and the Numba speed tier

TA-Lib wraps ~150 C functions (`SMA`, `RSI`, `MACD`, `ATR`, `BOLL`...) behind a uniform `function(series, params)` API; on Windows the `talib-binary` wheel saves the C-build pain. Its honest role at institutional desks: indicator computation for signal backtests, not charting decoration. The base tier everyone forgets to credit: NumPy's RNG discipline (`numpy.random.Generator` with a seeded `PCG64` — never the legacy `RandomState` global), SciPy's `interp1d`/`root_scalar` for curve interpolation and implied-vol solving (Newton/Brentq — `brentq` on the BS price minus market price is the implied-vol workhorse), and vectorized simulation (2M normals in a shape `(n_paths, n_steps)` array beats a Python loop by ~1000x before Numba even enters). Numba closes the gap for what can't vectorize: `@njit(fastmath=True)` on the path-dependent Monte Carlo (Asian/Barrier with path logic) buys 100-500x; `parallel=True` and prange buys the cores; the discipline is typing (Numba hates mixed-type containers and string ops) and cache=True for compile-time amortization.

---

## Practical exercise

Price and hedge one option, then allocate one portfolio, entirely in the stack. (1) Build a QuantLib script: 1y EUR flat curve at 3%, `BlackVarianceSurface` from 5 strikes × 3 maturities of made-up vols, price an ATM 6m European call, and dump `NPV/delta/gamma/vega/theta` — then set `Settings.instance().evaluationDate` forward a week and verify the Greeks shifted (calendar time decay you can see). (2) Invert it: use `scipy.optimize.brentq` on the BS formula to extract implied vol from a market price, then check against QuantLib's own implied-vol calc. (3) Pull 5 years of daily returns for 8 tickers (yfinance is fine for the exercise; note out loud it's not production data), estimate `mu`/`S` with `LedoitWolf`, run `PyPortfolioOpt`'s `EfficientFrontier().max_sharpe()`, then re-solve the same problem long-hand in cvxpy and confirm they agree. (4) Wrap the whole allocation in a loop over 500 bootstrap resamples of `mu` — the stability check that shows max-Sharpe weights jump around (why Black-Litterman and shrinkage exist). (5) Take a path-dependent barrier option Monte Carlo written in pure Python, watch it take 40 seconds, `@njit` it, watch it take 0.2. That sequence touches every tier of the map and every interview probe in the bank.

---

## How it's done in production

Desk and production-quant Python differs from notebook Python in three disciplines. **Determinism and environment pinning**: QuantLib's global evaluation date plus a pinned `quantlib`/`arch`/`cvxpy` version set; a pricing script that isn't reproducible a year later fails model validation, so production code sets dates explicitly and pins via lockfile (the MRM module, T24-mrm, is the org-level counterpart of this). **The data tier is not yfinance**: production pulls from the firm's market-data platform (Bloomberg via `blpapi`, LSEG, internal tick stores) into pyarrow/polars for multi-GB tick panels; yfinance appears in prototypes and interview exercises only, and saying "in production we'd use the firm's data platform" is the honest signal. **Compute tiers**: anything per-trade-path gets Numba/C++ or moves to the GPU tier; whole-portfolio vectorized NumPy handles the rest; the boundary is the profile question, and knowing when a 2-second computation is fine (research) vs unacceptable (risk, where the overnight batch has a deadline) is seniority. Model risk adds the final production layer: the validated model is the one in the approved library with the approved parameters — the quant's code that prices something new is a model change requiring validation, not a PR (T24-mrm).

---

## Tradeoffs

**cvxpy vs SciPy-minimize vs PyPortfolioOpt.** PyPortfolioOpt for the standard allocation family (fast, correct, batteries); cvxpy when the constraint set is nonstandard (tracking error caps, turnover penalties, sector bounds) — its real value is the convexity CHECK, not the solve; SciPy `minimize` only for smooth unconstrained fits (calibration, curve smoothing) where it's genuinely the right tool. The anti-pattern: penalty-method constraints in SLSQP for problems that are convex if written down properly.

**Numba vs vectorize vs rewrite in C++/Rust.** Vectorized NumPy first (zero toolchain cost, ~1000x on array math); Numba when the algorithm is path-dependent or loop-structured and the array rewrite would obscure it (compile cost amortizes via `cache=True`); C++/Rust (or the C++ QuantLib core itself) when the pricing loop is the product and microsecond latency matters. The interviewer's version: "your MC is slow — what do you reach for first?" — vectorize, THEN Numba, THEN native; reaching for Numba before vectorizing is the tell.

**pandas vs polars/pyarrow for tick data.** pandas: ecosystem (everything imports/exports it), ergonomics, the desk lingua franca; polars: multi-GB columnar ticks at 10-100x. The production cut is literal desk size: daily bars and options chains fit pandas; full tick history doesn't. The honest answer includes "both, joined at parquet."

**TA-Lib vs writing indicators yourself.** TA-Lib: 25 years of tested C, uniform API, instant; yourself: only when the definition matters (TA-Lib's `RSI` is Wilder's smoothing — if your research claims a different RSI, that mismatch is your bug or your contribution). At institutional desks TA-Lib wins on maintenance; the "write it yourself once to learn it" advice is pedagogy, not production.

**QuantLib vs the math yourself.** QuantLib: calendars, day counts, conventions, engines, tested — the boring correctness that is the whole job of pricing infrastructure. Yourself: once, for the one instrument your desk prices that QuantLib prices wrong or not at all (it happens; exotic desks maintain their own). The interview-safe line: "derive it on the board, implement in QuantLib, and diff the two — the diff is where the day counts hide."

---

## Interview questions

**Q1 — "How would you price this European option in Python?" Walk the whole path.**
- **Strong:** Names the object graph unprompted: build the flat/bootstrapped curve, the vol surface, the `BlackScholesMertonProcess`, the instrument with payoff/exercise, attach an `AnalyticEuropeanEngine`, then NPV/Greeks from the instrument. Mentions day count and calendar explicitly — "Actual365 vs Thirty360 changes the price" — and the global evaluation-date gotcha.
- **Weak:** "I'd use the Black-Scholes formula in NumPy" — correct for the formula tier, but the question was about pricing infrastructure, and the desk version wants curves/calendars/engines.
- **Follow-up trap:** *"Your price differs from the desk's by 0.3%. Where do you look first?"* Day counts, calendars, and curve conventions — not the formula. The formula is the one thing that's certainly right; the conventions are where the money hides.

**Q2 — Portfolio optimization with no-short and max-weight constraints. Which tool, and why not scipy.minimize?**
- **Strong:** cvxpy (or PyPortfolioOpt for the standard case) — expresses `Minimize(quad_form(w, S))` with explicit constraints, verifies convexity via DCP before solving (a non-PSD covariance raises instead of returning garbage). SLSQP with penalties: fragile, no convexity verification, silent infeasibility.
- **Weak:** `scipy.optimize.minimize` with a penalty term — the answer that tells the interviewer the candidate has never seen a constrained optimizer misbehave.
- **Follow-up trap:** *"Your covariance matrix isn't PSD. What happened, and what do you do?"* Pairwise-estimated or bootstrapped covariances go non-PSD at scale; fix by shrinkage (Ledoit-Wolf), nearest-PSD projection, or reformulate risk as a factor model — cvxpy's error IS the diagnostic.

**Q3 — You need implied vol from a market price. Mechanics?**
- **Strong:** Invert the BS price with a root-finder — `brentq` bracketed on a sensible vol range (0.01–3), or Newton with vega as the derivative; QuantLib has this built (`BlackCalibratedSimpleVol` or the implied-vol helper). Deep ITM/OTM options have near-flat price-vs-vol curves — the root-finder fails or returns unstable values, which is why the smile exists near expiry.
- **Weak:** "Grid search over vols" — works, embarrassingly slowly, and fails exactly where implied vol matters most.
- **Follow-up trap:** *"Two options, same strike, different implied vols. Bug?"* No — the vol surface is a surface (strike × tenor), not a number; this is the smile/skew, and the next question is what shape equity-index surfaces show (negative skew) and why (crash fear, leverage effect).

**Q4 — Fit GARCH on these returns. Which library, and what does the fit give you?**
- **Strong:** `arch` — `arch_model(r, vol='GARCH', p=1, q=1, dist='t').fit()`; the output is the conditional-volatility path (one σ per day), the fitted parameters (α persistence + β memory; α+β near 1 = IGARCH territory), and AIC/BIC for family comparison (GARCH vs EGARCH for asymmetry: bad news hits harder, EGARCH captures the leverage effect).
- **Weak:** Rolling standard deviation of returns — a window statistic, not a conditional-variance model; it can't forecast and can't capture clustering.
- **Follow-up trap:** *"Why not Statsmodels?"* Statsmodels is the mean-model backbone; arch's likelihood implementations for the GARCH family are deeper/faster and are the community standard — knowing the division of labor is the point, not loyalty to either library.

**Q5 — Your Monte Carlo is too slow. Order of operations.**
- **Strong:** Vectorize first (array-shape simulation, ~1000x on plain path generation); Numba `@njit(parallel=True, cache=True)` for path-dependent logic that won't vectorize cleanly (~100-500x more); GPU (PyTorch/JAX batching) when paths are the unit and they're homogeneous. Anti-pattern named: reaching for Numba before vectorizing.
- **Weak:** "Multiprocessing" — path-independent embarrassingly-parallel it may be, but it ignores the 1000x sitting in vectorization first.
- **Follow-up trap:** *"Greeks by finite differences need 4x the paths. Better way?"* Pathwise/adjoint differentiation — or in the modern stack, autodiff: JAX `grad` through the pricing graph, one pass for all Greeks. This is where the library conversation meets the derivatives math.

**Q6 — What's in your NumPy RNG discipline for a simulation?**
- **Strong:** `np.random.Generator(np.random.PCG64(seed))` — explicit generator object, never the global legacy `np.random.seed`; separate streams for reproducibility; antithetic variates as the cheap variance reducer that's a one-line change.
- **Weak:** `np.random.seed(42)` at the top — global state, legacy MT19937, and a reproducibility story that breaks under parallelism.
- **Follow-up trap:** *"Your colleague reran your notebook and got different numbers."* Generator-not-global, or unpinned library versions — the reproducibility failure that model validation actually rejects code for.

**Q7 — Where does Black-Litterman fit, and why does raw MVO need it?**
- **Strong:** MVO's inputs (μ especially) are estimated with huge error; optimizer-in, weights-out amplifies it — max-Sharpe weights jump on resampling. BL fixes the input, not the solver: market-implied prior (reverse optimization from cap weights) blended with subjective views, tuned by confidence (Ω). PyPortfolioOpt packages it; the math is T24-portfolio.
- **Weak:** "It's a better optimizer" — it's a better ESTIMATOR; the optimization is unchanged.
- **Follow-up trap:** *"You have no views. What does BL reduce to?"* The market prior — reverse-optimized equilibrium weights. The formula collapses, and knowing it collapses is the understanding.

**Q8 — TA-Lib's RSI vs "the" RSI you wrote. Which is right?**
- **Strong:** TA-Lib implements Wilder's smoothing (the original recursive alpha=1/n), not SMA-of-changes; both exist in the wild, and the mismatch is definitional. Production: use the library, document the definition; research: match the definition you claim to test.
- **Weak:** "RSI is RSI" — the definitional agnosticism that produces unreproducible signal backtests.
- **Follow-up trap:** *"Your backtest's signals don't match the platform's chart. Debug."* Convention mismatch (smoothing, warmup periods, adjusted-vs-raw closes) — indicator conventions before strategy logic, every time.

**Q9 — yfinance for the production pipeline? Defend or replace.**
- **Strong:** Replace: firm market-data platform / vendor API (blpapi, LSEG), into parquet/pyarrow; yfinance is prototype-grade — no SLA, no history guarantees, breaking-change-prone. The interview-safe sentence: "yfinance for the exercise, the firm's data platform for production, and I'd say which one I meant in each case."
- **Weak:** Defending yfinance for production on price.
- **Follow-up trap:** *"What breaks first when yfinance changes?"* Schema/fields and rate limits — and your pipeline notices when a backfill silently returns empties; contract tests on data shape are the mitigation (T18-data-quality's discipline applied to market data).

**Q10 — The tier list says "learn the math, not the libraries." Reconcile that with this whole module.**
- **Strong:** The libraries encode the math's operational layer (day counts, likelihoods, solvers) — knowing QuantLib without Black-Scholes is a technician; knowing Black-Scholes without a curve builder can't produce a price; the desk needs both, and the library tier is only learnable on top of the math tier. The corpus post's warning stands: the mistake is libraries INSTEAD of mathematics — the tier list exists to sequence, not to replace.
- **Weak:** Either extreme — "libraries are all that matter" (the resume-driven answer) or "real quats don't use libraries" (the machismo answer).
- **Follow-up trap:** *"So why does the interview loop test derivations first?"* Because derivations are hard to pick up on the job and library APIs are not — the interview buys the scarce signal, the library is the trainable one. Understanding THAT asymmetry is what the question is actually testing.

---

## Red flags

- **Prices an option with the BS formula and calls it done** — the object-graph gap; never built a curve, never seen a convention.
- **scipy SLSQP with penalties for constrained allocation** — never watched a non-convex hack return confidently-wrong weights.
- **np.random.seed in anything reproducible** — global legacy RNG; the notebook fails rerun and they don't know why.
- **"GARCH = rolling std"** — conflates a window statistic with a conditional-variance model; can't forecast vol, can't explain clustering.
- **Defends yfinance for production** — hasn't met a real data platform, or hasn't been paged by silent schema change.
- **Numba before vectorizing** — the tool-ordering tell; microsecond-optimizing what array-shape fixes for free.
- **Black-Litterman described as "a better optimizer"** — input estimation vs solve confusion; the math tier is missing underneath the library tier.

## Cheat card

- **QuantLib = object graph:** curve + vol-surface + process + instrument + engine → NPV/Greeks. Set `Settings.evaluationDate` explicitly; day counts are where the money hides.
- **Implied vol = `brentq` on BS-minus-market**, bracketed [0.01, 3]; flat curve near deep ITM/OTM = unstable inversion, that's the smile.
- **Allocation:** PyPortfolioOpt for standard, **cvxpy for nonstandard constraints — DCP checks convexity BEFORE solving**; SLSQP+penalties is the anti-pattern. Shrink `S` (Ledoit-Wolf) or MVO is garbage-in-garbage-out.
- **Black-Litterman = fix the INPUT (μ), not the solver**; no views → collapses to market prior.
- **arch for GARCH family (α+β≈1 = IGARCH); Statsmodels for the mean model + ADF + diagnostics.** Rolling std is not GARCH.
- **Numba order: vectorize → @njit(cache, parallel) → GPU/JAX.** Antithetics = one-line variance cut.
- **RNG: `Generator(PCG64(seed))`, never global seed.**
- **TA-Lib = Wilder-convention indicators**; convention mismatch is the first debug in any signal discrepancy.
- **yfinance = prototype tier; production = firm platform → parquet/pyarrow.**
- **Tier order (memorize):** NumPy/SciPy/Statsmodels/QuantLib/cvxpy → sklearn/Numba/PyTorch-JAX/polars → arch/PyPortfolioOpt/TA-Lib/yfinance — "your desk determines what matters most."
- **The one-liner:** the mistake isn't the wrong library — it's libraries instead of the mathematics underneath them.

## Sources

- The tier-list framing (non-negotiable / extremely valuable / powerful-but-situational) and the "math not libraries" bottom line: the corpus's quant-stack cluster (@quantchics institutional-quant post, OCR-verified, mining/posts/DcWGMwuNYfp/), accessed 2026-09-04 — cross-checked against each library's own documentation and release history.
- QuantLib architecture (handles, engines, evaluation date, day-count conventions): QuantLib documentation and the quantlib-python reference; library open-sourced 2000 (Ametrano/Ballabio), C++ core with Python bindings.
- cvxpy DCP discipline and solver defaults (ECOS/OSQP/SCS): cvxpy documentation (Diamond & Boyd, Stanford, 2013+).
- arch GARCH family and Statsmodels division of labor: arch and statsmodels documentation (Sheppard, Oxford; statsmodels core).
- PyPortfolioOpt MVO/BL/HRP surface: PyPortfolioOpt documentation (Martin, 2020).
- pandas origin (AQR, 2008): Wes McKinney's own account ("pandas: a Foundational Python Library for Data Analysis and Statistics").
- Numba speedup ranges and RNG-generator discipline: numba docs + NumPy NEP 19 legacy/global-random guidance; the 100-500x MC figure is practitioner-typical, flagged as such.

## Changelog

- 2026-09-04: First version — the hands-on library tier for T24's math modules, built from the mined quant-stack tier list as the spine. Standard profile.
