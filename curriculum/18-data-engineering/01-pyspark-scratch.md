# PySpark From Scratch: RDD → DataFrame → Catalyst → Tungsten

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-pyspark-scratch` · **Tags:** spark,critical

## The 30-second version

Spark takes a lazy DAG of transformations, splits it into jobs at every action, splits each job into stages at every shuffle boundary, and splits each stage into tasks, one per partition. RDDs give you that DAG but the driver only sees opaque lambdas, so it cannot optimize what it cannot read. DataFrames replace the lambda with a declarative, typed logical plan that Catalyst can analyze, reorder, and prune before a single task runs, and Tungsten then compiles the physical plan into JVM bytecode operating on raw binary rows instead of boxed JVM objects. That combination, plan-level optimization plus codegen execution, is why a DataFrame `groupBy().sum()` beats a hand-written RDD `reduceByKey` even though they express the same computation. If someone asks "why not just use RDDs, they're more flexible", the answer is that flexibility is exactly what kills the optimizer.

## Why this gets asked

Every PySpark job you write compiles down through this stack, and when a job is slow or OOMs, the fix usually lives in one of these layers: a UDF that Catalyst can't see through, a shuffle boundary you didn't know you created, a partition count that doesn't match your data volume. The interviewer has debugged a job where `explain()` showed a `BroadcastNestedLoopJoin` nobody intended, or a stage with 200 tasks each processing 50GB. They're checking whether you can read a physical plan and a DAG, not whether you can recite "RDD stands for Resilient Distributed Dataset."

---

## Lineage: past → present → future

**What came before.** Hadoop MapReduce (2006) forced every computation through disk between the map and reduce phases, and multi-stage jobs (the common case for anything beyond a single aggregation) meant multiple full read-write-read cycles to HDFS. A ten-stage pipeline could mean twenty disk round trips. Spark (Matei Zaharia's 2010 paper, Berkeley AMPLab) fixed exactly this pain: keep intermediate results in memory across stages, and represent the computation as a lineage graph (the RDD) so failed partitions can be recomputed instead of relying on replicated on-disk checkpoints. RDDs were the whole story through Spark 1.x, and they solved the disk-IO problem completely, but by 2015 it was clear they had a second problem: the API was a Scala/Python collection of opaque functions, and the driver had no way to reason about what a `.map(lambda x: ...)` actually computed.

**Where it stands now.** DataFrames and the Catalyst optimizer (Spark 1.3, 2015, "Spark SQL: Relational Data Processing in Spark" — Armbrust et al., SIGMOD 2015) solved the second problem by making the computation declarative: you describe *what* you want, Catalyst decides *how*. Tungsten (introduced alongside, matured through Spark 2.x) attacked a third problem the paper didn't fully address: even an optimized plan run through the JVM's object model pays for boxing, virtual dispatch per row, and GC pressure from millions of small objects. Tungsten's off-heap binary format and whole-stage code generation removed that tax. The live disagreement today isn't RDD-vs-DataFrame, that's settled, it's how much of the remaining "escape hatches" (Python UDFs, `.rdd` conversions, `foreachPartition`) a team tolerates, because each one reintroduces the exact opacity problem DataFrames were built to solve. RDDs are still there and still correct to reach for when you need custom partitioning logic or non-tabular data that doesn't fit a schema, but at any company running Spark at scale in 2026, DataFrame/SQL is the default and RDDs are the exception you have to justify.

**Where it's heading.** Spark 4.0 (May 2025) shipped ANSI SQL mode on by default, the Python Data Source API, and continued Spark Connect maturation, which decouples the client from the driver JVM entirely, a thin gRPC client that can run anywhere and talk to a remote Spark cluster. That direction (thin client, server-side execution, no local JVM) is the clearest trend: Spark is moving toward being consumed like a database rather than a framework you embed. Confidence: high, it's already shipping. More speculative: tighter integration with vectorized formats (Arrow-native UDFs, covered in the next module) suggests the JVM-Python boundary that has plagued PySpark performance for a decade will keep eroding, but a full switch to a non-JVM execution engine is not on any public roadmap. Treat that as a direction, not a prediction.

---

## Mental model

```
 DRIVER                                              CLUSTER MANAGER (YARN/K8s/EMR)
 ┌─────────────────────────┐                         ┌───────────────────────────┐
 │ SparkContext / SparkSession│───requests executors──▶│ allocates containers      │
 │ builds logical plan (lazy) │                         └───────────────────────────┘
 │ DAGScheduler: plan → jobs   │
 │   → stages (split on shuffle)                        EXECUTORS (one JVM each)
 │ TaskScheduler: stage → tasks│───ships tasks──────────▶┌─────────┐ ┌─────────┐
 │  (one task per partition)   │                         │ Task    │ │ Task    │
 └─────────────────────────┘                         │ Task    │ │ Task    │
                                                         │ (cores) │ │ (cores) │
                                                         └─────────┘ └─────────┘
