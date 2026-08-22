# Data: Glue, EMR, Athena, Redshift, Kinesis, MSK, OpenSearch

> **Track:** C-AWS AWS Atlas · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-data-analytics` · **Tags:** data

## The 30-second version

Glue is serverless Spark billed per DPU-hour ($0.44/DPU-hour on-demand, $0.29 with Flex for tolerant batch jobs) plus a catalog and crawler layer on top — it wins on zero-ops for straightforward ETL and loses hard once jobs are long-running, tuning-sensitive, or need library/version control that EMR's raw cluster access gives you. Athena is Presto/Trino under the hood, billed at $5/TB scanned with a 10MB-per-query minimum, and the entire cost optimization story is "scan less data" — Parquet/columnar format, compression, and partitioning (or partition projection for time-series data) routinely cut scans by 90%+. Redshift's RA3 nodes decouple compute from managed storage and Spectrum lets you query S3 directly, but it's cluster-billed against BigQuery's/Athena's pure query-billing, which flips the cost conversation from "control the scan" to "size the cluster right." Kinesis Data Streams, Firehose, and MSK solve three different problems — a low-ops replayable stream with per-shard limits, a zero-code delivery pipe into S3/Parquet, and a fully Kafka-compatible cluster for anyone with existing Kafka tooling — and the deciding question is almost always "do you have existing Kafka clients" before anything about throughput. OpenSearch does hybrid lexical-plus-vector search well at scale but a dedicated vector DB or Bedrock Knowledge Bases beats it when the team wants zero index-tuning ops rather than horizontal-scale control.

## Why this gets asked

Because the interviewer has watched a team pick the wrong tool for the wrong reason at least once: Glue chosen because it's "serverless" for a job that needed six hours of tuned Spark on EMR instead, an unpartitioned Athena table that turned a $50 query into a $4,500 one, or a Kinesis Data Streams deployment reimplementing Kafka semantics badly because nobody checked whether MSK was the better fit from day one. They want evidence you've actually paid an AWS data bill and had to explain a spike, not that you can name six services.

---

## Lineage: past → present → future

**What came before.** Before managed big-data services, "data engineering on AWS" meant self-managed Hadoop/Spark clusters on raw EC2 — provisioning, patching, and tuning a cluster by hand, with no elastic scaling and no separation between compute and storage. EMR (2009) was AWS's first answer: managed Hadoop/Spark clusters that could scale and terminate on demand, still requiring cluster sizing and tuning knowledge. Redshift (2012) brought the first managed MPP columnar warehouse to AWS, originally coupling compute and storage tightly on DC-family nodes, which meant scaling storage meant scaling (and paying for) compute you didn't need. Streaming ingestion before Kinesis (2013) meant hand-rolled polling loops or self-managed Kafka clusters with no managed alternative at all.

**Where it stands now.** The current AWS data stack has genuinely separated concerns: EMR/Glue for transformation, Athena/Redshift for query, Kinesis/Firehose/MSK for ingestion, OpenSearch for search-and-vector. Redshift's RA3 generation (2019 onward) decoupled storage from compute the way Snowflake and BigQuery always did, and Redshift Serverless removed cluster sizing entirely for variable workloads — closing much of the operational gap with BigQuery, though BigQuery/Athena's pure per-query billing model versus Redshift's cluster-time billing remains a live and genuine architectural difference, not a solved one. Glue vs EMR is the most persistent live disagreement in this list: Glue's serverless DPU model is unambiguously less operational overhead, but poorly-tuned Spark jobs can burn 10x the DPU-hours of an equivalent hand-tuned EMR cluster, and EMR gives raw access to Spark configuration, custom libraries, and long-running/streaming jobs that Glue's job model constrains. For streaming, the field has consolidated: Kinesis Data Streams for AWS-native low-ops streaming, MSK for anyone with existing Kafka investment (the migration cost of rewriting Kafka clients is consistently cited as exceeding any benefit of switching), Firehose as the default lowest-effort path from any stream into a queryable S3/Parquet lake.

**Where it's heading.** Lakehouse table formats — Iceberg specifically, with growing Delta Lake and Hudi support — are becoming the default over raw partitioned Parquet for anything requiring schema evolution, time travel, or ACID semantics on S3; Athena, Glue, EMR, and Redshift Spectrum all have native Iceberg support now, and this is a real, accelerating shift rather than a speculative one. Vector-native retrieval inside OpenSearch (GPU-accelerated indexing, disk-optimized vector engines cutting cost roughly 3x per recent AWS announcements) is maturing fast because RAG workloads are now a first-class OpenSearch use case, not an afterthought bolted onto a search engine. More speculatively: expect continued blurring between "warehouse" and "lake" as Redshift, Athena, and EMR converge on querying the same Iceberg tables in S3 rather than requiring data movement between systems — treat full convergence as a direction of travel, several years out, not the current default architecture.

---

## Mental model

```
                     INGEST                    TRANSFORM              QUERY / SERVE
  ┌───────────┐   ┌───────────────┐        ┌───────────────┐      ┌─────────────────┐
  │  App/IoT  │──▶│ Kinesis Data   │──┐     │                │      │  Athena          │
  │  events   │   │ Streams (shard)│  │     │  Glue (DPU-hr, │      │  ($/TB scanned) │
  └───────────┘   └───────────────┘  │     │  serverless    │─────▶│                 │
                                      ├────▶│  Spark + Data  │      ├─────────────────┤
  ┌───────────┐   ┌───────────────┐  │     │  Catalog)      │      │  Redshift        │
  │  Existing │──▶│  MSK (Kafka)  │──┤     │      OR        │─────▶│  (cluster-billed│
  │  Kafka    │   └───────────────┘  │     │  EMR (raw      │      │  RA3 + Spectrum)│
  └───────────┘                      │     │  Spark cluster,│      ├─────────────────┤
  ┌───────────┐   ┌───────────────┐  │     │  full tuning   │      │  OpenSearch      │
  │  Any      │──▶│  Firehose     │──┘     │  control)      │─────▶│  (lexical+vector│
  │  stream   │   │  (managed     │              │                │  hybrid search) │
  └───────────┘   │  delivery,    │              ▼                └─────────────────┘
                  │  auto Parquet)│         S3 (Parquet/Iceberg)
                  └───────────────┘         + Glue Data Catalog
