"""Reference solution: LRU + LFU caches, O(1) get/put, injectable clock."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


class Clock:
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


# ---------- LRU ----------

class _Node:
    __slots__ = ("key", "value", "expires", "prev", "next")

    def __init__(self, key, value, expires):
        self.key = key
        self.value = value
        self.expires = expires
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int, ttl: Optional[float] = None,
                 clock: Optional[Clock] = None, on_evict: Optional[Callable[[Any, Any], None]] = None):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock or SystemClock()
        self.on_evict = on_evict
        self._map: dict[Any, _Node] = {}
        self._head = _Node(None, None, None)   # most-recent sentinel
        self._tail = _Node(None, None, None)   # least-recent sentinel
        self._head.next = self._tail
        self._tail.prev = self._head
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _expired(self, node: _Node) -> bool:
        return self.ttl is not None and node.expires is not None and self.clock.now() > node.expires

    def _detach(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _attach_front(self, node: _Node) -> None:
        node.next = self._head.next
        node.prev = self._head
        self._head.next.prev = node
        self._head.next = node

    def _evict_lru(self) -> None:
        victim = self._tail.prev
        if victim is self._head:
            return
        self._detach(victim)
        del self._map[victim.key]
        self._evictions += 1
        if self.on_evict is not None:
            self.on_evict(victim.key, victim.value)

    def get(self, key: Any) -> Optional[Any]:
        node = self._map.get(key)
        if node is None:
            self._misses += 1
            return None
        if self._expired(node):
            self._detach(node)
            del self._map[key]
            self._evictions += 1
            if self.on_evict is not None:
                self.on_evict(key, node.value)
            self._misses += 1
            return None
        self._detach(node)
        self._attach_front(node)
        self._hits += 1
        return node.value

    def put(self, key: Any, value: Any) -> None:
        node = self._map.get(key)
        if node is not None:
            node.value = value
            node.expires = (self.clock.now() + self.ttl) if self.ttl is not None else None
            self._detach(node)
            self._attach_front(node)
            return
        if len(self._map) >= self.capacity:
            self._evict_lru()
        expires = (self.clock.now() + self.ttl) if self.ttl is not None else None
        node = _Node(key, value, expires)
        self._map[key] = node
        self._attach_front(node)

    def __len__(self) -> int:
        # drop expired entries lazily
        return len(self._map)

    def __contains__(self, key: Any) -> bool:
        node = self._map.get(key)
        if node is None:
            return False
        if self._expired(node):
            self._detach(node)
            del self._map[key]
            return False
        return True

    @property
    def stats(self) -> dict:
        return {"size": len(self._map), "capacity": self.capacity,
                "hits": self._hits, "misses": self._misses, "evictions": self._evictions}


# ---------- LFU ----------

class _LFUNode:
    __slots__ = ("key", "value", "freq", "prev", "next")

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.freq = 1
        self.prev = None
        self.next = None


class _FreqList:
    """Doubly linked list of nodes sharing one frequency, MRU at front."""

    def __init__(self):
        self.head = _LFUNode(None, None)
        self.tail = _LFUNode(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size = 0

    def push_front(self, node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
        self.size -= 1

    def pop_back(self):
        if self.size == 0:
            return None
        node = self.tail.prev
        self.remove(node)
        return node

    def is_empty(self):
        return self.size == 0


class LFUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._map: dict[Any, _LFUNode] = {}
        self._freq: dict[int, _FreqList] = {}
        self._min_freq = 0

    def _touch(self, node: _LFUNode) -> None:
        fl = self._freq[node.freq]
        fl.remove(node)
        if fl.is_empty() and node.freq == self._min_freq:
            self._min_freq += 1
        node.freq += 1
        self._freq.setdefault(node.freq, _FreqList()).push_front(node)

    def get(self, key: Any) -> Optional[Any]:
        node = self._map.get(key)
        if node is None:
            return None
        self._touch(node)
        return node.value

    def put(self, key: Any, value: Any) -> None:
        node = self._map.get(key)
        if node is not None:
            node.value = value
            self._touch(node)
            return
        if len(self._map) >= self.capacity:
            fl = self._freq.get(self._min_freq)
            victim = fl.pop_back() if fl else None
            if victim is not None:
                del self._map[victim.key]
        node = _LFUNode(key, value)
        self._map[key] = node
        self._freq.setdefault(1, _FreqList()).push_front(node)
        self._min_freq = 1

    def __len__(self) -> int:
        return len(self._map)
