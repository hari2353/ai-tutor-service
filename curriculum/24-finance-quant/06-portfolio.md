# Modern Portfolio Theory Derived, CAPM, Factor Models, Risk Parity

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-derivatives (mean-variance intuition helpful)
> **Module id:** `T24-portfolio` · **Tags:** quant
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Modern Portfolio Theory is a single Lagrangian optimization — minimize `w'Σw` subject to `w'μ=target return` and `w'1=1` — whose first-order condition, `Σw=λμ+γ1`, gives the **two-fund separation theorem**: every efficient portfolio is a weighted combination of exactly two portfolios, the minimum-variance portfolio (`w=Σ⁻¹1/(1'Σ⁻¹1)`) and the tangency (maximum-Sharpe) portfolio (`w∝Σ⁻¹(μ−Rf·1)`). For a 3-asset example (stocks 8%/15% return/vol, bonds 4%/5%, commodities 6%/20%, with realistic cross-correlations), the tangency portfolio comes out to `24.0%/74.0%/2.1%` weights, `5.0%` expected return, `4.7%` volatility, Sharpe `0.635` — and if the market portfolio equals this tangency portfolio (CAPM's core assumption), each asset's beta (`Cov(Rᵢ,Rm)/Var(Rm)`) exactly reproduces its own expected return through `E[Rᵢ]=Rf+βᵢ(E[Rm]−Rf)`, because that equation *is* the tangency portfolio's own optimality condition, not a separate empirical claim. The single most important practical fact, though, is that this whole framework is dangerously unstable to estimate in practice: with two assets at nearly the same volatility and correlated `0.95`, moving one asset's expected return from `8.0%` to `8.5%` — noise-level, well within any realistic estimation error — flips the optimal tangency weights from roughly balanced to a leveraged `-28%/+128%` position, and to `9%` versus `8%` swings it to `-100%/+200%`; the covariance matrix's condition number (`39` here) directly measures how violently mean-variance optimization amplifies small input noise into extreme, unstable portfolios (Michaud's "estimation-error maximization," 1989). Fama-French factor models (three-factor 1992/93: market, size SMB, value HML; five-factor 2015: `+` profitability RMW, investment CMA) decompose returns into systematic risk exposures rather than relying on a single market beta. Risk parity sidesteps the whole unstable-mean-estimation problem by not using expected returns at all — allocate so every asset contributes equal risk (`w_i·(Σw)_i` equal across `i`), which for the same 3-asset example gives stable, sensible weights (`19.9%/67.0%/13.1%`, each contributing exactly `33.3%` of total portfolio risk) that don't swing wildly on a 50bp return-estimate change.

## Why this gets asked

Because "explain mean-variance optimization" is table stakes, but "explain why nobody runs raw mean-variance optimization on real money without heavy modification" is the actual signal — every quant, portfolio-construction, or risk-adjacent interviewer has either watched an unconstrained optimizer produce an absurd, concentrated, leveraged-long-short portfolio from noisy return estimates, or built the shrinkage/Black-Litterman/risk-parity machinery specifically to prevent that from happening. This question tests whether a candidate understands portfolio theory as a genuine mathematical result (can derive it) while also having the practitioner's skepticism about applying it naively (knows exactly *why* it breaks and what the standard fixes are) — the combination of both is what separates someone who read a textbook chapter from someone who could credibly sit on a portfolio-construction team.

---

## Lineage: past → present → future

**What came before.** Before Harry Markowitz's "Portfolio Selection" (1952), investment practice treated diversification qualitatively — "don't put all your eggs in one basket" — without any formal way to quantify *how much* diversification benefit a given combination of assets provided, or to systematically trade off expected return against risk. The specific pain: an investor comparing two portfolios with different assets had no rigorous way to determine which offered better risk-adjusted characteristics, and portfolio construction was closer to qualitative judgment than optimization.

**Where it stands now.** Markowitz's mean-variance framework (Nobel Prize, 1990, shared with Sharpe and Miller) remains the conceptual foundation of virtually all portfolio construction as of 2026 — every factor model, risk-parity scheme, and portfolio optimizer is either a direct application or a deliberate modification of it. Sharpe's (1964), Lintner's (1965), and Mossin's (1966) independently-derived CAPM extended Markowitz's normative framework into a positive (testable) equilibrium theory, and Fama-French's three-factor (1992/1993) and five-factor (2015) models emerged specifically because CAPM's single-factor beta was empirically shown to leave substantial, systematic return variation unexplained (the size and value effects, well documented since the 1980s-90s, then profitability and investment effects added in 2015). The live, well-known practical problem — mean-variance optimization's extreme sensitivity to estimation error in expected returns, formalized as "estimation-error maximization" by Michaud (1989) — has never been theoretically solved, only worked around: shrinkage estimators (Ledoit-Wolf, 2004, for the covariance matrix), the Black-Litterman model (1992, blending market-equilibrium-implied returns with an investor's explicit views under a Bayesian framework to avoid using noisy raw historical means directly), and risk parity (popularized by Bridgewater's "All Weather" approach and formalized academically by Qian, 2005, and Maillard-Roncalli-Teiletche, 2010) all exist specifically to route around the instability rather than eliminate it.

