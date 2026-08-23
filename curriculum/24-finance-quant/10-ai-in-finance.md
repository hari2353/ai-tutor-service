# AI in Finance: Fraud, Credit, AML, Explainability & Fair-Lending Constraints

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** T24-mrm · **Updated:** 2026-08-23
> **Module id:** `T24-ai-in-finance` · **Tags:** ai, critical

## The 30-second version

Finance deploys ML where errors cost money AND carry legal exposure, so every model lives inside two constraint systems: statistical (class imbalance, drift, adversarial adaptation) and regulatory (ECOA/Reg B reason-giving, fair-lending disparate impact, EU AI Act high-risk classification from August 2026). Fraud detection fights base rates — fraud sits near 0.1% of transactions, so 99% accuracy is table stakes and the real work is precision/recall tradeoffs under <100ms latency budgets against adaptive adversaries; global card fraud runs ~$33-34B/year (Nilson). Credit scoring is the most litigated ML application alive: models must produce specific adverse-action REASONS (Reg B), survive disparate-impact analysis even when no protected attribute enters the feature set (proxy discrimination via zip code/transaction history is the core failure mode), and satisfy CFPB Circular 2022-03's demand for "legally sufficient justification." AML is inverted imbalance: rule-based transaction monitoring drowns in 90-95%+ false-positive alerts while missing networks, pushing banks toward graph analytics — with HSBC's $1.9B (2012) as the cautionary spend-more figure. The unifying skill interviewers probe: can you explain a model decision in regulator-grade language (SHAP mapped to reason codes, counterfactuals) and audit it for fairness (adverse-impact ratios, equalized odds) knowing Kleinberg-Chouldechova impossibility means you must CHOOSE which fairness definition to break?

## Why this gets asked

Because banking GenAI and ML JDs (Citi VP GenAI, Optum VP, D.E. Shaw adjacent roles) all sit exactly here — teams shipping AI into regulated decisions need engineers who read compliance docs, not just leaderboards. Interviewers test three distinct competencies in one pass: production statistics ("your fraud model catches 80% of fraud — is that good?" depends entirely on alert capacity, review costs, and customer-friction budgets), legal fluency ("can you use zip code?" — only if you can defend necessity and monitor proxy effects; "what goes in an adverse-action letter?" — specific principal reasons, not model internals), and judgment under impossibility results (calibration-across-groups vs equal error rates cannot both hold when base rates differ — pick, document, defend). Candidates who mention SR 11-7 inventory, EU AI Act timelines, and SHAP-to-reason-code mapping signal they've operated in this world; candidates who say "we'd use XGBoost because accuracy" reveal they haven't met a lawyer yet.

## Lineage

**What came before.** Credit scoring predates ML: FICO-style scorecards (logistic regression on binned features, points-based) industrialized after the 1956 founding of Fair Isaac; ECOA (1974) and FHA (1968) wrote fairness into law with protected classes and adverse-action duties. Fraud fighting ran on expert rules (velocity limits, country blocks); AML on the Bank Secrecy Act (1970) regime of thresholds, watchlists, and SAR filings. The 2010s brought gradient boosting everywhere, plus the first governance collisions: Apple Card's 2019 credit-limit controversy (NYDFS investigated gender disparity in Goldman-issued limits; closed March 2021 — no unlawful discrimination found, but transparency/appeals criticized) became the canonical "explainability meets viral scrutiny" case.

**Where it stands now.** Three tracks run hot simultaneously. Fraud: graph neural networks and device/behavioral biometrics against synthetic identity and account-takeover waves; real-time scoring budgets of 100-150ms end-to-end. Credit: challenger GBMs over scorecards with SHAP-derived reason codes, CFPB Circular 2022-03 requiring legally sufficient justification for complex models, and Upstart's no-action-letter era (2017-2022) as the alternative-data test balloon. AML: false-positive rates of 90-95%+ on rule engines force graph analytics and entity resolution; HSBC's $1.9B 2012 settlement and BNP Paribas' $8.9B 2014 sanctions penalty remain the budget-justifying precedents; Danske Bank's ~€200B Estonian suspicious flows showed what program failure at scale looks like. Meanwhile the governance stack crystallized: SR 11-7 absorbs AI models into inventory, NIST AI RMF provides vocabulary, ISO/IEC 42001 makes management systems auditable, and the EU AI Act classifies credit scoring of natural persons as HIGH-RISK with obligations biting August 2026.

