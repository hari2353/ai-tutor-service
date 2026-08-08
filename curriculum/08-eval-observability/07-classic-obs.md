# RED/USE, SLO/SLI/Error Budgets, Prometheus/Grafana, Alert Design

> **Track:** T08 Eval & Observability · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T08-classic-obs` · **Tags:** observability

## The 30-second version

RED (rate, errors, duration) and USE (utilization, saturation, errors) are not two flavors of the same idea — they watch different subjects. RED describes anything that serves discrete requests; USE describes any finite resource pool, and a system can look perfectly healthy on one axis while failing on the other, which is why both belong on a dashboard, not just whichever one the team learned first. An SLO turns a monitoring number into a business decision: 99.9% availability over a 30-day month buys exactly 43.2 minutes of allowed downtime, 99.95% buys 21.6 minutes, and an error-budget policy that freezes feature releases once that budget is spent is what actually connects a percentage on a dashboard to release cadence — without that policy, an SLO is just a number nobody acts on. Prometheus's classic failure mode is cardinality explosion: a histogram with 10 buckets across 50 services is already 500 time series before anyone adds a per-user label, and that's the single most common way a Prometheus deployment falls over in production. Alert design is where all of this either pays off or gets ignored: alerts must be symptom-based (the SLO is burning) rather than cause-based (CPU is at 85%), and multi-window multi-burn-rate alerting — requiring both a short and a long window to breach simultaneously — is the standard fix for the alternative failure, alert fatigue, where a noisy alert gets muted and the next real incident pages into silence.

## Why this gets asked

The interviewer has been paged at 3am for a CPU-threshold alert that had nothing to do with any actual user impact, and separately has watched a real multi-hour degradation go uncaught because the only alerts in place were tuned for fast spikes. They want to know whether you understand that RED and USE answer different questions, whether an SLO means anything to you beyond "a number we report to leadership," and whether you'll design an alerting system a human being can actually live with — one where every page is worth waking up for, because the alternative (alert fatigue) is the failure mode that quietly disables the whole observability investment.

---

## Lineage: past → present → future

**What came before.** Before RED/USE existed as named methodologies, ops teams monitored raw per-host infrastructure metrics — CPU, memory, disk — against static thresholds set by intuition, alerting on cause rather than symptom. This produced two compounding failures: alert storms during real incidents (every affected host paged independently, burying the actual signal), and blind spots where a service returned errors to users while every infra metric stayed in "normal" range, because request-level failure and resource-level saturation are genuinely different signals. Brendan Gregg formalized the USE method (~2012) specifically for systems-performance triage of finite resources. Tom Wilkie formalized RED (2015, at Weaveworks) explicitly as the request-side complement — a microservices-era answer to "USE tells you about the box, what tells you about the service running on it." Google's SRE book (2016) then formalized SLI/SLO/error budgets as the layer connecting reliability metrics to organizational decisions, born from the recognition that targeting 100% uptime is both technically impossible and actively harmful — it kills release velocity for no real user benefit past the point where users can't perceive the difference.

**Where it stands now.** RED-for-services-plus-USE-for-resources, wrapped in Google's "four golden signals" (latency, traffic, errors, saturation) framing, is settled industry practice. Multi-window multi-burn-rate (MWMBR) alerting, formalized in the Google SRE Workbook, is the settled consensus replacement for naive single-window threshold alerts, which are demonstrably vulnerable to both false positives (short blips trip a sensitive short-window alert) and false negatives (a slow, sustained burn stays under a threshold tuned for fast spikes). Prometheus plus Grafana remains the dominant self-hosted metrics stack, and it just went through a real architectural shift: **native histograms became stable as of Prometheus v3.8.0**, continuing to mature through the **v3.13.0 LTS release on 1 July 2026** [Prometheus Native Histograms in Production — Michal Drozd](https://www.michal-drozd.com/en/blog/prometheus-native-histograms-production/) — accessed 2026-08-01, which collapses the classic per-bucket cardinality multiplication into a single sparse series per histogram — though as of this version, scraping them still requires explicitly opting in via the `scrape_native_histograms` config setting, it isn't yet default-on. The live disagreements: how much to lean on synthetic/black-box probes versus metrics-derived SLIs for the same service, and whether AI-assisted anomaly detection is mature enough to replace human-designed burn-rate thresholds as the primary paging mechanism — most practitioners in 2026 still don't trust it as the primary signal, treating it as a supplementary investigation aid at best.

**Where it's heading.** Dashboards-as-code is mainstreaming — Grafana 13 (current as of 2026) supports Git-backed dashboards edited through a PR workflow rather than click-ops in the UI [Grafana 13 release — Grafana Labs](https://grafana.com/blog/grafana-13-release-all-the-latest-features/) — accessed 2026-08-01, applying the same version-control discipline to observability configuration that infrastructure-as-code applied to infra a decade earlier; this is real and actively shipping. Native histograms moving from stable-but-opt-in to default-on as ecosystem tooling (older exporters, Grafana panel types) catches up is a high-confidence near-term direction. More speculative: LLM-assisted correlation across traces, metrics, and logs to narrow root cause automatically during an incident — early, and unproven specifically at reducing false-positive rate, which is the metric that actually determines whether such a tool gets trusted in production.

---

## Mental model

```
        RED (subject = SERVICE, request-driven)      USE (subject = RESOURCE, finite pool)
        ┌───────────────────────────────┐             ┌───────────────────────────────┐
        │ Rate      requests/sec          │             │ Utilization  % time busy        │
        │ Errors    failed requests/sec   │             │ Saturation   queue depth /       │
        │ Duration  latency dist (p50/    │             │              extra work waiting  │
        │           p95/p99)              │             │ Errors       resource-level      │
        └───────────────────────────────┘             │              error events         │
                                                        └───────────────────────────────┘

        A GPU-serving inference endpoint needs BOTH views simultaneously:
        RED on the endpoint (is it serving requests correctly, how fast)
        USE on the GPU itself (is it saturated, is that WHY requests are slow)

        GPU utilization normal + request latency climbing = queueing UPSTREAM,
        not the GPU -- a regression that shows on one axis and not the other
        is common and is exactly why you need both, not either.

   ──────────────────────────────────────────────────────────────────────────

        SLO/ERROR BUDGET bridges metrics -> a release-cadence DECISION:

        SLI (measured) ──> SLO (target, e.g. 99.9%/month) ──> error budget
        (1 - SLO = 43.2 min/month allowed) ──> BUDGET POLICY: exhausted this
        window? freeze feature releases, shift to reliability work only.

   ──────────────────────────────────────────────────────────────────────────

        BURN-RATE ALERT needs TWO windows, both must breach (AND):

        SHORT window (confirms issue is CURRENT) ──┐
                                                     ├──► PAGE
        LONG window  (confirms issue is SUSTAINED)─┘

        short window ≈ long window / 12 (Google SRE Workbook guideline)
