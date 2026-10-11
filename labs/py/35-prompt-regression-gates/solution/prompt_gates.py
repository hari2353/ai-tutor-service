"""Reference implementation for the prompt regression gate lab."""
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


def _contains_phrase(output: str, term: str) -> bool:
    return " ".join(term.casefold().split()) in " ".join(output.casefold().split())


def score_case(case: GoldenCase, output: str) -> CaseResult:
    matched = tuple(term for term in case.required_terms if _contains_phrase(output, term))
    missing = tuple(term for term in case.required_terms if term not in matched)
    return CaseResult(case.id, case.slice_name, not missing, matched, missing)


def aggregate(results: Iterable[CaseResult]) -> tuple[float, dict[str, float]]:
    rows = tuple(results)
    if not rows:
        raise ValueError("results must not be empty")
    overall = sum(result.passed for result in rows) / len(rows)
    grouped: dict[str, list[bool]] = {}
    for result in rows:
        grouped.setdefault(result.slice_name, []).append(result.passed)
    slices = {name: sum(values) / len(values) for name, values in grouped.items()}
    return overall, slices


def evaluate_gate(
    results: Iterable[CaseResult],
    baseline_slices: Mapping[str, float],
    *,
    overall_threshold: float,
    slice_thresholds: Mapping[str, float],
    max_slice_drop: float = 0.0,
    min_slice_cases: int = 1,
) -> GateResult:
    rows = tuple(results)
    if min_slice_cases < 1 or max_slice_drop < 0:
        raise ValueError("invalid gate limits")
    overall, rates = aggregate(rows)
    counts: dict[str, int] = {}
    for result in rows:
        counts[result.slice_name] = counts.get(result.slice_name, 0) + 1

    failed = {
        name for name, threshold in slice_thresholds.items()
        if counts.get(name, 0) < min_slice_cases or rates.get(name, 0.0) < threshold
    }
    regressions = {
        name for name, before in baseline_slices.items()
        if name in rates and before - rates[name] > max_slice_drop
    }
    passed = overall >= overall_threshold and not failed and not regressions
    return GateResult(
        passed=passed,
        overall_rate=overall,
        slice_rates=rates,
        failed_slices=tuple(sorted(failed)),
        regression_slices=tuple(sorted(regressions)),
    )
