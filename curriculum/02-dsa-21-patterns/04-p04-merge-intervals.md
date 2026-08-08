# Merge Intervals

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-07-27
> **Module id:** `T02-p04-merge-intervals` · **Tags:** pattern, intervals, sweep-line

## The 30-second version

Merge Intervals sorts a list of ranges by start value, then does a single linear sweep comparing each interval's start against the running merged block's end: if the current interval starts at or before the merged block's end, fold it in by extending the end to `max(current.end, merged.end)`; otherwise close the current block and open a new one. Sorting is what makes the linear sweep valid — once ordered by start, only the interval immediately following the current merged block can possibly overlap it, so you never need to look back. That gives O(n log n) total, dominated entirely by the sort, with the merge pass itself O(n). Recognize it from "intervals," "meetings," "ranges," "schedule," "overlap," "free time," or "merge/insert a range into a sorted set of ranges." The two things that separate a working answer from a wrong one are which field you sort by (start, almost always — except the "maximize count of non-overlapping intervals" variant, which sorts by end) and getting the overlap boundary condition (`<=` vs `<`) to match whether touching intervals count as overlapping in that specific problem.

## Why this gets asked

The interviewer is checking whether you reach for sorting as the first move rather than trying to solve interval overlap with nested pairwise comparisons, which is the natural but wrong instinct and degrades to O(n^2) (or, worse, an incorrect greedy that doesn't handle transitive overlap: `[1,5]` and `[10,15]` don't overlap directly, but if a third interval `[4,12]` bridges them, all three must merge into one block). This is a pattern the interviewer has almost certainly implemented for real: calendar and meeting-room booking systems, log-timestamp range compaction before storage, CDN/cache invalidation window coalescing, and rate-limit window bucketing all reduce to "merge overlapping time ranges" or "how many concurrent ranges exist at the busiest moment." The follow-up that actually separates levels is Meeting Rooms II — computing the *maximum concurrency*, not just merging — because it forces a choice between a min-heap of end times and a sweep-line of +1/-1 events, and asking you to justify why one is asymptotically no better than the other but structurally different.

---

## Lineage: past → present → future

**What came before.** Before "sort then sweep" was the standard interview answer, interval problems were solved either by brute-force pairwise overlap checking (O(n^2), and easy to get subtly wrong on transitive overlap) or by reaching for a full interval tree — an augmented balanced BST storing the max endpoint in each subtree, giving O(log n + k) overlap queries against a dynamic set, described in Cormen/Leiserson/Rivest/Stein's *Introduction to Algorithms* and used in computational-geometry systems since the 1980s. The pain with the pairwise approach was quadratic blowup on large inputs; the pain with jumping straight to an interval tree for what's usually a one-shot batch merge was massive over-engineering — building and maintaining a balanced tree for a single merge-and-done pass is wasted complexity when a sort plus a linear scan solves the same problem in the same asymptotic time class for the static case.

**Where it stands now.** For the batch case — merge a fixed list of intervals once — sort-by-start-then-sweep is the unambiguous industry-standard answer; there is no live disagreement about the algorithm. For the dynamic case — intervals are inserted and queried continuously, like a live calendar or a booking system under concurrent writes — production systems genuinely do use interval trees or segment trees (e.g., database range-lock managers, calendar backends, and CDN edge cache invalidation trackers), because re-sorting the entire set on every insertion is wasteful. Meeting Rooms II is where practitioners' intuitions diverge on tooling even though the answer's complexity is identical: a min-heap of active end times and a sweep line built from +1/−1 delta events at sorted boundaries are both O(n log n) and both correct, but the heap generalizes more naturally to "assign this room number to this meeting" bookkeeping, while the sweep line generalizes more naturally to "give me the concurrency profile over the whole day," so the "right" one depends on what you need out of the answer, not on complexity.

