# Monitor, Log Analytics and KQL, Application Insights, Cost Management

> **Track:** C-AZ Azure Atlas · **Time:** 1.5h · **Prereqs:** `C-AZ-compute`, `C-AZ-storage-db` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-ops` · **Tags:** ops

## The 30-second version

**Azure Monitor** is the umbrella platform (metrics, logs, alerts, dashboards); **Log Analytics** is its log-storage-and-query backend, built on **Kusto Query Language (KQL)** — a pipe-based query language ("filter, then aggregate, then project") that is Azure's one genuinely distinct piece of observability tooling with no direct AWS/GCP equivalent (CloudWatch Logs Insights borrows syntax ideas but isn't the same engine). **Application Insights** is Azure Monitor's APM layer — distributed tracing, dependency tracking, adaptive sampling — now OpenTelemetry-based rather than a proprietary SDK, making it Azure's analog to X-Ray/Cloud Trace but natively multi-signal (traces, metrics, logs in one data model). **Cost Management** is Azure's native FinOps tool: budgets, anomaly alerts, Advisor-driven rightsizing recommendations — organizationally stronger than AWS Cost Explorer for cross-subscription budget governance, but weaker on automated remediation actions. The pricing mechanics that actually bite: Log Analytics ingestion is billed per-GB (**~$2.30/GB for Analytics Logs**, with cheaper **Basic Logs at ~$0.50/GB** trading away join/summarize KQL support, and **Auxiliary Logs at ~$0.05/GB** for compliance-only data nobody queries interactively) — the tier choice is a genuine cost-vs-query-capability tradeoff, not just a pricing knob. Application Insights defaults to **adaptive sampling** (SDK-side, traffic-responsive, on by default in current SDKs) rather than a fixed percentage, and understanding that adaptive and fixed-rate sampling **disable ingestion-point sampling** when active is the specific mechanic that trips people debugging "why am I missing traces." The single biggest trap for someone from CloudWatch: KQL is a real, distinct skill investment — reusing an AWS mental model of "just grep the logs" against Log Analytics without learning `where`-before-`summarize` filtering discipline produces queries that scan hundreds of millions of rows and time out.

## Why this gets asked

The interviewer has watched a Log Analytics bill balloon because nobody set retention or picked the wrong log tier for high-volume, rarely-queried data, has debugged a "missing trace" incident that turned out to be adaptive sampling working exactly as designed, has explained why a KQL query that felt like "just SQL" scanned 500 million rows because the `where` clause came after an expensive join instead of before it, and wants to know whether you can reason about observability cost as a first-class design constraint, not an afterthought discovered on the first real invoice.

---

## Lineage: past → present → future

**What came before.** Azure's early monitoring story was fragmented: Azure Diagnostics (per-resource, VM-focused metrics/logs), System Center Operations Manager (on-prem-era, ported awkwardly to cloud), and Application Insights launched (2014-2015) as a separate, standalone APM product with no unified query layer connecting it to infrastructure logs. The pain: correlating "this API is slow" (an app-level trace) with "this VM's CPU spiked" (an infrastructure metric) meant pivoting between genuinely separate tools with different data models and no shared query language — the same fragmentation CloudWatch itself struggled with before Logs Insights unified query access.

**Where it stands now.** **Azure Monitor** now sits as the umbrella brand over a genuinely unified backend: Log Analytics workspaces store both infrastructure logs and Application Insights telemetry in the same **KQL-queryable** data model, letting one query correlate an app-level trace with an underlying VM or container metric. Application Insights itself completed a significant architectural shift to **OpenTelemetry-based instrumentation** as the current recommended SDK path, moving away from the older proprietary Application Insights SDK — aligning Azure with the same vendor-neutral instrumentation standard AWS and GCP have also adopted, closing what used to be a real portability gap. [OpenTelemetry sampling in Application Insights — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-sampling) — accessed 2026-08-08. Log tiering matured into a genuine three-way cost/capability spectrum: **Analytics Logs** (full KQL, ~$2.30/GB), **Basic Logs** (~$0.50/GB, no joins or summarize operators — filter-and-view only), and **Auxiliary Logs** (~$0.05/GB, for compliance/audit data that's rarely queried and needs a slower "search job" to access at all). [Azure Monitor pricing 2026 — pump.co](https://www.pump.co/blog/azure-monitor-pricing/) — accessed 2026-08-08.

**Where it's heading.** **Summary rules** (in preview as of early 2026) let a workspace pre-aggregate high-volume data at ingestion time into a smaller target table, cutting per-query compute for recurring detection/dashboard patterns by a reported 90%+ for the specific workloads they fit — moderate-to-high confidence this becomes a standard cost-optimization pattern given the scale of the reported savings, though preview maturity should be re-verified near interview time. [KQL and Log Analytics practical guide 2026 — zlarsen.cloud](https://zlarsen.cloud/posts/2026-05-15-log-analytics-kql/) — accessed 2026-08-08. Cost Management's direction is deeper Advisor-driven automated rightsizing recommendations and tighter Cloud Adoption Framework/FinOps Hub integration — Azure's answer to third-party FinOps tools increasingly encroaching on native cloud cost tooling's territory, moderate confidence on how far native tooling closes the automated-remediation gap against dedicated FinOps platforms.

---

## Mental model

```
AZURE MONITOR (the umbrella brand)
  │
  ├── METRICS (near-real-time numeric time series, platform + custom)
  │     → Metric Alerts (fast, cheap, coarse)
  │
  ├── LOG ANALYTICS WORKSPACE (the KQL-queryable backend)
  │     │
  │     ├── Infrastructure/platform logs (VM, NSG flow logs, activity log...)
  │     ├── APPLICATION INSIGHTS telemetry (traces, deps, exceptions --
  │     │     now OpenTelemetry-instrumented) -- SAME workspace, SAME KQL
  │     │
  │     └── Log tiers (cost vs KQL capability tradeoff):
  │           ANALYTICS LOGS  (~$2.30/GB) -- full KQL: where/join/summarize
  │           BASIC LOGS      (~$0.50/GB) -- filter/view only, NO join/summarize
  │           AUXILIARY LOGS  (~$0.05/GB) -- compliance data, needs a SEARCH JOB
  │                                          (async) to query at all
  │
  └── Log Alerts (KQL-query-driven, flexible but slower/costlier than metric alerts)

