# Lab 21: Harness Engineering — The 15-Component Skeleton

**Track:** T07 Agentic AI · **Time:** 3.5h · **XP:** 50
**Module:** `T07-harness-engineering`

**You will build:** the load-bearing components of an agent harness — context window with compaction, tool router with risk-gated permissions, loop engine with budgets and stop conditions, event log, kill switch.

**You will be able to answer:** *"What are the parts of an agent harness, where does each decision live, and why is the kill switch checked between turns, not inside them?"*

## Setup

```bash
cd labs/py/21-harness-skeleton
pip install pytest
```

## The spec

1. **`Clock`** — `SystemClock` / `FakeClock(t=0).advance(dt)`. Nothing else touches time.
2. **`ContextWindow(cap, tokenizer)`** — `add(msg)`; on cap breach, compaction runs: drop oldest non-pinned messages, then call the `summarizer` hook to inject a running summary; pinned messages (system) never dropped.
3. **`ToolRouter`** — register `(name, fn, schema, risk)` with risk in `read_only | side_effect | destructive`. `call(name, args, approver)`: unknown tool → `ToolError`; schema validation (required keys); `destructive` requires `approver(name, args) is True` else `PermissionDenied`; tools may raise — router wraps failures as `ToolError(retryable=...)`.
4. **`LoopEngine(llm, router, context, cfg, clock)`** — each turn: append LLM reply; if it's a tool call, route it, append observation; check stop conditions between turns: `max_turns`, `token_budget` (sum of approx token counts), `wallclock_budget` (via clock), `max_tool_errors` (consecutive tool failures trip), `kill_switch` (a flag read BETWEEN turns), explicit `STOP` in the LLM reply.
5. **`EventLog`** — every decision point appends `(t, kind, payload)`; queryable `events(kind)`.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Retry with backoff** — retryable tool errors get 2 attempts with clock-based backoff; where does the retry budget live?
2. **Per-tool concurrency caps** — a semaphore per tool; a saturated tool queues or rejects (which is right for which risk level?).
3. **Checkpoint** — serialize engine state; resume mid-run after "process death".
