"""Lab 06 -- a RAG pipeline from scratch: chunking, BM25, dense retrieval, RRF.
Fill in every TODO. Tests define done.

Rules:
  * No network, no API keys, no downloads -- everything is deterministic and seeded.
  * `seeded_embed` is NOT a real embedding model. It hashes each word to a fixed
    pseudo-random unit vector (seeded off the word's own hash) and averages them.
    Same word -> same vector, every run. That's what "semantic-ish" means here.
  * Chunking must never split a word across two chunks.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

# --------------------------------------------------------------------------- tokenization
_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer used by BM25 and (optionally) chunking.

    TODO(step 0): return _WORD_RE.findall on the lowercased text.
    """
    raise NotImplementedError


_STOPWORDS = {
    "the", "a", "an", "is", "in", "on", "with", "from", "to", "and", "it",
    "this", "has", "for", "before", "so", "must", "of", "its", "as", "by",
    "at", "that", "goes", "make", "best", "reach", "degrees",
}


def _content_words(text: str) -> list[str]:
    """Tokens with common stopwords removed -- keeps the hashed bag-of-words
    embedding focused on topic-bearing vocabulary instead of function words
    that appear in every sentence regardless of topic.

    TODO(step 3a): return tokenize(text) filtered against _STOPWORDS.
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- chunking: fixed
def fixed_chunk(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Pack whole words into chunks up to `chunk_size` characters. Never
    splits a word across two chunks -- a single word longer than chunk_size
    becomes its own chunk rather than being cut.

    TODO(step 1):
      - text.split() into words; if empty, return []
      - greedily pack words into a chunk: keep adding the next word (with a
        single joining space) as long as the running length stays
        <= chunk_size; a chunk must contain at least one word even if that
        word alone exceeds chunk_size (never split it)
      - join each chunk's words with " " and append to the result
      - after finishing a chunk, step the start index forward by
        (words consumed - overlap), always making forward progress by at
        least 1 word even when overlap >= words consumed
      - stop when all words are consumed
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- chunking: recursive
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


def recursive_chunk(text: str, max_size: int, separators: list[str] | None = None) -> list[str]:
    """Classic recursive/structure-aware splitter: try the highest-level
    separator first (paragraph breaks), only fall through to finer ones
    (sentences, then words) for pieces that are still too big. Prefers to
    keep whole paragraphs/sentences intact whenever they already fit --
    never splits mid-word because the last-resort separator is a space and
    the true last resort is word-safe `fixed_chunk`.

    TODO(step 2):
      - default separators = DEFAULT_SEPARATORS if none given
      - strip text; if empty return []; if len(text) <= max_size return [text]
      - if no separators left, fall back to fixed_chunk(text, max_size)
      - split text on the first separator; greedily re-merge the resulting
        parts (re-inserting the separator between them) into chunks that
        stay <= max_size
      - if a single part is itself too big to fit, recurse into it with the
        REMAINING separators (rest_seps), and splice the results in
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- chunking: semantic-ish
def split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation followed by whitespace.

    TODO(step 3b): strip text; if empty return []. Use
    re.split(r"(?<=[.!?]) +", text) and strip/filter empty pieces.
    """
    raise NotImplementedError


def _word_vector(word: str, dim: int) -> np.ndarray:
    """A fixed pseudo-random unit vector for one word, seeded off a stable
    hash of the word itself (not off any shared/global RNG state) -- so the
    same word always maps to the same vector, in this process or any other.

    TODO(step 3c):
      - digest = hashlib.md5(word.encode("utf-8")).hexdigest()
      - seed = int(digest, 16) % (2**32)
      - rng = np.random.default_rng(seed); v = rng.normal(size=dim)
      - return the unit vector v / ||v||
    """
    raise NotImplementedError


def seeded_embed(text: str, dim: int = 16) -> np.ndarray:
    """Deterministic bag-of-words embedding: average the per-word hashed unit
    vectors of the content words, then renormalize. No model, no network.

    TODO(step 3d):
      - words = _content_words(text); if empty return np.zeros(dim)
      - stack _word_vector(w, dim) for each word, take the mean
      - renormalize the mean to unit length (guard against a zero vector)
    """
    raise NotImplementedError


def semantic_chunk(text: str, threshold: float = 0.3, max_sentences: int = 5,
                    dim: int = 16) -> list[str]:
    """Group consecutive sentences into a chunk while each new sentence stays
    "on topic" -- cosine similarity to the running chunk centroid at or above
    `threshold`. Starts a new chunk when similarity drops below threshold or
    the chunk hits `max_sentences`. Whole sentences in, whole sentences out:
    never splits mid-word.

    TODO(step 3e):
      - sentences = split_sentences(text); if empty return []
      - start `current` with the first sentence and its embedding
      - for each following sentence: embed it, compare to the mean of
        current's embeddings via cosine_similarity; if sim >= threshold AND
        len(current) < max_sentences, append to current; otherwise flush
        current (join with " ") as a finished chunk and start a new current
      - flush the final current chunk at the end
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- BM25
class BM25:
    """Okapi BM25 from scratch. score = sum over query terms of
    idf(term) * (f(term,doc) * (k1+1)) / (f(term,doc) + k1*(1 - b + b*dl/avgdl))
    with idf(term) = ln((N - n(term) + 0.5)/(n(term) + 0.5) + 1).

    TODO(step 4a): in __init__, store corpus_tokens/k1/b, compute n_docs,
      doc_lens (len of each doc's token list), avgdl (mean of doc_lens), and
      df: for each doc, for each UNIQUE term in it, increment df[term] by 1
      (document frequency, not raw term count).
    """

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        raise NotImplementedError

    def idf(self, term: str) -> float:
        """TODO(step 4b): n = self.df.get(term, 0);
        return ln((N - n + 0.5)/(n + 0.5) + 1)."""
        raise NotImplementedError

    def score(self, query_tokens: list[str], doc_index: int) -> float:
        """TODO(step 4c): sum the BM25 contribution of each query term that
        appears in the doc (f=0 terms contribute 0, skip them) using the
        formula in the class docstring. dl = self.doc_lens[doc_index].
        """
        raise NotImplementedError

    def search(self, query_tokens: list[str], top_k: int | None = None) -> list[tuple[int, float]]:
        """TODO(step 4d): score every doc, sort by (-score, doc_id) so ties
        break by ascending doc id, truncate to top_k if given.
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- dense retrieval
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """TODO(step 5a): return dot(a,b) / (||a|| * ||b||); return 0.0 if
    either vector has zero norm (avoid division by zero)."""
    raise NotImplementedError


class DenseRetriever:
    """Cosine-similarity search over a fixed set of (pre-computed) doc vectors."""

    def __init__(self, doc_vectors: dict[int, np.ndarray]) -> None:
        self.doc_vectors = doc_vectors

    def search(self, query_vector: np.ndarray, top_k: int | None = None) -> list[tuple[int, float]]:
        """TODO(step 5b): compute cosine_similarity(query_vector, vec) for
        every (doc_id, vec) pair, sort by (-score, doc_id), truncate to
        top_k if given.
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- fusion
def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Combine multiple ranked doc-id lists (best first) into one fused
    ranking. score(doc) = sum over each list the doc appears in of
    1 / (k + rank), rank starting at 1. Docs absent from a list simply don't
    receive that list's term. Ties broken by doc id ascending.

    TODO(step 6): for each ranking, for each (rank, doc_id) starting rank at
    1, accumulate scores[doc_id] += 1/(k+rank). Then sort the (doc_id, score)
    pairs by (-score, doc_id) and return as a list of tuples.
    """
    raise NotImplementedError
