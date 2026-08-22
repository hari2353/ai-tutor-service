# Redis: Structures, Persistence, Cluster, Eviction, Distributed Locks

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-redis` · **Tags:** nosql

## The 30-second version

Redis is a single-threaded, in-memory data structure server: the single thread is what makes every command atomic for free, and it's also the reason one slow command (an unindexed `KEYS *` scan, a huge `SMEMBERS`, a badly-written Lua script) blocks every other client on that instance for its full duration. Durability is a config choice, not a property: RDB gives you point-in-time snapshots that can lose minutes of writes, AOF with `appendfsync everysec` (the default) loses at most about one second, `always` loses at most one command but drops throughput to disk-fsync speed. Cluster mode shards 16,384 hash slots across nodes for horizontal scale, which is exactly why multi-key operations across slots throw `CROSSSLOT` and why you hash-tag related keys (`{user:42}:profile`, `{user:42}:sessions`) to keep them co-located. The distributed lock story is the sharpest interview trap: `SET key val NX EX ttl` and even Redlock give you a lock that a GC pause or clock jump can silently violate, so the honest position is that Redis locks are a performance optimization to reduce duplicate work, not a correctness mechanism for anything where two workers touching the same resource is a real safety violation.

## Why this gets asked

The interviewer has either been paged for a Redis instance that went from 2ms to 4-second p99 latency because someone ran `KEYS *` in a hot path, or has shipped a distributed lock that looked correct in code review and then let two workers double-process the same job during a leader failover. They want to know if you understand single-threaded execution well enough to predict what blocks the event loop, and whether you'll reach for Redlock as a correctness primitive without knowing about the fencing-token gap Kleppmann identified.

---

## Lineage: past → present → future

**What came before.** Before Redis (2009, Salvatore Sanfilippo), the standard cache layer was Memcached (2003), a pure key-value store with no data structures beyond byte strings and no persistence at all — a restart meant a cold cache and a thundering-herd stampede on the database behind it. Applications that needed anything richer than get/set (a leaderboard, a queue, a set of unique visitors) had to build it in the application layer on top of flat key-value pairs, usually badly, with race conditions in the read-modify-write cycle. The pain that killed pure key-value caching as sufficient: real applications kept needing atomic operations on structured data (increment a counter, push onto a list, add to a set) and Memcached's `CAS` (compare-and-swap) was a weak, manual substitute for what a server-side atomic operation gives you directly.

**Where it stands now.** Redis's single-threaded command execution model (one thread executes commands; I/O multiplexing via epoll/kqueue handles concurrent client connections) is still the core design in 2026, and it's the right tradeoff for the workload it targets: every command that doesn't explicitly fan out (like `KEYS`, `SMEMBERS` on a huge set, or `SORT`) completes in microseconds, so there's no lock contention to reason about and no partial-write anomalies. Redis 6 added an optional multi-threaded I/O path for the socket read/write layer only (command execution is still single-threaded), which helps saturate faster network links but does not change the fundamental blocking-command hazard. The live disagreement is over Redis's 2024 license change (from BSD to the source-available RSALv2/SSPLv1 dual license, which prompted the Linux Foundation's **Valkey** fork, backed by AWS, Google Cloud, and the original Redis engineers who left) — Redis 8 (2025) relicensed back to AGPLv3 for the core, but the ecosystem is now genuinely split between Redis proper and Valkey as a compatible drop-in, and which one a given cloud provider ships is no longer a safe assumption. What's actually deployed at scale: managed Redis/Valkey (ElastiCache, MemoryDB, Redis Cloud) in Cluster mode for anything beyond single-node memory limits, with Sentinel or Cluster's own failover for HA, and AOF-everysec as the default durability tradeoff for anything that isn't a pure cache.

**Where it's heading.** Redis 8's built-in vector search and JSON/search modules (formerly separate paid modules — RediSearch, RedisJSON — folded into open core) signal Redis positioning itself as a lightweight document/vector store competitor for small-to-mid corpora, not just a cache; confidence is high that this trend continues since it's already shipped. More speculative: whether Valkey or Redis proper wins mindshare long-term is genuinely unsettled and depends on cloud-provider defaults more than technical merit, since the two are command-compatible today.

---

## Mental model

```
                     ONE event loop thread executes ALL commands
                     (I/O multiplexing handles many client sockets,
                      but only one command runs at a time)

  client A ──╮
  client B ──┼──▶ [socket layer, multi-threaded since Redis 6] ──▶ [single command
  client C ──╯                                                      execution thread]
                                                                          │
                                                    every command is atomic BECAUSE
                                                    nothing else can run while it does

  KEYS *  on 10M keys  ──▶  blocks this thread for the ENTIRE scan
                             every other client's GET/SET queues behind it
                             (the "KEYS incident": p99 goes from 1ms to seconds)

  FIX: SCAN cursor-based iteration -- does bounded work per call, never blocks