**Where it's heading.** Four currents. First, explainability is becoming a legal artifact: reason-code generation pipelines (SHAP → mapped narrative reasons → Reg B letters) are production systems with their own validation. Second, GenAI enters constrained lanes — document processing, KYC summarization, analyst copilots — with hallucination treated as model-risk events (see T24-mrm) and human sign-off before customer impact. Third, fairness engineering industrializes: continuous disparate-impact monitoring dashboards, proxy-analysis tooling, and documented tradeoff choices per Kleinberg-Chouldechova impossibility. Fourth, regulation converges globally but unevenly: EU AI Act enforcement ramps through 2026-2027, US supervision stays examination-based (CFPB circulars + fair-lending law), UK runs principles-based (SS1/23) — multinationals build to the strictest common denominator.

---

## Mental model

```
EVERY FINANCE ML SYSTEM = STATISTICAL PROBLEM + LEGAL SHELL

fraud:   imbalance ~0.1% -> accuracy is a vanity metric
         optimize precision@alert-capacity under latency budget
         ADVERSARY ADAPTS: static models decay in months

credit:  decision + LEGAL REASONS required (Reg B adverse action)
         fairness is a DESIGN CONSTRAINT, not a post-hoc metric
         proxies: zip code ~ race; merchant mix ~ religion...

aml:     inverted problem: alerts are 90-95% false positives
         the object of study is NETWORKS not transactions

EXPLAINABILITY LADDER:
  scorecard points > SHAP attributions > counterfactuals
  ("too many recent inquiries" beats "feature 17 = -0.3")

FAIRNESS IMPOSSIBILITY (Kleinberg '16 / Chouldechova '17):
  calibration within groups  XOR  equal error rates across groups
  (when base rates differ) -- you must pick and document which
```

The unifying lens: in finance, model outputs are legal events. A declined loan, a frozen account, an SAR filing each trigger statutory clocks and rights — so the pipeline ends at an explanation generator and an audit log, not a probability.

---

## How it actually works

### Fraud detection — winning an adversarial game against base rates

The math: with fraud prevalence π = 0.1%, even 99.9% specificity yields one false alert per genuine fraud-scale transaction volume that dwarfs true catches — precision depends entirely on threshold placement against review capacity. Production stacks layer: rules (velocity, geo-mismatch — interpretable, instantly deployable), gradient-boosting scores on engineered features (amount z-scores vs customer baseline, device fingerprints, merchant risk history), graph signals (shared devices/accounts across "unrelated" applicants → synthetic identity rings), and behavioral biometrics. Latency budgets (~100-150ms) force feature precomputation into online stores. The adversary adapts: models trained on last quarter's fraud patterns decay as rings rotate tactics, so champion-challenger cycles run monthly-ish and drift monitors watch score distributions, not just labels (labels arrive late — chargebacks lag weeks). Cost-sensitive framing: a $500 fraud caught vs a good customer declined ($200 LTV + churn) sets the operating threshold; teams report expected-loss curves, not F1.

### Credit modeling — scorecards to GBMs inside a legal straightjacket

Modern flow: WoE-binned logistic scorecards (interpretable by construction: points per attribute map directly to reason codes) challenged by GBMs whose SHAP values get mapped to narrative reason codes for adverse-action letters. Regulatory requirements shape everything upstream: Reg B demands specific principal reasons within 30 days of adverse action (FCRA adds risk-based-pricing notices); CFPB Circular 2022-03 blocks "the algorithm did it" defenses — creditors need legally sufficient justification independent of model complexity; trade secrecy cannot hide from discovery. Fair lending operates through two doctrines: disparate treatment (intent; protected class used explicitly — rare) and disparate impact (neutral practice with discriminatory effect; upheld for lending contexts via Inclusive Communities, 2015). The engineering response: measure selection-rate ratios across protected classes (four-fifths guideline from EEOC Uniform Guidelines as the heuristic), hunt proxy features (geography, purchase patterns correlate with race/religion strongly enough that "no protected attributes" is never a defense), and document necessity justifications for any feature with proxy weight.

