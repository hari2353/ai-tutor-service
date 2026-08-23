"""Lab 08 tests — exact window math, separator ladders, and the no-loss
coverage property. Pure stdlib; no sleeps, no randomness without a seed."""
import random

import pytest

MIXED_PARAS = [
    "Retrieval quality starts at the boundary. Chunk it wrong and recall dies quietly.",
    "Fixed windows are cheap. Recursive splitting respects structure. Sentences are a decent floor.",
    "中文与 English 混排也要安全 🚀。重叠让答案跨块存活。",
    "Numbers 1234567890 and symbols !@#$% survive any splitter.",
]
MIXED = "\n\n".join(MIXED_PARAS) + "\n\n"


# ------------------------------------------------------------------ fixed
def test_fixed_single_chunk_when_text_fits(C):
    assert C.fixed_chunks("short", size=100, overlap=10) == ["short"]
    assert C.fixed_chunks("a" * 100, size=100, overlap=30) == ["a" * 100]
    chunks = C.fixed_chunks("a" * 101, size=100, overlap=30)
    assert chunks[0] == "a" * 100
    assert len(chunks) >= 2


def test_fixed_stride_math_exact(C):
    text = "0123456789" * 5                      # len 50, stride = 10 - 3 = 7
    expected = [
        "0123456789",   # [0:10]
        "7890123456",   # [7:17]
        "4567890123",   # [14:24]
        "1234567890",   # [21:31]
        "8901234567",   # [28:38]
        "5678901234",   # [35:45]
        "23456789",     # [42:50] — truncated tail, no redundant extra window
    ]
    assert C.fixed_chunks(text, size=10, overlap=3) == expected


def test_fixed_overlap_continuity(C):
    """Last `overlap` chars of chunk i are exactly the first `overlap` of i+1."""
    rng = random.Random(7)
    text = "".join(rng.choice("abcdefghij ") for _ in range(500))
    size, overlap = 40, 12
    chunks = C.fixed_chunks(text, size=size, overlap=overlap)
    assert len(chunks) > 2
    for prev, nxt in zip(chunks, chunks[1:]):
        assert len(nxt) >= overlap
        assert nxt[:overlap] == prev[-overlap:]
        assert len(prev) <= size


def test_fixed_rejects_bad_geometry_and_empty(C):
    with pytest.raises(ValueError):
        C.fixed_chunks("abc", size=5, overlap=5)     # stride 0 → infinite loop
    with pytest.raises(ValueError):
        C.fixed_chunks("abc", size=5, overlap=9)
    with pytest.raises(ValueError):
        C.fixed_chunks("abc", size=0, overlap=0)
    assert C.fixed_chunks("", size=10, overlap=3) == []


# ------------------------------------------------------------------ recursive
def test_recursive_respects_paragraph_boundaries(C):
    p1 = ("Alpha paragraph about retrieval quality. " * 2).strip()
    p2 = ("Beta paragraph about embedding drift. " * 2).strip()
    p3 = ("Gamma paragraph about rerankers. " * 2).strip()
    text = "\n\n".join([p1, p2, p3])
    chunks = C.recursive_chunks(text, size=100, overlap=0)
    assert len(chunks) == 3
    assert [c.strip() for c in chunks] == [p1, p2, p3]
    assert all(len(c) <= 100 for c in chunks)


def test_recursive_respects_paragraph_boundaries_with_overlap(C):
    p1 = ("Alpha paragraph about retrieval quality. " * 2).strip()
    p2 = ("Beta paragraph about embedding drift. " * 2).strip()
    text = "\n\n".join([p1, p2])
    chunks = C.recursive_chunks(text, size=100, overlap=10)
    assert all(c.endswith("\n\n") for c in chunks[:-1]), \
        "even with overlap, a chunk must not end mid-paragraph"


def test_recursive_falls_to_sentence_separator(C):
    """No paragraphs or lines exist; the ladder must fall to '. ' and still
    never exceed the cap."""
    text = "One. Two. Three. Four. Five."
    chunks = C.recursive_chunks(text, size=9, overlap=0)
    assert all(len(c) <= 9 for c in chunks)
    assert "".join(chunks) == text               # nothing dropped, order kept
    assert len(chunks) >= 3                      # actually split, not one blob


def test_recursive_long_unbreakable_token_splits_anyway(C):
    """95 chars with no separator in sight — character fallback must engage."""
    text = "Q" * 95
    chunks = C.recursive_chunks(text, size=20, separators=["\n\n", " "], overlap=0)
    assert "".join(chunks) == text
    assert sorted(map(len, chunks)) == [15, 20, 20, 20, 20]
    C.assert_no_loss(chunks, text)

    overlapped = C.recursive_chunks(text, size=20,
                                    separators=["\n\n", " "], overlap=8)
    assert all(len(c) <= 20 for c in overlapped)
    C.assert_no_loss(overlapped, text)


def test_recursive_custom_separators_and_defaults(C):
    assert C.recursive_chunks("aa\nbb\ncc", size=5,
                              separators=["\n"], overlap=0) == ["aa\n", "bb\ncc"]
    assert C.DEFAULT_SEPARATORS[0] == "\n\n"      # paragraph granularity first
    assert "" not in C.DEFAULT_SEPARATORS         # char fallback added internally


