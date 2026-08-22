# Databricks vs Snowflake vs BigQuery vs Redshift — the Honest Matrix

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-databricks-vs-snowflake` · **Tags:** tradeoffs,critical

## Why this gets asked

Because every candidate has a favorite and will pitch it like a vendor rep. The interviewer has sat in a real vendor bake-off, watched a platform get chosen for the wrong reason (a VP liked a demo), and lived with the multi-year consequence. What they're actually testing is whether you can hold two platforms' genuine strengths and genuine failure modes in your head at once without collapsing into "it depends" — and whether you know these products have been converging for two years, so a comparison written in 2024 is already stale on several axes.

---

## Lineage: past → present → future

**What came before.** Before cloud warehouses, the choice was an on-prem MPP appliance (Teradata, Netezza) sized for peak load and owned for years regardless of actual usage, or a Hadoop cluster where "warehouse" meant Hive on top of MapReduce, brutally slow for interactive SQL. The pain was capacity planning as a multi-year bet: overprovision and waste capital, underprovision and blow a quarter-end close. Redshift (2012) was the first mainstream cloud-native answer, but it still coupled storage and compute at the node level early on. Snowflake (GA 2014) and BigQuery (GA 2011, built on Google's internal Dremel) both separated storage from compute from the start, for different reasons — Snowflake to sell warehouse elasticity, BigQuery to eliminate cluster management entirely. Databricks came from a different direction: it started as managed Spark for data engineering and ML, and only became a warehouse competitor once Delta Lake and Databricks SQL matured enough to serve BI workloads credibly.

**Where it stands now.** All four are viable, all four are used by companies that are happy with the choice, and the honest 2026 position is that the products have converged more than marketing from any of them admits. Snowflake added Snowpark (Python execution) and Iceberg table support to compete on Databricks' ML/open-format turf. Databricks added Databricks SQL, serverless SQL warehouses, and BI-friendly features to compete on Snowflake's turf. BigQuery added BigQuery ML and Vertex AI integration to compete on the ML axis. Redshift added Serverless and RA3's storage/compute separation to stop bleeding customers to the other three. The genuine remaining differentiators are less "what can it technically do" and more organizational: which cloud you're already committed to, which workload dominates (ETL/ML-heavy vs. BI/SQL-heavy vs. ad-hoc/spiky), and how much operational tuning your team wants to own.

**Where it's heading.** The clearest trend is the catalog becoming the real point of lock-in, not the storage format — all four now support or are converging on Apache Iceberg with the REST Catalog protocol as the neutral interchange layer (Unity Catalog, Snowflake's Polaris/Open Catalog, Glue, BigQuery's BigLake). That means "which storage format" is decreasingly the strategic question and "which catalog governs your data, and how portable is that catalog" increasingly is. Expect the gap between these platforms to keep narrowing on raw capability while the actual switching cost keeps rising, because catalogs, orchestration patterns, and institutional tooling are stickier than file formats ever were. Treat any claim that one platform has "permanently won" a workload category as speculative — this list has a shelf life measured in quarters, not years.

---

## Mental model

```
                     WORKLOAD SHAPE  ──────────────────────────────▶
        ETL/ML-heavy, flexible code           BI/SQL-heavy, predictable, ad-hoc/spiky
                  │                                              │
                  ▼                                              ▼
            ┌───────────┐                                 ┌─────────────┐
            │ DATABRICKS │                                 │  SNOWFLAKE   │
            │ Spark-native,                                │  SQL-native,  │
            │ MLflow, GPU                                   │  near-zero    │
            │ clusters,                                     │  tuning,      │
            │ open lakehouse                                │  strong       │
            │ (Delta/Iceberg)                                │  concurrency  │
            └───────────┘                                 └─────────────┘
                  │                                              │
      ┌───────────┴──────────┐                    ┌──────────────┴────────────┐
      ▼                                            ▼                            ▼
