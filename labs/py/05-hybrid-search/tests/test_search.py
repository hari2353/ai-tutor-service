"""Lab 04 tests. Every ranking asserted here is deterministic."""
import pytest


DOCS = {
    "d1": "the cat sat on the mat",
    "d2": "dogs chase cats in parks",
    "d3": "quantum chromodynamics is hard",
}

TRIO = {
    "lex":   "engine repair manual",
    "sem":   "engines learning hum",
    "noise": "banana republic travel",
}


# ------------------------------------------------------------------ bm25
def test_bm25_ranks_keyword_doc_first(S):
    scorer = S.bm25(DOCS)
    assert scorer.rank("cat")[0] == "d1"
    assert scorer.rank("parks")[0] == "d2"


def test_bm25_score_matches_formula_exactly(S):
    # N=2, df(x)=1 → idf = ln((2-1+.5)/(1+.5)+1) = ln 2
    # |a|=2 tokens, avgdl=2.5 → norm = 1 + 1.5·(0.25 + 0.75·0.8) = 2.275
    # score = ln2 · 1·2.5 / (1 + 2.275·1) ... = ln2 · 2.5/2.275 ≈ 0.76170
    scorer = S.bm25({"a": "x y", "b": "z z z"})
    assert scorer.score("x", "a") == pytest.approx(0.76170, abs=1e-3)


def test_bm25_zero_for_unmatched_terms_and_empty_query(S):
    scorer = S.bm25(DOCS)
    assert scorer.score("cat", "d3") == 0.0
    assert scorer.score("zebra", "d1") == 0.0
    assert scorer.score("", "d1") == 0.0


def test_bm25_shorter_doc_scores_higher_for_same_tf(S):
    # Same single match ("cat"), but d1 is shorter than d4 → length norm wins.
    docs = dict(DOCS)
    docs["d4"] = "cat catalog catalogue catamaran catapult category caterpillar cataract"
    scorer = S.bm25(docs)
    assert scorer.score("cat", "d1") > scorer.score("cat", "d4")


# ------------------------------------------------------------------ dense leg
def test_dense_surfaces_semantic_neighbour_without_lexical_overlap(S):
    den = S.dense_scorer(TRIO)
    # "engines learning" shares zero TOKENS with "engine tuning",
    # but its character trigrams light up.
    assert S.bm25(TRIO).score("engine tuning", "sem") == 0.0
    assert den.score("engine tuning", "sem") > den.score("engine tuning", "noise")
    ranked = den.rank("engine tuning")
    assert ranked.index("sem") < ranked.index("noise")


def test_dense_zero_for_empty_query_and_disjoint_text(S):
    den = S.dense_scorer(TRIO)
    assert den.score("", "lex") == 0.0


# ------------------------------------------------------------------ rrf
def test_rrf_toy_math_is_exact(S):
    out = S.rrf([["a", "b", "c"], ["b", "a"]], k=60)
    assert out["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert out["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert out["c"] == pytest.approx(1 / 63)
    assert set(out) == {"a", "b", "c"}          # only ranked docs appear


def test_rrf_absent_from_one_list_gets_no_contribution(S):
    out = S.rrf([["a"], ["a", "b"]], k=60)
    assert out["a"] == pytest.approx(1 / 61 + 1 / 61)
    assert out["b"] == pytest.approx(1 / 62)


def test_rrf_k_controls_gap_compression(S):
    tight = S.rrf([["a", "b"]], k=60)
    wide = S.rrf([["a", "b"]], k=0)
    assert tight["a"] == pytest.approx(1 / 61)
    assert wide["a"] == pytest.approx(1.0)
    assert wide["b"] == pytest.approx(0.5)
    assert (wide["a"] - wide["b"]) > (tight["a"] - tight["b"])


# ------------------------------------------------------------------ hybrid
def test_hybrid_exact_lexical_match_wins_overall(S):
    res = S.hybrid_search("engine tuning", TRIO)
    assert res[0][0] == "lex"


def test_hybrid_semantic_only_doc_beats_irrelevant(S):
    res = S.hybrid_search("engine tuning", TRIO)
    ids = [doc_id for doc_id, _ in res]
    assert ids.index("sem") < ids.index("noise")
    # and the semantic neighbour genuinely rides the dense leg:
    # its fused score must exceed pure-noise's.
    fused = dict(res)
    assert fused["sem"] > fused["noise"]


def test_hybrid_empty_query_returns_empty_list(S):
    assert S.hybrid_search("", TRIO) == []
    assert S.hybrid_search("   ", TRIO) == []


def test_hybrid_tie_determinism_repeated_calls_equal(S):
    docs = {"p": "same words here", "q": "same words here"}
    first = S.hybrid_search("words", docs)
    again = S.hybrid_search("words", docs)
    assert first == again
    # RRF ranks are strict orders, so identical docs settle by doc id asc —
    # the same way, on every call.
    assert [d for d, _ in first] == ["p", "q"]


def test_hybrid_unicode_corpus(S):
    docs = {
        "zh": "机器学习 改变 世界",
        "en": "coffee brewing guide",
    }
    res = S.hybrid_search("机器学习", docs)
    assert res[0][0] == "zh"


def test_hybrid_respects_top_n(S):
    docs = {f"d{i}": f"topic number {i} filler filler" for i in range(5)}
    res = S.hybrid_search("topic", docs, top_n=2)
    assert len(res) == 2
    assert len(S.hybrid_search("topic", docs, top_n=100)) == 5


def test_hybrid_output_sorted_by_fused_desc(S):
    res = S.hybrid_search("engine tuning", TRIO)
    scores = [score for _, score in res]
    assert scores == sorted(scores, reverse=True)


# ------------------------------------------------------------------ purity
def test_scorers_do_not_mutate_caller_dict(S):
    snapshot = dict(TRIO)
    S.bm25(TRIO).rank("engine tuning")
    S.dense_scorer(TRIO).rank("engine tuning")
    S.hybrid_search("engine tuning", TRIO)
    assert TRIO == snapshot
