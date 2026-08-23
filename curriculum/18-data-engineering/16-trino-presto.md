# Trino & Presto: Federated Query Engines, Catalogs, and When They Beat a Warehouse

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** T18-lakehouse, T18-pyspark-scratch · **Updated:** 2026-08-23
> **Module id:** `T18-trino-presto` · **Tags:** query,critical

## The 30-second version

Trino, which was born as Presto at Facebook in 2012 and forked into its own project in late 2020, is a distributed MPP SQL engine that runs ANSI-SQL directly over data wherever it already lives, through a connector SPI: one coordinator parses, plans, and schedules; workers execute splits; connectors translate plan fragments into reads and writes against Hive, Iceberg, Delta, Postgres, Kafka, or anything else you can bind. Federation is the superpower and the most abused feature: one query can join a Postgres table to an Iceberg table to a Kafka topic with zero data movement, but every byte it cannot push down crosses the network through Trino's memory. Memory is the resource that kills Trino deployments: the query that would spill politely in Spark instead fails with EXCEEDED_MEMORY_LIMIT unless you have configured memory limits and spill deliberately. The honest positioning: interactive ad-hoc and light ELT over lakehouse tables, plus federation for low-volume cross-source joins; not petabyte nightly batch, and never an OLTP substitute.

## Why this gets asked

Because "we query it with Presto/Trino/Athena" appears on half the resumes of senior data engineers, and interviewers have learned that most candidates who ran Athena queries cannot explain what a coordinator does, what a split is, or why their 3 TB join failed while a 30 GB join succeeded. The interviewer has personally lived through one of these: an Athena bill shock from a full-scan habit, a Trino cluster OOM-killed by one careless cross join, or a "federated query" against production Postgres that degraded the OLTP database during business hours. They want evidence you know where the engine ends and the warehouse begins, because teams that confuse the two either overspend on compute or build a fragile virtual warehouse nobody can debug. At staff level, expect the architecture question inverted: "when would you refuse federation and copy the data instead?"

---

## Lineage: past → present → future

**What came before.** Interactive SQL at web scale meant MPP appliances: Teradata and Netezza sold racks with proprietary storage formats and a load-your-data-first contract, which made them fast but expensive and closed. The Hadoop generation replaced them with Hive (2008 onward): SQL compiled to MapReduce jobs over files on HDFS. It worked at exabyte scale, and that was the problem it solved, but the cost was latency: even a modest aggregation took minutes because every query paid full job-launch overhead across hundreds of JVMs. By 2011 Facebook's warehouse had outgrown this for human-facing analytics; engineers waited hours for dashboards. Four engineers (Martin Traverso, Dain Sundstrom, David Phillips, Eric Hwang) started Presto in 2012 specifically to fix that gap: a long-lived, in-memory, pipelined MPP engine over open file formats rather than batch jobs. It was open sourced in late 2013 and quickly became the standard "SQL-on-everything" layer outside the appliance world.

**Where it stands now.** The governance split defines the landscape. In late 2018 the original creators left Facebook and resumed the project as PrestoSQL; in September 2019 Facebook established the Presto Foundation under the Linux Foundation and moved to enforce the Presto trademark; on 27 December 2020 the creators' project was renamed Trino. Since then the two have diverged hard: Starburst (founded by the same creators) measures roughly three times the development velocity in Trino, which gained the fault-tolerant execution mode, better Delta and Iceberg support, and steady SQL dialect convergence, while Presto remained the engine inside Meta (running at multi-exabyte scale, which is its own justification) and a smaller open community. AWS quietly settled the argument for much of the market: Athena's engine version 2 was Presto 0.217, and Athena engine version 3 is Trino-based, so a huge fraction of "Athena users" are Trino users who never installed anything. The live disagreement is philosophical: Snowflake and BigQuery argue data should be copied into one governed platform, while Trino argues the query engine should come to the data. Both camps ship materialized views now, which is telling.

