# How production does it

## Resilience4j RateLimiter / Bucket4j — the JVM standards

- **Bucket4j** is exactly your token bucket: bandwidth with capacity + refill
  period, `tryConsume(tokens)` semantics, and optional blocking with timeout.
  Production adds what local state can't give you: distributed buckets backed
  by JCache/Hazelcast/Ignite or Redis, with optimistic retries on contention.
- **resilience4j RateLimiter** defaults to YOUR sliding-window-counter shape
  (`limitForPeriod` refreshed every `limitRefreshPeriod`) precisely because it
  needs no storage between refreshes — cheap, deterministic, thread-safe via
  atomics. Its `limitForPeriod × periods` math replaces your continuous blend;
  coarser, but good enough when windows are short.
- **Guava RateLimiter** implements a smoothed variant: instead of hard bursts,
  stored permits are handed out with computed wait times ("warm-up" included).
  The interview-worthy detail: Guava's design doc argues bursty-then-throttle
  is often WORSE than paced grants for protecting downstreams.

## Distributed reality

One process-local counter is a lie once you have two instances. Production
patterns, cheapest first:

1. Sticky sessions / consistent hashing → per-node limits that sum to the target.
2. Redis INCR-with-TTL (fixed window) — fast, carries the exact boundary bug you built.
3. Redis Lua sliding window / GCRA — atomic, correct, one RTT per check.
4. Central limiter service (Envoy's global rate-limit service) — authoritative, adds a hop.

GCRA (Generic Cell Rate Algorithm) is the connoisseur answer: O(1) state — one
timestamp per client — no background refills, exact burst+tie behavior. Your
TokenBucket with `lastRefillAt` is GCRA minus the elegance.

## What the interview probe looks for

- "Where do the tokens live?" (Process → sticky → Redis → Lua/GCRA ladder.)
- "Why does fixed window over-admit?" (Boundary alignment; show the 20-in-10 math.)
- "What breaks first under contention?" (Check-then-act races → atomic ops.)
- "How do you stop tenant A from starving B?" (Fair queueing / weights, not bigger buckets.)
