# Two Heaps

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-07-27
> **Module id:** `T02-p09-two-heaps` · **Tags:** pattern, heaps, streaming

## The 30-second version

Two Heaps maintains fast, continuously-updated access to a running median (or, more generally, an arbitrary running percentile) over a data stream by splitting all elements seen so far into a max-heap holding the smaller half and a min-heap holding the larger half, and enforcing that the two heaps' sizes never differ by more than one. Because of that balance invariant, the median is always available in O(1) by peeking at the top of one or both heaps, while each new insertion costs O(log n) to push into the correct heap and, if needed, rebalance by moving one element across. This is a fundamentally different problem from finding the median of a static, already-collected array (which is a one-shot O(n) quickselect problem) — the moment new elements keep arriving and you need the median after *every* insertion, re-sorting or re-selecting from scratch on each arrival is too slow, and two heaps is the standard incremental structure that avoids it. Recognize it from "median from a data stream," "running median," "sliding window median," or any streaming-percentile tracking problem — and note heaps don't natively support removing an arbitrary (non-top) element in O(log n), which is exactly what makes the sliding-window variant harder than the unbounded-stream base case.

## Why this gets asked

The interviewer wants to see whether you recognize that "compute the median" changes character entirely once it's asked *incrementally* rather than once on a fixed dataset — candidates who only know the batch quickselect/sort answer default to re-sorting after every insertion, which is O(n log n) per insertion and O(n^2 log n) over a full stream, versus O(log n) per insertion with two heaps. This maps directly to a real production problem: tracking live percentiles (p50, p95, p99 latency) on a metrics dashboard or a streaming leaderboard requires an incremental structure, not a batch recomputation, because the volume of updates makes re-sorting infeasible at scale. The sharper follow-up that separates levels is Sliding Window Median, because a plain heap has no efficient way to remove an element that's about to fall out of the window if it isn't at the top — forcing a choice between lazy deletion (tracking pending removals and skipping stale heap tops) and abandoning heaps altogether for an order-statistics structure, which tests whether you understand the limits of the data structure you just reached for, not just its happy path.

---

## Lineage: past → present → future

**What came before.** Computing the median of a fixed, already-collected dataset is a classical selection problem: full sort costs O(n log n); the median-of-medians algorithm (Blum, Floyd, Pratt, Rivest, and Tarjan, 1973 — often called BFPRT) gives a deterministic O(n) worst-case selection algorithm, and randomized quickselect gives expected O(n). Both are batch algorithms — they assume all the data is available up front and you compute the answer once. The pain that motivated a different structure was streaming: logging systems, live dashboards, and online leaderboards need the current median *after every single new data point*, and re-running a full O(n) or O(n log n) selection on every arrival is wasteful when only one element has changed since the last computation.

**Where it stands now.** Two heaps (sometimes called a "median heap" or "double-ended heap") is the standard textbook and interview answer for exact, incremental median tracking, and there's no disagreement about the core technique for the base problem. In production, however, systems tracking percentiles at genuinely large, distributed scale increasingly reach for **approximate mergeable sketches** instead of an exact two-heap structure — t-digest (Ted Dunning, 2013) and DDSketch (Datadog, 2019) are widely used specifically because they support bounded memory, configurable accuracy, and — critically — mergeability across distributed shards, which an exact two-heap structure does not support natively (merging two independent two-heap structures from different machines isn't a simple operation). This is a live, practical tradeoff: exact two heaps for a single-process, in-memory stream; approximate sketches once the data is distributed or the volume makes exact tracking too expensive.

**Where it's heading.** Expect continued emphasis on the "why not just keep the whole stream sorted" and "why does this not scale to a distributed system" follow-ups, since both test whether the tradeoff is understood rather than just the mechanism memorized. The sliding-window variant's lazy-deletion trick (or falling back to an order-statistics tree / Fenwick-tree-based rank structure) is likely to remain the standard "harder sibling" question, since it's the natural next question once the base pattern is established and it exposes a genuine limitation of heaps as a data structure.

---

## Mental model

