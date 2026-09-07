"""Lab 24 tests. Three docs, one wrong citation, one invented date.

Doc1 and Doc2 are DELIBERATELY topically similar (both about the Breakroom
loyalty program) — the lexical overlap of a wrong citation must come from
shared vocabulary, not from an unrelated corpus. The constants the solution
is calibrated against live at the top of attribution.py and are GIVEN.
"""
import pytest


# ------------------------------------------------------------------ the corpus
SOURCES = {
    "doc1": (
        "The Breakroom loyalty program launched in 2015 and offers members "
        "one free coffee after every ten purchases. Free coffees expire "
        "after thirty days, and members cannot transfer rewards between "
        "accounts."
    ),
    "doc2": (
        "Breakroom cafes accept the loyalty card at every till, and members "
        "can also pay using the mobile wallet app. New members receive a "
        "welcome drink during their first month of membership."
    ),
    "doc3": (
        "The company headquarters are located in Amsterdam, where the "
        "design team tests new espresso machines before each seasonal "
        "product launch."
    ),
}


def _answer(A, claims):
    return A.CitedAnswer(claims, SOURCES)


# ---------------------------------------------------------------- 1. verbatim
def test_verbatim_claim_cited_to_right_doc_is_supported(A):
    """Copy a sentence from doc1, cite doc1 -> SUPPORTED."""
    ans = _answer(A, [{
        "text": "Free coffees expire after thirty days",
        "source_ids": ["doc1"],
    }])
    report = A.verify(ans, SOURCES)
    assert report["claims"][0]["status"] == "SUPPORTED"
    assert report["supported"] == 1


# --------------------------------------------------------------- 2. paraphrase
def test_paraphrase_with_same_content_words_is_supported(A):
    """Different surface form, same content words -> still SUPPORTED."""
    ans = _answer(A, [{
        "text": "Members cannot transfer their rewards between accounts",
        "source_ids": ["doc1"],
    }])
    report = A.verify(ans, SOURCES)
    assert report["claims"][0]["status"] == "SUPPORTED"


# -------------------------------------------------------------- 3. wrong cite
def test_wrong_citation_is_never_supported(A):
    """THE test. Content from doc2, citation to doc1: topically close —
    doc1 says "free coffee", the claim says "free welcome drink" — but the
    offer is doc2's, never stated in doc1. Similarity is not entailment,
    so NOT SUPPORTED."""
    ans = _answer(A, [{
        "text": "New members receive a free welcome drink during their first month",
        "source_ids": ["doc1"],
    }])
    report = A.verify(ans, SOURCES)
    status = report["claims"][0]["status"]
    assert status != "SUPPORTED"
    assert status in ("PLAUSIBLE_UNSUPPORTED", "FABRICATED")


# ---------------------------------------------------------- 4. numeric mismatch
def test_fabricated_date_downgraded_with_numeric_mismatch(A):
    """"in 1999" cites doc1, matches its vocabulary, but the number is
    nowhere in it -> FABRICATED, reason mentions numeric mismatch."""
    ans = _answer(A, [{
        "text": "The Breakroom loyalty program launched in 1999",
        "source_ids": ["doc1"],
    }])
    report = A.verify(ans, SOURCES)
    c = report["claims"][0]
    assert c["status"] == "FABRICATED"
    assert any("numeric mismatch" in r for r in c["reasons"])


# ------------------------------------------------------------ 5. numbers gate
def test_true_date_from_the_doc_survives_the_numbers_gate(A):
    """The same claim shape with doc1's actual year passes: overlap high AND
    every number present. Numbers must not block supported claims."""
    ans = _answer(A, [{
        "text": "The Breakroom loyalty program launched in 2015",
        "source_ids": ["doc1"],
    }])
    report = A.verify(ans, SOURCES)
    assert report["claims"][0]["status"] == "SUPPORTED"


# ---------------------------------------------------------- 6. faithfulness
def test_faithfulness_score_two_of_three(A):
    """2 SUPPORTED + 1 wrong-citation claim -> score 2/3."""
    ans = _answer(A, [
        {"text": "Free coffees expire after thirty days",
         "source_ids": ["doc1"]},
        {"text": "Members cannot transfer their rewards between accounts",
         "source_ids": ["doc1"]},
        {"text": "New members receive a free welcome drink during their first month",
         "source_ids": ["doc1"]},          # doc2's fact, doc1's citation
    ])
    report = A.verify(ans, SOURCES)
    assert A.faithfulness_score(report) == pytest.approx(2 / 3)
    assert report["faithfulness"] == pytest.approx(2 / 3)


def test_faithfulness_score_perfect_answer(A):
    ans = _answer(A, [
        {"text": "Free coffees expire after thirty days", "source_ids": ["doc1"]},
        {"text": "The design team tests new espresso machines", "source_ids": ["doc3"]},
    ])
    report = A.verify(ans, SOURCES)
    assert A.faithfulness_score(report) == pytest.approx(1.0)


# ------------------------------------------------------------ 7. normalization
def test_normalize_merges_near_identical_ids_and_sorts(A):
    """"doc1 ", "Doc1#sec2", "doc1" are one citation; output sorted + clean."""
    ans = _answer(A, [{
        "text": "Free coffees expire after thirty days",
        "source_ids": ["doc2 ", "doc1 ", "Doc1#sec2", "doc1"],
    }])
    norm = A.normalize_citations(ans)
    assert norm.claims[0]["source_ids"] == ["doc1", "doc2"]
    # and the normalized answer still verifies SUPPORTED against doc1
    report = A.verify(norm, SOURCES)
    assert report["claims"][0]["status"] == "SUPPORTED"


# ------------------------------------------------- 8. construction validation
def test_claim_citing_unknown_source_raises_value_error(A):
    with pytest.raises(ValueError):
        _answer(A, [{"text": "Something true", "source_ids": ["doc99"]}])


def test_claim_with_no_sources_raises_value_error(A):
    with pytest.raises(ValueError):
        _answer(A, [{"text": "Something true", "source_ids": []}])


def test_construction_accepts_id_that_canonicalizes_to_known(A):
    """'Doc1#intro' is a known doc wearing a fragment — must NOT raise."""
    ans = _answer(A, [{
        "text": "Free coffees expire after thirty days",
        "source_ids": ["Doc1#intro"],
    }])
    assert ans.claims[0]["source_ids"] == ["Doc1#intro"]