┌───────────┐                              ┌─────────────┐              ┌─────────────┐
│  REDSHIFT  │                              │  BIGQUERY    │              │ (any: now    │
│  AWS-native,                              │  truly        │              │  Iceberg-    │
│  RA3 managed                              │  serverless,  │              │  compatible) │
│  storage,                                 │  no cluster,  │              │              │
│  mature but                               │  spiky/ad-hoc │              │              │
│  legacy pull                              │  analyst load │              │              │
└───────────┘                              └─────────────┘              └─────────────┘
```

No axis here is binary. The matrix below is the actual decision surface.

## How it actually works: the decision matrix

| Axis | Databricks | Snowflake | BigQuery | Redshift |
|---|---|---|---|---|
| **Workload fit** | ETL/ML/streaming-heavy, Spark-native, notebook-first | BI/SQL-heavy, high concurrency, near-zero tuning | Serverless ad-hoc/spiky analyst load, no cluster to size | AWS-centric mixed BI/ELT, tight S3/Glue/Kinesis integration |
| **Storage format** | Delta Lake (open) + native Iceberg/Hudi support via UniForm | Proprietary native format (fast path) + external Iceberg tables (catching up, not full parity) | Proprietary (Capacitor/Colossus) + BigLake external Iceberg | Proprietary, RA3 "managed storage" separates node from storage |
| **Real lock-in point (2026)** | Historically Unity Catalog; now open-sourced core + Iceberg REST server | Native-table performance features (clustering, Time Travel, clone) don't fully transfer to Iceberg tables yet | BigQuery-native SQL dialect and BI Engine/materialized-view tooling | Deep AWS ecosystem integration (IAM, Glue, Kinesis) |
| **Pricing model** | DBU/hour by compute type + separate cloud VM cost ("two bills") | Credits/hour by warehouse size, doubles per T-shirt size | On-demand $/TiB scanned, or capacity $/slot-hour | On-demand $/node-hour (RA3) or $/RPU-hour (Serverless) + managed storage $/TB |
| **Where it gets expensive** | Interactive All-Purpose clusters left running; DBU + VM cost both scale with cluster size | Oversized warehouses; unmanaged automatic clustering; multi-cluster left always-on | Full-table scans (`SELECT *`), no partitioning/clustering, ignoring the 467 TiB/month on-demand-vs-capacity break-even | Underutilized reserved nodes; RA3 storage growth outpacing compute needs |
| **Governance** | Unity Catalog: 3-level namespace, auto lineage, row/column security, governs models+volumes | Native RBAC + tag-based masking; less unified across non-warehouse assets (no native ML/model governance layer) | IAM + BigQuery-native column/row-level security; Dataplex for cross-product governance | IAM + Lake Formation (when paired with a lake), less unified if Redshift is used standalone |
| **ML/AI story** | Strongest: MLflow, GPU clusters, Mosaic AI, native to the platform's DNA | Snowpark ML, Cortex (managed LLM functions) — real but narrower than a full ML platform | BigQuery ML (SQL-native models) + deep Vertex AI integration | Redshift ML (SageMaker under the hood) — thinnest of the four |
| **Ecosystem/multi-cloud** | Available on AWS/Azure/GCP; genuinely multi-cloud | Available on AWS/Azure/GCP; genuinely multi-cloud | GCP-only (by design — it's a GCP product) | AWS-only (by design) |
| **Operational burden** | Highest — cluster policies, pool sizing, compute-type selection all matter | Lowest on compute (auto-suspend/scale), but warehouse topology still needs design | Lowest overall — no cluster sizing decision exists on-demand | Moderate — RA3 sizing and WLM (or Serverless RPU) still require tuning |

---

## Build it from scratch

There's no code to "build" a warehouse platform from scratch here — the useful artifact is a **decision script** you can actually walk an interviewer through:

```python
# untested sketch — a defensible first-pass decision heuristic, not a scoring formula to over-trust
def recommend_platform(workload):
    if workload.cloud_committed == "aws" and workload.wants_deep_native_integration:
        if workload.is_lakehouse_first:
            return "Databricks (on AWS) — or Redshift if pure BI and AWS lock-in is acceptable"
        return "Redshift, if BI-heavy and already deep in the AWS data ecosystem"
    if workload.ml_or_streaming_heavy and workload.team_owns_spark_expertise:
        return "Databricks"
    if workload.is_spiky_adhoc and workload.wants_zero_capacity_planning:
        return "BigQuery"
    if workload.is_bi_heavy and workload.wants_minimal_tuning and workload.high_concurrency:
        return "Snowflake"
    return "Run a bake-off on your actual top 5 production queries/pipelines — the matrix above is a filter, not an answer"
