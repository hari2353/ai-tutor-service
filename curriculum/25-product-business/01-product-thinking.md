# Product Thinking for Engineers: Problem → Outcome → Solution

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-08-08
> **Module id:** `T25-product-thinking` · **Tags:** product, critical

## The 30-second version

Every request that lands on an engineer's desk arrives pre-compressed into a solution — "add a cache," "build a Slack bot," "put a chatbot on the pricing page" — and the compression throws away the information you need to do the job well: the problem it was meant to solve and the outcome that would prove it worked. Product thinking is the discipline of decompressing the request before you build anything: what is the user actually stuck on (problem), what measurable change in their behavior or your business would mean that's fixed (outcome), and only then, what's the cheapest thing that produces that change (solution). Engineers jump straight to solution because solutions are the part of the job that feels like the job — code, architecture, a ticket you can close — while "what outcome are we actually chasing" feels like someone else's homework. The senior move is to make it your homework anyway: reframe every feature request as an outcome before you estimate it, because the estimate for the stated solution and the estimate for the real problem are frequently ten times apart.

## Why this gets asked

The interviewer has shipped a solution that satisfied the ticket and did nothing for the metric, and has watched a team spend two quarters on a "must-have" feature that a five-minute customer interview would have killed. They are not testing whether you can build things — your resume already proves that. They are testing whether you will spend the first hour of a request pushing back on its framing instead of the first hour writing code, because the engineers who don't do this generate technically excellent, strategically useless work, and at staff/principal level that failure mode is far more expensive than a bug.

---

## Lineage: past → present → future

**What came before.** Waterfall-era software development took requirements as given: a business analyst wrote a spec, engineering built to the spec, and "is this the right thing to build" was assumed to have been answered upstream, by someone else, before the document reached you. The pain that killed this was well documented by the 1990s — the Standish Group's CHAOS reports tracked decades of projects that shipped on spec and still failed, because the spec encoded someone's guess about a solution rather than a validated problem. Agile's response (the 2001 Manifesto, then Scrum and XP through the 2000s) fixed the *delivery* cadence — shorter loops, working software over documentation — but largely left the *framing* problem alone: a two-week sprint can ship the wrong outcome just as efficiently as a two-year waterfall project can. Marty Cagan's writing at SVPG (culminating in *Inspired*, 2008, revised 2017) and the "build trap" language popularized by Melissa Perri (*Escaping the Build Trap*, 2018) named the specific failure mode this module addresses: teams that are fully agile in process and still purely feature-factory in substance, taking a roadmap of solutions from stakeholders and executing it without ever validating the problem underneath.

**Where it stands now.** The mainstream product-org consensus (Cagan's "empowered teams," Torres's continuous discovery, the broader outcome-over-output movement) holds that teams should own problems and outcomes, not features, and that engineers are expected participants in that framing, not just downstream executors of a PM's decision. In practice this is unevenly deployed: well-run product orgs (the ones engineers describe wanting to work for) run discovery continuously and route requests through an opportunity-solution structure before committing engineering time; the median org still runs a roadmap of pre-decided features with a thin discovery veneer, because writing "reduce time-to-first-value for new sellers" on a roadmap slide is less legible to executives than "ship AI onboarding assistant." The live disagreement is less about the theory — almost nobody will argue on record that shipping features nobody asked for validated is good practice — and more about who is allowed to push back on a solution-shaped request from a VP, and whether an IC engineer has standing to do it without a PM as cover. At companies that take staff+ engineering seriously (the level this curriculum targets), the expectation is explicit: a Staff or Principal engineer is expected to reframe a request upward, not just implement it faster.

**Where it's heading.** Two directions, different confidence levels. First — high confidence, already underway — AI-assisted discovery (LLM-summarized support tickets, session replay clustering, synthetic user interviews) is lowering the cost of finding the *real* problem, which removes the historical excuse ("we don't have time to talk to users") for skipping straight to solution; expect discovery rigor to become cheaper to demand, not optional to skip. Second — moderate confidence — the "engineers should own outcomes" expectation is spreading down-level faster than most orgs' actual decision rights have caught up, meaning more engineers will be asked "what problem does this solve" in interviews and performance reviews well before their org actually gives them authority to say no to a solution-shaped mandate from above; that gap between stated expectation and real authority is itself something a principal-level answer should be able to name.

