# Lab 02: An Agent Loop From Scratch

**Track:** T07 Agents · **Time:** 2h · **XP:** 50
**Module:** `T07-agent-loop-from-scratch`

**You will build:** a tool-calling agent loop on a deterministic `FakeLLM` — prompt → model → parse → dispatch → observe → repeat — with a step budget instead of a time budget.

**You will be able to answer:** *"Walk me through the control flow of a tool-calling agent loop — what happens when a tool crashes, and why is the budget measured in steps, not seconds?"*

## Setup

```bash
cd labs/py/02-agent-loop
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`FakeLLM(script)`** — deterministic stand-in for a model. Queued JSON responses, each either `{"tool": name, "args": {...}}` or `{"final": "answer"}`. It records every prompt it is shown (`.prompts`) so tests can assert what the model actually saw. When the script runs dry it answers `{"final": ""}`.
2. **`AgentLoop(model, tools, max_steps=8)`** — the loop: build messages → `model.complete(messages)` → parse the response → dispatch the tool **or** finish. One model call == one step.
3. **Unknown tool name** — feed back the observation string `error: unknown tool <name>` and let the loop continue. The agent gets to recover; the harness does not crash.
4. **Tool raises an exception** — observation string `error: <exception message>`. The error never propagates out of the loop.
5. **Step budget exhausted** — return `Result(answer=None, steps=max_steps, reason="budget")`.
6. **Happy path** — tool call(s), then a final: `Result(answer=..., steps=n, reason="final")`.
7. **Tools receive/return plain JSON-able dicts.** Args are passed as a copy — a tool mutating its input must not corrupt the transcript. Inject nothing time-based: *steps are the budget*.
8. The caller's `tools` dict must never be mutated by the loop.

Message shape fed to the model (and recorded by `FakeLLM.prompts`): a list of
`{"role": ..., "content": ...}` dicts — a leading user turn with the task,
then alternating assistant turns (the raw action JSON) and user turns
(`"Observation: <observation>"`).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Malformed responses** — model emits neither `tool` nor `final`: feed back an `error:` observation instead of crashing. *(Interview: "who owns schema validation — model or harness?")*
2. **Parallel tool calls** — one response requesting several tools; observations returned in order.
3. **Context trimming** — drop old observations when the transcript exceeds N messages. What may you never drop?
4. **Cost accounting** — fake token counts per step, expose `Result.cost`. Why do real agents budget in tokens *and* dollars?
