# Tail Latency and Percentile SLO Engineering

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** `T10-estimation`, `T08-classic-obs`, `T21-resilience-catalogue` · **Updated:** 2026-10-03
> **Module id:** `T10-tail-latency-slos` · **Tags:** craft, observability, critical
> **Lab:** `labs/py/34-tail-latency-slos/`

## The 30-second version

The average is a capacity statistic, not a user experience. A percentile answers a different question: "how slow is the request at a chosen point in the distribution?" Define an SLI on the complete request population, choose a percentile target and a threshold, and alert on the tail rather than allowing fast requests to hide a small but important population of slow ones. Exact percentiles require retained samples; production telemetry usually uses a mergeable histogram or streaming sketch, so the result is an approximation with an explicit error bound. An SLO turns that measurement into a budget: if 99.9% of 1,000,000 requests must be under 300 ms, at most 1,000 may be bad. A sound design also states the window, minimum sample count, aggregation dimensions, burn-rate policy, and what action follows a breach.

## Why this gets asked

Because a service can report a healthy average while a customer-visible tail is failing. A downstream timeout, a saturated connection pool, a noisy neighbor, a garbage-collection pause, or a retry storm may affect only a few requests at first. Those requests are often the important ones: checkout, login, feed refresh, or an agent step waiting on a tool. The interviewer is testing whether you can distinguish mean from distribution, compose latency across fan-out, turn a product promise into arithmetic, and choose an alert that creates action instead of pager noise.

---

## Lineage: past → present → future

**What came before.** Early service dashboards leaned heavily on averages and maximums. A mean was compact and easy to aggregate; a maximum was easy to explain but unstable because one outlier could dominate a whole interval. As services began fanning out to many machines, the mean stopped describing the request a user saw. The latency ladder and the peak-to-average reasoning in the estimation module make the physical reason clear: one additional network hop or queue can be cheap for most requests and catastrophic when the dependency is contended.

**Where it stands now.** Percentiles are the operational language for latency, but a percentile is not a property that composes cleanly across services. The p99 of each child is not automatically the p99 of the parent. With serial calls, latency adds per request; with parallel fan-out, the parent is governed by the slowest child, so the chance of seeing a slow child increases with fan-out. Histograms and sketches make high-cardinality, high-volume measurement feasible, but operators must record bucket boundaries, interpolation or upper-bound semantics, sample count, and aggregation dimensions. An SLO is a contract over a time window, not a dashboard line: it needs an eligible-event definition and an error-budget policy.

**Where it's heading.** More systems will use exemplars and trace-linked tail events to connect a p99.9 breach to the exact dependency, tenant, route, or deployment that caused it. Histograms will remain the economical aggregate because they can be merged across instances, while sketches will serve cases needing finer quantile resolution over wide ranges. The durable principle is unchanged: measure the distribution at the user boundary, preserve enough information to explain the tail, and make the response proportional to budget consumption rather than to a noisy single sample.

## Mental model

Think of latency SLO engineering as four boundaries around the same request population:

```text
  USER REQUESTS
       │  define eligibility: success, timeout, cancellation, route
       ▼
  DISTRIBUTION ── exact samples, histogram buckets, or a quantile sketch
       │  ask p50 for typical, p95 for broad experience, p99/p99.9 for tail
       ▼
  SLO WINDOW ── good events / eligible events, not an average of averages
       │  error budget = eligible × (1 - target)
       ▼
  ACTION ── burn-rate alert, rollback, load shed, capacity work, or no page
```

The statistic and the contract are separate. A p99 of 250 ms does not mean 99% availability, and a 99.9% availability SLO does not say anything about latency unless the event is defined as "completed under the latency threshold." Keep the numerator and denominator visible.

## How it actually works

### Percentiles and nearest rank

For `n` observations sorted ascending, nearest rank chooses rank `ceil(p/100 × n)`, with rank 1 used for p0 and rank n for p100. The result is the observation at that rank. This is deterministic, easy to test, and intentionally different from linear interpolation. State the convention: libraries disagree about percentile definitions, and silently changing conventions makes alerts and historical comparisons meaningless.

