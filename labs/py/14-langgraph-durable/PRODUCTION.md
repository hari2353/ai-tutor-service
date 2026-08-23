# Production notes — durable graphs

## What you'd actually use

| Checkpointer | Survives process exit | Survives deploy | Multi-replica | Use |
|---|---|---|---|---|
| `InMemorySaver` | **no** | **no** | **no** | tests, notebooks |
| `SqliteSaver` | yes (file) | only if the file does | **no** (single writer) | local dev, CLI |
| `PostgresSaver` | yes | yes | yes | **production** |
| `ShallowPostgresSaver` | yes | yes | yes | latest-only; **no time travel** |
| Temporal / Restate | yes | yes | yes | when you need exactly-once |

`InMemorySaver` is a dict on the heap. Rolling deploy, SIGTERM, scale-in, spot reclaim, OOM kill — every one silently drops in-flight threads, including approvals humans already saw. It also breaks at two replicas: the resume request load-balances to a pod whose dict is empty.

## What the real ones add over yours

- **Serialisation with a schema** — msgpack + strict deserialisation allowlists (`LANGGRAPH_STRICT_MSGPACK`); a checkpoint store is otherwise a code-execution path into your workers.
- **Async twins** — `aput`/`aget_tuple`; using the sync saver under `ainvoke` blocks the event loop.
- **Retention** — nothing prunes checkpoints for you; full-value snapshots of a growing message list are quadratic in storage. Plan TTL/archival from day one — and note pruning kills time travel.
- **Encryption at rest** — checkpoints contain full prompts and tool arguments in plaintext unless you opt in.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Approvals vanish after deploys | in-process dict | real saver (Postgres) |
| Resume works locally, flaky at 2 replicas | resume hit the other pod | shared durable store |
| Duplicate charges per retry | mutating call before the crash/interrupt point | idempotency key derived from `(thread_id, step)` |
| Interrupt never surfaces | bare `except Exception` swallowed it | catch specific types only |
| Wrong answer lands on wrong question | interrupts reordered/skipped | index-matched: keep order fixed |
| Time travel returns nothing | shallow saver keeps latest only | history-preserving saver |

The honest sentence: **the orchestrator gives you at-least-once and tells you to be idempotent. Exactly-once is a property of the downstream system.**

## The 3 questions an interviewer asks after you describe this

1. *"Your node charged the card, then crashed. What happens on resume?"* — the node restarts from line one; the charge repeats unless keyed. Pending writes protect *siblings*, not the failing node.
2. *"How many checkpoints does START → A → B → END write?"* — four: input + one per completed node. People say two because they count nodes.
3. *"Why attach pending writes to the parent step?"* — because the snapshot that would contain them may never commit; recovery reads them off the last tuple that definitely exists.
