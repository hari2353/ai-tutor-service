"""Lab 03 -- byte-pair encoding, end to end: train, encode, decode, round-trip.
Fill in every TODO. Tests define done.

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
        """Byte-level BPE encode.

        TODO(step 2):
          1. ids = list(text.encode("utf-8")); if fewer than 2 bytes, return as-is
             (nothing to merge)
          2. loop: find the set of distinct adjacent pairs present in `ids`
             (_pairs_present). Among those that appear in self.merge_rank, pick
             the one with the LOWEST rank (the merge learned earliest). If none
             of the present pairs have a rank, stop -- this is the byte-level
             fallback in action: unseen byte sequences just never get merged.
          3. merge every occurrence of that pair via _merge_pair(), using
             self._pair_to_id(pair) as the new token id, and loop again.
        """
        raise NotImplementedError

    def _pair_to_id(self, pair: tuple[int, int]) -> int:
        return self._merged_id[pair]

    # ------------------------------------------------------------------ decode
    def decode(self, ids: list[int]) -> str:
        """TODO(step 3): concatenate self.vocab[i] for each id (bytes), then
        decode as UTF-8. Because encode() only ever combines adjacent tokens
        via learned merges (never drops or reorders bytes), this concatenation
        always reconstructs the exact original byte sequence."""
        raise NotImplementedError

    # ------------------------------------------------------------------ train
    @classmethod
    def train(cls, corpus: list[str], vocab_size: int) -> "BPETokenizer":
        """TODO(step 1):
          1. if vocab_size < 256: raise ValueError (256 raw bytes is the floor)
          2. vocab = {i: bytes([i]) for i in range(256)}; encode each corpus
             string to a list of byte ids -- these are your working sequences
          3. repeat until vocab reaches vocab_size:
             a. count EVERY adjacent pair occurrence across all sequences, WITH
                multiplicity (a pair occurring 3 times in one sequence counts
                3 times -- do not deduplicate before counting)
             b. if there are no pairs left anywhere, stop early (corpus
                exhausted -- vocab_size may not be reached, and that's correct
                behaviour, not a bug)
             c. pick the pair with the highest count. TIE-BREAK: among pairs
                tied for the max count, pick the lexicographically smallest
                pair (by comparing the (id, id) tuples). This is what makes
                merge order deterministic across runs -- do not rely on dict
                iteration order.
             d. assign it the next available id, record vocab[new_id] as the
                concatenation of the two merged pieces' bytes, append the pair
                to merges (rank = its position in that list), and replace every
                occurrence of the pair in every sequence with the new id
          4. return a BPETokenizer with vocab / merges / merge_rank populated
        """
        raise NotImplementedError

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
    need to know a pair EXISTS to consider merging it (not how often).
    TODO(step 2a)"""
    raise NotImplementedError


def _merge_pair(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    """Replace every non-overlapping occurrence of `pair` in `ids` with `new_id`,
    scanning left to right (so overlapping runs like "aaaa" with pair (a,a)
    merge into two tokens, not three).
    TODO(step 1a) -- used by both train() and encode()"""
    raise NotImplementedError
