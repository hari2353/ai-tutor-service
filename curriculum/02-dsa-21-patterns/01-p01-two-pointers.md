# Two Pointers

> **Track:** T02 DSA: 21 Patterns · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T02-p01-two-pointers` · **Tags:** pattern, arrays, strings

## The 30-second version

Two Pointers replaces an O(n^2) nested-loop scan with a single O(n) pass by walking two indices through a structure whose ordering lets you discard possibilities in bulk instead of checking them one at a time. The two canonical shapes are **converging** pointers that start at both ends of a sorted array and close inward, and **same-direction** pointers (often called fast/slow in this context, not to be confused with the linked-list cycle pattern) where one index scans ahead and the other marks a write position. The precondition that makes it legal is almost always sortedness, or a monotonic relationship between moving a pointer and the value you're tracking. When you see "sorted array" plus "find a pair/triplet," or "array/string, do it in O(1) extra space," reach for this first.

## Why this gets asked

It is the shortest path to testing whether a candidate can turn a brute-force O(n^2) idea into O(n) by reasoning about *monotonicity* rather than memorizing a trick. The interviewer has watched candidates write a correct but quadratic nested loop for Two Sum on a sorted array, and wants to see whether the candidate notices the sort is a gift: moving the left pointer right only increases the sum, moving the right pointer left only decreases it, so at every step exactly one move is provably correct. That "provably correct" argument, not the code, is what's being graded. At a senior level, the follow-up is whether you can extend the same idea to three or four pointers (3Sum, 4Sum) without the complexity blowing back up to O(n^3) or worse, and whether you handle duplicates without producing duplicate output.

---

## Lineage: past → present → future

**What came before.** Before two pointers was named as an interview pattern, the default answer to "find a pair/triplet with property X" was brute-force enumeration: nested loops checking every pair, O(n^2), or every triplet, O(n^3). The pain was straightforward — it scales terribly and it doesn't use the one piece of structure (sortedness) that the problem statement usually hands you for free. Classic algorithms texts (Knuth's *TAOCP*, CLRS) treat converging-pointer scans as a basic building block of array algorithms going back to merge-step logic in merge sort (1945, von Neumann) — the merge step of merge sort *is* a two-pointer walk over two sorted arrays. The interview-specific framing crystallized much later, popularized by prep resources like Design Gurus' *Grokking the Coding Interview* course (which organizes ~245 problems into named patterns, two pointers among the first) and community write-ups such as the widely shared "14 Patterns to Ace Any Coding Interview Question."

**Where it stands now.** Two pointers is universally taught and near-universally expected at any level from new-grad to staff for array/string questions; there is no live disagreement about the pattern itself. What separates candidates now is speed of recognition (sorted array + pair/triplet should trigger this in seconds, not minutes) and correctness on the edge cases that make it a bad "I understand this" false positive: duplicate handling in 3Sum, the direction each pointer should move and why, and integer-overflow-adjacent bugs in strongly typed languages. In practice this pattern shows up constantly as a sub-routine inside harder problems (3Sum inside 3Sum Closest, container-with-water inside trapping-rain-water) rather than only as a standalone question, so interviewers increasingly embed it as step one of a two-step problem.

**Where it's heading.** With AI-assisted and debugging-focused interview formats becoming more common in 2026 — candidates given a broken or partially written solution and asked to find the bug, rather than write from scratch — two pointers is an efficient testing ground precisely because its bugs are small and specific (off-by-one, wrong comparison direction, missed duplicate skip). Expect more "here's a two-pointer solution with a subtle bug, find and fix it in under two minutes" style rounds rather than blank-page prompts. This is a direction of travel with moderate confidence, based on how coding-round formats at several large tech employers have already shifted toward partially-written-code debugging in the past two years.

---

## Mental model

Converging pointers on a sorted array:

```
index:   0    1    2    3    4    5    6
value:  [2,   7,   11,  13,  16,  20,  24]
         ^L                            ^R
sum = 2 + 24 = 26   target = 24  -> too big, move R left
         ^L                       ^R
