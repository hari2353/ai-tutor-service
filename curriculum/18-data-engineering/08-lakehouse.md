# Lakehouse: Iceberg vs Delta vs Hudi, Table Formats, Catalog Evolution

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-lakehouse` · **Tags:** architecture

## Why this gets asked

Because "just use Iceberg, it won" is a slogan, not an architecture decision, and the interviewer wants to know if you understand *what problem table formats solve* well enough to pick correctly when the workload doesn't match the slogan — heavy upsert/CDC ingestion, for instance, where Hudi's merge-on-read still has real advantages. They've also probably lived through a small-files incident: a streaming job writing thousands of tiny Parquet files a day until Spark jobs spent more time opening files than reading data, and want to know you'd see it coming.

---

## Lineage: past → present → future

**What came before.** A "data lake" was originally just files — Parquet or ORC — sitting in HDFS or S3, tracked by the Hive Metastore, which recorded partition-to-location mappings but had no concept of a transaction. Writing an update meant rewriting whole partitions; a job crashing mid-write left readers looking at a half-complete, inconsistent set of files with no way to know it; schema changes required careful, manual coordination across every reader; and there was no way to ask "what did this table look like yesterday" without your own separate snapshotting discipline. The concrete pain that killed this approach: nightly batch jobs that silently double-counted data on partial failures, and analysts who couldn't reproduce a number from last week's report because the underlying files had already been overwritten.

**Where it stands now.** Three table formats solved this by adding a metadata layer on top of plain files that provides atomicity, schema evolution, and time travel without changing the underlying file format (still Parquet/Avro/ORC): **Apache Iceberg** (Netflix, 2018), **Delta Lake** (Databricks, 2019, open-sourced), and **Apache Hudi** (Uber, 2016, the earliest of the three, built specifically for upsert-heavy CDC ingestion). By 2026 the practical consensus favors Iceberg for broadest multi-engine support and vendor-neutral governance — Spark, Flink, Trino, Snowflake, BigQuery, and DuckDB all read/write it natively — while Delta remains strongest inside Databricks-centric shops and Hudi retains a real edge for pure streaming/CDC-heavy ingestion where merge-on-read's write-amplification advantage matters most [[Apache Iceberg vs Delta Lake vs Apache Hudi 2026]](https://risingwave.com/blog/apache-iceberg-vs-delta-lake-vs-hudi-2026/). The live disagreement is less "which format is best" (Iceberg has real momentum) and more "does the catalog underneath it matter more than the format choice" — which is where 2026's real architecture conversation has moved.

**Where it's heading.** The **REST Catalog** protocol (standardized as part of the Iceberg project) is emerging as the neutral interchange layer: by mid-2026, Spark, Trino, Flink, and DuckDB all implement the REST Catalog client, and Snowflake's Open Catalog (hosted Apache Polaris), AWS Glue's REST endpoint, and Databricks Unity Catalog all implement the server side [[The State of Apache Iceberg Catalogs, June 2026]](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e). Apache Polaris itself graduated to an Apache Software Foundation Top-Level Project in February 2026. Delta UniForm (auto-generating Iceberg and Hudi-compatible metadata from a Delta table, no extra storage) is a concrete bet that format wars are ending and catalog interoperability is what remains contested. Treat the claim "all three formats and catalogs are now fully interoperable" as speculative — feature parity for the *format-and-catalog combination* (native-table-only features like fine clustering or specific time-travel depth) still lags the marketing.

---

## Mental model

```
        WITHOUT a table format                  WITH a table format (Iceberg/Delta/Hudi)

  ┌─────────────────────┐                  ┌───────────────────────────────┐
  │  raw Parquet files    │                  │   METADATA LAYER               │
  │  in S3, tracked only  │                  │  (manifests / transaction log  │
  │  by Hive partition    │   ──────────▶   │   / timeline) — tracks which    │
  │  path convention       │                  │   files are live, schema,      │
  │                        │                  │   stats, history               │
  │  no atomicity           │                  ├───────────────────────────────┤
  │  no schema evolution   │                  │   underlying files (still      │
  │  no time travel         │                  │   Parquet/Avro/ORC — unchanged)│
  │  partial-write risk    │                  └───────────────────────────────┘
  └─────────────────────┘                  atomic commits, schema evolution,
                                             time travel — all metadata-layer
                                             tricks, no new file format needed
