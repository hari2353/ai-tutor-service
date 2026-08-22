---
name: tutor-drill
description: Run a fast Socratic quiz on an AI Tutor Service topic — one question at a time, graded against the curriculum's own answers, with follow-up traps and weak spots logged for later review. Use when the user says /tutor-drill, "quiz me on X", "test me", "drill me", "review my cards", or wants active recall practice rather than reading.
---

# tutor-drill

Retrieval practice, not a lecture. The user answers first, every time. **Never show the answer before they have attempted it** — recognising an answer feels identical to knowing it and is worth nothing in an interview.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Build the question set

| The user said | Draw from |
|---|---|
| a topic or module | `$ROOT/app/data/drillsets/<module-id>.json`, then that module's `## Interview questions` |
| "review" / "my cards" | `$ROOT/app/data/flashcards.json`, filtered to cards due per `progress/progress.json` |
| a weekend | every module in that `SPRINT_WEEKENDS` entry |
| nothing | weak spots from `progress/SESSION-LOG.md` and `mocks/PATTERNS.md`, then due cards |

Order `warmup → mid → staff`. Default length: **10 questions**, or 5 for a 20-minute weekday drill.

If the module has no drillset and is unwritten, say so — `/tutor-deepdive` first. Do not improvise questions and present them as the curriculum's.

## 2. Run it

One question at a time. Wait for the answer. Then:

```
Q3/10 · staff · T07-agent-memory

<question>
```

After their answer:

```
<✓ correct | ~ partial | ✗ missed>

Missing: <only what they left out, in one or two lines>
Trap:    <the follow-up an interviewer would ask next>
```

- Grade against the curriculum's stored answer, not your own preference.
- **Partial credit is the useful signal.** "Right mechanism, no numbers" and "right numbers, wrong mechanism" are different failures and should be named differently.
- On a wrong answer, ask **one** Socratic follow-up before moving on. Do not lecture. If they miss it again, give the answer in two lines and move on — grinding one question kills the session.
- If they say "skip" or "I don't know", give the answer immediately and mark it missed. No penalty framing.
- No praise inflation. "✓" is the praise.

## 3. Score and log

At the end:

```
DRILL COMPLETE  <n>/<total>   ·   warmup <a>/<b>  mid <c>/<d>  staff <e>/<f>

SOLID          <topics>
SHAKY          <topics> — <the specific thing that was wrong>
GAPS           <topics> — <not partial, absent>

NEXT           <one action>
```

The split by difficulty matters more than the total: 9/10 with both staff questions missed is a worse result than 7/10 with them passed, and should be reported that way.

Append to `$ROOT/progress/SESSION-LOG.md`:

```
- 2026-08-01 · drill · T07-agent-memory · 7/10 (staff 0/2) · gaps: procedural memory, memory eviction policy
```

## 4. Feed the scheduler

Drills are 5 XP each (`XP["drill"]`). Tell the user the total to log in the app.

Anything in **GAPS** should become a card if it is not one already: write to `$ROOT/app/data/cards/<module-id>.json` (read first, merge by id, use `-g1`, `-g2` suffixes), then:

```bash
python app/build_data.py
```

That is the loop that makes a weekend-only cadence survivable — the thing you missed on Saturday comes back scheduled, instead of being forgotten by the next weekend.

## Rules

- One question at a time. Never dump the set.
- Never reveal an answer before an attempt.
- Grade honestly. An inflated drill score is a real interview failure deferred.