```
Stream arrives: 5, 15, 1, 3

max-heap (small half, top = LARGEST of the small half)
min-heap (large half, top = SMALLEST of the large half)

insert 5:  max-heap=[5]              min-heap=[]
insert 15: compare to max-heap top(5): 15 > 5 -> goes toward large half
           max-heap=[5]              min-heap=[15]
insert 1:  compare to max-heap top(5): 1 <= 5 -> goes toward small half
           max-heap=[5,1]            min-heap=[15]
           rebalance: sizes differ by 1 (2 vs 1) -- still within tolerance, OK
insert 3:  compare to max-heap top(5): 3 <= 5 -> goes toward small half
           max-heap=[5,1,3]          min-heap=[15]
           rebalance: sizes differ by 2 (3 vs 1) -- move max-heap's top (5) to min-heap
           max-heap=[3,1]            min-heap=[5,15]

median: sizes equal (2,2) -> average of max-heap top (3) and min-heap top (5) = 4.0

Visual:
   small half (max-heap)   |   large half (min-heap)
      1   3                |    5    15
          ^ top=3 (largest of small half)
                                ^ top=5 (smallest of large half)
   median sits exactly between these two tops
```

The invariant that makes O(1) median access possible: **every element in the max-heap is `<=` every element in the min-heap, and the two heap sizes differ by at most 1.** Insertion always risks breaking one of these two properties, so every insert is followed by a check-and-fix step.

---

## Recognition heuristics

- **"Find median from a data stream" / "running median" / "continuous median"** — the base pattern by name.
- **"Sliding window median"** — two heaps plus a mechanism for removing elements that fall out of the window; a plain heap can't remove an arbitrary element in O(log n), so this requires lazy deletion (mark an element as stale, skip it when it surfaces at a heap's top) or falling back to a different structure entirely (order-statistics BST, Fenwick tree over compressed value ranks).
- **Two competing pools where you need the best-of-pool-A and best-of-pool-B simultaneously, and elements migrate between pools as state changes** — IPO/Maximize Capital (a min-heap of "not yet affordable" projects by required capital, a max-heap of "currently affordable" projects by profit, projects migrating from the first heap to the second as available capital grows).
- **Streaming event problems needing simultaneous "how many things have started" and "how many things have ended" bookkeeping** — dual heaps of start-events and end-events, often combined with binary search over a query time.
- **You need not just the median but an arbitrary percentile (p90, p99) tracked incrementally** — the same two-heap idea generalizes by keeping the heap-size ratio at `p : (1-p)` instead of `50:50`, still giving O(1) access to that percentile's value at the boundary between the two heaps.

**Anti-signal:** "kth largest element in a stream" (LC703) is a *single*-heap problem (a min-heap capped at size `k`, see `T02-p13-top-k`), not two heaps — don't conflate "track the top k elements" with "split all elements into two balanced halves for median access," they solve different questions with different heap structures. Similarly, "median of two sorted arrays" (LC4) sounds like this pattern but is efficiently solved by binary search over the shorter array's partition point in O(log(min(m,n))), not by heaps at all — the arrays are already sorted and static, so there's no streaming insertion to justify a heap-based incremental structure.

---

## Template code (Python, Java, Go)

Running median tracker — the reusable skeleton for the family:

**Python**
```python
import heapq

class MedianFinder:
    """O(log n) insert, O(1) median query. Python's heapq is min-heap only,
    so the 'small half' max-heap is simulated by negating values."""

    def __init__(self):
        self.small = []   # max-heap via negation: stores -value
        self.large = []   # min-heap: stores value directly

    def add_num(self, num: int) -> None:
        # Push to small (negated) first, then always cross-move the best of
        # small into large to guarantee the ordering invariant holds.
        heapq.heappush(self.small, -num)
        heapq.heappush(self.large, -heapq.heappop(self.small))

        # Rebalance sizes: large may now have one too many.
        if len(self.large) > len(self.small):
            heapq.heappush(self.small, -heapq.heappop(self.large))

    def find_median(self) -> float:
        if len(self.small) > len(self.large):
            return -self.small[0]
        return (-self.small[0] + self.large[0]) / 2.0
```

**Java**
```java
class MedianFinder {
    private final PriorityQueue<Integer> small = new PriorityQueue<>(Collections.reverseOrder()); // max-heap
    private final PriorityQueue<Integer> large = new PriorityQueue<>(); // min-heap

    public void addNum(int num) {
        small.offer(num);
        large.offer(small.poll());        // cross-move best of small into large
        if (large.size() > small.size()) {
            small.offer(large.poll());    // rebalance
        }
    }

    public double findMedian() {
        if (small.size() > large.size()) return small.peek();
        return (small.peek() + large.peek()) / 2.0;
    }
}
```