```

The recurring question across every box: **who pays for idle, and who pays for scan.** Kinesis/MSK/EMR bill for provisioned capacity whether or not you use it (shards, brokers, cluster nodes); Athena/Firehose/Glue-serverless bill for actual work done. Redshift historically leaned toward the first model (provisioned clusters) and has been moving toward the second (Serverless, RA3 storage decoupling).

---

## How it actually works

### Glue: catalog, crawlers, ETL jobs — and when it loses to EMR

Glue Data Catalog is a managed Hive-metastore-compatible metadata store, shared automatically with Athena, Redshift Spectrum, and EMR — this is the actual reason to use Glue even if you never run a Glue ETL job: one catalog, many query engines. **Crawlers** scan S3/JDBC sources and infer schema/partitions into the catalog; they're billed the same $0.44/DPU-hour as ETL jobs but with a 10-minute minimum per run [AWS Glue Pricing 2026 — Integrate.io](https://www.integrate.io/blog/aws-glue-pricing/) — accessed 2026-08-01. **ETL jobs** run Spark (or Python shell, or Ray) on a serverless pool of DPUs (a DPU is roughly 4 vCPU / 16GB), billed per-second with a 1-minute minimum at $0.44/DPU-hour on-demand, or $0.29/DPU-hour under **Flex** execution for jobs that can tolerate a delayed, opportunistic start (batch jobs with no tight SLA) [AWS Glue Pricing — Integrate.io](https://www.integrate.io/blog/aws-glue-pricing/) — accessed 2026-08-01.

**The honest "Glue is worse than EMR" list:** (1) long-running or continuous/streaming jobs, where EMR's persistent cluster amortizes better than Glue's job-startup overhead repeated on every run; (2) jobs needing fine-grained Spark configuration, custom JARs/libraries, or a specific Spark/Hadoop ecosystem version Glue doesn't expose; (3) poorly-optimized Spark code — a badly-partitioned job can burn 10x the DPU-hours of a tuned equivalent, and Glue gives you fewer knobs to fix that than raw EMR does; (4) very high-frequency short jobs, where per-job Glue startup latency (cold start commonly cited in the tens-of-seconds to low-minutes range) adds up against a warm, already-running EMR cluster picking up the next job instantly [AWS Glue vs EMR — XTIVIA](https://www.xtivia.com/blog/amazon-emr-versus-aws-glue/) — accessed 2026-08-01. The honest "Glue wins" case is exactly the inverse: intermittent, well-defined batch ETL where zero cluster management is worth more than raw tuning control. Deep EMR mechanics (cluster sizing, EMRFS, spot fleet strategy) are in `T18-emr`; this module treats EMR as the "when Glue isn't enough" answer, not a first-class deep dive.

### Athena: Presto/Trino lineage and the cost-per-TB lever

Athena is AWS's managed, serverless Presto/Trino, querying data in place in S3 via the Glue Data Catalog, billed at **$5 per TB of data scanned**, with a 10MB minimum charge per query [Amazon Athena Pricing — CloudBurn](https://cloudburn.io/blog/amazon-athena-pricing) — accessed 2026-08-01. Because the entire bill is a function of bytes scanned, not query complexity or runtime, the optimization levers are all about *scanning less*:

- **Columnar format (Parquet/ORC).** Athena reads only the columns referenced in the query — a query touching 1 of 4 columns in a Parquet table reads roughly a quarter of the data before compression even applies, versus a full-row-scan in CSV/JSON.
- **Compression.** Snappy gives roughly 3-5x compression, gzip roughly 5-10x — directly proportional to the bytes actually scanned and billed.
- **Partitioning.** Filtering on a partition key (commonly date) means Athena skips entire S3 prefixes rather than scanning them; daily partitioning over a year of data means a single-day query reads roughly 1/365th of the table.
- **Partition projection.** Instead of registering every partition in the Glue Catalog (which gets slow and expensive to maintain at high partition counts), partition projection computes partition locations algorithmically from a configured pattern (date ranges, enum lists), eliminating both the `MSCK REPAIR TABLE`/crawler maintenance step and the metadata-lookup overhead for high-cardinality time-series tables.

A documented real-world result: converting a 15TB-scan-per-query table to Snappy-compressed Parquet with daily partitioning dropped the average scan to roughly 50GB per query, cutting a ~$45,000/month bill to roughly $150/month [Athena Cost Optimization — FactualMinds](https://www.factualminds.com/blog/athena-query-cost-optimization-partition-compress-cache-iceberg/) — accessed 2026-08-01. That's a ~300x reduction from format + partitioning alone, which is why "did you check the table format and partition scheme" is the first question in any Athena cost review, not query rewriting.

### Redshift: RA3, distribution/sort keys, Spectrum, and its honest current position

RA3 nodes decouple compute from storage via **Redshift Managed Storage** — storage scales independently up to 64TB per node, and you size compute (node count/type) for query performance rather than for how much data you're storing [RA3 with Managed Storage — AWS Big Data Blog](https://aws.amazon.com/blogs/big-data/use-amazon-redshift-ra3-with-managed-storage-in-your-modern-data-architecture/) — accessed 2026-08-01. **Distribution keys (DISTKEY)** determine which node each row lands on; picking a key that colocates frequently-joined rows on the same node avoids expensive cross-node shuffles during joins — this is the single highest-leverage tuning decision in a Redshift schema. **Sort keys** determine on-disk ordering within each node's storage, letting range-filtered queries (again, commonly date-based) skip blocks entirely via zone maps, similar in spirit to Athena partitioning but at the storage-engine level rather than the file-layout level. **Spectrum** lets a Redshift cluster query data sitting in S3 directly, without loading it into managed storage first — useful for querying cold/rarely-accessed data or joining warehouse tables against a data lake without an ETL step, though it doesn't add to the cluster's own storage or benefit from RA3's storage scaling since the data never lands there.

The honest current position: Redshift is cluster-billed (you pay for provisioned compute-time, or Redshift Serverless's RPU-hours) where Athena and BigQuery are pure query-billed (you pay for bytes scanned, nothing when idle) — this is *the* architectural fork in the cross-cloud map, and it flips the cost-optimization conversation from "control what you scan" (Athena/BigQuery) to "size and schedule your cluster correctly, and use Serverless for spiky workloads" (Redshift). Redshift remains the right choice when you need a persistent, low-latency, BI-tool-friendly warehouse serving lots of concurrent dashboard queries; it's the wrong choice for ad hoc, infrequent, exploratory analytics on a data lake, where Athena's zero-idle-cost model wins outright.

### Kinesis Data Streams vs Firehose vs MSK

| | Kinesis Data Streams | Firehose | MSK |
|---|---|---|---|
| Model | Durable, replayable stream you manage consumers for | Managed delivery pipe to a destination (S3, Redshift, OpenSearch, HTTP endpoint) | Fully-managed Apache Kafka |
| Throughput unit | Shard: 1MB/s in, 2MB/s out per shard (provisioned mode) or on-demand auto-scaling | No shard concept — auto-scales to the source | Kafka partition on real broker hardware: commonly 10-100+ MB/s per partition depending on message size/replication |
| Replay / multi-consumer | Yes — up to 8 consumers can read independently within the retention window (24h default, up to 365 days extended) | No — it's a one-way delivery pipe, not a readable stream | Yes — native Kafka semantics, arbitrary consumer groups |
| Format conversion | No, raw records | Yes — JSON to Parquet/ORC conversion built in, with buffering/batching | No, raw Kafka records; needs Kafka Connect or a consumer to convert |
| Operational overhead | Low — AWS-managed, no broker patching | Lowest — fully hands-off | Higher — broker sizing, partition planning, though AWS manages the underlying infrastructure |
| Pick when | Need custom multi-consumer processing, replay, moderate throughput, AWS-native | Lowest-effort path from any stream into a queryable S3/Parquet lake, no custom consumer code wanted | Already have Kafka producers/consumers/tooling — rewriting Kafka clients almost never pays for itself |

The deciding question in practice, in order: *do you already have Kafka clients/tooling* → MSK, full stop, because "the migration cost of rewriting Kafka clients exceeds any benefit of Kinesis" is a near-universal finding [Kinesis vs MSK — jayendrapatil](https://jayendrapatil.com/aws-kinesis-vs-msk-kafka-streaming-comparison/) — accessed 2026-08-01. If greenfield: *do you need custom multi-consumer processing or replay* → Kinesis Data Streams; *do you just need the data landed in S3/a warehouse in a queryable format with no custom code* → Firehose. Throughput math for scale planning: to match a 1GB/s Kafka topic spread over 10 partitions on 3 brokers, provisioned-mode Kinesis would need on the order of 1,000 shards, which is where on-demand mode or MSK's raw per-partition throughput starts to matter [Kinesis vs Kafka 2026](https://bigdataboutique.com/blog/amazon-kinesis-explained) — accessed 2026-08-01.

### OpenSearch: when it's the right tool, and when it's the wrong one

OpenSearch supports HNSW-based approximate nearest-neighbor and exact k-NN vector search on top of its existing lexical/full-text search engine, across FAISS, NMSLIB, and Lucene backends, and AWS positions it as the recommended vector database for Bedrock Knowledge Bases at scale [OpenSearch vector database capabilities — AWS Big Data Blog](https://aws.amazon.com/blogs/big-data/amazon-opensearch-service-vector-database-capabilities-revisited/) — accessed 2026-08-01. Recent GPU-accelerated indexing and a disk-optimized vector engine have materially cut both indexing time and cost (AWS cites roughly a third of the prior cost on 2.17+ domains for the disk-optimized engine) [Disk-optimized vector engine — AWS](https://aws.amazon.com/about-aws/whats-new/2024/11/disk-optimized-vector-engine-amazon-opensearch-service) — accessed 2026-08-01.

**When it's the wrong tool:** a team that wants zero index-tuning operational surface and doesn't need horizontal-scale control is usually better served by Bedrock Knowledge Bases (which can itself use OpenSearch Serverless, Aurora pgvector, or a dedicated vector DB as its backend, abstracted away) or a purpose-built vector DB when the workload is vector-search-dominant with no real lexical/full-text search need — running an OpenSearch cluster purely for vector search means paying for and operating a general-purpose search engine's operational surface (shard management, cluster sizing, index lifecycle) for a narrower job a dedicated vector store does with less tuning. OpenSearch earns its complexity specifically when you need **hybrid search** — combining BM25 lexical scoring with vector similarity in one query, which is the common production RAG pattern that beats pure vector search on retrieval quality — or when you're already running OpenSearch for logs/full-text and vector search is incremental cost on infrastructure you have anyway.

**Azure/GCP equivalent.** Glue → Data Factory (Azure, more code-first than Glue's job model) / Dataflow-Beam (GCP). Athena → Synapse Serverless (Azure) / BigQuery external tables (GCP, though BigQuery itself is closer in spirit to Athena's query-billed model than Synapse dedicated pools are). Redshift → Synapse/Fabric dedicated pools (Azure) / **BigQuery** (GCP — fully serverless and query-billed, the sharpest architectural contrast on this list). Kinesis → Event Hubs (Azure) / Pub/Sub (GCP). MSK → Event Hubs Kafka API (Azure) / Managed Kafka (GCP). OpenSearch → AI Search (Azure) / no direct GCP-native equivalent (commonly Elastic on GKE). See `clouds/CROSS-CLOUD-MAP.md`.

---

## Build it from scratch

Minimal Athena partition-projection table definition — the piece most likely to come up as "fix this expensive query" in an interview:

```sql
-- untested sketch
CREATE EXTERNAL TABLE events (
    event_id string,
    user_id string,
    payload string
)
PARTITIONED BY (dt string)
STORED AS PARQUET
LOCATION 's3://my-bucket/events/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.dt.type' = 'date',
    'projection.dt.range' = '2024-01-01,NOW',
    'projection.dt.format' = 'yyyy-MM-dd',
    'storage.location.template' = 's3://my-bucket/events/dt=${dt}/'
);

