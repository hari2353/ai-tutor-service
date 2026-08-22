# Pattern: Top-K Elements

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** heaps/priority queues, T02-p09-two-heaps
> **Module id:** `T02-p13-top-k` · **Tags:** pattern, heap, quickselect
> **Lab:** `labs/py/13-top-k/`

## The 30-second version

Top-K is "find the K largest/smallest/most-frequent items without fully sorting" — the moment you see "kth largest", "top K frequent", "K closest", the naive answer is sort-everything in O(n log n), and the pattern answer is a size-K heap in O(n log k), or QuickSelect in O(n) average when you only need the k-th element itself and don't need the other k-1 in order. The heap you pick is inverted from intuition: to find the K *largest*, you keep a *min*-heap of size K, because the smallest item in that heap is your current cutoff and the one you evict first. QuickSelect trades the heap's O(log k) per-element worst case for O(1) average amortized, at the cost of losing the streaming property and a worse worst case (O(n²) without randomization).

## Why this gets asked

It's the fastest way to check whether a candidate defaults to "sort it" out of habit or actually reasons about what the problem needs. Someone who has run a leaderboard, a top-N recommendation query, or a "most active users this hour" dashboard has felt the cost of sorting a 50M-row table to read off the top 20 — that's the production failure behind the question. It also tests a specific piece of counterintuitive reasoning (min-heap for the largest-K) that either you've internalized or you haven't, which makes it a clean pass/fail signal in five minutes.

---

## Lineage: past → present → future

**What came before.** Full sort is the naive baseline everyone reaches for first, and the pain it exposes is throwing away O(n log n) work to read off O(k) results when k is usually far smaller than n — sorting a million rows to get the top 10 wastes essentially the entire computation. The heap-based selection algorithm and Hoare's Quickselect (1961, a byproduct of his Quicksort paper) both predate modern interviewing by decades; they were designed for exactly this waste.

**Where it stands now.** The consensus split is clean and stable: use a bounded heap when the data is a stream you can't hold in memory, when k is much smaller than n, or when you need the running top-k at every point in time; use QuickSelect when you have the full array in memory, need only the k-th value (not a sorted top-k), and can tolerate its worse worst case. In production systems, neither runs raw — Redis's sorted sets, Elasticsearch's top-N aggregations, and most analytics engines implement bounded priority structures internally and expose them as a query primitive, so the "heap of size k" is usually a library call (`heapq.nlargest`, a `TopN` collector) rather than hand-rolled.

**Where it's heading.** Nothing methodologically new — this is closed 60-year-old algorithm design. The interesting movement is in distributed and approximate variants: for genuinely huge streams (think "top-1000 URLs by click count across a day of traffic"), exact top-k with a single heap doesn't scale across machines, and systems use approximate sketches (Count-Min Sketch plus a heap, or Space-Saving algorithm) that trade a small, bounded error for sublinear memory. Treat exact top-k as the interview answer and approximate sketches as the follow-up staff-level answer when volume is named explicitly.

---

## Mental model

```
Stream:  7  2  9  4  1  8  5  ...   find top-3

Min-heap of size 3 (root = smallest of the 3 kept so far = the cutoff):

  see 7 → heap [7]
  see 2 → heap [2,7]
  see 9 → heap [2,7,9]              (full — 3 kept)
  see 4 → 4 > root(2)? yes → pop 2, push 4 → heap [4,7,9]
  see 1 → 1 > root(4)? no  → discard
  see 8 → 8 > root(4)? yes → pop 4, push 8 → heap [7,8,9]
  see 5 → 5 > root(7)? no  → discard

  final heap = {7, 8, 9} = top-3, root(7) is the current 3rd-largest cutoff
```

The heap root is always the *worst* item currently inside the top-k set — it's the threshold you compare every new candidate against, and it's the first thing evicted when something better arrives. That's why a min-heap finds the largest-k: the root is the smallest of "the best k so far," which is exactly the number you need to beat.

