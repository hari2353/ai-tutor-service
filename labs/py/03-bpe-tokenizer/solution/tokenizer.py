"""Lab 03 -- byte-pair encoding, end to end: train, encode, decode, round-trip.

Byte-level base alphabet (256 raw byte values, GPT-2 style) means there is no
out-of-vocabulary case: any string, in any language, with any emoji or stray
binary garbage, decomposes to bytes and is therefore always encodable. That is
the byte-level fallback -- it isn't a special code path, it's just what happens
when zero merges apply.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class BPETokenizer:
    vocab: dict[int, bytes] = field(default_factory=dict)          # id -> byte sequence
    merges: list[tuple[int, int]] = field(default_factory=list)    # in application order
    merge_rank: dict[tuple[int, int], int] = field(default_factory=dict)  # pair -> priority (lower = earlier)

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    # ------------------------------------------------------------------ encode
    def encode(self, text: str) -> list[int]:
        """Byte-level BPE encode. Falls back to raw bytes automatically: an
        input containing byte sequences never seen during training simply has
        no applicable merges, and comes back out as individual byte tokens
        (ids 0-255), which are always valid vocabulary entries."""
        ids = list(text.encode("utf-8"))
        if len(ids) < 2:
            return ids

        while True:
            pairs = _pairs_present(ids)
            if not pairs:
                break
            # of the pairs present in this sequence, apply the one with the
            # lowest merge rank (i.e. the one learned earliest during training)
            candidate = min(
                (p for p in pairs if p in self.merge_rank),
                key=lambda p: self.merge_rank[p],
                default=None,
            )
            if candidate is None:
                break
            ids = _merge_pair(ids, candidate, self._pair_to_id(candidate))
        return ids

    def _pair_to_id(self, pair: tuple[int, int]) -> int:
        return self._merged_id[pair]

    # ------------------------------------------------------------------ decode
    def decode(self, ids: list[int]) -> str:
        raw = b"".join(self.vocab[i] for i in ids)
        return raw.decode("utf-8")

    # ------------------------------------------------------------------ train
    @classmethod
    def train(cls, corpus: list[str], vocab_size: int) -> "BPETokenizer":
        if vocab_size < 256:
            raise ValueError("vocab_size must be >= 256 (the base byte alphabet)")

        vocab: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
        sequences: list[list[int]] = [list(text.encode("utf-8")) for text in corpus]

        merges: list[tuple[int, int]] = []
        merge_rank: dict[tuple[int, int], int] = {}
        merged_id: dict[tuple[int, int], int] = {}

        next_id = 256
        while next_id < vocab_size:
            counts: Counter[tuple[int, int]] = Counter()
            for seq in sequences:
                # count WITH multiplicity: a pair occurring 3 times in one
                # sequence must contribute 3, not 1 -- this is not a dedup step
                for i in range(len(seq) - 1):
                    counts[(seq[i], seq[i + 1])] += 1
            if not counts:
                break  # corpus exhausted, no more adjacent pairs anywhere

            best_count = max(counts.values())
            # Deterministic tie-break: among pairs at the max frequency, pick
            # the lexicographically smallest (by the pair of ids). This makes
            # merge order reproducible across runs/machines regardless of
            # dict/hash iteration order.
            best_pair = min(p for p, c in counts.items() if c == best_count)

            vocab[next_id] = vocab[best_pair[0]] + vocab[best_pair[1]]
            merges.append(best_pair)
            merge_rank[best_pair] = len(merges) - 1
            merged_id[best_pair] = next_id

            sequences = [_merge_pair(seq, best_pair, next_id) for seq in sequences]
            next_id += 1

        tok = cls(vocab=vocab, merges=merges, merge_rank=merge_rank)
        tok._merged_id = merged_id
        return tok

    def __post_init__(self):
        # rebuild the pair->new_id lookup from merges if constructed directly
        # (e.g. by a test) rather than via .train()
        if not hasattr(self, "_merged_id"):
            self._merged_id = {}
            next_id = 256
            for pair in self.merges:
                self._merged_id[pair] = next_id
                next_id += 1


def _pairs_present(ids: list[int]) -> set[tuple[int, int]]:
    """Set of distinct adjacent pairs -- used at encode time, where we only
    need to know a pair EXISTS to consider merging it (not how often)."""
    return {(ids[i], ids[i + 1]) for i in range(len(ids) - 1)}


def _merge_pair(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    """Replace every non-overlapping occurrence of `pair` in `ids` with `new_id`."""
    out = []
    i = 0
    n = len(ids)
    while i < n:
        if i < n - 1 and (ids[i], ids[i + 1]) == pair:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out
