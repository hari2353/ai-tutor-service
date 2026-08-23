# GCP Ops Deep: Cloud Logging, Monitoring, Trace, and FinOps

> **Track:** C-GCP Google Cloud Atlas · **Time:** 1.5h · **Prereqs:** any C-GCP service module · **Updated:** 2026-08-23
> **Module id:** `C-GCP-ops` · **Tags:** ops

## The 30-second version

GCP's observability stack is three services sharing one billing surface: **Cloud Logging** ingests structured entries through the Log Router into buckets — `_Required` keeps Admin Activity audit logs for a fixed 400 days free, `_Default` holds everything else for 30 days (configurable 1–3,650), ingestion costs ~$0.50/GiB after 50 GiB/project/month free, and retention past 30 days adds $0.01/GiB/month, which is why exclusion filters are the highest-leverage cost control in the entire stack. **Cloud Monitoring** turns metrics into SLOs with error budgets and multi-window burn-rate alerts (the SRE-book pattern implemented natively, MQL for queries, dashboards-as-code). **Cloud Trace** ingests spans via OpenTelemetry with a free span allotment, correlating traces to logs for incident work. **FinOps** on GCP is discount-stack arithmetic (Spot > committed use > sustained use, covered in the compute module) plus billing export to BigQuery making spend queryable like any other data — budget alerts at 80% catch surprises before invoices do. The interview core: can you design an observability estate that stays affordable at scale (exclusions, tiered retention, sampling) and explain SLO-based alerting instead of threshold folklore?

## Why this gets asked

Because observability bills are where good intentions meet line items: teams enable everything, discover load-balancer access logs are half their volume, and pay five figures monthly for logs nobody reads. Interviewers who run estates probe whether you know the actual cost mechanics (ingestion versus storage versus retention are separate meters; `_Required` is free and immutable) and whether you've designed alerts that page on *user impact* rather than CPU numbers — the SLO burn-rate pattern exists precisely because static thresholds either cry wolf or sleep through real incidents. On the FinOps side, the question underneath is cultural: is spend visible per-team/per-feature with owners, or a monthly org-wide shock? Candidates who answer "we look at the console bill" fail; candidates who describe BigQuery billing export, labeled attribution, and budget automation pass.

---

## Lineage: past → present → future

