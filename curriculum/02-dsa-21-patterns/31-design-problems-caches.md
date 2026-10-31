# Design Cache Problems: LRU/LFU Cache, Ring Buffer, Rate Limiter

> **Track:** T02 DSA: 21 Patterns · **Time:** 2h · **Prereqs:** T02-p13-top-k, T02-p06-ll-reversal
> **Module id:** `T02-design-problems-caches` · **Tags:** advanced, interview, design

## The 30-second version

A family of interview questions that are not data structures you memorize but data structures you *build to a contract*: implement an **LRU cache** with O(1) `get`/`put` (hashmap + doubly-linked list, or `OrderedDict`/`LinkedHashMap` in Java), an **LFU cache** with O(1) eviction (hashmap plus a frequency-to-keys map plus an in-frequency insertion-order list), a **ring buffer** that tails a live stream at O(1) per write with fixed memory (the structure behind log-tail and streaming metrics problems), and a **rate limiter** (token bucket, sliding-window counter) built from the same primitives. What interviewers grade is not that you can code an eviction policy — it's that you can state the contract first (capacity, O(1) bounds, tie-break rule, what happens at overflow), pick the two structures whose composition *gives* you the bound, reason about eviction with a concrete trace, and defend it against the standard follow-ups: thread-safety, memory-bound resizing, and "now make `get` also count as a use." If you start writing code before stating the contract and the complexity target, you fail the question regardless of whether the code runs.

## Why this gets asked

Because every real system you will ever build has a cache-shaped edge case, and the LRU-family questions are the cheapest way to watch a candidate design under three constraints at once: a latency target ("O(1) — not O(log n), not amortized-nowhere"), a memory budget ("fixed capacity, `put` must free exactly one entry when full"), and a *correctness invariant that's invisible in testing* (eviction is only observable on sequences longer than your test cases, so silent O(n) list scans and dict-copy races pass every toy test). It also has a rare property: the O(1) LRU construction (hashmap `key → node`, plus `node ↔ node` links) is *structurally surprising the first time you see it*, and you cannot derive it under pressure unless you've built it once with your hands. Interviewers ask it precisely because it separates people who have built one from people who can recite that caches exist.

---

## Lineage: past → present → future

**What came before.** The problem formalized in operating systems: page replacement under fixed frames (FIFO, optimal — untypeable, since it needs the future — then LRU as the standard implementable approximation, with FIFO's Belady-anomaly-shaped pathologies as the reason LRU wins). The interview version started as a LeetCode-recognized pattern but its production roots are older: every database buffer pool (PostgreSQL's shared buffers, MySQL's InnoDB LRU with midpoint insertion against full-scan pollution) and every read cache (memcached, Cloudflare's bounded queues) implements some member of this family with a twist the interview version strips out — frequency aging, admission control, or size-aware eviction.

**Where it stands now.** The canonical interview question set has barely moved since ~2015, which is itself information: LRU, LFU, ring buffer and rate limiter are the four "design-a-bound" warmups asked before a candidate reaches real system design, and they get asked at every level from new grad to staff (the interview difficulty moves from "code it" to "code it plus discuss contention, plus compare against language-standard types"). What has moved: `functools.lru_cache` and Java's `LinkedHashMap(accessOrder=true)` made "just use the standard library" a legitimate first answer *in production code* — but in interviews that answer buys you the follow-up "fine, implement `lru_cache`," so treat stdlib as the bug-free version and hand-rolled as the interview version.

**Where it's heading.** Medium confidence: the follow-up conversation shifts from pure eviction towards **contention and observability** — "two threads race `put` to the same empty slot," "your cache is 100% misses, how would you know" (hit-rate instrumentation, which connects to `T10-semantic-caching`'s semantic-layer versions of the same question). Speculative: adversarial LRU-degrading questions ("show an input sequence that makes pure LRU thrash while LFU survives") moving from behavioural trivia to scored follow-ups, since cache pollution is exactly what a candidate's future job produces.

---

