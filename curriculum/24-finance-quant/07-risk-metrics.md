# VaR, CVaR/Expected Shortfall, Stress Testing, Backtesting Risk Models

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-time-series-core · **Updated:** 2026-08-23
> **Module id:** `T24-risk-metrics` · **Tags:** risk, critical

## The 30-second version

Value-at-Risk answers one question — "how bad can the next day/10 days get at 95/99% confidence?" — as a single quantile of the loss distribution: parametric VaR is z·σ·V (z = 1.645 at 95%, 2.326 at 99% for normal returns), historical VaR reads the empirical quantile, Monte Carlo simulates it. Its fatal flaw: VaR says nothing about HOW bad beyond the threshold and is not subadditive, so it can punish diversification. Expected Shortfall/CVaR fixes both by averaging losses past the quantile — Artzner et al (1999) proved it coherent, and Basel's FRTB switched market-risk capital from 99% VaR to 97.5% ES precisely because fat tails break high-quantile VaR estimation and backtesting. That backtesting is the dirty secret: at 99% over a 250-day year you EXPECT 2.5 exceptions, so Kupiec's proportion-of-failures test has almost no power against realistic alternatives, and fat tails cluster exceptions (volatility clustering) violating the iid assumption every counting test relies on — which is why serious shops backtest conditional models, run Christoffersen independence tests, and treat stress testing as the real tail-risk tool: scenarios (CCAR/DFAST style: unemployment +~5-6pp, equities −50%) probe regimes VaR never sampled.

## Why this gets asked

Because market-risk, treasury, and model-validation interviews all live here, and the questions have sharp right answers that separate practitioners from tutorial readers. Ask a candidate to compute 99% VaR and everyone can multiply 2.33 by σ; ask them why their 99% backtest threw 7 exceptions in a calm year and whether that's a red or yellow light under the Basel traffic-light system (yellow, 5-9; add a plus-factor to the multiplier), and you learn instantly who has touched a real limit report. The FRTB shift to ES 97.5% is now the canonical "do you follow regulation" filter — the answer requires knowing BOTH the coherence argument AND the uncomfortable truth that ES cannot be backtested by exception counting at all (Acerbi-Székely 2014 is the reference). Stress-testing questions probe judgment: anyone can name 2008; strong candidates explain why hypothetical scenarios complement historical ones (history is a sample size of one per regime), what reverse stress testing adds ("what breaks us" vs "what if X"), and how CCAR capital planning turned stress from a research exercise into a binding constraint on dividends.

## Lineage

**What came before.** Pre-1990s risk control was notional limits and gut: desk heads watched Greek-letter exposures (delta, duration) but no single number aggregated cross-asset downside. The 1987 crash — DJIA −22.6% in one day, roughly a 20-sigma event under any normal model — exposed that option books hedged with Black-Scholes deltas could still vaporize. Bankers Trust, JPMorgan's RiskMetrics (1994, publishing covariance datasets and the methodology publicly), and Dennis Weatherstone's "4:15 report" (one page of tomorrow-worst-case by close of business) drove standardization. Basel codified it in the 1996 Market Risk Amendment: 99%/10-day VaR with backtesting and a capital multiplier of 3 to 4.

**Where it stands now.** The 2008 crisis showed VaR at 99% systematically understating what was coming — Goldman's CFO famously said models were seeing "25-standard-deviation moves, several days in a row." Basel III-era reform (FRTB, finalized January 2019 after the 2016 first version) replaced 99%/10-day VaR with Expected Shortfall at 97.5% on liquidity horizons of 10-120 days depending on risk factor, plus a Standardized Approach floor and Non-Modellable Risk Factor add-ons; EU banks applied SA from January 2024, US large-bank rules landed 2024-2025 with compliance phasing into 2025-2026. Backtesting doctrine matured alongside: Kupiec (1995) proportion-of-failures, Christoffersen (1998) independence/conditional coverage, Acerbi-Székely (2014) ES tests, plus regulatory P&L-attribution tests comparing hypothetical vs actual P&L. Stress testing institutionalized post-crisis: SCAP (2009) → annual CCAR/DFAST, with the Fed's 2024 exercise projecting ~$685B aggregate losses across the 31 tested banks under severely adverse scenarios.

