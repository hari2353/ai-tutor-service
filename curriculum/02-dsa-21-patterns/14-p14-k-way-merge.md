# Pattern: K-Way Merge

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** heaps/priority queues, merge sort, T02-p13-top-k
> **Module id:** `T02-p14-k-way-merge` · **Tags:** pattern, heap, merge
> **Practice:** the Problems tab in the app — this pattern has curated LeetCode problems rather than a lab

## The 30-second version

K-Way Merge is what you do when you have K already-sorted sequences (lists, streams, files) and need one combined sorted output: keep a min-heap of size K holding each sequence's current head, repeatedly pop the smallest, emit it, and push that sequence's next element. It's the generalization of the two-pointer merge step from merge sort to K inputs instead of 2, and it runs in O(N log K) for N total elements, versus O(NK) if you naively scan all K heads every time to find the minimum. The pattern shows up disguised as "merge k sorted linked lists", "smallest range covering elements from k lists", and "kth smallest in a sorted matrix" — anywhere the phrase "k sorted" appears alongside "merge" or "smallest/largest across all of them," reach for the heap-of-heads.

## Why this gets asked

Anyone who has built log aggregation, merged sharded and individually-sorted database result sets, or done an external sort on data too large for memory has implemented this exact loop for real. The interviewer wants to see whether you recognize that "merge K sorted things" is a different complexity class from "merge 2 sorted things" repeated K times — the naive pairwise-merge approach is a common wrong answer that looks reasonable but costs an extra factor of K in the total work, and catching that is the actual signal.

---

## Lineage: past → present → future

**What came before.** The two-way merge step is the load-bearing primitive of merge sort (von Neumann, 1945) — merge two sorted runs by repeatedly comparing their heads. The naive generalization to K sequences — scan all K heads each time to find the minimum — was the obvious first move and its pain is direct: that scan costs O(K) per output element, so for N total elements you pay O(NK), which is fine for K=2 but degrades badly as K grows (merging 100 shards of a sharded index, or the runs produced by an external sort, easily has K in the hundreds).

**Where it stands now.** Replacing the linear scan with a size-K min-heap is settled, decades-old technique — it's exactly how external sorting merges runs larger than memory (the classic multi-way external merge sort), how LSM-tree storage engines (LevelDB, RocksDB, Cassandra) merge sorted string tables (SSTables) during compaction, and how distributed query engines merge pre-sorted per-shard results. There's no live disagreement on the algorithm itself; the interesting engineering questions are all about K's practical size (a heap with K=1000 has meaningfully different cache behavior than K=4) and where the sequences physically live (in memory vs. needing paged I/O per sequence).

**Where it's heading.** Nothing algorithmically new is coming — the heap-of-heads is optimal in the comparison model and that won't change. What's evolving is the surrounding infrastructure: modern LSM engines increasingly use tiered/leveled compaction strategies that change *when* and *how many* SSTables get merged together to trade write amplification against read amplification, and vectorized/SIMD-accelerated merge implementations squeeze constant factors out of the comparison loop for very large K. Treat those as production nuance, not a different algorithm.

---

## Mental model

```
List A: 1 → 4 → 7
List B: 2 → 5 → 8
List C: 3 → 6 → 9

Min-heap holds current head of each list:  [1(A), 2(B), 3(C)]

pop 1(A) → emit 1 → push A's next (4)     heap: [2(B), 3(C), 4(A)]
pop 2(B) → emit 2 → push B's next (5)     heap: [3(C), 4(A), 5(B)]
pop 3(C) → emit 3 → push C's next (6)     heap: [4(A), 5(B), 6(C)]
pop 4(A) → emit 4 → push A's next (7)     ...
... continues until every list is exhausted

output: 1 2 3 4 5 6 7 8 9
```

The heap never holds more than K elements at once — one per active sequence — which is the whole efficiency story: you always know the global minimum in O(log K) instead of scanning K heads in O(K).

---

## Recognition heuristics

