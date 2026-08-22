---
name: tutor-debrief
description: Debrief a real interview — log every question asked, diagnose whether each miss was knowledge, structure, or nerves, queue the gaps as flashcards, and auto-promote any topic seen in two or more interviews into the sprint. Maintains mocks/PATTERNS.md, the highest-signal study list in the system. Use when the user says /tutor-debrief, "I just had an interview", "here's how it went", or reports back after a real loop.
---

# tutor-debrief

This is the skill that makes the curriculum learn. Prep → interview → debrief → the plan re-prioritises itself from **real evidence** instead of from a plan written months ago.

Run it the same day. Recall of the exact questions decays within hours, and the exact wording is the signal.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Extract, before analysing anything

Ask for, and do not analyse until you have:

- Company, role, round type, date, interviewer's role.
- **Every question, as close to verbatim as they can manage.** Push for exact wording — "how would you scale this" and "what breaks first as this scales" test different things.
- For each: what they answered, and how it landed (confident / stumbled / blank / ran out of time).
- What the interviewer pushed back on. Pushback is the highest-signal item in the whole debrief.
- Their own read: which round felt worst, and why.

If they remember only fragments, log the fragments. A partial record beats a reconstructed-and-wrong one; mark uncertain items with `?`.

## 2. Diagnose each miss by type — the types need different fixes

| Type | Looks like | Fix |
|---|---|---|
| **Knowledge** | did not know the fact or mechanism | `/tutor-deepdive`, then cards |
| **Structure** | knew it, answered in the wrong order or never landed the point | `/tutor-mock` reps, the design/communication modules |
| **Depth** | correct but shallow — no numbers, no tradeoff, no failure mode | re-read the module's cheat card, then a staff-difficulty drill |
| **Recall** | knew it once, could not retrieve under time | spaced repetition — the card was overdue |
| **Nerves** | knew it, froze | more mocks, not more content |
| **Fit** | not a gap — they wanted something the user does not do | nothing to fix. Say so. |

Misdiagnosis is expensive: reading another module does not fix a structure problem, and more mocks do not fix a knowledge gap. Be explicit about which one each miss was, and say when the evidence is ambiguous.

## 3. Write the debrief

`$ROOT/mocks/debrief-<date>-<company>-<round>.md`:

```markdown
# <Company> · <Round> · <date>
> Outcome: <passed | rejected | waiting> · Interviewer: <role>

## Questions asked
| # | Question (verbatim) | Module | How it went | Diagnosis |

## Pushback
<What the interviewer challenged, and whether the answer survived it.>

## What worked
## What failed
## The one thing
<If one thing changes before the next loop, this.>
```

## 4. Update PATTERNS.md — the auto-promotion

`$ROOT/mocks/PATTERNS.md` is the accumulated evidence across every real interview. Create it if absent:

```markdown
# Interview patterns
> Auto-maintained by /tutor-debrief. Topics asked in 2+ real interviews get promoted
> into the sprint — real evidence outranks the plan.

| Topic | Module | Asked | Companies | Record | Status |
|---|---|---|---|---|---|
| KV cache sizing | T05-inference-serving | 3 | A, B, C | 1 solid / 2 shaky | PROMOTED WE5 |
```

For each question in this debrief, match it to a module id and increment `Asked`. Match on concept, not wording — "how do you stop an agent looping forever" and "what's your stop condition" are the same topic.

**When a topic reaches 2 and the user did not answer it solidly**, promote it:

1. Add the module id to the earliest incomplete weekend in `SPRINT_WEEKENDS` in `$ROOT/app/build_data.py`.
2. If the weekend would exceed ~10.5h, the build warns — move the lowest-value existing module out rather than ignoring it.
3. Rebuild: `python app/build_data.py`
4. Set `Status` to `PROMOTED WE<n>` and tell the user exactly what moved and what it displaced.

A topic asked three times that keeps going badly is the most important thing in the curriculum. Treat it that way.

## 5. Queue the gaps as cards

Every knowledge and depth miss becomes a flashcard, so it comes back on a schedule instead of being forgotten by next weekend. Write to `$ROOT/app/data/cards/<module-id>.json` — read the file first and merge by id, using `-i1`, `-i2` suffixes for interview-sourced cards. Then:

```bash
python app/build_data.py
```

Interview-sourced cards are the highest-value cards in the deck. Tag the topic in the card so they are identifiable.

Append to `$ROOT/progress/SESSION-LOG.md`:

```
- 2026-08-01 · debrief · <Company> design · rejected · knowledge gaps: KV cache math, multi-tenant isolation · promoted T05-inference-serving to WE5
```

## 6. Report

```
DEBRIEF  <Company> · <round> · <date>

DIAGNOSIS   knowledge <n> · structure <n> · depth <n> · recall <n> · nerves <n> · fit <n>

PROMOTED    <module> → weekend <n>   (displaced: <module>)
QUEUED      <n> cards
PATTERN     <topic> now asked <n>× across <companies> — <verdict>

THE ONE THING
  <sentence>
```

## Rules

- Verbatim questions or marked uncertain. Never smooth them into what you think they meant.
- A rejection is data, not a verdict. Diagnose it; do not console. The user asked for a system that learns.
- Do not promote on a single sighting — one interviewer's hobby-horse is not a pattern. Two is the threshold, and it is deliberate.
- If the diagnosis is `fit`, say there is nothing to study. Studying the wrong gap is worse than studying nothing.
