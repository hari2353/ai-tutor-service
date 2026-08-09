# CloudWatch, X-Ray, CloudTrail, Cost Explorer, Well-Architected

> **Track:** C-AWS AWS Atlas · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-observability-cost` · **Tags:** ops

## The 30-second version

CloudWatch custom metrics bill per unique time series — every distinct combination of metric name, namespace, and dimension values is a separate billable metric at $0.30/month for the first 10,000 — and dimensions are multiplicative, so one high-cardinality tag (`userId`, `requestId`) can silently turn one metric into thousands of dollars a month. X-Ray traces at a default sampling rate of "first request per second, plus 5% of the rest," configurable per service/route, and is now formally in SDK/daemon maintenance mode with AWS steering new instrumentation toward OpenTelemetry. CloudTrail logs management events free by default but charges for every data event ($0.10/100,000) from the first one, and "enable data events on everything for a compliance audit" is the single most common CloudTrail bill surprise. The Well-Architected Framework's six pillars (operational excellence, security, reliability, performance efficiency, cost optimization, sustainability) are a real review checklist run through the Well-Architected Tool, not a slogan — treat it as a structured set of questions to walk an architecture against, not a poster. And the AI/data bill in practice is dominated by a short, repeatable list: NAT gateway data processing, cross-AZ transfer, idle provisioned endpoints/model units, unpartitioned Athena/Redshift scans, and forgotten CloudTrail data events — tagging and Cost Anomaly Detection catch the drift, but knowing this list by heart is what actually prevents it.

## Why this gets asked

Because the interviewer has been the one paged when a CloudWatch bill jumped 10x from a well-intentioned "let's add detailed per-user metrics" change, or has spent an afternoon in CloudTrail Lake trying to figure out why data-event logging was silently costing more than the entire rest of the observability stack, or has sat through a Well-Architected review that was treated as a compliance checkbox instead of an actual design conversation. They want evidence that observability and cost are treated as the same discipline — instrumenting something you can't afford to keep instrumented isn't actually observability, it's a future incident.

---

## Lineage: past → present → future

**What came before.** Pre-CloudWatch, AWS operational visibility meant scraping instance-level metrics yourself (custom Nagios/Ganglia-style polling) with no managed aggregation, and distributed tracing across services essentially didn't exist as a managed product — teams either lived without it or ran early self-hosted tracing systems modeled on Google's Dapper paper (2010). CloudWatch (2009) gave AWS-native metrics and alarms out of the box; CloudTrail (2013) answered "who did what" after a rising wave of security incidents made API-level audit logging a compliance necessity rather than a nice-to-have; X-Ray (2016) brought managed distributed tracing to AWS specifically because Lambda and microservices made "which service in the chain is slow" impossible to answer from logs alone.

**Where it stands now.** CloudWatch's pricing model — cheap for a handful of well-designed metrics, expensive fast for high-cardinality ones — has become a genuine architectural constraint that shapes how teams design metrics from the start, not an afterthought optimization; "aggregate before you publish, keep dimensions low-cardinality" is now standard guidance rather than a lesson learned the hard way. The live shift in this space: X-Ray's SDK and daemon are in maintenance mode as of February 2026, with AWS explicitly steering new instrumentation toward OpenTelemetry-based tracing (which can still flow into X-Ray as a backend, or to any OTel-compatible backend) — meaning "should we invest in X-Ray-specific instrumentation" is now genuinely the wrong question for new services; the right question is OpenTelemetry instrumentation with a chosen backend. CloudTrail's cost model (management events free, data events billed from the first event) remains a frequent, avoidable bill surprise specifically because data events aren't logged by default and teams often turn them on broadly for a compliance requirement without scoping which resources/event types actually need it. The Well-Architected Framework itself is stable in structure (six pillars, cross-pillar design principles) but its specific review question set is periodically revised — treat the pillar names as durable, the exact question count and content as something to re-check per review cycle.

**Where it's heading.** OpenTelemetry as the default instrumentation layer across CloudWatch, X-Ray, and third-party observability backends is the clear direction of travel, with high confidence, given X-Ray's own maintenance-mode status. Cost observability is converging with operational observability — AWS Cost Anomaly Detection (ML-based spend-pattern alerting) and natural-language cost querying (Cost Explorer integration with Amazon Q) are pushing cost investigation toward the same real-time, alert-driven model that metrics/logs already use, rather than a monthly after-the-fact bill review. This is a real, shipping direction, not speculative — though the specific tooling (which Q integration, which anomaly-detection sensitivity defaults) should be re-verified at time of use given how fast this sub-area moves.

---

## Mental model

```
  METRICS/LOGS         TRACING              AUDIT               COST
  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐     ┌─────────────┐
  │ CloudWatch  │     │  X-Ray      │      │ CloudTrail  │     │ Cost        │
  │ - metrics   │     │ (maint.mode,│      │ - mgmt      │     │ Explorer +  │
  │   ($/unique │     │  use OTel   │      │   events:   │     │ Budgets +   │
  │   time      │     │  for new    │      │   FREE      │     │ Anomaly     │
  │   series)   │     │  work)      │      │   (1st copy)│     │ Detection   │
  │ - logs      │     │ - sampling: │      │ - data      │     │             │
  │ - alarms    │     │   1/sec +5% │      │   events:   │     │ WELL-       │
  │ - Logs      │     │   default,  │      │   BILLED    │     │ ARCHITECTED │
  │   Insights  │     │   tunable   │      │   from #1   │     │ = the       │
  │ - EMF       │     │   per route │      │   ($0.10/   │     │ checklist   │
  └─────────────┘     └─────────────┘      │   100k)     │     │ tying it    │
                                            └─────────────┘     │ all together│
                                                                 └─────────────┘

  THE BILL-DOMINATING LINE ITEMS (memorize this list):
   1. NAT gateway data processing ($0.045/GB, see C-AWS-networking)
   2. Cross-AZ data transfer (easy to forget, adds up at scale)
   3. Idle provisioned capacity (SageMaker endpoints, Bedrock model units,
      Redshift clusters sized for peak but running at trough)
   4. Unpartitioned/uncompressed Athena or unoptimized Redshift scans
   5. CloudTrail data events enabled broadly "for compliance" with no scoping
