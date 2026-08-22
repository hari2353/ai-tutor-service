# Caching Layers, Invalidation, Rate Limiting Algorithms

> **Track:** T10 System Design · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T10-caching-ratelimiting` · **Tags:** fundamentals

## The 30-second version

Caching and rate limiting are the same underlying problem twice: bound the load a slow or finite resource sees, at the cost of either staleness (caching) or rejected requests (rate limiting). Caching has five layers (client, CDN, gateway, application, DB buffer pool) and four patterns (cache-aside, read-through, write-through, write-behind), each trading a different amount of consistency for latency, with cache-aside plus TTL the default and write-behind the dangerous, fast, eventually-consistent outlier that can lose data on a crash before flush. Invalidation is the genuinely hard part: TTL alone gives a stale-read window you have to size deliberately, and every cache expiring a hot key at once produces a cache stampede, whose fix is one of three concrete mechanisms (a recompute lock, probabilistic early recomputation, or request coalescing), not "just cache it." Rate limiting has the same escalation from naive to correct: fixed window is simple but bursts at the boundary (up to 2x the limit across a window edge), sliding window log is exact but O(n) in memory per client, sliding window counter approximates it at O(1), and token/leaky bucket separately control burst tolerance versus smoothing, with the hard part in production being making the check-and-increment atomic across distributed nodes without serializing every request through one lock.

## Why this gets asked

Every interviewer who has run a cache in production has seen a stampede take down a database during a cold restart or a synchronized TTL expiry, and every interviewer who has built a public API has watched a naive rate limiter get bypassed by bursting exactly at a window boundary. The question tests whether "we'll add a cache" or "we'll rate limit it" is backed by a specific invalidation and algorithm choice with numbers attached, or is a hand-wave that will fail identically to how it failed the last time someone tried it without thinking through the failure mode.

## Lineage: past → present → future

**What came before.** Early web-era caching was mostly application-level and ad hoc: a global in-process dictionary with a manually-tuned expiry, or relying entirely on the database's own buffer pool and hoping the working set fit in memory. The specific pain that forced a more disciplined approach was the **dogpile effect** becoming visible at scale: as traffic grew, a single popular cache entry expiring (or a cold cache after a restart) meant every concurrent request fell through to the database simultaneously, and the database, sized for cache-hit-reduced load, fell over. Memcached (2003, originally built for LiveJournal) and later Redis (2009) standardized the cache-aside pattern as a separate, addressable layer in front of the database, but for years the invalidation problem was solved per-team, inconsistently, giving rise to the well-known joke that cache invalidation is one of the two hard problems in computer science. Rate limiting followed a similar arc: early implementations were often a single global counter with a naive reset, which both under-protected (a burst right at reset could double the effective limit) and didn't scale past one process.

**Where it stands now.** The current consensus is that caching and rate limiting are not "add it and forget it" infrastructure but require an explicit, stated invalidation/algorithm choice tied to the actual consistency and burst-tolerance requirements. For caching, cache-aside with TTL plus an explicit stampede mitigation (request coalescing being the most broadly adopted, since it requires no client-visible staleness policy change) is the default for read-heavy workloads; write-through is standard wherever read-after-write consistency actually matters (session state, account balances read immediately after write). For rate limiting, the sliding window counter algorithm has become the practical default for distributed systems needing to balance accuracy against memory cost, with token bucket remaining the standard where the requirement is explicitly framed around burst tolerance (API quotas that allow occasional spikes). The live disagreement is about where to enforce the limit: gateway/edge-level limiting (simpler, coarser) versus per-service or per-user-tier limiting deep in the call graph (more precise, more state to coordinate) — most production systems now do both, coarse at the edge and fine-grained close to the actual constrained resource.

**Where it's heading.** High confidence: probabilistic early recomputation (XFetch and similar schemes, VLDB 2015) and stale-while-revalidate continue displacing hard-TTL-plus-lock as the default stampede mitigation, because they avoid both the dogpile and the added latency of a synchronous recompute lock, at the cost of briefly serving slightly stale data, a tradeoff most read-heavy systems accept happily. For rate limiting, expect continued movement toward limiting-as-a-managed-service (API gateway products with built-in distributed rate limiting) rather than hand-rolled Redis Lua scripts, simply because the atomicity and clock-skew correctness details are easy to get wrong and expensive to re-derive per team. More speculative: cost-aware, adaptive rate limiting (adjusting limits dynamically based on observed backend load rather than a static configured number) is an active area but not yet a settled default outside a handful of large-scale platforms.

---

## Mental model

```
CACHING LAYERS: each one shields the layer behind it, at a different cost/latency point

  client cache (browser/mobile, ms latency, per-user only)
       │ miss
       ▼
  CDN (edge, ~10-50ms, shared across users, static/semi-static content)
       │ miss
       ▼
  gateway/API cache (shared across all users of one API, request/response level)
       │ miss
       ▼
  application cache (Redis/Memcached, ~1-2ms, the layer most "caching" discussions mean)
       │ miss
       ▼
  DB buffer pool (in-process page cache inside the database itself, ~0.1-1ms)
       │ miss
       ▼
  disk / cold storage  <- the thing every layer above exists to protect