**Where it's heading.** Robust and Bayesian portfolio optimization (explicitly modeling parameter uncertainty rather than treating sample estimates as known-true inputs) and machine-learning-based factor discovery (extending the Fama-French-style linear factor framework with nonlinear, data-driven factor construction) are active production and research directions as of 2026. Confidence is high that the core mean-variance mathematics remains the reference framework indefinitely (it's a correct, elegant result within its assumptions); confidence is moderate-to-speculative that ML-discovered factors meaningfully displace the human-interpretable Fama-French-style factor taxonomy in mainstream institutional use, given how much value asset owners and regulators place on being able to explain *why* a factor should carry a risk premium, not just that it historically has.

---

## Mental model

```
EFFICIENT FRONTIER (risk on x-axis, return on y-axis):

  return
    ^                                    * tangency (max Sharpe) portfolio
    |                              *  <- Capital Market Line (from Rf, through tangency)
    |                        *
    |                  *
    |            * <- minimum variance portfolio (leftmost point of the frontier)
    |      *
    |  Rf  (risk-free asset)
    +------------------------------------------> risk (std dev)

TWO-FUND SEPARATION: every efficient portfolio = a combination of
  (1) the minimum-variance portfolio   w_minvar = Sigma^-1 * 1 / (1' Sigma^-1 1)
  (2) the tangency portfolio           w_tan    ~ Sigma^-1 * (mu - Rf*1)
  ... mixed in different proportions depending on the investor's risk aversion

CAPM: IF everyone holds the tangency portfolio (market clears at that portfolio)
  THEN each asset's required return is set by ITS CONTRIBUTION TO MARKET RISK:
  E[R_i] = Rf + beta_i * (E[Rm] - Rf),   beta_i = Cov(R_i, Rm) / Var(Rm)

INSTABILITY: Sigma^-1 AMPLIFIES noise in mu, especially when assets are
  highly correlated (ill-conditioned Sigma) -- tiny return-estimate changes
  can flip optimal weights from balanced to extreme leveraged long/short.

RISK PARITY sidesteps mu ENTIRELY: allocate so every asset contributes
  EQUAL RISK, not equal capital and not "optimal" given noisy return forecasts.
```

The one-line mental model: **MPT is a correct, elegant optimization whose Achilles' heel is that `Σ⁻¹` amplifies whatever noise is in your expected-return estimates, and every practical portfolio-construction technique since 1989 exists specifically to manage that one weakness.**

---

## How it actually works

### The Lagrangian derivation and two-fund separation

Minimize portfolio variance `w'Σw` subject to a target expected return `w'μ=r` and full investment `w'1=1`. The Lagrangian is `L=½w'Σw−λ(w'μ−r)−γ(w'1−1)`. The first-order condition (`∂L/∂w=0`) gives `Σw=λμ+γ1`, so:
```
w = λ·Σ⁻¹μ + γ·Σ⁻¹1
```
**This is the two-fund separation theorem stated directly**: every point on the efficient frontier is a linear combination of exactly two fixed portfolios (`Σ⁻¹μ` and `Σ⁻¹1`, each normalized to sum to `1`), with `λ` and `γ` (determined by the target return `r` and the constraint `w'1=1`) controlling the mix. Practically: you never need to re-solve the full optimization for every possible target return — compute the two component portfolios once, then blend.

**The minimum-variance portfolio** is the special case with no return target at all, just `min w'Σw` s.t. `w'1=1`: `w_minvar=Σ⁻¹1/(1'Σ⁻¹1)`. **Worked example** (stocks `μ=8%,σ=15%`; bonds `μ=4%,σ=5%`; commodities `μ=6%,σ=20%`; correlations `ρ_SB=−0.2, ρ_SC=0.3, ρ_BC=0.0`): `w_minvar=(13.5%, 84.8%, 1.8%)`, giving portfolio return `4.57%` and volatility `4.38%` — heavily weighted to bonds, which is intuitive (lowest individual volatility, and negative correlation with stocks provides diversification benefit).

**The tangency (maximum-Sharpe) portfolio** maximizes `(w'μ−Rf)/√(w'Σw)`; the first-order condition of this ratio gives `w∝Σ⁻¹(μ−Rf·1)`, normalized to sum to `1`. **Worked example** (same three assets, `Rf=2%`): `w_tan=(24.0%, 74.0%, 2.1%)`, return `5.00%`, volatility `4.73%`, Sharpe `=(5.00%−2%)/4.73%=0.635`.

### CAPM, derived directly from the tangency portfolio

