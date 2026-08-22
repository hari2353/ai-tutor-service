# Shuffle, Skew, AQE, Broadcast, Partitioning, Caching, UDF Costs

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-pyspark-advanced` · **Tags:** spark,critical

## The 30-second version

Almost every Spark performance problem traces back to one of three things: an unnecessary or badly-sized shuffle, data skew where one key dwarfs the rest, or a Python UDF paying a JVM-to-Python serialization tax on every row. Adaptive Query Execution, default on since Spark 3.2, fixes the first two automatically in the common case: it coalesces shuffle partitions to a target size instead of trusting a static `200`, it switches join strategies after seeing real output sizes instead of pre-execution estimates, and it detects and splits skewed partitions in a sort-merge join without you writing salting code. For the third, pandas/Arrow UDFs move data across that boundary in Arrow-columnar batches instead of row-by-row pickled objects, typically a 3x-100x improvement over row-at-a-time Python UDFs. The single most diagnostic symptom in this whole space is skew: 199 tasks finish in seconds, one runs for 40 minutes, and if AQE's skew-join handling isn't catching it, you're looking at a key that's either not part of an equi-join AQE can rewrite, or a groupBy where AQE's skew handling doesn't apply at all.

## Why this gets asked

Because "add more executors" is the wrong answer to nearly every Spark slowness ticket, and the interviewer has watched someone throw 3x the cluster size at a job with one skewed key and get a 5% improvement. They want to see you go to the Spark UI, find the one task that ran 200x longer than its siblings, and reason about *why*, not reach for the scaling lever. At staff level they're also checking whether you know AQE's limits: what it can't fix (groupBy skew, `.rdd` boundaries, non-equi joins) so you don't over-trust automation you haven't verified is actually engaging.

---

## Lineage: past → present → future

**What came before.** Pre-AQE Spark (2.x and earlier) planned everything statically before execution, using either no statistics or stale/absent table statistics, and committed to that plan for the entire job. Skew handling meant hand-rolled salting: append a random suffix to a hot key, explode the other side of the join to match every salt value, join, then strip the suffix, code every data engineer maintained a version of. Join strategy selection was a single pre-execution guess based on `spark.sql.autoBroadcastJoinThreshold` and whatever statistics happened to be available, and a stale statistic meant a multi-hour sort-merge join where a sub-second broadcast would have worked, discovered only by staring at a stuck job in the Spark UI.

**Where it stands now.** AQE landed experimentally in Spark 2.4, became **default-enabled in Spark 3.2.0** ([Spark 3.2.0 docs](https://downloads.apache.org/spark/docs/3.2.0/sql-performance-tuning.html)), and by Spark 3.5/4.x is the assumed baseline in any production cluster. It re-optimizes at **shuffle boundaries only**, using the actual map-output statistics of the shuffle that just completed, for three things: coalescing partitions toward `spark.sql.adaptive.advisoryPartitionSizeInBytes` (default 64MB), switching a planned sort-merge join to a broadcast join if the actual runtime size of one side is now known to be under the broadcast threshold, and detecting skewed partitions in a sort-merge join (a partition whose size exceeds `spark.sql.adaptive.skewJoin.skewedPartitionFactor`, default 5x the median, and an absolute floor `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes`, default 256MB) and splitting them into sub-partitions automatically. Manual salting is now mostly legacy technique for cases AQE can't reach: aggregation skew (`groupBy` without a join) and non-equi joins. On the UDF side, pandas UDFs (Arrow-backed, since Spark 2.3) are the accepted fix for row-at-a-time Python UDF cost, and Spark's newer Arrow-native UDFs push further by skipping the pandas conversion step entirely.

**Where it's heading.** The clear trend is AQE's scope widening (dynamic partition pruning integration, more join-strategy switches, better cost estimation) and the pandas-UDF-to-Arrow-UDF transition continuing (Arrow UDFs reported roughly 10% faster and ~40% less memory than pandas UDFs by avoiding the pandas/NumPy materialization step entirely, operating on Arrow's columnar layout end to end). More speculative: as vectorized execution engines (Photon at Databricks, Comet as an open Arrow-native Spark accelerator) mature, the JVM-row-based execution path this module assumes may itself become a legacy tier for compatibility, with a columnar/native path as the fast default. Treat that as a direction of travel; it is not yet the default for open-source Spark.

---

## Mental model

```
                                SHUFFLE = the expensive thing
  Stage N (map side)                              Stage N+1 (reduce side)
  ┌────────┐ ┌────────┐ ┌────────┐                ┌────────┐ ┌────────┐
  │ Task 0 │ │ Task 1 │ │ Task 2 │   ...           │ Task 0 │ │ Task 1 │  ...
  └───┬────┘ └───┬────┘ └───┬────┘                └───▲────┘ └───▲────┘
      │ writes N buckets each (1 per reduce partition) │           │
      ▼          ▼          ▼                          │           │
  ┌─────────────────────────────────────┐              │           │
  │ shuffle files on local disk           │──── each downstream task
  │ (M map tasks × N reduce partitions)   │     fetches its bucket from
  └─────────────────────────────────────┘     every upstream task ──┘

  AQE sits HERE, between stages, and rewrites the NEXT stage's plan
  using the ACTUAL sizes just observed, not the pre-execution guess:
    - coalesce many small output partitions into fewer right-sized ones
    - if one join side turned out small enough -> switch to broadcast
    - if one partition is way bigger than its siblings -> split it (skew)
