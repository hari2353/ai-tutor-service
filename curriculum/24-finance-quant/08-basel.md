# Basel I → II → III → IV: Capital, RWA, the Output Floor, LCR/NSFR, and What Each Fixed

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-risk-metrics (VaR/ES feed directly into market-risk RWA)
> **Module id:** `T24-basel` · **Tags:** banking, critical
> **Lab:** `labs/python/08-basel/`

## The 30-second version

Basel is a sequence of internationally agreed bank-capital-adequacy fixes, each one a direct response to a failure the previous version didn't catch: Basel I (1988) gave the world its first common 8% capital-to-risk-weighted-assets minimum but used crude 0/20/50/100% risk-weight buckets that treated an investment-grade corporate loan the same as a near-default one; Basel II (2004) fixed that with genuinely risk-sensitive weights and internal-ratings-based models but was finalized right before 2008 with capital that was both too low in quantity and too low in quality, and zero liquidity requirements at all; Basel III (2010-2011) responded directly by defining Common Equity Tier 1 (CET1) as the new highest-quality capital layer (minimum 4.5% of RWA, 6% for Tier 1, 8% total, plus a 2.5% capital conservation buffer that makes the effective CET1 floor 7.0% for every bank), adding a non-risk-weighted 3% leverage-ratio backstop, and — for the first time ever — quantitative liquidity standards (LCR for 30-day survival, NSFR for 1-year structural funding stability); the December 2017 "Basel III finalization," widely nicknamed **Basel IV** in industry usage, then fixed a documented problem where banks using internal models on similar portfolios produced wildly different RWA figures, via the **output floor**: internal-model RWA can never be less than **72.5%** of the standardized-approach figure. As of August 2026, the US is mid-implementation of this last piece: the Fed, OCC, and FDIC jointly re-proposed the US "Basel III Endgame" on March 19, 2026 under Vice Chair for Supervision Michelle Bowman, explicitly **capital-neutral** (an estimated $87.7B in system-wide CET1 relief) rather than the original 2023 proposal's roughly +19% capital hike, with comments due mid-2026, finalization expected Q4 2026, and phase-in starting 2027. For an engineering org, Basel isn't a formula you implement once — it's a permanent, multi-year data-lineage and calculation-engine program (BCBS 239's risk-data-aggregation principles, RWA engines that must reconcile exactly against the general ledger, and annual CCAR/DFAST stress-test submissions) that consumes serious platform-engineering headcount at any bank above the regulatory size thresholds.

## Why this gets asked

An interviewer at a bank or fintech asks about Basel to check whether you understand that "regulatory capital" isn't a compliance checkbox bolted onto the business — it's a binding constraint that shapes what products get built, how aggressively a balance sheet can grow, and how much engineering investment goes into risk-data infrastructure versus feature work, and someone who's actually sat near a capital-planning or regulatory-reporting function has personally lived through a quarter where an RWA reconciliation break, a late CCAR submission, or a liquidity-ratio breach became the most urgent problem in the building. The real test is whether you can connect the *numbers* (4.5%/6%/8%, 72.5%, LCR/NSFR ≥100%) to the *specific failure each rule was written to prevent*, and whether you understand Basel as an evolving, still-unfinished framework in 2026 rather than a fixed historical fact — a candidate who doesn't know the US Endgame is being actively re-proposed right now reads as someone who hasn't kept current with the industry they're interviewing into.

---

## Lineage: past → present → future

**What came before.** Before Basel I (1988), no international capital-adequacy standard existed at all — each country's regulators set their own requirements independently, and by the early 1980s this had become a genuine competitive problem: undercapitalized banks (Japanese banks in particular were widely cited as operating with materially thinner capital cushions than US and European peers) could win international business on price precisely because they weren't holding as much loss-absorbing capital, while the Latin American sovereign debt crisis of the early 1980s simultaneously exposed how thin many large international banks' capital actually was relative to the credit risk sitting on their books. The Basel Committee on Banking Supervision (BCBS, established 1974 by the G10 central bank governors in the wake of the Herstatt Bank collapse, which exposed cross-border settlement risk) produced the 1988 Capital Accord as the direct fix: the first internationally agreed minimum, 8% capital-to-risk-weighted-assets, computed using a small number of crude risk-weight buckets (0% sovereigns, 20% banks, 50% residential mortgages, 100% corporate loans) that made no distinction within a bucket — a loan to a blue-chip investment-grade corporate and a loan to a borrower near default carried an identical 100% risk weight.

**Where it stands now.** Basel II (finalized 2004) fixed that crudeness directly, building a genuinely risk-sensitive framework around three pillars — Pillar 1 (minimum capital, now allowing banks to use their own internal ratings-based, IRB, probability-of-default/loss-given-default models subject to supervisory approval, alongside a more granular standardized approach), Pillar 2 (supervisory review of a bank's own internal capital adequacy assessment), Pillar 3 (public disclosure requirements meant to let market discipline reinforce supervision) — but its implementation, completed just before the 2007-2008 financial crisis, left capital simultaneously too low in *quantity* and too low in *quality* (much of what legally counted as capital, hybrid instruments in particular, turned out not to genuinely absorb losses in a real crisis) and imposed zero standardized liquidity requirements whatsoever, a gap the 2007-2008 liquidity freeze exposed brutally — Northern Rock, Bear Stearns, and Lehman Brothers each failed with liquidity, not pure solvency, as the immediate proximate trigger. Basel III (agreed 2010-2011, phased in through the following decade) targeted both failures head-on: it defined Common Equity Tier 1 (CET1) as a new, strictly-defined highest-quality capital category, layered capital conservation and countercyclical buffers on top of the bare regulatory minimums, added a non-risk-weighted leverage ratio specifically as a backstop against internal-model gaming, and introduced quantitative liquidity standards — the Liquidity Coverage Ratio (LCR) and Net Stable Funding Ratio (NSFR) — for the first time in Basel's history. The subsequent "Basel III finalization" (BCBS, December 2017, widely nicknamed **Basel IV** in industry and press usage though the Committee itself never uses that term) fixed a different, more subtle problem that Basel II's internal-models approach had itself created: BCBS and EBA studies documented that banks running internal models against economically near-identical portfolios produced dramatically different RWA outputs, undermining the comparability of capital ratios across banks — the fix was the **output floor**, capping the capital relief any bank can extract from internal models at no less than 72.5% of what the standardized approach would produce for the same book. As of August 2026, this last package remains only partially implemented globally: the EU and UK are further along in phasing in the output floor and revised standardized approaches, while the US is mid-re-proposal — the Federal Reserve, OCC, and FDIC jointly issued a **capital-neutral** re-proposal of the US "Basel III Endgame" on March 19, 2026 (Vice Chair for Supervision Michelle Bowman's framework), explicitly abandoning the original 2023 proposal's roughly +19% aggregate large-bank capital increase in favor of an estimated **$87.7 billion in net system-wide CET1 relief**, alongside a separate, less burdensome capital track for regional and smaller banks and a revised G-SIB surcharge methodology; the 90-day comment period runs through mid-2026, with finalization expected in Q4 2026 and phase-in beginning in 2027.

**Where it's heading.** Given the US re-proposal was deliberately designed to be broadly capital-neutral rather than capital-increasing, confidence is high that the multi-year political fight over the *size* of the US capital increase is effectively resolved, with the remaining work being implementation detail — finalizing the exact standardized-approach mechanics for credit, market (FRTB), operational, and counterparty-credit (SA-CCR) risk, and the output floor's precise phase-in schedule — rather than another fundamental renegotiation of capital levels. With moderate confidence, expect continued tightening or extension of liquidity and interest-rate-risk standards (LCR/NSFR, and interest-rate risk in the banking book, IRRBB) given that the March 2023 US regional-bank failures (Silicon Valley Bank, Signature Bank) exposed real gaps in how uninsured-deposit run risk and available-for-sale securities losses interact with existing capital and liquidity rules for banks below the very largest size tier — that specific lesson is still being actively digested into rulemaking as of 2026 and remains genuinely unresolved, unlike the large-bank capital-level question.

---

## Mental model

```
CAPITAL ADEQUACY RATIO = CAPITAL (numerator) / RISK-WEIGHTED ASSETS (denominator)

    CAPITAL STACK                                    RWA
  ___________________________              ___________________________
 | Tier 2 (subordinated debt) |            | Credit risk RWA          |
 |___________________________| Total Cap   | (loans, weighted by      |
 | Additional Tier 1 (AT1,    |  >= 8.0%    |  riskiness: 0%-150%+,    |
 |  contingent convertibles)  |             |  standardized or IRB)    |
 |___________________________| Tier 1      |___________________________|
 | Common Equity Tier 1(CET1) |  >= 6.0%    | Market risk RWA          |
 | common stock + retained    |             | (trading book, FRTB      |
 | earnings -- HIGHEST quality|  >= 4.5%    |  97.5% ES -- see prior   |
 |_____________________________|            |  module)                 |
                                             |___________________________|
  + Capital Conservation Buffer (+2.5% CET1)| Operational risk RWA     |
    -> effective CET1 floor = 7.0% for ALL  | (standardized approach,  |
  + Countercyclical Buffer (0-2.5%, by      |  AMA retired under Basel |
    national regulator, credit-cycle driven)|  III finalization)       |
  + G-SIB surcharge (1.0-3.5% CET1, for      ___________________________
    globally systemic banks only)

  OUTPUT FLOOR: internal-model RWA >= 72.5% x standardized-approach RWA (firm-wide, aggregate)
  LEVERAGE RATIO (backstop, ignores risk weights): Tier 1 / Total Exposure >= 3%

LIQUIDITY (separate regime entirely, added by Basel III, no Basel I/II equivalent):
  LCR  = High-Quality Liquid Assets / Net Cash Outflows over 30-day stress   >= 100%
  NSFR = Available Stable Funding / Required Stable Funding, 1-year horizon >= 100%
```

The one-line mental model: **every Basel iteration exists because the previous one left a specific, name-able hole — crude risk weights, then too little/low-quality capital plus zero liquidity rules, then RWA variability across banks — and the current 2026 US rulemaking cycle is the industry finishing the last of those three fixes.**

---

## How it actually works

### The capital ratios, and what "risk-weighted assets" actually means

The three binding capital ratios are all `Capital / RWA`, with three numerator definitions of increasing breadth: **CET1** (common stock, retained earnings, and other comprehensive income — the highest-quality, permanently loss-absorbing capital, minimum **4.5%** of RWA), **Tier 1** (CET1 plus Additional Tier 1 instruments like contingent convertible bonds that convert to equity or get written down under stress, minimum **6.0%**), and **Total Capital** (Tier 1 plus Tier 2 subordinated debt, minimum **8.0%**). RWA itself is not the bank's total assets — it's total assets (and off-balance-sheet exposures, converted via credit-conversion factors) each multiplied by a risk weight reflecting how likely that specific exposure is to generate a loss: a cash position gets roughly 0% weight, a residential mortgage might get 35-50%, an unrated corporate loan commonly gets 100%, a below-investment-grade exposure can exceed 100%. **Two ways to compute the weight**: the **standardized approach** (SA) uses regulator-prescribed weights, often keyed off external credit ratings or standardized borrower categories; the **internal ratings-based approach** (IRB, available only to banks with supervisory approval) uses the bank's own modeled probability of default (PD), loss given default (LGD), and exposure at default (EAD) to compute a continuous, bank-specific weight rather than a fixed bucket.

On top of the bare 4.5%/6%/8% minimums, every bank must additionally hold a **capital conservation buffer** of 2.5% of RWA in CET1 — not a separate hard minimum, but a buffer whose erosion triggers automatically graduated restrictions on capital distributions (dividends, buybacks, discretionary bonus payouts), scaled to how deep into the buffer the bank has fallen, without requiring an abrupt regulatory seizure. That buffer makes the **effective CET1 floor 7.0%** for every bank in practice. A **countercyclical buffer** (0-2.5% of RWA, set by national regulators based on domestic credit growth) can be layered on top during credit booms, released during downturns. Banks designated **Globally Systemically Important (G-SIBs)** carry an additional **G-SIB surcharge** (roughly 1.0-3.5% of RWA in CET1, bucketed) based on a composite score across five categories — size, interconnectedness, cross-jurisdictional activity, substitutability, and complexity — deliberately not based on asset size alone, because systemic danger comes as much from how deeply interconnected and how hard-to-unwind a firm is as from its raw balance-sheet size.

### The output floor: fixing RWA variability, not adding a new risk category

Studies by the BCBS and the European Banking Authority, conducted through the 2010s, found that banks running internal models against economically near-identical loan portfolios produced RWA figures that differed by very large margins purely due to modeling choices, not underlying risk differences — undermining the entire premise that a published capital ratio meant the same thing across banks. The December 2017 Basel III finalization's fix: the **output floor** requires that firm-wide RWA computed via internal models can never fall below **72.5%** of what the standardized approach would compute for the same aggregate book. This is enforced at the **aggregate firm level, not per-exposure** — a bank can still have internal-model RWA well below standardized on individual portfolios as long as the firm-wide total satisfies the floor. Global full phase-in is scheduled through 2028 in most major jurisdictions (with an initial lower floor, e.g. 50%, stepping up annually).

### Leverage ratio: the non-risk-weighted backstop

The leverage ratio (**Tier 1 capital / total on- and off-balance-sheet exposure**, no risk-weighting at all, minimum **3%**, higher for G-SIBs under the enhanced supplementary leverage ratio) exists specifically to catch the failure mode risk-weighted ratios structurally can't: a bank whose internal models (or the standardized weights themselves) systematically underweight some asset class can look comfortably capitalized on a risk-weighted basis while carrying enormous absolute dollar exposure that would be catastrophic if that risk assessment turns out wrong — precisely what happened with supposedly low-risk, highly-rated securitized mortgage assets before 2008. When the leverage ratio, not a risk-weighted ratio, is the *binding* constraint for a given bank, that typically signals a genuinely low-risk-per-dollar balance sheet (heavy in sovereign bonds, agency mortgages, or cash) rather than a risk-concentrated one — the backstop functioning exactly as intended.

### LCR — worked example

The Liquidity Coverage Ratio tests 30-day survival under an acute stress scenario: `LCR = High-Quality Liquid Assets (HQLA) / Total Net Cash Outflows over 30 days`, minimum **100%**. HQLA is tiered — Level 1 (cash, central bank reserves, certain sovereign bonds) counts at full (100%) value with no cap on the amount; Level 2A (certain government-sponsored-entity and highly-rated corporate/covered bonds) gets an **85% haircut** and is capped, together with Level 2B, at **40% of total HQLA** (Level 2B alone further capped at 15%), specifically so a bank can't satisfy the ratio by loading up on lower-quality-but-technically-eligible assets instead of genuine cash-equivalents.

**Worked example**: a bank holds $500M Level 1 HQLA and $200M Level 2A HQLA, and stressed net cash outflows over 30 days are projected at $550M.
```
HQLA = 500 + (200 × 0.85) = 500 + 170 = $670M
LCR  = 670 / 550 = 121.8%   -->  compliant (>= 100%)
```

### NSFR — worked example

The Net Stable Funding Ratio tests structural, 1-year balance-sheet funding stability — is the bank's book of longer-term, less-liquid assets backed by sufficiently stable liabilities, rather than short-term wholesale funding that could evaporate overnight: `NSFR = Available Stable Funding (ASF) / Required Stable Funding (RSF)`, minimum **100%**. Each liability gets an **ASF factor** reflecting how likely it is to remain in place for a year (capital and long-term debt: 100%; stable retail deposits: 95%; wholesale funding from financial institutions under 6 months: 0%); each asset gets an **RSF factor** reflecting how much stable funding it needs behind it (cash/central bank reserves: 0%; long-term residential mortgages, low risk weight: 65%; short-term corporate loans: 50%; illiquid/other assets: 100%).

**Worked example**: $600M stable retail deposits (ASF 95% = $570M) + $200M Tier 1/Tier 2 capital and long-term debt (ASF 100% = $200M) + $200M short-term (<6mo) interbank wholesale funding (ASF 0% = $0) gives **ASF = $770M**. Against $100M cash/reserves (RSF 0% = $0) + $300M long-term residential mortgages (RSF 65% = $195M) + $400M short-term corporate loans (RSF 50% = $200M) + $200M other illiquid assets (RSF 100% = $200M) gives **RSF = $595M**.
```
NSFR = 770 / 595 = 129.4%   -->  compliant (>= 100%)
```
**The comparative point**: this bank's funding mix (mostly sticky retail deposits, minimal short-term wholesale reliance) is exactly the structural profile NSFR was designed to reward — a bank funded predominantly by short-term interbank borrowing against the same asset book would need far more capital-light, liquid assets to clear the same 100% threshold, because its ASF would collapse toward the 0%-factor end.

### BCBS 239 — the data-architecture mandate hiding inside Basel

**BCBS 239** ("Principles for effective risk data aggregation and risk reporting," January 2013) is not a capital formula at all — it's 14 principles requiring banks, especially G-SIBs, to be able to aggregate risk data *accurately, completely, and fast enough to support decisions during a crisis*, not just at a relaxed quarter-end pace. It matters disproportionately to an engineering organization because it's effectively a mandate for single sources of truth, full data lineage/traceability, automated reconciliation, and clearly defined data ownership across every system that feeds regulatory capital and liquidity numbers — and more than a decade after publication, many large banks are still running active remediation programs against it, because retrofitting clean lineage into decades of legacy trade, position, and general-ledger systems is a genuinely hard, expensive, multi-year engineering effort, not something you implement by writing a new ratio formula.

---

## Build it from scratch

```python
# untested sketch -- ratio mechanics and worked LCR/NSFR numbers verified by hand above
def capital_ratios(cet1, at1, tier2, rwa):
    tier1 = cet1 + at1
    total_capital = tier1 + tier2
    return {
        "CET1_ratio": cet1 / rwa,
        "Tier1_ratio": tier1 / rwa,
        "Total_ratio": total_capital / rwa,
        "meets_cet1_min_4.5pct": cet1 / rwa >= 0.045,
        "meets_effective_cet1_floor_7.0pct": cet1 / rwa >= 0.070,   # incl. 2.5% conservation buffer
    }

def output_floor_check(rwa_internal_model, rwa_standardized, floor=0.725):
    rwa_floor = floor * rwa_standardized
    binding_rwa = max(rwa_internal_model, rwa_floor)
    return {
        "rwa_floor": rwa_floor,
        "floor_binds": rwa_internal_model < rwa_floor,
        "rwa_used_for_capital": binding_rwa,
    }

def leverage_ratio(tier1_capital, total_exposure, min_ratio=0.03):
    ratio = tier1_capital / total_exposure
    return {"leverage_ratio": ratio, "compliant": ratio >= min_ratio}

def lcr(level1_hqla, level2a_hqla, net_cash_outflows_30d,
        level2a_haircut=0.85, level2_cap_pct=0.40):
    level2a_eligible = level2a_hqla * level2a_haircut
    hqla_uncapped = level1_hqla + level2a_eligible
    # Level 2 (2A+2B) capped at 40% of total HQLA -- simplified, no 2B here
    cap = (level1_hqla / (1 - level2_cap_pct)) * level2_cap_pct
    level2a_used = min(level2a_eligible, cap)
    hqla = level1_hqla + level2a_used
    return {"hqla": hqla, "lcr": hqla / net_cash_outflows_30d,
            "compliant": hqla / net_cash_outflows_30d >= 1.0}

def nsfr(asf_items, rsf_items):
    # asf_items / rsf_items: list of (amount, factor) tuples
    asf = sum(amount * factor for amount, factor in asf_items)
    rsf = sum(amount * factor for amount, factor in rsf_items)
    return {"asf": asf, "rsf": rsf, "nsfr": asf / rsf, "compliant": asf / rsf >= 1.0}

# worked example from the module text
print(lcr(500e6, 200e6, 550e6))
print(nsfr(
    asf_items=[(600e6, 0.95), (200e6, 1.00), (200e6, 0.00)],
    rsf_items=[(100e6, 0.00), (300e6, 0.65), (400e6, 0.50), (200e6, 1.00)],
))
```

Full runnable version — including a GSIB-surcharge bucket calculator and a multi-period RWA/output-floor projection model — is the lab exercise in `labs/python/08-basel/`.

---

## How it's done in production

Large banks run dedicated **regulatory reporting platforms** (vendor systems like Wolters Kluwer OneSumX, Moody's RiskFrontier, SAS Risk, or substantial in-house builds) that compute RWA, capital ratios, and LCR/NSFR from position and transaction data feeds, producing statutory filings — in the US, the FR Y-9C (bank holding company financial statement), the FR Y-14 series (the detailed CCAR/DFAST stress-test submission schedules), and FFIEC call reports; in the EU, COREP (capital) and FINREP (financial) reporting. The single hardest, most recurring engineering problem across nearly every large bank is **reconciliation**: the RWA/liquidity engine and the finance general ledger are almost always separate systems built at different times with different position snapshots, netting conventions, and currency-conversion logic, and getting them to agree exactly, every reporting cycle, without manual adjustment entries is the actual multi-year engineering program BCBS 239 exists to force.

| Symptom | Cause | Fix |
|---|---|---|
| Quarter-end RWA figure doesn't reconcile against finance's balance-sheet totals, requiring manual adjustment entries | Risk-data-aggregation pipeline uses a different position snapshot time, netting logic, or currency-conversion path than the general ledger — a classic BCBS 239 gap | Single golden-source data lineage from trade/position systems feeding both finance and risk pipelines identically, with automated daily (not quarter-end-only) reconciliation controls |
| LCR ratio swings sharply day to day with no underlying business change | Cash-flow product mapping into the regulatory outflow-rate taxonomy (stable vs less-stable retail, operational vs non-operational wholesale) applied inconsistently, or a timing mismatch in the HQLA eligibility feed | Centralize and version-control the product-to-regulatory-category mapping as reviewed, tested code with a change-control audit trail — never a spreadsheet lookup maintained by one person |
| Internal-model RWA is materially below standardized RWA once the output floor phases in, forcing an unplanned capital add | IRB models were built years before the output floor existed, with no parallel standardized-approach calculation path monitoring the gap in the meantime | Run both approaches continuously in parallel well before any regulatory deadline, and track the floor-binding gap as a first-class engineering/capital-planning metric, not a one-time implementation checklist item |
| Annual CCAR/DFAST stress-test submission requires weeks of manual patchwork before the deadline every cycle | Production risk-data infrastructure wasn't built for the specific granularity and format the Fed's scenario models require, so a large manual translation layer sits between production systems and the submission | Build a stress-testing-specific data mart aligned to FR Y-14 schedules year-round, maintained continuously, not assembled as an annual fire drill |
| A new regulatory calculation (e.g., a Basel III finalization standardized operational-risk formula) takes 12+ months to implement despite the rule text itself being short | The actual work is threading a new formula through a decade of legacy RWA-engine logic and revalidating every downstream consumer (finance, treasury, capital planning), not implementing the formula itself | Architect risk-calculation engines with calculation logic decoupled and independently versioned/testable from data plumbing, so a new regulatory formula becomes a configuration/rule change rather than a full pipeline rewrite |

---

## Tradeoffs & when NOT to use it

- **Don't treat Basel as a finished, static rulebook you can learn once.** As of 2026 the US is still mid-re-proposal on a package that directly changes standardized-approach mechanics for credit, market, operational, and counterparty-credit risk — an engineering roadmap built assuming the 2023 proposal's numbers, rather than the March 2026 capital-neutral re-proposal, would be planning against a rule that no longer exists.
- **Don't assume the output floor is uniformly "fairer" with no real cost.** A genuinely low-risk, well-diversified bank whose internal models correctly identify it as lower-risk than the standardized approach's generic weights suggest still gets floored at 72.5% of the standardized figure — the floor trades away some genuine risk-sensitivity specifically to buy comparability across banks, a real, acknowledged tradeoff, not a free improvement.
- **Don't apply full Basel III/Endgame-scale compliance engineering to a bank far below the regulatory size thresholds.** LCR/NSFR, CCAR/DFAST, and the most stringent standardized-approach requirements bind primarily at the largest and most systemically important institutions; the March 2026 US re-proposal explicitly carves out a separate, less burdensome track for regional and smaller banks precisely because building G-SIB-grade regulatory infrastructure for an institution that will never be a G-SIB is a real, avoidable engineering cost.
- **Don't confuse Basel capital adequacy with a guarantee against failure.** Silicon Valley Bank (March 2023) was, by conventional risk-weighted capital measures, adequately capitalized shortly before its failure — its actual proximate cause was uninsured-deposit run risk interacting with unrealized losses on available-for-sale securities, a genuine gap in how existing rules (at the time, for a bank of its size) captured interest-rate risk and deposit-concentration risk, which is exactly why IRRBB and liquidity-rule tightening remain live, unresolved regulatory threads in 2026.
- **Don't assume Basel covers every material risk a bank runs.** Cyber risk, climate/transition risk, and shadow-banking/non-bank-lender activity performing genuinely bank-like credit intermediation sit largely outside the classic Basel capital-and-liquidity framework as of 2026, handled (if at all) through separate, less mature supervisory initiatives — a real, acknowledged regulatory gap, not an oversight in this module.

---

## Interview questions

### Q1 — What specific problem did Basel I solve, and what was its most widely cited flaw?
**Testing:** history plus the core critique, not just the year and the number.
**Answer:** Basel I (1988) solved the lack of any common international capital-adequacy standard — undercapitalized banks (Japanese banks in particular were cited) could win business on price by holding less loss-absorbing capital, and the Latin American debt crisis exposed how thin many large banks' capital cushions actually were. It set the first internationally agreed 8% capital-to-RWA minimum. Its flaw: crude risk-weight buckets (0/20/50/100%) treated an investment-grade corporate loan identically to a near-default one — both got a 100% risk weight.
**Follow-up trap:** *"So did Basel II just add more buckets?"* — no, Basel II went further, allowing banks to use their own internal PD/LGD models (the IRB approach) for continuous, bank-specific risk sensitivity, not merely a finer static bucket table — though the standardized approach was also refined separately, e.g. using external credit ratings.

### Q2 — State the three Basel III capital ratios and their minimums, including the effective CET1 floor once the conservation buffer is added.
**Testing:** the core numbers, cold.
**Answer:** CET1/RWA ≥ 4.5%, Tier 1/RWA ≥ 6.0%, Total capital/RWA ≥ 8.0%. Adding the 2.5% capital conservation buffer (CET1-only) makes the practical CET1 floor 7.0% for every bank before automatic distribution restrictions kick in.
**Follow-up trap:** *"What actually happens to a bank whose CET1 falls to 5.5%, into the buffer range?"* — it isn't immediately non-compliant or seized; it triggers automatically graduated restrictions on capital distributions (dividends, buybacks, discretionary bonus payments), scaled to how deep into the buffer range the bank has fallen — a deliberately "soft," self-correcting enforcement mechanism, not an abrupt intervention.

### Q3 — What is the output floor, what specific problem did it fix, and what's the exact number?
**Testing:** whether the floor is understood as a fix for a documented, specific problem, not a generic "more capital" rule.
**Answer:** Internal-model RWA cannot fall below 72.5% of standardized-approach RWA, enforced at the aggregate firm level. It fixed a well-documented problem — BCBS and EBA studies found banks running internal models on economically near-identical portfolios producing dramatically different RWA outputs, undermining the comparability of published capital ratios across banks.
**Follow-up trap:** *"Is the 72.5% floor applied per-portfolio or firm-wide?"* — firm-wide, in aggregate — a bank can still run internal-model RWA well below 72.5% of standardized on specific portfolios as long as the total firm-wide RWA clears the floor overall.

### Q4 — Walk through a worked LCR calculation: $500M Level 1 HQLA, $200M Level 2A HQLA, $550M net cash outflows over 30 days.
**Testing:** the mechanics, including the haircut.
**Answer:** `HQLA = 500 + (200 × 0.85) = $670M`. `LCR = 670/550 = 121.8% ≥ 100%`, compliant — the bank holds enough high-quality liquid assets to survive a modeled 30-day acute stress period without new funding.
**Follow-up trap:** *"Is there a limit on how much of total HQLA can come from Level 2 assets?"* — yes, Level 2 (2A+2B combined) is capped at 40% of total HQLA, with a further 15% sub-cap on Level 2B specifically, precisely so a bank can't satisfy the ratio by loading up on lower-quality-but-technically-eligible assets instead of genuine cash/sovereign-grade Level 1 holdings.

### Q5 — What does NSFR measure that LCR doesn't, and why did Basel III need both?
**Testing:** the structural-vs-acute-stress distinction, the core reason two separate liquidity ratios exist.
**Answer:** LCR is a 30-day acute-stress survival test. NSFR is a 1-year structural funding-stability test — are longer-term, illiquid assets backed by sufficiently stable liabilities, rather than short-term wholesale funding that could evaporate. Both were needed because a bank can pass a 30-day stress test while still running a structurally fragile balance sheet funded by rolling short-term wholesale liabilities against long-dated illiquid assets — exactly the funding-model fragility that helped bring down Bear Stearns and Lehman in 2008, which a 30-day-only metric wouldn't catch.
**Follow-up trap:** *"Give an ASF-factor example showing why stable retail deposits and short-term interbank funding are treated so differently."* — stable retail deposits get a 95% ASF factor (behaviorally sticky, unlikely to run simultaneously); wholesale funding from financial institutions under six months to maturity gets a 0% ASF factor (assumed entirely unavailable to roll over under stress) — this gap is exactly why a bank funded mostly by short-term interbank borrowing needs far more stable, liquid assets to clear NSFR than one funded by retail deposits.

### Q6 — Explain the G-SIB surcharge and how a bank's bucket is determined.
**Testing:** whether systemic importance is understood as multi-dimensional, not just "big bank."
**Answer:** An additional CET1 requirement (roughly 1.0-3.5% of RWA, bucketed) layered on top of every other requirement for Globally Systemically Important Banks, based on a composite score across five categories: size, interconnectedness, cross-jurisdictional activity, substitutability, and complexity.
**Follow-up trap:** *"Why not just use total asset size?"* — because systemic danger isn't purely a function of size; a smaller bank can be far more systemically dangerous due to deep counterparty interconnectedness, activity that's genuinely hard to substitute elsewhere in the financial system, or operational complexity that would make an unwind chaotic — all captured by the composite score, not asset size alone.

### Q7 — Why is the leverage ratio described as a "backstop," and what failure mode does it catch that risk-weighted ratios can't?
**Testing:** understanding why a non-risk-weighted metric is necessary alongside risk-weighted ones.
**Answer:** The leverage ratio (Tier 1 capital / total exposure, no risk-weighting, minimum 3%) catches internal-model gaming or systematic underweighting of an asset class — a bank could look comfortably capitalized on risk-weighted ratios while carrying enormous absolute dollar exposure that would be catastrophic if that risk assessment turns out wrong, precisely what happened with highly-rated securitized mortgage assets before 2008.
**Follow-up trap:** *"If the leverage ratio is the binding constraint for a bank comfortably above its risk-weighted ratios, what does that imply?"* — that the bank's assets are, on average, genuinely low-risk-per-dollar (heavy in sovereign bonds, agency mortgages, or cash) rather than risk-concentrated — the leverage ratio binding here is the backstop functioning exactly as designed, not a sign of a broken balance sheet.

### Q8 — What is BCBS 239, and why does it matter more to an engineering organization than most other Basel documents?
**Testing:** whether Basel is understood as a data-architecture mandate, not purely a capital-formula document.
**Answer:** BCBS 239 (January 2013) sets 14 principles requiring accurate, complete, and fast risk-data aggregation, especially for G-SIBs — effectively a mandate for single sources of truth, full data lineage, automated reconciliation, and clear data ownership, not a capital-ratio formula at all. It matters disproportionately to engineering because retrofitting clean lineage into decades of legacy trade, position, and general-ledger systems is a genuinely hard, multi-year build, and many large banks are still running active remediation programs against it more than a decade after publication.
**Follow-up trap:** *"Give a concrete symptom a risk-reporting engineer would actually see from a BCBS 239 gap."* — quarter-end RWA or liquidity figures that don't reconcile cleanly against the finance general ledger, requiring recurring manual adjustment entries every reporting cycle — that manual-reconciliation burden is the visible, repeating symptom of a lineage gap, not a one-time bug to fix and forget.

### Q9 — What changed between the original 2023 US Basel III Endgame proposal and the March 2026 re-proposal, and why does it matter for a bank's technology roadmap?
**Testing:** currency — whether the candidate has kept up with 2026 developments, and can connect the policy change to engineering consequences.
**Answer:** The 2023 proposal would have raised aggregate large-bank capital by roughly 19%; the March 19, 2026 re-proposal (under Fed Vice Chair Bowman) is designed to be broadly capital-neutral, projecting an estimated $87.7B in net system-wide CET1 relief, alongside a separate, lighter track for regional/smaller banks and a revised G-SIB surcharge methodology. It matters for the technology roadmap because the underlying calculation-engine rebuild — new standardized approaches for credit, market, operational, and counterparty-credit risk, and the output-floor plumbing — is still required regardless of the political outcome on aggregate capital levels; the multi-year engineering program doesn't shrink just because the number was made more palatable.
**Follow-up trap:** *"Comments are due mid-2026, finalization expected Q4 2026, phase-in from 2027 — is it too early to start building?"* — no; the structural mechanics (standardized-approach logic, output-floor plumbing, data-lineage requirements) are stable across both the 2023 and 2026 proposals and very unlikely to change further, so building the pipeline architecture now and parameterizing the specific numeric calibrations to be swapped in once finalized is lower-risk than waiting for the final rule to start from zero.

### Q10 (staff/design) — You're the Principal engineer for a regional bank's regulatory reporting platform. The bank just crossed $100B in assets and picked up LCR/NSFR obligations it never had before. What's your first-quarter plan?
**Testing:** staff-level synthesis — translating the module's regulatory content into an actual engineering program with correct sequencing.
**Answer:** Start with data lineage and product-taxonomy mapping, not the ratio arithmetic — LCR/NSFR accuracy depends entirely on correctly classifying every deposit, loan, and security into the regulatory categories (stable vs less-stable retail, operational vs non-operational wholesale, HQLA tiers), and that classification work is the actual bottleneck, not the ratio formulas themselves. Build the classification/mapping layer as a versioned, testable, auditable component decoupled from the aggregation math, since regulatory category definitions get refined over time and examiner disputes over classification are common — a taxonomy change shouldn't require touching core calculation code. Stand up automated daily reconciliation between the new liquidity pipeline and existing treasury/finance cash-flow systems immediately, since an unreconciled first LCR/NSFR figure is the most common early failure mode banks hit scaling into these requirements. Treat the whole build as a BCBS-239-style data-governance program from day one, not a one-off report.
**Follow-up trap:** *"The board wants LCR/NSFR numbers in six weeks, before the data-lineage work is properly done. How do you handle that?"* — deliver an interim, clearly-labeled manual or semi-automated calculation with explicit, documented, conservative simplifying assumptions and gaps for the board deadline, while continuing the proper automated build in parallel — a precise-looking number resting on unreconciled or misclassified source data is worse than a clearly-caveated interim estimate, since it creates false confidence in a figure examiners will eventually test rigorously.

---

## Red flags that fail you

- States the Basel capital ratios without knowing the effective 7.0% CET1 floor once the conservation buffer is included.
- Calls "Basel IV" an official BCBS term rather than an industry nickname for the December 2017 Basel III finalization.
- Cannot explain what specific problem the output floor fixed, or claims it applies per-exposure rather than firm-wide.
- Confuses LCR (30-day stress survival) with NSFR (1-year structural funding stability), or treats them as redundant.
- Is unaware that the US Basel III Endgame was re-proposed in March 2026 on a capital-neutral basis, materially different from the original 2023 proposal.
- Treats Basel capital adequacy as a guarantee against bank failure, ignoring gaps (deposit-run risk, interest-rate risk in the banking book) exposed by SVB in March 2023.

---

## Cheat card

```
BASEL I (1988): first international 8% capital/RWA minimum, crude 0/20/50/100% risk-weight buckets
BASEL II (2004): 3 pillars (min capital / supervisory review / disclosure), IRB internal models added
  -- finalized just before 2008: capital too low in quantity+quality, ZERO liquidity requirements
BASEL III (2010-11): CET1 defined, capital buffers, non-risk leverage ratio, LCR+NSFR (first ever)
BASEL III FINALIZATION / "Basel IV" (Dec 2017, BCBS never uses "IV"): OUTPUT FLOOR = fixes RWA variability

CAPITAL RATIOS (Capital/RWA):  CET1>=4.5%  Tier1>=6.0%  Total>=8.0%
  + 2.5% conservation buffer (CET1 only) -> EFFECTIVE CET1 FLOOR = 7.0% for ALL banks
  + countercyclical buffer 0-2.5% (national regulator, credit-cycle) + G-SIB surcharge 1.0-3.5%

OUTPUT FLOOR: internal-model RWA >= 72.5% x standardized-approach RWA, FIRM-WIDE aggregate, not per-exposure
LEVERAGE RATIO (backstop, no risk weights): Tier1/Total Exposure >= 3%

LCR = HQLA / 30-day net cash outflows >= 100%
  Level1 HQLA: 100% value, uncapped. Level2A: 85% haircut. Level2(A+B) capped at 40% of total HQLA.
  worked: $500M L1 + $200M L2A(85%)=$170M -> HQLA=$670M, outflows=$550M -> LCR=121.8%

NSFR = Available Stable Funding / Required Stable Funding (1-year) >= 100%
  ASF: capital/LT debt=100%, stable retail deposits=95%, <6mo interbank wholesale=0%
  RSF: cash=0%, LT low-risk mortgages=65%, ST corporate loans=50%, illiquid other=100%
  worked: ASF=$770M, RSF=$595M -> NSFR=129.4%

BCBS 239 (Jan 2013): 14 risk-data-aggregation principles -- data lineage mandate, NOT a capital formula
  many G-SIBs STILL remediating gaps a decade+ later

US 2026: Fed/OCC/FDIC re-proposed Basel III Endgame March 19 2026 (Bowman), CAPITAL-NEUTRAL
  (~$87.7B system-wide CET1 relief, vs original 2023 proposal's ~+19% hike)
  comments due mid-2026, finalization Q4 2026, phase-in from 2027
```

## Sources

- [International Convergence of Capital Measurement and Capital Standards (Basel I) — Basel Committee on Banking Supervision, BIS (1988)](https://www.bis.org/publ/bcbs04a.htm) — accessed 2026-08-08
- [Basel III: A global regulatory framework for more resilient banks and banking systems — BCBS, BIS (2010, rev. 2011)](https://www.bis.org/publ/bcbs189.htm) — accessed 2026-08-08
- [Basel III: Finalising post-crisis reforms — BCBS, BIS (December 2017)](https://www.bis.org/bcbs/publ/d424.htm) — accessed 2026-08-08
- [Principles for effective risk data aggregation and risk reporting (BCBS 239) — BCBS, BIS (January 2013)](https://www.bis.org/publ/bcbs239.htm) — accessed 2026-08-08
- [Basel III: The Liquidity Coverage Ratio and liquidity risk monitoring tools — BCBS, BIS (2013)](https://www.bis.org/publ/bcbs238.htm) — accessed 2026-08-08
- [Basel III: the net stable funding ratio — BCBS, BIS (2014)](https://www.bis.org/bcbs/publ/d295.htm) — accessed 2026-08-08
- [Basel III Endgame, Take Two: 8 Key Takeaways from the Federal Banking Agencies' Capital Re-Proposals — Freshfields (March 2026)](https://www.freshfields.com/en/our-thinking/blogs/a-fresh-take/basel-iii-endgame-take-two-8-key-takeaways-from-the-federal-banking-agencies-c-102mnm3) — accessed 2026-08-08
- [Federal Reserve Vice Chair for Supervision Bowman Previews Basel III, G-SIB Surcharge & Revised Standardized Approach Proposals — Sullivan & Cromwell LLP (March 2026)](https://www.sullcrom.com/insights/memo/2026/March/Fed-Vice-Chair-Bowman-Previews-Basel-III-GSIB-Surcharge-Proposals) — accessed 2026-08-08
- [Fed remarks point to capital-neutral Basel III Endgame in 2026 — Bloomberg Professional Services](https://www.bloomberg.com/professional/insights/financial-services/fed-remarks-points-to-capital-neutral-basel-iii-endgame-in-2026/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