```

---

## How it actually works

### CloudWatch: metrics, logs, alarms, and the high-cardinality trap

CloudWatch charges for **custom metrics** on a tiered per-metric-per-month basis: $0.30 for each of the first 10,000, $0.10 for the next 240,000, $0.05 for the next 750,000, and $0.02 above 1,000,000 [CloudWatch Pricing 2026 — CloudZero](https://www.cloudzero.com/blog/cloudwatch-pricing/) — accessed 2026-08-01. The billable unit is a **unique time series** — every distinct combination of metric name, namespace, and dimension *values* is its own billable metric. This is why dimensions are described as multiplicative: a single metric name with a dimension like `userId` that takes 10,000 distinct values doesn't cost one metric's worth, it costs 10,000 separate metrics — roughly $3,000/month at the first pricing tier alone, for what looked like "one metric" in the code [CloudWatch custom metrics — CloudZero](https://www.cloudzero.com/blog/cloudwatch-pricing/) — accessed 2026-08-01. This is described as the single most common cause of CloudWatch bill surprises, and the fix is structural, not a configuration toggle: use low-cardinality dimensions (service name, environment, region, status code class) and aggregate high-cardinality data (per-user, per-request) *before* publishing, or route it to logs (queryable via Logs Insights) instead of metrics.

**Metric filters** turn log patterns into CloudWatch metrics without changing application code — useful for extracting a count/value from unstructured logs retroactively, but each filter still creates a billable custom metric subject to the same cardinality math. **Logs Insights** runs ad hoc query-language searches directly over log groups, billed by data scanned per query — the log-side analog of Athena's per-TB model, with the same "unindexed full scan" cost shape if queries aren't scoped by time range and log group tightly. **Embedded Metric Format (EMF)** lets you emit structured JSON log lines that CloudWatch automatically extracts into metrics, which is a genuinely good pattern for high-volume metric emission because you pay for the log ingestion (comparatively cheap and doesn't multiply per dimension the way custom `PutMetricData` metrics do) while still getting metrics extracted from a defined dimension set — but the same cardinality caution applies to whatever dimensions you extract into actual metrics from the EMF payload.

### X-Ray: sampling and its current status

The default sampling rule records the first request each second, plus 5% of requests beyond that, per service — enough to catch representative latency/error patterns without tracing every single request, which would both cost more and add overhead. Custom sampling rules let you override this per service, URL pattern, or HTTP method — a common production pattern is 100% sampling on high-value paths (checkout, payment) and near-zero on low-value ones (health checks), rather than a single global rate [X-Ray sampling rules — OneUptime](https://oneuptime.com/blog/post/2026-02-12-xray-sampling-rules/view) — accessed 2026-08-01. **Adaptive sampling** automatically adjusts rates within configured bounds to make sure important/anomalous traces (errors, latency outliers) are captured more consistently than the flat default rate would guarantee. Pricing is per trace recorded/retrieved/scanned, with a free tier covering 100,000 traces recorded and 1,000,000 traces retrieved/scanned per month [X-Ray pricing — AWS](https://aws.amazon.com/xray/pricing/) — accessed 2026-08-01.

**Status as of 2026: X-Ray's SDKs and daemon entered maintenance mode in February 2026**, with AWS recommending OpenTelemetry-based instrumentation for new work — existing X-Ray sampling rules and SDK-based instrumentation continue to function, but new services should be instrumented with OpenTelemetry (which can still export to X-Ray as a trace backend, or to any other OTel-compatible system) rather than the X-Ray SDK directly [X-Ray maintenance mode note — CubeAPM](https://cubeapm.com/blog/aws-x-ray-pricing-review/) — accessed 2026-08-01. This is a meaningful "don't recommend the old default" moment worth naming explicitly if asked about tracing strategy for a new service.

### CloudTrail: management vs data events, and the cost trap

**Management events** (control-plane API calls — creating a bucket, launching an instance, changing an IAM policy) are logged by CloudTrail automatically, with the **first copy per region free** and additional copies (e.g. a second multi-region trail overlapping an existing one) billed at roughly $2.00 per 100,000 events [CloudTrail pricing — CloudCostKit](https://cloudcostkit.com/guides/aws-cloudtrail-pricing/) — accessed 2026-08-01. **Data events** (data-plane operations — S3 object reads/writes, Lambda invocations, DynamoDB item-level operations) are **not enabled by default**, and once enabled, they are billed at $0.10 per 100,000 events **from the very first event**, with no free tier at all [CloudTrail data events pricing — Oreate AI](https://www.oreateai.com/blog/demystifying-cloudtrail-data-events-understanding-the-costs/b652492a7cee980beb498054ef2bfedd) — accessed 2026-08-01.

**The cost trap, concretely:** a team enables S3 data events across an entire account "to satisfy a compliance audit requirement" without scoping to specific buckets or prefixes. If those buckets see millions of GET/PUT operations per day (entirely plausible for anything backing an active data lake or ML training pipeline), the CloudTrail data-event bill can dwarf the rest of the observability stack combined — the commonly-cited failure pattern is "the 2nd-copy trap" (an overlapping multi-region trail plus a single-region trail both capturing the same events) stacked with "data events wide open" (no per-resource selector scoping) [CloudTrail cost traps — Tomoda Hinata](https://tomodahinata.com/en/blog/aws-cloudtrail-pricing-cost-optimization-guide) — accessed 2026-08-01. The fix is **advanced event selectors** scoping data-event logging to the specific buckets/tables/functions that actually need audit-level granularity, rather than account-wide, and auditing existing trails for overlapping multi-region/single-region duplication before adding a new one.

### The Well-Architected Framework as an actual checklist

The framework's six pillars — **operational excellence, security, reliability, performance efficiency, cost optimization, sustainability** — are backed by a structured review question set (dozens of questions per pillar) that the **AWS Well-Architected Tool** walks through directly in the console, producing a prioritized list of "High Risk Issues" (HRIs) rather than a vague impression [AWS Well-Architected Framework — NetCom Learning](https://www.netcomlearning.com/blog/aws-well-architected-framework) — accessed 2026-08-01. The cross-pillar design principles that apply regardless of which pillar you're reviewing are worth internalizing as a mindset, not just a pillar list: stop guessing capacity (use autoscaling and real usage data, not provisioned-for-worst-case guesses), test at production scale, automate with the expectation of experimentation, design for evolvability, drive decisions from data, and improve through deliberate game days rather than waiting for a real incident to teach the lesson [Well-Architected design principles — CloudToolStack](https://cloudtoolstack.com/learn/aws-well-architected-overview) — accessed 2026-08-01.

Used as an actual review, not a slogan, this looks like: pick a specific architecture, go pillar by pillar through the Tool's question set, flag every "no" or "partially" answer as a finding, prioritize findings by (a) how High-Risk AWS's own scoring flags them and (b) actual blast radius if that gap causes an incident, and produce a remediation backlog with owners — the same discipline as a security review or an incident postmortem, applied proactively instead of reactively.

### Cost Explorer, tagging, Budgets, and the line items that actually dominate an AI/data bill

**Cost Explorer** gives filterable, groupable historical and forecasted spend by service, account, region, and — critically — by **cost allocation tag**, which only works if tags were actually applied consistently at resource-creation time; retrofitting tags onto untagged historical spend doesn't recover the missing attribution. **Budgets** are proactive threshold alerts (commonly configured at 80% and 100% of a monthly target, scoped per team/environment/service) rather than after-the-fact analysis. **Cost Anomaly Detection** uses ML to flag spend patterns that deviate from the resource's own historical baseline, catching a spike days before a human would notice it in a monthly review [AWS Cost Management 2026 — Finout](https://www.finout.io/blog/aws-cost-management-in-2026-tools-kpis-pitfalls-and-finops-best-practices) — accessed 2026-08-01.

The five (or so) line items that dominate a real AI/data-heavy AWS bill, worth having memorized cold rather than rediscovering per incident:

1. **NAT gateway data processing** ($0.045/GB, compounding with cross-AZ and internet egress — full detail in `C-AWS-networking`).
2. **Cross-AZ data transfer** — easy to introduce accidentally (a NAT gateway and its private subnet in different AZs, a database and its application tier split across AZs with high-volume traffic between them) and easy to forget because it doesn't show up as a distinct, obviously-named line item the way NAT does.
3. **Idle provisioned capacity** — SageMaker real-time endpoints sized for peak and left running at trough, Bedrock provisioned-throughput model units committed for sustained load that turned out to be spikier than modeled, Redshift clusters provisioned for a monthly reporting burst and idle the rest of the time.
4. **Unpartitioned or uncompressed Athena/Redshift scans** — the $5/TB-scanned or cluster-time cost of a table nobody optimized (full detail in `C-AWS-data-analytics`).
5. **CloudTrail data events with no scoping**, and **high-cardinality CloudWatch custom metrics** — the two observability-side line items that belong on this list precisely because they're easy to enable broadly "just in case" without doing the cardinality/volume arithmetic first.

**Azure/GCP equivalent.** CloudWatch → Azure Monitor + Log Analytics / Cloud Monitoring + Logging (GCP). X-Ray → Application Insights (Azure) / Cloud Trace (GCP). CloudTrail → Activity Log (Azure) / Cloud Audit Logs (GCP). Cost Explorer → Cost Management (Azure) / Cloud Billing + FinOps Hub (GCP). The Well-Architected Framework itself is AWS-specific in name, though Azure (Well-Architected Framework, genuinely similarly named and structured) and GCP (Architecture Framework) both publish close analogs with broadly the same pillar concepts. See `clouds/CROSS-CLOUD-MAP.md`.

---

## Build it from scratch

A minimal cardinality-aware custom metric emitter — the discipline this module is actually testing, more than any specific number:

```python
# untested sketch
import boto3
from collections import Counter

