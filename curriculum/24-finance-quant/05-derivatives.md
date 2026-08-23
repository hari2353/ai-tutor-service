# Options, Black-Scholes Derived, the Greeks, Monte Carlo Pricing

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 3.0h · **Prereqs:** T24-time-series-core · **Updated:** 2026-08-23
> **Module id:** `T24-derivatives` · **Tags:** quant, critical

## The 30-second version

An option is a convexity contract, and Black-Scholes-Merton (1973) prices it by *replication*: continuously trading the underlying in exactly the right (delta) amounts manufactures the payoff, so absence of arbitrage forces the option's value to equal the hedge's cost — no expected-return forecast needed, only volatility. The closed form falls out of a risk-neutral expectation over geometric Brownian motion; the Greeks are the local sensitivities of that machinery: delta (∂V/∂S), gamma (convexity, ∂²V/∂S² — the reason hedged books earn or bleed via the identity ≈½·Γ·S²·(σ²_realized − σ²_implied)·dt), vega (vol exposure), theta (time decay — gamma's financing bill), rho. When no closed form exists (path-dependents, high-dimensional baskets), Monte Carlo simulates the risk-neutral process and averages discounted payoffs, tamed by variance-reduction tricks — antithetic draws and control variates (using the discounted terminal asset whose expectation you know exactly: E[e^{−rT}S_T] = S₀) cutting standard errors several-fold. The constant-σ assumption died empirically after October 1987: index options trade at a persistent skew/smile, so practitioners invert market prices into *implied* vols — "the wrong number to plug into the wrong formula" (Rebonato) — and manage entire surfaces with stochastic-vol (Heston 1993), local-vol (Dupire 1994), and jump models. Pricing, hedging, and quoting this chain fluently is the entry ticket to every derivatives desk interview.

## Why this gets asked

Because derivatives questions are compact physics: one prompt tests whether you can derive (risk-neutral pricing from hedging arguments), compute (Greeks signs, parity arbitrage), simulate (MC mechanics and its error budget), AND critique (where constant-vol dies). A Citi VP markets screen typically walks: put-call parity arb drill → Greeks table reasoning ("which position is long gamma but short theta?") → "your delta-hedged long call made money this week — what does that tell you about realized versus implied vol?" → smile phenomenology ("why do equity puts trade rich relative to calls post-87?"). D.E. Shaw-style screens push further into model risk: when does a Monte Carlo's standard error lie to you (discretization bias vs statistical noise; Greeks via bumping near kinks), how do you interpolate a surface consistently (arbitrage-free SVI slices), and what breaks at negative rates or deep tail strikes where no quotes exist (mark-to-model governance — T24-mrm territory). The failure mode being screened OUT is the candidate who memorized formulas without the replication logic underneath them: they cannot answer WHY delta changes, so they cannot reason about any regime the textbook didn't enumerate.

## Lineage

**What came before.** Bachelier (1900) priced options under arithmetic Brownian motion five years before Einstein's Brownian-motion paper — zero drift, possible-negative prices, no compounding: astonishingly close and structurally incomplete. Samuelson (1965) added lognormality and drift, but kept an exogenous discount rate, leaving the price partly arbitrary. The missing ingredient was equilibrium-through-replication: Sprenkle, Boness, and others had pieces; nobody had eliminated the stock's expected return.

**Where it stands now.** Black and Scholes (1973, Journal of Political Economy) and Merton (1973, Bell Journal) cracked it — continuous delta-hedging manufactures a riskless portfolio, forcing risk-neutral valuation; Scholes and Merton took the 1997 Nobel. Cox-Ross-Rubinstein (1979) recast it as a lattice — computable, extendable to Americans, and pedagogically immortal. The empirical world then rebelled: pre-1987 smiles were mild; after the crash, index put skew became permanent (OTM puts bid rich — crash insurance demand plus leverage effect), spawning the model zoo: Merton jump-diffusion (1976), Heston stochastic volatility (1993, mean-reverting variance with vol-of-vol κ/θ/σ/ρ parameterization), Dupire local volatility (1994, deterministic σ(S,t) fitting the whole surface exactly but with dynamics that hedge poorly), SVI/SABR parametrizations for arbitrage-free interpolation in production. Variance swaps and the VIX (CBOE; modern SPX-based methodology 2003) turned the smile itself into tradable instruments; FRTB-era capital rules and XVA desks pushed Monte Carlo onto GPU grids computing full-Greek ladders across hundreds of thousands of scenarios overnight.

**Where it's heading.** Three currents. First, machine-learned surfaces: neural-SVI interpolators and deep-hedging research (RL agents learning hedge strategies directly on data, benchmarked against delta-gamma baselines) — promising where transaction costs and discrete rebalancing dominate, controversial where explainability is regulated (every desk still needs the analytic Greek as challenger). Second, 24-hour options venues and crypto derivatives (Deribit-style books with fat-tailed underlying and 24/7 settlement) stressing conventions built for RTH sessions. Third, regulatory analytics as a pricing consumer: SA-CCR/FRTB sensitivity-based method requires bucketed vegas and curvatures computed daily across the book — the Greeks stopped being desk folklore and became reportable capital inputs, raising the governance bar on their computation methods (bump sizes, pathwise vs finite difference, model versioning).

---


## Mental model

```
REPLICATION IS THE ENGINE. Price = cost of the manufacturing process.

  DELTA-HEDGE LOOP (continuous limit):
    hold -delta shares against +1 call, rebalance as S moves
    portfolio earns gamma convexity: re-buy low / sell high on every wiggle
    pays for it via theta (time decay of the option's time value)
    => hedged P&L per dt ~ 0.5 * Gamma * S^2 * (sigma_real^2 - sigma_impl^2) dt
       long vol = betting realized > implied ; short vol = the reverse

  GREEKS CHEAT SHEET (long call):
    delta  dV/dS   in (0,1), ->1 deep ITM          hedge ratio
    gamma  d2V/dS2 peak ATM near expiry            convexity (good)
    vega   dV/dvol ~ S*phi(d1)*sqrt(T)             ATM, grows w/ sqrt(T)
    theta -dV/dt   most negative ATM short-dated   gamma's rent bill
    rho    dV/dr   K*T*e^{-rT}*N(d2)               rates matter for long T

  RISK-NEUTRAL WORLD:
    price = E^Q[ e^{-rT} * payoff ]   under drift r (NOT real-world mu)
    Q exists BECAUSE hedging kills risk; no risk premium survives in V

  MC RECIPE:
    simulate S_T under GBM exactly: S_T = S*exp((r-sig^2/2)T + sig*sqrt(T) Z)
    average discounted payoffs; shrink SE with antithetics + control variates
```

Deepest framing: an option is a *manufacturing contract* whose raw material is rebalancing trades. Everything — price, Greeks, model disputes — is accounting for what that factory costs to run in different worlds.

---

## How it actually works

### Deriving Black-Scholes without drowning

Set up a portfolio: long one option, short Δ shares. Over dt its value changes by dV − ΔdS. Choose Δ = ∂V/∂S and the random part (∝ dW) cancels EXACTLY — the remaining deterministic drift must equal the risk-free return or arbitrage exists: dV − ΔdS = (∂V/∂t + ½σ²S²∂²V/∂S²)dt = r(V − ΔS)dt. That's the Black-Scholes PDE; solving it for a European call payoff with lognormal transition density gives C = S₀N(d₁) − Ke^{−rT}N(d₂) with d₁ = [ln(S/K) + (r+σ²/2)T]/(σ√T), d₂ = d₁ − σ√T. Two readings worth having ready: (1) probabilistic — C equals the risk-neutral expectation E[e^{−rT}(S_T−K)⁺], where N(d₂) is exercise probability and N(d₁) the asset-or-nothing component; (2) economic — μ never appears because replication makes expected return irrelevant; volatility is the only state variable that matters. Put-call parity follows immediately from forward logic: C − P = S₀ − Ke^{−rT} (with dividends: subtract PV(divs)) — the zero-free-lunch backbone exploited synthetically every day.

### The Greeks as a coherent story

Delta hedges first-order risk; gamma measures how fast the hedge goes stale (convexity). Vega and theta are two faces of one tradeoff: long options collect convexity (gamma) and pay rent (theta); the identity above says a delta-hedged position's drift equals ½ΓS²(σ²_real − σ²_imp)dt — so implied vol is literally the breakeven realized vol priced into the hedge. Second-order/cross Greeks matter at book level: vanna (∂vega/∂S or ∂delta/∂vol) and volga/vomma (∂vega/∂vol) drive wing behavior and are why vol desks bucket vegas by strike/tenor rather than netting one number. Sign table fluency (long call/put: long gamma, long vega, short theta; short side mirrored) resolves half of desk trivia instantly.

### Monte Carlo pricing and its error budget

Simulate risk-neutral GBM exactly over [0,T] via S_T = S₀exp((r−σ²/2)T + σ√T·Z) — exact solution means no discretization bias for European claims; path-dependents use fine steps (Euler/Milstein, introducing weak-discretization error). Estimator = mean of discounted payoffs; standard error shrinks as SE/√n — four-digit accuracy costs ~10⁸ paths naively, hence variance reduction: (1) *antithetic variates* — pair each Z with −Z, halving effective noise for symmetric-ish payoffs; (2) *control variates* — subtract beta×(X − E[X]) for any X with known expectation; canonical choice X = e^{−rT}S_T with E[X] = S₀, and optimal beta* = Cov(Y,X)/Var(X) (our lab cuts SE 2.6x and halves absolute error); (3) importance sampling for far-tail payoffs; (4) stratified/quasi-random (Sobol) sequences approaching O(n^{-1}) convergence. Greeks from MC three ways: bump-and-revalue (finite differences — biased near kinks, noisy for second order), pathwise derivatives (exact where payoff is smooth — works for delta/vega, fails at indicator payoffs without smoothing), likelihood-ratio method (differentiate the density — handles kinks, high variance). Digital/barrier options are where method choice visibly changes answers — interviewers love this trap.

### Beyond constant sigma: the smile and its models

Implied vol extracted per (strike, tenor) draws a surface: equity indexes show persistent negative skew (OTM puts rich — crash insurance + leverage effect; typical index skew slopes marked ~ −5 to −15 vol points per 10% moneyness), FX shows smiles around risk-reversal conventions (25Δ RR/BF quoting), single names steeper and term-structure lumpier than indexes. Models trade off fit versus dynamics: local vol (Dupire) fits today's surface exactly but implies mean-reverting-ish forward dynamics that mis-hedge forward-vol products; Heston captures clustering/skew with five parameters but rarely fits extreme wings; jump diffusion prices crashes but leaves calibration ambiguous between jump intensity and diffusive vol. Production compromise: SVI-parameterized slices constrained arbitrage-free, calibrated daily, with stochastic-vol overlays for exotics — plus governance that knows all of them are interpolating devices on sparse quotes (Rebonato's line remains the honest definition of implied vol).

