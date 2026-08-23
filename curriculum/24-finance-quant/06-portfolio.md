# Modern Portfolio Theory, CAPM, Factor Models, Risk Parity

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T03-linear-models · **Updated:** 2026-08-23
> **Module id:** `T24-portfolio` · **Tags:** quant

## The 30-second version

Markowitz (1952) reframed investing as a constraint problem: choose weights that maximize return per unit of variance, exploiting the fact that correlations below 1 make the whole less volatile than its parts — the only free lunch in finance. CAPM (Sharpe 1964, Lintner 1965) is the equilibrium punchline: if everyone holds the same tangency portfolio, only beta — covariance with the market — is priced, and anything left over is alpha. Factor models (Fama-French 1993; Carhart momentum 1997; FF5 in 2015) generalized beta to a handful of priced characteristics — size, value, momentum, profitability, investment — so "alpha" usually turns out to be exposure to known premia. Risk parity (Bridgewater's All Weather, launched 1996) attacks mean-variance's practical failure: a classic 60/40 portfolio draws over 90% of its risk from equities, so risk parity allocates *risk* equally instead of *capital*, leveraging low-volatility assets to do it. The recurring villain across all four is estimation error: sample means are nearly useless at investment horizons, sample covariances invert badly when assets outnumber observations, and DeMiguel-Garlappi-Uppal (2009) showed naive equal-weighting beats optimized portfolios out-of-sample in most of their 7 datasets and 14 models tested. Production answers: covariance shrinkage (Ledoit-Wolf 2004), hard constraints, Bayesian views (Black-Litterman 1992), and risk-based weighting that sidesteps expected returns entirely.

## Why this gets asked

Because it is the rare interview topic where you can be handed a marker and asked to derive the answer end-to-end: write the mean-variance problem, take first-order conditions, get the tangency portfolio — then watch whether you flinch when asked "what happens when Σ is singular?" The question chain probes whether you understand *why* each idea exists: CAPM is what MPT becomes in equilibrium; factor models are what CAPM becomes after forty years of data embarrass it; risk parity is what MPT becomes when you stop trusting expected-return estimates at all. Asset-management, bank-treasury, and fintech-risk JDs all lean on this ladder. The failure modes are diagnostic. Candidates who recite CAPM but cannot say why the empirical security market line is flatter than theory predicts (leverage constraints bind; Frazzini-Pedersen's "Betting Against Beta," 2014) reveal textbook-only knowledge. Candidates who compute an efficient frontier but never ask about the condition number of Σ will build portfolios that flip sign weekly. If a job description mentions portfolio analytics, risk decomposition, or factor research, expect every layer here plus the estimation-error war stories.

## Lineage

**What came before.** Pre-1952 practice was Graham-Dodd security selection with folklore diversification ("don't put all eggs in one basket" — no mathematics of *how many baskets*). The quantitative seeds were Bachelier (1900) modeling prices as Brownian motion and Cowles (1933) showing professional forecasters could not beat indexes. Markowitz's 1952 "Portfolio Selection" made risk a number: portfolio variance is quadratic in weights through Σ, so diversification has an optimal dose, not just a direction. Tobin (1958) added two-fund separation: every mean-variance investor holds a mix of the risk-free asset and one common risky fund, regardless of risk appetite.

**Where it stands now.** Sharpe (1964), Lintner (1965) and Mossin (1966) derived CAPM from that separation plus homogeneous expectations; Jensen (1968) gave managers alpha to be judged by; Roll (1977) noted the market portfolio is unobservable so CAPM is jointly untestable; Ross (1976) offered arbitrage pricing theory as the multi-factor escape hatch. The empirical program did the real damage: Banz (1981) found the small-cap effect; Fama-French (1992, 1993) packaged size and value with the market into the 3-factor model; Carhart (1997) added momentum (UMD); Fama-French (2015) added profitability (RMW) and investment (CMA). Practitioner infrastructure industrialized alongside: Barra-style fundamental factor risk models (MSCI Barra USE4 lineage, Axioma, Northfield) became the standard risk-decomposition toolkit; Black-Litterman (1992) made views mixable with equilibrium priors; Bridgewater launched All Weather in 1996 and the risk-parity category grew to an estimated $100-200B+ AUM industry-wide by the 2010s peak. The replication crisis arrived on schedule: Harvey-Liu-Zhu (2016) catalogued 316 published factors and recommended a t-statistic hurdle above 3.0, not 2.0, for anything claiming to be new.

**Where it's heading.** Three currents. First, better inputs rather than better objectives: Ledoit-Wolf shrinkage as table stakes, factor-based covariance for large universes, EWMA/DCC-GARCH for time-varying correlations, hierarchical risk parity (López de Prado 2016) using clustering to avoid inverting noisy correlation matrices at all. Second, personalization: direct indexing (~$500-800B US AUM trajectory cited across brokers by 2025) makes each household its own optimizer with tax-loss harvesting as the alpha. Third, honest humility about regimes: 2022 — when stocks fell ~18% total return and the Bloomberg US Aggregate fell ~13% simultaneously, the worst joint year in decades — killed complacency about negative stock-bond correlation and pushed allocation research toward inflation-aware factors and regime-switching covariance.

---

## Mental model

```
RISK IS A BUDGET. Capital weights are not risk weights.

  60/40 portfolio (stocks vol ~16%, bonds vol ~5%, corr ~0.2):
    capital split   = 60% / 40%
    risk split      = ~93% / ~7%     <- equity owns the budget

FOUR LENSES ON THE SAME PROBLEM:
  MVO          maximize mu'w - (lambda/2) w'Sigma w
               -> needs GOOD estimates of everything
  CAPM         in equilibrium only ONE column of Sigma is priced:
               Cov(Ri, Rm)/Var(Rm) = beta
  FACTORS      returns = exposures x premia + noise
               R_i - Rf = a + b1 MKT + b2 SMB + b3 HML + ... + e
  RISK PARITY  set every slice of the variance pie EQUAL:
               w_i * (Sigma w)_i identical for all i
```

The unifying lens: every framework answers "how much should I pay for a stream of cash flows whose uncertainty correlates with things I already own?" MVO prices it from your utility function; CAPM from the marginal investor's; factor models from a menu of priced risks; risk parity refuses to price it and instead equalizes how much each position can hurt you.

---

## How it actually works

### Mean-variance optimization — the machine and its failure mode

Formally: minimize w'Σw subject to μ'w = r_target and 1'w = 1. The Lagrangian first-order condition gives 2Σw = λμ + γ1, so optimal weights are *linear* in the target return, tracing the frontier as a hyperbola in (σ, μ) space. Two portfolios anchor everything: the global minimum-variance portfolio (GMV) needs no expected returns at all — only Σ — and the tangency portfolio w_tan ∝ Σ⁻¹(μ − rf·1), which maximizes the Sharpe ratio. Tobin's separation says any frontier point is a mix of rf and tangency.

The catch is that Σ⁻¹ amplifies estimation error exactly where data is weakest. With N assets you need N(N+1)/2 covariance terms: 500 assets means ~125,000 parameters. If N approaches T (observations), sample Σ becomes singular or near-singular, and the optimizer arbitrages noise: it loads on assets whose historical mean was high *by luck* with low measured variance *by luck*. This "error maximization" is why unconstrained MVO produces corner solutions — a few weights at +100%, others shorted hard — that reverse out-of-sample. Jobson-Korkie (1981) quantified how badly estimated tangency portfolios underperform; Michaud coined the error-maximization framing in 1989.

### CAPM — one beta to price them all

Assume everyone is a mean-variance optimizer with identical beliefs over the same universe, frictionless lending/borrowing at rf. Then aggregate demand IS the market portfolio, the tangency portfolio must be the market, and equilibrium prices fall out of the SML:

```
E[Ri] = Rf + beta_i * (E[Rm] - Rf),   beta_i = Cov(Ri,Rm) / Var(Rm)
```

Only systematic risk is priced because idiosyncratic risk diversifies away for free — holding it earns nothing. Jensen's alpha (1968) measures the vertical distance off the SML. The empirical record since the 1970s: the SML slope runs flatter than the theory line (high-beta stocks underdeliver, low-beta overdeliver relative to CAPM — Black 1972's zero-beta model, confirmed by Frazzini-Pedersen 2014 across 90+ years of data). Explanations converge on institutional frictions: many investors cannot lever, so they buy high-beta instead, bidding down its expected return. Add Roll's critique — the true market portfolio includes human capital, real estate, everything — and CAPM's status settles at: a useful decomposition device, a weak absolute pricing engine.

### Factor models — what alpha actually is

A factor model regresses excess returns on factor returns: R_it − Rft = a_i + Σ b_ik F_kt + e_it. Three construction styles: time-series factors (long-short hedge portfolios like SMB/HML/UMD), fundamental risk models (exposures from company characteristics, factor returns estimated cross-sectionally — the Barra lineage used for *risk*, not forecasting), and statistical factors (PCA eigenportfolios). Canonical premia in the original samples: SMB roughly 2-4% annualized, HML similar magnitude, momentum historically the strongest gross premium (~8-10%/yr long-short before costs, but with brutal crash months — momentum lost ~70%+ in Jan-Mar 2009 rebound... actually its worst single month, January 2009, cost roughly -49% on the UMD long-short). FF5 explains more of the cross-section than FF3 but shrinks alpha everywhere — which is the point: most "skill" was exposure to profitability/investment tilts. The factor-zoo problem: with hundreds of tested characteristics, t > 2 arises by chance; Harvey-Liu-Zhu's correction demands t > 3.0 for new claims, and post-publication decay is real — premia shrink once tradeable products arbitrage them.

### Risk parity — budgeting variance instead of dollars

Define each asset's risk contribution RC_i = w_i · (Σw)_i / σ_p². In 60/40, RC_equity ≈ 93%. Risk parity sets all RC_i equal (equal risk contribution, ERC — Qian 2005-06 gave the category its name and math). For two assets with vols σ1, σ2 and correlation ρ, ERC weight on asset 1 simplifies to σ2/(σ1+σ2) when ρ is symmetric — inverse-vol weighting generalized for correlations. Because bonds carry ~5% vol vs equities ~16%, equal-risk bond sleeves must be levered roughly 2-3x, targeting a fund-level vol of ~10%. That leverage is the design feature AND the fragility: it assumes bonds are the stable ballast (they were, 1981-2021, as yields fell from ~15% to ~1.5%), and it pays financing costs that bite when cash rates spike. 2022 stress-tested all three legs at once: stocks -18%, Agg -13% (worst US bond year on record), correlations flipping positive under inflation shock — global risk-parity indices drew down roughly 20-30% peak-to-trough, their worst year since inception-era 2009... (the SG Risk Parity index fell ~22% in 2022 vs ~-14% in the 2020 COVID quarter).

---

## Build it from scratch

Runnable numpy-only efficient frontier + risk parity on four toy assets:

```python
import numpy as np

rng = np.random.default_rng(7)
mu  = np.array([0.04, 0.08, 0.11, 0.05])            # annual expected returns
vol = np.array([0.05, 0.12, 0.20, 0.16])            # bond, equity, em-equity, gold-ish
C   = np.array([[1.00, 0.30, 0.25, 0.10],
                [0.30, 1.00, 0.75, 0.05],
                [0.25, 0.75, 1.00, 0.10],
                [0.10, 0.05, 0.10, 1.00]])
cov = np.outer(vol, vol) * C
rf  = 0.02

def stats(w):
    r = float(mu @ w)
    s = float(np.sqrt(w @ cov @ w))
    return r, s

def frontier(n=50):
    # exact equality-constrained QP via KKT linear system:
    # [2Cov  mu  1][w ]   [0 ]
    # [mu'   0   0][l1] = [rt]
    # [1'    0   0][l2]   [1 ]
    k = len(mu); pts = []
    KKT = np.zeros((k+2, k+2)); KKT[:k,:k] = 2*cov
    KKT[:k,k] = mu;  KKT[k,:k] = mu
    KKT[:k,k+1] = 1; KKT[k+1,:k] = 1
    rhs = np.zeros(k+2); rhs[k+1] = 1
    for rt in np.linspace(mu.min(), mu.max(), n):
        rhs[k] = rt
        sol = np.linalg.solve(KKT, rhs)[:k]
        r, s = stats(sol)
        if (sol >= -1e-9).all():          # keep long-only points
            pts.append((s, r))
    return np.array(pts)

def gmv():
    k = len(mu); A = cov.copy()
    ones = np.ones(k)
    w = np.linalg.solve(A, ones)
    return w / (ones @ w)

def tangency():
    k = len(mu)
    w = np.linalg.solve(cov, mu - rf)
    return w / w.sum()

def erc(iters=200):
    # fixed-point: w_i proportional to 1/(Sigma w)_i, normalized.
    w = np.full(len(mu), 1/len(mu))
    for _ in range(iters):
        mrc = cov @ w                     # marginal risk contribution
        w_new = (1/mrc) / (1/mrc).sum()   # inverse-marginal-vol step
        if np.abs(w_new - w).max() < 1e-12:
            w = w_new; break
        w = w_new
    return w

def rc_table(w):
    sigma = np.sqrt(w @ cov @ w)
    rc = w * (cov @ w) / sigma**2      # shares of total variance
    return rc

pts = frontier()
print("GMV       ", np.round(gmv(), 3),     "vol %.2f%%" % (100*np.sqrt(gmv() @ cov @ gmv())))
w_t = tangency(); print("Tangency  ", np.round(w_t, 3), "Sharpe %.3f" % ((stats(w_t)[0]-rf)/stats(w_t)[1]))
w_e = erc();      print("ERC       ", np.round(w_e, 3), "risk shares", np.round(rc_table(w_e), 3))
print("frontier span: vol %.2f%%..%.2f%%" % (100*pts[:,0].min(), 100*pts[:,0].max()))
# sanity check: ERC risk contributions should print near [0.25, 0.25, 0.25, 0.25]
```

Reading the output: ERC weights tilt heavily toward the 5%-vol asset yet every asset contributes exactly 25% of variance; the tangency portfolio concentrates where Sharpe ratios look best and will not match ERC; GMV ignores mu entirely and lands near the lowest-variance corner of the frontier. Swap `default_rng(7)` seeds or perturb mu by ±1% and watch tangency weights swing violently while GMV/ERC barely move — that instability IS the estimation-error lesson.

---

## How it's done in production

**Covariance is engineered, not sampled.** Ledoit-Wolf shrinkage (2004) blends sample Σ toward a structured target (constant-correlation or identity×average-variance) with intensity fit by minimizing Frobenius loss; typical shrinkage intensities land 10-40% depending on N/T. Large universes use factor covariance: Σ = B F B' + D from a 50-100 factor risk model, cutting parameters by orders of magnitude. Time variation uses EWMA (RiskMetrics λ=0.94 for daily) or DCC-GARCH. Illiquid marks get de-lagging and R²-adjusted betas.

**Optimization hygiene.** Long-only + max-weight caps + turnover penalties + tracking-error bounds are not decoration; they are the fix for error maximization. Nearest-positive-semidefinite projection before inversion; condition-number alarms; Black-Litterman to blend views with equilibrium-implied returns so the optimizer fights the prior only where you actually have information. Transaction-cost-aware optimization (expected cost as a convex penalty) replaced naive rebalancing at most shops post-2010.

**Risk parity in practice.** Funds run ERC at ~10% vol with leverage via futures/swaps, monitor risk contributions daily against bands (±3pp drift triggers rebalance), and stress the leverage line itself: margin calls in 2020's March cash scramble forced some RP funds to de-risk into the bottom. Vol-targeting overlays adjust gross exposure when realized vol spikes.

**Factor research workflow.** Hypothesis → point-in-time data (no survivorship/lookahead) → cross-sectional portfolio sorts with realistic costs → t-stat hurdle ≥ 3 → capacity/crowding check → paper-trade. Attribution runs through a Barra-style model so P&L decomposes into factor timing vs selection vs currency vs costs. Walk-forward validation with purged/embargoed splits (see T24-ts-validation) is table stakes after López de Prado's backtest-overfitting critique.

## Tradeoffs & when NOT to use it

- **Don't trust unconstrained MVO** with short histories, many assets, or unstable means. If your expected-return estimate has an error bar bigger than its value (it does), use GMV/risk-based weights or heavy constraints.
- **CAPM is a language, not a calculator**: fine for decomposing exposure and communicating; wrong for setting hurdle rates on high-beta projects (flat SML means CAPM overstates their required return).
- **Factors decay**: published premia halve-ish post-publication in replication studies; capacity and crowding matter more than backtest Sharpe.
- **Risk parity fails when bonds stop diversifying**: inflation regimes flip stock-bond correlation positive; leverage plus financing costs (2022-23 rates) can turn the ballast into cargo. It also ignores valuation entirely — expensive everything still gets equal-risk weight.
- **Mean-variance utility itself** misprices drawdown-averse investors: if the objective is really "don't lose >X%", optimize CVaR or max-drawdown instead (see T24-risk-metrics).
- **Taxable accounts**: pre-tax MVO is the wrong problem; tax-aware direct indexing dominates small allocations.

## Interview questions

### Q1 — Derive the tangency portfolio and explain where it breaks.
**Testing:** can you actually do the math, not recite it.
**Answer:** Maximize (μ'w − rf)/√(w'Σw); first-order conditions give w_tan ∝ Σ⁻¹(μ − rf·1), normalized to sum to 1. It breaks when Σ is near-singular (N ≳ T): Σ⁻¹ has huge eigenvalues in the directions you estimated worst, so noise gets levered. Fixes: shrinkage, factor structure, constraints, or drop expected returns (GMV/ERC).
**Follow-up trap:** *"So just regularize Σ?"* — Shrinking covariance helps but the dominant error is usually in μ (sample mean noise scales with σ√T of the estimate window; a 60-month mean on 16%-vol assets carries ~2.3% annual standard error). Covariance fixes are second-order next to that.

### Q2 — Why does naive 1/N keep beating optimizers out-of-sample?
**Testing:** estimation-error intuition.
**Answer:** DeMiguel-Garlappi-Uppal (2009), 14 models across 7 datasets: optimization gains require accurate μ and Σ, but estimation error costs more than diversification structure earns. Equal weights have zero estimation error and still capture most breadth benefits. Optimizers win only with strong priors/constraints or risk-only objectives.
**Follow-up trap:** *"Does that kill MPT?"* — No — it kills *unregularized* MPT. GMV and ERC are MPT descendants that use only Σ; shrinkage + constraints is standard now; the frontier concept survives as the benchmark any allocation must beat.

### Q3 — CAPM says only beta is priced. Why is the empirical SML too flat?
**Testing:** knows the anomalies AND their economics.
**Answer:** If some investors can't borrow (mutual funds, risk parity post-2022 margin rules), they reach for return by buying high-beta stocks instead of leveraging, pushing high-beta prices up and expected returns down: beta becomes negatively related to alpha. Frazzini-Pedersen (2014) confirm across 90+ years and 19 markets ("betting against beta" earns positive Sharpe).
**Follow-up trap:** *"Then why do practitioners still compute beta daily?"* — As an accounting identity for exposure/attribution and cost-of-capital conversations, not as a pricing oracle. Beta tells you what you own; CAPM's premium line is the contested part.

### Q4 — What exactly is Roll's critique and what survives it?
**Testing:** epistemics of asset pricing tests.
**Answer:** Roll (1977): the market portfolio must include ALL wealth (human capital, property, private equity); it's unobservable, so tests using a proxy jointly test the proxy. Any test rejection could be proxy error. What survives: cross-sectional covariances with broad indexes remain the practical systematic-risk measure; APT-style multi-factor work sidesteps by pricing identified risks rather than "the" portfolio.
**Follow-up trap:** *"Is anything testable then?"* — Restrictions like mean-variance efficiency of ANY candidate index are testable (the critique targets identification, not falsifiability wholesale); factor-mimicking portfolios give internally consistent joint tests.

### Q5 — Walk me through ERC math for two assets.
**Testing:** risk-parity fluency at whiteboard speed.
**Answer:** RC_1 = w1(Σw)_1/σp². With vols σ1, σ2 and correlation ρ: setting RC_1 = RC_2 yields w1 = σ2/(σ1+σ2), w2 = σ1/(σ1+σ2) — correlation drops out for N=2 (it rescales both sides equally). So 16%/5% assets give w_bond = 16/21 ≈ 76% capital weight; leverage lifts total vol to target (~10% ⇒ gross ≈ 10%/6.9% ≈ 1.4x).
**Follow-up trap:** *"Same formula for five assets?"* — No: for N≥3 correlations matter and there's no closed form; you iterate (w_i ∝ 1/(Σw)_i fixed point) or solve the log-barrier system min ½y'Σy − (1/N)Σln y_i.

### Q6 — Your PM asks for max-Sharpe weights on 50 stocks with 3 years of data. What do you hand back?
**Testing:** production judgment vs textbook obedience.
**Answer:** Not raw tangency weights: 150 monthly observations vs 50 assets means sample Σ is rank-deficient-ish (rank ≤ 149 fine, but condition number explodes) and μ errors dominate. Hand back Ledoit-Wolf-shrunk inputs, long-only with position caps (e.g., ≤5%), turnover penalty, Black-Litterman neutral prior — plus a sensitivity table showing weight stability across input perturbations.
**Follow-up trap:** *"Why not Monte Carlo the frontier like Michaud resampling?"* — Legitimate (resample inputs, average optima), but it averages over estimation error without removing its cause and can smooth away real views; constraint-based robustness is cheaper and more explainable to a risk committee.

### Q7 — Explain the momentum crash of 2009 to a risk committee.
**Testing:** factor tail literacy beyond average premia.
**Answer:** Momentum is short losers/long winners; March 2009 was a violent reversal — beaten-down financials rocketed while prior winners kept falling — so UMD lost roughly half its notional within weeks (Jan-Mar 2009 drawdown ~70%+ peak-to-trough region, single worst month ≈ -49%). The premium averaged ~8-10%/yr gross historically but with negative skew and crash clustering at rebound inflections when vol is high.
**Follow-up trap:** *"So momentum is just riskier value?"* — They crash at different times and are negatively correlated ~40-50% of the time; combining them (as FF did NOT do until practitioners forced it) smooths the ride. The lesson: premia are paid partly FOR crash risk.

### Q8 — Why did Fama-French add profitability and investment factors in 2015?
**Testing:** model-evolution reasoning.
**Answer:** FF3 left the HML anomaly-of-the-anomaly unexplained: among value stocks, high-profitability firms outearn low-profitability ones (and vice versa among growth). RMW (robust-minus-weak operating profitability) and CMA (conservative-minus-aggressive investment) absorb this, tying into valuation theory (expected returns rise with profitable, low-investment firms à la discounted cash flow mechanics). Momentum stayed OUT because FF treat factors as risk-based explanations, and no consensus risk story exists for momentum.
**Follow-up trap:** *"FF5 killed alpha everywhere — so is active management dead?"* — It redefined alpha: gross alpha shrank, but after-cost live-fund alpha remains sharply negative on average (SPIVA: ~85-90% of US large-cap funds underperform S&P over 15 years), so the death verdict predates FF5 and comes from fees.

### Q9 — How would you build a Barra-style risk model, and how is it different from FF?
**Testing:** practitioner vs academic factor construction.
**Answer:** Exposures come from characteristics (beta, size, value, volatility, liquidity, sector dummies) measured TODAY per stock; factor returns are then estimated cross-sectionally each period (regress returns onto exposures); covariance of factor returns forecasts portfolio risk. FF runs time-series regressions with prebuilt hedge portfolios to price returns. Direction matters: Barra answers "what drives my risk?", FF answers "what earns premia?"
**Follow-up trap:** *"Can one model do both?"* — Hybrid attempts exist but tension is real: forecasting wants fast-moving exposures and fresh factors; audit-grade attribution wants stable definitions for years. Most shops run two models and reconcile.

### Q10 — Stock-bond correlation flipped positive in 2022. Walk through what that did to balanced books.
**Testing:** regime awareness, not frozen 2010s priors.
**Answer:** 2010s baseline correlation ran mildly negative (-0.2 to -0.4), making bonds the shock absorber. 2022 inflation shocks raised discount rates hitting BOTH duration and equity multiples: S&P 500 total return ≈ -18%, Bloomberg US Agg ≈ -13% (worst bond year on record; long Treasuries ≈ -30%), classic 60/40 fell ~16-17%, global risk-parity drew down ~20-30%. Allocation frameworks built on negative correlation (RP leverage, LDI hedges, vol-targeting ballast) all stressed simultaneously.
**Follow-up trap:** *"Was that predictable?"* — The conditional correlation under inflation regimes was documented (positive in the 1970s-80s); the mistake was treating a 12-year disinflationary sample as structural. Lesson: regime-conditional covariance, not unconditional history.

### Q11 — When would you deliberately choose GMV over the tangency portfolio?
**Testing:** knowing which inputs you actually own.
**Answer:** Whenever your μ estimates carry no information relative to their error bars — most horizons for most shops. GMV needs only Σ, which is estimable to usable precision from 3-5 years of data (variances converge far faster than means), and empirically sits near-max Sharpe anyway because the frontier is flat near its minimum. Add ERC if you want deliberate risk budgeting across sleeves rather than minimum total variance.
**Follow-up trap:** *"GMV ignores returns entirely — isn't that throwing away information?"* — Only if the information is real. Black-Litterman formalizes the compromise: start from equilibrium-implied μ, tilt only where you hold genuine views with stated confidence.

### Q12 — A client demands "market-beating returns with less than market risk." First response?
**Testing:** expectation management + framework selection.
**Answer:** Decompose the claim: beating the market with lower beta requires either leverage on diversified risk (risk-parity logic), factor tilts with positive premia (accepting tracking-error pain years), or genuine skill (rare, capacity-limited). Quantify the tradeoff menu — expected excess return vs TE budget vs drawdown tolerance — and get them to sign a policy statement; otherwise every inevitable underperformance year becomes your model's fault.
**Follow-up trap:** *"Just show them backtests."* — Backtests without cost/slippage/tax realism and walk-forward discipline are marketing; commit to reporting against stated benchmarks ex ante, and disclose that factor spreads have decade-long droughts (value 2010-2020).

## Red flags

- Quoting CAPM betas as if the SML slope were settled empirics (it runs flat).
- Presenting an efficient frontier computed from sample moments without mentioning estimation error.
- Confusing capital weights with risk contributions in a "balanced" portfolio.
- Claiming risk parity is unlevered buy-and-hold bonds+stocks.
- No answer for why 1/N is competitive (estimation error dominates).
- Treating published factor premia as constants rather than decaying, crowded trades.
- Recommending max-Sharpe optimization on more assets than independent observations.
- Ignoring transaction costs and taxes entirely in rebalancing advice.

## Cheat card

```
MVO        min w'Sigma w  s.t. mu'w = r, 1'w = 1
           KKT -> w linear in r; frontier = hyperbola
           tangency  w ∝ Sigma^-1 (mu - rf)
           GMV       w = Sigma^-1 1 / (1'Sigma^-1 1)   [no mu needed]
CAPM       E[Ri] = Rf + beta(E[Rm]-Rf), beta=Cov/Var
           idiosyncratic risk earns ZERO (diversify free)
           empirical SML flat -> BAB premium (Frazzini-Pedersen 14')
FACTORS    R = a + b'MKT,SMB,HML(,UMD,RMW,CMA) + e
           zoo: 316 factors (HLZ '16), demand t>3; decay post-publication
RISK PARITY RC_i = w_i(Sigma w)_i / sigma^2 equalized
           2-asset ERC: w_i = sigma_j/(sigma_i+sigma_j)
           60/40 -> ~93/7 risk split; RP levers bonds ~2-3x @10% vol target
EST ERROR  mu: SE ~ sigma/sqrt(T) (60m on 16% vol -> ~2.3%/yr!)
           N~T => singular Sigma; Ledoit-Wolf shrink 10-40%
           1/N beats naive MVO out-of-sample (DGU 09, 7 datasets)
REGIMES    2022: SPX -18%, Agg -13% (worst ever), corr flipped +
           RP dd ~20-30%; correlation is regime-conditional
PROD       BL views · turnover/cost-aware opt · PSD projection ·
           factor-cov for big N · walk-forward + purge (T24-ts-validation)
```

## Sources

- [Markowitz, H. (1952). Portfolio Selection. Journal of Finance 7(1)](https://www.jstor.org/stable/29779744); accessed 2026-08-23
- [Sharpe, W. (1964). Capital Asset Prices. Journal of Finance 19(3)](https://www.jstor.org/stable/29779523); accessed 2026-08-23
- [DeMiguel, Garlappi, Uppal (2009). Optimal Versus Naive Diversification. Review of Financial Studies](https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901); accessed 2026-08-23
- [Frazzini, Pedersen (2014). Betting Against Beta. Journal of Financial Economics](https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf); accessed 2026-08-23
- [Harvey, Liu, Zhu (2016). ...and the Cross-Section of Expected Returns. Review of Financial Studies](https://academic.oup.com/rfs/article/29/1/5/1585459); accessed 2026-08-23
- [Ledoit, Wolf (2004). Honey, I Shrunk the Sample Covariance Matrix. Journal of Portfolio Management](https://ssrn.com/abstract=422032); accessed 2026-08-23
- [Fama-French Data Library (SMB/HML/RMW/CMA series)](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html); accessed 2026-08-23
- [López de Prado (2016). Building Diversified Portfolios that Outperform Out-of-Sample (HRP)](https://ssrn.com/abstract=2708678); accessed 2026-08-23

## Changelog

- 2026-08-23 — created




