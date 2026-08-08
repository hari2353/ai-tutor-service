# Databases: RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune

> **Track:** C-AWS AWS Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-databases` · **Tags:** database

## Why this gets asked

The interviewer has watched a hot partition throttle a DynamoDB table at 30% of its provisioned capacity while the rest sat idle, has debugged a "single-table design" that made a simple feature request take three days because the access patterns changed and the denormalized model didn't, and has personally had to explain to a VP why a DocumentDB migration silently broke a feature that depended on a MongoDB aggregation stage that doesn't exist on DocumentDB. Database questions at this level aren't "what is a primary key" — they're "can you reason about the actual distributed-systems tradeoff each managed service made, and do you know honestly when the trendy pattern (single-table design, serverless everything) is the wrong call for this specific team."

---

## Lineage: past → present → future

**What came before.** RDS (2009) automated the operational grind of running a relational database — patching, backups, Multi-AZ failover — but it was still fundamentally one primary instance with synchronous block-level replication to a standby; scaling writes meant scaling up the instance, and read scaling meant read replicas lagging behind on ordinary asynchronous replication. DynamoDB (2012) grew out of Amazon's internal Dynamo paper (2007) and the recognition that many workloads at Amazon's scale needed partition tolerance and predictable latency more than they needed joins or ACID transactions across arbitrary keys — the pain it solved was relational databases falling over under Amazon's own retail-scale, unpredictable traffic patterns.

**Where it stands now.** Aurora (2014) represents the current consensus answer to "how do you get relational semantics with cloud-native scaling": separate compute from a distributed, log-structured storage layer replicated 6 ways across 3 AZs with a 4-of-6 write quorum, so failover promotes a replica against already-shared storage instead of rebuilding a standby from scratch. The live disagreement in the DynamoDB world is single-table design — its original advocate, Rick Houlihan, has publicly acknowledged the backlash after "works well for high-scale serverless apps with well-defined, stable access patterns" got flattened into "always put everything in one table," and even other prominent advocates have walked back unconditional endorsement. [Houlihan on single-table design criticism](https://x.com/houlihan_rick/status/1760469859761029228) — accessed 2026-08-01. In caching, the Redis license changes (SSPL in 2024, then AGPLv3 in 2025) triggered ElastiCache's shift to defaulting new deployments toward **Valkey**, the Linux Foundation-governed BSD-licensed fork, which by 2026 is a mature, cheaper, marginally faster drop-in.

**Where it's heading.** Aurora Serverless v2's scale-to-zero capability (GA November 2024) signals AWS's direction of making relational database cost track actual usage far more closely than the old "provision for peak, pay 24/7" model, high confidence this expands further. DocumentDB and Valkey will likely keep chasing upstream MongoDB/Redis feature parity incrementally rather than fully closing the gap, given the compatibility-layer nature of both services — treat any specific missing-feature claim as something to re-verify near an interview date, since this list moves.

---

## Mental model

Think of the AWS relational/NoSQL split as two different answers to "what do you give up to scale":

```
RDS (classic)          Aurora                    DynamoDB
┌────────────┐        ┌──────────────┐          ┌─────────────────┐
│  Primary   │        │   Compute    │          │  Partitioned     │
│  instance  │        │  (1 writer,  │          │  key-value store │
│     │      │        │  up to 15    │          │  hash(PK) routes │
│  sync repl │        │  readers)    │          │  to a partition; │
│     ▼      │        │      │       │          │  each partition  │
│  Standby   │        │      ▼       │          │  has its own     │
│ (failover  │        │ Shared,      │          │  fixed throughput│
│  target)   │        │ log-structured│         │  ceiling         │
│            │        │ storage, 6x  │          │                  │
│ read       │        │ across 3 AZs,│          │  scale = add     │
│ replicas   │        │ 4/6 write    │          │  partitions,     │
│ = async,   │        │ quorum,      │          │  not "add a      │
│ own copy   │        │ 3/6 read     │          │  bigger machine" │
└────────────┘        └──────────────┘          └─────────────────┘
   scale = bigger        scale = shared            scale = spread
   instance / more       storage layer, fast       load across
   read replicas         failover (no standby      partitions —
                          rebuild needed)           requires good
                                                     key design
