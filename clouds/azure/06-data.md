# Synapse, Data Factory, Microsoft Fabric, Event Hubs

> **Track:** C-AZ Azure Atlas · **Time:** 2.0h · **Prereqs:** `C-AZ-storage-db` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-data` · **Tags:** data

## The 30-second version

Azure's data platform is mid-migration, and knowing that is the interview signal itself: **Microsoft Fabric** (GA 2023-2024, the current strategic focus) is where all of Microsoft's new engineering investment goes — Copilot integration, Direct Lake query acceleration, OneLake (a single logical data lake every Fabric workload reads/writes against, avoiding data duplication across Warehouse/Lakehouse/Power BI), Data Activator, Fabric Data Agents — while **Azure Synapse Analytics** (GA 2020) is in maintenance mode: security and reliability patches continue, but no major new capability lands there anymore. Synapse is **not deprecated** and existing Synapse workloads keep running, but Microsoft's explicit guidance is "start new analytics work in Fabric." **Azure Data Factory** (ADF, 2015) is the standalone orchestration/ETL service billed per-pipeline-activity-run and per-DIU-hour; **Fabric Data Factory** is the same underlying engine re-platformed inside Fabric's unified capacity model — no separate provisioning, consumption drawn from the same Capacity Unit (CU) pool as every other Fabric workload. **Event Hubs** is Azure's high-throughput event-ingestion service, billed in Throughput Units (Standard, self-serve cap 20 TU, up to 40 via support ticket) or Processing/Capacity Units (Premium/Dedicated, capacity-based rather than throttled), and its headline feature is a **Kafka-compatible protocol endpoint** that lets existing Kafka producer/consumer code talk to Event Hubs with just a connection-string and SASL config change — no application code rewrite, though it's a protocol-compatibility layer, not a drop-in replacement for every Kafka-specific admin API or exactly-once semantics guarantee. The trap for someone fluent in AWS: there is no single "this is definitely the right default" answer for Synapse-vs-Fabric the way there is for, say, Aurora-vs-RDS — it's a genuinely live migration-in-progress, and saying so explicitly is the correct, current answer.

## Why this gets asked

The interviewer has lived through (or is currently living through) a Synapse-to-Fabric migration decision at their own company, has debugged a Fabric capacity that silently throttled background pipeline runs during a traffic spike because nobody was monitoring CU utilization, has migrated a Kafka-native application onto Event Hubs and hit a feature gap in the compatibility layer nobody warned them about, and wants to know whether you can reason about a genuinely unsettled platform choice rather than reciting a static feature comparison table that's already stale by the time it's memorized.

---

## Lineage: past → present → future

**What came before.** Azure's first serious enterprise data warehouse was SQL Data Warehouse (2016), a dedicated-pool, MPP columnar warehouse rebranded as **Azure Synapse Analytics** in 2020 when Microsoft folded in Spark pools, serverless SQL pools, and Data Factory-style pipeline orchestration into one workspace — the pain Synapse solved was the fragmentation of separately provisioning and stitching together a warehouse, a Spark cluster, and an ETL orchestrator as three disconnected Azure resources. Data Factory (2015) predates Synapse and solved the more basic problem of "Azure has no native equivalent to SSIS or a modern cloud ETL orchestrator" — before ADF, cross-service data movement meant custom scripts or third-party tools. Event Hubs (2014) launched specifically to give Azure a high-throughput event ingestion story competitive with Kinesis, well before Kafka's ecosystem dominance made Kafka-protocol compatibility a business necessity rather than a nice-to-have.

**Where it stands now.** **Microsoft Fabric** unifies what Synapse fragmented across separate pool types into one **OneLake**-backed, single-copy data estate: Lakehouse, Warehouse, Power BI datasets, and Real-Time Intelligence all read/write the same underlying Delta-Parquet-format data in OneLake rather than each maintaining its own copy — this is the specific architectural bet that differentiates Fabric from "Synapse with a new UI." Microsoft's own current guidance is explicit: **new engineering investment, including Spark 4.0 support, Copilot, Data Agents, and advanced Delta Lake features, goes to Fabric; Synapse gets maintenance and security updates only.** [Fabric vs Synapse 2026 — Flexera](https://www.flexera.com/blog/finops/azure-synapse-vs-fabric/) — accessed 2026-08-08. The live disagreement isn't whether Fabric is the future (settled) but **how fast** individual enterprises should migrate given real switching costs — Fabric's capacity-unit billing model is a genuinely different cost shape than Synapse's per-pool consumption billing, and migrations are explicitly expected to run "months to years," not a hard cutover. Event Hubs' Kafka-compatible endpoint has matured to the point of being production-standard for teams wanting managed Kafka semantics without operating a cluster, supported across Standard, Premium, and Dedicated tiers.

**Where it's heading.** Fabric's roadmap points toward deeper AI-native integration (Data Agents letting natural-language queries traverse OneLake data, Copilot embedded across Data Factory/Notebooks/Warehouse authoring) as the primary differentiator over both Synapse and competing lakehouse platforms — high confidence, since this is already shipping, not speculative. The realistic expectation for Synapse is a long tail of maintenance-mode operation (years, not months) for existing enterprise deployments with high migration switching costs, not an imminent deprecation announcement — moderate confidence on exact timelines, worth a fresh check near interview time given how fast this specific area has moved.

---

## Mental model

```
SYNAPSE (2020, maintenance mode)          FABRIC (2023-24 GA, ALL new investment)
┌────────────────────────────┐            ┌──────────────────────────────────────┐
│ Dedicated SQL Pool (MPP)    │            │           OneLake (single logical     │
│ Serverless SQL Pool         │            │           data lake, Delta/Parquet,   │
│ Spark Pool                  │            │           every workload reads/writes │
│ Pipelines (ADF engine)      │            │           the SAME copy, no duplication)│
│  -- each pool separately    │            │                    │                   │
│     provisioned/billed      │            │  ┌─────────┬───────┼────────┬────────┐ │
└────────────────────────────┘            │  │Lakehouse│Warehouse│Power BI│RT Intel│ │
        no new capability                 │  │         │         │        │ +Data  │ │
        lands here anymore                │  │         │         │        │Factory │ │
                                           │  └─────────┴─────────┴────────┴────────┘ │
                                           │  Billed as ONE Capacity Unit (CU) pool,   │
                                           │  F-SKU (F2..F2048), shared across ALL     │
                                           │  workloads -- throttling is a smoothed,   │
                                           │  not hard-cutoff, background-first model  │
                                           └──────────────────────────────────────┘