---

## Recognition heuristics

- **"Find the k-th largest / smallest element"** — QuickSelect if given the full array once; a size-k heap if it's a stream or you need it maintained over time.
- **"Find the top-k / K most frequent"** — bucket by frequency first (or a hashmap counter), then heap or bucket-sort on frequency; never re-sort the whole frequency table when k is small.
- **"K closest points to origin / K closest to a target"** — max-heap of size k on distance, same inverted-heap logic as top-k largest.
- **A live/streaming qualifier** — "as data arrives", "maintain the top-k at every point", "running median" — heap, because it updates incrementally in O(log k); a full re-sort per event is disqualifying.
- **"Without fully sorting" or an explicit O(n log k) / O(n) time bound stated in the prompt** — the interviewer is telling you sort is the wrong-complexity answer.
- **k is small relative to n, or k is fixed while n grows** — heap of size k keeps memory at O(k) regardless of n, which matters when n doesn't fit in memory.
- **"Median of a stream" / "sliding window median"** — the two-heaps sub-pattern (see `T02-p09-two-heaps`), a close cousin: a max-heap for the lower half, a min-heap for the upper half, kept balanced.

---

## Template code (Python, Java, Go)

```python
import heapq
from collections import Counter

# Kth largest via min-heap of size k — O(n log k)
def kth_largest(nums: list[int], k: int) -> int:
    heap: list[int] = []
    for n in nums:
        heapq.heappush(heap, n)
        if len(heap) > k:
            heapq.heappop(heap)
    return heap[0]                       # root = kth largest

# Top-k frequent elements — bucket sort on frequency, O(n)
def top_k_frequent(nums: list[int], k: int) -> list[int]:
    counts = Counter(nums)
    buckets: list[list[int]] = [[] for _ in range(len(nums) + 1)]
    for val, freq in counts.items():
        buckets[freq].append(val)
    result = []
    for freq in range(len(buckets) - 1, 0, -1):
        for val in buckets[freq]:
            result.append(val)
            if len(result) == k:
                return result
    return result

# QuickSelect — kth largest in expected O(n), worst O(n^2)
import random
def quickselect_kth_largest(nums: list[int], k: int) -> int:
    target = len(nums) - k              # index of kth largest in sorted order
    lo, hi = 0, len(nums) - 1
    while True:
        pivot_idx = partition(nums, lo, hi)
        if pivot_idx == target:
            return nums[pivot_idx]
        elif pivot_idx < target:
            lo = pivot_idx + 1
        else:
            hi = pivot_idx - 1

def partition(nums: list[int], lo: int, hi: int) -> int:
    pivot_i = random.randint(lo, hi)     # randomize to avoid O(n^2) on adversarial input
    nums[pivot_i], nums[hi] = nums[hi], nums[pivot_i]
    pivot = nums[hi]
    store = lo
    for i in range(lo, hi):
        if nums[i] < pivot:
            nums[i], nums[store] = nums[store], nums[i]
            store += 1
    nums[store], nums[hi] = nums[hi], nums[store]
    return store
```

```java
// Java — Kth largest via min-heap of size k
public int kthLargest(int[] nums, int k) {
    PriorityQueue<Integer> heap = new PriorityQueue<>();   // min-heap by default
    for (int n : nums) {
        heap.offer(n);
        if (heap.size() > k) heap.poll();
    }
    return heap.peek();
}

// Top-k frequent — bucket sort on frequency
public int[] topKFrequent(int[] nums, int k) {
    Map<Integer, Integer> counts = new HashMap<>();
    for (int n : nums) counts.merge(n, 1, Integer::sum);
    List<Integer>[] buckets = new List[nums.length + 1];
    for (var e : counts.entrySet()) {
        int freq = e.getValue();
        if (buckets[freq] == null) buckets[freq] = new ArrayList<>();
        buckets[freq].add(e.getKey());
    }
    int[] result = new int[k];
    int idx = 0;
    for (int freq = buckets.length - 1; freq >= 1 && idx < k; freq--) {
        if (buckets[freq] == null) continue;
        for (int val : buckets[freq]) {
            result[idx++] = val;
            if (idx == k) break;
        }
    }
    return result;
}
```

