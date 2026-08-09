# Blob/Files/Queues, Cosmos DB Consistency, Azure SQL, PostgreSQL Flexible Server

> **Track:** C-AZ Azure Atlas · **Time:** 2.5h · **Prereqs:** `C-AZ-identity`, `C-AZ-compute` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-storage-db` · **Tags:** storage

## The 30-second version

Azure splits storage into a general-purpose account family (**Blob**, **Files**, **Queues**, **Tables** — all billed and replicated through the same storage-account chassis) and a separate database family with genuinely different consistency and scaling models. **Blob Storage** has five access tiers (Hot/Cool/Cold/Archive plus Premium) trading per-GB storage cost against per-transaction/retrieval cost, and six redundancy options (LRS/ZRS/GRS/RA-GRS/GZRS/RA-GZRS) trading durability and read availability against roughly 1x-2.5x cost multipliers over LRS. **Cosmos DB** is the interview centerpiece: it's the only mainstream managed database offering **five distinct, tunable consistency levels** (Strong, Bounded Staleness, Session, Consistent Prefix, Eventual) rather than the binary strong-or-eventual choice DynamoDB and most others give you, and the levels aren't free — Strong and Bounded Staleness reads cost **2x the RUs** of Session/Consistent Prefix/Eventual because they require reading from a quorum of replicas instead of one. **Azure SQL** splits into Hyperscale (storage/compute separated, up to 128 TB, near-instant backups via storage snapshots) and Business Critical/General Purpose (traditional attached storage, much lower ceilings). **PostgreSQL Flexible Server** is Microsoft's recommended default Postgres deployment (Single Server is deprecated), running 40-45% cheaper than Azure SQL at equivalent vCore count, with a separate **Hyperscale (Citus)** deployment option for horizontal sharding when a single Postgres instance's vertical ceiling isn't enough. The trap that catches AWS engineers hardest: Cosmos DB's consistency model has no direct DynamoDB equivalent — DynamoDB gives you eventually-consistent or strongly-consistent reads as a per-request toggle with no cost difference; Cosmos DB's five-level spectrum is a database-level (overridable per-request) configuration with materially different RU economics at each level.

## Why this gets asked

The interviewer has watched a team default to Cosmos DB's Session consistency without understanding what they were trading away, has debugged an application that silently read stale data because a client outside the original session lost session-token continuity, has explained why a 20GB logical partition suddenly stopped accepting writes with no warning, and has migrated a team off Single Server PostgreSQL under deprecation pressure. They want to know you can reason about consistency as a cost-and-correctness tradeoff with real numbers attached, not recite "Cosmos DB has multiple consistency levels" as a factoid.

---

## Lineage: past → present → future

**What came before.** Azure's original NoSQL offering was DocumentDB (2014), a MongoDB-API-compatible document store with a single consistency model. The pain that killed it: global applications needed to trade off latency against correctness differently per use case (a shopping cart tolerates eventual consistency; a financial ledger doesn't), and forcing every application onto one consistency model meant either paying strong-consistency latency everywhere or accepting eventual-consistency correctness risk everywhere. Azure SQL's original single-tier model similarly forced a choice between a fixed compute/storage ratio (DTU model) that didn't scale storage independently from compute, mirroring the same pain that pushed AWS toward Aurora's separated storage layer. PostgreSQL on Azure started as "Single Server," a simpler but more limited deployment (no VNet integration, weaker HA story) that Microsoft explicitly deprecated in favor of Flexible Server's VNet-native, zone-redundant design.

**Where it stands now.** DocumentDB was rebranded and re-architected into **Azure Cosmos DB** (2017) with its current signature feature: **five well-defined, per-request-overridable consistency levels** on a single physical replication protocol, letting one application mix Strong reads for a payment path and Eventual reads for an activity feed against the same underlying data. [Consistency levels in Cosmos DB — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels) — accessed 2026-08-08. Azure SQL's **Hyperscale** tier (storage/compute separation, up to 128 TB per database, near-instant backups via storage-layer snapshots rather than full backup files) is now the recommended default for anything with growth uncertainty, while Business Critical remains for workloads needing the lowest possible write latency via local SSD-backed replicas rather than Hyperscale's remote page-server architecture. **PostgreSQL Flexible Server** is Microsoft's unambiguous current recommendation for all new PostgreSQL workloads, and the live disagreement in the ecosystem isn't "Flexible vs Single Server" (settled) but "Flexible Server vertical scaling vs Hyperscale (Citus) horizontal sharding" for workloads outgrowing a single instance — with Citus requiring genuine schema/query redesign around distribution keys that a lot of teams underestimate.

**Where it's heading.** Cosmos DB's direction is deeper integration of vector search directly into the existing document/RU model (see `C-AZ-ai` for the AI Search comparison) rather than requiring a separate vector database — moderate-to-high confidence given Microsoft's consistent positioning of Cosmos DB as the unified operational-plus-AI-workload store. Azure SQL Hyperscale is absorbing more Business-Critical-tier guarantees (faster failover, lower write latency options) over time, narrowing Business Critical's justification — moderate confidence. PostgreSQL Flexible Server's roadmap points toward closing remaining gaps with Citus for moderate-scale sharding needs without requiring the full Citus extension model, though this is more speculative and worth a fresh check near interview time.

---

## Mental model

```
STORAGE ACCOUNT FAMILY (one account, one bill, shared redundancy config)
  BLOB (objects)     FILES (SMB/NFS shares)   QUEUES (simple FIFO-ish)   TABLES (legacy NoSQL)
  5 tiers: Hot/Cool/Cold/Archive/Premium
  6 redundancy: LRS -> ZRS -> GRS -> RA-GRS -> GZRS -> RA-GZRS  (cost multiplier increases ->)

