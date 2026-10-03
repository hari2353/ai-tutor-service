"""Reference implementation for Lab 33."""
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
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        copied = tuple(candidates)
        names = [candidate.name for candidate in copied]
        if len(names) != len(set(names)):
            raise ValueError("candidate names must be unique")
        if any(candidate.cost_per_token < 0 or candidate.latency_ms < 0
               for candidate in copied):
            raise ValueError("candidate economics must be non-negative")
        self._candidates = copied
        self.max_candidates = max_candidates
        self.min_confidence = min_confidence

    def rank(self, required_skills: Iterable[str]) -> tuple[Candidate, ...]:
        required = frozenset(skill.casefold() for skill in required_skills)
        ranked = []
        for candidate in self._candidates:
            skills = {skill.casefold() for skill in candidate.skills}
            overlap = len(required & skills)
            if overlap:
                ranked.append((overlap, candidate.name, candidate))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return tuple(item[2] for item in ranked[:self.max_candidates])

    def dispatch(self, required_skills: Iterable[str], token_count: int,
                 call: Callable[[Candidate, tuple[str, ...]], Any]) -> RouteResult:
        if token_count < 0:
            raise ValueError("token_count must be non-negative")
        required = tuple(sorted({skill.casefold() for skill in required_skills}))
        ranked = self.rank(required)
        names = tuple(candidate.name for candidate in ranked)
        if not ranked:
            return RouteResult(None, 0.0, True, False, names, (), None,
                               "abstained", 0.0, 0)

        required_count = len(set(required))
        top_overlap = len(set(required) &
                          {skill.casefold() for skill in ranked[0].skills})
        coverage = top_overlap / required_count if required_count else 0.0
        if len(ranked) == 1:
            margin = 1.0
        else:
            second_overlap = len(set(required) &
                                 {skill.casefold() for skill in ranked[1].skills})
            margin = (top_overlap - second_overlap) / top_overlap
        confidence = coverage * margin
        if confidence < self.min_confidence:
            return RouteResult(None, confidence, True, False, names, (), None,
                               "abstained", 0.0, 0)

        attempts = []
        total_cost = 0.0
        total_latency = 0
        for index, candidate in enumerate(ranked):
            attempts.append(candidate.name)
            total_cost += token_count * candidate.cost_per_token
            total_latency += candidate.latency_ms
            try:
                output = call(candidate, required)
            except CandidateUnavailable:
                continue
            return RouteResult(candidate.name, confidence, False, index > 0,
                               names, tuple(attempts), output, "success",
                               total_cost, total_latency)

        return RouteResult(None, confidence, False, len(attempts) > 1, names,
                           tuple(attempts), None, "failed", round(total_cost, 12),
                           total_latency)