**Where it's heading.** Three currents. First, ES and scenario metrics converge into integrated stress-testing frameworks where VaR is just one gridpoint; regulators increasingly test climate scenarios (NGFS pathways) with 30-year horizons no historical calibration supports. Second, machine-learning tail models — EVT/GPD peaks-over-threshold fits, quantile regression, distributional deep learning — are entering production for nonlinearity that parametric ES misses, with validation teams demanding interpretability tradeoffs be documented (see T24-mrm). Third, intraday and liquidity-aware risk: the March 2020 Treasury cash scramble and August 5, 2024 yen-carry unwind (VIX spiked above 60 intraday) pushed desks toward real-time VaR and funding-liquidity overlays rather than end-of-day snapshots.

---

## Mental model

```
VaR   = ONE POINT on the loss curve.        "You will not lose more than X
                                             on 99 days out of 100."
ES    = THE AVERAGE past that point.         "When the bad 1% happens,
                                             you lose Y on average."
STRESS= A CHOSEN BAD DAY, fully specified.  "Rates +300bp, spreads +500bp,
                                             equities -50%, VIX 80."

loss distribution:
                 fat tail
                .·°°···
             .··°    |<-- ES_97.5 = mean of this region
           .·°       |
         _.-'        |
      __|            |
  ---+---------------+------------------> loss
     median       VaR_97.5

VaR answers "where does bad start?"
ES answers "how much when it does?"      <- coherent, subadditive
Stress answers "what if the sample never contained the real bad day?"
```

Key identity to internalize: for normal returns, 97.5% ES ≈ 2.338σ while 99% VaR = 2.326σ — nearly identical. For Student-t with 4 degrees of freedom, 97.5% ES is ~30-40% larger relative to its VaR. That asymmetry IS the FRTB rationale: same confidence level produces comparable capital under normality but properly punitive capital under fat tails.

---

## How it actually works

### The three VaR engines

**Parametric (variance-covariance).** Assume returns ~ N(μ, σ²): VaR_α = −(μ − z_α·σ)·V, usually dropping μ for short horizons so VaR = z_α·σ·V. Fast, decomposable (marginal/component VaR falls out linearly), and wrong exactly where it matters: equity daily returns show skewness ≈ −0.5 to −1 and excess kurtosis 5-20; a 4-degrees-of-freedom Student-t fits far better in the tails. Cornish-Fisher expansion patches the quantile for skew/kurtosis; GARCH(1,1) forecasting σ_t fixes the bigger sin — treating volatility as constant when it clusters violently (RiskMetrics EWMA λ=0.94 became the industry default precisely for this).

**Historical simulation.** Revalue today's portfolio under the last N (typically 250-500) historical return vectors; read the empirical quantile. No distributional assumption, captures fat tails that actually occurred, handles nonlinearity if you full-revalue. Weaknesses: the tail is estimated from maybe 2-5 observations (99th percentile of 250 days), ancient data lingers or gets windowed out arbitrarily, and it assumes the past sample contains tomorrow's regime — it never did in 1987/2008/2020's first days. Filtered historical simulation (fit GARCH, standardize residuals, bootstrap them forward) combines both worlds and is the desk-standard upgrade.

**Monte Carlo.** Simulate from a chosen joint distribution (t-copulas with GARCH marginals being common); essential for path-dependent books and multi-day horizons with rebalancing. Cost: model risk migrates into the simulator; you've now got a model OF your model to validate.

### CVaR/Expected Shortfall — the coherent fix

ES_α = E[loss | loss ≥ VaR_α] (for continuous distributions; discretely you average the worst (1−α) fraction of observations — the Rockafellar-Uryasev definition). Artzner et al (1999) defined coherence: monotonicity, translation invariance, positive homogeneity, subadditivity. Subadditivity means ES(A+B) ≤ ES(A)+ES(B) — diversification can NEVER increase risk — while 99% VaR violates it on asymmetric positions (two books each with 0.5% chance of catastrophic loss can have combined 99%-VaR exceeding the sum of individual VaRs, because the catastrophe moved inside the 1% bucket). Practical bonus: CVaR optimization is linear programming-friendly (Rockafellar-Uryasev 2000 turned portfolio CVaR minimization into an LP over scenario variables), unlike max-VaR which is non-convex.

### Why high-quantile backtesting behaves badly under fat tails

This is the JD-depth crux, so spell out all three mechanisms:

