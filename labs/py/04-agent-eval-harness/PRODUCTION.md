# Production notes — agent trajectory eval

## What you'd actually use

| Concern | Real thing | What it adds over yours |
|---|---|---|
| Trajectory comparison | LangSmith `evaluate()` with a custom evaluator; Langfuse datasets + scores; Phoenix experiments | run trees stored as spans, per-step token/cost capture, side-by-side run diffs, dataset versioning, webhooks |
| Tool-call accuracy | LangSmith `RunEvalConfig.CustomEvaluationCriteria`, DeepEval `GEval` with tool-call criteria, promptfoo `llm-rubric` assertions | LLM-graded *semantic* arg equivalence ("same query intent") vs your exact-match-on-relevant-args; reference trajectories auto-extracted from past good runs |
| Task completion | promptfoo assertion types (`equals`, `contains`, `javascript`, `python`, `similar`, `is-valid-json`), DeepEval `Assertion` metrics | regex / JSON-path / model-graded checks, per-task weighted scoring, custom grader scripts with CI exit codes |
| Position in CI | promptfoo CI matrix, LangSmith CI/CD integrations, Langfuse eval jobs | PR-gating, eval-per-commit, leaderboards, alerting to Slack, experiment lineage (prompt/model/params pinned per run) |
| Cost & latency | LiteLLM cost maps, LangSmith/Langfuse per-span token accounting | per-model pricing tables updated centrally, streaming cost, budget alerts, p95 computed over weeks of traffic, not 10 fixtures |

## What the real ones add over yours

- **The golden set is alive.** You built a static dict; LangSmith/Langfuse datasets are versioned, annotated, sampled from production traces, and de-duplicated with clustering. The canonical workflow: promote real production traces into the eval set on every release.
- **Relevant-args matching is schema-driven in production.** Your `relevant_args: dict[str, set]` is a hand-rolled version of "match on typed fields, ignore telemetry noise." Promptfoo/LangSmith do this with per-assertion paths (JSONPath) or LLM-based graders for semantic equivalence.
- **Regression gating is the whole point.** LangSmith/Langfuse both do run-vs-run comparison with visual diffs and statistical significance; promptfoo's killer feature is CI exit codes: the PR does not merge if scores regress. Tolerances exist because eval sets sample — a 0.2% drop on 50 tasks is noise; 15% on 500 is a bug.
- **Cost needs a pricing map you don't own.** Your fixtures have `cost_usd` stamped on. Production computes it from token counts × the model's price, which changes monthly — LiteLLM/community-maintained cost maps exist precisely so teams don't hand-maintain that dict.
- **p95 over 20 steps is not p95.** Your nearest-rank percentile on a handful of fixtures is a smoke test. Production percentiles come from OTel span data (RED/USE) over real traffic — the eval number's job is to catch "a prompt change doubled the tool calls," not to estimate the SLA.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Eval passes, prod breaks | golden set too small / from an old distribution | sample new traces into the set per release; stratify by task type |
| Regression alarms every other PR | tolerances at zero, noisy LLM-dependent metrics | thresholds with slack (your 0.05 / 20%); n-run averaging before comparing |
| Flaky evaluations | completion graded by an LLM judge on nondeterministic answers | prefer deterministic checkers (exact/contains/numeric) wherever possible; the LLM judge only for open-ended tasks (Lab 02 calibrates it) |
| Trajectories diverge legitimately (loops, retries, re-planning) but fail exact matching | order-strict gold sequences | subsequence scoring (yours) + DAG edit distance or state-machine validity (yours) instead of strict equality |
| Cost metric drifts as models change price | hardcoded prices | central cost map keyed by (model, date); recompute historical runs, don't replay them |
| Nobody looks at the report | buried in CI logs | PR comment with the diff (promptfoo), dashboard (Langfuse/LangSmith), Slack alert on regression only |
| Eval suite becomes a golden copy of one prompt's quirks | trajectories written from what the model *did* once, not what it *should* do | author expected trajectories from the task definition; audit the golden set like code |

## The 3 questions an interviewer asks after you describe this

1. *"Exact match on tool args is brittle — the agent rephrases queries. How do you handle that without losing rigor?"* — two layers: fuzzy/structural matching on declared-relevant fields (ignore telemetry), then LLM-graded semantic equivalence as a *fallback* metric — never as the primary gate. The calibration harness (Lab 02) validates that fallback before you trust it.
2. *"Accuracy went from 92% to 90%. Is that a regression?"* — it depends on eval-set size and per-task variance: with 10 tasks, one task flipped; with 500 sampled from prod, that's 10 tasks. Set tolerances from observed run-to-run variance, and compare against a baseline distribution, not a single number.
3. *"What do you do about cost — isn't a strict cost gate going to block every quality improvement?"* — gate on *cost regressions* (rise > 20%), not absolute cost; the stretch-goal accuracy-per-dollar ratio makes the tradeoff explicit so the decision to spend more is a data point, not an accident.
