# Production notes — mini LangGraph core

## What you'd actually use

| Your lab piece | Real LangGraph |
|---|---|
| `add_reducer(key, fn)` | `Annotated[list, operator.add]` / `add_messages` on the TypedDict |
| default overwrite | last-write-wins — and 2 writes to one unannotated key in ONE super-step raises `InvalidUpdateError: Can receive only one value per step` |
| conditional router returning a name/`END` | `add_conditional_edges(node, route, mapping)` |
| router returning a list of names | parallel fan-out of *different* nodes on the same state |
| `Send(node, arg)` | `langgraph.types.Send` — same node N times, N different states |
| static join dedupe | fan-in node fires when inbound edges are satisfied; unequal branch lengths need `defer=True` |
| `recursion_limit=1000` guard | config `recursion_limit` (default **1000 since 1.0.6**, was 25) → `GraphRecursionError` |

**Deliberate simplifications.** Your engine is single-threaded, so the reducer fold is deterministic and the default-overwrite rule can't corrupt anything mid-tick. Real LangGraph runs a tick's tasks concurrently and *refuses* two writes to an unreduced channel rather than guessing. If you port to threads (stretch goal), keep the fold ordered or your logs lie.

## What the real ones add over yours

- **Typed state + schema-driven reducers** read from `Annotated` metadata instead of manual registration.
- **Checkpointing at every super-step** (`checkpointer=`), which is why resume means "re-run the node", not "resume the line" — see Lab 14.
- **Streaming** (7 modes), subgraph namespacing, `interrupt()`/HITL, per-node `RetryPolicy`, `Command(goto=...)`.
- **Bounded concurrency**: `config={"max_concurrency": N}` — 500 unbounded `Send`s against a rate-limited provider is how 429 storms are born.

## What breaks at scale (mirrors curriculum table)

| Symptom | Cause | Fix |
|---|---|---|
| Branch output silently missing | no reducer; sequential writes; last one won | declare the reducer; audit every non-scalar key |
| Works in dev, `InvalidUpdateError` in prod | first real run hit the multi-destination path | test every router's multi-destination return |
| Fan-in sees partial results | unequal branch lengths fired it early | `defer=True` |
| Duplicate messages after human edit | `operator.add` used where `add_messages` (merge by id) belongs | swap the reducer |
| Runaway loop costs money | default `recursion_limit` 1000 trusted as safety net | set it explicitly; carry your own budget in state |

## The 3 questions an interviewer asks after this lab

1. *"What does the default reducer do?"* — overwrite. Saying "merge" or "append" is the red flag.
2. *"Why does `Send` require a reducer on the fan-in channel?"* — N concurrent writers to one channel with no combine rule is the one-value-per-step error N times over.
3. *"Your graph loops forever — what stops it?"* — a conditional edge to `END`, your own budget in state, then `recursion_limit` as backstop (top-level config key, not inside `configurable`).
