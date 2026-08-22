---
name: tutor-deepdive
description: Write one interview-grade curriculum module for the AI Tutor Service in the house format — 30-second version, lineage past/present/future, mental model, mechanics, build-from-scratch, production, tradeoffs, 10+ interview questions with follow-up traps, red flags, cheat card — plus its flashcards and drills. Use when the user says /tutor-deepdive, "write a module on X", "deep dive on X", "write weekend N", or asks for curriculum content on a topic.
---

# tutor-deepdive

Writes **one module**, properly. Thin files are worse than missing files: a green tracker full of filler is how you walk into a loop overconfident.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Read the spec first — do not skip this

1. `$ROOT/templates/MODULE-SPEC.md` — the house format, the student profile, the voice, the 10-point checklist. This is the contract.
2. At least one exemplar, as the quality bar:
   - `$ROOT/curriculum/21-architecture-principles/06-resilience-catalogue.md`
   - `$ROOT/curriculum/07-agentic-ai/01-agent-loop-from-scratch.md`

If your draft is thinner than the exemplar, it is not done.

## 2. Resolve the module

Find it in `$ROOT/app/data/curriculum.json`. You need `id` (`T07-agent-memory`), `slug`, `title`, `hours`, `tags`, `order`, and the track's `dir`.

- Match on slug or fuzzy title. If two match, ask which.
- **Not in the spec?** It has to be added to `TRACKS` in `app/build_data.py` first — hand off to `/tutor-add`, then come back. A module file with no spec line is invisible to the app.
- Already written? Say so, show the changelog, and ask: extend, rewrite, or stop.

## 3. Research before writing

`WebSearch` anything version-dependent — framework APIs, model capabilities, library defaults, cloud service behaviour, benchmark numbers. **Do not write these from memory.** Cite as `[title](url) — accessed <today>`. Prefer the primary source: the paper, the official docs, the release notes.

Also search for what is *actually asked* on this topic — interview retrospectives, Glassdoor/Blind write-ups — and prefer real reported questions to invented ones.

## 4. Write three files

**The module** → `$ROOT/curriculum/<track-dir>/<NN>-<slug>.md`, where `NN` is `order + 1`, zero-padded to 2 digits. Full house format from MODULE-SPEC.md, every section, in order. Write the 30-second version **last**.

**Flashcards** → `$ROOT/app/data/cards/<module-id>.json`

```json
{"flashcards": [
  {"id": "T07-agent-memory-c1", "topic": "Agent Memory", "q": "...", "a": "...", "module": "T07-agent-memory"}
]}
```

**Drills** → `$ROOT/app/data/drillsets/<module-id>.json`

```json
{"drills": [
  {"id": "T07-agent-memory-d1", "module": "T07-agent-memory", "q": "...", "a": "...", "difficulty": "warmup|mid|staff"}
]}
```

Roughly 12-15 cards (one per cheat-card line, atomic) and 10-12 drills spread across the three difficulties.

> **Never edit `app/data/flashcards.json`, `drills.json`, or their `.js` twins directly.** Those are aggregates. Write the per-module fragment; `build_data.py` merges by id, so an edited fragment corrects the aggregate on the next run and a stale hand-edit gets silently overwritten.

## 5. Reindex

```bash
python app/build_data.py
```

Confirm the output shows `merged fragments: flashcards +N` and that `written=` went up by one. **The app cannot see the module until this runs.**

If a matching lab should exist, name it in the module header and offer `/tutor-lab <slug>`.

## 6. Self-check before reporting done

Fail any of 1-7 and the module goes back:

1. 30-second version is genuinely 3-5 sentences, no hedging.
2. Lineage has all three parts, and names the **specific pain** that killed the old approach.
3. **At least 5 concrete numbers** — latencies, defaults, thresholds, complexities, costs.
4. At least one **named failure mode with its observable symptom** (what shows up in a log or trace).
5. **10+ interview questions, every one with a follow-up trap.**
6. A real "when NOT to use this", not a token paragraph.
7. Sources cited with access dates for anything version-dependent.
8. Code runs, or is marked `# untested sketch`.
9. No marketing voice. If a tool is usually the wrong choice, say so.
10. Cheat card is one screen, and every line is atomic enough to become a flashcard.

## Writing a whole weekend

"Write weekend N" means the 3-4 modules in `SPRINT_WEEKENDS[N]` in `build_data.py`. Write them one at a time in the listed order, each fully to spec, reindexing once at the end. Do not parallelise into thin drafts.

## Report

File paths written, flashcard count, drill count, and **any claim you could not verify with a source**. Do not summarise the content back — the point is that it is on disk.
