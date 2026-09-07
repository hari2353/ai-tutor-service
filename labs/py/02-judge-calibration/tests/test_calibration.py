"""Lab 02 tests. Deterministic fake judges — no LLM, no network, no sleep."""
import pytest


RUBRIC = "grade 1-5 for correctness and completeness"


def words(n: int, filler: str = "word") -> str:
    return " ".join([filler] * n)


# ------------------------------------------------------------------ golden judge
def test_golden_judge_reproduces_gold_labels(C):
    ds = [C.LabeledExample("q1", "cat sat", 4),
          C.LabeledExample("q2", "dog ran", 2)]
    g = C.GoldenJudge(ds)
    assert g.grade("q1", "cat sat", RUBRIC) == 4
    assert g.grade("q2", "dog ran", RUBRIC) == 2
    with pytest.raises(KeyError):
        g.grade("q1", "not in dataset", RUBRIC)


def test_golden_judge_name(C):
    assert C.GoldenJudge([]).name == "golden"


# ------------------------------------------------------------------ position judge
def test_position_judge_single_grade_delegates(C):
    ds = [C.LabeledExample("q", "answer text", 3)]
    pos = C.PositionBiasedJudge(C.GoldenJudge(ds))
    assert pos.grade("q", "answer text", RUBRIC) == 3


def test_position_judge_first_presented_wins(C):
    ds = [C.LabeledExample("q", "equal quality a", 4),
          C.LabeledExample("q", "equal quality b", 4)]
    pos = C.PositionBiasedJudge(C.GoldenJudge(ds), bonus=1)
    s_a, s_b = pos.grade_pair("q", "equal quality a", "equal quality b", RUBRIC)
    assert s_a > s_b, "the first-presented answer must be favoured"
    # reversed presentation: b is now first
    s_b2, s_a2 = pos.grade_pair("q", "equal quality b", "equal quality a", RUBRIC)
    assert s_b2 > s_a2, "presentation order alone flips the preference"


def test_position_judge_scores_clamped_to_1_5(C):
    ds = [C.LabeledExample("q", "great", 5),
          C.LabeledExample("q", "terrible", 1)]
    pos = C.PositionBiasedJudge(C.GoldenJudge(ds), bonus=3)
    s_a, s_b = pos.grade_pair("q", "great", "terrible", RUBRIC)
    assert 1 <= s_a <= 5 and 1 <= s_b <= 5
    assert s_a == 5, "5 + bonus clamps to 5, not 8"


def test_position_judge_name_composes(C):
    ds = [C.LabeledExample("q", "a", 3)]
    pos = C.PositionBiasedJudge(C.GoldenJudge(ds))
    assert pos.name == "golden+position"


# ------------------------------------------------------------------ verbosity judge
def test_verbosity_judge_longer_is_higher(C):
    v = C.VerbosityBiasedJudge()
    s10 = v.grade("q", words(10), RUBRIC)
    s50 = v.grade("q", words(50), RUBRIC)
    s200 = v.grade("q", words(200), RUBRIC)
    assert s10 < s50 < s200, "score must correlate with word count"
    assert s200 == 5, "cap at 5"


def test_verbosity_judge_deterministic_same_count_same_score(C):
    v = C.VerbosityBiasedJudge()
    assert v.grade("q", words(30), RUBRIC) == v.grade("q", words(30), RUBRIC)
    assert v.grade("q", words(30), RUBRIC) == v.grade("q", words(31), RUBRIC), \
        "30 and 31 words fall in the same 20-word bucket"


def test_verbosity_judge_ignores_question(C):
    v = C.VerbosityBiasedJudge()
    assert v.grade("any question at all", words(40), RUBRIC) == \
           v.grade("a totally different one", words(40), RUBRIC)


# ------------------------------------------------------------------ self-preference judge
def test_selfpref_judge_five_for_own_style(C):
    sp = C.SelfPreferenceJudge(["In summary,", "To conclude,"])
    assert sp.grade("q", "In summary, the answer is two.", RUBRIC) == 5
    assert sp.grade("q", "Plain answer without markers.", RUBRIC) == 3


