# Resilience Catalogue: Timeout, Retry+Jitter, Circuit Breaker, Bulkhead

> **Track:** T21 Architecture & Design Principles · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T21-resilience-catalogue` · **Tags:** resilience, critical
> **Lab:** `labs/py/01-circuit-breaker/` · `labs/go/01-circuit-breaker/`

## The 30-second version

Four patterns compose into one defence, and the order matters: **timeout** bounds how long a single call can hurt you, **retry with exponential backoff and jitter** recovers from transient faults without synchronising your fleet into a thundering herd, **circuit breaker** stops you from retrying a service that is genuinely down, and **bulkhead** confines the damage so one sick dependency cannot consume every thread and take the whole process with it. Retry without a timeout is unbounded latency. Retry without a circuit breaker amplifies an outage — if every client retries three times, a struggling service receives 4× its normal load exactly when it can least handle it. And none of it is safe unless the downstream operation is idempotent.

## Why this gets asked

Because almost everyone can name "circuit breaker" and almost nobody can explain **how it interacts with retry**. The interviewer has lived through a retry storm: a downstream service degrades, every caller retries, load quadruples, the service dies completely, and the retries keep the it down through recovery. They want to hear you reason about *amplification*, not recite a pattern list. At staff and principal level they will also probe the failure mode of the safety mechanism itself — what happens when the circuit breaker is wrong.

## Lineage: past → present → future

**What came before.** Early distributed systems treated remote calls as if they were local ones — CORBA, RMI, and early SOAP all worked hard to make the network invisible. Peter Deutsch's *Fallacies of Distributed Computing* (1994) is a list of the assumptions that made this fail. The industry's first real answer was Michael Nygard's *Release It!* (2007), which named the stability patterns after watching production systems die in ways nobody had vocabulary for. Netflix then productised them in **Hystrix** (2012), which is where most engineers first met the circuit breaker; its command-object model, with a thread pool per dependency, made bulkheading the default rather than an afterthought.

**Where it stands now.** Hystrix went into maintenance mode in 2018, and the centre of gravity split in two. In-process, **Resilience4j** replaced it with a lighter functional design and — importantly — added slow-call detection, since the industry had learned that *slow success* kills services just as reliably as failure. Simultaneously, service meshes (Envoy, Istio, Linkerd) moved outlier detection, retry budgets, and connection-pool limits out of application code entirely, giving uniform behaviour across languages with no redeploy. The genuine current consensus is that these are complementary, not competing: the mesh handles transport-level defaults, in-process handles anything requiring semantics the mesh cannot see — whether an operation is idempotent, what a meaningful fallback is, per-tenant policy. The live disagreement is about **retry budgets**: Envoy, gRPC, and Finagle implement fleet-level budgets, but most application code still ships naive `maxAttempts`, and the gap between what the literature recommends and what is actually deployed remains wide.

**Where it's heading.** Three directions, with varying confidence. First, **adaptive limits** — static bulkhead sizing is being replaced by controllers that infer concurrency from observed latency (Netflix's `concurrency-limits`, Envoy's adaptive limiter, TCP-Vegas-style algorithms); this is real and shipping. Second, **durable execution** — Temporal, Restate, and LangGraph's checkpointers reframe retry and recovery as properties of persisted state rather than in-process wrappers, which is a strictly better model for long-running and multi-step work, and it is where agent systems are converging. Third, and more speculatively, **agent-specific resilience**: the primitives here were designed for calls that are fast, cheap, and deterministic, and none of those hold for an LLM tool call that costs money, takes seconds, and may fail semantically rather than mechanically. Expect budget-aware and cost-aware variants of every pattern in this catalogue. Treat that last one as a direction of travel, not settled practice.

---

## Mental model

Think of one outbound call passing through four gates, outermost first:

```
                    ┌──────────────────────────────────────────────┐
  request  ────────▶│ BULKHEAD    limit concurrent calls to this   │
                    │             dependency (semaphore / pool)    │
                    │  reject immediately if full ──────────────┐  │
                    │  ┌────────────────────────────────────┐   │  │
                    │  │ CIRCUIT BREAKER   is it worth      │   │  │
                    │  │   trying at all right now?         │   │  │
                    │  │  open → fail fast ──────────────┐  │   │  │
                    │  │  ┌──────────────────────────┐   │  │   │  │
                    │  │  │ RETRY   attempt N times  │   │  │   │  │
                    │  │  │  with backoff + jitter   │   │  │   │  │
                    │  │  │  ┌────────────────────┐  │   │  │   │  │
                    │  │  │  │ TIMEOUT  bound one │  │   │  │   │  │
                    │  │  │  │ attempt            │──┼───┼──┼───┼──┼──▶ dependency
                    │  │  │  └────────────────────┘  │   │  │   │  │
                    │  │  └──────────────────────────┘   │  │   │  │
                    │  └────────────────────────────────────┘   │  │
                    └──────────────────────────────────────────────┘
                                      │  │  │
                                      ▼  ▼  ▼
                                    FALLBACK (cached / degraded / error)