---

## Mental model

```
REQUEST AS RECEIVED               DECOMPRESSED                      WHAT YOU ACTUALLY BUILD
"Add a chatbot to the             PROBLEM: users abandon the        Could be a chatbot. Could
 pricing page"          ────▶      pricing page because they        also be: clearer plan
                                    can't tell which plan fits        names, an inline
                                    them, and support tickets         comparison table, one
                                    about plan selection are          fewer plan tier, or a
                                    18% of pre-sales volume           "recommend a plan" quiz
                                                                      that's 3 days of work
                                   OUTCOME: cut pre-sales
                                    "which plan" tickets by 50%,
                                    lift pricing→checkout
                                    conversion by X%
```

The compression is lossy in one direction only: a solution implies *a* problem and *an* outcome (usually not stated explicitly), but you cannot reconstruct which problem or outcome from the solution alone. "Add a chatbot" is consistent with a dozen different underlying problems — confusing pricing copy, too many tiers, a support team that's slow, a sales-assist gap for enterprise buyers — each of which has a different, often much cheaper, correct solution. The engineer's job before estimating is to walk back up the arrow: solution → outcome → problem, confirm the problem is real and worth solving, confirm the outcome is the right one to chase, and only then decide whether the original solution is still the best way to get there.

---

## How it actually works

### The three-question reframe

When a request arrives already shaped as a solution, ask, in order:

1. **"What problem is this solving?"** — not rhetorically; get a specific, falsifiable answer. "Users are confused" is not falsifiable. "18% of pre-sales support tickets are about plan selection, and pricing-page bounce rate is 34% above the site average" is.
2. **"How would we know it worked?"** — force a metric or an observable behavior change, before any design work starts. If nobody can answer this, the request is not yet a problem statement, it's a hunch, and hunches deserve a spike or a small experiment, not a quarter of roadmap.
3. **"Is the proposed solution the cheapest way to move that metric?"** — only now do you evaluate the original ask. Sometimes the chatbot really is the right call. Often a $500, three-day fix (rewriting plan names, adding a comparison table) gets 70% of the outcome the chatbot was pitched to deliver, and you learn this only by asking questions 1 and 2 first.

This is not a one-time gate — it's the question you re-ask any time scope grows. A request that started as "add a chatbot" and became "add a chatbot with proactive outbound messages and a CRM integration" needs the reframe run again on the new scope, because scope creep is usually solution creep: someone added more solution without re-checking it against the same problem and outcome.

### Why engineers jump straight to solution

Four real, non-flattering reasons, worth naming honestly because pretending it's purely a discipline gap misses the incentive structure:

- **Solutions are legible work.** "I reframed the requirements and killed 60% of the proposed scope" does not show up cleanly in a sprint burndown or a promo packet the way "shipped feature X" does, even when the reframe was the higher-value contribution. Until you've built career capital, skipping to solution is the path of least resistance to visible output.
- **Asking "what problem" can look like resistance.** Especially junior-to-mid engineers worry that questioning a stakeholder's request reads as not being a team player, or as trying to get out of work. Senior engineers who do this well frame it as *derisking the stakeholder's own bet*, not obstruction — "help me make sure this gets you the number you need" lands very differently from "why do we need this."
- **Discovery is uncertain and estimation is comfortable.** Engineers are trained to produce confident estimates. "I don't know the problem well enough to size this yet" is an uncomfortable thing to say in a planning meeting, so the path of least resistance is to size the stated solution and move on.
- **Nobody explicitly owns the problem-outcome layer.** In orgs without strong PM partnership, or where the PM themselves is operating in solution-mode (common — PMs inherit solution-shaped mandates from their own leadership just like engineers do), there may genuinely be no one in the room whose job it is to ask. That's exactly the gap a senior IC is expected to fill, not defer past.

### Reframing a feature request into an outcome, mechanically

Take the request at face value, then run it through four moves:

