# Production notes -- rate limiters

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Token bucket state | in-process float, one bucket per limiter instance | Redis (`INCRBY`/Lua script for atomicity), or a sidecar like Envoy's rate limit service |
| Sliding window | in-process two-counter approximation | same algorithm, but the counters live in Redis with `EXPIRE`, or a proper sliding-log if you need exactness over approximation |
| Distributed sharing | one Python object referenced by multiple `Node` wrappers in the same process | a genuinely shared external store (Redis, DynamoDB with conditional writes, or a dedicated rate-limit service) reachable by every real node/process/pod |
| Fair queueing | in-memory round-robin over a dict | a real scheduler (weighted fair queueing in a proxy/gateway, or Kubernetes-style resource quotas) with persistence across requests, not just one batch |
| Clock | injectable, deterministic for tests | real wall-clock (`time.monotonic()`) in production, but the injectable-clock *pattern* is exactly how you'd unit test the real thing without `sleep()`-based flaky tests |

## What the real ones add over yours

- **Atomicity across concurrent requests, not just correctness on paper.** This
  lab's `TokenBucket._refill()` + `try_acquire()` is two operations with no lock;
  in a single-threaded test harness that's fine, but two real concurrent requests
  hitting the same bucket without a lock (or without an atomic Redis Lua script)
  can both read "1 token available" and both decrement, over-admitting by exactly
  the race window's width. Production token buckets are either single-threaded by
  design (one goroutine/actor owns the bucket) or use an atomic primitive
  (`INCR`+`Lua`, compare-and-swap) for the check-then-decrement.
- **A real shared store, not a shared Python object.** `Node` in this lab shares
  one in-process `TokenBucket` instance to make the "aggregate limit across
  nodes" property testable without infrastructure. Production sharing means every
  actual process/pod/instance reads and writes the same external counter (Redis
  key, DynamoDB row) over the network, which introduces its own failure modes:
  network partition between a node and the store, store latency adding overhead
  to every single request, and the store itself becoming a single point of
  failure or a hot key under high QPS.
- **Clock skew across nodes.** This lab's FakeClock is shared, so all "nodes" see
  identical time. Real distributed nodes have clocks that drift by milliseconds
  to seconds; a sliding-window or fixed-window limiter that relies on wall-clock
  window boundaries needs those boundaries computed consistently (e.g., always
  against the STORE's clock, like Redis's `TIME` command, never each node's local
  clock) or windows disagree across nodes and the limit becomes fuzzy.
- **Backoff signaling, not just rejection.** This lab's limiters return a bare
  `True`/`False`. Production rate limiting returns a `429` with a `Retry-After`
  header (or gRPC's equivalent status + metadata) so well-behaved clients know
  when to retry instead of hammering immediately and making the overload worse.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Two concurrent requests both get admitted when only one token was left | Non-atomic check-then-decrement under real concurrency | Lock the critical section, or push the check+decrement into a single atomic store operation (Redis Lua script, DB conditional update) |
| A rate limiter "sometimes" allows a burst way over the configured limit | Per-node/per-instance buckets instead of a shared counter (the exact bug `test_naive_per_node_buckets_over_admit_by_node_count` demonstrates) | Share the counter across every instance that enforces the limit; if you can't (e.g., no shared store available), size each node's local limit as `global_limit / node_count` as a degraded fallback |
| Rate limit store becomes the bottleneck / single point of failure | Every request round-trips to the shared store before proceeding | Cache a short-lived local budget per node (sub-second lease from the shared store) to absorb most checks locally, reconciling periodically |
| A "fair" limiter still lets one tenant dominate under sustained (not just batch) load | Round-robin fairness computed per-batch, but batches are processed independently with no memory across batches | Track per-client debt/credit across time (e.g., a fair-share token bucket per client, refilled from a shared pool), not just fairness within one snapshot |
| Sliding window counter estimate is "wrong" right after a traffic pattern change | The algorithm is an APPROXIMATION (assumes uniform request distribution within the previous window) -- it can under- or over-estimate for bursty, non-uniform traffic | Accept the approximation error as a known tradeoff (it's still far better than fixed-window), or use a sliding LOG (store every timestamp) if exactness matters more than memory |
| Clients keep retrying immediately after a 429 and make the overload worse | No `Retry-After` or backoff hint returned | Always return a concrete retry hint, and expect (or require) clients to implement exponential backoff with jitter on top of it |

## Cost & latency

An in-process token bucket check is sub-microsecond -- free. The moment the
counter has to live in a shared store to work across multiple nodes, every
`try_acquire` call pays a network round trip (typically 0.5-2ms to a same-region
Redis), which is real added latency on every single request if it's not batched
or locally cached. This is why production rate limiters almost universally add a
local, short-lived budget cache (a node holds a small lease of tokens locally,
refreshed from the shared store every N milliseconds or N requests) rather than
hitting the shared store on every request -- trading a small amount of burst
imprecision across nodes for a large latency win.

## The 3 questions an interviewer asks after you describe this

1. *"Your token bucket has a burst of `capacity` and a sustained rate of
   `refill_rate`. If two requests race on the same bucket, could you ever admit
   one more than the bucket had?"* -- yes, if `_refill()` and the decrement in
   `try_acquire()` aren't atomic under real concurrency; this lab's version is
   safe only because tests run single-threaded against a FakeClock. Say this
   before they ask it.
2. *"Why not just use a fixed window -- it's simpler?"* -- because it allows
   exactly 2x the stated limit through in a burst spanning any window boundary,
   which is not a corner case, it's the predictable behavior of any client that
   naturally batches or retries near a round-number time boundary.
3. *"Your fair queueing test processes one batch. What happens over many batches
   if client A always shows up with more pending requests than B and C?"* --
   per-batch round-robin fairness resets every batch; it does NOT track
   cumulative share over time, so a client that's consistently noisier gets
   consistently equal treatment per-batch but no memory of having "used more" in
   aggregate -- true long-run fairness needs a credit/debt system across batches,
   not just fairness within one.
