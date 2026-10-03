"""Starter implementation for Lab 33. Replace every stub."""
from dataclasses import dataclass
from typing import Any, Callable, Iterable


class CandidateUnavailable(RuntimeError):
    """The selected worker cannot serve this request right now."""


@dataclass(frozen=True)
class Candidate:
    name: str
    skills: frozenset[str]
    cost_per_token: float
    latency_ms: int


@dataclass(frozen=True)
class RouteResult:
    selected: str | None
    confidence: float
    abstained: bool
    fallback_used: bool
    candidate_set: tuple[str, ...]
    attempts: tuple[str, ...]
    output: Any
    status: str
    cost: float
    latency_ms: int


class SelectiveRouter:
    def __init__(self, candidates: Iterable[Candidate], *,
                 max_candidates: int = 3,
                 min_confidence: float = 0.5) -> None:
        raise NotImplementedError

    def rank(self, required_skills: Iterable[str]) -> tuple[Candidate, ...]:
        raise NotImplementedError

    def dispatch(self, required_skills: Iterable[str], token_count: int,
                 call: Callable[[Candidate, tuple[str, ...]], Any]) -> RouteResult:
        raise NotImplementedError