1. **Starvation.** At 99%, one year = 250 days gives you 2.5 expected exceptions. The Kupiec test needs the exception count to discriminate between p=1% and, say, p=3%; distinguishing those reliably requires hundreds of periods — a decade-plus. At conventional significance you cannot reject "model fine" vs "model dangerously thin-tailed" within any useful horizon. At 97.5% you get 6.25 expected exceptions/year — still noisy, but 2.5x more signal.
2. **Clustering.** Fat-tailed markets mean volatility clustering: exceptions arrive in runs (Oct 2008 gave daily exceptions five days straight). Kupiec assumes iid Bernoulli(p); clustered violations make the unconditional rate look acceptable while conditional coverage is terrible. Christoffersen's independence test (first-order Markov transition matrix) catches run structure; the proper fix is modeling conditionally — backtest a GARCH-filtered VaR, not an unconditional one.
3. **Estimator feedback loop.** Historical-simulation VaR reacts to a crash only AFTER it enters the window, then keeps flagging exceptions for months as the same dates roll through — "VaR ghosting"/echo effects inflate exception counts post-crisis even when the model is fine. Hybrid quantile weighting (Boudoukh-Richardson-Whitelaw) and FHS mitigate.

Regulatory compromise that emerged: Basel kept backtesting at 99% (where the traffic-light counting logic has decades of precedent) while moving CAPITAL to ES 97.5% — accepting that ES itself lacks a clean exception-count backtest (Acerbi-Székely's Z-test compares realized tail averages against forecast ones but has low power too), and adding P&L-attribution tests (hypothetical vs actual daily P&L, Spearman/KS-based with an unresolved-trades ratio <10%) to police the model-to-books pipeline instead.

### Stress testing — scenarios as complements, not substitutes

VaR/ES extrapolate from history; stress tests impose judgment. Taxonomy: **historical replay** (rerun 2008 week, COVID March 2020 — S&P fell ~34% in 23 trading days, VIX printed 82.69 on March 16, 2020), **hypothetical macro** (CCAR severely-adverse style: unemployment +5-6pp toward 10%, equities −50%, CRE −40-50%, HPI −25-35%), **sensitivity shocks** (+300bp parallel rate shift, +500bp spread widening), and **reverse stress** (solve backwards: what combination kills us? — required conceptually under Pillar 2 and TRIM reviews). The CCAR machine made it binding: pass the scenario → capital plan → dividends/buybacks approved; fail → capital ratios under stress below minimums trigger resubmission restrictions.

---

## Build it from scratch

Historical + parametric VaR/CVaR with Kupiec and independence backtests, numpy-only:

```python
import numpy as np

rng = np.random.default_rng(11)
# fat-tailed daily returns: Student-t(4), scaled to ~1% daily vol, slight drift
T = 2500
r = rng.standard_t(df=4, size=T) * (0.01 / np.sqrt(4/2)) - 0.0002

Z = {0.99: 2.326, 0.975: 1.960, 0.95: 1.645}   # one-sided normal quantiles

def hist_var_es(x, alpha):
    q = np.quantile(x, 1 - alpha)
    tail = x[x <= q]
    return -q, -tail.mean()                    # VaR, ES as positive losses

def par_var_es(x, alpha):
    mu, sd = x.mean(), x.std(ddof=1)
    z = Z[alpha]
    var = -(mu - z * sd)
    # normal ES = phi(z)/(1-alpha) * sd  (+ mean term)
    es = -(mu - sd * np.exp(-z*z/2) / ((1 - alpha) * np.sqrt(2*np.pi)))
    return var, es

def kupiec(exceptions, T, alpha):
    """Proportion-of-failures LR test vs expected rate p. chi2(1) crit 3.841."""
    p = 1 - alpha; x = exceptions
    if x == 0:
        lr = -2 * (T * np.log(1 - p))
    else:
        phat = x / T
        lr = -2 * ((T-x)*np.log(1-p) + x*np.log(p)) \
             + 2 * ((T-x)*np.log(1-phat) + x*np.log(phat))
    return lr, lr > 3.841                       # reject at 5%

def christoffersen(exc):
    """Independence LR on exception runs. chi2(1) crit 3.841."""
    n00 = n01 = n10 = n11 = 0
    for i in range(1, len(exc)):
        a, b = exc[i-1], exc[i]
        n00 += (a == 0 and b == 0); n01 += (a == 0 and b == 1)
        n10 += (a == 1 and b == 0); n11 += (a == 1 and b == 1)
    pi01 = n01 / max(n00 + n01, 1); pi11 = n11 / max(n10 + n11, 1)
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    def ll(p01, p11):                           # transition log-likelihood
        eps = 1e-10
        return (n00*np.log(1-p01+eps) + n01*np.log(p01+eps) +
                n10*np.log(1-p11+eps) + n11*np.log(p11+eps))
    lr = -2 * (ll(pi, pi) - ll(pi01, pi11))
    return lr, lr > 3.841

# rolling out-of-sample backtest for each method/level
for name, fn in [("hist", hist_var_es), ("param", par_var_es)]:
    for alpha in (0.99, 0.975):
        w = 500                                  # estimation window
        exc = []
        vars_ = []
        for t in range(w, T):
            v, _ = fn(r[t-w:t], alpha)
            vars_.append(v); exc.append(r[t] < -v)
        exc = np.array(exc); n_exc = int(exc.sum())
        kl, krej = kupiec(n_exc, len(exc), alpha)
        cl, crej = christoffersen(exc.astype(int))
        print(f"{name:5} a={alpha:.3f} exc={n_exc:3d}/{len(exc)} "
              f"exp={len(exc)*(1-alpha):6.1f} KupiecLR={kl:5.2f} rej={krej} "
              f"IndepLR={cl:5.2f} rej={crej}")

print("full-sample tails: hist", np.round(hist_var_es(r, .975), 4),
      "param", np.round(par_var_es(r, .975), 4))
```

Expected behavior: both methods land near their expected exception counts over the full sample, but individual years swing from zero to 8+ — the small-sample noise that makes 99% backtests nearly powerless. Feed returns through a volatility-shock episode (concatenate `np.concatenate([r, rng.standard_t(df=4, size=250)*0.02])`) and watch exceptions cluster while Christoffersen's independence statistic starts rejecting.

---

## How it's done in production

**Stack:** market-data pipeline → risk factor mapping → full revaluation or sensitivities ladder (delta/gamma/vega grids) → VaR engine (usually FHS at desk level, MC for complex books) → aggregation with liquidity horizons → limit monitoring → daily P&L explain. Vendors (Murex/RiskMetrics/Bloomberg PORT/MSCI RiskManager) or homegrown; either way validation owns an independent implementation.

**Regulatory machinery.** FRTB desks compute SA (sensitivities-based: delta/vega/curvature buckets with correlation scenarios) alongside IMA where approved; capital = max of relevant measures with the SA floor binding via the output floor (see T24-basel). Backtesting runs at trading-desk level: green/yellow/red exception zones set the plus-factor; P&L attribution compares risk-theoretical P&L to front-office actuals weekly. NMRF governance decides which factors are "modellable" — unmodellable ones get stressed-scenario ES add-ons, deliberately punitive.

**Stress testing as workflow, not number.** Scenario libraries maintained by risk committees; reverse-stress solvers search factor-space for business-breaking combos; results feed ICAAP/CCAR capital planning, contingency funding plans, and limit structures. Climate scenarios (NGFS orderlies/disorderlies) now run on 30-year horizons forcing banks into structural assumptions rather than statistical extrapolation.

## Tradeoffs & when NOT to use it

- **Don't use unconditional VaR** for anything volatile-regime dependent — GARCH-condition it or accept clustered exceptions.
- **ES is not backtestable by counting**: if your control framework needs clean pass/fail counts, keep a VaR track alongside ES (regulators do exactly this).
- **Stress tests are judgments, not statistics**: they can be gamed by scenario choice; require independent scenario challenge and reverse-stress coverage.
- **Single-number risk hides correlation breakdown**: report marginal/component contributions and re-run under stressed correlations; a 99% VaR computed on calm-correlation covariances is a fair-weather number.
- **sqrt-of-time scaling lies** for fat tails: scaling 1-day 99% VaR by √10 understates multi-day tail risk when vol clusters; use overlapping/bootstrap methods or explicit multi-day simulation.
- **Historical simulation window choice is a free parameter** regulators increasingly challenge: document why 250 vs 500 days and test sensitivity.

## Interview questions

### Q1 — Compute 1-day 99% VaR for a $10M position with 2% daily vol, normal returns.
**Testing:** baseline fluency.
**Answer:** VaR = z·σ·V = 2.326 × 0.02 × $10M ≈ $465K. Keeping the mean subtracts μV; at daily horizons μ (~0.02%/day) is negligible. 10-day scaled: ×√10 ≈ $1.47M — with the caveat that √t scaling understates fat-tailed multi-day risk.
**Follow-up trap:** *"Is that the most we can lose?"* — No — it's the 1% quantile; losses beyond it are unbounded and average MORE than VaR (that's ES). Treating VaR as a worst case is the misreading that killed its credibility in 2008.

