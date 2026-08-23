# Lab 01 (Go): Circuit Breaker From Scratch

**Track:** T21 Architecture & Design Principles · **Time:** 2h · **XP:** 50
**Module:** `T21-resilience-catalogue`

**You will build:** deadline propagation, jittered retry, a three-state circuit
breaker with slow-call detection, a rejecting bulkhead, and their composition —
in idiomatic Go (mutexes, `select`/`default` semaphores, generics-free API),
with an injectable clock so the tests run in milliseconds.

**You will be able to answer:** *"Walk me through a circuit breaker implementation — and why does the retry go inside it?"*

## Setup

```bash
cd labs/go/01-circuit-breaker
go version          # 1.24+ — nothing else to install
```

## How starter/solution selection works

- `starter.go` carries `//go:build !solution` — the broken implementation.
- `solution.go` carries `//go:build solution` — the reference.
- The test file is tag-neutral; both builds compile it.

```bash
go test ./...                    # against starter/ → FAILS. Make them pass.
go test -tags solution ./...     # reference must pass
```

## The spec

1. **`Clock` / `FakeClock`** — injectable time. Nothing may call `time.Now()`
   or `time.Sleep()` directly except through the clock. `FakeClock.Sleep`
   records the duration instead of blocking. *(Tests that sleep are broken tests.)*
2. **`Deadline`** — `After(d, clock)`, `Remaining()` clamped at 0, `Expired()`,
   and `BudgetFor(max)`: a nested step gets `min(max, remaining)`; an expired
   deadline returns `ErrTimeout`. This is deadline propagation.
3. **`FullJitter(attempt, base, cap, rng)`** — uniform in `[0, min(cap, base·2^attempt))`.
   **`DecorrelatedJitter(prev, base, cap, rng)`** — uniform in `[base, min(cap, prev·3)]`.
4. **`Retry.Call(fn)`** — up to `Attempts`, sleeping via the clock with full
   jitter between tries (never after the last). Only errors accepted by
   `RetryOn` are retried; stats record calls + exhausted.
5. **`CircuitBreaker.Call(fn)`** — three states over a sliding window of the
   last `SlidingWindow` outcomes. Honours `FailureRateThreshold`, `MinCalls`
   (no evaluation below it), `OpenDuration` (lazy OPEN→HALF_OPEN on the next
   observation after it elapses), `HalfOpenProbes` (N clean probes close; any
   probe failure reopens immediately), `SlowCallRateThreshold` +
   `SlowCallDuration` (a dependency answering 200s in 5s still kills you),
   and `Ignore` (404s are business outcomes, not faults). OPEN rejects with
   `ErrBreakerOpen` WITHOUT invoking fn.
6. **`Bulkhead.Call(fn)`** — semaphore cap; saturated → immediate
   `ErrBulkheadFull`, never queues. The slot is released even when fn panics.
7. **`Resilient(fn, Opts)`** — compose **bulkhead → breaker → retry → fallback,
   outside-in**. THE invariant (see `TestRetryGroupCountsAsOneBreakerOutcome`):
   one logical call records ONE breaker outcome no matter how many retries ran
   inside — otherwise the breaker trips N× faster than reality.
8. **Metrics** — every primitive exposes `Stats{Calls, Failures, Rejections,
   Exhausted, MaxConcurrent, Transitions}`.

## Run the tests

```bash
go test ./... -v                 # starter → FAILS. Make them pass.
go test -tags solution ./...     # reference must pass
go vet ./... && gofmt -l .       # stay clean
```

## Stretch goals

1. **Per-shard breakers** — a `Registry` keyed by `(service, shard)` so one bad
   shard cannot cut off healthy ones. *(Interview: "how do you stop one bad
   backend from tripping every caller?")*
2. **Time-based sliding window** — replace the call-count window with
   per-second buckets like sentinel/resilience4j metrics. What breaks under
   bursty-but-low-volume traffic either way?
3. **Retry budget** — cap retries at 10% of total calls across a shared budget
   object instead of fixed maxAttempts. *(Interview: "budget vs maxAttempts?")*
4. **Context everywhere** — take `context.Context` as the first argument of
   every Call and derive child deadlines from `Deadline`. Which parts get
   simpler than manual BudgetFor?