```

**Why skew looks the way it does in the UI**: a hash partitioner sends every row of key `K` to the same reducer task, deterministically. If key `K` is 40% of your data (a common real-world case: a default/null customer ID, a dominant SKU, a bot user-agent), one task gets 40% of the shuffle's data and 199 others split the remaining 60%. Task duration is roughly proportional to data volume for a CPU-bound operator, so you see 199 tasks finish in seconds and one run for 40 minutes while sitting at nearly 100% of one core, the textbook observable symptom of skew.

## How it actually works

### Shuffle mechanics and why it dominates cost

A shuffle costs on three axes simultaneously: **disk I/O** (every map task writes its shuffle output to local disk, every reduce task reads its bucket back from disk), **network I/O** (reduce tasks fetch buckets from remote executors over the wire, an all-to-all pattern in the worst case), and **serialization** (each record is serialized on write and deserialized on read). None of this exists for narrow transformations, which is exactly why they fuse into a single stage with zero data movement. A job dominated by shuffles (multiple joins and aggregations chained together) is, in practice, a job dominated by disk and network time, not CPU time, which is the first thing to check when a job "isn't using much CPU" in monitoring but is still slow.

### Skew: symptom, cause, every fix

**The symptom, stated precisely** (this is the pattern-match the interviewer wants): in the Spark UI's stage view, task duration is wildly non-uniform, e.g. 199 tasks complete in under 10 seconds and 1 task runs for 40 minutes, visible as a single outlier bar in the event timeline or a huge max/median ratio in the task summary metrics. The task's shuffle-read size will also be an outlier, confirming it's data skew and not, say, a slow node.

**Every fix, in order of how automated it is:**

1. **AQE skew join splitting** (automatic, if applicable). Only applies to **sort-merge joins**. AQE detects a partition exceeding `skewedPartitionFactor × median partition size` (default factor 5) AND exceeding the absolute floor `skewedPartitionThresholdInBytes` (default 256MB), then splits it into multiple smaller tasks, replicating the other side's matching partition as needed. Requires `spark.sql.adaptive.skewJoin.enabled=true` (on by default when AQE is on).
2. **Broadcast the small side** (removes the shuffle, and skew with it). If one side of a skewed join is small enough to broadcast, there's no shuffle on the join key at all, no partitioner, no skew. This is the best fix when applicable, and AQE will often make this switch itself post-shuffle if the size becomes known to be under threshold.
3. **Salting** (manual, for what AQE can't reach: `groupBy` aggregation skew, or joins AQE's skew handling doesn't trigger on). Append `floor(rand() * N)` to the skewed key, do the aggregation/join against an equivalently exploded other side, then strip the salt and do a final combine.
   ```python
   from pyspark.sql import functions as F
   N_SALT = 20
   salted = df.withColumn("salt", (F.rand() * N_SALT).cast("int"))
   partial = salted.groupBy("key", "salt").agg(F.sum("value").alias("partial_sum"))
   final = partial.groupBy("key").agg(F.sum("partial_sum").alias("total"))
   ```
   This trades one skewed groupBy for two evenly-distributed ones plus a small final combine, at the cost of more code and an extra shuffle stage.
4. **Isolate the hot key** — filter it out, process it separately (often it can go through a broadcast path or a dedicated single-partition job), union results back. Useful when one or two known keys (a null/default bucket, a test account) dominate.

### AQE: what it actually does and the version it matters from

Three AQE features, gated by `spark.sql.adaptive.enabled=true` (**default true since Spark 3.2.0**, [Spark 3.2.0 release docs](https://downloads.apache.org/spark/docs/3.2.0/sql-performance-tuning.html)):

| Feature | Config | Default | What it does |
|---|---|---|---|
| Coalesce partitions | `spark.sql.adaptive.coalescePartitions.enabled` | true | Merges small post-shuffle partitions toward `advisoryPartitionSizeInBytes` (64MB default) |
| Switch join strategy | (automatic, part of AQE) | — | Re-plans a join to broadcast if a shuffle's actual output proves one side is under `autoBroadcastJoinThreshold` |
| Skew join split | `spark.sql.adaptive.skewJoin.enabled` | true | Splits sort-merge join partitions exceeding `skewedPartitionFactor` (5x median) and `skewedPartitionThresholdInBytes` (256MB) |

AQE only re-plans at **materialization points** (shuffle boundaries), because that's the only point where it has real statistics instead of estimates. This is the important limitation: AQE cannot help with skew inside a single non-shuffling stage, cannot fix a bad plan choice made before the first shuffle even happens, and does not apply to RDD operations at all, only the DataFrame/SQL/Dataset API.

### Join strategy selection

```python
df_a.join(df_b, "id").explain()
```

| Strategy | When chosen | Cost profile |
|---|---|---|
| **Broadcast hash join** | One side's size (bytes) is below `spark.sql.autoBroadcastJoinThreshold` (**default 10MB**) or AQE observes it's small enough post-shuffle | No shuffle of the large side at all; small side sent whole to every executor. Fastest when applicable. |
| **Sort-merge join** | Default for two large sides on an equi-join | Both sides shuffled and sorted by join key, then merged. Standard, scalable, but pays full shuffle cost both sides. |
| **Shuffle hash join** | Explicitly enabled/hinted, one side small-ish but over broadcast threshold, and `spark.sql.join.preferSortMergeJoin=false` | Both sides shuffled (not sorted); a hash table built from the smaller side per partition. Avoids the sort cost but risks OOM building the hash table if that side is bigger than expected. Rarely the default choice in modern Spark. |
| **Broadcast nested loop join** | No equi-join condition available (non-equi condition, or a cross join) | O(n×m) per partition. A correctness/performance red flag if seen unintentionally; usually means the join condition isn't what you think it is. |

`autoBroadcastJoinThreshold` defaults to **10MB** ([Spark internals docs](https://jaceklaskowski.gitbooks.io/mastering-spark-sql/content/spark-sql-joins-broadcast.html)), deliberately conservative because broadcasting too aggressively risks driver and executor OOM (the whole table is materialized in the driver first, then pushed to every executor). Raising it (commonly to 100MB-1GB for dimension tables) is a very common, very safe tuning lever, but it depends on accurate table size statistics from `ANALYZE TABLE`; without them the optimizer's size estimate can be wrong and either miss a broadcast opportunity or attempt one that OOMs the driver.

### Caching and persist storage levels

`.cache()` is shorthand for `.persist(StorageLevel.MEMORY_AND_DISK)` (PySpark default; Scala's default is also `MEMORY_AND_DISK` since Spark 2.x for DataFrames/Datasets, though the plain RDD API default is `MEMORY_ONLY`).

| Storage level | Behavior | Use when |
|---|---|---|
| `MEMORY_ONLY` | Cached in JVM object form in memory; recompute from lineage if evicted | Small dataset, cheap to recompute |
| `MEMORY_AND_DISK` | Spills to local disk if it doesn't fit in memory | Default choice; avoids recompute cost at the price of disk I/O |
| `MEMORY_ONLY_SER` / `MEMORY_AND_DISK_SER` | Serialized (compact) form; more CPU to (de)serialize, much less memory | Memory-constrained clusters, large cached datasets |
| `DISK_ONLY` | Never in memory | Rare; effectively a manual checkpoint without lineage truncation |

**Caching makes things slower** in several concrete, real cases:
- The cached DataFrame is used **only once** downstream. You pay the cost of materializing and storing it for zero reuse benefit, and if it doesn't fit in memory you've added disk spill cost on top for nothing.
- The cache **evicts something else that was actually being reused**, under memory pressure, forcing that other DataFrame to recompute from lineage, a net loss.
- Caching **before** a filter that would have reduced the data significantly. Caching the full table before `.filter()` holds far more in memory (or disk) than caching after.
- Using `.cache()` as a substitute for fixing an actual performance problem (a bad join strategy, a missing broadcast) rather than addressing the cause, it hides the symptom by trading it for memory pressure elsewhere.

Verify a cache is actually being used via the Spark UI's Storage tab (shows fraction cached, size in memory/disk) — a very common bug is caching a DataFrame reference and then applying a further transformation before the reuse point, which produces a *new* logical plan that doesn't hit the cached one at all, since caching is keyed to the specific plan node, not "the data" abstractly.

### Python UDF cost: the JVM/Python boundary

A standard PySpark UDF (`@udf` / `F.udf(...)`) executes **row by row**, and each row crosses the JVM-Python process boundary: the JVM executor serializes the row (historically via a per-row protocol, now still fundamentally per-row for plain UDFs), pipes it to a separate Python worker process, the Python function runs, and the result is serialized back. This has three costs stacked on top of each other: (1) the UDF itself is an optimization barrier, as covered in the previous module, so Catalyst can't push filters or prune columns across it; (2) inter-process communication overhead per row; (3) the Python interpreter's own per-call overhead versus a JIT-compiled JVM expression.

**Pandas UDFs (Arrow-backed)** fix the throughput problem by batching: rows are transferred to the Python worker in **Arrow columnar batches**, the Python function operates on a `pandas.Series`/`DataFrame` (vectorized, using NumPy/pandas under the hood), and the result batch is transferred back the same way. Measured improvement: **3x to 100x** over row-at-a-time Python UDFs depending on the operation (higher for simple vectorizable math, lower for operations that don't vectorize well).

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf("double")
def normalize(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()          # vectorized, batch at a time

df.withColumn("norm_amount", normalize(df.amount))
```