COSMOS DB CONSISTENCY SPECTRUM (per-request overridable, database-level default)
  STRONG ─────── BOUNDED STALENESS ─────── SESSION ─────── CONSISTENT PREFIX ─────── EVENTUAL
  (linearizable)  (lag bound: K ops or       (read-your-      (never out of         (no ordering
   2x read RU      T time; 2x read RU)        own-writes,       order, may lag)       or freshness
   quorum read)                               1x read RU,                            guarantee,
                                               DEFAULT)                               1x read RU)

  Cost cliff is between Bounded Staleness and Session: quorum-read levels cost 2x RUs.

RELATIONAL FAMILY
  Azure SQL: DTU model (legacy) -> vCore model (current)
    General Purpose (attached storage) -> Business Critical (local SSD replicas,
    lowest write latency) -> Hyperscale (separated storage/compute, up to 128TB,
    near-instant snapshot backups)
  PostgreSQL: Flexible Server (recommended default, vertical scale) vs
    Hyperscale/Citus (horizontal sharding, requires distribution-key schema design)
```

---

## How it actually works

### Blob, Files, Queues — the storage-account chassis

A **storage account** is the billing/replication boundary; Blob, Files, Queues, and Tables inside one account share its redundancy tier. **Access tiers**: Hot (frequent access, no minimum retention, highest per-GB storage cost, lowest per-transaction cost), Cool (infrequent, 30-day minimum retention or an early-deletion penalty applies), Cold (rarely accessed but still online, roughly 64% cheaper capacity cost than Cool), Archive (offline — data must be **rehydrated** before read, taking hours), and Premium (SSD-backed, for high-transaction-rate, low-latency workloads where per-transaction cost dominates over per-GB cost). Roughly: Hot runs **~$0.02/GB**, Archive runs **under $0.001/GB**, with retrieval/access costs rising sharply as the tier gets colder — the classic pattern is enabling **lifecycle management policies** that auto-tier blobs from Hot → Cool → Archive based on last-access time. [Access tiers overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview) — accessed 2026-08-08.

**Redundancy**: LRS (3 copies, one datacenter, cheapest baseline) → ZRS (synchronous replication across availability zones in-region, ~1.25x LRS cost) → GRS (async replication to a paired secondary region, roughly 2x LRS cost) → RA-GRS (GRS plus read access to the secondary) → GZRS/RA-GZRS (zone-redundant primary plus geo-replicated secondary, ~2.5x LRS cost, the strongest combined guarantee). **Trap**: the Archive tier is only supported on LRS/GRS/RA-GRS accounts — it is explicitly **not supported** on ZRS/GZRS/RA-GZRS accounts, a real design constraint when a team wants both zone redundancy and archive tiering in the same account. [Blob Storage pricing/redundancy — nOps 2026](https://www.nops.io/blog/azure-storage-pricing/) — accessed 2026-08-08.

**Queue Storage** caps messages at **64 KB**, is the cheap/simple option for basic decoupling (worker polling pattern, similar spirit to SQS Standard but with a simpler feature set — no dead-lettering built in the way Service Bus has, no FIFO guarantee). Compare against Service Bus below.

### Cosmos DB — the five consistency levels, mechanically

This is the single most-tested Azure database topic. Ordered strongest to weakest:

1. **Strong** — linearizable; every read sees the most recent committed write, guaranteed. Requires a quorum read from a majority of replicas. Cross-region Strong consistency is supported but adds real write latency (synchronous replication across regions).
2. **Bounded Staleness** — reads lag writes by at most **K versions or T time** (both configurable), guaranteed ordering. Still a quorum-style read, same RU cost profile as Strong.
3. **Session** (the **default** and Microsoft's recommended starting point) — within a single client "session" (tracked via a session token), guarantees read-your-own-writes, monotonic reads, and consistent prefix. Outside that session (a different client, or a client that lost its session token), guarantees drop toward eventual. Reads cost **1x RU**.
4. **Consistent Prefix** — reads never see out-of-order writes (no reordering), but may lag arbitrarily. 1x RU reads.
5. **Eventual** — no ordering or freshness guarantee at all, lowest possible latency. 1x RU reads.

**The RU economics that make this a real design decision, not just a correctness knob**: Strong and Bounded Staleness reads cost **2x the RUs** of Session/Consistent Prefix/Eventual reads for local (single-region) minority reads, because satisfying those guarantees requires reading from two replicas instead of one to confirm quorum. [How to configure consistency levels — OneUptime 2026](https://oneuptime.com/blog/post/2026-02-16-how-to-configure-consistency-levels-in-azure-cosmos-db/view) — accessed 2026-08-08. This means choosing Strong consistency isn't just a latency tradeoff the way it often is in other systems — it's a **direct, doubled RU bill** for every read at that consistency level, which is why Session is both the default and the pragmatic middle ground most production applications land on.

```python
# untested sketch — per-request consistency override, Python SDK
from azure.cosmos import CosmosClient, PartitionKey

