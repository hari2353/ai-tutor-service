# Azure Data Deep: Blob/Files/Queues, Cosmos DB, Azure SQL, PostgreSQL Flexible

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-storage-db` · **Tags:** data,critical

## The 30-second version

Four services cover most Azure persistence decisions, each with one trap that decides them: Blob Storage tiers (Hot/Cool/Cold/Archive) trade retrieval latency and early-deletion fees against pennies-per-GB, and Archive means hours-long rehydration, not instant access; Cosmos DB's RU/s model gives guaranteed p99 latency under 10 ms but makes cost proportional to *provisioned* capacity, so spiky workloads pay the autoscale floor (~10% of max) around the clock and analytics-style scans burn money per query; Azure SQL Database splits into vCore provisioning with Hyperscale reaching ~100 TB-class sizes and serverless that auto-pauses after ~60 minutes idle; PostgreSQL Flexible Server replaced the retired Single Server offering with same-zone or zone-redundant HA (~99.99% with cross-zone standby) and now carries the pgvector story for RAG on Azure. The interview question under all of it: given an access pattern, can you name the failure mode of your chosen store before it happens — hot partitions, RU exhaustion, subnet IP starvation for private endpoints, or archive-tier invoices nobody forecast?

## Why this gets asked

Because data-layer mistakes are the ones that show up as invoices and incidents simultaneously. Interviewers have seen teams leave a logging container on Hot tier for years at multiples of Cool pricing; watched a Cosmos container get 429-throttled during a launch because the partition key was `region` and one region took 80% of traffic; migrated off Azure SQL to Flexible Server mid-project because Single Server retirement landed on their roadmap; and paid surprise Cosmos bills where one dashboard's cross-partition queries cost more than the whole application. The probe: do you reason about *cost mechanics* (RU math, tier economics, HA SKU deltas) and *distribution mechanics* (partitioning, replication modes, failover semantics) as one system rather than reciting feature lists.

---

## Lineage: past → present → future

**What came before.** Azure SQL Database grew out of on-prem SQL Server as PaaS in 2010 with DTU-based sizing (a blended throughput benchmark unit) that made capacity planning opaque; Cosmos began as Microsoft's internal "Project Florence" (2008-2010), powering Azure internals before emerging publicly as DocumentDB (2014) and rebranding as Cosmos DB in 2017 with global distribution as the headline. Storage blobs date to 2008 with Hot/Cool added 2016 and Archive 2017. PostgreSQL arrived on Azure first as Single Server (2018) — fully managed but with customer-unfriendly constraints: no server-level extensions control, fixed maintenance windows, limited HA choices. The pain driving every subsequent redesign: DTU opacity, single-region defaults, and Single Server's rigidity versus the AWS RDS/Aurora competitive benchmark.

**Where it stands now.** Current state is consolidation plus specialization. Single Server retired (March 2025) leaving Flexible Server as the only PostgreSQL path, with same-zone and zone-redundant HA modes, customer-controlled maintenance, and extension freedom including pgvector. Azure SQL's center of gravity moved to the vCore model with serverless compute (auto-pause/resume, per-second billing) and Hyperscale architecture (log-service-based scale-out, up to ~128 TB, named replicas for read scaling); DTU tiers persist only for legacy estates. Cosmos DB matured its cost levers — autoscale with 0.1×Tmax floors, serverless consumption mode, hierarchical partition keys solving the 20 GB logical-partition ceiling — while keeping its five consistency levels as the textbook distributed-systems spectrum. Storage added the Cold tier (between Cool and Archive) and continues pushing Data Lake Gen2 (hierarchical namespace) as the analytics substrate. The live disagreement: whether Cosmos's RU abstraction is a feature (predictable latency, no noisy neighbors) or a tax (cost modeling complexity, vendor lock-in of query patterns) — reasonable architects land differently depending on workload shape.

**Where it's heading.** High confidence: PostgreSQL Flexible keeps absorbing investment (it's Microsoft's fastest-growing relational engine on Azure) and becomes the default answer for new greenfield OLTP unless deep SQL Server dependency exists; vector search keeps collapsing into existing stores (pgvector, Cosmos for NoSQL vector policies, DiskANN-backed index integration). Medium confidence: Hyperscale's log-service architecture becoming the template for all Azure SQL tiers eventually. Speculative: consumption-priced everything eroding provisioned models further, and OneLake/Fabric blurring storage-versus-warehouse boundaries enough that "which database holds the truth" becomes a governance question more than an engineering one.

---

## Mental model

```
                    ACCESS PATTERN DECIDES THE STORE

  write-once/read-rarely          known-schema OLTP         planet-scale KV/doc
  ─────────────────────           ─────────────────        ────────────────────
  BLOB (tiered)                   AZURE SQL                COSMOS DB
   Hot   ~instant, $$$            vCore/serverless          RU/s budgeted
   Cool   ms-ms, $$               Hyperscale ~128TB         partition key = physics
   Cold  hours-scale, $           elastic pools             5 consistency levels
   Archive hours+, ¢              failover groups           change feed
                                  RPO ~5 s geo
       ▲                              │                        │
       │ files/SMB for lift-shift     │  open-source stack     │
       │ QUEUES: 64KB msgs,           │  → POSTGRES FLEXIBLE   │
       │  7-day TTL, at-least-once ◄──┘   ZRS-HA ~99.99%,      │
       │                                   pgvector, PgBouncer  │
       └────────────────────────────────────────────────────────┘
        COST MODEL: storage+tiers    COMPUTE: provisioned/paused  THROUGHPUT: RU/s
