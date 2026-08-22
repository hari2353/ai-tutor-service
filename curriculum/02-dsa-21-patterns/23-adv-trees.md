# Advanced Trees: Segment Tree and Fenwick/BIT

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** T02-p04-merge-intervals, arrays, binary representation
> **Module id:** `T02-adv-trees` · **Tags:** advanced, range-query, data-structures

## The 30-second version

Both structures answer "range query + point/range update in better than O(n) per operation" but they trade capability for simplicity. A Fenwick tree (Binary Indexed Tree) is a compact array-backed structure that does prefix sums (or any invertible associative operation) in O(log n) per update and query, in about 10 lines of code and O(n) space with a tiny constant factor. A segment tree is strictly more general — it supports arbitrary associative operations including non-invertible ones (min, max, gcd), arbitrary range updates with lazy propagation, and range-assignment — at the cost of roughly 4x the memory (a tree of size `4n`) and more code. The decision rule: if the query is a sum (or another invertible group operation) and updates are point updates, use a Fenwick tree — it's simpler and faster in practice. If the query is min/max/gcd, or you need range updates (add k to every element in [l,r]) with lazy propagation, or the operation isn't invertible, use a segment tree. Fenwick trees cannot do range-min/max queries with point updates in the naive form because there's no way to "subtract" a min from a prefix min to get a suffix min — the whole trick behind Fenwick's O(log n) relies on invertibility.

## Why this gets asked

It tests whether you know there's a whole tier of problems ("range sum, then update a value, then range sum again, repeated thousands of times") where a naive recomputation is O(n) per operation and a prefix-sum array's O(1) query is invalidated by every update — both fail once queries and updates interleave at scale. The production pain this maps to is any leaderboard, analytics dashboard, or time-series aggregation system that needs "sum/count of events in a range, then a new event arrives" repeatedly and can't afford to rebuild an aggregate from scratch each time — that's the shape of a metrics rollup or a range-based rate limiter. It also tests bit-manipulation fluency (`i & -i`) in a second context beyond the XOR pattern, and whether you can reason about when a simpler structure (Fenwick) is sufficient versus reaching for the more general, heavier tool (segment tree) out of habit.

---

## Lineage: past → present → future

**What came before.** The naive approach — recompute a running sum, min, or max over a range by scanning it every query — is O(n) per query, and O(1) per update if you never need range queries at all; a plain prefix-sum array flips that to O(1) query but O(n) per update because every subsequent prefix must shift. Both were the default until Peter Fenwick published "A New Data Structure for Cumulative Frequency Tables" in 1994, motivated by data compression (arithmetic coding needs fast cumulative frequency lookups that update as symbol frequencies change) — the pain it killed was exactly the query/update tradeoff: neither a flat array nor a prefix-sum array could do both operations fast. Segment trees emerged earlier and less attributably from competitive programming and computational geometry communities in the 1970s-80s (closely related to interval trees and range trees used for geometric range queries), designed for the more general problem of arbitrary associative range operations, not just sums.

**Where it stands now.** Fenwick trees are the default for range-sum-with-point-update in competitive programming and production metrics systems because of their small code footprint and low constant factor; segment trees (often with lazy propagation) are the default the moment the operation isn't invertible (min/max/gcd) or range updates are needed. A 2D/multi-dimensional Fenwick tree (BIT of BITs) is a common but underused extension for range-sum queries over a grid, and a "Fenwick tree that supports range update + range query" exists via a clever two-BIT trick, but it's less discoverable than reaching for a segment tree with lazy propagation, and most practitioners just default to the segment tree once range updates enter the picture rather than deriving the double-BIT trick live. There's a live practical disagreement about whether segment trees should be implemented recursively (clearer, error-prone with lazy propagation edge cases) or iteratively (faster constant factor, harder to extend to lazy propagation) — competitive programmers favor iterative for pure range-sum/min without updates-with-effect, recursive once lazy propagation is needed.