---

## Build it from scratch

Runnable std-lib+numpy lab: closed-form BS with analytic Greeks, Monte Carlo cross-checked via control variate, finite-difference Greek verification:

```python
import numpy as np
from math import log, sqrt, exp, erf, pi

PHI = lambda x: 0.5*(1.0 + erf(x/sqrt(2.0)))          # std normal CDF
pdf = lambda x: exp(-0.5*x*x)/sqrt(2.0*pi)

# ---------------- Black-Scholes closed form + Greeks ----------------
def bs_call_greeks(S, K, T, r, sigma):
    d1 = (log(S/K) + (r + 0.5*sigma*sigma)*T) / (sigma*sqrt(T))
    d2 = d1 - sigma*sqrt(T)
    call = S*PHI(d1) - K*exp(-r*T)*PHI(d2)
    return dict(price=call, d1=d1, d2=d2,
                delta=PHI(d1),
                gamma=pdf(d1)/(S*sigma*sqrt(T)),
                vega=S*pdf(d1)*sqrt(T),                 # per 1.00 vol move
                theta=(-S*pdf(d1)*sigma/(2*sqrt(T))
                       - r*K*exp(-r*T)*PHI(d2)),        # per year
                rho=K*T*exp(-r*T)*PHI(d2))

S, K, T, r, sig = 100.0, 100.0, 1.0, 0.05, 0.20
g = bs_call_greeks(S, K, T, r, sig)
print("Black-Scholes European call, S=K=100 T=1y r=5% vol=20%")
for k in ["price", "delta", "gamma", "vega", "theta", "rho"]:
    print(f"  {k:6s}: {g[k]:9.4f}")
print(f"  sanity: put via parity = {g['price'] - S + K*exp(-r*T):.4f}")

# ---------------- Monte Carlo with control variate ----------------
n_paths, n_batches = 50_000, 40
rng = np.random.default_rng(42)

def mc_batch(n):
    z = rng.standard_normal(n)
    ST = S*np.exp((r - 0.5*sig*sig)*T + sig*sqrt(T)*z)
    disc = exp(-r*T)
    return disc*np.maximum(ST - K, 0.0), disc*ST         # (Y_i, X_i)

plain_sums, cv_sums = [], []
for b in range(n_batches):
    Y, X = mc_batch(n_paths)
    # control variate: Y_cv = Y - beta*(X - E[X]); X = disc*S_T => E[X] = S
    EX = float(S)
    beta = float(np.cov(Y, X, ddof=1)[0, 1] / np.var(X, ddof=1))
    Ycv = Y - beta*(X - EX)
    plain_sums.append((Y.mean(), Y.std(ddof=1)/np.sqrt(len(Y))))
    cv_sums.append((Ycv.mean(), Ycv.std(ddof=1)/np.sqrt(len(Ycv))))

pm = np.array(plain_sums); cm = np.array(cv_sums)
se_plain, se_cv = pm[:,1].mean(), cm[:,1].mean()
print(f"\nMC ({n_batches} batches x {n_paths:,} paths)")
print(f"  closed form        : {g['price']:.4f}")
print(f"  MC plain   estimate: {pm[:,0].mean():.4f}  (avg batch SE {se_plain:.4f})")
print(f"  MC + ctrl-variate  : {cm[:,0].mean():.4f}  (avg batch SE {se_cv:.4f})")
print(f"  SE reduction factor: {se_plain/se_cv:.1f}x   |error vs closed form| "
      f"{abs(pm[:,0].mean()-g['price']):.4f} -> {abs(cm[:,0].mean()-g['price']):.4f}")

# ---------------- bump-and-revalue Greek cross-check ----------------
h = 0.01
up   = bs_call_greeks(S+h, K, T, r, sig)['price']
down = bs_call_greeks(S-h, K, T, r, sig)['price']
print(f"\nfinite-difference check: delta_fd={(up-down)/(2*h):+.4f} vs analytic {g['delta']:+.4f}")
gamma_fd = (up - 2*g['price'] + down)/(h*h)
print(f"                        gamma_fd={gamma_fd:.4f} vs analytic {g['gamma']:.4f}")
```