```

**Why this nesting.** The timeout must be *inside* the retry, because you retry a timed-out attempt. The retry must be *inside* the circuit breaker, because the breaker should see the outcome of the whole retry group as one decision — otherwise a single logical failure records three failures and trips the breaker too eagerly. The bulkhead is outermost because it is about protecting *your* process, not the dependency, and it must reject before you spend a thread on any of the rest.

> This nesting order is a favourite follow-up. Resilience4j's documented default order is Bulkhead → TimeLimiter → RateLimiter → CircuitBreaker → Retry, which places retry innermost; that is a defensible alternative, and the tradeoff is exactly what the interviewer wants you to discuss. Know that both orderings exist and why.

---

## How it actually works

### 1. Timeout — the one that is always missing

Every remote call has a timeout. If you did not set one, you inherited a library default, and that default is usually far too long or infinite.

Two timeouts, not one:

- **Connect timeout** — how long to establish the TCP/TLS connection. Short: 1–3s. A slow connect means the host is unreachable or saturated.
- **Read/request timeout** — how long to wait for the response. Derive it from the downstream's p99, not from a guess: `timeout ≈ p99 × 1.5`, then verify against your own SLO.

**The budget rule.** Timeouts must shrink as you go deeper. If the user-facing SLO is 3s and A calls B calls C, then C's timeout must be small enough that B still has time to fall back. Pass a **deadline** (absolute time), not a duration — Go's `context.WithDeadline` and gRPC deadlines do this natively.

```python
# Bad: fixed timeout at every layer — inner call can consume the entire budget
resp = httpx.get(url, timeout=3.0)

# Good: deadline propagation — each layer gets what's actually left
remaining = deadline - time.monotonic()
if remaining <= 0.05:
    raise DeadlineExceeded("no budget left; failing fast")
resp = httpx.get(url, timeout=min(remaining, PER_CALL_MAX))
```

**The subtle failure:** a timeout on the client does *not* cancel the work on the server. The server keeps computing, holding a DB connection, writing a row. Under a retry storm you can have three servers doing the same expensive work for a client that stopped listening. This is why cancellation propagation (gRPC cancellation, `context`, `asyncio` task cancellation) matters, and why timed-out writes need idempotency.

### 2. Retry — the pattern most likely to hurt you

Retry is only safe under three conditions, all of which are interview material:

1. **The operation is idempotent** (or you carry an idempotency key). Retrying `POST /charge` without one charges twice.
2. **The error is retryable.** Retrying a 400 or a 403 is pure waste. Retry on: connection errors, timeouts, 429, 502/503/504. Never on 400/401/403/404/422.
3. **There is a budget.** Unbounded retries turn a blip into an outage.

**Backoff and jitter.** Plain exponential backoff synchronises clients: everyone fails at T, everyone retries at T+1s, T+2s, T+4s — the herd stays a herd. Jitter breaks the synchronisation.

```python
import random

def full_jitter(attempt: int, base: float = 0.1, cap: float = 10.0) -> float:
    """AWS 'full jitter'. Best general choice: lowest contention, good spread."""
    return random.uniform(0, min(cap, base * (2 ** attempt)))

def decorrelated_jitter(prev: float, base: float = 0.1, cap: float = 10.0) -> float:
    """Slightly better completion time under high contention."""
    return min(cap, random.uniform(base, prev * 3))
