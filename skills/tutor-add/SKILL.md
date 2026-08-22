---
name: tutor-add
description: Add new content to the AI Tutor Service and reindex the app — a new module line, a new track, flashcards, drills, or LeetCode problems — by editing the TRACKS spec in app/build_data.py and regenerating app/data. Use when the user says /tutor-add, "add a module on X", "add a track for X", "add these problems", or wants new content to show up in the tutor app.
---

# tutor-add

The app renders from `app/data/*.js`, which is generated. **Nothing appears in the app until `build_data.py` runs.** This skill is the only correct way to change the index.

**Repo root** (`$ROOT`): `C:\Users\medic\OneDrive\Documents\ai-tutor-service`

## The source of truth

`$ROOT/app/build_data.py` holds the spec. Everything in `app/data/` is output.

| To add | Edit | Then |
|---|---|---|
| a module | one line in the track's `modules` list in `TRACKS` | rebuild |
| a track | a `dict(...)` in `TRACKS` + create `curriculum/<dir>/` | rebuild |
| a sprint slot | the weekend's list in `SPRINT_WEEKENDS` | rebuild |
| flashcards | `app/data/cards/<module-id>.json` | rebuild |
| drills | `app/data/drillsets/<module-id>.json` | rebuild |
| problems | `app/data/problemsets/<set>.json` | rebuild |

## Module line format

```python
"slug | Human Title | hours | tag1,tag2"
```

- `slug` is kebab-case and must be unique inside the track. The module id becomes `<TrackId>-<slug>` — that id is the join key for cards, drills, the sprint list and the curriculum file, so **do not rename a slug after content exists** without renaming the fragments too.
- `hours` is a float; be honest, the quest generator budgets on it.
- Tags are free-form. `critical` marks must-know. `sprint` is added automatically — never write it by hand.
- Position in the list sets `order`, which sets the module file's `NN` prefix. Appending is safe; inserting in the middle renumbers everything after it.

## Track dict format

```python
dict(id="T32", dir="32-new-track", title="New Track", icon="🧪", phase="B", prereqs=[], modules=[
    "first-module | First Module | 2 | core",
]),
```

`id` must be unique. `dir` must match a real directory under `curriculum/` — create it. `phase` is `A` (core, needed for loops now) or `B` (mastery). Cloud tracks go in `CLOUDS`, not `TRACKS`, and their `dir` is under `clouds/`.

## Adding to the sprint

Only for something that genuinely decides an interview outcome. Add the **full module id** to the right weekend in `SPRINT_WEEKENDS`:

```python
4: ["T07-context-engineering", "T07-agent-memory", "T07-multi-agent-topologies"],
```

The build hard-fails on an unknown id (`SPRINT references unknown module ids`) — that check exists because a typo silently drops a module from the sprint and you would not notice for weeks. It also warns if a weekend exceeds 10.5h; a weekend is ~9h, so take that warning seriously rather than shipping an impossible plan.

## Problems

`app/data/problems.json` is currently empty, so the app's Problems tab renders nothing. Add sets as fragments under `app/data/problemsets/`:

```json
{"problems": [
  {"id": "lc-121", "title": "Best Time to Buy and Sell Stock", "url": "https://leetcode.com/problems/...",
   "difficulty": "easy", "pattern": "T02-p02-sliding-window", "module": "T02-p02-sliding-window"}
]}
```

Tag every problem to the DSA pattern module it drills. An untagged problem is just a link.

## Rebuild, always

```bash
python app/build_data.py
```

Expected: `OK tracks=.. modules=.. hours=.. written=..` plus a `merged fragments:` line when fragments changed. A `SystemExit` means a bad id or malformed JSON — fix it, do not work around it.

Then verify nothing broke:

```bash
node app/tests/dom.test.js "C:\Users\medic\OneDrive\Documents\ai-tutor-service"
```

## Rules

- **Never hand-edit `app/data/*.json` or `*.js`.** They are regenerated; your edit will vanish, and the `.js` twin will disagree with the `.json` until it does.
- Adding a spec line does not write the module. It creates an empty slot that shows as unwritten in `CONTENT-STATUS.md`. Follow with `/tutor-deepdive`.
- Report what changed: modules before/after, hours before/after, and whether the sprint moved.
