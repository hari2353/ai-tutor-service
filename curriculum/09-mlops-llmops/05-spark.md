# Spark/PySpark Tuning: Shuffle, Skew, AQE, Broadcast, EMR Packaging

> **Track:** T09 MLOps / LLMOps · **Time:** 3h · **Prereqs:** none
> **Module id:** `T09-spark` · **Tags:** spark,pyspark,emr,performance,critical

## The 30-second version

A shuffle is the single most expensive operation in Spark — it serializes data, writes it to local disk on every executor, transfers it across the network to whichever executor owns the destination partition, and deserializes it again, and any join or aggregation whose keys aren't already co-located triggers one. Data skew — one or a handful of partition keys holding disproportionately more rows or bytes than the rest — turns a distributed job into a job bottlenecked by its single slowest task, because Spark's stage doesn't complete until every task in it does; the fix is either salting the skewed key (splitting it into N synthetic sub-keys to spread the load) or letting Adaptive Query Execution's skew-join optimization split an oversized shuffle partition automatically once it's flagged as skewed (default: a partition is skewed if it's over 256MB **and** more than 5x the median partition size). AQE, enabled by default since Spark 3.2 (`spark.sql.adaptive.enabled=true`), re-optimizes the query plan mid-execution using actual runtime statistics instead of only the pre-execution estimate: it coalesces too-many-small post-shuffle partitions toward a 64MB advisory target, converts a sort-merge join to a broadcast join if runtime stats show one side is actually small enough, and splits skewed partitions automatically — a real, load-bearing improvement over Spark's pre-3.0 static-plan-only behavior, though it does not eliminate the value of understanding shuffle and skew by hand, because AQE only kicks in once a stage boundary is hit and can't retroactively fix a badly-chosen partitioning strategy upstream of that boundary. Broadcast joins avoid a shuffle entirely by sending a small table's full contents to every executor (default threshold `spark.sql.autoBroadcastJoinThreshold` = 10MB, comparing the estimated/runtime size of the smaller side), and they backfire specifically when the "small" table's actual runtime size is underestimated by stale statistics, driving executors to OOM trying to hold a broadcast that turns out to be gigabytes, not megabytes. On EMR specifically, the real operational surface is bootstrap actions (shell scripts run on every node at cluster launch, before YARN/Spark are up, for OS-level dependencies pip/conda alone can't satisfy), dependency packaging (a `venv`/conda-pack archive or a custom AMI, not `pip install` at runtime, because production clusters shouldn't reach the internet mid-job), and cluster sizing that has to account for YARN's own overhead (`yarn.nodemanager.resource.memory-mb` isn't the full instance RAM) on top of Spark executor memory, not just executor-core-count arithmetic in isolation.

## Why this gets asked