## Mental model

Two lists pretending to be one cache.

```
  KEY → NODE map (the "is it here?" half, O(1))          EVICTION list (the "how fresh?" half)

  ┌─────────┐        ┌──────────────────────────────┐
  │ key_A ──┼──────► │ head ⟷ A ⟷ C ⟷ D ⟷ … ⟷ tail │
  │ key_C ──┼──────► │                              │
  │ key_D ──┼──────► │ most used        least used  │
  └─────────┘        │   (MRU)              (LRU)   │
                     └──────────────────────────────┘

  get(k): map → node → unlink → relink at head → return. O(1).
  put(k,v):
    hit  = same, then overwrite value.
    miss = full? unlink tail, delete its map entry.
           splice new node at head, map[k] = node. O(1).
```

Every eviction policy in this family is which end feeds whom and what the list is ordered *by* — LRU orders by recency (one list), LFU orders by frequency (one list *per frequency*), ring buffer orders by nothing but arrival (a fixed array that wraps, no eviction decision at all). If you hold that shape, all four implementations are the same paragraph with different ordering keys.

---

## Recognition heuristics

- **"implement a cache / get & put / constant time / evict least recently used"** → LRU. Two structures: hashmap + doubly-linked list. If the interviewer accepts "amortized", `OrderedDict`/`LinkedHashMap` with an ordering flag is correct and complete — the whiteboard version is what its code does.
- **"least *frequently* used / ties broken by recency"** → LFU. Add `freq → list-of-keys` on top of the LRU skeleton; move-to-head becomes move-across-frequency-buckets, with a global `minFreq` pointer instead of a head/tail.
- **"stream of values / fixed buffer / tail or last N / O(1) per item / no eviction worth asking about"** → ring buffer. Fixed array + write index + count, wrap-around modulo. Interviewers love the precision asking: what's the姜 invariant between `head`/`count` at each write, and boundary bugs at wrap.
- **"throttle / at most N requests per window / drop or delay"** → rate limiter → token bucket (allows bounded burst, smooth refill) or sliding-window counter (no burst allowance). Connects maps directly to `T30-api-security`'s production rate limiting — the interview version is the primitive, the security module is the deployed version.

---

## How it actually works — writing the LRU, and where it fails

The hashmap alone cannot tell you *what to evict*; the list alone cannot give you O(1) *lookup*. So the design is exactly the two halves in the mental model, and every interview-grade detail is either a link bookkeeping rule or a contract statement:

- **Sentinel nodes at both ends** (`self.head`, `self.tail` are real nodes, not `None`). Only rule: the eviction branch never checks "is the list empty" — empty list means only the sentinels are present, so `remove(self.tail.prev)` is uniform code. The most common whiteboard bug is reconstructing edge cases at both ends separately; sentinels delete that entire bug class.
- **Remove-then-insert is one helper** (`_unlink(node)` then `_push_front(node)`), called by both `get` (on hit) and `put` (on hit-and-overwrite). If those two paths renumber links by hand, one of them is wrong by the time you've typed it.
- **`put` on existing key is an update, not an insert** — you'd be surprised how many candidates mutate `capacity` logic into the miss branch because the "update path" never frees anything.
- **The contract must leave your mouth before code.** "O(1) `get` and `put`, capacity `n`, ties on equal recency resolved by recency order, thread-safety assumed single-threaded unless you follow up." And the fifth follow-up ~always called: *"get also renews recency?"* — the contract decides, not you; guess and you're building the wrong interview.

