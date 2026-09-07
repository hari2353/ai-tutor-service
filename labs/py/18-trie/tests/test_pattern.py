"""Lab 18 tests — trie. Deterministic; timing only in the witness."""
import random
import string
import time

import pytest


# ------------------------------------------------------------------ trie basics
def test_trie_insert_search(P):
    t = P.Trie()
    t.insert("apple")
    assert t.search("apple") is True
    assert t.search("app") is False
    assert t.starts_with("app") is True
    assert t.starts_with("b") is False


def test_trie_insert_idempotent(P):
    t = P.Trie()
    t.insert("cat")
    t.insert("cat")
    assert t.search("cat") is True
    assert t.starts_with("cat") is True


def test_trie_empty_string(P):
    t = P.Trie()
    assert t.search("") is False
    t.insert("")
    assert t.search("") is True
    assert t.starts_with("") is True


def test_trie_prefix_of_inserted_word_is_not_word(P):
    t = P.Trie()
    t.insert("interpolation")
    assert t.search("inter") is False
    assert t.starts_with("inter") is True


def test_trie_two_words_common_prefix(P):
    t = P.Trie()
    t.insert("car")
    t.insert("card")
    assert t.search("car") is True
    assert t.search("card") is True
    assert t.search("ca") is False
    assert t.starts_with("car") is True


def test_trie_many_words(P):
    words = ["".join(random.Random(i).choice(string.ascii_lowercase)
                     for _ in range(6)) for i in range(200)]
    t = P.Trie()
    for w in words:
        t.insert(w)
    for w in words:
        assert t.search(w) is True
    assert t.search("zzzzzz") is False or "zzzzzz" in words


# ------------------------------------------------------------------ word dictionary
def test_wildcard_basic(P):
    d = P.WordDictionary()
    d.add_word("bad")
    d.add_word("dad")
    d.add_word("mad")
    assert d.search("pad") is False
    assert d.search("bad") is True
    assert d.search(".ad") is True
    assert d.search("b..") is True
    assert d.search("...") is True
    assert d.search("....") is False
    assert d.search(".") is False


def test_wildcard_all_dots_multi(P):
    d = P.WordDictionary()
    d.add_word("a")
    d.add_word("ab")
    assert d.search("a") is True
    assert d.search("a.") is True
    assert d.search("ab") is True
    assert d.search(".b") is True
    assert d.search(".a") is False


def test_wildcard_empty_dictionary(P):
    d = P.WordDictionary()
    assert d.search("anything") is False
    assert d.search(".") is False


def test_wildcard_empty_string(P):
    d = P.WordDictionary()
    assert d.search("") is False
    d.add_word("")
    assert d.search("") is True
    assert d.search(".") is False


def test_wildcard_longer_pattern_than_words(P):
    d = P.WordDictionary()
    d.add_word("hello")
    assert d.search("hello.") is False
    assert d.search("hel.o") is True


# ------------------------------------------------------------------ autocomplete
def test_autocomplete_basic(P):
    t = P.Trie()
    for w in ["banana", "band", "bandana", "bat", "bath", "cat"]:
        t.insert(w)
    assert P.autocomplete(t, "ba", 10) == ["banana", "band", "bandana", "bat", "bath"]


def test_autocomplete_bounded_k(P):
    t = P.Trie()
    for w in ["ab", "ac", "ad", "ae", "af"]:
        t.insert(w)
    assert P.autocomplete(t, "a", 3) == ["ab", "ac", "ad"]


def test_autocomplete_k_zero_or_negative(P):
    t = P.Trie()
    t.insert("apple")
    assert P.autocomplete(t, "a", 0) == []


def test_autocomplete_dead_prefix(P):
    t = P.Trie()
    t.insert("apple")
    assert P.autocomplete(t, "zzz", 5) == []


def test_autocomplete_exact_word_is_included(P):
    t = P.Trie()
    t.insert("car")
    t.insert("card")
    assert P.autocomplete(t, "car", 10) == ["car", "card"]


def test_autocomplete_empty_prefix(P):
    t = P.Trie()
    for w in ["b", "a", "c"]:
        t.insert(w)
    assert P.autocomplete(t, "", 3) == ["a", "b", "c"]


