# Cloud Logging, Monitoring, Trace, and FinOps

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** `C-GCP-iam`, `C-GCP-compute` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-ops` · **Tags:** observability, finops, critical

## The 30-second version

Cloud Logging bills **$0.50/GiB ingested** (50 GiB/month free) with the first **30 days of storage included in that charge** — extended retention beyond 30 days is a separate, much cheaper **$0.01/GiB-month**. The lever that actually controls the bill is the **Log Router**: every log entry passes through inclusion/exclusion filters before landing in a bucket, and an **exclusion filter drops a log from ingestion billing entirely** — even if the same log is simultaneously exported via a sink to Pub/Sub, GCS, or BigQuery, where you pay that destination's (usually far lower) rate instead. This is the single most-tested cost-control mechanic: route high-volume, low-value logs (health checks, verbose debug) out of the `_Default` bucket via exclusion + sink rather than paying $0.50/GiB to ingest noise nobody queries. **Cloud Trace** is nearly free at normal scale (2.5M spans/month free, $0.20/million beyond) but head-based sampling at 5-10% is still standard practice, cutting cost ~90% with negligible operational loss for anything not actively debugging a specific incident. **Cloud Monitoring's SLO framework** is built around **error budgets** and **burn-rate alerts** — alerting on "X% of budget consumed in the last 60 minutes exceeds threshold" rather than on raw latency/error-rate crossing a static line, which is the mental shift from AWS CloudWatch's default alarm-on-metric-threshold pattern. **Cloud Audit Logs** has four types — Admin Activity (free, always on, can't disable), System Event (free, Google-initiated actions), Data Access (chargeable, off by default except for a few services), Policy Denied (chargeable, on by default) — and only Admin Activity + System Event get free 400-day retention in the `_Required` bucket. FinOps on GCP centers on **Committed Use Discounts** (resource-based: 37% off 1-year, 55% off 3-year, no-upfront-only, now shareable at the billing-account level by default) stacked with **automatic Sustained Use Discounts** (up to 30%, zero commitment, N1/N2/N2D/C2/M1/M2 only — E2, C3, C4, N4, and accelerator families are excluded) — the automatic-discount-with-no-commitment layer is a real structural difference from AWS, which has no equivalent to SUDs at all.

## Why this gets asked

The interviewer has watched a logging bill balloon after someone enabled Data Access audit logs on a chatty BigQuery workload without an exclusion filter, and separately has watched an SLO-based alerting rollout fail because the team copy-pasted a CloudWatch-style static-threshold alarm instead of a burn-rate policy, causing either alert fatigue (too sensitive) or missed incidents (too permissive) because a static threshold doesn't account for how much error budget is actually left. On the FinOps side, they've had to explain to a director why the CUD recommender's suggestion turned into a stranded commitment after a workload shrank. They want to know whether you understand these systems' actual cost and alerting mechanics, not whether you can name the product logos.

---

## Lineage: past → present → future

**What came before.** Google's operations suite traces back to **Stackdriver**, acquired in 2014 and rebranded into "Google Cloud's operations suite" (2020) then split into standalone **Cloud Logging**, **Cloud Monitoring**, and **Cloud Trace** products — the pain the original Stackdriver era solved was the same one every cloud faced early on: logs, metrics, and traces lived in separate silos with no shared resource-labeling model, making cross-signal correlation (this trace's slow span corresponds to this log error corresponds to this metric spike) manual and slow. AWS's parallel evolution ran through CloudWatch (metrics/logs, 2009-era) and X-Ray (tracing, 2016) as separately billed, separately configured products that still don't share a unified query surface the way GCP's operations suite increasingly does. SLO-based reliability engineering itself traces to Google's own internal SRE practice, formalized in the 2016 *Site Reliability Engineering* book — the error-budget concept (a service gets a budget for how much it's allowed to fail before violating its SLO, and burns that budget at some rate) predates Cloud Monitoring's SLO feature by years as internal Google practice before becoming a public product surface.

**Where it stands now.** Cloud Logging's pricing model (ingestion-based, $0.50/GiB, 50GiB free) has stayed structurally stable, with the Log Router's inclusion/exclusion filter mechanism as the primary cost lever exposed to customers — the live practitioner consensus is that a well-tuned exclusion-filter-plus-sink strategy is not optional at any real production log volume, it's baseline hygiene. [How To Reduce Logging Costs in GCP — Finout](https://www.finout.io/blog/reducing-gcp-logging-costs) — accessed 2026-08-08. Cloud Trace's pricing (2.5M free spans/month, $0.20/million beyond) makes it nearly free for most workloads, so the live disagreement there isn't cost, it's sampling strategy — head-based (sample at ingestion, cheap, simple) versus tail-based (sample after seeing the full trace, catches errors/slow requests you'd otherwise miss, more complex, usually done via an OpenTelemetry Collector rather than natively in Cloud Trace). [OpenTelemetry vs Google Cloud Trace — OneUptime](https://oneuptime.com/blog/post/2026-02-06-compare-opentelemetry-vs-google-cloud-trace/view) — accessed 2026-08-08. On FinOps, GCP's 2026 CUD update changed the **default scope from project to billing-account** for most new and many existing billing accounts, meaning a single commitment now automatically covers eligible usage across projects rather than requiring per-project commitments — a real structural simplification that removes a common source of stranded/underutilized commitments. [Introducing CUD recommendations — Google Cloud Blog](https://cloud.google.com/blog/products/management-tools/introducing-committed-use-discount-recommendations) — accessed 2026-08-08. A single Flex CUD commitment can now also cover an entire eligible compute footprint (VMs, containers, serverless) without separate per-service commitments. [GCP FinOps Tools 2026 — nOps](https://www.nops.io/blog/gcp-finops-tools/) — accessed 2026-08-08.

**Where it's heading.** Moderate-to-high confidence: GCP's operations suite continues converging with OpenTelemetry as the standard instrumentation layer rather than pushing proprietary SDKs — the current recommended pattern (OTel SDK + OTel Collector + Cloud Trace/Logging exporter) is explicitly the one Google's own docs and third-party guides converge on, reducing lock-in on the instrumentation side even as the backend remains GCP-specific. Moderate confidence: FinOps tooling (the Recommender, billing-account-scoped CUDs) keeps trending toward more automatic, less manually-managed commitment optimization, mirroring the industry-wide FinOps-as-continuous-practice (not a quarterly review) movement. Speculative: whether SLO-based alerting (burn-rate policies) becomes the default recommended pattern over static-threshold alerting industry-wide, or remains a more sophisticated practice adopted mainly by teams with mature SRE functions — worth a fresh check near interview time, since adoption of burn-rate alerting specifically (versus just having SLO dashboards) still varies a lot team to team.

---

## Mental model

```
LOG ROUTER: THE COST-CONTROL CHOKE POINT

  Log entry generated
        |
        v
  LOG ROUTER evaluates INCLUSION + EXCLUSION filters
        |
        +--- matches EXCLUSION filter --> DROPPED, not ingested,
        |                                  NOT BILLED (even if a sink
        |                                  also exports it elsewhere --
        |                                  you pay the DESTINATION's
        |                                  rate instead, not Logging's
        |                                  $0.50/GiB)
        |
        +--- no exclusion match --> routed to destination bucket
                                      (_Default, _Required, or custom)
                                      BILLED at $0.50/GiB ingestion,
                                      30 days storage included

  _REQUIRED bucket: Admin Activity + System Event audit logs.
    Free ingestion, free 400-day retention, CANNOT be excluded/disabled.
  _DEFAULT bucket: everything else routed here unless excluded/redirected.
    Chargeable, 30-day default retention.

