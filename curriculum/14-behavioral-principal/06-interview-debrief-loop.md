# Interview Debrief Loop: Evidence, Gaps, Promotion, Repeat

> **Track:** T14 Behavioral & Principal · **Time:** 2h · **Prereqs:** T14-star-bank · **Updated:** 2026-10-11
> **Module id:** `T14-interview-debrief-loop` · **Tags:** behavioral, critical

## The 30-second version
An interview debrief is an evidence pipeline, not a feelings journal. Capture the exact question, the pushback, the answer you gave, and classify the miss as knowledge, structure, evidence, or nerves; then convert the smallest fix into a card, drill, story edit, or lab. Repeated topics are stronger evidence than one awkward question, so a topic asked twice should be promoted and scheduled before broad curriculum work. The loop is complete only when the fix is rehearsed and a later interview tests it.

## Why this gets asked
The prep packs in this repository repeatedly identify gaps in evaluation, cost, production ownership, resume evidence, and leadership examples. Without a debrief loop, those observations remain anecdotes and the same miss repeats. The interviewer-facing skill is not merely reflection; it is turning an unexpected follow-up into a durable improvement.

## Lineage: past -> present -> future
**What came before.** Candidates wrote generic notes such as “need to improve system design.” The pain was no retrieval key: a broad topic did not identify the exact question, missing number, or next practice action. STAR and structured interviews improved answer shape, but not the feedback loop after the interview.

**Where it stands now.** A useful debrief records question, round, company, pushback, answer, evidence status, miss type, linked module, and next action. The repository's `/tutor-debrief` process appends records and promotes topics seen in two or more real interviews into `mocks/PATTERNS.md`. OPM's official structured-interview guidance describes predetermined questions and common rating standards; that supports comparing evidence against a competency rather than grading mood. The live disagreement is whether every miss needs a new module. Usually it needs a narrower card, a spoken drill, or a confirmed number, not more reading.

**Where it is heading.** High confidence: interview prep will become a closed loop from job description to interview evidence to curriculum priority. Medium confidence: transcripts and structured notes will automate candidate-side tagging. Speculative: an AI debriefer can reliably judge credibility without the candidate verifying the transcript; sensitive claims and personal metrics still require human ownership.

## Mental model
```text
question -> answer -> pushback -> diagnosis -> smallest artifact -> rehearsal
    ^                                                        |
    +-------------------- next interview evidence <----------+
```
The unit of progress is not “studied behavioral.” It is “answered the same follow-up with evidence under time pressure.”

## How it actually works
Record the question nearly verbatim. Preserve pushback because it reveals the interviewer's uncertainty: “what did you personally write?”, “what was the denominator?”, and “what would you cut?” are different gaps even when attached to the same project.

Classify one primary miss:
- **Knowledge:** could not explain the mechanism.
- **Structure:** knew it but wandered, omitted result, or never answered the question.
- **Evidence:** knew the story but lacked a baseline, denominator, ownership boundary, or measured result.
- **Nerves/retrieval:** had the material but could not retrieve it in roughly 5 seconds.

Assign a next action with a completion test. “Read more” is not a completion test. “Answer Q7 in 90 seconds, name the rejected alternative, and include the confirmed baseline” is.

Use promotion rules: one miss creates a card or drill; two distinct interviews on the same concept create a pattern row and priority; three misses on the same story justify rewriting the story or collecting missing evidence. Keep a 24-hour capture window, a 7-day fix window, and a later re-test target. These are workflow defaults, not claims about hiring probability.

## Build it from scratch
Use a Markdown or JSON record with `date`, `company`, `round`, `question`, `pushback`, `answer`, `miss_type`, `module`, `evidence_needed`, and `next_action`. A simple promotion function counts normalized topic ids and emits a queue sorted by count and severity.

```python
def diagnose(answer, pushback, evidence):
    if evidence and not any(marker in answer for marker in evidence):
        return "evidence"
    if pushback and answer.strip() == "":
        return "retrieval"
    return "knowledge_or_structure_review"
```

## How it's done in production
The repository's `mocks/PATTERNS.md` is the durable pattern ledger. Job-specific packs under `mocks/company/inbox/` provide demand evidence, while the STAR bank provides personal source material and `[CONFIRM]` markers. A production-grade loop keeps the raw note, a sanitized summary, links to artifacts, and a clear distinction between observed interviewer behavior and the candidate's interpretation.

