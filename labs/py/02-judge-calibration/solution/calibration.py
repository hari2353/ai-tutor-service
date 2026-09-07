"""Lab 02 — reference solution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class LabeledExample:
    question: str
    candidate_answer: str
    gold_score: int


class Judge(Protocol):
    name: str

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        ...


def _clamp(n: int, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, n))


class GoldenJudge:
    name = "golden"

    def __init__(self, dataset: list[LabeledExample]) -> None:
        self.dataset = dataset
        self._gold: dict[tuple[str, str], int] = {}
        for ex in dataset:
            self._gold.setdefault((ex.question, ex.candidate_answer), ex.gold_score)

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        return self._gold[(question, candidate_answer)]

    def grade_pair(self, question: str, a: str, b: str,
                   rubric: str) -> tuple[int, int]:
        """Both answers graded by their gold labels — symmetric by
        construction, so the golden judge never flips. Answers not in the
        dataset default to 3 (the bias sweep may use fresh pairs)."""
        def safe(ans: str) -> int:
            try:
                return self.grade(question, ans, rubric)
            except KeyError:
                return 3
        return safe(a), safe(b)


class PositionBiasedJudge:
    def __init__(self, inner: Judge, bonus: int = 1) -> None:
        self.inner = inner
        self.bonus = bonus
        self._missing: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return f"{self.inner.name}+position"

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        return self.inner.grade(question, candidate_answer, rubric)

    def grade_pair(self, question: str, a: str, b: str, rubric: str) -> tuple[int, int]:
        def safe(ans: str) -> int:
            try:
                return self.inner.grade(question, ans, rubric)
            except KeyError:
                self._missing.append((question, ans))
                return 3

        s_a = _clamp(safe(a) + self.bonus)
        s_b = _clamp(safe(b))
        return s_a, s_b


class VerbosityBiasedJudge:
    name = "verbosity"

    def __init__(self, baseline_words: int = 10, bump_per_20_words: int = 1,
                 base_score: int = 1, cap: int = 5) -> None:
        self.baseline_words = baseline_words
        self.bump_per_20_words = bump_per_20_words
        self.base_score = base_score
        self.cap = cap

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        wc = len(candidate_answer.split())
        score = self.base_score + self.bump_per_20_words * (
            (wc - self.baseline_words) // 20)
        return _clamp(score, 1, self.cap)


class SelfPreferenceJudge:
    def __init__(self, style_markers: list[str], inner: Optional[Judge] = None) -> None:
        self.style_markers = style_markers
        self.inner = inner

    @property
    def name(self) -> str:
        if self.inner is not None:
            return f"selfpref({self.inner.name})"
        return "selfpref(default)"

    def grade(self, question: str, candidate_answer: str, rubric: str) -> int:
        low = candidate_answer.lower()
        if any(m.lower() in low for m in self.style_markers):
            return 5
        if self.inner is not None:
            return self.inner.grade(question, candidate_answer, rubric)
        return 3


@dataclass
class PositionBiasReport:
    flips: int
    total: int
    per_question: list[tuple[str, bool]]
    flip_rate: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.flip_rate <= self.threshold


@dataclass
class CalibrationReport:
    judge_name: str
    n: int
    per_class_accuracy: dict[int, float]
    confusion_matrix: list[list[int]]
    kappa: float
    bias_report: Optional[PositionBiasReport] = None
    kappa_threshold: float = 0.6

    @property
    def flip_rate(self) -> Optional[float]:
        return None if self.bias_report is None else self.bias_report.flip_rate

    @property
    def passed(self) -> bool:
        if self.kappa < self.kappa_threshold:
            return False
        if self.bias_report is not None and not self.bias_report.passed:
            return False
        return True

    @property
    def fail_reasons(self) -> list[str]:
        reasons = []
        if self.kappa < self.kappa_threshold:
            reasons.append(f"kappa {_fmt(self.kappa)} < {_fmt(self.kappa_threshold)}")
        if self.bias_report is not None and not self.bias_report.passed:
            reasons.append(
                f"flip_rate {_fmt(self.bias_report.flip_rate)} > "
                f"{_fmt(self.bias_report.threshold)}")
        return reasons


def _fmt(n: float) -> str:
    """3 decimals without trailing zeros; falls back to the raw value when
    rounding to 3 decimals would hide the real number (e.g. 0.5999)."""
    rounded = round(float(n), 3)
    if abs(rounded - float(n)) > 1e-12:
        return repr(round(float(n), 6))
    s = f"{n:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"


def cohen_kappa(gold: list[int], judged: list[int]) -> float:
    n = len(gold)
    if n == 0 or len(judged) != n:
        raise ValueError("kappa needs two non-empty, equal-length lists")
    po = sum(1 for g, j in zip(gold, judged) if g == j) / n
    gold_marg: dict[int, float] = {}
    judged_marg: dict[int, float] = {}
    classes = sorted(set(gold) | set(judged))
    for c in classes:
        gold_marg[c] = sum(1 for g in gold if g == c) / n
        judged_marg[c] = sum(1 for j in judged if j == c) / n
    pe = sum(gold_marg[c] * judged_marg[c] for c in classes)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return 1.0 - (1.0 - po) / (1.0 - pe)


def confusion_matrix(gold: list[int], judged: list[int]) -> list[list[int]]:
    m = [[0] * 5 for _ in range(5)]
    for g, j in zip(gold, judged):
        m[g - 1][j - 1] += 1
    return m


def per_class_accuracy(gold: list[int], judged: list[int]) -> dict[int, float]:
    out: dict[int, float] = {}
    for c in sorted(set(gold)):
        idx = [i for i, g in enumerate(gold) if g == c]
        out[c] = sum(1 for i in idx if judged[i] == c) / len(idx)
    return out


def calibrate(judge: Judge, dataset: list[LabeledExample],
              pair_questions: Optional[list[tuple[str, str, str]]] = None,
              rubric: str = "grade 1-5 for correctness and completeness",
              flip_threshold: float = 0.10) -> CalibrationReport:
    gold = [ex.gold_score for ex in dataset]
    judged = [judge.grade(ex.question, ex.candidate_answer, rubric) for ex in dataset]

    bias_report: Optional[PositionBiasReport] = None
    if pair_questions is not None and hasattr(judge, "grade_pair"):
        flips = 0
        per_question: list[tuple[str, bool]] = []
        for question, a, b in pair_questions:
            s_a_first, s_b_first = judge.grade_pair(question, a, b, rubric)
            s_b_second, s_a_second = judge.grade_pair(question, b, a, rubric)
            flipped = (s_a_first > s_b_first and s_a_second < s_b_second) or \
                      (s_a_first < s_b_first and s_a_second > s_b_second)
            if flipped:
                flips += 1
            per_question.append((question, flipped))
        total = len(pair_questions)
        rate = flips / total if total else 0.0
        bias_report = PositionBiasReport(flips=flips, total=total,
                                         per_question=per_question,
                                         flip_rate=rate, threshold=flip_threshold)

    return CalibrationReport(
        judge_name=judge.name,
        n=len(dataset),
        per_class_accuracy=per_class_accuracy(gold, judged),
        confusion_matrix=confusion_matrix(gold, judged),
        kappa=cohen_kappa(gold, judged),
        bias_report=bias_report,
    )