**Where it's heading.** No new foundational structure is imminent — these are closed, well-understood 20th-century results. The applied direction is persistent and versioned variants (persistent segment trees, used for "range query as of version k" problems, e.g., k-th smallest in a range via merge-sort-tree/persistent-segment-tree combinations) showing up more often in staff-level interview problem sets, and segment trees beating out simpler structures in systems that need mergeable range aggregates across sharded data (a segment tree's subtree aggregates compose naturally in a map-reduce-style merge). Treat persistence as a real, if rarer, follow-up rather than speculative trivia.

---

## Mental model

A Fenwick tree stores partial sums at indices chosen by the lowest set bit of that index — index `i` is responsible for a range of size `i & -i` ending at `i`. Moving to the parent for updates means adding the lowest set bit; moving to compute a prefix sum means subtracting it.

```
Fenwick tree responsibility ranges (1-indexed), n=8:
index:        1   2   3   4   5   6   7   8
i & -i:        1   2   1   4   1   2   1   8
covers:      [1] [1,2] [3] [1..4] [5] [5,6] [7] [1..8]

query(7) = tree[7] + tree[6] + tree[4]
           (7 -> 7-1=6 -> 6-2=4 -> 4-4=0, stop)
update(3) touches 3 -> 3+1=4 -> 4+4=8 -> 8+8=16>n, stop
```

A segment tree is a literal binary tree over the array where each node stores the aggregate (sum/min/max/gcd) of a contiguous range, the root covers the whole array, and every internal node's value is the combine of its two children.

```
array: [2, 5, 1, 4]
                [0,3]=12
               /        \
          [0,1]=7      [2,3]=5
          /    \        /    \
     [0,0]=2 [1,1]=5 [2,2]=1 [3,3]=4

query(1,2) = combine(node[1,1], node[2,2]) = 5 + 1 = 6
             (decomposes the query range into O(log n) disjoint tree nodes)
```

---

## Recognition heuristics

- **"Range sum query" combined with "update a single element"**, repeated many times → Fenwick tree first choice; a segment tree also works but is unnecessary overhead.
- **"Range minimum/maximum query"** (RMQ) with updates → segment tree; Fenwick's invertibility trick doesn't extend to min/max.
- **"Update every element in a range by some amount, then query a range"** → segment tree with lazy propagation; naive per-element update is O(n) per operation, unacceptable at scale.
- **"Count of inversions in an array"** or **"count elements less than x seen so far"** → Fenwick tree over value-ranks (coordinate compression + BIT), a very common LeetCode/interview disguise for BIT.
- **"K-th smallest element in a range"**, **"count distinct elements in a range"** → merge-sort tree or persistent segment tree, a staff-level giveaway that plain BIT/segment tree isn't enough.
- **Static array, no updates ever** → sparse table (O(1) query after O(n log n) build) beats both for idempotent operations like min/max/gcd; mention this as the "no updates" escape hatch interviewers sometimes probe for.
- **2D grid range-sum with point updates** → 2D Fenwick tree (BIT of BITs), O(log n · log m) per operation.

---

## How it actually works — deriving the O(log n) bound from `i & -i`

The Fenwick tree's entire mechanism is one identity, the same one from the XOR pattern: `i & -i` isolates the lowest set bit. Index `i` in the tree array stores the sum of the range `(i - (i & -i), i]` (half-open, 1-indexed). To **update** index `i`, you propagate the change to every ancestor that "contains" `i` in its responsibility range — walk `i += i & -i` repeatedly until you exceed `n`; there are at most `log2(n)` such ancestors because each step strictly increases the number of trailing zero bits in `i`, and a number has at most `log2(n)` bits. To **query** a prefix sum ending at `i`, walk `i -= i & -i` repeatedly, accumulating `tree[i]`, until `i` reaches 0; the same bit argument bounds this to `O(log n)` steps. A range sum `[l, r]` is `prefix(r) - prefix(l-1)`, which is why the operation must be invertible (subtraction has to make sense) — this is exactly the property that breaks for min/max, since `min(prefix(r)) - min(prefix(l-1))` is meaningless.

