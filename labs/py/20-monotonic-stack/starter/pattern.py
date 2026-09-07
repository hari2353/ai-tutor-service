"""Lab 20 — monotonic stack. Fill in every TODO. Tests define done.

Rules:
  * O(n): every element is pushed and popped at most once. No nested scans.
  * Strictly greater for all "greater element" queries (>= is a different
    problem — think about duplicates carefully).
  * matrix rows may be "0110" strings OR [0,1,1,0] lists — accept both.
"""
from __future__ import annotations

from typing import List, Sequence, Union


def next_greater_element(nums: List[int]) -> List[int]:
    """First strictly greater value to the right of each index, else -1."""
    raise NotImplementedError


def previous_greater_element(nums: List[int]) -> List[int]:
    """First strictly greater value to the left of each index, else -1."""
    raise NotImplementedError


def daily_temperatures(temps: List[int]) -> List[int]:
    """Days until a strictly warmer day, else 0. O(n)."""
    raise NotImplementedError


def largest_rectangle_in_histogram(heights: List[int]) -> int:
    """Largest rectangle under the histogram. O(n) with a sentinel flush."""
    raise NotImplementedError


def maximal_square(matrix: Sequence[Union[str, Sequence[int]]]) -> int:
    """Largest all-1s square: return its AREA."""
    raise NotImplementedError


def maximal_rectangle(matrix: Sequence[Union[str, Sequence[int]]]) -> int:
    """Largest all-1s rectangle: return its AREA. Row-histogram compression
    + largest_rectangle_in_histogram per row."""
    raise NotImplementedError


def stock_span(prices: List[int]) -> List[int]:
    """Consecutive preceding days (inclusive) with price <= today's. O(n)."""
    raise NotImplementedError