CAPM's core assumption is that in equilibrium, since every investor (with homogeneous expectations) holds some combination of the risk-free asset and the *same* tangency portfolio (two-fund separation again), the market-clearing condition forces the market-cap-weighted portfolio to *equal* the tangency portfolio. Given that, each asset's contribution to the tangency portfolio's own optimality condition (`Σw_tan∝μ−Rf1`, from the derivation above) can be rewritten per-asset as `Cov(Rᵢ,R_tan)∝μᵢ−Rf`, and substituting `R_tan=Rm`:
```
E[Rᵢ] = Rf + βᵢ(E[Rm]−Rf),      βᵢ = Cov(Rᵢ,Rm)/Var(Rm)
```
**This is not a separate empirical claim bolted onto MPT — it is the tangency portfolio's own first-order optimality condition, restated per-asset.** Worked example, computing each asset's beta against the tangency portfolio from above: `β_stocks=2.00, β_bonds=0.667, β_commodities=1.333`. Plugging into the CAPM formula reproduces the original expected returns *exactly* (`Rf+β·(5.00%−2%)` gives back `8%, 4%, 6%` respectively) — which is expected and instructive, not a coincidence: since the tangency portfolio was constructed using these exact `μ` values, its own optimality condition must be self-consistent with them. **In a real application, `μ` isn't known and CAPM is used the other direction** — estimate `β` from historical return covariances (much more stable to estimate than `μ` itself, as covered below) and use the CAPM equation to back out a *required* return for capital-budgeting or cost-of-capital purposes, rather than to reproduce an already-known input.

### Fama-French: what CAPM's single beta misses

Empirically, CAPM's single market beta leaves substantial, *systematic* (not random) return variation unexplained — small-cap stocks and high book-to-market ("value") stocks have historically earned higher average returns than their market beta alone would predict. The **three-factor model** (Fama & French, 1992/1993) adds two factors to the regression: `Rᵢ−Rf=α+b(Rm−Rf)+s·SMB+h·HML+ε`, where `SMB` ("small minus big") is the return of small-cap stocks minus large-cap, and `HML` ("high minus low") is high book-to-market (value) minus low book-to-market (growth). The **five-factor model** (Fama & French, 2015) adds `RMW` ("robust minus weak" operating profitability — profitable firms minus unprofitable) and `CMA` ("conservative minus aggressive" investment — firms that invest conservatively minus firms that invest aggressively), motivated directly by a dividend-discount-model argument that expected return should depend on book-to-market, expected profitability, and expected investment jointly, not book-to-market alone. **Practically**: a portfolio's factor loadings (`b, s, h, r, c`) decompose *why* it earned what it earned — a portfolio manager who "beat the market" with a high loading on SMB and HML wasn't necessarily skilled, they were structurally overweight small-cap value, a well-documented risk premium, not idiosyncratic alpha — this decomposition is exactly what performance-attribution systems compute.

### Why mean-variance optimization is unstable: the mechanism, then the numbers

**The core problem**: expected returns (`μ`) are estimated with far more sampling error, relative to their own magnitude, than covariances (`Σ`) are. The standard error of a sample mean return shrinks as `σ/√T` — for a stock with `20%` annual volatility and `10` years of data, the standard error on the mean estimate is still `20%/√10≈6.3%`, comparable in magnitude to a typical *equity risk premium itself* — you'd need on the order of a century of data to estimate a single stock's expected return to a useful precision, data that doesn't exist for any individual asset over a stationary regime. Covariances, by contrast, are estimated far more precisely from the same sample (using every pair of daily/monthly returns, not just the single overall average), which is *why* risk models are trusted far more than return forecasts in practice.

Optimization then compounds this: `Σ⁻¹` **amplifies** whatever noise is in `μ` in the direction of the covariance matrix's smallest eigenvalues — when two assets are highly correlated, the direction "long one, short the other" has very low *actual* variance (they move together, so a long-short position in them is nearly riskless in-sample) but the return estimates in that same direction are still just as noisy as anywhere else, so the optimizer, chasing any tiny apparent return edge in a direction it (wrongly) believes is nearly risk-free, takes an enormous, leveraged position exploiting noise.

**Worked demonstration.** Two assets, both `σ=15%`, correlation `ρ=0.95` (a very plausible real-world case — two similar large-cap tech stocks, or two country ETFs in the same region), `Rf=2%`:

| Asset B's `μ` (Asset A fixed at 8%) | Tangency weights `(w_A, w_B)` |
|---|---|
| `8.5%` (50bp higher) | `(−28%, +128%)` |
| `9.0%` (100bp higher) | `(−100%, +200%)` |
| `7.5%` (50bp lower) | `(+135%, −35%)` |

A **50 basis point** change in one asset's estimated expected return — well within any realistic estimation error given the `σ/√T` argument above — swings the "optimal" portfolio from a modest tilt to a **massively leveraged long-short position**, and reversing the sign of the same-magnitude difference flips which asset gets shorted. The covariance matrix's **condition number** (ratio of largest to smallest eigenvalue, `39` for this example) directly measures this sensitivity — a well-conditioned (low condition number) covariance matrix produces stable optimal weights under small input perturbations; an ill-conditioned one (common whenever assets are highly correlated, or the number of assets approaches the number of historical observations) amplifies estimation noise into portfolio decisions no rational investor would actually want to hold.

### Risk parity: sidestepping the unstable input entirely