```python
class Node:
    __slots__ = ("key", "val", "prev", "next")
    def __init__(self, key=None, val=None):
        self.key, self.val = key, val
        self.prev = self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.map = {}                       # key -> Node
        self.head, self.tail = Node(), Node()   # sentinels
        self.head.next, self.tail.prev = self.tail, self.head

    def _unlink(self, n):                   # n has real neighbours
        n.prev.next, n.next.prev = n.next, n.prev

    def _push_front(self, n):               # right after head sentinel
        n.next, n.prev = self.head.next, self.head
        self.head.next.prev = n
        self.head.next = n

    def get(self, key):
        n = self.map.get(key)
        if n is None: return -1
        self._unlink(n); self._push_front(n)
        return n.val

    def put(self, key, value):
        n = self.map.get(key)
        if n:
            n.val = value
            self._unlink(n); self._push_front(n)
            return
        if len(self.map) >= self.cap:
            lru = self.tail.prev
            self._unlink(lru)               # never None: sentinels guarantee >=2
            del self.map[lru.key]
        n = Node(key, value)
        self.map[key] = n
        self._push_front(n)
```

**LFU** keeps the same skeleton and adds: `freq_to_list: {freq: OrderedDict[key → node]}`, `min_freq`, and on access `f → f+1` moves the key across buckets (in practice, one nested `OrderedDict` per frequency: pop from the old bucket's front, append to the new bucket's end); when the old bucket empties at exactly `min_freq`, bump `min_freq`. That gives O(1) get/put with the classic tie-break: evict the *front* of the lowest-frequency bucket, i.e. least-recently-touched among the least-frequent.

**Ring buffer** — no allocation after init, no locks on commit, and the only trick is two invariants you state out loud: `count == capacity` before advancing a full buffer's write pointer means *overwrite is allowed by contract* (this is what makes it "fixed memory"), and a read never crosses the written range. Ring buffers are the minimal version of the log-tail problem: "return the K most frequent log lines" reads as ring-buffer-write + HashMap-counter.

**Rate limiter** — token bucket: `tokens = min(cap, tokens + (now - last)*rate); if tokens >= 1: tokens -= 1; allow` (the interview-grade detail: refill is computed from elapsed time at request time, not from a background tick); sliding-window counter: bucket by window, keep last two buckets, weight = `prev*(1 - elapsed_fraction) + curr`. Both O(1) with a dict keyed by client.

---

## Complexity — derived, not asserted

