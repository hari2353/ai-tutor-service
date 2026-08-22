# MongoDB: WiredTiger, Replica Sets, Concerns, Sharding, Race Conditions

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 3h · **Prereqs:** `T17-storage-engines`, `T17-mvcc-isolation` · **Updated:** 2026-07-26
> **Module id:** `T17-mongodb` · **Tags:** mongodb, critical

## The 30-second version

MongoDB's WiredTiger storage engine gives document-level concurrency via MVCC — readers see a point-in-time snapshot with no locking, writers take fine-grained intent locks down to the document level, and multiple clients can write to different documents in the same collection simultaneously with no blocking. Schema design in MongoDB is a modeling choice, not an afterthought: embed for data that's read together and bounded in size, reference for data that's independently large or queried separately, and the single most common production-killing anti-pattern is the **unbounded array** — a document that grows a new array element on every event (comments, log entries, order-history items) eventually blows through MongoDB's 16MB document size limit and, well before that limit, degrades write performance because every array append can force the whole document to be rewritten and relocated on disk. Replica sets provide durability and availability via a primary-secondary architecture with a Raft-like election protocol; **read/write concerns** are the actual durability dial — `w: majority` durably survives a primary failure, `w: 1` does not — and **causal consistency** sessions guarantee a client's own reads reflect its own prior writes, which plain majority reads alone don't provide across different secondaries. Sharding partitions data by shard key across nodes with a balancer redistributing chunks, and a poorly chosen shard key (low cardinality, monotonically increasing, or highly skewed) creates hot shards that no amount of horizontal scaling fixes. The `$lookup` aggregation stage is MongoDB's join, and it's expensive precisely because MongoDB isn't optimized for the join patterns a relational planner handles natively. The single most important production lesson: **any read-then-write sequence in application code is a race condition waiting to happen** — `findOneAndUpdate` (MongoDB's atomic find-and-modify) performs the check and mutation as one atomic server-side operation, eliminating the window where two concurrent requests both read the same stale state and both act on it, which a naive `find()` followed by a separate `update()` call cannot do no matter how carefully the application code is written.

## Why this gets asked

Because MongoDB looks deceptively like "JSON with a query language" and the interviewer wants to know if you understand the specific concurrency and consistency model underneath it — and because a resume mentioning "MongoDB race conditions" (fixed in production, not theoretical) is a direct invitation to go deep on exactly this. They've watched a team ship a `find()` then `update()` pattern for something that looked harmless (decrementing inventory, claiming a job from a queue, incrementing a counter) and get bitten by two concurrent requests both reading the same stale count and both proceeding as if they'd claimed the only remaining unit. The follow-up they're listening for is whether you can explain *why* `findOneAndUpdate` fixes it at the mechanism level (one atomic server-side operation, no window between check and mutation) rather than just knowing it's "the atomic one."

---

## Lineage: past → present → future

**What came before.** Relational databases dominated web application backends through the 2000s, and the pain that MongoDB (2009) and the broader document-database movement responded to was twofold: **schema rigidity** (every attribute change required a migration, painful at scale and awkward for genuinely variable/nested application data like user-generated content or event payloads with evolving shapes) and **the object-relational impedance mismatch** (application code naturally works with nested objects; mapping that cleanly to normalized rows-and-joins required an ORM layer that was often a leaky, performance-costly abstraction). MongoDB's answer was to store data in the shape the application actually uses it — a JSON-like document (BSON) that can naturally embed nested structure — trading some of the relational model's constraint-enforcement and join ergonomics for schema flexibility and a data model that maps directly onto how application code thinks about its own objects.