KQL QUERY DISCIPLINE (the actual skill gap vs "just grep the logs"):
  SecurityEvent
  | where TimeGenerated > ago(1h) and EventID == 4625   <- FILTER FIRST
  | summarize count() by Account, Computer                <- THEN aggregate
  (filtering after a join/summarize on an unfiltered table = 500M-row scan)

COST MANAGEMENT: budgets + anomaly alerts + Advisor rightsizing recs
  ~= AWS Cost Explorer, but stronger cross-subscription budget governance,
     weaker automated remediation actions
```

---

## How it actually works

### Azure Monitor, Log Analytics, and the three log tiers

A **Log Analytics workspace** is the storage/query unit — most organizations end up with multiple workspaces (per environment, per team, per compliance boundary), which is fine for isolation but creates a real cross-workspace query need, solved via KQL's `union` and `workspace()` cross-workspace query functions rather than a single global namespace the way CloudWatch Logs groups can feel.

**Analytics Logs** (the default, full-featured tier, **~$2.30/GB** ingestion) support the complete KQL surface: joins, `summarize`, full indexing, alerting, dashboards. **Basic Logs** (**~$0.50/GB**) trade away joins and summarization operators entirely — usable for filtering and direct viewing of high-volume, verbose diagnostic data (think: verbose application debug logs you occasionally grep but never aggregate) at roughly a fifth of the cost. **Auxiliary Logs** (**~$0.05/GB**) target compliance/audit data that's ingested for retention purposes and almost never queried — querying it requires launching an asynchronous **search job** that runs a KQL query against the archived data and materializes results into a new, normally-queryable table, rather than being interactively queryable the way Analytics/Basic tiers are. [Azure Monitor pricing 2026 — pump.co](https://www.pump.co/blog/azure-monitor-pricing/) — accessed 2026-08-08.

**Retention**: workspaces get a **31-day grace period** before additional retention charges kick in. Beyond that, **Interactive Retention** (queryable retention up to 2 years) runs roughly **$0.10/GB/month**, and **Long-Term Retention** (archived, up to 12 years, requiring a search job to query — same async pattern as Auxiliary Logs) runs roughly **$0.02/GB/month**. Workspaces ingesting consistently **above 100GB/day** qualify for commitment-tier discounts, a meaningful lever for high-volume production estates. [Azure Monitor pricing — Microsoft](https://azure.microsoft.com/en-us/pricing/details/monitor/) — accessed 2026-08-08.

### KQL — the actual skill, not "SQL with different keywords"

KQL is pipe-based: each operator transforms the result of the previous stage, read top-to-bottom as a data pipeline rather than SQL's declarative "describe the result set" structure. The single highest-leverage discipline: **filter with `where` before expensive operations** (`join`, `summarize`) — a 24-hour query against a high-volume table like `SecurityEvent` without an early `EventID` or similarly selective filter can scan **50-500 million rows** depending on audit policy verbosity, versus a filtered query touching a small fraction of that.

```kql
// untested sketch — KQL discipline: filter before summarize
SecurityEvent
| where TimeGenerated > ago(1h)
| where EventID == 4625                    // filter FIRST, narrows the row set
| summarize FailedLogons = count() by Account, Computer   // THEN aggregate
| where FailedLogons > 5
| order by FailedLogons desc

