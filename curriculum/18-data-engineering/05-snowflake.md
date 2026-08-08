# Snowflake: Micro-Partitions, Virtual Warehouses, Time Travel, Zero-Copy Clone

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-snowflake` · **Tags:** platform,critical

## Why this gets asked

The interviewer has watched a warehouse bill triple in a month because someone set a 4XL warehouse as the default for a dashboard nobody optimized, or a query "run slow" ticket that turned out to be a clustering key that stopped matching how the table was actually filtered two quarters ago. Snowflake's pitch — "just run SQL, we handle the infrastructure" — is true enough that engineers stop reasoning about the physical layout underneath it, and that's exactly the gap the interview probes: can you explain *why* a query is fast or slow in terms of micro-partitions and pruning, not just "it's Snowflake, it's fast."

---

## Lineage: past → present → future

**What came before.** Traditional MPP warehouses (Teradata, early Redshift) tightly coupled storage and compute: to get more query throughput you resized the same cluster that held your data, so storage and compute scaled together whether you needed both or not, and a single heavy query could starve every other workload sharing the cluster. The pain was concrete — a nightly ETL load and a live BI dashboard competing for the same fixed compute, with no isolation between them, forced teams into complex workload-management schedules or duplicate clusters holding copies of the same data.

**Where it stands now.** Snowflake (founded 2012, GA 2014) built the architecture around **separating storage and compute** from day one: data lives once in Snowflake-managed cloud storage as immutable micro-partitions, and any number of independently-sized "virtual warehouses" can query it concurrently without contending for the same compute. This is now the industry-standard architecture — Databricks SQL Warehouses and BigQuery's slot model both converge on the same separation, though each implements it differently. The live disagreement in 2026 is less about the architecture and more about **openness**: Snowflake's native storage format is proprietary, and Snowflake's answer has been to add first-class support for externally-managed Apache Iceberg tables so customers aren't locked into Snowflake's internal format for new data.

**Where it's heading.** Snowflake donated the Polaris Catalog to the Apache Software Foundation as **Apache Polaris**, which reached Top-Level Project status in February 2026, and by mid-2026 the Iceberg REST Catalog protocol it implements is a practical multi-engine standard that Spark, Trino, Flink, and DuckDB all speak [[The State of Apache Iceberg Catalogs, June 2026]](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e). Expect continued convergence toward "bring your own Iceberg tables, Snowflake is one of several engines that can read and write them" as a first-class mode, alongside the classic native-table mode that still has performance and feature advantages (time travel, clustering, zero-copy clone all currently work best or only on native tables). Treat full feature parity between Iceberg tables and native Snowflake tables as not yet real — check current docs before promising a client-facing team otherwise.

---

## Mental model

```
                     ┌─────────────────────────────────────┐
                     │         STORAGE LAYER (shared)        │
                     │   immutable micro-partitions,         │
                     │   50-500MB uncompressed each,         │
                     │   per-column min/max/null/distinct     │
                     │   metadata stored separately           │
                     └─────────────────────────────────────┘
                        ▲            ▲             ▲
                        │            │             │
              ┌─────────┴───┐ ┌──────┴──────┐ ┌────┴────────┐
              │ WAREHOUSE A  │ │ WAREHOUSE B  │ │ WAREHOUSE C  │
              │ (ETL, Large) │ │ (BI, Small)  │ │ (ad-hoc,     │
              │              │ │              │ │  auto-scale) │
              └──────────────┘ └──────────────┘ └──────────────┘
              each independently sized, billed, suspended —
              none contends with the others for compute