**Where it's heading.** Three directions with different confidence. First, fault-tolerant execution (exchange manager persisting intermediate results to S3/HDFS so a lost worker retries its splits instead of killing the query) landed experimentally in early 2023 and keeps expanding; this is real and shipping, and it moves Trino into territory that previously required Spark. Second, Iceberg is becoming the default catalog story, with Trino acting as both query engine and maintenance tool (expiring snapshots, rewriting manifests); high confidence direction. Third, disaggregated architectures and better result reuse: materialized views exist in OSS Trino for the Hive/Iceberg/Delta connectors with manual REFRESH, and commercial distributions add automatic refresh and caching; expect the gap between "query engine" and "warehouse" to keep narrowing. Speculative flag: Trino replacing dedicated warehouses outright. It happens for modest scales, but nobody has shown Trino beating Snowflake-class engines on concurrent heavy BI without significant tuning talent on staff.

---

## Mental model

```
                        ┌──────────────────────────────┐
  client ──SQL────────▶ │ COORDINATOR                  │
                        │  parse → analyze → plan      │
                        │  optimize → schedule splits  │
                        │  tracks cluster/query memory │
                        └──────┬───────────────────────┘
                               │ stage graph (DAG)
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐     ┌──────────┐     ┌──────────┐
        │ WORKER 1 │◀───▶│ WORKER 2 │◀───▶│ WORKER 3 │   exchanges =
        │ splits   │     │ splits   │     │ splits   │   shuffle boundaries
        └────┬─────┘     └────┬─────┘     └────┬─────┘   between stages
             │                │                │
        ┌────▼─────┐     ┌────▼──────┐    ┌────▼──────┐
        │connector │     │connector  │    │connector  │   catalog.schema.table
        │ iceberg  │     │ postgres  │    │ kafka     │   each catalog binds
        └────┬─────┘     └────┬──────┘    └────┬──────┘   one connector
             ▼                ▼                ▼
         S3/Iceberg       OLTP DB          topics
```

The two sentences that unlock everything: a **stage** is one parallelized fragment of the plan, and a **split** is the unit of work inside a stage (roughly "one connector chunk, e.g. one file stripe or one predicate-pushed scan range"). Workers are stateless between queries; all state lives in the source systems and in the memory the coordinator is accounting for right up until it evicts, spills, or kills your query.

---

## How it actually works

### 1. Query lifecycle, mechanically

Client submits text over HTTP to the coordinator. Parse and analysis produce a logical plan; the planner then applies optimization rules (predicate pushdown, projection pruning, join reordering via cost-based optimization when table stats exist) and decomposes the plan into a tree of stages connected by exchanges. A **local exchange** connects threads within one node; a **remote exchange** ships partitions over HTTP between workers. The scheduler assigns splits to workers, which advertise capacity back; the coordinator streams status updates and aggregates memory usage continuously (workers push memory reports on a short interval, so the cluster-wide picture lags reality by milliseconds, not seconds). Results stream back incrementally, which is why `LIMIT 10` on a huge table returns fast while the rest of the stage keeps running until cancelled.

Two properties of the scheduler matter operationally. First, blocking operators (hash build side of a join, full aggregation, ORDER BY) must consume their entire input before emitting anything: that is where memory goes, and why "it worked with LIMIT" proves nothing about the un-LIMITed version. Second, task concurrency per worker scales with CPU cores; a cluster of c6i.4xlarge workers (16 vCPU) wants dozens of concurrent splits per node, so undersizing the fleet and oversubmitting queries produces queueing you will see as time-to-first-byte latency, not errors.

### 2. Connectors and catalogs: how federation is possible

A **catalog** maps a name (say `lake`) to a configured connector instance plus schema mapping, giving three-part naming `lake.silver.orders`. The connector SPI lets the source declare capabilities: Can it filter? Project columns? Aggregate? Return table statistics? Support topN? The optimizer pushes predicates and projections down to any capable source and leaves the residual plan to execute inside Trino. This is why `WHERE created_at > now() - interval '1' day` against Postgres becomes a cheap indexed lookup, while the same filter applied after joining to Iceberg forces a full transfer of the joined result.

