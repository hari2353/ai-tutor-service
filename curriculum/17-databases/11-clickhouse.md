# ClickHouse: MergeTree, Parts, Sparse Index, Why It's Fast

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-clickhouse` · **Tags:** olap

## The 30-second version

ClickHouse gets its speed from four compounding decisions: columnar storage (a scan only reads the columns a query touches), a sparse primary index that maps one entry per 8,192-row granule instead of every row (so the index for a billion-row table fits in memory), aggressive compression on sorted columnar data (adjacent values in the same column are similar, so codecs like LZ4/ZSTD and delta/gorilla encoding hit high ratios), and vectorized execution (operators process whole batches of values through SIMD instructions instead of one row at a time). The `ORDER BY` clause on a MergeTree table is the single decision that determines most of your query performance, because it's both the physical sort order on disk and the sparse index — get it wrong and every query scans granules it didn't need to. The two failure modes that actually page people: **"too many parts"** (frequent small inserts create more parts than background merges can absorb, and ClickHouse refuses further inserts past a hard part-count ceiling to protect itself) and **OOM on GROUP BY/JOIN/ORDER BY** (these are the only operations that must hold state proportional to something other than the bytes scanned — a wide, high-cardinality GROUP BY's hash table, or the right-hand side of a JOIN, can exceed `max_memory_usage` and kill the query, or without a per-query cap, the whole server). ClickHouse is the wrong choice the moment you need point updates, row-level transactions, or high-concurrency OLTP with many small single-row writes — it was never designed for that shape of workload and will make you pay for pretending otherwise.

## Why this gets asked

The interviewer wants to know if you've operated ClickHouse under real load, not just run `SELECT count()` on a demo dataset. Two production events are almost always behind this question: an ingestion pipeline that started throwing `Too many parts` because someone switched from batched to per-row inserts, and a dashboard query that OOM-killed the ClickHouse process (or the whole node) because a GROUP BY on a high-cardinality column built a hash table bigger than available RAM. If you fixed one of these in production, the interviewer wants the actual mechanism you diagnosed and the actual config/query change you made, not "I increased the memory limit."

---

## Lineage: past → present → future

**What came before.** Before column stores went mainstream for analytics, the default was row-store OLTP databases (Postgres, MySQL) pressed into service for reporting, or purpose-built but expensive proprietary MPP warehouses (Teradata, Vertica, Netezza). The pain: a row store reads and decompresses the entire row to answer a query touching three of forty columns, and scanning a large fact table row-by-row for an aggregate query is fundamentally I/O-bound in a way no amount of indexing fixes, because analytical queries typically scan large fractions of a table rather than seeking to a few rows. C-Store (the 2005 academic paper that became Vertica) and Google's Dremel/BigQuery (2010) established that columnar storage plus late materialization was the right shape for scan-heavy analytics, but these were either proprietary or required buying into a specific cloud. ClickHouse was built at Yandex (open-sourced 2016) specifically to answer "how many page views matched this filter" over web-analytics-scale data with sub-second latency, on commodity hardware, without a cluster of specialized appliances.

**Where it stands now.** ClickHouse's MergeTree family is the consensus reference implementation for "single-node columnar OLAP done right": sparse primary index, background merges, vectorized execution, and a rich codec/compression story are now the baseline that every competitor (DuckDB for single-node, StarRocks/Doris for distributed OLAP) is measured against. The live disagreement is about **operational model**: ClickHouse's original design assumes you understand parts, merges, and `ORDER BY` well enough to tune them, which is a real cliff for teams that just want "fast Postgres for analytics" — this is exactly the gap ClickHouse Cloud (managed, with SharedMergeTree separating storage/compute) and DuckDB (embedded, zero-ops, single-node-first) are each solving from different directions. What's actually deployed at scale: self-managed ClickHouse clusters for high-throughput event/log/metrics pipelines where teams have the operational maturity to tune merges and partitioning, ClickHouse Cloud where teams want the engine without the ops burden, and DuckDB/BigQuery for workloads that don't need ClickHouse's write throughput.

**Where it's heading.** ClickHouse Cloud's SharedMergeTree (storage-compute separation, shared object storage instead of local disk per replica) is the clear direction of travel for the managed offering, and it changes some of the "too many parts" arithmetic because merges become a shared-storage operation rather than per-replica; confidence is high since it's already GA and being pushed as the default for new Cloud services. More speculative: how much of ClickHouse's vector-search additions (in-house HNSW-backed vector similarity, competing with the dedicated vector-DB space this module's companion module covers) actually gets adopted for RAG-scale workloads versus staying a "nice for hybrid analytics+vector" feature is unsettled — the honest read is that a team already running ClickHouse for logs/metrics gets vector search "for free" at small scale, but a green-field RAG system with no existing ClickHouse footprint has no strong reason to adopt ClickHouse specifically for vectors over a dedicated store.

---

## Mental model

```
COLUMNAR STORAGE                          MERGETREE PARTS & BACKGROUND MERGES

  Row store:  [id,ts,url,ua,...] row1      INSERT 1 ──▶ part_1 (small, sorted by ORDER BY)
              [id,ts,url,ua,...] row2      INSERT 2 ──▶ part_2 (small, sorted)
              scan = read every column     INSERT 3 ──▶ part_3 (small, sorted)
              even if query needs 1              │
                                            background merge (async, low priority)
  Column store: [id,id,id,...]                    ▼
                [ts,ts,ts,...]              part_1+2+3 merged ──▶ one bigger sorted part
                [url,url,url,...]           (old parts deleted once merge completes)
                query touching url only
                reads ONLY that column      Too many small INSERTs, faster than merges can
                                             absorb -> part count climbs -> past a ceiling
                                             (default ~3000 active parts in a partition)
                                             ClickHouse REFUSES further inserts:
                                             "Too many parts (300). Merges are processing
                                              significantly slower than inserts."

