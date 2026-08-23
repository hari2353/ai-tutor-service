# Model Risk Management: SR 11-7, Validation, Governance, the MRM Role

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-basel · **Updated:** 2026-08-23
> **Module id:** `T24-mrm` · **Tags:** banking, critical

## The 30-second version

Model risk is the risk of LOSS from decisions based on wrong or misused models — not whether your math is elegant but whether anyone checked it, monitored it, and could say no. The governing US text is the Fed/OCC's SR 11-7 / OCC 2011-12 (2011): models are "quantitative methods... that process input data into quantitative estimates," and banks must manage two risk sources — model error and model misuse — through a lifecycle of independent validation (conceptual soundness review, outcomes analysis, ongoing monitoring), a complete inventory with tiering by materiality, effective challenge backed by incentive alignment, and board-approved policy. The cautionary canon is rich: JPMorgan's 2012 London Whale ($6.2B loss after an unvalidated VaR-model swap built partly on a spreadsheet with copy-paste errors cut reported VaR roughly in half) wrote the textbook on change control; Barclays paid the SEC $200M in 2022 after unvalidated overrides let it over-issue ~$15B of structured notes; Zillow's 2021 iBuying collapse (~$300M+ write-downs, 25% of homes bought above market) proved MRM applies far beyond banks. The modern frontier is GenAI: banks are extending SR 11-7 machinery to LLMs by treating eval-gate results as validation evidence, classifying hallucination as a model-risk event, and running champion-challenger across prompt/model versions.

## Why this gets asked

Because "model risk/validation" appears verbatim in banking JDs from Citi's GenAI governance teams to Optum's analytics groups, and interviewers need to know whether you've operated inside a second line or merely read about ML. The questions are behavioral-technical hybrids: describe a validation you'd run on a PD model (conceptual soundness → data lineage → benchmark comparison → backtesting discrimination/calibration → monitoring thresholds); what makes challenge "effective" (incentives: validators compensated/reporting independently, authority to veto, documented findings with severity ratings); why the Whale matters (a model CHANGE bypassed validation during transition — governance failure, not statistics failure). For AI-heavy roles expect the bridge question: "SR 11-7 predates transformers — how do you validate an LLM?" Strong answers map old concepts onto new artifacts: eval suites = outcomes analysis, model cards = documentation standards, red-teaming = effective challenge, hallucination incidents = model-limitation events logged and trended. Weak answers either claim LLMs are unvalidatable or hand-wave "we use SHAP."

## Lineage

**What came before.** Pre-2011 US supervision of models lived in scattered guidance: the Fed's 1998 trading-book model guidance, OCC 2000-16 on credit-scoring validation, SR 07-1 (2007) on complex structured products — the one that flagged CDO-model reliance months before the crisis and was ignored in practice. Post-mortems of 2008 (senior supervisors' reviews) found banks couldn't produce model inventories, validations were rubber stamps, and third-line audit lacked quant skills. The London Whale then supplied a live demonstration mid-rule-writing: JPMorgan's CIO switched VaR methodologies in January 2012, cutting reported VaR roughly from ~$139M to ~$80M on the growing synthetic credit book; by April 2012 task-force review found spreadsheet errors (copy-paste averaging across cells) had understated VaR further, breaches followed, and cumulative losses reached ~$6.2B with $920M+ in fines (OCC $300M + Fed $200M in September 2013; FCA £137.6M).

**Where it stands now.** SR 11-7 became the de facto global template (echoed in ECB TRIM/EGMA expectations, PRA SS1/23 for AI in financial services consultation, OSFI E-23). MRM matured into a career track: second-line Model Risk groups with hundreds of validators at GSIBs, tiering schemes (Tier 1 = material/high-complexity → annual full revalidation with conceptual-soundness deep dive; Tier 3 = low impact → lighter periodic review), findings registers with severity ratings and remediation SLAs, and annual board attestations. The 2023 interagency third-party risk guidance extended coverage to vendor models (a huge share of bank AI), and 2021-2025 supervisory letters began explicitly folding AI/ML models into inventory scope. Meanwhile the failure catalog kept teaching: Knight Capital (August 1, 2012 — $440M gone in ~45 minutes from a deployment flag error, SEC settlement 2013) for implementation risk; Barclays' unvalidated model overrides over-issuing ~$15.2B of structured notes (SEC order March 2022, $200M penalty); Zillow Offers shutting November 2021 after its home-price AVM systematically overbid (~25% of homes purchased above eventual value; Q3 2021 write-down $304M plus ~$240M guided for Q4).

