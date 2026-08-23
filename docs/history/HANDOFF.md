# HANDOFF — resume point

> Last updated 2026-08-08. Regenerate the live numbers with `python app/build_data.py`,
> `python app/tests/review_gate.py` and `bash app/tests/run.sh`; this file is the plan,
> those are the truth.

## State — curriculum COMPLETE

| | |
|---|---|
| Written | **452 / 452 modules (100%)** |
| Review gate | **452 pass · 0 fail** |
| App tests | dom 20/20 · sm2 10/10 · labs SKIPPED (pytest not installed) |
| Flashcards / drills | **5,503 / 4,570** |
| Volume | ~2.99M words across 453 files |
| Tracks | **36 / 36 complete** |
| Git | repo on `main`, **0 commits**, ~1,900 files staged |
| GitHub | not pushed — needs `gh auth login` (user action; never run by an agent) |

Every track is finished, including the two written against live job descriptions:
**T32 Applied NLP & Marketing ML** (Expedia Marketing Content ML: LDA, NER, Bayesian
methods, factorial/multivariate/stratified design, uplift, MMM) and **T33 Frontend & UI**.

## What is NOT done

Modules are complete. These are not:

| Gap | State |
|---|---|
| **Labs** | 1 of ~40. `labs/{go,infra,java,rust,ts}` are empty. Pattern to copy: `labs/py/01-circuit-breaker` — starter fails, solution passes, injectable clock, no network in tests. |
| **Problems** | `app/data/problems.json` is empty; the app's Problems tab renders blank. 30 DSA patterns have nothing to practise against. Fragments go in `app/data/problemsets/`. |
| **Cheatsheets** | 0. `/tutor-cheatsheet` exists and has 452 modules to compress. |
| **`/tutor-update`** | Never run. Watermarks seeded 2026-07-26, `runs: 0`. The cloud atlases and the agent/LLM tracks will start drifting within weeks. |
| **Git** | Never committed. See `COMMIT.md`. |

## The 184 `[CONFIRM: ]` placeholders — needs the student, not an agent

In `T10-resume-systems`, `T14-star-bank`, `T14-company-specific`, `T15-round-hm`. That is
the whole weekend-8 resume-defence block, which PLAN.md calls the highest-ROI weekend in
the plan. They are honest placeholders for real numbers: team sizes, how the 89% ETL cut
was measured, what actually happened in the ClickHouse OOM. An invented number in a STAR
story is exactly what a hiring manager catches on the follow-up.

Also flagged by the agent that read the resume: **`ml.4xlarge` and `g4.2xlarge` are not
valid SageMaker instance identifiers** (real ones are `ml.g4dn.2xlarge` / `ml.g5.xlarge`).
That sits on the strongest technical story on the CV.

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

**Check the agent wrote to the right repo.** One agent wrote all 7 quantum modules to
`F:\ai-tutor-service` instead of `F:\v1\ai-tutor-service`; they had to be moved by hand.
State the absolute path in the prompt and verify afterwards.

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