SLO / ERROR BUDGET MENTAL MODEL:
  SLO = 99.9% availability over 30 days
    -> Error budget = 0.1% of requests allowed to fail = 43.2 min/month
  BURN RATE = how fast you're consuming that budget right now
    burn rate 1x  = exactly on pace to exhaust budget at period end (OK)
    burn rate 10x = exhausting a month's budget in ~3 days -- ALERT NOW
  Static-threshold alert: "error rate > 5%" -- fires the same whether
    you have 99% of your budget left or 2% left. Ignores budget state.
  Burn-rate alert: "consuming budget X times faster than sustainable"
    -- fires based on REMAINING BUDGET TRAJECTORY, the actually useful
    signal for "will we breach the SLO if this continues."

CUD vs SUD, STACKED (not either/or):
  SUD: automatic, $0 commitment, up to 30% off, ONLY N1/N2/N2D/C2/M1/M2,
       kicks in once a VM runs >25% of the billing month
  CUD: you commit vCPU+memory in a region for 1yr (37% off) or 3yr
       (55% off), no-upfront-only, now billing-account-scoped by default
  Both can apply to the same eligible instance simultaneously --
  SUD as the free floor, CUD stacked on top for committed workloads.
```

---

## How it actually works

### Cloud Logging: the Log Router and cost mechanics

Ingestion is billed at **$0.50/GiB** with **50 GiB/month free** per project, and that $0.50/GiB charge already includes **30 days of storage** in the destination bucket — extending retention beyond 30 days costs an additional **$0.01/GiB-month** on top. [GCP Cloud Logging Pricing — Finout](https://www.finout.io/blog/gcp-cloud-logging-pricing) — accessed 2026-08-08. The **Log Router** is the mechanism every log entry passes through: it evaluates **inclusion filters** (which sinks receive a copy) and **exclusion filters** (which entries never get ingested/billed at all) before an entry lands anywhere. Critically, an excluded log can still be routed to an external destination (a **sink** targeting Pub/Sub, a GCS bucket, or a BigQuery dataset) — the export itself is free at the Logging layer, you just pay whatever that destination normally charges (GCS storage rates, BigQuery ingestion, etc.), which is typically far cheaper than $0.50/GiB for high-volume, rarely-queried log types. [How To Reduce Logging Costs in GCP — Finout](https://www.finout.io/blog/reducing-gcp-logging-costs) — accessed 2026-08-08. The practical pattern: identify high-volume, low-diagnostic-value log types (load balancer health-check noise, verbose framework debug logs), add an exclusion filter on the `_Default` sink for them, and if they're needed for compliance/audit purposes, add a separate sink exporting them to GCS/BigQuery instead.

Cloud Audit Logs ships **four log types**, and this is a frequently-tested distinction: **Admin Activity** (API calls that modify configuration/metadata — free, enabled by default, cannot be disabled), **System Event** (Google-initiated administrative actions on your resources, not triggered by a user — also part of the free `_Required` bucket), **Data Access** (read/write operations on data itself — e.g., BigQuery query execution, GCS object reads — **chargeable**, off by default for most services except a few like BigQuery), and **Policy Denied** (an access attempt blocked by a security policy — chargeable for storage, generated by default). [Cloud Audit Logs overview — Google Cloud Docs](https://docs.cloud.google.com/logging/docs/audit) — accessed 2026-08-08. Only Admin Activity and System Event get the free, fixed **400-day retention** in the `_Required` bucket; Data Access and Policy Denied logs, if enabled, land in the regular chargeable buckets subject to normal retention pricing.

```yaml
# untested sketch -- exclusion filter dropping noisy health-check logs
# from ingestion billing, paired with a sink exporting a genuinely
# useful subset to BigQuery for occasional compliance querying
# (gcloud logging sinks create / gcloud logging sinks update syntax)

# 1. Exclude health-check noise from the _Default bucket entirely:
#    gcloud logging sinks update _Default \
#      --add-exclusion=name=drop-healthchecks,filter='resource.type="gce_instance" AND jsonPayload.path="/healthz"'