cloudwatch = boto3.client("cloudwatch")

# BAD: one dimension value per user -- multiplies into thousands of billable
# metrics the moment you have thousands of active users.
def emit_bad(user_id: str, latency_ms: float) -> None:
    cloudwatch.put_metric_data(
        Namespace="MyApp",
        MetricData=[{
            "MetricName": "RequestLatency",
            "Dimensions": [{"Name": "UserId", "Value": user_id}],  # high cardinality
            "Value": latency_ms,
            "Unit": "Milliseconds",
        }],
    )

# GOOD: aggregate to a low-cardinality dimension (route + status class) before
# publishing; per-user detail goes to structured LOGS (EMF or plain JSON),
# queryable via Logs Insights when actually needed, not billed per time series.
_buffer: Counter = Counter()

def emit_good(route: str, status_class: str, latency_ms: float) -> None:
    cloudwatch.put_metric_data(
        Namespace="MyApp",
        MetricData=[{
            "MetricName": "RequestLatency",
            "Dimensions": [
                {"Name": "Route", "Value": route},              # bounded set
                {"Name": "StatusClass", "Value": status_class},  # bounded set
            ],
            "Value": latency_ms,
            "Unit": "Milliseconds",
        }],
    )
```

A minimal CloudTrail advanced event selector scoping data events to one bucket instead of the whole account:

```bash
# untested sketch — scoped, not account-wide
aws cloudtrail put-event-selectors \
  --trail-name my-audit-trail \
  --advanced-event-selectors '[
    {
      "Name": "S3 data events for the sensitive-audit bucket only",
      "FieldSelectors": [
        {"Field": "eventCategory", "Equals": ["Data"]},
        {"Field": "resources.type", "Equals": ["AWS::S3::Object"]},
        {"Field": "resources.ARN", "StartsWith": ["arn:aws:s3:::sensitive-audit-bucket/"]}
      ]
    }
  ]'
