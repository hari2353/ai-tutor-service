"""Lab 10 -- a golden-set eval harness against a scripted fake model, a
regression gate, and a deliberately biased fake LLM-as-judge used to
*measure* position bias and verbosity bias with real numbers.
Fill in every TODO. Tests define done.

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
    """TODO(step 1a): 1.0 if output.strip() == case.expected.strip(), else 0.0."""
    raise NotImplementedError


def contains_scorer(output: str, case: "GoldenCase") -> float:
    """TODO(step 1b): 1.0 if case.expected (stripped, casefolded) is a
    substring of output (stripped, casefolded), else 0.0."""
    raise NotImplementedError


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
        """TODO(step 2): append input_text to self.calls, then:
          - if input_text is a scripted key, return its response
          - elif self.default is not None, return self.default
          - else raise KeyError with a message naming the unscripted input
        """
        raise NotImplementedError


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
        """TODO(step 3):
          - for each case: call model(case.input), score it with
            self.scorer(output, case), build a CaseResult (passed = score
            >= self.pass_threshold)
          - aggregate metrics: "mean_score" = average of all scores,
            "pass_rate" = fraction of results where passed is True
          - guard against division by zero when `cases` is empty --
            both metrics should be 0.0, and results should be []
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- regression gate
@dataclass
class RegressionResult:
    passed: bool
    failures: list[str]


def check_regression(current_metrics: dict[str, float], baseline: dict[str, float],
                      tolerance: float = 0.0) -> RegressionResult:
    """TODO(step 4a): for every (name, baseline_value) in baseline:
      - if name is missing from current_metrics: record a failure
        "<name>: missing from current metrics"
      - elif current_metrics[name] < baseline_value - tolerance: record a
        failure "<name>: dropped from <baseline_value> to <current_value>
        (tolerance <tolerance>)"
      Return RegressionResult(passed=(no failures), failures=failures).
    """
    raise NotImplementedError


def save_baseline(path: str, metrics: dict[str, float]) -> None:
    # TODO(step 4b): json.dump metrics to the file at `path`
    raise NotImplementedError


def load_baseline(path: str) -> dict[str, float]:
    # TODO(step 4c): json.load metrics from the file at `path`
    raise NotImplementedError


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
    """A deliberately biased fake LLM-as-judge.

    TODO(step 5): compute
      score_a = _base_quality(answer_a) + POSITION_BONUS + VERBOSITY_WEIGHT * len(answer_a)
      score_b = _base_quality(answer_b) + VERBOSITY_WEIGHT * len(answer_b)
    then return {"winner": "A" if score_a > score_b else "B" if score_b >
    score_a else "tie", "score_a": score_a, "score_b": score_b}.
    """
    raise NotImplementedError


def measure_position_bias(judge: Callable[[str, str, str], dict], question: str,
                           answer_pairs: list[tuple[str, str]]) -> dict:
    """TODO(step 6a): for each (a, b) pair in answer_pairs, call
    judge(question, a, b) AND judge(question, b, a) (2 calls per pair).
    Count how many of ALL those calls had winner == "A". Return
    {"first_slot_win_rate": count / total_calls, "n": total_calls}
    (use 0.0 for the rate if there were no calls)."""
    raise NotImplementedError


def measure_verbosity_bias(judge: Callable[[str, str, str], dict], question: str,
                            short_answer: str, long_answer: str) -> dict:
    """TODO(step 6b): call judge(question, short_answer, long_answer)
    (round_1: short=A, long=B) and judge(question, long_answer,
    short_answer) (round_2: long=A, short=B). Count how many of those 2
    rounds the LONG answer won (round_1 winner=="B", round_2
    winner=="A"). Return {"long_answer_win_rate": long_wins / 2,
    "round_1": round_1, "round_2": round_2}."""
    raise NotImplementedError