**Arrow UDFs**, the newer generation, skip the pandas/NumPy materialization step and operate directly on Arrow's columnar format, reported roughly **10% faster and ~40% less memory** than pandas UDFs with better support for complex/nested types, at the cost of writing against the raw Arrow API instead of the more familiar pandas API.

The single most important number here for an interview: **row-at-a-time Python UDF vs pandas/Arrow UDF is the single largest, cheapest lever available** for a Python-heavy Spark job, because it's a one-line decorator change with no algorithmic rework, unlike shuffle/skew fixes which require understanding the data distribution.

### Partitioning and bucketing on write

**Partitioning** (Hive-style directory partitioning, `df.write.partitionBy("date")`) splits output into directories by column value, enabling partition pruning on read (a query filtering `date = '2026-08-01'` only touches that directory). Over-partitioning (high-cardinality columns, or too many small partitions) creates the classic **small files problem**: thousands of tiny files, each with per-file overhead on open/list/read that dominates actual data transfer, especially painful on S3 where listing is a metadata API call with real latency.

**Bucketing** (`df.write.bucketBy(50, "user_id")`) pre-shuffles data into a fixed number of buckets by hash of a column at write time, so that a *future* join or aggregation on that same column can skip the shuffle entirely if both sides are bucketed identically (same bucket count, same column). The cost is paid once at write time instead of repeatedly at every read-time join. Underused in practice because it requires the write-time schema decision to match all future query patterns, and because it's poorly supported by Spark's file-format-agnostic table formats (Iceberg/Delta have their own, different mechanisms for the same goal, e.g. Iceberg's hidden partitioning and z-ordering/sort-based clustering).

### Spill, OOM, and executor memory layout

Executor memory (`spark.executor.memory`) is divided by the **Unified Memory Manager** (default since Spark 1.6): `spark.memory.fraction` (**default 0.6**) of the JVM heap is reserved for Spark's unified execution+storage region; the remainder is "user memory" for user data structures and Spark internal metadata. Within the unified region, `spark.memory.storageFraction` (**default 0.5**) sets the boundary between storage (cached data) and execution (shuffle buffers, sort buffers, hash tables for joins/aggregations) memory, but the boundary is soft: execution can evict storage under pressure (storage cannot evict execution, execution always wins a contention). On top of `spark.executor.memory`, `spark.executor.memoryOverhead` (**default 10% of executor memory, minimum 384MB**) covers off-heap JVM overhead, native library allocations, and (for PySpark) is where the separate Python worker process's memory usage effectively needs to be budgeted, since `spark.executor.memory` only covers the JVM.

**Spill** happens when an operator that supports external (disk-backed) execution, sort, aggregation, some join implementations, runs out of its allotted execution memory: it writes partial results to disk and merges later, trading time for staying within memory bounds. Visible in the Spark UI as "Spill (Memory)" / "Spill (Disk)" metrics on a stage; non-zero spill isn't automatically a bug, but heavy spill on a job that used to run fine is a strong signal that either data volume grew or a skewed partition is forcing one task to handle far more than its fair share.

**OOM** happens when memory pressure exceeds what spilling or eviction can resolve, most commonly: (a) a broadcast join where the "small" side turned out much larger than the optimizer's stale statistics suggested, driver or executor OOMs trying to materialize the full broadcast; (b) a single skewed partition whose data plus working set (e.g. building a hash table for a shuffle hash join) exceeds one executor's memory even though the *cluster* has plenty of aggregate memory; (c) `.collect()` on data larger than driver memory.

---

## Build it from scratch

A minimal reproduction of skew and its fix, runnable locally, useful for demonstrating the mechanism rather than reciting it:

```python
from pyspark.sql import SparkSession, functions as F
import random

spark = SparkSession.builder.master("local[4]") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.skewJoin.enabled", "true") \
    .getOrCreate()

# Skewed dataset: key "HOT" is 60% of rows, 99 other keys share the rest.
rows = [("HOT", i) for i in range(600_000)] + \
       [(f"k{i % 99}", i) for i in range(400_000)]
df = spark.createDataFrame(rows, ["key", "val"]).repartition(8)

dim = spark.createDataFrame([(f"k{i}", f"name{i}") for i in range(99)] +
                             [("HOT", "hot_name")], ["key", "name"])

# Without any handling: sort-merge join, AQE skew split should engage
# automatically if the skewed partition clears the thresholds.
joined = df.join(dim, "key")
joined.explain(mode="formatted")   # look for OptimizeSkewedJoin in the plan

# Manual salting, for comparison (what you'd do pre-AQE, or for a groupBy
# AQE's skew-join handling doesn't cover):
N_SALT = 10
salted_df = df.withColumn("salt", (F.rand() * N_SALT).cast("int"))
exploded_dim = dim.withColumn(
    "salt", F.explode(F.array(*[F.lit(i) for i in range(N_SALT)]))
)
salted_join = salted_df.join(exploded_dim, ["key", "salt"]).drop("salt")
```

Run with `spark.sql.adaptive.skewJoin.enabled` toggled true/false and diff the physical plan (`joined.explain(mode="formatted")` shows an `OptimizeSkewedJoin` node when engaged) and the Stage UI's task duration distribution. A full lab with `spark-submit` scripts against generated skewed Parquet data, a UDF-vs-pandas-UDF throughput benchmark harness, and a broadcast-threshold experiment belongs in a lab folder for hands-on practice; it is not required to answer this module's interview questions.

---

## How it's done in production

**Databricks / EMR / open-source Spark 3.5+** ship AQE on by default; production tuning work is mostly about *verifying* AQE is engaging (checking `explain()` for `AQEShuffleRead` and `OptimizeSkewedJoin` nodes) rather than writing manual skew-handling code, reserving salting for the cases AQE genuinely can't reach (`groupBy` skew, non-equi joins). Table statistics maintenance (`ANALYZE TABLE ... COMPUTE STATISTICS FOR ALL COLUMNS`, or the managed-platform equivalent, e.g. Databricks' predictive optimization) matters more than most tuning knobs, because both broadcast-threshold decisions and AQE's initial (pre-shuffle) plan depend on them being fresh.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| 199 tasks finish in seconds, 1 task runs 40 minutes | Data skew on the shuffle key | Verify AQE skew-join is engaged (check plan for `OptimizeSkewedJoin`); if it's a groupBy or non-equi join, salt manually |
| Job OOMs right after a join that used to work fine | Broadcast attempted on a table that grew past the stale-statistics estimate | Refresh statistics (`ANALYZE TABLE`), lower `autoBroadcastJoinThreshold` or disable broadcast with a hint, let AQE's runtime size check correct it |
| Stage shows heavy "Spill (Disk)" on every task uniformly | Executor memory undersized for the shuffle/sort/aggregation working set at current data volume | Increase executor memory or `shuffle.partitions`/AQE advisory size to shrink per-partition working set |
| PySpark job's Python worker processes show high CPU, JVM executor shows low CPU | Row-at-a-time Python UDF dominating wall-clock time | Convert to pandas/Arrow UDF, or replace with built-in `pyspark.sql.functions` if possible |
| Cache "helps" in dev on sampled data but production job is slower with `.cache()` than without | Cached DataFrame only consumed once, or cache evicting a more valuable cached dataset | Remove the cache; verify actual reuse via the Storage tab before adding one |
| Thousands of tiny output files under one partition directory | Over-partitioning on write (high-cardinality partition column, or too many shuffle partitions feeding the writer) | Coarser partition column, or `.coalesce()`/AQE-driven partition sizing before write |
| `explain()` shows sort-merge join for a join against a table you know is small | Missing or stale table statistics, so the optimizer's size estimate is wrong | `ANALYZE TABLE`, or an explicit `.hint("broadcast")` |