**Where it's heading.** Expect this pattern to keep showing up mostly unchanged as a standalone question, but increasingly composed with a second constraint — weighted interval scheduling (choose a maximum-weight subset of non-overlapping intervals, solved with DP plus binary search over end times, a step up from the greedy LC435 variant) or streaming insertion (LC57, insert one interval into an already-merged sorted set without re-sorting everything) — because both test whether you understand *why* the sort-then-sweep invariant holds rather than having memorized the code for the static case. This is a moderate-confidence prediction based on how often "insert interval" and "employee free time" already appear as the assigned harder sibling to the basic merge question in current interview reports.

---

## Mental model

```
Unsorted input:      [8,10]   [1,3]   [2,6]   [15,18]

Sort by start:       [1,3]  [2,6]  [8,10]  [15,18]

Sweep, one running merged block:

merged = [1,3]
next = [2,6]: 2 <= merged.end(3)?  yes -> merged = [1, max(3,6)] = [1,6]
next = [8,10]: 8 <= merged.end(6)? no  -> close [1,6], open merged = [8,10]
next = [15,18]: 15 <= merged.end(10)? no -> close [8,10], open merged = [15,18]
end of input -> close [15,18]

output: [1,6]  [8,10]  [15,18]
```

The invariant that makes a single forward pass sufficient: once sorted by start, if interval `k` does not overlap the current merged block, no interval `k+1, k+2, ...` can either, because their starts are all `>= start[k] >= ` the merged block's start, and if `start[k]` already exceeds the merged block's end, every later (larger) start does too. You never need to reopen a closed block or look backward.

---

## Recognition heuristics

- **"Merge overlapping intervals/ranges/meetings"** — the base pattern by name. Sort by start, sweep, extend or close.
- **"Insert a new interval into an already-sorted, already-merged list"** — do not re-sort and re-merge everything (that's the naive-but-correct O(n log n) approach); instead do a single O(n) linear scan: copy every interval ending strictly before the new one starts, merge every interval overlapping the new one into it, then copy the rest.
- **"Minimum number of meeting rooms" / "maximum number of overlapping intervals at any point"** — this is *not* a merge question, it's a concurrency-counting question: min-heap of active end times (pop while the heap's smallest end `<=` current start) or a sweep line of `+1` at each start and `-1` at each end, sorted by time, tracking a running sum's maximum.
- **"Maximum number of non-overlapping intervals to keep" / "minimum number to remove"** — classic greedy interval scheduling: sort by **end** time, not start, and greedily keep an interval if its start is `>=` the last kept interval's end. Sorting by start here gives the wrong answer.
- **"Free time across multiple people's schedules"** — merge the union of all intervals across all schedules into one sorted, merged list, then the gaps *between* consecutive merged blocks are the free time.
- **"Intersection of two lists of intervals"** — not a merge at all; two-pointer walk across both sorted lists, emitting `[max(starts), min(ends)]` whenever it's a valid (non-empty) range, then advancing whichever interval ends first.

**Anti-signal:** if the intervals are not comparable by a single scalar range (e.g., 2D rectangles, not 1D intervals), this pattern doesn't directly apply — that's a computational-geometry sweep with a different event model (rectangle union/area problems), not interval merging.

---

## Template code (Python, Java, Go)

Base merge — the reusable skeleton for the whole family:

**Python**
```python
def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """Merge all overlapping intervals. O(n log n) time (sort-dominated), O(n) output space."""
    if not intervals:
        return []
    intervals.sort(key=lambda iv: iv[0])
    merged = [intervals[0][:]]
    for start, end in intervals[1:]:
        last = merged[-1]
        if start <= last[1]:            # overlap (or touch, if that counts for this problem)
            last[1] = max(last[1], end)  # must take the max -- a shorter interval can be fully nested
        else:
            merged.append([start, end])
    return merged
```

