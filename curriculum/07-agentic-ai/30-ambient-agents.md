# Ambient Agents: Unattended, Long-Running, Resumable — the Half Nobody Demos

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-langgraph-durable`, `T07-loop-engineering` · **Updated:** 2026-08-10
> **Module id:** `T07-ambient-agents` · **Tags:** harness, critical
> **Lab:** `labs/py/08-durable-graph/`

## The 30-second version

Almost every agent demo is synchronous: a human types, the model answers, the process exits, nothing persists. Production agents are the other half — cron- or event-triggered, running unattended for minutes to hours, pausing for a human who shows up whenever they show up, and expected to survive the process dying mid-run. That needs four things a chat demo never touches: a durable interrupt whose resume token outlives the process and whose payload gets re-validated against current world state, not trusted at face value; checkpoint storage a *different* process can pick up, which means the state has to serialize and survive the graph's own schema changing underneath it; a budget-truncation story where partial work lands in durable storage as it's produced instead of vanishing with a killed run; and idempotency at both the tool-call level and the trigger level, because cron overlaps and webhooks redeliver. The single sharpest fact: `interrupt()` doesn't resume the next line, it re-runs the whole node from the top, because LangGraph checkpoints at node granularity — there's no saved continuation to jump back into, only a saved value the re-executed `interrupt()` call now returns. Anything before it that isn't idempotent fires again on every resume, every retry, every redelivered webhook.

## Why this gets asked

"I built an agent" and "I built an agent that runs unattended" are different systems, and ambient-agent incidents live in that gap. The interviewer has shipped a triage agent that fired twice because a cron job overlapped its own previous run. Or a refund flow where a Tuesday-morning approval click re-executed a Monday-night audit insert for the third time, because nobody read the "resume restarts the node" warning. Or an overnight research agent that discarded two hours of findings at the token cap because they only existed in the final message the run never sent. None of these are model failures — they're the failure of treating "unattended" as "the same loop, just longer," when it's a different set of guarantees: durability across process death, idempotency across redelivery, and value that survives truncation.

---

## Lineage: past → present → future

**What came before.** Early agent products were request/response: state lived in memory for one HTTP call, and the agent's existence ended when the response did. The first "let it run longer" attempts were that same loop inside a bigger timeout — a background thread or Celery task running an hour instead of ten seconds. The pain was arithmetic: a process holding an hour of irreplaceable work with no persistence loses it all to any deploy, OOM kill, or autoscaler event — the exact failure `T07-langgraph-durable` names as the reason checkpointers exist. The second attempt put a job queue in front of a stateless agent — cron fires, a worker runs the task start to finish, dies. That fixed who starts the work, not what happens when the work needs to pause for a human who isn't at a keyboard, which both a request/response system and a naive worker handle by blocking a thread for hours — the resource-exhaustion failure that made durable pausing necessary at all.

**Where it stands now.** The consensus, sharpened through 2025–2026 and named directly by LangChain's "ambient agents" framing, is that unattended agents are event-driven, not conversation-driven: a webhook, cron tick, or queue message starts a run, the run may pause indefinitely for approval, and "ambient does not mean fully autonomous" — a human stays in the loop asynchronously rather than in a blocking chat turn. Deployed today: durable Postgres-backed checkpointers as the substrate, platform-native cron (LangGraph Platform's default creates a fresh thread per fire), and an "agent inbox" pattern where a human works through pending interrupts on their own schedule. Live disagreement: whether the harness or the agent should own truncation decisions during a long unattended run — the same contested question `T07-loop-engineering` raises, sharper here because nobody notices a bad truncation until days later — and how aggressively to auto-approve low-risk actions versus routing everything to a human.

**Where it's heading.** High confidence: kill-switch and rate-budget infrastructure becomes a control-plane concern rather than an in-loop `if`, driven by a documented governance gap — surveyed organizations increasingly report an agent incident they couldn't reliably stop once running, pushing teams toward an out-of-band cancellation channel rather than trusting a running process to police itself. Medium confidence: trigger-level idempotency (deduplicating on delivery or cron-fire id, not just tool-call arguments) becomes a documented harness responsibility rather than something every team rediscovers after a duplicate-charge incident. Speculative: standardized "approval staleness" semantics — expiry and mandatory precondition re-checks built into a framework rather than hand-rolled — don't exist yet anywhere mainstream; treat any claim otherwise as unverified.

---

## Mental model

An ambient agent's real lifetime is the row, not the process.

```
 TRIGGER                    PROCESS A (pod-7f3a)
 cron / webhook / event ──▶ run starts ──▶ step, step, step ──▶ interrupt()
                                                                     │
                                            checkpoint written; PROCESS A EXITS
                                                                     ▼
                              durable store, keyed by thread_id (Postgres row)
                              ┌──────────────────────────────────────────────┐
                              │ state snapshot · pending interrupt + payload  │
                              │ approval request, expires_at = T+24h         │
                              │ budget counters · run_status (live/cancelled)│
                              └──────────────────────────────────────────────┘
                                                                     │
                    8 hours later: human clicks "approve" in an email/Slack link
                                                                     ▼
 PROCESS B (pod-9c11, never saw process A)
   loads thread_id → checks run_status, checks approval not expired
   → RE-VALIDATES PRECONDITIONS against current world state, not the 8h-old snapshot
   → node RE-RUNS FROM ITS FIRST LINE (checkpoints are node-granular, not line-granular)
   → interrupt() returns the approval → side effect fires ONCE (idempotency key)
