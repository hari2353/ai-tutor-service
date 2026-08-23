# Lab 14: Durable Graphs — Checkpointer, interrupt()/HITL, Time Travel

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 60
**Module:** `T07-langgraph-durable`

**You will build:** a mini node-runner with a four-method `MemoryCheckpointer` in pure Python — every completed node is a full state checkpoint keyed `(thread_id, step)`; resume skips completed work; `SimulatedCrash` leaves the last checkpoint intact; `ctx.interrupt()` pauses for a human and `resume()` delivers their answer; `get_state(at_step=k)` is time travel.

**You will be able to answer:** *"Walk me through durable resume — what exactly happens to side effects when a node re-runs after a crash or an interrupt?"*

## Setup

```bash
cd labs/py/14-langgraph-durable
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`MemoryCheckpointer`** — `put` / `put_writes` / `get_tuple` / `list`, keyed `(thread_id, step)`. Stores full state snapshots **plus per-task pending writes**, attached to the step they extend. Deepcopy on write AND read.
2. **`DurableGraph(nodes, edges, checkpointer, thread_id)`** — linear mini-graph (`START → n1 → … → END`). After EVERY node completes it writes the node's pending-write row, then the full snapshot. Completed-node log lives in state meta (`state[META]["completed"]`).
3. **Durable resume** — re-invoking on the same thread loads the last checkpoint and skips every completed node. Prove it with an execution-order log.
4. **Crash injection** — nodes raise `SimulatedCrash` (use the injectable `FlakyCrash(n)`: raises N times, then passes). A crash writes *nothing*; the next invoke converges. Side effects placed before the failure point repeat — that's the lesson.
5. **`ctx.interrupt(payload)`** — halts the run, saves status=`waiting_human` plus the payload; `resume(thread_id, human_input)` injects the value as `ctx.input` and the waiting node **re-runs from its top**. Resuming twice raises `NotWaitingError`.
6. **Time travel** — `get_state(at_step=k)` returns a read-only deep-copied snapshot from history.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Fork** — `update_state(at_step=k, values=...)` that branches a NEW checkpoint chain without touching the original.
2. **`SqliteSaver`** — same four methods backed by sqlite3; drop-in swap proves the interface is the contract.
3. **Parallel super-step with sibling recovery** — two tasks per tick; one crashes; prove the sibling's pending write means it does not re-execute.
4. **Durability modes** — `durability="exit"` (checkpoint only at end) vs `"sync"`; measure how many steps a crash loses under each.
