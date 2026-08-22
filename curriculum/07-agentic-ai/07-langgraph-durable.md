# LangGraph II: Checkpointers, interrupt()/HITL, Durable Resume

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-langgraph-core`, `T07-agent-loop-from-scratch` · **Updated:** 2026-07-26
> **Module id:** `T07-langgraph-durable` · **Tags:** sprint, framework, langgraph
> **Lab:** `labs/py/07-langgraph-durable/`

## The 30-second version

A checkpointer is a four-method interface (`put`, `put_writes`, `get_tuple`, `list`) that writes a snapshot of every channel at every super-step, keyed by `thread_id` and `checkpoint_ns`. That single mechanism is what makes durable resume, human-in-the-loop, time travel, and fault tolerance all the same feature. The reason it matters is arithmetic: reliability is multiplicative, so at 85% per-step success a 10-step agent completes about 20% of the time, and without checkpointing 80% of your runs throw away all the work they'd already done. `interrupt()` exploits the same machinery to pause a node indefinitely and resume it with `Command(resume=value)`. The subtle part, and the thing interviews actually probe: **resume restarts the whole node from its first line**, so any side effect before the interrupt or before the failure point executes again — which makes idempotency keys on mutating tools a correctness requirement, not a nicety. And `InMemorySaver` is a dict in a process; it does not survive a deploy, a pod eviction, or a second replica, so it is a development tool that has caused a lot of production incidents.

## Why this gets asked

Because "we used LangGraph" and "we shipped a durable agent" are different claims, and checkpointing is where they diverge. The interviewer has lived through one of two incidents. Either they shipped `InMemorySaver`, a routine deploy rolled the pods, and every in-flight approval request evaporated — including the ones a human had already approved but not yet resumed. Or they put a `create_ticket` call before an `interrupt()`, the reviewer bounced the request three times, and support ended up with four identical tickets, because nobody had internalised that the node re-runs from the top on every resume. At staff level they will push further and ask what happens to in-flight tool side effects when the process dies mid-super-step, which is the question that separates people who read the docs from people who have paged on it.

---

## Lineage: past → present → future

**What came before.** The first agent frameworks kept state in the process: a Python list of messages inside an `AgentExecutor`, or an in-memory conversation buffer. This works exactly as long as nothing goes wrong. The pain that killed it was not exotic — it was **the ordinary deploy**. An agent doing a 12-step research task, or waiting on a human to approve a refund, is a long-lived stateful object living inside a stateless web process, and every rolling deploy, autoscaler scale-in, spot reclaim, and OOM kill destroys it. Teams' first fix was to serialise the message list into Redis by hand, which fails on the second requirement: you can restore the *messages* but not the *position in the control flow*, so resume means re-running from the top and paying for the whole trajectory again. The second attempt was to pull in a general workflow engine — **AWS Step Functions** (2016) or **Temporal** (open-sourced 2019, from Uber's Cadence, itself descended from Amazon's SWF) — which solved durability properly via event-sourced replay, but had no notion of streaming tokens, no notion of a message list, and required you to structure your agent as a workflow definition with deterministic replay constraints. LangGraph's contribution was noticing that if the runtime already advances in discrete super-steps, then a super-step boundary is a natural, free checkpoint boundary, and durability becomes a property of the runtime rather than a rewrite.

**Where it stands now.** The consensus that **agent state belongs in a database, not a process** is settled; nobody credible argues otherwise in 2026. What is actually deployed: `PostgresSaver`/`AsyncPostgresSaver` for anything real, `SqliteSaver` for local development and single-node tools, `InMemorySaver` for tests. LangSmith's managed Agent Server handles the persistence layer for you, which is a real chunk of its value proposition. Encryption at rest via `EncryptedSerializer` exists and is automatic on LangSmith when `LANGGRAPH_AES_KEY` is present. There are two live disagreements. The first is **checkpoint granularity versus cost**: writing the full value of every channel at every super-step is simple and expensive, and on a long chat thread it's quadratic in storage because the whole growing message list is re-serialised each tick. `DeltaChannel` (beta, requires `langgraph>=1.2`) stores only the per-step delta with `snapshot_frequency=K` to bound read latency, and `durability="exit"|"async"|"sync"` lets you trade consistency for throughput. Both are admissions that the naive model doesn't scale, and neither is the default yet. The second is **LangGraph versus Temporal for the durability layer**. The honest position: LangGraph gives you agent-native primitives (token streaming, `interrupt()`, time travel over a message list) but its durability guarantees are weaker than an event-sourced engine's — notably, it does **not** give you exactly-once side effects, and it says so, telling you to make your operations idempotent. Temporal gives you battle-tested guarantees and mature in-flight visibility but no agent primitives. Teams doing money movement increasingly run both: LangGraph for the reasoning loop, Temporal for the transactional steps.

**Where it's heading.** **High confidence: the runtime is absorbing workflow-engine features.** `1.2.0` (12 May 2026) added cooperative graceful shutdown — `RunControl.request_drain()` stops the run at the next super-step boundary, raises `GraphDrained`, and leaves a resumable checkpoint, which is the correct answer to SIGTERM during a deploy and was previously your problem. Same release added per-node timeouts and node-level `error_handler=` for Saga compensation. **Medium confidence: delta-based checkpointing becomes the default** once `DeltaChannel` leaves beta, because the storage arithmetic on long threads is not defensible otherwise. **Speculative, flagged as such: durable *tool* execution with real exactly-once semantics.** Today LangGraph's answer to "what happens to an in-flight side effect on resume" is "make it idempotent," which pushes the hard part onto you. The obvious next move is a first-class durable-side-effect primitive — a `@task` whose completed result is guaranteed-once from the checkpoint rather than merely cached within a run. The Functional API's `@task` is a step in that direction and works inside `StateGraph` nodes today, but treat "LangGraph gives me exactly-once" as false until the docs say it plainly.

---

## Mental model

Think of the checkpointer as **an append-only event log per thread, where each entry is a full state snapshot plus a pointer to what runs next.**

```
 thread_id = "refund-8812"                  checkpoint_ns = ""  (root graph)

 step  checkpoint_id      values                          next            source
 ────  ─────────────────  ──────────────────────────────  ─────────────   ──────
  -1   1ef663ba-28f0...   {input written}                 ("__start__",)  input
   0   1ef663ba-28f4...   {amount:500, status:"pending"}  ("triage",)     loop
   1   1ef663ba-28f9...   {amount:500, tier:"manual"}     ("approve",)    loop
   2   1ef663ba-28fe...   {... interrupt pending ...}     ("approve",)    loop
                             ▲ tasks[0].interrupts = (Interrupt(value={...}, id=...),)
   3   1ef663ba-2904...   {status:"approved"}             ()              loop
                                                            ▲ empty = done

  ┌── graph.get_state(config) ─────────▶ latest snapshot
  ├── graph.get_state_history(config) ─▶ ALL of them, reverse chronological
  ├── graph.invoke(None, snap.config) ─▶ REPLAY: re-run everything AFTER that step
  └── graph.update_state(snap.config, {..}) ─▶ FORK: new checkpoint branching from there
```

Two things to burn in:

**1. `thread_id` is a cursor, not a name.** Reuse it and you resume that state. Use a new one and you get an empty graph. Most "my agent lost its memory" bugs are a `thread_id` that was regenerated per HTTP request.

**2. Resume means "re-run the node," not "resume the line."**

```
   node body:   ┌────────────────────────────────────────────────┐
                │ 1  audit = db.insert_audit_row(...)   ← RE-RUNS│
                │ 2  decision = interrupt({"approve?": ...})     │
                │ 3  if decision: db.charge(...)                 │
                └────────────────────────────────────────────────┘
   first call:  lines 1, then 2 raises GraphBubbleUp → checkpoint → return
   resume:      lines 1 AGAIN, 2 returns the resume value, then 3
                            ▲
                  a second audit row. every resume. forever.