CACHE STAMPEDE: the failure every naive TTL cache eventually hits

  key expires at T=0 ──▶ 8,000 concurrent requests all miss simultaneously
                     ──▶ all 8,000 hit the origin/DB at once
                     ──▶ origin falls over, or at minimum p99 spikes hard

  THREE fixes, pick one (or combine):
    1. LOCK: first miss acquires a recompute lock, others wait on it, then read the fresh value
    2. EARLY RECOMPUTE: probabilistically refresh BEFORE expiry, with rising probability
       as expiry nears (XFetch) -- smooths the cliff into a slope
    3. REQUEST COALESCING (single-flight): N concurrent misses for the same key become
       exactly 1 origin call; the other N-1 block on that one result

RATE LIMITING: same shape, different currency (requests, not data)

  fixed window:    |--100 req allowed--|--100 req allowed--|   BOUNDARY BURST: up to
                   0:00                1:00                2:00 200 req in a 2-second span
                                                                 straddling 0:59-1:01

  token bucket:    bucket refills at rate R, holds up to CAPACITY tokens
                   burst up to CAPACITY instantly, then throttled to steady rate R
```

---

## How it actually works

### Cache layers

- **Client cache** (browser HTTP cache, mobile app local storage): per-user, zero network cost on hit, but you have no server-side control once a value is issued short of a low TTL or `Cache-Control` header discipline.
- **CDN**: shared across all users hitting an edge location; excellent for static assets and cacheable API responses (product catalogs, public content), inappropriate for anything personalized without careful `Vary` header use, since a CDN cache poisoned with one user's personalized response and served to another is a real, embarrassing incident class.
- **Gateway/API cache**: sits in front of application servers, can cache whole responses keyed on request shape; useful for expensive, widely-shared computed responses.
- **Application cache** (Redis, Memcached): the layer most system-design discussions mean by "the cache," roughly 1-2ms round trip, shared across all application instances, where cache-aside/read-through/write-through/write-behind patterns actually live.
- **DB buffer pool**: the database engine's own in-memory page cache; invisible to the application, but its effectiveness (whether your working set fits) is directly why a well-designed application cache in front of it can still make a dramatic difference, the buffer pool caches raw pages, not computed query results.

### The four access patterns and what consistency each gives

- **Cache-aside (lazy loading)**: the application checks the cache, on a miss reads the database and populates the cache itself, on a write, the application writes to the database and either invalidates or updates the cache entry. Most common pattern because the cache and database are decoupled, a cache outage degrades to "slower, cache is just empty," not "broken." Consistency: whatever your invalidation strategy gives you, nothing is automatic.
- **Read-through**: the cache library itself is responsible for loading from the database on a miss, transparent to the application; functionally similar to cache-aside but the loading logic lives in the cache layer, reducing duplicated cache-population code across call sites.
- **Write-through**: every write goes to the cache and the database together, synchronously, before the write is considered complete. Gives strong read-after-write consistency (a subsequent read always sees the write) at the cost of write latency, since the write now waits on both stores.
- **Write-behind (write-back)**: the write updates the cache immediately and returns, with the database update queued and applied asynchronously. Fastest writes, but **eventual consistency only**, and the named failure mode is real: if the cache crashes or the process dies before the queued write flushes to the database, that write is lost entirely, this is not a theoretical risk, it's the standard failure mode write-behind trades away durability for and must be explicitly accepted, not discovered in an incident.

### Invalidation: the actually hard part

- **TTL (time-to-live)**: the simplest mechanism, every entry expires after a fixed duration regardless of whether the underlying data changed. Creates a deliberate **stale-read window** of up to the TTL's length, sizing this window is a real design decision: too short and you lose most of the caching benefit (near-constant cache misses), too long and users see stale data for longer than acceptable.
- **Explicit invalidation**: the write path actively deletes or updates the cache entry when the underlying data changes. Gives tighter consistency than pure TTL but requires every write path to remember to invalidate, and misses (a write path that forgets, or a direct database write that bypasses the application) leave stale entries with no natural expiry unless you also set a TTL as a backstop.
- **Versioned keys**: instead of invalidating in place, encode a version (or the underlying data's last-modified timestamp/hash) into the cache key itself, so a data change naturally produces a new key and old entries simply age out unreferenced. Avoids race conditions in in-place invalidation (a stale writer overwriting a fresher value) at the cost of leaving old versions in the cache until TTL/eviction cleans them up.

### Cache stampede: symptom and the three fixes

**The symptom**, observable directly in production: a sharp, synchronized spike in database/origin QPS and latency that correlates exactly with a popular key's TTL expiry or a cache cluster restart (cold cache), followed by a return to normal once the cache repopulates, a signature very different from a gradual organic traffic increase.

1. **Lock-based recompute**: the first request to miss acquires a short-lived lock (e.g., `SETNX` in Redis) and is the only one allowed to query the origin and repopulate the cache; concurrent requests either block briefly waiting on the lock's result or serve a stale value if one exists. Simple and correct, but adds latency to the unlucky first request and requires careful lock-timeout handling (what happens if the lock holder crashes mid-recompute).
2. **Probabilistic early recomputation** (XFetch, from "Optimal Probabilistic Cache Stampede Prevention," VLDB 2015): each reader, as expiry approaches, recomputes the value with a probability that rises the closer to expiry, so instead of every reader waiting until exactly T=0 to all miss simultaneously, a small trickle of readers refresh the value slightly early and reset the TTL, smoothing what would be a synchronized cliff into a gradual, staggered refresh curve ([Cache Stampede prevention techniques — oneuptime.com](https://oneuptime.com/blog/post/2026-01-30-cache-stampede-prevention/view) — accessed 2026-08-01).
3. **Request coalescing (single-flight)**: at most one in-flight request per key is ever allowed to reach the origin; every other concurrent request for that same key is deduplicated and simply waits on the first request's result rather than issuing its own. This turns N concurrent misses into exactly 1 origin call, origin load drops from N to 1 regardless of how large N is ([Prevent Cache Stampede: Single-Flight Pattern — 1xapi.com](https://1xapi.com/blog/nodejs-cache-stampede-single-flight-pattern-2026/) — accessed 2026-08-01).

### Hot keys and negative caching

A **hot key** is a different problem from a stampede: it's sustained, disproportionate traffic to one specific key (a viral post, a celebrity's profile), not a synchronized expiry event. No amount of horizontal cache sharding fixes it, since one key's traffic is served by whichever single node owns that key's partition. Fixes: replicate the hot key across multiple cache nodes and route reads round-robin (accepting the added invalidation complexity of multiple copies), or cache the hot value at a layer even closer to the client (CDN/local in-process cache with a short TTL) to shave load off the shared cache tier entirely.

**Negative caching**: caching the fact that something was *not found*, briefly, to stop a client (or attacker) from repeatedly triggering an expensive lookup for a key that doesn't exist. Set a short TTL on negative entries specifically (the absence might become presence at any time, e.g. a user who hasn't signed up yet but will), and invalidate the negative entry immediately once the underlying data actually appears, or you serve a stale "not found" to a user who just successfully created the resource.

### Rate limiting algorithms, derived

**Fixed window counter**: increment a counter keyed by `(client, current_window)`, reject once the counter exceeds the limit, reset at each window boundary. Trivial to implement, `O(1)` memory per client. **The boundary burst problem**: a client can send the full limit's worth of requests at the very end of one window and the full limit again at the very start of the next, producing up to **2x the intended limit** within a short span straddling the boundary (e.g., 100 requests at 0:59 and another 100 at 1:00 for a "100 req/min" limit means 200 requests in about 2 seconds).

**Sliding window log**: store a timestamp for every request in a sorted structure (e.g. a Redis sorted set), and on each check, remove entries older than the window and count what remains. **Exact**, no boundary burst possible, but memory cost is `O(n)` in the number of requests within the window per client, a client making 10,000 requests/minute costs 10,000 stored timestamps just for that one client's rate-limit state.

**Sliding window counter**: approximate the sliding log using two fixed windows (current and previous) and a weighted interpolation, `count = current_window_count + previous_window_count × (1 - elapsed_fraction_of_current_window)`. Gets close to exact accuracy at `O(1)` memory per client (just two counters), this is the practical default for most distributed rate limiting because it avoids both the fixed window's boundary burst and the sliding log's memory cost ([Rate Limiting Algorithms Compared — Medium](https://medium.com/@erwindev/rate-limiting-algorithms-compared-token-bucket-leaky-bucket-and-sliding-window-log-acd9c44bc86f) — accessed 2026-08-01).

**Token bucket**: a bucket holds up to `capacity` tokens, refilling at a steady rate `r` tokens/second; each request consumes one token, and a request is rejected if the bucket is empty. Explicitly designed to **allow bursts**, a client that hasn't made requests in a while can burst up to `capacity` requests instantly, then is throttled to the steady refill rate, this is the right model whenever bursty-but-bounded usage is a legitimate pattern (a user opening an app and firing several requests at once, then going idle).

**Leaky bucket**: requests enter a queue (the bucket) and are processed (leak out) at a strictly constant rate regardless of arrival burstiness; if the queue is full, new requests are dropped. Unlike token bucket, it **smooths** output to a constant rate rather than permitting bursts through, appropriate when the downstream resource genuinely cannot tolerate any burst at all (a fixed-capacity legacy system with no headroom).

**Worked arithmetic**: a "1000 requests/minute" limit as sliding window log costs roughly 1000 timestamps × ~8 bytes (a Redis sorted-set score) × however many active clients, at 100,000 concurrent clients that's roughly 800 MB just for rate-limit state, versus the sliding window counter's roughly two integers per client (~16 bytes × 100,000 ≈ 1.6 MB), a genuinely material difference at scale.

### Distributed rate limiting: why it's hard

A single-process, in-memory rate limiter is trivial: a counter and a lock. The moment the limit needs to be enforced across multiple application instances (which is almost always the real requirement, since horizontally-scaled services are the norm), the state has to live somewhere shared, and **the check-then-increment has to be atomic**, or two concurrent requests on different instances can both read "count = 99, limit = 100," both decide to allow the request, and both increment, silently letting the limit slip to 101 or more under concurrent load. The standard production fix is a Redis Lua script: the entire read-check-increment sequence executes as one atomic operation on the Redis server, since Lua scripts in Redis run to completion without interleaving with other clients' commands ([Designing a Distributed Rate Limiter with Redis Lua Scripts](https://sibilsarjamsoren.in/blog/distributed-rate-limiting-redis-lua) — accessed 2026-08-01). A second, easy-to-miss correctness issue: **clock skew** across distributed nodes computing "current window" independently can produce inconsistent windowing; the standard fix is to use Redis's own `TIME` command (or a similarly centralized clock) as the source of truth for window boundaries rather than each node's local wall clock.

### 429 and client backoff

A rejected request should return **HTTP 429 Too Many Requests** with a `Retry-After` header (either a number of seconds or an HTTP date) telling the client when it's safe to retry. A well-behaved client implements **exponential backoff with jitter**: on a 429, wait `min(cap, base × 2^attempt) × random_jitter_factor` before retrying, rather than retrying immediately (which just re-triggers the limit and can synchronize retries across many clients into another burst, a self-inflicted stampede against the rate limiter itself).

---

## Build it from scratch

A minimal, single-process sliding window counter and a request-coalescing cache wrapper, enough to see the arithmetic and the deduplication mechanism without a real Redis backend:

```python
# untested sketch -- illustrates sliding window counter arithmetic and single-flight
# coalescing; not production-hardened (no distributed locking, no real clock source)
import time
import threading

