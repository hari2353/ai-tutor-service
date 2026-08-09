"""Lab 06 tests. Fully deterministic, no network, no real embedding model --
everything is seeded and fixed. Tests define done."""
import math

import numpy as np
import pytest


# ============================================================== step 1: fixed chunking
def test_fixed_chunk_never_splits_mid_word(R):
    text = ("supercalifragilisticexpialidocious antidisestablishmentarianism "
            + "the quick brown fox jumps over the lazy dog " * 5)
    words = text.split()
    chunks = R.fixed_chunk(text, chunk_size=15, overlap=0)
    reconstructed = []
    for c in chunks:
        reconstructed.extend(c.split())
    assert reconstructed == words
    original_words = set(words)
    for c in chunks:
        for w in c.split():
            assert w in original_words


def test_fixed_chunk_respects_size_budget(R):
    text = "the quick brown fox jumps over the lazy dog and then trots away slowly"
    chunks = R.fixed_chunk(text, chunk_size=20, overlap=0)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 20


def test_fixed_chunk_a_single_long_word_stands_alone(R):
    """A word longer than chunk_size must not be split -- it becomes its own
    (over-budget) chunk rather than being cut mid-word."""
    text = "short pneumonoultramicroscopicsilicovolcanoconiosis short"
    chunks = R.fixed_chunk(text, chunk_size=10, overlap=0)
    assert "pneumonoultramicroscopicsilicovolcanoconiosis" in chunks


def test_fixed_chunk_overlap_repeats_boundary_words(R):
    # equal-length words so every non-final chunk packs the same word count
    # (3 words per chunk) -- comfortably more than overlap=1, so the overlap
    # window never has to fight the "always make forward progress" guard.
    text = " ".join(["aaa", "bbb", "ccc", "ddd", "eee", "fff", "ggg", "hhh", "iii", "jjj"])
    chunks = R.fixed_chunk(text, chunk_size=11, overlap=1)
    assert len(chunks) >= 2
    # the last word of chunk i should reappear as the first word of chunk i+1
    for i in range(len(chunks) - 1):
        tail = chunks[i].split()[-1:]
        head = chunks[i + 1].split()[:1]
        assert tail == head


def test_fixed_chunk_empty_text_returns_no_chunks(R):
    assert R.fixed_chunk("", chunk_size=10) == []


# ============================================================== step 2: recursive chunking
PARAGRAPH_TEXT = (
    "Paragraph one is about ovens and baking bread at high heat.\n\n"
    "Paragraph two discusses distant planets and violent storms in the solar system.\n\n"
    "Paragraph three returns to kitchen matters like whisking eggs and folding batter gently."
)


def test_recursive_chunk_never_splits_mid_word(R):
    chunks = R.recursive_chunk(PARAGRAPH_TEXT, max_size=80)
    allowed_words = set(PARAGRAPH_TEXT.replace("\n\n", " ").split())
    for c in chunks:
        for w in c.split():
            assert w in allowed_words


def test_recursive_chunk_respects_max_size(R):
    chunks = R.recursive_chunk(PARAGRAPH_TEXT, max_size=80)
    for c in chunks:
        assert len(c) <= 80


def test_recursive_chunk_prefers_larger_separators(R):
    """Paragraphs that already fit under max_size must be kept intact, not
    cut down to sentence/word level just because a lower-level separator
    exists -- recursion should only descend into a piece that doesn't fit."""
    paragraphs = PARAGRAPH_TEXT.split("\n\n")
    chunks = R.recursive_chunk(PARAGRAPH_TEXT, max_size=80)
    assert paragraphs[0] in chunks
    assert paragraphs[1] in chunks
    # paragraph three is 89 chars -- too long, so it MUST be split further
    assert paragraphs[2] not in chunks
    assert len(chunks) > 3


def test_recursive_chunk_short_text_is_single_chunk(R):
    assert R.recursive_chunk("just one short sentence.", max_size=200) == ["just one short sentence."]