**Java**
```java
public int[][] mergeIntervals(int[][] intervals) {
    if (intervals.length == 0) return intervals;
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[0], b[0]));
    List<int[]> merged = new ArrayList<>();
    merged.add(intervals[0]);
    for (int i = 1; i < intervals.length; i++) {
        int[] last = merged.get(merged.size() - 1);
        int[] cur = intervals[i];
        if (cur[0] <= last[1]) {
            last[1] = Math.max(last[1], cur[1]);
        } else {
            merged.add(cur);
        }
    }
    return merged.toArray(new int[merged.size()][]);
}
```

**Go**
```go
func mergeIntervals(intervals [][]int) [][]int {
	if len(intervals) == 0 {
		return intervals
	}
	sort.Slice(intervals, func(i, j int) bool { return intervals[i][0] < intervals[j][0] })
	merged := [][]int{{intervals[0][0], intervals[0][1]}}
	for _, iv := range intervals[1:] {
		last := merged[len(merged)-1]
		if iv[0] <= last[1] {
			if iv[1] > last[1] {
				last[1] = iv[1]
			}
		} else {
			merged = append(merged, []int{iv[0], iv[1]})
		}
	}
	return merged
}
```

---

## Complexity, derived

The sort costs `O(n log n)` comparisons (comparison-sort lower bound), and every subsequent step touches each interval exactly once: the linear sweep does one comparison and at most one array append or in-place extend per interval, so the merge pass itself is `O(n)`. Total: `O(n log n)`, entirely dominated by the sort — the merge logic contributes only a lower-order `O(n)` term. Space is `O(n)` for the output (or `O(log n)` to `O(n)` for the sort's own working space depending on the sort implementation; Python's Timsort is O(n) worst case, Java's dual-pivot quicksort on primitives is O(log n) auxiliary). For **Insert Interval** (no re-sort needed, input already sorted and merged): the single linear scan is `O(n)` time, `O(n)` output space — strictly better than re-running the full merge, and the complexity difference (`O(n)` vs `O(n log n)`) is the entire point of that variant. For **Meeting Rooms II** via min-heap: `O(n log n)` for the initial sort by start plus `O(n log n)` for up to `n` heap push/pop operations, so `O(n log n)` total, `O(n)` heap space in the worst case (all meetings overlap).

---

## The 5 variants interviewers actually ask

1. **Merge Intervals (base).** Sort by start, sweep, extend `end = max(end, next.end)` on overlap. `O(n log n)`.
2. **Insert Interval.** Input is already sorted and merged; insert one new interval without re-sorting. Three linear phases: copy intervals ending before the new one starts, merge all overlapping intervals into the new one (expanding its start/end as you go), copy the remainder. `O(n)` time — the entire point is avoiding the `O(n log n)` re-sort.
3. **Meeting Rooms II (minimum rooms / max concurrency).** Not a merge — a concurrency count. Min-heap of active end times: for each meeting sorted by start, pop-while the heap's minimum end `<=` current start (that room freed up), then push the current meeting's end; the heap's peak size across the sweep is the answer. Equivalent sweep-line formulation: create `+1` events at each start and `-1` events at each end, sort all events by time (ties: process `-1` before `+1` at the same timestamp if a same-instant end/start doesn't count as overlapping), and track the running sum's maximum.
4. **Non-overlapping Intervals (minimum removals to eliminate all overlaps).** Sort by **end** time (not start). Greedily keep an interval whenever its start is `>=` the end of the last kept interval; every interval that fails this check must be removed. This is the classic activity-selection greedy, proven optimal by an exchange argument: any optimal solution can be transformed to also pick the earliest-ending compatible interval without reducing its size.
5. **Employee Free Time.** Flatten every employee's intervals into one list, run the base merge across the union, then the free time is exactly the gaps between consecutive merged blocks: for each adjacent pair `(merged[i], merged[i+1])`, if `merged[i+1].start > merged[i].end`, that gap is a free-time interval.

---

## Common bugs