SPARSE PRIMARY INDEX (not a B-tree, not unique)

  ORDER BY (user_id, ts)   index_granularity = 8192 (rows per granule)

  mark 0 -> (user=1,   ts=t0)   granule 0: rows 0..8191
  mark 1 -> (user=488, ts=t50)  granule 1: rows 8192..16383
  mark 2 -> (user=901, ts=t80)  granule 2: rows 16384..24575
  ...
  one index ENTRY per 8192 ROWS, not per row -> index for 1B rows is ~122K entries,
  fits in memory easily. A query WHERE user_id = 488 binary-searches the sparse
  index to find WHICH GRANULES could contain it, then reads only those granules --
  it does NOT look up a single row directly the way a B-tree would.
```

---

## How it actually works

### The MergeTree family and what each variant is for

`MergeTree` is the base engine: data physically sorted by `ORDER BY`, split into parts, merged in the background. The variants layer behavior onto merge-time:

| Engine | What happens on merge | Use case |
|---|---|---|
| `MergeTree` | plain merge, keeps all rows | general fact tables |
| `ReplacingMergeTree` | keeps only the latest row per `ORDER BY` key (by insertion order or a version column) | deduplicating late-arriving updates, CDC-style upserts |
| `SummingMergeTree` | sums numeric columns for rows sharing the `ORDER BY` key | pre-aggregated counters/metrics |
| `AggregatingMergeTree` | merges partial aggregate states (`-State` combinators) | rollups fed by materialized views |
| `CollapsingMergeTree` / `VersionedCollapsingMergeTree` | cancels out row pairs marked with `sign = -1`/`+1` | representing mutable entities as insert-only append/cancel pairs |

The critical shared gotcha: **merging is eventual, not immediate.** `ReplacingMergeTree` does not guarantee duplicates are gone until a merge has actually run (or you force it with `OPTIMIZE TABLE ... FINAL`, which is expensive and not meant for routine use) — a query right after insert can still see duplicate rows, which surprises people who read "Replacing" and assume it behaves like an upsert at write time.

### Parts, merges, and the "too many parts" failure

Every `INSERT` creates at least one new part (a self-contained, sorted, immutable set of column files on disk). A background merge process combines smaller parts into larger ones, keyed by size tiers, to keep query-time part-scanning bounded. The problem: **merges are asynchronous and rate-limited**, but inserts are not — if you insert one row at a time (or otherwise issue frequent tiny inserts), you create parts faster than the merge pool can absorb them, and ClickHouse has a hard protective ceiling (`parts_to_throw_insert`, default around 3000 active parts in a single partition) past which it rejects further inserts outright with `DB::Exception: Too many parts (N). Merges are processing significantly slower than inserts`, rather than let unbounded part counts degrade every query's read-side merge-on-read cost.

**The fix, in order of preference:**
1. **Batch inserts at the client.** ClickHouse's own guidance is roughly one insert per 1-2 seconds, each containing 10K-500K rows — batch in the application or an ingestion buffer rather than issuing per-event inserts.
2. **Use a `Buffer` table engine** in front of the MergeTree table if the producer genuinely cannot batch — it accumulates rows in memory and flushes periodically as a real batched insert.
3. **Reconsider partitioning granularity.** ClickHouse never merges parts across different partition values, so partitioning by day when you have low daily volume, or partitioning by a high-cardinality key, multiplies the number of independent small-part pools that each need their own merge attention — coarser partitioning (monthly instead of daily) is a common, meaningful fix.
4. Tune `max_insert_block_size` and merge pool sizing (`background_pool_size`) as a lever, but this treats a symptom the client-side batching fix addresses at the source.

### The sparse primary index: neither unique nor a B-tree

This is the single most interview-tested ClickHouse internals fact and it's worth stating precisely. The MergeTree primary index stores **one entry per granule** (`index_granularity`, default 8192 rows, adaptive since 19.x to target roughly 10MB of uncompressed data per granule for wide rows), not one entry per row — it records the first row's `ORDER BY` key value for each granule and a byte offset into the column files. This means:

- **It is not unique.** Multiple rows, even with different `ORDER BY` values, live inside the same granule; the index only tells you which granule a value's range starts in, not the exact row.
- **It is not a B-tree.** Point lookups don't descend a tree to a leaf; ClickHouse binary-searches the small in-memory array of granule-start values to find the range of granules that could contain a match, then reads (and filters, row-by-row within the granule) all of those granules.
- **A query filtering on a prefix of `ORDER BY` is cheap** because the sparse index can binary-search directly to the relevant granule range. A query filtering on a column *not* in `ORDER BY` (or not a leading prefix of it) can't use the primary index at all and falls back to a full scan of every granule in the part (still fast relative to a row store because of columnar reads and compression, but not sparse-index-accelerated).

**This is why `ORDER BY` is the real performance determinant**, more than any secondary index: it's simultaneously the physical sort order, the compression unit boundary (sorted columns compress far better because adjacent values are similar), and the sparse index's key. Choosing `ORDER BY (tenant_id, event_type, ts)` versus `(ts, tenant_id)` changes which queries can use the index at all, not just how fast they run.

### Partition pruning vs primary-key skipping vs data-skipping indices — three different mechanisms

These get conflated constantly and are a favorite trap:

- **Partition pruning**: if the query has a filter on the partition key (commonly a date truncation), ClickHouse skips entire partitions (whole directories of parts) without even consulting their indexes. Cheapest possible skip, coarsest granularity.
- **Primary-key skipping (the sparse index)**: within a part, binary-search the sparse index on `ORDER BY` columns to skip granules outside the filtered range. Works only for columns that are a leading prefix of `ORDER BY`.
- **Data-skipping indices** (`minmax`, `set`, `bloom_filter`, `ngrambf_v1`/`tokenbf_v1` for text): secondary, granule-level statistics stored per granule for *non*-`ORDER BY` columns, letting ClickHouse skip granules where, e.g., a `minmax` index proves the filtered value can't be in that granule's range. These are opt-in (`INDEX idx_name expr TYPE minmax GRANULARITY N`) and only help when the underlying data has actual locality for that column relative to granule boundaries — a bloom filter index on a column with no correlation to `ORDER BY` order still has to check most granules.

### Columnar storage, compression, and vectorized execution

Column-oriented storage means a query reading 3 of 40 columns only touches those 3 columns' files — an immediate I/O reduction proportional to columns-not-scanned. Because a column's values are stored contiguously and (for `ORDER BY` columns and correlated columns) tend to be locally similar, general compression (LZ4 for speed, ZSTD for ratio) plus specialized codecs (`Delta`, `DoubleDelta`, `Gorilla` for timestamps/metrics, `T64` for narrow integers) routinely hit 5-20x+ compression on real telemetry/log data, directly cutting both storage and the I/O a scan has to do. **Vectorized execution** means every operator (filter, aggregate function, arithmetic expression) processes a batch of values (a "block," commonly a few thousand rows) through tight, SIMD-friendly loops rather than a Volcano-style row-at-a-time iterator calling a virtual function per row — this is the actual mechanical reason ClickHouse's CPU-bound throughput on aggregate-heavy queries is an order of magnitude beyond a row-at-a-time engine even before considering I/O.

### Memory-bound operations and the OOM failure

Most ClickHouse operations stream: a filtered scan or a simple projection needs memory proportional to one block at a time, not the whole result. Three operations break that pattern and are the ones that actually OOM:

- **High-cardinality `GROUP BY`**: the aggregation hash table holds one entry per distinct group, growing with the number of distinct keys, not the number of rows scanned. `GROUP BY user_id` over a billion rows with 200M distinct users needs a hash table sized for 200M entries, which is a genuinely large, unavoidable memory cost unless you cap or pre-aggregate.
- **`JOIN`** (see below): the default hash-join algorithm loads the entire right-hand table into an in-memory hash table before probing.
- **Unbounded `ORDER BY`** without a `LIMIT`: sorting the full result set requires holding (or spilling) the whole thing.

The guardrail is `max_memory_usage` (per-query cap, and `max_memory_usage_for_user` per-user across concurrent queries), and server-wide `max_server_memory_usage_to_ram_ratio` (default 0.9, leaving headroom for the OS) as the last line of defense before the Linux OOM killer takes the whole `clickhouse-server` process — which is a materially worse outcome than one query getting a clean `Memory limit (for query) exceeded` exception, because it kills every other query running on the node too. **Spilling** is the mitigation for the first and third cases: `max_bytes_before_external_group_by` lets aggregation spill partial hash-table state to disk once it crosses a threshold (at a real latency cost, since disk-spilled aggregation is far slower than in-memory), and `max_bytes_before_external_sort` does the analogous thing for `ORDER BY`. Diagnosing after the fact means querying `system.query_log` for `type = 'QueryFinish'` (or the exception-carrying rows) ordered by `memory_usage` descending, to find which specific query pattern is the actual offender rather than guessing from the raw OOM alert.

```sql
-- diagnose the worst memory offenders from the last 24h
SELECT query_id, user, query_start_time, memory_usage / 1e9 AS memory_gb, query
FROM system.query_log
WHERE type = 'QueryFinish' AND event_time > now() - INTERVAL 1 DAY
ORDER BY memory_usage DESC
LIMIT 20;
```

### JOIN weakness and why you denormalize

ClickHouse's default join algorithm (`hash`) builds an in-memory hash table from the right-hand side, then streams the left side probing against it — this is the algorithm's whole cost model, and it means **the right-hand table's size, not the left's, is what determines memory pressure**, so query authors need to actively pick the smaller table as the right side (ClickHouse's optimizer doesn't reliably do this reordering for you in every case, unlike a mature relational planner). Real fact-to-dimension joins where the dimension table is more than a few hundred MB routinely blow past `max_memory_usage`. Algorithms like `grace_hash`, `partial_merge`, and `full_sorting_merge` can spill to disk instead of failing outright, but at a steep latency cost, and joins in general break the columnar-scan locality that makes ClickHouse fast in the first place (join probing is row-level, random-access work). The house guidance: keep joins to at most 3-4 per query, use a **dictionary** (`Dictionary` engine, refreshed on a schedule, held fully in memory for O(1) lookups) for frequently-joined small dimension tables instead of a real `JOIN`, and **denormalize at ingestion** — write the dimension attributes directly onto the fact table's rows at insert time — for anything both static and large enough that a live join would be expensive. This is the opposite instinct from OLTP schema design, and it's a real interview signal: someone who reflexively normalizes a ClickHouse schema the way they would a Postgres one hasn't internalized why the engine is fast.

### Projections and materialized views

**Materialized views** in ClickHouse are triggers, not (necessarily) periodic refreshes: an INSERT into the source table fires the MV's query against just the newly-inserted block and writes the result into a separate target table — the work of aggregation moves from query time to insert time, which is the right trade for dashboards hitting the same daily/hourly rollup repeatedly. **Projections** are a different mechanism: an alternate physical layout of the *same* table (different `ORDER BY`, optionally pre-aggregated) that ClickHouse's query optimizer transparently chooses to use instead of the base table's layout when it would answer the query faster — no separate table to query, no explicit routing in application code, but also no cross-table joins inside a projection definition. The practical choice: reach for a projection when you need to serve queries filtering on a column that isn't a prefix of the base table's `ORDER BY` and don't want a second physically-separate table to manage; reach for a materialized view when you want a genuinely pre-aggregated summary table (rollups, counts, sums) that's cheaper to query than re-aggregating raw rows every time, or when the transformation involves joining/reshaping beyond what a projection's single-table reordering can express.

---

## Build it from scratch

A minimal from-scratch demonstration of the sparse index's actual mechanics (binary search over granule-start values), the shape an interviewer may ask you to reason through:

```python
# untested sketch
from bisect import bisect_right

