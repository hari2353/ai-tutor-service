"""Lab 03 — reference solution."""
from __future__ import annotations

from collections import Counter


Pair = tuple[int, int]


def _byte_ids(text: str) -> list[int]:
    return list(text.encode("utf-8"))


def _merge_once(ids: list[int], pair: Pair, new_id: int) -> list[int]:
    out: list[int] = []
    i = 0
    n = len(ids)
    while i < n:
        if i < n - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out


def train(text: str, vocab_size: int) -> list[Pair]:
    num_merges = max(0, vocab_size - 256)
    ids = _byte_ids(text)
    merges: list[Pair] = []
    for _ in range(num_merges):
        if len(ids) < 2:
            break
        counts = Counter(zip(ids, ids[1:]))
        best = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        ids = _merge_once(ids, best, 256 + len(merges))
        merges.append(best)
    return merges


def encode(text: str, merges: list[Pair]) -> list[int]:
    ranks = {pair: rank for rank, pair in enumerate(merges)}
    ids = _byte_ids(text)
    while len(ids) >= 2:
        best_rank: int | None = None
        best_pair: Pair | None = None
        for pair in zip(ids, ids[1:]):
            rank = ranks.get(pair)
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank = rank
                best_pair = pair
        if best_pair is None:
            break
        ids = _merge_once(ids, best_pair, 256 + best_rank)
    return ids


def decode(ids: list[int], merges: list[Pair]) -> str:
    vocab: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
    for k, (a, b) in enumerate(merges):
        vocab[256 + k] = vocab[a] + vocab[b]
    try:
        buf = b"".join(vocab[i] for i in ids)
    except KeyError as exc:
        raise ValueError(f"unknown token id: {exc.args[0]}") from None
    return buf.decode("utf-8")