**Where it's heading.** Three trajectories. First, GenAI governance is being built ON TOP of SR 11-7 rather than beside it: LLM use cases get tiered like any model, with eval-gate pass rates archived as validation evidence, prompt/model version changes treated as model changes requiring approval, and hallucination/fabrication incidents logged in the model-risk-event taxonomy alongside backtest exceptions. Second, regulators are converging from multiple directions — EU AI Act high-risk obligations bite August 2026 for credit scoring, NIST AI RMF gives a common vocabulary, ISO/IEC 42001 makes AI management systems auditable — so banks are mapping these onto existing MRM policy instead of inventing parallel structures (details in T24-ai-in-finance). Third, continuous validation tooling: automated monitoring dashboards (PSI/drift, calibration decay), CI/CD eval gates, and challenger pipelines are turning point-in-time validation into always-on surveillance, with validators reviewing code-as-evidence.

---

## Mental model

```
MODEL RISK = P(model wrong) x LOSS(decisions taken on it)

THREE LINES OF DEFENSE:
  1st: developers/users own the model, document it
  2nd: MRM independently validates + challenges  <- the job
  3rd: internal audit checks THAT THE PROCESS ran

SR 11-7 VALIDATION = THREE LEGS (all three or it isn't validation):
  conceptual soundness   is the theory right? assumptions? benchmarks?
  outcomes analysis      do outputs match reality? backtests?
  ongoing monitoring     does it STILL match reality this month?

EFFECTIVE CHALLENGE requires: authority + incentives + competence.
  validator can veto · paid to find problems · reports to CRO not CDO

TIERING DRIVES EVERYTHING:
  Tier 1 material/complex -> annual deep revalidation
  Tier 2 moderate         -> lighter cycle
  Tier 3 low              -> periodic review only

LLM EXTENSION MAP:
  eval suite pass rates == outcomes analysis evidence
  model card            == documentation standard
  red-team results      == effective challenge record
  hallucination incident== model-risk event (log + trend)
```

The unifying lens: SR 11-7 institutionalizes distrust. Every mechanism — independence, tiering, challenge, monitoring — exists because self-assessment fails predictably under production pressure. When you adapt it to any new technology, ask only "where could this fail silently, and who is paid to catch it?"

---

## How it actually works

### The lifecycle a bank model actually passes through

Development → independent validation BEFORE approval for use → implementation testing (independent code verification against spec; benchmark datasets) → approved-use registration in inventory with tier, limitations, and compensating controls → ongoing monitoring (backtesting thresholds, drift metrics, performance decay) → change management (material changes re-trigger validation) → periodic revalidation → decommission. Skipping steps has named precedents: Whale (change control), Knight (implementation), Zillow (monitoring/feedback loops ignored as market shifted), Barclays (override governance).

### What a real validation report contains

Scope and independence statement; business context and materiality; conceptual soundness review (theory basis, assumption stress: stationarity, linearity, population stability; benchmark model comparison — e.g., logistic scorecard vs gradient boosting on same data); data-quality assessment (lineage, representativeness, survivorship); quantitative testing — discrimination (AUC/Gini with confidence intervals), calibration (predicted vs observed by decile, binomial tests), stability (PSI < 0.10 stable / 0.10-0.25 watch / >0.25 action rule-of-thumb), sensitivity analysis around key parameters; outcomes/backtesting vs realized defaults or returns; findings register with severity (High/Medium/Low), owner, remediation deadline; final rating (e.g., Approved / Approved-with-limitations / Not-approved) and approved-use boundaries.

### Governance mechanics that make it bite