```

Every query against a table first consults the **metadata layer** (min/max/null-count/distinct-count per column, per micro-partition) to decide which micro-partitions can be skipped entirely — this is pruning, and it happens before a single byte of the actual data is scanned.

## How it actually works

### Micro-partitions and pruning

Snowflake automatically divides every table into **micro-partitions**: immutable, contiguous units of storage containing **50-500MB of uncompressed data** (roughly 16MB compressed) [[Snowflake docs: Micro-partitions & Data Clustering]](https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions). "Immutable" means an `UPDATE` or `DELETE` never modifies a micro-partition in place — it writes new micro-partitions with the changed rows and marks the old ones as no longer part of the current table version, which is also what makes time travel possible without a separate change log.

Each micro-partition carries per-column metadata: min, max, null count, and distinct count. A query with `WHERE order_date = '2026-07-15'` checks that metadata against every micro-partition's min/max for `order_date` and skips any partition whose range can't contain that value — this is **pruning**, and it's the single biggest lever on both query cost and latency, because Snowflake bills by warehouse-time, and a warehouse scanning less data finishes faster.

### Clustering keys

By default, micro-partitions are ordered roughly by insertion order, which means pruning is naturally effective on time-based filters (new data keeps arriving, so recent partitions cluster by date automatically) but ineffective on other predicates unless you explicitly define a **clustering key**:

```sql
ALTER TABLE orders CLUSTER BY (customer_id);
```

This tells Snowflake's background **automatic clustering** service to reorganize micro-partitions so rows with similar `customer_id` values co-locate, keeping min/max ranges tight and pruning effective for queries filtered on that column. Automatic clustering consumes compute credits in the background — it is not free, and it's only worth it when: the table is large (multi-TB+), queries consistently filter on the clustering key, and the natural insertion-order clustering doesn't already serve those queries well. Clustering a rarely-queried dimension, or one where the natural load order already aligns with query filters, burns credits for no measurable benefit.

### Virtual warehouses: sizing, scaling, and the credit model

Warehouses use T-shirt sizing where each size doubles compute (and credit consumption) versus the one below it:

| Size | Credits/hour |
|---|---|
| X-Small | 1 |
| Small | 2 |
| Medium | 4 |
| Large | 8 |
| X-Large | 16 |
| ... | ... doubling ... |
| 6X-Large | 512 |

[[Snowflake warehouse considerations docs]](https://docs.snowflake.com/en/user-guide/warehouses-considerations)

**Scale up vs. scale out** is a real distinction interviewers probe: a single slow query that's spilling to local disk or remote storage needs a *bigger* warehouse (scale up — more memory/compute per query). A queue of many small concurrent queries competing for the same warehouse needs a **multi-cluster warehouse** (scale out — more clusters of the *same* size, auto-added when queueing is detected, auto-removed when idle). Sizing up a single warehouse to fix a concurrency problem wastes money; adding clusters to fix a single-query spill problem does nothing.

**Auto-suspend** is the primary cost control: a suspended warehouse burns zero credits. Recommended defaults are roughly **60 seconds** for interactive/BI warehouses (balances avoiding cold-start latency against idle burn) and **30 seconds** for programmatic ETL/orchestrated warehouses (no human waiting on a fresh session, so minimize idle burn aggressively) [[Snowflake cost optimization guide 2026]](https://leanopstech.com/blog/snowflake-pricing-cost-optimization-2026/). A warehouse left at the default (which historically defaults higher, and some teams never touch it) can waste a meaningful fraction of total warehouse spend on pure idle time between queries.

### Caching: three layers, easy to conflate

1. **Result cache** — Snowflake-wide (not warehouse-specific), keyed on the exact SQL text and underlying data being unchanged, retained roughly 24 hours. A repeated identical query can return in milliseconds with **zero warehouse compute**, and therefore zero additional credit cost.
2. **Local disk cache (warehouse cache)** — each running warehouse caches recently-scanned micro-partitions on local SSD. Lost entirely when the warehouse suspends, which is the real tradeoff behind aggressive auto-suspend: faster suspend saves idle credits but means the next query is a cold cache.
3. **Remote storage** — the durable copy in cloud object storage; always correct, always available, but the slowest to read from directly.

### Time travel, zero-copy clone, and Fail-safe

Because micro-partitions are immutable and old versions aren't deleted immediately, Snowflake can answer `SELECT * FROM t AT (OFFSET => -3600)` or `BEFORE (STATEMENT => '...')` for any point within the table's retention window. **Standard Time Travel retention is 1 day by default**, extendable up to **90 days**, but only on **Enterprise Edition or above** [[Snowflake Time Travel docs]](https://docs.snowflake.com/en/user-guide/data-time-travel). After Time Travel expires, data enters **Fail-safe**: a fixed, non-configurable **7-day** window during which only Snowflake support (not the customer directly) can attempt recovery. With a 90-day Time Travel window, total protection extends to 97 days — but Fail-safe is explicitly a last resort, not a self-service tool, and shouldn't be relied on as part of an operational recovery plan.

**Zero-copy clone** (`CREATE TABLE t_clone CLONE t`) creates a new table that shares the same underlying micro-partitions — no data is physically copied, so cloning a 50TB table is near-instant and costs no extra storage until the clone or the source diverges (at which point only the *changed* micro-partitions incur new storage). This is why clone-based dev/test/staging environments are cheap in Snowflake in a way they aren't in most warehouses. A clone inherits the source's Time Travel and Fail-safe state at creation time, but the clone then has its own independent retention clock going forward — cloning doesn't extend or share the source's future retention.

### Streams and tasks for CDC

A **stream** on a table records an offset and, when queried, returns the delta (inserted/updated/deleted rows) since that offset was last consumed — it's Snowflake's native change-data-capture primitive, requiring no external CDC tool for in-warehouse change tracking. Stream types: **standard** (full CDC — inserts, updates, deletes), **append-only** (inserts only, cheaper to maintain, fits event/log-style source tables), and **insert-only** (for external tables). A **task** schedules SQL execution on a cron or interval basis; the common pattern is a task that checks `SYSTEM$STREAM_HAS_DATA` before running, so it's a no-op (and costs nothing) when there's nothing new to process. Chaining tasks (`AFTER` another task) builds simple DAGs without an external orchestrator for in-warehouse pipelines — though anything with cross-system dependencies still needs Airflow or equivalent.

### Snowpark and reading the query profile

**Snowpark** lets you write DataFrame-style transformations in Python/Java/Scala that compile down to SQL executed inside Snowflake's engine — the code runs where the data lives rather than pulling data out to a client process, avoiding the classic "extract everything to pandas" anti-pattern for anything beyond small result sets.

The **Query Profile** (Snowsight's query detail view) is where you diagnose real performance problems: check the percentage of **partitions scanned vs. total partitions** (low ratio = good pruning; near-100% on a filtered query = clustering or predicate problem), look for **spilling** to local disk or remote storage (a step's memory requirement exceeded what the warehouse size provides — the fix is usually a bigger warehouse, not query rewriting), and check for exploding join cardinality (a step whose output rows vastly exceed input rows, usually an unintended cross-join-like condition).

---

## Build it from scratch

Minimal pruning simulator — the mechanism an interviewer might ask you to sketch to prove you understand it below the SQL level:

```python
# untested sketch
from dataclasses import dataclass

