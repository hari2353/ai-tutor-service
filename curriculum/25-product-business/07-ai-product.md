# Pricing & Positioning AI Products; Why Most AI Features Don't Ship

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-unit-economics Â· **Updated:** 2026-08-23
> **Module id:** `T25-ai-product` Â· **Tags:** product, critical

## The 30-second version

Pricing AI products is hard because costs scale with usage while buyers anchor on seats â€” so every vendor eventually collides with the same wall: someone's power users cost more than they pay. The 2024-2026 resolution converged on **hybrid models**: a seat price covering median usage plus metered credits/caps above it (Microsoft's Copilot at $30/user/month set the enterprise anchor; consumer chat tiers and API credits set self-serve anchors), because unlimited-usage plans bled out industry-wide within quarters. Pricing discipline starts from COGS (module 06) but prices against **value and alternatives** â€” "what does the buyer do instead, and what does that cost?" â€” with a standing warning: anchoring AI to salary replacement invites brutal comparisons and churn when quality disappoints. Positioning (April Dunford's chain: competitive alternatives â†’ unique attributes â†’ enabling value â†’ target segment â†’ market category) decides whether you're judged against software (cheap, fast, must-be-perfect) or against labor (expensive, slow, fault-tolerant) â€” arguably the highest-leverage sentence in your go-to-market. And why most AI features don't ship: pilot-failure rates are brutal (Gartner projected ~30% of GenAI projects abandoned after proof-of-concept by end-2025; MIT's widely-cited 2025 NANDA study reported ~95% of enterprise GenAI pilots showing zero measurable P&L impact), and the causes are mostly NOT model quality â€” they're undefined outcomes, missing evals, broken unit economics, trust/compliance gates, workflow non-integration, and org ownership ambiguity. Every one of those six is engineering-addressable, which makes shipping-rate literacy a principal-engineer competency.

## Why this gets asked

Interviewers at AI-forward companies ask two flavors. Product sense: "How would you price our AI feature?" â€” testing whether you reason from cost, value, and alternatives rather than copying a competitor's number. Diagnostic: "Why do so many AI features get built and never ship?" â€” testing whether you know production failure is organizational as much as technical, and whether you've personally fought through one of the six killers. Your resume sits exactly on this ground: an 8-service recsys platform invites "what made that shippable where others stall?" A strong answer names the gates you cleared â€” baseline evals, cost ceilings per request, guardrail metrics, staged rollout â€” versus where features die: demo-quality outputs with no measurement story, or business cases requiring unlimited inference at fixed price. There's a self-preservation angle too: engineers who articulate how their work creates priced value are the ones whose projects survive portfolio cuts.

---

## Lineage: past â†’ present â†’ future

**What came before.** Software pricing evolved toward capturing value rather than cost: perpetual licenses (1980s), then subscriptions (Salesforce 1999 popularizing SaaS seats), then usage-based cloud pricing (AWS 2006+) and product-led freemium (2010s). Pricing research gave practitioners two durable tools: Van Westendorp's Price Sensitivity Meter (1976 â€” four questions deriving acceptable-price bands) and Gabor-Granger-style willingness-to-pay curves; Patrick Campbell's ProfitWell/Price Intelligently work (2010s) industrialized segmentation-based WTP studies showing that pricing changes routinely move revenue more than acquisition (commonly cited: pricing optimization worth up to several times more revenue impact per unit effort than equivalent acquisition spend). Positioning theory ran parallel from Ries & Trout (*Positioning*, 1981) to April Dunford's modern practitioner synthesis (*Obviously Awesome*, 2019) which made positioning a repeatable 5+1 component process rather than ad-agency mystique.