**Go**
```go
// container/heap requires implementing heap.Interface; MaxHeap and MinHeap
// are two thin wrappers around []int with inverted Less() for MaxHeap.
type MaxHeap []int
func (h MaxHeap) Len() int            { return len(h) }
func (h MaxHeap) Less(i, j int) bool  { return h[i] > h[j] } // inverted: largest on top
func (h MaxHeap) Swap(i, j int)       { h[i], h[j] = h[j], h[i] }
func (h *MaxHeap) Push(x interface{}) { *h = append(*h, x.(int)) }
func (h *MaxHeap) Pop() interface{} {
	old := *h
	n := len(old)
	x := old[n-1]
	*h = old[:n-1]
	return x
}

type MinHeap []int
func (h MinHeap) Len() int            { return len(h) }
func (h MinHeap) Less(i, j int) bool  { return h[i] < h[j] }
func (h MinHeap) Swap(i, j int)       { h[i], h[j] = h[j], h[i] }
func (h *MinHeap) Push(x interface{}) { *h = append(*h, x.(int)) }
func (h *MinHeap) Pop() interface{} {
	old := *h
	n := len(old)
	x := old[n-1]
	*h = old[:n-1]
	return x
}

type MedianFinder struct {
	small *MaxHeap
	large *MinHeap
}

func (mf *MedianFinder) AddNum(num int) {
	heap.Push(mf.small, num)
	heap.Push(mf.large, heap.Pop(mf.small))
	if mf.large.Len() > mf.small.Len() {
		heap.Push(mf.small, heap.Pop(mf.large))
	}
}

func (mf *MedianFinder) FindMedian() float64 {
	if mf.small.Len() > mf.large.Len() {
		return float64((*mf.small)[0])
	}
	return float64((*mf.small)[0]+(*mf.large)[0]) / 2.0
}
```

---

## Complexity, derived

Each insertion performs a constant number of heap push/pop operations (one push into `small`, one pop-and-push to cross into `large`, and at most one more pop-and-push to rebalance), and each individual heap operation on a heap of size `m` costs `O(log m)` to maintain the heap property (sift-up/sift-down through at most `log2(m)` levels). So a single insertion is **O(log n)**, and processing an entire stream of `n` elements is **O(n log n)** total — versus a naive "keep a sorted array/list and binary-insert" approach, where finding the insertion point is `O(log n)` via binary search but the actual insertion requires shifting up to `n` elements to maintain sorted order, making each insert **O(n)** and the whole stream **O(n^2)**. Median query is **O(1)**, just peeking at one or two heap tops, no traversal required — this is the entire point of maintaining the balance invariant. Space is **O(n)** to hold all elements across both heaps. For the sliding-window variant, a naive removal of an arbitrary (non-top) element from a heap costs **O(n)** (linear scan to find it, since heaps only guarantee fast access to the top), which would make the window-slide step the bottleneck; lazy deletion avoids this by deferring actual removal until the stale element happens to surface at a heap's top, at which point it's discarded in **O(log n)** — turning an O(n) worst-case removal into an amortized O(log n) one.

---

## The 5 variants interviewers actually ask

1. **Find Median from Data Stream (LC295).** The base pattern exactly as described above: max-heap for the small half, min-heap for the large half, rebalance after every insert.
2. **Sliding Window Median (LC480).** Modification: elements must also be removable as the window slides. Since heaps don't support efficient arbitrary removal, use lazy deletion — maintain a count of "pending removals" per value (e.g., in a hash map), and whenever a heap's top is a value marked for removal, pop and discard it before trusting the top as the true current extreme.
3. **IPO / Maximize Capital (LC502).** Modification: two heaps with entirely different semantics than median-splitting — a min-heap of "locked" projects ordered by required capital (so you can efficiently find the cheapest project to unlock next) and a max-heap of "currently unlocked/affordable" projects ordered by profit (so you can greedily pick the most profitable one available). After each pick, capital increases, potentially unlocking more projects from the locked heap, which must be moved into the unlocked heap before the next greedy pick.
4. **Number of Flowers in Full Bloom (LC2251).** Modification: two heaps of *events* rather than values — a min-heap (or sorted array) of bloom start times and a min-heap (or sorted array) of bloom end times — combined with binary search over a given query time to count how many flowers have started blooming but not yet finished by that time.
5. **Arbitrary Percentile Tracking (generalization beyond the median).** Modification: instead of keeping the two heaps balanced 50:50, keep their size ratio at `p : (1-p)` for a target percentile `p` (e.g., a 90:10 split for tracking p90 latency incrementally); the value at the boundary between the two heaps is always the current p-th percentile, updated in O(log n) per new data point — directly the technique behind lightweight in-process latency-percentile tracking on a metrics dashboard.

