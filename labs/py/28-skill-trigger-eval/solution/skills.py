"""Lab 28 — reference implementation. skills.py"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- errors
class RegisteringError(Exception): ...


# --------------------------------------------------------------------------- skill
@dataclass
class Skill:
    name: str
    description: str
    patterns: list[str]
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled", [re.compile(p) for p in self.patterns])

    def matches(self, query: str) -> Optional[tuple[int, int]]:
        hits = [m for rx in self._compiled if (m := re.search(rx, query))]
        if not hits:
            return None
        return (len(hits), max(len(m.group(0)) for m in hits))


def bump(skill: Skill) -> Skill:
    return Skill(skill.name, skill.description, skill.patterns, skill.version + 1)


# --------------------------------------------------------------------------- index
@dataclass
class SkillIndex:
    skills: list[Skill] = field(default_factory=list)

    def register(self, skill: Skill) -> None:
        for i, existing in enumerate(self.skills):
            if existing.name == skill.name:
                if skill.version <= existing.version:
                    raise RegisteringError(
                        f"'{skill.name}' is at version {existing.version}; "
                        f"replacing needs version > {existing.version}")
                self.skills[i] = skill
                return
        self.skills.append(skill)

    def get(self, name: str) -> Optional[Skill]:
        for s in self.skills:
            if s.name == name:
                return s
        return None

    def match(self, query: str) -> Optional[tuple[str, tuple[int, int]]]:
        scored = [(s.matches(query), i, s) for i, s in enumerate(self.skills)]
        scored = [(sc, i, s) for sc, i, s in scored if sc is not None]
        if not scored:
            return None
        # most patterns matched, then longest span, then earliest registered
        best = min(scored, key=lambda t: (-t[0][0], -t[0][1], t[1]))
        return (best[2].name, best[0])

    def ambiguous(self, query: str) -> list[str]:
        scored = [(s.matches(query), s.name) for s in self.skills]
        scored = [t for t in scored if t[0] is not None]
        if len(scored) < 2:
            return []
        best = max(t[0] for t in scored)
        tied = [name for sc, name in scored if sc == best]
        return tied if len(tied) > 1 else []


# --------------------------------------------------------------------------- eval harness
@dataclass
class CaseResult:
    query: str
    expected: Optional[str]
    actual: Optional[str]
    passed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "passed", self.actual == self.expected)


@dataclass
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)

    @property
    def misses(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)


def evaluate(index: SkillIndex, cases: list[tuple[str, Optional[str]]]) -> EvalReport:
    results = []
    for query, expected in cases:
        m = index.match(query)
        actual = m[0] if m else None
        results.append(CaseResult(query=query, expected=expected, actual=actual,
                                  passed=actual == expected))
    return EvalReport(results=results)
