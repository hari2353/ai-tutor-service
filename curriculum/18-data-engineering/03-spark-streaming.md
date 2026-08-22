# Structured Streaming: Watermarks, Triggers, Exactly-Once Sinks

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-spark-streaming` · **Tags:** spark

## The 30-second version

Structured Streaming treats a stream as an unbounded table and re-expresses your batch DataFrame logic as an incremental query re-run on new data each micro-batch, which is why the API looks identical to batch Spark. Watermarks bound how long the engine keeps state for a window by declaring "I won't accept data more than N minutes late," trading completeness for a hard cap on state size, without a watermark, stateful state grows forever and eventually OOMs. Exactly-once is not something the engine hands you: Spark guarantees exactly-once *processing* per micro-batch via checkpointed offsets and idempotent internal retries, but the end-to-end guarantee only holds if your sink is idempotent or transactional, which is why the Kafka sink is at-least-once by default and only the file sink gets exactly-once out of the box. If someone asks "is Spark Streaming exactly-once," the honest answer is "the engine is, the pipeline is only exactly-once if the sink cooperates."

## Why this gets asked

The interviewer has debugged a state store that grew until an executor died, or a "duplicate row" bug in a downstream table that traced back to an at-least-once sink after a restart replayed a partially-committed batch. They want to know whether you understand watermarks as a state-size control (not just a "handle late data" feature), and whether you'll correctly push back when someone says "just turn on Structured Streaming, it's exactly-once" without checking what the sink actually guarantees.

---

## Lineage: past → present → future

**What came before.** Spark's original streaming API, DStreams (Spark Streaming, pre-2016), modeled a stream as a sequence of micro-batch RDDs, each processed with the RDD API. The pain: it inherited every RDD-era limitation from the previous modules (no Catalyst optimization, no unified batch/streaming code path), and correctness for late-arriving or out-of-order data was almost entirely the application's problem to solve by hand, there was no first-class notion of event-time versus processing-time. Storm and Flink, contemporaneously, offered true record-at-a-time processing with more mature event-time semantics (Flink's watermarks predate Spark's by several years and directly influenced the design), but at the cost of a separate execution engine and programming model from batch.

**Where it stands now.** Structured Streaming (Spark 2.0, 2016) unified the model: a streaming DataFrame is the same DataFrame API as batch, executed incrementally, re-using Catalyst and Tungsten entirely. This is genuinely one query engine for both batch and streaming code, and it's the reason a well-written streaming aggregation and its batch equivalent look almost identical. Micro-batch is still the default and dominant execution mode in production; **Continuous Processing** mode (introduced Spark 2.3, targeting ~1ms latency via long-running tasks instead of discrete batches) exists but remains experimental with a much narrower operator support surface (no aggregations) and sees comparatively little production adoption versus tuned micro-batch with small trigger intervals. RocksDB as a state store backend (built-in since Spark 3.2) is now the standard answer for any job with large keyed state, replacing the default in-memory (`HDFSBackedStateStore`) backend which holds all state in executor JVM heap and causes GC pressure as state grows into the millions of keys. The live disagreement is less about the model and more about state store choice and sizing, and about how honestly "exactly-once" claims should be qualified per sink.

**Where it's heading.** The trend is toward broader native connector support for exactly-once semantics without hand-rolled `foreachBatch` idempotency logic (transactional/idempotent write support maturing across more sinks and table formats, Delta/Iceberg's ACID commit protocols make the "transactional sink" half of the exactly-once story easier to get for free when writing to a lakehouse table versus a raw Kafka topic or JDBC sink). Confidence: high, this is incremental and already shipping. More speculative: convergence between streaming state management and durable-execution/checkpointing patterns seen elsewhere (the same direction flagged in the resilience-patterns module for agentic systems) suggests state stores may eventually be exposed as a more general queryable/inspectable primitive rather than an internal implementation detail; Spark 4.0's streaming state store data source is an early step in that direction (letting you read a checkpoint's state as a batch DataFrame for debugging), but a fully general external state API is not yet standard practice.

---

## Mental model

Think of the stream as **an unbounded input table** that new rows are continuously appended to. Your query is a batch query written *as if* it ran once against the whole table; Structured Streaming instead re-runs the equivalent incremental computation against just the new rows each trigger, and maintains whatever intermediate state (partial aggregates, join buffers) is needed to keep the *result* correct as if the query had been run fresh against the whole table each time.

```
 Unbounded Input Table (conceptual)          Result Table (conceptual)
 ┌───────────────────────────┐               ┌───────────────────────────┐
 │ t=0 rows                   │  incremental  │ result after t=0          │
 │ t=1 rows (appended)  ─────▶│    query   ──▶│ result after t=1          │
 │ t=2 rows (appended)         │  (same code   │ result after t=2          │
 │ ...                         │   as batch!)  │ ...                        │
 └───────────────────────────┘               └───────────────────────────┘
        │
        ▼ each micro-batch trigger:
 ┌──────────────────────────────────────────────────────────────┐
 │ 1. read new offsets from source (Kafka, files, ...)            │
 │ 2. process against STATE (checkpointed: offsets + operator     │
 │    state, e.g. partial window aggregates, dedup sets)          │
 │ 3. advance the watermark (max event-time seen - lateness bound)│
 │ 4. drop state for windows older than the watermark             │
 │ 5. write output (mode: append/update/complete) to the sink     │
 │ 6. commit new offsets + state to the checkpoint atomically      │
 └──────────────────────────────────────────────────────────────┘