```

Every arrow into that row from outside — a click, a redelivered webhook, an overlapping cron — is a potential duplicate. Each one needs its own idempotency story, not just the tool calls inside the loop.

---

## How it actually works

### 1. The durable interrupt: where the resume token lives

The resume token is not a session or a callback — it's the pair `(thread_id, checkpointer)`. When `approval_node` calls `interrupt(payload)`, write a row to your own `approvals` table (`thread_id`, payload, `created_at`, `expires_at`) and notify the human through a channel that survives your infrastructure being down — a link encoding `thread_id`. Hours later a different replica handles the click, looks up `thread_id`, and calls `graph.invoke(Command(resume=...), config)`. Nothing about that call needs process A to exist.

### 2. Expiring and re-validating stale approvals

An eight-hour-old approval is a claim about the world as it was eight hours ago — the refund it authorizes may already be issued through another channel. Enforce single-use and expiry before the resume ever reaches the graph:

```python
# untested sketch
def resume_approval(thread_id, decision):
    row = db.get_approval(thread_id)
    if row is None or row.consumed_at is not None:
        raise ApprovalInvalid("no pending approval, or already used")
    if datetime.now(UTC) > row.expires_at:
        raise ApprovalExpired("window closed; re-open the request")
    db.mark_consumed(thread_id)                     # atomic, single-use
    graph.invoke(Command(resume=decision), config={"configurable": {"thread_id": thread_id}})
```

Then, inside the node that mutates state, re-check the precondition against *live* data:

```python
# untested sketch
def settle(state, config):
    order = db.get_order(state["order_id"])           # fresh read, not state["order"]
    if order.status != "pending_refund":
        return {"status": "aborted", "reason": f"order moved to {order.status}"}
    payments.refund(order.id, idempotency_key=f"{config['configurable']['thread_id']}:settle")
    return {"status": "settled"}