// cross-workspace query -- a real need once an org has multiple workspaces
// per environment/team/compliance boundary
union
    workspace("prod-workspace").AppRequests,
    workspace("staging-workspace").AppRequests
| where TimeGenerated > ago(24h)
| summarize avg(DurationMs) by bin(TimeGenerated, 1h), cloud_RoleName
```

`project` (select only needed columns) reduces data moved through the query pipeline and is a real performance lever, not just a style preference — the KQL equivalent of avoiding `SELECT *`. **Summary rules** (preview, early 2026) let a workspace pre-aggregate high-volume raw data into a smaller target table at ingestion time, so a recurring detection or dashboard query hits the pre-aggregated table instead of re-scanning raw data every run — reported to cut per-query compute by 90%+ for the specific pattern of "same aggregation, run every N minutes, against a large table."

### Application Insights — OpenTelemetry and sampling

Application Insights' current recommended instrumentation path is **OpenTelemetry-based** rather than the older proprietary SDK, aligning with AWS/GCP's own OTel adoption and closing a real vendor-lock-in gap that used to exist in APM instrumentation choice.

**Sampling** has two layers that interact in a way that trips people: **adaptive sampling** (SDK-side, enabled by default in current ASP.NET/ASP.NET Core/Azure Functions SDKs) dynamically adjusts the sampled percentage in real time based on observed traffic volume, rather than sampling at a fixed rate — the goal is staying under a target telemetry volume automatically as traffic fluctuates. **Fixed-rate sampling** (SDK-side, manually configured, commonly tuned to **10-25% for steady-state production**) is the simpler, predictable alternative. Both are *source-level* controls. **Ingestion sampling** is a separate, ingestion-point fallback that drops data after it's already been sent, with **no control over which specific traces/spans are kept** — and critically, **when the Application Insights ingestion endpoint detects a sampling rate below 100% already applied at the SDK level (adaptive or fixed), it ignores any configured ingestion sampling rate entirely.** [Telemetry sampling in Application Insights — Microsoft Learn](https://learn.microsoft.com/en-us/previous-versions/azure/azure-monitor/app/sampling-classic-api) — accessed 2026-08-08. This is the specific mechanic behind the common "why is data missing / why isn't my ingestion sampling rate taking effect" debugging session — SDK-level sampling silently wins.

Real cost-shape numbers for high-volume tracing: at roughly 100 RPS with 10 spans/request and 100% sampling, that's **~86 million spans/day**, and vendor tracing ingestion commonly runs **$0.50-2.50 per million spans** — meaning unsampled tracing at moderate production volume can run **$43-215/day** on span ingestion alone, the concrete number that makes sampling a cost decision, not just a noise-reduction one.

### Cost Management

Azure Cost Management provides **budgets** (spend thresholds with configurable alert actions), **cost analysis** (breakdowns by resource group, subscription, service, tag, time period), **anomaly detection alerts** (flagging unusual consumption patterns), and **Advisor** integration surfacing rightsizing and Reserved Instance/Savings Plan coverage recommendations, with native **Power BI** export for organizations already standardized on Microsoft's BI stack. Compared to **AWS Cost Explorer**: Azure's tooling is generally regarded as stronger for **organization-wide, cross-subscription budget governance** (management-group-scoped budgets mirroring the RBAC scope hierarchy from `C-AZ-identity`), while AWS Cost Explorer is stronger on **automated remediation actions** and has a longer historical lookback (12 months back, 12 months forecast) with no additional cost to enable — Cost Management is free to use as well, but its automated-action ecosystem is thinner, more often requiring Azure Automation/Logic Apps glue to act on a cost anomaly rather than a built-in automated response. [Azure vs AWS Cost Explorer 2026 — costimizer.ai](https://costimizer.ai/blogs/azure-vs-aws-cost-explorer) — accessed 2026-08-08.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| CloudWatch (metrics + logs) | Azure Monitor + Log Analytics | Cloud Monitoring + Logging | KQL is a genuinely distinct query language with no direct AWS/GCP equivalent — budget real learning time |
| CloudWatch Logs Insights | KQL over Log Analytics | Cloud Logging query language | Log Analytics unifies infra logs and APM telemetry (App Insights) in one workspace/query surface by default |
| X-Ray | Application Insights (distributed tracing) | Cloud Trace | All three have converged on OpenTelemetry as the recommended instrumentation standard |
| CloudTrail | Activity Log | Cloud Audit Logs | Activity Log is control-plane/management-operation audit, distinct from Log Analytics' application/infra telemetry |
| Cost Explorer | Cost Management | Cloud Billing / FinOps Hub | Azure stronger on cross-subscription budget governance; AWS stronger on automated remediation actions |

---

## Build it from scratch

Minimal end-to-end shape: a metric alert plus a log-based KQL alert covering both the fast/coarse and flexible/precise alerting patterns, matching `labs/bicep/08-ops/`:

```bash
# untested sketch — az CLI: fast metric alert (near-real-time, coarse) ...
az monitor metrics alert create \
  --name high-cpu-alert \
  --resource-group my-rg \
  --scopes /subscriptions/.../virtualMachines/my-vm \
  --condition "avg Percentage CPU > 85" \
  --window-size 5m --evaluation-frequency 1m

