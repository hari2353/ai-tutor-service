# Databricks: Delta Lake, Unity Catalog, Photon, DLT, Workflows

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-databricks` · **Tags:** platform,critical

## Why this gets asked

Every Databricks interviewer has been paged for one of three things: a `VACUUM` that silently broke a downstream time-travel job, a cluster that cost 4x what finance expected because someone ran an ad-hoc notebook on All-Purpose Compute instead of a job, or a Z-ORDER job that took two hours to rewrite a table nobody actually queries by that key anymore. They're not testing whether you know Delta Lake has ACID transactions — everyone says that. They're testing whether you understand *why* an object store, which has no cross-file transaction primitive, can support ACID at all, and what breaks when the abstraction leaks.

---

## Lineage: past → present → future

**What came before.** Hadoop-era data lakes were directories of Parquet/ORC files on HDFS or S3 with no transaction boundary: a job writing 500 files could crash after 300, leaving readers with a half-written, inconsistent view, and there was no way to delete or update a record without rewriting entire partitions by hand. The Hive Metastore tracked partition locations but not file-level consistency. The pain that killed this was concrete: analysts got double-counted revenue from partially-written jobs, GDPR "right to be forgotten" deletes required full-partition rewrites, and nobody could reproduce "what did this table look like last Tuesday" for a bad model retrain. Databricks open-sourced Delta Lake in 2019 specifically to bolt ACID semantics onto Parquet-on-object-storage without requiring a new file format.

**Where it stands now.** Delta Lake, Unity Catalog, Photon, and Lakeflow (formerly Delta Live Tables) form Databricks' vertically integrated lakehouse stack, and as of October 2025 Databricks retired the Standard pricing tier on AWS and GCP entirely — Premium (which includes Unity Catalog, serverless compute, and RBAC) is now the floor for new workspaces [[Databricks pricing guide 2026]](https://www.flexera.com/blog/finops/databricks-pricing-guide/). The live disagreement is about lock-in: Delta's storage format is technically open (Parquet + JSON transaction log), but for years the *catalog* — Unity Catalog — was Databricks-proprietary, which is where the real dependency lived even after the file format stopped being one. Liquid clustering has functionally replaced Z-ORDER as the recommended default for new tables in 2026, because Z-ORDER's full-rewrite cost made it expensive to maintain on continuously-growing tables.

**Where it's heading.** Databricks open-sourced Unity Catalog's core (April 2024) and has since positioned it as an interoperable Iceberg REST catalog, not just a Databricks-only governance plane — by mid-2026 Unity Catalog implements the server side of the Iceberg REST Catalog protocol alongside Glue and Snowflake's Polaris/Open Catalog [[The State of Apache Iceberg Catalogs, June 2026]](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e). Delta UniForm (metadata generated automatically in Iceberg and Hudi formats alongside Delta, at write time, no extra storage cost) is the concrete bet that the storage-format war is over and the catalog is the new battleground. Treat "which catalog wins" as unresolved; treat "Delta the file format will keep mattering in isolation from a catalog" as increasingly unlikely.

---

## Mental model

```
 Write path                                   Read path
 ──────────                                   ─────────
 writer reads latest version N            reader lists _delta_log/, finds
      │                                    latest checkpoint + subsequent JSONs
      ▼                                         │
 writes new Parquet data files                  ▼
 (not yet visible to anyone)                reconstructs the file manifest
      │                                     for version N by replaying actions
      ▼                                         │
 writes 000...00N+1.json                        ▼
 (atomic rename / put-if-absent)            reads only the Parquet files
      │                                     listed as "add" and not "removed"
      ▼
 commit succeeds → table is now at N+1,
 atomically, for every reader
