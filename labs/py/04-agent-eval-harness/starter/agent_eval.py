"""Lab 04 — agent trajectory eval harness. Fill in every TODO. Tests define done.

Rules:
  * No LLM, no network, no time.sleep — latencies and costs come from fixtures.
  * Everything is pure stdlib.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------- data
@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict
    result: Any
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class TaskSpec:
    """How to grade one task's final answer."""
    expected_answer: str
    mode: str = "exact"          # "exact" | "contains" | "numeric"
    tolerance: float = 0.01
    relevant_args: Optional[dict[str, set[str]]] = None   # tool -> arg names that matter


@dataclass
class Trajectory:
    task_id: str
    steps: list[ToolCall]
    final_answer: Any
    task_spec: Optional[TaskSpec] = None


# --------------------------------------------------------------------------- task completion
def task_completion(expected: Any, actual: Any, mode: str = "exact",
                    tolerance: float = 0.01) -> bool:
    """Grade a final answer. Modes: exact, contains, numeric (within tolerance).
    Unknown mode -> ValueError."""
    # TODO(step 3)
    raise NotImplementedError


# --------------------------------------------------------------------------- tool call accuracy
def tool_call_accuracy(gold_steps: list[ToolCall], actual_steps: list[ToolCall],
                       relevant_args: Optional[dict[str, set[str]]] = None) -> float:
    """Fraction of gold steps matched, in order, by the run's steps.

    Fuzzy arg matching: a gold step matches an actual step when the tool names
    are equal and every RELEVANT arg is equal. Relevant args come from
    `relevant_args[tool_name]` — when a tool has no entry, ALL args are
    relevant. Extra actual args never hurt; a wrong relevant arg is a
    mismatch; a missing gold step is a miss. Empty gold -> 0.0.
    """
    # TODO(step 2)
    raise NotImplementedError


# --------------------------------------------------------------------------- trajectory validity
@dataclass
class TrajectoryValidityReport:
    violations: list[tuple[int, str, str]] = field(default_factory=list)  # (i, from, to)

    @property
    def valid(self) -> bool:
        # TODO(step 4): no violations
        raise NotImplementedError


def trajectory_validity(steps: list[ToolCall],
                        allowed: dict[str, set[str]],
                        entry: str = "init") -> TrajectoryValidityReport:
    """Walk the trajectory against the allowed-transitions spec.

    State starts at `entry`. Each step's tool must be in allowed[state];
    otherwise record (step_index, from_state, to_tool) as a violation and
    STAY on the current state (so one illegal call does not cascade).
    On a legal step, state becomes that tool's name.
    """
    # TODO(step 4)
    raise NotImplementedError


# --------------------------------------------------------------------------- cost & latency
def total_cost(traj: Trajectory) -> float:
    """Sum of step costs."""
    # TODO(step 5)
    raise NotImplementedError


def cost_per_step(traj: Trajectory) -> float:
    """total_cost / max(1, len(steps)); 0.0 when there are no steps."""
    # TODO(step 5)
    raise NotImplementedError


def latency_p50(steps: list[ToolCall]) -> float:
    """Median latency_ms; 0.0 for an empty list."""
    # TODO(step 5)
    raise NotImplementedError


def latency_p95(steps: list[ToolCall]) -> float:
    """Nearest-rank p95: sorted[ceil(0.95*n)-1]; 0.0 for an empty list."""
    # TODO(step 5)
    raise NotImplementedError


# --------------------------------------------------------------------------- eval suite
@dataclass
class TaskRow:
    task_id: str
    tool_accuracy: float
    completion: float          # 1.0 or 0.0
    valid: float               # 1.0 or 0.0
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
        """Report['tool_accuracy'] -> the average."""
        # TODO(step 6)
        raise NotImplementedError


class EvalSuite:
    """Aggregates per-task scores into one report with pass/fail per metric."""

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
        """golden_set maps task_id -> {"steps": [ToolCall...],
        "allowed": {...}, "entry": "init"} (allowed/entry optional).
        Completion grading uses the trajectory's task_spec when present,
        else the golden entry's "expected_answer"/"mode"/"tolerance"."""
        # TODO(step 6): score each task, average each metric, apply thresholds.
        #                cost_per_step and p95_latency_ms are upper bounds (<=);
        #                tool_accuracy, completion, validity are lower bounds (>=).
        #                fail_reasons: "tool_accuracy avg X < Y" style, one per failing metric.
        raise NotImplementedError


# --------------------------------------------------------------------------- regression
@dataclass
class RegressionReport:
    regressions: list[tuple[str, float, float]] = field(default_factory=list)  # (metric, prev, cur)

    @property
    def regressed(self) -> bool:
        # TODO(step 7): any regressions
        raise NotImplementedError


LOWER_IS_BETTER = {"cost_per_step", "p95_latency_ms", "p50_latency_ms"}
HIGHER_IS_BETTER = {"tool_accuracy", "completion", "validity"}
MAX_DROP = 0.05          # higher-is-better: absolute drop beyond this regresses
MAX_RISE = 0.20          # lower-is-better: relative rise beyond this regresses


def compare_runs(previous: RunReport, current: RunReport) -> RegressionReport:
    """Compare metric averages. A higher-is-better metric regresses when
    prev - cur > MAX_DROP (0.05). A lower-is-better metric regresses when
    (cur - prev) / prev > MAX_RISE (0.20) — prev of exactly 0.0 compares
    absolutely: any cur > 0 regresses. Only metrics present in BOTH reports
    are compared."""
    # TODO(step 7)
    raise NotImplementedError