The mechanical truth of federation: **whatever the connectors cannot absorb, the exchange carries.** Joining a 500 million row Postgres table to Iceberg without a selective predicate means shipping 500 million rows over HTTP into worker memory. Federation is free only when pushdown makes the transferred cardinality small. Check with `EXPLAIN`: the plan shows the `PostgresTableHandle` carrying your predicate, or embarrassingly, nothing.

### 3. Memory management: the thing that actually breaks

Trino divides memory into categories with distinct enforcement:

- **User memory**: allocation attributable to the query's blocking operators (hash tables, sort buffers). Limited by `query.max-memory` (cluster-wide per query) and `query.max-memory-per-node`.
- **Revocable memory**: intermediate state the engine *chooses* to hold, which it can revoke and spill to local disk when the cluster is under pressure (spill must be enabled; the operators that support it include hash aggregation, hash join, and sort, with window functions arriving later than the others).
- **System memory**: internal buffers and exchange queues, tracked but not user-tunable.

When a query exceeds its user-memory limits, the coordinator kills it immediately with EXCEEDED_MEMORY_LIMIT, naming the offending operator and bytes requested; this fail-fast behavior is correct and you should not fight it by raising limits tenfold, because the alternative failure mode is a worker hitting OS OOM-kill and taking down every co-located query. When the *cluster* is short but the pressure is revocable, running queries spill and survive with a latency hit. Practical sizing: leave real headroom below the container/JVM ceiling (a common rule is keeping per-node query limits well under half of heap on shared clusters, reserving the rest for exchange buffers, untracked native allocations, and GC), enable spill for batch-ish workloads, and set `query.max-execution-time` so runaway queries die instead of squatting.

### 4. Join strategies and the 100 MB instinct

With `join.distribution-type=AUTOMATIC` (the default), the optimizer broadcasts the build side when its estimated size sits under `join.broadcast-threshold` (on the order of 100 MB) and otherwise partition-hash joins on the key, shuffling both sides. Broadcast of an underestimated large table is a classic OOM generator, which is one more reason current table statistics matter. Skewed keys create straggler workers holding giant hash partitions; the mitigations are bucketed/organized Iceberg tables aligning with join keys, pre-aggregation, or simply moving that workload to Spark, whose skew handling (AQE splitting skewed partitions) is mature where Trino's remains coarser.

### 5. CTEs, materialized views, and the caching question

Historically Trino inlined common table expressions like macros: three references to a CTE meant three executions of its subtree. Newer releases improve reuse planning, but the safe mental model for review and billing is "N references = N scans" until you verify reuse in the plan. OSS Trino supports **materialized views** over the Hive, Iceberg, and Delta connectors: `CREATE MATERIALIZED VIEW` stores the result as a table and the optimizer transparently rewrites eligible queries to read it, but refresh is explicit (`REFRESH MATERIALIZED VIEW mv_name`); there is no built-in scheduler, and freshness staleness risk transfers to you. There is **no general automatic result cache in OSS Trino**: repeated identical queries re-pay the full cost. Commercial distributions (Starburst) and surrounding infrastructure (external result caching layers, Iceberg metadata caches) fill this gap. If someone tells you "we rely on Trino caching," ask which product feature they mean.

### 6. Athena, BigQuery, and the managed variants

Amazon Athena is serverless Trino: no clusters, priced primarily per TB scanned (about $5 per TB), with engine version 3 tracking Trino releases. Its constraints are Trino's constraints wearing a managed face: scan volume is your cost lever, so partitioning, columnar formats, and predicate selectivity translate directly to dollars; provisioned throughput modes change the math but not the physics. Federated queries in Athena run through connector SDKs executed in Lambda, which adds per-call latency and function limits to the federation equation, fine for dashboard lookups, hostile to row-by-row probing. BigQuery's federation is narrower: external tables via BigLake over object stores, plus federated queries to Cloud SQL and Spanner through connection objects, all billed within the BigQuery model. The decision pattern across all three: managed serverless wins for bursty, multi-team ad-hoc analytics; self-managed Trino wins when you need custom connectors, aggressive per-query cost control, or consistent sub-second-to-few-second performance that shared serverless capacity cannot promise.