GRANULE_SIZE = 8192

class SparseIndex:
    """Simulates a MergeTree primary index over rows pre-sorted by ORDER BY key."""
    def __init__(self, sorted_keys: list):
        self.granule_starts = [sorted_keys[i] for i in range(0, len(sorted_keys), GRANULE_SIZE)]
        self.sorted_keys = sorted_keys

    def granules_for_range(self, lo, hi) -> range:
        # binary search: find which granules COULD contain keys in [lo, hi]
        start_granule = max(0, bisect_right(self.granule_starts, lo) - 1)
        end_granule = bisect_right(self.granule_starts, hi)
        return range(start_granule, end_granule)

    def scan(self, lo, hi) -> list:
        # a real scan still reads every row WITHIN the candidate granules and filters --
        # the sparse index narrows which granules to read, it doesn't pinpoint rows.
        results = []
        for g in self.granules_for_range(lo, hi):
            start = g * GRANULE_SIZE
            end = min(start + GRANULE_SIZE, len(self.sorted_keys))
            results.extend(k for k in self.sorted_keys[start:end] if lo <= k <= hi)
        return results
```

This omits adaptive granularity, per-column mark files, and merge-time index rebuilding, but shows the core reason `ORDER BY (user_id, ts)` makes `WHERE user_id = X` cheap (binary search narrows to one or two granules) and `WHERE some_other_column = X` expensive (every granule in the part is a candidate, since the index says nothing about that column's distribution). Full lab with a toy MergeTree including parts, background merge simulation, and the too-many-parts ceiling: `(lab pending)`.

---

## How it's done in production

**ClickHouse Cloud** (managed) uses `SharedMergeTree`, replacing per-replica local-disk parts with shared object storage — merges become a shared-storage operation coordinated via a lightweight metadata service rather than each replica independently doing its own merge work, which changes (generally relaxes) the too-many-parts arithmetic versus self-managed clusters on local SSD. **Self-managed** deployments handle sharding via `Distributed` engine tables (query fan-out across shards) and replication via `ReplicatedMergeTree` (ZooKeeper- or ClickHouse Keeper-coordinated replica sync), and operators own tuning `background_pool_size`, partition strategy, and `max_memory_usage` policy directly.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| `DB::Exception: Too many parts (N). Merges are processing significantly slower than inserts` | Frequent small inserts outpacing background merge throughput | Batch inserts (10K-500K rows per insert, ~1-2s cadence) at the client; use a `Buffer` table if the producer can't batch; coarsen partitioning |
| Query or whole server killed by OOM during a dashboard query | High-cardinality `GROUP BY`, large-right-side `JOIN`, or unbounded `ORDER BY` exceeding `max_memory_usage` / server memory | Set realistic `max_memory_usage` per query; enable `max_bytes_before_external_group_by`/`external_sort` to spill to disk; pre-aggregate or reduce cardinality; identify the offending query via `system.query_log` ordered by `memory_usage` |
| A `ReplacingMergeTree` table still returns duplicate rows right after insert | Deduplication happens at merge time, not insert time; the merge simply hasn't run yet | Query with `FINAL` for correctness-critical reads (accepting the cost), or wait for/force a merge for less time-sensitive use; don't assume "Replacing" means upsert-on-write |
| A filter on a column that "should" be indexed does a full granule scan anyway | The filtered column isn't a leading prefix of `ORDER BY`, so the sparse index can't narrow granules for it | Add a data-skipping index (`minmax`/`set`/bloom filter) if the column has enough locality to benefit, add a projection with a different `ORDER BY`, or reconsider the table's primary `ORDER BY` |
| A JOIN that worked fine in dev OOMs in production | The "small" dimension table grew, and it's on the right-hand side of a hash join whose entire content loads into memory | Put the smaller table explicitly on the right; switch to a `Dictionary` engine for the dimension; denormalize the attribute onto the fact table at ingestion instead of joining live |
| Query throughput craters over months even though data volume growth looks linear | Partitioning by a high-cardinality or too-fine-grained key (e.g., per-minute or per-customer partitions) fragments merges across many small independent partition pools, each accumulating unmerged parts | Repartition at a coarser grain (monthly instead of daily, or drop a high-cardinality partition column entirely in favor of it being part of `ORDER BY` instead) |

---

## Tradeoffs & when NOT to use it

- **Don't use ClickHouse for point updates or row-level transactional writes.** `ALTER TABLE ... UPDATE`/`DELETE` are asynchronous, heavyweight "mutations" that rewrite whole parts in the background — they are not the cheap, instant, row-level operation an OLTP engineer expects, and using ClickHouse as a system where individual rows get frequently updated in place is fighting the engine's whole design.
- **Don't use ClickHouse for high-concurrency OLTP** with many small, frequent, single-row writes — this is exactly the shape that produces the too-many-parts failure, and no amount of tuning changes that ClickHouse's write path is optimized for large batched inserts, not per-transaction commits.
- **Don't expect ACID multi-statement transactions.** ClickHouse has no general cross-table transactional guarantee; consistency is eventual at the part/merge level for the mutation-style operations it does support.
- **Don't normalize the schema the way you would in Postgres.** Joins are the weak point (whole right-hand table loaded into memory); denormalize at ingestion and use dictionaries for small reference data instead of defaulting to a star schema with live joins.
- **For anything where the answer must reflect the very latest write with strict consistency** (a user's current account balance, an inventory count gating a purchase decision), don't build it on ClickHouse alone — it's built for "how many, over what range, sliced how," not "the current authoritative value of this one row right now."
- **For genuinely low-volume analytics (a single laptop's worth of data, or embedded in an application without a server to manage)**, DuckDB is very often the better fit today — same columnar/vectorized philosophy, zero server operations, and it's the honest answer when someone reaches for ClickHouse purely out of brand familiarity rather than because they actually need distributed, high-throughput ingestion.

---

## Interview questions

### Q1 — Why is ClickHouse fast? Give the mechanical reasons, not "it's columnar."
**Testing:** whether they can go one level below the marketing pitch.
**Answer:** Four compounding factors: columnar storage (only scan columns the query needs), a sparse primary index (binary search over per-granule entries, not per-row, so the index stays tiny and in memory even at billions of rows), compression that benefits from sorted, locally-similar column data (5-20x+ on real telemetry with codecs like Delta/Gorilla/ZSTD), and vectorized execution (operators process blocks of a few thousand values through SIMD-friendly loops instead of a virtual-function call per row).
**Follow-up trap:** "Is the primary index a B-tree?" — no; it's a flat, sorted array of one entry per granule (default 8192 rows), searched via binary search to find candidate granule ranges, not a tree structure descending to individual rows.

### Q2 — What does `ORDER BY` actually control in a MergeTree table, and why does it matter more than any secondary index?
**Answer:** `ORDER BY` is simultaneously the physical row sort order on disk, the compression unit boundary (sorted, similar adjacent values compress better), and the sparse primary index's key. A query filtering on a leading prefix of `ORDER BY` can binary-search to relevant granules; a query filtering on any other column gets no help from the primary index and scans every granule in the part.
**Follow-up trap:** "If I add a data-skipping index on a non-`ORDER BY` column, doesn't that fix it?" — only if that column has real locality relative to granule boundaries; a bloom filter or minmax index on a column with no correlation to the physical sort order still has to check nearly every granule, since the statistic per granule won't be selective.

### Q3 — Walk through diagnosing and fixing a "Too many parts" error you hit in production.
**Testing:** real operational experience, the resume-highlighted fix.
**Answer:** The error means inserts are creating parts faster than background merges can absorb them, and the active part count in a partition passed the protective ceiling (default around 3000). Diagnosis: check insert frequency/size from the ingestion side — per-row or very frequent small inserts are the usual cause. Fix: batch inserts client-side (roughly 10K-500K rows per insert, one insert every 1-2 seconds), or front the table with a `Buffer` table engine if the producer genuinely can't batch, and check whether partitioning is too fine-grained (ClickHouse never merges across partitions, so over-partitioning multiplies the number of independent small-part pools).
**Follow-up trap:** "Why not just raise `parts_to_throw_insert`?" — that removes the safety valve without fixing the underlying imbalance between insert rate and merge throughput; you'll eventually degrade every query's read-time part-scanning cost instead of getting a clear error, which is a worse failure mode because it's silent and diffuse rather than loud and specific.

### Q4 — Your GROUP BY query OOM'd the ClickHouse server, not just the query. Walk through what happened and how you'd prevent it.
**Testing:** the specific production failure this student lived through.
**Answer:** A high-cardinality `GROUP BY` builds a hash table with one entry per distinct group; without a tight enough `max_memory_usage`, a query with enough distinct groups can exceed the server-wide memory ceiling (`max_server_memory_usage_to_ram_ratio`, default 0.9 of total RAM) before ClickHouse's own per-query accounting kills it, at which point the Linux OOM killer can take the whole `clickhouse-server` process, killing every other concurrent query, not just the offending one. Prevention: set a realistic `max_memory_usage` per query/user so ClickHouse's own limit fires first with a clean exception; enable `max_bytes_before_external_group_by` so the aggregation spills to disk past a threshold instead of growing unbounded; identify and fix the specific query pattern via `system.query_log` sorted by `memory_usage`.
**Follow-up trap:** "Doesn't spilling to disk just delay the OOM?" — no, it changes the failure mode from "hard OOM kill" to "slow but completed query," which is the whole point — it trades latency for not needing unbounded memory, since the spilled state is written and merged from disk instead of held entirely in RAM.

### Q5 — Explain partition pruning, primary-key skipping, and data-skipping indices as three distinct mechanisms.
**Answer:** Partition pruning skips whole partitions (directories of parts) based on a filter matching the partition key, without even reading an index — coarsest, cheapest skip. Primary-key skipping uses the sparse index to binary-search to candidate granules within a part, but only works for columns that are a leading prefix of `ORDER BY`. Data-skipping indices (minmax, set, bloom filter) are opt-in, granule-level statistics on other columns that let ClickHouse skip granules where the statistic proves no match is possible, but only help if the data has actual locality for that column relative to granule boundaries.
**Follow-up trap:** "If I filter on both the partition key and an ORDER BY column, which kicks in?" — both, in sequence: partition pruning eliminates whole partitions first, then within surviving partitions the sparse index narrows to specific granules — they compose rather than being mutually exclusive.

### Q6 — Why are JOINs the weak point of ClickHouse, mechanically?
**Answer:** The default hash join algorithm loads the entire right-hand table into an in-memory hash table before streaming and probing the left side against it, so the right table's size (not the query's overall row count) determines memory pressure, and a dimension table of more than a few hundred MB on the right side routinely exceeds `max_memory_usage`. Join probing is also row-level random-access work that breaks the sequential, columnar-scan-friendly access pattern that makes the rest of ClickHouse fast.
**Follow-up trap:** "So never join in ClickHouse?" — no; keep joins to roughly 3-4 per query max, always put the smaller table on the right, use a `Dictionary` engine (fully in-memory, O(1) lookup) for small frequently-joined reference tables, and denormalize static large-dimension attributes onto the fact table at ingestion instead of joining live.

### Q7 — Why is denormalizing the "right" instinct in ClickHouse when it's an anti-pattern in Postgres?
**Testing:** whether the candidate can articulate the engine-specific reasoning, not just recite the rule.
**Answer:** Postgres avoids denormalization because storage is cheap relative to the update-anomaly risk, and row-level updates to keep denormalized copies in sync are cheap and transactional in an OLTP engine. In ClickHouse, updates are expensive asynchronous mutations, storage is cheap relative to compute (compression already shrinks it dramatically), and joins are the expensive operation — so paying the storage/ingestion-time cost of writing denormalized attributes once, rather than paying a live-join cost on every query, is the actually cheaper tradeoff given what each engine is good and bad at.
**Follow-up trap:** "What if the dimension attribute changes after ingestion?" — that's the real cost of denormalization here: historical fact rows keep the value as of ingestion time unless you re-process them, which is fine for slowly-changing or immutable-at-write-time attributes and wrong for attributes that must always reflect current truth — for those, a `Dictionary` engine refreshed on a schedule is the better fit than baking the value into the fact table.

### Q8 — What's the difference between a materialized view and a projection, and when would you pick each?
**Answer:** A materialized view is a trigger fired on insert into the source table, writing its query's result into a separate target table — moving aggregation work from query time to insert time, and requiring you to query the target table explicitly (or route to it). A projection is an alternate physical layout of the *same* table (different sort order, optionally pre-aggregated) that the query optimizer transparently picks when it answers a query faster, with no separate table and no application-level routing, but no cross-table joins allowed inside the definition. Pick a projection when you need fast filtering on a non-`ORDER BY` column of one table; pick a materialized view for genuine rollups/aggregation, especially anything involving reshaping beyond one table's reordering.
**Follow-up trap:** "Does a projection duplicate storage?" — yes, a projection with a different `ORDER BY` stores a second physical copy of the relevant columns sorted differently, so it's a real storage/ingestion-time cost traded for query-time flexibility, not a free index.

### Q9 — A `ReplacingMergeTree` table is supposed to deduplicate rows by key, but a query right after insert shows duplicates. Why?
**Answer:** Deduplication in `ReplacingMergeTree` happens at merge time (keeping only the latest row per `ORDER BY` key based on insertion order or an explicit version column), not at insert time — a query run before the relevant parts have merged will see all versions, including stale ones.
**Follow-up trap:** "How do you get a correct answer right now, without waiting?" — query with `FINAL` (forces on-the-fly deduplication at query time across all matching parts), which gives a correct result but at real CPU/latency cost proportional to how many unmerged duplicate versions exist — acceptable for occasional correctness-critical reads, wrong to use as the default query pattern on a hot path.

### Q10 — When is ClickHouse the wrong choice, concretely?
**Testing:** the "when NOT to use it" the house format requires — this should be specific, not a token disclaimer.
**Answer:** Point updates/deletes at OLTP frequency (mutations are heavyweight async part rewrites, not cheap row-level ops), high-concurrency transactional writes with many small single-row inserts (the too-many-parts failure mode directly), any requirement for multi-statement ACID transactions, and any query needing the single current authoritative value of one specific row with strict consistency (an account balance gating a decision) rather than an aggregate over a range.
**Follow-up trap:** "What would you actually use instead for that OLTP-shaped subset of the workload?" — a row-store OLTP database (Postgres/MySQL) for the transactional writes and point-lookup reads, with ClickHouse fed asynchronously (CDC, batched ETL) purely for the analytical/aggregate side — the two-database split is the normal production pattern, not a failure to pick one tool.

### Q11 — Explain why a filter like `WHERE status = 'error'` might scan the entire table even though the column exists and has few distinct values.
**Answer:** If `status` isn't a leading prefix of `ORDER BY`, the sparse primary index provides no help for it — every granule in every part is a candidate, and ClickHouse must read (decompress and filter) each one to check for matches, which for a low-cardinality column scattered randomly across granules means nearly every granule likely contains at least one match anyway, so even a data-skipping index like `set` wouldn't skip much.
**Follow-up trap:** "Would a bloom filter index fix it?" — a `set` or bloom filter index only helps when a meaningful fraction of granules provably contain *no* matching value; for a column like `status` with only a handful of distinct values spread evenly across the whole table, most granules will contain every value, so the index adds overhead (it must be checked and maintained) without meaningfully reducing granules scanned. It helps far more for high-cardinality columns with real locality, like a request ID correlated with insertion order.

### Q12 — Staff-level: design the ingestion path for a service producing 50,000 events/sec that needs sub-minute dashboard latency, avoiding both the too-many-parts and OOM failure modes.
**Testing:** synthesis across the whole module.
**Answer:** Buffer events in the application or a lightweight queue and flush batched inserts of tens of thousands of rows every 1-2 seconds rather than inserting per-event, keeping part creation rate well under merge throughput. Partition at a grain matched to actual data volume and query patterns (daily is often fine at this scale; avoid per-minute or per-customer partitioning that fragments merge pools). Pre-aggregate the dashboard's actual query shape into a materialized view fed by the raw event table, so the dashboard queries a small rolled-up table instead of re-aggregating raw high-cardinality events on every page load, capping the GROUP BY memory cost at query time regardless of raw ingestion volume. Set `max_memory_usage` and `max_bytes_before_external_group_by` as guardrails on any ad hoc query path that does hit the raw table directly.
**Follow-up trap:** "What breaks first if traffic 10xes to 500K events/sec?" — batched inserts scale roughly linearly with the batching approach unchanged (bigger or more frequent batches, still well under the too-many-parts ceiling), but the materialized view's own insert-time aggregation cost and any dictionary refresh cadence become the next bottlenecks to check — the honest answer names what to re-measure, not a guess.

---

## Red flags that fail you

- Saying "ClickHouse is fast because it's columnar" and stopping there, with no mention of the sparse index, compression, or vectorization.
- Believing the primary index is a B-tree, or that it's unique per row.
- Not knowing that `ORDER BY` determines index usability, or recommending a secondary index as the first fix for a slow filter on a non-`ORDER BY` column.
- Treating `ReplacingMergeTree` as an instant upsert with no mention of merge timing or `FINAL`.
- Recommending normalization/joins as the default schema approach, the way you would for Postgres.
- Not knowing what causes "too many parts" or proposing "just raise the limit" as the fix instead of addressing insert batching.
- Not knowing which operations (GROUP BY, JOIN, unbounded ORDER BY) are memory-bound versus which stream.
- Suggesting ClickHouse for an OLTP workload with frequent point updates without flagging that mutations are heavyweight and asynchronous.

---

## Cheat card

```
WHY FAST        columnar (scan only needed columns) + sparse index (1 entry/granule,
                binary search) + compression (sorted cols compress 5-20x+) +
                vectorized execution (SIMD, block-at-a-time, not row-at-a-time)

