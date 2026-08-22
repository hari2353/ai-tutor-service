# 25 Classic System Designs: From URL Shortener to Google Docs

> **Track:** T10 System Design · **Time:** 6.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T10-classic-designs` · **Tags:** practice

## The 30-second version

Roughly 25 prompts cover the large majority of "design X" rounds, and every one of them is a mutation of about eight recurring decision patterns: atomic compare-and-swap on a scarce resource, fanout-write versus fanout-read amplification, prefix/geo indexing that collapses a high-dimensional lookup to O(1), content-addressed dedup storage, distributed ID generation without a central bottleneck, durable-intent-then-confirm across a boundary you don't control, cache-in-front-of-durable-store, and correctness-via-single-writer-serialization. Interviewers deliberately mutate the classic prompt (change the follower distribution, the consistency requirement, the write rate) specifically to find out whether you recall an architecture or can re-derive one from the pattern underneath it. This module gives 15 designs full depth (requirements through follow-ups) and 10 more in compact form, because a memorized answer to a mutated prompt is worse than a shallow answer you can actually defend.

## Why this gets asked

Because the interviewer needs a proxy for "will this person's design survive contact with production," and 45 minutes is not enough time to watch that happen for real, so they watch you navigate a compressed, deliberately underspecified version of a problem they have actually lived through. Every design below maps to a real production system with a real incident behind at least one of its decisions: Dropbox's block-level dedup exists because early sync clients re-uploaded whole files on a one-byte edit; Stripe's idempotency keys exist because a network retry once double-charged a real card; Twitter's Snowflake exists because a single-machine auto-increment ID generator became the whole platform's write bottleneck. The interviewer is listening for whether you know *why* the pattern exists, not whether you can draw the boxes.

---

## Lineage: past → present → future

**What came before.** Through the mid-2010s the dominant candidate strategy was pure pattern recall: memorize the reference architecture for a shortener, a feed, a chat system, and hope the prompt matched. The pain that killed it, documented across FAANG interview retrospectives, is that interviewers started deliberately mutating the classic prompts specifically to catch recall without derivation — "now the average user follows 50,000 accounts" collapses a memorized fanout-on-write answer immediately, while a candidate who understood *why* fanout-on-write was chosen can name the threshold at which it stops paying for itself. Alex Xu's *System Design Interview* (2020) systematized the classic-25 canon and remains the shared vocabulary every interviewer and candidate uses, but it froze the answers at a moment when "design Twitter" meant a specific fanout diagram rather than a derivation exercise.

**Where it stands now.** The current bar, consistent with `T10-design-method`, treats every one of these 25 prompts as an instance of "derive requirements → numbers → API → data model → architecture," with the classic answer serving only as a sanity check on the destination, never as the starting point. The live disagreement is how much of the canonical answer to *say out loud* as prior knowledge versus re-derive live: naming "this is the celebrity-fanout problem, hybrid fanout-on-write below a follower threshold and fanout-on-read above it" in the first two minutes reads as expertise to some interviewers and as "reciting" to others who want to watch you get there. The safe move, confirmed across Meta, Google, and Stripe interview guides ([Exponent, Meta System Design](https://www.tryexponent.com/blog/meta-system-design-interview), [Exponent, Google System Design](https://www.tryexponent.com/blog/google-system-design-interview), [Exponent, Stripe System Design](https://www.tryexponent.com/blog/stripe-system-design-interview) — accessed 2026-08-01), is to derive the number that forces the pattern ("50M followers means 50M writes for one post, that's the celebrity problem") rather than naming the pattern cold.

**Where it's heading.** High confidence: prompts increasingly mutate a classic design with an AI-shaped constraint bolted on ("design a news feed with an LLM-generated summary," "design a support ticket system with an agent that can take actions"), which is covered in `T10-ml-designs` and `T10-design-method`'s Q12. Medium confidence: cost is graded on every one of these 25 now, not just the AI-flavored ones — expect "what does this cost per month" on a plain URL shortener. Speculative: the canon itself is slowly shifting as interviewers retire the most-memorized prompts (URL shortener is reportedly being phased down at some companies precisely because it is too well-rehearsed) in favor of less-searchable variants of the same underlying patterns.

---

## Mental model

Twenty-five systems, eight patterns. Learn the pattern, not the system, and a mutated prompt stops being scary.

```
PATTERN                                   WHERE IT SHOWS UP BELOW
──────────────────────────────────────    ──────────────────────────────────────
1. Atomic CAS on a scarce resource         ticket booking, hotel reservation,
   (never read-then-write)                 ride-hailing driver offer, rate limiter

2. Fanout-write vs fanout-read             news feed, notification system, group
   (amplification tradeoff, celebrity      chat, leaderboard
   problem = hybrid of both)

3. Prefix/geo index collapsing a           proximity service, ride-hailing match,
   high-dimensional lookup to O(1)-ish     search autocomplete (prefix trie is the
                                           same trick in string-space, not map-space)

4. Content-addressed / dedup storage       pastebin, Google Drive, object store

5. Distributed ID / ordering without       unique ID generator, payment idempotency
   a central bottleneck                    keys, chat per-conversation sequence no.

6. Durable-intent-then-confirm across      payment system, ticket booking payment
   a boundary you do not control           step, distributed job scheduler claim

7. Cache-in-front-of-durable-store         URL shortener redirect, KV store,
                                           distributed cache, autocomplete

8. Correctness via single-writer          matching engine, distributed scheduler
   serialization (the exception to        leader election
   "shard everything for scale")
```

The meta-skill this module teaches is not "know 25 answers." It is: **when you hear the mutated prompt, identify which of these 8 problems it actually is, and the design falls out of the pattern rather than out of memory.**

---

## How it actually works

Every design below follows the same eight-part structure, which is `T10-design-method`'s CRAFT phases (Requirements → Constraints → API → Data model → Architecture → Scale → Failure) compressed for a catalogue entry:

| Header here | Design-method phase | What it forces you to commit to |
|---|---|---|
| Requirements | Phase 1 | The 3-5 in-scope FRs, the NFRs via SCALD-CoM, and 3 clarifying questions that name two alternatives each |
| Scale | Phase 2 | 3-4 numbers you will actually use, with the arithmetic shown |
| API | Phase 3 | The 3-5 endpoints whose signatures encode the read/write split and the sync/async boundary |
| Data model | Phase 4 | Tables, keys, and the one line that matters: the partition key |
| The design | Phase 5 | The ASCII box diagram, derived from the four artefacts above |
| The hard part | — | The one decision the question actually exists to test. This is the line an interviewer remembers you by. |
| Failure modes | Phase 7 | What breaks first and its observable symptom |
| Follow-ups | Interview questions | 3 real follow-ups with answers, distinct from the per-question "why" |

Reproduce this live by running the actual 45-minute clock from `T10-design-method`; this module supplies the destination each phase should reach, not a replacement for the process that gets you there.

The first 15 designs get full depth because interviewers spend real follow-up time on them; the remaining 10 are compact because the marginal value of a sixth deep breakdown of "another CRUD-plus-cache system" is lower than covering more of the pattern space. Depth ordering below is: 1-15 deep, 16-25 compact, in the order listed in the module spec.

## Build it from scratch

Pattern 1 (atomic CAS on a scarce resource) recurs in four designs below and is the single most commonly botched piece of code in this catalogue — candidates reach for read-then-write under pressure even when they know better. This is the reference implementation, a Redis Lua script that makes the check-and-hold a single atomic round trip:

```python
# untested sketch — illustrates the pattern, not a production library
import redis
import time
import uuid

r = redis.Redis()

HOLD_SCRIPT = """
-- KEYS[1] = seat key, e.g. "seat:event123:A17"
-- ARGV[1] = hold_id, ARGV[2] = ttl_seconds
local current = redis.call('GET', KEYS[1])
if current then
    return 0                                   -- already held or sold
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""
hold_seat = r.register_script(HOLD_SCRIPT)

def try_hold_seat(event_id: str, seat_id: str, ttl_seconds: int = 600) -> str | None:
    hold_id = str(uuid.uuid4())
    key = f"seat:{event_id}:{seat_id}"
    ok = hold_seat(keys=[key], args=[hold_id, ttl_seconds])
    return hold_id if ok else None

def confirm_booking(event_id: str, seat_id: str, hold_id: str) -> bool:
    key = f"seat:{event_id}:{seat_id}"
    # WATCH/MULTI or another Lua script in production: this needs the same
    # atomicity guarantee as the hold itself, shown here as a single script.
    RELEASE_ON_MATCH = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        redis.call('SET', KEYS[1], 'SOLD')
        return 1
    end
    return 0
    """
    confirm = r.register_script(RELEASE_ON_MATCH)
    return bool(confirm(keys=[key], args=[hold_id]))
```

The property that matters: `GET`-then-`SET` inside one Lua script is atomic from Redis's perspective because Redis executes a script as a single command with no interleaving. The same shape (compare, then conditionally write, as one indivisible operation) reappears as `UPDATE ... WHERE status = 'available'` with an affected-row check in a relational database, or as a versioned conditional write (`ETag`/`If-Match`) against an object store. Whatever the storage engine, the rule is identical: never let application code observe a value and then decide to write based on that observation in two separate round trips.

## How it's done in production

| Design here | Real system | Actual documented choice |
|---|---|---|
| Unique ID generator | Twitter/X Snowflake | 64-bit: timestamp + machine id + sequence, no central coordinator ([Twitter Engineering, Snowflake](https://blog.x.com/engineering/en_us/a/2010/announcing-snowflake) — accessed 2026-08-01) |
| Google Drive / file sync | Dropbox | Block-level, content-addressed dedup; famously moved off S3 to custom infrastructure partly over egress cost at their scale ([Dropbox Tech Blog, Magic Pocket](https://dropbox.tech/infrastructure/inside-the-magic-pocket) — accessed 2026-08-01) |
| Payment system | Stripe | `Idempotency-Key` header, durable local record before the network call, reconciliation against the processor for ambiguous outcomes ([Stripe Docs, Idempotent Requests](https://docs.stripe.com/api/idempotent_requests) — accessed 2026-08-01) |
| Collaborative editing | Google Docs vs. Figma/Notion | Docs uses Operational Transformation with a central server as ordering authority; Figma and Notion use CRDTs for offline/peer-to-peer tolerance ([SystemDR, CRDTs vs OT](https://systemdr.systemdrd.com/p/crdts-vs-operational-transformation) — accessed 2026-08-01) |
| Rate limiter | Stripe, Cloudflare | Token bucket / sliding-window counter in a shared store (Redis), Lua-scripted for atomicity ([ByteByteGo, Design a Rate Limiter](https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter) — accessed 2026-08-01) |
| Ticket booking | Ticketmaster-class systems | Temporary seat hold with TTL, waiting-room admission control ahead of the booking service for flash sales ([Hello Interview, Ticketmaster](https://www.hellointerview.com/learn/system-design/problem-breakdowns/ticketmaster) — accessed 2026-08-01) |

### What breaks when you apply this catalogue wrong

| Symptom | Cause | Fix |
|---|---|---|
| You recite the celebrity-fanout hybrid before computing a single number | Pattern recall without derivation | Force yourself to state the follower-count number that makes fanout-on-write break, then name the fix |
| Interviewer mutates one constraint and your whole design collapses | You memorized the destination, not the derivation | Re-run phases 1-2 of `T10-design-method` against the new constraint out loud |
| You reach for the same "add a cache" answer on every design | Treating pattern 7 as the universal answer | Ask what pattern 1-8 the *specific* bottleneck actually is before reaching for cache |
| You describe two designs identically because "they both need a queue" | Missing the load-bearing difference (ordering guarantee, replay semantics, fanout ratio) | Name the one number or constraint that would make the two designs diverge |

---

## Tradeoffs & when NOT to use it

**This catalogue is a floor, not a ceiling.** Passing on pattern recognition gets you to "competent." It does not survive a genuinely novel prompt, and interviewers increasingly choose prompts precisely because they resist this catalogue: "design the developer experience for our internal deploy tool," "design a system that lets a support agent safely let an LLM take actions on a customer's account," "here is our real architecture, find the problem." None of these have a canonical shape to recall.

**Do not force a design into one of the 8 patterns if it genuinely does not fit.** A prompt about front-end state synchronization or API ergonomics has no QPS number that matters; spending five minutes on capacity estimation there is a tell that you pattern-matched the *round type* incorrectly, not just the system.

**When the interviewer hands you an existing architecture and asks you to find the problem**, this catalogue's "derive from scratch" posture is actively wrong — you are doing failure-mode and bottleneck analysis on someone else's completed design (`T10-design-method`'s phases 6-7 only), not re-deriving requirements they already have.

**ML-flavored variants of these same 25 prompts need `T10-ml-designs`, not this module.** "Design a news feed" here is about the storage/fanout system; "design the *ranking* for that feed" is a different discipline (label definition, offline/online metric divergence, training/serving skew) covered there.

---

## The 15 deep designs

### 1. URL Shortener
**Asked at:** Reported at Amazon, Google, and as a generic first-round staple across FAANG-adjacent companies ([Glassdoor, Amazon URL shortener](https://www.glassdoor.com/Interview/How-would-you-design-a-URL-shortener-service-QTN_1274023.htm), [Hello Interview, URL Shortener](https://www.hellointerview.com/community/questions/url-shortener-design/cm5svnaco01dqxszbok7e1lk1) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: shorten a long URL (optionally with a custom alias and expiration), redirect a short code to its long URL. NFR: redirect latency dominates the SLO (users notice a slow redirect, not a slow shorten), read:write ratio is heavily read-skewed, uniqueness of codes is non-negotiable, availability over strict consistency (a redirect served from a slightly stale cache is fine). Clarifying questions: (1) "Do we need custom aliases, or only generated codes?" — custom aliases add a uniqueness-conflict path the generator alone doesn't have. (2) "Do we need click analytics?" — turns this from a pure cache-and-redirect system into one with a write-heavy side pipeline. (3) "Do links expire?" — changes whether the datastore needs a TTL/GC path at all.

**Scale** — Assume 100M new URLs/month, 5-year retention: 100M × 60 months × ~500B/row ≈ 3 TB of metadata, trivial for a single sharded relational store. Write rate: 100M/month ÷ 2.6M s/month ≈ 40 writes/sec average. Read:write of 100:1 (typical for this kind of link-sharing product) gives ~4,000 reads/sec average, ×3 for peak ≈ 12,000 reads/sec. Code space: base62 at 7 characters gives 62⁷ ≈ 3.5 trillion codes, comfortably enough headroom that collision handling is a corner case, not a bottleneck.

**API**
```
POST /v1/urls   { long_url, custom_alias?, ttl_days? }
  → 201 { short_code, short_url }         errors: 400, 409 (alias taken)
