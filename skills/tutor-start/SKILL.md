---
name: tutor-start
description: Start a study session against the AI Tutor Service curriculum. Shows the current weekend's quest sized to the hour budget, flashcards due for spaced-repetition review, weak spots from past drills and real interview debriefs, and one concrete next action. Use when the user says /tutor-start, "start studying", "what should I study", "what's my quest today", or begins a weekend session.
---

# tutor-start

Opens a session. Answers exactly one question: **what do I do in the next N hours.**

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Read state

In this order, skipping what is absent:

| Source | Gives you |
|---|---|
| `$ROOT/progress/SESSION-LOG.md` | what happened last session — the primary ledger |
| `$ROOT/progress/progress.json` | exported app state (`xp`, `modules`, `cards`, `bosses`, `streak`) if the user exported it |
| `$ROOT/CONTENT-STATUS.md` | which modules are actually written vs merely scoped |
| `$ROOT/app/data/curriculum.json` | sprint order (`sprint_week`, `sprint_order`), hours, tags, prereqs |
| `$ROOT/mocks/PATTERNS.md` | topics asked in 2+ real interviews — these outrank everything |
| `$ROOT/app/data/flashcards.json` | the card pool, for the due count |

**The app's real state lives in browser localStorage, not on disk.** `progress.json` only exists if the user exported it from the Save/Load tab. When it is missing or older than the session log, trust `SESSION-LOG.md` and say which you used. Do not silently present stale XP as current.

## 2. Pick the weekend

The current weekend is the lowest `sprint_week` that still has an incomplete module. A module counts complete only if it is both **written** (per CONTENT-STATUS.md) and **done** (per state). If a sprint module is unwritten, the quest for it is *write it* — offer `/tutor-deepdive`.

Sprint modules bypass prerequisite gating. Non-sprint modules do not: check `prereqs` before suggesting one.

## 3. Size the quest

Ask for the available hours if the user did not say. Defaults: **9h** for a weekend day, **20 minutes** for a weekday.

- **Weekend (≥4h):** weekend blocks are `3h AI depth · 2h design/principles · 2h DSA · 1.5h databases/cloud · 0.5h review`. Fill from the current weekend's sprint modules first, then the block that is furthest behind.
- **Short session (<1h):** flashcards due + one drill. Never start a 3h module in a 20-minute window.

Never propose more hours of work than the user has. Cutting the list is the job.

## 4. Overrides, in priority order

1. **A real interview is scheduled this week** → drop breadth work. Run `/tutor-company` for that company, then weekend 8 (resume defense + STAR bank), then the relevant topic. Say this explicitly.
2. **`mocks/PATTERNS.md` has a topic seen 2+ times that is not yet done** → it leads the quest, labelled `PROMOTED FROM REAL INTERVIEWS`.
3. **≥20 cards overdue** → review comes first. Recall decays between weekends; that is the whole reason the scheduler exists.
4. Otherwise: sprint order.

## 5. Output — this exact shape, nothing else

```
WEEKEND <n>  ·  <x>/<y>h done  ·  <streak> weekend streak  ·  L<level> <name>

QUEST (<hours available>h)
  1. <Module Title>            <h>h   <written|NEEDS WRITING>   → /tutor-deepdive <slug>
  2. <Module Title>            <h>h
  3. Cards: <n> due            0.5h                             → /tutor-drill review

WEAK SPOTS
  <topic> — <where it came from: drill / mock / real interview>

NEXT ACTION
  <one sentence. one command.>
```

Then stop. No preamble, no motivational text, no recap of the curriculum.

## 6. Close the loop

Append one line to `$ROOT/progress/SESSION-LOG.md` (create it with a `# Session log` heading if absent):

```
- 2026-08-01 · start · WE4 · quest: T07-context-engineering, T07-agent-memory · 14 cards due
```

Nothing else writes to this file except the tutor skills. Keep it append-only and one line per event.

## Rules

- Do not mark anything complete. Only `/tutor-progress` and the app do that.
- Do not invent XP, levels, or streaks. If state is missing, print `—` and say state was not found.
- If the user asks for a topic outside the plan, give it to them, then note in one line where it sits relative to the sprint.