### Q2 — Why did Basel's FRTB switch from 99% VaR to 97.5% Expected Shortfall?
**Testing:** regulation + coherence literacy.
**Answer:** Three reasons: (1) ES is coherent — subadditivity guarantees diversification never increases measured risk, which 99% VaR violates on skewed positions; (2) under normality ES97.5 ≈ VaR99 (2.338σ vs 2.326σ), so capital is comparable in calm regimes, but under fat tails ES grows faster than VaR, properly penalizing tail risk; (3) 97.5% leaves more tail observations for estimation support than 99%. FRTB also replaced flat 10-day horizons with liquidity-horizon-scaled ES of 10-120 days.
**Follow-up trap:** *"So ES fixed backtesting too?"* — Opposite: ES has no clean exception-count test (you cannot "breach" an expectation), hence Acerbi-Székely Z-tests with weaker power; regulators kept 99% VaR backtests and added P&L-attribution tests to police the model-to-P&L pipeline.

### Q3 — Your 99% historical VaR threw 7 exceptions last year (250 days). Green, yellow, red?
**Testing:** traffic-light specifics + judgment.
**Answer:** Basel zones: green 0-4, yellow 5-9, red ≥10. Seven = yellow: the plus-factor raises the capital multiplier k from 3 toward 4, and internally a model-review trigger fires. Statistically, 7 vs expected 2.5 is within noisy reach of a fat-tailed truth — check clustering before declaring the model broken.
**Follow-up trap:** *"What makes it red, and then what?"* — ≥10 exceptions has <1% probability under correct iid calibration → presumption of inadequacy, mandatory multiplier 4, revalidation/remediation of the risk model.