1. **Name the actor and the moment.** Who, doing what, when does the friction happen? "Sales reps, mid-demo, when a prospect asks about SSO support" is specific enough to design against; "users want better documentation" is not.
2. **Quantify the current state.** Pull whatever number already exists — ticket volume, funnel drop-off, time-on-task, churn reason codes. If no number exists, that's itself information: you're being asked to solve a problem nobody has measured, which means the estimate of value is someone's gut feeling, and you should say so out loud before committing months of engineering to it.
3. **State the target state as a number, not an adjective.** "Better" is not a target state. "Reduce median time-to-first-successful-query in the RAG onboarding flow from 6 minutes to under 90 seconds" is.
4. **Write the solution back down, explicitly marked as one option among several.** "Proposed: an inline chatbot. Alternatives considered: clearer copy, a guided setup wizard, pre-filled defaults based on plan tier." This single sentence — writing down that alternatives exist — is usually enough to trigger a five-minute conversation that either confirms the chatbot or replaces it with something cheaper.

Worked example, in the shape you'd actually write it in a design doc or a Slack thread:

> **As received:** "Marketing wants an AI chatbot on the pricing page, EOQ."
> **Problem:** Pricing-page visitors who don't self-select a plan within 90 seconds convert at 4%; those who do convert at 22%. Support gets ~40 "which plan is right for me" tickets/week pre-sale, each one taking a rep off a live queue.
> **Outcome:** Cut the self-select failure rate (currently ~61% of pricing-page visitors) in half within one quarter; cut pre-sales "which plan" ticket volume by 50%.
> **Options considered:** (a) chatbot — 6-8 weeks, ongoing eval/monitoring cost, uncertain accuracy on plan-selection questions; (b) a 3-question "recommend my plan" quiz that maps answers to a plan via a decision table — 3-4 days, fully deterministic, zero hallucination risk; (c) rewrite plan-tier copy and add a comparison table — 2 days.
> **Recommendation:** ship (c) first as a one-week bet, measure the self-select failure rate, and only build (a) or (b) if (c) doesn't move it enough — a static-copy fix is testable in days and might close most of the gap for near-zero cost.

That memo is the actual deliverable of product thinking. It costs an afternoon. Skipping it costs 6-8 weeks of engineering time on a bet nobody sized against the cheaper alternative.

---

## Build it from scratch

There's no code artifact for this module — the "build it from scratch" here is the reframe memo itself, and the muscle is doing it under time pressure, not with unlimited discovery time. A useful practice drill: take the last five feature requests you personally implemented without pushback, and write the four-part reframe (actor/moment, current-state number, target-state number, solution options) for each, after the fact. If you can't fill in the current-state number for a shipped feature, that's a real, specific gap — it means you (or your team) can't tell today whether that feature is working, which is the same failure mode this module is trying to prevent, just discovered late.

```text
# untested sketch — a lightweight reframe template you can paste into any ticket
## Reframe: <ticket title>
Actor + moment:          <who, doing what, when the friction occurs>
Current state (number):  <the metric today, or "not measured" — say so explicitly>
Target state (number):   <the number that would mean this is solved>
Requested solution:      <what was asked for>
Alternatives considered: <at least one cheaper option, even if you reject it>
Recommendation:          <what you're building and why, in one sentence>
```

---

## How it's done in production

In organizations that do this well, the reframe isn't a personal habit an individual engineer performs quietly — it's structural: a PRD or one-pager template that has a required "problem" and "success metric" field before a "solution" field can be filled in, and a review gate (design review, roadmap review) that rejects documents where the problem field is a restatement of the solution ("the problem is we don't have a chatbot").

| Symptom | Cause | Fix |
|---|---|---|
| A shipped feature has no metric anyone checks post-launch | Outcome was never defined before build started, so there's nothing to check against | Require a named metric and a dashboard link in the doc before code review starts, not after launch |
| Stakeholder is upset an alternative was proposed | Request arrived pre-decided at their level too — they were handed a solution by their own leadership and have no room to negotiate it | Reframe the conversation as de-risking their commitment ("help me make sure this hits your number"), and if they still can't move, build the requested solution but write down the predicted outcome so the miss is visible later |
| Team ships the "obvious" fix and the metric doesn't move | The stated problem was a symptom, not the actual friction — no one validated it with real usage data or user contact before building | Spend a day on log/ticket analysis or three user conversations before committing engineering weeks, especially when the fix is expensive |
| Engineers treat "why do we need this" as insubordination | No shared team norm that this question is expected, so it lands as personal pushback | Normalize the reframe as a standing step in planning (a template field), not a judgment call an individual has to justify each time |