```

The watermark is the mechanism that turns "unbounded" into "bounded": without it, step 4 never happens, and state (one entry per open window/group) grows forever.

## How it actually works

### Micro-batch vs continuous, and the incremental-query model

**Micro-batch** (the default and dominant mode) discretizes the stream into small batches on a trigger interval; each batch is planned and executed as a genuine, if small, Spark job with its own stages and tasks, going through the same Catalyst/Tungsten pipeline as a batch query. Latency floor is bounded by trigger interval plus batch-planning overhead, typically hundreds of milliseconds at best for tuned micro-batch, seconds is far more common and fine for most real workloads. **Continuous processing** instead runs long-lived tasks that process records as they arrive with no discrete batch boundary, targeting single-digit-millisecond latency, but supports a much narrower set of operators (as of current Spark, only map-like operations and simple filters; no aggregations, no most joins) and has seen limited production adoption relative to its age, most latency-sensitive teams either tune micro-batch trigger intervals down or reach for a purpose-built engine (Flink) instead.

### Watermarks, derived

**Late data**, precisely: a record whose **event-time** (when the thing actually happened, a field in the data) arrives after the engine has already advanced past that time in **processing-time** (wall-clock time at the engine). Event-time and processing-time diverge constantly in real systems: mobile clients buffering offline, a Kafka partition lagging behind its siblings, retried writes.

**Deriving the watermark**: declare `withWatermark("event_time", "10 minutes")`. On every trigger, the engine tracks `maxEventTimeSeen`, the maximum event-time observed across all data processed so far, and sets:

```
watermark = maxEventTimeSeen - lateness_threshold
```

Any window whose *end* falls before the current watermark is considered closed: the engine emits its final result (in `complete`/`update` mode; in `append` mode, the emit *is* the close) and **drops its state**. Any incoming record with event-time older than the current watermark is treated as too late and dropped rather than reopening a closed window.

```python
from pyspark.sql import functions as F

events = (
    spark.readStream.format("kafka")
    .option("subscribe", "clicks")
    .load()
    .select(F.from_json(F.col("value").cast("string"), schema).alias("e"))
    .select("e.*")
)

