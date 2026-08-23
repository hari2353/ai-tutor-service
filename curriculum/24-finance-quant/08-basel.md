# Basel I → II → III → IV: Capital, RWA, LCR/NSFR, What Each Fixed

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-risk-metrics · **Updated:** 2026-08-23
> **Module id:** `T24-basel` · **Tags:** banking, critical

## The 30-second version

Each Basel accord exists because the previous one got gamed or missed a crisis channel entirely. Basel I (1988) created THE rule — capital ≥ 8% of risk-weighted assets — but with four crude risk buckets (0/20/50/100%) biased toward OECD membership, so banks arbitraged weights while keeping risk. Basel II (2004) added risk sensitivity via internal models (IRB) and the three-pillar structure (minimum capital / supervisory review / disclosure) — then the 2008 crisis showed AAA-rated securitizations defaulting within a year and internal models procyclical enough to amplify the bust; Northern Rock died with zero wholesale-deposit insurance and no liquidity rule anywhere. Basel III (2010) fixed capital QUALITY (CET1 ≥ 4.5% + buffers to 7%+, G-SIB surcharges 1-3.5%) and finally LIQUIDITY (LCR: survive 30-day runoff with high-quality assets ≥ 100%; NSFR: one-year structural funding match ≥ 100%) plus a 3% leverage backstop. Basel IV (the December 2017 "finalization," live from January 2023, EU from 2025) attacks model variance itself: after studies showed near-identical portfolios carrying wildly different RWA across banks, regulators rebuilt the standardized approach, floored IRB parameters, and imposed the OUTPUT FLOOR — internal-model RWA can never fall below 72.5% of standardized RWA, phased in through 2028-2030 across jurisdictions — capping the entire benefit of fancy models at a 27.5% discount.

## Why this gets asked

Because banking JDs — credit risk analytics, treasury, model validation, regulatory reporting, GenAI-for-finance teams at universal banks — all assume you can read a capital adequacy report and know why numbers moved. Interviewers probe whether you understand the CAUSAL chain, not just acronyms: "why did CET1 ratios rise after 2010 even before earnings retained?" (definition changes: deductions, goodwill, DTA treatment — not just new minima). "Why does the output floor matter if your bank's IRB models are excellent?" (because floor math compares your TOTAL RWA to 72.5% of standardized — good models still hit the ceiling when their standardized shadow-RWA is fat). "What's the actual difference FRTB made?" (SA sensitivities-based method became the de facto benchmark; IMM desks face PLA tests and NMRF penalties; the floor caps model benefit). Candidates who answer these fluently signal they've sat in ALCO or validation meetings; those who recite "8% capital" reveal they've never computed an RWA density in their lives.

## Lineage

**What came before.** Pre-1988: national capital rules diverged wildly (US regulators used 10 leverage ratios variants, Japan allowed hidden reserves, UK informal). Competitive pressure — Japanese banks expanding US business on thinner capital — plus the 1974 Herstatt and 1982 Banco Ambrosiano failures pushed the G10's Basel Committee to the 1988 Accord: a single 8% capital-to-RWA floor with four sovereign/bank/corporate risk-weight buckets keyed to OECD membership. The 1996 Market Risk Amendment bolted on 99%/10-day VaR for trading books with backtesting.

