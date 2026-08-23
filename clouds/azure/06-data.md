# Azure Data Deep: Synapse, Data Factory, Databricks, Event Hubs, Fabric

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-data` · **Tags:** data,analytics,critical

## The 30-second version

Azure's analytics estate is mid-transition and the interview tests whether you know which side of the transition things are on: **Microsoft Fabric** is the SaaS successor unifying lakehouse, warehouse, real-time intelligence, and Power BI onto OneLake storage with capacity-unit (CU) billing shared across every workload — Microsoft's own migration guides now treat Synapse as the source system. **Synapse** still runs production everywhere (dedicated SQL pools you pause/resume, serverless SQL billed per TB scanned, Spark pools with a 3-node minimum) but receives maintenance rather than new investment. **Databricks** remains the heavyweight independent option with Unity Catalog governance and Delta Lake, priced in DBUs. **Data Factory** moves pipelines into Fabric as its direct successor while the standalone service keeps running with three integration-runtime types. **Event Hubs** is Kafka-wire-compatible streaming where throughput units (~1 MB/s ingress each on Standard) and partition count (the hard cap on consumer parallelism per group) decide designs. The senior-level question is picking per-workload: new greenfield leans Fabric, heavy Spark/ML at scale often stays Databricks, existing Synapse estates migrate deliberately not reflexively.

## Why this gets asked

Because Azure data platforms are where architectural decisions get locked in for years and the vendor's own strategy shifted underneath everyone mid-project. Interviewers have inherited Synapse dedicated pools burning money while paused-capacity debates raged, watched Fabric capacity throttling silently slow dashboards during month-end because one workload smoothed into another's window, debugged Event Hubs consumers that couldn't scale past partition count no matter how many instances deployed, and sat through Fabric-versus-Databricks evaluations where nobody separated marketing from mechanics. What they're probing: can you reason about *compute-billing models* (DWU versus CU versus DBU versus per-TB-scan), *storage-lake semantics* (Delta ACID, shortcuts, V-order tradeoffs), and *streaming physics* (partitions = parallelism ceilings) as an integrated platform decision rather than five product names.

---

## Lineage: past → present → future

**What came before.** The pre-unified era: SQL Data Warehouse (2016) brought MPP columnstore warehousing with DWU pricing; HDInsight ran open-source Hadoop/Spark clusters customers sized and patched manually; Data Factory v1 (2015) was JSON-golf orchestration; Event Hubs (2014) preceded Kafka's dominance as Azure's ingestion funnel; Power BI grew separately as the BI layer. The pain was fragmentation — four billing models, four security models, data copied between systems for BI versus ML versus streaming, and HDInsight's operational burden killing adoption just as Databricks' managed Spark (Azure partnership, 2017-2018) proved teams would pay premium for never touching cluster plumbing.

**Where it stands now.** Synapse (2020) merged SQL DW + Spark + pipelines + Kusto into one workspace — the first unification attempt, PaaS-shaped, now explicitly the legacy path: Microsoft publishes first-party migration runbooks from Synapse to Fabric for both dedicated SQL pools and Spark workloads. Fabric (announced 2023, GA November 2023, OneLake as its "OneDrive for data") is the SaaS destination: capacities from F2 upward, lakehouse/warehouse/notebooks/pipelines/eventstreams/real-time hubs sharing one CU pool, Direct Lake mode reading Delta directly into Power BI's Vertipaq engine without import duplication, shortcuts referencing ADLS/S3 without copying, and mirroring replicating operational databases near-real-time. Databricks on Azure keeps differentiating at the frontier: Photon vectorized engine, mature MLflow/Mosaic AI stack, Unity Catalog cross-platform governance, and multi-cloud reality that Fabric cannot offer. Event Hubs standardized tiers around TUs (Standard) and PUs (Premium, ~1 PU ≈ 5-10 MB/s ingress class), kept its Kafka protocol endpoint, and added Capture for automatic landing into Blob/Data Lake. Live disagreements: Fabric CU predictability (throttling/smoothing behavior versus Databricks cluster isolation) and whether OneLake lock-in is acceptable strategic positioning or unacceptable concentration risk.

**Where it's heading.** High confidence: Fabric absorbs the Microsoft-aligned mid-market aggressively — new Power BI/Fabric SKUs ship monthly, Copilot features land Fabric-first, and Synapse guidance routes to migration runbooks; expect dedicated-pool-style provisioning to keep fading. Medium confidence: Real-Time Intelligence (Eventhouse/KQL databases, Activator alerts) becoming the default streaming-to-action path for Microsoft shops, displacing bespoke Stream Analytics architectures. Speculative-but-plausible: deeper Databricks-Fabric interoperability via open table formats (both read Delta/Iceberg) making storage-format choice matter more than compute-brand choice; treat any specific convergence timeline as speculation. The durable skill underneath all of it: medallion-architecture thinking, incremental-load patterns, and partition-aware stream design transfer across every one of these engines.

---

## Mental model

```
        ONE LAKE, MANY ENGINES  (the Fabric thesis)

   ADLS Gen2 ──shortcut──▶┐                    ┌──▶ Warehouse (T-SQL)
   Cosmos ────mirroring──▶│    O N E L A K E   │
   Snowflake/S3 shortcut ▶│  (Delta tables,    ├──▶ Lakehouse (Spark)
                           │   one namespace,   │
   Event Hubs ─eventstream▶│   ADLS-backed)     ├──▶ Real-Time (Eventhouse/KQL)
                           │                    │
                           │  billed as CAPACITY UNITS (CU/hour, F2..F2048)
                           │  smoothing: usage averaged over ~5-min buckets,
                           │  bursting above SKU, throttling when sustained
                           └──▶ Power BI Direct Lake (no import copies)

   THE OLD WORLD (still running):  Synapse workspace = dedicated pools +
   serverless SQL + Spark pools(min 3 nodes) + ADF pipelines · DWU/CU billing
   Databricks = your-subscription clusters · DBU billing · Unity Catalog