### Q4 — Derive or justify the Kupiec test and state its fatal weakness.
**Testing:** backtest statistics depth.
**Answer:** LR_POF = −2 ln[(1−p)^(T−x) p^x] + 2 ln[(1−x/T)^(T−x)(x/T)^x] — twice the log-likelihood ratio of observed exception frequency x/T against hypothesized p; χ²(1), critical value 3.841 at 5%. Fatal weakness: power. At p=1%, T=250 gives 2.5 expected exceptions; reliably distinguishing p=1% from p=3% needs thousands of observations — years of data — so Type II errors dominate exactly where models are worst.
**Follow-up trap:** *"Fixes?"* — Longer windows, pooling exceptions across desks, conditional coverage tests, and stress testing as the complementary detector for regime-driven failure.

### Q5 — Why do VaR exceptions cluster and what does that break?
**Testing:** conditional coverage intuition.
**Answer:** Volatility clustering (GARCH effects): big days follow big days; a calm-window VaR entering a shock breaches in runs — October 2008 produced consecutive daily exceptions. This breaks the iid Bernoulli assumption behind Kupiec; unconditional counts can look acceptable while the model is conditionally useless. Christoffersen's independence LR compares transition probabilities P(exc today | none yesterday) vs P(exc today | exc yesterday).
**Follow-up trap:** *"Best structural fix?"* — Make the model conditional: GARCH/EWMA-filtered VaR reacts same-day to vol spikes; then backtest exceptions of the conditional model.

### Q6 — Explain subadditivity with a concrete 99%-VaR violation.
**Testing:** why coherence matters beyond axiom recital.
**Answer:** Subadditivity says Risk(A+B) ≤ Risk(A)+Risk(B). Violation: two independent digitals each losing $100M with probability 0.7%. Each has 99%-VaR = 0 (loss probability below 1%); combined book has 99%-VaR ≈ $100M > 0+0 — merging books increased measured risk, punishing diversification. ES fixes it because averaging over the worst 1% keeps the measure subadditive.
**Follow-up trap:** *"Anyone actually burned by this?"* — Limit-setting is: subadditive measures aggregate consistently across desk hierarchies; with VaR, summed desk limits can understate firm risk in ways traders arbitrage.

