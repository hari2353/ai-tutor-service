"""Lab 10 — the four memory types. Fill in every TODO. Tests define done.

Rules:
  * Nothing touches time.time/monotonic directly — Clock only.
  * Evictions never remove pinned messages (the system prompt).
  * Contradicted facts are KEPT — both versions, with dates.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional


# --------------------------------------------------------------------------- clock
class Clock:
    def now(self) -> float: raise NotImplementedError
    def sleep(self, seconds: float) -> None: raise NotImplementedError


class SystemClock(Clock):
    import time as _t

    def now(self) -> float: return _t.monotonic()
    def sleep(self, seconds: float) -> None: _t.sleep(seconds)


class FakeClock(Clock):
    """Deterministic clock. sleep() advances instead of blocking."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t
        self.slept: list[float] = []

    def now(self) -> float:
        # TODO(step 0a)
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        # TODO(step 0b): record and advance — never block
        raise NotImplementedError

    def advance(self, dt: float) -> None:
        # TODO(step 0c)
        raise NotImplementedError


def _estimate_tokens(text: str) -> int:
    """~4 chars/token, min 1 — the standard cheap heuristic."""
    # TODO(step 1)
    raise NotImplementedError


# --------------------------------------------------------------------------- working memory
@dataclass
class Eviction:
    """One eviction event, for tests/telemetry."""
    role: str
    content: str
    tokens: int


class WorkingMemory:
    """A bounded message deque with token-estimate eviction.

    Oldest messages go first — EXCEPT pinned messages, which never evict.
    Every eviction appends an Eviction(role, content, tokens) to .evictions.
    """

    def __init__(self, max_tokens: int, clock: Optional[Clock] = None) -> None:
        self.max_tokens = max_tokens
        self.clock = clock or SystemClock()
        self._messages: deque[tuple[str, str]] = deque()   # (role, content)
        self.evictions: list[Eviction] = []

    def add(self, role: str, content: str, pinned: bool = False) -> None:
        """Append; then evict oldest NON-PINNED messages until under budget.
        If everything left is pinned and still over budget, keep it all."""
        # TODO(step 2)
        raise NotImplementedError

    def tokens_used(self) -> int:
        # TODO(step 2b): sum of estimates over all messages
        raise NotImplementedError

    def messages(self) -> list[tuple[str, str]]:
        # TODO(step 2c): [(role, content)] oldest-first, pinned flags stripped
        raise NotImplementedError


# --------------------------------------------------------------------------- episodic
def _tokenize(text: str) -> list[str]:
    """Lowercase words: [a-z0-9'] runs. Everything else is a separator."""
    # TODO(step 3a)
    raise NotImplementedError


def _bag(text: str) -> set[str]:
    # TODO(step 3b): set of tokens
    raise NotImplementedError


def overlap_similarity(a: str, b: str) -> float:
    """Jaccard-ish overlap: |bag(a) ∩ bag(b)| / |bag(a) ∪ bag(b)|.
    Two empty texts → 0.0."""
    # TODO(step 3c)
    raise NotImplementedError


@dataclass
class Episode:
    content: str
    timestamp: float
    kind: str = "episode"
    score: float = 0.0


class EpisodicMemory:
    """Append episodes; retrieve top-k by bag-of-words overlap similarity."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        self._episodes: list[Episode] = []

    def record(self, content: str, kind: str = "episode") -> Episode:
        """Timestamp from the clock, not from the wall."""
        # TODO(step 4a)
        raise NotImplementedError

    def retrieve(self, query: str, k: int = 3) -> list[Episode]:
        """Top-k by similarity, ties broken by earlier timestamp.
        Zero-overlap episodes are NOT returned."""
        # TODO(step 4b)
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self._episodes)


# --------------------------------------------------------------------------- semantic
@dataclass
class Fact:
    key: str
    value: str
    source: str
    confidence: float
    recorded_at: float


class SemanticMemory:
    """Key-value fact store with source+confidence and contradiction handling:
    a conflicting write does NOT overwrite — both versions are kept with dates."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        self._by_key: dict[str, list[Fact]] = {}

    def insert(self, key: str, value: str, source: str,
               confidence: float = 1.0) -> Fact:
        """Append to the key's history — even if it contradicts an old value."""
        # TODO(step 5a)
        raise NotImplementedError

    def lookup(self, key: str) -> Optional[Fact]:
        """The LATEST fact for a key (None if unknown)."""
        # TODO(step 5b)
        raise NotImplementedError

    def history(self, key: str) -> list[Fact]:
        """All versions, in insertion order — contradictions included."""
        # TODO(step 5c)
        raise NotImplementedError

    def keys(self) -> list[str]:
        # TODO(step 5d): sorted key list
        raise NotImplementedError

    def contradictions(self) -> list[tuple[str, list[Fact]]]:
        """Keys holding more than one DISTINCT value, with the full history."""
        # TODO(step 5e)
        raise NotImplementedError


# --------------------------------------------------------------------------- procedural
@dataclass
class Skill:
    name: str
    trigger: re.Pattern
    instructions: str
    uses: int = 0
    successes: int = 0
    failures: int = 0
    created_at: float = 0.0
    last_used_at: Optional[float] = None

    @property
    def success_rate(self) -> float:
        # TODO(step 6a): successes/uses; 0.0 when never used
        raise NotImplementedError


class ProceduralMemory:
    """A skill library: register (trigger pattern, instructions); match a
    query; record success/failure; prune under-performers."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        self._skills: dict[str, Skill] = {}

    def register(self, name: str, trigger: str, instructions: str) -> Skill:
        """Compile the trigger (case-insensitive regex). Overwrites by name."""
        # TODO(step 6b)
        raise NotImplementedError

    def match(self, query: str) -> Optional[Skill]:
        """First registered skill whose trigger matches; None otherwise."""
        # TODO(step 6c)
        raise NotImplementedError

    def match_all(self, query: str) -> list[Skill]:
        # TODO(step 6d): every matching skill, registration order
        raise NotImplementedError

    def record_success(self, name: str) -> None:
        # TODO(step 6e): bump uses/successes, stamp last_used_at from clock
        raise NotImplementedError

    def record_failure(self, name: str) -> None:
        # TODO(step 6f)
        raise NotImplementedError

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def prune(self, min_success_rate: float = 0.5, min_uses: int = 3) -> list[str]:
        """Remove skills used >= min_uses times with success_rate below the
        threshold. Young skills (uses < min_uses) are protected.
        Returns the pruned names."""
        # TODO(step 6g)
        raise NotImplementedError


# --------------------------------------------------------------------------- compose
class AgentMemory:
    """All four, wired to one clock — the shape a real agent carries."""

    def __init__(self, working_max_tokens: int = 4000,
                 clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        # TODO(step 7): working/episodic/semantic/procedural, shared clock
        raise NotImplementedError
