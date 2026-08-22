# Cassandra/DynamoDB: Partition Keys, Hot Partitions, Single-Table Design

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-wide-column-kv` · **Tags:** nosql

## The 30-second version

Wide-column stores make you model tables per query, not per entity, because there is no join and no cheap secondary access path by default — you denormalize at write time so every read is a single partition lookup, which means the schema design step is really "enumerate my access patterns first, then derive the tables," the reverse order from normalized relational design. The partition key is the whole game: every row with the same partition key lives together on the same replica set, so a partition key that isn't evenly distributed produces a hot partition — one node pegged at high CPU/IO while the rest of the cluster looks idle, the classic symptom of a bad key choice (a single tenant ID, a low-cardinality status column, a fixed device ID for a time-series). Cassandra gives you a ring of nodes, a replication factor, and tunable per-request consistency levels; the arithmetic `R + W > N` is what guarantees a read sees the latest write, and choosing weaker levels trades that guarantee for lower latency and availability during partition/node failure. DynamoDB hides the ring behind managed partitions with hard physical caps (3,000 RCU/s and 1,000 WCU/s per partition, adaptive capacity smoothing skew up to those caps but no further) and a sharp constraint that LSIs cannot outlive their base table's 10GB per-partition-key item collection limit while GSIs can. Single-table design is a real, useful technique for a small number of well-understood, stable access patterns at high scale and a real liability once access patterns are still evolving, multiple teams share the table, or the workload needs ad hoc analytical queries — most teams building against DynamoDB should start with more, simpler tables and only collapse into single-table design once the access patterns and cost picture actually justify it.

## Why this gets asked

The interviewer has watched a partition key chosen for developer convenience (a boolean status flag, a single "global" partition for a counter, a device ID with a small fleet) turn into a single node or partition eating 100% of the traffic while the rest of the cluster sits idle, and wants to know if you can name that failure before it happens, not just debug it after a page. They've also watched a team commit hard to DynamoDB single-table design from a blog post, discover eighteen months later that a new access pattern requires a schema migration across billions of items, and want to know if you'll recommend the trendy pattern or the honest one for the actual constraints in front of you.

---

## Lineage: past → present → future

**What came before.** Amazon's 2007 Dynamo paper and Google's 2006 Bigtable paper are the two lineages wide-column stores actually descend from: Dynamo contributed the consistent-hashing ring, tunable quorum-based consistency, and eventual consistency with conflict resolution (vector clocks, later simplified); Bigtable contributed the sparse, sorted, column-family data model (a row is a map of maps, sorted by row key, columns grouped into families) built on an LSM-tree storage engine. Cassandra (built at Facebook, open-sourced 2008) explicitly combined both: Bigtable's data model on top of Dynamo's distribution model. The pain that drove this combination away from single-master relational replication: a single-master database's write throughput and availability are capped by that one master, and cross-datacenter relational replication at Amazon/Google/Facebook scale in the mid-2000s could not deliver the write availability those companies needed during network partitions and node failures — CAP-theorem tradeoffs (see `T17-oltp-vs-olap` for the broader OLTP consistency landscape) became something you tuned per-request instead of something the database imposed uniformly.

**Where it stands now.** Cassandra (via DataStax and the open-source Apache project) and DynamoDB (AWS's fully-managed descendant of the original Dynamo paper, not literally the same codebase) are the two dominant production wide-column systems, and the consensus is sharp: they trade joins, secondary-index flexibility, and cheap ad hoc queries for horizontal write scalability and predictable per-partition latency, and are the right choice exactly when your access patterns are known, stable, and write-heavy at a scale where a single-master relational system's write throughput becomes the bottleneck. The live disagreement is over **how much modeling discipline is actually worth it upfront**: Cassandra requires you to design tables around queries from day one (there is no cheap way to add a new access pattern later without a new table or a materialized view with its own consistency caveats), and DynamoDB's single-table design pushes this even further, collapsing multiple entity types into one table keyed by generic partition/sort key attributes — proponents point to real cost and latency wins at scale, critics (including practitioners at AWS and independent consultants) point out that most teams don't actually have the stable, fully-enumerated access patterns single-table design assumes, and pay a real comprehensibility and flexibility cost for a theoretical efficiency gain they may never need. What's actually deployed at scale: many production DynamoDB systems use a handful of purpose-built tables rather than one single table, reserving true single-table design for the specific subsystems where access patterns are genuinely locked down (e.g., a well-understood entity graph like "users, their orders, and order items").

**Where it's heading.** DynamoDB's throughput model has moved toward more automatic elasticity — on-demand capacity mode (billed per request, auto-scaling with no explicit provisioning) is now a common default for unpredictable or spiky workloads, and adaptive capacity (automatically shifting a partition's *isolated* throughput allowance up to the hard per-partition physical caps) has made some classes of moderate skew self-healing without operator intervention — but the physical per-partition ceiling (3,000 RCU/s, 1,000 WCU/s) is a hard architectural constant, not a tunable, so partition key design discipline remains non-optional regardless of how much AWS automates around the edges. Cassandra's evolution (4.x and beyond) has focused on operational maturity (better repair, virtual tables for introspection, ZGC support) rather than any fundamental data-model change; the core partition-key discipline hasn't changed since the original Bigtable/Dynamo lineage and there's no credible sign it will, since it follows directly from the physics of "co-locate related data for one round-trip access."

---

## Mental model

```
CASSANDRA RING (consistent hashing, RF=3)

         Node A (tokens 0-99)
        /                    \
  Node F                      Node B (tokens 100-199)
     |                            |
  Node E                      Node C (tokens 200-299)
        \                    /
         Node D (tokens 300-399, wraps to 0)

  hash(partition_key) -> a token -> walk the ring clockwise -> first 3
  DISTINCT nodes encountered = the 3 replicas for that partition key
  (RF=3). Every row sharing that partition key lives on the SAME 3 nodes.