```

An approval authorizes an intent, not a fact about the world at execution time. Re-derive the fact.

### 3. Checkpoint storage: what serializes and what doesn't

`T07-langgraph-durable` covers the checkpointer interface; the ambient question is what breaks when one process writes a checkpoint and an unrelated one reads it. Anything referencing a live OS or network resource can't cross that boundary: an open DB connection or file handle points at a file descriptor meaningless in a new process; a socket or lock has no serialized form; an in-memory closure over a live object fails at the serializer or reconstructs into something broken. State holds ids, paths, primitives; nodes re-acquire live resources on every execution. This is why persisted-output paths (`T07-loop-engineering`) must point at shared storage (S3, a shared volume), not local disk — process B can't read what only ever existed on process A.

### 4. Don't let a killed run discard its best work

A run that hits `cost_budget` or `deadline` at hour six returns nothing if its findings only lived in running commentary. Fix: write results incrementally to durable storage as they're produced (a row per finding, not an assembled final message), and make progress externally visible (a todo list with items marked done, a row count a dashboard can read). A truncated run then has value proportional to how far it got, instead of all-or-nothing.

### 5. Why `interrupt()` replays the whole node, verified

LangGraph's docs are explicit: "the runtime restarts the entire node from the beginning... any code that ran before the `interrupt()` will execute again." [Interrupts — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/interrupts) — accessed 2026-08-10. This is structural: checkpointing happens at super-step (node) granularity, not statement granularity. A paused node has no saved program counter — the runtime's only record is "this node hasn't produced its writes yet." Resuming re-executes it, with each `interrupt()` call site now returning a value from the resume list instead of raising. One consequence the docs add beyond the mechanism itself: a `while True` loop calling `interrupt()` repeatedly inside one node doesn't just replay once per resume — it replays *every prior iteration* on every resume, exponential re-execution of the loop body. The documented fix isn't a loop inside a node at all; it's a conditional edge back to a node that calls `interrupt()` exactly once per invocation, with re-prompt state carried between invocations. Nesting doesn't change the granularity either: a subgraph invoked as a function re-executes its parent node's pre-subgraph code on resume, and the subgraph resumes its own node from the beginning too.

Fixes, in order: move the mutating call after the interrupt or into a separate node (free, the default); make it naturally idempotent (upsert, not insert); attach a deterministic idempotency key from `(thread_id, checkpoint_id, op)` with a TTL that exceeds your longest realistic approval wait — a weekend on-call handoff can be 60+ hours, and a 24-hour TTL stops protecting you exactly when the wait is long enough to matter.

### 6. Two processes, one SQLite file

`SqliteSaver` is fine for a single-node ambient job and breaks the moment two processes touch the file concurrently. `PRAGMA journal_mode=WAL` lets readers proceed against the last-committed snapshot while a writer appends to a separate `-wal` file, folded back roughly every 1,000 pages (~4 MB at the default page size). WAL fixes reader/writer contention; it does **not** give you concurrent writers — SQLite has exactly one, full stop. `PRAGMA busy_timeout=5000` (5s is a reasonable floor) makes it retry instead of failing immediately. Under real contention — 3+ processes writing checkpoints — even a generous timeout occasionally expires, and the fix is retry-with-backoff around the call, not a bigger number. The signal you've outgrown SQLite is a shape, not an error: more than one process regularly writing checkpoints, or more than one replica. At that point `PostgresSaver` is a correctness requirement, not an upgrade — MVCC and row-level locking give you real concurrent writers, which WAL was never going to.

### 7. Scheduling, triggers, and rate budgets that span a run

Cron creates a fresh thread per fire; if the job can run longer than the interval, lock on the job's identity, not the thread, or overlapping fires hit the same downstream resources. Event triggers map one event to one thread, but queues are commonly at-least-once, so dedupe on the event id before creating a thread. Webhooks add redelivery — providers commonly retry for hours to days — so dedupe on `delivery_id` before a new run starts, not inside the graph. All three need the same shape: a dedupe key that's the trigger's own identity, checked before thread creation.

Provider rate limits are a fleet-wide axis, not a per-run one. Anthropic enforces per-org RPM/ITPM/OTPM via a token bucket that replenishes continuously; Start tier runs roughly 1,000 RPM / 2M ITPM / 400K OTPM, Scale roughly 10,000/10M/2M, and cached-read tokens don't count against ITPM, so an 80%-cache-hit workload gets meaningfully more real throughput than the raw ceiling suggests. [LLM API Rate Limits (2026)](https://www.requesty.ai/blog/rate-limits-for-llm-providers-openai-anthropic-and-deepseek) — accessed 2026-08-10. A hundred cron-triggered agents each within their own `T07-loop-engineering` cost budget can still collectively blow the org-wide RPM ceiling if nothing coordinates them, producing a 429 wave at the top of every hour when crons cluster. Treat it as a shared, reserved budget your scheduler checks before dispatch — independent per-run backoff just turns a smooth ceiling into a thundering herd every time the bucket refills.

### 8. Idempotency one layer above the tool call

Tool-call idempotency keys derived from `(thread_id, checkpoint_id, op)` don't protect against a duplicated *trigger* — a redelivered webhook or overlapping cron produces a whole new run with a fresh `checkpoint_id`, so the derived key changes too. The guard sits in front of thread creation: check whether this trigger identity has already produced a completed or in-flight thread, atomically, before starting a new one, with the same insert-or-conflict discipline as any other idempotency key.

### 9. Observability and the kill switch, for a run nobody's watching

A hard crash stops checkpoints and spans alike, and looks identical to "still working" until you check the right metric: alert on `last_checkpoint_at` staleness relative to the task's own expected cadence (minutes for a research run, low single digits for a cron job), not on "no logs," since a completed run also produces no new logs.

A kill switch needs two layers. Soft: a `run_status` column checked at every tool-call boundary (not once per iteration — a single call can run long), so an admin action stops the next side effect without touching the process. Hard: revoke the credentials its tools use, which works even if the process never checks `run_status` again. LangGraph 1.2's `RunControl.request_drain()` (per `T07-langgraph-durable`) is the graceful, cooperative version — the SIGTERM handler for a deploy, not an emergency stop for a process you no longer trust.

---

## Build it from scratch

`labs/py/08-durable-graph/` already demonstrates checkpoint-resume across a simulated process death and proves a non-idempotent node fires its side effect twice across a resume — the concrete case behind section 5. Extend it with what this module adds: an `approvals` table with `expires_at` and a single-use `consumed_at` guard (section 2); a trigger-dedupe table keyed by an external delivery/event id in front of thread creation (sections 7–8); and a `run_status` column checked at every tool-call boundary, with a test that cancels a thread mid-run from a second connection and asserts the next tool call never fires (section 9). Same discipline as the lab already uses: kill the process, resume from a fresh one, assert the outcome.

---

## How it's done in production

An ambient refund-approval agent: a Postgres-backed graph on a 10-minute cron poll, deduped on `(source_system, request_id)` before a thread exists; `interrupt()` in an `approval` node whose payload lands in an `approvals` table with a 48-hour expiry; a notification carrying a link that resolves to `thread_id`; a `settle` node that re-reads live order status before charging, keyed `f"{thread_id}:settle"`; a `run_status` check before every tool call; and a staleness alert on `last_checkpoint_at`.

| Symptom | Cause | Fix |
|---|---|---|
| Refund issued twice for one approval | Mutating call before `interrupt()`, or approval clicked twice | Move the charge after the interrupt with an idempotency key; mark the approval consumed atomically |
| Agent acts on a decision no longer true | Precondition trusted from the paused snapshot | Re-fetch live state right before the side effect |
| Approval honored a week late | No `expires_at` on the request | Reject resumes past expiry; require re-opening the request |
| Two runs for one webhook event | Provider redelivered; no dedupe before thread creation | Dedupe on `delivery_id` before `graph.invoke` is ever called |
| Cron doubles up on a slow day | Run exceeds the cron interval | Lock on job identity, not thread id; skip an overlapping fire |
| Two processes fight over `checkpoints.sqlite` | Concurrent writers on SQLite | WAL + `busy_timeout`; move to `PostgresSaver` past one real writer |
| Six-hour run returns nothing at the budget wall | Findings held in context, never externalized | Write results durably as produced; keep progress externally visible |
| Org-wide 429 storm on the hour | Independent per-run backoff, no coordination | A shared token-bucket limiter the scheduler checks pre-dispatch |
| Run silently dead for hours, unnoticed | No heartbeat distinct from "slow" | Alert on `last_checkpoint_at` staleness vs. expected cadence |
| Cancelling a run does nothing | `run_status` read once per loop, not per tool call | Check it at every tool-call boundary |
| Checkpoint won't deserialize elsewhere | State held a live connection, handle, or closure | State holds ids/paths only; re-acquire resources per execution |

---

## Tradeoffs & when NOT to use it

- **A same-session chat confirmation needs none of this.** If the human is present and the wait is seconds, an inline confirmation beats a durable interrupt, an approvals table, and an expiry policy. The ambient machinery earns its cost only once the wait genuinely spans processes, hours, or days.
- **Don't build trigger-level dedupe for one controlled trigger source.** If nothing redelivers and nothing overlaps, a dedupe table is overhead for a problem you don't have.
- **SQLite is not a mistake for a single-node job.** The mistake is not moving off it once a second writer or replica shows up.
- **A kill switch that's only a graceful drain is a false sense of security.** Cooperative cancellation assumes the process is healthy enough to check a flag. The only real backstop for the case it isn't is revoking what it can act with — an access-control decision, not a loop-engineering one.
- **Fleet-wide rate coordination isn't worth building for one ambient agent.** Build the shared limiter once you have enough independently-scheduled agents that their triggers can plausibly cluster.

---

## Interview questions

### Q1 — An agent pauses for a human who shows up eight hours later. The process is gone. What makes resume work anyway?
**Testing:** whether "durable" means something concrete to you.
**Answer:** The pause is a row, not a suspended process: `interrupt()` raises, the checkpointer persists state keyed by `thread_id`, and the process exiting doesn't matter because nothing about resume depends on it. The resume token is `thread_id` (plus the interrupt's own id if several are pending), typically embedded in a link sent through a channel that outlives your infrastructure. A different process, hours later, loads state by `thread_id` and calls `Command(resume=value)`.
**Follow-up trap:** *"What if the token gets clicked twice?"* — a replay, needing its own guard: an `approvals` row with `consumed_at` set atomically on first use, so the second click is rejected before it reaches the graph.

### Q2 — Why isn't an eight-hour-old approval automatically safe to act on?
**Testing:** intent vs. current fact.
**Answer:** An approval is a claim about the world as of when it was requested. Hours later the order may already be refunded, the account closed, the price changed. The fix is re-reading the live precondition inside the executing node, right before the side effect — not trusting `state["order"]` as captured at pause time.
**Follow-up trap:** *"Do you re-run the whole graph to get fresh state?"* — no, only the mutating node re-fetches its own precondition; everything upstream is legitimately stale and doesn't need re-deriving.

### Q3 — Design the expiry policy for a pending approval.
**Testing:** whether "the human hasn't responded" is a handled state.
**Answer:** Every approval gets an `expires_at` — 24 to 72 hours is typical for an on-call human. A resume against an expired approval is rejected before it reaches `graph.invoke`; the run either re-issues a fresh request or escalates.
**Follow-up trap:** *"What TTL on the idempotency key protecting the side effect?"* — it must exceed the approval's own expiry, or the idempotency guard lapses first, and a retried resume inside the approval window but outside a too-short TTL can double-execute.

### Q4 — Why does `interrupt()` replay the whole node instead of resuming the next line?
**Testing:** the sharpest question here — mechanism, not memorized behavior.
**Answer:** Checkpointing happens at node (super-step) granularity, not statement granularity. A paused node has no saved program counter to jump back into — the runtime's record is "this node hasn't produced its writes yet." Resuming re-executes it, with each `interrupt()` call now returning a value instead of raising. LangGraph's docs: "the runtime restarts the entire node from the beginning... any code that ran before the `interrupt()` will execute again."
**Follow-up trap:** *"What if the node has a `while True` loop calling `interrupt()` repeatedly?"* — each resume replays every prior iteration, exponentially — resume 2 replays 1 iteration, resume 3 replays 2, and so on. The fix isn't a loop in the node at all; it's a conditional edge back to a node calling `interrupt()` exactly once per invocation, with re-prompt state carried between invocations.

### Q5 — How do you actually write a node with a mutating call and an interrupt in it?
**Testing:** whether Q4 becomes a design decision.
**Answer:** Move the mutating call after the interrupt or into a separate node — free, the default. If it must precede it, make it naturally idempotent (upsert, not insert). If neither works, attach a deterministic idempotency key from `(thread_id, checkpoint_id, op)`, stored atomically so a repeat returns the prior result.
**Follow-up trap:** *"Does `@task` solve this?"* — it retrieves a completed result on replay instead of recomputing, but the docs' own caveat is that a task that starts and fails to finish gets re-run on resumption. Not exactly-once; still need idempotency.

### Q6 — Where do you store a half-finished workflow so a different process can finish it, and what can't go there?
**Testing:** the serialization boundary.
**Answer:** A durable, network-reachable store keyed by `thread_id`. What can't cross it: open DB connections, file handles, sockets, locks — the OS handle means nothing in a new process — and in-memory closures over live objects, which fail at serialization or reconstruct broken. State holds ids, paths, primitives; nodes re-acquire live resources every execution.
**Follow-up trap:** *"A node persists a 2 MB result to local disk and keeps the path in state. What breaks?"* — resuming on a different machine. The path checkpoints fine as a string but points at a file only the original box has. Persisted output needs shared storage, not local disk.

### Q7 — You need to rename a state key with live ambient threads that might not resume for weeks. What do you ship?
**Testing:** schema evolution under a graph that's already deployed.
**Answer:** Expand/contract: add the new key, dual-write it alongside the old one from every touching node, deploy, and remove the old key only once every in-flight thread has passed through a dual-write node. For a node rename, drain interrupted threads first, or route the old name to the new node as a no-op alias until nothing points at it.
**Follow-up trap:** *"What's actually unsafe for an interrupted thread specifically?"* — renaming or removing a node it might be about to enter. Completed threads tolerate any topology change; interrupted ones don't tolerate losing a node they're mid-route toward.

### Q8 — How do you stop an agent from silently discarding its own best work under a budget?
**Testing:** data placement, not compaction tuning.
**Answer:** Don't hold results in context waiting for a final message — write each finding to durable storage as it's produced, and keep progress externally visible (a todo list, a row count). A run truncated by `cost_budget` or `deadline` then has value proportional to how far it got.
**Follow-up trap:** *"Isn't that just compaction?"* — the opposite failure. Compaction is about not losing information the agent still needs mid-run; this is about a run legitimately ending with nothing retrievable because it never left context. The fix is architectural — write-through, not a compaction-tuning knob.

### Q9 — How do two processes share one SQLite checkpoint file without locking each other out?
**Testing:** whether "SQLite doesn't scale" is a slogan or a mechanism.
**Answer:** `PRAGMA journal_mode=WAL` lets readers proceed against the last-committed snapshot while a writer appends to a separate file, folded back roughly every 1,000 pages (~4 MB). That fixes reader/writer contention, not writer/writer — SQLite has exactly one writer regardless of mode. `busy_timeout` makes a second writer retry instead of erroring immediately.
**Follow-up trap:** *"Still seeing `SQLITE_BUSY` with WAL and a 5s timeout under load?"* — that's the signal to move, not raise the number. Under 3+ concurrent writers even a generous timeout occasionally expires; `PostgresSaver` gives real concurrent writers via MVCC instead of a longer wait on a single-writer queue.

### Q10 — A webhook redelivers because your handler didn't respond fast enough. What breaks, and how do you prevent it?
**Testing:** idempotency one layer above the tool call.
**Answer:** Without a guard, redelivery starts a second full run — a new thread, a new `checkpoint_id` — so tool-call idempotency keys don't help, since the key changes too. The guard sits in front of thread creation: dedupe on `delivery_id`, checked and recorded atomically before `graph.invoke` runs.
**Follow-up trap:** *"What if the redelivery arrives an hour after the first run completed?"* — the dedupe record must outlive the run, with retention at least as long as the provider's redelivery window (some retry for days), not just tracked while "in flight."

### Q11 — Design the kill switch for an ambient agent fleet.
**Testing:** graceful cancellation vs. an actual emergency stop.
**Answer:** Soft: a `run_status` column checked at every tool-call boundary — an admin action sets it to `cancelled`, stopping the next side effect. Hard, for a process that's stuck, compromised, or unreachable: revoke the credentials its tools use, which works regardless of whether it ever checks `run_status` again.
**Follow-up trap:** *"Isn't `RunControl.request_drain()` the kill switch?"* — it's the graceful-shutdown answer to a deploy: cooperative, in-process, saves a resumable checkpoint at the next super-step. It doesn't cancel a hung tool call and isn't reachable from outside the process. Treat it as the SIGTERM handler, not incident response.

### Q12 — When would you not build any of this — durable interrupts, expiry, trigger dedupe, a fleet-wide limiter?
**Testing:** the senior signal — knowing the wrong context for your own toolkit.
**Answer:** When the human is present and the wait is seconds — inline confirmation beats a durable interrupt. When there's one controlled trigger source that neither redelivers nor overlaps — dedupe is overhead. When it's one ambient agent, not a fleet — a shared rate limiter solves a coordination problem that doesn't exist yet. And when the actual requirement is exactly-once side effects or cross-service compensation — idempotency keys give at-least-once with duplicates suppressed, not a transactional guarantee; reach for Temporal instead.
**Follow-up trap:** *"When does the fleet-wide limiter become worth it?"* — when enough independently-scheduled agents can plausibly cluster and approach the org-wide ceiling together. The tell is a 429 you can't attribute to any single run being over its own budget — the constraint is fleet-wide, and a per-run fix won't touch it.

---

## Red flags that fail you

- Trusting a snapshot from pause time as still true hours later, instead of re-reading live state.
- No expiry on a pending approval — "waiting forever" treated as acceptable.
- Believing `interrupt()` resumes the next line rather than re-running the node from the top.
- Idempotency keys scoped only to tool calls, with no dedupe at the trigger layer.
- Checkpointing an open connection, file handle, or closure and being surprised it fails elsewhere.
- A kill switch checked once per loop iteration instead of at every tool-call boundary.
- Believing `RunControl.request_drain()` is an emergency stop rather than a graceful-shutdown hook.
- Per-run rate-limit backoff with no fleet-wide coordination, then surprise at synchronized 429 waves.
- "No logs in an hour" as the only signal for a dead run.
- Recommending SQLite for a multi-writer or multi-replica deployment.
- Assembling results only in a final message, so a budget-truncated run returns nothing.

## Cheat card

```
DURABLE INTERRUPT
  resume token = (thread_id, checkpointer), NOT a process or session
  approvals table: thread_id, payload, expires_at, consumed_at (atomic, single-use)
  re-validate PRECONDITIONS live, in the executing node, right before the side effect
  idempotency-key TTL must EXCEED the approval's own expiry window