```

```
CLUSTER: 16,384 hash slots, keys land in slot = CRC16(key) mod 16384

  node A: slots 0-5460        node B: slots 5461-10922      node C: slots 10923-16383

  MGET {user:42}:profile {user:42}:sessions   -- same hash tag {user:42} -> same slot -> OK
  MGET user:42 user:99                        -- different slots, maybe different nodes
                                               -- -> CROSSSLOT error, command refused
```

---

## How it actually works

### Structures and the problem each one solves

| Structure | Solves | Example op | Complexity |
|---|---|---|---|
| String | counters, flags, cached blobs, bitmaps overlay | `INCR views:page42` | O(1) |
| Hash | an object's fields without separate keys per field | `HSET user:42 name "A" age 31` | O(1) per field |
| List | queue/stack, capped recent-activity feed | `LPUSH`/`RPOP`, `LTRIM` | O(1) at head/tail, O(N) for `LINDEX` mid-list |
| Set | uniqueness, tag membership, set algebra | `SADD`, `SINTER` | O(1) add, O(N) for set ops |
| Sorted set (ZSet) | leaderboards, rate-limit windows, priority queues, range-by-score | `ZADD leaderboard 1500 "alice"`, `ZRANGEBYSCORE` | O(log N) insert (skip list), O(log N + M) range |
| Stream | append-only log with consumer groups | `XADD`, `XREADGROUP` | O(1) append |
| Bitmap | huge boolean sets (daily-active-user tracking) at ~1 bit/user | `SETBIT`, `BITCOUNT` | O(1) set, O(N) count over range |
| HyperLogLog | approximate distinct count at fixed 12KB regardless of cardinality | `PFADD`, `PFCOUNT` | ~0.81% standard error, O(1) space |
| Geo | radius queries over lat/lon (built on ZSet with geohash scores) | `GEOADD`, `GEOSEARCH` | O(log N + M) |

The sorted set is the one people underuse: it's a skip list plus a hash table internally, giving O(log N) insert/update and O(log N + M) range scans, which is why it's the right structure for both "top 10 leaderboard" and "sliding-window rate limiter" (score = timestamp, `ZREMRANGEBYSCORE` to expire old entries, `ZCARD` to count the window).

### Single-threaded execution and the KEYS incident

Every command runs to completion before the next one starts. This is *why* `INCR`, `LPUSH`, `SADD`, even multi-step things like `GETSET`, are atomic with zero locking code anywhere in your application — there is no interleaving possible. The cost is symmetric: **any command whose runtime scales with dataset or result size blocks every other client for that whole duration.** The canonical incident: `KEYS *` on a 10M-key instance walks the entire keyspace, taking hundreds of milliseconds to seconds, and during that window every other client's `GET`/`SET` queues behind it, so p99 latency across the whole service spikes even though only one client issued the offending command. The fix is `SCAN` with a cursor, which does a small bounded amount of work per call and lets other commands interleave between calls, at the cost of not being a point-in-time-consistent view (keys added/removed mid-scan may or may not be seen). The same hazard applies to `SMEMBERS`/`HGETALL` on a multi-million-element structure, `SORT` without `LIMIT`, and Lua scripts with unbounded loops — Lua scripts run with the same atomicity-via-blocking guarantee, so a slow script blocks exactly like a slow native command.

### Persistence: RDB vs AOF, and the honest durability guarantee

**RDB** (Redis Database) is a point-in-time binary snapshot, forked via `fork()` (copy-on-write) so the parent keeps serving while the child writes the snapshot to disk. Fast to load on restart, compact, but every snapshot interval (commonly minutes) is a window of unrecoverable data loss on crash, and the fork itself can cause a latency spike on instances with large, actively-mutated datasets (COW page duplication under write pressure).

**AOF** (Append-Only File) logs every write command (or its effect, in `RESP`-encoded form since Redis 7's "multi-part AOF") and replays it on restart. The durability knob is `appendfsync`:

| Policy | Data loss on crash | Throughput |
|---|---|---|
| `always` | at most 1 command | drops to disk fsync speed, hundreds/sec on HDD, low thousands/sec on SSD |
| `everysec` (**default**) | ~1 second of writes (up to ~2s worst case) | near-full throughput, fsync happens on a background thread |
| `no` | until the OS flushes (Linux default ~30s) | full throughput, weakest guarantee |

The honest guarantee to state in an interview: **Redis's default configuration (AOF everysec, or RDB alone) is not the same durability class as a WAL-backed relational database fsyncing every commit.** If you need zero-data-loss guarantees, you run AOF with `always` (accepting the throughput hit) or you don't treat Redis as your system of record at all. Most production Redis is a cache or a derived-state store precisely because this tradeoff is acceptable when the source of truth lives elsewhere.

### Replication, Sentinel vs Cluster, and the multi-key constraint

**Replication** is asynchronous by default: a write is acknowledged to the client before replicas confirm it, so a primary failover can lose the last few writes that hadn't propagated (`WAIT` can force synchronous acknowledgment from N replicas at a latency cost, per-command).

**Sentinel** monitors a primary/replica set that fits on nodes with enough memory for the whole dataset, and handles automatic failover (promotes a replica when quorum of Sentinels agree the primary is down) without sharding the keyspace — it solves availability, not capacity.

**Cluster** solves capacity: the keyspace is split into 16,384 hash slots (`CRC16(key) mod 16384`), each owned by one primary (plus its own replicas for HA). This is why **multi-key commands are constrained** — `MGET`, `MSET`, transactions (`MULTI`/`EXEC`), and Lua scripts touching multiple keys all require every key involved to hash to the same slot, or Redis returns `CROSSSLOT Keys in request don't hash to the same slot`. The fix is a **hash tag**: `{user:42}:profile` and `{user:42}:sessions` both hash only the substring inside `{}`, so they land on the same slot regardless of the rest of the key name, letting you keep related keys co-located and still use multi-key commands on them.

