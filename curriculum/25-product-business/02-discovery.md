# Discovery: Jobs To Be Done, User Interviews, Opportunity Solution Trees, Killing Your Own Idea Early

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** T25-product-thinking · **Updated:** 2026-08-08
> **Module id:** `T25-discovery` · **Tags:** product

## The 30-second version

Discovery is the set of cheap, fast techniques for finding out whether a problem is real and a solution direction is worth betting engineering time on, before you spend engineering time on it. Jobs To Be Done (JTBD) reframes "who is our user" into "what progress is someone trying to make, and what are they currently hiring — however clumsy — to make it," which surfaces competitors you'd never find by looking at your category (a spreadsheet, a coworker, doing nothing, are all "hired" alternatives to your product). User interviews are only useful if you ask about specific past behavior ("tell me about the last time you...") instead of hypotheticals or preferences, because people are unreliable narrators of their own future behavior and surprisingly reliable narrators of a specific remembered event. Teresa Torres's opportunity solution tree keeps a team honest by forcing every proposed solution to trace back through a named opportunity (an unmet need or pain point, evidenced by real interview data) to the outcome it's meant to move, so "let's build X" always has to answer "which opportunity does X address, and how do you know that opportunity is real." The hardest and rarest skill in this whole module is killing your own idea early — actively looking for the evidence that would prove your favorite solution wrong, before you've spent six weeks building it, because sunk cost makes that same evidence much harder to act on later.

## Why this gets asked

The interviewer has watched — or been part of — a team that built a fully-featured product nobody asked for, based on stakeholder conviction rather than user evidence, and shipped it to silence. They want to know if you have a repeatable, cheap way to catch that outcome before code gets written, and specifically whether you know how to run an interview that produces signal instead of politeness — most people who claim to "talk to users" are running interviews that only ever confirm what they already believed, because they're asking leading, hypothetical, or preference-based questions that let the interviewee be agreeable instead of honest.

---

## Lineage: past → present → future

**What came before.** Traditional market research — surveys, focus groups, A/B-tested feature preference polls — dominated product discovery through the 1990s and into the 2000s, and its failure mode is well documented: people are bad at predicting their own future behavior (stated preference diverges from revealed preference constantly), focus groups produce groupthink and defer to the most confident voice in the room, and surveys with leading questions return whatever answer confirms the question-writer's hypothesis. Clayton Christensen's Jobs To Be Done theory (developed through the 1990s-2000s, most widely popularized via the 2016 book *Competing Against Luck* with Bob Moesta) was a direct reaction to this: the famous "milkshake" study reframed a fast-food chain's stalled milkshake sales not as a product-attribute problem (thicker? more flavors?) but as a jobs problem — commuters were "hiring" the milkshake for a one-handed, slow-to-finish, boring-commute companion, a job a banana or a candy bar competed for far more than a competitor's milkshake did. Separately, the Lean Startup movement (Eric Ries, 2011, building on Steve Blank's customer development work) pushed "get out of the building" and build-measure-learn cycles as the antidote to building in isolation from real usage.

**Where it stands now.** Teresa Torres's continuous discovery framework (*Continuous Discovery Habits*, 2021, and ongoing work through Product Talk) is the closest thing to current industry consensus among well-run product orgs: weekly touchpoints with customers (not a one-off research phase), opportunity solution trees to keep discovery traceable to outcomes, and assumption testing before full builds. The live disagreement is about cadence and ownership: some orgs treat discovery as a dedicated research function's job (UX researchers run interviews, product/eng consume findings secondhand), others push it directly onto the PM and engineering leads doing the weekly touchpoints themselves — Torres's own position is strongly the latter, on the grounds that secondhand research findings lose the nuance and serendipity of being in the room. A second live disagreement, sharpened since 2024-2025: how much of discovery can be accelerated or partially automated with AI (LLM-clustered support ticket themes, synthetic user simulation, AI-assisted interview transcription and synthesis) without losing the signal that comes from a human noticing a surprising, off-script remark — practitioners broadly agree AI helps with volume and synthesis, and broadly agree it cannot yet replace the moment of actually listening to a real person describe a real struggle.

**Where it's heading.** High confidence: AI-assisted synthesis of existing qualitative data (support tickets, sales call transcripts, churn interviews) will keep lowering the cost of finding *candidate* opportunities, shifting scarce human interview time toward validating the most promising ones rather than fishing blind. Moderate confidence: "continuous" discovery cadences (weekly customer contact) will keep spreading from consumer/B2B SaaS orgs into more traditionally research-averse domains (enterprise, regulated industries) as the tooling for lightweight, low-overhead customer contact improves. More speculative: some teams are experimenting with LLM-simulated user interviews (synthetic personas trained on real transcript corpora, probed with the same story-based interview technique) as a cheap first pass to sharpen questions before spending real user time — early and contested; the risk of confirming a model's biases about users rather than discovering anything new is real and unresolved.

---

## Mental model

```
OPPORTUNITY SOLUTION TREE  (Torres)

                          OUTCOME
                 (business/product metric to move)
                             |
        ┌────────────────────┼────────────────────┐
        │                    │                     │
   OPPORTUNITY A         OPPORTUNITY B         OPPORTUNITY C
  (unmet need,          (unmet need,          (unmet need,
   evidenced by          evidenced by          evidenced by
   interview data)       interview data)       interview data)
        │                    │
   ┌────┼────┐          ┌────┼────┐
 SOLN  SOLN  SOLN      SOLN SOLN SOLN
  1     2     3          4    5    6
   │
 ASSUMPTION TESTS  (cheapest experiment that could kill this
                     solution before you fully build it)
```

Every branch has to trace upward. A solution not attached to a named, evidenced opportunity is a stakeholder's hunch wearing a roadmap item's clothes — this is the same disguised-solution pattern from the previous module, applied at the discovery layer instead of the individual-request layer.

---

## How it actually works

### Jobs To Be Done: the reframe and why it surfaces competitors you'd miss

The JTBD question is not "what does the user want" but "what progress is someone trying to make in a specific circumstance, and what are they currently hiring to make that progress." This reframe does two things a feature-request or persona-based approach doesn't:

- **It surfaces functional, social, and emotional dimensions together.** The famous milkshake job wasn't just functional (something to eat) — it was social/emotional too (something that wouldn't embarrass a parent buying breakfast for a kid, something that made a boring commute feel less boring). A feature request rarely captures all three; a job story does.
- **It surfaces non-obvious competitors.** If the job is "give me something to do with my hands and mouth during a 45-minute boring commute," a milkshake's real competition is a banana, a bagel, or the car radio — not other milkshakes. In software: if the job a project-management tool is hired for is "make me look organized and in-control to my manager during a status update," its real competition might be a well-formatted spreadsheet or a five-minute conversation, not another PM tool.