A segment tree's `O(log n)` bound comes from a different argument: any query range `[l, r]` decomposes into at most `O(log n)` "canonical" nodes of the tree — at each level of recursion, the query range either fully covers a node (return immediately), is fully outside (return identity), or partially overlaps (recurse into both children, at most 2 partial nodes per level). Since there are `log n` levels and at most 2 partially-overlapping nodes per level, the total work is `O(log n)`. Lazy propagation defers range updates: instead of pushing an update all the way down to every leaf in `[l,r]` immediately (O(n) worst case), store a pending update at the highest node that's fully covered by `[l,r]`, and only push it down to children when a future query or update actually needs to descend past that node.

---

## Template code (Python, Java, Go)

```python
# Fenwick Tree (Binary Indexed Tree) — 1-indexed internally
class Fenwick:
    def __init__(self, n: int):
        self.n = n
        self.tree = [0] * (n + 1)

    def update(self, i: int, delta: int) -> None:
        i += 1  # convert 0-indexed input to 1-indexed
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)

    def prefix(self, i: int) -> int:
        i += 1
        s = 0
        while i > 0:
            s += self.tree[i]
            i -= i & (-i)
        return s

    def range_sum(self, l: int, r: int) -> int:  # inclusive, 0-indexed
        return self.prefix(r) - (self.prefix(l - 1) if l > 0 else 0)


# Segment Tree — sum, with lazy propagation for range-add
class SegmentTree:
    def __init__(self, arr: list[int]):
        self.n = len(arr)
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self._build(arr, 1, 0, self.n - 1)

    def _build(self, arr, node, lo, hi):
        if lo == hi:
            self.tree[node] = arr[lo]
            return
        mid = (lo + hi) // 2
        self._build(arr, 2 * node, lo, mid)
        self._build(arr, 2 * node + 1, mid + 1, hi)
        self.tree[node] = self.tree[2 * node] + self.tree[2 * node + 1]

    def _push_down(self, node, lo, hi):
        if self.lazy[node] == 0:
            return
        mid = (lo + hi) // 2
        for child, (clo, chi) in ((2 * node, (lo, mid)), (2 * node + 1, (mid + 1, hi))):
            self.tree[child] += self.lazy[node] * (chi - clo + 1)
            self.lazy[child] += self.lazy[node]
        self.lazy[node] = 0

    def range_add(self, l, r, delta, node=1, lo=None, hi=None):
        if lo is None:
            lo, hi = 0, self.n - 1
        if r < lo or hi < l:
            return
        if l <= lo and hi <= r:
            self.tree[node] += delta * (hi - lo + 1)
            self.lazy[node] += delta
            return
        self._push_down(node, lo, hi)
        mid = (lo + hi) // 2
        self.range_add(l, r, delta, 2 * node, lo, mid)
        self.range_add(l, r, delta, 2 * node + 1, mid + 1, hi)
        self.tree[node] = self.tree[2 * node] + self.tree[2 * node + 1]

    def range_sum(self, l, r, node=1, lo=None, hi=None):
        if lo is None:
            lo, hi = 0, self.n - 1
        if r < lo or hi < l:
            return 0
        if l <= lo and hi <= r:
            return self.tree[node]
        self._push_down(node, lo, hi)
        mid = (lo + hi) // 2
        return (self.range_sum(l, r, 2 * node, lo, mid) +
                self.range_sum(l, r, 2 * node + 1, mid + 1, hi))
```

