"""Lab 16 — unbounded knapsack. Reference solution."""
from __future__ import annotations

from typing import List


def unbounded_knapsack(weights: List[int], values: List[int], capacity: int) -> int:
    if capacity <= 0 or not weights:
        return 0
    dp = [0] * (capacity + 1)
    for w, v in zip(weights, values):
        for cap in range(w, capacity + 1):         # FORWARD — reuse enabled
            cand = dp[cap - w] + v
            if cand > dp[cap]:
                dp[cap] = cand
    return dp[capacity]


def coin_change(coins: List[int], amount: int) -> int:
    if amount < 0:
        return -1
    if amount == 0:
        return 0
    usable = [c for c in coins if c > 0]
    if not usable:
        return -1
    INF = amount + 1
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in usable:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return dp[amount] if dp[amount] <= amount else -1


def coin_change_ii(coins: List[int], amount: int) -> int:
    usable = [c for c in coins if c > 0]
    dp = [1] + [0] * max(amount, 0)
    for c in usable:                                # coins OUTER — combinations
        for a in range(c, amount + 1):
            dp[a] += dp[a - c]
    return dp[amount]


def rod_cutting(prices: List[int], length: int) -> int:
    if length <= 0 or not prices:
        return 0
    dp = [0] * (length + 1)
    for cap in range(1, length + 1):
        best = 0
        for piece in range(1, min(cap, len(prices)) + 1):
            best = max(best, prices[piece - 1] + dp[cap - piece])
        dp[cap] = best
    return dp[length]


def integer_break(n: int) -> int:
    if n < 2:
        raise ValueError("integer_break is defined for n >= 2")
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        for j in range(1, i):
            # either don't break j further, or take its best sub-break
            dp[i] = max(dp[i], j * (i - j), j * dp[i - j])
    return dp[n]
