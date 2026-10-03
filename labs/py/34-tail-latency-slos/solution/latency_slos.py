"""Reference implementation for Lab 33."""
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


def _finite_number(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _rank(count: int, percentile: float) -> int:
    p = _finite_number(percentile, "percentile")
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")
    return max(1, math.ceil(p / 100 * count))


def nearest_rank_percentile(values: Iterable[float], percentile: float) -> float:
    samples = sorted(_finite_number(value, "value") for value in values)
    if not samples:
        raise ValueError("values must not be empty")
    return samples[_rank(len(samples), percentile) - 1]


class LatencyHistogram:
    def __init__(self, bounds: Iterable[float]) -> None:
        normalized = tuple(_finite_number(bound, "bound") for bound in bounds)
        if not normalized or any(left >= right
                                 for left, right in zip(normalized, normalized[1:])):
            raise ValueError("bounds must be strictly increasing and non-empty")
        self.bounds = normalized
        self._counts = [0] * (len(normalized) + 1)

    @property
    def counts(self) -> tuple[int, ...]:
        return tuple(self._counts)

    @property
    def total(self) -> int:
        return sum(self._counts)

    def observe(self, value: float) -> None:
        sample = _finite_number(value, "value")
        for index, bound in enumerate(self.bounds):
            if sample <= bound:
                self._counts[index] += 1
                return
        self._counts[-1] += 1

    def approx_percentile(self, percentile: float) -> float:
        if not self.total:
            raise ValueError("histogram has no observations")
        target = _rank(self.total, percentile)
        cumulative = 0
        for index, count in enumerate(self._counts):
            cumulative += count
            if cumulative >= target:
                return self.bounds[index] if index < len(self.bounds) else math.inf
        raise AssertionError("histogram counts are inconsistent")


@dataclass(frozen=True)
class ErrorBudget:
    allowed_bad: int
    bad_events: int
    remaining: int
    consumed_fraction: float
    exhausted: bool


def compute_error_budget(total_events: int, target: float,
                         bad_events: int) -> ErrorBudget:
    if isinstance(total_events, bool) or not isinstance(total_events, int):
        raise TypeError("total_events must be an integer")
    if isinstance(bad_events, bool) or not isinstance(bad_events, int):
        raise TypeError("bad_events must be an integer")
    if total_events < 0 or bad_events < 0:
        raise ValueError("event counts must be non-negative")
    target_value = _finite_number(target, "target")
    if not 0 <= target_value <= 1:
        raise ValueError("target must be between 0 and 1")
    allowed = int(Decimal(total_events) * (Decimal("1") - Decimal(str(target_value))))
    remaining = allowed - bad_events
    consumed = (bad_events / allowed) if allowed else (0.0 if bad_events == 0 else math.inf)
    exhausted = remaining <= 0 if allowed else bad_events > 0
    return ErrorBudget(allowed, bad_events, remaining, consumed, exhausted)


def should_alert_on_tail(values: Iterable[float], percentile: float,
                         threshold: float, min_samples: int = 1) -> bool:
    if isinstance(min_samples, bool) or not isinstance(min_samples, int):
        raise TypeError("min_samples must be an integer")
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    samples = tuple(values)
    if len(samples) < min_samples:
        return False
    return nearest_rank_percentile(samples, percentile) > _finite_number(threshold, "threshold")