**Where it stands now.** MongoDB's storage engine has matured significantly since the early MMAPv1 era (which had collection-level locking, a real production bottleneck) — **WiredTiger**, the default engine since MongoDB 3.2 (2015), brought document-level concurrency and proper MVCC, closing much of the concurrency gap with mature relational engines. Multi-document ACID transactions, added in MongoDB 4.0 (2018) and extended to sharded clusters in 4.2, closed another historical gap, though the live consensus is that **transactions in MongoDB remain a deliberately reached-for tool, not a default posture** — the document model's core value proposition (atomic single-document operations that don't need a transaction wrapper for the overwhelming majority of application operations) is undermined if a schema is designed such that most writes need multi-document transactions, which is generally read as a sign the schema should be redesigned around better-embedded documents rather than reached for transactions as a first response. The live disagreement in schema design is precisely embed-vs-reference, and MongoDB's own documented anti-patterns (unbounded arrays, massive arrays, excessive collection growth from over-embedding) reflect years of accumulated real production pain, not theoretical concerns — this module's schema-design section is drawn directly from that lineage.

**Where it's heading.** MongoDB 8.0 (2024) and the ongoing 8.x line (current through 2026) continue investing in sharding ergonomics specifically — `sh.shardAndDistributeCollection()` (wrapping shard-then-immediately-reshard-and-rebalance into one operation) reflects a real, current-generation acknowledgment that the historical sharding workflow (shard, then wait on the balancer to slowly redistribute) was operationally painful enough to warrant a first-class fix, not a speculative future direction. Time series collections (native support since MongoDB 5.0, with continued optimization) are MongoDB's answer to the OLAP-adjacent workloads document databases handle poorly by default, using a columnar-like internal storage optimization for time-bucketed data without requiring a document model change from the application's perspective — this is real, shipped, and growing in adoption for IoT/metrics use cases specifically because it avoids needing a separate specialized time-series database for that workload shape. More speculative: MongoDB's push into vector search (Atlas Vector Search) competing directly with dedicated vector databases and pgvector-on-Postgres follows the same general-purpose-database-absorbs-a-specialized-workload pattern seen elsewhere in this track, and the honest assessment (consistent with the equivalent pgvector discussion in `06-postgres.md`) is that it's a legitimate choice at moderate scale with the benefit of data co-location, with dedicated vector engines still generally winning at very large scale and strict recall/latency requirements — validate against actual corpus size rather than assuming either direction.

---

## Mental model

```
WIREDTIGER MVCC + DOCUMENT-LEVEL CONCURRENCY

  Client A: db.orders.updateOne({_id: 1}, {$set: {status: "shipped"}})
  Client B: db.orders.updateOne({_id: 2}, {$set: {status: "shipped"}})

  -> NO BLOCKING. Different documents, WiredTiger's document-level
     concurrency lets both proceed simultaneously — only intent locks
     at the global/database/collection level, no exclusive document lock
     held for the operation's full duration the way row-level locking in
     some engines can serialize contending writers.

  Client C: db.orders.find({_id: 1})   <- reads a consistent SNAPSHOT
                                            as of the read's start, via MVCC,
                                            never blocked by A's in-flight write.

READ-THEN-WRITE RACE (the failure mode you're here to master):

  Client A: doc = db.inventory.findOne({_id: "sku1"})   // reads qty: 1
            if doc.qty > 0:
                db.inventory.updateOne({_id:"sku1"}, {$inc:{qty:-1}})

  Client B: doc = db.inventory.findOne({_id: "sku1"})   // ALSO reads qty: 1
                                                          // (before A's update lands)
            if doc.qty > 0:                              // ALSO true
                db.inventory.updateOne({_id:"sku1"}, {$inc:{qty:-1}})

  RESULT: qty goes from 1 to -1. BOTH clients believed they had the last unit.
  The check (find) and the mutation (update) are TWO separate server round
  trips with an unprotected window between them — no lock spans that window.

ATOMIC FIX:

  db.inventory.findOneAndUpdate(
    {_id: "sku1", qty: {$gt: 0}},        // condition checked SERVER-SIDE,
    {$inc: {qty: -1}}                     // atomically, in the SAME operation
  )
  // Second caller's filter {qty: {$gt: 0}} simply fails to match once qty=0.
  // No window exists between check and mutation because there IS no
  // separate check — the condition is part of the atomic operation itself.
```

---

## How it actually works

### WiredTiger and document-level concurrency

WiredTiger (see `01-storage-engines.md` for the general B-Tree/LSM-adjacent mechanics — WiredTiger itself uses a B-Tree by default, with an LSM option rarely used in practice) provides **MVCC**: every operation gets a point-in-time snapshot, readers never block writers and vice versa, and concurrent writers to *different* documents proceed with no contention. Locking is genuinely fine-grained: WiredTiger takes intent locks at the global, database, and collection levels (cheap, non-blocking bookkeeping) and uses optimistic concurrency control for the actual document-level read/write conflict — two writers targeting the **same** document do serialize (one wins, the other retries transparently or per its configured concern), but that's the only real contention point, a dramatic improvement over MongoDB's original MMAPv1 engine's collection-level locking.

### Schema design: patterns and anti-patterns

**Embed when:** the data is read together, has a bounded/predictable size, and doesn't need independent querying at scale — a blog post's comments if capped at a reasonable count, an order's shipping address (one-to-one, small, always read with the order).

**Reference when:** the data is large, grows unboundedly, needs independent access patterns, or is shared across many parent documents — a product referenced by thousands of orders should be a separate collection referenced by ID, not duplicated into every order document.

**The unbounded array anti-pattern, precisely:** a schema like
```javascript
// ANTI-PATTERN: array grows forever
{ _id: "user123", name: "Alice", activity_log: [ {ts: ..., action: ...}, /* thousands more */ ] }
```
is dangerous for two compounding reasons. First, MongoDB documents have a **16MB hard size limit** — an unbounded array eventually hits it and writes start failing outright. Second, and more insidiously, **long before hitting 16MB**, a growing array frequently causes the document to exceed its currently-allocated space on disk, forcing WiredTiger to relocate the entire document to a new location — this means every array append on a large document can cost a full document rewrite, not an incremental append, and write latency degrades progressively as the document grows, well before the hard limit is ever reached. The fix is the **bucket pattern** (group array elements into time-windowed or count-bounded sub-documents, e.g., one document per user per day of activity, each internally bounded) or moving the growing data into its own referenced collection entirely (`activity_log` as a separate collection with `user_id` as a foreign key, queried and paginated independently).

**The "massive array" anti-pattern** is the same failure from the reference direction: storing an array of references that itself grows unboundedly (a `product.order_ids` array listing every order that ever purchased the product) has the same disk-relocation and eventual-size-limit problems, and additionally makes any query needing to check membership in that array (`$in`) progressively more expensive as the array grows — the fix is always to invert the reference (`orders` collection stores `product_id`, queried via an index on that field) rather than accumulating a growing list on the "one" side of a one-to-many relationship.

**Other well-documented anti-patterns:** case-sensitive/inconsistent field naming across documents in the same collection (breaks index usability and query consistency), deeply nested sub-documents beyond what queries actually need (adds parsing/serialization cost with no query benefit), and separating data that's *always* queried together into separate collections purely out of relational habit (forcing an unnecessary `$lookup` for every query when embedding would have been both simpler and faster).

### Replica sets and elections

A **replica set** is one primary (accepts all writes) plus multiple secondaries (asynchronously replicate the primary's oplog — operation log — and can serve reads depending on read preference). If the primary becomes unreachable, the remaining members hold an **election** (a Raft-derived consensus protocol) to choose a new primary from among eligible secondaries, based on who has the most recent applied oplog entry among reachable nodes and priority configuration. Elections typically complete within a few seconds to low tens of seconds depending on configuration (`electionTimeoutMillis`, default 10 seconds, plus discovery/heartbeat overhead) — during that window, the replica set has no primary and cannot accept writes, which is a real, bounded availability gap applications must be designed to tolerate (retry with backoff, not fail permanently) rather than something a client driver silently makes invisible.

**Write acknowledgment during failover**: a write acknowledged with `w: 1` before a primary fails and before it replicated to any secondary can be **rolled back** if a different secondary (which never received that write) is elected primary — this is a real, documented MongoDB behavior, not a hypothetical edge case, and it's the core argument for `w: majority` in anything requiring durability across a failover.

### Read and write concerns, and their durability implications

**Write concern** controls how many replica set members must acknowledge a write before the driver considers it successful:
- `w: 1` — only the primary acknowledges. Fastest, but that write can be lost entirely if the primary fails before replicating it to any secondary and a different secondary becomes primary.
- `w: majority` — a majority of voting members (including the primary) must acknowledge. This write is durable across a subsequent election, because any node that could win an election must have replicated at least as far as any majority-acknowledged write (a direct consequence of the election protocol's "most recent oplog" requirement).
- `j: true` — additionally requires the acknowledging node(s) to have written to their on-disk journal (see `02-wal-recovery.md` for the general journal/WAL durability argument), protecting against loss from an ungraceful process crash, not just a replica set failover.

**Read concern** controls what a read is allowed to return:
- `local` — the primary's (or queried secondary's) current data, which **may be rolled back** later if it wasn't majority-replicated and a failover occurs — reading data that could later be proven to have never durably existed.
- `majority` — only data that has been majority-acknowledged (and therefore cannot be rolled back) is returned — the read-side counterpart to `w: majority`'s write-side guarantee.
- `linearizable` — the strongest guarantee: reflects all previously completed majority-committed writes, at the cost of confirming with a majority of the replica set on every single read (real latency cost), used only when a single read must reflect the absolute latest committed state with no staleness at all.

### Causal consistency

Even with `read concern: majority`, a client reading from **different secondaries** across successive operations can observe an apparent step backward in time — secondary A might be slightly further behind in replication than secondary B, so a read from A after a read from B could show older data, violating the intuitive expectation that "my own reads shouldn't go backward." **Causally consistent sessions** (`session = client.startSession({causalConsistency: true})`) fix this specifically: MongoDB tracks a logical clock (`operationTime`) across operations within the session, and routes/gates subsequent reads to ensure they reflect at least everything the session has already observed or written — combined with `read concern: majority` and `write concern: majority`, this gives the full causal consistency guarantee: **read-your-own-writes**, **monotonic reads**, **monotonic writes**, and **writes-follow-reads**, without requiring full linearizability's per-read majority-confirmation cost on every operation.

### Sharding and chunk balancing

A **shard key** determines how documents are partitioned across shards. MongoDB divides the shard key's range into **chunks** (contiguous key ranges, historically targeted around 128MB-ish by default before dynamic chunk sizing in newer versions, now more adaptive), and a background **balancer** migrates chunks between shards to keep data volume roughly even.

**Shard key selection is the single highest-leverage, hardest-to-reverse decision in a sharded deployment** (directly analogous to fact-table grain in `17-dimensional-modeling.md` — get it wrong and you're rebuilding, not migrating):
- **Cardinality** — needs enough distinct values that chunks can actually be split finely; a boolean or a 3-value status field as a shard key caps you at a handful of possible chunks regardless of data volume, defeating horizontal scaling entirely.
- **Monotonically increasing keys** (an auto-incrementing ID, a timestamp) as a range shard key concentrate all new writes onto whichever single shard currently owns the "highest" range — a hot-shard problem that gets *worse*, not better, as write volume grows, since all new data lands in the same place. The fix is either **hashed sharding** (MongoDB hashes the key's value before determining chunk placement, spreading monotonic values pseudo-randomly across shards) or choosing a genuinely non-monotonic key.
- **Frequency/skew** — a shard key where one value dominates the dataset (a single enterprise tenant's ID in a multi-tenant system, if that tenant is far larger than others) creates a hot shard regardless of overall cardinality, and MongoDB 8.0's improved balancer/resharding tooling helps redistribute after the fact but doesn't retroactively fix a fundamentally skewed access pattern — this is the same noisy-neighbor problem discussed for multi-tenant B-tree indexing in `05-index-design.md`, applying identically at the sharding layer.

**MongoDB 8.0's `sh.shardAndDistributeCollection()`** wraps sharding and an immediate resharding-to-the-same-key into one operation specifically to avoid the historical pain of waiting on the background balancer to slowly redistribute data after an initial shard operation — a direct, current-generation operational improvement.

### The aggregation pipeline and $lookup cost

The **aggregation pipeline** is MongoDB's primary query/transformation mechanism — a sequence of stages (`$match`, `$group`, `$sort`, `$project`, `$lookup`, etc.) each transforming the document stream from the previous stage. `$lookup` performs a left-outer-join-like operation against another collection, and it is genuinely expensive relative to a well-indexed relational join: it's most efficient when the `$lookup`'s local/foreign key comparison can use an index on the foreign collection (equivalent to a nested-loop join with an index, see `04-query-planner.md`), and it degrades toward a full collection scan per input document when it can't, which is a much worse cost curve than a relational hash or merge join over the same data. `$lookup` also cannot span shards efficiently prior to more recent versions' improvements to sharded `$lookup` support, and even with support, cross-shard `$lookup` inherently costs more than a same-shard join due to the network round trips involved. The senior guidance: `$lookup` sparingly, and if a specific join pattern is hit constantly, that's usually a signal the two collections should be embedded together (if the cardinality/size profile supports it) rather than joined repeatedly at query time.

### Multi-document transactions

MongoDB (4.0+, single replica set; 4.2+, sharded clusters) supports full ACID multi-document transactions with snapshot isolation semantics, but they come with real costs relative to single-document atomic operations: transactions hold resources for their duration, have a default execution time limit (historically 60 seconds), and add meaningful latency overhead versus a single atomic document operation. The consistent guidance across MongoDB's own documentation and practitioner consensus: **reach for a well-embedded document (atomic single-document operations) first**; use multi-document transactions when the operation genuinely spans multiple documents/collections in a way no schema redesign can avoid (e.g., a funds transfer between two account documents, where "just embed one account in the other" makes no sense) — needing transactions pervasively across your application's hot paths is generally a signal to revisit the schema, not a normal steady state.

### Race conditions: findAndModify/findOneAndUpdate vs. read-then-write

This is the section to know cold, given it's a lived production incident. The failure pattern is always structurally the same: application code performs a `find()` (or `findOne()`), inspects the result, decides on an action, then performs a **separate** `update()`/`save()` call — and between the read and the write, another concurrent request can perform the exact same read (seeing the same pre-update state) and the exact same decision, because nothing has locked or marked that state as "being acted on."

**`findOneAndUpdate`** (and `findAndModify`, its older/more general predecessor) collapses the check and the mutation into **one atomic server-side operation**: the filter (which can include the business condition, like `qty: {$gt: 0}`) and the update are evaluated and applied together, atomically, by the server, with no window where a second client's request can interleave between "check" and "act." If the filter's condition is no longer true by the time this operation actually executes on the server (because a concurrent request already changed it), the operation simply matches zero documents and returns null/no-match — the second caller gets a clean, correct "this didn't happen" signal instead of a silent double-decrement.

**Concretely, in order of preference for solving a check-then-write problem:**
1. **Atomic update operators with an embedded condition** — `updateOne({_id: x, qty: {$gt: 0}}, {$inc: {qty: -1}})`, checking the modified-count in the response to know if it actually applied. This is the cheapest and most idiomatic fix for simple conditional mutations.
2. **`findOneAndUpdate` with a conditional filter** — same idea, but returns the matched/updated document directly, useful when you need the resulting (or prior) document state in the same round trip, e.g., claiming a job from a queue and getting the claimed job's data back atomically.
3. **Optimistic concurrency via a version field** — read a document including a `version` field, attempt `updateOne({_id: x, version: v}, {$set: {...}, $inc: {version: 1}})`, and check the modified count; if zero, someone else updated it first and the caller must re-read and retry. Useful when the "condition" is more complex than a simple comparison and doesn't fit cleanly into an atomic operator's filter.
4. **Unique/partial indexes for uniqueness guarantees** — when the actual invariant is "at most one of X can exist" (claiming a unique slot, preventing duplicate registration), a unique index rejecting the second insert is often simpler and more robust than any read-then-check logic.
5. **Multi-document transactions** — for genuinely cross-document invariants that can't be expressed as a single atomic operation on one document (see above), at the cost of transaction overhead.

**The trap that catches people who "know" `findOneAndUpdate` exists:** using it correctly for the write, but still performing a **separate prior read** to decide *whether* to call it at all, and building business logic on that separate read's result rather than on `findOneAndUpdate`'s own return value — this reintroduces exactly the same race, just with an unnecessary extra read in front of an otherwise-correct atomic operation. The discipline is: the condition must be evaluated **inside** the atomic operation's filter, not in application code beforehand.

---

## Build it from scratch

A minimal in-memory simulation demonstrating the race condition and its fix, runnable without a real MongoDB instance, to make the mechanism (not just the vocabulary) concrete:

```python
# untested sketch — illustrates the race and its fix mechanically, not a MongoDB driver
import threading

class ToyCollection:
    """Simulates enough of MongoDB's semantics to demonstrate the race:
    find() and update() are separate calls with a real gap between them;
    find_one_and_update() performs the check-and-mutate as one atomic step."""
    def __init__(self, docs: dict):
        self.docs = docs
        self.lock = threading.Lock()  # simulates the server's internal atomicity,
                                       # NOT something application code gets to use

    def find_one(self, _id):
        with self.lock:
            return dict(self.docs[_id])   # a snapshot read, gap starts right after this

    def update_one(self, _id, inc_field, amount):
        with self.lock:
            self.docs[_id][inc_field] += amount

    def find_one_and_update(self, _id, condition_field, condition_op, condition_val, inc_field, amount):
        with self.lock:                                  # THE WHOLE THING is one atomic step
            doc = self.docs[_id]
            if condition_op(doc[condition_field], condition_val):
                doc[inc_field] += amount
                return dict(doc)
            return None   # condition failed — no mutation, clean signal


# --- Demonstrating the RACE (read-then-write) ---
inv = ToyCollection({"sku1": {"qty": 1}})

def racy_decrement():
    doc = inv.find_one("sku1")            # <-- gap opens here; a real MongoDB
    if doc["qty"] > 0:                    #     deployment has network latency here too
        inv.update_one("sku1", "qty", -1)

threads = [threading.Thread(target=racy_decrement) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print("Racy result (should be 0, watch it go negative):", inv.docs["sku1"]["qty"])
# With true concurrency (no artificial lock forcing serialization of the CHECK+ACT
# pair), this can go negative — 5 threads, only 1 unit of inventory.


# --- Demonstrating the FIX (findOneAndUpdate) ---
inv2 = ToyCollection({"sku1": {"qty": 1}})
import operator

def atomic_decrement():
    result = inv2.find_one_and_update("sku1", "qty", operator.gt, 0, "qty", -1)
    return result is not None   # True = this caller actually got the unit

threads = [threading.Thread(target=atomic_decrement) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print("Atomic result (guaranteed 0, never negative):", inv2.docs["sku1"]["qty"])
```

Run this enough times with the racy version and, especially under real thread scheduling variance, you can observe `qty` go negative — the atomic version structurally cannot, because the check and the mutation are never separated by a scheduling gap. Full version against a real MongoDB instance (via `pymongo`/`motor`), including a job-queue-claiming scenario and a version-field optimistic-concurrency example: **`labs/py/08-mongo-race-lab/`**.

---

## How it's done in production

**Driver-level defaults matter.** Modern MongoDB drivers default to `w: majority` write concern and `readConcern: local` (not `majority`) for most operations unless configured otherwise — teams that assume "the driver's defaults are safe for financial-grade durability" without checking read concern specifically can be surprised that a read immediately after a majority write can, in edge cases around a concurrent failover, still observe data that later gets rolled back, if that specific read wasn't itself issued at `majority` read concern.

**Retryable writes** (enabled by default since MongoDB 4.2 client-side) automatically retry a write once if it fails due to a transient network error or replica set election, using an idempotency token so the retry doesn't double-apply — this specifically protects against the "did my write actually land or not" ambiguity during a failover window, distinct from (and complementary to) the application-level race conditions this module focuses on.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Inventory/counter goes negative or double-decrements under load | Read-then-write race: `find()` followed by a separate `update()` with a decision made on stale data | Replace with `findOneAndUpdate`/`updateOne` with the condition embedded in the filter itself, verify via modified-count, not a prior read |
| Write acknowledged successfully but "disappears" after a primary failover | `w: 1` write acknowledged by the old primary before it replicated to any secondary; a different secondary (without that write) became the new primary | Use `w: majority` for anything requiring durability across failover; understand this is expected MongoDB behavior at `w: 1`, not a bug |
| A client's own reads appear to go backward in time across requests | Reads routed to different secondaries with different replication lag, no causal consistency session in use | Use a causally consistent session (`causalConsistency: true`) combined with majority read/write concern |
| Write latency degrades progressively on a collection as documents grow, well before hitting any size limit | Unbounded array anti-pattern — array growth forces whole-document relocation on disk repeatedly | Bucket pattern (bounded sub-documents per time window/count) or move the growing data to its own referenced collection |
| One shard is consistently hotter than others, and adding more shards doesn't help | Poorly chosen shard key: low cardinality, monotonically increasing, or heavily skewed toward one value | Reshard with a higher-cardinality or hashed key; for monotonic keys specifically, hashed sharding spreads writes; for tenant skew, consider isolating the largest tenant(s) |
| `$lookup`-based aggregation query is far slower than expected | No index on the foreign collection's join field, forcing a per-document scan instead of an indexed lookup | Add an index on the foreign collection's compared field; if this join pattern is constant, consider embedding instead of joining at query time |
| Multi-document transaction times out or adds unexpected latency under load | Transaction default execution time limit exceeded, or transaction held open across an external/slow operation | Keep transactions short and scoped to database operations only (never wait on an external API call mid-transaction); reconsider whether the operation could be redesigned around a single-document atomic update instead |

---

## Tradeoffs & when NOT to use it

- **Do not use `w: 1` for anything where losing an acknowledged write during a failover is unacceptable** — this is the single most consequential MongoDB durability decision, and defaults can be deceptive across driver versions and deployment configurations, so verify explicitly rather than assume.
- **Do not reach for multi-document transactions as a default problem-solving tool.** If most of an application's hot-path writes need transactions, that's a strong signal the schema should be redesigned around better document embedding, not a signal that transactions are simply "the correct MongoDB way" to write application logic.
- **Do not choose a shard key based on what's convenient to query by (like a customer-facing ID) without separately checking cardinality, monotonicity, and skew** — a shard key chosen for query convenience alone is one of the most common, hardest-to-reverse MongoDB production mistakes, directly analogous to picking the wrong dimensional-model grain.
- **Do not use `$lookup` as a substitute for proper schema design when the same join pattern runs on every request** — MongoDB's document model is at its best when related data that's read together is embedded; leaning on constant `$lookup` calls forfeits much of the performance advantage the document model is supposed to provide.
- **Do not assume MongoDB's flexible schema means "no schema design is needed."** The well-documented anti-patterns (unbounded arrays, massive arrays) exist precisely because schema flexibility without schema *discipline* leads to structures that degrade badly under real production growth, in ways that are much harder to migrate away from once a collection has grown large than they would have been to avoid up front.
- **For workloads that are fundamentally relational** (many-to-many relationships queried from both directions with complex, ad hoc joins, strong need for cross-entity referential integrity enforced at the database level), a relational database is very often still the better default than forcing that shape into documents — MongoDB earns its place when the document model's natural fit (nested, mostly-independently-accessed entities) genuinely matches the application's actual data shape.

---

## Interview questions

### Q1 — Explain the read-then-write race condition and why `findOneAndUpdate` fixes it structurally, not just "because it's atomic."
**Testing:** the core production lesson this module is built around.
**Answer:** A `find()` followed by a separate `update()` has an unprotected window between the read and the write where a concurrent request can perform the identical read (seeing the same pre-update state) and act on the same stale decision — nothing marks the state as "being acted on" during that gap. `findOneAndUpdate` fixes this by evaluating the filter condition and applying the mutation as a **single atomic operation on the server**, so there is no separate "check" step in application code at all for a second caller to race against; if the condition is no longer true by execution time, the operation simply matches nothing.
**Follow-up trap:** *"If I call `findOneAndUpdate` but decide whether to call it based on a prior separate `find()`, am I safe?"* — no, this reintroduces the exact same race with an unnecessary extra read in front of it; the business condition must be evaluated **inside** the atomic operation's filter (e.g., `{qty: {$gt: 0}}`), not in application code based on a preceding read, or the atomicity of the write doesn't protect the decision that led to calling it.

### Q2 — Rank the five approaches to fixing a check-then-write race, and explain when you'd reach for something other than the simplest option.
**Answer:** (1) Atomic update operators with an embedded condition (`updateOne` with the condition in the filter) — cheapest, use for simple comparisons. (2) `findOneAndUpdate` with a conditional filter — same idea but returns the document, use when you need the result in the same round trip (e.g., claiming a queue job). (3) Optimistic concurrency via a version field — use when the condition is too complex for a simple atomic filter comparison. (4) Unique/partial indexes — use when the actual invariant is uniqueness, not a numeric threshold. (5) Multi-document transactions — use only for genuinely cross-document invariants that can't be expressed as one atomic operation.
**Follow-up trap:** *"Why not just always use multi-document transactions since they're the most general solution?"* — transactions carry real overhead (execution time limits, resource holding, latency), and reaching for them by default for problems solvable with a single atomic document operation is both slower and a sign the schema might not actually need the multi-document scope it's being given credit for.

### Q3 — Explain WiredTiger's document-level concurrency and how it differs from MongoDB's original MMAPv1 engine.
**Answer:** WiredTiger uses MVCC (point-in-time snapshots for readers, no reader-writer blocking) plus fine-grained intent locking down to the document level via optimistic concurrency control — two writers targeting different documents in the same collection proceed with no contention at all, and only writers to the **same** document actually serialize. MMAPv1 (MongoDB's original default engine) locked at the collection level, meaning any write to a collection could block concurrent writes to unrelated documents in that same collection — a much coarser, more contention-prone model that WiredTiger's adoption as the default (MongoDB 3.2, 2015) specifically fixed.
**Follow-up trap:** *"Does document-level concurrency mean two writes to the same document never conflict?"* — no, writes to the *same* document do genuinely serialize (one succeeds, the conflicting one is retried or fails depending on the operation), which is exactly right — WiredTiger's improvement is scoping contention down to the actual conflicting unit (the document), not eliminating contention where it's genuinely necessary.

### Q4 — What is the unbounded array anti-pattern, and why does it hurt performance well before hitting MongoDB's 16MB document limit?
**Answer:** A document with an array that grows indefinitely (an activity log embedded directly in a user document, appended forever) eventually hits the hard 16MB document size limit, but the more insidious cost arrives earlier: as the array grows, appends frequently exceed the document's currently-allocated disk space, forcing WiredTiger to relocate the entire document to a new location — turning what looks like an incremental append into a full-document rewrite, with progressively worsening write latency as the document grows.
**Follow-up trap:** *"What's the fix that doesn't require giving up the embedding entirely?"* — the bucket pattern: group array elements into bounded sub-documents (e.g., one document per user per day, each internally capped), preserving much of embedding's locality benefit for recent/relevant data while keeping any single document's size bounded and predictable, rather than either accepting unbounded growth or fully normalizing into a separate collection when that's not actually necessary.

### Q5 — Explain `w: 1` vs `w: majority` and what specifically can happen to a `w: 1` write during a primary failover.
**Answer:** `w: 1` is acknowledged once the primary alone has applied the write, before it necessarily replicates to any secondary. If the primary then fails before that write reaches any secondary, and a different secondary (which never received the write) is elected the new primary, the write is **rolled back** — it's genuinely lost despite having been acknowledged as successful to the original client. `w: majority` requires a majority of voting members to acknowledge before returning success, and because any node capable of winning a subsequent election must have replicated at least as far as any majority-acknowledged write, a majority-acknowledged write survives any failover.
**Follow-up trap:** *"Does `w: majority` guarantee the write is visible to all subsequent reads immediately?"* — no, that's a separate axis (read concern): a `w: majority` write is durable across failover, but a read at `readConcern: local` against a lagging secondary might not reflect it yet; you need `readConcern: majority` (or a causally consistent session) on the read side to get the corresponding read-side guarantee.

### Q6 — What does a causally consistent session guarantee that plain `readConcern: majority` alone doesn't?
**Answer:** Plain majority reads guarantee you only see majority-committed (non-rollback-able) data, but successive reads within the same client session, if routed to different secondaries with different replication lag, can still appear to go backward in time (a later read from a more-lagging secondary shows older data than an earlier read from a less-lagging one). A causally consistent session tracks a logical clock (`operationTime`) across the session's operations and ensures subsequent reads reflect at least everything the session has already observed or written, giving read-your-own-writes, monotonic reads, monotonic writes, and writes-follow-reads — without needing full linearizability's per-read majority-confirmation cost.
**Follow-up trap:** *"Is a causally consistent session the same as linearizability?"* — no, it's a strictly weaker (and cheaper) guarantee: it only orders operations *within the same causal session*, not a global total order across all clients in the system the way linearizable reads provide; two different, causally-unrelated sessions have no ordering guarantee relative to each other under causal consistency alone.

### Q7 — Why does a monotonically increasing shard key create a hot shard, and what fixes it?
**Answer:** Range-based sharding on a monotonic key (an auto-incrementing ID, a timestamp) means every new document's key value is greater than all previous ones, so all new writes land in the chunk currently owning the "highest" range, which lives on a single shard — every insert goes to the same shard, and the problem gets worse as write volume grows, not better with more shards added. Hashed sharding (MongoDB hashes the key value to determine placement) fixes this by spreading monotonically increasing values pseudo-randomly across shards, at the cost of losing efficient range-query scans on that key (a hashed key can't be range-scanned across shards the way an unhashed range key can).
**Follow-up trap:** *"If you hash-shard the key, can you still do efficient date-range queries if the key is a timestamp?"* — not directly on the hashed field's ordering — a hashed shard key destroys the ability to route a range query to a contiguous subset of shards, so a date-range query would need to scatter-gather across all shards regardless; if range queries on that field are a common access pattern, consider a compound shard key (a lower-cardinality, well-distributed prefix field plus the timestamp) rather than reflexively hashing the timestamp alone.

### Q8 — Why is `$lookup` typically more expensive than a well-indexed relational join, and what's the senior guidance on using it?
**Answer:** `$lookup` performs best when the foreign collection has an index on the compared field, giving roughly nested-loop-with-index performance, but degrades toward scanning the entire foreign collection per input document when it can't use an index — a much worse cost curve than a relational engine's hash or merge join over the same data volume, and cross-shard `$lookup` adds network round-trip costs on top even with sharded support. The senior guidance: use it sparingly for genuinely ad hoc or infrequent join needs, index the foreign field when you do use it, and treat a `$lookup` pattern that runs on every request as a signal to consider embedding the related data instead.
**Follow-up trap:** *"Doesn't this mean MongoDB is just bad at relational data?"* — it means MongoDB's document model is optimized for a different default access pattern (related data embedded and read together); reaching for constant `$lookup` usage is usually a sign the schema is fighting the document model rather than using it, not that MongoDB's join implementation is poorly engineered relative to what it's designed to be used for.

### Q9 — When would you use multi-document transactions, and why is "we use transactions for most of our writes" considered a schema smell?
**Answer:** Use them for operations that genuinely span multiple documents/collections in a way no reasonable embedding could avoid — the canonical example is a funds transfer debiting one account document and crediting another, where embedding one account inside the other makes no structural sense. Needing transactions across most hot-path writes suggests the schema wasn't designed around MongoDB's actual strength (atomic single-document operations covering the majority of real application invariants when documents are embedded well), and is generally a signal to revisit the schema rather than to keep leaning on transactions as the default correctness mechanism.
**Follow-up trap:** *"What's the actual cost of overusing transactions, concretely?"* — transactions hold resources (locks/snapshots) for their duration, have a default execution time limit historically around 60 seconds that can be hit under load or contention, and add real latency overhead per operation versus a single atomic document write — at meaningful scale this shows up as measurably worse throughput and occasional transaction-timeout errors under load that a well-embedded schema wouldn't need to pay for.

### Q10 — A team notices their sharded MongoDB cluster has one shard consistently at 90% disk and CPU while others sit at 30%. Diagnose the likely cause and the fix.
**Answer:** Almost certainly a shard key problem: either low cardinality (too few distinct values to split into enough chunks), a monotonically increasing key concentrating all new writes on one shard, or skew (one value, like a dominant tenant, accounting for a disproportionate share of the data). Diagnose by checking the shard key's actual value distribution and chunk distribution (`sh.status()`); fix depends on the specific cause — hashed sharding for monotonic keys, a higher-cardinality or compound key for low cardinality, and potentially isolating an outsized tenant onto dedicated infrastructure for genuine skew that resharding alone can't fix.
**Follow-up trap:** *"MongoDB 8.0 has better resharding tools now — doesn't that solve this?"* — improved resharding/balancing tooling (like `sh.shardAndDistributeCollection()`) makes the *operational process* of fixing a bad shard key faster and less painful once identified, but it doesn't retroactively fix the underlying skew in the data or access pattern itself — a fundamentally skewed workload (one enormous tenant) still needs an architectural response (isolation, not just redistribution), not just a faster rebalance.

### Q11 — Explain why retryable writes exist and how they differ from the application-level race conditions this module focuses on.
**Answer:** Retryable writes (default since MongoDB 4.2 client-side) automatically retry a write once if it fails due to a transient network error or a replica set election, using a server-tracked idempotency token so the retry can't double-apply the same write — this specifically resolves the ambiguity of "did my write actually land or not" during a failover or network blip, a driver/infrastructure-level concern. Application-level race conditions (read-then-write) are a completely separate problem: they occur even with perfectly reliable networking and no failover at all, purely from two concurrent requests both reading the same pre-mutation state with no atomicity spanning the read and the write.
**Follow-up trap:** *"So does enabling retryable writes protect against the inventory-race scenario earlier?"* — no, not even slightly; retryable writes solve "was my single write applied exactly once despite a network/failover hiccup," not "did I make my decision to write based on stale data that a concurrent request also read" — these are orthogonal problems solved by orthogonal mechanisms (retry/idempotency tokens vs. atomic check-and-mutate operations).

### Q12 — Design the schema and concurrency strategy for a job queue where workers claim jobs from a shared MongoDB collection, ensuring no job is claimed by two workers.
**Testing:** synthesizing atomicity, schema design, and production judgment into a realistic scenario.
**Answer:** Each job document has a `status` field (`pending`/`claimed`/`done`) and a `claimed_by`/`claimed_at` field. A worker claims a job via `findOneAndUpdate({status: "pending"}, {$set: {status: "claimed", claimed_by: worker_id, claimed_at: now}}, {sort: {priority: -1}})` — the atomic filter-plus-update ensures only one worker's operation can actually transition a given job from `pending` to `claimed`; any other concurrent worker's identical query simply won't match that job anymore. Add a `claimed_at` staleness check and a periodic reclaim job (find jobs stuck in `claimed` past a timeout, atomically reset to `pending`) to handle a worker crashing mid-processing. Avoid storing jobs as elements of an array on a single "queue" document (unbounded-array anti-pattern); each job should be its own document in its own collection.
**Follow-up trap:** *"What if you need `findOneAndUpdate` to also atomically consider job priority ordering across a large, high-throughput queue?"* — `sort` combined with the filter works correctly for a single call, but under very high contention, many workers racing for the same top-priority job all attempt the same `findOneAndUpdate` and only one succeeds per call — which is correct but can mean the others waste a round trip; at very high throughput, this is sometimes addressed by sharding the queue by a partition key (worker pool/region) to reduce contention on the "top of queue" hot spot, trading some strict global priority ordering for reduced contention, a real and sometimes necessary tradeoff at scale.

---

## Red flags that fail you

- Describing a `find()` followed by an `update()` as safe "because MongoDB is fast."
- Not knowing that `w: 1` writes can be rolled back during a primary election.
- Confusing read concern and write concern, or not knowing `readConcern: majority` exists.
- Recommending multi-document transactions as the default fix for any multi-step operation.
- Choosing a shard key without checking cardinality, monotonicity, and skew.
- Not knowing what causes the unbounded array anti-pattern's performance cliff.
- Claiming `$lookup` performs like a relational join regardless of indexing.

---

## Cheat card

```
WIREDTIGER      MVCC — point-in-time snapshots, readers never block writers.
                Document-level concurrency: only SAME-document writers serialize;
                different documents proceed with zero contention. Default engine
                since MongoDB 3.2 (fixed MMAPv1's collection-level locking).

SCHEMA          EMBED: read together, bounded size, no independent query need.
                REFERENCE: large/unbounded, independently queried, shared widely.
                ANTI-PATTERN unbounded array: append forces whole-doc RELOCATION
                  on disk long before 16MB hard limit — progressive write-latency
                  decay. Fix: bucket pattern (bounded sub-docs) or own collection.
                ANTI-PATTERN massive array: growing reference array on the "one"
                  side of 1:many — same relocation cost + costly $in membership
                  checks. Fix: invert the reference.

REPLICA SET     1 primary + secondaries, Raft-like election on primary loss.
                electionTimeoutMillis default 10s — no writes accepted during
                election window (design for retry-with-backoff, not "invisible").
                w:1 write can be ROLLED BACK if primary fails before replicating
                it and a different secondary (without it) wins the election.

WRITE CONCERN   w:1 = primary only, can be lost on failover.
                w:majority = survives failover (any future primary must have it).
                j:true = + journaled on disk, survives ungraceful process crash.
READ CONCERN    local = may later be rolled back (not majority-replicated yet).
                majority = only durable, non-rollback-able data.
                linearizable = strongest, majority-confirms on EVERY read (cost).

CAUSAL CONSISTENCY   session{causalConsistency:true} + majority r/w concern =
                read-your-writes + monotonic reads + monotonic writes +
                writes-follow-reads. Weaker/cheaper than full linearizability
                (only orders within one session, not globally).

SHARDING        shard key = highest-leverage, hardest-to-reverse decision.
                Check: cardinality (enough distinct values to split chunks),
                monotonicity (increasing key -> all writes hit ONE shard,
                  worsens with scale -> fix: hashed sharding, loses range-scan),
                skew (one dominant value -> hot shard regardless of cardinality,
                  same noisy-neighbor problem as multi-tenant B-tree indexing).
                MongoDB 8.0: sh.shardAndDistributeCollection() — shard + reshard
                  to same key in one op, skips slow balancer wait.

$LOOKUP         MongoDB's join. Fast WITH an index on the foreign field (~nested
                loop w/ index); degrades to full scan per doc WITHOUT one.
                Constant $lookup on a hot path = signal to embed instead.

TRANSACTIONS    Full ACID since 4.0 (single RS) / 4.2 (sharded). Real cost:
                held resources, default ~60s exec limit, added latency.
                Reach for embedding FIRST; transactions for genuine cross-doc
                invariants only (e.g. funds transfer). "Most writes need a
                transaction" = schema smell, redesign around embedding.

RACE CONDITION  find() then update() = UNPROTECTED WINDOW, two concurrent
                readers see same stale state, both act -> double-decrement/
                negative inventory. FIX ORDER OF PREFERENCE:
                1. updateOne(filter WITH condition, $inc/...) — check modified count
                2. findOneAndUpdate(filter WITH condition, update) — need doc back
                3. optimistic concurrency: version field in filter, retry on 0-match
                4. unique/partial index — invariant IS uniqueness
                5. multi-doc transaction — genuine cross-document invariant only
                TRAP: doing a separate find() to DECIDE whether to call
                findOneAndUpdate reintroduces the same race — condition MUST be
                inside the atomic filter, never in application code beforehand.

RETRYABLE WRITES   default since 4.2 — auto-retry on transient network/election
                failure via idempotency token. Solves "did my write land," NOT
                the application-level race condition (orthogonal problems).
```

## Sources

- [DevRel Insights: Read-Modify-Write Anti-Pattern — MongoDB](https://medium.com/mongodb/devrel-insights-read-modify-write-anti-pattern-36245f56489f) — accessed 2026-07-26
- [Causal Consistency and Read and Write Concerns — MongoDB Manual](https://www.mongodb.com/docs/manual/core/causal-consistency-read-write-concerns/) — accessed 2026-07-26
- [WiredTiger Storage Engine — MongoDB Manual](https://www.mongodb.com/docs/manual/core/wiredtiger/) — accessed 2026-07-26
- [Choose a Shard Key — MongoDB Manual v8.0](https://www.mongodb.com/docs/v8.0/core/sharding-choose-a-shard-key/) — accessed 2026-07-26
- [Sharding — MongoDB Manual v8.0](https://www.mongodb.com/docs/v8.0/sharding/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