# ============================================================== step 3: semantic-ish chunking
TOPIC_A = ("The oven must reach 375 degrees before the batter goes in. "
           "Mix the batter slowly so the oven bakes it evenly. "
           "A hot oven and a smooth batter make the best bake.")
TOPIC_B = ("Jupiter is a giant planet with a violent storm. "
           "The storm on this planet has raged for centuries. "
           "Astronomers watch the planet storm from telescopes on Earth.")


def test_semantic_chunk_splits_at_topic_boundary(R):
    text = TOPIC_A + " " + TOPIC_B
    chunks = R.semantic_chunk(text, threshold=0.3, max_sentences=5)
    assert len(chunks) == 2
    assert chunks[0] == TOPIC_A
    assert chunks[1] == TOPIC_B


def test_semantic_chunk_never_splits_mid_word(R):
    text = TOPIC_A + " " + TOPIC_B
    chunks = R.semantic_chunk(text, threshold=0.3, max_sentences=5)
    allowed_words = set(text.split())
    for c in chunks:
        for w in c.split():
            assert w in allowed_words


def test_semantic_chunk_respects_max_sentences_cap(R):
    """Even with a very permissive threshold, a chunk never exceeds
    max_sentences sentences."""
    text = TOPIC_A + " " + TOPIC_B
    chunks = R.semantic_chunk(text, threshold=-1.0, max_sentences=2)
    for c in chunks:
        assert len(R.split_sentences(c)) <= 2


def test_seeded_embed_is_deterministic(R):
    v1 = R.seeded_embed("the oven bakes the batter")
    v2 = R.seeded_embed("the oven bakes the batter")
    assert np.allclose(v1, v2)


# ============================================================== step 4: BM25 -- hand-computed
# Tiny corpus, hand-computed against the Okapi BM25 formula:
#   idf(t) = ln((N - n(t) + 0.5)/(n(t) + 0.5) + 1)
#   score(d,q) = sum_t idf(t) * f(t,d)*(k1+1) / (f(t,d) + k1*(1-b+b*dl/avgdl))
# corpus:
#   d0 = "the cat sat on the mat"     (dl=6)
#   d1 = "the dog sat on the log"     (dl=6)
#   d2 = "cats and dogs are pets"     (dl=5)
# avgdl = 17/3 = 5.6667, N=3
# query = ["cat", "sat"]
# idf(cat) = ln((3-1+0.5)/(1+0.5)+1) = 0.98083   (df(cat)=1)
# idf(sat) = ln((3-2+0.5)/(2+0.5)+1) = 0.47000   (df(sat)=2)
# d0: has both cat(f=1) and sat(f=1), dl=6 -> score = 1.41342
# d1: has sat only (f=1), dl=6           -> score = 0.45788
# d2: has neither                         -> score = 0.0
TINY_CORPUS_TOKENS = [
    "the cat sat on the mat".split(),
    "the dog sat on the log".split(),
    "cats and dogs are pets".split(),
]


def test_bm25_hand_computed_scores_tiny_corpus(R):
    bm25 = R.BM25(TINY_CORPUS_TOKENS, k1=1.5, b=0.75)
    query = ["cat", "sat"]
    assert bm25.score(query, 0) == pytest.approx(1.41342, abs=1e-3)
    assert bm25.score(query, 1) == pytest.approx(0.45788, abs=1e-3)
    assert bm25.score(query, 2) == pytest.approx(0.0, abs=1e-9)


def test_bm25_hand_computed_idf_values(R):
    bm25 = R.BM25(TINY_CORPUS_TOKENS, k1=1.5, b=0.75)
    assert bm25.idf("cat") == pytest.approx(0.98083, abs=1e-3)
    assert bm25.idf("sat") == pytest.approx(0.47000, abs=1e-3)