```

| Strategy | Sleep for attempt *n* | Behaviour |
|---|---|---|
| Fixed | `base` | Synchronises the herd. Avoid. |
| Exponential | `base · 2ⁿ` | Still synchronised. Avoid alone. |
| Equal jitter | `b/2 + rand(0, b/2)` where `b = base·2ⁿ` | Decent |
| **Full jitter** | `rand(0, base · 2ⁿ)` | **Default choice** |
| Decorrelated | `min(cap, rand(base, prev·3))` | Best under heavy contention |

**Retry budgets beat retry counts.** "3 attempts per request" is a per-request view. What actually protects the downstream is a *fleet-level* cap: allow retries only while they are under ~10% of total requests. Envoy, gRPC, and Finagle all implement this. Saying "I'd use a retry budget, not just maxAttempts" is a strong senior signal.

**Amplification math — know this cold.** With 3 attempts and a downstream failing 100% of calls, offered load is 3× baseline. Add a second layer of retrying services and it is 9×. This is why retry is the pattern most likely to *cause* the outage it was meant to survive, and why it must sit inside a circuit breaker.

### 3. Circuit breaker — three states

```
                 failure rate ≥ threshold
                 (over a sliding window)
        ┌────────┐ ──────────────────────▶ ┌────────┐
        │ CLOSED │                          │  OPEN  │
        │ (pass) │ ◀──────────────────────  │ (fail  │
        └────────┘   probe succeeded         │  fast) │
             ▲                               └────────┘
             │                                    │ after waitDuration
             │  probe failed                      ▼
             │                              ┌───────────┐
             └───────────────────────────── │ HALF-OPEN │
                                            │ allow N   │
                                            │ probes    │
                                            └───────────┘
```

- **CLOSED** — calls pass. Outcomes are recorded in a sliding window (count-based or time-based).
- **OPEN** — calls fail immediately with `CircuitBreakerOpen`. No thread is spent, no timeout is waited on. This is the entire point: **fail fast so your own resources stay free**.
- **HALF-OPEN** — after `waitDurationInOpenState`, allow a small number of probe calls. All succeed → CLOSED. Any fail → back to OPEN (often with a longer wait).

**Configuration that matters:**

| Knob | Typical | Why |
|---|---|---|
| `failureRateThreshold` | 50% | Rate, not count — a count trips on volume |
| `slidingWindowSize` | 100 calls or 60s | Too small = flappy; too large = slow to trip |
| `minimumNumberOfCalls` | 20 | **Critical.** Without it, 1 failure out of 1 call = 100% → trips instantly at low traffic |
| `waitDurationInOpenState` | 30s | Long enough for a restart or a GC pause to clear |
| `permittedCallsInHalfOpenState` | 5–10 | Too few = noisy decisions; too many = you re-hammer a recovering service |
| `slowCallRateThreshold` | 50% over 2s | **Underused.** A service that is slow but not failing will still exhaust your threads |

Note that last one: a dependency returning 200s in 30 seconds never trips a failure-rate breaker, yet it is the more common production killer. Configure slow-call thresholds.

**Per what?** One breaker per (service, endpoint) — sometimes per (service, endpoint, shard). A single global breaker means one bad endpoint blocks healthy ones. Too fine a granularity and no breaker ever reaches `minimumNumberOfCalls`.

**The failure mode of the breaker itself:** it can be wrong. A breaker on a partially-degraded dependency (one bad shard out of twenty) will trip and cut off the nineteen healthy ones. Mitigation: per-shard breakers, or trip only on errors that indicate total unavailability.

### 4. Bulkhead — isolating the blast radius

Named after ship compartments: flood one, the ship floats.

Without a bulkhead, one slow dependency consumes every thread in a shared pool and the process stops serving *everything*, including endpoints that never touch that dependency. The failure spreads laterally.

Two implementations:

| Type | Mechanism | Cost | Use when |
|---|---|---|---|
| **Semaphore** | Counter caps concurrent calls; caller's own thread does the work | Cheap | Async/non-blocking code, high call volume |
| **Thread-pool** | Dedicated pool per dependency; caller hands off | Context-switch overhead, but gives true isolation *and* a place to enforce timeouts on blocking clients | Blocking clients you cannot interrupt |

Sizing via **Little's Law**: `concurrency = throughput × latency`. A dependency at 100 rps with 50ms p99 needs `100 × 0.05 = 5` concurrent slots; provision ~2× for burst, so 10. Sizing pools by intuition is how you end up with 200 threads all blocked on one host.

In async Python the semaphore bulkhead is natural:

```python
class Bulkhead:
    def __init__(self, limit: int, queue_timeout: float = 0.0):
        self._sem = asyncio.Semaphore(limit)
        self._queue_timeout = queue_timeout

    async def __aenter__(self):
        try:
            # queue_timeout=0 → reject immediately when full (usually what you want:
            # queueing converts a capacity problem into a latency problem)
            await asyncio.wait_for(self._sem.acquire(), self._queue_timeout or 0.001)
        except asyncio.TimeoutError:
            raise BulkheadFull("dependency at capacity")
        return self

    async def __aexit__(self, *exc):
        self._sem.release()