**Where it stands now.** Basel II (2004) introduced three pillars: Pillar 1 minimum capital with IRB credit models (foundation: supervisory LGD; advanced: bank-estimated PD/LGD/EAD), operational-risk charges, Pillar 2 ICAAP/SREP add-ons, Pillar 3 disclosure. The crisis exposed its seams: ratings-based securitization weights collapsed (AAA CDO tranches got 20% weights then defaulted within months), IRB models were calibrated through-the-cycle but hit by point-in-time losses, and NOTHING addressed liquidity or off-balance-sheet SIVs. Basel III (2010-2017 phase-in) rebuilt quality and quantity: CET1 minima rose from 2% effective to 4.5%, plus capital conservation buffer 2.5% → 7% CET1 all-in minimum; countercyclical buffer 0-2.5%; G-SIB surcharges 1-3.5% of RWA; leverage ratio ≥ 3% unweighted backstop; LCR from 2015 phasing to 100% in 2019; NSFR final January 2014, effective 2018 (EU via CRR2, applied 2021); TLAC for G-SIBs at 16%/18% of RWA plus leverage-based TLAC 6%/6.75%. Basel IV — officially "Basel III finalization," BCBS d424 December 2017, implementation delayed by COVID to January 2023 — revised standardized credit risk (ratings/LTV-driven weights), replaced operational-risk approaches with the SMA (business indicator × internal loss multiplier), killed advanced CVA, floored IRB inputs, and added the output floor. EU transposed as CRR3 from January 2025; UK Basel 3.1 slid to January 2027; the US re-proposed a narrower endgame package after the 2023 draft drew pushback, with compliance targeted into 2028-2030 territory.

**Where it's heading.** Three live fronts. First, the output floor phase-in completes across jurisdictions between July 2028 (original BCBS schedule ending) and 2030 (EU's delayed start reaching full 72.5%), forcing IRB banks to run parallel standardized calculators forever — a permanent data/infrastructure cost. Second, non-bank financial intermediation is the acknowledged gap: NBFI leverage sat outside every accord while it grew past ~50% of global financial assets, and 2020's Treasury dash plus private-credit growth keep it atop the FSB agenda. Third, climate and crypto exposures are entering Pillar 3 disclosure (BCBS crypto standard DIS25 finalized 2024, Group 1/Group 2 exposure caps) and scenario-analysis expectations — regulation is expanding from solvency toward structural-resilience monitoring.

---

## Mental model

```
CAPITAL = equity-ish loss absorbers;  RWA = assets scaled by riskiness

              capital
RATIO = -------------------          >= minimums + buffers
         risk-weighted assets        (CET1 7% all-in typical)

THE FOUR ACCORDS AS FOUR PATCHES:
  I   (1988)  invented the ratio:      crude buckets, OECD bias
  II  (2004)  made weights smart:      internal models -> gaming
  III (2010)  added liquidity+quality: buffers, LCR/NSFR, leverage cap
  IV  (2017)  capped model variance:   floors -> IRB benefit <= 27.5%

LIQUIDITY = SURVIVING A RUN, NOT SOLVENCY:
  LCR  = HQLA / 30-day stressed net outflows       >= 100%  (short)
  NSFR = available funding / required funding      >= 100%  (1-year)

OUTPUT FLOOR LOGIC:
  RWA_used = max( RWA_internal_models , 72.5% x RWA_standardized )
```

The unifying lens: every round tightens the DEFINITION of the numerator, the ESTIMATION of the denominator, or adds a second constraint the last crisis showed was missing. Read any Basel document by asking "which of the three did this change?"

---

## How it actually works

### The capital stack and its ratios

CET1 (common shares, retained earnings minus goodwill/DTAs beyond thresholds) ≥ 4.5%; AT1 (contingent-convertibles, perpetuals with loss absorption) brings Tier 1 to 6%; Tier 2 (subordinated debt) brings total to 8%. Buffers stack ON TOP and breach consequences are graduated: dipping into the capital conservation buffer restricts dividends and bonuses via maximum-distribution tables, not license revocation. G-SIB surcharges (1.0-3.5% of RWA, from a scorecard of size/interconnectedness/substitutability/complexity/cross-border) sit above that — JPMorgan-type US GSIBs face effective CET1 requirements in the low teens once stress-capital-buffer regimes apply.

### Risk-weighted assets — three engines per book