def test_bm25_search_orders_by_score_descending(R):
    bm25 = R.BM25(TINY_CORPUS_TOKENS, k1=1.5, b=0.75)
    results = bm25.search(["cat", "sat"])
    doc_ids = [doc_id for doc_id, _ in results]
    assert doc_ids == [0, 1, 2]
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_bm25_search_top_k_truncates(R):
    bm25 = R.BM25(TINY_CORPUS_TOKENS, k1=1.5, b=0.75)
    results = bm25.search(["cat", "sat"], top_k=1)
    assert len(results) == 1
    assert results[0][0] == 0


def test_bm25_unknown_query_term_contributes_zero(R):
    bm25 = R.BM25(TINY_CORPUS_TOKENS, k1=1.5, b=0.75)
    assert bm25.score(["spaceship"], 0) == pytest.approx(0.0, abs=1e-9)


# ============================================================== step 5: BM25 -- real saturation
def _padded_doc(term, freq, pad_len=20):
    return [term] * freq + [f"filler{i}" for i in range(pad_len - freq)]


def test_bm25_saturation_diminishing_returns(R):
    """The Okapi saturation term f*(k1+1)/(f+k1*(...)) must genuinely
    saturate: score keeps rising with term frequency but each additional
    occurrence buys strictly less than the previous one. A linear (non-BM25)
    scoring function would fail this."""
    freqs = [1, 2, 4, 8]
    corpus = [_padded_doc("target", f) for f in freqs]
    bm25 = R.BM25(corpus, k1=1.5, b=0.75)
    scores = [bm25.score(["target"], i) for i in range(len(freqs))]

    # monotonically increasing
    assert scores == sorted(scores)
    assert scores[0] < scores[-1]

    # but with strictly diminishing increments (concave / saturating)
    increments = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]
    assert all(increments[i] > increments[i + 1] for i in range(len(increments) - 1))


def test_bm25_longer_document_scores_lower_for_same_term_frequency(R):
    """Length normalization: two docs with the same raw term frequency but
    different lengths should not score identically -- the longer one is
    penalized by the b*(dl/avgdl) term."""
    short_doc = ["target"] + [f"pad{i}" for i in range(4)]     # dl=5
    long_doc = ["target"] + [f"pad{i}" for i in range(40)]     # dl=41
    corpus = [short_doc, long_doc]
    bm25 = R.BM25(corpus, k1=1.5, b=0.75)
    assert bm25.score(["target"], 0) > bm25.score(["target"], 1)


# ============================================================== step 6: dense retrieval
def test_cosine_similarity_identical_vectors_is_one(R):
    v = np.array([1.0, 2.0, 3.0])
    assert R.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-9)


def test_cosine_similarity_orthogonal_vectors_is_zero(R):
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert R.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-9)


def test_cosine_similarity_opposite_vectors_is_negative_one(R):
    a = np.array([1.0, 0.0])
    b = np.array([-1.0, 0.0])
    assert R.cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-9)


def test_dense_retriever_search_orders_by_similarity_descending(R):
    vectors = {
        0: np.array([1.0, 0.0]),
        1: np.array([0.0, 1.0]),
        2: np.array([0.7071, 0.7071]),
    }
    retriever = R.DenseRetriever(vectors)
    query = np.array([1.0, 0.0])
    results = retriever.search(query)
    doc_ids = [doc_id for doc_id, _ in results]
    assert doc_ids == [0, 2, 1]


# ============================================================== step 7: RRF -- combining rankings
def test_rrf_favors_docs_ranked_highly_in_multiple_lists(R):
    ranking_a = [10, 20, 30, 40]
    ranking_b = [20, 10, 40, 30]
    fused = R.reciprocal_rank_fusion([ranking_a, ranking_b])
    fused_ids = [doc_id for doc_id, _ in fused]
    # 10 and 20 are #1/#2 in both lists -- they must lead the fused ranking
    assert set(fused_ids[:2]) == {10, 20}


