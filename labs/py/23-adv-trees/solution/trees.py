"""Lab 23 — reference: segment trees & Fenwick (BIT)."""


class SegmentTree:
    """Iterative bottom-up point-update / range-sum segment tree."""

    def __init__(self, values):
        if not values:
            raise ValueError("values must be non-empty")
        self.n = len(values)
        self.tree = [0] * (2 * self.n)
        self.tree[self.n:] = list(values)
        for i in range(self.n - 1, 0, -1):
            self.tree[i] = self.tree[2 * i] + self.tree[2 * i + 1]

    def range_sum(self, l, r):
        res = 0
        lo = l + self.n
        hi = r + 1 + self.n
        while lo < hi:
            if lo & 1:
                res += self.tree[lo]
                lo += 1
            if hi & 1:
                hi -= 1
                res += self.tree[hi]
            lo >>= 1
            hi >>= 1
        return res

    def point_update(self, i, val):
        pos = i + self.n
        self.tree[pos] = val
        pos >>= 1
        while pos:
            self.tree[pos] = self.tree[2 * pos] + self.tree[2 * pos + 1]
            pos >>= 1


class LazySegmentTree:
    """Range-add / range-sum segment tree with lazy propagation."""

    def __init__(self, values):
        if not values:
            raise ValueError("values must be non-empty")
        self.n = len(values)
        self.sum = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self._build(1, 0, self.n - 1, values)

    def _build(self, node, lo, hi, values):
        if lo == hi:
            self.sum[node] = values[lo]
            return
        mid = (lo + hi) // 2
        self._build(2 * node, lo, mid, values)
        self._build(2 * node + 1, mid + 1, hi, values)
        self.sum[node] = self.sum[2 * node] + self.sum[2 * node + 1]

    def _apply(self, node, lo, hi, delta):
        self.sum[node] += delta * (hi - lo + 1)
        self.lazy[node] += delta

    def _push(self, node, lo, hi):
        if self.lazy[node]:
            mid = (lo + hi) // 2
            self._apply(2 * node, lo, mid, self.lazy[node])
            self._apply(2 * node + 1, mid + 1, hi, self.lazy[node])
            self.lazy[node] = 0

    def _add(self, node, lo, hi, l, r, delta):
        if r < lo or hi < l:
            return
        if l <= lo and hi <= r:
            self._apply(node, lo, hi, delta)
            return
        self._push(node, lo, hi)
        mid = (lo + hi) // 2
        self._add(2 * node, lo, mid, l, r, delta)
        self._add(2 * node + 1, mid + 1, hi, l, r, delta)
        self.sum[node] = self.sum[2 * node] + self.sum[2 * node + 1]

    def _query(self, node, lo, hi, l, r):
        if r < lo or hi < l:
            return 0
        if l <= lo and hi <= r:
            return self.sum[node]
        self._push(node, lo, hi)
        mid = (lo + hi) // 2
        return (self._query(2 * node, lo, mid, l, r)
                + self._query(2 * node + 1, mid + 1, hi, l, r))

    def range_add(self, l, r, delta):
        self._add(1, 0, self.n - 1, l, r, delta)

    def range_sum(self, l, r):
        return self._query(1, 0, self.n - 1, l, r)


class FenwickTree:
    """Binary Indexed Tree, 1-indexed internally, 0-based public API."""

    def __init__(self, values):
        self.n = len(values)
        self.bit = [0] * (self.n + 1)
        for i, v in enumerate(values):
            self.bit[i + 1] = v
        for i in range(1, self.n + 1):
            j = i + (i & -i)
            if j <= self.n:
                self.bit[j] += self.bit[i]

    def point_update(self, i, delta):
        i += 1
        while i <= self.n:
            self.bit[i] += delta
            i += i & -i

    def prefix_sum(self, i):
        if i < 0:
            return 0
        res = 0
        i += 1
        while i > 0:
            res += self.bit[i]
            i -= i & -i
        return res

    def range_sum(self, l, r):
        return self.prefix_sum(r) - self.prefix_sum(l - 1)


def count_inversions(arr):
    """Count pairs i < j with arr[i] > arr[j], strictly. O(n log n)."""
    ranks = {v: i for i, v in enumerate(sorted(set(arr)))}
    bit = FenwickTree([0] * len(ranks))
    inversions = 0
    for j, x in enumerate(arr):
        inversions += j - bit.prefix_sum(ranks[x])
        bit.point_update(ranks[x], 1)
    return inversions