```

The trick: Delta never needs a distributed lock on the data files themselves. It needs exactly one atomic operation — "create this JSON file if it doesn't already exist" — which S3 (conditional PUT, GA since 2023), ADLS, and GCS all provide natively. Everything else (which files are live, what the schema was, what stats each file has) is derived by replaying that log.

## How it actually works

### The transaction log and optimistic concurrency

Every Delta table is a directory of Parquet files plus a `_delta_log/` directory of numbered JSON commit files (checkpointed to Parquet every 10 commits by default). Each commit is a set of **actions**: `add` (a new file, with column-level min/max stats), `remove` (a file that's logically gone but not necessarily physically deleted yet), `metaData` (schema), `protocol` (reader/writer version).

Writers use **optimistic concurrency control**: read the current version, stage new data files, then attempt to commit by writing the next-numbered log entry. If another writer already claimed that log entry, the commit fails and Delta checks whether the two writers' file sets actually conflict (e.g., two `INSERT`s to disjoint files can both succeed; two `UPDATE`s touching the same file cannot) before retrying. This is why Delta scales better than a table-level lock under concurrent writers, and why isolation is **not** full serializability by default — it's closer to snapshot isolation, and write-write conflicts on the same files still fail one side.

```python
# untested sketch — the read/write/validate/commit cycle Delta implements internally
def commit(table_path, version, actions):
    log_path = f"{table_path}/_delta_log/{version:020d}.json"
    try:
        atomic_create_if_absent(log_path, actions)   # S3 conditional PUT
    except AlreadyExistsError:
        current = read_actions(f"{table_path}/_delta_log/{version:020d}.json")
        if conflicts(current, actions):
            raise ConcurrentModificationException()
        return commit(table_path, version + 1, actions)   # retry at next version
```

### Time travel and the VACUUM retention trap

Because `remove` actions don't immediately delete the underlying Parquet file, you can query any prior version: `SELECT * FROM t VERSION AS OF 12` or `TIMESTAMP AS OF '2026-07-01'`. Two table properties govern this:

- `delta.logRetentionDuration` — default **30 days**. How long the JSON commit history itself is kept.
- `delta.deletedFileRetentionDuration` — default **7 days**. How long a "removed" Parquet file is kept on disk before `VACUUM` is allowed to delete it.

**The trap:** these two defaults don't match. A table advertises 30 days of log history, but the default `VACUUM` (no arguments) deletes any removed file older than 7 days. Run `VACUUM` on a schedule with defaults and `VERSION AS OF` for anything older than a week starts throwing `FileNotFoundException` even though the log entry for that version still exists — the log remembers the version happened, but the data files it pointed to are gone. Symptom in the field: a data scientist's reproducibility notebook that worked last month now fails with "file not found" on a path that looks legitimate. Fix: either raise `deletedFileRetentionDuration` to match your time-travel SLA, or never run `VACUUM RETAIN 0 HOURS` (which Databricks blocks by default via `spark.databricks.delta.retentionDurationCheck.enabled`, precisely because someone will eventually try it during an incident and destroy their own recovery window).

### OPTIMIZE, Z-ORDER, and liquid clustering

`OPTIMIZE table_name` compacts small files into larger ones (bin-packing, target ~1GB files) — necessary because streaming/micro-batch writes and per-partition inserts otherwise produce thousands of small files that kill read throughput (each file is a separate object-store GET with its own latency).

`ZORDER BY (col)` additionally co-locates rows with similar values in that column across files, so min/max-based data skipping is effective. The problem: Z-ORDER is a full rewrite of the touched files every time you run it, so on a continuously-growing table you're re-clustering data that was already well-clustered last week.

**Liquid clustering** (`CLUSTER BY (col)`, GA as the default recommendation for new tables in 2026) replaces both partitioning and Z-ORDER: it's incremental — `OPTIMIZE` only touches files that actually need reclustering — and clustering keys can be changed without a full table rewrite. It also handles skewed cardinality better than Hive-style partitioning, which produces pathologically many tiny partitions on high-cardinality keys.

### Unity Catalog

Three-level namespace: `catalog.schema.table` (previously two-level `database.table` under the legacy Hive Metastore). One **metastore** per region typically, attached to a cloud account; catalogs live inside it. This gives you a real access-control boundary above the schema level — you can grant a whole catalog to a business unit — which the legacy Hive Metastore never had.

Unity Catalog automatically captures **lineage** at the column level for anything run through Databricks SQL, notebooks, or Lakeflow pipelines — no manual instrumentation — and extends governance to models, feature tables, and volumes (unstructured file governance), not just tables. Row-level and column-level security are enforced via row filters and column masks defined once in the catalog rather than per-query.

### Photon

Photon is a vectorized execution engine written in native C++ that replaces JVM-based Spark SQL execution for supported operators (scans, joins, aggregations, writes) — it does **not** replace the JVM driver or the Spark scheduler, just the row-processing hot path, and it processes data in columnar batches rather than row-at-a-time. Databricks reports up to **12x** improvement on TPC-DS-style workloads versus a naive Spark configuration [[What is Photon — Databricks docs]](https://docs.databricks.com/aws/en/compute/photon). It does **not** help UDF-heavy Python/Scala workloads (a Python UDF still round-trips through the JVM/Python boundary Photon can't vectorize), and the gain on already-well-tuned Spark SQL is smaller than the headline number implies — treat "up to 12x" as a ceiling, not a typical case.

### Lakeflow Declarative Pipelines (formerly Delta Live Tables)

DLT was rebranded to **Lakeflow Declarative Pipelines** in 2025; existing DLT code runs unmodified. You declare tables and the transformations between them (SQL or Python `@dlt.table`), and the engine handles orchestration, incremental processing, and retries. **Expectations** are row-level data-quality constraints:

```python
# untested sketch
@dlt.table
@dlt.expect_or_drop("valid_amount", "amount > 0")
@dlt.expect("recent_event", "event_ts > current_date() - INTERVAL 7 DAYS")
def silver_orders():
    return dlt.read_stream("bronze_orders").select(...)
