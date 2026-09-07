"""Lab 10 — reference solution: the four memory types."""
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
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds

    def advance(self, dt: float) -> None:
        self.t += dt


def _estimate_tokens(text: str) -> int:
    """~4 chars/token, min 1 — the standard cheap heuristic."""
    return max(1, (len(text) + 3) // 4)


# --------------------------------------------------------------------------- working memory
@dataclass
class Eviction:
    """One eviction event, for tests/telemetry."""
    role: str
    content: str
    tokens: int


class WorkingMemory:
    """A bounded message deque with token-estimate eviction.

    Oldest messages go first — EXCEPT pinned messages (the system prompt),
    which never evict. Eviction events are recorded for inspection.
    """

    def __init__(self, max_tokens: int, clock: Optional[Clock] = None) -> None:
        self.max_tokens = max_tokens
        self.clock = clock or SystemClock()
        self._messages: deque[tuple[str, str]] = deque()   # (role, content)
        self._pinned: set[int] = set()                      # indices are unstable;
        self.evictions: list[Eviction] = []                  # pinned roles are checked instead

    def add(self, role: str, content: str, pinned: bool = False) -> None:
        if pinned:
            role = f"__pinned__{role}"
        self._messages.append((role, content))
        self._evict_while_over()

    def _is_pinned(self, role: str) -> bool:
        return role.startswith("__pinned__")

    def tokens_used(self) -> int:
        return sum(_estimate_tokens(c) for _, c in self._messages)

    def messages(self) -> list[tuple[str, str]]:
        return [(r.removeprefix("__pinned__"), c) for r, c in self._messages]

    def _evict_while_over(self) -> None:
        while self.tokens_used() > self.max_tokens and len(self._messages) > 1:
            # find the oldest non-pinned message
            idx = next((i for i, (r, _) in enumerate(self._messages)
                        if not self._is_pinned(r)), None)
            if idx is None:
                break           # only pinned messages left
            role, content = self._messages[idx]
            self._messages.remove((role, content))
            self.evictions.append(
                Eviction(role.removeprefix("__pinned__"), content,
                         _estimate_tokens(content)))


# --------------------------------------------------------------------------- episodic
def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _bag(text: str) -> set[str]:
    return set(_tokenize(text))


def overlap_similarity(a: str, b: str) -> float:
    """Jaccard-ish overlap: |bag(a) ∩ bag(b)| / |bag(a) ∪ bag(b)|."""
    ba, bb = _bag(a), _bag(b)
    if not ba and not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


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
        ep = Episode(content=content, timestamp=self.clock.now(), kind=kind)
        self._episodes.append(ep)
        return ep

    def retrieve(self, query: str, k: int = 3) -> list[Episode]:
        scored = []
        for ep in self._episodes:
            s = overlap_similarity(query, ep.content)
            ep.score = s
            scored.append((s, ep))
        scored.sort(key=lambda t: (-t[0], t[1].timestamp))
        return [ep for s, ep in scored[:k] if s > 0]

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
        f = Fact(key, value, source, confidence, self.clock.now())
        self._by_key.setdefault(key, []).append(f)
        return f

    def lookup(self, key: str) -> Optional[Fact]:
        """The LATEST fact for a key."""
        facts = self._by_key.get(key, [])
        return facts[-1] if facts else None

    def history(self, key: str) -> list[Fact]:
        """All versions, in insertion order — contradictions included."""
        return list(self._by_key.get(key, []))

    def keys(self) -> list[str]:
        return sorted(self._by_key)

    def contradictions(self) -> list[tuple[str, list[Fact]]]:
        """Keys holding >1 distinct value."""
        out = []
        for key, facts in self._by_key.items():
            if len({f.value for f in facts}) > 1:
                out.append((key, list(facts)))
        return out


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
        return self.successes / self.uses if self.uses else 0.0


class ProceduralMemory:
    """A skill library: register (trigger pattern, instructions); match a
    query; record success/failure; prune under-performers by decay."""

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        self._skills: dict[str, Skill] = {}

    def register(self, name: str, trigger: str, instructions: str) -> Skill:
        pattern = trigger if isinstance(trigger, re.Pattern) \
            else re.compile(trigger, re.IGNORECASE)
        skill = Skill(name, pattern, instructions, created_at=self.clock.now())
        self._skills[name] = skill
        return skill

    def match(self, query: str) -> Optional[Skill]:
        """First registered skill whose trigger matches; None otherwise."""
        for skill in self._skills.values():
            if skill.trigger.search(query):
                return skill
        return None

    def match_all(self, query: str) -> list[Skill]:
        return [s for s in self._skills.values() if s.trigger.search(query)]

    def record_success(self, name: str) -> None:
        s = self._skills[name]
        s.uses += 1
        s.successes += 1
        s.last_used_at = self.clock.now()

    def record_failure(self, name: str) -> None:
        s = self._skills[name]
        s.uses += 1
        s.failures += 1
        s.last_used_at = self.clock.now()

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def prune(self, min_success_rate: float = 0.5, min_uses: int = 3) -> list[str]:
        """Remove skills used >= min_uses times with success_rate below the
        threshold. Returns the names pruned."""
        doomed = [name for name, s in self._skills.items()
                  if s.uses >= min_uses and s.success_rate < min_success_rate]
        for name in doomed:
            del self._skills[name]
        return doomed


# --------------------------------------------------------------------------- compose
class AgentMemory:
    """All four, wired to one clock — the shape a real agent carries."""

    def __init__(self, working_max_tokens: int = 4000,
                 clock: Optional[Clock] = None) -> None:
        self.clock = clock or SystemClock()
        self.working = WorkingMemory(working_max_tokens, self.clock)
        self.episodic = EpisodicMemory(self.clock)
        self.semantic = SemanticMemory(self.clock)
        self.procedural = ProceduralMemory(self.clock)
