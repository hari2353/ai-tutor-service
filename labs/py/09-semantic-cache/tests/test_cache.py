"""Lab 09 tests. Fully deterministic, no network, no real embedding model --
query vectors are fixed seeded fixtures. Tests define done."""
import numpy as np
import pytest


# ============================================================== step 1: exact match
def test_exact_match_hit_after_put(C):
    cache = C.ExactCache()
    cache.put("what is python?", "a programming language")
    assert cache.get("what is python?") == "a programming language"


def test_exact_match_miss_for_new_query(C):
    cache = C.ExactCache()
    assert cache.get("never seen this") is None


def test_exact_match_normalizes_case_and_whitespace(C):
    cache = C.ExactCache()
    cache.put("What is   Python?", "a programming language")
    assert cache.get("  what is python? ") == "a programming language"


def test_exact_match_does_not_match_different_query(C):
    cache = C.ExactCache()
    cache.put("what is python?", "a programming language")
    assert cache.get("what is rust?") is None


# ============================================================== step 2: prefix match
def test_prefix_match_hit_when_query_starts_with_cached_prefix(C):
    cache = C.PrefixCache(min_prefix_len=10)
    cache.put("translate to french: ", "bonjour")
    assert cache.get("translate to french: hello") == "bonjour"


def test_prefix_match_miss_when_prefix_too_short(C):
    cache = C.PrefixCache(min_prefix_len=20)
    cache.put("hi: ", "response")
    assert cache.get("hi: hello there") is None


def test_prefix_match_miss_when_query_does_not_start_with_prefix(C):
    cache = C.PrefixCache(min_prefix_len=5)
    cache.put("translate to french: ", "bonjour")
    assert cache.get("something else entirely") is None


def test_prefix_match_picks_longest_matching_prefix(C):
    """When two cached prefixes both match, the longer (more specific) one
    must win -- it is the safer, higher-confidence match."""
    cache = C.PrefixCache(min_prefix_len=5)
    cache.put("translate", "generic translation response")
    cache.put("translate to french:", "bonjour (french-specific)")
    assert cache.get("translate to french: good morning") == "bonjour (french-specific)"


# ============================================================== step 3: semantic match
def test_semantic_match_hit_above_threshold(C):
    cache = C.SemanticCache(threshold=0.8)
    cache.put(np.array([1.0, 0.0, 0.0]), "cached response")
    hit = cache.get(np.array([0.99, 0.01, 0.0]))
    assert hit is not None
    response, similarity = hit
    assert response == "cached response"
    assert similarity > 0.8


def test_semantic_match_miss_below_threshold(C):
    cache = C.SemanticCache(threshold=0.95)
    cache.put(np.array([1.0, 0.0, 0.0]), "cached response")
    hit = cache.get(np.array([0.5, 0.5, 0.0]))
    assert hit is None


def test_semantic_match_picks_nearest_neighbor(C):
    cache = C.SemanticCache(threshold=0.5)
    cache.put(np.array([1.0, 0.0]), "response A")
    cache.put(np.array([0.0, 1.0]), "response B")
    response, similarity = cache.get(np.array([0.1, 0.99]))
    assert response == "response B"


def test_semantic_match_empty_cache_is_a_miss(C):
    cache = C.SemanticCache(threshold=0.5)
    assert cache.get(np.array([1.0, 0.0])) is None


# ============================================================== step 4: layered orchestration
def test_layered_cache_prefers_exact_over_semantic(C):
    layered = C.LayeredCache(semantic_threshold=0.5)
    layered.put("what is python", "exact answer", query_vector=np.array([1.0, 0.0]))
    result = layered.get("what is python", query_vector=np.array([1.0, 0.0]))
    assert result.hit is True
    assert result.layer == "exact"
    assert result.response == "exact answer"