Example:

```text
latencies = [10, 20, 20, 30, 100]
p50: ceil(.50 × 5) = 3 → 20 ms
p90: ceil(.90 × 5) = 5 → 100 ms
```

Small windows need a minimum sample policy. A p99 from five requests is not evidence that the service has a stable p99; it is one order statistic. Use a longer rolling window, aggregate enough traffic, or mark the result unknown rather than paging on a tiny sample.

### Histograms and approximation

An exact sample reservoir costs memory proportional to traffic and is hard to merge without retaining raw data. A histogram maps each observation to a bucket, such as `<=50`, `<=100`, `<=200`, `<=500`, and `>500` ms. To estimate a percentile, walk cumulative bucket counts until the target rank is reached and return the bucket's upper bound. This is conservative for an upper-bound histogram: the actual quantile is no greater than the reported boundary, but the error can be as large as the bucket width.

Use buckets that match decisions, not an arbitrary aesthetic scale. If the SLO is 300 ms, a boundary at 300 ms is more useful than a broad 100-1000 ms bucket. Use logarithmic or native exponential buckets for a wide range, and add dense boundaries around user-visible thresholds. Every aggregate must retain its bucket schema and count; two histograms with incompatible boundaries cannot be combined safely without re-bucketing from raw data.

### SLO arithmetic

For `N` eligible events and a target `T`,

```text
allowed bad events = floor(N × (1 - T))
remaining budget   = allowed bad events - observed bad events
budget consumed    = observed bad events / allowed bad events
```

If `N = 1,000,000` and `T = 99.9%`, the budget is 1,000 bad events. A request over the latency threshold, an error, or a timeout is bad only if the SLO's event definition says so. Do not average daily percentages: a 99% day with 100 requests and a 99.99% day with 10 million requests must be weighted by eligible events.

### Alerting on the tail

An alert predicate should compare a tail percentile or a directly equivalent bad-event ratio to its objective. It should not compare the arithmetic mean to the objective. A useful policy has two layers:

- Page on a fast burn rate, such as consuming a large fraction of the budget in a short window, when the breach is actionable now.
- Ticket or investigate on a slow burn, so a persistent small regression is not hidden until the monthly budget is gone.

Include `route`, `region`, `dependency`, `tenant class`, and deployment version only when cardinality and action justify them. A global p99 can look healthy while one region or one endpoint is unusable; an over-segmented dashboard can also make every small slice too sparse to interpret. Alert labels must identify the owner and the next safe action.

## Build it from scratch

The lab implements the smallest useful version without clocks, randomness, files, or third-party packages:

1. `nearest_rank_percentile(values, percentile)` validates a non-empty finite input and returns an exact nearest-rank value.
2. `LatencyHistogram(bounds)` records counts into sorted inclusive upper-bound buckets and returns the upper bound containing the nearest-rank bucket.
3. `compute_error_budget(total_events, target, bad_events)` returns allowed, remaining, consumption, and exhaustion without floating-point surprises in the common integer case.
4. `should_alert_on_tail(values, percentile, threshold, min_samples)` checks the tail percentile and never consults the mean. It returns false for insufficient data.

The important design seam is the data boundary. The exact implementation accepts a finite sequence; production swaps in an instrumented recorder or a telemetry backend while preserving the contract: eligible count, bad count, percentile convention, bucket schema, and window.

## How it's done in production

Instrument the user-visible request boundary and preserve eligible, good, and bad event counts alongside a mergeable latency distribution. Define the SLO and error-budget policy before choosing alert thresholds. Link tail exemplars to traces, then segment only by dimensions that have an owner and an action. Use fast-burn alerts for active incidents and slow-burn alerts for persistent regressions.

## Production failure table