```

---

## How it actually works

### RED vs. USE: different subjects, not competing methodologies

**RED** — Rate (requests/sec), Errors (failed-request rate), Duration (latency distribution, tracked as p50/p95/p99, never a single average) — applies to anything that serves discrete requests: an HTTP endpoint, an RPC, a queue consumer processing messages one at a time. **USE** — Utilization (percent of time the resource is busy), Saturation (queue depth or extra work waiting beyond capacity), Errors (resource-level error events — disk I/O errors, ECC memory errors, dropped packets) — applies to finite resource pools: CPU, memory, disk, a connection pool, a thread pool, a GPU. The test for which applies: does the thing serve discrete units of work to a caller (RED) or does it represent finite capacity being consumed (USE)? A GPU serving an inference workload needs both simultaneously and independently — RED on the inference endpoint, USE on the GPU device itself — because GPU utilization can look completely normal while request latency climbs (the bottleneck is queueing upstream of the GPU, not the GPU itself), a regression pattern invisible if you only instrument one axis.

### Four golden signals

Google's SRE book packages latency, traffic, errors, and saturation as the four things every user-facing service should have a dashboard for — mechanically this is RED (latency = duration, traffic = rate, errors = errors) plus saturation borrowed from USE, presented as a single checklist rather than two separate methodologies, which is the framing most teams actually use day to day.

### SLI, SLO, error budget — with the arithmetic

An **SLI** is the measured indicator (e.g., the fraction of requests completing successfully, or the fraction completing under a latency threshold). An **SLO** is the target for that SLI over a defined window (e.g., 99.9% of requests succeed, measured monthly). The **error budget** is `1 - SLO`, and translating it into wall-clock time is what makes it operationally real:

| SLO | Allowed downtime / month (30 days) |
|---|---|
| 99% | 432 minutes (7.2 hours) |
| 99.9% | 43.2 minutes |
| 99.95% | 21.6 minutes |
| 99.99% | 4.32 minutes |

The number by itself does nothing. What makes it matter is an **error-budget policy**: when the budget for the current rolling window is exhausted, feature releases freeze and the team shifts to reliability work until the budget recovers. This is the concrete mechanism that ties an abstract percentage to an actual release-cadence decision — an SLO with no budget policy attached is a vanity metric on a dashboard, not a governance tool.

### Prometheus data model, PromQL, and cardinality explosion

Prometheus is **pull-based**: it scrapes `/metrics` endpoints on an interval rather than receiving pushed data, which means a target that's down produces an observable `up == 0` signal instead of silence, at the cost of needing service discovery to know what to scrape. Every unique combination of metric name plus label set is one time series. This is where the classic operational failure lives: a **classic histogram** stores each bucket as its own separate series — a histogram with 10 latency buckets tracked across 50 services is already **500 time series** before anyone adds a single additional label like region, version, or endpoint, and adding a label with K unique values multiplies total series count by K. **Cardinality explosion** — the symptom is Prometheus falling behind on ingestion, memory usage climbing until the process OOMs, or query latency degrading sharply with "too many series" errors in the logs — is almost always caused by putting an effectively-unbounded value (a raw user ID, a request ID, an untemplated URL path) on a label. The fix is structural, not tuning: drop the high-cardinality label from the metric entirely and use a trace store for per-request drill-down instead (see `T08-otel-genai`'s exemplar pattern, which links a bounded metric back to a specific unbounded trace ID without putting that ID in the metric's own dimensionality).

**Native histograms** — stable as of **Prometheus v3.8.0**, maturing through the **v3.13.0 LTS release (1 July 2026)** — directly attack this specific failure for histograms: instead of N separate bucket series, the entire distribution lives in one sparse series with dynamically adapting exponential bucket resolution, so a bucket with zero observations costs nothing. As of this version they still require explicitly enabling `scrape_native_histograms` — not yet default-on, and downstream tooling (older exporters, some Grafana panel types) is still catching up to full support.

**Recording rules** precompute an expensive or frequently-queried PromQL expression on a schedule and store the result as its own time series, so a dashboard panel queries the cheap precomputed series instead of re-running a heavy aggregation live on every page load — the standard fix for a dashboard that takes tens of seconds to render.

**Pull vs. push**: pull is the default and generally preferred for long-running services; push (via a Pushgateway or equivalent) exists for short-lived batch jobs that don't live long enough between runs to be scraped on a normal interval.

### Grafana dashboards people actually use

A dashboard that works follows the same top-down structure as the RED/USE mental model: an overview layer showing RED per service (is anything user-facing broken right now), a drill-down layer showing USE per resource (if something's broken, is a resource the cause), and a link-out to the trace store for the specific request-level detail neither RED nor USE aggregates capture. Grafana 13's dashboards-as-code (Git-backed, PR-reviewed) closes a gap that plagued click-ops dashboards for years: no audit trail for who changed a panel's threshold and why, which matters directly for post-incident review when a dashboard's own configuration is a suspect.

### Alert design: symptom-based, burn-rate, and the failure that makes it all worthless

**Symptom-based, not cause-based.** The primary paging signal should be "the user-facing SLO is burning" (a RED-derived symptom), not "CPU is at 85%" (a USE-derived cause). A resource can run hot without any user impact (autoscaling doing exactly its job), and conversely users can be impacted by a cause that never crosses any infra threshold (one slow downstream dependency adding tail latency with no resource anywhere near saturated). Cause-based signals still matter — as tickets and investigation aids once a symptom-based page fires — but they're a poor primary trigger because they don't reliably correlate with what the user actually experiences.

**Burn rate**, precisely: `burn_rate = SLI_error_rate / (1 - SLO)` — how many multiples of the *sustainable* budget-consumption rate you're currently burning. A burn rate of 1 means you're on track to exhaust exactly this window's allotted budget by the end of the window; a burn rate of 14.4 means that, sustained, you'd exhaust a full 30-day budget in roughly 2 hours.

**Multi-window multi-burn-rate (MWMBR)** requires a short window and a long window to breach *simultaneously* before paging: the long window confirms the issue is sustained (not a transient blip), the short window confirms the issue is still happening right now (not a historical spike that's already resolved). The Google SRE Workbook's standard guideline sizes the short window at roughly 1/12 the long window, and gives concrete alert tiers: **page at 14.4x burn rate** on 5-minute/1-hour windows (consumes 2% of a 30-day budget in that one hour), **page at 6x burn rate** on 30-minute/6-hour windows (5% of budget in 6 hours), **file a ticket (don't page) at 3x burn rate** on 2-hour/24-hour windows (10% of budget in 24 hours) [How to Set Up Multi-Window Multi-Burn-Rate Alerting for SLOs — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-set-up-multi-window-multi-burn-rate-alerting-for-slos-on-google-cloud/view) — accessed 2026-08-01, and [Google SRE Workbook — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) — accessed 2026-08-01.

**Alert fatigue** is the named failure mode that makes the entire alerting investment worthless: too many alerts, or alerts with too high a false-positive rate, get muted or ignored by on-call, and the next real incident pages into silence because the human on the other end has learned that pages don't mean anything. The observable symptom is a growing list of permanently-silenced alert rules, rising acknowledgment time on pages, and on-call engineers self-reporting "I just ignore most of these." The fix isn't a tooling change, it's a discipline: track pages-per-week per on-call rotation as a first-class metric the team actively tries to reduce, require every alert to carry an actionable next step (a runbook link, a clear "here's what to do"), and delete any alert that fails that bar rather than tuning its threshold indefinitely.

---

## Build it from scratch

A Prometheus recording rule plus a multi-window multi-burn-rate alert rule — the shape an interviewer may ask you to sketch on a whiteboard:

```yaml
# untested sketch -- prometheus rule file, illustrative not copy-paste-ready
groups:
  - name: slo_recording_rules
    interval: 30s
    rules:
      - record: job:http_requests_error_rate:ratio_5m
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) by (job)
          /
          sum(rate(http_requests_total[5m])) by (job)

      - record: job:http_requests_error_rate:ratio_1h
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[1h])) by (job)
          /
          sum(rate(http_requests_total[1h])) by (job)

  - name: slo_burn_rate_alerts
    rules:
      # Page: 14.4x burn rate, 5m short window + 1h long window, both must breach
      - alert: SLOBurnRateCritical
        expr: |
          job:http_requests_error_rate:ratio_5m > (14.4 * 0.001)
          and
          job:http_requests_error_rate:ratio_1h > (14.4 * 0.001)
        for: 2m
        labels:
          severity: page
        annotations:
          summary: "SLO burning at 14.4x on {{ $labels.job }} -- 2% of 30d budget in 1h"
          runbook: "https://runbooks.internal/slo-burn-critical"