Board-approved policy defining models broadly enough to catch spreadsheets and vendor tools; complete inventory (banks routinely count thousands — GSIBs report 1,500-5,000+ models); tiering rubric weighting materiality × complexity × novelty; validation capacity planning (Tier 1 annual cycles set headcount); compensation/reporting independence for validators; annual MRM effectiveness reporting to board risk committees; third-party model intake mirroring first-party rigor per the 2023 interagency guidance. The Whale's specific lesson lives here: methodology TRANSITIONS need shadow-running periods, parallel metrics, and explicit approval gates — JPMorgan cut over mid-transition without full validation, then kept the flawed model running while volumes grew.

### Champion-challenger as an MRM instrument

Champion = approved incumbent. Challengers run in SHADOW mode (same inputs, no decisions taken). Promotion requires: identical population/time windows; statistically significant improvement on the decision metric (e.g., KS/AUC lift beyond noise via paired bootstrap); no degradation on guardrail metrics (approval rate shifts, fairness ratios, tail behavior); stability across at least one full seasonal cycle where relevant; documented approval through model governance. For LLMs the pattern translates directly: golden eval datasets + regression gates in CI/CD act as automated outcome analysis; challenger prompts/models must beat champion on eval suites AND human-judged samples before traffic shifts.

### Cross-industry AI governance: adapting MRM to LLMs (~200 words)

Banks are converging on one answer: treat LLM applications AS models under SR 11-7, extended rather than replaced. Concretely: each GenAI use case enters the inventory tiered by customer impact (a credit-decision copilot lands Tier 1; an internal summarizer lower); model cards plus system prompts become the documentation artifact; eval suites (golden datasets, adversarial prompt banks, regression gates in CI/CD) are archived as outcomes-analysis evidence so every promotion has reproducible validation artifacts. Hallucination gets formalized: fabrication incidents are logged as model-risk events with severity, root cause (retrieval miss vs reasoning error), and trend tracking — exactly like backtest exceptions. Prompt injection sits at the security/model boundary with guardrail tests in scope. Champion-challenger governs model/prompt swaps: new versions must beat champions on eval gates before traffic shifts, keeping EU AI Act Article 9 risk-management evidence and ISO/IEC 42001 audit trails as byproducts of existing process rather than parallel bureaucracy. NIST AI RMF's GOVERN/MAP/MEASURE/MANAGE functions map cleanly onto policy/inventory/validation/monitoring already in place. The strategic insight interviewers reward: banks that retrofit LLMs INTO MRM inherit decades of effective-challenge machinery free — those that build separate "AI governance" tracks recreate SR 11-7 badly and fail audits twice.

---

## Build it from scratch

Champion-challenger validation checklist generator (pure std-lib):

```python
from dataclasses import dataclass

@dataclass
class ModelMeta:
    name: str
    kind: str          # 'pd' | 'var' | 'llm' | 'avm'
    tier: int          # 1..3 materiality
    champion_metrics: dict   # e.g. {"auc": .78, "psi": .08}
    challenger_metrics: dict
    n_shadow: int            # shadow-mode observations
    seasonal_cycles_seen: float

def checklist(m: ModelMeta):
    out = [f"VALIDATION CHECKLIST — {m.name} ({m.kind}, Tier {m.tier})"]
    add = out.append
    # universal legs
    add("[ ] Conceptual soundness reviewed & benchmarked")
    add("[ ] Data lineage + population representativeness confirmed")
    add("[ ] Implementation tested vs spec (code verification)")
    add("[ ] Monitoring thresholds set (drift, calibration, PSI)")
    # champion-challenger gates
    ch = m.champion_metrics.get("auc"); ca = m.challenger_metrics.get("auc")
    if m.n_shadow < 1000:
        add(f"[x] BLOCKED: shadow sample {m.n_shadow} < 1,000 minimum")
    else:
        add(f"[ ] Shadow sample adequate: {m.n_shadow} obs")
    if ch and ca:
        lift = ca - ch
        need = 0.02 if m.tier == 1 else 0.01
        add(("[ ] " if lift >= need else "[x] ") +
            f"AUC lift {lift:+.3f} vs required {need:+.3f}")
    add(("[ ] " if m.champion_metrics.get("psi", 1) <= .25 else "[x] ") +
        f"Champion stability acceptable (PSI {m.champion_metrics.get('psi')})")
    if m.seasonal_cycles_seen < 1:
        add("[x] WARNING: challenger untested across a full season")
    add("[ ] Guardrails unchanged (fairness ratios, tail behavior)")
    add("[ ] Rollback plan + revert trigger documented")
    add("[ ] Approval logged in inventory (change ticket attached)")
    if m.kind == "llm":
        add("[ ] Eval-suite regression gate passed (golden dataset)")
        add("[ ] Adversarial/red-team prompts re-run on challenger")
        add("[ ] Hallucination-rate delta within tolerance band")
    if m.kind == "pd":
        add("[ ] Rank-ordering + calibration by decile verified")
        add("[ ] IRB input floors respected (PD>=floor, LGD floor)")
    return out

demo = ModelMeta("CreditCopilot-v3", "llm", 1,
                 {"auc": .81, "psi": .09},
                 {"auc": .835}, n_shadow=2400, seasonal_cycles_seen=0.5)
for line in checklist(demo):
    print(line)
```