---

## Common bugs

- **Letting the heap sizes drift apart by more than 1.** The O(1) median guarantee depends entirely on the size invariant; forgetting the rebalance step after an insert (or rebalancing conditionally instead of unconditionally checking every time) breaks median correctness silently rather than crashing.
- **Forgetting Python's `heapq` is min-heap only.** Simulating a max-heap by negating values on push and negating again on read is required; forgetting to negate on read (or negating twice) produces silently wrong medians rather than an error.
- **Miscomputing the median for odd vs. even total counts.** When the two heaps are equal in size, the median is the average of both tops; when one heap has exactly one more element (by the size-difference-of-at-most-1 invariant, that heap must be `small`), the median is just that heap's top alone — mixing these up is a frequent off-by-one.
- **Inserting a new value directly into whichever heap "seems right" by comparing it only to the current median, without the cross-heap-push-and-pop discipline.** The robust algorithm always pushes into one heap first, then unconditionally moves that heap's extreme into the other heap, then rebalances sizes — this three-step discipline is what correctly handles edge cases that a naive single comparison misses.
- **Attempting to remove an arbitrary element directly from a heap for the sliding-window variant.** Heaps only expose fast access to the top; removing a non-top element requires an O(n) linear scan unless you use lazy deletion (or abandon heaps for an order-statistics structure) — reaching for `heap.remove(value)` and assuming it's O(log n) is a common and costly mistake.
- **Conflating this pattern with Top-K Elements.** A single min-heap capped at size `k` (Top-K, see `T02-p13-top-k`) answers a completely different question ("what are the k largest/smallest seen so far") than two balanced heaps answering "what's the value exactly in the middle of everything seen so far."

---

## Interview questions

### Q1 — Find Median from Data Stream (LC295)
**Testing:** the base two-heap mechanism and the balance invariant.
**Answer:** Max-heap for the small half, min-heap for the large half; push-then-cross-move-then-rebalance on every insert; median from the top(s) in O(1).
**Follow-up trap:** *"Why not just keep a sorted list and binary-insert each new value?"* — binary search finds the insertion point in O(log n), but the actual insertion into a sorted array/list requires shifting up to n elements, making each insert O(n) and the whole stream O(n^2); two heaps avoid the shifting cost entirely by only ever touching O(log n) elements per insert.

### Q2 — Sliding Window Median (LC480)
**Testing:** whether you recognize a heap's fundamental limitation (no cheap arbitrary removal) and design around it.
**Answer:** Two heaps as in the base pattern, plus a hash map tracking pending removals by value; when a window slide requires removing an element, mark it for lazy deletion instead of removing it immediately, and discard stale entries whenever they surface at a heap's top during a subsequent operation.
**Follow-up trap:** *"What if two equal values are in the window and only one needs to be removed?"* — lazy deletion by value with a per-value pending-removal counter (not a boolean flag) handles this correctly: decrement the counter for that value's slot, and only actually discard a heap-top entry matching a value whose pending-removal counter is still positive.

### Q3 — IPO / Maximize Capital (LC502)
**Testing:** recognizing a two-heap structure serving a completely different purpose than median-splitting.
**Answer:** Min-heap of locked projects by required capital; max-heap of currently affordable projects by profit; repeatedly move newly-affordable projects from the locked heap into the affordable heap, then greedily pop the most profitable affordable project, updating capital, for up to `k` rounds.
**Follow-up trap:** *"What if, after picking a project, multiple previously-locked projects become affordable at once?"* — the unlock step must be a loop (`while locked heap's cheapest project's capital requirement <= current capital: move it to the affordable heap`), not a single conditional check, since one profit gain can unlock several projects simultaneously.

