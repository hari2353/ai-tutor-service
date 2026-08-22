# Batch vs Stream Ingestion, CDC, Idempotent Loads, Backfills, Late Data

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-ingestion` · **Tags:** pipelines

## The 30-second version

Ingestion comes down to three questions: how fresh does this actually need to be, can the source tell you about deletes, and will a retry duplicate data. Batch is the default until something concrete needs sub-minute freshness — streaming buys latency at real infra and correctness cost. Query-based incremental extraction (`updated_at > watermark`) is cheap but structurally blind to hard deletes and to updates that never touch the tracking column; log-based CDC (Debezium tailing the binlog/WAL) fixes both by reading the transaction log directly. At-least-once delivery is the default everywhere, so every load has to be idempotent — merge/upsert on a natural key with a monotonic guard column, never a plain insert — or a retry silently duplicates rows. The most common silent failure is a stuck watermark: row counts look normal, nothing errors, and a downstream aggregate just drifts.

## Why this gets asked

Because "we ingested data from Postgres into the warehouse" is a sentence a junior and a principal both say, and the difference only shows up in the follow-ups. The interviewer has been paged for a dashboard that quietly drifted for three weeks because an incremental watermark silently stopped advancing past a NULL `updated_at`, and for a duplicate-charge incident caused by a Kafka consumer retry hitting a non-idempotent insert. They want to know whether you reason about *delivery guarantees* (at-least-once is the default everywhere; exactly-once is a property you build, not one you get) and whether you've actually hit the query-based-CDC-misses-deletes trap in production, not read about it.

---

## Lineage: past → present → future

**What came before.** The first generation of ingestion was the nightly `.csv` dump: a cron job on the OLTP replica ran `SELECT * FROM orders`, wrote a file, and an ETL job loaded it into the warehouse before business hours. This worked while data was small and the business tolerated next-day freshness. The pain that killed it was threefold: full extracts don't scale past a few million rows without saturating the source or the network window, they cannot represent deletes cleanly (a row missing from today's dump could mean "deleted" or "extract failed halfway"), and every hour of ingestion latency was an hour the business was making decisions on stale numbers. Informatica and DataStage-era ETL tools formalized this pattern in the 1990s-2000s but didn't remove the core constraint: full-refresh batch does not scale with data volume or freshness requirements.

**Where it stands now.** The consensus split into two co-existing tracks rather than one replacing the other. **CDC (change data capture)**, popularized in open source by Debezium (2016, built on Kafka Connect) reading database transaction logs (`binlog` for MySQL, WAL for Postgres, redo logs for Oracle), became the standard for OLTP-to-warehouse replication because it captures every row-level change including deletes with sub-second latency and near-zero source load. Alongside it, batch/micro-batch extraction (Fivetran, Airbyte, custom Spark/Airflow jobs) remains dominant for SaaS APIs and files, where there is no transaction log to tail. The live disagreement is not "batch vs streaming" in the abstract, it's **how fresh does this specific table actually need to be**, and most teams over-invest in streaming CDC for tables that get queried once a day. ELT (load raw, transform in-warehouse with dbt) displaced ETL (transform before load) as the default pattern because cheap columnar compute made in-warehouse transforms faster to iterate on than pre-load transform code, and it decouples "did the data land" from "is the data correct" (see `T18-data-quality`).

**Where it's heading.** Real-time OLAP (ClickHouse, Apache Pinot, Apache Druid) with sub-second CDC-to-queryable latency is moving from "specialist streaming shop" to "default option for user-facing analytics," with fairly high confidence given adoption at Uber, LinkedIn, and Stripe by 2026. **Lakehouse table formats with CDC-native merge support** (Iceberg's row-level deletes, Delta's `MERGE INTO`) are collapsing the old distinction between "streaming into Kafka" and "batch-loading a warehouse" into a single continuous-ingestion pattern where the storage layer itself handles upserts efficiently. More speculative: schema-inference and drift-handling assisted by LLMs (auto-generating a mapping when a source API adds a field) exists in early vendor tooling but should not be trusted unsupervised on anything feeding a financial or compliance report yet.

---

## Mental model

```
                         SOURCE                         WAREHOUSE
                    ┌───────────────┐                ┌───────────────┐
  FULL SNAPSHOT      │ entire table  │──dump─────────▶│ overwrite      │
  (simple, expensive)│ every run     │                │ full table     │
                    └───────────────┘                └───────────────┘

                    ┌───────────────┐   WHERE          ┌───────────────┐
  INCREMENTAL        │ updated_at >  │──watermark─────▶│ append/merge   │
  (query-based CDC)  │ last_watermark│                 │ new+changed    │
                    └───────────────┘                 └───────────────┘
                    MISSES: hard deletes, rows updated without
                    bumping updated_at, backdated writes

                    ┌───────────────┐   binlog/WAL      ┌───────────────┐
  LOG-BASED CDC       │ transaction   │──tail───────────▶│ Kafka topic   │──▶ merge
  (Debezium)          │ log           │  (row events:     │ (I/U/D events)│
                    └───────────────┘   insert/update/  └───────────────┘
                                          delete, in order)
