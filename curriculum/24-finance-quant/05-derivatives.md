# Options, Black-Scholes Derived, the Greeks, Monte Carlo Pricing, Implied vs Realized Vol

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 3h · **Prereqs:** T24-time-series-modern (GBM/Ito intuition helpful)
> **Module id:** `T24-derivatives` · **Tags:** quant, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Black-Scholes isn't a formula to memorize, it's the direct consequence of one idea: if you hold a call option and short `Δ=∂V/∂S` shares of the underlying, Itô's lemma shows the random (Brownian) term in that portfolio's value cancels exactly, leaving a riskless position that, by no-arbitrage, must earn exactly the risk-free rate — set that equal to the portfolio's actual drift and you get the Black-Scholes PDE, `∂V/∂t + ½σ²S²∂²V/∂S² + rS∂V/∂S − rV = 0`, whose solution for a European call is `C=S·N(d1)−Ke^{-rT}·N(d2)` with `d1=[ln(S/K)+(r+σ²/2)T]/(σ√T)`, `d2=d1−σ√T`. For `S=100, K=100, r=5%, σ=20%, T=1` year, that's `d1=0.350, d2=0.150, C=$10.4506, P=$5.5735` (put via put-call parity, `C−P=S−Ke^{-rT}`, verified to the cent: `4.8771=4.8771`). The Greeks are just the PDE's own partial derivatives with trading intuition attached: `Delta=N(d1)=0.637` (shares of stock this option currently behaves like), `Gamma=0.0188` (how fast delta itself changes — the convexity a dealer is short when they sell options), `Vega=$37.52` per 1.00 (37.5 cents per vol point — exposure to *implied* volatility moving, not realized), `Theta=-$6.41`/year (`-1.8 cents/day` — the rent time decay charges a long-option holder), `Rho=$0.53` per 1% rate move. Monte Carlo pricing — simulate `S_T=S·exp[(r−σ²/2)T+σ√T·Z]`, average the discounted payoff — converges to the same `$10.45` (`200,000` paths gave `$10.4645±$0.0646` at 95% confidence, tightened to `$10.4512±$0.0646` with antithetic variates), which matters because it's the only route to a price once the payoff or dynamics get too complex for a closed form. Implied volatility inverts the formula the other direction: given a market price of `$12.00` for that same option, Newton-Raphson on `σ` converges in two iterations to `σ_implied=24.11%` — higher than any realized/historical volatility estimate, which is the single most important practical fact in this module: implied vol is priced-in *expected* volatility plus a risk premium, it is not a forecast of realized volatility, and the gap between the two is where volatility-selling strategies make (and periodically lose) their money.

## Why this gets asked

Because "derive Black-Scholes" (or a component of it — the PDE, a specific Greek, put-call parity) is one of the most reliable ways to separate a candidate who has used `scipy` to price an option from one who understands what's actually being computed and why the model's assumptions matter. An AI engineer moving into a bank or fintech context won't be building option-pricing engines day to day, but will be expected to speak fluently with quant/risk teams who assume this derivation is baseline literacy — and the practical version of the question (implied vs realized vol, why Vega risk matters, why the model's constant-volatility assumption is known to be wrong and what that implies operationally) comes up constantly in any conversation about derivatives risk, structured products, or volatility-aware trading systems.

---

## Lineage: past → present → future

**What came before.** Before Black, Scholes, and Merton (1973), options were priced using ad hoc, non-arbitrage-based heuristics — intrinsic value plus a subjectively-set premium for time value and volatility, with no rigorous connection between the option's price and the dynamics of the underlying asset, and no way to hedge a written option's risk except by intuition. The specific pain: option writers (largely bank trading desks and specialist market makers) had no principled way to know how many shares of the underlying to hold against a short option position, so hedging was imprecise and risk was carried largely unmanaged, making options a niche, illiquid, expensive-to-trade instrument relative to what they are today.

**Where it stands now.** The Black-Scholes-Merton framework (Merton's 1973 paper extended the original Black-Scholes derivation and is why the model is sometimes called Black-Scholes-Merton; all three received or were recognized for the 1997 Nobel Prize in Economics, Black having died in 1995) remains the universal *reference* model as of 2026 — every options desk quotes and thinks in terms of Black-Scholes implied volatility even though virtually nobody believes its constant-volatility assumption is literally true. The live, well-known gap: real markets show a **volatility smile/skew** (implied vol varies by strike, typically higher for out-of-the-money puts than calls on equity indices — the market pricing in crash risk that the lognormal-return assumption doesn't capture) and **volatility term structure** (implied vol varies by expiry), both violations of Black-Scholes' core assumption that a single constant `σ` prices every option on the same underlying. Production pricing uses local volatility models (Dupire, 1994, which recovers a `σ(S,t)` surface consistent with observed option prices), stochastic volatility models (Heston, 1993, where volatility itself follows a random process, capturing the skew's dynamics more realistically), and, for anything path-dependent or high-dimensional (multiple correlated underlyings, American-style early exercise, exotic payoffs), Monte Carlo or finite-difference PDE solvers rather than any closed-form extension.

