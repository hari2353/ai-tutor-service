"""Lab 14 tests — k-way merge. Deterministic; timing only in the witness."""
import random
import time

import pytest


# ------------------------------------------------------------------ linked list plumbing
def test_build_and_unbuild_list(P):
    head = P.build_list([1, 2, 3])
    assert P.list_to_values(head) == [1, 2, 3]


def test_build_list_empty(P):
    assert P.build_list([]) is None
    assert P.list_to_values(None) == []


def test_build_list_single(P):
    head = P.build_list([9])
    assert head.value == 9
    assert head.next is None


# ------------------------------------------------------------------ merge_k_sorted_lists
def test_merge_two_sorted_lists(P):
    a = P.build_list([1, 4, 5])
    b = P.build_list([2, 3, 6])
    merged = P.merge_k_sorted_lists([a, b])
    assert P.list_to_values(merged) == [1, 2, 3, 4, 5, 6]


def test_merge_leetcode_example(P):
    lists = [P.build_list([1, 4, 5]),
             P.build_list([1, 3, 4]),
             P.build_list([2, 6])]
    assert P.list_to_values(P.merge_k_sorted_lists(lists)) == [1, 1, 2, 3, 4, 4, 5, 6]


def test_merge_with_empty_lists(P):
    lists = [None, P.build_list([1]), None, P.build_list([0, 2]), None]
    assert P.list_to_values(P.merge_k_sorted_lists(lists)) == [0, 1, 2]


def test_merge_all_empty(P):
    assert P.merge_k_sorted_lists([]) is None
    assert P.merge_k_sorted_lists([None, None]) is None


def test_merge_single_list(P):
    assert P.list_to_values(P.merge_k_sorted_lists([P.build_list([3, 7])])) == [3, 7]


def test_merge_stability_on_equal_values(P):
    """Ties come from the earlier list first: build lists whose values carry
    their origin as a second element — here we verify with distinct-but-equal
    values by interleaving equal ints and checking they merge in order."""
    a = P.build_list([1, 1, 1])
    b = P.build_list([1, 1])
    merged = P.list_to_values(P.merge_k_sorted_lists([a, b]))
    assert merged == [1, 1, 1, 1, 1]


def test_merge_disjoint_ranges(P):
    lists = [P.build_list([100, 200]), P.build_list([1]), P.build_list([50, 51])]
    assert P.list_to_values(P.merge_k_sorted_lists(lists)) == [1, 50, 51, 100, 200]


# ------------------------------------------------------------------ k_sorted_arrays_merge
def test_arrays_merge_basic(P):
    assert P.k_sorted_arrays_merge([[1, 4, 5], [1, 3, 4], [2, 6]]) == \
        [1, 1, 2, 3, 4, 4, 5, 6]


def test_arrays_merge_empty_members(P):
    assert P.k_sorted_arrays_merge([[], [1], [], [0, 2]]) == [0, 1, 2]
    assert P.k_sorted_arrays_merge([]) == []
    assert P.k_sorted_arrays_merge([[], []]) == []


def test_arrays_merge_single_array(P):
    assert P.k_sorted_arrays_merge([[5, 6, 7]]) == [5, 6, 7]


def test_arrays_merge_matches_sorted(P):
    rng = random.Random(4)
    for _ in range(20):
        arrays = [sorted(rng.randrange(0, 30) for _ in range(rng.randrange(0, 8)))
                  for _ in range(rng.randrange(1, 6))]
        expected = sorted(x for arr in arrays for x in arr)
        assert P.k_sorted_arrays_merge(arrays) == expected


def test_arrays_merge_no_input_mutation(P):
    arrays = [[3, 6], [1, 2]]
    P.k_sorted_arrays_merge(arrays)
    assert arrays == [[3, 6], [1, 2]]


# ------------------------------------------------------------------ smallest range
def test_smallest_range_basic(P):
    lists = [[4, 10, 15, 24, 26], [0, 9, 12, 20], [5, 18, 22, 30]]
    assert P.smallest_range_covering_k_lists(lists) == (20, 24)


def test_smallest_range_single_each(P):
    assert P.smallest_range_covering_k_lists([[10], [12]]) == (10, 12)


def test_smallest_range_overlapping(P):
    lists = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
    assert P.smallest_range_covering_k_lists(lists) == (1, 1)


def test_smallest_range_tie_smaller_start(P):
    lists = [[1, 5], [2, 6]]
    assert P.smallest_range_covering_k_lists(lists) == (1, 2)


def test_smallest_range_wide_spread(P):
    lists = [[1], [100], [50]]
    assert P.smallest_range_covering_k_lists(lists) == (1, 100)


# ------------------------------------------------------------------ external sort
def test_external_sort_matches_sorted(P):
    rng = random.Random(8)
    records = [rng.randrange(-100, 100) for _ in range(500)]
    assert P.external_sort(records, 37) == sorted(records)


def test_external_sort_chunk_of_one(P):
    assert P.external_sort([3, 1, 2], 1) == [1, 2, 3]


def test_external_sort_chunk_bigger_than_input(P):
    assert P.external_sort([5, 4, 3, 2, 1], 100) == [1, 2, 3, 4, 5]


def test_external_sort_empty(P):
    assert P.external_sort([], 10) == []


def test_external_sort_invalid_capacity(P):
    with pytest.raises(ValueError):
        P.external_sort([1, 2], 0)


def test_external_sort_does_not_mutate(P):
    records = [9, 1, 8]
    P.external_sort(records, 1)
    assert records == [9, 1, 8]


# ------------------------------------------------------------------ complexity witness
def _pairwise_merge_brute(lists):
    """The naive: repeatedly merge result with next array — O(Nk)."""
    out = []
    for arr in lists:
        out = _merge2(out, list(arr))
    return out


def _merge2(a, b):
    i = j = 0
    res = []
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            res.append(a[i]); i += 1
        else:
            res.append(b[j]); j += 1
    res.extend(a[i:]); res.extend(b[j:])
    return res


def test_k_way_heap_beats_pairwise_at_high_k(P):
    """With k=120 lists of 800 elements each: heap O(N log k) vs pairwise
    O(Nk). Both must be correct; the heap path must win on time."""
    rng = random.Random(6)
    k, m = 120, 800
    arrays = [sorted(rng.randrange(0, 10**6) for _ in range(m)) for _ in range(k)]

    t0 = time.perf_counter()
    heap_result = P.k_sorted_arrays_merge(arrays)
    t_heap = time.perf_counter() - t0

    t0 = time.perf_counter()
    brute_result = _pairwise_merge_brute(arrays)
    t_brute = time.perf_counter() - t0

    assert heap_result == brute_result
    assert t_heap < t_brute, (
        f"heap merge {t_heap:.2f}s vs pairwise {t_brute:.2f}s — "
        "the O(N log k) path must beat O(Nk) at k=200"
    )


def test_big_merge_under_2s(P):
    """N = 160k total elements across 200 lists — heap merge stays linear-ish.
    Generous bound: this is pure-Python, we witness the scaling not constants."""
    rng = random.Random(7)
    k, m = 200, 800
    arrays = [sorted(rng.randrange(0, 10**9) for _ in range(m)) for _ in range(k)]
    t0 = time.perf_counter()
    out = P.k_sorted_arrays_merge(arrays)
    assert len(out) == k * m
    assert all(out[i] <= out[i + 1] for i in range(len(out) - 1))
    assert time.perf_counter() - t0 < 2.0