```

And the streaming physics diagram:

```
 Event Hub: [P0][P1][P2]...[Pn-1]
              ▲      ▲
   producer picks partition by key (ordering guaranteed ONLY within partition)
              │      │
   consumer group G1: instance i owns subset of partitions
   => MAX PARALLEL CONSUMERS PER GROUP = PARTITION COUNT (immutable on Standard!)
```

**The one-liner:** Fabric bets everything on shared-capacity economics over shared storage; Databricks bets on best-engine-per-dollar; Synapse waits to be migrated; Event Hubs makes you pay attention to partitions before anything else.

---

## How it actually works

### Fabric: capacities, OneLake, and the throttling model

Everything bills against **capacity units**: F SKUs from F2 (~2 CUs) to F2048, purchasable Pay-As-You-Go or reserved. Workloads don't own compute — they consume CUs from the shared pool, with **smoothing**: bursts average out over rolling windows (~minutes-scale buckets) so a 60-second intensive Spark job doesn't spike-bill like raw usage would; **bursting** lets short usage exceed the SKU baseline briefly; **throttling** kicks in when smoothed usage sustains above capacity — interactive requests delay first, then background jobs queue. Practical consequence: month-end report storms and nightly Spark waves compete inside one pool, so workload isolation planning (separate capacities per environment/severity) becomes a real architecture task, not an ops afterthought. OneLake stores everything as Delta-Parquet under one logical namespace; **shortcuts** point at external ADLS Gen2/S3/Databricks-Unity locations without copying (virtualized references); **mirroring** continuously replicates Azure SQL/Cosmos/etc. into OneLake near-real-time. Direct Lake mode lets Power BI query those Delta files with import-class speed minus import-storage duplication — falling back to DirectQuery semantics when data changes exceed cached bounds.

### Synapse: the estate you probably inherit

Dedicated SQL pools: provisioned DWU compute (100-30000 scale), pause/resume for cost control, distribution-key design (hash/round-robin/replicate) deciding shuffle costs — small dimension tables want REPLICATE, big facts hash on join keys; CTAS patterns and statistics maintenance are the tuning surface. Serverless SQL pool: pay per TB scanned (~$5/TB-class pricing), T-SQL over Parquet/CSV/Delta in the lake via OPENROWSET — brilliant for exploration, dangerous as a production serving layer because scan costs scale with query carelessness (partition pruning and file layout decide everything). Spark pools: min 3 nodes, autoscale, libraries per pool; same engine family as Databricks-with-fewer-features. Pipelines: literally ADF embedded. Data Explorer pools: hosted Kusto for log/telemetry analytics.

### Data Factory: pipelines and the three IRs

Concepts: pipelines contain activities operate on datasets through linked services. **Mapping Data Flows** compile visually-designed transformations down to Spark jobs (cluster spin-up latency makes them batch-appropriate, not micro-latency). Execution happens on **Integration Runtimes**: Azure IR (managed, region-selectable, data-movement/transformation), **self-hosted IR** (customer VM bridging on-prem/private networks — the ONLY path to on-prem sources, installable for HA), SSIS IR (lift-and-shift SSIS packages). Triggers: schedule, tumbling-window (stateful backfill/retry per window — the correct choice for incremental pipelines), event-based. Copy activity is the workhorse: staged vs direct copy, DIUs (data integration units) scaling throughput, and the 89%-latency-reduction-style wins come from parallel-copy tuning plus format choices (Parquet staging beats row-by-row JSON).

### Databricks on Azure

Runs clusters in YOUR subscription (VM costs + DBU markup above them); Photon (~2-8x on SQL-heavy workloads, vendor-measured — verify on yours) accelerates Delta scans/joins; Unity Catalog provides three-level namespace (catalog.schema.table) governance spanning workspaces; Delta Lake gives ACID transactions/time-travel/schema-evolution on the lake — the format both Fabric and Databricks read natively, making it the de-facto interoperability layer; Structured Streaming's micro-batch and (where available) continuous modes power most production pipelines; medallion layers (bronze raw → silver cleansed/conformed → gold aggregates) organize it all. Cluster economics: job clusters die with the job, all-purpose clusters bill idle time — autoscaling plus spot workers plus serverless-SQL-warehouse-style options decide whether the invoice matches the workload.

### Event Hubs: partitions, TUs, Kafka

Throughput units (Standard): each TU ≈ 1 MB/s or 1000 events/s ingress, 2 MB/s or 4096 events/s egress; namespaces bundle up to 40 TUs with auto-inflate available. Premium replaces TUs with processing units (1, 2, 4...16) — roughly 5-10 MB/s ingress per PU depending on workload shape, with CPU/memory isolation per tenant. Retention: Standard up to 7 days, Premium/Dedicated up to 90. **Partition count is set at creation on Standard** (immutable there; Premium/Dedicated allow increases) and caps consumer-group parallelism — more consumer instances than partitions sit idle. The Kafka endpoint speaks the wire protocol, so standard clients connect by swapping bootstrap servers and port (9093), but ordering guarantees map to partition semantics identically — application-level assumptions about global order break the same way they would on native Kafka. Capture writes streams to Blob/Data Lake automatically (avro/json formats) feeding batch/lakehouse paths without custom consumers.

### Sizing arithmetic that decides designs

Streaming example: 50k events/s averaging 2 KB = 100 MB/s aggregate ingress → Standard needs ≥100 TUs if purely MB/s-bound (impractical — Premium PUs or multiple namespaces become the answer), illustrating why realistic designs check BOTH the MB/s and events/s constraints per TU. Batch example: nightly 2 TB load into dedicated pool at DWU500c-class throughput takes hours; either scale DWU temporarily (linear-ish cost) or redesign into incremental loads keyed on watermark columns — the second is always the durable fix.

```python
# untested sketch — Event Hubs sizing + partition sanity checker
import math

