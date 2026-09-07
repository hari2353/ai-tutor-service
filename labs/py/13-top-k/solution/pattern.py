"""Lab 13 — top-k selection. Reference solution."""
from __future__ import annotations

from collections import Counter
from typing import List, Optional, Tuple


def _sift_up(heap: List[int], i: int) -> None:
    while i > 0:
        parent = (i - 1) // 2
        if heap[i] < heap[parent]:
            heap[i], heap[parent] = heap[parent], heap[i]
            i = parent
        else:
            break


def _sift_down(heap: List[int], i: int) -> None:
    n = len(heap)
    while True:
        l, r = 2 * i + 1, 2 * i + 2
        smallest = i
        if l < n and heap[l] < heap[smallest]:
            smallest = l
        if r < n and heap[r] < heap[smallest]:
            smallest = r
        if smallest == i:
            return
        heap[i], heap[smallest] = heap[smallest], heap[i]
        i = smallest


def _heap_replace_min(heap: List[int], val: int) -> None:
    """Pop the min and push val, keeping the heap (used with len == k)."""
    heap[0] = val
    _sift_down(heap, 0)


def kth_largest_heap(nums: List[int], k: int) -> Optional[int]:
    if k <= 0 or k > len(nums):
        return None
    heap: List[int] = []
    for x in nums:
        if len(heap) < k:
            heap.append(x)
            _sift_up(heap, len(heap) - 1)
        elif x > heap[0]:
            _heap_replace_min(heap, x)
    return heap[0]


def _median_of_three(a: List[int], lo: int, hi: int) -> int:
    """Index of the median of a[lo], a[mid], a[hi]."""
    mid = (lo + hi) // 2
    x, y, z = a[lo], a[mid], a[hi]
    if x <= y <= z or z <= y <= x:
        return mid
    if y <= x <= z or z <= x <= y:
        return lo
    return hi


def quickselect(nums: List[int], k: int) -> int:
    a = list(nums)
    lo, hi = 0, len(a) - 1
    while True:
        if lo == hi:
            return a[lo]
        p = _median_of_three(a, lo, hi)
        a[p], a[hi] = a[hi], a[p]
        pivot = a[hi]
        store = lo
        for i in range(lo, hi):
            if a[i] < pivot:
                a[i], a[store] = a[store], a[i]
                store += 1
        a[store], a[hi] = a[hi], a[store]
        if k == store:
            return a[store]
        if k < store:
            hi = store - 1
        else:
            lo = store + 1


def kth_largest(nums: List[int], k: int) -> Optional[int]:
    if k <= 0 or k > len(nums):
        return None
    return quickselect(nums, len(nums) - k)


def top_k_frequent(words: List[str], k: int) -> List[str]:
    counts = Counter(words)
    # bounded heap of at most k entries, min-first by (count, -alpha order)
    # i.e. worst candidate: lowest count, then alphabetically LAST word
    heap: List[Tuple[int, str]] = []

    def worse(a: Tuple[int, str], b: Tuple[int, str]) -> bool:
        """True if a is a worse candidate than b (a would be evicted first)."""
        if a[0] != b[0]:
            return a[0] < b[0]
        return a[1] > b[1]                     # alphabetically later = worse

    def sift_up(i: int) -> None:
        while i > 0:
            par = (i - 1) // 2
            if worse(heap[par], heap[i]):      # parent worse than child → swap
                heap[par], heap[i] = heap[i], heap[par]
                i = par
            else:
                break

    def sift_down(i: int) -> None:
        n = len(heap)
        while True:
            l, r = 2 * i + 1, 2 * i + 2
            best = i
            if l < n and worse(heap[best], heap[l]):
                best = l
            if r < n and worse(heap[best], heap[r]):
                best = r
            if best == i:
                return
            heap[i], heap[best] = heap[best], heap[i]
            i = best

    for w, c in counts.items():
        entry = (c, w)
        if len(heap) < k:
            heap.append(entry)
            sift_up(len(heap) - 1)
        elif worse(heap[0], entry):            # heap[0] is the worst candidate
            heap[0] = entry
            sift_down(0)

    result = sorted(heap, key=lambda e: (-e[0], e[1]))
    return [w for _, w in result]


def k_closest_points(points: List[Tuple[int, int]], k: int) -> List[Tuple[int, int]]:
    def key(p: Tuple[int, int]) -> Tuple[int, int, int]:
        x, y = p
        return (x * x + y * y, x, y)

    pts = list(points)
    # quickselect-style partition on the key, then sort the k survivors.
    lo, hi = 0, len(pts) - 1
    target = k - 1
    while lo < hi:
        mid = (lo + hi) // 2
        pts[mid], pts[hi] = pts[hi], pts[mid]
        pivot = key(pts[hi])
        store = lo
        for i in range(lo, hi):
            if key(pts[i]) < pivot:
                pts[i], pts[store] = pts[store], pts[i]
                store += 1
        pts[store], pts[hi] = pts[hi], pts[store]
        if store == target:
            break
        if store < target:
            lo = store + 1
        else:
            hi = store - 1
    return sorted(pts[:k], key=key)


class TopKTracker:
    def __init__(self, k: int) -> None:
        self.k = k
        self.heap: List[int] = []

    def add(self, x: int) -> None:
        if len(self.heap) < self.k:
            self.heap.append(x)
            _sift_up(self.heap, len(self.heap) - 1)
        elif x > self.heap[0]:
            _heap_replace_min(self.heap, x)

    def top(self) -> List[int]:
        return sorted(self.heap)
