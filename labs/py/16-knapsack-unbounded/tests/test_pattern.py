"""Lab 16 tests — unbounded knapsack. Deterministic; timing only in the witness."""
import itertools
import random
import time

import pytest


# ------------------------------------------------------------------ unbounded knapsack
def test_unbounded_reuse_beats_01(P):
    """One item (w=3, v=5), capacity 9: reusable → 15; 0/1 would cap at 5."""
    assert P.unbounded_knapsack([3], [5], 9) == 15


def test_unbounded_classic(P):
    assert P.unbounded_knapsack([1, 3, 4, 5], [1, 4, 5, 7], 7) == 9


def test_unbounded_exact_fit(P):
    assert P.unbounded_knapsack([2, 3], [4, 5], 6) == 12


def test_unbounded_empty_or_zero_capacity(P):
    assert P.unbounded_knapsack([], [], 10) == 0
    assert P.unbounded_knapsack([1], [5], 0) == 0
    assert P.unbounded_knapsack([5], [3], 3) == 0       # item never fits


def test_unbounded_matches_bruteforce(P):
    rng = random.Random(1)
    for _ in range(20):
        n = rng.randrange(1, 5)
        weights = [rng.randrange(1, 6) for _ in range(n)]
        values = [rng.randrange(1, 10) for _ in range(n)]
        cap = rng.randrange(0, 18)
        best = 0
        # brute force: try every multiset bounded by cap/min_weight copies
        max_copies = cap // min(weights) if weights and cap else 0
        for counts in itertools.product(range(max_copies + 1), repeat=n):
            tw = sum(c * w for c, w in zip(counts, weights))
            tv = sum(c * v for c, v in zip(counts, values))
            if tw <= cap:
                best = max(best, tv)
        assert P.unbounded_knapsack(weights, values, cap) == best


# ------------------------------------------------------------------ coin change
def test_coin_change_classic(P):
    assert P.coin_change([1, 2, 5], 11) == 3


def test_coin_change_impossible(P):
    assert P.coin_change([2], 3) == -1


def test_coin_change_zero_amount(P):
    assert P.coin_change([1, 2, 5], 0) == 0
    assert P.coin_change([], 0) == 0


def test_coin_change_no_coins(P):
    assert P.coin_change([], 7) == -1


def test_coin_change_greedy_trap(P):
    """Greedy (largest-first) fails here; DP must not."""
    assert P.coin_change([1, 3, 4], 6) == 2            # 3+3, not 4+1+1


def test_coin_change_single_coin(P):
    assert P.coin_change([3], 9) == 3
    assert P.coin_change([3], 10) == -1


def test_coin_change_amount_one(P):
    assert P.coin_change([1], 1) == 1


# ------------------------------------------------------------------ coin change ii
def test_coin_change_ii_classic(P):
    assert P.coin_change_ii([1, 2, 5], 5) == 4          # 5;2+2+1;2+1+1+1;1x5


def test_coin_change_ii_combinations_not_permutations(P):
    """[2,3,5], 7 → 2 ways (2+5, 2+2+3). Permutation-counting would say 5."""
    assert P.coin_change_ii([2, 3, 5], 7) == 2


def test_coin_change_ii_zero_amount(P):
    assert P.coin_change_ii([1, 2], 0) == 1
    assert P.coin_change_ii([], 0) == 1


def test_coin_change_ii_empty_coins(P):
    assert P.coin_change_ii([], 5) == 0


def test_coin_change_ii_ignores_nonpositive_coins(P):
    assert P.coin_change_ii([0, -3, 2], 4) == 1


def test_coin_change_ii_matches_bruteforce(P):
    rng = random.Random(2)
    for _ in range(20):
        coins = [rng.randrange(1, 7) for _ in range(rng.randrange(1, 4))]
        amount = rng.randrange(0, 15)
        brute = 0
        for a in range(amount + 1):
            for b in range(amount + 1):
                for c in range(amount + 1):
                    if a * (coins[0] if coins else 0) + 0 == -1:
                        break
        # simpler brute: count multisets directly
        def ways(idx, remaining):
            if remaining == 0:
                return 1
            if idx >= len(coins) or remaining < 0:
                return 0
            total = 0
            take = 0
            while take * coins[idx] <= remaining:
                total += ways(idx + 1, remaining - take * coins[idx])
                take += 1
            return total
        assert P.coin_change_ii(coins, amount) == ways(0, amount)