- **"Merge k sorted lists / arrays"** stated directly (LC 23) — the textbook case.
- **"Smallest range that includes at least one number from each of k lists"** (LC 632) — the heap tracks one pointer per list plus the running max, and the range shrinks by always advancing the list holding the current minimum.
- **"Kth smallest element in a sorted matrix"** (rows and columns individually sorted) — treat each row as one of the K sorted sequences.
- **"Find the smallest common element" or "median across k sorted arrays"** — same heap-of-heads shape, different termination condition.
- **A count K given explicitly alongside "sorted"** — if K is small and fixed (like "merge these 4 files"), heap-of-heads; if K is huge and the sequences are on disk, the same idea generalizes to external merge sort with I/O buffering per run.
- **Log/event merging across shards or services**, when framed as a systems question — "merge sorted-by-timestamp logs from N servers" is this pattern wearing a production costume.
- **Early-termination variant**: "find the k smallest elements across k sorted lists" (not the full merge) — this is the Top-K pattern's k-way variant; stop after k pops instead of exhausting every list (see `T02-p13-top-k` Q11).

---

## Template code (Python, Java, Go)

```python
import heapq

# Merge k sorted lists (as Python lists, not linked lists, for clarity)
def merge_k_sorted(lists: list[list[int]]) -> list[int]:
    heap = []
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst[0], i, 0))   # (value, list_idx, elem_idx)

    result = []
    while heap:
        val, list_i, elem_i = heapq.heappop(heap)
        result.append(val)
        if elem_i + 1 < len(lists[list_i]):
            next_val = lists[list_i][elem_i + 1]
            heapq.heappush(heap, (next_val, list_i, elem_i + 1))
    return result

# Kth smallest element across k sorted lists (early termination)
def kth_smallest_k_lists(lists: list[list[int]], k: int) -> int:
    heap = []
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst[0], i, 0))

    val = None
    for _ in range(k):
        val, list_i, elem_i = heapq.heappop(heap)
        if elem_i + 1 < len(lists[list_i]):
            heapq.heappush(heap, (lists[list_i][elem_i + 1], list_i, elem_i + 1))
    return val

# Smallest range covering at least one element from each of k lists (LC 632)
def smallest_range(lists: list[list[int]]) -> list[int]:
    heap = []
    current_max = float("-inf")
    for i, lst in enumerate(lists):
        heapq.heappush(heap, (lst[0], i, 0))
        current_max = max(current_max, lst[0])

    best = [float("-inf"), float("inf")]
    while True:
        val, list_i, elem_i = heapq.heappop(heap)
        if current_max - val < best[1] - best[0]:
            best = [val, current_max]
        if elem_i + 1 == len(lists[list_i]):
            break                              # one list exhausted, no wider coverage possible
        next_val = lists[list_i][elem_i + 1]
        current_max = max(current_max, next_val)
        heapq.heappush(heap, (next_val, list_i, elem_i + 1))
    return best
```

```java
// Java — merge k sorted linked lists (real ListNode, the LC 23 shape)
public ListNode mergeKLists(ListNode[] lists) {
    PriorityQueue<ListNode> heap = new PriorityQueue<>((a, b) -> a.val - b.val);
    for (ListNode node : lists) {
        if (node != null) heap.offer(node);
    }
    ListNode dummy = new ListNode(0);
    ListNode tail = dummy;
    while (!heap.isEmpty()) {
        ListNode smallest = heap.poll();
        tail.next = smallest;
        tail = tail.next;
        if (smallest.next != null) heap.offer(smallest.next);
    }
    return dummy.next;
}
```

```go
// Go — merge k sorted int slices
package main

import "container/heap"

type Item struct {
    val, listIdx, elemIdx int
}
type MinHeap []Item

func (h MinHeap) Len() int            { return len(h) }
func (h MinHeap) Less(i, j int) bool  { return h[i].val < h[j].val }
func (h MinHeap) Swap(i, j int)       { h[i], h[j] = h[j], h[i] }
func (h *MinHeap) Push(x interface{}) { *h = append(*h, x.(Item)) }
func (h *MinHeap) Pop() interface{} {
    old := *h
    n := len(old)
    v := old[n-1]
    *h = old[:n-1]
    return v
}

func mergeKSorted(lists [][]int) []int {
    h := &MinHeap{}
    heap.Init(h)
    for i, lst := range lists {
        if len(lst) > 0 {
            heap.Push(h, Item{lst[0], i, 0})
        }
    }
    result := []int{}
    for h.Len() > 0 {
        item := heap.Pop(h).(Item)
        result = append(result, item.val)
        if item.elemIdx+1 < len(lists[item.listIdx]) {
            next := lists[item.listIdx][item.elemIdx+1]
            heap.Push(h, Item{next, item.listIdx, item.elemIdx + 1})
        }
    }
    return result
}
```

## Complexity — derived, not asserted