---

## Build it from scratch

Minimal single-node federation demo, fully runnable locally (untested sketch, adapted from the official container image docs):

```bash
# 1. Start a single-node Trino container
docker run --name trino -d -p 8080:8080 trinodb/trino:latest

# 2. Add a Postgres catalog: create etc/catalog/business.properties inside the
#    container (or mount it):
#    connector.name=postgresql
#    connection-url=jdbc:postgresql://host.docker.internal:5432/appdb
#    connection-user=readonly
#    connection-password=secret
docker restart trino

# 3. Federate the built-in memory catalog against Postgres
docker exec -it trino trino
```

```sql
-- untested sketch: the federation moment
CREATE TABLE memory.demo.events AS
SELECT * FROM VALUES
  (1, 'signup', TIMESTAMP '2026-08-20 09:00:00'),
  (2, 'purchase', TIMESTAMP '2026-08-21 10:00:00')
AS t(id, event, ts);

SELECT u.email, count(*) AS purchases          -- aggregate pushed to Postgres?
FROM business.public.users u
JOIN memory.demo.events e ON e.id = u.id
GROUP BY u.email;

-- prove what actually happened:
EXPLAIN ANALYZE SELECT count(*)
FROM business.public.orders
WHERE created_at > TIMESTAMP '2026-08-01 00:00:00';
-- read the plan: if the PostgresTableHandle shows your predicate,
-- pushdown worked; if the filter sits above the scan, you shipped rows for nothing
```

Three things this exercise teaches faster than any doc: catalogs are just properties files (so "which data can this cluster see" is a config-review question), `EXPLAIN ANALYZE` is where federation honesty lives, and the memory catalog exists precisely so you can prototype joins without touching real sources.

---

## How it's done in production

Production deployments divide into four shapes: **self-managed Trino on Kubernetes** (Helm chart from the project, coordinator + workers separated by node groups, exchange over the pod network), **Starburst Enterprise/Galaxy** (commercial Trino adding autoscaling, access control, caching, automatic MV refresh), **Amazon Athena** (serverless, per-TB pricing), and **Presto at hyperscalers** (Meta-scale bespoke deployments, irrelevant to almost everyone interviewing). Common production additions regardless of flavor: a query-governance layer (resource groups and queue policies bounding concurrency per workload class, so a dashboard stampede cannot starve the finance close), JMX/Prometheus metrics on running-query memory versus limits, and Iceberg table maintenance scheduled beside the query engine.

| Symptom | Cause | Fix |
|---|---|---|
| EXCEEDED_MEMORY_LIMIT naming a hash join operator | Broadcast join picked an underestimated build side, or missing stats | Collect table statistics, cap `join.broadcast-threshold`, force PARTITIONED for that query |
| Worker pods OOMKilled while query limits look respected | Native/untracked memory (exchange buffers, client libs) plus heap headroom exhausted | Lower per-node query limits, raise container limits, verify `memory.heap-headroom-per-node` |
| Queries queue for seconds before starting | Resource group or concurrency limit saturated by chatty BI tool | Raise worker count or concurrency, add result-layer caching, stagger dashboard refreshes |
| Simple count takes minutes on Iceberg/Hive table | Metadata explosion: thousands of small files, deep partition listing | Compaction (`OPTIMIZE`), rewrite manifests, partition on real predicates |
| Federation query degrades production Postgres | Predicate not pushed down; full table shipped per dashboard refresh | Fix pushdown (indexed predicate), or replicate the table on schedule instead |
| Long batch query dies mid-flight on worker loss | Classic best-effort mode restarts whole query | Enable fault-tolerant execution with the exchange manager backed by S3/HDFS |

---

## Tradeoffs & when NOT to use it

