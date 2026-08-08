# Modified Binary Search

> **Track:** T02 DSA: 21 Patterns · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-07-27
> **Module id:** `T02-p11-binary-search` · **Tags:** pattern, binary-search, predicate

## The 30-second version

Binary search's real generalization, the one that actually separates senior candidates, has nothing to do with arrays: it applies to *any* search space where you can define a boolean predicate `f(x)` that is false for a contiguous prefix and true for a contiguous suffix (or vice versa) over an ordered domain — a monotonic predicate. Once that monotonicity holds, you can find the exact boundary in `O(log(range))` probes regardless of whether the "array" is a literal sorted list, an implicit range of integers (`1` to `10^9` possible answers), or a real-valued interval. This is "binary search on the answer": instead of searching *for* a value in a data structure, you search *over the space of candidate answers* for the smallest (or largest) one for which some feasibility check returns true, and that feasibility check is very often not O(1) — it's frequently an O(n) simulation or greedy pass, making the honest total complexity `O(n log(range))`, not `O(log n)`. Recognize this from "minimize the maximum," "smallest value such that," "minimum capacity/speed/days such that a condition holds," in addition to the classical array forms (rotated sorted array, first/last occurrence, peak element). The two skills actually being tested are: correctly identifying which quantity is monotonic before writing a single line of code, and getting the loop invariant (boundary update rules, termination condition) exactly right, because binary search is notoriously easy to get subtly wrong even when the core idea is correctly understood.

## Why this gets asked