# 2. Still capture Data Access logs for a specific BigQuery dataset,
#    routed to BigQuery itself instead of the (chargeable) _Default bucket:
#    gcloud logging sinks create audit-export \
#      bigquery.googleapis.com/projects/my-proj/datasets/audit_logs \
#      --log-filter='logName:"logs/cloudaudit.googleapis.com%2Fdata_access"'
```

### Cloud Monitoring: SLOs, error budgets, and burn-rate alerting

An SLO in Cloud Monitoring is defined against one or more **SLIs** (service-level indicators — e.g., the fraction of requests completing under 300ms) over a **compliance period** (commonly 28 or 30 days rolling). The **error budget** is simply `1 - SLO target` applied to that period's total request volume or time — a 99.9% availability SLO over 30 days yields roughly **43.2 minutes** of allowed downtime for the period. A **burn-rate alert** fires based on how fast that budget is being consumed relative to a sustainable pace, using a **lookback window** (commonly defaulting to 60 minutes as a starting point) — the alert condition is "X% of the total budget consumed within the lookback period," not a raw error-rate threshold. [Alerting on budget burn rate — Google Cloud Docs](https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/alerting-on-budget-burn-rate) — accessed 2026-08-08. This is the mechanical reason burn-rate alerts avoid two failure modes static thresholds hit: **alert fatigue** from a static threshold firing during normal, budget-cheap noise, and **missed slow-burn incidents** where the error rate never spikes dramatically but steadily consumes the whole month's budget by day 20. A tiered burn-rate policy is common practice: a fast/high-multiplier burn rate (e.g., 10x, consuming a month's budget in ~3 days) pages immediately; a slow burn (e.g., 2x) creates a ticket rather than paging, since it's a real problem but not an immediate one. Error-budget policies also gate releases in mature setups — a defined automated check before each deploy (auto-approve, require approval, or block based on remaining budget) ties SLO health directly into the release process, not just alerting. [Error Budget Policies for Release Gating — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-establish-error-budget-policies-for-release-gating-on-google-cloud/view) — accessed 2026-08-08.

### Cloud Trace: sampling economics

Pricing: **2.5 million spans/month free**, **$0.20 per million spans** beyond that — at typical application scale this is close to negligible compared to Logging or compute spend, so sampling decisions are driven by signal-to-noise and downstream processing cost (trace storage/query, not raw ingestion cost) rather than the Trace API bill itself. [Cloud Trace pricing — MonitoringCost](https://monitoringcost.com/apm-pricing-comparison) — accessed 2026-08-08. **Head-based sampling** (a decision made per-request at the start, before knowing the outcome, typically at a fixed rate like 5-10%) is simple and standard practice, reported to cut trace volume roughly 90% with negligible operational loss for steady-state monitoring. **Tail-based sampling** (deferring the keep/drop decision until the full trace is seen, so error traces and slow-outlier traces can be kept at a much higher rate than routine fast successful ones) requires an intermediary — the recommended pattern is an **OpenTelemetry Collector** doing tail-based sampling before exporting to Cloud Trace, since Cloud Trace itself doesn't natively implement tail-based sampling logic. [Compare OpenTelemetry vs Google Cloud Trace — OneUptime](https://oneuptime.com/blog/post/2026-02-06-compare-opentelemetry-vs-google-cloud-trace/view) — accessed 2026-08-08.

### FinOps: Sustained Use, Committed Use, and the Recommender

**Sustained Use Discounts (SUDs)** are automatic and require zero commitment: a qualifying VM running more than 25% of the billing month earns up to **30% off**, scaling with usage within the month, but **only for N1, N2, N2D, C2, M1, and M2 machine families** — E2, C3, C4, N4, and all accelerator-optimized (GPU) families are explicitly **not eligible**. [Sustained use discounts — Google Cloud Docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts) — accessed 2026-08-08. This is a structural difference from AWS, which has no zero-commitment automatic discount equivalent — every AWS discount mechanism (Reserved Instances, Savings Plans) requires an explicit commitment. **Committed Use Discounts (CUDs)** require committing to a specific vCPU/memory quantity in a region for **1 year (37% off) or 3 years (55% off)**, **no-upfront-payment only** (unlike AWS RIs, which offer All-Upfront/Partial-Upfront for deeper discounts at the cost of cash flow). [GCP Committed Use Discounts vs AWS Savings Plans — atonementlicensing.com](https://atonementlicensing.com/blog/gcp-cud-vs-aws-savings-plan/) — accessed 2026-08-08. As of a 2026 update, the default CUD scope moved from **project to billing account** for most billing accounts, meaning one commitment automatically applies across projects instead of being stranded on a single project's usage — a direct fix for the classic "we committed based on Project A's usage, then Project A's workload shrank, and the commitment couldn't apply to Project B's growing usage" failure mode. [Introducing CUD recommendations — Google Cloud Blog](https://cloud.google.com/blog/products/management-tools/introducing-committed-use-discount-recommendations) — accessed 2026-08-08. The **Recommender** suggests CUD coverage based on recent usage patterns, but explicitly does not account for growth uncertainty or protect against usage dropping after commitment — it's described as a good free starting signal for teams early in FinOps maturity, not a substitute for ongoing, judgment-based commitment management. [Top GCP FinOps Tools 2026 — nOps](https://www.nops.io/blog/gcp-finops-tools/) — accessed 2026-08-08. **Cloud Billing Budgets** let you set spend thresholds at project/folder/billing-account/service granularity, triggering email or Pub/Sub notifications (enabling programmatic response, e.g., auto-disabling non-critical resources) when spend crosses a defined percentage.

### Cross-cloud observability cost comparison

AWS CloudWatch Logs ingestion is a flat **$0.50/GB** (matching Cloud Logging's rate almost exactly) with only **5 GB/month free** (versus Cloud Logging's 50 GiB free — a 10x difference in free tier). AWS X-Ray charges **$0.000005/trace** after a 100,000-trace/month free tier — a per-trace model rather than Cloud Trace's per-span model, and directly comparable cost scenarios show a small team's full CloudWatch stack (logs + X-Ray + Synthetics) landing around **$815/month**, with logs and traces alone accounting for over $750 of that. [Amazon CloudWatch Pricing 2026 — CloudBurn](https://cloudburn.io/blog/amazon-cloudwatch-pricing) — accessed 2026-08-08. The mechanical takeaway for a cost-modeling interview question: per-unit ingestion pricing looks similar across clouds, but GCP's larger free tier and the exclusion-filter cost-avoidance mechanism give more headroom before real spend starts, while AWS's smaller free tier means logging costs become material faster at the same log volume.

---

## Build it from scratch

Minimal illustration of an SLO definition and burn-rate alert policy, and a log exclusion filter, matching the shape of a from-scratch observability setup (no lab folder ships with this module):

```python
# untested sketch -- define an SLO and a fast-burn alert policy via the
# Cloud Monitoring API, illustrating the error-budget math directly
from google.cloud import monitoring_v3