windowed = (
    events
    .withWatermark("event_time", "10 minutes")
    .groupBy(F.window("event_time", "5 minutes"), "user_id")
    .count()
)
```

Worked example: if `maxEventTimeSeen` is `12:33` and lateness is `10 minutes`, the watermark is `12:23`. A 5-minute window `[12:15, 12:20)` closes and its state is dropped once the watermark passes `12:20`, i.e. once `maxEventTimeSeen` reaches `12:30`. A record arriving afterward with `event_time = 12:18` is now older than the watermark and is silently dropped, not late-merged into the already-closed window.

**The tradeoff, stated as a dial**: a short lateness threshold keeps state small (windows close quickly, memory stays bounded) but drops more genuinely late data as "too late," hurting completeness. A long threshold captures more late data correctly but keeps many more windows open simultaneously, growing state proportionally and increasing memory/checkpoint size, and delaying final results. There is no threshold that is simply "correct"; it's chosen from the real observed lateness distribution of the upstream source (99th percentile client clock skew, typical Kafka replication lag, etc.), not a default.

### Window types

- **Tumbling windows** — fixed-size, non-overlapping (`window("event_time", "5 minutes")`). Each event belongs to exactly one window.
- **Sliding windows** — fixed-size, overlapping, advancing by a slide interval smaller than the window size (`window("event_time", "10 minutes", "5 minutes")`). Each event contributes to multiple overlapping windows, multiplying state proportionally to `window_size / slide_interval`.
- **Session windows** (native support since Spark 3.2) — dynamic-length windows that close after a gap of inactivity per key (`session_window("event_time", "30 minutes")`), used for user-session-style aggregation where fixed boundaries don't fit the semantics.

### Output modes and sink compatibility

| Mode | Emits | Typical use | Sink support |
|---|---|---|---|
| **Append** (default) | Only new rows since the last trigger, once they're final | Non-aggregating queries (select/filter/map/flatMap), and windowed aggregations with a watermark (rows emitted once their window closes) | Broadest support: file sinks, Kafka, Delta/Lake table sinks |
| **Update** | Rows that changed since the last trigger | Aggregations where you want incremental updated results, not just final ones | Console, Kafka, memory; notably **not** most file/table sinks (e.g. Delta/Lake-backed tables commonly support append and complete but not update) |
| **Complete** | The entire result table, every trigger | Small aggregations where downstream wants the full current state each time | Console, memory, some table sinks; expensive for anything but small result sets since the whole table is rewritten every trigger |

**Joins only support append mode.** This is a common trap: attempting `update` or `complete` output on a stream-stream join fails at query start, not silently, because Spark cannot express incremental updates to already-emitted join results the way it can for aggregations.

### Checkpointing and state stores, RocksDB

The checkpoint directory (`.option("checkpointLocation", ...)`) is what makes restart-safe, exactly-once-*processing* semantics possible: it durably stores (a) the source offsets already processed, (b) the operator state (partial aggregates, join buffers, dedup keys) as of the last successfully committed batch, and (c) write-ahead logs where needed for sink coordination. On restart, Spark reads the checkpoint, resumes from the last committed offset, and reconstructs state, so a crash mid-batch does not lose or (for the parts within Spark's control) duplicate processing.

**State store backends**:
- **`HDFSBackedStateStore`** (default): state lives as objects in executor JVM heap, periodically snapshotted to durable storage (despite the name, this typically means the configured checkpoint filesystem, e.g. S3/HDFS/ADLS, not literally requiring HDFS). Fine for modest state (thousands to low millions of keys); as state grows, JVM heap pressure and GC pauses grow with it, since every key/value lives as a full JVM object.
- **RocksDB state store** (built-in since Spark 3.2, enable via `spark.sql.streaming.stateStore.providerClass=org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider`): state lives in RocksDB (native, off-heap, disk-backed LSM-tree storage) local to each executor, with changes checkpointed incrementally. Handles state in the tens of millions of keys without JVM GC pressure, at the cost of some added latency per state access (native calls, potential disk I/O) versus pure in-memory JVM state for small state sizes. The standard recommendation once a job's state (visible via the Streaming UI's "state rows" / "state size" metrics) climbs into the millions.

### Triggers

| Trigger | Behavior |
|---|---|
| `ProcessingTime(interval)` (default-ish, e.g. `"10 seconds"`) | Fires a micro-batch on a fixed wall-clock interval; if a batch takes longer than the interval, the next one starts immediately after, no overlap |
| `Once()` | **Deprecated.** Processes exactly one batch of all currently available data, then stops. |
| `AvailableNow()` (replacement for `Once()`) | Processes all data available *at query start* across one or more batches (respecting rate limits like `maxOffsetsPerTrigger`), then stops; unlike `Once()`, it can split the available backlog into multiple appropriately-sized batches instead of forcing everything into one giant batch |
| `Continuous(interval)` | Continuous processing mode; `interval` here is a checkpoint interval, not a batch interval, since there are no discrete batches |

`AvailableNow` is the standard choice for scheduled/batch-like invocations of an otherwise-streaming pipeline (e.g. an hourly Airflow-triggered "catch up on everything new" run) since it correctly bounds and paginates a potentially large backlog rather than trying to force it through one oversized batch the way `Once()` does.

### Exactly-once as a property of the whole pipeline

The engine's own guarantee: **exactly-once processing**, meaning each micro-batch's *input* offsets are recorded and committed atomically with the batch's completion, so a restart never reprocesses a batch that was already fully committed, and never skips one that wasn't. This is real and Spark delivers on it internally.

What it does **not** guarantee: that the **output actually written to the sink** reflects exactly-once effects, because writing to the sink and committing the batch's checkpoint are two separate operations, and a crash between "sink write succeeded" and "checkpoint committed" (or the reverse ordering, depending on the sink) can cause a batch to be retried and its output written again. Whether that's safe depends entirely on the sink:

- **File sinks** (writing new files per batch to object storage) are naturally exactly-once-friendly: a retried batch either produces a new file (harmless duplicate data unless downstream doesn't dedupe) or, with Spark's file-sink commit protocol, uses an atomic rename/manifest mechanism that avoids partial files. This is the one sink type commonly cited as exactly-once "for free."
- **Kafka sink** is **at-least-once by default**: Kafka's own idempotent producer (`enable.idempotence=true`) prevents duplicate *individual* message sends on retry within one producer session, but does not make an entire retried micro-batch's write exactly-once end to end, achieving true exactly-once against Kafka requires transactional writes coordinated with consumer offset commits, which Structured Streaming's built-in Kafka sink does not do automatically; you'd need custom `foreachBatch` logic with Kafka transactions.
- **JDBC / arbitrary sinks via `foreachBatch`** get whatever guarantee *you* build: exactly-once requires either an idempotent write (e.g. `INSERT ... ON CONFLICT DO NOTHING` keyed by a batch or record id) or a transactional write coordinated with tracking which batch IDs have already been committed (checking `batchId` against a durably stored "last committed batch" marker before writing).

```python
def write_idempotent(batch_df, batch_id):
    # untested sketch
    (batch_df.write
        .mode("append")
        .option("txnAppId", "clicks-pipeline")   # Delta idempotent write support
        .option("txnVersion", str(batch_id))
        .format("delta")
        .save("s3://bucket/clicks_gold/"))

