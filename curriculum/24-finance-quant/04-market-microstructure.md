# Order Books, Liquidity, Slippage, Execution — How Markets Actually Work

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-time-series-core · **Updated:** 2026-08-23
> **Module id:** `T24-market-microstructure` · **Tags:** markets

## The 30-second version

A market is not a price — it's a *matching engine* holding two queues. The limit order book stores resting buy/sell commitments ranked by price then time priority; the bid-ask spread and level depth are standing PRICES OF LIQUIDITY, set by a three-way tug between order-processing costs, inventory risk, and adverse selection (Kyle 1985; Glosten-Milgrom 1985). Two roles define the game: *makers* post passively — they earn the spread plus rebates (~$0.002/share credits at many venues, ~0.2bp scale) but bear queue risk and the winner's curse (a fill is evidence the market moved against you); *takers* cross the spread for certainty, paying spread plus take fees (~$0.003/share, ~0.35bp scale). Moving size beyond the touch costs *impact*: the most robust empirical law in execution is the square-root form Δp ≈ Y·σ·√(Q/VADV) with Y ~ 0.4–1.0 × daily volatility at one-day participation (marked ~ throughout — coefficients are regime-dependent), turned into optimal scheduling by Almgren-Chriss (2000)'s risk-versus-impact frontier. This machinery explains the JD's sharpest question — *why backtests lie about fills*: simulated fills happen instantly at signal prices with zero queue position, no adverse selection, no latency drift, and no capacity decay, which together routinely overstate achievable performance by 30–80% of gross Sharpe. Anyone who can't reason about books is quoting prices they can't get filled at.

## Why this gets asked

Because execution quality decides whether quant research survives contact with markets, and it's the cheapest interview to fake-proof. D.E. Shaw Principal/GA-Tech screens and Citi VP targets probe three layers. (1) *Mechanics*: can you walk a matching engine, explain price-time priority, and compute a fill through five levels without hand-waving? (2) *Economics*: do you understand why maker/taker pricing shapes flow, why payment-for-order-flow wholesalers compete for retail (uninformed flow = low adverse-selection cost per fill), and why your own limit order filling is statistically bad news — you were filled because informed flow hit your quote. (3) *Judgment*: given a 500k-share order in a 2M-share ADV name (25% participation if done naively — absurd), can you decompose implementation shortfall into delay cost, spread paid, temporary impact, permanent impact, and opportunity cost of unfilled remainder, then choose a schedule along the Almgren-Chriss frontier instead of reciting "use VWAP"? The kill-question family mirrors T24-ts-validation: "your backtest assumed mid fills — quantify the damage" expects the chain half-spread → impact at realistic participation → adverse-selection haircut on passive fills → "gross Sharpe minus 30–80% depending on capacity." Candidates who treat microstructure as plumbing beneath their pay grade fail precisely the interviews designed to find people who lose money quietly.

## Lineage

**What came before.** Markets ran on specialists and open outcry: a designated dealer quoted both sides, kept inventory, matched by hand — liquidity was a person, not an algorithm. Theory arrived in a burst: Kyle (1985) modeled an informed trader strategically draining a market maker who breaks even against noise traders, defining price-impact lambda λ = dP/dFlow; Glosten-Milgrom (1985) derived spreads purely from adverse selection — the maker updates beliefs after every trade, so quotes must move even with risk-neutral competitive dealers; Roll (1984) showed spreads leave a fingerprint in serial price covariances (cov(Δp_t, Δp_{t−1}) ≈ −(s/2)²), giving the first effective-spread estimator from closes alone. Amihud (2002) later supplied the workhorse illiquidity proxy: average |return| per dollar of volume. Execution was craft until Perold (1988) named implementation shortfall — the gap between the decision-price paper portfolio and realized P&L — making execution quality measurable for the first time.

**Where it stands now.** Fragmentation industrialized liquidity: Reg NMS (2005) linked US venues through the NBBO with $0.01 minimum ticks; today ~16 registered exchanges plus 30–40 ATSs/dark pools compete, and roughly 42–47% of US equity volume executes off-exchange (dark pools plus internalizing wholesalers) through the 2020s. Fee structures flipped incentives: maker-taker schedules reward passive quoting with per-share rebates while taker fees ($0.0025–0.0035/share typical tiers) tax immediacy; PFOF lets wholesalers internalize retail profitably because retail flow carries little information. Execution became quantitative engineering: Almgren-Chriss (2000) cast scheduling as minimizing impact cost plus timing-risk variance along an explicit frontier; Almgren et al. (2005) estimated impact directly from ~700k metaorder... more conservatively: from hundreds of thousands of institutional child orders, confirming square-root scaling; Bouchaud's school (Tóth et al.) verified the law's universality across futures, equities, FX, crypto. Latency became infrastructure sport: colocation at exchange data centers, microwave relays cutting Chicago-NYC one-way to ~4ms versus ~7ms+ on fiber, IEX selling a deliberate 350-microsecond speed bump as fairness. Market-making theory matured with Avellaneda-Stoikov (2008) reservation-quote skewing by inventory, and TCA desks standardized markouts — post-trade drift after YOUR fills, the honest mirror of execution quality.

