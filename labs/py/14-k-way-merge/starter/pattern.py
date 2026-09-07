"""Lab 14 — k-way merge. Fill in every TODO. Tests define done.

Rules:
  * No heapq for the merge — implement the binary heap yourself (sift_up/sift_down).
  * Merges must be O(N log k): a heap of size k over k cursors.
  * Never mutate a caller's list/array.
  * Stability: on equal values, elements from the earlier list come first.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- heap core
def _sift_up(heap: list, i: int) -> None:
    """heap[i] bubbles up until the min-heap property holds. Heap items compare
    with < (use tuples like (value, list_index) for stability)."""
    raise NotImplementedError


def _sift_down(heap: list, i: int) -> None:
    """heap[i] sinks down until the min-heap property holds."""
    raise NotImplementedError


# --------------------------------------------------------------------------- linked list
class ListNode:
    """value + next. next is None for the tail."""

    def __init__(self, value: int, next: Optional["ListNode"] = None) -> None:
        self.value = value
        self.next = next


def build_list(values: List[int]) -> Optional[ListNode]:
    """Python list -> chain of ListNodes. Empty -> None."""
    raise NotImplementedError


def list_to_values(head: Optional[ListNode]) -> List[int]:
    """Chain of ListNodes -> Python list. None -> []."""
    raise NotImplementedError


# --------------------------------------------------------------------------- merges
def merge_k_sorted_lists(lists: List[Optional[ListNode]]) -> Optional[ListNode]:
    """Merge k sorted chains into one, ascending, stable (earlier list wins ties).

    Heap of size k, seeded with each head; pop-repush as you go. O(N log k).
    """
    raise NotImplementedError


def k_sorted_arrays_merge(arrays: Sequence[Sequence[int]]) -> List[int]:
    """Merge k sorted sequences into one sorted Python list. O(N log k)."""
    raise NotImplementedError


def smallest_range_covering_k_lists(lists: Sequence[Sequence[int]]) -> Tuple[int, int]:
    """Smallest [lo, hi] (inclusive) hitting every list; ties -> smaller lo.

    Window: pointers into each list; repeatedly advance the list holding the
    current min. O(n log k).
    """
    raise NotImplementedError


def external_sort(records: List[int], chunk_capacity: int) -> List[int]:
    """Sort by chunks: split into chunks of <= chunk_capacity, sort each,
    k-way merge. Input is NOT mutated. chunk_capacity < 1 -> ValueError."""
    raise NotImplementedError