-- This query only scans the single day's prefix, not the whole table's history,
-- and needs no crawler run or MSCK REPAIR to pick up new days as they land.
SELECT user_id, count(*) FROM events WHERE dt = '2026-08-01' GROUP BY user_id;
```

Minimal Glue job DPU-hour cost estimate, the kind of back-of-envelope math worth doing out loud in an interview:

```python
# untested sketch
def glue_job_cost(num_dpus: int, runtime_minutes: float, flex: bool = False) -> float:
    rate_per_dpu_hour = 0.29 if flex else 0.44
    billed_minutes = max(runtime_minutes, 1.0)  # 1-minute minimum
    return num_dpus * (billed_minutes / 60.0) * rate_per_dpu_hour

# 10 DPUs, 45-minute job, standard: 10 * 0.75 * 0.44 = $3.30
# Same job under Flex (tolerates delayed start): 10 * 0.75 * 0.29 = $2.18
print(glue_job_cost(10, 45), glue_job_cost(10, 45, flex=True))
```

---

## How it's done in production

| Concern | Tool | What it adds |
|---|---|---|
| Shared metadata across engines | Glue Data Catalog | One schema/partition registry used by Athena, Redshift Spectrum, EMR, and third-party engines |
| Table format for evolving schema on S3 | Apache Iceberg (via Glue/Athena/EMR/Redshift Spectrum native support) | ACID semantics, time travel, schema evolution on top of raw partitioned Parquet |
| Orchestration across Glue/EMR/Athena jobs | Managed Workflows for Apache Airflow (MWAA) | DAG-based scheduling, retries, cross-service dependency management |
| High-concurrency BI workload | Redshift (provisioned or Serverless) with concurrency scaling | Elastic extra compute for query bursts without resizing the base cluster |
| RAG retrieval backend | OpenSearch Service (managed) or OpenSearch Serverless | Hybrid lexical+vector search, integrates directly as a Bedrock Knowledge Bases backend |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Athena bill spikes with no query volume change | A table lost its Parquet conversion or partitioning (e.g. a pipeline change started writing raw JSON), or a new query pattern doesn't filter on the partition key | Audit recent schema/format changes; add `WHERE` clauses on the partition column; convert to Parquet |
| Glue job burns far more DPU-hours than expected | Skewed partitions causing one executor to do most of the work, or a shuffle-heavy join with no broadcast hint | Check Spark UI for skew; repartition or add broadcast join hints; consider moving to EMR for tuning control if this recurs |
| Redshift query queues under load despite a "healthy" cluster | Distribution key mismatch causing cross-node shuffle on every join, or WLM queue misconfiguration | Run `SVV_TABLE_INFO` / Advisor recommendations for dist/sort keys; review WLM queue assignment |
| Kinesis producer getting `ProvisionedThroughputExceededException` | Shard count undersized for actual write rate (1MB/s or 1000 records/s per shard) | Increase shard count or switch to on-demand capacity mode |
| MSK consumer lag growing steadily | Consumer group under-provisioned relative to partition count/throughput, or a slow downstream sink | Scale consumers, check partition count vs consumer count, profile the sink |
| OpenSearch vector queries suddenly slow | Index not using the right engine/algorithm for the scale (e.g. exact k-NN on a large index instead of HNSW ANN), or shard count too low for the data volume | Switch to HNSW ANN for large indices, review shard sizing (commonly 10-50GB/shard as a starting heuristic) |
| Partition count in Glue Catalog growing unmanageably, `MSCK REPAIR` taking minutes | Manually-registered partitions instead of partition projection for a high-cardinality time-series table | Migrate to partition projection, eliminating the catalog-entry-per-partition model entirely |

---

## Tradeoffs & when NOT to use it

- **Don't default to Glue for long-running or tuning-sensitive Spark jobs.** If a job needs specific Spark configs, custom libraries, or runs for hours with complex joins, EMR's raw cluster control usually pays for the added ops burden; poorly-tuned Spark on Glue can cost 10x a tuned equivalent.
- **Don't run Athena queries against unpartitioned, uncompressed, row-format (CSV/JSON) data at any meaningful scale.** The $5/TB rate makes format and partitioning the highest-leverage cost lever available, and skipping it is the single most common Athena bill complaint.
- **Don't choose Redshift for infrequent, exploratory, ad hoc analytics on a data lake.** A provisioned cluster billing per hour whether queried or not loses badly to Athena's zero-idle-cost model for spiky/rare query patterns; use Redshift Serverless if you need the warehouse but the load is too irregular for a provisioned cluster.
- **Don't build Kinesis Data Streams consumers from scratch if the team already runs Kafka.** The migration cost of rewriting producers/consumers, tooling, and monitoring almost never pays back versus just using MSK.
- **Don't use Firehose when you need to replay or have multiple independent consumers read the same stream.** It's a one-way delivery pipe, not a readable/replayable stream — that's what Kinesis Data Streams or MSK are for.
- **Don't stand up OpenSearch purely for vector search if you have no lexical/full-text need and want minimal index-tuning ops.** Bedrock Knowledge Bases with a simpler backend, or a dedicated vector DB, is usually less operational surface for a vector-only workload.

---

## Interview questions

### Q1 — When would you choose EMR over Glue for a new ETL pipeline?
**Testing:** whether "serverless is always better" gets challenged.
**Answer:** When the job is long-running or continuous, needs specific Spark/Hadoop library versions or custom JARs Glue doesn't expose, or when the workload is complex enough that hands-on tuning (executor sizing, shuffle partitions, caching strategy) matters more than the operational savings of not managing a cluster. Glue wins for intermittent, well-understood batch ETL where zero cluster management is worth more than fine-grained control.
**Follow-up trap:** *"Give me a number for when the cost tips over."* — there isn't a clean universal number; the honest answer is that poorly-tuned Spark on Glue can burn 10x the DPU-hours of a tuned equivalent, so the real trigger is "this job's cost or runtime is unpredictable and I need to actually profile and tune it," not a fixed job-duration threshold.

### Q2 — An Athena table costs $4,500/month to query. Walk through your optimization approach.
**Answer:** Check three things in order: file format (is it Parquet/ORC or raw CSV/JSON), compression (Snappy/gzip applied), and partitioning (is the table partitioned on a column the queries actually filter on, ideally date). A documented real case went from ~15TB scanned per query to ~50GB after converting to Snappy Parquet with daily partitioning — a ~300x reduction. Only after those are fixed would I look at query-level optimization (avoiding `SELECT *`, pruning unused columns).
**Follow-up trap:** *"The table already has thousands of date partitions and the crawler run is now slow and costly too."* — switch to partition projection, which computes partition locations algorithmically from a pattern instead of registering every partition in the Glue Catalog, eliminating the crawler/`MSCK REPAIR` maintenance step entirely for well-structured time-series data.

### Q3 — Why is Redshift architecturally different from Athena/BigQuery in a way that changes how you think about cost?
**Answer:** Redshift (outside Serverless) is cluster-billed — you pay for provisioned compute time whether or not you're querying, which means cost optimization is about right-sizing and scheduling the cluster. Athena and BigQuery are pure query-billed — you pay per byte scanned and nothing when idle, which means cost optimization is about reducing what each query scans. Applying Athena-style "reduce data scanned" thinking to a Redshift bill misses the actual lever, which is cluster utilization and WLM queue efficiency.
**Follow-up trap:** *"Does Redshift Serverless close this gap?"* — mostly, yes, it bills per RPU-second rather than a fixed cluster, which is much closer to the query-billed model, but it's still charged for compute consumed by a running query rather than purely bytes scanned, so the optimization mental model is still closer to "reduce compute-seconds" than "reduce bytes scanned."

### Q4 — What's the actual role of a distribution key in Redshift, and what happens if you pick badly?
**Answer:** It determines which node each row is physically stored on. Picking a DISTKEY that colocates frequently-joined tables' matching rows on the same node lets joins execute locally; picking badly forces a cross-node shuffle on every join involving that table, which is one of the most common causes of slow Redshift queries despite an apparently healthy cluster.
**Follow-up trap:** *"What if there's no single good join key because the table is joined differently by different queries?"* — consider `DISTSTYLE ALL` for small, frequently-joined dimension tables (full copy on every node, no shuffle needed for any join), or accept the shuffle cost for the less common join pattern and optimize for the dominant one.

### Q5 — Kinesis Data Streams or MSK for a new streaming pipeline, greenfield, no existing Kafka investment?
**Answer:** Depends on the specific need: Kinesis Data Streams if AWS-native low-ops streaming with moderate throughput and simple consumer patterns is enough; MSK if you need throughput per partition that scales well beyond Kinesis's per-shard 1MB/s-in limit, need Kafka-ecosystem tooling (Kafka Streams, ksqlDB, Kafka Connect connectors), or anticipate needing that ecosystem later. Absent existing Kafka tooling, Kinesis is usually the lower-ops starting point.
**Follow-up trap:** *"The team has Kafka experience from a previous job but no existing AWS Kafka clients."* — that experience is a legitimate factor (familiarity reduces operational risk) but isn't the same as "existing tooling that would need rewriting" — the decisive factor for MSK is actual migration cost of existing producers/consumers, not team familiarity alone, though familiarity can reasonably tip a close call.

### Q6 — Why would you pick Firehose over Kinesis Data Streams even though Firehose can't be read by multiple consumers?
**Answer:** Because most "just get streaming data queryable in S3" use cases don't need multiple independent consumers or replay — they need one destination, format conversion (JSON to Parquet), buffering/batching, and automatic retry, all of which Firehose does with zero custom consumer code. Building the same pipeline on Kinesis Data Streams means writing and operating a consumer application to do the batching/conversion/delivery Firehose gives for free.
**Follow-up trap:** *"What if you later need a second consumer for real-time alerting on the same data?"* — Firehose alone can't do this; the fix is either adding Kinesis Data Streams upstream of Firehose (stream feeds both Firehose for the lake and a separate consumer for alerting) or reconsidering whether Kinesis Data Streams should have been the ingestion point from the start.

### Q7 — When is OpenSearch the wrong choice for a RAG retrieval backend, given the student's production RAG background?
**Answer:** When the workload is purely vector-similarity search with no lexical/full-text search requirement and the team wants minimal index-tuning operational surface — a dedicated vector DB or Bedrock Knowledge Bases with a simpler managed backend gives the same retrieval quality with less cluster/shard management. OpenSearch earns its complexity specifically for hybrid lexical+vector search (BM25 plus HNSW in one query), which is common in production RAG because pure vector search alone often underperforms hybrid on retrieval quality.
**Follow-up trap:** *"Isn't OpenSearch 'the AWS-recommended vector database for Bedrock'? Doesn't that settle it?"* — AWS recommending it as a scalable backend option doesn't mean it's the right choice for every team; "recommended for scale" and "lowest-ops for your specific workload" are different axes, and a team without a dedicated search/OpenSearch operator should weigh that against a fully-managed alternative.

### Q8 — Explain partition projection and why it matters beyond just "saves a crawler run."
**Answer:** Partition projection computes partition locations algorithmically from a configured pattern (a date range, an enumerated list) instead of requiring every partition to be registered as metadata in the Glue Catalog. Beyond avoiding crawler runs, it removes the metadata-lookup overhead Athena otherwise pays per query for high-cardinality time-series tables (thousands to millions of partitions), and it means new partitions are queryable the instant data lands, with no `MSCK REPAIR TABLE` or crawler re-run needed to "discover" them.
**Follow-up trap:** *"What's the tradeoff versus a normal partitioned table?"* — projection requires the partition values to be predictable/computable (dates, known enums) — it doesn't work for arbitrary, unpredictable partition values that need to be discovered from what's actually in S3, which is exactly what a crawler is for.

### Q9 — A Glue crawler run costs money every time it runs even if nothing changed. How would you reduce that cost?
**Answer:** Reduce crawler frequency to match actual schema-change cadence rather than running on every pipeline execution, use partition projection instead of crawler-based partition discovery for predictable time-series partitions (eliminating the need for the crawler on that table entirely), or use Glue's incremental crawl feature to scan only newly-added data rather than the whole dataset each run.
**Follow-up trap:** *"What if the schema genuinely changes unpredictably and you need the crawler?"* — then accept the cost but bound it: run against a sample or specific new-data prefix rather than crawling the entire bucket each time, since the crawler has its own DPU-hour billing with a 10-minute minimum per run.

### Q10 — Your team wants "one dashboard-friendly warehouse" but query volume is extremely spiky — near-zero most of the time, huge concurrent bursts during monthly reporting. Redshift provisioned, Redshift Serverless, or Athena?
**Answer:** Redshift Serverless is the strongest fit — it gives the BI-tool-friendly, low-latency, concurrent-query experience of Redshift without paying for a fixed provisioned cluster sitting idle most of the month, billing per RPU-second consumed instead. A provisioned cluster would mean paying for burst-capacity headroom 24/7; Athena would work for the query pattern cost-wise but loses the sub-second BI-dashboard responsiveness and connection-pooling behavior Redshift's engine is built for.
**Follow-up trap:** *"What if the monthly burst is so large that Serverless's max RPU ceiling can't keep up?"* — Redshift Serverless has a maximum RPU capacity per workgroup; if the burst genuinely exceeds it, you'd need Redshift's concurrency scaling on a provisioned cluster instead, which adds temporary extra compute specifically for query bursts.

### Q11 — Design the cheapest correct pipeline for: clickstream events arriving continuously, needing to land in a queryable data lake within 5 minutes, with no custom processing logic required.
**Answer:** Firehose directly from the event source (or fed by a lightweight Kinesis Data Streams if you also need a real-time consumer later), configured to convert incoming JSON to Parquet, buffer for up to 5 minutes or a size threshold (whichever hits first), and deliver to S3 partitioned by date/hour. Register the resulting table in Glue Data Catalog (or use partition projection) so Athena can query it immediately. No custom consumer code needed anywhere in this path.
**Follow-up trap:** *"What if 'no custom processing' later becomes 'we need light transformation before landing'?"* — Firehose supports invoking a Lambda for lightweight per-record transformation inline in the delivery stream, which covers simple cases without needing to introduce Glue or EMR into the path.

### Q12 — Why does the interviewer care whether you've actually paid an AWS data bill, rather than just knowing the service names?
**Answer:** Because the failure modes in this space are almost all cost-shaped rather than functionality-shaped — every one of these services technically works for a huge range of use cases, and the real skill is knowing which default configuration (unpartitioned Athena tables, Glue jobs with unexamined DPU allocation, an oversized Redshift cluster, Kinesis shards sized by guess) turns a reasonable architecture into an expensive one. Reciting "Glue does ETL, Athena does query-in-place" demonstrates vocabulary, not judgment.
**Follow-up trap:** *"Give a specific number you'd expect to see and be suspicious of."* — an Athena query scanning more than a few hundred MB to answer a question that's obviously time-bounded (e.g. "yesterday's events") is a signal the table isn't partitioned or isn't in a columnar format; at $5/TB that's the kind of thing that should visibly show up in Cost Explorer within the first billing cycle if unaddressed.

---

## Red flags that fail you

- Recommending Glue reflexively "because it's serverless" without asking about job duration, tuning needs, or frequency.
- Not knowing Athena bills per TB scanned, or not naming partitioning/columnar format as the primary cost lever.
- Describing Redshift and Athena/BigQuery as interchangeable without naming the cluster-billed vs query-billed distinction.
- Recommending Kinesis Data Streams for a team with an existing Kafka investment without at least raising MSK.
- Confusing Firehose (delivery pipe) with Kinesis Data Streams (readable, replayable stream) — treating them as the same thing with different names.
- Suggesting OpenSearch as the default for any vector search need with no discussion of when a dedicated vector DB or Bedrock Knowledge Bases is simpler.
- Not mentioning the Glue Data Catalog as shared infrastructure across Athena/Redshift Spectrum/EMR.

---

## Cheat card

```
GLUE        $0.44/DPU-hr on-demand, $0.29/DPU-hr Flex (tolerant batch)
            crawler: same rate, 10-min minimum per run
            worse than EMR: long-running/streaming jobs, custom libs/tuning,
                            poorly-optimized Spark can burn 10x DPU-hrs
            Data Catalog shared by Athena / Redshift Spectrum / EMR

