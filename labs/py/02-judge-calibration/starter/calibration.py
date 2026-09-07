"""Lab 02 — judge calibration harness. Fill in every TODO. Tests define done.

Rules:
  * No LLM, no network, no randomness — every judge is a deterministic fake.
  * Scores are ints 1..5.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


# --------------------------------------------------------------------------- types
@dataclass(frozen=True)
class LabeledExample:
    """One graded answer: what the candidate said, and the human gold score."""
    question: str
    candidate_answer: str
    gold_score: int          # 1..5, human label


class Judge(Protocol):
    """Anything that can score (question, candidate_answer) against a rubric 1..5."""
    name: str

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        ...


# --------------------------------------------------------------------------- judges
class GoldenJudge:
    """Returns the dataset's own gold labels — the humans. calibrate() against
    this must give perfect agreement; this fake is your ground truth."""

    name = "golden"

    def __init__(self, dataset: list[LabeledExample]) -> None:
        self.dataset = dataset
        # TODO(step 2): store a fast lookup so grade() finds the example's gold score.
        #                (question, candidate_answer) -> gold_score is enough.

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        # TODO(step 2): return the gold score for this exact example,
        #                KeyError if it is not in the dataset.
        raise NotImplementedError

    def grade_pair(self, question: str, a: str, b: str,
                   rubric: str) -> tuple[int, int]:
        """Both answers graded by gold labels — symmetric by construction, so
        the golden judge never flips. Answers not in the dataset default to 3
        (the bias sweep may use fresh pair texts)."""
        # TODO(step 2b): (grade(q,a), grade(q,b)) with a 3-fallback on KeyError.
        raise NotImplementedError


class PositionBiasedJudge:
    """Delegates single grading to `inner`, but in pairwise mode always
    prefers the answer presented FIRST. Models the classic "order bias":
    the judge favours whatever it read first."""

    def __init__(self, inner: Judge, bonus: int = 1) -> None:
        self.inner = inner
        self.bonus = bonus

    @property
    def name(self) -> str:
        # TODO(step 3): "<inner.name>+position" — the test asserts this format
        #                so calibrate() reports say WHICH judge graded.
        raise NotImplementedError

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        # TODO(step 3): delegate to inner.
        raise NotImplementedError

    def grade_pair(self, question: str, a: str, b: str, rubric: str) -> tuple[int, int]:
        """Grade a and b as a pair. The FIRST-presented answer gets a bonus.
        Returns (score_a, score_b) for this presentation order."""
        # TODO(step 3): s_a = inner.grade(q, a) + bonus, s_b = inner.grade(q, b),
        #                both clamped to 1..5. The first-presented wins ties and all.
        raise NotImplementedError


class VerbosityBiasedJudge:
    """Score is a pure function of word count: longer looks better.
    Deterministic — same word count, same score."""

    name = "verbosity"

    def __init__(self, baseline_words: int = 10, bump_per_20_words: int = 1,
                 base_score: int = 1, cap: int = 5) -> None:
        self.baseline_words = baseline_words
        self.bump_per_20_words = bump_per_20_words
        self.base_score = base_score
        self.cap = cap

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        # TODO(step 4): score = base_score + bump_per_20_words * ((wc - baseline_words) // 20)
        #                clamped to 1..cap. wc = number of whitespace-separated tokens.
        raise NotImplementedError


class SelfPreferenceJudge:
    """Answers containing one of ITS OWN style markers get a 5; everything
    else delegates to inner (or a flat 3). The judge likes answers that
    sound like the judge itself wrote them."""

    def __init__(self, style_markers: list[str], inner: Optional[Judge] = None) -> None:
        self.style_markers = style_markers
        self.inner = inner

    @property
    def name(self) -> str:
        # TODO(step 5): "selfpref(<inner.name>)" with inner, else "selfpref(default)".
        raise NotImplementedError

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        # TODO(step 5): 5 if any marker (case-insensitive substring) appears in the answer;
        #                otherwise inner.grade(...) if inner, else 3.
        raise NotImplementedError


# --------------------------------------------------------------------------- metrics
@dataclass
class PositionBiasReport:
    flips: int
    total: int
    per_question: list[tuple[str, bool]]      # (question, flipped?)
    flip_rate: float                          # flips / total, 0.0 when total == 0
    threshold: float

    @property
    def passed(self) -> bool:
        # TODO(step 7): flip_rate <= threshold
        raise NotImplementedError


@dataclass
class CalibrationReport:
    judge_name: str
    n: int
    per_class_accuracy: dict[int, float]      # gold score -> accuracy on that class
    confusion_matrix: list[list[int]]         # matrix[gold-1][judged-1]
    kappa: float
    bias_report: Optional[PositionBiasReport] = None
    kappa_threshold: float = 0.6

    @property
    def flip_rate(self) -> Optional[float]:
        # TODO(step 8): bias_report.flip_rate if attached, else None
        raise NotImplementedError

    @property
    def passed(self) -> bool:
        # TODO(step 8): kappa >= kappa_threshold AND (bias_report is None
        #                or bias_report.passed)
        raise NotImplementedError

    @property
    def fail_reasons(self) -> list[str]:
        # TODO(step 8): list what failed, in this order:
        #   f"kappa <kappa> < <kappa_threshold>"  (numbers via a helper that
        #   formats 0.6 as '0.6' and keeps 0.5999 as '0.5999')
        #   f"flip_rate <rate> > <threshold>" (only when a bias report is attached)
        raise NotImplementedError


def cohen_kappa(gold: list[int], judged: list[int]) -> float:
    """Cohen's kappa: 1 - (1-po)/(1-pe).
    po = observed agreement; pe = sum over classes of gold_marginal * judged_marginal.
    kappa = 1.0 when pe == po == 1.0 (perfect agreement with degenerate marginals).
    Both lists must be non-empty and the same length."""
    # TODO(step 6)
    raise NotImplementedError


def confusion_matrix(gold: list[int], judged: list[int]) -> list[list[int]]:
    """5x5 counts, matrix[gold-1][judged-1]."""
    # TODO(step 6)
    raise NotImplementedError


def per_class_accuracy(gold: list[int], judged: list[int]) -> dict[int, float]:
    """For each gold score present: correct-on-that-class / examples-with-that-gold.
    Only classes that appear in gold are keys."""
    # TODO(step 6)
    raise NotImplementedError


def calibrate(judge: Judge, dataset: list[LabeledExample],
              pair_questions: Optional[list[tuple[str, str, str]]] = None,
              rubric: str = "grade 1-5 for correctness and completeness",
              flip_threshold: float = 0.10) -> CalibrationReport:
    """Grade every example once, compute agreement metrics, and (when
    pair_questions is given) run the position-bias sweep: grade every pair
    both ways and count flips.

    pair_questions: list of (question, a, b) — grade (a,b) then (b,a).
    The judge needs a grade_pair method for the sweep; judges without one
    get no bias report (bias_report=None).
    """
    # TODO(step 6/7): grade every example, build CalibrationReport.
    # TODO(step 7): for the pair sweep call judge.grade_pair(question, a, b, rubric)
    #               then judge.grade_pair(question, b, a, rubric); a flip is when
    #               (s_a > s_b) != (s_a' > s_b') — i.e. the strict ordering reversed.
    #               ties on both sides are NOT flips.
    raise NotImplementedError
