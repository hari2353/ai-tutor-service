# BigQuery, Dataflow/Beam, Pub/Sub, Looker

> **Track:** C-GCP Google Cloud Atlas · **Time:** 3.0h · **Prereqs:** `C-GCP-iam`, `C-GCP-storage-db` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-data` · **Tags:** data, analytics, critical

## The 30-second version

BigQuery is fully serverless and **scan-billed by default** — on-demand pricing charges **$6.25/TiB scanned** (first 1 TiB/month free) with no cluster to size, which inverts the entire cost-optimization mindset coming from Redshift: instead of "is my cluster big enough," the question becomes "how much data does this query actually touch." **Partitioning** (one DATE/TIMESTAMP/INTEGER column, 4,000-partition hard cap) and **clustering** (up to four columns, auto-sorted, no partition limit) are the two levers that shrink bytes scanned, and combined they can cut query cost by an order of magnitude. Past a scan volume around **400-500 TiB/month**, capacity pricing (**Editions**: Standard $0.04, Enterprise $0.06, Enterprise Plus $0.10 per slot-hour, autoscaling by default) beats on-demand — this is the one number worth memorizing for a cost-modeling question. **Materialized views** give incremental, auto-maintained pre-aggregation without a cron job; **BI Engine** gives sub-second in-memory acceleration for dashboards. Dataflow is GCP's fully managed Apache Beam runner — the same unified batch/streaming programming model as everywhere else, with **Streaming Engine** offloading windowing/state from workers so autoscaling is fast and worker VMs stay thin. Pub/Sub is **at-least-once by default** with a GA **exactly-once delivery** mode that trades latency for a formal no-redelivery-after-ack guarantee, and **ordering keys** (opt-in, single-region-per-key) for strict per-entity sequencing — the opposite default of Kinesis, which gives per-shard ordering for free but leaves de-duplication entirely to the consumer. Looker (LookML, six-figure annual contracts) is the enterprise semantic layer; Looker Studio (free, Pro tier $9/user/month) is a lightweight dashboard tool — conflating the two in an interview is an instant tell that you haven't used either.

## Why this gets asked

The interviewer has watched an engineer move from Redshift to BigQuery, keep doing `SELECT *` out of habit because "it's just SQL," and get a surprise five-figure bill from a handful of dashboard refreshes scanning a multi-TB unpartitioned table. They have also watched the opposite mistake: someone provisioning BigQuery Editions slots like an EC2 instance, sizing for peak load 24/7 when on-demand would have been an order of magnitude cheaper for a spiky workload. On the streaming side, they've debugged a pipeline that assumed Pub/Sub gives Kafka-style partition ordering for free and shipped a state-machine bug the day traffic patterns changed. They want to know whether you actually understand *why* the billing model is different, not just that the sticker price per TB looks different from Redshift's per-node-hour number.

---

## Lineage: past → present → future

**What came before.** Google's internal analytics lineage runs through **Dremel** (2010 paper), the columnar, tree-architecture query engine that let engineers run ad-hoc SQL over petabyte-scale datasets in seconds without a DBA provisioning a cluster first — Dremel is BigQuery's direct ancestor, launched externally in 2010 and GA in 2011. The pain Dremel solved: MapReduce-based analysis (Hive on top of Hadoop, the mainstream answer circa 2008-2012) required minutes-to-hours for interactive queries and forced analysts to either wait or pre-aggregate everything, because the execution model was batch-job-shaped, not query-shaped. AWS's answer to the same interactive-SQL-at-scale pressure was **Redshift** (2012), built on ParAccel's MPP architecture — a provisioned, cluster-based columnar warehouse that was a massive improvement over Hive-on-Hadoop but kept the fundamental "you own a cluster, you size it, you pay for it whether it's busy or idle" model that mainframe and on-prem warehouse operators already knew. On the streaming side, the pre-Beam world was fragmented: Storm, Spark Streaming (micro-batch, not true streaming), and Google's own internal MillWheel and FlumeJava papers (2010, 2013) that never had one unified public programming model — every team wrote its own windowing and watermark logic, and porting a pipeline from batch to streaming meant a rewrite.

**Where it stands now.** BigQuery decoupled storage from compute completely and kept the Dremel-style scan-based billing as the default, with **Editions** (Standard/Enterprise/Enterprise Plus, replacing the older flat-rate slot commitments retired July 5, 2023) as the opt-in capacity model for steady, predictable, high-volume workloads. [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing) — accessed 2026-08-08. The live disagreement in practice is exactly where the on-demand-vs-capacity break-even sits — industry estimates cluster around **400-500 TiB scanned per month** as the crossover point, but the real answer depends heavily on query concurrency and how well partitioning/clustering already control scan volume, which is why teams that migrate to Editions without first fixing bad partitioning routinely overpay for slots they didn't need to buy. [BigQuery Slots vs On-Demand — Codastra](https://medium.com/@2nick2patel2/bigquery-slots-vs-on-demand-choose-with-math-3dbe43048c00) — accessed 2026-08-08. Apache Beam (Dataflow's programming model, donated to Apache by Google in 2016, itself a generalization of the internal FlumeJava/MillWheel lineage) is now the industry-standard unified batch/streaming API, with Dataflow as the fully managed, most mature runner and Flink/Spark as portable alternatives for teams avoiding GCP lock-in — this multi-runner portability is genuinely delivered, not just a spec on paper. Pub/Sub's exactly-once delivery feature reached GA and is now the standard recommendation when idempotent-consumer design is impractical, while at-least-once plus idempotency remains the default, lower-latency recommendation for the common case. [Pub/Sub exactly-once delivery GA — Google Cloud Blog](https://cloud.google.com/blog/products/data-analytics/cloud-pub-sub-exactly-once-delivery-feature-is-now-ga) — accessed 2026-08-08.

**Where it's heading.** BigQuery's direction is deeper convergence with AI workloads — `ML.PREDICT` and `AI.GENERATE` inline SQL calls to Vertex AI/Gemini models, BigQuery ML expanding beyond classic regression/classification into LLM-backed row-level inference — moderate-to-high confidence given the pace of releases through 2025-2026, since this mirrors AlloyDB's and Spanner's parallel AI-integration bets. BI Engine and materialized views point toward BigQuery absorbing more of the "serving layer" role that used to require a separate OLAP cube or pre-aggregation pipeline — moderate confidence. On the streaming side, Dataflow's ML-focused runners (`RunInference` transform, GPU-backed workers) suggest streaming inference pipelines converging onto the same Beam programming model as ETL — moderate confidence, worth a fresh check near interview time since the agentic-AI pipeline space is moving fast. Pub/Sub's trajectory toward tighter Kafka-API compatibility (Managed Kafka launched as a separate GCP product rather than a Pub/Sub feature) suggests Google is choosing to let two products coexist — Pub/Sub for GCP-native pub/sub semantics, Managed Kafka for teams that want wire-compatible Kafka — rather than converging them, which is worth confirming close to interview time since product boundaries here have shifted before.

---

## Mental model

```
BIGQUERY COST MODEL — THE MENTAL FLIP FROM REDSHIFT

  REDSHIFT / cluster-based:
    Fixed-size cluster running 24/7 (or Serverless RPUs, still capacity-shaped)
    -> Cost = f(cluster size x uptime), roughly INDEPENDENT of query efficiency
    -> Optimization lever: right-size the cluster, use Concurrency Scaling for bursts

  BIGQUERY / scan-based (on-demand):
    No cluster. Every query bills for BYTES SCANNED, not time running.
    -> Cost = f(bytes scanned x $6.25/TiB), roughly INDEPENDENT of cluster size
    -> Optimization lever: partition + cluster + select fewer columns
       (columnar storage means SELECT col1 vs SELECT * changes bytes scanned
        directly -- there IS no "warm cache" fallback on cost the way a
        provisioned cluster's buffer cache changes nothing about your bill)

  CROSSOVER: ~400-500 TiB/month scanned is roughly where switching from
  on-demand to Editions capacity pricing starts winning -- below that,
  on-demand's "pay only for what you scan" beats paying for idle slots.

PARTITION + CLUSTER, STACKED:
  Table: 10 years of event data, 500 columns
  Query: WHERE event_date = '2026-08-01' AND user_id = 'x123'

  No partition/cluster  -> full table scan, ALL columns touched by query,
                            ALL 10 years -- most expensive possible query
  + partition on event_date -> scan shrinks to ONE DAY's data
  + cluster on user_id       -> within that day, BigQuery skips blocks that
                                 don't contain user_id 'x123'
  Order of magnitude or more reduction in bytes scanned, stacked.

PUB/SUB vs KINESIS ORDERING — THE OPPOSITE DEFAULT:
  Kinesis: ordering is FREE within a shard (partition key -> shard),
           but exactly-once is NEVER free -- consumer must dedupe.
  Pub/Sub: ordering is OPT-IN via ordering keys (adds a same-region
           publish constraint), exactly-once is a GA managed FEATURE
           you can turn on -- but both cost latency you don't pay by default.
```

---

## How it actually works

### BigQuery: scan-based billing, mechanically

On-demand pricing bills **$6.25 per TiB scanned** logically (uncompressed bytes of the columns actually read, not the compressed on-disk size), with the **first 1 TiB per project per month free**. [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing) — accessed 2026-08-08. Because storage is columnar, `SELECT specific_col FROM huge_table WHERE ...` scans only the bytes in `specific_col` (plus any columns referenced in the WHERE clause) — this is the mechanical reason `SELECT *` is expensive in a way it never was on a row-store system with a warm buffer cache: there is no cache to save you, every query pays for the columns it touches, every time. On-demand queries get access to up to roughly **2,000 concurrent slots** shared across all queries in a project — a real concurrency ceiling that shows up as queued queries under heavy simultaneous load, not a cost problem but a latency one.

**Editions** (Standard, Enterprise, Enterprise Plus) replaced the old flat-rate slot commitments on July 5, 2023. Pay-as-you-go slot-hour rates in the US region: **Standard $0.04**, **Enterprise $0.06**, **Enterprise Plus $0.10** per slot-hour, with 1-year and 3-year commitments available on Enterprise/Enterprise Plus at a discount. [BigQuery Editions — DoiT](https://www.doit.com/blog/bigquery-cost-optimization) — accessed 2026-08-08. **Autoscaling slots are the default capacity model**: you configure a baseline (the floor always held) and a maximum (the autoscaler's ceiling), billed per slot-hour only while slots are actually in use, scaling in increments of 100 slots — this is meaningfully different from the old flat-rate model where you paid for a fixed reservation whether it was busy or not. The commonly cited break-even point between on-demand and capacity pricing is **roughly 400-500 TiB scanned per month**; below that, on-demand's pay-only-for-what-you-scan model wins, above it a slot commitment amortizes cheaper. [BigQuery Slots vs On-Demand — Codastra](https://medium.com/@2nick2patel2/bigquery-slots-vs-on-demand-choose-with-math-3dbe43048c00) — accessed 2026-08-08.

### Partitioning and clustering, mechanically

**Partitioning** splits a table by a single **DATE, TIMESTAMP, DATETIME, or INTEGER-range** column (or ingestion time). Hard limit: **4,000 partitions per table** — daily partitioning gets roughly 11 years of runway before hitting that ceiling, hourly partitioning only about 5 months, which is the trap teams hit when they partition high-ingest-rate tables by hour without doing this arithmetic first. [Introduction to partitioned tables — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/partitioned-tables) — accessed 2026-08-08. **Clustering** sorts data within each partition (or across the whole table if unpartitioned) by up to **four columns**, in the order specified — order matters, BigQuery sorts by the first column, then the second within that, and so on, and re-ordering the same four columns produces different pruning effectiveness. Clustering has **no limit on cardinality or number of partitions** the way partitioning does, and works for a wider range of types, including STRING (where only the **first 1,024 characters** are used for clustering — a real gotcha for long free-text cluster keys). [Introduction to clustered tables — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/clustered-tables) — accessed 2026-08-08. Both only help when the query's WHERE clause actually filters on the partition/cluster columns — a query that filters on an unrelated column gets zero benefit from either, which is a common false assumption ("I partitioned the table, why is this query still expensive"). Over-partitioning is a real anti-pattern too: partitions with only a few MB of data each add per-partition metadata overhead and can make queries *slower*, not faster — the practical target is partitions in the multi-GB range.

```sql
-- untested sketch: partition + cluster stacked on an events table
CREATE TABLE analytics.events
PARTITION BY DATE(event_timestamp)
CLUSTER BY user_id, event_type
AS SELECT * FROM analytics.events_raw;

-- Query below only scans the Aug 1 partition, then within that partition
-- BigQuery skips storage blocks that don't contain user_id = 'x123'
-- (block-level pruning from clustering, not a full partition re-scan).
SELECT event_type, COUNT(*)
FROM analytics.events
WHERE DATE(event_timestamp) = '2026-08-01'
  AND user_id = 'x123'
GROUP BY event_type;
```

### Materialized views and BI Engine

**Materialized views** pre-compute and cache a query result (single-table aggregations, and a subset of JOIN patterns), with **automatic incremental refresh**: BigQuery reprocesses only the data that changed rather than recomputing the whole view. By default BigQuery tries to start a refresh within 5 minutes of the previous refresh being more than 30 minutes stale, and you can configure a refresh-frequency cap between **1 minute and 7 days**. [Use materialized views — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/materialized-views-use) — accessed 2026-08-08. For JOIN-based materialized views, only tables on the **left side** of the JOIN can have appended data and still refresh incrementally — a change to a right-side table forces a full non-incremental rebuild, which is the mechanical reason JOIN materialized views need careful table-ordering design, not just correct JOIN logic. Queries against the base table are **automatically rewritten** to hit the materialized view when BigQuery's optimizer determines it's valid and fresher-or-equal to what a direct query would return — this happens transparently, no query rewrite needed in application code.

**BI Engine** is an in-memory acceleration layer sitting in front of BigQuery, specifically aimed at dashboard tools (Looker, Looker Studio, Tableau, Power BI via the BigQuery connector) issuing the same handful of query shapes repeatedly — it caches hot data in memory and serves sub-second responses instead of re-scanning storage on every dashboard refresh. [BI Engine — 66degrees](https://www.66degrees.com/insights/bigquery-pricing-explained) — accessed 2026-08-08.

### Cost control: the layered defense

Three independent levers, stacked: **maximum bytes billed** at the individual-query level — BigQuery estimates bytes to be scanned before running the query and fails it with zero charge if the estimate exceeds your limit, a hard per-query safety net. **Custom quotas** at project or user level cap total daily bytes scanned — as of September 1, 2025, new projects default to a **200 TiB daily** on-demand query limit; quotas reset at midnight Pacific Time and are approximate safeguards, not a strict byte-by-byte billing cap. [Create custom query quotas — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/custom-quotas) — accessed 2026-08-08. **Partitioning/clustering** attacks the root cause (bytes scanned per query) rather than capping after the fact. None of these three alone is sufficient — maximum-bytes-billed protects against one runaway query, quotas protect against many small runaway queries adding up, and partitioning/clustering is what keeps normal queries cheap in the first place.

### Dataflow / Apache Beam

Beam's unified model: a **PCollection** (bounded or unbounded dataset) flows through **PTransforms** (ParDo, GroupByKey, Combine), with **windowing** (fixed, sliding, session, or global windows) partitioning an unbounded PCollection into finite chunks for aggregation, and **watermarks** tracking event-time progress to decide when a window is "done enough" to emit results despite late-arriving data. Dataflow is Google's fully managed runner for this model — it handles worker provisioning, autoscaling (from a handful up to 1,000+ workers based on backlog), and dynamic work rebalancing. **Streaming Engine** (the default execution mode for streaming jobs) offloads windowing and state/timer management from worker VMs to a separate managed backend service, which is what makes horizontal autoscaling fast and responsive — an **autoscaling hint** between 0.3 (favor minimal latency) and 0.7 (favor minimal cost) tunes how aggressively Dataflow scales workers in response to backlog. [Use Streaming Engine — Google Cloud Docs](https://docs.cloud.google.com/dataflow/docs/streaming-engine) — accessed 2026-08-08.

```python
# untested sketch -- Beam pipeline: windowed aggregation over a Pub/Sub stream
import apache_beam as beam
from apache_beam.transforms.window import FixedWindows

with beam.Pipeline() as p:
    (
        p
        | "Read" >> beam.io.ReadFromPubSub(subscription="projects/x/subscriptions/events")
        | "Window" >> beam.WindowInto(FixedWindows(60))  # 60s fixed windows
        | "ParseAndKey" >> beam.Map(lambda msg: (parse(msg).user_id, 1))
        | "CountPerUser" >> beam.CombinePerKey(sum)
        | "Write" >> beam.io.WriteToBigQuery(
            "project:dataset.user_event_counts",
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
        )
    )
```

### Pub/Sub: delivery semantics, mechanically

Default delivery is **at-least-once**: a message can be redelivered even after acknowledgment, under retry/failure conditions — application code must be idempotent by default. **Exactly-once delivery** (GA) guarantees no redelivery occurs once a message has been successfully acknowledged, tracked via a per-message-per-subscription delivery attempt token, at the cost of added acknowledgment latency — Google's own guidance is to reserve it for cases where building an idempotent consumer is genuinely impractical, not to reach for it by default. [Pub/Sub exactly-once GA — Google Cloud Blog](https://cloud.google.com/blog/products/data-analytics/cloud-pub-sub-exactly-once-delivery-feature-is-now-ga) — accessed 2026-08-08. **Ordering keys** are opt-in: messages published with the same key are delivered in publish order to a subscriber that has ordering enabled, but **all messages for one ordering key must publish to the same region** (subscribers can be anywhere), and because delivery is still at-least-once underneath, a single redelivered message forces redelivery of every subsequent message for that key — even already-acked ones — until the stuck message is acked. [Order messages — Google Cloud Docs](https://docs.cloud.google.com/pubsub/docs/ordering) — accessed 2026-08-08. This is the mechanical opposite of Kinesis: Kinesis gives per-shard ordering for free by construction (the shard *is* the ordering unit, no opt-in needed) but never offers a managed exactly-once mode — deduplication is entirely the consumer's job, typically via the Kinesis Client Library's checkpointing plus an application-level idempotency key.

### Looker vs. Looker Studio

**Looker** is the enterprise semantic-layer platform: **LookML** (a modeling language compiled to SQL) defines governed metrics and dimensions once, centrally, so every downstream dashboard/embed uses consistent definitions — sold on annual contracts with no public pricing, real-world figures land in the **$60K-$150K+/year** range depending on scale. [Looker Pricing 2026 — Shearwater Data](https://www.shearwaterdata.com/blog/looker-pricing-total-cost-breakdown-explained) — accessed 2026-08-08. It requires dedicated data-engineering investment to maintain the LookML layer — teams without at least 1-2 FTEs on it routinely see 2-4 week turnaround on new metric requests. **Looker Studio** (formerly Data Studio) is a free, lightweight, drag-and-drop dashboard tool with a **Pro tier at $9/user/month** for org-level sharing/administration features — it has no LookML semantic layer, no governed metric definitions, and is not the enterprise product despite the name overlap. Confusing the two in an interview — claiming Looker Studio has LookML, or that Looker is a free BI tool — is a quick tell.

---

## Build it from scratch

Minimal illustration of the partition-pruning and Pub/Sub-ordering-key concepts (matching `labs/python/06-data/` conceptually — no lab folder ships with this module):

```python
# untested sketch -- estimate bytes scanned before running, mirroring
# what "maximum bytes billed" checks internally
from google.cloud import bigquery

client = bigquery.Client()
query = """
    SELECT event_type, COUNT(*) AS n
    FROM `proj.analytics.events`
    WHERE DATE(event_timestamp) = '2026-08-01'
    GROUP BY event_type
"""
job_config = bigquery.QueryJobConfig(
    dry_run=True, use_query_cache=False,  # dry_run: estimate only, no charge
)
job = client.query(query, job_config=job_config)
print(f"This query will process {job.total_bytes_processed / 1e9:.2f} GB")
# In production: set maximum_bytes_billed on the real QueryJobConfig as a
# hard safety net so an accidental full-table scan fails for $0 instead
# of billing for terabytes.
```

```python
# untested sketch -- publishing with an ordering key, and why redelivery
# of one message blocks all subsequent messages for that key
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient(
    publisher_options=pubsub_v1.types.PublisherOptions(enable_message_ordering=True)
)
topic_path = publisher.topic_path("my-project", "orders")

# All three publish to the SAME region because they share ordering_key.
# If message 2 fails to ack, message 3 will NOT be delivered until
# message 2 is redelivered and acked -- this is the ordering guarantee's
# cost: head-of-line blocking per key, not just "messages arrive in order."
for order_event in ["created", "paid", "shipped"]:
    publisher.publish(topic_path, data=order_event.encode(), ordering_key="order-42")
```

---

## How it's done in production

A typical GCP data platform: **BigQuery on-demand** for exploratory/ad-hoc analyst workloads and spiky reporting, **Editions capacity pricing** (usually Enterprise, autoscaling slots with a modest baseline) once steady scan volume crosses the few-hundred-TiB/month range or query concurrency SLAs matter more than raw cost. **Partitioning by ingestion/event date is close to a default** on any table over a few GB; clustering is added once query patterns stabilize enough to know which columns are actually filtered on. **Materialized views** sit in front of dashboard-facing aggregate tables that would otherwise be recomputed by a scheduled query every few minutes; **BI Engine** sits in front of the whole dashboard layer once query latency, not just cost, becomes the complaint. **Dataflow** handles the streaming ETL path — Pub/Sub topic to windowed aggregation to BigQuery — with Streaming Engine on by default for anything beyond a toy pipeline. **Pub/Sub at-least-once plus idempotent consumers** is the default messaging pattern; ordering keys and exactly-once delivery are reserved for the specific subset of flows (financial transaction sequences, inventory decrements) where correctness genuinely requires it, because both add latency. **Looker** is reserved for organizations that need a governed semantic layer across many consumers and dashboards; **Looker Studio** covers the long tail of one-off or team-level dashboards that don't justify LookML's engineering investment.

| Symptom | Cause | Fix |
|---|---|---|
| BigQuery bill spikes after a dashboard tool starts polling every few minutes | Dashboard re-runs the same expensive unpartitioned scan on every refresh, no caching layer | Add a materialized view or BI Engine in front of the dashboard's query pattern; partition/cluster the base table |
| Query that "should be cheap" still scans the whole table | WHERE clause filters on a column that isn't the partition or cluster key | Re-check which columns the query actually filters on; repartition/recluster to match real query patterns, not assumed ones |
| BigQuery Editions slot commitment costs more than on-demand did | Slots purchased for peak load but workload is actually spiky/bursty, not steady | Recalculate against actual monthly TiB scanned; autoscaling slots with a low baseline, or reverting to on-demand, usually wins below ~400-500 TiB/month |
| Dataflow streaming job falls behind and backlog grows during a traffic spike | Streaming Engine autoscaling hint tuned toward cost (0.7) instead of latency (0.3), or worker max ceiling too low | Lower the autoscaling hint toward 0.3 for latency-sensitive pipelines; raise the max worker count |
| Pub/Sub subscriber stops receiving new messages for one entity, others fine | An unacked/failed message on that entity's ordering key is blocking all subsequent messages for that same key (head-of-line blocking) | Investigate and resolve the stuck message (dead-letter topic, manual nack/redrive); don't assume ordering keys are "free" ordering with no failure mode |
| Two teams' dashboards show different numbers for "revenue" | No governed semantic layer — each team wrote its own ad-hoc SQL/Looker Studio query with slightly different filters | Move the shared metric definition into LookML (Looker) or a shared BigQuery view, single source of truth |

---

## Tradeoffs & when NOT to use it

- **Don't default to BigQuery Editions capacity pricing "because it sounds more enterprise."** Below roughly 400-500 TiB scanned/month, on-demand is cheaper and requires zero capacity planning. Buying slots for a spiky or low-volume workload is paying for idle capacity, the exact anti-pattern BigQuery's scan-based model exists to avoid.
- **Don't partition by hour on a high-cardinality or long-lived table without doing the 4,000-partition arithmetic first.** Hourly partitioning burns through the limit in about 5 months; daily buys roughly 11 years. Getting this wrong means an expensive schema migration later.
- **Don't reach for Pub/Sub exactly-once delivery or ordering keys as a default.** Both add latency (exactly-once via acknowledgment overhead, ordering keys via head-of-line blocking on redelivery). The default should be at-least-once plus an idempotent consumer; reserve the stronger guarantees for the specific flows where idempotency is genuinely impractical to build.
- **Don't use Dataflow for a workload with no real streaming or complex-batch-transform need.** A simple scheduled BigQuery query or a Cloud Function is cheaper and simpler than standing up a Beam pipeline and its worker fleet for a job that's fundamentally "copy this table daily."
- **Don't buy Looker for a single team's dashboards.** The LookML investment and six-figure contract only pay off when multiple teams need a governed, consistent semantic layer across many consumers; Looker Studio (free-to-$9/user) covers the common case.
- **Don't assume materialized views are a free win on every aggregate query.** JOIN-based materialized views lose incremental refresh the moment a right-side table changes, silently falling back to full rebuilds — validate the JOIN shape against BigQuery's incremental-refresh rules before relying on it for cost control.

---

## Interview questions

### Q1 — Why does BigQuery's cost model fundamentally change how you think about query optimization compared to Redshift?
**Testing:** whether the candidate understands the mechanism, not just that the price-per-unit differs.
**Answer:** Redshift bills for cluster size x uptime, roughly independent of how efficient any individual query is — optimization means right-sizing the cluster and managing concurrency. BigQuery on-demand bills per query for bytes scanned ($6.25/TiB), independent of cluster size because there is no cluster — optimization means shrinking bytes scanned per query via partitioning, clustering, and column selection. A `SELECT *` that would cost nothing extra on an idle, already-provisioned Redshift cluster directly costs money on BigQuery every single time it runs, because columnar storage means every column read is billed bytes, with no buffer-cache fallback that makes repeated queries free.
**Follow-up trap:** *"So is BigQuery always cheaper for ad-hoc analytics?"* — not necessarily; a workload with sustained, predictable, high-volume querying (many TiB scanned daily, every day) can end up cheaper on a well-utilized Redshift cluster or BigQuery Editions capacity commitment than paying on-demand per-scan rates repeatedly — the crossover is empirical (~400-500 TiB/month), not a blanket rule.

### Q2 — Design the partitioning and clustering strategy for a 50-column, 5-year event table queried mostly by date range and user_id.
**Testing:** applying the mechanical rules, not reciting them.
**Answer:** Partition by `DATE(event_timestamp)` — daily partitioning covers the 5-year range comfortably within the 4,000-partition limit (11-year runway) and matches the dominant date-range query pattern. Cluster by `user_id` (and optionally a second frequently-filtered column like `event_type`) so that within any given day's partition, BigQuery can block-prune to just the rows for that user instead of scanning the full day. Order clustering columns by selectivity/filter frequency — the column filtered most often and with highest cardinality goes first.
**Follow-up trap:** *"What if queries sometimes filter by month instead of a specific day?"* — daily partitions still work fine for month-range queries (BigQuery scans all partitions in the range, no penalty for querying across multiple partitions beyond the sum of their sizes) — the trap is assuming partition granularity must match every query's exact filter granularity; it doesn't, partitioning just needs to be *finer than or equal to* the coarsest common filter pattern.

### Q3 — A team hits a "query exceeded resource limits" concurrency slowdown during a product launch, all queries under the free on-demand slot pool. What's happening and what are the options?
**Testing:** understanding the ~2,000 concurrent slot ceiling on-demand queries share per project.
**Answer:** On-demand queries share a pool of roughly 2,000 concurrent slots per project — during a traffic spike with many simultaneous dashboard/API-triggered queries, individual queries queue or slow down because they're competing for that shared pool, not because any single query got more expensive. Options: purchase Editions capacity (a reservation gives dedicated, non-shared slots), spread heavy query load across multiple projects, or reduce per-query cost (partitioning/clustering/materialized views) so more queries fit in the same slot-time.
**Follow-up trap:** *"Wouldn't buying more slots just be paying to fix a self-inflicted inefficiency problem?"* — sometimes yes; the correct diagnostic order is to first check whether individual queries are unnecessarily expensive (unpruned scans) before concluding the fix is more capacity — buying slots to paper over an unpartitioned table's inefficiency is a real anti-pattern interviewers watch for.

### Q4 — Explain why a materialized view built on a two-table JOIN might silently stop refreshing incrementally.
**Testing:** the specific JOIN-side asymmetry in materialized view incremental refresh.
**Answer:** BigQuery's incremental refresh for JOIN-based materialized views only supports appended data on the **left-side** table of the JOIN. If the right-side table receives any change (append, update, delete), the materialized view can no longer be incrementally maintained for that refresh cycle and falls back to a full rebuild — which is slower and, if the base tables are large, potentially expensive, defeating part of the original cost-saving intent.
**Follow-up trap:** *"How would you even notice this happening in production?"* — refresh latency and cost creep up gradually as the right-side table churns more, without any explicit error — the fix is monitoring materialized view refresh job cost/duration over time and structuring JOINs so the more frequently-changing table is on the left, or splitting into separate materialized views if that's not achievable.

### Q5 — Walk through the mechanical difference between Pub/Sub's default delivery guarantee and Kinesis's, and why that matters for a payment-processing pipeline.
**Testing:** cross-cloud precision on delivery semantics, a common trap for AWS-background candidates.
**Answer:** Pub/Sub defaults to at-least-once delivery with no ordering guarantee unless ordering keys are explicitly enabled (opt-in, same-region-per-key constraint); a GA exactly-once mode exists as an opt-in feature trading latency for a formal no-redelivery-after-ack guarantee. Kinesis gives per-shard ordering for free by construction (the shard is the ordering unit) but has no managed exactly-once mode at all — deduplication is entirely the consumer's responsibility via idempotency keys and KCL checkpointing. For a payment pipeline needing strict per-account event ordering: on Pub/Sub you'd explicitly enable ordering keys keyed by account ID; on Kinesis you'd choose the partition key to be account ID so ordering falls out naturally, then build idempotent processing regardless, since neither guarantees exactly-once end-to-end for free.
**Follow-up trap:** *"If Pub/Sub has a GA exactly-once feature, why not just turn it on for the payment pipeline and skip idempotent consumer design?"* — exactly-once delivery guarantees no redelivery after ack, but it doesn't protect against every failure mode (a consumer crash between processing and acking still needs correct retry behavior, and cross-system side effects like a downstream payment API call aren't covered by Pub/Sub's guarantee at all) — idempotent consumer design is still the safer default even with exactly-once enabled, not a replacement for it.

### Q6 — A candidate says "BigQuery has no indexes so it must be slow for point lookups." Evaluate that claim.
**Testing:** understanding that partitioning/clustering are BigQuery's substitute for indexes, with different mechanics.
**Answer:** BigQuery genuinely has no traditional B-tree indexes — it's a columnar, scan-oriented engine, not built for single-row point lookups the way an OLTP database with a primary-key index is. That's a legitimate limitation: a workload needing "fetch this one row by ID in single-digit milliseconds" is the wrong fit for BigQuery regardless of partitioning/clustering (Bigtable, Cloud SQL, or Firestore are the right tools). But for analytical range/filter queries, partitioning (coarse pruning by date/int range) and clustering (fine-grained block pruning within a partition) serve the same *cost and scan-reduction* purpose an index would, just via a different mechanism (block-level metadata pruning, not row-level index lookup) suited to bulk analytical scans rather than single-row fetches.
**Follow-up trap:** *"So could you just cluster on a unique ID and get index-like point lookup performance?"* — clustering helps prune which storage blocks get scanned, but BigQuery still executes a query as a scan over the relevant blocks, not a true index seek — for genuinely latency-sensitive single-row lookups at scale, this is still meaningfully slower than an indexed OLTP system, and the correct answer is to route that access pattern to a different service entirely, not to over-tune BigQuery clustering to compensate.

### Q7 — Explain Dataflow's Streaming Engine and why it matters for autoscaling responsiveness.
**Testing:** understanding what Streaming Engine actually offloads, not just that it "makes things faster."
**Answer:** Without Streaming Engine, each Dataflow worker VM holds its own windowing state, timers, and persistent state locally — scaling the worker fleet up or down means moving or rebalancing that state, which is slow and limits how aggressively Dataflow can autoscale. Streaming Engine moves windowing/state/timer management out of worker VMs into a separate managed backend service, so workers become comparatively stateless compute units that can be added or removed quickly without state-migration overhead — this is what enables fast, responsive horizontal autoscaling (from a handful to 1,000+ workers) in response to backlog changes.
**Follow-up trap:** *"Does Streaming Engine change the pipeline's correctness guarantees (windowing, watermarks, exactly-once processing within Beam)?"* — no; Streaming Engine is an execution/infrastructure optimization, not a semantic change — the same Beam windowing and watermark model applies whether or not Streaming Engine is enabled. Conflating an infrastructure optimization with a correctness guarantee is exactly the kind of imprecision that fails a staff-level round.

### Q8 — When would you choose Redshift Serverless over BigQuery, given both are now "consumption-priced" in some sense?
**Testing:** precision about what "serverless" actually means in each product, since the terms sound convergent but aren't.
**Answer:** Redshift Serverless still bills RPU-hours consumed while the workload is active (a capacity-shaped unit, $0.375/RPU-hour, 60-second minimum, each RPU = 16GB memory) — it's compute-consumption pricing, but the unit is still "capacity x time," conceptually closer to BigQuery's Editions model than to BigQuery on-demand's bytes-scanned model. BigQuery on-demand bills purely on bytes scanned with zero idle charge and no capacity unit to reason about at all. Redshift Serverless is the right choice when a team is already AWS-native (IAM, VPC, existing Redshift schema/tooling) and wants the "no cluster to size" experience within that ecosystem; BigQuery on-demand specifically wins for genuinely ad-hoc, low-and-spiky query volume where even RPU-hour billing would carry a floor cost that scan-based billing avoids entirely.
**Follow-up trap:** *"Isn't 'per-second billing with no idle charge' basically the same value proposition as BigQuery on-demand?"* — the value proposition is similar (both avoid the old fixed-cluster problem) but the unit of billing differs in a way that matters at low volume: Redshift Serverless still has a 60-second minimum per active period and RPU capacity granularity, while BigQuery on-demand's true zero-idle-cost, pay-per-byte model has no comparable floor — for extremely spiky, low-volume workloads BigQuery on-demand's cost curve is flatter and lower than Redshift Serverless's.

### Q9 — A finance team wants strict LookML-governed metric definitions across 40 dashboards built by different teams. Justify Looker over Looker Studio given the cost difference.
**Testing:** whether the candidate can make (and defend) a real build-vs-buy tradeoff, not just recite feature lists.
**Answer:** The core problem — 40 dashboards built independently risk diverging metric definitions (two teams' "revenue" numbers disagreeing) — is exactly what LookML's centralized semantic layer solves: define the metric once, compile to governed SQL, every dashboard/embed inherits the same definition. Looker Studio has no equivalent modeling layer; each dashboard's query logic is independent, so consistency depends entirely on manual discipline across 40 separate teams, which doesn't scale. The six-figure annual cost is justified specifically by the governance requirement and consumer count — for a single team's dashboards, that same cost would be unjustifiable and Looker Studio (free-to-$9/user) would be the correct call instead.
**Follow-up trap:** *"Couldn't you get the same governance by just centralizing the queries into shared BigQuery views instead of paying for Looker?"* — partially; shared views do enforce a single source of truth for the underlying SQL, but they don't give LookML's higher-level modeling features (derived metrics, access-controlled exploration, embedded analytics, a business-user-facing modeling layer non-engineers can extend within guardrails) — for a pure "one consistent number" requirement, shared views can be enough and are much cheaper; Looker's premium is for the broader self-service/governance platform, not just consistent SQL.

### Q10 — Diagnose: a Pub/Sub subscriber with ordering enabled stops processing new messages for one specific customer, while all other customers' messages flow normally.
**Testing:** the head-of-line blocking failure mode specific to ordering keys, a real production incident pattern.
**Answer:** Because Pub/Sub delivery is still at-least-once underneath ordering keys, one message for that customer's ordering key likely failed to ack (a transient error, a bug on a specific payload shape, a poison message) and is stuck in redelivery. Since ordering keys guarantee in-order delivery, every subsequent message for that same key is held back until the stuck message is successfully acked — this is a designed behavior, not a bug in Pub/Sub, but it means one bad message blocks an entire entity's message stream indefinitely if not handled.
**Follow-up trap:** *"How do you prevent one customer's stream from blocking indefinitely without breaking the ordering guarantee for everyone?"* — configure a dead-letter topic with a max-delivery-attempts threshold, so a message that repeatedly fails to ack gets moved out of the ordered stream after N attempts, unblocking subsequent messages for that key — this necessarily breaks strict ordering for that one problematic message (it's diverted, not delivered in sequence) but is the standard mitigation, since the alternative (no dead-letter policy) risks indefinite stalls on any poison message.

### Q11 — Why might a team see BigQuery's `maximum bytes billed` safeguard fail to catch a runaway query that ends up costing real money?
**Testing:** the estimate-vs-actual distinction in BigQuery's cost-control mechanics.
**Answer:** `maximum bytes billed` fails the query *before execution* based on BigQuery's pre-execution byte estimate — if that estimate comes in under the limit but the query's actual execution touches more data than estimated (rare, but possible with certain dynamic/wildcard table patterns or federated queries where BigQuery's estimator has less visibility), the safeguard doesn't trigger. It's also strictly a per-query control — it does nothing against a large number of individually-small, individually-under-the-limit queries adding up to a large daily bill, which is what custom quotas exist to catch instead.
**Follow-up trap:** *"So is maximum bytes billed unreliable and not worth using?"* — no, it's reliable for its actual scope (catching an individual query's byte estimate exceeding a threshold before it runs) — the trap is treating it as a complete cost-control solution on its own rather than one layer of a stack that needs quotas and good partitioning/clustering alongside it.

### Q12 — Explain why partitioning by hour instead of by day is often the wrong default, even for a high-ingest-volume table.
**Testing:** the 4,000-partition hard limit and its practical runway math.
**Answer:** BigQuery caps a table at 4,000 partitions total. Daily partitioning gives roughly 11 years of runway before hitting that cap; hourly partitioning burns through it in about 5 months. A team defaulting to hourly "because ingest volume is high" without checking this runs into a hard partition-limit error well before the table's natural retention period ends, forcing an emergency re-partitioning migration. High ingest volume within a day is what clustering (not finer-grained partitioning) is meant to handle — clustering has no partition-count ceiling and can subdivide within a daily partition far more granularly than hourly partitioning would.
**Follow-up trap:** *"What if a query genuinely only ever needs one specific hour of data at a time — wouldn't hourly partitioning be strictly better for that query?"* — for that single query shape, yes, hourly partitioning prunes more precisely — but the 4,000-partition ceiling is a hard constraint on the whole table regardless of any one query's needs, so the right fix for an hour-precision access pattern is daily partitioning plus clustering on an hour-derived column (or a separate integer partition on hour-of-day combined with date), not abandoning the partition-count budget entirely for one query pattern.

---

## Red flags that fail you

- Describing BigQuery cost optimization purely in terms of "buy more slots" without mentioning partitioning/clustering.
- Not knowing partitioning caps at 4,000 partitions, or recommending hourly partitioning without checking the runway math.
- Claiming Pub/Sub guarantees ordering by default the way Kinesis does per-shard.
- Recommending Pub/Sub exactly-once delivery as the default rather than idempotent consumers plus at-least-once.
- Conflating Looker and Looker Studio, or claiming either has features that belong to the other.
- Assuming a materialized view always refreshes incrementally regardless of JOIN shape.
- Treating "serverless" as synonymous across Redshift Serverless, BigQuery on-demand, and Aurora Serverless without naming the billing-unit differences.

---

## Cheat card

```
BIGQUERY: scan-billed, $6.25/TiB on-demand (1 TiB/mo free), ~2000 shared
  slots per project on-demand. Editions (replaced flat-rate 2023-07-05):
  Standard $0.04, Enterprise $0.06, Enterprise Plus $0.10 /slot-hr,
  autoscaling default, 100-slot increments. Break-even vs on-demand
  ~400-500 TiB/month scanned.

PARTITION: 1 col (DATE/TIMESTAMP/DATETIME/INT), 4000-partition hard cap.
  Daily = ~11yr runway, hourly = ~5mo. CLUSTER: up to 4 cols, no cap,
  order matters (sort by col1 then col2...), STRING uses first 1024 chars.
  Stack both for order-of-magnitude scan reduction.

MATERIALIZED VIEWS: auto incremental refresh (single-table + some JOINs).
  JOIN views: only LEFT-side table can append and stay incremental; any
  right-side change = full rebuild. Refresh cap: 1min-7day, default
  tries <5min after 30min staleness.

COST CONTROL layers: maximum_bytes_billed (per-query, pre-execution
  estimate, fails free if over) + custom quotas (project/user daily cap,
  200 TiB default since 2025-09-01, resets midnight PT) + partition/cluster
  (fixes root cause). BI Engine = in-memory dashboard accelerator.

DATAFLOW/BEAM: unified batch+streaming, PCollection/PTransform, windowing
  (fixed/sliding/session/global) + watermarks for late data. Streaming
  Engine offloads state/windowing off workers -> fast autoscale (1 to
  1000+ workers). Autoscaling hint 0.3=latency, 0.7=cost.

PUB/SUB: at-least-once DEFAULT (redelivery possible post-ack) -- opposite
  of Kinesis (ordered-per-shard default, dedupe always manual). Exactly-
  once = GA opt-in, adds ack latency. Ordering keys = opt-in, same-region
  publish per key, ONE stuck message blocks all later messages for that
  key (head-of-line block) -- use dead-letter topic to unstick.

LOOKER: LookML semantic layer, $60K-150K+/yr, needs 1-2+ FTE. LOOKER
  STUDIO: free, Pro $9/user/mo, no LookML, dashboard tool only. Don't
  conflate them.

CROSS-CLOUD: BigQuery~Redshift (scan- vs cluster/RPU-billed -- THE
  interview flip). Dataflow~Kinesis Data Analytics/Glue (Beam = portable
  across Flink/Spark too). Pub/Sub~Kinesis/Event Hubs (ordering/exactly-
  once defaults are OPPOSITE of Kinesis). Looker~QuickSight/Power BI
  (Looker Studio is the closer free-tier analog).
```

## Sources

- [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing) — accessed 2026-08-08
- [BigQuery Slots vs On-Demand: Choose with Math — Codastra/Medium](https://medium.com/@2nick2patel2/bigquery-slots-vs-on-demand-choose-with-math-3dbe43048c00) — accessed 2026-08-08
- [BigQuery Cost Optimization — DoiT](https://www.doit.com/blog/bigquery-cost-optimization) — accessed 2026-08-08
- [Introduction to partitioned tables — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/partitioned-tables) — accessed 2026-08-08
- [Introduction to clustered tables — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/clustered-tables) — accessed 2026-08-08
- [Use materialized views — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/materialized-views-use) — accessed 2026-08-08
- [Create custom query quotas — Google Cloud Docs](https://docs.cloud.google.com/bigquery/docs/custom-quotas) — accessed 2026-08-08
- [BigQuery Pricing Explained (BI Engine) — 66degrees](https://www.66degrees.com/insights/bigquery-pricing-explained) — accessed 2026-08-08
- [Use Streaming Engine — Google Cloud Docs](https://docs.cloud.google.com/dataflow/docs/streaming-engine) — accessed 2026-08-08
- [Order messages — Google Cloud Docs](https://docs.cloud.google.com/pubsub/docs/ordering) — accessed 2026-08-08
- [Cloud Pub/Sub exactly-once delivery is now GA — Google Cloud Blog](https://cloud.google.com/blog/products/data-analytics/cloud-pub-sub-exactly-once-delivery-feature-is-now-ga) — accessed 2026-08-08
- [Looker Pricing: Complete Cost Breakdown for 2026 — Shearwater Data](https://www.shearwaterdata.com/blog/looker-pricing-total-cost-breakdown-explained) — accessed 2026-08-08
- [Amazon Redshift Pricing Guide 2026 — CloudZero](https://www.cloudzero.com/blog/redshift-pricing/) — accessed 2026-08-08
- [Apache Kafka vs Amazon Kinesis vs Google Pub/Sub — Index.dev](https://www.index.dev/skill-vs-skill/apache-kafka-vs-amazon-kinesis-vs-google-pubsub) — accessed 2026-08-08
- `clouds/CROSS-CLOUD-MAP.md` — internal cross-cloud equivalence reference

## Changelog
- 2026-08-08 — created