```

**Job → stage → task**, concretely: an **action** (`.collect()`, `.write()`, `.count()`) triggers one **job**. The DAGScheduler walks the logical DAG backward from the action and cuts a new **stage** every time it hits a shuffle dependency (a wide transformation: `groupBy`, `join`, `repartition`, `distinct`). Everything between shuffle boundaries is a chain of narrow transformations (`map`, `filter`, `select`) that can be pipelined into a single stage with no data movement. Each stage is then split into **tasks**, one per partition of the stage's input, and tasks are the unit actually scheduled onto executor cores.

Why "a stage boundary is a shuffle" matters operationally: stage count and shuffle count are the same number. If your Spark UI shows 6 stages for a query with 2 joins and 1 groupBy, that's expected (roughly: read stages plus one per shuffle-inducing operation, with narrow ops fused in). If it shows 15, something is shuffling that shouldn't be, often a `repartition()` left over from debugging or a join that isn't being broadcast when it should be.

## How it actually works

### RDD lineage and laziness

An RDD is not data, it's a recipe: a graph of `(parent RDDs, transformation function, partitioner)`. Nothing executes until an action is called.

```python
rdd = sc.textFile("s3://bucket/logs/")      # no read happens yet
mapped = rdd.map(lambda line: line.split(",")[2])   # no computation yet
filtered = mapped.filter(lambda x: x != "")          # still nothing
count = filtered.count()                             # ACTION: now the whole
                                                      # lineage executes
```

`filtered.toDebugString()` prints the lineage graph — this is the mechanism that makes RDDs fault-tolerant without replication: lose a partition, recompute it from its parents using the recorded function chain. This is also exactly why RDDs are opaque to the optimizer: `filtered`'s definition is a Python closure. Spark can see there's a `map` then a `filter`, but it cannot see *what* the lambda does, so it cannot push the filter before the map, cannot prune columns the lambda never touches, cannot vectorize the row-at-a-time Python call.

**Transformations vs actions**, the distinction that governs everything above: transformations (`map`, `filter`, `join`, `groupByKey`) are lazy and return a new RDD/DataFrame describing more computation. Actions (`collect`, `count`, `write`, `take`, `foreach`) force evaluation and return a concrete result or side effect. A common bug: calling an action inside a loop (e.g., `.count()` on every iteration for "debugging") silently re-executes the entire lineage from source each time, because nothing is cached unless you explicitly `.cache()` or `.persist()`.

### Why DataFrames beat RDDs: what Catalyst can see

The core argument, stated precisely: an RDD transformation is an arbitrary function; a DataFrame transformation is an expression tree in Spark's own algebra (`Column`, `Expression`, `LogicalPlan` nodes). Because the DataFrame plan is data, not code, Catalyst can:

- **Push down predicates** — move a `.filter()` below a `.join()` or into the Parquet reader itself (predicate pushdown), reading fewer row groups from disk.
- **Prune columns** — a `select("a", "b")` after reading a 200-column Parquet table means only 2 column chunks are ever deserialized.
- **Reorder joins** based on cost estimates from table statistics.
- **Constant-fold and simplify** expressions (`WHERE 1=1 AND x > 5` becomes `WHERE x > 5`).

None of this is possible across a `.map(lambda row: my_func(row))` boundary, because `my_func` is a black box. This is the single most important fact in this module: **a Python/Scala UDF or an RDD lambda is an optimization barrier**. Everything upstream and downstream of it can still be optimized, but the operator itself is opaque, and depending on the API, may force a full-row Python round trip (see next module).

### Catalyst's four phases

```
SQL / DataFrame API
        │
        ▼
 ┌─────────────────┐   resolve column/table names & types
 │ Parsed Plan      │   against the catalog; unresolved refs
 └─────────────────┘   become resolved or throw AnalysisException
        │
        ▼
 ┌─────────────────┐
 │ Analyzed Plan    │   fully resolved logical plan
 └─────────────────┘
        │  rule-based optimization (predicate pushdown,
        │  constant folding, column pruning, join reorder)
        ▼
 ┌─────────────────┐
 │ Optimized Logical│
 │ Plan             │
 └─────────────────┘
        │  cost-based: pick join strategy (broadcast vs
        │  sort-merge vs shuffle-hash), pick physical operators
        ▼
 ┌─────────────────┐
 │ Physical Plan(s) │──▶ Spark picks the cheapest via cost model
 └─────────────────┘
        │
        ▼
 ┌─────────────────┐   Tungsten: generate actual JVM bytecode
 │ Selected Physical│   for the whole plan (whole-stage codegen)
 │ Plan → RDDs      │
 └─────────────────┘
