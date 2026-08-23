# Azure Operations Deep: Azure Monitor, Log Analytics, App Insights, Cost Management

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-ops` · **Tags:** operations,critical

## The 30-second version

Azure Monitor is one pipeline wearing four products: platform metrics (free, ~93-day retention) and the Activity Log flow automatically, while everything else funnels into **Log Analytics workspaces** whose *table plans* decide your bill — Analytics tables include 31 days of interactive retention (90 with Sentinel or App Insights) and full KQL at included query cost; Basic and Auxiliary plans cut ingestion price dramatically in exchange for single-table queries billed per GB scanned and only 30 interactive days, with all plans reaching up to ~12 years of cheap long-term retrieval via search jobs. Application Insights rides inside Log Analytics as the `App*` tables, instrumented today through the **Azure Monitor OpenTelemetry Distro**, with adaptive sampling controlling volume and — the trap — silently biasing per-request telemetry while metrics stay exact. Cost Management closes the loop: budgets with threshold alerts, ML-driven cost anomaly detection, amortized-cost views exposing reservation/savings-plan reality, and tag governance enforced by Azure Policy. The interview probes whether you can design telemetry that survives both an outage review and a finance review — teams fail at the second far more often.

## Why this gets asked

Because observability bills are where engineering meets CFO, and every interviewer has a scar: the team that left console logging enabled in production and multiplied ingestion costs (one documented case cut observability spend ~87% just by disabling a console provider); the daily cap nobody remembered setting that silently swallowed error telemetry during an outage; the log alert that fired hundreds of times during a blip because evaluation frequency wasn't matched to remediation; the month-end invoice nobody could attribute to teams. At staff level these are design questions — which table plan for which stream, what sampling preserves and destroys, how alert quality survives alert volume, how cost attribution works before the first surprise invoice — not "how do you write KQL."

---

## Lineage: past → present → future

**What came before.** The OMS/SCOM lineage: Operations Management Suite workspaces, the Microsoft Monitoring Agent, per-node pricing entitling each VM roughly 500 MB/day, and Application Insights as a separate SDK-based product with its own classic resource type and per-node enterprise tiers. Everything fragmented: metrics in one store, logs in another, App Insights data in a third; cross-correlation required manual joins between portals. The pain: per-node economics punished fleet growth, agents duplicated, and "where does this telemetry live" had three correct answers depending on product version.

**Where it stands now.** Consolidation completed around Azure Monitor's pipeline: Data Collection Rules (DCRs) declaratively route telemetry from the unified Azure Monitor Agent (legacy MMA/OMS agent retired August 2024) into workspace tables with transformations applied at ingestion; workspace-based App Insights made application telemetry ordinary workspace tables (`AppRequests`, `AppTraces`, `AppDependencies`); table plans (Analytics/Basic/Auxiliary) turned retention economics into a per-table decision mixing all three in one workspace; the Azure Monitor OpenTelemetry Distro became the standard instrumentation path with auto-instrumentation; managed Prometheus and managed Grafana absorbed Kubernetes-native monitoring; alerts, workbooks, and DCRs are Bicep/Terraform resources like any other. Cost tooling matured in parallel: cost anomaly detection flags irregular daily spend, amortized views spread reservation/savings-plan purchases across consuming resources, and FOCUS-format cost exports became the FinOps interchange. Live disagreements: centralized versus per-team workspace architectures (cost control versus RBAC/retention autonomy), and how aggressively to sample traces before incident forensics suffers.

**Where it's heading.** High confidence: OpenTelemetry keeps absorbing vendor-specific agents; Auxiliary/Lake-class storage gets cheaper as audit-scale retention normalizes; FOCUS billing spreads making multi-cloud FinOps tooling real. Medium confidence: summary-rule aggregation becoming default practice (query-the-aggregate-not-the-raw) as volumes grow; AI-assisted diagnostics shipping into every surface. Speculative: tracing economics improving enough to make 100% capture affordable at high scale — don't architect around it. Durable underneath: sampling theory, cardinality discipline, SLO-shaped alerting, and unit-economics-of-telemetry transfer across every cloud.

---

## Mental model

```
                 AZURE MONITOR PIPELINE

 SOURCES                COLLECTION            STORE (Log Analytics)
 ---------              ----------            ---------------------
 apps (OTel distro) --> DCR + transformations -> TABLE PLAN decides $:
 k8s (managed Prom.) -->   (filter/project       ANALYTICS : full KQL,
 PaaS diagnostic         at ingest; >50%        31 d incl. (90 w/Sentinel),
   settings ---------->    filtered = extra     queries included
 VMs (AMA agent) ------>    processing fee!)    BASIC     : cheap ingest,
 Activity Log --------->                       30 d fixed, per-GB scans
 platform metrics -----> (separate TS store,   AUXILIARY : cheapest ingest,
                          free ~93 d)          slowest queries
                                            all -> LONG-TERM RETENTION
