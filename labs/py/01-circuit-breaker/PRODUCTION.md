# Production notes — resilience primitives

## What you'd actually use

| Language | Retry | Breaker | Bulkhead | Timeout |
|---|---|---|---|---|
| Python | `tenacity` | `pybreaker` / `purgatory` | `asyncio.Semaphore` | `httpx` timeouts |
| Java | Resilience4j `Retry` | Resilience4j `CircuitBreaker` | Resilience4j `Bulkhead` (semaphore or threadpool) | `TimeLimiter` |
| Go | `cenkalti/backoff` | `sony/gobreaker` | `x/sync/semaphore` | `context.WithDeadline` |
| Mesh | Envoy retry policy + budget | Envoy outlier detection | connection-pool limits | route timeout |

**Do not use Hystrix.** Maintenance mode since 2018. Naming it as a current recommendation is a red flag in interviews.

## What the real ones add over yours

- **Sliding windows that are actually cheap** — ring buffers with O(1) update, not a `deque` you sum on every call. Yours is O(n) per call; at 50k rps that matters.
- **Lock-free state** — atomics and CAS rather than a mutex around every call. Your `threading.Lock` is a contention point.
- **Event streams** — Resilience4j publishes transition events you can subscribe to for alerting, rather than polling a gauge.
- **Exception classification** — `recordExceptions` / `ignoreExceptions` so business errors (a 404, a validation failure) never trip the breaker. Getting this wrong is the most common misconfiguration in the wild.
- **Bulkhead queueing policy** — `maxWaitDuration` for the cases where a short queue genuinely is better than rejection.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Breaker flaps every few seconds | `min_calls` too low / window too small | Raise both; use a time-based window |
| Lock contention shows up in profiles | Mutex on the hot path | Atomics, or shard the breaker state |
| Memory grows with endpoint count | One breaker per URL including path params | Key on the *route template*, not the URL |
| Breaker trips on 404s | No exception classification | Ignore business exceptions explicitly |
| Everything slow, breaker CLOSED | Only failure rate configured | Add slow-call rate |
| Bulkhead rejects under normal load | Sized by intuition | Little's Law: `concurrency = throughput × latency`, ×2 |

## Cost & latency

The primitives themselves are ~microseconds. What costs is what they prevent: a single 30s hung call holding a thread that could have served ~600 requests at 50ms. That is the actual ROI argument, and it is the one to make in a design review.

## The 3 questions an interviewer asks after you describe this

1. *"Your breaker uses a lock. What happens at 50k rps, and how would you fix it?"* — contention; move to atomics/CAS, or shard state per-core and aggregate.
2. *"How do you test the half-open path without sleeping?"* — inject the clock. That is why `Clock` is requirement #1.
3. *"You have 200 endpoints. One breaker each, or one shared?"* — per (service, route-template). Too coarse cuts off healthy routes; too fine and no breaker reaches `min_calls`. Memory is bounded by keying on templates, not URLs.
