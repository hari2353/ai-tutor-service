"""Lab 06 -- a RAG pipeline from scratch: chunking, BM25, dense retrieval, RRF.

Everything here is deterministic and offline. There is no real embedding model:
`seeded_embed` builds a reproducible bag-of-words vector by hashing each word to
a fixed pseudo-random unit vector (seeded off the word's own hash, not off any
global RNG state) and averaging. Same word, same vector, every run, every
machine -- no network, no API key, no download. Two sentences that share
vocabulary land close together in cosine space; two that don't, don't. That is
"semantic-ish": good enough to demonstrate topic-boundary chunking and to give
dense retrieval something real to rank against BM25, without pretending it's a
trained embedding model.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

# --------------------------------------------------------------------------- tokenization
_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer used by BM25 and (optionally) chunking."""
    return _WORD_RE.findall(text.lower())


_STOPWORDS = {
    "the", "a", "an", "is", "in", "on", "with", "from", "to", "and", "it",
    "this", "has", "for", "before", "so", "must", "of", "its", "as", "by",
    "at", "that", "goes", "make", "best", "reach", "degrees",
}


def _content_words(text: str) -> list[str]:
    """Tokens with common stopwords removed -- keeps the hashed bag-of-words
    embedding focused on topic-bearing vocabulary instead of function words
    that appear in every sentence regardless of topic."""
    return [w for w in tokenize(text) if w not in _STOPWORDS]


# --------------------------------------------------------------------------- chunking: fixed
def fixed_chunk(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Pack whole words into chunks up to `chunk_size` characters. Never
    splits a word across two chunks -- a single word longer than chunk_size
    becomes its own chunk rather than being cut."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    n = len(words)
    start = 0
    while start < n:
        cur_words: list[str] = []
        cur_len = 0
        i = start
        while i < n:
            w = words[i]
            add_len = len(w) if not cur_words else cur_len + 1 + len(w)
            if cur_words and add_len > chunk_size:
                break
            cur_words.append(w)
            cur_len = add_len
            i += 1
        chunks.append(" ".join(cur_words))
        if i >= n:
            break
        # step forward, re-including the last `overlap` words of this chunk;
        # always make progress even if overlap >= len(cur_words)
        start = max(i - overlap, start + 1)
    return chunks


# --------------------------------------------------------------------------- chunking: recursive
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


def recursive_chunk(text: str, max_size: int, separators: list[str] | None = None) -> list[str]:
    """Classic recursive/structure-aware splitter: try the highest-level
    separator first (paragraph breaks), only fall through to finer ones
    (sentences, then words) for pieces that are still too big. Prefers to
    keep whole paragraphs/sentences intact whenever they already fit --
    never splits mid-word because the last-resort separator is a space and
    the true last resort is word-safe `fixed_chunk`."""
    if separators is None:
        separators = DEFAULT_SEPARATORS
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_size:
        return [text]
    if not separators:
        return fixed_chunk(text, max_size)

    sep, rest_seps = separators[0], separators[1:]
    parts = text.split(sep)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + sep + part) if current else part
        if len(candidate) <= max_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(part) <= max_size:
            current = part
        else:
            sub_chunks = recursive_chunk(part, max_size, rest_seps)
            if sub_chunks:
                chunks.extend(sub_chunks[:-1])
                current = sub_chunks[-1]
            else:
                current = ""
    if current:
        chunks.append(current)
    return chunks