### Q7 — Historical vs parametric vs Monte Carlo: pick an engine for an options book and defend it.
**Testing:** engine selection reasoning.
**Answer:** Full-revaluation Monte Carlo with t-copula/GARCH marginals (nonlinearity, fat tails, correlation breakdown) or filtered historical simulation with full revaluation if you distrust simulator assumptions. Parametric delta-normal fails outright — gamma skews the P&L even with normal factors. Cost: MC on exotics needs sensitivity ladders or AAD-backed pricers.
**Follow-up trap:** *"Why not just lengthen the historical window?"* — Responsiveness vs relevance tradeoff: pre-2022 windows contain no rising-rate regime; longer windows dilute current vol information. FHS + stressed overlays beats raw window-stretching.

### Q8 — What is the P&L attribution test and why does FRTB need it?
**Testing:** regulatory plumbing beyond the headline metric.
**Answer:** Compares risk-theoretical (hypothetical) P&L — what the risk model would have predicted for actual positions — against front-office actual P&L daily/weekly, via Spearman correlation and Kolmogorov-Smirnov tests plus an unresolved-trades ratio (unresolved/(resolved+unresolved) < 10%). Purpose: catch books whose risk model is fed wrong mappings (missing trades, stale sensitivities), which pure tail statistics can't see. Fail IMA eligibility → desk falls to SA capital.
**Follow-up trap:** *"Hypothetical vs theoretical P&L — same thing?"* — No: hypothetical uses the risk-model factor set; theoretical uses full front-office revaluation with ALL factors. The gap between them localizes where risk mapping diverges from pricing.

