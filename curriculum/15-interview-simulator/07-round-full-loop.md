# Boss: Full Onsite Loop (5 rounds)

> **Track:** T15 Interview Simulator · **Time:** 4h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T15-round-full-loop` · **Tags:** boss,final

**Runs under `tutor-mock` as round type `loop`. Orchestrates `T15-round-coding`, `T15-round-design`, one of `T15-round-ml` / `T15-round-genai` (or both, split, if the loop calls for two AI-depth rounds), and `T15-round-behavioral`, then closes with a committee verdict. Optionally substitute `T15-round-hm` for one technical round if the target loop includes a hiring-manager round, as most real onsites do.**

## The round in 30 seconds

Five 45-minute rounds back to back with short breaks, run and scored exactly as they would be standalone, followed by a committee verdict that is not an average. A pass looks like: consistent seniority signals across all five rounds (not just the one the candidate is strongest in), a coherent narrative that survives being told five different ways to five different interviewers, and a clean recovery from at least one manufactured failure per round. A fail looks like the pattern real loops actually fail on: uneven performance where one round is dramatically worse than the other four, because a real hiring committee anchors hardest on the outlier, not the mean. The single most important thing this module teaches is that **a candidate does not get hired by being good on average — they get hired by not being bad anywhere, plus being excellent somewhere**, and the debrief format exists to surface exactly where "somewhere" was and wasn't.

## Format

- **Total: roughly 4 hours** — five 45-minute rounds plus breaks (a real onsite typically runs 5-10 minutes between rounds; simulate at least a 5-minute break to reset context between each).
- **The five rounds, run in this order** (the order itself is a deliberate choice — see Format notes below):
  1. **Coding** (`T15-round-coding`) — first, because it's the most mechanically graded and sets a baseline before fatigue sets in.
  2. **System Design** (`T15-round-design`) — second, while the candidate is still fresh enough for 45 minutes of sustained structured reasoning.
  3. **AI/ML Depth** (`T15-round-ml` or `T15-round-genai`, interviewer's choice based on the target role's emphasis) — third, positioned mid-loop where fatigue starts to matter and derivation quality (versus recall) becomes the discriminator.
  4. **Behavioral** (`T15-round-behavioral`) — fourth, deliberately placed after the technical gauntlet, because a candidate who is technically sharp but has nothing left for STAR discipline by round four is a real and common failure pattern worth surfacing in practice.
  5. **Hiring Manager / Resume Grill** (`T15-round-hm`) — fifth and last, closing the loop the way most real onsites do, with the person who has to defend the hire internally.
- **Between rounds:** a genuine break, not a instant cut — the candidate should physically step away for at least 2-3 minutes. Context does not carry between rounds; each interviewer in a real loop has not seen the others' rounds, and simulating that means not referencing round 1's specifics in round 3 unless the candidate brings it up.
- **What the interviewer does across the loop:** runs each round exactly as its own module specifies, with no softening because it's round 4 of 5 and the candidate looks tired — real interviewers do not know or care that this is the candidate's fourth round of the day. Tracks, silently, which round is trending weakest as the loop progresses, because that's the input to the committee verdict.
- **What the interviewer does not do:** carry a bad round's score into the next round's scoring (each round is judged on its own evidence); let the candidate reference "I already covered this in an earlier round" as a substitute for actually answering the current round's question; skip the debrief.

## What is actually being tested

This module tests something none of the five individual rounds can test alone:

1. **Consistency under cumulative fatigue.** Whether seniority signals (unprompted tradeoffs, named rejected alternatives, honest uncertainty) persist into round 4 and 5, or whether they were only present when the candidate was fresh in round 1.
2. **Narrative coherence across interviewers who don't talk to each other in real time.** Whether the same story, told to two different rounds for two different purposes, stays factually consistent (the same number, the same rejected alternative, the same scope) rather than drifting to fit whatever's convenient in the moment.
3. **Whether one weak round is recoverable or disqualifying.** This is the single most consequential thing a real committee decides, and it's almost never a simple average — see Committee verdict below.
4. **Level calibration from the full evidence set, not one data point.** A single round can make someone look staff-level (a strong design round) or senior-level (a shaky coding round); the level read that survives a real committee debate comes from the pattern across all five.
5. **Whether the candidate manages their own energy and focus across a long day.** A candidate who visibly front-loads all their best material into round 1 and has nothing left by round 5 is showing a real, observable limitation, not bad luck.

## Question bank

This round's "questions" are not a per-topic technical bank — that lives in the five component modules — but the closing-loop questions a real onsite actually asks at the end of the day, plus the calibration questions a committee runs on itself when producing a verdict. Both are real, reported mechanisms and both are frequently under-prepared for. Twelve entries, organized closing-questions-to-the-candidate → self-calibration-for-the-mock-interviewer → level-differentiation.

### Closing questions asked directly to the candidate

**Q1 — "How do you think the day went overall?"**
- **Strong:** A specific, honest self-assessment naming which round felt strongest and which felt weakest, with a reason for each, rather than a uniform "I think it went well." Volunteering a real weak spot here (rather than waiting to be asked) is itself read as a seniority and self-awareness signal.
- **Weak:** "I think it went really well, thank you for having me" with no differentiation across rounds — reads as either not self-aware or managing the answer rather than answering it.
- **Follow-up trap:** *"Which round would you want to redo, and what would you do differently?"* Wants a concrete, specific answer tied to an actual moment (not "I'd be less nervous"), which tests whether the self-assessment in Q1 was real or performative.

**Q2 — "Is there anything from an earlier round you'd like to add or clarify?"**
- **Strong:** Used sparingly and specifically — a genuine clarification of a number that was misspoken, or a mechanism that wasn't fully unpacked under time pressure, stated crisply. This is a real, limited-use opportunity, not an invitation to re-litigate the whole day.
- **Weak:** Either declining to use it when there's a real, known gap (a wrong number given earlier that was never corrected), or using it to relitigate a round at length rather than making one crisp addition.
- **Follow-up trap:** *"Why didn't you say that during the round itself?"* Tests whether the addition is a genuine afterthought (time pressure, a follow-up trap that derailed the original point) or an attempt to retroactively patch a real gap — the honest answer to the "why not then" question matters more than the addition itself.

**Q3 — "Do you have any questions for us?"**
- **Strong:** One or two specific, well-informed questions that demonstrate the candidate was listening across all five rounds (referencing something a specific interviewer said, or a tension surfaced in the design round) rather than a generic "what's the culture like" — asked with genuine curiosity, not as a scripted close.
- **Weak:** No questions at all, or purely logistical questions (start date, PTO policy) with zero content-based curiosity about the role or the day's rounds.
- **Follow-up trap:** *"That's a good question — what's your own hypothesis before I answer?"* Some interviewers turn a candidate's question back on them to see if it was genuinely curious or rehearsed; a candidate with a real working hypothesis behind their own question scores this well.

### Self-calibration questions the mock interviewer/orchestrator runs when producing the verdict

**Q4 — "Would I want to be blocked on a decision by this person's judgment, based on today?"**
- **Strong finding:** Evidence across at least two rounds (typically design and one depth round) of judgment under ambiguity that would hold up without supervision — named tradeoffs, honest uncertainty, a defensible call under incomplete information.
- **Weak finding:** Judgment only demonstrated when explicitly prompted for it ("what would you do differently") rather than exercised proactively during the rounds themselves.
- **Follow-up trap (for the orchestrator, not the candidate):** *"Is this judgment, or is this recitation of a judgment framework?"* A candidate who says all the right words about tradeoffs but whose actual decisions in the design and coding rounds didn't reflect judgment (e.g., picked the over-engineered option despite correctly naming the simpler one as usually better) should be scored on the decision, not the vocabulary.

**Q5 — "If I had no other candidate in the pipeline, would this still be a hire?"**
- **Strong finding:** The answer doesn't change based on this framing — a genuine HIRE or STRONG HIRE holds regardless of the comparison set, because the evidence stands on its own.
- **Weak finding:** The verdict was implicitly relative ("better than the other people we've seen this week") rather than absolute against the role's actual bar — this is a real distortion that creeps into real hiring loops and the mock should guard against it explicitly.
- **Follow-up trap:** *"Would this be a hire at the level they're asking for, or one level down?"* Forces the orchestrator to separate "should this person be hired" from "should this person be hired at THIS level," which are different questions with different evidence bars.

**Q6 — "What would change my mind about the weakest round?"**
- **Strong finding:** A specific, falsifiable answer (e.g., "if the GenAI round had included even one unprompted mention of an eval strategy, I'd move this to HIRE overall") rather than a vague sense that the round wasn't great.
- **Weak finding:** No clear answer — the weak round is just generally "not as strong," with no specific missing evidence named, which makes the verdict unfalsifiable and therefore not trustworthy as a diagnostic.
- **Follow-up trap:** *"Is that a real bar, or a bar you're inventing to justify a verdict you already decided on?"* A genuine self-check against motivated reasoning, in either direction (either being too harsh because one round was memorable, or too lenient because four rounds were strong).

### Level-differentiation questions

**Q7 — "Across all five rounds, how many times did the candidate name a tradeoff or a rejected alternative without being asked?"**
- **Strong finding:** A real count, not an impression — staff-level candidates should show this pattern in at least 3 of 5 rounds; principal-level in essentially all 5.
- **Weak finding:** Unprompted tradeoffs only appeared in the rounds the candidate was clearly most comfortable in (often GenAI, if that's the strong suit), with none in coding, design, or behavioral.
- **Follow-up trap:** *"Does the domain matter, or is this candidate-level behavior?"* Tests whether the pattern is a genuine trait (shows up regardless of topic) or an artifact of one domain's comfort level — a real differentiator between "strong in one area" and "operates at this level generally."

**Q8 — "Did the candidate ever say 'I don't know' or 'I'd need to check' precisely, rather than confidently guessing?"**
- **Strong finding:** At least one instance of precise, well-placed uncertainty (not hedging on everything, but a clean admission on a genuinely unknown point) — this is a specific, positive signal at senior level and above, not a weakness.
- **Weak finding:** Either the candidate never admitted uncertainty anywhere across five rounds (a % likely to be either extremely knowledgeable or unwilling to be caught not knowing — worth distinguishing), or admitted uncertainty so often it read as a lack of preparation rather than calibration.
- **Follow-up trap:** *"Was the uncertainty about something genuinely uncertain, or something they should have known?"* Distinguishes well-calibrated uncertainty (a real open question, like an unmeasured cost model) from a knowledge gap dressed up as humility.

**Q9 — "Which round's evidence would a principal-level bar-raiser find most attackable, and did the candidate defend it or update?"**
- **Strong finding:** When pushed on the most attackable point (usually a bare metric or an inflated scope claim), the candidate updated the claim honestly rather than defending it past two challenges.
- **Weak finding:** The most attackable point was never actually pushed on hard enough during the loop to see the reaction — a gap in how the mock was run, not just in the candidate's performance, worth noting for the next mock.
- **Follow-up trap:** *"If we ran this exact loop again in three months, what's the one thing most likely to still be unresolved?"* Forces a genuinely predictive, not retrospective, answer — useful for queueing the next study cycle.

**Q10 — "Was there a round where the candidate seemed to be performing confidence rather than reasoning?"**
- **Strong finding:** No — reasoning was visible and could be interrupted/redirected without the candidate losing the thread, across all five rounds.
- **Weak finding:** At least one round where a confident-sounding answer, when interrupted or pushed, revealed the confidence wasn't backed by a reasoning process that could adapt to new information.
- **Follow-up trap:** *"Which specific interrupt or follow-up revealed this, if it happened?"* Requires citing the actual moment, not an overall impression, which keeps the finding falsifiable and useful for the debrief.

**Q11 — "Knowing everything from all five rounds, what's the ONE topic that shows up as a gap more than once?"**
- **Strong finding:** A single, specific, cross-round pattern (e.g., "numbers without baselines showed up in both the ML round's metric questions and the behavioral round's engagement figure") rather than five separate unrelated gaps.
- **Weak finding:** A list of five different weaknesses, one per round, with no attempt to find the common thread — this produces a debrief that's accurate but not actionable, since a candidate can't fix five things before the next loop but can fix one pattern.
- **Follow-up trap:** *"Is this pattern about knowledge, structure, or nerves?"* The same three-way diagnostic used in real interview debriefs — the fix is completely different depending on which one it is, and conflating them produces a useless "study more" recommendation.

**Q12 — "If this candidate got an offer today, what would the onboarding plan need to address in the first 90 days based on this loop?"**
- **Strong finding:** A specific, evidence-based answer (e.g., "pair them with someone senior on cost modeling for GPU workloads, since that gap showed up in both the design round and the HM grill") rather than a generic "get them ramped up."
- **Weak finding:** No answer, or an answer disconnected from anything actually observed in the five rounds — this is the clearest sign the debrief wasn't actually used to extract a specific, forward-looking finding.
- **Follow-up trap:** *"Is that a real gap, or just the most recent thing you remember from the last round?"* Guards against recency bias in the verdict — the loop ran coding first and HM grill last, and a lazy debrief over-weights the last round simply because it's freshest in memory.

## Committee verdict

This is the part that makes a full-loop run different from five independent mock scores stapled together. After all five rounds are scored individually using each round's own rubric and score bands:

1. **State each round's score and verdict plainly**, in the order run: `Coding: 15/20 HIRE · Design: 18/20 STRONG HIRE · GenAI Depth: 12/20 LEAN HIRE · Behavioral: 16/20 HIRE · HM Grill: 14/20 HIRE`.
2. **Name the weakest round explicitly and ask whether it's disqualifying.** Real committees weight this far more heavily than an average would suggest. The operative question is not "what's the mean score" but **"does the weakest round, on its own, indicate a gap serious enough to sink the hire regardless of the other four?"** A LEAN HIRE on a depth round the role specifically needs (GenAI depth for a GenAI-heavy role) is a much bigger problem than a LEAN HIRE on a round more tangential to the day-to-day (a coding round for a role that's 90% design and stakeholder work).
3. **Look for a pattern of contradiction, not just a low score.** A candidate who is STRONG HIRE on system design but NO HIRE on the coding round's "explain the mechanism behind your own claim" moments raises a different, worse flag than a uniformly middling performance: it suggests the strong round may have been well-rehearsed rather than reflecting real depth, and the committee should re-examine the strong round's evidence more skeptically, not just average around the weak one.
4. **State the level read from the pattern, not from the best round.** If four rounds show senior-level structure and only one shows a genuine staff-level unprompted tradeoff, the honest level read is senior with staff potential, not staff — real committees resist the temptation to round up to the best single data point.
5. **Give the verdict in the same shape a real committee would document it**, four required elements:
   - **Overall recommendation:** STRONG HIRE / HIRE / LEAN HIRE / NO HIRE / STRONG NO HIRE — not an arithmetic average of the five round scores, an explicit judgment call weighted by which round would have sunk it.
   - **The round that would have sunk it, and why**, named specifically even in an overall HIRE — a real committee discussion always surfaces this, and pretending a HIRE loop had no weak points is dishonest to the candidate's actual development needs.
   - **The level read:** senior / staff / principal, stated with the specific evidence that supports it and the specific gap that would need to close to justify the next level up.
   - **One thing to fix before the next real loop:** the single highest-leverage gap across all five rounds, not five separate gaps — if the coding round and the behavioral round both showed the same underlying issue (e.g., silence under pressure, or a reluctance to name a rejected alternative unprompted), name that pattern once, not twice.

## Debrief format

Run immediately after the committee verdict, while the loop is still fresh:

```
FULL LOOP DEBRIEF — <date>