Actual output (executed before embedding):

```text
Black-Scholes European call, S=K=100 T=1y r=5% vol=20%
  price :   10.4506
  delta :    0.6368
  gamma :    0.0188
  vega  :   37.5240
  theta :   -6.4140
  rho   :   53.2325
  sanity: put via parity = 5.5735

MC (40 batches x 50,000 paths)
  closed form        : 10.4506
  MC plain   estimate: 10.4556  (avg batch SE 0.0659)
  MC + ctrl-variate  : 10.4482  (avg batch SE 0.0251)
  SE reduction factor: 2.6x   |error vs closed form| 0.0050 -> 0.0024

finite-difference check: delta_fd=+0.6368 vs analytic +0.6368
                        gamma_fd=0.0188 vs analytic 0.0188
```

Reading the output: the closed form anchors everything — call 10.4506, put-by-parity 5.5735, delta 0.6368 meaning the replicating portfolio holds ~64 shares per call, gamma 0.0188 saying that hedge goes stale by ~19 deltas per $1 move, vega 37.52 total (= 0.375 per vol point — quote convention divides by 100). Monte Carlo plain already lands within one SE (0.0659); the control variate exploits knowing E[e^{−rT}S_T] = S₀ exactly, cutting batch SE 2.6× and absolute error to 0.0024 — variance reduction buys accuracy without extra paths, which is money when pricing books of thousands of contracts. Finite differences reproduce both Greeks to 4 decimals, demonstrating that bump-and-revalue agrees with analytic calculus ONLY while the payoff is smooth — swap the call payoff for a digital and watch central differences become noise-dependent garbage near the discontinuity.