**Job story format** (an alternative to user-story format, deliberately built to avoid baking in a persona and a solution): *"When [situation], I want to [motivation], so I can [expected outcome]."* Compare to a typical user story — *"As a [persona], I want [feature], so that [benefit]"* — which already smuggles in a persona label and often a specific feature, both of which narrow the solution space prematurely. "When I'm mid-demo and a prospect asks about SSO, I want to answer confidently without breaking my flow, so I can keep the demo's momentum" is a job story; "As a sales rep, I want a chatbot, so that I can answer questions" already presupposes the chatbot.

### User interviews: the technique, and the specific failure modes that produce useless data

The single most consequential mistake in discovery interviewing is asking questions that let the interviewee answer with an opinion, a hypothetical, or a prediction about their own future behavior, instead of a specific memory of a real past event. Three failure patterns, all extremely common:

1. **Hypothetical/future questions** — "Would you use a feature that did X?" People say yes to be agreeable, or because they can imagine a world where it'd be useful, with zero cost to them for being wrong. This is the single most misleading question type in product research and it's also the most common one asked.
2. **Preference/opinion questions** — "What do you think about our pricing page?" produces an opinion formed on the spot, shaped heavily by how the question is framed and by social desirability bias, not a description of real behavior.
3. **Leading questions** — "Don't you find it frustrating when...?" hands the interviewee the answer.

The fix — story-based interviewing, per Teresa Torres's guidance — is to ask about a **specific, recent, real event**: "Tell me about the last time you tried to figure out which pricing plan was right for you. Walk me through what happened." This produces a concrete narrative you can mine for the actual friction points, the actual workarounds, the actual emotional beats — data about what *did* happen, not a guess about what *might*.

**Interview mechanics that separate signal from noise:**

- **One story per interview segment, mined deeply**, rather than a checklist of ten shallow questions. "What happened right before that? What did you do next? What were you thinking at that moment?" — depth beats breadth.
- **Follow the energy.** When someone's tone shifts, or they say "actually, that reminds me," that's usually where the real signal is; a rigid script will walk right past it.
- **Recruit for recency and relevance, not convenience.** An interview with someone who did the behavior last week beats one with someone who "generally" does it, because memory of a specific recent event is far more reliable than a summarized habit.
- **Interview close to the moment of decision when possible.** Post-purchase or post-churn interviews conducted within days are dramatically more accurate than ones conducted months later, when the interviewee has rationalized or forgotten the actual sequence.