HOT PARTITION FAILURE

  Good key: hash(user_id) spreads ~evenly across the ring -> every node
            gets a proportional share of both storage and request load.

  Bad key:  hash(tenant_id) where tenant_id=7 (one huge customer) sends
            80% of all reads/writes to the SAME 3 replica nodes.
  Symptom:  1 node (or a 3-node replica set) pegged at 100% CPU/disk IO,
            p99 latency spiking cluster-wide (coordinator overhead),
            while nodes NOT holding that partition report idle-looking
            metrics. "The cluster looks healthy except one node is on fire."

R+W>N ARITHMETIC (Cassandra tunable consistency)

  N = replication factor (how many nodes hold a copy)
  W = nodes that must ACK a write before it succeeds
  R = nodes that must respond to a read before it returns
  R + W > N  =>  every read set and every write set overlaps by >=1 node
             =>  a read is GUARANTEED to see the most recent write
  RF=3, W=QUORUM(2), R=QUORUM(2): 2+2=4 > 3 -> strong consistency
  RF=3, W=ALL(3),    R=ONE(1):    3+1=4 > 3 -> strong, but W=ALL kills
                                   write availability during ANY node down
  RF=3, W=ONE(1),    R=ONE(1):    1+1=2 < 3 -> NO overlap guarantee,
                                   fastest, eventually consistent only
```

---

## How it actually works

### The wide-column data model: table per query, not per entity

A wide-column table is a sorted map of maps: rows are identified by a **partition key** (determines which node(s) hold the row) plus an optional **clustering key** (determines sort order *within* the partition). Unlike a normalized relational schema, there is no cheap join — a query that needs data from two differently-partitioned entities requires two round trips (or denormalizing one into the other at write time). The consequence: schema design starts from **"what are my queries"**, not **"what are my entities."** A `users` table and an `orders_by_user` table (partitioned by `user_id`, clustered by `order_date`) might both contain a duplicated copy of the user's name, because storing it once normalized would require a join Cassandra doesn't do cheaply. This is the single biggest mental shift from relational design: **denormalization is the default, not an optimization applied later.**

```sql
-- Cassandra CQL: query-first schema. This table exists ONLY to serve
-- "get a user's orders sorted by date" -- nothing else.
CREATE TABLE orders_by_user (
    user_id    UUID,
    order_date TIMESTAMP,
    order_id   UUID,
    total      DECIMAL,
    status     TEXT,
    PRIMARY KEY (user_id, order_date)   -- user_id = partition key,
) WITH CLUSTERING ORDER BY (order_date DESC);  -- order_date = clustering key
-- "get orders by status" needs a SEPARATE table (orders_by_status),
-- populated by writing to both tables at insert time (denormalization),
-- or a secondary index (works, but has real performance caveats at scale).
```

### Partition key design and the hot-partition failure

The partition key's hash determines which physical nodes own a row (Cassandra: consistent hashing around a token ring; DynamoDB: an internal partitioning scheme AWS manages, conceptually the same hashing idea). **Every row sharing a partition key lives together, on the same replica set, forever** (barring a resharding/repartitioning operation). This creates two distinct risks:

1. **Skewed key cardinality**: a partition key with too few distinct values (a `status` column, a `region` with 4 possible values, a boolean) concentrates all rows with the popular value on one replica set regardless of overall cluster size — adding nodes doesn't help because the key space you're hashing over hasn't gotten any wider.
2. **Skewed access pattern on an otherwise fine key**: a partition key that's well-distributed in cardinality but not in *traffic* — a multi-tenant system partitioned by `tenant_id` where one enterprise customer generates 1000x the request volume of everyone else — produces the same symptom even with a "good" key by cardinality standards.

**Observable symptom:** one node (or one replica set) at or near 100% CPU/disk I/O while the rest of the cluster's nodes report idle-to-moderate load; cluster-wide p99 latency degrades because the coordinator node for the hot partition's requests becomes a bottleneck even for requests it's merely routing. `nodetool tablestats`/`nodetool toppartitions` in Cassandra, or CloudWatch's per-partition throttling metrics in DynamoDB, are the standard tools to confirm a hot-partition diagnosis versus a generic capacity problem.

**The fix is architectural, not tunable**: add entropy to the partition key. A common pattern is **key salting/sharding**: append a random or hashed suffix (`tenant_id#shard_0` through `tenant_id#shard_9`) to spread one logical entity's rows across multiple physical partitions, at the cost of needing to fan out reads across all shards and merge results client-side when you need the full logical partition's data. For time-series data with a natural hot-partition risk (all of "today's" writes hitting one partition), bucketing by a coarser time window plus an entropy suffix (`device_id#2026-08-01#03` for hour-bucketed data) is the standard mitigation.

