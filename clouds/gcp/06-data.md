# GCP Data Analytics Deep: BigQuery, Dataflow, Dataproc, Pub/Sub, Looker

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** C-GCP-storage-db · **Updated:** 2026-08-23
> **Module id:** `C-GCP-data` · **Tags:** data,critical

## The 30-second version

Five services cover the analytics estate, and each has one decision that defines it. **BigQuery** bills two meters — bytes scanned (on-demand, $6.25/TiB after a free TiB/month) or slot-time (Editions capacity from $0.04/slot-hour) — and the honest crossover math compares GiB-scanned-per-slot-hour against your edition's rate, not a memorized "switch at N TB" number; storage is separate (~$0.02/GiB-month active, half that once a table sits unmodified for 90 days). **Dataflow** is managed Apache Beam: one programming model over bounded and streaming windows with exactly-once semantics via checkpointing. **Dataproc** is managed Spark/Hadoop where the winning pattern is ephemeral clusters that exist per-job. **Pub/Sub** is at-least-once messaging by default — exactly-once delivery exists but only on pull subscriptions in specific regions with throughput costs — plus ordering keys that order *per key* while serializing that key's throughput. **Looker** contributes LookML, a governed semantic layer compiled to SQL, which is why enterprises pick it despite cheaper dashboards existing. The interview core is BigQuery cost mechanics and Pub/Sub delivery semantics — both are places where hand-waving is instantly visible.

## Why this gets asked

Because these are the services where money leaks silently and correctness breaks subtly. The interviewer has seen an analyst run `SELECT *` against an unpartitioned multi-TiB table and burn thousands in an afternoon (on-demand bills bytes *read*, not rows returned — `LIMIT` doesn't save you); watched a "switch to Editions, everyone does" migration make costs worse because their workload scans little per slot-hour; debugged duplicate processing traced to assuming Pub/Sub was exactly-once; or inherited a Dataproc estate paying 24/7 for persistent clusters running four hours daily. They're probing whether you understand the metering model of each service deeply enough to predict its failure modes: bytes-vs-slots arithmetic, windowing/triggers in Beam when events arrive late, ordering keys as a throughput tradeoff rather than a free feature.

---

## Lineage: past → present → future

**What came before.** Google's internal lineage is Dremel (the 2010 VLDB paper behind BigQuery's interactive columnar engine), MapReduce/FlumeJava (which Beam's model descends from directly — FlumeJava's authorship overlaps heavily), and PubSub.io-era messaging that became Cloud Pub/Sub (GA 2015ish). The pre-BigQuery world was self-managed warehouses: Teradata appliances or Hadoop clusters where "interactive query" meant minutes-to-hours and capacity planning was a procurement exercise. Dremel's contribution was columnar storage + serving tree architecture making ad-hoc scans over petabytes return in seconds — BigQuery externalized it in 2010-2012, making it arguably the first true serverless analytics product.

