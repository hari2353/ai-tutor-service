# Lab 24: Zero → Production — The Complete Agent, End to End

**Track:** T07 Agentic AI · **Time:** 4h · **XP:** 50
**Module:** `T07-agent-zero-to-prod`

**You will build:** the capstone composition — a production-shaped agent service with cost guard, error resilience, checkpoints, and an event log whose invariants you can validate.

**You will be able to answer:** *"You've shown me a loop and a tool registry. What stands between that demo and production?"* — and name every component.

## Setup

```bash
cd labs/py/24-zero-to-prod
pip install pytest
```

## The spec

1. **`FakeLLM(replies, resume_at=0)`** — queue-scripted; exposes `.i`; last reply repeats when exhausted.
2. **`ProductionAgent(llm, tools, config, clock)`** — run(task) → `{answer, turns, cost_usd, events, stopped_by}`. Tool protocol: `CALL: name {json}` / `DONE: answer`. Unknown tool or tool exception → error observation, loop continues.
3. **Stop conditions** (between turns): `max_turns`, 3 consecutive tool errors → `tool_errors`, `cost_cap_usd` → `cost` (events preserved), `token_budget`.
4. **`checkpoint()` / `resume(agent, cp)`** — plain-data snapshot of messages + LLM index + counters; resume continues exactly where it stopped.
5. **`validate(events)`** — invariant checks: every tool_call has a matching observation/tool_error; cost entries monotonic non-decreasing. Returns violation list.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Durable checkpointer** — swap the dict for a JSON file (tmp_path); resume across "process death" (new agent instance).
2. **Streaming** — make `run` a generator yielding events; a cancelled generator must still be resumable.
3. **Canary eval** — a golden task set; the agent must score 100% before the "deploy" button unlocks.