ROUND-BY-ROUND
  1. Coding          <score>/20  <verdict>   weakest moment: <one line>
  2. Design          <score>/20  <verdict>   weakest moment: <one line>
  3. <ML or GenAI>   <score>/20  <verdict>   weakest moment: <one line>
  4. Behavioral      <score>/20  <verdict>   weakest moment: <one line>
  5. HM Grill        <score>/20  <verdict>   weakest moment: <one line>

COMMITTEE VERDICT
  Overall: <STRONG HIRE | HIRE | LEAN HIRE | NO HIRE | STRONG NO HIRE>
  Would have sunk it: <round> — <specific reason, quoting the candidate>
  Level read: <senior | staff | principal>
  Evidence for that level: <2-3 bullets across multiple rounds>
  Gap to the next level up: <specific, not generic>

CONSISTENCY CHECK
  Did the same fact/number/story stay consistent across rounds where it
  reappeared? <yes/no, with the specific discrepancy if no>
  Did seniority signals (unprompted tradeoffs, honest uncertainty, named
  rejected alternatives) persist into round 4-5, or only appear early?

THE ONE THING
  <the single highest-leverage fix across all five rounds, not five separate
  fixes — find the common thread if one exists>

QUEUED
  <topics added to the weak list, tagged by which round(s) surfaced them>