The interviewer has personally watched a Spark job go from a 40-minute nightly ETL run to a 6-hour, cluster-melting incident because one join key was skewed 200:1 and nobody noticed until the driver's event log showed 199 tasks finishing in 90 seconds and one task still running three hours later. They've also debugged a broadcast join that looked like a free performance win in dev (a 2MB lookup table) and OOM'd production executors because the "same" table had grown to 4GB by the time the job ran against real data, with the broadcast threshold's underlying size estimate stale relative to actual runtime size. They want concrete, numeric fluency — shuffle partition counts, skew thresholds, broadcast defaults — not a conceptual gesture at "distributed computing is hard," and at senior/staff level they want to hear you reason about *why* a specific symptom (one long-tail task, an executor OOM, a job that scales linearly with data volume until it suddenly doesn't) points to a specific mechanical cause, the way you'd debug it live against a Spark UI.

---

## Lineage: past → present → future

**What came before.** Hadoop MapReduce (2006-era) forced every intermediate result to disk between the map and reduce phases, and every multi-stage pipeline meant writing to HDFS and reading it back for the next job — correct, but brutally slow for anything iterative (machine learning training loops, graph algorithms) because each iteration paid the full disk I/O cost of the previous stage's output. Spark (UC Berkeley AMPLab, 2009; Apache project, 2014) was built specifically to fix this: keep intermediate data in memory across stages via the RDD abstraction (Resilient Distributed Datasets, tracking lineage so lost partitions could be recomputed rather than needing replication), trading MapReduce's guaranteed-durable-to-disk-every-stage model for an order-of-magnitude speedup on iterative and interactive workloads at the cost of needing enough cluster memory to actually hold working data. Early Spark (1.x) query optimization was static and pre-execution-only: the Catalyst optimizer built a plan from pre-execution statistics (table sizes, if `ANALYZE TABLE` had been run) and executed it as planned, with no mechanism to adjust mid-execution if those estimates turned out wrong — a job whose actual runtime data distribution diverged from its pre-execution estimate (extremely common with skewed real-world data, or with statistics that were stale or never collected) simply ran the suboptimal plan to completion.

**Where it stands now.** Adaptive Query Execution (AQE), introduced in Spark 3.0 and **enabled by default since Spark 3.2.0**, is the current, unambiguous consensus fix for static-plan brittleness: it re-optimizes using actual runtime shuffle statistics rather than only pre-execution estimates, coalescing small post-shuffle partitions toward an advisory 64MB target, converting a sort-merge join to a broadcast join when runtime stats reveal one side is actually small enough, and splitting skewed shuffle partitions automatically [Performance Tuning — Apache Spark 4.2.0 Documentation](https://spark.apache.org/docs/latest/sql-performance-tuning.html) — accessed 2026-08-03. This is genuinely settled, load-bearing production behavior now, not an experimental feature — but the live disagreement in practice is how much manual tuning (explicit `.repartition()`, manual salting, explicit broadcast hints) is still worth doing versus trusting AQE fully; experienced practitioners still hand-tune skew and partitioning for genuinely pathological cases (extreme skew ratios, joins AQE's heuristics don't handle well) rather than assuming AQE's defaults are sufficient for every workload, and knowing when AQE's automatic behavior isn't enough is itself a real, current skill gap between mid-level and senior Spark engineers. On managed platforms, **Amazon EMR's latest release (7.13.0) ships Apache Spark 3.5.6** — meaningfully behind the open-source project's latest 4.x line, which is a genuinely relevant, checkable fact: EMR users get AQE's mature 3.2+ behavior but not yet Spark 4.0's newer features (like Storage Partition Join's expanded compatible-transform support), and assuming "whatever's newest in open-source Spark" is what's running on a given production EMR cluster is a real, common mistake [Amazon EMR release 7.13.0 — AWS documentation](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-7130-release.html) — accessed 2026-08-03.

**Where it's heading.** High confidence: AQE's scope keeps expanding (it already covers shuffle-partition coalescing, skew splitting, and join-strategy conversion) as the project keeps discovering more static-plan brittleness cases worth fixing adaptively — this direction is well-established and unlikely to reverse. Medium confidence: Storage Partition Join (avoiding shuffle entirely by exploiting a data source's existing partitioning/bucketing layout, expanded significantly in Spark 4.0 with compatible-transform support) is a growing area of investment, particularly relevant as more workloads move to Iceberg/Delta-style partitioned table formats where the storage layer itself can carry co-partitioning information the query engine can exploit — but this remains a smaller share of real production joins than AQE-covered shuffle joins today. Speculative: continued convergence between Spark's batch and streaming execution models (Structured Streaming's micro-batch engine already shares much of the SQL engine's optimizer) and increasing GPU-accelerated execution paths for specific workloads (vectorized execution, columnar formats) as data volumes and cost pressure keep pushing performance-per-dollar as a first-class optimization target, not just correctness.

---

## Mental model

```
SHUFFLE: the expensive operation everything else exists to avoid or minimize

  Stage 1 (map-side)              SHUFFLE (disk write, network            Stage 2 (reduce-side)
  executor A: partition 1  --\      transfer, disk read)                  executor A: reads its
  executor B: partition 2  ---\--> [shuffle files written to local  -->    assigned partition(s)
  executor C: partition 3  ----\    disk on EACH source executor,          from wherever they
                                \    then FETCHED over the network        physically landed
                                     by whichever executor owns the
                                     DESTINATION partition]

  Triggered by: any join/groupBy/aggregation whose relevant keys
  aren't ALREADY co-located on the same partition.
  Cost: serialize -> disk write -> network transfer -> disk read ->
  deserialize, PER SHUFFLE, for every byte that crosses partition
  boundaries. This is what "shuffle is expensive" actually MEANS.

SKEW: one task becomes the whole job's critical path

  Stage completes only when EVERY task in it completes.
  199 tasks: 90 seconds each.  1 task (skewed key): 3 hours.
  STAGE DURATION = 3 HOURS, not 90 seconds -- the other 199 executors
  sit idle waiting on the one straggler.

  AQE default skew detection: a partition is SKEWED if
    size > 256MB   AND   size > 5x the MEDIAN partition size
  (spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes = 256MB,
   spark.sql.adaptive.skewJoin.skewedPartitionFactor = 5.0)

BROADCAST JOIN: skip the shuffle entirely for a SMALL side

  Normal join: BOTH sides shuffled so matching keys co-locate.
  Broadcast join: the SMALL side's FULL data is copied to EVERY
    executor -- the LARGE side is never shuffled at all, each
    executor just joins its local large-side partition against
    the full small-side copy it now holds in memory.
  Default threshold: spark.sql.autoBroadcastJoinThreshold = 10MB
  (compares the SMALLER side's estimated or runtime size against this)
  BACKFIRES when: the "small" table's ACTUAL size is underestimated
  (stale stats) -- broadcasting a table that's actually gigabytes,
  not megabytes, OOMs every executor trying to hold the full copy.

AQE (default ON since Spark 3.2.0): re-optimizes using RUNTIME stats,
  not just pre-execution estimates
  - coalesces too-many-small shuffle partitions toward 64MB advisory size
  - converts sort-merge join -> broadcast join if RUNTIME stats show
    one side is actually small enough
  - splits SKEWED partitions automatically (the 256MB/5x rule above)
  KICKS IN AT STAGE BOUNDARIES ONLY -- can't retroactively fix a bad
  upstream partitioning choice before the first shuffle boundary.
```

---

## How it actually works

### Shuffle: the concrete mechanical cost, and why `spark.sql.shuffle.partitions` matters

Every shuffle writes intermediate data to local disk on each source executor (shuffle write), then each destination executor fetches its assigned partition(s) over the network from wherever they landed (shuffle read), then deserializes. This is fundamentally different from Spark's in-memory RDD lineage advantage over MapReduce — a shuffle boundary is exactly the place where Spark still pays real disk and network I/O, and minimizing the number and size of shuffles is the single highest-leverage Spark performance lever that exists.

`spark.sql.shuffle.partitions` (default **200**, unchanged since Spark 1.1.0) controls how many partitions a shuffle produces — a number picked once, globally, with no awareness of actual data volume. This is the concrete reason the default is frequently wrong in both directions: **too few partitions** for a genuinely large shuffle means each partition is huge, slow to process, and risks executor OOM; **too many partitions** for a genuinely small shuffle means enormous per-task scheduling overhead relative to the tiny amount of actual work each task does — a job processing a few GB with 200 shuffle partitions might spend more wall-clock time on task scheduling overhead than actual computation. AQE's `coalescePartitions` feature (on by default alongside AQE itself) is the direct fix for the too-many-small-partitions case, coalescing contiguous shuffle partitions toward `spark.sql.adaptive.advisoryPartitionSizeInBytes` (default **64MB**) — which is why, on a modern AQE-enabled cluster, manually tuning `spark.sql.shuffle.partitions` down for a small job matters far less than it used to on Spark 1.x/2.x, though setting a sufficiently large *initial* partition count (`spark.sql.adaptive.coalescePartitions.initialPartitionNum`) still matters for AQE to have enough granularity to coalesce intelligently in the first place [Performance Tuning — Apache Spark 4.2.0 Documentation](https://spark.apache.org/docs/latest/sql-performance-tuning.html) — accessed 2026-08-03.

### Diagnosing and fixing skew: salting, and AQE's automatic handling

**The symptom, precisely**: in the Spark UI's stage view, a stage's task duration distribution shows the overwhelming majority of tasks finishing quickly and clustered together, with one or a handful of outlier tasks taking dramatically longer — the stage's *total* duration is bounded by the slowest task, not the median, because a stage only completes once every task in it does. This is distinguishable from generic slowness (all tasks uniformly slow, pointing to genuinely large data volume or under-provisioned executors) precisely by that distribution shape.

**AQE's automatic fix** (`spark.sql.adaptive.skewJoin.enabled`, default true): a shuffle partition is flagged skewed if its size exceeds **256MB** (`skewedPartitionThresholdInBytes`) **and** exceeds **5x the median partition size** (`skewedPartitionFactor`) — both conditions, not either alone, because a 256MB partition in a stage where the median is also 200MB isn't meaningfully skewed, and a partition 10x the median but only 2MB in absolute terms isn't worth the overhead of splitting. When flagged, AQE splits the oversized partition into smaller sub-partitions (and replicates the join partner side as needed) automatically, with no code change required — a genuine, load-bearing improvement over hand-rolled salting for the common case.

**Manual salting**, still necessary when AQE's heuristics don't cover the specific case (skew below the 256MB/5x threshold combination but still bad enough to matter at your specific scale, or a groupBy/aggregation shape AQE's skew-join optimization doesn't target the same way it targets joins):

```python
# untested sketch — salting a skewed join key
from pyspark.sql import functions as F

SALT_BUCKETS = 20

# the skewed side: split each skewed key into N synthetic sub-keys
skewed_df = skewed_df.withColumn(
    "salted_key",
    F.concat(F.col("join_key"), F.lit("_"), (F.rand() * SALT_BUCKETS).cast("int"))
)

# the other side: explode each row into N copies, one per possible salt value,
# so every salted sub-key on the skewed side still finds its match
salt_range = spark.range(SALT_BUCKETS).withColumnRenamed("id", "salt")
other_df = other_df.crossJoin(salt_range).withColumn(
    "salted_key", F.concat(F.col("join_key"), F.lit("_"), F.col("salt"))
)

result = skewed_df.join(other_df, on="salted_key")
```

The mechanical effect: a single skewed key that would have landed entirely on one shuffle partition is now spread across `SALT_BUCKETS` distinct partitions, each handled by a different task — trading one enormous straggler task for `SALT_BUCKETS` moderately-sized tasks that actually parallelize. The cost: the non-skewed side pays a real `crossJoin`-driven data volume increase (multiplied by `SALT_BUCKETS`), which is why salting is a targeted fix applied to specifically-identified skewed keys, not a blanket strategy applied to every join.

### Broadcast joins: the threshold, and the specific way they backfire

`spark.sql.autoBroadcastJoinThreshold` (default **10MB**, `10485760` bytes) is the size below which Spark will automatically broadcast a join side without an explicit hint — comparing this against either a table's known statistics (if `ANALYZE TABLE` has been run, or metadata Spark can read directly from the data source) or, with AQE, the actual runtime size once available. Below this threshold, Spark sends the *entire* smaller table to *every* executor, letting each executor complete the join against its local large-side partition with zero shuffle needed for that join — a substantial win when it's correctly applied, since it eliminates the shuffle cost entirely for that operation.

**The specific, checkable failure mode**: the threshold check depends on Spark's *estimate* of the smaller side's size, and that estimate can be wrong in a way that isn't obvious until production — a table that was 2MB in a dev/staging dataset can grow to gigabytes in production without anyone updating the size assumption, and if stale catalog statistics (from a stale `ANALYZE TABLE` run) still report the small dev-era size, Spark can broadcast a genuinely enormous table, attempting to copy it in full to every executor and OOM-ing them all simultaneously — a distinctive failure signature (many/all executors failing near-simultaneously with OOM, rather than one straggler task) that immediately points at broadcast, not skew.

**Explicit broadcast hints** (`.hint("broadcast")` or the `/*+ BROADCAST(t) */` SQL hint) override the size-based auto-detection entirely, prioritized by Spark even if the hinted table's actual size is above the configured threshold — which means an explicit hint written against dev-scale data and never revisited is exactly as dangerous as stale auto-detection statistics, arguably more so, since a hint is a much stronger, harder-to-silently-override signal than an estimate Spark might otherwise reconsider. AQE additionally provides *automatic* sort-merge-to-broadcast conversion mid-execution (`spark.sql.adaptive.autoBroadcastJoinThreshold`, defaulting to the same value as the static threshold) when *runtime* statistics reveal a side is actually small enough — genuinely safer than a hardcoded hint because it reacts to the real data, not a stale assumption, though it only helps if AQE is enabled and the relevant stage hasn't already committed to a shuffle plan before the runtime stats become available.

### EMR packaging and deployment realities

**Bootstrap actions** run as shell scripts on every node at cluster launch, *before* Hadoop/YARN/Spark daemons start — this timing matters concretely: bootstrap actions are the right place for OS-level package installation (`yum`/`apt` dependencies a Python package needs at the C-library level, not just the Python package itself) and are the wrong place for anything that depends on Spark/YARN already being up. A bootstrap action failing on even one node can fail cluster provisioning entirely, or (worse, and harder to detect) silently leave that one node inconsistent with the rest of the fleet if the failure isn't configured to be fatal — a real, checkable production risk if bootstrap scripts aren't written to fail loudly and are idempotent enough to be safely retried.

**Dependency packaging**: production Spark clusters should not run `pip install` at job-submission time or reach out to PyPI mid-job — that's a real reliability and reproducibility risk (a package version silently changing between runs, a transient network failure taking down job submission, a private registry outage blocking all jobs). The production pattern is packaging a full, pinned Python environment ahead of time — a `venv-pack` or `conda-pack` archive shipped alongside the job and distributed to executors via `spark-submit --archives`, or building a custom EMR AMI with dependencies baked in at the image level — so every executor runs from an identical, pre-validated environment with zero runtime network dependency on an external package index.

**Cluster sizing**: a common, checkable mistake is sizing Spark executors purely from instance vCPU/RAM without accounting for YARN's own resource-management overhead. `yarn.nodemanager.resource.memory-mb` (the memory YARN considers available for containers on a node) is not the full instance RAM — some must be reserved for the OS and YARN's own daemons, and EMR's default configurations already account for this per instance type, but a manually-overridden executor memory/core configuration that ignores this reservation can request more from YARN than the node can actually grant, producing container allocation failures or, worse, an executor that gets allocated but then gets killed by YARN for exceeding its granted container's memory limit under real load — a distinct, specific "container killed by YARN" failure signature in application logs versus a plain Spark-level OOM, worth being able to tell apart when triaging a cluster incident.

---

## Build it from scratch

A minimal PySpark job demonstrating deliberate skew diagnosis and the salting fix, runnable against a local Spark session to see the mechanics directly:

```python
# untested sketch — reproducing and fixing skew locally
from pyspark.sql import SparkSession, functions as F
import random

spark = SparkSession.builder.appName("skew-demo").getOrCreate()

# deliberately skewed data: key "0" appears in 90% of rows
skewed_data = [(str(0 if random.random() < 0.9 else random.randint(1, 99)), i)
               for i in range(1_000_000)]
skewed_df = spark.createDataFrame(skewed_data, ["key", "value"])

lookup_data = [(str(k), f"label_{k}") for k in range(100)]
lookup_df = spark.createDataFrame(lookup_data, ["key", "label"])

# UNSALTED join: key "0"'s shuffle partition holds ~900K of 1M rows --
# check the Spark UI stage view, one task will dominate the stage duration
naive_result = skewed_df.join(lookup_df, on="key")
naive_result.count()   # trigger execution, inspect the Spark UI

# SALTED join: spread key "0"'s rows across SALT_BUCKETS partitions
SALT_BUCKETS = 20
salted_skewed = skewed_df.withColumn(
    "salted_key", F.concat(F.col("key"), F.lit("_"), (F.rand() * SALT_BUCKETS).cast("int"))
)
salt_range = spark.range(SALT_BUCKETS).withColumnRenamed("id", "salt")
salted_lookup = lookup_df.crossJoin(salt_range).withColumn(
    "salted_key", F.concat(F.col("key"), F.lit("_"), F.col("salt"))
)
salted_result = salted_skewed.join(salted_lookup, on="salted_key")
salted_result.count()   # compare stage task-duration distribution in the UI
```

The point of running both versions side by side: the Spark UI's stage view makes the difference directly visible — the naive join's task-duration histogram shows one dramatic outlier, the salted join's shows a much tighter, more even distribution across `SALT_BUCKETS` tasks, which is the concrete, checkable evidence a real production diagnosis relies on.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A stage's 199 tasks finish in ~90s, one task runs for 3+ hours, stage duration = the straggler's duration | Data skew — one partition key holds disproportionately more data than the rest; the stage doesn't complete until every task does | Check whether AQE's skew-join splitting is enabled and whether the skew clears its 256MB/5x-median thresholds; if it does but AQE still isn't helping, or the skew is below those thresholds but still problematic, apply manual salting to the specific skewed key(s) |
| Many/all executors OOM near-simultaneously, rather than one straggler task running long | A broadcast join is attempting to broadcast a table whose actual runtime size is far larger than assumed — stale catalog statistics or a hardcoded broadcast hint written against dev-scale data | Verify the actual current size of the broadcast candidate; remove a stale explicit hint, re-run `ANALYZE TABLE` to refresh statistics, or explicitly disable the broadcast (hint override or lowering `autoBroadcastJoinThreshold`) if the table has genuinely outgrown broadcast-appropriate size |
| A job that scales roughly linearly with data volume suddenly falls off a cliff in performance past a certain size | `spark.sql.shuffle.partitions`'s fixed default (200) becomes badly undersized once shuffle data volume crosses a threshold where 200 giant partitions can't fit comfortably in executor memory | Increase the initial shuffle partition count for genuinely large shuffles, or verify AQE's `coalescePartitions` is enabled and configured with a large enough `initialPartitionNum` to give it granularity to work with |
| A small job with only a few GB of data takes an oddly long time relative to its actual data volume | Excessive shuffle partition count (still defaulting toward 200) creates enormous per-task scheduling overhead relative to the tiny amount of real work each task does | Confirm AQE's `coalescePartitions` (on by default) is actually engaging — check the Spark UI's actual post-coalesce partition count against the advisory 64MB target; if AQE is disabled for some reason, explicitly lower `spark.sql.shuffle.partitions` for small jobs |
| A bootstrap action succeeds on 9 of 10 nodes but the 10th silently has a missing OS-level dependency, causing sporadic task failures only on that node | Bootstrap script isn't written to fail loudly/fatally on error, or isn't idempotent/retried correctly, leaving one node's environment inconsistent with the rest of the fleet | Write bootstrap actions to exit non-zero on any real failure (so cluster provisioning itself fails visibly rather than silently proceeding with an inconsistent node), and make them idempotent so a retry is always safe |
| A job that runs fine locally fails in production with intermittent package-version-related errors, or fails entirely during a transient network blip at job submission | Runtime `pip install` (or reaching PyPI mid-job) instead of a pre-packaged, pinned environment | Package a full pinned environment ahead of time (venv-pack/conda-pack archive shipped via `spark-submit --archives`, or a custom AMI with dependencies baked in) so every executor runs an identical, network-independent environment |
| Executors get allocated by YARN but are later killed mid-job, distinct from a plain Spark-level OOM in the logs | Executor memory/core configuration was set without accounting for YARN's `yarn.nodemanager.resource.memory-mb` reservation (not the full instance RAM) — requesting more from YARN than a node can actually grant under real load | Size executor memory/cores against the actual YARN-available memory per node type, not raw instance specs; check for the specific "container killed by YARN for exceeding memory limits" log signature versus a plain Spark OOM to correctly diagnose which layer failed |

---

## Tradeoffs & when NOT to use it

- **Don't apply manual salting reflexively to every join.** It's a targeted fix for a specifically-identified skewed key, and applying it broadly (or to a join that isn't actually skewed) adds real overhead — the `crossJoin`-driven data volume increase on the non-skewed side is a genuine cost, not free insurance.
- **Don't broadcast a table just because it was small in dev.** Verify actual current production-scale size before relying on either an explicit hint or auto-detection; a stale assumption here produces one of the most distinctive and painful Spark production failures (simultaneous executor OOM across the whole cluster).
- **Don't disable AQE reflexively because "we tune manually."** AQE's defaults (skew splitting, partition coalescing, broadcast conversion) solve the majority of common cases with zero code change; manual tuning should supplement AQE for the specific cases its heuristics don't cover, not replace it wholesale.
- **Don't assume EMR is running the latest open-source Spark release.** EMR's latest release (7.13.0, as of this writing) ships Spark 3.5.6, meaningfully behind the open-source project's 4.x line — verify the actual Spark version on your specific EMR release before assuming a newer feature (like expanded Storage Partition Join support) is available.
- **Don't install dependencies via `pip install` at job-submission or runtime on a production EMR cluster.** It's a reliability and reproducibility risk; package a pinned environment ahead of time instead.
- **Don't size Spark executors from raw instance vCPU/RAM alone.** YARN's own memory reservation (`yarn.nodemanager.resource.memory-mb`) isn't the full instance RAM, and ignoring this produces container allocation failures or executors killed by YARN under real load, a distinct failure mode from a plain Spark OOM.
- **Don't reach for Spark at all for a workload that fits comfortably in a single machine's memory with pandas/DuckDB.** Spark's distributed overhead (shuffle, task scheduling, cluster provisioning) is real cost that only pays off once the workload genuinely exceeds single-machine capacity — a small dataset processed via Spark purely out of habit is slower and more operationally complex than it needs to be.

---

## Interview questions

### Q1 — Explain, mechanically, why a shuffle is expensive.
**Testing:** whether the candidate can describe the actual I/O path, not just assert "shuffles are slow."
**Answer:** A shuffle writes intermediate data to local disk on every source executor (shuffle write), transfers it over the network to whichever executor owns the destination partition (shuffle read), and deserializes it there — serialize, disk write, network transfer, disk read, deserialize, for every byte crossing a partition boundary. This is the concrete cost any join or aggregation whose relevant keys aren't already co-located pays, and it's the specific I/O Spark's in-memory RDD model doesn't eliminate the way it eliminates inter-stage disk writes in MapReduce.
**Follow-up trap:** *"Does keeping everything in memory avoid this cost?"* — no; a shuffle's disk write is to *local* disk on the source executor regardless of overall cluster memory pressure, specifically because shuffle data needs to be durably available for the destination executor to later fetch, potentially after the source task has already finished — it's not the same as RDD caching, and having abundant executor memory doesn't eliminate shuffle's disk-and-network cost.

### Q2 — What are the two conditions AQE uses to flag a shuffle partition as skewed, and why both, not either alone?
**Testing:** precise, numeric knowledge of the actual default thresholds.
**Answer:** A partition is flagged skewed if its size exceeds 256MB (`skewedPartitionThresholdInBytes`) **and** exceeds 5x the median partition size (`skewedPartitionFactor`) — both conditions required. The absolute threshold alone would flag a 256MB partition even in a stage where every partition happens to be around 256MB (not meaningfully skewed relative to its peers); the relative threshold alone would flag a partition 10x the median even if that median and the "skewed" partition are both trivially small in absolute terms, not worth the overhead of splitting.
**Follow-up trap:** *"A partition is 300MB and the median is 40MB — a 7.5x ratio, both thresholds cleared. Does AQE definitely split it?"* — provided `spark.sql.adaptive.skewJoin.enabled` (default true) and AQE itself are enabled, yes, this partition clears both thresholds and AQE's skew-join optimization will split it — but this only applies to sort-merge join skew handling specifically; the same skew in a plain `groupBy` aggregation (not a join) isn't covered by this exact mechanism, which is a distinction worth stating precisely rather than assuming AQE's skew handling is universal across all shuffle operations.

### Q3 — What's the default broadcast join threshold, and what's the specific mechanism by which broadcast joins backfire in production?
**Testing:** numeric precision plus the actual failure mechanism.
**Answer:** `spark.sql.autoBroadcastJoinThreshold` defaults to 10MB (10,485,760 bytes), compared against the estimated or (with AQE) runtime size of the smaller join side. It backfires when the actual runtime size of the "small" side is underestimated — stale catalog statistics from an old `ANALYZE TABLE` run, or a hardcoded explicit broadcast hint written when the table was genuinely small in dev — causing Spark to attempt broadcasting a table that's actually gigabytes, which OOMs every executor trying to hold the full copy simultaneously, rather than the single-straggler-task signature of skew.
**Follow-up trap:** *"How would you distinguish a broadcast-OOM incident from a skew incident just from the failure pattern, before digging into the plan?"* — broadcast-OOM typically shows many or all executors failing near-simultaneously with OOM errors; skew shows the stage completing (eventually) with a task-duration distribution dominated by one or a few extreme outliers while the rest finish normally — the failure *shape* (simultaneous cluster-wide OOM vs one straggler task) is diagnostic before even opening the query plan.

### Q4 — Explain AQE's role, precisely: what does it fix, and what can it not fix?
**Testing:** whether AQE is understood as a real but bounded improvement, not a total fix for query planning.
**Answer:** AQE re-optimizes using actual runtime shuffle statistics at stage boundaries: coalescing too-many-small post-shuffle partitions toward a 64MB advisory target, converting a sort-merge join to broadcast when runtime stats show a side is small enough, and splitting skewed partitions per the 256MB/5x-median rule. It cannot retroactively fix a partitioning strategy or data layout decision made *before* the first shuffle boundary it can act at — AQE reacts to statistics available once a stage has run, not before any shuffle has happened at all, so a poor upstream partitioning choice (e.g., reading source data in a way that creates pathological skew before Spark ever gets a chance to shuffle it) isn't something AQE alone resolves.
**Follow-up trap:** *"Given AQE handles skew and broadcast conversion automatically, is manual tuning (explicit hints, salting) ever still worth doing on a modern Spark version?"* — yes, for cases AQE's heuristics don't cover well: skew below the 256MB/5x thresholds but still problematic at your specific SLA, `groupBy`-shaped skew not covered by the join-specific skew-join optimization, or genuinely pathological cases where AQE's generic heuristics make a suboptimal choice a human with domain knowledge of the actual data distribution can improve on with an explicit hint.

### Q5 — Design a fix for a nightly ETL job where one customer_id (a large enterprise account) generates 40% of all rows, causing severe join skew against a dimension table.
**Testing:** applying salting concretely to a realistic, named scenario.
**Answer:** Salt the skewed side by appending a random sub-key (`concat(customer_id, '_', rand()*N)`) to spread that single customer_id's rows across N synthetic partitions instead of one; explode the dimension table side with a `crossJoin` against a range of N salt values so every salted sub-key still finds its match. This trades one enormous straggler task for N moderately-sized parallel tasks. Given it's specifically one known, identifiable large account (not diffuse skew across many keys), a simpler alternative worth considering is isolating that one customer_id's rows into a separate, dedicated processing path (filter it out, process it with an explicit broadcast of the dimension table since the dimension table itself is likely small, union the results back) rather than generic salting — often simpler to reason about and verify correct when the skew source is one specific, known key rather than many.
**Follow-up trap:** *"Would you expect AQE's automatic skew-join splitting to already handle this without any manual intervention?"* — potentially, if the resulting shuffle partition for that customer_id clears both the 256MB and 5x-median thresholds — check the Spark UI first before assuming manual salting is even necessary; the manual fix should be reserved for confirmed cases where AQE's automatic handling isn't sufficient (either disabled, below threshold, or a shape AQE's skew-join optimization doesn't cover), not applied reflexively without checking whether the built-in mechanism already resolves it.

### Q6 — Why is `spark.sql.shuffle.partitions` defaulting to 200 a real, checkable production risk, and how does AQE change that risk profile?
**Testing:** understanding a specific, longstanding default's failure modes on both ends of the data-volume spectrum.
**Answer:** 200 is a fixed, data-volume-agnostic number — for a genuinely large shuffle, 200 partitions can each end up enormous, slow to process, and prone to executor memory pressure; for a genuinely small shuffle, 200 partitions creates disproportionate per-task scheduling overhead relative to the tiny amount of actual work per task. AQE's `coalescePartitions` feature (on by default) directly mitigates the too-many-small-partitions case by merging contiguous shuffle partitions toward a 64MB advisory target at runtime, meaningfully reducing how much this default number matters in practice on a modern, AQE-enabled cluster — though a sufficiently large *initial* partition count is still needed for AQE to have enough granularity to coalesce intelligently.
**Follow-up trap:** *"Does AQE's coalescing help with the too-few-partitions-for-a-huge-shuffle case symmetrically?"* — no, coalescing only merges partitions together (fewer, larger); it doesn't split an initially-too-small partition count for a genuinely huge shuffle into more partitions — that's a distinct problem needing either a larger explicit `spark.sql.shuffle.partitions` setting or AQE's separate skew-splitting mechanism if the specific symptom is one oversized skewed partition rather than a uniformly-too-small partition count.

### Q7 — What's the difference between a bootstrap action failure and a "container killed by YARN" failure on EMR, and how do you tell them apart while triaging?
**Testing:** specific EMR operational knowledge, distinguishing two failure layers.
**Answer:** A bootstrap action runs at cluster launch, before YARN/Spark daemons even start, for OS-level dependency installation — its failure shows up as cluster provisioning itself failing (or, worse, silently succeeding with one node left inconsistent if the script doesn't fail loudly), before any Spark job has even been submitted. A "container killed by YARN" failure happens during actual job execution, when an executor's requested memory/cores exceed what `yarn.nodemanager.resource.memory-mb` (not full instance RAM) allows the node to grant, and shows a distinct log signature (YARN's container-killed message) versus a plain Spark-level OOM, which instead shows an executor's own JVM running out of heap during task execution.
**Follow-up trap:** *"If a job is failing intermittently only on specific instance types within a heterogeneous cluster, which of these two would you suspect first?"* — a bootstrap action inconsistency across node types (a script that assumes a specific instance type's OS image or available disk layout and fails silently or behaves differently on a different type) is a strong first suspect for instance-type-specific intermittent failures, since it points to environment inconsistency at the node level rather than a job-execution-time resource sizing issue that would typically be more uniform across instance types of similar spec.

### Q8 — Why should a production EMR job never `pip install` a dependency at job-submission time?
**Testing:** the actual reliability/reproducibility argument, not just "it's slow."
**Answer:** Runtime `pip install` introduces a live dependency on an external package index (PyPI or a private registry) at job-submission time — a transient network failure or registry outage blocks job submission entirely, and a package version that silently changes between two runs (no pin, or a pin resolved differently due to a changed dependency graph) breaks reproducibility, making "why did this job's behavior change with no code change" a real, hard-to-diagnose failure mode. The production fix is a pre-packaged, pinned environment (venv-pack/conda-pack archive shipped via `spark-submit --archives`, or a custom AMI) validated once, ahead of time, with zero runtime network dependency.
**Follow-up trap:** *"What if the team needs to patch a single dependency quickly in response to a security vulnerability?"* — rebuild and re-validate the packaged environment (the venv-pack/conda-pack archive or AMI) with the patched dependency and redeploy it as a new, versioned artifact — the fix is still packaged ahead of time and validated, just on an expedited timeline, rather than reaching for a live runtime `pip install` as a shortcut even under time pressure, since the reliability risk that packaging exists to prevent doesn't go away just because the situation is urgent.

### Q9 — A PySpark job's performance scales roughly linearly with input data volume until a specific size threshold, past which it falls off a cliff. Walk through your diagnosis.
**Testing:** staff-level methodical diagnosis connecting several of the module's concepts.
**Answer:** First check the Spark UI for the specific stage where the cliff appears and look at task duration distribution — a sudden appearance of one or a few extreme-outlier tasks at that data volume (versus previously uniform task durations) points to skew crossing AQE's detection thresholds (or a skew pattern AQE doesn't cover) only becoming severe enough to matter past that volume. If instead *all* tasks in the affected stage slow down roughly uniformly at that volume, suspect a fixed-size resource hitting its limit — executor memory pressure once partition sizes cross a threshold given the fixed `spark.sql.shuffle.partitions` count, or a broadcast join whose "small" side has finally grown past a size where it's still genuinely fast to broadcast, both consistent with a threshold-crossing rather than continuously linear cost.
**Follow-up trap:** *"Assume it's confirmed to be broadcast-related — the broadcast side crossed a size where it's no longer a good broadcast candidate. What's the fix, concretely?"* — either lower `autoBroadcastJoinThreshold` (or remove an explicit broadcast hint) so Spark falls back to a standard shuffle join for that table once it's grown past broadcast-appropriate size, or, if the table's growth is itself unexpected/undesirable, investigate why a table assumed to stay small has grown substantially — sometimes the more useful fix addresses why the "dimension" table stopped being dimension-table-sized in the first place.

### Q10 — Design the EMR cluster sizing and packaging strategy for a nightly PySpark ETL job processing roughly 500GB of Parquet data, needing to complete within a 2-hour SLA window.
**Testing:** synthesizing shuffle/skew/broadcast/EMR-operational knowledge into one coherent production design.
**Answer:** Size executors accounting for YARN's actual available memory per node (`yarn.nodemanager.resource.memory-mb`, not raw instance RAM) rather than naive instance-spec arithmetic, choosing an instance type and count that gives adequate parallelism for 500GB with headroom for skew-driven partition size variance. Confirm AQE is enabled (default since 3.2, verify against the actual EMR release's bundled Spark version, e.g. 3.5.6 on EMR 7.13.0) so skew-splitting and partition-coalescing apply automatically; check whether any known dimension/lookup tables in the job are broadcast-join candidates and verify their *current* production size against `autoBroadcastJoinThreshold` rather than assuming dev-scale size still holds. Package the job's Python dependencies as a pinned, pre-built venv-pack/conda-pack archive shipped via `spark-submit --archives` (no runtime `pip install`), and write any needed bootstrap actions to fail loudly and idempotently. Instrument the job to surface Spark UI stage-level task-duration distributions (or an equivalent metrics export) so a future skew regression is visible from monitoring rather than discovered only when the SLA is missed.
**Follow-up trap:** *"The job meets its SLA in testing but occasionally misses it in production by a wide margin, seemingly at random. What's your first hypothesis?"* — data-dependent skew that varies day to day based on actual production data distribution (a specific customer's activity spike, a batch of unusually large records) rather than a fixed, always-present skew pattern testing against a static sample wouldn't have caught — recommend adding skew monitoring (partition size distribution per run, not just overall job duration) as a standing production signal, since testing against one static dataset can't surface a skew pattern that only manifests under specific, variable real-world data conditions.

---

## Red flags that fail you

- Describing shuffle as generically "slow" without naming the actual disk-write/network-transfer/disk-read/deserialize cost sequence.
- Not knowing AQE's skew detection requires both an absolute size threshold (256MB) and a relative-to-median factor (5x), not either alone.
- Confusing a broadcast-join OOM's failure signature (many/all executors failing near-simultaneously) with skew's failure signature (one straggler task, stage otherwise completes).
- Presenting AQE as a total fix for query planning with no acknowledgment of what it can't retroactively correct (pre-shuffle-boundary partitioning decisions).
- Applying salting as a reflexive default rather than a targeted fix for a confirmed, identified skewed key.
- Assuming EMR runs the latest open-source Spark release rather than checking the specific EMR release's bundled version.
- Recommending runtime `pip install` on a production cluster instead of a pre-packaged, pinned environment.
- Not knowing that YARN's available memory per node isn't the full instance RAM, or being unable to distinguish a YARN-container-killed failure from a plain Spark OOM.

---

## Cheat card

```
SHUFFLE COST: serialize -> LOCAL DISK write (source executor) -> NETWORK
  transfer -> disk read (dest executor) -> deserialize. Triggered by any
  join/groupBy/agg whose keys aren't already co-located.

spark.sql.shuffle.partitions: default 200 (fixed since Spark 1.1.0,
  data-volume-agnostic) -- too few = huge partitions/OOM risk on big
  shuffles; too many = scheduling overhead swamps tiny jobs.

AQE (default ON since Spark 3.2.0, spark.sql.adaptive.enabled=true):
  re-optimizes using RUNTIME stats at stage boundaries
  - coalescePartitions: merges small partitions toward 64MB advisory
    size (spark.sql.adaptive.advisoryPartitionSizeInBytes)
  - skew-join split: partition flagged skewed if size > 256MB
    (skewedPartitionThresholdInBytes) AND > 5x median
    (skewedPartitionFactor) -- BOTH conditions required
  - sort-merge -> broadcast conversion when runtime stats show a side
    is small enough (autoBroadcastJoinThreshold, same default as static)
  CANNOT fix a bad partitioning decision BEFORE the first shuffle
  boundary it can act at.

SKEW SYMPTOM: stage duration = SLOWEST task's duration (stage only
  completes when ALL tasks do). One/few extreme-outlier tasks, rest
  finish normally = skew signature.
MANUAL FIX (salting): salted_key = concat(key, "_", rand()*N) on
  skewed side; crossJoin other side against a range(N) salt table.
  Trades 1 straggler for N parallel tasks; costs data-volume increase
  on the non-skewed side via crossJoin -- targeted fix, not a default.

BROADCAST JOIN: spark.sql.autoBroadcastJoinThreshold default 10MB
  (10,485,760 bytes). Sends WHOLE small side to EVERY executor, large
  side never shuffled. BACKFIRES: stale stats or a stale hardcoded
  hint underestimate actual size -> broadcasting a multi-GB table ->
  MANY/ALL executors OOM near-simultaneously (distinct signature vs
  skew's single straggler).

EMR REALITIES
  Latest release (7.13.0) ships Spark 3.5.6 -- BEHIND open-source
    Spark's 4.x line. Verify actual bundled version per release,
    don't assume "latest OSS Spark."
  Bootstrap actions: shell scripts, run BEFORE YARN/Spark start --
    OS-level deps only. Must fail LOUDLY + be idempotent.
  Dependency packaging: NEVER pip install at runtime/submission --
    pre-pack pinned venv-pack/conda-pack archive via
    spark-submit --archives, or bake into a custom AMI.
  Cluster sizing: yarn.nodemanager.resource.memory-mb != full instance
    RAM. Ignoring this -> container allocation failures or executors
    KILLED BY YARN (distinct log signature from plain Spark OOM).
```

## Sources
- [Performance Tuning — Apache Spark 4.2.0 Documentation](https://spark.apache.org/docs/latest/sql-performance-tuning.html) — accessed 2026-08-03
- [About Amazon EMR Releases — AWS Documentation](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-release-components.html) — accessed 2026-08-03
- [Amazon EMR release 7.13.0 — AWS Documentation](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-7130-release.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