sum = 2 + 20 = 22   -> too small, move L right
              ^L                  ^R
sum = 7 + 20 = 27   -> too big, move R left
              ^L              ^R
sum = 7 + 16 = 23   -> too small, move L right
                   ^L         ^R
sum = 11 + 16 = 27  -> too big, move R left
                   ^L    ^R
sum = 11 + 13 = 24  -> match, return (2, 3)
```

Same-direction (write pointer / scan pointer), used for in-place compaction:

```
nums:  [0, 0, 1, 1, 1, 2, 2]
        w
        r  (w never runs ahead of r; w marks "next slot to write")
each time nums[r] is a new distinct value, write it at nums[w], then w++
```

The invariant that makes converging pointers correct: at every step, one of the two moves (advance L or retreat R) is *guaranteed* not to lose the answer, because the array is sorted. That guarantee is the entire proof of correctness — say it out loud in the interview.

---

## Recognition heuristics

These are the concrete signals. If two or more line up, this is very likely the pattern.

- **"Sorted array" + "find a pair/triplet/quadruple" summing to (or comparing to) a target.** The sort is not incidental; it is the enabling condition. If the array is *not* sorted but you're told to find pairs, the fallback is a hash set, not two pointers — sort first only if you also need indices unmodified or O(1) space.
- **"In-place" + "O(1) extra space"** on an array or string — a strong signal for the same-direction (read/write) variant: remove duplicates, move zeroes, partition by a predicate.
- **Palindrome checking** on a string or array — converging pointers from both ends, no extra space.
- **"Container," "trap," "area between two lines/walls"** — greedy converging pointers where you always move the pointer bounding the smaller value, because it's provably the only one that can improve the answer.
- **Two sorted structures need to be merged or intersected** — one pointer per structure, advance the one pointing at the smaller (or lesser-priority) element. This is literally the merge step of merge sort.
- **"Reverse a string/array in place"** — trivial converging-pointer swap.
- **k-Sum family (3Sum, 4Sum)** — fix the outer k-2 indices with nested loops (with duplicate-skipping), then two pointers on the remaining sorted suffix. If you see "3Sum" think "one loop + two pointers," not "three nested loops."

**Anti-signal:** if the array is unsorted and sorting would destroy needed information (e.g., you need original indices and can't afford to carry them alongside the sort), a hash map is usually the better tool, not two pointers forced onto unsorted data.

---

## Template code (Python, Java, Go)

Converging two pointers on a sorted array, target-sum search — the reusable skeleton for the entire converging-pointer family:

**Python**
```python
def two_sum_sorted(nums: list[int], target: int) -> list[int]:
    """Return indices of a pair summing to target, or [-1, -1]. O(n) time, O(1) space."""
    left, right = 0, len(nums) - 1
    while left < right:
        current = nums[left] + nums[right]
        if current == target:
            return [left, right]
        elif current < target:
            left += 1          # need a bigger sum -> only moving left can increase it
        else:
            right -= 1         # need a smaller sum -> only moving right can decrease it
    return [-1, -1]