GET  /{short_code}
  → 302 Location: <long_url>              cached aggressively; 302 not 301
DELETE /v1/urls/{short_code}              → 204
```

**Data model** — `urls(short_code PK, long_url, owner_id, created_at, expires_at, click_count)`, partitioned by `hash(short_code)` since access is always by exact code, never a range. No secondary index needed on the hot path.

**The design**
```
client ──▶ LB ──▶ API service ──▶ Redis (short_code → long_url) ──▶ Postgres (sharded)
                        │                    ▲ cache-aside, 302 on hit
                        └── write path: allocate code (range-based counter
                            service, base62-encode) → write DB → warm cache
```

**The hard part** — Generating unique short codes at write scale *without* a single global auto-increment becoming the write bottleneck. The production-grade answer is a range allocator ("ticket server"): each API node leases a block of IDs (e.g., 10,000 at a time) from a coordination service, base62-encodes them locally with zero further coordination until the block is exhausted. The naive alternative, hashing the long URL and truncating, needs a collision-retry loop and makes codes somewhat guessable from the input, which is a security-relevant tradeoff worth naming.

**Failure modes** — Cache layer down: read traffic falls through entirely to the database; symptom is a latency spike on every redirect and DB CPU climbing in lockstep with cache miss rate; mitigation is read replicas plus a cache warm-up path, not just "the cache will refill." Range allocator down: writes block entirely because no node can safely mint a code; mitigation is running the allocator with multiple nodes each owning disjoint ranges, not a single point of failure. Viral link: one short code receives a redirect storm; because a 302 response is small and the mapping is immutable once created, this is trivially CDN-cacheable at the edge, which most naive designs miss.

**Follow-ups they will ask**
1. *How do you stop someone from enumerating all your URLs?* Don't expose sequential IDs as codes directly; add a permutation step (e.g., encode a counter through a reversible bijection, or mix in a per-shard random component) so codes aren't trivially guessable in order, and rate-limit the creation endpoint.
2. *301 or 302?* 302, because a 301 gets cached by the browser/CDN and every subsequent click for that user bypasses your server entirely, killing click analytics. 301 is the wrong default the moment analytics matters, and most real link shorteners use 302 for exactly this reason.
3. *How do custom aliases interact with the generated-code space?* Treat them as the same namespace with a uniqueness constraint on insert, and return 409 with a suggestion on conflict; never silently reassign.

---

### 2. Pastebin
**Asked at:** Common warm-up/first-round prompt, functionally adjacent to the URL shortener in most FAANG-style question banks ([AlgoMaster, System Design Interviews](https://algomaster.io/learn/system-design-interviews) — accessed 2026-08-01) · **Time:** 40 min

**Requirements** — FR: create a paste (text, up to a size cap) and get a shareable link, retrieve by ID, optional expiration. NFR: read-heavy, payloads up to several MB (unlike the URL shortener's tiny payload), durability of stored content matters more than for a link. Clarifying questions: (1) "What's the max paste size?" — decides whether content lives in the row store at all. (2) "Is expiration mandatory or optional per-paste?" — decides whether GC is a core requirement or an add-on. (3) "Public, or private with auth?" — decides whether access control is in scope.

**Scale** — 1M pastes/day, average 10 KB ⇒ 10 GB/day, 1-year hot retention ⇒ ~3.65 TB. Read:write ≈ 10:1.

**API**
```
POST /v1/pastes  { content, expires_in? }  → 201 { id, url }
GET  /v1/pastes/{id}                       → 200 { content, created_at, expires_at }
DELETE /v1/pastes/{id}                     → 204
```

**Data model** — `pastes(id PK, owner_id, size, storage_pointer, created_at, expires_at)` in Postgres; actual content in an object store (S3-class), never in the row itself once past a few KB, because large blobs in a row store blow out buffer-cache efficiency for every unrelated query.

**The design**
```
client ──▶ API ──┬─▶ object store (content, content-addressed by sha256)
                  └─▶ metadata DB (id → pointer, expiry)
GET: metadata DB (pointer) ──▶ object store (content) ──▶ client, CDN-cached if public
```

**The hard part** — Ordering the two writes (blob, then metadata) so a crash mid-operation fails safe. Write the content-addressed blob first (idempotent: re-writing the same hash is a no-op), then the metadata row pointing at it. A crash before the metadata write leaves an orphaned blob (cheap, garbage-collected later); doing it the other way round leaves a metadata row pointing at content that was never written, which breaks every read of that paste.

**Failure modes** — Object store write succeeds, metadata write fails: orphaned blob, invisible to users, cleaned up by a reference-counted GC sweep. Expiration not enforced: lazy-delete on read (check `expires_at`, return 404, queue for deletion) plus a background sweep, rather than relying on the sweep alone, so a still-cached-but-expired paste doesn't linger visible.

**Follow-ups they will ask**
1. *Can you deduplicate identical pastes?* Content-hash the blob (SHA-256) and use it as the object key; two identical pastes point at one stored blob with a reference count, and you only pay storage once.
2. *How do you stop this from becoming a malware/phishing host?* Async content-scanning pipeline off the write path (never block the create call on a scan), rate limits per account/IP, and a takedown path that flips a `blocked` flag without deleting the audit trail.
3. *What changes if pastes can be edited?* Content addressing breaks (the hash changes), so you need a mutable pointer with a version history — this is a smaller version of the Google Drive versioning problem below.

---

### 3. Rate Limiter
**Asked at:** One of the most consistently reported system-design prompts across companies, cited as a staple at Google, Uber, and Stripe-style interviews ([ByteByteGo, Design a Rate Limiter](https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter) — accessed 2026-08-01) · **Time:** 40 min

**Requirements** — FR: given a key (user, API key, or IP) and an endpoint, decide allow/deny against a configured policy, and return standard headers (`X-RateLimit-Remaining`, `Retry-After`). NFR: must add negligible latency to every request it guards (sub-millisecond), must actually bound abuse across a fleet of stateless callers (not just per-node), and the limiter's own downtime must not become an outage. Clarifying questions: (1) "Fail open or fail closed if the limiter store is unreachable?" — a security-sensitive endpoint wants fail-closed, a general API usually wants fail-open. (2) "Global limit shared across the whole fleet, or per-node approximate?" — the former needs a shared store, the latter can be local and cheaper but overshoots the limit by up to N× the node count. (3) "Smooth rate or allow bursts?" — token bucket allows controlled bursts; a strict window does not.

**Scale** — 1M requests/sec across the fleet need a check; a single Redis node handles on the rough order of 100k-1M simple ops/sec, so the limiter must shard its counters by key across a Redis cluster rather than serialize through one node.

**API** — Usually an internal library or sidecar call, not a public endpoint: `ALLOW(key, cost=1) -> {allowed: bool, remaining: int, reset_at: ts}`. If exposed as a shared service: `POST /v1/check {key, limit, window_seconds}`.

**Data model** — Per-key counter or timestamp log in Redis, sharded by `hash(key)`. Sliding-window-counter representation: two adjacent fixed windows plus a weighted interpolation, giving O(1) memory per key instead of the O(n) a sliding-window-log would need.

**The design**
```
request ──▶ middleware ──▶ Lua script on Redis shard for hash(key)
                              GET bucket state, compute allow/deny + new state,
                              SET atomically — one round trip, no race
                              └─ allow → forward request
                              └─ deny  → 429 + Retry-After
```

**The hard part** — Making the check atomic under concurrent requests for the same key without adding a network round trip per check. A naive `GET count; if count < limit: INCR` is a read-then-write race: two concurrent requests can both read `count = limit - 1` and both proceed, exceeding the limit. The fix is a single Lua script executed atomically by Redis (or an atomic `INCR` with a separately-set `EXPIRE`, which is nearly as good for the simple fixed-window case).

**Failure modes** — Fixed window at a boundary: 2× the intended limit can pass in a small window straddling the boundary (100 requests in the last 1ms of one window plus 100 in the first 1ms of the next); the sliding-window-counter algorithm exists specifically to close this, at the cost of being an approximation. Redis shard for a hot key down: fail-open (protect availability, accept some over-limit traffic) or fail-closed (protect the backend, reject everything for that key) — state which you chose and why, because the "right" answer depends entirely on what's behind the limiter. Clock skew across app servers if you roll your own local counters instead of a shared store: inconsistent enforcement, visible as some users getting rate-limited earlier than others for identical traffic.

**Follow-ups they will ask**
1. *Token bucket vs. sliding window log vs. sliding window counter?* Token bucket allows bursts up to the bucket size, then smooths — best UX for bursty legitimate clients. Sliding window log is exact but O(requests-in-window) memory per key. Sliding window counter approximates with ~1% typical error and O(1) memory — the right default for most systems.
2. *How would you rate-limit at a CDN/edge layer vs. the origin?* Edge for cheap, coarse, IP-based limiting with no real auth context; origin for precise per-user/per-key limits that need the authenticated identity the edge doesn't have.
3. *How do you rate-limit consistently across multiple regions?* Either accept per-region approximate limits with async cross-region replication of counters (simple, eventually consistent, usually good enough), or pay for a coordinated global counter service (expensive, rarely justified) — say explicitly which you're choosing and why.

---

### 4. Distributed Key-Value Store
**Asked at:** Common infra-track prompt, frequently framed as "design DynamoDB" or "design a distributed cache with durability" ([Hello Interview, distributed KV patterns](https://www.hellointerview.com) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: `put(key, value)`, `get(key)`, `delete(key)`, replicated for durability and partition tolerance. NFR: an explicit CAP choice (this design defaults to AP, Dynamo-style, favoring write availability), tunable read/write consistency, horizontal scalability with no single coordinator on the hot path. Clarifying questions: (1) "Do we need read-your-own-writes?" — decides whether quorum reads are mandatory or eventual consistency is acceptable. (2) "What's the value size distribution?" — large values change replication cost and may need chunking. (3) "Single datacenter or multi-region?" — multi-region reopens the whole consistency model.

**Scale** — 10M keys × 1 KB average value × 3-way replication ≈ 30 GB, trivial; real systems at this pattern (Dynamo, Cassandra) scale to billions of keys and petabytes. Assume 100k ops/sec mixed 80/20 read/write, requiring sharding across dozens of nodes.

**API** — `PUT /v1/kv/{key} {value}`, `GET /v1/kv/{key}`, `DELETE /v1/kv/{key}`, each internally routed to a coordinator node that computes the key's position on the hash ring.

**Data model** — Consistent hashing ring with virtual nodes (each physical node owns many small ring segments, so a node joining/leaving redistributes load across many peers rather than dumping it all on one neighbor). Replication factor N=3; quorum reads/writes with R+W>N (e.g., N=3, W=2, R=2) guarantee at least one overlapping replica between any write and any subsequent read.

**The design**
```
client ──▶ any node (coordinator) ──▶ hash(key) → position on ring
                                        → preference list of N nodes
                                        → write to W, ack on quorum
                                        → read from R, resolve conflicts, return