client = monitoring_v3.ServiceMonitoringServiceClient()

slo = monitoring_v3.ServiceLevelObjective(
    display_name="API availability 99.9%",
    goal=0.999,
    rolling_period={"seconds": 30 * 24 * 60 * 60},  # 30-day compliance period
    service_level_indicator=monitoring_v3.ServiceLevelIndicator(
        request_based=monitoring_v3.RequestBasedSli(
            good_total_ratio=monitoring_v3.TimeSeriesRatio(
                good_service_filter='metric.type="serviceruntime.googleapis.com/api/request_count" AND metric.label.response_code_class="2xx"',
                total_service_filter='metric.type="serviceruntime.googleapis.com/api/request_count"',
            )
        )
    ),
)
# 99.9% over 30 days -> ~43.2 minutes of allowed downtime in the period.
# A burn-rate alert policy (created separately via AlertPolicy) watching
# "10% of budget consumed in the last 60 minutes" catches a fast burn
# that would exhaust the full 43.2-minute budget in about 10 hours if
# it continued unaddressed -- long before the 30-day period ends.
```

```bash
# untested sketch -- gcloud commands showing the exclusion + sink pattern
# Exclude a high-volume, low-value log pattern from ingestion billing:
gcloud logging sinks update _Default \
  --add-exclusion=name=drop-lb-healthchecks,filter='httpRequest.requestUrl:"/healthz"'

# Still retain it, cheaply, via export to GCS instead of paying
# $0.50/GiB Cloud Logging ingestion:
gcloud logging sinks create healthcheck-archive \
  storage.googleapis.com/my-healthcheck-log-archive \
  --log-filter='httpRequest.requestUrl:"/healthz"'
