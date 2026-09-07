"""Lab 12 — XOR patterns. Reference solution."""
from __future__ import annotations

from typing import List, Tuple


def single_number(nums: List[int]) -> int:
    x = 0
    for v in nums:
        x ^= v
    return x


def single_number_iii(nums: List[int]) -> Tuple[int, int]:
    x = 0
    for v in nums:
        x ^= v
    diff = x & -x                     # lowest set bit: a and b differ here
    a = b = 0
    for v in nums:
        if v & diff:
            a ^= v
        else:
            b ^= v
    return (a, b) if a <= b else (b, a)


def missing_number(nums: List[int]) -> int:
    x = 0
    for i, v in enumerate(nums):       # XOR 0..n-1 (indices) against the values
        x ^= i ^ v
    return x ^ len(nums)               # fold in the last index n


def build_xor_list(values: List[int]) -> Tuple[int, dict]:
    memory: dict = {}
    if not values:
        return 0, memory
    prev = 0
    head = 1
    for i, v in enumerate(values, start=1):
        nxt = i + 1 if i < len(values) else 0
        memory[i] = (v, prev ^ nxt)
        prev = i
    return head, memory


def _walk(head: int, memory: dict, steps: int) -> int:
    prev, cur = 0, head
    for _ in range(steps):
        _, both = memory[cur]
        prev, cur = cur, prev ^ both
    return cur


def xor_list_to_list(head: int, memory: dict) -> List[int]:
    out: List[int] = []
    prev, cur = 0, head
    while cur:
        v, both = memory[cur]
        out.append(v)
        prev, cur = cur, prev ^ both
    return out


def xor_get_nth(head: int, memory: dict, i: int) -> int:
    return memory[_walk(head, memory, i)][0]


def count_bits(n: int) -> int:
    c = 0
    while n:
        n &= n - 1
        c += 1
    return c


def parity(n: int) -> int:
    return count_bits(n) & 1