- **Do not use Trino as your nightly bulk transform engine without fault-tolerant mode.** Best-effort execution means one worker restart replays a 2 hour query; Spark with AQE plus checkpointing handles churn better. With the exchange manager enabled this objection shrinks considerably, which is exactly the tradeoff to articulate.
- **Do not federate OLTP databases into hot paths.** Every dashboard refresh becomes load on a database sized for transactions. Federation belongs behind selective predicates and low frequency, or behind a replica.
- **Do not serve row-level application lookups from Trino.** It is an MPP scan engine; point lookups pay coordinator round trip plus stage startup measured in hundreds of milliseconds minimum, versus low-single-digit milliseconds for a keyed read. If you catch yourself doing `SELECT ... WHERE id = ?` through Trino, stop.
- **Do not assume federation replaces ETL for anything analytical-heavy.** Copying data once (ETL) amortizes transfer cost across many queries; federation re-pays it per query. Break-even is roughly "will this join run many times?" Many times: copy. Once or twice, exploratory: federate.
- **Compliance can veto federation entirely.** A cross-region query moves bytes between jurisdictions mid-execution; if your sources sit in regulated regions and your Trino cluster does not, no amount of engineering fixes the policy violation. This is a real reason enterprises choose copy-based warehouses with region pinning.
- **Concurrency-heavy BI at strict SLAs favors warehouses.** Trino resource groups help, but Snowflake/BigQuery multi-cluster models handle 200 concurrent dashboard users more gracefully than one tuned Trino cluster, unless staff exists to tune it.

---

## Interview questions

### Q1 — Walk me through what happens when a query hits Trino, from SQL to rows.
**Testing:** whether "distributed query engine" is vocabulary or understanding.
**Answer:** Coordinator receives SQL over HTTP, parses and analyzes it, optimizes the plan (pushdown, join reordering with stats), splits it into a DAG of stages connected by exchanges, and schedules splits onto workers. Each worker runs splits concurrently, shuffling intermediate data through local and remote exchanges; blocking operators accumulate state in memory until complete. Results stream back incrementally while the coordinator tracks per-query memory cluster-wide and kills queries that breach limits.
**Follow-up trap:** *"Where exactly can this fail besides bugs?"* — memory exhaustion on blocking operators, metadata bottlenecks on small-file tables, queueing at resource-group saturation, worker loss restarting the whole query in best-effort mode. Listing failure surfaces, not just the happy path, is the signal.

### Q2 — What is the difference between Presto and Trino, honestly?
**Testing:** whether you know the ecosystem politics and technical divergence.
**Answer:** Same origin: Presto, built 2012 at Facebook for interactive analytics over their warehouse, open sourced 2013. The creators left in 2018 and continued as PrestoSQL; after Facebook formed the Presto Foundation under the Linux Foundation and enforced the trademark in 2019, the creators' project renamed to Trino in December 2020. Since then Trino developed several times faster by most counts, gaining fault-tolerant execution, stronger Iceberg/Delta support, and dialect breadth, while Presto stayed the in-house Meta engine with a smaller community. Athena engine v3 is Trino-based, so most managed-cloud usage traces to Trino.
**Follow-up trap:** *"Does the fork matter technically if the SQL looks identical?"* — increasingly yes: connector quality, spill coverage, and fault tolerance diverged, and new deployments should default to Trino unless operating inside a Meta-lineage stack. Knowing the rename happened over governance and trademark, not technology, shows you read primary sources.

### Q3 — Explain federation versus copying data into a warehouse. When is each right?
**Testing:** the core judgment of the module.
**Answer:** Federation executes the query at the sources' location boundary, transferring only what pushdown leaves; copying (ETL) pays transfer and storage once, then serves unlimited queries locally at warehouse speed. Federation wins for low-frequency, highly selective, exploratory, or compliance-boundary-respecting access where maintaining a copy is pure overhead. Copy wins when many consumers hammer the same data, when you need warehouse-grade join performance, or when source SLAs cannot absorb analytical load. Break-even intuition: federation re-pays transfer per query; copy amortizes it.
**Follow-up trap:** *"Your BI team runs the same five federated dashboards hourly. Right or wrong?"* — wrong: five dashboards hourly re-transfer the same bytes 120 times a day; a nightly incremental sync into Iceberg plus local queries cuts network cost and removes OLTP exposure, at the price of one pipeline to own.