```

---

## How it's done in production

A typical GCP operations setup: **Cloud Logging** with an actively maintained exclusion-filter list on the `_Default` sink, reviewed periodically as new noisy log sources appear, with genuinely valuable-but-high-volume logs (audit trails, compliance-relevant Data Access logs) exported via dedicated sinks to BigQuery (for queryability) or GCS (for cheap cold storage) rather than left in the chargeable `_Default` bucket. **Cloud Monitoring** SLOs defined for every customer-facing service with tiered burn-rate alert policies (fast burn pages on-call, slow burn opens a ticket), and error-budget status wired into the release-gating process for services mature enough to automate that. **Cloud Trace** instrumented via OpenTelemetry SDKs across services, with an OTel Collector doing head-based sampling at 5-10% in steady state and the option to temporarily raise the sample rate (or rely on tail-based sampling for error/slow-outlier capture) during an active incident investigation. **FinOps**: Sustained Use Discounts apply automatically to any eligible steady-state N1/N2 family workloads at zero effort; Committed Use Discounts purchased at the billing-account level (post-2026 default scope) for baseline, predictable capacity, sized conservatively below historical minimum usage rather than to the Recommender's raw usage-pattern suggestion, specifically to avoid stranding a commitment if a workload shrinks; Cloud Billing Budgets with Pub/Sub-triggered alerts wired to a Cloud Function that can flag or throttle non-critical spend automatically past a threshold.

| Symptom | Cause | Fix |
|---|---|---|
| Cloud Logging bill spikes after enabling BigQuery Data Access audit logs | Data Access logs are chargeable and can be extremely high-volume for a query-heavy BigQuery workload, with no exclusion filter applied | Add an exclusion filter for routine, low-risk query patterns while keeping Data Access logging on for genuinely sensitive datasets; export what's needed to BigQuery/GCS instead of the chargeable `_Default` bucket |
| SLO burn-rate alert never fires despite a real ongoing incident | Alert policy's lookback window and burn-rate multiplier are tuned for fast-burn detection only, missing a slow, steady degradation | Add a second, slower-burn-rate policy with a longer lookback window and lower multiplier threshold (ticket-severity, not page-severity) to catch gradual budget consumption a fast-burn policy is blind to |
| Team gets paged constantly for an SLO alert that turns out to be low-severity | Static error-rate threshold alert (not a true burn-rate policy) fires on routine noise regardless of remaining error budget | Replace the static threshold with a proper burn-rate policy referencing the SLO's actual remaining budget, so alerts reflect whether the current error rate genuinely threatens the period's SLO, not just whether it crossed an arbitrary line |
| Committed Use Discount goes underutilized after a workload shrinks | Commitment sized to the Recommender's raw historical-usage suggestion, with no margin for demand variability, and pre-2026-scope-change stranded at the project level | Size commitments conservatively below historical minimum usage; take advantage of billing-account-level default scope so the commitment can apply across other projects' usage if one project's workload drops |
| Cloud Trace shows gaps around exactly the requests that errored | Head-based sampling at a fixed low rate randomly drops most requests including the interesting error cases, since the sampling decision is made before the outcome is known | Add tail-based sampling via an OpenTelemetry Collector so error and slow-outlier traces are kept at a much higher rate than routine successful ones, independent of the steady-state head-based sample rate |
| Sustained Use Discount doesn't show up on an E2 or C3 instance's bill | SUD eligibility is limited to N1/N2/N2D/C2/M1/M2 — E2, C3, C4, N4, and accelerator-optimized families are explicitly excluded | Confirm machine family eligibility before assuming SUD applies; for ineligible families, Committed Use Discounts are the available discount lever instead |

---

## Tradeoffs & when NOT to use it

- **Don't enable Data Access audit logs broadly "just in case" without exclusion filters.** They're chargeable and can dwarf every other Logging cost on a query-heavy service; scope them to genuinely sensitive datasets/operations and export what's needed for compliance to a cheaper destination.
- **Don't use static error-rate threshold alerts as a substitute for burn-rate SLO alerting on a service with a defined SLO.** A static threshold ignores how much error budget actually remains, producing both false urgency (budget-cheap noise) and missed slow burns — burn-rate policies are the correct primitive once an SLO exists, not an optional upgrade.
- **Don't leave Cloud Trace at 100% sampling in steady state "for completeness."** At typical production volume the cost difference is small in absolute dollars but the downstream trace-storage and query-latency cost compounds; 5-10% head-based sampling plus tail-based sampling for errors covers the practically useful signal.
- **Don't size Committed Use Discounts to the Recommender's raw usage-pattern suggestion without margin.** The Recommender doesn't model growth uncertainty or protect against usage drops — over-committing based on a recent usage spike strands spend the moment that spike normalizes.
- **Don't assume Sustained Use Discounts apply to every machine family.** E2 (the most commonly recommended cost-optimized general-purpose family for many workloads), C3, C4, N4, and all GPU/accelerator families get zero automatic SUD — that's a real, non-obvious gap that changes the actual effective cost of choosing E2 over N2 for a steady-state workload.
- **Don't build an SLO/error-budget release-gating process before the underlying SLOs are validated against real user impact.** An SLO set arbitrarily (rather than derived from what users actually tolerate) that then blocks releases produces friction without a corresponding reliability benefit — validate the SLO target itself before wiring it into deploy gates.

---

## Interview questions

### Q1 — Explain exactly how a Cloud Logging exclusion filter saves money, including what happens if the excluded log is also exported via a sink.
**Testing:** whether the candidate understands the mechanism precisely, not just that "exclusion filters reduce cost."
**Answer:** The Log Router evaluates exclusion filters before an entry is ingested into any Logging bucket; a match means the entry is never billed at Logging's $0.50/GiB ingestion rate. If a sink independently exports that same log to a different destination (Pub/Sub, GCS, BigQuery), that export is unaffected by the exclusion — the entry still reaches the destination, and you pay that destination's normal rate (GCS storage, BigQuery ingestion) instead of Cloud Logging's ingestion charge. The net effect: you can retain a log for compliance/audit purposes at a fraction of the cost by routing it around Cloud Logging's bucket storage entirely.
**Follow-up trap:** *"If exclusion filters are this effective, why not exclude everything and export it all to GCS?"* — GCS storage has no built-in structured querying, alerting, or log-based metrics the way a Logging bucket does — excluding a log you actually need to search/alert on in near-real-time trades a cost saving for losing Logging's native query and alerting capability on that data. The right call depends on whether the log needs interactive querying (keep in a Logging bucket) or just retention for occasional audit access (export and exclude).

### Q2 — Distinguish the four Cloud Audit Log types and state which are free and which are chargeable.
**Testing:** a specific, frequently-tested factual distinction with real cost implications.
**Answer:** Admin Activity (API calls modifying config/metadata) — free, always on, cannot be disabled. System Event (Google-initiated actions on your resources, not user-triggered) — free, part of the same `_Required` bucket as Admin Activity. Data Access (reads/writes on data itself, e.g. BigQuery queries, GCS object reads) — chargeable, off by default except for a handful of services. Policy Denied (an access attempt blocked by policy) — chargeable for storage, on by default. Only Admin Activity and System Event get the free, fixed 400-day retention in `_Required`; enabling Data Access broadly is the most common source of an unexpected audit-logging cost spike.
**Follow-up trap:** *"If Policy Denied logs are on by default and chargeable, isn't that itself a cost risk?"* — yes, at meaningful scale (e.g., a noisy IAM misconfiguration generating many denied-access attempts) Policy Denied logs can accumulate real volume — the mitigation is the same exclusion-filter pattern applied to Data Access, scoped to whichever resource/service is generating excessive denied-access noise, rather than assuming "on by default" means "safe to ignore for cost purposes."

### Q3 — Design a tiered burn-rate alerting policy for a service with a 99.9% availability SLO over 30 days, and explain why a single static threshold wouldn't work as well.
**Testing:** applied SRE alerting design, not just definitions.
**Answer:** Two tiers: a fast-burn policy (e.g., 10x burn rate over a 1-hour lookback, meaning the budget would be exhausted in about 3 days if sustained) pages on-call immediately, since that trajectory threatens the SLO within days. A slow-burn policy (e.g., 2x burn rate over a longer lookback, like 6 hours) creates a ticket rather than paging, catching gradual degradation that a 1-hour window would miss entirely because the hourly consumption rate looks unremarkable even though it's steadily draining the month's budget. A single static error-rate threshold (e.g., "alert if error rate > 1%") doesn't distinguish between "1% error rate with 95% of budget remaining" (not urgent) and "1% error rate with 5% of budget remaining, three days before period end" (urgent) — it has no concept of remaining budget at all.
**Follow-up trap:** *"Wouldn't more alert tiers (5 instead of 2) give even better signal?"* — more tiers add real operational complexity (more policies to tune, more thresholds that can each be mis-set) for diminishing signal improvement past 2-3 tiers — the standard SRE-book-derived pattern uses two or three multi-window, multi-burn-rate tiers specifically because that balances sensitivity against alert fatigue; more granularity is rarely worth the maintenance cost.

### Q4 — A team's Cloud Trace shows suspiciously few error traces despite a known elevated error rate in the logs. Diagnose.
**Testing:** understanding head-based versus tail-based sampling as a concrete failure mode.
**Answer:** The team is very likely using head-based sampling at a low fixed rate (e.g., 5-10%), where the sample/drop decision is made before the request's outcome (success or error) is known — this randomly drops most requests including a proportional share of the actual error cases, so the trace store ends up with a representative sample of *all* traffic but not a representative sample of *interesting* traffic. The fix is tail-based sampling (via an OpenTelemetry Collector), which defers the keep/drop decision until the full trace, including its outcome, is known, so errors and slow outliers can be retained at a much higher rate than routine successful requests.
**Follow-up trap:** *"Why not just set head-based sampling to 100% to guarantee no error traces are missed?"* — at any real production volume, 100% sampling multiplies both Trace ingestion cost and downstream storage/query cost roughly proportionally to traffic, for a benefit (catching every error trace) that tail-based sampling delivers far more cheaply by being selective about what it keeps — 100% head-based sampling is treating a targeting problem as a volume problem.

### Q5 — Explain the difference between GCP's Sustained Use Discounts and Committed Use Discounts, and why AWS has no direct equivalent to the former.
**Testing:** cross-cloud precision on discount mechanics, a frequent AWS-background trap.
**Answer:** SUDs are automatic, require zero commitment, and apply up to 30% off once a qualifying VM (N1/N2/N2D/C2/M1/M2 only) runs more than 25% of the billing month — you get the discount just by using the resource steadily, no purchase or commitment action required. CUDs require explicitly committing to a specific vCPU/memory quantity for 1 or 3 years (37%/55% off), no-upfront-only. AWS's discount mechanisms — Reserved Instances and Savings Plans — both require an explicit commitment; there's no AWS equivalent that grants an automatic discount purely from sustained usage with zero commitment, which is a genuine structural difference, not just a naming difference.
**Follow-up trap:** *"So is GCP compute automatically cheaper than AWS compute for any steady-state workload, given SUDs are free?"* — not necessarily; SUDs only apply to a specific subset of machine families (excluding E2, C3, C4, N4, and all accelerator families), and AWS's Savings Plans, once committed, can reach deeper discounts (up to ~66% on Compute Savings Plans) than GCP's uncommitted SUD ceiling of 30% — a fair cost comparison has to account for actual machine family choice and whether the workload is a good fit for a committed-discount model, not just "GCP gives a free discount, AWS doesn't."

### Q6 — Why did GCP change the default Committed Use Discount scope from project to billing account, and what production problem did that solve?
**Testing:** understanding the practical failure mode the change fixes, not just the fact of the change.
**Answer:** Under project-scoped CUDs, a commitment sized against one project's usage could become stranded (underutilized, still being paid for) if that project's workload shrank, even if another project in the same organization had growing usage that could have absorbed the committed capacity. Billing-account-scoped CUDs let one commitment apply automatically across any eligible usage in the billing account, so capacity shifts between projects no longer strand the commitment — a direct structural fix for the "we committed based on Project A, then Project A shrank" failure pattern.
**Follow-up trap:** *"Does billing-account scoping mean a team no longer needs to think carefully about commitment sizing?"* — no; it removes one specific failure mode (cross-project stranding) but doesn't protect against the org's *total* eligible usage shrinking, which the Recommender explicitly doesn't model either — sizing commitments conservatively below historical minimum usage is still necessary regardless of scope.

### Q7 — A candidate says "SLOs and uptime percentages are basically the same thing." Correct this.
**Testing:** precision about what an SLO actually formalizes versus a raw uptime number.
**Answer:** An uptime percentage alone is just a number; an SLO formalizes it against a specific, measurable SLI (e.g., fraction of requests under a latency threshold, or fraction returning non-5xx), a compliance period (e.g., rolling 30 days), and critically an **error budget** derived from the gap between 100% and the target — which is what enables burn-rate alerting and release-gating decisions. Two services both reporting "99.9% uptime" could have very different SLO definitions underneath (different SLIs, different compliance windows) that aren't directly comparable without knowing those specifics.
**Follow-up trap:** *"If two services both report 99.9% availability SLOs with 30-day windows, are their error budgets directly comparable?"* — only if their SLI definitions (what counts as "available" — e.g., synthetic uptime checks vs. real request success rate) and traffic patterns are actually equivalent; a low-traffic service and a high-traffic service with the same percentage SLO have very different absolute error budgets in terms of tolerable failed requests, even though the percentage looks identical.

### Q8 — Walk through why Cloud Trace's cost is rarely the deciding factor in a sampling-strategy decision, and what actually drives that decision instead.
**Testing:** distinguishing raw ingestion cost from the real operational cost drivers.
**Answer:** At 2.5M free spans/month and $0.20/million beyond, Cloud Trace's direct billing is negligible relative to compute or Logging spend for most workloads — a sampling decision driven purely by minimizing that specific line item would be optimizing the wrong number. The actual drivers are: downstream trace storage/query cost and latency at high retained-trace volume, signal-to-noise for engineers investigating an incident (too much routine trace data buries the interesting traces), and the practical need to preferentially retain error/slow-outlier traces (which head-based sampling doesn't guarantee) over routine successful ones.
**Follow-up trap:** *"So does that mean sampling rate doesn't matter much at all, since the direct cost is so low?"* — sampling rate still matters a great deal, just not primarily for the Cloud Trace bill itself — it matters for whether the traces an engineer actually needs during an incident are present in the trace store at all, which is a signal-quality problem that tail-based sampling addresses directly and head-based sampling addresses only probabilistically.

### Q9 — Explain why enabling verbose Data Access audit logs on a high-QPS BigQuery workload without any mitigation is a common, expensive mistake.
**Testing:** connecting a specific audit-log type to a realistic cost incident with numbers.
**Answer:** Data Access audit logs capture read/write operations on the data itself — for BigQuery specifically, that means every query execution generates an audit log entry, and a high-QPS analytics workload can produce audit-log volume comparable to or exceeding the workload's actual query traffic. Since Data Access logs are chargeable at the standard $0.50/GiB ingestion rate with no special discount, a workload running thousands of queries per hour can turn audit logging into one of the largest line items on the Logging bill, especially if nobody applied an exclusion filter or routed the logs to a cheaper destination.
**Follow-up trap:** *"If Data Access logging is this expensive, should you just leave it disabled?"* — no; for datasets with real compliance/security requirements (who accessed what data, when), Data Access logging is often a hard requirement, not optional — the correct mitigation is scoping it precisely (only the datasets that genuinely need the audit trail) and exporting to a cheap destination (BigQuery/GCS) rather than leaving it in the chargeable `_Default` bucket, not disabling it wholesale where it's actually required.

### Q10 — Compare GCP's and AWS's logging free tiers and explain the practical implication for a team migrating a logging-heavy workload from AWS to GCP.
**Testing:** applying a specific numeric comparison to a realistic migration scenario.
**Answer:** Cloud Logging offers 50 GiB/month free ingestion; CloudWatch Logs offers only 5 GB/month free — a 10x difference in free-tier headroom, even though both charge a similar flat rate (roughly $0.50/GB) beyond the free tier. A team migrating a logging-heavy workload gets meaningfully more runway before logging costs become material on GCP purely from the larger free tier, independent of any other optimization — though at real production log volume (well beyond either free tier), the per-GB rates converge and the actual cost driver becomes how well exclusion filters and log-routing hygiene are applied, not the free-tier difference.
**Follow-up trap:** *"Does that mean GCP is always cheaper for logging overall?"* — no, the free-tier gap mostly matters at low-to-moderate volume; at high volume, the deciding factor is operational discipline (exclusion filters, targeted sinks, right-sized retention) on either platform far more than the free-tier size, and a poorly-managed GCP logging setup with no exclusion filters can easily cost more in absolute terms than a well-managed CloudWatch setup with tight log-group retention policies.

### Q11 — Design a FinOps commitment strategy for a workload with genuinely unpredictable, growing usage on N2 instances. Would you recommend CUDs?
**Testing:** judgment under uncertainty, not blind commitment-purchasing.
**Answer:** For genuinely unpredictable, growing usage, the automatic Sustained Use Discount (up to 30%, zero commitment, applies to N2) already captures meaningful savings with no risk of stranding a commitment. A CUD purchase should be sized conservatively — well below the historical *minimum* observed usage, not the average or the Recommender's raw suggestion — so that even if growth stalls or usage temporarily drops, the committed portion stays fully utilized; the remainder of usage above that conservative floor rides on SUDs (or no discount) until the growth trajectory is established enough to justify committing further. Buying a CUD sized to current peak or average usage on a genuinely volatile workload risks paying for committed capacity that goes underutilized the moment growth slows.
**Follow-up trap:** *"Isn't leaving usage above the conservative CUD floor on SUD/no-discount pricing leaving savings on the table?"* — it's a deliberate tradeoff between capturing more discount now versus risk of a stranded commitment later — the right amount of conservatism depends on how confident the team actually is in the growth forecast, and the honest answer in an interview is naming that tradeoff explicitly rather than picking a number with false precision.

### Q12 — A service's SLO burn-rate alert fires correctly, on-call responds, but the underlying cause turns out to be a dependency's outage entirely outside the team's control. Was the alerting "wrong"?
**Testing:** understanding that SLO alerting measures user-observed impact, not attributing fault — a subtle but important distinction interviewers probe for.
**Answer:** No — the burn-rate alert did exactly what it's designed to do: signal that the service's error budget (a proxy for user-observed reliability) is being consumed too fast, regardless of root cause. SLOs and error budgets are deliberately cause-agnostic; a downstream dependency's outage degrading this service's SLI is still real user-observed impact, and the alert correctly surfaced it. What might need adjustment is the *response* process (routing a dependency-caused incident to the right owning team faster) or, if this is a recurring pattern, an architectural conversation about resilience against that dependency's failures — not the alerting logic itself, which correctly measured what users experienced.
**Follow-up trap:** *"Should the team then exclude that dependency's failures from the SLI calculation going forward, since it wasn't 'their fault'?"* — that's a legitimate question to raise but the default answer should be no: excluding dependency failures from the SLI risks the SLO no longer reflecting actual user experience, which defeats its purpose — if the dependency is genuinely outside reasonable control and its failures are common enough to distort the SLO meaningfully, the better fix is usually improving resilience (retries, fallbacks, circuit breakers) or renegotiating the SLO target itself with that dependency's reliability factored in, not quietly excluding inconvenient data from the measurement.

---

## Red flags that fail you

- Claiming an exclusion filter deletes the log entirely rather than just avoiding Logging's ingestion charge (it can still be exported via a sink).
- Not knowing which Cloud Audit Log types are free (Admin Activity, System Event) versus chargeable (Data Access, Policy Denied).
- Using a static error-rate threshold and calling it "SLO alerting" without a burn-rate/error-budget mechanism behind it.
- Not knowing Sustained Use Discounts are automatic/zero-commitment, or claiming they apply to every machine family (E2, C3, C4, N4, and accelerator families are excluded).
- Sizing a Committed Use Discount to the Recommender's raw suggestion without accounting for growth uncertainty or usage drops.
- Treating Cloud Trace's near-zero direct cost as a reason sampling strategy doesn't matter.
- Excluding a dependency's failures from an SLI to make the numbers look better rather than addressing the underlying resilience gap.

---

## Cheat card

```
CLOUD LOGGING: $0.50/GiB ingestion (50 GiB/mo free, includes 30-day
  storage). Extended retention: $0.01/GiB-mo beyond 30 days. LOG ROUTER
  = choke point: EXCLUSION filter stops ingestion billing entirely, even
  if a separate SINK still exports the log elsewhere (pay destination's
  rate instead -- GCS/BigQuery/Pub/Sub, usually far cheaper).

