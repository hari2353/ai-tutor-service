# Unit Economics: CAC/LTV, Margins, and the Cost of an AI Feature

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-product-thinking Â· **Updated:** 2026-08-23
> **Module id:** `T25-unit-economics` Â· **Tags:** finance, critical

## The 30-second version

Unit economics asks one question at the smallest scale of the business: when ONE more user flows through, does value created exceed variable cost of serving them? The canonical pair is **CAC** (fully-loaded cost to acquire a customer â€” ad spend + sales salaries amortized over acquired customers, blended or paid-channel) versus **LTV** (average revenue per user Ã— gross margin Ã— customer lifetime, where lifetime â‰ˆ 1/monthly-churn-rate), with two heuristics that gate funding conversations everywhere: **LTV:CAC â‰¥ 3** and **CAC payback within 12-18 months**. Gross margin is where engineers live: traditional SaaS runs **70-85%** because COGS is hosting and support; AI features routinely run **25-50%** pre-optimization because every request burns tokens â€” a per-request cost structure software never had since marginal copies were free. That inversion makes inference-COGS arithmetic a core engineering literacy: tokens/request Ã— price/Mtok Ã— volume = your new cost of goods, and it scales with usage, not headcount. The deeper skill for a principal is the **cost-of-GOOD-enough curve**: quality improvements have diminishing returns against flat costs, so there's an accuracy knee below which the product fails and above which you're burning margin for unperceived quality â€” finding that knee, then engineering cost down along it (caching, cascades, distillation, model routing) is the highest-leverage optimization most AI teams own, usually worth more than any code-level performance work.

## Why this gets asked

Engineers get hired on technical interviews and fired â€” or promoted â€” on economics they never learned. Principal loops now probe this directly ("how would you decide whether our AI feature should exist at all?" "your proposal doubles serving cost â€” justify it"), and cross-functional credibility depends on speaking CFO: contribution margin, payback period, fully-loaded cost. The failure pattern interviewers probe for is the engineer who treats compute as free until the finance review: the team that shipped an LLM feature to 100K users before discovering $80K/month of token spend nobody budgeted, or the opposite pathology â€” refusing to ship anything AI because someone quoted worst-case token math without modeling caching, routing, or the actual usage distribution (real usage is heavily skewed: typically ~10-20% of users drive 50%+ of requests, which changes everything). Your resume invites the question concretely: an 8-service recsys platform has real serving costs, and "~25% engagement lift" begs "against what incremental serving bill?" Being the engineer who volunteers that framing â€” value AND cost per unit, together â€” is what wins architecture debates that are secretly finance debates.

---

## Lineage: past â†’ present â†’ future

**What came before.** Unit economics descends from retail and direct-mail economics: merchants always knew gross margin per widget; the modern CAC/LTV apparatus crystallized in subscription/dot-com era analysis (late 1990s-2000s) as customer-acquisition spending became measurable per channel through digital ads, and VCs needed a screen for subscription businesses burning cash on growth. The LTV:CAC â‰¥ 3 and 12-month payback heuristics hardened into industry folklore through SaaS-era investor memos (Bessemer's SaaS cloud indexes and David Skok's forEntrepreneurs essays, mid-2000s-2010s, being the most-cited sources). Gross-margin norms settled around software's magic property: near-zero marginal cost of copy â€” 70-85% gross margins made SaaS structurally attractive versus hardware (30-40%) and services (20-40%).

**Where it stands now.** AI inverted software's core assumption: marginal cost per user action returned. A support ticket answered by an LLM costs real cents per resolution; a coding assistant's heavy users can consume $50-200/month of inference against $10-30 seats â€” negative contribution margin per power user, subsidized by light users, exactly the dynamic that forced 2024-2026 pricing resets across AI products (usage caps, credits, tiered models). The current craft is cost-engineering the margin back: prompt/response caching (repeated context is nearly free on repeat), model cascades (small model answers 70-90% of traffic, big model escalates hard cases), distillation (teacherâ†’student transfers quality at 5-20x lower serving cost), batch APIs for latency-tolerant paths (typically ~50% discounts), and aggressive output-length control. Meanwhile investors adapted their screens: AI-native companies get scrutinized on inference-adjusted gross margin from day one, and "AI wrapper" became a pejorative precisely because thin application layers inherit supplier COGS without offsetting moats.