def test_recursive_never_exceeds_size_across_sweep(C):
    for size in (10, 17, 32, 64, 128):
        for ov in (0, size // 5):
            chunks = C.recursive_chunks(MIXED, size=size, overlap=ov)
            assert chunks, (size, ov)
            assert all(len(c) <= size for c in chunks), (size, ov)
            if ov == 0:
                assert "".join(chunks) == MIXED   # zero-overlap lossless concat


# ------------------------------------------------------------------ sentence
def test_sentence_boundaries_respected(C):
    text = "S1 is here. S2 follows! S3 asks? S4 ends."
    assert C.sentence_chunks(text, size=100, overlap_sentences=0) == [text]
    chunks = C.sentence_chunks(text, size=24, overlap_sentences=0)
    assert all(len(c) <= 24 for c in chunks)
    for c in chunks:
        assert c.lstrip().startswith("S")
        assert c.rstrip().endswith((".", "!", "?"))
    assert sum(c.count(".") + c.count("!") + c.count("?") for c in chunks) == 4
    C.assert_no_loss(chunks, text)


def test_sentence_overlap_count(C):
    sents = [f"w{i}x." for i in range(5)]
    text = " ".join(sents)                       # "w0x. w1x. w2x. w3x. w4x."
    two_per_chunk = C.sentence_chunks(text, size=10, overlap_sentences=1)
    assert two_per_chunk == [
        "w0x. w1x. ",
        "w1x. w2x. ",                            # shares w1x. with previous
        "w2x. w3x. ",
        "w3x. w4x.",
    ]
    no_overlap = C.sentence_chunks(text, size=10, overlap_sentences=0)
    assert no_overlap == ["w0x. w1x. ", "w2x. w3x. ", "w4x."]
    for prev, nxt in zip(two_per_chunk, two_per_chunk[1:]):
        shared = nxt[:nxt.index(".") + 1]
        assert nxt.startswith(shared)
        assert prev.rstrip().endswith(shared), "exactly one sentence overlaps"
        assert prev.count(shared) == nxt.count(shared) == 1


def test_sentence_oversized_single_sentence_emitted_alone(C):
    text = "B" * 45 + ". Short."
    chunks = C.sentence_chunks(text, size=10, overlap_sentences=1)
    assert any(len(c) > 10 for c in chunks), \
        "a monster sentence is emitted alone, not silently corrupted"
    assert chunks[-1].strip() == "Short."
    C.assert_no_loss(chunks, text)


def test_sentence_cjk_and_unicode_safe(C):
    text = "你好世界。检索增强生成。分块很重要！数据不会丢失？完成。"
    chunks = C.sentence_chunks(text, size=12, overlap_sentences=1)
    assert chunks
    assert all(len(c) <= 12 for c in chunks)
    for c in chunks[:-1]:
        assert c.rstrip().endswith(("。", "！", "？"))
    C.assert_no_loss(chunks, text)


def test_unicode_emoji_all_chunkers_no_crash_full_coverage(C):
    text = ("emoji 🚀 rocket. " * 8) + "中文段落一。\n\n中文段落二。第二句。" * 4
    for chunks in (
        C.fixed_chunks(text, size=37, overlap=11),
        C.recursive_chunks(text, size=50, overlap=8),
        C.sentence_chunks(text, size=29, overlap_sentences=1),
    ):
        assert chunks
        C.assert_no_loss(chunks, text)


# ------------------------------------------------------------------ inputs
def test_empty_and_whitespace_inputs(C):
    assert C.fixed_chunks("", size=10, overlap=2) == []
    assert C.recursive_chunks("", size=10) == []
    assert C.sentence_chunks("", size=10) == []
    C.assert_no_loss([], "")

    ws = "  \n\t\t  \n  "
    assert C.fixed_chunks(ws, size=4, overlap=1)
    C.assert_no_loss(C.fixed_chunks(ws, size=4, overlap=1), ws)
    assert "".join(C.recursive_chunks(ws, size=4)) == ws
    assert C.sentence_chunks(ws, size=4) == [ws]   # one honest whitespace span
    C.assert_no_loss(C.recursive_chunks(ws, size=4), ws)


# ------------------------------------------------------------------ property
def test_assert_no_loss_detects_corruption(C):
    C.assert_no_loss(["abcde", "defgh"], "abcdefgh")     # overlapping stitch: ok
    C.assert_no_loss(["a", "b", "c"], "abc")             # touching stitch: ok
    with pytest.raises(AssertionError):
        C.assert_no_loss(["abc", "xyz"], "abcdefxyz")    # gap between chunks
    with pytest.raises(AssertionError):
        C.assert_no_loss(["abc"], "abcd")                # trailing text lost
    with pytest.raises(AssertionError):
        C.assert_no_loss(["bcdef"], "abcdef")            # head lost
    with pytest.raises(AssertionError):
        C.assert_no_loss(["abz"], "abc")                 # chunk not from source
    with pytest.raises(AssertionError):
        C.assert_no_loss([], "abc")


def test_no_loss_property_mixed_corpus_all_three(C):
    cases = [
        lambda: C.fixed_chunks(MIXED, size=64, overlap=16),
        lambda: C.fixed_chunks(MIXED, size=200, overlap=0),
        lambda: C.recursive_chunks(MIXED, size=90, overlap=0),
        lambda: C.recursive_chunks(MIXED, size=120, overlap=20),
        lambda: C.recursive_chunks(MIXED, size=60,
                                   separators=["\n\n", ". ", " "]),
        lambda: C.sentence_chunks(MIXED, size=80, overlap_sentences=1),
        lambda: C.sentence_chunks(MIXED, size=45, overlap_sentences=2),
    ]
    for make in cases:
        chunks = make()
        assert chunks
        C.assert_no_loss(chunks, MIXED)