```

The point of writing this in an interview isn't the code — it's demonstrating you'd anchor the decision to actual workload characteristics rather than brand preference.

---

## How it's done in production: real cost anchors

Rough, source-cited figures as of 2026 — expect these to move, and say so if asked:

- **Databricks**: DBU rates range **$0.08 to $0.70/DBU** depending on compute type and tier, plus the underlying cloud VM cost billed separately [[Databricks pricing guide 2026]](https://www.flexera.com/blog/finops/databricks-pricing-guide/).
- **Snowflake**: credits cost roughly **$2/credit (Standard) to $4/credit (Business Critical)** on AWS US East on-demand, with warehouse sizes consuming 1 to 512 credits/hour depending on size [[2026 Snowflake Pricing Guide]](https://www.revefi.com/blog/snowflake-pricing-guide).
- **BigQuery**: on-demand is **$6.25/TiB scanned** (first 1 TiB/month free); capacity pricing is **$0.04/slot-hour (Standard) to $0.06/slot-hour (Enterprise)**, with the on-demand/capacity break-even around **467 TiB scanned/month** [[BigQuery pricing]](https://cloud.google.com/bigquery/pricing).
- **Redshift**: an RA3.xlplus node runs about **$1.086/hour on-demand** (~$782/month), with managed storage billed separately at roughly **$24.58/TB-month**; Redshift Serverless charges **$0.375/RPU-hour** with an 8-RPU minimum base [[Snowflake vs BigQuery vs Redshift 2026]](https://reintech.io/blog/snowflake-vs-bigquery-vs-redshift-2026-comparison).

For a mid-size team, reported all-in comparisons put Snowflake around **$36K/year** and Databricks around **$28K/year** for a similar workload profile, though this flips depending on whether the workload is ETL-heavy (Databricks tends 15-30% cheaper) or pure-BI (Snowflake tends 20-40% *more expensive but faster with less tuning*) [[Databricks vs Snowflake 2026 comparison]](https://tech-insider.org/snowflake-vs-databricks-2026/). Treat any single "$X vs $Y" headline number as workload-specific, not a general truth — the delta between "ETL-heavy" and "BI-heavy" for the *same* company can flip which platform is cheaper.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Databricks bill triples with no new workloads | Interactive All-Purpose clusters left running for what should be scheduled jobs | Move to Jobs Compute; enforce cluster policies |
| Snowflake bill triples with no new workloads | Warehouse oversized, or auto-suspend regressed to a high default | Right-size via query profile; audit auto-suspend settings account-wide |
| BigQuery monthly cost unpredictable and spiky | On-demand pricing with unpartitioned/unclustered tables and `SELECT *` habits | Enforce partitioning/clustering on large tables; consider capacity pricing if consistently >~467 TiB/month scanned |
| Redshift cluster underutilized most of the day | Fixed-size RA3 cluster sized for peak, idle off-peak | Migrate to Redshift Serverless, or schedule pause/resume for predictable low-usage windows |
| "We migrated to platform X and it's not actually cheaper" | Workload profile doesn't match the platform's strength (e.g., BI-heavy team picked Databricks for its ML story) | Re-run the workload-shape analysis, not just a headline price comparison |

---

## Tradeoffs & when NOT to use it — plainly, per platform

- **Databricks is usually the wrong choice** for a pure BI/SQL shop with no ML, no streaming, and no need for Spark-scale processing — you pay for and operationally own a platform built for a workload you don't have. It's also the wrong choice for a small team without dedicated platform engineering; cluster policy and compute-type discipline require real ongoing attention.
- **Snowflake is usually the wrong choice** for heavy ML/feature-engineering pipelines or large-scale unstructured data processing — Snowpark narrows the gap but doesn't replace a real ML platform. It's also a poor fit if your workload is a single small, predictable job that doesn't need elastic multi-cluster concurrency — you're paying for flexibility you don't use.
- **BigQuery is usually the wrong choice** if you need fine-grained control over compute isolation between workloads on-demand pricing (noisy-neighbor risk on shared on-demand slots is real at scale, mitigated only by moving to capacity/reservations), or if you're not on GCP and don't want to be — it is a GCP product first.
- **Redshift is usually the wrong choice** outside a deep AWS commitment — its ML story is the thinnest of the four, and RA3's node-based pricing still requires more capacity-planning judgment than BigQuery's serverless model or Snowflake's warehouse elasticity, even with Serverless available.
- **A "we chose the market leader" decision with no workload analysis is the actual anti-pattern** across all four — the honest answer to "which is best" is "for which workload," and an interviewer who hears a platform recommended with no workload qualifier should treat that as underdeveloped judgment, not confidence.

### Pick X if

- **Pick Databricks if**: ML/AI is a first-class workload, you're doing meaningful stream processing, your team already has Spark expertise, or you need one platform spanning raw data engineering through model serving.
- **Pick Snowflake if**: the workload is predominantly BI/SQL with high concurrency across many teams, you want the least possible infrastructure tuning, and elastic warehouse isolation between workloads (ETL vs BI vs ad-hoc) matters more than raw cost minimization.
- **Pick BigQuery if**: usage is spiky/unpredictable and you don't want to size anything, ever; you're already on GCP; and you can enforce partitioning/clustering discipline to keep on-demand costs sane.
- **Pick Redshift if**: you're deeply embedded in AWS (Glue, Lake Formation, Kinesis, IAM) and want the tightest native integration, and your ML needs are minor enough that Redshift ML/SageMaker pass-through covers them.

---

## Interview questions

### Q1 — Snowflake or Databricks — which would you pick for a company doing 80% BI dashboards and 20% batch ETL?
**Testing:** whether you can apply the matrix instead of reciting brand loyalty.
**Answer:** Snowflake, primarily — the workload is BI-dominant, and Snowflake's near-zero-tuning warehouse elasticity and strong BI-tool concurrency handling matches that better than Databricks' Spark-native strengths, which the 20% ETL slice doesn't need enough of to outweigh the 80% BI fit. If the ETL portion were 50%+ or involved ML, the calculus shifts.
**Follow-up trap:** *"What if that 20% ETL is actually complex streaming with sub-second latency requirements?"* — that changes the answer meaningfully; Databricks' Structured Streaming maturity is a real differentiator Snowflake doesn't match as well, and at that point you'd weigh running two platforms (Snowflake for BI, Databricks for streaming ETL feeding it) against a single-platform compromise.

### Q2 — Is Databricks or Snowflake more "locked in" — the vendor pitch says neither, because both support open formats now. Do you buy that?
**Answer:** Partially. The storage format itself (Delta with UniForm, or Snowflake's native format alongside Iceberg support) is decreasingly the lock-in point for either. The real lock-in has moved to the **catalog**: Unity Catalog historically was Databricks-only (now open-sourcing its core and adding Iceberg REST server support), and Snowflake's Iceberg-table feature set doesn't yet have full parity with native-table features like clustering and Time Travel. So "not locked in on format, still somewhat locked in on catalog and on native-table-only features" is the accurate 2026 position, not "no lock-in."
**Follow-up trap:** *"So which one is less locked in today?"* — this is a fast-moving target; the honest answer is to check current docs at decision time rather than assert a permanent ranking, and to say so explicitly in the interview — asserting a fixed winner here is itself a small red flag given how quickly both have moved.

### Q3 — BigQuery's on-demand pricing model: what's the actual failure mode that makes teams migrate to capacity/reservations?
**Answer:** On-demand bills per byte scanned with no cap; a team with unpartitioned tables and `SELECT *` habits can see unpredictable, spiky bills, and one bad query (say, an accidental full scan of a 10TB table) can cost tens of dollars in seconds with no guardrail. The break-even against capacity pricing is roughly 467 TiB scanned/month — below that, on-demand is usually cheaper; above it, reservations give predictable cost and let Enterprise-tier customers share idle slot capacity across workloads.
**Follow-up trap:** *"Does moving to capacity pricing fix the `SELECT *` problem?"* — no, it just caps and smooths the cost; it doesn't fix wasted compute from full scans. Partitioning/clustering discipline is still required either way — capacity pricing changes the billing shape, not the underlying inefficiency.

### Q4 — A hiring manager says "we're moving off Redshift because it's legacy." Push back or agree?
**Answer:** Push back on "legacy" as a blanket claim — RA3 with managed storage and Redshift Serverless have closed much of the historical gap versus Snowflake/BigQuery on elasticity, and if the team is deeply embedded in AWS (Glue, Lake Formation, IAM, Kinesis), the integration cost of moving off Redshift is real and often underweighted in migration proposals. The legitimate reasons to move are usually about ML maturity (Redshift's is the thinnest of the four) or wanting multi-cloud flexibility, not raw architecture staleness.
**Follow-up trap:** *"What would make you agree it actually is time to move?"* — if the workload has grown a real ML/AI component Redshift can't serve natively, or if multi-cloud optionality has become a genuine business requirement (AWS-only is a real constraint, not a bug, but it is a constraint), those are legitimate triggers — distinguishing "legitimate driver" from "vague legacy label" is the actual signal being tested.

### Q5 — Design a system where a company keeps data in Iceberg on S3 and wants to query it from both Databricks and Snowflake without duplicating storage. Is that realistic in 2026?
**Answer:** Largely yes for reads via the REST Catalog protocol both now implement server-side (Unity Catalog, Snowflake's Open Catalog/Polaris), so both platforms can discover and read the same Iceberg tables through a shared catalog without copying data. The caveat: write patterns, performance-critical features (fine-grained clustering, Time Travel depth), and governance semantics don't yet have full cross-platform parity — a table written by one engine and read by the other works, but you should verify current docs before promising indistinguishable performance across both.
**Follow-up trap:** *"Does that mean you'd never need a native table in either platform again?"* — no; native tables in both still offer real performance and feature advantages current Iceberg support doesn't fully match. The realistic architecture is "shared Iceberg tables for interoperable/bronze-layer data, native tables where a specific platform's performance features are worth the lock-in trade."

### Q6 — Cost model comparison: why can the "same workload" be cheaper on Databricks for one company and cheaper on Snowflake for another?
**Answer:** Because the pricing models charge for fundamentally different things — Databricks' DBU model plus separate VM cost scales with compute-type choice and cluster discipline, rewarding teams that move workloads to Jobs Compute and size clusters tightly; Snowflake's credit model scales with warehouse size and auto-suspend discipline, rewarding teams that right-size warehouses and avoid idle burn. A team with strong platform-engineering discipline on one model will look artificially cheap on that platform compared to a team with weak discipline on the other, independent of the "true" cost of the workload itself.
**Follow-up trap:** *"So cost comparisons between the two are meaningless?"* — not meaningless, but they're comparisons of *operational discipline applied to a pricing model*, not pure architecture comparisons — which is exactly why vendor-published head-to-head cost benchmarks should be read skeptically, including the ones cited in this module.

### Q7 — When would you run two of these platforms simultaneously rather than picking one?
**Answer:** When workload segments genuinely don't share a good single-platform fit — e.g., Databricks for ML training/feature pipelines feeding a Snowflake warehouse that serves BI, with Iceberg or Delta UniForm as the interoperable handoff layer. This is increasingly common and not automatically an anti-pattern, but it does add real operational cost: two governance models to reconcile, two cost centers to monitor, and a data-movement or catalog-sharing layer that itself needs engineering investment.
**Follow-up trap:** *"Isn't running two platforms always more expensive than picking one and living with its weaknesses?"* — not always; if the weaker fit's inefficiency (e.g., forcing ML workloads through Snowflake, or forcing high-concurrency BI through Databricks) would cost more in wasted compute and tuning effort than the integration overhead of running two platforms, the two-platform answer can be the more defensible one. The senior signal is running that comparison explicitly rather than defaulting to "always consolidate."

### Q8 — Your CFO wants a single number: "which platform is cheapest?" How do you respond?
**Testing:** whether you'll cave to a bad question or reframe it honestly.
**Answer:** There isn't a single honest number — cost depends on workload shape (ETL-heavy vs BI-heavy flips which platform wins by the cited comparisons), operational discipline applied to each pricing model, and which lock-in costs you're willing to accept. The responsible answer is a workload-weighted TCO model built from your actual top queries/pipelines run as a bake-off, not a headline comparison pulled from a blog post.
**Follow-up trap:** *"That's not a number, that's a process. Give me your best guess anyway."* — give a range anchored to your actual dominant workload type using the cited cost anchors (e.g., "if we're 80% BI, expect Snowflake in the ballpark of $Xk/month based on our current warehouse-hours estimate, with real uncertainty until we run the bake-off") rather than either refusing to answer or fabricating false precision.

### Q9 — What's the strongest argument *against* choosing based on this matrix at all?
**Testing:** self-aware, staff-level meta-judgment.
**Answer:** The matrix is a snapshot; these four platforms have been converging for two years and will keep converging, so a decision anchored purely to today's feature/cost differences risks looking stale within 12-18 months, especially as Iceberg/REST-catalog interoperability matures further. The more durable inputs are organizational (existing cloud commitment, existing team skills, existing data-platform investments) rather than point-in-time feature comparisons, because those don't get out of date as fast.
**Follow-up trap:** *"So why build the matrix at all?"* — because it's still the right tool for a first-pass filter and for communicating tradeoffs to stakeholders; the mistake is treating its current-state feature comparisons as permanent facts rather than a snapshot to be revisited before the actual decision is finalized.

### Q10 — Do the arithmetic: a workload scans 550 TiB/month on BigQuery with even, steady load. On-demand or capacity pricing, and what's the monthly delta?
**Testing:** whether you'll do the math or retreat to "it depends" when actually pressed for a number.
**Answer:** On-demand: 550 TiB × $6.25/TiB ≈ $3,438/month (ignoring the 1 TiB free tier, which is noise at this volume). Capacity at Enterprise's $0.06/slot-hour needs a slot count to compare directly, but the cited break-even (~467 TiB/month) is already below this workload's 550 TiB, so at steady, predictable load capacity/reservations should come out cheaper than on-demand here — the arithmetic, not intuition, is what justifies the reservation, and it only justifies it because the load is steady; the same 550 TiB compressed into a bursty 2-hour daily window would flip the answer toward autoscaling reservations or even on-demand, since a flat baseline reservation sized for peak would sit idle most of the day.
**Follow-up trap:** *"You picked capacity pricing. Does that number hold if usage grows 20% next quarter?"* — reservations are billed on committed slot-hours regardless of bytes scanned, so growing bytes-scanned within the same reservation's slot capacity costs nothing extra until you're compute-bound, not data-volume-bound — which is exactly the predictability capacity pricing is sold on. But if the *query complexity* (not just volume) grows enough to need more concurrent slots, the reservation itself needs resizing, and that's a capacity-planning decision on-demand pricing would have avoided entirely — trading one planning problem for a different one, not eliminating planning.

### Q11 — Your company needs to migrate off Snowflake in six months due to a cost or strategic decision. What's actually hard about it, beyond rewriting SQL?
**Testing:** whether "lock-in" is understood as a real migration cost or just a talking point raised without ever being priced out.
**Answer:** The SQL dialect differences (Snowflake-specific functions, `QUALIFY`, semi-structured `VARIANT` handling) are the visible, straightforward part and mostly mechanical. The hard part is everything built *around* the warehouse: clustering keys and query patterns tuned to Snowflake's micro-partition pruning that need re-tuning for a different engine's optimizer, zero-copy-clone-based dev/test workflows that don't have a free equivalent elsewhere, Snowpark transformation code that needs a full rewrite (not a port) if the destination isn't Python-DataFrame-native in the same way, Time Travel/Fail-safe-dependent operational recovery assumptions that need a new disaster-recovery design, and every downstream BI tool's connection, semantic layer, and cached-credential configuration. None of that shows up in a SQL-compatibility audit, and all of it is why "just rewrite the queries" estimates are reliably wrong.
**Follow-up trap:** *"So is switching to an Iceberg-native architecture the fix for future lock-in?"* — it reduces *storage-format* lock-in for the next migration, but it doesn't reduce most of what actually made this migration hard, since clustering behavior, warehouse-specific caching, and platform-specific operational tooling are engine-level concerns that persist regardless of which table format sits underneath. Confusing "our data format is now portable" with "our platform is now portable" is the mistake this question is designed to catch.

### Q12 — Design the actual evaluation you'd run before committing to one of these four platforms for a new workload. What do you benchmark, on what data, and what result would change your recommendation?
**Testing:** staff-level judgment — whether you'd run a real bake-off or just cite the matrix and call it done.
**Answer:** Pull the top 10-20 queries/pipelines by expected frequency and cost from the actual target workload, not a synthetic benchmark like TPC-DS, since vendor-optimized benchmark results notoriously don't transfer to a specific company's schema and query patterns. Run those on a representative data volume (a real production-scale sample, not a toy dataset that fits in cache on every platform and hides the differences that only show up at scale) against at least the two most plausible candidates from the matrix, measuring wall-clock latency, cost per run under each platform's actual pricing model, and operational effort (how much manual tuning — clustering keys, partition schemes, warehouse sizing — was needed to hit that latency/cost). Explicitly time-box the eval and pre-register what result would flip the decision, so the exercise can't quietly become "confirm what we already picked."
**Follow-up trap:** *"Your bake-off shows Platform A is 15% cheaper but Platform B needed zero tuning to get there while A needed two weeks of clustering-key iteration. Which do you recommend?"* — this is exactly the trap staff-level candidates should name explicitly: a raw cost/latency number that excludes the ongoing tuning burden and the cost of the team's time understates Platform A's true total cost, especially if that tuning effort recurs every time query patterns shift. The correct answer is to fold operational effort into the TCO comparison rather than treating a clean benchmark number as the final word, and to say which one you'd pick only after doing that folding explicitly.

---

## Red flags that fail you

- Recommending one platform as universally superior with no workload qualifier.
- Claiming either Databricks or Snowflake has "zero lock-in" because storage formats are open (the catalog is the real 2026 lock-in point).
- Citing a single cost comparison number as though it generalizes across workload types.
- Not knowing BigQuery and Redshift exist as real alternatives, or dismissing either without a stated reason.
- Treating this comparison as settled/permanent rather than acknowledging active convergence.
- Recommending running two platforms without acknowledging the real governance/ops overhead that adds.

---

## Cheat card

```
WORKLOAD FIT      Databricks: ETL/ML/streaming-heavy, Spark-native
                   Snowflake:  BI/SQL-heavy, high concurrency, low tuning
                   BigQuery:   spiky/ad-hoc, zero capacity planning (GCP-only)
                   Redshift:   AWS-native mixed BI/ELT (AWS-only)

