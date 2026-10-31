"""Lab 37 tests. Deterministic, injectable clock, no time.sleep()."""
import pytest


def test_fake_clock_advances(C):
    c = C.FakeClock(t=0.0)
    c.advance(3.0)
    assert c.now() == 3.0


# ---- LRU basics ----

def test_lru_get_miss_returns_none(C):
    cache = C.LRUCache(capacity=2)
    assert cache.get("a") is None


def test_lru_put_then_get(C):
    cache = C.LRUCache(capacity=2)
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert len(cache) == 1


def test_lru_evicts_least_recently_used(C):
    cache = C.LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")          # touch a -> b becomes LRU
    cache.put("c", 3)       # evicts b
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lru_update_existing_does_not_grow(C):
    cache = C.LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("a", 99)
    assert len(cache) == 1
    assert cache.get("a") == 99


def test_lru_eviction_callback_fires(C):
    evicted = []
    cache = C.LRUCache(capacity=1, on_evict=lambda k, v: evicted.append((k, v)))
    cache.put("a", 1)
    cache.put("b", 2)
    assert evicted == [("a", 1)]


def test_lru_ttl_expiry(C):
    clock = C.FakeClock(t=0.0)
    cache = C.LRUCache(capacity=2, ttl=5.0, clock=clock)
    cache.put("a", 1)
    assert cache.get("a") == 1
    clock.advance(6.0)
    assert cache.get("a") is None
    assert "a" not in cache


def test_lru_ttl_refresh_on_put(C):
    clock = C.FakeClock(t=0.0)
    cache = C.LRUCache(capacity=2, ttl=5.0, clock=clock)
    cache.put("a", 1)
    clock.advance(4.0)
    cache.put("a", 2)        # refreshes TTL
    clock.advance(4.0)        # 8s total, but only 4 since refresh
    assert cache.get("a") == 2


def test_lru_capacity_validation(C):
    with pytest.raises(ValueError):
        C.LRUCache(capacity=0)


def test_lru_stats(C):
    cache = C.LRUCache(capacity=2)
    cache.put("a", 1)
    cache.get("a")
    cache.get("missing")
    s = cache.stats
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["size"] == 1


# ---- LFU ----

def test_lfu_evicts_least_frequent(C):
    cache = C.LFUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")           # a: freq 2, b: freq 1
    cache.put("c", 3)        # evicts b (lowest freq)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lfu_tie_broken_by_lru(C):
    cache = C.LFUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    # both freq 1; a was inserted first -> a is LRU among ties
    cache.put("c", 3)        # evicts a
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_lfu_update_increments_freq(C):
    cache = C.LFUCache(capacity=2)
    cache.put("a", 1)
    cache.put("a", 99)       # put on existing key increments freq
    cache.put("b", 2)
    cache.put("c", 3)        # a has freq 2, b has freq 1 -> evicts b
    assert cache.get("b") is None
    assert cache.get("a") == 99


def test_lfu_capacity_validation(C):
    with pytest.raises(ValueError):
        C.LFUCache(capacity=0)