| Structure | get | put/evict | Memory | The bound comes from |
|---|---|---|---|---|
| LRU (map + linked list) | O(1) | O(1) | O(capacity) | map lookup +intrusion a few pointer writes |
| LFU (map + freq buckets) | O(1) | O(1) | O(capacity + #freqs) | bucket move is pointer arithmetic |
| Ring buffer (array) | O(1) (oldest) | O(1) write (overwrite) | O(capacity), *zero* per-item | modulo wrap, no allocation |
| Token-bucket / window limiter | O(1) | O(1) | O(#clients) | arithmetic on the bucket entry |

The one-liner interviewers drill for: "Why not an array or a plain dict for LRU?" — because the *eviction decision* needs an order (the array gives you O(n) min-by-recency scans), and a plain dict gives you lookup without *order* (the O(1) guarantee comes only when the two structures each cover one of the two requirements). Saying that sentence cleanly is most of the points.

---

## The 5 variants interviewers actually ask

1. **LRU with capacity 0 / negative capacity** — validate at init; the contract-level follow-up hidden in construction.
2. **`get` in O(log n) also being fine?** — fine, but say what changed: `OrderedDict.move_to_end` is O(1); a heap-based recency would be update-cost — walk the tradeoff rather than assuming.
3. **Thread-safe LRU** — a lock around get/put is the naive answer; the good answer notes that the per-touch move-to-front serialises on the hottest key, hence batched/sharded caches — which is the production fix, not the interview and not the exam.
4. **"Show me a workload where LRU thrashes but LFU doesn't"** and in the same breath, a workload where LFU is permanently poisoned by a cold start that has become dead weight (frequency aging / "LFU-k" fixes）— admission-control is the production-shaped answer to both directions of pollution, which is roughly what MySQL's midpoint insertion does.
5. **Merge with real infra** — "your in-process dict LRU is now cloned across 4 pods; what breaks?" — hit-rate collapse, cache coherency, and why Redis or an L1+L2 layer follows (bridge away from the pattern into `T21-cache-hit`/`T10-semantic-caching`).

---

## Common bugs and how these get shipped wrong under pressure

- **Deleting the entry from the map but not unlinking the node** (leak: the list grows without bound and the O(1) claim becomes fiction — under load, not in test).
- **`put` on a full cache evicting *before* the key-exists check** — evicts then re-adds, needlessly cycling a fresh entry in and out (correctness unaffected; hit-rate on hot keys dies quietly).
- **Ring-buffer wrap with `head + count > capacity` pointers handled inconsistently** for read versus write — the single most-shipped memory bug in this family, because every unit test writes one item and reads it back once.
- **Limiter refill computed per-request against `last` stored as a wall-clock second** (truncation) rather than with elapsed time (typically a token-bucket refill rounding bug that shows up as "customer saw double requests").

---

## Interview questions

1. **Implement an LRU cache with O(1) get and put.** Core. Say the contract; build sentinel'd list + hashmap; trace a four-key sequence out loud.
2. **What if `get` must not renew recency?** The contract question: pass a flag, or stop calling `_push_front` on read — the cost: reading hot keys no longer protects them, and the eviction list becomes write-only-recency (why that is genuinely the wrong production answer matters more than the code).
3. **LFU with O(1) get and put, ties to LRU.** Freq buckets + min-freq pointer; state the `min_freq`-bump rule before being asked; note frequency-aging as the honest follow-up.
4. **Design a rate limiter for 1M users, 100 req/min, distributed.** Token bucket per-user dict is the start; then the honest escalation: per-request post-check race window, then Redis + Lua atomic ops (`T30-api-security`'s distributed limiter), then "within one node" vs "global quota" as a product decision.
5. **Ring buffer: the last 1000 log lines in O(1) per flush, memory fixed.** Array + head + count; the fix for "mod wrap" correctness is a two-interval read (`[head, cap)` ∪ `[0, head+count-cap)`).
6. **Why is `functools.lru_cache` not the answer in an interview but the answer in production?** — names the product wall: instance-method memory leaks (Ruff B019), unbounded key explosion, and what `maxsize=None` means in production (a leak).

## Red flags that fail you

- Coding before stating capacity / bounds / tie-break contract — interviewers score the question by the contract, not typing speed.
- Reaching for `OrderedDict.move_to_end` and stopping — it's correct; what fails you is not being able to hand-build the structure whose behavior that call hides.
- Caching questions answered without mentioning *hit-rate in production* (or at least "how would I know my eviction policy is wrong") — that observation is the difference between "I implemented a cache" and "I operate a cache."

## Cheat card

- LRU = `map: key→node` + DLL with sentinels; unlink-then-push-front on every touch; O(1) get/put.
- LFU = LRU skeleton + `freq→OrderedDict` + `min_freq`; evict front of lowest freq bucket; O(1) with careful bucket moves.
- Ring buffer = fixed array + head + count + wrap; zero allocation, overwrite-by-contract when full.
- Rate limiter = token bucket (burst-allowing, time-computed refill) or sliding-window counter (fixed window smoothing); O(1) per check.
- Trace every structure against a four-entry sequence before claiming done; state contract-first, code second.

## Sources

- [LeetCode 146 — LRU Cache](https://leetcode.com/problems/lru-cache/) and [LeetCode 460 — LFU Cache](https://leetcode.com/problems/lfu-cache/) — problem definitions (accessed 2026-10-31)
- [medium.com/@codedsoul_05 — coding patterns sheet](https://www.instagram.com/p/DbnephXDbZb/) — the "50 coding patterns" framing that motivated this module (accessed 2026-10-31)
- MySQL manual — InnoDB buffer pool LRU [midpoint insertion](https://dev.mysql.com/doc/refman/8.4/en/innodb-buffer-pool.html) (accessed 2026-10-31)

## Changelog

- 2026-10-31: Created from the IG batch audit (LRU + cache-design problems were the only DSA-family gap; every other pattern already had a module).