```go
// Go — Kth largest via min-heap (container/heap)
type MinHeap []int

func (h MinHeap) Len() int            { return len(h) }
func (h MinHeap) Less(i, j int) bool  { return h[i] < h[j] }
func (h MinHeap) Swap(i, j int)       { h[i], h[j] = h[j], h[i] }
func (h *MinHeap) Push(x interface{}) { *h = append(*h, x.(int)) }
func (h *MinHeap) Pop() interface{} {
    old := *h
    n := len(old)
    v := old[n-1]
    *h = old[:n-1]
    return v
}

func kthLargest(nums []int, k int) int {
    h := &MinHeap{}
    heap.Init(h)
    for _, n := range nums {
        heap.Push(h, n)
        if h.Len() > k {
            heap.Pop(h)
        }
    }
    return (*h)[0]
}

// Top-k frequent — bucket sort on frequency
func topKFrequent(nums []int, k int) []int {
    counts := make(map[int]int)
    for _, n := range nums {
        counts[n]++
    }
    buckets := make([][]int, len(nums)+1)
    for val, freq := range counts {
        buckets[freq] = append(buckets[freq], val)
    }
    result := make([]int, 0, k)
    for freq := len(buckets) - 1; freq >= 1 && len(result) < k; freq-- {
        for _, val := range buckets[freq] {
            result = append(result, val)
            if len(result) == k {
                break
            }
        }
    }
    return result
}
```

## Complexity — derived, not asserted

**Heap of size k:** each of the `n` elements does at most one push and one pop against a heap bounded at size `k`, and each heap operation is `O(log k)` because the heap never grows past `k` — so total work is `O(n log k)`, strictly better than `O(n log n)` full sort whenever `k < n`, which is the entire point. Space is `O(k)`, independent of `n` — this is what makes it viable for streams that don't fit in memory.

**QuickSelect:** the recurrence for expected work is `T(n) = T(n/2) + O(n)` on average (a random pivot splits the remaining search range roughly in half and you only recurse into *one* side, unlike Quicksort which recurses into both) which solves to `T(n) = O(n)` by the same geometric-series argument as `n + n/2 + n/4 + ... = 2n`. Worst case is `O(n²)` if the pivot is always the min or max (e.g., an adversarial or already-sorted input with a naive last-element pivot) — random pivot selection makes this practically unreachable, but it's why interviewers ask you to randomize.

**Bucket sort on frequency:** frequencies are bounded by `n`, so allocating `n+1` buckets and one pass to place each of the (at most `n`) distinct values, then reading off from the top is `O(n)` total, better than sorting by frequency (`O(n log n)`) or a heap of all distinct values (`O(n log d)` where `d` is distinct count) when you don't need the entire frequency order, only the top-k slice.

---

## The 5 variants interviewers actually ask

