"""Starter for the resume evidence matching lab."""
from dataclasses import dataclass
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
    raise NotImplementedError


def extract_terms(resume_text: str, terms: Iterable[str]) -> tuple[str, ...]:
    raise NotImplementedError


def match_requirements(resume_text: str, requirements: Iterable[Requirement]) -> tuple[MatchResult, ...]:
    raise NotImplementedError


def explain_missing(results: Iterable[MatchResult]) -> str:
    raise NotImplementedError