def test_selfpref_judge_case_insensitive(C):
    sp = C.SelfPreferenceJudge(["delve deeper"])
    assert sp.grade("q", "We DELVE DEEPER into the data.", RUBRIC) == 5


def test_selfpref_judge_delegates_to_inner(C):
    ds = [C.LabeledExample("q", "plain answer", 2)]
    sp = C.SelfPreferenceJudge(["In summary,"], inner=C.GoldenJudge(ds))
    assert sp.grade("q", "plain answer", RUBRIC) == 2
    assert sp.grade("q", "In summary, decorated", RUBRIC) == 5


def test_selfpref_judge_names(C):
    ds = [C.LabeledExample("q", "a", 3)]
    assert C.SelfPreferenceJudge(["x"]).name == "selfpref(default)"
    assert C.SelfPreferenceJudge(["x"], inner=C.GoldenJudge(ds)).name == \
           "selfpref(golden)"


# ------------------------------------------------------------------ kappa
def test_kappa_perfect_agreement_is_one(C):
    assert C.cohen_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1.0)


def test_kappa_degenerate_perfect(C):
    """All-4 golds judged all-4: po=1, pe=1 — kappa defined as 1.0."""
    assert C.cohen_kappa([4, 4, 4], [4, 4, 4]) == pytest.approx(1.0)


def test_kappa_zero_when_agreement_equals_chance(C):
    """2x2: gold 50/50, judged 50/50, agreed 50% -> kappa = 0."""
    assert C.cohen_kappa([1, 1, 2, 2], [1, 2, 1, 2]) == pytest.approx(0.0)


def test_kappa_negative_when_worse_than_chance(C):
    assert C.cohen_kappa([1, 1, 2, 2], [2, 2, 1, 1]) < 0


def test_kappa_hand_computed(C):
    """gold=[1,2,1,2], judged=[1,1,2,2]: po=0.5, pe=0.5 -> kappa=0."""
    assert C.cohen_kappa([1, 2, 1, 2], [1, 1, 2, 2]) == pytest.approx(0.0)


def test_kappa_rejects_length_mismatch(C):
    with pytest.raises(ValueError):
        C.cohen_kappa([1, 2], [1, 2, 3])


# ------------------------------------------------------------------ confusion matrix
def test_confusion_matrix_hand_computed(C):
    m = C.confusion_matrix([1, 2, 2, 5], [1, 2, 3, 5])
    assert m[0][0] == 1          # gold 1, judged 1
    assert m[1][1] == 1          # gold 2, judged 2
    assert m[1][2] == 1          # gold 2, judged 3
    assert m[4][4] == 1          # gold 5, judged 5
    assert sum(sum(row) for row in m) == 4


def test_confusion_matrix_shape(C):
    m = C.confusion_matrix([1], [1])
    assert len(m) == 5 and all(len(r) == 5 for r in m)


# ------------------------------------------------------------------ per-class accuracy
def test_per_class_accuracy_hand_computed(C):
    acc = C.per_class_accuracy([1, 1, 2, 2], [1, 2, 2, 2])
    assert acc[1] == pytest.approx(0.5)
    assert acc[2] == pytest.approx(1.0)
    assert set(acc) == {1, 2}, "only classes present in gold get keys"


def test_per_class_accuracy_skips_absent_classes(C):
    acc = C.per_class_accuracy([3, 3, 3], [3, 3, 4])
    assert acc == {3: pytest.approx(2 / 3)}


# ------------------------------------------------------------------ calibrate: golden
def test_calibrate_golden_judge_passes_everything(C):
    ds = [C.LabeledExample(f"q{i}", words(20 + i * 5, f"topic{i}"), (i % 5) + 1)
          for i in range(10)]
    pairs = [(f"q{i}", words(20 + i * 5, f"topic{i}"), words(10 + i, "other"))
             for i in range(6)]
    rep = C.calibrate(C.GoldenJudge(ds), ds, pair_questions=pairs)
    assert rep.n == 10
    assert rep.kappa == pytest.approx(1.0)
    assert all(v == 1.0 for v in rep.per_class_accuracy.values())
    assert rep.passed is True
    assert rep.fail_reasons == []
    assert rep.judge_name == "golden"