```

The vertical axis that actually matters in an interview is **latency vs blast radius**: a full snapshot is slow but self-healing (rerun it, it's correct); log-based CDC is fast but every ordering bug or dropped event replicates immediately into every downstream consumer. Batch trades latency for simplicity and idempotence; streaming trades simplicity for latency and correctness surface area.

---

## How it actually works

### Batch vs micro-batch vs stream — the honest tradeoff

| | Batch | Micro-batch | Streaming |
|---|---|---|---|
| Typical latency | hours to 1 day | 1-15 min | sub-second to a few seconds |
| Throughput model | large fixed windows | small fixed windows | continuous, per-event |
| Infra cost | cheapest (spin up, run, tear down) | moderate (always-on scheduler) | most expensive (always-on cluster/broker) |
| Failure recovery | rerun the whole window, cheap | rerun one small window | replay from offset, needs exactly-once sink design |
| Typical stack | Airflow + Spark/dbt, nightly | Airflow every 5-15 min, or Spark Structured Streaming with a trigger interval | Kafka + Flink/Spark Structured Streaming (continuous) |

The honest answer to "should this be streaming" is almost always **no** unless a human or an automated decision is waiting on the data within seconds. A finance close report that runs once a day does not need sub-second CDC; it needs correctness. A fraud-scoring feature store does. Teams that default to streaming for everything pay 3-10x the infra cost (always-on Kafka + Flink cluster vs a nightly Spark job that runs for 20 minutes) for freshness nobody consumes. **When NOT to use streaming**: any table where the query pattern is "as of this morning" — building CDC pipelines for a table that's queried once a day in a BI dashboard is pure cost with no benefit, and it adds an entire class of ordering and exactly-once bugs you don't need.

### Full snapshot vs incremental vs CDC

- **Full snapshot** — extract the whole table every run, overwrite the target. Correct by construction (no watermark to get wrong), but doesn't scale: a 200M-row table at 500 rows/sec extraction throughput is over 3 days per run. Use for small dimension tables (<1M rows) or sources with no reliable change-tracking column.
- **Incremental (query-based)** — `WHERE updated_at > :last_watermark`. Cheap, works with any source that has a trustworthy `updated_at`, but has two structural blind spots that are a favorite interview trap:
  1. **Hard deletes are invisible.** A row that no longer exists produces no row in the query result — there's nothing to diff against unless you also do periodic full reconciliation or the source uses soft deletes (`deleted_at`).
  2. **Rows updated without bumping the tracking column are invisible.** A backfill script that does a raw `UPDATE` without going through the ORM, or a migration that touches `updated_at`-less legacy columns, silently skips those rows forever.
- **Log-based CDC (Debezium, AWS DMS, Fivetran's log-based connectors)** — tails the source's transaction log (MySQL binlog in row-based format, Postgres logical replication slot reading WAL, Oracle LogMiner/redo logs) and emits every insert/update/delete as an ordered event, including deletes and any update regardless of which column changed. Near-zero query load on the source (it's not running `SELECT`s, it's reading a log the database already writes) and latency in the 100ms-2s range end to end. Cost: operational complexity (replication slots that aren't consumed fast enough grow unboundedly and can fill the source's disk — a real production incident class), and you need a durable sink (Kafka) plus schema registry to handle source DDL changes gracefully.

**The observable symptom of a broken incremental watermark**: row counts look completely normal — the pipeline reports "12,403 rows loaded" every night, no errors, no alerts — while a downstream aggregate (say, monthly active users, or total order value) quietly drifts from the source of truth by a fraction of a percent per day. Nobody notices until a quarterly reconciliation against the source system turns up a gap, at which point the fix requires figuring out how long the watermark has been stuck and running a full backfill (see `T18-backfill-replay`) against however many weeks of missed hard-deleted or silently-updated rows. This is the single most common "silent" data engineering incident, precisely because nothing throws an exception.

### Schema drift on ingest

Sources change shape without warning: a SaaS API adds a field, a producer team renames a column, a nested JSON blob gains a new key. Three postures, in order of how much they cost you later:

1. **Fail the load on any unexpected column** (strict schema, reject unknowns). Safest for anything feeding financial reporting; loudest failure mode, so you find out immediately.
2. **Accept new columns, quarantine or alert on type changes** (permissive schema, evolve additively). The common default for analytics warehouses — a new `string` field showing up doesn't break the pipeline, but an existing `int` column suddenly emitting strings does.
3. **Accept everything into a raw/variant column** (schema-on-read, e.g. Snowflake `VARIANT`, BigQuery `JSON`). Maximum ingest resilience, defers the correctness problem to whoever queries it — fine for a bronze/raw layer (see `T18-data-modeling-e2e`), a real liability if silver/gold consumers query the variant column directly without a contract.

### Idempotent loads — the load-bearing concept of this module

**At-least-once delivery is the default everywhere** — Kafka consumers can reprocess a message after a rebalance, an Airflow task can be retried after a worker dies mid-write, an HTTP webhook can be redelivered after a timeout the receiver actually processed. At-least-once delivery plus a non-idempotent load equals silent duplication: the same order row gets inserted twice, and unless something is watching row counts against an expected cardinality, nobody notices until a revenue number is 2% too high.

Idempotency is achieved one of three ways:

1. **Natural key + merge/upsert.** `MERGE INTO target USING staging ON target.order_id = staging.order_id WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...`. Reprocessing the same batch is a no-op change. This is the default for CDC-fed tables.
2. **Deterministic dedup window.** Insert into a staging table, then `ROW_NUMBER() OVER (PARTITION BY natural_key ORDER BY event_time DESC) = 1` before promoting — needed when the source doesn't guarantee uniqueness within a batch (e.g., a Kafka topic that can deliver the same event twice within one micro-batch).
3. **Idempotency key on the write path.** For event-driven ingestion (webhooks, queue consumers), generate or receive a UUID per logical event and use `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING`, checking the affected-row count rather than reading-then-writing (a read-then-write has a race window).

```sql
-- Idempotent upsert, the load-bearing pattern for CDC-fed tables
MERGE INTO warehouse.orders AS tgt
USING staging.orders_batch AS src
ON tgt.order_id = src.order_id
WHEN MATCHED AND src.updated_at > tgt.updated_at THEN
  UPDATE SET tgt.status = src.status, tgt.total = src.total, tgt.updated_at = src.updated_at
