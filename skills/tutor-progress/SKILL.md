---
name: tutor-progress
description: Give an honest read on where the user actually stands in the AI Tutor Service curriculum — sprint burn-down, written vs scoped modules, card retention, mock scores, interview-debrief patterns — and name the single highest-leverage next thing. Use when the user says /tutor-progress, "where am I", "how am I doing", "am I ready", or asks whether they are on track.
---

# tutor-progress

The honest version. Optimism here costs interviews, so the bar is: **would this read the same if an interviewer wrote it?**

**Repo root** (`$ROOT`): `C:\Users\medic\OneDrive\Documents\ai-tutor-service`

## 1. Gather

```bash
python app/build_data.py
```

Run this first — `CONTENT-STATUS.md` is generated and is stale the moment a module lands. Then read:

- `$ROOT/CONTENT-STATUS.md` — written vs scoped, per track and per sprint weekend
- `$ROOT/app/data/curriculum.json` — sprint order, hours, totals
- `$ROOT/progress/progress.json` and `$ROOT/progress/SESSION-LOG.md` — completion, XP, streak, card state
- `$ROOT/mocks/*.md` — mock transcripts and scores
- `$ROOT/mocks/PATTERNS.md` — what real interviews actually asked

## 2. Separate the three numbers that people conflate

State all three. They are usually very different, and the gap between them is the finding.

| Number | Means |
|---|---|
| **Scoped** | exists as a line in `build_data.py`. Costs nothing. Means nothing. |
| **Written** | the `.md` exists and passed the format bar. |
| **Learned** | completed in state, cards not overdue, and defensible in a mock. |

"36% written" and "36% ready" are not the same claim. Never let the report imply they are.

## 3. Card retention is the leading indicator

From `progress.json` `cards`: count overdue, and compute the share of cards with `lapses >= 2`. A weekend-only cadence forgets; a growing lapse pile means the last three weekends did not stick and more new modules will not help. Say that plainly when it is true.

## 4. Readiness call

Answer the question the user is actually asking. Give a per-round verdict, with the evidence:

```
READINESS
  Agentic / AI depth    ████████░░  strong — W1-W4 done, 2 mocks passed
  System design         █████░░░░░  thin — W6 written, never practiced live
  DSA                   ███░░░░░░░  at risk — 30 patterns written, 0 problems solved
  Behavioral / resume   ██░░░░░░░░  WEAKEST — W8 written, no STAR run out loud
```

Base each bar on completion **and** evidence of practice. A written module with no drill, no lab and no mock is not a strong bar, however good the file is.

## 5. Name the gaps that are structural, not just incomplete

Check for and report these explicitly, because they will not surface from the percentages:

- `app/data/problems.json` empty → the DSA track has no problems to practice against.
- `labs/` with one lab → theory written, nothing built.
- `clouds/*/services` empty → the cloud atlases are scaffolding only.
- Sprint weekend written but zero mocks logged → knowledge untested under time pressure.

## 6. Output

```
SPRINT      <n>/32 modules · <x>/<y>h · weekend <w> of 10
LIBRARY     <n>/401 written (<pct>%) · <n> tracks with zero content
RETENTION   <n> cards due · <n> lapsed 2+ times
EVIDENCE    <n> labs · <n> mocks · <n> real interviews debriefed

READINESS
  <the bars>

THE HONEST READ
  <2-4 sentences. The one thing that is actually wrong.>

DO THIS NEXT
  <one action, one command>
```

## Rules

- Round down. Never present scoped as written.
- If evidence is missing, say "no evidence" rather than assuming the best case.
- One next action. A list of five is how nothing gets done.
- Do not restate the curriculum back to the user. They wrote it.