Flip inputs to see the generator block promotions: shrink `n_shadow` below 1,000, drop the AUC lift under threshold, or set PSI above 0.25 — each flips a line from `[ ]` to `[x]` and mirrors what a second-line reviewer would actually demand before sign-off.

---

## How it's done in production

**Org chart reality:** Model Risk sits in the second line under the CRO; validators are quants with production experience; a Model Governance team maintains inventory/policy/reporting; first-line teams own developer docs and remediation. GSIBs run 200-500 validators across credit/market/ALM/AI models. Audit (third line) tests process adherence annually.

**Tooling:** model inventory platforms (Clarity, IBM OpenPages, homegrown) tracking tier/owner/validation dates/findings; monitoring dashboards per model with threshold alerts feeding the findings register; validation workbenches reproducing results from raw data; increasingly CI/CD-integrated eval harnesses for AI models where promotion requires green gates — evidence archived automatically.

**Cadence and metrics that matter:** Tier 1 annual revalidation with interim monitoring reviews; findings SLAs (High: 30-90 days); MRM effectiveness KPIs (validation cycle time, high-severity finding recurrence, late-stage discovery rate — discoveries at deployment signal weak first-line testing). Post-SVB-style events also taught ALM models get the same rigor as trading models now.

## Tradeoffs & when NOT to use it

- **Full SR 11-7 ceremony on every spreadsheet is impossible**: tiering exists precisely to concentrate depth where materiality lives; applying Tier 1 process everywhere buries real risk in queue times.
- **Independence has costs**: strict second-line veto power slows launches and can push shadow analytics outside governance ("model risk of avoiding model risk") — mitigate via fast-track lanes for low-tier changes.
- **Champion-challenger fails on non-stationary populations**: if the market regime shifted, the challenger beating the champion may just be overfit to new data; require seasonal cycles before promotion.
- **Don't treat eval scores as ground truth for LLMs**: golden datasets age; benchmark contamination is real; human-judged samples remain necessary evidence alongside automated gates.
- **Validation is not a substitute for engineering**: Knight Capital passed its reviews; the deploy script killed them. Implementation/change controls are separate controls with separate audits.

## Interview questions

### Q1 — Quote SR 11-7's definition of a model and explain why breadth matters.
**Testing:** primary-source fluency.
**Answer:** "A quantitative method, system, or approach that applies statistical, economic, financial, or mathematical theories, techniques, and assumptions to process input data into quantitative estimates" — deliberately covering spreadsheets, vendor tools, ML systems. Breadth matters because risk concentrates where governance doesn't look: unregistered Excel models caused real losses (Whale), and today's equivalent is the un-inventoried GenAI prototype making customer-facing text.
**Follow-up trap:** *"Does a rules engine count?"* — Judgment-based rules without quantitative estimation generally fall outside, but hybrid systems scoring inputs do; banks document the boundary case-by-case rather than litigating philosophy.