### Q4 — Number of Flowers in Full Bloom (LC2251)
**Testing:** using dual heaps (or sorted structures) of *events* rather than of raw values.
**Answer:** Sort/heap start times and end times separately; for a given query time, binary search each to count how many flowers have started blooming by that time and how many have already finished, and subtract.
**Follow-up trap:** *"Do you need actual heaps here, or would sorted arrays plus binary search suffice?"* — for a batch of queries processed after seeing all flowers, sorted arrays with binary search are simpler and equally efficient (O(log n) per query); heaps earn their keep specifically when insertions are interleaved with queries in an online/streaming fashion, which isn't the case in this problem's typical framing — worth stating explicitly rather than reflexively reaching for heaps everywhere "median/interval" appears.

### Q5 — Generalize to p90/p99 latency tracking for a metrics dashboard
**Testing:** whether the median-specific 50:50 balance generalizes in your mental model, or whether you've only memorized the exact-median case.
**Answer:** Keep the heap-size ratio at roughly `p : (1-p)` instead of `50:50`; the boundary value between the two heaps is the running p-th percentile, updated in O(log n) per new data point, same mechanism as the median case with a different target ratio.
**Follow-up trap:** *"This needs to run across a fleet of 500 machines and be mergeable centrally — is exact two-heap tracking still the right tool?"* — no; exact two-heap structures from independent machines don't merge cleanly into a single combined structure, which is exactly why production systems at that scale use approximate, explicitly mergeable sketches like t-digest or DDSketch instead, trading exactness for bounded memory and mergeability.

### Q6 — Median of Two Sorted Arrays (LC4)
**Testing:** whether "median" reflexively triggers two heaps even when the input is already fully sorted and static.
**Answer:** Binary search over the partition point in the shorter array, checking that the max of the left partitions is `<=` the min of the right partitions across both arrays; O(log(min(m,n))).
**Follow-up trap:** *"Why not use two heaps here, since it's a median problem?"* — there's no streaming insertion to justify an incremental structure; both arrays are already fully available and sorted, so a direct O(log(min(m,n))) binary-search partition beats building and maintaining O(m+n) heaps for a one-shot computation.

### Q7 — Kth Largest Element in a Stream (LC703)
**Testing:** the specific anti-signal — distinguishing two-heaps median tracking from single-heap top-k tracking.
**Answer:** A single min-heap capped at size `k`; if a new value exceeds the heap's current minimum (once the heap is full), pop the minimum and push the new value; the heap's top is always the k-th largest seen so far.
**Follow-up trap:** *"Isn't this basically the same idea as two heaps?"* — no; two heaps split *every* element into two balanced groups to expose the middle value, while this problem only ever needs to retain the top `k` elements and can safely discard everything smaller, requiring just one bounded-size heap, not a balanced pair.

### Q8 — Prove the balance invariant is sufficient for O(1) median access
**Testing:** whether you can justify the invariant rather than just implement it.
**Answer:** If every element in `small` is `<=` every element in `large`, and `|len(small) - len(large)| <= 1`, then the overall sorted order is exactly `small`'s elements (in some order) followed by `large`'s elements (in some order); the median position(s) of the full combined set always fall exactly at the boundary between the two heaps, i.e., at `small`'s max (its top) and/or `large`'s min (its top), which is precisely what both heap types expose in O(1).
**Follow-up trap:** *"What if you allowed the size difference to grow to 2 instead of enforcing at most 1?"* — the median could then require looking one element deeper than either heap's top (e.g., the 2nd-from-top of the larger heap), which heaps don't expose in O(1) — the strict at-most-1 tolerance is exactly the minimum slack that keeps the answer at the top, not one level down.

