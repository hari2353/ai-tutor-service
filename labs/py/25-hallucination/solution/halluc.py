"""Lab 25 — reference solution."""
from __future__ import annotations

import itertools
import re
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

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_SENT_RE = re.compile(r"[.!?\n]+")


# --------------------------------------------------------------------- helpers
def _tokens(text: str) -> list[str]:
    return [t for t in text.split() if t]


def _normalise(tok: str) -> str:
    return tok.strip(string.punctuation).lower()


def _content_words(text: str) -> list[str]:
    """Lowercase tokens, edge punctuation stripped, len >= 3, stopwords gone.
    "1998." -> "1998" (a content word); "50" is too short to be one."""
    return [w for w in (_normalise(t) for t in _tokens(text))
            if len(w) >= 3 and w not in STOPWORDS]


def _context_words(context_docs: list[str]) -> set[str]:
    return {_normalise(t) for doc in context_docs for t in _tokens(doc)}


def _numbers(text: str) -> list[float]:
    return [float(m) for m in _NUM_RE.findall(text)]


def _fmt(n: float) -> str:
    return str(int(n)) if n.is_integer() else str(n)


def _entity_parts(raw: str, idx: int) -> list[str]:
    """Entity candidates inside one token. All-caps counts anywhere ("RAG");
    Titlecase only mid-sentence (sentence-start capitals are ambiguous, and
    we deliberately miss rather than flag every sentence). Hyphen parts are
    checked separately ("Lisbon-based" -> "Lisbon")."""
    out = []
    for part in (p for p in re.split(r"[-/]", raw.strip(string.punctuation)) if p):
        if len(part) < 2 or not any(c.isalpha() for c in part):
            continue
        if part.isupper():
            out.append(part)
        elif idx > 0 and part[0].isupper() and part.lower() not in STOPWORDS:
            out.append(part)
    return out


def _entities(span: str) -> list[str]:
    entities = []
    for sentence in (s for s in _SENT_RE.split(span) if s.strip()):
        tokens = _tokens(sentence)
        flags = [" ".join(_entity_parts(tok, i)) or None
                 for i, tok in enumerate(tokens)]
        i = 0
        while i < len(flags):
            if flags[i] is None:
                i += 1
                continue
            group = [flags[i]]
            j = i + 1
            while j < len(flags) and flags[j] is not None:
                group.append(flags[j])
                j += 1
            entities.append(" ".join(group))
            i = j
    return entities


# --------------------------------------------------------------------- API
def numeric_consistency(span: str, context_docs: list[str]) -> tuple[bool, str]:
    """Every number in the span must appear in the context OR be derivable
    via a SINGLE arithmetic step (+ or -) from two numbers both present.
    Two-step chains must fail: 1971 = 1998 - 27 does not count when 27
    itself is only derivable, not present."""
    ctx_nums = _numbers(" ".join(context_docs))
    present = set(ctx_nums)
    for n in _numbers(span):
        if n in present:
            continue
        if not any(a + b == n or a - b == n or b - a == n
                   for a, b in itertools.combinations(ctx_nums, 2)):
            return False, (f"number {_fmt(n)} appears neither in the context nor as "
                          f"a single +/- step from two context numbers")
    return True, "every number is present or single-step derivable"


def entity_grounding(span: str, context_docs: list[str]) -> tuple[bool, list[str]]:
    """Every entity candidate must appear (word-boundary match) in the context."""
    blob = " ".join(context_docs)
    missing = [e for e in _entities(span)
               if not re.search(rf"\b{re.escape(e)}\b", blob)]
    return (not missing), missing


def classify_span(span: str, context_docs: list[str]) -> str:
    ctx = _context_words(context_docs)
    words = _content_words(span)
    overlap = (sum(1 for w in words if w in ctx) / len(words)) if words else 1.0
    num_ok, _ = numeric_consistency(span, context_docs)
    ent_ok, _ = entity_grounding(span, context_docs)
    # Numbers and entities gate BOTH classes: a copied sentence with one
    # swapped number is 80%+ overlap and still a hallucination.
    if num_ok and ent_ok:
        if overlap >= EXTRACTED_MIN:
            return "extracted"
        if overlap >= INFERRED_MIN:
            return "inferred"
    return "unsupported"


def detect(answer: str, context_docs: list[str]) -> dict:
    spans = []
    for segment in _SENT_RE.split(answer):
        text = segment.strip()
        if text:
            spans.append({"span": text, "class": classify_span(text, context_docs)})
    unsupported = sum(1 for s in spans if s["class"] == "unsupported")
    return {"spans": spans, "unsupported_fraction": unsupported / len(spans) if spans else 0.0}