def test_calibrate_golden_bias_sweep_no_flips(C):
    ds = [C.LabeledExample("q", "a", 4), C.LabeledExample("q", "b", 2),
          C.LabeledExample("q2", "c", 5), C.LabeledExample("q2", "d", 5)]
    pairs = [("q", "a", "b"), ("q2", "c", "d")]
    rep = C.calibrate(C.GoldenJudge(ds), ds, pair_questions=pairs)
    assert rep.bias_report.total == 2
    assert rep.bias_report.flips == 0
    assert rep.bias_report.flip_rate == pytest.approx(0.0)
    assert rep.bias_report.passed


# ------------------------------------------------------------------ calibrate: position bias detected
def test_position_bias_detector_catches_flipping_judge(C):
    ds = [C.LabeledExample("q1", "answer one", 4),
          C.LabeledExample("q2", "answer two", 3)]
    judge = C.PositionBiasedJudge(C.GoldenJudge(ds))
    pairs = [(f"q{i}", words(20, "a"), words(20, "b")) for i in range(4)]
    rep = C.calibrate(judge, ds, pair_questions=pairs)
    assert rep.bias_report.total == 4
    assert rep.bias_report.flips == 4, "equal-quality pairs flip 100% under order bias"
    assert rep.bias_report.flip_rate == pytest.approx(1.0)
    assert rep.bias_report.flip_rate > 0.10
    assert not rep.bias_report.passed
    assert not rep.passed, "flip rate > 10% must fail the whole report"
    assert any("flip_rate" in r for r in rep.fail_reasons)


def test_position_bias_ties_are_not_flips(C):
    """A judge that scores everything identically is useless but not order-biased."""
    class FlatJudge:
        name = "flat"
        def grade(self, q, a, rubric): return 3
        def grade_pair(self, q, a, b, rubric): return (3, 3)

    ds = [C.LabeledExample("q", "a", 3)]
    pairs = [("q", "x", "y"), ("q2", "y", "x")]
    rep = C.calibrate(FlatJudge(), ds, pair_questions=pairs)
    assert rep.bias_report.flips == 0
    assert rep.bias_report.flip_rate == pytest.approx(0.0)


# ------------------------------------------------------------------ calibrate: verbosity detected
def test_verbosity_judge_kappa_tanks_on_length_confounded_dataset(C):
    """Gold scores are independent of length; the judge's are a function of
    length — kappa must collapse and the report must fail."""
    ds = []
    for i in range(12):
        length = 10 + (i % 4) * 40          # 10, 50, 90, 130 words
        gold = (i % 5) + 1                  # gold score uncorrelated with length
        ds.append(C.LabeledExample(f"q{i}", words(length, f"c{i}"), gold))
    rep = C.calibrate(C.VerbosityBiasedJudge(), ds)
    assert rep.kappa < 0.6, "verbosity bias must be caught by kappa"
    assert not rep.passed
    assert any("kappa" in r for r in rep.fail_reasons)
    assert rep.judge_name == "verbosity"


def test_verbosity_judge_perfect_when_gold_follows_length(C):
    """Sanity: when gold labels DO track length the judge agrees — the metric
    is measuring agreement, not punishing the judge for existing.
    VerbosityBiasedJudge(baseline=10, bump=1): wc 10->1, 30->2, 50->3, 70->4, 90->5."""
    lengths_golds = [(10, 1), (30, 2), (50, 3), (70, 4), (90, 5)]
    ds = [C.LabeledExample(f"q{i}", words(wc), gold)
          for i, (wc, gold) in enumerate(lengths_golds)]
    rep = C.calibrate(C.VerbosityBiasedJudge(), ds)
    assert rep.kappa == pytest.approx(1.0), "gold tracks length: judge must agree"
    assert rep.passed