```

That diagram is the module. Everything else is detail.

---

## How it actually works

### 1. The checkpointer interface

Every checkpointer implements `BaseCheckpointSaver` with four methods (plus async twins used automatically by `ainvoke`/`astream`/`abatch`):

| Method | Purpose | Surfaces as |
|---|---|---|
| `.put(config, checkpoint, metadata, versions)` | store a full state snapshot | one write per super-step |
| `.put_writes(config, writes, task_id)` | store per-task intermediate writes | **pending writes** recovery |
| `.get_tuple(config)` | fetch by `thread_id` (+ optional `checkpoint_id`) | `graph.get_state()` |
| `.list(config, filter=...)` | enumerate matching checkpoints | `graph.get_state_history()` |

Async variants: `.aput`, `.aput_writes`, `.aget_tuple`, `.alist`.

`put_writes` is the one people don't know exists and it's worth a whole answer. Within one super-step, as each node finishes, its writes are persisted as task rows *before* the super-step's full snapshot is committed. So if nodes `A`, `B`, `C` run in parallel and `C` throws, `A` and `B`'s writes are already durable and **do not re-execute** on resume. Only `C` re-runs. That is the difference between "resume the failed node" and "resume the failed tick."

### 2. The four checkpointers, and why one of them is a trap

| Checkpointer | Package | Survives process exit | Survives deploy | Multi-replica | Use |
|---|---|---|---|---|---|
| `InMemorySaver` | `langgraph-checkpoint` (bundled) | **no** | **no** | **no** | tests, notebooks |
| `SqliteSaver` / `AsyncSqliteSaver` | `langgraph-checkpoint-sqlite` | yes (file) | only if the file does | **no** (single writer) | local dev, single-node CLI |
| `PostgresSaver` / `AsyncPostgresSaver` | `langgraph-checkpoint-postgres` | yes | yes | yes | **production** |
| `ShallowPostgresSaver` | same | yes | yes | yes | latest-only; **no time travel** |
| `CosmosDBSaver` | `langchain-azure-cosmosdb` | yes | yes | yes | production on Azure |

**Why `InMemorySaver` does not survive a deploy, spelled out.** It is a Python dict in the process's heap. A rolling deploy replaces the container; a Kubernetes rollout sends SIGTERM and starts a new pod; an autoscaler scale-in evicts; a spot instance gets reclaimed; the OOM killer fires. In every case the heap goes away and every thread's state with it. Two consequences people underestimate:

- **Any HITL flow is broken by construction**, because an approval is by definition a wait that spans requests. The gap between "surface the interrupt to a human" and "human clicks approve" is minutes to days, and every deploy in that window silently drops the pending request. The observable symptom is `Command(resume=...)` on a `thread_id` the checkpointer has never heard of, so the graph starts from scratch and the approval is silently ignored — no exception, just wrong behaviour.
- **It breaks at two replicas even without a restart.** Request 1 hits pod A and creates the thread; the resume request load-balances to pod B, which has an empty dict. Works perfectly in dev with one process. Fails nondeterministically the moment you scale, which makes it look like a flaky bug rather than an architecture error.

`ShallowPostgresSaver` is the other quiet trap: it keeps only the latest checkpoint per thread. Cheap, durable, resumable — and `get_state_history()` gives you nothing, so no time travel and no forking. Choose it deliberately.

### 3. `thread_id` and checkpoint namespacing

```python
config = {"configurable": {"thread_id": "refund-8812"}}          # required
config = {"configurable": {"thread_id": "refund-8812",
                           "checkpoint_id": "1ef663ba-28f9-..."}}  # a specific point
```

`thread_id` is the primary key. Without it a checkpointer cannot save or resume, and `interrupt()` cannot work at all. Operationally it is the join key between your agent state and everything else you own, so pick it deliberately: derive it from a business entity (`refund-8812`, `ticket-4471`) rather than generating a UUID per request, and note it can be a PII vector — don't put an email address in it.

`checkpoint_ns` identifies which graph a checkpoint belongs to:

- `""` — the root graph.
- `"node_name:uuid"` — a subgraph invoked as that node.
- nested subgraphs join with `|`: `"outer:uuid|inner:uuid"`.

Readable from inside a node via `config["configurable"]["checkpoint_ns"]`. Two practical consequences. First, **renaming a node changes the namespace**, so interrupted threads that were about to enter it break — the docs explicitly say topology changes are safe for *completed* threads but renaming or removing nodes is not safe for *interrupted* ones. Second, **per-thread subgraphs called in parallel collide**, because two concurrent calls to the same subgraph write the same namespace; the documented fix is to wrap each subagent in its own `StateGraph` with a unique node name so the namespace is stable and distinct, or to prevent parallel calls.

### 4. Reading, replaying, forking

```python
snap = graph.get_state(config)              # StateSnapshot
snap.values         # channel values
snap.next           # tuple of node names to run next; () means complete
snap.metadata       # {"source": "input"|"loop"|"update", "writes": {...}, "step": n}
snap.parent_config  # previous checkpoint's config; None for the first
snap.tasks          # tuple[PregelTask]: .id .name .error .interrupts [.state]

history = list(graph.get_state_history(config))     # reverse chronological

before_charge = next(s for s in history if s.next == ("charge_card",))
step_2        = next(s for s in history if s.metadata["step"] == 2)
forks         = [s for s in history if s.metadata["source"] == "update"]
interrupted   = next(s for s in history if s.tasks and any(t.interrupts for t in s.tasks))
```

**Replay** — re-run from a prior point with the same state:

```python
graph.invoke(None, before_charge.config)
```

Nodes *before* that checkpoint are skipped; their results are already saved. Nodes *after* it **genuinely re-execute** — this is not a cache replay. LLM calls fire again (and may answer differently), API calls fire again, and interrupts are always re-triggered. Replaying from the final checkpoint (`next == ()`) is a no-op.

**Fork** — branch with modified state:

```python
fork_cfg = graph.update_state(before_charge.config, values={"amount": 250})
graph.invoke(None, fork_cfg)
```

`update_state` does **not** roll back. It creates a *new* checkpoint branching from the specified one; the original history stays intact, which is what makes this an audit-friendly operation. Two subtleties:

- Values pass through **reducers**, so a channel with `operator.add` *accumulates* your update rather than replacing it. Wrap in `Overwrite(...)` if you meant to replace.
- `as_node="generate_topic"` controls which node the update is attributed to, and therefore which node runs next (that node's successors). LangGraph infers it from version history and is usually right; specify it explicitly when parallel branches wrote in the same step (otherwise `InvalidUpdateError`), when the thread has no history (test setup), or when you want to skip a node by pretending it already ran.

### 5. `interrupt()` and resuming with `Command`

```python
from langgraph.types import interrupt, Command

def approve(state: State) -> Command[Literal["charge", "cancel"]]:
    decision = interrupt({                    # must be JSON-serialisable
        "question": "Approve this refund?",
        "amount": state["amount"],
        "customer": state["customer_id"],
    })
    return Command(goto="charge" if decision else "cancel")
```

Mechanically: `interrupt()` raises a special `GraphBubbleUp` exception that the runtime catches. It writes the checkpoint, surfaces the payload, and waits **indefinitely**. Requirements: a checkpointer, a `thread_id`, and a JSON-serialisable payload.

Reading the payload depends on your API version:

```python
# v1 invoke
result = graph.invoke(inp, config)
if "__interrupt__" in result:
    print(result["__interrupt__"][0].value)