def test_layered_cache_prefers_prefix_over_semantic(C):
    layered = C.LayeredCache(semantic_threshold=0.5)
    layered.prefix.put("summarize: ", "prefix answer")
    layered.semantic.put(np.array([1.0, 0.0]), "semantic answer")
    result = layered.get("summarize: this long article", query_vector=np.array([1.0, 0.0]))
    assert result.layer == "prefix"
    assert result.response == "prefix answer"


def test_layered_cache_falls_through_to_semantic(C):
    layered = C.LayeredCache(semantic_threshold=0.8)
    layered.put("original question", "semantic answer", query_vector=np.array([1.0, 0.0]))
    result = layered.get("a rephrased version", query_vector=np.array([0.99, 0.01]))
    assert result.layer == "semantic"
    assert result.response == "semantic answer"
    assert result.similarity > 0.8


def test_layered_cache_total_miss_when_nothing_matches(C):
    layered = C.LayeredCache(semantic_threshold=0.99)
    layered.put("original question", "answer", query_vector=np.array([1.0, 0.0]))
    result = layered.get("completely unrelated query", query_vector=np.array([0.0, 1.0]))
    assert result.hit is False
    assert result.layer == "miss"
    assert result.response is None


# ============================================================== step 5: the threshold tradeoff
# 6 cached entries ("topics"), each a fixed seeded 32-dim unit vector.
# 6 "true paraphrase" queries -- one per topic, engineered to cosine ~0.93
#   against their OWN topic's cached vector and near enough to nothing else
#   to matter. Matching them to their own topic is always CORRECT.
# 8 "confusable" queries -- each engineered to a SPECIFIC cosine similarity
#   against a DIFFERENT (wrong) topic's cached vector: "refund policy for
#   annual plans" landing close to the cached "refund policy for monthly
#   plans" vector despite having a different correct answer. Their true
#   answer is never the topic they're confusable with, so being served that
#   topic's cached response is, by construction, a WRONG ANSWER.
# None of these numbers are tunable after the fact -- they fall out of the
# fixed vectors below.
CACHE_VECTORS = {
    0: [0.0068, 0.2691, 0.2424, -0.101, -0.059, -0.1044, 0.1128, -0.0111, 0.1478, -0.3656,
        0.31, -0.0191, 0.1347, -0.027, -0.075, 0.0917, 0.1632, -0.0401, -0.0302, 0.1357,
        -0.1723, -0.2997, 0.0782, -0.1327, -0.3801, -0.1611, -0.0925, -0.2361, -0.2954, 0.0073,
        0.1776, -0.0461],
    1: [-0.1581, 0.0819, 0.1525, -0.0638, 0.1158, 0.2218, -0.044, -0.173, 0.0739, 0.0526,
        0.2337, -0.2732, -0.1407, -0.1782, -0.3688, 0.0269, 0.1122, -0.1571, 0.2947, 0.1748,
        0.1334, 0.0854, 0.2032, -0.2833, 0.1306, 0.1282, -0.3759, 0.0738, -0.0533, 0.1662,
        -0.0934, -0.0039],
    2: [0.0574, -0.1467, 0.1002, -0.0176, 0.0824, -0.0873, 0.1818, 0.1013, -0.0298, 0.1058,
        0.2108, 0.2998, -0.2634, 0.1478, 0.0778, -0.0157, -0.1685, 0.2104, -0.2112, 0.0949,
        0.2179, -0.2677, -0.0506, -0.2191, 0.0408, 0.2535, 0.3387, -0.2976, -0.0962, 0.1178,
        0.2643, 0.0705],
    3: [-0.1396, 0.0556, -0.0031, -0.0381, -0.1374, 0.0725, 0.0576, -0.0174, -0.0415, -0.2404,
        -0.091, 0.2257, -0.0357, -0.2694, 0.2497, 0.0992, 0.3944, 0.0117, -0.0863, -0.2708,
        0.2477, 0.4807, -0.1536, -0.1211, 0.1115, -0.1554, -0.0506, -0.0655, 0.0359, 0.2048,
        0.0041, 0.1719],
    4: [-0.0716, 0.0559, -0.3644, -0.2471, 0.1357, -0.1006, 0.0988, 0.0924, 0.2254, 0.1384,
        0.1733, -0.019, -0.119, -0.1247, -0.0832, -0.1926, -0.0933, -0.0158, 0.0429, -0.0578,
        -0.3279, -0.0123, 0.0384, 0.1848, 0.0985, -0.1097, -0.1234, 0.3427, 0.129, 0.3121,
        0.3629, -0.1394],
    5: [0.1084, 0.1289, 0.1574, 0.1524, 0.0568, 0.049, -0.4226, -0.0465, -0.2103, 0.0355,
        -0.1315, 0.174, 0.2304, 0.0868, 0.0889, 0.0261, -0.126, -0.0463, -0.1394, 0.1091,
        0.004, 0.1635, -0.3737, 0.2497, -0.2145, -0.2065, -0.0555, -0.1585, 0.0819, -0.1615,
        -0.3008, -0.2379],
}
CACHE_RESPONSES = {i: f"canonical answer for topic {i}" for i in range(6)}