# ------------------------------------------------------------------ calibrate: self-preference detected
def test_selfpref_judge_exposed_by_style_marker_dataset(C):
    """Half the answers carry the judge's own style marker, all scored 1 by
    humans; the judge gives marker answers a 5. Non-marker answers delegate
    to the golden judge so they grade honestly."""
    ds = [C.LabeledExample(f"q{i}", f"In summary, wrong answer {i}", 1)
          for i in range(8)]
    # plain answers: golds 2..5, none carries the marker — inner grades them gold
    ds += [C.LabeledExample(f"p{i}", f"plain decent answer {i}", 2 + (i % 4))
           for i in range(8)]
    judge = C.SelfPreferenceJudge(["In summary,"], inner=C.GoldenJudge(ds))
    rep = C.calibrate(judge, ds)
    assert rep.judge_name == "selfpref(golden)"
    assert rep.per_class_accuracy[1] == 0.0, "gold-1 class all carry the marker: judge gives 5"
    assert rep.per_class_accuracy[2] == 1.0, "non-marker answers delegate honestly"
    assert rep.per_class_accuracy[1] < rep.per_class_accuracy[2]
    assert rep.kappa < 0.6
    assert not rep.passed
    # the confusion matrix shows the signature: gold row 1 concentrated on judged col 5
    assert rep.confusion_matrix[0][4] == 8
    # plain answers fall on the diagonal — only the marker class is corrupted
    for g in (2, 3, 4, 5):
        assert rep.confusion_matrix[g - 1][g - 1] == 2


def test_selfpref_judge_clean_when_no_markers_present(C):
    ds = [C.LabeledExample(f"q{i}", f"plain answer {i}", (i % 5) + 1)
          for i in range(10)]
    rep = C.calibrate(C.SelfPreferenceJudge(["In summary,"]), ds)
    assert rep.judge_name == "selfpref(default)"
    assert rep.kappa == pytest.approx(0.0) or rep.kappa >= 0.0
    # flat-3 judge vs varied gold: never passes kappa, but no marker-5 inflation
    assert rep.confusion_matrix[4][4] == 0


# ------------------------------------------------------------------ report thresholds
def test_report_passes_exactly_at_kappa_boundary(C):
    rep = C.CalibrationReport(judge_name="x", n=10, per_class_accuracy={},
                              confusion_matrix=[[0]*5 for _ in range(5)],
                              kappa=0.6, bias_report=None)
    assert rep.passed, "kappa == 0.6 is a pass (>= threshold)"


def test_report_fails_just_below_kappa_boundary(C):
    rep = C.CalibrationReport(judge_name="x", n=10, per_class_accuracy={},
                              confusion_matrix=[[0]*5 for _ in range(5)],
                              kappa=0.5999, bias_report=None)
    assert not rep.passed
    assert rep.fail_reasons == ["kappa 0.5999 < 0.6"]


def test_report_flip_rate_boundary(C):
    class FakeBias:
        flip_rate = 0.10
        threshold = 0.10
        passed = True

    rep = C.CalibrationReport(judge_name="x", n=10, per_class_accuracy={},
                              confusion_matrix=[[0]*5 for _ in range(5)],
                              kappa=1.0)
    rep.bias_report = FakeBias()
    assert rep.passed, "flip_rate == 0.10 is a pass (<= threshold)"


def test_report_without_bias_report_needs_only_kappa(C):
    rep = C.CalibrationReport(judge_name="x", n=10, per_class_accuracy={},
                              confusion_matrix=[[0]*5 for _ in range(5)],
                              kappa=0.9)
    assert rep.bias_report is None
    assert rep.flip_rate is None
    assert rep.passed


def test_fail_reasons_list_both_problems(C):
    class BadBias:
        flip_rate = 0.5
        threshold = 0.10

        @property
        def passed(self):
            return self.flip_rate <= self.threshold

    rep = C.CalibrationReport(judge_name="x", n=10, per_class_accuracy={},
                              confusion_matrix=[[0]*5 for _ in range(5)],
                              kappa=0.2)
    rep.bias_report = BadBias()
    assert len(rep.fail_reasons) == 2
    assert "kappa" in rep.fail_reasons[0]
    assert "flip_rate" in rep.fail_reasons[1]