ALERTS <--- metric rules · log-scheduled rules · activity rules      (12 y max,
ACTION GROUPS ---> email/SMS/webhook/logic-app/ITSM                  search jobs)
COST SIDE: budgets + anomaly detection + amortized views + tags
```

The one-liner: **telemetry is a supply chain** — every span you emit is inventory someone pays to store, so design collection like procurement: buy what incident response needs, discount what compliance needs, refuse what neither justifies.

---

## How it actually works

### The pipeline: DCRs, agents, transformations

Data Collection Rules declare source → destination flows: which extension/agent collects what, optional KQL transformations applied in the Azure Monitor cloud pipeline (filter columns/rows before storage), and target tables. The Azure Monitor Agent replaced legacy agents entirely (MMA retired August 2024). Transformations matter commercially: filtering more than ~50% of incoming data out triggers billed "log processing" charges on the excess beyond that threshold, so aggressive-but-thoughtful filtering beats blanket drops. PaaS services route logs via diagnostic settings (per resource), apps via OTel, VMs via AMA+DCR, Kubernetes via Container Insights and managed Prometheus add-ons.

### Table plans — the economic core

| Plan | Ingestion | Interactive retention | Query | Best for |
|---|---|---|---|---|
| Analytics | Standard rate | 31 days included (90 w/ Sentinel/App Insights), extendable interactively up to 2 years | Full KQL, multi-table joins, query price included | High-value operational data |
| Basic | Reduced flat rate | Fixed 30 days | Single-table KQL (+lookup joins to Analytics), billed per GB scanned | Troubleshooting-tier data |
| Auxiliary | Lowest flat rate | Fixed 30 days | Single-table, slowest, per-GB scanned | Verbose/audit streams |

All plans share long-term retention pricing up to ~12 years total; retrieving anything past interactive retention runs asynchronous **search jobs** (billed by GB scanned, results land in a new table). Summary rules pre-aggregate raw tables into compact ones on schedule — the standard pattern for keeping dashboards fast and cheap while raw detail ages into cheaper tiers. Commitment tiers discount Analytics ingestion for steady volume with a 31-day minimum commitment window after any change.

### Application Insights specifics

Workspace-based resources write `App*` tables sharing the workspace's economics. Instrumentation via the OpenTelemetry distro gives traces/metrics/logs/auto-instrumentations (HTTP, SQL, etc.) with W3C trace-context propagation. **Sampling**: adaptive sampling adjusts dynamically toward a target rate (~5 events/sec default class in older SDKs; configurable ceilings), fixed-rate sampling for predictability; crucially metrics are aggregated pre-sample so dashboards stay accurate while individual request traces thin out — the documented failure mode is debugging one specific failed request that sampling discarded. Trace-based log sampling correlates log emission with trace decisions so sampled-out traces take their logs with them (logs outside trace context sample in). **Live Metrics** streams near-real-time without ingestion charges — the outage-time tool. Daily caps stop ingestion at a threshold (data silently dropped afterward — dangerous default-off or misconfigured-on). Availability tests: standard tests replace legacy ping tests (multi-step web app tests retired earlier), executing from multiple Azure geographies with SSL-cert validation and custom headers.

### Alerting architecture

Metric alerts evaluate near-real-time on the metrics store (cheap, reliable, support dynamic thresholds learning seasonality); log alerts run scheduled KQL (expensive at high frequency, powerful for cross-resource semantics) with evaluation frequency vs lookback windows deciding both cost and duplication; activity-log alerts react to control-plane events. Action groups fan out (email/SMS/voice/push/webhook/logic app/ITSM); alert-processing rules implement suppression and routing windows. SLO-shaped design beats threshold sprawl: error-budget burn-rate alerts (fast-burn page, slow-burn ticket) survive contact with reality far better than static CPU thresholds.

### Cost Management mechanics

Cost analysis views slice actual/amortized spend by scope/tag/resource; **budgets** trigger alerts at threshold percentages (or forecast-based) but do NOT enforce caps — enforcement needs Policy/automation layered on top; **cost anomaly detection** profiles daily spend patterns and raises anomalies (spike/dips) with suggested scopes; reservations and savings plans appear properly only under **amortized** views — reading actual-cost views during reservation-heavy months misleads everyone; exports push FOCUS-format CSVs to storage for warehouse-grade FinOps; tags drive attribution but only if Azure Policy enforces tagging at creation (deny untagged, inherit-from-resource-group patterns).

---

## Build it from scratch

A telemetry cost estimator — the arithmetic behind every Log Analytics invoice, and the model to run before choosing table plans:

```python
# untested sketch — telemetry plan/cost estimator: the arithmetic behind the invoice
def monthly_log_cost(gb_per_day: float, plan: str = "analytics",
                     interactive_days: int = 31, ltr_days: int = 0,
                     price_analytics_ingest: float = 2.76,   # ~$/GB, verify current
                     ltr_per_gb_month: float = 0.02) -> float:
    """Analytics-plan baseline: ingestion + long-term-retention storage.
    Basic/Auxiliary swap cheaper ingest for per-GB scan fees at query time."""
    ingest_rate = {"analytics": price_analytics_ingest,
                   "basic": price_analytics_ingest * 0.45,     # ~illustrative ratio
                   "auxiliary": price_analytics_ingest * 0.18}[plan]
    ingest = gb_per_day * 30 * ingest_rate
    # LTR stores everything past interactive retention
    ltr_gb_months = gb_per_day * max(0, ltr_days - interactive_days) / ltr_days * ltr_days
    ltr = gb_per_day * max(0, ltr_days - interactive_days) * ltr_per_gb_month
    return round(ingest + ltr, 2)

