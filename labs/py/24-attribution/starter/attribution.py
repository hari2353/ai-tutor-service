"""Lab 24 — attribution: citations that hold up. Fill in every TODO. Tests define done.

A citation that RESOLVES and a citation that SUPPORTS the claim are two
different products. You are building the lexical ancestor of an NLI
faithfulness gate (RAGAS faithfulness, ALCE citation recall/precision):
split an answer into claims, classify each against the sources it actually
cites, score the answer, and normalize the citations.

Rules:
  * Pure stdlib. No model calls, no sleeps, no network.
  * The constants below are GIVEN — the tests are calibrated to them exactly.
    Do not change them.
"""
from __future__ import annotations

import re

# --------------------------------------------------------------- given constants
STOPWORDS = frozenset({
    "the", "and", "for", "are", "was", "were", "with", "from", "that", "this",
    "these", "those", "has", "have", "had", "not", "but", "all", "can",
    "could", "you", "your", "its", "their", "which", "will", "would", "there",
    "what", "when", "where", "who", "how", "than", "then", "them", "they",
    "been", "being", "into", "also", "may", "might", "shall", "should",
    "must", "does", "did", "doing", "having", "about", "against", "between",
    "through", "during", "before", "after", "above", "below", "further",
    "once", "here", "why", "again", "over", "under",
})

SUPPORTED = "SUPPORTED"
PLAUSIBLE_UNSUPPORTED = "PLAUSIBLE_UNSUPPORTED"
FABRICATED = "FABRICATED"

_WORD = re.compile(r"[a-z]+")            # content words: pure alpha runs
_NUM = re.compile(r"\d+(?:\.\d+)?")      # numbers: digit runs, decimals kept

_OVERLAP_FULL = 0.60                     # >=  -> SUPPORTED candidate
_OVERLAP_PARTIAL = 0.20                  # >=  -> PLAUSIBLE_UNSUPPORTED


# --------------------------------------------------------------------- step 1
def _canonical_id(raw: str) -> str:
    """' Doc1#sec2' -> 'doc1': strip whitespace, lowercase, cut at first '#'.

    Near-identical ids ('doc1', 'doc1 ', 'Doc1#sec2') all canonicalize to one
    id. This is the ONLY notion of id equality in the module.
    """
    raise NotImplementedError


def content_words(text: str) -> set[str]:
    """Lowercase alpha words of length >= 3, minus STOPWORDS. Returns a set.

    Digit runs are NOT content words — numbers get their own gate, because
    lexical overlap is blind to '30 days' vs '90 days'.
    """
    raise NotImplementedError


def numbers(text: str) -> set[str]:
    """Digit runs found in the text: '30', '2015', '4.5'.

    Spelled-out numbers ('four') are out of scope — they are content words.
    """
    raise NotImplementedError


# --------------------------------------------------------------------- step 2
class CitedAnswer:
    """An answer split into claims, each bound to the source ids it cites.

    claims: list of dicts {"text": str, "source_ids": list[str]}
    sources: {source_id: source_text}

    Validates AT CONSTRUCTION and raises ValueError when a claim has empty
    source_ids, or when NO cited id resolves (after canonicalisation) to a
    key of sources. This is the structural ancestor of citation-constrained
    decoding: a fabricated id never enters the answer object.
    """

    def __init__(self, claims: list[dict], sources: dict[str, str]) -> None:
        # TODO(step 2): validate + copy the claims, keep the sources.
        #   self.claims  -> list of {"text": str, "source_ids": list[str]}
        #   self.sources -> the sources dict
        raise NotImplementedError


# --------------------------------------------------------------------- step 3
def verify(answer: CitedAnswer, sources: dict[str, str]) -> dict:
    """Classify every claim against the union of the sources it cites.

    Per claim:
      overlap = |content_words(claim) & content_words(union of cited sources)|
                / |content_words(claim)|                      (0.0 if no words)

      SUPPORTED              overlap >= 0.60, and every number in the claim
                             appears in the union of cited sources
      PLAUSIBLE_UNSUPPORTED  0.20 <= overlap < 0.60 — on topic, never stated:
                             the dominant real-world citation failure
      FABRICATED             overlap < 0.20 — or a SUPPORTED candidate whose
                             numbers are absent (reason "numeric mismatch")

    Report shape:
      {"claims": [{"text", "source_ids", "status", "overlap", "reasons"}, ...],
       "total", "supported", "plausible_unsupported", "fabricated",
       "faithfulness"}
    """
    raise NotImplementedError


# --------------------------------------------------------------------- step 4
def faithfulness_score(report: dict) -> float:
    """Fraction of claims classified SUPPORTED — RAGAS faithfulness, lexical
    edition. Empty report -> 1.0 (nothing unsupported)."""
    raise NotImplementedError


# --------------------------------------------------------------------- step 5
def normalize_citations(answer: CitedAnswer) -> CitedAnswer:
    """Dedupe near-identical ids and order citations canonically (sorted).

    Returns a NEW CitedAnswer validated against the same sources, so
    normalization can never smuggle in an unknown id.
    """
    raise NotImplementedError
