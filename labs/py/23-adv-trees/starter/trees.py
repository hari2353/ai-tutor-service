"""Lab 23 — segment trees & Fenwick (BIT). Fill in every TODO. Tests define done.

Conventions:
  * All public indices are 0-based, bounds INCLUSIVE.
  * Values may be negative.
  * No comments explaining the build — normal docstrings fine.
"""


class SegmentTree:
    """Point-update / range-sum segment tree.

    Build from a non-empty list in O(n). range_sum(l, r) and
    point_update(i, val) both O(log n). point_update ASSIGNS
    (sets values[i] = val), it does not add.

    Internal layout is your choice (array-of-4n or iterative
    bottom-up) — the tests touch behavior only.
    """

    def __init__(self, values):
        """:param values: non-empty list of numbers."""
        raise NotImplementedError

    def range_sum(self, l, r):
        """Return values[l] + values[l+1] + ... + values[r], inclusive."""
        raise NotImplementedError

    def point_update(self, i, val):
        """Set values[i] = val."""
        raise NotImplementedError


class LazySegmentTree:
    """Segment tree with lazy propagation for range-add.

    range_add(l, r, delta) adds delta to every element of [l, r] in
    O(log n) via lazy tags pushed only along the visited path — a
    naive per-leaf update is O(n) and fails the point of the structure.
    range_sum(l, r) still O(log n).
    """

    def __init__(self, values):
        raise NotImplementedError

    def range_add(self, l, r, delta):
        """Add delta to every element of [l, r]."""
        raise NotImplementedError

    def range_sum(self, l, r):
        """Return the inclusive-range sum, applying pending lazy tags."""
        raise NotImplementedError


class FenwickTree:
    """Binary Indexed Tree, 1-indexed internally, 0-based public API.

    point_update(i, delta) ADDS delta to values[i] (unlike
    SegmentTree.point_update, which assigns). prefix_sum(i) returns
    values[0] + ... + values[i]; prefix_sum(-1) == 0.
    """

    def __init__(self, values):
        """:param values: list of numbers (may be empty)."""
        raise NotImplementedError

    def point_update(self, i, delta):
        """values[i] += delta."""
        raise NotImplementedError

    def prefix_sum(self, i):
        """Sum of values[0..i], inclusive. prefix_sum(-1) == 0."""
        raise NotImplementedError

    def range_sum(self, l, r):
        """Sum of values[l..r], inclusive."""
        raise NotImplementedError


def count_inversions(arr):
    """Count pairs i < j with arr[i] > arr[j] (strictly greater —
    equal elements never count).

    Coordinate-compress to ranks, sweep left to right, accumulate
    i - prefix_sum(rank) before inserting each element. O(n log n).
    Must not mutate the input. [] has 0 inversions.

    :param arr: list of comparable values.
    :return: int, number of inversions.
    """
    raise NotImplementedError
