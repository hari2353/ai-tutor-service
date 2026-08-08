# Skills

The twelve `/tutor-*` skills. **This directory is the source of truth** — it lives in the repo, so the skills are versioned alongside the content they operate on.

## Install

```powershell
powershell -ExecutionPolicy Bypass -File skills\install.ps1
```

Copies each `SKILL.md` to `~/.claude/skills/<name>/SKILL.md`, which makes them available in **any** session, not only when the working directory is this repo. Re-run after editing a skill — the account copy does not track the repo.

## The twelve

| Skill | Reads | Writes |
|---|---|---|
| `/tutor-start` | curriculum.json, CONTENT-STATUS, SESSION-LOG, PATTERNS | SESSION-LOG |
| `/tutor-deepdive` | MODULE-SPEC, curriculum.json, web | `curriculum/`, `cards/`, `drillsets/` |
| `/tutor-lab` | the exemplar lab, the module | `labs/<lang>/` |
| `/tutor-drill` | drillsets, flashcards, modules | SESSION-LOG, `cards/` |
| `/tutor-mock` | modules, PATTERNS, company packs | `mocks/`, SESSION-LOG |
| `/tutor-review` | the code, the lab spec | nothing |
| `/tutor-cheatsheet` | written modules | `cheatsheets/`, `cards/` |
| `/tutor-progress` | everything | nothing (runs the build) |
| `/tutor-update` | watermarks, release feeds | `clouds/*/changelog/`, module changelogs |
| `/tutor-add` | build_data.py | `build_data.py`, `app/data/` |
| `/tutor-company` | the JD, web, resume modules | `mocks/company/` |
| `/tutor-debrief` | the user's account of a real interview | `mocks/`, PATTERNS, `build_data.py`, `cards/` |

## Two invariants every skill obeys

**Fragments, never aggregates.** Content is written to `app/data/cards/<module-id>.json` and `app/data/drillsets/<module-id>.json`, one file per module. Nothing hand-edits `flashcards.json`, `drills.json`, or their `.js` twins — `build_data.py` merges fragments by id and regenerates those, so a hand-edit is overwritten and a `.json`/`.js` mismatch is invisible until the app misbehaves.

**Anything that adds content ends with `python app/build_data.py`.** The app renders from generated files. Content that is not indexed does not exist as far as the app is concerned.

## State

The app's real state is browser `localStorage`; `progress/progress.json` exists only when exported from the Save/Load tab. So the skills keep their own ledger at `progress/SESSION-LOG.md` — append-only, one line per event — which is what lets `/tutor-start` and `/tutor-progress` work without the user remembering to export.
