# Outbox, Inbox, Saga, CQRS, Event Sourcing

> **Track:** T21 Architecture & Design Principles · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T21-outbox-saga-cqrs` · **Tags:** patterns, distributed

## The 30-second version

All five of these exist to solve one problem: a single logical operation that must touch two things you cannot commit atomically together, usually a database and a message broker, or a database in one service and a database in another. The transactional outbox writes the event into the same local transaction as the business row, so a poller or CDC connector can drain it later with at-least-once delivery instead of a dual write that can silently diverge. The inbox is the same trick on the consumer side, deduplicating retried deliveries against a operation-id so at-least-once becomes effectively-once for you. A saga is what you do when the "single logical operation" spans multiple services and there is no ACID boundary left to fall back on: a sequence of local transactions, each with a compensating action, run either by a central orchestrator or by services reacting to each other's events. CQRS splits the write model from the read model so each can be shaped and scaled for its own workload, and it does not require event sourcing, though the two are frequently sold as a pair. Event sourcing makes the append-only log of events the source of truth instead of current-state rows, which buys a perfect audit trail and replayability, and costs you a second, much harder system to operate correctly.

## Why this gets asked

Because "dual write problem" is the fastest way to tell whether a candidate has actually run a service that publishes events, versus one who has only read the diagram. The interviewer has debugged the specific 2 a.m. page: the database commit succeeded, the Kafka publish threw, and now the order exists but no downstream system heard about it, or the reverse, an event went out for a transaction that then rolled back. They want the failure interleaving stated precisely, not "use two-phase commit" (which does not work across a database and a broker in practice, and which nobody actually runs). At staff level they are also checking whether you know CQRS and event sourcing are separable decisions, because most teams that reach for event sourcing did so because a blog post bundled it with CQRS, and lived to regret it.

---

## Lineage: past → present → future

**What came before.** The naive approach was the direct dual write: commit the database transaction, then publish to the broker in application code right after. This is not a bug people wrote by accident so much as the thing you write first, because it looks correct and passes every test that does not inject a crash between the two calls. Distributed transactions (two-phase commit, XA) were the textbook fix through the 1990s and 2000s, and they died in practice for the reason Pat Helland's *Life Beyond Distributed Transactions* (2007) named explicitly: a coordinator that blocks all participants while any one of them is slow or down does not survive at internet scale, and most message brokers (Kafka chief among them) never implemented an XA resource manager because nobody who ran a broker at scale wanted the availability hit. Saga as a concept predates microservices entirely: Hector Garcia-Molina and Kenneth Salem's 1987 paper *Sagas* proposed exactly this, breaking a long-lived transaction into a sequence of steps with compensations, for the same reason — long-lived locks kill throughput. Event sourcing's lineage runs through accounting ledgers (which have always been append-only, for audit reasons that predate computing) and was named and popularized for software by Martin Fowler and the DDD/CQRS community around 2005-2010, with Greg Young as its most persistent advocate.

**Where it stands now.** The transactional outbox plus CDC (Debezium reading the database's write-ahead log, or a native connector like Postgres logical replication) is the accepted default for reliable event publication in 2026; polling the outbox table is the fallback when you cannot run a CDC pipeline, at the cost of publish latency (typically a poll interval of 100ms-1s) and periodic query load on the outbox table. The live disagreement is less about the outbox itself, which is settled, and more about saga topology: orchestration wins on debuggability and centralized saga state (a single place to query "where is this order stuck"), choreography wins on decoupling and avoiding a saga-orchestrator becoming a second distributed monolith, and most teams that start with choreography for its "simplicity" end up building an ad hoc orchestrator once they need to answer "what happened to order 4471" without grepping five services' logs. CQRS without event sourcing is common and mostly uncontroversial: separate read replicas or read-optimized denormalized tables, updated by a projector consuming domain events or CDC, is a standard scaling move for read-heavy systems. Event sourcing as the system of record is the more contested one: it is genuinely deployed at scale (banking ledgers, EventStoreDB users, some fintech and audit-heavy domains) but it is also the pattern most commonly adopted for the wrong reason, chased for "flexibility" or "future-proofing" rather than because the domain has a real audit or temporal-query requirement.

**Where it's heading.** CDC-based outbox draining is displacing polling as CDC tooling matures and becomes easier to operate (managed Debezium/CDC offerings from Confluent, AWS DMS, and cloud-native change-stream primitives) — high confidence, already the trend. Saga orchestration is converging with durable execution engines (Temporal, AWS Step Functions, Restate): rather than hand-rolling a saga state machine and its own persistence, teams increasingly model the saga as a durable workflow where retry, compensation, and state persistence are the engine's job, not yours — medium-high confidence, and the more interesting framing is that "saga" and "durable execution" are converging vocabulary for the same underlying need. Event sourcing adoption looks flat to slightly declining outside its established niches, as more teams discover the operational cost (see below) after the first schema migration or the first GDPR deletion request; the honest speculative claim is that CQRS-without-event-sourcing plus an outbox for integration events will keep eating the use cases people used to reach for full event sourcing to solve.

---

## Mental model

```
DUAL WRITE (broken):                    OUTBOX (fixed):
  BEGIN TX                                BEGIN TX
    INSERT order                            INSERT order
  COMMIT TX                                 INSERT outbox_event   ← same TX
  publish(OrderCreated)  ← can fail       COMMIT TX
  here, after the commit,                relay/CDC reads outbox_event
  with no way back                       publish(OrderCreated)
                                          mark/delete outbox row
                                          (relay can crash here too —
                                           that's why delivery is
                                           at-least-once, not exactly-once)