```

Append the loop result to `progress/SESSION-LOG.md` in the same format individual mocks use, and log it in the app's Boss tab — a passed full loop counts toward the `full-loop` badge (5-round onsite) in addition to the per-round `boss-slayer` progress.

## Rubric

Each round is scored on its own 4×5=20-point rubric exactly as defined in its own module (`T15-round-coding`, `T15-round-design`, `T15-round-ml`/`T15-round-genai`, `T15-round-behavioral`, `T15-round-hm`). The full-loop module adds one cross-cutting dimension on top, scored separately and reported alongside the five round scores rather than folded into them:

| Cross-cutting dimension | 1-2 | 3 | 4-5 |
|---|---|---|---|
| Consistency across rounds | A fact, number, or scope claim changes materially between rounds where it reappears (e.g., a headline metric's stated measurement method differs in the behavioral round versus the HM grill); seniority signals present only in round 1-2 and absent by round 4-5 | Facts stay broadly consistent with minor phrasing differences; some fatigue-related drop in unprompted tradeoff-naming by the later rounds but not a collapse | Every recurring fact, number, and scope claim is identical across rounds; unprompted seniority signals (tradeoffs, rejected alternatives, honest uncertainty) are present at the same rate in round 5 as round 1 |

## Score bands

The full-loop verdict is not computed from these bands mechanically — it is a judgment call per the Committee verdict section above — but these bands describe what each overall recommendation should look like in practice.

- **STRONG HIRE overall.** No round below HIRE (13+/20); at least one round at STRONG HIRE (17+/20) in the domain most relevant to the target role; the consistency check passes cleanly; the level read is supported by evidence from at least three of the five rounds, not just one.
- **HIRE overall.** At most one round at LEAN HIRE, and that round is not in a domain central to the role; no round at NO HIRE or below; consistency check passes with at most minor phrasing drift; seniority signals persist into the later rounds even if less frequently than round 1.
- **LEAN HIRE overall.** One round at NO HIRE, or two rounds at LEAN HIRE, especially if either falls in a domain central to the role; consistency check shows one real (not cosmetic) discrepancy; seniority signals visibly thin out by round 4-5, suggesting the strong early rounds may have been front-loaded preparation rather than sustainable depth.
- **NO HIRE overall.** Any round at STRONG NO HIRE, or two or more rounds at NO HIRE; a consistency check failure that suggests a story was materially reshaped between rounds rather than merely reframed; a pattern of contradiction between a strong round and a weak one that undermines confidence in the strong round's evidence.
- **STRONG NO HIRE overall.** Multiple rounds at NO HIRE or below with no round reaching STRONG HIRE; a consistency failure involving a fabricated or materially inconsistent number; visible defensiveness or evasiveness escalating across the loop rather than resolving.

## Red flags that end the round

- A number, scope claim, or rejected alternative that materially contradicts itself between two rounds where the same story is told (this is worse than a weak individual round, because it undermines every other claim made in the loop).
- Front-loading: a visibly strong round 1 followed by a collapse in seniority signals (no more unprompted tradeoffs, no more honest uncertainty, no more rejected alternatives) by round 4-5 — this reads as rehearsed material running out, not fatigue.
- Referencing an earlier round's content as a substitute for answering the current round's question ("I already went through this in the design round") — real interviewers in a real loop have not seen the other rounds and this reads as evasive regardless of intent.
- Any single round scoring STRONG NO HIRE (0-4/20), regardless of how strong the other four are — a real committee treats this as a serious, not automatically overridable, signal.
- Visible fatigue-driven defensiveness that gets worse as the loop progresses rather than the candidate self-correcting.

## Time-management failures

The specific ways a full loop goes wrong that no single round would catch:

- **Spending recovery time from a bad round complaining about it instead of resetting.** A rough coding round followed by 10 minutes of the design round spent mentally re-litigating the coding round instead of being present for the new prompt is a real, observable pattern and it compounds the damage of the first bad round into a second one.
- **Running the rounds back to back with no break**, which manufactures a fatigue effect that isn't representative of how the candidate will actually perform in a real, appropriately-spaced onsite — the debrief's fatigue-based findings are only meaningful if a real break was taken.
- **Letting the behavioral round (placed fourth deliberately) run over time because coding and design ran long**, which is exactly the compounding time-debt pattern a real onsite day produces and is worth surfacing rather than protecting against by artificially extending the day.
- **Skipping the debrief because the loop already took four hours.** The debrief is where roughly half of this module's value lives — a candidate who runs all five rounds and skips straight to "how did I do overall" without the round-by-round consistency check and level-read reasoning has wasted the harder half of the exercise.

## Cheat card

```
ORDER: Coding → Design → AI Depth (ML or GenAI) → Behavioral → HM Grill
        (deliberately: mechanical-first, STAR-discipline tested under fatigue
        fourth, closes with the person who defends the hire internally)