**Where it stands now.** The AI wave stress-tested everything at once. Costs became variable per request (inverting software economics), model quality became table-stakes-fast (differentiation decays as capabilities commoditize within months), and buyers got whiplash: 2023's "add AI, charge more" era produced add-on pricing (Copilot's $30/user/mo on top of M365 seats being the canonical enterprise anchor) while 2024-2026 forced hybrid seat-plus-consumption models as unlimited plans met power users. Positioning bifurcated: "AI-powered" stopped differentiating (everyone says it), pushing serious vendors toward outcome-based categories ("resolution platform," "coding agent") while thin wrappers got punished in the market for inheriting supplier COGS without moats. The shipping-crisis data matured: Gartner's mid-2024-2025 guidance (~30% of GenAI projects predicted abandoned post-PoC by end-2025), MIT NANDA's 95% figure, and S&P/Ramp surveys converging on the same shape â€” pilots everywhere, production value rare, causes organizational.

**Where it's heading.** Confidence-ordered: (1) consumption pricing spreads beyond infrastructure into application software generally â€” AI made variable costs normal, and billing is following; expect seat-only competitors to look increasingly anachronistic; (2) outcome-based pricing matures in bounded domains (per-resolution support AI, per-recruited-candidate tools) where attribution is clean â€” it remains impractical where outcomes are diffuse or lagged; (3) contested: agents force the biggest pricing rupture â€” if software completes workflows rather than assisting, pricing anchors shift from per-seat toward per-workflow/per-result, colliding with the labor-budget line item instead of the software budget, which changes both the buyer and the comparison set.

## Mental model

```
        WHAT IS THE BUYER'S ALTERNATIVE?  <- pricing & positioning both hang here

  judged vs SOFTWARE            judged vs HUMAN LABOR
  (other tools)                 (the employee/agency doing the job)
  price anchor: $10-100/mo      price anchor: $3,000-8,000/mo
  tolerance for error: ~0       tolerance: humans err constantly
  switching: minutes            switching: weeks-months
  => must be flawless, cheap    => "80% as good at 20% of cost" WINS

  PICKING THE CATEGORY PICKS YOUR JUDGE. Positioning is that choice.
```

And the shipping funnel â€” why most AI features die, with each death assignable to a gate an engineer can own:

```
ideas -> PoC/demo -> pilot -> GA launch -> measured value
         |            |          |             |
      gate: evals   gate: unit-  gate: trust/  gate: outcome
      + problem     economics +  compliance +  instrumentation
      fit           latency      workflow fit   + iteration loop
      ~ most die here ~ many die ~ some die   ~ quiet deaths:
                    here          here          shipped but unmeasured
```

## How it actually works

### Pricing mechanics: from COGS floor to value ceiling

Three reference points set any AI price. **Cost floor:** fully-loaded COGS per user per month (module 06 arithmetic) times your target gross margin â€” price below this and growth destroys cash. **Value ceiling:** what the alternative costs the buyer â€” the analyst-hour it replaces (an analyst hour at $60-150 loaded), the support ticket ($5-15 industry-typical cost per ticket; deflection value is measurable), the error prevented (cost Ã— probability). **Market anchors:** what comparable products charge â€” Copilot's $30/user/mo made enterprise AI assistants a budgeted line item, which helps every competitor; consumer chat tiers ($20/mo era) anchor prosumer expectations. Practical method: Van Westendorp's four questions (at what price too cheap to trust / cheap deal / expensive but considerable / too expensive) over 100+ target-buyer responses yields the acceptable band; segment before averaging because WTP distributions in AI tools are extreme (power users would pay 10x light users â€” which is precisely why hybrid seat+credits works: it's price discrimination by usage without asking anyone's salary).

Packaging choices matter as much as numbers: **add-on** (visible ROI, but adoption friction and churn risk when budgets tighten), **bundled tier-upgrade** (drives ARPA, hides COGS until usage explodes), **pure consumption** (aligns revenue to cost, but bill shock kills trust and forecasting dies). The 2024-2026 equilibrium: bundle into premium tiers with credit meters above median usage.

### The salary-replacement trap

