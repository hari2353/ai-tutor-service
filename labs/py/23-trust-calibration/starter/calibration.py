"""Trust calibration: ECE, abstention policy, selective prediction."""

ABSTAIN = "ABSTAIN"


def ece(pairs, n_bins=10):
    """Expected calibration error.

    pairs: list of (confidence in [0,1], correct: bool).
    Bin confidences into n_bins equal-width bins over [0,1]; conf == 1.0
    goes in the last bin. ECE = sum over non-empty bins of
    (bin_size / N) * |mean bin confidence - bin accuracy|.
    """


class AbstentionPolicy:
    """Answer only when confidence >= threshold.

    should_answer(conf) -> bool: conf >= threshold (inclusive boundary).

    tune_threshold(data, target_accuracy) -> the LARGEST threshold such
    that the items with conf >= threshold have accuracy >= target.
    data: list of (conf, correct). Candidates are the distinct
    confidences; an empty answered set never qualifies. None if nothing
    qualifies.
    """

    def __init__(self, threshold):
        ...

    def should_answer(self, conf):
        ...

    def tune_threshold(self, data, target_accuracy):
        ...


def selective_metrics(data, threshold):
    """{"coverage": fraction of items answered (conf >= threshold),
    "risk": error rate among answered items}. Risk is 0.0 when nothing
    is answered."""


def risk_coverage_points(data):
    """One (coverage, risk) point per distinct confidence threshold,
    strictest threshold first — the risk–coverage curve."""


def classify_with_abstention(classifier, x, policy):
    """classifier exposes .confidence(x) and .predict(x).
    Return classifier.predict(x) when policy.should_answer(confidence),
    else the sentinel ABSTAIN."""