def test_rrf_score_matches_formula(R):
    ranking_a = [1, 2]
    fused = dict(R.reciprocal_rank_fusion([ranking_a], k=60))
    assert fused[1] == pytest.approx(1 / 61, abs=1e-9)
    assert fused[2] == pytest.approx(1 / 62, abs=1e-9)


def test_rrf_ties_broken_by_doc_id_ascending(R):
    fused = R.reciprocal_rank_fusion([[5, 1], [1, 5]])
    fused_ids = [doc_id for doc_id, _ in fused]
    assert fused_ids[0] == 1  # tied score, lower id wins


def test_rrf_doc_absent_from_a_list_still_gets_included(R):
    fused = dict(R.reciprocal_rank_fusion([[1, 2], [2]]))
    assert 1 in fused
    assert 2 in fused
    assert fused[2] > fused[1]  # doc 2 appears in both lists


# ============================================================== step 8: RRF beats either retriever alone
# A 10-document corpus, one query, with a *fixed relevance judgment*
# (relevant = {2, 5}) engineered so that:
#   - doc 2 is a pure LEXICAL match (contains every query term) but its fixed
#     seeded embedding is deliberately unremarkable, so dense retrieval alone
#     does not surface it in the top-4.
#   - doc 5 is a pure SEMANTIC/paraphrase match (shares zero query terms) but
#     its fixed seeded embedding is engineered to be the closest to the query
#     vector, so BM25 alone cannot surface it (score 0) in the top-4.
# Neither retriever alone can find both relevant docs in its top-4. RRF,
# fusing both ranked lists, finds both -- this is the whole point of hybrid
# search and the numbers below are not tunable after the fact.
RRF_CORPUS = {
    0: "the cat sat lazily on the warm mat in the sunny yard",
    1: "stock market prices rose sharply after the earnings report",
    2: "python exception handling lets you manage runtime failures gracefully",
    3: "the quarterly budget review meeting ran long on friday afternoon",
    4: "the chef seasoned the soup with fresh herbs and cracked pepper",
    5: "wrapping risky code in try and except blocks lets programs recover gracefully from runtime failures",
    6: "robust bridge design accounts for wind load and material fatigue",
    7: "the weekend hiking trail wound through pine forest and rocky ridges",
    8: "the orchestra rehearsed the symphony for three hours before the show",
    9: "the museum exhibit featured ancient pottery from coastal excavation sites",
}
RRF_QUERY = "python exception handling"
RRF_RELEVANT = {2, 5}

# Fixed, seeded vectors (dim=16) -- NOT derived from the text above. These
# stand in for a real embedding model's output and are engineered so doc 5
# (semantic match) is closest to the query vector and doc 2 (lexical match)
# is not, per the corpus design above. Regenerated with
# np.random.default_rng(7); rounded to 4dp for a stable, literal fixture.
RRF_QUERY_VECTOR = np.array([0.0005, 0.119, -0.1092, -0.3547, -0.1811, -0.395, 0.024, 0.5338,
                              -0.1961, -0.2471, 0.1951, 0.1422, 0.042, -0.3706, -0.0117, 0.2769])
