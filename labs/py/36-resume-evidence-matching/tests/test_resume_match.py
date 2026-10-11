import pytest


def test_normalize_term_collapses_case_and_spaces(R):
    assert R.normalize_term("  Retrieval   Augmented Generation ") == "retrieval augmented generation"


def test_extract_terms_matches_phrases_not_substrings(R):
    text = "Built RAG services with FastMCP and Python."
    assert R.extract_terms(text, ["RAG", "FastMCP", "Go"]) == ("RAG", "FastMCP")


def test_match_requirements_uses_canonical_or_synonym(R):
    requirements = [
        R.Requirement("retrieval augmented generation", ("RAG",)),
        R.Requirement("OpenTelemetry", ("OTel",)),
        R.Requirement("Kubernetes"),
    ]
    rows = R.match_requirements("Built RAG services and instrumented with OTel.", requirements)
    assert rows[0].matched_term == "RAG"
    assert rows[0].requirement == "retrieval augmented generation"
    assert not rows[1].missing
    assert rows[2].missing


def test_match_result_keeps_evidence_line(R):
    rows = R.match_requirements("A2A architecture\nBuilt FastMCP tool servers for agents.",
                                [R.Requirement("FastMCP")])
    assert rows[0].evidence == "Built FastMCP tool servers for agents."


def test_explain_missing_is_honest(R):
    result = R.MatchResult("Kubernetes", None, None, True)
    explanation = R.explain_missing([result])
    assert "Kubernetes" in explanation
    assert "truthful" in explanation
    assert "experience" in explanation


def test_explain_complete_result(R):
    result = R.MatchResult("Python", "Python", "Built Python services.", False)
    assert "No missing requirements" in R.explain_missing([result])


def test_empty_inputs_are_invalid(R):
    with pytest.raises(ValueError):
        R.extract_terms("Python", [])
    with pytest.raises(ValueError):
        R.match_requirements("Python", [])