```

**The hard part** — Resolving concurrent writes to the same key across replicas when the system favors availability over strict consistency. Two options: vector clocks, which detect that two writes were concurrent (neither happened-before the other) and push resolution to the application (Dynamo's shopping-cart merge is the canonical example — union the two carts rather than picking one); or last-write-wins by wall-clock timestamp, which is simpler but silently discards one write, and is only acceptable when losing data silently is tolerable for that value type.

**Failure modes** — Node down: hinted handoff writes to a substitute node temporarily, replayed once the original returns; if the substitute also fails before replay, there is a real data-loss window, which is the honest cost of choosing availability. Stale replica detected on read: read-repair pushes the newest value to the stale replicas in the background. Network partition: sloppy quorum keeps the system available on both sides of the partition at the cost of temporary inconsistency, which is the AP choice made explicit rather than an accident.

**Follow-ups they will ask**
1. *Why does consistent hashing avoid a full reshard when a node joins?* Virtual nodes spread the departing/joining node's key range across many other nodes in small pieces, instead of one physical neighbor absorbing the entire range at once.
2. *Walk through the quorum math for N=3, W=2, R=2.* Any write touches 2 of 3 replicas; any read touches 2 of 3; by pigeonhole, the read set and the write set must overlap in at least one node, so the read is guaranteed to see the latest acknowledged write (or something concurrent with it, which is where vector clocks matter).
3. *Vector clocks or last-write-wins, and why would you pick one?* Vector clocks when silently dropping a concurrent write is unacceptable (financial or cart data); LWW when simplicity matters more and occasional silent overwrite is tolerable (a "last seen" timestamp, a cache entry).

---

### 5. Unique ID Generator
**Asked at:** Frequently framed directly as "design Twitter's Snowflake" or as a sub-problem inside a larger design ([Twitter Engineering, Announcing Snowflake](https://blog.x.com/engineering/en_us/a/2010/announcing-snowflake) — accessed 2026-08-01) · **Time:** 30 min

**Requirements** — FR: generate 64-bit, roughly time-sortable, globally unique IDs at high throughput with no central coordination bottleneck on the hot path. NFR: >10k IDs/sec per node, zero collisions across the whole fleet, sortable enough that ID order approximates creation order for range scans. Clarifying questions: (1) "Must IDs be strictly increasing system-wide, or per-node monotonic and roughly time-ordered is fine?" — the latter is dramatically cheaper. (2) "Does it need to fit in a 64-bit integer (a DB primary key column) or can it be UUID-length?" (3) "How many nodes, realistically, ever?" — decides how many bits to spend on machine ID.

**Scale** — 1,000 nodes × 10,000 IDs/sec each = 10M IDs/sec system-wide with zero cross-node coordination per ID.

**API** — Internal library call, `next_id() -> int64`; if centralized as a service for polyglot callers, `POST /v1/ids/next`.

**Data model** — Nothing persisted per ID. Machine-ID assignment is the only piece of state, coordinated via a lease from etcd/ZooKeeper on startup (or a static per-node config baked into infrastructure-as-code, simpler but less dynamic).

**The design**
```
64 bits: [1 unused][41 bits: ms since custom epoch, ~69 years][10 bits: machine id, 1024 nodes][12 bits: sequence, 4096/ms/node]
next_id():
  now = current_ms()
  if now < last_ms: refuse and wait — clock moved backward, never reuse a sequence
  if now == last_ms: sequence += 1; if sequence overflows 4095, spin to next ms
  else: sequence = 0
  return (now << 22) | (machine_id << 12) | sequence
```

**The hard part** — Handling clock skew, specifically an NTP correction that moves the local clock backward. Reusing the timestamp bits from before the jump risks generating an ID identical to one already issued. The correct behavior is to detect `now < last_timestamp`, refuse to generate, and either wait for the clock to catch up or alert and fail — never silently reuse a sequence for an earlier timestamp.

**Failure modes** — Clock jumps backward: ID generation stalls on that node until the clock recovers, observable as a latency spike (not an error) on that node's ID allocations specifically. Machine ID space exhausted (more than 1,024 nodes): requires widening the bit allocation, which is a breaking format change if IDs are already persisted elsewhere — plan the bit budget with real headroom up front. Sequence overflow within one millisecond (more than 4,096 IDs requested by one node in 1ms): spin until the next millisecond tick rather than dropping the request.

**Follow-ups they will ask**
1. *Why not just use UUIDv4?* Random and not sortable, which is bad for B-tree index locality as a primary key (inserts scatter across the whole index rather than appending), and 128 bits versus 64. UUIDv7 (time-ordered) closes most of this gap and is a legitimate modern alternative, but you lose the compact fixed bit-layout you get from designing your own.
2. *How do you assign machine IDs without that becoming a central bottleneck itself?* A short-lived lease from etcd/ZooKeeper at process startup, cached in memory for the process lifetime and renewed periodically — coordination happens once per process lifetime, not once per ID.
3. *Can two different datacenters ever generate the same ID?* Only if their machine-ID bit ranges overlap. Partition the machine-ID bits into a datacenter sub-field and a per-datacenter worker sub-field so global uniqueness is structural, not a coordination promise.

---

### 6. Web Crawler
**Asked at:** Commonly framed as a Google-flavored large-scale infra prompt ([GeeksforGeeks, Web Crawler design](https://www.geeksforgeeks.org/system-design/design-a-web-crawler/) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: given seed URLs, fetch pages, extract links, store content, respect `robots.txt` and per-host politeness, avoid infinite loops and near-duplicate content. NFR: scale to billions of pages, never overload a single host, support recrawl for freshness. Clarifying questions: (1) "Whole web or a bounded domain set?" — changes frontier size by orders of magnitude. (2) "What's the freshness requirement?" — decides whether recrawl prioritization is in scope. (3) "What happens to the content after crawling — indexed, or just archived?" — decides whether ranking/indexing is in scope (it usually isn't for this prompt).

**Scale** — Target 1B pages/month ⇒ ~400 pages/sec average, much higher at peak. Average page 500 KB raw ⇒ 500 TB of raw storage for 1B pages before any dedup or compression.

**API** — Internal system, not a public API. If exposed for operational control: `POST /v1/seeds {urls[]}`, `GET /v1/crawl/status`.

**Data model** — URL frontier: per-host priority queues keyed by `(host, next_allowed_fetch_time)`. Dedup: a Bloom filter for "seen this exact URL" plus simhash/minhash for "seen this content before under a different URL." Content store: blob store keyed by URL hash. Metadata: `pages(url_hash, last_crawled, etag, priority_score)`.

**The design**
```
frontier (per-host queues) ──▶ fetcher pool (respects robots.txt + per-host delay)
     ▲                              │
     │                              ▼
     │                        parser (extract links, normalize URLs)
     │                              │
     └────── new links ◀── dedup filter (Bloom + simhash) ──▶ content store
```

**The hard part** — Politeness and prioritization at odds with each other at scale. Thousands of fetcher workers must never concurrently hammer one host, but a billion-URL frontier still needs a global sense of what to crawl next. The resolution: make each host's queue the unit of serialization for its own politeness budget (a per-host next-allowed-time gate), while a separate, cheap priority score (combining staleness and an importance signal) decides ordering *within* what's currently eligible — so politeness and prioritization are two independent, composable mechanisms rather than one tangled scheduler.

**Failure modes** — Crawler trap: a site generates infinite URLs (calendar pages, session-ID query strings), observable as one host's queue never draining and frontier size growing unboundedly from a single domain; fix with depth limits, URL normalization (strip session params), and a hard per-host budget. DNS resolution bottleneck: at fetcher-fleet scale, a shared or slow resolver becomes the actual throughput ceiling; fix with a local caching resolver pool per fetcher group. Slow or malicious servers holding connections open: aggressive per-request timeouts and a circuit breaker per host (see `T21-resilience-catalogue`) so one bad host can't tie up a disproportionate share of fetcher capacity.

**Follow-ups they will ask**
1. *How do you detect near-duplicate pages (mirrors, syndicated content, boilerplate)?* Simhash or minhash over shingled content, comparing Hamming distance against a threshold; exact-hash dedup only catches byte-identical copies, which is rare in practice.
2. *How do you decide recrawl frequency per page?* Estimate a per-page change rate from historical diffs and prioritize the frontier by staleness weighted by an importance signal (link count/PageRank-like score), not a fixed interval for every page.
3. *How does the frontier stay balanced across a billion URLs without one popular host starving everything else?* Partition frontier storage by host hash across many shards, enforce politeness locally within each shard, and let a lightweight global scheduler only assign priority scores rather than owning the full ordering.

---

### 7. Notification System
**Asked at:** Frequently framed as "design a multi-channel notification service" ([AlgoMaster, Notification Service](https://algomaster.io/learn/system-design-interviews/design-notification-service) — accessed 2026-08-01) · **Time:** 40 min

**Requirements** — FR: producer services enqueue a notification by template + params, fan out across the channels a user has enabled, respect preferences and quiet hours, expose delivery status. NFR: never double-send (a duplicate SMS is a real cost, not just annoyance), transactional notifications (OTP, password reset) need a tight latency SLO while bulk/marketing can lag. Clarifying questions: (1) "Is this a single latency class or does transactional vs. bulk need to be separated?" — this decision alone reshapes the whole queueing layer. (2) "What's the acceptable staleness for preference checks?" — decides whether you cache preferences or read-through every time. (3) "Which channels, and do their rate limits differ wildly?" — SMS providers cap far below push/email, and that gap is often the actual bottleneck. A fully worked numeric example of this exact design (10M users, cost modeling, dedup, priority lanes) is in `T10-design-method`'s Build-it-from-scratch section; this entry summarizes the destination.

**Scale** — 10M users × 5 notifications/day ≈ 500 notifications/sec average; a single campaign can burst to 10M sends over 30 minutes ≈ 5,500/sec, which typically exceeds SMS provider limits (often 100-500/sec per account) by an order of magnitude — the provider, not your infrastructure, is usually the real bottleneck.

**API**
```
POST /v1/notifications  { user_id, template_id, params, priority, dedup_key }
  → 202 { notification_id }
GET  /v1/notifications/{id}  → { status, attempts: [...] }
```

**Data model** — `notifications(id, user_id, template_id, priority, dedup_key, status)`; `attempts(notification_id, channel, attempt_no, status)` append-only; `dedup(dedup_key, channel) → sent_at` in Redis with a TTL exceeding the maximum retry/replay window.

**The design**
```
producer ──▶ ingest API ──▶ notifications.transactional topic (32 partitions)
                         └─▶ notifications.bulk topic (128 partitions)   ← separate lane
                                     │
                                     ▼
                          router worker: preference check → quiet hours → dedup
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              channel.push     channel.email      channel.sms  ← per-provider
              (near-unlimited) (SES/Sendgrid)      (100-500/s cap: THE bottleneck)
```

**The hard part** — Separating latency classes at the topic level, not just the worker level. If transactional and bulk notifications share one queue, a 10M-user marketing campaign puts a password-reset SMS behind millions of marketing messages, blowing the transactional latency SLO. The fix is architectural (separate topics/lanes), not a priority field on a shared queue, because a priority field still processes head-of-line in a single consumer group under load.

**Failure modes** — Dedup key TTL shorter than the maximum possible retry/replay window: a delayed-queue replay re-sends everything, which at SMS pricing is a real dollar cost, not just a UX blemish — this is the single most expensive bug class in this design. Router worker dies after the dedup check succeeds but before the channel enqueue: gap between "marked as deduped" and "actually sent," requiring either an outbox pattern (commit dedup and enqueue in one transaction) or a reconciliation sweep for stuck `queued` rows.

**Follow-ups they will ask**
1. *How is `Idempotency-Key` different from `dedup_key` here?* Idempotency-Key protects against the same HTTP call being retried by a flaky client; `dedup_key` protects against two different producers (or two code paths in one producer) both deciding to send the "same" logical notification.
2. *Why not a single priority field instead of separate topics?* A shared consumer group still processes roughly in arrival order under load; separate topics with separate consumer pools give you a hard latency isolation guarantee a priority field cannot.
3. *How do you handle a channel provider being down?* Circuit breaker per provider (see `T21-resilience-catalogue`), fallback to a secondary channel for transactional messages only (a password reset can fall back from SMS to email; a marketing blast should not fail over, it should just wait).

---

### 8. News Feed
**Asked at:** A Meta staple, reported as "design Facebook Newsfeed" or "design Instagram" ([Exponent, Meta System Design](https://www.tryexponent.com/blog/meta-system-design-interview), [ByteByteGo, News Feed](https://bytebytego.com/courses/system-design-interview/design-a-news-feed-system) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: post content, follow/unfollow, read a merged feed of followed accounts' posts. NFR: read-heavy (feed opens vastly outnumber posts), read latency dominates the SLO, eventual consistency on propagation is acceptable (a follower seeing a new post a few seconds late is fine). Clarifying questions: (1) "Chronological or ranked?" — ranked kills naive precomputation and pulls in a scoring service (`T10-ml-designs`). (2) "What's the follower-count distribution — any accounts with tens of millions of followers?" — this single answer decides fanout-on-write vs. hybrid. (3) "Retention window for the feed?" — decides materialized-feed storage cost.

**Scale** — 50M DAU × 10 feed opens/day ≈ 5×10⁸ reads/day ≈ 5,000 QPS average, ×3 peak ≈ 15,000 QPS. 50M DAU × 1 post/day ≈ 500 writes/sec average. With fanout-on-write and an average of 500 followers per account, amplified writes ≈ 500 × 500 = 250,000 timeline inserts/sec — the number that actually sizes the architecture, not the small API-level write rate. (Full derivation in `T10-design-method`.)

**API**
```
POST /v1/posts { text }              → 201 { post_id }
GET  /v1/feed?cursor=&limit=20        → 200 { items[], next_cursor }   cursor, not offset
POST /v1/follows { target_user_id }   → 202                            async fanout
```

**Data model** — `timeline(user_id, created_at DESC, post_id)` partitioned by `user_id`, capped at ~800 entries per user and TTL'd, because at 40 bytes/row and 250k inserts/sec this table is the write-amplified hot path and must stay bounded. `follows(follower_id, followee_id)` plus an inverted index on `followee_id`, because fanout needs "who follows X," the reverse of the natural partition key.

**The design**
```
post write ──▶ Postgres (posts) ──▶ Kafka post.created ──▶ fanout worker
                                                               │
                              < 10k followers: fanout-on-write │  > 10k followers:
                              ──▶ Redis ZSET per follower ◀────┘  fanout-on-read,
                                                                    merge at query time