### Q4 — A query fails with EXCEEDED_MEMORY_LIMIT. What happened and what do you do?
**Testing:** memory-model depth, the number one operational Trino skill.
**Answer:** The query's user memory breached `query.max-memory` or `query.max-memory-per-node`; the error names the operator, usually a hash join build or aggregation. Diagnosis path: read which operator and how many bytes, check whether a broadcast join chose an underestimated build side (missing or stale table statistics), check for skew concentrating one partition, check whether LIMIT-based testing masked the full-input cost. Fixes in order: gather stats, force PARTITIONED join, reduce input cardinality earlier, enable spill so pressure becomes revocable, and only then consider raising limits, which trades fail-fast correctness for cluster-wide OOM risk.
**Follow-up trap:** *"Why not just give workers 256 GB and raise the limits?"* — because untracked native memory and GC headroom grow with heap, OS OOM-kills take down every co-located query on the node, and one tenant's runaway query then causes a fleet incident. Limits are isolation, not inconvenience.

### Q5 — What does the connector SPI actually do during a federated join, and how do you verify pushdown happened?
**Testing:** mechanism plus verification habit.
**Answer:** The connector exposes metadata (tables, columns, stats) and implements scans the planner can decorate with pushed filters, projections, aggregations, limits, and topN depending on declared capability. During planning, applicable operations become part of the connector's table handle; whatever remains executes inside Trino with exchanges carrying the residual rows. Verification: `EXPLAIN` (or `EXPLAIN ANALYZE`) and inspect the source-scan node; if your WHERE clause appears in the connector's table handle, pushdown occurred, and on Postgres you can confirm in `pg_stat_statements` that the parameterized filtered query arrived.
**Follow-up trap:** *"Pushdown worked but the query is still slow. Now what?"* — pushdown reduced rows, not necessarily work: a filter on an unindexed column still scans remotely, and aggregation pushdown helps only if the source can exploit indexes or materializations. Move to measuring where time goes (remote scan duration in the plan), and consider replicating the table if it recurs.

### Q6 — How does memory management work across a Trino cluster?
**Testing:** user versus revocable memory and the kill-versus-spill decision.
**Answer:** Per-query memory splits into user memory (blocking-operator state, strictly limited per node and cluster wide) and revocable memory (state the engine may evict and spill to local disk when the cluster tightens), plus tracked system memory. Workers report usage to the coordinator frequently; when limits are hit the coordinator kills the query with EXCEEDED_MEMORY_LIMIT rather than risking worker death. Spill must be enabled and applies to hash aggregation, hash join, and sorts among others; spilled queries survive with a latency penalty.
**Follow-up trap:** *"If spill exists, why keep hard limits at all?"* — spill converts memory pressure into disk IO pressure, and a cluster where every query spills simultaneously degrades into thrashing that hurts everyone; hard user limits bound worst-case per query, spill absorbs moderate overshoot. Both mechanisms compose; neither substitutes for the other.

### Q7 — Your Trino CTE is referenced three times in the final query. How many times does it execute?
**Testing:** knowledge of inlining semantics and verification habits.
**Answer:** Treat it as three executions: Trino historically inlines CTEs like macro expansion, and although newer optimizers improve reuse in some plans, the conservative and usually correct assumption is one execution per reference. Verify with EXPLAIN: if you see three copies of the subtree, rewrite using a temporary table or a materialized view for expensive shared subtrees.
**Follow-up trap:** *"So CTEs are bad?"* — no: they are free when referenced once and invaluable for readability; the cost only appears with multiple references over expensive scans. Saying "measure, don't superstition" and knowing the EXPLAIN check is stronger than either dogma.

