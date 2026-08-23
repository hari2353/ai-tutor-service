# Discovery: JTBD, User Interviews, Opportunity Trees, Killing Your Idea Early

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-product-thinking Â· **Updated:** 2026-08-23
> **Module id:** `T25-discovery` Â· **Tags:** product

## The 30-second version

Discovery is the systematic process of finding out whether a problem is real, frequent, and worth solving *before* committing engineering capacity to a solution â€” and its central law is that people are unreliable narrators of their own future behavior but decent witnesses of their past behavior. Jobs-to-be-Done (JTBD) reframes demand: customers don't buy products, they hire them to make progress in a circumstance ("when I'm commuting and bored, I want something engaging for 10 minutes"), which explains why feature lists predict adoption so badly. User interviews extract truth only when they ask about specific past episodes instead of hypotheticals and opinions â€” Rob Fitzpatrick's *Mom Test* rules: talk about their life, not your idea; ask about specifics in the past, not generics about the future; listen more than you pitch. Teresa Torres's opportunity solution tree gives discovery a data structure â€” a desired outcome branches into opportunities (needs/pains observed in the wild), each branching into solution candidates, each into experiments â€” which turns vague brainstorming into a searchable map and makes gaps visible. Killing your idea early is the point, not the failure: every idea should face a pre-written kill condition and the cheapest test capable of triggering it, because an idea killed after two weeks and $200 of landing-page traffic costs 1% of what the same idea costs when killed by a failed launch two quarters later.

## Why this gets asked

Principal-level loops increasingly include a product sense or "0â†’1" segment: "How would you figure out whether we should build X?" The interviewer isn't testing whether you've read a PM book â€” they're checking whether you can lead an investment-grade investigation without a PM holding your hand, because at principal scope you'll own initiatives too small for a dedicated PM and too strategic to guess on. The failure mode they screen for is the engineer who falls in love with a solution, runs a "user survey" with leading questions, collects enthusiastic answers, and burns two quarters building something nobody uses. On your resume, the 8-service recsys platform invites exactly this probe: "before you built the personalization service â€” how did you validate that users actually wanted recommendations versus, say, better search?" A credible answer involves talking to actual users about past behavior, structuring findings against alternatives, and naming what evidence would have stopped you. Teams also ask this because discovery failures are expensive and invisible: nobody writes a postmortem for the feature that quietly got zero adoption.

---

## Lineage: past â†’ present â†’ future

**What came before.** Market research spent decades asking customers what they wanted â€” and shipping failures anyway, because stated preferences don't survive contact with purchase decisions. Two responses emerged from different worlds. In academia-industry, Clayton Christensen's jobs-to-be-done theory grew out of the milkshake study (research conducted in the late 1990s-early 2000s with Bob Moesta and colleagues, popularized in his 2003-2016 writing and formalized in *Competing Against Luck*, 2016): fast-food milkshake sales spiked at morning commute hours because commuters were hiring the milkshake for a job â€” a one-handed, non-messy, boredom-killing 20-minute drive companion â€” a job no competitor product category names. In parallel, Anthony Ulwick's outcome-driven innovation (ODI, developed through the 1990s-2000s at Strategyn) argued you shouldn't ask for solutions OR feelings: decompose the job into desired outcomes ("minimize the time it takes to...") and measure their importance and satisfaction on 1-10 scales; the underserved-and-important quadrant is where innovation pays. Meanwhile practitioners were learning interview craft the hard way: Cindy Alvarez (*Lean Customer Development*, 2014) and Rob Fitzpatrick (*The Mom Test*, 2013, self-published and now arguably the most-assigned short book in product) codified why "would you use this?" produces polite fiction.

**Where it stands now.** Teresa Torres's *Continuous Discovery Habits* (2021) is the current operating standard for product trios (PM + design + engineering): weekly customer touchpoints, opportunity solution trees as the shared artifact, and assumption tests rather than grand launches. Continuous interviewing at cadence (weekly touchpoints, 5+ interviews per major bet, small n repeated often) has largely displaced the quarterly research-report model at product-led companies. The live tension in 2026 is authenticity versus scale: AI tooling can transcribe, cluster, and summarize hundreds of interviews cheaply, which tempts teams to substitute volume for quality â€” synthetic respondents and LLM-simulated personas produce plausible-sounding validation that has no causal connection to reality, and several high-profile 2024-2026 postmortems trace shipped-but-unused AI features back to validation that never touched a real user. The craft differentiators now are recruiting the right respondents, noticing what interviewees *do* rather than what they say, and resisting the confirmation bias of a team that already loves its idea.