| Symptom | Cause | Fix |
|---|---|---|
| Same follow-up is missed repeatedly | Debrief was descriptive, not actionable | Create a timed drill with a pass condition |
| Every miss becomes a new module | No smallest-fix rule | Prefer card, drill, evidence confirmation, or story edit |
| Pattern list becomes noisy | Topics are matched by wording | Normalize to concepts and require repeated evidence |
| Story sounds stronger but remains unconvincing | Ownership or denominator is missing | Add personal contribution, baseline, method, and limit |
| Candidate overfits one company's rubric | Company-specific notes replace fundamentals | Keep universal competency tags plus company overlay |
| Debrief itself invents metrics | Generated prep text is treated as fact | Mark corpus claims and `[CONFIRM]` items explicitly |

## Tradeoffs & when NOT to use it
- Do not write a 20-page postmortem for a routine screen; capture the question and next action while memory is fresh.
- Do not promote a topic after one ambiguous question; one interviewer may have used different wording for the same concern.
- Do not let an AI summary replace the raw note, especially for personal ownership and exact numbers.
- Do not turn every nervous miss into a knowledge module. Practice retrieval and answer shape first.
- Do not expose confidential interview content in a shared corpus; sanitize company and customer data.

## Interview questions
### Q1 - What makes a useful interview debrief?
**Testing:** Feedback discipline.
**Answer:** Exact question, pushback, answer, diagnosis, evidence gap, linked topic, and a measurable next action. A score without the question and follow-up cannot guide practice.
**Follow-up trap:** *What if you remember only the feeling?* Write what is known, label the rest as inference, and do not fabricate the question.

### Q2 - How do you classify knowledge versus structure?
**Testing:** Self-diagnosis.
**Answer:** If the candidate cannot explain the mechanism even with time, it is knowledge. If they can explain it in writing but failed to answer directly under time, it is structure or retrieval. Use a timed re-answer to distinguish them.
**Follow-up trap:** *What if both failed?* Fix the smallest structural blocker first, then verify mechanism in a written or whiteboard explanation.

### Q3 - Why is pushback more valuable than the original question?
**Testing:** Signal extraction.
**Answer:** Pushback reveals what the interviewer did not believe or could not calibrate: ownership, denominator, mechanism, or tradeoff. It tells you which hidden requirement the first answer failed.
**Follow-up trap:** *Is pushback always a negative signal?* No. Strong answers also receive pushback to test depth; record it without assuming the verdict.

### Q4 - When should a topic be promoted?
**Testing:** Prioritization.
**Answer:** One miss gets a targeted artifact; the same concept in two real interviews becomes a pattern and priority; repeated failure on one story triggers evidence collection or rewrite. Promotion is evidence-weighted, not emotion-weighted.
**Follow-up trap:** *What if a rare topic is safety-critical?* Risk can override frequency; label it high severity and practice it despite one occurrence.

### Q5 - How do you repair a missing resume number?
**Testing:** Integrity.
**Answer:** Identify metric, baseline, comparison, window, and owner of the measurement. Retrieve the source or mark `[CONFIRM]`; never infer a denominator from a headline percentage.
**Follow-up trap:** *What do you say if it was never measured?* Say so plainly, state the proxy used, and name what you would instrument now.

### Q6 - How do you avoid overfitting to one company?
**Testing:** Transfer.
**Answer:** Store a universal concept such as ownership, evidence, or cost tradeoff, then attach company-specific wording as an overlay. Rehearse the mechanism and story, not the company's exact script.
**Follow-up trap:** *Why keep company overlays at all?* Rubrics and vocabulary differ; the underlying evidence remains portable.

### Q7 - What is a good next action?
**Testing:** Execution.
**Answer:** It has an artifact and pass condition: “record a 90-second answer to the ETL question, include the bottleneck and cost impact, then grade against three anchors.” “Study ETL” is not actionable.
**Follow-up trap:** *How do you know the action worked?* A later timed drill or real interview must test the same follow-up.

### Q8 - How do you use generated job-prep packs safely?
**Testing:** Source hygiene.
**Answer:** Treat JD text and generated questions as demand evidence, not personal experience. Link internal corpus claims, preserve `[CONFIRM]` markers, and verify external current facts against primary sources.
**Follow-up trap:** *What if the pack contains a confident but wrong answer?* Mark it unverified, replace it with source-backed mechanics, and do not rehearse it as fact.

