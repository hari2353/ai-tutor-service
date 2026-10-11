"""Reference implementation for the resume evidence matching lab."""
from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Requirement:
    canonical: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchResult:
    requirement: str
    matched_term: str | None
    evidence: str | None
    missing: bool


def normalize_term(term: str) -> str:
    if not isinstance(term, str) or not term.strip():
        raise ValueError("term must be non-empty text")
    value = term.casefold().strip()
    value = re.sub(r"(^|\s)[,.;:!?]+|[,.;:!?]+(?=\s|$)", " ", value)
    return " ".join(value.split())


def _find_phrase(text: str, term: str) -> tuple[int, int] | None:
    pattern = re.compile(r"(?<!\w)" + re.escape(normalize_term(term)) + r"(?!\w)", re.IGNORECASE)
    match = pattern.search(text)
    return match.span() if match else None


def extract_terms(resume_text: str, terms: Iterable[str]) -> tuple[str, ...]:
    if not isinstance(resume_text, str):
        raise ValueError("resume_text must be text")
    requested = tuple(terms)
    if not requested:
        raise ValueError("terms must not be empty")
    found = [term for term in requested if _find_phrase(resume_text, term)]
    return tuple(found)


def _snippet(text: str, span: tuple[int, int]) -> str:
    start = text.rfind("\n", 0, span[0]) + 1
    end = text.find("\n", span[1])
    return text[start:] if end < 0 else text[start:end]


def match_requirements(resume_text: str, requirements: Iterable[Requirement]) -> tuple[MatchResult, ...]:
    if not isinstance(resume_text, str):
        raise ValueError("resume_text must be text")
    rows = tuple(requirements)
    if not rows:
        raise ValueError("requirements must not be empty")
    results = []
    for requirement in rows:
        if not isinstance(requirement, Requirement) or not requirement.canonical.strip():
            raise ValueError("invalid requirement")
        candidates = (requirement.canonical,) + tuple(requirement.synonyms)
        hit = next(((term, _find_phrase(resume_text, term)) for term in candidates
                    if _find_phrase(resume_text, term)), None)
        if hit is None:
            results.append(MatchResult(requirement.canonical, None, None, True))
        else:
            term, span = hit
            results.append(MatchResult(requirement.canonical, term, _snippet(resume_text, span), False))
    return tuple(results)


def explain_missing(results: Iterable[MatchResult]) -> str:
    rows = tuple(results)
    missing = [row.requirement for row in rows if row.missing]
    if not missing:
        return "No missing requirements; verify every matched term has defensible ownership and results."
    names = ", ".join(missing)
    return f"Missing evidence for: {names}. Add a truthful evidence sentence or a learning task; do not imply experience without proof."
