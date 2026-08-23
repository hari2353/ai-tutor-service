"""Lab 04 — reference solution."""
from __future__ import annotations

import math
import re
from collections import Counter


Term = str
Vector = Counter


def _tokens(text: str) -> list[Term]:
    return re.findall(r"\w+", text.lower())


def _char_ngrams(text: str, n: int = 3) -> Vector:
    t = text.lower()
    return Counter(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


def _cosine(a: Vector, b: Vector) -> float:
    if not a or not b:
        return 0.0
    dot = sum(c * b.get(t, 0) for t, c in a.items())
    na = math.sqrt(sum(c * c for c in a.values()))
    nb = math.sqrt(sum(c * c for c in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class BM25:
    def __init__(self, corpus_docs: dict[str, str], k1: float = 1.5,
                 b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs = dict(corpus_docs)
        self._doc_ids = sorted(self.docs)
        self._tf: dict[str, Counter] = {
            d: Counter(_tokens(text)) for d, text in self.docs.items()
        }
        self._dl = {d: sum(tf.values()) for d, tf in self._tf.items()}
        self.N = len(self.docs)
        self.avgdl = (sum(self._dl.values()) / self.N) if self.N else 0.0
        self._df: Counter = Counter()
        for tf in self._tf.values():
            for term in tf:
                self._df[term] += 1

    def _idf(self, term: Term) -> float:
        df = self._df.get(term, 0)
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str, doc_id: str) -> float:
        tf = self._tf[doc_id]
        dl = self._dl[doc_id]
        norm = self.k1 * (1.0 - self.b + self.b * dl / self.avgdl)
        total = 0.0
        for term in set(_tokens(query)):
            f = tf.get(term, 0)
            if f == 0:
                continue
            total += self._idf(term) * f * (self.k1 + 1.0) / (f + norm)
        return total

    def rank(self, query: str) -> list[str]:
        scored = {d: self.score(query, d) for d in self._doc_ids}
        return sorted(self._doc_ids, key=lambda d: (-scored[d], d))


class DenseScorer:
    def __init__(self, docs: dict[str, str]) -> None:
        self.docs = dict(docs)
        self._doc_ids = sorted(self.docs)
        self._vec = {d: _char_ngrams(t) for d, t in self.docs.items()}

    def score(self, query: str, doc_id: str) -> float:
        return _cosine(_char_ngrams(query), self._vec[doc_id])

    def rank(self, query: str) -> list[str]:
        scored = {d: self.score(query, d) for d in self._doc_ids}
        return sorted(self._doc_ids, key=lambda d: (-scored[d], d))


def bm25(corpus_docs: dict[str, str], k1: float = 1.5, b: float = 0.75) -> BM25:
    return BM25(corpus_docs, k1=k1, b=b)


def dense_scorer(docs: dict[str, str]) -> DenseScorer:
    return DenseScorer(docs)


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for pos, doc_id in enumerate(ranking):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + pos + 1)
    return fused


def hybrid_search(query: str, docs: dict[str, str], top_n: int = 10,
                  k: int = 60) -> list[tuple[str, float]]:
    if not query or not query.strip() or not docs:
        return []
    lex = BM25(docs)
    den = DenseScorer(docs)
    fused = rrf([lex.rank(query), den.rank(query)], k=k)
    ordered = sorted(fused,
                     key=lambda d: (-fused[d], -lex.score(query, d), d))
    n = max(0, top_n)
    return [(d, fused[d]) for d in ordered[:n]]