| Symptom | Likely cause | Fix |
|---|---|---|
| Average is green while users report slowness | A small tail is hidden by the mean | Alert on p95/p99/p99.9 or bad-event ratio; segment by route and dependency |
| p99 jumps wildly every minute | Too few samples or a high-variance short window | Minimum sample gate, longer window, and a slower-burn companion alert |
| Dashboard shows different p99 after a telemetry migration | Percentile interpolation or bucket semantics changed | Version the quantile convention and bucket schema; backfill or annotate the discontinuity |
| Fleet p99 is lower than every instance's p99 | Averaging percentiles or averaging per-host summaries | Aggregate counts/histograms first, then compute the percentile over the combined population |
| Parent request tail is much worse than each dependency's tail | Serial addition or parallel fan-out amplifies slow-child probability | Budget the whole request, measure spans, cap fan-out, use deadlines and hedging carefully |
| SLO says 100% after a quiet period | No eligible events or denominator is wrong | Expose eligible count, mark empty windows as no-data, and define timeout/cancel treatment |
| Error budget lasts forever despite repeated incidents | Daily SLO percentages were averaged unweighted | Track good and eligible event counts over the full window |
| Pages fire for one harmless outlier | Alert is on max or raw samples | Use a percentile with a sample gate and burn rate; preserve the outlier as an exemplar |
| Tail regresses only for one tenant or region | Global aggregation masks a localized failure | Segment by an actionable dimension and keep a global roll-up for capacity |
| Histogram reports an exact-looking number | Bucket upper bound is mistaken for an exact quantile | Label it approximate and size buckets around SLO thresholds |
| Retry storm creates a latency incident | Retries multiply work and queueing | Deadline propagation, retry budget, jitter, per-dependency bulkheads, and tail instrumentation |

## Tradeoffs & when NOT to use it

- **Exact samples vs histograms/sketches:** exact samples are simple and precise for a small deterministic window, but expensive at volume and difficult to merge. Histograms are cheap and mergeable but have bucket error. Sketches offer configurable rank error but add implementation and validation complexity.
- **p99 vs p99.9:** a higher percentile exposes more users and is more sensitive to sparse data. Choose the percentile from user harm and traffic volume, not because p99.9 sounds senior.
- **Short vs long windows:** short windows react quickly and page on noise; long windows detect sustained harm but can be slow to act. Pair fast and slow burn alerts rather than picking one magical window.
- **Global vs segmented SLOs:** global roll-ups help capacity planning; route/region/tenant slices find localized harm. Only create a slice with an owner and an action, or cardinality becomes an observability outage.
- **Hedged requests:** hedging can reduce tail latency when independent replicas exist, but increases load and can worsen a saturated system. Never add it before measuring the queue and enforcing a hedge budget.
- **Do not use the mean as a latency SLO.** It can remain below target while a material tail is unusable. The mean still belongs in capacity and cost analysis; it is not a substitute for a tail objective.
- **Do not page on a tiny sample.** If the product has low traffic, define an event-based or availability SLO, use a broader window, or route the signal to a ticket until there is enough evidence.

## Interview questions

### Q1 — Why is average latency a poor user-facing SLO?
**Testing:** whether the candidate understands distributions rather than memorized dashboards.
**Answer:** A mean weights fast requests heavily and can hide a small but harmful slow population. A timeout, queue, or one slow dependency can move p99 while barely moving the average. Define the user event and alert on the percentile or bad-event ratio that represents the harm.
**Follow-up trap:** *"Would you delete the average?"* — no. Keep it for capacity and cost diagnosis; do not use it as the sole user-experience objective.

### Q2 — Compute p50 and p90 by nearest rank for `[10, 20, 20, 30, 100]`.
**Testing:** whether the candidate can state a percentile convention.
**Answer:** Sorted input is unchanged. p50 has rank `ceil(0.5 × 5) = 3`, so it is 20 ms. p90 has rank `ceil(0.9 × 5) = 5`, so it is 100 ms.
**Follow-up trap:** *"Why might a library disagree?"* — it may use linear interpolation or another quantile definition. Pin and document the convention before comparing series.

### Q3 — How do you aggregate percentiles across hosts?
**Testing:** recognition of the average-of-percentiles error.
**Answer:** Do not average host p99 values. Merge raw samples, histogram bucket counts with the same schema, or compatible sketch summaries, then calculate the fleet percentile. Preserve the event count because a quiet host must not weigh the same as a busy host.
**Follow-up trap:** *"Can I average p50?"* — not generally for the same reason; use counts or raw distributions unless a mathematically valid weighted summary is available.