LOCK-IN (2026)     storage format increasingly open on all four (Delta/Iceberg convergence)
                   CATALOG is the real lock-in point now: Unity Catalog, Polaris/Open Catalog,
                   Glue, BigLake — check current REST-catalog interop before assuming portability

PRICE ANCHORS      Databricks: $0.08-$0.70/DBU + separate cloud VM cost
                   Snowflake:  $2-4/credit, warehouse doubles credits/hr per size tier
                   BigQuery:   $6.25/TiB on-demand (1 TiB free/mo) | $0.04-0.06/slot-hr capacity
                               break-even ≈ 467 TiB scanned/month
                   Redshift:   RA3 ~$1.086/node-hr + ~$24.58/TB-mo managed storage
                               Serverless: $0.375/RPU-hr, 8 RPU minimum

ML STORY           Databricks (strongest) > BigQuery (BQML+Vertex) > Snowflake (Snowpark/Cortex)
                   > Redshift (thinnest, SageMaker pass-through)

WRONG CHOICE IF    Databricks: pure BI/SQL shop, no ML/streaming, no platform team
                   Snowflake:  heavy ML/unstructured pipelines, or tiny predictable single job
                   BigQuery:   need hard compute isolation on-demand, or not on GCP
                   Redshift:   not on AWS, or ML is a real requirement