```java
// Fenwick Tree (Binary Indexed Tree)
public class Fenwick {
    private final int[] tree;
    private final int n;

    public Fenwick(int n) {
        this.n = n;
        this.tree = new int[n + 1];
    }

    public void update(int i, int delta) {
        for (i += 1; i <= n; i += i & (-i)) {
            tree[i] += delta;
        }
    }

    public int prefix(int i) {
        int s = 0;
        for (i += 1; i > 0; i -= i & (-i)) {
            s += tree[i];
        }
        return s;
    }

    public int rangeSum(int l, int r) {
        return prefix(r) - (l > 0 ? prefix(l - 1) : 0);
    }
}

// Segment Tree — sum, with lazy propagation for range-add
public class SegmentTree {
    private final long[] tree;
    private final long[] lazy;
    private final int n;

    public SegmentTree(int[] arr) {
        n = arr.length;
        tree = new long[4 * n];
        lazy = new long[4 * n];
        build(arr, 1, 0, n - 1);
    }

    private void build(int[] arr, int node, int lo, int hi) {
        if (lo == hi) { tree[node] = arr[lo]; return; }
        int mid = (lo + hi) / 2;
        build(arr, 2 * node, lo, mid);
        build(arr, 2 * node + 1, mid + 1, hi);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }

    private void pushDown(int node, int lo, int hi) {
        if (lazy[node] == 0) return;
        int mid = (lo + hi) / 2;
        int left = 2 * node, right = 2 * node + 1;
        tree[left] += lazy[node] * (mid - lo + 1);
        lazy[left] += lazy[node];
        tree[right] += lazy[node] * (hi - mid);
        lazy[right] += lazy[node];
        lazy[node] = 0;
    }

    public void rangeAdd(int l, int r, long delta, int node, int lo, int hi) {
        if (r < lo || hi < l) return;
        if (l <= lo && hi <= r) {
            tree[node] += delta * (hi - lo + 1);
            lazy[node] += delta;
            return;
        }
        pushDown(node, lo, hi);
        int mid = (lo + hi) / 2;
        rangeAdd(l, r, delta, 2 * node, lo, mid);
        rangeAdd(l, r, delta, 2 * node + 1, mid + 1, hi);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }

    public long rangeSum(int l, int r, int node, int lo, int hi) {
        if (r < lo || hi < l) return 0;
        if (l <= lo && hi <= r) return tree[node];
        pushDown(node, lo, hi);
        int mid = (lo + hi) / 2;
        return rangeSum(l, r, 2 * node, lo, mid) + rangeSum(l, r, 2 * node + 1, mid + 1, hi);
    }
}
```

```go
package main

// Fenwick Tree (Binary Indexed Tree)
type Fenwick struct {
    tree []int
    n    int
}

func NewFenwick(n int) *Fenwick {
    return &Fenwick{tree: make([]int, n+1), n: n}
}

func (f *Fenwick) Update(i, delta int) {
    for i += 1; i <= f.n; i += i & (-i) {
        f.tree[i] += delta
    }
}

func (f *Fenwick) Prefix(i int) int {
    s := 0
    for i += 1; i > 0; i -= i & (-i) {
        s += f.tree[i]
    }
    return s
}

func (f *Fenwick) RangeSum(l, r int) int {
    if l > 0 {
        return f.Prefix(r) - f.Prefix(l-1)
    }
    return f.Prefix(r)
}

// Segment Tree — sum, with lazy propagation for range-add
type SegmentTree struct {
    tree, lazy []int64
    n          int
}

func NewSegmentTree(arr []int) *SegmentTree {
    n := len(arr)
    st := &SegmentTree{tree: make([]int64, 4*n), lazy: make([]int64, 4*n), n: n}
    st.build(arr, 1, 0, n-1)
    return st
}

func (st *SegmentTree) build(arr []int, node, lo, hi int) {
    if lo == hi {
        st.tree[node] = int64(arr[lo])
        return
    }
    mid := (lo + hi) / 2
    st.build(arr, 2*node, lo, mid)
    st.build(arr, 2*node+1, mid+1, hi)
    st.tree[node] = st.tree[2*node] + st.tree[2*node+1]
}

func (st *SegmentTree) pushDown(node, lo, hi int) {
    if st.lazy[node] == 0 {
        return
    }
    mid := (lo + hi) / 2
    left, right := 2*node, 2*node+1
    st.tree[left] += st.lazy[node] * int64(mid-lo+1)
    st.lazy[left] += st.lazy[node]
    st.tree[right] += st.lazy[node] * int64(hi-mid)
    st.lazy[right] += st.lazy[node]
    st.lazy[node] = 0
}

func (st *SegmentTree) RangeAdd(l, r int, delta int64, node, lo, hi int) {
    if r < lo || hi < l {
        return
    }
    if l <= lo && hi <= r {
        st.tree[node] += delta * int64(hi-lo+1)
        st.lazy[node] += delta
        return
    }
    st.pushDown(node, lo, hi)
    mid := (lo + hi) / 2
    st.RangeAdd(l, r, delta, 2*node, lo, mid)
    st.RangeAdd(l, r, delta, 2*node+1, mid+1, hi)
    st.tree[node] = st.tree[2*node] + st.tree[2*node+1]
}

func (st *SegmentTree) RangeSum(l, r, node, lo, hi int) int64 {
    if r < lo || hi < l {
        return 0
    }
    if l <= lo && hi <= r {
        return st.tree[node]
    }
    st.pushDown(node, lo, hi)
    mid := (lo + hi) / 2
    return st.RangeSum(l, r, 2*node, lo, mid) + st.RangeSum(l, r, 2*node+1, mid+1, hi)
}
```