```

The one-liner: **blob charges for bytes-at-rest, SQL/Postgres charge for running compute, Cosmos charges for reserved request units** — three different currencies, and misreading which currency a workload spends is how bills explode.

---

## How it actually works

### Blob Storage: tiers, redundancy, immutability

Access tiers price storage down and operations/retrieval up: Hot (frequent access), Cool (~30-day minimum retention expectation), Cold (~90-day minimum), Archive (offline; rehydration takes hours — standard priority up to ~15 h, high priority where available faster — plus early-deletion penalties). Lifecycle management policies automate tier transitions by prefix/age. Redundancy ladder: LRS (3 copies, one datacenter), ZRS (across 3 zones), GRS/GZRS (async replication to paired region; RA- variants keep read access to secondary), with durability marketed at ~11 nines for LRS and read SLAs from ~99.9% upward by configuration. Two security-relevant mechanics: **immutable storage** (WORM, time-based or legal-hold policies — compliance-grade, cannot be shortened once set) and **versioning/immutability combined** as ransomware defense. Auth should be Entra ID + RBAC data roles (`Storage Blob Data Reader/Contributor`) with account-key/SAS usage minimized; SAS still rules ad-hoc sharing but service-SAS-with-user-delegation narrows blast radius versus account keys. For analytics-shaped workloads, enable **hierarchical namespace** (ADLS Gen2): directories become real O(1) rename/ACL operations instead of simulated prefixes.

Azure Files: SMB and NFS shares, HDD-standard (transaction-optimized) or SSD-premium SKUs, sized in GiB quotas; Azure File Sync bridges on-prem Windows Servers with cloud tiering. Queues: the humble sibling — 64 KB messages, 7-day maximum TTL, visibility timeouts, at-least-once delivery, poison-queue convention (`<queue>-poison` after N dequeues). The Queue-vs-Service-Bus question resolves on features: SB gives topics/rules, sessions (ordered FIFO groups), transactions, dead-lettering built-in, duplicate detection; Storage Queues win on simplicity and price for fire-and-forget decoupling.

### Cosmos DB: the RU machine

Everything prices in **Request Units**: a 1 KB point read at session/eventual consistency costs 1 RU; writes cost more (roughly ~5-10 RU for small items depending on indexing); queries bill by consumed RUs measured per execution. Provisioning modes: manual throughput (floor ~400 RU/s per container), **autoscale** (you set Tmax; system scales between 0.1×Tmax and Tmax; hourly billing at whichever is higher — usage or 0.1×Tmax floor), and **serverless** (per-request RU billing, no provisioning, but throughput caps per region make it dev/small-workload territory).

Partition physics decide performance: the **partition key** routes items to logical partitions (max 20 GB, effectively ~10k RU/s each), which map onto physical partitions (50 GB storage, 10k RU/s each) that split automatically as data grows. A hot key concentrates all traffic on one physical partition and throttles regardless of total provisioned RUs. Escape hatches: synthetic keys (concatenate tenant+id), or **hierarchical partition keys** (up to 3 levels, with documented patterns ending in `/id` letting higher levels exceed 20 GB safely). Items cap at ~2 MB. Consistency spectrum — Strong, Bounded Staleness (configurable K versions/T interval), Session (default), Consistent Prefix, Eventual — trades latency/durability guarantees: Strong requires global-majority writes (multi-region accounts with >8000 km spread block Strong by default due to latency), and the durability table says a single-region account of any consistency faces RPO <240 minutes in a regional disaster, while multi-region single-write-region configs get RPO <15 minutes (Strong: RPO=0).

Change feed (sorted, durable log of inserts/updates per logical partition key order) powers downstream projections — materialized views, cache invalidation, CDC pipelines — without polling.

### Azure SQL Database

vCore model exposes compute like a VM (General Purpose remote-storage, Business Critical local-SSD with built-in readable secondaries, **Hyperscale** with log-service architecture separating compute from page servers — up to ~128 TB databases, multiple named replicas, fast restores from snapshots). **Serverless** compute auto-scales within min/max vCPU bounds and **auto-pauses** after configurable inactivity (~default 1 hour), billing storage only while paused — ideal for dev/test and bursty internal apps, with cold-resume latency ~tens-of-seconds to a minute as the price. High availability: zone-redundant configurations place replicas across zones; **failover groups** replicate asynchronously to another region with RPO typically ~5 seconds and application-level DNS cutover (RTO ~tens-of-seconds to minutes). Elastic pools share capacity across many small databases — the multi-tenant SaaS lever.

### PostgreSQL Flexible Server

Single Server retired March 2025; Flexible is the path: choose region AND zone, pick compute from Burstable (B-series, e.g., ~B1ms 1 vCPU/2 GiB for dev) through General Purpose/Memory-Optimized D/ESeries, storage to tens-of-TB class with provisioned IOPS. HA modes: **same-zone** (standby replica in the same AZ, automatic failover typically ~60-120 s) and **zone-redundant** (standby in another zone; ~99.99% SLA target) — synchronous replication to standby, with failover handled by the platform including DNS flip. Read replicas (cross-region supported) serve read scaling and migrations. Operational wins versus the old offering: customer-controlled maintenance windows, `shared_preload_libraries` freedom (pgvector, pg_cron, TimescaleDB-class extensions where licensed), built-in PgBouncer connection pooling (essential because Postgres connections are processes — hundreds of Functions instances x concurrency will exhaust max_connections without pooling), and flexible autovacuum tuning per-server. Vector search via **pgvector** makes it a credible RAG store below massive scale — HNSW indexes, hybrid search composable with full-text tsvector ranking.

---

## Build it from scratch

An RU/cost estimator capturing Cosmos's actual pricing mechanics:

```python
# untested sketch — Cosmos DB RU estimator: the arithmetic interviews ask you to derive
def point_read_rus(item_kb: float, consistency: str = "session") -> float:
    base = max(1.0, math.ceil(item_kb))            # 1 RU per 1 KB, min 1
    return base * 2 if consistency == "strong" else base   # strong reads 2 replicas