### Q8 — When does federated query become an anti-pattern?
**Testing:** the senior judgment the whole module exists for.
**Answer:** Five recurring cases: hot-path OLTP sources absorbing analytical load; row-level lookups paying MPP stage-startup latency per call; high-cardinality joins where pushdown cannot shrink transfers; compliance regimes where bytes crossing regions violate policy; and anything needing transactional consistency across sources, which federation cannot provide since it reads without cross-source snapshots. In all five, copying data on schedule, or moving the compute to the data's home, beats live federation.
**Follow-up trap:** *"Isn't 'just copy it' how shadow pipelines proliferate?"* — yes, which is why the answer includes governance: a managed ingestion layer with SLAs and contracts, not fifty ad hoc dumps. Naming the organizational consequence, not only the technical tradeoff, distinguishes staff-level answers.

### Q9 — Compare Athena, self-managed Trino, and BigQuery for a 40-analyst ad-hoc workload over 80 TB in S3.
**Testing:** managed-versus-self-managed economics grounded in mechanics.
**Answer:** Athena: zero ops, roughly $5 per TB scanned, so cost is governed entirely by partitioning/format/selectivity discipline; shared capacity means noisy neighbors affect tail latency; federated connectors ride Lambda with per-call latency. Self-managed Trino: fixed cluster cost that flat-lines above heavy usage, custom connectors, predictable latency once tuned, but you own upgrades, memory tuning, and security patches. BigQuery: strongest if data lands in its storage or BigLake external tables suffice, slot-based pricing smooths cost, but its federation surface (Cloud SQL, Spanner, BigLake) is narrower than Trino's connector range. Forty analysts over 80 TB usually starts on Athena, graduates to provisioned capacity or self-managed when spend or latency demands it.
**Follow-up trap:** *"Your Athena bill doubled month over month. First three things you check?"* — new unpartitioned scans (query the Athena API for scanned bytes by query/user), a dashboard switching from partition-pruned to full-table patterns, and a format regression (JSON over Parquet). Cost incidents are almost always scan-discipline incidents.

### Q10 — What is fault-tolerant execution and what does it change about Trino's role?
**Testing:** awareness of the biggest architectural shift since the fork.
**Answer:** Traditionally Trino was best-effort: losing a worker failed the query and restarted it from scratch, tolerable for 30 second queries, brutal for 2 hour ones. Fault-tolerant execution persists stage intermediates to an exchange manager backed by S3 or HDFS so a lost worker's splits retry from checkpointed state, extending Trino into longer batch territory that belonged to Spark. Landed experimentally in early 2023 releases and hardened since; requires enabling the exchange manager and accepting IO overhead.
**Follow-up trap:** *"Does that make Spark redundant?"* — no: Spark retains richer ML/UDF ecosystems, mature AQE skew handling, and streaming; Trino FT covers batch SQL transforms elegantly but the ecosystems differ. Claiming total replacement signals vendor-blog thinking; claiming overlap with different centers of gravity signals judgment.

### Q11 — Why does a small-files problem hurt Trino so badly, and what fixes it at the table-format layer?
**Testing:** whether you connect engine symptoms to lakehouse hygiene.
**Answer:** Every file becomes (at least) one split with open/read/close overhead plus metadata listing; 2 million one-MB Parquet files mean millions of splits and coordinator-side planning dominated by listing and manifest resolution, so a simple count takes minutes before any data movement. Fixes belong to the table format: Iceberg compaction (`OPTIMIZE` or rewrite_data_files procedures), manifest rewriting, and partition evolution to match real predicates; Hive tables additionally suffer partition-listing storms that Iceberg's metadata tree eliminates.
**Follow-up trap:** *"Who should own compaction, and when?"* — scheduled alongside ingestion with thresholds (target file size around 128 MB, compact when small-file ratio breaches it), because reactive cleanup after dashboards degrade means you already paid weeks of wasted compute. Assigning ownership explicitly is the staff-level part.