**Equal risk contribution** allocates so that every asset contributes the same fraction of total portfolio risk, not the same fraction of capital. Each asset's **marginal risk contribution** to portfolio volatility `σ_p=√(w'Σw)` is `∂σ_p/∂w_i=(Σw)_i/σ_p`, and its **risk contribution** is `w_i·(Σw)_i/σ_p` (Euler's theorem on homogeneous functions guarantees these sum exactly to `σ_p`). Risk parity solves for weights such that `w_i·(Σw)_i` is equal across all `i` — this uses **only** the covariance matrix, never `μ`, which is precisely why it avoids the instability problem above entirely.

**Worked example**, same three assets. **Naive inverse-volatility weighting** (`w_i∝1/σ_i`, a common simplified approximation) gives `(21.1%, 63.2%, 15.8%)` — but this is only *exactly* equal-risk-contribution when assets are uncorrelated; with the actual correlation structure here, the resulting risk-contribution *fractions* come out to `(34.4%, 25.0%, 40.6%)`, meaningfully unequal because it ignores the diversification/concentration effect correlation introduces. A proper iterative numerical solve (repeatedly rescaling weights to pull each asset's risk contribution toward the average) converges to weights `(19.9%, 67.0%, 13.1%)` with **exactly equal** risk-contribution fractions of `33.3%/33.3%/33.3%`. **The key comparative point**: none of these risk-parity weights moved at all when the earlier mean-variance example perturbed `μ_stocks` by 50-100bp — risk parity is completely insensitive to exactly the input that made mean-variance optimization swing to extreme leveraged positions, at the direct cost of not using any return forecast at all (it has no view on which asset is expected to outperform, by construction).

---

## Build it from scratch

```python
# untested sketch -- structure verified against every worked number above
import numpy as np

def min_variance_weights(Sigma):
    ones = np.ones(Sigma.shape[0])
    Sigma_inv = np.linalg.inv(Sigma)
    return Sigma_inv @ ones / (ones @ Sigma_inv @ ones)

def tangency_weights(mu, Sigma, rf):
    ones = np.ones(Sigma.shape[0])
    Sigma_inv = np.linalg.inv(Sigma)
    raw = Sigma_inv @ (mu - rf)
    return raw / (ones @ raw)

def capm_beta(Sigma, w_market):
    market_var = w_market @ Sigma @ w_market
    return (Sigma @ w_market) / market_var

def risk_contributions(w, Sigma):
    port_vol = np.sqrt(w @ Sigma @ w)
    marginal = Sigma @ w
    return w * marginal / port_vol           # sums exactly to port_vol (Euler's theorem)

def risk_parity_weights(Sigma, n_iter=200):
    sigma = np.sqrt(np.diag(Sigma))
    w = (1 / sigma) / np.sum(1 / sigma)       # naive inverse-vol starting point
    for _ in range(n_iter):
        rc = w * (Sigma @ w)
        w = w * np.sqrt(rc.mean() / rc)       # multiplicative update toward equal RC
        w = w / w.sum()
    return w