client = CosmosClient(url, credential)
container = client.get_database_client("orders_db").get_container_client("orders")

# Database-level default might be Session; override to Eventual for a
# read-heavy analytics/activity-feed path that doesn't need read-your-writes
items = list(container.query_items(
    query="SELECT * FROM c WHERE c.status = 'shipped'",
    enable_cross_partition_query=True,
    consistency_level="Eventual",  # cheaper, weaker guarantee than the DB default
))
```

**Partitioning limits worth knowing cold**: a **logical partition** (all items sharing one partition key value) is capped at **20 GB** of storage, hard, with no override — this is the single most common Cosmos DB production incident, a partition key chosen with insufficient cardinality (e.g., partitioning by `tenant_id` for a tenant that grows large) silently approaches 20GB and writes start failing with no advance warning unless you've wired up the storage-alert metric proactively. A **physical partition** caps at **10,000 RU/s** and **50 GB** — Cosmos DB automatically splits physical partitions as data grows, but a single logical partition can never span more than one physical partition, which is exactly why the 20GB logical-partition ceiling is hard rather than something splitting can relieve. [Create alerts for logical partition key storage — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-alert-on-logical-partition-key-storage-size) — accessed 2026-08-08; [Cosmos DB service quotas — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits) — accessed 2026-08-08.

### Queue Storage vs. Service Bus vs. Event Grid — pick the right one

| | Queue Storage | Service Bus | Event Grid |
|---|---|---|---|
| Max message size | 64 KB | 256 KB (Standard); up to **100 MB via AMQP on Premium** (note: still 1 MB over HTTP/SBMP even on Premium) | ~1 MB (event payload) |
| Ordering | No FIFO guarantee | FIFO via sessions | No ordering guarantee |
| Dead-lettering | Manual (poison-message pattern via dequeue count) | Built-in DLQ | Built-in retry + dead-letter destination |
| Model | Simple polling queue | Full enterprise messaging (topics/subscriptions, sessions, transactions) | Pub/sub event routing, push-based |
| AWS equivalent | SQS Standard (roughly) | SQS + SNS combined, enterprise features | EventBridge |

[Service Bus 100MB messages — Sandro Pereira 2024](https://blog.sandro-pereira.com/2024/10/18/friday-fact-you-can-now-send-a-100-mb-message-to-a-service-bus-queue-or-topic/) — accessed 2026-08-08.

### Azure SQL — Hyperscale vs. Business Critical vs. General Purpose

**Hyperscale** separates compute from a distributed, remote storage layer (page servers), enabling databases up to **128 TB** regardless of compute size, with near-instant backups (storage-layer snapshots, not a traditional backup-file copy) and fast storage autoscaling. **Business Critical** uses local SSD-backed replicas for the lowest possible write latency (synchronous local replication, no network hop to remote storage for writes), but storage is capped much lower — roughly **4-16 TB depending on hardware generation/vCore tier** for Managed Instance Business Critical. [Azure SQL Managed Instance resource limits — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-sql/managed-instance/resource-limits?view=azuresql) — accessed 2026-08-08. **General Purpose** is the middle tier: attached remote storage (not local SSD replicas), lower cost than Business Critical, adequate for most workloads without extreme write-latency requirements.

### PostgreSQL Flexible Server

The current, unambiguously recommended PostgreSQL deployment on Azure (Single Server is deprecated — migrate off it if still running it). Three pricing tiers: **Burstable** (B-series, cheapest, CPU credits like AWS T-series, starts around **$12/month** for B1ms), **General Purpose**, and **Memory Optimized**. Runs **40-45% cheaper than Azure SQL at equivalent vCore count**, a real driver for teams with Postgres-portable workloads and no hard Azure SQL feature dependency. [PostgreSQL Flexible Server pricing — Bytebase](https://www.bytebase.com/dbcost/azure-flexible-server-pricing/) — accessed 2026-08-08. For horizontal scale beyond a single instance's ceiling, **Hyperscale (Citus)** is the separate deployment option — it distributes data across worker nodes via a chosen distribution column, structurally similar to sharding any Postgres cluster with the Citus extension, and requires real schema/query design around that distribution key (collocated joins, avoiding cross-shard queries) rather than being a transparent scale-out.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| S3 | Blob Storage | Cloud Storage | S3 is now strongly read-after-write consistent; don't cite stale "eventual consistency" S3 answers |
| DynamoDB | Cosmos DB | Firestore / Bigtable | DynamoDB's consistency choice is a free per-request toggle (eventual vs strong); Cosmos DB's 5-level spectrum has real RU cost differences per level |
| RDS / Aurora | Azure SQL (Hyperscale ~ Aurora's separated storage) | Cloud SQL / AlloyDB | Hyperscale's page-server architecture is Azure's closest analog to Aurora's decoupled storage layer |
| RDS for PostgreSQL / Aurora PostgreSQL | PostgreSQL Flexible Server / Hyperscale (Citus) | Cloud SQL for PostgreSQL / AlloyDB | Citus sharding requires real schema redesign, unlike Aurora's transparent storage scaling |
| SQS | Queue Storage / Service Bus | Pub/Sub (pull) | Queue Storage ~ SQS Standard simplicity; Service Bus ~ SQS+SNS combined enterprise feature set |

---

## Build it from scratch

Minimal demonstration of the consistency-level tradeoff end to end, matching `labs/python/04-storage-db/`:

```python
# untested sketch — creating a Cosmos DB container with an explicit default
# consistency level, then overriding per-request for a specific read path
from azure.cosmos import CosmosClient, PartitionKey

