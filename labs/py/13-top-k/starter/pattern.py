"""Lab 13 — top-k selection. Fill in every TODO. Tests define done.

Rules:
  * Implement heap sift-up/sift-down yourself; heapq/sorted are off-limits for the
    core selection logic (sorted is allowed only to normalize final output order
    where the spec says so).
  * Never mutate a caller's list.
  * quickselect must avoid the sorted-input worst case (median-of-three pivots).
"""
from __future__ import annotations

from typing import List, Optional, Tuple


def _sift_up(heap: List[int], i: int) -> None:
    """Move heap[i] up until the min-heap property holds."""
    raise NotImplementedError


def _sift_down(heap: List[int], i: int) -> None:
    """Move heap[i] down until the min-heap property holds."""
    raise NotImplementedError


def kth_largest_heap(nums: List[int], k: int) -> Optional[int]:
    """K-th largest via a size-k min-heap. O(n log k) time, O(k) space.

    Does not modify nums. k > len(nums) returns None.
    """
    raise NotImplementedError


def quickselect(nums: List[int], k: int) -> int:
    """K-th smallest (0-indexed) via in-place quickselect on a copy.

    Average O(n). Median-of-three pivots so sorted input is not quadratic.
    """
    raise NotImplementedError


def kth_largest(nums: List[int], k: int) -> Optional[int]:
    """K-th largest, implemented via quickselect on a copy."""
    raise NotImplementedError


def top_k_frequent(words: List[str], k: int) -> List[str]:
    """The k most frequent words; ties broken alphabetically ascending.

    O(n log k): keep a bounded heap of at most k candidates.
    """
    raise NotImplementedError


def k_closest_points(points: List[Tuple[int, int]], k: int) -> List[Tuple[int, int]]:
    """K points closest to the origin. Compare on dist**2 (no sqrt).

    Output order: sorted by (dist**2, x, y) — deterministic.
    """
    raise NotImplementedError


class TopKTracker:
    """Streaming top-k: .add(x) unlimited times, O(k) memory for the heap,
    .top() returns the k largest values sorted ascending."""

    def __init__(self, k: int) -> None:
        raise NotImplementedError

    def add(self, x: int) -> None:
        raise NotImplementedError

    def top(self) -> List[int]:
        raise NotImplementedError