CHECKPOINT STORAGE
  serializes: ids, paths, primitives. doesn't: sockets, file handles, locks, closures
  → nodes RE-ACQUIRE live resources every execution
  persisted large outputs → path in state, blob on SHARED storage, not local disk

SCHEMA EVOLUTION UNDER A LIVE THREAD
  completed threads: any topology change safe
  interrupted threads: NOT safe to rename/remove a node
  state keys: add/remove safe · RENAME loses saved value · ship via expand/contract

BUDGET-TRUNCATED RUNS
  write results to durable store AS PRODUCED · keep progress externally visible

interrupt() = NODE GRANULARITY (docs.langchain.com/oss/python/langgraph/interrupts)
  "restarts the ENTIRE node... code before interrupt() executes again"
  while-True + interrupt() in one node → EXPONENTIAL replay per resume
  fix: conditional edge to a node calling interrupt() ONCE per invocation
  order: side effect after interrupt/own node > naturally idempotent > idempotency key > @task

SQLITE TWO-PROCESS SHARING
  PRAGMA journal_mode=WAL   readers don't block writer; ~1000-page (~4MB) auto-checkpoint
  PRAGMA busy_timeout=5000+ retries instead of instant SQLITE_BUSY
  WAL fixes reader/writer, NOT writer/writer — still ONE writer
  3+ writers → busy_timeout expires anyway → PostgresSaver (MVCC)