### Eviction policies and maxmemory

`maxmemory` caps Redis's memory use; what happens at the cap is `maxmemory-policy`, defaulting to `noeviction` (writes start failing with an OOM error, reads still work) — a default that fits almost no cache workload and is a common misconfiguration to flag. For a pure cache: `allkeys-lru` (evict least-recently-used across all keys) or `allkeys-lfu` (evict least-frequently-used, better when you have viral spikes you don't want to evict just because they're not the *most* recent). For a mixed workload where some keys must never be evicted, set TTLs only on the evictable subset and use `volatile-lru`/`volatile-lfu`/`volatile-ttl` (only considers keys with a TTL set; keys without a TTL are never evicted under these policies). Redis approximates true LRU/LFU by sampling (`maxmemory-samples`, default 5) rather than maintaining an exact ordered list, since an exact LRU list would cost memory and CPU on every access; raising the sample size (10) trades a little CPU for closer-to-true LRU accuracy.

### Distributed locks: the honest treatment

**Naive lock:** `SET lock:resource token NX EX 10` — atomically sets only if absent, with a TTL so a crashed holder doesn't lock the resource forever. Release must check the token before deleting (`GET` then `DEL` is not atomic and lets you delete someone else's lock that acquired after your TTL expired) — the correct release is a Lua script (single command, atomic): compare token, delete only if it matches.