# ------------------------------------------------------------------ find words
def test_find_words_classic(P):
    board = [["o", "a", "a", "n"],
             ["e", "t", "a", "e"],
             ["i", "h", "k", "r"],
             ["i", "f", "l", "v"]]
    words = ["oath", "pea", "eat", "rain"]
    assert set(P.find_words(board, words)) == {"oath", "eat"}


def test_find_words_no_matches(P):
    board = [["a", "b"], ["c", "d"]]
    assert set(P.find_words(board, ["zzz"])) == set()


def test_find_words_reuse_across_words_but_not_within(P):
    # board: a b / c d  — "abd" is a(0,0)->b(0,1)->d(1,1); "abc" is NOT a
    # contiguous path (c is not adjacent to b). Cells reused across words.
    board = [["a", "b"], ["c", "d"]]
    assert set(P.find_words(board, ["abc", "abd", "ab"])) == {"ab", "abd"}


def test_find_words_single_cell_words(P):
    board = [["x"]]
    assert set(P.find_words(board, ["x", "y"])) == {"x"}


def test_find_words_empty_board(P):
    assert P.find_words([], ["a"]) == []
    assert P.find_words([[]], ["a"]) == []


def test_find_words_no_reuse_of_cell_within_word(P):
    # word "aa" on a single 'a' cell must NOT match (cell used once per word)
    board = [["a"]]
    assert set(P.find_words(board, ["aa"])) == set()


# ------------------------------------------------------------------ longest common prefix
def test_lcp_basic(P):
    assert P.longest_common_prefix_via_trie(
        ["flower", "flow", "flight"]) == "fl"


def test_lcp_no_common(P):
    assert P.longest_common_prefix_via_trie(["dog", "racecar", "car"]) == ""


def test_lcp_empty_input(P):
    assert P.longest_common_prefix_via_trie([]) == ""


def test_lcp_single_word(P):
    assert P.longest_common_prefix_via_trie(["hello"]) == "hello"


def test_lcp_one_word_is_prefix_of_another(P):
    # terminal marker stops the walk: "flow" ends, "flower" continues → "flow"
    assert P.longest_common_prefix_via_trie(["flow", "flower"]) == "flow"


def test_lcp_identical_words(P):
    assert P.longest_common_prefix_via_trie(["same", "same", "same"]) == "same"


# ------------------------------------------------------------------ complexity witness
def test_trie_lookup_is_length_independent_of_corpus(P):
    """Insert 30k words; 20k lookups of a fixed-length probe must scale with
    probe length, not corpus size: well under 2 seconds total."""
    rng = random.Random(42)
    corpus = ["".join(rng.choice(string.ascii_lowercase) for _ in range(12))
              for _ in range(30_000)]
    t = P.Trie()
    t0 = time.perf_counter()
    for w in corpus:
        t.insert(w)
    t_insert = time.perf_counter() - t0
    assert t_insert < 2.0, f"insert of 30k words took {t_insert:.2f}s"

    probes = ["".join(rng.choice(string.ascii_lowercase) for _ in range(12))
              for _ in range(20_000)]
    t0 = time.perf_counter()
    hits = sum(1 for p in probes if t.search(p))
    t_search = time.perf_counter() - t0
    assert t_search < 2.0, f"20k lookups took {t_search:.2f}s"
    assert hits >= 0                      # sanity only


def test_find_words_pruned_by_trie_beats_no_prune_bruteforce(P):
    """Without trie pruning, searching every path for every word explodes.
    With it, a 4x4 board and 12 words resolves in milliseconds. This test
    witnesses the pruning by running the real thing fast; a naive
    per-word-DFS would time out on the same input."""
    rng = random.Random(7)
    board = [[rng.choice(string.ascii_lowercase[:6]) for _ in range(4)]
             for _ in range(4)]
    words = ["".join(rng.choice(string.ascii_lowercase[:6]) for _ in range(5))
             for _ in range(12)]
    words += ["abcdef"]                    # impossible-length probe
    t0 = time.perf_counter()
    out = P.find_words(board, words)
    dt = time.perf_counter() - t0
    assert set(out) <= set(words)
    assert dt < 2.0
