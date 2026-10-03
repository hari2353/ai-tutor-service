"""Starter implementation for Lab 33. Replace every stub."""
from dataclasses import dataclass
from typing import Iterable


def nearest_rank_percentile(values: Iterable[float], percentile: float) -> float:
    raise NotImplementedError


class LatencyHistogram:
    def __init__(self, bounds: Iterable[float]) -> None:
        raise NotImplementedError

    def observe(self, value: float) -> None:
        raise NotImplementedError

    def approx_percentile(self, percentile: float) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class ErrorBudget:
    allowed_bad: int
    bad_events: int
    remaining: int
    consumed_fraction: float
    exhausted: bool


def compute_error_budget(total_events: int, target: float,
                         bad_events: int) -> ErrorBudget:
    raise NotImplementedError


def should_alert_on_tail(values: Iterable[float], percentile: float,
                         threshold: float, min_samples: int = 1) -> bool:
    raise NotImplementedError
