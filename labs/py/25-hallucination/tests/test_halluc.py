"""Lab 25 tests. A fictional company corpus; no model calls, no sleeps."""
import pytest

from halluc import STOPWORDS  # noqa: F401 — asserts the module exports the list


# ------------------------------------------------------------------ the corpus
# Fictional company: Acme Analytics, founded 1998, 50 employees, HQ Lisbon,
# product "Foresight". Nothing here is real, so nothing can be "true" by
# accident — the only ground truth is the context itself.
DOCS = [
    "Acme Analytics is a data analytics company founded in 1998.",
    "The company is headquartered in Lisbon and employs 50 people.",
    "Its flagship product, Foresight, helps teams forecast demand and was "
    "launched in 2023.",
    "Acme Analytics reported 12 million euros in revenue for 2025.",
]


# ------------------------------------------------------------- extraction
def test_verbatim_sentence_is_extracted(H):
    span = "Acme Analytics is a data analytics company founded in 1998."
    assert H.classify_span(span, DOCS) == "extracted"


def test_punctuated_verbatim_is_extracted(H):
    span = "The company is headquartered in Lisbon and employs 50 people."
    assert H.classify_span(span, DOCS) == "extracted"


# --------------------------------------------------------------- inference
def test_paraphrase_with_entities_and_numbers_is_inferred(H):
    span = "The analytics firm Acme Analytics was established in 1998 and is based in Lisbon."
    assert H.classify_span(span, DOCS) == "inferred"


def test_synonym_paraphrase_is_inferred(H):
    span = "Acme Analytics makes money from Foresight, its core offering launched in 2023."
    assert H.classify_span(span, DOCS) == "inferred"


# ---------------------------------------------------------------- numbers
def test_fabricated_number_fails_numeric_consistency(H):
    ok, reason = H.numeric_consistency("The company was founded in 1999.", DOCS)
    assert not ok
    assert "1999" in reason


def test_fabricated_year_makes_span_unsupported(H):
    assert H.classify_span("The company was founded in 1999.", DOCS) == "unsupported"


def test_present_number_passes(H):
    ok, _ = H.numeric_consistency("It employs 50 people.", DOCS)
    assert ok


def test_unmentioned_number_fails(H):
    # 3 is not in the context, and no pair of context numbers derives it
    ok, _ = H.numeric_consistency("The company operates 3 offices.", DOCS)
    assert not ok


def test_high_overlap_with_swapped_number_is_not_extracted(H):
    """A copied sentence with one number swapped is 80%+ overlap and still
    a hallucination — the single most copied sentence in the corpus, with
    1998 replaced by 1999."""
    span = "Acme Analytics is a data analytics company founded in 1999."
    assert H.classify_span(span, DOCS) == "unsupported"


# ------------------------------------------------------------- arithmetic
def test_derivable_number_passes(H):
    # 2025 - 1998 = 27, both present in context
    ok, _ = H.numeric_consistency("The company was founded 27 years before 2025.", DOCS)
    assert ok


def test_derivable_year_count_is_inferred(H):
    span = "The company was founded 27 years before 2025."
    assert H.classify_span(span, DOCS) == "inferred"


def test_two_step_derivation_fails(H):
    """2005 is not in the context, and no single +/- step over context
    numbers {12, 50, 1998, 2023, 2025} reaches it — a number needing a
    two-step chain must fail. (1998 + 2005 = nothing useful.)"""
    ok, _ = H.numeric_consistency("The company opened its Lisbon office in 2005.", DOCS)
    assert not ok


# -------------------------------------------------------------- entities
def test_unmentioned_entity_fails_grounding(H):
    ok, missing = H.entity_grounding("It announced a partnership with Google.", DOCS)
    assert not ok
    assert missing == ["Google"]


def test_unmentioned_entity_makes_span_unsupported(H):
    assert H.classify_span("It announced a partnership with Google.", DOCS) == "unsupported"


def test_present_entity_passes(H):
    ok, missing = H.entity_grounding("Foresight is used by many teams.", DOCS)
    assert ok
    assert missing == []


def test_multi_word_entity_groups(H):
    ok, missing = H.entity_grounding("The Eiffel Tower is famous.", DOCS)
    assert not ok
    assert missing == ["Eiffel Tower"]


def test_sentence_start_capital_not_flagged(H):
    """Sentence-start capitals are ambiguous (could just be a sentence) —
    we skip them rather than flag every sentence."""
    ok, missing = H.entity_grounding("Lisbon is a lovely city.", DOCS)
    assert ok  # "Lisbon" at position 0 is skipped; everything else is fine


# -------------------------------------------------------------- detect
def test_detect_mixed_answer_fraction(H):
    answer = (
        "Acme Analytics is a data analytics company founded in 1998. "
        "The company was founded 27 years before 2025. "
        "It announced a partnership with Google. "
        "The company was founded in 1999."
    )
    report = H.detect(answer, DOCS)
    assert len(report["spans"]) == 4
    assert report["spans"][0]["class"] == "extracted"
    assert report["spans"][1]["class"] == "inferred"
    assert report["spans"][2]["class"] == "unsupported"
    assert report["spans"][3]["class"] == "unsupported"
    assert report["unsupported_fraction"] == pytest.approx(0.5)


def test_detect_all_extracted_fraction_zero(H):
    answer = ("Acme Analytics is a data analytics company founded in 1998. "
              "The company is headquartered in Lisbon and employs 50 people.")
    report = H.detect(answer, DOCS)
    assert report["unsupported_fraction"] == pytest.approx(0.0)


# -------------------------------------------- the trap: truth is not grounding
def test_true_fact_absent_from_context_is_unsupported(H):
    """THE test. The Eiffel Tower IS in Paris — true in the world, absent
    from the context. Grounding is against the context, not the world."""
    span = "The Eiffel Tower is in Paris."
    assert H.classify_span(span, DOCS) == "unsupported"
    ok, missing = H.entity_grounding(span, DOCS)
    assert not ok
    assert "Eiffel Tower" in missing


def test_true_numeric_fact_absent_from_context_fails(H):
    """Also true, also ungrounded: the US declaration was 1776 — the context
    never says 1776, and no present pair derives it."""
    ok, _ = H.numeric_consistency("The Declaration of Independence was signed in 1776.", DOCS)
    assert not ok
