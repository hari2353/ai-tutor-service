"""Lab 16 — unbounded knapsack. Fill in every TODO. Tests define done.

Rules:
  * Inner loops run FORWARD (ascending) — reuse is the point.
  * Pure integer DP. No floats, no recursion-without-memo, no input sorting
    except where the algorithm genuinely needs sorted input (integer_break
    does not).
  * Edge cases are the contract: amount 0, empty coins, unbreakable amounts.
"""
from __future__ import annotations

from typing import List


def unbounded_knapsack(weights: List[int], values: List[int], capacity: int) -> int:
    """Max value, each item usable any number of times.

    dp[w] = best value with capacity exactly w (allowing reuse).
    Inner loop ASCENDS: dp[w - weight] may already include this item.
    """
    raise NotImplementedError


def coin_change(coins: List[int], amount: int) -> int:
    """Fewest coins summing to amount; -1 if impossible. amount 0 -> 0."""
    raise NotImplementedError


def coin_change_ii(coins: List[int], amount: int) -> int:
    """Number of order-independent combinations summing to amount.

    coin_change_ii([], 0) == 1. Coins <= 0 are ignored. Standard trap: if you
    loop amounts outer / coins inner you count permutations, not combinations.
    """
    raise NotImplementedError


def rod_cutting(prices: List[int], length: int) -> int:
    """prices[i] = value of a piece of length i+1. Maximize value of a rod
    of `length`, cuts free, any number of pieces. length 0 -> 0."""
    raise NotImplementedError


def integer_break(n: int) -> int:
    """Split n >= 2 into >= 2 positive integers maximizing their product.

    integer_break(2) == 1, integer_break(10) == 36 (3+3+4).
    """
    raise NotImplementedError