TRUE_QUERY_VECTORS = {
    0: [0.0958, 0.2664, 0.1578, -0.0983, -0.1635, 0.0196, 0.0067, 0.0217, 0.1816, -0.4564,
        0.3239, 0.0491, 0.1636, -0.0087, -0.0089, 0.1006, 0.1826, -0.0478, 0.0134, 0.0688,
        -0.1147, -0.3277, 0.0023, -0.105, -0.2568, -0.0923, -0.1256, -0.1836, -0.32, -0.0013,
        0.1799, -0.2027],
    1: [-0.1484, 0.0138, 0.1084, -0.1651, 0.0154, 0.1624, 0.011, -0.0637, 0.0738, 0.1277,
        0.2206, -0.4084, -0.1335, -0.1517, -0.4054, 0.0479, 0.1534, -0.2189, 0.2007, 0.1634,
        0.1219, 0.0633, 0.2744, -0.1722, 0.105, 0.1782, -0.3199, 0.1237, 0.0166, 0.1433,
        -0.0452, 0.1333],
    2: [0.1115, -0.1733, 0.1327, 0.0832, 0.099, -0.1183, 0.2751, -0.0109, 0.0138, 0.0889,
        0.0869, 0.3505, -0.1975, 0.0353, 0.1132, -0.047, -0.2917, 0.1258, -0.1596, 0.1304,
        0.1987, -0.2248, -0.0066, -0.2033, 0.1264, 0.2277, 0.3117, -0.2117, -0.1643, 0.0452,
        0.3443, 0.0862],
    3: [-0.1503, 0.0728, -0.0302, -0.021, -0.1699, 0.0853, -0.0337, 0.0584, -0.0689, -0.3207,
        -0.1002, 0.1963, -0.0257, -0.324, 0.2628, 0.3002, 0.3074, 0.0303, -0.1006, -0.2498,
        0.136, 0.3977, -0.1219, -0.1187, 0.1997, -0.1893, -0.0389, 0.1016, -0.0087, 0.1461,
        0.002, 0.163],
    4: [-0.0168, 0.059, -0.3796, -0.2153, 0.2783, -0.0187, -0.0707, 0.0769, 0.1567, 0.1636,
        0.1495, 0.0948, -0.0555, -0.0631, -0.0657, -0.1797, -0.0661, 0.0608, 0.0706, -0.0736,
        -0.2278, -0.0002, 0.0309, 0.1242, 0.0578, -0.138, -0.2759, 0.3747, 0.1517, 0.275,
        0.395, -0.1029],
    5: [0.1233, -0.0438, 0.1287, 0.1741, 0.1571, 0.1649, -0.2933, -0.1184, -0.3358, 0.0697,
        -0.1184, 0.2219, 0.2024, 0.0937, -0.0166, 0.0532, -0.1442, -0.0195, -0.0975, 0.0921,
        0.0243, 0.1486, -0.2921, 0.2611, -0.2319, -0.2272, 0.0631, -0.1515, 0.1396, -0.122,
        -0.3119, -0.2664],
}