### Q12 — Design the query layer for a company with a Snowflake warehouse, an Aurora OLTP pair, and 300 TB of event data in S3 as JSON. Leadership wants "one place to ask questions."
**Testing:** synthesis under realistic messiness, the actual staff interview.
**Answer:** Convert events to Parquet under Iceberg incrementally (existing ingestion gains a format step; 300 TB of JSON scanned raw is a cost bomb on any engine). Stand up one Trino cluster (or Athena) exposing: lake catalog over Iceberg, a replica-backed Postgres catalog for dimensional lookups, and leave Snowflake for the finance-grade modeled warehouse, federating only selective, low-volume bridges. Governance: resource groups separating BI from ad-hoc, per-query memory caps, mandatory EXPLAIN review for cross-catalog queries, and a rule that anything queried daily gets materialized. "One place to ask" becomes one catalog surface, not one physical copy of everything, because the latter recreates the ETL farm they hired you to retire.
**Follow-up trap:** *"Leadership insists on federating Aurora directly instead of replicas. Your move?"* — quantify blast radius: dashboard-refresh query patterns against OLTP primaries during peak, propose read replica plus pushdown-enforced guardrails (statement timeouts, resource group caps), and escalate the residual risk in writing. Being the engineer who says "here is the risk, here is the cheaper safe alternative, here is the decision deadline" is the entire principal pitch.

---

## Red flags that fail you

- Using "Presto," "Trino," and "Athena" interchangeably with no awareness of the fork or that Athena engine v3 is Trino-based.
- Describing Trino as a database: no discussion of storage, transactions, or why point lookups are wrong.
- Having run Athena queries but unable to say what a coordinator or split is.
- Proposing federation against production OLTP with no pushdown or replica discussion.
- Treating EXCEEDED_MEMORY_LIMIT as "raise the limits" without mentioning statistics, broadcast joins, or spill.
- Claiming Trino automatically caches query results or materializes CTEs.
- No opinion on when to prefer copying data over federation, or vice versa.

---

## Cheat card

```
TRINO (ex-PrestoSQL, renamed Dec 2020; Presto b.2012 @Facebook, OSS 2013)
ARCH    coordinator: parse/plan/optimize/schedule + memory accounting
        workers: run SPLITS (unit of work) in STAGES joined by EXCHANGES
        catalog = properties file binding CONNECTOR -> 3-part naming
MEMORY  user (hard limits, fail-fast EXCEEDED_MEMORY_LIMIT)
        revocable (spill to disk: hash agg/join/sort) · system (tracked)
        limits: query.max-memory[-per-node]; don't fight limits w/ bigger boxes
JOINS   AUTOMATIC: broadcast if est < join.broadcast-threshold (~100MB)
        else partitioned hash; underestimated broadcast = classic OOM
CTE     inlined: N refs ≈ N executions; verify in EXPLAIN
MV      CREATE/REFRESH MATERIALIZED VIEW (Hive/Iceberg/Delta), manual refresh
CACHE   no OSS result cache; Starburst/commercial adds caching+auto-refresh
FT EXEC exchange manager on S3/HDFS; worker loss = split retry not query
        restart (experimental 2023 -> production path for batch SQL)
ATHENA  serverless Trino (engine v3), ~$5/TB scanned; federation via Lambda
BIGQUERY federation narrower: BigLake ext tables, Cloud SQL/Spanner links
FEDERATION RIGHT: selective/infrequent/exploratory; WRONG: OLTP hot paths,
        point lookups, unbounded joins, cross-region compliance, txn consistency
SMALL FILES millions of splits + listing storms; fix = OPTIMIZE/compaction
DEBUG   EXPLAIN ANALYZE: predicate inside connector handle = pushdown OK
FIRST LEVER for cost/latency: partitioning + Parquet + predicate discipline
```

## Sources

- [We're rebranding PrestoSQL as Trino — trino.io](https://trino.io/blog/2020/12/27/announcing-trino.html) — accessed 2026-08-23
- [Trino 483 release notes / release history — trino.io](https://trino.io/docs/current/release.html) — accessed 2026-08-23
- [A pivotal summer (Trino 483 announcement) — trino.io](https://trino.io/blog/2026/07/18/a-pivotal-summer.html) — accessed 2026-08-23
- [PrestoDB, Presto, PrestoSQL: the fork history — Starburst](https://www.starburst.io/learn/presto-sql/) — accessed 2026-08-23

## Changelog

- 2026-08-23 — created
