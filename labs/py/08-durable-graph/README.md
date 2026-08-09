# Lab 08: A Durable State Graph From Scratch

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 50
**Module:** `T07-langgraph-durable`

**You will build:** a minimal state graph -- nodes, conditional edges, and
a pluggable checkpointer (in-memory and SQLite) -- with no LangGraph
dependency, so you can see exactly what the framework's checkpointing
mechanism is actually doing underneath `interrupt()` and durable resume.

**You will be able to answer:** *"What does a checkpointer actually persist,
and why does the node that crashed re-run from its first line on resume
instead of continuing where it left off?"*

## Setup

```bash
cd labs/py/08-durable-graph
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`StateGraph`** -- `add_node(name, fn)`, `set_entry_point(name)`,
   `add_edge(from_node, to_node)` for fixed transitions, and
   `add_conditional_edges(from_node, router)` where `router(state)` returns
   the name of the next node (or `END`) at runtime.
2. **The one mechanism that does everything** -- after every node finishes,
   the graph saves a `Checkpoint(state, next_node, status)` **before**
   moving on. `run()` starts a new thread at step 0; `resume()` loads the
   latest checkpoint for a thread and continues from `next_node`. A node
   that already has a checkpoint recorded past it never runs again.
3. **Pluggable checkpointer**, two implementations behind the same
   interface (`save`, `load_latest`, `list_checkpoints`):
   - `InMemoryCheckpointer` -- a dict in the process. Gone on restart.
   - `SqliteCheckpointer` -- stdlib `sqlite3`, one row per checkpoint. A
     **brand-new** `SqliteCheckpointer` pointed at the same file (a fresh
     connection, no shared Python state) can resume a thread -- that's
     what makes it a legitimate stand-in for a real process restart.
4. **Kill mid-execution, resume from the checkpoint, not from scratch.**
   If a node raises anything other than `Interrupt`, that exception
   propagates out of `run()`/`resume()` uncaught -- no checkpoint gets
   written for the node that was in flight. Calling `resume()` afterward
   picks up exactly at that node; every node that already has a completed
   checkpoint **does not run again** (verified in tests by counting side
   effects, not by reading the code).
5. **`Interrupt`** -- a node raises `Interrupt(payload)` to pause a run
   cleanly. The graph checkpoints `status="interrupted"` with
   `next_node` still pointing at that node, and returns
   `RunResult(status="interrupted", ...)` instead of propagating.
   `resume(thread_id, resume_value=...)` stashes `resume_value` under
   `state[RESUME_KEY]` and re-runs the interrupted node from its first
   line -- which means **any side effect before the `Interrupt` fires a
   second time.** That's not a bug; it's the actual LangGraph contract,
   and it's why idempotency keys on mutating tool calls matter.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Sub-graphs** -- let a node's `fn` itself be a compiled `StateGraph`,
   checkpointed under a nested `checkpoint_ns`, the way LangGraph does for
   reusable multi-agent components. *(Interview: "how do checkpoint
   namespaces avoid collisions between a parent graph and a sub-graph?")*
2. **Idempotency keys** -- fix the non-idempotent-node problem the centre
   test demonstrates: give nodes a way to register a dedupe key so a
   second execution of the same step can detect "I already did this" and
   skip the mutating part while still returning the right update.
3. **Time travel** -- add `StateGraph.get_state_history(thread_id)` and a
   way to re-run from an arbitrary earlier checkpoint (not just the
   latest), the mechanism behind LangGraph Studio's replay/fork feature.
4. **Parallel branches** -- let a conditional router return a *list* of
   next nodes that all run before the next super-step, and decide how
   checkpointing should treat their side effects if one branch crashes
   while another completes.
