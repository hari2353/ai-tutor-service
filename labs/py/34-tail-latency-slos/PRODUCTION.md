# Production notes - tail latency and percentile SLOs

The lab uses exact samples and a small upper-bound histogram so the percentile convention is visible. Production systems should preserve the same semantic contract while moving storage and aggregation into telemetry infrastructure: record eligible events at the user boundary, aggregate mergeable distributions, retain the bucket schema or sketch configuration, and attach trace exemplars to the slow population.

| Lab concept | Production addition |
|---|---|
| `nearest_rank_percentile` | A versioned quantile convention in the metrics backend; validate it against a known fixture during migrations |
| `LatencyHistogram` | Mergeable native histograms or sketches with dense boundaries around SLO thresholds and explicit overflow handling |
| `ErrorBudget` | Good/eligible counters over a rolling calendar window, plus fast- and slow-burn alert rules |
| `should_alert_on_tail` | A policy engine with minimum sample gates, no-data behavior, owner routing, and deployment-aware annotations |
| deterministic values | Route-, region-, dependency-, tenant-class-, and version-level dimensions selected for actionability, not arbitrary cardinality |
| tail threshold | A user-boundary SLI that includes timeouts, cancellations, retries, and fan-out semantics in the event definition |

## Failure modes

1. **Averaging percentiles.** Per-host or per-minute p99 values are not a fleet p99. Merge counts, samples, compatible histograms, or compatible sketches before calculating the quantile.
2. **Sparse-tail paging.** A p99.9 from six events is not a stable operational signal. Require a minimum sample count, use a broader window, or use an event-count SLO for low-volume routes.
3. **Bucket discontinuity.** Changing bucket boundaries changes reported quantiles even when traffic does not change. Version the schema and annotate migrations; keep thresholds as bucket boundaries where possible.
4. **Wrong denominator.** Excluding timeouts or failed retries can make the SLO look better while users wait longer. Define eligible and bad events at the user boundary and expose both counts.
5. **Global masking.** A healthy global p99 can hide one broken region, route, or tenant class. Add a segment only when it has an owner and a response, and retain the global roll-up for capacity.
6. **Retry amplification.** Retrying a slow dependency consumes the same saturated pool and increases queueing. Propagate deadlines, add jitter, cap retries with a fleet budget, and use bulkheads or load shedding.
7. **Fan-out composition.** A parent waits for a slow serial or parallel child. Instrument spans and end-to-end latency, allocate a path budget, and do not infer parent health from isolated child p99s.
8. **Alert without action.** A page that says "p99 high" but gives no route, owner, deployment, or safe mitigation creates fatigue. Include the next decision in the alert policy.

## Operational policy

- Define the SLI as `good eligible requests / eligible requests`; document whether errors, timeouts, cancellations, and successful retries are bad.
- Use an upper-bound histogram or a sketch for high-volume aggregation, and verify approximation error at the SLO threshold with replayed traffic.
- Pair a fast-burn alert with a slow-burn alert. A single raw p99 threshold is too noisy for urgent paging and too narrow for long-term budget governance.
- Link tail exemplars to traces and deployment versions. The aggregate detects the problem; the exemplar explains it.
- Treat an empty or sparse window as no-data, not as perfect service and not automatically as an outage.
- Review error-budget consumption in release policy. A budget breach should slow risky changes or trigger reliability work, not merely produce another dashboard.

## Evaluation contract

Replay a fixed latency fixture through exact samples and the histogram. Report p50/p95/p99, bucket approximation error at each SLO threshold, eligible and bad counts, remaining budget, alert decisions, and behavior for sparse windows. Run the same fixture before and after any telemetry backend or bucket-schema change; a lower reported p99 without a stable convention is not evidence of improvement.