def monthly_autoscale_cost(tmax_ru: int, avg_util: float,
                           ru_price_per_hour_per_100: float = 0.0082) -> float:
    """Autoscale bills hourly: max(observed, 0.1*Tmax).
    Spiky workloads with low duty cycle pay the floor most hours."""
    billed_floor = tmax_ru * 0.1
    typical_billed = max(billed_floor, tmax_ru * avg_util)
    hours_month = 24 * 30
    return (typical_billed / 100) * ru_price_per_hour_per_100 * hours_month

def hot_partition_check(keys_traffic: dict[str, int], total_rus: int) -> list:
    """Flag any logical key whose traffic exceeds what ONE physical
    partition (~10k RU/s) could serve."""
    return [k for k, share in keys_traffic.items()
            if share / sum(keys_traffic.values()) * total_rus > 10_000]

if __name__ == "__main__":
    import math
    # 2 KB reads at session consistency
    print(point_read_rus(2))                       # -> 2
    # Tmax 10k RU/s, real average utilization 12%
    print(f"${monthly_autoscale_cost(10_000, 0.12):,.0f}/month")
    # ^ floor (1000 RU/s-equivalent billing) dominates most hours
    print(hot_partition_check({"tenantA": 70, "tenantB": 25, "tenantC": 5}, 30_000))
    # -> ['tenantA'] at 21k effective RU/s: throttle city despite headroom elsewhere