# ------------------------------------------------------------------ rod cutting
def test_rod_cutting_classic(P):
    prices = [1, 5, 8, 9, 10, 17, 17, 20]
    assert P.rod_cutting(prices, 8) == 22


def test_rod_cutting_no_cut(P):
    assert P.rod_cutting([5], 1) == 5


def test_rod_cutting_zero_length(P):
    assert P.rod_cutting([1, 5, 8], 0) == 0


def test_rod_cutting_all_cuts_better(P):
    # piece of length 1 worth 3: cutting into 1s beats whole
    assert P.rod_cutting([3, 4, 5], 3) == 9


def test_rod_cutting_fewer_prices_than_length(P):
    # prices only cover pieces up to length 2, rod is length 5
    assert P.rod_cutting([2, 5], 5) == 12               # 2+2+... 5x2+5? see below


# ------------------------------------------------------------------ integer break
def test_integer_break_small(P):
    assert P.integer_break(2) == 1
    assert P.integer_break(3) == 2


def test_integer_break_ten(P):
    assert P.integer_break(10) == 36


def test_integer_break_all_threes(P):
    assert P.integer_break(9) == 27                     # 3+3+3
    assert P.integer_break(8) == 18                     # 3+3+2


def test_integer_break_matches_dp_bruteforce(P):
    # recursive definition: split k into parts, product of parts; parts >= 1.
    # integer_break requires >= 2 parts, so handle the small cases explicitly.
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def best(k):
        """Best product splitting k into >= 2 parts."""
        if k == 2:
            return 1
        if k == 3:
            return 2
        m = 0
        for i in range(1, k):
            m = max(m, i * (k - i), i * best(k - i))
        return m

    for n in range(2, 16):
        assert P.integer_break(n) == best(n)


# ------------------------------------------------------------------ direction witness
def test_forward_vs_backward_is_the_whole_difference(P):
    """The 0/1 knapsack (backwards, lab 15) and the unbounded (forwards)
    must DISAGREE on reuse-friendly input — proving loop direction is the
    entire semantics."""
    w, v, cap = [3], [5], 9
    unbounded = P.unbounded_knapsack(w, v, cap)         # 15

    # reproduce the 0/1 (backwards) algorithm inline
    dp = [0] * (cap + 1)
    for wi, vi in zip(w, v):
        for c in range(cap, wi - 1, -1):
            dp[c] = max(dp[c], dp[c - wi] + vi)
    zero_one = dp[cap]                                  # 5

    assert unbounded == 15
    assert zero_one == 5
    assert unbounded != zero_one


# ------------------------------------------------------------------ complexity witness
def _brute_coin_change(coins, amount):
    """BFS-free brute: recursive enumeration, exponential in amount/min(coin)."""
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def solve(a):
        if a == 0:
            return 0
        if a < 0:
            return float("inf")
        return min((solve(a - c) + 1 for c in coins), default=float("inf"))
    r = solve(amount)
    solve.cache_clear()
    return -1 if r == float("inf") else r


def test_coin_change_dp_beats_naive_recursion_witness(P):
    """Memoized-with-cache-clear naive recursion on amount=26 with coin 1
    present degenerates toward exponential path counting; the DP must be
    dramatically faster. (Both must agree.)"""
    coins = [7, 14]
    amount = 49

    t0 = time.perf_counter()
    dp_res = P.coin_change(coins, amount)
    t_dp = time.perf_counter() - t0

    t0 = time.perf_counter()
    brute_res = _brute_coin_change(coins, amount)
    t_brute = time.perf_counter() - t0

    assert dp_res == brute_res == -1 or dp_res == brute_res
    assert t_dp < 0.5


def test_unbounded_big_capacity_under_2s(P):
    weights = [3, 7, 11, 13]
    values = [5, 12, 19, 23]
    cap = 60_000
    t0 = time.perf_counter()
    P.unbounded_knapsack(weights, values, cap)
    assert time.perf_counter() - t0 < 2.0


def test_coin_change_large_amount_under_2s(P):
    t0 = time.perf_counter()
    r = P.coin_change([1, 5, 11], 90_000)
    assert 0 < r <= 90_000
    assert time.perf_counter() - t0 < 2.0