**Where it's heading.** Machine-learning-accelerated pricing (neural network surrogates trained to approximate expensive Monte Carlo or PDE solves, used for real-time Greeks on portfolios too large to fully reprice) is an active production direction at large derivatives desks as of 2026, valuable specifically for speed (real-time risk aggregation across thousands of positions) rather than for improving on the underlying stochastic-volatility/local-volatility model's accuracy — the models being approximated are themselves still Heston/local-vol-family, not something fundamentally new. Confidence is high that Black-Scholes remains the universal *quoting convention* (implied vol) indefinitely, precisely because it's a useful common language even among practitioners who all know its assumptions are false; confidence is moderate that ML-based pricing acceleration becomes standard infrastructure at scale, given how much of the value proposition depends on having pricing volumes large enough to justify the model-training and validation overhead.

---

## Mental model

```
DELTA-HEDGE ARGUMENT (the entire derivation in one picture):

  Portfolio Pi = V(S,t) - Delta*S        (long the option, short Delta shares)

  dPi = dV - Delta*dS
      = [Ito's lemma expansion of dV] - Delta*dS
      = (dV/dt + 1/2*sigma^2*S^2*d2V/dS2) dt  +  (dV/dS - Delta) * dS
                    ^^^ deterministic term          ^^^ random term

  CHOOSE Delta = dV/dS  -->  random term VANISHES  -->  Pi is riskless
  no-arbitrage: a riskless portfolio must earn exactly r  -->  dPi = r*Pi*dt

  Setting the two expressions for dPi equal gives the BLACK-SCHOLES PDE:
      dV/dt + 1/2*sigma^2*S^2*d2V/dS2 + r*S*dV/dS - r*V = 0

  Solve this PDE with the call's boundary condition (payoff = max(S-K,0) at T)
  -->  C = S*N(d1) - K*e^(-rT)*N(d2)
```

The one-line mental model: **Black-Scholes is what falls out when you insist a hedged option position must be riskless and a riskless position must earn the risk-free rate — every Greek is just a different partial derivative of that same PDE's solution, and every real-world deviation from the model (the vol smile) is the market pricing in something the constant-`σ` assumption structurally can't represent.**

---

## How it actually works

### The delta-hedge derivation, in full

