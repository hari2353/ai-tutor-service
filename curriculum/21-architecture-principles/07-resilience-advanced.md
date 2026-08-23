# Load Shedding, Backpressure, Hedged Requests, Idempotency Keys, DLQ

> **Track:** T21 Architecture & Design Principles · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T21-resilience-advanced` · **Tags:** resilience
> **Lab:** `labs/java/01-rate-limiter/`

## Why this gets asked

`T21-resilience-catalogue` covers timeout, retry, circuit breaker, and bulkhead — all of them protect *you* at the edge where you call someone else. This module is the sequel because that catalogue has a gap: it says nothing about what to do when the load is arriving at *you*, faster than you can serve it, and there is no breaker to trip because nothing downstream is failing — your own service is the bottleneck. The interviewer has been on call during a load spike (a marketing push, a retry storm from an upstream client, a re-index job that fanned out) where CPU sat at 100%, queues grew, and every request got slower instead of some requests failing fast. They want to know if you'd reach for load shedding and backpressure, not just add more retries on top of an already-overloaded system. The second half — hedged requests, idempotency keys, DLQs — tests whether you can reason about tail latency and safe-retry-at-scale, which is where senior candidates usually stop and staff candidates keep going.

## The 30-second version

Four more tools past the resilience catalogue. **Load shedding** is admission control: reject the cheapest possible request at the front door, prioritized by criticality, rather than accepting everything and having every in-flight request degrade together — shedding early is O(1) per rejected request, collapsing late means every accepted request pays the cost of an overloaded system and most of them fail anyway. **Backpressure** is a protocol-level signal telling a producer to slow down, backed by a *bounded* queue; an unbounded queue doesn't prevent failure, it just converts an immediate, visible failure into a slow, invisible one — latency grows with no single error ever logged, until something (OOM, a health check) kills the whole process at once. **Hedged requests** trade a small amount of extra load, on the order of 2-5%, for a large cut in tail latency, by firing a duplicate request after the first one has run longer than its p95 and taking whichever answer comes back first — only safe on idempotent reads. **Idempotency keys** make retried writes safe by having the server remember it already did the work, and the interesting failure is the race where two concurrent retries both check the key store, both find nothing, and both proceed. **DLQs** catch messages that exhausted their retries so one poison message can't block a queue behind it; the pattern only works if someone owns draining it, and a DLQ nobody drains is worse than no DLQ, because it manufactures false confidence that failures are being handled.

---

## Lineage: past → present → future

**What came before.** The resilience catalogue's four patterns are about a single outbound call to a single dependency. They say nothing about *inbound* overload, because the vocabulary for that came from a different lineage: TCP congestion control (Van Jacobson, 1988) established that a network under contention needs the *sender* to back off based on a signal from the receiver, not the receiver simply dropping packets silently. Queueing theory gave the math — Little's Law (John D. C. Little, 1961: `L = λW`, the number of items in a system equals arrival rate times time in system) — decades before anyone applied it to service capacity planning. Early web servers handled overload with nothing more than an OS-level accept queue and a process pool; when the pool exhausted, new connections just piled up until the OS refused them, which is load shedding by accident rather than by design. Google's *Tail at Scale* paper (Dean & Barroso, 2013) is the origin of hedged requests as a named technique, arising from the observation that at fan-out scale, a request touching 100 backends each with a 1% chance of a slow response has roughly a 63% chance of hitting at least one straggler (`1 - 0.99^100 ≈ 0.63`) — averages stop being the right metric and the tail becomes the product. Idempotency keys as a documented API contract trace to Stripe's 2017 write-up on building a payments API where retries are mandatory but double-charging is not an option.

**Where it stands now.** Google's SRE book (2016) formalized load shedding with a criticality model — requests are tagged `CRITICAL_PLUS`, `CRITICAL`, `SHEDDABLE_PLUS`, `SHEDDABLE`, and under load the lowest tier sheds first — and this pattern (priority-tiered admission control, not blanket rejection) is now the default recommendation at every hyperscaler's SRE org, though most mid-size companies still ship a single global rate limiter with no priority tiers at all. Backpressure is a first-class protocol concept in Reactive Streams (2013, standardized into `java.util.concurrent.Flow` in Java 9) and in HTTP/2's flow-control frames, which gRPC inherits — a stream gets a receive window (64 KiB, `65536` bytes, by default) and the sender must wait for `WINDOW_UPDATE` before sending more; the live disagreement is that most application code above the transport layer still uses in-memory unbounded collections (`asyncio.Queue()`, an unbounded `ArrayBlockingQueue` substitute, a Python `list` used as a buffer) with no signal back to the producer at all, so protocol-level backpressure exists but application-level backpressure is inconsistently adopted. Hedged requests remain underused relative to how well understood they are — most engineers who can recite "circuit breaker" have never implemented a hedge, because it requires the operation to be cheaply cancellable and genuinely idempotent, which rules out most writes. Idempotency keys are now a standard header (`Idempotency-Key`) across Stripe, PayPal, and most payment and order-management APIs, and DLQs are a built-in feature of every major queue (SQS, Kafka via dead-letter topics, GCP Pub/Sub, RabbitMQ) rather than something you build yourself.

**Where it's heading.** Adaptive, latency-inferred admission control (the same direction as adaptive concurrency limits from the resilience catalogue — Netflix's `concurrency-limits`, Envoy's adaptive limiter) is replacing static thresholds for load shedding, and this is shipping today, not speculative. Cost-aware variants of all four patterns are emerging for LLM and agent workloads specifically: a hedge on a $0.02 LLM call is a real dollar cost multiplier at volume, not just extra network load, and shedding decisions increasingly need to account for token budget, not just queue depth or CPU. That direction is real but the tooling for it is immature — most agent frameworks in 2026 still apply plain HTTP-era resilience primitives to LLM calls without adjusting for the cost asymmetry. More speculatively, durable-execution engines (Temporal, Restate) are starting to absorb DLQ-and-replay as a built-in property of a workflow's persisted history rather than a queue-level bolt-on, which would remove the "nobody drains it" failure mode structurally rather than procedurally — treat this as a direction of travel, not a settled default.

---

## Mental model

```
                         ┌─────────────────────────────────────────┐
 flood of requests ─────▶│  ADMISSION CONTROL (load shedding)       │
                         │  cheap check BEFORE real work starts:    │
                         │  queue depth? CPU? priority tier?        │
                         │  reject SHEDDABLE first, cheaply ────┐   │
                         └───────────────────┬───────────────────┘  │
                                             ▼                     ▼
                                   ┌──────────────────┐      fast reject
                                   │  BOUNDED QUEUE    │      (503, cost ~1ms)
                                   │  size = λ × W_max │
                                   │  (Little's Law)   │
                                   │  full → signal    │
                                   │  BACKPRESSURE     │
                                   │  upstream to slow │
                                   └────────┬──────────┘
                                            ▼
                                  ┌───────────────────┐
                                  │  do the work       │
                                  │  (idempotent? →     │
                                  │   safe to hedge/    │
                                  │   safe to retry)    │
                                  └────────┬────────────┘
                                           │  exhausted retries
                                           ▼
                                   ┌───────────────┐
                                   │      DLQ       │──▶ someone must own this
                                   └───────────────┘     or it's a graveyard
```

The admission-control gate and the queue bound are the same idea applied at two different points: shed *before* you even queue the request, and bound the queue so that anything admitted still gets served within a latency you can defend. Neither one is optional if the other exists — a bounded queue with no shedding just moves the rejection point from "instant 503" to "503 after sitting in a full queue," and shedding with an unbounded queue behind it never actually triggers because the queue absorbs everything until it OOMs.

---

## How it actually works

### 1. Load shedding — reject cheap, reject early

Admission control means deciding whether to accept a request *before* doing the work that would make it expensive to reject — ideally before deserializing the body, before opening a DB connection, before starting an LLM call.

**Priority tiers, not a single threshold.** Google's SRE-book model tags every request with a criticality: `CRITICAL_PLUS` (must succeed — payment capture), `CRITICAL` (should succeed — user-facing reads), `SHEDDABLE_PLUS` (nice to have — recommendations), `SHEDDABLE` (best-effort — background prefetch, analytics pings). Under load, shed lowest tier first. A single global rate limiter with no tiers sheds indiscriminately, which means a health check, a login, and a "related products" carousel all have equal odds of getting rejected — the carousel should be sacrificed first every time.

```python
# untested sketch — admission control by priority, cheapest possible check
from enum import IntEnum
import time

class Priority(IntEnum):
    SHEDDABLE = 0
    SHEDDABLE_PLUS = 1
    CRITICAL = 2
    CRITICAL_PLUS = 3

class AdmissionController:
    def __init__(self, max_inflight: int):
        self.max_inflight = max_inflight
        self.inflight = 0
        # as load rises, the tier allowed to enter shrinks
        self.min_priority_at_load = {
            1.0: Priority.SHEDDABLE,
            0.85: Priority.SHEDDABLE_PLUS,
            0.70: Priority.CRITICAL,
        }

    def admit(self, priority: Priority) -> bool:
        load = self.inflight / self.max_inflight
        threshold = Priority.CRITICAL_PLUS
        for frac, tier in sorted(self.min_priority_at_load.items()):
            if load <= frac:
                threshold = tier
                break
        return priority >= threshold
```

**Why shed early beats collapsing late.** Once a request is admitted, it consumes a thread, a DB connection, maybe a GPU slot. If the system is already over capacity, that request will very likely time out or fail downstream anyway — you paid the full cost of processing and still failed. A concrete number: a service provisioned for 500 rps at 100ms p99 that receives a 2,000 rps spike has two paths. Without shedding: all 2,000 rps get accepted, queueing delay balloons, p99 climbs past client timeouts, clients retry (amplifying load per the retry math in `T21-resilience-catalogue`), and the service enters a death spiral where it is doing 4x the useful work of before while serving close to 0% of requests successfully. With shedding at the door: 500 rps admitted continue to see ~100ms p99, and 1,500 rps get an immediate, cheap 503 — a rejected request costs on the order of 1ms of CPU versus the full request latency it would have burned before failing anyway.

### 2. Backpressure — a protocol, not a queue

Backpressure is the producer *slowing down because the consumer told it to*, as opposed to the producer never finding out there's a problem. The three real implementations:

- **Reactive Streams** (`request(n)` demand signaling): the subscriber pulls exactly as much as it can process; the publisher is contractually forbidden from sending more than requested. This is *pull*, not push, and it's the cleanest form because there's no ambiguity about who's allowed to send what.
- **gRPC / HTTP/2 flow control**: byte-based, per-stream. Each stream gets a receive window, `65536` bytes by default, and the sender must wait for a `WINDOW_UPDATE` frame before exceeding it. This exists whether or not your application code thinks about it — but if your handler processes messages faster than it applies backpressure logically (e.g., buffering deserialized objects in an unbounded list before handling them), you've defeated it one layer up.
- **Bounded queues with an explicit reject/block policy**: the crudest but most common form. A bounded `queue.Queue(maxsize=N)` in Python, or Java's `ArrayBlockingQueue`, blocks the producer (or raises) once full — that block *is* the backpressure signal.

**The unbounded-queue failure, and why it's dangerous specifically because it's silent.** An unbounded queue (`asyncio.Queue()` with no `maxsize`, a `list` used as a buffer, an in-memory channel with no cap) never rejects. If the consumer falls behind the producer for any sustained period, the queue grows. Nothing errors. Nothing alerts. Latency for items already in the queue grows linearly with queue depth, but every individual *enqueue* still succeeds instantly, so your health check and your error rate both look fine while your p99 (measured end-to-end) silently climbs from 50ms to 50 seconds. The failure resolves itself eventually — but violently: an OOM kill, or a liveness probe timing out and the orchestrator restarting the process, at which point every queued item is lost at once. The observable symptom in a trace: request latency growing smoothly and monotonically over minutes with zero corresponding error-rate increase, followed by a step-function process restart.

**Sizing the bound with Little's Law.** `L = λW` — queue length equals arrival rate times the maximum latency you're willing to tolerate for something sitting in it. A pipeline processing 1,000 items/second where anything older than 5 seconds is no longer useful (a stale price quote, an expired session action) should bound the queue at `1000 × 5 = 5,000` items, not "whatever fits in memory." A queue sized at 5,000,000 for the same system represents a 5,000-second backlog — by the time the last item is processed, its result is worthless, and you've built a system that looks like it's keeping up while actually accumulating five thousand seconds of debt.

### 3. Hedged requests — buying tail latency with a little extra load

The problem hedging solves: at fan-out, tail latency compounds. If a single backend has a 1% chance of a slow response on any call, a request that fans out to 100 of them has `1 - 0.99^100 ≈ 63%` odds of hitting at least one straggler — so your p50-looking backend produces a terrible aggregate p99.

**The mechanism.** Send the request. If no response arrives within some threshold — typically the *p95* latency for that call class, not a guess — fire a second, identical request to a different replica. Take whichever response returns first; cancel the other. Google's canonical example (BigTable lookups across a 1,000-key read spread over 100 servers): sending a hedge after a 10ms delay reduced p999 from **1,800ms to 74ms** while increasing total request volume by only about **2%**. The general guidance from the same paper: hedging after the p95 threshold typically costs on the order of **5%** extra load for most of the tail-latency benefit, because 95% of requests never trigger the hedge at all.

**The cost, stated plainly.** This is not free — it's an explicit tradeoff of load for latency. Only ever hedge:
- **Idempotent, side-effect-free operations.** Reads, or writes behind an idempotency key (see below).
- **Operations cheap enough that 2-5% more volume is affordable.** Hedging a $0.02 LLM completion call at scale is a real, measurable cost increase, not just "a bit more network traffic" — treat this as a budget decision, not a free latency win.
- **When the first-to-return result can actually be raced and the other cancelled**, which requires cancellation propagation (see the resilience catalogue's discussion of client timeouts not stopping server-side work — the same caveat applies here: cancelling the client side doesn't necessarily stop the loser's server-side work).

```python
# untested sketch — hedged request against two replicas
import asyncio

async def hedged_call(fn, args, hedge_delay_s: float):
    primary = asyncio.create_task(fn(*args))
    done, _ = await asyncio.wait({primary}, timeout=hedge_delay_s)
    if primary in done:
        return primary.result()
    hedge = asyncio.create_task(fn(*args))          # second replica ideally
    done, pending = await asyncio.wait(
        {primary, hedge}, return_when=asyncio.FIRST_COMPLETED
    )
    for p in pending:
        p.cancel()                                  # best-effort; doesn't stop server work
    return done.pop().result()
```

### 4. Idempotency keys — making a retried write safe

**Design.** The client generates a unique key per *logical* operation (a UUID, not derived from request content alone unless you also validate the content matches on replay) and sends it as a header, e.g. `Idempotency-Key: 3fa8...`. The server, in the same transaction as the business write, records `(key → outcome)`. On a repeat with the same key, the server returns the stored outcome instead of redoing the work.

**Storage and TTL.** A dedup store needs an atomic write path — `INSERT ... ON CONFLICT DO NOTHING` in Postgres, checked against the affected-row count, or a Redis `SETNX` — never a naive read-then-write, which races. The TTL must exceed your maximum plausible retry window: Stripe uses a **24-hour** TTL on its v1 API and **30 days** on v2, reflecting that a client might legitimately retry a failed request the next day after a deploy or an outage, not just within the next few seconds.

**The race that catches almost everyone.** Two concurrent retries for the same logical operation (a client that fires a retry on a timeout while the original request is still in flight, or two threads racing a "resume where we left off" path) both check the dedup store, both find no existing key, and both proceed to do the work — because a plain existence check is not atomic with the insert. The fix is to make claiming the key and starting the work one atomic step: `INSERT ... ON CONFLICT DO NOTHING` and check `rowcount`; if `0`, someone else already claimed it, so either poll/wait for their result or return `409 Conflict` and let the client back off. A row with a `status = 'in_progress'` value, written atomically, lets the second caller distinguish "already done, here's the cached response" from "in flight, retry shortly" — collapsing that distinction back into a boolean "exists or not" is exactly how the race reappears.

```python
# untested sketch — atomic claim, not read-then-write
def claim_idempotency_key(conn, key: str) -> str:
    """Returns 'claimed' | 'in_progress' | 'done:<cached_response>'"""
    row = conn.execute(
        """INSERT INTO idempotency_keys (key, status, created_at)
           VALUES (%s, 'in_progress', now())
           ON CONFLICT (key) DO NOTHING
           RETURNING status""",
        (key,),
    ).fetchone()
    if row:
        return "claimed"                     # we own it, do the work
    existing = conn.execute(
        "SELECT status, response FROM idempotency_keys WHERE key = %s", (key,)
    ).fetchone()
    return f"done:{existing.response}" if existing.status == "done" else "in_progress"
```

### 5. Dead letter queues — the safety net, and the graveyard it becomes

**When a message goes to the DLQ.** After a consumer has received and failed to process the same message more than a configured number of times. SQS's `maxReceiveCount` defaults to **10** and can go up to **1,000**; Kafka has no built-in DLQ, so it's a convention — a consumer that fails processing publishes the message (plus failure metadata) to a separate `*.dlq` topic itself.

**Replaying safely.** A message in the DLQ failed for a reason — a bug, a schema mismatch, a downstream outage that has since recovered. Blind replay assumes the *only* reason was transient, which is often false. Safe replay: (1) inspect a sample first, not the whole backlog blind; (2) fix the root cause before replaying if it was a bug, or you'll refill the DLQ immediately; (3) replay through the *same* idempotent consumer path, at a controlled rate (not "dump 50,000 messages back onto the queue at once," which is its own load spike); (4) replay must be idempotent-safe, because the original message may have partially succeeded before failing — this is exactly where idempotency keys pay for themselves a second time.

**The DLQ nobody drains — a real organizational failure, not just a technical one.** A DLQ is created, wired up correctly, and then nobody owns alerting on its depth. It quietly grows for months. The failure surfaces only when a customer complains — a refund never processed, a notification never sent — and someone discovers 40,000 unprocessed messages sitting in a queue that has been there the whole time. The observable symptom: DLQ depth as a metric that exists in a dashboard nobody looks at, with no alert threshold and no runbook attached to it. **A DLQ without an owner and an alert is worse than no DLQ**, because its mere existence lets a team believe failures are being handled when they are, in fact, being filed away and forgotten.

**Retry budgets vs max-attempts (recap).** `T21-resilience-catalogue` derives this in full: a per-request `maxAttempts` says nothing about aggregate load, while a fleet-level retry budget (cap retries at roughly 10-20% of total request volume) is what actually bounds amplification. The same principle governs DLQ redrive counts — `maxReceiveCount` is a per-message cap, but a fleet-wide spike of poison messages (a bad deploy that makes every message fail) will still exhaust a downstream dependency at 10x normal load before any of them reach the DLQ, unless you also have a circuit breaker on the consumer side.

---

## Build it from scratch

The bulkhead and circuit breaker implementations live in `T21-resilience-catalogue`'s companion lab (`labs/py/01-circuit-breaker/`); this module's from-scratch pieces (admission controller, bounded-queue backpressure, hedged call, atomic idempotency claim) are given inline above as the runnable core of each pattern — each is small enough to hand-roll in an interview, and each is `# untested sketch` because they omit production concerns (metrics emission, config hot-reload, distributed coordination for the idempotency store) covered in the next section.

---

## How it's done in production

| Pattern | Managed / library version | What it adds over the sketch |
|---|---|---|
| Load shedding | Envoy adaptive concurrency limiter, Netflix `concurrency-limits`, Google's per-RPC criticality metadata | Infers capacity from observed latency instead of a static threshold; propagates criticality across service hops via request metadata |
| Backpressure | Reactive Streams (`Flow` in Java 9+, Project Reactor, RxJava), gRPC flow control (built into HTTP/2) | Standardized demand-signaling contract; no custom protocol needed between hops |
| Hedged requests | Finagle (Twitter) has native hedging support; most other stacks hand-roll it | Finagle ties hedge timing to a running latency percentile automatically rather than a hardcoded delay |
| Idempotency keys | Stripe-style `Idempotency-Key` header + Postgres unique constraint, or Redis `SETNX` with TTL | Handles the concurrent-claim race and response caching; some frameworks (e.g. `stripe`-pattern libraries) provide it as middleware |
| DLQ | AWS SQS redrive policy, Kafka dead-letter topic convention, GCP Pub/Sub dead-letter topics | `StartMessageMoveTask`/`ListMessageMoveTasks` (SQS) give managed, rate-controlled redrive without hand-rolled replay tooling |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| p99 climbs smoothly for minutes, error rate stays flat, then the process restarts | Unbounded queue absorbing backlog silently until OOM | Bound the queue via Little's Law; reject or apply backpressure when full |
| Login and health checks fail during a load spike alongside low-value background jobs | No priority tiers; a single rate limiter sheds indiscriminately | Tag requests by criticality; shed `SHEDDABLE` before `CRITICAL_PLUS` |
| Hedge requests double your LLM/API bill during a provider slowdown | Hedging every call unconditionally instead of only past the p95 threshold | Hedge only after the client-observed p95 delay, and only for idempotent calls |
| Same operation processed twice after a client-side retry | Idempotency check was read-then-write, not atomic | Atomic claim (`INSERT ... ON CONFLICT`, check rowcount) before doing the work |
| Refunds/notifications silently never happen for months | DLQ has no owner, no depth alert, no runbook | Alert on DLQ depth > 0 sustained past a threshold; assign an owner; document replay steps |
| Replay of a DLQ immediately refills the DLQ | Root cause (bug, schema mismatch) never fixed before replay | Sample and diagnose before bulk replay; fix forward first |
| A bad deploy fills the DLQ *and* takes the downstream dependency down at the same time | No circuit breaker on the consumer side; poison messages retried at full fleet volume before hitting `maxReceiveCount` | Circuit-break the consumer's downstream call independently of the queue-level retry count |

---

## Tradeoffs & when NOT to use it

- **Don't shed load that has legal or audit obligations to be accepted.** A payment capture or a compliance-relevant write should be queued (with backpressure) rather than rejected outright — shed the recommendation carousel, not the transaction ledger.
- **Don't hedge non-idempotent operations**, and don't hedge cheaply-computed-but-expensive-to-cancel operations (a write that starts a side effect the moment it's received) — you'll get two side effects, or you'll pay for two units of expensive compute (an LLM call, a GPU inference) when you only needed one.
- **Don't add idempotency-key infrastructure to operations that are naturally idempotent already** — a `PUT` that fully replaces a resource by ID doesn't need a dedup store; that's pure overhead for behavior you already have for free.
- **Don't build DLQ tooling for messages you don't need to recover.** If a failed message is a best-effort analytics ping with no downstream cost to losing it, drop it and increment a counter — a DLQ with no one ever intending to drain it is the anti-pattern this module names explicitly.
- **Don't apply backpressure by simply making the queue bigger.** A bigger unbounded-in-practice queue delays the OOM, it doesn't fix the fact that latency is growing unbounded and invisibly; you need a bound plus a signal to the producer, not more buffer.
- **Load shedding and backpressure are the wrong layer for long-running, multi-step work** — same caveat as the resilience catalogue: use a durable execution engine where a step's retry/resume is a property of persisted state, not an in-process admission decision made once at ingress.

---

## Interview questions

### Q1 — What's the difference between load shedding and a circuit breaker?
**Testing:** whether the candidate actually understands the boundary between the two modules, not just that both "reject requests."
**Answer:** A circuit breaker protects *you* from a dependency that is failing — it fails fast on outbound calls to a specific downstream. Load shedding protects you from *your own* overload — it's an admission-control decision at your own front door, independent of whether any downstream dependency is unhealthy. You can need load shedding with zero unhealthy dependencies (you're just receiving more traffic than you provisioned for), and you can have a perfectly healthy admission policy while a single downstream is on fire, which is what the breaker is for.
**Follow-up trap:** *"Could you build load shedding out of a circuit breaker pointed at yourself?"* — sort of, but it's the wrong abstraction: a breaker's failure-rate signal doesn't map cleanly onto "am I at capacity," and you lose the priority-tier decision entirely. Load shedding needs a load signal (queue depth, CPU, latency), not a failure-rate signal.

### Q2 — Design load shedding for a service seeing a 4x traffic spike. Walk through it.
**Testing:** whether they reach for priority tiers rather than a blanket rate limit.
**Answer:** Tag inbound requests by criticality at the edge (`CRITICAL_PLUS` for payment capture, down to `SHEDDABLE` for prefetch/analytics). Track a load signal — queue depth or in-flight count relative to provisioned capacity is cheaper and more honest than raw CPU%. As load crosses thresholds, shed the lowest tier first, and reject *before* deserializing the body or opening a DB connection — the rejection itself should cost close to nothing. Concretely: provisioned for 500 rps at 100ms p99, seeing 2,000 rps — admit 500 rps of `CRITICAL`+ traffic at full latency, shed the remaining 1,500 rps of lower tiers with an immediate 503 and `Retry-After`.
**Follow-up trap:** *"What if everything is CRITICAL_PLUS?"* — then you haven't actually done the tiering work, and shedding degenerates to random rejection. Push back in the interview: ask what's genuinely allowed to fail, because if the honest answer is "nothing," the fix isn't clever shedding logic, it's more capacity or a hard SLA renegotiation.

### Q3 — Why is an unbounded queue dangerous, precisely?
**Testing:** the "silent failure" insight, not just "it can run out of memory."
**Answer:** It's dangerous specifically because it fails invisibly before it fails visibly. Every enqueue succeeds, so no error rate rises. But if the consumer is even slightly slower than the producer for a sustained period, items pile up and end-to-end latency for anything already queued grows linearly with depth — a request that would have failed fast with a bounded queue instead sits for tens of seconds looking, from the caller's perspective, exactly like a slow but "working" system, until the process OOMs or a liveness probe kills it and every queued item is lost at once.
**Follow-up trap:** *"So bound the queue and reject when full — problem solved?"* — that fixes the invisibility, but now you need to decide what a full queue *means* upstream: reject at that point, or propagate backpressure so the producer slows down before it even tries to enqueue. Rejecting after enqueue-attempt-fails is strictly better than silent unbounded growth, but propagating the signal earlier (reactive-streams style demand, or gRPC flow control) avoids wasting the producer's own work building a request that gets rejected on arrival.

### Q4 — Derive the queue bound for a system doing 2,000 items/sec where anything older than 3 seconds is useless.
**Testing:** can they actually apply Little's Law rather than just cite it.
**Answer:** `L = λW = 2000 × 3 = 6,000`. Bound the queue at 6,000 items; anything beyond that represents work that will be stale by the time it's processed, so it should be rejected (or the producer backpressured) rather than queued.
**Follow-up trap:** *"What if λ is bursty, not steady?"* — Little's Law gives you the steady-state average; a bursty arrival pattern needs headroom above the naive bound (the same "provision 2x for burst" logic used for bulkhead sizing in the resilience catalogue), and you should validate under an actual load test rather than shipping the arithmetic as final.

### Q5 — Explain hedged requests and the exact tradeoff they make.
**Testing:** whether they can state the load cost as a number, not just "it's a bit more traffic."
**Answer:** Fire a duplicate request to a different replica after the first one has run past its p95 latency; take whichever comes back first, cancel the loser. Google's BigTable example: hedging after a 10ms delay cut p999 from 1,800ms to 74ms while adding only about 2% extra request volume, because 95%+ of requests never trigger the hedge. Only valid on idempotent, side-effect-free operations, since you may genuinely execute the call twice.
**Follow-up trap:** *"Why hedge at p95 and not, say, p50?"* — hedging at p50 means half of all requests trigger a second call, which is a huge load multiplier for almost no benefit (you're duplicating work for requests that were already fast). Hedging at p95 targets exactly the slow tail you're trying to fix and keeps the extra-load percentage small by construction.

### Q6 — A fan-out request touches 100 backend shards, each with a 1% chance of a slow response. What's the odds the aggregate request is slow?
**Testing:** the specific arithmetic from the Tail at Scale paper.
**Answer:** `1 - 0.99^100 ≈ 0.63`, roughly 63%. Independent small per-shard risks compound multiplicatively at fan-out, which is why average latency per shard is the wrong metric to optimize and tail latency (and mitigations like hedging) matters disproportionately as fan-out grows.
**Follow-up trap:** *"Does adding more shards make this worse or better?"* — worse, monotonically, for a fixed per-shard slow-probability — more independent chances to hit at least one straggler. This is a real argument for keeping fan-out width down, or for hedging specifically on the highest-fan-out paths first.

### Q7 — Design an idempotency-key scheme for a payment-capture endpoint.
**Testing:** the mechanical design, and whether they think about the race.
**Answer:** Client sends `Idempotency-Key: <uuid>` per logical charge attempt. Server does an atomic claim — `INSERT INTO idempotency_keys (key, status) VALUES (?, 'in_progress') ON CONFLICT DO NOTHING`, in the *same* transaction as (or immediately preceding) the charge logic — and checks the affected-row count. If it inserted, proceed and later update the row with `status='done'` and the response body to return on replay. If it didn't insert, someone else claimed it: look up the current status and either return the cached response (`done`) or a `409`/short-poll wait (`in_progress`). TTL on the row should exceed the client's maximum retry window — Stripe uses 24 hours.
**Follow-up trap:** *"What if the first request is still in flight when the retry arrives?"* — exactly the race this design has to handle: a naive existence check (`SELECT` then `INSERT` if missing) lets both requests see "no key" and both proceed, double-charging. The atomic `INSERT ... ON CONFLICT` with rowcount check is what prevents it — this is the single most common wrong answer to this question.

### Q8 — When does a message end up in a DLQ, and how do you replay it safely?
**Testing:** whether they know it's not "just requeue it."
**Answer:** After a consumer has failed to process it past a configured retry limit — SQS's `maxReceiveCount` defaults to 10. Safe replay: inspect a sample first to understand *why* it failed (bug vs. transient outage vs. schema mismatch); fix the root cause if it was a bug, or replay will refill the DLQ immediately; replay through the same idempotent consumer path at a controlled rate rather than dumping the entire backlog at once, since the original message may have partially succeeded before failing — which is exactly where idempotency keys matter a second time.
**Follow-up trap:** *"Your DLQ has 40,000 messages and nobody noticed for two months. What actually went wrong?"* — the technical failure is secondary; the real failure is organizational — no alert on DLQ depth, no owner, no runbook. A DLQ that exists but is never monitored gives false confidence that failures are handled when they're actually being silently filed away.

### Q9 — Your service's error rate is flat but users are complaining about slowness. Where do you look first?
**Testing:** whether "backpressure failure" is in their differential diagnosis at all.
**Answer:** An unbounded queue or buffer somewhere in the pipeline absorbing a producer/consumer speed mismatch without surfacing any error — check queue depth metrics specifically, not just error rate and CPU. If queue depth is climbing while error rate is flat, that's the signature: everything technically "succeeds" but takes longer and longer to do so.
**Follow-up trap:** *"You add a metric for queue depth and it confirms it. What's your immediate fix versus your real fix?"* — immediate: bound the queue so it starts rejecting/backpressuring now, converting invisible latency growth into visible, alertable rejection. Real fix: find why the consumer fell behind the producer (undersized pool, a slow downstream dependency, insufficient concurrency) — bounding the queue treats the symptom, not the capacity mismatch.

### Q10 — Would you ever hedge a write?
**Testing:** whether "idempotent" is a reflexive checkbox or an understood constraint.
**Answer:** Only if the write is genuinely idempotent *and* cheap enough to risk executing twice concurrently — e.g., a `PUT` that fully overwrites a resource by ID, protected additionally by an idempotency key so a duplicate execution collapses to the same stored outcome. A `POST /charge` without an idempotency key must never be hedged; you'd be racing two live charge attempts against each other.
**Follow-up trap:** *"Doesn't the idempotency key make it safe regardless?"* — the key prevents duplicate *side effects*, but the two hedge attempts are still racing to claim the same key, and if your claim path isn't atomic (see Q7) you've just built a faster way to trigger the exact race the key was supposed to prevent.

### Q11 — Design the resilience story for an LLM agent's tool calls, including cost.
**Testing:** whether they can apply this module to the domain their resume claims expertise in.
**Answer:** Load-shed low-priority background agent runs first under capacity pressure (batch summarization) before interactive, user-facing runs. Bound any internal work queue by Little's Law using the agent's own token/time budget as the tolerable-latency term. Hedge only read-only tool calls (a lookup, a retrieval query) past their p95, and treat the hedge's cost explicitly as 2x the token/dollar cost for the ~5% of calls that trigger it — that's a real budget line, not free capacity. Idempotency keys on any tool call with a side effect (sending an email, writing a record) so a retried agent step doesn't double-execute. DLQ failed tool-call steps into a queue a human or a repair-agent actually drains, with an alert on depth.
**Follow-up trap:** *"Which of those would you cut under a one-week deadline?"* — hedging, first — it's the one with a direct, ongoing dollar cost and the smallest blast radius if skipped (you just keep the existing tail latency). Idempotency keys on side-effecting tool calls and DLQ-with-an-owner are the ones that prevent an actual incident (double-sent emails, silently dropped agent failures) and should ship first.

### Q12 — Rank load shedding, backpressure, hedging, idempotency keys, and DLQs by how often their absence causes a real production incident.
**Testing:** synthesis — can they weigh the five against each other rather than treat them as an unordered list.
**Answer:** 1) **Missing idempotency keys on retried writes** — directly causes data corruption (double charges, duplicate orders), the most expensive class of bug in the set. 2) **Missing load shedding** — an overload event turns into a total outage instead of a partial, prioritized degradation. 3) **Missing backpressure (unbounded queues)** — turns overload into a delayed, more dramatic outage (OOM) instead of an immediate, contained one. 4) **A DLQ with no owner** — doesn't cause an outage, but causes a slow-burn correctness failure (silently lost work) that surfaces as a customer complaint months later. 5) **Missing hedging** — the least severe; its absence just means your tail latency is worse than it could be, which is a UX cost, not a correctness or availability one.
**Follow-up trap:** *"Isn't a full outage worse than data corruption?"* — arguable, and worth saying so out loud: an outage is visible and self-limiting (it ends when you fix it), while silent double-charges or duplicate orders are invisible until a customer or auditor finds them, and by then the damage (refunds, trust, sometimes regulatory exposure) is harder to bound. Both orderings are defensible; the senior signal is stating the axis you're ranking on rather than asserting one true order.