```

### 5. Fallback — what you do when all of it fires

A rejection is only useful if you have something to return. In descending order of quality:

1. **Cached / stale data** — "prices as of 5 minutes ago". Usually the right answer.
2. **Degraded response** — drop the recommendations carousel, render the page.
3. **Default value** — empty list, neutral score.
4. **Queue for later** — accept the write, process asynchronously.
5. **Explicit error** — honest and fast beats a hung request. Return 503 with `Retry-After`.

Never let the fallback call another remote service without its own protection. That is how you get a cascading fallback failure.

---

## Build it from scratch

Minimal circuit breaker — this is the code the interviewer may ask you to write.

```python
import time, threading
from collections import deque
from enum import Enum

class State(Enum):
    CLOSED = "closed"; OPEN = "open"; HALF_OPEN = "half_open"

class CircuitBreakerOpen(Exception): ...

class CircuitBreaker:
    def __init__(self, failure_threshold=0.5, window=100, min_calls=20,
                 open_duration=30.0, half_open_probes=5):
        self.failure_threshold = failure_threshold
        self.min_calls = min_calls
        self.open_duration = open_duration
        self.half_open_probes = half_open_probes
        self._results: deque[bool] = deque(maxlen=window)   # True = failure
        self._state = State.CLOSED
        self._opened_at = 0.0
        self._probes_left = 0
        self._lock = threading.Lock()

    def _failure_rate(self) -> float:
        if len(self._results) < self.min_calls:
            return 0.0                      # not enough evidence to judge
        return sum(self._results) / len(self._results)

    def _allow(self) -> bool:
        with self._lock:
            if self._state is State.OPEN:
                if time.monotonic() - self._opened_at >= self.open_duration:
                    self._state = State.HALF_OPEN
                    self._probes_left = self.half_open_probes
                else:
                    return False
            if self._state is State.HALF_OPEN:
                if self._probes_left <= 0:
                    return False            # probes in flight; don't pile on
                self._probes_left -= 1
            return True

    def _record(self, failed: bool) -> None:
        with self._lock:
            if self._state is State.HALF_OPEN:
                if failed:
                    self._trip()
                else:
                    self._probes_left -= 1
                    if self._probes_left <= 0:
                        self._state = State.CLOSED
                        self._results.clear()
                return
            self._results.append(failed)
            if self._failure_rate() >= self.failure_threshold:
                self._trip()

    def _trip(self) -> None:
        self._state = State.OPEN
        self._opened_at = time.monotonic()
        self._results.clear()

    def call(self, fn, *a, **kw):
        if not self._allow():
            raise CircuitBreakerOpen(f"circuit open for {fn.__name__}")
        try:
            out = fn(*a, **kw)
        except Exception:
            self._record(True)
            raise
        self._record(False)
        return out
```

Three things this gets right that most whiteboard versions miss: `min_calls` prevents tripping on tiny samples, HALF_OPEN limits *concurrent* probes rather than just counting them, and the window clears on state change so stale results do not immediately re-trip.

Full version with timeout, retry, bulkhead, metrics, and tests: **`labs/py/01-circuit-breaker/`**.

---

## How it's done in production

**Java — Resilience4j** (the Hystrix successor; Hystrix has been in maintenance since 2018 and should not be your answer):

```java
CircuitBreakerConfig cfg = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)
    .slowCallRateThreshold(50)
    .slowCallDurationThreshold(Duration.ofSeconds(2))
    .slidingWindowType(SlidingWindowType.TIME_BASED)
    .slidingWindowSize(60)
    .minimumNumberOfCalls(20)
    .waitDurationInOpenState(Duration.ofSeconds(30))
    .permittedNumberOfCallsInHalfOpenState(5)
    .recordExceptions(IOException.class, TimeoutException.class)
    .ignoreExceptions(BusinessException.class)   // don't trip on 4xx-equivalents
    .build();