# ... alongside a KQL-driven log alert (flexible, slower, precise)
az monitor scheduled-query create \
  --name failed-logon-spike \
  --resource-group my-rg \
  --scopes /subscriptions/.../workspaces/my-log-analytics-ws \
  --condition "count 'FailedLogons' > 5" \
  --condition-query FailedLogons="SecurityEvent | where EventID == 4625 | summarize count() by bin(TimeGenerated, 5m)" \
  --window-size 5m --evaluation-frequency 5m
```

---

## How it's done in production

A typical production observability setup: **Analytics Logs** tier for anything feeding active dashboards/alerts/investigations (application traces, security events, key infrastructure metrics-as-logs), **Basic Logs** for high-volume verbose diagnostic data that's occasionally grepped but never aggregated, **Auxiliary Logs** for pure compliance/audit retention nobody expects to query interactively. **Application Insights** instrumented via OpenTelemetry, adaptive sampling as the default with fixed-rate sampling tuned in for specific high-volume, well-understood traffic patterns where predictable cost matters more than adaptive responsiveness. **Log Analytics workspace topology** split by environment and compliance boundary (not one giant workspace), with cross-workspace KQL queries for the genuine cross-cutting investigations, and **summary rules** (once past preview) applied to the specific recurring dashboard/detection queries that dominate compute cost. **Cost Management** budgets scoped at the management-group level mirroring the RBAC hierarchy, with Advisor rightsizing recommendations reviewed on a cadence rather than ignored.

| Symptom | Cause | Fix |
|---|---|---|
| Log Analytics bill grows sharply after onboarding a new high-volume application | New app's logs landed in the default Analytics Logs tier despite being high-volume, rarely-aggregated diagnostic data | Route that data source to Basic Logs (or Auxiliary Logs if genuinely compliance-only) instead of Analytics Logs |
| A KQL query against `SecurityEvent` times out or takes minutes to return | `where` filter applied after a `join`/`summarize`, or missing an early selective filter (like `EventID`) — scanning 50-500M rows depending on audit verbosity | Restructure the query to filter first with the most selective `where` clause before any join/summarize/aggregation |
| Distributed traces are "missing" for some requests despite Application Insights being enabled | Adaptive (or fixed-rate) sampling is working as designed — not every request is traced by default; ingestion sampling is also silently disabled once SDK-level sampling is active | Confirm expected behavior against the configured sampling rate; if full trace capture is genuinely required for specific critical paths, consider disabling sampling for those paths specifically rather than assuming a bug |
| Setting an ingestion sampling rate in the portal has no visible effect | SDK-level adaptive or fixed-rate sampling is already active (below 100%), which causes the ingestion endpoint to ignore the configured ingestion sampling rate entirely | Adjust sampling at the SDK level (adaptive target or fixed-rate percentage) instead of relying on ingestion-point sampling when SDK-level sampling is already in play |
| A cost anomaly alert fires but nobody takes action until the next billing cycle | Cost Management flagged the anomaly but no automated remediation action was wired up — native tooling is weaker here than AWS's automated-response ecosystem | Wire the anomaly alert to an Azure Automation runbook or Logic App that takes a concrete action (notify + optionally scale down/deallocate), rather than relying on a human noticing the alert |
| Querying archived compliance log data takes much longer than expected | Auxiliary Logs (and Long-Term Retention data generally) aren't interactively queryable — a search job must run asynchronously and materialize results into a new table first | Plan for search-job latency explicitly in any compliance-investigation runbook; it is not a live KQL query against the archive |

---

## Tradeoffs & when NOT to use it

- **Don't default every log source to the Analytics Logs tier.** High-volume, rarely-aggregated diagnostic data is a strong candidate for Basic Logs at roughly a fifth of the cost, trading away joins/summarize for data that's usually filtered-and-viewed, not aggregated.
- **Don't assume a KQL query written like SQL will perform like SQL.** The `where`-before-`summarize`/`join` filtering discipline is not optional at real log volumes; treating KQL as "SQL with different keywords" produces genuinely slow, expensive queries.
- **Don't rely on ingestion sampling as your primary sampling control once SDK-level sampling is active.** It's silently ignored in that case — control sampling at the SDK (adaptive target or fixed rate), not at the ingestion endpoint, when both could theoretically apply.
- **Don't run 100% unsampled distributed tracing at real production volume without a specific reason.** The per-span ingestion cost is real and scales linearly with traffic; adaptive or tuned fixed-rate sampling is the default for a reason.
- **Don't treat Auxiliary Logs or Long-Term Retention data as interactively queryable.** Any workflow depending on querying that data needs to account for asynchronous search-job latency, not assume live KQL access.
- **Don't assume Azure Cost Management's anomaly alerts trigger any automated response on their own.** Unlike some AWS-native automated-remediation patterns, Azure's native tooling generally requires explicit Automation/Logic Apps glue to turn a cost alert into an action.

---

## Interview questions

### Q1 — Explain the three Log Analytics log tiers and the real tradeoff each represents.
**Testing:** whether tiering is understood as a cost-vs-capability decision, not just a pricing table.
**Answer:** Analytics Logs (~$2.30/GB) support the full KQL surface — joins, summarize, indexing, alerting. Basic Logs (~$0.50/GB) drop joins and summarization operators entirely, usable for filter-and-view access to high-volume data that's rarely aggregated. Auxiliary Logs (~$0.05/GB) target compliance/audit data that's essentially never interactively queried — accessing it requires an asynchronous search job rather than a live KQL query. The decision for each data source is whether it needs real-time aggregation/alerting (Analytics), occasional filtered viewing (Basic), or pure retention (Auxiliary).
**Follow-up trap:** *"Can a workspace mix tiers per table, or is the whole workspace locked to one tier?"* — tiers are configured per-table (per data source), not workspace-wide, which is exactly what makes the cost-optimization pattern of "route high-volume diagnostic logs to Basic while keeping security events on Analytics" possible within a single workspace.

### Q2 — A KQL query against a high-volume security log table times out. Diagnose the likely structural issue.
**Testing:** the `where`-before-`summarize`/`join` discipline, the single highest-leverage KQL performance lesson.
**Answer:** The query likely applies its `where` filter after an expensive operation (join or summarize) rather than before, or lacks an early, selective filter (like a specific `EventID`) at all — a 24-hour query against a table like `SecurityEvent` without early filtering can scan 50-500 million rows depending on audit policy verbosity. Fix: restructure so the most selective `where` clause runs first, narrowing the row set before any join or aggregation touches it.
**Follow-up trap:** *"Does adding `project` to select fewer columns matter as much as filtering rows?"* — filtering rows early is the higher-leverage fix since it reduces the actual data volume the query engine processes at each subsequent stage, but `project` (selecting only needed columns) is a real secondary lever that reduces data moved through the pipeline — both matter, but row filtering first is the more common root cause of a timeout.

### Q3 — A team reports "missing" distributed traces despite Application Insights being fully configured. What's the most likely explanation, and how do you confirm it?
**Testing:** the sampling-as-expected-behavior distinction, a common false-alarm-vs-real-bug debugging scenario.
**Answer:** Adaptive sampling (on by default in current SDKs) or fixed-rate sampling is very likely working as designed — not every request is traced by default, and adaptive sampling specifically adjusts its rate based on real-time traffic volume rather than sampling every request. Confirm by checking the configured sampling settings and the observed sampled percentage in telemetry, rather than assuming an instrumentation bug.
**Follow-up trap:** *"If a specific critical business path genuinely needs 100% trace capture regardless of sampling, how do you achieve that?"* — most SDKs support marking specific operations/telemetry as always-included (bypassing the sampling decision) or configuring a separate, unsampled telemetry initializer for critical paths, rather than disabling sampling globally, which would reintroduce the cost problem sampling exists to solve.

### Q4 — Explain why setting an ingestion sampling rate in the Azure portal sometimes has no observable effect.
**Testing:** the specific SDK-vs-ingestion sampling interaction, a genuinely non-obvious mechanic.
**Answer:** When the Application Insights ingestion endpoint detects that telemetry already arrived with a sampling rate below 100% (meaning SDK-level adaptive or fixed-rate sampling is active), it ignores any configured ingestion sampling rate entirely — SDK-level sampling takes precedence. Setting an ingestion sampling rate only has effect when no SDK-level sampling is already reducing the incoming data.
**Follow-up trap:** *"Why would ingestion sampling exist at all if SDK-level sampling usually wins?"* — ingestion sampling is a fallback specifically for scenarios where SDK-level sampling *isn't* controllable or configured (e.g., telemetry arriving at 100% from a source that can't be instrumented with sampling logic), giving a last-resort cost control at the ingestion point rather than a primary control mechanism.

### Q5 — Estimate the daily span-ingestion cost for a service running at 100 RPS with 10 spans per request and full (unsampled) tracing, and explain why this matters for a sampling decision.
**Testing:** whether the cost-of-unsampled-tracing math is understood concretely, not just qualitatively.
**Answer:** 100 RPS × 10 spans/request × 86,400 seconds/day ≈ 86 million spans/day. At a typical vendor tracing rate of roughly $0.50-2.50 per million spans, that's approximately $43-215/day on span ingestion alone for one moderately-trafficked service. This is the concrete number that turns sampling from a "reduce noise" decision into a direct, material cost-control decision — a fleet of several such services running fully unsampled compounds quickly into a real budget line item.
**Follow-up trap:** *"Does sampling to 10% simply cut this cost to 10% of the unsampled figure?"* — roughly, yes, for the ingestion cost specifically (10% of 86M spans/day ≈ 8.6M spans/day, correspondingly ~10% of the cost), but the tradeoff is losing visibility into the 90% of unsampled requests for tail-latency or rare-error debugging — the cost savings are real and roughly linear, but so is the corresponding loss of trace completeness for anomaly investigation.

### Q6 — Compare Azure Cost Management to AWS Cost Explorer on the specific dimension most likely to matter for a large multi-team organization.
**Testing:** the cross-subscription governance vs. automated-remediation distinction, not a generic feature list.
**Answer:** Azure Cost Management is generally stronger for organization-wide, cross-subscription budget governance — budgets can be scoped at the management-group level, mirroring the same RBAC scope hierarchy (management group → subscription → resource group) used for access control, giving genuinely hierarchical cost governance. AWS Cost Explorer is generally stronger on automated remediation actions and has a longer native historical lookback (12 months) at no additional cost. For a large multi-team Azure organization specifically, the management-group-aligned budget hierarchy is the more differentiating capability.
**Follow-up trap:** *"Does Azure Cost Management have any native automated remediation at all, or is it purely visibility/alerting?"* — it provides budget alerts and Advisor recommendations, but turning an alert into an automated action (e.g., auto-deallocating an over-budget resource) typically requires explicit glue via Azure Automation or Logic Apps rather than a built-in automated-response feature — visibility and governance are native strengths, automated action is not.

### Q7 — Design a Log Analytics workspace topology for an organization with dev/staging/prod environments and a compliance requirement to retain audit logs for 7 years.
**Testing:** synthesizing workspace design, tiering, and retention into a coherent architecture.
**Answer:** Separate workspaces per environment (dev/staging/prod) for data isolation and blast-radius containment, using cross-workspace KQL `union`/`workspace()` queries for the genuine cross-cutting investigations that need to span environments. Application and infrastructure telemetry actively used for dashboards/alerts stays on Analytics Logs tier with standard interactive retention; the 7-year compliance audit data goes on Auxiliary Logs (cheapest ingestion) with Long-Term Retention (up to 12 years, well past the 7-year requirement, at the cheapest retention rate), accepting that querying it requires an async search job rather than live KQL access — appropriate for data that's retained for audit purposes, not day-to-day investigation.
**Follow-up trap:** *"Does splitting workspaces by environment complicate alerting that needs to correlate prod incidents with staging validation data?"* — yes, this is a real tradeoff; cross-workspace log alerts and queries are supported via KQL's cross-workspace functions, but they add query complexity and can't always match the simplicity of a single-workspace query — the isolation benefit (blast radius, RBAC scoping, compliance boundary) is usually judged worth this added complexity for genuinely separate environments.

### Q8 — A team notices their Log Analytics bill spiked after a new microservice's verbose debug-level logging went to production. Diagnose and fix without disabling logging.
**Testing:** the tiering-as-cost-lever answer, avoiding the naive "just log less" response.
**Answer:** Rather than disabling the verbose logging (losing debugging visibility), check whether that specific log source is landing in the default Analytics Logs tier despite being high-volume and rarely aggregated — if the team mostly filters and views this data rather than running joins/summarize against it, routing it to Basic Logs (roughly a fifth of the per-GB cost) preserves the debugging capability at materially lower cost. If it's genuinely never queried outside rare compliance investigations, Auxiliary Logs is an even more aggressive option.
**Follow-up trap:** *"Does moving to Basic Logs break any existing alerts or dashboards built against that data?"* — yes, Basic Logs' restricted KQL feature set (no joins, no summarize) will break any alert or dashboard query relying on those operators against that specific table — this migration requires auditing existing queries against the table first, not just flipping the tier and discovering breakage after the fact.

### Q9 — Explain what a KQL "summary rule" does and why it specifically targets a common cost/performance pattern.
**Testing:** a genuinely current (preview-stage) feature and the specific pattern it optimizes.
**Answer:** A summary rule pre-aggregates high-volume raw data at ingestion time into a smaller target table, so a recurring query (a detection rule or dashboard refresh running every few minutes against a large raw table) can query the pre-aggregated table instead of re-scanning and re-aggregating raw data on every single run. This specifically targets the "same aggregation, run repeatedly, against a large table" pattern common in security detections and operational dashboards, reportedly cutting per-query compute by 90%+ for workloads matching that shape.
**Follow-up trap:** *"Does a summary rule eliminate the need to ever query the raw underlying table?"* — no, the raw table remains available for ad-hoc, non-repeating investigative queries that need row-level detail the pre-aggregated summary doesn't preserve; summary rules optimize the specific repeated-aggregation pattern, not general-purpose querying of that data source.

### Q10 — Why is KQL described as having "no direct AWS/GCP equivalent," and what's the practical implication for an AWS-experienced engineer joining an Azure-heavy team?
**Testing:** honest assessment of a genuine skill-transfer gap, avoiding the trap of assuming all cloud query languages are interchangeable.
**Answer:** CloudWatch Logs Insights and Cloud Logging's query languages share some surface-level ideas with KQL (filtering, aggregation pipelines) but are different engines with different syntax, operators, and performance characteristics — KQL's pipe-based, Kusto-engine-specific model (used across Log Analytics, Application Insights, Microsoft Sentinel, and Microsoft Fabric's Real-Time Intelligence) is a genuinely distinct skill investment, not a syntax reskin of something an AWS-experienced engineer already knows. Practical implication: budget real learning time for KQL specifically — the filter-before-aggregate performance discipline, join syntax, and time-series functions (`bin()`, `ago()`) are not things that transfer automatically from CloudWatch Logs Insights fluency.
**Follow-up trap:** *"Is that learning investment wasted if the organization later moves off Azure?"* — largely portable within the Microsoft ecosystem (the same KQL skill applies across Log Analytics, Sentinel, and Fabric's Real-Time Intelligence), but it doesn't transfer to CloudWatch or Cloud Logging directly the way, say, general SQL knowledge transfers across relational databases — a fair, non-defensive answer names this as a real, scoped cost of choosing Azure's observability stack rather than downplaying it.

---

## Red flags that fail you

- Not knowing the three Log Analytics log tiers (Analytics/Basic/Auxiliary) or their real KQL-capability tradeoffs.
- Writing or describing a KQL query that filters after an expensive join/summarize rather than before.
- Treating "missing traces" as automatically a bug without considering adaptive/fixed-rate sampling as the likely explanation.
- Not knowing that SDK-level sampling silently overrides configured ingestion sampling.
- Claiming Auxiliary Logs or Long-Term Retention data is interactively queryable the same way Analytics Logs is.
- Describing KQL as "basically the same as CloudWatch Logs Insights" without naming it as a distinct skill investment.
- Assuming Azure Cost Management anomaly alerts trigger automated remediation without explicit configuration.

---

## Cheat card

```
AZURE MONITOR = umbrella. LOG ANALYTICS WORKSPACE = KQL-queryable backend for BOTH
  infra logs and Application Insights telemetry (unified, unlike separate CloudWatch
  Logs vs X-Ray data stores).