### Q2 — Name the three components of SR 11-7 validation and what each would catch.
**Testing:** framework mechanics.
**Answer:** Conceptual soundness (theory/assumption review + benchmarks): catches wrong functional form, violated assumptions — e.g., linear PD model on nonlinear population. Outcomes analysis/backtesting: catches calibration failure — predicted 2% defaults, realized 8%. Ongoing monitoring: catches DECAY after approval — drift, PSI creep, threshold breaches between validations. All three legs required; skipping one leaves a known hole (no outcomes analysis = Whale-era CIO VaR).
**Follow-up trap:** *"Which leg do banks fail most?"* — Monitoring: it's nobody's sprint priority, decays silently, and supervisors' exam findings skew heavily toward stale monitoring and missing thresholds.

### Q3 — What made the London Whale a GOVERNANCE failure specifically?
**Testing:** case-study causality.
**Answer:** The January 2012 VaR methodology change went live mid-transition without completed independent validation; the replacement contained spreadsheet averaging errors understating risk; limit breaches were renegotiated instead of forcing de-risking; escalation chains stalled while the book quadrupled (~$6.2B final loss; $920M+ fines including OCC $300M/Fed $200M). Each control existed on paper — change management, limits, escalation — and each was bypassed under pressure. The Senate report documented all of it.
**Follow-up trap:** *"Single root cause?"* — No single one: culture (CIO's profit halo), capacity (models couldn't keep up with growth), and incentives (breach tolerance) compounded. Interviewers want you to resist single-cause narratives.

