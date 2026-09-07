"""Lab 25 — hallucination span classification. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. No model calls, no network, no sleeping.
  * Grounding is against the provided context ONLY — a true fact the context
    does not contain is still "unsupported". That is the point of the lab.
"""
from __future__ import annotations

import string

EXTRACTED_MIN = 0.80      # content-word overlap required for "extracted"
INFERRED_MIN = 0.40        # content-word overlap required for "inferred"

STOPWORDS = frozenset("""
a an the and or but if then else when at by for with about against between into
through during before after above below to from up down in out on off over under
again further once here there all any both each few more most other some such no
nor not only own same so than too very can will just should now is are was were
be been being have has had having do does did doing would could ought i you he
she it we they them his her its our your their this that these those am what
which who whom of as until while because since also must may might shall
""".split())


# --------------------------------------------------------------------- helpers
def _tokens(text: str) -> list[str]:
    """Whitespace-split tokens, empties dropped."""
    # TODO(step 0)
    raise NotImplementedError


def _content_words(text: str) -> list[str]:
    """Lowercased tokens with edge punctuation stripped, len >= 3, stopwords
    removed. "1998." -> "1998" (a content word); "50" is too short to be one."""
    # TODO(step 1)
    raise NotImplementedError


def _context_words(context_docs: list[str]) -> set[str]:
    """Every normalised word across all context docs, as a set."""
    # TODO(step 1)
    raise NotImplementedError


def _numbers(text: str) -> list[float]:
    """Every number in the text ("founded in 1998" -> [1998.0])."""
    # TODO(step 2)
    raise NotImplementedError


def _entities(span: str) -> list[str]:
    """Entity candidates, grouped: all-caps tokens (len >= 2), or capitalized
    words NOT at sentence start. Consecutive candidates group into one
    multi-word entity ("Eiffel Tower"). Sentence-start capitals are skipped
    on purpose — that ambiguity is the NER hard case."""
    # TODO(step 3)
    raise NotImplementedError


# --------------------------------------------------------------------- API
def numeric_consistency(span: str, context_docs: list[str]) -> tuple[bool, str]:
    """Every number in the span must appear in the context OR be derivable
    via a SINGLE arithmetic step (+ or -) from two numbers both present.
    Returns (ok, reason); the reason names the offending number on failure."""
    # TODO(step 4)
    raise NotImplementedError


def entity_grounding(span: str, context_docs: list[str]) -> tuple[bool, list[str]]:
    """Every entity candidate must appear (word-boundary match) in the
    context. Returns (ok, missing_entities)."""
    # TODO(step 5)
    raise NotImplementedError


def classify_span(span: str, context_docs: list[str]) -> str:
    """'extracted' | 'inferred' | 'unsupported'.

    extracted  — >= 80% of content words verbatim in context, numbers and
                 entities check out (a copied sentence with a swapped
                 number is NOT extracted)
    inferred   — numbers consistent + entities grounded + overlap >= 40%
    unsupported — otherwise
    """
    # TODO(step 6)
    raise NotImplementedError


def detect(answer: str, context_docs: list[str]) -> dict:
    """Sentence-split the answer, classify each span, and return
    {"spans": [{"span": ..., "class": ...}], "unsupported_fraction": float}."""
    # TODO(step 7)
    raise NotImplementedError
