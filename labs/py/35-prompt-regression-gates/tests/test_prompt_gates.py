import pytest


def case(R, name="case-1", slice_name="default", terms=("timeout",)):
    return R.GoldenCase(name, "prompt", slice_name, tuple(terms))


def test_score_case_matches_all_required_phrases(R):
    result = R.score_case(case(R, terms=("timeout", "retry budget")), "Set a timeout and a retry budget.")
    assert result.passed
    assert result.missing == ()
    assert result.matched == ("timeout", "retry budget")


def test_score_case_reports_missing_phrase_case_insensitively(R):
    result = R.score_case(case(R, terms=("PagedAttention", "continuous batching")), "PagedAttention is enabled.")
    assert not result.passed
    assert result.matched == ("PagedAttention",)
    assert result.missing == ("continuous batching",)


def test_aggregate_reports_overall_and_slices(R):
    results = [
        R.CaseResult("a", "safe", True, (), ()),
        R.CaseResult("b", "safe", False, (), ("x",)),
        R.CaseResult("c", "locale", True, (), ()),
    ]
    overall, slices = R.aggregate(results)
    assert overall == pytest.approx(2 / 3)
    assert slices == {"safe": pytest.approx(0.5), "locale": pytest.approx(1.0)}


def test_gate_requires_overall_and_slice_thresholds(R):
    results = [
        R.CaseResult("a", "critical", True, (), ()),
        R.CaseResult("b", "critical", False, (), ("x",)),
        R.CaseResult("c", "common", True, (), ()),
        R.CaseResult("d", "common", True, (), ()),
    ]
    report = R.evaluate_gate(results, {}, overall_threshold=0.75,
                             slice_thresholds={"critical": 0.75})
    assert not report.passed
    assert report.failed_slices == ("critical",)


def test_gate_detects_regression_against_baseline(R):
    results = [
        R.CaseResult("a", "safe", True, (), ()),
        R.CaseResult("b", "safe", False, (), ("x",)),
    ]
    report = R.evaluate_gate(results, {"safe": 0.9}, overall_threshold=0.5,
                             slice_thresholds={"safe": 0.5}, max_slice_drop=0.1)
    assert not report.passed
    assert report.regression_slices == ("safe",)


def test_gate_rejects_under_sampled_configured_slice(R):
    result = R.CaseResult("a", "critical", True, (), ())
    report = R.evaluate_gate([result], {}, overall_threshold=0.0,
                             slice_thresholds={"critical": 0.0, "locale": 0.0},
                             min_slice_cases=2)
    assert not report.passed
    assert report.failed_slices == ("critical", "locale")


def test_empty_aggregate_is_invalid(R):
    with pytest.raises(ValueError):
        R.aggregate([])