TRIGGERS
  cron → lock on JOB IDENTITY if runtime can exceed interval
  event → dedupe on event_id (queues are at-least-once)
  webhook → dedupe on delivery_id; retention >= provider's redelivery window (days)

RATE-LIMIT BUDGET spans the FLEET, not one run
  Anthropic: per-org token-bucket RPM/ITPM/OTPM, continuous refill
    Start ~1,000/2M/400K · Scale ~10,000/10M/2M · cached reads excluded from ITPM
  independent per-run backoff → synchronized 429 herd at cron boundaries
  fix: shared token-bucket the SCHEDULER checks before dispatch

OBSERVABILITY FOR AN UNWATCHED RUN
  alert on last_checkpoint_at STALENESS vs. expected cadence, not "no logs"

KILL SWITCH
  soft: run_status checked at EVERY tool-call boundary
  hard: revoke credentials — works even if unreachable
  RunControl.request_drain() = graceful SIGTERM handler, NOT emergency stop

WHEN NOT TO
  human present, wait in seconds → inline confirm
  single trusted trigger → skip dedupe · one agent, no fleet → skip shared limiter
  need real exactly-once → Temporal, not idempotency keys
```

## Sources

- [Interrupts — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/interrupts) — node-granularity resume, the quoted restart behavior, exponential replay of `while True` + `interrupt()`, the conditional-edge fix, subgraph-as-function re-execution, idempotency guidance; accessed 2026-08-10
- [Introducing ambient agents](https://www.langchain.com/blog/introducing-ambient-agents) — "ambient does not mean fully autonomous," event-driven vs. conversation-driven design, agent-inbox pattern; accessed 2026-08-10
- [Use cron jobs — Docs by LangChain](https://docs.langchain.com/langsmith/cron-jobs) — LangGraph Platform cron semantics, fresh-thread-per-fire default; accessed 2026-08-10
- [SQLite — Write-Ahead Logging](https://www.sqlite.org/wal.html) — WAL mechanics, single-writer constraint, auto-checkpoint threshold; accessed 2026-08-10
- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — `busy_timeout` behavior under real contention; accessed 2026-08-10
- [LLM API Rate Limits (2026): OpenAI, Anthropic & DeepSeek RPM and TPM by Tier](https://www.requesty.ai/blog/rate-limits-for-llm-providers-openai-anthropic-and-deepseek) — Anthropic per-tier RPM/ITPM/OTPM, token-bucket replenishment, cached-read exclusion; accessed 2026-08-10
- [Agent kill-switch architecture: closing the 2026 containment gap](https://agentmodeai.com/agent-kill-switch-containment-architecture/) — kill-criteria vs. kill-architecture, the documented inability of many orgs to reliably stop a running agent; accessed 2026-08-10
- `T07-langgraph-durable` — checkpointer interface, `interrupt()` mechanics, Postgres production setup, `RunControl.request_drain()`, schema-migration rules (cross-referenced, not repeated)
- `T07-loop-engineering` — budgets, compaction cascade, stop conditions, resumability via typed event log (cross-referenced, not repeated)

## Changelog
- 2026-08-10 — created