if __name__ == "__main__":
    print(monthly_log_cost(50, ltr_days=365))          # 50 GB/day verbose stream
    print(monthly_log_cost(50, plan="auxiliary", ltr_days=2555))  # audit, 7 years
```

Run it against your real GB/day: the exercise shows why routing verbose streams away from Analytics dominates any other optimization — plan selection moves whole invoices, KQL cleverness moves percentages.

## How it's done in production

Reference estate: one workspace per environment per data domain (prod/non-prod split mandatory for access control and cost attribution); OTel distro everywhere with W3C context; DCR transformations dropping debug/health-check noise at ingestion (documented, not ad-hoc); table plans assigned deliberately — Analytics for requests/dependencies/errors, Basic for verbose app traces, Auxiliary for audit streams with multi-year retention; sampling at fixed-rate for prod traces with trace-based log sampling enabled; metric alerts on SLO burn rates plus golden signals (latency/error/saturation/traffic), log alerts reserved for cross-resource semantics at sane frequencies; workbooks as the incident-response surface; budgets per subscription/team with anomaly detection wired to Teams/email via action groups; monthly FinOps review walking amortized views and tag-compliance reports.

| Symptom | Cause | Fix |
|---|---|---|
| Observability bill 5x after container migration | Console logging provider left on; Container Apps exported millions of console rows/day into Log Analytics | Disable console provider in prod; filter health endpoints in DCR transformations |
| Missing error logs during an outage investigation | Daily cap hit — ingestion silently stopped | Alert on cap-near/throttling metrics; treat caps as emergency brakes, not cost controls |
| p99 dashboards fine but users report slowness | Sampling discarded the slow tail's individual traces | Keep metrics unsampled (they are); add targeted full-fidelity capture on error paths; adjust fixed-rate upward where forensics matters |
| Same log alert fired 400 times in minutes | Short evaluation interval + no suppression window | Match evaluation to remediation cadence; alert-processing rules dedupe; migrate to metric alerts where possible |
| Finance can't reconcile invoice against teams | Actual-cost view during reservation-heavy month + untagged resources | Amortized views for reporting; Policy-enforced tagging with inherit-from-RG |
| Queries time out on audit tables | Multi-year Analytics retention queried raw | Move audit streams to Auxiliary/LTR; search jobs on demand; summary rules for trends |

---

## Tradeoffs & when NOT to use it

- **Don't default everything to Analytics plan** — it's the most expensive ingest for a reason: full KQL joins and included query costs belong on high-value operational tables only. Verbose diagnostics on Analytics is the single most common self-inflicted cost wound.
- **Daily caps are not budget tools** — they're silent data-loss switches; using them for cost control produces exactly the missing-evidence-during-incident scenario they were meant to prevent. Real control happens upstream: transformations, plan selection, sampling.
- **Log alerts don't scale to fleet-wide conditions** — high-frequency scheduled KQL across big tables gets expensive and laggy; push numeric signals into custom metrics (via API or summary rules) and alert on those instead. KQL alerts earn their keep on semantic/cross-resource conditions, not volume conditions.
- **Managed Prometheus/Grafana vs App Insights isn't either/or** — Kubernetes-native ecosystems often prefer Prom metrics + Grafana dashboards with App Insights providing distributed tracing; forcing one product everywhere fights each tool's grain. The integration cost of running both is real but usually smaller than the impedance mismatch of not.
- **Centralized mega-workspaces trade cost leverage for blast radius** — one workspace means one RBAC perimeter, shared retention settings, combined quotas, and cross-team noise; the federated pattern (workspace per team/domain, centralized security workspace receiving duplicates) costs more effort and less arguing.
- **Amortized-vs-actual confusion is a governance bug, not a UI preference** — pick amortized for all internal reporting or every reservation purchase looks like a spend spike.

---

## Interview questions

### Q1 — Design the observability stack for 30 microservices on AKS plus PaaS dependencies. What goes where?
**Testing:** end-to-end pipeline design, not tool listing.
**Answer:** OTel distro in each service emitting traces/metrics/logs with W3C propagation; managed Prometheus add-on scraping cluster/service metrics with Grafana dashboards; App Insights wiring traces into `App*` workspace tables for cross-service transaction search; Container Insights for node/pod telemetry; DCRs filtering health/debug noise at ingestion; table plans split by value (Analytics for requests/errors, Basic for verbose traces); diagnostic settings streaming PaaS (SQL, Service Bus) into the same workspace region; unified alerting on SLO burn rates with action groups routed by service ownership tags.
**Follow-up trap:** *"Why both managed Prometheus AND App Insights?"* — Prometheus owns Kubernetes-native metrics ergonomics and ecosystem (recording rules, exporters); App Insights owns distributed tracing correlation across HTTP hops including PaaS dependencies; merging either into the other loses real capability — the cost is two dashboards' worth of context switching.

### Q2 — Explain table plans and assign streams: request telemetry, verbose debug traces, audit events needing 7 years, security logs.
**Testing:** economic-model fluency.
**Answer:** Request/dependency telemetry → Analytics (31 days included interactive, queries free, joins needed). Verbose debug traces → Basic (cheap ingest, 30-day window, single-table scans acceptable for troubleshooting). Audit events → Auxiliary with long-term retention extended toward years (cheapest ingest, slow queries acceptable, search jobs when auditors come knocking). Security logs → Analytics if Sentinel operates (90-day inclusion, alerting needs), with LTR beyond. The principle: match plan to query-frequency × query-richness, then let LTR absorb compliance depth cheaply.
**Follow-up trap:** *"What breaks moving a busy table from Analytics to Basic?"* — loss of multi-table joins (only lookups to Analytics tables remain), per-GB scan charges on heavy queries, fixed 30-day interactive window, and alerting restrictions — dashboards hitting that table start billing visibly and some queries stop working outright.

### Q3 — How does adaptive sampling interact with your ability to debug incidents? What do you configure instead?
**Testing:** sampling theory applied operationally.
**Answer:** Adaptive sampling thins individual telemetry toward a rate target while preserving aggregated metric accuracy — so dashboards stay truthful while per-request forensics loses exactly the outliers you need post-incident (slow tails, rare failures get sampled out proportionally to their rarity). Configure: fixed-rate sampling sized to retain meaningful percentages under peak load; trace-based log sampling keeping logs/traces consistent; full-fidelity capture on error paths (sampling exceptions differently from successes); Live Metrics for real-time un-sampled windows during active incidents; and acceptance that finding "that one request" requires its trace-id surfaced to clients so you can hunt it in whatever survived.
**Follow-up trap:** *"Why not just disable sampling?"* — ingestion economics scale linearly with traffic; disabling sampling converts your best days directly into your worst invoices, and high-volume traces degrade query performance for everyone — the fix is targeted fidelity, not zero sampling.

### Q4 — A latency incident hits. Walk the App Insights path from symptom to root cause.
**Testing:** operational fluency under the pressure scenario.
**Answer:** Availability/performance blade confirms scope and geography spread; end-to-end transaction details on failing operations show the dependency waterfall — which downstream call stretched; Application Map aggregates which edge degraded; failures tab filters by dependency vs exception type; Live Metrics validates whether it's ongoing; KQL over `AppDependencies`/`AppRequests` quantifies p95 deltas correlated by region/version/deployment slot; trace correlation follows one request-id through services to the blocking call (SQL wait? external API? thread-pool starvation visible in custom dimensions?). Root cause discipline: correlate deployment timeline before blaming code — platform upgrades and config changes explain half of "mystery" latency.
**Follow-up trap:** *"Sampling removed the slowest requests — how do you still quantify them?"* — metrics recorded pre-sample (aggregates include everyone): percentile metrics, failure counts, and custom histograms stay exact; combine those numbers with surviving exemplars rather than claiming the sample distribution is the truth.

### Q5 — Design alerting that survives contact with a real on-call rotation.
**Testing:** alert-fatigue literacy — where most monitoring designs actually fail.
**Answer:** SLO-first: define user-facing SLIs, page on fast error-budget burn (e.g., >2% budget/hour), ticket on slow burn (>5%/week) — pages always actionable within minutes. Golden-signal thresholds tuned from measured baselines, dynamic thresholds where seasonality exists. Suppression windows matched to remediation cadence; maintenance windows via alert-processing rules; routing by ownership metadata so pages reach owners not channels. Kill criteria reviewed quarterly: any alert that fired without action twice gets deleted or demoted. Log alerts restricted to genuinely semantic conditions at minute-plus frequencies.
**Follow-up trap:** *"Your burn-rate alert fired during a planned migration — false positive?"* — no: planned work consuming user-facing error budget is exactly what burn-rate alerting should catch; the correct response is pre-declaring the SLO pause window (with approval trail), not exempting deployments from measurement.

### Q6 — Explain Azure Monitor cost levers in priority order for a team spending too much on Log Analytics.
**Testing:** practical FinOps sequencing inside observability specifically.
**Answer:** 1) Route streams by value — move verbose/audit tables off Analytics to Basic/Auxiliary (largest lever, structural). 2) Filter at ingestion via DCR transformations (drop known-noise fields/rows; watch the >50%-filtered processing fee threshold). 3) Sample traces/logs appropriately. 4) Right-size interactive retention (don't pay extended interactive rates for data queried monthly — LTR covers compliance). 5) Commitment tiers once volume stabilizes. 6) Summary rules powering dashboards from aggregates instead of raw scans. Never lead with caps (data loss) and never optimize before attributing (tag first or you optimize blind).
**Follow-up trap:** *"Which lever is most commonly misused?"* — daily caps as a cost control: bills drop, evidence vanishes, and the outage postmortem pays back tenfold; caps belong behind change-control as incident brakes only.

### Q7 — Cost Management: budgets vs anomaly detection vs reservations — what does each actually do and what doesn't it do?
**Testing:** precision about enforcement gaps that surprise teams.
**Answer:** Budgets: threshold-triggered notifications (percentage or forecast-based) — they notify, never enforce; enforcement requires Policy (deny/modify) or automation reacting to budget events. Anomaly detection: ML profiling of daily spend raising anomalies with suggested scopes — reactive signal, good for catching runaway resources early. Reservations/savings plans: commitment discounts appearing correctly only in amortized views; utilization metrics tell you whether commitments fit actual consumption. Exports/FOCUS feeds feed external FinOps tooling. The design error: treating any of these as guardrails rather than instruments — guardrails live in Policy (allowed SKUs, tag requirements, region constraints).
**Follow-up trap:** *"Budget alerted, nobody acted, bill doubled — what failed?"* — the operating model: budget events must route into actionable workflows (owner-tagged, escalation ladder, runbook links), otherwise they're calendar spam; wire action groups to ownership metadata set by Policy.

### Q8 — Tag governance for chargeback: how do you make it actually stick?
**Testing:** governance mechanics versus aspiration.
**Answer:** Policy assignments: deny creation of resources missing required tags (env, owner, cost-center); append/inherit patterns stamp resource-group tags onto children automatically; modify effect retro-fixes existing resources where possible; exemption workflow for exceptions (shared platform resources) documented centrally. Validate continuously: tag-compliance dashboards from Resource Graph queries feeding the same FinOps reviews; exports sliced by tags reconcile against invoices monthly. Drift happens when policies allow exceptions silently — every exemption appears on the compliance dashboard with an expiry date.
**Follow-up trap:** *"Shared platform resources serve five teams — how attribute?"* — metered attribution below resource granularity: usage-based allocation (API calls, GB stored, vCPU-hours from utilization telemetry) apportioned by agreed keys; imperfect but far better than splitting evenly, and the argument about fairness surfaces once in design rather than every month-end.

### Q9 — When would you choose managed Prometheus/Grafana over App Insights-native monitoring entirely?
**Testing:** honest ecosystem-fit judgment.
**Answer:** Choose Prom/Grafana-centric when: the org standardizes on Grafana across clouds, existing Prometheus exporters/recipes cover your stack, alerting lives in Alertmanager workflows already, and OpenTelemetry collector pipelines export metrics there — App Insights becomes optional tracing layer or drops out. Stay App Insights-native when: deep Azure integrations matter (availability tests, workbooks, Microsoft support path), teams want lowest-moving-parts PaaS experience, or .NET auto-instrumentation covers everything. Hybrid is the realistic default; choosing one exclusively is defensible only when team topology strongly favors it.
**Follow-up trap:** *"What's the hidden cost of hybrid?"* — dual cardinality/dimension models, two alert languages, and correlation glue (exemplars linking Grafana panels to traces); mitigate with shared naming conventions and linked dashboards, or accept context-switching as the tax.

### Q10 — Your KQL queries over billions of rows take minutes. Optimize systematically.
**Testing:** query-engine craft.
**Answer:** Time-filter first (`TimeGenerated` range narrows partitions before anything else); project early to needed columns (columnar store rewards narrow scans); summarize/filter before joins; avoid `contains` on wide text where `has`/exact operators work; materialize hot aggregates via summary rules into small tables dashboards query; use `hint.shuffle`/broadcast strategies deliberately for large joins; check for accidental cross-workspace fan-outs. Structural fix beats query golf: route that workload's raw data to cheaper plans and query summaries — minutes-long interactive queries are an architecture smell, not a tuning problem.
**Follow-up trap:** *\"Query is fast for yesterday, times out for 90 days.\"* — partition pruning: 90-day ranges scan vastly more storage nodes; break into batched windows, or better, accept that 90-day interactive analytics belongs in a warehouse/lakehouse copy, not the log store.

### Q11 — Design availability monitoring for a public endpoint with login flow, respecting modern test capabilities.
**Testing:** currency on availability-test changes plus synthetic-flow thinking.
**Answer:** Standard tests (replacing retired ping/multi-step tests) from multiple geographies: validate TLS expiry, custom headers, status codes, content matching on critical endpoints; authenticated flows via certificate/request-level auth rather than scripted browser replay where possible; TrackAvailability calls instrument deeper flows from worker code (custom synthetic executing business transactions and recording availability telemetry with durations). Alerts on availability percentage over sliding windows with geo-granularity to distinguish regional network issues from application faults; separate synthetic traffic in analytics via known headers/user-agents so dashboards exclude it.
**Follow-up trap:** *"Synthetic passes, users still broken."* — synthetics test happy-path reachability from Azure POPs, not user reality: third-party scripts, regional ISP issues, client-side rendering. Layer RUM (real-user telemetry the OTel browser SDK provides) beneath synthetics and alert on divergence between the two.

### Q12 — Rank these ops failures by frequency: uncontrolled log ingestion costs, sampling-blind forensics, alert fatigue misses, cap-induced evidence loss. Justify.
**Testing:** prioritization grounded in how observability systems actually fail.
**Answer:** 1) Ingestion cost creep — grows silently with every new service/console-log regression; discovered at invoices, affects everyone eventually. 2) Alert fatigue — accumulates gradually until the one real page drowns; hardest to notice from inside because each individual alert seems justified. 3) Sampling-blind forensics — bites during incidents but only when debugging rare/outlier behavior. 4) Cap-induced evidence loss — rarest but most catastrophic per event, and increasingly avoided as teams learn caps aren't cost tools. Frequency ordering again inverts severity — governance (plans, budgets, alert hygiene reviews) addresses all four structurally.
**Follow-up trap:** *"Which single practice prevents most?"* — monthly telemetry review pairing cost dashboards with alert-fire statistics: cost creep shows up as trend lines, alert noise as fire-count-per-rule — fifteen minutes a month catches what quarters of firefighting miss.

---

## Red flags that fail you

- Recommending daily caps as a primary cost-control mechanism.
- Not knowing Analytics includes ~31 days (90 with Sentinel/App Insights) while Basic/Auxiliary are fixed 30.
- Claiming sampling makes metrics inaccurate (metrics aggregate pre-sample).
- Legacy answers: MMA agent, ping tests, classic App Insights resources as current recommendations.
- No distinction between budget alerts and actual spend enforcement.
- Log alerts at sub-minute frequency across huge tables as a scaling strategy.
- Treating amortized and actual cost views as interchangeable for reporting.
- Console logging enabled in production with no ingestion-noise story.

---

## Cheat card

```
PIPELINE: sources -> AMA agent / OTel distro / diagnostic settings
          -> DCR (transformations at ingest; >50% filtered = extra fee)
          -> Log Analytics tables · platform metrics free ~93 d