**Where it's heading.** Three currents. First, structure reform pressure: the SEC's 2022–24 equity market structure push (tick-size/round-lot modernization for sub-dollar stocks, expanded Rule 605 execution-quality disclosure, auction-time competition for individual investor orders) and T+1 settlement (May 28, 2024) shrink capital-and-latency edges incrementally. Second, 24-hour trading creep — overnight sessions from major venues and retail brokers force liquidity-provision models beyond human-hours books. Third, ML-native market making: learned impact models conditioned on order-flow imbalance, RL schedulers benchmarked against Almgren-Chriss baselines, and generative order-flow simulators (agent-based calibrations à la ABIDES) replacing static book snapshots in backtests — the exact direction our toy matching engine gestures toward.

---


## Mental model

```
THE BOOK IS TWO QUEUES AND A CONTRACT:

        asks  100.04 | 120           <- sellers, worst first
              100.03 | 450
              100.02 | 300    <- BEST ASK (the touch)
   spread ->   100.02|100.01
              100.01 | 500     <- BEST BID (the touch)
               99.99 | 380
               99.98 | 210

THREE PRICES OF LIQUIDITY (every trade pays >= one):
  1. SPREAD       cost of NOW, tiny size      ~ half-spread per side
  2. DEPTH/IMPACT cost of SIZE                ~ Y*sigma*sqrt(Q/V), Y~0.4-1
  3. TIMING RISK  cost of PATIENCE            ~ vol during the wait

ADVERSE SELECTION CYCLE (why quotes are wide):
  informed flow arrives -> hits best quote -> quote moves AGAINST maker
  -> maker widens/skews -> spread = compensation for losing to info
  -> Roll: cov(dp_t, dp_{t-1}) ~= -(s/2)^2 measures it from closes

MAKER vs TAKER:
  MAKER  earns spread + rebate (~+0.2bp) ... IF filled; queue risk,
         and fills are ADVERSELY SELECTED (you were wrong on arrival)
  TAKER  pays spread + fee (~-0.35bp), gets certainty, no queue
```

Deepest framing: every fill is a trade between you and someone who priced the asset better than you did at that instant — sometimes that's noise (fine, that's the premium makers earn), sometimes it's information (that's the rent). Liquidity is not a property of the asset; it's a *service* with a price schedule that changes by the second.

---

## How it actually works

### Matching engines and order types

Modern exchanges run price-time-priority continuous limit order books: resting orders queue at each price level FIFO; incoming marketable orders sweep levels best-first until filled or exhausted. Variants exist (pro-rata allocation in some futures/staking books, midpoint auctions, closing auctions matching all supply/demand at a single print — the close now handles ~10%+ of daily volume in US equities). Order types encode execution intent: market (immediate, any price), limit (price-capped, rests if unmarketable), IOC/FOK (immediate-or-cancel / fill-or-kill — no resting), iceberg (display a slice, hide residual to reduce information leakage), pegged/midpoint (track NBBO or mid). The hidden reality: displayed depth is the tip of true interest — icebergs, reserved liquidity at away venues, and wholesalers' internalized books mean the visible book understates available liquidity while overstating what will still be there when YOU arrive.

### Where the spread comes from — three components

Decompose s into processing costs (fixed per share, tiny for liquid names), inventory risk compensation (maker absorbs position risk until offsetting flow arrives; scales with σ), and adverse selection (expected loss to informed traders per fill; dominates in news regimes and illiquid names). Glosten-Milgrom logic: even zero-cost, risk-neutral makers must widen spreads because the ACT of trading reveals counterparties know something. Testable fingerprints: Roll's covariance estimator recovers effective spreads from daily closes; effective spreads widen around earnings; half-spread correlates with volatility roughly linearly across assets. Amihud's |r|/$volume proxy captures the cross-sectional liquidity gradient well enough to price an "illiquidity premium" (~historically 0.3–0.7%/yr return premia attributed in some studies, marked ~).

### Maker/taker economics and the retail-flow business

Fee schedules make liquidity provision a business line: typical exchange tiers charge takers $0.0025–0.0035/share and rebate makers $0.0015–0.0030/share (at a $100 stock ≈ 0.30bp cost / 0.20bp credit; crypto venues run wider schedules). Makers profit from spread capture + rebates MINUS adverse selection minus queue-position opportunity cost — top-of-book queue priority is worth real money, which is why colocation and sub-millisecond cancel-replace games exist. Takers pay for certainty. PFOF extends the logic: wholesalers bid for retail order flow (paying brokers per share) because retail is uninformed — internalizing it is profitable even after price improvement, and the wholesaler hedges net exposure in the lit markets. Regulatory tension follows the money: SEC 2022–24 proposals target order-by-order auctions and expanded disclosure precisely because internalization may (or may not) harm price discovery — the empirical debate remains live.