def eh_sizing(events_per_s: float, avg_event_kb: float,
             tu_mb_s: float = 1.0, tu_events_s: int = 1000,
             max_tus: int = 40) -> dict:
    ingress_mbs = events_per_s * avg_event_kb / 1024
    tus_by_bw   = math.ceil(ingress_mbs / tu_mb_s)
    tus_by_rate = math.ceil(events_per_s / tu_events_s)
    tus_needed  = max(tus_by_bw, tus_by_rate)
    return {
        "ingress_MBps": round(ingress_mbs, 1),
        "tus_binding": "bandwidth" if tus_by_bw >= tus_by_rate else "event-rate",
        "tus_needed": tus_needed,
        "fits_standard": tus_needed <= max_tus,
        "premium_pus_estimate": math.ceil(ingress_mbs / 7.5),  # ~midpoint of 5-10
    }

def partition_check(partitions: int, consumer_instances: int,
                   peak_events_per_s: float, per_instance_capacity: float):
    idle = max(0, consumer_instances - partitions)
    effective = min(consumer_instances, partitions)
    lag_risk = peak_events_per_s > effective * per_instance_capacity
    return {"idle_instances": idle,
            "effective_parallelism": effective,
            "lag_risk": lag_risk}

print(eh_sizing(50_000, 2))          # bandwidth-bound, needs Premium territory
print(partition_check(32, 64, 120_000, 2000))   # 32 idle instances, lag risk True
```

The lesson encoded: bandwidth OR event-rate whichever binds first, and partitions — not instances — cap throughput.

---

## Build it from scratch

An incremental-pipeline watermark runner — the pattern underlying every production ELT job regardless of engine:

```python
# untested sketch — watermark-based incremental extraction with late-data handling
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

