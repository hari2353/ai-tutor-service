# Model Risk Management: SR 26-2, Validation, Governance, and the MRM Engineering Role

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-risk-metrics (VaR/PD models are the classic validated-model example), T24-basel (regulatory context)
> **Module id:** `T24-mrm` · **Tags:** banking, critical
> **Lab:** `labs/python/09-mrm/`

## The 30-second version

Model Risk Management is the discipline of treating "the model might be wrong" as a first-class, governed risk category, not an engineering afterthought — every model gets inventoried, tiered by materiality, validated by someone independent of whoever built it (conceptual soundness, outcomes analysis, ongoing monitoring), and subjected to **effective challenge**, meaning the independent reviewer has real authority to block deployment, not just the ability to write a critique that gets ignored. As of 2026, US MRM practice runs on **SR 26-2** (issued jointly by the Fed, OCC, and FDIC on **April 17, 2026**), which **rescinded and replaced both SR 11-7** (the April 2011 guidance that governed MRM for fifteen years) **and SR 21-8** (2021, BSA/AML-specific MRM) — the change moved from SR 11-7's blanket annual-revalidation habit to a **materiality- and change-velocity-driven** validation cadence, sharpened the definition of "model" to a three-prong test (complex quantitative method + statistical/economic/financial theory + quantitative output, explicitly excluding spreadsheets and deterministic rule engines), and strengthened effective challenge to require genuine organizational standing, not just technical sign-off. The single most consequential — and most interview-relevant — detail: **SR 26-2 explicitly excludes generative AI, RAG systems, and agentic AI from its formal "model" definition**, citing that the technology is "novel and rapidly evolving," even while traditional ML (classifiers, gradient-boosted models, neural networks used for credit and fraud decisions) remains squarely in scope — creating a real governance gap that examiners and prudent banks are filling voluntarily, since an agentic AI system that can move money doesn't stop carrying real financial risk just because it falls outside a regulatory definition written in 2026 for a still-evolving technology. For a Principal AI engineer, MRM is where a huge share of the actual day-to-day work sits: building the model inventory and automated materiality-tracking system, the validation and drift-monitoring infrastructure, and — increasingly — the evaluation and red-teaming harnesses that a framework built in 2011 around interpretable regression models was never designed to validate.

## Why this gets asked

Anyone who has sat inside or adjacent to a bank's model risk function has watched a model get shipped, quietly drift, and cause real financial or regulatory damage before anyone with the authority to stop it noticed — and has separately watched a well-intentioned validation process degrade into a compliance-checkbox exercise that burns capacity on trivial models while the genuinely dangerous ones sail through. The interviewer wants to know whether you understand MRM as a governance and organizational-design problem (who has the authority, when does review actually happen, what triggers escalation) as much as a technical one, and — increasingly in 2026 — whether you've actually thought about the specific, uncomfortable gap between a framework built for regression models and the LLM/agentic systems a Principal AI engineer is now shipping into production at a bank, rather than assuming "model risk management" is a solved problem that predates and doesn't apply to your work.

---

## Lineage: past → present → future

**What came before.** Before 2011, model risk in US banks was handled ad hoc, siloed within individual business lines — credit risk models were reviewed (if at all) by credit teams using whatever internal standard existed, market-risk VaR models were separately subject to Basel's 1996 backtesting regime, and there was no unified, firm-wide definition of what counted as a "model," no consistently mandated independent validation function, and no common lifecycle framework across an institution. The 2008 financial crisis exposed exactly this gap in the most consequential way possible: mortgage-related valuation and rating models (for MBS, CDOs, and the credit ratings built on top of them) were deeply flawed, but no independent, empowered effective-challenge process forced critical review before those models drove trillions of dollars of exposure across the financial system. The Federal Reserve and OCC's direct response was **SR 11-7** ("Guidance on Model Risk Management," April 4, 2011) — the first unified, firm-wide US standard, establishing the model lifecycle framework (development, implementation, use, validation) and the three-pillar validation approach still recognizable today.