```

Full runnable version, including the two-asset instability sweep reproducing the `(-28%,+128%)` / `(-100%,+200%)` table above, and a proper convex-optimization-based risk-parity solver (`scipy.optimize` or `cvxpy`) cross-checked against the iterative version, is the lab exercise in `labs/python/06-portfolio/`.

---

## How it's done in production

`PyPortfolioOpt` and `Riskfolio-Lib` (Python) implement mean-variance optimization with shrinkage estimators, Black-Litterman, and risk-parity solvers out of the box; `statsmodels`/`linearmodels` for Fama-French factor regressions against published factor data (Kenneth French's data library is the standard source for the factor returns themselves); risk models from vendors (Barra/MSCI, Axioma) provide production-grade, professionally-maintained covariance and factor-exposure estimates rather than raw sample covariance matrices, specifically because a raw sample covariance matrix with more assets than historical observations is singular (not invertible at all) and even with enough observations is noisy in exactly the ways that matter for optimization.

| Symptom | Cause | Fix |
|---|---|---|
| Mean-variance optimizer outputs extreme long/short positions (weights far outside 0-100%, or wildly different from last quarter's optimal weights on similar inputs) | Estimation-error maximization — the optimizer is exploiting noise in `μ`, amplified by `Σ⁻¹`, especially where assets are highly correlated | Use shrinkage on the covariance matrix (Ledoit-Wolf) and/or the mean estimates (shrink toward a common prior, or use Black-Litterman to blend market-equilibrium-implied returns with explicit views rather than raw historical means) |
| Optimizer fails outright (covariance matrix not invertible) | More assets than historical observations (`N>T`), making the sample covariance matrix rank-deficient/singular | Reduce the number of assets, use a factor model to estimate `Σ` with fewer parameters (Barra-style structural covariance), or apply shrinkage toward a well-conditioned target (e.g., a diagonal or single-factor matrix) |
| A portfolio manager's "alpha" disappears once returns are regressed against Fama-French factors | Apparent skill was actually a structural factor tilt (overweight small-cap/value/high-profitability names), a well-documented risk premium, not idiosyncratic manager skill | Report performance net of factor exposures (the regression's `alpha`, not raw excess return) as the actual skill measure; size manager allocations based on that, not gross outperformance |
| Risk-parity portfolio's risk contributions drift away from equal over time without rebalancing | Asset volatilities and correlations shift (regime change), and static weights computed once no longer reflect current risk contributions | Rebalance risk-parity weights on a regular schedule using updated covariance estimates, not a set-once allocation |
| CAPM beta estimated from a short historical window swings dramatically quarter to quarter | Beta estimation itself has sampling error, and a short window is disproportionately influenced by a few large return observations (outliers) | Use a longer estimation window, shrinkage toward an industry/peer-group average beta (a standard practitioner adjustment, e.g. "adjusted beta" `=⅔·raw beta+⅓·1`), or a robust regression less sensitive to outliers |

---

## Tradeoffs & when NOT to use it

- **Don't run unconstrained mean-variance optimization on raw historical sample means for a real allocation decision.** The instability demonstrated above isn't a corner case, it's the expected behavior whenever assets are meaningfully correlated (which is most real asset universes) — always apply shrinkage, position constraints, or use Black-Litterman/risk-parity instead of feeding raw sample `μ` directly into an unconstrained optimizer.
- **Don't treat CAPM beta as a stable, precisely-known constant for any individual stock.** Beta estimates from different windows, frequencies (daily vs monthly returns), or index proxies for "the market" can differ meaningfully — use it as a reasonable systematic-risk approximation for cost-of-capital and risk-decomposition purposes, not as a precise input to a high-stakes decision without checking its estimation stability.
- **Don't assume Fama-French factor loadings are stable over an individual company's history.** A company's size/value/profitability characteristics genuinely change over time (a small-cap value stock can become a large-cap growth stock), so a factor regression estimated over one period may not describe the same company's risk exposure in a later period — re-estimate periodically, don't treat factor loadings as fixed company attributes.
- **Don't use risk parity when you genuinely have high-conviction, well-founded views on expected returns.** Risk parity's entire advantage (insensitivity to noisy return estimates) is also its limitation — it has no mechanism to overweight an asset you have real information suggesting will outperform; if you have a defensible return forecast, a properly shrunk/regularized mean-variance approach (or Black-Litterman, which explicitly blends views with equilibrium priors) uses that information, risk parity by construction cannot.
- **Don't confuse "the market portfolio" in CAPM with any single tradeable index.** CAPM's market portfolio is theoretically every risky asset in existence (weighted by market value) including private equity, real estate, human capital — using the S&P 500 or any single index as a proxy is a real, acknowledged approximation, not the theoretical construct itself, and this proxy gap ("Roll's critique," 1977) is a well-known limitation of every practical CAPM test or application.

---

## Interview questions

### Q1 — Derive the two-fund separation theorem from the mean-variance Lagrangian.
**Testing:** whether MPT is understood as a derived result, not a set of formulas to recall.
**Answer:** Minimizing `w'Σw` subject to `w'μ=r` and `w'1=1` gives Lagrangian `L=½w'Σw−λ(w'μ−r)−γ(w'1−1)`; the first-order condition `∂L/∂w=Σw−λμ−γ1=0` gives `w=λΣ⁻¹μ+γΣ⁻¹1`. Every efficient portfolio is therefore a linear combination of two fixed portfolios (`Σ⁻¹μ` and `Σ⁻¹1`, each normalized), with only the mixing weights `λ,γ` (determined by the target `r`) varying across the frontier.
**Follow-up trap:** *"What does this imply practically about how many optimizations you need to run to trace out the whole efficient frontier?"* — just two (compute the two component portfolios once), then any point on the frontier is a simple linear blend of them — a genuinely useful computational shortcut, not just a theoretical curiosity.

### Q2 — Given the worked three-asset example, why does the minimum-variance portfolio allocate 84.8% to bonds despite bonds having the lowest expected return?
**Testing:** whether "minimum variance" is understood as ignoring return entirely by construction, and using correlation for diversification.
**Answer:** The minimum-variance portfolio's optimization (`min w'Σw` s.t. `w'1=1`) never references `μ` at all — it only cares about risk. Bonds have both the lowest individual volatility (`5%`) and negative correlation with stocks (`ρ=−0.2`), making them extremely effective for variance reduction regardless of their own expected return; a portfolio's total variance depends on cross-terms (correlations), not just individual asset risk, so an asset that hedges the others' risk gets a large weight even with a low own-return.
**Follow-up trap:** *"If bonds had zero expected return, would the minimum-variance weights change at all?"* — no, not at all — the minimum-variance portfolio's weights are a pure function of `Σ`, completely independent of `μ`; this is exactly why it's the natural "no-view" starting point on the efficient frontier.

### Q3 — Derive CAPM's expected-return equation from the tangency portfolio's own optimality condition, and explain why this isn't a separate empirical assumption.
**Testing:** the connection between MPT and CAPM as one continuous derivation, not two separate topics.
**Answer:** The tangency portfolio satisfies `Σw_tan∝μ−Rf·1` (its own first-order condition from maximizing the Sharpe ratio). Per-asset, this rearranges to `Cov(Rᵢ,R_tan)∝μᵢ−Rf`. CAPM's equilibrium assumption is that the market-cap-weighted portfolio equals the tangency portfolio (since every investor holds some mix of `Rf` and the same tangency portfolio, per two-fund separation, market clearing forces this equality); substituting `R_tan=Rm` gives `E[Rᵢ]=Rf+βᵢ(E[Rm]−Rf)` directly. It's not a separate assumption bolted onto MPT — it's MPT's own tangency-portfolio math, restated per-asset, under one added equilibrium assumption (market portfolio = tangency portfolio).
**Follow-up trap:** *"What's the one assumption CAPM adds beyond pure Markowitz mean-variance math, and why is it the most commonly criticized part of the theory?"* — the equilibrium assumption that all investors have homogeneous expectations and therefore hold the *same* tangency portfolio, making it equal to the market portfolio; this is criticized (Roll's critique, 1977) because the true market portfolio is unobservable in practice (every risky asset in existence, not just a tradeable index), so any empirical CAPM test is really testing "the model plus a specific market proxy" jointly, not the model alone.

### Q4 — Why are covariances estimated far more precisely than expected returns from the same historical data, and what does this imply about which one should drive portfolio decisions?
**Testing:** the statistical mechanism behind mean-variance instability, the module's central practical point.
**Answer:** A sample mean's standard error shrinks as `σ/√T` — for a `20%`-vol asset and `10` years of data, that's still `≈6.3%`, comparable to the entire equity risk premium being estimated, so `μ` estimates are essentially noise-dominated over any realistic sample length. Covariances use every pairwise observation in the sample (not collapsing to one number per asset the way a mean does) and converge to precise estimates much faster. This implies risk (covariance-based) inputs should be trusted and weighted heavily in portfolio construction, while raw historical return estimates should be treated with heavy skepticism, shrinkage, or replaced with equilibrium-implied/view-based estimates (Black-Litterman) rather than fed directly into an optimizer.
**Follow-up trap:** *"Does this mean expected returns should just be ignored entirely in portfolio construction, as risk parity does?"* — not necessarily; it means raw historical sample means specifically shouldn't be trusted, not that all information about expected returns is worthless — Black-Litterman's whole approach is using *better* return estimates (blending a stable equilibrium prior with explicit, defensible views) rather than abandoning return information altogether, which is a middle ground between naive mean-variance and pure risk parity.

### Q5 — Walk through the worked instability example: two assets, both 15% vol, 0.95 correlation, and explain why a 50bp change in one asset's expected return swings the tangency weights from balanced to (-28%, +128%).
**Testing:** connecting the abstract "estimation-error maximization" concept to the concrete mechanism and numbers.
**Answer:** With `ρ=0.95`, the covariance matrix is nearly singular (condition number `39` in this example) — the "long one, short the other" direction has very low realized variance historically (the two assets move almost identically), so the optimizer perceives that direction as nearly risk-free. Any small difference in estimated `μ` between the two assets, even pure noise, looks to the optimizer like a huge risk-adjusted opportunity (tiny risk, seemingly real return edge), so `Σ⁻¹` amplifies that noise into an extreme leveraged position exploiting the (illusory, noise-driven) return difference.
**Follow-up trap:** *"Would adding a long-only constraint (no shorting) fully fix this problem?"* — it prevents the specific extreme negative weight from being realized, but doesn't fix the underlying instability — a long-only-constrained optimizer facing this same noisy input would still concentrate almost entirely into whichever asset has the (noise-driven) higher estimated return, producing an under-diversified, unstable-quarter-to-quarter portfolio even without ever going short; the constraint masks the symptom, not the cause.

### Q6 — What specifically does risk parity optimize for, and why does it not require an expected-return estimate at all?
**Testing:** whether risk parity is understood as a genuinely different objective, not "mean-variance with a shortcut."
**Answer:** Risk parity solves for weights such that every asset's risk contribution `w_i·(Σw)_i/σ_p` is equal across assets — a condition defined entirely in terms of the covariance matrix `Σ`. Since `μ` never appears anywhere in the objective or constraint, the resulting weights are completely insensitive to return-estimate noise, at the direct cost of having no mechanism to express any view about which asset is expected to do better.
**Follow-up trap:** *"In the worked example, naive inverse-volatility weights gave risk contributions of (34.4%, 25.0%, 40.6%) instead of exactly equal thirds — why doesn't inverse-vol weighting achieve exact risk parity here?"* — inverse-vol weighting (`w_i∝1/σ_i`) achieves exact equal risk contribution only when assets are *uncorrelated*; with real correlation structure (stocks and commodities positively correlated here), the diversification/concentration effects mean naive inverse-vol under- or over-states each asset's true marginal contribution to portfolio risk, requiring the full iterative solve (using the complete covariance matrix, not just individual volatilities) to hit exact equal contribution.

### Q7 — A portfolio manager reports strong outperformance versus the S&P 500. How would you use a Fama-French regression to determine whether this reflects genuine skill?
**Testing:** the practical use of factor models for performance attribution, a common real-world application.
**Answer:** Regress the manager's excess returns against the five factors: `Rᵢ−Rf=α+b(Rm−Rf)+s·SMB+h·HML+r·RMW+c·CMA+ε`. If the manager has significant positive loadings on SMB and/or HML (systematically overweight small-cap and/or value names) and the regression's `α` (intercept, return unexplained by any factor exposure) is statistically indistinguishable from zero, the "outperformance" is fully explained by structural factor tilts — a well-documented risk premium the manager captured by portfolio construction, not by security selection skill. Genuine skill would show up as a significant, positive `α` after controlling for all five factors.
**Follow-up trap:** *"If the manager's alpha is statistically significant at the 5% level over a 3-year track record, is that strong evidence of skill?"* — treat with the same skepticism as any backtested Sharpe ratio (from the ts-validation module) — a 3-year track record is a short sample for statistical significance, and if the manager (or their firm) tested many strategies/managers before highlighting this one, the reported alpha needs a multiple-testing correction (conceptually the same Deflated Sharpe Ratio logic) before being taken as strong evidence rather than a plausibly-lucky outcome.

### Q8 — Why does Roll's critique (1977) matter for any practical use of CAPM, even today?
**Testing:** whether a genuine, still-relevant limitation is known, not just the formula.
**Answer:** CAPM's market portfolio is theoretically every risky asset in existence (all equities, bonds, real estate, private equity, human capital, globally) weighted by market value — entirely unobservable in practice. Every real application substitutes a tradeable proxy (S&P 500, MSCI World), which means any empirical test or beta calculation is jointly testing "CAPM plus this specific proxy," and a different reasonable proxy can produce meaningfully different beta estimates and CAPM-implied required returns for the same asset.
**Follow-up trap:** *"Does this mean CAPM is essentially untestable and therefore practically useless?"* — Roll's critique means CAPM in its strict theoretical form is untestable, but this doesn't make beta-based risk decomposition useless in practice — it means results should be understood as conditional on the specific market proxy chosen, and practitioners should sanity-check sensitivity to reasonable proxy choices (does the conclusion change materially using MSCI World versus S&P 500?) rather than treating a single beta estimate as an exact, unconditional truth.

### Q9 — Why is a raw sample covariance matrix often not directly invertible in a real portfolio-construction problem, and what's the standard fix?
**Testing:** a concrete, common practical failure mode in applying this theory with real data.
**Answer:** A sample covariance matrix estimated from `T` historical observations across `N` assets is rank-deficient (not invertible) whenever `N>T` — you simply don't have enough independent data points to estimate all `N(N+1)/2` unique entries of the covariance matrix. This is common for portfolios spanning hundreds of assets with only a few years of daily or monthly return history. The standard fix is shrinkage (Ledoit-Wolf, 2004: blend the noisy sample covariance matrix with a simpler, well-conditioned structural target, like a single-factor or constant-correlation matrix, weighted to minimize expected estimation error) or explicitly using a factor model (Barra-style) to estimate `Σ` from far fewer parameters than the full matrix.
**Follow-up trap:** *"Even when N<T and the matrix IS technically invertible, why might you still want to apply shrinkage?"* — technical invertibility doesn't mean the estimate is *precise*; even with `N<T`, sample covariance matrices remain noisy, particularly their smallest eigenvalues (systematically underestimated) and largest eigenvalues (systematically overestimated) — a well-known small-sample bias — and shrinkage improves the matrix's out-of-sample behavior even when inversion isn't the immediate blocking issue.

### Q10 — Design question: you're asked to build the portfolio-construction module for an internal robo-advisor allocating across ~15 asset classes, using no explicit human return forecasts (fully systematic). Would you use mean-variance optimization, risk parity, or a hybrid, and why?
**Testing:** staff-level synthesis, applying the whole module's tradeoffs to a realistic system-design constraint.
**Answer:** With no explicit return forecasts available (the stated constraint), pure mean-variance optimization is a poor fit regardless of `N` versus `T` — it would either need to fabricate return estimates from noisy historical means (walking directly into the instability problem demonstrated above) or default to the degenerate case of ignoring `μ` entirely, which is just risk parity by another route. Risk parity (or a close cousin, minimum-variance with position constraints) is the more defensible systematic default specifically because it needs no return forecast and produces stable, explainable weights that don't swing on noise quarter to quarter — a real requirement for a system serving retail clients who need consistent, justifiable allocations. A hybrid worth considering: Black-Litterman with the equilibrium prior alone (no additional investor views layered on top) as a principled way to incorporate *some* market-implied return information (derived from market-cap weights, not noisy historical means) without the instability of raw sample-mean mean-variance.
**Follow-up trap:** *"What would change your recommendation if the robo-advisor later wanted to incorporate a tactical asset allocation view (e.g., 'we believe emerging markets will outperform over the next year')?"* — that's exactly the scenario Black-Litterman is built for: layer the specific view onto the equilibrium prior with an explicit confidence weighting, rather than either ignoring the view (pure risk parity can't use it) or overweighting it via a naive mean-variance re-optimization that would again be vulnerable to the estimation-error-maximization problem if the view's confidence isn't handled carefully.

---

## Red flags that fail you

- Cannot derive the two-fund separation theorem or explain what the Lagrangian's first-order condition actually says.
- States CAPM's formula without knowing it's derivable directly from the tangency portfolio's own optimality condition under an equilibrium assumption.
- Recommends running unconstrained mean-variance optimization on raw historical sample means for a real allocation without mentioning the estimation-error/instability problem.
- Cannot explain why covariances are more reliably estimated than expected returns from the same data.
- Confuses risk parity with equal-capital-weighting (they are different — risk parity equalizes risk contribution, not dollar allocation).
- Treats a manager's excess return as proof of skill without checking whether it's explained by systematic factor exposure (Fama-French loadings).

---

## Cheat card

```
MPT LAGRANGIAN: min 1/2 w'Sigma*w  s.t. w'mu=r, w'1=1
  FOC: Sigma*w = lambda*mu + gamma*1  ->  w = lambda*Sigma^-1*mu + gamma*Sigma^-1*1
  TWO-FUND SEPARATION: every efficient portfolio = blend of 2 fixed portfolios