---

## Tradeoffs & when NOT to use it

- **Do not manually salt a join AQE already handles.** If `explain()` shows `OptimizeSkewedJoin` already engaging correctly, hand-rolled salting adds an extra shuffle stage and maintenance burden for a problem that's already solved. Check the plan before writing salting code.
- **Do not raise `autoBroadcastJoinThreshold` blindly.** A large broadcast threshold combined with stale or absent statistics can cause the optimizer to attempt a broadcast of a table that's actually much bigger than believed, OOMing the driver during collection or every executor during distribution. Pair any threshold increase with actual statistics maintenance.
- **Do not cache reflexively.** Caching costs memory (competing with execution memory, per the Unified Memory Manager) and, for anything beyond `MEMORY_ONLY`, CPU for serialization. A DataFrame used once should never be cached. Verify reuse via the Storage tab before trusting that a cache is paying for itself.
- **Do not reach for a pandas/Arrow UDF as a first resort over a built-in function.** If the logic is expressible as `pyspark.sql.functions` composition, it stays fully inside Catalyst's optimization and codegen path, faster than even a well-vectorized UDF, which is still an opacity barrier for that operation, just a cheaper one. UDFs (of any flavor) are the fallback, not the default.
- **Do not bucket write-side data for a join pattern that will change.** Bucketing locks in an assumption about future query shape; if the join key or bucket count assumption changes, you've paid a shuffle cost at write time for nothing, and worse, mismatched bucket counts between two "bucketed" tables silently fall back to a full shuffle join anyway.