```

Run it with your own trace percentages: the exercise teaches that autoscale's floor and partition-key skew — not raw volume — drive most Cosmos cost/performance surprises.

## How it's done in production

Reference patterns: storage accounts per environment with ZRS default, lifecycle policies moving logs to Cool/Cold at day 30-90 and Archive beyond a year, immutable+WORM containers for audit streams, Entra-only auth with account keys rotated-but-unused; Cosmos containers keyed by high-cardinality tenant-aligned keys, autoscale Tmax set from p95 observed RU/s x burst factor, change feed processors building read-model projections, alerts on normalized RU consumption (>80%) and 429 rates; Azure SQL behind failover groups for regional DR, elastic pools for SaaS tenant databases, Hyperscale adopted when size or restore-time demands it; PostgreSQL Flexible with zone-redundant HA for anything user-facing, PgBouncer always on, PITR backups verified quarterly by actual restore tests.

| Symptom | Cause | Fix |
|---|---|---|
| Cosmos 429s during launch spike despite low overall load | Hot logical partition concentrating traffic | Re-key (synthetic/hierarchical), spread writes, raise only that container's throughput |
| Autoscale Cosmos bill flat-out huge with modest traffic | 0.1×Tmax floor billed most hours; Tmax set for rare peaks | Lower Tmax, split hot paths to dedicated containers, consider serverless for tiny workloads |
| Dashboard queries cost more than the app | Cross-partition fan-out queries consuming RUs linearly | Materialize via change feed, use Analytics/synapse-link style paths, aggregate offline |
| Postgres "too many connections already" | Functions/CA fleet x concurrency exceeds max_connections | Enable PgBouncer transaction pooling; size pool = instances x concurrency |
| Blob restore takes hours, stakeholders angry | Data landed in Archive/Cold tier unknowingly via lifecycle policy | Tier-aware retrieval runbook; rehydrate ahead of need; alert on tier transitions |
| SQL failover succeeded, app still erroring | Failover group flipped DNS but cached connections pinned to old primary | Short retry windows with connection reset; rely on `RedirectReadOnlyRegion`-style retry logic |

---

## Tradeoffs & when NOT to use it

- **When Cosmos's RU model hurts you:** unpredictable bursty traffic pays autoscale floors continuously; heavy ad-hoc analytics burns RUs per scan with no cache amortization; cost forecasting requires modeling RU-per-operation distributions rather than counting servers; and deep relational queries (multi-joins) are anti-patterns by design. If your workload is "medium-scale relational, spiky, analytics-heavy," PostgreSQL Flexible or Azure SQL serverless will usually be cheaper and saner. Cosmos earns its keep for planet-distributed, predictable-latency, high-write KV/document patterns — not as a default NoSQL reflex.
- **Archive tier is not storage you can query.** Rehydration is hours plus fees; if stakeholders expect instant access to "cold" data, they need Cool/Cold tiers, not Archive. Budget early-deletion charges when retention policies are uncertain.
- **Azure SQL Hyperscale isn't automatically better** — its log-service architecture changes backup/restore semantics and replica behavior; small databases gain nothing and pay more. It's the answer when size (~TB-class upward), restore speed, or read-replica counts demand it.
- **PostgreSQL Flexible same-zone HA saves money but shares the zone's fate** — zone-redundant HA is the user-facing default unless the workload tolerates zone-outage downtime.
- **Storage Queues stop being enough** when you need ordering guarantees, duplicate detection, transactions across queues, or rich dead-letter semantics — that's Service Bus territory, and retrofitting those features onto Storage Queues produces bespoke bugs.
- **pgvector is not a search engine.** Below ~millions of vectors it's excellent (HNSW, hybrid with tsvector); beyond that, filter-heavy workloads and multi-tenant isolation push toward AI Search or dedicated vector stores. Know your vector count trajectory before committing.

---

## Interview questions

### Q1 — Design blob tiering for a document pipeline: 10 TB/month ingested, accessed heavily for 30 days, occasionally for a year, audit-required for 7 years.
**Testing:** tier economics plus lifecycle automation.
**Answer:** Lifecycle policy: Hot → Cool at day 30 (past Cool's early-deletion window), → Cold around day 180-365 depending on observed access decay, → Archive at day 365+ for audit copies. Archive rehydration hours is acceptable for audit-only access; keep an index/manifest in Hot for discovery. Redundancy: ZRS baseline, GZRS if regional DR required; immutable WORM container (or versioned immutability) for the audit stream so even admins can't tamper.
**Follow-up trap:** *"What does the lifecycle policy NOT protect against?"* — early-deletion fees from misconfigured transitions (moving to Cool then deleting at day 20 re-bills the full 30-day minimum) and retrieval surprises: policies automate costs but don't understand access intent.

### Q2 — Explain Cosmos DB consistency levels and why Strong + multiple write regions don't combine.
**Testing:** distributed-systems fundamentals through Azure's lens.
**Answer:** Five levels from Strong (linearizable reads via global-majority quorums) through Bounded Staleness (K versions/T time lag), Session (read-your-writes within session token), Consistent Prefix, Eventual (single-replica reads). Multi-region writes can't offer Strong because that demands RPO=0 AND low-latency global commits simultaneously — physically impossible under partition tolerance; Microsoft explicitly blocks the combination, and Strong multi-region write latency equals roughly 2x RTT between furthest regions plus overhead at p99, which is why >~8000 km spreads disable Strong by default.
**Follow-up trap:** *"Which level do most apps actually need?"* — Session: read-your-writes covers the user-facing correctness most products mean by 'consistent', at single-replica read cost; reaching for Strong without a concrete linearizability requirement just doubles read RUs.

### Q3 — Your Cosmos container throttles during peak despite 100k provisioned RU/s. Walk the diagnosis.
**Testing:** partition physics over "add RUs."
**Answer:** Check normalized RU consumption per PHYSICAL partition: if one key consumes >its share (each physical partition serves up to ~10k RU/s), total capacity is irrelevant — the hot key caps throughput. Confirm via metrics showing skewed consumption; identify the key (usually tenant-id or timestamp-prefix); fix by synthetic keys (tenant+shard), hierarchical keys, or splitting the hot tenant's traffic pattern. Only after distribution is fixed does raising Tmax help.
**Follow-up trap:** *"Why did this pass load testing?"* — synthetic loads typically use uniform keys; production skew (one whale tenant, one busy hour) concentrates what tests distributed — test with production-shaped key distributions or catch it in staging with recorded traces.

### Q4 — Estimate the monthly cost difference between autoscale Tmax=50k RU/s with 15% average utilization versus manual 7,500 RU/s provisioned.
**Testing:** actual RU arithmetic, the thing that separates operators from tutorial readers.
**Answer:** Autoscale bills max(observed, 0.1×Tmax) hourly = floor of 5k RU/s-equivalent; at 15% average of 50k (=7.5k) typical billed ≈7.5k but many hours sit at the 5k floor during valleys — effectively paying for 5k-7.5k continuously. Manual 7,500 RU/s bills flat 24/7 regardless. The delta depends on valley depth: shallow valleys favor manual; deep valleys (dev/test, business-hours apps) make autoscale's floor still cheaper than flat provisioning only if floor < manual need. Do the multiplication per hour-class, never quote list price intuition.
**Follow-up trap:** *"When does serverless beat both?"* — tiny/idle-mostly containers where even 400 RU/s manual minimum dwarfs usage; serverless per-request billing wins until sustained throughput makes its higher per-RU rate dominate.

### Q5 — Compare Azure SQL failover groups' geo-DR against zone-redundant deployments: RPO/RTO tradeoffs?
**Testing:** DR arithmetic precision.
**Answer:** Zone-redundant deployment: synchronous replicas across zones in-region — RPO≈0 for zonal failures, RTO seconds-to-minutes, protects against datacenter loss only. Failover group: asynchronous geo-replication to paired region — RPO typically ~5 s (async lag), RTO tens-of-seconds-to-minutes once DNS cutover completes, survives region loss. They compose: zone-redundant inside each region plus a failover group across regions gives both layers. Application must handle transient connection errors on any failover regardless.
**Follow-up trap:** *"Async replication means possible data loss — how do you bound it?"* — monitor replication lag metrics as an SLO, force-sync critical writes where the feature exists, and design idempotency/compensation for the RPO window; pretending async is sync is the actual failure mode.

### Q6 — When would you choose PostgreSQL Flexible over Azure SQL Database for new OLTP, and when is that wrong?
**Testing:** honest engine-selection judgment.
**Answer:** Choose Flexible for: open-source stack alignment (ORM/ecosystem assumptions), extension needs (PostGIS, pgvector), licensing-cost sensitivity at scale, JSONB-first designs, avoiding SQL Server-specific T-SQL gravity. Wrong when: existing .NET estate leans on SQL Server tooling/SSIS/T-SQL depth, need Hyperscale-class scale (>32 TB-ish class), require SQL Server feature parity (columnstore breadth, advanced security integrations), or org skills are deeply MSSQL. Both have HA parity (~99.99% zone-redundant); decide on ecosystem and scale ceiling, not religion.
**Follow-up trap:** *"Single Server users had no choice — what actually changed moving to Flexible?"* — control plane freedom (zone selection, maintenance windows, extensions, PgBouncer) but also responsibility shifts: parameter tuning, connection management discipline; migrations used dump/restore or replica-based cutover since retirement was forced March 2025.

### Q7 — pgvector on Flexible Server versus Azure AI Search for a RAG system at ~2M chunks: pick and defend.
**Testing:** vector-store judgment relevant to his AI-heavy resume.
**Answer:** At 2M vectors, pgvector HNSW is comfortably capable and keeps embeddings next to relational metadata — filtered retrieval via SQL joins, transactional updates with documents, one less service. AI Search wins when: hybrid lexical+vector+semantic-ranker pipeline out-of-the-box matters, multi-tenant security filtering at index level is needed, or ops team shouldn't own a database for search. Latency profile similar at this scale. My default at his described scales: Flexible+pgvector unless product needs semantic ranker quality jumps or massive filter fan-outs.
**Follow-up trap:** *"What breaks first as vectors grow?"* — index build/rebuild times and memory for HNSW graphs; plan for periodic reindex windows and consider partial indexes per tenant before jumping services.

### Q8 — Storage Queue vs Service Bus for order-processing events: decision factors?
**Testing:** messaging-tier fluency adjacent to storage.
**Answer:** Service Bus when: FIFO sessions per entity, exactly-once-flavored dedup window, transactions spanning queue operations, native dead-lettering with rich metadata, topics/rules for pub-sub fan-out, VNet-private premium tiers. Storage Queues when: simple decoupling, huge message counts cheaply, longer TTL needs (up to 7 days), tight integration with blob-triggered pipelines. Orders flow usually justifies SB Premium/Standard for sessions+DLQ alone.
**Follow-up trap:** *"Cost-wise?"* — Storage Queues are dramatically cheaper per operation; SB's premium pricing buys isolation and features, not raw throughput economics — quantify op count before defaulting to SB everywhere.

### Q9 — A stakeholder wants "instant access" to last year's logs currently proposed for Archive. Resolve the conflict.
**Testing:** translating requirements into tier reality.
**Answer:** Quantify access: true instant-access needs Cool/Cold tier pricing (~2-6x archive storage but online). Offer middle path: recent 90 days Cool/Cold online, older Archive with documented rehydration SLA (hours) plus pre-hydration runbooks for anticipated investigations; or export audit subset to a searchable store (Log Analytics archive/search-job pattern) sized to query frequency. Present invoice deltas per option — the conversation resolves on numbers, not preferences.
**Follow-up trap:** *"They insist everything stays instantly queryable."* — then budget honestly for Cold-tier storage plus query-scan costs, and set lifecycle review cadence; unbounded 'keep hot forever' is a governance failure worth escalating, not silently absorbing.

### Q10 — Explain change feed and give two architectures built on it.
**Testing:** knowing Cosmos beyond CRUD.
**Answer:** Change feed is a durable, ordered-by-key log of inserts/updates (not deletes by default) readable via pull model or processor library with lease-based load balancing across consumers — effectively Kafka-like semantics native to the container. Architectures: (1) materialized views/projections — transform documents into denormalized read models for specific query shapes, cutting RU-expensive cross-partition queries; (2) CDC pipelines into warehouses/event systems replacing polling exporters; also cache invalidation streams feeding Redis/AI Search indexers.
**Follow-up trap:** *"Deletes?"* — change feed doesn't capture them natively; soft-delete markers (tombstone property) are the standard pattern, with cleanup jobs compacting history later — forgetting this produces zombie records downstream.

### Q11 — Design multi-tenant isolation on Azure SQL: shared database with row-level security vs elastic pools vs database-per-tenant. Tradeoffs?
**Testing:** SaaS data-plane architecture depth.
**Answer:** Row-level security (RLS) in one DB: cheapest density, simplest ops, noisy-neighbor risk, blast radius = whole DB; enforce via SESSION_CONTEXT predicates. Elastic pools of per-tenant DBs: strong isolation, per-tenant restore/SLA stories, moderate density; management surface grows with tenants. Fully isolated servers: maximum isolation/compliance story, highest cost. Common progression: RLS early-stage → elastic pools at compliance-sensitive growth → dedicated for whale tenants only.
**Follow-up trap:** *"Where does RLS bite in production?"* — every access path must carry tenant context correctly; one forgotten SESSION_CONTEXT set call reads cross-tenant rows silently — mitigate with default-deny policies and automated context-injection tests per repository method.

### Q12 — Rank these data-layer incidents by frequency: hot partitions, wrong blob tier invoices, connection-pool exhaustion, failed geo-failover DNS propagation. Justify.
**Testing:** incident-pattern prioritization.
**Answer:** 1) Connection-pool exhaustion — near-universal once serverless compute meets serverless databases (instances x concurrency math ignored). 2) Blob-tier invoice surprises — lifecycle policies quietly doing their job while access patterns shift. 3) Hot partitions — real but mostly caught by RU-normalized alerts if monitoring exists; devastating when absent. 4) Failed failover DNS — rarest because failovers themselves are rare, but highest drama per occurrence. Frequency inversely tracks how much each gets discussed in vendor blogs.
**Follow-up trap:** *"One guardrail covering most?"* — capacity-aware defaults in IaC: pool sizing formulas, mandatory normalized-RU alerts, tier-transition notifications — encode the arithmetic once, catch all four classes earlier.

---

## Red flags that fail you

- Quoting Cosmos consistency levels without knowing Session is the default and Strong can't span multi-region writes.
- Treating autoscale as "pay only for what you use" (the 0.1×Tmax floor says otherwise).
- Recommending Single Server for new Postgres workloads (retired March 2025).
- Not knowing blob Archive means hours-long rehydration plus early-deletion fees.
- Partition-key advice that ignores skew ("just use tenantId" without whale-tenant discussion).
- Confusing zone redundancy with geo-redundancy (RPO 0 vs ~5 s).
- Skipping PgBouncer in any Functions/Container-Apps-to-Postgres design.
- Calling pgvector enterprise-search-grade at hundreds-of-millions-of-vectors scale.

---

## Cheat card

```
BLOB TIERS: Hot > Cool(~30d min) > Cold(~90d min) > Archive(hours rehydrate,
            std priority ~15 h) · lifecycle policies automate · early-delete fees