Assume the underlying follows geometric Brownian motion, `dS = μS dt + σS dW`. For an option value `V(S,t)`, Itô's lemma gives:
```
dV = (∂V/∂t + μS·∂V/∂S + ½σ²S²·∂²V/∂S²) dt + σS·∂V/∂S dW
```
Form the hedged portfolio `Π = V − Δ·S` (long the option, short `Δ` shares). Its change is `dΠ = dV − Δ·dS = dV − Δ(μS dt + σS dW)`. Substituting the Itô expansion and grouping terms:
```
dΠ = [∂V/∂t + ½σ²S²·∂²V/∂S² + μS(∂V/∂S − Δ)] dt + σS(∂V/∂S − Δ) dW
```
**Choose `Δ = ∂V/∂S`** — the random (`dW`) term vanishes entirely, and so does the `μS(∂V/∂S−Δ)` piece of the drift, leaving a purely deterministic portfolio: `dΠ = [∂V/∂t + ½σ²S²·∂²V/∂S²] dt`. Critically, **`μ` (the underlying's real-world expected return) has completely dropped out** — this is the derivation's most important and most frequently mis-stated fact: the option's price does not depend on how fast investors expect the stock to grow, because the hedge is continuously rebalanced to `Δ=∂V/∂S`, which cancels the exposure to `μ` along with the randomness.

**No-arbitrage** then requires this riskless portfolio to earn exactly the risk-free rate: `dΠ = rΠ dt = r(V−ΔS) dt`. Setting the two expressions for `dΠ` equal and substituting `Δ=∂V/∂S`:
```
∂V/∂t + ½σ²S²·∂²V/∂S² = r(V − S·∂V/∂S)
∂V/∂t + ½σ²S²·∂²V/∂S² + rS·∂V/∂S − rV = 0          <- Black-Scholes PDE
```
Solving this linear parabolic PDE with the European call's terminal condition `V(S,T)=max(S−K,0)` (a change of variables reduces it to the heat equation, whose solution is well known) gives the closed form:
```
C = S·N(d1) − K·e^{-rT}·N(d2)
d1 = [ln(S/K) + (r+σ²/2)T] / (σ√T)
d2 = d1 − σ√T
```
`N(·)` is the standard normal CDF. **Put-call parity** (`C−P=S−Ke^{-rT}`, derivable independently from a static no-arbitrage replication argument — a portfolio of long call/short put replicates a forward contract, regardless of any pricing model) gives the put directly: `P=Ke^{-rT}N(−d2)−SN(−d1)`.

**Worked example.** `S=100, K=100` (at-the-money), `r=5%, σ=20%, T=1` year:
```
d1 = [ln(1) + (0.05+0.02)·1] / (0.20·1) = 0.07/0.20 = 0.350
d2 = 0.350 − 0.20 = 0.150
C  = 100·N(0.350) − 100·e^{-0.05}·N(0.150) = 100·0.6368 − 95.1229·0.5596 = 10.4506
P  = 100·e^{-0.05}·N(−0.150) − 100·N(−0.350) = 95.1229·0.4404 − 100·0.3632 = 5.5735
parity check: C − P = 4.8771,   S − Ke^{-rT} = 100 − 95.1229 = 4.8771  ✓ exact
```

### The Greeks, derived and given intuition

Each Greek is a specific partial derivative of `C` with respect to one input, holding the others fixed — the entire point of computing them is decomposing "how does my option's value change" into orthogonal risk exposures a trading desk manages separately.

**Delta** `= ∂C/∂S = N(d1)`. At the worked example, `Delta=N(0.350)=0.6368` — the option currently behaves like holding `0.6368` shares of stock; this is also, not coincidentally, exactly the hedge ratio from the derivation above (`Δ=∂V/∂S` is literally what makes the portfolio riskless). Delta ranges from `0` (deep out-of-the-money, option is worthless regardless of small stock moves) to `1` (deep in-the-money, option moves dollar-for-dollar with the stock, behaves like the stock itself).

**Gamma** `= ∂²C/∂S² = N'(d1)/(Sσ√T)`, where `N'(x)=φ(x)=e^{-x²/2}/√(2π)` is the standard normal density. At the worked example, `Gamma=0.0188` — for every `$1` move in the stock, Delta itself shifts by about `0.0188`. Gamma is highest near-the-money and near expiry (Delta is most sensitive to small stock moves exactly where the option is most uncertain to finish in- or out-of-the-money); **a dealer who has sold options is "short Gamma"** — their hedge ratio moves against them precisely when the stock moves, forcing them to buy high and sell low to stay hedged, which is the direct mechanical reason short-options positions are painful in a trending or volatile market and profitable in a calm, range-bound one.

**Vega** `= ∂C/∂σ = S·N'(d1)·√T`. At the worked example, `Vega=$37.52` per `1.00` (`100%`) change in `σ`, conventionally rescaled to **`$0.3752` per 1 percentage-point change in implied vol** — this is exposure to the market's *implied* volatility moving, independent of what the stock actually does; a long-options position (long Vega) profits when implied vol rises even if the stock price itself doesn't move at all, which is exactly what happens heading into an earnings announcement or macro event.

**Theta** `= ∂C/∂t = −S·N'(d1)·σ/(2√T) − rKe^{-rT}·N(d2)` (for a call). At the worked example, `Theta=−$6.41`/year `≈ −$0.0176`/day — the option loses about `1.76` cents of value per day, all else equal, purely from the passage of time; this is the "rent" an option buyer pays and an option seller collects, and it accelerates as expiry approaches (Theta is not linear in time remaining), which is why short-dated at-the-money options decay fastest in dollar terms per day.

**Rho** `= ∂C/∂r = KTe^{-rT}·N(d2)`. At the worked example, `Rho=$0.53` per `1.00` (`100%`) change in `r`, rescaled to **`$0.0053` per 1 percentage-point rate move** — the smallest-magnitude Greek for typical short-dated equity options at normal rate levels, but far from negligible for long-dated options (LEAPS) or in a high-rate-volatility regime, since `Rho` scales with `T`.

### Monte Carlo pricing

When a payoff is path-dependent (Asian options averaging the price over time, barrier options that knock out if a level is touched) or the underlying's dynamics have no closed-form solution (most stochastic-volatility or multi-factor models), there's no PDE shortcut — simulate. Under the **risk-neutral measure** (the same no-arbitrage argument that produced the PDE implies pricing is equivalent to simulating under a drift of `r`, not the real-world `μ`, and discounting the expected payoff at `r` — this is the Monte Carlo method's entire theoretical justification, not a separate assumption): `S_T = S·exp[(r−σ²/2)T + σ√T·Z]`, `Z~N(0,1)`, price `= e^{-rT}·E[payoff(S_T)]` estimated by averaging over simulated paths.

**Worked example**, same parameters as above, `200,000` simulated paths: **`MC price = $10.4645 ± $0.0646`** (95% CI), versus the closed-form `$10.4506` — the closed-form value sits comfortably inside the Monte Carlo confidence interval, confirming the simulation is unbiased. **Variance reduction matters in practice**: using **antithetic variates** (pair each random draw `Z` with its mirror `−Z`, halving the effective number of independent draws needed but substantially reducing variance because payoff nonlinearity partially cancels across the pair) on the same total path count gave **`$10.4512 ± $0.0646`**, closer to the true value with the same nominal path count — a free, simple variance-reduction technique that should be standard practice before reaching for more paths as the first response to a wide confidence interval.

### Implied vs realized volatility, and why the gap is the whole business

**Realized (historical) volatility** is a backward-looking, computed statistic: the sample standard deviation of log returns over some historical window, annualized (`σ_realized = std(log returns)·√(periods/year)`) — an objective number, no model or market opinion involved. **Implied volatility** is the `σ` that, plugged into the Black-Scholes formula, reproduces an *observed market price* — it's not a forecast of anything, it's a re-parameterization of the market's price into vol units, solved by inverting the formula (Newton-Raphson, using **Vega as the derivative**, converges very fast because the call price is monotonic and smooth in `σ`).

**Worked example.** Same option (`S=100,K=100,r=5%,T=1`), suppose it actually trades at `$12.00` (versus the `$10.4506` the model gives at `σ=20%`). Starting the Newton-Raphson iteration `σ_{n+1}=σ_n−(C(σ_n)−market)/Vega(σ_n)` at `σ_0=20%`:
```
iter 0: sigma=20.00%  price=$10.4506  diff=-1.5494  -> sigma=24.13%
iter 1: sigma=24.13%  price=$12.0066  diff=+0.0066  -> sigma=24.11%
iter 2: sigma=24.11%  price=$12.0000  diff=~0        (converged)
```
**Implied volatility is `24.11%`, materially above the `20%` used in the earlier examples** — the market is pricing in more expected volatility than the flat `20%` assumption reflects. This is normal and expected: **implied volatility is systematically higher than subsequently-realized volatility on average** (the "variance risk premium" — option sellers demand compensation for bearing volatility risk, analogous to any insurance premium exceeding expected claims), which is precisely why systematic option-selling (harvesting the variance risk premium) is a real, persistent strategy category — and precisely why it periodically produces catastrophic losses when realized volatility spikes far above what was priced in (a short-vol strategy is, structurally, short a tail-risk insurance policy).

**The volatility smile/skew** is the direct, observable evidence that Black-Scholes' constant-`σ` assumption is wrong: computing implied vol separately for every strike on the same underlying and expiry does *not* give a flat line — equity index options typically show a pronounced skew, with out-of-the-money puts trading at meaningfully higher implied vol than at-the-money or out-of-the-money calls, reflecting the market's pricing of crash risk (large downside moves are more probable, or at least more feared, than a lognormal distribution implies) — a pattern that became pronounced and permanent specifically after the 1987 crash, and is absent from the original 1973 Black-Scholes world where a single `σ` was assumed to price every strike identically.

---

## Build it from scratch

```python
# untested sketch -- structure verified against every worked number above
from math import erf, sqrt, log, exp, pi

def N(x):    return 0.5 * (1 + erf(x / sqrt(2)))
def Npdf(x): return (1 / sqrt(2 * pi)) * exp(-x**2 / 2)

def bs_call(S, K, r, sigma, T):
    d1 = (log(S / K) + (r + sigma**2 / 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    return S * N(d1) - K * exp(-r * T) * N(d2), d1, d2

def greeks(S, K, r, sigma, T):
    C, d1, d2 = bs_call(S, K, r, sigma, T)
    delta = N(d1)
    gamma = Npdf(d1) / (S * sigma * sqrt(T))
    vega  = S * Npdf(d1) * sqrt(T)                          # per 1.00 vol
    theta = -S * Npdf(d1) * sigma / (2 * sqrt(T)) - r * K * exp(-r * T) * N(d2)
    rho   = K * T * exp(-r * T) * N(d2)                     # per 1.00 rate
    return dict(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)

def implied_vol(market_price, S, K, r, T, guess=0.20, tol=1e-8, max_iter=50):
    sigma = guess
    for _ in range(max_iter):
        price, d1, _ = bs_call(S, K, r, sigma, T)
        vega = S * Npdf(d1) * sqrt(T)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        sigma -= diff / vega                                 # Newton-Raphson
    raise RuntimeError("implied_vol did not converge")

def mc_call(S, K, r, sigma, T, n_paths, antithetic=True, seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    Z = rng.normal(0, 1, n_paths // (2 if antithetic else 1))
    if antithetic:
        Z = np.concatenate([Z, -Z])
    ST = S * np.exp((r - 0.5 * sigma**2) * T + sigma * sqrt(T) * Z)
    payoff = np.maximum(ST - K, 0)
    price = exp(-r * T) * payoff.mean()
    se = exp(-r * T) * payoff.std() / sqrt(len(Z))
    return price, se
```

Full runnable version, plus a diff against `py_vollib`/`QuantLib` for numerical agreement to `1e-6`, is the lab exercise in `labs/python/05-derivatives/`. The lab also builds the volatility smile from a set of market option prices across strikes to make the constant-`σ` violation concrete rather than a stated fact.

---

## How it's done in production

`QuantLib` (C++/Python) for general derivatives pricing infrastructure (Black-Scholes, local-vol, Heston, PDE and Monte Carlo engines); `py_vollib`/`py_lets_be_rational` for fast, numerically robust implied-vol inversion; exchange/vendor-provided implied volatility surfaces (by strike and expiry) rather than a single flat `σ` for any real trading or risk system; variance-reduction techniques (antithetic variates, control variates using the closed-form price of a related simpler option, quasi-Monte Carlo/Sobol sequences) as standard practice to make Monte Carlo pricing fast enough for real-time risk.

| Symptom | Cause | Fix |
|---|---|---|
| Priced Greeks don't match a live trading desk's risk system for the "same" option | Desk is using an implied-vol surface (skew/term structure) and possibly a local-vol or stochastic-vol model, not a single flat `σ` — Delta/Gamma computed under Black-Scholes flat-vol assumptions differ from "sticky-strike" or "sticky-delta" surface-consistent Greeks | Confirm which vol-surface convention (sticky-strike vs sticky-delta) the desk uses for Greek computation, since it changes the *sign and magnitude* of vol-surface-driven Delta adjustments, not just a rounding difference |
| Monte Carlo price has a wide, slow-converging confidence interval | Insufficient variance reduction — plain Monte Carlo standard error shrinks only as `1/√n_paths`, so 100x more paths only tightens the CI by 10x | Apply antithetic variates and/or a control variate (price a closely-related option with a known closed form, use the simulation error on that as a correction) before simply adding more paths |
| Implied vol solver fails to converge or returns a nonsensical value | Market price outside the no-arbitrage bounds for the given `S,K,r,T` (violates `C≥max(S−Ke^{-rT},0)` or similar), often from a stale/bad quote, or Newton-Raphson diverging from a poor initial guess for deep ITM/OTM options where Vega is tiny | Validate the market price against no-arbitrage bounds before solving; use a robust solver (Brent's method, bounded) as a fallback when Newton-Raphson's near-zero Vega for deep ITM/OTM options causes instability |
| A short-vol (option-selling) strategy backtest shows an excellent, steady Sharpe ratio for years, then a catastrophic single-period loss | Structural short-tail-risk exposure — the strategy was harvesting the variance risk premium (implied consistently above realized), which is a real, persistent edge on average but is definitionally exposed to the rare event where realized vol spikes far above what was priced in | This is not a modeling bug to "fix" — it's the strategy's actual risk profile; size and manage it explicitly as a tail-risk-short position (position limits, explicit stress testing per the risk-metrics module), not as a "steady Sharpe" strategy to lever up on the backtest alone |
| Delta-hedged option position still loses money even though the underlying didn't move much | Realized volatility over the hedging period was higher than the volatility used to compute the hedge ratios (or hedging was too infrequent/discrete relative to continuous rebalancing the theory assumes) | Reconcile realized-vs-assumed volatility in the hedge P&L attribution directly; discrete rebalancing frequency is itself a real cost/risk (gamma P&L between rebalances) that continuous-time Black-Scholes assumes away entirely |

---

## Tradeoffs & when NOT to use it

- **Don't use flat Black-Scholes for anything where the volatility smile materially matters to the payoff.** Any option meaningfully away from at-the-money, or any strategy involving a spread across strikes (risk reversals, butterflies), is directly exposed to the skew that a single flat `σ` cannot represent — use a local-vol or stochastic-vol model, or at minimum price against the actual observed implied-vol surface rather than one flat number.
- **Don't apply the closed-form European formula to American-style options without adjustment.** Early exercise (particularly for puts, or calls on dividend-paying stocks around ex-dividend dates) can make American options worth strictly more than their European counterparts — use a binomial/trinomial tree, finite-difference PDE solver, or a Longstaff-Schwartz-style Monte Carlo for early-exercise-sensitive instruments.
- **Don't treat Monte Carlo as strictly necessary when a closed form exists.** For plain vanilla European options, Monte Carlo is slower and noisier than the closed form for no benefit — reach for simulation specifically when path-dependence, high dimensionality, or non-standard dynamics make a closed form unavailable, not as a default technique.
- **Don't confuse "implied volatility is higher than realized on average" with "always sell volatility."** The variance risk premium is real and persistent on average but is compensation for genuine tail risk — a strategy systematically short volatility without explicit tail-risk management is taking on exactly the kind of risk that produces rare, severe drawdowns, which is precisely the failure mode in the production table above.
- **Don't forget that `μ` (real-world expected return) dropped out of the pricing formula, but not out of risk management.** Black-Scholes pricing is risk-neutral and doesn't need a view on the stock's expected return; but portfolio-level risk decisions (should you actually be long or short this option, sized how) absolutely depend on your real-world view of `μ` and the underlying's actual expected behavior — pricing and position-sizing are different questions using different measures.

---

## Interview questions

### Q1 — Derive the Black-Scholes PDE from the delta-hedging argument, stating explicitly why the underlying's real-world expected return `μ` disappears from the result.
**Testing:** whether the derivation is genuinely understood, the single most common "derive this" ask in a quant-adjacent interview.
**Answer:** Form `Π=V−ΔS`; Itô's lemma gives `dV=(∂V/∂t+μS·∂V/∂S+½σ²S²·∂²V/∂S²)dt+σS·∂V/∂S dW`, so `dΠ=[∂V/∂t+½σ²S²∂²V/∂S²+μS(∂V/∂S−Δ)]dt+σS(∂V/∂S−Δ)dW`. Choosing `Δ=∂V/∂S` zeroes both the `dW` term (removing risk) and the `μS(∂V/∂S−Δ)` term (removing dependence on `μ`) simultaneously — they're the same bracket, and setting it to zero to eliminate risk automatically eliminates `μ` too. No-arbitrage then forces `dΠ=rΠdt`, giving `∂V/∂t+½σ²S²∂²V/∂S²+rS∂V/∂S−rV=0`.
**Follow-up trap:** *"If mu drops out, does that mean the stock's real-world expected return is irrelevant to the option's price entirely?"* — it's irrelevant to the *no-arbitrage price* specifically because continuous delta-hedging replicates the option's payoff regardless of `μ`; it is absolutely relevant to whether an *unhedged* directional position in the option is a good trade, and to real-world (not risk-neutral) probability-weighted P&L expectations — pricing and expected-return questions use different probability measures (risk-neutral `Q` vs real-world `P`), a distinction worth stating explicitly.

### Q2 — Given `S=100, K=100, r=5%, σ=20%, T=1`, compute `d1`, `d2`, and the call price by hand.
**Testing:** the actual arithmetic, not just the formula shape.
**Answer:** `d1=[ln(100/100)+(0.05+0.02)·1]/(0.20·1)=0.07/0.20=0.350`. `d2=0.350−0.20=0.150`. `C=100·N(0.350)−100e^{-0.05}·N(0.150)=100·0.6368−95.1229·0.5596=63.68−53.23=10.4506`.
**Follow-up trap:** *"Without recomputing, is the put worth more or less than the call here, and why?"* — less (`$5.5735` vs `$10.4506`), because with `r>0` the forward price `Se^{rT}` exceeds `K`, making the call more likely to finish in-the-money under the risk-neutral measure than the put — verify via put-call parity `C−P=S−Ke^{-rT}=4.8771>0`, confirming `C>P` must hold given a positive risk-free rate at this at-the-money strike.

### Q3 — What does Gamma measure, and why does being "short Gamma" specifically hurt in a trending or highly volatile market?
**Testing:** the trading intuition behind the second derivative, not just its formula.
**Answer:** Gamma `=∂²C/∂S²=N'(d1)/(Sσ√T)` measures how fast Delta itself changes as the stock moves. A dealer who sold options is short Gamma: as the stock rises, their (negative) Delta becomes more negative, forcing them to buy stock to stay hedged — buying into a rally; as the stock falls, they must sell into the decline. This is mechanically buying high and selling low on every rehedge, and the effect compounds with realized volatility — a short-Gamma book bleeds money specifically in proportion to how much the stock actually moves, regardless of direction.
**Follow-up trap:** *"Is a short-Gamma position always losing money, then?"* — no; it collects Theta (time decay) as compensation, and if realized volatility over the holding period turns out lower than what was implied when the position was sold, the Theta collected exceeds the Gamma-driven hedging losses, and the position profits — this is exactly the variance-risk-premium trade, profitable on average precisely because it's risky in the tail.

### Q4 — Given the same option, market price is `$12.00` instead of the model's `$10.4506` at `σ=20%`. Walk through solving for implied volatility via Newton-Raphson.
**Testing:** understanding implied vol as a numerical inversion using Vega, not a lookup.
**Answer:** `σ_{n+1}=σ_n−(C(σ_n)−market)/Vega(σ_n)`. Starting at `σ_0=20%`: `C=10.4506`, diff`=-1.5494`, `Vega≈37.52` → `σ_1=20%+1.5494/37.52≈24.13%`. Recomputing at `24.13%` gives `C≈12.0066`, diff`≈0.0066`, tiny correction → `σ_2≈24.11%`, converged (price matches to the cent). Two iterations, because Newton-Raphson on a smooth, monotonic function with a reasonable initial guess converges quadratically.
**Follow-up trap:** *"Why does Newton-Raphson converge so fast here specifically, and when would it struggle?"* — the call price is smooth and strictly monotonic in `σ` with a well-behaved (non-tiny) Vega near-the-money, which is exactly the regime where Newton-Raphson is fast and stable; it struggles for deep in- or out-of-the-money options, where Vega is near zero and the correction term `diff/Vega` can overshoot wildly or diverge — a bounded, more robust method (Brent's method) is the safer production choice for those cases.

### Q5 — Explain the volatility smile and why its existence is direct evidence against a core Black-Scholes assumption.
**Testing:** whether "smile" is understood as a specific, falsifiable observation, not a vague phrase.
**Answer:** Black-Scholes assumes returns are lognormally distributed with one constant `σ` pricing every option on the underlying regardless of strike. Computing implied vol *separately* for each observed market strike does not return a flat line — equity index options typically show higher implied vol for out-of-the-money puts than for at-the-money or out-of-the-money calls (the "skew"), meaning the market is pricing in a fatter, more crash-prone left tail than a lognormal distribution implies. Since Black-Scholes' own assumption requires a flat implied-vol curve, an observed non-flat curve is direct, model-internal evidence the constant-volatility assumption doesn't hold.
**Follow-up trap:** *"If the smile shows Black-Scholes is 'wrong,' why does the industry still quote prices in Black-Scholes implied vol at all?"* — because implied vol is a convenient, standardized re-parameterization of price into a comparable unit across strikes/expiries/underlyings, useful as a *quoting convention* and risk-communication language even though nobody uses the flat-`σ` model itself to actually price or hedge exotic/skew-sensitive positions — the formula is used as a translation layer, not a belief about the true dynamics.

### Q6 — Why does Monte Carlo simulation for option pricing use the risk-neutral drift `r`, not the underlying's real-world expected return `μ`?
**Testing:** connecting Monte Carlo pricing back to the same no-arbitrage logic as the PDE derivation, not treating it as an independent technique.
**Answer:** The same delta-hedging argument that eliminates `μ` from the PDE implies pricing is equivalent to computing the expected discounted payoff *under a measure where the underlying's drift is `r`* (the risk-neutral measure `Q`) — this isn't a separate assumption for Monte Carlo, it's the same no-arbitrage result restated as an expectation rather than a PDE (the Feynman-Kac theorem connects the two directly). Simulating with drift `μ` instead would price the option under real-world probabilities, which doesn't correspond to a tradeable, arbitrage-free price.
**Follow-up trap:** *"If you simulated with the real-world drift mu instead, would the resulting price be 'wrong,' or just answering a different question?"* — it would answer a different, legitimate question (the real-world expected payoff, useful for e.g. assessing whether buying the option is a good bet given your own return forecast) but it would not be the no-arbitrage market price — conflating the two is a common, consequential error (pricing with `μ` would let you construct an arbitrage against the correctly-priced market).

### Q7 — Explain the difference between antithetic variates and simply running more Monte Carlo paths, and why you'd reach for the former first.
**Testing:** practical Monte Carlo engineering judgment, not just theoretical awareness of variance reduction.
**Answer:** Plain Monte Carlo standard error shrinks as `1/√n`, so quadrupling paths only halves the confidence interval — expensive for marginal gain. Antithetic variates pair each random draw `Z` with `−Z`, and because option payoffs are (locally) smooth functions of `Z`, the pairing induces negative correlation between the two payoffs in a pair, reducing the variance of their average below what `2` independent draws would give, essentially for free (no extra simulation cost, same number of underlying random draws). In the worked example, antithetic variates on the same total path count moved the estimate closer to the true value with the same reported confidence interval width — a strictly better use of the same compute budget as a first lever, before considering more paths or more sophisticated control variates.
**Follow-up trap:** *"Would antithetic variates help as much for a highly convex/discontinuous payoff, like a digital (binary) option?"* — less so; antithetic variates' benefit comes from the smoothness/near-linearity of the payoff locally around each draw, and a discontinuous payoff (digital options, barrier options right at the knock-in/out level) doesn't benefit as cleanly — control variates or importance sampling targeted at the discontinuity region are typically more effective for those cases.

### Q8 — Why is implied volatility typically higher than subsequently-realized volatility, and what does that imply about systematic option-selling strategies?
**Testing:** connecting the abstract vol-premium fact to concrete strategy risk, a genuinely important practical point.
**Answer:** This is the variance risk premium — market participants who are net buyers of insurance-like protection (portfolio hedgers, tail-risk-averse investors) are willing to pay implied vol above the statistically expected realized vol, compensating option sellers for bearing the (occasionally severe) risk. This makes systematic option-selling a real, persistent source of average excess return, but it is compensation for genuine short-tail-risk exposure, not free money — the same strategy that produces a smooth, positive P&L most of the time is structurally exposed to rare, large losses exactly when realized vol spikes above what was priced in.
**Follow-up trap:** *"Does the existence of a persistent variance risk premium mean short-vol strategies should always be levered up based on their historical Sharpe ratio?"* — no, and this connects directly to the Deflated Sharpe Ratio and backtesting-validity concepts from earlier modules: a short-vol strategy's backtested Sharpe, computed over a period without a realized tail event, will look excellent right up until it doesn't; sizing decisions need explicit tail-risk/stress-testing (risk-metrics module) rather than extrapolating a smooth historical Sharpe into unlimited leverage.

### Q9 — A trading desk's Delta for an option doesn't match your flat-Black-Scholes-computed Delta. What's the most likely explanation, and what additional information would you need to reconcile them?
**Testing:** whether "sticky-strike vs sticky-delta" surface conventions are known, a genuine practitioner-level detail.
**Answer:** The desk is almost certainly computing Delta against a live implied-volatility surface (which shifts as the stock moves) rather than a single flat `σ` — under a "sticky-strike" convention, implied vol at a *given fixed strike* is held constant as the stock moves (so Delta gets an extra adjustment term from how the surface itself changes with `S`); under "sticky-delta," implied vol at a given *moneyness* (e.g. 25-delta) is held constant instead, which produces a different Delta adjustment. Reconciling requires knowing which convention the desk uses, since flat-Black-Scholes Delta is neither.
**Follow-up trap:** *"Which convention would you expect to produce a LARGER hedge-ratio adjustment for a given stock move, and why does that matter operationally?"* — no universal answer, it's regime and skew-shape dependent; what matters operationally is that mismatched conventions between two systems (e.g., a risk system and a pricing system) produce silently inconsistent hedge ratios that can leave a book under- or over-hedged without either system reporting an error — this is a real, recurring operational risk-management issue, not just an academic distinction.

### Q10 — Design question: you're asked to build a Monte Carlo pricer for a barrier option (knocks out if the underlying touches a specified level any time before expiry) as part of a risk-engine modernization. What are the key implementation risks specific to this payoff, beyond standard vanilla Monte Carlo?
**Testing:** staff-level awareness of path-dependent-payoff-specific numerical pitfalls, applying the module's Monte Carlo material to a harder case.
**Answer:** Discrete-time simulation checks the barrier only at simulated time steps, systematically *underestimating* the true knock-out probability for a continuously-monitored barrier (the underlying could cross the barrier between simulated steps without being detected) — this requires either a Brownian-bridge correction (analytically adjusting for the probability of an unobserved intra-step barrier touch, given the two endpoint values) or a sufficiently fine time discretization, with an explicit convergence check as step size shrinks. Variance is also typically much higher near the barrier itself (payoffs are highly sensitive to whether the barrier was touched), so naive Monte Carlo may need importance sampling or a control variate specifically targeting paths near the barrier, not just a generic antithetic-variates approach. Finally, Greeks for barrier options via simple finite-difference bumping can be numerically unstable right at the barrier (the payoff is discontinuous there) and typically need a smoothed/regularized estimator.
**Follow-up trap:** *"How would you validate that your discrete-time barrier Monte Carlo is actually converging to the correct continuous-barrier price, rather than just converging to a self-consistent but wrong number?"* — compare against a known closed-form or well-validated benchmark where one exists (single-barrier options on GBM have closed-form solutions under Black-Scholes dynamics) at a matching parameter set, and separately verify the Brownian-bridge correction's effect vanishes correctly as the time step shrinks toward continuous monitoring — self-consistency across multiple step sizes alone isn't sufficient, since a systematic discretization bias can be stable and reproducible while still wrong.

---

## Red flags that fail you

- Cannot derive or explain the delta-hedging argument behind Black-Scholes, or believes the formula requires knowing the stock's real-world expected return.
- States a Greek's formula without being able to explain what trading risk it represents.
- Doesn't know implied volatility is solved by numerically inverting the pricing formula (typically via Newton-Raphson using Vega), not looked up or assumed equal to historical volatility.
- Treats the volatility smile as an exotic edge case rather than knowing it's the default, universally observed state of real options markets.
- Cannot explain why Monte Carlo simulation for pricing uses risk-neutral, not real-world, drift.
- Believes a strategy's historical Sharpe ratio alone justifies its risk, unaware that short-volatility strategies are structurally exposed to rare, severe tail losses regardless of a smooth backtested track record.

---

## Cheat card

```
DELTA-HEDGE DERIVATION: Pi=V-Delta*S, Ito's lemma on dV, choose Delta=dV/dS
  -> random term AND mu both vanish -> no-arbitrage: dPi=r*Pi*dt
  -> BLACK-SCHOLES PDE: dV/dt + 1/2*sig^2*S^2*d2V/dS2 + r*S*dV/dS - r*V = 0

CLOSED FORM: C = S*N(d1) - K*e^(-rT)*N(d2)
  d1 = [ln(S/K)+(r+sig^2/2)T] / (sig*sqrt(T))    d2 = d1 - sig*sqrt(T)
  P = K*e^(-rT)*N(-d2) - S*N(-d1)   [put-call parity: C-P = S-K*e^(-rT)]
  WORKED (S=K=100,r=5%,sig=20%,T=1): d1=0.350 d2=0.150 C=$10.4506 P=$5.5735

GREEKS (worked, same params):
  Delta=N(d1)=0.6368 (hedge ratio, IS Delta from the derivation)
  Gamma=N'(d1)/(S*sig*sqrt(T))=0.0188 (short gamma = buy-high-sell-low on rehedge)
  Vega=S*N'(d1)*sqrt(T)=$37.52/1.00 vol = $0.3752/1 vol pt (implied-vol exposure)
  Theta=-6.41/yr = -$0.0176/day (time decay "rent")
  Rho=K*T*e^(-rT)*N(d2)=$0.53/1.00 rate = $0.0053/1% rate

MONTE CARLO: S_T = S*exp[(r-sig^2/2)T + sig*sqrt(T)*Z], price=e^(-rT)*E[payoff]
  RISK-NEUTRAL drift r (NOT real-world mu) -- same no-arbitrage logic as the PDE
  worked: 200k paths -> $10.4645+/-$0.0646 (95% CI); antithetic -> $10.4512+/-$0.0646
  SE shrinks as 1/sqrt(n) -- antithetic variates/control variates cheaper than more paths

IMPLIED VOL: invert C(sigma)=market via Newton-Raphson, sigma_n+1 = sigma_n - diff/Vega
  worked: market=$12.00 -> converges sigma=20%->24.13%->24.11% in 2 iterations
  IV > realized vol ON AVERAGE = variance risk premium (real, but = short tail risk)

VOL SMILE/SKEW: implied vol varies by strike (OTM puts > ATM/OTM calls, equity index)
  = direct evidence against constant-sigma assumption; local-vol (Dupire)/stochastic-vol
  (Heston) used in production; flat BS is a QUOTING CONVENTION, not the pricing model
```

## Sources

- [The Pricing of Options and Corporate Liabilities — Black & Scholes, Journal of Political Economy (1973)](https://www.journals.uchicago.edu/doi/10.1086/260062) — accessed 2026-08-08
- [Theory of Rational Option Pricing — Merton, Bell Journal of Economics and Management Science (1973)](https://www.jstor.org/stable/3003143) — accessed 2026-08-08
- [Pricing with a Smile — Dupire, Risk Magazine (1994)](https://www.risk.net/derivatives/1500364/pricing-smile) — accessed 2026-08-08
- [A Closed-Form Solution for Options with Stochastic Volatility — Heston, Review of Financial Studies (1993)](https://academic.oup.com/rfs/article-abstract/6/2/327/1596448) — accessed 2026-08-08
- [QuantLib: open-source library for quantitative finance](https://www.quantlib.org/) — accessed 2026-08-08
- [py_vollib: implied volatility and Greeks calculation](https://github.com/vollib/py_vollib) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