```

`expect` logs violations but keeps the row; `expect_or_drop` silently drops violators; `expect_or_fail` halts the pipeline. As of 2026 expectations can be stored centrally as Unity Catalog objects rather than hardcoded per-pipeline, and can be attached to standalone materialized views via `CONSTRAINT ... EXPECT (...)` without a full pipeline definition [[Lakeflow release notes 2026]](https://docs.databricks.com/aws/en/release-notes/dlt/2026). The known limitation: expectations are row-scoped — they can't natively express "this table's row count shouldn't drop by more than 20% day over day," which needs a separate data-quality tool (Great Expectations, or a custom check task).

### Workflows and the medallion pattern

Databricks Workflows orchestrates multi-task jobs (notebooks, SQL, DLT pipelines, JARs) with dependencies, retries, and alerting, comparable to Airflow but scoped to the Databricks workspace. The medallion architecture — **bronze** (raw, as-ingested, append-only), **silver** (cleaned, deduplicated, conformed schema), **gold** (business-level aggregates ready for BI) — is Databricks' opinionated framing of what is otherwise a standard staged-refinement pattern; the interesting engineering is less the three names and more that each layer is a real, queryable Delta table with its own lineage, not an ETL black box.

### Cluster types and cost model

| Compute type | Use case | Relative cost |
|---|---|---|
| All-Purpose | Interactive notebooks, ad-hoc exploration | Highest DBU rate (~$0.55/DBU Premium) |
| Jobs Compute | Scheduled/automated pipelines | 40-60% cheaper per DBU than All-Purpose |
| SQL Warehouses | BI/SQL queries, can be serverless | Serverless SQL up to ~$0.70/DBU but zero idle cost |
| Serverless (jobs/notebooks) | Fully managed, no cluster config | ~$0.08/DBU for model serving up to higher rates elsewhere |

Total cost = DBU-rate × DBU/hour × hours, **plus** the underlying cloud VM cost — DBU pricing does not include EC2/VM charges, which is the "second bill" most teams forget when estimating [[Databricks pricing guide 2026]](https://www.flexera.com/blog/finops/databricks-pricing-guide/). The single highest-leverage cost lever most teams ignore: moving a production pipeline from an interactive All-Purpose cluster (because someone "just tested it there") to a scheduled Jobs Compute cluster typically cuts 40-60% of that pipeline's compute cost with zero code change.

---

## Build it from scratch

A minimal single-writer transaction log, enough to demonstrate the mechanism an interviewer might ask you to sketch on a whiteboard:

```python
# untested sketch
import json, os, glob

