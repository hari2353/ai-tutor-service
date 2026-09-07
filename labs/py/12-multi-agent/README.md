# Lab 12: Multi-Agent Topologies — and When NOT To

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-multi-agent-topologies`

**You will build:** five orchestrator topologies — supervisor, pipeline, debate, blackboard, router — as pure-Python composable classes over injectable agent callables, with failure containment at every seam.

**You will be able to answer:** *"Design a multi-agent system for X" — and push back on the premise: which topology earns its keep, what each seam costs, and when one agent with tools beats all five.*

## Setup

```bash
cd labs/py/12-multi-agent
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

Every "agent" is a callable you inject — `fn(task) -> result` for workers/proposers/stages, `fn(state) -> state-update dict` for blackboard agents. No LLM, no I/O, no sleeps. One file: `topologies.py`.

1. **`Supervisor(workers: dict name -> fn)`** — central router, workers never talk to each other. `dispatch(task, worker_name)` routes to one worker and returns its result; unknown name raises `RoutingError`. `broadcast(task)` runs every worker and returns `{name: result}` — a worker that raises is caught and reported under its own name as `Failure(worker, error)`; the rest still run.
2. **`Pipeline(stages: list of fns)`** — `run(task)` feeds each stage's output to the next. A stage raising `StageError` aborts with `PipelineAborted` carrying `.trace` (outputs of completed stages only), `.stage_index`, and `.error`. Stages after the failure never run; any other exception propagates raw — `StageError` is the protocol, the rest are bugs.
3. **`Debate(proposers: list of fns, judge: fn)`** — every proposer answers the same task independently; `judge(proposals, task)` returns the winning index; `run(task)` returns `(winner_index, proposals)`.
4. **`Blackboard(agents, max_rounds=3)`** — shared state dict; each agent's update dict is applied sequentially in registration order (an agent sees earlier agents' same-round writes) until a full round produces no changes, or `max_rounds` is hit. `run(initial_state=None)` returns `(final_state, rounds_used)`; the final changeless round counts.
5. **`Router(classifier: fn(task) -> worker_name, workers)`** — `route(task)` asks the classifier, runs the chosen worker, returns its result; unknown route raises `RoutingError`.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Structured routing** — make the router's classifier emit `(worker, subtask, why)` and log it; measure route accuracy against labels. *(Interview: "how do you debug a supervisor that mis-routes 8% of requests?")*
2. **Hop budget** — turn the supervisor into an iterative planner: routes back through itself until `FINISH` or a hop cap. *(Interview: "what stops an infinite router?")*
3. **Distilled returns** — give workers a return contract `{answer, evidence, tokens}` and assert the supervisor's context only ever receives that, never raw history. *(Interview: "what crosses the boundary and what does it cost you?")*
4. **The honest comparison** — script a 20-task set, run one big worker with all the tools, then the supervisor; count calls. *(Interview: "when does the single agent win?" — usually.)*
