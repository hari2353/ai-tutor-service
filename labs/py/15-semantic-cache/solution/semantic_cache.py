"""Lab 15 — reference solution: three-layer LLM cache (exact → prefix → semantic)."""
from __future__ import annotations

import hashlib
import json
import string
import time
from dataclasses import dataclass, field
from typing import Callable

# Marker appended to answers served from the prefix layer. The shared prefix was
# byte-identical (after whitespace/punct normalization) but the tail of the new
# prompt diverged, so the cached continuation is an approximation — say so.
PREFIX_CONTINUATION_MARKER = " [cached-prefix continuation]"

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


# --------------------------------------------------------------------------- clock
class Clock:
    def now(self) -> float:
        raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float:
        return time.monotonic()


class FakeClock(Clock):
    """Deterministic clock for tests. advance() moves time without sleeping."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# --------------------------------------------------------------------------- text ops
def normalize(text: str) -> str:
    """Lowercase, DROP punctuation, collapse every whitespace run to one space.

    Used by the prefix and semantic layers ONLY. The exact layer hashes the raw
    prompt bytes — that asymmetry is the point of layering.
    """
    return " ".join(text.lower().translate(_PUNCT_TABLE).split())


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def char_3grams(text: str) -> frozenset[str]:
    """Set of character trigrams over normalize(text).

    Inputs shorter than 3 chars fall back to {normalize(text)} so short prompts
    still produce a non-degenerate signature; "" produces the empty set.
    """
    s = normalize(text)
    if not s:
        return frozenset()
    if len(s) < 3:
        return frozenset({s})
    return frozenset(s[i:i + 3] for i in range(len(s) - 2))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """|a ∩ b| / |a ∪ b|; two empty sets have no evidence → 0.0."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def exact_key(model: str, params: dict | None, prompt: str) -> str:
    """sha256 over the FULL request. sort_keys makes param order irrelevant;
    the raw prompt goes in untouched (no strip, no case-fold, no punct-drop)."""
    payload = json.dumps(
        {"model": model, "params": dict(params or {}), "prompt": prompt},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- records
@dataclass
class CacheStats:
    exact_hits: int = 0
    prefix_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hits(self) -> int:
        return self.exact_hits + self.prefix_hits + self.semantic_hits

    @property
    def lookups(self) -> int:
        return self.hits + self.misses

    def as_dict(self) -> dict[str, int]:
        return {
            "exact_hits": self.exact_hits,
            "prefix_hits": self.prefix_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }


@dataclass(frozen=True)
class CacheResult:
    answer: str
    layer: str                        # "exact" | "prefix" | "semantic" | "backend"
    similarity: float | None = None   # semantic layer only
    prefix_chars: int | None = None   # prefix layer only
    model: str = ""


@dataclass
class _Entry:
    key: str                          # exact-layer hash
    model: str                        # namespace: all layers are model-scoped
    prompt: str                       # raw bytes (exact layer)
    norm: str                         # normalized (prefix layer)
    grams: frozenset[str]             # char-3gram signature (semantic layer)
    answer: str
    ts: float


# --------------------------------------------------------------------------- cache
class SemanticCache:
    """Exact → prefix → semantic fallthrough with one backing entry store.

    One fill populates ALL layers because each _Entry carries the three views of
    a prompt: raw bytes, normalized string, trigram set. Layers only decide HOW
    a lookup matches, never what gets stored.

    Layer knobs: `prefix_min_chars=None` disables the prefix layer,
    `threshold=None` disables the semantic layer. Capacity evicts oldest-inserted
    entries (FIFO by insertion); TTL expiry is lazy and does NOT count as an
    eviction. All lookups are scoped to a single model — cross-model leakage
    through any layer is a bug, per the tenant-isolation rule.
    """

    def __init__(self, backend_fn: Callable[[str], str], *,
                 clock: Clock | None = None,
                 ttl: float = 300.0,
                 prefix_min_chars: int | None = 20,
                 threshold: float | None = 0.6,
                 capacity: int | None = 128) -> None:
        self.backend_fn = backend_fn
        self.clock = clock or SystemClock()
        self.ttl = ttl
        self.prefix_min_chars = prefix_min_chars
        self.threshold = threshold
        self.capacity = capacity
        self.stats = CacheStats()
        self._entries: list[_Entry] = []   # insertion order; linear scan is fine here

    # -- internals ------------------------------------------------------------
    def _purge_expired(self) -> None:
        now = self.clock.now()
        self._entries = [e for e in self._entries if now - e.ts < self.ttl]

    def _evict_if_full(self) -> None:
        while self.capacity is not None and len(self._entries) >= self.capacity:
            self._entries.pop(0)
            self.stats.evictions += 1

    def _fill(self, model: str, params: dict | None, prompt: str) -> CacheResult:
        answer = self.backend_fn(prompt)
        self._evict_if_full()
        self._entries.append(_Entry(
            key=exact_key(model, params, prompt),
            model=model,
            prompt=prompt,
            norm=normalize(prompt),
            grams=char_3grams(prompt),
            answer=answer,
            ts=self.clock.now(),
        ))
        return CacheResult(answer=answer, layer="backend", model=model)

    def _try_exact(self, model: str, key: str) -> CacheResult | None:
        for e in self._entries:
            if e.model == model and e.key == key:
                self.stats.exact_hits += 1
                return CacheResult(answer=e.answer, layer="exact", model=model)
        return None

    def _try_prefix(self, model: str, prompt: str) -> CacheResult | None:
        if self.prefix_min_chars is None:
            return None
        qnorm = normalize(prompt)
        best_e, best_len = None, -1
        for e in self._entries:
            if e.model != model:
                continue
            plen = common_prefix_len(qnorm, e.norm)
            if plen > best_len:
                best_e, best_len = e, plen
        if best_e is not None and best_len >= self.prefix_min_chars:
            self.stats.prefix_hits += 1
            return CacheResult(
                answer=best_e.answer + PREFIX_CONTINUATION_MARKER,
                layer="prefix",
                prefix_chars=best_len,
                model=model,
            )
        return None

    def _try_semantic(self, model: str, prompt: str) -> CacheResult | None:
        if self.threshold is None:
            return None
        qgrams = char_3grams(prompt)
        best_e, best_sim = None, -1.0
        for e in self._entries:
            if e.model != model:
                continue
            sim = jaccard(qgrams, e.grams)
            if sim > best_sim:
                best_e, best_sim = e, sim
        if best_e is not None and best_sim >= self.threshold:
            self.stats.semantic_hits += 1
            return CacheResult(answer=best_e.answer, layer="semantic",
                               similarity=best_sim, model=model)
        return None

    # -- public API -------------------------------------------------------------
    def ask(self, prompt: str, model: str = "default",
            params: dict | None = None) -> CacheResult:
        """Serve from exact → prefix → semantic; on total miss call the backend
        exactly once and populate every applicable layer."""
        self._purge_expired()
        hit = self._try_exact(model, exact_key(model, params, prompt))
        if hit is None:
            hit = self._try_prefix(model, prompt)
        if hit is None:
            hit = self._try_semantic(model, prompt)
        if hit is not None:
            return hit
        self.stats.misses += 1
        return self._fill(model, params, prompt)

    def hit_rate(self) -> float:
        """hits / (hits + misses) — the denominator is ALL asks, not just misses."""
        total = self.stats.lookups
        return self.stats.hits / total if total else 0.0

    def invalidate(self, model: str) -> int:
        """Drop every entry belonging to `model`. Returns how many were dropped."""
        keep = [e for e in self._entries if e.model != model]
        removed = len(self._entries) - len(keep)
        self._entries = keep
        return removed

    def __len__(self) -> int:
        return len(self._entries)