### Q4 — Design validation for a vendor-provided credit scorecard you cannot see inside.
**Testing:** black-box validation craft.
**Answer:** Treat as theory-limited: demand documentation (development sample, methodology summary, performance claims), then verify empirically on YOUR population — discrimination/calibration by segment, stability/PSI over time, benchmark against incumbent, sensitivity to missing inputs, override analysis (when humans disagree with scores, who's right?), plus contractual audit rights and SOC reports per third-party guidance. Document limitations as compensating-control conditions in the approval.
**Follow-up trap:** *"Vendor refuses scorecard internals — acceptable?"* — Common and workable IF outcome-level access suffices for your use case; not workable for IRB regulatory capital use where parameter floors/lineage must be demonstrable. The use case determines the depth contractually.

### Q5 — Your champion-challenger test shows challenger AUC +0.03 but PSI 0.31. Promote?
**Testing:** reading stability signals.
**Answer:** No — PSI 0.31 (>0.25 action band) says the population shifted; the challenger's lift likely rides the shift (overfit to new-regime data). Actions: investigate the driver (macro? policy change? data pipeline bug?), re-test on pre-shift window, require another cycle post-stabilization, and check whether the CHAMPION also degraded (then both need recalibration regardless).
**Follow-up trap:** *"What if the shift is permanent and real?"* — Then redevelop/retrain explicitly through change control with fresh validation, not silent challenger promotion. Promotion gates protect against noise AND wishful thinking.

### Q6 — How would you validate an LLM-based customer-service agent under an SR 11-7 lens?
**Testing:** the modern bridge question.
**Answer:** Inventory + tier by customer impact. Conceptual soundness → design review: retrieval architecture, guardrails, system-prompt versioning, refusal behavior spec. Outcomes analysis → eval suites: golden Q&A sets, adversarial/red-team prompt banks, hallucination-rate measurement against grounded answers, regression gates in CI/CD archived as evidence. Monitoring → live dashboards: escalation rates, hallucination incidents logged as model-risk events with trend thresholds, drift in query distribution. Effective challenge → red-team exercises independent of the build team. Human oversight thresholds for irreversible actions. That maps every classic leg onto GenAI artifacts.
**Follow-up trap:** *"Is pass-rate 92% good enough?"* — Wrong question without error taxonomy: what fraction fabricate financial facts vs style misses, and what's the cost asymmetry? Set tolerances per failure class, not aggregate.

### Q7 — Why does validator independence require more than reporting lines?
**Testing:** incentive-design depth.
**Answer:** Independence = authority (can block approvals/limit use), competence (quant skills to genuinely challenge), AND incentives (compensation/promotion not tied to business-line throughput; findings quotas inverted — rewarding found-and-fixed issues). Banks that pay validators like deal-makers get rubber stamps; those isolating validators from context get pedantry. The craft is structured challenge: documented assumptions log the business must defend.
**Follow-up trap:** *"Ever seen independence theater?"* — Yes-signals: validation turnaround SLAs shorter than any real analysis takes, 100% approval rates, findings only Low severity, validators embedded in delivery squads permanently. Auditors look for exactly these patterns.

### Q8 — A Tier 1 model's backtest starts failing mid-cycle. Walk the response.
**Testing:** operational maturity.
**Answer:** Immediate: quantify severity (calibration vs discrimination vs distribution shift), apply interim compensating controls (wider margins, reduced limits, human review on affected decisions), notify governance per policy. Investigate root cause: data pipeline? regime break? code change? Then either remediate + re-validate, restrict approved-use boundaries, or decommission. Log as model-risk event; feed lessons to policy. Never: quiet threshold adjustments to make numbers pass — that's the Whale pattern in miniature.
**Follow-up trap:** *"Who decides?"* — Pre-defined authority matrix: MRM recommends, a committee (CRO chair) decides restrictions; business owns remediation execution. Ambiguity here is itself a finding.

### Q9 — What does Zillow Offers teach about MRM outside banking?
**Testing:** transferable reasoning.
**Answer:** November 2021 wind-down after the AVM systematically overbid (~25% of homes above eventual value; $304M Q3 write-down, ~$240M guided Q4; ~25% workforce cut). Lessons: feedback loops must close FAST in fast markets (their buy-price model lagged a cooling market); confidence intervals belong in decisioning, not just point estimates; scaling a known-flawed model amplifies losses (they paused, resumed, then doubled down); monitoring needs market-regime tripwires, not just accuracy drift. Same anatomy as a bank credit model failing in a downturn.
**Follow-up trap:** *"So don't use ML for pricing?"* — No — use decision policies robust to model error: position limits per asset, max-bid formulas with haircuts, staged rollout geographies. The model was one input; the absence of error-budgeting was the sin.

### Q10 — Map NIST AI RMF functions onto SR 11-7 components.
**Testing:** cross-framework fluency.
**Answer:** GOVERN ↔ SR 11-7 governance/policy/board reporting; MAP ↔ inventory/tiering/business-context documentation; MEASURE ↔ validation's conceptual-soundness + outcomes-analysis testing plus ongoing monitoring metrics; MANAGE ↔ compensating controls, limitations register, incident response (model-risk events). The RMF's Generative AI Profile (July 2024) adds risk categories (confabulation, information integrity) slotting into MEASURE/MANAGE. Banks adopt RMF vocabulary to talk to non-bank stakeholders while keeping SR 11-7 as the operating system.
**Follow-up trap:** *"Do we need both?"* — Practically yes for US multinationals: regulators reference RMF language, examiners enforce SR 11-7 machinery; mapping table beats dual compliance programs.

### Q11 — How do model tiers drive validation cadence concretely?
**Testing:** operational parameters recall.
**Answer:** Typical scheme: Tier 1 (high materiality/complexity/regulatory exposure): full independent validation before use + annual revalidation + quarterly monitoring review. Tier 2: validation every 2-3 years, semiannual monitoring. Tier 3 (low impact): simplified initial review, periodic attestation, event-driven re-review. Tier assignment weighs financial impact, customer impact, novelty, complexity, reversibility — and gets revisited when use expands (a Tier 3 summarizer promoted into customer-facing advice re-tiers immediately).
**Follow-up trap:** *"Who arbitrates tier disputes?"* — Model governance committee with documented rubric; disputes logged. Silent down-tiering to dodge validation is a classic audit target.

### Q12 — Why is "the model was fine, users misused it" NOT a defense?
**Testing:** misuse-as-risk doctrine.
**Answer:** SR 11-7 defines model risk as arising from BOTH error AND misuse — limitations must be documented, communicated, and enforced through approved-use boundaries, training, and system constraints. If a stress model approved for capital planning got repurposed for trading decisions, the governance chain failed regardless of model quality: approved-use scope is part of the validation deliverable, and monitoring should flag usage outside scope (query logs, application telemetry).
**Follow-up trap:** *"How do you technically enforce scope?"* — API gating (only sanctioned applications call the endpoint), watermarked outputs, usage logging reviewed in monitoring, contractual terms for vendor models. Enforcement lives in plumbing, not memos.

## Red flags

- Describing validation as "checking accuracy metrics" with no conceptual-soundness or monitoring legs.
- No London Whale narrative or wrong moral (it was governance/change control, not math).
- Claiming LLMs can't be validated / no answer for eval-gates-as-evidence.
- Champion-challenger promotion without identical-population or significance checks.
- Treating vendor models as out of MRM scope.
- Validator independence described purely as org-chart lines.
- PSI quoted without thresholds (know 0.10/0.25 bands).
- Confusing three lines of defense with three tiers.

## Cheat card

```
SR 11-7   Fed/OCC Apr 2011 (+OCC 2011-12); model = quant method ->
          estimates; risk = ERROR + MISUSE
VALIDATE  conceptual soundness | outcomes analysis | ongoing monitoring
          all 3 or incomplete; benchmarks + sensitivity + backtests
GOVERN    inventory (GSIBs 1500-5000+ models) · tiers 1-3 by
          materiality x complexity · T1 annual reval · findings
          register w/ SLAs · board-approved policy · 3LOD split
CHALLENGE authority + incentives + competence; veto power;
          comp independent of business throughput
CASES     Whale '12: VaR swap w/o validation, XLS errors,
          ~$6.2B, OCC300+Fed200+FCA137.6M -> change control
          Knight '12: $440M/45min deploy flag -> implementation risk
          Barclays '22: unvalidated overrides, ~$15B over-issue,
          SEC $200M -> override governance
          Zillow '21: AVM overbid ~25% homes, $304M+$240M writedowns
          -> fast feedback loops + error budgets
CC        champion-challenger: SHADOW mode, same population/window,
          sig. improvement (AUC/KS lift), no guardrail degradation,
          >=1 seasonal cycle, rollback plan; LLMs: eval gates =
          validation evidence, hallucination = model-risk EVENT
MONITOR   PSI <0.10 stable / .10-.25 watch / >0.25 act; drift,
          calibration decay, threshold breaches -> findings
AI MAP    model cards=docs · eval suites=outcomes · red-team=
          challenge · NIST GOVERN/MAP/MEASURE/MANAGE ~= policy/
          inventory/validation/monitoring; EU AI Act high-risk
          bites Aug 2026 (credit) -> reuse MRM, don't fork it
```

## Sources

- [Federal Reserve SR 11-7: Supervisory Guidance on Model Risk Management](https://www.federalreserve.gov/boarddocs/srletters/2011/SR1107.htm); accessed 2026-08-23
- [OCC Bulletin 2011-12: Model Risk Management companion guidance](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html); accessed 2026-08-23
- [US Senate Permanent Subcommittee (2013). JPMorgan Whale Report](https://www.hsgac.senate.gov/wp-content/uploads/imo-media/doc/2013-0315-jpmorgan-whale-report.pdf); accessed 2026-08-23
- [SEC Press Release 2022-46: Barclays charged $200M over unregistered offers of securities](https://www.sec.gov/newsroom/press-releases/2022-46); accessed 2026-08-23
- [SEC Administrative Proceeding: In re Knight Capital America LLC (2013)](https://www.sec.gov/litigation/admin/2013/34-70694.pdf); accessed 2026-08-23
- [Zillow Group (Nov 2021). Zillow Offers wind-down announcement and Q3 2021 results](https://investors.zillowgroup.com/investors/news-and-events/news/news-details/2021/Zillow-Group-Reports-Third-Quarter-2021-Financial-Results-Announces-Wind-Down-of-Zillow-Offers/default.aspx); accessed 2026-08-23
- [Interagency Guidance on Third-Party Relationships (June 2023)](https://www.federalreserve.gov/newsevents/pressreleases/files/bcreg20230607a1.pdf); accessed 2026-08-23
- [NIST AI Risk Management Framework 1.0 (Jan 2023) + GenAI Profile (July 2024)](https://www.nist.gov/itl/ai-risk-management-framework); accessed 2026-08-23

## Changelog

- 2026-08-23 — created