```

---

## How it's done in production

| Concern | Tool | What it adds |
|---|---|---|
| Metrics, logs, alarms | CloudWatch | Native AWS integration, EMF for structured metric-from-logs emission, Logs Insights for ad hoc query |
| Distributed tracing (new instrumentation) | OpenTelemetry (exporting to X-Ray, or any OTel backend) | Vendor-neutral instrumentation given X-Ray SDK/daemon maintenance-mode status |
| Audit trail | CloudTrail + advanced event selectors | Scoped, cost-controlled data-event logging instead of account-wide |
| Structured architecture review | AWS Well-Architected Tool | Prioritized High-Risk Issue list per pillar, not just a mental checklist |
| Cost visibility and alerting | Cost Explorer + Budgets + Cost Anomaly Detection | Historical/forecast analysis, proactive threshold alerts, ML-based spend-anomaly detection |
| Cost attribution | Cost allocation tags | Per-team/per-environment/per-project showback or chargeback — only works if applied at resource creation |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| CloudWatch bill jumps sharply after a metrics change | A new metric dimension carries high-cardinality values (userId, requestId, instanceId) | Move high-cardinality detail to logs (EMF/Logs Insights); keep metric dimensions to bounded, low-cardinality sets |
| CloudTrail costs spike with no obvious cause | Data events enabled broadly (whole account/bucket) rather than scoped, or overlapping multi-region + single-region trails double-logging the same events | Use advanced event selectors scoped to specific resources; audit for duplicate/overlapping trails |
| X-Ray traces missing for a genuinely important but low-traffic error path | Default sampling (1/sec + 5%) undersamples a rare path | Add a custom sampling rule at or near 100% for that specific route/service |
| Well-Architected review produces a long list nobody acts on | Review treated as a one-time compliance exercise, findings not prioritized or assigned owners | Prioritize by AWS's own High-Risk Issue flag plus actual blast radius; assign owners and re-review on a cadence, not once |
| Monthly AWS bill has an unexplained spike, discovered weeks later | No proactive alerting — relying on manual Cost Explorer review | Enable Cost Anomaly Detection and Budgets with 80%/100% thresholds per team/environment |
| Cost Explorer can't attribute a spend spike to a team | Resources created without cost allocation tags | Enforce tagging at creation time (SCP/tag policies), not retroactively — historical untagged spend can't be recovered into the attribution |
| Logs Insights query costs more than expected | Query not scoped by time range or log group, effectively full-scanning a large log group | Narrow the time range and target the specific log group(s) actually relevant to the question |

---

## Tradeoffs & when NOT to use it

- **Don't publish a CloudWatch custom metric with a high-cardinality dimension "just to have the detail available."** The cost is multiplicative and immediate; per-entity detail belongs in logs, queried on demand, not in metrics billed per unique time series every month regardless of whether anyone looks at it.
- **Don't enable CloudTrail data events account-wide as a default compliance posture.** Scope to the specific resources that actually need data-plane audit granularity; a blanket policy is the most commonly cited cause of CloudTrail bill surprises.
- **Don't invest in new X-Ray-SDK-specific instrumentation for a new service in 2026.** With the SDK/daemon in maintenance mode, OpenTelemetry instrumentation (which can still export to X-Ray) is the forward-looking choice and avoids building on a component AWS itself has signaled is not where new investment is going.
- **Don't treat a Well-Architected review as a one-time checkbox.** Findings without owners and a re-review cadence produce a document nobody acts on; the value is in the recurring discipline, not the one-time exercise.
- **Don't rely on end-of-month Cost Explorer review as your only cost control.** By the time a human notices a spike in a monthly report, weeks of anomalous spend have already accrued — Budgets and Cost Anomaly Detection catch it in days, not weeks.
- **Don't skip tagging "because we'll add it later."** Cost allocation tags only attribute spend from the point they're applied forward; untagged historical spend has no retroactive attribution, so the cost of skipping tagging compounds the longer it's deferred.

---

## Interview questions

### Q1 — A team's CloudWatch bill jumped from $200/month to $3,000/month after adding "more detailed metrics." Diagnose.
**Testing:** the highest-signal CloudWatch failure mode.
**Answer:** Almost certainly a new metric dimension with high cardinality — something like `userId`, `requestId`, or `instanceId` — because CloudWatch bills per unique combination of metric name, namespace, and dimension values, and dimensions multiply. A metric with 10,000 distinct dimension values isn't one billable metric, it's 10,000, at $0.30/month each in the first pricing tier alone — roughly $3,000/month, which matches the described jump closely.
**Follow-up trap:** *"The team needs per-user visibility for debugging. How do you give them that without the cost?"* — move per-user detail into structured logs (EMF or plain JSON) instead of metrics; Logs Insights can query per-user detail on demand, and log ingestion cost doesn't multiply per dimension value the way CloudWatch custom metrics do. Keep the actual metrics aggregated to low-cardinality dimensions (route, status class, environment).

### Q2 — Why are CloudTrail data events a common cost trap, specifically?
**Answer:** Because they're not enabled by default (so teams have to actively turn them on, usually for a compliance requirement) and once enabled they're billed from the very first event with no free tier, unlike management events which get a free first copy per region. The trap is enabling them broadly — across an entire account or bucket — instead of scoping to the specific resources that need data-plane audit granularity, which at any meaningful S3/DynamoDB/Lambda volume can produce a bill that dwarfs the rest of the observability stack.
**Follow-up trap:** *"The compliance requirement genuinely needs to audit all S3 access across the account. Is there a way to do this without the blanket cost?"* — advanced event selectors can still scope by resource type and other fields even when the requirement is broad, and it's worth confirming the requirement actually needs every bucket versus a defined sensitive-data scope — but if it genuinely is account-wide, the cost is a real, unavoidable requirement to budget for, not something to route around; the point is not skipping the audit, it's not enabling it broader than the actual requirement by accident.

### Q3 — X-Ray's default sampling is "first request per second plus 5% of the rest." Why might this be wrong for a specific service, and how do you fix it?
**Answer:** It's a reasonable general-purpose default but undersamples rare, high-value paths — a payment or checkout flow that only sees a handful of requests per second could go long stretches with zero traces captured for an occasional but important error. Fix with a custom sampling rule scoped to that specific service/route at or near 100%, while leaving low-value, high-volume paths (health checks) at or below the default rate.
**Follow-up trap:** *"Would you recommend investing further in X-Ray-specific tooling for a new microservice in 2026?"* — no; X-Ray's SDK and daemon are in maintenance mode as of February 2026, so new instrumentation should go through OpenTelemetry, which can still export traces to X-Ray as a backend if that's the chosen visualization/storage layer, but the instrumentation investment itself shouldn't be X-Ray-SDK-specific going forward.

### Q4 — Walk through the Well-Architected Framework's six pillars and how you'd actually use it, not just recite it.
**Answer:** Operational excellence, security, reliability, performance efficiency, cost optimization, sustainability. Used properly, it's a structured review run through the AWS Well-Architected Tool against a specific architecture — walking each pillar's question set, flagging every gap, and getting a prioritized High-Risk Issue list rather than a vague sense of "we should probably improve reliability sometime." The output is a remediation backlog with owners, re-reviewed on a cadence, the same discipline as a security review or postmortem applied proactively.
**Follow-up trap:** *"Your team ran a Well-Architected review six months ago and nothing on the list got fixed. What went wrong?"* — most likely the findings weren't prioritized against actual blast radius and given owners with a deadline — a review that produces a document instead of a tracked backlog with accountability is functionally the same as not having done the review at all.

### Q5 — Name the five line items that most commonly dominate an AI/data-heavy AWS bill, and why observability tooling itself makes this list.
**Answer:** NAT gateway data processing, cross-AZ data transfer, idle provisioned capacity (SageMaker endpoints, Bedrock provisioned throughput, oversized Redshift clusters), unpartitioned/uncompressed Athena or Redshift scans, and unscoped CloudTrail data events plus high-cardinality CloudWatch custom metrics. The observability line items belong on the list because they're specifically the ones teams enable broadly "just in case" without doing the volume or cardinality arithmetic first — unlike compute or storage costs, which at least scale visibly with obvious usage, these two can balloon from a single well-intentioned but unscoped configuration change.
**Follow-up trap:** *"Which of these five is hardest to catch with automated tooling, and why?"* — idle provisioned capacity, because Cost Anomaly Detection is tuned to catch deviations from a resource's own historical baseline, and a SageMaker endpoint or Redshift cluster sized for peak and simply always running at that size doesn't look anomalous against its own history — it looks like steady, expected spend. Catching it requires a utilization-based review (comparing provisioned capacity against actual usage), not an anomaly-detection alert.

### Q6 — What's the practical difference between a CloudWatch metric filter and Embedded Metric Format (EMF), and when would you pick one over the other?
**Answer:** A metric filter extracts a value from existing unstructured log lines retroactively (via a pattern match) into a CloudWatch metric — useful when you can't or don't want to change the application's log format. EMF has the application emit structured JSON log lines in a specific format that CloudWatch parses to extract metrics automatically at ingestion, which is generally the better pattern for new instrumentation because it's less brittle than pattern-matching unstructured text and integrates cleanly with structured logging you'd want anyway.
**Follow-up trap:** *"Does EMF avoid the high-cardinality cost problem?"* — no — whatever dimensions you configure EMF to extract into actual CloudWatch metrics are still subject to the same per-unique-time-series billing; EMF changes how metrics get created (from structured logs vs a direct API call), not the underlying cardinality economics. The cardinality discipline still has to be applied to whatever dimension set you extract.

### Q7 — Your team wants to enable Cost Anomaly Detection but isn't sure what scope to apply it at. What's the tradeoff?
**Answer:** Scoping too broadly (the whole account) means a real anomaly in a small, low-spend service can be diluted below the detection threshold by the overall account's noise; scoping too narrowly (per individual resource) creates alert fatigue and misses cross-resource anomalies (a coordinated spend pattern across several related resources that's each individually unremarkable). A reasonable middle ground is scoping by cost-allocation-tag-defined groups (per team, per environment, per major service) — granular enough to catch team-level anomalies, aggregated enough to avoid noise on every individual resource.
**Follow-up trap:** *"What has to be true before this scoping strategy works at all?"* — consistent, correctly-applied cost allocation tags at resource creation time — Cost Anomaly Detection scoped by tag groups is only as good as the tagging discipline behind it, which is why tagging strategy is a prerequisite conversation, not an independent optimization.

### Q8 — Explain why "the first copy of CloudTrail management events per region is free" can still result in real CloudTrail charges for a team that never touched data events.
**Answer:** The free tier is per region for the first trail's management events — a second, overlapping trail (a common accidental setup: an existing single-region trail plus a newly-added multi-region trail both capturing the same region's events) means the *second* copy of those events is billed even though no data events are involved at all. This is the "2nd-copy trap" and it's purely a trail-configuration issue, unrelated to data-event scoping.
**Follow-up trap:** *"How would you detect this without waiting for a bill surprise?"* — audit existing CloudTrail trails for regional overlap before adding a new one (list all trails and their region scope), and treat "why do we have two trails covering the same region" as a red flag worth investigating immediately rather than assuming redundancy is intentional.

### Q9 — Design an instrumentation strategy for a new microservice in 2026: what do you use for metrics, tracing, and logs, and why?
**Answer:** CloudWatch for metrics (with disciplined low-cardinality dimension design from day one) and logs (structured JSON, using EMF where metric extraction from logs is useful), and OpenTelemetry for tracing instrumentation — exporting to X-Ray if that's the team's chosen trace visualization backend, or to any other OTel-compatible system, rather than instrumenting directly against the X-Ray SDK given its maintenance-mode status.
**Follow-up trap:** *"Why not just use the X-Ray SDK directly since it's simpler and still works?"* — it still works today, but building new instrumentation against a component AWS has explicitly signaled is not receiving further investment is a foreseeable migration cost later; OpenTelemetry gives the same tracing capability with vendor flexibility and is the direction AWS itself is pointing new work toward.

### Q10 — A Well-Architected review flags "no autoscaling, capacity provisioned for peak" as a finding under performance efficiency. Which cross-pillar design principle does this violate, and what's the cost-optimization angle?
**Answer:** "Stop guessing capacity" — one of the Well-Architected Framework's cross-pillar design principles, which argues for autoscaling and real usage-driven sizing over provisioning for an assumed worst case. The cost-optimization angle is direct: capacity provisioned for peak and left running at trough is exactly the "idle provisioned capacity" line item that dominates real AI/data bills — the same finding shows up as a legitimate concern under both the performance-efficiency and cost-optimization pillars simultaneously, which is a useful illustration of why the pillars aren't independent silos.
**Follow-up trap:** *"If a finding shows up under multiple pillars, does that mean it's double-counted in prioritization?"* — no, it means it's higher-priority — a finding with cross-pillar impact (affecting both cost and performance/reliability) generally deserves to be weighted above a finding that's isolated to a single pillar, all else equal.

### Q11 — What specifically does Logs Insights cost, and what's the analogous cost-optimization lever to Athena's partitioning story?
**Answer:** Logs Insights bills by the volume of log data scanned per query, similar in shape to Athena's per-TB-scanned model. The analogous optimization lever is scoping queries tightly by time range and to the specific log group(s) relevant to the question, rather than running a broad query across a large, long-retention log group — an unscoped query effectively full-scans a large volume of irrelevant log data the same way an unpartitioned Athena query full-scans an entire table.
**Follow-up trap:** *"Does structuring log lines (e.g. as JSON) help with Logs Insights cost the way Parquet helps Athena?"* — structured logs make Logs Insights queries easier to write and more precise in what they extract, but they don't reduce the underlying bytes-scanned billing the way columnar formats reduce Athena's scan — the primary Logs Insights cost lever is query scoping (time range, log group), not data format.

### Q12 — Your CFO asks you to name the single highest-leverage cost-observability practice to implement this quarter, given limited engineering time. What do you recommend and why?
**Answer:** Enforce cost allocation tagging at resource creation (via tag policies/SCPs) and turn on Cost Anomaly Detection scoped to those tag groups. Tagging is the prerequisite for almost every other cost-visibility practice (Cost Explorer filtering, Budgets scoping, anomaly detection granularity, showback/chargeback) — without it, every other tool operates on a coarser, less actionable view of spend, and untagged historical spend can never be retroactively attributed. It's also comparatively low engineering effort (policy enforcement, not application code changes) relative to the visibility it unlocks across every other line item on this list.
**Follow-up trap:** *"Isn't fixing the specific NAT/CloudTrail/Athena cost traps more immediately impactful than a tagging policy?"* — those fixes are real and worth doing, but they're point fixes for specific symptoms; tagging is the structural change that makes every future cost anomaly (including ones not yet discovered) attributable and actionable quickly, which compounds in value over time in a way a one-time point fix doesn't.

---

## Red flags that fail you

- Not naming high-cardinality dimensions as the cause of a CloudWatch cost spike.
- Not knowing CloudTrail data events are unbilled-by-default-but-not-free-once-enabled, with no free tier.
- Recommending new X-Ray SDK instrumentation for a greenfield service without mentioning its maintenance-mode status or OpenTelemetry.
- Treating the Well-Architected Framework as a slogan or a poster rather than a structured review process with prioritized findings.
- Naming only one or two cost line items when asked what dominates a real AI/data bill, rather than the fuller list (NAT, cross-AZ, idle capacity, unoptimized scans, unscoped audit logging).
- Recommending Cost Anomaly Detection or tagging as a fix without acknowledging tagging has to happen at resource-creation time to be useful.
- Presenting a Well-Architected review as a one-time compliance exercise rather than a recurring discipline with owned findings.

---

## Cheat card

```
CLOUDWATCH   custom metric = $0.30/mo (first 10k), $0.10 (next 240k),
             $0.05 (next 750k), $0.02 (>1M) -- PER UNIQUE TIME SERIES
             DIMENSIONS ARE MULTIPLICATIVE: 1 metric x 10k userId values
                                            = 10k billable metrics (~$3k/mo)
             fix: low-cardinality dims only; high-cardinality -> LOGS (EMF)
             Logs Insights bills by bytes scanned -- scope time range + log group

