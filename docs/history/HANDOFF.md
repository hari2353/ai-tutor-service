# HANDOFF — resume point

> Last updated 2026-09-06 (the union merge: v1 + v2 + the F:\ai-tutor-service
> working copy combined into one repo). Regenerate the live numbers with
> `python app/build_data.py`, `python app/tests/review_gate.py` and
> `powershell -ExecutionPolicy Bypass -File app\tests\run.ps1`; this file is
> the plan, those are the truth.

## State — curriculum COMPLETE, repos UNIFIED

| | |
|---|---|
| Written | **461 / 461 modules (100%)** |
| Review gate | **461 pass · 0 fail** |
| App tests | dom 25/25 · sm2 10/10 · unit 11 · integration 5 |
| Labs | **40 total** (py 28 + misc 6 + go 2 + rust 1 + ts 1 + java 1 + review-exercises 1), all suites green |
| Flashcards / drills / problems | **5,677 / 4,630 / 450** |
| Tracks | **36 / 36 complete** |
| Git | repo on `main`, synced with github/hari2353/ai-tutor-service (private) |

## What the union merge did (2026-09-06)

Three parallel copies existed. This repo is now the single source of truth:

1. **From v1's unpushed work**: `T07-ambient-agents` (module + cards + drills +
   spec entry) — the one module v2 lacked.
2. **From the `F:\ai-tutor-service` working copy** (newest T07 rewrites):
   agent-safety, structured-output, prompt-versioning, guardrails modules with
   their cards/drillsets; `labs/misc/*` (docker + 5 k8s labs);
   `labs/go/03-k8s-core-operator`; `mocks/PATTERNS.md`.
3. **v2's own newer work**: hr-round-basics + aptitude-puzzles (T15),
   excel-analyst + bi-tooling + oracle-sql (T18), quant-python-stack (T24),
   their cards/drillsets, `labs/py/19-oracle-sql-semantics`,
   `labs/py/20-excel-formula-engine`, `labs/py/21-bi-filter-context`
   (finished in this merge: tests + solution + PRODUCTION), the mining
   worklist tooling and `scripts/ig_crawler`.
4. **Repaired**: 7 broken `labs/k8s/*` pointers repointed at `labs/misc/*`;
   `labs/py/19-guardrails` built from scratch (the guardrails module
   referenced it); PRODUCTION.md added to py/02, py/03-bpe, py/03-reasoning,
   py/04-tool, py/05-hybrid, py/21; `link_check.py` taught each language's
   house lab shape (go/rust/ts/java) — **0 broken pointers, 0 incomplete labs**.
5. **Security**: `opencode.json` (live API keys) and `mining/crawl_state/`,
   `mining/posts/` are gitignored; never let them into history.

## What is NOT done

| Gap | State |
|---|---|
| **`/tutor-update`** | Watermarks seeded 2026-07-26, delta run once (2026-08). The cloud atlases drift weekly — run it before any cloud-focused interview. |
| **Cheatsheets** | 33 of ~461 modules. The sprint-bearing ones are covered; the rest on demand. |
| **Labs breadth** | 40 labs for 461 modules. T02 DSA patterns have problemsets instead; high-value tracks (T05/T06/T07) are well covered. |
| **`T15` boss rounds** | `round-full-loop` needs the pipeline from `/tutor-company` for company-specific rounds. |

## The 184 `[CONFIRM: ]` placeholders — needs the student, not an agent

In `T10-resume-systems`, `T14-star-bank`, `T14-company-specific`, `T15-round-hm`.
That is the whole weekend-8 resume-defence block. They are honest placeholders
for real numbers: team sizes, how the 89% ETL cut was measured, what actually
happened in the ClickHouse OOM. An invented number in a STAR story is exactly
what a hiring manager catches on the follow-up.

Also flagged by the agent that read the resume: **`ml.4xlarge` and `g4.2xlarge`
are not valid SageMaker instance identifiers** (real ones are `ml.g4dn.2xlarge`
/ `ml.g5.xlarge`). That sits on the strongest technical story on the CV.

If a real loop lands, that hour beats any amount of new content.

## Five rules every agent prompt must carry

Each was learned by something breaking.

1. **`## The 30-second version` is REQUIRED — state it separately from "write it last."**
   The spec says write it last, so long-running agents drop it or append it at the end.
2. **Lineage labels exactly `**What came before.**` / `**Where it stands now.**` /
   `**Where it's heading.**`, bold run containing ONLY the label.** A single stray space
   inside the bold (`**Where it stands now. **`) failed C-GCP-serverless with good content.
3. **10+ interview questions per module, each with a `**Follow-up trap:**`.** 27 modules
   landed at 5-9 and had to be repaired in a separate pass. Cheaper to count up front.
4. **Write modules one at a time — module, then cards, then drills, then the next.**
   Agents are killed mid-batch constantly. With this rule they leave complete work behind;
   without it they leave half-written files.
5. **Fragments only, never the aggregates.** Write `app/data/cards/<id>.json` and
   `drillsets/<id>.json`. Never `flashcards.json`, `drills.json` or any `.js`. Never run
   `build_data.py` while other agents run — the orchestrator runs it once after.

## Always re-derive the unwritten list from disk before spawning

Killed agents finish far more than their last message suggests. Spawning from a stale plan
overwrites good work.

```bash
python -c "
import json,glob,pathlib
c=json.load(open('app/data/curriculum.json',encoding='utf-8'))
for t in c['tracks']:
    files={pathlib.Path(p).stem for p in glob.glob(str(pathlib.Path(t['dir'])/'*.md'))}
    un=[m['slug'] for m in t['modules'] if not any(f.endswith(m['slug']) for f in files)]
    if un: print(t['id'], len(un), un)
"
```

**One repo, one truth.** The old copies (`F:\v1\...`, `F:\ai-tutor-service`)
are now read-only history; make all changes here and push. State the absolute
path of THIS repo in every agent prompt and verify afterwards.

## Before sending a module back, check whether the gate is wrong

The gate has been wrong more often than the content. It has three profiles (standard,
pattern for T02, boss for T15) because behavioural modules legitimately substitute a
practical exercise for "build it from scratch", a 40-question SQL bank formatted as `**Qn**`
counted as 3, and T15 rounds have no lineage by design. Sending good work back is worse
than not checking.

## Claims flagged as secondary-sourced

Fine in the module, do not quote cold in an interview: Bedrock provisioned-throughput
pricing, the ViT crossover threshold, pyannote DER figures, Tungsten's "10x", the GraphRAG
"$33,000 → $33" figure, FastAPI-vs-Go RPS benchmarks, Container Apps and Front Door
per-unit pricing, exact 2026 frontier-model pricing and benchmark numbers, and several
CAC/LTV industry benchmarks. Each is flagged in-module.