EVENT HUBS: dual protocol surface
  AMQP-native clients ──┐
                        ├──► Event Hubs namespace ──► consumers (AMQP or Kafka)
  Kafka clients ────────┘     (Standard: TU-billed, throttled hard cap
                                Premium/Dedicated: PU/CU-billed, capacity-based)
```

---

## How it actually works

### Synapse Analytics — what it still is

Synapse workspaces bundle: **Dedicated SQL Pool** (provisioned MPP columnar warehouse, billed per DWU-hour regardless of query volume — the "size the cluster" model), **Serverless SQL Pool** (query-in-place over data lake files, billed per TB scanned — the "control the scan" model, Azure's rough analog to Athena), **Spark Pool** (managed Spark for big-data processing), and **Synapse Pipelines** (the Data-Factory-engine-derived orchestration layer). The architectural limitation that Fabric's OneLake specifically fixes: each of these pools can end up maintaining its own copy or projection of data, and moving data between a Dedicated SQL Pool and a Spark Pool inside the same workspace still typically means an actual data movement step, not a shared-storage read.

### Microsoft Fabric — OneLake and Capacity Units

**OneLake** is the architectural core: one logical, tenant-wide data lake (Delta Parquet format under the hood) that every Fabric workload — Lakehouse, Warehouse, Power BI's Direct Lake mode, Real-Time Intelligence — reads and writes against directly, eliminating the "export/copy data between engines" step that was routine in Synapse. **Direct Lake** is the specific Power BI acceleration that lets reports query OneLake's Delta tables directly without a separate import/DirectQuery step, closing a real performance gap that used to force a choice between import-mode speed and DirectQuery-mode freshness.

Billing is capacity-based: an **F-SKU** (F2, F4, F8, F16, F32, F64, ... up to F2048) provisions a fixed pool of **Capacity Units (CUs)**, and every Fabric workload in that capacity — pipelines, Spark jobs, warehouse queries, Power BI report refreshes — draws from the *same* CU pool rather than being billed independently. An F64 provides 64 CU-seconds of compute per second continuously (~166 million CU-seconds/month at full utilization), and F-SKUs double at each step (F2→F4→F8...→F2048). [Fabric Capacity Units explained 2026](https://powerbiconsulting.com/blog/microsoft-fabric-capacity-units-cus-explained-2026) — accessed 2026-08-08.

**Throttling mechanics** (a real production-incident source): Fabric doesn't hard-cut-off at the CU ceiling; it applies a **smoothing algorithm** — sustained usage above capacity first delays *background* operations (pipeline runs, scheduled refreshes), and only escalates to throttling *interactive* operations (live report queries) if the overage persists. Symptom pattern: users first notice slow or stalled interactive reports; data engineers separately notice pipeline completions running later than scheduled — these can look like unrelated incidents but share the same root cause. [Fabric throttling — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/enterprise/throttling) — accessed 2026-08-08. Documented upgrade signals: average CU utilization sustained above 75% for 2+ weeks, more than one throttling event per week at the same time of day, or peak-hour utilization sustained above 150%.

### Data Factory vs. Fabric Data Factory

**Azure Data Factory** is a standalone, separately-provisioned Azure resource billed on multiple dimensions: pipeline orchestration/activity runs, data-flow compute (General Purpose Data Flow compute priced around **$0.274/vCore-hour** pay-as-you-go), Integration Runtime hours, and managed storage. **Fabric Data Factory** is the same underlying pipeline engine, but re-platformed inside Fabric — it requires no separate provisioning or billing setup; its compute draws directly from the Fabric capacity's shared CU pool the same as every other Fabric workload. [ADF vs Fabric Data Factory 2026 — Team 400](https://team400.ai/blog/2026-05-azure-data-factory-vs-fabric-data-factory-choosing) — accessed 2026-08-08. The practical decision: a team already on Fabric capacity effectively gets pipeline orchestration "for free" (i.e., absorbed into existing CU spend) versus provisioning ADF as a separate billed resource — but a team with heavy, spiky ETL load can end up competing with Power BI refreshes and Spark jobs for the same shared CU pool, a real capacity-planning consideration that standalone ADF doesn't have.

### Event Hubs and its Kafka-compatible surface

Event Hubs exposes **two protocol endpoints against the same underlying data**: native AMQP, and a **Kafka protocol-compatible endpoint** — existing Kafka producer/consumer applications can point at an Event Hubs namespace by changing only the bootstrap server connection string and SASL/OAuth configuration, with no application code rewrite required for standard produce/consume operations. This is Azure's answer to needing Kafka semantics without operating a self-managed Kafka cluster or MSK-equivalent. [Event Hubs and Kafka compatibility — Conduktor](https://www.conduktor.io/glossary/azure-event-hubs-and-kafka-compatibility) — accessed 2026-08-08.

Real throughput numbers:
- **Standard tier**: billed in **Throughput Units (TUs)**. One TU = up to **1 MB/s or 1,000 events/s ingress** (whichever limit hits first), up to **2 MB/s or 4,096 events/s egress**. Self-serve cap of **20 TUs**, extensible to **40 TUs via a support ticket**. This tier is hard-throttled — exceeding the provisioned TU capacity results in throttling errors, not graceful degradation.
- **Premium tier**: billed in **Processing Units (PUs)** — 1, 2, 4, 6, 8, 10, 12, or 16 PUs per namespace. Unlike Standard, throughput isn't a hard throttle at a fixed number — actual achievable throughput depends on workload shape, with **one PU roughly delivering 5-10 MB/s ingress and 10-20 MB/s egress** for a single event hub with 100 partitions.
- **Dedicated tier**: billed in **Capacity Units (CUs)**, minimum deployment of **8 CUs**, extensible past 10 CUs via support request — this is single-tenant dedicated infrastructure, the tier for the highest, most predictable sustained throughput needs.

[Event Hubs quotas and limits — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-quotas) — accessed 2026-08-08; [Event Hubs Premium overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-premium-overview) — accessed 2026-08-08.

```python
# untested sketch — existing Kafka producer code pointed at Event Hubs,
# no application logic changes, only connection config
from kafka import KafkaProducer
import ssl

