"""Lab 28 — skill triggering as a testable matching problem. Fill in every TODO.

In Claude, a skill fires when the model judges your prompt fits its
`description`. This lab shrinks that to regex patterns and a scoring rule
so the "does it trigger when it should?" question becomes pytest.

Rules:
  * Pure stdlib. `re` is the only module you need.
  * Skills are immutable: `bump()` returns a new Skill, never mutates.
  * Comparing scores: tuple compare (patterns matched, longest matched span).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- errors
class RegisteringError(Exception): ...


# --------------------------------------------------------------------------- skill
@dataclass
class Skill:
    """name + description + trigger patterns. The description is what a
    model would rank you against; the patterns are the lab's stand-in."""
    name: str
    description: str
    patterns: list[str]
    version: int = 1

    # TODO(step 1): precompile patterns on construction (post_init) so
    #   match() is not recompiling on every query. Keep .patterns as the
    #   original strings; store the compiled regexes separately.


def bump(skill: Skill) -> Skill:
    """TODO(step 5): a NEW Skill, same name/description/patterns,
    version + 1. The old one is untouched."""
    raise NotImplementedError


# --------------------------------------------------------------------------- scoring
def score(skill: Skill, query: str) -> Optional[tuple[int, int]]:
    """(patterns matched, longest matched span), or None if no pattern hits."""
    raise NotImplementedError


# --------------------------------------------------------------------------- index
@dataclass
class SkillIndex:
    """Registry of skills + the matcher."""
    skills: list[Skill] = field(default_factory=list)

    # TODO(step 2): register(skill)
    #   * new name            -> append
    #   * same name, version strictly higher -> REPLACE in place
    #   * same name, version equal or lower   -> raise RegisteringError
    def register(self, skill: Skill) -> None:
        raise NotImplementedError

    # TODO(step 2): get(name) -> the registered Skill (or None)
    def get(self, name: str) -> Optional[Skill]:
        raise NotImplementedError

    # TODO(step 3): match(query) -> (best_name, score) or None
    #   score = (number of patterns matched, length of longest matched text)
    #   ties: longest match wins; full tie -> earliest registered wins
    #   no skill matches -> None
    def match(self, query: str) -> Optional[tuple[str, tuple[int, int]]]:
        raise NotImplementedError

    # TODO(step 4): ambiguous(query) -> names of every skill sharing the best
    #   score when MORE THAN ONE does, else []. The over-trigger audit.
    def ambiguous(self, query: str) -> list[str]:
        raise NotImplementedError


# --------------------------------------------------------------------------- eval harness
@dataclass
class CaseResult:
    query: str
    expected: Optional[str]   # skill name, or None = must NOT trigger
    actual: Optional[str]
    passed: bool

    # TODO(step 6): fill passed = (actual == expected) at construction


@dataclass
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)

    # TODO(step 6): misses -> the failing CaseResults, in order
    @property
    def misses(self) -> list["CaseResult"]:
        raise NotImplementedError

    # TODO(step 6): accuracy -> fraction passed (0.0 when empty)
    @property
    def accuracy(self) -> float:
        raise NotImplementedError


def evaluate(index: SkillIndex, cases: list[tuple[str, Optional[str]]]) -> EvalReport:
    """TODO(step 6): run every case through index.match and collect the
    report. cases = [(query, expected_skill_name_or_None)]."""
    raise NotImplementedError