### Q9 - How do you handle nerves separately from knowledge?
**Testing:** Coaching precision.
**Answer:** Compare untimed written, 90-second spoken, and pressure drill performance. If written is correct and spoken retrieval fails, use story index cards, a five-second retrieval cue, and repeated timed practice.
**Follow-up trap:** *Can more content solve nerves?* Usually not; more content can increase retrieval load.

### Q10 - What would you automate?
**Testing:** Principal judgment.
**Answer:** Normalize tags, count repeated concepts, create due cards, and link evidence. Keep human review for diagnosis, confidentiality, personal ownership, and final story claims.
**Follow-up trap:** *Why not let the model assign the score?* It can propose a label, but the candidate owns whether the answer and metric are true.

## Red flags that fail you
- “I need to improve communication” with no question or next action.
- Treating generated prep material as personal evidence.
- Inventing a missing number to make a STAR result sound complete.
- Promoting every one-off question into a new module.
- Keeping only a polished summary and losing the interviewer's pushback.

## Cheat card
```text
Capture: exact question, pushback, answer, round, company, date.
Diagnose one primary miss: knowledge, structure, evidence, retrieval/nerves.
Pushback identifies the hidden requirement the answer missed.
One miss -> card/drill; two interviews -> promote pattern; three -> rewrite/evidence.
Every next action needs an artifact and a pass condition.
Numbers require metric, baseline, comparison, window, and denominator.
Unknown personal facts stay [CONFIRM], never become invented evidence.
Job-prep packs show demand; STAR/resume artifacts show personal truth.
Use written vs timed spoken vs pressure performance to separate nerves.
Re-test the same follow-up in a later drill or interview.
Keep raw notes and sanitized summaries separate.
``` 

## Operating numbers in practice
- Capture the raw note within `24` hours while question wording and pushback are still available.
- Give the first repair a `7`-day completion window.
- Use a `5`-second retrieval target for the story index.
- Rehearse the repaired answer in `60` or `90` seconds, depending on the round.
- Keep `4` primary miss labels: knowledge, structure, evidence, and retrieval/nerves.
- Require at least `2` distinct real interviews before promoting a concept as a recurring pattern.
- Escalate to story rewrite or evidence collection after `3` misses on the same story.
- Store at least `10` fields in a durable record: date, company, round, question, pushback, answer, diagnosis, evidence, module, and next action.
- Compare at least `3` modes when diagnosing nerves: untimed writing, timed speaking, and hostile follow-up.
- Retest after `7` days or at the next interview; a polished note without a retest is not closure.
- A `90-second` answer should contain roughly `10-15` seconds of context, `45-60` seconds of decisions, and `15-20` seconds of result and tradeoff.
- If a mock has `5` questions and the same ownership gap appears in `2`, promote it; after `3`, rewrite the story or collect evidence.

## Sources
- [OPM Structured Interviews](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/) - official structured-question and common-rating guidance; accessed 2026-10-11
- [Tutor debrief workflow](../../skills/tutor-debrief/SKILL.md) - internal process for evidence capture and promotion; accessed 2026-10-11
- [Interview patterns ledger](../../mocks/PATTERNS.md) - internal evidence ledger; accessed 2026-10-11
- [30-Story STAR Bank](01-star-bank.md) - internal personal evidence and confirmation markers; accessed 2026-10-11
- [Nexperia job prep pack](../../mocks/company/inbox/jobspy_079ec3cf8fc417.md) - internal job-hunt demand evidence; accessed 2026-10-11

## Changelog
- 2026-10-11 - created

## Operating numbers to carry into the loop
- Capture the raw note within `24` hours while question wording and pushback are still available.
- Give the first repair a `7`-day completion window.
- Use a `5`-second retrieval target for the story index.
- Rehearse the repaired answer in `60` or `90` seconds, depending on the round.
- Keep `4` primary miss labels: knowledge, structure, evidence, and retrieval/nerves.
- Require at least `2` distinct real interviews before promoting a concept as a recurring pattern.
- Escalate to story rewrite or evidence collection after `3` misses on the same story.
- Store at least `10` fields in a durable record: date, company, round, question, pushback, answer, diagnosis, evidence, module, and next action.
- Compare at least `3` modes when diagnosing nerves: untimed writing, timed speaking, and hostile follow-up.
- Retest after `7` days or at the next interview; a polished note without a retest is not closure.

