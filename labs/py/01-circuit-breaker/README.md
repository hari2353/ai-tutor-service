# Lab 01: Resilience Primitives From Scratch

**Track:** T21 Architecture & Design Principles · **Time:** 2h · **XP:** 50
**Module:** `T21-resilience-catalogue`

**You will build:** a composable `timeout → retry(jitter) → circuit breaker → bulkhead` stack in pure Python, with a fake clock so the tests run in milliseconds.

**You will be able to answer:** *"Walk me through a circuit breaker implementation — and why does the retry go inside it?"*

## Setup

```bash
cd labs/py/01-circuit-breaker
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Clock`** — injectable time source. `SystemClock` and `FakeClock(t=0)` with `.advance(dt)`. Nothing else may call `time.monotonic()` directly. *(Tests that sleep are broken tests.)*
2. **`Timeout`** — wrap a callable; raise `TimeoutExceeded` if it exceeds the budget. Support **deadline propagation**: `remaining()` returns the budget left, and a nested call gets `min(remaining, its_own_max)`.
3. **`retry(fn, attempts, backoff)`** — retry only on a configurable retryable-exception set. Implement `full_jitter` and `decorrelated_jitter`. Sleeps go through the clock.
4. **`CircuitBreaker`** — three states. Honour `failure_rate_threshold`, `sliding_window`, `min_calls`, `open_duration`, `half_open_probes`. Also implement `slow_call_rate_threshold` + `slow_call_duration`.
5. **`Bulkhead`** — semaphore-based concurrency cap. Reject immediately with `BulkheadFull` when saturated (do not queue).
6. **`resilient(...)`** — compose them in the correct nesting order, with an optional `fallback`.
7. **Metrics** — every primitive records counters (`calls`, `failures`, `rejections`, `state_transitions`) readable via `.stats()`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Retry budget** — cap retries at 10% of total calls across a shared budget object. *(Interview: "budget vs maxAttempts?")*
2. **Per-shard breakers** — a `BreakerRegistry` keyed by `(service, shard)` so one bad shard cannot cut off healthy ones.
3. **Adaptive bulkhead** — grow/shrink the limit from observed latency (a mini Netflix `concurrency-limits`).
4. **Async port** — rewrite on `asyncio` with `asyncio.Semaphore` and `wait_for`. Note which parts get simpler and which get harder.