1. **Kth largest in an array (LC 215).** Template: min-heap of size k, or QuickSelect if the whole array is given upfront and you don't need it sorted.
2. **Top-K frequent elements (LC 347).** Template modification: don't heap on the raw values — heap (or bucket) on `(frequency, value)` pairs after a counting pass; bucket sort wins outright since frequency is bounded by `n`.
3. **K closest points to origin (LC 973).** Template modification: heap key becomes squared Euclidean distance (avoid the sqrt, it's monotonic so unnecessary), max-heap of size k so you can evict the farthest when a closer point arrives.
4. **Kth smallest element in a sorted matrix (LC 378).** Template modification: this isn't a flat array — use a min-heap seeded with the first element of each row (or binary search on value range, which is O(n log(max-min)) and often preferred at scale); walking off the standard 1D top-k template here is a common trap since rows are individually sorted but the matrix isn't fully sorted.
5. **Sliding window / running median (two-heaps sub-pattern, LC 295/480).** Template modification: two balanced heaps (max-heap for the lower half, min-heap for the upper half) instead of one; every insertion may require rebalancing between the two heaps to keep sizes within one of each other. See `T02-p09-two-heaps` for the full derivation.

---

## Common bugs and how this pattern gets written wrong under pressure

- **Using a max-heap to find the k largest.** The intuitive-but-wrong instinct: "I want the largest, so max-heap." That gives you access to the single largest element cheaply but forces you to either hold *all* n elements in the heap (no space savings) or repeatedly pop-and-track which defeats the purpose. The correct structure is a min-heap capped at size k, where the root is the cutoff.
- **Forgetting to cap the heap at size k**, silently degrading to `O(n log n)` — a full heap with no eviction is just heapsort with extra steps.
- **Comparing the new element against the wrong thing** — comparing against the max instead of the heap's root (which after capping *is* the current minimum of the kept set) is a common off-by-logic error when translating "min-heap of the top-k" into code under time pressure.
- **Not randomizing the QuickSelect pivot**, leaving an implementation that's O(n) on random data in an interview's test cases but silently O(n²) on sorted or reverse-sorted input, which some interviewers deliberately include as a hidden test.
- **Forgetting partial results in the recursion after finding the pivot position** — QuickSelect must only recurse into the *one* side containing the target index, not both; recursing into both silently turns it back into full Quicksort's O(n log n) average (still correct, but it defeats the point of the pattern and signals you didn't understand why QuickSelect is faster).
- **Building a heap of all distinct values for top-k frequent** instead of bucket-sorting by frequency, missing the O(n) bound that's available because frequency counts are bounded by array length.
- **Using Euclidean distance with sqrt** in "K closest points," adding an unnecessary floating-point op — squared distance preserves order and avoids the sqrt entirely.

---

## Interview questions

### Q1 — Find the kth largest element in an unsorted array.
**Testing:** the core min-heap-for-largest inversion.
**Answer:** Maintain a min-heap capped at size k; push each element, pop when size exceeds k; the root after processing everything is the kth largest. O(n log k).
**Follow-up trap:** *"Can you do better than O(n log k)?"* — yes, QuickSelect averages O(n), but loses the streaming property and worst case degrades to O(n²) without a randomized pivot.

### Q2 — Why a min-heap and not a max-heap, for the k *largest* elements?
**Testing:** whether the inversion is understood or memorized.
**Answer:** The heap holds your current best-k candidates; its root must be the *worst* of them, because that's what a new, better candidate needs to beat and what gets evicted. A min-heap's root is the smallest — exactly the weakest member of your top-k set.
**Follow-up trap:** *"What if you wanted the k smallest instead?"* — invert it: max-heap of size k, root is the current largest of the kept set, evicted when something smaller arrives.

### Q3 — Top-K frequent elements — walk through both the heap and bucket-sort solutions and their complexities.
**Answer:** Heap: count frequencies with a hashmap (O(n)), then min-heap of size k on frequency (O(d log k) where d = distinct count). Bucket sort: allocate n+1 buckets indexed by frequency, place each distinct value in its frequency's bucket, then read top-down from the highest bucket until k values are collected — O(n) total since frequency is bounded by array length.
**Follow-up trap:** *"When would the heap actually be preferred over bucket sort?"* — when the stream is unbounded/live and you need the current top-k at every point without re-bucketing from scratch, since bucket sort as shown is a batch operation, not incremental.