```

Decorator order is explicit and worth memorizing:
`Bulkhead → TimeLimiter → RateLimiter → CircuitBreaker → Retry`.

**Python** — `tenacity` for retry, `pybreaker` or `purgatory` for breakers, `httpx` for timeouts, `asyncio.Semaphore` for bulkheads. No single library covers all four; you compose them.

**Go** — `sony/gobreaker`, `cenkalti/backoff`, `golang.org/x/sync/semaphore`, and `context` for deadlines. Deadline propagation is idiomatic and free.

**Service mesh (Envoy/Istio)** — outlier detection, retry budgets, and connection-pool limits configured declaratively, outside your code. Advantages: uniform across languages, changeable without redeploy. Limits: the mesh cannot express business-level fallbacks or per-tenant policy, and it has no idea whether your operation is idempotent. **The senior answer is "both": mesh for the transport-level defaults, in-process for the semantics the mesh cannot see.**

**Observability — non-negotiable.** Every one of these patterns is invisible until instrumented. Emit: breaker state transitions (as events, not just gauges), rejection counts per pattern, retry attempt histograms, bulkhead queue depth and rejections, and the *reason* a request failed. A dashboard that cannot distinguish "downstream returned 500" from "our breaker was open" will cost you hours in an incident.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Latency spikes to exactly the timeout value | Timeout too generous; you are waiting on dead connections | Set from p99, add connect timeout |
| Downstream dies right as it starts recovering | Retry storm; no breaker or no budget | Circuit breaker + fleet-level retry budget |
| Breaker flaps open/closed every few seconds | `minimumNumberOfCalls` too low, or window too small | Raise both; consider time-based window |
| Whole service unresponsive, one dependency at fault | No bulkhead; shared thread pool exhausted | Per-dependency bulkhead sized by Little's Law |
| Duplicate charges/writes after a deploy | Retry on non-idempotent operation | Idempotency keys, dedup store |
| Breaker never trips but everything is slow | Only failure-rate configured, not slow-call rate | Add `slowCallRateThreshold` |
| Healthy shards cut off | Breaker granularity too coarse | Per-shard or per-endpoint breakers |

---

## Tradeoffs & when NOT to use it

- **Do not retry non-idempotent writes** without an idempotency key. This is the single most expensive mistake in the catalogue.
- **Do not put a circuit breaker on a dependency you cannot fall back from.** If the request is meaningless without it, the breaker converts a slow error into a fast error — occasionally worth it for resource protection, but be explicit that this is the goal.
- **Do not retry inside every layer.** Retries at A, B, and C multiply to 27 attempts. Retry at **one** layer, ideally the one closest to the failure that knows the operation is idempotent.
- **Bulkheads cost capacity.** Partitioning 200 threads into ten pools of 20 means you cannot burst to 100 on one dependency even when the rest are idle. Adaptive concurrency limits (Netflix's `concurrency-limits`, Envoy's adaptive limiter) address this.
- **Timeouts that are too aggressive cause the outage.** Set below the real p99 and you fail healthy requests, retry them, and manufacture the load spike you feared.
- **For long-running or multi-step work, this catalogue is the wrong layer.** Use a durable execution engine (Temporal, Step Functions, or LangGraph checkpointers for agents) where retry and recovery are properties of persisted state, not of an in-process wrapper.

---

## Interview questions

### Q1 — What is a circuit breaker and what are its states?
**Testing:** baseline. Everyone passes this; the score comes from the follow-ups.
**Answer:** A proxy around a remote call that tracks failure rate over a sliding window. CLOSED passes traffic; when the failure rate crosses a threshold over a minimum call count, it moves to OPEN and fails fast without spending a thread; after a wait duration it moves to HALF-OPEN and admits a few probes; probes succeed → CLOSED, any probe fails → OPEN again.
**Follow-up trap:** *"Why a failure rate and not a failure count?"* — a count trips on volume, so a high-traffic endpoint trips constantly while a low-traffic one never does. Rate normalises this, and `minimumNumberOfCalls` guards against a tiny sample producing a 100% rate.

### Q2 — How do retry and circuit breaker interact? Which wraps which?
**Testing:** the real question. This separates recall from understanding.
**Answer:** The circuit breaker wraps the retry group, so one logical failure records one breaker outcome rather than three. If retry were outside, a tripped breaker would be retried immediately — pointless — and if the breaker sat inside the retry loop, three attempts of one failed call would count as three failures and trip it three times too fast. Without a breaker at all, retry *amplifies*: 3 attempts against a fully-failing downstream is 3× offered load, and two layers of retrying services is 9×.
**Follow-up trap:** *"Resilience4j puts Retry outermost. Is it wrong?"* — no, it is a different tradeoff: retry-outermost lets you retry *after* a breaker rejection (useful when you have several instances and the retry can hit a different one, each with its own breaker). Say that the right order depends on whether retries can be routed elsewhere.

### Q3 — Your downstream degrades. Walk me through what happens with and without these patterns.
**Testing:** systems thinking under failure.
**Answer:** Without: calls hang until the default timeout (often 30s+), threads accumulate, the pool exhausts, unrelated endpoints start failing, health checks fail, your instance is removed from the LB, the remaining instances absorb its traffic and follow it down. With: timeout caps each attempt at ~1.5× p99, retry handles the transient portion with full jitter so clients do not synchronise, the breaker trips after a 50% failure rate over 20+ calls and fails fast, the bulkhead ensures only the slots allocated to that dependency are consumed, and the fallback serves stale cache. Users see degraded results on one feature instead of a total outage.
**Follow-up trap:** *"Which of the four would you add first if you could only have one?"* — **timeout.** Everything else assumes a bounded call. An unbounded call defeats retry (never returns to retry), defeats the breaker (never records an outcome), and defeats the bulkhead (occupies the slot forever).

### Q4 — Semaphore bulkhead vs thread-pool bulkhead?
**Answer:** Semaphore is a counter on concurrent calls executed on the caller's thread — cheap, no context switch, but it cannot interrupt a blocking call, so it relies on the client honouring timeouts. Thread-pool gives true isolation and lets you enforce a timeout on a blocking client you cannot otherwise interrupt, at the cost of context switching and the memory of the pool. In async code, use semaphores. With blocking JDBC drivers or legacy HTTP clients, use pools.
**Follow-up trap:** *"How do you size it?"* — Little's Law: `concurrency = throughput × latency`. 100 rps at 50ms p99 → 5, provision ~10 for burst. Then verify under load; do not ship the arithmetic as final.

### Q5 — Why jitter?
**Answer:** Without it, all clients that failed at time T retry at T+1, T+2, T+4 — the herd stays synchronised and each retry wave hits simultaneously, which is precisely when a recovering service is most fragile. Full jitter (`sleep = rand(0, base·2ⁿ)`) spreads the load; AWS's analysis showed it minimises both contention and total work versus plain exponential and equal jitter.
**Follow-up trap:** *"Does jitter alone fix retry storms?"* — no. It spreads them in time but does not reduce total offered load. You still need a breaker and a fleet-level retry budget.

### Q6 — Retry budget vs max attempts?
**Answer:** `maxAttempts` is per-request and says nothing about aggregate load; 10,000 clients each retrying 3× is still 3× on the downstream. A retry budget caps retries as a *fraction of total requests* across the fleet — typically 10–20%. Once the budget is exhausted, retries are dropped even if attempts remain. Envoy, gRPC, and Finagle implement this. It is the only mechanism that bounds amplification directly.
**Follow-up trap:** *"Who enforces the budget across 500 pods?"* — that's the hard part, and it's why this usually lives in the mesh or a shared sidecar rather than in each service. In-process budgets are per-instance, so 500 instances each staying under 10% can still triple aggregate load. Envoy tracks it at the cluster level; if you implement it yourself you need a shared counter and you've just built a distributed rate limiter.

### Q7 — How do you make a retried write safe?
**Answer:** Idempotency keys. Client generates a UUID per logical operation and sends it as a header; the server stores `(key → response)` in a dedup store (Redis with a TTL, or a unique constraint in the DB) and returns the stored response on a repeat. Must be atomic — `INSERT ... ON CONFLICT DO NOTHING` and check the affected-row count, not read-then-write. TTL must exceed your maximum retry window.
**Follow-up trap:** *"What if the first request is still in flight when the retry arrives?"* — that is the hard case. Either return 409 and let the client back off, or block on a lock keyed by the idempotency key with a short timeout. Naive read-then-write races and double-processes.

### Q8 — Where do these belong — application code, or the service mesh?
**Answer:** Both, at different levels. The mesh (Envoy outlier detection, retry budgets, connection-pool limits) gives uniform transport-level defaults across languages with no redeploy. But the mesh does not know whether an operation is idempotent, cannot express a business fallback ("serve the cached price"), and cannot do per-tenant policy. Transport defaults in the mesh; semantic protection in-process.
**Follow-up trap:** *"The mesh already retries and so does your code. What happens?"* — they multiply. Three mesh retries times three application retries is nine attempts for one logical call, and this is one of the most common real misconfigurations in service-mesh deployments. Pick one layer to retry at, and explicitly disable it at the other.

### Q9 — Your circuit breaker keeps flapping. Diagnose it.
**Answer:** Most likely `minimumNumberOfCalls` is too low or the sliding window is too small, so a handful of failures on a low-traffic endpoint produces a 100% failure rate. Or `waitDurationInOpenState` is too short and probes hit a service that has not finished restarting. Or `permittedNumberOfCallsInHalfOpenState` is 1, making the whole decision hinge on a single sample. Fix: raise the minimum, use a time-based window, lengthen the open duration, and consider exponential backoff *of the open duration* on repeated failed probes.
**Follow-up trap:** *"You raised the minimum and it still flaps. What else?"* — the breaker is probably too coarse and is aggregating a genuinely unhealthy endpoint with healthy ones, so the failure rate oscillates around the threshold. Split per route template. Also check whether your health-check traffic is being recorded in the window, which biases the rate in both directions.

### Q10 — A dependency returns 200s but takes 30 seconds. Does your breaker trip?
**Testing:** whether you know slow-call detection exists.
**Answer:** Not with failure-rate alone — every call succeeds. This is the more dangerous case, because slow success exhausts threads exactly like failure. Configure `slowCallRateThreshold` with `slowCallDurationThreshold` (e.g. trip if >50% of calls exceed 2s). And the timeout should have converted those into failures anyway — if a 30s call reached you, your timeout is missing or too generous.
**Follow-up trap:** *"What's the right slow-call threshold?"* — derive it from your own SLO, not the dependency's behaviour. If you owe the user 3 seconds and this call is one of three, anything past ~800ms is already too slow to be useful, so that's the threshold, not the dependency's p99. People set it from the downstream's latency and end up tolerating calls that have already blown their budget.

### Q11 — When would you deliberately NOT add a circuit breaker?
**Answer:** When there is no meaningful fallback and the dependency is on the critical path — the breaker converts a slow failure into a fast one without improving the user outcome. It may still be worth it purely to protect your own thread pool, but that should be a stated, deliberate choice rather than a reflex. Also skip it for single-instance internal calls where a mesh already handles outlier ejection, and for long-running workflows where a durable execution engine is the right abstraction.
**Follow-up trap:** *"So you'd let it hang?"* — no. Without a breaker you still need the timeout and the bulkhead; those protect *you*. The breaker specifically buys fail-fast behaviour, and without a fallback that's a faster error rather than a better outcome. Being explicit that you're protecting your own thread pool rather than improving the user experience is the senior framing.

### Q12 — Design the resilience strategy for an LLM-backed agent calling five tools.
**Testing:** whether you can transfer the catalogue to the domain you claim expertise in.
**Answer:** Per-tool bulkheads sized by expected concurrency, since one slow tool must not starve the others. Per-tool timeouts, but derived from the *agent's* total budget — an agent with a 60s ceiling and up to 10 steps cannot give any one tool 30s. Retry only on transient transport errors and 429, never on a tool returning a semantic error, because a tool saying "no results" retried three times just burns tokens and latency. Circuit breaker per tool with a fallback that returns a structured "tool unavailable" observation, so the model can route around it rather than the whole run failing. Above all of it, a token/cost budget and a step-count cap acting as the outermost bulkhead. And checkpoint state (LangGraph's PostgresSaver or equivalent) so a failure resumes rather than restarts — at ten steps with 85% per-step reliability, an un-checkpointed run completes only ~20% of the time, which no amount of retry tuning fixes.
**Follow-up trap:** *"Which of those would you cut if you had one week?"* — the step cap and the cost budget, because they're two lines each and they prevent the incident that ends careers. Per-tool breakers and bulkheads are more work and the blast radius without them is bounded by the step cap you already added. Sequencing by cost-to-implement against risk-prevented is the answer they want.

### Q13 — What does a timeout NOT protect you from?
**Answer:** Server-side work continuing after the client gives up. The timeout is a client-side decision; unless cancellation is propagated (gRPC cancellation, `context`, async task cancellation) the server keeps holding its DB connection and finishing the query. Under retries you get N servers doing duplicate work for a client that has stopped listening — which is both a capacity leak and, for writes, a correctness bug.
**Follow-up trap:** *"How do you actually propagate cancellation through three services?"* — gRPC does it natively via deadlines, which is a real argument for gRPC on internal hops. Over HTTP you get nothing for free: you pass a deadline header, each service enforces it, and each checks a cancellation token at await points. Most codebases claim propagation and don't have it, which you can verify by timing out a client and watching whether the downstream query still completes.

### Q14 — How do you test any of this?
**Answer:** Unit tests with a fake clock — never `sleep()` in tests — asserting state transitions at the boundaries: exactly at threshold, one below, and the half-open probe paths. Integration tests with a fault-injecting proxy (Toxiproxy) for latency, connection resets, and partial failure. Load tests that verify the bulkhead rejects rather than queues unboundedly. Then game days / chaos experiments in a real environment, because the interesting failures are the ones between components.
**Follow-up trap:** *"Your chaos experiment took down staging. Was that a success?"* — yes, if you learned something and had a rollback; no, if you had no hypothesis and no blast-radius limit. Chaos engineering without a stated hypothesis, a bounded scope, and an abort condition isn't an experiment, it's an outage you scheduled.

### Q15 — Rank the four by how often their absence causes a real incident.
**Answer:** 1) **Missing timeout** — the root of most cascading failures, and the easiest to overlook because a default always exists. 2) **Missing bulkhead** — turns one sick dependency into total unavailability. 3) **Retry without a breaker or budget** — turns a degradation into an outage. 4) **Missing circuit breaker alone** — bad, but with sound timeouts and bulkheads the blast radius is already contained. Note this ranking is the inverse of how often the patterns get discussed.

---

## Red flags that fail you

- Saying "add retries" without mentioning idempotency.
- Naming Hystrix as your current recommendation (maintenance mode since 2018).
- Describing a circuit breaker as having two states.
- Not knowing why `minimumNumberOfCalls` exists.
- Claiming the service mesh removes the need for in-process resilience.
- Treating "add a circuit breaker" as automatically correct, with no fallback story.
- Suggesting retry at every layer.
- Sizing a thread pool or bulkhead with no reference to throughput and latency.

---

## Cheat card

```
ORDER (outermost→innermost): Bulkhead → CircuitBreaker → Retry → Timeout
  Resilience4j documented order: Bulkhead → TimeLimiter → RateLimiter → CB → Retry

