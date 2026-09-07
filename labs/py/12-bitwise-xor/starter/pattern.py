"""Lab 12 — XOR patterns. Fill in every TODO. Tests define done.

Rules:
  * No bin()/str conversion for bit counting — bitwise ops only.
  * single_number family must be O(n) time, O(1) extra space: no Counter, no sets, no sort.
  * The XOR linked list is simulated: memory maps node_id -> (value, both), both = prev ^ next.
"""
from __future__ import annotations

from typing import List, Tuple


def single_number(nums: List[int]) -> int:
    """Every element appears exactly twice except one; return the unpaired one.

    XOR-accumulate the whole array: pairs cancel (x^x=0), the survivor remains.
    Empty input returns 0.
    """
    raise NotImplementedError


def single_number_iii(nums: List[int]) -> Tuple[int, int]:
    """Exactly two elements appear once, everything else twice.

    XOR of all = a^b. The lowest set bit of a^b separates the array into two
    groups; XOR each group separately. Return a sorted tuple (low, high).
    """
    raise NotImplementedError


def missing_number(nums: List[int]) -> int:
    """nums is a permutation of 0..len(nums) with one value missing.

    XOR 0..n together with all of nums; everything cancels except the hole.
    Empty input returns 0.
    """
    raise NotImplementedError


def build_xor_list(values: List[int]) -> Tuple[int, dict]:
    """Build a simulated XOR linked list.

    Node ids are 1..len(values); id 0 is NULL.
    memory: {node_id: (value, both)} where both = prev_id ^ next_id.
    Returns (head_id, memory); head_id is 0 for an empty list.
    """
    raise NotImplementedError


def xor_list_to_list(head: int, memory: dict) -> List[int]:
    """Traverse the XOR list from head using next = prev ^ both. Start with prev=0."""
    raise NotImplementedError


def xor_get_nth(head: int, memory: dict, i: int) -> int:
    """Value of the i-th node (0-indexed), traversing with XOR pointer arithmetic."""
    raise NotImplementedError


def count_bits(n: int) -> int:
    """Number of set bits. Kernighan: n &= n-1 clears the lowest set bit each pass.

    No bin()/format()/str tricks.
    """
    raise NotImplementedError


def parity(n: int) -> int:
    """1 if count_bits(n) is odd, else 0."""
    raise NotImplementedError