### Impact: temporary vs permanent, and the square-root law

A metaorder of size Q moves price in two parts: TEMPORARY impact (reverts after execution ends — liquidity consumption) and PERMANENT impact (information leakage — the market updates fair value because someone traded big). Almgren-Chriss formalize scheduling: splitting Q across time trades impact cost against timing risk (variance of remaining inventory); faster = more impact, slower = more risk, with an optimal trajectory front-loading when risk aversion is low. Empirically, impact vs Q/V follows the square-root law remarkably well across markets: Δp ≈ ±Y·σ_daily·√(Q/VADV), Y ≈ 0.4–1.0 (marked ~; regime/venue-dependent), NOT the linear-in-participation form naive models assume. Why square-root? The diffusion argument: information diffuses through the trader population like heat; cumulative permanent impact grows with √time-of-execution, and participation Q/V over horizon T gives the observed scaling. Consequences worth quoting: 1% ADV costs ~5–9bp for a 25%-vol-year name (marked ~); doubling size costs only ~40% more; capacity math follows directly.

### Why backtests lie about fills — the JD's kill-shot, answered precisely

Five compounding fantasies. (1) *Mid-price fills*: every trade implicitly saves half-spread — on our lab book that's ~1bp median each side, pure fiction. (2) *Infinite queue priority*: passive backtest fills assume you were FIRST in queue; real queues hold thousands of contracts/shares ahead, and fill probability decays with distance from touch. (3) *No adverse selection on fills*: your limit fill arriving means informed flow hit YOU — conditional on filling, your signal's edge is lower than unconditional; simulators that fill you whenever price touches your quote give you the winner's curse for free. (4) *Zero latency drift*: signal computed at bar close executed at that same close ignores 1ms–1s of price movement toward your alpha being arbed away. (5) *No self-impact/capacity*: strategies tested at sizes that would move the very prices they predict. Aggregate damage: realistic cost models commonly erase 30–80% of gross Sharpe (marked ~; strategy-dependent), which is exactly why TCA exists and why validation gates pair with microstructure realism (T24-ts-validation).

---

## Build it from scratch

Runnable numpy-only limit-order-book matching engine with stochastic flow, then metaorder slippage measured against the square-root law:

```python
import numpy as np

rng = np.random.default_rng(23)
TICK = 0.01

class LOB:
    def __init__(self):
        self.bids = {}                       # price -> resting qty
        self.asks = {}
    def best_bid(self): return max(self.bids) if self.bids else None
    def best_ask(self): return min(self.asks) if self.asks else None
    def add_limit(self, side, price, qty):
        bk = self.bids if side == "B" else self.asks
        bk[price] = bk.get(price, 0) + qty
    def cancel(self, side, price, qty):
        bk = self.bids if side == "B" else self.asks
        if price in bk:
            bk[price] -= qty
            if bk[price] <= 0: del bk[price]
    def market_order(self, side, qty):
        """Cross the spread -> (filled_qty, vwap). Mutates resting book."""
        bk = self.asks if side == "B" else self.bids
        prices = sorted(bk)
        if side == "A": prices = prices[::-1]
        filled, notional = 0, 0.0
        for p in prices:
            if filled >= qty: break
            take = min(bk[p], qty - filled)
            filled += take; notional += take * p
            bk[p] -= take
            if bk[p] <= 0: del bk[p]
        return filled, (notional / filled if filled else float("nan"))

book, mid = LOB(), 100.00
for _ in range(400):                              # seed two-sided liquidity
    side = "B" if rng.random() < 0.5 else "A"
    lvl  = int(rng.integers(1, 8))
    px   = round(mid - lvl*TICK, 2) if side == "B" else round(mid + lvl*TICK, 2)
    book.add_limit(side, px, int(rng.integers(5, 60)))

spreads, depths = [], []
for ev in range(4000):                            # stochastic order flow
    u = rng.random()
    if u < 0.62:                                  # passive limit near the touch
        side = "B" if rng.random() < 0.5 else "A"
        bb, ba = book.best_bid(), book.best_ask()
        px = round((bb + int(rng.integers(-2, 3))*TICK) if side == "B"
                   else (ba - int(rng.integers(-2, 3))*TICK), 2)
        if side == "B" and (ba is None or px < ba): book.add_limit("B", px, int(rng.integers(5, 50)))
        elif side == "A" and (bb is None or px > bb): book.add_limit("A", px, int(rng.integers(5, 50)))
    elif u < 0.78:                                # cancellation thins best level
        side = "B" if rng.random() < 0.5 else "A"
        bk = book.bids if side == "B" else book.asks
        if bk:
            px = (max if side == "B" else min)(bk)
            book.cancel(side, px, min(bk[px], int(rng.integers(1, 15))))
    else:                                         # market order consumes depth
        q = int(rng.integers(10, 120))
        book.market_order("B" if rng.random() < 0.5 else "A", q)
    bb, ba = book.best_bid(), book.best_ask()
    if bb is None or ba is None or bb >= ba:      # re-seed crossed/vanished book
        book.add_limit("B", round(mid-TICK, 2), 30)
        book.add_limit("A", round(mid+TICK, 2), 30)
        continue
    mid = 0.95*mid + 0.05*(bb+ba)/2
    spreads.append((ba-bb)/mid*1e4)
    depths.append(sum(q for p, q in book.asks.items() if p <= ba+4*TICK))

print(f"avg spread           : {np.mean(spreads):6.1f} bps (median {np.median(spreads):.1f})")
print(f"avg ask depth <=5tix : {np.mean(depths):6.0f} shares")

# ---------------- metaorder slippage vs square-root law ----------------
SIG_DAILY_BPS = 25.0        # ~ daily vol of this asset, bps (~0.25%)
ADV           = 250_000      # ~ ADV in same share units as the book
K_SQRT        = 0.9          # ~ sqrt coefficient Y, typical range ~0.4-1.0

def walk_cost(Q):
    snap_b, snap_a = dict(book.bids), dict(book.asks)
    bb, ba = book.best_bid(), book.best_ask()
    arrival_mid = (bb + ba) / 2
    f, vwap = book.market_order("B", Q)
    slip_bps = (vwap - arrival_mid) / arrival_mid * 1e4
    book.bids, book.asks = snap_b, snap_a             # restore state exactly
    return f, slip_bps

print(f"\n{'Q':>6} {'particip%':>10} {'walked bps':>11} {'sqrt-model bps':>15}")
for Q in [200, 800, 3000, 8000]:
    eta  = Q / ADV
    pred = K_SQRT * SIG_DAILY_BPS * np.sqrt(eta)
    _, s = walk_cost(Q)
    print(f"{Q:6d} {100*eta:10.4f} {s:11.1f} {pred:15.1f}")

# ---------------- maker/taker economics of one round trip ----------------
HALF_SPREAD_BPS  = float(np.median(spreads)) / 2
MAKER_REBATE_BPS, TAKER_FEE_BPS = 0.20, 0.35       # ~ typical tiered schedule
maker_pnl  = HALF_SPREAD_BPS + MAKER_REBATE_BPS    # earn spread + rebate IF filled
taker_cost = HALF_SPREAD_BPS + TAKER_FEE_BPS       # cross + fee buys certainty
print(f"\nround-trip economics vs median half-spread {HALF_SPREAD_BPS:.1f} bps:")
print(f"  passive maker earns {maker_pnl:+.2f} bps | aggressive taker pays {-taker_cost:+.2f} bps")
print(f"  queue-risk tradeoff: maker waits (adverse-selection risk), taker doesn't")
```

Actual output (executed before embedding):

```text
avg spread           :    2.8 bps (median 2.0)
avg ask depth <=5tix :   3276 shares

     Q  particip%  walked bps  sqrt-model bps
   200     0.0800         2.0             0.6
   800     0.3200         2.7             1.3
  3000     1.2000         3.4             2.5
  8000     3.2000         3.4             4.0

round-trip economics vs median half-spread 1.0 bps:
  passive maker earns +1.20 bps | aggressive taker pays -1.35 bps
  queue-risk tradeoff: maker waits (adverse-selection risk), taker doesn't
```

Reading the output: small orders pay essentially THE SPREAD — walked cost at Q=200 is 2.0bps versus a 1.0bp half-spread plus thin level penetration, while the square-root model underpredicts (0.6bps) because impact laws describe FLOW effects, not instant book-walking; by Q=8000 the regime flips and the model (4.0bps) overtakes the snapshot walk (3.4bps) — the static book underestimates sustained-trading costs because real execution also faces replenishment dynamics and your own footprint. That crossover IS the lesson: spread pricing governs small size, impact pricing governs large size, and honest execution modeling switches regimes explicitly. Note the walk numbers are instantaneous-snapshot lower bounds: a live 8k-share parent order worked over hours meets adverse selection and persistent impact the snapshot cannot show.

---


## How it's done in production

**Execution infrastructure.** FIX/OUCH/ITCH connectivity to each venue, colocation for latency-sensitive strategies, drop-copy reconciliation for audit. Smart order routers sweep lit venues respecting NBBO while applying venue-fee-aware routing; dark aggregators sweep non-displayed liquidity with information-leakage penalties. Clock sync (PTP) because timestamp ordering decides queue priority and regulatory best-execution defense.