stream.writeStream.foreachBatch(write_idempotent).start()
```

The interview-ready framing: **exactly-once is a property of the whole pipeline** (source replayability, engine-side offset/state commit atomicity, and sink idempotency/transactionality all three), not something the streaming engine alone provides. Claiming "Structured Streaming is exactly-once" without qualifying which sink is doing the work is the single most common overclaim in this space.

### Kafka offsets

Structured Streaming reads Kafka offsets itself and stores them in the checkpoint, it does **not** rely on Kafka consumer group commits for its own recovery (though it can optionally report progress to a consumer group for external monitoring). This is a deliberate design choice: relying on the checkpoint (co-located with operator state, committed atomically with batch completion) rather than Kafka's own offset-commit mechanism (which would be a separate, non-atomic commit relative to Spark's own state) is what makes engine-side exactly-once processing possible at all.

### The state-explosion failure mode

**Symptom**: the Streaming UI's state metrics (`numRowsTotal`/state size for a stateful operator) show state size growing monotonically batch over batch with no plateau, executor memory usage on stateful tasks climbs correspondingly, and eventually the job either OOMs, or (with RocksDB) local disk fills up, or batch processing time itself starts increasing because each batch now touches an ever-larger state store.

**Cause, almost always one of:**
- No watermark declared at all on a windowed aggregation or stream-stream join, so no window/join-buffer entry is ever eligible to be dropped, state accumulates for the lifetime of the query.
- A watermark declared but set far too generously relative to actual lateness (e.g. "24 hours" when real lateness is minutes), keeping vastly more windows open than necessary.
- A **sliding window** with a small slide interval relative to window size, multiplying live window count by `window_size / slide_interval` versus an equivalent tumbling window.
- A stream-stream **join without a watermark on both sides**, which similarly has no bound on how long unmatched rows are buffered waiting for a match.

**Fix**: declare a watermark sized from the source's real lateness distribution, prefer tumbling over sliding windows unless the overlap is genuinely required, watermark both sides of any stream-stream join, and monitor state size as a first-class metric, not just batch latency, since state growth often precedes a latency or OOM symptom by hours.

---

## Build it from scratch

A minimal watermarked windowed count with a manual late-data check, runnable locally against a rate source (no external Kafka needed for the demo):

```python
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.master("local[2]").getOrCreate()

# Rate source: generates rows with a monotonic `timestamp` and `value`.
# Simulate event-time lateness by shifting timestamp backward for some rows.
raw = spark.readStream.format("rate").option("rowsPerSecond", 5).load()
events = raw.withColumn(
    "event_time",
    F.when(F.col("value") % 7 == 0, F.col("timestamp") - F.expr("INTERVAL 15 MINUTES"))
     .otherwise(F.col("timestamp"))
)

windowed_counts = (
    events
    .withWatermark("event_time", "10 minutes")   # 15-min-late rows above get dropped
    .groupBy(F.window("event_time", "1 minute"))
    .count()
)

query = (
    windowed_counts.writeStream
    .outputMode("update")           # append would also work but delays visible output
    .format("console")
    .option("truncate", False)
    .trigger(processingTime="10 seconds")
    .option("checkpointLocation", "/tmp/claude-scratch/streaming-ckpt")
    .start()
)
query.awaitTermination(60)
```

Run it and watch the console output: rows with the simulated 15-minute lateness (beyond the 10-minute watermark threshold) never appear in any window's count, demonstrating the drop behavior directly, and the Streaming UI (`http://localhost:4040` while running) shows the state-row count plateauing rather than growing, confirming the watermark is bounding state. A full lab with a Kafka source, a `foreachBatch` idempotent Delta sink using `txnAppId`/`txnVersion`, and a chaos test that kills the query mid-batch to verify no duplicate/missing output belongs in a lab folder; it is not required to answer this module's interview questions.

---

## How it's done in production