ATHENA      $5/TB scanned, 10MB minimum per query (Presto/Trino under the hood)
            cost lever order: columnar format (Parquet/ORC) > compression
                              (Snappy 3-5x, gzip 5-10x) > partitioning (date)
            partition projection: computed partitions, no crawler/MSCK needed,
                                   for predictable (date/enum) time-series data
            real example: 15TB/query -> 50GB/query via Parquet+partition
                          ($45k/mo -> $150/mo)

REDSHIFT    RA3: compute/storage decoupled, up to 64TB managed storage/node
            DISTKEY: colocate joined rows, avoid cross-node shuffle
            SORTKEY: on-disk order, zone-map block skipping on range filters
            Spectrum: query S3 directly, doesn't add to managed storage
            CLUSTER-BILLED (or RPU-billed Serverless) vs Athena/BigQuery
            QUERY-BILLED -- this is THE architectural fork

KINESIS DS  shard = 1MB/s in, 2MB/s out; replayable, up to 8 consumers,
            24h-365d retention -- pick for custom multi-consumer/replay
FIREHOSE    one-way delivery pipe, auto Parquet conversion, zero consumer
            code -- pick for lowest-effort stream-to-lake
MSK         real Kafka, 10-100+MB/s per partition -- pick if Kafka clients
            already exist; rewrite cost almost never worth avoiding MSK