```

Catalyst is a rule-based (with some cost-based elements for joins) tree-transformation engine: each phase applies a batch of rules until a fixed point, rewriting the tree. This is the standard four/five-phase pipeline described in the original Catalyst paper (Armbrust et al., SIGMOD 2015): parse → analyze → logical optimization → physical planning → code generation.

### Reading `explain()`

```python
df = spark.read.parquet("s3://bucket/orders/").filter("amount > 100").select("order_id", "amount")
df.explain(mode="formatted")
```

```
== Physical Plan ==
* Project (3)
+- * Filter (2)
   +- * ColumnarToRow (1)
      +- FileScan parquet [order_id#12,amount#15] Batched: true,
         PushedFilters: [IsNotNull(amount), GreaterThan(amount,100)]
```

Read this bottom-up: `FileScan` shows `PushedFilters`, proof the `amount > 100` predicate reached the Parquet reader (not just applied after the full scan), and the column list `[order_id, amount]` shows pruning happened even though the source file has more columns. The `*` prefix on `Project` and `Filter` means those operators are whole-stage-codegen'd into one generated function; a `ColumnarToRow` boundary marks the switch from Tungsten's columnar batch format to row-at-a-time for operators that aren't vectorized. `df.explain(mode="cost")` additionally shows estimated row counts and sizes, which is how you diagnose a bad join strategy choice: if the optimizer's row-count estimate for a table is wildly wrong (stale statistics), it will pick a sort-merge join where a broadcast would have worked, and `explain(mode="cost")` is how you catch that before staring at a slow job in the UI.

### Tungsten: off-heap memory and whole-stage codegen

Two separate mechanisms, often conflated:

1. **Off-heap binary row format.** Instead of a JVM object per row (with per-object headers, boxing of primitives, and pointer chasing), Tungsten packs rows into a compact binary format (`UnsafeRow`) that Spark manages directly via `sun.misc.Unsafe`, off the JVM heap. This cuts GC pressure (fewer objects for the collector to trace) and memory footprint (no object headers, no boxing overhead per field), and lets Spark use processor cache lines effectively since the layout is fixed and dense.
2. **Whole-stage code generation.** The naive "Volcano" execution model calls `next()` virtually up a chain of iterator objects, one virtual call per operator per row. Tungsten instead **fuses an entire stage's operators into one generated Java function**, compiled at runtime, eliminating the virtual call chain entirely. Databricks' own benchmark ("Apache Spark as a Compiler," 2016) reports whole-stage codegen approaching hand-written loop performance, roughly a **10x speedup** over the Volcano-style interpreted execution for CPU-bound operators, and the same work demonstrated joining and aggregating **one billion rows per second on a single laptop core** for a simple aggregation query, the number people remember from that post.

The `*` markers in `explain()` output are exactly the boundary of one generated function; when you see a plan with no `*` at all, whole-stage codegen didn't kick in (often because of a UDF, or an operator like `SortMergeJoin`'s sort phase that isn't codegen'd), and that's a place to look for performance.

### Partitions and the shuffle-partitions default

`spark.sql.shuffle.partitions` defaults to **200**, set once, globally, for every shuffle in the job — every `groupBy`, every `join` that isn't broadcast, every `repartition`. This default is wrong in both directions:

- **Too many for a small job.** A 2GB dataset shuffled into 200 partitions gives ~10MB per partition. Task scheduling overhead (typically a few ms of driver-side bookkeeping per task, plus executor JVM task setup) starts to dominate actual work, and you pay for 200 small file writes to shuffle storage instead of a handful of reasonably sized ones.
- **Too few for a large job.** A 2TB shuffle into 200 partitions gives ~10GB per partition, which likely exceeds a single executor's available shuffle-read memory, forcing spill to disk, and creates 200 enormous tasks that take minutes each instead of thousands of tasks that take seconds each and pipeline well across the cluster.

The fix in modern Spark (3.2+) is to stop hand-tuning this at all and let **Adaptive Query Execution** coalesce partitions after seeing actual shuffle output sizes at runtime, targeting `spark.sql.adaptive.advisoryPartitionSizeInBytes` (default 64MB) per partition instead of a fixed count. This is covered in depth in the next module; the fact to hold here is that 200 is a legacy default from an era before AQE existed, and any answer to "how do you set shuffle partitions" that doesn't mention AQE is answering a pre-2021 question.

---

## Build it from scratch

A minimal illustration of the RDD → DataFrame gap, runnable in a local PySpark shell:

```python
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("scratch").getOrCreate()
sc = spark.sparkContext

# --- RDD path: Spark cannot see inside the lambda ---
rdd = sc.parallelize([("a", 10), ("b", 20), ("a", 5), ("c", 30)])
rdd_result = (
    rdd.filter(lambda kv: kv[1] > 5)          # opaque predicate
       .map(lambda kv: (kv[0], kv[1] * 2))    # opaque projection
       .reduceByKey(lambda a, b: a + b)       # shuffle; combiner known
       .collect()
)
# Spark scheduled: 1 job, stages split at reduceByKey's shuffle.
# It could NOT push the filter before a source scan (there's no
# scan here) and in a real read-then-filter pipeline it could not
# push this filter into the file reader, because it doesn't know
# what `kv[1] > 5` means until it runs the Python bytecode per row.

# --- DataFrame path: same computation, visible plan ---
df = spark.createDataFrame([("a", 10), ("b", 20), ("a", 5), ("c", 30)], ["k", "v"])
df_result = (
    df.filter(df.v > 5)
      .withColumn("v2", df.v * 2)
      .groupBy("k").sum("v2")
)
df_result.explain(mode="formatted")   # shows PushedFilters, whole-stage codegen
df_result.collect()
```

Run both with `spark.sparkContext.setLogLevel("INFO")` and diff the Spark UI's SQL tab (only the DataFrame version has one) against the Jobs tab (both appear). The DataFrame version's physical plan shows a `HashAggregate` with partial aggregation before the shuffle (a combiner, same idea as `reduceByKey`, but chosen by the optimizer, not hand-coded), and if you swap the source for a Parquet file, only the DataFrame version's `explain()` shows `PushedFilters`.

A from-scratch toy Catalyst-style rule engine (parse a tiny expression tree, apply a "push filter below projection" rule, print before/after) belongs in a lab folder if you want to build intuition for how rule-based optimizers work; it is not required to answer any question in this module's interview section.

---

## How it's done in production

In production PySpark, you almost never touch RDDs directly. The DataFrame/Dataset API, `spark.sql`, and increasingly Spark Connect (`SparkSession.builder.remote(...)`) are the entire interface. What the framework adds over the mental model above:

- **Adaptive Query Execution** (default on since 3.2.0) revisits the physical plan mid-execution using real shuffle statistics, not just the optimizer's pre-execution estimates. Covered fully in the next module.
- **The catalog and metastore** (Hive Metastore, AWS Glue Catalog, Unity Catalog) supply the table statistics (`row count`, `data size`, column histograms via `ANALYZE TABLE ... COMPUTE STATISTICS`) that the cost-based optimizer needs to make good join-strategy decisions. Without `ANALYZE TABLE` ever having been run, Spark falls back to conservative defaults and cost-based join selection is effectively guessing.
- **Dynamic partition pruning** (3.0+) — for a join between a large fact table and a filtered dimension table, Spark can push the *values that survived the dimension-side filter* into the fact table scan as a partition filter, avoiding a full scan of the fact table's partitions.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Physical plan has no `*` (no whole-stage codegen) around an operator | UDF, or an operator Tungsten doesn't codegen (e.g. sort in `SortMergeJoin`) | Replace UDF with built-in `pyspark.sql.functions`; accept the sort cost or switch join strategy |
| 200 tiny shuffle files for a 5GB job | Default `shuffle.partitions=200` on a small dataset, AQE coalescing disabled or not triggering | Enable/verify `spark.sql.adaptive.coalescePartitions.enabled=true` |
| `explain()` shows `PushedFilters: []` on a Parquet scan with an obvious `WHERE` clause | Filter references a computed/derived column, or is inside a UDF, so it can't be pushed to the reader | Filter on raw source columns before deriving new ones |
| Job re-reads the same source data from S3 twice for what looks like one logical computation | An action was called twice on a lineage without `.cache()`/`.persist()`, or two separate jobs share upstream work uncached | Cache the shared upstream DataFrame, verify with the Storage tab |
| `AnalysisException: cannot resolve column` only on some runs | Schema drift in the source (new/renamed column) between the Parsed and Analyzed plan phases | Pin schema on read (`spark.read.schema(...)`), fail fast on schema mismatch |
| Cost-based join choice looks wrong in `explain(mode="cost")` (huge broadcast attempted, or sort-merge chosen for a tiny table) | Table statistics stale or never computed | Run `ANALYZE TABLE ... COMPUTE STATISTICS FOR ALL COLUMNS`, re-check the plan |

---

## Tradeoffs & when NOT to use it

- **RDDs are still the right tool** when you need custom, non-default partitioning logic that the DataFrame partitioner API doesn't expose (e.g. a domain-specific consistent-hash partitioner over a composite key), when your data isn't tabular at all (arbitrary Python objects, graphs), or when you're writing a library that must run identically regardless of the DataFrame API's evolving semantics. Reaching for RDDs "because they're more familiar from a tutorial" is not a good reason and will read as a red flag.
- **Spark itself is the wrong tool** below roughly single-machine-memory data sizes with straightforward transformations; the fixed overhead of driver coordination, task scheduling, and shuffle serialization means a well-tuned pandas/DuckDB/Polars job on a single large box will beat a small Spark cluster on latency for sub-tens-of-GB workloads. Principal-level candidates should be willing to say "I wouldn't reach for Spark here" when the data doesn't need it.
- **Catalyst cannot help you if you hide logic in a UDF.** Writing your entire transformation as one big Python UDF that takes a row and returns a row defeats the entire point of this module: you get RDD-era opacity with DataFrame-era serialization overhead layered on top. This is a common anti-pattern from engineers new to Spark who think in row-at-a-time terms.
- **Whole-stage codegen has a compile-time cost per stage.** For very short-lived queries (interactive notebooks running trivial queries against tiny data), the JIT/codegen overhead can exceed the query's actual execution time; `spark.sql.codegen.wholeStage` can be disabled for pathological cases, though this is rarely the right lever versus just accepting the fixed cost.

---

## Interview questions

### Q1 — Walk me through what happens between calling `.collect()` and getting a result back.
**Testing:** whether you actually understand the job/stage/task decomposition or just know the vocabulary.
**Answer:** `.collect()` is an action, so the DAGScheduler first materializes the logical DAG that's been lazily built up. It walks it backward, cutting a new stage at every shuffle dependency (wide transformation). Each stage becomes a set of tasks, one per partition of that stage's input, and the TaskScheduler assigns tasks to executor cores respecting locality preferences where possible. Stages run in dependency order; a stage can't start until its parent stage's shuffle output is fully written. The results from the final stage's tasks are serialized back to the driver and collected into a single local list.
**Follow-up trap:** *"What if collect() would return 500GB?"* — the driver OOMs, because collect pulls everything into driver memory as a local Python/Scala collection. This is a real production incident pattern; the fix is `.write()` to distributed storage, or `.take(n)`/sampling, never `.collect()` on anything whose size you haven't bounded.

### Q2 — Why does a DataFrame `groupBy().agg()` outperform an RDD `reduceByKey` doing the identical logical aggregation?
**Testing:** the core thesis of this module, not just "DataFrames are faster."
**Answer:** They can end up scheduling similar physical work (partial aggregation before shuffle, combine after), but the DataFrame version runs through Tungsten's off-heap row format and whole-stage codegen, avoiding JVM object boxing and per-row virtual calls, while the RDD version operates on boxed Python/Scala objects the whole way. In PySpark specifically, the RDD version's lambda executes in a separate Python process per executor core, so every row crosses the JVM-Python boundary via serialization; the DataFrame version's `sum()` is a built-in Catalyst expression that never leaves the JVM.
**Follow-up trap:** *"So RDDs are always slower?"* — not intrinsically; a Scala RDD with a tight, JIT-friendly reduce function can be fast. The gap is largest for PySpark specifically, because of the cross-process serialization, and for cases where Catalyst can additionally exploit visibility into the computation (predicate pushdown, column pruning) that an RDD chain can't offer regardless of language.

### Q3 — What exactly does a shuffle do, mechanically, and why is it a stage boundary?
**Testing:** whether "shuffle" is a real mechanism to you or a scary word.
**Answer:** A shuffle repartitions data across the cluster by key: each task in the upstream stage writes its output records into buckets, one per downstream partition, determined by a partitioner (hash of the key, by default). Those bucketed files are written to local disk (shuffle write) and then each downstream task pulls the relevant bucket from every upstream task over the network (shuffle read/fetch). It's a stage boundary because the downstream stage cannot start until the shuffle write from *every* upstream task is complete and the data has physically moved; you can't pipeline across that barrier the way you can across a chain of narrow transformations.
**Follow-up trap:** *"Where do shuffle files live, and what happens if an executor holding them dies?"* — they live on local disk (or external shuffle service storage) of the executor that produced them. If that executor dies before downstream tasks have read its shuffle output, Spark must recompute the upstream stage's lost partitions via lineage, which is why losing an executor mid-shuffle is disproportionately expensive versus losing one during a narrow-transformation stage.

### Q4 — Show me `explain()` output and tell me if it's healthy.
**Testing:** can you actually read a physical plan, the single most useful production debugging skill for this stack.
**Answer:** Walk bottom-up from the scan: check `PushedFilters` is non-empty if there's a WHERE clause, check the column list is pruned to what's actually used, check for `*` markers indicating whole-stage codegen, check the join strategy (`BroadcastHashJoin` vs `SortMergeJoin` vs the dangerous `BroadcastNestedLoopJoin`) matches what you'd expect given table sizes, and with `mode="cost"` check the estimated sizes aren't wildly wrong versus what you know about the data.
**Follow-up trap:** *"You see BroadcastNestedLoopJoin. What does that tell you?"* — it means there was no equality condition Spark could use for a hash join, usually a non-equi join condition (`a.x < b.y`) or a cross join, and it's broadcasting one side and doing a nested-loop comparison, which is O(n×m) and a common accidental-cartesian-product bug. Immediately check whether the join condition is actually what was intended.

### Q5 — Why does the Catalyst optimizer have separate "analyzed" and "optimized" logical plan phases instead of one?
**Testing:** depth beyond the "four boxes" diagram.
**Answer:** Analysis is about correctness: resolving column and table references against the catalog, checking types, and it can fail (`AnalysisException`) if references don't exist. Optimization is about performance and assumes correctness is already established; it applies rewrite rules (predicate pushdown, constant folding, pruning) to a plan that's already known to be valid. Separating them means optimization rules never have to worry about unresolved references, and analysis errors surface before any optimization work (or execution) is attempted, giving fast, clear failures.
**Follow-up trap:** *"Give me an example of a rule that could be unsafe if applied before full analysis."* — predicate pushdown past a `LIMIT` or into a subquery with side-effect-adjacent semantics (e.g. a non-deterministic UDF used in a filter) — pushing a filter containing `rand()` below a join changes which rows see which random value, so Catalyst explicitly excludes non-deterministic expressions from certain pushdown rules once it can identify them as non-deterministic during analysis.

### Q6 — What does Tungsten's off-heap memory actually buy you, mechanically?
**Testing:** whether "off-heap" is a fact you memorized or a mechanism you understand.
**Answer:** Standard JVM objects carry per-object overhead (a header, alignment padding, pointers for references) and primitives inside collections get boxed (an `Integer` object instead of a raw `int`), both of which bloat memory footprint and create garbage for the collector to trace. Tungsten's `UnsafeRow` format packs row data into a flat byte layout that Spark manages directly via `sun.misc.Unsafe`, off the normal JVM heap, so there's no per-object header, no boxing, and the GC doesn't need to trace into it at all since it's not a JVM object graph. This cuts both memory usage and GC pause frequency, which matters a lot for large `shuffle.partitions` counts holding many small objects.
**Follow-up trap:** *"Does off-heap memory show up in your OOM errors?"* — it shows up differently: instead of `java.lang.OutOfMemoryError: Java heap space`, exhausting Tungsten's managed off-heap region under `spark.memory.offHeap.enabled=true` typically manifests as a Spark-level `OutOfMemoryError` from the `TaskMemoryManager` or triggers spill-to-disk first if the operator supports it (like sort or aggregate). Knowing that the error surface is different is the actual signal here.

### Q7 — Derive a sane value for `spark.sql.shuffle.partitions` for a 500GB shuffle, and explain why 200 is wrong.
**Testing:** whether you can reason quantitatively instead of quoting a rule of thumb.
**Answer:** Target roughly 100-200MB per partition post-shuffle for good task granularity without excessive scheduling overhead: 500GB / 150MB ≈ 3,400 partitions. The default of 200 would give ~2.5GB per partition, which risks spill and gives you only 200 tasks to spread across potentially hundreds of cores, underutilizing the cluster and creating long-tail tasks.
**Follow-up trap:** *"Why not just always set it very high, like 10,000?"* — task scheduling and shuffle-file overhead scale with partition count; each task has fixed per-task overhead (a few ms) and each shuffle produces M×N intermediate files (M map tasks × N reduce partitions) before consolidation, so an excessive partition count creates a huge number of small shuffle files, hurting both the shuffle service and small-file overhead on the read side. This exact "guess a static number" problem is what AQE's dynamic coalescing (next module) is designed to eliminate.

### Q8 — Your DataFrame pipeline has a `.rdd.map(...)` in the middle for "some custom logic." What's your reaction?
**Testing:** whether you recognize this as an anti-pattern and can explain the cost precisely, not just say "UDFs bad."
**Answer:** That's a full optimization-barrier round trip: Catalyst can optimize everything before the `.rdd` conversion and everything after re-entering DataFrame land, but the conversion itself forces materializing `UnsafeRow`s back into JVM objects (Scala) or serializing to Python objects (PySpark, with a full JVM↔Python trip per row), runs the opaque map, then re-infers a schema and reconstructs `UnsafeRow`s to continue. I'd ask what the custom logic actually does; it's very often expressible as a combination of built-in `pyspark.sql.functions`, or at worst a pandas/Arrow UDF (see next module), both of which stay inside the optimizer's visibility or at least avoid the RDD round-trip's schema reconstruction cost.
**Follow-up trap:** *"What if the logic genuinely can't be expressed as a column expression?"* — then it should be a UDF applied via `.withColumn()`, not a full RDD conversion; a UDF is still an opacity barrier for that one operation, but it doesn't force the plan to leave DataFrame representation entirely, and everything else in the query still gets optimized around it.

### Q9 — Explain the RDD fault-tolerance model. Why doesn't Spark replicate data like HDFS does?
**Testing:** understanding of lineage as the recovery mechanism, and why that was the actual innovation.
**Answer:** Every RDD records its lineage: the parent RDD(s) and the deterministic transformation that produced it. If a partition is lost (executor dies), Spark recomputes just that partition by replaying the recorded transformation chain against the parent partition(s), rather than reading a replicated copy from disk. This trades some recomputation cost on failure for avoiding the write-amplification and storage cost of replicating every intermediate dataset the way HDFS replicates blocks.
**Follow-up trap:** *"When does lineage-based recovery get expensive?"* — with long, deep lineage chains (many chained transformations with no persisted checkpoint), losing a partition near the end of the chain means recomputing a long history. `.checkpoint()` truncates lineage by writing a materialized copy to reliable storage, trading storage cost for bounded recovery cost, and is used for iterative algorithms (e.g. graph algorithms) where lineage would otherwise grow unboundedly across iterations.

### Q10 — A junior engineer says "Spark is just parallel pandas." What's wrong with that framing, precisely?
**Testing:** systems-level understanding versus API-level understanding, staff-level framing question.
**Answer:** Pandas assumes the entire dataset fits in one process's memory and executes eagerly, operation by operation, on that in-memory representation. Spark's core value is a lazy, distributed execution model where an entire multi-step computation is described as a plan *before* anything runs, cluster-wide, which is what allows cross-operation optimization (Catalyst can rewrite the whole plan, not one operation at a time), fault tolerance via lineage across machines, and out-of-core processing of datasets far larger than any single machine's RAM. "Parallel pandas" undersells that Spark's optimizer reasons globally across the whole query, not operation-by-operation.
**Follow-up trap:** *"So Spark is always better than pandas?"* — no, and saying otherwise is the actual red flag here. Below the point where data fits comfortably on one machine, pandas (or Polars/DuckDB) avoids Spark's fixed distributed-coordination overhead (driver scheduling, serialization, network shuffle) entirely and wins on latency. Good engineers pick based on data size and latency needs, not on Spark being "the more advanced tool."

---

## Red flags that fail you

- Saying RDDs and DataFrames have "basically the same performance, DataFrames are just nicer syntax."
- Not knowing that a shuffle is what defines a stage boundary.
- Claiming Catalyst can optimize inside a UDF or an RDD lambda.
- Describing `explain()` output without checking `PushedFilters` or join strategy.
- Treating `spark.sql.shuffle.partitions=200` as a value you'd never touch, with no mention of AQE.
- Calling `.collect()` on unbounded data "because it works in the notebook."
- Not distinguishing whole-stage codegen from off-heap memory as two separate Tungsten mechanisms.

## Cheat card

```
JOB → STAGE → TASK: action triggers job; DAGScheduler cuts a stage at every
  shuffle (wide transform); each stage = 1 task per partition.
RDD: lineage graph (parent, fn, partitioner). Lazy. Recompute lost
  partitions via lineage, not replication. .toDebugString() shows it.
TRANSFORMATIONS lazy (map/filter/join) vs ACTIONS eager (collect/count/write).
WHY DATAFRAMES WIN: plan is DATA (Column/Expression tree), not opaque code.
  Catalyst can push filters, prune columns, reorder joins. A UDF/RDD lambda
  is an OPTIMIZATION BARRIER Catalyst cannot see through.
CATALYST PHASES: Parsed → Analyzed (resolve+typecheck) → Optimized Logical
  (rule-based: pushdown/pruning/folding) → Physical (cost-based join pick)
  → whole-stage codegen (Tungsten) → RDDs.
TUNGSTEN = 2 things: (1) UnsafeRow off-heap binary format, no boxing/headers,
  less GC. (2) whole-stage codegen fuses a stage into one JIT'd function,
  ~10x vs Volcano-style virtual-call iteration (Databricks 2016 benchmark;
  1B rows/sec aggregation on one laptop core in that post).
explain(mode="formatted"): read bottom-up. Check PushedFilters non-empty,
  column pruning, `*` = codegen'd, join strategy sane.
  explain(mode="cost") shows row/size estimates -> needs ANALYZE TABLE.
shuffle.partitions DEFAULT = 200, global, applies to every shuffle.
  Too many -> small-job overhead; too few -> spill/OOM on big shuffles.
  Fixed by AQE dynamic coalescing (next module), target ~64MB/partition
  (spark.sql.adaptive.advisoryPartitionSizeInBytes default).
```

## Sources

- [Adaptive Query Execution — Spark 4.2.0 Performance Tuning docs](https://spark.apache.org/docs/latest/sql-performance-tuning.html) — accessed 2026-08-01
- [Apache Spark as a Compiler: Joining a Billion Rows per Second on a Laptop — Databricks](https://www.databricks.com/blog/2016/05/23/apache-spark-as-a-compiler-joining-a-billion-rows-per-second-on-a-laptop.html) — accessed 2026-08-01
- [What's New in Apache Spark 4.0 — DZone](https://dzone.com/articles/apache-spark-4-0-new-features-2025) — accessed 2026-08-01
- [Whole-Stage Java Code Generation — The Internals of Spark SQL](https://jaceklaskowski.gitbooks.io/mastering-spark-sql/content/spark-sql-whole-stage-codegen.html) — accessed 2026-08-01
- [Tungsten Execution Backend — The Internals of Spark SQL](https://jaceklaskowski.gitbooks.io/mastering-spark-sql/spark-sql-tungsten.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
