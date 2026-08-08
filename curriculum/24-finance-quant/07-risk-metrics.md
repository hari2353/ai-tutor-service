# Value at Risk, Expected Shortfall, Stress Testing, and Backtesting Risk Models

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-portfolio (covariance estimation), T24-ts-validation (backtesting discipline)
> **Module id:** `T24-risk-metrics` · **Tags:** risk, critical
> **Lab:** `labs/python/07-risk-metrics/`

## The 30-second version

Value at Risk answers "how much could I lose on a bad day at confidence level c" — three ways to compute it (parametric/Gaussian, historical simulation, Monte Carlo) will disagree with each other on the same portfolio because they make different assumptions about the tail: for a $10M portfolio with 0.05% daily mean return and 1.2% daily volatility, 1-day 99% VaR comes out to **$274,162 parametric**, **$307,776 Monte Carlo with fat-tailed (Student-t, 5 df) returns**, and roughly **$375,000 historical simulation** on a stylized empirical sample — the gap is fat tails and skew that the Gaussian assumption erases. VaR's structural flaw is that it is a single quantile, not a coherent risk measure — it can be **non-subadditive** (diversification can look like it *increases* risk under VaR, which is absurd), which a concrete two-independent-bonds counterexample proves numerically (VaR(A)+VaR(B)=$0 but VaR(A+B)=$100), while Expected Shortfall (the average loss *beyond* the VaR threshold) is provably coherent and never does this ($80+$80=$160 ≥ $103.20=ES(A+B) in the same example). This is exactly why the Basel Committee's Fundamental Review of the Trading Book (FRTB, finalized 2019) replaced 99% VaR with **97.5% Expected Shortfall** as the market-risk capital metric for banks using internal models — the confidence levels were calibrated so that, under a normal distribution, they'd produce roughly the same number, but ES additionally captures tail severity and satisfies subadditivity, VaR does neither. Regulators don't just trust a bank's VaR model on faith — they backtest it daily against realized P&L using the **Kupiec proportion-of-failures test** (is the exception rate statistically consistent with the stated confidence level?) and the **Christoffersen independence test** (are exceptions clustering in time, which a correctly-calibrated iid model shouldn't produce?), and Basel's traffic-light system escalates the capital multiplier from 3.0x toward 4.0x as exceptions accumulate past 4 out of 250 trading days.

## Why this gets asked

Every risk-adjacent interview at a bank or fintech touches VaR because it's the metric every risk officer, regulator, and board member has internalized as the common language for "how much risk are we carrying" — but an interviewer who has actually run a market-risk desk has also watched a VaR model pass its backtest for two years and then get blown through by 8 sigma during a crisis (2008, March 2020), and wants to know if you understand *why* that happens structurally, not just how to compute the number. The real test is whether you know VaR's mathematical failure mode (non-subadditivity, tail-blindness) cold enough to explain why regulators moved away from it for capital purposes, and whether you can reason about model validation (backtesting) as an ongoing statistical discipline rather than a one-time model-build exercise — this is the same muscle a Principal engineer needs for any production ML system whose failure mode is "looks fine until a regime shift, then catastrophically wrong."

---

## Lineage: past → present → future

**What came before.** Before Value at Risk, risk management on a trading desk was largely a patchwork of notional position limits, gross/net exposure caps, and duration/gap analysis for interest-rate books — none of which produced a single, comparable number across different asset classes, so a risk committee had no way to answer "which desk is riskier, the FX book or the equity derivatives book" except by comparing incommensurate limit-utilization percentages. The specific pain that killed this approach: as derivatives books grew more complex through the 1980s (following the 1987 crash, which exposed how poorly firms understood portfolio-level tail risk), banks needed one number that aggregated risk across instruments with genuinely different risk drivers, and notional limits couldn't do that because a $100M notional interest-rate swap and a $100M notional equity option carry wildly different actual risk.