---

## Interview questions

### Q1 — You see 199 tasks finish in 5 seconds and one task running for 40 minutes. Diagnose it, step by step.
**Testing:** the canonical skew scenario, whether you can name the symptom and reason to cause without prompting.
**Answer:** This is the textbook data-skew fingerprint: one partition (one key, under a hash partitioner) holds a disproportionate share of the data, so its task takes proportionally longer while every other task, handling a fair share, finishes quickly. First step: check the Spark UI's stage detail for that task's shuffle-read size versus the median, confirming it's data volume and not a slow node or GC pause. Then check `explain()` for whether this is a sort-merge join (where AQE skew handling could apply) or a groupBy aggregation (where it can't).
**Follow-up trap:** *"AQE is enabled. Why didn't it fix this?"* — either the skewed partition didn't clear both thresholds (`skewedPartitionFactor` 5x median AND the 256MB absolute floor), or this is a `groupBy`/aggregation, not a sort-merge join, which is outside what AQE's skew-join feature covers. Salting is still needed for aggregation skew.

### Q2 — Explain what `spark.sql.shuffle.partitions=200` actually controls, and why AQE's coalescing is a better default.
**Testing:** whether you understand this as a legacy static knob versus a dynamic target.
**Answer:** It sets the number of reduce partitions for every shuffle in the job, a single static number chosen before execution and applied everywhere regardless of the actual data volume at each shuffle. AQE's `coalescePartitions` feature instead starts from a larger initial partition count and merges adjacent small partitions after seeing real post-shuffle sizes, targeting `advisoryPartitionSizeInBytes` (64MB default) per partition, which adapts automatically per-shuffle within a single job, something a single static config value structurally cannot do.
**Follow-up trap:** *"If AQE handles this, why does the config still exist?"* — it still sets the *initial* number of shuffle partitions before AQE's coalescing kicks in (governed further by `coalescePartitions.initialPartitionNum` if set separately), and it's the fallback behavior if AQE is disabled. It also still matters for the `minPartitionSize` floor AQE respects when coalescing.

