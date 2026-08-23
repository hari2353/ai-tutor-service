# Lab 03: Reasoning Patterns — ReAct, Plan-Execute, Reflexion

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-react-pattern-raw`

**You will build:** three decision architectures on one deterministic `FakeLLM` — a ReAct loop whose `Thought/Action/Observation` trace you can assert on, a Plan-and-Execute pipeline with a replan edge that fires at most once, and a Reflexion outer loop whose reflections are fed back into the next attempt's prompt.

**You will be able to answer:** *"When does the model decide what to do next — per step, up front, or between attempts — and what does each position cost and break?"*

## Setup

```bash
cd labs/py/03-reasoning-patterns
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`FakeLLM(script)`** — same protocol idea as lab 02: pops queued JSON responses in order, records every prompt it is shown (`.prompts`, verbatim), hands out copies (never its own script), answers `{"final": ""}` when dry. Responses used by this lab: `{"thought", "tool", "args"}`, `{"thought", "final"}`, `{"plan": [...]}`, `{"answer": ...}`, `{"reflection": ...}`.
2. **`react_loop(model, tools, max_steps=6, task="")`** — ReAct. One model call == one step. Trace lines, exact format: `"Thought: <text>"`, `"Action: <name>(<canonical json args>)"`, `"Observation: <stringified>"`, `"Final: <answer>"`. Every action is preceded by its thought; every observation follows its action. Unknown tool / crashing tool → `"error: ..."` observation, loop continues. Budget out → `ReactResult(None, trace, max_steps, "budget")`.
3. **Tools receive JSON args** — a copy of the scripted dict; the Action line records canonical JSON (`sort_keys=True`). A tool mutating its args must not corrupt the script or the trace.
4. **`plan_execute(model, tools, task="")`** — planner call returns `{"plan": [...]}`; then one executor call per step whose prompt carries the step text plus all results so far, answering `{"tool", "args"}`. All steps succeed → `PlanExecuteResult(plan, outputs, answer=last output, replans=0, reason="completed")`.
5. **Replan-on-failure fires at most ONCE.** An output starting `"error:"` is a failure. First failure → one replan call (the failure text is in the replanner's prompt), the revised plan replaces the old one, outputs reset. Any later failure → stop: `replans == 1`, `reason="failed"` — a replan is an edge, not a loop.
6. **`reflexion(model, task_fn, max_trials=3, task="")`** — `task_fn` is the *external* verdict (`-> bool`; a test, not a vibe). Per trial: an answer call (`{"answer": ...}`); if `task_fn` passes → stop immediately with `reason="pass"` (no reflection call). If not → one reflection call (prompt says the attempt *"did not pass"*; skipped after the final failed trial — no next attempt to inform), non-empty reflections accumulate in `.reflections` and the next trial's prompt embeds them under `"Feedback from previous attempts:"`. Trials exhausted without passing → best-effort result: the LAST candidate answer, `success=False`, `reason="exhausted"`.
7. **Determinism** — no time, no randomness anywhere. Identical scripts → identical prompts, traces and results.
8. **Purity** — never mutate the caller's `tools` dict, the model's script, or the scripted args.

Message shapes fed to the model (recorded verbatim in `.prompts`) are single-user-turn transcripts: `[{"role": "user", "content": ...}]`, except `react_loop`, which appends assistant turns (`"Thought: ...\nAction: ..."`) and user turns (`"Observation: ..."`) like lab 02.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **The gate** — deterministic precondition check between executor steps; pay for the LLM replan only when the gate fires. Count what blanket replanning would have cost. *(Interview: "why is replan-after-every-step just ReAct with a worse name?")*
2. **Help/harm instrumentation** — log the `(pre_verdict, post_verdict)` pair per reflexion invocation; report help rate, harm rate, cost per net-correct answer. *(If harm ≥ help you shipped a random-answer-perturber.)*
3. **Degeneration detector** — abort when successive reflections are near-identical (`difflib.SequenceMatcher.ratio() > 0.9`) while outputs barely change.
4. **ToT teaser** — k scripted candidate thoughts scored by a scripted scorer per node. Then explain why the scorer is the whole algorithm and the tree is decoration.
