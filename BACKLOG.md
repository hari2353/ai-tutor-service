# BACKLOG — what is deliberately not done

> Everything buildable has been built and gated: 454/454 modules written, review gate
> 454/454, 18 Python labs + PR-review exercise (~350 test cases), 33 cheatsheets,
> app at feature parity with its data. What remains falls into three honest buckets.

## A. Needs YOU, not an agent (highest ROI in the plan)

| Item | Where | Why it can't be automated |
|---|---|---|
| Fill **184 `[CONFIRM]` facts** | `progress/CONFIRM-CHECKLIST.md` | Your real team sizes, measured latencies, incident outcomes. An invented number is what HM follow-ups catch. |
| Run the first **full-loop mock** | `/tutor-mock loop`, log to `mocks/` | Establishes your actual score bands (70/80/88 bar). Zero logged today. |
| Prep the **Siemens Brightly JD (score 88)** | `/tutor-company` | Sitting unpicked since 2026-07-26. `progress/PERSONAL-PLAN.md` §1 prices this hour-for-hour above any new content. |
| Debrief after each real interview | `/tutor-debrief` | Feeds `mocks/PATTERNS.md` — the auto-promotion loop stays dormant without ≥1 entry. |

## B. Needs toolchains or runtime you don't have yet

| Item | Blocker | Unblocks when |
|---|---|---|
| Remaining labs in `labs/go, java, rust, ts, infra` beyond the first per language | One lab per language now exists and gates green (`go/01-circuit-breaker`, `java/01-rate-limiter`, `rust/01-bpe-tokenizer`, `ts/01-chunking`); infra wants Docker | Spawn `/tutor-lab <module>` batches per language; house pattern (`starter` fails → solution passes) proven in all five toolchains |
| CI on GitHub Actions (`windows-latest` runner executing `run.ps1`) | Repo not yet pushed | Add `.github/workflows/ci.yml` post-upload; the suite is already subprocess-clean |

## C. Scheduled maintenance, not creation

| Item | Cadence | Mechanism |
|---|---|---|
| `/tutor-update` cloud/agent-stack deltas | weekly Saturday | Watermarks seeded, `runs: 0`; say "update" or schedule the task |
| Cheatsheet regeneration | after any sprint-module edit | `python scripts/gen_cheatsheets.py` (already scripted) |
| CONTENT-STATUS / LEARNING-PATH refresh | automatic on build | `build_data.py` regenerates both |
| Security scan drift | automatic | wired into `run.ps1`; extend patterns as new key shapes appear |

## Explicitly out of scope (decided, documented)

- Blockchain/quantum/finance depth beyond the 25 written modules — Phase B reference,
  zero next-loop value (PLAN v0.3 tension table, honored).
- Auto-generating mocks or progress data to fill dashboards — synthetic scores would
  poison the only honest feedback loop in the system.