### AML — networks over transactions

Rule engines generate alerts from thresholds (cash >$10k structuring patterns, high-risk corridors); the industry's dirty secret is 90-95%+ false-positive rates, so investigation capacity becomes the binding constraint and real laundering slips through noise. The ML upgrade path: entity resolution (one criminal, 40 accounts/names/devices), graph anomaly detection (community detection surfacing mule networks invisible per-transaction), NLP on SAR narratives and adverse media, and risk-scoring alerts to prioritize analyst queues. Constraints differ from credit: no adverse-action duty, but BSA program requirements (independent testing, training, SAR timeliness — typically 30 days from detection) make recall-on-real-rings existential; HSBC's 2012 DPA ($1.9B: $1.256B forfeiture + penalties) remains the reference point for what program failure costs.

### Explainability — matching the technique to the audience

Four tiers serve four audiences: global feature importance (risk committees: "what drives this model"), local attributions (SHAP values per decision: analysts investigating cases), reason codes/narratives (regulators and customers: mapped, human-readable principal reasons — legally required artifacts), counterfactuals ("what would change the decision": increasingly favored because it's actionable and non-revealing of internals). Rules of thumb: SHAP on tree ensembles for internal analytics; scorecard points or constrained monotonic GBMs where letters demand clean reasons; counterfactual search (DiCE-style) for customer-facing appeals. GDPR Article 22's automated-decision rights push European deployments toward human-in-the-loop for consequential outcomes regardless of US law.

### Cross-industry AI governance: EU AI Act, ISO 42001, NIST RMF (~200 words)

The EU AI Act (Regulation 2024/1689, in force August 1, 2024) sorts systems into four risk tiers: prohibited (social scoring, manipulative techniques), HIGH-RISK — Annex III explicitly includes creditworthiness evaluation of natural persons and life/health insurance pricing, i.e., this module's core use cases — transparency-tier (chatbots must disclose they're AI), minimal. Timeline to memorize: prohibitions applied February 2, 2025; GPAI obligations August 2, 2025; the big one — high-risk Annex III obligations (risk management system, data governance, logging, human oversight, robustness) — applies August 2, 2026; embedded-product high-risk and pre-August-2025 GPAI compliance run to August 2, 2027. Penalties reach €35M or 7% of global turnover. ISO/IEC 42001:2023 adds a certifiable AI management system (AIMS): PDCA structure mirroring ISO 27001 with Annex controls spanning policy, roles, lifecycle, data governance, impact assessment, third parties. NIST AI RMF 1.0 (January 2023; GenAI Profile July 2024) contributes the four functions — GOVERN, MAP, MEASURE, MANAGE — that map almost one-to-one onto SR 11-7 machinery. The bank playbook: extend model inventory/tiering to LLM applications, archive eval-gate evidence as validation artifacts, classify hallucination as a model-risk event, and treat ISO/NIST/EU-AI-Act mappings as views over ONE governance dataset rather than three parallel programs.

---

## Build it from scratch

Fair-lending audit calculator on synthetic decisions (numpy only):

```python
import numpy as np

rng = np.random.default_rng(3)
N = 4000
group = rng.binomial(1, 0.35, N)                    # 1 = protected class
true_quality = rng.normal(0, 1, N)
# inject proxy harm: protected group's observed score carries a penalty
score = true_quality + group * -0.25 + rng.normal(0, 0.8, N)
threshold = np.quantile(score, 0.70)                # approve top 30%
approved = score >= threshold
repaid = true_quality > np.quantile(true_quality, 0.72)   # ground truth

def rates(mask):
    sel = approved[mask].mean()                     # selection rate
    tpr = approved[mask & repaid].mean()            # equal opportunity side
    fpr = approved[mask & ~repaid].mean()
    return sel, tpr, fpr

sel_g1, tpr_g1, fpr_g1 = rates(group == 1)
sel_g0, tpr_g0, fpr_g0 = rates(group == 0)

air = sel_g1 / sel_g0                               # adverse impact ratio
dp_diff = sel_g1 - sel_g0                           # demographic parity diff
eo_diff = tpr_g1 - tpr_g0                           # equal-opportunity diff

print(f"selection rates: protected {sel_g1:.1%} vs {sel_g0:.1%}")
print(f"AIR = {air:.2f}  ({'FAIL <0.80 four-fifths' if air < .80 else 'pass heuristic'})")
print(f"demographic-parity diff = {dp_diff:+.3f}")
print(f"equal-opportunity diff  = {eo_diff:+.3f}")

# calibration check within groups: predicted vs realized among approved
for g, name in [(0, "majority"), (1, "protected")]:
    m = approved & (group == g)
    print(f"{name}: approval-quality {repaid[m].mean():.1%} "
          f"(n={m.sum()}, base rate {repaid[group==g].mean():.1%})")

# counterfactual flip: how many flips fix AIR?
adj = score + 0.10 * group                          # remove injected penalty
flipped = (adj >= threshold) & ~approved
new_air = ((approved | flipped)[group==1].mean()) / sel_g0
print(f"after +0.10 counterfactual adjustment: AIR -> {new_air:.2f}, "
      f"{flipped.sum()} flipped decisions")
```