## Complexity — derived, not asserted

**Fenwick tree:** both `update` and `prefix` walk a chain of ancestors determined by repeatedly adding or subtracting the lowest set bit; since each step changes the trailing-zero-bit-count of the index and an integer has at most `log2(n)` bits, both operations are `O(log n)`. Space is `O(n)`, one array, roughly 4-8 bytes per element depending on width — a small constant factor that makes it the practical default over a segment tree's `4n`-node array when the operation is invertible.

**Segment tree:** build is `O(n)` (each of `n` leaves is touched once, each of `n-1` internal nodes combines its children once). Point/range query and point/range update (with lazy propagation) are each `O(log n)`, from the canonical-decomposition argument above. Space is `O(4n)` in the common recursive array-backed implementation (a complete binary tree over `n` leaves needs at most `4n` array slots to stay safely within bounds, though `2n` rounded up to the next power of two is the tight bound) — a real, if small, memory cost relative to Fenwick's `O(n)`.

**Sparse table (static, no updates):** `O(n log n)` build, `O(1)` query for idempotent operations (min/max/gcd/AND/OR where overlapping the same element twice doesn't corrupt the answer), but does not support updates at all — rebuilding after any change costs the full `O(n log n)` again, so it's a fundamentally different tool for a fundamentally different problem shape (static array, huge number of queries, zero updates).

---

## The 5 variants interviewers actually ask

1. **Range Sum Query - Mutable (LC 307).** The canonical Fenwick tree problem: point update, range sum query, repeated. A segment tree also passes but is strictly more code for the same guarantee.
2. **Range Sum Query 2D - Mutable (LC 308).** 2D Fenwick tree (BIT of BITs): `update(row, col, delta)` walks the outer BIT over rows, and at each touched row walks an inner BIT over columns. O(log n · log m) per operation.
3. **Count of Smaller Numbers After Self (LC 315) / Count Inversions.** Coordinate-compress the values, then walk the array right to left (or left to right, depending on framing), using a Fenwick tree over compressed ranks to count how many already-inserted values are smaller than the current one. This is the "BIT wearing a counting-problem costume" variant most likely to be missed.
4. **Range Minimum Query with point updates.** Not solvable with a plain Fenwick trick — use a segment tree where the combine function is `min` instead of `+`; the lazy-propagation logic for a point update (not range update) is trivial (no lazy needed at all, just update-and-recombine up the ancestor chain).
5. **My Calendar III / Range addition with range-max query (LC 732-style, or "maximum overlap of intervals after many range-add operations").** Segment tree with lazy propagation for range-add, and the aggregate function is `max` instead of `sum` — tests whether you can adapt the lazy-propagation push-down math (linear for sum, but for max you propagate the raw delta and just add it to the child's max instead of multiplying by range length).

---

## Common bugs and how this gets written wrong under pressure

- **Off-by-one between 0-indexed input and 1-indexed Fenwick internals.** Fenwick trees are naturally 1-indexed because `i & -i` behaves incorrectly at index 0 (there is no lowest set bit); forgetting the `+1` shift on the way in (and matching `-1` conceptually on the way out) is the single most common Fenwick bug.
- **Using a Fenwick tree for range-min/max.** `i & -i` gives you an invertible prefix structure; min/max have no inverse operation, so `prefix_min(r) "minus" prefix_min(l-1)` is meaningless. This mistake usually surfaces as "it works on the sample input" (where the minimum happens to lie inside both prefixes) and silently breaks on a case where it doesn't.
- **Forgetting to push down lazy values before recursing in a segment tree.** Reading `tree[node]` or recursing into children without first calling `push_down` returns a stale aggregate that hasn't accounted for a pending range update — this passes small tests where updates and queries don't interleave and fails once they do.
- **Segment tree array under-sized.** Allocating exactly `2n` instead of `4n` for a recursive, non-power-of-two-friendly implementation causes an index-out-of-bounds on tree sizes that aren't already a power of two; `4n` is the standard safe bound.
- **Recomputing coordinate compression incorrectly for the inversion-counting variant.** Using the raw value as the Fenwick index instead of its compressed rank works only if values are small and dense; forgetting compression on inputs with large or sparse values causes a huge, memory-wasteful (or out-of-bounds) Fenwick array.
- **Applying a range update's lazy delta without scaling by range length for sum, or scaling when you shouldn't for max.** The push-down math is operation-specific: `tree[child] += delta * (range length)` is correct for sum-aggregation but wrong for max-aggregation, where it should just be `tree[child] += delta` (or reassigned, depending on whether the update is additive or a hard set); mixing the two up is a common under-pressure slip when adapting a memorized sum-segment-tree template to a max-segment-tree problem.

---

## Interview questions

### Q1 — Range Sum Query - Mutable (LC 307): point updates, range sum queries, repeated many times.
**Testing:** the baseline Fenwick tree implementation.
**Answer:** Fenwick tree, O(log n) per update and per prefix/range query.
**Follow-up trap:** *"Why not a segment tree instead?"* — a segment tree also works, but it's 4x the memory and more code for the same guarantee; the interviewer is checking you know the simpler tool suffices for a sum-only, point-update-only problem.

### Q2 — Range Sum Query 2D - Mutable (LC 308).
**Testing:** whether you can extend the 1D idea to 2D without over-complicating it.
**Answer:** A 2D Fenwick tree — an outer BIT over rows, each touched row holding an inner BIT over columns. Update and query are O(log n · log m).
**Follow-up trap:** *"What if updates were rare and queries extremely frequent?"* — precompute a 2D prefix-sum matrix instead for O(1) query, accepting O(nm) rebuild cost per update; the right structure depends on the read/write ratio, not just the shape of the problem.

### Q3 — Count of Smaller Numbers After Self (LC 315).
**Testing:** recognizing a counting problem as a disguised Fenwick-over-ranks problem.
**Answer:** Coordinate-compress all values to ranks, then process the array from right to left, querying `prefix(rank-1)` (count of smaller values already inserted) before each insertion.
**Follow-up trap:** *"Could you solve this with a merge sort instead?"* — yes, a modified merge sort counting cross-inversions during the merge step also achieves O(n log n); know both, and be ready to say the Fenwick version is usually easier to get right under interview time pressure.

### Q4 — Range Minimum Query with point updates.
**Testing:** knowing the Fenwick-versus-segment-tree boundary precisely.
**Answer:** Segment tree with `min` as the combine function; no lazy propagation needed since updates are point, not range.
**Follow-up trap:** *"Can you adapt the Fenwick trick for this?"* — no, and explaining *why not* (no inverse for min) is the actual test; a "min-Fenwick" only works in restricted special cases (e.g., when updates only decrease values monotonically), not in general.

### Q5 — Range-add, range-sum query (assign a delta to every element in [l,r], then ask for range sums).
**Testing:** lazy propagation.
**Answer:** Segment tree with lazy propagation: defer pushing the update to children until a query or update actually needs to descend past the lazily-marked node.
**Follow-up trap:** *"Can a Fenwick tree do this too?"* — yes, with a less obvious trick: maintain two Fenwick trees (one for the raw delta, one for delta*index) that together let you derive both range-update and range-query in O(log n); most candidates don't derive this live and defaulting to the segment tree is the pragmatic answer.

### Q6 — Explain why `i & -i` gives the size of the range that Fenwick index `i` is responsible for.
**Testing:** the bit-level derivation, not just the formula.
**Answer:** In two's complement, `-i = ~i + 1`; ANDing `i` with `-i` isolates the lowest set bit of `i`, and the value of that isolated bit *is* the size of the range index `i` covers, because the Fenwick indexing scheme is defined so each node's range length equals its lowest set bit's value.
**Follow-up trap:** *"Prove the update and query loops each take O(log n) steps."* — each step of the update loop strictly increases the number of trailing zero bits (moving to a "bigger" responsibility range); each step of the query loop strictly decreases the index by clearing its lowest set bit; both processes are bounded by the bit-width of `n`, i.e., `O(log n)`.

### Q7 — Given a static array (no updates ever) and a huge number of range-min queries, what's the fastest structure?
**Testing:** knowing when neither Fenwick nor segment tree is optimal.
**Answer:** Sparse table: O(n log n) preprocessing, O(1) per query, by precomputing min over every power-of-two-length window and combining two overlapping windows per query (min is idempotent, so overlap doesn't corrupt the answer).
**Follow-up trap:** *"What if a single update needs to happen after all?"* — the sparse table doesn't support updates at all; you'd need to rebuild it in O(n log n), which defeats the purpose the moment updates are frequent — fall back to a segment tree.

### Q8 — Implement lazy propagation for range-add + range-max (not range-sum).
**Testing:** whether you can adapt the standard sum-lazy math to a different aggregate.
**Answer:** Store the same pending delta at a lazy node, but push it down by simply adding the delta to the child's max value (not scaling by range length, since max isn't additive across elements the way sum is) and to the child's own lazy value.
**Follow-up trap:** *"What if the update were a range 'set to value' rather than 'add delta'?"* — that requires a different lazy tag (an assignment tag that overrides, rather than a delta that accumulates), and a node can't have both an "add" and an "assign" pending simultaneously without additional bookkeeping to define which applies first.

### Q9 — K-th smallest element in a range, with the array static but with q > n queries.
**Testing:** recognizing when persistence is the right escalation.
**Answer:** A persistent segment tree (a "merge sort tree") built by inserting each element in array order, keeping a versioned root per prefix; answering "k-th smallest in [l,r]" as a difference of two versions' segment trees, similar in spirit to how prefix sums difference two cumulative states.
**Follow-up trap:** *"What's the space cost of persistence?"* — each update only changes O(log n) nodes along a root-to-leaf path, so persisting n versions costs O(n log n) total space, not O(n) per version — a key fact that makes persistent structures practical rather than a memory bomb.

### Q10 — Why is a segment tree's array typically sized `4n` instead of a tight `2n`?
**Testing:** understanding the actual space bound versus the commonly memorized "safe" number.
**Answer:** For an array-backed complete binary tree over n leaves, the tight bound is close to `2 * 2^(ceil(log2 n))`, which can be slightly more than `2n` when n isn't a power of two; `4n` is a simple, always-safe upper bound engineers use to avoid deriving the tight formula.
**Follow-up trap:** *"Does the choice of 4n vs a tighter bound matter for a production system?"* — at scale (millions of elements) the 2x-ish overhead is a real, measurable memory cost; production segment tree implementations often use an iterative, exactly-2n-sized layout precisely to avoid it, at the cost of losing easy lazy-propagation support.

### Q11 — Multiple Fenwick trees are updated concurrently by different threads. What breaks?
**Testing:** whether you can reason about the structure under concurrency, a staff-level extension.
**Answer:** Fenwick tree updates touch a chain of O(log n) shared array slots; concurrent updates to overlapping ancestor chains race unless externally synchronized (a lock per node, a striped lock scheme, or a single writer with readers snapshotting).
**Follow-up trap:** *"Is there a lock-free version?"* — approaches exist using atomic fetch-and-add per node for sum-only Fenwick trees (since the update is a simple additive combine with no read-modify-write dependency across nodes in the same chain being an issue for sum), but a correctness argument for lock-free min/max segment trees is materially harder and rarely worth the complexity versus a coarser lock.

---

## Red flags that fail you

- Reaching for a Fenwick tree for a range-min/max problem without noticing the invertibility requirement doesn't hold.
- Forgetting the 1-indexing convention and not being able to explain why `i & -i` breaks at index 0.
- Not pushing down lazy values before reading or recursing past a segment tree node.
- Defaulting to a segment tree for a plain range-sum-with-point-update problem without acknowledging a Fenwick tree is simpler and sufficient.
- Not knowing that a static array with zero updates has a strictly better O(1)-query structure (sparse table) than either.
- Confusing the push-down formula for sum-aggregation (scale by range length) with max-aggregation (don't scale).

---

## Cheat card

```
FENWICK/BIT    point update + prefix/range SUM, O(log n) both ops, O(n) space
               i & -i isolates lowest set bit = size of index's range
               update: i += i&-i ; query: i -= i&-i ; 1-indexed internally
               CANNOT do min/max (no inverse) -- sum/xor/invertible ops only
SEGMENT TREE   any associative op (sum/min/max/gcd), O(log n) query+update
               O(4n) space (array-backed), build O(n)
               range update -> needs LAZY PROPAGATION or O(n) per update
LAZY PROP      defer push to children; push_down before reading/recursing
               past a node; sum: delta*(range len); max: just += delta
SPARSE TABLE   static array, NO updates, O(n log n) build, O(1) query
               only for idempotent ops (min/max/gcd/and/or)
2D FENWICK     grid range-sum + point update, O(log n * log m)
PERSISTENT     versioned segment tree, O(log n) new nodes per update,
               O(n log n) total space for n versions -- k-th smallest in range
WATCH          off-by-one on 1-indexing; missing push_down; 2n vs 4n sizing;
               scaling lazy delta correctly per aggregate type
```

## Sources

- Fenwick, P. M. (1994). "A New Data Structure for Cumulative Frequency Tables." Software: Practice and Experience, 24(3), 327-336.
- [Binary Indexed Tree — CP-Algorithms](https://cp-algorithms.com/data_structures/fenwick.html) — accessed 2026-07-26
- [Segment Tree — CP-Algorithms](https://cp-algorithms.com/data_structures/segment_tree.html) — accessed 2026-07-26
- [Range Sum Query - Mutable — LeetCode](https://leetcode.com/problems/range-sum-query-mutable/) — accessed 2026-07-26
- [Count of Smaller Numbers After Self — LeetCode](https://leetcode.com/problems/count-of-smaller-numbers-after-self/) — accessed 2026-07-26
- [Range Sum Query 2D - Mutable — LeetCode](https://leetcode.com/problems/range-sum-query-2d-mutable/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