---

## Red flags that fail you

- Describing load shedding as "just a rate limiter" with no mention of priority tiers.
- Not knowing that an unbounded queue fails silently, and describing "the queue filled up" as the failure rather than "nothing signaled it was filling up."
- Suggesting hedging for a non-idempotent write.
- Treating idempotency keys as solved by a plain existence check instead of an atomic claim.
- Saying "just requeue it" for DLQ replay with no mention of diagnosing root cause first.
- Not being able to state hedging's load cost as a number.
- Assuming a DLQ's existence means failures are handled, with no mention of alerting or ownership.

---

## Cheat card

```
LOAD SHEDDING   admission control BEFORE real work starts (before deserialize/DB open)
                priority tiers: CRITICAL_PLUS > CRITICAL > SHEDDABLE_PLUS > SHEDDABLE
                shed lowest tier first; reject cost ~1ms vs full request cost if collapsed late
                500rps@100ms p99 provisioned, 2000rps spike -> shed 1500, keep 500 healthy

BACKPRESSURE    protocol signal (consumer tells producer to slow), not just "a queue"
                reactive streams: request(n) demand pull
                gRPC/HTTP2: flow-control window, 65536 bytes default, WINDOW_UPDATE
                bound queue: L = λW (Little's Law) — 1000/s x 5s tolerable = 5000 cap
                unbounded queue failure: latency grows, error rate FLAT, then OOM/restart

HEDGED REQUESTS fire duplicate after p95 delay; take first, cancel loser
                only idempotent, cancellable ops
                BigTable example: hedge @10ms delay -> p999 1800ms -> 74ms, +~2% load
                general rule: hedge at p95 costs ~5% extra load
                fan-out risk: 100 shards x 1% slow-each -> 63% chance of >=1 straggler

IDEMPOTENCY KEY client UUID per logical op, header e.g. Idempotency-Key
                atomic claim: INSERT...ON CONFLICT DO NOTHING, check rowcount
                NEVER read-then-write (races)
                TTL > max retry window (Stripe: 24h v1, 30d v2)
                race: 2 concurrent retries both see "no key" -> both proceed if not atomic

DLQ             SQS maxReceiveCount default 10, max 1000
                replay: sample+diagnose -> fix root cause -> controlled-rate replay
                                        -> through idempotent consumer path
                DLQ with no owner/alert = false confidence; worse than no DLQ
                fleet-wide poison-message spike still needs a circuit breaker on consumer

RANKING (absence -> worst incident): idempotency > shedding > backpressure > DLQ-no-owner > hedging
```

