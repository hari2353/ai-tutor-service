# Lab 37: LRU and LFU Caches From Scratch

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Modules:** `T02-design-problems-caches`

**You will build:** an LRU cache (O(1) get/put with capacity eviction) and an LFU
cache (least-frequently-used, ties broken by LRU), both backed by a hash map plus
doubly linked lists, with an injectable clock for TTL expiry.

**You will be able to answer:** *"Implement an LRU cache. Now make it O(1). Now
add TTL. Now make it LFU. What changes?"*

## Setup

```bash
cd labs/py/37-lru-cache
python -m venv .venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **`Clock` / `SystemClock` / `FakeClock`** — injectable time source. `FakeClock(t).advance(dt)`. No `time.sleep()` in tests.
2. **`LRUCache(capacity, ttl=None, clock=None, on_evict=None)`** — capacity > 0 else `ValueError`.
   - `get(key)` → value or `None` (missing or expired). Touches the entry (moves to front).
   - `put(key, value)` → insert or update; evicts LRU on overflow; fires `on_evict(key, value)`.
   - `__len__`, `__contains__`, `.stats` (hits/misses/evictions/size/capacity).
   - TTL: lazy expiry on access; `put` on existing key refreshes TTL.
3. **`LFUCache(capacity)`** — evict least-frequently-used; ties broken by LRU (oldest among equal freq). `put` on existing key increments freq.

## Run the tests

```bash
pytest tests/ -v          # against starter/ -> FAILS. Make them pass.
pytest tests/ -v --solution   # reference passes
```

## Stretch goals

1. **LFU with O(1)** — freq buckets of doubly linked lists (already in solution).
2. **Combined LRU+LFU** — a cache that evicts by LFU then LRU.
3. **Thread safety** — add a lock; measure the contention cost.

