"""Lab 25 — greedy + exchange arguments. Reference solution."""
from __future__ import annotations

from collections import Counter
from typing import List, Tuple


def interval_schedule(intervals: List[Tuple[int, int]]) -> int:
    """Sort by finish; take any interval starting at/after the last finish.

    Exchange: OPT's first pick finishing later can be swapped for the
    earliest-finishing pick one-for-one — still feasible, same count. Induct.
    O(n log n) for the sort, O(n) for the scan.
    """
    count = 0
    last = float("-inf")
    for s, e in sorted(intervals, key=lambda iv: (iv[1], iv[0])):
        if s >= last:                 # half-open: touching intervals are fine
            count += 1
            last = e
    return count


def jump_game(nums: List[int]) -> bool:
    """Track farthest reachable; False the moment the scan index outruns it.

    Reachability is monotone — nothing is ever chosen, so nothing can be
    exchanged away. O(n), O(1) space.
    """
    farthest = 0
    for i, reach in enumerate(nums):
        if i > farthest:
            return False
        if i + reach > farthest:
            farthest = i + reach
    return True


def jump_game_min(nums: List[int]) -> int:
    """Greedy layer expansion — one jump per BFS-like level.

    Exchange: any optimal route's k-th jump lands within greedy's k-th level,
    and landing anywhere in a level leaves remaining reach at least as large
    as the frontier. Count one jump per level. O(n), O(1) space.
    """
    n = len(nums)
    if n <= 1:
        return 0
    jumps = 0
    level_end = 0                     # last index of the current level
    farthest = 0
    i = 0
    while level_end < n - 1:
        jumps += 1
        while i <= level_end:         # walk this level, extend the frontier
            if i + nums[i] > farthest:
                farthest = i + nums[i]
            i += 1
        if farthest <= level_end:     # frontier never advances: stuck
            return -1
        level_end = farthest
    return jumps


def gas_station(gas: List[int], cost: List[int]) -> int:
    """One pass; reset candidate start whenever the tank dips negative.

    Exchange: if start i fails first at j, every k in (i, j] reaches j with
    <= the fuel i had — so all of i..j are dead starts; jump to j+1. Feasible
    iff total gas >= total cost. O(n), O(1) space.
    """
    total = tank = 0
    start = 0
    for i, (g, c) in enumerate(zip(gas, cost)):
        delta = g - c
        total += delta
        tank += delta
        if tank < 0:                   # i..j all impossible — skip them
            start = i + 1
            tank = 0
    return start if total >= 0 else -1


def task_scheduler(tasks: List[str], n: int) -> int:
    """Simulate one tick at a time; run the most-remaining available task.

    Exchange: where an optimal schedule runs another available task, swap in
    the most-remaining one — cooldowns stay satisfied and the makespan
    cannot grow, since deferring the most frequent task is what creates
    idle tail slots. O(T log 26) ≈ O(T). Agrees with the closed formula
    max(len, (max_freq-1)*(n+1) + count_of_max_freq) — the tests check both.
    """
    remaining = Counter(tasks)
    last_run = {}                      # task -> tick it last ran
    t = 0
    while remaining:
        avail = [tk for tk in remaining
                 if tk not in last_run or t >= last_run[tk] + n + 1]
        if not avail:                 # everyone cooling down: idle tick
            t += 1
            continue
        # largest remaining count; deterministic tie-break: alphabetical
        tk = max(avail, key=lambda x: (remaining[x], x))
        remaining[tk] -= 1
        if remaining[tk] == 0:
            del remaining[tk]
        last_run[tk] = t
        t += 1
    return t


def fractional_knapsack(capacity: float, items: List[Tuple[float, float]]) -> float:
    """Sort by value/weight ratio; fill, splitting the last item if needed.

    Exchange: any unit of capacity OPT fills with lower-ratio material while
    a higher-ratio item has weight left can be swapped unit-for-unit — same
    weight, value not worse. Induct over units: greedy is optimal. O(n log n).
    """
    total = 0.0
    remaining = capacity
    for w, v in sorted(items, key=lambda it: it[1] / it[0], reverse=True):
        if remaining <= 0:
            break
        take = min(w, remaining)
        total += v * take / w
        remaining -= take
    return total


def knapsack_01(capacity: int, items: List[Tuple[int, int]]) -> int:
    """1D rolling DP, inner loop DOWN so each item is used at most once.

    No exchange argument exists: atomic items can't be swapped in units, and
    whole-for-whole swaps can breach capacity — so local ratio choices can't
    be repaired, and both branches (take/skip) must be explored. O(n * W)
    time, O(W) space, pseudo-polynomial.
    """
    dp = [0] * (capacity + 1)
    for w, v in items:
        for c in range(capacity, w - 1, -1):
            if dp[c - w] + v > dp[c]:
                dp[c] = dp[c - w] + v
    return dp[capacity]


def greedy_knapsack_01(capacity: int, items: List[Tuple[int, int]]) -> int:
    """Ratio greedy on indivisible items — WRONG BY DESIGN, the failure witness.

    capacity=50, [(10,60),(20,100),(30,120)] -> takes 160, optimal is 220.
    """
    total = 0
    remaining = capacity
    for w, v in sorted(items, key=lambda it: it[1] / it[0], reverse=True):
        if w <= remaining:
            total += v
            remaining -= w
    return total
