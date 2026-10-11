"""Starter for the prompt regression gate lab."""
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class GoldenCase:
    id: str
    prompt: str
    slice_name: str
    required_terms: tuple[str, ...]
    critical: bool = False


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    slice_name: str
    passed: bool
    matched: tuple[str, ...]
    missing: tuple[str, ...]


@dataclass(frozen=True)
class GateResult:
    passed: bool
    overall_rate: float
    slice_rates: Mapping[str, float]
    failed_slices: tuple[str, ...]
    regression_slices: tuple[str, ...]


def score_case(case: GoldenCase, output: str) -> CaseResult:
    raise NotImplementedError


def aggregate(results: Iterable[CaseResult]) -> tuple[float, dict[str, float]]:
    raise NotImplementedError


def evaluate_gate(
    results: Iterable[CaseResult],
    baseline_slices: Mapping[str, float],
    *,
    overall_threshold: float,
    slice_thresholds: Mapping[str, float],
    max_slice_drop: float = 0.0,
    min_slice_cases: int = 1,
) -> GateResult:
    raise NotImplementedError