client = CosmosClient(url, credential)
db = client.create_database_if_not_exists("orders_db")

# Container-level partition key choice determines the 20GB logical-partition
# ceiling's blast radius -- partitioning by low-cardinality tenant_id risks
# a single large tenant hitting the ceiling; a higher-cardinality composite
# key (tenant_id + order_id prefix) spreads writes across more partitions.
container = db.create_container_if_not_exists(
    id="orders",
    partition_key=PartitionKey(path="/tenantId"),
    offer_throughput=400,  # minimum provisioned RU/s for a dedicated container
)

# Write path: uses the account/database default consistency (Session)
container.upsert_item({"id": "o1", "tenantId": "acme", "status": "placed"})

# Read path for a payment-critical query: explicitly request Strong,
# accepting the 2x RU cost for that one query
result = list(container.query_items(
    query="SELECT * FROM c WHERE c.id = 'o1'",
    partition_key="acme",
    consistency_level="Strong",
))
```

---

## How it's done in production

A typical production data layer: **Blob Storage** with lifecycle management policies auto-tiering Hot → Cool → Archive by last-access-time, GRS or GZRS redundancy for anything business-critical, LRS for easily-regenerable derived data (build artifacts, cache dumps). **Cosmos DB** at the database-level default of Session consistency, with explicit per-request overrides to Strong only for the specific paths that need linearizability (payment state, inventory decrement) and Eventual for read-heavy, staleness-tolerant paths (activity feeds, search-adjacent reads) to save RUs at scale. **Azure SQL Hyperscale** as the default for new relational workloads with any growth uncertainty; Business Critical reserved for the specific subset needing the lowest write latency (often trading tier choice against Hyperscale's slightly higher write-commit latency due to the remote page-server hop). **PostgreSQL Flexible Server** for Postgres-native workloads, with Citus considered only once vertical scaling on the largest Memory Optimized SKU is demonstrably insufficient, since the schema-redesign cost of adopting Citus is real and shouldn't be paid preemptively.

| Symptom | Cause | Fix |
|---|---|---|
| Cosmos DB writes to a specific partition key value start failing with no warning | Logical partition hit the hard 20 GB ceiling — usually a low-cardinality partition key (e.g., large single tenant) | Redesign the partition key for higher cardinality (composite key), or pre-split by adding a synthetic suffix; the 20GB ceiling cannot be raised |
| Cosmos DB RU consumption doubled after a consistency-level change | Someone moved the container/database default (or a hot read path) from Session/Eventual to Strong/Bounded Staleness | Confirm whether linearizability is actually required for that specific read path; if not, move back to Session and reserve Strong for the specific paths that need it |
| A client reads stale data despite Session consistency being configured | The client lost continuity of its session token (new client instance, load-balanced across SDK instances without token propagation) — Session guarantees only hold within a continuous session | Propagate the session token explicitly across the relevant client boundary, or accept Eventual-level guarantees for that path and design around it |
| Archive-tier blob move fails on a specific storage account | Account is configured for ZRS/GZRS/RA-GZRS — Archive tier isn't supported on zone-redundant configurations | Use LRS/GRS/RA-GRS for any storage account that needs Archive tier, or accept Cool/Cold as the coldest tier available on a ZRS account |
| PostgreSQL Flexible Server query performance degrades sharply as data grows past a single instance's practical ceiling | Outgrew vertical scaling on the largest available SKU for that workload's access pattern | Evaluate Hyperscale (Citus) — but budget real engineering time for distribution-key schema redesign, not a drop-in migration |
| Azure SQL Business Critical database can't grow past its documented storage ceiling | Business Critical's local-SSD-replica architecture caps storage well below Hyperscale's 128TB ceiling | Migrate to Hyperscale if storage growth is the binding constraint and the workload can tolerate its slightly different write-latency profile |

---

## Tradeoffs & when NOT to use it

- **Don't default to Strong consistency on Cosmos DB "to be safe."** It doubles read RU cost versus Session/Eventual for local reads and adds cross-region write latency if applied globally — reserve it for the specific paths that actually need linearizability.
- **Don't choose a Cosmos DB partition key for query convenience without checking write-distribution cardinality.** A partition key that's great for one query pattern but has low cardinality (few distinct values, one value growing unboundedly) walks straight into the hard 20GB logical-partition ceiling.
- **Don't put anything needing FIFO ordering or built-in dead-lettering on Queue Storage.** It's the simple/cheap option specifically because it lacks Service Bus's enterprise messaging features; reach for Service Bus once ordering or DLQ semantics matter.
- **Don't reach for Cosmos DB Hyperscale (Citus) or a distributed database preemptively.** The schema-redesign cost around distribution keys is real; exhaust vertical scaling on Flexible Server or Azure SQL first.
- **Don't put Archive-tier data on a ZRS/GZRS storage account expecting archive economics.** The feature combination doesn't exist — plan account-level redundancy and tiering strategy together, not independently.
- **Don't assume Azure SQL Business Critical is strictly "better" than General Purpose or Hyperscale.** It optimizes specifically for lowest write latency via local replicas at the cost of a much lower storage ceiling and higher price; Hyperscale is usually the better default absent a specific sub-millisecond write-latency requirement.

---

## Interview questions

### Q1 — Name and order Cosmos DB's five consistency levels, and explain the RU cost cliff between them.
**Testing:** the single most-probed fact in this module — whether the levels and their real cost implications are both known.
**Answer:** Strong, Bounded Staleness, Session, Consistent Prefix, Eventual — strongest to weakest. Strong and Bounded Staleness require quorum reads (reading from two replicas) to guarantee their consistency properties, costing **2x the RUs** of Session/Consistent Prefix/Eventual reads, which only need a single-replica read. Session is the default and the pragmatic middle: read-your-own-writes and monotonic reads within a session, at 1x RU cost.
**Follow-up trap:** *"Is the doubled RU cost only for writes or only for reads?"* — it's specifically a **read** cost difference; the quorum requirement for Strong/Bounded Staleness affects how many replicas must be consulted to serve a consistent read, not the write path's replication mechanics.

### Q2 — A Cosmos DB container using `tenant_id` as the partition key suddenly starts rejecting writes for one large tenant. Diagnose.
**Testing:** the hard 20GB logical-partition ceiling, one of Cosmos DB's most-hit real incidents.
**Answer:** Every item sharing a partition key value lives in one logical partition, hard-capped at 20 GB with no override — a single large tenant's data grew past that ceiling. Fix requires redesigning the partition key for higher cardinality (e.g., a composite key combining tenant_id with a time bucket or entity type) so no single logical partition can grow unboundedly; this cannot be resolved by adding throughput or waiting for automatic partition splits, since a logical partition can never span multiple physical partitions.
**Follow-up trap:** *"Why doesn't Cosmos DB just split the oversized logical partition the way it splits physical partitions?"* — physical partition splitting redistributes *different* logical partition key values across more physical partitions as aggregate data/throughput grows; it can't split a *single* logical partition key's data, since consistent lookups by that key value require it to live in one place.

### Q3 — Compare Cosmos DB's consistency model to DynamoDB's, and explain why this trips AWS engineers specifically.
**Testing:** the direct cross-cloud trap.
**Answer:** DynamoDB offers a binary, per-request, free choice: eventually-consistent or strongly-consistent reads, with no cost difference (strongly consistent reads simply consume roughly double the read capacity units under the older model, or draw from the same read-capacity pool under on-demand — but conceptually it's a two-way toggle). Cosmos DB offers five distinct, database-configurable-with-per-request-override levels, and two of them (Strong, Bounded Staleness) carry a real, documented 2x RU cost versus the other three. AWS engineers often assume "Cosmos DB has a strong/eventual toggle like DynamoDB" and miss both the three intermediate levels and the specific cost structure.
**Follow-up trap:** *"Does Session consistency have a DynamoDB equivalent?"* — not directly; DynamoDB has no native concept of a session-scoped read-your-writes guarantee outside of using the same connection/consistent-read flag per call — Session consistency's session-token-based continuity guarantee across a client's requests is architecturally distinct from either DynamoDB option.

### Q4 — Design the consistency strategy for an e-commerce system: inventory decrement, order placement, and a "recently viewed items" feed.
**Testing:** applying the consistency levels to real workload shapes rather than picking one level for everything.
**Answer:** Inventory decrement needs **Strong** (or at minimum Bounded Staleness with a tight bound) — a race condition overselling inventory is a real correctness bug, and the 2x RU cost is justified by the low-volume, high-stakes nature of that specific write/read path. Order placement confirmation reads (the user's own order right after placing it) fit **Session** — read-your-own-writes is exactly what's needed, at 1x RU cost, and it's the sensible database default. The recently-viewed-items feed fits **Eventual** — staleness of a few seconds is imperceptible and irrelevant, and it's the cheapest, lowest-latency option.
**Follow-up trap:** *"Why not just use Bounded Staleness everywhere as a compromise?"* — Bounded Staleness still costs 2x RUs like Strong, so it doesn't save money over Strong for paths that don't need strict linearizability, and it doesn't save money over Session for paths that don't need bounded-time ordering guarantees across all clients — it's a specific tool for a specific requirement (bounded lag with strict ordering across all readers), not a universal middle ground.

### Q5 — Explain the architectural difference between Azure SQL Hyperscale and Business Critical, and when each wins.
**Testing:** the storage/compute separation concept and its latency tradeoff, a direct analog to Aurora vs. traditional RDS.
**Answer:** Hyperscale separates compute from a distributed remote storage layer (page servers), enabling databases up to 128 TB regardless of compute size and near-instant backups via storage snapshots rather than copying backup files. Business Critical uses local SSD-backed synchronous replicas for the lowest possible write commit latency, since writes don't need a network hop to remote storage, but caps storage far lower (roughly 4-16 TB depending on hardware generation). Hyperscale wins for growth-uncertain or very large workloads; Business Critical wins specifically when sub-millisecond-sensitive write latency matters more than storage ceiling.
**Follow-up trap:** *"Is Hyperscale strictly the better default given its much higher storage ceiling?"* — for most workloads yes, but a workload genuinely bottlenecked on write commit latency (not just storage size) can see a measurable regression moving from Business Critical's local-replica writes to Hyperscale's remote page-server writes — verify the workload's actual latency sensitivity before defaulting to Hyperscale purely for its storage ceiling.

### Q6 — A team wants FIFO ordering and dead-letter handling for a message queue. Why is Queue Storage the wrong choice, and what should they use instead?
**Testing:** the Queue Storage vs. Service Bus decision, a common cross-cloud "which AWS-equivalent" probe.
**Answer:** Queue Storage provides no FIFO guarantee and no built-in dead-lettering — it's deliberately the simple, cheap option (64KB max message size, basic poll-based consumption), closer to SQS Standard than to any ordering-aware queue. Service Bus provides FIFO via sessions, built-in dead-letter queues, topics/subscriptions for pub/sub fan-out, and transactional message handling — the right choice whenever ordering or DLQ semantics are actual requirements, not just nice-to-haves.
**Follow-up trap:** *"Does Service Bus's 100MB message size apply universally?"* — no, the 100MB ceiling is specifically for the AMQP protocol on the Premium tier; the same Premium tier is still capped at 1MB over HTTP or SBMP protocols, and Standard/Basic tiers cap at 256KB regardless of protocol — a design assuming 100MB messages work everywhere on Service Bus will break outside that specific protocol/tier combination.

### Q7 — Why is PostgreSQL Single Server deprecated, and what does a team migrating off it need to plan for?
**Testing:** currency on a real, disruptive platform change, plus migration-planning judgment.
**Answer:** Flexible Server superseded Single Server with VNet-native networking, zone-redundant HA, and more granular maintenance-window control — Single Server lacked VNet integration and had a weaker HA story, and Microsoft has explicitly deprecated it in favor of Flexible Server as the recommended default for all new and existing workloads. Migration planning needs to account for VNet/private-networking reconfiguration (Flexible Server's networking model differs), a maintenance window for the migration itself (typically not a zero-downtime online migration without using logical replication explicitly), and re-validating any extensions or configuration flags that may differ between the two deployment models.
**Follow-up trap:** *"Can a team use Azure Database Migration Service for a fully online, zero-downtime migration?"* — logical-replication-based online migration paths exist and can minimize downtime significantly, but "zero-downtime" claims for any managed-database migration should be verified against the current DMS documentation and tested against the specific workload's replication lag tolerance before being promised as fact.

### Q8 — Explain why Bounded Staleness's "K versions or T time" bound matters for a multi-region deployment, and name a scenario where it's the correct choice over both Strong and Session.
**Testing:** whether Bounded Staleness is understood as a distinct tool, not just "weaker than Strong."
**Answer:** Bounded Staleness guarantees every reader across every region sees writes in the same order, lagging by at most K versions or T time (whichever bound is configured) — this is a strictly *global* ordering guarantee that Session, which only guarantees ordering within a single client's session, doesn't provide. It's the correct choice when multiple independent clients across regions need a consistent, bounded-lag view of the same data with strict ordering (e.g., a leaderboard or auction state that every region's readers must see progress through in the same sequence) but full cross-region synchronous Strong consistency's write-latency cost is unacceptable.
**Follow-up trap:** *"Does Bounded Staleness avoid Strong consistency's cross-region write latency penalty?"* — yes, that's precisely its value proposition: it decouples the ordering/freshness guarantee from requiring synchronous cross-region write acknowledgment, trading a bounded (not zero) staleness window for materially lower write latency than global Strong consistency.

### Q9 — Design a Cosmos DB partition key for a multi-tenant SaaS system where tenant sizes vary from tiny to enormous.
**Testing:** synthesizing the 20GB/10,000 RU/s limits into an actual schema decision, a classic staff-level probe.
**Answer:** A pure `tenant_id` partition key risks the largest tenants hitting the 20GB logical-partition ceiling. A composite/synthetic key — e.g., `tenant_id` combined with a coarse time bucket (`tenant_id_2026Q3`) or an entity-type suffix — spreads a large tenant's data across multiple logical partitions while still allowing efficient tenant-scoped queries (which now need to fan out across the known set of synthetic-key variants for that tenant, a manageable tradeoff). Small tenants naturally stay well under any per-partition ceiling regardless.
**Follow-up trap:** *"Doesn't this synthetic-key approach make single-tenant queries slower by requiring cross-partition fan-out?"* — yes, there's a real query-cost tradeoff versus a pure single-tenant partition key; the design explicitly accepts slightly more expensive tenant-scoped queries (bounded fan-out across a known small set of synthetic partitions) in exchange for removing the unbounded-growth risk that a pure tenant_id key carries for the largest tenants.

### Q10 — A read-heavy analytics dashboard querying Cosmos DB is consuming far more RUs than expected. What consistency-level and query-pattern changes would you investigate first?
**Testing:** practical RU-cost debugging, tying consistency levels back to a concrete cost incident.
**Answer:** First check the consistency level in use for that read path — if it's inheriting a database default of Strong or Bounded Staleness (rather than Session or Eventual), that's an immediate 2x RU multiplier for every read with no correctness benefit for a staleness-tolerant analytics use case. Second, check for cross-partition queries without a partition key filter, which fan out to every physical partition and multiply RU cost by partition count regardless of consistency level. Moving the dashboard's reads to Eventual consistency and ensuring queries include the partition key filter where possible are the two highest-leverage fixes.
**Follow-up trap:** *"If the dashboard needs to reflect writes within a few seconds, does moving to Eventual consistency break that requirement?"* — Eventual consistency has no *guaranteed* bound on staleness, though in practice lag is often small; if a specific freshness bound is a real product requirement (not just a nice-to-have), Bounded Staleness with an explicit T-time bound is the correct tool, accepting its 2x RU cost as the price of a guaranteed (not just typical) freshness window.

### Q11 — Compare choosing Cosmos DB Hyperscale-style global distribution against sharding PostgreSQL with Citus for a workload outgrowing a single instance.
**Testing:** synthesizing the document-vs-relational scaling stories into a coherent technology-selection answer.
**Answer:** Cosmos DB's partitioning is a first-class, built-in part of the document model from day one — you choose a partition key and Cosmos DB manages physical partition placement and splitting transparently (within the 20GB/10,000 RU/s per-logical-partition constraints already discussed). Citus-sharded PostgreSQL requires deliberately redesigning the schema around a distribution column, ensuring joins are collocated on that column to avoid expensive cross-shard queries, and accepting that not every relational feature (some constraint types, certain query patterns) works identically across a distributed Citus cluster. The choice is really "does this workload's data model and existing relational investment justify the Citus redesign cost, or is a document model with Cosmos DB's native partitioning a better fit going forward."
**Follow-up trap:** *"If the team has a large existing PostgreSQL codebase with complex joins, is Citus obviously the right call over migrating to Cosmos DB?"* — not automatically; complex multi-table joins that don't collocate cleanly on a single distribution key can perform far worse under Citus than they did on a single non-sharded instance, so the honest answer is to profile the actual query patterns against a realistic distribution-key candidate before committing, rather than assuming "stay relational, add Citus" is free of its own redesign risk.

---

## Red flags that fail you

- Not being able to name all five Cosmos DB consistency levels in order, or missing the 2x RU cost of Strong/Bounded Staleness.
- Claiming Cosmos DB's consistency model is "basically the same as DynamoDB's."
- Not knowing the 20GB hard logical-partition ceiling, or suggesting it can be resolved by adding throughput.
- Recommending Queue Storage for a workload that explicitly needs FIFO ordering or dead-lettering.
- Treating PostgreSQL Single Server as still a valid choice for new workloads.
- Not distinguishing Hyperscale's separated-storage architecture from Business Critical's local-replica architecture.
- Assuming Archive tier works on any redundancy configuration.

---

## Cheat card

```
BLOB TIERS: Hot (~$0.02/GB, no min retention) -> Cool (30-day min) -> Cold (~64% cheaper
  than Cool) -> Archive (offline, hours to rehydrate, <$0.001/GB). Premium = SSD, high txn rate.
