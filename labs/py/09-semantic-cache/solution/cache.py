"""Lab 09 -- a three-layer semantic cache: exact, prefix, semantic.

No network, no real embedding model: query vectors are given (fixed, seeded
fixtures in the tests), exactly like a production cache is handed a vector by
whatever embedding service already ran. This lab is about the cache logic and
the threshold tradeoff, not about producing embeddings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np


# --------------------------------------------------------------------------- normalization
def normalize_query(text: str) -> str:
    """Lowercase, strip, and collapse internal whitespace so trivial
    formatting differences don't defeat the exact-match layer."""
    return re.sub(r"\s+", " ", text.strip().lower())


# --------------------------------------------------------------------------- layer 1: exact
class ExactCache:
    """Byte-identical (post-normalization) match. Catches idempotent retries
    and repeated identical requests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, query: str) -> Optional[str]:
        return self._store.get(normalize_query(query))

    def put(self, query: str, response: str) -> None:
        self._store[normalize_query(query)] = response


# --------------------------------------------------------------------------- layer 2: prefix
class PrefixCache:
    """Serves a response cached under a shared prefix (e.g. a fixed
    instruction template) when the incoming query starts with that exact
    prefix. Only matches prefixes at least `min_prefix_len` characters long,
    so trivial one-character overlaps can't produce a false hit. When
    multiple stored prefixes match, the LONGEST one wins -- it's the most
    specific, and therefore the safest, match.
    """

    def __init__(self, min_prefix_len: int = 10) -> None:
        self.min_prefix_len = min_prefix_len
        self._entries: list[tuple[str, str]] = []  # (prefix, response)

    def get(self, query: str) -> Optional[str]:
        q = normalize_query(query)
        best_prefix = None
        best_response = None
        for prefix, response in self._entries:
            if len(prefix) < self.min_prefix_len:
                continue
            if q.startswith(prefix):
                if best_prefix is None or len(prefix) > len(best_prefix):
                    best_prefix, best_response = prefix, response
        return best_response

    def put(self, prefix: str, response: str) -> None:
        self._entries.append((normalize_query(prefix), response))


# --------------------------------------------------------------------------- layer 3: semantic
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


@dataclass
class SemanticEntry:
    vector: np.ndarray
    response: str
    entry_id: int


class SemanticCache:
    """Nearest-neighbor cosine-similarity match against previously cached
    query vectors. Serves the response of the closest cached entry IF its
    similarity clears `threshold` -- the single most consequential knob in
    the whole cache: too low and it serves confidently wrong answers for
    topically-adjacent-but-different queries, too high and hit rate
    collapses toward zero."""

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self._entries: list[SemanticEntry] = []
        self._next_id = 0

    def put(self, vector: np.ndarray, response: str) -> int:
        entry_id = self._next_id
        self._entries.append(SemanticEntry(vector=vector, response=response, entry_id=entry_id))
        self._next_id += 1
        return entry_id

    def best_match(self, query_vector: np.ndarray) -> Optional[tuple[SemanticEntry, float]]:
        """Nearest neighbor regardless of threshold -- used internally and
        exposed for tests/analysis that need the raw similarity."""
        if not self._entries:
            return None
        scored = [(entry, cosine_similarity(query_vector, entry.vector)) for entry in self._entries]
        scored.sort(key=lambda pair: -pair[1])
        return scored[0]

    def get(self, query_vector: np.ndarray) -> Optional[tuple[str, float]]:
        match = self.best_match(query_vector)
        if match is None:
            return None
        entry, similarity = match
        if similarity >= self.threshold:
            return entry.response, similarity
        return None


# --------------------------------------------------------------------------- layered cache
@dataclass
class CacheResult:
    hit: bool
    layer: str                      # "exact" | "prefix" | "semantic" | "miss"
    response: Optional[str]
    similarity: Optional[float] = None


class LayeredCache:
    """Checks exact -> prefix -> semantic, in that order (cheapest and
    highest-confidence first). Returns the first hit; a miss means none of
    the three layers had anything to offer."""

    def __init__(self, semantic_threshold: float = 0.85) -> None:
        self.exact = ExactCache()
        self.prefix = PrefixCache()
        self.semantic = SemanticCache(threshold=semantic_threshold)

    def get(self, query: str, query_vector: Optional[np.ndarray] = None) -> CacheResult:
        exact_hit = self.exact.get(query)
        if exact_hit is not None:
            return CacheResult(hit=True, layer="exact", response=exact_hit)

        prefix_hit = self.prefix.get(query)
        if prefix_hit is not None:
            return CacheResult(hit=True, layer="prefix", response=prefix_hit)

        if query_vector is not None:
            semantic_hit = self.semantic.get(query_vector)
            if semantic_hit is not None:
                response, similarity = semantic_hit
                return CacheResult(hit=True, layer="semantic", response=response, similarity=similarity)

        return CacheResult(hit=False, layer="miss", response=None)

    def put(self, query: str, response: str, query_vector: Optional[np.ndarray] = None) -> None:
        self.exact.put(query, response)
        if query_vector is not None:
            self.semantic.put(query_vector, response)