PICK X IF          ML/AI first-class + Spark skills      → Databricks
                   BI-heavy, high concurrency, low ops   → Snowflake
                   Spiky/unpredictable, zero sizing       → BigQuery
                   Deep AWS commitment, BI/ELT             → Redshift

SHELF LIFE         all four converging fast — treat any fixed ranking as time-boxed,
                   re-verify feature/pricing claims before a real decision
```

## Sources

- [Databricks pricing guide 2026 — Flexera](https://www.flexera.com/blog/finops/databricks-pricing-guide/) — accessed 2026-08-01
- [2026 Snowflake Pricing Guide — Revefi](https://www.revefi.com/blog/snowflake-pricing-guide) — accessed 2026-08-01
- [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing) — accessed 2026-08-01
- [Snowflake vs BigQuery vs Redshift 2026 — Reintech](https://reintech.io/blog/snowflake-vs-bigquery-vs-redshift-2026-comparison) — accessed 2026-08-01
- [Databricks vs. Snowflake: Complete Platform Comparison (2026) — Dataforest](https://dataforest.ai/blog/databricks-vs-snowflake) — accessed 2026-08-01
- [Snowflake vs Databricks: $36K vs $28K/Year [2026] — Tech Insider](https://tech-insider.org/snowflake-vs-databricks-2026/) — accessed 2026-08-01
- [The State of Apache Iceberg Catalogs in June 2026 — dev.to](https://dev.to/alexmercedcoder/the-state-of-apache-iceberg-catalogs-in-june-2026-265e) — accessed 2026-08-01
- [Top Amazon Redshift alternatives for 2026 — MotherDuck](https://motherduck.com/learn/top-amazon-redshift-alternatives/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Databricks wins ML/streaming/Spark-native workloads and open-lakehouse flexibility; Snowflake wins BI-heavy, high-concurrency SQL with the least tuning; BigQuery wins spiky, unpredictable ad-hoc load with zero capacity planning but locks you to GCP; Redshift wins deep AWS-native integration but has the thinnest ML story of the four. The storage-format lock-in argument is mostly over — all four are converging on Iceberg and REST catalogs — but the catalog itself, and each platform's native-table-only performance features, are the real 2026 lock-in point. Cost comparisons between them are really comparisons of operational discipline applied to very different pricing models (DBU-plus-VM, credits-per-warehouse-hour, bytes-scanned-or-slots, node-or-RPU-hours), so a single "X is cheaper" headline is workload-specific, not a general truth. Pick based on dominant workload shape and existing cloud/team investment, not brand loyalty, and expect this whole comparison to need revisiting within a year.