WHEN NOT MATCHED THEN
  INSERT (order_id, status, total, updated_at)
  VALUES (src.order_id, src.status, src.total, src.updated_at);
```

Note the `AND src.updated_at > tgt.updated_at` guard — without it, an out-of-order redelivery (a stale CDC event replayed after a newer one already landed) overwrites newer data with older data. This is a second, subtler idempotency bug: the merge is idempotent against *duplicates* but not against *out-of-order* delivery unless you guard on a monotonic column.

### Late-arriving data and dead-letter handling

Late data is any event whose event-time is older than the watermark already processed — a mobile client buffering offline for six hours and flushing events once reconnected, or a source database's replication lag delivering a change 40 seconds after it committed. Two structural responses:

- **A grace period / reprocessing window**: hold the partition open for N minutes/hours past the watermark before considering it final, at the cost of added latency for everyone. Spark Structured Streaming's watermark (`withWatermark("event_time", "10 minutes")`) and Flink's allowed lateness implement this natively.
- **Accept it late and reprocess the affected partition**: let the aggregate be provisionally wrong, then correct it via a targeted backfill once the late data is detected (see `T18-backfill-replay` for the mechanics and risk).

**Dead-letter handling**: rows that fail schema validation, type coercion, or a business rule at ingest should never silently drop or crash the whole batch. Route them to a dead-letter table/topic with the original payload, the error, and a timestamp, and alert on volume (not on every row — see the alert-fatigue discussion in `T18-data-quality`). A pipeline that crashes the entire nightly load because one row out of 2 million had a malformed timestamp is itself an availability bug, not a correctness win.

---

## Build it from scratch

A minimal idempotent, watermark-driven incremental loader — the shape of the code an interviewer might ask you to sketch on a whiteboard.

```python
# untested sketch — illustrates the watermark + idempotent-merge pattern, not production code
import time
from dataclasses import dataclass