@dataclass
class WatermarkState:
    last_high: datetime          # committed extraction position
    overlap: timedelta           # re-read window for late arrivals (idempotency!)

def plan_extract(state: WatermarkState, now: datetime) -> tuple[datetime, datetime]:
    """Read [last_high - overlap, now). Downstream MERGE dedupes the overlap."""
    start = state.last_high - state.overlap
    return start, now

def commit(state: WatermarkState, new_high: datetime) -> WatermarkState:
    assert new_high > state.last_high, "watermark must advance monotonically"
    return replace(state, last_high=new_high)

if __name__ == "__main__":
    st = WatermarkState(last_high=datetime(2026, 8, 23, 0, 0),
                        overlap=timedelta(hours=1))
    lo, hi = plan_extract(st, datetime(2026, 8, 23, 1, 0))
    print(f"extract [{lo} .. {hi}) then MERGE-on-key")   # overlap absorbed by merge
    st2 = commit(st, hi)
    print("advanced:", st2.last_high)
```

Whether the MERGE target is a Synapse dedicated pool CTAS-swap, a Delta MERGE in Fabric/Databricks, or a PostgreSQL UPSERT, the skeleton is identical: monotone watermarks, deliberate overlap, idempotent merge. Late-data tolerance is a parameter you choose, not an accident you discover.

## How it's done in production

Reference estate: bronze/silver/gold Delta layers on OneLake (or Databricks-managed ADLS), Fabric capacities split prod/non-prod with monitoring app dashboards reviewed weekly, mirroring from OLTP for near-real-time silver, ADF-in-Fabric pipelines on tumbling-window triggers with watermarked increments, Event Hubs Premium fronting telemetry with Capture landing raw bronze, Databricks retained where ML lifecycle depth (MLflow registries, feature engineering at scale) exceeds Fabric's current reach; Unity Catalog or Fabric OneLake security governing access; cost control via capacity metrics review, reservation purchase on steady F-SKUs, and pipeline-level concurrency caps.

| Symptom | Cause | Fix |
|---|---|---|
| Fabric reports throttle/slow during month-end close | Multiple workloads' smoothed CU demand exceeds capacity | Split capacities by severity/environment; stagger schedules; raise SKU |
| Event Hubs consumers idle while lag grows | More consumer instances than partitions | Raise partitions (Premium/Dedicated) or repartition upstream; size instances to partition count |
| Serverless SQL query costs explode | Unpruned full-file scans on wide Parquet | Partition files by date/path, enforce predicate pushdown patterns, cap with workload labels |
| Dedicated pool queries regress after data growth | Skewed hash distributions / stale stats | Review DBCC PDW_SHOWSPACEUSED skew, rebuild stats post-load, revisit replicate tables |
| ADF copy crawls at KB/s | Single-threaded copy, wrong DIU settings, row-by-row format | Parallel copy ranges, bump DIUs, stage as Parquet, binary copy where possible |
| Kafka client loses global-order assumption after migration | Ordering exists only within partition | Key messages for co-partitioning of related events; design consumers for per-key order |

---

## Tradeoffs & when NOT to use it

- **Fabric's shared-CU model is a liability for noisy-neighbor-sensitive workloads** — one team's runaway notebook throttles another's executive dashboards; if workload isolation is contractual, Databricks' per-cluster isolation (or multiple Fabric capacities, which multiplies fixed costs) is the honest answer.
- **OneLake is strategic lock-in.** Shortcuts and Delta open formats soften exit paths, but pipelines, Direct Lake bindings, and security models assume the Microsoft estate; organizations hedging multi-cloud keep raw storage in ADLS/S3 with compute-agnostic formats and treat engines as swappable — which constrains how deep into Fabric-native features they can go.
- **Synapse dedicated pools are the wrong place for NEW builds**, but migrating running estates reflexively is also wrong: migration runbooks exist, yet T-SQL surface gaps, data-type mappings (datetimeoffset → datetime2 losing offset information), and pipeline re-validation make it a project per workspace, not a toggle.
- **Serverless SQL is an exploration layer, not a serving layer** — every careless query bills full scans; production consumption belongs in warehouse/lakehouse engines where compute is provisioned rather than per-scan.
- **Event Hubs Standard hits ceilings fast**: ~1 MB/s-per-TU means real telemetry volumes land in Premium quickly; and its 7-day retention cap breaks replay/backfill patterns Kafka users expect — plan Capture-to-lake as the durable archive rather than stretching retention.
- **Databricks costs compound quietly** — all-purpose clusters idling over weekends, DBU markup on top of VM spend, job-cluster spin-up latency encouraging always-on patterns; without cluster policies and auto-termination discipline, invoices outrun value. It remains the right answer for serious ML lifecycle work regardless.

---

## Interview questions

### Q1 — Greenfield analytics platform on Azure in 2026: Fabric, Synapse, or Databricks? Walk your decision tree.
**Testing:** current-platform judgment beyond brand recency.
**Answer:** Default Fabric for Microsoft-aligned BI + lakehouse: unified CU billing, OneLake simplicity, Power BI native integration, mirroring reducing ETL plumbing. Choose Databricks when ML lifecycle depth is primary (MLflow maturity, distributed training), Spark scale exceeds Fabric's engine comfort, cross-cloud portability matters, or Unity Catalog governance exists. Synapse only for extending existing estates; new dedicated pools are deprecated-by-guidance. Hybrid is common: Fabric for BI/serving, Databricks for heavy transformation/ML, sharing Delta tables.
**Follow-up trap:** *"Isn't betting on Fabric risky given its age?"* — risk cuts both ways: Synapse receives maintenance-level investment while Fabric ships monthly; the real analysis is lock-in depth versus momentum, a business call to surface explicitly rather than hide.

### Q2 — Explain Fabric capacity throttling mechanics and design around them.
**Testing:** whether they understand CU smoothing/bursting beyond marketing.
**Answer:** Usage smooths over rolling windows (~minutes) so short bursts average down; bursting permits brief exceedance of the SKU baseline; sustained smoothed-overage triggers progressive throttling — interactive operations delay first, background/scheduled jobs queue at severe levels. Design responses: separate capacities for prod/dev and latency-sensitive BI versus batch Spark; stagger schedules away from overlapping waves; monitor via the Capacity Metrics app with alerts on sustained utilization above ~80%; reserve headroom for close-period spikes.
**Follow-up trap:** *"Why did adding that nightly job slow morning dashboards?"* — background Spark usage smoothed into the same pool raised baseline pressure; interactive requests get delayed under load-shedding order — the isolation fix is capacity separation, not job tuning alone.

### Q3 — Medallion architecture: what changes between bronze, silver, gold, and where do teams mess it up?
**Testing:** pattern fluency versus cargo-culting.
**Answer:** Bronze: raw immutable landing, append-only, full fidelity including bad records. Silver: cleansed/deduped/conformed — typed columns, PII handling, merge-upserts on business keys. Gold: aggregates/business marts serving BI/ML directly. Common failures: transforming in bronze (loses auditability/replay), skipping silver (gold built on garbage), embedding business logic in ingestion so schema drift becomes catastrophic, neglecting Delta OPTIMIZE/vacuum schedules until small-file explosion tanks query latency.
**Follow-up trap:** *"Who owns late-arriving corrections?"* — silver MERGE logic keyed on event time plus watermark overlap windows making merges idempotent; teams assuming arrival-order correctness build silent corruption.

### Q4 — ADF integration runtimes: when is self-hosted IR mandatory and how do you run it reliably?
**Testing:** hybrid data-movement realism.
**Answer:** SHIR is the only path to sources behind private networks/on-prem (SQL Servers, file shares, SAP) without Azure line-of-sight. Reliability: 2+ nodes for HA sharing one IR, sized to copy throughput, network-placed near sources, patch-channel policy defined, queue depth and heartbeat monitored, credentials via encrypted store or Key Vault references. Azure IR region choice also matters for egress and compliance boundaries.
**Follow-up trap:** *"Copy fails intermittently through SHIR during backup windows."* — contention on the SHIR host itself; scale up or separate SHIR from other workloads — the IR is software on YOUR VM, not magic Microsoft infrastructure.

### Q5 — Event Hubs partition strategy for clickstream: 200k events/s peak, ~500 bytes average, strict per-user ordering required.
**Testing:** partition math plus key-design reasoning.
**Answer:** Throughput: ~100 MB/s ingress — far past Standard's ~40 TU ceiling (~40 MB/s), so Premium (~10-14 PUs by bandwidth) or Dedicated. Partitions sized for consumer parallelism plus headroom since Standard can't change post-creation — think 64-128. Per-user ordering via partition key = user_id (co-partitioning gives within-partition ordering); whale users create hot partitions — acceptable because ordering forces co-location, but monitor skew. Consumers scale up to partition count; extra instances idle by design.
**Follow-up trap:** *"What happens to ordering during rebalances?"* — ownership handoffs pause/duplicate partition processing briefly (at-least-once); downstream must be idempotent/merge-capable since exactly-once across rebalances needs transactional checkpoint patterns.

### Q6 — Compare billing models: DWU vs CU vs DBU vs per-TB-scanned vs TU/PU. Where does each bite?
**Testing:** cost-model literacy separating seniors from tutorial-followers.
**Answer:** DWU: provisioned regardless of use — bites idle estates; automate pause/resume. CU: smoothed shared capacity — bites under concurrent workload waves via throttling though bursts average favorably. DBU: per-compute-second markup atop VM costs — bites idle all-purpose clusters. Serverless SQL per-TB-scanned: bites careless queries against unpartitioned files. TU/PU: pre-provisioned hourly — bites rare-peak sizing; Premium's PU floor punishes small-but-spiky streams.
**Follow-up trap:** *"Which surprises new teams most?"* — serverless-SQL scan pricing: one exploratory join over wide Parquet scans terabytes invisibly; enforce pruning patterns and isolate exploration accounts so finance sees it coming.

### Q7 — Your Synapse dedicated pool runs fine weekdays but Monday loads regress badly. Diagnose systematically.
**Testing:** MPP-specific debugging craft.
**Answer:** In order: weekend growth changing distributions — check hash-distribution skew (data movement in plans, uneven space usage); stale statistics after big loads — rebuild before Monday queries; tempdb contention from concurrent CTAS-heavy pipelines; materialized views stale forcing recomputation; resource-class/concurrency-slot starvation from someone's new superuser-class job. Fixes follow diagnosis: re-distribute hot tables, stats maintenance inside load pipelines, workload classifiers for isolation.
**Follow-up trap:** *"Why do replicate tables help dimension joins?"* — full copies cached per node eliminate shuffle for small dimensions; they degrade once tables grow (per-load replication overhead) — size thresholds matter more than blind replication.

### Q8 — Design near-real-time operational reporting with OLTP changes visible in dashboards within ~2 minutes.
**Testing:** modern CDC/mirroring fluency.
**Answer:** Fabric mirroring from Azure SQL/Cosmos continuously replicates into OneLake Delta (~minutes-class latency), Direct Lake dashboards read it — minimal custom plumbing. Classic alternative: CDC → Event Hubs → Stream Analytics/Fabric eventstream → KQL database/warehouse. Choose mirroring for standard sources wanting managed simplicity; explicit CDC pipelines when en-route transformations, multi-source merges, or sub-minute SLAs demand control. Either way never point BI directly at OLTP primaries for these SLAs — connection storms and replica lag both bite.
**Follow-up trap:** *"What breaks mirroring during bulk updates?"* — large batch UPDATEs create change backlogs spiking replication lag; monitor lag as an SLO and chunk maintenance operations instead of discovering stale dashboards mid-quarter-close.

### Q9 — When would you still pick standalone Data Factory over Fabric Data Factory?
**Testing:** knowing the successor's current gaps honestly.
**Answer:** Legitimate cases: SSIS lift-and-shift (SSIS IR has no Fabric equivalent), deep reliance on mature ADF features (SSIS packages, certain integration types still absent), organizations standardizing pipelines outside Fabric licensing while keeping ADF's consumption billing, or change-management processes pinned to ADF's ARM/Bicep deployment story. Otherwise Fabric Data Factory inherits the same pipeline/dataflow concepts with Gen2 dataflows and native OneLake targets, so greenfield pipelines default there.
**Follow-up trap:** *"How painful is moving ADF pipelines later?"* — concept mapping is direct (pipelines/activities/linked services survive) but connection objects, IR bindings, trigger identities, and CI/CD wiring all move; treat it as re-platforming with translation, not copy-paste.

### Q10 — Delta Lake vs plain Parquet on the lake: what does ACID actually buy, what does it cost?
**Testing:** format-level understanding beneath both Databricks and Fabric.
**Answer:** Buys: transactional reads/writes across files (no readers seeing half-written datasets), MERGE/UPDATE/DELETE on lake tables, time-travel for audits/rollbacks, schema enforcement+evolution, and the metadata enabling fast metadata queries. Costs: transaction-log overhead, small-file problems requiring OPTIMIZE/compaction jobs, vacuum management balancing time-travel retention against storage bills, and writer-version compatibility discipline between engines. Plain Parquet remains right for immutable append-only archives where nobody mutates anything.
**Follow-up trap:** *\"Why did concurrent writers start failing?\"* — Delta serializes commits per table; hot-table high-concurrency writes conflict and retry-thrash — partition-wide transactions or staging-then-MERGE patterns fix contention that naive parallel writers create.

### Q11 — Your Fabric Spark notebook takes 40 minutes while the same logic on Databricks took 8. Explain plausible causes before blaming hardware.
**Testing:** Spark-runtime differences knowledge.
**Answer:** Check: runtime version differences (Fabric RT 1.3 = Spark 3.5 GA; older RT pinning), Native Execution Engine availability (Velox/Gluten acceleration, up to ~4x TPC-DS-class gains when applicable), starter-pool vs custom sizing and node counts (Fabric supports single-node minimums — misconfigured pools may run undersized), high-concurrency mode sharing sessions, V-order write overhead inflating write-heavy stages (~15-33%), missing Photon-equivalent acceleration on specific operators, and library/JVM differences. Also verify data locality: reading via shortcut from external storage adds latency versus co-resident OneLake.
**Follow-up trap:** *\"After tuning it's still slower — accept it?\"* — quantify the gap against cost: if the workload is ML-lifecycle-heavy, keep it on Databricks and land results as shared Delta; platform-per-workload beats forcing everything through one engine.

### Q12 — Rank these incidents by frequency in Azure data estates: CU throttling, partition starvation, scan-cost blowouts, dedicated-pool skew regressions. Justify.
**Testing:** operational prioritization grounded in how these platforms fail.
**Answer:** 1) Scan-cost/careless-query blowups — serverless SQL and any per-scan model punish exploration constantly, quietly. 2) CU throttling — rises fast as Fabric adoption concentrates workloads on one capacity. 3) Partition starvation — classic but well-known enough that designs pre-size partitions; bites migrations most. 4) Pool skew regressions — serious but increasingly rare as dedicated pools freeze in legacy estates. The ranking tracks how often each platform sits in production multiplied by how silently each failure mode accumulates.
**Follow-up trap:** *"Single cheapest guardrail across all four?"* — utilization telemetry wired to budgets/alerts (capacity metrics, lag monitors, scan-account segregation, skew views): every one of these failures announces itself in metrics weeks before stakeholders notice.

---

## Red flags that fail you

- Recommending Synapse dedicated SQL pools for new builds in 2026, or unaware Fabric supersedes it in Microsoft guidance.
- Treating Fabric CU capacity as per-workload isolation (it's shared and smoothed).
- Not knowing Event Hubs partitions cap consumer parallelism or that Standard can't repartition after creation.
- Claiming Kafka clients get global ordering on Event Hubs by default.
- Billing-model confusion — quoting DBU/DWU/CU interchangeably.
- Medallion architecture described as "three folders" with no Delta/MERGE/late-data mechanics.
- Missing the self-hosted IR requirement when integrating on-prem sources.
- Presenting serverless SQL as a production serving layer.

---

## Cheat card

```
FABRIC:  SaaS · OneLake (Delta everywhere) · capacities F2..F2048 shared CU pool
         smoothing (~min windows) -> bursting -> throttling (interactive first)
         Direct Lake = Power BI reads Delta w/o import · shortcuts = no-copy refs
         mirroring: Azure SQL/Cosmos -> OneLake near-real-time
         Spark RT 1.3 (3.5) GA · RT 2.0 (4.0) preview · NEE/Velox up to ~4x
         V-order: +40-60% Direct Lake reads, ~15-33% write overhead