TABLE PLANS: ANALYTICS = full KQL, queries incl., 31 d incl. (90 Sentinel/AI),
             interactive extendable to 2 y · BASIC = cheap ingest, 30 d fixed,
             single-table + lookups, billed per GB scanned · AUXILIARY =
             cheapest, slowest, audit-grade · ALL -> LTR up to ~12 y,
             retrieval via SEARCH JOBS (per-GB scanned) · summary rules
             pre-aggregate · commitment tiers: 31-day min commitment

APP INSIGHTS: workspace-based, AppRequests/AppTraces/AppDependencies tables
  OTel distro = instrumentation standard (W3C ctx, auto-instrumentation)
  ADAPTIVE SAMPLING thins traces NOT metrics (metrics aggregate pre-sample)
  trace-based log sampling keeps logs+traces consistent
  Live Metrics = near-real-time, no ingestion charge · daily cap = silent
  data loss (emergency brake ONLY) · standard availability tests replaced
  ping/multi-step tests

ALERTS: metric rules (near-real-time, dynamic thresholds) > log rules
        (scheduled KQL, expensive) · action groups fan out · processing
        rules suppress/route · DESIGN: SLO burn-rate (fast=page, slow=ticket)

COST MGMT: budgets ALERT ONLY, never enforce (Policy enforces) ·
  anomaly detection = ML on daily spend · AMORTIZED view for reservation/
  savings-plan truth · FOCUS exports · tag governance via Policy deny+
  inherit · levers order: stream routing > transform-filter > sampling >
  retention right-size > commitment tiers > summary rules

KQL SPEED: TimeGenerated filter FIRST · project early · summarize before join
           has > contains · hot aggregates via summary rules
DEBUG PATH: availability -> e2e transaction waterfall -> app map -> failures
            tab -> KQL percentiles by version/region -> trace-id follow
```

## Sources

- [Azure Monitor Logs cost calculations and options — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/cost-logs); accessed 2026-08-23
- [Azure Monitor pricing — Microsoft Azure](https://azure.microsoft.com/en-us/pricing/details/monitor/); accessed 2026-08-23
- [Azure Monitor Logs overview: platforms and table plans — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-platform-logs); accessed 2026-08-23
- [Tables in Azure Monitor Logs — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-table-overview); accessed 2026-08-23
- [Optimizing cost using the Azure Monitor OpenTelemetry Distro — Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azureobservabilityblog/optimizing-cost-using-the-azure-monitor-opentelemetry-distro/4115870); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