---


## How it's done in production

**Pricing infrastructure.** QuantLib-class libraries or proprietary engines compute closed forms where they exist, lattices/PDEs for Americans and early-exercise features, MC for path-dependents (Asians, barriers, lookbacks) and XVA. Vol surfaces parameterized via SVI slices or SABR per tenor, calibrated intraday to tick with arbitrage constraints (butterfly/calendar positivity), interpolated consistently for strikes without quotes. Conventions matter embarrassingly much: day counts, calendar vs business-day vol, settlement style (SPX AM-settled opens vs PM-settled weeklies), dividend schedules — most "model disagreements" are convention bugs.

**Risk systems.** Overnight full-reval ladders plus intraday analytic Greeks: delta by underlying with hedge baskets, gamma scaled by expected moves, vega bucketed by tenor/strike region (wings monitored via volga), vanna for surface-shift sensitivity. Stress grids shock spot/vol/rate jointly because ATM-forward drift makes naive parallel shocks mislead. Margin engines (SPAN-style scenario arrays at clearinghouses; SA-CCR ISDA SIMM for bilateral) consume the same sensitivities as capital inputs.

**Monte Carlo at scale.** XVA desks run 100k+ paths × thousands of exposure dates × counterparty dimensions overnight on GPU/CPU grids, using control variates, quasi-random sequences, and adjoint (AAD) methods to get ALL Greeks from one sweep instead of per-parameter bumps — AAD cut Greek-computation cost roughly to O(1)× pricing cost and is now standard in bank libraries. Discretization bias budgets are documented like model-risk items: scheme choice validated against closed-form cases before trusting exotics.