---

## Tradeoffs & when NOT to use it

- **Don't run a full discovery cycle on a two-day fix.** If the requested solution is cheap, reversible, and low-risk, the cost of a rigorous reframe can exceed the cost of just building it and observing. Reserve the full reframe for anything that's multi-week, hard to reverse, or where you have a real, cheaper alternative in mind.
- **Don't use "what problem does this solve" as a stalling tactic.** If you ask the question and get a good answer, build the thing. The failure mode isn't "engineers should always push back" — it's "engineers should never skip the question." Asking and then building the original solution is a completely legitimate outcome.
- **Don't demand a metric that doesn't exist and can't be instrumented cheaply.** Sometimes the honest answer is "we can't measure this well, we're making a bet" — that's a valid thing to ship on, as long as it's stated as a bet and not dressed up as data-backed certainty.
- **Regulatory, compliance, and contractual asks are usually not up for reframing.** "SOC 2 requires audit logging on this endpoint" doesn't need a problem/outcome debate — the problem and outcome are externally fixed. Spend the pushback budget where it has leverage.
- **Political capital is finite.** Reframing every single request from every stakeholder burns trust fast. Save it for requests that are expensive, that you're genuinely unsure will work, or where you can see a materially cheaper path — not for everything that crosses your desk.

---

## Interview questions

### Q1 — A stakeholder asks you to "add a recommendation engine" to the product. Walk me through your first day.
**Testing:** whether your instinct is to start estimating or start asking.
**Answer:** First conversation is with the requester, not with a design doc: what's the actor and moment (who's missing what, when), what number today shows this is a real problem (browse-to-purchase rate, session depth, repeat-visit rate), and what number would prove a recommendation engine fixed it. Only after that do you evaluate whether a recommendation engine — versus, say, better category navigation, or surfacing "recently viewed" — is the cheapest path to that number.
**Follow-up trap:** *"What if they say 'just build it, we don't have time for discovery'?"* — build the smallest version that lets you observe the target metric fastest (e.g., a simple co-purchase-based "customers also bought" rail before a full ML recsys), and write down the predicted outcome before shipping so there's something to check the bet against later. Refusing to build anything without discovery is its own failure mode.

### Q2 — Give an example from your own work where you reframed a feature request and it changed what got built.
**Testing:** real experience, not theory — specifics or it didn't happen.
**Answer:** (Candidate-specific — the interviewer wants a concrete before/after: what was asked, what you found when you dug into the problem, what shipped instead, and what the measured result was.) The structure that reads as credible: state the original ask verbatim, state the number you found that reframed it, state what you built, state the actual metric movement — including if it was smaller than hoped.
**Follow-up trap:** *"What would you have done if the data had supported the original request?"* — say you'd have built it, and that the value of the reframe wasn't "prove them wrong," it was "confirm before spending six weeks." A candidate who only tells stories where they were right and the stakeholder was wrong is presenting a curated narrative, not a repeatable process.

### Q3 — Why do engineers jump straight to solutions, and why is that specifically a problem at the senior/staff level?
**Answer:** Solutions are legible, estimable, closeable work; asking "what problem" is uncertain and can read as resistance; and in weak PM partnerships nobody explicitly owns the outcome layer. It's specifically a staff+ problem because a staff engineer's technical decisions compound — architecture choices made against the wrong outcome are expensive to unwind, and a staff engineer is expected to catch a misframed problem before a team spends a quarter on it, not after.
**Follow-up trap:** *"Isn't that the PM's job?"* — it's the PM's job too, but staff+ engineers are expected to be a second line of defense, especially on technical framing the PM may not have the depth to interrogate (e.g., "is this actually an ML problem or a data-quality problem") — deferring entirely to the PM on problem framing is under-scoping the staff role.

