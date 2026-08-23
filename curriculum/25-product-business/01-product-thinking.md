# Product Thinking for Engineers: Problem â†’ Outcome â†’ Solution

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** none (pairs with T14 behavioral track) Â· **Updated:** 2026-08-23
> **Module id:** `T25-product-thinking` Â· **Tags:** product, critical

## The 30-second version

Product thinking is the discipline of decomposing any "we should build X" into three layers in strict order: the **problem** (who hurts, how often, how much it costs them), the **outcome** (a measurable change in user or business behavior that would prove the problem got smaller), and only then the **solution** (the cheapest artifact plausibly capable of moving that outcome). Engineers are trained to start at layer three; a principal engineer who can walk the chain backwards â€” from a proposed feature to the outcome it claims to move to the problem underneath â€” wins resource debates because they convert opinion ("I think we need AI summaries") into arithmetic ("this targets $1.2M/yr of churn driven by time-to-answer; here's the smallest experiment that tests it"). The core moves: refuse to discuss solutions until the outcome has a number and a date; treat every feature request as a hypothesis, not an order; and know your company's unit economics well enough to translate engineering deltas (latency, accuracy, engagement) into dollars â€” because the person deciding whether your project gets headcount is doing exactly that translation, just worse.

## Why this gets asked

At the principal level nobody asks you to code a feature spec â€” they ask "tell me about a time you disagreed with a PM" or "how do you decide what NOT to build," and both probe the same thing: do you behave like someone who owns outcomes, or like a very fast order-taker? The interviewer â€” usually a director or distinguished engineer who has personally killed projects â€” wants evidence that when handed a half-formed idea from a VP, you ask "what user problem does this solve and how would we measure it" before asking "what's the architecture." On this candidate's resume there's an 8-service recommendation platform; the natural follow-up is "you drove ~25% engagement lift â€” what was that worth, and how did you know?" If the answer stops at "the metric went up," the interview stalls at senior. If the answer walks engagement â†’ session depth â†’ retention â†’ revenue per user with numbers and a guardrail caveat, it lands at principal. This module builds that reflex deliberately.

---

## Lineage: past â†’ present â†’ future