**Desk workflow.** Quotes are two-sided in implied vol, not price; traders position along the surface (long skew via put spreads, long term-structure via calendars) while delta-hedging mechanically. Expiry mechanics get operational respect: pin risk near strikes into expiration, assignment/early-exercise checks (dividend dates drive American call exercise; deep-ITM puts exercise for interest), corporate-action adjustments, and borrow/cost modeling for synthetics. Governance wraps everything in SR 11-7-style validation (T24-mrm): independent reimplementation of pricers, benchmark books with known answers, documented interpolation choices.

## Tradeoffs & when NOT to use it

- **Black-Scholes assumptions are a calibration language, not physics**: fat tails, discrete hedging costs, transaction costs, and stochastic vol mean BS prices are consensus quoting devices (implied vol), not fair values. Trading deep OTM tails priced purely off extrapolated smiles is where books die.
- **MC is the wrong tool for strong early exercise**: American features need lattices/PDEs/Longstaff-Schwartz; naive European-style MC underprices exercisability silently.
- **Bump-and-revalue breaks on discontinuities**: digital/barrier Greeks need pathwise-smoothing or likelihood-ratio methods; finite-difference noise near kinks produces unstable hedges that look fine until expiry.
- **Local-vol fit ≠ local-vol dynamics**: fitting today's surface exactly does not make forward-vol hedges right; barrier/range products priced purely local-vol systematically mis-hedge (the reason exotics desks overlay stochastic-vol judgments).
- **Variance reduction can hide model risk**: a beautifully converged MC of a misspecified process is precise nonsense; separate statistical error (SE) from model error (process choice) in every review.
- **Don't quote what you can't hedge**: illiquid strikes, gap-risk names over weekends, and event binaries demand margin beyond models — mark-to-model positions need governance haircuts (T24-mrm).

## Interview questions

### Q1 — Derive the Black-Scholes price WITHOUT the PDE. What's the intuition doing the work?
**Testing:** replication logic beneath the formula.
**Answer:** Continuous delta-hedging manufactures the payoff synthetically: holding ∂C/∂S shares makes portfolio risk vanish locally, so its return must be risk-free — hence value = cost of replication = discounted risk-neutral expectation E[e^{−rT}(S_T−K)⁺] with S_T lognormal drifting at r. Compute via d₂ = P(S_T>K) under Q, integrate piecewise: S₀N(d₁) − Ke^{−rT}N(d₂). The punchline interviewers want stated: μ disappears because hedging eliminates the risk premium from the OPTION's price — only σ survives.
**Follow-up trap:** *"So expected returns never matter?"* — For continuously-hedgeable vanilla claims, correct. They rush back the moment hedging is discrete/costly (gamma-barrier rebalancing P&L depends on realized paths), for jump gaps no continuous hedge exists across, and for any position sized past liquidity — which is why real desks track realized-vs-implied attribution obsessively.

### Q2 — Your delta-hedged long call made +$40k this week. What happened?
**Testing:** the gamma-theta breakeven identity in live action.
**Answer:** Hedged convexity earned ≈ Σ½ΓᵢSᵢ²(σ²_realized,i − σ²_implied,i)Δt over the week: realized vol exceeded your entry implied (you were long gamma cheaper than the market moved). The mirror statement: theta you bled equals the implied vol rent; net positive means realized > implied. Follow-ups write themselves — annualize realized, compare against entry IV, check whether the win was path luck (one gap) versus sustained dispersion.
**Follow-up trap:** *"Then just always buy cheap vol?"* — Cheap relative to WHAT forecast? Long-gamma strategies bleed steadily when realized stays under implied (vol risk premium is persistently negative for index puts — sellers harvest it); the edge must come from a volatility FORECAST advantage or structural flows, not from the identity itself. The identity is accounting, not alpha.

