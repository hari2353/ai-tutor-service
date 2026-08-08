"""Lab 03 tests. No network, no downloads -- corpora are inline strings."""
import pytest

CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "the dog barks at the quick fox",
    "the quick brown fox runs away from the dog",
    "a lazy dog sleeps while the quick fox watches",
    "the fox and the dog are not friends",
] * 4

TINY_REPEATED_CORPUS = ["ababababababab"] * 20


# ------------------------------------------------------------------ base vocab
def test_base_vocab_is_256_bytes_with_no_merges(T):
    tok = T.BPETokenizer.train([], vocab_size=256)
    assert tok.vocab_size == 256
    assert tok.merges == []
    assert all(isinstance(b, bytes) for b in tok.vocab.values())


def test_vocab_entries_are_bytes(T):
    tok = T.BPETokenizer.train(CORPUS, vocab_size=280)
    assert all(isinstance(v, bytes) for v in tok.vocab.values())
    for i in range(256):
        assert tok.vocab[i] == bytes([i])


# ------------------------------------------------------------------ vocab size respected
def test_vocab_size_respected_when_reachable(T):
    tok = T.BPETokenizer.train(CORPUS, vocab_size=300)
    assert tok.vocab_size <= 300
    assert tok.vocab_size == 300, "corpus has enough distinct pairs to reach the target"


def test_vocab_size_capped_when_corpus_exhausted(T):
    tok = T.BPETokenizer.train(["ab"], vocab_size=1000)
    assert tok.vocab_size < 1000
    assert tok.vocab_size == 257  # exactly one mergeable pair: (a, b)


def test_vocab_size_never_below_256(T):
    with pytest.raises(ValueError):
        T.BPETokenizer.train(CORPUS, vocab_size=200)


# ------------------------------------------------------------------ deterministic merges
def test_merges_deterministic_across_runs(T):
    tok1 = T.BPETokenizer.train(CORPUS, vocab_size=290)
    tok2 = T.BPETokenizer.train(CORPUS, vocab_size=290)
    assert tok1.merges == tok2.merges


def test_merges_deterministic_with_ties(T):
    """A corpus engineered to have frequency ties on the first merge --
    determinism must come from an explicit tie-break rule, not dict order."""
    corpus = ["ab", "cd", "ab", "cd"]
    tok1 = T.BPETokenizer.train(corpus, vocab_size=257)
    tok2 = T.BPETokenizer.train(corpus, vocab_size=257)
    assert tok1.merges == tok2.merges
    assert tok1.merges == [(97, 98)]  # (a,b) < (c,d) lexicographically -- the tie-break


# ------------------------------------------------------------------ round-trip
@pytest.fixture
def trained(T):
    return T.BPETokenizer.train(CORPUS, vocab_size=300)


def test_roundtrip_ascii(T, trained):
    for s in ["the quick brown fox", "hello world", "", "a", "THE QUICK FOX 123!?"]:
        assert trained.decode(trained.encode(s)) == s


def test_roundtrip_unicode(T, trained):
    for s in ["héllo wörld", "日本語のテスト", "Привет мир", "café naïve résumé", "north star: ★"]:
        assert trained.decode(trained.encode(s)) == s


def test_roundtrip_emoji(T, trained):
    for s in ["🎉🚀😀", "party 🎉 time 🚀!", "family: 👨‍👩‍👧‍👦", "flag: 🇨🇦"]:
        assert trained.decode(trained.encode(s)) == s


def test_roundtrip_empty_string(T, trained):
    assert trained.encode("") == []
    assert trained.decode([]) == ""


def test_roundtrip_mixed_scripts_and_whitespace(T, trained):
    s = "  the fox\tjumps\n日本語 🎉  café  "
    assert trained.decode(trained.encode(s)) == s


def test_roundtrip_long_random_unicode(T, trained):
    import random
    rng = random.Random(42)
    chars = "abcdefgh日本語えい🎉🚀😀★中文字符" + " \t\n"
    s = "".join(rng.choice(chars) for _ in range(500))
    assert trained.decode(trained.encode(s)) == s


# ------------------------------------------------------------------ byte-level fallback
def test_byte_fallback_for_input_absent_from_training_corpus(T):
    """Trained only on plain English ASCII. Any unicode/emoji thrown at encode()
    was never seen -- there is no merge for it -- so it must still round-trip
    exactly via the byte-level fallback (no crash, no data loss, no UNK token)."""
    tok = T.BPETokenizer.train(["the quick brown fox jumps over the lazy dog"] * 10,
                                vocab_size=270)
    unseen = "日本語テスト 🎉🚀😀 emoji и русский текст"
    assert tok.decode(tok.encode(unseen)) == unseen


def test_byte_fallback_handles_arbitrary_bytes_like_symbols(T):
    tok = T.BPETokenizer.train(["hello world"] * 5, vocab_size=260)
    s = "\x00\x01\x02 weird ﻿ control chars ​"
    assert tok.decode(tok.encode(s)) == s


# ------------------------------------------------------------------ merges are actually used
def test_encode_uses_learned_merges_to_shrink_token_count(T):
    tok = T.BPETokenizer.train(TINY_REPEATED_CORPUS, vocab_size=257)
    s = "abababab"
    encoded = tok.encode(s)
    raw_byte_len = len(s.encode("utf-8"))
    assert len(encoded) < raw_byte_len, "merges were learned but never applied at encode time"
    assert tok.decode(encoded) == s


def test_untrained_tokenizer_is_pure_byte_level(T):
    """Zero merges means encode() is just UTF-8 byte values -- the baseline
    the byte-level fallback degrades to."""
    tok = T.BPETokenizer.train([], vocab_size=256)
    s = "hello"
    assert tok.encode(s) == list(s.encode("utf-8"))


# ------------------------------------------------------------------ decode of known ids
def test_decode_reconstructs_exact_bytes_for_known_merge(T):
    tok = T.BPETokenizer.train(["ab"], vocab_size=257)
    merged_id = 256
    assert tok.vocab[merged_id] == b"ab"
    assert tok.decode([merged_id]) == "ab"