Positioning against labor ("replaces a $70K analyst") sets expectations you cannot meet: humans are fault-tolerant, context-switching, accountable generalists; models are narrow, confident-when-wrong specialists. The durable pattern positions against the TASK not the PERSON: "drafts first-pass reports in minutes" beats "your junior analyst" â€” smaller promise, deliverable, and expandable on evidence. When labor comparison is unavoidable (support automation), quantify narrowly and honestly: tickets resolved end-to-end without human touch, with QA sampling â€” never "headcount reduction" promises to enterprises who know change-management reality.

### The six killers of AI features (and their engineering countermeasures)

1. **Undefined outcome:** no baseline metric agreed pre-build â†’ nobody can declare success â†’ zombie pilots. Fix: outcome spec + kill condition before code (module 01).
2. **No evals:** quality claims untestable, regressions invisible, every stakeholder anecdote counts equally. Fix: golden-set evals + LLM-judge panels wired into CI (T08 stack); this single artifact converts debates into dashboards.
3. **Unit economics:** unlimited inference at fixed price meets power users â†’ margin death or emergency caps â†’ user revolt. Fix: COGS-per-request ceilings as launch gates; cascade architecture day one.
4. **Trust/compliance gates:** hallucination exposure, PII flows, audit requirements stall legal review for quarters. Fix: guardrail metrics, human-in-loop escalation paths, eval logs as compliance artifacts, data-flow diagrams in the design doc.
5. **Workflow non-integration:** feature lives in its own tab; users try twice, forget. Fix: embed where work happens, measure depth-of-use not activation (module 03).
6. **Ownership ambiguity:** PM thinks engineering owns quality, engineering thinks PM owns outcomes, nobody owns the P&L â†’ decisions stall. Fix: one named owner, per-feature P&L, decision-log cadence.

The meta-pattern: features ship when someone treats them as products (owner, outcome, economics, evals) and die when they remain demos wearing roadmaps.

---

## Build it from scratch

**Exercise: pricing analysis for your AI feature, coded (60 min) â€” then fill the positioning statement.**

```python
# pricing_lab.py -- COGS floor, WTP bands, scheme comparison on a real usage distribution
import random

def usage_distribution(n=10_000, p50=8, skew=2.0):
    """Weekly requests: exponential-ish skew typical of AI features."""
    return [max(1, int(random.expovariate(1/p50) * skew)) for _ in range(n)]

def analyze(users_weekly_reqs, cost_per_req, schemes):
    monthly = [(r * 4.33 * cost_per_req) for r in users_weekly_reqs]
    monthly.sort()
    p50 = monthly[len(monthly)//2]; p90 = monthly[int(len(monthly)*0.9)]
    out = {"COGS_p50": round(p50,2), "COGS_p90": round(p90,2)}
    for name, price, credits_free in schemes:
        # price covers up to credits_free $ of COGS; overage billed at 4x marginal
        rev = 0; cogs = 0
        for m in monthly:
            rev += price + max(0, m - credits_free) * 4 if m > credits_free else price
            cogs += m
        gm = (rev - cogs) / rev
        out[name] = {"GM%": round(gm*100,1),
                     "rev_per_user": round(rev/len(monthly),2)}
    return out

usage = usage_distribution()
# frontier-ish path: $0.0126/request; tuned path: $0.0025 blended after cascade+caching
print(analyze(usage, 0.0126,
              [("flat_$29", 29, 29), ("seat25_plus_credits", 19, 15)]))
print(analyze(usage, 0.0025,
              [("flat_$29", 29, 29), ("seat25_plus_credits", 19, 15)]))
```

Read results like a pricing committee: flat pricing at frontier costs shows GM collapsing under skew; the tuned path restores margin â€” meaning **architecture choices ARE pricing choices**. Then write Dunford's chain in six sentences: alternatives (analyst hours / existing tools), unique attributes (what only we do), value enabled (in their words), segments who care most, market category (picks the judge), plus the one sentence a skeptic would find believable. If the category sentence says "AI-powered X," redo it â€” that's a feature description, not a category.