**Where it's heading.** Highest confidence first: (1) interview analysis gets automated â€” transcription, theme clustering, and highlight reels are table stakes now â€” shifting human effort toward question design and observation; (2) in-product discovery grows: telemetry-triggered micro-surveys and session-replay mining mean some "discovery" happens continuously inside the product rather than in scheduled calls, though this skews toward existing users and misses the non-users who define growth ceilings; (3) moderate confidence and worth skepticism: synthetic-user simulation may become legitimate for narrowing large question spaces before spending scarce human attention â€” but any claim that simulated users replace real ones should be treated as vendor marketing until causally validated, and interviewers increasingly probe whether candidates understand this distinction.

---

## Mental model

The **opportunity solution tree** â€” discovery's data structure:

```
                        OUTCOME (metric the business needs)
                              |
        +---------------------+-----------------------+
        |                     |                       |
   OPPORTUNITY           OPPORTUNITY              OPPORTUNITY
   "I re-watch videos    "I lose my place         "I can't tell
    to find one moment    between devices"          if content is
    and can't"                                      at my level"
        |                     |                       |
   +----+----+          +-----+-----+                 |
   |         |          |           |             SOLUTIONS...
SOLUTION  SOLUTION   SOLUTION   SOLUTION               |
(prototype) (prompt   (bookmark   (cross-device      EXPERIMENT
             ideas)    sync)       resume)            (smoke test,
                                                      concierge, A/B)
```

JTBD supplies the vocabulary for opportunities. The job statement: **When** [situation], **I want to** [motivation], **so I can** [expected outcome]. And the **four forces** acting on any switching decision â€” push of the current situation, pull of the new solution, anxiety about the new solution, habit/allegiance to the current way. An idea dies when push and pull are weak, regardless of how much interviewees politely praise it: anxiety and habit win ties, which is why "they said they'd use it" is worthless evidence and "they're currently duct-taping a workaround" is gold.

Think of discovery as a funnel with deliberate attrition: ~10 raw opportunities heard â†’ ~3 scored worth pursuing â†’ 1 chosen with 2-3 solution candidates â†’ 1-2 cheap experiments â†’ maybe one survives to build. If nothing dies, you aren't discovering, you're decorating.

---

## How it actually works

### Interview craft: the Mom Test rules and their mechanics

The rules (Fitzpatrick): talk about their life, not your idea; ask about specifics in the past, not the future or hypotheticals; listen for commitments and behavior, not compliments. Mechanically, a good interview moves through four phases in 30 minutes: (1) **frame** â€” "I'm not selling anything, I'm trying to learn how you handle X" â€” 2 minutes, sets honesty incentives; (2) **last-episode excavation** â€” "Tell me about the last time you studied for an exam. Walk me through it step by step" â€” 15 minutes of concrete narrative; follow-ups are all "what did you do next," "when was this exactly," "what did you use before this existed"; (3) **workaround probe** â€” the money question: "What's the most you've ever done to try to fix that?" Real pain leaves receipts: spreadsheets built, tools bought, hours spent. A claimed pain with zero attempted workarounds is a preference, not a problem; (4) **commitment close** â€” never "would you pay?" but a real ask: "Would you join a 30-minute pilot next week?" or "Can I come back when we have something to test?" Time, reputation, and repeat engagement are currencies people don't spend on things they don't value.

Signal hierarchy, strongest to weakest: what they currently do > what they've spent money/time on > specific past intentions > generic statements about habits > predictions about future behavior > opinions about your idea. Note that interviews have known failure modes even when done well: recall bias compresses detail, social desirability inflates enthusiasm, and interviewees self-select as engaged users. That's why discovery triangulates interviews with behavioral telemetry (what do people actually do in-product) and, where possible, revealed-preference experiments (does anyone click, sign up, pre-order).

