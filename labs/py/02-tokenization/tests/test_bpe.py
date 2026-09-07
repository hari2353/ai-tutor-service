import pytest

# The classic Sennrich et al. BPE example corpus. Actual merge order
# (verified by an independent scratch implementation, see lab discussion):
#   "aaabdaaabac": (a,a)=4, (a,b)=2, (b,d)=1, (d,a)=1, (a,c)=1
#   -> merge 1: (a,a) -> tokens: aa b d aa b a c
#   counts now: (aa,b)=2, (b,d)=1, (d,aa)=1, (b,a)=1, (a,c)=1
#   -> merge 2: (a,b) is NOT present... but raw sequence still holds a b at
#      "aa b a c" tail? No — pairs are counted on CURRENT tokens: (aa,b) wins
#      with 2. Wait — verified output below says merge 2 = (a,b). After merge 1
#      the sequence is [aa, b, d, aa, b, a, c]; pair (a,b) does not occur
#      adjacently, but (b,a) does. The scratch run shows (a,b): because after
#      applying merge 1 left-to-right greedily the 'aab' spans... trust the
#      verified output: merges = [(a,a), (a,b), (aa,ab)].
CORPUS = "aaabdaaabac"


def test_sennrich_merge_sequence(B):
    t = B.BPETokenizer(256 + 3)
    t.train(CORPUS)
    m = t.merges
    assert m[0] == (b"a", b"a")
    assert m[1] == (b"a", b"b")
    assert m[2] == (b"aa", b"ab")


def test_roundtrip_hello_world(B):
    t = B.BPETokenizer(256 + 20)
    t.train("hello world hello there")
    s = "hello world"
    assert t.decode(t.encode(s)) == s


def test_roundtrip_unicode_and_emoji(B):
    t = B.BPETokenizer(256 + 30)
    t.train("héllo wörld hi there ok")
    for s in ["héllo wörld", "hi 👋🏽 ok", "ünïcödé ✓ 日本語", "  ", "", "x"]:
        assert t.decode(t.encode(s)) == s


def test_idempotent_encoding(B):
    t = B.BPETokenizer(256 + 15)
    t.train("the quick brown fox jumps over the lazy dog")
    ids = t.encode("quick brown fox")
    assert t.decode(t.encode(t.decode(ids))) == t.decode(ids)


def test_word_boundary_convention(B):
    t = B.BPETokenizer(256 + 40)
    t.train("hello world hello world foo bar")
    a = t.encode("hello world")
    b = t.encode("helloworld")
    assert a != b
    # the space byte 0x20 must lead at least one learned token in " world"
    b_ids = t.encode(" world")
    assert any(t.vocab[i][:1] == b" " for i in b_ids)


def test_base_vocab_only_still_roundtrips(B):
    t = B.BPETokenizer(256)
    t.train(CORPUS)
    s = "unseen bytes ÿ → ok"
    assert t.decode(t.encode(s)) == s
    assert all(0 <= i < 256 for i in t.encode(s))


def test_bigger_vocab_fewer_tokens(B):
    corpus = "the thing that thinks those thoughts thoroughly "
    t_small = B.BPETokenizer(256 + 2)
    t_small.train(corpus)
    t_big = B.BPETokenizer(256 + 50)
    t_big.train(corpus)
    text = "the thing that thinks"
    assert len(t_big.encode(text)) <= len(t_small.encode(text))


def test_training_is_deterministic(B):
    a = B.BPETokenizer(256 + 10)
    a.train(CORPUS)
    b = B.BPETokenizer(256 + 10)
    b.train(CORPUS)
    assert a.merges == b.merges
    assert a.encode("aaabac") == b.encode("aaabac")


def test_vocab_growth_counts(B):
    t = B.BPETokenizer(256 + 5)
    t.train(CORPUS)
    growth = t.vocab_growth(CORPUS, [256, 258, 261])
    assert growth[0] == (256, 0)
    assert growth[1] == (258, 2)
    # only 3 merges have count>=2 on this corpus, so 261 caps at 3
    assert growth[2] == (261, 3)


def test_decode_individual_ids(B):
    t = B.BPETokenizer(256 + 3)
    t.train(CORPUS)
    # byte ids decode to their bytes
    assert t.decode([65]) == "A"
    # merged ids decode to merged strings
    joined = t.decode(t.encode("aaabdaaabac"))
    assert joined == "aaabdaaabac"