SAGA (orchestrated):                    SAGA (choreographed):
  Orchestrator                            OrderService --OrderCreated--> PaymentService
   ├─ step1: reserve inventory                                            |
   │    fail → compensate: none needed                              charges card
   ├─ step2: charge payment                                               |
   │    fail → compensate: release inventory                    --PaymentCharged/Failed-->
   └─ step3: ship order                                                InventoryService
        fail → compensate: refund + release                    (each service reacts to
                                                                  the previous one's event)

CQRS:                                    EVENT SOURCING:
  writes -> write model (normalized)      writes -> append event to log (source of truth)
  reads  -> read model (denormalized,     reads  -> replay events, or read a
            eventually consistent,                  materialized projection built
            updated async from events)              by replaying/consuming the log
```

The throughline: every arrow that crosses a transaction boundary is a place where "succeeded" and "the other side knows about it" can disagree, and every pattern here is a specific, named way of making that disagreement recoverable instead of silent.

---

## How it actually works

### The dual-write problem, precisely

Given `BEGIN; INSERT INTO orders ...; COMMIT;` followed by `broker.publish(OrderCreated)`, there are exactly two bad interleavings:

1. DB commit succeeds, publish fails (broker down, network partition, process crash between the two calls) → the order exists, nothing downstream ever hears about it. Silent data loss from the consumer's perspective.
2. Publish succeeds, DB commit then fails or the process crashes before commit → an event went out describing a state change that never happened. Downstream services now believe something false.

Neither is rare under real failure rates; a crash-between-two-calls is a design flaw, not an edge case, because it happens on every deploy that restarts a process mid-request. **Observable symptom:** support tickets or reconciliation jobs finding orders with no corresponding shipment, or shipments for orders that don't exist in the source system, with no error anywhere in the logs, because from each system's local point of view it did exactly what it was told.

### Transactional outbox

Write the event as a row in an `outbox` table, in the same database transaction as the business write. A separate process drains it:

```sql
CREATE TABLE outbox (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aggregate_type TEXT NOT NULL,
  aggregate_id   TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  payload        JSONB NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```python
# untested sketch
def create_order(conn, order):
    with conn.transaction():
        order_id = conn.execute(
            "INSERT INTO orders (...) VALUES (...) RETURNING id", order
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
               VALUES (%s, %s, %s, %s)""",
            ("Order", order_id, "OrderCreated", json.dumps({"order_id": order_id, **order})),
        )
    # both rows commit together or neither does — this is the whole trick
```

Two draining strategies:

| Strategy | How | Latency | Cost |
|---|---|---|---|
| **Polling** | A job queries `WHERE published_at IS NULL ORDER BY created_at`, publishes, marks published, deletes old rows | Bound by poll interval, typically 100ms-1s | Extra read load on the table proportional to poll frequency |
| **CDC (Debezium et al.)** | A connector tails the DB's write-ahead log (Postgres WAL, MySQL binlog) and streams outbox inserts to Kafka directly, no polling query | Sub-second, log-tail latency | Operating a CDC pipeline: connector, offsets, schema registry |

Either way, delivery is **at-least-once**: the relay can crash after publishing but before marking the row done, and will republish on restart. This is why the consumer needs the inbox pattern, not because the outbox is broken.

### Inbox pattern (consumer-side dedup)

```sql
CREATE TABLE inbox (
  message_id TEXT PRIMARY KEY,   -- from the event, not generated here
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```python
# untested sketch
def handle(conn, event):
    with conn.transaction():
        inserted = conn.execute(
            "INSERT INTO inbox (message_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (event.id,),
        )
        if inserted.rowcount == 0:
            return  # already processed, skip — this is what makes at-least-once safe
        apply_business_effect(conn, event)
```

The insert-or-skip and the business effect must be in the **same transaction**, otherwise you have reintroduced a dual write one level down.

### Saga: orchestration vs choreography

**Orchestration** — a central coordinator issues commands and tracks saga state explicitly:

```python
# untested sketch
class OrderSaga:
    STEPS = ["reserve_inventory", "charge_payment", "ship_order"]

    def run(self, order_id):
        completed = []
        for step in self.STEPS:
            try:
                self.execute(step, order_id)
                completed.append(step)
            except StepFailed:
                for done_step in reversed(completed):
                    self.compensate(done_step, order_id)
                raise SagaFailed(order_id, failed_at=step)
```

**Choreography** — no coordinator; each service publishes an event, the next service reacts:

```
OrderService  --OrderCreated-->        InventoryService reserves stock, emits InventoryReserved
InventoryService --InventoryReserved--> PaymentService charges card, emits PaymentCharged/PaymentFailed
PaymentService --PaymentFailed-->       InventoryService reacts, releases stock (compensation)
```

| | Orchestration | Choreography |
|---|---|---|
| Saga state | Explicit, queryable in one place | Implicit, reconstructed from event streams across services |
| Coupling | Services coupled to the orchestrator's contract | Services coupled to each other's event schemas |
| Adding a step | Change the orchestrator | Change every service in the new dependency chain |
| Debugging "where's my order stuck" | One query | Distributed trace across N services |
| Failure mode at scale | Orchestrator becomes a bottleneck / a second monolith | Cascade of implicit ordering assumptions nobody wrote down |

**Compensation is not rollback.** A database rollback undoes a transaction that never committed, so no one else ever saw the intermediate state. A compensating transaction undoes a transaction that *did* commit and that other things may already have observed or acted on. `RefundPayment` is not `UndoChargePayment` — the charge happened, possibly a receipt emailed, possibly the customer already saw a confirmation. The compensation is a new, forward-moving business operation that happens to net out the effect, not a magic undo.

**The semantic-lock problem.** Between "inventory reserved" and "payment confirmed," the reserved inventory is locked out of the pool for other customers, but there's no database lock enforcing this, only saga logic. If the saga stalls (a step times out, a service is down), that inventory is semantically locked indefinitely unless you add a timeout that triggers compensation. This is the saga equivalent of a held mutex with no deadlock detector, and it is the single most common saga production bug: "why is our inventory count wrong" traces back to a saga that died mid-flight with no timeout-driven compensation.

### CQRS

Separate models for write and read:

```
Write path:  Command -> validate -> write model (normalized, enforces invariants) -> emit event
Read path:   event -> projector -> read model (denormalized, shaped for one query pattern)
             Query -> read model directly, never touches the write model
```

The read model is **eventually consistent** with the write model — the gap is the time between the write committing and the projector applying the resulting event, typically tens to low hundreds of milliseconds with an outbox+CDC pipeline, longer if the projector is polling or backlogged. This has a concrete UI consequence: a user who just submitted a form and is immediately redirected to a page reading from the projection can see stale or missing data for that window. The standard fixes are read-your-writes patterns (route the immediate post-write read to the write model or a cache seeded synchronously, then switch to the projection), or an optimistic UI update that doesn't wait for the round trip at all.

**CQRS does not require event sourcing.** The read model can be built by a projector that consumes ordinary domain events published via an outbox, applied to a denormalized table, with the write model still being plain rows in a normalized schema. This is the common case: most teams doing CQRS are not event-sourced.

### Event sourcing

The event log is the source of truth; current state is a fold over it.

```python
# untested sketch — a projection is just reduce()
def account_balance(events: list[dict]) -> int:
    balance = 0
    for e in events:
        if e["type"] == "Deposited":
            balance += e["amount"]
        elif e["type"] == "Withdrawn":
            balance -= e["amount"]
    return balance
```

- **Projections** are materialized views built by folding the event stream, kept up to date incrementally as new events arrive, and rebuildable from scratch by replaying the whole log — this is the entire value proposition: a bug in a projection is fixed by fixing the projector code and replaying, not by a data migration.
- **Snapshots** exist because replaying 500,000 events to answer "what's the balance now" is wasteful; periodically persist the folded state (every N events, e.g. N=100-500) and replay only the events since.
- **The brutal parts:**
  - **Schema evolution.** An event written in 2023 as `{"type": "OrderPlaced", "currency": "USD"}` and a 2026 version that always includes `"taxRate"` means every consumer forever must handle both shapes, via versioned event types, upcasting (transforming old-shape events to new-shape on read), or weak schemas that push the problem to every reader. There is no ALTER TABLE for an immutable log.
  - **GDPR / right-to-erasure.** An append-only log is structurally opposed to deletion. The two accepted mitigations are crypto-shredding (encrypt PII per-subject with a key you can later destroy, rendering the ciphertext permanently unreadable without ever mutating the log) and forgettable payloads (store PII in a separate mutable store, keep only a reference id in the event, delete from the mutable store on request). Both add a second system and a second thing that can be wrong.
  - **Debugging.** "What is the current state" requires replaying or trusting a projection; when a projection disagrees with expectation, you're debugging a fold over potentially millions of events rather than reading a row. Tooling for this (event-store query languages, replay-with-breakpoint) is far less mature than SQL tooling.

---

## Build it from scratch

Minimal outbox + relay + idempotent consumer, runnable with sqlite for the demo:

```python
# untested sketch
import sqlite3, json, uuid

def setup(conn):
    conn.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, total INTEGER)")
    conn.execute("""CREATE TABLE outbox (
        id TEXT PRIMARY KEY, event_type TEXT, payload TEXT, published INTEGER DEFAULT 0)""")
    conn.execute("CREATE TABLE inbox (message_id TEXT PRIMARY KEY)")

def create_order(conn, total):
    order_id = str(uuid.uuid4())
    with conn:
        conn.execute("INSERT INTO orders VALUES (?, ?)", (order_id, total))
        conn.execute(
            "INSERT INTO outbox (id, event_type, payload) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), "OrderCreated", json.dumps({"order_id": order_id, "total": total})),
        )
    return order_id

def relay(conn, publish_fn):
    rows = conn.execute("SELECT id, event_type, payload FROM outbox WHERE published = 0").fetchall()
    for row_id, event_type, payload in rows:
        publish_fn(row_id, event_type, json.loads(payload))   # can crash here — at-least-once
        conn.execute("UPDATE outbox SET published = 1 WHERE id = ?", (row_id,))
        conn.commit()

def consume(conn, message_id, event_type, payload):
    with conn:
        cur = conn.execute("INSERT OR IGNORE INTO inbox VALUES (?)", (message_id,))
        if cur.rowcount == 0:
            return "duplicate, skipped"
        # apply business effect here, in the same transaction
        return f"applied {event_type} for {payload}"
```

Full version with a saga orchestrator, a CQRS read-side projector, and tests that inject a crash mid-relay: no dedicated lab folder for this module yet; the pattern reuses the transactional/idempotency techniques exercised in the resilience labs (`labs/py/01-circuit-breaker/`) plus the sketch above.

---

## How it's done in production

| Concern | Tool / approach | What it adds over the sketch |
|---|---|---|
| CDC-based outbox draining | Debezium (Kafka Connect), AWS DMS, Postgres logical replication slots | Tails the WAL directly; no polling query load; ordering preserved per key |
| Saga orchestration | Temporal, AWS Step Functions, Camunda, or a hand-rolled state machine | Durable execution: retries, timers, and compensation survive process crashes without you persisting saga state yourself |
| Event store | EventStoreDB, Kafka-as-log (with compaction), Axon Server, or a Postgres table with an append-only convention | Optimistic concurrency on append (expected version check), stream subscriptions, snapshotting support |
| CQRS read models | Materialized views, a denormalized Postgres/Elasticsearch table updated by a consumer, or a cache | Query shape matches the access pattern instead of forcing joins on read |
| Schema registry | Confluent Schema Registry, AWS Glue Schema Registry | Enforces compatibility rules (backward/forward) so a producer can't ship a breaking event shape unnoticed |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Order exists, no downstream event ever arrives | Dual write instead of outbox; publish call failed silently after commit | Move to transactional outbox with CDC or a polling relay |
| Same event processed twice, double-charged customer | Consumer has no idempotency check | Inbox pattern: dedup on message id in the same transaction as the effect |
| Saga stuck forever, inventory never released | No timeout on a saga step; semantic lock held indefinitely | Add step timeouts that trigger compensation; use a durable-execution engine with built-in timers |
| Read model shows stale/missing data right after write | Eventual consistency window in the projector | Read-your-writes: route immediate post-write reads to the write model, or optimistic UI |
| Old consumers crash on new event shape | No schema versioning or compatibility check | Schema registry with backward-compatible evolution; upcasters for old versions |
| Cannot honor a deletion request | PII embedded directly in immutable events | Crypto-shredding or forgettable-payload pattern designed in from day one, not retrofitted |
| Outbox table grows unbounded | Rows never purged after publish | Delete or archive published rows on a retention policy; partition by created_at |
| Orchestrator becomes single point of failure / bottleneck | All saga traffic funneled through one coordinator with no HA | Run the orchestrator as a horizontally-scaled durable-execution engine, not a bespoke singleton service |

---

## Tradeoffs & when NOT to use it

- **Outbox and inbox are close to free** once you accept the extra table and a relay process; there is little reason not to use them for any cross-boundary write. The main cost is operational: someone owns the relay's health and the outbox table's growth.
- **Sagas are the wrong tool if you can still fit the operation in one database transaction.** A saga trades ACID guarantees for availability and service autonomy; if all the data lives in one service's database, just use a transaction and skip the compensating-transaction design work entirely.
- **Choreography looks simpler and becomes the harder system.** Every team that picks choreography "because it's decoupled" eventually needs to answer "what's the current state of saga X," and ends up either bolting on a tracking service (which is an orchestrator with extra steps) or debugging via distributed tracing across five services. Default to orchestration once there are more than two or three steps or any real compensation logic; choreography earns its keep mainly for genuinely independent, low-coordination event chains.
- **CQRS is overkill for a CRUD app with one query shape.** If reads and writes have the same shape and the same store serves both fine, splitting them buys eventual-consistency bugs for no scaling benefit. Reach for it when read and write load profiles diverge (heavy read fan-out, different query patterns, need to scale reads independently) — not by default.
- **Event sourcing is the one to be most skeptical of. Most teams that adopt it should not have.** It is justified when the domain genuinely needs a full audit trail as a first-class requirement (financial ledgers, regulatory record-keeping), needs to answer "what did we believe at time T" (temporal queries), or needs to rebuild wildly different projections from the same history repeatedly. It is not justified by "flexibility" or "in case we need it later" — that "later" cost shows up immediately, in every consumer needing to handle schema evolution, in GDPR requiring crypto-shredding infrastructure from day one, and in every engineer joining the team needing to learn to debug via replay instead of `SELECT *`. If you cannot name the specific query "what was true at time T" or "prove to an auditor exactly what happened" that only event sourcing answers, you are paying its cost for CQRS's benefit, which CQRS gives you without it.

---

## Interview questions

### Q1 — What is the dual-write problem, exactly?
**Testing:** whether you can state the failure precisely rather than gesture at "consistency issues."
**Answer:** A single logical operation writes to two systems that cannot commit atomically (typically a database and a message broker). Two bad interleavings: DB commits, publish fails — an event that should have gone out never does, and the state exists nowhere else. Or publish succeeds, DB transaction then fails or the process crashes before commit — a message goes out describing something that never actually happened. Both look correct in the happy path and both are triggered by ordinary failures (network blip, process restart during a deploy), not exotic edge cases.
**Follow-up trap:** *"Why not just use a distributed transaction / 2PC?"* — most message brokers, Kafka included, never implemented an XA resource manager, because a coordinator blocking all participants on the slowest one kills availability at scale. It's not merely unfashionable, it's largely unavailable for this exact pairing.

### Q2 — Walk me through the transactional outbox pattern.
**Testing:** mechanics, not just the name.
**Answer:** Write the event as a row in an outbox table inside the same local transaction as the business write, so both commit or neither does. A separate relay (polling query or CDC connector tailing the WAL) later reads unpublished rows, publishes them, and marks them done. Delivery is at-least-once because the relay can crash between publishing and marking, so consumers need their own dedup.
**Follow-up trap:** *"Polling or CDC, and why?"* — CDC (Debezium et al.) reads the write-ahead log directly, giving sub-second latency with no extra read load on the table; polling is simpler to stand up but adds latency bound by the poll interval and periodic query load. Say you'd start with polling if there's no CDC infrastructure yet and migrate once volume justifies it.

### Q3 — What does the inbox pattern add, and why can't the outbox alone guarantee exactly-once?
**Answer:** The outbox guarantees at-least-once delivery, never exactly-once, because the relay itself can fail between publish and mark-done. The inbox pattern makes the consumer idempotent: it inserts the incoming message's id into a dedup table inside the same transaction as applying the business effect, and skips if the id is already present. That combination, at-least-once delivery plus idempotent consumption, gives you effectively-once processing without ever needing true exactly-once semantics from the transport.
**Follow-up trap:** *"What if two different messages happen to reuse the same id?"* — that's a producer bug, not something the inbox can catch; the inbox trusts the message id is unique per logical event. If you can't guarantee that upstream, dedup on a content hash instead, understanding that's strictly weaker (two legitimately-different events with the same payload would collide).

### Q4 — Compensating transaction versus rollback. What's the actual difference?
**Answer:** A rollback undoes a transaction that never committed, so nothing else ever observed the intermediate state. A compensating transaction undoes a transaction that *did* commit, and other systems, users, or downstream steps may already have acted on it. `RefundPayment` is a new forward-moving business operation, not an undo of `ChargePayment` — the charge happened, a confirmation email may have gone out, the customer's bank already saw the debit. The compensation only nets out the effect; it does not erase history.
**Follow-up trap:** *"Give me an example where compensation genuinely can't fully undo the effect."* — sending a confirmation email. You can refund a payment and release inventory, but you can't un-send an email the customer already read. The saga has to either avoid emitting irreversible side effects until the saga is confident it will complete, or accept the compensation is imperfect and handle it with a follow-up (a "sorry, that order was cancelled" message).

### Q5 — Orchestration or choreography for a five-step checkout saga. Defend your choice.
**Answer:** Orchestration, once there are more than two or three steps with real compensation logic. A central coordinator gives you one place to query saga state ("where is order 4471 stuck"), one place to add a new step, and explicit, testable compensation logic. Choreography's appeal (no central point of coupling) is real for genuinely independent low-coordination chains, but a five-step checkout has enough interdependency and enough need for a support engineer to answer "what happened to this order" that the implicit, cross-service state choreography produces becomes the bigger cost.
**Follow-up trap:** *"Doesn't the orchestrator become a distributed monolith itself?"* — it can, if every service's release now has to coordinate with the orchestrator's version. Mitigate by keeping the orchestrator's contract with each service narrow (command in, event out) and versioning that contract independently, and by running the orchestrator on a durable-execution engine (Temporal, Step Functions) rather than a bespoke singleton, so it scales horizontally instead of becoming a bottleneck.

### Q6 — What's the semantic-lock problem in sagas?
**Testing:** whether you've actually operated one, not just read the pattern name.
**Answer:** Between two saga steps, a resource can be logically reserved (inventory held, a discount applied) with nothing enforcing that reservation at the database level except the saga's own logic continuing to run. If the saga stalls, that resource stays semantically locked indefinitely. It's the saga equivalent of a held mutex with no deadlock detector.
**Follow-up trap:** *"How do you fix it?"* — a timeout on every step that, if exceeded, triggers compensation for everything completed so far, ideally enforced by the saga engine itself (Temporal timers, Step Functions timeouts) rather than a length of application code someone has to remember to write for every new saga.

### Q7 — Does CQRS require event sourcing?
**Answer:** No, and conflating them is the most common mistake in this area. CQRS just means separate read and write models; the read model can be a plain denormalized table kept up to date by a projector consuming ordinary domain events published via an outbox, with the write side being ordinary normalized rows. Event sourcing is a separate decision about whether the write side's source of truth is an event log or current-state rows. Most teams doing CQRS in production are not event-sourced.
**Follow-up trap:** *"So why do people always mention them together?"* — because Greg Young and the early CQRS/DDD community demonstrated them together and the combination made for a clean conference talk. The coupling in people's minds is historical, not architectural.

### Q8 — CQRS's read model is eventually consistent. What does that do to the UI?
**Answer:** A user who just wrote data and is immediately shown a page reading from the projection can see stale or missing data for the propagation window, typically tens to low hundreds of milliseconds with an outbox+CDC pipeline. Fix with read-your-writes: route the immediate post-write read to the write model or a synchronously-seeded cache, then switch subsequent reads to the projection; or design the UI to optimistically show the write without waiting on the read round trip.
**Follow-up trap:** *"What if the write model can't answer the read's query shape at all?"* — that's common once the read model has denormalized into a shape the write model was never designed to serve. Then you either accept a brief inconsistency window and communicate it in the UI (a spinner, "processing"), or maintain a narrow synchronous fallback query against the write model just for the immediate post-write case.

### Q9 — What's the single biggest operational cost of event sourcing that people underestimate?
**Answer:** Schema evolution of the event log itself. Every event ever written stays around forever; a shape change means every consumer, forever, must handle both the old and new shapes, via versioned event types and upcasters, because there's no `ALTER TABLE` for an immutable append-only log. Teams that haven't hit this yet usually haven't been in production long enough to need to change an early event's shape.
**Follow-up trap:** *"How do you version an event type in practice?"* — tag every event with a schema version, write an upcaster function per historical version that transforms it to the current shape on read, and enforce compatibility rules (backward-compatible additions only, no field removal/retyping) via a schema registry so a producer can't ship a breaking change unnoticed.

### Q10 — How do you handle a GDPR deletion request in an event-sourced system?
**Answer:** You cannot delete or mutate an event once written without breaking the source-of-truth guarantee, so the accepted mitigations are crypto-shredding (encrypt PII per-subject with a key stored outside the log; destroy the key on a deletion request, rendering the ciphertext permanently unreadable without ever touching the log) or forgettable payloads (keep PII in a separate mutable store, only a reference id in the event, delete from the mutable store on request). Both require designing this in before you have real PII in the log; retrofitting either onto years of existing events is a project of its own.
**Follow-up trap:** *"Which would you pick and why?"* — forgettable payloads if you already have a mutable PII store for other reasons (most systems do, for operational lookups); crypto-shredding if PII is scattered across many event types and centralizing it into a separate store is itself a large migration. There's no universally right answer; state the tradeoff.

### Q11 — When would you explicitly recommend against event sourcing?
**Answer:** When nobody can name a specific requirement — a real audit mandate, a "what did we believe at time T" query, or a genuine need to rebuild materially different projections repeatedly — that only the event log satisfies. If the actual ask is "keep a history of changes" or "enable CQRS," a normal table plus an audit log or CDC-driven outbox gets you most of the value at a fraction of the operational cost. Event sourcing adopted for "future flexibility" is the single most common architecture regret reported by teams that have lived with it for a few years.
**Follow-up trap:** *"Your team already event-sourced this service and it's causing pain. Do you migrate off it?"* — depends on whether the pain is schema evolution (fixable with better upcasting discipline and a schema registry, often not worth a rewrite) or the team genuinely never needed the audit/replay properties (worth planning a migration to CQRS-over-normal-tables, but expect it to be a multi-quarter project, not a quick fix, since every consumer that reads the event stream needs a replacement).

### Q12 — Design the reliability layer for a checkout flow spanning Orders, Inventory, and Payments services.
**Testing:** synthesis under a realistic scenario.
**Answer:** Each service owns its own database and publishes domain events via a transactional outbox drained by CDC. An orchestrated saga (on a durable-execution engine, not hand-rolled) coordinates: reserve inventory, charge payment, confirm order; each step has a compensation (release inventory, refund payment) and a timeout that triggers compensation if the step stalls, closing the semantic-lock window. Consumers of each event use the inbox pattern to dedup against at-least-once delivery. A CQRS read model, projected from the same domain events, serves the order-status page so it doesn't hit three services' write databases on every page load. No event sourcing unless there's a stated audit requirement; the outbox events plus a simple state column per aggregate are enough.
**Follow-up trap:** *"Where would you add event sourcing here, if anywhere?"* — the Payments service specifically, if there's a regulatory requirement to reconstruct exactly what happened to a charge over time (disputes, chargebacks, audits) — that's the one sub-domain in this flow with a concrete, nameable reason. Orders and Inventory don't need it.

### Q13 — A saga step succeeds, but its compensating action then also fails. What now?
**Testing:** whether you've thought past the happy-path compensation story.
**Answer:** This is the case the saga literature calls a "compensation failure" and most implementations handle badly. The compensation should itself be retried with the same idempotency and outbox discipline as any other write, and if it exhausts retries, the saga needs a terminal failure state that pages a human rather than silently giving up — the alternative is a customer permanently double-charged or inventory permanently short, discovered only by reconciliation weeks later.
**Follow-up trap:** *"So compensations need to be more reliable than the steps they undo?"* — effectively yes, because there's no compensation for a failed compensation; the chain has to terminate somewhere in a state a human can act on. Design compensations to be simple, idempotent, and as failure-resistant as you can make them, and instrument saga terminal-failure states as a paged alert, not a log line.

### Q14 — How would you test a saga's compensation logic?
**Answer:** Inject a failure at every step boundary in an integration test and assert the full compensation chain runs and leaves the system in a consistent observable state — not just that compensation was "called," but that inventory is actually released and payment actually refunded. Also test the timeout path specifically: a step that never responds should trigger compensation, not hang forever. A fake clock, the same discipline used for testing circuit breakers, avoids real sleeps in the test suite.
**Follow-up trap:** *"What's the one saga test everyone forgets?"* — the compensation-of-a-compensation-boundary case: the last completed step's compensation itself fails. Most test suites cover "step N fails, compensate 1..N-1" and stop there, never testing what happens when the compensation itself doesn't succeed.

### Q15 — CQRS read model or a cache. When is a cache the wrong answer and CQRS the right one?
**Answer:** A cache is a copy of the same shape of data, invalidated or expired, useful when the read is simply the write data served faster. A CQRS read model is a *different shape* of the data, built by a projector, useful when the read pattern genuinely doesn't match the write model's schema (heavy joins collapsed into one denormalized row, search-optimized indices, aggregations precomputed). If you find yourself doing the same expensive join on every cache miss, that's a signal you actually want a materialized, incrementally-updated read model, not a bigger cache.
**Follow-up trap:** *"Isn't a materialized view basically free in Postgres now?"* — a standard materialized view is a good CQRS read model for simple cases, but it's refreshed on a schedule or on demand, not incrementally on each event, so for a low-latency read model you still want an event-driven projector unless the staleness of a periodic refresh is acceptable.

---

## Red flags that fail you

- Proposing two-phase commit across a database and a message broker as the fix for dual writes.
- Calling a compensating transaction a "rollback."
- Saying CQRS implies event sourcing, or the reverse.
- Not knowing that outbox delivery is at-least-once, not exactly-once.
- Choreography with no answer for "how do you know where a saga is stuck."
- Recommending event sourcing without naming a specific requirement it uniquely satisfies.
- No mention of GDPR/deletion when discussing event sourcing in production.
- A saga design with no step timeouts (the semantic-lock problem left unaddressed).

---

## Cheat card

```
DUAL WRITE PROBLEM   commit DB + publish event not atomic → 2 bad interleavings:
                      commit ok/publish fails = silent loss; publish ok/commit fails = false event

OUTBOX                write event row in SAME TX as business write
                       relay: poll (100ms-1s latency) or CDC (Debezium, tails WAL, sub-second)
                       delivery = AT-LEAST-ONCE (relay can crash between publish and mark-done)

INBOX                  dedup incoming message id in SAME TX as applying the effect
                       at-least-once delivery + idempotent consumer = effectively-once

SAGA                   sequence of local TXs + compensations, no cross-service ACID
                       orchestration: central coordinator, queryable state, default choice >2-3 steps
                       choreography: services react to events, decoupled, state is implicit
                       compensation ≠ rollback: undoes a COMMITTED effect, doesn't erase history
                       semantic lock: resource held only by saga logic → ALWAYS add step timeouts

CQRS                   separate read/write models. DOES NOT require event sourcing.
                       read model eventually consistent (~10s-100s ms with outbox+CDC)
                       fix for stale-read-after-write: read-your-writes or optimistic UI

EVENT SOURCING         event log = source of truth; state = fold over events; snapshot every N (100-500)
                       brutal parts: schema evolution (upcasters, schema registry),
                       GDPR (crypto-shredding or forgettable payloads), debugging (replay, not SELECT)
                       WHEN NOT TO: no named audit/temporal-query requirement = don't. Most teams shouldn't.

DURABLE EXECUTION      Temporal / Step Functions absorb saga retry+timer+compensation as engine features
```

## Sources

- [The Transactional Outbox Pattern: Reliable Event Publishing](https://james-carr.org/posts/2026-01-15-transactional-outbox-pattern/) — accessed 2026-08-01
- [Debezium Outbox Pattern: Reliable Event Streaming for Microservices — RisingWave](https://risingwave.com/blog/debezium-outbox-pattern-microservices/) — accessed 2026-08-01
- [Saga Design Pattern — Azure Architecture Center, Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga) — accessed 2026-08-01
- [Saga Pattern: Orchestration vs Choreography — ByteByteGo](https://blog.bytebytego.com/p/saga-pattern-demystified-orchestration) — accessed 2026-08-01
- [Pattern: Saga — microservices.io](https://microservices.io/patterns/data/saga.html) — accessed 2026-08-01
- [How to deal with privacy and GDPR in Event-Driven systems — Event-Driven.io](https://event-driven.io/en/gdpr_in_event_driven_architecture/) — accessed 2026-08-01
- [Event Sourcing Production Anti-Patterns: Schema Evolution, Snapshotting, and Event Store Scaling](https://www.youngju.dev/blog/architecture/2026-03-07-architecture-event-sourcing-cqrs-production-patterns.en) — accessed 2026-08-01
- [GDPR Compliance — EventSourcingDB docs](https://docs.eventsourcingdb.io/best-practices/gdpr-compliance/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