```

The `and` between the two window expressions is the entire mechanism: neither window alone is sufficient, both must independently confirm the breach before this fires, which is what suppresses both short blips and stale historical spikes that a single-window threshold would either miss or false-positive on.

---

## How it's done in production

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Prometheus OOMs or falls behind on ingestion, "too many series" errors | An unbounded-value label (user ID, request ID, raw URL path) added to a metric, or a classic histogram × many services multiplying bucket series | Drop the high-cardinality label; use trace-store exemplars for per-request drill-down instead; consider native histograms for the histogram-specific multiplication |
| Alert fires constantly with no real incident behind it, team mutes it within weeks | Single-window threshold alert too sensitive to short blips, or a cause-based (CPU/memory) alert with no correlation to actual user impact | Replace with a symptom-based burn-rate alert using multi-window multi-burn-rate |
| A real multi-hour degradation wasn't caught until customer complaints arrived | Alert thresholds tuned only for fast spikes (short window only), no slow-burn detection | Add the long-window leg of MWMBR specifically to catch sustained, low-magnitude burns |
| Release velocity has ground to a halt, team is frustrated with the SLO process | Error budget set stricter than actual business need, or the budget resets on a punitive hard calendar boundary instead of a rolling window | Revisit whether the SLO target matches real business criticality; ensure the budget recovers on a rolling window, not just a hard monthly reset |
| A Grafana dashboard panel times out or takes 20-30 seconds to render | An expensive PromQL aggregation is computed live on every page load with no recording rule backing it | Add a recording rule precomputing the aggregation on ingest; point the panel at the precomputed series |
| Two teams' dashboards disagree about whether the same incident happened | No shared, version-controlled definition of the SLI/SLO; each team's dashboard defines "success" slightly differently | Define SLIs once, centrally, version-controlled (Grafana 13's Git-backed dashboards make this an actual PR-reviewable artifact, not tribal knowledge) |

---

## Tradeoffs & when NOT to use it

- **Don't apply RED to a resource.** CPU utilization has no "error rate" or "requests/sec" in the RED sense — it's the wrong subject; use USE for resources and reserve RED for things that serve discrete requests.
- **Don't set a 99.99%+ SLO for a genuinely non-critical internal tool.** The operational cost — on-call load, engineering time spent chasing a razor-thin budget — isn't justified when the actual business impact of an occasional outage is low; match the SLO target to real criticality, not to what sounds impressive on a dashboard.
- **Don't page on every cause-level (USE) metric crossing a threshold.** Most resource fluctuation is normal operating range, not user-impacting; reserve pages for symptom-based burn-rate breaches and keep cause-based signals as tickets or investigation dashboards.
- **Don't roll out native histograms across an existing Prometheus deployment without checking downstream tooling support first.** Stabilization is recent (v3.8.0); older exporters and some Grafana panel types are still catching up, and a blind rollout can silently break dashboards that expect classic bucket series.
- **Don't force per-request or per-user dimensional analysis into Prometheus's metric model.** That's exactly the shape of query a trace store (`T08-otel-genai`, `T08-obs-platforms`) is built for; trying to get there by adding high-cardinality labels to metrics is the direct path to cardinality explosion.

---

## Interview questions

### Q1 — What's the difference between RED and USE, and when do you use each?
**Testing:** whether the candidate understands these are different subjects, not competing frameworks.
**Answer:** RED (rate, errors, duration) applies to anything serving discrete requests — a service, an endpoint, a queue consumer. USE (utilization, saturation, errors) applies to finite resource pools — CPU, memory, disk, a connection pool. The test is whether the thing serves work to a caller (RED) or represents consumed capacity (USE); many systems need both simultaneously on different components.
**Follow-up trap:** *"Give an example where a system looks healthy on one and broken on the other."* — a GPU inference endpoint where GPU utilization (USE) looks normal but request latency (RED) is climbing, because the bottleneck is queueing upstream of the GPU, not the GPU itself; only instrumenting one axis would miss this entirely.

### Q2 — Derive how much downtime a 99.9% monthly SLO actually buys, and why that arithmetic matters.
**Answer:** A 30-day month has 43,200 minutes; 0.1% of that is 43.2 minutes of allowed downtime. It matters because it converts an abstract percentage into a number an engineer can reason about concretely — "we have 43 minutes of budget left this month" is actionable in a way "99.9%" alone is not.
**Follow-up trap:** *"What does the number alone actually accomplish without anything else attached?"* — nothing operationally; it only matters once paired with an error-budget policy (e.g., freeze releases when exhausted) that ties the number to an actual decision, otherwise it's a vanity metric.

### Q3 — What does an error-budget policy actually do, mechanically?
**Answer:** When the error budget for the current rolling window is exhausted, feature releases freeze and the team shifts effort to reliability work until the budget recovers — this is the concrete mechanism connecting an SLO to release cadence, which is the entire point of having an SLO in the first place rather than just monitoring uptime passively.
**Follow-up trap:** *"The team blows through budget in week one of a monthly window every single month. What does that tell you?"* — either the SLO target is set unrealistically tight for the system's actual reliability, or there's a recurring root cause that isn't being fixed between windows; a budget that's chronically exhausted immediately is a signal to revisit the target or the underlying reliability work, not to ignore the policy.

### Q4 — Explain cardinality explosion in Prometheus with a concrete number.
**Answer:** Each unique metric-name-plus-label-set combination is a separate time series; a classic histogram stores each bucket as its own series, so 10 buckets tracked across 50 services is already 500 series before any additional label. Adding a label with K unique values multiplies total series by K, and an unbounded label (user ID, request ID) creates effectively unbounded series, which is what actually crashes Prometheus.
**Follow-up trap:** *"Native histograms fix this — so is cardinality solved now?"* — only for the histogram-bucket-specific multiplication; native histograms don't fix cardinality explosion caused by an unbounded label on any metric type, and as of Prometheus v3.8.0/v3.13.0 they're still opt-in, not default, so the underlying discipline (never put unbounded values on labels) still has to be followed everywhere else.

### Q5 — Design a burn-rate alert and explain why a single-window threshold alert is insufficient.
**Answer:** A single-window alert (e.g., "error rate > 1% for 5 minutes") either false-positives on short blips if the window is short, or misses slow sustained burns if the window is long enough to smooth those out. Multi-window multi-burn-rate requires both a short window (confirms currency) and a long window (confirms sustained duration) to breach simultaneously, with the short window sized around 1/12 the long window per the Google SRE Workbook guideline.
**Follow-up trap:** *"Walk through what happens with only the short window and no long window, concretely."* — a 5-minute spike from a deploy's brief cold-start would page even though it self-resolves and never threatens the actual monthly budget; the long window is what filters that noise out while still catching genuinely sustained problems the short window alone would keep re-triggering on.

### Q6 — What burn rate corresponds to exhausting a 30-day error budget in 1 hour, and what does that number mean operationally?
**Answer:** 14.4x — this is the Google SRE Workbook's tier-1 page threshold, on 5-minute/1-hour windows, consuming 2% of the 30-day budget in that single hour if sustained. Operationally it means: at this rate, if nothing is done, you'll blow the entire month's budget in about 1 hour, which is exactly the urgency that justifies waking someone up.
**Follow-up trap:** *"Why 14.4 specifically and not a round number like 10 or 15?"* — it's derived from the ratio of the alerting window to the SLO window and the target budget-consumption fraction (2% of budget in 1 hour, against a 30-day/720-hour window, gives 1/0.02 × (1/720) inverted to a burn multiple) — the exact derivation matters less than knowing it's principled arithmetic tied to the SLO window size, not a guessed threshold.

### Q7 — Why should alerts be symptom-based rather than cause-based?
**Answer:** A cause-level metric (CPU, memory) can be elevated without any user-facing impact (autoscaling working as designed), and conversely users can be impacted by a cause that never crosses any infra threshold (a single slow dependency adding tail latency with no resource saturated). Symptom-based alerts (the SLO itself burning) correlate directly with what the user experiences, which is the only thing that justifies paging a human at 3am.
**Follow-up trap:** *"So cause-based metrics are useless?"* — no, they're essential for diagnosis once a symptom-based page fires, and useful as tickets/dashboards for proactive capacity planning; they're just the wrong *primary paging trigger* because they don't reliably correlate with user impact on their own.

### Q8 — What is alert fatigue, and what's the concrete fix?
**Testing:** the named failure mode the whole module builds toward.
**Answer:** Too many alerts, or alerts with a high false-positive rate, get muted or ignored by on-call, so the next real incident pages into silence because pages have stopped meaning anything. Observable symptoms: a growing list of permanently-silenced alert rules, rising acknowledgment time, on-call self-reporting they ignore most pages. The fix is a discipline, not a tuning knob: track pages/week per rotation as a metric to actively reduce, require every alert to be actionable with a runbook, and delete alerts that fail that bar rather than endlessly re-tuning thresholds.
**Follow-up trap:** *"A team wants to 'fix' alert fatigue by just raising every threshold 20%."* — that's tuning, not fixing; it reduces volume short-term but doesn't address whether each remaining alert is actually actionable or correlated with user impact, and it risks quietly increasing false negatives (missing real incidents) as a side effect of chasing a lower page count.

### Q9 — When is a recording rule the right fix, and what's the actual mechanism?
**Answer:** When an expensive or frequently-run PromQL aggregation is being computed live on every dashboard load or alert evaluation, a recording rule precomputes it on a schedule and stores the result as its own time series, so subsequent queries read the cheap precomputed series instead of recomputing the aggregation from raw data every time.
**Follow-up trap:** *"Doesn't this just move the cost somewhere else?"* — yes, deliberately: the cost moves from "every dashboard viewer/alert evaluation pays the full aggregation cost" to "the aggregation runs once per recording interval regardless of how many consumers read it," which is a real efficiency win whenever the ratio of reads to the underlying data change rate is high, as it almost always is for dashboards.

### Q10 — A GPU-serving inference service's request latency has doubled, but GPU utilization metrics look completely normal. Diagnose using RED/USE.
**Answer:** This is exactly the case where RED (on the inference endpoint) and USE (on the GPU) disagree, and the disagreement is the diagnostic signal — normal GPU utilization rules out the GPU itself as the bottleneck, pointing instead at something upstream: request queueing before requests reach the GPU, a batching/scheduling change, or a saturated resource elsewhere in the request path (network, a preprocessing step, a different shared resource) that isn't being measured at all.
**Follow-up trap:** *"What would you instrument next to actually confirm the queueing hypothesis?"* — a USE view specifically on the request queue itself (depth over time, wait time before a request reaches GPU processing), which is a resource metric distinct from both the GPU's own USE metrics and the endpoint's RED metrics — the queue is its own resource that needs its own instrumentation.

### Q11 — When should you NOT build a strict SLO/error-budget process for a service?
**Testing:** the "when not to use it" signal.
**Answer:** For a genuinely low-stakes internal tool where the operational cost of chasing a tight budget (on-call burden, engineering time) exceeds the actual business impact of occasional downtime — a formal SLO/error-budget process earns its cost once a service has real user-facing criticality or contractual reliability commitments, not by default for everything.
**Follow-up trap:** *"That internal tool just got embedded in a customer-facing workflow. Now what?"* — that's the trigger to revisit the decision, exactly as with formal eval harnesses (`T08-eval-harness`) and formal agent trajectory eval (`T08-agent-eval`) — the blast radius of a regression changing is what should re-trigger the cost/benefit calculation, not a fixed schedule.

### Q12 — Your team's dashboards in two different tools disagree about whether an incident happened last Tuesday. How do you prevent this going forward?
**Answer:** The root cause is almost always that each team's dashboard independently defines "success" for the same underlying SLI slightly differently (different latency threshold, different error-code inclusion). Fix it by defining SLIs once, centrally, in a version-controlled artifact — Grafana 13's Git-backed dashboards with a PR workflow make this reviewable and auditable rather than tribal knowledge embedded separately in each team's panel configuration.
**Follow-up trap:** *"What if the two teams genuinely need different definitions of success for the same underlying metric?"* — that's legitimate (a payments team's latency SLI threshold may reasonably differ from a search team's), but the definitions themselves — not just the dashboards displaying them — should be explicit, named, and version-controlled artifacts, so a disagreement traces back to a documented, deliberate difference rather than an accidental one nobody remembers configuring.

---

## Red flags that fail you

- Treating RED and USE as interchangeable or not knowing which applies to a resource versus a service.
- Citing an SLO percentage with no idea what error budget (in actual minutes) it corresponds to.
- Describing an SLO with no mention of an error-budget policy that ties it to a release-cadence decision.
- Recommending CPU/memory threshold alerts as the primary paging mechanism for a user-facing service.
- Not knowing what multi-window multi-burn-rate alerting is, or why a single-window threshold alert is insufficient.
- Not being able to name alert fatigue as the specific failure mode that disables an alerting system, with its observable symptom.
- Suggesting a high-cardinality label (user ID, request ID) on a Prometheus metric without recognizing the cardinality-explosion risk.
- Treating a passing dashboard as proof of reliability with no discussion of what it doesn't cover (blind spots between RED and USE, missing SLI definitions).

---

## Cheat card

```
RED (service)   Rate (req/s), Errors (failed req/s), Duration (p50/p95/p99)
USE (resource)  Utilization (%busy), Saturation (queue depth), Errors (resource-level)
4 GOLDEN        latency, traffic, errors, saturation = RED + saturation