# --------------------------------------------------------------------------- chunking: semantic-ish
def split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation followed by whitespace."""
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?]) +", text)
    return [p.strip() for p in parts if p.strip()]


def _word_vector(word: str, dim: int) -> np.ndarray:
    """A fixed pseudo-random unit vector for one word, seeded off a stable
    hash of the word itself (not off any shared/global RNG state) -- so the
    same word always maps to the same vector, in this process or any other."""
    digest = hashlib.md5(word.encode("utf-8")).hexdigest()
    seed = int(digest, 16) % (2**32)
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim)
    return v / np.linalg.norm(v)


def seeded_embed(text: str, dim: int = 16) -> np.ndarray:
    """Deterministic bag-of-words embedding: average the per-word hashed unit
    vectors of the content words, then renormalize. No model, no network."""
    words = _content_words(text)
    if not words:
        return np.zeros(dim)
    vecs = np.array([_word_vector(w, dim) for w in words])
    v = vecs.mean(axis=0)
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def semantic_chunk(text: str, threshold: float = 0.3, max_sentences: int = 5,
                    dim: int = 16) -> list[str]:
    """Group consecutive sentences into a chunk while each new sentence stays
    "on topic" -- cosine similarity to the running chunk centroid at or above
    `threshold`. Starts a new chunk when similarity drops below threshold or
    the chunk hits `max_sentences`. Whole sentences in, whole sentences out:
    never splits mid-word."""
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current = [sentences[0]]
    current_vecs = [seeded_embed(sentences[0], dim)]

    for sent in sentences[1:]:
        vec = seeded_embed(sent, dim)
        centroid = np.mean(current_vecs, axis=0)
        sim = cosine_similarity(centroid, vec)
        if sim >= threshold and len(current) < max_sentences:
            current.append(sent)
            current_vecs.append(vec)
        else:
            chunks.append(" ".join(current))
            current = [sent]
            current_vecs = [vec]

    chunks.append(" ".join(current))
    return chunks


# --------------------------------------------------------------------------- BM25
class BM25:
    """Okapi BM25 from scratch. score = sum over query terms of
    idf(term) * (f(term,doc) * (k1+1)) / (f(term,doc) + k1*(1 - b + b*dl/avgdl))
    with idf(term) = ln((N - n(term) + 0.5)/(n(term) + 0.5) + 1).
    """

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus_tokens = corpus_tokens
        self.k1 = k1
        self.b = b
        self.n_docs = len(corpus_tokens)
        self.doc_lens = [len(toks) for toks in corpus_tokens]
        self.avgdl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0

        self.df: dict[str, int] = {}
        for toks in corpus_tokens:
            for term in set(toks):
                self.df[term] = self.df.get(term, 0) + 1

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log((self.n_docs - n + 0.5) / (n + 0.5) + 1)

    def score(self, query_tokens: list[str], doc_index: int) -> float:
        toks = self.corpus_tokens[doc_index]
        dl = self.doc_lens[doc_index]
        total = 0.0
        for term in query_tokens:
            f = toks.count(term)
            if f == 0:
                continue
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            total += self.idf(term) * (numerator / denominator)
        return total

    def search(self, query_tokens: list[str], top_k: int | None = None) -> list[tuple[int, float]]:
        scores = [(i, self.score(query_tokens, i)) for i in range(self.n_docs)]
        scores.sort(key=lambda pair: (-pair[1], pair[0]))
        return scores[:top_k] if top_k is not None else scores


# --------------------------------------------------------------------------- dense retrieval
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class DenseRetriever:
    """Cosine-similarity search over a fixed set of (pre-computed) doc vectors."""

    def __init__(self, doc_vectors: dict[int, np.ndarray]) -> None:
        self.doc_vectors = doc_vectors

    def search(self, query_vector: np.ndarray, top_k: int | None = None) -> list[tuple[int, float]]:
        scores = [(doc_id, cosine_similarity(query_vector, vec))
                   for doc_id, vec in self.doc_vectors.items()]
        scores.sort(key=lambda pair: (-pair[1], pair[0]))
        return scores[:top_k] if top_k is not None else scores


# --------------------------------------------------------------------------- fusion
def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Combine multiple ranked doc-id lists (best first) into one fused
    ranking. score(doc) = sum over each list the doc appears in of
    1 / (k + rank), rank starting at 1. Docs absent from a list simply don't
    receive that list's term. Ties broken by doc id ascending."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    return fused