LOG TIERS (per-table, not workspace-wide):
  ANALYTICS LOGS  ~$2.30/GB -- full KQL (join, summarize, indexing, alerting).
  BASIC LOGS      ~$0.50/GB -- filter/view only, NO join/summarize.
  AUXILIARY LOGS  ~$0.05/GB -- compliance data, needs ASYNC SEARCH JOB to query.
  Retention: 31-day grace, then Interactive ~$0.10/GB/mo (up to 2yr),
    Long-Term ~$0.02/GB/mo (up to 12yr, also needs search job). >100GB/day =
    commitment-tier discounts.

KQL DISCIPLINE: pipe-based (filter -> aggregate -> project), NOT SQL. FILTER
  (where) BEFORE join/summarize -- unfiltered 24hr query on high-volume table
  (e.g. SecurityEvent) can scan 50-500M rows. project = select only needed cols.
  Cross-workspace: union + workspace("name").Table.
  SUMMARY RULES (preview, early 2026): pre-aggregate at ingest, cuts repeated-
  query compute 90%+ for recurring detection/dashboard patterns.

APPLICATION INSIGHTS: current SDK path = OpenTelemetry-based (not proprietary SDK).
  ADAPTIVE SAMPLING: SDK-side, ON BY DEFAULT, adjusts % in real-time to traffic.
  FIXED-RATE SAMPLING: SDK-side, manual, typically 10-25% steady-state prod.
  INGESTION SAMPLING: ingestion-point fallback, NO control over which spans kept,
  SILENTLY IGNORED whenever SDK-level sampling (adaptive/fixed, <100%) is active.
  Cost math: 100 RPS x 10 spans/req x 100% sampling = ~86M spans/day.
  Vendor tracing ~$0.50-2.50/M spans => ~$43-215/day unsampled for ONE service.