### Q3 — Rank Greeks behavior: where do gamma, vega, theta peak, and how do they scale with T?
**Testing:** table fluency without looking up.
**Answer:** Gamma peaks ATM and grows as expiry approaches (∝1/(σ√T)-ish scaling) — 0DTE options carry explosive gamma. Vega peaks ATM but GROWS with √T (more time for vol to act); a 2y ATM has ~14x the vega of a 1-week ATM (marked ~). Theta most negative ATM short-dated — exactly mirroring gamma since they're the same coin's faces (gamma earnings vs theta rent). Rho grows with T, negligible short-dated. Deep ITM/OTM wings: all first-order Greeks fade except delta saturating to 0/1.
**Follow-up trap:** *"Long calendar then — which legs give what?"* — Sell near-dated (short gamma, collecting fast theta), buy far-dated (long vega, slow theta): profits if spot pins near strike short-term or implied term structure rises; dies if spot rips through both strikes (you're short the front gamma precisely when movement accelerates). Calendars are term-structure trades wearing gamma clothing.

### Q4 — C = 10.45, K=100, S=105, r=5%, T=1, no dividends. What's P? What synthetic does that let you build?
**Testing:** parity drill at whiteboard speed.
**Answer:** Parity: C − P = S − Ke^{−rT} ⇒ P = 10.45 − 105 + 100·e^{−0.05} = 10.45 − 105 + 95.12 = 0.57. Synthetics: short call + long put + lend PV(K) replicates... more usefully: long stock = long call + short put (+ bond leg); converting desk inventory between calls/puts/stock via parity is daily bread. Arbitrage discipline: if traded P were 1.20, buy put + sell call + buy stock financed at repo → lock 0.63 minus costs; parity deviations in liquid names live inside transaction-cost bands, not zero.
**Follow-up trap:** *"With dividends?"* — Subtract PV(divs) from the stock leg: C − P = S − PV(div) − Ke^{−rT}. Ignore dividends and every conversion/reversal desk trade quietly leaks — the classic junior mistake on index books around ex-div dates.

### Q5 — Why does the equity index smile skew downward, since WHEN, and why didn't the original model care?
**Testing:** empirical history plus model-theory reconciliation.
**Answer:** Post-October-1987, OTM index puts price at higher implied vols than calls — permanent crash-insurance demand plus the leverage effect (equity falls ⇒ debt/equity ratio rises ⇒ vol rises). Pre-87 smiles were mild; the crash taught the market that large downward gaps exist, and BS's constant-σ lognormal world cannot price them. Single names show steeper skew than indexes (idiosyncratic jumps), FX quotes symmetric-ish smiles via 25Δ risk reversals, commodities flip sign seasonally.
**Follow-up trap:** *"Isn't skew just fear premium — sellable?"* — Shorting wings harvests premium until it doesn't: 1987 itself bankrupted vol sellers (gap moves exceed any dynamic hedge); the smile persists partly BECAUSE supply of tail insurance is structurally scarce. Position sizing on wing shorts is a survival question, not a Sharpe question.

### Q6 — Heston vs Dupire local vol vs jump diffusion: pick and defend for (a) vanillas book, (b) forward-variance product.
**Testing:** model-zoo judgment tied to product, not fashion.
**Answer:** (a) Vanillas: local vol or SVI-fitted surfaces suffice — you're marking to a liquid market, dynamics barely matter for linear-in-vol claims; keep it simple and auditable. (b) Forward variance/VIX options: Heston-class stochastic vol (or explicit forward-variance models) is mandatory because local vol implies forward vols locked to today's surface — empirically forward vol moves independently, so LV systematically misprices mean reversion of variance. Jump diffusion earns its slot for short-dated wing pricing (crash binaries). The senior answer names WHY each fails outside its lane.
**Follow-up trap:** *"Why not calibrate one big model to everything?"* — Over-parameterized joint fits become unfalsifiable and unfixable at 3am; production desks run small models per product family with documented overlap policies, because a model whose failures you understand beats a black box whose failures you discover client-side.

### Q7 — Explain Monte Carlo control variates with the canonical choice. Why does it work and when does it fail?
**Testing:** variance-reduction mathematics with operational sense.
**Answer:** If X has known expectation EX and correlates with payoff Y, define Y_cv = Y − β(X − EX); Var(Y_cv) minimized at β* = Cov(Y,X)/Var(X), giving variance reduction factor 1/(1−ρ²). Canonical pair: X = e^{−rT}S_T with EX = S₀ exactly under Q; for an ATM call ρ ≈ 0.95+ ⇒ ~10x SE cuts available; our lab showed 2.6x at these parameters with error halving to 0.0024. Fails when correlation is weak (deep OTM wings — payoff nearly orthogonal to terminal asset; switch controls to integrated variance for vol-driven payoffs), and β estimation adds its own noise if recomputed naively per batch.
**Follow-up trap:** *"Antithetics too — always stack them?"* — Antithetic pairing helps symmetric problems and is free; but for asymmetric payoffs (barriers) antithetic pairs can be BOTH worthless (one path knocked out, its mirror not, doubling nothing) or even degrade convergence slightly. Measure, don't assume — SE diagnostics belong in every MC report.

### Q8 — How do you get Greeks out of a Monte Carlo, and which method breaks on digitals?
**Testing:** MC-Greek method taxonomy — separates practitioners from tutorial readers.
**Answer:** Three routes: bump-and-revalue (finite differences — intuitive; noisy for second order, biased near kinks, bump-size dilemma: too small = numerical noise, too big = curvature error); pathwise (differentiate the simulated payoff pathwise — exact and cheap for smooth payoffs like vanillas; FAILS at discontinuous payoffs like digitals/barriers without smoothing tricks like sigmoid proxies); likelihood-ratio (differentiate the transition density w.r.t. parameter — handles kinks cleanly but high variance). Production stacks increasingly use AAD (adjoint) to get every Greek from one backward pass at ~O(1)x pricing cost.
**Follow-up trap:** *"Just smooth the digital with a narrow call spread?"* — That's the practical fix (static replication approximation), but the spread width becomes a hidden model parameter: document it, stress it, and reconcile against market-quoted digital prices — otherwise your "Greeks" embed an arbitrary choice that risk reports will happily launder into capital numbers.

### Q9 — When would you exercise an American call early? American put?
**Testing:** early-exercise logic without hand-waving.
**Answer:** American CALL on non-dividend stock: NEVER optimal (selling beats exercising — exercising throws away time value and forfeits insurance; proof via parity bounds). With dividends: exercise just before an ex-div date when div > remaining time value (typically only deep ITM near expiry). American PUT: early exercise CAN be optimal when deep ITM because interest on K received NOW beats option's remaining insurance value (put's time value shrinks as S falls); the boundary is a curve in (S,t), computed by lattice/PDE — the American premium over European widens for low rates/high vol.
**Follow-up trap:** *"Rates go negative — what flips?"* — Negative rates invert the put logic (holding cash costs money, so delaying exercise earns negative carry → earlier exercise optimal) and break some closed-form conventions built assuming positive carry; post-2015 EUR/CHF markets forced repricing libraries to handle it — interviewers love checking whether candidates know this actually happened.