### Q3 — Walk through the difference between a broadcast hash join, sort-merge join, and shuffle hash join, and when each is chosen.
**Testing:** baseline join mechanics; the score comes from precision on the thresholds.
**Answer:** Broadcast hash join: one side is under `autoBroadcastJoinThreshold` (10MB default), it's sent whole to every executor, no shuffle needed on either side, fastest option when applicable. Sort-merge join: the default for two large sides on an equi-join, both sides shuffled and sorted by key, then merged, standard and scalable but pays full shuffle cost on both sides. Shuffle hash join: both sides shuffled but not sorted, a hash table built per partition from the smaller side, avoids sort cost but risks OOM if that side is bigger than expected; requires an explicit hint or `preferSortMergeJoin=false` in modern Spark, rarely the automatic default.
**Follow-up trap:** *"What if there's no equality condition at all?"* — broadcast nested loop join, O(n×m) comparisons per partition. Seeing this unintentionally on two large tables is almost always a sign the join condition isn't what was intended, or it's an accidental cross join.

### Q4 — A job's throughput is dominated by a Python UDF. What's your fix and what number do you cite to justify it?
**Testing:** the single highest-leverage optimization in PySpark performance work.
**Answer:** Convert the row-at-a-time `@udf` to a pandas UDF (or Arrow UDF), which transfers data to the Python worker in Arrow columnar batches instead of per-row, letting the function operate vectorized over a `pandas.Series`. Measured improvement is 3x-100x over row-at-a-time UDFs depending on the operation, with the newer Arrow UDFs reporting roughly another 10% on top with ~40% less memory versus pandas UDFs by skipping the pandas materialization step.
**Follow-up trap:** *"What if the UDF logic isn't vectorizable, e.g. it calls an external API per row?"* — a pandas UDF still helps by batching the I/O (call the API once per batch if the API supports batch requests, or at minimum reduce serialization overhead per call), but if the logic is inherently sequential/row-dependent, the vectorization win is smaller; the real fix there is reducing round trips (batch the external calls) rather than expecting UDF-type-alone to solve it.

### Q5 — When does caching a DataFrame make a job slower, concretely?
**Testing:** whether "cache more" is a reflex or a judgment call.
**Answer:** Three concrete cases: (1) the cached DataFrame is consumed only once downstream, so you pay materialization and storage cost for zero reuse; (2) the cache evicts a different DataFrame that was actually being reused multiple times, forcing that one to recompute from lineage, a net loss; (3) caching happens before a filter that would have shrunk the data significantly, so far more is held in memory/disk than necessary. In all three, the fix is removing the cache or moving it to after the filter, verified against the Storage tab's actual reuse count, not assumed.
**Follow-up trap:** *"You added .cache() and the job got slower. Why might that be, mechanically, not just 'unnecessary caching'?"* — under memory pressure, the cache write itself can force eviction of storage or contend with execution memory (the Unified Memory Manager lets execution reclaim storage space, and heavy caching can increase spill for concurrent execution-memory-hungry operators like large sorts or aggregations), so the cost isn't just "wasted," it can actively starve unrelated operators in the same job.