### Q4 — How do you reframe a request when there's genuinely no usable data to quantify the current state?
**Answer:** Say so explicitly rather than inventing a number — "we don't have this instrumented" is itself a finding. Then decide: is the bet cheap enough to make anyway (ship small, instrument it, observe), or expensive enough that you should spend a day getting a proxy signal first (support ticket tagging, a handful of user conversations, a log query)? The failure mode isn't lacking data, it's presenting a guess as if it were data.
**Follow-up trap:** *"Leadership wants a number for the business case regardless."* — give a range with your confidence stated ("likely $50-150K annual impact, low confidence, based on X proxy"), not a single fabricated point estimate — a stated range with its basis is defensible under questioning; a confident-sounding made-up number is not, and gets exposed the first time someone asks "where did that come from."

### Q5 — Your VP hands you a fully-specified solution and says "just build this." How do you respond?
**Answer:** Build it — but not silently. Write down, in one paragraph, what problem and outcome you believe this is meant to solve, and share it back ("confirming my understanding — this is meant to move X, is that right?"). This costs the VP thirty seconds to confirm or correct, creates a record of the intended outcome for later, and doesn't block delivery.
**Follow-up trap:** *"What if your understanding is wrong and they correct you?"* — that's the entire point of doing it — you just caught a misunderstanding for the cost of one Slack message instead of discovering it after delivery. A candidate who treats being corrected as a bad outcome doesn't understand why the technique works.

### Q6 — What's the difference between a problem statement and a solution wearing a problem statement's clothes?
**Answer:** A real problem statement names an actor, a moment, and an observable friction, independent of any fix — "sales reps can't answer SSO questions live, mid-demo." A disguised solution restates the fix as if it were the problem — "the problem is we don't have a chatbot" or "the problem is our docs aren't AI-searchable" — both already presuppose the answer and foreclose alternatives before they're considered.
**Follow-up trap:** *"How do you catch this in a document you're reviewing?"* — check whether the "problem" section would still make sense if you deleted every noun related to the proposed solution. If "the problem is we don't have a chatbot" becomes meaningless once you remove "chatbot," it wasn't a problem statement.