## Sources

- [The Tail at Scale — Communications of the ACM (Dean & Barroso, 2013)](https://cacm.acm.org/research/the-tail-at-scale/) — accessed 2026-08-01
- [The tail at scale — original PDF (Barroso)](https://www.barroso.org/publications/TheTailAtScale.pdf) — accessed 2026-08-01
- [Designing robust and predictable APIs with idempotency — Stripe](https://stripe.com/blog/idempotency) — accessed 2026-08-01
- [Advanced error handling — Stripe Documentation](https://docs.stripe.com/error-low-level) — accessed 2026-08-01
- [Using dead-letter queues in Amazon SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html) — accessed 2026-08-01
- [Understand the Amazon SQS dead-letter queue — AWS re:Post](https://www.repost.aws/knowledge-center/sqs-dead-letter-queue) — accessed 2026-08-01
- [Backpressure & queue design best practices — Sachith Dassanayake](https://www.sachith.co.uk/backpressure-queue-design-best-practices-in-2025-practical-guide-jul-21-2026/) — accessed 2026-08-01
- [Pattern: Backpressure / Flow Control — Battle-Tested Patterns](https://totoro-jam.github.io/battle-tested-patterns/patterns/backpressure/) — accessed 2026-08-01
- [The Thundering Herd Problem in Agentic AI — CockroachDB](https://www.cockroachlabs.com/blog/agentic-ai-thundering-herd-problem/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