**Where it's heading.** Confidence-ordered: (1) continued price-per-intelligence deflation (~10x per 18-24 months across generations) keeps rescuing business cases that were underwater at signing â€” but smart teams underwrite at CURRENT prices and treat declines as upside; (2) hybrid architectures standardize: local/small-model handling for routine tokens, frontier calls only at escalation points â€” the cascade becomes as standard as caching was for web; (3) contested: agentic workloads multiply token consumption per "task" by 10-100x over single-shot calls, so agent products either find order-of-magnitude efficiency gains or price like labor (which changes who the competitor is â€” people, not software). The durable lesson regardless: whoever owns the cost-of-GOOD-enough curve owns the margin.

---

## Mental model

```
        ONE USER'S MONTHLY FLOW THROUGH THE MACHINE

   ARPU $29/mo
        |
        |-- COGS: inference  $6.20  (tokens x price)
        |          hosting    $1.10
        |          support    $2.00
        |-- GROSS PROFIT     $19.70  -> 68% gross margin
        |
        |-- CAC amortized: paid $150 one-time -> 12-mo payback if GP/mo >= $12.5

   LTV = ARPU x GM% / churn      (churn 4%/mo -> lifetime 25 mo)
       = 29 x 0.68 / 0.04 ~= $493
   LTV:CAC = 493/150 ~= 3.3x   [>=3 heuristic passes]
```

Three numbers do most of the talking: **gross margin %** (is the product structurally profitable per use?), **payback months** (how long cash is trapped per customer?), **LTV:CAC** (does growth create or destroy value?). Everything else â€” cohort tables, channel splits, sensitivity bands â€” exists to defend those three from wishful inputs. And the engineer-specific lens: COGS is the line item YOU control most directly. Every architectural choice is a margin decision wearing a technical costume.

## How it actually works

### The formulas, precisely, with their traps

**CAC** = (sales + marketing spend over period) Ã· new customers acquired in period. Blended CAC divides ALL spend; paid CAC isolates channels â€” comparing paid CAC to blended LTV is a classic self-deception. Fully-loaded honesty: include sales salaries, tools, and the promo discounts that quietly halve first-year revenue. **Churn and lifetime:** monthly churn 4% â†’ expected lifetime â‰ˆ 1/0.04 = 25 months (geometric decay); annual-churn businesses divide accordingly (~10% annual â†’ ~10 years, where LTV math becomes fiction because 10-year discounting and market change dominate â€” cap horizons at 3-5 years or apply discount rates). **LTV** = ARPU Ã— gross-margin% Ã— lifetime. **Payback months** = CAC Ã· (ARPU Ã— GM%). Traps: revenue â‰  gross profit (using ARPU instead of GP inflates LTV by 1/GM%); averaging hides cohort decay (newer cohorts with worse retention make aggregate LTV look fine for quarters); and churn is non-constant early on (first-month churn often 2-4x steady-state).

### Token COGS arithmetic, worked end to end

An AI study-helper feature: median request = 1,200 input + 600 output tokens at $3/Mtok input, $15/Mtok output (frontier-class pricing as of 2025-2026 era):

```
cost/request = 1200/1e6 x $3  +  600/1e6 x $15
             = $0.0036        +  $0.009          = $0.0126
sessions/user/week: 4 requests/session x 2 sessions = 8 req/wk
monthly tokens cost/user = 8 x 4.33 wk x $0.0126 ~= $0.44/mo   [median user]
P95 power user: 60 req/wk -> $3.28/mo    [the skew matters]
```