Reading it: the injected −0.25 proxy penalty drags the protected group's selection rate down and typically breaks the four-fifths guideline even though NO protected attribute entered the model — that is precisely how proxy discrimination manifests in production audits. The counterfactual block quantifies remediation cost ("how many decisions change if we neutralize this feature") which is what fair-lending remediation negotiations actually discuss.

---

## How it's done in production

**Fraud:** streaming feature stores + model ensembles behind a rules-first funnel; case-management systems feed investigator labels back for retraining; chargeback-lag-aware evaluation (delayed labels → delayed-feedback learning techniques); device-intelligence vendors alongside in-house models; sanctions/AML screening kept separate from card fraud ops.

**Credit:** scorecards still dominate regulated portfolios because reasons are native; GBM+SHAP challengers run under SR 11-7 validation with fairness dashboards (AIR by product/geo, monthly); adverse-action letter generation is a tested pipeline with legal-approved reason mappings; champion-challenger with guardrail metrics including selection-rate deltas.

**AML:** entity-resolution graphs + alert-scoring models prioritizing queues; SAR narrative NLP; tuning governance documented because threshold choices ARE risk appetite; FinCEN innovation-hours participation signals where the industry probes (privacy-preserving federated analytics across banks).

**Governance plumbing:** every fraud/credit/AML model sits in the SR 11-7 inventory with tiering; GenAI assistants get eval gates + hallucination event tracking (see T24-mrm's cross-industry subsection); EU AI Act readiness runs as a data-labeling exercise over the inventory ("which systems are Annex III high-risk?") feeding conformity documentation ahead of August 2026.

## Tradeoffs & when NOT to use it

- **Don't deploy complex models where reasons must be exact**: scorecard points or monotonic constrained models beat SHAP-post-hoc when letters face litigation — post-hoc explanations of black boxes are increasingly disfavored legally.
- **Fairness metrics conflict**: optimizing demographic parity can force approving riskier protected-class applicants (profitability hit), while equal opportunity preserves merit but tolerates selection gaps; impossibility means document the CHOICE with business/legal sign-off.
- **Fraud recall maximization is a trap**: every false positive costs LTV and creates manual review debt; optimize expected cost at capacity, not catch rates.
- **AML ML doesn't remove human investigators**: models prioritize; SAR narratives and law-enforcement referrals stay human-judged — full automation is both illegal-adjacent and operationally naive.
- **Proxy removal is not set-and-forget**: correlations drift; continuous disparate-impact monitoring is mandatory hygiene, not an annual audit checkbox.
- **LLMs in customer-facing credit conversations**: hallucinated terms create UDAAP exposure; keep generative components away from binding commitments without retrieval-grounded, validated pipelines.

## Interview questions

### Q1 — Your fraud model has 99% accuracy. Why is that number useless?
**Testing:** imbalance intuition reflex.
**Answer:** With π = 0.1% prevalence, predicting NEVER FRAUD yields 99.9% accuracy. Real questions: precision at your alert capacity (investigators can clear ~X/day), recall on true fraud weighted by dollar value, and expected cost = fraud losses + review costs + good-customer friction. Report precision@k, PR-AUC, and cost curves.
**Follow-up trap:** *"What threshold do you pick?"* — From the operating point: marginal caught-fraud value equals marginal false-alert cost at available capacity; it moves with staffing and chargeback rates, so thresholds are business inputs, not model constants.

### Q2 — What must go into an adverse-action letter and how do you generate reasons from a GBM?
**Testing:** Reg B mechanics + explainability pipeline.
**Answer:** Specific principal reasons for denial (Reg B) within 30 days, plus FCRA disclosures if a consumer report was used (score disclosure under risk-based pricing rules). Pipeline: per-applicant SHAP attributions → map to approved reason-code vocabulary ("insufficient length of credit history") → rank by attribution magnitude → legal-approved templates. The mapping layer needs validation like any model — wrong reason codes are violations even when scores are right.
**Follow-up trap:** *"Can we decline to disclose because the model is proprietary?"* — No: CFPB Circular 2022-03 says trade secrecy doesn't excuse specific-reason duties; complexity isn't a defense.

### Q3 — Explain proxy discrimination with a concrete mechanism.
**Testing:** fair-lending depth beyond "we don't use race."
**Answer:** Features correlate with protected classes through history and geography: zip code encodes segregation patterns, transaction categories encode religious observance, social ties encode network effects. A model using only these reproduces discriminatory patterns — measurable via AIR gaps despite zero protected attributes among inputs. Defenses require necessity justification + continuous monitoring + sometimes removing/reweighting features at accuracy cost.
**Follow-up trap:** *"Is dropping zip code enough?"* — Rarely: other features absorb the signal (feature leakage through proxies). Test empirically — rerun fairness audits after removals; residual proxies usually persist.

### Q4 — State the fairness impossibility result and how you'd handle it in production.
**Testing:** Kleinberg-Chouldechova fluency.
**Answer:** When base rates differ across groups, calibration-within-groups is incompatible with equalizing error rates (FPR/FNR) — you cannot satisfy both. Production handling: choose per context with documented rationale (lending typically prioritizes calibration + equal opportunity for qualified applicants; fraud may tolerate FPR gaps differently), measure all candidate metrics continuously, and get legal/compliance sign-off recorded — regulators increasingly ask WHICH definition you chose and why, not whether you achieved all.
**Follow-up trap:** *"Can't better models escape the tradeoff?"* — No: it's mathematical, driven by base-rate differences, not estimator quality. Improving overall accuracy shrinks magnitudes but never removes the incompatibility.

### Q5 — Walk through HSBC 2012 and what modern AML stacks change.
**Testing:** case literacy + current-state knowledge.
**Answer:** December 2012 $1.9B resolution ($1.256B forfeiture): cartel money laundered through Mexican branches, sanctioned-country exposures unmonitored, program understaffed against known risk. Modern changes: entity-resolution graphs surfacing networks, ML alert prioritization against 90-95%+ false-positive baselines, automated sanctions screening improvements, and governance treating monitoring coverage as measurable (population coverage %, model-based alert quality tracked to SAR outcomes).
**Follow-up trap:** *"So just buy graph analytics?"* — Technology was rarely the binding constraint: data quality across silos, investigation capacity, and governance ownership were. Graph tools amplify a functioning program; they don't replace one.

### Q6 — Design the latency budget for a real-time card authorization fraud decision.
**Testing:** production systems thinking.
**Answer:** ~100-150ms end-to-end: network/auth overhead leaves ~30-60ms for scoring. Precompute customer-history features in online store (p99 reads <5ms); rules evaluate first (<1ms, short-circuit extremes); single-model scoring on engineered features (~5-15ms); heavy graph/GNN signals run ASYNC post-authorization for case linkage, not inline. Fallback path: if scorer times out, fall back to rules-only rather than declining everyone.
**Follow-up trap:** *"Why not your best GNN inline?"* — Latency kills authorizations at scale; every ms degrades approval rates worth more than incremental fraud catches. Inline simplicity + async depth is the standard compromise.

### Q7 — What did the Apple Card controversy teach about explainability?
**Testing:** public-case reasoning.
**Answer:** November 2019: viral claims of large credit-limit disparities between spouses with shared finances; NYDFS investigated Goldman's Apple Card underwriting; closed March 2021 finding no unlawful discrimination BUT criticizing opacity — customers couldn't understand decisions or appeal effectively. Lessons: individual explanations must exist and be communicable BEFORE virality; couples/joint-finances edge cases need explicit design; the reputational clock runs faster than the regulatory one.
**Follow-up trap:** *"Was the model biased?"* — Investigation said no unlawful discrimination; likely drivers were individual-credit-based limits ignoring household context — a product-design gap, not necessarily statistical bias. Distinguish those two in answers.

### Q8 — How would you structure a champion-challenger test for a new credit model under fair-lending constraints?
**Testing:** merging T24-mrm machinery with this module.
**Answer:** Standard gates (same population/windows, significance via paired bootstrap, PSI stability) PLUS fairness guardrails as blocking metrics: selection-rate/AIR deltas vs incumbent within tolerance bands approved by compliance; reason-code stability (letter churn is operational risk); segment calibration checks. Promotion requires joint sign-off: model governance + fair lending. Document everything — challenger files become examination evidence.
**Follow-up trap:** *"Challenger improves accuracy but worsens AIR below four-fifths."* — That's a business/legal decision, not an engineering one: quantify profit delta vs litigation/regulatory exposure, consider mitigation (thresholds per segment are themselves legally fraught — adverse treatment risk), escalate with options memo. Never silently ship.

### Q9 — Which EU AI Act obligations will hit a bank's credit-scoring system and when?
**Testing:** regulatory timeline precision.
**Answer:** Creditworthiness evaluation of natural persons is Annex III high-risk: obligations apply August 2, 2026 — risk management system, data governance/quality, technical documentation, logging, transparency to deployers/users, human oversight, accuracy/robustness measures, conformity assessment. Penalties up to €35M/7% turnover. GPAI-model obligations began August 2, 2025; pre-existing GPAI models and embedded-product high-risk have until August 2, 2027. Practical read: inventory mapping + gap analysis NOW, since documentation/logging take quarters to retrofit.
**Follow-up trap:** *"US banks ignore it then?"* — Extraterritorial reach applies to outputs used in the EU; multinationals build once to strictest denominator. Also watch simplification/omnibus proposals adjusting timelines — cite dates with "as currently scheduled."

### Q10 — Why does AML prefer recall-oriented metrics while credit optimizes calibrated probability?
**Testing:** objective-function reasoning per domain.
**Answer:** AML: missing a real ring carries existential penalties ($1B+ fines, consent orders) while extra alerts cost analyst hours — asymmetric loss favors recall within capacity, and probability calibration matters less than ranking quality. Credit: probabilities feed pricing/provisioning (IFRS 9/CECL), so calibration is load-bearing; miscalibration misprices risk portfolio-wide even with great ranking. Same math, opposite metric emphasis, driven entirely by loss functions.
**Follow-up trap:** *"Could one platform serve both?"* — Shared feature/entity infrastructure yes; shared objectives no. Conflating them produces AML models afraid to alert and credit models that aren't calibrateable.

### Q11 — How do you monitor a deployed fraud model for adversarial adaptation?
**Testing:** drift + adversary literacy.
**Answer:** Watch three layers: input distributions (feature drift via PSI/KS), score distributions (adversaries probe until scores compress), and outcome lag structures (chargebacks arrive weeks late — use delayed-feedback methods, not naive accuracy). Ring-level analytics: velocity of new-device enrollments, shared-attribute clustering growth. Champion refresh cadence monthly-ish; kill-switch to rules-only mode ready; every confirmed new pattern becomes training data AND a rule.
**Follow-up trap:** *"How do you know decay is adversarial vs organic drift?"* — Attribution: organic drift shifts marginals broadly; adversarial adaptation concentrates on decision boundary features with temporal correlation to deployment. Neither proof is clean — treat unexplained degradation as hostile until proven otherwise.

### Q12 — Where do LLMs legitimately help in these workflows today?
**Testing:** sober GenAI judgment.
**Answer:** High-value lanes: SAR/narrative summarization and drafting (analyst copilot, human signs), KYC document extraction, adverse-media triage, dispute-letter classification, code/query assistance for investigators. Each lands in MRM inventory with eval gates; hallucination incidents tracked as model-risk events; nothing generative makes binding decisions (declines, account freezes, SAR filings) without deterministic systems + human sign-off. EU AI Act transparency tier also forces disclosing AI interaction to customers.
**Follow-up trap:** *"Why not let it decide borderline cases?"* — Borderline cases are exactly where explanation duties, appeal rights, and consistency requirements bind hardest; probabilistic text generators fail auditability there by construction.

## Red flags

- Reporting fraud-detection accuracy without prevalence context.
- Believing excluding protected attributes solves fair lending (proxies).
- No answer for which fairness metric you'd sacrifice (impossibility).
- Adverse-action reasons generated by reading out raw SHAP values to customers.
- Claiming LLMs can autonomously file SARs or deny credit.
- Treating EU AI Act as EU-only irrelevance for US institutions.
- Confusing disparate treatment (intent) with disparate impact (effect).
- AML "AI replaces investigators" framing.

## Cheat card

```
FRAUD     prevalence ~0.1% -> accuracy vanity; optimize precision
          @capacity + $-weighted recall; latency budget ~100-150ms
          (rules<1ms inline, graphs async); adversary adapts ->
          monthly champions, delayed-feedback labels (chargebacks)
CREDIT    ECOA'74/Reg B: specific principal reasons <=30 days;
          FCRA risk-based-pricing notices; CFPB Circ 2022-03:
          complex model != excuse; scorecard points > SHAP for letters
FAIRNESS  doctrines: treatment(intent) vs impact(effect,
          Inclusive Communities '15); four-fifths AIR guideline
          IMPOSSIBILITY (Kleinberg'16/Chouldechova'17): calibration
          XOR equal errors across groups @ differing base rates ->
          choose + document + monitor; proxies: zip/merchant/ties
AML       BSA'70; SARs ~30d from detection; rule FP rates 90-95%+
          -> entity resolution + graph anomaly + alert scoring;
          HSBC'12 $1.9B · BNP'14 $8.9B · Danske ~EUR200B flows
EXPLAIN   ladder: global importance / local SHAP / reason codes /
          counterfactuals (actionable, safe); GDPR Art22 human-loop
EU AI ACT 2024/1689 in force Aug 1 '24; tiers: banned/high-risk/
          transparency/minimal; credit scoring = HIGH-RISK (Annex III)
          timeline: prohibitions Feb 2 '25 · GPAI Aug 2 '25 ·
          high-risk obligations Aug 2 '26 · legacy GPAI Aug 2 '27
          fines EUR35M/7%; ISO 42001: certifiable AIMS (PDCA);
          NIST RMF: GOVERN/MAP/MEASURE/MANAGE ~= SR11-7 mapped
GOV       all models in SR 11-7 inventory; GenAI: eval gates =
          evidence, hallucination = model-risk EVENT (see T24-mrm)
```

## Sources

- [CFPB Circular 2022-03: Adverse action notification requirements in connection with credit decisions supported by complex algorithms](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-supported-by-complex-algorithms/); accessed 2026-08-23
- [NY DFS (March 2021). Conclusion of Apple Card investigation](https://www.dfs.ny.gov/reports_and_publications/press_releases/pr2103231); accessed 2026-08-23
- [Kleinberg, Mullainathan, Raghavan (2016). Inherent Trade-Offs in Fair Classification. PNAS](https://www.pnas.org/doi/10.1073/pnas.1616010114); accessed 2026-08-23
- [Chouldechova (2017). Fair Prediction with Disparate Impact. Big Data](https://www.liebertpub.com/doi/10.1089/big.2016.0047); accessed 2026-08-23
- [US DOJ (2012). HSBC Holdings plc Deferred Prosecution Agreement announcement](https://www.justice.gov/archive/opa/pr/2012/December/12-crm1548.html); accessed 2026-08-23
- [Nilson Report. Global card fraud loss figures](https://nilsonreport.com/); accessed 2026-08-23
- [EU AI Act, Regulation (EU) 2024/1689 — official text](https://eur-lex.europa.eu/eli/reg/2024/1689/oj); accessed 2026-08-23
- [ISO/IEC 42001:2023 — AI management system standard](https://www.iso.org/standard/81230.html); accessed 2026-08-23
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework); accessed 2026-08-23
- [FinCEN. BSA data and SAR statistics](https://www.fincen.gov/resources/statistics-and-data); accessed 2026-08-23

## Changelog

- 2026-08-23 — created