```

---

## How it actually works

### RDS vs Aurora, architecturally

Standard RDS Multi-AZ keeps a synchronously-replicated standby instance with its own separate storage volume; failover means promoting that standby and redirecting the DNS endpoint, typically **1-2 minutes**. Aurora separates compute from storage entirely: the storage layer is a distributed, log-structured service that all of a cluster's instances (one writer, up to 15 readers) share, replicated **6 ways across 3 Availability Zones (2 copies per AZ)**, with a **4-of-6 write quorum** (a write commits once 4 of 6 storage nodes acknowledge) and a **3-of-6 read quorum**. Because reads and writes overlap by at least one node mathematically (4+3 > 6), a read quorum is guaranteed to include at least one up-to-date copy without needing distributed consensus for every read. The primary sends compact **redo log records** to storage rather than full data pages, which is what makes the 4/6 write quorum practical without saturating the network. [Aurora storage architecture](https://muratbuffalo.blogspot.com/2022/03/amazon-aurora-design-considerations-and.html) — accessed 2026-08-01.

Because Aurora replicas share the same underlying storage as the writer, **Aurora failover is typically under 30 seconds and commonly under 60 seconds** — there's no separate standby to rebuild, just a role promotion. [Aurora high availability — AWS docs](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.AuroraHighAvailability.html) — accessed 2026-08-01.

### Aurora Serverless v2 scaling behavior

Aurora Serverless v2 scales in **0.5 ACU increments**, adjusting capacity within seconds in response to connection count, query load, and memory pressure for scale-*up*, but scaling **down happens more gradually, over several minutes**, specifically to avoid thrashing from brief load spikes — you cannot configure a custom cooldown period or scaling algorithm; it's fully managed. As of **November 2024**, Aurora Serverless v2 supports **scaling to zero ACUs** when idle, with only storage charges continuing during the paused state and roughly a **15-second resume time** on the next connection. [Aurora Serverless v2 scale to zero](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-aurora-serverless-v2-scaling-zero-capacity) — accessed 2026-08-01.

### Read replicas and replica lag

Standard RDS read replicas use **asynchronous, engine-native replication** (binlog-based for MySQL/MariaDB, WAL-based for PostgreSQL), and lag is measured in **seconds**, not milliseconds — real-world lag under heavy write load or a replica running a large query can stretch into minutes, and pathological cases (nontransactional storage engines, unindexed writes replaying on the replica) have been reported reaching **thousands of seconds** of lag. Aurora replicas, sharing the same underlying storage as the writer, typically see **sub-10ms replication lag** since they're reading from the same log stream rather than replaying a separate copy — this is one of Aurora's most concrete practical advantages over standard RDS replication, not just an architecture diagram difference.

### Failover behavior and time

| | Typical failover time | Mechanism |
|---|---|---|
| RDS Multi-AZ (non-Aurora) | 1-2 minutes | Promote synchronous standby, redirect DNS |
| Aurora | Under 60s, often under 30s | Promote an existing reader against already-shared storage |

### DynamoDB partition key design and hot partitions

DynamoDB spreads a table's data and throughput across partitions based on the hash of the partition key. Each partition has a hard ceiling — **3,000 read capacity units or 1,000 write capacity units per second, per partition** — and this ceiling applies even if the table overall has unused provisioned or on-demand capacity. **The observable symptom of a hot partition**: `ProvisionedThroughputExceededException` (or throttling under on-demand) on specific items or a narrow key range, while CloudWatch shows the table's aggregate consumed capacity well below its total provisioned capacity — the giveaway is throttling *despite* apparent headroom, because the headroom is sitting unused on other partitions. **Adaptive capacity** helps by automatically boosting a hot partition's effective throughput to absorb uneven traffic without manual intervention, but it cannot exceed the per-partition hard ceiling — a genuinely too-hot key (a viral item, a poorly chosen key like a status enum with only 3 values) will still throttle. [DynamoDB hot partition symptoms](https://www.scylladb.com/glossary/dynamodb-hot-partition/) — accessed 2026-08-01.

### Single-table design — an honest assessment

Single-table design (popularized by Rick Houlihan's re:Invent talks) denormalizes multiple entity types into one table using generic `PK`/`SK` attributes and overloaded GSIs, minimizing the number of round trips needed to satisfy a known, fixed set of access patterns. **It genuinely works** when: access patterns are well-understood upfront and unlikely to change significantly, the team needs to minimize round-trip latency at serious scale, and there's real DynamoDB expertise on the team to maintain the resulting schema. **It genuinely fails, and Houlihan himself has publicly acknowledged this**, when: access patterns evolve (a new feature needs a query shape the original overloaded-index design didn't anticipate, and retrofitting it onto a single table is far harder than adding a new table would have been), the team doesn't have deep DynamoDB fluency and treats the pattern as a cargo-culted best practice rather than a deliberate scale tradeoff, or the actual scale doesn't justify the schema-flexibility cost being paid. **Most teams should not do single-table design** — multi-table, one-entity-per-table modeling is easier to reason about, easier to onboard new engineers into, and the round-trip cost it "wastes" is often irrelevant below genuinely large scale. [When NOT to use single-table design](https://singletable.dev/blog/when-not-to-use-single-table-design) — accessed 2026-08-01.

### LSI vs GSI

| | Local Secondary Index (LSI) | Global Secondary Index (GSI) |
|---|---|---|
| Partition key | Must match the base table's | Can be entirely different |
| Sort key | Different from base table | Different from base table |
| Consistency | Supports strongly consistent reads | Eventually consistent reads only |
| Created | Only at table creation, cannot add/remove later | Can be added or removed anytime, backfilled from existing data |
| Limit | Up to 5 per table | Up to 20 per table (soft limit, can request increase) |
| Size constraint | 10GB per partition key value across base table + all LSIs combined | No equivalent size constraint |

[DynamoDB GSI vs LSI](https://useme-alehosaini.medium.com/the-good-the-bad-and-the-ugly-of-gsi-and-lsi-in-amazon-dynamodb-56b29fdc543c) — accessed 2026-08-01. The LSI's "must create at table creation, can't add later" constraint is the practical reason most new designs default to GSIs — locking in an access pattern decision permanently at table-creation time is a real operational risk most teams should avoid unless they specifically need the strong-consistency option LSIs uniquely offer.

### On-demand vs provisioned capacity

On-demand pricing dropped significantly in **November 2024**, meaningfully shifting the break-even point: AWS now recommends on-demand as the default for most new workloads, particularly anything with unpredictable or spiky traffic, or under roughly 10 million requests/month. Provisioned capacity (with auto-scaling) remains cheaper — often by **3-4x at realistic ~70% utilization**, and dramatically more (**~26x** at theoretical 100% utilization) — for workloads with sustained, predictable throughput where utilization consistently stays above roughly 40%. [DynamoDB on-demand vs provisioned 2026](https://www.usage.ai/blogs/aws/reserved-instances/dynamodb/on-demand-vs-provisioned/) — accessed 2026-08-01.

### DynamoDB Streams

Streams capture item-level changes in near-real time, grouped into shards. Stream records expire and are automatically removed after **24 hours** — a consumer that falls behind by more than a day permanently loses those change records, unlike Kinesis's configurable longer retention. Shards split automatically under load and are also rotated roughly every **4 hours**, which can cause visible `IteratorAge` spikes in a Lambda-based consumer during shard transitions even when the consumer itself is healthy.

### Transactions and their cost

`TransactWriteItems`/`TransactGetItems` support up to **100 items** per transaction (also capped by a 4MB aggregate size), guaranteeing all-or-nothing atomicity across multiple items and even multiple tables in the same account and region. The cost: transactional operations consume **2x the capacity units** of the equivalent non-transactional operation — a transactional write of a 1KB item consumes 2 WCUs instead of 1; a transactional read of up to 4KB consumes 2 RCUs instead of 1. This is a real, frequently-overlooked cost multiplier when a team reaches for transactions as a default rather than only where cross-item atomicity is genuinely required.

### ElastiCache: Redis vs Memcached vs Valkey

The Redis license changed twice in quick succession: **March 2024** to a dual SSPLv1/RSALv2 license (no longer OSI-approved open source), then **Redis 8.0 in 2025** added an AGPLv3 option. **Valkey**, forked from Redis OSS 7.2 in March 2024 under Linux Foundation governance and the permissive BSD license, is AWS's (and Google's) response, and is now the **default engine for new ElastiCache deployments**. As of 2026, ElastiCache continues legacy support for Redis OSS only up to version 7.2 — anyone wanting newer Redis-compatible features must move to Valkey, since ElastiCache doesn't ship newer licensed Redis versions. Valkey 8.1/9.x benchmarks show roughly **8% higher ops/sec, 22% lower p99 latency, 20% less memory use, and a 20% lower ElastiCache hourly rate** versus Redis OSS. [Valkey for ElastiCache](https://www.dragonflydb.io/guides/elasticache-valkey) — accessed 2026-08-01. **Memcached** remains relevant specifically for pure, simple key-value caching with a multi-threaded architecture and no persistence/replication needs — simpler operationally when you genuinely don't need Redis/Valkey's data structures, pub/sub, or durability options.

### DocumentDB's actual MongoDB compatibility limits

DocumentDB is MongoDB API-*compatible*, not MongoDB itself — it's a separate implementation built on Aurora's storage layer. Known, real gaps as of the 5.0-8.0 compatibility line: **no retryable writes** (application code needs its own error-handling/retry logic that native MongoDB drivers assume is handled transparently), **no `$graphLookup`** aggregation stage, limited or missing support for **capped collections, GridFS, text indexes, vector search indexes, partial indexes, case-insensitive indexes, time-series collections, client-side field-level encryption, and queryable encryption**. Many newer aggregation pipeline operators and stages added to recent MongoDB releases are also not available. [DocumentDB MongoDB compatibility](https://www.mongodb.com/docs/drivers/documentdb-support/) — accessed 2026-08-01. The practical implication: **migrating an existing MongoDB application to DocumentDB requires actually testing the specific aggregation pipelines and driver behaviors in use**, not just assuming "MongoDB-compatible" means drop-in — CRUD and most indexing strategies work unchanged, but anything relying on the missing feature list needs rework or won't be caught until production.

### Neptune and when a graph is right

Neptune fits when the actual question being asked of the data is relational-in-the-graph-theory-sense — "how is this connected to everything else" — rather than "what is this record": fraud detection (ring detection across accounts/devices/transactions), recommendation engines (collaborative filtering via graph traversal), social network-shaped data, and knowledge graphs. A relational database *can* model this with join tables, but multi-hop traversal queries ("friends of friends who also follow X") degrade badly with nested joins as hop count grows, where a graph database's traversal is closer to constant-time-per-hop regardless of overall graph size. Cross-reference `T17-knowledge-graphs` for when a dedicated graph beats a relational or vector-based approach for that specific class of problem. **When NOT to use Neptune**: if the actual query pattern is mostly single-entity lookups with occasional shallow joins, a relational database with proper indexing is simpler to operate, cheaper, and has a much larger hiring pool of engineers who can maintain it.

---

## Build it from scratch

A minimal, correct DynamoDB conditional write demonstrating both idempotency and avoiding the "read then write" race that plagues hand-rolled uniqueness checks:

```python
# untested sketch
import boto3
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table("orders")