### Cassandra's ring, replication factor, tunable consistency

Cassandra assigns each node a range of hash tokens on a ring (consistent hashing, so adding/removing nodes only reshuffles a fraction of the keyspace, not everything). A **replication factor (RF)** of *N* means each partition key's data is stored on *N* distinct nodes, found by walking the ring clockwise from the key's token until *N* distinct nodes are encountered. Every read and write specifies a **consistency level** independently — `ONE`, `QUORUM` (`⌊N/2⌋ + 1`), `LOCAL_QUORUM` (quorum within the local datacenter only, for multi-DC clusters), `ALL` — and the **R + W > N** inequality is the precise condition under which a read is guaranteed to overlap with the most recent write's replica set, guaranteeing it observes that write (strong consistency in the "read your writes across any client" sense, not full linearizability). `RF=3, W=QUORUM(2), R=QUORUM(2)` (2+2=4>3) is the standard "strong enough, still available with one node down" default; `RF=3, W=ONE, R=ONE` (1+1=2, not >3) is eventually-consistent-only but the fastest and most available option, appropriate when a stale read is an acceptable cost (a view counter, a non-critical cache).

### Compaction strategies and their tradeoffs

Cassandra's SSTables (immutable, sorted, written on flush from the memtable, an LSM-tree design — see `T17-storage-engines`) accumulate multiple versions of the same row across different SSTables as updates and deletes happen; **compaction** merges SSTables to reclaim space and collapse row versions. The three strategies trade differently:

| Strategy | Mechanism | Best for | Cost |
|---|---|---|---|
| **SizeTieredCompactionStrategy (STCS)** | Merges SSTables of similar size once enough accumulate | Write-heavy workloads, default | Can temporarily need up to 2x disk space during a large compaction; read amplification grows as uncompacted SSTable count grows |
| **LeveledCompactionStrategy (LCS)** | Organizes SSTables into levels of fixed size (~160MB per SSTable), each level ~10x the previous | Read-heavy workloads needing predictable, low read amplification | Significantly higher write amplification (each row can be rewritten many more times across its lifetime as it's promoted through levels) |
| **TimeWindowCompactionStrategy (TWCS)** | Groups SSTables by time window, compacting only within a window | Time-series/TTL-heavy data where whole time windows expire together | Poor fit for data with unpredictable update patterns across time windows; excellent, predictable expiry for the workload it targets |

### Tombstones and the deleted-data read-latency trap

A `DELETE` in Cassandra does not remove data immediately — it writes a **tombstone** (a delete marker with its own timestamp) that must survive until `gc_grace_seconds` (default 10 days) has passed and compaction has run, to give the delete time to propagate to all replicas before physical removal (skipping this window risks a "zombie" row reappearing if a replica that missed the delete gets read from). **The trap**: a workload that does heavy TTL-based deletes or explicit deletes on a partition that's also read frequently accumulates tombstones the read path must scan past to find live data — a read scanning a partition with a very large number of tombstones can time out or trigger `tombstone_warn_threshold`/`tombstone_failure_threshold` warnings/errors in the logs, a distinct, commonly-misdiagnosed failure mode that looks like "the query is slow" but is actually "the query is reading through millions of graves to find a handful of living rows."

### DynamoDB: partitions, adaptive capacity, LSI vs GSI, on-demand vs provisioned

DynamoDB hides its ring behind managed partitions but the physical limits are hard and documented: a single partition caps out at **3,000 read capacity units/sec or 1,000 write capacity units/sec** (approximately, and shared between the two proportionally), and a table adds partitions automatically when provisioned throughput is raised beyond current partition capacity, an on-demand table's traffic hits a new high-water mark, or a partition approaches roughly **10GB** of stored data. **Adaptive capacity** automatically reallocates a table's *aggregate* provisioned throughput toward a hot partition, but it cannot raise that partition's *physical* ceiling above the hard per-partition caps — it smooths moderate skew, it does not fix a partition key with severe, sustained skew past the physical limit.

**LSI vs GSI**, the sharpest constraint in the whole model: a **Local Secondary Index (LSI)** shares the base table's partition key and offers an alternate sort key, but it must be created at table-creation time (cannot be added later) and its **item collection (base table item + all its LSI entries, per partition key) is capped at 10GB** — exceeding it is a hard write failure, not a performance degradation. A **Global Secondary Index (GSI)** has its own partition key (and thus its own separate partitioning/scaling), can be added or removed after table creation, but is **eventually consistent** and has its own provisioned/on-demand throughput that can throttle independently of the base table — and critically, **a throttled GSI write blocks the corresponding base table write**, even if the base table itself has ample spare capacity, because DynamoDB propagates writes to GSIs synchronously as part of the write path's acceptance, not as a fully decoupled async process.

**On-demand vs provisioned**: provisioned capacity requires pre-declaring RCU/WCU (with optional auto-scaling reacting to utilization with some lag) and is cheaper per-request at steady, predictable volume; on-demand bills per-request with no pre-declaration and adapts to spiky/unpredictable traffic instantly, at a materially higher per-request cost, and is the safer default for a new or highly variable workload until real traffic patterns are known.

### Single-table design, assessed honestly

Single-table design collapses multiple logical entity types (users, orders, order items) into one physical DynamoDB table using generic attribute names (`PK`, `SK`) and overloaded key patterns (`PK=USER#123`, `SK=ORDER#456`) so that a single `Query` call can retrieve a user and all their related entities in one round trip instead of several. **What it buys**: fewer round trips per logical operation (a 3-entity fetch collapses from 3 `GetItem`/`Query` calls to 1), and — because DynamoDB provisioned capacity is allocated per table, and teams typically over-provision by 20-30% as a safety buffer — consolidating N tables into one means paying that buffer once instead of N times, a real cost saving under provisioned capacity specifically (on-demand capacity mostly removes this particular argument). **What it costs**: the resulting table's key structure is genuinely hard to read (described by practitioners as looking "more like machine code than a spreadsheet"), a schema change to one entity's key pattern risks breaking another team's queries against the same table, ad hoc analytical queries (the kind a BI tool or a data scientist would run) become materially harder against a denormalized, overloaded-key table than against several clean tables, and adding a genuinely new access pattern not anticipated at design time can require a full-table migration rather than a localized schema change. **Why most teams should not do it**: single-table design assumes you have already enumerated your access patterns fully and they are stable — a fair assumption for a narrow, mature subsystem, a poor assumption for a product still finding its access patterns, or one shared across multiple teams who don't coordinate on schema changes. The pragmatic default most experienced DynamoDB practitioners now recommend is starting with more, simpler, per-entity tables and consolidating specific hot paths into single-table patterns only once the cost or latency case is concretely demonstrated, not applying it as a default up front.

---

## Build it from scratch

A minimal hash-ring simulator demonstrating consistent hashing, replica placement, and the hot-partition failure mode:

```python
# untested sketch
import bisect
import hashlib

class ConsistentHashRing:
    def __init__(self, nodes: list[str], vnodes_per_node: int = 100):
        self.ring: dict[int, str] = {}
        self.sorted_tokens: list[int] = []
        for node in nodes:
            for v in range(vnodes_per_node):
                token = self._hash(f"{node}#{v}")
                self.ring[token] = node
        self.sorted_tokens = sorted(self.ring.keys())

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def get_replicas(self, partition_key: str, rf: int) -> list[str]:
        token = self._hash(partition_key)
        idx = bisect.bisect(self.sorted_tokens, token) % len(self.sorted_tokens)
        replicas = []
        seen = set()
        while len(replicas) < rf and len(seen) < len(self.sorted_tokens):
            candidate = self.ring[self.sorted_tokens[idx]]
            if candidate not in seen:
                seen.add(candidate)
                replicas.append(candidate)
            idx = (idx + 1) % len(self.sorted_tokens)
        return replicas

# Demonstrate the hot-partition failure: skewed key cardinality
ring = ConsistentHashRing(nodes=["n1", "n2", "n3", "n4", "n5"])

# Good key: high-cardinality, evenly distributed
from collections import Counter
good_key_load = Counter()
for user_id in range(100_000):
    primary_replica = ring.get_replicas(f"user#{user_id}", rf=3)[0]
    good_key_load[primary_replica] += 1
print("Good key distribution:", good_key_load)  # roughly even across 5 nodes

# Bad key: low-cardinality tenant_id, one tenant dominates traffic
bad_key_load = Counter()
tenant_weights = {"tenant_1": 80_000, "tenant_2": 5_000, "tenant_3": 5_000,
                   "tenant_4": 5_000, "tenant_5": 5_000}
for tenant, request_count in tenant_weights.items():
    primary_replica = ring.get_replicas(tenant, rf=3)[0]
    bad_key_load[primary_replica] += request_count
print("Bad key distribution:", bad_key_load)  # one node gets 80% of ALL traffic
```

Running this shows the good-key case spreading load within a few percent across all 5 nodes, and the bad-key case dumping 80% of simulated request volume onto whichever single node happens to own `tenant_1`'s token — the exact shape of the production hot-partition failure, just without the paging alert. Full version with R+W>N quorum simulation and salted-key sharding as the fix: **`labs/py/09-wide-column-lab/`**.

---

## How it's done in production

**Diagnosing a hot partition.** Cassandra: `nodetool tablestats` for per-table read/write latency and `nodetool toppartitions` (or, more precisely, sampling via `nodetool profileload`/large-partition warnings in the logs) to identify the specific offending partition key. DynamoDB: CloudWatch `ThrottledRequests` and per-partition consumed-capacity metrics; AWS also publishes internal partition-count and per-partition-throughput heuristics via `DescribeTable` in some contexts, but the practical diagnostic loop is usually "throttling correlates with one known high-traffic key" plus application-level logging of request keys.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| One Cassandra node at ~100% CPU/IO while the rest of the cluster looks idle | Hot partition: low-cardinality or traffic-skewed partition key concentrating rows/requests on one replica set | Salt the partition key (append a shard suffix) and fan out reads across shards; redesign the key around a higher-cardinality, evenly-trafficked attribute |
| DynamoDB `ProvisionedThroughputExceededException` / throttling on a specific key range despite ample table-level capacity | Per-partition physical cap (3,000 RCU/s or 1,000 WCU/s) exceeded on one partition; adaptive capacity smooths moderate skew but cannot exceed the hard cap | Redesign the partition key for higher cardinality/even traffic, or pre-shard a known-hot logical key |
| A read on a partition with heavy delete/TTL history times out or logs tombstone warnings | Read scanning past a large number of tombstones to find live rows before `gc_grace_seconds` compaction has cleared them | Reduce partition size, use TWCS for TTL-heavy time-series data so whole expired windows compact away together, tune `gc_grace_seconds` deliberately (never to 0 without understanding the replica-repair risk) |
| DynamoDB base table writes throttle even though the base table itself has spare capacity | A GSI is under-provisioned relative to write volume; GSI writes are synchronous with base table writes and a throttled GSI blocks the base table write | Provision the GSI for the actual write volume, or move to on-demand capacity mode if traffic is unpredictable |
| Adding an LSI-backed access pattern later in a table's life is impossible without recreating the table | LSIs must be declared at table-creation time and cannot be added afterward | Add the access pattern via a GSI instead (addable after creation), accepting eventual consistency, or plan LSI needs fully at design time |
| A single-table DynamoDB design breaks a second team's queries after a schema tweak | Overloaded generic keys (`PK`/`SK`) shared across unrelated entity types with no per-team isolation | Document key-pattern ownership explicitly, or default to per-entity tables for teams/subsystems that don't share tightly coordinated access patterns |
| A large Cassandra compaction unexpectedly exhausts disk space | STCS can require up to ~2x the affected SSTables' size in free disk space during a large compaction | Keep meaningful headroom (commonly 50% free disk as a rule of thumb) on Cassandra data volumes, or use LCS/TWCS where their tradeoffs fit the workload better |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a wide-column store when your access patterns are still unknown or rapidly changing.** The entire model assumes you know your queries at schema-design time; a relational database's ability to add an index or a join for a newly-discovered query pattern without a data migration is a real advantage during early-stage product development.
- **Don't use a low-cardinality or traffic-skewed column as a partition key**, ever, regardless of how "natural" it feels (status, region, a single "global" counter row) — it is the single most common cause of production hot-partition incidents in both Cassandra and DynamoDB.
- **Don't default to single-table design for DynamoDB.** It is a powerful, deliberate technique for a small number of stable, fully-enumerated access patterns at meaningful scale, not a best practice to apply reflexively; most teams are better served starting with clean per-entity tables and consolidating only once a concrete cost or latency justification exists.
- **Don't run heavy delete/TTL churn on a partition that's also read-hot** without accounting for tombstone accumulation; a time-series compaction strategy (TWCS) or a redesigned partition granularity is usually the right answer, not raising timeout thresholds.
- **Don't pick provisioned DynamoDB capacity for a new, poorly-understood workload.** On-demand costs more per request but avoids under-provisioning throttling and over-provisioning waste while the real traffic shape is still being learned; move to provisioned once the pattern stabilizes and the cost delta justifies the operational tuning.
- **Don't use Cassandra or DynamoDB for workloads needing ad hoc analytical queries, multi-row transactions across arbitrary keys, or strong joins** — that's squarely a relational or OLAP-store problem (see `T17-postgres`, `T17-oltp-vs-olap`, `T17-clickhouse`); wide-column stores are not a general-purpose replacement for either.

---

## Interview questions

### Q1 — Why does wide-column schema design start from queries instead of entities?
**Testing:** baseline model understanding.
**Answer:** There's no cheap join and no free secondary access path by default; a query needing data shaped differently from how it's stored requires either a second round trip or duplicating the data into a table shaped for that query at write time. So the design process is: enumerate access patterns first, then build one table per pattern, denormalizing as needed — the inverse of normalized relational design.
**Follow-up trap:** *"Doesn't that mean you're duplicating data everywhere?"* — yes, deliberately; the tradeoff is accepting write-time duplication and eventual/application-managed consistency between the duplicates in exchange for every read being a single-partition operation with predictable latency, which is the entire point of the model.

### Q2 — What is a hot partition, precisely, and what's the observable symptom?
**Answer:** A partition key whose cardinality or traffic distribution concentrates a disproportionate share of rows or requests onto one replica set (one node or a small group of nodes), because every row with the same partition key lives together permanently. Symptom: one node (or replica set) pegged near 100% CPU/disk I/O while the rest of the cluster reports idle-to-moderate load, and cluster-wide p99 latency can degrade even for unrelated requests due to coordinator overhead.
**Follow-up trap:** *"Adding more nodes should fix it, right?"* — no, if the partition key's cardinality is the problem (not raw cluster capacity), adding nodes doesn't help because the hot key still hashes to the same replica set; the fix is architectural (redesign or salt the key), not operational.

### Q3 — Explain R + W > N and give two concrete consistency-level combinations with their tradeoffs.
**Answer:** N is the replication factor; W and R are how many replicas must ack a write or respond to a read, chosen per request. When R + W > N, every possible read-replica-set and write-replica-set overlap by at least one node, guaranteeing a read observes the most recent committed write. RF=3, W=QUORUM(2), R=QUORUM(2): 2+2=4>3, strong consistency and tolerates one node down. RF=3, W=ONE, R=ONE: 1+1=2, not >3, fastest and most available but only eventually consistent.
**Follow-up trap:** *"If R+W>N, is that the same guarantee as serializability?"* — no; it guarantees a single read sees the latest acknowledged write (a form of consistency per key), not multi-key transactional isolation or ordering guarantees across different keys or operations — don't conflate it with the isolation-level guarantees covered in `T17-mvcc-isolation`.

### Q4 — Compare STCS, LCS, and TWCS compaction strategies and when you'd choose each.
**Answer:** STCS (default) merges similarly-sized SSTables, good for general write-heavy workloads but can transiently need up to ~2x disk space during large compactions and has growing read amplification as SSTable count grows. LCS organizes SSTables into fixed-size levels for predictable, low read amplification, at the cost of significantly higher write amplification from repeated rewrites as data is promoted through levels — good for read-heavy workloads. TWCS groups SSTables by time window so whole expired windows compact away together, ideal for TTL-heavy time-series data, poor fit for unpredictable update patterns across time.
**Follow-up trap:** *"Why would LCS's higher write amplification matter if disk is cheap?"* — it's not disk space that's the cost, it's the I/O and CPU spent rewriting the same logical row multiple times as it's promoted through levels, which competes with foreground write/read traffic on the same nodes — a real throughput cost, not just a storage one.

### Q5 — What's the tombstone read-latency trap and how do you avoid it?
**Answer:** A DELETE writes a tombstone rather than removing data immediately, retained until `gc_grace_seconds` (default 10 days) and compaction clear it, to let the delete propagate to all replicas safely. A partition with heavy delete/TTL churn accumulates tombstones the read path must scan past to find live rows, which can time out or trip tombstone warning/failure thresholds — looking like a generic slow query but actually being "scanning graves to find survivors."
**Follow-up trap:** *"Why not just set gc_grace_seconds to 0 to clear tombstones faster?"* — that removes the safety window that lets deletes propagate to replicas that were down or partitioned when the delete happened, risking a deleted row reappearing (a "zombie") when that replica comes back and gets read from before it's caught up via repair.

### Q6 — What is DynamoDB adaptive capacity, and what can't it fix?
**Answer:** It automatically reallocates a table's aggregate provisioned throughput toward a partition receiving disproportionate traffic, smoothing moderate, temporary skew without manual intervention. It cannot raise a single partition's throughput above the hard physical caps (3,000 RCU/s, 1,000 WCU/s) — severe, sustained skew past those caps still throttles regardless of adaptive capacity or how much spare aggregate table capacity exists elsewhere.
**Follow-up trap:** *"So what do you do once adaptive capacity's ceiling is hit?"* — redesign the partition key for higher cardinality or more even traffic distribution (key salting/sharding), since no capacity-mode setting changes the physical per-partition ceiling.

### Q7 — Explain the LSI 10GB item collection constraint and why it matters at design time.
**Answer:** An LSI shares the base table's partition key with an alternate sort key; the item collection (the base table item plus all its LSI index entries, per partition key value) is capped at 10GB, and exceeding it is a hard write failure, not a slow query. LSIs must also be declared at table creation and cannot be added later.
**Follow-up trap:** *"What if you realize after launch you need an LSI-style access pattern?"* — you can't add an LSI to an existing table; use a GSI instead (addable after creation, own partition key, own scaling) and accept its eventual consistency, or plan the LSI need fully during initial design since retrofitting it means a full table migration.

### Q8 — Why can a throttled GSI block writes to a healthy, well-provisioned base table?
**Answer:** DynamoDB propagates writes to GSIs synchronously as part of accepting the base table write, not as a fully decoupled asynchronous process; if the GSI's own provisioned/on-demand capacity throttles, the base table write is rejected too, even though the base table itself has ample spare capacity.
**Follow-up trap:** *"Doesn't 'eventually consistent GSI' imply async replication, so why would it block synchronously?"* — eventual consistency describes read visibility (a GSI read might not reflect the very latest base table write yet), not the write acceptance path; the write itself must still be accepted into the GSI's own capacity model before the base table write completes, which is the part that can throttle.

### Q9 — Assess single-table design honestly: what does it buy, what does it cost, and when should a team not use it?
**Testing:** the module's central "resume-facing" judgment question.
**Answer:** It buys fewer round trips per logical operation (collapsing several `GetItem`/`Query` calls into one) and, under provisioned capacity specifically, avoids paying the per-table over-provisioning safety buffer N times over. It costs real comprehensibility (overloaded generic keys read like machine code, not a spreadsheet), cross-team schema fragility (one team's key-pattern change can silently break another team's queries on the shared table), and much harder ad hoc analytical access. Teams should not default to it unless their access patterns are already fully enumerated and stable — most product teams still discovering their access patterns, or with multiple uncoordinated teams sharing a table, are better served by simpler per-entity tables.
**Follow-up trap:** *"If it's mostly downside for most teams, why does it get recommended so often?"* — because the cost/benefit genuinely favors it at the specific scale and stability profile of the teams (often at large tech companies) who popularized the pattern in blog posts and conference talks, and that context doesn't transfer to a smaller team or an evolving product — a classic case of a scale-specific optimization being generalized past where it actually applies.

### Q10 — Design the partition key for a time-series IoT ingestion table where a naive design (device_id as partition key) creates hot partitions for high-frequency devices.
**Answer:** Compound the partition key with a coarser time bucket and, if needed, an entropy suffix — e.g., `device_id#2026-08-01#03` (hourly bucket) or `device_id#shard_N` for a fixed number of shards per device — trading a fan-out read (querying all shards for a device and merging client-side, or a bounded number of hourly buckets for a time range) for spreading both storage and request load across more physical partitions.
**Follow-up trap:** *"How do you decide the number of shards or the time-bucket granularity?"* — based on the actual measured write rate per device against the per-partition physical ceiling (DynamoDB's 1,000 WCU/s, or Cassandra's practical per-partition guidance), not a round number picked upfront; under-sharding leaves the hot-partition risk, over-sharding adds unnecessary fan-out cost on every read.

### Q11 — When would you choose Cassandra over DynamoDB, or vice versa, for a new system?
**Answer:** DynamoDB when you want a fully-managed system with no operational burden (no repair, no compaction tuning, no node management) and are comfortable with AWS lock-in and its specific constraints (LSI limits, GSI propagation behavior, per-partition physical caps); Cassandra when you need multi-cloud or on-prem portability, tunable consistency at a finer grain than DynamoDB exposes, or workloads where the operational cost of running Cassandra is justified by avoiding AWS-specific constraints or costs at very large scale.
**Follow-up trap:** *"Isn't DynamoDB just 'managed Cassandra'?"* — no; despite a shared Dynamo-paper lineage in spirit, they have materially different consistency models (Cassandra's per-request tunable R/W consistency levels vs DynamoDB's simpler eventually-consistent/strongly-consistent read toggle), different secondary-index mechanics (LSI/GSI vs Cassandra's secondary indexes and materialized views), and different operational models entirely — treating them as interchangeable is a real interview red flag.

### Q12 — A multi-tenant SaaS table on DynamoDB has one enterprise customer generating far more traffic than the rest combined. Diagnose and fix.
**Answer:** This is a traffic-skew hot partition even if `tenant_id` has fine cardinality overall — one value dominates request volume. Diagnose via CloudWatch throttling metrics correlated to that tenant's key range. Fix: shard that specific tenant's partition key with a suffix (`tenant_id#shard_N`) sized to its actual traffic, fanning out reads across the shards and merging, while leaving low-traffic tenants unsharded; a blanket sharding scheme for all tenants would add unnecessary fan-out overhead for the tenants that don't need it.
**Follow-up trap:** *"Why not just give every tenant their own DynamoDB table instead?"* — viable and simpler operationally for a moderate tenant count, but table-per-tenant multiplies the per-table provisioned-capacity overprovisioning cost discussed earlier and can hit account-level table-count limits at high tenant counts; the right choice depends on tenant count and the actual skew profile, not a universal answer either way.

---

## Red flags that fail you

- Choosing a boolean, status, or otherwise low-cardinality column as a partition key without flagging the hot-partition risk.
- Believing adding more nodes/capacity fixes a hot partition caused by key cardinality rather than raw volume.
- Not knowing that LSIs must be declared at table creation and are capped by the 10GB item-collection limit.
- Claiming DynamoDB and Cassandra have the same consistency model just because both trace to the Dynamo paper.
- Recommending single-table design as a default best practice without naming its real comprehensibility and flexibility costs.
- Not knowing that a throttled GSI can block base table writes.
- Confusing R+W>N (per-key read/write consistency) with transactional isolation or serializability.

---

## Cheat card

```
MODEL              Partition key = physical placement, clustering key = sort order
                   WITHIN partition. No cheap join -> denormalize at write time.
                   Design order: enumerate QUERIES first, then build 1 table/query.

HOT PARTITION      All rows sharing a partition key live on the SAME replica set,
                   forever. Symptom: 1 node/replica-set at ~100% CPU/IO, rest of
                   cluster looks idle; cluster-wide p99 degrades via coordinator
                   overhead. Causes: low-cardinality key OR traffic-skewed key.
                   FIX: salt/shard the key (tenant_id#shard_N), fan out + merge.
                   Adding nodes does NOT fix a cardinality-caused hot partition.

CASSANDRA RING     Consistent hashing -> RF=N distinct nodes per key (walk ring
                   clockwise). Per-request tunable consistency:
                   R+W>N  => read guaranteed to see latest write.
                   RF3/W=QUORUM(2)/R=QUORUM(2): 2+2=4>3, strong, survives 1 down.
                   RF3/W=1/R=1: 1+1=2, NOT >3, fastest, eventual only.

COMPACTION         STCS (default): merge similar-size SSTables, up to ~2x disk
                     during big compactions, read amp grows with SSTable count.
                   LCS: fixed-size levels (~160MB/SSTable), low read amp, HIGH
                     write amp (repeated rewrites through levels).
                   TWCS: group by time window, best for TTL-heavy time-series.

TOMBSTONES         DELETE = marker, not removal. Survives gc_grace_seconds
                   (default 10 days) for replica-repair safety. Heavy delete/TTL
                   churn on a hot-read partition -> read scans past tombstones ->
                   timeout / tombstone_warn/failure_threshold in logs.

DYNAMODB LIMITS    Per-partition HARD cap: 3,000 RCU/s or 1,000 WCU/s.
                   Adaptive capacity smooths skew UP TO that cap, not past it.
                   New partition added at ~10GB stored or new throughput high-water.
                   LSI: shares base PK, altSK, MUST declare at table creation,
                     10GB item-collection cap (base+LSI), hard write failure if hit.
                   GSI: own PK, addable later, eventually consistent reads, own
                     capacity -> THROTTLED GSI BLOCKS BASE TABLE WRITE (sync path).
                   On-demand: per-request billing, instant elasticity, costs more/req.
                   Provisioned: pre-declared RCU/WCU, cheaper at steady volume.

SINGLE-TABLE       Buys: fewer round trips, 1x overprovision buffer not Nx (under
                     provisioned capacity specifically).
                   Costs: unreadable overloaded keys, cross-team schema fragility,
                     hard ad hoc analytics, expensive to add unanticipated patterns.
                   Use ONLY for stable, fully-enumerated access patterns at scale.
                   Default for most teams: simpler per-entity tables.
```

## Sources

- [Cassandra Distributed Data — AxonOps](https://axonops.com/docs/data-platforms/cassandra/architecture/distributed-data/) — accessed 2026-08-01
- [Apache Cassandra Data Partitioning — Instaclustr](https://www.instaclustr.com/blog/cassandra-data-partitioning/) — accessed 2026-08-01
- [Managing Tombstones in Apache Cassandra — Instaclustr](https://www.instaclustr.com/support/documentation/cassandra/using-cassandra/managing-tombstones-in-cassandra/) — accessed 2026-08-01
- [Configuring compaction — DataStax Cassandra 3.0 Docs](https://docs.datastax.com/en/cassandra-oss/3.0/cassandra/operations/opsConfigureCompaction.html) — accessed 2026-08-01
- [Read/Write Quorums and the Algebra of Consistency — Java Code Geeks](https://www.javacodegeeks.com/2026/07/read-write-quorums-and-the-algebra-of-consistency-why-n-r-and-w-arent-just-configuration-knobs.html) — accessed 2026-08-01
- [DynamoDB burst and adaptive capacity — AWS Docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/burst-adaptive-capacity.html) — accessed 2026-08-01
- [1- Key range throughput exceeded (hot partitions) — AWS Docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/throttling-key-range-limit-exceeded-mitigation.html) — accessed 2026-08-01
- [In DynamoDB, what's partition size limitation of a table without LSI — AWS re:Post](https://repost.aws/questions/QUx0mIILjaR5GjwYllYNpbKA/in-dynamodb-what-s-partition-size-limitation-of-a-table-without-lsi) — accessed 2026-08-01
- [The What, Why, and When of Single-Table Design with DynamoDB — Alex DeBrie](https://www.alexdebrie.com/posts/dynamodb-single-table/) — accessed 2026-08-01
- [Single table design for DynamoDB: The reality — Momento](https://www.gomomento.com/blog/single-table-design-for-dynamodb-the-reality/) — accessed 2026-08-01
- [Single-Table vs Multi-Table Design in Amazon DynamoDB — AWS Database Blog](https://aws.amazon.com/blogs/database/single-table-vs-multi-table-design-in-amazon-dynamodb/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