```

The three formats differ mainly in *how that metadata layer is structured* — a manifest tree (Iceberg), a JSON transaction log (Delta), or a timeline directory (Hudi) — not in what problem they solve.

## How it actually works

### Metadata architecture, side by side

- **Iceberg**: hierarchical — a `metadata.json` file points to a **manifest list**, which points to **manifest files**, each tracking a set of data files along with column-level statistics. Reading the table means walking this tree; the manifest structure is what enables Iceberg's more sophisticated partition-pruning without scanning every file's stats individually.
- **Delta Lake**: a sequential, append-only **transaction log** (`_delta_log/*.json`, checkpointed to Parquet periodically) of `add`/`remove`/`metaData` actions — see the Databricks module for the full mechanism. Simpler structurally, but less flexible for some multi-engine scenarios historically, though this is changing with REST Catalog support.
- **Hudi**: a **timeline** directory recording every instant (commit, compaction, cleaning) as a discrete event, organized by timestamp and operation type — closer to an event log of table operations than a manifest tree or linear commit log.

### Partition evolution: Iceberg's differentiator

Hive-style partitioning (used by Delta by default) bakes the partition scheme into the physical directory layout (`/year=2026/month=07/`), so changing the partitioning scheme later requires rewriting the entire table. **Iceberg's hidden partitioning** decouples the logical partition transform from physical layout: partition values are computed from a source column via a transform function (e.g., `bucket(16, user_id)`, `month(event_ts)`) and tracked in metadata rather than baked into paths, so you can change partitioning going forward without rewriting historical data, and queries don't need to know the physical partition transform to filter correctly (Iceberg applies the transform to the query predicate automatically). This is the single most cited "Iceberg wins here" feature in current comparisons.

### Copy-on-write vs. merge-on-read

This is Hudi's defining axis, though Iceberg (v2 spec, via deletion vectors/delete files) and Delta (via deletion vectors) both now support a version of the same tradeoff:

- **Copy-on-write (CoW)**: an update/delete rewrites the entire affected data file(s) immediately. Reads are fast (no merge step at query time) but writes are expensive, especially for small, frequent updates touching large files.
- **Merge-on-read (MoR)**: an update/delete is recorded as a small delta/log file referencing the base file; the base file isn't rewritten immediately. Writes are cheap and fast — critical for high-frequency CDC ingestion — but reads must merge the base file with any pending delta files at query time, adding read-time cost until a compaction job merges deltas back into the base files.

Hudi explicitly offers both as first-class table types you choose per table; this is why Hudi retains a real edge for CDC-heavy ingestion pipelines where write latency matters more than every single read being maximally fast — the tradeoff is native and well-tuned rather than a bolted-on feature.

### Catalogs: where the lock-in actually lives now

The catalog is the component that answers "what tables exist, and where is their current metadata pointer" — a level above the table-format metadata layer itself. The evolution:

**Hive Metastore** (original, still widely deployed) → **AWS Glue Data Catalog** (managed Hive Metastore-compatible service, but works only over S3-compatible storage it controls, which is itself a lock-in vector) → **Unity Catalog** (Databricks, historically Databricks-only, now open-sourcing its core and implementing the Iceberg REST Catalog server-side) → **Apache Polaris / REST Catalog** (vendor-neutral, ASF Top-Level Project as of February 2026, implements the standardized REST protocol that Spark, Trino, Flink, and DuckDB all speak natively as clients).

Why the catalog, not the format, is now the real lock-in point: even with an open file format like Iceberg, if only one vendor's catalog can serve as the *source of truth* for which snapshot is current, switching engines means either migrating the catalog or losing multi-engine write consistency. A REST-standardized catalog breaks that dependency — any compliant engine can read and write against it — which is exactly why every major vendor has converged on implementing the REST Catalog server side rather than competing on file format anymore.

### Small-file problem and compaction

Every table format inherits the same underlying physical reality: **object storage performs badly on many small files** — each file is a separate network round-trip (GET/LIST), and metadata catalogs (Hive Metastore, Glue) degrade as file counts climb, since metadata operations (partition listing, stats gathering) get slower and, for managed catalogs charging per-object, more expensive. Streaming ingestion makes this continuous rather than a one-time cleanup: every micro-batch commit can produce new small files, so **compaction has to be budgeted as an ongoing operational cost from day one**, not treated as occasional maintenance. The standard fix across all three formats is the same: a background job (Iceberg's `rewrite_data_files` procedure, Delta's `OPTIMIZE`/liquid clustering, Hudi's built-in compaction service) reads many small files and rewrites them into fewer, larger ones — typically targeting a few hundred MB to ~1GB per file — plus periodic cleanup of orphaned files and expired snapshots that would otherwise accumulate storage cost indefinitely.

### Engine support and where each genuinely wins

| Format | Strongest engine support | Genuine sweet spot |
|---|---|---|
| **Iceberg** | Spark, Flink, Trino, Snowflake, BigQuery (BigLake), DuckDB — broadest of the three | Multi-engine environments, long-term architectural flexibility, partition-scheme changes over table lifetime |
| **Delta Lake** | Databricks (best-in-class), Spark generally; growing elsewhere via UniForm | Databricks-centric shops wanting the tightest integration with Unity Catalog, Photon, liquid clustering |
| **Hudi** | Spark, Flink, Presto/Trino; historically strongest CDC/streaming tooling | High-frequency upsert/CDC ingestion where merge-on-read's write-latency advantage matters more than read-time simplicity |

---

## Build it from scratch

A minimal illustration of the copy-on-write vs. merge-on-read tradeoff, the concept most likely to be asked as a whiteboard exercise:

```python
# untested sketch
class CopyOnWriteTable:
    def __init__(self):
        self.files = {}  # file_id -> list of rows

    def update(self, file_id, row_id, new_value):
        # rewrite the ENTIRE file immediately
        rows = self.files[file_id]
        self.files[file_id] = [
            (rid, new_value) if rid == row_id else (rid, v) for rid, v in rows
        ]
        # read cost: zero extra work, always reads the current file directly

class MergeOnReadTable:
    def __init__(self):
        self.base_files = {}     # file_id -> list of rows (rarely rewritten)
        self.delta_logs = {}     # file_id -> list of (row_id, new_value) pending merges

    def update(self, file_id, row_id, new_value):
        # cheap: append to a small delta log, don't touch the base file
        self.delta_logs.setdefault(file_id, []).append((row_id, new_value))

    def read(self, file_id):
        # expensive at read time: merge base + all pending deltas
        base = dict(self.base_files[file_id])
        for row_id, new_value in self.delta_logs.get(file_id, []):
            base[row_id] = new_value          # last write wins
        return list(base.items())

    def compact(self, file_id):
        # periodic background job: fold deltas back into the base file
        self.base_files[file_id] = self.read(file_id)
        self.delta_logs[file_id] = []
```

The point to make explicit: MoR defers cost from write-time to read-time (until compaction reclaims it), and the choice is a genuine latency tradeoff, not a strictly-better-or-worse decision.

---

## How it's done in production

There's no single "reference implementation" to compare against here — the honest production question is which format-plus-catalog combination to standardize on, and how compaction/maintenance gets operationalized.

| Symptom | Cause | Fix |
|---|---|---|
| Query latency degrades gradually over weeks on a streaming-fed table | Small-file accumulation from continuous micro-batch commits | Schedule regular compaction (`rewrite_data_files`, `OPTIMIZE`, or Hudi's compaction service); consider MoR-with-scheduled-compaction if writes are frequent |
| Glue/Hive Metastore partition listing calls start timing out | Excessive file/partition count bloating catalog metadata | Compact files; consider Iceberg's hidden partitioning to reduce partition explosion from over-granular manual partitioning schemes |
| Two engines reading the "same" table see different data | Catalog not shared, or not REST-standardized — one engine's writes aren't visible to a catalog the other engine reads from | Standardize on a REST Catalog implementation both engines actually speak; verify current interop rather than assuming |
| Reads on a Hudi MoR table are slower than expected | Compaction hasn't run recently; too many pending delta log files being merged at read time | Trigger/schedule compaction more frequently, or reconsider CoW if reads dominate over writes for that table |
| Storage cost grows even though the "live" data size looks stable | Expired snapshots and orphaned files (from rewrites/compactions) not being cleaned up | Schedule snapshot expiry and orphan-file removal (`expire_snapshots`, `VACUUM`, Hudi's cleaner service) alongside compaction |
| Partition-scheme change requires a full table rewrite | Table uses Hive-style physical partitioning (Delta default) rather than Iceberg's hidden partitioning | For new tables expecting partition scheme changes over their lifetime, prefer Iceberg; for existing Delta tables, a rewrite may genuinely be unavoidable |

---

## Tradeoffs & when NOT to use it

- **Don't adopt a table format for a small, static, rarely-queried dataset.** The metadata-layer overhead (manifest management, catalog registration, compaction scheduling) is pure operational cost with no payoff if the data barely changes and query volume is low — plain partitioned Parquet with no table format is still a legitimate choice at small scale.
- **Don't default to Hudi if your workload is append-heavy analytics rather than upsert-heavy CDC.** Its strongest advantages are specifically about write-amplification under frequent updates; an append-only event log gets little extra benefit from Hudi's merge-on-read machinery over Iceberg or Delta.
- **Don't assume full interoperability across formats/catalogs without checking current docs.** Delta UniForm, Iceberg REST Catalog adoption, and cross-engine feature parity are all real but incomplete as of 2026 — native-table-only features (fine-grained clustering, certain time-travel depths) commonly don't transfer cleanly to a cross-format read path.
- **Don't skip compaction planning until it's a problem.** Every one of these formats degrades the same way under small-file accumulation; budgeting compaction as a first-class, ongoing operational cost from the start is cheaper than firefighting a latency regression that crept in over months.
- **Don't pick a format/catalog combination purely on "most popular" without checking your actual engine mix.** If your stack is Databricks end-to-end, Delta's tighter integration with Unity Catalog and Photon can outweigh Iceberg's broader-but-generic multi-engine support; the "Iceberg won" narrative is directionally true but not universally the right call for every stack.

---

## Interview questions

### Q1 — What problem does a table format actually solve that raw Parquet-on-S3 doesn't?
**Testing:** whether the fundamentals are understood, not just brand names.
**Answer:** Atomicity (a writer's changes become visible all-at-once or not at all, never partially), schema evolution without full rewrites, and time travel — none of which raw files tracked only by a Hive-style partition-path convention can provide, since there's no metadata layer recording what changed, when, or what the table's schema was at any prior point.
**Follow-up trap:** *"Does this require a new file format?"* — no, and that's the key insight: all three (Iceberg, Delta, Hudi) still store data in Parquet/Avro/ORC; the innovation is entirely in the metadata layer sitting on top, not in how bytes are physically encoded.

### Q2 — Iceberg's hidden partitioning — what does it actually solve, mechanically?
**Answer:** Hive-style partitioning bakes the partition scheme into physical file paths, so changing it later requires a full rewrite. Iceberg tracks partition values as a transform function (e.g., `bucket(16, user_id)`, `month(ts)`) applied to a source column, recorded in metadata rather than baked into directory structure — you can add or change partition transforms going forward without touching historical data, and queries filtering on the source column get the transform applied automatically without needing to know the physical layout.
**Follow-up trap:** *"So can you re-partition years of historical data for free with this?"* — no — hidden partitioning lets new data use a new partition scheme without rewriting old data, but it doesn't retroactively re-optimize old files' physical layout; historical data keeps whatever partition scheme was active when it was written unless you explicitly rewrite it.

### Q3 — Copy-on-write vs. merge-on-read — when would you deliberately choose CoW even though MoR has cheaper writes?
**Answer:** When reads dominate over writes and read latency is the thing users actually feel — a BI dashboard queried constantly by many users cares more about consistently fast reads than about shaving milliseconds off an infrequent update. MoR defers cost to read time (merging deltas), which is the wrong tradeoff when reads vastly outnumber writes.
**Follow-up trap:** *"Your CDC pipeline uses CoW and write latency is now the bottleneck under high update volume. What do you do?"* — either switch that table to MoR (Hudi natively, or Delta/Iceberg's deletion-vector mechanism as a partial equivalent) to defer the rewrite cost, or reduce the frequency of full-file rewrites by batching updates before committing, accepting slightly staler visibility in exchange for lower write amplification.

### Q4 — Why has the "catalog" become the more interesting lock-in conversation than "table format" in 2026?
**Answer:** All three table formats are now genuinely open (Parquet/Avro/ORC underneath, with published metadata specs), so the format itself is decreasingly a vendor-specific dependency. But the catalog is what answers "which snapshot is current" for any engine trying to read or write — if only one vendor's catalog can serve as that source of truth, switching engines means migrating the catalog, which is a much bigger undertaking than switching a file format reader. The REST Catalog standardization effort exists specifically to remove that dependency.
**Follow-up trap:** *"Does using Apache Polaris or a REST Catalog fully solve lock-in then?"* — it solves *catalog-protocol* lock-in (any REST-compliant engine can talk to it), but doesn't automatically guarantee every engine gets identical performance or feature access against tables in that catalog — native-table-only optimizations in a given engine can still create a softer form of lock-in even with an open catalog underneath.

### Q5 — Design the compaction strategy for a table receiving continuous streaming writes at high frequency.
**Answer:** Budget compaction as an always-on background process, not periodic maintenance — schedule it frequently enough that small-file count and pending-delta-log volume never grow unbounded between runs. Pair it with snapshot-expiry/orphan-file cleanup on its own schedule, since compaction itself produces new files and marks old ones obsolete, and without expiry those obsolete files silently accumulate storage cost. Size target files in the low hundreds of MB to ~1GB range, matched to the query engine's optimal scan size.
**Follow-up trap:** *"Compaction is now competing for compute resources with the streaming ingestion job itself. How do you prioritize?"* — this is a genuine resource contention problem with no free answer: either isolate compaction onto separate compute (its own cluster/warehouse/reservation) so it doesn't starve ingestion, or accept a compaction lag SLA and monitor small-file count as a leading indicator rather than waiting for query latency complaints to reveal the backlog.

### Q6 — A team wants to change their partitioning scheme on an existing multi-year Delta table. What's actually involved, and how would Iceberg have avoided this?
**Answer:** Delta's Hive-style partitioning is baked into physical layout, so changing it means rewriting the entire historical dataset into the new partition structure — a genuinely expensive, often multi-day operation on large tables, with a real risk window during the migration. Iceberg's hidden partitioning would have let the team change the partition transform going forward with zero rewrite of historical data, since partition values are metadata-computed rather than physically encoded in paths.
**Follow-up trap:** *"Does this mean you should always pick Iceberg over Delta specifically for this reason?"* — not automatically; if the team is deeply invested in Databricks-specific tooling (Unity Catalog governance, Photon acceleration, liquid clustering) that outweighs this one scenario's cost, staying on Delta and accepting a one-time rewrite may still be the better overall tradeoff than migrating the whole platform to gain partition evolution.

### Q7 — What's the actual difference between Iceberg's manifest-tree metadata and Delta's transaction log, and does it matter in practice?
**Answer:** Iceberg's `metadata.json` → manifest list → manifest files hierarchy lets query planning consult column-level stats at the manifest level without opening every individual data file's footer, and supports efficient metadata operations (like partition evolution) that a flat sequential log handles less naturally. Delta's JSON transaction log is simpler and easier to reason about directly, but historically required more work to expose the same level of multi-engine metadata access that Iceberg's spec was designed for from the start. In practice, both work well at moderate scale; the difference shows up more at very large table sizes (many thousands of files) and in how cleanly each format's spec maps onto third-party engines that aren't the format's primary sponsor.
**Follow-up trap:** *"So is Delta's simpler log a disadvantage?"* — not inherently; simplicity has real operational value (easier to debug, easier to reason about by hand), and Delta's checkpointing (periodic Parquet snapshots of the log) mitigates the "replay a long log" cost. The tradeoff is more about ecosystem breadth than raw architectural superiority.

### Q8 — Explain why Hudi is described as having "the strongest CDC story" among the three, mechanically.
**Answer:** Hudi was built from the outset (Uber, 2016) specifically for upsert-heavy, high-frequency CDC ingestion, and its merge-on-read table type is a first-class, well-tuned feature rather than a bolted-on addition — writes append small delta/log files instead of rewriting base files, minimizing write amplification exactly where CDC workloads generate the most pressure (many small, frequent updates arriving continuously from a source database's change stream). Its built-in compaction service is designed around this same workload pattern from day one.
**Follow-up trap:** *"Delta and Iceberg both now have deletion vectors, which is a similar idea. Does that close the gap?"* — it narrows it, but deletion vectors in Delta/Iceberg were added later as an incremental feature on top of a copy-on-write-first design, whereas Hudi's read/write path was architected around the MoR tradeoff from the beginning — for extremely high-frequency CDC, the maturity and tuning of Hudi's native implementation can still have a real edge, though this gap is narrowing and should be re-verified for the specific workload rather than assumed.

### Q9 — Your Iceberg table's manifest files have grown huge and query planning itself is now slow, before any data is even scanned. Diagnose.
**Answer:** This usually means manifests haven't been rewritten/consolidated after a long history of many small commits, each adding its own manifest entries — query planning has to read an increasingly large manifest list/tree just to figure out which data files are relevant, which is itself now a bottleneck independent of the underlying data volume. The fix is Iceberg's manifest rewrite procedure (`rewrite_manifests`), analogous to data-file compaction but for the metadata layer itself.
**Follow-up trap:** *"Isn't this the same problem as small data files? Why does it need a separate fix?"* — related but distinct: data-file compaction (`rewrite_data_files`) addresses the actual data being scanned; manifest rewriting addresses the metadata *about* those files, which can bloat independently, especially on tables with many small, frequent commits even if the resulting data files themselves are reasonably sized.

### Q10 — When would you recommend NOT adopting any table format at all?
**Answer:** A small, rarely-updated, single-engine dataset with low query volume doesn't need the operational overhead of manifest management, catalog registration, and compaction scheduling — plain partitioned Parquet files with simple Hive-style discovery are a legitimate, lower-complexity choice at that scale. The table-format investment pays off specifically when you need multi-engine consistency, frequent schema evolution, time travel, or upsert-heavy ingestion — none of which are automatic requirements just because a dataset exists.
**Follow-up trap:** *"The team says 'we might need multi-engine access someday, so let's adopt Iceberg now just in case.'* Response?" — push back gently: adopting a table format preemptively for a hypothetical future need adds real, current operational cost (someone has to own compaction, catalog choice, and metadata hygiene) for a benefit that may never materialize; it's a legitimate choice if the "someday" is reasonably near-term and specific, not a free hedge against an unspecified future.

---

## Red flags that fail you

- Saying a table format is a new file format rather than a metadata layer over existing formats.
- Recommending Iceberg or Delta with no mention of Hudi's genuine CDC/upsert advantage.
- Claiming full cross-format/cross-catalog interoperability with no caveat about native-feature parity gaps.
- Not knowing the difference between copy-on-write and merge-on-read, or claiming one is strictly better.
- Treating the catalog choice as an afterthought after the format decision, rather than recognizing it as the primary 2026 lock-in question.
- Not budgeting compaction as an ongoing cost for streaming-fed tables.
- Confusing manifest/metadata bloat with data-file small-file bloat as though they're the same problem with the same fix.

---

## Cheat card

```
PROBLEM SOLVED   atomicity + schema evolution + time travel over immutable files on
                 object storage — NOT a new file format, a metadata layer on Parquet/Avro/ORC

METADATA LAYOUT  Iceberg: metadata.json → manifest list → manifest files (hierarchical)
                 Delta:   sequential _delta_log/*.json, checkpointed periodically
                 Hudi:    timeline directory of instants (commit/compaction/clean)

PARTITION EVO    Iceberg: hidden partitioning — transform-based, metadata-only, no rewrite
                 Delta:   Hive-style physical partitioning by default — rewrite to change
                 (both Iceberg and Delta now also support partition evolution to some degree
                  via metadata; Iceberg's is the most mature/native)

COW vs MOR       CoW: rewrite whole file on update — fast reads, expensive frequent writes
                 MoR: append small delta log — cheap writes, read-time merge cost until compact
                 Hudi: both first-class, purpose-built for CDC-heavy MoR
                 Iceberg/Delta: deletion vectors = a later-added, narrower version of the idea

ENGINE SUPPORT   Iceberg: broadest (Spark/Flink/Trino/Snowflake/BigQuery/DuckDB)
                 Delta:   best inside Databricks; growing elsewhere via UniForm
                 Hudi:    Spark/Flink/Trino; strongest native CDC/streaming tooling

CATALOG EVOLUTION Hive Metastore → Glue (managed, S3-only) → Unity Catalog (was
                 Databricks-only, now open + Iceberg REST server) → Apache Polaris/
                 REST Catalog (ASF top-level project, Feb 2026 — the neutral standard)
                 CATALOG is the real 2026 lock-in point, not the file format

SMALL FILES      object storage penalizes many small files (per-file GET/LIST overhead,
                 catalog metadata bloat) — compaction must be an ONGOING cost for
                 streaming-fed tables, not occasional maintenance
                 also watch MANIFEST bloat (metadata about files) as a separate axis

WRONG CHOICE IF  small/static/single-engine dataset → skip table formats entirely
                 append-only analytics workload → Hudi's MoR advantage barely matters
                 assuming full interop across formats/catalogs without checking current docs
```

## Sources

- [Apache Iceberg vs Delta Lake vs Apache Hudi (2026) — RisingWave](https://risingwave.com/blog/apache-iceberg-vs-delta-lake-vs-hudi-2026/) — accessed 2026-08-01
- [Apache Iceberg vs Delta Lake vs Apache Hudi - Feature Comparison Deep Dive — Onehouse](https://www.onehouse.ai/blog/apache-hudi-vs-delta-lake-vs-apache-iceberg-lakehouse-feature-comparison) — accessed 2026-08-01
- [Apache Polaris — polaris.apache.org](https://polaris.apache.org/) — accessed 2026-08-01
- [The State of Apache Iceberg Catalogs in June 2026 — dev.to](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e) — accessed 2026-08-01
- [Iceberg Catalog Showdown: Apache Polaris vs Unity Catalog — Estuary](https://estuary.dev/blog/iceberg-catalog-apache-polaris-vs-unity-catalog/) — accessed 2026-08-01
- [HOW TO: Use Delta UniForm to unify different open table formats (2026) — Flexera](https://www.flexera.com/blog/finops/delta-uniform/) — accessed 2026-08-01
- [Data Lake Architecture in 2026: Iceberg on S3, Real-Time Ingestion, and Federated Catalogs — BigDataBoutique](https://bigdataboutique.com/blog/data-lake-architecture-2026) — accessed 2026-08-01
- [Hive Metastore - Did We Replace It With A Vendor Lock? — lakeFS](https://lakefs.io/blog/hive-metastore-vendor-lock/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Table formats solve exactly one problem: atomicity, schema evolution, and time travel over immutable files on object storage, which raw Parquet-plus-Hive-Metastore never had — and they do it entirely in a metadata layer, without inventing a new file format. Iceberg has the broadest engine support and the cleanest partition-evolution story via hidden partitioning; Delta wins inside Databricks-centric stacks; Hudi keeps a genuine edge for upsert-heavy CDC ingestion because merge-on-read was its founding design goal, not a bolted-on feature. The catalog, not the file format, is the real 2026 lock-in question — Hive Metastore gave way to Glue, which gave way to Unity Catalog, which is now converging with Apache Polaris around a standardized REST Catalog protocol every major engine is adopting. None of this eliminates the small-file problem, which every format inherits from object storage itself and which has to be budgeted as continuous compaction cost on any streaming-fed table, not a one-time cleanup.
