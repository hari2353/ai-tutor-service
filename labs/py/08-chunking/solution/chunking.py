"""Lab 08 — reference solution: fixed, recursive, and sentence chunking."""
from __future__ import annotations

import re

DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]

# A sentence ends at a .!? (optionally closed quotes/brackets) followed by
# whitespace, OR at CJK terminal punctuation, which needs no trailing space.
_SENTENCE_BOUNDARY = re.compile(r"[.!?…。！？]+[\"'”’)\]]*\s+|[。！？]+")


def fixed_chunks(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Hard character windows: chunk i covers [i*(size-overlap), ...+size).
    Last window is truncated rather than duplicated. [] for empty text."""
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    if not 0 <= overlap < size:
        raise ValueError(f"overlap must satisfy 0 <= overlap < size, got {overlap}")
    if not text:
        return []
    step = size - overlap
    chunks: list[str] = []
    start = 0
    while True:
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += step
    return chunks


def recursive_chunks(text: str, size: int,
                     separators: list[str] | None = None,
                     overlap: int = 0) -> list[str]:
    """Split on the best separator that makes pieces fit, falling down the
    ladder (paragraph -> line -> sentence -> word -> character) only where a
    piece is still too big. Character-level splitting is always the final
    fallback, so unbreakable tokens get split anyway. Every chunk <= size.
    With overlap=0 the chunks concatenate back to the original text exactly;
    with overlap>0 each later chunk is prefixed with up to `overlap` leading
    characters of context, capped so the size bound still holds."""
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    if not 0 <= overlap < size:
        raise ValueError(f"overlap must satisfy 0 <= overlap < size, got {overlap}")
    seps = list(DEFAULT_SEPARATORS) if separators is None else list(separators)
    if "" not in seps:
        seps.append("")
    leaves = _split_spans(text, 0, len(text), size, tuple(seps))
    groups = _pack_spans(leaves, size)
    return _materialize(text, groups, overlap, size)


def _segments(text: str, lo: int, hi: int, sep: str) -> list[tuple[int, int]]:
    """Sub-spans of [lo, hi) split on sep, keeping sep glued to the END of
    the preceding piece, so pieces concatenate back to text[lo:hi] exactly."""
    spans: list[tuple[int, int]] = []
    pos = lo
    parts = text[lo:hi].split(sep)
    for i, part in enumerate(parts):
        n = len(part) + (len(sep) if i < len(parts) - 1 else 0)
        if n:
            spans.append((pos, pos + n))
        pos += n
    return spans


def _split_spans(text: str, lo: int, hi: int, size: int,
                 seps: tuple[str, ...]) -> list[tuple[int, int]]:
    """Leaf spans that exactly tile [lo, hi), each no longer than size once
    the ladder bottoms out at the '' (character) separator."""
    if hi - lo <= size:
        return [(lo, hi)] if hi > lo else []
    sep, rest = seps[0], seps[1:]
    if sep == "":
        return [(i, i + 1) for i in range(lo, hi)]
    out: list[tuple[int, int]] = []
    for a, b in _segments(text, lo, hi, sep):
        if b - a > size and rest:
            out.extend(_split_spans(text, a, b, size, rest))
        else:
            out.append((a, b))
    return out


def _pack_spans(spans: list[tuple[int, int]],
                size: int) -> list[tuple[int, int]]:
    """Greedily merge adjacent spans while the merged span stays <= size."""
    groups: list[tuple[int, int]] = []
    cur_a, cur_b = None, None
    for a, b in spans:
        if cur_a is None:
            cur_a, cur_b = a, b
        elif b - cur_a <= size:
            cur_b = b
        else:
            groups.append((cur_a, cur_b))
            cur_a, cur_b = a, b
    if cur_a is not None:
        groups.append((cur_a, cur_b))
    return groups


def _materialize(text: str, groups: list[tuple[int, int]], overlap: int,
                 size: int) -> list[str]:
    chunks: list[str] = []
    prev_start = 0
    for k, (a, b) in enumerate(groups):
        s = a
        if k and overlap > 0:
            s = a - min(overlap, size - (b - a), a - prev_start)
        chunks.append(text[s:b])
        prev_start = s
    return chunks


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) sentence spans that exactly tile `text`; trailing
    whitespace sticks to the preceding sentence."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _SENTENCE_BOUNDARY.finditer(text):
        spans.append((pos, m.end()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def sentences(text: str) -> list[str]:
    return [text[a:b] for a, b in sentence_spans(text)]


def sentence_chunks(text: str, size: int, overlap_sentences: int = 1) -> list[str]:
    """Pack whole sentences into chunks <= size. Each chunk after the first
    repeats the last `overlap_sentences` sentences of the previous chunk (as
    many as fit). A single sentence longer than size is emitted alone — an
    honest boundary beats a dishonest cut. [] for empty text."""
    if size < 1:
        raise ValueError(f"size must be >= 1, got {size}")
    if overlap_sentences < 0:
        raise ValueError(f"overlap_sentences must be >= 0, got {overlap_sentences}")
    spans = sentence_spans(text)
    if not spans:
        return []
    n = len(spans)
    chunks: list[str] = []
    i = 0
    while i < n:
        j = i
        while j < n and spans[j][1] - spans[i][0] <= size:
            j += 1
        if j == i:
            j = i + 1
        chunks.append(text[spans[i][0]:spans[j - 1][1]])
        if j >= n:
            break
        i = max(i + 1, j - overlap_sentences)
    return chunks


def assert_no_loss(chunks: list[str], text: str) -> None:
    """Property check: stitched back onto the source (overlaps collapsed),
    the chunks must cover every character index — nothing before the first
    chunk, no gap between consecutive chunks, nothing after the last.
    Raises AssertionError naming the first uncovered range."""
    if not chunks:
        assert not text, "chunker returned no chunks for non-empty text"
        return
    prev_start = 0
    prev_end = 0
    for k, chunk in enumerate(chunks):
        assert chunk, f"chunk {k} is empty"
        occ = text.find(chunk, prev_start)
        assert occ != -1, f"chunk {k} does not occur in the source text"
        # Take the latest occurrence that still starts at or before the covered
        # frontier — on repetitive text the earliest match would never advance.
        best = None
        while occ != -1 and occ <= prev_end:
            best = occ
            occ = text.find(chunk, occ + 1)
        assert best is not None, (
            f"gap before chunk {k}: chars [{prev_end}, ...) "
            "are in no chunk before it begins")
        if k == 0:
            assert best == 0, "coverage starts at 0 but first chunk sits later"
        prev_start = best
        prev_end = best + len(chunk)
    assert prev_end == len(text), (
        f"trailing text lost: chars [{prev_end}, {len(text)}) are in no chunk")
