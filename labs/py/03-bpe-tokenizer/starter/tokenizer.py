"""Lab 03 — byte-level BPE tokenizer. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib, fully deterministic — no randomness anywhere.
  * Base vocab = the 256 bytes. Merge #k creates id 256 + k.
  * Pair ties break to the lowest (left_id, right_id) tuple.
"""
from __future__ import annotations


Pair = tuple[int, int]


def _byte_ids(text: str) -> list[int]:
    """UTF-8 encode `text` and return the list of byte ids."""
    # TODO(step 0)
    raise NotImplementedError


def _merge_once(ids: list[int], pair: Pair, new_id: int) -> list[int]:
    """Replace every non-overlapping occurrence of `pair` (left-to-right)
    in `ids` with `new_id`."""
    # TODO(step 1)
    raise NotImplementedError


def train(text: str, vocab_size: int) -> list[Pair]:
    """Learn merges until the vocab reaches vocab_size (256 base + N merges).

    Each iteration: count adjacent pairs over the whole sequence, pick the
    most frequent (ties → lowest pair tuple), merge it everywhere.
    Stops early if fewer than two ids remain or no pairs are left.
    """
    # TODO(step 2)
    raise NotImplementedError


def encode(text: str, merges: list[Pair]) -> list[int]:
    """Apply merges by rank (earliest learned first) until none applies.

    Pairs that were never merged stay as raw byte ids.
    """
    # TODO(step 3)
    raise NotImplementedError


def decode(ids: list[int], merges: list[Pair]) -> str:
    """Rebuild id → bytes from the merges, join, decode UTF-8.

    Unknown ids raise ValueError. Invalid UTF-8 raises UnicodeDecodeError
    (a ValueError subclass). Both are "clean" errors.
    """
    # TODO(step 4)
    raise NotImplementedError