# v2 invoke → GraphOutput
result = graph.invoke(inp, config, version="v2")
if result.interrupts:
    print(result.interrupts[0].value)

# v3 event streaming (langgraph >= 1.2, recommended for new code)
stream = graph.stream_events(inp, config=config, version="v3")
_ = stream.output                       # drive the stream to completion
if stream.interrupted:
    print(stream.interrupts)            # (Interrupt(value=..., id=...),)
```

Resume by re-invoking with `Command(resume=value)` on the **same** `thread_id`. The value becomes the return of `interrupt()`.

```python
graph.invoke(Command(resume=True), config)
```

**`Command(resume=...)` is the only `Command` form meant as graph *input*.** Passing `Command(update={...})` as input to continue a conversation is a documented trap: any `Command` input resumes from the latest checkpoint rather than `__start__`, so on a finished thread the graph appears stuck and does nothing. To continue a conversation, pass a plain dict.

**Parallel interrupts.** If two fan-out branches both call `interrupt()`, you get two pending `Interrupt` objects and must map each `id` to its answer:

```python
resume_map = {i.id: answer_for(i.value) for i in stream.interrupts}
graph.stream_events(Command(resume=resume_map), config, version="v3")
```

### 6. The four rules of `interrupt()` (each one is a real bug)

**Rule 1 — never wrap `interrupt()` in a bare `try/except`.** It works by raising. A bare `except Exception` swallows the pause signal and the interrupt silently never reaches the caller. Catch specific exception types, or put the interrupt outside the try block.

```python
# BAD — the pause is swallowed
try:
    name = interrupt("What's your name?")
except Exception as e:
    log.warning(e)

# GOOD — specific exception type doesn't catch GraphBubbleUp
try:
    name = interrupt("What's your name?")
    fetch_data()
except NetworkError as e:
    log.warning(e)
```

**Rule 2 — never reorder or conditionally skip interrupts within a node.** Resume values are matched to `interrupt()` calls **strictly by index** within the node's task. Skip the second interrupt on one run and the third call receives the second answer. So no `if state.get("needs_age"): age = interrupt(...)`, and no loops over a list whose length changes between executions.

**Rule 3 — payloads must be JSON-serialisable.** No functions, no class instances. Dicts of primitives.

**Rule 4 — side effects before `interrupt()` must be idempotent.** This is the one that costs money. Covered next.

For **debugging** — as opposed to HITL — use static breakpoints, `compile(interrupt_before=["charge"], interrupt_after=["triage"])` or the same arguments at runtime, and resume with `graph.invoke(None, config)`. The docs are explicit that static interrupts are *not* recommended for human-in-the-loop; use `interrupt()`.

### 7. In-flight side effects on resume — the subtle part

This is the staff-level question. Three distinct cases, and they behave differently.

**Case A: the node completed, a *sibling* in the same super-step failed.** Safe. `put_writes` already persisted the successful node's writes as a task row, so on resume it is not re-executed. This is the pending-writes mechanism and it is the one case LangGraph handles for you.

**Case B: the node itself failed part-way through.** Its side effects up to the failure point already happened in the world. The graph resumes **from the beginning of that node** — LangGraph says this explicitly — so every side effect before the failure point happens a second time. A node that does `charge_card()` then `send_receipt()` and fails in `send_receipt` charges the card twice on resume.

**Case C: `interrupt()` in the middle of a node.** Same as B but worse, because it's not an error path — it's the *designed* path, and a validation loop that re-prompts three times re-runs the pre-interrupt code three times.

The mitigations, in order of preference:

1. **Move side effects after the interrupt, or into their own node.** A node that only interrupts and returns the decision is trivially safe. The mutation happens in the next node, which runs exactly once after the decision is durable. This is free and it is the right default.
2. **Make the operation idempotent.** `db.upsert_user(id, status="pending")` is safe to repeat; `db.insert_audit_row(...)` is not. Prefer upsert-by-natural-key over insert.
3. **Idempotency keys on anything you can't make naturally idempotent.** Derive the key deterministically from state so it's identical across re-runs — `f"{thread_id}:{checkpoint_id}:charge"` — and have the server store `(key → result)` so a repeat returns the stored result rather than acting twice. Store it atomically (`INSERT ... ON CONFLICT DO NOTHING` and check the affected-row count), never read-then-write, and set the TTL longer than your maximum human-approval window, which for an interrupt could be days.
4. **Wrap the operation in a `@task`.** From `langgraph.func`, usable inside `StateGraph` nodes: on replay the recorded result is retrieved from the persistence layer rather than re-executed. The docs' own caveat is the one to quote: if a task *starts but fails to complete*, resumption re-runs it — so this reduces duplicate work but is **not** exactly-once, and you still need idempotency for correctness.

The honest summary, and the sentence to say in an interview: **LangGraph gives you at-least-once side effects and tells you to make them idempotent. If you need exactly-once, that's a property of the downstream system, not of the orchestrator.**

### 8. Durability modes and graceful shutdown

```python
graph.stream({"input": "..."}, config, durability="sync")
```

| Mode | Writes when | Crash mid-execution | Cost |
|---|---|---|---|
| `"exit"` | only on exit (success, error, or interrupt) | **lose everything** since start | fastest |
| `"async"` | asynchronously while the next step runs | small window of loss | good default |
| `"sync"` | synchronously before the next step starts | nothing lost | slowest |

`"exit"` still supports HITL (an interrupt counts as an exit) but gives you no crash recovery, so it's for long graphs where you care about latency more than mid-run failure. `"sync"` is the choice when a step has external side effects and you must know the checkpoint landed before the next step runs.

**Graceful shutdown** (`langgraph>=1.2`, alpha) is the correct answer to "SIGTERM during a deploy":

```python
import signal
from langgraph.runtime import RunControl
from langgraph.errors import GraphDrained

control = RunControl()
signal.signal(signal.SIGTERM, lambda *_: control.request_drain("sigterm"))

try:
    result = graph.invoke(inputs, config, control=control)
except GraphDrained as e:
    log.info("drained: %s", e.reason)     # checkpoint saved; resume on next boot
```

Drain is **cooperative and operates between super-steps** — it never preempts running work:

| Situation | Behaviour |
|---|---|
| Node mid-execution | runs to completion; drain applies at the next super-step |
| Node in a retry loop | retries run to exhaustion or success first |
| Graph finishes on the same tick | returns normally; check `control.drain_requested` |
| More super-steps remain | raises `GraphDrained`, checkpoint saved and resumable |
| Subgraph requests drain | bubbles up; parent stops at *its* next boundary |

Resume with `graph.invoke(None, config)` on the same `thread_id`. Inside a node you can read `runtime.drain_requested` and skip expensive work early. Note `request_drain()` does **not** cancel asyncio tasks or kill threads, so pair it with a hard timeout if you need a real upper bound.

### 9. Recovering from a failure

```python
try:
    graph.invoke(inp, config)
except Exception:
    ...                                  # alert, inspect graph.get_state(config)
graph.invoke(None, config)               # resume from the last checkpoint
```

`invoke(None, config)` is the universal resume: it applies after a crash, after a drain, and after a static breakpoint. `Command(resume=v)` is specifically for an `interrupt()` waiting on a value.

---

## Build it from scratch

A minimal checkpointer proves how little the interface is. Writing this makes the `put_writes` / pending-writes distinction concrete.

```python
# untested sketch — illustrative, mirrors the BaseCheckpointSaver shape
import json, sqlite3, uuid
from dataclasses import dataclass, field

