"""Lab 03 tests. Determinism is the whole point — no randomness anywhere."""
import pytest


CORPUS = "the quick brown fox jumps over the lazy dog. " * 20

MULTILINGUAL = (
    "ASCII first. Héllo wörld — naïve café. "
    "你好，世界。机器学习改变世界。 "
    "Привет мир. "
    "rockets 🚀 fire 🔥 family 👨‍👩‍👧‍👦 done."
)


# ------------------------------------------------------------------ roundtrips
def test_roundtrip_ascii(T):
    m = T.train(CORPUS, 280)
    s = "The quick brown fox jumps over the lazy dog!"
    assert T.decode(T.encode(s, m), m) == s


def test_roundtrip_accents(T):
    m = T.train(CORPUS, 280)
    s = "Héllo wörld — naïve café, crème brûlée"
    assert T.decode(T.encode(s, m), m) == s


def test_roundtrip_cjk(T):
    m = T.train(CORPUS, 280)
    s = "机器学习改变世界，你好世界"
    assert T.decode(T.encode(s, m), m) == s


def test_roundtrip_emoji_and_zwj(T):
    m = T.train(CORPUS, 280)
    s = "ship it 🚀🔥 status 👨‍👩‍👧‍👦 ok ✅"
    assert T.decode(T.encode(s, m), m) == s


def test_roundtrip_combined_multilingual(T):
    m = T.train(CORPUS, 290)
    assert T.decode(T.encode(MULTILINGUAL, m), m) == MULTILINGUAL


def test_empty_string_everywhere(T):
    m = T.train("", 300)
    assert m == []
    assert T.encode("", m) == []
    assert T.decode([], m) == ""


# ------------------------------------------------------------------ training
def test_merge_count_respects_vocab_size_minus_256(T):
    m = T.train(CORPUS, 290)
    assert len(m) == 290 - 256
    m2 = T.train(CORPUS, 275)
    assert len(m2) == 275 - 256


def test_vocab_size_256_means_no_merges(T):
    assert T.train(CORPUS, 256) == []


def test_most_frequent_pair_merged_first(T):
    # (a,b) occurs 10x, every other pair fewer → must be merge #0.
    m = T.train("ab" * 10 + "cd" * 3, 260)
    assert len(m) >= 1
    assert m[0] == (ord("a"), ord("b"))


def test_ties_break_to_lowest_pair_not_first_seen(T):
    # All three pairs occur once; (c,d) is seen FIRST while scanning,
    # but (a,b) is the lowest tuple and must win.
    m = T.train("cdab", 258)
    assert m[0] == (ord("a"), ord("b"))


def test_crafted_corpus_full_merge_chain(T):
    # abcabcabc → (a,b) ties with (b,c), lowest wins; then (AB,c); then (ABc,ABc).
    m = T.train("abcabcabc", 259)
    assert m == [(ord("a"), ord("b")), (256, 99), (257, 257)]
    # The learned chain compresses the training fragment to ONE id.
    assert T.encode("abcabc", m) == [258]


def test_training_is_deterministic_across_runs(T):
    assert T.train(CORPUS, 288) == T.train(CORPUS, 288)


def test_merges_are_well_formed_tuples(T):
    m = T.train(CORPUS, 270)
    assert isinstance(m, list) and len(m) > 0
    for t in m:
        assert isinstance(t, tuple) and len(t) == 2
        assert all(isinstance(x, int) and x >= 0 for x in t)
    a, b = m[0]
    assert a < 256 and b < 256          # the first merge is a pure byte pair


# ------------------------------------------------------------------ encoding
def test_unmerged_pairs_fall_back_to_raw_bytes(T):
    m = T.train("abcabcabc", 259)
    ids = T.encode("zzz q?", m)         # z, ?, space never participated in a merge
    assert all(i < 256 for i in ids)
    assert T.decode(ids, m) == "zzz q?"


def test_encode_returns_list_of_ints(T):
    m = T.train(CORPUS, 280)
    ids = T.encode("jumps over", m)
    assert isinstance(ids, list)
    assert all(isinstance(i, int) for i in ids)


# ------------------------------------------------------------------ decoding errors
def test_decode_unknown_id_raises_valueerror(T):
    m = T.train(CORPUS, 270)
    with pytest.raises(ValueError):
        T.decode([10_000_000], m)


def test_decode_invalid_utf8_is_also_a_valueerror(T):
    # 0x80 alone is a dangling continuation byte → UnicodeDecodeError,
    # which IS a ValueError subclass. Clean either way.
    with pytest.raises(ValueError):
        T.decode([0x80], [])