SYNAPSE: dedicated pools DWU 100-30000, pause/resume · hash/round-robin/
         REPLICATE distributions · serverless ~per-TB scanned (exploration ONLY)
         Spark pools min 3 nodes · Data Explorer pools = Kusto
ADF:     Azure IR / SELF-HOSTED IR (only path to on-prem; run 2+ for HA) /
         SSIS IR · tumbling-window triggers for incremental · copy = DIU+parallel
DATABRICKS: your-subscription VMs + DBU markup · Unity Catalog governance
            Photon ~2-8x SQL-ish workloads · Delta ACID/time-travel · medallion
EVENT HUBS: Standard TU ~= 1 MB/s OR 1000 ev/s in, 2 MB/s / 4096 ev/s out,
            max 40 TUs/namespace · Premium PU 1-16 (~5-10 MB/s in each)
            retention std <=7 d, premium/dedicated <=90 d · partitions FIXED on
            standard = consumer-group parallelism CAP · Kafka wire endpoint :9093
            Capture -> blob/lake automatic landing

STREAM RULES: ordering only WITHIN partition · key by entity needing order
              consumers > partitions = idle instances
INCREMENTAL: monotone watermark + overlap window + idempotent MERGE

PICK: greenfield MS-stack -> Fabric · heavy ML/Spark scale -> Databricks
      legacy extension only -> Synapse · on-prem sources -> SHIR mandatory
ALERT: capacity utilization >~80% sustained · EH lag vs partitions · scan accounts
```

## Sources

- [Migration from Synapse dedicated SQL pools to Fabric — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/data-warehouse/migration-synapse-dedicated-sql-pool-warehouse); accessed 2026-08-23
- [Synapse-to-Fabric Spark migration strategy and planning — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/data-engineering/synapse-migration-strategy-planning); accessed 2026-08-23
- [Azure Event Hubs scalability guide (TUs/PUs/partitions) — Microsoft Learn](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-scalability); accessed 2026-08-23
- [Understanding Fabric Eventstream pricing — Microsoft Fabric Blog](https://blog.fabric.microsoft.com/en-us/blog/understanding-fabric-eventstream-pricing/); accessed 2026-08-23
- [Fabric Eventstreams capacity consumption — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/monitor-capacity-consumption); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