def create_order_idempotent(order_id: str, payload: dict) -> bool:
    """Returns True if this call created the order, False if it already existed."""
    try:
        table.put_item(
            Item={"PK": f"ORDER#{order_id}", **payload},
            ConditionExpression="attribute_not_exists(PK)",  # atomic uniqueness check
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False  # already exists — this is the idempotent retry path
        raise
```

This is the mechanical shape of every "safe retry" pattern in DynamoDB: the condition expression is evaluated and applied atomically server-side, avoiding the read-then-write race a naive `get_item` followed by `put_item` would have.

---

## How it's done in production

A typical production stack: **Aurora PostgreSQL/MySQL** for the primary OLTP store where relational modeling and joins genuinely matter, with **Aurora Serverless v2** for variable-load environments (staging, low-traffic services, dev) where scale-to-zero avoids paying for idle capacity; **DynamoDB with a multi-table design** for the majority of services, reserving single-table design specifically for the handful of genuinely high-scale, access-pattern-stable services where a DynamoDB specialist owns the schema; **ElastiCache for Valkey** as the default cache layer, with Memcached reserved for pure caching with no need for Redis/Valkey's richer data structures; **DocumentDB** only when migrating an existing MongoDB workload where the compatibility gaps have been explicitly tested against, not chosen as a greenfield default over DynamoDB; **Neptune** scoped narrowly to the specific graph-shaped subset of the domain (fraud rings, recommendation traversal) rather than as a general-purpose database.

| Symptom | Cause | Fix |
|---|---|---|
| DynamoDB throttling at 30% of provisioned table capacity | A single partition (hot key) exceeding its 3,000 RCU/1,000 WCU ceiling while other partitions are idle | Redesign the partition key for better distribution (add a random/hashed suffix, shard the hot key); adaptive capacity helps but can't exceed the per-partition ceiling |
| RDS read replica lag balloons to minutes under load | Asynchronous, single-threaded (or limited-parallelism) replication falling behind write volume, or a large query holding up replay | Move to Aurora for shared-storage replicas with sub-10ms typical lag, or reduce replica query load, or use multi-threaded replication where the engine supports it |
| Aurora Serverless v2 feels sluggish right after a burst | Scale-down is intentionally gradual (minutes) to avoid thrashing, but scale-up should be fast — check if the workload pattern is actually scaling up fast enough or if min ACU is set too low | Raise the minimum ACU floor if bursts are frequent and predictable enough that scale-up latency itself (not scale-down) is the issue |
| DocumentDB migration passes CRUD tests but a reporting feature silently returns wrong aggregated data | An aggregation pipeline uses `$graphLookup` or a newer operator DocumentDB doesn't support and silently errors or behaves differently | Test every aggregation pipeline explicitly against DocumentDB's documented compatibility gaps before migration, not just basic CRUD |
| DynamoDB Streams consumer misses records after an outage | Consumer was down for more than 24 hours; stream records expired | Ensure consumer recovery SLAs stay well under 24 hours, or add a periodic full-table reconciliation for anything where a missed change is unacceptable |
| DynamoDB transaction costs spike unexpectedly | Transactions used as a default pattern for writes that don't actually need cross-item atomicity | Reserve TransactWriteItems for genuine multi-item atomicity needs; use conditional writes on a single item for simple idempotency instead, at half the capacity cost |
| Single-table DynamoDB design breaks when a new feature needs an unanticipated query shape | Access patterns changed after the schema was locked into overloaded PK/SK/GSI structure | Add a new GSI if the change fits the existing entity shape, or accept that a genuinely new access pattern may need a new table rather than forcing it into the existing overload |

---

## Tradeoffs & when NOT to use it

- **Don't default to single-table DynamoDB design.** It's a deliberate, expert-level tradeoff for a narrow set of high-scale, access-pattern-stable workloads — most teams get more value from simpler multi-table modeling that's easier to evolve and onboard new engineers into.
- **Don't reach for DynamoDB transactions as a default write pattern.** They cost 2x the capacity units of a normal write/read; use conditional writes on a single item for idempotency where cross-item atomicity isn't actually the requirement.
- **Don't migrate to DocumentDB assuming "MongoDB-compatible" means zero rework.** Test the actual aggregation pipelines, retryable-write assumptions, and index types in use against DocumentDB's real, documented gap list before committing to the migration.
- **Don't use Neptune (or any graph database) for workloads that are mostly single-entity lookups with shallow joins** — a relational database is simpler, cheaper, and has a larger available talent pool for that shape of problem.
- **Don't assume Aurora Serverless v2's scale-down is a knob you can tune** — it's fully managed and intentionally conservative on scale-down to avoid thrashing; if that gradual scale-down is a cost problem at your traffic pattern, provisioned Aurora may actually be cheaper.
- **Redis license changes are a real operational decision point, not a footnote** — new ElastiCache deployments should default to Valkey unless a specific Redis-only feature (post-fork) is required, since ElastiCache doesn't carry newer licensed Redis versions forward anyway.

---

## Interview questions

### Q1 — Explain Aurora's storage architecture and why it enables faster failover than standard RDS Multi-AZ.
**Testing:** whether "Aurora is faster" is understood mechanically, not just memorized as a fact.
**Answer:** Aurora separates compute from a distributed, log-structured storage layer shared by all instances in the cluster — one writer, up to 15 readers — replicated 6 ways across 3 AZs with a 4-of-6 write quorum and 3-of-6 read quorum, guaranteeing overlap between the two without full consensus on every read. Because readers already share the writer's storage, failover is a role promotion against existing shared storage rather than rebuilding a standby from a separate replication stream, giving Aurora failover typically under 60 seconds (often under 30) versus RDS Multi-AZ's 1-2 minutes for standby promotion and DNS redirect.
**Follow-up trap:** *"Why 4-of-6 and 3-of-6 specifically, not something simpler like 3-of-6 and 3-of-6?"* — 4+3=7 > 6 guarantees any read quorum overlaps with any write quorum by at least one node, which is what makes it safe to read without full consensus; a 3-of-6/3-of-6 split wouldn't guarantee that overlap and could return stale data from a read quorum that missed the latest write entirely.

### Q2 — A DynamoDB table shows throttling on CloudWatch, but aggregate consumed capacity is well under the provisioned total. What's going on?
**Testing:** the specific, named failure mode with its observable symptom.
**Answer:** A hot partition — one partition (driven by a poorly distributed partition key, or a single viral/hot item) is hitting its hard per-partition ceiling of 3,000 RCU or 1,000 WCU per second, while other partitions sit well under their share, so the table-wide aggregate looks healthy while that specific key range throttles with `ProvisionedThroughputExceededException`. Adaptive capacity helps absorb some imbalance automatically but cannot exceed the per-partition hard ceiling.
**Follow-up trap:** *"Won't adding more provisioned capacity fix it?"* — no, if the bottleneck is one partition already at its per-partition ceiling, adding table-wide capacity doesn't raise that specific partition's limit; the fix is redesigning the partition key (adding a random or hashed suffix, sharding the hot key across multiple physical keys) for better distribution.

### Q3 — Is single-table design for DynamoDB a best practice you'd recommend by default?
**Testing:** the honest, senior-level assessment rather than parroting a conference talk.
**Answer:** No. It's a legitimate, deliberate tradeoff for a narrow set of cases — high-scale serverless applications with well-understood, stable access patterns and a team with real DynamoDB expertise to maintain the resulting overloaded schema. For most teams, it optimizes minimizing round trips at the cost of schema flexibility, and when access patterns inevitably change, retrofitting a new query shape onto an already-overloaded single table is significantly harder than adding a new table would have been. Even Rick Houlihan, who popularized the pattern, has publicly acknowledged the backlash against it being applied as a default rather than a deliberate scale decision.
**Follow-up trap:** *"If a candidate in a system design interview proposes single-table design immediately for a moderate-scale service, is that a good or bad signal?"* — generally a mild red flag unless they immediately justify it against the specific scale and access-pattern-stability of the problem; reflexively reaching for it without that justification suggests cargo-culting a pattern rather than reasoning about the actual tradeoff.

### Q4 — LSI or GSI for a new access pattern you're not 100% sure you'll need forever?
**Testing:** whether the create-time-only constraint on LSIs is known and correctly weighted.
**Answer:** GSI, almost always, specifically because LSIs can only be defined at table creation time and can never be added or removed afterward, while GSIs can be added, modified, or removed at any point and are backfilled automatically from existing data. The only reason to reach for an LSI is needing strongly consistent reads on that secondary access pattern, which GSIs cannot provide (GSI reads are eventually consistent only).
**Follow-up trap:** *"Are there other differences that matter besides consistency and creation timing?"* — yes, LSIs must share the base table's partition key and only vary the sort key, and count against a combined 10GB-per-partition-key-value size limit across the base table and all LSIs, which GSIs (with an independent partition key and no equivalent size ceiling) don't share.

### Q5 — How does DynamoDB's on-demand vs provisioned pricing decision actually play out at realistic utilization?
**Testing:** whether the November 2024 price cut is known and whether the "just use on-demand" oversimplification is avoided.
**Answer:** On-demand's per-request pricing dropped substantially in November 2024, and AWS now recommends it as the default for unpredictable or lower-volume workloads (roughly under 10M requests/month, or genuinely spiky traffic). But for sustained, predictable throughput with auto-scaled provisioned capacity running at a realistic ~70% utilization, provisioned remains meaningfully cheaper — commonly 3-4x — and the gap widens further (theoretically ~26x) the closer utilization gets to 100%. The right choice is a function of both predictability and sustained utilization, not a blanket rule either direction.
**Follow-up trap:** *"A workload has predictable traffic but low absolute volume — which wins?"* — at low absolute request volume, the fixed operational overhead of managing provisioned capacity and auto-scaling policies often isn't worth the savings versus on-demand's simplicity, even if provisioned would technically be cheaper per-request; the crossover depends on both volume and the team's tolerance for capacity-management overhead.

### Q6 — What does a DynamoDB transaction actually cost compared to a normal write, and when do you actually need one?
**Testing:** the specific 2x multiplier and appropriate use, not just "transactions exist."
**Answer:** `TransactWriteItems` and `TransactGetItems` consume 2x the capacity units of the equivalent non-transactional operation — a 1KB transactional write costs 2 WCUs instead of 1. They're genuinely needed when an operation must atomically succeed or fail across multiple distinct items (or tables), such as transferring a value between two records where a partial update would leave the data inconsistent. For simple idempotency on a single item, a conditional write (`ConditionExpression`) achieves the same safety at half the capacity cost, since it doesn't need the multi-item atomicity guarantee.
**Follow-up trap:** *"What's the item and size limit on a single transaction?"* — up to 100 items, with a 4MB aggregate size cap across the whole transaction, and no two actions in the same transaction can target the same item.

### Q7 — ElastiCache Redis vs Valkey vs Memcached — what would you actually deploy today and why?
**Testing:** currency on the license fork, not stale "just use Redis" advice.
**Answer:** Valkey by default for any new deployment needing Redis-like data structures, pub/sub, or persistence — it's the Linux Foundation-governed, BSD-licensed fork AWS now defaults ElastiCache to, roughly 8% faster, 20% less memory, and about 20% cheaper per hour than Redis OSS on ElastiCache, with ElastiCache only carrying Redis OSS forward up to version 7.2 anyway due to the 2024/2025 license changes. Memcached remains the right call specifically for pure, simple caching with no need for persistence, replication, or Redis/Valkey's richer data structures, given its simpler multi-threaded architecture.
**Follow-up trap:** *"Is Valkey a drop-in replacement with zero migration risk?"* — command-set and protocol compatibility is high, making most migrations low-friction, but any application relying on Redis-specific behavior introduced in versions after the March 2024 fork point (7.2) won't have that behavior in Valkey, so a compatibility check against the specific commands and modules in use is still warranted before migrating a production workload.

### Q8 — A team is planning to migrate a MongoDB application to DocumentDB purely for cost savings. What do you tell them?
**Testing:** whether "MongoDB-compatible" is understood as a compatibility layer with real gaps, not a synonym for MongoDB.
**Answer:** DocumentDB is MongoDB API-compatible, not MongoDB itself, built on a completely different storage engine (Aurora's). Real gaps that will break a naive migration include no retryable writes (their driver code likely assumes the native MongoDB retryable-write behavior and needs its own error handling added), no `$graphLookup`, and missing or limited support for capped collections, GridFS, text indexes, vector search indexes, and several other features. The migration needs every actual aggregation pipeline and driver assumption tested against DocumentDB specifically — CRUD operations and most indexing generally work unchanged, but the gap list is exactly where a "should just work" migration silently breaks in production.
**Follow-up trap:** *"If the app only uses basic CRUD, is DocumentDB definitely safe?"* — mostly yes for pure CRUD, but retryable-write behavior is still a gap even for simple operations under network blips, so error-handling code that relied on the driver silently retrying needs to be made explicit rather than assumed to carry over.

### Q9 — When is a graph database like Neptune actually the right choice over a relational database with join tables?
**Testing:** the real "when a graph is right" judgment, not just naming Neptune's existence.
**Answer:** When the dominant query shape is deep, multi-hop traversal — "how is this connected to everything else" rather than "what is this record" — such as fraud-ring detection across accounts and devices, or recommendation engines doing collaborative-filtering traversal. Relational joins for these queries degrade as hop count grows because each additional hop is another join, while a graph database's traversal cost per hop stays roughly constant regardless of overall graph size. If the actual workload is mostly single-entity lookups with shallow, predictable joins, a relational database remains simpler to operate and has a far larger available talent pool.
**Follow-up trap:** *"Could you just use recursive CTEs in Postgres instead of a dedicated graph database?"* — for shallow traversal depth and moderate data volume, yes, and it avoids introducing a new database technology; the crossover to a dedicated graph database is really about traversal depth and volume where recursive CTE performance degrades unacceptably, which should be measured against the actual workload rather than assumed.

### Q10 — Design the database layer for a service currently on standard RDS PostgreSQL that's starting to see replica lag complaints during traffic spikes.
**Testing:** synthesizing the Aurora vs RDS tradeoff into an actual recommendation.
**Answer:** Migrate to Aurora PostgreSQL specifically for the shared-storage replication model — Aurora replicas read from the same underlying log stream as the writer rather than replaying a separate asynchronous copy, typically producing sub-10ms lag versus standard RDS's second-to-minutes lag under load. This is a genuine architectural fix for the specific symptom described (lag under spikes), not just a "bigger instance" fix, since standard RDS replica lag is fundamentally bounded by single-threaded (or limited-parallelism) replay speed regardless of instance size.
**Follow-up trap:** *"Is Aurora strictly better, or are there real costs to this migration?"* — Aurora costs more per equivalent instance size than standard RDS, has some engine-version and extension compatibility differences from vanilla PostgreSQL to verify, and migration itself (via DMS or a snapshot-based cutover) carries real operational risk and downtime planning that shouldn't be hand-waved as a pure win.

### Q11 — Explain the tradeoff Aurora Serverless v2's scale-to-zero introduces for a low-traffic internal service.
**Testing:** knowing the specific numbers and the honest tradeoff, not just "it saves money."
**Answer:** Scale-to-zero (GA November 2024) pauses the database entirely after a configurable idle period, stopping ACU charges while continuing to bill only storage, and resumes on the next connection in roughly 15 seconds. This is a real cost win for genuinely idle-most-of-the-time services (dev, staging, low-traffic internal tools), at the cost of that 15-second cold-resume latency being visible to whatever makes the first request after an idle period — acceptable for an internal tool, likely unacceptable for a customer-facing synchronous request path.
**Follow-up trap:** *"Would you ever use scale-to-zero on a production customer-facing database?"* — only if the traffic pattern genuinely has extended true-zero windows and the first-request-after-idle latency is either acceptable or can be masked (a warming ping on a schedule, accepting the small population of users who hit the cold resume); for anything with continuous, unpredictable traffic, scale-to-zero's benefit doesn't materialize since the database rarely actually reaches the idle threshold.

---

## Red flags that fail you

- Recommending single-table DynamoDB design by default without justifying it against actual scale and access-pattern stability.
- Not knowing the per-partition DynamoDB throughput ceiling (3,000 RCU / 1,000 WCU) or its observable symptom.
- Claiming DocumentDB is "just MongoDB in AWS" without knowing the real compatibility gaps.
- Not knowing DynamoDB transactions cost 2x capacity units.
- Recommending a graph database for workloads that are mostly single-entity lookups.
- Not knowing Aurora's failover speed advantage comes from shared storage, not just "it's newer."
- Recommending new Redis deployments on ElastiCache without mentioning the license changes or Valkey.
- Confusing LSI and GSI creation-time constraints.

---

## Cheat card

```
AURORA STORAGE: log-structured, 6 copies / 3 AZs (2 per AZ), 4-of-6 write quorum, 3-of-6 read quorum
  (4+3>6 guarantees read/write quorum overlap). Redo-log shipping, not full pages.
  Failover: <60s (often <30s) -- role promotion on shared storage, no standby rebuild.
  RDS Multi-AZ (non-Aurora) failover: 1-2 min.

AURORA SERVERLESS v2: scales in 0.5 ACU steps. Scale-up: seconds. Scale-down: minutes (anti-thrash).
  Scale-to-zero (GA Nov 2024): pauses fully, storage-only billing, ~15s resume on next connection.

READ REPLICA LAG: standard RDS = async, SECONDS typical, can reach 1000s under heavy load/big queries.
  Aurora replicas = shared storage w/ writer, typically SUB-10ms lag.

DYNAMODB PARTITION CEILING: 3,000 RCU / 1,000 WCU per partition, PER SECOND. Hard ceiling.
  Hot partition symptom: throttling (ProvisionedThroughputExceededException) DESPITE
    healthy table-wide aggregate consumed capacity -- the giveaway.
  Adaptive capacity absorbs imbalance but can't exceed the per-partition ceiling.

SINGLE-TABLE DESIGN: works for stable access patterns + real DynamoDB expertise + high scale.
  MOST TEAMS SHOULD NOT DO IT. Houlihan (its own advocate) has publicly acknowledged the backlash.

LSI vs GSI:
  LSI: same PK as base table, diff SK, up to 5, CREATE-TIME ONLY (never add/remove later),
       supports strong consistency, 10GB/partition-key-value limit (base+LSIs combined)
  GSI: independent PK+SK, up to 20 (soft), addable/removable anytime, EVENTUALLY CONSISTENT ONLY

ON-DEMAND vs PROVISIONED (post Nov-2024 price cut):
  On-demand: default for unpredictable/spiky/<~10M req/mo
  Provisioned+autoscale: ~3-4x cheaper at realistic ~70% utilization, ~26x at 100% theoretical

TRANSACTIONS: TransactWriteItems/GetItems, up to 100 items, 4MB aggregate cap.
  COST: 2x capacity units vs equivalent non-transactional op. Use conditional writes for
  single-item idempotency instead (half the cost, no need for multi-item atomicity).

DYNAMODB STREAMS: records expire after 24hr. Shards rotate ~every 4hr (watch IteratorAge spikes).

ELASTICACHE: Redis license changed SSPL(2024)->AGPLv3 option(2025). ElastiCache caps
  legacy Redis OSS support at 7.2. Valkey (BSD, Linux Foundation, forked from 7.2) = new default,
  ~8% faster, ~20% less memory, ~20% cheaper/hr. Memcached = simple pure caching, no persistence.

DOCUMENTDB GAPS: no retryable writes, no $graphLookup, no/limited: capped collections, GridFS,
  text indexes, vector search indexes, partial indexes, time-series, CSFLE/queryable encryption.
  "MongoDB-compatible" != MongoDB. TEST every aggregation pipeline before migrating.

NEPTUNE: right when the query IS "how is X connected to everything" (fraud rings, recs, social graph).
  Wrong when queries are mostly single-entity lookups + shallow joins -- relational is simpler/cheaper.
```

## Sources

- [Amazon Aurora: Design Considerations — muratbuffalo.blogspot.com](https://muratbuffalo.blogspot.com/2022/03/amazon-aurora-design-considerations-and.html) — accessed 2026-08-01
- [High availability for Amazon Aurora — AWS docs](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.AuroraHighAvailability.html) — accessed 2026-08-01
- [Amazon Aurora Serverless v2 supports scaling to zero capacity — AWS announcement](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-aurora-serverless-v2-scaling-zero-capacity) — accessed 2026-08-01
- [What is a DynamoDB Hot Partition? — ScyllaDB glossary](https://www.scylladb.com/glossary/dynamodb-hot-partition/) — accessed 2026-08-01
- [Rick Houlihan on single-table design criticism — X/Twitter](https://x.com/houlihan_rick/status/1760469859761029228) — accessed 2026-08-01
- [When NOT to Use DynamoDB Single-Table Design — singletable.dev](https://singletable.dev/blog/when-not-to-use-single-table-design) — accessed 2026-08-01
- [The Good, the Bad, and the Ugly of GSI and LSI — Medium](https://useme-alehosaini.medium.com/the-good-the-bad-and-the-ugly-of-gsi-and-lsi-in-amazon-dynamodb-56b29fdc543c) — accessed 2026-08-01
- [DynamoDB On-Demand vs Provisioned — Usage.ai](https://www.usage.ai/blogs/aws/reserved-instances/dynamodb/on-demand-vs-provisioned/) — accessed 2026-08-01
- [Amazon ElastiCache for Valkey — DragonflyDB guide](https://www.dragonflydb.io/guides/elasticache-valkey) — accessed 2026-08-01
- [Amazon DocumentDB compatibility with MongoDB drivers — MongoDB docs](https://www.mongodb.com/docs/drivers/documentdb-support/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Aurora's speed advantage over standard RDS comes from a real architectural choice, not just newer marketing: a shared, log-structured storage layer replicated 6 ways across 3 AZs with a 4-of-6 write quorum and 3-of-6 read quorum lets replicas read from the writer's own storage, giving sub-10ms replica lag and sub-60-second failover versus standard RDS's second-to-minutes async lag and 1-2 minute failover. DynamoDB's per-partition throughput ceiling (3,000 RCU/1,000 WCU) means a hot key throttles independently of table-wide headroom, and single-table design — despite its popularity — is a deliberate expert-level tradeoff for stable, high-scale access patterns that most teams shouldn't reach for by default, a view its own original advocate now publicly acknowledges. GSIs beat LSIs for anything not requiring strong consistency, since LSIs lock in at table creation and can never be added later. DynamoDB transactions cost double the capacity units of an equivalent non-transactional operation, and DocumentDB's MongoDB compatibility has real, specific gaps — retryable writes and `$graphLookup` among them — that require testing before any migration, not assuming.