**What came before.** Stackdriver launched in 2012 as an independent startup doing monitoring/logging for clouds generally; Google acquired it in 2014 and spent years integrating it until the 2020-ish rebrand to Google Cloud Operations, then split naming into Cloud Logging/Monitoring/Trace/Profiler under "Google Cloud Observability." The pre-Stackdriver world was per-service consoles and SSH-plus-grep; the pain that killed it was cross-service correlation being manual archaeology during incidents. The SRE movement (Google's own books, 2016 onward) supplied the conceptual layer — SLIs/SLOs/error budgets — that Monitoring then productized natively rather than leaving to add-ons like every other cloud.

**Where it stands now.** Current mechanics worth knowing precisely: Log Router evaluates every entry against all sinks (one entry can go many places — and bill multiple times); Log Analytics enables SQL queries directly over log buckets linked to BigQuery datasets without routing copies; OpenTelemetry has become the instrumentation standard with managed collection; dashboards/alerts/SLOs are all Terraform-manageable resources. Alerting pricing was announced to arrive no sooner than September 2027 (~$0.35/month per metric reference plus per-point query charges ~) — a future cost signal worth tracking but not yet live. Live disagreement: centralized shared observability projects versus per-team projects — central logging simplifies cross-team queries and IAM but concentrates cost ownership disputes; both patterns exist at scale and the honest answer names the tradeoff.

**Where it's heading.** High confidence: AI-assisted incident work (log summarization, anomaly explanation) embedding into the consoles — Gemini integration already appears across the surfaces; expect assist features to become default rather than opt-in. High confidence: FinOps tooling maturing toward automated commitment recommendations executed via APIs (slot advisors, CUD analyzers exist today in suggestion form). Medium confidence: OpenTelemetry absorbing vendor-specific agents entirely until "GCP agent" means OTel config presets. Speculative: autonomous remediation closing the loop from alert to action without humans — treat current offerings as runbook-assist, not autonomy.

## Mental model

Telemetry flows one way with cost meters at each stage:

```
SERVICE (structured logs / metrics / OTel spans)
   |
   v
LOG ROUTER -- evaluates EVERY entry against EVERY sink
   |-- _Required sink -> _Required bucket: audit logs, 400 days, FREE, immutable
   |-- _Default sink  -> _Default bucket: 30 days free-ish
   |      ^-- EXCLUSION FILTERS live here: the #1 cost lever
   |-- custom sinks -> custom buckets (1-3650 days), GCS, BigQuery, Pub/Sub
   |                    (routing to N destinations bills storage N times!)
   v
COST METERS: ingestion ~$0.50/GiB (first 50 GiB/project/mo free)
             retention $0.01/GiB/mo beyond 30 days
             vended network logs ~$0.25/GiB separate (~)

ALERTING LADDER (SRE pattern):
  SLI (measured ratio) -> SLO (target) -> error budget ->
  burn-rate alert: fast window catches spikes, slow window confirms trends
  e.g., page when 1h burn >=14.4x AND 5m burn >=14.4x; ticket when 6h>=6x AND 30m>=6x
```

## How it actually works

### Cloud Logging mechanics

Entries are structured JSON (`LogEntry`: payload, severity, resource type, labels) matched to monitored resource types (`gce_instance`, `cloud_run_revision`, `k8s_container`). The **Log Router** runs sinks in every project/folder/org; sink filters use the logging query language; destinations: log buckets (queryable in Log Explorer/Analytics), Cloud Storage (cheap archive), BigQuery (SQL analysis), Pub/Sub (streaming to external SIEM). Two defaults exist everywhere: `_Required` (Admin Activity + System Event audit logs, 400 days, cannot modify or disable, free) and `_Default` (everything else unless excluded, 30 days, retention configurable 1–3,650 days at project level). Shortening retention triggers a 7-day grace period where expired logs become unqueryable but restorable. Log Analytics links buckets to BigQuery for SQL without duplicating storage — the compliance-analysis path that avoids double billing.

Cost control hierarchy, highest leverage first:

1. **Exclusion filters** on `_Default`: health-check access logs often exceed half of volume; GKE system namespace info-level logs and LB 2xx access lines follow.
2. **Routing tiering**: application logs stay in buckets for query windows; compliance-relevant copies go to GCS/BigQuery long-term instead of extended bucket retention.
3. **Sampling** extreme-volume debug streams at write time.
4. Retention tuning per bucket — not everything needs 30+ days online.

### Monitoring: SLOs and burn-rate alerts

SLI = measured ratio of good events (availability from request counts, latency as share under threshold). SLO = target over a compliance period (rolling 7/28-day typical). Error budget = allowed bad fraction; burn rate = consumption speed relative to plan. The multi-window multi-burn-rate pattern pairs a fast detection window with a longer confirmation window so alerts fire on genuine fast burns (page) versus slow erosion (ticket): classic parameters page at 14.4× burn over 1h-with-5min confirmation, ticket at 6× over 6h (~). MQL (Monitoring Query Language) expresses ratio computations natively; dashboards and alert policies are versionable Terraform resources — treat console drift like IAM drift. Uptime checks and synthetic monitors extend black-box coverage (synthetics bill past ~100 executions/month/account free ~).

### Trace and OpenTelemetry

Spans arrive via OTel SDKs/auto-instrumentation through the managed collector; Trace stores them (free allotment ~5M spans/billing-account/month, then per-million charges ~), correlates trace IDs into log entries, and powers latency breakdowns across service hops. The practical discipline: propagate context end-to-end (W3C traceparent headers), sample deliberately (head-based for volume control, tail-based to keep erroring/slow traces), and keep span cardinality bounded — unbounded label values (user IDs as span attributes) destroy both query performance and cost models.

### FinOps on GCP

Mechanics: **billing export** streams line items to BigQuery continuously — spend becomes SQL like any dataset. Attribution via labels/projects enforced by org policy; budgets with threshold alerts (50/80/100%) wired to Pub/Sub for automation. Discount stack (compute module details it): Spot for interruptible, CUD commitments on measured baselines, SUD automatic. Service-specific levers recur across modules: BigQuery bytes-vs-slots crossover, log exclusions, Autopilot request rightsizing. The operating rhythm that separates real FinOps from bill-watching: weekly top-movers review, monthly commitment decisions, quarterly architecture-level reviews — all against exported data, none against console vibes.

## Build it from scratch

The observability baseline every estate needs, minimal commands:

```bash
# 1. Kill the #1 log cost: health-check noise in _Default
gcloud logging sinks update _Default --project=prod \
  --add-exclusion='name=no-healthchecks,filter=httpRequest.requestUrl="/healthz"'

# 2. Tier compliance logs: audit data-access -> 1yr bucket
gcloud logging buckets create security-logs --location=global \
  --retention-days=365 --project=prod
gcloud logging sinks create audit-sink security-logs \
  --logging-filter='logName:"cloudaudit.googleapis.com%2Fdata_access"'

# 3. Budget alert wired to Pub/Sub for automation
gcloud billing budgets create --billing-account=BILLING_ID \
  --display-name="prod-monthly" --budget-amount=20000USD \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.8,spend-basis=current-spend

# 4. SLO + burn-rate alert as code (Terraform-shaped sketch)
# google_monitoring_slo { service "api" ; availability 99.9% rolling 28d }
# alert_policy: condition monitoring.googleapis.com/v3/projects/.../slo
#   burn_rate_threshold 14.4 over 1h AND 5m  -> PAGE
#   burn_rate_threshold 6.0  over 6h AND 30m -> TICKET
```

A spend-attribution query on the exported bill:

```sql
-- untested sketch - top movers week-over-week from billing export
SELECT service.description AS svc,
       SUM(CAST(cost AS NUMERIC)) AS spend,
       ANY_VALUE(project.labels)  AS who_owns_it
FROM `proj.billing.gcp_billing_export_v1_x`
WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY svc ORDER BY spend DESC LIMIT 20;
```

## How it's done in production

Reference estate: centralized observability project holding log buckets and dashboards, with per-team projects routing into it via aggregate sinks; exclusion filters reviewed quarterly against volume reports; SLOs defined per user-facing service (RED method) with burn-rate paging tied to an on-call rotation; error-budget policy written down — budget exhausted means feature freeze until reliability work lands; OTel instrumentation standardized via a shared library so trace context propagates uniformly; FinOps runs the weekly top-movers review from BigQuery export, monthly commitment adjustments, and labels enforced at deploy time.

| Symptom | Cause | Fix |
|---|---|---|
| Logging bill five figures monthly | Unfiltered access/system logs ingesting everything | Exclusion filters first; volume-by-log-name report; tiered retention |
| Alerts page nightly, nobody trusts them | Static CPU/memory thresholds | Replace with SLI/SLO burn-rate alerts on user impact |
| Incident took hours; logs were there but unfindable | No trace-log correlation or structured payloads | OTel trace IDs in log entries; enforce structured JSON schemas |
| Error budget burned but no one noticed | SLOs defined, no burn alerts or policy | Multi-window burn-rate alerts; documented budget policy |
| Month-end bill surprise | No budgets/attribution; console-only visibility | Billing export to BigQuery, labels enforced, budget alerts at 50/80% |
| Traces exist but gaps across services | Context propagation missing between hops | W3C traceparent propagation in shared libraries; verify per hop |

## Tradeoffs & when NOT to use it

- **Don't centralize all logs into one project blindly** — cross-team queries get easy; cost ownership gets political and IAM blast radius widens. Aggregate sinks to a shared analytics bucket while keeping team-owned ingestion is the common middle path.
- **Don't keep everything queryable** — Log Explorer convenience tempts 365-day retention on debug noise; archive tiers (GCS) serve compliance without online-query pricing.
- **Burn-rate alerting isn't free of tuning** — wrong window pairs either duplicate pages (fast windows too sensitive) or late detection (confirmation too long); tune against incident history, not defaults alone.
- **SLOs on everything dilute focus** — define them where users feel failure (checkout, auth, core APIs); internal batch jobs get simpler alerting.
- **FinOps tooling doesn't replace ownership** — exports and advisors surface waste; someone must own each line item or the review ritual decays into calendar theater.

## Interview questions

### Q1 — Your GCP logging bill is $30k/month. Walk me through your first week of fixes.
**Testing:** cost mechanics plus prioritization instinct.
**Answer:** Day 1: volume-by-log-name report — offenders are usually LB access logs, health checks, GKE system info lines, debug app logs. Days 1–2: exclusion filters on `_Default` for health checks and sub-WARNING system logs (often 40–60% volume cut immediately, ~). Day 3: tier retention — compliance copies to BigQuery/GCS rather than extended bucket retention ($0.01/GiB/month beyond 30 days compounds); application logs keep queryable incident windows only. Days 4–5: budget alerts at 50/80% so regressions page someone; per-team log schemas so debug verbosity is a deploy-time decision.
**Follow-up trap:** *"Why not just route everything to GCS?"* — routing stops ingestion billing but loses Log Explorer queryability; the pattern is hot-in-buckets for incident windows, cold-in-GCS for compliance. Routing one entry to multiple destinations also bills storage multiple times.

### Q2 — Explain SLO-based alerting end to end: SLI, error budget, burn rate, multi-window logic.
**Testing:** SRE literacy separating platform engineers from dashboard tourists.
**Answer:** SLI measures good-over-total events (availability ratio, latency-under-threshold share). SLO sets the target; error budget is the complement; burn rate is consumption speed versus plan. Multi-window pairs fast detection with confirmation: page when 1h burn ≥14.4× AND 5m ≥14.4× (catches spikes, suppresses blips); ticket when 6h ≥6× AND 30m ≥6× (~). Replaces static thresholds that cry wolf or miss slow degradation entirely.
**Follow-up trap:** *"Why 14.4 specifically?"* — arithmetic: 14.4× sustained burn exhausts a 28-day 99.9% budget in roughly an hour; constants derive from budget-exhaustion math in Google's SRE workbook. The derivation matters more than memorizing the number.

### Q3 — What can and cannot be changed about the default log buckets?
**Testing:** foundational mechanics people get wrong constantly.
**Answer:** `_Required`: Admin Activity/System Event audit logs plus Access Transparency, fixed 400-day retention, free, cannot be modified or disabled. `_Default`: 30 days default; project-level retention configurable 1–3,650 days; exclusion filters keep entries out entirely; shortening retention gives a 7-day grace period (expired logs unqueryable but restorable by extending again). Folder/organization-level `_Default` isn't configurable — aggregate sinks into project buckets are the standard workaround.
**Follow-up trap:** *"Delete audit logs to save space?"* — Admin Activity logs are non-configurable by design and free anyway; the chargeable ones are data-access audit logs, controlled via sinks/exclusions.

### Q4 — Design observability for a new microservice before its first production request.
**Testing:** designed-in versus bolted-on instinct.
**Answer:** Shared OTel library: RED metrics per endpoint, W3C trace propagation, structured JSON logs carrying trace IDs. SLIs/SLOs from product requirements with burn-rate alerts wired to on-call. Dashboards-as-code committed beside the service. Log schema documented; health-check paths excluded at the sink. Budget alerts on projected spend. The acceptance test: could a stranger diagnose at 3am from telemetry alone?
**Follow-up trap:** *"Which single artifact first?"* — the SLO definition with its owner. Everything follows from defined failure semantics; instrumentation without them produces dashboards nobody acts on.

### Q5 — How does billing export to BigQuery change FinOps practice?
**Testing:** tooling-plus-process versus console screenshots.
**Answer:** Line items stream continuously into a dataset: top movers week-over-week, label/project attribution, commitment coverage analysis become SQL. That enables automation (budget alerts to Pub/Sub triggering scaling caps), accountability (teams see labeled spend), and commitment decisions from measured baselines. With labels enforced mechanically via org policy/pipeline validation, attribution stops being archaeology.
**Follow-up trap:** *"Labels rot — enforcement?"* — reject unlabeled resources at deploy time via custom constraints; reconcile unattributed spend periodically. Human diligence decays; mechanical gates don't.

### Q6 — Traces exist but spans break between services. Debug systematically.
**Testing:** tracing mechanics depth.
**Answer:** Context propagation breaks somewhere: verify `traceparent` passes each hop (LBs/proxies stripping unknown headers are classic); async boundaries need trace metadata embedded in messages; check instrumentation version mismatches; confirm samplers aren't orphaning children by dropping parents. Managed collection accepts OTLP; mixed vendor agents cause attribute gaps.
**Follow-up trap:** *"Sampling kills rare-bug traces?"* — head-based sampling drops interesting traces randomly; tail-based sampling keeps slow/error traces while cutting healthy volume, trading collector buffering. Critical paths land on tail-based in serious estates.

### Q7 — What's coming for Cloud Monitoring alerting pricing, and how should teams prepare?
**Testing:** currency on the observability cost surface.
**Answer:** Google announced alerting charges arriving no sooner than September 2027 (~$0.35/month per metric reference in a policy plus per-point query charges ~) — currently free. Preparation: audit policy sprawl (dead policies referencing metrics), consolidate duplicate conditions, prefer log-based metrics where they collapse several metric references into one, and model post-pricing spend from current policy counts before it lands.
**Follow-up trap:** *"Should we pre-emptively delete alert policies?"* — no: alert coverage is cheap insurance today and the pricing is future-dated with contract grandfathering windows (~). Audit and consolidate for hygiene, not panic; deleting working alerts to dodge a 2027 charge is optimizing the wrong thing.

### Q8 — A service's SLO compliance looks green but users complain constantly. What's wrong?
**Testing:** SLI-design depth — the difference between measuring the system and measuring user experience.
**Answer:** The SLI probably measures the wrong plane: uptime checks hitting `/healthz` pass while real requests fail behind auth/DB paths; or latency measured server-side excludes client-perceived time (network, TLS, rendering); or the SLO window averages away recurring bad periods (daily batch storms inside a green weekly average). Fix: define good requests from the client's seat — synthetic transactions through real flows, per-endpoint SLIs rather than one global ratio, shorter rolling windows alongside long ones.
**Follow-up trap:** *"'Green SLO but angry users' — ever legitimate?"* — yes when complaints come from a segment outside measurement (one region, one client version, one tenant). Slice SLIs by dimensions that matter before assuming the number lies; then fix the slicing.

### Q9 — Compare centralized versus per-team observability projects.
**Testing:** estate-design judgment with honest tradeoffs.
**Answer:** Centralized: cross-service queries trivially easy, single IAM/cost surface, consistent retention policy — costs: one team becomes bottleneck for access, cost attribution blurs, blast radius of misconfiguration grows. Per-team: autonomy and clean billing — costs: cross-service incident archaeology needs sink aggregation anyway, tooling duplicates. Common resolution: teams own ingestion and dashboards; aggregate sinks copy production logs into shared buckets scoped by log views/analytics views for cross-cutting queries.
**Follow-up trap:** *"Who pays the shared bucket?"* — chargeback by routed volume share from sink metrics, or platform-team budget with showback reporting. Deciding this *before* adoption prevents the political stall that kills centralization projects.

### Q10 — Design the error-budget policy for a payments API at 99.95% availability.
**Testing:** whether SLOs connect to engineering behavior, not just dashboards.
**Answer:** Budget math: 99.95% over 28 days ≈ ~20 minutes allowed downtime-equivalent. Policy: budget burn >50% in a week triggers reliability review; >90% freezes feature deploys except reliability fixes until under threshold; burn-rate pages override feature work immediately. Every page links to budget impact so prioritization debates have numbers. Quarterly: revisit the target itself — if budgets never exhaust, the SLO may be too loose to drive anything; if always exhausted, either architecture or target needs changing.
**Follow-up trap:** *"Product refuses the freeze."* — the policy only works with pre-agreed executive sponsorship; document the escalation path when signing the SLO. An error-budget policy without teeth is a dashboard decoration — say that out loud in design reviews.

### Q11 — What does "structured logging" actually buy over println logs, concretely?
**Testing:** fundamentals check disguised as an ops question.
**Answer:** Structured entries become queryable fields: filter by severity/user/request-id without regex archaeology; log-based metrics derive alertable counters from entries; sinks route subsets precisely; BigQuery analysis runs SQL over payload fields; trace-ID correlation joins logs to spans mechanically. Unstructured logs pay ingestion identically but return a fraction of the value — same $0.50/GiB, less signal. Enforce schemas via logging libraries and CI linting, not convention.
**Follow-up trap:** *"Cost of structure?"* — slightly larger payloads (field names repeated) plus schema-maintenance discipline; mitigate with sensible field naming and excluding high-cardinality noise from labels. The ROI question is signal-per-GiB, which structure raises dramatically.

## Red flags that fail you

- Not knowing `_Required` (400 days, free, immutable) versus `_Default` (30 days, configurable).
- Treating log ingestion, storage, and retention as one bill — they're separate meters.
- Alerting on CPU/memory thresholds instead of SLI burn rates for user-facing services.
- No answer for observability cost control beyond "we delete old logs."
- FinOps described as monthly bill review rather than exported-data-driven automation.
- Claiming traces work without deliberate context propagation across every hop.
- Defining SLOs with no error-budget policy behind them.

---

## Cheat card

```
LOGGING:  Log Router evaluates every entry against every sink
          _Required: admin/system audit logs, 400d, FREE, immutable
          _Default: 30d default, configurable 1-3650d (project level);
                    shorten -> 7-day grace period (unqueryable, restorable)
          sinks -> buckets | GCS | BigQuery | Pub/Sub; N destinations = N x storage
          COSTS: ingestion ~$0.50/GiB (first 50 GiB/proj/mo free);
                 retention $0.01/GiB/mo >30d; vended network logs ~$0.25/GiB (~)
          #1 lever: exclusion filters on _Default (health checks = huge share)
          Log Analytics: SQL over buckets via BQ link w/o duplicate storage

MONITORING: SLI (good/total) -> SLO (target) -> error budget ->
          burn rate = consumption speed vs plan
          multi-window multi-burn-rate: page 1h>=14.4x AND 5m>=14.4x;
          ticket 6h>=6x AND 30m>=6x (~); 14.4x exhausts 28d budget in ~1h
          MQL for ratios; dashboards/alerts/SLOs all Terraform resources
          alerting pricing announced no-sooner-than Sep 2027 (~)

TRACE:    OTel SDKs -> managed collector; ~5M spans/billing-acct/mo free (~)
          W3C traceparent propagation everywhere; head vs tail sampling
          (tail keeps slow/error traces); bound span label cardinality

FINOPS:   billing export -> BigQuery = spend is SQL; budgets 50/80/100% alerts
          -> Pub/Sub automation; labels enforced at deploy time (org policy)
          discount stack: Spot > CUD commitments > automatic SUD
          rhythm: weekly top-movers, monthly commitment review, quarterly arch

POLICY:   error-budget exhaustion -> documented consequence (freeze/review)
          or the SLO is decoration. SLO owner named before instrumentation.
```

## Sources

- [Configure log buckets — Cloud Logging docs](https://docs.cloud.google.com/logging/docs/buckets); accessed 2026-08-23
- [Quotas and limits — Cloud Logging docs](https://docs.cloud.google.com/logging/quotas); accessed 2026-08-23
- [Google Cloud Observability pricing](https://cloud.google.com/products/observability/pricing); accessed 2026-08-23
- [Setting up log retention policies per bucket — OneUptime guide](https://oneuptime.com/blog/post/2026-02-17-how-to-set-up-log-retention-policies-for-different-log-buckets-in-cloud-logging/view); accessed 2026-08-23
- [Cloud Logging and Monitoring usage and pricing optimization guide](https://cloudtoolstack.com/learn/gcp-cloud-logging-monitoring-guide); accessed 2026-08-23
- [Google Cloud Logging usage and pricing optimization — Astrafy](https://astrafy.io/blog/google-cloud-logging-complete-guide-on-usage-and-pricing-optimization); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