class SlidingWindowCounter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.counts = {}  # client_id -> {window_start: count}

    def _window_start(self, now, offset=0):
        return int(now // self.window) * self.window - offset * self.window

    def allow(self, client_id, now=None):
        now = now if now is not None else time.time()
        cur_start = self._window_start(now)
        prev_start = self._window_start(now, offset=1)
        client_windows = self.counts.setdefault(client_id, {})
        cur_count = client_windows.get(cur_start, 0)
        prev_count = client_windows.get(prev_start, 0)
        elapsed_fraction = (now - cur_start) / self.window
        estimated = prev_count * (1 - elapsed_fraction) + cur_count
        if estimated >= self.limit:
            return False
        client_windows[cur_start] = cur_count + 1
        # prune old windows
        for w in list(client_windows):
            if w not in (cur_start, prev_start):
                del client_windows[w]
        return True


class CoalescingCache:
    """Ensures at most one in-flight recompute per key -- fixes cache stampede."""
    def __init__(self):
        self.cache = {}
        self.locks = {}
        self.global_lock = threading.Lock()

    def get_or_compute(self, key, compute_fn, ttl=60):
        entry = self.cache.get(key)
        now = time.time()
        if entry and entry[1] > now:
            return entry[0]

        with self.global_lock:
            lock = self.locks.setdefault(key, threading.Lock())

        with lock:
            # re-check after acquiring: another thread may have already recomputed
            entry = self.cache.get(key)
            if entry and entry[1] > now:
                return entry[0]
            value = compute_fn()  # the ONLY caller that actually hits the origin
            self.cache[key] = (value, now + ttl)
            return value
```

This omits the distributed case entirely (a real deployment needs the Redis Lua atomic check-increment for rate limiting, and a distributed lock or Redis-based single-flight for coalescing across multiple application instances, not just threads in one process). A full lab covering both the Redis Lua rate limiter and a distributed request-coalescing cache belongs at `(lab pending)` (not yet in this repo).

---

## How it's done in production

| Concern | What the managed/framework version adds |
|---|---|
| Distributed rate limiting | Redis with atomic Lua scripts (`EVAL`) for the check-increment; API gateway products (Kong, Envoy rate limit service, cloud API gateways) offering built-in distributed limiting so teams don't hand-roll the atomicity and clock-skew handling |
| Cache stampede prevention at scale | CDNs and caching proxies (Varnish, nginx) implement request collapsing natively; application-level libraries (`golang.org/x/sync/singleflight`, various Node/Python single-flight packages) for in-process coalescing, paired with a distributed lock for cross-instance coalescing |
| Hot key mitigation | Client-side local caching of known-hot keys with a short TTL to shave load off the shared tier; some managed caches (certain Redis-compatible services) offer built-in hot-key detection and automatic local replication |
| Write-behind durability | Backing the write-behind queue with a durable, replayable log (Kafka) rather than an in-memory queue, so a cache crash doesn't silently lose unflushed writes |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Database CPU/QPS spikes sharply and briefly, correlated with a cache TTL or restart | Cache stampede: many concurrent requests miss simultaneously and all hit the origin | Request coalescing (single-flight) as the default fix; probabilistic early recomputation for read-heavy hot keys |
| One cache node/shard is at far higher load than the rest despite even key distribution | Hot key: disproportionate traffic to one specific key, not a partitioning problem | Replicate the hot key across nodes with round-robin reads, or cache it one layer closer to the client |
| A user sees their own just-created resource as "not found" for a period after creating it | Negative cache entry not invalidated when the resource was created | Explicitly invalidate negative cache entries on write, and keep negative-entry TTLs short |
| Two concurrent requests both get allowed even though the count should have exceeded the limit | Non-atomic check-then-increment across distributed instances (race condition) | Atomic check-and-increment via a Redis Lua script, or a single source of truth with proper locking |
| A rate limiter allows roughly double the configured limit right at the top of every minute | Fixed window boundary burst | Move to sliding window counter or sliding window log |
| Write-behind cache crashes and a batch of writes that were queued are simply gone | Write-behind queue was in-memory only, not backed by durable storage | Back the async write queue with a durable log (Kafka, a WAL) so queued writes survive a crash |
| Clients hammering a rate-limited endpoint in synchronized retry bursts right after being throttled | No backoff, or fixed-interval retry without jitter, causing retries to re-synchronize | Return 429 with `Retry-After`; require exponential backoff with jitter on the client |

---

## Tradeoffs & when NOT to use it

- **Don't use write-behind caching for anything where losing an unflushed write is unacceptable** (financial transactions, anything with a compliance or audit requirement). The performance win is real but the durability trade is not appropriate for that class of data; use write-through instead and accept the latency cost.
- **Don't reach for a sliding window log by default "for accuracy."** The `O(n)` memory cost per client is a real, scaling operational cost; sliding window counter gets close enough to exact for the overwhelming majority of rate-limiting use cases at a fraction of the memory.
- **Don't use fixed window rate limiting for anything public-facing or adversarial** (a public API, anything an attacker might probe). The boundary burst is a known, exploitable gap, not a theoretical edge case, and it will be found.
- **Caching is the wrong fix for a genuinely write-heavy, low-repeat-read workload.** If most reads are for data that was just written once and rarely re-read, cache hit rate will be low and you've added invalidation complexity for little benefit; profile the actual hit rate before committing to a caching layer.
- **Negative caching is dangerous for security-sensitive lookups** (e.g., "does this username exist" used for account enumeration): caching and returning a fast "not found" response can itself be an information-leak side channel via timing, and the tradeoff needs explicit security review, not just a performance one.
- **A recompute lock for stampede prevention adds latency to whichever request is unlucky enough to be first.** If sub-100ms tail latency matters more than avoiding a brief origin spike, probabilistic early recomputation (which never makes any single request wait) is usually the better fit despite being harder to reason about.
- **Token bucket is the wrong model when the downstream system genuinely cannot handle any burst at all.** Leaky bucket's strict output smoothing is the correct choice there; token bucket's whole point is permitting controlled bursts, which is precisely what such a system can't absorb.

---

## Interview questions

### Q1 — Compare cache-aside, read-through, write-through, and write-behind. What consistency does each give?
**Testing:** whether the four patterns are distinguished by consistency behavior, not just by which side populates the cache.
**Answer:** Cache-aside and read-through both let a miss fall through to the database and populate the cache afterward (application-driven vs. cache-library-driven respectively); consistency depends entirely on the invalidation strategy layered on top, nothing is automatic. Write-through writes to cache and database synchronously, giving strong read-after-write consistency at the cost of write latency. Write-behind writes to the cache immediately and queues the database write asynchronously, giving the fastest writes but only eventual consistency, and a real risk of losing the queued write if the cache crashes before it flushes.
**Follow-up trap:** *"Which would you use for a shopping cart total that must be correct immediately after a user adds an item?"* — write-through, or cache-aside with synchronous invalidation on write; write-behind's eventual consistency window means the user could refresh and see a stale, wrong total right after their own action, which is exactly the read-your-writes violation a shopping flow can't tolerate.

### Q2 — What causes a cache stampede, and name the three concrete fixes.
**Testing:** whether "add a cache" comes with an actual stampede mitigation plan.
**Answer:** A stampede happens when a popular key expires (or the cache restarts cold) and many concurrent requests all miss at the same instant, all falling through to the origin/database simultaneously and overwhelming it. Three fixes: a recompute lock (first miss acquires a lock and is the only one allowed to repopulate, others wait), probabilistic early recomputation (readers refresh with rising probability as expiry approaches, smoothing the cliff into a slope), and request coalescing/single-flight (all concurrent misses for one key collapse into exactly one origin call).
**Follow-up trap:** *"Your fix is a recompute lock. What happens if the lock holder crashes mid-recompute?"* — without a lock timeout, every other request waiting on that lock blocks forever; the lock needs a TTL shorter than the acceptable wait time, and on timeout another waiter should be allowed to attempt the recompute itself, accepting the small risk of two recomputes racing rather than an indefinite stall.

### Q3 — Explain the fixed window rate limiter's boundary burst problem with numbers.
**Testing:** whether the failure is understood mechanically, not just named.
**Answer:** A fixed window limiter resets its counter at fixed boundaries (e.g., every 60 seconds). A client can send the full limit's worth of requests in the last second of one window and the full limit again in the first second of the next window, since each window's counter is independent. For a "100 requests/minute" limit, that's 100 requests at 0:59 and another 100 at 1:00, 200 requests within about 2 seconds, double the intended rate.
**Follow-up trap:** *"Why doesn't a sliding window log have this problem?"* — it counts requests within a continuously moving window (now minus the window length), not a fixed clock-aligned bucket, so there's no boundary at which the counted history discontinuously resets to zero; the count at any instant reflects exactly the true request history for the preceding window length.

### Q4 — Token bucket vs. leaky bucket: same category of algorithm, different behavior. Explain the difference and when each is right.
**Testing:** the distinction most candidates blur.
**Answer:** Token bucket accumulates tokens at a steady rate up to a capacity, and permits a burst up to that capacity instantly before throttling to the steady rate, it's designed to allow controlled burstiness. Leaky bucket processes requests out of a queue at a strictly constant rate regardless of how bursty the arrivals are, smoothing everything to one steady output rate and dropping what doesn't fit in the queue. Use token bucket when bursty-but-bounded usage is legitimate (a user firing a batch of requests then going idle); use leaky bucket when the downstream resource genuinely cannot tolerate any burst, only a constant rate.
**Follow-up trap:** *"Can you configure a token bucket to behave like a leaky bucket?"* — not exactly; setting capacity equal to the refill rate (bucket size = 1 second's worth of tokens) minimizes burst tolerance but a token bucket still releases tokens instantly on request rather than smoothing output timing the way leaky bucket's queue-and-drain model does, they optimize different things (burst admission vs. output smoothing) even at extreme parameter settings.

### Q5 — Why is check-then-increment for a distributed rate limiter a race condition, and how do you fix it?
**Testing:** whether the atomicity requirement is understood as the actual hard part.
**Answer:** If checking the current count and incrementing it are two separate operations, two concurrent requests on different application instances can both read "count = 99, limit = 100" before either has incremented, both decide to allow the request, and both increment, letting the effective limit slip past 100 under concurrency. The fix is making the read-check-increment sequence atomic, typically via a Redis Lua script, which Redis executes as a single, non-interleaved operation.
**Follow-up trap:** *"What if you're not using Redis, just a distributed SQL database?"* — you'd need an atomic increment-with-constraint operation (e.g., a conditional `UPDATE ... WHERE count < limit RETURNING`) executed as a single statement or within a transaction with appropriate isolation, the underlying requirement, atomicity of the check-and-increment, doesn't change with the storage technology, only the specific mechanism for achieving it does.

### Q6 — What's the memory cost difference between a sliding window log and a sliding window counter, with numbers?
**Testing:** quantitative reasoning about a real design tradeoff.
**Answer:** Sliding window log stores one timestamp per request within the window, per client, for a "1000 req/min" limit and 100,000 concurrent clients, that's up to 1000 × 100,000 = 10^8 timestamp entries at peak, roughly 800MB at ~8 bytes each. Sliding window counter stores just two integers per client (current and previous window counts), so the same 100,000 clients cost roughly 100,000 × 2 × 8 bytes ≈ 1.6MB, several orders of magnitude less, at the cost of the counter being a close approximation rather than exact.
**Follow-up trap:** *"How inaccurate is the sliding window counter approximation, concretely?"* — it assumes requests are uniformly distributed within the previous window when computing the weighted estimate, which is an approximation, not exact; in practice the error is small enough to be acceptable for the overwhelming majority of rate-limiting use cases, but it can under- or over-count slightly for a client whose request pattern is heavily clustered rather than uniform within that prior window.

### Q7 — What's the difference between a hot key and a cache stampede? Why doesn't the stampede fix solve the hot key problem?
**Testing:** whether these two failure modes, often confused, are correctly distinguished.
**Answer:** A stampede is a synchronized, transient event, a specific key's expiry (or a cold cache) triggers a burst of simultaneous misses that resolves once the cache repopulates. A hot key is sustained, disproportionate traffic to one key over time, not tied to an expiry event, one popular item gets far more reads than any other key, concentrating load on whichever single cache node or partition owns it. Stampede fixes (coalescing, locks, early recompute) all assume the problem is "too many concurrent recomputes," but a hot key's problem is "too much sustained read traffic to one node even with a warm cache," which those fixes don't address at all.
**Follow-up trap:** *"How would you actually fix a hot key, then?"* — replicate that specific key across multiple cache nodes and route reads round-robin across the copies, or push it up a layer (CDN or local in-process cache with a short TTL) to shave load off the shared cache tier entirely; you cannot fix a single overloaded key by re-sharding or adding more cache nodes, since sharding still routes that one key to exactly one node.

### Q8 — Design a stale-read-window policy: how would you decide the TTL for a product price cache on an e-commerce site?
**Testing:** synthesis, connecting invalidation choice to a business requirement with numbers.
**Answer:** Start from the actual acceptable staleness: if the business tolerates a customer seeing a price up to 60 seconds old (common for non-flash-sale catalog browsing), a 60-second TTL with cache-aside is sufficient and simple. If price changes need to be reflected immediately (a flash sale, a price correction), pair a longer TTL (for the common case's efficiency) with explicit invalidation on the write path specifically for price-change events, so the fast path (TTL) handles normal staleness tolerance while the exception path (explicit invalidation) handles the cases that can't wait.
**Follow-up trap:** *"What happens if the explicit invalidation write path has a bug and silently fails for some updates?"* — this is exactly why a TTL backstop matters even when you have explicit invalidation: without it, a missed invalidation leaves a stale price cached indefinitely; with even a generous TTL (say, 10 minutes) as a backstop, the blast radius of a missed invalidation is bounded to that window rather than unbounded.

### Q9 — A candidate proposes negative caching for a "check if username is available" endpoint. What's the risk?
**Testing:** whether performance optimizations are checked against security implications.
**Answer:** Negative caching here means caching "username not found" (i.e., available) responses; the risk is less about staleness (a username becoming taken between checks is a normal race any registration flow must already handle) and more that a cached fast-path response for "not found" versus a slower uncached path for "found" can become a timing side channel for account enumeration, letting an attacker infer which usernames exist based on response latency alone, independent of the actual cached content.
**Follow-up trap:** *"How would you cache this safely then?"* — cache both the positive and negative result with the same latency profile (so timing reveals nothing), keep the negative TTL very short since availability changes are meaningful, and treat this as a security review item, not purely a performance one, since the actual fix (uniform latency) is a security requirement layered on top of the caching decision.

### Q10 — Your rate limiter uses sliding window counter, and monitoring shows it's letting through roughly 5-10% more requests than the configured limit during highly bursty traffic. Is this a bug?
**Testing:** whether the algorithm's known approximation error is understood versus an actual implementation defect.
**Answer:** Not necessarily a bug, this is the sliding window counter's known behavior: it interpolates the previous window's count assuming uniform distribution within that window, and traffic that's heavily clustered near the end of the previous window (rather than uniform) causes the counter to underestimate the true recent request rate, letting slightly more through than an exact sliding log would. Whether this is acceptable depends on how tightly the limit needs to be enforced; if 5-10% overage is unacceptable (a hard resource ceiling, not just fairness), sliding window log's exactness is worth its memory cost for that specific limiter.
**Follow-up trap:** *"How would you verify it's the algorithm's expected approximation error and not a real bug?"* — compare against a sliding window log implementation on the same traffic sample; if the overage tracks the known interpolation-error pattern (worse under clustered bursty traffic, near-exact under uniform traffic) rather than being unconditional or growing over time, that's evidence it's the expected approximation rather than a race condition or logic error.

### Q11 — When would you explicitly choose NOT to add a cache in front of a data store?
**Testing:** the "when not to use it" the module demands, applied under interview pressure.
**Answer:** When the read pattern is dominated by unique, rarely-repeated reads (each query fetches data unlikely to be requested again soon), cache hit rate will be low, and you've added invalidation complexity, a new failure mode (stale reads), and operational surface for negligible benefit; profiling actual hit rate before committing to caching, rather than assuming it helps, is the correct default. Also skip it when the underlying store is already fast enough for the read pattern (a well-indexed query hitting a warm DB buffer pool) and the added consistency risk of a cache isn't worth shaving a few milliseconds off an already-fast path.
**Follow-up trap:** *"Give a concrete example from a real system."* — an audit log query interface where analysts run ad hoc, highly varied queries against historical data; almost no two queries repeat exactly, so a query-result cache would have a near-zero hit rate while adding real invalidation risk (stale audit data is a compliance problem), the right investment there is query performance (indexing, columnar storage) rather than caching.

### Q12 — Design rate limiting for a public API with three tiers (free, pro, enterprise) with different limits, enforced across a fleet of stateless API servers.
**Testing:** synthesis across algorithm choice, distributed atomicity, and a real multi-tenant requirement.
**Answer:** Use sliding window counter (best accuracy/memory tradeoff for a public API) keyed by `(api_key, tier_limit)`, backed by Redis with the check-increment done via a Lua script for atomicity across the stateless server fleet, since any server might handle any given client's request. Store the tier's limit as configuration looked up by API key (not hardcoded), so upgrading a customer's tier takes effect on their next request without redeploying. Return 429 with `Retry-After` computed from the window's remaining time, and document the exponential-backoff-with-jitter expectation for clients.
**Follow-up trap:** *"Enterprise customers complain that a single burst of legitimate batch activity gets throttled even though their monthly usage is well under quota. What do you change?"* — this is a signal that sliding window (which enforces a smooth rate) is the wrong model for enterprise's usage pattern; switch enterprise tier specifically to token bucket with a larger capacity, explicitly permitting bursts up to that capacity while still bounding the long-term average rate via the refill rate, keeping free/pro on sliding window counter where burst tolerance isn't a stated requirement.

---

## Red flags that fail you

- Proposing "add a cache" or "add a rate limiter" with no stated invalidation strategy or algorithm choice.
- Not knowing the fixed window boundary burst can double the effective limit.
- Recommending sliding window log without acknowledging its O(n) memory cost, or recommending it as the default without being asked for exactness.
- Confusing a hot key with a cache stampede, or proposing a stampede fix (coalescing, lock) for a sustained hot-key load problem.
- Treating write-behind as a strictly-better write-through with no durability caveat.
- Proposing a distributed rate limiter without addressing the check-then-increment atomicity problem.
- Not mentioning 429 + Retry-After, or not knowing clients need backoff with jitter, not fixed-interval retry.
- Suggesting negative caching for a security-sensitive existence check without flagging the enumeration/timing risk.

---

## Cheat card

```
CACHE LAYERS (each shields the next): client -> CDN -> gateway -> app cache (Redis/Memcached,
  ~1-2ms) -> DB buffer pool (~0.1-1ms) -> disk

FOUR PATTERNS, consistency ranked strong -> eventual
  write-through: sync write to cache+DB, strong read-after-write, higher write latency
  read-through / cache-aside: consistency = whatever invalidation strategy you add
  write-behind: async DB write, FASTEST, eventual consistency, LOSES unflushed writes on crash

INVALIDATION
  TTL: simple, deliberate stale-read window sized to acceptable staleness
  explicit: tighter, but every write path must remember to invalidate (backstop w/ TTL)
  versioned keys: new data -> new key, avoids in-place race, old versions age out naturally

CACHE STAMPEDE (many concurrent misses hit origin at once) -- symptom: sharp synced
  DB QPS/latency spike at TTL expiry or cold-cache restart. THREE fixes:
  1. recompute lock (SETNX) -- first miss recomputes, others wait; needs a lock TTL
  2. probabilistic early recompute (XFetch, VLDB 2015) -- rising-probability early refresh
  3. request coalescing / single-flight -- N misses -> exactly 1 origin call

HOT KEY != stampede. Sustained, not transient. Fix: replicate key across nodes + round-robin
  reads, or push a layer closer to client (CDN/local cache). Sharding does NOT fix one hot key.

NEGATIVE CACHING: cache "not found" briefly (short TTL), invalidate on write. Security risk
  for existence checks (enumeration via timing) -- needs uniform latency, not just perf review.

RATE LIMITING ALGORITHMS
  fixed window: O(1) mem, BOUNDARY BURST up to 2x limit across window edge
  sliding window log: EXACT, O(n) mem per client (timestamp per request)
  sliding window counter: O(1) mem (2 counters), interpolated approx -- practical default
  token bucket: refill rate r, capacity C -- ALLOWS BURST up to C, then throttles to r
  leaky bucket: constant drain rate, SMOOTHS bursty input, drops overflow -- no burst allowed

  numbers: 1000req/min sliding-log @ 100k clients ~800MB vs sliding-counter ~1.6MB

DISTRIBUTED RATE LIMITING IS HARD because check-then-increment is a RACE across instances.
  Fix: atomic Redis Lua script (EVAL) for read-check-increment as one op.
  Clock skew: use a shared clock source (Redis TIME), not each node's local wall clock.

429 + Retry-After (seconds or HTTP date). Client MUST use exponential backoff + jitter,
  not fixed-interval retry, or throttled clients synchronize into a retry storm.
```

## Sources

- [Optimal Probabilistic Cache Stampede Prevention (XFetch) — VLDB 2015, summarized via Cache Stampede Prevention — oneuptime.com](https://oneuptime.com/blog/post/2026-01-30-cache-stampede-prevention/view) — accessed 2026-08-01
- [Prevent Cache Stampede in Node.js: Single-Flight Pattern — 1xapi.com](https://1xapi.com/blog/nodejs-cache-stampede-single-flight-pattern-2026/) — accessed 2026-08-01
- [Rate Limiting Algorithms Compared: Token Bucket, Leaky Bucket, and Sliding Window Log — Medium](https://medium.com/@erwindev/rate-limiting-algorithms-compared-token-bucket-leaky-bucket-and-sliding-window-log-acd9c44bc86f) — accessed 2026-08-01
- [Rate Limiting Algorithms: Token Bucket vs Sliding Window vs Fixed Window — Arcjet](https://blog.arcjet.com/rate-limiting-algorithms-token-bucket-vs-sliding-window-vs-fixed-window/) — accessed 2026-08-01
- [Build 5 Rate Limiters with Redis — Redis docs](https://redis.io/tutorials/howtos/ratelimiting/) — accessed 2026-08-01
- [Designing a Distributed Rate Limiter with Redis Lua Scripts](https://sibilsarjamsoren.in/blog/distributed-rate-limiting-redis-lua) — accessed 2026-08-01
- [Design a Distributed Rate Limiter — Hello Interview](https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter) — accessed 2026-08-01
- [Negative Caching — System Design — GeeksforGeeks](https://www.geeksforgeeks.org/system-design/negative-caching-system-design/) — accessed 2026-08-01
- [Caching challenges and strategies — AWS Builders' Library](https://aws.amazon.com/builders-library/caching-challenges-and-strategies/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