Let `N` be the total number of elements across all K sequences. Each of the `N` elements is pushed onto the heap exactly once and popped exactly once, and the heap never holds more than `K` elements at a time (one per active sequence), so every push/pop is `O(log K)`. Total time is therefore **`O(N log K)`**. Compare this against the naive "scan all K heads to find the minimum" approach, which costs `O(K)` per output element and `O(NK)` total — for K=100 sequences merging a million total elements, that's the difference between roughly `N log(100) ≈ 6.6N` and `100N` operations, a 15x factor that only widens as K grows. Space is `O(K)` for the heap plus whatever output buffer you need; if merging in place (linked lists) you need no extra output storage beyond the heap itself.

For **smallest-range-covering-k-lists**, the same `O(N log K)` bound holds — you still push/pop each element once — with the extra bookkeeping of tracking the current maximum across all heap entries in O(1) per step (a running variable, not a second heap), since a second heap for the max would be redundant work.

---

## The 5 variants interviewers actually ask

1. **Merge k sorted linked lists (LC 23).** Template as shown directly: heap keyed on node value, holding one node reference per active list.
2. **Kth smallest element in a sorted matrix (LC 378).** Template modification: each matrix row is one of the k sequences; heap seeded with `(value, row, col=0)` triples, pop k times. (Shares this shape with the Top-K pattern — see `T02-p13-top-k` Q5 for the binary-search alternative.)
3. **Smallest range covering elements from k lists (LC 632).** Template modification: track a running current-maximum alongside the heap; every pop-push updates both the heap minimum and possibly the maximum, and the answer is the range with the smallest max-min span seen across all steps. Terminates early the moment any one list is exhausted, since no wider list can then contribute a new minimum.
4. **Merge k sorted arrays into one sorted array, memory-constrained (external sort framing).** Template modification: instead of holding full arrays in memory, each "sequence" is a buffered read cursor into a file on disk; the heap logic is identical, but pushing "the next element" triggers a disk read when a buffer empties. This is the systems-question version of the exact same pattern.
5. **Find the median of k sorted arrays combined.** Template modification: instead of merging everything, use the heap to advance to the `(N/2)`-th and `(N/2+1)`-th elements only (early termination like the Top-K variant), avoiding a full merge when you only need the middle one or two values.

---

## Common bugs and how this pattern gets written wrong under pressure

- **Doing pairwise merges of the k lists sequentially** (merge list 1+2, then merge that with 3, then with 4, ...) instead of a single k-way heap merge. This is correct but costs `O(NK)` in the worst case (each of the K-1 sequential merges touches up to N elements), not `O(N log K)` — a common wrong answer that "works" on small test cases and hides its complexity problem.
- **Pushing raw values onto the heap without tracking which list/index they came from.** Once you pop a value you need to know where to fetch its successor; forgetting the `(value, list_idx, elem_idx)` tuple (or storing node references directly, for linked lists) leaves you with no way to advance that sequence.
- **Heap comparison breaking on tuples with non-comparable second elements.** In Python, `heapq` compares tuples element-wise, so `(value, node)` breaks if two values tie and `node` objects aren't comparable — always include a tie-breaking index (`(value, list_idx, elem_idx)`) as the second element so ties resolve on an orderable int, never on the payload itself.
- **Forgetting to skip empty lists during heap initialization**, causing an index-out-of-bounds when trying to read a nonexistent head element.
- **In the smallest-range variant, using a second heap or full re-scan to track the current maximum** instead of a single running variable updated in O(1) — this silently reintroduces an extra log factor or a full-scan cost per step.
- **Stopping the smallest-range merge only when the heap is fully empty** instead of the moment any single list is exhausted — once one list runs out, its remaining potential contributions (which could only be larger values, since lists are sorted ascending) can never again form part of the minimal covering range, so continuing is wasted work and, worse, can miss the actual best answer if you exit at the wrong condition.

---

## Interview questions

### Q1 — Merge k sorted linked lists into one sorted list.
**Testing:** the base mechanism.
**Answer:** Min-heap seeded with the head of each list; repeatedly pop the smallest, append it to the output, and push its `.next` if one exists. O(N log K) time, O(K) heap space.
**Follow-up trap:** *"Why not just merge them two at a time, k-1 times?"* — that's correct but costs O(NK) in the worst case since each sequential merge can touch up to N elements; the heap does it in one pass at O(N log K).