feed read ──▶ Redis ZSET (hit ~95%) ──▶ Postgres/Cassandra (cold fallback)
```

**The hard part** — The celebrity problem: fanout-on-write for an account with 50M followers means 50M writes for a single post, which at 40 bytes/row is 2 GB of writes and minutes of propagation lag. The production answer is hybrid — fanout-on-write below a stated follower threshold (10,000 is a reasonable, explicitly tunable line), fanout-on-read above it, merged into the requester's feed at query time from a small per-celebrity cache.

**Failure modes** — Redis timeline shard restarts cold: thundering herd as every follower of every user on that shard misses simultaneously, observable as a Cassandra/Postgres QPS spike and a timeout cascade in the read tier; mitigated with request coalescing (single-flight per key) and a jittered warm-up, not just "the cache refills." Kafka consumer lag on the fanout topic: new posts appear in feeds minutes late, observable directly as a climbing consumer-lag metric; alert on lag, not on raw throughput.

**Follow-ups they will ask**
1. *Why cursor pagination instead of offset?* Offset pagination on an insert-heavy list skips or duplicates rows as new items shift the window underneath a paging client; an opaque cursor encoding `(created_at, post_id)` doesn't have this problem.
2. *How do you rank instead of showing strict reverse-chronological?* That's a separate scoring service consuming engagement features, covered in `T10-ml-designs`; this design's storage and fanout layer is agnostic to whether the final ordering is chronological or a ranking score, as long as the read path can fetch a candidate set before ranking.
3. *What if read:write flips to 2:1 instead of 100:1?* Precomputed fanout-on-write stops paying for itself (you're doing 250k inserts/sec to serve a read rate only twice as high); switch to read-time merge across the follow set with a short-TTL cache, dropping the materialized timeline entirely.

---

### 9. Chat / Messaging System
**Asked at:** A near-universal FAANG prompt, framed as "design WhatsApp" or "design Slack" ([Hello Interview, WhatsApp](https://www.hellointerview.com/learn/system-design/problem-breakdowns/whatsapp) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: send/receive 1:1 and group messages, deliver in real time when online, queue for delivery when offline, per-conversation ordering. NFR: at-least-once delivery with client-side dedup, ordering per conversation (not global), presence and typing indicators are best-effort, not durable. Clarifying questions: (1) "What are the delivery-guarantee tiers — sent/delivered/read, and does each need to be durable?" (2) "Group size ceiling?" — a 5-person group and a 500-person group are different fanout problems. (3) "Multi-device per account?" — changes whether "delivered" means one device or all of a user's devices.

**Scale** — 1B users, 100B messages/day ≈ 1.15M messages/sec average, ×3 peak ≈ 3.5M/sec.

**API** — Primarily a persistent connection (WebSocket), not REST: `SEND {conversation_id, client_msg_id, content} → ACK {server_msg_id, seq_no, ts}`; ordering is by server-assigned `seq_no` per conversation, dedup by client-supplied `client_msg_id`.

**Data model** — `messages(conversation_id, seq_no, sender_id, content, ts)` partitioned by `conversation_id` (all reads for a conversation are single-partition, in order). `connection_registry(user_id → gateway_node)` in Redis, updated on connect/disconnect, is the routing table that lets any gateway find where a recipient is actually connected.

**The design**
```
sender ──WS──▶ gateway A ──▶ message service: write durable, assign seq_no
                                    │
                        lookup connection_registry[recipient] ──▶ gateway B
                                    │                                │
                        if online: push over gateway B's WS ◀────────┘
                        if offline: leave in durable per-user queue + push notification
```

**The hard part** — Routing a message to whichever of thousands of stateful gateway nodes currently holds the recipient's live connection, and handling the recipient reconnecting to a *different* node mid-flight. The connection registry (a fast, frequently-updated key-value lookup, not a durable database) is the load-bearing piece; a message that can't find a live connection falls back to a durable per-user queue that's drained on the recipient's next connect, which is also what makes offline delivery work at all.

**Failure modes** — Gateway node crash: every connection it held drops simultaneously, and all those clients reconnect at once — a thundering-reconnect storm that needs backoff-with-jitter on the client and connection draining (stop routing new connections to a node before killing it) during planned deploys. Group chat fanout for a 500-person group: identical amplification math to the news feed's celebrity problem, and the fix is the same pattern (a dedicated fanout worker, not inline fanout on the send path).

**Follow-ups they will ask**
1. *How do you guarantee ordering with at-least-once delivery?* A server-assigned monotonic `seq_no` per conversation at write time; the client dedups by `client_msg_id` and orders display by `seq_no`, never by receipt order, which is not guaranteed under retries or multi-path delivery.
2. *How do read receipts scale for a 500-person group without 500× write amplification per message?* Don't write a row per (message, reader); store `last_read_seq_no` per (user, conversation) and derive "read by N people" from a range comparison, updated on the read event rather than the send event.
3. *How does presence scale to a billion users without broadcasting to everyone?* Presence updates only go to users who currently have that contact's chat open or visible — a subscription model, not a global broadcast, which is the same "don't fan out to everyone by default" instinct as the news feed's celebrity threshold.

---

### 10. Search Autocomplete
**Asked at:** Reported at Google and Meta as a "typeahead" prompt ([Exponent, Meta System Design](https://www.tryexponent.com/blog/meta-system-design-interview) — accessed 2026-08-01) · **Time:** 35 min

**Requirements** — FR: given a prefix, return the top-k completions ranked by popularity within tens of milliseconds. NFR: extremely low read latency (this is called on every keystroke), very high QPS relative to the underlying search volume, eventual freshness is fine (hourly/daily rebuild). Clarifying questions: (1) "Global suggestions or personalized?" — personalization needs a per-user overlay, not a per-user trie. (2) "Typo tolerance required?" — a fuzzy layer is materially more expensive than exact-prefix and should not run on every keystroke. (3) "How fresh must trending queries be?" — decides whether a real-time overlay is in scope.

**Scale** — 500M searches/day, each triggering roughly 5 keystroke-level autocomplete calls ⇒ ~30,000 QPS on the autocomplete endpoint alone, far exceeding the underlying search QPS.

**API** — `GET /v1/autocomplete?q=<prefix>&limit=10 → [{text, score}]`.

**Data model** — A trie built offline from query logs, where every node caches its own top-k completions (not just the terminal nodes), computed bottom-up during construction by merging each node's children's top-k with its own frequency.

**The design**
```
query logs (batch, hourly) ──▶ trie builder (bottom-up top-k merge per node)
                                      │
                                      ▼
                          sharded in-memory trie service (shard by hash of prefix)
                                      ▲
GET /autocomplete?q= ─────────────────┘   O(prefix length) read, not a subtree scan
```

**The hard part** — Precomputing top-k at every node so the online read is O(prefix length) rather than a scan of a potentially huge subtree. This trades a heavier, batch-only offline build (each node's top-k is a small heap merge of its children's top-k lists plus its own terminal frequency) for an online read that's essentially free.

**Failure modes** — Staleness: a genuinely trending query won't appear until the next rebuild, which for breaking news is unacceptable; the fix is a real-time overlay (a Redis sorted set of the last hour's query counts) blended with the precomputed trie at read time, with a decay function so old spikes fade. Shard skew: naive sharding by first character overloads whatever shard holds common prefixes ("a" gets vastly more traffic than "z"); shard by a hash of the prefix instead, or rebalance ranges based on observed traffic.

**Follow-ups they will ask**
1. *How do you personalize without building a trie per user?* Blend the global trie's top-k with a small per-user recent-searches list at read time, rather than maintaining per-user index structures.
2. *How do you handle typos?* A separate, more expensive fuzzy layer (edit-distance index or phonetic bucketing) invoked only when the exact-prefix trie returns too few results — never run fuzzy matching on every keystroke by default.
3. *What's the actual staleness window for a breaking-news query?* Whatever the rebuild interval is (hourly is typical) unless you add the real-time overlay described above; state the tradeoff explicitly rather than assuming freshness you haven't built.

---

### 11. Video Streaming
**Asked at:** A generic FAANG-scale prompt, framed as "design YouTube" or "design Netflix" ([ByteByteGo, Design YouTube](https://bytebytego.com/courses/system-design-interview) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: upload video, transcode into multiple resolutions/bitrates, stream adaptively, serve globally with fast startup. NFR: enormous storage and bandwidth, cost dominated by egress (this is the design where "add a CDN" is not optional flavor, it's the entire cost model), high availability. Clarifying questions: (1) "Live or VOD (video on demand)?" — live removes the option to transcode the whole file in parallel ahead of time. (2) "DRM required?" — changes the delivery pipeline meaningfully. (3) "Global audience, or one region?" — decides multi-CDN and origin-shield design.

**Scale** — Assume 10 hours of video uploaded per minute (a mid-scale reference point), ~1 GB/hour raw ⇒ 10 GB/min raw ingest. Each video is transcoded into ~5 renditions, multiplying total stored bytes even after compression gains. On the read side, at scale the CDN is expected to absorb the overwhelming majority of egress via cache hits; origin bandwidth is the exception path, not the norm.

**API**
```
POST /v1/videos          (resumable/multipart upload)  → { video_id, upload_url }
GET  /v1/videos/{id}/manifest  → HLS/DASH manifest listing available renditions
```
Playback clients fetch segments directly from the CDN, not through the API.

**Data model** — `videos(video_id, owner, status, duration)`; `renditions(video_id, resolution, bitrate, codec, cdn_path)`. Metadata in a relational store; actual segments in an object store fronted by a CDN.

**The design**
```
upload ──▶ object store (raw) ──▶ transcode job queue ──▶ parallel workers (per rendition,
                                                             GOP-aligned chunks)
                                                                  │
                                                                  ▼
                                              segmented output (HLS/DASH, ~6s segments)
                                                                  │
                                                                  ▼
                                    origin store ──(pull-through, first request)──▶ CDN
```

**The hard part** — Making transcoding parallelizable rather than a serial bottleneck. Splitting the source at GOP (group-of-pictures) boundaries lets independent workers transcode chunks concurrently and reassemble into the final segmented output, which is the difference between a 2-hour 4K video taking longer than its own runtime to transcode versus a few minutes on a large enough worker pool.

**Failure modes** — Transcode worker crash mid-job: checkpoint completion per chunk, resume only the failed chunks rather than restarting the whole video. Newly popular video causing a cache-miss storm before CDN propagation catches up: an origin-shield layer, or proactive pre-warming for known high-profile uploads (a scheduled premiere), addresses this before it becomes an incident. Regional CDN outage: multi-CDN failover with client-side fallback to a secondary CDN URL in the manifest.

**Follow-ups they will ask**
1. *Why segment into small chunks instead of streaming one file?* Enables adaptive bitrate switching mid-playback based on measured client bandwidth, and fine-grained CDN caching/seeking without re-downloading the whole asset.
2. *Do you pre-generate every rendition for every video?* No — pre-generate the popular tier (e.g., 480p/720p/1080p) always; generate 4K/8K or unusual codecs on first request and cache, since most views never need the largest rendition (a long-tail cost optimization).
3. *How does live streaming change this design?* There's no complete source file to chunk-parallelize; transcoding must be real-time, single-pass per bitrate rung, with a latency budget of a few seconds end to end, and CDN caching becomes short-TTL rolling segments instead of a permanent cacheable asset.

---

### 12. Google Drive / File Sync
**Asked at:** A common infra/product-flavored prompt, framed as "design Dropbox" ([Dropbox Tech Blog, Magic Pocket](https://dropbox.tech/infrastructure/inside-the-magic-pocket) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: upload/download files, sync across devices, folder hierarchy, sharing, versioning. NFR: durability above all (never silently lose a file), bandwidth efficiency (never re-transfer unchanged bytes), support for large files. Clarifying questions: (1) "Is real-time collaborative editing in scope?" — if yes, that's a different design (see #23); this one assumes file-level sync, not character-level merge. (2) "Offline editing support required?" — decides whether conflict resolution is a core requirement or an edge case. (3) "Max file size?" — decides whether chunked upload is mandatory.

**Scale** — 500M users, average 5 GB stored/user ⇒ 2.5 EB total logical storage before replication/erasure-coding overhead, which multiplies the physical footprint substantially.

**API**
```
POST /v1/files      (chunked, resumable upload)  → { file_id, version }
GET  /v1/files/{id}?version=
GET  /v1/changes?cursor=                          delta sync, not a full listing
```

**Data model** — Content-addressed block store: `blocks(block_hash PK, ref_count)`. `file_blocks(file_id, version, block_hash, sequence)` maps a file version to its ordered chunk list. This is a deliberate example of pattern 4 (content-addressed dedup storage) at the block level rather than the whole-file level.

**The design**
```
client chunker: split file into blocks (fixed-size or content-defined),
                hash each block, diff against server's known-block index
                          │
              upload only NEW blocks ──▶ object store
                          │
              commit new file_blocks version pointer
                          │
              other devices notified via long-lived per-user channel
                          │
              pull delta: GET /changes?cursor= → only the blocks they're missing
