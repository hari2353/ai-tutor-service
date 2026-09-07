# Lab 13: Top-K Selection

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p13-top-k`

**You will build:** the top-k family two ways — a bounded min-heap (streaming, O(n log k)) and quickselect (in-place, average O(n)) — plus the three classic applications: kth-largest, top-k-frequent, k-closest-points, and a memory-bounded streaming tracker.

**You will be able to answer:** *"Your dashboard needs the top 100 customers out of 10M. Sort, heap, or quickselect — and what's the memory story of each?"*

## Setup

```bash
cd labs/py/13-top-k
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`kth_largest_heap(nums, k)`** — build a min-heap of size k, stream every element: if bigger than the min, replace the min. Return the k-th largest (the heap's root). Must not modify `nums`. `k > len(nums)` returns `None`.
2. **`quickselect(nums, k)`** — in-place average-O(n) selection of the k-th **smallest** (0-indexed: `quickselect(nums, 0)` is the min). Use median-of-three pivots to avoid the sorted-input worst case. Returns a sorted copy of `nums` untouched (work on a copy).
3. **`kth_largest(nums, k)`** — via `quickselect` on the copy: the k-th largest is element at index `len-k` of the sorted order. Must agree with `kth_largest_heap` on every input.
4. **`top_k_frequent(words, k)`** — the k most frequent words; ties broken **alphabetically ascending**. O(n log k) with a bounded heap.
5. **`k_closest_points(points, k)`** — k points closest to the origin **by Euclidean distance, no sqrt needed**. Order within the result is sorted by (distance², x, y) — deterministic output, no `math.sqrt`.
6. **`TopKTracker(k)`** — streaming API: `.add(x)` any number of times, then `.top()` returns the k largest values **sorted ascending**, using at most O(k) memory for the heap (the state must survive unlimited adds).
7. **No `heapq`/`sorted`/`.sort()` for the core selection logic** — implement sift-up/sift-down yourself (`heapq` is allowed *only* if you are checking your own work, and `sorted` only to normalize output order where stated). No modifying caller's lists.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Weighted top-k** — items carry weights and frequency ties break by last-seen timestamp (an approximate "trending" feed).
2. **Count-Min Sketch + heap** — top-k over a stream too big to count exactly; estimate frequencies with bounded memory and return the k highest estimates.
3. **Bounded-space selection** — median of a stream in O(log n) per element with two heaps (a median maintenance structure).
4. **Worst-case O(n) select** — implement Blum-Floyd-Pratt-Rivest-Tarjan median-of-medians pivoting and articulate why production code rarely bothers.