### Q10 — What exactly IS implied vol, given Rebonato's 'wrong number in the wrong formula' line?
**Testing:** conceptual honesty about the field's central object.
**Answer:** Operationally: IV is the σ that maps a market PRICE through BS back to a number — a standardized quotation unit, letting desks trade vol directly (bid/offer in vol points) independent of premium clutter. It is NOT a forecast of realized vol, NOT a model parameter with physical meaning; different strikes/tenors imply different σ precisely because the true process isn't GBM. Its value: comparability, Greeks computation (vega/gamma from a single coherent framework), and cross-market communication. Its danger: treating surface shape as model truth rather than supply/demand record of insurance preferences.
**Follow-up trap:** *"Then why compute anything analytically at all?"* — Because hedging happens in delta/gamma space regardless of pricing model sophistication; BS-Greeks remain the industry's lingua franca for risk transfer, and even ML-priced books publish BS-equivalent Greeks so counterparties/regulators can parse them. The formula survived as LANGUAGE after dying as PHYSICS.

### Q11 — How is the VIX calculated and what financial claim is it approximately?
**Testing:** connects smile math to a tradable everyone has heard of.
**Answer:** Modern methodology (2003): a model-free strip of out-of-money SPX calls+puts across strikes integrates their weighted prices into expected swap variance over the next 30 days — essentially the fair STRIKE of a 30-day variance swap (annualized, sqrt'd). So VIX ≈ √(E^Q[realized variance₁₅d–₄₅d]) quoted in vol points. VIX futures/options therefore trade variance risk premium — contango most of the time, violent backwardation in crises (Feb 2018 'Volmageddon' killed short-vol ETPs when a spike exceeded product leverage).
**Follow-up trap:** *"Buy VIX calls as crash hedge then?"* — Works directionally but bleeds structurally: roll yield in contango eats ~5-10%/month (marked ~), and basis between VIX (implied, Q-measure) and realized SPX vol varies. Direct variance swaps or listed SPX put spreads often implement the same view cheaper once sizing/friction is honest.

### Q12 — You must price a 3-month exotic whose payoff depends on the path average. Walk through the MC design end-to-end including Greeks and error budget.
**Testing:** end-to-end engineering of the module's whole stack.
**Answer:** Process: calibrated surface (SVI slice at 3m, or Heston if forward-vol sensitivity matters) → simulate daily (or better, Brownian-bridge exact averages between coarser steps to kill discretization bias for the averaging feature) under risk-neutral drift with dividends → payoff on arithmetic average → control variate pairing with geometric-average Asian (closed form available!) for massive SE cuts — the textbook-perfect CV here. Greeks: pathwise delta/vega work (smooth payoff), AAD if part of a book system. Error budget: statistical SE target (e.g., <0.01% of notional ⇒ n paths chosen accordingly), discretization bias measured against weekly-vs-daily convergence study, model risk flagged separately (LV vs Heston disagreement reported as a range). Deliverable includes all three error types labeled — statistical, discretization, model.
**Follow-up trap:** *"Why not just fine-grid everything to death?"* — Cost scales linearly in steps × paths while accuracy gains square-root: brute force wastes the compute budget that governance wants spent on SCENARIO breadth (XVA-style); smart variance reduction and exact-simulation tricks dominate raw resolution. Knowing WHERE the budget goes is the job.

## Red flags

- Reciting the BS formula with no replication/risk-neutral story behind it.
- Believing implied vol forecasts realized vol rather than quoting it as a price.
- No gamma-theta breakeven identity when discussing hedged option P&L.
- Greeks tables memorized without signs reasoning (e.g., short put = long gamma).
- MC presented without standard errors or variance reduction discussion.
- Bump-and-revalue Greeks on discontinuous payoffs without acknowledging the kink problem.
- Local vol treated as dynamics truth rather than today's-surface interpolator.
- Selling wings/skew with no gap-risk narrative (1987 amnesia).
- Ignoring dividends/borrow in parity and synthetic constructions.
- Mark-to-model marks with no documented interpolation or governance.

## Cheat card

```
BS          C = S*N(d1) - K e^{-rT} N(d2)
            d1=[ln(S/K)+(r+s^2/2)T]/(s*sqrt(T)); d2=d1-s*sqrt(T)
            parity: C-P = S - PV(div) - K e^{-rT}
RISK-NEUTRAL price = E^Q[e^{-rT} payoff]; mu gone via hedging
GREEKS      delta=N(d1); gamma=phi(d1)/(S s sqrtT) ATM-short-T max
            vega=S phi(d1) sqrtT (grows w/ T); theta=-[...] (gamma's rent)
            hedged P&L ~ .5 G S^2 (sig_real^2 - sig_impl^2) dt
            vanna=dvega/dS ; volga=dvega/dvol -> wings
AMERICAN    call: only before ex-div if div>time value
            put: deep-ITM exercise (interest on K); neg rates -> sooner
SMILE       post-87 index put skew permanent (crash insurance +
            leverage); FX 25RR/BF quoting; SVI/SABR interpolation
MODELS      local vol fits surface, wrong fwd dynamics; Heston
            stoch vol for fwd variance; jumps for short wings
MC          S_T exact: exp((r-s^2/2)T + s sqrtT Z); SE~1/sqrt(n)
            antithetic pairs; control variate beta*=Cov/Var,
            X=e^{-rT}S_T, EX=S0 (lab: 2.6x SE cut)
            greeks: pathwise (smooth) | LR (kinks) | AAD (books)
VIX         model-free 30d var-swap strike from SPX otm strip;
            contango bleeds short-vol rolls; Feb-18 volmageddon
GOVERNANCE  IV = wrong number/wrong formula (Rebonato) - a QUOTE;
            label errors: statistical / discretization / model
```

## Sources

- [Black, Scholes (1973). The Pricing of Options and Corporate Liabilities. J. Political Economy 81(3)](https://www.jstor.org/stable/1831029); accessed 2026-08-23
- [Merton (1973). Theory of Rational Option Pricing. Bell Journal of Economics 4(1)](https://www.jstor.org/stable/3003143); accessed 2026-08-23
- [Cox, Ross, Rubinstein (1979). Option Pricing: A Simplified Approach. J. Financial Economics 7](https://www.sciencedirect.com/science/article/abs/pii/0304405X79790151); accessed 2026-08-23
- [Heston (1993). A Closed-Form Solution for Options with Stochastic Volatility… Review of Financial Studies 6(2)](https://academic.oup.com/rfs/article/6/2/327/1591701); accessed 2026-08-23
- [Dupire (1994). Pricing with a Smile. Risk Magazine 7(1)](https://www.risk.net/derivatives/1508266/pricing-smile); accessed 2026-08-23
- [Glasserman (2003). Monte Carlo Methods in Financial Engineering. Springer](https://link.springer.com/book/10.1007/978-0-387-21617-1); accessed 2026-08-23
- [Gatheral (2006). The Volatility Surface: A Practitioner's Guide. Wiley](https://www.wiley.com/en-us/The+Volatility+Surface%3A+A+Practitioner%27s+Guide-p-9780471792512); accessed 2026-08-23
- [CBOE (2003/2019). VIX White Paper (variance-swap methodology)](https://www.cboe.com/microsites/vix/documents/VIXWhitePaper.pdf); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