### Q9 — Design a stress test for a bank treasury book in one minute.
**Testing:** structured scenario thinking under time pressure.
**Answer:** Pick shock families: rates (+300bp parallel; +100bp steepener/flattener), credit spreads (+500bp), deposit behavior (30-50% runoff of unstable deposits — SVB's lesson), collateral haircuts widening. Apply to balance sheet: mark securities to shocked curves (SVB end-2022 carried ~$15B+ unrealized HTM losses on a ~$90B book at +~200bp), project NII, compute surviving capital ratios. Report breach distances vs minimums and required management actions.
**Follow-up trap:** *"What's reverse stress adding?"* — Inverts the question: solve for the shock combination that breaches capital (e.g., X% deposit runoff + Y bp rate rise). Reveals vulnerability magnitudes rather than confirming chosen fears; regulators expect it under Pillar 2/ICAAP.

### Q10 — Why can't you backtest Expected Shortfall by counting exceptions?
**Testing:** understanding what ES estimates.
**Answer:** ES forecasts a conditional TAIL MEAN, not a threshold — there's no binary event to count. You'd compare realized average losses ON days that breached against forecast ES (Acerbi-Székely's Z1/Z2 tests), but those use few observations (only exception days), so power stays low even over years. Hence regulators pair ES capital with VaR-based backtesting at 99% and P&L attribution instead.
**Follow-up trap:** *"Could you backtest ES at lower confidence?"* — Yes — ES95 has ~12-13 tail days/year giving more support, and shops do internal ES backtests at 95/97.5 with el-type tests; but regulatory-grade confidence levels leave too little data, hence the compromise stack.

### Q11 — COVID week, March 2020: what did risk systems get right and wrong?
**Testing:** lived-through-regime literacy.
**Answer:** Wrong first: calm-window historical VaR was blown through within days (S&P fell ~34% peak-to-trough in 23 trading days; VIX hit 82.69 on March 16, 2020), correlation matrices built on quiet data inverted, liquidity costs exploded wider than models assumed. Right eventually: GARCH-filtered engines re-marked within days; stress overlays (rates/spreads shocks) had sized capital correctly; margin calls flowed per LCH/CME rules. Postmortems pushed real-time intraday risk, funding-liquidity overlays, and stressed-correlation reporting.
**Follow-up trap:** *"So VaR failed?"* — The unconditional variant did what unconditional metrics always do in new regimes. Conditional models + scenario overlays performed as designed; the failure was treating fair-weather VaR as sufficient.

### Q12 — Aug 5, 2024: VIX spiked above 60 intraday then collapsed within days. What does that event teach about tail metrics?
**Testing:** distinguishing volatility spikes from regime breaks.
**Answer:** The yen-carry unwind produced a one-day vol spike (VIX intraday >60, S&P -3%) that mean-reverted almost immediately — unlike March 2020's sustained regime. Lessons: (1) fat tails include fast-reverting jumps that break stop-loss logic but not necessarily capital math; (2) intraday liquidity matters — end-of-day VaR missed both the spike depth and the recovery; (3) leverage forced selling (carry unwinds) transmits across asset classes faster than daily risk cycles can react.
**Follow-up trap:** *"Should models include jump processes everywhere then?"* — Cost-benefit: jumps matter most for levered/carry strategies and short-gamma books; adding them everywhere degrades estimation stability. Map where jump risk concentrates and instrument those desks specifically.

## Red flags

- Calling VaR "the maximum possible loss."
- No idea of green/yellow/red exception zones or the multiplier mechanics.
- Proposing to backtest ES by counting breaches.
- Ignoring volatility clustering when explaining backtest exceptions.
- Using √10 scaling without acknowledging fat-tail understatement.
- Treating stress testing as redundant with 99.9% VaR ("just crank up z").
- Historical simulation window picked by default with no sensitivity analysis.
- Confusing confidence level (99%) with horizon (10-day) in VaR specs.

## Cheat card

```
VaR_a   = quantile of loss dist.  parametric: z_a*sigma*V
          z: 95%=1.645 · 97.5%=1.96 · 99%=2.326
          sqrt-time scaling x sqrt(h); lies under fat tails
ES_a    = E[loss | loss>=VaR_a] = mean of worst (1-a) fraction
          coherent: monotone, transl.-inv., pos.-homog., SUBADDITIVE
          normal: ES97.5=2.338s ~ VaR99=2.326s; t4: ES >> VaR
ENGINES parametric (fast, thin tails) / historical (250-500d,
          tail from 2-5 obs!) / MC (t-copula+GARCH) / FHS = best of both
BACKTEST Kupiec POF '95: LR chi2(1)=3.841 @5%; expected exc/yr:
          99%->2.5, 97.5%->6.25 (T=250). POWER COLLAPSES at high alpha
          clustering -> Christoffersen independence LR ('98)
          fix: GARCH-filter (conditional) VaR
BASEL    '96 MRA: 99%/10d VaR, traffic light g0-4/y5-9/r>=10,
          k=3..4 plus-factor; FRTB '19: ES97.5%, liq horizons 10-120d,
          PLA test unresolved<10%, NMRF add-ons; EU live 2024+, US 25-26
STRESS   SCAP'09 -> CCAR/DFAST yearly (2024: ~$685B projected losses,
          31 banks); sev-adverse: U+5-6pp, EQ-50%, CRE-40%;
          reverse stress = solve for breach; climate NGFS 30y horizons
EVENTS   '87: -22.6% (~20-sigma) · '08: "25-sigma days" · 3/'20:
          SPX -34%/23d, VIX 82.69 · 8/5/'24: VIX>60 intraday, reverted
```

## Sources

- [Basel Committee (2019). Minimum capital requirements for market risk (FRTB)](https://www.bis.org/bcbs/publ/d457.htm); accessed 2026-08-23
- [Kupiec, P. (1995). Techniques for Verifying the Accuracy of Risk Measurement Models. Journal of Derivatives](https://www.jstor.org/stable/23462013); accessed 2026-08-23
- [Christoffersen, P. (1998). Evaluating Interval Forecasts. International Economic Review](https://www.jstor.org/stable/2527342); accessed 2026-08-23
- [Artzner, Delbaen, Eber, Heath (1999). Coherent Measures of Risk. Mathematical Finance](https://onlinelibrary.wiley.com/doi/10.1111/1467-9965.00068); accessed 2026-08-23
- [Acerbi, Székely (2014). Back-testing Expected Shortfall. MSCI Research](https://www.msci.com/documents/10199/591565f9-3d68-4163-a248-19a3a40a3b17); accessed 2026-08-23
- [Rockafellar, Uryasev (2000). Optimization of Conditional Value-at-Risk. Journal of Risk](https://www.risk.net/journal-of-risk/2161159/optimization-conditional-value-risk); accessed 2026-08-23
- [Federal Reserve. CCAR/DFAST stress test results and scenario documentation](https://www.federalreserve.gov/supervisionreg/dfa-stress-tests.htm); accessed 2026-08-23
- [JPMorgan RiskMetrics Technical Document (1996 archive)](https://www.msci.com/documents/10199/dd4250dc-e330-46e5-b0a4-11b0d9ed6471); accessed 2026-08-23

## Changelog

- 2026-08-23 — created







