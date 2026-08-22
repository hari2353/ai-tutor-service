# HANDOFF — resume point

> Last updated 2026-08-01. Regenerate the live numbers with `python app/build_data.py`
> and `python app/tests/review_gate.py`; this file is the plan, those are the truth.

## State

| | |
|---|---|
| Written | **236 / 425** modules |
| Review gate | 236 pass · 0 fail |
| App tests | dom 20/20 · sm2 10/10 |
| Flashcards / drills | ~2,800 / ~2,300 |
| Git | repo initialised on `main`, **0 commits**, 451+ files staged |
| GitHub | not pushed — blocked on `gh auth login` (user action; never run by the agent) |

Complete tracks: T02 DSA · T06 RAG · T15 Interview Simulator · T18 Data Engineering ·
T29 Networking · T30 Auth · C-AWS Atlas.

## What was done this session

- **The 12 `/tutor-*` skills** now exist in `skills/`, installed to `~/.claude/skills` by
  `skills/install.ps1`. They did not exist before; README and PLAN both claimed they did.
- **`build_data.py` never merged the fragments.** `app/data/cards/` and `drillsets/` were
  written by module authors and silently ignored. Merge is now by id and idempotent.
  Recovered 137 flashcards and 105 drills across 12 modules that were invisible to the app.
- **`app/tests/run.sh` reported ALL GREEN while testing nothing** — the lab step discarded
  stderr and piped to `tail`, so a missing pytest exited 0. Fixed, plus python3/python/py probing.
- **`review_gate.py`** gained a BOSS profile (T15 rounds have no lineage by design) and now
  counts `**Qn**` as well as `### Qn` questions.
- Fixed the `F:\` drive paths in `README.md` and `templates/MODULE-SPEC.md`, which pointed
  every module author at a nonexistent path.

## Resume here — 26 Phase A modules

One agent per row. Sonnet writes, Opus runs the review gate after each lands.

| Batch | Track | Modules |
|---|---|---|
| A | T07 | risk-taxonomy, harness-evals |
| B | T10 | ml-designs, principal-layer, tech-selection, poc-to-prod, case-studies |
| C | T08 | ragas-deepeval, otel-genai, obs-platforms, classic-obs |
| D | T28 | mcp-authoring, ai-arch-review, agent-skills-arch, harness-comparison, when-not-to |
| E | mixed | T17 vector-db-compare + sql-mastery, T05 multimodal, T21 anti-patterns |
| F | mixed | T14 principal-competencies + negotiation, T19 llm-testing + coverage-mutation, T27 prod-debugging + observability-debug |

Then **Phase B, ~163 modules**: T12 DevOps (18), T31 RL (14), T16 Computer Systems (13),
T11 Polyglot (12), T24 Finance (10), T04 Deep Learning (10), T26 Frontier (9), T25 Product (8),
T22 Blockchain (8), T20 Rust (8), T03 Classical ML (8), T01 Python (8), T23 Quantum (7),
T13 SDE Craft (7), T09 MLOps (7), C-AZ (8), C-GCP (8).

**Always re-derive the unwritten list from disk before spawning** — killed agents finish more
than their last message suggests, and spawning from a stale plan overwrites good work:

```bash
python -c "
import json,glob,pathlib
c=json.load(open('app/data/curriculum.json',encoding='utf-8'))
for t in c['tracks']:
    files={pathlib.Path(p).stem for p in glob.glob(str(pathlib.Path(t['dir'])/'*.md'))}
    un=[m for m in t['modules'] if not any(f.endswith(m['slug']) for f in files)]
    if un: print(t['id'], len(un), [m['slug'] for m in un])
"
```

## Four rules every agent prompt must carry

Each was learned by something breaking.

1. **`## The 30-second version` is REQUIRED — state it separately from "write it last."**
   The spec says write it last, so long-running agents drop it. Six T18 modules did, in one batch.
2. **Lineage labels exactly `**What came before.**` / `**Where it stands now.**` /
   `**Where it's heading.**`, bold run containing ONLY the label.** Twice an agent let the
   bold run absorb the following sentence; the content was fine and the gate failed it.
3. **Write modules one at a time, finishing module + cards + drills before starting the next.**
   Eleven agents were killed mid-batch by a spend limit. Before this rule they left half-written
   files; after it they left zero gate failures.
4. **Fragments only, never the aggregates.** Write `app/data/cards/<id>.json` and
   `drillsets/<id>.json`. Never `flashcards.json`, `drills.json` or any `.js`. Never run
   `build_data.py` while other agents are running — the orchestrator runs it once after.

## Before sending a module back, check whether the gate is wrong

Three times the gate was wrong and the content was fine: T15 rounds legitimately have no
lineage, a 40-question SQL bank formatted as `**Qn**` counted as 3, and the full-loop round
has no question bank because it orchestrates the other five. Sending good work back is worse
than not checking.

## Not modules, still zero

| Gap | State |
|---|---|
| Problems | `app/data/problems.json` is empty; the app's Problems tab renders blank. 30 DSA patterns have nothing to practise against. Fragments go in `app/data/problemsets/`. |
| Labs | 1 of ~40. `labs/{go,infra,java,rust,ts}` are empty. Pattern: `labs/py/01-circuit-breaker` (starter fails, solution passes, injectable clock). |
| Cheatsheets | 0. `/tutor-cheatsheet` exists and has 236 modules to compress. |
| Azure / GCP atlases | 0 of 16. Only the watermark JSONs. |
| `/tutor-update` | never run; watermarks seeded 2026-07-26, `runs: 0`. |

## The 184 `[CONFIRM: ]` placeholders — needs the student, not an agent

In `T10-resume-systems`, `T14-star-bank`, `T14-company-specific`, `T15-round-hm`. That is the
whole weekend-8 resume-defence block, which PLAN.md calls the highest-ROI weekend in the plan.
They are honest placeholders for real numbers: team sizes, how the 89% ETL cut was measured,
what actually happened in the ClickHouse OOM. An invented number in a STAR story is exactly
what a hiring manager catches on the follow-up. If a real loop lands before the library is
finished, that hour beats any amount of new content.

## Claims flagged as secondary-sourced

Agents flagged these rather than asserting them. Fine in the module, do not quote in an interview:
Bedrock provisioned-throughput pricing (AWS does not publish it), the ViT crossover threshold,
pyannote DER figures, the FastAPI threadpool default of 40 (correct, but the primary source
403s), Tungsten's "10x" (2016 benchmark, not current hardware), the GraphRAG "$33,000 → $33"
figure, and the semantic-caching cost arithmetic (a constructed worked example, labelled as such).
