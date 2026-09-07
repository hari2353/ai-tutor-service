# Lab 23: Segment Trees & Fenwick (BIT)

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-adv-trees`

**You will build:** a point-update segment tree, a lazy-propagation range-add tree, a Fenwick tree (BIT), and an O(n log n) inversion counter — all from scratch, pure stdlib.

**You will be able to answer:** *"Prefix sums answer range queries in O(1) — so why does anyone build a tree? How does lazy propagation make a range update O(log n), and why does a BIT get away with n integers where a segment tree needs 4n?"*

## Setup

```bash
cd labs/py/23-adv-trees
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

Index conventions everywhere: **0-based, bounds inclusive**, caller guarantees `0 <= l <= r < n`. Values may be negative.

1. **`SegmentTree(values)`** — build from a non-empty list in O(n).
   `range_sum(l, r)` returns `values[l] + ... + values[r]`;
   `point_update(i, val)` sets `values[i] = val` (assignment, not add).
   Both O(log n). Internal layout is yours — recursive array-of-4n or
   iterative bottom-up — the tests touch behavior only.
2. **`LazySegmentTree(values)`** — same `range_sum` contract, plus
   `range_add(l, r, delta)`: add `delta` to every element of `[l, r]`.
   Both O(log n) via lazy tags pushed only along the visited path —
   a naive "update every leaf" is O(n) and fails the point of the structure.
3. **`FenwickTree(values)`** — 1-indexed internally, **0-based public API**.
   `point_update(i, delta)` adds delta to `values[i]`;
   `prefix_sum(i)` returns `values[0] + ... + values[i]` (define `prefix_sum(-1) == 0`);
   `range_sum(l, r) = prefix_sum(r) - prefix_sum(l-1)`.
4. **`count_inversions(arr)`** — number of pairs `i < j` with `arr[i] > arr[j]`
   (**strictly** greater — equal elements never count). Coordinate-compress
   values to ranks, sweep left to right, and on a BIT of counts accumulate
   `i - prefix_sum(rank)` before inserting each element. O(n log n), must not
   mutate the input, `[]` has 0 inversions.

## Run the tests

```bash
pytest tests/ -v          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Range assignment** — add `range_set(l, r, v)`. Note why the tag discipline changes: a pending assignment must overwrite pending adds beneath it. *(Interview: "why does range-assign break naive lazy propagation?")*
2. **Min tree** — swap the monoid to `min`: `range_min(l, r)` + point update. Watch the BIT fail to do this at all, and be able to say why. *(Interview: "which operations does a BIT support, and what's the property that decides?")*
3. **Order-statistics tree** — BIT over counts plus binary-lifting descent finds the k-th smallest in O(log n); use it for the running median of a stream. *(Interview: "running median in O(log n) per element?")*
4. **Merge-sort inversions** — count inversions as a side effect of merge sort and cross-check against your BIT version on random arrays. *(Interview: "count inversions without a Fenwick tree?")*