### Q4 — Explain an upper-bound histogram percentile.
**Testing:** understanding approximation error.
**Answer:** Record each value in the smallest bucket whose upper bound contains it, compute the target rank from total count, and return the first bucket whose cumulative count reaches that rank. The result is an upper bound on the true nearest-rank value; error is bounded by the bucket width, not zero.
**Follow-up trap:** *"How would you tune buckets?"* — put boundaries at SLO thresholds and densely around decisions, then use logarithmic/exponential spacing for the long tail.

### Q5 — One million requests, 99.9% under 300 ms. What is the budget?
**Testing:** SLO arithmetic.
**Answer:** `1,000,000 × 0.001 = 1,000` bad events. The numerator must count requests over 300 ms plus whatever errors/timeouts the event definition classifies as bad. Track good and eligible counts, not an average of interval percentages.
**Follow-up trap:** *"What if there are 500,000 requests?"* — recompute from the current eligible denominator; the budget is 500 bad events if the same target applies.

### Q6 — Why does a parent p99 exceed every dependency p99?
**Testing:** serial and fan-out reasoning.
**Answer:** Serial latency adds per request, and parallel fan-out waits for the slowest child. Even if each child has a small chance of being slow, the probability that at least one of many children is slow increases with fan-out. Measure end-to-end and span distributions; do not infer the parent SLO from isolated child percentiles.
**Follow-up trap:** *"Would making every child p99 equal to the parent target solve it?"* — no. The composition still has addition and fan-out amplification; allocate a latency budget per path.

### Q7 — When should a p99 alert page?
**Testing:** operational judgment.
**Answer:** When there is enough data, the tail breach consumes budget at an actionable rate, and an owner has a safe immediate action such as rollback, load shedding, or capacity intervention. Pair a fast-burn page with a slower ticket/investigation alert.
**Follow-up trap:** *"Should one over-threshold request page?"* — no; use a sample gate and aggregate evidence. Preserve the request as an exemplar for diagnosis.

### Q8 — What is the difference between an SLI, SLO, and error budget?
**Testing:** terminology tied to mechanics.
**Answer:** The SLI is the measurement, such as the fraction of eligible requests under 300 ms. The SLO is the target, such as 99.9%. The error budget is the allowed bad fraction, 0.1% of eligible events, converted into a count over the window.
**Follow-up trap:** *"Is p99 itself an SLO?"* — it can be the measured SLI form, but the contract still needs its target, window, eligibility, and response policy.

### Q9 — How do retries affect a tail SLO?
**Testing:** whether the candidate sees amplification.
**Answer:** Retries consume capacity and add queueing, so a partial dependency failure can become a tail-wide incident. Propagate a deadline, cap retry attempts and aggregate retry volume, add jitter, and measure both initial and total request latency. A successful retry may still violate the original user budget.
**Follow-up trap:** *"Should retries be excluded from latency?"* — generally no for the user-facing SLO; if you define an internal attempt SLI, keep it separate and do not let it hide user harm.

### Q10 — Why is a maximum a bad alert signal?
**Testing:** robustness to outliers.
**Answer:** The maximum is dominated by one sample and grows with traffic even when the distribution is unchanged. It is useful for forensic exemplars, not as the primary health objective. A percentile plus sample gate and burn rate is more stable and actionable.
**Follow-up trap:** *"What if the one sample was a safety-critical timeout?"* — capture it in a separate hard-failure alert if the event is individually severe; do not pretend that the max is a stable latency SLO.

### Q11 — How do you handle a p99.9 with low traffic?
**Testing:** statistical humility.
**Answer:** Require a minimum sample count and mark low-volume windows as no-data. Use a longer window, aggregate only across a justified population, or define a failure-count/error-budget SLO. A p99.9 calculated from a handful of samples is not a reliable trend.
**Follow-up trap:** *"Would you interpolate to make it smoother?"* — interpolation does not create evidence. It only changes the estimator.

