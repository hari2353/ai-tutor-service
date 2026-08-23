# Resilience Catalogue: Timeout, Retry+Jitter, Circuit Breaker, Bulkhead

> Sprint weekend 1 · source: `curriculum/21-architecture-principles/06-resilience-catalogue.md`

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