### JTBD and outcome scoring

For each candidate opportunity, decompose into measurable desired outcomes Ulwick-style ("minimize the time it takes to find a specific moment in a lecture video") and score on two 1-10 axes with real users: importance ("how critical is avoiding/achieving this?") and satisfaction ("how well do current solutions serve it?"). The opportunity score is importance Ã— (10 âˆ’ satisfaction) â€” an important-and-miserable job scores ~80-90; an unimportant one scores low no matter how unhappy anyone is. This arithmetic does two jobs: it depersonalizes prioritization debates (you argue about scores' provenance, not whose opinion wins) and it surfaces the classic error â€” building excellent solutions to well-served jobs because they were easy to demo.

### Opportunity solution tree mechanics

Build top-down from the business outcome and bottom-up from interview data, then reconcile. Rules: opportunities are phrased as user needs/pains, never as solutions ("find my place across devices," not "bookmark sync"); sibling opportunities should be mutually exclusive-ish and collectively cover the space (if a branch feels incomplete, interview until it isn't); solutions attach only to opportunities, experiments attach only to solutions. The tree's practical payoff: when a solution fails its experiment, you don't restart from zero â€” you slide sideways to a sibling solution under the same opportunity, preserving the validated problem framing. Teams without trees restart the whole argument every cycle.

### Killing ideas early: the ladder of cheapest tests

Pre-write the kill condition, then buy evidence at the lowest rung that could trigger it:

```
RUNG 0  Desk research + support-ticket mining      cost: hours
RUNG 1  5-8 targeted interviews                    cost: days
RUNG 2  Landing/smoke page + $100-300 ads          cost: ~1 week
RUNG 3  Concierge / Wizard-of-Oz (humans fake it)  cost: 2-4 weeks
RUNG 4  Coded prototype behind a flag              cost: weeks
RUNG 5  Full build                                 cost: quarters
```

Each rung answers the same question â€” will anyone change behavior for this? â€” at 5-20x less cost than the next. A smoke test measuring *sign-up intent* (email submitted against a promise) is imperfect but brutally informative: conversion rates below ~1-2% on cold traffic usually kill the demand story outright, while 5-10%+ justifies rung 3. The concierge test is underrated by engineers precisely because it's embarrassing â€” manually doing what the product would automate reveals whether the *outcome* has pull before any architecture exists. Preceding everything: the **pre-mortem** â€” "it's six months later and this failed; write its obituary" â€” which reliably surfaces kill conditions the team already believes but hasn't stated.

---

## Build it from scratch

**Exercise 1: a complete JTBD interview script for the tutoring/LMS world (run it on 3 real humans this week).**

```
FRAME (2 min)
"I'm researching how students prepare for exams â€” not selling anything,
and there are no wrong answers. I want to understand YOUR actual habits."

WARMUP (3 min)
- "Set the scene: tell me about the last exam you prepared for."
- "When was that? What subject? How long did you have?"

EPISODE EXCAVATION (12 min) -- past tense, specific, no leading
- "Walk me through the first evening you studied. What did you open first?"
- "Where were you? What device? What else was running?"
- "What did you do when you got stuck?"
- "What tools did you touch? In what order?"
- "Was there a moment you almost gave up? What happened next?"

WORKAROUND / RECEIPTS PROBE (8 min)
- "What's the most you've EVER done to fix [problem they named]?
  Have you paid for anything? Built anything? Imported notes anywhere?"
- "What did you do before [tool they mentioned] existed?"
- "If it vanished tomorrow, what would you actually do?"

FOUR FORCES CHECK (3 min)
- Push: "What's most annoying about how you do it today?"
- Pull: "Have you seen anything that seemed like it might fix that?"
- Anxiety: "What would make you NOT trust a new tool with this?"
- Habit: "What would switching cost you â€” notes, streaks, muscle memory?"

COMMITMENT CLOSE (2 min)
- "Can I message you when we have something rough to poke at?"
- (Real ask: pilot invite, beta waitlist, scheduled follow-up.)

NEVER SAY: "Would you use...?", "Do you like...?", "We're building..."
NEVER DEMO during the episode phase.
```

Score afterward using the signal hierarchy: count receipts (money spent, tools adopted, workarounds built). One receipt beats ten "that sounds cool"s.

**Exercise 2: opportunity scoring from survey data, coded.**

```python
# opportunity_score.py -- Ulwick-style importance x dissatisfaction ranking
opportunities = [
    # (name, importance 1-10 avg, satisfaction 1-10 avg, n_respondents)
    ("find-a-moment-in-video",   8.7, 3.1, 41),
    ("cross-device-resume",      6.2, 4.9, 41),
    ("know-if-content-fits-level", 9.1, 2.4, 41),
    ("share-progress-parent",    4.3, 6.8, 41),
]

def score(imp: float, sat: float) -> float:
    return round(imp * (10 - sat), 1)

rows = sorted(((score(i, s), n, name) for name, i, s, n in opportunities),
              reverse=True)
for sc, n, name in rows:
    print(f"{name:28} score={sc:5}  (n={n})")
# know-if-content-fits-level  score=69.7   <- build target: important AND miserable
# find-a-moment-in-video      score=59.7
# cross-device-resume         score=25.4   <- well served; skip despite easy demo
# share-progress-parent       score=13.8   <- unimportant; kill regardless of ease
```

The point of coding it: the ranking is mechanical, so the debate moves to whether the inputs are honest (who answered, how many, leading questions?) instead of whose taste wins.

---

## How it's done in production

| Org | Discovery practice | Engineer-visible artifact |
|---|---|---|
| Intercom | JTBD as shared product language; every feature pitch states the job and the four forces | Feature briefs open with "the job," not the solution |
| P&G (via Ulwick/Strategyn) | ODI: jobs decomposed into 50-150 desired outcomes, surveyed on importance/satisfaction | A ranked, scored outcome list â€” teams pick from targets, not opinions |
| Netflix | Consumer-insight research triangulated with heavy telemetry; taste claims must survive both | Interview findings shown beside behavioral data; mismatches investigated |
| Product-led SaaS (Figma/Linear-style) | Weekly interview cadence per team; in-product micro-surveys triggered by behavior events | Interview highlights posted publicly; opportunity tree visible to eng |
| Amazon | Working Backwards PR/FAQ doubles as a demand-hypothesis doc before build starts | The FAQ's customer-experience section is falsifiable prose |

The mature pattern is **triangulation**: interviews (why), telemetry (what), experiments (how much). Any single leg lies â€” interviews inflate enthusiasm, telemetry can't explain itself, experiments measure only the tested framing. Teams running all three let each method catch the others' biases. Classic supporting number: NN/g's usability research since 2000 found 5 users surface roughly 85% of usability problems in a single round â€” qualitative small-n is legitimate for *finding* issues, never for *sizing* them.

---

## Tradeoffs & when NOT to use it

- **Platform and infrastructure work has no interviewable end user.** The "user" is another engineering team; discovery becomes RFC review plus internal-customer conversations. Don't force student-style scripts onto a message-bus migration â€” but keep the kill condition and cheapest-test logic.
- **Small-n qualitative data cannot prove magnitude.** Eight interviews surface problems, not prevalence; sizing requires surveys or telemetry follow-up. Presenting "6 of 7 users struggled" as a market-size claim gets shredded by anyone who has run real research.
- **Contracted enterprise work sometimes outruns discovery.** A paying account demanding a capability with named dollars attached is revealed preference with a signature; validate *scope*, not existence.
- **Regulated domains constrain disclosure and recording** (health, finance): discovery shifts toward compliance experts, incident data, and advisory boards; keep the past-behavior rule where legally possible.
- **Discovery can become procrastination-by-process.** Endless trees with nothing shipped is a comfort blanket. Guardrail cadence: if three consecutive cycles produce nothing testable, the process has replaced the goal.

---

## Interview questions

### Q1 â€” How would you validate demand for a feature before writing any code?
**Testing:** whether "validation" means surveys or evidence.
**Answer:** Define the outcome metric first, then climb the cheapest-test ladder: desk research and support-ticket mining for existence-of-pain; 5-8 Mom-Test interviews about last-episode behavior and workarounds; a landing/smoke test with cold traffic measuring sign-up intent (~1-2% conversion kills the story, 5%+ advances it); concierge delivery to observe real usage before any architecture. Each rung gets a pre-written kill condition.
**Follow-up trap:** *"People said they'd pay â€” isn't that enough?"* â€” No: stated intent overpredicts badly because politeness and self-image distort hypotheticals. Only committed resources count â€” money spent, time invested, contracts signed. Ask what receipts exist, not what words were said.

### Q2 â€” Explain Jobs-to-be-Done using an example that is NOT the milkshake.
**Testing:** whether they understand JTBD or memorized one anecdote.
**Answer:** A student hires our tutoring app facing Friday's exam: functional job â€” raise expected score per hour of remaining study time; emotional jobs â€” reduce panic, feel progress; social job â€” avoid looking unprepared in class. Note the competing hires: Netflix, sleep, and Discord compete for that same evening though none are education products; that competitive set defines the real market.
**Follow-up trap:** *"So how does JTBD change what you build?"* â€” it shifts analysis from features to progress-per-situation: session lengths respecting a 25-minute commute window, visible-progress indicators serving the emotional job â€” both fall out of the job statement, neither from a competitor feature matrix.

### Q3 â€” Why do leading questions ruin interviews? Explain the mechanism.
**Testing:** depth on response bias beyond reciting the rule.
**Answer:** People optimize for being agreeable; a question embedding its own answer ("would a smart progress bar help you stay motivated?") collects agreement regardless of truth â€” answering the implied question "is this a good idea?" negatively feels socially costly. You end up with a transcript full of yeses that predict nothing, which is worse than no data because it creates false confidence.
**Follow-up trap:** *"How do you fix a stakeholder who insists on asking them?"* â€” never in the room; debrief after with paired questions showing what each version yields, and give stakeholders a separate role (note-taking on exact phrases) so their energy has somewhere to go.

### Q4 â€” What's an opportunity solution tree and what does it buy you when an experiment fails?
**Testing:** whether they know discovery's core data structure and its purpose.
**Answer:** An outcome at the root branches into opportunities (user needs/pains phrased solution-free), each branching into solution candidates, each into experiments. When a solution fails its experiment you slide sideways to a sibling under the same validated opportunity instead of restarting from zero â€” the tree preserves what you learned and localizes failure.
**Follow-up trap:** *"When do you prune an opportunity branch entirely?"* â€” when scoring or interviews show it's unimportant or already well served (high importance Ã— high satisfaction), or when two consecutive distinct solutions both fail â€” evidence the opportunity lacks pull rather than bad execution.

### Q5 â€” A stakeholder wants to survey 500 users instead of interviewing 8. When is each right?
**Testing:** qualitative vs quantitative literacy.
**Answer:** Surveys measure prevalence and priority across known options; interviews discover unknown options and mechanisms. Sequencing matters: interview first to generate the answer space, then survey to size it. A 500-person survey of leading questions industrializes bias; 8 well-run interviews surface what nobody thought to ask about. NN/g's classic finding â€” ~5 users per round catch ~85% of usability issues â€” applies to discovery rounds too, repeated fresh each cycle.
**Follow-up trap:** *"What single question ruins most surveys?"* â€” "Would you use/pay for X?" Intent questions without cost produce fantasy data; ask about past behavior and let revealed preference carry the weight.

### Q6 â€” Tell me about killing your own idea. What triggered it and when?
**Testing:** lived kill-reflex, not theory; also honesty under pressure.
**Answer:** Structure: idea â†’ cheapest test chosen â†’ pre-written kill condition â†’ observed result â†’ decision. Example shape: we believed students wanted AI-generated flashcard decks; the smoke page promised "exam-ready flashcards in 60 seconds," cold traffic converted at 0.8% against a 5% bar while a sibling pitch ("know exactly what to study tonight") hit 9% â€” killed the framing, pivoted to the sibling within a week for ~$200 plus four days.
**Follow-up trap:** *"Couldn't low conversion be bad marketing rather than bad demand?"* â€” yes, that's the standard confound; mitigate by testing two distinct value propositions against each other and by checking qualitative bounce reasons. If every framing fails, demand is dead; if framings diverge wildly, copy was the problem.

### Q7 â€” How do the four forces explain why users praise your product and never switch to it?
**Testing:** whether they can reason about switching behavior, not just interest.
**Answer:** Praise raises perceived pull, but switching is decided by all four forces: push (how unbearable is today?), pull (is the new thing credible?), anxiety (will it fail me mid-exam?), habit (what must I migrate?). High habit + anxiety beats polite pull â€” users stay with painful-but-known tools. Evidence of push comes from active workarounds; reducing anxiety needs trust signals and reversibility (import tools, free tiers), not more feature enthusiasm.
**Follow-up trap:** *"Which force is most underestimated by engineers?"* â€” habit: migration cost is invisible from inside the building because engineers already switched mentally when they wrote the ticket. Ask "what would you have to re-do, re-enter, re-learn?" â€” answers routinely kill launch plans.

### Q8 â€” Design the discovery plan for adding AI hints to a problem-solving practice tool. Budget: 2 weeks before any build decision.
**Testing:** synthesis under constraint.
**Answer:** Days 1-2: mine support tickets and session telemetry for stuck-signals (repeat wrong attempts, rage abandons) to size the pain; days 3-6: six Mom-Test interviews with students who recently practiced, excavating last stuck-episode and workarounds (asking friends? searching? giving up?); days 7-8: score opportunities (importance Ã— dissatisfaction); days 9-14: Wizard-of-Oz the hint experience manually for 10-15 learners to observe whether hints change completion vs just satisfaction. Kill conditions written day 1: e.g., fewer than half of interviewees report active workarounds, or Oz hints don't move next-attempt success â‰¥15%.
**Follow-up trap:** *"'Manually faking AI' sounds like lying â€” how do you keep it honest?"* â€” consent framing: participants are told they're evaluating a prototype experience; the Wizard detail is disclosed post-session. The test measures whether the outcome helps, independent of implementation.

### Q9 â€” Your CEO saw a competitor's AI feature and demands parity by next quarter. Run discovery anyway.
**Testing:** political spine + method adaptation.
**Answer:** Reframe as de-risking speed, not blocking: parity features still need scope choices, so compress discovery to 1-2 weeks â€” mine competitor reviews and user complaints for their feature's weaknesses, interview our users who tried the competitor's version (their workarounds reveal gaps), define the outcome metric where we'd claim victory, and propose the smallest shippable slice with instrumented guardrails. Discovery here converts "match them" into "beat them where their users already complain."
**Follow-up trap:** *"What if there's genuinely no time?"* â€” then negotiate minimum instrumentation: baseline captured before launch, kill/iterate thresholds agreed in writing. Even mandated builds deserve measurement; skipping it guarantees the same debate recurs with less information.

### Q10 â€” When do you stop discovering and start building?
**Testing:** judgment on the discovery/build boundary â€” over-discovery is a real failure mode.
**Answer:** When three things hold simultaneously: an opportunity scores clearly above alternatives on importance Ã— dissatisfaction; at least one solution has survived its cheapest meaningful test (behavioral, not verbal); and the remaining uncertainty is about execution scale, not demand direction. Also timebox-driven: if two rungs of the ladder have passed without triggering the kill condition, further discovery has diminishing returns â€” build the flagged prototype and let production telemetry take over as the discovery instrument.
**Follow-up trap:** *"Who arbitrates 'clearly above'?"* â€” pre-agreed numeric rules set during planning (e.g., top-scoring opportunity must exceed runner-up by â‰¥30%); arbitration rules made after seeing data are politics wearing math's clothes.

### Q11 â€” How do you recruit honest interviewees rather than fans?
**Testing:** practical craft knowledge.
**Answer:** Avoid power users and friends; recruit recent doers of the target job via in-product triggers ("you studied last night â€” 20 minutes?"), communities where complaints live, or modest incentives ($15-30 gift cards are standard) framed as research-not-sales. Screen out people who can't describe a specific recent episode â€” that's the tell of opinion-havers versus practitioners. Never pitch during recruiting; describe the topic area only.
**Follow-up trap:** *"$50 gift cards attract professional survey-takers â€” does that corrupt findings?"* â€” somewhat; screen with open-ended past-behavior questions ("walk me through the last time..."), where fabricators run out of specifics fast. Incentive level tunes quantity; screening quality protects signal.

### Q12 â€” What can AI tooling legitimately do in discovery, and where does it lie to you?
**Testing:** current-tools judgment; increasingly asked in 2026 loops.
**Answer:** Legitimately: transcription, theme clustering across dozens of transcripts, surfacing contradictions, drafting follow-up questions, mining reviews/tickets at corpus scale. It lies when asked to simulate respondents (plausible personas with no causal link to reality), when clustering invents coherence among weak signals, and when summaries smooth away disconfirming quotes â€” always read raw excerpts for decisions. The rule: AI compresses human-collected evidence; it cannot manufacture it.
**Follow-up trap:** *"Could synthetic users substitute when access is hard?"* â€” treat as hypothesis generation only, never validation. If an LLM persona panel says 70% would adopt, that number has zero evidentiary weight; it can only prioritize which real interviews to run first.

---

## Red flags

- Interview scripts containing "would you use / would you pay / do you like."
- Demoing the product during the episode-exacavation phase.
- Validation consisting solely of positive survey responses with no behavioral receipts.
- Opportunity statements written as solutions ("bookmark sync") rather than needs.
- No kill condition recorded before the first test spends money.
- Eight interviews quoted as market sizing ("most users want X").
- Discovery artifacts (trees, notes, highlight reels) with zero decisions attached across multiple cycles.
- Synthetic-user output cited as validation evidence.

## Cheat card

```
JTBD          When [situation], I want [motivation], so I can [outcome]
              competing hires include non-obvious categories (sleep > rival apps)
FOUR FORCES   push x pull vs anxiety x habit; habit+anxiety win ties
INTERVIEW     past episodes > opinions; receipts (money/time/workarounds)
              = truth; commitments (time/reputation) = gold
              NEVER: would-you-use / demo mid-story / hypotheticals
TREE          outcome -> opportunities -> solutions -> experiments;
              fail sideways to sibling solutions, don't restart
SCORING       opportunity = importance(1-10) x (10 - satisfaction(1-10))
              important AND miserable wins; well-served jobs lose regardless
KILL LADDER   desk research -> 5-8 interviews -> smoke page ($100-300 ads,
              <1-2% conv kills, 5%+ advances) -> concierge/WoZ -> flag ->
              full build; each rung ~5-20x cheaper than the next
SMALL-N       ~5 users/round ~= 85% of usability problems (NN/g);
              finds problems, NEVER sizes them
CADENCE       weekly touchpoints; decide every cycle; 3 cycles w/o a
              shipped test = process theater
AI IN DISC    transcribe/cluster/mine YES; simulate respondents NO
```

## Sources

- Rob Fitzpatrick, *The Mom Test* (self-published, 2013), https://www.momtestbook.com/ â€” accessed 2026-08-23
- Clayton M. Christensen et al., *Competing Against Luck* (HarperBusiness, 2016); summary essay "Know Your Customers' Jobs to Be Done," Harvard Business Review, https://hbr.org/2016/09/know-your-customers-jobs-to-be-done â€” accessed 2026-08-23
- Teresa Torres, *Continuous Discovery Habits* (Product Talk LLC, 2021); opportunity solution tree write-ups at https://www.producttalk.org/ â€” accessed 2026-08-23
- Anthony W. Ulwick, "Turn Customer Input into Innovation," Harvard Business Review, https://hbr.org/2002/01/turn-customer-input-into-innovation â€” accessed 2026-08-23
- Nielsen Norman Group, "Why You Only Need to Test with 5 Users," https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/ â€” accessed 2026-08-23
- Cindy Alvarez, *Lean Customer Development* (O'Reilly, 2014), https://www.oreilly.com/library/view/lean-customer-development/9780133155740/ â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