### Q6 — Derive `autoBroadcastJoinThreshold`'s default and explain why it's conservative rather than aggressive.
**Testing:** whether you understand the risk profile behind a specific number, not just the number.
**Answer:** Default is 10MB. It's conservative because a broadcast join materializes the entire "small" side in the driver first (to build the broadcast variable) and then pushes a full copy to every executor's memory; if the "small" side is actually large due to a bad or stale size estimate, this risks driver OOM during collection or executor OOM when every executor tries to hold a copy simultaneously, a failure mode with a worse blast radius than a slow sort-merge join. A small conservative default limits how wrong a stale-statistics bet can be.
**Follow-up trap:** *"When would you deliberately raise it to, say, 200MB?"* — for a cluster with generous executor memory, dimension tables reliably under a few hundred MB, and, critically, statistics you trust (recent `ANALYZE TABLE` runs), raising it converts a good fraction of your sort-merge joins to broadcasts for a real speedup. Doing it without trustworthy statistics is how you turn a slow-but-safe job into an OOM incident.

### Q7 — Explain executor memory layout: where does `spark.executor.memoryOverhead` come from and why does it matter specifically for PySpark?
**Testing:** memory model depth beyond "give it more RAM."
**Answer:** `spark.executor.memory` sets the JVM heap size for the executor; `spark.memory.fraction` (default 0.6) of that heap is the Unified Memory region split between execution and storage (`storageFraction`, default 0.5, as the soft boundary, execution can evict storage under pressure). `memoryOverhead` (default 10% of executor memory, minimum 384MB) is separate, off-heap budget for JVM internals, native libraries, and any off-heap allocations. For PySpark specifically, the actual Python worker process(es) spawned per executor run entirely outside the JVM heap and are effectively budgeted against this overhead (or a dedicated `spark.executor.pyspark.memory` setting where configured); undersizing overhead on a UDF-heavy PySpark job is a common, non-obvious OOM cause because the JVM heap metrics look fine while the Python process is what's actually starved.
**Follow-up trap:** *"Your executor OOMs but heap usage graphs show plenty of headroom. What do you check next?"* — off-heap/overhead memory, specifically Python worker process memory for PySpark UDF-heavy jobs, since JVM heap monitoring won't show it at all; this is exactly the scenario `memoryOverhead` under-provisioning produces.