X-RAY        default sampling: 1 req/sec + 5% of rest, tunable per route
             adaptive sampling: auto-adjusts within bounds for anomalies/errors
             MAINTENANCE MODE since Feb 2026 -- use OpenTelemetry for new work
             free tier: 100k traces recorded, 1M retrieved/scanned per month

CLOUDTRAIL   management events: 1st copy/region FREE, extra copies ~$2/100k
             data events: NOT default, $0.10/100k from event #1, no free tier
             traps: "2nd-copy" (overlapping trails) + "wide open" (unscoped
                    account-wide data events) -- use advanced event selectors

WELL-ARCHITECTED  6 pillars: Ops Excellence / Security / Reliability /
                  Performance Efficiency / Cost Optimization / Sustainability
             run via the Well-Architected TOOL -> prioritized High-Risk Issues
             cross-pillar principles: stop guessing capacity, test at
             production scale, automate, design for evolution, use data,
             improve via game days

TOP 5 AI/DATA BILL LINE ITEMS (memorize):
  1. NAT gateway data processing ($0.045/GB)
  2. Cross-AZ data transfer
  3. Idle provisioned capacity (SageMaker endpoints, Bedrock model units,
     oversized Redshift)
  4. Unpartitioned/uncompressed Athena or Redshift scans
  5. Unscoped CloudTrail data events + high-cardinality CloudWatch metrics