```

**The hard part** — Making the unit of sync the *changed block*, not the changed file. Without block-level dedup, a one-byte edit to a 4 GB file re-uploads and re-downloads the entire 4 GB on every device, which is precisely the failure that pushed Dropbox toward custom, content-addressed storage infrastructure.

**Failure modes** — Sync conflict from two devices editing offline and reconnecting: never silently pick one and drop the other; fork a "conflicted copy" (Dropbox's actual documented behavior) so no data is lost, and let the user reconcile manually. Partial upload interrupted mid-transfer: resumable protocol keyed on which blocks are already acknowledged, so a reconnect resumes rather than restarts. Block garbage-collected while a file still references it: reference-count every block and only GC at count zero, with a grace period to protect against races with in-flight commits.

**Follow-ups they will ask**
1. *How does the client know what changed without scanning the whole filesystem?* Local filesystem watch APIs (inotify/FSEvents) plus a server-side delta/cursor endpoint, so a reconnecting client asks "what changed since cursor X" instead of diffing the entire tree.
2. *Can you dedupe across different users uploading the same file?* Yes at the block level, since the hash is the key regardless of owner — but note the privacy wrinkle: cross-user dedup on content hash alone can leak "someone else already has this exact file" via response timing, so production systems often scope dedup within an account or add additional checks.
3. *How do you make large uploads reliable over flaky connections?* Chunked resumable upload (the same shape as the tus protocol or S3 multipart upload): each chunk independently retryable and hash-verified before the final commit.

---

### 13. Ticket Booking (the double-booking problem)
**Asked at:** Framed as "design Ticketmaster" or "design a movie ticket booking system," explicitly testing concurrency correctness under contention ([Hello Interview, Ticketmaster](https://www.hellointerview.com/learn/system-design/problem-breakdowns/ticketmaster), [Benjamin Dickman, The Double Booking Problem](https://benjamindickman.com/blog/system-design-interview-the-double-booking-problem/) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: browse seats, place a temporary hold, complete purchase, release the hold on timeout or cancellation. NFR: correctness (never sell the same seat twice) matters more than raw throughput on the booking path itself; the system must survive an extreme, brief burst at on-sale time far above steady-state traffic. Clarifying questions: (1) "Assigned seating, or general admission with a quantity?" — general admission is a simpler counter-decrement problem, not per-seat CAS. (2) "How long should a hold last?" — a real tradeoff between checkout friction and seat availability. (3) "Do we need a virtual waiting room for flash-sale traffic?" — if yes, the booking service is never the front door; the waiting room is.

**Scale** — A popular on-sale event can see 100,000 concurrent users competing for 20,000 seats within seconds — a spike two to three orders of magnitude above steady-state, meaning the design problem is admission control in front of the booking service, not scaling the booking service itself.

**API**
```
POST /v1/holds { event_id, seat_ids[] }     → 201 { hold_id, expires_at } | 409 (seat taken)
POST /v1/bookings { hold_id, payment_token } → 201 { booking_id }
DELETE /v1/holds/{hold_id}                   → 204
```

**Data model** — `seats(event_id, seat_id, status, hold_id, hold_expires_at)`, PK `(event_id, seat_id)`, partitioned by `event_id` — all contention for one sale is within a single event, so partitioning by event keeps the hot compare-and-swap traffic together where it can be reasoned about and provisioned for, rather than scattered and still globally contended.

**The design**
```
client ──▶ waiting room (token-bucket admission, protects everything downstream)
              │
              ▼
        hold service: atomic CAS on seat status (Redis Lua script or
        `UPDATE ... WHERE status='available'` with affected-row check)
              │
     success ─┴─ failure (409, seat already taken)
              ▼
        TTL timer (hold expires in 5-10 min if not confirmed)
              │
     payment (async, outside the lock) ──▶ confirm: held → sold
```

**The hard part** — The seat-status transition must be atomic under extreme concurrent contention for the *same small set of rows*. A naive `SELECT status; if available, UPDATE` is a textbook read-then-write race: two concurrent requests both observe "available" and both proceed to hold the same seat. The fix is always an atomic conditional write — `UPDATE seats SET status='held' WHERE seat_id=? AND status='available'` with an affected-row-count check, or the Redis Lua CAS shown in this module's "Build it from scratch" section — never a read followed by a separate write.

**Failure modes** — Hold service crashes after marking a seat held but before returning the `hold_id` to the client: the client's retry must be recognized as the same logical request via an idempotency key, not treated as a fresh attempt that fails against a seat "already held by itself." TTL expiry racing payment completion: re-validate the hold inside the same transaction that confirms payment, and design the tiebreak to favor honoring a payment that lands a few hundred milliseconds late (with a refund path as the fallback) over losing a completed sale. Payment succeeds but the booking-confirm write fails: the classic distributed-transaction gap, closed with a durable outbox (record "payment succeeded, must confirm" before telling the payment provider you're done) plus a reconciliation job that finds and fixes mismatched pairs.

**Follow-ups they will ask**
1. *How do you stop bots from grabbing every seat in a flash sale?* A waiting room with proof-of-work or CAPTCHA at entry, per-account/per-IP hold limits, and randomized (not strict FIFO) admission, since strict FIFO is exactly what a faster bot exploits.
2. *Why partition by `event_id` rather than by a hash of `seat_id`?* All the contention for a given sale is scoped to one event; keeping it on one shard means you can provision and reason about exactly that hot shard during a known on-sale time, instead of spreading (and still fully contending) the same load across many shards.
3. *What breaks if the hold TTL is too long or too short?* Too long: seats sit locked while a distracted user abandons checkout, starving genuine buyers during a sale — the most common real complaint. Too short: users lose their seat mid-checkout on a slow payment form. Typical is 5-10 minutes with a visible countdown, plus a background sweep of expired holds.

---

### 14. Payment System (idempotency, exactly-once illusions)
**Asked at:** A Stripe-style prompt explicitly reported to separate senior from staff candidates ([Medium/T3CH, The Stripe System Design Question](https://medium.com/h7w/the-stripe-system-design-question-that-separates-senior-from-staff-engineers-ecb9a98af1fd), [Stripe Docs, Idempotent Requests](https://docs.stripe.com/api/idempotent_requests) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: charge a payment source, refund, ingest processor webhooks, maintain an auditable ledger. NFR: correctness above throughput (never double-charge, never lose a charge), full auditability, and the system must interoperate correctly with an external network it does not control and cannot roll back. Clarifying questions: (1) "Are we the merchant-facing API (Stripe's position) or a merchant calling someone else's payment API?" — changes who owns the idempotency contract. (2) "Synchronous auth+capture, or async settlement?" — changes the latency SLO on the write path materially. (3) "Multi-currency?" — affects the ledger's unit-of-account design.

**Scale** — Assume 500 payments/sec average, 2,000/sec peak, 5-year retention at ~1 KB/transaction ⇒ roughly 500 × 86,400 × 365 × 5 × 1 KB ≈ 79 TB of transaction history, before replication.

**API**
```
POST /v1/charges  { amount, currency, source }
  headers: Idempotency-Key: <uuid>
  → 201 { charge_id, status }
POST /v1/refunds  { charge_id, amount }
POST /v1/webhooks/processor   (inbound, signature-verified)
```

**Data model** — `idempotency_keys(key PK, request_hash, response, status)` with a TTL well beyond any plausible client retry window; `charges(charge_id, amount, status, processor_ref)`; `ledger_entries(entry_id, account_id, charge_id, amount, direction, ts)`, append-only, double-entry.

**The design**
```
POST /charges (Idempotency-Key) ──▶ check idempotency_keys: seen+matching? return stored response
                                    seen+mismatched payload? 422
                                    unseen? continue
                                        │
                          write charges row, status=pending (durable, LOCAL txn,
                          BEFORE the network call — this line is the whole design)
                                        │
                          call payment processor (external, non-transactional)
                                        │
                    success/failure ────┴──── ambiguous timeout
                          │                          │
              update charge + ledger        reconciliation job polls processor
              in one local transaction      for ground truth, repairs local state
```

**The hard part** — There is no true exactly-once across a network boundary you don't control. What exists is: durably record intent before the external call (so a crash before the call is safely retryable from scratch), make the call, durably record the observed outcome, and run a reconciliation job that resolves every case where the outcome is ambiguous (a timeout with no confirmed response). Every payment system's correctness ultimately rests on that reconciliation job actually running and being tested against the ambiguous-timeout path specifically, not just the happy path.

**Failure modes** — Process crashes after the processor confirms success but before the local charge is marked succeeded: the client sees an error and may retry with the *same* idempotency key, which must eventually return the real (successful) result once reconciliation catches up — never silently double-charge on that retry. Processor returns an ambiguous timeout: never blind-retry with a fresh attempt against the network; query the processor's status for that idempotency key, or wait for the async webhook, before deciding anything. Ledger and charges table diverge: because the ledger is append-only and derived-from-events rather than mutated in place, a balance can always be replayed and recomputed, and drift shows up as a non-zero sum across paired entries rather than a silently wrong number.

**Follow-ups they will ask**
1. *`Idempotency-Key` vs. a business-level `dedup_key` — what's the difference?* `Idempotency-Key` protects against the same HTTP call being retried by a client after a network blip; a `dedup_key` (e.g., "invoice #123's payment") protects against two *different* callers or code paths independently deciding to charge the same logical thing, which an HTTP-level key on two separate requests can't catch.
2. *Why double-entry bookkeeping instead of a single mutable balance column?* A single balance loses the audit trail and turns concurrent updates into a lost-update race; append-only double-entry makes balance a sum-over-events (always recomputable) and turns a bug into a detectable non-zero sum rather than a silently corrupted number.
3. *How do you test this without charging real cards?* Processor sandbox/test-mode keys with deterministic test card numbers simulating success/decline/timeout, with chaos-testing specifically aimed at the ambiguous-timeout-then-reconciliation path, since that's both the hardest to exercise naturally and the most likely to be wrong.

---

### 15. Ride Hailing
**Asked at:** A generic large-scale geospatial prompt, framed as "design Uber" or "design Lyft" ([DesignGurus, Uber system design](https://www.designgurus.io) — accessed 2026-08-01) · **Time:** 45 min

**Requirements** — FR: request a ride, match to a nearby available driver, track the trip in real time, calculate fare, handle cancellation. NFR: matching latency in seconds, extremely high write throughput for continuous location updates, geographic partitioning is load-bearing, surge pricing must respond quickly to sudden imbalance. Clarifying questions: (1) "How often does a driver's location update?" — this single number decides whether location ingestion or matching is the actual throughput problem. (2) "What's the matching radius/expansion policy?" (3) "Is dynamic pricing (the ranking/pricing model itself) in scope, or just the matching mechanics?" — the pricing *model* belongs in `T10-ml-designs`; this design covers the matching and location-serving mechanics only.

**Scale** — 5M active drivers pinging location every 4 seconds ⇒ 1.25M location updates/sec. Matching requests: 100k rides/hour at metro peak ⇒ ~28/sec — trivially small next to location ingestion, which is the real throughput problem in this design, not matching.

**API**
```
POST /v1/drivers/{id}/location { lat, lng, ts }     high-frequency, overwrite not append
POST /v1/rides { pickup, dropoff }  → { ride_id, status: matching }
```
Ride status and live driver location during a trip are pushed over a persistent connection, not polled.

**Data model** — Current driver location lives in an in-memory, geo-partitioned store (Redis with geohash/H3 cell keys) that is **overwritten** on every ping, never appended — this is deliberately not a durable, indexed, row-store table, because that write rate would drown any conventional database. Historical trip data (for billing/analytics) is a separate, much-lower-rate, durable, append-only store, written once per trip rather than once per location ping.

**The design**
```
driver app ──▶ location ingest ──▶ geo-index (partitioned by H3 cell, overwrite-only)
                                          ▲
rider request ──▶ matching service ───────┘ query nearby cells, expanding rings
                        │
                  score candidates (ETA, rating) ──▶ offer top driver, short accept
                  timeout, cascade to next on decline/timeout