RRF_DOC_VECTORS = {
    0: np.array([-0.2896, -0.1039, -0.4047, -0.2619, -0.3886, -0.0329, -0.2741, 0.0345,
                 0.0426, -0.0292, -0.5509, -0.1224, -0.0123, 0.041, -0.3291, -0.1153]),
    1: np.array([-0.2931, -0.2557, 0.3301, -0.2016, 0.0108, 0.3096, -0.1775, -0.094,
                 0.0553, 0.0471, -0.389, 0.0067, 0.4022, -0.4213, 0.2587, 0.0043]),
    2: np.array([-0.1885, 0.5672, 0.2425, -0.2917, 0.0528, 0.2368, -0.0595, 0.1094,
                 0.0139, 0.2382, 0.3892, -0.2227, 0.0525, -0.0728, 0.0394, -0.396]),
    3: np.array([-0.1531, -0.0394, 0.2262, 0.2657, -0.3687, -0.2513, 0.1735, -0.4709,
                 -0.1429, -0.0515, 0.3526, 0.1971, -0.0821, -0.1361, -0.0673, 0.4316]),
    4: np.array([-0.181, -0.1175, 0.1391, -0.0837, -0.1001, -0.5076, -0.0027, -0.1385,
                 0.4752, 0.2535, 0.0077, 0.2958, -0.1399, 0.411, -0.0034, 0.2722]),
    5: np.array([-0.1547, 0.1091, -0.2646, -0.4454, -0.1392, -0.3319, 0.0333, 0.5721,
                 -0.211, -0.215, 0.1352, 0.1398, 0.0026, -0.2348, 0.0777, 0.2194]),
    6: np.array([-0.2682, -0.0593, 0.0447, -0.158, 0.1263, -0.0939, 0.2443, -0.1238,
                 0.087, -0.0728, -0.0943, -0.5643, -0.3071, 0.2147, -0.5482, 0.1294]),
    7: np.array([-0.4896, 0.1807, -0.2082, 0.312, 0.0845, -0.3265, 0.3438, 0.2632,
                 0.0333, -0.0115, -0.0963, -0.3109, 0.2969, -0.0544, -0.0113, -0.2955]),
    8: np.array([-0.1873, -0.3712, 0.366, -0.0791, 0.2722, -0.0327, -0.2055, -0.0481,
                 -0.1859, -0.0206, -0.0941, -0.0765, -0.4086, -0.2759, 0.4938, -0.1751]),
    9: np.array([-0.2949, 0.0751, 0.4113, -0.3492, -0.029, -0.1128, -0.4964, 0.1191,
                 0.0252, 0.06, -0.242, 0.1042, -0.1576, 0.0201, -0.3081, -0.385]),
}


def _recall_at_k(ranked_doc_ids, k, relevant):
    top_k = set(ranked_doc_ids[:k])
    return len(top_k & relevant) / len(relevant)


def test_rrf_outperforms_either_retriever_alone(R):
    corpus_tokens = [R.tokenize(RRF_CORPUS[i]) for i in range(len(RRF_CORPUS))]
    bm25 = R.BM25(corpus_tokens, k1=1.5, b=0.75)
    dense = R.DenseRetriever(RRF_DOC_VECTORS)

    query_tokens = R.tokenize(RRF_QUERY)
    bm25_rank = [doc_id for doc_id, _ in bm25.search(query_tokens)]
    dense_rank = [doc_id for doc_id, _ in dense.search(RRF_QUERY_VECTOR)]
    rrf_rank = [doc_id for doc_id, _ in R.reciprocal_rank_fusion([bm25_rank, dense_rank])]

    K = 4
    bm25_recall = _recall_at_k(bm25_rank, K, RRF_RELEVANT)
    dense_recall = _recall_at_k(dense_rank, K, RRF_RELEVANT)
    rrf_recall = _recall_at_k(rrf_rank, K, RRF_RELEVANT)

    # each single retriever finds exactly one of the two relevant docs
    assert bm25_recall == pytest.approx(0.5)
    assert dense_recall == pytest.approx(0.5)
    # BM25 finds the lexical match, misses the semantic one (and vice versa)
    assert 2 in bm25_rank[:K] and 5 not in bm25_rank[:K]
    assert 5 in dense_rank[:K] and 2 not in dense_rank[:K]

    # fusion recovers BOTH relevant docs -- strictly better than either alone
    assert rrf_recall == pytest.approx(1.0)
    assert rrf_recall > bm25_recall
    assert rrf_recall > dense_recall
    assert 2 in rrf_rank[:K] and 5 in rrf_rank[:K]
