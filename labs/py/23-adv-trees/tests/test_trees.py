"""Lab 23 tests. Pure stdlib, seeded randomness, no sleeps."""
import random

import pytest

A = [2, 1, 5, 3, 4]


# ------------------------------------------------------------------ segment tree
def test_segment_tree_hand_computed_range_sums(T):
    st = T.SegmentTree(A)
    assert st.range_sum(0, 4) == 15
    assert st.range_sum(0, 0) == 2
    assert st.range_sum(4, 4) == 4
    assert st.range_sum(1, 3) == 1 + 5 + 3
    assert st.range_sum(2, 4) == 5 + 3 + 4
    assert st.range_sum(2, 2) == 5
    assert st.range_sum(0, 1) == 3


def test_segment_tree_point_update_changes_queries(T):
    st = T.SegmentTree(A)
    st.point_update(2, 10)
    assert st.range_sum(0, 4) == 2 + 1 + 10 + 3 + 4
    assert st.range_sum(1, 3) == 1 + 10 + 3
    assert st.range_sum(0, 2) == 13
    st.point_update(0, -5)
    assert st.range_sum(0, 4) == -5 + 1 + 10 + 3 + 4
    assert st.range_sum(0, 1) == -4
    assert st.range_sum(3, 4) == 7


def test_segment_tree_negative_and_single(T):
    st = T.SegmentTree([-3, 7, -1, 4])
    assert st.range_sum(0, 3) == 7
    assert st.range_sum(1, 2) == 6
    assert st.range_sum(0, 1) == 4
    one = T.SegmentTree([42])
    assert one.range_sum(0, 0) == 42
    one.point_update(0, -42)
    assert one.range_sum(0, 0) == -42


def test_segment_tree_random_vs_brute_force(T):
    rng = random.Random(7)
    for _ in range(5):
        vals = [rng.randint(-50, 50) for _ in range(40)]
        st = T.SegmentTree(vals)
        for _ in range(30):
            l = rng.randrange(40)
            r = rng.randrange(l, 40)
            assert st.range_sum(l, r) == sum(vals[l:r + 1])
        for _ in range(15):
            i = rng.randrange(40)
            vals[i] = rng.randint(-50, 50)
            st.point_update(i, vals[i])
            l = rng.randrange(40)
            r = rng.randrange(l, 40)
            assert st.range_sum(l, r) == sum(vals[l:r + 1])


# ------------------------------------------------------------------ lazy
def test_lazy_range_add_hand_computed(T):
    lt = T.LazySegmentTree(A)
    assert lt.range_sum(0, 4) == 15
    lt.range_add(1, 3, 10)
    assert lt.range_sum(0, 4) == 45
    assert lt.range_sum(1, 3) == 39
    assert lt.range_sum(0, 1) == 13
    assert lt.range_sum(4, 4) == 4
    assert lt.range_sum(0, 0) == 2
    lt.range_add(0, 4, -2)
    assert lt.range_sum(0, 4) == 35
    assert lt.range_sum(2, 4) == 26
    assert lt.range_sum(1, 2) == 22
    lt.range_add(2, 2, 5)
    assert lt.range_sum(0, 4) == 40
    assert lt.range_sum(2, 2) == 18
    assert lt.range_sum(0, 2) == 27


def test_lazy_range_add_vs_brute_force_seeded(T):
    rng = random.Random(42)
    for _ in range(4):
        n = 60
        vals = [rng.randint(-50, 50) for _ in range(n)]
        lt = T.LazySegmentTree(vals)
        for _ in range(80):
            if rng.random() < 0.5:
                l = rng.randrange(n)
                r = rng.randrange(l, n)
                delta = rng.randint(-20, 20)
                lt.range_add(l, r, delta)
                for i in range(l, r + 1):
                    vals[i] += delta
            l = rng.randrange(n)
            r = rng.randrange(l, n)
            assert lt.range_sum(l, r) == sum(vals[l:r + 1])


def test_lazy_scale(T):
    """2000 range-adds on 100k elements — a per-leaf lazy impl is O(n) per op."""
    rng = random.Random(99)
    n = 100_000
    vals = [rng.randint(-100, 100) for _ in range(n)]
    lt = T.LazySegmentTree(vals)
    assert lt.range_sum(0, n - 1) == sum(vals)
    lo, hi = 10, n - 10
    expect_full = sum(vals)
    expect_mid = lt.range_sum(lo, hi)
    for step in range(2000):
        l = rng.randrange(n)
        r = rng.randrange(l, n)
        delta = rng.randint(-5, 5)
        lt.range_add(l, r, delta)
        expect_full += delta * (r - l + 1)
        overlap = min(r, hi) - max(l, lo) + 1
        if overlap > 0:
            expect_mid += delta * overlap
        if step % 500 == 499:
            assert lt.range_sum(0, n - 1) == expect_full
            assert lt.range_sum(lo, hi) == expect_mid
    assert lt.range_sum(0, n - 1) == expect_full
    assert lt.range_sum(lo, hi) == expect_mid