producer = KafkaProducer(
    bootstrap_servers="myeventhubnamespace.servicebus.windows.net:9093",
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username="$ConnectionString",
    sasl_plain_password="Endpoint=sb://myeventhubnamespace.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=...",
    ssl_context=ssl.create_default_context(),
)
producer.send("my-event-hub-topic", b"payload bytes")
```

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| Redshift | Synapse Dedicated SQL Pool / Fabric Warehouse | BigQuery | Redshift and Synapse Dedicated Pool are cluster-billed; BigQuery and Fabric's serverless-adjacent modes are query/capacity-billed differently again |
| Athena | Synapse Serverless SQL Pool | BigQuery external tables | Both are query-in-place, billed per data scanned |
| Glue | Azure Data Factory / Fabric Data Factory | Dataflow (Beam) | ADF is a standalone billed resource; Fabric Data Factory draws from shared capacity |
| EMR / Glue Spark | Synapse Spark Pool / Fabric Spark (notebooks) | Dataproc | Fabric's Spark is capacity-unit billed alongside everything else in that Fabric workspace |
| Kinesis | Event Hubs | Pub/Sub | Event Hubs has a native Kafka-compatible protocol endpoint; Kinesis has no equivalent Kafka-wire-protocol compatibility |
| MSK | Event Hubs (Kafka API) | Managed Kafka | Event Hubs' Kafka compatibility is a protocol-compatibility layer, not a literal Kafka broker — some Kafka-specific admin APIs and exactly-once transactional semantics have gaps versus a real Kafka cluster |
| QuickSight | Power BI (native Fabric integration via Direct Lake) | Looker | Power BI's Direct Lake mode is Fabric-specific, no equivalent depth of integration existed in classic Synapse |

---

## Build it from scratch

Minimal end-to-end shape: a Fabric Lakehouse table queried directly by Power BI via Direct Lake, illustrating the OneLake single-copy model that differentiates Fabric from Synapse, matching `labs/notebooks/06-data/`:

```python
# untested sketch — Fabric notebook (PySpark), writing to a Lakehouse table
# that Power BI can then query directly via Direct Lake with zero data
# duplication or separate import/refresh step
df = spark.read.format("csv").option("header", "true").load(
    "Files/raw/orders.csv"
)

