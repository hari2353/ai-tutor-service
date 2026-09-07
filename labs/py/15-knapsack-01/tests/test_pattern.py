"""Lab 15 tests — 0/1 knapsack. Deterministic; timing only in the witness."""
import itertools
import random
import time

import pytest


# ------------------------------------------------------------------ knapsack core
def test_knapsack_classic(P):
    w = [1, 3, 4, 5]
    v = [1, 4, 5, 7]
    assert P.knapsack_2d(w, v, 7) == 9


def test_knapsack_one_item_fits(P):
    assert P.knapsack_2d([2], [10], 5) == 10


def test_knapsack_one_item_too_heavy(P):
    assert P.knapsack_2d([6], [10], 5) == 0


def test_knapsack_empty_items(P):
    assert P.knapsack_2d([], [], 10) == 0
    assert P.knapsack_1d([], [], 10) == 0


def test_knapsack_zero_capacity(P):
    assert P.knapsack_2d([1, 2], [5, 5], 0) == 0
    assert P.knapsack_1d([1, 2], [5, 5], 0) == 0


def test_knapsack_exact_fit_all_items(P):
    assert P.knapsack_2d([1, 2, 3], [10, 20, 30], 6) == 60


def test_knapsack_all_same(P):
    assert P.knapsack_2d([2, 2, 2, 2], [5, 5, 5, 5], 6) == 15


def test_knapsack_1d_matches_2d_randomized(P):
    rng = random.Random(1)
    for _ in range(40):
        n = rng.randrange(0, 12)
        weights = [rng.randrange(1, 15) for _ in range(n)]
        values = [rng.randrange(1, 30) for _ in range(n)]
        cap = rng.randrange(0, 40)
        assert P.knapsack_1d(weights, values, cap) == P.knapsack_2d(weights, values, cap)


def test_knapsack_matches_bruteforce(P):
    rng = random.Random(2)
    for _ in range(15):
        n = rng.randrange(0, 10)
        weights = [rng.randrange(1, 12) for _ in range(n)]
        values = [rng.randrange(1, 25) for _ in range(n)]
        cap = rng.randrange(0, 30)
        best = 0
        for mask in itertools.product([0, 1], repeat=n):
            tw = sum(w for w, b in zip(weights, mask) if b)
            tv = sum(v for v, b in zip(values, mask) if b)
            if tw <= cap:
                best = max(best, tv)
        assert P.knapsack_1d(weights, values, cap) == best


def test_knapsack_1d_survives_big_capacity(P):
    """The 2D table would need n*W cells; 1D needs W. A capacity of 200000
    with 30 items must return fast (spot-checks the memory profile)."""
    weights = [i % 97 + 1 for i in range(30)]
    values = [i % 41 + 1 for i in range(30)]
    t0 = time.perf_counter()
    v1 = P.knapsack_1d(weights, values, 200_000)
    dt = time.perf_counter() - t0
    assert v1 == P.knapsack_2d(weights, values, 200_000)
    assert dt < 2.0


# ------------------------------------------------------------------ subset sum
def test_subset_sum_basic(P):
    assert P.subset_sum([1, 2, 3, 7], 6) is True
    assert P.subset_sum([1, 2, 3, 7], 100) is False


def test_subset_sum_zero_target(P):
    assert P.subset_sum([1, 2, 3], 0) is True       # the empty subset
    assert P.subset_sum([], 0) is True


def test_subset_sum_negative_target(P):
    assert P.subset_sum([1, 2, 3], -1) is False


def test_subset_sum_empty_nums(P):
    assert P.subset_sum([], 5) is False


def test_subset_sum_all_must_be_used(P):
    assert P.subset_sum([2, 4, 6], 12) is True      # everything
    assert P.subset_sum([2, 4, 6], 11) is False


def test_subset_sum_single_element(P):
    assert P.subset_sum([5], 5) is True
    assert P.subset_sum([6], 5) is False


# ------------------------------------------------------------------ partition
def test_partition_classic_true(P):
    assert P.partition_equal_subset_sum([1, 5, 11, 5]) is True


def test_partition_false(P):
    assert P.partition_equal_subset_sum([1, 2, 3, 5]) is False


def test_partition_odd_total(P):
    assert P.partition_equal_subset_sum([1, 2, 4]) is False   # total 7


def test_partition_empty(P):
    assert P.partition_equal_subset_sum([]) is True     # two empty halves


def test_partition_single(P):
    assert P.partition_equal_subset_sum([4]) is False
    assert P.partition_equal_subset_sum([0]) is True


def test_partition_all_equal(P):
    assert P.partition_equal_subset_sum([7, 7, 7, 7]) is True


# ------------------------------------------------------------------ target count
def test_target_count_basic(P):
    # subsets of [1,1,1,1] summing to 2: C(4,2) = 6
    assert P.target_count([1, 1, 1, 1], 2) == 6


def test_target_count_zero_items(P):
    assert P.target_count([], 0) == 1
    assert P.target_count([], 5) == 0


def test_target_count_negative_target(P):
    assert P.target_count([1, 2], -3) == 0


def test_target_count_mixed(P):
    # subsets of [1,2,3] summing to 3: {3}, {1,2} → 2
    assert P.target_count([1, 2, 3], 3) == 2


def test_target_count_full_sum_only(P):
    assert P.target_count([2, 3], 5) == 1
    assert P.target_count([2, 3], 4) == 0


def test_target_count_matches_bruteforce(P):
    rng = random.Random(3)
    for _ in range(20):
        n = rng.randrange(0, 10)
        nums = [rng.randrange(0, 9) for _ in range(n)]
        target = rng.randrange(0, 20)
        brute = sum(1 for mask in itertools.product([0, 1], repeat=n)
                    if sum(x for x, b in zip(nums, mask) if b) == target)
        assert P.target_count(nums, target) == brute


# ------------------------------------------------------------------ complexity witness
def test_subset_sum_dp_beats_bruteforce_witness(P):
    """DP is O(n·target); subset enumeration is O(2^n). At n=22 the DP must
    finish; the enumeration is the timed baseline — DP must be faster."""
    rng = random.Random(4)
    n = 22
    nums = [rng.randrange(1, 40) for _ in range(n)]
    target = sum(nums) // 2

    t0 = time.perf_counter()
    dp_res = P.subset_sum(nums, target)
    t_dp = time.perf_counter() - t0

    t0 = time.perf_counter()
    brute_res = any(sum(c for c in comb) == target
                    for r in range(n + 1)
                    for comb in itertools.combinations(nums, r))
    t_brute = time.perf_counter() - t0

    assert dp_res == brute_res
    assert t_dp < t_brute, (
        f"DP {t_dp:.3f}s vs enumeration {t_brute:.3f}s at n=22 — "
        "the O(n·target) path must win"
    )


def test_knapsack_1d_linear_capacity_witness(P):
    """n=200, W=50000 → 10M cell updates. The witness is ASYMPTOTIC: the
    O(n*W) DP must finish this in seconds where enumeration is impossible.
    5s is the ceiling so slow/loaded machines don't flake; a solution that
    accidentally reverts to exponential time still blows far past it."""
    rng = random.Random(5)
    weights = [rng.randrange(1, 300) for _ in range(200)]
    values = [rng.randrange(1, 1000) for _ in range(200)]
    t0 = time.perf_counter()
    P.knapsack_1d(weights, values, 50_000)
    dt = time.perf_counter() - t0
    assert dt < 5.0