```

**Java**
```java
public int[] twoSumSorted(int[] nums, int target) {
    int left = 0, right = nums.length - 1;
    while (left < right) {
        int sum = nums[left] + nums[right];
        if (sum == target) {
            return new int[]{left, right};
        } else if (sum < target) {
            left++;
        } else {
            right--;
        }
    }
    return new int[]{-1, -1};
}
```

**Go**
```go
func twoSumSorted(nums []int, target int) [2]int {
	left, right := 0, len(nums)-1
	for left < right {
		sum := nums[left] + nums[right]
		switch {
		case sum == target:
			return [2]int{left, right}
		case sum < target:
			left++
		default:
			right--
		}
	}
	return [2]int{-1, -1}
}
```

---

## Complexity, derived

Each iteration of the loop moves `left` up by one or `right` down by one, never both, and the loop ends when `left >= right`. The total number of moves before that happens is bounded by `right - left` at the start, which is `n - 1`. So the loop body runs at most `n - 1` times: **O(n) time**. No auxiliary data structure scales with input, only three scalar variables: **O(1) extra space** (excluding the input array and, if required, an initial O(n log n) sort). For the k-Sum family: fixing `k - 2` indices via nested loops with an inner two-pointer scan gives O(n^(k-1)) — O(n^2) for 3Sum, O(n^3) for 4Sum — versus O(n^k) for naive nested-loop enumeration at every level.

---

## The 5 variants interviewers actually ask

1. **Pair with target sum, sorted array (Two Sum II).** The base template above, unmodified.
2. **3Sum — triplets summing to zero, no duplicate triplets.** Sort the array. Fix index `i` with an outer loop; skip `i` if `nums[i] == nums[i-1]` to avoid duplicate outer choices. Run the base two-pointer scan on `nums[i+1:]` with target `-nums[i]`; on a match, record the triplet and advance both pointers past any duplicate values before continuing.
3. **Container With Most Water.** Converging pointers from both ends; area is `min(height[left], height[right]) * (right - left)`. Modification: always move the pointer at the *shorter* wall inward, because the taller wall could still pair with something better later, but the shorter wall can never do better paired with anything closer than its current partner.
4. **Trapping Rain Water.** Converging pointers plus two running maxima (`left_max`, `right_max`). Modification: move whichever side has the smaller running max, and add `max_side - height[pointer]` to the trapped total before advancing — the smaller max is the one that actually bounds the water at that position.
5. **Dutch National Flag / Sort Colors — three-way partition.** Modification: three pointers (`low`, `mid`, `high`) instead of two. `mid` scans; a `0` swaps to `low` and both `low`/`mid` advance, a `2` swaps to `high` and only `high` retreats (recheck the swapped-in value), a `1` just advances `mid`.

---

## Common bugs

- **`left <= right` vs `left < right`.** For pair-finding, using `<=` lets `left` and `right` land on the same index and "find" a pair using one element twice. Use strict `<` unless the problem explicitly allows reusing an index.
- **Moving the wrong pointer, or moving both, on a tie.** In Container With Most Water, moving the taller pointer instead of the shorter one breaks the greedy proof and can skip the optimal answer silently — no crash, just a wrong number.
- **Forgetting to skip duplicates in 3Sum/4Sum**, which produces duplicate triplets in the output. The skip has to happen in *two* places: skipping the outer loop's repeated value, and skipping repeated values on both `left` and `right` after a successful match — missing either one leaks duplicates.
- **Sorting when you needed original indices**, then returning sorted-array positions instead of the caller's original indices (classic Two Sum I vs Two Sum II confusion — Two Sum I on an unsorted array wants original indices and is solved with a hash map, not two pointers).
- **Off-by-one in the same-direction / write-pointer variant** — advancing the write pointer before or after the check inconsistently, which either drops the first valid element or leaves a stale duplicate at the end of the compacted array.
- **Assuming two pointers on an unsorted array without sorting it first**, then being surprised the "provably correct" move argument no longer holds because nothing is monotonic.

---

## Interview questions

### Q1 — Two Sum II — Input Array Is Sorted (LC167)
**Testing:** whether you reach for two pointers instead of a hash map once told the array is sorted.
**Answer:** Converging pointers, the base template. O(n) time, O(1) space, versus O(n) space for the hash-map approach that Two Sum I needs.
**Follow-up trap:** *"Why not just reuse your Two Sum I hash-map solution?"* — it works but throws away the sortedness for no benefit and costs O(n) extra space; say explicitly that sortedness is the reason you switch approach, not habit.

### Q2 — 3Sum (LC15)
**Testing:** whether you can compose a loop with a two-pointer inner scan, and handle duplicates.
**Answer:** Sort, fix `i`, two-pointer scan on the remainder for `-nums[i]`, skip duplicate `i` and duplicate `left`/`right` after a match. O(n^2) time, O(1) extra space beyond the output.
**Follow-up trap:** *"What if the array has 10,000 duplicate zeros?"* — without the duplicate-skip logic you emit the same `[0,0,0]` triplet thousands of times; the skip loops (`while left < right and nums[left] == nums[left-1]: left += 1`) must run *after* a match, not instead of the match check.

### Q3 — 3Sum Closest (LC16)
**Testing:** adapting the exact-match template to a "closest to target" variant.
**Answer:** Same structure as 3Sum, but instead of checking `== 0` track `min(abs(sum - target))` across all `i` and pointer positions, updating a running best.
**Follow-up trap:** *"Can you terminate early anywhere?"* — if `sum == target` exactly, return immediately since nothing can be closer; otherwise you must scan the full space, there's no early exit that preserves correctness.

### Q4 — 4Sum (LC18)
**Testing:** whether the pattern generalizes past three pointers without you reinventing it badly.
**Answer:** Two nested loops fixing the first two indices (each with duplicate-skipping), then the base two-pointer scan on the remainder. O(n^3) time.
**Follow-up trap:** *"Where would this stop scaling?"* — every additional "Sum" adds one more nested loop and one more power of n; kSum is O(n^(k-1)), which is why nobody asks 5Sum — say this proactively, it signals you understand the pattern's growth, not just its code.

### Q5 — Container With Most Water (LC11)
**Testing:** the greedy pointer-movement proof, not just the formula.
**Answer:** Converging pointers, always move the shorter wall inward; area is `min(h[l], h[r]) * (r - l)`. O(n) time, O(1) space.
**Follow-up trap:** *"Prove that moving the shorter wall is always safe."* — the shorter wall bounds the current area; keeping it fixed and moving the other pointer can only produce a width-decreasing area bounded by the same short wall, so it can never beat the current area. Moving the shorter one is the only move that has a chance to find something taller and thus better.

### Q6 — Trapping Rain Water (LC42)
**Testing:** whether you can extend converging pointers with auxiliary running state (this is the "container" problem's harder sibling and a frequent follow-up to it).
**Answer:** Track `left_max` and `right_max` while converging; add water at the side with the smaller max, since that max is what actually bounds the trapped water at the current pointer.
**Follow-up trap:** *"Solve it without the two extra arrays."* — the naive solution precomputes `left_max[]` and `right_max[]` arrays, O(n) space; the interview-grade answer collapses those into two running scalars during a single converging pass, O(1) space.

### Q7 — Sort Colors / Dutch National Flag (LC75)
**Testing:** extending two pointers to three pointers for in-place partitioning.
**Answer:** `low`, `mid`, `high` pointers; swap `0`s to `low`, leave `1`s, swap `2`s to `high`. Single pass, O(n) time, O(1) space.
**Follow-up trap:** *"After swapping a value from `high` into `mid`, why don't you advance `mid`?"* — the value swapped in from `high` hasn't been examined yet and could itself be a `0` or `2`; advancing `mid` unconditionally there is the single most common bug in this problem.

### Q8 — Remove Duplicates from Sorted Array (LC26)
**Testing:** the same-direction read/write pointer variant, in place.
**Answer:** `write` pointer marks the next slot for a new distinct value; `read` scans forward; when `nums[read] != nums[write-1]`, copy it to `nums[write]` and advance both.
**Follow-up trap:** *"Now allow each value to appear at most twice"* (LC80) — compare `nums[read]` against `nums[write-2]` instead of `nums[write-1]`; candidates who hardcode "compare to the previous written value" fail this immediately because the rule generalizes to a fixed lookback, not literally "previous."

### Q9 — Valid Palindrome (LC125)
**Testing:** converging pointers on a string with a filtering step.
**Answer:** Converging pointers, skipping non-alphanumeric characters on both sides before comparing case-insensitively.
**Follow-up trap:** *"Do it without allocating a cleaned copy of the string."* — filtering into a new string first is O(n) space; the interview-grade version advances each pointer past non-alphanumeric characters inline during the same converging walk, O(1) space.

### Q10 — Squares of a Sorted Array (LC977)
**Testing:** recognizing two pointers when the array is sorted but signed (negatives present).
**Answer:** The largest squared value is always at one of the two ends (most negative or most positive), never in the middle; converging pointers filling the result array from the back, comparing `abs` values.
**Follow-up trap:** *"Why fill the result from the back instead of the front?"* — the two candidate values you're comparing at any step are the *largest remaining* squares, so they belong at the largest remaining output slot; filling from the front would require knowing final positions in advance.

### Q11 — Backspace String Compare (LC844)
**Testing:** whether you recognize the "reverse scan + skip-count" variant of same-direction pointers when a naive stack solution is the easy fallback.
**Answer:** Two independent pointers starting at the *end* of each string, walking backward, each one internally skipping characters cancelled by pending `#` backspaces, comparing the next surviving character from each string.
**Follow-up trap:** *"Can you do this in O(1) space?"* — a stack-based simulation is the obvious O(n) space answer; the interview-grade one processes both strings back-to-front with two independent skip-counters and never materializes the cleaned string.