### Q2 — What if K is enormous — say, merging 10,000 sharded, individually sorted result sets?
**Testing:** whether the pattern's constant factor and I/O reality register.
**Answer:** The heap itself stays O(log K) per operation, so algorithmically it's fine, but at K=10,000 you now care about cache locality of the heap array and whether each "sequence" requires a network round-trip or disk read to fetch its next element — buffer reads per shard rather than fetching one element at a time, or use a tournament tree (a variant with better cache behavior for very wide fan-in) if profiling shows the heap itself is the bottleneck.
**Follow-up trap:** *"Would you ever NOT do a full k-way merge here?"* — if you only need the top-N results (a paginated query), stop after N pops instead of merging everything, turning it into the Top-K pattern's early-termination variant.

### Q3 — Kth smallest element in an n×n matrix sorted ascending along rows and columns.
**Answer:** Treat each row as one of n sorted sequences; heap seeded with the first element of each row; pop k times, pushing each popped row's next element. O(k log n) time.
**Follow-up trap:** *"What's a better approach when k is close to n²?"* — binary search on the value range [min, max], counting elements ≤ mid via a staircase walk from the top-left or bottom-left corner in O(n) per check, giving O(n log(max-min)) total — faster than the heap when k is large because it doesn't scale with k at all.

### Q4 — Smallest range that includes at least one number from each of k sorted lists.
**Answer:** Heap holds the current head of each list plus a running current-maximum; at each step compute the range `[heap_min, current_max]`, record it if it's the smallest seen so far, then advance the list that contributed the current minimum. Stop the moment any one list is exhausted, since it can no longer contribute a next candidate. O(N log K).
**Follow-up trap:** *"Why does advancing the minimum's list (not any other) make progress toward a tighter range?"* — advancing any other list can only increase the max without changing the min, which never shrinks the range; only replacing the current minimum with that list's next (larger) value has a chance of raising the floor of the range while the ceiling stays controlled, which is the only direction that can tighten the span.

### Q5 — Merge k sorted arrays that are too large to fit in memory (external sort framing).
**Testing:** transferring the in-memory pattern to a systems/disk context.
**Answer:** Same heap-of-heads logic, but each "sequence" is a buffered read cursor into a file; when a sequence's in-memory buffer empties, refill it with the next chunk from disk. This is precisely how classical external merge sort combines runs larger than RAM, and how LSM-tree engines (LevelDB, RocksDB) merge SSTables during compaction.
**Follow-up trap:** *"What determines how many runs (K) you can merge in one pass?"* — available memory divided by the buffer size per run; if K exceeds what fits, you merge in multiple passes (merge K/2 at a time, then merge the results), trading I/O passes for memory — the same tradeoff that determines the "fan-in" of an external sort or the compaction strategy of an LSM tree.

### Q6 — Find the median of the combined elements across k sorted arrays without fully merging them.
**Answer:** Heap-of-heads, but only pop until you reach the `(N/2)`-th (and, if N is even, `(N/2+1)`-th) element, then stop — an early-termination variant of the same merge, avoiding the cost of producing the full merged output when only the middle values matter.
**Follow-up trap:** *"With only 2 arrays, is there a faster way?"* — yes, the classic O(log(min(m,n))) binary-search-on-partition algorithm for median of two sorted arrays is asymptotically much better than a heap merge, but it's a fundamentally different (partition-based, not merge-based) technique that doesn't generalize cleanly past k=2; naming that boundary is the senior signal.

### Q7 — Merge k sorted iterators/generators (Python) or streams where you can't know the length in advance.
**Answer:** Same heap logic, but the "push next element" step calls `next()` on the iterator and catches `StopIteration` to know when that sequence is exhausted, rather than checking an index bound against a known length — the algorithm is length-agnostic by construction.
**Follow-up trap:** *"What if one of the streams never terminates?"* — the merge itself is still correct and lazy (you only ever hold K elements in flight), but if you're materializing the *entire* output, that never terminates either; this only works as an infinite lazy generator itself, consumed on demand rather than collected into a list.

### Q8 — How does this pattern relate to merge sort itself?
**Answer:** Merge sort's combine step is the K=2 special case of this pattern — a two-pointer merge is a degenerate min-heap of size 2 (an if/else comparison instead of heap operations, since comparing 2 things doesn't need a heap). K-way merge generalizes that combine step to arbitrary K, which is exactly what a bottom-up iterative merge sort could do directly if it merged more than 2 runs per pass — most implementations stick to K=2 per merge step for simplicity, but external sorts routinely merge many runs per pass to reduce the number of I/O passes.
**Follow-up trap:** *"So why doesn't merge sort just use k-way merges as its standard combine step?"* — because K=2 keeps each merge step trivial (no heap overhead) and the O(log N) factor from repeated halving is already optimal for in-memory sort; k-way merging earns its keep specifically when I/O or network cost per pass dominates over comparison cost, which is why it shows up in external sort and distributed merges but not in a textbook in-memory merge sort.