### Q4 — Derive QuickSelect's average time complexity.
**Answer:** A random pivot partitions the array so, on average, about half the elements are eliminated from consideration each round, and you only recurse into the single side containing the target index (unlike Quicksort, which recurses into both). This gives the recurrence T(n) = T(n/2) + O(n), which sums to O(n) via the same geometric argument as n + n/2 + n/4 + ... → 2n.
**Follow-up trap:** *"What's the actual worst case and when does it happen?"* — O(n²), when the pivot is repeatedly the min or max of the remaining range, e.g., an adversarial or sorted array with a fixed (non-random) pivot choice such as always picking the last element. Randomizing the pivot makes this practically unreachable but doesn't change the theoretical worst case.

### Q5 — Kth smallest element in a row- and column-sorted matrix.
**Answer:** Two viable approaches: a min-heap seeded with the first element of every row, popping and pushing the next element in that row's sequence k times; or binary search on the value range [min, max], counting how many matrix elements are ≤ mid via a staircase walk, narrowing until you converge on the kth value. The heap approach is O(k log n) for an n×n matrix; binary search is O(n log(max-min)), often faster for large k.
**Follow-up trap:** *"Why can't you just flatten and use the 1D top-k template?"* — flattening loses the O(n) per-row/column sorted structure that lets you avoid looking at the whole matrix; a naive flatten-and-heap is O(n² log k), ignoring the structure the problem hands you for free.