```

**The hard part** — The location-update write rate (over a million per second) must never touch a durable, replicated, indexed database in the naive way. Current-location state belongs in an in-memory, geo-partitioned, overwrite-only store, entirely decoupled from the durable trip-history writes that happen at a rate orders of magnitude lower. "Just use Postgres with a geo index" is the wrong answer here specifically because of the write volume, even though it's exactly the right answer for the much lower-volume ride and fare records in the same system.

**Failure modes** — A geo-index shard goes down: drivers in that region become invisible to matching, but because the index is a cache of recent pings (rebuildable from the next wave of pings within seconds), replication here is about matching continuity, not data durability. Driver accepts a ride but the confirmation doesn't propagate before the app goes offline: matching timeout triggers an automatic cascade to the next-best driver rather than blocking the rider indefinitely. Surge computation lagging a sudden demand spike (a concert letting out): computed on a short rolling window per cell, not a slow batch job, because riders seeing a stale, too-low price at exactly the moment supply is tightest worsens the shortage rather than correcting it.

**Follow-ups they will ask**
1. *Why geohash/H3 cells instead of a naive lat/lng range query?* A raw range query on lat/lng needs a genuine 2D spatial index (R-tree/quad-tree) or degrades to a scan; geohashing/H3 collapses 2D proximity into a 1D string/integer prefix match, so "nearby" becomes a cheap lookup of a handful of cells that even a plain key-value store can serve, with cell size as the tunable accuracy/cost knob.
2. *How do you avoid offering a ride to a driver who just accepted another one (a race between two riders and one driver)?* An optimistic compare-and-swap on driver status (`available → pending_offer`), so only one offer can be outstanding for a driver at a time — the exact same atomic-CAS pattern as the ticket-booking seat hold.
3. *How does matching change during a sudden supply/demand imbalance?* Expand the search radius progressively in rings of cells rather than fixing a radius, and let surge pricing pull in drivers who would otherwise not bother repositioning — price as a supply-elasticity lever, not only a revenue mechanism.

---

## The 10 compact designs

*These get the same eight headers, compressed. Depth on these ten is lower by design; the deep 15 above cover the interview time budget more realistically.*

### 16. Proximity Service
**Asked at:** Framed as "design Yelp" or "design a nearby-search feature." · **Time:** 30 min
**Requirements** — Search businesses/places near a location, filterable by category. Read-heavy, and unlike ride-hailing, the underlying data barely moves (businesses don't relocate every 4 seconds). Clarifying: how often does the dataset change; radius default and max; ranking beyond distance?
**Scale** — 10M points of interest, 50k QPS search, mostly reads.
**API** — `GET /v1/search?lat=&lng=&radius_km=&category=`.
**Data model** — Geo-indexed store keyed by geohash/H3 cell; since data is largely static, a heavier index (PostGIS R-tree, or Elasticsearch geo-query) is affordable in a way it is not for ride-hailing's overwrite-every-4-seconds workload.
**The design** — `client → search API → geo index (cell lookup, expand rings if sparse) → hydrate from POI metadata DB → rank by distance + business score`.
**The hard part** — The decision point is precisely the mirror of ride-hailing: because writes are rare, you can afford a durable, indexed, more feature-rich geo store instead of an overwrite-only cache, and the interview signal is knowing *why* the two designs differ despite looking similar on the surface.
**Failure modes** — Stale POI data (closed business still showing) — mitigated with a freshness SLA and owner/user-reported flags, not real-time sync. Sparse regions returning zero results within the default radius — expanding-ring search, same pattern as ride-hailing.
**Follow-ups** — (1) Why not the ride-hailing overwrite-only store here? Because write volume is low, so durability and richer query features are affordable. (2) How do you rank beyond raw distance? Blend distance with a static popularity/rating score. (3) How do you keep the index fresh as businesses update hours/close? Async pipeline off the write path, not synchronous with every read.

### 17. Hotel Reservation
**Asked at:** Framed as "design a hotel booking system," reported as a common Exponent/interview-guide variant ([Exponent, Hotel Booking Service](https://www.tryexponent.com/blog/design-a-hotel-booking-service-system-design-interview-question-answer) — accessed 2026-08-01). · **Time:** 35 min
**Requirements** — Search availability across a date range, hold, book, cancel. The core difference from ticket booking: inventory is a *count per room-type per night*, not an individually identified seat, and a booking spans a range of nights, not one instant.
**Scale** — 10k hotels × 100 rooms × 365 nights of inventory rows to check per search; must not be a live range-scan per request.
**API** — `GET /v1/hotels/{id}/availability?checkin=&checkout=`, `POST /v1/holds`, `POST /v1/bookings`.
**Data model** — Pre-materialized `inventory(hotel_id, room_type, date, available_count)` per night, decremented atomically on hold — avoids computing availability from a raw bookings table by scanning a date range on every search.
**The design** — `search → read pre-materialized per-night counts across the range → all nights available? → atomic decrement across the range (multi-row CAS, needs a transaction) → hold → confirm/expire`.
**The hard part** — The atomic operation isn't a single-row CAS like a seat hold; it's a multi-row conditional decrement across every night in the stay, which needs a real transaction (or a Lua script iterating the range) so a partial success (nights 1-2 succeed, night 3 fails because just sold out) never leaves a half-booked stay.
**Failure modes** — Overbooking from a race across the date range if the multi-night decrement isn't transactional — same class of bug as the ticket-booking read-then-write race, just spread across more rows. Hold TTL expiring mid-multi-night-checkout leaving a partially-held range — release the whole range atomically, never per-night.
**Follow-ups** — (1) Why pre-materialize per-night counts instead of deriving from bookings live? A live derivation is a range scan and aggregation on every search, which doesn't hold up at 10k hotels × real QPS. (2) How do you handle overbooking policy (hotels intentionally overbook)? Add a configurable overbook buffer to the count rather than treating it as a bug. (3) What changes for a multi-room booking? The same range-decrement problem, just across rooms and nights simultaneously — the transaction scope grows, the pattern doesn't change.

### 18. Distributed Job Scheduler
**Asked at:** Framed as "design a distributed cron" or "design Airflow." · **Time:** 35 min
**Requirements** — Schedule jobs to run at specific times/intervals, ensure exactly one execution per scheduled instance despite a scheduler fleet, handle catch-up after an outage. Clarifying: is at-least-once with idempotent jobs acceptable, or must it be exactly-once; what's the catch-up policy after downtime (backfill every missed run, or skip to now)?
**Scale** — 1M scheduled jobs, most running hourly/daily, so scheduler throughput itself is modest; the hard part is correctness under a multi-node scheduler, not raw QPS.
**API** — `POST /v1/jobs {cron_expr, target}`, internal: workers `CLAIM` ready jobs.
**Data model** — `jobs(job_id, cron_expr, next_run_at)`; `job_runs(job_id, scheduled_for, status)` with a unique constraint on `(job_id, scheduled_for)` so a claim is a conditional insert, not a flag flip.
**The design** — `scheduler leader (elected via etcd/ZK) scans jobs where next_run_at <= now → enqueues run → workers CLAIM via unique-constraint insert on (job_id, scheduled_for) → execute → mark done, compute next_run_at`.
**The hard part** — Preventing double-firing when multiple scheduler instances exist for availability. Leader election picks one active scanner at a time, but the actual safety net is the unique constraint on `(job_id, scheduled_for)` at claim time — even a brief split-brain during leader failover can't produce two successful runs of the same scheduled instance, because the second claim attempt fails the constraint.
**Failure modes** — Scheduler down for an hour: on recovery, does it fire every missed hourly run (backfill) or just the next one (skip)? This must be an explicit, stated policy per job, not an accident of however the recovery code happens to behave. Worker claims a job then crashes before executing: a claim needs a lease/heartbeat so an abandoned claim is detected and requeued, not silently lost.
**Follow-ups** — (1) How does leader election prevent double-scanning? Only the elected leader scans for due jobs; followers stand by, so at most one process is looking for work at a time (belt), backed by the unique-constraint claim (suspenders). (2) What's the tradeoff in catch-up policy? Backfill risks a thundering herd of a thousand missed runs firing at once on recovery; skip-to-now silently drops work — the right answer is job-specific and must be configured, not defaulted. (3) How do you scale beyond one scheduler's scan capacity? Shard jobs by a hash of `job_id` across multiple leader-elected scanner groups, each owning a disjoint job range.

### 19. Metrics / Monitoring System
**Asked at:** Framed as "design Datadog" or "design a time-series metrics platform." · **Time:** 35 min
**Requirements** — Ingest metrics (counters, gauges, histograms) from a large fleet, support alerting queries and dashboards over time ranges. Clarifying: push or pull ingestion; retention and downsampling policy; alerting latency requirement.
**Scale** — 1M hosts × 100 metrics × 1 sample/10s ⇒ 10M writes/sec ingestion, dwarfing query volume.
**API** — Push: `POST /v1/metrics {name, tags, value, ts}` (batched). Pull: agents expose `/metrics`, a central collector scrapes on an interval (Prometheus model).
**Data model** — Time-series store keyed by `(metric_name, tag_set_hash, timestamp)`, with downsampling rollups (raw for 24h, 1-minute rollups for 30 days, 1-hour rollups for a year) to bound storage growth.
**The design** — `agents → (push: ingest gateway; pull: scrape) → write buffer → time-series DB, sharded by metric+tag hash → downsampling job (compacts old raw data) → query/alerting layer`.
**The hard part** — Cardinality. Every unique combination of tags creates a new time series; an incautious tag (embedding a user ID or a request ID as a tag value) can multiply the number of series by orders of magnitude and take down the ingestion tier or blow out storage — this is the single most common real-world failure mode of every metrics system, not a theoretical concern.
**Failure modes** — Cardinality explosion: observable as ingestion latency climbing and the time-series index growing unboundedly from one bad deploy that tagged metrics by request ID; the fix is cardinality limits enforced at ingestion, not detected after the fact. Query hitting un-downsampled long-range raw data: a dashboard querying a year of raw 10-second data times out; the query layer must route to the appropriate rollup tier automatically based on the requested range.
**Follow-ups** — (1) Push vs. pull, and why does it matter? Pull (Prometheus-style) gives the collector control over load and makes "is this host even alive" trivial (a failed scrape is itself a signal); push (StatsD-style) suits ephemeral/serverless workloads that don't live long enough to be scraped. (2) How do you bound cardinality? Enforce a tag-value allowlist or cardinality budget per metric name at the ingestion gateway, rejecting or dropping tags that would blow the budget. (3) How does alerting stay fast over a large ingestion volume? Alerting typically runs on a much shorter, hot window of raw or near-raw data rather than querying the full historical store, decoupled from dashboard queries entirely.

### 20. Ad Click Aggregation
**Asked at:** Framed as "design an ad click counting/aggregation pipeline," a common infra-and-correctness prompt. · **Time:** 35 min
**Requirements** — Count ad clicks/impressions accurately enough to bill advertisers, with a real-time approximate view for dashboards. Clarifying: does the billing number need to be exact (usually yes) even if the dashboard is approximate; what's the reconciliation window?
**Scale** — 1M clicks/sec at peak across a large ad network; billing precision matters at this volume because a 1% error is real money.
**API** — Ingest: `POST /v1/events {ad_id, event_type, ts}` (internal, high volume). Query: `GET /v1/stats/{ad_id}?window=`.
**Data model** — Streaming layer: approximate distinct-click counts via HyperLogLog for dashboards (bounded memory, ~1-2% error). Batch layer: exact daily aggregation from raw event logs for the number that goes on the invoice.
**The design** — `event ingest → Kafka → (streaming: approximate aggregation, HyperLogLog, for live dashboards) and (batch: daily exact reconciliation job over the full raw log, for billing)`.
**The hard part** — Exactly-once counting in the presence of duplicate click events (a user double-clicking, a network retry re-sending the same event) directly determines advertiser billing accuracy; the interview tests whether you propose both a fast, approximate real-time path *and* a slower, exact batch path for the number that actually matters financially, rather than treating one number as sufficient for both purposes.
**Failure modes** — Streaming aggregation drifting from the batch-reconciled truth: expected and acceptable *if* the drift is bounded and disclosed (dashboards say "approximate"), but a batch/streaming divergence beyond the expected HLL error bound indicates a real bug (likely duplicate events not deduped) and should page someone. Late-arriving events (a click logged with a clock-skewed timestamp) landing after the daily batch has closed: a reconciliation/correction window (e.g., re-run the previous day's batch if late events exceed a threshold) rather than silently excluding them.
**Follow-ups** — (1) Why not just use the exact batch number everywhere? Batch jobs run on a delay (hours); dashboards need near-real-time numbers, which forces the approximate/exact split. (2) How do you dedupe a click that arrives twice? An idempotency key per click event (device + ad + timestamp bucket, or a client-generated event ID) checked against a short-TTL dedup store. (3) How do you detect click fraud in this pipeline? Out of scope for the counting pipeline itself, but the design should note it as a separate downstream consumer of the raw event log, not bolted onto the counting path.

### 21. Object Store (S3-like)
**Asked at:** Framed as "design a blob/object storage service," a systems-infra prompt distinct from designing a *feature* that uses one. · **Time:** 35 min
**Requirements** — Store and retrieve immutable objects by key, at exabyte scale, with configurable durability. Clarifying: is versioning required; what durability target (measured in nines); strong or eventual read-after-write consistency?
**Scale** — Exabyte-scale storage; durability targets in production object stores are commonly stated as eleven nines (99.999999999%) of annual object durability.
**API** — `PUT /bucket/{key}`, `GET /bucket/{key}`, `LIST /bucket?prefix=`.
**Data model** — Objects are immutable once written (a "put" of the same key is a new version, not a mutation) — this single property is what makes the rest of the design tractable: immutable data is trivially cacheable and replicable without coordination. Metadata (bucket/key namespace, ACLs) is a separate service and a separate scaling problem from the data plane that stores actual bytes.
**The design** — `client → metadata service (namespace, permissions, object location) → data plane (erasure-coded or replicated storage nodes) → object retrieved by content location, not re-derived per request`.
**The hard part** — Durability-vs-cost at exabyte scale: full replication (e.g., 3 copies) is simple but costs 3× storage; erasure coding (e.g., splitting an object into 10 data shards + 4 parity shards, tolerating any 4 shard losses) achieves comparable durability at roughly 1.4× overhead instead of 3×, at the cost of more complex reads (reconstructing from shards) and rebuild traffic when a shard is lost.
**Failure modes** — A storage node failure under pure replication: straightforward re-replication from a surviving copy. Under erasure coding: reconstructing a lost shard requires reading enough of the remaining shards to recompute it, which is more network- and CPU-intensive per failure but pays for itself in steady-state storage cost. Metadata service outage: even if the data plane is healthy, objects become unreachable because their location can't be resolved — the metadata service, despite storing a tiny fraction of the bytes, is often the more failure-sensitive component.
**Follow-ups** — (1) Why is immutability so central to this design? It removes the need for any write-coordination on reads — a cached or replicated copy is never stale because it never changes, which is not true of a mutable file. (2) Replication vs. erasure coding — when would you pick each? Replication for hot, small, frequently-read objects where simplicity and read locality matter; erasure coding for cold, large, infrequently-accessed data where storage cost dominates. (3) How does `LIST` stay fast over billions of keys? The metadata namespace is typically a separate, range-indexed store (not a scan of the data plane), often lexicographically ordered by key so prefix listing is a range query.

### 22. Distributed Cache
**Asked at:** Framed as "design Memcached/Redis Cluster," the cache itself as the subject rather than a component of another design. · **Time:** 30 min
**Requirements** — Get/set/delete with low latency, horizontal scale, and a defined eviction policy under memory pressure. Clarifying: write-heavy or read-heavy workload; is losing the cache on a node failure acceptable (usually yes, it's a cache); what consistency does the caller need with the source of truth?
**Scale** — Millions of keys per node, sub-millisecond latency target, sharded across dozens to hundreds of nodes.
**API** — `GET key`, `SET key value ttl`, `DEL key`.
**Data model** — Consistent hashing across nodes (same pattern as the distributed KV store, #4) to minimize redistribution on node add/remove; per-key TTL and an eviction policy (LRU or LFU) applied once memory pressure hits a configured ceiling.
**The design** — `client → hash(key) → shard → in-memory store, LRU/LFU eviction under memory pressure`, fronting a durable source of truth via one of three patterns: cache-aside (app reads/writes cache and DB separately), write-through (writes go to cache and DB synchronously), write-behind (writes go to cache immediately, DB asynchronously).
**The hard part** — Choosing the right read/write pattern for the failure mode you're willing to accept: cache-aside is simplest and tolerates a cold cache gracefully (just slower, falls through to DB) but risks momentary staleness between DB write and cache invalidation; write-through keeps cache and DB consistent at write time but adds write latency; write-behind is fastest but can lose the most recent writes if the node crashes before flushing to the durable store.
**Failure modes** — Node failure under cache-aside: no data loss, just a temporary cache-miss increase on that shard's keys — this is precisely why cache-aside is the default choice for most systems. Node failure under write-behind: the unflushed writes on that node are gone, which is only acceptable if the cached data is truly disposable. Thundering herd on a cold restart: identical to the news-feed and URL-shortener cache failure modes — request coalescing and jittered warm-up, the same fix every time this pattern appears.
**Follow-ups** — (1) LRU or LFU? LRU is simpler and handles recency-biased access well; LFU handles a workload with a stable set of "always hot" keys better but costs more to track frequency accurately, especially with decay. (2) Cache-aside, write-through, or write-behind, and why? Cache-aside by default; write-through when read-after-write consistency for cached data matters; write-behind only when write latency is the dominant concern and some data loss on crash is acceptable. (3) How do you avoid a hot key overwhelming one shard despite consistent hashing? Consistent hashing balances *key count*, not *traffic per key* — a genuinely hot single key still needs client-side replication of that specific key across multiple cache nodes or a local in-process cache layer in front of the distributed one.

### 23. Collaborative Editing (CRDT vs. OT)
**Asked at:** Framed as "design Google Docs" or "design real-time collaborative editing," reported specifically as a design where the algorithm choice is the whole interview ([SystemDR, CRDTs vs OT](https://systemdr.systemdrd.com/p/crdts-vs-operational-transformation) — accessed 2026-08-01). · **Time:** 40 min
**Requirements** — Multiple users edit the same document concurrently and converge to the same final state without conflicts. Clarifying: is offline/peer-to-peer editing required, or is a reliable central server assumed; does the data model need to support rich structures (tables, nested lists) or just flat text; what's the acceptable metadata overhead per edit?
**Scale** — A document with 50 concurrent editors, each producing an operation every keystroke (~1/sec), needs sub-100ms propagation to feel real-time.
**API** — `WS: SEND_OP {doc_id, op, base_version}`, server/peers broadcast the transformed or merged op.
**Data model** — OT: the document is a sequence with a central server maintaining the canonical operation order, and each client's operations are transformed against every operation that landed before them. CRDT: each character/element carries a unique, globally-ordered identifier (not just a position), so merges are commutative and associative by construction — any arrival order produces the same final state.
**The design (OT)** — `client → op (insert/delete at position) → central server (canonical order, transform against concurrent ops) → broadcast transformed op to all clients`.
**The design (CRDT)** — `client → op tagged with a unique ID → any peer (no central authority required) → merge function is mathematically guaranteed commutative/associative/idempotent → convergence without coordination`.
**The hard part** — This is the whole question: Google Docs uses OT because it already has a reliable, low-latency central server and OT gives a compact wire format, but transformation functions are notoriously hard to prove correct (real historical OT implementations have shipped convergence bugs). Figma and Notion use CRDTs because they need offline and peer-to-peer tolerance, mathematically guaranteed convergence with no central coordinator, at the cost of per-operation metadata overhead (tombstones for deleted elements, unique IDs per character) that OT doesn't need.
**Failure modes** — OT: a transformation function bug causes two clients to converge to *different* final documents, which is silent and severe (the historical motivation for CRDTs existing at all). CRDT: unbounded tombstone growth in naive implementations (deleted content that must be kept as a marker to preserve merge correctness) causing memory bloat on long-lived, heavily-edited documents — production CRDT implementations need a garbage-collection strategy for tombstones once all peers have acknowledged the deletion.
**Follow-ups** — (1) When would you choose OT over CRDT? When you control a reliable, low-latency central server and want a compact wire format and don't need offline editing — OT centralizes complexity into one well-tested server implementation rather than distributing it into every client's merge logic. (2) When would you choose CRDT? Offline-first or peer-to-peer requirements, or when you can't guarantee a central server is always the ordering authority. (3) What's the actual cost of CRDTs in production? Metadata overhead per character/element (unique IDs, tombstones) that can multiply document size several-fold versus the raw text, and needs an explicit GC strategy or it grows unboundedly.

### 24. Leaderboard
**Asked at:** Framed as "design a real-time gaming leaderboard," a common infra prompt testing whether Redis is applied naively or with an escape hatch for extreme scale. · **Time:** 30 min
**Requirements** — Update a player's score, retrieve global rank and nearby ranks, retrieve top-K. Clarifying: how many ranked entities (thousands vs. hundreds of millions); is exact global rank required for every entity or only near the top; update frequency per player?
**Scale** — 100M players, score updates at 50k/sec peak (e.g., a mobile game after a tournament ends).
**API** — `POST /v1/scores {player_id, score}`, `GET /v1/leaderboard/top?k=100`, `GET /v1/leaderboard/rank/{player_id}`.
**Data model** — Default answer: a Redis sorted set (`ZADD`, `ZRANK`, `ZRANGE`), giving O(log n) insert and O(log n + k) range reads. At true global scale (hundreds of millions of ranked entities), a single ZSET doesn't shard cleanly because rank is inherently a global property — the fix is a two-tier design: shard players into buckets with locally exact scores, and periodically merge each shard's local top-K into a globally accurate top-K, accepting that *exact* global rank is only cheap and precise near the very top of the leaderboard.
**The design** — `score update → shard by player_id hash → local Redis ZSET per shard (exact within shard) → periodic merge job aggregates each shard's top-K into a global top-K cache → GET requests read the merged cache for "top," or query the owning shard directly for a specific player's local rank plus an approximation of global rank`.
**The hard part** — The single-node ZSET is the "obviously correct" answer that stops working exactly at the scale the interviewer is probing for. Recognizing that global rank across sharded data is fundamentally an aggregation problem — not a lookup — and that exact rank for the 90-millionth player is rarely a real product requirement (only the top-K and "your own rank" usually matter) is the actual signal being tested.
**Failure modes** — A single global ZSET under write load at 50k/sec: the sorted set becomes a single-threaded hot spot (Redis is single-threaded per key operation), observable as write latency climbing under tournament-end load spikes; sharding is the fix, at the cost of only-approximate global rank between merge cycles. Merge job falling behind: global top-K becomes stale during exactly the highest-traffic moment (end of a tournament), which is when it's watched most closely — mitigate with a shorter merge interval for the top tier specifically, since that's the part users actually look at.
**Follow-ups** — (1) Why does a single Redis ZSET stop working at scale? It's a single logical key, so all writes for the entire leaderboard serialize through wherever that key lives, and a single node's memory bounds the whole leaderboard's size. (2) How do you get a player's approximate global rank cheaply if only local shard rank is exact? Estimate global rank from local rank plus each other shard's known score distribution (a percentile estimate), refreshed on the same cadence as the top-K merge. (3) What if the leaderboard resets every season? Treat it as writing to a new key/namespace per season rather than deleting and rebuilding in place, so historical seasons remain queryable and the reset is instantaneous (a pointer swap, not a data migration).

### 25. Matching Engine
**Asked at:** Framed as "design a stock exchange order book" or "design a marketplace matching engine," a systems-depth prompt testing whether candidates default to "shard for scale" when the correct answer is the opposite. · **Time:** 40 min
**Requirements** — Match buy and sell orders at a price, in strict price-time priority, with microsecond-scale latency for financial use cases. Clarifying: strict price-time priority required (usually yes for an exchange), or is approximate/batched matching acceptable (a general marketplace might allow this); what's the durability requirement on an accepted order before it's matched?
**Scale** — A liquid symbol can see hundreds of thousands of order events per second; matching latency budgets in real exchanges are measured in microseconds, not milliseconds.
**API** — `POST /v1/orders {symbol, side, price, qty}`, internal matching produces `fills` events consumed by settlement.
**Data model** — An in-memory order book per symbol: two priority structures (typically a pair of sorted structures or heaps) for resting buy and sell orders, ordered by price then arrival time.
**The design** — `order arrives → single-threaded matching loop for that symbol's book (no locks, no concurrency within a symbol) → match against best opposing price if crossed, else rest in the book → write to a write-ahead log before acknowledging → emit fill events`.
**The hard part** — This is the deliberate exception to "always shard for horizontal scale." Strict price-time priority is a total-ordering requirement, and total ordering across concurrent writers demands a single writer. The correct scaling axis is *across* symbols (each symbol's book runs single-threaded on its own core/process, fully independent of every other symbol), never *within* one symbol's book. A candidate who proposes sharding a single symbol's order book across multiple nodes for throughput has broken price-time priority, which is the one property this whole system exists to guarantee.
**Failure modes** — Matching engine process crash: because state is entirely in-memory for latency, durability comes from a write-ahead log of every accepted order and match, replayed on restart to rebuild the book exactly — a synchronous database write per order would blow the microsecond latency budget, so durability and low latency are reconciled via the WAL, not by giving up on either. Two symbols with correlated demand both spiking (a sector-wide move): since each symbol is independent, this scales horizontally across cores/processes with no cross-symbol contention, which is precisely the payoff of having enforced single-writer-per-symbol in the first place.
**Follow-ups** — (1) Why can't you shard a single symbol's book for more throughput? Sharding would let two orders on different shards match independently at potentially different effective prices or in the wrong time order, directly violating price-time priority — the one invariant the system is required to hold. (2) How do you get durability without giving up microsecond latency? A write-ahead log, appended before acknowledgment, replayed to rebuild in-memory state after a crash — never a synchronous transactional database write on the hot path. (3) How would this design differ for a general e-commerce marketplace instead of a stock exchange? If strict price-time priority isn't a legal/business requirement, batched or approximate matching (clearing every N milliseconds, or a simpler first-come allocation) is acceptable and removes the single-writer constraint, trading fairness precision for much easier horizontal scaling.

---

## Interview questions

### Q1 — You've been asked "design Twitter" for the third time this month. How do you avoid sounding rehearsed?
**Testing:** whether you can distinguish having the answer from deriving it live.
**Answer:** Lead with the derivation, not the destination. State the clarifying question that actually matters (follower distribution) before naming the hybrid-fanout pattern, so the interviewer watches you arrive at it rather than announce it. If you already know the number that forces the celebrity problem, ask for it early and let the answer produce the architecture in real time.
**Follow-up trap:** *"Just skip to the architecture, I know you know this one."* Compress, don't skip: state your assumptions in one sentence each and move, but never draw a box you can't trace to a stated requirement or number, even under explicit pressure to hurry.

### Q2 — Two of these designs both need a queue. How do you avoid describing them identically?
**Testing:** whether "add a queue" is a reflex or a reasoned choice.
**Answer:** Name the specific property the queue buys in each case. In the notification system, the queue exists to isolate latency classes (transactional vs. bulk) via separate topics. In the web crawler, per-host queues exist to enforce politeness, not to decouple latency. Two systems both "having a queue" is not the same design if the queue is solving different problems.
**Follow-up trap:** *"So when wouldn't you use a queue?"* When the operation must be synchronously acknowledged with a success/failure the caller needs immediately (the ticket-booking hold, the payment charge) — a queue there just delays the moment of finding out something failed, without adding any real decoupling benefit.

### Q3 — The interviewer mutates the classic prompt mid-round: "actually, assume the read:write ratio is 2:1, not 100:1." What do you do?
**Testing:** mutation resistance, `T10-design-method`'s central claim.
**Answer:** Walk the specific downstream decision that assumption fed and change only that. For the news feed, 100:1 justified fanout-on-write; at 2:1 the amplified write cost (250k inserts/sec to serve a read rate only twice as high) stops paying for itself, so switch to read-time merge with a short-TTL cache. State this as a scoped amendment, not a restart.
**Follow-up trap:** *"Your whole diagram is now wrong."* No — the API, the requirements, and most of the failure-mode table survive; only the fanout mechanism and the timeline table change. Naming exactly what survives the mutation and what doesn't is the higher-signal answer than admitting the diagram is wrong wholesale.

### Q4 — What's the one code pattern that shows up across four different designs in this module, and why does it matter that you recognize it?
**Testing:** pattern recognition versus memorizing 25 separate answers.
**Answer:** Atomic compare-and-swap on a scarce resource — ticket booking's seat hold, hotel reservation's per-night inventory decrement, ride-hailing's driver-offer lock, and the rate limiter's token check. All four fail the identical way (a read-then-write race) if implemented naively, and all four are fixed the identical way (a single atomic conditional operation, whether that's a Lua script, a `WHERE status = 'available'` clause with an affected-row check, or a versioned conditional write).
**Follow-up trap:** *"Show me the code."* Have the Lua-script version from this module's "Build it from scratch" section ready to write from memory; an interviewer who asks this is checking whether "atomic CAS" is a phrase you can implement, not just say.

### Q5 — Every design in this catalogue eventually mentions caching. When is adding a cache the wrong answer?
**Testing:** whether cache is a reflex or a reasoned tool.
**Answer:** When the workload is write-dominated and the "cache" would need write-through on every write anyway (little read benefit, added write latency), or when staleness is genuinely unacceptable for that specific field (a seat's `available` status during an active hold — caching that and serving a stale "available" invites the exact double-booking the design exists to prevent). Caching the read-heavy, staleness-tolerant parts of a system while explicitly *not* caching its correctness-critical writes is itself a design decision worth stating out loud.
**Follow-up trap:** *"But caching the seat status would make the read path faster."* Yes, and that's exactly the trap — the read that matters for correctness (checking availability right before a hold) must hit the source of truth, not a cache that could be milliseconds stale during the one moment contention is highest.

### Q6 — Rank the eight patterns in this module's mental model by how often getting them wrong causes a real production incident.
**Testing:** judgment about where the actual risk concentrates, not textbook completeness.
**Answer:** Atomic CAS failures (double-booking, double-spend) are the most severe because they're silent and directly costly. Fanout amplification failures (a celebrity post or a large group chat taking down a service) are the most common because they only appear at a scale most testing never reaches. Durable-intent-then-confirm gaps (the payment reconciliation problem) are the most insidious because they require deliberately testing an ambiguous-failure path that's easy to never exercise. The remaining patterns (indexing, dedup storage, ID generation, cache-in-front, single-writer serialization) cause performance and cost problems more often than correctness incidents.
**Follow-up trap:** *"Which pattern have you never seen fail in your own experience?"* Answer honestly rather than inventing a story — a true "I haven't hit that one personally, here's why I'd still test for it" is a stronger answer than a fabricated incident.

### Q7 — How would you answer "design a system that combines two of these" — e.g., a marketplace that needs both a ticket-booking-style hold and a payment charge?
**Testing:** composition, since real systems are rarely a single pattern.
**Answer:** Sequence the patterns rather than merging them into one step: the seat hold (atomic CAS, pattern 1) completes and returns a `hold_id` before the payment charge (durable-intent-then-confirm, pattern 6) ever begins, and the booking confirmation only fires when both have independently succeeded. Treating this as "one big transaction" across a database and an external payment processor is the wrong instinct — they can't share a transaction boundary, so the design must make each step idempotent and sequence them with a durable record of "which step are we on," which is the outbox pattern from the payment design applied to a two-step flow instead of one.
**Follow-up trap:** *"What if the payment succeeds but the hold expired one second earlier?"* This is the same TTL-races-payment failure mode named in the ticket-booking design; the mitigation (favor honoring a payment that lands slightly late, refund as the fallback path) applies unchanged.

### Q8 — Which of these 25 designs would you refuse to answer with a memorized architecture, even if you knew one cold?
**Testing:** self-awareness about where recall is a liability.
**Answer:** The matching engine, because the entire point of the question is the single-writer-per-symbol insight, and reciting "in-memory order book, write-ahead log" without deriving *why sharding within a symbol is wrong* skips the one thing being tested. Collaborative editing is a close second: naming "OT or CRDT" without being able to say which failure mode each one accepts (a silent convergence bug for OT, unbounded tombstone growth for CRDT) is reciting vocabulary, not demonstrating understanding.
**Follow-up trap:** *"Isn't that true of all 25?"* To a degree, yes — but these two are the sharpest examples because a memorized answer to either is easy to state confidently and completely wrong under a small mutation (e.g., "what if this doesn't need strict ordering" for the matching engine).

### Q9 — A prompt doesn't match any of these 25. How do you know you're not just missing the reference architecture?
**Testing:** whether the pattern-based mental model actually transfers, or whether it's cosmetic.
**Answer:** Run the 8-pattern checklist against the prompt's actual constraints rather than searching memory for a matching system name. "Design a system to let support agents approve refunds above a threshold with a second reviewer" isn't in this catalogue by name, but it's an atomic-CAS-on-approval-state problem (pattern 1, don't let two reviewers approve concurrently) composed with a durable-intent-then-confirm problem (pattern 6, the refund itself crosses a payment boundary). If none of the 8 patterns fit at all, say so honestly — that's the signal the round wants an actual first-principles derivation, not a faster search through memory.
**Follow-up trap:** *"What if you genuinely don't know the domain (e.g., a genomics pipeline)?"* Ask the clarifying questions that would apply to any unfamiliar domain — what's the read/write shape, what's the correctness requirement, what's the failure a domain expert would find embarrassing — rather than bluffing domain knowledge you don't have.

### Q10 — What's the cost story for the most expensive design in this catalogue, and which one is it?
**Testing:** the 2026 cost-grading expectation applied to a full catalogue, not just one worked example.
**Answer:** Video streaming, because egress bandwidth at scale is typically the single largest and most volatile cost line item in any of these 25 systems — a CDN cache-hit ratio moving from 95% to 90% can double origin egress cost overnight, and that ratio is influenced by content popularity distribution the design can't fully control. Object storage and the news feed's Redis timeline are the next most expensive, for different reasons (raw exabyte-scale storage cost versus in-memory footprint), but neither has egress's volatility.
**Follow-up trap:** *"Give me a rough number."* Even an order-of-magnitude estimate said with the arithmetic shown ("15k QPS × 6 KB average response ≈ 90 MB/s ≈ 230 TB/month egress, at roughly $0.05-0.09/GB that's $12-20k/month just for one moderately-sized service") beats a vague "it would be expensive" — the specific worked example lives in `T10-design-method`.

### Q11 — Why does this module put ticket booking, hotel reservation, and ride-hailing's driver offer in the same pattern bucket when they look like different products?
**Testing:** whether the pattern abstraction is genuinely internalized or just a table you memorized.
**Answer:** Strip away the product surface and all three reduce to "many concurrent actors compete to atomically claim one of a small number of scarce, identically-shaped resources, and a naive read-then-write implementation double-allocates under load." The fix (a single atomic conditional operation) and the failure mode (a race window between reading and writing) are identical across all three; only the specific resource (a seat, a room-night, a driver) and its lifecycle (TTL length, cancellation policy) differ.
**Follow-up trap:** *"Then why does the module give them different data models?"* Because the *resource shape* differs even when the *concurrency pattern* doesn't: a seat is a single row, a hotel-night stay is a range across multiple rows needing a transactional multi-row decrement, and a driver's status is one field with no date dimension at all. The pattern predicts the failure mode and the fix; it doesn't predict the schema.

### Q12 — If you had to cut this module down to the one thing worth remembering, what is it?
**Testing:** synthesis under a forced constraint, a common closing question.
**Answer:** Never let application code observe a value and then decide to write based on that observation in two separate round trips when the value is contended — collapse the read and the write into one atomic operation, every time, regardless of which of the 25 systems you're in. That single discipline prevents the most severe and most silent failure mode across this entire catalogue (double-booking, double-charging, double-matching), and it's the one piece of advice that transfers unchanged to a prompt not on this list.
**Follow-up trap:** *"That's just for booking-style systems though, right?"* No — it's why the rate limiter's counter check, the leaderboard's score update contention, and the matching engine's order acceptance all need the same discipline; "booking-style" undersells how often contended state shows up disguised as something else.

---

## Red flags that fail you

- Naming the classic architecture before computing the number that would justify it.
- Describing two different designs' queues, caches, or shards identically without saying what property each is buying.
- Read-then-write on any contended resource (seat, inventory count, driver status, rate-limit counter) — this is the single most common correctness bug across the whole catalogue.
- Treating "add a cache" as a universal fix, including for a value where staleness would reintroduce the exact bug the design exists to prevent.
- Sharding a stock-exchange order book within one symbol for "more throughput," breaking price-time priority.
- No idempotency story on any write endpoint a client can retry (shortener creation, payment charge, notification send, seat hold).
- Zero cost discussion on a video streaming or object storage design in 2026.
- Claiming "exactly-once" across a payment or messaging boundary without describing the reconciliation job that actually makes the claim true.
- Defending a memorized architecture against a stated mutation instead of adjusting it.

## Cheat card

```
PATTERN → DESIGNS → THE ONE DECISION TO DEFEND
1. Atomic CAS on scarce resource
   → ticket booking, hotel reservation, ride-hail offer, rate limiter
   → never read-then-write; one atomic conditional op (Lua/CAS/WHERE+affected-rows)

2. Fanout-write vs fanout-read (celebrity problem = hybrid of both)
   → news feed, notifications, group chat, leaderboard
   → name the follower/group-size THRESHOLD where write-fanout stops paying off

3. Prefix/geo index collapsing high-dim lookup to O(1)-ish
   → proximity service, ride-hail match, autocomplete (trie = geo in string-space)
   → state the cell size / prefix depth as the tunable accuracy-cost knob

4. Content-addressed dedup storage
   → pastebin, Google Drive, object store
   → hash-as-key; write blob before metadata, never the reverse

5. Distributed ID/ordering, no central bottleneck
   → unique ID gen, payment idempotency keys, chat per-conversation seq_no
   → Snowflake: 41-bit ts + 10-bit machine + 12-bit seq = 4096/ms/node

6. Durable-intent-then-confirm across an uncontrolled boundary
   → payment system, ticket booking's payment step, job scheduler claim
   → "exactly-once" = idempotent retry + reconciliation job, not a property that exists

7. Cache-in-front-of-durable-store
   → URL shortener, KV store, distributed cache, autocomplete
   → cold-cache thundering herd fix = single-flight + jittered warm-up, always

8. Correctness via single-writer serialization (exception to "shard for scale")
   → matching engine, distributed scheduler leader election
   → shard ACROSS symbols/jobs, never WITHIN one symbol's/job's ordering domain

DEPTH: 15 deep (Requirements/Scale/API/Data/Design/HardPart/Failure/Follow-ups)
       10 compact (same 8 headers, terser) — say which tier you're in if asked

COST IS GRADED IN 2026 — name the dominant line item with a number, every design
```

## Sources

- [The 2026 FAANG System Design Question Bank — DesignGurus](https://designgurus.substack.com/p/amazon-vs-google-vs-meta-the-2026) — accessed 2026-08-01
- [Amazon Interview Question: URL shortener — Glassdoor](https://www.glassdoor.com/Interview/How-would-you-design-a-URL-shortener-service-QTN_1274023.htm) — accessed 2026-08-01
- [Design a URL Shortener — Hello Interview](https://www.hellointerview.com/community/questions/url-shortener-design/cm5svnaco01dqxszbok7e1lk1) — accessed 2026-08-01
- [How to Design a Rate Limiter — ByteByteGo](https://bytebytego.com/courses/system-design-interview/design-a-rate-limiter) — accessed 2026-08-01
- [Design a Ticket Booking Site Like Ticketmaster — Hello Interview](https://www.hellointerview.com/learn/system-design/problem-breakdowns/ticketmaster) — accessed 2026-08-01
- [System Design Interview: The Double Booking Problem — Benjamin Dickman](https://benjamindickman.com/blog/system-design-interview-the-double-booking-problem/) — accessed 2026-08-01
- [Meta System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/meta-system-design-interview) — accessed 2026-08-01
- [Google System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/google-system-design-interview) — accessed 2026-08-01
- [Stripe System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/stripe-system-design-interview) — accessed 2026-08-01
- [Design a News Feed System — ByteByteGo](https://bytebytego.com/courses/system-design-interview/design-a-news-feed-system) — accessed 2026-08-01
- [Design a Messaging App Like WhatsApp — Hello Interview](https://www.hellointerview.com/learn/system-design/problem-breakdowns/whatsapp) — accessed 2026-08-01
- [The Stripe System Design Question That Separates Senior From Staff Engineers — Medium/T3CH](https://medium.com/h7w/the-stripe-system-design-question-that-separates-senior-from-staff-engineers-ecb9a98af1fd) — accessed 2026-08-01
- [Stripe Docs — Idempotent Requests](https://docs.stripe.com/api/idempotent_requests) — accessed 2026-08-01
- [CRDTs vs. Operational Transformation: How Google Docs Handles Collaborative Editing — SystemDR](https://systemdr.systemdrd.com/p/crdts-vs-operational-transformation) — accessed 2026-08-01
- [Twitter Engineering — Announcing Snowflake](https://blog.x.com/engineering/en_us/a/2010/announcing-snowflake) — accessed 2026-08-01
- [Dropbox Tech Blog — Inside the Magic Pocket](https://dropbox.tech/infrastructure/inside-the-magic-pocket) — accessed 2026-08-01
- [Design a Hotel Booking Service — Exponent](https://www.tryexponent.com/blog/design-a-hotel-booking-service-system-design-interview-question-answer) — accessed 2026-08-01
- [Design a Web Crawler — GeeksforGeeks](https://www.geeksforgeeks.org/system-design/design-a-web-crawler/) — accessed 2026-08-01
- [AlgoMaster — Design a Notification Service](https://algomaster.io/learn/system-design-interviews/design-notification-service) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