COST MANAGEMENT: budgets (mgmt-group-scoped, mirrors RBAC hierarchy), cost
  analysis, anomaly alerts, Advisor rightsizing recs, Power BI export.
  vs AWS Cost Explorer: Azure stronger cross-subscription budget governance,
  AWS stronger automated remediation + longer free lookback (12mo). Azure alerts
  need explicit Automation/Logic Apps glue for automated action.

CROSS-CLOUD: Monitor+Log Analytics~=CloudWatch. KQL has NO direct AWS/GCP
  equivalent -- genuine distinct skill investment. App Insights~=X-Ray/Cloud
  Trace (all 3 now OpenTelemetry-based). Activity Log~=CloudTrail. Cost
  Management~=Cost Explorer.
```

## Sources

- [Azure Monitor Pricing: Complete Cost Guide for 2026 — pump.co](https://www.pump.co/blog/azure-monitor-pricing/) — accessed 2026-08-08
- [Pricing — Azure Monitor — Microsoft](https://azure.microsoft.com/en-us/pricing/details/monitor/) — accessed 2026-08-08
- [Telemetry sampling in Azure Application Insights — Microsoft Learn](https://learn.microsoft.com/en-us/previous-versions/azure/azure-monitor/app/sampling-classic-api) — accessed 2026-08-08
- [OpenTelemetry sampling — Azure Monitor — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-sampling) — accessed 2026-08-08
- [Azure Log Analytics and KQL: A Practical Guide — zlarsen.cloud](https://zlarsen.cloud/posts/2026-05-15-log-analytics-kql/) — accessed 2026-08-08
- [Azure vs AWS Cost Explorer: Which Tool Stops Cloud Waste? — costimizer.ai](https://costimizer.ai/blogs/azure-vs-aws-cost-explorer) — accessed 2026-08-08
- [How to Write KQL Queries to Analyze Performance Metrics — OneUptime 2026](https://oneuptime.com/blog/post/2026-02-16-how-to-write-kql-queries-to-analyze-performance-metrics-in-azure-log-analytics/view) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