## How it's done in production

| Practice | Example |
|---|---|
| Anchor-setting add-on pricing | Microsoft 365 Copilot at $30/user/mo (2023) created the enterprise AI-assistant budget line every vendor now prices against |
| Hybrid seat+consumption | Consumer/prosumer AI tiers: subscription covers median usage; credits meter heavy paths â€” post-2024 standard after unlimited plans bled |
| Outcome pricing in bounded domains | Support-AI vendors charging per-resolution (where attribution is clean); recruiting tools per qualified candidate |
| Positioning-led categories | "Coding agent," "resolution platform" vs generic "AI chatbot" â€” category choice determines the buyer, the budget line, and the comparison set |
| Ship-gate checklists | Launch reviews requiring eval reports, COGS ceilings, guardrail thresholds, and named ownership before GA â€” the organizational immune system against demo-ware |

Production reality worth internalizing: most orgs now run MORE pilots than they can productionize, so the scarce skill is conversion, not ideation. Teams that ship consistently run a standing "path-to-GA" doc per pilot listing exactly which of the six killers applies and who owns each countermeasure â€” the doc is boring and that's the point.

---

## Tradeoffs & when NOT to use it

- **Don't usage-price everything.** Consumption billing kills adoption predictability for buyers with fixed budgets and adds billing-infrastructure cost; seats remain right where usage variance is low or value is role-based rather than volume-based.
- **Outcome pricing needs clean attribution.** Where outcomes lag months or depend on many inputs, per-outcome pricing creates endless disputes; price the proxy action instead (per document processed) or stay on seats.
- **Positioning against labor wins deals and invites churn.** The bigger the promise, the harder the renewal; some teams deliberately under-promise to over-deliver renewals â€” a real strategy with a real growth cost.
- **The six-killer checklist can become launch theater** if gates are checked without evidence ("evals: yes" against a 20-case golden set). Gates need teeth: minimum eval-set sizes, measured not asserted.
- **Premium "AI tier" positioning ages badly** when competitors bundle equivalent capability into base price â€” differentiation from the MODEL decays in months, so anchor premium claims in proprietary assets (data loops, workflow embedment, compliance posture) that don't commoditize overnight.

---

## Interview questions

### Q1 â€” How would you price an AI feature we're adding to our existing product?
**Testing:** structured pricing reasoning vs number-copying.
**Answer:** Three anchors: COGS floor per user (module 06 arithmetic including skew), value ceiling versus the buyer's real alternative (task-hours Ã— loaded rate, tickets deflected), market anchors ($30/user/mo enterprise-assistant precedent). Then pick packaging by usage variance: hybrid seat covering ~P80 plus credits above it if variance is high (AI features always are). Validate with Van Westendorp bands across 100+ target buyers, segmented.
**Follow-up trap:** *"'Why not just match Competitor X's price?'"* â€” because their COGS structure, bundling strategy, and target segment may differ fundamentally; matching their number without their economics either leaves margin on the table or inherits a loss position. Price your economics, sanity-check theirs.

### Q2 â€” Why did unlimited-usage AI pricing die, and what replaced it?
**Testing:** industry-pattern literacy.
**Answer:** Variable per-request costs met power-user skew: P99 users consumed 10-50x median, making flat prices negative-margin at scale; the 2023-2024 wave of unlimited tiers retracted within quarters. Replacement: seat/subscription covering ~P80 usage plus metered credits at 3-5x marginal COGS beyond, with caps on pathological paths. It's second-degree price discrimination that protects both sides: most users never feel limits, heavy users fund themselves.
**Follow-up trap:** *"'Doesn't metering kill the magic?'"* â€” invisible at P80 allowances, which is why percentile design matters more than the mechanism; what actually killed trust was surprise overage bills â€” hence soft notifications near thresholds and hard caps instead of silent runaway charges.

