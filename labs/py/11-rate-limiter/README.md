# Lab 11: Rate Limiters From Scratch

**Track:** T01 Python & SWE Craft / T21 Architecture & Design Principles · **Time:** 3h · **XP:** 50
**Modules:** `T01-asyncio`, `T21-resilience-advanced`

**You will build:** a token bucket (exact burst-then-throttle behavior), a fixed-
window counter and the sliding-window counter that fixes its classic boundary bug,
a distributed-style limiter that shares one counter across multiple "nodes", and a
round-robin fair-queueing limiter -- all driven by an injectable clock, no
`time.sleep()` anywhere.

**You will be able to answer:** *"Implement a token bucket rate limiter. Then
explain the fixed-window counter bug and why your fix doesn't have it -- with
numbers, not a hand wave."*

## Setup

```bash
cd labs/py/11-rate-limiter
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`FakeClock`** -- `now()` returns the current fake time; `advance(seconds)`
   moves it forward without blocking. Every limiter below takes a `Clock` and
   never touches the real wall clock directly.
2. **`TokenBucket(capacity, refill_rate, clock, initial_tokens=None)`** -- starts
   full (or at `initial_tokens`), refills continuously at `refill_rate`
   tokens/second capped at `capacity`. `try_acquire(cost=1.0)` returns `True`/`False`
   and only spends tokens on success. A fresh bucket permits an immediate burst of
   up to `capacity` requests; after that, sustained throughput is exactly
   `refill_rate` requests/second.
3. **`FixedWindowCounter(limit, window_seconds, clock)`** -- the naive, buggy
   baseline included on purpose: resets its count to 0 the instant a new
   calendar-aligned window starts, so a client that saves up requests can push
   `limit` through right at the end of one window and `limit` more right at the
   start of the next -- 2x the limit in a near-instant span.
4. **`SlidingWindowCounter(limit, window_seconds, clock)`** -- the fix: blends the
   previous window's count into the current window's estimate, weighted by how
   much of the previous window is still inside the trailing look-back. Right at a
   boundary, a maxed-out previous window keeps throttling the new one.
5. **`Node(node_id, shared_bucket)`** -- wraps a `TokenBucket` that multiple nodes
   share, modeling the correct distributed pattern (one counter, e.g. a Redis key,
   read/written by every app server). `fcfs_process_batch` and independent
   per-node buckets exist in the tests specifically to demonstrate the bug this
   avoids: give each node its own bucket and the effective limit becomes
   `capacity * node_count`.
6. **`FairQueueLimiter(capacity, refill_rate, clock)`** -- `process_batch(dict[client_id, pending_count])`
   allocates tokens round-robin across distinct clients with pending requests, so
   one noisy client submitting far more requests than everyone else can't starve
   the rest.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

Two tests are worth reading before you start:
`test_fixed_window_counter_allows_2x_burst_across_a_boundary` proves the bug
happens (20 requests admitted in a 0.02-second span against a limit of 10), and
`test_sliding_window_counter_does_not_allow_2x_burst_across_a_boundary` proves the
fix holds under the identical scenario.

## Stretch goals

1. **Leaky bucket** -- implement the third classic algorithm (constant-rate
   output regardless of input burstiness) and write a test distinguishing its
   behavior from the token bucket's (same average rate, different burst
   tolerance).
2. **Weighted fair queueing** -- extend `FairQueueLimiter` so clients can have
   different weights (e.g. paid tier gets 3x the share of free tier) instead of
   strict round-robin equality, and prove the weighted split with a test.
3. **Distributed limiter under real concurrency** -- swap the single-threaded
   `Node` simulation for actual `threading.Thread`s hammering one shared
   `TokenBucket` with a lock, and write a test proving no race lets total
   admissions exceed capacity even under real concurrent access.
4. **Adaptive limits** -- make `refill_rate` respond to a signal (e.g., observed
   downstream error rate) instead of being a static constant, and test that it
   backs off under simulated errors and recovers once they stop.
