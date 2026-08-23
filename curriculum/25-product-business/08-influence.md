# Influence: Writing the One-Pager, the Business Case, and Getting Funded

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-product-thinking, T25-unit-economics Â· **Updated:** 2026-08-23
> **Module id:** `T25-influence` Â· **Tags:** leadership, critical

## The 30-second version

Getting funded as a principal engineer is a writing problem wearing a politics costume: the artifacts that decide resource debates are the **one-pager** (problem â†’ outcome â†’ cheapest path â†’ ask, readable in 3 minutes), the **business case** (the same skeleton with full economics: value band, cost band, risks with mitigations, alternatives considered, decision requested), and the **pre-alignment loop** that determines whether either document lands â€” because documents ratified in meetings are written weeks earlier in 1:1s, and a proposal arriving cold at a committee is already dead. The mechanics that matter: lead with the decision and its size (executives read top-down and triage by stakes), quantify in ranges with named assumptions rather than point estimates (false precision is disqualifying), present alternatives you genuinely considered including "do nothing" (its absence signals advocacy, not analysis), pre-negotiate dissent (Netflix's "farming for dissent" â€” circulate to known skeptics BEFORE the meeting so objections arrive as addressed footnotes instead of ambushes), and make the ask concrete: dollars, headcount, deadline, and what happens if the answer is no. The meta-skill is writing for the reader's decision process, not your authorship pride: every paragraph earns its place by shortening someone's path to yes, no, or a better counter-proposal.

## Why this gets asked

Principal loops increasingly contain an artifact review or a "walk me through how you got X funded" behavioral probe because staff+ influence is exercised through documents, not charisma: design docs that win architecture wars, RFCs that redirect roadmaps, business cases that conjure headcount. Interviewers â€” often people who've sat through hundreds of funding reviews â€” are checking whether you know the difference between writing that informs and writing that DECIDES: does the candidate state the ask crisply, size it honestly, name the alternatives including inaction, address the strongest objection rather than the weakest, and close with a decision request complete with default-if-no-answer? They're also screening for the failure patterns that burn credibility: proposals whose numbers only survive squinting, "alternatives" sections containing straw men, meetings ambushing stakeholders who first see the idea in the invite. On this resume, the natural prompt is "how did you get the 8-service platform funded/built?" â€” and the difference between a senior and principal answer is whether the story features a document that did work without you in the room.

---

## Lineage: past â†’ present â†’ future

**What came before.** Business-case formalism descends from capital budgeting: NPV/IRR machinery from mid-20th-century corporate finance (discounted cash flow becoming MBA canon by the 1960s), military-industrial planning systems (PPBS, McNamara-era 1960s) normalizing structured justification memos. Tech adapted the genre: Bell Labs/Lucent-era design proposals, NASA's mission rationale docs, and eventually the internet company variants â€” Amazon's six-page narrative memo + silent reading (instituted mid-2000s, famously banning PowerPoint in executive reviews circa 2012-2018 era reporting), Google's design docs, Stripe/Shopify RFC culture. Amazon's mechanism matters most for engineers because it moved WRITING into engineering promotion criteria: narratives force complete thoughts; slides hide gaps between bullets.

**Where it stands now.** The current synthesis across serious orgs: short narrative docs over decks for decisions (Amazon-style), async-first review cycles (docs circulated with comment windows, meetings reserved for unresolved disagreement â€” GitLab's handbook culture being the extreme), and decision records (ADRs for architecture, now generalizing to product decisions). AI has changed drafting but not persuasion: LLMs produce competent first drafts in minutes, which devalues prose polish and revalues judgment â€” the scarce skills are knowing which numbers matter, which objections are real, and which stakeholder needs a pre-read conversation. Meanwhile attention economics worsened: exec attention per document keeps shrinking (the working assumption for a one-pager is 90 seconds of genuine reading), rewarding ruthless front-loading. The chronic failure remains unchanged since forever: engineers bury the ask under implementation detail, and reviewers conclude "no decision needed" when the truth is "no decision was requested."

**Where it's heading.** Confidence-ordered: (1) async decision-making deepens â€” written proposals with comment-window workflows become the default at distributed companies, making document skill a hard prerequisite for staff+ roles rather than a differentiator; (2) AI-assisted review arrives â€” models flagging unsupported claims, missing alternatives, inconsistent numbers in proposals before humans read them, raising the floor and punishing sloppy arithmetic harder; moderate-high confidence; (3) contested: whether standardized "decision templates" converge across industry enough that document fluency becomes portable like coding languages â€” early signs say partially, with house styles persisting where they encode genuine strategic differences.

## Mental model

```
   THE DECISION PYRAMID (readers triage top-down)

   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ ASK + stakes        (10 seconds) â”‚  <- most documents never state this
   â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
   â”‚ WHY NOW + outcome  (60 seconds)  â”‚
   â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
   â”‚ ECONOMICS: value band, cost band,â”‚
   â”‚ alternatives incl. do-nothing    â”‚
   â”‚                    (3 minutes)   â”‚
   â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
   â”‚ RISKS x mitigations, plan,       â”‚
   â”‚ kill conditions    (appendix)    â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

   MEETING MATH: a doc that reaches the meeting un-read is a failure;
   the meeting ratifies what 1:1s already settled. Documents are the
   residue of alignment, not its substitute.
```

Three laws: (1) **the ask comes first** â€” decision requested, size, deadline, default if unanswered; (2) **ranges with named assumptions beat point estimates** â€” every number carries provenance; (3) **the strongest objection belongs in your document**, addressed in good faith â€” because it will be asked, and the choice is whether its answer arrives from you or against you.

## How it actually works

### The one-pager anatomy (that actually gets funded)

Eight blocks, one page, ~450-600 words: (1) **Decision requested** â€” one sentence with the ask, size, and by-when ("approve 2 engineers for Q4 to build X; decide by Oct 15; silence = no"); (2) **Problem & why now** â€” three sentences max, forcing function dated; (3) **Evidence** â€” the two or three numbers that make the problem real (baseline metric with source, segment size, ticket volume); (4) **Proposed path** â€” cheapest test first, not full vision; (5) **Economics** â€” value band vs cost band, both honest, weakest link labeled; (6) **Alternatives including do-nothing** â€” one line each on why insufficient; (7) **Risks & mitigations** â€” top three only, real ones; (8) **Kill condition** â€” pre-written cancel threshold. Anything longer is a business case wearing a one-pager's name.

### The business case: where ranges do the arguing

Full case for material investments adds: cohort/sensitivity tables (value at pessimistic/base/optimistic), fully-loaded costs (module 06 discipline), NPV or payback framing for capital-scale asks, dependencies and sequencing, and an explicit decision timeline. The craft is in assumption labeling: each number gets measured / modeled / assumed tags, and the sensitivity table shows which assumptions the conclusion actually survives. A case that holds at pessimistic-end value with doubled costs is unanswerable; one needing base-case everything invites the reviewer to hunt for your error â€” reviewers who find one inflated number discount all of them.

### Pre-alignment: the actual game

Sequence that works: (1) map deciders vs influencers vs blockers BEFORE writing â€” the doc's job is to arm supporters, not convert enemies solo; (2) socialize the problem statement first (cheaper to agree on than solutions), incorporating feedback visibly so co-authors form; (3) circulate drafts to the strongest skeptic privately â€” "what would make you kill this?" â€” then address their objection IN the document ("[Skeptic] raised latency risk at scale; mitigation below"); this converts ambushes into footnotes and skeptics into co-signers; (4) send the final doc â‰¥48h before any meeting with comments open; (5) open the meeting with silent reading time if Amazon-style, then unresolved-issues-only discussion; (6) close with explicit decision, owner, date â€” "we'll circle back" is a no with worse documentation. Budget roughly: 60% of influence work happens before anyone else sees the document.

### Getting funded: the economics of the room

Resource allocation follows predictable physics: budgets are annual/quarterly with mid-cycle flexibility mostly for small reversible spends, so timing asks to planning cycles multiplies hit rates; headcount is stickier than dollars (hiring then unwinding is expensive, so headcount asks face higher scrutiny â€” propose contractors or fixed-term spikes for uncertain-duration work); and every yes spends political capital proportionally to ask size relative to the decider's discretionary pool. Practical consequences: split big bets into staged tranches with re-up gates (easier yes per stage, built-in optionality), attach your ask to metrics the decider is personally accountable for, and when told no, ask the diagnostic question â€” "what would this need to show for you to fund the next tranche?" â€” which converts rejection into specification.

---

## Build it from scratch

**Exercise: write a real one-pager and survive a mock review (90 min).**

Scenario (fill from your own backlog ideally): proposing an AI hint system for the tutoring platform. Draft against the eight-block anatomy, then have someone play CFO-skeptic and attack: Where did the baseline come from? What does 'do nothing' cost? Why not buy instead? What's the kill condition? Revise until every attack lands on an answered paragraph. Below is a filled example compressed for print:

```
DECISION REQUESTED: Approve 2 engineers + $8K/mo inference budget for
Q4 to ship AI hints behind a flag. Decide by Oct 15. Silence = no.

PROBLEM / WHY NOW: 34% of new learners abandon within their first
stuck moment (session telemetry, n=41K sessions, Aug). Support tickets
tagged "stuck" grew 40% QoQ. Tractable now: model quality crossed our
eval bar in July at $0.0025/request blended (cascade).

EVIDENCE: Baseline next-attempt success after stuck = 22%. Cohorts
with ANY help (human forum reply) return at 2.1x rate 30 days out.

PATH: Flag-gated hints on math items only -> eval gate >= human-forum
parity on 500-item golden set -> 10% traffic -> read at 14 days.

ECONOMICS: Value band: retention link modeled at $0.31/D7-pt ARPU
x est. +2-4pts D7 => $260K-$780K/yr (modeled - weakest link).
Cost band: inference $70-95K/yr at target adoption + 0.5 eng-FTE run.

ALTERNATIVES: Do nothing: churn contribution persists (~$300K+/yr
est.). Human TA hours: $180K/yr, doesn't scale to nights/weekends.
Buy tutoring-API: $140K/yr, no mastery-data loop, vendor lock-in.

RISKS: Over-reliance (guardrail: >70% hint-rate flag -> auto-throttle);
accuracy harm (kill: CSAT drop >5pts); cost overrun (per-request
ceiling enforced in gateway).

KILL CONDITION: <15% hint usage among eligibles OR no next-attempt
success lift >=10pts by week 6 => cut flag, keep eval harness.
```

Then the meta-exercise: log your own last proposal against the pyramid â€” did the ask appear in the first 50 words? Did alternatives include do-nothing? Which objection arrived in the meeting that should have been in the doc? That gap analysis is the curriculum.

```python
# funding_math.py -- tranche sizing and payback framing for the ask
def staged_ask(total_eng_months, total_value_band, tranches=3,
               loaded_rate=35_000, review_gate_each=True):
    """Split a bet into re-up tranches with gates; easier yes per stage."""
    per = total_eng_months // tranches
    stages = []
    for t in range(tranches):
        cost = per * loaded_rate
        cum_cost = (t + 1) * per * loaded_rate
        # each gate requires evidence share proportional to spend
        stages.append({"tranche": t+1,
                       "eng_months": per,
                       "cost": cost,
                       "cum_cost": cum_cost,
                       "gate": f"evidence >= {round((t+1)/tranches*100)}% of "
                               f"value-band midpoint before re-up"})
    payback_mo = round(cum_cost / (total_value_band["mid"]/12), 1)
    return {"stages": stages, "full_payback_months": payback_mo}

print(staged_ask(9, {"low": 150_000, "mid": 400_000, "high": 800_000}))
# 3 tranches x ~$105K; full payback ~9.5 months at midpoint ->
# present as: '$105K buys the next proof point; stop-loss defined'
```

The tranche table is how big bets get funded under uncertainty: nobody approves $315K on faith, but three consecutive $105K decisions each backed by evidence are routine.

---

## How it's done in production

| Org | Mechanism | The transferable detail |
|---|---|---|
| Amazon | Six-page narrative memos; meetings open with silent reading time | Narratives force complete thoughts; if the memo can't survive silent reading, the meeting can't survive the memo |
| Netflix | "Farming for dissent" â€” proposals circulate with a dissent section naming objectors | Dissent collected BEFORE meetings, converting objections into addressed content |
| Stripe/Shopify | RFC culture with async comment windows; decisions logged with context | Meetings happen only on unresolved threads; the doc trail IS institutional memory |
| Google | Design docs + launch reviews with explicit alternatives sections | Straw-man alternatives get rejected on sight â€” reviewers test whether you argued against yourself honestly |
| GitLab | Handbook-first: decisions documented publicly by default, async-by-default | Writing quality is infrastructure, not decoration â€” onboarding depends on it |

Common thread: written artifacts carry decisions, meetings ratify them, memory lives in docs. Engineers fluent in this grammar operate at org scale; engineers who reserve writing energy for code hit a ceiling exactly where their proposals stop being readable.

---

## Tradeoffs & when NOT to use it

- **Don't document what deserves a conversation.** Two people disagreeing resolve faster talking than trading memos; documents serve decisions needing broad ratification, durable records, or async input â€” not avoiding hard 1:1s.
- **Over-formalizing small asks burns capital.** A full business case for $5K of tooling signals proportionality failure; match artifact weight to ask size (paragraph â†’ one-pager â†’ full case).
- **Pre-alignment can shade into pre-deciding.** Socializing builds co-authorship; side-deals that predetermine outcomes build resentment. State what remains genuinely open â€” "socialized widely, still deciding X vs Y" beats rigged theater.
- **Ranges protect from false precision, not from laziness.** "$100K-$10M" is homework avoidance; bands must come from real sensitivity analysis.
- **Kill conditions need teeth.** Without an actual stop mechanism (flag removal path, budget sunset), pre-registration is decoration; wire the kill switch before asking for funds.

---

## Interview questions

### Q1 â€” Walk me through getting a controversial technical investment funded.
**Testing:** end-to-end influence process, not document cosmetics.
**Answer:** Map stakeholders (decider/influencers/blockers); socialize the problem statement in 1:1s incorporating feedback visibly; draft the one-pager with ranged economics and labeled assumptions; circulate to the strongest skeptic privately and address their objection in-document; send final â‰¥48h ahead with comments open; meet on unresolved issues only; close with explicit decision/owner/date; structure the ask in tranches with re-up gates so each yes is small and evidence-backed.
**Follow-up trap:** *"What if the skeptic won't budge privately?"* â€” their objection goes IN the document with my honest response, and I tell them I've done so. Respect survives disagreement; ambushes don't. Some objections legitimately win â€” better they win in review than in production.

### Q2 â€” What belongs in a one-pager, in order?
**Testing:** artifact literacy at reflex speed.
**Answer:** Decision requested with size/deadline/default-if-silent; problem + why-now with dated forcing function; two or three evidence numbers with sources; cheapest-path proposal; economics as value band vs cost band; alternatives including do-nothing; top-three risks with mitigations; kill condition â€” ~450-600 words, everything else appendix.
**Follow-up trap:** *"Why state 'silence = no'? Doesn't that invite no?"* â€” it prevents zombie approvals dying later during execution when someone finally objects. Explicit defaults surface real blockers while there's still time; ambiguity collects interest.

### Q3 â€” How do you present numbers so finance doesn't shred them?
**Testing:** CFO-language credibility discipline.
**Answer:** Ranges not points; every number tagged measured/modeled/assumed with provenance one click away; a sensitivity table showing the conclusion survives pessimistic value Ã— doubled costs (or saying plainly when it doesn't); weakest link named proactively; definitions aligned with finance's own metrics. The meta-rule: defend your worst number, not your best â€” one inflated figure discovered discounts everything else you said.
**Follow-up trap:** *"Isn't a wide range just covering yourself?"* â€” width proportional to genuine uncertainty is information; the fix is narrowing work (instrumentation, cohort studies) listed as tranche one of the ask, turning humility into a plan rather than an apology.

### Q4 â€” Tell me about a document that worked without you in the room.
**Testing:** whether influence scales beyond personal presence â€” the principal signal.
**Answer shape:** Contested decision â†’ doc written self-sufficient (ask, economics, alternatives, objection addressed) â†’ forwarded through the chain without author present â†’ ratified with minor comments. Example shape: recsys consolidation RFC read by two VPs who never met me; the do-nothing cost analysis carried it. What made it portable: zero tribal knowledge required, all claims sourced, strongest objection answered inside.
**Follow-up trap:** *"How do you know the doc did it?"* â€” causal honesty: reviewer questions asked were only ones the doc hadn't answered, and the draft-to-decision diff was small. If pressed, acknowledge relationships carried part of it â€” overclaiming sole credit reads worse than shared credit.

### Q5 â€” Your proposal gets deferred: 'great doc, wrong quarter.' Now what?
**Testing:** persistence mechanics without nagging.
**Answer:** Diagnose the no: capacity, priority, or courtesy-deferral (a slow no). Ask directly: "What would need to be true for Q2?" Then attach to the blocker's success metric, shrink the tranche into discretionary space, or set a dated follow-up tied to the stated condition. Meanwhile ship the cheapest unblockable slice generating evidence, so next cycle arrives with data instead of the same slide.
**Follow-up trap:** *"When do you escalate over the deferrer's head?"* â€” rarely and only after transparent warning; skipping levels trades one decision for lasting trust damage. Exception: safety/compliance urgency where formal escalation paths exist precisely for bypassing preference.

### Q6 â€” How much pre-alignment is too much?
**Testing:** judgment on the alignment-vs-manipulation boundary.
**Answer:** Too much = review becomes theater: outcome predetermined, objections suppressed via unrelated side-deals, participants performing consent. Keep decisions genuinely open: state what's undecided, invite written dissent, accept losing. Alignment work should improve the decision's QUALITY (better assumptions, fewer surprises); when it only improves PASSAGE, it's politics.
**Follow-up trap:** *"Pure meritocratic review never happens though?"* â€” degree matters and is measurable over time: whether outcomes track doc quality or sponsor identity. Win your cases without accelerating cynicism; cultures where only sponsored items pass bleed talent.

### Q7 â€” Write the ask paragraph right now for [scenario]. Go.
**Testing:** live composition under pressure â€” increasingly common in staff+ loops.
**Answer pattern:** Decision + resource + duration + deadline + default + what-no-means: "Approve 1 engineer and $3K/mo inference for six weeks to validate AI hints against our eval gate; decide by Friday; silence = no; a no costs us a quarter of learning and we revisit with vendor data." It sizes exposure, bounds duration, defines both exits.
**Follow-up trap:** *"Why include what a no costs YOU?"* â€” reframes refusal as a priced choice instead of rejection and demonstrates you've accepted the downside, which paradoxically raises perceived competence and eases yes.

### Q8 â€” How do you write for executives who give a doc 90 seconds?
**Testing:** audience adaptation.
**Answer:** Front-load ruthlessly: ask and stakes inside 50 words; one-screen self-sufficiency; numbers in tables not prose; assertion-style headings carrying each section's conclusion. Kill hedging ("might potentially consider") â€” hedges transfer doubt upward. Put methodology and caveats in appendix linked from claims. Then test it: hand to someone outside your team for 90 seconds and ask them to state the ask, the stakes, and the deadline â€” failure means revise, not explain.
**Follow-up trap:** *"Doesn't simplifying distort?"* â€” simplification lives in presentation, not substance: the full model stays linked behind every number. What distorts is burying material caveats so they can't be found; front-loading with linked depth informs both readerships honestly.

### Q9 â€” A peer keeps torpedoing your proposals in meetings after friendly 1:1s. Handle it.
**Testing:** political spine with documentation instincts.
**Answer:** First verify it's pattern not paranoia (meeting minutes, repeated topics). Second, take their objections seriously enough to write down â€” some torpedoes are unprocessed disagreements about facts. Third, make pre-alignment impossible to skip: circulate docs earlier, explicitly invite written dissent with deadlines, and in-meeting redirect: "That concern's addressed on page two â€” does the mitigation fail some test you'd name?" If it persists as pure status combat, escalate the RELATIONSHIP conversation privately, once, directly.
**Follow-up trap:** *"Shouldn't you just go around them?"* â€” going around converts a peer into an enemy with receipts; most torpedo behavior responds to being taken seriously early plus public processes that raise ambush costs. Reserve escalation for genuine bad faith.

### Q10 â€” What goes in the business case that doesn't fit the one-pager?
**Testing:** artifact hierarchy fluency.
**Answer:** Full sensitivity tables (three-scenario value/cost matrix), cohort-level assumptions, NPV/payback framing for capital-scale asks, dependency and sequencing plan, staffing plan with named-vs-TBD roles, detailed risk register with owners, compliance/security review status, and the decision timeline with explicit re-up gates. Rule of thumb: the one-pager must remain true standalone; the business case defends every line of it under oath.
**Follow-up trap:** *"Who actually reads the long version?"* â€” finance, security, legal, and the decider's chief of staff â€” the people whose objections surface later as blockers if unaddressed. The long doc exists for the reviewers who kill projects quietly in back-channels.

### Q11 â€” How do you build a reputation that makes future asks cheaper?
**Testing:** long-horizon capital management.
**Answer:** Close the loop on every funded item: report actuals against promised bands within a quarter of launch â€” especially when results disappoint (credibility compounds fastest from honest misses). Kill your own failing projects publicly per pre-registered conditions. Share credit precisely (named contributions). And bank small yeses: asking for reversible, well-bounded things first establishes the pattern that your asks come pre-priced with kill switches. Reputation is just your historical hit-rate plus honesty-about-misses, stored in other people's memories.
**Follow-up trap:** *"Doesn't killing your own project look weak?"* â€” the opposite, once framed: 'we spent $105K learning this didn't clear the bar we set beforehand' is the strongest possible evidence your future $500K asks are safe. Teams remember who burned budget defending zombies far longer than who canceled early.

### Q12 â€” When should you NOT write a document at all and act?
**Testing:** bias-of-action judgment â€” trapping candidates who over-rotated toward process in earlier answers.
**Answer:** Reversible two-way-door calls under your own authority (experiment flags, tooling trials within budget) don't need ratification theater â€” act, then document outcomes. Emergencies invert the pipeline: stabilize, narrate after. And early-trust-building phases sometimes need visible delivery before any proposal lands â€” a principal with zero shipped artifacts writes into a vacuum. Documents multiply existing credibility; they don't substitute for it.
**Follow-up trap:** *"Where's the line between decisiveness and dodging review?"* â€” authority boundaries made explicit: acting inside your mandate and reporting is decisiveness; acting outside mandate and reporting later is process-violation regardless of outcome quality. State which door you're walking through BEFORE walking through it.

---


### Q13 â€” Your CFO challenges the value band mid-meeting with a different churn assumption. Handle it live.
**Testing:** composure plus model fluency under fire.
**Answer:** Don't defend the number â€” recompute together: take their churn input, rerun the chain visibly, show the revised band, and state whether the decision flips at their assumption. If it survives: 'even at your churn we clear cost.' If it doesn't: 'at your churn the tranche-one gate tells us cheaply before most spend is committed' â€” which is exactly why tranches exist. The win condition isn't my original number; it's a defensible decision either way.
**Follow-up trap:** *"What if you can't recompute on the spot?"* â€” say so and commit to a dated follow-up with the sensitivity added, then actually deliver within 24-48h. Pretending to model live and fumbling destroys more credibility than admitting the table needs an hour.

### Q14 â€” How do you write a document that must survive legal, finance, AND engineering review?
**Testing:** multi-audience composition.
**Answer:** Each audience reads for different failure modes: legal reads for liability language and data flows; finance for cost definitions and commitments; engineering for feasibility claims. Structure so each finds theirs fast â€” glossary defining terms precisely (what 'resolution' means), data-flow appendix for legal, cost-model appendix for finance, architecture sketch for eng. Avoid adjectives with legal weight ('secure,' 'guaranteed') unless reviewed; prefer testable statements ('AES-256 at rest per policy X').
**Follow-up trap:** *"Won't four audiences make it unreadable?"* â€” the core stays one page; audiences are served by labeled appendices they choose to open. What makes it unreadable is averaging all audiences into mush â€” write the spine for the decider, appendices for the reviewers.

### Q15 â€” Tell me about a time your proposal lost. What did you do after?
**Testing:** losing-with-grace mechanics â€” interviewers probe whether resentment leaks.
**Answer shape:** Structure: genuine contest â†’ lost on merits or politics (say which honestly) â†’ what I did: asked for the deciding factors in writing, supported the chosen direction publicly ('disagree and commit'), captured what evidence would change the answer, and revisited exactly once when that evidence arrived. If the winning path then struggled, no 'told-you-so' â€” offered help. The reputation effect of losing well funded my NEXT proposal disproportionately.
**Follow-up trap:** *"Did the other side's approach fail?"* â€” answer honestly without relish: partial struggles are normal; the moment to raise them is when YOUR pre-stated evidence materializes, framed as new information, not vindication. Scorekeeping aloud is how losing well stops working.

### Q16 â€” A skip-level asks you directly to fast-track something your manager deprioritized. Navigate it.
**Testing:** organizational navigation without faction damage.
**Answer:** Don't refuse and don't secretly comply. Acknowledge the interest, then route transparency: tell my manager the conversation happened and what was asked, propose the skip-level join a discussion where trade-offs get made openly, and if priority genuinely conflicts, put both items' costs side by side for whoever owns the portfolio. Skip-levels often don't know the queue state; the fix is information, not loyalty tests.
**Follow-up trap:** *"And if the skip-level insists?"* â€” then it's an explicit priority override, which managers absorb professionally when done transparently; what poisons orgs is silent overrides discovered later. My job: make the override visible and documented, not to arbitrate seniority by stealth.

### Q17 â€” How do you disagree with a decision already announced publicly?
**Testing:** dissent timing and channel judgment.
**Answer:** Before announcement: fight hard in the document/meeting. After: commit unless it's harmful-illegal-safety territory, where escalation duties override teamplay. If genuinely new disqualifying information emerges post-decision, bring it privately to the decider first with specifics ('the latency data shipped yesterday changes assumption three') â€” giving them the chance to amend their own decision rather than contradicting them publicly. Public second-guessing buys moral satisfaction at the price of every future private consultation.
**Follow-up trap:** *"Isn't 'disagree and commit' just enforced silence?"* â€” no: it channels disagreement into the decision process where it has leverage, and preserves standing for next time. Silence is never-committing-to-disagree-later; the practice requires stating disagreement clearly BEFORE committing â€” in writing where possible.

### Q18 â€” What's your system for tracking asks so nothing dies in follow-up?
**Testing:** operational discipline behind influence.
**Answer:** A decision log: each ask with date, audience, requested decision, current status, next action + owner + date. Review weekly; nudge on missed dates with one-line replies linking context. Post-decision, the log seeds the actuals-vs-promise report. It sounds bureaucratic and takes ~20 minutes weekly â€” what it replaces is the far costlier state where your proposals die of neglect rather than rejection and nobody, including you, noticed.
**Follow-up trap:** *"Tools?"* â€” any shared tracker works; the non-negotiables are dates attached to every waiting-state item and a single source of truth others can inspect. Private lists defeat the purpose: visibility itself applies gentle pressure that closes loops.

---

## Red flags

- The ask appears in the last paragraph (or never â€” only "context and options").
- Point estimates everywhere with no provenance labels or sensitivity table.
- Alternatives section contains straw men; do-nothing omitted.
- Skeptics first see the proposal in the meeting invite.
- No kill condition, or one with no enforcement mechanism.
- Post-decision silence: funded items never report actuals versus promise.
- Every disagreement handled by adding another meeting instead of a written position.

## Cheat card

```
ONE-PAGER     ask+stakes(50 words) -> why-now -> evidence(2-3 nums
              w/sources) -> cheapest path -> value band vs cost band
              -> alternatives INCL DO-NOTHING -> risks x3 -> KILL
              CONDITION. ~450-600 words. Silence = no.
BUSINESS CASE adds sensitivity tables, NPV/payback, dependencies,
              staffing, risk register w/owners, re-up gates;
              must defend every one-pager line under oath
RANGES        every number tagged measured/modeled/assumed;
              show conclusion survives pessimistic x doubled-cost;
              name weakest link FIRST - defend worst number
PRE-WORK      map deciders/influencers/blockers -> socialize PROBLEM
              -> skeptic preview ("what would kill this?") -> their
              objection answered IN doc -> final >=48h ahead ->
              meeting = unresolved issues only -> decide/owner/date
TRANCHES      big bets split ~3x with evidence gates per re-up:
              '$105K buys next proof point; stop-loss defined'
ASK PHYSICS   headcount stickier than dollars; time to planning
              cycles; attach to decider's own metrics; on NO ask
              'what would fund the next tranche?' -> spec
EXEC READING  90 seconds real; assertion-headings, tables, hedge-
              kill; test: stranger states ask/stakes/deadline in 90s
CREDIBILITY   report actuals vs bands quarterly ESPECIALLY misses;
              kill own failures publicly; precise credit; small
              reversible yeses first - reputation = hit rate + honesty
```

## Sources

- Colin Bryar & Bill Carr, *Working Backwards* (St. Martin's Press, 2021) â€” six-page memo + silent reading mechanics, https://www.workingbackwards.com/ â€” accessed 2026-08-23
- Netflix Culture Memo ("farming for dissent," context-not-control), https://jobs.netflix.com/culture â€” accessed 2026-08-23
- April Dunford, *Obviously Awesome* (Ambient Press, 2019) â€” positioning feeds the narrative skeleton â€” accessed 2026-08-23
- Stripe blog on writing/RFC culture; GitLab handbook on async decision-making, https://handbook.gitlab.com/handbook/company/culture/all-remote/asynchronous/ â€” accessed 2026-08-23
- Barbara Minto, *The Pyramid Principle* (Pearson, orig. 1987) â€” assertion-first structure, https://www.barbaraminto.com/ â€” accessed 2026-08-23
- Jeff Bezos, 2017 shareholder letter (narrative structure, "disagree and commit"), https://www.aboutamazon.com/news/company-news/2017-letter-to-shareholders â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