**Execution algorithms.** Standard suite: VWAP/TWAP schedulers tracking volume curves; POV (percentage-of-volume) capping participation typically 5–15% (marked ~); implementation-shortfall algos solving the Almgren-Chriss frontier explicitly — front-load when alpha decays fast or risk aversion low, back-load when impact dominates; adaptive tactics layering limit orders inside the spread when flow imbalance favors patience, crossing when signals decay. Market makers run Avellaneda-Stoikov-style inventory skews: reservation quotes shift away from fair as inventory grows, effectively charging the market for warehousing risk.

**TCA (transaction cost analysis).** Every parent order decomposed into implementation shortfall components vs arrival-price benchmark: delay cost (signal-to-start), execution cost (fills vs arrival), opportunity cost (unfilled remainder drift). Markouts measure post-trade drift at +1s/+1min/+1h after YOUR fills — positive markouts after buys mean you paid too much, negative mean you captured edge. Venue analysis ranks fill quality net of fees/rebates; quarterly best-execution reviews are regulatory obligations (MiFID II in Europe; FINRA 5310 in the US).

**Backtesting realism ladder.** Best practice tiers: (1) bar-close mid fills (research only — lies by construction); (2) top-of-book snapshot walking with spread cost; (3) event-driven LOB replay with queue-position simulation; (4) calibrated agent-based simulators (ABIDES-style) with learned flow. Desks doing serious capacity work live at tier 3–4 and validate simulator fills against live TCA continuously.

## Tradeoffs & when NOT to use it

- **Passive isn't free**: saving spread+fees (~1.5bp round trip here) costs fill uncertainty, adverse selection on the fills you DO get, and signal decay while queued — aggressive posting is correct when alpha half-life is short.
- **Dark pools trade impact against information leakage**: hiding size avoids lighting up your intent, but adverse selection from informed counterparties and predatory flow-toxicity detection can make lit-market sweeps cheaper on net.
- **Square-root law is a prior, not physics**: coefficients drift across regimes/crises (Y spikes when liquidity evaporates); never extrapolate a calm-market calibration into stressed execution without widening error bars massively.
- **Toy LOB sims teach mechanics, not forecasts**: our engine's Poisson-ish flow lacks strategic interaction (Kyle's informed trader), clustering, and fat-tailed arrivals; don't calibrate production expectations to it — use it to build intuition for queue/fill/impact accounting.
- **Latency arms race has diminishing returns for non-HFT**: beyond "fast enough to not be picked off" (sub-10ms for intraday signals), chasing microseconds is a capital sink unless your P&L literally lives in the queue.
- **Don't optimize execution before validating the signal**: perfecting fills of an unprofitable strategy is polishing a losing ticket; validation gates (T24-ts-validation) come first, TCA second, both before capital.

## Interview questions

### Q1 — Decompose the bid-ask spread: where does each basis point go?
**Testing:** three-component literacy, not one-line answers.
**Answer:** Processing/order-handling costs (smallest for liquid names, scales per share), inventory-risk compensation (maker holds position until offsetting flow; scales with volatility and inventory persistence), and adverse-selection cost (expected loss when the counterparty knows more; dominates around news, in options, illiquid names). Glosten-Milgrom shows spreads exist even with zero costs and risk-neutral competition purely from informational asymmetry. Empirically the mix shifts intraday: adverse selection spikes at open/close and news, inventory terms dominate midday.
**Follow-up trap:** *"So wider spread means worse market?"* — Wider spread can reflect MORE informative trading protection, not just gouging: too-narrow spreads attract informed flow and bankrupt honest makers, then liquidity vanishes entirely (flash-crash dynamics). Optimal spread balances participation against maker survival.