EACH ROUND scored on ITS OWN 20-pt rubric, independently — no score bleeds
        into the next round, and no round gets softened for being #4 or #5
VERDICT IS NOT AN AVERAGE. The operative question: does the WEAKEST round,
        alone, indicate a gap serious enough to sink the hire for THIS role?
A LEAN HIRE in the role's core skill (e.g. GenAI depth for a GenAI role)
        outweighs a STRONG HIRE somewhere less central — weight by relevance
CONTRADICTION > LOW SCORE: a strong round that contradicts a fact from a
        weak round is worse than two consistently middling rounds — it means
        re-examine the strong round's evidence, don't just average around it
LEVEL READ comes from the PATTERN across 3+ rounds, never from the single
        best round. Resist rounding up to the best data point.
CONSISTENCY CHECK: same number, same scope claim, same rejected alternative,
        every time a story recurs across rounds — any drift is a real flag
SENIORITY SIGNALS MUST PERSIST TO ROUND 5: unprompted tradeoffs, honest
        uncertainty, named rejected alternatives — if these vanish by round
        4-5, the early rounds were rehearsed material, not sustainable depth
VERDICT FORMAT (all four required): overall recommendation, the round that
        would have sunk it (name it even in a HIRE), level read + evidence,
        ONE fix (find the common thread across rounds, don't list five)
NEVER skip the debrief. Half the value of a full loop is in the cross-round
        consistency check and level read, not in the five individual scores.
```

## Sources

- `skills/tutor-mock/SKILL.md` — round definitions, scoring format, and the "full loop mode" committee-verdict directive this module implements in full (internal).
- [Amazon LPs, Google, Meta, Microsoft, Netflix, AI Startups — `curriculum/14-behavioral-principal/04-company-specific.md`](../14-behavioral-principal/04-company-specific.md) — internal, real loop-length and structure data by company (Amazon 4-5 rounds/7-8 at Principal, Google 4-6, Meta 5 at E6 plus a pre-onsite Leadership Assessment, Microsoft 4-5 plus an As Appropriate round, Netflix ~7, AI labs staged gates plus a paid work trial) — full citation list in that module, accessed 2026-07-26.
- [Learnings from conducting ~1,000 interviews at Amazon — The Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/learnings-from-conducting-1000-interviews) — accessed 2026-07-26

## Changelog
- 2026-08-01 — created