### Q3 â€” Explain positioning as 'choosing your judge.' Why does it matter more for AI products?
**Testing:** Dunford-level positioning depth.
**Answer:** Your market category determines which alternative you're compared against and thus which attributes matter: positioned as software, you're judged cheap/fast/flawless; positioned as labor replacement, judged against human flexibility and fault-tolerance at salary-scale prices. AI sits awkwardly between â€” good enough to invoke labor comparisons, unreliable enough to lose them. Deliberate positioning picks the favorable comparison: task-level automation ("first drafts in minutes") beats person-replacement framing almost always.
**Follow-up trap:** *"'Isn't positioning just marketing spin?'"* â€” no: it dictates product requirements, sales conversations, and pricing headroom. Repositioning from feature-to-category changes what engineering must build (integration depth, compliance surface); it's strategy expressed in one sentence.

### Q4 â€” Why do most AI features fail to reach production? Give the top causes with evidence.
**Testing:** shipping-crisis literacy plus diagnosis.
**Answer:** Failure rates are documented and brutal: Gartner projected ~30% of GenAI projects abandoned after PoC by end-2025; MIT's 2025 NANDA study reported ~95% of enterprise GenAI pilots showing zero measurable P&L impact. Causes rank organizational-first: undefined success outcomes, missing evals, broken unit economics, trust/compliance stalls, workflow non-integration, ownership ambiguity â€” model quality rarely the binding constraint anymore.
**Follow-up trap:** *"'So the tech is ready and companies just fail at process?'"* â€” partly, but the technical bar moved too: production demands latency budgets, guardrails, eval infrastructure, and cost ceilings that demos never exercise. It's BOTH: orgs underrate the organizational work AND underestimate the engineering distance from demo to dependable.

### Q5 â€” Which of the six killers have you personally fought, and how?
**Testing:** lived experience signal â€” resume-grounded.
**Answer shape:** Pick honestly from recsys/AI work. Example: evals â€” shipped a ranking change that looked better on offline metrics and regressed relevance live; built the golden-set + interleaving harness afterward; next three launches carried pre-registered metrics. Or unit economics: discovered serving-cost regression via per-request tagging, added cost dashboards to CI. Name the artifact that survived, not the war story.
**Follow-up trap:** *"'What would you do differently now?'"* â€” earlier and cheaper instrumentation: baseline evals BEFORE first build, COGS-per-request ceilings as design constraints rather than post-hoc discoveries. The killers are cheap to prevent at design time and expensive to fix post-launch.

### Q6 â€” When is outcome-based pricing viable, and when does it explode?
**Testing:** pricing-mechanism judgment.
**Answer:** Viable when attribution is clean and verifiable by both parties: per-resolution support AI (resolved = closed without reopen), per-screened-candidate tools, per-document-processed pipelines. Explodes when outcomes are lagged, multi-causal, or disputable: revenue-lift pricing invites attribution wars; quality disputes become billing disputes. Fallback: price measurable proxies (documents processed) or revert to consumption.
**Follow-up trap:** *"'Buyers love aligned incentives â€” why isn't everything outcome-priced?'"* â€” because sellers then carry risk they can't control (buyer's data quality, adoption, definition drift), and dispute resolution becomes the core business process. Alignment has administrative costs that only clean attribution amortizes.

### Q7 â€” A VP wants 'add AI, charge $30/user like Microsoft.' What's wrong with that reasoning?
**Testing:** anchor literacy.
**Answer:** Copilot's $30 works because it rides M365's installed base, IT-admin distribution, and deep workflow integration (Office files, email context) â€” the price reflects THAT moat, not AI capability alone. Copying the number without the embeddedness produces sticker-shock churn: users compare against free consumer chatbots, not Office productivity. Price your value evidence and COGS; cite Copilot as category validation, not as your number.
**Follow-up trap:** *"'But finance already put $30 in the board deck'"* â€” reframe as sequencing: launch at validated price with grandfathering language, instrument realized value, and revisit at renewal with usage data. Boards respond to de-risked plans, not refusals.