COST TOOLS   Cost Explorer (historical/forecast, tag-filterable) +
             Budgets (proactive 80%/100% thresholds) +
             Cost Anomaly Detection (ML baseline deviation)
             ALL depend on TAGGING applied AT CREATION -- can't retrofit history
```

## Sources

- [CloudWatch Pricing: A Straightforward 2026 Guide — CloudZero](https://www.cloudzero.com/blog/cloudwatch-pricing/) — accessed 2026-08-01
- [How to Set Up X-Ray Sampling Rules — OneUptime](https://oneuptime.com/blog/post/2026-02-12-xray-sampling-rules/view) — accessed 2026-08-01
- [AWS X-Ray pricing — AWS](https://aws.amazon.com/xray/pricing/) — accessed 2026-08-01
- [AWS X-Ray Pricing and Review 2026 — CubeAPM](https://cubeapm.com/blog/aws-x-ray-pricing-review/) — accessed 2026-08-01
- [AWS CloudTrail Pricing: Free Management Copy, Data Events — CloudCostKit](https://cloudcostkit.com/guides/aws-cloudtrail-pricing/) — accessed 2026-08-01
- [Demystifying CloudTrail Data Events — Oreate AI](https://www.oreateai.com/blog/demystifying-cloudtrail-data-events-understanding-the-costs/b652492a7cee980beb498054ef2bfedd) — accessed 2026-08-01
- [AWS CloudTrail Pricing & Cost-Optimization Guide 2026 — Tomoda Hinata](https://tomodahinata.com/en/blog/aws-cloudtrail-pricing-cost-optimization-guide) — accessed 2026-08-01
- [AWS Well-Architected Framework - 6 Pillars 2026 — NetCom Learning](https://www.netcomlearning.com/blog/aws-well-architected-framework) — accessed 2026-08-01
- [Well-Architected Framework design principles — CloudToolStack](https://cloudtoolstack.com/learn/aws-well-architected-overview) — accessed 2026-08-01
- [AWS Cost Management in 2026 — Finout](https://www.finout.io/blog/aws-cost-management-in-2026-tools-kpis-pitfalls-and-finops-best-practices) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
- 2026-08-09 — Amazon CloudWatch adds managed Prometheus collectors — agentless scraping for EKS, EC2, ECS, MSK, and OpenSearch Service, removing the need to run and maintain your own Prometheus scrape infrastructure ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-price-reduction-of-gpt-models-in-bedrock-cloudwatch-managed-collectors-for-prometheus-metrics-and-more-august-3-2026/))