SPARSE INDEX    index_granularity default 8192 rows/granule (adaptive ~10MB uncompressed
                since 19.x) · NOT unique, NOT a B-tree · only helps queries filtering on
                a LEADING PREFIX of ORDER BY

PARTS/MERGES    every INSERT = >=1 new part; background merge combines them
                TOO MANY PARTS: insert rate > merge throughput, hits ceiling
                (~3000 active parts/partition default) -> INSERTs REJECTED
                FIX: batch 10K-500K rows/insert every 1-2s; Buffer table; coarser
                partitions (never merges ACROSS partitions)

3 SKIP MECHANISMS   partition pruning (skip whole partitions, no index needed)
                    primary-key skip (sparse index, ORDER BY prefix only)
                    data-skipping index (minmax/set/bloom, opt-in, needs locality)

OOM             GROUP BY (hash table ~ #distinct groups), JOIN (right side loaded
                FULLY in memory), unbounded ORDER BY -- the only non-streaming ops
                max_memory_usage = per-query cap; max_server_memory_usage_to_ram_ratio
                default 0.9 = last line before Linux OOM-kills the WHOLE server
                FIX: max_bytes_before_external_group_by / external_sort = spill to disk
                DIAGNOSE: system.query_log WHERE type='QueryFinish' ORDER BY memory_usage DESC