### Q9 — Removing an arbitrary element from a heap in general
**Testing:** whether you understand this as a structural limitation of heaps, applicable beyond just the sliding-window variant.
**Answer:** A binary heap only guarantees O(log n) access to its extreme (top) element; finding an arbitrary non-top element requires an O(n) linear scan (heaps aren't sorted, only partially ordered), so true O(log n) arbitrary removal isn't natively supported without extra bookkeeping (an auxiliary hash map from value to heap index, updated on every swap during sift operations — which most standard library heap implementations, including Python's `heapq` and Java's `PriorityQueue`, do not provide out of the box).
**Follow-up trap:** *"Is there a data structure that natively supports both O(log n) insertion and O(log n) arbitrary removal, if you needed that instead of lazy deletion?"* — a balanced BST (or an order-statistics tree/Fenwick tree over compressed ranks) supports both in O(log n) directly, at the cost of more implementation complexity and typically worse constant factors than a plain heap for the common case where arbitrary removal isn't needed.

### Q10 — Design a running median tracker that also supports "remove a specific past value" in true O(log n), not amortized
**Testing:** pushing past lazy deletion to a data-structure-selection question under a stricter requirement.
**Answer:** Replace both heaps with a single order-statistics structure (a balanced BST augmented with subtree-size counts, or two Fenwick trees over compressed value ranks — one tracking counts, one tracking sums) that supports O(log n) insM, O(log n) exact removal by value, and O(log n) "find the k-th smallest" queries, which gives the median (and, with the ratio generalization, any percentile) directly without ever relying on amortization.
**Follow-up trap:** *"Why would you ever choose the amortized lazy-deletion two-heap approach over this strictly-bounded structure, if this one is strictly better?"* — the order-statistics structure is meaningfully more complex to implement correctly (especially the augmented-BST version) and has worse constant factors in practice for the common case where removals are rare or absent; lazy deletion with two heaps is simpler code with the same asymptotic bound in the amortized sense, and amortized O(log n) is often good enough when removal frequency is low relative to insertion frequency.

---

## Red flags that fail you

- Letting heap sizes drift apart by more than 1, silently breaking O(1) median correctness.
- Forgetting Python's `heapq` is min-heap only and mishandling the negation trick for the max-heap half.
- Getting the odd/even total-count median formula backward (averaging when one heap has the extra element, or taking a single top when they're equal).
- Reaching for `heap.remove(value)` in a sliding-window variant and assuming it's O(log n) without acknowledging the O(n) reality or the lazy-deletion workaround.
- Reflexively reaching for two heaps on Median of Two Sorted Arrays without recognizing the input is already sorted and static, making binary search strictly better.
- Conflating this pattern with Top-K Elements' single bounded-size heap.

---

## Cheat card

```
STRUCTURE       max-heap = SMALL half (top = largest of small half)
                min-heap = LARGE half (top = smallest of large half)
INVARIANT       every small-heap element <= every large-heap element; |size diff| <= 1
INSERT ALGO     push to small -> pop small's top into large -> if large bigger, pop its top back to small
MEDIAN QUERY    O(1): equal sizes -> avg of both tops; small has extra -> small's top alone
COMPLEXITY      O(log n) insert, O(1) query, O(n log n) total for n elements
                vs sorted-array binary-insert: O(log n) find + O(n) SHIFT = O(n) insert, O(n^2) total
PYTHON GOTCHA   heapq is min-heap only -- negate on push AND on read for the max-heap half
SLIDING WINDOW  heaps can't remove arbitrary elements in O(log n) natively -> LAZY DELETION
                (pending-removal counter per value; discard stale tops when they surface)
IPO VARIANT     min-heap(locked, by capital) + max-heap(unlocked, by profit); unlock in a LOOP, not once
GENERALIZE      p-th percentile: keep heap-size ratio p:(1-p) instead of 50:50
NOT THIS        Top-K (single bounded min-heap, size k) != Two Heaps (split ALL elements into 2 halves)
NOT THIS        Median of Two Sorted Arrays: already sorted+static -> binary search O(log(min(m,n))), no heaps
AT SCALE        exact two-heap doesn't merge across distributed shards -> t-digest/DDSketch instead
```

## Sources
- [Find Median from Data Stream — LeetCode](https://leetcode.com/problems/find-median-from-data-stream/) — accessed 2026-07-27
- [Sliding Window Median — LeetCode](https://leetcode.com/problems/sliding-window-median/) — accessed 2026-07-27
- [IPO — LeetCode](https://leetcode.com/problems/ipo/) — accessed 2026-07-27
- [Number of Flowers in Full Bloom — LeetCode](https://leetcode.com/problems/number-of-flowers-in-full-bloom/) — accessed 2026-07-27
- [Median of Two Sorted Arrays — LeetCode](https://leetcode.com/problems/median-of-two-sorted-arrays/) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
