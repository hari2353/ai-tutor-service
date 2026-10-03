# Lab 33: Tail Latency and Percentile SLOs

**Track:** T10 System Design · **Time:** 2h · **XP:** 50
**Module:** `T10-tail-latency-slos`

**You will build:** deterministic standard-library helpers for exact nearest-rank percentiles, upper-bound histogram approximation, SLO error-budget arithmetic, and tail-breach alerting.

**You will be able to answer:** *"How do you detect a user-visible latency regression when the average is still healthy, and how do you turn that signal into an SLO action?"*

## Setup

```bash
cd labs/py/34-tail-latency-slos
python -m venv .venv && .venv/Scripts/activate
pip install pytest
```

The implementation uses only the Python standard library. `pytest` is used only to run the lab tests.

## The spec

Implement `latency_slos.py`:

1. `nearest_rank_percentile(values, percentile)` returns the exact nearest-rank value. Percentiles are in `[0, 100]`; p0 uses rank 1 and p100 uses rank n. Reject empty input, non-finite values, and invalid percentiles.
2. `LatencyHistogram(bounds)` accepts strictly increasing finite upper bounds. `observe(value)` increments the first inclusive bucket that contains the value; values above the final bound go into an implicit `+Inf` bucket. `approx_percentile(percentile)` returns the first bucket upper bound containing the nearest rank, or `math.inf` for the overflow bucket.
3. `compute_error_budget(total_events, target, bad_events)` returns an immutable `ErrorBudget` with `allowed_bad`, `bad_events`, `remaining`, `consumed_fraction`, and `exhausted`. Targets are in `[0, 1]`; counts are non-negative integers; allowed bad events use floor arithmetic.
4. `should_alert_on_tail(values, percentile, threshold, min_samples=1)` returns true only when there are at least `min_samples` values and the nearest-rank percentile is strictly greater than the threshold. It must not use the arithmetic mean as a proxy for the tail.
5. The code must not sleep, use wall-clock time, use randomness, read files, access a network, or import third-party packages.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add a merge operation for histograms with identical bucket schemas.
2. Add a burn-rate helper for two windows without introducing a clock.
3. Add trace exemplars that retain the slowest deterministic samples without retaining every sample.
4. Compare histogram approximation error against exact samples on a replayed fixture.
