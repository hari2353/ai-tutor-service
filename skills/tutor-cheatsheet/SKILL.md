---
name: tutor-cheatsheet
description: Produce a one-page revision sheet for the morning of an interview — bare facts, numbers, thresholds, decision rules and the three sentences to open with — plus matching flashcards, from written AI Tutor Service modules. Use when the user says /tutor-cheatsheet, "make me a cheat sheet on X", "one-pager for X", "I'm interviewing tomorrow, give me X in one page", or wants condensed revision material.
---

# tutor-cheatsheet

This gets read on a phone, twenty minutes before a call. Optimise for **recall under stress**, not comprehension. Anything that needs to be read twice does not belong.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Source it from what is written

Find the relevant modules in `$ROOT/curriculum/` (check `CONTENT-STATUS.md` for what exists). A cheat sheet is a **compression of written material**, not new content.

Pull primarily from each module's `## Cheat card` section — that section was written to be atomic for exactly this reason — then the numbers from `## How it actually works` and the decision rules from `## Tradeoffs & when NOT to use it`.

**If the module is not written**, say so and offer `/tutor-deepdive` first. Do not invent a cheat sheet from general knowledge and present it as curriculum-derived — the numbers are the whole value, and unverified numbers are worse than none.

Scope can be one module, a sprint weekend, or a track. A weekend is the sweet spot.

## 2. Write to

`$ROOT/cheatsheets/<scope>.md` — e.g. `we03-retrieval.md`, `T07-agentic-ai.md`, `langgraph-durability.md`.

## 3. Format

```markdown
# <Scope> — cheat sheet
> Sources: <module ids> · generated <date>

## Say this first
<The 3 sentences that answer the cold-open question. Lifted from the module's
30-second version. Verbatim-speakable — read it aloud and it should sound normal.>

## Numbers
| What | Value | Why it matters |
|---|---|---|
<8-15 rows. Defaults, thresholds, latencies, complexities, costs. No adjectives.>

## Decision rules
- **Use X when** <condition>. **Use Y when** <condition>. **Neither when** <condition>.

## The mechanism, in one diagram
<ASCII. One screen.>

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|

## Traps
- <question that catches people> → <the survival line>

## Do not say
- <the phrase that ends the interview, and what to say instead>
```

Hard limits: **one page** (~60 lines rendered). Tables over prose. No section that is only prose.

If it does not fit, the scope is too wide — split it, do not shrink the font.

## 4. Flashcards

Every row in **Numbers** and every rule in **Decision rules** becomes a card. Write to `$ROOT/app/data/cards/<module-id>.json`, merging with what is already there **by id** (read the file first; do not overwrite other cards for that module). Use ids that will not collide: `<module-id>-cs1`, `-cs2`, …

Then:

```bash
python app/build_data.py
```

Confirm the `merged fragments: flashcards +N` line.

## 5. The morning-of variant

If the user says they are interviewing tomorrow, also produce a **60-second version** at the top: the five things they will actually be asked, and one line each. Then tell them to stop studying — cramming new material the night before displaces what is already consolidated. Say it once, plainly.

## Rules

- Every number traceable to a written module. If you cannot trace it, cut it.
- No explanation. They already learned it; this is the index, not the book.
- Never use this to paper over an unwritten module.