### Q8 â€” How do you run a Van Westendorp study for an AI product without garbage results?
**Testing:** research-method craft.
**Answer:** Sample actual buyers in-segment (100+ minimum for stable bands, 300+ if segmenting), describe the offer concretely BEFORE asking (vague concepts yield noise), ask the four questions (too-cheap-to-trust / bargain / expensive-but-viable / too-expensive), then read intersections: the acceptable band and the indifference point. Watch for AI-specific distortions: respondents anchor on consumer-chat prices ($20/mo era) unless the enterprise context is vivid, and power users' WTP skews the mean â€” report segments separately.
**Follow-up trap:** *"'Stated WTP lied to us before â€” why trust this?'"* â€” Van Westendorp measures price PERCEPTION ranges, not purchase promises; treat output as hypothesis bounds, validate with real pricing tests (cohort A/B on price points, waitlist conversions) before committing.

### Q9 â€” Your AI feature ships but users try it twice and vanish. Diagnose.
**Testing:** workflow-integration failure mode recognition.
**Answer:** Classic killer #5: activation without habit â€” the feature lives outside the work path. Check telemetry: time-to-first-value within session (if >2 minutes, dead), return-within-7-days by cohort, entry-point analysis (buried tab vs inline surfaces). Fix by embedding at the moment of need (in-editor, in-ticket, in-doc), reducing invocation friction to zero, and measuring depth-of-use not trial counts. If embedding reveals the VALUE is weak, that's discovery again â€” no placement fixes a thin promise.
**Follow-up trap:** *"'Should we email/incentivize re-engagement?'*" â€” notifications paper over placement failures briefly and train users to ignore them; fix the surface first, then measure organic return. Growth mechanics on top of weak workflow fit is churn on a delay.

### Q10 â€” When should AI be an add-on SKU versus bundled into existing tiers?
**Testing:** packaging strategy reasoning.
**Answer:** Add-on when: costs are material and variable, WTP segments differ sharply, and you need ROI visibility to justify continued investment â€” add-on SKUs make revenue and churn legible. Bundle when: AI is table-stakes competitive parity (charging for it invites switching), or when bundling drives premium-tier mix-shift worth more than standalone revenue. Watch the ratchet: bundled AI raises COGS forever while pricing power stays flat; add-ons can later be bundled as retention sweeteners, rarely reverse.
**Follow-up trap:** *"'We bundled it and margins dropped 12 points â€” undo?'"* â€” unbundling reads as a pay-cut and burns trust; usually better: keep the bundle, add fair-use limits, migrate heavy users to higher tiers with credits, and fix COGS architecture. Announce nothing; engineer quietly.

### Q11 â€” What makes 'wrapper' accusations stick, and how do you escape the label?
**Testing:** moats-meets-positioning synthesis (module 05 tie-in).
**Answer:** The accusation sticks when your product adds a thin UI over rented intelligence: supplier can replicate you in a release cycle, switching costs are nil, and COGS tracks your supplier's whims. Escapes: proprietary data loops (usage improves outcomes measurably), workflow embedment (integrations and state that take months to rebuild), evaluation/compliance depth in regulated niches, distribution advantages. Note the pattern: all four are module-05 moats â€” the wrapper question IS the moat question wearing product clothes.
**Follow-up trap:** *"'Isn't everything a wrapper on something?'"* â€” sure, and the question is whether YOUR layer captures durable margin or just passes rent through. Databases wrapped filesystems successfully because they owned semantics; wrappers die when they own only plumbing.