- **Sorting by start when the problem needs a sort by end (Non-overlapping Intervals).** Sorting by start and greedily keeping the interval with the earliest start produces a wrong, smaller kept-set in cases where an early-starting interval is very long and blocks several short ones that would otherwise all fit.
- **Taking `last[1] = end` instead of `last[1] = max(last[1], end)`.** If the current merged block is `[1,10]` and the next interval is `[2,3]` (fully nested), a naive overwrite shrinks the merged end to 3, silently corrupting the result. This is the single most common bug in this pattern.
- **Off-by-one on the overlap boundary.** Whether touching intervals `[1,2]` and `[2,3]` should merge into `[1,3]` depends on the problem's stated semantics (closed vs half-open intervals); using `<` when the problem means `<=`, or vice versa, produces a result that's wrong only on adjacent-boundary test cases, which is exactly the case interviewers add to catch this.
- **Re-sorting and re-merging everything for Insert Interval.** It's correct but throws away the fact that the input was already sorted and merged, missing the `O(n)` linear-scan answer the interviewer is actually testing for.
- **In Meeting Rooms II, popping from the heap unconditionally instead of only when the top's end `<=` current start.** This either frees a room that's still in use (undercounting rooms needed) or never frees a room that has actually ended (overcounting).
- **In a sweep-line concurrency count, mishandling event ties** — if a meeting ends at time `t` and another starts at time `t`, whether that counts as needing two rooms depends on whether the interval is closed or half-open; processing `-1` events before `+1` events at the same timestamp treats an ending meeting as freeing the room before the new one needs it, which is usually — but not always — the intended semantics.

---

## Interview questions

### Q1 — Merge Intervals (LC56)
**Testing:** whether sorting by start is the reflexive first move.
**Answer:** Sort by start, linear sweep extending `end = max(end, next.end)` on overlap, else close and open a new block. `O(n log n)` time, `O(n)` output space.
**Follow-up trap:** *"Can you do the merge pass in less than O(n log n)?"* — no, not if the input is unsorted; the sort is the asymptotic bottleneck and can't be avoided for arbitrary input order. If the input is guaranteed pre-sorted, the merge pass alone is `O(n)`.

### Q2 — Insert Interval (LC57)
**Testing:** recognizing that a full re-sort is wasteful when the input is already sorted and merged.
**Answer:** Three linear phases — copy non-overlapping intervals ending before the new one, absorb all overlapping intervals into the new one's expanding bounds, copy the remaining non-overlapping intervals. `O(n)` time.
**Follow-up trap:** *"Why not just append the new interval and re-run your Merge Intervals solution?"* — that works and is easy to justify, but it's `O(n log n)` due to the re-sort, throwing away the fact that the array was already sorted; the interview-grade answer exploits that invariant for `O(n)`.

### Q3 — Meeting Rooms (LC252, boolean version)
**Testing:** the simplest form of "can a single person attend all meetings" — no overlap at all allowed.
**Answer:** Sort by start; if any interval's start is strictly less than the previous interval's end, return false. `O(n log n)`.
**Follow-up trap:** *"What if meeting A ends at 10 and meeting B starts at 10 — is that a conflict?"* — depends on whether the interval is closed or half-open in the problem statement; state your assumption explicitly rather than silently picking one, since this is exactly the boundary case interviewers probe.

### Q4 — Meeting Rooms II (LC253)
**Testing:** whether you can move from "merge" to "count concurrency," a genuinely different sub-problem.
**Answer:** Sort by start; min-heap of active end times; for each meeting, pop all heap entries with end `<= ` current start (rooms freed), then push the current meeting's end; the heap's peak size is the answer. `O(n log n)`.
**Follow-up trap:** *"Solve it without a heap."* — build `+1`/`-1` delta events at every start/end, sort combined events by time, sweep while tracking a running sum; the maximum value of that running sum is the answer, same complexity, no heap needed. Interviewers ask for this to see if you understand the heap wasn't essential, just convenient.