@dataclass
class Watermark:
    table: str
    last_value: str   # ISO timestamp of the last successfully processed updated_at

def load_watermark(table: str) -> Watermark:
    # in production: read from a small control table in the warehouse itself,
    # never from a file on a worker — workers are ephemeral and interchangeable
    ...

def save_watermark(wm: Watermark) -> None:
    ...

def extract_incremental(conn, table: str, since: str, page_size: int = 5000):
    """Query-based incremental extract. Caller is responsible for knowing
    this misses hard deletes and non-updated_at-bumping writes (see module body)."""
    offset = 0
    while True:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE updated_at > %s "
            f"ORDER BY updated_at LIMIT %s OFFSET %s",
            (since, page_size, offset),
        ).fetchall()
        if not rows:
            return
        yield rows
        offset += page_size

def run(conn, warehouse, table: str):
    wm = load_watermark(table)
    max_seen = wm.last_value
    for batch in extract_incremental(conn, table, wm.last_value):
        # idempotent upsert keyed on natural key + monotonic guard column,
        # so a retried batch (at-least-once redelivery) is a safe no-op
        warehouse.merge_upsert(
            target=table,
            rows=batch,
            key="id",
            guard_column="updated_at",   # prevents stale out-of-order overwrite
        )
        max_seen = max(max_seen, max(r["updated_at"] for r in batch))

    # only advance the watermark AFTER every batch in this run committed —
    # advancing early and then failing mid-run is exactly how you get a gap
    # that looks like a broken watermark six weeks later
    save_watermark(Watermark(table=table, last_value=max_seen))