### Q12 — A histogram p99 is 500 ms and the SLO is 300 ms. What do you know?
**Testing:** approximation semantics.
**Answer:** You know the target rank lies in or below the first bucket reported as 500 ms, and the true percentile could be anywhere within that bucket's range. You know enough to alert if 300 ms is a bucket boundary and the cumulative count has crossed it; otherwise refine or redesign buckets around 300 ms before claiming an exact 500 ms breach.
**Follow-up trap:** *"Can two teams merge their histograms?"* — only if the bucket boundaries and semantics are compatible, or if one can safely re-bucket from a richer representation.

### Q13 — How do you prove a deployment caused the tail regression?
**Testing:** observability that leads to causality.
**Answer:** Correlate the change window with route-, region-, version-, and dependency-level histograms or sketches, then inspect trace-linked exemplars from the slow population. Compare a canary/control group and check traffic shape, queue depth, saturation, retries, and GC. A global p99 alone establishes a symptom, not the cause.
**Follow-up trap:** *"Would a rollback always be correct?"* — not if the tail is caused by a dependency or traffic event; use the blast-radius and canary evidence, and choose rollback, mitigation, or load shedding accordingly.

## Red flags that fail you

- Alerting on average latency while calling it a percentile SLO.
- Averaging p99 values from hosts or time buckets.
- Claiming a histogram percentile is exact without naming bucket error.
- Computing an error budget from averaged percentages instead of good and eligible counts.
- Ignoring timeouts, cancellations, retries, or fan-out in the SLO event definition.
- Paging on p99.9 from a handful of requests with no minimum sample gate.
- Saying "use p99" without naming the threshold, window, owner, or action.
- Treating a global percentile as proof that every route, tenant, and region is healthy.
- Adding hedged requests or retries without discussing load amplification and budgets.
- Confusing a latency percentile with availability nines.

## Cheat card

```text
MEAN = capacity/cost clue              PERCENTILE = distribution/user harm
MAX  = forensic outlier                SLO = SLI + target + window + event definition

NEAREST RANK
  sorted values; rank = max(1, ceil(p/100 * n)); value[rank - 1]
  document convention; libraries may interpolate differently

HISTOGRAM
  record into smallest inclusive upper-bound bucket
  cumulative count >= ceil(p/100 * total) -> report bucket upper bound
  approximate; error <= relevant bucket width; merge only compatible schemas

ERROR BUDGET
  allowed_bad = floor(eligible * (1 - target))
  remaining = allowed_bad - observed_bad
  never average interval percentages; count good + eligible across the window

TAIL ALERT
  require enough samples
  alert on p95/p99/p99.9 or bad-event ratio, never mean alone
  fast burn -> page; slow burn -> ticket/investigate
  segment only by dimensions with an owner and action

COMPOSITION
  serial latencies add; parallel fan-out waits for the slowest child
  retries amplify work and queueing; propagate deadlines and cap retry volume
```

## Sources

- [`curriculum/10-system-design/11-estimation.md`](11-estimation.md) — latency ladder, peak-to-average, queueing non-linearity, and the warning that p99.9 is driven by variance rather than volume; checked in source, accessed 2026-10-03
- [`curriculum/07-agentic-ai/13-production-agent-loops.md`](../07-agentic-ai/13-production-agent-loops.md) — p99 alerting for bimodal step counts, retry amplification, budgets, and production observability; checked in source, accessed 2026-10-03
- [Google SRE Book: Service Level Objectives](https://sre.google/sre-book/service-level-objectives/) — SLI/SLO/error-budget framing
- [Google SRE Workbook: Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) — burn-rate alerting and actionable policy
- [Prometheus documentation: Histograms and summaries](https://prometheus.io/docs/practices/histograms/) — mergeable histograms, quantile tradeoffs, and bucket semantics
- Instagram post mining note `DdfjIpeTKvK` — discovery lead for the tail-latency gap; the source was not present in this checkout and is not treated as evidence

## Changelog

- 2026-10-03 — created from the percentile SLO / tail-latency gap
