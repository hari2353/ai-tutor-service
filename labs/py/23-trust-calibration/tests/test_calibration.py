"""Lab 23 (trust calibration) tests. Pure stdlib, no sleeps, no wall-clock."""
import pytest


# ------------------------------------------------------------------ fixtures
def _mix(n_correct, n_wrong, conf):
    """n_correct + n_wrong items, all at the same confidence."""
    return [(conf, True)] * n_correct + [(conf, False)] * n_wrong


def _calibrated():
    """Every bin's mean confidence equals its accuracy — ECE must be 0.

    Bin 0 (conf 0.0): 10 wrong items, accuracy 0.0.
    Bin 7 (conf 0.7): 7 correct + 3 wrong, accuracy 0.7.
    Bin 10 (conf 1.0): 10 correct items, accuracy 1.0.
    """
    return _mix(0, 10, 0.0) + _mix(7, 3, 0.7) + _mix(10, 0, 1.0)


# ------------------------------------------------------------------ ece
def test_ece_zero_when_perfectly_calibrated(C):
    # hand-check: bin conf 0.0/acc 0.0, bin 0.7/acc 0.7, bin 1.0/acc 1.0
    assert C.ece(_calibrated()) == pytest.approx(0.0)


def test_ece_overconfident(C):
    """All items claim 0.9; half are wrong. One bin, conf 0.9, acc 0.5,
    ECE = |0.9 - 0.5| = 0.4."""
    data = _mix(5, 5, 0.9)
    assert C.ece(data) == pytest.approx(0.4)


def test_ece_underconfident_symmetric(C):
    """Claim 0.3, all correct: |0.3 - 1.0| = 0.7."""
    data = _mix(10, 0, 0.3)
    assert C.ece(data) == pytest.approx(0.7)


def test_ece_conf_one_lands_in_last_bin(C):
    """conf 1.0 must not fall off the end (bin index clamped to 9)."""
    data = _mix(10, 0, 1.0)                     # calibrated: bin 1.0, acc 1.0
    assert C.ece(data) == pytest.approx(0.0)
    data = _mix(5, 5, 1.0)                      # |1.0 - 0.5| = 0.5
    assert C.ece(data) == pytest.approx(0.5)


def test_ece_weighted_mean(C):
    """Half the data perfectly calibrated (bin 1.0), half off by 0.4:
    ECE = 0.5*0 + 0.5*0.4 = 0.2."""
    data = _mix(5, 5, 0.9) + _mix(10, 0, 1.0)
    assert C.ece(data) == pytest.approx(0.2)


# ------------------------------------------------------------------ policy
def test_should_answer_boundary_is_inclusive(C):
    p = C.AbstentionPolicy(0.5)
    assert p.should_answer(0.5) is True         # conf == threshold answers


def test_should_answer_above_and_below(C):
    p = C.AbstentionPolicy(0.5)
    assert p.should_answer(0.9) is True
    assert p.should_answer(0.4) is False


def test_tune_threshold_finds_0_8(C):
    """conf >= 0.8: (0.8,T)x3 -> accuracy 1.0. conf >= 0.7 adds (0.7,T),
    accuracy 3/4 = 0.75. Target 0.9 therefore lands exactly on 0.8."""
    data = [(0.8, True)] * 3 + [(0.7, True), (0.6, False), (0.5, False)]
    t = C.AbstentionPolicy(0.0).tune_threshold(data, 0.9)
    assert t == pytest.approx(0.8)


def test_tune_threshold_prefers_largest(C):
    """Both 0.9 and 0.85 give accuracy 1.0; the LARGER threshold wins.
    0.8 is excluded: (0.8,T),(0.8,T),(0.8,F) -> 3/4 < 1.0."""
    data = [(0.9, True), (0.85, True),
            (0.8, False), (0.8, True), (0.8, True),
            (0.6, True), (0.5, False)]
    t = C.AbstentionPolicy(0.0).tune_threshold(data, 1.0)
    assert t == pytest.approx(0.9)


def test_tune_threshold_unreachable_returns_none(C):
    """Every subset includes a wrong item: accuracy caps at 3/4."""
    data = [(0.9, False), (0.8, True), (0.7, True), (0.6, True)]
    assert C.AbstentionPolicy(0.0).tune_threshold(data, 0.95) is None
    # same data, reachable target: conf >= 0.6 -> accuracy 3/4
    assert C.AbstentionPolicy(0.0).tune_threshold(data, 0.7) == pytest.approx(0.6)


