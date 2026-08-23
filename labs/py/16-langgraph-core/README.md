# Lab 16: Mini LangGraph Core — StateGraph, Reducers, Conditional Edges, Send

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 60
**Module:** `T07-langgraph-core`

**You will build:** a Pregel-style mini state-graph engine in pure Python — dict state with per-key reducers (default overwrite), nodes returning partial updates, static/conditional edges, `Send` fan-out with deep-copy branch isolation, `compile()` structural validation, and a deterministic `execution_log` — the ~200 lines that make real LangGraph stop being magic.

**You will be able to answer:** *"Walk me through what a reducer actually does, why fan-in breaks without one, and what `Send` gives you that a conditional edge doesn't?"*

## Setup

```bash
cd labs/py/16-langgraph-core
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`StateGraph(state_schema)`** — state is a plain dict; the schema is declared metadata only. One reducer per key via `add_reducer(key, fn)` where `fn(current, update) -> new` (e.g. append/concat for list keys). **No reducer = OVERWRITE (last write wins)** — the silent-clobber default from the curriculum.
2. **Declaration API** — `add_node(name, fn(state) -> partial updates | None)`, `add_edge(a, b)` (`a` may be `START`), `add_conditional_edges(a, router_fn(state))` where the router returns a node name, `END`, a `Send`, or a list of them. `set_entry(name)` or `add_edge(START, x)` — exactly one entry.
3. **`compile()` validation → `GraphError`** — unknown edge targets; no/duplicate entry; unreachable-from-entry nodes; mixing static + conditional routing on one node; **pure-STATIC cycles** (a loop is legal only if a conditional edge sits on it, because that's the only way it can terminate).
4. **Super-steps** — every scheduled node runs on its OWN deep copy of committed state, all writes are reduced in execution order, then the next frontier schedules. Node input mutation never leaks unless returned; returned updates are deep-copied in.
5. **`Send(node_name, arg)` fan-out** — returned from a conditional edge. N Sends = N invocations of the same node, each with its own sub-state (deep copy of committed state overlaid with `arg`); results merge through that node's updates with reducer semantics; its static join target runs exactly ONCE after all branches (dedupe per tick). Never dedupe Send items themselves.
6. **`invoke(values, recursion_limit=1000)`** — runs until END, returns final state as a detached deep copy, and records `graph.execution_log`: node names in exact execution order, Send fan-out in the deterministic order of the router's list.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **`Command(update=..., goto=...)`** — route and write atomically from a node; annotate destinations so compile() can check them. *(Interview: "Command vs conditional edge?")*
2. **`Overwrite`** — an escape-hatch wrapper that bypasses a declared reducer for one write ("compact messages to a summary"), allowing exactly one per key per tick.
3. **True parallel super-steps** — run one tick's nodes on threads with a `max_concurrency` cap; then find which of your tests stops being deterministic and explain why the reducer fold must stay ordered.
4. **Durable port** — bolt Lab 14's `MemoryCheckpointer` onto this engine: checkpoint at every super-step boundary and resume mid-loop. *(Interview: "why is the checkpoint boundary the super-step, not the node line?")*