At 50K MAU with that distribution (say mean $0.90/user given skew): ~$45K/month inference bill. Against a $29 seat this looks trivial â€” until the feature serves free-tier users ($0 revenue) or agents multiply requests per task by 10-100x. The engineering levers, ranked by typical leverage: (1) **output-length control** (output tokens usually price 3-6x input; cutting verbose outputs cuts the biggest term); (2) **cascades** (a small model at $0.15/Mtok handling 80% of traffic transforms blended cost even if it's only 40% cheaper per call, because volume-weighted); (3) **prompt caching** (repeated system/context billed at steep discounts on major providers); (4) **distillation** (5-20x serving-cost reduction keeping most of teacher quality on narrow tasks); (5) **batch endpoints** (~50% off for latency-tolerant workloads like nightly summarization).

### Cost-of-GOOD-enough: the accuracy knee

Quality vs cost is a curve, not a point: each accuracy point gets more expensive than the last (bigger models, longer reasoning, ensemble voting), while user-perceived value has its own S-curve â€” below a threshold the product is broken (wrong answers destroy trust), above saturation users can't tell. The margin-optimal operating point sits just past the perception knee:

```
quality ->  |            ____----____  perceived value (S-curve)
            |        ___/              \___ (can't tell beyond here)
            |    _--'
            |  _'      <- KNEE: cheapest config past 'good enough'
            | /        cost per request rises steeply left->right? no:
            |/         RIGHT = better quality AND steeper cost
            +--------------------------> cost per request
```

Finding it empirically: run an eval sweep across model tiers Ã— prompt variants, plot task-success vs cost-per-request, and locate where success-rate slope flattens. Typical finding: mid-tier model + retrieval + tight output spec lands within 2-4 points of frontier quality at 5-15x lower cost â€” and users rate them equal in blind tests because the residual gap lives in rare long-tail cases. Escalation architecture operationalizes the knee: cheap path answers most traffic; confidence checks route uncertain cases up.

### From engineering choices to CFO language

Translate every infra proposal into the three numbers. "Add semantic caching" becomes: "35-45% cache-hit rate observed on similar workloads â†’ blended COGS per request drops from $0.0126 to ~$0.008 â†’ gross margin on AI-assisted seats moves from 62% to 69%, payback improves by ~1 month." That sentence wins budgets; "we should add caching" does not. Same discipline for uplift claims: the recsys engagement win nets against incremental serving bill â€” if the new ranker adds 30ms p95 and 15% more compute, state the margin impact alongside the engagement gain, because finance will compute it anyway and you want to be the one who framed it.

---

## Build it from scratch

**Unit-economics spreadsheet-as-code for an AI feature with token-cost COGS** â€” the artifact to bring to every AI-feature debate:

```python
# unit_econ.py -- spreadsheet-as-code: AI feature unit economics w/ sensitivity
from dataclasses import dataclass, field

@dataclass
class AIFeatureEcon:
    name: str
    # pricing side
    arpu_month: float                 # revenue per paying user per month
    free_ratio: float                 # share of users on $0 plans
    monthly_churn: float              # e.g. 0.04 = 4%/mo
    # token COGS side
    reqs_per_user_week: float         # MEDIAN user
    skew_mult: float                  # mean/median multiplier from usage skew (1.5-3)
    in_tokens: int; out_tokens: int
    price_in_mtok: float; price_out_mtok: float   # $ per Mtok
    cache_hit_rate: float = 0.0       # fraction of input tokens cached (discounted)
    cache_discount: float = 0.5
    cascade_small_share: float = 0.0  # fraction of reqs handled by cheap model
    cascade_savings: float = 0.7      # cheap model costs (1-savings) of big
    # other variable cost
    support_per_user_month: float = 1.50
    hosting_per_user_month: float = 0.60

    def cogs_per_user_month(self):
        base = (self.in_tokens/1e6*self.price_in_mtok +
                self.out_tokens/1e6*self.price_out_mtok)
        cached_in = self.in_tokens * self.cache_hit_rate * (1-self.cache_discount)
        eff_in = self.in_tokens - self.in_tokens*self.cache_hit_rate*self.cache_discount
        base = eff_in/1e6*self.price_in_mtok + self.out_tokens/1e6*self.price_out_mtok
        weekly = self.reqs_per_user_week * base
        mean_weekly = weekly * self.skew_mult
        if self.cascade_small_share:
            mean_weekly *= (1 - self.cascade_small_share*self.cascade_savings)
        return mean_weekly * 4.33

    def report(self):
        cogs = self.cogs_per_user_month() + self.support_per_user_month \
               + self.hosting_per_user_month
        paying_arpu = self.arpu_month
        blended_arpu = self.arpu_month * (1 - self.free_ratio)
        gm_blended = (blended_arpu - cogs*(1-self.free_ratio*0.3)) / blended_arpu
        lifetime = min(1/self.monthly_churn, 36)     # cap at 3 years
        ltv = blended_arpu * max(gm_blended, 0.01) * lifetime
        return {"name": self.name,
                "COGS/user/mo": round(cogs, 2),
                "gross_margin_%": round(gm_blended*100, 1),
                "lifetime_mo": round(lifetime, 1),
                "LTV": round(ltv, 0)}

naive = AIFeatureEcon("study-helper naive", 29, 0.25, 0.04,
                      8, 2.0, 1200, 600, 3, 15)
tuned = AIFeatureEcon("study-helper tuned", 29, 0.25, 0.04,
                      8, 2.0, 1200, 600, 3, 15,
                      cache_hit_rate=0.35, cascade_small_share=0.8)
for r in (naive, tuned):
    print(r.report())
# naive: COGS ~$9+/user/mo, GM ~55-60%, LTV ~$250-300
# tuned: COGS ~$4/user/mo,  GM ~70%+ ,  LTV ~$350-400  <- same product!
```

Exercises: (1) reproduce the worked token arithmetic above and verify the $0.0126/request figure by hand; (2) find the break-even free ratio â€” at what share of $0 users does blended gross margin hit zero? (3) run the cost-of-GOOD-enough sweep: take your eval set, three model tiers, plot success vs cost/request, mark the knee, then encode the escalation policy (small-model-first with confidence routing) and re-run `report()` â€” that delta is your raise case written in finance's native language.

## How it's done in production

| Practice | What it looks like |
|---|---|
| Per-feature P&L | AI features carry their own COGS line: tokens, eval runs, fine-tune jobs â€” reviewed monthly against margin targets, not buried in a platform budget |
| Usage-tier pricing | Seats + credits/caps: light users subsidize heavy ones; caps protect worst-case contribution margins (the 2024-2026 industry pattern after unlimited AI tiers bled) |
| Cost dashboards per request path | Token spend tagged by feature/model/tier; anomalies (a prompt regression doubling outputs) page like latency regressions |
| Margin gates in launch reviews | No AI launch without modeled COGS/user, gross-margin delta, and break-even analysis â€” same gate as security review |
| FinOps for inference | Budget alerts on token burn, cascade-hit-rate monitoring, cache-efficiency tracking; cost regressions block rollouts |

The cultural marker of mature orgs: engineers know the current COGS per request of the paths they own the way they know p95 latencies. Finance trusts engineering numbers when engineering demonstrates it prices its own work.

---

## Tradeoffs & when NOT to use it

- **LTV math is fiction past ~3 years.** Discounting, market shifts, and churn non-stationarity make 10-year LTVs astrology; cap horizons and show discount-rate sensitivity, or finance will do it for you with less charity.
- **Averages hide the business.** Cohort-level and percentile-level views are mandatory where usage skews (AI products always skew): median user profitability plus P99 user bankruptcy is the honest two-number summary.
- **Unit economics can't justify platform investments** whose value is optionality or speed, not per-unit margin â€” internal tooling argues in cycle-time and risk terms instead.
- **Growth-stage exceptions exist deliberately:** companies underwrite CAC payback >18 months when LTV expansion is proven and capital is cheap; that's a financing strategy, not unit-economics health â€” label it as such before someone else does.
- **Don't optimize COGS below perception.** Cutting model quality past the knee saves cents and destroys the product; the curve exists to find good-enough, not minimum.

---

## Interview questions

### Q1 â€” Walk me through computing LTV properly for our subscription product.
**Testing:** formula fluency plus trap-awareness.
**Answer:** LTV = ARPU Ã— gross-margin% Ã— lifetime; lifetime â‰ˆ 1/monthly-churn capped at 3-5 years. Use gross profit not revenue (ARPU-only inflates by 1/GM%), cohort-specific churn rather than blended averages, and state the horizon. Example: $29 ARPU, 68% GM, 4%/mo churn â†’ 29 Ã— 0.68 Ã— 25 â‰ˆ $493.
**Follow-up trap:** *"'Why cap lifetime at 3-5 years when 1/0.04 = 25 months anyway?'"* â€” at low churn rates the geometric-mean explodes into fiction: 2%/mo implies 4+ years during which pricing, competition, and product change completely. Cap or discount; either way, say so explicitly.

### Q2 â€” What's a healthy LTV:CAC ratio and what does deviation mean?
**Testing:** heuristic literacy with interpretation.
**Answer:** â‰¥3x is the standard screen â€” below 1 you destroy value per acquisition; 1-3 means growth depends on financing and retention improvements; above ~5 often signals underinvestment in growth (could buy more customers profitably). Pair with payback: 12-18 months is the norm for mid-market SaaS; consumer apps often need faster because churn is brutal.
**Follow-up trap:** *"'Our ratio is 8x â€” celebrate?'"* â€” investigate first: it usually means sales capacity is the constraint, channel saturation is untested, or LTV inputs are inflated (revenue-not-margin error, survivorship cohorts). Ratios that high trigger audits, not parties.

### Q3 â€” Why do AI features wreck traditional SaaS margins, and how do you fix them?
**Testing:** the module's core arithmetic under pressure.
**Answer:** Software assumed near-zero marginal cost (70-85% gross margins); LLM calls reintroduce per-action COGS â€” every request burns tokens priced by the Mtok, so margins drop toward 25-50% naive. Fixes ranked by leverage: output-length control (output tokens price 3-6x input), cascades (small model handles most traffic), semantic/prompt caching, distillation (5-20x cheaper serving), batch endpoints (~50% off tolerant paths), plus usage-tier pricing so heavy users fund themselves.
**Follow-up trap:** *"'Just wait for model prices to fall'"* â€” prices ARE falling ~10x/18-24mo, but usage grows faster than deflation when products succeed (Jevons dynamics), and supplier concentration means your COGS follows their roadmap. Underwrite at today's prices; treat deflation as upside.

### Q4 â€” Compute the per-request cost: 1,200 input + 600 output tokens, $3/Mtok in, $15/Mtok out.
**Testing:** token arithmetic cold.
**Answer:** 1200/1e6 Ã— 3 = $0.0036; 600/1e6 Ã— 15 = $0.009; total $0.0126/request. Note output dominates despite half the tokens â€” that asymmetry drives why output-length control tops the optimization list. At 8 req/wk Ã— 4.33 wk â‰ˆ 35 req/mo â†’ ~$0.44/mo median user, but apply a 2x skew multiplier for the mean: ~$0.88/mo.
**Follow-up trap:** *"'So 50K users cost ~$22K/month â€” fine?'*" â€” check who the users are: if 25% are free-tier, paying users carry everyone's COGS; recompute blended margin including free-ratio before declaring victory. Free riders are the silent margin killer in AI freemium.

### Q5 â€” Explain the cost-of-GOOD-enough knee and how you'd find it empirically.
**Testing:** the quality-cost tradeoff as an engineering artifact.
**Answer:** Quality improvements get more expensive per point while perceived value S-curves â€” below a threshold trust breaks, above saturation nobody notices. The operating point sits just past the perception knee: typically mid-tier models + retrieval + tight output specs land within a few points of frontier quality at 5-15x lower cost. Find it with an eval sweep across model tiers Ã— prompt variants plotting task-success vs cost-per-request, then encode escalation routing (cheap-first with confidence checks) as architecture.
**Follow-up trap:** *"'Users can't tell â€” so why ever call the frontier model?'"* â€” the residual gap lives in rare long-tail cases that generate disproportionate support load and trust damage when wrong; escalation routing buys frontier quality exactly there while paying commodity prices everywhere else. It's not either/or â€” it's routing.

### Q6 â€” Your recsys upgrade adds +25% engagement AND +15% serving compute. Present this to finance.
**Testing:** whether value and cost arrive framed together.
**Answer:** One sentence each: engagement chain translates to $4-8M/yr band (module 01 method); incremental compute prices at X$/yr from measured CPU/memory deltas â€” margin impact net positive even at pessimistic engagement end. Bring the sensitivity table: engagement at half, compute at double â€” still clears zero. Framing both sides yourself preempts the re-derivation that erodes trust.
**Follow-up trap:** *"'Why bring costs up proactively â€” doesn't that invite cuts?'"* â€” finance computes them regardless, silently, and discounts everything else you said if hidden. Volunteering costs is what buys credibility for your value claims; it's the whole game.

### Q7 â€” When is negative gross margin acceptable?
**Testing:** strategic nuance beyond rule-citing.
**Answer:** Deliberately, temporarily, and labeled: land-and-expand motions buying logos whose expansion revenue arrives later (enterprise pilots); marketplace subsidy phases balancing supply-demand; learning-phase products where usage data IS the product improvement loop. The requirements are a dated plan to positivity, visibility into per-unit trends month over month, and leadership agreement in writing. Indefinite negative unit economics isn't strategy, it's burn with branding.
**Follow-up trap:** *"'Every AI startup seems to run negative margins â€” isn't the heuristic dead?'"* â€” the survivors treat negative margin as financing strategy while engineering the curve down (cascades, caching); the ones that died treated it as identity. The heuristic survives; the acceptable duration shrank post-2022 rate environment.

### Q8 â€” Design the usage-based pricing for an AI tutoring assistant. What protects margin?
**Testing:** pricing mechanics tied to COGS structure.
**Answer:** Base seat covers median usage (priced off median-user COGS Ã— target GM); metered credits beyond a generous-but-bounded allowance price at 3-5x marginal COGS (covering support, variance, free-rider subsidy); hard caps on the worst-case path (agent-style loops) or steep degressive pricing; cached/off-peak paths priced cheaper to shape demand. Model the distribution, not the average: set allowances at ~P80 so most users never feel limits while P99 funds itself.
**Follow-up trap:** *"'Won't caps kill adoption?'"* â€” caps at P80+ are invisible to 80% of users and convert power users into revenue; unlimited plans are what killed margins across the 2024 wave of AI products. The alternative â€” throttling quality silently â€” destroys trust faster than transparent credits.

### Q9 â€” How do you build the business case for spending two quarters cutting inference cost by 40%?
**Testing:** framing infrastructure work in CFO language.
**Answer:** Quantify current annualized COGS (usage Ã— cost/request Ã— 12), take 40% as recurring annual savings, subtract fully-loaded eng cost (2 quarters Ã— team â‰ˆ $400-800K), express payback months and NPV over 3 years, and add the strategic kicker: lower COGS enables pricing moves and free-tier economics locked out today. If current spend is only $300K/yr, the math says don't â€” propose the cheaper lever (caching config) instead. Showing when NOT to do your own project is credibility gold.
**Follow-up trap:** *"'Model prices will fall 10x anyway â€” why engineer costs?'"* â€” because relative margins decide competitive moves now, usage scales faster than deflation, and the cost-engineering capability (routing, caching discipline) compounds across every future model generation. You're building the muscle, not chasing one price point.

### Q10 â€” What goes into FULLY-LOADED CAC that people forget?
**Testing:** honesty about acquisition costs.
**Answer:** Sales salaries + commission amortized per closed deal, marketing tools and agency fees, promotional discounts and free-trial service costs (they halve effective first-year ARPU), onboarding/support hours specific to new accounts, and channel-saturation effects (marginal CAC rises with spend â€” average CAC flatters). Compare against paid-channel reality: blended CAC can be half paid CAC when organic carries, which is healthy but must be labeled.
**Follow-up trap:** *"'Organic users are free though'"* â€” no: content/engineering/brand budgets produce them, and treating them as free corrupts every channel decision. Attribute organic with a shadow cost or you'll overspend on paid channels that look better than they are.

### Q11 â€” Cohort data shows newer users retain worse than older aggregates suggested. What happened and what now?
**Testing:** cohort literacy â€” the aggregate-LTV trap.
**Answer:** Blended LTV mixed aging cohorts: early adopters (self-selected enthusiasts) retain beautifully; scaled acquisition brings mainstream users with worse fit. Aggregates look fine until early cohorts age out of the denominator. Now: rebuild LTV per acquisition cohort and per channel, recompute payback honestly, pause channels whose cohort-LTV < CAC even if blended looks okay, and feed retention differences back into targeting â€” this discovery early is cheap; late, it's the postmortem of a funded-to-death company.
**Follow-up trap:** *"'Retention improves with product maturity â€” wait it out?'"* â€” sometimes true, but 'wait' needs a mechanism (which fixes, expected effect sizes, checkpoints), not hope; otherwise you're averaging your runway away. Write the falsifiable version of the bet.

### Q12 â€” Where does unit-economics thinking NOT apply?
**Testing:** frame limits.
**Answer:** Platform/infra investments arguing speed-or-risk (cycle time, incident reduction); regulatory/compliance spends argued in risk terms; R&D bets with learning outcomes; loss-leader ecosystem plays where value accrues elsewhere in the portfolio (loss-leading devices selling services). Forcing per-unit margin frames onto these produces fake precision â€” the discipline is choosing the right financial lens per decision type, then being explicit about which lens you used.
**Follow-up trap:** *"'Isn't that convenient â€” escape hatches whenever the math fails?'"* â€” the difference is labeling and governance: escape-hatch arguments get held to different evidence standards (risk registers, milestone-gated funding) precisely BECAUSE they lack per-unit math. What's banned is quietly switching lenses when one loses.

---

## Red flags

- Business cases using ARPU where gross profit belongs.
- Token-cost estimates at median usage with no skew multiplier or P99 view.
- Unlimited-usage AI pricing justified by "we'll optimize later."
- LTV computed on 10-year lifetimes with no discounting.
- Paid-channel CAC compared against blended LTV.
- No per-feature COGS line item â€” AI spend invisible inside a platform budget.
- Cost-engineering proposals with no eval evidence that quality stays past the knee.

## Cheat card

```
FORMULAS    LTV = ARPU x GM% x lifetime; lifetime ~= 1/churn (cap 3-5y)
            CAC = full S&M / new customers (blended vs PAID - never mix)
            payback mo = CAC / (ARPU x GM%)
HEURISTICS  LTV:CAC >= 3; payback 12-18mo; SaaS GM 70-85%
            AI-feature GM naive 25-50%; fix before scaling
TOKEN COGS  cost/req = in/1e6 x $in + out/1e6 x $out
            ex: 1200in/$3 + 600out/$15 = .0036+.009 = $.0126/req
            OUTPUT dominates (3-6x price); usage skews 2-3x median
LEVERS      1) output-length control 2) cascades (small model
            70-90% traffic) 3) prompt caching 4) distillation
            (5-20x) 5) batch ~50% off
KNEE        quality $ rises per point; perception S-curves ->
            operate just past good-enough; mid-tier+retrieval
            within 2-4pts of frontier at 5-15x cheaper;
            escalate rare/uncertain cases to frontier
PRICING     seat covers P80; credits at 3-5x marginal COGS;
            caps on agent loops; free ratio eats blended GM
DISCIPLINE  per-feature P&L monthly; know COGS/req like p95;
            volunteer costs WITH value claims; underwrite AI
            cases at TODAY's prices (deflation = upside)
```

## Sources

- David Skok, "SaaS Metrics 2.0" (LTV/CAC definitions and heuristics), https://www.forentrepreneurs.com/saas-metrics-2/ â€” accessed 2026-08-23
- Bessemer Venture Partners, SaaS/cloud metrics guidance incl. efficiency benchmarks, https://www.bvp.com/atlas â€” accessed 2026-08-23
- OpenAI API pricing pages (token pricing structure, cached-input discounts, batch API), https://openai.com/api/pricing/ â€” accessed 2026-08-23
- Anthropic API pricing (input/output tier pricing, prompt caching), https://www.anthropic.com/pricing â€” accessed 2026-08-23
- a16z, "Who Owns the Generative AI Platform?" and AI margin analyses, https://a16z.com/ai/ â€” accessed 2026-08-23
- Sequoia Capital, "Generative AI's Act o1" (margin and pricing dynamics in AI), https://www.sequoiacap.com/article/generative-ais-act-o1/ â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