REDUNDANCY: LRS (baseline) -> ZRS (~1.25x, AZ-sync) -> GRS (~2x, async cross-region) ->
  RA-GRS (GRS + readable secondary) -> GZRS/RA-GZRS (~2.5x, zone + geo).
  ARCHIVE TIER only on LRS/GRS/RA-GRS -- NOT supported on ZRS/GZRS/RA-GZRS.

COSMOS DB 5 CONSISTENCY LEVELS (strong->weak):
  STRONG: linearizable, quorum read, 2x RU.
  BOUNDED STALENESS: lag <= K versions or T time, global ordering, 2x RU.
  SESSION (DEFAULT): read-your-own-writes within session, 1x RU.
  CONSISTENT PREFIX: never out-of-order, may lag, 1x RU.
  EVENTUAL: no guarantee, lowest latency, 1x RU.
  Cost cliff: Strong/Bounded Staleness = 2x RU vs the other three (quorum vs single-replica read).

COSMOS PARTITION LIMITS: logical partition HARD CAP 20GB (no override, no split possible
  for one key value). Physical partition: 10,000 RU/s + 50GB (auto-splits across MORE
  logical partition VALUES, not within one).

QUEUE STORAGE vs SERVICE BUS: Queue Storage = 64KB msg, no FIFO, no DLQ (~SQS Standard).
  Service Bus = 256KB std / up to 100MB Premium+AMQP only (still 1MB over HTTP/SBMP),
  FIFO via sessions, built-in DLQ, topics/subscriptions (~SQS+SNS).

