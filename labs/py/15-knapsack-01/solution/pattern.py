"""Lab 15 — 0/1 knapsack. Reference solution."""
from __future__ import annotations

from typing import List


def knapsack_2d(weights: List[int], values: List[int], capacity: int) -> int:
    n = len(weights)
    if n == 0 or capacity <= 0:
        return 0
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w, v = weights[i - 1], values[i - 1]
        for cap in range(capacity + 1):
            dp[i][cap] = dp[i - 1][cap]
            if w <= cap:
                take = dp[i - 1][cap - w] + v
                if take > dp[i][cap]:
                    dp[i][cap] = take
    return dp[n][capacity]


def knapsack_1d(weights: List[int], values: List[int], capacity: int) -> int:
    if capacity <= 0 or not weights:
        return 0
    dp = [0] * (capacity + 1)
    for w, v in zip(weights, values):
        for cap in range(capacity, w - 1, -1):     # DOWN — 0/1, not unbounded
            cand = dp[cap - w] + v
            if cand > dp[cap]:
                dp[cap] = cand
    return dp[capacity]


def subset_sum(nums: List[int], target: int) -> bool:
    if target < 0:
        return False
    if target == 0:
        return True
    reachable = {0}
    for x in nums:
        if x < 0:
            return False                      # out of contract for this lab
        nxt = set(reachable)
        for s in reachable:
            if s + x == target:
                return True
            nxt.add(s + x)
        reachable = nxt
    return target in reachable


def partition_equal_subset_sum(nums: List[int]) -> bool:
    total = sum(nums)
    if total % 2:
        return False
    return subset_sum(nums, total // 2)


def target_count(nums: List[int], target: int) -> int:
    if target < 0:
        return 0
    # dp[s] = number of subsets with sum s, using 0/1 semantics
    dp = [0] * (target + 1)
    dp[0] = 1
    for x in nums:
        if x < 0:
            return 0
        for s in range(target, x - 1, -1):     # backwards again — 0/1
            dp[s] += dp[s - x]
    return dp[target]
