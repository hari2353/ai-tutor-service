"""Lab 15 — 0/1 knapsack. Fill in every TODO. Tests define done.

Rules:
  * knapsack_1d: inner loop runs DOWN from capacity to weight. Ascending = unbounded.
  * No floating point, no input sorting. Pure integer DP.
  * Edge cases are part of the contract: empty items, 0 capacity, negative target.
"""
from __future__ import annotations

from typing import List


def knapsack_2d(weights: List[int], values: List[int], capacity: int) -> int:
    """Max total value, each item at most once.

    dp[i][w] = best value using the first i items with capacity w.
    O(n * W) time and space.
    """
    raise NotImplementedError


def knapsack_1d(weights: List[int], values: List[int], capacity: int) -> int:
    """Same result as knapsack_2d, but O(W) space.

    The inner loop MUST go DOWN from capacity to weights[i]: ascending would
    let one item be counted twice (see lab 16 for why that is a *different*
    problem).
    """
    raise NotImplementedError


def subset_sum(nums: List[int], target: int) -> bool:
    """True iff some subset of nums sums exactly to target. target < 0 -> False."""
    raise NotImplementedError


def partition_equal_subset_sum(nums: List[int]) -> bool:
    """True iff nums splits into two subsets with equal sums."""
    raise NotImplementedError


def target_count(nums: List[int], target: int) -> int:
    """Count subsets summing exactly to target.

    Edge cases: target_count([], 0) == 1 (the empty subset); ([], k) == 0.
    """
    raise NotImplementedError