AZURE SQL: Hyperscale = separated compute/storage, up to 128TB, near-instant snapshot
  backups. Business Critical = local SSD replicas, lowest write latency, ~4-16TB cap
  depending on HW gen. General Purpose = attached remote storage, middle tier.

POSTGRESQL: Flexible Server = current recommended default (Single Server DEPRECATED).
  Tiers: Burstable (~$12/mo B1ms) / General Purpose / Memory Optimized.
  ~40-45% cheaper than Azure SQL at equal vCore count.
  Hyperscale (Citus) = horizontal sharding, requires real distribution-key schema design.

CROSS-CLOUD: Blob~=S3 (S3 now strong read-after-write). Cosmos~=DynamoDB (DynamoDB's
  consistency = free binary toggle; Cosmos = 5 tunable levels with real RU cost delta).
  Azure SQL Hyperscale ~= Aurora (separated storage). Queue Storage ~= SQS Standard.
```

## Sources

- [Consistency levels in Azure Cosmos DB — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels) — accessed 2026-08-08
- [Service quotas and default limits — Azure Cosmos DB — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits) — accessed 2026-08-08
- [Create alerts to monitor logical partition key storage size — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-alert-on-logical-partition-key-storage-size) — accessed 2026-08-08
- [How to configure consistency levels in Azure Cosmos DB — OneUptime 2026](https://oneuptime.com/blog/post/2026-02-16-how-to-configure-consistency-levels-in-azure-cosmos-db/view) — accessed 2026-08-08
- [Access tiers for blob data — Microsoft Learn](https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview) — accessed 2026-08-08
- [Azure Storage Pricing in 2026 — nOps](https://www.nops.io/blog/azure-storage-pricing/) — accessed 2026-08-08
- [Azure SQL Managed Instance resource limits — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-sql/managed-instance/resource-limits?view=azuresql) — accessed 2026-08-08
- [Azure SQL Database Hyperscale FAQ — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-sql/database/service-tier-hyperscale-frequently-asked-questions-faq?view=azuresql) — accessed 2026-08-08
- [Limits in Azure Database for PostgreSQL flexible server — Microsoft Learn](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/concepts-limits) — accessed 2026-08-08
- [Azure Database for PostgreSQL & MySQL Pricing — Bytebase](https://www.bytebase.com/dbcost/azure-flexible-server-pricing/) — accessed 2026-08-08
- [Azure Service Bus now supports 100MB messages — Sandro Pereira 2024](https://blog.sandro-pereira.com/2024/10/18/friday-fact-you-can-now-send-a-100-mb-message-to-a-service-bus-queue-or-topic/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
- 2026-08-09 — Azure SQL Database and Azure SQL Managed Instance now apply immutability to the most recent 7 days of backups by default (GA), a compliance/ransomware-protection posture change enabled for all databases regardless of configured point-in-time retention ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