AUDIT LOGS (4 types): Admin Activity (free, always on, can't disable) +
  System Event (free, Google-initiated) = _Required bucket, 400-day free
  retention. Data Access (chargeable, off by default except a few
  services -- BIGGEST cost-spike risk) + Policy Denied (chargeable, on
  by default) = regular chargeable buckets.

CLOUD TRACE: 2.5M spans/mo free, $0.20/million beyond -- near-free.
  Sampling strategy driven by signal quality, not cost. HEAD-BASED
  (5-10% typical, ~90% cost cut, decision before outcome known -- misses
  proportional share of errors). TAIL-BASED (decision after full trace
  seen, keeps errors/slow outliers preferentially -- needs OTel Collector,
  not native to Cloud Trace).

SLO / ERROR BUDGET: budget = (1 - SLO%) x period. 99.9%/30-day =
  ~43.2 min allowed downtime. BURN RATE = consumption speed vs
  sustainable pace. Burn-rate alert (X% of budget in N-min lookback,
  default ~60min) beats static threshold -- accounts for REMAINING
  budget, not just current error rate. Tiered: fast-burn (10x, ~3 days
  to exhaust) = page; slow-burn (2x) = ticket.

SUD (Sustained Use Discount): AUTOMATIC, $0 commitment, up to 30% off,
  VM runs >25% of billing month. ONLY N1/N2/N2D/C2/M1/M2 -- E2, C3, C4,
  N4, accelerator families EXCLUDED. No AWS equivalent (RIs/Savings
  Plans always require commitment).

CUD (Committed Use Discount): commit vCPU+mem, 1yr=37% / 3yr=55% off,
  NO-UPFRONT ONLY (AWS RIs offer All/Partial-Upfront for deeper cuts).
  Default scope now BILLING ACCOUNT (2026 change, was per-project) --
  fixes cross-project commitment stranding. Recommender = usage-pattern
  suggestion only, no growth/drop modeling -- size below historical MIN
  usage, not the raw recommendation.

CROSS-CLOUD: Cloud Logging~CloudWatch Logs (both ~$0.50/GB, but GCP free
  tier 50GiB vs AWS 5GB = 10x). Cloud Trace~X-Ray (per-span vs per-trace
  billing model). Cloud Monitoring SLO~CloudWatch (no native burn-rate
  concept in CloudWatch -- build manually or use a 3rd party). SUD has
  NO AWS/Azure equivalent (automatic zero-commitment discount).
```

## Sources

- [GCP Cloud Logging Pricing — Finout](https://www.finout.io/blog/gcp-cloud-logging-pricing) — accessed 2026-08-08
- [How To Reduce Logging Costs in GCP — Finout](https://www.finout.io/blog/reducing-gcp-logging-costs) — accessed 2026-08-08
- [Cloud Audit Logs overview — Google Cloud Docs](https://docs.cloud.google.com/logging/docs/audit) — accessed 2026-08-08
- [Alerting on budget burn rate — Google Cloud Docs](https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/alerting-on-budget-burn-rate) — accessed 2026-08-08
- [How to Establish Error Budget Policies for Release Gating — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-establish-error-budget-policies-for-release-gating-on-google-cloud/view) — accessed 2026-08-08
- [Cloud Trace pricing — MonitoringCost](https://monitoringcost.com/apm-pricing-comparison) — accessed 2026-08-08
- [How to Compare OpenTelemetry vs Google Cloud Trace — OneUptime](https://oneuptime.com/blog/post/2026-02-06-compare-opentelemetry-vs-google-cloud-trace/view) — accessed 2026-08-08
- [Sustained use discounts — Google Cloud Docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts) — accessed 2026-08-08
- [GCP Committed Use Discounts vs AWS Savings Plans — atonementlicensing.com](https://atonementlicensing.com/blog/gcp-cud-vs-aws-savings-plan/) — accessed 2026-08-08
- [Introducing Committed Use Discount recommendations — Google Cloud Blog](https://cloud.google.com/blog/products/management-tools/introducing-committed-use-discount-recommendations) — accessed 2026-08-08
- [Top GCP FinOps Tools in 2026 — nOps](https://www.nops.io/blog/gcp-finops-tools/) — accessed 2026-08-08
- [Amazon CloudWatch Pricing 2026 — CloudBurn](https://cloudburn.io/blog/amazon-cloudwatch-pricing) — accessed 2026-08-08
- `clouds/CROSS-CLOUD-MAP.md` — internal cross-cloud equivalence reference

## Changelog
- 2026-08-08 — created
- 2026-08-09 — Cloud Monitoring Telemetry API for OTLP metric ingestion reaches GA — ingest OTLP metrics via an OpenTelemetry Collector/OTLP exporter directly into Cloud Monitoring ([src](https://docs.cloud.google.com/release-notes))
