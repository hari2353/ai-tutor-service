# Lab 01 (Java): Rate Limiters From Scratch

**Track:** T01 Python & SWE Craft / T21 Architecture & Design Principles · **Time:** 3h · **XP:** 50
**Modules:** `T01-asyncio`, `T21-resilience-advanced`

**You will build:** a token bucket (exact burst-then-throttle behavior), a fixed-
window counter and the sliding-window counter that fixes its classic boundary bug,
a distributed-style limiter that shares one counter across multiple "nodes", and a
round-robin fair-queueing limiter — all driven by an injectable clock, zero
external dependencies (no JUnit download; a 40-line harness runs the suite).

**You will be able to answer:** *"Implement a token bucket rate limiter. Then explain the fixed-window counter bug and why your fix doesn't have it — with numbers, not a hand wave."*

## Setup

```bash
cd labs/java/01-rate-limiter
javac --version      # JDK 21+ — nothing else to install
```

## How starter/solution selection works

`starter/` and `solution/` hold the same class names in the same packages;
the gate script compiles `lib/ + <one of them> + tests/` into a scratch dir:

```powershell
powershell -File gate.ps1                 # starter  → FAILS. Make them pass.
$env:LAB_IMPL='solution'; powershell -File gate.ps1   # reference must pass
```

(bash: `bash gate.sh`, same env var.)

## The spec

1. **`RateLimitClock` / `FakeClock`** — `nowSeconds()` reads time;
   `advance(s)` moves fake time without blocking. Every limiter takes a clock
   and never touches the wall clock directly.
2. **`TokenBucket(capacity, refillPerSecond, clock[, initialTokens])`** —
   refills continuously at `refillPerSecond` tokens/second capped at
   `capacity`. `tryAcquire(cost)` returns true/false and spends ONLY on
   success. Fresh bucket → immediate burst up to capacity; sustained
   throughput exactly refillPerSecond. Fractional advances accumulate.
3. **`FixedWindowCounter(limit, windowSeconds, clock)`** — the naive buggy
   baseline ON PURPOSE: count resets at each calendar-aligned boundary, so a
   client can push `limit` through late in one window and `limit` more right
   after the boundary — 2x in a near-instant span. The test proves it happens:
   20 admitted across one boundary against a limit of 10.
4. **`SlidingWindowCounter(limit, windowSeconds, clock)`** — the fix: blend
   the previous window's count weighted by how much is still inside the
   look-back: `est = current + prev * (window - posInCurrent) / window`.
   Same scenario admits exactly ONE more at the boundary, and recovers fully
   as old windows age out. A jump of >1 window drops stale history entirely.
5. **`Node(nodeId, sharedBucket)`** — models the correct distributed pattern:
   one counter (a Redis key) shared by every app server. The test shows the
   alternative silently multiplies your limit by nodeCount (6 → 18).
6. **`FairQueueLimiter(capacity, refillPerSecond, clock)`** —
   `processBatch(pendingByClient)` distributes tokens round-robin over
   DISTINCT client ids (sorted order for determinism), so a noisy client
   submitting 100× more than everyone else cannot starve the rest.
7. **Bounded probes** — every admission loop in the suite caps its tries: a
   broken implementation may never answer "yes" forever, but it must never
   wedge the run either. (A hung test is worse than a failed test.)

## Run the tests

```powershell
$env:LAB_IMPL='solution'; powershell -File gate.ps1 -Verbose
```

## Stretch goals

1. **Leaky bucket** — implement the third classic algorithm and write a test
   distinguishing it from the token bucket (same average rate, different burst
   tolerance). *(Interview: name all three without notes.)*
2. **Weighted fair queueing** — paid tier gets 3× the share of free; prove the
   split with a test. *(Interview: how do you sell fairness to the paying customer?)*
3. **Real concurrency** — hammer one shared TokenBucket from N threads with a
   lock; prove total admissions never exceed capacity under races.
4. **GCRA** — reimplement the token bucket as Generic Cell Rate Algorithm:
   one timestamp of state per client, no background refill math.