# Writing to the Lakehouse's managed Delta table area (part of OneLake) --
# this table is now immediately queryable by Warehouse SQL endpoints AND
# by Power BI's Direct Lake mode without any data movement or duplication
df.write.format("delta").mode("overwrite").saveAsTable("orders_clean")
```

---

## How it's done in production

A typical production data platform mid-migration: **existing Synapse Dedicated SQL Pool workloads remain in place** (migration cost and risk not yet justified against maintenance-mode-but-stable operation), while **all new analytics initiatives provision directly on Fabric capacity**, sized to an F-SKU based on projected sustained CU utilization with headroom for the documented upgrade signals (75%+ sustained utilization, weekly throttling events). **Fabric Data Factory** replaces standalone ADF for new pipeline work specifically to avoid provisioning a second billed resource once Fabric capacity already exists. **Event Hubs** ingests high-volume event streams (clickstream, IoT telemetry, application logs) using the Kafka-compatible endpoint specifically to let existing Kafka-based stream-processing code (Spark Structured Streaming, Kafka Streams-based services) migrate with minimal rewrite, landing in Premium or Dedicated tier once Standard's hard TU throttling becomes a bottleneck.

| Symptom | Cause | Fix |
|---|---|---|
| Power BI reports go slow and pipeline completions run late around the same time | Fabric capacity's smoothing throttle kicked in: background operations (pipelines) get delayed first, then interactive operations (reports) throttle if overage persists | Check CU utilization trend in the Fabric capacity metrics app; if sustained above ~75% for weeks, upgrade the F-SKU rather than treating each symptom as a separate incident |
| A Kafka-based stream processor migrated to Event Hubs hits an unsupported operation | Event Hubs' Kafka endpoint is a protocol-compatibility layer, not a literal Kafka broker — some admin APIs, certain exactly-once transactional guarantees, and specific broker-side configuration knobs don't have full parity | Verify the specific Kafka feature against Event Hubs' documented Kafka-compatibility gaps before migration, not after; some gaps require Premium/Dedicated tier or an architecture change |
| Event Hubs Standard-tier producers start getting throttling errors under a traffic spike | Provisioned Throughput Units exceeded (1MB/s or 1,000 events/s ingress per TU) — Standard tier hard-throttles rather than gracefully degrading | Increase provisioned TUs (up to the 20 self-serve cap, 40 via support ticket) ahead of known traffic patterns, or move to Premium/Dedicated tier for capacity-based (non-hard-throttled) scaling |
| A team provisions Fabric Data Factory pipelines that intermittently starve Power BI refreshes | Both draw from the same shared Fabric capacity CU pool — heavy, spiky ETL competes directly with report refresh compute | Separate heavy ETL workloads onto their own dedicated Fabric capacity (or keep them on standalone ADF) rather than sharing capacity with latency-sensitive BI workloads |
| Team can't decide whether to migrate an existing Synapse Dedicated Pool workload to Fabric | Treating this as a binary "must migrate now" decision instead of Microsoft's actual guidance | Confirm Synapse isn't deprecated (maintenance mode, not sunset) — build a phased migration roadmap based on feature availability and switching cost, expected to run months to years, not a forced cutover |

---

## Tradeoffs & when NOT to use it

- **Don't recommend a hard Synapse-to-Fabric migration as universally urgent.** Synapse is in maintenance mode, not deprecated; existing stable workloads with high switching costs are legitimately fine staying put while new work goes to Fabric.
- **Don't provision Fabric capacity for a single lightweight workload without checking whether shared-capacity CU contention with other Fabric workloads (Power BI, other pipelines) is a real risk.** Heavy ETL sharing capacity with latency-sensitive BI refreshes is a documented production pain point.
- **Don't assume Event Hubs' Kafka-compatible endpoint is a literal drop-in Kafka replacement for every use case.** It's a protocol-compatibility layer with documented gaps in some admin APIs and transactional semantics — verify the specific features a migrating application depends on.
- **Don't leave Event Hubs Standard tier's TU provisioning static ahead of a known traffic spike.** It hard-throttles at the provisioned ceiling rather than degrading gracefully; proactive TU scaling (or Premium/Dedicated tier) is required for spike-prone ingestion.
- **Don't reach for Synapse Serverless SQL Pool (or Fabric's equivalent query-in-place mode) for high-frequency, low-latency query patterns.** Per-TB-scanned billing and query-in-place performance characteristics make it a poor fit for anything needing consistent sub-second response at high query volume — a provisioned warehouse or indexed store fits better.
- **Don't ignore Fabric's smoothing-throttle behavior when debugging performance incidents.** Treating a slow-report incident and a late-pipeline incident as unrelated wastes debugging time when they're often the same capacity-pressure root cause.

---

## Interview questions

### Q1 — Is Azure Synapse Analytics deprecated? What's Microsoft's actual current guidance?
**Testing:** currency and precision — the honest, current answer versus outdated "Synapse is legacy, use Fabric" oversimplification.
**Answer:** Synapse is **not deprecated** — it continues to receive maintenance and security updates, and existing workloads keep running. But it receives no major new capability investment; all of Microsoft's new engineering (Copilot, Direct Lake, OneLake, Data Agents, Spark 4.0 support) goes to Fabric. Microsoft's explicit guidance: start new analytics workloads on Fabric, keep existing Synapse workloads running, and build a phased migration roadmap expected to take months to years.
**Follow-up trap:** *"So should every existing Synapse customer start migrating immediately?"* — no, the honest answer weighs migration switching cost against the real but not urgent risk of staying on a maintenance-only platform; a stable, well-functioning Synapse Dedicated Pool workload with no pressing new-feature need has a legitimate case for staying put in the near term.

### Q2 — Explain OneLake and why it's the specific architectural feature that differentiates Fabric from "Synapse with new branding."
**Testing:** whether the actual differentiator (not just "Fabric is newer") is understood.
**Answer:** OneLake is one logical, tenant-wide data lake (Delta Parquet format) that every Fabric workload — Lakehouse, Warehouse, Power BI's Direct Lake mode, Real-Time Intelligence — reads and writes against directly, with no separate copy or export step between engines. Synapse's Dedicated SQL Pool, Serverless SQL Pool, and Spark Pool each typically maintain or require moving data into their own storage/format, so combining them still involves real data-movement steps that OneLake eliminates by design.
**Follow-up trap:** *"Does Direct Lake mode always give Power BI reports the fastest possible performance?"* — no, Direct Lake accelerates by skipping import/refresh cycles and querying OneLake's Delta tables directly, but very complex DAX calculations or extremely high query concurrency can still fall back to DirectQuery-like behavior or hit capacity throttling — it's a significant architectural improvement, not an unconditional performance guarantee.

### Q3 — A Fabric capacity shows both slow Power BI reports and late-running pipelines around the same time. Diagnose.
**Testing:** the smoothing-throttle mechanism, a real and non-obvious production incident pattern.
**Answer:** Fabric doesn't hard-cut-off at the CU ceiling; it applies a smoothing algorithm that delays background operations (like scheduled pipeline runs) first when sustained usage exceeds capacity, and only escalates to throttling interactive operations (live report queries) if the overage persists. These two symptoms — slow reports and late pipelines — are very likely the same root cause (capacity pressure) rather than two unrelated incidents, and should be diagnosed by checking CU utilization trends in the capacity metrics app rather than investigating each symptom independently.
**Follow-up trap:** *"What specific utilization pattern should trigger an F-SKU upgrade rather than just monitoring?"* — documented upgrade signals include average CU utilization sustained above 75% for 2+ weeks, more than one throttling event per week at the same time of day, or peak-hour utilization sustained above 150% — reactive one-off spikes don't necessarily require an upgrade, but sustained patterns matching these signals do.

### Q4 — Compare how Azure Data Factory and Fabric Data Factory are billed, and the capacity-planning implication of that difference.
**Testing:** the standalone-resource-vs-shared-capacity billing distinction and its real operational consequence.
**Answer:** Azure Data Factory is a standalone, separately provisioned and billed Azure resource (pipeline activity runs, data-flow vCore-hours, Integration Runtime hours). Fabric Data Factory is the same engine but draws compute from the Fabric capacity's shared Capacity Unit pool alongside every other Fabric workload in that capacity — no separate provisioning. The implication: a team already on Fabric gets pipeline orchestration effectively "free" against existing CU spend, but heavy or spiky ETL now directly competes for the same capacity pool as latency-sensitive workloads like Power BI report refreshes, a contention risk standalone ADF never had.
**Follow-up trap:** *"Is moving from standalone ADF to Fabric Data Factory always a cost win?"* — not necessarily; if the existing ADF workload is large and steady, its standalone consumption-based billing might be cheaper or more predictable than the capacity-unit cost of the F-SKU tier needed to absorb it without contention — it needs to be modeled, not assumed.

### Q5 — Explain Event Hubs' Kafka-compatible protocol endpoint and one concrete limitation a migrating team should verify before committing.
**Testing:** whether "Kafka-compatible" is understood as a protocol-compatibility layer with real, specific gaps, not a full Kafka clone.
**Answer:** Event Hubs exposes a Kafka protocol-compatible endpoint alongside its native AMQP endpoint — existing Kafka producer/consumer code can point at it by changing only bootstrap server connection details and SASL/OAuth config, no application-logic rewrite needed for standard produce/consume operations. Limitation to verify: some Kafka-specific admin APIs and certain exactly-once transactional semantics guarantees don't have full parity with a real Kafka broker — a team relying on specific advanced Kafka broker features needs to check compatibility explicitly rather than assuming "Kafka-compatible" means feature-complete parity.
**Follow-up trap:** *"Does the Kafka endpoint work on Event Hubs' Standard tier, or only Premium/Dedicated?"* — the Kafka endpoint itself is supported across Standard, Premium, and Dedicated tiers, but Standard's hard TU-based throttling still applies to Kafka traffic the same as AMQP traffic — tier choice is about throughput/scaling behavior, not Kafka-endpoint availability.

### Q6 — State the real throughput numbers for Event Hubs Standard tier and explain what happens when a producer exceeds them.
**Testing:** whether the specific numbers (not just "it scales") are known cold.
**Answer:** One Throughput Unit (TU) provides up to 1 MB/s or 1,000 events/s ingress (whichever limit is hit first) and up to 2 MB/s or 4,096 events/s egress. Standard tier self-serve caps at 20 TUs, extensible to 40 via a support ticket. Unlike Premium/Dedicated's capacity-based model, Standard tier hard-throttles: exceeding provisioned TU capacity produces throttling errors rather than graceful degradation, so proactive TU scaling ahead of known traffic patterns is required rather than relying on the platform to absorb spikes.
**Follow-up trap:** *"Does adding more TUs always linearly increase achievable throughput?"* — TUs set a throttling ceiling, but actual achievable throughput also depends on partition count and consumer parallelism; under-partitioning an event hub can leave provisioned TU capacity unused because consumers can't parallelize reads across enough partitions to reach that ceiling.

### Q7 — A workload needs the highest, most predictable sustained Event Hubs throughput with dedicated infrastructure. Which tier, and what's the minimum commitment?
**Testing:** the Dedicated tier's specific minimum deployment size.
**Answer:** Dedicated tier, billed in Capacity Units (CUs), with a minimum deployment of 8 CUs — this provisions genuinely single-tenant dedicated infrastructure rather than shared capacity metered by throughput units. Scaling beyond 10 CUs requires a support request rather than self-serve provisioning.
**Follow-up trap:** *"Is Dedicated tier's throughput also hard-throttled the way Standard tier is?"* — no, like Premium, Dedicated tier's achievable throughput depends on actual workload shape and dedicated capacity rather than a fixed per-unit throttle ceiling — it's capacity-based, not throttle-based, matching Premium's model but with single-tenant infrastructure.

### Q8 — Compare Synapse Dedicated SQL Pool billing to Synapse Serverless SQL Pool billing, and explain when each wins.
**Testing:** the cluster-billed vs. query-billed distinction, mirroring the Redshift-vs-Athena / Redshift-vs-BigQuery framing.
**Answer:** Dedicated SQL Pool is cluster-billed per DWU-hour of provisioned capacity, regardless of actual query volume — right for predictable, sustained, high-concurrency workloads where a warehouse is genuinely busy most of the time. Serverless SQL Pool is billed per TB of data scanned, query-in-place over lake files with no provisioned cluster — right for sporadic, exploratory, or low-frequency query patterns where paying for constant provisioned capacity would waste money sitting idle.
**Follow-up trap:** *"Does Fabric's Warehouse offering follow the same cluster-billed model as Synapse Dedicated Pool?"* — no, Fabric Warehouse draws from the shared Fabric capacity's CU pool rather than being separately cluster-billed — this is a materially different cost model that needs to be re-modeled, not assumed equivalent, when comparing a Synapse-based cost estimate to a Fabric-based one.

### Q9 — Design a data platform migration plan for a company running a stable Synapse Dedicated Pool warehouse alongside a growing need for near-real-time Power BI dashboards.
**Testing:** synthesizing the "not urgent to migrate, but new work goes to Fabric" guidance into an actual plan.
**Answer:** Keep the stable Synapse Dedicated Pool warehouse running as-is — no urgent migration driver exists for a stable, functioning workload. Provision new Fabric capacity specifically for the near-real-time dashboard requirement, using OneLake and Direct Lake mode to give Power BI reports fresh data without a separate import/refresh cycle — this is exactly the kind of new capability (real-time-adjacent BI) that Fabric was built for and Synapse wasn't. Over time, evaluate migrating the Synapse warehouse only if a specific new-capability need (Copilot, Data Agents, deeper OneLake integration) or a maintenance-mode risk becomes concrete, not on a fixed calendar.
**Follow-up trap:** *"Should the Synapse warehouse's data also be exposed through OneLake for consistency, even if the warehouse itself doesn't migrate?"* — Fabric supports shortcuts that can reference external data (including certain Synapse-adjacent storage) into OneLake without physically moving it, which is a legitimate middle-ground pattern worth knowing about, though the specifics of shortcut support for a given Synapse storage configuration should be verified against current documentation before committing to that design.

### Q10 — Explain why "control the scan" (Synapse Serverless / Fabric query-in-place) and "size the cluster" (Dedicated Pool / Redshift) represent fundamentally different cost-modeling disciplines.
**Testing:** the deeper cost-architecture reasoning behind the cross-cloud map's warehouse row.
**Answer:** Cluster-billed warehouses (Dedicated Pool, Redshift) require capacity planning ahead of load — you provision for expected peak or accept queueing/slower queries under-provisioned, and cost is roughly fixed regardless of whether the cluster sits idle or fully loaded. Query-billed, scan-based systems (Serverless SQL Pool, BigQuery) flip the discipline to controlling how much data each query actually scans — partitioning, clustering, and query design that minimizes scanned bytes directly reduces cost, with no idle-capacity waste but real risk of cost surprises from an unexpectedly expensive ad-hoc query scanning far more data than intended.
**Follow-up trap:** *"Which model is cheaper overall?"* — there's no universal answer; a consistently busy, high-concurrency warehouse is usually cheaper cluster-billed (you're using the capacity you're paying for), while a sporadic, exploratory, or highly variable query pattern is usually cheaper scan-billed (you're not paying for idle capacity) — the honest answer requires modeling actual usage pattern, not picking a side reflexively.

---

## Red flags that fail you

- Calling Synapse "deprecated" instead of "maintenance mode, new investment goes to Fabric."
- Describing Fabric as just "Synapse with a new UI" without naming OneLake as the actual architectural differentiator.
- Not knowing Fabric's throttling is a smoothing algorithm (background-first) rather than a hard real-time cutoff.
- Claiming Event Hubs' Kafka endpoint is a literal, fully feature-complete Kafka broker replacement.
- Not knowing Event Hubs Standard tier hard-throttles at the provisioned TU ceiling rather than degrading gracefully.
- Confusing cluster-billed (Dedicated Pool) and scan-billed (Serverless Pool) warehouse cost models.
- Presenting Synapse-to-Fabric migration as a binary, urgent, all-or-nothing decision.

---

## Cheat card

```
SYNAPSE (2020) = MAINTENANCE MODE, not deprecated. Security/reliability patches only,
  NO new capability investment. Pools: Dedicated SQL (DWU/cluster-billed, MPP),
  Serverless SQL (per-TB-scanned, query-in-place, ~Athena), Spark Pool, Pipelines.