```lua
-- untested sketch
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

**Correctness holes even with the token check:** the TTL is a guess about how long the critical section takes. If the holder pauses (GC pause, network partition, CPU steal on a noisy-neighbor VM) longer than the TTL, the lock expires and a second process acquires it — now two processes believe they hold the lock simultaneously, and there is no mechanism in this scheme to detect or prevent that.

**Redlock** (antirez's proposal) tries to harden this by acquiring the lock against a majority of N independent Redis instances (typically 5) within a bounded time window, treating majority-acquisition-within-timeout as "the lock is held." **Kleppmann's critique** (2016, "How to do distributed locking"): Redlock still has no fencing token — a monotonically increasing number handed to the lock holder that the protected resource can use to reject a stale write from a holder that no longer actually holds the lock — so a process that acquired the lock, then experienced a long pause past the TTL (GC, VM migration, disk stall), can resume believing it still holds the lock and issue a write that arrives at the protected resource *after* a second process has legitimately acquired the lock and started its own critical section. Redlock also assumes synchronized clocks; a clock jump (NTP correction, VM host time skew) on any of the N instances can cause a lock to expire early or late relative to what other participants believe. Antirez's rebuttal argued these are edge cases unlikely to matter for Redlock's intended use cases (not applications requiring hard correctness guarantees).

**The honest conclusion:** Redis-based locks (naive or Redlock) are a **performance optimization** — preventing duplicate work, like two cron-triggered jobs racing to do the same expensive computation — not a **correctness mechanism** for anything where two processes concurrently believing they hold a lock is a real safety violation (double-charging a payment, double-shipping an order). For actual correctness, you need either a fencing token validated by the resource itself (the resource, not the lock service, is what must reject stale writes) or a consensus-based lock service (ZooKeeper, etcd) whose guarantees are designed around exactly this failure mode.

### Lua for atomicity

Any sequence of reads and writes that must happen with no other command interleaving is a candidate for a Lua script (`EVAL`/`EVALSHA`, or `FUNCTION` since Redis 7 for persisted, named scripts) — the entire script runs as one atomic unit under the single-thread guarantee, which is how you implement check-and-set patterns (like the lock release above) or multi-key read-modify-write without `WATCH`/`MULTI`/`EXEC` transaction overhead. The tradeoff mirrors the KEYS hazard: a slow or unbounded-loop Lua script blocks the whole instance for its entire runtime, so scripts must be short and bounded.

---

## Build it from scratch

A minimal sliding-window rate limiter using a sorted set, the idiomatic ZSet pattern:

```python
# untested sketch
import time

def is_allowed(redis_client, key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)   # drop entries older than window
    pipe.zadd(key, {str(now): now})                       # record this request
    pipe.zcard(key)                                        # count requests in window
    pipe.expire(key, window_seconds)                       # don't leak memory if traffic stops
    _, _, count, _ = pipe.execute()
    return count <= limit
```

This isn't fully atomic (the pipeline batches commands but doesn't make the whole read-then-decide atomic against a concurrent request from the same key) — the production-correct version wraps the same four operations in a Lua script so no other client's request can interleave between the count and the decision. Full lock/rate-limiter lab with the fencing-token discussion worked out: `(lab pending)`.

---

## How it's done in production

Managed Redis/Valkey (ElastiCache, MemoryDB for Redis, Redis Cloud, Azure Cache for Redis) handles node failover, backups, and Cluster resharding operations; MemoryDB additionally adds a multi-AZ transactional log for stronger durability than open-source Redis's AOF alone, at higher latency. `redis-py`/`Jedis`/`node-redis` cluster clients handle slot-to-node routing and `MOVED`/`ASK` redirects transparently during resharding.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency spikes from ~1ms to hundreds of ms or seconds, cluster-wide, correlated with one client's request | A blocking O(N) command (`KEYS *`, `SMEMBERS` on huge set, unbounded `SORT`) ran on the single command thread | Replace with `SCAN`/`SSCAN`/`HSCAN` cursor iteration; audit for any command whose cost scales with dataset size |
| `OOM command not allowed when used memory > 'maxmemory'` | `maxmemory-policy` is `noeviction` (the default) and the instance is full | Set an eviction policy appropriate to the workload, or provision more memory and alert before the ceiling |
| `CROSSSLOT Keys in request don't hash to the same slot` | Multi-key command touches keys that hash to different Cluster slots | Hash-tag related keys (`{tenant:42}:*`) so they co-locate; or issue per-key commands instead of a multi-key one |
| Two workers both believe they hold a lock and both process the same job | TTL expired during a long GC pause/VM stall before the holder finished; Redlock/naive lock has no fencing token | Add a fencing token validated by the protected resource itself, or use a consensus lock service for hard correctness |
| Replica promoted during failover is missing the last several writes | Asynchronous replication; writes acknowledged before replica ack | Use `WAIT` for critical writes needing durability across replicas, accepting the latency cost |
| Redis Stream memory grows unbounded even though consumers are keeping up | Entries aren't trimmed after being read/acked; Streams don't auto-delete consumed entries | `XTRIM` with `MAXLEN`/`MINID`, or `XADD ... MAXLEN ~ N` to cap stream length on write |

