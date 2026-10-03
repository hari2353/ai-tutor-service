import math

import pytest


def test_nearest_rank_percentile_is_deterministic(R):
    assert R.nearest_rank_percentile([100, 10, 20, 20, 30], 50) == 20
    assert R.nearest_rank_percentile([100, 10, 20, 20, 30], 90) == 100
    assert R.nearest_rank_percentile([7, 8, 9], 0) == 7


def test_histogram_reports_upper_bound_for_tail_bucket(R):
    histogram = R.LatencyHistogram([100, 200, 500])
    for value in [50, 80, 120, 180, 220, 300, 700, 800, 900, 1000]:
        histogram.observe(value)

    assert histogram.counts == (2, 2, 2, 4)
    assert histogram.approx_percentile(90) ==  math.inf


def test_error_budget_counts_bad_events_and_exhaustion(R):
    budget = R.compute_error_budget(1_000_000, 0.999, 800)
    assert budget.allowed_bad == 1_000
    assert budget.remaining == 200
    assert budget.consumed_fraction == pytest.approx(0.8)
    assert budget.exhausted is False

    exhausted = R.compute_error_budget(1_000_000, 0.999, 1_001)
    assert exhausted.remaining == -1
    assert exhausted.exhausted is True

    exact = R.compute_error_budget(1_000_000, 0.9999, 100)
    assert exact.allowed_bad == 100
    assert exact.exhausted is True


def test_alert_uses_tail_not_average_and_has_sample_gate(R):
    latencies = [10, 10, 10, 10, 1000]
    assert sum(latencies) / len(latencies) < 250
    assert R.should_alert_on_tail(latencies, 90, 250) is True
    assert R.should_alert_on_tail(latencies[:2], 90, 250, min_samples=5) is False


def test_invalid_inputs_are_rejected(R):
    with pytest.raises(ValueError):
        R.nearest_rank_percentile([], 99)
    with pytest.raises(ValueError):
        R.nearest_rank_percentile([1, 2], 101)
    with pytest.raises(ValueError):
        R.LatencyHistogram([100, 100])
    with pytest.raises(ValueError):
        R.compute_error_budget(10, 1.1, 0)