OPENSEARCH  HNSW ANN + BM25 hybrid; AWS-recommended Bedrock KB vector backend
            wrong tool when: pure vector-only workload, want zero index-
            tuning ops -> dedicated vector DB or Bedrock KB simpler backend
```

## Sources

- [AWS Glue Pricing: How Much Does AWS Glue Really Cost in 2026 — Integrate.io](https://www.integrate.io/blog/aws-glue-pricing/) — accessed 2026-08-01
- [Deciding When to Use EMR vs Glue — XTIVIA](https://www.xtivia.com/blog/amazon-emr-versus-aws-glue/) — accessed 2026-08-01
- [Amazon Athena Pricing 2026 — Cloud Burn](https://cloudburn.io/blog/amazon-athena-pricing) — accessed 2026-08-01
- [Athena Cost Optimization: Partitions, Compression, Iceberg — FactualMinds](https://www.factualminds.com/blog/athena-query-cost-optimization-partition-compress-cache-iceberg/) — accessed 2026-08-01
- [Use Amazon Redshift RA3 with Managed Storage — AWS Big Data Blog](https://aws.amazon.com/blogs/big-data/use-amazon-redshift-ra3-with-managed-storage-in-your-modern-data-architecture/) — accessed 2026-08-01
- [Kinesis Data Streams vs MSK — jayendrapatil](https://jayendrapatil.com/aws-kinesis-vs-msk-kafka-streaming-comparison/) — accessed 2026-08-01
- [Amazon Kinesis Explained — bigdataboutique](https://bigdataboutique.com/blog/amazon-kinesis-explained) — accessed 2026-08-01
- [Amazon OpenSearch Service vector database capabilities revisited — AWS](https://aws.amazon.com/blogs/big-data/amazon-opensearch-service-vector-database-capabilities-revisited/) — accessed 2026-08-01
- [Disk-optimized vector engine now available on OpenSearch Service — AWS](https://aws.amazon.com/about-aws/whats-new/2024/11/disk-optimized-vector-engine-amazon-opensearch-service) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