SLO ARITHMETIC  99%    = 432 min/mo downtime allowed
                99.9%  = 43.2 min/mo
                99.95% = 21.6 min/mo
                99.99% = 4.32 min/mo
                error budget = 1 - SLO. BUDGET POLICY (freeze releases when
                exhausted) is what makes the number DO anything.

PROMETHEUS      pull-based scrape. metric+labelset = 1 series.
                CARDINALITY TRAP: 10 buckets x 50 svcs = 500 series before
                ANY other label. unbounded label (user_id/request_id) = OOM.
                symptom: ingestion falls behind, "too many series", OOM.
                NATIVE HISTOGRAMS: stable v3.8.0, LTS v3.13.0 (1 Jul 2026).
                1 sparse series/histogram, still opt-in (scrape_native_histograms)
                RECORDING RULES: precompute expensive PromQL, query the cheap
                result instead. PUSH (Pushgateway): only for short-lived batch.

GRAFANA         v13 (2026): dashboards-as-code, Git-backed, PR workflow.
                good structure: RED overview -> USE drill-down -> trace link-out

ALERT DESIGN    SYMPTOM-based (SLO burning), not CAUSE-based (CPU% high) = page
                cause-based = ticket/investigation aid, not page
                burn_rate = SLI_error_rate / (1 - SLO)
                MWMBR: short + long window, BOTH must breach (AND).
                short window ~= long window / 12
                TIERS (Google SRE Workbook): 14.4x on 5m/1h = page (2%/1h)
                6x on 30m/6h = page (5%/6h) · 3x on 2h/24h = ticket (10%/24h)

ALERT FATIGUE   too many/noisy alerts -> muted -> next REAL incident pages
                into silence. symptom: rising silenced-rule count, rising ack
                time, on-call says "I ignore most of these."
                FIX: track pages/week as a metric to reduce, every alert needs
                a runbook + actionable step or gets DELETED, not re-tuned forever
```

## Sources

- [Prometheus Native Histograms in Production: Rollout Plan, Budgets, and Failure Modes — Michal Drozd](https://www.michal-drozd.com/en/blog/prometheus-native-histograms-production/) — accessed 2026-08-01
- [How to Set Up Multi-Window Multi-Burn-Rate Alerting for SLOs on Google Cloud — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-set-up-multi-window-multi-burn-rate-alerting-for-slos-on-google-cloud/view) — accessed 2026-08-01
- [Google SRE Workbook — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) — accessed 2026-08-01
- [Grafana 13 release: get value from your data faster, manage operations at scale, and more! — Grafana Labs](https://grafana.com/blog/grafana-13-release-all-the-latest-features/) — accessed 2026-08-01
- [Prometheus At Scale: Taming High Cardinality (2026) — Alexandre Vazquez](https://alexandre-vazquez.com/prometheus-scalability/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