### Q8 — What's the difference between spill and OOM, and is spill itself a problem?
**Testing:** whether you conflate "using disk" with "failing."
**Answer:** Spill is a deliberate, supported behavior: an operator (sort, aggregate, some join implementations) that exceeds its allotted execution memory writes intermediate state to local disk and merges later, trading time for staying within memory bounds. OOM is the operator or the JVM having no such fallback available (data structure doesn't support spilling, like the in-memory broadcast build side) or the disk-based fallback itself being exhausted. Spill alone isn't a bug; heavy spill on a job that used to run cleanly is a signal (data growth, or a new skew) worth investigating, but shows up as slower runtime, not failure.
**Follow-up trap:** *"Give an operator that can't spill and OOMs instead."* — the broadcast build side: materializing the broadcast variable is an in-memory operation by design (that's the entire point of broadcasting), so if the "small" side turns out too large, there's no spill fallback, it's a hard OOM on the driver or executors building/receiving the broadcast.

### Q9 — Design a bucketing strategy and explain when it pays off versus when it's wasted effort.
**Testing:** whether you understand bucketing as a write-time investment against a specific future access pattern, not a general "best practice."
**Answer:** Bucket both tables that will be repeatedly joined on the same column by that column, with the same bucket count, e.g. `df.write.bucketBy(50, "user_id")`. This front-loads the shuffle cost to write time; every subsequent join on `user_id` between these two bucketed tables can skip the shuffle (and potentially the sort) at read time, a big win if that join happens many times against data that doesn't change often. It's wasted effort, actually a net loss, if the join pattern changes (different key, or one side no longer bucketed identically), because mismatched bucket counts or columns silently fall back to a full shuffle join, and you've paid the write-time cost for nothing.
**Follow-up trap:** *"How does this interact with Iceberg or Delta tables?"* — those table formats have their own, generally preferred mechanisms for similar goals (Iceberg's hidden partitioning, sort-order/clustering via z-ordering or Hilbert curves via `OPTIMIZE`), and classic Hive-style bucketing is less commonly used directly on top of them; know that the concept (pre-arranging data to avoid future shuffles) persists even where the specific mechanism (`bucketBy`) doesn't apply.

### Q10 — You raise executor count 3x and the job barely improves. What do you check before concluding "Spark doesn't scale for this workload"?
**Testing:** the anti-pattern this whole module exists to prevent, staff-level systems reasoning.
**Answer:** First check for skew: adding executors doesn't help if one task is still bottlenecked on one oversized partition, since that single task's wall-clock time is bounded by its own data volume regardless of how many idle executors exist elsewhere. Second, check whether the bottleneck is actually a serial section (driver-side collection, a single broadcast build, a small number of output partitions on write) that more executors can't parallelize. Third, check for UDF-bound stages, where the bottleneck is Python interpreter throughput per core, not available cores, more executors just means more idle cores waiting on the same per-row Python overhead pattern.
**Follow-up trap:** *"So when does adding executors actually help?"* — when the job is genuinely partition-parallel-bound: enough well-distributed partitions, no oversized broadcast/collect step, and the existing executors were actually saturated (check CPU utilization in the UI, not just task count) rather than waiting on I/O, a shuffle fetch, or a skewed sibling task.

---

## Red flags that fail you

- Recommending manual salting without first checking whether AQE's skew-join handling already covers the case.
- Saying "add more executors" as a first response to a slow job without checking for skew.
- Not knowing pandas/Arrow UDFs exist, or treating all UDFs as equally costly.
- Recommending `.cache()` without checking actual reuse via the Storage tab.
- Raising `autoBroadcastJoinThreshold` without mentioning table statistics.
- Confusing spill (normal, disk-backed fallback) with OOM (hard failure).
- Not knowing AQE only re-plans at shuffle boundaries, and only for the DataFrame/SQL API, not RDDs.

---

## Cheat card

```
SHUFFLE COST = disk (write+read local files) + network (fetch across nodes)
  + serialization, on every wide transform. Narrow transforms: none of this.

SKEW SYMPTOM: 199 tasks in seconds, 1 task 40 min. Check shuffle-read size
  outlier in Spark UI to confirm data volume, not a slow node.
SKEW FIXES (in order of automation):
  1. AQE skew-join split (sort-merge joins only; auto since it's part of AQE)
  2. Broadcast the small side (removes shuffle+skew entirely)
  3. Salt manually (groupBy skew, non-equi joins -- what AQE can't reach)
  4. Isolate hot key, process separately, union back

AQE default ON since Spark 3.2.0. Re-plans ONLY at shuffle boundaries,
  ONLY for DataFrame/SQL (not RDD). Three things:
  - coalescePartitions: merge small post-shuffle partitions -> target
    advisoryPartitionSizeInBytes (default 64MB)
  - switch join strategy to broadcast if runtime size proves it's small
  - skewJoin.enabled: split partition if > skewedPartitionFactor (5x median)
    AND > skewedPartitionThresholdInBytes (256MB)

JOIN STRATEGY: broadcast hash (< autoBroadcastJoinThreshold, default 10MB,
  no shuffle) > sort-merge (default, both sides shuffled+sorted) >
  shuffle hash (hinted, no sort, OOM risk) > broadcast nested loop
  (no equi condition -- O(n*m), usually a bug if unintentional)

CACHE = persist(MEMORY_AND_DISK) [PySpark/DF default]. Slower when: used
  once, evicts something more valuable, cached before a filter that
  shrinks data. Verify reuse in Spark UI Storage tab before trusting it.

UDF COST: row-at-a-time Python UDF = per-row JVM<->Python serialization
  + optimization barrier. pandas/Arrow UDF = Arrow columnar batches =
  3x-100x faster. Arrow UDF (newer) ~10% faster, ~40% less memory than
  pandas UDF (skips pandas/NumPy materialization).

MEMORY: executor heap * memory.fraction (0.6 default) = Unified region,
  split execution/storage by storageFraction (0.5 default, soft boundary,
  execution can evict storage). memoryOverhead = 10% of executor memory,
  min 384MB, off-heap -- this is where PySpark's Python worker process
  memory effectively lives; JVM heap graphs won't show it starving.

SPILL (disk-backed fallback, normal) != OOM (no fallback available, e.g.
  broadcast build side can't spill).

BUCKETING: pre-shuffle at write time (bucketBy) so future joins on that
  key skip the shuffle -- pays off only if the join pattern is stable;
  mismatched bucket count/column silently falls back to full shuffle.
```

## Sources

- [Performance Tuning (AQE) — Spark 3.2.0 Documentation](https://downloads.apache.org/spark/docs/3.2.0/sql-performance-tuning.html) — accessed 2026-08-01
- [Performance Tuning — Spark 4.2.0 Documentation](https://spark.apache.org/docs/latest/sql-performance-tuning.html) — accessed 2026-08-01
- [Broadcast Joins (aka Map-Side Joins) — The Internals of Spark SQL](https://jaceklaskowski.gitbooks.io/mastering-spark-sql/content/spark-sql-joins-broadcast.html) — accessed 2026-08-01
- [Introducing Arrow UDFs in PySpark: A Faster, Leaner Replacement for Pandas UDFs — Databricks Blog](https://www.databricks.com/blog/introducing-arrow-udfs-pyspark-faster-leaner-replacement-pandas-udfs) — accessed 2026-08-01
- [Everything You Ever Wanted to Know about Pandas / PyArrow UDFs in Apache Spark — Databricksters](https://www.databricksters.com/p/everything-you-ever-wanted-to-know) — accessed 2026-08-01
- [Spark Memory Management and its types — Medium](https://medium.com/@vtrkayalrajan/spark-memory-management-and-its-types-425af52d7c15) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