### Opportunity solution trees: keeping solutions traceable

The tree (Torres, *Continuous Discovery Habits*) has three levels below the outcome:

- **Opportunities** are unmet needs, pain points, or desires, stated from the customer's perspective, evidenced by interview data — not invented in a brainstorm. "Prospects can't self-assess whether they need SSO before talking to sales" is an opportunity if you have interview or ticket evidence for it; if it's a guess, it doesn't belong on the tree yet, or it belongs with an explicit "unvalidated" tag.
- **Solutions** are the ideas that might address an opportunity — plural, deliberately, because generating three to five candidate solutions per opportunity before picking one is the entire point: a team that jumps to the first solution never discovers the cheaper fourth option.
- **Assumption tests** are the smallest, cheapest experiments that could kill a solution before a full build — a fake-door test, a concierge/manual version, a landing page, a five-minute prototype walkthrough with three users. The tree's discipline is: no solution graduates to full build without at least one assumption test that could have falsified it and didn't.

The tree's real value in a staff/principal-level conversation is as a **communication artifact**: it makes visible, in one picture, why the team is building X instead of Y — X traces to an opportunity with real evidence and Z (a stakeholder's pet idea) doesn't appear on the tree at all yet, which is a much stronger "no" than a verbal debate, because it's structural rather than personal.

### Killing your own idea early

This is the hardest discipline in the module, because it fights directly against incentives: you get promoted for shipping things, not for correctly killing them before you built them, and the emotional investment in an idea you've been pitching for weeks makes disconfirming evidence feel like a personal loss rather than useful information. The mechanical technique:

1. **Write down, before you build anything, what evidence would prove this idea wrong** — a specific, falsifiable prediction ("if fewer than 15% of the pilot cohort completes onboarding using this flow, the flow doesn't work"), not a vague hope.
2. **Run the cheapest experiment that could produce that evidence**, before the expensive build — a prototype, a manual/concierge version, a smoke test, a fake-door click-through.
3. **Actually look at the result before defending the idea.** The trap isn't failing to run the test, it's rationalizing a bad result after the fact ("the sample was too small," "they didn't understand the prototype") to protect the idea instead of updating on it.
4. **Have a pre-committed kill threshold**, decided before you see the data, exactly like a statistical test's alpha decided before running the experiment — deciding the bar for "kill this" after seeing the number is how motivated reasoning wins every time.

---

## Build it from scratch

There's no runnable code lab for this module; the artifact to practice building from scratch is the opportunity solution tree itself and a story-based interview script.

```text
# untested sketch — a minimal opportunity solution tree in plain text,
# the kind you'd actually sketch in a design doc or a Miro board

OUTCOME: Increase self-serve pricing-page -> checkout conversion by 15% this quarter

OPPORTUNITY 1: "Visitors can't tell which plan fits their team size"
  evidence: 40 pre-sales tickets/week tagged "which plan"; 61% pricing-page
            bounce without plan selection (GA funnel, last 90 days)
  candidate solutions:
    - inline plan comparison table                 [assumption test: fake-door click rate]
    - 3-question "recommend my plan" quiz           [assumption test: manual/concierge version
                                                       with 10 real visitors]
    - AI chatbot                                    [assumption test: Wizard-of-Oz test,
                                                       human answering as "the bot" for a week]

OPPORTUNITY 2: "Enterprise buyers can't find SSO/security info without contacting sales"
  evidence: 12 discovery-call transcripts mention searching for this and not finding it
  candidate solutions:
    - dedicated security/compliance page
    - inline SSO badge on pricing tiers

# a solution with no opportunity above it, e.g. "AI chatbot" pitched
# standalone by a stakeholder, does not get added to the tree until
# an opportunity is found and evidenced for it.
```

A minimal story-based interview script to pair with it:

```text
# untested sketch — story-based interview opener, avoid hypotheticals entirely
1. "Tell me about the last time you [did the behavior]. Walk me through what happened,
    start to finish."
2. "What were you trying to accomplish right before that?"
3. "What did you try first? What happened when you did that?"
4. "What were you thinking / feeling at that point?"
5. "What did you do next?"
6. (only if it comes up naturally) "Why did you choose that over [alternative]?"

NEVER ask: "Would you use...", "Do you think you'd...", "What do you want in..."
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Interview notes are full of opinions ("users think the pricing is confusing") with no specific incident behind them | Questions were hypothetical/preference-based, not story-based | Re-run with "tell me about the last time..." framing; if you can't cite a specific remembered event, the data point isn't usable |
| Roadmap items can't be traced to any evidence when questioned in review | No opportunity solution tree, or one exists but isn't maintained/consulted before prioritization | Require every roadmap item to show its opportunity and evidence before it's prioritized, not just before it's built |
| A shipped feature underperforms and the retro says "users told us they wanted this" | The team asked a hypothetical ("would you use X") and got a polite yes, mistaken for validated demand | Distinguish "expressed interest in a hypothetical" from "demonstrated behavior in an assumption test" as different evidence tiers, and don't greenlight a full build on the former alone |
| Team keeps defending a solution after two failed assumption tests | No pre-committed kill threshold; motivated reasoning post-hoc justifies each miss | Set the kill criterion in writing before running the test, and hold the team to it as a real gate, not a suggestion |
| Research findings get diluted by the time they reach engineering | Discovery is siloed to a research function; findings arrive as a slide deck summary, stripped of nuance | Rotate engineers/PMs into a portion of interviews directly (even 2-3 per quarter), per Torres's continuous-discovery guidance |

---

## Tradeoffs & when NOT to use it

- **Don't run full discovery on low-stakes, cheap, reversible changes.** A copy tweak or a config change doesn't need an opportunity solution tree; reserve the ceremony for bets that are expensive or hard to reverse.
- **JTBD framing can be over-applied to purely operational or compliance-driven work** — "what job is SOC 2 audit logging hired for" is a stretch that produces no useful insight; know when the frame doesn't fit.
- **Interviews are a qualitative signal, not a sample-size-backed quantitative one.** Five interviews telling a consistent story is real signal; five interviews used to justify a precise conversion-rate prediction is a category error — pair interviews with usage data and, eventually, an actual experiment (see the experimentation module) before betting big.
- **Story-based interviewing takes real skill and real time** — a rushed, poorly-run story interview produces worse data than a well-designed survey would for some questions (e.g., broad prevalence: "what % of our users have this problem" is a quant question, not an interview question). Use interviews for depth and mechanism, use analytics/surveys for prevalence.
- **Killing your own idea early has a real cost if taken to an extreme** — a team that kills every idea at the first ambiguous signal never ships anything bold. The discipline is a pre-committed, specific kill threshold, not maximal risk aversion.

---

## Interview questions

### Q1 — Explain Jobs To Be Done and why it's different from persona-based product thinking.
**Testing:** whether you understand JTBD as a reframe of competition, not just a research technique.
**Answer:** JTBD asks what progress someone is trying to make in a specific circumstance and what they currently "hire" to make it — including non-obvious substitutes outside your product category. Persona-based thinking segments by who the user is (demographics, role); JTBD segments by the circumstance and the progress sought, which is why the same person can "hire" completely different things for different jobs, and why a milkshake's real competitor turned out to be a banana, not another milkshake.
**Follow-up trap:** *"Give an example from software."* — a note-taking app's job during a meeting ("capture what's said without breaking eye contact") competes with a phone's voice memo and a colleague's shared notes, not just other note-taking apps; naming a concrete non-category competitor is what separates a real understanding from a memorized definition.

### Q2 — What's wrong with asking a user "would you use a feature that does X?"
**Answer:** It's a hypothetical about future behavior, and people are unreliable predictors of their own future actions — they answer to be agreeable, or because they can imagine a scenario where it'd help, with zero real cost for being wrong. It produces expressed interest, not evidence of a real, resolvable friction.
**Follow-up trap:** *"So how do you get at the same information reliably?"* — ask about the last specific time they faced the situation the feature would address ("tell me about the last time you tried to do X") and mine that real story for the actual friction, workaround, and emotional response — behavior described from memory is far more reliable than a prediction about the future.

### Q3 — Walk me through an opportunity solution tree and what problem it solves structurally.
**Answer:** Below a stated outcome, opportunities (evidenced unmet needs) branch off; below each opportunity, multiple candidate solutions branch off; below each solution, assumption tests validate or kill it before a full build. It solves the structural problem of solutions arriving pre-decided and untraceable — every item on the tree has to show its lineage back to real evidence, which turns "why are we building this" from a verbal argument into a visible, falsifiable structure.
**Follow-up trap:** *"A VP's pet idea isn't on the tree. What do you do?"* — don't refuse it outright; find or seek the opportunity it might address, add it with an "unvalidated" tag if there's no evidence yet, and propose the cheapest assumption test to validate it before a full build — the tree is a tool for structuring the conversation, not a weapon for blocking a stakeholder.

### Q4 — Describe a time you killed your own idea before it shipped. What told you to stop?
**Testing:** real experience with disconfirming your own hypothesis, not a hypothetical answer.
**Answer:** (Candidate-specific.) A credible answer names the pre-committed kill criterion decided before the test ran, the specific evidence that crossed it, and — critically — that the candidate acted on it rather than rationalizing around it.
**Follow-up trap:** *"What made it hard to accept the result?"* — sunk cost and the emotional investment of having pitched the idea; naming this honestly, rather than claiming it was easy, is what makes the answer credible instead of rehearsed.

### Q5 — How do you decide when qualitative interviews are enough evidence versus when you need a quantitative experiment?
**Answer:** Interviews are strong for mechanism and depth — why something happens, what the friction actually feels like — but weak for prevalence and magnitude — how many users have this problem, how big the effect would be. Use interviews to generate and sharpen a hypothesis, then use usage data, a survey, or an actual experiment to size it before committing significant engineering investment.
**Follow-up trap:** *"Five interviews all say the same thing — isn't that enough to ship?"* — consistent qualitative signal justifies building the cheapest testable version and instrumenting it, not skipping straight to a full build; five people agreeing is strong directional evidence, not a sample size that lets you predict a conversion-rate lift.

### Q6 — What's an assumption test, and give an example for a feature you might actually build.
**Answer:** The cheapest experiment that could falsify a proposed solution before you fully build it — a fake-door (a button that measures click-through with no feature behind it yet), a concierge/manual version (a human doing by hand what the feature would automate), a landing page, or a Wizard-of-Oz test (a human pretending to be the automated system, e.g. answering as "the AI chatbot" manually for a week to see if the demand and the answerable-question-rate are real).
**Follow-up trap:** *"What if the fake-door test shows high interest but the real build underperforms?"* — a fake door measures interest, not satisfaction with the actual experience; it's a necessary but not sufficient test — pair it with a lightweight real (even manual) version before fully building, especially for anything where the execution quality matters as much as the concept.

### Q7 — How do you run discovery on an enterprise/B2B product where you can't easily talk to end users?
**Answer:** Lean on channels that already have contact: sales call transcripts and win/loss interviews, support ticket themes, customer success check-ins, and champion/admin interviews at existing accounts — mine these for job stories and specific incidents the same way you would a direct interview, and negotiate a small number of direct customer conversations (even quarterly) through account teams rather than trying to run a self-serve-style research cadence.
**Follow-up trap:** *"Sales and CS have incentives that bias what they report — how do you correct for that?"* — go to primary transcripts and raw ticket text, not secondhand summaries, whenever possible; a CS rep's summary ("customers love this") is already filtered through their own incentive to look good, while the raw transcript often contains the actual friction underneath.

### Q8 — A stakeholder says "I talked to five customers and they all want this feature." How do you evaluate that claim?
**Answer:** Ask how the questions were framed — hypothetical/preference questions produce polite agreement, story-based questions produce real evidence. Ask whether the five were representative of the segment the outcome targets, or convenience-sampled (whoever was easy to reach, often the friendliest or most engaged customers, which biases toward "yes"). Ask if there's a specific remembered incident behind each "want," or just a stated preference.
**Follow-up trap:** *"The stakeholder gets defensive when you ask this. How do you keep the conversation productive?"* — frame it as strengthening their case, not doubting it ("let's make sure this survives scrutiny in the roadmap review — can we look at what was actually asked?"), and offer to help design the next round of validation rather than just critiquing the last one.

### Q9 — How does AI change discovery practice, and what does it not change?
**Answer:** It lowers the cost of synthesizing existing qualitative data at volume — clustering support tickets, summarizing hundreds of sales call transcripts, surfacing recurring themes a human would take weeks to find manually — which shifts scarce human interview time toward validating the most promising candidate opportunities rather than fishing blind. It doesn't replace the moment of a human noticing a surprising, off-script remark in a live conversation, and synthetic/simulated user interviews risk confirming a model's existing biases about users rather than discovering anything genuinely new.
**Follow-up trap:** *"Would you use an LLM-simulated persona to pre-test interview questions?"* — as a cheap way to sharpen question wording before spending real user time, plausibly yes; as a substitute for talking to real users, no — treat any output from a simulated persona as a hypothesis to validate, never as evidence itself.

### Q10 — You're a Principal engineer, not a PM. Why should you be doing any of this yourself instead of trusting product's discovery?
**Answer:** Because technical framing errors are often invisible to a PM without deep systems knowledge — "is this actually an ML problem or a data-quality problem," "is the latency the users complain about a UX issue or an infra issue" — and a staff/principal engineer who participates directly in a portion of discovery (even a handful of interviews or ticket reviews per quarter) catches those framing errors before architecture decisions get made against a wrong premise, which is far more expensive to unwind than a missed feature.
**Follow-up trap:** *"Doesn't that duplicate the PM's job and cause friction?"* — frame it as a targeted technical-diagnosis pass, not a parallel discovery track — you're not re-running the PM's user research, you're adding a technical lens to a subset of the same evidence, and sharing findings back collaboratively rather than unilaterally reprioritizing the roadmap.

### Q11 — What's the difference between an "opportunity" and a "solution" on the tree, and why does mixing them up cause real damage?
**Answer:** An opportunity is a customer-stated or evidenced unmet need, independent of any fix; a solution is one candidate way to address it. Mixing them up — writing "the opportunity is: we need an AI chatbot" — collapses the tree's whole point, because it forecloses the three-to-five alternative solutions a real opportunity would generate, and re-introduces the disguised-solution problem one layer up.
**Follow-up trap:** *"How do you catch this when reviewing someone else's tree?"* — apply the same test as spotting a disguised problem statement elsewhere: does the "opportunity" reference a specific technology or feature name? If so, it's a solution mislabeled, and you push it down a level and ask what unmet need it might actually be evidencing.

---

## Red flags that fail you

- Describing "talking to users" without being able to say what questions were actually asked.
- Treating a hypothetical "would you use X" answer as validated demand.
- Not being able to name a specific past incident when asked for interview evidence.
- Claiming to always kill weak ideas, with no story of the emotional/organizational difficulty of actually doing it.
- Conflating "the opportunity is we need feature X" — a disguised solution one level up the tree.
- No distinction between qualitative signal (mechanism, depth) and quantitative signal (prevalence, magnitude) when asked to justify a decision.

---

## Cheat card

```
JTBD             job = progress someone's trying to make in a circumstance;
                 competitors include non-category substitutes (spreadsheet, doing
                 nothing) -- milkshake's real rival was a banana, not another shake