```

The two details that separate this from a toy script: the watermark only advances after every batch in the run has committed (advance-then-fail is how gaps happen), and the merge carries a guard column so a retried or redelivered batch cannot regress newer data. Full version with a dead-letter sink and schema-drift detection: `labs/py/18-ingestion-lab/` (reference the pattern in `labs/py/17-dimensional-lab/` for the merge mechanics).

---

## How it's done in production

**Managed ELT connectors** — Fivetran, Airbyte, Stitch. Handle schema drift, retries, and incremental state for hundreds of common sources (Salesforce, Stripe, SaaS APIs) so you don't write custom extractors. Cost scales with rows/monthly active rows synced, which becomes the actual argument for building custom extraction once volume is high enough that the per-row pricing exceeds engineering time.

**CDC** — Debezium (open source, Kafka Connect-based) is the default for self-hosted log-based CDC off MySQL/Postgres/MongoDB/SQL Server. AWS DMS (Database Migration Service) is the managed equivalent inside AWS, commonly used to replicate RDS/Aurora into S3 or Redshift. Both need a durable landing zone (Kafka topic or S3) between source and warehouse so a downstream outage doesn't force replaying from the source's transaction log, which has a finite retention window (MySQL binlog retention is commonly 1-7 days by default — if your Kafka Connect cluster is down for longer than that, you lose the ability to catch up incrementally and need a full re-snapshot).

**Orchestration** — see `T18-airflow` for how these extracts are actually scheduled, and `T18-scheduling-triggering` for the honest tradeoff between cron-triggered batch and event-triggered ingestion (S3 event → Lambda → load, EventBridge-scheduled extracts, or Airflow Datasets/Assets triggering downstream DAGs the moment upstream lands).

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Row counts look normal, downstream aggregate drifts by a small % daily | Incremental watermark stuck on hard deletes or non-`updated_at`-bumping writes | Switch to log-based CDC, or add a periodic full-reconciliation job that diffs counts against source |
| Duplicate rows / inflated revenue numbers after a retry or redeploy | At-least-once delivery into a non-idempotent (plain `INSERT`) load | Merge/upsert on natural key, or idempotency key with `ON CONFLICT DO NOTHING` |
| Newer data overwritten by an older, redelivered event | Merge with no monotonic guard column | Add `WHEN MATCHED AND src.updated_at > tgt.updated_at` |
| Replication slot / binlog growing unboundedly, source disk filling | CDC consumer (Kafka Connect) down or lagging longer than log retention | Alert on replication slot lag, autoscale/restart the consumer, cap max lag with a paging alert |
| Pipeline crashes entirely on one malformed row | No dead-letter routing, hard failure on first bad row | Quarantine bad rows to a dead-letter table, alert on volume not per-row |
| A batch reprocessed after a crash produces different totals than the first (failed) attempt | Non-idempotent partial write — first attempt partially committed before failing | Wrap the load in a transaction scoped to the whole batch, or make every write idempotent so partial + retry converges |
| New source field silently missing from the warehouse for weeks | Strict schema silently dropping unknown columns instead of alerting | Alert on schema-drift detection, don't just drop-and-continue |

---

## Tradeoffs & when NOT to use it

- **Do not build streaming CDC for a table queried once a day.** The infra cost (always-on Kafka + connector + schema registry) and the added correctness surface area (ordering, exactly-once sinks, replication slot management) buy freshness nobody uses. A nightly batch job is simpler, cheaper, and self-healing on rerun.
- **Do not use query-based incremental extraction on a table with hard deletes that matter downstream.** It is structurally blind to them; either move to log-based CDC or accept the gap and document it (see "when not to backfill" in `T18-backfill-replay` — sometimes the honest fix is documenting the limitation, not engineering around it).
- **Do not skip idempotency because "it's just a batch job that runs once a day."** Airflow retries failed tasks by default; a task killed mid-write and retried is at-least-once delivery whether or not you call it streaming.
- **Full snapshot is still the right choice for small, slowly-changing dimension tables** (currency codes, a few thousand product categories) — the complexity of incremental/CDC machinery isn't worth it under roughly 1M rows with no urgent freshness requirement.
- **CDC is the wrong tool when the source has no accessible transaction log** — most SaaS APIs (Salesforce, HubSpot, Stripe) expose only a REST/webhook interface, so "CDC" there really means incremental polling or subscribing to the vendor's own webhook/event stream, not tailing a binlog you don't have access to.

---

## Interview questions

### Q1 — Walk through why query-based incremental extraction misses deletes.
**Testing:** whether this is understood mechanically or just recited as a bullet point.
**Answer:** `WHERE updated_at > watermark` only returns rows that still exist and were touched after the watermark. A hard-deleted row produces zero result rows — there's nothing in the query result to signal "this used to exist and is now gone." The only ways to detect it are periodic full reconciliation (diff source and target row counts/keys), soft deletes (a `deleted_at` column, itself a schema change the source team must adopt), or moving to log-based CDC, which emits an explicit delete event from the transaction log regardless of how the row was removed.
**Follow-up trap:** *"What about updates that don't bump `updated_at`?"* — same blind spot, different cause: a raw `UPDATE` bypassing the ORM/trigger that maintains the timestamp, or a backfill script writing directly to the table. This is why log-based CDC, which tails the transaction log itself rather than trusting an application-maintained column, is structurally more complete — it captures every write regardless of whether the application remembered to bump a timestamp.

### Q2 — Your incremental pipeline reports normal row counts every night, but finance flags a 3% revenue discrepancy after quarter close. Diagnose it.
**Testing:** the named failure mode from this module, applied cold.
**Answer:** This is the classic silently-stuck-watermark symptom: the pipeline is functioning (extracting rows, loading them, logging a plausible count) but missing a category of changes the watermark can't see — hard deletes, or updates to a legacy path that doesn't bump `updated_at`. Row counts look fine because the pipeline is correctly loading everything it's told to look at; the gap is in what it's told to look at. Fix: reconcile source and target counts/checksums on the affected table, find the first date the gap appears, and run a targeted backfill (see `T18-backfill-replay`) for that window, ideally moving the table to log-based CDC afterward so it can't recur the same way.
**Follow-up trap:** *"How would you have caught this before finance did?"* — a periodic (e.g. weekly) full-reconciliation job comparing source `COUNT(*)` / a checksum against the warehouse table, alerting on drift past a threshold. This is a freshness/volume data-quality check (`T18-data-quality`), and its absence is the actual root cause, not the watermark bug itself — watermark blind spots are a known, structural limitation of the approach; not detecting them for a full quarter is a monitoring gap.

### Q3 — Explain the amplification risk of "at-least-once delivery + non-idempotent load."
**Answer:** At-least-once is the default guarantee almost everywhere (Kafka consumer rebalances, Airflow task retries, webhook redelivery on timeout) — it means a message or task can be processed more than once, never less. If the load itself is a plain `INSERT` with no natural-key constraint, every redelivery inserts a duplicate row. This isn't a rare edge case; it's the default outcome of combining a common delivery guarantee with a naive write path, and it silently inflates any aggregate built on top (revenue, counts) without throwing an error.
**Follow-up trap:** *"How do you get exactly-once, then?"* — you don't get it from the delivery layer; you build it at the write layer via idempotency: merge/upsert on a natural key, or a unique constraint plus `ON CONFLICT DO NOTHING` checked by affected-row count. "Exactly-once processing" is really "at-least-once delivery plus an idempotent sink," and saying that distinction out loud is the senior signal.

### Q4 — When would you deliberately choose batch over streaming, even though streaming is technically available?
**Answer:** Whenever nothing downstream consumes sub-minute freshness — a finance close report, a weekly cohort analysis, most internal BI dashboards. Streaming's cost isn't just infra spend (an always-on Kafka + Flink/Spark Structured Streaming cluster vs a 20-minute nightly Spark job); it's an entire additional correctness surface: exactly-once sink semantics, watermarks and allowed lateness, ordering guarantees, and a harder debugging story when something goes wrong at 2am. Batch is simpler, cheaper, and self-healing on rerun (rerun the whole window, get a correct answer) in a way continuous streaming pipelines generally are not.
**Follow-up trap:** *"Isn't streaming strictly more capable, so why not always use it?"* — capability isn't free. A team that defaults to streaming for a table queried once a day is paying continuously for a class of bugs (late data, out-of-order events, replication slot lag) it doesn't need to have. The senior answer names the actual latency requirement and works backward from it, rather than picking the more impressive-sounding architecture.

### Q5 — Design the ingestion for a table where deletes matter and freshness needs to be under a minute.
**Testing:** synthesizing CDC + idempotency + orchestration into one answer.
**Answer:** Log-based CDC (Debezium reading the binlog/WAL) into a Kafka topic, with a consumer that merges into the warehouse on a natural key with a monotonic guard column (to survive redelivery and out-of-order events safely). Deletes arrive as explicit tombstone/delete events from the log and are applied as `DELETE` or a soft-delete flag in the merge. Monitor replication slot lag with a paging alert, since an unconsumed slot grows unboundedly and can fill the source database's disk.
**Follow-up trap:** *"What happens if the Kafka Connect cluster is down for four days and your binlog retention is two?"* — you've lost the ability to catch up incrementally from where you left off; you need a full re-snapshot of the table (Debezium supports this, but it's expensive and re-processes the whole table through your merge logic). This is the real argument for setting binlog/WAL retention comfortably longer than your worst-case CDC-consumer downtime, and for alerting on lag well before retention is exhausted, not after.

### Q6 — What's the difference between ETL and ELT, and why did the industry move toward ELT?
**Answer:** ETL transforms data before loading it into the warehouse (transform logic lives in a separate tool — Informatica, custom Spark jobs — outside the warehouse). ELT loads raw data first, then transforms it in-warehouse (dbt models running as SQL against the loaded raw tables). The shift happened because cheap columnar compute (Snowflake, BigQuery, ClickHouse) made in-warehouse transforms fast enough to be practical, and because ELT decouples "did the data land" (an ingestion concern) from "is the data correct/shaped right" (a transformation concern, testable with dbt tests independently of the load).
**Follow-up trap:** *"Is ELT strictly better?"* — no: ELT means raw, possibly sensitive or messy data lands in the warehouse before any cleaning, which has real governance and PII-handling implications or you're one `SELECT *` away from exposing something you shouldn't. Some regulated environments still require pre-load masking/transformation (ETL) precisely because "raw" cannot legally land anywhere first, even temporarily.

### Q7 — How do you handle a source schema change (a new field appears) without breaking the pipeline?
**Answer:** Depends on the layer. At the raw/bronze layer (see `T18-data-modeling-e2e`), the safest default is schema-on-read or permissive additive evolution — accept the new field, don't fail the load, and let it flow through as an additional column or into a variant/JSON column. At silver/gold, where a contract exists (`T18-data-quality`), a *type* change to an existing field (int becomes string) should fail loudly, while a genuinely new, unused field should not.
**Follow-up trap:** *"What if the new field replaces an old one that other consumers still read?"* — that's a breaking contract change regardless of how gracefully ingestion handles it; the fix is a data contract with a deprecation window (dual-write old and new field for N weeks) communicated to consumers, not a purely ingestion-side decision. Ingestion can absorb the *shape* change; it cannot unilaterally decide the *semantic* migration is safe for every downstream consumer.

### Q8 — What's a dead-letter queue for in an ingestion pipeline, and what should trigger an alert versus just logging?
**Answer:** A dead-letter table/topic captures rows that fail validation, type coercion, or a business rule at ingest, along with the original payload and the error, so a single malformed row doesn't crash or block the entire batch. Alerting should fire on *volume* crossing a threshold (e.g., dead-letter rate exceeds 0.1% of the batch, or exceeds a fixed count) rather than per-row, because per-row alerting on a pipeline processing millions of rows nightly produces alert fatigue and the alert gets muted within a week (see the anti-pattern discussion in `T18-data-quality`).
**Follow-up trap:** *"What if the dead-letter volume is small but the rows are high-value (large orders)?"* — volume-based thresholds alone miss this; pair the volume alert with a value-based or business-criticality check on specific tables (e.g., any dead-lettered row over $10k GMV pages immediately, everything else rolls up into a daily digest).

### Q9 — Compare Debezium/log-based CDC against AWS DMS. When would you pick each?
**Answer:** Both do log-based CDC. Debezium is open source, Kafka Connect-native, gives you the raw change stream as Kafka topics you own and can fan out to multiple consumers, and requires you to run and operate Kafka Connect yourself. AWS DMS is managed, integrates natively with RDS/Aurora sources and S3/Redshift targets, and is the lower-operational-overhead choice inside an all-AWS stack, at the cost of less flexibility in the event format and fan-out pattern. Pick Debezium when you need multiple independent downstream consumers off one change stream or you're not fully AWS; pick DMS when the destination is S3/Redshift and you want to avoid operating Kafka Connect yourself.
**Follow-up trap:** *"Does either give you exactly-once out of the box?"* — no. Both are at-least-once at the event-delivery layer (a connector restart can redeliver events already processed); exactly-once still has to be engineered at the merge/sink layer via idempotent upserts, same as any other CDC consumer.

### Q10 — A backfill script updates 50,000 rows directly via `UPDATE` outside the application. Your incremental pipeline is query-based on `updated_at`. What happens?
**Testing:** connecting the query-based-CDC blind spot to a concrete operational scenario.
**Answer:** If the raw `UPDATE` doesn't touch `updated_at` (common when a DBA or script bypasses the ORM/trigger that normally maintains it), those 50,000 rows are permanently invisible to the incremental extractor — they already existed before the watermark, they were changed, but nothing in the queryable state signals "re-extract me." The warehouse silently continues serving stale versions of those rows indefinitely, with no error anywhere.
**Follow-up trap:** *"How do you prevent this operationally, not just detect it after the fact?"* — require any direct/bulk update against a CDC-source table to either touch the tracked timestamp explicitly or go through log-based CDC instead of query-based incremental, since log-based CDC doesn't depend on the write path remembering to maintain a column at all — it sees every committed transaction regardless of how it was written.

### Q11 — How would you size a dead-letter and retry strategy for a webhook-based ingestion endpoint that a third party can redeliver up to 5 times over 24 hours?
**Answer:** Every webhook handler needs an idempotency key check (the third party's event ID, if provided, or a hash of the payload) before any write, with a dedup store (Redis with TTL longer than 24h, or a unique constraint on the event ID) so redeliveries 2 through 5 are no-ops rather than duplicate inserts. Failures that aren't transient (malformed payload) go to a dead-letter table immediately rather than being retried, since retrying a permanently malformed payload 5 times just delays detection.
**Follow-up trap:** *"What if the third party's event ID isn't guaranteed unique across their own retries?"* — fall back to a content hash of the payload plus a coarse time bucket as the dedup key; it's not perfect (two genuinely distinct events with identical payloads in the same window collide) but it's a documented, bounded risk versus an unbounded one.

---

## Red flags that fail you

- Describing "we do incremental loads" without knowing what it structurally misses (deletes, non-timestamp-bumping updates).
- Treating "batch" and "streaming" as a maturity ladder where streaming is always the better answer.
- Not knowing that at-least-once is the default delivery guarantee almost everywhere, and that idempotency is something you build, not something the messaging layer gives you for free.
- Proposing a merge/upsert with no monotonic guard column, allowing out-of-order redelivery to regress data.
- Suggesting per-row alerting on dead-letter volume for a multi-million-row nightly batch.
- Not having a story for schema drift beyond "the pipeline would just fail."

---

## Cheat card

```
LATENCY/COST   batch: hrs-1d, cheapest, reruns cleanly
               micro-batch: 1-15min, moderate
               streaming: sub-sec, most expensive, hardest to debug