REDUNDANCY: LRS(1 DC,3 copies) ZRS(3 zones) GRS/GZRS(paired region, async)
            RA- = read secondary · durability ~11 nines(LRS) · WORM immutable
FILES: SMB/NFS · premium SSD vs HDD std · File Sync bridges on-prem
QUEUES: 64 KB msgs · TTL <= 7 days · at-least-once · <queue>-poison convention
        SB wins on: sessions/FIFO, dedup, DLQ, topics, transactions

COSMOS: 1 RU ~= 1 KB point read (session) · strong reads = 2x RU
        min 400 RU/s manual · autoscale bills max(used, 0.1*Tmax)/hour
        physical partition: 50 GB, ~10k RU/s cap · logical: 20 GB
        HPK up to 3 levels (/id-ending pattern beats 20 GB) · item <= 2 MB
        consistency: Strong/BoundedStaleness/Session(default)/Prefix/Eventual
        strong x multi-write-regions IMPOSSIBLE · RPO: 1-region <240 min(!),
          multi-region <15 min, strong=0 · p99 <10 ms SLA (single region)
        change feed = ordered durable log -> projections/CDC (no deletes:
          soft-delete tombstones)

AZURE SQL: vCore GP(remote stg)/BC(local SSD+secondaries)/Hyperscale(~128 TB,
           named replicas, fast restore) · serverless auto-pause ~1 h idle
           failover groups: async geo, RPO ~5 s, DNS cutover
PG FLEX:   Single Server RETIRED 2025-03 · B-series burstable -> E/D series
           HA: same-zone vs zone-redundant (~99.99%) · failover ~60-120 s
           read replicas · PgBouncer ALWAYS for serverless fleets
           pgvector HNSW good to millions-scale RAG

INCIDENT ORDER: pool exhaustion > tier invoices > hot partitions > failover DNS
GUARDRAILS: instances x concurrency <= pool size · normalized-RU alerts >80%
            tier-transition alerts · verify restores quarterly
```

## Sources

- [Azure Cosmos DB limits and quotas — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits); accessed 2026-08-23
- [Partitioning and horizontal scaling in Azure Cosmos DB — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning); accessed 2026-08-23
- [Consistency levels in Azure Cosmos DB — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/consistency-levels); accessed 2026-08-23
- [Unlimited logical partition storage with hierarchical partition keys — Microsoft Learn](https://learn.microsoft.com/en-us/azure/cosmos-db/hierarchical-partition-keys-unlimited-scale); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
