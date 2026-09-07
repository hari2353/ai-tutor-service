# Lab 04: Agent Trajectory Eval Harness

**Track:** T08 Eval & Observability · **Time:** 2h · **XP:** 50
**Module:** `T08-agent-eval`

**You will build:** a trajectory eval harness — `ToolCall`/`Trajectory` dataclasses, a golden set of expected trajectories, scoring functions (tool-call accuracy with fuzzy arg matching, task completion with exact/contains/numeric-tolerance modes, trajectory validity against an allowed-transitions spec, cost per step, latency p50/p95), an `EvalSuite` that aggregates per-run scores into a pass/fail report, and a regression runner that compares the current run against a stored previous run. All data from fake fixture trajectories — no LLM, no network.

**You will be able to answer:** *"Your agent 'works' in the demo. How do you know a prompt change didn't silently break it — what do you measure, and what fires the alarm?"*

## Setup

```bash
cd labs/py/04-agent-eval-harness
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`ToolCall`** — dataclass `ToolCall(name, args: dict, result, latency_ms, cost_usd)`. **`Trajectory`** — dataclass `Trajectory(task_id, steps: list[ToolCall], final_answer, task_spec: TaskSpec | None = None)`.
2. **`ToolCallAccuracy`** — score a run's steps against an expected sequence. `score(gold_steps, actual_steps)` → fraction of expected steps matched in order. **Fuzzy arg matching:** a step matches when name is equal AND all *relevant* args are equal — irrelevant args are ignored (e.g. `run_id`, `trace_id`, `timestamp`). An extra actual arg is fine; a wrong relevant arg is a mismatch. A missing expected step is a miss.
3. **`task_completion`** — `check(expected, actual, mode)` with modes:
   - `exact`: `str(actual) == str(expected)`
   - `contains`: expected is a substring of actual
   - `numeric`: `abs(float(actual) - float(expected)) <= tolerance` (default `0.01`)
   Unknown mode raises `ValueError`.
4. **`trajectory_validity`** — given an allowed-transitions spec (`{"init": {"search", "end"}, "search": {"fetch", "end"}, ...}`, `"init"` is the entry state) and a trajectory's steps, walk the states: first tool must be reachable from `init`, then each next tool from the current tool's state. Any illegal transition appends `(step_index, from_tool, to_tool)` to `violations`. `"end"` terminates. Returns `TrajectoryValidityReport(valid: bool, violations)`.
5. **`cost_per_step`** — `total_cost_usd(trajectory) / max(1, len(steps))` — an empty trajectory costs 0. `latency_p50` / `latency_p95` — percentiles of `latency_ms` across steps; a trajectory with no steps has both `0.0`. p95 via the nearest-rank method: index `ceil(0.95 * n) - 1` on the **sorted** list.
6. **`EvalSuite(thresholds).run(trajectories, golden_set) -> RunReport`** — for each task: tool-call accuracy, completion (from the trajectory's `task_spec`: `expected_answer` + `mode` + `tolerance`), validity (from the spec in the golden set), cost/step, p50/p95. `RunReport` has per-metric averages, per-task rows, `passed` (every metric average meets its threshold), and `fail_reasons`. Defaults: `tool_accuracy >= 0.9`, `completion >= 0.8`, `validity >= 1.0`, `cost_per_step <= 0.05`, `p95_latency_ms <= 5000`.
7. **`compare_runs(previous: RunReport, current: RunReport) -> RegressionReport`** — flag metrics that regressed beyond tolerance: a *lower-is-better* metric (cost, p95) regresses when it rises more than 20%; a *higher-is-better* metric (accuracy, completion, validity) regresses when it drops more than 0.05 absolute. `RegressionReport.regressions` lists `(metric, previous, current)` tuples; `regressed` is True when the list is non-empty. Equal-or-better runs produce an empty list.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Partial-credit tool matching** — a wrong relevant arg is 0.5 credit, not 0; see how the pass boundary moves. Should real harnesses give partial credit? (Debate: strict matching catches more bugs.)
2. **Cost-weighted accuracy** — accuracy per dollar: what did getting to 95% cost, and is the last 5% worth a tool call that triples cost?
3. **JSON-diff failures** — on a mismatch, emit a structured diff (`{"arg": {"expected": x, "actual": y}}`) so CI output tells you *which* arg broke, not just that one did.
4. **Async + parallel tasks** — score tasks concurrently with `asyncio.gather`; report wall-clock of the eval itself. What are the hazards of parallel scoring against a golden set?