@dataclass
class Snapshot:
    values: dict
    next: tuple
    checkpoint_id: str
    parent_id: str | None
    step: int

class TinySaver:
    """Two tables, exactly like the real thing: snapshots and per-task writes."""
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS checkpoints(
            thread_id TEXT, ns TEXT, checkpoint_id TEXT, parent_id TEXT,
            step INT, blob TEXT, PRIMARY KEY(thread_id, ns, checkpoint_id));
          CREATE TABLE IF NOT EXISTS checkpoint_writes(
            thread_id TEXT, ns TEXT, checkpoint_id TEXT, task_id TEXT,
            blob TEXT, PRIMARY KEY(thread_id, ns, checkpoint_id, task_id));
        """)
        self.db.commit()

    def put(self, cfg, values, next_nodes, parent_id, step) -> str:
        cid = str(uuid.uuid4())
        self.db.execute("INSERT INTO checkpoints VALUES (?,?,?,?,?,?)",
                        (cfg["thread_id"], cfg.get("ns", ""), cid, parent_id, step,
                         json.dumps({"values": values, "next": list(next_nodes)})))
        self.db.commit()
        return cid

    def put_writes(self, cfg, cid, task_id, writes):
        """Per-node durability WITHIN a super-step. This is what stops a
        successful sibling node re-running when another node in the tick fails."""
        self.db.execute("INSERT OR REPLACE INTO checkpoint_writes VALUES (?,?,?,?,?)",
                        (cfg["thread_id"], cfg.get("ns", ""), cid, task_id,
                         json.dumps(writes)))
        self.db.commit()

    def get_tuple(self, cfg) -> Snapshot | None:
        if cid := cfg.get("checkpoint_id"):
            row = self.db.execute(
                "SELECT checkpoint_id,parent_id,step,blob FROM checkpoints "
                "WHERE thread_id=? AND ns=? AND checkpoint_id=?",
                (cfg["thread_id"], cfg.get("ns", ""), cid)).fetchone()
        else:
            row = self.db.execute(
                "SELECT checkpoint_id,parent_id,step,blob FROM checkpoints "
                "WHERE thread_id=? AND ns=? ORDER BY step DESC LIMIT 1",
                (cfg["thread_id"], cfg.get("ns", ""))).fetchone()
        if not row:
            return None
        cid, parent, step, blob = row
        d = json.loads(blob)
        return Snapshot(d["values"], tuple(d["next"]), cid, parent, step)

    def list(self, cfg):
        for cid, parent, step, blob in self.db.execute(
                "SELECT checkpoint_id,parent_id,step,blob FROM checkpoints "
                "WHERE thread_id=? AND ns=? ORDER BY step DESC",
                (cfg["thread_id"], cfg.get("ns", ""))):
            d = json.loads(blob)
            yield Snapshot(d["values"], tuple(d["next"]), cid, parent, step)
```

The lab at `labs/py/07-langgraph-durable/` builds this against the mini-Pregel from `T07-langgraph-core`, then adds: resume after an injected crash, `interrupt()` via a sentinel exception, replay from an arbitrary snapshot, fork with `as_node`, and a test that proves a non-idempotent pre-interrupt side effect fires twice. Writing that last test is the point of the lab.

---

## How it's done in production

A Postgres-backed graph with a real HITL approval gate. Every line marked is load-bearing.

```python
# untested sketch — API verified against docs.langchain.com + langgraph.checkpoint.postgres
#                    reference, accessed 2026-07-26
# pip install -U "langgraph>=1.2" langgraph-checkpoint-postgres "psycopg[binary,pool]"
import os
from typing import Literal
from typing_extensions import TypedDict

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.types import Command, interrupt, RetryPolicy

# Restrict deserialisation so a compromised checkpoint store cannot execute code.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

DB_URI = os.environ["CHECKPOINT_DB_URI"]   # postgresql://.../agents?sslmode=require

# autocommit=True  -> required or .setup() may not persist the DDL
# row_factory=dict_row -> required; the saver reads rows as row["col"], and the default
#   tuple_row raises: TypeError: tuple indices must be integers or slices, not str
pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=2,
    max_size=20,
    kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
)

serde = EncryptedSerializer.from_pycryptodome_aes()      # reads LANGGRAPH_AES_KEY
checkpointer = PostgresSaver(pool, serde=serde)
checkpointer.setup()          # idempotent; creates checkpoints, checkpoint_blobs,
                              # checkpoint_writes, checkpoint_migrations. Run ONCE per
                              # deploy (a migration job), not on every worker boot.


class RefundState(TypedDict):
    refund_id: str
    customer_id: str
    amount_cents: int
    tier: Literal["auto", "manual"]
    status: Literal["pending", "approved", "rejected", "settled"]
    reason: str


def triage(state: RefundState):
    tier = "manual" if state["amount_cents"] > 100_00 else "auto"
    return {"tier": tier}


def route(state: RefundState) -> Literal["approve", "settle"]:
    return "approve" if state["tier"] == "manual" else "settle"


def approve(state: RefundState) -> Command[Literal["settle", "reject"]]:
    # NOTHING mutating happens before the interrupt. The node re-runs from the top
    # on EVERY resume, so a db.insert() here would duplicate per resume.
    decision = interrupt({
        "action": "approve_refund",
        "refund_id": state["refund_id"],
        "amount_cents": state["amount_cents"],
        "customer_id": state["customer_id"],
        "prompt": "Approve this refund?",
    })
    if decision.get("approved"):
        return Command(update={"status": "approved"}, goto="settle")
    return Command(update={"status": "rejected",
                           "reason": decision.get("reason", "")}, goto="reject")


def settle(state: RefundState, config):
    # Side effect lives in its OWN node, after the decision is durable.
    # Key is derived from (thread, checkpoint) so it is identical across re-runs.
    key = f"{config['configurable']['thread_id']}:" \
          f"{config['configurable']['checkpoint_id']}:settle"
    payments.refund(                      # server dedups on Idempotency-Key
        customer_id=state["customer_id"],
        amount_cents=state["amount_cents"],
        idempotency_key=key,
    )
    return {"status": "settled"}


def reject(state: RefundState):
    return {"status": "rejected"}


builder = StateGraph(RefundState)
builder.add_node("triage", triage)
builder.add_node("approve", approve)
builder.add_node("settle", settle, retry_policy=RetryPolicy(max_attempts=3))
builder.add_node("reject", reject)
builder.add_edge(START, "triage")
builder.add_conditional_edges("triage", route, ["approve", "settle"])
builder.add_edge("settle", END)
builder.add_edge("reject", END)

graph = builder.compile(checkpointer=checkpointer)

# ---- request 1: start the run, hit the approval gate -----------------------
cfg = {"configurable": {"thread_id": "refund-8812"}}    # a BUSINESS id, not a UUID
out = graph.invoke(
    {"refund_id": "8812", "customer_id": "c-771", "amount_cents": 45_000,
     "tier": "auto", "status": "pending", "reason": ""},
    cfg,
    durability="sync",      # money is involved; know the checkpoint landed
)
if "__interrupt__" in out:
    payload = out["__interrupt__"][0].value
    enqueue_review_task(payload)          # notify a human; do NOT block a worker

# ---- request N (minutes or days later, DIFFERENT process, DIFFERENT pod) ----
graph.invoke(Command(resume={"approved": True}), cfg, durability="sync")

# ---- audit / debug --------------------------------------------------------
for snap in graph.get_state_history(cfg):
    print(snap.metadata["step"], snap.metadata["source"], snap.next, snap.values["status"])
```

**Why this survives a deploy and `InMemorySaver` doesn't:** every super-step is a row in Postgres, `thread_id` is `refund-8812` regardless of which pod handles the resume, and the human's approval arrives as a fresh HTTP request that any replica can serve.

### Operational details that bite

- **`setup()` in a migration job, not on worker boot.** It's idempotent (it maintains a `checkpoint_migrations` table), but N workers racing DDL on cold start is avoidable noise, and in a locked-down environment your app role may not have DDL rights at all.
- **`autocommit=True` and `row_factory=dict_row` are mandatory** when you pass your own connection or pool. Without `autocommit`, `setup()` may not persist the tables. Without `dict_row`, every read raises `TypeError: tuple indices must be integers or slices, not str`, because the implementation accesses columns by name.
- **`AsyncPostgresSaver` for async graphs.** If you run `ainvoke`/`astream`, the runtime calls `aput`/`aget_tuple`; using the sync saver blocks the event loop under load. Same for `AsyncSqliteSaver`.
- **Encryption is opt-in.** Checkpoints contain full prompts, tool arguments, and model outputs in plaintext by default. `EncryptedSerializer.from_pycryptodome_aes()` reads `LANGGRAPH_AES_KEY`; on LangSmith it's automatic when the env var is present. If your state ever contains customer data, this is a compliance question, not a preference.
- **`LANGGRAPH_STRICT_MSGPACK=true`** (or an explicit `allowed_msgpack_modules` list) restricts deserialisation to known-safe types. The package README calls this out as a security requirement, because a compromised checkpoint store is otherwise a code-execution path into your workers.
- **Retention.** Nothing prunes checkpoints. A chat product with 100k threads × 30 super-steps × a growing message list will surprise you. Plan a TTL/archival job from day one, and note that pruning history kills time travel for those threads.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Approvals vanish after every deploy | `InMemorySaver`; heap died with the pod | `PostgresSaver` |
| Resume works locally, fails ~50% in staging | `InMemorySaver` + 2 replicas; resume hit the other pod | `PostgresSaver` |
| `Command(resume=...)` silently starts a new run | `thread_id` regenerated per request, or thread unknown | derive `thread_id` from a business entity; assert the thread exists |
| Duplicate tickets/charges per human retry | mutating call *before* `interrupt()`; node re-runs from the top | move it after, or its own node; idempotency key |
| `interrupt()` never surfaces to the caller | wrapped in a bare `try/except`, which caught `GraphBubbleUp` | catch specific exception types only |
| Wrong answer applied to the wrong question | interrupts conditionally skipped/reordered; matching is index-based | keep interrupt order fixed and unconditional |
| `TypeError: tuple indices must be integers...` | custom connection without `row_factory=dict_row` | set it (and `autocommit=True`) |
| Tables missing after first run | `setup()` never called, or called without `autocommit=True` | migration job runs `setup()` |
| Time travel returns nothing | `ShallowPostgresSaver` keeps only the latest checkpoint | `PostgresSaver` |
| Can't time-travel into a subgraph | inherited checkpointer treats it as one parent super-step | give the subgraph `checkpointer=True` |
| Checkpoint writes dominate p99 latency | `durability="sync"` on a hot path; full channel re-serialised each tick | `"async"`; `DeltaChannel` (beta, ≥1.2); keep blobs out of state |
| Everything lost on a crash despite a checkpointer | `durability="exit"` | `"async"` or `"sync"` |
| Checkpoint table growing without bound | no retention policy | TTL/archival job |
| Interrupted threads break after a refactor | a node was renamed or removed | topology changes are safe for completed threads only; drain first |
| Parallel calls to one subagent conflict | per-thread subgraph (`checkpointer=True`), one namespace | prevent parallel calls, or wrap each in its own uniquely-named `StateGraph` |
| SIGTERM kills mid-run work | no drain handling | `RunControl.request_drain()`, catch `GraphDrained`, resume on boot |

### The arithmetic that justifies all of it

Reliability is multiplicative. Per-step success `p` over `n` steps gives `p^n`:

| `p` | n=5 | n=10 | n=20 | n=50 |
|---|---|---|---|---|
| 0.99 | 95% | 90% | 82% | 61% |
| 0.95 | 77% | **60%** | 36% | 8% |
| 0.85 | 44% | **20%** | 4% | 0.03% |
| 0.70 | 17% | 3% | 0.08% | ~0% |

**0.85^10 ≈ 20%** is the number to have memorised. It means that on a 10-step agent whose steps succeed 85% of the time — an entirely ordinary figure once real network calls and flaky third-party APIs are involved — **four runs in five fail somewhere**. Without checkpointing every one of those discards all completed work and you pay for the whole trajectory again on retry; expected cost per successful completion is roughly `1/0.20 = 5×` the cost of one clean run. With checkpointing, a failure at step 8 resumes at step 8, so a retry costs the remaining steps rather than all of them, and the same reliability produces a completion rate close to 1 after a couple of retries. That is the entire business case, and it also explains why per-node `RetryPolicy` and checkpointing are complements rather than alternatives: retry raises `p`, checkpointing makes failures cheap.

---

## Tradeoffs & when NOT to use it

- **`durability="sync"` on a chat turn is the wrong trade.** You're adding a synchronous DB round-trip per super-step to protect against a process crash inside a two-second interaction that the user will simply retry. Use `"async"` there and reserve `"sync"` for steps with real external side effects.
- **Don't checkpoint a stateless request/response.** A single-shot classification or extraction has nothing to resume. The checkpointer is pure overhead: a write per super-step, a table that grows, and a retention policy to own.
- **`interrupt()` is not a UI.** It's a durable pause. If the human is available synchronously, an inline confirmation is simpler and you skip a persistence round-trip. `interrupt()` earns its cost when the wait spans requests, processes, or days — and at that point you also need a notification path and a queue, because the graph waits indefinitely and nothing tells the human they have work.
- **Time travel is a debugging and exploration tool, not a rollback.** Replay re-executes LLM calls and API calls; forking creates a new branch and leaves the original intact. Do not reach for it as a compensation mechanism for a side effect that already happened — that's a Saga, and 1.2's node-level `error_handler=` returning a `Command` is the intended primitive.
- **If you need exactly-once side effects or cross-service compensation, LangGraph is the wrong layer.** It documents at-least-once and tells you to be idempotent. Temporal or Restate gives you real guarantees, mature in-flight visibility, and a decade of operational history. The pragmatic architecture for money movement is LangGraph for the reasoning loop and a durable engine for the transactional steps.
- **Full-value checkpointing is quadratic in a growing channel.** Every super-step re-serialises the whole message list. On a 200-turn thread that's a real storage and latency bill. `DeltaChannel` addresses it but is beta at `>=1.2`; until then, keep large payloads out of state.
- **The checkpoint store is a security surface.** Plaintext prompts, tool arguments, and outputs unless you configure `EncryptedSerializer`, plus a deserialisation path unless you set `LANGGRAPH_STRICT_MSGPACK`. Treat it as a system of record containing customer data, because it is one.

---

## Interview questions

### Q1 — What is a checkpointer, and what does one checkpoint actually contain?
**Testing:** baseline. The follow-ups carry the score.
**Answer:** An implementation of `BaseCheckpointSaver` that persists a snapshot of graph state at every super-step, keyed by `thread_id` and `checkpoint_ns`. A checkpoint is a `StateSnapshot`: `values` (all channel values), `next` (nodes to run next — empty tuple means complete), `config` (thread id, namespace, checkpoint id), `metadata` (`source` ∈ input/loop/update, the `writes` that produced it, and the `step` counter), `created_at`, `parent_config`, and `tasks` (each with `id`, `name`, `error`, `interrupts`).
**Follow-up trap:** *"How many checkpoints for `START → A → B → END`?"* — **four.** One for the input at step −1, one at step 0 with the input applied and `A` next, one at step 1 with `A`'s output and `B` next, one at step 2 with `B`'s output and `next == ()`. People say two because they count nodes.

### Q2 — Name the checkpointer implementations and when you'd use each.
**Answer:** `InMemorySaver` (bundled in `langgraph-checkpoint`) for tests and notebooks. `SqliteSaver`/`AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`) for local dev and single-node tools. `PostgresSaver`/`AsyncPostgresSaver` (`langgraph-checkpoint-postgres`) for production. `ShallowPostgresSaver` when you want durability without history. `CosmosDBSaver` from `langchain-azure-cosmosdb` on Azure. Match the async variant to `ainvoke`/`astream`, or you block the event loop.
**Follow-up trap:** *"What's actually wrong with `ShallowPostgresSaver`?"* — it keeps only the latest checkpoint per thread. Durable and resumable, but `get_state_history()` is empty, so no time travel, no forking, and no audit trail of how the thread reached its current state. Fine for a stateless-ish chatbot, wrong the moment someone asks "why did the agent do that."

### Q3 — Why doesn't `InMemorySaver` survive a deploy?
**Testing:** whether you understand it as a process-lifetime problem, not a config flag.
**Answer:** It's a Python dict on the process heap. A rolling deploy replaces the container, a K8s rollout SIGTERMs the pod, an autoscaler evicts, a spot node is reclaimed, the OOM killer fires — in every case the heap and all thread state go with it. Any HITL flow is broken by construction, because an approval is a wait spanning requests, and every deploy in that window silently drops pending approvals.
**Follow-up trap:** *"And what if you never deploy?"* — it still breaks at two replicas. Request 1 creates the thread on pod A; the resume load-balances to pod B, whose dict is empty. That's the nastier version because it's nondeterministic and looks like a flaky bug rather than an architecture error. The observable symptom is `Command(resume=...)` on an unknown thread: no exception, the graph just starts over and the approval is ignored.

### Q4 — What is `thread_id` operationally, beyond "which conversation is this"?
**Answer:** It's the checkpointer's primary key and effectively a durable cursor. Reuse it and you resume that state; use a new one and you get an empty graph. It's the join key between agent state and the rest of your system, so derive it from a business entity (`refund-8812`) rather than minting a UUID per request. It's also a PII surface — don't use an email address — and a multi-tenancy boundary, so a thread id must not be guessable across tenants.
**Follow-up trap:** *"What's `checkpoint_ns`?"* — the namespace identifying which graph a checkpoint belongs to: `""` for the root, `"node_name:uuid"` for a subgraph invoked as that node, joined with `|` when nested. Two consequences: renaming a node changes the namespace and breaks interrupted threads that were about to enter it, and two parallel calls to the same per-thread subgraph collide because they write the same namespace.

### Q5 — Walk me through `interrupt()` and resuming.
**Answer:** `interrupt(payload)` raises a special `GraphBubbleUp` exception the runtime catches; it writes the checkpoint, surfaces the payload (`result["__interrupt__"]` with v1 invoke, `result.interrupts` with v2, `stream.interrupts` with `stream_events(version="v3")`), and waits indefinitely. You resume by re-invoking with `Command(resume=value)` on the same `thread_id`; that value becomes the return of the `interrupt()` call. Requirements: a checkpointer, a `thread_id`, a JSON-serialisable payload.
**Follow-up trap:** *"What happens to the code before the `interrupt()` call on resume?"* — **it runs again.** The runtime restarts the node from its first line, not from the interrupt. That's the single most important fact about `interrupt()` and everything else follows from it.

### Q6 — Given that, how do you write a node containing `interrupt()`?
**Answer:** Four rules. (1) No mutating side effects before the interrupt — move them after, or into a separate node, which is the right default and free. (2) Never wrap the interrupt in a bare `try/except`; it works by raising, so `except Exception` swallows the pause and the interrupt silently never surfaces. Catch specific types. (3) Never conditionally skip or reorder interrupts within a node — resume values are matched **strictly by index** within the task, so skipping one makes the next answer land on the wrong question. (4) Payload must be JSON-serialisable: no functions, no class instances.
**Follow-up trap:** *"Show me the validation-loop case."* — `while True: answer = interrupt(prompt); if valid(answer): break` is fine *because the interrupt is unconditional at a fixed position*, but every re-prompt re-runs the whole node body from the top. A three-attempt validation loop runs pre-interrupt code three times. Keep that body pure.

### Q7 — A process dies mid-super-step with three nodes running in parallel. What happens on resume?
**Testing:** whether you know `put_writes` exists.
**Answer:** Nodes that completed had their writes persisted as **pending writes** via `put_writes` at the task level, before the super-step's full snapshot committed. On resume those nodes are **not** re-executed; their writes are already durable. Only the failed node re-runs, and it re-runs from its beginning. That's `checkpoint_writes` in the Postgres schema.
**Follow-up trap:** *"So the failed node's partial side effects?"* — already happened in the world and will happen again, because resume restarts the node from line one. Pending writes protect *siblings*, not the failing node itself. If it did `charge_card()` then failed in `send_receipt()`, resume charges the card twice unless that call is idempotent or keyed.

### Q8 — What happens to in-flight tool side effects on resume, and what do you do about it?
**Testing:** the staff-level question in this module.
**Answer:** Three cases. A sibling in the same super-step completed: safe, pending writes cover it. The node itself failed part-way: everything before the failure point re-executes. `interrupt()` mid-node: same, but on the designed path, once per resume. Mitigations in order: move side effects after the interrupt or into their own node; make operations naturally idempotent (upsert, not insert); attach idempotency keys derived deterministically from state — `f"{thread_id}:{checkpoint_id}:charge"` — with the server storing `(key → result)` atomically and a TTL longer than your maximum approval window, which for an interrupt could be days; and wrap unavoidable side effects in a `@task` so a completed result is retrieved from persistence on replay rather than recomputed.
**Follow-up trap:** *"So does LangGraph give you exactly-once?"* — **no, and saying yes fails the question.** The docs are explicit: if a task starts but fails to complete, resumption re-runs it. LangGraph gives at-least-once and instructs you to make side effects idempotent. Exactly-once is a property of the downstream system. If you genuinely need it, that's a durable execution engine with transactional activities, or an idempotency layer you own.

### Q9 — What's the difference between checkpointing and durable execution?
**Answer:** Checkpointing is the mechanism — persist state at each super-step. Durable execution is the property you get from it: a workflow can pause and resume exactly where it left off, across process death or a week of human latency. LangGraph's framing is that if you compiled with a checkpointer you already have durable execution, subject to two constraints it names: your workflow must be **deterministic** on replay, and side effects should be **idempotent**, with non-deterministic operations wrapped in tasks or nodes.
**Follow-up trap:** *"So when would you still reach for Temporal?"* — when durability spans hours to days across multiple services, when you need cross-service compensation with real guarantees, when you need mature visibility into in-flight workflows, or when the org already runs it. LangGraph's advantage is agent-native primitives: token streaming, `interrupt()`, time travel over a message list. Note 1.2 added per-node timeouts, error handlers, and graceful drain — LangGraph moving toward Temporal, which tells you where the gap has been.

### Q10 — Explain the three durability modes and pick one for a payments agent.
**Answer:** `"exit"` writes only when execution exits (success, error, or interrupt) — fastest, no mid-run crash recovery. `"async"` writes asynchronously while the next step runs — good default, small window where a crash loses the last write. `"sync"` writes before the next step starts — highest durability, most overhead. For a payments agent, `"sync"` at least around the mutating steps: you need to know the checkpoint landed before the side effect runs, so that a crash between them resumes into a state consistent with the world.
**Follow-up trap:** *"Does `'exit'` break human-in-the-loop?"* — no, an interrupt counts as an exit, so the pause is persisted. What `"exit"` loses is recovery from a *crash* mid-execution: intermediate state was never written, so you restart from the beginning of the run. That's an acceptable trade for a long read-only research graph and a bad one for anything with side effects.

### Q11 — Time travel: what's replay, what's fork, and what's the trap in each?
**Answer:** Replay is `invoke(None, prior_snapshot.config)`: nodes before that checkpoint are skipped, nodes after it re-execute. Fork is `update_state(prior_config, values={...})` returning a new config, then `invoke(None, fork_config)`: a new checkpoint branches from that point and the original history is untouched. Traps: replay is **not** a cached read — LLM calls, API calls, and interrupts all fire again and may give different results. `update_state` does **not** roll back, it forks. And its values pass through **reducers**, so a channel with `operator.add` accumulates your "replacement" instead of replacing it; wrap in `Overwrite`.
**Follow-up trap:** *"What's `as_node` for?"* — it attributes the update to a specific node, which determines which node runs next (that node's successors) and which writers/reducers apply. LangGraph infers it from version history and is usually right when forking from a real checkpoint. Specify it explicitly when parallel branches wrote in the same step (otherwise `InvalidUpdateError`), when the thread has no history (test setup), or when you want to skip a node by pretending it already ran.

### Q12 — Write the production Postgres setup and tell me what's non-obvious.
**Answer:** A `psycopg_pool.ConnectionPool` with `kwargs={"autocommit": True, "row_factory": dict_row}`, passed to `PostgresSaver(pool)`, with `.setup()` called once. Non-obvious bits: `autocommit=True` is required or `setup()` may not persist the DDL; `row_factory=dict_row` is required because the implementation reads rows by column name and the default `tuple_row` raises `TypeError: tuple indices must be integers or slices, not str` on every read; `setup()` belongs in a migration job rather than on every worker boot, since racing DDL on cold start is avoidable and your app role may not have DDL rights; and `AsyncPostgresSaver` for async graphs. It creates `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and a `checkpoint_migrations` table.
**Follow-up trap:** *"Anything about the data itself?"* — two things, both compliance-adjacent. Checkpoints hold full prompts, tool arguments, and model outputs in **plaintext** by default; pass `EncryptedSerializer.from_pycryptodome_aes()` as `serde=`, which reads `LANGGRAPH_AES_KEY`. And set `LANGGRAPH_STRICT_MSGPACK=true` (or an explicit `allowed_msgpack_modules` list) so a compromised checkpoint store isn't a code-execution path into your workers. Then a retention policy, because nothing prunes checkpoints.

### Q13 — Two parallel branches both call `interrupt()`. What does the caller see?
**Answer:** Two pending `Interrupt` objects, each with a `value` and an `id`. You must pair each `id` with its answer and resume once with a map: `Command(resume={i.id: answer_for(i.value) for i in stream.interrupts})`. Resuming with a single bare value against multiple pending interrupts is ambiguous and is why the id-keyed form exists.
**Follow-up trap:** *"What if you call `Command(resume=...)` on a thread that isn't paused?"* — it resumes from the latest checkpoint, which on a completed thread means there is nothing to run, so the graph appears stuck and silently does nothing. Related and more common: passing `Command(update={...})` as input to continue a conversation. Any `Command` input resumes from the last checkpoint rather than `__start__`. To continue a conversation, pass a plain dict.

### Q14 — Design HITL for a refund approval that a human may take three days to action.
**Answer:** `PostgresSaver` (never in-memory). `thread_id` derived from the refund id so any replica can resume. A node that *only* interrupts, with the payload carrying everything the reviewer needs to render a decision. On interrupt, enqueue a review task and notify — never block a worker, because the graph waits indefinitely and nothing tells the human they have work. The mutating settlement lives in a separate downstream node with an idempotency key derived from `(thread_id, checkpoint_id)` and a TTL longer than three days. `durability="sync"` around the money step. A sweeper that lists threads whose latest snapshot has pending interrupts older than N hours and escalates, because the failure mode of HITL done badly is a request that waits forever with nobody watching.
**Follow-up trap:** *"What breaks if the reviewer rejects and then re-submits with edits?"* — the node re-runs from the top on every resume, so anything mutating in it happens once per attempt. If you logged an audit row before the interrupt, you now have three. Also make sure your interrupt sequence within the node is fixed and unconditional, or the index-based matching pairs the wrong answer with the wrong prompt.

### Q15 — SIGTERM arrives during a deploy while a 20-step run is on step 8. What happens, and what should?
**Answer:** By default the process dies; with `durability="async"` or `"sync"` you keep the checkpoints up to step 7 or 8 and resume with `invoke(None, config)` on the same `thread_id`, so you lose at most the in-flight super-step. With `langgraph>=1.2` you do it properly: create a `RunControl`, register `signal.signal(SIGTERM, lambda *_: control.request_drain("sigterm"))`, pass `control=control` to `invoke`, and catch `GraphDrained`. Drain is cooperative — it takes effect at the next super-step boundary, lets the running node and any retry loop finish, saves a resumable checkpoint, and bubbles up through subgraphs.
**Follow-up trap:** *"Does drain guarantee you stop within your termination grace period?"* — **no.** `request_drain()` doesn't cancel asyncio tasks or kill threads, so a node blocked on a 300-second call keeps going. Pair it with per-node `timeout=` and a hard supervisor deadline. And check `control.drain_requested` after a normal return, because a graph that happened to finish on the same tick returns normally rather than raising.

### Q16 — How would you test any of this?
**Answer:** Layered. `InMemorySaver` plus a fake model for the deterministic parts: assert that `get_state_history()` has the expected steps and `next` values, that an injected failure in node B leaves A's writes durable and re-runs only B, that resume produces the right final state. A test that proves a non-idempotent pre-interrupt side effect fires **twice** — a counter in a fake DB and an assertion that it's 1, which fails until you move the side effect after the interrupt. Fork tests using `update_state(..., as_node=...)` to set up state on a fresh thread with no history. Then integration tests against real Postgres in a container, because `autocommit`/`row_factory` bugs and DDL permissions only appear there.
**Follow-up trap:** *"How do you test the deploy-survives case?"* — you can't with `InMemorySaver`, which is the point. Two processes against one Postgres: process 1 starts the run to the interrupt and exits; process 2 (fresh interpreter, same DB, same `thread_id`) resumes and completes. That test fails loudly on `InMemorySaver` and is the single highest-value integration test in an agent codebase.

### Q17 — You need to change the state schema and there are live interrupted threads. What's safe?
**Answer:** The documented rules: for threads at the **end** of the graph (not interrupted) you can change the entire topology — add, remove, rename nodes and edges. For **interrupted** threads, all topology changes are supported *except* renaming or removing nodes, since a thread may be about to enter a node that no longer exists. For state: adding and removing keys is fully forward- and backward-compatible; **renaming a key loses its saved state** on existing threads; and changing a key's type incompatibly can break threads holding pre-change values.
**Follow-up trap:** *"So how do you actually ship a rename?"* — expand/contract, exactly as with a database column. Add the new key, dual-write both from the node, deploy. Backfill or let live threads drain. Only then remove the old key, in a later deploy. For a node rename, drain interrupted threads first — or add the new node, route to it, and keep the old node as a no-op alias until nothing points at it.

---

## Red flags that fail you

- Recommending `InMemorySaver` for anything with a human in the loop.
- Not knowing that resume re-runs the node from its first line.
- Claiming LangGraph gives exactly-once side effects.
- Putting a mutating call before `interrupt()` with no idempotency story.
- Wrapping `interrupt()` in a bare `try/except`.
- Conditionally skipping interrupts inside a node (index-based matching).
- Thinking `update_state` rolls back rather than forks.
- Thinking replay reads from cache rather than re-executing LLM and API calls.
- Passing a custom Postgres connection without `autocommit=True` and `row_factory=dict_row`.
- Generating a fresh `thread_id` per HTTP request.
- No answer for checkpoint retention, encryption, or PII in state.
- Not knowing the reliability arithmetic that justifies checkpointing at all.

---

## Cheat card

```
WHY AT ALL — reliability is MULTIPLICATIVE
  0.95^10 ≈ 60%   0.85^10 ≈ 20%   0.95^50 ≈ 8%   0.85^20 ≈ 4%
  0.85^10 ≈ 20% → 4 of 5 runs fail somewhere; un-checkpointed retry pays for
  the WHOLE trajectory again (~5x expected cost per success)
  retry raises p · checkpointing makes failure CHEAP · they are complements

INTERFACE  BaseCheckpointSaver: .put .put_writes .get_tuple .list
                        async:  .aput .aput_writes .aget_tuple .alist
  put_writes = per-TASK writes inside a super-step → PENDING WRITES:
    sibling node that succeeded in a failed tick does NOT re-run

IMPLEMENTATIONS
  InMemorySaver     bundled       dict on the heap. dies on deploy/evict/OOM/2nd replica
  SqliteSaver       -sqlite pkg   file; single writer; dev + single-node only
  PostgresSaver     -postgres pkg PRODUCTION (+ AsyncPostgresSaver for ainvoke)
  ShallowPostgres   -postgres pkg latest checkpoint only → NO time travel / fork
  CosmosDBSaver     langchain-azure-cosmosdb

KEYS  config={"configurable":{"thread_id": ..., ["checkpoint_id": ...]}}   REQUIRED
  thread_id = durable cursor. business id, not per-request UUID. PII + tenancy surface.
  checkpoint_ns: "" root · "node:uuid" subgraph · nested joined by "|"
  renaming a node changes the ns → breaks INTERRUPTED threads

StateSnapshot  values · next (()=done) · config · created_at · parent_config
  metadata{source: input|loop|update, writes, step} · tasks[PregelTask: id,name,error,interrupts]
  START→A→B→END produces FOUR checkpoints (steps -1, 0, 1, 2)

TIME TRAVEL
  get_state / get_state_history (REVERSE chronological)
  REPLAY  invoke(None, snap.config)   → nodes after re-EXECUTE (LLM+API+interrupts fire again)
  FORK    update_state(snap.config, values) → NEW checkpoint, original history intact
          values pass through REDUCERS (add accumulates!) → use Overwrite to replace
          as_node= when parallel writes / no history / to skip a node

interrupt()  raises GraphBubbleUp · needs checkpointer + thread_id · JSON-serialisable
  read: v1 result["__interrupt__"] · v2 result.interrupts · v3 stream.interrupts/.interrupted
  resume: Command(resume=v) — the ONLY Command valid as INPUT
  parallel interrupts → Command(resume={interrupt.id: answer, ...})
  ★ NODE RE-RUNS FROM ITS FIRST LINE ON EVERY RESUME ★
  1 no bare try/except (swallows the pause)   2 never skip/reorder (INDEX-matched)
  3 JSON-serialisable only                    4 pre-interrupt side effects IDEMPOTENT
  static interrupt_before/after = DEBUG breakpoints, resume with invoke(None, cfg)

SIDE EFFECTS ON RESUME
  sibling completed in failed tick → safe (pending writes)
  node failed mid-way / interrupt  → everything before it RE-RUNS
  fix order: (1) side effect AFTER interrupt or in its OWN node
             (2) naturally idempotent (upsert > insert)
             (3) idempotency key = f"{thread_id}:{checkpoint_id}:{op}", TTL > approval window
             (4) @task (retrieved on replay) — still NOT exactly-once
  LangGraph = AT-LEAST-ONCE. Exactly-once is the downstream system's property.

DURABILITY  exit (on exit only; no crash recovery) · async (default choice) · sync (safest)
GRACEFUL SHUTDOWN (>=1.2 alpha)  RunControl().request_drain(); catch GraphDrained;
  resume invoke(None, cfg). Cooperative: BETWEEN supersteps; does NOT cancel tasks.

POSTGRES  ConnectionPool(kwargs={"autocommit": True, "row_factory": dict_row})
  autocommit → .setup() persists DDL · dict_row → else TypeError: tuple indices...
  .setup() ONCE in a migration job → checkpoints, checkpoint_blobs, checkpoint_writes,
                                     checkpoint_migrations
  serde=EncryptedSerializer.from_pycryptodome_aes()  (LANGGRAPH_AES_KEY) — plaintext otherwise
  LANGGRAPH_STRICT_MSGPACK=true — restrict deserialisation
  NOTHING prunes checkpoints. Own a retention job.

MIGRATIONS  completed threads: any topology change · interrupted threads: NOT rename/remove
  state keys: add/remove safe · RENAME LOSES SAVED STATE · type change may break

WHEN NOT TO USE  stateless single-shot call · synchronous confirmation (no durable pause needed)
  exactly-once / cross-service compensation → Temporal / Restate (LLM calls as activities)
```

## Sources

- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer interface, threads, `checkpoint_ns`, `StateSnapshot` fields, four-checkpoint example, pending writes, replay/`update_state`, durability modes, serializer, `EncryptedSerializer`, `DeltaChannel`; accessed 2026-07-26
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — `interrupt()` mechanics, resume via `Command`, the four rules, index-based resume matching, idempotency guidance, parallel interrupts, static breakpoints; accessed 2026-07-26
- [LangGraph — Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution) — determinism/idempotency requirements, `@task`, resume starting points, graceful shutdown and drain semantics; accessed 2026-07-26
- [LangGraph — Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) — replay vs fork, `as_node`, interrupts always re-trigger, subgraph checkpointer granularity; accessed 2026-07-26
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) — `RetryPolicy` defaults, `TimeoutPolicy`, `error_handler`, resume-safe failure provenance, interrupt bypassing retries; accessed 2026-07-26
- [`langgraph.checkpoint.postgres` reference](https://reference.langchain.com/python/langgraph.checkpoint.postgres) — `setup()` requirement, `autocommit=True` and `row_factory=dict_row` rationale and the exact `TypeError`, `LANGGRAPH_STRICT_MSGPACK` guidance, `ShallowPostgresSaver`; accessed 2026-07-26
- [LangGraph — Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — graph migration rules for completed vs interrupted threads and state-key renames; accessed 2026-07-26
- [LangChain Python changelog](https://docs.langchain.com/oss/python/releases/changelog) — `langgraph` 1.2.0 (2026-05-12): graceful shutdown, per-node timeouts, error handlers, `DeltaChannel`, v3 event streaming; accessed 2026-07-26
- [Internals of the LangGraph Postgres checkpointer](https://blog.lordpatil.com/posts/langgraph-postgres-checkpointer/) — `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` table roles; accessed 2026-07-26
- [Temporal — Error handling in distributed systems](https://temporal.io/blog/error-handling-in-distributed-systems) — durable execution as the alternative framing; accessed 2026-07-26
- [250 LangGraph Interview Questions & Answers (2026)](https://rpabotsworld.com/langgraph-interview-questions/) — question phrasings used in screens; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
