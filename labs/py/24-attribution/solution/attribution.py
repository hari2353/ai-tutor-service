"""Lab 24 — attribution: citations that hold up. Reference solution.

The lexical ancestor of an NLI faithfulness gate (RAGAS faithfulness,
ALCE citation recall/precision): claims are checked against the union of
the sources they actually cite, numbers get their own deterministic gate,
and the answer gets a single faithfulness score.

The one design decision that matters here: classification is computed
against the sources the CLAIM CITES, never against the full corpus. A
correct fact cited to the wrong document is a citation failure even when
some other document supports it — that is the whole module in one sentence.
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
    """' Doc1#sec2' -> 'doc1': strip whitespace, lowercase, cut at first '#'."""
    return raw.strip().lower().split("#", 1)[0]


def content_words(text: str) -> set[str]:
    """Lowercase alpha words of length >= 3, minus STOPWORDS. Returns a set.

    Digit runs are NOT content words — numbers get their own gate, because
    lexical overlap is blind to '30 days' vs '90 days'.
    """
    words = _WORD.findall(text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def numbers(text: str) -> set[str]:
    """Digit runs found in the text: '30', '2015', '4.5'.

    Spelled-out numbers ('four') are out of scope — they are content words.
    """
    return set(_NUM.findall(text))


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
        self.sources = sources
        self.claims: list[dict] = []
        for i, claim in enumerate(claims):
            text = claim["text"]
            cited = list(claim.get("source_ids", []))
            if not text or not isinstance(text, str):
                raise ValueError(f"claim {i}: text must be a non-empty string")
            if not cited:
                raise ValueError(f"claim {i} cites no sources: {text!r}")
            resolved = [c for c in cited if _canonical_id(c) in sources]
            if not resolved:
                raise ValueError(
                    f"claim {i} cites no known source (got {cited}, "
                    f"known: {sorted(sources)})"
                )
            self.claims.append({"text": text, "source_ids": cited})


# --------------------------------------------------------------------- step 3
def verify(answer: CitedAnswer, sources: dict[str, str]) -> dict:
    """Classify every claim against the union of the sources it cites.

    SUPPORTED: >= 60% content-word overlap AND all numbers present.
    PLAUSIBLE_UNSUPPORTED: 20-60% overlap — on topic, never stated.
    FABRICATED: < 20% overlap, or a numbers gate failure ("numeric mismatch").
    """
    claims_out = []
    supported = plausible = fabricated = 0

    for claim in answer.claims:
        text = claim["text"]
        cited_ids = {_canonical_id(c) for c in claim["source_ids"]}

        # The union of the texts of the sources THIS claim cites.
        union_text = " ".join(
            sources[cid] for cid in cited_ids if cid in sources
        )
        claim_words = content_words(text)
        source_words = content_words(union_text)

        if claim_words:
            overlap = len(claim_words & source_words) / len(claim_words)
        else:
            overlap = 0.0

        reasons: list[str] = []
        if overlap >= _OVERLAP_FULL:
            missing = numbers(text) - numbers(union_text)
            if missing:
                status = FABRICATED
                reasons.append("numeric mismatch: " + ", ".join(sorted(missing)))
            else:
                status = SUPPORTED
        elif overlap >= _OVERLAP_PARTIAL:
            status = PLAUSIBLE_UNSUPPORTED
            reasons.append(f"partial overlap {overlap:.2f} < {_OVERLAP_FULL}")
        else:
            status = FABRICATED
            reasons.append(f"overlap {overlap:.2f} < {_OVERLAP_PARTIAL}")

        supported += status == SUPPORTED
        plausible += status == PLAUSIBLE_UNSUPPORTED
        fabricated += status == FABRICATED

        claims_out.append({
            "text": text,
            "source_ids": list(claim["source_ids"]),
            "status": status,
            "overlap": round(overlap, 4),
            "reasons": reasons,
        })

    total = len(claims_out)
    return {
        "claims": claims_out,
        "total": total,
        "supported": supported,
        "plausible_unsupported": plausible,
        "fabricated": fabricated,
        "faithfulness": supported / total if total else 1.0,
    }


# --------------------------------------------------------------------- step 4
def faithfulness_score(report: dict) -> float:
    """Fraction of claims classified SUPPORTED — RAGAS faithfulness, lexical
    edition. Empty report -> 1.0 (nothing unsupported)."""
    total = report.get("total", 0)
    if not total:
        return 1.0
    return report.get("supported", 0) / total


# --------------------------------------------------------------------- step 5
def normalize_citations(answer: CitedAnswer) -> CitedAnswer:
    """Dedupe near-identical ids and order citations canonically (sorted).

    Returns a NEW CitedAnswer validated against the same sources, so
    normalization can never smuggle in an unknown id.
    """
    normalized_claims = []
    for claim in answer.claims:
        seen: dict[str, str] = {}
        for raw in claim["source_ids"]:
            key = _canonical_id(raw)
            seen.setdefault(key, key)   # canonical form wins; order irrelevant
        normalized_claims.append({
            "text": claim["text"],
            "source_ids": sorted(seen),
        })
    return CitedAnswer(normalized_claims, answer.sources)