EXTRACTION     full snapshot: correct by construction, doesn't scale (>1M rows)
               incremental (query, updated_at>watermark): cheap, MISSES hard
                 deletes + non-timestamp-bumping updates
               log-based CDC (Debezium/DMS, tails binlog/WAL): captures
                 everything incl. deletes, near-zero source load, ~100ms-2s
                 latency, needs durable landing zone (Kafka) + schema registry

WATERMARK BUG  symptom: row counts look normal, downstream aggregate drifts
               slowly, no errors thrown. Root cause: hard deletes or
               non-bumped updates invisible to query-based incremental.
               Fix: full reconciliation job + move to log-based CDC.

IDEMPOTENCY    at-least-once delivery is the DEFAULT (Kafka rebalance,
                 Airflow retry, webhook redelivery)
               at-least-once + non-idempotent load = silent duplication
               fix: merge/upsert on natural key + monotonic guard column,
                 or idempotency key + INSERT...ON CONFLICT DO NOTHING
                 (check affected-row count, never read-then-write)

LATE DATA      grace period / watermark+allowed-lateness (Spark/Flink) OR
                 accept late + targeted backfill after detection

DEAD-LETTER    quarantine bad rows, don't crash the batch. Alert on VOLUME
                 crossing a threshold, not per-row (alert fatigue).

ELT > ETL      load raw first, transform in-warehouse (dbt) — decouples
                 "did it land" from "is it correct". Tradeoff: raw/messy
                 data lands before cleaning — governance implication.

BINLOG RETENTION   commonly 1-7 days MySQL default. CDC consumer downtime
                   longer than retention = forced full re-snapshot.

CROSS-REF   what starts a run -> T18-scheduling-triggering
            re-running safely -> T18-backfill-replay
            where ingested data lands -> T18-data-modeling-e2e (bronze)
```

## Sources

- [Log-Based vs Query-Based CDC: Comparison — Conduktor](https://www.conduktor.io/glossary/log-based-vs-query-based-cdc-comparison) — accessed 2026-08-01
- [Five Advantages of Log-Based Change Data Capture — Debezium](https://debezium.io/blog/2018/07/19/advantages-of-log-based-change-data-capture/) — accessed 2026-08-01
- [Debezium Features — Debezium Documentation](https://debezium.io/documentation/reference/stable/features.html) — accessed 2026-08-01
- [Less is More: A Case for Query Based Change Data Capture](https://medium.com/@christinataylor0926/less-is-more-a-case-for-query-based-change-data-capture-a3b22349dba6) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
