# Strategy: Porter, Moats, Build-vs-Buy, Platform vs Product, Wardley Maps

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-product-thinking Â· **Updated:** 2026-08-23
> **Module id:** `T25-strategy` Â· **Tags:** strategy

## The 30-second version

Strategy is the set of choices about where to play and how to win such that being different â€” not just better â€” produces durable returns, and the engineer-relevant core is four tools. **Porter's Five Forces** (supplier power, buyer power, threat of substitutes, threat of new entrants, rivalry) explains *why* an industry's profits pool where it does; his sharper insight for builders is that **operational excellence â‰  strategy**: running faster on the same treadmill as everyone else (the LLM-API-stack equivalent: everyone calls the same models through the same clouds) is efficiency, and efficiency competition converges everyone's margins toward zero. **Moats** are structural advantages that don't decay under competition â€” network effects, switching costs, economies of scale, brand/trust, regulatory position, data flywheels â€” and the interview-grade skill is testing a proposed moat with "what specifically would a well-funded attacker do, and what stops them?" **Build-vs-buy** resolves on where your differentiation actually lives: buy/build everything commodity (databases, now often base models), build only the layer where you compound advantage; the discipline is admitting which parts of your system are genuinely differentiated versus comfort builds. **Wardley Maps** make all this spatial: user needs on top, value-chain dependencies below, components plotted against evolution (genesis â†’ custom â†’ product â†’ commodity/utility), then exploit evolution mechanics â€” commodities become utilities, enabling previously impossible higher-order plays (electric grids enabled appliances). For a principal engineer, these are the vocabulary of every build-vs-buy war, platform bet, and "should we open-source this" debate you'll be asked to arbitrate.

## Why this gets asked

Principal interviews at product companies increasingly include a strategy segment because principals sit where architecture meets money: "Should we build our own embedding service or use the vendor?" "Why won't [cloud giant] crush us?" "What's defensible about our AI feature?" â€” these are staff+ questions precisely because wrong answers burn quarters. Interviewers screen for engineers who can reason about *where value accrues* in a stack: the 2023-2026 AI wave made this vivid, when application-layer startups discovered that model providers could ship their entire product as a "feature" overnight, while infrastructure layers (vector DBs, serving runtimes) got commoditized from both directions â€” open weights above, managed platforms below. On your resume, the 8-service recsys platform invites "which of those services would you buy today instead of building, and why did building make sense then?" A credible answer separates what was strategic (the ranking logic that encodes domain knowledge) from what was commodity (everything around it), and admits that the boundary moves as ecosystems evolve â€” which is exactly the Wardley point.

---

## Lineage: past â†’ present â†’ future

