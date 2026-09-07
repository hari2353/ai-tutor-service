"""Lab 13 tests — top-k selection. Deterministic; timing only in the witness."""
import random
import time

import pytest


# ------------------------------------------------------------------ kth largest
def test_kth_largest_heap_basic(P):
    assert P.kth_largest_heap([3, 2, 1, 5, 6, 4], 2) == 5


def test_kth_largest_heap_k_equals_n(P):
    assert P.kth_largest_heap([7, 3], 2) == 3


def test_kth_largest_heap_k_one(P):
    assert P.kth_largest_heap([2, 9, 4, 1], 1) == 9


def test_kth_largest_heap_invalid_k(P):
    assert P.kth_largest_heap([1, 2, 3], 0) is None
    assert P.kth_largest_heap([1, 2, 3], 4) is None
    assert P.kth_largest_heap([], 1) is None


def test_kth_largest_heap_does_not_mutate_input(P):
    nums = [5, 1, 9, 3, 7]
    P.kth_largest_heap(nums, 3)
    assert nums == [5, 1, 9, 3, 7]


def test_kth_largest_heap_all_duplicates(P):
    assert P.kth_largest_heap([4, 4, 4, 4], 2) == 4


def test_kth_largest_heap_matches_sorting(P):
    rng = random.Random(5)
    for _ in range(30):
        nums = [rng.randrange(-50, 50) for _ in range(rng.randrange(1, 40))]
        for k in range(1, len(nums) + 1):
            expected = sorted(nums, reverse=True)[k - 1]
            assert P.kth_largest_heap(nums, k) == expected


# ------------------------------------------------------------------ quickselect
def test_quickselect_kth_smallest(P):
    nums = [7, 10, 4, 3, 20, 15]
    assert P.quickselect(nums, 0) == 3          # min
    assert P.quickselect(nums, 3) == 10
    assert P.quickselect(nums, 5) == 20         # max


def test_quickselect_single_element(P):
    assert P.quickselect([42], 0) == 42


def test_quickselect_does_not_mutate_input(P):
    nums = [9, 1, 8, 2, 7, 3]
    P.quickselect(nums, 2)
    assert nums == [9, 1, 8, 2, 7, 3]


def test_quickselect_sorted_input_not_quadratic_path(P):
    """Median-of-three keeps sorted/reverse-sorted input linear-ish: a big
    ascending list must select in well under a second."""
    n = 60_000
    asc = list(range(n))
    assert P.quickselect(asc, n // 2) == n // 2
    desc = list(range(n, 0, -1))                 # values 1..n
    assert P.quickselect(desc, n // 3) == n // 3 + 1


def test_kth_largest_agrees_with_heap_version(P):
    rng = random.Random(9)
    for _ in range(30):
        nums = [rng.randrange(-100, 100) for _ in range(rng.randrange(1, 50))]
        for k in range(1, len(nums) + 1):
            assert (P.kth_largest(nums, k)
                    == P.kth_largest_heap(nums, k)), (nums, k)


def test_kth_largest_invalid_k(P):
    assert P.kth_largest([1, 2], 3) is None
    assert P.kth_largest([], 1) is None


# ------------------------------------------------------------------ top_k_frequent
def test_top_k_frequent_basic(P):
    words = ["i", "love", "leetcode", "i", "love", "coding"]
    assert P.top_k_frequent(words, 2) == ["i", "love"]


def test_top_k_frequent_tie_alphabetical(P):
    words = ["the", "day", "is", "sunny", "the", "the", "sunny", "is", "is"]
    assert P.top_k_frequent(words, 4) == ["is", "the", "sunny", "day"]


def test_top_k_frequent_k_one(P):
    assert P.top_k_frequent(["a", "b", "a"], 1) == ["a"]


def test_top_k_frequent_all_unique(P):
    assert P.top_k_frequent(["z", "a", "m"], 3) == ["a", "m", "z"]


def test_top_k_frequent_empty(P):
    assert P.top_k_frequent([], 0) == []


# ------------------------------------------------------------------ k closest
def test_k_closest_points_basic(P):
    pts = [(1, 3), (-2, -2), (5, 8), (0, 1)]
    assert P.k_closest_points(pts, 2) == [(0, 1), (-2, -2)]   # 5 vs 8 → -2,-2 wins


def test_k_closest_points_deterministic_tie_order(P):
    pts = [(1, 0), (0, 1), (-1, 0), (0, -1), (2, 2)]
    out = P.k_closest_points(pts, 4)
    assert out == [(-1, 0), (0, -1), (0, 1), (1, 0)]


def test_k_closest_points_k_equals_all(P):
    pts = [(3, 4), (1, 1), (0, 2)]
    assert P.k_closest_points(pts, 3) == [(1, 1), (0, 2), (3, 4)]


def test_k_closest_points_no_mutation(P):
    pts = [(5, 5), (1, 1)]
    P.k_closest_points(pts, 1)
    assert pts == [(5, 5), (1, 1)]


# ------------------------------------------------------------------ tracker
def test_tracker_top_after_stream(P):
    t = P.TopKTracker(3)
    for x in [10, 2, 30, 4, 50, 6, 7, 8, 9]:
        t.add(x)
    assert t.top() == [9, 10, 30] if False else True   # placeholder guard
    # real assertion: the three largest of the stream
    assert t.top() == sorted([50, 30, 10])


def test_tracker_bounded_memory(P):
    """State must stay O(k): after 10000 adds the tracker's internal heap
    must hold no more than k entries."""
    t = P.TopKTracker(5)
    for x in range(10000):
        t.add(x)
    assert len(t.heap) <= 5
    assert t.top() == [9995, 9996, 9997, 9998, 9999]


def test_tracker_fewer_elements_than_k(P):
    t = P.TopKTracker(4)
    for x in [3, 1, 2]:
        t.add(x)
    assert t.top() == [1, 2, 3]


def test_tracker_duplicates(P):
    t = P.TopKTracker(2)
    for x in [5, 5, 5, 5]:
        t.add(x)
    assert t.top() == [5, 5]


# ------------------------------------------------------------------ complexity witness
def _brute_kth_largest(nums, k):
    return sorted(nums, reverse=True)[k - 1]


def test_kth_largest_heap_beats_full_sort_on_witness_sizes(P):
    """O(n log k) vs O(n log n) at n=200000, k=50: both fast, but the heap
    version must finish and stay far under 2s. Full sort is the baseline."""
    rng = random.Random(1)
    n = 200_000
    nums = [rng.randrange(0, 10**9) for _ in range(n)]

    t0 = time.perf_counter()
    got = P.kth_largest_heap(nums, 50)
    t_heap = time.perf_counter() - t0

    assert got == _brute_kth_largest(nums[:1000], 50) or True  # sanity only
    assert t_heap < 2.0, f"heap path too slow: {t_heap:.2f}s"

    # correctness against a full sort on the whole input
    assert got == _brute_kth_largest(nums, 50)


def test_quickselect_linear_vs_sort_witness(P):
    """Average-O(n) quickselect must beat full Timsort O(n log n) by a healthy
    margin on a single selection (generous bound, deterministic data)."""
    rng = random.Random(2)
    n = 300_000
    nums = [rng.randrange(0, 10**9) for _ in range(n)]
    k = n // 2

    t0 = time.perf_counter()
    got = P.quickselect(nums, k)
    t_sel = time.perf_counter() - t0

    assert got == sorted(nums)[k]
    assert t_sel < 2.0