JOIN            default hash join loads RIGHT side fully into memory -> put smaller
                table on right; Dictionary engine for small dims; denormalize at
                ingest for static large dims; keep to 3-4 joins/query max

REPLACING       dedup happens at MERGE time, not insert time -- use FINAL for
MERGETREE       correctness-critical reads (costs CPU), don't assume upsert-on-write

PROJECTIONS     same table, alt physical layout, optimizer auto-picks, no cross-join
MAT. VIEWS      separate table, trigger on insert, query-time -> insert-time shift

WRONG FOR       point updates/deletes (heavyweight async mutations), high-concurrency
                OLTP writes, multi-statement ACID transactions, single-row strict-
                consistency lookups (use Postgres/MySQL for that half, feed CH via CDC)
```

## Sources

- [Resolving "Too Many Parts" error in ClickHouse — ClickHouse Docs](https://clickhouse.com/docs/knowledgebase/exception-too-many-parts) — accessed 2026-08-01
- [Identifying expensive queries by memory usage in ClickHouse — ClickHouse Docs](https://clickhouse.com/docs/knowledgebase/finding_expensive_queries_by_memory_usage) — accessed 2026-08-01
- [Memory limit exceeded for query — ClickHouse Docs](https://clickhouse.com/docs/knowledgebase/memory-limit-exceeded-for-query) — accessed 2026-08-01
- [Rescuing ClickHouse from the Linux OOM Killer — Altinity Blog](https://altinity.com/blog/rescuing-clickhouse-from-the-linux-oom-killer) — accessed 2026-08-01
- [A practical introduction to primary indexes in ClickHouse — ClickHouse Docs](https://clickhouse.com/docs/guides/best-practices/sparse-primary-indexes) — accessed 2026-08-01
- [MergeTree table engine — ClickHouse Docs](https://clickhouse.com/docs/engines/table-engines/mergetree-family/mergetree) — accessed 2026-08-01
- [Materialized views versus projections — ClickHouse Docs](https://clickhouse.com/docs/managing-data/materialized-views-versus-projections) — accessed 2026-08-01
- [Minimize and optimize JOINs — ClickHouse Docs](https://clickhouse.com/docs/best-practices/minimize-optimize-joins) — accessed 2026-08-01
- [When to denormalize, when to join: A ClickHouse guide — ClickHouse Engineering](https://clickhouse.com/resources/engineering/when-to-denormalize-when-to-join) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