**Where it stands now.** The pricing landscape restructured in July 2023: flat-rate slots died, replaced by **BigQuery Editions** (Standard/Enterprise/Enterprise Plus) with autoscaler slots and commitments, which changed the on-demand-versus-reserved calculus materially — autoscaling capacity made Editions viable for bursty workloads that previously stayed on-demand, and the GiB-per-slot-hour crossover method became the defensible way to decide. [BigQuery pricing](https://cloud.google.com/bigquery/pricing); accessed 2026-08-23. Dataflow matured into Dataflow Prime (right-sizing, vertical autoscaling ~); Dataproc added serverless Spark batches that killed most persistent-cluster justifications; Pub/Sub shipped exactly-once delivery (GA 2023) with real constraints (pull-only, regional endpoints, ordered-ack requirements). Looker split its brand: Looker proper (LookML semantic layer) versus Looker Studio (free visualization, ex-Data Studio). Live disagreement: whether BigQuery remains price-competitive against Snowflake/DuckDB-class engines for mixed workloads — Snowflake's warehouse-second metering wins steady predictable pipelines, BigQuery's zero-idle byte-metering wins spiky exploration, and honest practitioners say workload shape decides.

**Where it's heading.** High confidence: AI features absorbing into every surface — BigQuery ML plus Gemini integration for SQL generation, vector search inside BigQuery itself, continuous queries feeding LLM contexts. High confidence: open-table-format convergence — BigQuery reading/writing Iceberg and Delta tables makes the warehouse increasingly format-neutral, weakening lock-in complaints. Medium confidence: streaming-batch convergence completing in Beam/Dataflow until the distinction stops mattering operationally. Speculative: usage-based automatic Editions switching (Google already models this in slot advisors ~) — fully automated billing-mode optimization would remove a whole FinOps niche; treat as direction, not product.

## Mental model

The estate as one flow with two billing meters at the warehouse:

```
SOURCES -> Pub/Sub (at-least-once bus)  ──> Dataflow (Beam: windows, exactly-once)
   |                                              |
   | batch files                                  v
   +-------------------------------------> BigQuery  <----- Looker (LookML -> SQL)
                                            |
                              meter 1: bytes scanned ($6.25/TiB on-demand)
                              meter 2: slot-hours (Editions, $0.04-0.10/hr)

CROSSOVER MATH (the defensible version):
  on-demand GiB cost      = $6.25 / 1024 = $0.0061 per GiB
  Enterprise PAYG slot-hr = $0.06
  break-even = $0.06 / $0.0061 ~= 9.8 GiB scanned per slot-hour consumed
  workload scanning MORE than ~9.8 GiB per slot-hour -> capacity wins
  (Standard edition breaks even ~6.5, Enterprise Plus ~16.4)
  measure yours: INFORMATION_SCHEMA.JOBS has total_bytes_processed AND total_slot_ms
```

And Pub/Sub's delivery semantics in one picture:

```
topic -> subscription (each = independent stream; fan-out is N subscriptions)
  delivery default: AT-LEAST-ONCE  (duplicates possible; ack deadline expiry redelivers)
  exactly-once option: pull-only, regional endpoint, acks confirmed per-message,
                       ordering+EO limits throughput to thousands/sec (~)
  ordering keys: order PER KEY only; one outstanding message per key on push;
                 a stuck key blocks that key (not others); DLQ can break key order
```

## How it actually works

### BigQuery mechanics that decide money

- **On-demand**: $6.25/TiB scanned (US multi-region), first TiB/month free per billing account. Bills *columnar bytes read from disk*, not rows returned — `LIMIT` doesn't reduce the scan; identical queries within 24 hours hit the free result cache; every referenced table bills minimum 10 MB. On-demand draws from a shared pool of up to ~2,000 slots per project (~).
- **Capacity/Editions**: Standard $0.04, Enterprise $0.06, Enterprise Plus $0.10 per slot-hour pay-as-you-go; commitments cut Enterprise to ~$0.054/1yr and ~$0.048/3yr, Standard to ~$0.032/3yr. Reservations start at 100 slots, increments of 100, region-bound. Autoscaling slots bill per second above baseline.
- **Storage**: active logical ~$0.02–0.023/GiB-month, dropping automatically to long-term (~$0.01–0.016) after 90 days unmodified. Optional physical-storage billing trades compression: cheaper only if compression beats ~1.74:1 (~), but then time-travel bytes bill too.
- **Partitioning/clustering** are the biggest levers on either meter: partition by date column so queries prune to relevant partitions; cluster by high-cardinality filter columns. `INFORMATION_SCHEMA.JOBS` exposes `total_bytes_processed` and `total_slot_ms` per query — measure before choosing a billing mode.
- Edition feature gates matter: Standard omits BigQuery ML model training, BI Engine acceleration, and several enterprise features (~); Enterprise Plus adds compliance packaging (Assured Workloads paths, managed DR ~).

### Dataflow / Beam: windows, watermarks, triggers

Beam programs against unbounded PCollections with event-time windows; watermarks declare "no more events earlier than T expected," triggers control when window results emit (early/on-time/late panes), and allowed lateness bounds how long late data keeps updating state. Exactly-once across sources/sinks comes from checkpointed offsets plus idempotent or transactional sinks. The streaming engine offloads shuffle/state to managed services so autoscaling works mid-stream. Classic production bugs are all timing: watermark drift when a source stalls (backlog metric), dropped "late" data because allowed lateness was set to zero, and hot keys concentrating into one worker.

### Dataproc: ephemeral by default

Managed Spark/Hadoop/Hive with cluster creation in ~90 seconds (~). The pattern that wins: **ephemeral clusters** — create, run job, delete — paying only for job duration instead of idle persistence, often with preemptible/Spot secondary workers for executors. **Dataproc Serverless** goes further: submit Spark batches without any cluster object at all, billed per-DPU-second (~). Persistent clusters remain right for interactive notebooks estates (Dataproc Hub/Jupyter) where startup latency per query hurts more than idle cost.

### Pub/Sub: semantics and their costs

Topics decouple publishers from subscriptions; each subscription is an independent full copy of the stream (fan-out via multiple subscriptions, not consumer groups). Delivery is at-least-once with configurable ack deadline (10–600s, extendable via lease management), exponential retry backoff, and dead-letter topics after 5–100 max delivery attempts (forwarding is best-effort; the Pub/Sub service agent needs publisher IAM on the DLQ — the classic silent failure). Message retention up to 7 days (~) enables seek/replay. Ordering keys give per-key FIFO at real cost: reduced publish availability, higher latency, and throughput capped per key; exactly-once delivery composes with ordering only if acks arrive in order, limiting throughput further. Schemas enforce protobuf/Avro compatibility modes at publish time.

### Looker vs Looker Studio

Looker compiles LookML (version-controlled YAML-ish modeling) into governed SQL: metrics defined once, reused consistently across every dashboard and downstream tool via its API — the value is governance and consistency, not visualization quality. Looker Studio is the free dashboarding tool without the semantic layer. Enterprises standardizing metrics definitions pick Looker; quick viz needs pick Studio; both connect to BigQuery trivially.

## Build it from scratch

The billing-mode decision, computed rather than remembered:

```python
# untested sketch - BigQuery on-demand vs Editions crossover
ON_DEMAND_PER_TIB = 6.25
EDITIONS = {"standard_payg": 0.04, "enterprise_payg": 0.06,
            "enterprise_1yr": 0.054, "enterprise_3yr": 0.048}
HOURS_MONTH = 730

def break_even_gib_per_slot_hour(rate_per_slot_hour):
    per_gib = ON_DEMAND_PER_TIB / 1024
    return rate_per_slot_hour / per_gib      # GiB scanned per slot-hour

for name, rate in EDITIONS.items():
    print(f"{name}: capacity wins above {break_even_gib_per_slot_hour(rate):.1f} "
          f"GiB/slot-hour")

# From your own estate:
# SELECT SUM(total_bytes_processed)/1e9 / (SUM(total_slot_ms)/1000/3600)
# FROM `region-us`.INFORMATION_SCHEMA.JOBS WHERE creation_time > TIMESTAMP_SUB(...)

# 100-slot Enterprise reservation floor:
floor = 100 * EDITIONS["enterprise_payg"] * HOURS_MONTH
print(f"Enterprise 100-slot floor: ${floor:,.0f}/mo = {floor/6.25:.0f} TiB on-demand")
```

And the Pub/Sub reliability baseline in Terraform-shaped commands:

```bash
gcloud pubsub topics create orders
gcloud pubsub topics create orders-dlq
gcloud pubsub subscriptions create orders-sub --topic=orders \
  --ack-deadline=60 --dead-letter-topic=orders-dlq \
  --max-delivery-attempts=5 \
  --message-retention-duration=7d \
  --min-retry-delay=10s --max-retry-delay=600s
# THE silent failure fix - Pub/Sub service agent needs publisher on the DLQ:
gcloud pubsub topics add-iam-policy-binding orders-dlq \
  --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role=roles/pubsub.publisher
```

## How it's done in production

Reference architecture: events land in Pub/Sub with schemas enforced; Dataflow streams into partitioned/clustered BigQuery tables via the Storage Write API (the modern path; legacy streaming inserts bill separately ~); batch sources land via load jobs from GCS (free) or Storage Read API; transformations that are pure SQL stay in scheduled BigQuery jobs, Spark-shaped logic goes to Dataproc Serverless batches; Looker serves governed metrics on top. FinOps loop runs against `INFORMATION_SCHEMA.JOBS`: top scanners weekly, slot utilization for reservation sizing, partitioning candidates flagged by full-table-scan ratio.

| Symptom | Cause | Fix |
|---|---|---|
| BigQuery bill spiked 10× overnight | Analyst ran unpartitioned full scans on-demand | Partition + cluster; dry-run before execute (`--dry_run`); maximum-bytes-billed per query |
| "Switched to Editions and costs rose" | Workload scans <~10 GiB per slot-hour | Compute GiB/slot-hour from JOBS metadata before committing |
| Duplicate records in downstream tables | At-least-once Pub/Sub delivery assumed exactly-once | Dedup keys or exactly-once subscriptions where constraints allow |
| One Pub/Sub ordering key stalls everything behind it | Stuck message blocks its key | Per-key isolation by design; DLQ to unstick; don't order what doesn't need ordering |
| Dataflow watermark lagging hours | Source stall or hot key concentrating state | Backlog metrics alerting; fan out hot keys; check allowed lateness config |
| Dataproc cluster idle 20h/day | Persistent clusters from lift-and-shift | Ephemeral clusters per job or Dataproc Serverless batches |

## Tradeoffs & when NOT to use it

- **Don't buy Editions because "serious teams have reservations"** — the crossover is measurable per-workload; a dashboard-heavy estate scanning little data can pay multiples more on committed slots. Run the GiB/slot-hour query before committing to 1–3 years.
- **Don't use Pub/Sub ordering keys as a general correctness tool** — you trade publish availability and latency for per-key FIFO; most dedup-key designs beat ordered delivery for both performance and clarity.
- **Exactly-once Pub/Sub is not free exactly-once processing** — it guarantees no redelivery after successful ack, but your sink must still be idempotent for crashes between ack and side effect; and it's pull-only with throughput ceilings (~thousands/sec when combined with ordering).
- **Dataflow is wrong for simple scheduled SQL** — if the transform is expressible as BigQuery SQL on a schedule, Dataflow adds operational weight for nothing; it earns its keep in event-time windows, complex fan-outs, or cross-source joins.
- **Dataproc persistent clusters are almost always waste** — the interactive-notebook case is the exception worth defending explicitly, not the default.
- **Looker without metric governance needs** is expensive ceremony — if three analysts define metrics consistently anyway, Looker Studio + dbt-exposed metrics deliver similar outcomes cheaper.

---

## Interview questions

### Q1 — Explain BigQuery's two compute pricing models and how you'd decide between them for an existing estate.
**Testing:** the module's core question — metering-model literacy.
**Answer:** On-demand bills $6.25/TiB scanned (first TiB/month free), zero idle cost, ~2,000 shared slots ceiling per project (~). Editions bill slot-hours: $0.04/$0.06/$0.10 per hour (Standard/Enterprise/Enterprise Plus PAYG) with commitments cutting Enterprise to ~$0.054/1yr/~$0.048/3yr, 100-slot reservation floors, region-bound. Decide from `INFORMATION_SCHEMA.JOBS`: compute GiB scanned per slot-hour consumed across the last weeks; each edition has a break-even ratio ($0.06 ÷ $0.0061 ≈ 9.8 GiB/slot-hour for Enterprise PAYG) — above it capacity wins, below it on-demand wins regardless of monthly totals.
**Follow-up trap:** *"Isn't there a simple TB-per-month threshold?"* — rules of thumb exist (~320–700 TiB depending on edition) but they encode assumptions about scan-to-compute ratios that vary wildly by workload. The ratio method uses your actual jobs, which is why it's the defensible answer.

### Q2 — Why doesn't `LIMIT` reduce a BigQuery query's cost? What actually controls bytes billed?
**Testing:** understanding of what the meter reads.
**Answer:** The meter counts columnar bytes read from storage to *process* the query; LIMIT applies after reading, so cost is unchanged. Controls: partition pruning (query only relevant partitions via partition filters), clustering order matching filter columns, selecting explicit columns instead of `SELECT *`, materialized views pre-aggregating hot paths, `maximum_bytes_billed` as a hard per-query cap, and the 24-hour result cache making identical re-runs free. Dry-run (`--dry_run`) reports bytes before execution.
**Follow-up trap:** *"Does caching make dashboards free?"* — only exact-query matches within 24h and only for on-demand-style billing contexts; parameterized dashboard queries differ per parameter set, so cache hits are partial at best. BI Engine exists precisely for repeated-dashboard acceleration.

### Q3 — Your team moved to Enterprise Edition and costs went up 40%. Diagnose properly.
**Testing:** whether they reach for measurement or folklore.
**Answer:** Query `INFORMATION_SCHEMA.JOBS` for total_slot_ms versus bytes processed over representative weeks. Likely finding: workload scans few GiB per slot-hour (small tables, heavy joins/aggregations — compute-heavy not scan-heavy), so on-demand's byte meter was cheaper despite high query volume. Remedies: revert billing mode where possible, reserve only baseline with autoscaler for peaks, move genuinely scan-heavy workloads onto the reservation and leave compute-heavy ones on-demand (mixed assignment).
**Follow-up trap:** *"Can we mix billing modes?"* — yes: assignments route projects/folders to reservations while everything else stays on-demand, which is how you optimize heterogeneous estates rather than forcing one mode org-wide.

### Q4 — Design ingestion for 50k events/sec into BigQuery with sub-minute freshness.
**Testing:** streaming-path fluency including current best practice.
**Answer:** Producers publish to Pub/Sub (schema-enforced); Dataflow streams, windows, and writes via the Storage Write API into date-partitioned, clustered tables — Write API is the modern mechanism (gRPC, lower cost than legacy streaming inserts, exactly-once semantics via default stream ~). Set allowed lateness for late events, dead-letter malformed payloads, monitor watermark backlog and BigQuery stream insertion errors. Alternative without Dataflow: direct Storage Write API from producers when transforms are trivial.
**Follow-up trap:** *"Why not legacy streaming inserts?"* — they still work but bill separately (~$0.01/200MB ~) and lack the Write API's exactly-once append semantics and pending-stream flexibility; new designs should standardize on Storage Write API.

### Q5 — A downstream table shows duplicate rows traced to Pub/Sub. Walk me through why and every fix tier.
**Testing:** delivery-semantics depth.
**Answer:** Default Pub/Sub is at-least-once: ack-deadline expiry, client disconnects, or failed ack handling cause redelivery — duplicates are normal behavior, not bugs. Tiers: (1) application idempotency via message_id/dedup keys in sink (works everywhere, always correct); (2) exactly-once delivery subscriptions — pull-only, regional endpoints, ack confirmation, throughput cost; (3) structural avoidance — BigQuery subscriptions write once per message into tables directly. Never fix by "just retry less": that trades duplicates for losses.
**Follow-up trap:** *"Is exactly-once delivery end-to-end exactly-once processing?"* — no: it removes redelivery-after-ack, but a crash between external side effect and ack still double-applies unless the side effect itself is idempotent. Exactly-once remains an application composition property.

### Q6 — When do ordering keys help, and what do they cost?
**Testing:** knowing the price of a feature most treat as free.
**Answer:** They give FIFO per key — right when state transitions must apply in sequence per entity (account updates, per-device telemetry folds). Costs: publish availability drops (ordering requires coordination), latency rises, one stuck/unacked message blocks its key's tail, push allows one outstanding message per key, and combining with exactly-once caps throughput around thousands/sec (~). DLQ forwarding can break key order. Keys should be as narrow as correctness requires — per-entity, never global.
**Follow-up trap:** *"Dataflow consumer — enable keys?"* — no: Beam orders via its own windowing/watermark machinery; enabling Pub/Sub ordering under Dataflow degrades pipeline performance for nothing.

### Q7 — Ephemeral clusters vs Dataproc Serverless vs persistent cluster: decide for three shapes.
**Testing:** Spark-ops judgment.
**Answer:** Scheduled nightly PySpark ETL → ephemeral clusters (create/run/delete, Spot secondary workers) or Serverless batches if versions fit — zero idle. Ad-hoc analyst notebooks all day → persistent small cluster with autoscaling, because per-session startup would dominate experience. Massive periodic backfills → Serverless batches with parallelism, paying DPU-seconds only (~). Persistent clusters are the exception needing justification, not the default.
**Follow-up trap:** *"Serverless limits that bite?"* — runtime version constraints, no custom init actions/forks beyond supported config (~), queue-based concurrency quotas. When any of those bind, ephemeral clusters restore control at the price of managing creation.

### Q8 — Where does Looker earn its cost versus Looker Studio plus dbt metrics?
**Testing:** whether they understand the semantic-layer argument, not brand preference.
**Answer:** Looker compiles LookML into governed SQL: one definition per metric reused across dashboards, API access, row-level permissions applied centrally — value shows when many teams consume consistent definitions and auditability matters. If metrics live in dbt anyway, Looker Studio visualizing modeled tables achieves much of the outcome free; Looker's remaining edge is its modeling layer's interactivity (drilling, cross-view exploration) and enterprise governance features.
**Follow-up trap:** *"So Looker is just expensive dashboards?"* — the defensible framing: it's a metrics governance platform whose dashboards are incidental; priced accordingly, bought accordingly — organizations without definition-drift problems shouldn't buy it.

### Q9 — A Dataflow pipeline's watermark keeps falling behind. Diagnose systematically.
**Testing:** streaming debugging literacy.
**Answer:** Watermark = service's estimate of complete event time; lag means data arrives slower than processing or sources stall. Checks: backlog metrics (oldest unprocessed event age), worker CPU saturation (scale out), hot keys concentrating state into one thread (fan-out/re-key), source throttling (Pub/Sub quota, backlogs), and GC/stragglers (Dataflow Prime right-sizing helps ~). Config-level causes: allowed lateness and trigger settings interacting badly with window sizes.
**Follow-up trap:** *"Watermark is fine but results are late anyway."* — then latency lives outside event-time bookkeeping: sink throughput (BigQuery Write API quotas), downstream load, or trigger emission timing. Separate pipeline-internal from sink-side before tuning windows.

### Q10 — Design the FinOps loop for a 200-person org querying BigQuery.
**Testing:** operationalizing cost control beyond one-off fixes.
**Answer:** Weekly `INFORMATION_SCHEMA.JOBS` review: top-N by bytes and by slot-hours, full-scan ratio per table (partitioning candidates), per-project/per-user attribution via labels. Controls: `maximum_bytes_billed` defaults in BI tooling, custom query pricing tiers via reservations only where measured, staging dataset expirations, authorized views for sensitive/expensive joins. Alerts on daily spend anomalies; slot advisor for reservation sizing (~). Culture: dry-run requirement for new scheduled queries.
**Follow-up trap:** *"Who pays when marketing runs wild queries?"* — chargeback needs attribution: enforce query labels via custom constraints/IAM conditions where possible and assign projects per domain so billing export splits cleanly. Attribution designed after the fact is archaeology.

### Q11 — Compare Pub/Sub against Kafka-style log semantics honestly.
**Testing:** cross-system messaging literacy for a polyglot profile.
**Answer:** Pub/Sub is a managed queue/topic bus: at-least-once, per-subscription independent streams, ack-based consumption, retention up to ~7 days for replay — no consumer-group offset semantics like Kafka logs; seek/snapshot provides replay but not arbitrary re-read of an immutable log as first-class storage. Kafka wins retention-as-storage, ecosystem (Connect/Streams), ordering-per-partition with partition-count parallelism; Pub/Sub wins zero-ops global scale, per-message DLQ/retry policies, push integrations, Eventarc coupling. Choose by whether you need a *log* (Kafka) or *messaging* (Pub/Sub).
**Follow-up trap:** *"Can Pub/Sub act Kafka-ish?"* — partially: longer retention + file sinks to GCS approximates replayable streams, but offset-anchored consumer semantics don't exist; designs depending on them should use Kafka/managed Kafka equivalents.

### Q12 — What breaks first at 10× data volume in this stack?
**Testing:** capacity reasoning under scaling pressure.
**Answer:** Ordered by typical failure point: Pub/Sub ordering keys (per-key serialization caps) break before unordered topics do; Dataflow hot keys concentrate before aggregate throughput does; BigQuery ingestion rarely breaks (Write API scales) but slot contention on concurrent transforms does — autoscaler absorbs if Editions configured; Looker dashboards hitting raw detail tables degrade before BigQuery does — aggregate tables/materialized views are the relief valve. The pattern: serialization points (keys, single-threaded state, dashboard fan-in) fail first, not raw throughput limits.
**Follow-up trap:** *"Pre-emptive fixes ranked?"* — remove unnecessary ordering keys now, re-key hot partitions now, set autoscaling bounds + alerts now, pre-aggregate known-heavy dashboards next. All cheaper than incident-driven discovery.

---

## Red flags that fail you

- Quoting "switch to slots around N TB/month" without the GiB-per-slot-hour method.
- Believing LIMIT reduces bytes billed or that result caching covers parameterized dashboards.
- Assuming Pub/Sub is exactly-once by default, or that exactly-once delivery makes side effects idempotent.
- Using ordering keys globally instead of per-entity, unaware of the availability/latency price.
- Running persistent Dataproc clusters for scheduled batch jobs.
- Confusing Looker with Looker Studio, or justifying Looker without a metric-governance argument.

## Cheat card

```
BIGQUERY COMPUTE: on-demand $6.25/TiB scanned (1 TiB/mo free; min 10MB/table;
  LIMIT does NOT reduce scan; 24h result cache free; ~2000 shared slots ~)
  Editions slot-hour: Std $0.04 | Ent $0.06 | Ent+ $0.10 PAYG
    commitments: Ent ~$0.054/1y, ~$0.048/3y; reservations min 100 slots, regional
  CROSSOVER: $0.0061/GiB on-demand -> Ent breaks even at ~9.8 GiB/slot-hr
    measure: INFORMATION_SCHEMA.JOBS (total_bytes_processed / total_slot_ms)
BIGQUERY STORAGE: active ~$0.02-0.023/GiB-mo -> long-term (~half) at 90d untouched
  partition + cluster = biggest lever; maximum_bytes_billed as circuit breaker
LOADS: batch loads from GCS free; Storage Write API = modern streaming path
  (legacy streaming inserts bill separately ~)

DATAFLOW: managed Beam - windows/watermarks/triggers/allowed-lateness;
  exactly-once via checkpoints + idempotent sinks; hot keys & watermark lag
  are the classic failures; Prime adds right-sizing (~)

DATAPROC: ephemeral clusters per-job > persistent (idle = waste);
  Serverless batches = no cluster object, DPU-seconds (~); Spot secondary workers

PUB/SUB: default AT-LEAST-ONCE; ack deadline 10-600s; retry backoff;
  DLQ after 5-100 attempts (best-effort forward; service agent NEEDS publisher
  IAM on DLQ - classic silent failure); retention <=7d for seek/replay
  ordering keys: FIFO PER KEY, costs publish availability + latency,
                 stuck key blocks its tail; Dataflow: do NOT enable keys
  exactly-once delivery: pull-only, regional endpoints, ordered acks required,
                         ~thousands msg/s with ordering (~)
LOOKER: LookML semantic layer -> governed SQL metrics (governance value);
  Looker Studio = free dashboards without semantic layer
```

## Sources

- [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing); accessed 2026-08-23
- [BigQuery cost: on-demand vs slots — c3x.dev](https://c3x.dev/blog/gcp-bigquery-on-demand-vs-flat-rate-cost/); accessed 2026-08-23
- [The real crossover between BigQuery on-demand and Editions — AgentSQL](https://agentsql.com/bigquery-pricing); accessed 2026-08-23
- [BigQuery pricing models compared — FollowRabbit](https://followrabbit.ai/blog/comparing-bigquery-pricing-models-on-demand-vs-capacity-based); accessed 2026-08-23
- [Exactly-once delivery — Pub/Sub docs](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery); accessed 2026-08-23
- [Order messages — Pub/Sub docs](https://docs.cloud.google.com/pubsub/docs/ordering); accessed 2026-08-23
- [Pub/Sub dead letter topics implementation guide](https://oneuptime.com/blog/post/2026-01-26-pubsub-dead-letter-topics/view); accessed 2026-08-23
- [BigQuery Pricing 2026 reference — CheckThat](https://checkthat.ai/brands/bigquery/pricing); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