JOB STORY        "When [situation], I want to [motivation], so I can [outcome]"
                 -- avoids baking in a persona or a solution, unlike user stories
INTERVIEW RULE   ask about ONE specific past event ("tell me about the last time..."),
                 never a hypothetical ("would you use...") or preference ("what do
                 you think of...") -- people are unreliable predictors of their own
                 future behavior, reliable narrators of a remembered event
OPPORTUNITY      evidenced unmet need, customer's language, NOT a solution or a
                 feature name -- if deleting the tech name breaks the sentence, it's
                 a solution mislabeled as an opportunity
SOLN TREE        outcome -> opportunities (evidenced) -> solutions (3-5 candidates
                 per opportunity) -> assumption tests -> full build
ASSUMPTION TEST  cheapest experiment that could KILL a solution before full build:
                 fake-door, concierge/manual version, landing page, Wizard-of-Oz
KILL YOUR OWN    write the falsifying evidence BEFORE testing, pre-commit the kill
IDEA EARLY       threshold, run the cheapest test, act on the result even when it hurts
QUAL vs QUANT    interviews = mechanism/depth (why, how); analytics/experiments =
                 prevalence/magnitude (how many, how much) -- don't ask interviews
                 to do quant's job
```

## Sources

- [Teresa Torres on how to interview customers — Lenny's Newsletter](https://www.lennysnewsletter.com/p/teresa-torres-on-how-to-interview) — accessed 2026-08-08
- [Ask Teresa: What Are the Best Customer Interview Questions? — Product Talk](https://www.producttalk.org/2022/04/best-customer-interview-questions/) — accessed 2026-08-08
- [Sourcing Opportunities: Unlocking the Power of Opportunity Mapping — Product Talk](https://www.producttalk.org/sourcing-opportunities/) — accessed 2026-08-08
- Clayton Christensen, Taddy Hall, Karen Dillon, David Duncan, *Competing Against Luck* (2016) — the milkshake study and JTBD theory
- Teresa Torres, *Continuous Discovery Habits* (2021)

## Changelog
- 2026-08-08 — created