### Q5 — Non-overlapping Intervals (LC435)
**Testing:** whether you correctly identify this as a *different* sort key than the base merge problem.
**Answer:** Sort by **end** time; greedily keep an interval if its start `>=` the last kept interval's end; count and remove the ones that fail. `O(n log n)`.
**Follow-up trap:** *"Prove the greedy choice — always keeping the earliest-ending compatible interval — is optimal."* — exchange argument: take any optimal solution; if it doesn't include the earliest-ending interval among the first compatible choice, swap it in — it ends no later than whatever was there, so it can't reduce the number of subsequent compatible intervals, and the solution size is unchanged. This is the same proof structure as classical activity selection (Kleinberg & Tardos).

### Q6 — Employee Free Time (LC759)
**Testing:** composing the base merge across multiple pre-sorted-per-person lists.
**Answer:** Flatten all employees' intervals into one list, run the base merge, then report the gaps between consecutive merged blocks. `O(n log n)` where `n` is the total interval count across all employees.
**Follow-up trap:** *"Each employee's own schedule is already individually sorted — can you avoid a full O(n log n) re-sort of everything?"* — yes, via a k-way merge (min-heap keyed by each employee's next interval's start, one entry per employee) to produce the globally sorted order in `O(n log k)` where `k` is the number of employees, better than `O(n log n)` when `k << n`.