# ------------------------------------------------------------------ fenwick
def test_fenwick_prefix_sums_hand_computed(T):
    ft = T.FenwickTree(A)
    assert ft.prefix_sum(0) == 2
    assert ft.prefix_sum(1) == 3
    assert ft.prefix_sum(2) == 8
    assert ft.prefix_sum(3) == 11
    assert ft.prefix_sum(4) == 15
    assert ft.prefix_sum(-1) == 0
    assert ft.range_sum(1, 3) == 1 + 5 + 3
    assert ft.range_sum(0, 0) == 2
    assert ft.range_sum(4, 4) == 4
    assert ft.range_sum(2, 4) == 5 + 3 + 4
    assert ft.range_sum(0, 4) == 15


def test_fenwick_point_update_accumulates(T):
    ft = T.FenwickTree(A)
    ft.point_update(0, 10)
    assert ft.prefix_sum(0) == 12
    assert ft.prefix_sum(1) == 13
    assert ft.range_sum(0, 1) == 13
    ft.point_update(0, 10)
    assert ft.prefix_sum(0) == 22
    ft.point_update(2, -5)
    assert ft.prefix_sum(2) == 22 + 1 + 0
    assert ft.prefix_sum(4) == 22 + 1 + 0 + 3 + 4
    assert ft.range_sum(2, 2) == 0
    assert ft.range_sum(2, 4) == 0 + 3 + 4


def test_fenwick_negative_and_single(T):
    ft = T.FenwickTree([-3, 7, -1, 4])
    assert ft.prefix_sum(2) == 3
    assert ft.range_sum(1, 3) == 7 - 1 + 4
    assert ft.range_sum(0, 1) == 4
    assert ft.range_sum(3, 3) == 4
    one = T.FenwickTree([42])
    assert one.prefix_sum(0) == 42
    one.point_update(0, -42)
    assert one.prefix_sum(0) == 0
    assert one.range_sum(0, 0) == 0


def test_fenwick_random_vs_brute_force(T):
    rng = random.Random(11)
    for _ in range(5):
        n = 50
        vals = [rng.randint(-50, 50) for _ in range(n)]
        ft = T.FenwickTree(vals)
        for _ in range(40):
            if rng.random() < 0.5:
                i = rng.randrange(n)
                delta = rng.randint(-30, 30)
                ft.point_update(i, delta)
                vals[i] += delta
            i = rng.randrange(n)
            assert ft.prefix_sum(i) == sum(vals[:i + 1])
            l = rng.randrange(n)
            r = rng.randrange(l, n)
            assert ft.range_sum(l, r) == sum(vals[l:r + 1])


def test_segment_vs_fenwick_cross_check_random(T):
    rng = random.Random(23)
    for _ in range(4):
        n = 45
        vals = [rng.randint(-40, 40) for _ in range(n)]
        st = T.SegmentTree(vals)
        ft = T.FenwickTree(vals)
        for _ in range(50):
            i = rng.randrange(n)
            delta = rng.randint(-25, 25)
            vals[i] += delta
            ft.point_update(i, delta)
            st.point_update(i, vals[i])
            l = rng.randrange(n)
            r = rng.randrange(l, n)
            expect = sum(vals[l:r + 1])
            assert st.range_sum(l, r) == expect
            assert ft.range_sum(l, r) == expect


# ------------------------------------------------------------------ inversions
def test_inversions_fully_reversed(T):
    assert T.count_inversions([5, 4, 3, 2, 1]) == 10
    assert T.count_inversions(list(range(10))) == 0
    assert T.count_inversions(list(range(10, 0, -1))) == 45


def test_inversions_duplicates_hand_verified(T):
    assert T.count_inversions([1, 3, 2, 3, 1]) == 4
    assert T.count_inversions([2, 2, 2]) == 0
    assert T.count_inversions([3, 2, 2]) == 2
    assert T.count_inversions([1, 2, 1, 1]) == 2


def test_inversions_edges_and_negatives(T):
    assert T.count_inversions([]) == 0
    assert T.count_inversions([7]) == 0
    assert T.count_inversions([-3, 7, -1, 4]) == 2
    assert T.count_inversions([1, 10**12, -10**12]) == 2


def test_inversions_does_not_mutate_input(T):
    arr = [3, 1, 2]
    snapshot = list(arr)
    assert T.count_inversions(arr) == 2
    assert arr == snapshot


def test_inversions_vs_brute_force_seeded(T):
    def brute(a):
        return sum(1 for i in range(len(a))
                   for j in range(i + 1, len(a)) if a[i] > a[j])

    rng = random.Random(5)
    for _ in range(6):
        arr = [rng.randint(-15, 15) for _ in range(200)]
        assert T.count_inversions(arr) == brute(arr)