**What came before.** For most of software history the engineer's relationship to product decisions was contractual: a systems analyst gathered requirements, froze them in a specification, and engineering implemented. Waterfall-era process standards (DoD-STD-2167A, issued 1988 for defense software) made deviation from spec a compliance failure, which made thinking about *why* a feature existed somebody else's department. The backlash came in two waves: Agile (the 2001 manifesto) collapsed the freeze cycle but mostly changed *delivery cadence*, not decision ownership â€” many "Agile" teams still received tickets fully specified by someone else. The genuinely structural shift was Lean Startup (Eric Ries, 2011) importing validated-learning logic (descending from Toyota's genchi genbutsu â€” go and see for yourself), plus Steve Blank's customer development: features are experiments, and the build-measure-learn loop is the unit of progress, not shipped code.

**Where it stands now.** The current synthesis is Marty Cagan's dual-track model (discovery runs continuously ahead of delivery, popularized in *Inspired*, first edition 2008, revised 2017) and Teresa Torres's *Continuous Discovery Habits* (2021), which pushes weekly customer touchpoints down to the team level. Josh Seiden's *Outcomes Over Output* (2019) supplied the vocabulary this module uses: an outcome is "a change in human behavior that the organization believes will drive business results" â€” not a shipped feature list. Amazon formalized the extreme version with Working Backwards (PR/FAQ before code, built out in the mid-2000s). The state of play in 2026: most large tech orgs nominally run OKRs layered over roadmaps, but the failure mode is chronic â€” output theater, where "outcomes" are deliverables wearing metric costumes ("ship AI copilot" is an output; "cut median time-to-first-insight from 9 minutes to 3" is an outcome). Engineers who can spot and fix this in their own team's planning docs are rare enough that it reads as leadership, not scope-grabbing.

**Where it's heading.** Three visible trends, highest confidence first. First, the rise of the "product engineer" â€” small AI-leveraged teams (commonly cited examples run 5-15 engineers shipping what took 50+) collapse the discovery/delivery handoff, so engineers run interviews and metric reviews directly rather than receiving PRDs; startups have always worked this way and the pattern is migrating into enterprise teams. Second, AI features make outcome discipline *harder* and therefore more valuable: demo-driven enthusiasm ("it works on 3 cherry-picked prompts, ship it") collapses against a defined outcome, so people who insist on baseline, guardrails, and success thresholds before building become the brake everyone complains about and nobody will fire. Third â€” moderate confidence â€” measurement tooling keeps getting cheaper (experimentation platforms, warehouses, LLM-assisted analysis), shifting the scarce skill from *access to data* to *knowing which outcome matters*; expect interview signal to move further toward metric reasoning and away from process recitation.

---

## Mental model

```
        WHAT PEOPLE SAY                 WHAT YOU SHOULD HEAR
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ "Build AI summaries    â”‚      â”‚ SOLUTION: one candidate answer  â”‚
   â”‚  in the dashboard"     â”‚ â”€â”€â”€â–º â”‚ PROBLEM: users abandon reports  â”‚
   â”‚                        â”‚      â”‚   before acting on them         â”‚
   â”‚                        â”‚      â”‚ OUTCOME: % of reports leading   â”‚
   â”‚                        â”‚      â”‚   to a next action within 48h   â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜      â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

The chain is **problem â†’ outcome â†’ solution**, and every arrow is falsifiable:

- **Problem:** a specific population Ã— a specific pain Ã— a frequency/cost. Weak version: "users want insights." Strong version: "analysts at our top-20 accounts open a report, scan for 90 seconds, and leave without exporting or sharing â€” 34% of weekly actives do this at least twice a week."
- **Outcome:** the behavioral change that would prove the pain shrank, stated as *metric + direction + magnitude + timeframe*. Weak: "improve engagement." Strong: "raise report-follow-through from 12% to 18% within two quarters without degrading p95 load time."
- **Solution:** the cheapest testable artifact. Multiple valid solutions exist per outcome â€” which means solution debates held *before* the outcome is fixed are unfalsifiable preference arguments, i.e., politics.

The inversion trick: whenever someone proposes a solution, walk *up* the chain â€” "what outcome would tell us this worked? What problem does that outcome imply?" If either step has no crisp answer, the proposal isn't ready to be argued on its merits; it goes back through discovery (module 02).

---

## How it actually works

### The three artifacts, in order

**1. Problem statement.** One paragraph, five components: who (segment, sized), what pain (observable behavior, not adjectives), when/how often, what it costs them (time, money, risk), and why now (what changed â€” a new capability like LLMs, new regulation, a competitor move, a cost curve crossing). "Why now" is the most-skipped and most-decisive component: a real problem with no forcing function loses to a mediocre problem whose time is this quarter. A usable template:

> *[Segment] currently [observable painful behavior] [frequency]. This costs them [quantified cost] and us [quantified business cost]. It's tractable now because [why-now].*

**2. Outcome definition.** Three properties separate a real outcome from an output in disguise. It measures **user behavior** (not delivery: "% of reports with summaries enabled" is deployment telemetry, not value); it has a **baseline** (you know today's number and trust how it's measured); and it carries **guardrails** (what you must not break while moving it â€” for a recsys engagement push: relevance score, p95 latency, diversity, complaint rate). The magnitude comes from sizing the problem: if the abandoned-report population represents an estimated $1.2M/yr of churn contribution and follow-through correlates with renewal, a 6-point improvement plausibly returns $200-400K/yr depending on the elasticity assumption â€” and stating that range honestly persuades CFO audiences more than any single confident number, because they discount false precision hard.

**3. Solution candidates.** Generate at least three before evaluating one â€” the discipline matters more than the ideas' quality, because single-candidate evaluation collapses into advocacy. Price each: eng-weeks, ongoing run-cost (for AI features, tokens per request Ã— volume â€” worked in module 06), risk, time-to-first-evidence. Pick by expected value per week, not novelty. The standard failure here is the **hammer looking for nails**: the team has a shiny capability (an LLM, a vector DB) and searches backward for justification. The tell is that the problem statement gets written *after* the solution choice, and bends suspiciously to fit it.

### Translating engineering deltas to money (the skill that wins debates)

Your recsys platform drives a measured ~25% relative lift in engagement versus the previous ranker â€” sessions where users interact with recommended items. Nobody funds "engagement." The translation chain, each link owned by a named assumption:

```
+25% engaged interactions/session
  â†’ +X% session length        (measured: 11 min â†’ 13.2 min, +20%)
  â†’ +Y pts 7-day return rate  (cohort data: 41% â†’ 46%, +5pts)
  â†’ +Z revenue/user           (LTV model: each +1pt D7 â‰ˆ +$0.31 ARPU/mo)
  â†’ 5pts Ã— $0.31 Ã— 4.2M MAU   â‰ˆ $6.5M/mo upper bound; present $4-8M/yr band
  MINUS guardrail check: relevance -0.3% (flat), latency +40ms p95 (within budget)
```

Every arrow needs a confidence label: the first two links are within-platform measurements (high confidence); the third is a correlational model (medium â€” cite the regression fit or admit it's a heuristic); the fourth multiplies a point estimate across the whole base (hence the band). Presenting the chain *with its weakest link labeled* separates a principal-level business case from a slide that finance quietly re-derives and disbelieves. The same machinery runs in reverse for cost: an AI feature adding 2,000 tokens per request at $3 per million input tokens costs $0.006/request; at 10M requests/month that's $60K/mo of COGS â€” so the question flips from "does it work?" to "does the outcome it moves clear $720K/yr?" (full treatment in modules 06-07).

### The four conversations you'll actually have

Product thinking shows up as four recurring conversational moves. (1) **The reframe:** a VP says "build X"; you respond "help me understand â€” is the goal outcome A or outcome B? They suggest different smallest-tests." (2) **The kill:** a proposal's best-case math doesn't cover its fully-loaded cost (two engineers Ã— two quarters â‰ˆ $400-600K opportunity cost alone) â€” you present the arithmetic and let the room draw the conclusion, never editorializing. (3) **The sequence:** two proposals target the same outcome; the cheaper one producing evidence in 3 weeks beats the thorough one taking a quarter, because information compounds. (4) **The guardrail veto:** a change moves the headline metric while breaching a guardrail threshold â€” you're the person who wrote the threshold down beforehand, which is what makes the veto non-political.

---

## Build it from scratch

**Exercise: decompose a live feature request in 45 minutes.** Take the vaguest ticket in your actual backlog (if none: "add an AI study-buddy to our tutoring app"). Produce, on one page:

1. **Problem statement** using the five-component template, with a segment size you defend with a query you actually ran or an estimate with named assumptions.
2. **Outcome spec:** primary metric, baseline value with source, target magnitude, timeframe, plus two guardrails with thresholds.
3. **Three solution candidates** priced in eng-weeks and ongoing run-cost, each with time-to-first-evidence.
4. **The kill question:** what cheaply observable result would make you cancel? Write it down *before* building â€” this is pre-registration for product work, and skipping it is how zombie projects survive.

Then run the $-translation drill on your own work: take any metric you've moved in the last year (latency, recall@k, engagement) and produce the chain from that delta to revenue or cost, labeling each link measured / modeled / assumed. If a link has no defensible number, that's the finding â€” it names the instrumentation to build next, which turns "business thinking" into an engineering backlog item.

```python
# outcome_ledger.py -- turn an engineering delta into a dollar range, honestly

def revenue_band(mau, d7_pts_gained, arpu_per_d7_pt, low=0.5, high=1.5):
    """Each modeled link widens the band; output is a RANGE, not a point."""
    mid = mau * d7_pts_gained * arpu_per_d7_pt
    return {"annual_low": round(12 * mid * low, -3),
            "annual_mid":  round(12 * mid, -3),
            "annual_high": round(12 * mid * high, -3)}

# recsys example: 4.2M MAU, +5pts D7 retention, $0.31 ARPU per D7 pt (modeled)
print(revenue_band(4_200_000, 5, 0.31))
# -> {'annual_low': 3906000, 'annual_mid': 7812000, 'annual_high': 11718000}
# lead with the band + weakest-link label, never the midpoint alone

def ai_feature_breakeven(requests_per_month, tokens_per_request,
                         price_per_mtok, value_moved_annual):
    cogs = requests_per_month * tokens_per_request / 1e6 * price_per_mtok * 12
    return {"cogs_annual": round(cogs),
            "net_annual": round(value_moved_annual - cogs),
            "net_margin": round((value_moved_annual - cogs)
                                / max(value_moved_annual, 1), 3)}

# 10M req/mo x 2K tokens x $3/Mtok = $720K/yr COGS floor
print(ai_feature_breakeven(10_000_000, 2_000, 3, 2_500_000))
# -> {'cogs_annual': 720000, 'net_annual': 1780000, 'net_margin': 0.712}
```

The second function is the habit that matters: before arguing whether an AI feature is good, compute its COGS floor and net margin mechanically, so the debate starts from arithmetic instead of enthusiasm.

---

## How it's done in production

| Company | Mechanism | What the engineer actually does |
|---|---|---|
| Amazon | Working Backwards: PR/FAQ drafted before any code; the FAQ forces the customer-value claim into plain prose | Reviewers attack the press release's claims; engineers defend the feasibility/cost section, which sits adjacent to the value claim in the same doc |
| Spotify | DIBB (Data â†’ Insight â†’ Belief â†’ Bet): strategy cascades as beliefs that teams convert into bets | Each bet names its leading indicator, so "done" is a metric movement, not a merge |
| Google | Design docs require an explicit background/problem statement and an "alternatives considered" section before launch review | Reviewers reject docs whose alternatives are straw men â€” this is where product thinking leaks into engineering culture |
| Netflix | Memo culture, "farming for dissent": a proposal circulates with named dissenters before any meeting | Engineers write and circulate these memos themselves; the dissent section kills weak projects before they consume quarters |
| Stripe | RFC culture with an explicit "why now" and "what we're not doing" | The "not doing" paragraph is highest leverage â€” it converts implicit scope fights into explicit decisions |

The common structure across all five: the value claim and the cost claim live in the *same document, adjacent*, so neither can be argued in isolation. Teams where those claims live in different documents (PM deck vs. eng estimate spreadsheet) systematically underprice projects, because each side optimizes its own document.

---

## Tradeoffs & when NOT to use it

- **Don't demand quantified outcomes from genuinely exploratory work.** Research spikes and "can this even work" prototypes have learning outcomes, not metric outcomes; demanding a revenue projection for a 1-week spike is cargo-culting. The honest framing is "spend â‰¤N weeks to buy answer M" â€” bounded cost, binary question.
- **Don't fake precision to win a meeting.** A "$7.8M impact" derived from an unvalidated correlation gets found out in the finance review, and one inflated number can poison your next ten honest ones. Lead with ranges; name the weakest link yourself before anyone else does.
- **Compliance, security, and reliability work doesn't fit the outcome frame.** These are constraint-driven: the outcome is absence-of-bad-event, which resists uplift math. Argue them in risk terms (expected loss avoided, audit exposure), not growth terms â€” switching frames to match work type is itself the skill.
- **Problem-first can become procrastination.** A team endlessly refining problem statements never learns anything reality could teach it; discovery is timeboxed (Torres's cadence is weekly touchpoints, not quarterly studies) and closed by shipping something small.
- **Not every ticket deserves the full chain.** Executing a well-understood pattern (another CRUD screen) with full problem-outcome ceremony wastes everyone's time; calibrate rigor to reversibility â€” one-way doors get the full treatment, two-way doors get a paragraph.

---

## Interview questions

### Q1 â€” A PM hands you a fully-specced feature. What do you do before writing any design doc?
**Testing:** whether product thinking is a lived reflex or interview vocabulary.
**Answer:** Read the spec for its implied outcome, then meet the PM with questions in order: what user behavior changes if this ships and works; what's today's baseline for that behavior and where's it measured; what guardrails matter; what evidence would kill it post-launch. Only after the outcome is crisp do I evaluate the proposed solution against cheaper alternatives targeting the same outcome.
**Follow-up trap:** *"What if the PM says 'just build it, it was decided upstairs'?"* â€” build the smallest slice that generates outcome evidence anyway, instrumented before launch. If it works you've created proof for the next investment; if it doesn't, you've limited the burn. Resisting mandates openly loses influence; measuring them builds it.

### Q2 â€” Your recsys drove a ~25% engagement lift. What was it worth?
**Testing:** the translation skill this module exists for; the resume-probing moment.
**Answer:** Engagement isn't money, so I show the chain: +25% engaged interactions translated to ~+20% session length (measured), which correlated with +5pts on 7-day return (cohort data); our LTV model priced each D7 point at ~$0.31 monthly ARPU, giving 5 Ã— $0.31 Ã— 4.2M MAU â‰ˆ $6.5M/mo at face value â€” presented honestly as a $4-8M/yr band because the ARPU-per-point link is a model, and I name it as the weakest link myself.
**Follow-up trap:** *"Why a range instead of the point estimate?"* â€” because finance will re-derive it; a range with named assumptions survives scrutiny while false precision invites distrust of everything else you said. And the band carries the real decision info: even the pessimistic end clears this project's cost.

### Q3 â€” Tell me about a project you killed or deprioritized. How did you do it?
**Testing:** evidence of the kill reflex â€” the rarest principal-level signal.
**Answer:** A proposed personalization feature had a best-case story around $300K/yr against a fully-loaded cost of two engineers for two quarters (~$500-600K opportunity cost) plus ongoing inference spend. I didn't argue taste; I built the one-page ledger showing best-case value below worst-case cost, plus a cheap 2-week probe that would have to come back wildly positive to change the math. It was deprioritized within one review cycle.
**Follow-up trap:** *"Didn't killing it cost you political capital with the requesting exec?"* â€” less than shipping it would have: failed projects cost credibility twice, once in spend and once in the postmortem. Framing matters â€” "the math says not yet" preserves the relationship; "I don't like it" spends it.

### Q4 â€” How do you decide what NOT to build when everything requested sounds reasonable?
**Testing:** whether prioritization is arithmetic or vibes.
**Answer:** Force every candidate onto one axis: expected outcome value per engineering week, using each proposal's own stated assumptions. Reasonable-sounding proposals die on contact with their own numbers â€” a feature serving 2% of accounts with a plausible $50K/yr return loses to anything with better value density. Where values tie, prefer the option that produces information fastest.
**Follow-up trap:** *"Isn't that reductive â€” some things matter that can't be quantified?"* â€” yes, and I say so explicitly: strategic bets, platform health, and trust get argued qualitatively but deliberately labeled as such. What's unacceptable is pretending a qualitative preference is a quantitative case; mislabeled arguments are how politics beats arithmetic.

### Q5 â€” What's the difference between an output and an outcome? Give a real example from your work.
**Testing:** vocabulary depth â€” this distinction is the module's core.
**Answer:** An output is what you ship (a feature, a service, 12 releases); an outcome is the behavioral change that justifies it (users completing more learning sessions per week). From my recsys work: "migrate ranker to the new two-tower model" is output; "+5pts D7 return rate without degrading relevance below threshold" is outcome. Outputs are fully inside engineering's control; outcomes require users to change behavior, which is why they need measurement discipline rather than delivery discipline.
**Follow-up trap:** *"Can a project have great outputs and zero outcome?"* â€” constantly, and it's the most common failure in big companies: polished features nobody uses. The defense is defining the outcome and its kill-threshold before writing code, so a shipped-but-inert feature triggers a decision instead of a shrug.

### Q6 â€” When is it right to push back on a customer request that sales has already promised?
**Testing:** spine plus diplomacy â€” the actual hard case.
**Answer:** First establish what problem the customer is really hiring the feature to solve â€” requests arrive as solutions. If a materially cheaper path solves the same job, I present both costs to sales and let them renegotiate with options rather than a refusal. I only dig in when the promise creates a structural cost (unmaintainable one-off architecture, unit economics that lose money on every use) â€” then I put the lifetime numbers side by side in writing and escalate with data.
**Follow-up trap:** *"What if the deal is strategically important despite bad economics?"* â€” then it's a pricing problem, not a product problem: take the custom work but price it as professional services or negotiate reference rights, making the loss deliberate and capped rather than accidental and recurring.

### Q7 â€” How would you introduce product thinking to a team of strong engineers who've never done it?
**Testing:** leadership-through-influence, not authority.
**Answer:** Start with one visible artifact, not training sessions: rewrite one epic template so no ticket enters sprint without a baseline number and a success threshold, then run one retro comparing outcomes of tickets that had them versus ones that didn't. Engineers adopt measurement habits faster than process mandates, especially when the first example shows a feature that "succeeded" on delivery but moved nothing.
**Follow-up trap:** *"What resistance do you expect?"* â€” "that's PM's job." My answer: it becomes your job because you hold information neither PM nor user has â€” what's cheap to build and cheap to measure â€” and teams where engineers bring that information ship higher-value work and get promoted for it.

### Q8 â€” Your team's feature shipped on time and adoption is fine, but the target metric didn't move. What happened?
**Testing:** causal reasoning under ambiguity.
**Answer:** Three usual suspects: adoption without behavior change (people opened it, used it once, reverted â€” check depth-of-use, not activation); the outcome metric is dominated by other drivers (segment the data â€” maybe the affected cohort moved 20% but they're 4% of the base); or the original theory linking feature to outcome was wrong. Diagnose in that order with cohort cuts before theorizing.
**Follow-up trap:** *"Should you roll it back?"* â€” depends on maintenance weight: a zero-cost feature that helps a small cohort can stay; anything consuming ongoing run-cost (especially AI inference) needs its cost re-priced against the smaller-than-hoped benefit, and usually that arithmetic says simplify or remove.

### Q9 â€” How do you translate a latency improvement into business value?
**Testing:** whether the engineer can speak CFO on a purely technical delta.
**Answer:** Through a measured elasticity, not folklore: e-commerce studies commonly cited put conversion lift around 1% per 100ms saved (Amazon's famous 100ms â‰ˆ 1% figure dates to 2006-2012 era analyses; Walmart reported ~2% per second). I'd instrument my own funnel to fit the coefficient on our data, then multiply: p95 cut of 400ms on a checkout flow doing $40M/yr at a conservative 0.5% per 100ms â‰ˆ $800K/yr â€” again banded and labeled.
**Follow-up trap:** *"Where do those elasticities break?"* â€” they're nonlinear and context-specific: gains flatten once pages feel instant (under ~100ms nothing is perceptible), and they differ wildly between browsing (tolerant) and checkout (intolerant) flows. Importing another company's coefficient without fitting your own is how a deck gets laughed out of a review.

### Q10 â€” When should engineering say no to an outcome-driven frame?
**Testing:** judgment about the framework's limits â€” traps candidates who over-applied earlier answers.
**Answer:** Three cases: constraint work (security, compliance, SRE error budgets) argues in risk terms; exploratory spikes argue in bounded-cost/binary-answer terms; and platform migrations argue in avoided-future-cost terms (a 30% ops-burden reduction priced against migration weeks). Forcing growth-metric framing onto these produces theater â€” fake numbers finance ignores â€” which is worse than honestly labeling the work type.
**Follow-up trap:** *"But leadership speaks growth metrics â€” won't risk framing lose the budget fight?"* â€” leadership also speaks risk when translated: expected loss Ã— probability, audit exposure, incident cost history. Every org has an outage invoice; anchoring reliability asks to the last one is often more persuasive than any engagement chart.

### Q11 â€” What makes a "why now" argument credible rather than hype?
**Testing:** discrimination between forcing functions and fashion.
**Answer:** A credible why-now names a changed variable with a date attached: a capability crossing a threshold (inference cost down ~10x in two years making per-request economics viable), a regulation with an effective date, a competitor shipment resetting expectations, or internal scale crossing the point where the old approach breaks. Hype versions cite the technology existing â€” technologies exist for years before they're actionable.
**Follow-up trap:** *"Give me a why-now that turned out false."* â€” plenty of 2023-era AI features assumed token prices and quality curves that didn't materialize on schedule; features whose business case needed the 2024 price curve to hold were stranded when it didn't. The lesson: state the why-now as a testable prediction with a checkpoint, not a mood.

### Q12 â€” You have one engineering quarter and three candidate projects. Walk through choosing.
**Testing:** synthesis of the whole module under time pressure.
**Answer:** One page per project: problem statement, outcome with baseline, three solution candidates, cheapest path to evidence, kill condition, and value-per-week arithmetic. Then compare on two axes â€” expected annualized value band vs. weeks-to-first-evidence â€” and pick the one whose cheapest probe either returns outsized information or outsized value. Announce the kill conditions publicly at kickoff.
**Follow-up trap:** *"All three have identical value bands â€” now what?"* â€” then decide on optionality and reversibility: prefer the project whose failure leaves reusable infrastructure and whose success doesn't lock the roadmap; when value ties, portfolio logic (one safe incremental, one bold bet) beats single-pick maximization.

---

## Red flags

- Discussing architecture before anyone can state the outcome metric and its baseline.
- "Outcomes" written as deliverables ("ship X by Q3") â€” output theater.
- A single solution candidate evaluated in isolation, with no cheaper alternative priced.
- Business-value claims with point estimates, no range, and no weakest-link label.
- Problem statements containing adjectives ("seamless," "delightful") instead of observable behavior.
- No kill condition recorded before kickoff â€” the project can't lose, so it can't learn.
- Guardrail thresholds invented after results arrived.

## Cheat card

```
CHAIN         problem -> outcome -> solution; argue UP the chain, build DOWN it
PROBLEM       who (sized) x pain (observable) x frequency x cost x WHY NOW
OUTCOME       user behavior, baseline known, magnitude + timeframe + guardrails
SOLUTION      >=3 candidates, priced (eng-wks, run-cost, time-to-evidence),
              pick by value/week; watch hammer-seeking-nails
$ TRANSLATION delta -> behavior -> retention/revenue chain; label each link
              measured / modeled / assumed; lead with the BAND
AI FEATURE    COGS = reqs/mo x tokens/req /1e6 x $/Mtok x 12 -> breakeven first
KILL RULE     write the cancel-condition BEFORE building; pre-registration
FRAMES        growth work = outcomes; constraints (sec/compliance/SRE) = risk;
              exploration = bounded cost, binary answer
POLITICS      present arithmetic, let the room conclude; veto via pre-written
              guardrail thresholds, never taste
```

## Sources

- Marty Cagan, *Inspired: How to Create Tech Products Customers Love* (2nd ed., Wiley, 2017); companion essays at https://www.svpg.com/articles/ â€” accessed 2026-08-23
- Josh Seiden, *Outcomes Over Output* (Sense & Respond Press, 2019), https://www.joshseiden.com/ â€” accessed 2026-08-23
- Teresa Torres, *Continuous Discovery Habits* (Product Talk LLC, 2021), https://www.producttalk.org/ â€” accessed 2026-08-23
- Colin Bryar & Bill Carr, *Working Backwards* (St. Martin's Press, 2021); method overview https://www.productplan.com/glossary/working-backwards/ â€” accessed 2026-08-23
- Eric Ries, *The Lean Startup* (Crown Business, 2011) â€” accessed 2026-08-23
- Amazon 100ms/conversion lore and Walmart speed findings surveyed in "Why Performance Matters," https://web.dev/articles/why-performance-matters â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