---

## Tradeoffs & when NOT to use it

- **Don't use Redis as a system of record for data you cannot afford to lose seconds of on crash**, unless you're running AOF `always` and have accepted its throughput cost — the default configuration is a cache/derived-state durability class, not a WAL-backed database's.
- **Don't run `KEYS`, unbounded `SMEMBERS`/`HGETALL`, or unbounded Lua loops against production traffic** — the single-thread model means these don't just cost the caller, they cost every other client on the instance.
- **Don't reach for Redlock (or any Redis lock) as a correctness mechanism for financial or safety-critical mutual exclusion.** Use it to reduce duplicate work; use a real consensus system (ZooKeeper, etcd) or a fencing token validated at the resource when correctness actually matters.
- **Don't put unrelated keys that need multi-key atomicity on different logical tenants** in Cluster mode without hash tags — you'll hit `CROSSSLOT` in production the first time traffic actually spans nodes, not in dev with a single-node cluster.
- **For workloads needing durable, ordered, replayable event logs at high throughput with independent consumers** (audit trail, event sourcing at scale), Kafka is the better fit — Redis Streams work well under roughly 200k events/sec on a single stream with in-memory retention, but Kafka's disk-backed retention and consumer-group rebalancing are more mature for that specific shape of problem.
- **For complex relational queries, joins, or ad hoc analytics**, Redis's structures are the wrong tool regardless of how creatively you model them — reach for a relational or OLAP store instead of contorting sorted sets into a query engine.

---

## Interview questions

### Q1 — Why is Redis single-threaded, and what does that buy you?
**Testing:** baseline mechanics, not trivia.
**Answer:** One thread executes commands to completion with no interleaving, so every single command is atomic without any locking code in Redis or your application. I/O multiplexing (and, since Redis 6, a multi-threaded I/O layer) handles many concurrent client connections, but command *execution* stays on one thread.
**Follow-up trap:** "So Redis 6+ is multi-threaded?" — only the socket read/write layer got threaded to help saturate fast NICs; command execution, and therefore the atomicity guarantee, is still single-threaded.

### Q2 — Walk through the KEYS incident: what happens and what's the fix?
**Testing:** whether they've actually operated Redis, not just used it.
**Answer:** `KEYS *` on a large keyspace walks every key on the single command thread, taking anywhere from tens of milliseconds to seconds depending on keyspace size; every other client's commands queue behind it for that whole duration, so cluster-wide p99 spikes even though only one client issued the command. Fix: `SCAN` with a cursor does bounded work per call and interleaves with other commands, at the cost of not being a point-in-time-consistent snapshot of the keyspace.
**Follow-up trap:** "Is SCAN guaranteed to return every key exactly once?" — no; keys added or removed during the scan may or may not appear, and a key could theoretically be returned more than once under certain resizing conditions, but it will never miss a key that existed for the entire scan duration and was never modified.

### Q3 — RDB vs AOF: what does each actually guarantee on crash?
**Answer:** RDB is a periodic point-in-time snapshot; you lose everything written since the last snapshot, commonly minutes. AOF logs every write; durability depends on `appendfsync` — `always` loses at most one command at the cost of throughput dropping to disk fsync speed, `everysec` (the default) loses roughly one second, `no` defers to the OS flush interval (commonly ~30s on Linux).
**Follow-up trap:** "Can you use both?" — yes, and it's the common production setup: AOF for durability, RDB for fast restarts/backups; on restart Redis prefers AOF if both are present since it's the more complete record.