Production streaming pipelines on Spark almost always run on a managed platform (Databricks Jobs/DLT, EMR with a long-running Spark application, or Kubernetes via the Spark Operator) rather than a hand-managed `spark-submit` daemon, specifically because restart/retry orchestration, checkpoint lifecycle management, and alerting on state-size or lag metrics are operational concerns the platform handles. Databricks' Delta Live Tables (DLT, now branded Lakeflow Declarative Pipelines) layers declarative dependency management and built-in data-quality expectations on top of the same Structured Streaming engine underneath.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| State size in the Streaming UI grows without bound, batch time creeping up | No watermark, or watermark far too generous relative to actual lateness | Add/tighten watermark based on real observed lateness distribution |
| Records silently missing from output that you know were sent | Watermark too tight; records arrived later than the threshold and were dropped as "too late" | Widen the watermark, or route rejected-late records to a dead-letter sink for visibility |
| Duplicate rows in the downstream table after a job restart | Sink is at-least-once (e.g. plain Kafka sink or a non-idempotent JDBC write) and a batch was retried after partially succeeding | Make the sink idempotent (dedup key, `ON CONFLICT`) or transactional (Delta `txnAppId`/`txnVersion`, Kafka transactional producer) |
| Query fails immediately at start with an output-mode error | Attempting `update` or `complete` mode on a stream-stream join, which only supports `append` | Switch to `append`, restructure the query |
| Checkpoint directory grows very large / restart is slow | RocksDB or HDFS-backed state store accumulating without compaction, or a very large declared watermark keeping enormous state live | Verify RocksDB is being used for large state, review watermark sizing, check for a genuine state-explosion cause above |
| Job "processes fine" per-batch metrics but wall-clock output lag keeps growing | Batch processing time exceeding the trigger interval consistently (the query can't keep up with input rate) | Reduce per-batch work (repartition, reduce shuffle), increase resources, or accept a longer trigger interval deliberately |

---

## Tradeoffs & when NOT to use it

- **Do not reach for Structured Streaming when you actually have a scheduled batch job.** If data arrives in predictable, complete chunks (an hourly file drop) and low latency isn't a real requirement, a batch job with `AvailableNow` semantics achieved via plain batch Spark, or genuinely just a scheduled batch read, is simpler to reason about, test, and debug than a long-running streaming query with checkpoint and state-store lifecycle to manage.
- **Do not promise sub-second latency without checking whether Continuous Processing's operator restrictions (no aggregations, narrow operator set) are compatible with your actual query.** Most real pipelines need aggregations or joins, which forces micro-batch, with a practical latency floor in the hundreds of milliseconds to low seconds even when heavily tuned.
- **Do not claim exactly-once without naming the sink.** This is the single most common overclaim; the honest statement is always "exactly-once processing from the engine, plus [idempotent/transactional mechanism] at the sink."
- **Do not use sliding windows by default.** They multiply state by `window_size / slide_interval` versus tumbling windows; only use them when the actual analytical need requires overlapping windows (e.g. a "rolling 10-minute average updated every minute" requirement), not as a default choice.
- **A watermark is a correctness tradeoff, not a performance-only knob.** Setting it too tight silently drops real data; this needs to be a deliberate, monitored decision (dead-letter the dropped-as-late records if data loss is unacceptable), not a default value copied from a tutorial.

---

## Interview questions

### Q1 — Explain the unbounded-table model. Why does the streaming DataFrame API look identical to the batch API?
**Testing:** baseline conceptual model.
**Answer:** A streaming DataFrame is modeled as a query against a conceptually infinite, continuously-appended input table; Structured Streaming compiles the same declarative query you'd write in batch and executes it incrementally, re-running the equivalent computation against new data each trigger while maintaining whatever state is needed to keep the result consistent with "run the whole query fresh each time." Because the query itself is the same DataFrame/Catalyst plan either way, batch and streaming share the entire optimizer and execution engine; only the driving loop (micro-batch vs single execution) differs.
**Follow-up trap:** *"So can I always convert a batch job to streaming by just changing readStream/writeStream?"* — not always; some operations (e.g. certain non-deterministic UDFs relying on full-dataset context, or global sorts) don't have a sensible incremental semantic, and Spark will reject unsupported operations at query-plan-analysis time with an explicit error, not silently produce wrong incremental results.

### Q2 — Derive what a watermark actually bounds, using the formula.
**Testing:** whether you can derive it, not just recite "handles late data."
**Answer:** `watermark = maxEventTimeSeen - latenessThreshold`, recomputed on every trigger as new data updates `maxEventTimeSeen`. Any window whose end time falls before the current watermark is considered closed and its state is dropped; any incoming record with event-time older than the current watermark is dropped as too late rather than reopening closed state. This bounds the number of "open" windows/groups being tracked at any time to roughly `latenessThreshold / window_size` (plus in-flight partial windows), which is what keeps state size from growing without limit.
**Follow-up trap:** *"What if event-time in the source is monotonically decreasing due to a bug (e.g. clock skew across producers)?"* — the watermark only moves forward based on `maxEventTimeSeen`, so a single spurious future-dated event-time can advance the watermark prematurely and cause subsequent, correctly-timed data to be dropped as "too late." This is a real production bug pattern; validating/clamping event-time at ingestion is the standard defense.

### Q3 — Why is exactly-once "a property of the whole pipeline, not the engine"? Give the precise mechanism.
**Testing:** the module's central claim; tests whether the candidate actually understands the boundary between engine guarantees and sink guarantees.
**Answer:** The engine's guarantee (exactly-once *processing*) covers offset tracking and operator state: checkpointed atomically with batch completion, so a restart neither reprocesses a committed batch nor skips an uncommitted one. But writing to the external sink is a separate step from committing that checkpoint; a crash between them can cause a batch's output to be written more than once on retry. Whether that duplicate write matters depends entirely on whether the sink is idempotent (a retried write has no additional effect, e.g. an upsert keyed by record id) or transactional (the whole batch's write either fully lands or fully doesn't, e.g. Delta's `txnAppId`/`txnVersion` idempotent-write tracking). Without one of those two properties at the sink, exactly-once processing inside Spark does not translate to exactly-once *effects* in the destination.
**Follow-up trap:** *"Is the file sink actually exactly-once, or just 'usually fine'?"* — it's the sink most commonly cited as exactly-once because Spark's file-sink commit protocol uses an atomic manifest/rename-based commit that avoids partial files on retry, and duplicate whole-file writes from a retried batch are generally treated as safe under standard consumption patterns (readers process the manifest, not raw directory listings). It's a genuine guarantee for that sink, not a hand-wave, but it's specific to how the file sink's commit protocol works, not a property that transfers to arbitrary sinks.

### Q4 — Your Kafka sink is producing duplicate messages after every job restart. Why, and how do you actually fix it end to end?
**Testing:** practical debugging of the exact failure mode named in the topic notes.
**Answer:** The built-in Kafka sink is at-least-once by default: Kafka's idempotent producer prevents duplicate sends of the *same* message within one producer session/retry, but a retried micro-batch after a restart is effectively a new attempt at writing that batch's rows, which the sink has no cross-batch memory to deduplicate against. Fixing it end to end requires either downstream deduplication (consumers dedupe by an embedded idempotency key/batch id) or building transactional writes yourself via `foreachBatch` using Kafka's transactional producer API coordinated with tracking which Spark batch IDs have already been fully committed, checked before each write attempt.
**Follow-up trap:** *"Doesn't enable.idempotence=true on the producer already solve this?"* — it solves message-level duplicate sends within a single producer session (e.g. a network retry re-sending the same message), not batch-level duplication from an entirely new attempt at the same logical Spark micro-batch after a restart; those are different scopes of "duplicate," and conflating them is the actual bug in most "I turned on idempotence and still get duplicates" incidents.

### Q5 — Design the fix for a state store that has grown from 2M keys to 40M keys over a week and is now causing GC pauses.
**Testing:** practical remediation combining state-store choice and watermark sizing.
**Answer:** First check whether a watermark exists at all and whether it's sized reasonably against real lateness (this state growth pattern often means no watermark, or one so generous it's not effectively bounding anything). Independently of that, switch the state store backend to RocksDB (`RocksDBStateStoreProvider`), which moves state off JVM heap into native, disk-backed storage local to each executor, eliminating the GC pressure regardless of key count; RocksDB comfortably handles tens of millions of keys where the default `HDFSBackedStateStore` (JVM-heap-resident) does not.
**Follow-up trap:** *"Does switching to RocksDB alone fix the underlying growth, or just the symptom?"* — just the symptom (GC pauses); if there's a genuine watermark/window-sizing problem causing state to grow unboundedly, RocksDB buys more runway (disk is cheaper and larger than heap) but the state will still eventually exhaust disk if nothing ever closes windows. Both fixes are usually needed together: correct watermarking to bound growth, RocksDB to handle the legitimately large-but-bounded steady state comfortably.

### Q6 — What output modes exist, and why do stream-stream joins only support one of them?
**Testing:** output-mode mechanics plus the reasoning behind the join restriction, not just memorized support tables.
**Answer:** Append (only new, final rows since the last trigger), update (rows that changed since last trigger), and complete (the entire result table every trigger, viable only for small aggregated results). Stream-stream joins only support append because a join's output is a set of matched row-pairs; Spark has no representation for "this previously-emitted joined row has now changed" the way it does for an aggregate's running total (which naturally has an "old value vs new value" for update mode), so once a joined row is emitted it's final, which is exactly what append mode represents, and update/complete semantics for a join aren't well-defined enough to implement.
**Follow-up trap:** *"What happens to an unmatched row in a stream-stream join if the other side's matching row never arrives?"* — with a watermark on both sides, the row is retained in a join buffer until the watermark passes its event-time-plus-lateness bound, at which point it's dropped as unmatched (or emitted with nulls for the other side, for outer joins); without watermarks on both sides, the join buffer for unmatched rows grows unboundedly, one of the concrete state-explosion causes.

### Q7 — What's the actual difference between `Trigger.Once()` and `Trigger.AvailableNow()`, and why was `Once()` deprecated?
**Testing:** whether "run it once and stop" is understood at the mechanism level, a common scheduled-streaming pattern.
**Answer:** Both process all currently-available data and then stop, useful for running an otherwise-continuous streaming query on a schedule (e.g. hourly via Airflow) instead of leaving it running. `Once()` forces all available data through a single micro-batch regardless of size, which for a large backlog (e.g. after downtime) can create one enormous, hard-to-tune batch. `AvailableNow()` instead processes the available backlog across potentially multiple appropriately-sized batches (respecting the query's normal rate limits like `maxOffsetsPerTrigger`), giving better resource behavior and progress visibility for catching up a large backlog.
**Follow-up trap:** *"If I use AvailableNow on a schedule, do I still need a watermark?"* — yes; watermark semantics and state management are unrelated to the trigger type. If the query is stateful (aggregations, joins), late data and state bounding rules apply exactly the same whether the query runs continuously or is scheduled via `AvailableNow`.

### Q8 — Why does Structured Streaming manage Kafka offsets itself in the checkpoint rather than relying on Kafka consumer group commits?
**Testing:** understanding why offset-tracking design is what makes engine-side exactly-once processing possible at all.
**Answer:** For engine-side exactly-once processing, offset advancement and operator state must be committed atomically with each other, if a batch's state update commits but the corresponding offset advance doesn't (or vice versa), a restart can either reprocess or skip data relative to state. Kafka consumer group offset commits are a separate system, committed independently and not atomically with Spark's own checkpoint, so relying on them would reopen exactly the race condition the checkpoint mechanism exists to close. Managing offsets inside the same checkpoint as operator state keeps the commit atomic from Spark's perspective.
**Follow-up trap:** *"So is the consumer group offset in Kafka just unused?"* — Structured Streaming can still report progress to a consumer group for external monitoring/lag-tracking tools that read consumer group offsets, but that reported position is not what Spark uses for its own recovery; recovery is driven entirely from the checkpoint. Conflating the two is a common source of confusion when someone tries to "rewind" a stream by resetting a Kafka consumer group offset, that has no effect on Spark's checkpointed position.

### Q9 — A sliding window `window("event_time", "1 hour", "5 minutes")` is causing far more state than an equivalent 1-hour tumbling window. Quantify why.
**Testing:** whether the state-multiplication math for sliding windows is understood quantitatively, not just qualitatively.
**Answer:** A sliding window's slide interval determines how many overlapping windows are alive at once: with a 1-hour window and 5-minute slide, any given event falls into `window_size / slide_interval = 60/5 = 12` distinct concurrent windows, versus exactly 1 for a tumbling window of the same size. State (roughly, one entry per open window per group) scales proportionally, so this configuration uses on the order of 12x the state of the tumbling equivalent for the same underlying data and watermark.
**Follow-up trap:** *"When is that 12x cost actually justified?"* — when the business requirement genuinely needs a frequently-updated rolling metric (e.g. "current rolling 1-hour count, refreshed every 5 minutes" for a live dashboard) rather than a metric that's only meaningful once per hour boundary; if the consumer only ever reads the value once per hour anyway, a tumbling window delivers the same useful information at a twelfth of the state cost.

### Q10 — Design the resilience strategy for a stateful streaming job that must survive a full cluster restart with no data loss and no duplicate downstream writes.
**Testing:** synthesis across the whole module, staff-level end-to-end reasoning.
**Answer:** Checkpoint location on durable, versioned storage (S3/ADLS/HDFS) separate from ephemeral cluster storage, so a full cluster teardown doesn't lose the checkpoint. RocksDB state store if state is large, with its own incremental checkpointing to the same durable location. Watermarks sized from real observed lateness on both sides of any join and on every windowed aggregation, monitored as a first-class metric (state size, not just latency). Source must be replayable from the checkpointed offset (Kafka retention long enough to cover the worst-case restart delay; a file source that doesn't delete files before they're processed). Sink must be idempotent or transactional: Delta with `txnAppId`/`txnVersion`, or a custom `foreachBatch` with an idempotency key and a durably tracked last-committed-batch-id check before every write, so a batch retried after restart either has no effect (idempotent) or is skipped entirely if already committed (transactional tracking).
**Follow-up trap:** *"Which piece would you cut first under a deadline?"* — none of the correctness pieces (checkpoint durability, sink idempotency) are safely cuttable, they're what "no data loss, no duplicates" actually means mechanically; the cuttable piece is usually RocksDB (default HDFSBackedStateStore is fine at modest state volumes) and aggressive watermark tuning (a slightly-too-generous watermark costs extra state/memory but doesn't break correctness the way an unmonitored sink does). Naming checkpoint durability and sink idempotency as non-negotiable, and state-store choice as tunable, is the senior framing.

---

## Red flags that fail you

- Claiming "Structured Streaming is exactly-once" without naming which sink and mechanism makes that true.
- Describing a watermark as only "for handling late data" without connecting it to state-size bounding.
- Not knowing that stream-stream joins only support append output mode.
- Recommending Kafka's `enable.idempotence=true` as a complete fix for duplicate rows after a job restart.
- Treating `Trigger.Once()` as still the recommended API (deprecated in favor of `AvailableNow()`).
- Not distinguishing event-time from processing-time when discussing lateness.
- Assuming sliding windows are a free choice with no state cost versus tumbling windows.

## Cheat card

```
MODEL: stream = unbounded input table. Same DataFrame API as batch,
  executed incrementally each trigger, same Catalyst/Tungsten engine.
MICRO-BATCH (default): discrete Spark jobs per trigger, ~100ms-seconds
  latency floor. CONTINUOUS mode: ~1ms target, no aggregations, narrow
  operator support, limited production adoption.

WATERMARK = maxEventTimeSeen - latenessThreshold, recomputed each trigger.
  Window closes + state dropped once window-end < watermark.
  Record older than watermark -> dropped as "too late", not merged.
  Tradeoff: short threshold = small state, more dropped late data.
            long threshold = more completeness, more state/memory.

WINDOWS: tumbling (1x state) < session (native since 3.2) < sliding
  (state x= window_size/slide_interval -- e.g. 1hr/5min slide = 12x state).

OUTPUT MODES: append (new final rows; broadest sink support; REQUIRED for
  stream-stream joins) / update (changed rows; not most file/table sinks)
  / complete (whole result table every trigger; small aggregates only).

STATE STORE: HDFSBackedStateStore (default) = JVM heap, GC pressure at
  scale. RocksDB (built-in since Spark 3.2, set via
  spark.sql.streaming.stateStore.providerClass) = native, off-heap,
  disk-backed, handles 10s of millions of keys.

STATE-EXPLOSION SYMPTOM: state size climbs with no plateau in Streaming
  UI, batch time creeps up, eventual OOM or disk fill. CAUSE: missing/
  too-generous watermark, or an unwatermarked stream-stream join buffer.

TRIGGERS: ProcessingTime(interval) = fixed cadence. Once() DEPRECATED.
  AvailableNow() = drain backlog across multiple sized batches, then
  stop -- the scheduled-run standard. Continuous(interval) = checkpoint
  interval, not batch interval.

EXACTLY-ONCE = ENGINE (offset+state committed atomically per batch,
  real) + SINK (idempotent or transactional, your job). File sink:
  exactly-once via atomic commit protocol "for free." Kafka sink:
  AT-LEAST-ONCE by default; idempotent producer only dedupes within one
  producer session, not across a retried batch after restart -- need
  custom foreachBatch + Kafka transactions for true exactly-once.
Offsets tracked in the CHECKPOINT, not Kafka consumer-group commits --
  that's what makes atomic offset+state commit possible.
```

## Sources

- [Event-time Aggregation and Watermarking in Apache Spark's Structured Streaming — Databricks](https://www.databricks.com/blog/2017/05/08/event-time-aggregation-watermarking-apache-sparks-structured-streaming.html) — accessed 2026-08-01
- [Optimize stateful processing with watermarks — Databricks docs](https://docs.databricks.com/gcp/en/ldp/stateful-processing) — accessed 2026-08-01
- [RocksDB State Store — The Internals of Spark Structured Streaming](https://books.japila.pl/spark-structured-streaming-internals/rocksdb/) — accessed 2026-08-01
- [Configure RocksDB state store on Databricks](https://docs.databricks.com/aws/en/structured-streaming/rocksdb-state-store) — accessed 2026-08-01
- [Understanding Triggers with Databricks Spark Structured Streaming — Medium](https://medium.com/towards-data-engineering/understanding-triggers-with-databricks-spark-structured-streaming-default-processingtime-and-be39b68ea6d6) — accessed 2026-08-01
- [Select an output mode for Structured Streaming — Databricks docs](https://docs.databricks.com/gcp/en/structured-streaming/output-mode) — accessed 2026-08-01
- ['Exactly Once' processing with Spark Structured Streaming — Medium](https://sbanerjee01.medium.com/exactly-once-processing-with-spark-structured-streaming-f2a78f45a76a) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