**Where it stands now.** JPMorgan's RiskMetrics methodology (developed internally from the late 1980s, published publicly in 1994 under Til Guldimann) popularized VaR as that single number, and the Basel Committee's 1996 Market Risk Amendment then let banks use internal VaR models (99% confidence, 10-day horizon) to compute regulatory market-risk capital, cementing VaR as the industry standard for nearly two decades. VaR (in parametric, historical, and Monte Carlo forms) remains the most board-level-understood risk metric as of 2026 — it's intuitive ("we could lose $X on a bad day") in a way that a lot of more sophisticated risk measures aren't — but its coherence failure (proven formally by Artzner, Delbaen, Eber, and Heath's 1999 "Coherent Measures of Risk," which showed VaR can violate subadditivity) combined with its blindness to tail severity beyond the threshold led the Basel Committee's Fundamental Review of the Trading Book (FRTB, finalized January 2019, phased into national implementations through the 2020s as part of the broader Basel III/IV "endgame") to replace 99% VaR with 97.5% Expected Shortfall for internal-models-based market-risk capital specifically. In practice, most large banks in 2026 run VaR and ES in parallel — VaR for desk-level limits and board reporting because it's the number people intuitively understand, ES for FRTB regulatory capital because it's the number regulators now require — while backtesting both against realized P&L is a continuous, automated daily process, not an annual model-validation exercise.

**Where it's heading.** FRTB implementation is still an active, uneven rollout across jurisdictions as of 2026 (the EU and UK are further along than the US, whose Basel III Endgame re-proposal timeline is covered in the Basel module), so a genuinely mixed regulatory landscape — 99% VaR still legally governing capital in some jurisdictions, 97.5% ES in others — will persist for at least the next few years with high confidence. Extreme value theory (EVT) and machine-learning-based tail models (aiming to capture fat tails and regime shifts better than either Gaussian-parametric or plain historical simulation) are active research and early-production directions, but confidence here is moderate at best: regulators remain genuinely cautious about approving opaque models for regulatory capital calculations precisely because of the model risk management and explainability burden covered in the MRM module, so a widely-adopted "black-box tail model" replacing today's three standard VaR methodologies for regulatory purposes specifically is speculative, not a near-term certainty.

---

## Mental model

```
LOSS DISTRIBUTION (right side = losses, tail = bad days)

 density
   |            ___
   |           /   \
   |          /     \___
   |         /          \___
   |        /               \_____              <- fat left-over tail
   |_______/______________________\_______________________> loss ($)
                          |<--- worst 1% of outcomes --->|
                          ^                              
                        VaR_99%                          
                    (ONE point: the threshold             
                     itself, tells you nothing            
                     about how bad it gets past it)

                          |<--------- ES_99% --------->|
                          = the AVERAGE loss across the entire
                            worst-1% region, not just its edge

VaR asks:  "what's the loss I will not exceed 99% of the time?"
ES asks:   "GIVEN that I'm in the worst 1%, what do I lose ON AVERAGE?"

COHERENCE: VaR can penalize diversification (non-subadditive).
           ES cannot -- it is a proven coherent risk measure.
           This single mathematical fact is why FRTB replaced
           99% VaR with 97.5% ES for market-risk capital.
```

The one-line mental model: **VaR tells you where the cliff edge is; Expected Shortfall tells you how far the fall is once you're over it — and only one of those two numbers is provably safe to add up across a portfolio.**

---

## How it actually works

### Three ways to compute VaR, on the same portfolio

Take a $10,000,000 portfolio with an estimated daily mean return `μ=0.05%` and daily volatility `σ=1.2%` (roughly 19% annualized, a reasonable diversified-equity-book figure). All three methods target 1-day, 99% VaR.

**Parametric (variance-covariance / Gaussian).** Assume returns are normally distributed. `VaR_c = V·(z_c·σ − μ)`, where `z_c` is the standard normal quantile at confidence `c` (`z_0.99 = 2.3263`).
```
VaR_99% = 10,000,000 × (2.3263 × 0.012 − 0.0005) = $274,162
```
Fast, closed-form, and the standard first cut — but only as good as the normality assumption, which understates real market tails badly (see below).

**Historical simulation.** No distributional assumption at all: take the last `N` (commonly 250–500) days of actual portfolio returns, sort them, and read off the empirical `(1−c)` quantile directly. For `N=250` at 99% confidence, `250×0.01=2.5`, so the VaR sits between the 2nd- and 3rd-worst historical daily loss, interpolated. **Stylized worked example**: if the worst five historical daily returns in the sample were `−4.8%, −3.9%, −3.6%, −3.1%, −2.7%`, linear interpolation between rank 2 (`−3.9%`) and rank 3 (`−3.6%`) at position 2.5 gives `−3.75%`, so `VaR_99% ≈ 10,000,000 × 0.0375 = $375,000`. This is meaningfully higher than the parametric figure because real return distributions are negatively skewed and fat-tailed (crashes are bigger and more frequent than a Gaussian predicts) — historical simulation captures whatever shape actually happened, at the cost of needing enough history and implicitly assuming the future tail resembles the sampled past.

**Monte Carlo.** Simulate a large number of return draws from an explicitly chosen (and ideally more realistic than Gaussian) distribution, then read the empirical quantile off the simulated sample, same as historical simulation but on synthetic data. Using a Student-t distribution with 5 degrees of freedom (fatter tails than Gaussian, a common practitioner choice) scaled to match the same `μ=0.05%, σ=1.2%`: the 99th-percentile t-quantile is `t_0.99,df=5 = 3.365` versus the Gaussian `z_0.99 = 2.326`, so after scaling (`t`-distribution variance is `df/(df−2)`, requiring a scale factor of `σ/√(5/3) = 0.00930`):
```
VaR_99% = 10,000,000 × (3.365 × 0.00930 − 0.0005) = $307,776
```
Between the parametric and historical figures — capturing kurtosis (fat tails) but, in this simple iid-t specification, still missing the skew and volatility clustering that historical simulation picked up. **The ordering `$274K < $308K < $375K` is the pedagogical point**: every VaR number is conditional on a modeling choice about the tail, and the choice matters by tens of thousands of dollars on the same portfolio, same day, same confidence level.

### Expected Shortfall (CVaR): the average loss beyond the threshold

Expected Shortfall (also called Conditional VaR) at confidence `c` is the **expected loss given that the loss exceeds VaR_c** — it uses the entire tail, not just its edge. For a Gaussian return distribution, ES has a closed form:
```
ES_c = V·(σ·φ(z_c)/(1−c) − μ)
```
where `φ` is the standard normal density. At `c=0.99`, `z_0.99=2.3263`, `φ(2.3263)=0.026652`, so the ES multiplier is `0.026652/0.01 = 2.6652` versus VaR's multiplier of `z_0.99=2.3263`:
```
ES_99% = 10,000,000 × (2.6652 × 0.012 − 0.0005) = $314,826
ES_99% / VaR_99% = $314,826 / $274,162 = 1.148
```
**For a Gaussian distribution, 99% ES is always about 15% larger than 99% VaR** — a useful sanity-check ratio. Real (fat-tailed) distributions push this ratio higher, because ES is sensitive to how bad the tail actually gets and VaR isn't.

### Why VaR isn't coherent, and ES is — with the actual numbers

A risk measure `ρ` is **coherent** (Artzner, Delbaen, Eber, Heath, 1999) if it satisfies four axioms, the practically important one being **subadditivity**: `ρ(A+B) ≤ ρ(A) + ρ(B)` — combining two positions should never look riskier than holding them separately, because that's the entire mathematical content of "diversification helps." VaR can violate this. Concrete counterexample, verified numerically:

Two independent bonds, each with a 4% annual probability of default and a loss of $100 given default (zero otherwise). At 95% confidence:

| | Single bond A (or B) | Portfolio A+B (independent) |
|---|---|---|
| P(loss=0) | 96% | 92.16% |
| P(loss=100) | 4% | 7.68% |
| P(loss=200) | — | 0.16% |
| **VaR₉₅%** | **$0** (96% ≥ 95%, so the 95th percentile loss is 0) | **$100** (92.16% < 95%, so the 95th percentile falls in the "one default" bucket) |
| **ES₉₅%** | **$80** | **$103.20** |

`VaR(A) + VaR(B) = $0 + $0 = $0`, but `VaR(A+B) = $100` — **the combined position appears riskier than the sum of its parts under VaR**, purely because each individual bond's default probability (4%) sits just under the 5% threshold, hiding the risk entirely, while the *combined* probability of at least one default (`1−0.96²=7.84%`) pushes past 5% and reveals it discontinuously. This is not a pathological edge case; it's a generic feature of VaR applied to any loss distribution with a probability mass concentrated just below the confidence threshold, which is exactly the shape of credit and default risk. Expected Shortfall doesn't do this: `ES(A)+ES(B) = $80+$80 = $160 ≥ ES(A+B) = $103.20` — subadditivity holds, because ES averages the *entire* tail rather than reading a single quantile, so it can't be fooled by probability mass shifting just across a threshold.

**This is the precise, provable reason FRTB moved from 99% VaR to 97.5% Expected Shortfall for market-risk regulatory capital** — the confidence levels were chosen so that, under a normal distribution, 97.5% ES and 99% VaR come out close to each other (keeping the overall capital stringency roughly unchanged), but ES additionally captures tail severity and can never penalize genuine diversification the way VaR demonstrably can.

### Stress testing

VaR and ES are both fundamentally statistical — they describe "what's likely," calibrated on history or a distributional assumption. Stress testing asks a different question: "what happens to this portfolio under a specific, named scenario," independent of that scenario's historical probability. Two flavors:

- **Historical scenarios** — replay an actual past crisis (2008 GFC, March 2020 COVID liquidity shock, 1998 LTCM/Russia default, 2022 UK gilt crisis) against today's portfolio: what would today's positions have lost if that exact market move happened again?
- **Hypothetical scenarios** — construct a plausible-but-not-yet-observed shock (a 200bp overnight rate spike, a specific sovereign default, a sudden 40% equity drawdown combined with a credit-spread blowout) calibrated by risk management or regulators, not sampled from history at all.

**Reverse stress testing** flips the direction: instead of "given this scenario, what's the loss," it asks "what scenario would cause a loss large enough to threaten the firm's viability," forcing risk teams to identify scenarios they might not have thought to construct forward. In the US, the Fed's annual CCAR/DFAST stress tests apply this discipline supervisory-wide across large banks (>$100B in assets) using Fed-designed macroeconomic scenarios (baseline, adverse, severely adverse) to determine whether a bank can keep lending through a severe recession while staying above minimum capital ratios — stress testing isn't just a risk-management best practice, it's a binding capital-planning constraint for large US banks.

### Backtesting: is the VaR model actually calibrated?

A VaR model that claims 99% confidence should be exceeded (realized loss > predicted VaR) on roughly 1% of days — backtesting checks whether that's actually true, using realized P&L compared against the prior day's VaR forecast.

**Kupiec's Proportion-of-Failures (POF) test** checks whether the *observed exception rate* is statistically consistent with the *stated* confidence level, via a likelihood-ratio test. With `n` observations, `x` exceptions, and stated exception probability `p=1−c`:
```
LR_POF = −2·ln[ (1−p)^(n−x)·p^x / (1−x/n)^(n−x)·(x/n)^x ]     ~ χ²(1) under H0
```
**Worked example**: `n=250` trading days, 99% VaR (`p=0.01`), `x=6` exceptions observed (expected: `250×0.01=2.5`).
```
LR_POF = 3.555
```
Critical value at 5% significance, `χ²(1) = 3.841`. Since `3.555 < 3.841`, this **fails to reject** the null hypothesis that the model is correctly calibrated — borderline, but not statistically damning on its own, illustrating that Kupiec alone is not very sensitive to modest exception-count excesses.

**Christoffersen's independence test** checks something Kupiec's test entirely misses: whether exceptions *cluster* in time (a sign the model's iid assumption is wrong — real VaR breaches tend to cluster during volatility regimes, which a correctly-specified iid model shouldn't produce). It fits a two-state Markov chain to the exception indicator sequence and compares a model where transition probabilities depend on the previous day's state against a model where they don't:
```
LR_ind = −2·ln[ L(single π) / L(π01, π11) ]     ~ χ²(1) under H0
```
**Worked example**, same 6 exceptions but now with 4 of them clustered in a 4-day stretch (a volatility event) and 2 isolated: counting transitions gives `n00=240, n01=3, n10=3, n11=3`, so `π01=3/243=0.0123` (probability of an exception given yesterday was calm) versus `π11=3/6=0.50` (probability of an exception given yesterday was *also* an exception) — a fiftyfold difference, strong evidence of clustering.
```
LR_ind = 15.915
```
Critical value `χ²(1)=3.841` — **strongly rejected** (`15.915 ≫ 3.841`), even though the overall exception count alone (Kupiec) was borderline-acceptable. **This is the entire point of running both tests**: a model can have roughly the right long-run exception rate while systematically failing exactly when it matters most — clustering breaches during the exact stress period a risk model exists to warn about. The combined **conditional coverage test** sums both statistics: `LR_cc = LR_POF + LR_ind = 3.555 + 15.915 = 19.47 ~ χ²(2)`, critical value `5.991` — decisively rejected.

**Basel's traffic-light backtesting framework** translates exception counts (out of 250 days, 99% VaR) directly into a regulatory capital penalty via a multiplier `k` applied to the VaR-based capital charge: **green zone** (0–4 exceptions) keeps `k=3.00`; **yellow zone** (5–9 exceptions) steps `k` up progressively (`5→3.40, 6→3.50, 7→3.65, 8→3.75, 9→3.85`); **red zone** (10+ exceptions) sets `k=4.00` and typically triggers a supervisory review of the model itself. Our worked example's 6 exceptions land the bank in the yellow zone at `k=3.50` — a real capital cost for a model that Kupiec alone wouldn't have flagged as broken.

---

## Build it from scratch

```python
# untested sketch -- structure and all numeric outputs verified against
# the worked examples above using an independent pure-Python implementation
import numpy as np
from scipy import stats

def parametric_var(V, mu, sigma, conf=0.99):
    z = stats.norm.ppf(conf)
    return V * (z * sigma - mu)

def parametric_es(V, mu, sigma, conf=0.99):
    z = stats.norm.ppf(conf)
    phi_z = stats.norm.pdf(z)
    return V * (phi_z / (1 - conf) * sigma - mu)

def historical_var(V, returns, conf=0.99):
    # returns: array of historical daily portfolio returns
    losses = -np.sort(returns)                 # worst first
    idx = (1 - conf) * len(returns)             # e.g. 2.5 for n=250, c=0.99
    lo, hi = int(np.floor(idx)) - 1, int(np.ceil(idx)) - 1
    frac = idx - np.floor(idx)
    interp_loss = losses[lo] * (1 - frac) + losses[hi] * frac
    return V * interp_loss

def monte_carlo_var(V, mu, sigma, df=5, conf=0.99, n_sims=200_000, seed=0):
    rng = np.random.default_rng(seed)
    scale = sigma / np.sqrt(df / (df - 2))       # match target sigma
    sims = mu + scale * rng.standard_t(df, n_sims)
    losses = -np.sort(sims)
    var_return = losses[int(n_sims * (1 - conf))]
    return V * var_return

def subadditivity_demo(p=0.04, L=100, conf=0.95):
    single = {0: 1 - p, L: p}
    port = {}
    for l1, p1 in single.items():
        for l2, p2 in single.items():
            port[l1 + l2] = port.get(l1 + l2, 0) + p1 * p2

    def var_of(dist, c):
        cum = 0
        for loss in sorted(dist):
            cum += dist[loss]
            if cum >= c - 1e-12:
                return loss

    def es_of(dist, c):
        remaining, total = 1 - c, 0
        for loss in sorted(dist, reverse=True):
            take = min(dist[loss], remaining)
            total += take * loss
            remaining -= take
            if remaining <= 1e-9:
                break
        return total / (1 - c)

    return {
        "VaR_A": var_of(single, conf), "VaR_A+B": var_of(port, conf),
        "ES_A": es_of(single, conf), "ES_A+B": es_of(port, conf),
    }

def kupiec_pof(n, x, p=0.01):
    xn = x / n
    ln_null = (n - x) * np.log(1 - p) + x * np.log(p)
    ln_alt = (n - x) * np.log(1 - xn) + x * np.log(xn)
    return -2 * (ln_null - ln_alt)             # compare to chi2(1): 3.841 @ 5%

def christoffersen_independence(n00, n01, n10, n11):
    pi01 = n01 / (n00 + n01)
    pi11 = n11 / (n10 + n11)
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    ln_null = (n00 + n10) * np.log(1 - pi) + (n01 + n11) * np.log(pi)
    ln_alt = (n00 * np.log(1 - pi01) + n01 * np.log(pi01)
              + n10 * np.log(1 - pi11) + n11 * np.log(pi11))
    return -2 * (ln_null - ln_alt)             # compare to chi2(1): 3.841 @ 5%
```

Full runnable version — including a rolling nightly backtest harness that classifies exceptions into Basel's traffic-light zones and plots the exception clustering — is the lab exercise in `labs/python/07-risk-metrics/`.

---

## How it's done in production

Production risk systems (Barra/MSCI, Numerix, Murex, Calypso, or in-house engines at large banks) compute VaR and ES nightly across the full trading book, typically via a **hybrid historical/Monte Carlo approach**: full revaluation or sensitivity-based (delta-gamma) repricing of every position under thousands of historical or simulated scenarios, aggregated up to desk, business-line, and firm level. Backtesting compares two distinct P&L series against the prior day's VaR: **hypothetical (clean) P&L** — repricing yesterday's *exact* portfolio against today's actual market moves, holding positions fixed, isolating the risk-model's accuracy — versus **actual (dirty) P&L**, which includes intraday trading, fees, and other effects the VaR model was never meant to capture. FRTB requires both to be tracked and reconciled; a bank whose hypothetical-P&L backtest passes but whose actual-P&L backtest routinely fails has a model that's fine but a trading-desk risk-taking pattern that isn't being captured by end-of-day snapshots.

| Symptom | Cause | Fix |
|---|---|---|
| Backtest exceptions cluster in a short window rather than spreading uniformly across the year | Model assumes iid returns (constant volatility), but real markets have volatility clustering (GARCH-type regimes) that a static VaR window doesn't adapt to fast enough | Use exponentially weighted volatility (EWMA) or a GARCH-based conditional VaR that reacts to recent volatility, not a flat trailing-window estimate; run Christoffersen's test routinely, not just Kupiec's |
| VaR looks stable and well-calibrated for years, then blows through 5-10x on a single day | Historical/parametric VaR is calibrated on a "normal" regime and structurally cannot see a regime it hasn't sampled (2008, March 2020); this is the tail VaR is blind to by construction | Overlay stress testing and reverse stress testing as a mandatory complement to VaR/ES, never a substitute — VaR tells you the likely case, stress tests tell you the scenario that breaks you |
| Regulatory capital charge jumps sharply after a quiet period with no obvious desk-level risk change | Basel's traffic-light multiplier `k` steps up mechanically once exception count crosses 4 out of 250 days (yellow zone), even if the exceptions were individually small or explainable | Investigate root cause immediately at 3-4 exceptions rather than waiting for the yellow-zone threshold to be crossed; document explainable exceptions for supervisory dialogue, since the multiplier applies mechanically regardless of cause |
| Two risk systems (front-office pricing risk vs independent risk-management VaR) report materially different VaR for the same book | Different valuation models, market data snapshots, or scenario sets feeding nominally the same VaR calculation — a very common large-bank reconciliation problem | Establish a single golden source for market data and position feeds into both systems, and run daily P&L attribution/reconciliation between front-office and independent risk numbers as a standing control, not an ad hoc investigation |
| Monte Carlo VaR estimate is noisy and changes meaningfully run-to-run with the same inputs | Too few simulation paths for the tail quantile being estimated (99% VaR needs many more effective tail samples than the total path count suggests) | Increase path count specifically in variance-reduction-aware ways (importance sampling toward the tail, antithetic variates) rather than brute-force scaling, and report a confidence interval around the VaR estimate itself, not a single point number |

---

## Tradeoffs & when NOT to use it

- **Don't report a single VaR number as "the" risk of a portfolio without the confidence level, horizon, and methodology attached.** "$300K VaR" is meaningless without knowing 95% vs 99%, 1-day vs 10-day, and parametric vs historical vs Monte Carlo — the worked example above shows a >35% spread across methodologies on identical inputs.
- **Don't aggregate VaR across desks by simple addition and assume it bounds total firm risk.** Because VaR isn't subadditive, `VaR(desk A)+VaR(desk B)` is *not* guaranteed to be an upper bound on `VaR(A+B)` — the counterexample above is not a corner case, it's a generic property whenever loss probability mass sits near the confidence threshold, common in credit and default-risk books specifically.
- **Don't use VaR (of either kind) as the sole risk gate for tail-heavy, illiquid, or credit-default-driven books.** VaR and even ES are calibrated on recent history or a chosen distribution; genuinely novel regime shifts (a first-of-its-kind sovereign default, a liquidity freeze) are exactly what neither statistical measure can see coming — that's what stress testing and reverse stress testing exist for, and skipping them because "VaR looks fine" is a well-documented failure mode (AIG and multiple dealer desks in 2008 had VaR models that looked calibrated right up until they didn't).
- **Don't treat a passing Kupiec test as sufficient model validation.** A model can have the statistically correct long-run exception rate while clustering all its failures during the exact crisis period it exists to warn about — always run Christoffersen's independence test (or the combined conditional-coverage test) alongside Kupiec, not instead of it.
- **Don't assume 97.5% ES is a strictly "more conservative" replacement for 99% VaR in every situation.** The FRTB calibration targets rough equivalence *under normality*; for genuinely fat-tailed or skewed books the two can diverge meaningfully, and ES's greater tail-sensitivity also makes it noisier to estimate (it needs more of the tail's shape, not just one quantile) — a real practical cost, not just a theoretical footnote, when data is scarce.

---

## Interview questions

### Q1 — Compute 1-day 99% parametric VaR for a $10M portfolio with daily mean return 0.05% and daily volatility 1.2%.
**Testing:** whether the formula and the ability to plug in numbers correctly are both there, not just the concept.
**Answer:** `VaR_99% = V·(z_0.99·σ − μ) = 10,000,000 × (2.3263 × 0.012 − 0.0005) = $274,162`.
**Follow-up trap:** *"Why do some practitioners drop the `μ` term entirely for short-horizon VaR?"* — at a 1-day horizon, `μ` (a fraction of a percent) is small relative to `z·σ` and is itself a noisy estimate (as covered in the portfolio-theory module — mean returns are much harder to estimate precisely than volatility), so many desks conservatively set `μ=0`, which slightly *increases* the VaR estimate here (to `10,000,000×2.3263×0.012=$279,156`) and removes a noisy, weakly-estimated input from a number regulators scrutinize closely.

### Q2 — Why did parametric, historical, and Monte Carlo VaR give three different answers ($274K, $308K, $375K) on the exact same portfolio?
**Testing:** understanding that VaR methodology is a modeling choice about the tail, not a single well-defined number.
**Answer:** Parametric assumes Gaussian returns, understating real tail risk (no skew, no excess kurtosis). Monte Carlo with a Student-t(5 df) distribution adds fat tails (kurtosis) but, in this simple iid specification, still assumes symmetric, time-independent shocks. Historical simulation makes no distributional assumption at all — it reflects whatever skew, kurtosis, and volatility clustering actually happened in the sampled window, which is why it produced the highest (most conservative) figure here.
**Follow-up trap:** *"Which of the three would you trust most for a book with genuine tail/crash exposure, like a short-volatility options book?"* — historical simulation, generally, *if* the sample window includes a real stress period (otherwise it's blind to tails it hasn't sampled, same failure mode as parametric); the strongest practical answer is to run all three and treat material disagreement between them as a signal to investigate the book's actual return distribution, not to pick whichever number is most convenient.

### Q3 — Walk through the subadditivity counterexample: two independent bonds, 4% default probability each, $100 loss given default. Why does 95% VaR make diversification look bad?
**Testing:** the mechanical proof, not just the claim that "VaR isn't subadditive."
**Answer:** Each bond alone has `P(loss=0)=96% ≥ 95%`, so its 95% VaR is $0 — the 4% default probability sits entirely below the 5% tail threshold, invisible to VaR. Combined, `P(no default)=96%²=92.16% < 95%`, so the 95th percentile now falls in the "at least one default" bucket, making combined VaR $100. `VaR(A)+VaR(B)=$0` but `VaR(A+B)=$100` — combining the positions makes VaR *worse*, the opposite of what diversification should do.
**Follow-up trap:** *"Does Expected Shortfall avoid this because it's simply a larger number than VaR, or for a structural reason?"* — structural, not just magnitude: ES averages the *entire* worst-`(1−c)` tail rather than reading a single quantile, so probability mass shifting just across the confidence threshold (exactly what happened here) changes ES smoothly and proportionally rather than discontinuously — in this example `ES(A)+ES(B)=$160 ≥ ES(A+B)=$103.20`, subadditivity holds by a wide margin, and this holds for any distribution, not just this specific numeric setup (it's a proven theorem, not a coincidence of these numbers).

### Q4 — Derive the Gaussian closed-form formula for Expected Shortfall and explain why ES is always larger than VaR at the same confidence level under normality.
**Testing:** whether ES is understood as a derived quantity (conditional expectation of the tail), not a memorized formula.
**Answer:** `ES_c = E[Loss | Loss > VaR_c]`. For a normal distribution, this conditional expectation has closed form `ES_c = σ·φ(z_c)/(1−c) − μ` where `φ` is the standard normal density at the VaR quantile `z_c`. Since `φ(z_c)/(1−c) > z_c` for any `c<1` (the average of a truncated tail is always further out than the truncation point itself), ES's multiplier always exceeds VaR's — concretely at 99%, `2.6652 > 2.3263`, an ~15% gap.
**Follow-up trap:** *"Is that ~15% ES/VaR ratio a universal constant, or specific to the Gaussian assumption?"* — specific to Gaussian and to the 99% level; fatter-than-normal tails (any real market return distribution) push the ratio higher because the average of the tail moves further from the threshold as the tail gets heavier, so a materially larger observed ES/VaR ratio than ~1.15 on real data is itself a signal that the return distribution has meaningfully fat tails relative to normal.

### Q5 — Why did FRTB specifically choose 97.5% ES to replace 99% VaR, rather than, say, 99% ES?
**Testing:** understanding the calibration logic behind the regulatory change, not just that a change happened.
**Answer:** The Basel Committee calibrated the confidence level so that, under a normal distribution, 97.5% ES and 99% VaR produce approximately the same capital number (`99% VaR ≈ 97.5% ES` for Gaussian returns) — the goal was to fix VaR's structural flaws (non-subadditivity, tail-blindness) without mechanically increasing capital requirements as a side effect of the methodology switch itself.
**Follow-up trap:** *"Does that calibration hold for real, non-normal trading books, or only in the idealized Gaussian case used to pick the number?"* — only approximately; for genuinely fat-tailed books the two diverge, which is expected and by design (ES is supposed to be more sensitive to real tail risk than VaR) — the 97.5%/99% correspondence was a normal-distribution calibration anchor for setting the confidence level, not a claim that the two measures track each other on real market data.

### Q6 — What does the Kupiec POF test actually test, and what does it NOT test?
**Testing:** precise understanding of what a passing/failing backtest result means.
**Answer:** Kupiec's test checks whether the *observed exception rate* (exceptions/total days) is statistically consistent with the *stated* VaR confidence level, via a likelihood-ratio test asymptotically distributed `χ²(1)`. In the worked example (`n=250, x=6, p=0.01`), `LR_POF=3.555 < 3.841` (critical value), so the test fails to reject — the exception *count* looks roughly acceptable. It does **not** test *when* those exceptions occurred — a model that fails 6 times randomly spread across the year and a model that fails 6 times in one clustered volatility event produce the identical Kupiec statistic.
**Follow-up trap:** *"So if Kupiec passes, is the VaR model backtested and validated?"* — no, that's the entire reason Christoffersen's independence test exists as a separate, required check — a model with clustered exceptions (exactly the dangerous case, since it means the model fails when it matters most) can pass Kupiec cleanly while decisively failing Christoffersen, as the worked example shows (`LR_ind=15.915 ≫ 3.841`).

### Q7 — Walk through why the same 6 exceptions that nearly passed Kupiec's test decisively failed Christoffersen's independence test.
**Testing:** the mechanical distinction between "right average rate" and "right distribution over time."
**Answer:** Christoffersen's test fits a two-state Markov chain to the exception sequence and compares transition-probability estimates conditional on the prior day's state. With 4 of the 6 exceptions clustered in a short stretch, `π11` (probability of an exception given yesterday was also an exception) came out to `0.50`, versus `π01` (probability of an exception given yesterday was calm) at `0.0123` — a fiftyfold difference that a correctly-specified iid model should never produce. The resulting likelihood-ratio statistic (`LR_ind=15.915`) massively exceeds the `χ²(1)` critical value of `3.841`, decisively rejecting independence.
**Follow-up trap:** *"In practical risk-management terms, why does clustering matter more than the raw exception count?"* — because clustering during a specific period usually means the model failed during an actual volatility regime shift — precisely the moment a risk model's warning matters most — while a model that fails randomly with the "right" average rate is at least failing unpredictably rather than catastrophically at the worst possible time; regulators and risk committees treat clustered failures as a much more serious governance signal than the same total count spread uniformly.

### Q8 — Explain Basel's traffic-light backtesting framework and what happens to a bank's capital requirement as exceptions accumulate.
**Testing:** knowledge of the concrete regulatory consequence attached to backtesting results, not just the statistics.
**Answer:** Over a 250-day window at 99% VaR, 0-4 exceptions is the green zone (capital multiplier `k=3.00`, no penalty); 5-9 exceptions is the yellow zone, stepping `k` up progressively (`5→3.40` through `9→3.85`); 10+ exceptions is the red zone (`k=4.00`, typically triggering supervisory review of the model itself, potentially loss of internal-model approval). The worked example's 6 exceptions land in the yellow zone at `k=3.50` — a direct, mechanical increase in regulatory capital, not just a statistical footnote.
**Follow-up trap:** *"If 6 exceptions is only borderline-significant under Kupiec's test statistically, is it fair that the bank still faces a capital penalty?"* — yes, and that's intentional: Basel's traffic-light system is a conservative, mechanical penalty schedule designed to be robust to the statistical nuance of exactly how significant 6-vs-5-vs-4 exceptions are — regulators explicitly chose a blunt, hard-to-game rule over relying on banks' own significance-test interpretations, precisely because backtest statistics can be borderline in ways a bank has an incentive to argue away.

### Q9 — A market-risk model has passed backtesting cleanly for three years, then loses 8x its stated 99% VaR in a single day during a crisis. Was the model wrong?
**Testing:** understanding VaR's structural blindness to unprecedented regimes, a genuinely important distinction from "the model has a bug."
**Answer:** Not necessarily wrong in a statistical-calibration sense — a well-calibrated 99% VaR model is *expected* to be exceeded roughly 1% of the time, and an 8x breach during a genuine tail event (2008, March 2020) is consistent with the model correctly describing the "normal" regime it was calibrated on while being structurally blind to a regime shift it had never sampled. VaR (and even ES) describe *likely* outcomes conditional on historical or assumed distributions; they cannot see a truly novel shock coming by construction.
**Follow-up trap:** *"So does that mean VaR/ES backtesting is pointless for crisis preparedness?"* — no, it means backtesting validates the *statistical calibration* of the model for the regime it was built on, which is necessary but insufficient — crisis preparedness specifically requires stress testing and reverse stress testing as separate, mandatory complements, not a replacement for VaR/ES, precisely because those are the tools designed to probe scenarios outside the sampled or assumed distribution.

### Q10 — Design question: you're building the automated nightly backtesting pipeline for a bank's nine trading desks. What would you actually compute and alert on, beyond a single pass/fail Kupiec test per desk?
**Testing:** staff-level synthesis — translating the module's statistical content into an actual production system design.
**Answer:** Run both hypothetical (clean) and actual (dirty) P&L against the prior VaR forecast per desk, since FRTB requires both and their divergence itself is diagnostic (a clean-pass/dirty-fail pattern flags intraday risk-taking the snapshot model doesn't see). Compute Kupiec POF *and* Christoffersen independence (and the combined conditional-coverage statistic) rather than Kupiec alone, specifically to catch clustering. Track exception counts against Basel's traffic-light thresholds proactively (alert at 3 exceptions, not just after crossing into yellow at 5) so root-cause investigation starts before the mechanical capital penalty triggers. Cross-check parametric, historical, and Monte Carlo VaR against each other daily and alert on material divergence between methodologies (as in the worked example) as an early signal that the return distribution's shape has changed. Finally, maintain a rolling reconciliation between front-office and independent risk-management VaR numbers for the same book, since a silent divergence there is one of the most common real-world large-bank risk-system failure modes.
**Follow-up trap:** *"How would you decide the alerting threshold for methodology divergence, given VaR methods will never agree exactly?"* — set it relative to the divergence observed during a stable historical baseline period for that specific book (e.g., flag if the spread between methods exceeds 2x its own trailing 90-day average spread), rather than an absolute dollar or percentage threshold, since "normal" disagreement between methodologies varies a great deal by asset class and book composition, and a fixed threshold would either be constantly noisy for volatile books or blind for calm ones.

---

## Red flags that fail you

- Reports a VaR number without stating the confidence level, horizon, and methodology.
- Claims VaR is subadditive, or cannot explain the two-independent-bonds counterexample when asked.
- Treats a passing Kupiec test as sufficient model validation without mentioning Christoffersen's independence test or exception clustering.
- Says Expected Shortfall was adopted by FRTB simply because "it's more conservative" without connecting it to coherence/subadditivity as the actual mathematical justification.
- Cannot explain why parametric, historical, and Monte Carlo VaR give different numbers on the same portfolio.
- Treats a large VaR breach during a crisis as proof the model was "wrong" or buggy, without acknowledging VaR's structural blindness to unprecedented regimes.

---

## Cheat card

```
PARAMETRIC VaR:  VaR_c = V*(z_c*sigma - mu)         z_0.99=2.3263
  worked ($10M, mu=0.05%, sigma=1.2%): VaR_99=$274,162

HISTORICAL VaR: empirical (1-c) quantile of sorted historical returns, interpolated
  n=250, c=0.99 -> rank 2.5 (between 2nd and 3rd worst observation)

MONTE CARLO VaR: simulate from a chosen (fat-tailed) dist, read empirical quantile
  Student-t(df=5) calibrated same mu/sigma: t_0.99=3.365 -> VaR_99=$307,776

PARAMETRIC ES (Gaussian):  ES_c = V*(sigma*phi(z_c)/(1-c) - mu)
  worked: ES_99=$314,826  ->  ES_99/VaR_99 = 1.148 (Gaussian, always ~universal at 99%)

COHERENCE: subadditivity = rho(A+B) <= rho(A)+rho(B). VaR CAN VIOLATE THIS. ES CANNOT (proven, Artzner et al 1999).
  counterexample (2 bonds, p=4% default, L=$100, 95% conf):
    VaR(A)=VaR(B)=$0, VaR(A+B)=$100   -- VaR says diversifying makes it WORSE
    ES(A)=ES(B)=$80,  ES(A+B)=$103.20 -- ES(A)+ES(B)=$160 >= ES(A+B), holds

FRTB (2019): market-risk capital = 97.5% ES replaces 99% VaR (calibrated to roughly match under normality)

KUPIEC POF TEST: LR = -2*ln[(1-p)^(n-x)*p^x / (1-x/n)^(n-x)*(x/n)^x] ~ chi2(1), crit=3.841 @5%
  worked: n=250,x=6,p=0.01 -> LR=3.555 (fails to reject, borderline)

CHRISTOFFERSEN INDEPENDENCE TEST: catches CLUSTERING Kupiec misses. ~chi2(1), crit=3.841
  worked (same 6 exceptions, 4 clustered): LR_ind=15.915 (STRONGLY rejects independence)
  combined conditional coverage: LR_cc = LR_POF+LR_ind ~ chi2(2), crit=5.991

BASEL TRAFFIC LIGHT (250 days, 99% VaR): 0-4 exceptions=green(k=3.00)
  5-9=yellow (5->3.40, 6->3.50, 7->3.65, 8->3.75, 9->3.85), 10+=red(k=4.00, model review)

STRESS TESTING != VaR/ES: historical scenarios (2008, Mar-2020) + hypothetical scenarios
  + reverse stress test ("what scenario breaks us") -- covers regimes VaR structurally can't see
```

## Sources

- [Coherent Measures of Risk — Artzner, Delbaen, Eber, Heath, Mathematical Finance (1999)](https://onlinelibrary.wiley.com/doi/10.1111/1467-9965.00068) — accessed 2026-08-08
- [Minimum capital requirements for market risk (FRTB) — Basel Committee on Banking Supervision, BIS (2019)](https://www.bis.org/bcbs/publ/d457.pdf) — accessed 2026-08-08
- [Supervisory framework for the use of "backtesting" in conjunction with the internal models approach — Basel Committee on Banking Supervision, BIS (1996)](https://www.bis.org/publ/bcbs22.pdf) — accessed 2026-08-08
- [Techniques for Verifying the Accuracy of Risk Measurement Models — Kupiec, Journal of Derivatives (1995)](https://jod.pm-research.com/content/3/2/73) — accessed 2026-08-08
- [Evaluating Interval Forecasts — Christoffersen, International Economic Review (1998)](https://www.jstor.org/stable/2527341) — accessed 2026-08-08
- [RiskMetrics Technical Document — J.P. Morgan/Reuters (1996)](https://www.msci.com/documents/10199/5915b101-4206-4ba0-aee2-3449d5c7e95a) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