FABRIC (2023-24 GA) = ALL new Microsoft data investment (Copilot, Direct Lake,
  Data Agents, Spark 4.0). Architectural differentiator: ONELAKE -- one logical
  Delta/Parquet lake every workload (Lakehouse/Warehouse/Power BI/RT Intelligence)
  reads/writes directly, NO cross-engine data duplication.
  Billing: F-SKU (F2..F2048, doubling ladder) = fixed Capacity Unit (CU) pool,
  ALL workloads in that capacity share the SAME CU pool (contention risk).
  THROTTLING = smoothing algorithm, NOT hard cutoff: background ops (pipelines)
  delayed FIRST, interactive ops (reports) throttle only if overage persists.
  Upgrade signals: >75% avg CU util sustained 2+ weeks, >1 throttle event/week
  same time of day, peak >150% sustained.

ADF vs FABRIC DATA FACTORY: ADF = standalone billed resource (per activity run,
  ~$0.274/vCore-hr data flow compute, IR hours). Fabric DF = same engine, draws
  from SHARED Fabric capacity CU pool, no separate provisioning.

EVENT HUBS KAFKA COMPAT: protocol-compatibility layer (change bootstrap server +
  SASL config, no app rewrite) -- NOT a literal Kafka broker clone. Gaps in some
  admin APIs / exactly-once transactional semantics -- verify before migrating.
  Supported on Standard, Premium, AND Dedicated tiers.