### Q2 — Derive Roll's effective-spread estimator from price serial covariance.
**Testing:** classic microstructure econometrics at whiteboard depth.
**Answer:** Model observed price p_t = m_t + (s/2)·q_t with efficient price m random-walking (Δm iid) and q_t = ±1 trade direction. Then cov(Δp_t, Δp_{t−1}) = −(s/2)² because the bounce term anticorrelates adjacent changes while Δm contributes nothing serially. So ŝ = 2√(−cov̂) when covariance is negative. Fails when prices trend (positive covariance masks the bounce → ŝ undefined) or trades cluster directionally — hence later estimators (Corwin-Schultz high-low, Hasbrouck's Gibbs) exist.
**Follow-up trap:** *"Why does this matter if I have Level-2 data?"* — Historical research often doesn't (daily closes only), and cross-country/long-history studies rely on Roll precisely because tape data doesn't reach back; also effective spread ≠ quoted spread (trades inside quotes via price improvement).

### Q3 — State the square-root law, give typical coefficients (marked ~), and explain WHY sqrt scaling emerges.
**Testing:** THE impact model every desk assumes somewhere in its stack.
**Answer:** Δp ≈ Y·σ_daily·√(Q/VADV): price move grows with the square root of participation ratio Q/V times daily volatility, Y ≈ 0.4–1.0 marked ~ (Almgren et al. 2005 estimation; Bouchaud-school universality across equities/futures/FX/crypto). Why sqrt: information about the metaorder diffuses through the population of liquidity providers roughly like heat — cumulative impact grows √t during execution; executing Q over horizon T at rate Q/T gives Δp ∝ σ√(Q/V)-style scaling rather than linear-in-Q. Consequences: doubling size adds only ~41% more cost; capacity limits bite gently then suddenly.
**Follow-up trap:** *"Linear models like Kyle's contradict it?"* — They operate at different horizons: Kyle's λ is instantaneous/per-trade marginal impact under strategic informed trading; sqrt-law describes AGGREGATE metaorder footprint after diffusion and order-splitting responses. Reconciliation attempts (nonlinear propagator models) are active research; practitioners carry both tools and mark their coefficients ~.

### Q4 — Temporary versus permanent impact: define both and how they hit your P&L differently.
**Testing:** execution-P&L accounting precision.
**Answer:** Temporary impact = liquidity consumption that reverts once you stop (walking the book; others re-quote) — a pure cost of speed, avoidable by slowing down. Permanent impact = information conveyed; price ratchets and stays (your own future exits face it; so do copycats) — unavoidable by ANY schedule, only by trading less or hiding better. Almgren-Chriss objective minimizes permanent+temporary cost plus λ-weighted timing variance; IS decomposition attributes realized slippage accordingly (delay vs execution vs opportunity).
**Follow-up trap:** *"Which one does the square-root law describe?"* — Mostly the total observed excursion, dominated by permanent component for institutional-size flow; temporary governs the fine structure during execution and the post-completion partial reversion ("post-metaorder drift") that TCA markouts measure.

### Q5 — You're a maker quoting the touch. Your order fills. Good news?
**Testing:** winner's-curse intuition — separates traders from tourists.
**Answer:** Conditionally bad news on average: you were filled BECAUSE someone chose to trade against your quote — either noise (fine, you earn the spread) or informed flow (you just bought right before down-drift / sold before up-drift). Expected fill quality = unconditional spread capture MINUS adverse-selection rent; empirical markouts show passive fills underperform the prevailing mid systematically. Profitable market making therefore requires either informational neutrality of your queue (retail-heavy flow) or selection/skewing technology (cancel ahead of toxic flow, Avellaneda-Stoikov inventory skew).
**Follow-up trap:** *"Then why does anyone make passively?"* — Because the REBATE plus spread minus adverse selection stays positive against sufficiently uninformed flow, and queue priority at the right venues converts latency into expected-fill share. It's a business of surviving toxic flow, not avoiding fills.

### Q6 — Walk through payment-for-order-flow economics: who wins, who loses, and what's the current controversy?
**Testing:** market-structure awareness with numbers attached.
**Answer:** Retail broker routes orders to wholesalers (Citadel Securities, Virtu) receiving ~$0.0005–0.0017/share (marked ~, varies); wholesaler internalizes because retail flow is uninformed — near-zero adverse selection per fill — earning spread minus small price improvements required under Rule 605. Winners historically: retail investors (price improvement, zero commissions) and wholesalers; contested losers: lit-market makers facing thinner public flow and exchanges claiming price-discovery erosion. SEC's 2022–24 proposals (order-by-order auctions for individual orders, expanded 605 disclosure) aim to force competition AT the point of execution; empirical literature remains split on whether retail P&L would improve.
**Follow-up trap:** *"Is PFOF why my fills are good?"* — For small retail-sized orders, often yes: guaranteed internalization beats NBBO slightly. The distributional question is whether the wholesale margin exceeds the price improvement — different question from whether any individual fill beat the NBBO, which is exactly how the debate gets demagogued.

### Q7 — Design an execution schedule for 500k shares in a name with 2M ADV, 30% annualized vol, low alpha decay. Constraints and math.
**Testing:** Almgren-Chriss reasoning applied, not recited.
**Answer:** Participation check first: naive same-day completion = 25% of ADV — square-root impact alone ≈ Y·σ_d·√0.25 with σ_d≈30%/√252≈1.9% ⇒ ~0.9·190bp·0.5 ≈ 85bp (marked ~) — prohibitive. Spread over 3 days at ~8% daily participation: impact ≈ Y·190bp·√0.08 ≈ 54bp still heavy; 10 days at 5%: ≈ 42bp (marked ~) with rising timing/exposure risk (~2 weeks of market risk on residual). Real answer: cap participation 5–8%, run IS-algo with moderate front-loading (alpha decays slowly so back-loading is affordable), use passive-first tactics with crossing fallback, monitor real-time impact vs model, and pre-agree risk limits (max unhedged exposure, kill-switch on vol spike). Also consider alternatives: work over multiple days overnight+close auctions (~10%+ of volume prints at close with minimal impact), or trade correlated proxies while working core.
**Follow-up trap:** *"Just use VWAP?"* — VWAP tracks volume but ignores YOUR risk aversion and alpha profile; it's the right default only for benchmark-chasing mandates with no view. The interview wants the frontier logic: schedule = f(impact coefficient, timing-risk aversion, alpha decay) — say those words with numbers attached.

### Q8 — What breaks in market-making models during a flash crash, using Avellaneda-Stoikov as the baseline?
**Testing:** regime-break humility about elegant math.
**Answer:** AS assumes stationary arrival intensities and diffusive mid — a flash crash violates both: cancellations explode (liquidity vanishes in milliseconds), arrivals become one-sided (all sells), volatility jumps far outside calibration, and correlation goes to 1 across names breaking hedging assumptions. Inventory skews calibrated for calm markets quote INTO a falling knife; adverse selection hits 100% of flow. Survivors: hard inventory caps, auto-widening triggers keyed on short-horizon vol/imbalance, pull-and-requote circuit breakers — plus exchange-level halt mechanisms (LULD bands, the IEX speed bump slowing toxic-flow arbitrage).
**Follow-up trap:** *"So quants should just stand aside?"* — Standing aside IS the destabilizing equilibrium (everyone cancels → no bids); the interesting design problem is contracts/mechanisms keeping SOME liquidity posted through stress — central bank style backstops, auction states, committed market-maker obligations. Say that and you've understood the policy debates too.

### Q9 — Explain markout analysis to a PM and what a bad markout curve looks like.
**Testing:** TCA fluency — the honest mirror of execution quality.
**Answer:** After each fill, plot average price drift at +1s/+1min/+10min/+1h versus your fill price. Buys drifting DOWN after your fills = you systematically paid above subsequent value (execution bleeding edge); drifting UP = your fills captured value (either genuine alpha or lucky timing). Bad curves: monotonic adverse drift for taker flows (paying spread AND being wrong), hump-then-revert for large parents (overpaid temporary impact that decays). Markouts isolate execution from strategy P&L: the strategy can lose money with clean markouts (bad signal) but dirty markouts mean the EXECUTION desk burns money regardless of signal quality.
**Follow-up trap:** *"Markouts look great — ship bigger size?"* — Careful: great markouts on tiny size may reflect adverse-selection-free luck or slow venue; scaling changes impact regime (sqrt-law) and attracts toxicity detectors. Re-measure at target size in shadow before committing.

### Q10 — A backtest shows 4.0 Sharpe trading a mid-cap with 0.5% participation per signal, mid-price fills. Tear it down in order of damage magnitude.
**Testing:** the JD's kill-shot executed calmly and quantitatively.
**Answer:** Order of damage: (1) Impact/capacity: 0.5% per signal × frequency × sqrt-law — could be 20-60bp/trade (marked ~) depending on holding period; likely fatal alone. (2) Spread fantasy: mid fills save half-spread × 2 sides × turnover — 1-3bp×turnover, material at high frequency. (3) Adverse selection on any simulated passive fills — conditional edge lower than modeled. (4) Latency: signal-at-close-executed-at-close assumes zero drift toward your alpha. (5) THEN statistical validity: purged walk-forward? trials count? (T24-ts-validation). Rebuild with tier-3+ simulation and realistic participation caps; expect Sharpe 4.0 → sub-1.0 honestly, and decide if THAT survives.
**Follow-up trap:** *"What single number approximates total damage fastest?"* — Round-trip all-in cost (spread+fees+impact at your participation) × annual turnover vs gross returns: if costs exceed ~30% of gross, demand forensic evidence before believing the net.

### Q11 — Why do closing auctions now print 10%+ of US equity volume, and what makes auction fills special?
**Testing:** modern market-structure facts with mechanism understanding.
**Answer:** Index/passive rebalancing (ETFs tracking S&P etc.) benchmarks to closing prints, so natural flow concentrates there; auctions aggregate ALL supply/demand into ONE clearing price — no queue position, no spread crossing, minimal impact per share relative to working size through continuous hours (impact scales with urgency, and auctions remove urgency). Special properties: single-price uniform clearing (everyone gets same print), imbalance information published pre-close (M/EEO messages revealing net supply/demand), and near-zero adverse selection within the auction itself since everyone transacts at the discovered equilibrium.
**Follow-up trap:** *"Any catch?"* — Auction imbalance data leaks your interest if you participate visibly; close-price manipulation schemes (marking-the-close) attract enforcement attention; and benchmark concentration means your execution quality metric (closing price) is set by the very flow you're adding to.

### Q12 — Compare lit-exchange routing versus dark-pool aggregation for a 200k-share parent in a $60 stock, 1M ADV.
**Testing:** venue economics judgment with concrete tradeoffs.
**Answer:** Lit: immediate transparency, NBBO protection, but displaying intent invites front-running and impact precedes you; sweeping visible levels pays full depth. Dark: midpoint matching saves half-spread, hides intent, but faces toxicity (informed counterparties), minimum-fraction rules post-2016 reforms (ATSs need displayed-priced volume thresholds), and fragmentation reduces fill probability per ping. Sensible architecture: passive-dark-first for patient slices (midpoint pegs), opportunistic lit postings inside spread, reserve lit sweeps for deadline pressure — with venue-level TCA feedback adjusting the mix monthly. Numbers to anchor: half-spread ~1-2bp saved per dark fill vs maybe 5-15% lower fill rates and some probability of adverse print (marked ~).
**Follow-up trap:** *"Isn't dark volume evil for price discovery?"* — Evidence is mixed: moderate off-exchange share correlates with tighter spreads overall (competition effect), while extreme concentration risks opacity; the academic fight continues, and the honest answer acknowledges both channels instead of picking a team.

## Red flags

- Backtests filled at bar-close mid with no spread/impact/slippage modeling.
- No concept of queue position when simulating limit-order fills.
- Treating square-root law coefficients as universal constants rather than marked-~ regime parameters.
- Confusing temporary with permanent impact in execution accounting.
- Ignoring adverse selection on passive fills (winner's curse blindness).
- No TCA/markout vocabulary when discussing live performance attribution.
- Claiming capacity without a participation constraint or impact model.
- Believing displayed depth equals available liquidity.
- Dismissing microstructure as irrelevant to "strategy-level" roles.

## Cheat card

```
BOOK        two queues, price-time priority; types: LMT/MKT/IOC/
            iceberg/pegged; close auction ~= 10%+ of US volume
SPREAD      processing + inventory risk + ADVERSE SELECTION
            Roll: cov(dp_t,dp_{t-1}) ~= -(s/2)^2 -> s_eff
MAKER/TAKER maker earns spread+rebate(~+0.2bp) IF filled,
            bears queue + winner's curse; taker pays ~-0.35bp fee
            + half-spread for certainty; PFOF = retail flow sold
            b/c uninformed (low tox)
IMPACT      temp (reverts) + permanent (info); Almgren-Chriss
            frontier: speed vs timing variance
            SQRT LAW dp ~= Y*sigma_d*sqrt(Q/V), Y~0.4-1 (MARKED ~)
            double size -> +~41% cost; 25% ADV ~ 85bp @30%vol yr
BACKTEST    5 fantasies: mid fills · infinite queue · no adv sel ·
            zero latency · no self-impact => 30-80% Sharpe gone (~)
EXECUTION   IS algo = f(impact coef, risk aversion, alpha decay);
            POV cap 5-15%; TCA: delay+exec+opportunity shortfall;
            markouts +1s..+1h = honest execution mirror
VENUES      ~16 exchanges + 30-40 ATS; ~42-47% off-exchange;
            microwave ~4ms NYC-CHI vs fiber ~7ms; IEX bump 350us
GOVERNANCE  Reg NMS $0.01 tick; Rule 605/FINRA 5310 best-ex;
            MiFID II; T+1 May 2024; SEC 2022-24 auction proposals
```

## Sources

- [Kyle (1985). Continuous Auctions and Insider Trading. Econometrica 53(6)](https://www.jstor.org/stable/1913210); accessed 2026-08-23
- [Glosten, Milgrom (1985). Bid, Ask and Transaction Prices in a Specialist Market… J. Financial Economics 14](https://www.sciencedirect.com/science/article/abs/pii/0304405X85900443); accessed 2026-08-23
- [Roll (1984). A Simple Implicit Measure of the Effective Bid-Ask Spread. J. Finance 39](https://www.jstor.org/stable/2327622); accessed 2026-08-23
- [Almgren, Chriss (2000). Optimal Execution of Portfolio Transactions. Journal of Risk 3](https://www.math.nyu.edu/~almgren/papers/optliq.pdf); accessed 2026-08-23
- [Almgren et al. (2005). Direct Estimation of Equity Market Impact. Risk Magazine](https://www.math.nyu.edu/~almgren/papers/mktimpct.pdf); accessed 2026-08-23
- [Avellaneda, Stoikov (2008). High-frequency Trading in a Limit Order Book. Quantitative Finance 8(3)](https://www.tandfonline.com/doi/abs/10.1080/14697680701381228); accessed 2026-08-23
- [Tóth et al. (2011). Does Liquidity Beget Liquidity? Evidence from a True Limit Order Book (square-root law)](https://arxiv.org/abs/1103.0992); accessed 2026-08-23
- [Perold (1988). The Implementation Shortfall Paper. Journal of Portfolio Management 14(3)](https://journals.pmresearch.com/doi/10.3905/jpm.1988.409188); accessed 2026-08-23
- [SEC (2022). Equity Market Structure Proposals (Order Competition Rule, Rule 605 amendments)](https://www.sec.gov/rules/proposed/2022/34-96230.pdf); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