Use a concrete record example when practicing: `1` question, `2` follow-ups, `1` primary diagnosis, `1` evidence gap, and `1` next action. A `90-second` answer should contain roughly `10-15` seconds of context, `45-60` seconds of decisions, and `15-20` seconds of result and tradeoff. If a mock has `5` questions and the same ownership gap appears in `2`, promote it to the pattern queue; if it appears in `3`, rewrite the story or collect the missing source evidence. Keep the active repair queue below `10` items so the next session can close work instead of creating another backlog. A useful weekly review has `3` outputs: closed fixes, still-due drills, and new patterns.

## Lineage detail: from memory to an evidence loop
**What came before.** Candidates often kept a single document called “interview notes” and wrote 1 to 3 paragraphs after a call. The pain was that it mixed facts, emotion, and interpretation. A note saying “system design went badly” cannot tell you whether the failure was missing capacity math, weak structure, lack of ownership evidence, or retrieval under pressure.

**Where it stands now.** A useful debrief has at least 10 fields: date, company, round, question, pushback, answer, miss type, evidence needed, linked module, and next action. Add a confidence field and preserve the raw note separately from the sanitized pattern ledger. The repository uses a two-interview promotion rule for recurring topics, a 24-hour capture window, and a 7-day fix window as workflow defaults. These are not hiring statistics; they are operating constraints that keep the queue small enough to use.

**Where it's heading.** High confidence: job-specific demand, real interview questions, and candidate evidence will form one searchable loop. Medium confidence: transcript tools will normalize topics and detect repeated pushback. Low confidence: an automated system can judge personal credibility, ownership, or confidential company detail without human review. Keep the candidate as the final authority for all personal facts.

## Debrief scoring and prioritization
Rank a miss with three independent dimensions: frequency, severity, and fix cost. A topic asked twice has frequency `2`; a safety or ownership miss may have severity `3`; a missing number may have fix cost `1` if the source exists, while a missing measurement may have cost `3`. A simple queue priority can be `frequency x severity / fix_cost`, but the formula is only a sorting aid. A rare security question can outrank a common low-risk topic.

Use a 4-step verification loop. First, write the answer untimed. Second, speak it in `60` or `90` seconds. Third, add one hostile follow-up and answer it within `5` seconds of retrieval. Fourth, re-run the same drill after `7` days or in the next interview. If the answer is correct untimed but fails under pressure, create a retrieval card rather than a new module.

For evidence misses, capture the metric definition, baseline, comparison, window, denominator, and personal contribution. If one item is unknown, keep `[CONFIRM]`. Never turn a generated job-prep answer into personal history. A pack can tell you that employers ask about vLLM, cost, MCP, and evaluation; only the resume, project records, or your own verified memory can tell you what you personally did.

## Additional interview drills
### Q11 - You remember the interview only as “bad.” What do you write?
**Testing:** Evidence discipline.
**Answer:** Separate known facts from inference. Record the round, approximate question, exact pushback if remembered, answer shape, and the next observable test. Mark uncertainty instead of inventing a transcript.
**Follow-up trap:** *What if the exact question is gone?* Record the closest faithful paraphrase and label it paraphrase; do not fabricate precision.

### Q12 - When does a miss become a module?
**Testing:** Scope control.
**Answer:** Usually it does not. One miss becomes a card, drill, confirmed number, or story edit. Repeated misses across two interviews or a mechanism that blocks multiple roles may justify a module. A high-severity safety gap can override frequency.
**Follow-up trap:** *What if you enjoy the topic?* Enjoyment is not evidence of priority; the queue is driven by role demand and observed failure.

### Q13 - How do you distinguish evidence from knowledge?
**Testing:** Diagnosis.
**Answer:** Ask the mechanism in writing, then ask for the same answer with personal scope and numbers. If the mechanism is correct but “what did you personally write?” fails, it is evidence. If the mechanism fails both times, it is knowledge.
**Follow-up trap:** *What if both fail under time pressure only?* It is retrieval/structure; use a timed drill before reading more.

### Q14 - How do you protect confidential interview information?
**Testing:** Judgment.
**Answer:** Keep raw notes local, remove customer and interviewer identifiers from durable patterns, and store only the generalized competency and question shape. Do not paste confidential prompts or internal architecture into a shared corpus.
**Follow-up trap:** *Can the model summarize it?* It can propose a sanitized summary, but a human must review what leaves the private note.

### Q15 - What proves the debrief loop worked?
**Testing:** Closed-loop measurement.
**Answer:** The same follow-up is answered with the required structure, evidence, and time limit in a later drill or interview. A prettier note or higher self-confidence is not enough.
**Follow-up trap:** *What if no later interview arrives?* Use a mock with the same question and a blind evaluator, then keep the item due until a real retest occurs.