@dataclass
class MicroPartition:
    id: str
    min_vals: dict
    max_vals: dict
    rows: list  # the actual data, only "scanned" if not pruned

def prune_and_scan(partitions: list[MicroPartition], column: str, value):
    scanned = []
    skipped = 0
    for p in partitions:
        lo, hi = p.min_vals.get(column), p.max_vals.get(column)
        if lo is not None and (value < lo or value > hi):
            skipped += 1
            continue  # pruned: metadata alone rules this partition out
        scanned.append(p)
    print(f"scanned {len(scanned)}/{len(partitions)} partitions "
          f"({skipped} pruned by metadata alone)")
    return [row for p in scanned for row in p.rows if row[column] == value]
```

The point to make out loud: pruning is a metadata-only decision made *before* any row is read, which is why a well-clustered table can answer a selective filter by touching a tiny fraction of total storage regardless of table size.

---

## How it's done in production

Snowflake is itself the managed product — there's no separate "OSS version" to compare, unlike the Postgres/pgvector pattern elsewhere in this curriculum. The relevant production question is almost always **cost governance**, since Snowflake makes it trivially easy to spin up compute with no capacity-planning friction.

| Symptom | Cause | Fix |
|---|---|---|
| Warehouse credit spend triples with no query volume change | Warehouse oversized for its workload, or auto-suspend left at a high default | Right-size via query profile spill analysis; tighten auto-suspend (60s BI / 30s ETL) |
| Query scans 95%+ of partitions despite a selective `WHERE` | Clustering key doesn't match actual filter columns, or no clustering key defined | Check query profile's partitions-scanned ratio; redefine clustering key to match real filters |
| Concurrent BI queries queueing during peak hours | Single-cluster warehouse hit its concurrency ceiling | Convert to multi-cluster warehouse with auto-scale (scale out, not up) |
| Query suddenly spills to remote storage, huge latency spike | Warehouse memory insufficient for the query's working set (large join/sort) | Scale up warehouse size for that workload, or reduce intermediate result size |
| `TIME TRAVEL` query fails past a few days | Standard Edition (max 1 day Time Travel) or retention window already exceeded | Confirm edition supports required retention (90 days needs Enterprise+); adjust `DATA_RETENTION_TIME_IN_DAYS` |
| Dev/test environment costs balloon | Teams manually copying full tables instead of using zero-copy clone | Standardize on `CREATE ... CLONE` for dev/test/staging provisioning |
| Automatic clustering credit line item unexpectedly large | Clustering key defined on a column that doesn't match query patterns, or too high-cardinality/volatile | Audit clustering key against actual `WHERE`/`JOIN` predicates in query history; drop unused keys |

---

## Tradeoffs & when NOT to use it

- **Snowflake is usually the wrong choice for heavy ML/feature-engineering workloads and unstructured data pipelines.** It's a SQL-first warehouse; Snowpark narrows the gap for Python transformations, but it doesn't have the native GPU training, MLflow-equivalent lifecycle tooling, or Spark-scale unstructured processing that Databricks does. Bolting a real ML platform on top of Snowflake is possible but not its strength.
- **Do not treat automatic clustering as free.** It's background compute billed like any other credit consumption; clustering a column that doesn't match real query patterns is pure cost with no benefit.
- **Do not rely on Fail-safe as disaster recovery.** It is a non-configurable, support-mediated last resort, not a self-service restore path — operational recovery planning should assume Time Travel is the only self-service window you have.
- **Standard Edition's 1-day Time Travel is often a real operational gap** — teams frequently discover they need multi-day recovery only after an incident, at which point upgrading to Enterprise is a procurement delay, not a five-minute fix.
- **Small, low-concurrency workloads with predictable, low data volume overpay for the flexibility.** The separation of storage and compute is most valuable when you actually have varying concurrency and workload types to isolate from each other; a single small team running one modest nightly job doesn't need multi-cluster auto-scaling warehouses to justify the platform's pricing complexity.
- **Native Snowflake tables and externally-managed Iceberg tables inside Snowflake are not fully at feature parity as of 2026** — check current docs before assuming zero-copy clone, Time Travel, and clustering all behave identically on Iceberg tables.

---

## Interview questions

### Q1 — What is a micro-partition and how does pruning actually work?
**Testing:** baseline — whether you know the mechanism, not just the term.
**Answer:** An immutable, contiguous storage unit holding 50-500MB of uncompressed data, created automatically as data loads. Snowflake stores per-column min, max, null-count, and distinct-count metadata for every micro-partition. A query's `WHERE` predicate is checked against that metadata before scanning any actual data; any micro-partition whose min/max range can't satisfy the predicate is skipped entirely (pruned).
**Follow-up trap:** *"Does pruning require an index?"* — no, and that's the point: there's no user-managed index to build or maintain. Pruning effectiveness instead depends on how well the physical ordering of rows across micro-partitions matches your query's filter columns — which is exactly what clustering keys control.

### Q2 — When do you actually need a clustering key, and when is it a waste of money?
**Answer:** Worth it when the table is large (multi-TB+), a specific column is consistently used in `WHERE`/`JOIN` predicates, and the natural insertion-order clustering doesn't already align with that column (e.g., filtering by `customer_id` on a table naturally ordered by `load_timestamp`). It's a waste when the table is small enough that full scans are already cheap, when queries don't consistently filter on one column, or when the natural load order already produces good pruning (most time-series tables filtered by date need no explicit key).
**Follow-up trap:** *"You add a clustering key and the bill goes up but queries aren't faster. Why?"* — automatic clustering is itself background compute; if the key doesn't match real query predicates, or the data pattern makes maintaining that clustering expensive (high write volume constantly reshuffling), you pay the maintenance cost without the pruning benefit. Check the query profile's partitions-scanned ratio to confirm clustering is actually helping before keeping it.

### Q3 — Scale up or scale out — how do you decide, and what's the failure mode of picking wrong?
**Answer:** Scale up (bigger warehouse size) fixes a single query that's slow because it's memory-constrained — spilling to local disk or remote storage. Scale out (multi-cluster, more clusters of the same size) fixes queueing caused by too many concurrent queries competing for one warehouse. Picking wrong: sizing up to fix concurrency wastes money on a bigger warehouse that still serializes queries one at a time per cluster; relying on multi-cluster to fix one slow query does nothing, because more clusters just mean more parallel *copies* of the same undersized compute, not more memory for any single query.
**Follow-up trap:** *"How do you tell which one you're facing from the query profile alone?"* — spilling shown in the profile (bytes spilled to local/remote storage) points to scale up; queueing time shown in the warehouse load monitoring (not the individual query profile) points to scale out. Conflating "my query in the profile looks fine but is slow to start" with a compute-size problem is the trap — that's usually a queueing/concurrency signal instead.

### Q4 — Explain the three caching layers and what breaks if you set auto-suspend too aggressively.
**Answer:** Result cache is Snowflake-account-wide, keyed on exact SQL text plus unchanged underlying data, retained roughly 24 hours, costs zero compute on hit. Local disk (warehouse) cache holds recently-scanned micro-partitions on the running warehouse's SSD, and is lost entirely when the warehouse suspends. Remote storage is the durable source of truth, always correct but slowest. Setting auto-suspend very aggressively (e.g., a few seconds) maximizes idle-credit savings but means nearly every query after any pause is a cold local-disk cache, trading credit savings for consistently higher per-query latency.
**Follow-up trap:** *"Does lowering auto-suspend ever increase total cost?"* — indirectly, yes: if a warehouse suspends and resumes constantly for a bursty workload, you pay resume/warm-up overhead repeatedly and lose local cache benefit each time, which can push queries to scan remote storage more often — not a direct credit line item, but a real latency and sometimes indirect cost.

### Q5 — How is zero-copy clone actually implemented, and why doesn't cloning a 50TB table cost 50TB of extra storage?
**Answer:** The clone is a new table pointing at the same underlying immutable micro-partitions as the source — nothing is physically copied. Storage cost only appears once the clone or the source diverges, and even then only for the newly-written micro-partitions, not the whole table. This works precisely because micro-partitions are immutable: a shared reference is safe since neither side can silently overwrite what the other reads.
**Follow-up trap:** *"Does the clone share the source's future Time Travel window?"* — no. It inherits the source's Time Travel/Fail-safe state at the moment of cloning, but from that point on the clone has its own independent retention clock — a clone made today doesn't get to "see" changes the source makes tomorrow via the source's own Time Travel.

### Q6 — Standard vs Enterprise Edition — what's the real-world impact of Time Travel being capped at 1 day on Standard?
**Answer:** Standard Edition defaults to and caps at 1-day Time Travel; extending to up to 90 days requires Enterprise Edition or above. In practice this means a Standard-tier customer discovers a bad load or accidental delete has to be caught within roughly a day, or the only remaining recourse is Fail-safe — a 7-day, support-mediated, non-self-service window, not a quick fix. Teams frequently learn this the hard way during an actual incident rather than planning for it upfront.
**Follow-up trap:** *"Can you just always set retention to 90 days to be safe?"* — it requires Enterprise+ licensing (a real cost and procurement decision, not a config toggle), and longer retention means more storage held for unchanged/superseded micro-partitions, which has a real ongoing storage cost — it's a deliberate tradeoff, not a free safety net.

### Q7 — Streams and tasks vs. a dedicated CDC tool (Debezium, Fivetran) — when is the native approach the wrong call?
**Answer:** Streams/tasks are the right call for in-warehouse change propagation — building a silver/gold layer from a raw table entirely inside Snowflake, with no external moving parts, cron-based or event-checked via `SYSTEM$STREAM_HAS_DATA`. They're the wrong call when the source of truth is an external OLTP database and you need low-latency, log-based capture from that source system into Snowflake in the first place — that's an ingestion problem streams don't solve; you still need Debezium/Fivetran/native connectors to get the data into Snowflake before a stream can track further changes on it.
**Follow-up trap:** *"Your task keeps running even when the stream is empty. What's wrong and what does it cost?"* — the task isn't checking `SYSTEM$STREAM_HAS_DATA` before running its body, so it burns a full warehouse resume/query cycle on every scheduled interval regardless of whether there's anything to process — real, avoidable credit cost from a missing guard clause.

### Q8 — Walk me through reading a query profile that shows high remote-storage spilling.
**Answer:** Spilling to remote storage means an operator (usually a large sort, hash join, or aggregation) needed more working memory than the warehouse's local memory and even local disk could provide, so intermediate results spilled all the way to cloud storage — the slowest tier. This is a strong signal the warehouse is undersized for that specific query's working set, not a query-logic bug per se. The fix is almost always scaling up (bigger warehouse) for that workload, or reducing the size of the intermediate result (filter earlier, reduce join fan-out) if resizing isn't an option.
**Follow-up trap:** *"Would a clustering key fix this?"* — not directly. Clustering improves pruning (how much data is scanned in the first place); spilling happens after data is already read, during in-memory processing. They address different stages of the query, and conflating them is a common interview mistake.

### Q9 — Design the warehouse topology for a company with nightly ETL, a live BI dashboard used by 200 analysts, and occasional data-science ad-hoc queries.
**Testing:** systems judgment across cost and isolation.
**Answer:** Three separate warehouses, minimum: an ETL warehouse (Jobs-style, sized to the heaviest transform, aggressive 30s auto-suspend since nothing waits on it interactively), a BI warehouse (multi-cluster with auto-scale for the 200-analyst concurrency, 60s auto-suspend to balance cold-start latency against idle cost), and an ad-hoc/data-science warehouse (separately sized and billed so a runaway exploratory query doesn't degrade the BI dashboard's SLA). Isolating by workload type is the whole point of the separated storage/compute architecture — sharing one warehouse across all three defeats it.
**Follow-up trap:** *"The BI warehouse's cost is dominated by idle time, not query time. Multi-cluster auto-scale won't fix that — what will?"* — auto-scale adds/removes *clusters* based on queueing, it doesn't address a single cluster idling between queries; that's purely an auto-suspend tuning problem, and the two levers (auto-scale for concurrency, auto-suspend for idle cost) are independent and often conflated.

### Q10 — What does Snowpark actually change about how you'd architect a Python-heavy transformation pipeline compared to pulling data out to pandas?
**Answer:** Snowpark compiles DataFrame-style Python operations down into SQL executed inside Snowflake's own engine, so the data never leaves Snowflake's storage/compute boundary — no network transfer of the full dataset to a client process, no separate compute cluster to manage, and the transformation benefits from the same pruning and warehouse elasticity as any SQL query. Pulling data into pandas is fine for genuinely small results but doesn't scale, and re-introduces a whole separate compute environment (a Python process, its memory limits, its own scaling story) that Snowpark avoids.
**Follow-up trap:** *"So Snowpark eliminates the need to ever export data?"* — no, some workloads (real ML training loops needing GPU frameworks, arbitrary Python library dependencies with native extensions) still need to leave Snowflake; Snowpark narrows that gap for transformation-style work but doesn't replace a full ML training stack.

### Q11 — A finance stakeholder asks why the Snowflake bill tripled this month with no new use cases. What's your diagnostic sequence?
**Answer:** Start with `ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY` to find which warehouse's credit consumption actually grew. Then check whether it's driven by more query volume, longer-running queries (check query profile spilling — undersized warehouse), more idle time (auto-suspend regression or a change in usage pattern extending idle windows), or a new clustering key/automatic clustering job consuming background credits. This is a diagnostic funnel, not a single query — quoting one root cause without ruling out the others is the weak answer.
**Follow-up trap:** *"You find it's automatic clustering. Do you just drop the clustering key?"* — only after confirming the key isn't actually serving a real, high-value query pattern; dropping it blind might fix the bill but silently regress a dashboard's query latency that nobody connected to the clustering key in the first place.

---

## Red flags that fail you

- Describing pruning as requiring a manually-built index.
- Recommending a bigger warehouse to fix a queueing/concurrency problem (that's scale-out, not scale-up).
- Treating Fail-safe as a self-service backup/restore mechanism.
- Not knowing Time Travel beyond 1 day requires Enterprise Edition or above.
- Claiming zero-copy clone has no eventual storage cost under any circumstance.
- Recommending automatic clustering without checking it against actual query filter patterns.
- Confusing the result cache (account-wide, ~24h, SQL-text-keyed) with the local warehouse disk cache (lost on suspend).

---

## Cheat card

```
MICRO-PARTITIONS   immutable, 50-500MB uncompressed (~16MB compressed)
                    per-column metadata: min, max, null count, distinct count
                    pruning = metadata-only skip decision, BEFORE any data is scanned