### Q12 â€” Design the path-to-GA plan for a promising support-ticket AI pilot.
**Testing:** synthesis â€” converting pilot to production deliberately.
**Answer:** One page naming each killer and its countermeasure owner: outcome spec (deflection rate baseline + target, CSAT floor); evals (500-ticket golden set + judge panel wired into CI, threshold â‰¥ human-agent parity on sampled QA); economics (COGS/resolution ceiling vs $5-15 ticket benchmark, cascade architecture, monthly P&L); trust (PII redaction flow, human-review queue for low-confidence, audit logs); workflow (embedded in agent console, escalation UX); ownership (named PM+eng pair, weekly decision log). Gate reviews at each stage with kill conditions written upfront.
**Follow-up trap:** *"'This sounds like bureaucracy that slows pilots down'"* â€” the checklist runs in days when drafted at pilot start and prevents the quarter-long stalls it looks like overhead against; the teams skipping it are the ones Gartner counted as abandoned post-PoC.

---

## Red flags

- Pricing set by copying a competitor's number with no COGS or WTP analysis.
- Unlimited-usage commitments on variable-cost AI workloads.
- Value narrative anchored to replacing salaries wholesale.
- "AI-powered" used as the market category (it's a feature adjective, not a position).
- Pilots with no golden-set evals and no COGS ceiling â€” demo-ware pipeline.
- No named owner or per-feature P&L for AI initiatives.
- Success measured by trial activations with zero depth-of-use or return telemetry.

## Cheat card

```
PRICING ANCHORS  COGS floor (incl skew, P90 user) | value ceiling
                 (alt x loaded rate) | market anchors ($30/user
                 Copilot precedent; $20 consumer-chat era)
SCHEMES          seat (predictable, ignores variance) | pure usage
                 (aligns cost, bill shock) | HYBRID: seat~P80 +
                 credits 3-5x marginal COGS - post-2024 standard
WTP RESEARCH     Van Westendorp 4 questions, 100+/segment;
                 perception bands not purchase promises -> price-test
POSITIONING      alternatives -> unique attrs -> value -> segment ->
                 CATEGORY (picks your judge: software=flawless&cheap,
                 labor=fault-tolerant&pricey). Task-framing > person-
                 replacement. 'AI-powered' is not a category.
SIX KILLERS      1 undefined outcome 2 no evals 3 unit economics
                 4 trust/compliance 5 workflow non-integration
                 6 ownership ambiguity -- all engineering-addressable
EVIDENCE         Gartner ~30% GenAI projects abandoned post-PoC by
                 end-2025; MIT NANDA 2025: ~95% pilots no P&L impact
WRAPPER TEST     supplier replicates in a release? no data loop, no
                 embedment, no compliance depth => rent passing through
PATH-TO-GA       outcome spec + golden-set evals in CI + COGS ceilings
                 + guardrails/HITL + embedded surface + named owner,
                 kill conditions written UPFRONT
```

## Sources

- April Dunford, *Obviously Awesome* (Ambient Press, 2019), https://www.aprildunford.com/ â€” accessed 2026-08-23
- Gartner press release, "Gartner Predicts 30% of Generative AI Projects Will Be Abandoned After Proof of Concept By End of 2025" (July 2024), https://www.gartner.com/en/newsroom/ â€” accessed 2026-08-23
- MIT NANDA initiative, "The GenAI Divide: State of AI in Business 2025" (95% pilot-impact figure), https://nanda.media.mit.edu/ â€” accessed 2026-08-23
- Microsoft 365 Copilot pricing announcement ($30/user/month), https://www.microsoft.com/en-us/microsoft-365/blog/ â€” accessed 2026-08-23
- Patrick Campbell / ProfitWell pricing research archive, https://www.priceintelligently.com/ â€” accessed 2026-08-23
- Martin Casado & Sarah Wang, "Who Owns the Generative AI Platform?" a16z, https://a16z.com/who-owns-the-generative-ai-platform/ â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