The interviewer wants to know whether your mental model of binary search is "look up a value in a sorted array" (narrow, and it stops being useful the moment the problem doesn't hand you a literal sorted array) or "collapse any monotonic predicate's boundary in log time" (general, and it transfers directly to capacity-planning and resource-allocation problems that look nothing like array search on the surface). This maps directly onto real system-design-adjacent reasoning: "what's the minimum number of shards needed so no shard exceeds X load," "what's the minimum worker speed so a batch job finishes within a deadline," and "what's the smallest cache size that keeps the hit-rate feasibility check satisfied" are all literally binary-search-on-the-answer problems wearing an operations-research costume. The follow-up that separates levels further is complexity honesty: many candidates say "binary search is O(log n)" reflexively without accounting for the cost of the feasibility check itself, which is frequently the dominant term in the real complexity — and binary search is also, famously, one of the easiest correct-looking algorithms to get subtly wrong (the `(low + high) / 2` overflow bug lived in `java.util.Arrays.binarySearch` for roughly nine years before being fixed), so precise loop-invariant reasoning is itself part of what's being graded.

---

## Lineage: past → present → future

**What came before.** The core idea of halving a sorted search space to locate a value dates to at least 1946 (John Mauchly described it as an efficient method), but a fully and provably correct published binary search implementation didn't appear until 1962 — for roughly 16 years, most descriptions and implementations had subtle bugs, and this pattern of "simple to describe, easy to implement incorrectly" never really went away. The most famous instance is documented in Joshua Bloch's 2006 post "Extra, Extra – Read All About It: Nearly All Binary Searches and Mergesorts are Broken," which found that `mid = (low + high) / 2` silently overflows for large enough `low + high` in fixed-width 32-bit integer arithmetic, corrupting the result — and this exact bug had been present in `java.util.Arrays.binarySearch` in the JDK for approximately nine years before it was found and fixed. Before "binary search on the answer" was a named, recognized generalization, problems requiring you to find an optimal threshold value (minimum capacity, maximum feasible allocation) were often solved with slower linear scans or ad hoc greedy adjustment, missing the fact that a monotonic feasibility check turns the search into a logarithmic one.

**Where it stands now.** The array-lookup form (including its rotated, duplicate-containing, and boundary-finding variants) remains a standard, universally expected baseline. What's now equally expected at senior level is the predicate-generalization: recognizing that "minimize the maximum" or "smallest X such that condition Y holds" problems are searches over an implicit answer space, not over a literal array, with a feasibility check (often greedy or a simulation) that itself has a real cost multiplying into the total complexity. There's no live disagreement about the technique; the practical skill gap is entirely in recognizing monotonicity in a *derived* or *computed* quantity (does increasing the candidate answer make the feasibility check monotonically easier or harder to satisfy?) rather than in a raw, already-sorted array value.

**Where it's heading.** Expect continued emphasis on composed problems — binary search on the answer where the feasibility check is itself a greedy pass or a DP computation (Split Array Largest Sum, Minimize Max Distance to Gas Station) — because these test whether a candidate can identify monotonicity in a non-obvious, derived property rather than pattern-matching a memorized template. This is a stable, closed algorithmic area; the direction of travel is entirely in which compositions get asked, not in the core technique changing.

---

## Mental model

```
Classical array search: nums = [1, 3, 5, 7, 9, 11], target = 7

lo=0 hi=5  mid=2  nums[2]=5 < 7 -> lo = mid+1 = 3
lo=3 hi=5  mid=4  nums[4]=9 > 7 -> hi = mid-1 = 3
lo=3 hi=3  mid=3  nums[3]=7 == 7 -> found at index 3

Each step discards HALF the remaining candidates -- that's the O(log n) guarantee.


Predicate-boundary view (this is the general form everything else reduces to):

index:      0    1    2    3    4    5
predicate:  F    F    F    T    T    T     (monotonic: once True, stays True)

Binary search here doesn't look for a VALUE, it looks for the BOUNDARY --
the smallest index where the predicate flips from False to True.

lo=0 hi=5  mid=2  f(2)=False -> answer is NOT here or earlier -> lo = mid+1 = 3
lo=3 hi=5  mid=4  f(4)=True  -> answer could be here or earlier -> hi = mid   (keep mid, don't -1)
lo=3 hi=4  mid=3  f(3)=True  -> hi = mid = 3
lo=3 hi=3  -> loop ends, answer = index 3

"Binary search on the answer" is EXACTLY this predicate-boundary search, except
the "array" is an implicit range of candidate answers (e.g. 1 to 10^9), and
f(mid) = "is mid a FEASIBLE answer" is computed by an external check function
that may itself cost O(n) per call.
```

---

## Recognition heuristics

- **Array is sorted (possibly rotated, possibly with duplicates)** — the classical form; determine which half of a rotated array is properly ordered by comparing `nums[lo]` to `nums[mid]`, then decide which half to search based on where the target falls relative to that ordered half's bounds.
- **"Find the first/last occurrence of X" / "find the boundary where property A becomes property B"** — this is boundary search on a monotonic predicate, the `bisect_left`/`bisect_right` family; be precise about which boundary (first-True vs. last-False) the problem actually wants, since they differ by one index.
- **"Minimize the maximum ..." / "maximize the minimum ..." / "smallest capacity/speed/value such that a feasibility condition holds"** — binary search on the answer: the search space is an implicit numeric range of candidate answers, and a separate feasibility-check function (often greedy simulation, sometimes DP) determines, for a given candidate, whether it's sufficient. This is the generalization that has nothing to do with a literal sorted array.
- **"Find a peak element" in an array that is not globally sorted** — binary search using only a *local* monotonic comparison (`nums[mid]` vs. `nums[mid+1]`) to decide which direction guarantees a peak exists, without the array needing to be sorted at all.
- **A fully sorted, row-major-flattenable 2D matrix ("Search a 2D Matrix I")** — map a single binary-search index directly to `(row, col)` via integer division/modulo and search as if it were one flat sorted array.
- **Precision-bounded search over real numbers** (e.g., `sqrt(x)` to a given epsilon, or continuous resource-spacing problems) — terminate on an epsilon threshold or a fixed iteration count rather than integer pointer convergence, since `lo == hi` may never exactly occur in floating-point arithmetic.

**Anti-signal:** "Search a 2D Matrix II" — rows sorted left-to-right *and* columns sorted top-to-bottom independently, but the matrix is *not* flattenable into one globally sorted sequence — is not solved with binary search at all; it needs a staircase walk from a corner (start at top-right, move left if the current value is too big, down if too small), an `O(m+n)` technique distinct from this pattern entirely. Don't force binary search onto a structure just because it's "sorted" in some sense.

---

## Template code (Python, Java, Go)

Classical array search, plus the general "binary search on the answer" template driven by an external feasibility check — the two skeletons this whole family builds on:

**Python**
```python
def binary_search(nums: list[int], target: int) -> int:
    """Classical search. O(log n) time, O(1) space. Returns index or -1."""
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2       # avoids overflow in fixed-width languages
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

def binary_search_on_answer(lo: int, hi: int, feasible) -> int:
    """Find the smallest value in [lo, hi] for which feasible(x) is True.
    feasible must be monotonic: False...False True...True across the range.
    Total cost = O(cost_of_feasible * log(hi - lo))."""
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if feasible(mid):
            hi = mid          # mid could be the answer -- keep it in range
        else:
            lo = mid + 1      # mid is provably too small/insufficient
    return lo   # lo == hi, the boundary
```

**Java**
```java
public int binarySearch(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;   // avoids (lo+hi) overflow
        if (nums[mid] == target) return mid;
        else if (nums[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}

public interface Feasible { boolean check(int candidate); }

public int binarySearchOnAnswer(int lo, int hi, Feasible feasible) {
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (feasible.check(mid)) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    return lo;
}
```

**Go**
```go
func binarySearch(nums []int, target int) int {
	lo, hi := 0, len(nums)-1
	for lo <= hi {
		mid := lo + (hi-lo)/2 // avoids overflow
		switch {
		case nums[mid] == target:
			return mid
		case nums[mid] < target:
			lo = mid + 1
		default:
			hi = mid - 1
		}
	}
	return -1
}

func binarySearchOnAnswer(lo, hi int, feasible func(int) bool) int {
	for lo < hi {
		mid := lo + (hi-lo)/2
		if feasible(mid) {
			hi = mid
		} else {
			lo = mid + 1
		}
	}
	return lo
}
```

---

## Complexity, derived

Each iteration of classical binary search discards exactly half the remaining candidates (`hi - lo` shrinks by roughly half every step), so the number of iterations before the range collapses to a single element is bounded by `log2(n)`: **O(log n) time, O(1) space**. This is a direct consequence of halving — after `k` iterations, at most `n / 2^k` candidates remain, and that reaches `1` when `k = log2(n)`. For binary search on the answer, the *search itself* still runs in `O(log(hi - lo))` iterations, where `hi - lo` is the width of the candidate-answer range — but each iteration invokes the feasibility check, which is frequently **not O(1)**: Koko Eating Bananas and Capacity To Ship Packages both require an O(n) linear pass per feasibility check (simulating whether a given speed/capacity actually finishes in time). The honest total complexity is therefore **O(n log(range))**, not O(log n) — stating "O(log n)" for these problems without acknowledging the feasibility check's own cost is a real complexity error, not a rounding nitpick, since for large `n` and a large answer range the `n` factor often dominates in practice.

---

## The 5 variants interviewers actually ask

1. **Binary Search (LC704).** The base classical form on a plain sorted array.
2. **Search in Rotated Sorted Array (LC33).** Modification: at each step, determine which half (`lo` to `mid`, or `mid` to `hi`) is properly sorted by comparing `nums[lo]` to `nums[mid]`; then check whether the target falls within that sorted half's value range to decide which half to recurse into — one comparison decides both "which half is ordered" and "which half to search."
3. **Find First and Last Position of Element in Sorted Array (LC34).** Modification: two separate boundary searches — one for the leftmost index where `nums[i] == target` (equivalent to finding the first index where `nums[i] >= target`), one for the rightmost (equivalent to finding the first index where `nums[i] > target`, then subtracting one) — using the predicate-boundary template, not value-equality search.
4. **Koko Eating Bananas (LC875) / Capacity To Ship Packages Within D Days (LC1011).** Binary search on the answer: the candidate-answer range is "possible eating speeds" (1 to `max(piles)`) or "possible daily capacities" (`max(weights)` to `sum(weights)`); the feasibility check simulates whether that candidate speed/capacity satisfies the deadline constraint, an O(n) pass per check, giving O(n log(range)) total.
5. **Find Peak Element (LC162).** Modification: no global sortedness required at all — compare `nums[mid]` to `nums[mid+1]`; if `nums[mid] < nums[mid+1]`, a peak is guaranteed to exist to the right (values are "climbing"), so search the right half; otherwise search the left half (including `mid`, since `mid` itself could be the peak). Correct purely by the local comparison, not global order.

---

## Common bugs

- **`mid = (lo + hi) / 2` overflow in fixed-width integer languages.** For sufficiently large `lo + hi` (exceeding a 32-bit signed integer's range, e.g. `Integer.MAX_VALUE` in Java), the sum overflows before the division happens, silently corrupting `mid` — this is precisely the bug that lived undetected in `java.util.Arrays.binarySearch` for about nine years. Always compute `lo + (hi - lo) / 2` instead.
- **Inconsistent boundary update rules relative to how `mid` is computed (floor vs. ceiling), causing an infinite loop.** If `mid` is computed via floor division and the update rule sets `lo = mid` (instead of `lo = mid + 1`) in the branch where the search should move forward, `lo` and `hi` can converge to adjacent values (`lo = hi - 1`) and `mid` recomputes to `lo` forever, never terminating.
- **Conflating "find the first True" (leftmost boundary, `bisect_left`-style) with "find the last False" (which is one index earlier).** These two boundary definitions differ by exactly one index, and using the wrong update rule (`hi = mid` vs. `hi = mid - 1`, `lo = mid + 1` vs. `lo = mid`) for the specific boundary being sought produces consistently off-by-one-wrong answers.
- **In rotated-array search with duplicates (Search in Rotated Sorted Array II), failing to handle the ambiguous case where `nums[lo] == nums[mid] == nums[hi]`.** When all three are equal, you genuinely cannot tell which half is sorted from that comparison alone; the correct fallback is to shrink the search space by one from both ends (`lo += 1; hi -= 1`) and re-evaluate, which degrades the worst case to O(n) but remains correct — skipping this case entirely produces wrong answers on inputs with enough duplicates.
- **Choosing the feasibility check's direction backward** — e.g., checking "is this candidate speed too slow" when the loop's boundary-update logic assumes the predicate means "is this candidate speed fast enough" — inverts which half of the range gets discarded, converging to the wrong boundary.
- **Reporting binary-search-on-the-answer's complexity as flatly O(log n)**, omitting the feasibility check's own cost, which is very often the dominant O(n) term in the true O(n log(range)) total.
- **Applying binary search to "Search a 2D Matrix II"**, where rows and columns are independently sorted but the matrix isn't globally flattenable — this structure needs an O(m+n) staircase walk from a corner, not binary search, and forcing binary search onto it either fails to terminate correctly or requires an unjustified extra assumption about the matrix's structure.

---

## Interview questions

### Q1 — Binary Search (LC704)
**Testing:** the base template, cleanly and without overflow bugs.
**Answer:** `lo + (hi - lo) // 2` for `mid`; standard three-way comparison; O(log n) time, O(1) space.
**Follow-up trap:** *"What's wrong with `mid = (lo + hi) / 2`?"* — it overflows in fixed-width 32-bit integer arithmetic once `lo + hi` exceeds the integer type's max value, a real historical bug that persisted in the JDK's own `Arrays.binarySearch` for roughly nine years before being found and fixed in 2006.

### Q2 — Search in Rotated Sorted Array (LC33)
**Testing:** determining which half is properly ordered before deciding where to search.
**Answer:** Compare `nums[lo]` to `nums[mid]` to determine which half is sorted; check whether the target lies within that sorted half's value range to decide which half to recurse into.
**Follow-up trap:** *"What if the array contains duplicates?"* — see Search in Rotated Sorted Array II: when `nums[lo] == nums[mid] == nums[hi]`, you cannot determine which half is sorted from that comparison alone, and must fall back to shrinking both ends by one and re-checking, which degrades the worst case from O(log n) to O(n).

### Q3 — Search in Rotated Sorted Array II (LC81)
**Testing:** whether you handle the duplicate-driven ambiguity correctly rather than assuming LC33's logic transfers unchanged.
**Answer:** Same half-determination logic as LC33, with an explicit fallback: if `nums[lo] == nums[mid] == nums[hi]`, decrement `hi` and increment `lo` by one each and retry, since the sorted-half comparison is genuinely ambiguous in that case.
**Follow-up trap:** *"Does this fallback change the worst-case complexity?"* — yes, from O(log n) to O(n) in the worst case (e.g., an array of all-identical values with one rotation point), and you should say this plainly rather than claiming the algorithm is "still O(log n)."

### Q4 — Find First and Last Position of Element in Sorted Array (LC34)
**Testing:** the predicate-boundary template applied twice, with correct boundary semantics.
**Answer:** First occurrence = leftmost index where `nums[i] >= target`; last occurrence = (leftmost index where `nums[i] > target`) minus one; both via the boundary-search template, verifying the found index actually equals `target` afterward (it might not exist at all).
**Follow-up trap:** *"Can you get both boundaries with a single pass instead of two separate binary searches?"* — not while keeping the algorithm a clean binary search; a single linear scan could find both in one O(n) pass, but that defeats the O(log n) purpose entirely — two separate O(log n) searches is the correct, intentional tradeoff here, not a limitation to apologize for.

### Q5 — Koko Eating Bananas (LC875)
**Testing:** recognizing binary search on the answer, with an explicit feasibility check.
**Answer:** Candidate answers are eating speeds from `1` to `max(piles)`; feasibility check simulates total hours needed at a given speed (`sum(ceil(pile / speed) for pile in piles)`) and compares to the hour limit; binary search for the smallest feasible speed. O(n log(max(piles))).
**Follow-up trap:** *"What's the actual total time complexity, precisely?"* — O(n log(max(piles))), not O(log(max(piles))); each of the O(log(range)) probes requires an O(n) pass over all piles to evaluate feasibility, and omitting that factor is a real complexity error.

### Q6 — Capacity To Ship Packages Within D Days (LC1011)
**Testing:** recognizing the same binary-search-on-the-answer shape under a different cover story, and correctly setting the search bounds.
**Answer:** Candidate answers are daily capacities from `max(weights)` (must be at least large enough for the single heaviest package) to `sum(weights)` (one day, ship everything); feasibility check greedily simulates how many days are needed at a given capacity; binary search for the smallest feasible capacity.
**Follow-up trap:** *"Why must the lower bound be `max(weights)` and not `1`?"* — any capacity smaller than the heaviest single package can never ship that package at all, making the feasibility check trivially and permanently false below that point; starting the search range below the true minimum feasible value wastes iterations (or, if the feasibility check doesn't itself guard against this, can produce an incorrect answer).

### Q7 — Find Peak Element (LC162)
**Testing:** whether you require full sortedness out of habit, or recognize local monotonicity is sufficient.
**Answer:** Compare `nums[mid]` to `nums[mid+1]`; if ascending, a peak is guaranteed somewhere to the right, so move `lo = mid + 1`; otherwise move `hi = mid` (not `mid - 1`, since `mid` itself could be the peak).
**Follow-up trap:** *"The array isn't sorted at all — how can binary search possibly be correct here?"* — correctness doesn't depend on global order; it depends only on the local guarantee that a strictly ascending step to the right implies a peak exists further right (values can't ascend forever in a finite array with defined boundary conditions), which is a strictly weaker and different property than full sortedness.

### Q8 — Search a 2D Matrix (LC74) vs. Search a 2D Matrix II (LC240)
**Testing:** the anti-pattern boundary — recognizing when binary search stops applying to a "sorted-looking" 2D structure.
**Answer:** LC74 (fully row-major sorted, so `matrix[i][j] <= matrix[i][j+1]` and the last element of each row is less than the first of the next) flattens conceptually into one sorted array and is searched with straight binary search via `mid -> (mid // cols, mid % cols)`. LC240 (rows sorted left-to-right, columns sorted top-to-bottom, but *not* globally flattenable that way) requires an O(m+n) staircase walk starting from a corner (e.g., top-right, moving left if too big, down if too small), not binary search.
**Follow-up trap:** *"Why can't you binary search LC240 the same way?"* — there's no single global ordering to binary search against: a value greater than `matrix[mid_row][mid_col]` in LC240 could be either further right in the same row *or* further down in the same column, and a single binary-search-style probe can't disambiguate between those two directions the way flattened row-major order in LC74 can.

### Q9 — Sqrt(x) to a given precision
**Testing:** whether you correctly convert integer-pointer binary search termination logic to real-valued termination.
**Answer:** Binary search over a real-valued range with a fixed epsilon threshold (`while hi - lo > epsilon`) or a fixed iteration count (each iteration halves the interval, so ~50 iterations gets far past double-precision limits) instead of the integer `lo <= hi` / `lo < hi` convergence conditions, since floating-point `lo` and `hi` will essentially never become exactly equal.
**Follow-up trap:** *"How many iterations do you actually need for double-precision accuracy?"* — since each iteration halves the interval, about 50-60 iterations reduces even a huge initial range to a width far below double-precision's representable granularity (`2^-52` relative precision); a fixed loop count of around 100 is a common, safely-overprovisioned choice in practice, not something that needs tuning per problem.

### Q10 — Split Array Largest Sum (LC410)
**Testing:** a harder composition — recognizing monotonicity in a property that requires a greedy simulation to evaluate, not a simple arithmetic check.
**Answer:** Candidate answers are possible "largest subarray sum" values, ranging from `max(nums)` (each element its own subarray) to `sum(nums)` (one subarray); feasibility check greedily partitions the array into the minimum number of subarrays such that no subarray sum exceeds the candidate value, then compares that count to the allowed number of splits; binary search for the smallest feasible candidate value.
**Follow-up trap:** *"Why is this feasibility check's underlying property actually monotonic — walk through why a larger candidate value never requires MORE subarrays than a smaller one."* — allowing a larger maximum subarray sum can only ever let the greedy partitioner merge more elements into each subarray (never fewer), which can only decrease or hold constant the number of subarrays needed, never increase it — that non-increasing relationship between candidate value and required subarray count is exactly the monotonicity binary search on the answer depends on, and stating it explicitly (rather than assuming monotonicity holds because "the problem looks like the others") is the mark of understanding versus pattern-matching.

### Q11 — Median of Two Sorted Arrays (LC4)
**Testing:** recognizing a variant where binary search operates over a partition INDEX, not over a data value or an answer-range value.
**Answer:** Binary search over the number of elements taken from the shorter array into the "left partition" (0 to `len(shorter array)`), checking whether the max of both arrays' left partitions is `<=` the min of both arrays' right partitions; adjust the partition point based on which side violates that condition.
**Follow-up trap:** *"How is what you're binary-searching over here different from the classical array search or the binary-search-on-the-answer problems?"* — the object being searched isn't a data value present in either array, nor an implicit numeric "candidate answer" being tested for feasibility against a simulation — it's a *partition index* into the shorter array, and the "predicate" being tested is a structural balance condition between the two arrays' partitions, which is a third distinct flavor of what counts as the "ordered space" binary search collapses.

### Q12 — The `(low + high) / 2` overflow bug as a production war story
**Testing:** whether you treat binary search's correctness as something to verify carefully rather than assume, given how easy it is to get subtly wrong.
**Answer:** For 32-bit signed integers, `low + high` can exceed `Integer.MAX_VALUE` (~2.1 billion) well before the array itself is anywhere near that large if `low` and `high` are both large enough individually (e.g., searching near the end of a very large array), causing the sum to wrap into a negative number before the division, corrupting `mid` into an out-of-bounds or nonsensical index.
**Follow-up trap:** *"This bug was in a widely-used standard library for years before anyone noticed — what does that imply about testing this kind of code?"* — the bug only manifests on sufficiently large arrays/indices, which most unit tests never exercise; it's a reminder that algorithmically "obviously correct" code still needs boundary-value and large-scale testing, and that "well-known, widely used, surely already correct" is not the same guarantee as "verified correct for the actual input sizes your system will see."

---

## Red flags that fail you

- Writing `mid = (lo + hi) / 2` without recognizing the overflow risk in fixed-width integer languages.
- Inconsistent boundary updates relative to how `mid` rounds, causing an infinite loop on a two-element range.
- Conflating "first True" and "last False" boundary semantics, producing consistent off-by-one errors.
- Not handling the `nums[lo] == nums[mid] == nums[hi]` ambiguous case in rotated-array search with duplicates.
- Claiming binary-search-on-the-answer is O(log n) without acknowledging the feasibility check's own cost.
- Forcing binary search onto "Search a 2D Matrix II" instead of recognizing it needs a staircase walk.

---

## Cheat card

```
CORE IDEA       any monotonic predicate over an ORDERED space collapses to its boundary in O(log range)
CLASSICAL       sorted array lookup: O(log n) time, O(1) space
OVERFLOW FIX    mid = lo + (hi - lo) / 2   -- never (lo + hi) / 2 in fixed-width int languages
BOUNDARY SEARCH first-True vs last-False differ by ONE index -- pick the right update rule deliberately
ROTATED ARRAY   compare nums[lo] vs nums[mid] to find the SORTED half, then check target's range
ROTATED+DUPES   nums[lo]==nums[mid]==nums[hi] is ambiguous -> shrink both ends by 1, fallback O(n) worst case
ON THE ANSWER   search space = implicit range of candidate answers; f(mid) = external feasibility check
COMPLEXITY      O(n log(range)), NOT O(log n) -- the feasibility check's own O(n) cost multiplies in
PEAK ELEMENT    only needs LOCAL comparison (nums[mid] vs nums[mid+1]), no global sortedness required
2D MATRIX I     fully flattenable -> straight binary search via mid -> (mid//cols, mid%cols)
2D MATRIX II    NOT flattenable -> staircase walk from a corner, O(m+n), NOT binary search
FLOATING POINT  terminate on epsilon or fixed iteration count (~50-100), not lo==hi convergence
PARTITION SEARCH Median of 2 Sorted Arrays: binary search over a PARTITION INDEX, not a value
```

## Sources
- [Search in Rotated Sorted Array — LeetCode](https://leetcode.com/problems/search-in-rotated-sorted-array/) — accessed 2026-07-27
- [Koko Eating Bananas — LeetCode](https://leetcode.com/problems/koko-eating-bananas/) — accessed 2026-07-27
- [Capacity To Ship Packages Within D Days — LeetCode](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) — accessed 2026-07-27
- [Find Peak Element — LeetCode](https://leetcode.com/problems/find-peak-element/) — accessed 2026-07-27
- [Search a 2D Matrix II — LeetCode](https://leetcode.com/problems/search-a-2d-matrix-ii/) — accessed 2026-07-27
- [Extra, Extra – Read All About It: Nearly All Binary Searches and Mergesorts are Broken — Joshua Bloch, Google AI Blog](https://ai.googleblog.com/2006/06/extra-extra-read-all-about-it-nearly.html) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