MIN-VAR:  w = Sigma^-1*1 / (1'Sigma^-1*1)         -- ignores mu ENTIRELY
TANGENCY: w ~ Sigma^-1*(mu - Rf*1), normalize sum=1  -- maximizes Sharpe
  worked (stocks/bonds/commod, Rf=2%): w_tan=(24.0%,74.0%,2.1%), ret=5.0%, vol=4.7%, SR=0.635

CAPM: E[Ri] = Rf + beta_i*(E[Rm]-Rf), beta_i=Cov(Ri,Rm)/Var(Rm)
  IS the tangency portfolio's own FOC, restated per-asset, given market=tangency (equilibrium)
  Roll's critique (1977): true market portfolio is unobservable; any test uses a PROXY

FAMA-FRENCH: Ri-Rf = a + b*(Rm-Rf) + s*SMB + h*HML [+ r*RMW + c*CMA, 5-factor 2015]
  SMB=small-big, HML=value-growth, RMW=profitable-weak, CMA=conservative-aggressive inv
  manager "alpha" = intercept AFTER controlling for factor tilts, not raw outperformance

INSTABILITY (Michaud 1989, "estimation-error maximization"):
  mu standard error ~ sigma/sqrt(T) -- 20% vol, 10yrs -> SE~6.3% (larger than risk premium!)
  Sigma^-1 amplifies mu noise most where assets are highly correlated (ill-conditioned Sigma)
  worked: 2 assets, sigma=15% both, rho=0.95, cond#=39
    mu_B: 8%->8.5% (50bp)  tangency: (-28%,+128%)
    mu_B: 8%->9.0% (100bp) tangency: (-100%,+200%)
  FIXES: Ledoit-Wolf shrinkage (Sigma), Black-Litterman (blend equilibrium+views for mu),
         position constraints, or skip mu entirely -> risk parity

RISK PARITY: equal risk contribution w_i*(Sigma*w)_i/sigma_p equal for all i (Euler's thm)
  uses ONLY Sigma, never mu -> immune to the instability above, but has NO return view
  worked: naive inv-vol (21.1%,63.2%,15.8%) -> RC fractions (34.4%,25.0%,40.6%) NOT equal!
  proper iterative solve -> weights (19.9%,67.0%,13.1%) -> RC fractions exactly (33.3% each)
```

## Sources

- [Portfolio Selection — Markowitz, Journal of Finance (1952)](https://www.jstor.org/stable/2975974) — accessed 2026-08-08
- [Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk — Sharpe, Journal of Finance (1964)](https://www.jstor.org/stable/2977928) — accessed 2026-08-08
- [The Cross-Section of Expected Stock Returns — Fama & French, Journal of Finance (1992)](https://www.jstor.org/stable/2329112) — accessed 2026-08-08
- [A five-factor asset pricing model — Fama & French, Journal of Financial Economics (2015)](https://www.sciencedirect.com/science/article/abs/pii/S0304405X14002323) — accessed 2026-08-08
- [The Markowitz Optimization Enigma: Is 'Optimized' Optimal? — Michaud, Financial Analysts Journal (1989)](https://www.jstor.org/stable/4479177) — accessed 2026-08-08
- [Honey, I Shrunk the Sample Covariance Matrix — Ledoit & Wolf, Journal of Portfolio Management (2004)](https://www.ledoit.net/honey.pdf) — accessed 2026-08-08
- [Global Portfolio Optimization — Black & Litterman, Financial Analysts Journal (1992)](https://www.jstor.org/stable/4479577) — accessed 2026-08-08
- [On the Property of Equally-Weighted Risk Contribution Portfolios — Maillard, Roncalli, Teiletche, Journal of Portfolio Management (2010)](https://www.thierry-roncalli.com/download/erc.pdf) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