**Where it stands now.** SR 11-7 governed US bank model risk management for fifteen years, and its three-pillar validation structure and broad definition of "model" (a quantitative method applying statistical, economic, financial, or mathematical theory) became the de facto global template — cited as the reference standard well beyond the US, echoed in EU supervisory practice (the ECB's Targeted Review of Internal Models, TRIM) and in countless banks' internal policies worldwide regardless of jurisdiction. But fifteen years of accumulated supervisory experience surfaced real friction: mandatory, calendar-driven revalidation regardless of a model's actual materiality became, in practice, a compliance exercise that consumed validation-team capacity on trivially low-risk models while high-risk, fast-changing machine-learning models didn't reliably get proportionally more scrutiny; SR 11-7's broad model definition swept in simple spreadsheets and deterministic calculators, adding inventory overhead without corresponding risk reduction; and the rapid, bank-wide adoption of machine learning, and starting around 2023, generative AI for credit decisioning, fraud detection, customer-facing assistants, and now agentic workflows, exposed that a framework built around interpretable, regression-style models didn't map cleanly onto ensemble and deep-learning methods, let alone onto large language models. The Federal Reserve, OCC, and FDIC jointly issued **SR 26-2** ("Revised Guidance on Model Risk Management," April 17, 2026), which **rescinds and replaces both SR 11-7 and SR 21-8** outright. It formally scopes applicability to banking organizations with **over $30 billion in total assets** as the institutions where the guidance is "expected to be most relevant" (a materiality threshold SR 11-7 never stated explicitly), replaces blanket annual revalidation with a cadence driven by materiality, change velocity, and data availability, sharpens the model definition to a three-prong test that excludes simple arithmetic and deterministic rule engines lacking statistical/economic/financial theory, strengthens effective challenge to require genuine organizational standing and authority to halt deployment, and — the detail that matters most for an AI engineer reading this in 2026 — **explicitly excludes generative AI, RAG systems, and agentic AI** from the formal "model" definition, citing their novel and rapidly evolving nature, while leaving traditional ML squarely in scope.

**Where it's heading.** With high confidence, banks and MRM tooling vendors are moving in 2026 to voluntarily extend MRM-equivalent governance to generative and agentic AI systems even though SR 26-2 doesn't formally require it (this is the explicit thrust of the OCC's companion 2026-13 guidance and the direction of the emerging MRM-tooling vendor landscape), because the underlying prudential and reputational risk from an LLM-driven decisioning system or a money-moving agentic AI doesn't disappear just because it falls outside a regulatory definition — and examiners are expected, in supervisory practice, to scrutinize AI governance broadly even absent a rule specifically compelling it. With moderate confidence, expect a dedicated interagency statement or SR letter specifically addressing generative and agentic AI governance within the next several years — SR 26-2's own carve-out language, explicitly citing the technology's rapid evolution as the reason for exclusion, signals that regulators see this as a deliberate, temporary gap rather than a permanent judgment that these systems pose no model risk, and are waiting for supervisory experience and industry practice to mature before writing rules they'd have to quickly revise.

---

## Mental model

```
MODEL LIFECYCLE (SR 26-2, same skeleton as SR 11-7):

  DEVELOPMENT --> IMPLEMENTATION --> USE --> ONGOING MONITORING --> RETIREMENT
       |                                          |
       v                                          v
  independent VALIDATION at each stage      drift/performance triggers
  (conceptual soundness, outcomes           can force RE-VALIDATION
   analysis, ongoing monitoring)            (materiality-driven, not
                                             a fixed annual calendar)

MATERIALITY TIERING (SR 26-2's central organizing idea):

  MODEL EXPOSURE ($ magnitude of decisions driven)
        x
  MODEL PURPOSE (regulatory-critical vs internal decision-support)
        x
  INHERENT RISK (complexity, novelty, degree of automation)
        =
  TIER  -->  HIGH materiality: intensive validation, frequent review, deep effective challenge
        -->  LOW materiality:  lightweight controls + automated "is this becoming material?" trigger

THE 2026 STRAIN POINT:

  regression / PD-LGD models  -->  fits SR 26-2's 3-prong "model" test cleanly, in scope
  gradient-boosted / neural net (credit, fraud)  -->  in scope, but "conceptual soundness"
                                                        review has no equation to inspect
  generative AI / RAG / agentic AI  -->  FORMALLY EXCLUDED from SR 26-2's model definition
                                          ("novel, rapidly evolving") -- real financial risk,
                                          genuine governance gap unless extended voluntarily
```

The one-line mental model: **SR 26-2 replaced a one-size-fits-all annual-checklist framework with a materiality-driven one, but it also drew its formal boundary right where the newest, fastest-growing category of financial-decisioning technology sits — which means the most important MRM engineering work in 2026 is voluntarily extending the framework's substance to systems its own letter doesn't formally reach.**

---

## How it actually works

### The three validation pillars

**Conceptual soundness** asks whether the model's design, assumptions, and theoretical basis are appropriate for its intended use — for a logistic-regression probability-of-default model, this means literally inspecting the estimated coefficients, checking sign and magnitude against economic intuition, and reviewing the variable-selection rationale. **Outcomes analysis** checks whether the model's actual performance holds up against realized outcomes — backtesting predictions against what actually happened, benchmarking against a simpler or alternative ("challenger") model, and quantifying the gap. **Ongoing monitoring** tracks whether performance remains sound after deployment, as the underlying data and population continue to shift — this is the pillar that never really finishes, unlike the other two, which are heaviest at initial validation.

These three pillars are unchanged in substance between SR 11-7 and SR 26-2 — what changed is *when* and *how intensively* they're applied.

### What counts as a "model" under SR 26-2's three-prong test

SR 26-2 defines a model as **(1)** a complex quantitative method or system, **(2)** that applies statistical, economic, or financial theory, **(3)** to process input data into quantitative estimates. All three prongs must hold. This explicitly **excludes** simple arithmetic calculations (including spreadsheets that just apply fixed formulas), and deterministic rule-based processes or software with no underlying statistical, economic, or financial theory — a spreadsheet that sums a fee schedule against a fixed rate table is no longer formally inventory-worthy, closing a source of compliance overhead that added inventory volume without corresponding risk reduction under SR 11-7's broader wording. A spreadsheet that implements a regression-derived pricing adjustment, by contrast, still satisfies all three prongs and remains squarely in scope — the exclusion targets pure arithmetic and lookup logic, not the computational medium.

### Materiality-based tiering and the retirement of blanket annual revalidation

SR 26-2 reframes the entire oversight intensity question around **materiality** — a combination of **model exposure** (the dollar magnitude of the decisions the model drives) and **model purpose** (is it critical to regulatory reporting, or purely internal decision support), modulated by the model's **inherent risk** (complexity, novelty, degree of automation). High-materiality models get intensive oversight: frequent validation, deep effective challenge, close monitoring. Genuinely immaterial models can sit in the inventory with lightweight controls — **provided there is an automated mechanism to detect if and when they become material** (usage or dollar exposure growing beyond an initial pilot scope, for instance). Validation *frequency* itself is now a function of materiality, change velocity (how often the model or its inputs change), and data availability, with **explicit triggers** for re-review — a significant population shift, a monitoring alert, a material retraining event — replacing SR 11-7-era practice's default of routine, often-annual revalidation regardless of actual risk. Done correctly, this means a continuously-retrained, high-materiality fraud model gets *more* frequent review than a fixed annual calendar would have given it, while a static, low-materiality internal tool correctly gets less.

### Effective challenge, strengthened

Effective challenge is the requirement that model review be genuinely independent and critical — done by people with the incentive, competence, *and authority* to identify flaws and force real changes, not a rubber-stamp exercise. SR 26-2 strengthens this explicitly: independent reviewers must have **real organizational standing and resources to effect actual change** — including the authority to halt or delay deployment when a material risk is unmitigated — rather than merely the ability to author a technical critique that a business or technology team can override unilaterally. The practical organizational-design implication: a Chief Model Risk Officer (or equivalent) needs a genuine seat at the model-deployment decision table, ideally with real escalation or veto authority reaching executive management, not an advisory sign-off buried inside a larger approval workflow.

### Why generative and agentic AI sit outside SR 26-2's formal scope, and why that matters

SR 26-2's model definition, applied literally, struggles to cleanly capture a large language model: is a fine-tuned LLM a "complex quantitative method applying statistical... theory"? Arguably yes in a loose sense, but the *validation methodology* built around the three pillars assumes something closer to an inspectable, relatively stable statistical model — and the agencies chose to **explicitly exclude generative AI, RAG systems, and agentic AI** from the formal definition, citing their "novel and rapidly evolving" nature, rather than force-fit them into a framework built around 2011-era regression and scorecard models. Traditional machine learning — classifiers, gradient-boosted models, neural networks used for credit underwriting or fraud detection — **remains fully in scope**, since these systems, while less inspectable than a regression, still fit the three-pillar validation approach reasonably well (they have a stable training process, a well-defined prediction target, and standard performance metrics to backtest). The practical risk is that a team reads the GenAI carve-out as "no governance required" — but an agentic AI system with authority to initiate a wire transfer, or an LLM-based assistant influencing a lending decision, carries real prudential and reputational risk to the institution regardless of its formal regulatory categorization, and bank examiners, in supervisory practice, scrutinize AI governance broadly even where no rule specifically compels it.

### Where the traditional model-risk taxonomy strains against ML and LLM failure modes

SR 11-7-era model risk was typically decomposed into **input error** (bad or stale data), **specification error** (the model's theoretical structure is wrong for the problem), **estimation/implementation error** (a bug or estimation flaw in fitting the model), and **use error** (deploying a sound model for a purpose it wasn't validated for) — categories built with fairly clean, separable causes in mind, assuming a model with legible internal logic. An LLM's **hallucination** — a fluent, confident, wrong output — doesn't map cleanly onto any single one of these: the prompt and context can be entirely correct (no input error), there's no small set of economic or statistical assumptions to inspect for a specification-error review, and it's rarely a discrete implementation bug either. It behaves more like an emergent property of a probabilistic generative process interacting with an underspecified evaluation surface, and sound LLM-adjacent governance in practice supplements the traditional taxonomy with LLM-specific risk categories — hallucination/factual-accuracy risk, prompt-injection and adversarial-input risk, guardrail-bypass risk, training-data provenance and contamination risk — that have no clean SR-11-7-era analogue.

---

## Build it from scratch

```python
# untested sketch -- illustrates the SR 26-2 three-prong test and materiality-tiering logic
from dataclasses import dataclass
from datetime import date, timedelta

@dataclass
class ModelCandidate:
    name: str
    is_complex_quant_method: bool
    applies_stat_econ_fin_theory: bool
    produces_quantitative_estimate: bool
    dollar_exposure: float          # magnitude of decisions the system drives, annualized
    is_regulatory_critical: bool
    inherent_risk_score: float      # 0-1, complexity/novelty/automation composite
    change_velocity_days: int       # typical days between material retrains/changes
    formally_excluded_category: str = None   # e.g. "generative_ai", "agentic_ai", None

def sr262_model_test(m: ModelCandidate) -> bool:
    """Three-prong test: is this in scope of SR 26-2's formal 'model' definition?"""
    return (m.is_complex_quant_method
            and m.applies_stat_econ_fin_theory
            and m.produces_quantitative_estimate)

def materiality_tier(m: ModelCandidate) -> str:
    exposure_score = min(m.dollar_exposure / 100_000_000, 1.0)   # normalize vs $100M reference
    purpose_score = 1.0 if m.is_regulatory_critical else 0.5
    composite = (exposure_score * 0.5 + purpose_score * 0.25
                 + m.inherent_risk_score * 0.25)
    if composite >= 0.7:
        return "high"
    elif composite >= 0.35:
        return "medium"
    return "low"

def next_validation_due(m: ModelCandidate, last_validated: date) -> date:
    tier = materiality_tier(m)
    base_interval = {"high": 90, "medium": 180, "low": 365}[tier]
    # faster change velocity shortens the interval further, materiality never lengthens it
    interval = min(base_interval, max(30, m.change_velocity_days * 2))
    return last_validated + timedelta(days=interval)

def governance_recommendation(m: ModelCandidate) -> str:
    in_formal_scope = sr262_model_test(m)
    if m.formally_excluded_category:
        return (f"OUTSIDE SR26-2's formal 'model' definition ({m.formally_excluded_category}) -- "
                f"apply MRM-EQUIVALENT governance voluntarily, scaled to actual business risk "
                f"(exposure=${m.dollar_exposure:,.0f}), NOT skipped due to the formal carve-out.")
    if in_formal_scope:
        tier = materiality_tier(m)
        return f"IN SCOPE, tier={tier} -- apply full three-pillar validation at tier cadence."
    return "Excluded (simple arithmetic / deterministic rules, no underlying theory) -- no formal MRM inventory entry required."
```

A full runnable version — including a monitoring-drift trigger (population stability index thresholds that automatically force re-tiering and re-validation) — is the lab exercise in `labs/python/09-mrm/`.

---

## How it's done in production

Production MRM organizations run on a combination of a **model inventory/GRC system** (often a customized governance-risk-compliance platform, or vendor MRM tooling like SAS Model Risk Management, Wolters Kluwer OneSumX, or newer AI-specific validation platforms), a **validation workbench** where independent teams reproduce a model's development pipeline and run challenger/benchmark comparisons, and **ongoing monitoring dashboards** tracking drift metrics — Population Stability Index (PSI) for feature/population drift, AUC or KS-statistic decay for classifier performance degradation over time — that feed automated alerts back into the tiering and re-validation-trigger logic described above. The engineering-heaviest, least glamorous part of the job is almost always **reproducibility and audit-defensibility**: an independent validator, and ultimately an examiner, needs to be able to re-run a model's training pipeline against versioned data and get the same result, not just trust a static report — which drives real architecture decisions around data versioning, environment pinning, and access-controlled audit trails that a typical internal analytics pipeline doesn't need.

| Symptom | Cause | Fix |
|---|---|---|
| A materially important LLM-based system ships to production with no MRM-equivalent review at all | SR 26-2 formally excludes generative AI from its "model" definition, and teams read that as "no governance required," bypassing MRM entirely | Internal policy should require MRM-equivalent governance for GenAI/agentic systems gated by actual business risk (dollar exposure, decision criticality), not by whether the system meets SR 26-2's formal three-prong test |
| Validation team backlog balloons; high-materiality models go months without revalidation while low-risk deterministic calculators get reviewed on schedule | Legacy blanket-annual-revalidation habits from SR 11-7-era process haven't been re-tuned to SR 26-2's materiality-driven cadence | Rebuild the validation scheduling engine around the tiering matrix (materiality × change velocity × data availability) with automated trigger-based scheduling, not a fixed calendar |
| "Effective challenge" findings are documented but never actually change a model's deployment decision | Validators lack real organizational standing or escalation authority — exactly the gap SR 26-2's strengthened effective-challenge language targets | Give MRM leadership genuine authority in the model-deployment approval chain (real escalation path to executive management), not an advisory sign-off a business line can override unilaterally |
| A fine-tuned LLM's "conceptual soundness" review turns into an unproductive debate with no clear resolution | SR 11-7-era validation methodology assumes a mathematically inspectable model; a transformer has no equivalent closed form to check | Adapt conceptual-soundness review for ML/LLM systems around evaluation-harness design, training-data provenance, red-teaming coverage, and guardrail architecture, not equation-level derivation |
| The model inventory has quietly become unreliable — teams stopped registering internal decision-support scripts | Ambiguity or inconsistent application of the "model" definition boundary across teams | Apply SR 26-2's explicit three-prong test consistently, and re-baseline the inventory against it rather than leaving the boundary to individual teams' judgment |

---

## Tradeoffs & when NOT to use it

- **Don't apply full formal SR 26-2 validation rigor line-for-line to a genuinely low-risk internal tool.** Materiality-based tiering exists specifically so a low-exposure, non-regulatory-critical internal dashboard doesn't consume the same validation capacity as a credit-decisioning model — over-applying rigor uniformly is a real, avoidable engineering and validation-team cost, not a conservative safety margin.
- **Don't read SR 26-2's GenAI/agentic-AI carve-out as "no governance needed."** The exclusion reflects regulatory caution about writing premature, quickly-obsolete rules for a fast-moving technology, not a judgment that these systems pose no model risk — an agentic system with financial authority carries real risk regardless of its formal categorization, and skipping governance because "it's not technically a model" is a defensible-sounding argument that won't hold up to an examiner, a board, or an actual incident.
- **Don't force-fit LLM/GenAI validation into the exact SR-11-7-era three-pillar methodology unmodified.** "Conceptual soundness" review built around inspecting regression coefficients doesn't translate to a transformer with no equivalent closed form — the substance (independent, critical, empowered review) should carry over; the specific mechanics need genuine adaptation (evaluation harnesses, red-teaming, guardrail review), not a checkbox exercise pretending an LLM is a scorecard model.
- **Don't conflate MRM with a general AI-ethics or fairness program.** MRM specifically targets financial safety-and-soundness risk to the institution from model error — it overlaps meaningfully with fair-lending and explainability obligations (covered in the AI-in-finance module) but isn't a substitute for them, and a model can be perfectly "sound" under MRM's definition while still violating fair-lending law.
- **Don't assume an MRM-facing engineering role is purely a quant/statistics job.** A large share of the actual day-to-day work — inventory systems, materiality-tracking automation, drift-monitoring dashboards, reproducibility and audit-trail tooling, evaluation harnesses for LLM systems — is genuine software and data engineering, not model-building, and a Principal AI engineer's skill set maps directly onto it even without a quant-finance background.

---

## Interview questions

### Q1 — What is SR 26-2, and what did it replace?
**Testing:** currency — whether the candidate has kept up with the April 2026 change, not just SR 11-7 as historical fact.
**Answer:** SR 26-2, issued jointly by the Federal Reserve, OCC, and FDIC on April 17, 2026, is the revised interagency guidance on Model Risk Management. It supersedes and replaces both SR 11-7 (the April 2011 guidance that governed US bank MRM for fifteen years) and SR 21-8 (2021, BSA/AML-specific model risk guidance), consolidating both into a single, risk-based, materiality-driven framework.
**Follow-up trap:** *"Does SR 26-2 apply to every US bank the way SR 11-7 did?"* — no; SR 26-2 states explicitly it is "expected to be most relevant" to banking organizations with over $30 billion in total assets, an explicit materiality/size scoping SR 11-7 never stated, though smaller institutions can still be examined against its principles proportionally to their risk profile.

### Q2 — State SR 26-2's three-prong test for what counts as a "model," and give a concrete example of something newly excluded.
**Testing:** precise knowledge of the updated definition, not just "it's still a model if it's quantitative."
**Answer:** A model must be (1) a complex quantitative method or system, (2) that applies statistical, economic, or financial theory, (3) to process input data into quantitative estimates. This explicitly excludes simple arithmetic/spreadsheet calculations and deterministic rule-based processes with no underlying statistical/economic/financial theory — e.g., a spreadsheet that sums a fixed fee schedule against a fixed rate table is no longer formally an inventory-worthy model.
**Follow-up trap:** *"Does that mean spreadsheets are entirely outside model risk governance now?"* — no; a spreadsheet implementing a regression-derived pricing adjustment or an internally-derived statistical calculation still satisfies all three prongs and stays in scope — the exclusion targets pure arithmetic/lookup logic, not the spreadsheet-as-medium itself.

### Q3 — Walk through the three pillars of model validation, and identify which is hardest to execute for a deep learning model versus a logistic regression.
**Testing:** whether validation is understood mechanically, and whether the ML-specific difficulty is genuinely understood.
**Answer:** Conceptual soundness (design/assumptions/theoretical basis appropriate for intended use), outcomes analysis (backtesting/benchmarking against realized outcomes), ongoing monitoring (does performance hold up post-deployment as data shifts). Conceptual soundness is hardest for deep learning: a regression's soundness review can inspect actual estimated coefficients and economic rationale directly; a neural network or gradient-boosted ensemble has no equivalently inspectable closed form, so review has to shift toward architecture justification, training-data provenance, and evaluation-harness design.
**Follow-up trap:** *"If conceptual soundness can't be reviewed the same way, does that mean deep learning models can't really be validated under this framework?"* — no, it means the mechanics of that specific pillar need adaptation, not abandonment; outcomes analysis and ongoing monitoring translate reasonably well to ML models (they still have stable training processes and measurable performance metrics to backtest), so the framework degrades gracefully for traditional ML even where one pillar needs rework — it strains far more severely, as covered later, for generative and agentic AI.

### Q4 — What changed about validation frequency between SR 11-7 and SR 26-2?
**Testing:** the practical operational change, not just "it got more flexible."
**Answer:** SR 11-7-era practice defaulted to routine, often-annual revalidation regardless of a model's materiality. SR 26-2 reframes frequency as a function of materiality, change velocity, and data availability, with explicit triggers for re-review (a material population shift, a monitoring alert, a significant retraining event) rather than a blanket calendar cadence.
**Follow-up trap:** *"Doesn't removing mandatory annual revalidation risk high-risk models going unchecked for years?"* — not if implemented correctly: a high-materiality, high-change-velocity model (e.g. a continuously retrained fraud model) should see *more* frequent review under a materiality-and-velocity-driven cadence than a fixed annual calendar ever gave it — the risk is entirely in poor implementation (using the new flexibility to under-review genuinely high-risk models), not in the design intent of the change itself.

### Q5 — What is "effective challenge," and how did SR 26-2 strengthen it?
**Testing:** understanding independence as an organizational-authority question, not just a technical-review question.
**Answer:** Effective challenge requires model review to be genuinely independent and critical — done by reviewers with the incentive, competence, and authority to identify flaws and force real changes, not a rubber-stamp. SR 26-2 strengthens this by requiring independent reviewers to have real organizational standing and resources to effect actual change, including authority to halt deployment when material risk is unmitigated, not merely the ability to author a critique a business line can override.
**Follow-up trap:** *"What's the practical org-design implication for a Chief Model Risk Officer?"* — MRM leadership needs a genuine seat at the model-deployment decision table with real escalation or veto authority to executive management, not an advisory sign-off buried inside a larger approval workflow that business or technology leadership can override unilaterally.

### Q6 — Explain SR 26-2's materiality-based tiering, and what engineering capability its "detect when a model becomes material" requirement forces.
**Testing:** whether tiering is understood as requiring live monitoring infrastructure, not a one-time assessment.
**Answer:** Materiality combines model exposure (dollar magnitude of decisions driven) and model purpose (regulatory-critical vs internal decision support), modulated by inherent risk. High-materiality models get intensive oversight; genuinely immaterial models get lightweight controls, provided there's a mechanism to detect if they become material. The engineering implication: model inventory and monitoring systems need automated, ongoing tracking of usage/exposure metrics for every registered model, not a one-time materiality assessment at launch — a model that starts as a small pilot but scales to drive a large share of decisions needs to trigger an automatic re-tiering event, a genuine monitoring build, not a paperwork process.
**Follow-up trap:** *"What happens if a model's exposure grows gradually rather than in a single obvious jump — how do you avoid missing the re-tiering trigger?"* — set the monitoring on a rolling-window exposure metric with a threshold crossing alert (not a point-in-time snapshot compared only at review time), so gradual creep past the materiality boundary triggers the same automated re-tiering event a sudden jump would — the failure mode to avoid is relying on a human noticing gradual growth during an infrequent scheduled review.

### Q7 — Why does SR 26-2 explicitly exclude generative AI, RAG, and agentic AI from its formal "model" scope, and what's the practical risk of over-reading that exclusion?
**Testing:** the module's central 2026-currency point — whether the candidate understands both the regulatory logic and the practical governance risk.
**Answer:** The agencies cite these technologies as "novel and rapidly evolving" — a deliberate choice to avoid writing detailed, binding validation rules for a technology whose architecture and failure modes are still actively changing, since premature rules risk becoming quickly obsolete. The practical risk of over-reading the exclusion as "no governance needed": an agentic AI system that can move money or influence a lending decision carries real prudential and reputational risk regardless of whether it formally satisfies the three-prong "model" test, and examiners scrutinize AI governance broadly in practice even absent a binding rule.
**Follow-up trap:** *"Should a bank apply full SR 26-2-style validation, unmodified, to every LLM feature it ships?"* — not full formal rigor line-for-line, since LLM/GenAI systems don't fit the traditional methodology cleanly (no equivalent to inspecting regression coefficients) — but the *substance* of governance (independent evaluation, red-teaming, ongoing drift monitoring, clear deployment accountability) should be applied proportionally to actual business risk, adapted in method, not skipped because of the formal scope carve-out.

### Q8 — What does SR 26-2's guidance actually mean for an MRM-facing AI/ML engineer's day-to-day work?
**Testing:** whether MRM is understood as a genuine engineering discipline, not purely a quant/compliance function.
**Answer:** Building and maintaining the model inventory system and its automated materiality/exposure-tracking mechanism, building validation infrastructure (backtesting harnesses, champion-challenger pipelines, drift-monitoring dashboards using PSI or AUC/KS decay), building documentation and audit-trail tooling that lets independent validators reproduce and test a model rather than trust a static report, and increasingly, building evaluation and red-teaming harnesses for LLM/GenAI systems that traditional quant validation teams don't yet have the tooling for.
**Follow-up trap:** *"Isn't that just data engineering with extra paperwork?"* — the real differentiator is that everything must be built with independent reproducibility and audit-defensibility as first-class requirements from the start — a validator or examiner needs to be able to independently re-run and challenge a result, not just trust a dashboard — which materially changes design choices around data versioning, environment pinning, and access control compared to a typical internal analytics pipeline.

### Q9 — How does the traditional model-risk taxonomy (input, specification, estimation/implementation, use error) map onto an LLM's hallucination failure mode?
**Testing:** genuine understanding of where the 2011-era conceptual framework strains against modern generative systems.
**Answer:** These categories assume a model with legible internal logic and separable failure causes. A hallucination — a fluent, confident, wrong output — doesn't map cleanly onto any of them: the prompt/context can be entirely correct (no input error), there's no small set of assumptions to inspect for specification error, and it's rarely a discrete implementation bug. It's closer to an emergent property of a probabilistic generative process interacting with an underspecified evaluation surface than to any single traditional category.
**Follow-up trap:** *"Does that mean the traditional taxonomy is useless for LLM systems?"* — not useless, but insufficient alone; sound LLM-adjacent governance supplements it with LLM-specific risk categories — hallucination/factual-accuracy risk, prompt-injection risk, guardrail-bypass risk, training-data provenance risk — that have no clean SR-11-7-era analogue, which is precisely the strain this question is testing for.

### Q10 (staff/design) — Design MRM-equivalent governance for a new agentic AI system that can autonomously initiate wire transfers under a defined authority limit, even though SR 26-2 formally excludes agentic AI from its scope. How do you argue for the investment?
**Testing:** staff-level synthesis — translating the module's regulatory-gap content into a concrete, defensible engineering and governance program.
**Answer:** Build proportional to actual business risk, not to the letter of SR 26-2's scope: an inventory entry with materiality/exposure tracking (dollar authority limit × transaction frequency, the same "model exposure" concept SR 26-2 uses for in-scope models); an independent evaluation and red-teaming function specifically testing prompt-injection, unauthorized-action, and guardrail-bypass scenarios; ongoing monitoring for behavioral drift and anomalous transaction patterns; and a genuine effective-challenge mechanism with real authority to pause the system's autonomous authority if monitoring flags a problem. Argue for the investment on prudential and reputational-risk grounds independent of the regulatory carve-out: a failed or exploited money-moving agentic system creates direct financial loss and examiner-relationship damage regardless of its formal regulatory categorization, and the carve-out's own "novel, rapidly evolving" language signals dedicated guidance is likely coming, making early investment a defensible hedge rather than a purely discretionary cost.
**Follow-up trap:** *"Leadership pushes back that this isn't legally required, so it's wasted engineering effort — how do you respond?"* — reframe away from "regulatory compliance" and toward "operational risk control for an autonomous system with financial authority": the same segregation-of-duties, transaction-limit, and independent-audit controls a bank would already require for a *human* employee with wire-transfer authority apply with at least equal force to a non-human agent holding the same authority — that framing typically lands with risk-conscious leadership even without a specific SR-letter citation to point to.

---

## Red flags that fail you

- Cites SR 11-7 as current US guidance without knowing it was rescinded and replaced by SR 26-2 in April 2026.
- Claims SR 26-2 applies uniformly to every bank regardless of size, missing the ~$30B total-assets relevance threshold.
- Treats generative AI/agentic AI's exclusion from SR 26-2's formal model definition as meaning no governance is needed.
- Cannot explain why validation frequency moved away from blanket annual revalidation, or frames the change as "less rigorous" rather than "differentiated by materiality."
- Describes effective challenge as purely a technical-review concept without mentioning organizational authority/standing.
- Treats MRM as a compliance-only function unrelated to actual software/data engineering work.

---

## Cheat card

```
SR 26-2 (Apr 17 2026, Fed+OCC+FDIC): supersedes SR 11-7 (2011) AND SR 21-8 (2021, BSA/AML MRM)
  applicability: "most relevant" to banking orgs with >$30B total assets (SR 11-7 had no such threshold)

MODEL DEFINITION (3-prong test): (1) complex quantitative method/system (2) applies
  statistical/economic/financial theory (3) processes inputs into quantitative estimates
  EXCLUDES: simple arithmetic/spreadsheets, deterministic rule engines w/ no underlying theory
  EXCLUDES FORMALLY: generative AI (LLMs, diffusion), RAG, agentic AI -- "novel, rapidly evolving"
  STILL IN SCOPE: traditional ML -- classifiers, GBMs, neural nets used for credit/fraud

3 VALIDATION PILLARS (unchanged since SR11-7): conceptual soundness, outcomes analysis, ongoing monitoring
VALIDATION FREQUENCY: SR11-7 habit = blanket annual revalidation. SR26-2 = f(materiality, change
  velocity, data availability), explicit re-review triggers, NOT a fixed calendar

MATERIALITY/TIERING: exposure ($ magnitude of decisions) x purpose (regulatory vs internal) x
  inherent risk. High-materiality = intensive oversight. Immaterial = light controls +
  REQUIRED automated mechanism to detect when an immaterial model becomes material

EFFECTIVE CHALLENGE (strengthened): independent reviewers need real ORGANIZATIONAL STANDING +
  authority to halt deployment, not just technical critique power

LINEAGE: pre-2011 = ad hoc per business line, no unified standard -> SR 11-7 (Apr 2011, post-2008
  response) -> 15 yrs supervisory experience -> SR 26-2 (Apr 2026)

MRM ENGINEERING DAY-TO-DAY: model inventory + automated exposure/materiality tracking, validation
  infra (backtesting, champion-challenger, drift dashboards: PSI, AUC/KS decay), audit-trail/
  reproducibility tooling for independent validators, LLM eval harnesses + red-teaming

LLM/ML STRAIN ON THE FRAMEWORK: no inspectable closed form for "conceptual soundness"; continuous
  retraining breaks static-model backtesting assumptions; hallucination doesn't map cleanly to
  input/specification/estimation/use-error taxonomy; GenAI formally OUT of SR26-2 scope -->
  real governance gap unless banks extend MRM-equivalent controls voluntarily
```

## Sources

- [SR 26-2: Revised Guidance on Model Risk Management — Board of Governors of the Federal Reserve System (April 17, 2026)](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) — accessed 2026-08-08
- [SR 11-7: Guidance on Model Risk Management — Board of Governors of the Federal Reserve System (April 4, 2011)](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm) — accessed 2026-08-08
- [Federal Banking Agencies Issue Revised Guidance on Model Risk Management — Sullivan & Cromwell LLP (April 2026)](https://www.sullcrom.com/insights/memo/2026/April/OCC-Fed-FDIC-Issue-Revised-Guidance-Model-Risk-Management) — accessed 2026-08-08
- [SR 11-7 vs. SR 26-2: Model Risk Management Modernization — Sia Partners (2026)](https://www.sia-partners.com/en/insights/publications/sr-11-7-vs-sr-26-2-model-risk-management-modernization) — accessed 2026-08-08
- [Updated Interagency Guidance on Model Risk Management (SR 26-2) — Baker Tilly (2026)](https://www.bakertilly.com/insights/updated-interagency-guidance-on-model-risk-management) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
