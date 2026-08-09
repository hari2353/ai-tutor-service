"""Lab 10 -- a golden-set eval harness against a scripted fake model, a
regression gate, and a deliberately biased fake LLM-as-judge used to
*measure* position bias and verbosity bias with real numbers.

No network, no API keys: ScriptedModel plays back a fixed dict of
responses and BiasedJudge is a pure function with hand-tuned bias
constants -- both fully deterministic and free to test.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# --------------------------------------------------------------------------- golden set + scorers
@dataclass
class GoldenCase:
    id: str
    input: str
    expected: str
    tags: list[str] = field(default_factory=list)


Scorer = Callable[[str, "GoldenCase"], float]


def exact_match_scorer(output: str, case: "GoldenCase") -> float:
    """1.0 if output matches expected exactly (surrounding whitespace
    ignored), else 0.0."""
    return 1.0 if output.strip() == case.expected.strip() else 0.0


def contains_scorer(output: str, case: "GoldenCase") -> float:
    """1.0 if the expected text appears anywhere in the output
    (case-insensitive), else 0.0 -- a looser, more forgiving scorer than
    exact match."""
    return 1.0 if case.expected.strip().lower() in output.strip().lower() else 0.0


# --------------------------------------------------------------------------- scripted fake model
class ScriptedModel:
    """Plays back a fixed dict of {input: output}. Deterministic and free
    -- the whole point of testing an eval harness without hitting a real
    model API. Records every input it was called with."""

    def __init__(self, responses: dict[str, str], default: Optional[str] = None) -> None:
        self.responses = dict(responses)
        self.default = default
        self.calls: list[str] = []

    def __call__(self, input_text: str) -> str:
        self.calls.append(input_text)
        if input_text in self.responses:
            return self.responses[input_text]
        if self.default is not None:
            return self.default
        raise KeyError(f"ScriptedModel has no scripted response for input: {input_text!r}")


# --------------------------------------------------------------------------- eval runner
@dataclass
class CaseResult:
    case_id: str
    output: str
    score: float
    passed: bool


@dataclass
class EvalReport:
    results: list[CaseResult]
    metrics: dict[str, float]


class EvalRunner:
    """Runs a model over a golden set, scores each case, and aggregates
    metrics. `pass_threshold` decides whether a case counts as "passed"
    for the pass_rate metric -- score is kept continuous either way."""

    def __init__(self, scorer: Scorer, pass_threshold: float = 1.0) -> None:
        self.scorer = scorer
        self.pass_threshold = pass_threshold

    def run(self, model: Callable[[str], str], cases: list[GoldenCase]) -> EvalReport:
        results: list[CaseResult] = []
        for case in cases:
            output = model(case.input)
            score = self.scorer(output, case)
            results.append(CaseResult(
                case_id=case.id, output=output, score=score,
                passed=score >= self.pass_threshold,
            ))

        n = len(results)
        mean_score = sum(r.score for r in results) / n if n else 0.0
        pass_rate = sum(1 for r in results if r.passed) / n if n else 0.0
        return EvalReport(results=results, metrics={"mean_score": mean_score, "pass_rate": pass_rate})


# --------------------------------------------------------------------------- regression gate
@dataclass
class RegressionResult:
    passed: bool
    failures: list[str]


def check_regression(current_metrics: dict[str, float], baseline: dict[str, float],
                      tolerance: float = 0.0) -> RegressionResult:
    """Fails (passed=False) if any baseline metric dropped by more than
    `tolerance` in the current run. A metric missing from current_metrics
    also counts as a failure -- you can't silently stop reporting a metric
    to dodge the gate."""
    failures: list[str] = []
    for name, baseline_value in baseline.items():
        current_value = current_metrics.get(name)
        if current_value is None:
            failures.append(f"{name}: missing from current metrics")
            continue
        if current_value < baseline_value - tolerance:
            failures.append(
                f"{name}: dropped from {baseline_value} to {current_value} (tolerance {tolerance})"
            )
    return RegressionResult(passed=not failures, failures=failures)


def save_baseline(path: str, metrics: dict[str, float]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f)


def load_baseline(path: str) -> dict[str, float]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- biased fake judge
# These constants are the whole bias, in plain sight -- a real judge model
# hides the same effect inside its weights instead of a readable formula.
POSITION_BONUS = 0.5     # thumb on the scale for whichever answer is shown FIRST (slot A)
VERBOSITY_WEIGHT = 0.01  # points of score per character of answer length


def _base_quality(answer: str) -> float:
    """Stand-in for 'how correct/good is this answer'. Deliberately
    constant -- every answer this judge sees in the bias tests is equally
    correct, so any winner it picks is attributable ONLY to position or
    length, never to actual quality."""
    return 1.0


def biased_judge(question: str, answer_a: str, answer_b: str) -> dict:
    """A deliberately biased fake LLM-as-judge. Scores both answers with
    the SAME quality baseline, but tilts the score toward slot A
    (position bias) and toward longer text (verbosity bias). Returns
    {"winner": "A"|"B"|"tie", "score_a": float, "score_b": float}."""
    score_a = _base_quality(answer_a) + POSITION_BONUS + VERBOSITY_WEIGHT * len(answer_a)
    score_b = _base_quality(answer_b) + VERBOSITY_WEIGHT * len(answer_b)
    if score_a > score_b:
        winner = "A"
    elif score_b > score_a:
        winner = "B"
    else:
        winner = "tie"
    return {"winner": winner, "score_a": score_a, "score_b": score_b}


def measure_position_bias(judge: Callable[[str, str, str], dict], question: str,
                           answer_pairs: list[tuple[str, str]]) -> dict:
    """For each (a, b) pair, ask the judge BOTH ways round (a,b) and (b,a)
    and report how often the FIRST slot wins -- if the judge were
    unbiased, and the pairs are equal-quality/equal-length, this should be
    ~0.5. A biased judge skews it hard toward 1.0."""
    first_slot_wins = 0
    total = 0
    for a, b in answer_pairs:
        for x, y in [(a, b), (b, a)]:
            result = judge(question, x, y)
            total += 1
            if result["winner"] == "A":
                first_slot_wins += 1
    return {"first_slot_win_rate": first_slot_wins / total if total else 0.0, "n": total}


def measure_verbosity_bias(judge: Callable[[str, str, str], dict], question: str,
                            short_answer: str, long_answer: str) -> dict:
    """Runs the judge in BOTH slot orders for the same (short, long) pair,
    which cancels out position bias (each answer gets one turn in each
    slot) and isolates how often the longer answer wins purely on length."""
    r1 = judge(question, short_answer, long_answer)   # short=A, long=B
    r2 = judge(question, long_answer, short_answer)    # long=A, short=B
    long_wins = 0
    if r1["winner"] == "B":
        long_wins += 1
    if r2["winner"] == "A":
        long_wins += 1
    return {"long_answer_win_rate": long_wins / 2, "round_1": r1, "round_2": r2}