def test_tuned_threshold_answers_correctly(C):
    """A tuned policy must actually deliver on its target."""
    data = [(0.8, True)] * 3 + [(0.7, True), (0.6, False), (0.5, False)]
    t = C.AbstentionPolicy(0.0).tune_threshold(data, 0.9)
    p = C.AbstentionPolicy(t)
    assert p.should_answer(0.8) is True
    assert p.should_answer(0.7) is False


# ------------------------------------------------------------------ selective
def test_selective_metrics_basic(C):
    """2 of 4 answered (conf >= 0.7); 1 of those wrong.
    coverage = 2/4, risk = 1/2."""
    data = [(0.9, True), (0.7, False), (0.5, True), (0.5, False)]
    m = C.selective_metrics(data, 0.7)
    assert m["coverage"] == pytest.approx(0.5)
    assert m["risk"] == pytest.approx(0.5)


def test_selective_metrics_full_coverage(C):
    data = [(0.9, True), (0.7, False)]
    m = C.selective_metrics(data, 0.0)
    assert m["coverage"] == pytest.approx(1.0)
    assert m["risk"] == pytest.approx(0.5)


def test_selective_metrics_empty_answered(C):
    """Nothing answered: coverage 0, risk defined as 0 (not a crash)."""
    data = [(0.9, True), (0.5, False)]
    m = C.selective_metrics(data, 0.95)
    assert m["coverage"] == pytest.approx(0.0)
    assert m["risk"] == pytest.approx(0.0)


def test_risk_zero_when_only_correct_answered(C):
    data = [(0.9, True), (0.8, True), (0.5, False), (0.4, False)]
    m = C.selective_metrics(data, 0.75)
    assert m["risk"] == pytest.approx(0.0)


def test_coverage_monotonic_non_increasing(C):
    """As the threshold rises, coverage can only shrink."""
    data = [(0.9, True), (0.8, False), (0.7, True), (0.6, False)]
    coverages = [C.selective_metrics(data, t)["coverage"]
                 for t in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
    assert all(a >= b for a, b in zip(coverages, coverages[1:]))
    assert coverages[0] == pytest.approx(1.0)
    assert coverages[-1] == pytest.approx(0.0)


def test_risk_coverage_curve_endpoints(C):
    """Data: 3x(0.9,T), (0.7,T), (0.7,F), (0.5,T), (0.5,F), (0.3,F).
    Threshold 0.3 (everything answered): coverage 1.0, risk 3/8 = 0.375.
    Threshold 0.9 (only the certain survive): coverage 3/8, risk 0.0."""
    data = (_mix(3, 0, 0.9) + _mix(1, 1, 0.7)
            + _mix(1, 1, 0.5) + _mix(0, 1, 0.3))
    pts = C.risk_coverage_points(data)
    coverages = [c for c, _ in pts]

    # thresholds 0.9 -> 0.3: strictest first, so coverage only grows
    assert coverages == sorted(coverages)
    assert coverages[0] == pytest.approx(3 / 8)

    by_cov = dict(pts)
    assert by_cov[1.0] == pytest.approx(3 / 8)      # overall error at full coverage
    assert by_cov[3 / 8] == pytest.approx(0.0)      # zero risk when only-correct answered
    # hand-check middle point: threshold 0.7 answers 5, one wrong -> risk 1/5
    assert by_cov[5 / 8] == pytest.approx(0.2)


def test_risk_coverage_points_count(C):
    """One point per distinct confidence, no duplicates."""
    data = [(0.9, True), (0.9, False), (0.7, True), (0.5, False)]
    assert len(C.risk_coverage_points(data)) == 3


# ------------------------------------------------------------------ classifier
class _Clf:
    """confidence(x) is odd(x)/10; predicts 'odd' or 'even'."""

    def confidence(self, x):
        return (x if x % 2 else 10 - x) / 10.0

    def predict(self, x):
        return "odd" if x % 2 else "even"


def test_classify_with_abstention_answers_when_confident(C):
    p = C.AbstentionPolicy(0.8)
    assert C.classify_with_abstention(_Clf(), 9, p) == "odd"    # conf 0.9
    assert C.classify_with_abstention(_Clf(), 0, p) == "even"   # conf 1.0


def test_classify_with_abstention_abstains_below_threshold(C):
    p = C.AbstentionPolicy(0.8)
    assert C.classify_with_abstention(_Clf(), 4, p) == C.ABSTAIN   # conf 0.6
    assert C.classify_with_abstention(_Clf(), 6, p) == C.ABSTAIN   # conf 0.4


def test_classify_boundary_answered(C):
    """conf exactly at the threshold is answered — the inclusive rule
    flows through the classifier path too."""
    p = C.AbstentionPolicy(0.8)
    assert C.classify_with_abstention(_Clf(), 2, p) == "even"      # conf 0.8