EVENT HUBS TIERS:
  Standard: Throughput Units (TU). 1 TU = 1MB/s or 1000 evt/s ingress, 2MB/s or
    4096 evt/s egress. Self-serve cap 20 TU (40 via support ticket). HARD THROTTLE.
  Premium: Processing Units (PU), 1/2/4/6/8/10/12/16 PU/namespace. Capacity-based,
    NOT hard-throttled. ~5-10MB/s ingress, ~10-20MB/s egress per PU (100 partitions).
  Dedicated: Capacity Units (CU), MIN 8 CU deployment, >10 CU needs support request.
    Single-tenant dedicated infra, capacity-based like Premium.

CROSS-CLOUD: Synapse Dedicated~=Redshift (cluster-billed). Serverless SQL Pool~=
  Athena/BigQuery-external (scan-billed). ADF/Fabric DF~=Glue/Dataflow.
  Event Hubs~=Kinesis (+Kafka-compat endpoint Kinesis lacks). Event Hubs Kafka API~=MSK.
```

## Sources

- [Azure Synapse vs Fabric: 9 things you should know (2026) — Flexera](https://www.flexera.com/blog/finops/azure-synapse-vs-fabric/) — accessed 2026-08-08
- [Microsoft Fabric Capacity Units (CUs) Explained: 2026 Sizing Guide](https://powerbiconsulting.com/blog/microsoft-fabric-capacity-units-cus-explained-2026) — accessed 2026-08-08
- [Understand throttling — Microsoft Fabric — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/enterprise/throttling) — accessed 2026-08-08
- [Azure Data Factory vs Fabric Data Factory — Team 400 Blog](https://team400.ai/blog/2026-05-azure-data-factory-vs-fabric-data-factory-choosing) — accessed 2026-08-08
- [Azure Event Hubs and Kafka Compatibility — Conduktor](https://www.conduktor.io/glossary/azure-event-hubs-and-kafka-compatibility) — accessed 2026-08-08
- [Azure Event Hubs Quotas and Limits Overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-quotas) — accessed 2026-08-08
- [Azure Event Hubs Premium overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-premium-overview) — accessed 2026-08-08
- [Azure Event Hubs Scalability Guide — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-scalability) — accessed 2026-08-08
- [Microsoft Fabric vs Synapse vs Databricks 2026 — EPC Group](https://www.epcgroup.net/answers/microsoft-fabric-vs-synapse-vs-databricks-2026) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