### Q6 — K closest points to the origin.
**Answer:** Max-heap of size k keyed by squared distance (`x²+y²`, no sqrt needed since it's monotonic); push each point, pop the farthest when size exceeds k. O(n log k).
**Follow-up trap:** *"What if 'closest' meant closest to a moving target that updates each query?"* — you'd need to rebuild or re-key the heap per query, which is O(n log k) per query; for many repeated queries against a static point set, a k-d tree or ball tree amortizes better across queries.

### Q7 — Design a running "top 10 trending hashtags in the last hour."
**Testing:** transferring the pattern to a real streaming/production scenario.
**Answer:** A sliding time window (evict counts older than an hour, e.g., via a queue of timestamped increments or a time-bucketed count-min sketch) feeding a frequency map, with a min-heap of size 10 maintained incrementally as counts change; re-heapify only the affected entry rather than rebuilding from scratch on every event.
**Follow-up trap:** *"Millions of hashtags, memory is bounded — now what?"* — exact per-hashtag counting doesn't fit; use an approximate frequency sketch (Count-Min Sketch or the Space-Saving algorithm) to bound memory at the cost of a small, bounded overcount error, and keep only a bounded heap of current candidates rather than a live count for every hashtag ever seen.

### Q8 — Running median of a data stream.
**Answer:** Two heaps: a max-heap for the lower half of seen values, a min-heap for the upper half, rebalanced after each insertion so their sizes differ by at most one; the median is the top of the larger heap, or the average of both tops when sizes are equal. O(log n) per insertion, O(1) per median query.
**Follow-up trap:** *"What if the stream is huge and you need the median over only the last N elements (a sliding window)?"* — you now need to *remove* arbitrary elements from the heaps as they age out, which a standard binary heap doesn't support in O(log n); real implementations use lazy deletion (mark-as-stale and skip on pop) or an order-statistics tree / Fenwick tree over value buckets instead.

### Q9 — Sort a nearly-sorted (k-sorted) array where every element is at most k positions from its sorted position.
**Answer:** Min-heap of size k+1: push the first k+1 elements, then repeatedly pop the minimum (guaranteed correct since nothing more than k positions away could beat it) and push the next incoming element. O(n log k), and crucially O(k) space instead of O(n) for a full sort — this is a top-k pattern applied to a bounded-disorder sort rather than a literal "find the top k" ask.
**Follow-up trap:** *"How do you prove popping the min at each step is safe?"* — because any element that could be smaller than the current heap's minimum and appear later must be within k positions of where it belongs, and by the time you've seen k+1 elements, everything that could still beat the current min is already in the heap; nothing outside the window can be smaller.

### Q10 — You're asked to find the k-th largest element and the interviewer says "don't use a heap." What do you do?
**Testing:** whether QuickSelect is a second tool, not a memorized synonym for "the heap problem."
**Answer:** QuickSelect: partition around a random pivot, recurse only into the side containing the target rank, average O(n).
**Follow-up trap:** *"What if you can't mutate the input array?"* — either copy it first (O(n) extra space, defeats part of the appeal) or use the heap approach instead, which naturally doesn't require mutating the source; state this tradeoff explicitly rather than silently copying.

### Q11 — Merge k sorted lists to produce the overall top-k smallest values without merging everything.
**Testing:** recognizing the boundary with the K-Way Merge pattern (`T02-p14-k-way-merge`).
**Answer:** Min-heap seeded with the head of each list; pop the minimum, push that list's next element, repeat k times — you never merge the tails you don't need. This is the K-Way Merge pattern's early-termination variant, sharing the same heap machinery as top-k.
**Follow-up trap:** *"How is this different from full k-way merge?"* — full merge runs the heap until every list is exhausted (O(n log k) for n total elements); stopping after k pops is the top-k-specific optimization, valid only when you don't need the rest of the merged output.

---

## Red flags that fail you

- Reaching for a max-heap to find the k largest elements without noticing the inversion.
- Not knowing QuickSelect exists as an alternative to the heap.
- Proposing QuickSelect without randomizing the pivot, and not knowing why that matters.
- Sorting the whole array/frequency table when k is small and explicitly stated to be much less than n.
- Not recognizing when a problem needs the two-heaps median variant instead of a single bounded heap.
- Using sqrt for point-distance comparisons instead of squared distance.

---

## Cheat card

```
CORE INVERSION   want k LARGEST → min-heap size k (root = current cutoff, evict smallest)
                 want k SMALLEST → max-heap size k (root = current cutoff, evict largest)
HEAP COMPLEXITY  O(n log k) time, O(k) space — beats O(n log n) full sort when k << n
QUICKSELECT      partition around random pivot, recurse ONE side only
                 avg O(n): T(n)=T(n/2)+O(n) → geometric sum → O(n)
                 worst O(n^2) without randomized pivot (adversarial/sorted input)
TOP-K FREQUENT   counter + bucket sort on frequency (bounded by n) = O(n), beats heap-on-all-distinct
K CLOSEST POINTS max-heap size k on SQUARED distance (skip sqrt, monotonic)
KTH IN SORTED    heap seeded with row heads, OR binary search on value range O(n log(max-min))
                 MATRIX          matrix
RUNNING MEDIAN   two heaps: max-heap(lower half) + min-heap(upper half), rebalance to size diff <=1
K-SORTED ARRAY   min-heap of size k+1, pop-push streaming — O(n log k), O(k) space
STREAMING/HUGE   exact heap doesn't scale across machines/unbounded keys →
                 Count-Min Sketch / Space-Saving algorithm for approximate top-k
NEVER            full sort when only top-k is needed and k is explicitly small
```

## Sources

- [Kth Largest Element in an Array — LeetCode](https://leetcode.com/problems/kth-largest-element-in-an-array/) — accessed 2026-07-26
- [Top K Frequent Elements — LeetCode](https://leetcode.com/problems/top-k-frequent-elements/) — accessed 2026-07-26
- [Kth Smallest Element in a Sorted Matrix — LeetCode](https://leetcode.com/problems/kth-smallest-element-in-a-sorted-matrix/) — accessed 2026-07-26
- [K Closest Points to Origin — LeetCode](https://leetcode.com/problems/k-closest-points-to-origin/) — accessed 2026-07-26
- [Top K problems - Sort, Heap, and QuickSelect — LeetCode Discuss](https://leetcode.com/discuss/general-discussion/1088565/top-k-problems-sort-heap-and-quickselect/) — accessed 2026-07-26
- [What is the top K elements pattern for coding interviews? — DesignGurus](https://www.designgurus.io/answers/detail/what-is-the-top-k-elements-pattern-for-coding-interviews) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