### Q4 — Explain hash slots and why CROSSSLOT happens.
**Answer:** Cluster mode splits the keyspace into 16,384 hash slots, each owned by exactly one primary node; a key's slot is `CRC16(key) mod 16384`. Multi-key commands (`MGET`, transactions, Lua scripts touching multiple keys) require every key to hash to the same slot because the command executes on a single node and Redis doesn't do cross-node multi-key coordination. Keys landing on different slots throw `CROSSSLOT`.
**Follow-up trap:** "How do you keep related keys together?" — hash tags: wrapping the part of the key that should determine the slot in `{}` (e.g. `{user:42}:profile`) makes Redis hash only that substring, so all keys sharing the tag land on the same slot regardless of the rest of the key name.

### Q5 — What's the default eviction policy and why is it usually wrong for a cache?
**Answer:** `noeviction` — once `maxmemory` is hit, writes start failing with an OOM error while reads keep working. For a cache workload you almost always want `allkeys-lru` or `allkeys-lfu` so old/cold data is evicted to make room, rather than the application starting to see write failures.
**Follow-up trap:** "When would `noeviction` actually be correct?" — when Redis holds data that must never be silently dropped (e.g., a queue or a store you're treating as closer to a system of record) and you'd rather fail loudly and alert than lose data invisibly to eviction.

### Q6 — Design a sliding-window rate limiter with Redis.
**Testing:** applying sorted sets to a real pattern.
**Answer:** A sorted set per rate-limited key, score = request timestamp. On each request: `ZREMRANGEBYSCORE` to drop entries older than the window, `ZADD` the current timestamp, `ZCARD` to get the count in the window, compare to the limit, `EXPIRE` the key so it doesn't leak memory if traffic stops. All logarithmic in the number of requests in the window.
**Follow-up trap:** "Is that sequence atomic?" — not unless wrapped in a Lua script or `MULTI`/`EXEC`; run as separate pipelined commands, two concurrent requests from the same key can both read a count that's about to become stale, permitting slightly more than the limit through under race conditions.

### Q7 — Explain the naive `SET NX EX` lock and its correctness hole.
**Answer:** `SET lock:key token NX EX ttl` atomically acquires only if absent, with a TTL as a dead-man's switch against a crashed holder. The hole: the TTL is a guess at critical-section duration; if the holder is paused (GC, VM stall, network partition) longer than the TTL, the lock expires and a second process can acquire it, so two processes can believe they hold the lock simultaneously with nothing detecting that.
**Follow-up trap:** "Does checking the token before DEL on release fix it?" — it fixes accidentally deleting someone else's lock on release, but does nothing about the TTL-expiry double-acquisition scenario above; those are two different bugs.

### Q8 — What is Redlock, and what's Kleppmann's specific critique?
**Testing:** whether they've engaged with the actual argument, not just the folklore "Redlock is bad."
**Answer:** Redlock acquires the lock against a majority of N (typically 5) independent Redis instances within a bounded time window. Kleppmann's critique: Redlock has no fencing token, so a process that acquires the lock and then experiences a long pause (GC, VM migration) past the TTL can resume execution believing it still holds the lock and write to the protected resource after a different process has legitimately acquired the lock and is also in its critical section — nothing stops the stale writer, because the resource itself has no way to reject writes from a holder whose lock has actually expired.
**Follow-up trap:** "What would actually fix this?" — a fencing token: a monotonically increasing number issued with each lock acquisition that the *protected resource* checks and rejects if it's lower than the last token it accepted. The fix has to live at the resource, not in the lock service, because the lock service can't know the writer is stale after the writer resumes from its pause.

### Q9 — Given Kleppmann's critique, when is a Redis lock still the right tool?
**Answer:** When the cost of the correctness hole being hit is "duplicate work happened, harmlessly" rather than "data corruption" — e.g., preventing two cron-triggered instances from both running the same expensive report generation. If two instances occasionally both run it, that's wasted compute, not a safety violation. The distinction is what fails, not how often.
**Follow-up trap:** "So it's never appropriate for anything transactional?" — for a hard correctness requirement (double-charge prevention, exactly-once side effects), use a fencing token validated at the resource or a consensus-based lock (ZooKeeper/etcd session-based locks with ordered ephemeral nodes), not a bare Redis TTL lock.

### Q10 — Sentinel vs Cluster: what problem does each solve?
**Answer:** Sentinel provides automatic failover for a primary/replica set where the whole dataset fits on one node's memory — it solves availability. Cluster shards the keyspace across multiple primaries via hash slots, solving capacity beyond one node's memory, and each shard can itself have replicas for availability within Cluster.
**Follow-up trap:** "Can you use Sentinel and Cluster together?" — no, they're alternative topologies; Cluster has its own built-in failure detection and failover mechanism (gossip protocol between nodes) and doesn't run alongside Sentinel.

### Q11 — What's the actual data-loss window if a Cluster primary fails right after acknowledging a write?
**Testing:** connecting replication semantics to a concrete number.
**Answer:** Replication is asynchronous by default — the client gets acknowledgment before any replica confirms receipt — so any writes not yet propagated to the replica that gets promoted are lost. There's no fixed window; it's whatever hasn't made it across the replication link at the moment of failure, which under normal network conditions is small (sub-millisecond to low milliseconds) but is not bounded or guaranteed.
**Follow-up trap:** "How would you get a guarantee?" — `WAIT numreplicas timeout` blocks the client until at least `numreplicas` replicas acknowledge the write (or timeout), converting the specific write to synchronous replication at a latency cost — used selectively for writes that need it, not universally.

### Q12 — Why does a Redis Stream keep growing even after every consumer has processed every message?
**Answer:** Streams are append-only; consuming and acknowledging (`XACK`) a message doesn't delete it, it just advances the consumer group's position and marks it as no longer pending. Without an explicit trim, every message ever added stays in memory forever.
**Follow-up trap:** "How do you bound it?" — `XTRIM key MAXLEN ~ N` (approximate trim, cheaper) or `MINID`, either as a standalone maintenance command or inline on every `XADD` (`XADD key MAXLEN ~ N * field value`) so the stream self-bounds on every write.

### Q13 — When would you pick Redis Streams over Kafka, and vice versa?
**Answer:** Redis Streams fit single-region workloads under roughly 200k events/sec per stream where you already run Redis and want simple consumer-group semantics without introducing new infrastructure, and where bounded in-memory retention is acceptable. Kafka fits when you need durable disk-backed retention independent of memory size, throughput beyond that range, multiple independent consumer systems reading the same log without coordinating with each other, or strict exactly-once semantics across a distributed pipeline.
**Follow-up trap:** "Doesn't Redis Streams support consumer groups just like Kafka?" — yes, `XREADGROUP` gives at-least-once delivery with per-consumer pending-entry tracking, but Kafka's automatic partition rebalancing across a changing consumer set is more mature; Redis Streams consumer group membership and rebalancing is comparatively manual.

### Q14 — HyperLogLog claims to count distinct elements in fixed space. What's the catch?
**Answer:** HyperLogLog gives an approximate cardinality estimate (~0.81% standard error) using a fixed ~12KB of memory regardless of how many elements were added — it trades exactness for constant space, which is the right trade for "roughly how many unique visitors today" and the wrong trade for anything requiring an exact count or the ability to enumerate the distinct elements (HLL can't tell you what the elements were, only how many there probably are).
**Follow-up trap:** "Can you merge HyperLogLogs?" — yes, `PFMERGE` combines multiple HLLs into a union estimate, which is why it's commonly used for "unique visitors this week" computed from daily HLLs without re-scanning raw data.

### Q15 — A staff-level question: your team wants to use Redis as the source of truth for account balances with concurrent debits. What do you say?
**Testing:** synthesis — durability, atomicity, and locking all at once.
**Answer:** Push back on Redis as the system of record for money: its default durability (AOF everysec or RDB) can lose recent writes on crash, which is unacceptable for balances. If Redis must be involved (e.g., as a fast cache/counter in front of a durable ledger), use atomic operations (`INCRBY`/Lua scripts) for the arithmetic itself so concurrent debits don't race, but treat Redis as derived state reconciled against the durable system of record, not the authority — and if a real cross-process lock is needed, don't use a bare Redis TTL lock for a correctness-critical mutation; use a fencing token validated by the ledger.
**Follow-up trap:** "What if they insist Redis is fast enough and want to skip a separate durable store?" — name the actual failure mode concretely: an AOF everysec crash loses up to ~1 second of debits, silently producing an incorrect balance with no error raised anywhere; make them own that risk explicitly rather than assuming "fast" implies "safe."

---

## Red flags that fail you

- Saying "Redis is atomic so it's safe for concurrent counters" without knowing which specific operations are atomic (single commands, Lua scripts) versus which patterns (read-then-write across multiple round trips) are not.
- Recommending Redlock as a hard correctness mechanism without mentioning the fencing-token gap.
- Not knowing the default eviction policy is `noeviction`, or not knowing `KEYS` is dangerous in production.
- Confusing Sentinel (availability, single dataset) with Cluster (capacity, sharded dataset).
- Claiming Redis persistence gives WAL-database-grade durability by default.
- Not knowing why multi-key commands fail in Cluster mode, or never having heard of hash tags.

---

## Cheat card

```
SINGLE THREAD   1 thread executes commands -> every command atomic, no locks needed
                COST: any O(N) command (KEYS, SMEMBERS/HGETALL on huge structs,
                unbounded SORT/Lua) blocks EVERY client for its duration
                FIX: SCAN/SSCAN/HSCAN cursor iteration, bounded per call

PERSISTENCE     RDB = snapshot, loses since-last-snapshot (minutes) on crash
                AOF appendfsync: always = lose <=1 cmd, disk-fsync speed
                                 everysec (DEFAULT) = lose ~1s, near full throughput
                                 no = lose until OS flush (~30s Linux default)

CLUSTER         16,384 hash slots, slot = CRC16(key) mod 16384, 1 primary/slot
                multi-key cmd across slots -> CROSSSLOT error
                FIX: hash tags {tag}:rest -> only {tag} hashed -> co-locate keys

SENTINEL vs CLUSTER   Sentinel = HA failover, single dataset fits 1 node
                      Cluster  = sharding for capacity + its own failover

EVICTION        maxmemory-policy default = noeviction (writes fail at cap!)
                cache workload: allkeys-lru / allkeys-lfu
                maxmemory-samples default 5 (10 approaches true LRU)

LOCKS           SET k v NX EX ttl = naive lock; release must Lua-check token first
                Redlock = majority of N instances; Kleppmann: NO FENCING TOKEN ->
                paused holder can resume + write after a new holder acquired
                CONCLUSION: Redis locks = perf optimization, NOT correctness
                REAL FIX: fencing token checked at the resource, or ZK/etcd

STREAMS vs KAFKA   Streams: <~200k ev/s, in-memory, simple; must XTRIM (no auto-delete)
                   Kafka: disk retention, >1M ev/s, independent consumers, exactly-once
```

## Sources

- [Key eviction — Redis Docs](https://redis.io/docs/latest/develop/reference/eviction/) — accessed 2026-08-01
- [How to do distributed locking — Martin Kleppmann's blog](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — accessed 2026-08-01
- [Is Redlock safe? — antirez](https://antirez.com/news/101) — accessed 2026-08-01
- [Redis cluster specification — Redis Docs](https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/) — accessed 2026-08-01
- [Redis Persistence and Durability: RDB Snapshots & AOF — Redis](https://redis.io/tutorials/operate/redis-at-scale/persistence-and-durability/) — accessed 2026-08-01
- [Redis persistence — Redis Docs](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/) — accessed 2026-08-01
- [Redis Streams vs Apache Kafka — Instaclustr](https://www.instaclustr.com/blog/redis-streams-vs-apache-kafka/) — accessed 2026-08-01
- [Streams Consumer Group Patterns — Redis Patterns (antirez)](https://redis.antirez.com/fundamental/streams-consumer-patterns.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
