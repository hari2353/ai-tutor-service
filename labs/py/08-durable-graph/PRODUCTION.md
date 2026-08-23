# Production notes -- durable state graphs

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Graph engine | ~150 lines, one node at a time | LangGraph -- same checkpoint-per-superstep idea, plus parallel branches, subgraphs, streaming, and a visual debugger (LangGraph Studio) |
| Checkpointer | `InMemoryCheckpointer` / `SqliteCheckpointer` | `PostgresSaver` or a managed store; SQLite is fine for a single-process dev box, not for multiple replicas writing concurrently |
| State shape | a plain dict, last-write-wins merge | typed `TypedDict`/Pydantic channels with explicit reducers (e.g. `operator.add` to append instead of overwrite) so two nodes writing the same key don't silently clobber each other |
| Interrupt/HITL | `Interrupt` exception + `resume_value` | `interrupt()` + `Command(resume=value)`, integrated with the same checkpointer so an approval can sit for days without holding a process open |
| Idempotency | none -- the lab's node deliberately re-fires | explicit dedupe keys (e.g. a Stripe idempotency key) on every mutating tool call inside a node, checked against a store before the mutation runs |

## What the real ones add over yours

- **Super-steps, not single nodes.** LangGraph checkpoints at the
  *super-step* boundary -- potentially several nodes running in parallel
  in the same step -- not strictly one node at a time like this lab. That
  matters for exactly-once reasoning: if three nodes run in one super-step
  and the process dies after two finish, what happens to the third depends
  on how atomically the checkpoint write covers the whole step.
- **A real reducer model.** This lab merges `{**state, **update}` --
  last write wins, silently, if two updates touch the same key. Production
  graphs define a reducer per channel (`add_messages`, `operator.add`, a
  custom merge function) specifically to make concurrent or repeated
  writes to the same key well-defined instead of an accidental bug.
- **Checkpoint namespaces for sub-graphs.** A node that is itself a
  compiled graph gets its own checkpoint namespace so its internal steps
  don't collide with the parent's, and so time-travel/replay can target
  just the sub-graph without replaying the whole parent.
- **Durable interrupts that survive days, not just a resume() call.** A
  production human-in-the-loop step checkpoints and then genuinely stops
  the process -- no thread is blocked waiting. The approval can come back
  hours or days later through an API call that loads the checkpoint fresh,
  exactly like `test_resume_with_sqlite_survives_a_simulated_process_restart`
  in this lab, just with a much longer gap.
- **Concurrent-write safety on the checkpoint store.** Multiple replicas
  of the same service resuming the same thread_id at once is a real
  failure mode (a retried webhook, a duplicate queue message). Production
  checkpointers use `SELECT ... FOR UPDATE` or optimistic concurrency
  (a version column) so two processes don't both "win" the same resume.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| A refund gets charged twice after a human approves it | The node that calls the payment API runs again on resume (its side effect sat *before* the `interrupt()` call) | Move the mutating call to *after* the interrupt point, or make it idempotent with a dedupe key checked before executing |
| Two concurrent workers both "complete" the same thread | No locking on `load_latest` + `save`; both read the same checkpoint, both write | Optimistic concurrency: include the expected prior step/version in the write, reject if it doesn't match |
| SQLite checkpointer works in dev, falls over in staging | Multiple app replicas hitting one SQLite file -- `sqlite3` write-locks the whole file, so concurrent resumes serialize and eventually time out | Move to a real concurrent-safe store (Postgres) once you have more than one writer process |
| A checkpoint table grows without bound | Every single step for every thread kept forever, including completed threads from months ago | TTL/archive policy: compact or delete checkpoint history for `status="done"` threads past a retention window |
| An interrupted run never gets picked back up | Nothing is watching for `status="interrupted"` threads; the approval UI never got told there was something to approve | A separate index/queue of pending interrupts, not just "hope someone calls resume()" |

## Cost & latency

A checkpoint write is one row insert -- single-digit milliseconds on
Postgres, sub-millisecond on SQLite -- but it happens after *every* node,
so a 20-node agent run does 20 extra writes it wouldn't need if it trusted
in-memory state. That's the price of "a crash loses at most one step of
work" instead of "a crash loses the whole run," and at a 85%-per-step
success rate a 10-step agent without checkpointing completes end-to-end
only about 20% of the time (`0.85^10`) -- so the write cost is nearly
always worth it. The place teams get surprised is state size: checkpointing
a full multi-turn message history on every step, instead of just the delta,
turns a cheap row insert into a multi-KB write repeated dozens of times per
run.

## The 3 questions an interviewer asks after you describe this

1. *"Why does the node re-run from the top on resume instead of continuing
   from where it interrupted?"* -- because the checkpoint granularity is
   the whole node, not a line inside it; the framework has no way to know
   which lines already ran, so it treats "didn't finish" the same whether
   the cause was an `Interrupt` or a crash, and reruns the entire node.
2. *"Two replicas of your service both call resume() on the same thread_id
   at the same instant. What happens?"* -- with this lab's checkpointer,
   both read the same last checkpoint and both could complete the run,
   double-executing every step; production needs a lock or optimistic
   concurrency check on the checkpoint write to make only one of them win.
3. *"Where would you put a Stripe API call in this graph, and why does it
   matter which side of the interrupt it's on?"* -- after the interrupt,
   guarded by an idempotency key, never before it -- a call placed before
   an `interrupt()` (or anywhere that can re-run on resume) fires again
   every time that step retries, which is exactly the double-charge bug
   this lab's `test_non_idempotent_node_executed_twice_on_resume_is_detectable`
   demonstrates on purpose.