### Q12 — Merge Sorted Array (LC88)
**Testing:** recognizing that filling in-place from the back avoids overwriting unread data — a classic same-direction two-pointer trap.
**Answer:** Three pointers: end of the two logical arrays and the end of the combined buffer; copy the larger of the two remaining values into the last free slot and retreat that source pointer and the write pointer.
**Follow-up trap:** *"Why fill from the back instead of merging into a new array from the front?"* — `nums1` has trailing free space precisely so you can write in-place; merging from the front would overwrite elements of `nums1` you haven't compared yet, since the destination and one source array are the same buffer.

---

## Red flags that fail you

- Writing a nested O(n^2) loop for a problem explicitly labeled "sorted array, find a pair" without mentioning the O(n) alternative.
- Using `left <= right` for pair-finding and not noticing it lets an index pair with itself.
- Forgetting duplicate-skip logic in 3Sum/4Sum and shrugging off duplicate output as "close enough."
- Sorting an array when the problem needs original indices returned, without acknowledging the tradeoff.
- Claiming Container With Most Water requires checking every pair to be safe — not being able to state or defend the greedy proof.
- Advancing both pointers on a three-way-partition swap without checking the newly swapped-in value.

---

## Cheat card

```
PATTERN     converging (sorted, ends inward) or same-direction (read/write)
PRECONDITION  sortedness or monotonic relationship between pointer move and tracked value
LOOP GUARD  left < right (not <=) for pair-finding; avoids reusing one index twice
MOVE RULE   sum < target -> left++ ; sum > target -> right-- ; sum == target -> done
CONTAINER   always move pointer at the SHORTER wall; taller one can't be improved by moving it
RAIN WATER  track left_max/right_max scalars; add water on the side with the smaller max
3SUM        sort + fix i (skip dup i) + 2-pointer scan; skip dup on left/right AFTER a match
COMPLEXITY  O(n) single pass; kSum family is O(n^(k-1)) via nested loop + inner 2-pointer
3-WAY PART  low/mid/high pointers (Dutch flag); re-check value swapped in from `high`
IN-PLACE    write pointer never runs ahead of read pointer; compare against fixed lookback (k)
WRONG TOOL  unsorted array + need original indices -> hash map, not two pointers
```

## Sources
- [14 Patterns to Ace Any Coding Interview Question — LeetCode Discuss](https://leetcode.com/discuss/post/4039411/14-Patterns-to-Ace-Any-Coding-Interview-Question/) — accessed 2026-07-26
- [Ultimate Coding Patterns Cheat Sheet for Tech Interviews — DesignGurus](https://www.designgurus.io/blog/coding-patterns-for-tech-interviews) — accessed 2026-07-26
- [Two Sum II - Input Array Is Sorted — LeetCode](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) — accessed 2026-07-26
- [3Sum — LeetCode](https://leetcode.com/problems/3sum/) — accessed 2026-07-26
- [Trapping Rain Water — LeetCode](https://leetcode.com/problems/trapping-rain-water/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