# (query_vector, wrong_topic_it_resembles) -- true correct answer is NEVER
# wrong_topic's canonical answer, so any semantic hit here is a wrong answer.
CONFUSABLE_QUERIES = [
    ([0.016, 0.2585, 0.2649, -0.1948, -0.1016, -0.0999, 0.233, -0.2069, 0.1669, -0.3672,
      0.3092, -0.0579, 0.1491, 0.1069, -0.0365, 0.117, 0.1749, -0.098, 0.0187, 0.1022,
      -0.2196, -0.2673, 0.0499, -0.054, -0.3384, -0.1862, 0.0401, -0.1255, -0.1542, 0.0571,
      0.1473, -0.0757], 0),
    ([-0.1652, 0.1511, 0.1465, -0.1786, 0.1011, 0.084, -0.0261, -0.2541, -0.0367, 0.0571,
      0.204, -0.3817, -0.0656, 0.0162, -0.453, 0.1729, 0.0449, -0.1818, 0.2507, 0.0393,
      0.2262, 0.1172, 0.1216, -0.2777, -0.0063, 0.087, -0.262, -0.0737, -0.0836, 0.1616,
      0.0016, 0.1067], 1),
    ([0.0012, -0.1835, 0.1201, -0.0479, 0.0345, 0.0345, 0.3005, 0.1035, -0.0412, 0.1359,
      -0.0152, 0.2304, -0.3041, 0.3403, 0.1283, 0.0012, -0.1488, -0.0748, -0.0961, 0.2275,
      0.0998, -0.1427, 0.0291, -0.316, 0.1201, 0.3243, 0.2838, -0.2364, -0.0, -0.0545,
      0.2135, 0.1542], 2),
    ([-0.2876, 0.1817, -0.0591, -0.3134, -0.1324, -0.0688, 0.0926, -0.173, 0.106, -0.3064,
      -0.0302, 0.114, -0.0742, -0.0709, 0.2438, 0.032, 0.1704, 0.1665, 0.0246, -0.277,
      0.2458, 0.2746, -0.269, -0.2155, 0.1436, -0.0937, -0.1441, 0.0432, 0.1367, 0.1995,
      0.1436, 0.1091], 3),
    ([-0.0713, 0.1094, -0.2874, -0.0808, -0.0697, 0.1211, -0.0324, 0.0487, -0.0176, 0.1912,
      0.3123, 0.1348, 0.0241, -0.3142, -0.1738, -0.214, -0.2029, 0.1445, 0.059, -0.0482,
      -0.1862, -0.1425, -0.0971, 0.0203, 0.1459, -0.0374, -0.015, 0.4164, -0.0895, 0.1638,
      0.3021, -0.2965], 4),
    ([-0.0095, 0.2403, 0.2727, 0.2655, 0.0442, 0.0001, -0.1151, -0.0877, -0.0877, 0.2259,
      -0.1433, 0.022, 0.1512, 0.1489, 0.1326, 0.0411, 0.0015, -0.275, -0.2236, 0.0972,
      -0.1392, -0.0966, -0.4321, 0.0252, -0.1694, -0.2931, -0.0009, 0.1541, 0.0317, 0.0877,
      -0.1553, -0.3287], 5),
    ([-0.0238, 0.0654, 0.2404, -0.1916, 0.1073, -0.0037, -0.1495, 0.079, 0.2657, -0.3222,
      0.3078, -0.2098, 0.1144, -0.1998, 0.0047, -0.1373, -0.1841, 0.0177, 0.2318, 0.022,
      -0.0197, -0.1808, 0.0148, -0.0179, -0.0643, -0.2393, 0.0023, -0.1141, -0.3466, 0.182,
      0.3284, -0.1343], 0),
    ([0.1482, 0.0832, 0.1102, 0.194, 0.1425, 0.2541, 0.2143, 0.0596, 0.2161, -0.1869,
      -0.0524, -0.0579, -0.2819, -0.1359, -0.5122, -0.0065, -0.1128, 0.1311, 0.0952, 0.1372,
      0.0888, 0.2788, -0.0543, -0.261, 0.0827, 0.2043, -0.26, -0.0111, -0.0079, 0.0872,
      -0.0059, -0.0207], 1),
]


