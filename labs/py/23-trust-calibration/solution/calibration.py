"""Trust calibration: ECE, abstention policy, selective prediction."""

ABSTAIN = "ABSTAIN"


def _bin_index(conf, n_bins):
    return max(0, min(int(conf * n_bins + 1e-9), n_bins - 1))


def ece(pairs, n_bins=10):
    total = len(pairs)
    if total == 0:
        return 0.0
    bins = [[] for _ in range(n_bins)]
    for conf, correct in pairs:
        bins[_bin_index(conf, n_bins)].append((conf, correct))
    err = 0.0
    for b in bins:
        if not b:
            continue
        mean_conf = sum(c for c, _ in b) / len(b)
        acc = sum(1 for _, ok in b if ok) / len(b)
        err += (len(b) / total) * abs(mean_conf - acc)
    return err


class AbstentionPolicy:
    def __init__(self, threshold):
        self.threshold = threshold

    def should_answer(self, conf):
        return conf >= self.threshold

    def tune_threshold(self, data, target_accuracy):
        best = None
        for t in sorted({c for c, _ in data}):    # ascending: last qualifying wins
            answered = [ok for c, ok in data if c >= t]
            if not answered:
                continue
            acc = sum(answered) / len(answered)
            if acc >= target_accuracy:
                best = t
        return best


def selective_metrics(data, threshold):
    answered = [ok for c, ok in data if c >= threshold]
    n = len(data)
    coverage = (len(answered) / n) if n else 0.0
    risk = (sum(1 for ok in answered if not ok) / len(answered)) if answered else 0.0
    return {"coverage": coverage, "risk": risk}


def risk_coverage_points(data):
    points = []
    for t in sorted({c for c, _ in data}, reverse=True):    # strictest first
        m = selective_metrics(data, t)
        points.append((m["coverage"], m["risk"]))
    return points


def classify_with_abstention(classifier, x, policy):
    if policy.should_answer(classifier.confidence(x)):
        return classifier.predict(x)
    return ABSTAIN
