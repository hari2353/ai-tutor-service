"""Lab 04 — hybrid search from scratch. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib, deterministic. Same inputs → same ranking, every call.
  * The corpus shape is dict[str, str] (doc id → text). Never mutate the caller's dict.
  * Fusion happens on RANKS, never on raw scores.
"""
from __future__ import annotations

import math
import re
from collections import Counter


Term = str
Vector = Counter  # term/3-gram → count


def _tokens(text: str) -> list[Term]:
    """Lowercase word tokens: runs of \\w+ (unicode-aware)."""
    # TODO(step 0)
    raise NotImplementedError


def _char_ngrams(text: str, n: int = 3) -> Vector:
    """Overlapping lowercase character n-grams → TF counter."""
    # TODO(step 1)
    raise NotImplementedError


def _cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity of two TF counters; 0.0 if either vector is empty."""
    # TODO(step 2)
    raise NotImplementedError


# --------------------------------------------------------------------------- bm25
class BM25:
    """Okapi BM25 over a static corpus.

    score(q, d) = Σ_terms idf(t) · tf·(k1+1) / (tf + k1·(1 − b + b·|d|/avgdl))
    idf(t)      = ln((N − df + 0.5)/(df + 0.5) + 1)
    """

    def __init__(self, corpus_docs: dict[str, str], k1: float = 1.5,
                 b: float = 0.75) -> None:
        # TODO(step 3): index tf per doc, doc lengths, avgdl, document
        # frequencies. Do not alias the caller's dict.
        raise NotImplementedError

    def _idf(self, term: Term) -> float:
        # TODO(step 4)
        raise NotImplementedError

    def score(self, query: str, doc_id: str) -> float:
        # TODO(step 5): sum the formula above over unique query terms.
        raise NotImplementedError

    def rank(self, query: str) -> list[str]:
        """All doc ids by score desc; ties broken by doc id asc."""
        # TODO(step 6)
        raise NotImplementedError


# --------------------------------------------------------------------------- dense leg
class DenseScorer:
    """Pseudo-embeddings: char 3-gram TF vectors scored with cosine."""

    def __init__(self, docs: dict[str, str]) -> None:
        # TODO(step 7)
        raise NotImplementedError

    def score(self, query: str, doc_id: str) -> float:
        # TODO(step 8)
        raise NotImplementedError

    def rank(self, query: str) -> list[str]:
        # TODO(step 9)
        raise NotImplementedError


# --------------------------------------------------------------------------- fusion
def bm25(corpus_docs: dict[str, str], k1: float = 1.5, b: float = 0.75) -> BM25:
    """Factory: build a BM25 scorer over the corpus."""
    # TODO(step 3a)
    raise NotImplementedError


def dense_scorer(docs: dict[str, str]) -> DenseScorer:
    """Factory: build the char-3-gram cosine scorer."""
    # TODO(step 7a)
    raise NotImplementedError


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal-rank fusion.

    score(d) = Σ over rankings of 1 / (k + position), positions starting at 1.
    Docs absent from a ranking simply get no contribution from it.
    """
    # TODO(step 10)
    raise NotImplementedError


# --------------------------------------------------------------------------- hybrid
def hybrid_search(query: str, docs: dict[str, str], top_n: int = 10,
                  k: int = 60) -> list[tuple[str, float]]:
    """Both legs → rrf over their rankings → top_n as (doc_id, fused_score).

    Order: fused desc, tie-break higher bm25, then doc id asc.
    Empty/whitespace query or empty docs → [].
    """
    # TODO(step 11)
    raise NotImplementedError