def _build_cache(C, threshold):
    cache = C.SemanticCache(threshold=threshold)
    for topic_id in range(6):
        cache.put(np.array(CACHE_VECTORS[topic_id]), CACHE_RESPONSES[topic_id])
    return cache


def _measure(C, threshold):
    """Run all 14 test queries (6 true paraphrases + 8 confusables) through a
    semantic cache set to `threshold`. Returns (hit_rate, wrong_answer_rate)
    as fractions of the full 14-query set."""
    cache = _build_cache(C, threshold)
    total = 6 + len(CONFUSABLE_QUERIES)
    hits = 0
    wrong = 0

    for topic_id, vec in TRUE_QUERY_VECTORS.items():
        hit = cache.get(np.array(vec))
        if hit is not None:
            hits += 1
            response, _ = hit
            if response != CACHE_RESPONSES[topic_id]:
                wrong += 1

    for vec, wrong_topic in CONFUSABLE_QUERIES:
        hit = cache.get(np.array(vec))
        if hit is not None:
            hits += 1
            # a confusable query's true answer is NEVER wrong_topic's answer,
            # so any served hit here is wrong by construction
            wrong += 1

    return hits / total, wrong / total


def test_true_paraphrases_always_match_their_own_topic(C):
    """Sanity check on the fixture itself: at a generous threshold, every
    true-paraphrase query must match its OWN topic, never someone else's."""
    cache = _build_cache(C, threshold=0.5)
    for topic_id, vec in TRUE_QUERY_VECTORS.items():
        response, similarity = cache.get(np.array(vec))
        assert response == CACHE_RESPONSES[topic_id]
        assert similarity > 0.9


def test_lowering_threshold_raises_hit_rate_and_wrong_answer_rate(C):
    """The centerpiece test: sweep the semantic threshold down across four
    settings and measure both hit rate and wrong-answer rate directly on the
    fixed, relevance-judged 14-query set above. A correct implementation
    must show BOTH climbing as the threshold drops -- that IS the tradeoff a
    semantic cache forces you to make. This is not asserted in prose; every
    number below is computed from the fixture."""
    thresholds = [0.90, 0.80, 0.70, 0.60]  # strictly decreasing
    hit_rates = []
    wrong_rates = []
    for th in thresholds:
        hr, wr = _measure(C, th)
        hit_rates.append(hr)
        wrong_rates.append(wr)

    # both metrics must be strictly increasing as threshold decreases
    for i in range(len(thresholds) - 1):
        assert hit_rates[i] < hit_rates[i + 1], (
            f"hit rate did not rise when threshold dropped from "
            f"{thresholds[i]} to {thresholds[i+1]}: {hit_rates}"
        )
        assert wrong_rates[i] < wrong_rates[i + 1], (
            f"wrong-answer rate did not rise when threshold dropped from "
            f"{thresholds[i]} to {thresholds[i+1]}: {wrong_rates}"
        )

    # and the exact, hand-verified numbers this fixture is built to produce
    assert hit_rates == [pytest.approx(v, abs=1e-9) for v in
                          [7 / 14, 9 / 14, 11 / 14, 13 / 14]]
    assert wrong_rates == [pytest.approx(v, abs=1e-9) for v in
                            [1 / 14, 3 / 14, 5 / 14, 7 / 14]]


def test_high_enough_threshold_has_zero_wrong_answers(C):
    """At a strict enough threshold, none of the confusable queries clear
    the bar -- wrong-answer rate is exactly the true-paraphrase baseline
    (zero, since true paraphrases always match correctly)."""
    hr, wr = _measure(C, threshold=0.95)
    assert wr == pytest.approx(0.0, abs=1e-9)