### Q9 — Merge k sorted log streams from different servers by timestamp, in a live system.
**Testing:** the production-systems framing of the same algorithm.
**Answer:** Each server's stream is one sequence; a min-heap on timestamp merges them into one global chronological stream, with the added real-world wrinkle of clock skew between servers (two "sorted" streams may not be perfectly ordered relative to each other) and the need for backpressure if one server's stream is slow to produce data (block that heap slot rather than assume a value is available).
**Follow-up trap:** *"What happens if server C is 2 seconds behind on wall-clock but its next event should have come 'before' something you already emitted?"* — you've discovered why exactly-ordered global merge of independently-clocked streams is fundamentally approximate; production systems either buffer a small watermark/delay window before emitting (trading latency for a bounded out-of-order tolerance) or accept eventual/approximate ordering and reconcile downstream.

### Q10 — What's the smallest interval `[a, b]` such that every one of k sorted arrays has at least one element in `[a, b]`? Prove your termination condition is correct.
**Answer:** (Same as Q4's mechanism.) Prove: the range only needs checking when the heap minimum changes, since that's the only event that can tighten the lower bound; the upper bound only grows or stays the same as elements are pushed. The moment any list is fully consumed, no further minimum-advancing step is possible from that list, so the current best-so-far range is provably final — continuing would require a value from an exhausted list, which doesn't exist.
**Follow-up trap:** *"Could the answer ever come from a range checked before any list was exhausted, and would your loop have found it?"* — yes, and correctly so: the loop checks the range at *every* pop, not just at the end, precisely because the minimal range can occur at any intermediate state, not only the final one.

---

## Red flags that fail you

- Merging k lists pairwise/sequentially and not recognizing the extra factor of K that adds.
- Forgetting to track which source sequence a popped value came from, losing the ability to advance it.
- Using a second heap (or full rescan) to track a running maximum when a single variable suffices.
- Not knowing the O(N log K) vs O(NK) distinction cold, or why it matters as K grows.
- Confusing this pattern with plain Top-K when the problem needs the *entire* merged output, not just the top k values.
- No answer for what changes when the sequences don't fit in memory.

---

## Cheat card

```
CORE LOOP     min-heap holds current head of each of K sequences (value, seq_idx, elem_idx)
              pop smallest → emit → push that sequence's next element → repeat
COMPLEXITY    O(N log K) time, O(K) space  (N = total elements across all sequences)
              naive K-head linear scan = O(NK) — the wrong answer that "looks reasonable"
NEVER         pairwise-merge K lists sequentially — reintroduces the O(NK) factor
TIE-BREAK     always include a source index in the heap tuple; never compare raw
              non-orderable payloads (nodes) directly on tie
KTH IN MATRIX seed heap with row heads; pop k times — O(k log n)
              or binary search on value range — O(n log(max-min)), better for large k
SMALLEST      track running current-max (O(1) var, not a 2nd heap);
RANGE (632)   stop the instant ANY one list is exhausted — it can't help further
EXTERNAL SORT same heap logic, sequences = buffered disk/network cursors
              LSM engines (LevelDB/RocksDB) merge SSTables this way during compaction
RELATION      k-way merge = merge sort's 2-way combine step, generalized to K
EARLY STOP    only need top-N or the median? pop until you have what you need, not
              until every sequence is exhausted (shares this with Top-K pattern)
```

## Sources

- [Merge k Sorted Lists — LeetCode](https://leetcode.com/problems/merge-k-sorted-lists/) — accessed 2026-07-26
- [Smallest Range Covering Elements from K Lists — LeetCode](https://leetcode.com/problems/smallest-range-covering-elements-from-k-lists/) — accessed 2026-07-26
- [Kth Smallest Element in a Sorted Matrix — LeetCode](https://leetcode.com/problems/kth-smallest-element-in-a-sorted-matrix/) — accessed 2026-07-26
- [Top K problems - Sort, Heap, and QuickSelect — LeetCode Discuss](https://leetcode.com/discuss/general-discussion/1088565/top-k-problems-sort-heap-and-quickselect/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