### Q7 — Interval List Intersections (LC986)
**Testing:** recognizing this is a two-pointer walk across two sorted lists, not a merge.
**Answer:** Two pointers, one per list; at each step compute `[max(a.start, b.start), min(a.end, b.end)]`, emit it if the range is valid (start `<=` end), then advance whichever interval has the smaller end (it can't intersect anything further).
**Follow-up trap:** *"Why advance the pointer with the smaller end, not the smaller start?"* — the interval with the smaller end has been fully "used up" against everything it could possibly intersect going forward (since both lists are sorted by start and this one ends first), so it's safe to discard; advancing by smaller start would risk skipping a still-relevant interval.

### Q8 — Remove Interval (LC1272)
**Testing:** the inverse of Insert Interval — subtracting a range instead of adding one.
**Answer:** For each interval, if it doesn't overlap the interval to remove, keep it unchanged; if it partially overlaps, split it into the surviving piece(s) (up to two pieces if the removed interval is fully contained inside it); if fully contained in the removed interval, drop it entirely. `O(n)`.
**Follow-up trap:** *"What if the interval to remove fully contains one of your intervals?"* — that interval must be dropped entirely, contributing zero output pieces; candidates who only handle the "partial overlap on one side" case miss full containment and either emit an invalid (start > end) interval or leave a stale one in the output.

### Q9 — Minimum Number of Arrows to Burst Balloons (LC452)
**Testing:** recognizing a disguised "minimum points to cover all intervals" problem, structurally identical to LC435's greedy.
**Answer:** Sort by end coordinate; greedily place an arrow at the end of the first unburst balloon, then skip every subsequent balloon whose start is `<=` that arrow's position (already burst); when a balloon starts after the current arrow, place a new arrow at its end. `O(n log n)`.
**Follow-up trap:** *"Isn't this the same greedy as Non-Overlapping Intervals?"* — yes, structurally: both sort by end and greedily commit to the earliest-ending option; the only difference is what "commit" means (keep an interval vs. place an arrow), which is worth saying out loud to demonstrate you see the shared skeleton rather than treating them as unrelated problems.

### Q10 — Data Stream as Disjoint Intervals (LC352)
**Testing:** the fully dynamic/online version — intervals arrive one at a time and the merged set must be queryable after every insertion.
**Answer:** Maintain a sorted structure (balanced BST / `TreeMap` in Java, `SortedList` in Python, or a self-balancing tree in Go) of disjoint merged intervals; each new value triggers a localized merge with its immediate neighbors only (at most one interval on each side), never a full re-scan. Amortized close to `O(log n)` per insertion for the neighbor lookups, though a merge can still cost `O(k)` for `k` intervals coalesced in one step.
**Follow-up trap:** *"Your batch Merge Intervals solution is O(n log n) once — why is that not good enough here?"* — because the data arrives incrementally and queries can be interleaved between insertions; re-sorting and re-merging the entire structure from scratch on every single insertion would cost `O(n log n)` *per insertion*, `O(n^2 log n)` total across `n` insertions, versus a design that only touches the locally affected neighbors each time.

### Q11 — Divide Intervals Into Minimum Number of Groups (LC2406)
**Testing:** recognizing this is Meeting Rooms II wearing a different name.
**Answer:** Identical to Meeting Rooms II — sort by start, min-heap (or sweep line) tracking peak concurrent overlap; the answer is the peak, which equals the minimum number of groups needed so no two intervals in the same group overlap.
**Follow-up trap:** *"Convince me this is really the same problem and not a coincidence."* — a "group" here is exactly a "room" there: both ask for the minimum number of parallel non-overlapping tracks needed to host all intervals without conflict, which is precisely the maximum number of intervals simultaneously active at any single point in time (a classical interval graph coloring result: the chromatic number of an interval graph equals its maximum clique size, computable via this same sweep).

---

## Red flags that fail you

- Sorting by start for Non-Overlapping Intervals or Minimum Arrows — both need a sort by **end** for the greedy proof to hold.
- Overwriting the merged end with the next interval's end instead of taking the max, silently corrupting results whenever a later interval is nested inside the current merged block.
- Re-sorting and re-merging the entire array for Insert Interval instead of the linear three-phase scan.
- Treating Meeting Rooms II as a merge problem and trying to answer it with the base merge template — it needs a concurrency count (heap or sweep line), not a merged interval list.
- Being unable to state, out loud, the boundary-condition assumption (does `[1,3]` and `[3,5]` count as overlapping) before writing code.
- Not noticing Interval List Intersections needs a two-pointer walk across two *separate* sorted lists rather than a single-list merge.

---

## Cheat card

```
SORT KEY        by START for merge/insert; by END for greedy-max-non-overlap (LC435, LC452)
OVERLAP TEST    next.start <= merged.end   (confirm <= vs < against problem's boundary semantics)
MERGE STEP      merged.end = max(merged.end, next.end)  -- never a plain overwrite
COMPLEXITY      O(n log n) total, sort-dominated; merge sweep itself is O(n)
INSERT INTERVAL 3 linear phases (before / merge-in / after) -- O(n), skip the re-sort
MEETING ROOMS 2 min-heap of end times, pop while top.end <= cur.start, track peak size
              (equivalent: +1/-1 sweep-line events, track running-sum peak)
NON-OVERLAP     sort by end, keep if start >= last_kept.end -- classical activity selection
INTERSECTION    two pointers across 2 sorted lists; advance whichever interval ends first
FREE TIME       merge the union of all schedules, gaps between merged blocks = free time
DYNAMIC/STREAM  balanced BST / TreeMap of disjoint intervals; merge only local neighbors
NOT THIS        2D rectangles need a geometry sweep with a different event model
```

## Sources
- [Merge Intervals — LeetCode](https://leetcode.com/problems/merge-intervals/) — accessed 2026-07-27
- [Insert Interval — LeetCode](https://leetcode.com/problems/insert-interval/) — accessed 2026-07-27
- [Meeting Rooms II — LeetCode](https://leetcode.com/problems/meeting-rooms-ii/) — accessed 2026-07-27
- [Non-overlapping Intervals — LeetCode](https://leetcode.com/problems/non-overlapping-intervals/) — accessed 2026-07-27
- [14 Patterns to Ace Any Coding Interview Question — LeetCode Discuss](https://leetcode.com/discuss/post/4039411/14-Patterns-to-Ace-Any-Coding-Interview-Question/) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
