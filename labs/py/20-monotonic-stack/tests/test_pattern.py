"""Lab 20 tests — monotonic stack. Deterministic; timing only in the witness."""
import random
import time

import pytest


# ------------------------------------------------------------------ next/prev greater
def test_next_greater_basic(P):
    assert P.next_greater_element([2, 1, 3, 2, 5]) == [3, 3, 5, 5, -1]


def test_next_greater_all_descending(P):
    assert P.next_greater_element([5, 4, 3, 2, 1]) == [-1, -1, -1, -1, -1]


def test_next_greater_all_ascending(P):
    assert P.next_greater_element([1, 2, 3, 4]) == [2, 3, 4, -1]


def test_next_greater_empty_and_single(P):
    assert P.next_greater_element([]) == []
    assert P.next_greater_element([7]) == [-1]


def test_next_greater_all_duplicates(P):
    """Strictly greater: duplicates never qualify."""
    assert P.next_greater_element([3, 3, 3]) == [-1, -1, -1]
    assert P.next_greater_element([2, 3, 3, 4]) == [3, 4, 4, -1]


def test_previous_greater_basic(P):
    assert P.previous_greater_element([2, 1, 3, 2, 5]) == [-1, 2, -1, 3, -1]


def test_previous_greater_descending(P):
    assert P.previous_greater_element([5, 4, 3]) == [-1, 5, 4]


def test_previous_greater_matches_bruteforce(P):
    rng = random.Random(1)
    for _ in range(50):
        nums = [rng.randrange(0, 20) for _ in range(rng.randrange(0, 25))]
        brute = [-1] * len(nums)
        for i in range(len(nums)):
            for j in range(i - 1, -1, -1):
                if nums[j] > nums[i]:
                    brute[i] = nums[j]
                    break
        assert P.previous_greater_element(nums) == brute


# ------------------------------------------------------------------ temperatures
def test_daily_temperatures_leetcode(P):
    assert P.daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73]) == \
        [1, 1, 4, 2, 1, 1, 0, 0]


def test_daily_temperatures_all_warmer(P):
    assert P.daily_temperatures([50, 51, 52]) == [1, 1, 0]


def test_daily_temperatures_never_warmer(P):
    assert P.daily_temperatures([90, 80, 70]) == [0, 0, 0]


def test_daily_temperatures_empty(P):
    assert P.daily_temperatures([]) == []


def test_daily_temperatures_single(P):
    assert P.daily_temperatures([42]) == [0]


# ------------------------------------------------------------------ histogram
def test_histogram_classic(P):
    assert P.largest_rectangle_in_histogram([2, 1, 5, 6, 2, 3]) == 10


def test_histogram_single_bar(P):
    assert P.largest_rectangle_in_histogram([7]) == 7


def test_histogram_empty(P):
    assert P.largest_rectangle_in_histogram([]) == 0


def test_histogram_all_same(P):
    assert P.largest_rectangle_in_histogram([4, 4, 4, 4]) == 16


def test_histogram_valley(P):
    assert P.largest_rectangle_in_histogram([5, 0, 5]) == 5


def test_histogram_ascending(P):
    assert P.largest_rectangle_in_histogram([1, 2, 3, 4, 5]) == 9


def test_histogram_matches_bruteforce(P):
    rng = random.Random(2)
    for _ in range(40):
        hs = [rng.randrange(0, 12) for _ in range(rng.randrange(1, 15))]
        best = 0
        for i in range(len(hs)):
            lo = hs[i]
            for j in range(i, len(hs)):
                lo = min(lo, hs[j])
                best = max(best, lo * (j - i + 1))
        assert P.largest_rectangle_in_histogram(hs) == best


# ------------------------------------------------------------------ maximal square
def test_maximal_square_basic(P):
    matrix = [["1", "0", "1", "0", "0"],
              ["1", "0", "1", "1", "1"],
              ["1", "1", "1", "1", "1"],
              ["1", "0", "0", "1", "0"]]
    assert P.maximal_square(matrix) == 4


def test_maximal_square_all_zeros(P):
    assert P.maximal_square([["0", "0"], ["0", "0"]]) == 0


def test_maximal_square_all_ones(P):
    assert P.maximal_square([["1"] * 4 for _ in range(3)]) == 9   # 3x3 fits


def test_maximal_square_int_matrix(P):
    assert P.maximal_square([[1, 1], [1, 1]]) == 4


def test_maximal_square_single_cell(P):
    assert P.maximal_square([["1"]]) == 1
    assert P.maximal_square([["0"]]) == 0


def test_maximal_square_empty(P):
    assert P.maximal_square([]) == 0


# ------------------------------------------------------------------ maximal rectangle
def test_maximal_rectangle_classic(P):
    matrix = [["1", "0", "1", "0", "0"],
              ["1", "0", "1", "1", "1"],
              ["1", "1", "1", "1", "1"],
              ["1", "0", "0", "1", "0"]]
    assert P.maximal_rectangle(matrix) == 6


def test_maximal_rectangle_tall_column(P):
    matrix = [["1"], ["1"], ["1"]]
    assert P.maximal_rectangle(matrix) == 3


def test_maximal_rectangle_empty(P):
    assert P.maximal_rectangle([]) == 0


def test_maximal_rectangle_all_zeros(P):
    assert P.maximal_rectangle([["0", "0"], ["0", "0"]]) == 0


def test_maximal_rectangle_ints_and_l_shape(P):
    matrix = [[1, 1, 0],
              [1, 1, 1],
              [0, 1, 1]]
    assert P.maximal_rectangle(matrix) == 4


# ------------------------------------------------------------------ stock span
def test_stock_span_basic(P):
    assert P.stock_span([100, 80, 60, 70, 60, 75, 85]) == [1, 1, 1, 2, 1, 4, 6]


def test_stock_span_all_ascending(P):
    assert P.stock_span([1, 2, 3, 4]) == [1, 2, 3, 4]


def test_stock_span_all_descending(P):
    assert P.stock_span([4, 3, 2, 1]) == [1, 1, 1, 1]


def test_stock_span_equal_prices_chain(P):
    # equal prices: <= counts, so spans accumulate
    assert P.stock_span([5, 5, 5]) == [1, 2, 3]


def test_stock_span_empty(P):
    assert P.stock_span([]) == []


# ------------------------------------------------------------------ complexity witness
def _brute_nge(nums):
    return [next((nums[j] for j in range(i + 1, len(nums)) if nums[j] > nums[i]), -1)
            for i in range(len(nums))]


def test_nge_linear_vs_quadratic_witness(P):
    """The stack scans once; the brute force re-scans for every element.
    n = 30000: stack must beat brute and stay under 2s."""
    rng = random.Random(3)
    n = 30_000
    nums = [rng.randrange(0, 10**6) for _ in range(n)]

    t0 = time.perf_counter()
    fast = P.next_greater_element(nums)
    t_fast = time.perf_counter() - t0

    t0 = time.perf_counter()
    brute = _brute_nge(nums)
    t_brute = time.perf_counter() - t0

    assert fast == brute
    assert t_fast < 2.0
    assert t_fast < t_brute, (
        f"stack {t_fast:.2f}s vs brute {t_brute:.2f}s — the O(n) path must win"
    )


def test_histogram_linear_witness(P):
    """n = 200k bars: the stack histogram scan must stay under 2s."""
    rng = random.Random(4)
    hs = [rng.randrange(1, 1000) for _ in range(200_000)]
    t0 = time.perf_counter()
    area = P.largest_rectangle_in_histogram(hs)
    dt = time.perf_counter() - t0
    assert area > 0
    assert dt < 2.0