**What came before.** Michael Porter's *Competitive Strategy* (1980) and "What Is Strategy?" (HBR, 1996) supplied the frame: industry structure determines profit pools; firms win by choosing distinct positions with fit among activities, and the greatest error is "competing to be the best," which collapses into a quality-price convergence race. Clayton Christensen added disruption dynamics (The Innovator's Dilemma, 1997): incumbents get eaten from low-end and new-market footholds because rational resource allocation chases existing customers upmarket. Build-vs-buy formalized much earlier in transaction-cost economics (Coase 1937, Williamson 1970s-80s: firms internalize activities when market transaction costs exceed hierarchy costs). Simon Wardley mapped Sun Tzu onto tech evolution in the 2000s (blog-era work, *Wardley Maps* canonized in the O'Reilly "Wardley Maps" artcles and 2016+ talks): components evolve left-to-right from genesis to commodity driven by competition, and strategy means positioning along that drift.

**Where it stands now.** The live debates are all AI-shaped. Are foundation-model providers a utility (Porter: supplier power collapsing app margins) or a rent-extracting chokepoint that open-weight alternatives will discipline? Do data flywheels still constitute moats when synthetic data and transfer learning erode proprietary-data scarcity? Platform-vs-product decisions now hinge on model access economics: token COGS as a tollbooth (module 06), rate limits as supply contracts, fine-tuning lock-in as switching cost â€” some real, some illusory once you can export weights. Meanwhile Wardley mapping has quietly become the lingua franca of serious platform strategy inside large orgs (widely used at government digital services, banks, and cloud teams) because it converts religion ("we must own our ML stack") into position statements on an evolvable map that can be argued.

**Where it's heading.** Confidence-ordered: (1) commoditization pressure on model inference keeps intensifying â€” price per unit intelligence has fallen roughly 10x per 18-24 months across multiple generations, so any business case requiring current prices to persist is fragile; strategies that assume cheap inference (agentic everything) look smarter monthly; (2) regulation as a moat grows â€” EU AI Act compliance burdens (phased obligations through 2025-2027) advantage incumbents who can afford them, making "boring compliance excellence" a genuine defensive position; (3) contested: whether orchestration/framework layers (agents, RAG plumbing) capture durable value or get absorbed by the model layer's next release â€” history says middleware survives only by moving up the stack faster than platforms absorb it.

---

## Mental model

```
        VALUE CHAIN vs EVOLUTION  (a Wardley map skeleton)

 user need: "get answers from our documents"
        |
   +----+-----+------------------+
   |          |                  |
 chat UI   retrieval         generation
 [PRODUCT] [commodity-ish]   [UTILITY <- rented]
              |
        embeddings      chunking/index
        [commodity]     [custom -> product?]

 EVOLUTION AXIS:  genesis -> custom -> product -> commodity/utility
 READ: things to the RIGHT get cheaper & standardized;
       your DEFENSIBLE work lives LEFT of where markets mature,
       and each rightward drift ENABLES new leftward plays
```

Three lenses stack: **Five Forces** reads the profit pool around a position (who has power over whom); **moats** ask what structurally prevents displacement FROM that position; **Wardley** asks where components sit on the evolution axis and which way they're drifting. A build decision is correct only if the component sits left-of-commodity AND owning it compounds a moat; everything right-of-that line should be rented and re-evaluated annually, because utilities keep getting cheaper and betting engineering time against that drift is swimming upstream.

## How it actually works

### Five Forces, applied to an AI feature you're about to build

Run the audit in 20 minutes before committing a team: **Supplier power** â€” if your feature calls one model API, that vendor controls your COGS, latency ceiling, and roadmap (their pricing moves are your margin events; the 2023-2026 pattern of ~10x/18-24mo price declines cuts both ways: relief, but proof you don't control the curve). **Buyer power** â€” enterprise buyers with multi-year contracts and switching costs give YOU power; consumers with zero switching cost give themselves all of it. **Substitutes** â€” for "AI summaries," the substitute isn't a competitor's summaries, it's users reading the original document: your real competition is often non-consumption. **New entrants** â€” how many weeks would it take a funded team to replicate? If the honest answer is under 8 weeks and nothing compounds during those weeks, you have a feature, not a business. **Rivalry** â€” if five competitors ship near-identical features within two quarters (they will, when everyone rides the same base models), margins converge to support-cost levels.

### Moats: the catalog and the stress test

The durable categories: **network effects** (value grows with users â€” marketplaces, social graphs; test with "does user #4,001 get more value than #101?" â€” most claimed network effects fail this); **switching costs** (data gravity, workflow embedment, contract terms â€” enterprise SaaS's real moat); **economies of scale** (fixed costs amortized across volume â€” chip design, foundation training runs at $100M+); **brand/trust** (the reason enterprises pay premiums for "boring" vendors in risk-sensitive domains); **regulatory position** (licenses, certifications, compliance history); **process/data flywheels** (usage generates data that improves product that attracts usage â€” only real if the data is hard to replicate and actually feeds improvement loops). The stress test that separates moats from vibes: name the well-funded attacker, their attack path, and the specific structural thing that slows them by years not months. "Our AI tutor has better pedagogy" fails (attackers hire teachers); "our tutor holds 3 years of per-student mastery traces that transfer across grades" might pass (replication requires time Ã— students regardless of funding).

### Build-vs-buy as a moving boundary

The decision isn't static: every commodity was once custom (databases, payments, now embeddings), and utilities keep getting cheaper on schedule. The working rules: (1) **buy everything that doesn't differentiate** â€” renting Postgres beats running Postgres unless database operations ARE your product; (2) **build where ownership compounds a moat** â€” the ranking logic encoding three years of domain feedback is strategic; the service wrapper around it is not; (3) **watch the drift** â€” re-audit annually: components you built because vendors were inadequate get re-priced when vendors catch up (the entire 2015-2020 self-built ML-infra wave got partially re-bought as managed platforms matured); (4) **price exit before entry** â€” write the migration story BEFORE adopting any dependency: what's locked in, what's portable, what does week-one-after-deprecation look like. For LLM stacks specifically: abstraction layers (provider-neutral interfaces, exported prompts-as-config, eval harnesses independent of vendor) are cheap insurance against supplier-power shocks.

### Platform vs product

A product solves a user need directly; a platform makes OTHER builders productive and takes a cut. Platforms win bigger when they win (ecosystems compound) but die without supply-demand balance â€” the classic chicken-and-egg that kills most platform pivots (industry folklore: most platform pivots from products fail because the product's users weren't builders). The engineer-relevant tests: does anyone actually want to build on you (evidence: unsolicited integration attempts, API usage patterns)? Can you enforce the toll (API keys, billing, ToS â€” otherwise you're a free public good)? And do you accept the platform tax: backward-compatibility forever, ecosystem politics, and slower iteration (every breaking change strands third parties).

### Wardley mapping mechanics, minimal viable version

List user needs top; decompose into value-chain dependencies below; place each component on evolution (genesis = unique/uncertain, custom = bespoke, product = off-the-shelf with competition, utility = rented/commoditized); mark movement arrows where drift is visible. The map then yields plays: **commoditize a blocker** (open-source the component strangling your margin so the whole chain gets cheap â€” Amazon's classic playbook), **exploit inertia** (competitors' org charts resist utility adoption), **sensible substitution** (swap customâ†’product wherever possible to free engineers for left-of-map work). Its real power is political: arguments become position claims on a shared map ("you want us to hand-build what AWS sells at 1/40th our internal cost") instead of taste wars.

---

## Build it from scratch

**Exercise: map and decide a real build-vs-buy war (90 minutes, one page).**

Take your actual stack (or the tutoring platform): pick a contested component â€” say, the recommendation/ranking service versus "just use [vendor] personalization API."

1. **Wardley pass:** list needs â†’ dependencies (UI â†’ serving â†’ ranking â†’ features/embeddings â†’ storage) â†’ place each on genesisâ†’utility with arrows (embeddings drifting right fast; your mastery-model features sitting custom).
2. **Five Forces pass:** who supplies each dependency, what happens when they raise prices 5x or deprecate (real events: vendors deprecate APIs on 6-12 month notice).
3. **Moat pass:** for each BUILD box, run the attacker test â€” what stops a funded replica? Keep only passes.
4. **Decision ledger:** table with columns component / buy price ($/mo at YOUR volume) / build cost (eng-months + run cost) / moat contribution (0-3) / exit cost. Decide per row; total the engineering months freed by buying.

```python
# buildbuy.py -- decision ledger with weighted scoring
from dataclasses import dataclass

@dataclass
class Component:
    name: str
    eng_months_build: float          # fully-loaded ~$25-40K/month each
    monthly_run_cost: float          # $/month ongoing (infra + oncall + tokens)
    vendor_price_monthly: float      # $/month at your volume
    moat_contribution: int           # 0 none .. 3 core differentiator
    exit_cost_months: float          # cost to leave vendor later

    def verdict(self, horizon_years=3, hourly=90):
        eng_cost = self.eng_months_build * 160 * hourly
        build_total = eng_cost + self.monthly_run_cost * 12 * horizon_years
        buy_total = self.vendor_price_monthly * 12 * horizon_years \
                    + self.exit_cost_months * 160 * hourly   # option to leave
        moat_bonus = self.moat_contribution * 150_000       # strategic premium
        score = (build_total - moat_bonus) - buy_total
        call = "BUILD" if score > 0 else "BUY"
        return {"component": self.name,
                "build_3yr": round(build_total, -3),
                "buy_3yr": round(buy_total, -3),
                "net_of_moat": round(score, -3),
                "verdict": call}

rows = [
    Component("ranking-logic", 14, 4_000, 30_000, 3, 2),
    Component("vector-search", 3, 6_500, 2_400, 0, 1),
    Component("auth",          4, 3_000, 900,   0, 1),
]
for r in rows:
    print(r.verdict())
# ranking-logic -> BUILD (vendor can't encode your domain knowledge)
# vector-search -> BUY  (commodity, drifting right, exit is cheap)
# auth          -> BUY  (nobody's moat ever depended on hand-rolled OIDC)
```

The moat bonus column is deliberately crude but directionally honest: paying a premium to own something defensible is rational; paying it for plumbing is how teams end up maintaining databases out of pride.

---

## How it's done in production

| Org | Strategic practice | Engineer-visible artifact |
|---|---|---|
| Amazon | Working Backwards + "two-pizza" ownership maps onto value chains; famous commoditize-yourself plays (S3, EC2 turned internal utilities into businesses) | Service boundaries drawn along what could be externalized â€” every internal service has a hypothetical external customer |
| Google/DeepMind | Vertical integration where scale IS the moat (TPUs: $100M+ fixed costs amortized fleet-wide) | Build-vs-buy reviews weigh TPU economics vs GPU market pricing per FLOP |
| Apple | Integrated product moat via switching costs + brand; buys commodity components ruthlessly (screens, now often modems) | Engineers see the map as "which chips are strategic vs bought" â€” same ledger logic |
| Cloud vendors (AWS/Azure/GCP) | Wardley-style evolution exploitation: watch genesisâ†’utility drift, then launch managed versions of whatever enterprises still hand-run | Internal pattern reviews ask "what's becoming a utility?" quarterly |
| Open-source companies (HashiCorp-era debates) | License strategy as moat management (BSL/BUSL shifts 2023-2024 when cloud vendors absorbed OSS value) | The "should we open-source X" debate is literally a Five-Forces exercise |

The recurring production pattern: strategy documents that engineers actually use are one page with a MAP plus a LEDGER â€” anything longer gets skimmed and ignored. Teams re-audit annually because evolution arrows don't respect your roadmap: components you correctly classified as buy-able at last year's vendor maturity get cheaper again this year, while some custom component quietly became strategic (your data accumulated).

---

## Tradeoffs & when NOT to use it

- **Five Forces fits industries, not teams-of-five.** Applying industry-structure analysis to an internal tool choice produces theater; for small decisions, cost-plus-moat-ledger suffices. Reserve the full framework for bets with multi-year consequences.
- **Moats justify premiums but also excuse waste.** "Strategic" is the most expensive word in engineering; demand the attacker test before accepting any moat claim, and time-box strategic builds ("we own ranking until vendor parity + 1 year, then re-vote").
- **Wardley maps describe, they don't predict precisely.** Evolution direction is reliable; timing is not (utilities arrive years late or early). Use maps to choose positions robust to timing error, not to bet on dates.
- **Platform pivots from products usually die.** Without evidence builders exist among your users, platform-vs-product resolves to product-with-an-API; the chicken-and-egg tax is real and most orgs can't pay it.
- **Build-vs-buy isn't loyalty.** Re-evaluate on triggers (vendor price shock, deprecation notice, usage crossing volume tiers), not just annually; the ledger exists so re-deciding is cheap, not so the first decision is eternal.

---

## Interview questions

### Q1 â€” Should we build our own embedding/retrieval stack or use a vendor? Give your decision process.
**Testing:** build-vs-buy discipline rather than ideology.
**Answer:** Ledger it: build cost (eng-months Ã— loaded rate + run cost over horizon) vs vendor price + exit cost, scored against moat contribution. Retrieval plumbing is commodity drifting toward utility â€” rent it unless latency/regulatory constraints force self-hosting AND operating it teaches nothing proprietary. Keep custom only where domain knowledge compounds (chunking policy tuned to our corpus, eval harness encoding our quality bar).
**Follow-up trap:** *"'Vendor lock-in though'"* â€” lock-in matters proportionally to exit cost, which is an engineering choice: provider-neutral interfaces, portable indexes (re-embedding is hours of compute, not months of work), config-as-data. Price the exit explicitly; if it's under ~2 eng-months, lock-in is a talking point, not a risk.

### Q2 â€” What's a moat you've seen claimed that wasn't real, and how did you test it?
**Testing:** skepticism mechanics.
**Answer:** Common fake: "our AI feature is better because we fine-tuned" â€” tested with the attacker question: funded competitor replicates fine-tuning in weeks if the data isn't structurally scarce. Real-ish version: three years of per-user interaction traces feeding continuous improvement â€” replication needs timeÃ—users regardless of budget. The test is always: name the attacker, name the path, name what slows them by YEARS.
**Follow-up trap:** *"'Data network effects' â€” real or buzzword?"* â€” usually weak: marginal data value decays logarithmically (the billionth example adds little), and much "proprietary" data is scrapeable or synthetic-generatable. It's real only when data is hard to replicate AND demonstrably feeds the improvement loop AND competitors can't substitute.

### Q3 â€” Explain Porter's 'operational effectiveness is not strategy' using an AI-stack example.
**Testing:** whether they understand positioning vs efficiency.
**Answer:** Every team calling the same frontier model through the same cloud with similar RAG plumbing is competing on operational effectiveness â€” whoever tunes prompts harder wins briefly, and improvements diffuse, converging everyone toward identical output at identical COGS. Strategy would be choosing a position others can't or won't occupy: proprietary evaluation depth in a regulated niche, workflow embedment creating switching costs, or owning distribution the model layer lacks.
**Follow-up trap:** *"'So prompt engineering is worthless?'"* â€” no, it's valuable but non-defensible: necessary table stakes whose returns accrue temporarily until diffusion catches up. Worth doing; wrong to call it strategy.

### Q4 â€” Draw a mini Wardley map for a RAG product and identify one strategic play.
**Testing:** mapping fluency under interview conditions.
**Answer:** Need: trusted answers from private docs. Chain: chat UI (product), orchestration (customâ†’product fast), retrieval (commodity-ish), embeddings (utility), base generation (utility). Play candidates: commoditize the orchestrator bottleneck by open-sourcing ours (competitors' chains get cheap, but our eval-harness advantage becomes the visible differentiator); or exploit inertia â€” enterprises won't hand docs to raw APIs, so the compliance-wrapped deployment layer captures margin even though every component inside is commodity.
**Follow-up trap:** *"'Maps say embeddings are utility â€” why do vector DB startups raise millions?'"* â€” evolution position â‰  current profit: windows exist between genesis and full utility where product-form vendors capture real money; the map predicts their END state (absorbed into databases/clouds as features), not their near-term revenue.

### Q5 â€” When does vertical integration beat buying? Concrete example.
**Testing:** transaction-cost intuition applied to tech.
**Answer:** When the component is both critical AND the market can't supply it at required spec/scale: Google's TPUs ($100M+ design amortized across a fleet that buys no margin-marked GPUs), Amazon's fulfillment software, Apple silicon. Conditions: huge stable volume to amortize fixed costs, differentiated requirements markets won't prioritize, tolerance for maintaining non-core expertise. Absent those, integration is empire-building.
**Follow-up trap:** *"'Should a mid-size company self-host open-weight models?'"* â€” usually no below meaningful scale: serving engineering + GPU ops costs several engineers' fully-loaded time (~$1M+/yr) versus API prices falling ~10x per 18-24 months â€” the drift is against you. Cross-over cases: extreme privacy constraints, predictable giant volumes, or latency-critical edge inference.

### Q6 â€” Your CEO says '[Cloud Giant] could clone us.' How do you assess the threat seriously?
**Testing:** Five Forces applied without panic.
**Answer:** Ask what cloning requires: distribution (do they have our channel?), the data loop (years of usage traces?), workflow embedment (migration friction for installed users?), and incentive (is our market big enough to matter to them, and does it cannibalize their existing lines?). Cloud giants absorb categories where infrastructure leverage applies; they're slow where success depends on messy vertical workflows and trust. Score each factor honestly; the output is either 'real risk â†’ differentiate into workflow/trust layers now' or 'noise â†’ stop relitigating.'
**Follow-up trap:** *"'They gave a keynote demo of exactly our feature'"* â€” keynotes signal interest, not commitment; check whether they shipped AND maintained the category after 18 months. Vaporware demos kill more startups than actual competition does by inducing premature pivots.

### Q7 â€” Platform or product for our API-first tutoring engine? What evidence decides?
**Testing:** platform literacy including its failure modes.
**Answer:** Evidence first: unsolicited integration attempts, users scripting against exposed endpoints, partner inquiries â€” platforms are pulled, rarely pushed. Then the toll test: can billing/enforcement actually work (metering, ToS teeth)? Then accept the platform tax: backward compatibility forever, slower iteration, ecosystem politics. Without builder evidence, ship product-with-clean-API and revisit â€” pushing platform on a user-base of end-consumers is how most platform pivots die.
**Follow-up trap:** *"'APIs make us look bigger for fundraising'"* â€” narrative-driven platforms accumulate surface area without ecosystem; every public endpoint is a compatibility liability. Ship private integrations for named partners instead; formalize into platform only when partners outnumber your own roadmap.

### Q8 â€” Where do switching costs actually come from in enterprise SaaS?
**Testing:** moat catalog precision.
**Answer:** Data gravity (accumulated records + integrations nobody wants to rebuild), workflow muscle memory across hundreds of users, permission/config archaeology, compliance certifications tied to the incumbent audit history, contract structures (multi-year, bundled discounts), and the internal-political cost of championing a migration that might fail. Individually small, jointly worth 20-40% price premiums and brutal churn resistance â€” which is why sales-led enterprise software tolerates mediocre products better than consumer ever could.
**Follow-up trap:** *"'So consumer products have no switching costs?'"* â€” different currency: habit loops, social graphs, content libraries (photos, playlists), identity portability pain. Weaker contractually, stronger emotionally; explains why better consumer products routinely fail against entrenched defaults.

### Q9 â€” Should we open-source our core framework?
**Testing:** strategy reasoning about commoditization and control.
**Answer:** Open-sourcing commoditizes YOUR component: rational when it blocks a competitor's complementary revenue, accelerates ecosystem adoption toward something you monetize elsewhere (hosting, support, enterprise features â€” the classic open-core split), or recruits talent. Irrational when the component itself IS the differentiation with no adjacent monetization. Also decide license deliberately post-2023: cloud vendors absorbing OSS value drove BSL/aggressive-license shifts (HashiCorp 2023); pick terms matching who you'd sue.
**Follow-up trap:** *"'Open source = free marketing, always net positive?'"* â€” maintenance burden is permanent and community governance is a skill most teams lack; abandoned OSS destroys brand equity faster than never shipping it. Budget maintainership (commonly cited: sustainable OSS needs dedicated staffing) before counting the marketing win.

### Q10 â€” Regulators add major AI-compliance obligations effective 2026-2027. Threat or opportunity?
**Testing:** regulatory-as-strategy thinking.
**Answer:** Both, asymmetrically: compliance costs favor incumbents who can amortize audit/tooling across revenue, so it raises entry barriers protecting installed bases â€” an opportunity disguised as burden. For challengers, the play is compliance-forward positioning in risk-sensitive segments (health, finance, education) where buyers pay premiums for certified boringness. Either way: build the evidence pipeline (eval logs, documentation, incident response) once, reuse forever â€” compliance engineering done generically becomes a moat input.
**Follow-up trap:** *"'Won't regulation kill innovation?'"* â€” it kills SOME paths (high-risk unassessed deployments), redirects capital toward auditable designs, and historically rewards organizations that treat it as architecture (privacy-by-design era) rather than paperwork bolted on late.

### Q11 â€” Vendor announces 5x price increase on your core dependency. Walk the playbook.
**Testing:** supplier-power crisis management.
**Answer:** Immediate: quantify exposure (COGS impact per unit economics â€” module 06 framing), invoke contract terms, negotiate using credible alternative as leverage. Parallel: activate the pre-priced exit plan (this is why exit cost was written before entry): abstraction layer means weeks not quarters. Strategic: log the event into the ledger process â€” dependency concentration that survives one shock invites the next; diversify where cheap (dual-provider interfaces), accept where switching costs exceed expected repeat-shock losses.
**Follow-up trap:** *"'Just pass the cost to customers'"* â€” depends on buyer power and elasticity: consumer apps with free tiers eat it; enterprise contracts may forbid repricing mid-term. Passing cost silently through margin compression instead hides the strategic problem from leadership â€” surface it with numbers.

### Q12 â€” What's the difference between a feature, a product, and a business? Why does it matter for resourcing?
**Testing:** strategic vocabulary depth.
**Answer:** A feature improves an existing product (defended by the host product's moats); a product solves a need directly and must stand on acquisition+retention economics; a business wraps products in durable economics â€” margins above COGS, retention above replacement, defensibility against the forces. Resourcing follows: features get incremental headcount against host-product metrics; products need dedicated go-to-market; businesses need the full ledger (CAC, LTV, moat plan) BEFORE scaling investment. Mislabeling a feature as a business is how companies fund orphaned teams that neither move the host nor survive alone.
**Follow-up trap:** *"'Our AI assistant started as a feature â€” when does it deserve business-level investment?'"* â€” when it shows independent retention (users return for IT specifically) and unit economics that survive standalone attribution: separate activation funnel, measurable willingness-to-pay, and a defensible wedge. Until then it borrows the parent's moat and shouldn't pay business-team prices.

---

## Red flags

- Build decisions justified by "control" or "flexibility" with no moat analysis or ledger.
- Moat claims that fail the attacker test ("we hire good people," "our prompts are better").
- No exit-cost estimate written down before adopting any vendor dependency.
- Platform pivot without evidence anyone wants to build on you.
- Strategy decks with no map, no ledger, and no falsifiable position statements.
- Business cases requiring current LLM prices to persist (they won't).
- "We should open-source it" decided without a license/maintenance/monetization answer.

## Cheat card

```
FIVE FORCES   suppliers / buyers / substitutes / entrants / rivalry;
              read WHO holds power over your margin pool
PORTER RULE   operational excellence != strategy; identical stacks
              converge to identical COGS -> zero-margin rivalry
MOATS         network effects, switching costs, scale economies,
              brand/trust, regulatory, data flywheels
              ATTACKER TEST: who, path, what slows them YEARS?
              data flywheels: only if scarce AND feeds improvement loop
BUILD-vs-BUY  ledger: eng-months x $25-40K loaded + run cost
              vs vendor price + EXIT COST; moat premium 0-3 scale
              rules: rent everything right-of-custom; annual re-audit;
              write exit plan BEFORE entry
PLATFORM      pull not push (unsolicited builders?); toll enforceable?;
              platform tax: compat forever, slow iteration
WARDLEY       needs top, dependencies below; genesis->custom->
              product->utility; direction reliable, TIMING is not;
              plays: commoditize blocker, exploit inertia
AI ERA        model inference -> utility drift (~10x/18-24mo price fall);
              any case needing current prices is fragile; compliance
              excellence = rising moat; middleware must outrun absorption
```

## Sources

- Michael E. Porter, "What Is Strategy?" Harvard Business Review (1996), https://hbr.org/1996/11/what-is-strategy â€” accessed 2026-08-23
- Michael E. Porter, *Competitive Strategy* (Free Press, 1980); Five Forces overview https://hbr.org/1979/03/how-competitive-forces-shape-strategy â€” accessed 2026-08-23
- Simon Wardley, *Wardley Maps* / medium book draft, https://medium.com/wardleymaps â€” accessed 2026-08-23
- Clayton M. Christensen, *The Innovator's Dilemma* (Harvard Business School Press, 1997) â€” accessed 2026-08-23
- Oliver Williamson, *Markets and Hierarchies* (1975); Coase, "The Nature of the Firm" (1937), https://en.wikipedia.org/wiki/The_Nature_of_the_Firm â€” accessed 2026-08-23
- Jerry Neumann, "Moats" reaction essays incl. "The Moat Map," https://reactionwheel.net/ â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

