"""LRU cache starter -- implement LRU (and LFU) from scratch.

Goal: O(1) get and put with capacity eviction, plus TTL expiry via an
injectable clock. No functools.lru_cache, no OrderedDict shortcuts in the
starter (you may use them in the solution if you understand them).
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


class Clock:
    """Injectable time source. Tests use FakeClock; production uses SystemClock."""
    def now(self) -> float:
        raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float:
        return time.monotonic()


class FakeClock(Clock):
    def __init__(self, t: float = 0.0):
        self._t = t

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt


class LRUCache:
    """Least-recently-used cache with O(1) get/put and optional TTL.

    Evicts the least-recently-used entry when capacity is exceeded.
    Entries older than ttl (if set) are expired lazily on access.
    """

    def __init__(self, capacity: int, ttl: Optional[float] = None,
                 clock: Optional[Clock] = None, on_evict: Optional[Callable[[Any, Any], None]] = None):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock or SystemClock()
        self.on_evict = on_evict
        # TODO: implement with a hash map + doubly linked list (or OrderedDict)
        raise NotImplementedError

    def get(self, key: Any) -> Optional[Any]:
        """Return the value for key, or None if missing/expired. Touches the entry."""
        raise NotImplementedError

    def put(self, key: Any, value: Any) -> None:
        """Insert or update. Evicts LRU if over capacity."""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    def __contains__(self, key: Any) -> bool:
        raise NotImplementedError

    @property
    def stats(self) -> dict:
        raise NotImplementedError


class LFUCache:
    """Least-frequently-used cache. Evicts the least-frequently-used entry;
    ties broken by LRU (oldest among equal frequency)."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        # TODO: implement with freq buckets + doubly linked lists
        raise NotImplementedError

    def get(self, key: Any) -> Optional[Any]:
        raise NotImplementedError

    def put(self, key: Any, value: Any) -> None:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