CLUSTERING          worth it: large table + consistent filter column + poor natural order
                    NOT worth it: small table, unpredictable filters, already well-ordered
                    automatic clustering = background compute, billed, not free

WAREHOUSES          T-shirt sizing, doubles credits/hr each size: XS=1 ... 6XL=512
                    scale UP  = fix one slow/spilling query (more memory/compute)
                    scale OUT = fix queueing from concurrent queries (multi-cluster)
                    auto-suspend: ~60s BI/interactive, ~30s programmatic ETL

CACHING             result cache: account-wide, ~24h, exact-SQL-keyed, zero compute on hit
                    local disk cache: per-warehouse, LOST on suspend
                    remote storage: durable, always correct, slowest

TIME TRAVEL         Standard: 1 day default/cap · Enterprise+: up to 90 days
                    Fail-safe: fixed 7 days, non-configurable, support-mediated only
                    max total protection: up to 97 days (90 TT + 7 fail-safe)

ZERO-COPY CLONE     shares source's micro-partitions, no copy cost until divergence
                    clone gets its OWN retention clock going forward, not shared with source

STREAMS & TASKS     stream = offset + delta since last read (standard/append-only/insert-only)
                    task = scheduled SQL; guard with SYSTEM$STREAM_HAS_DATA to avoid empty runs

