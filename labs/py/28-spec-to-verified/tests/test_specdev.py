"""Lab 28 tests. Pure stdlib, no sleeps — the loop runs on scripted builders."""

import pytest

from specdev import Spec, run_spec, verify


def _impl(report_rows):
    """Build an implementation dict {req_id: {criterion: bool}} from
    (req_id, criterion, passed) tuples."""
    impl = {}
    for req_id, criterion, passed in report_rows:
        impl.setdefault(req_id, {})[criterion] = passed
    return impl


# ------------------------------------------------------------- spec parsing
def test_spec_parses_requirements_from_multiline_text():
    text = """
    # Header

    Some prose about caching that should be ignored.

    REQ R1: responses cache by tenant
    REQ R2 : eviction is LRU

    ACCEPT R1: two reads hit the backend once
    """
    spec = Spec(text)
    assert spec.requirements == {"R1": "responses cache by tenant",
                                  "R2": "eviction is LRU"}
    assert spec.criteria == {"R1": ["two reads hit the backend once"]}


def test_spec_with_missing_sections_is_empty_not_error():
    spec = Spec("")
    assert spec.requirements == {}
    assert spec.criteria == {}
    spec2 = Spec("no req lines at all\nACCEPT R9: orphaned criterion")
    assert spec2.requirements == {}
    assert spec2.criteria == {"R9": ["orphaned criterion"]}


def test_spec_lines_missing_colon_are_dropped():
    spec = Spec("REQ R1 no colon here\nACCEPT R1 also broken\nREQ R2: fine: with inner colon")
    assert spec.requirements == {"R2": "fine: with inner colon"}
    assert spec.criteria == {}


def test_criteria_attach_by_req_id_and_append_in_order():
    text = """
    REQ A: first
    REQ B: second
    ACCEPT A: criterion one
    ACCEPT B: criterion b1
    ACCEPT A: criterion two
    ACCEPT A: criterion three
    """
    spec = Spec(text)
    assert spec.criteria["A"] == ["criterion one", "criterion two", "criterion three"]
    assert spec.criteria["B"] == ["criterion b1"]


# ------------------------------------------------------------------ verify
def test_verify_all_pass_when_every_criterion_true():
    requirements = {"R1": "desc", "R2": "desc2"}
    criteria = {"R1": ["c1", "c2"], "R2": ["c3"]}
    impl = _impl([("R1", "c1", True), ("R1", "c2", True), ("R2", "c3", True)])
    report = verify(requirements, criteria, impl)
    assert report["R1"] == {"passed": True, "failed_criteria": []}
    assert report["R2"] == {"passed": True, "failed_criteria": []}
    assert report["hallucinated"] == []


def test_verify_flags_one_failing_criterion():
    requirements = {"R1": "desc"}
    criteria = {"R1": ["ok criterion", "broken criterion"]}
    impl = _impl([("R1", "ok criterion", True), ("R1", "broken criterion", False)])
    report = verify(requirements, criteria, impl)
    assert report["R1"]["passed"] is False
    assert report["R1"]["failed_criteria"] == ["broken criterion"]


def test_verify_fails_criterion_the_report_never_mentions():
    """Absence of a verdict is not success — unverifiable is not done."""
    requirements = {"R1": "desc"}
    criteria = {"R1": ["mentioned", "never mentioned"]}
    impl = _impl([("R1", "mentioned", True)])
    report = verify(requirements, criteria, impl)
    assert report["R1"]["passed"] is False
    assert report["R1"]["failed_criteria"] == ["never mentioned"]


def test_verify_no_criteria_requirement_fails_by_default():
    requirements = {"R1": "no criteria", "R2": "has one"}
    criteria = {"R2": ["c"]}
    impl = _impl([("R1", "anything", True), ("R2", "c", True)])
    report = verify(requirements, criteria, impl)
    assert report["R1"]["passed"] is False
    assert report["R1"]["failed_criteria"] == []
    assert report["R2"]["passed"] is True


def test_verify_hallucinated_requirement_reported_and_ignored():
    """The builder 'finished' work the spec never asked for. It must not
    count as passing anything, but it must be visible in the report."""
    requirements = {"R1": "real"}
    criteria = {"R1": ["c1"]}
    impl = _impl([("R1", "c1", True), ("R7", "hallucinated criterion", True)])
    report = verify(requirements, criteria, impl)
    assert "R7" not in report
    assert report["hallucinated"] == ["R7"]
    assert report["R1"]["passed"] is True


# ------------------------------------------------------------------ run_spec
def test_run_spec_converges_when_builder_fixes_failures():
    """Round 1: R1 criterion X fails. Round 2: builder receives the failure
    report, fixes X, everything passes. rounds == 2, and the builder
    demonstrably saw the report."""
    spec = Spec("REQ R1: needs X and Y\nACCEPT R1: X works\nACCEPT R1: Y works")
    seen = []

    def builder(requirements, prev_impl=None, report=None):
        seen.append({"prev_impl": prev_impl, "report": report})
        if report is None:
            return {"R1": {"X works": True, "Y works": False}}
        assert report["R1"]["failed_criteria"] == ["Y works"]
        return {"R1": {"X works": True, "Y works": True}}

    result = run_spec(spec, builder)
    assert result["rounds"] == 2
    assert result["all_passed"] is True
    assert result["implementation"] == {"R1": {"X works": True, "Y works": True}}
    assert len(seen) == 2
    assert seen[0]["report"] is None
    assert seen[1]["report"]["R1"]["failed_criteria"] == ["Y works"]
    assert seen[1]["prev_impl"] == {"R1": {"X works": True, "Y works": False}}


def test_run_spec_passes_first_try():
    spec = Spec("REQ R1: simple\nACCEPT R1: single criterion")
    result = run_spec(spec, lambda reqs: {"R1": {"single criterion": True}})
    assert result == {"implementation": {"R1": {"single criterion": True}},
                      "rounds": 1, "all_passed": True}


def test_run_spec_exhausts_max_rounds_when_builder_never_improves():
    spec = Spec("REQ R1: never done\nACCEPT R1: X works")
    calls = []

    def stubborn(requirements, prev_impl=None, report=None):
        calls.append(1)
        return {"R1": {"X works": False}}

    result = run_spec(spec, stubborn)
    assert result["rounds"] == 3
    assert result["all_passed"] is False
    assert len(calls) == 3


def test_run_spec_empty_spec_trivially_passes_with_zero_rounds():
    spec = Spec("nothing here but prose")
    called = []

    def builder(*args):
        called.append(1)
        return {}

    result = run_spec(spec, builder)
    assert result == {"implementation": {}, "rounds": 0, "all_passed": True}
    assert called == []