class MiniDeltaTable:
    def __init__(self, path):
        self.path = path
        os.makedirs(f"{path}/_delta_log", exist_ok=True)

    def _log_files(self):
        return sorted(glob.glob(f"{self.path}/_delta_log/*.json"))

    def current_version(self):
        files = self._log_files()
        return len(files) - 1 if files else -1

    def read_active_files(self):
        """Replay the log: files added minus files removed, up to current version."""
        active = set()
        for f in self._log_files():
            for action in json.load(open(f)):
                if action["type"] == "add":
                    active.add(action["path"])
                elif action["type"] == "remove":
                    active.discard(action["path"])
        return active

    def commit(self, actions):
        next_version = self.current_version() + 1
        target = f"{self.path}/_delta_log/{next_version:020d}.json"
        if os.path.exists(target):                       # someone else committed first
            raise ConcurrentModificationException()
        tmp = target + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(actions, fh)
        os.rename(tmp, target)                            # atomic on POSIX, analogous
                                                            # to S3 conditional PUT
        return next_version

class ConcurrentModificationException(Exception): ...
```

This deliberately omits stats-based pruning, checkpointing, and the retry-on-conflict loop — enough to show you understand that the *log*, not the data files, is the source of truth, and that atomicity of one small JSON write is the whole trick.

---

## How it's done in production

Databricks itself is "production" here — there's no separate reference implementation to compare against, which is unusual for this catalogue. The relevant comparison is Delta Lake (the OSS format, usable outside Databricks via `delta-rs`/Spark) versus the full Databricks platform (Photon, Unity Catalog, Lakeflow, Workflows), and increasingly Delta Lake versus Iceberg as the underlying format regardless of platform (see the lakehouse module).

| Symptom | Cause | Fix |
|---|---|---|
| `TIMESTAMP AS OF` / `VERSION AS OF` query fails with file-not-found | `VACUUM` ran with default 7-day retention while log retention promised 30 days | Raise `delta.deletedFileRetentionDuration` to match your time-travel SLA before running scheduled VACUUM |
| Small-file explosion, read latency climbs over weeks | Streaming/micro-batch writes producing many small files, no compaction | Enable liquid clustering + predictive optimization, or schedule `OPTIMIZE` |
| `ConcurrentAppendException` / `ConcurrentDeleteReadException` | Two writers touched overlapping files under optimistic concurrency | Reduce write concurrency on the same partitions, or restructure to append-only where possible |
| Query 10x slower than expected on a Z-ORDERed table | Data has grown since the last Z-ORDER; new files aren't clustered | Migrate to liquid clustering (incremental) instead of re-running full Z-ORDER on schedule |
| Monthly bill spikes with no code change | Ad-hoc notebooks running on interactive All-Purpose clusters left idle/attached | Enforce cluster policies restricting notebook use to job/pool clusters; auto-termination on idle |
| DLT/Lakeflow pipeline silently drops rows | `expect_or_drop` on a constraint that started failing after an upstream schema change | Monitor expectation metrics (Databricks emits pass/fail counts per expectation); alert on drop-rate change |
| Photon enabled, no speedup observed | Workload is dominated by Python/Scala UDFs Photon can't vectorize | Rewrite hot-path logic as native SQL/DataFrame expressions; reserve UDFs for logic that truly needs them |

---

## Tradeoffs & when NOT to use it

- **Databricks is the wrong choice for a pure BI/SQL shop with no ML/Spark workload.** You are paying for a Spark-and-ML-oriented platform's operational surface (clusters, Photon, MLflow) to run what is fundamentally a warehouse workload; Snowflake or BigQuery will usually be cheaper and require less tuning for that case.
- **Small teams without dedicated platform engineering underuse it.** Cluster policies, pool sizing, DBU-vs-VM cost accounting, and choosing the right compute type per workload are real operational burdens; a team that just runs everything on a default All-Purpose cluster will overpay by multiples.
- **Liquid clustering and Z-ORDER both assume you know your query patterns in advance.** If your table is queried by unpredictable ad-hoc predicates, clustering keys buy you little and you're paying compaction cost for marginal benefit.
- **Time travel is not a backup strategy.** It's bounded by retention windows you control and can be defeated by your own `VACUUM` schedule; use it for "what changed since yesterday" debugging, not disaster recovery.
- **DLT/Lakeflow expectations are not a substitute for a real data-contract/data-quality framework** if you need cross-row or cross-table checks (referential integrity, volume anomalies) — they're row-scoped by design.

---

## Interview questions

### Q1 — How does Delta Lake get ACID transactions on top of an object store that has no cross-file transaction API?
**Testing:** whether you understand the mechanism versus reciting "ACID on Parquet."
**Answer:** It doesn't need a transaction across files — it needs exactly one atomic primitive: "create this next-numbered JSON log file if it doesn't already exist." S3 conditional PUT, ADLS, and GCS all support this natively. The log is the source of truth for which Parquet files are logically part of the table at any version; readers reconstruct state by replaying `add`/`remove` actions, writers commit by atomically claiming the next log entry.
**Follow-up trap:** *"What isolation level does that actually give you?"* — not full serializability. It's closer to snapshot isolation: two writers touching disjoint files both succeed, but two writers touching the same file conflict and one must retry or fail. Claiming "full ACID like a relational database" without that caveat is a tell.

### Q2 — Walk me through what happens when you run `VACUUM` on a table someone is time-traveling against.
**Testing:** the retention-trap failure mode, a real production incident pattern.
**Answer:** `delta.logRetentionDuration` defaults to 30 days (how long log history is kept) but `delta.deletedFileRetentionDuration` defaults to 7 days (how long removed data files survive on disk). Default `VACUUM` deletes files older than 7 days regardless of the log's 30-day memory. A `VERSION AS OF` query for day 20 will find the log entry but get `FileNotFoundException` on the underlying Parquet file.
**Follow-up trap:** *"Why doesn't Databricks just default both to the same value?"* — because VACUUM's retention floor exists to protect *concurrent readers*, not historical queries: a long-running query might still be reading files from a version a writer just superseded, and 7 days is a safety margin against that, not a promise about time-travel depth. Conflating the two is the actual interview trap.

### Q3 — Z-ORDER vs liquid clustering — what's actually different?
**Testing:** whether "just use liquid clustering, it's better" is understood or memorized.
**Answer:** Z-ORDER is a full rewrite of every touched file each time you run it, so re-clustering a continuously growing table means repeatedly reprocessing data that hasn't changed. Liquid clustering is incremental — `OPTIMIZE` only processes files that need it — handles high-cardinality/skewed keys better than Hive-style partitioning, and lets you change the clustering key without rewriting the whole table.
**Follow-up trap:** *"So would you migrate every existing Z-ORDERed table today?"* — for most new tables, yes; but a large, rarely-rewritten table that's already well Z-ORDERed and stable gets little from migrating, and migration itself costs a rewrite. The senior answer is "for new tables, default to liquid clustering; migrate existing ones opportunistically, not as a blanket project."

### Q4 — What's the actual difference between `expect`, `expect_or_drop`, and `expect_or_fail` in Lakeflow/DLT, and what can't expectations express?
**Testing:** production data-quality judgment, not API trivia.
**Answer:** `expect` logs violations and keeps the row (visibility without blocking), `expect_or_drop` silently removes violating rows, `expect_or_fail` halts the pipeline. They're all row-scoped constraints evaluated per record. They cannot express cross-row invariants — "row count shouldn't drop >20% day over day," referential integrity against another table — which needs a separate check, often a data-quality tool or a custom validation task in the DAG.
**Follow-up trap:** *"Your `expect_or_drop` pipeline has been silently dropping 15% of rows for two weeks. How did that happen and how do you catch it faster?"* — an upstream schema or semantic change started violating the constraint, and `expect_or_drop` by design fails silently from the pipeline's perspective. The fix is monitoring the expectation's pass/fail metrics (Databricks emits these) with an alert on drop-rate change, not just on pipeline failure.

### Q5 — When would you turn Photon off, or not pay for it?
**Testing:** whether "Photon = always turn it on" is a reflex or a judgment.
**Answer:** Photon accelerates the vectorizable hot path (scans, joins, aggregations, writes) but doesn't help workloads dominated by Python/Scala UDFs, since those still cross the JVM/Python boundary Photon can't vectorize. On a workload that's mostly UDF logic, you're paying Photon's premium DBU rate for a part of the pipeline it barely touches.
**Follow-up trap:** *"The vendor benchmark says 12x. Why would you see less?"* — the 12x figure is against a naive/default Spark configuration on TPC-DS-style queries; a workload already tuned with proper partitioning, caching, and broadcast joins has a smaller JVM baseline to beat, so the realistic gain is meaningfully lower. Quoting the ceiling as the expectation is the mistake.

### Q6 — Explain Unity Catalog's namespace model and what it actually buys you over the legacy Hive Metastore.
**Answer:** Three-level namespace, `catalog.schema.table`, versus the legacy two-level `database.table`. The catalog level gives you a real access-control boundary above schema — you can grant an entire catalog to a business unit or environment (dev/prod as separate catalogs) — which Hive Metastore never had. It also unifies governance across tables, views, volumes (unstructured files), functions, and ML models under one permission model, with automatic column-level lineage captured with no manual instrumentation.
**Follow-up trap:** *"Does Unity Catalog eliminate Databricks lock-in since Delta is an open format?"* — no, historically the opposite: the file format being open didn't matter much when the catalog enforcing access and lineage was Databricks-only. That's exactly why Databricks open-sourced Unity Catalog's core and added Iceberg REST Catalog server support — acknowledging the catalog, not the file format, was the real lock-in point.

### Q7 — A team disables autovacuum-equivalent maintenance (`OPTIMIZE`/predictive optimization) to avoid disrupting a nightly batch window. What breaks?
**Answer:** Small files accumulate from every micro-batch or partition-level write, and read latency on that table degrades over weeks as query engines pay per-file object-store GET overhead across thousands of tiny files instead of hundreds of well-sized ones. Nothing fails outright — it's silent, gradual degradation, which is why it's dangerous: nobody notices until a dashboard SLA is already blown.
**Follow-up trap:** *"How would you detect this before a user complains?"* — track file count and average file size per table over time (available via `DESCRIBE DETAIL`), and alert on average file size dropping below a threshold (well under Databricks' ~1GB compaction target), rather than waiting for a query-latency complaint.

### Q8 — Design the cluster strategy for a team running 20 scheduled ETL jobs and 30 analysts doing ad-hoc SQL.
**Testing:** cost-model literacy, not just feature knowledge.
**Answer:** ETL jobs go on Jobs Compute (40-60% cheaper per DBU than All-Purpose, auto-terminates), ideally on job clusters or a shared pool to amortize startup latency. Analysts go on SQL Warehouses, likely serverless to avoid idle cost during off-hours, sized by concurrency (multi-cluster SQL Warehouse) rather than a single oversized warehouse. Nobody runs production ETL on an interactive All-Purpose cluster left attached to a notebook — that's the single most common source of unexplained cost.
**Follow-up trap:** *"Finance says the bill doubled and nobody changed any code. Where do you look first?"* — DBU cost is separate from the underlying cloud VM cost; check both, but the fastest lever is usually an interactive cluster someone forgot to auto-terminate, or a notebook that got promoted to "production" without ever being migrated off All-Purpose Compute.

### Q9 — Your `OPTIMIZE ZORDER BY (customer_id)` job takes two hours every night and query performance hasn't improved in months. Diagnose it.
**Answer:** Most likely the actual query predicates have drifted away from `customer_id` — maybe queries are now filtering on `event_date` or a different dimension — so the clustering investment isn't matching read patterns anymore. Check query history / the query profile for the actual filter columns being used, not the ones you assumed. Separately, if the table has grown, Z-ORDER is re-rewriting already-clustered data every run, which is pure waste; that alone argues for migrating to liquid clustering, which only touches files that need reclustering.
**Follow-up trap:** *"You migrate to liquid clustering. Does the nightly maintenance cost drop to zero?"* — no, it drops to the incremental cost of clustering only new/changed data, which is not zero, just proportional to what actually changed rather than the whole table.

### Q10 — Design the resilience/governance story for a Unity Catalog deployment shared by three business units with different compliance requirements.
**Testing:** whether governance is understood as an architecture decision, not a checkbox.
**Answer:** Separate catalogs per business unit (or per environment within a unit) as the top-level isolation boundary, since catalog-level grants are the coarsest and most auditable control. Row-level security via row filters and column masks for PII fields shared across units but restricted by role, defined once at the catalog/schema level rather than duplicated per query. Lineage is automatic, so audit trail for "who touched this column and what fed it" doesn't need separate instrumentation — but it does need someone to actually review it, since capturing lineage and acting on lineage are different maturity levels.
**Follow-up trap:** *"One business unit wants to use their own separate metastore for data residency reasons. Can they?"* — a metastore is typically bound to a region/cloud account; if genuine data-residency separation is required, that's a real architectural constraint, not a permissions setting, and it affects whether cross-unit lineage and sharing (Delta Sharing) can span the boundary at all.

### Q11 — What does the medallion architecture (bronze/silver/gold) actually buy you that a single well-modeled warehouse table wouldn't?
**Answer:** Each layer is independently queryable and independently recoverable: if silver has a bug, you can rebuild it from bronze without re-ingesting from source, since bronze is the durable, as-ingested record. It also separates concerns — schema conformance and dedup logic live in the bronze-to-silver transform, business logic lives in silver-to-gold — so a change to a business rule doesn't require touching ingestion code.
**Follow-up trap:** *"Isn't this just staging tables with a marketing name?"* — largely yes, and saying so is a stronger signal than pretending it's novel. The genuine engineering value is that each stage is a real, ACID, queryable Delta table with lineage, not an opaque intermediate the ETL tool owns — that's a Databricks-specific implementation detail worth naming, not the staging pattern itself.

---

## Red flags that fail you

- Describing Delta as requiring a distributed lock across data files (it doesn't — one atomic log-file write is the whole mechanism).
- Claiming full serializable isolation with no caveat about write-write conflicts on overlapping files.
- Recommending Z-ORDER as the default for new tables in 2026 without mentioning liquid clustering.
- Not knowing that `VACUUM`'s default retention (7 days) and the log's default retention (30 days) don't match, and that this breaks time travel.
- Saying Photon "makes everything faster" with no mention of UDF-heavy workloads being unaffected.
- Treating Delta's open file format as proof there's no Databricks lock-in, with no mention of the catalog.
- Recommending All-Purpose Compute for production scheduled jobs.

---

## Cheat card

```
DELTA LOG      _delta_log/*.json actions: add/remove/metaData/protocol
               atomicity = one conditional-PUT-style file create, not a distributed lock
               isolation ≈ snapshot isolation, not full serializable (overlapping writes conflict)

RETENTION      logRetentionDuration            default 30 days (log history)
               deletedFileRetentionDuration    default 7 days  (data files) ← VACUUM trap
               time travel breaks past 7d unless you raise deletedFileRetentionDuration

CLUSTERING     OPTIMIZE = bin-pack small files, target ~1GB
               ZORDER BY = full rewrite every run, co-locates by value for skipping
               liquid clustering (CLUSTER BY) = incremental, 2026 default, no full rewrite

UNITY CATALOG  catalog.schema.table (3-level, vs legacy 2-level Hive Metastore)
               auto column-level lineage, row filters + column masks, governs models/volumes too
               2026: implements Iceberg REST Catalog server side (Glue/Polaris interop)

PHOTON         native vectorized C++ engine, replaces JVM execution for scans/joins/agg/writes
               up to 12x TPC-DS vs naive Spark — NOT for UDF-heavy workloads

LAKEFLOW/DLT   expect (log) / expect_or_drop (silent drop) / expect_or_fail (halt)
               row-scoped only — no cross-row/referential checks

COST           All-Purpose ~$0.55/DBU Premium (highest) · Jobs Compute 40-60% cheaper
               Serverless SQL up to ~$0.70/DBU · model serving ~$0.08/DBU
               DBU cost is SEPARATE from underlying cloud VM cost — the "second bill"
               Premium is now the pricing floor (Standard retired AWS/GCP, Oct 2025)
```

## Sources

- [Understanding Delta Lake's Optimistic Concurrency Control](https://docs.delta.io/concurrency-control/) — accessed 2026-08-01
- [What are ACID guarantees on Databricks? — Databricks docs](https://docs.databricks.com/aws/en/lakehouse/acid) — accessed 2026-08-01
- [What is Unity Catalog? — Databricks docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) — accessed 2026-08-01
- [What is Photon? — Databricks docs](https://docs.databricks.com/aws/en/compute/photon) — accessed 2026-08-01
- [Lakeflow Spark Declarative Pipelines release notes 2026 — Databricks docs](https://docs.databricks.com/aws/en/release-notes/dlt/2026) — accessed 2026-08-01
- [Liquid Clustering vs Z-Ordering — Databricks Community](https://community.databricks.com/t5/data-engineering/liquid-clustering-vs-z-ordering/td-p/157984) — accessed 2026-08-01
- [Predictive optimization for Unity Catalog managed tables — Databricks docs](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) — accessed 2026-08-01
- [Databricks pricing guide 2026 — Flexera](https://www.flexera.com/blog/finops/databricks-pricing-guide/) — accessed 2026-08-01
- [The State of Apache Iceberg Catalogs in June 2026 — dev.to](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Delta Lake gets ACID on an object store with no cross-file transaction primitive by needing only one: atomically creating the next numbered JSON commit file in `_delta_log/`. Readers replay that log to know which Parquet files are live; writers use optimistic concurrency, so disjoint writes both succeed and overlapping ones conflict — it's snapshot isolation, not full serializability. Time travel rides on that same log, but the default `VACUUM` retention (7 days) is shorter than the default log retention (30 days), which is the single most common way teams accidentally break their own reproducibility. Layer Unity Catalog for governance and lineage, Photon for vectorized execution on the SQL/DataFrame hot path (not UDFs), and Lakeflow for declarative pipelines with row-level expectations, and you have the platform — but it's the wrong platform for a shop that's pure BI/SQL with no ML or Spark workload, where Snowflake or BigQuery cost less and need less tuning.