### Q7 — Estimate the cost of skipping the problem/outcome reframe on a project you're familiar with.
**Testing:** ability to translate this discipline into real dollar/time terms, not just process language.
**Answer:** Concrete framing: N engineer-weeks at fully-loaded cost, multiplied by the probability the shipped solution doesn't move the real metric (often 30-50% for AI features per industry failure-rate data — cite it if you have it), versus the cost of a reframe (a few hours to a few days). Even a modest failure-rate discount makes the reframe cost-positive by a wide margin on anything multi-week.
**Follow-up trap:** *"Doesn't that logic argue for reframing everything, always?"* — no, because the reframe itself has a cost too (opportunity cost of the requester's and your time, delay). The right rule is proportional: reframe scales with (cost of being wrong) × (probability of being wrong), and for a two-day reversible fix that product is usually smaller than the reframe's own cost.

### Q8 — How do you tell the difference between healthy pushback on a request and just being difficult?
**Answer:** Healthy pushback ends in a decision within one conversation and is framed around the requester's own success ("help me make sure this hits your number"), not around your preferences. Being difficult repeats the same objection after being overruled, or frames the pushback around your own workload/interest rather than the outcome. If you've asked the three questions, gotten answers, and still disagree, the senior move is to say so once, clearly, get overruled if that's the call, and build it well — not to relitigate it in every standup.
**Follow-up trap:** *"What if you're overruled and you still think it's wrong?"* — build it with full competence, and write down your prediction beforehand so there's a clean signal later regardless of who was right. Undermining a decision you lost, even subtly, is a bigger trust cost than losing the argument.

### Q9 — Walk through reframing "we need better observability" into an outcome.
**Answer:** "Better observability" is itself solution-shaped — it presupposes tooling is the gap. Push one level further: what incident, in the last quarter, took longer to diagnose than it should have, and what specifically was missing when you needed it (a trace across services, a metric that wasn't emitted, a log that got sampled away)? The outcome is something like "cut mean time-to-detect for cross-service latency regressions from 45 minutes to under 10," and the solution might be distributed tracing, might be three specific new alerts, might be fixing a sampling config — you don't know until you've named the actual incident pattern.
**Follow-up trap:** *"Isn't infrastructure work inherently hard to tie to a business metric?"* — it's harder, not impossible; tie it to an internal outcome (MTTD, MTTR, on-call pages/week) rather than forcing it to a revenue number — internal engineering-quality metrics are legitimate outcomes, they just need to be as specific as a customer-facing one.

### Q10 — How do you scale this reframe habit across a team of twenty engineers without becoming a bottleneck yourself?
**Testing:** staff/principal-level thinking — can you turn a personal practice into a team norm.
**Answer:** Bake the four fields (actor/moment, current state, target state, solution options) into the doc template every request has to pass through, so the question gets asked by the format itself, not by you personally reviewing every ticket. Model it visibly on a few high-stakes requests early so the team sees what a good answer looks like, then let peer review (not you) enforce it going forward.
**Follow-up trap:** *"What if the template becomes a box-ticking exercise people fill in without thinking?"* — that happens, and the fix isn't more process, it's spot-checking: periodically pick a shipped feature and ask whether its stated outcome was actually measured post-launch. Teams that know the outcome will be checked write real ones; teams that know it won't, don't.

### Q11 — When is "just build the solution as asked, no reframe" actually the right call?
**Answer:** When the ask is cheap and reversible (a config change, a copy tweak, a two-day fix), when it's externally mandated (compliance, contractual, security), when the requester already has strong data behind it and can produce the problem/outcome on request, or when the relationship cost of pushing back exceeds the expected value of the reframe on this specific low-stakes item.
**Follow-up trap:** *"How do you avoid this becoming an excuse to skip discovery on things that actually need it?"* — set the threshold explicitly in terms of cost and reversibility before you're in the room being asked, not in the moment — e.g., "anything under a week and reversible, I build without a formal reframe; anything bigger gets the three questions" — a pre-committed rule resists being talked out of it case by case.

---

## Red flags that fail you

- Starting every answer with "I would build..." instead of "I would first ask..."
- Treating "what problem does this solve" as a rhetorical flourish rather than something you'd get a real, specific answer to before writing an estimate.
- Claiming you always push back on every request — reads as inexperienced or performative, not senior.
- No concrete example when asked for one — theory without a story is a tell.
- Confusing "the problem is we lack feature X" (a disguised solution) with an actual problem statement.
- Framing pushback around your own preferences ("I don't want to build a chatbot") instead of the requester's outcome.

---

## Cheat card

```
REFRAME ORDER      solution (as received) -> problem -> outcome -> re-evaluate solution
THREE QUESTIONS     1) what problem does this solve (specific, falsifiable)
                    2) how would we know it worked (a number or observable behavior)
                    3) is the proposed solution the cheapest path to that number
WHY ENGINEERS SKIP  solutions = legible work; asking looks like resistance;
                    estimating feels safer than admitting uncertainty;
                    often nobody explicitly owns the problem/outcome layer
DISGUISED PROBLEM   "the problem is we don't have X" -- delete X, if the sentence
                    breaks, it wasn't a problem statement, it was a solution
MEMO SHAPE          actor+moment / current-state number / target-state number /
                    requested solution / >=1 alternative / recommendation (1 line)
WHEN TO SKIP IT     cheap + reversible; externally mandated (compliance/contract);
                    requester already has the data; low relationship-cost item
SCALE IT            bake the 4 fields into the doc template so the format asks
                    the question, not you personally, every single time
COST MATH           reframe cost (hours-days) vs (eng-weeks x P(wrong outcome))
                    -- reframe wins on anything multi-week and not fully certain
```

## Sources

- [Product Sense Interview Prep (2026 Guide) — Exponent](https://www.tryexponent.com/blog/product-sense-interview) — accessed 2026-08-08
- [Product Sense Interview Questions & Framework (2026 Guide) — Aakash Gupta](https://www.news.aakashg.com/p/master-the-product-sense-interview) — accessed 2026-08-08
- [The Amazon Working Backwards PR/FAQ Process](https://workingbackwards.com/concepts/working-backwards-pr-faq-process/) — accessed 2026-08-08
- Marty Cagan, *Inspired: How to Create Tech Products Customers Love* (2008, rev. 2017) — SVPG
- Melissa Perri, *Escaping the Build Trap* (2018)

## Changelog
- 2026-08-08 — created