TIMEOUT     connect 1-3s · read ≈ p99 × 1.5 · propagate DEADLINES not durations
            budget must shrink with depth; timeout ≠ server-side cancellation

RETRY       only if idempotent + retryable error + budgeted
            retryable: conn error, timeout, 429, 502, 503, 504
            NOT retryable: 400, 401, 403, 404, 422
            full jitter: sleep = rand(0, base · 2^n)     ← default choice
            decorrelated: min(cap, rand(base, prev·3))   ← best under contention
            amplification: 3 attempts = 3× load; 2 layers = 9×
            fleet retry budget ~10% of total requests > per-request maxAttempts

BREAKER     CLOSED → OPEN → HALF_OPEN → CLOSED
            failureRateThreshold      50%
            slidingWindowSize         100 calls / 60s
            minimumNumberOfCalls      20        ← without it, 1/1 = 100% = instant trip
            waitDurationInOpenState   30s
            permittedCallsHalfOpen    5-10
            slowCallRateThreshold     50% over 2s   ← the one people forget
            one breaker per (service, endpoint)

BULKHEAD    semaphore = cheap, async, can't interrupt blocking calls
            thread-pool = true isolation + enforceable timeout, costs context switches
            size: Little's Law → concurrency = throughput × latency, then ×2 for burst
            reject immediately; queueing turns capacity problems into latency problems

