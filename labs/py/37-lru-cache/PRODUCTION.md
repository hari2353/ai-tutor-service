# Production notes: how real caches do it

- **Python's `functools.lru_cache`** is a C-optimized LRU for function results; it
  does not support TTL or eviction callbacks. Use it for memoization, not for
  bounded caches with expiry.
- **Redis** is the production default for shared caches: LRU/LFU eviction policies
  built in (`maxmemory-policy allkeys-lfu`), TTL via `EXPIRE`, atomic ops via Lua.
- **Caffeine (Java)** and **groupcache (Go)** add W-TinyLFU: a windowed TinyLFU
  admission filter in front of an LRU, which beats plain LRU/LFU on real workloads.
- **Key insight:** the doubly-linked-list + hash-map trick gives O(1) for both
  get and put. The "move to front" is a pointer relink, not a data copy.
- **TTL trap:** lazy expiry on access is simple but leaks memory if keys are never
  re-accessed. Production caches use a background sweeper or per-bucket expiry.