PRICING             credits: Standard ~$2 · Enterprise ~$3 · Business Critical ~$4 (AWS US East, on-demand)
                    capacity contracts: 20-45% discount depending on volume/term

QUERY PROFILE       low partitions-scanned % = good pruning
                    spilling to local/remote = undersized warehouse for that query's memory need
                    exploding row counts mid-query = unintended join fan-out
```

## Sources

- [Micro-partitions & Data Clustering — Snowflake docs](https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions) — accessed 2026-08-01
- [Warehouse considerations — Snowflake docs](https://docs.snowflake.com/en/user-guide/warehouses-considerations) — accessed 2026-08-01
- [Multi-cluster warehouses — Snowflake docs](https://docs.snowflake.com/en/user-guide/warehouses-multicluster) — accessed 2026-08-01
- [Understanding & using Time Travel — Snowflake docs](https://docs.snowflake.com/en/user-guide/data-time-travel) — accessed 2026-08-01
- [Snowflake Time Travel & Fail-safe — Snowflake docs](https://docs.snowflake.com/en/user-guide/data-availability) — accessed 2026-08-01
- [Introduction to streams and tasks — Snowflake docs](https://docs.snowflake.com/en/user-guide/data-pipelines-intro) — accessed 2026-08-01
- [2026 Snowflake Pricing Guide — Revefi](https://www.revefi.com/blog/snowflake-pricing-guide) — accessed 2026-08-01
- [Snowflake Cost Optimization: The Complete 2026 Guide — LeanOps](https://leanopstech.com/blog/snowflake-pricing-cost-optimization-2026/) — accessed 2026-08-01
- [The State of Apache Iceberg Catalogs in June 2026 — dev.to](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Snowflake separates storage and compute so any number of independently-sized virtual warehouses can query the same data without contending for resources, and it hides physical layout behind immutable, automatically-created micro-partitions (50-500MB uncompressed) that carry per-column min/max/null/distinct metadata for pruning-before-scanning. Time travel and zero-copy clone both fall out of that immutability for free: old micro-partition versions stick around until retention expires, so you can query the past or clone a 50TB table instantly with no physical copy. The two things that actually cost money if you get them wrong are warehouse sizing (scale up for a slow single query, scale out for concurrent queueing, and don't confuse the two) and clustering keys (background compute that only pays for itself if it matches real query predicates). It's the wrong tool for heavy ML/unstructured-data workloads — that's Databricks' strength, not Snowflake's.
