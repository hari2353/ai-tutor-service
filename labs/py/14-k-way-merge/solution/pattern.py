"""Lab 14 — k-way merge. Reference solution."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple


def _sift_up(heap: list, i: int) -> None:
    while i > 0:
        parent = (i - 1) // 2
        if heap[i] < heap[parent]:
            heap[i], heap[parent] = heap[parent], heap[i]
            i = parent
        else:
            break


def _sift_down(heap: list, i: int) -> None:
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


class ListNode:
    def __init__(self, value: int, next: Optional["ListNode"] = None) -> None:
        self.value = value
        self.next = next


def build_list(values: List[int]) -> Optional[ListNode]:
    head: Optional[ListNode] = None
    tail: Optional[ListNode] = None
    for v in values:
        node = ListNode(v)
        if head is None:
            head = tail = node
        else:
            assert tail is not None
            tail.next = node
            tail = node
    return head


def list_to_values(head: Optional[ListNode]) -> List[int]:
    out: List[int] = []
    while head is not None:
        out.append(head.value)
        head = head.next
    return out


def merge_k_sorted_lists(lists: List[Optional[ListNode]]) -> Optional[ListNode]:
    """Heap entries: (value, list_index, node). list_index keeps ties stable
    and gives the heap a total order."""
    heap: list = []
    for idx, h in enumerate(lists):
        if h is not None:
            heap.append((h.value, idx, h))
            _sift_up(heap, len(heap) - 1)

    dummy = ListNode(0)
    tail = dummy
    while heap:
        _, idx, node = heap[0]
        tail.next = node
        tail = node
        last = heap.pop()
        if len(heap):
            heap[0] = last
            _sift_down(heap, 0)
        nxt = node.next
        if nxt is not None:
            heap.append((nxt.value, idx, nxt))
            _sift_up(heap, len(heap) - 1)
    return dummy.next


def k_sorted_arrays_merge(arrays: Sequence[Sequence[int]]) -> List[int]:
    heap: list = []
    for idx, arr in enumerate(arrays):
        if arr:
            heap.append((arr[0], idx, 0))
            _sift_up(heap, len(heap) - 1)

    out: List[int] = []
    while heap:
        val, idx, pos = heap[0]
        out.append(val)
        last = heap.pop()
        if heap:
            heap[0] = last
            _sift_down(heap, 0)
        pos += 1
        if pos < len(arrays[idx]):
            heap.append((arrays[idx][pos], idx, pos))
            _sift_up(heap, len(heap) - 1)
    return out


def smallest_range_covering_k_lists(lists: Sequence[Sequence[int]]) -> Tuple[int, int]:
    import heapq
    heap = [(arr[0], i, 0) for i, arr in enumerate(lists) if arr]
    heapq.heapify(heap)
    if not heap:
        raise ValueError("need at least one non-empty list")
    best_lo, best_hi = heap[0][0], max(h[0] for h in heap)
    while True:
        lo, i, pos = heap[0]
        hi = max(h[0] for h in heap)
        if hi - lo < best_hi - best_lo or (hi - lo == best_hi - best_lo and lo < best_lo):
            best_lo, best_hi = lo, hi
        pos += 1
        if pos >= len(lists[i]):
            return (best_lo, best_hi)
        heapq.heapreplace(heap, (lists[i][pos], i, pos))


def external_sort(records: List[int], chunk_capacity: int) -> List[int]:
    if chunk_capacity < 1:
        raise ValueError("chunk_capacity must be >= 1")
    if not records:
        return []
    chunks = [sorted(records[i:i + chunk_capacity])
              for i in range(0, len(records), chunk_capacity)]
    return k_sorted_arrays_merge(chunks)