**Standardized approach (SA):** external ratings or prescriptive grids. Revised SA corporate: AAA to AA− 20%, A+ to A− 50%, BBB+ to BBB− 75%, BB+ to BB− 100%, below BB− 150%, unrated 100%. Banks under ECRA: 20/30/50/100/150%. Sovereigns: AAA-AA 0%, A 20%, BBB 50%, BB-B 100%, junkier 150%. Retail: flat 75%. Residential mortgages: LTV grids (roughly 20-50% at low LTV up to 100%+/105% caps at high LTV). Past-due: 150% net of provisions. Equity holdings in funds/institutions: 250%. Commitments get credit-conversion factors (unconditionally cancellable: 10%/40% depending on framework version).

**IRB:** bank models estimate PD/LGD/EAD/M; capital formula maps them to unexpected-loss capital at 99.9% over one year through the asymptotic single risk factor (ASRF) model — Vasicek's granularity-adjusted portfolio theory. Foundation IRB fixes LGD/EAD supervisory; advanced estimates everything. Basel IV floors inputs (PD floored around 5bp for mortgages/transactor retail, 25bp for other retail; LGD floors by collateral class) because pre-crisis IRB produced absurd parameters: some banks ran corporate PDs near 0.03%.

**Output floor (Basel IV's teeth):** total RWA used in ratios = max(IRB/market-model RWA, 72.5% × standardized RWA including CVA). Phase-in raises the floor percentage 5 points yearly: BCBS original schedule 50% (2023) → 72.5% (2028); EU CRR3 started 2025 at 50% → 72.5% in 2030; US re-proposal contemplates completion ~July 2028. Strategic consequence: your standardized shadow-book becomes as important as your modeled book — data quality on collateral/LTV drives capital even for model banks.

### FRTB delta: SA vs IMM for trading books

The revised market-risk SA is now sensitivities-based: delta (linear sensitivity per bucket), vega (option vol sensitivity), curvature (convexity shocks up/down), each aggregated across risk classes with prescribed correlations run at HIGH/MEDIUM/LOW settings and averaged (weighted toward medium, bounded between 50%-of-average and 100%). Plus Default Risk Charge (jump-to-default, issuer-level) and Residual Risk Add-On (exotic exposures). IMM remains available desk-by-desk: ES 97.5% with liquidity horizons 10-120 days, eligibility gated by backtesting green zone and PLA pass (<10% unresolved trades). The practical delta: SA capital typically runs materially higher than IMM for liquid flow desks (often estimated 1.3-2x), but NMRF penalties can flip that for exotic books — and since January 2023-era frameworks the floor means even perfect internal models keep at most a 27.5% discount to SA across the whole bank. Result: mid-size banks abandoned IMM entirely (SA-only), while global dealers maintain both engines and optimize desk-by-desk.

### Liquidity: LCR and NSFR

**LCR (30-day survival):** HQLA / net stressed outflows ≥ 100%. Outflow assumptions: stable retail deposits run off 3-5%, less-stable 10%, operational wholesale deposits 25%, non-operational wholesale 40%, committed credit lines assumed 10% drawn, secured-funding haircuts by collateral. HQLA tiers: Level 1 (cash, central-bank reserves, 0%-RW sovereigns — no haircut, uncapped), Level 2A (15% haircut; ≤ 40% of total HQLA), Level 2B (25-50% haircut; ≤ 15%). Born from Northern Rock/Lehman runs where solvent institutions died of outflows.

**NSFR (one-year structural):** Available Stable Funding / Required Stable Funding ≥ 100%. ASF factors reward capital (100%), retail/small-business deposits (90-95%), wholesale < 6 months (0-50%); RSF factors charge assets by liquidity (cash 0%, Level 1 5%, Level 2A 15%, short-term consumer loans ~50%, long-dated loans/mortgages ~65-85%, derivatives by residual maturity/collateral). Design intent: kill the borrow-short-lend-long maturity mismatch at scale — which is why post-2018 bank profitability arguments shifted toward deposit franchises as the core asset.

---

## Build it from scratch

Standardized RWA calculator on a mini balance sheet, with output-floor logic:

```python
import numpy as np

# (asset, EAD $mm, class) -- weights follow Basel III finalization SA
BOOK = [
    ("US Treasuries",        500, "sovereign_AA"),
    ("Bank bonds A-rated",   200, "bank_A"),
    ("Corporate unrated",    300, "corp_unrated"),
    ("Corp bonds BBB+",      150, "corp_BBB"),
    ("Credit-card retail",   250, "retail"),
    ("Resi mortgages LTV70", 800, "mortgage"),
    ("CRE loans",            400, "cre"),
    ("Past-due loan",         50, "past_due"),
    ("Equity stake",          30, "equity"),
]
RW = {"sovereign_AA": 0.00, "bank_A": 0.30, "corp_unrated": 1.00,
      "corp_BBB": 0.75, "retail": 0.75, "mortgage": 0.35,
      "cre": 1.00, "past_due": 1.50, "equity": 2.50}

def rwa_standardized(book=BOOK):
    rows = [(a, ead, RW[c], ead*RW[c]) for a, ead, c in book]
    return rows, sum(r[3] for r in rows)

# pretend the bank's IRB engines produced modeled RWA:
rwa_irb = 1100.0

rows, rwa_sa = rwa_standardized()
floor_pct = 0.725                              # full phase-in value
floor = floor_pct * rwa_sa                     # EU reaches this in 2030;
                                               # BCBS original schedule 2028
used = max(rwa_irb, floor)
density_sa = rwa_sa / sum(e for _, e, _ in BOOK)

cet1, tier1, total_cap = 180.0, 200.0, 220.0   # $mm
print(f"{'asset':24} {'EAD':>6} {'RW':>5} {'RWA':>7}")
for a, ead, rw, r in rows:
    print(f"{a:24} {ead:6.0f} {rw:5.0%} {r:7.1f}")
print(f"\nRWA_SA={rwa_sa:.0f}  density={density_sa:.1%}")
print(f"IRB RWA={rwa_irb:.0f} -> floor {floor_pct:.1%} x SA = {floor:.1f}"
      f" -> used {used:.1f} ({'FLOOR BINDS' if floor > rwa_irb else 'models bind'})")
for nm, cap, req in [("CET1", cet1, .07), ("Tier1", tier1, .085), ("Total", total_cap, .105)]:
    ratio = cap / used
    headroom = cap - req * used
    print(f"{nm:6} {ratio:6.2%} vs req {req:.1%}  surplus ${headroom:6.1f}mm")

# quick LCR check
l1, l2a, net_out = 400.0, 100.0, 300.0         # caps: L2 <= 40% of HQLA
hqla = l1 + min(l2a, 0.40 * (l1 + l2a))
print(f"LCR = {hqla:.0f}/{net_out:.0f} = {hqla/net_out:.0%}  "
      f"({'pass' if hqla/net_out >= 1 else 'FAIL'})")
```

Reading it: the mortgage sleeve (35% weight) contributes nearly a fifth of RWA despite being the biggest asset; the equity stake at 250% shows how punitive non-standard exposures are; with IRB RWA of 1,100 against an SA shadow of 1,530, the 72.5% floor (~1,109) binds — your "excellent" internal models buy almost nothing here. Cut IRB RWA to 900 and the floor still forces 1,109 into every ratio.

---

## How it's done in production

**Regulatory reporting is an industrial pipeline:** daily capital calculators (SA + IRB + market + op risk) feeding COREP/FR Y-9C/FFIEC filings monthly-quarterly, with reconciliation between finance ledger, risk engines, and the filing layer — mismatches here are audit findings. Large banks run standardized and internal engines in parallel permanently because the floor requires the SA shadow-book anyway; data lineage from origination systems to collateral fields is the actual bottleneck.

**Strategic responses banks actually take:** optimizing collateral documentation (LTV grid points move RWA), managing IRB model churn under floor constraints (a model improvement that helps modeled RWA may not help once floored), TLAC issuance calendars, deposit-franchise management for LCR/NSFR (pricing non-operational wholesale away), and G-SIB scorecard management — banks have visibly shrunk derivatives books near reporting dates to stay under surcharge thresholds (the "scorecard games" regulators publicly grumble about).

**Validation/audit angle:** RWA engines ARE models under SR 11-7-style regimes (see T24-mrm); floor logic, EAD calculation, CCF assumptions all get independent validation. FRTB desk approvals require demonstrating PLA compliance continuously — risk technology teams monitor attribution ratios daily like SLOs.

## Tradeoffs & when NOT to use it

- **Basel ratios are not risk management**: they're regulatory minima. Managing to 8% would be absurd when stress tests imply 12%+ effective requirements; conversely hoarding capital destroys ROE — the whole game is buffer optimization.
- **The floor punishes genuinely better models**: a bank whose IRB truly discriminates risk still eats 72.5% of standardized conservatism. Don't sell "model improvement" as capital benefit without checking floor arithmetic.
- **RWA density comparisons across banks became meaningless** in mixed regimes (US delay vs EU live): identical portfolios report different densities by jurisdiction. Use SA-basis comparisons.
- **LCR/NSFR optimize liquidity metrics, not survival**: HQLA concentration in sovereigns creates its own rate-risk exposure (SVB's HTM book was full of Level 1 assets — liquid on paper, fatal to capital when marked).
- **Don't extrapolate US/EU timelines**: as of 2026 the regimes diverge (EU CRR3 live, UK Jan 2027, US endgame re-proposal pending) — cross-border capital planning must run jurisdiction-specific calculators.

## Interview questions

### Q1 — Walk through what Basel I fixed and its two biggest flaws.
**Testing:** causal history, not date recital.
**Answer:** Fixed: divergent national capital standards — one global 8% RWA ratio, leveling the competitive field after Herstatt/Ambrosiano. Flaws: (1) crude buckets keyed to OECD membership lent Mexico and Korea 0% weights while rated corporates paid 100%; (2) no market risk until the 1996 amendment, so trading books grew untaxed. Both flaws drove arbitrage: banks stuffed into thin-weighted risky assets.
**Follow-up trap:** *"So was Basel I useless?"* — No — creating THE common metric mattered more than its calibration; every later round edits the same ratio. But yes, its weights were gameable within a decade.

### Q2 — What are the three pillars of Basel II and which failed hardest in 2008?
**Testing:** framework structure + crisis literacy.
**Answer:** Pillar 1: minimum capital (credit via standardized/IRB, market risk, operational risk). Pillar 2: supervisory review — ICAAP/SREP add-ons for risks Pillar 1 misses. Pillar 3: market discipline through disclosure. Failure ranking in 2008: Pillar 1's IRB/ratings machinery (AAA securitizations at low weights defaulting within a year; procyclical models), then Pillar 2 (supervisors saw SIVs and did nothing binding), while Pillar 3 disclosure was nearly irrelevant — nobody read the reports that mattered.
**Follow-up trap:** *"Was Basel II the cause of the crisis?"* — No — it was barely implemented (US never applied it to major banks; EU implemented just as the crisis hit). The securitization machine predated it. It codified the era's trust in models/ratings rather than causing the excess.

### Q3 — Why does the output floor cap internal-model benefit at exactly 27.5%?
**Testing:** floor arithmetic.
**Answer:** Floor = 72.5% × total standardized RWA; used RWA = max(modeled, floor). Best case, modeled RWA reaches the floor — you save 27.5% versus pure-SA capital, never more. The percentage phases in 50% → 72.5% over years (BCBS schedule ending 2028; EU reaching full effect 2030), so during phase-in the cap on benefit is even tighter.
**Follow-up trap:** *"Does the floor apply desk-by-desk?"* — No — it applies to TOTAL bank RWA including CVA. A bank can still win below-floor outcomes on some portfolios if others' modeled RWA sits above their floors; optimization is portfolio-level.

### Q4 — LCR vs NSFR: horizons, formulas, what each prevents.
**Testing:** liquidity mechanics fluency.
**Answer:** LCR: HQLA / 30-day stressed net outflows ≥ 100% — prevents Northern-Rock/Lehman-style runs killing solvent banks; outflow rates by deposit stickiness (stable retail 3-5%, non-operational wholesale 40%), HQLA tiers with caps (Level 2 ≤ 40%, Level 2B ≤ 15%). NSFR: available/required stable funding ≥ 100% over one year — structurally penalizes short-term wholesale funding of long assets (ASF 0-50% for <6-month wholesale vs RSF ~85% on long loans).
**Follow-up trap:** *"Can a bank pass both and still die in a run?"* — Yes — SVB passed its categories while uninsured deposits (~90%+ of its base) ran in hours; metrics assume 30-day runoff rates calibrated to history, not Twitter-speed bank runs. Hence post-2023 proposals for haircuts on HTM marks and longer runoff assumptions for digital-era deposit behavior.

### Q5 — Explain FRTB SA vs IMM to a CFO deciding where to spend technology budget.
**Testing:** regulatory economics reasoning.
**Answer:** SA is mandatory everywhere (sensitivities-based delta/vega/curvature + DRC + RRAO); IMM is optional per-desk subject to backtesting green zone, PLA pass (<10% unresolved), and NMRF exposure. IMM typically produces lower capital on liquid flow desks but requires heavy infrastructure (full-revaluation grids, data lineage); NMRF penalties can make exotic books cheaper under SA. The floor caps any bank-wide benefit at 27.5%. Rational spend: SA excellence first (it's unavoidable and now the benchmark), IMM only where desk P&L justifies it.
**Follow-up trap:** *"Why not IMM everywhere since it's 'risk-sensitive'?"* — Approval is desk-by-desk and revocable; PLA failures kick desks to SA mid-cycle; and under the floor the prize shrank enough that many regional banks dropped IMM entirely.

### Q6 — A model improvement cuts your mortgage LGD estimates materially. Does capital fall? Walk through it.
**Testing:** floor-aware thinking.
**Answer:** Three gates: (1) input floors — Basel IV floored LGDs by collateral class, so cuts below floors don't count; (2) validation must approve the new LGD (SR 11-7 process, months); (3) output floor arithmetic — if modeled RWA stays above 72.5%-of-SA anyway, zero capital benefit materializes despite better economics. Post-Basel IV, model improvements increasingly buy pricing/limiting benefits rather than capital relief.
**Follow-up trap:** *"So should banks stop investing in credit models?"* — No — models drive provisioning (IFRS 9/CECL), pricing, and limit-setting even when capital-neutral; but the BUSINESS CASE changed from capital optimization to decision quality.

### Q7 — Why did regulators choose 72.5% for the floor rather than something cleaner like 80% or 100%?
**Testing:** understanding the calibration politics/economics.
**Answer:** BCBS calibrated so aggregate G-SIB capital requirements stayed broadly neutral overall: modeled books would lose part of their discount while revised-SA conservatism rose — net capital roughly unchanged (+0-2% aggregate per impact studies) but redistributed toward banks with aggressive models and complex books. 100% would have abolished internal models' capital role entirely (politically fatal to Europe's universal banks); 50% would have left most dispersion intact.
**Follow-up trap:** *"Did it actually reduce RWA variance?"* — Yes directionally — dispersion studies drove the reform because near-identical portfolios showed ~2x RWA differences across banks; the floor plus revised SA compresses that, though jurisdictional timing gaps re-created variance across regions.

### Q8 — Compute: assets $2,000mm, CET1 $150mm, all corporate unrated. Ratio? Now half converts to retail.
**Testing:** mental RWA math.
**Answer:** All-unrated-corporate: RWA = 2,000 × 100% = 2,000; CET1 ratio = 7.5%. Half retail: RWA = 1,000×100% + 1,000×75% = 1,750; ratio = 8.57%. Same assets, same equity — the mix moved the ratio >100bp. This IS why loan-book composition strategy is capital strategy.
**Follow-up trap:** *"Now apply the floor if this bank also runs IRB showing RWA 1,200."* — Floor = 0.725×1,750 = 1,269 > 1,200 → use 1,269; ratio = 11.8%. The floor just ate the model's entire advantage.

### Q9 — What did Basel III change about capital QUALITY specifically? Why did ratios jump without new earnings?
**Testing:** definition-vs-quantity distinction.
**Answer:** Pre-2010 Tier 1 included hybrids (trust preferreds, innovation instruments) that failed to absorb losses in the crisis; Basel III redefined CET1 with strict deductions (goodwill, intangibles, DTAs beyond thresholds), phased out AT1 grandfathering, and added buffers. Ratios jumped partly from redefinition: the same dollar of capital counted differently. US large banks went further via stress-test-derived SCB requirements.
**Follow-up trap:** *"Is AT1 still risky then?"* — Credit Suisse March 2023: CHF 16B of AT1 written down to zero while equity holders got something in the UBS rescue — reversing the expected seniority order and freezing the AT1 market for weeks. The instrument's contractual triggers matter more than its label.

### Q10 — SVB 2023: which Basel-era gap does it expose?
**Testing:** connecting frameworks to real failures.
**Answer:** Multiple gaps at once: it was exempt from LCR/NSFR (Category IV tailoring under the 2019 US rules), held massive HTM sovereign books whose unrealized losses (~$15B+) sat outside regulatory capital marks, and ran ~90% uninsured deposits that ran in hours — faster than any 30-day runoff assumption. Basel III's liquidity framework assumed deposit stickiness calibrated to pre-social-media history. Post-mortems (Fed's Barr review, April 2023) recommend applying full standards to Category IV banks and reconsidering AFS/HTM treatment.
**Follow-up trap:** *"Would Basel compliance have saved SVB?"* — Probably not mechanically — but NSFR would have penalized its funding structure, and mark-to-market or interest-rate-risk Pillar 2 scrutiny would have surfaced the duration hole earlier. The failure was supervision + calibration, not just exemption.

### Q11 — What is TLAC and how does it interact with Basel III capital?
**Testing:** resolution-regime literacy (common VP-level question).
**Answer:** Total Loss-Absorbing Capacity: G-SIBs must hold eligible debt (senior bonds meeting terms) ≥ 16%/18% of RWA (plus leverage-based 6%/6.75%) OUTSIDE the capital stack so a failing bank can be recapitalized via bail-in without taxpayer injection. Interaction: MREL in EU overlaps; TLAC sits senior to equity but absorbs losses before operating-customer senior claims. Since 2019 all G-SIB holdings companies comply; the practical effect is a second, larger "capital-like" requirement funded by debt issuance.
**Follow-up trap:** *"Why not just raise equity instead?"* — Debt is cheaper (tax-deductible interest, no dilution); TLAC gets loss-absorbency while preserving ROE — it's the political compromise between bondholder bail-ins and equity doubling.

### Q12 — Rank the four accords by real-world impact and defend the ranking.
**Testing:** synthesis judgment.
**Answer:** Defensible ranking: III > I > IV > II. III changed behavior most visibly — liquidity stacks, buffer regimes, G-SIB surcharges reshaped funding markets permanently. I created the global metric itself. IV is mid-flight (phase-ins complete 2028-2030) — floors already bind some banks' strategies, but full impact is pending. II is last: barely implemented where it mattered, discredited by 2008, though its three-pillar architecture survived as scaffolding for everything since.
**Follow-up trap:** *"Anything they ALL missed?"* — NBFI/shadow-bank leverage (the FSB's current obsession), climate systemic risk, and cyber/operational resilience beyond capital — each accord patched the LAST war.

## Red flags

- Reciting "8% minimum" as if buffers/surcharges don't exist (effective CET1 needs are low-teens for GSIBs).
- No idea what the output floor does to internal-model benefits.
- Confusing LCR (30-day survival) with NSFR (structural one-year match).
- Claiming Basel II caused 2008 (it wasn't even implemented in the US).
- Ignoring jurisdiction divergence (EU 2025 vs UK 2027 vs US pending) in cross-border answers.
- Treating AT1 as safe equity-like paper post-Credit-Suisse write-down.
- Believing HQLA composition is risk-free after watching rate-driven unrealized losses kill SVB.

## Cheat card

```
RATIO     capital / RWA   CET1>=4.5% +CCb2.5% ->7%; T1 6+2.5; Total 8+2.5
          + CCyB 0-2.5% + GSIB 1-3.5%; leverage backstop >=3% unweighted
RATIOS    CET1 stack: common+retained - goodwill/DTA deductions;
          AT1 CoCos absorb via conversion/write-down (CS: CHF16B->0 '23)
SA RWs    corp AAA-AA 20/A 50/BBB 75/BB-B 100/<BB 150/unrated 100
          banks ECRA 20/30/50/100/150 · retail 75 · resi mortgage
          LTV-grid ~20-105 · past-due 150 · equity 250
IRB       PD/LGD/EAD models -> ASRF 99.9% UL capital; Basel IV input
          floors (PD ~5bp mortgage/25bp other retail; LGD floors)
OUTPUT    RWA_used = max(model_RWA, 72.5% x SA_RWA)
FLOOR     BCBS: 50%'23 ->72.5%'28 (+5pp/yr); EU CRR3 '25 ->2030;
          US re-proposal ~'28 => model benefit hard-capped 27.5%
FRTB      SA: delta/vega/curvature buckets + DRC + RRAO,
          corr scenarios hi/med/low averaged
          IMM: ES97.5%, horizons 10-120d, PLA unresolved<10%, NMRF
          delta: SA ~1.3-2x IMM on flow desks; floor caps total edge
LIQUID    LCR = HQLA/net 30d outflows >=100% (retail stable 3-5% run,
          wholesale non-op 40%; L1 uncapped, L2<=40%, L2B<=15%)
          NSFR = ASF/RSF >=100% 1yr (wholesale<6m ASF 0-50%;
          long loans RSF ~85%)
TLAC      GSIB debt >=16%/18% RWA (+6%/6.75% lev) bail-in fodder
LESSON    I: common metric · II: smart weights -> gaming ·
          III: quality+liquidity · IV: variance control via floors
          gap: NBFI, climate, crypto (DIS25 caps Group 2)
```

## Sources

- [Basel Committee (1988). International Convergence of Capital Measurement](https://www.bis.org/publ/bcbs04a.htm); accessed 2026-08-23
- [Basel Committee (2017). Basel III: Finalising post-crisis reforms (d424)](https://www.bis.org/bcbs/publ/d424.htm); accessed 2026-08-23
- [Basel Framework full text (CRE/CVA/MAR/LCR/NSFR chapters)](https://www.bis.org/basel_framework/); accessed 2026-08-23
- [Basel Committee (2019). Minimum capital requirements for market risk](https://www.bis.org/bcbs/publ/d457.htm); accessed 2026-08-23
- [EBA. CRR3 implementation and output floor phase-in schedule](https://www.eba.europa.eu/basel-iii-framework-eu); accessed 2026-08-23
- [Federal Reserve (2023). Review of the Federal Reserve's Supervision of Silicon Valley Bank](https://www.federalreserve.gov/publications/review-of-the-federal-reserves-supervision-of-silicon-valley-bank.htm); accessed 2026-08-23
- [Financial Stability Board. 2024 TLAC term sheet and monitoring reports](https://www.fsb.org/work-of-the-fsb/market-and-institutional-resilience/post-2008-financial-crisis-reforms/ending-too-big-to-fail/total-loss-absorbing-capacitytlac/); accessed 2026-08-23
- [Basel Committee (2013). Regulatory consistency assessment programme (RCAP) — RWA dispersion analysis](https://www.bis.org/publ/bcbs256.htm); accessed 2026-08-23

## Changelog

- 2026-08-23 — created






