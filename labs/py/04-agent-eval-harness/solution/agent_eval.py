"""Lab 04 — reference solution."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict
    result: Any
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class TaskSpec:
    expected_answer: str
    mode: str = "exact"
    tolerance: float = 0.01
    relevant_args: Optional[dict[str, set[str]]] = None


@dataclass
class Trajectory:
    task_id: str
    steps: list[ToolCall]
    final_answer: Any
    task_spec: Optional[TaskSpec] = None


def task_completion(expected: Any, actual: Any, mode: str = "exact",
                    tolerance: float = 0.01) -> bool:
    if mode == "exact":
        return str(actual) == str(expected)
    if mode == "contains":
        return str(expected) in str(actual)
    if mode == "numeric":
        try:
            return abs(float(actual) - float(expected)) <= tolerance
        except (TypeError, ValueError):
            return False
    raise ValueError(f"unknown completion mode: {mode!r}")


def _args_match(gold_args: dict, actual_args: dict,
                relevant: Optional[set[str]]) -> bool:
    keys = set(gold_args) if relevant is None else relevant
    for key in keys:
        if gold_args.get(key) != actual_args.get(key):
            return False
    return True


def tool_call_accuracy(gold_steps: list[ToolCall], actual_steps: list[ToolCall],
                       relevant_args: Optional[dict[str, set[str]]] = None) -> float:
    """Subsequence matching: each gold step may only match an actual step at
    or after the previous gold step's match — order is part of correctness."""
    if not gold_steps:
        return 0.0
    cursor = 0
    matched = 0
    for gold in gold_steps:
        relevant = None
        if relevant_args is not None:
            relevant = relevant_args.get(gold.name)
        for i in range(cursor, len(actual_steps)):
            actual = actual_steps[i]
            if actual.name == gold.name and _args_match(gold.args, actual.args, relevant):
                matched += 1
                cursor = i + 1
                break
    return matched / len(gold_steps)


@dataclass
class TrajectoryValidityReport:
    violations: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.violations


def trajectory_validity(steps: list[ToolCall],
                        allowed: dict[str, set[str]],
                        entry: str = "init") -> TrajectoryValidityReport:
    report = TrajectoryValidityReport()
    state = entry
    for i, step in enumerate(steps):
        if step.name not in allowed.get(state, set()):
            report.violations.append((i, state, step.name))
        else:
            state = step.name
    return report


def total_cost(traj: Trajectory) -> float:
    return sum(s.cost_usd for s in traj.steps)


def cost_per_step(traj: Trajectory) -> float:
    if not traj.steps:
        return 0.0
    return total_cost(traj) / len(traj.steps)


def latency_p50(steps: list[ToolCall]) -> float:
    if not steps:
        return 0.0
    vals = sorted(s.latency_ms for s in steps)
    n = len(vals)
    mid = n // 2
    if n % 2:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def latency_p95(steps: list[ToolCall]) -> float:
    if not steps:
        return 0.0
    vals = sorted(s.latency_ms for s in steps)
    rank = max(1, math.ceil(0.95 * len(vals)))
    return float(vals[rank - 1])


@dataclass
class TaskRow:
    task_id: str
    tool_accuracy: float
    completion: float
    valid: float
    cost_per_step: float
    p50_ms: float
    p95_ms: float


@dataclass
class RunReport:
    rows: list[TaskRow] = field(default_factory=list)
    averages: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    passed: bool = True
    fail_reasons: list[str] = field(default_factory=list)

    def __getitem__(self, metric: str) -> float:
        return self.averages[metric]


class EvalSuite:
    DEFAULT_THRESHOLDS = {
        "tool_accuracy": 0.9,
        "completion": 0.8,
        "validity": 1.0,
        "cost_per_step": 0.05,
        "p95_latency_ms": 5000.0,
    }

    def __init__(self, thresholds: Optional[dict[str, float]] = None) -> None:
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)

    def run(self, trajectories: list[Trajectory],
            golden_set: dict[str, dict[str, Any]]) -> RunReport:
        report = RunReport(thresholds=dict(self.thresholds))
        for traj in trajectories:
            gold = golden_set.get(traj.task_id, {})
            gold_steps = gold.get("steps", [])
            relevant = None
            if traj.task_spec is not None and traj.task_spec.relevant_args is not None:
                relevant = traj.task_spec.relevant_args
            accuracy = tool_call_accuracy(gold_steps, traj.steps, relevant)

            spec = traj.task_spec
            if spec is None:
                spec = TaskSpec(
                    expected_answer=gold.get("expected_answer", ""),
                    mode=gold.get("mode", "exact"),
                    tolerance=gold.get("tolerance", 0.01),
                )
            done = task_completion(spec.expected_answer, traj.final_answer,
                                  spec.mode, spec.tolerance)

            allowed = gold.get("allowed")
            valid = 1.0
            if allowed:
                entry = gold.get("entry", "init")
                valid = 1.0 if trajectory_validity(traj.steps, allowed, entry).valid else 0.0

            report.rows.append(TaskRow(
                task_id=traj.task_id,
                tool_accuracy=accuracy,
                completion=1.0 if done else 0.0,
                valid=valid,
                cost_per_step=cost_per_step(traj),
                p50_ms=latency_p50(traj.steps),
                p95_ms=latency_p95(traj.steps),
            ))

        n = len(report.rows)
        if n == 0:
            report.averages = {}
            report.passed = True       # no data, no failures
            return report
        metrics = {
            "tool_accuracy": sum(r.tool_accuracy for r in report.rows) / n,
            "completion": sum(r.completion for r in report.rows) / n,
            "validity": sum(r.valid for r in report.rows) / n,
            "cost_per_step": sum(r.cost_per_step for r in report.rows) / n,
            "p95_latency_ms": sum(r.p95_ms for r in report.rows) / n,
            "p50_latency_ms": sum(r.p50_ms for r in report.rows) / n,
        }
        report.averages = {k: v for k, v in metrics.items()}

        lower_is_better = {"cost_per_step", "p95_latency_ms", "p50_latency_ms"}
        for metric, threshold in self.thresholds.items():
            value = metrics.get(metric)
            if value is None:
                continue
            if metric in lower_is_better:
                ok = value <= threshold
            else:
                ok = value >= threshold
            if not ok:
                report.fail_reasons.append(
                    f"{metric} avg {value} {'>' if metric in lower_is_better else '<'} {threshold}")
        report.passed = not report.fail_reasons
        return report


LOWER_IS_BETTER = {"cost_per_step", "p95_latency_ms", "p50_latency_ms"}
HIGHER_IS_BETTER = {"tool_accuracy", "completion", "validity"}
MAX_DROP = 0.05
MAX_RISE = 0.20


@dataclass
class RegressionReport:
    regressions: list[tuple[str, float, float]] = field(default_factory=list)

    @property
    def regressed(self) -> bool:
        return bool(self.regressions)


def compare_runs(previous: RunReport, current: RunReport) -> RegressionReport:
    report = RegressionReport()
    eps = 1e-9          # binary-float noise: 0.90-0.85 must count as exactly 0.05
    for metric, prev in previous.averages.items():
        if metric not in current.averages:
            continue
        cur = current.averages[metric]
        if metric in LOWER_IS_BETTER:
            if prev == 0.0:
                regressed = cur > 0.0
            else:
                regressed = (cur - prev) / prev > MAX_RISE + eps
        else:
            regressed = prev - cur > MAX_DROP + eps
        if regressed:
            report.regressions.append((metric, prev, cur))
    return report