FALLBACK    stale cache > degraded > default > queue-for-later > fast 503 + Retry-After

LIBS        Java resilience4j (not Hystrix) · Py tenacity+pybreaker+httpx
            Go gobreaker+backoff+x/sync/semaphore+context · Mesh: Envoy/Istio

FIRST PATTERN TO ADD IF YOU ONLY GET ONE: timeout
```

## Sources

- [Fault Tolerance Patterns: Circuit Breaker, Bulkhead, Retry — System Design Space](https://system-design.space/en/chapter/resilience-patterns/) — accessed 2026-07-26
- [Microservices Resilience Patterns — GeeksforGeeks](https://www.geeksforgeeks.org/system-design/microservices-resilience-patterns/) — accessed 2026-07-26
- [Error handling in distributed systems: a guide to resilience patterns — Temporal](https://temporal.io/blog/error-handling-in-distributed-systems) — accessed 2026-07-26
- [Circuit Breakers and Resilience Patterns — Imperialis Tech](https://imperialis.tech/en/blog/circuit-breakers-resilience-patterns-distributed-systems-2026) — accessed 2026-07-26
- [Resilient Microservices: A Systematic Review (arXiv 2512.16959)](https://arxiv.org/pdf/2512.16959) — accessed 2026-07-26
- [Design patterns for resilient microservices — DesignGurus](https://www.designgurus.io/answers/detail/what-are-design-patterns-for-resilient-microservices-circuit-breaker-bulkhead-retries) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
**Follow-up trap:** *"Why is that the inverse of how much they get discussed?"* — because circuit breakers are conceptually interesting and timeouts are boring. Interviews and blog posts optimise for interesting; production rewards boring. Being able to say that out loud, and that you'd add the timeout before the breaker, is a stronger signal than reciting the pattern catalogue.

