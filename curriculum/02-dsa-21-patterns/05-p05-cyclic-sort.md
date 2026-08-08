# Cyclic Sort

> **Track:** T02 DSA: 21 Patterns · **Time:** 1h · **Prereqs:** none · **Updated:** 2026-07-27
> **Module id:** `T02-p05-cyclic-sort` · **Tags:** pattern, arrays, in-place

## The 30-second version

Cyclic Sort exploits a specific, narrow precondition — an array of `n` (or `n-1`) numbers drawn from a known contiguous range like `[1, n]` or `[0, n-1]` — to place every value at its "home" index in a single O(n) pass with O(1) extra space, no sorting algorithm and no hash set required. The mechanism: at index `i`, repeatedly swap the current value into the index it belongs at (`value - 1` for a `[1,n]` range) until the value that lands at `i` is already correctly placed there, then move on. It looks like it should be O(n^2) because of the inner while loop, but it's provably O(n) because every swap permanently seats at least one value in its final home, and a placed value is never touched again — so the total number of swaps across the entire outer loop is bounded by `n`. Recognize it instantly from "array contains numbers in the range [1, n]" (or `[0, n]`, or `[0, n-1]`) combined with "find missing," "find duplicate," or "sort in O(1) space" — the range constraint is the whole trick, and without it this pattern doesn't apply at all.

## Why this gets asked

The interviewer is testing whether you notice a value-range constraint as exploitable structure the same way sortedness is exploitable structure for two pointers — most candidates default to sorting (`O(n log n)`) or a hash set (`O(n)` extra space) for "find the missing/duplicate number," both of which work but neither of which is optimal once the range constraint is stated explicitly. This has real production lineage: index-compaction and slot-assignment problems (assigning a bounded set of IDs to array slots, deduplicating a known-range key space without extra memory) reduce to exactly this operation, and counting-sort-style range exploitation goes back to Harold Seward's 1954 counting sort, which is the ancestor idea — sort by direct placement when the value range is small and known, rather than by comparison. The sharper follow-up interviewers use to separate levels is First Missing Positive (LC41), because it forces you to handle values *outside* the valid range (negatives, zero, values larger than `n`) without breaking the O(1)-space guarantee, which is where sloppy implementations throw index-out-of-bounds errors or silently produce wrong answers.

---

## Lineage: past → present → future

**What came before.** Before cyclic sort was named as an interview-pattern shortcut, "find the missing/duplicate number in a constrained range" was answered with a full sort (`O(n log n)` time) or a hash set / boolean array of size `n` (`O(n)` time, `O(n)` extra space) — both correct, neither optimal. The specific insight that a known, bounded value range lets you place elements directly by value rather than by comparison predates the interview framing by decades: Harold Seward's 1954 counting sort is the conceptual ancestor, exploiting exactly the same fact (small known range means you don't need comparisons at all). Sum-formula and XOR tricks (`expected_sum - actual_sum`, or XOR-ing all indices and values together) were also common single-missing-number answers before cyclic sort was popularized as the general in-place technique covering the whole family — missing, duplicate, and combinations of both.

**Where it stands now.** Cyclic sort is the standard answer whenever a problem states or implies a `[1,n]`/`[0,n-1]`-range array and requires `O(1)` extra space; there's no live disagreement about the core technique. What separates levels of fluency is (a) correctly deriving the O(n) bound instead of assuming the nested while loop makes it quadratic, and (b) transferring the "index-as-value" idea to negative-marking (flip the sign of `nums[abs(v)-1]` to record "value v has been seen" without any extra array) for problems that only need existence checks rather than full physical sorting. The XOR and sum-formula tricks remain valid alternatives specifically for the single-missing-number case, and interviewers sometimes ask you to produce both and explain the tradeoff (XOR avoids overflow risk that a sum-formula has for large `n`, but generalizes less cleanly to "find the duplicate too" variants).

**Where it's heading.** This pattern is stable and closed — the technique itself isn't evolving — but expect continued emphasis on the negative-marking variant and on First Missing Positive specifically, because both require careful boundary reasoning (index validity, sign confusion after marking, values out of range) that's easy to get subtly wrong, making them efficient tests of implementation discipline rather than algorithmic novelty. There is little room for new variants beyond compositions already seen (e.g., "find the number that appears twice and the number that's missing," LC645), so expect the question set to stay essentially fixed.

---

## Mental model

```
nums = [3, 1, 2]     -- values in range [1,3], want each value v at index v-1

i=0: nums[0]=3, home index for value 3 is index 2. nums[2]=2 != 3, so swap.
     nums = [2, 1, 3]
     nums[0]=2 now, home index for value 2 is index 1. nums[1]=1 != 2, so swap.
     nums = [1, 2, 3]
     nums[0]=1 now, home index for value 1 IS index 0. Already home -- advance i.

i=1: nums[1]=2, home index for value 2 is index 1. Already home -- advance i.
i=2: nums[2]=3, home index for value 3 is index 2. Already home -- advance i.

result: [1, 2, 3]   -- every value at index (value - 1)
```

The invariant: each swap moves *some* value into its own permanent final position (the value that was sitting at the target index before the swap either was already correct, or gets swapped again next iteration until it too lands correctly). A value is swapped at most once into its correct home and then never touched again — that's what bounds total swap count by `n`, not `n^2`.

---

## Recognition heuristics

- **"Array of n numbers, each in the range [1, n]" (or "[0, n]", "[0, n-1]") with possible duplicates or a missing value.** The range constraint — bounded, known, and tied to the array's own length — is the entire signal. Without it, cyclic sort doesn't apply.
- **"Find the missing number" / "find all missing numbers" / "find the duplicate" / "find all duplicates" / "find the number that's both missing and duplicated"** on such a constrained-range array — this whole family is cyclic sort or a close variant.
- **"Do it in O(n) time and O(1) extra space"** stated explicitly — this phrase is usually there specifically to rule out sorting (`O(n log n)`) and hash sets (`O(n)` space), pointing you at cyclic sort or negative marking.
- **"You may modify the input array"** — cyclic sort and negative marking are both in-place techniques that permanently alter the input; if the problem says the array *cannot* be modified (a common twist on Find the Duplicate Number), you need a different tool (Floyd's cycle detection treating the array as an implicit linked list, or binary search over the value range) — see `T02-p03-fast-slow` for that alternative.
- **Only an existence check is needed, not a full sort** — the negative-marking variant is enough: for each value `v` encountered, flip the sign of `nums[abs(v) - 1]` to mean "value `v` exists"; a second pass finds which indices were never flipped negative, i.e., which values never appeared.

**Anti-signal:** if the array's values are not constrained to a range tied to its length (arbitrary integers, or a range far larger than `n`), this pattern doesn't apply — fall back to a hash set/map, which handles arbitrary ranges at the cost of `O(n)` space.

---

## Template code (Python, Java, Go)

Base cyclic sort — the reusable skeleton for the entire family:

**Python**
```python
def cyclic_sort(nums: list[int]) -> None:
    """In-place sort of an array containing values 1..n. O(n) time, O(1) space."""
    i = 0
    while i < len(nums):
        correct_index = nums[i] - 1
        if nums[i] != nums[correct_index]:
            nums[i], nums[correct_index] = nums[correct_index], nums[i]
        else:
            i += 1   # nums[i] is already home (or a duplicate occupying it) -- move on
```

**Java**
```java
public void cyclicSort(int[] nums) {
    int i = 0;
    while (i < nums.length) {
        int correctIndex = nums[i] - 1;
        if (nums[i] != nums[correctIndex]) {
            int tmp = nums[i];
            nums[i] = nums[correctIndex];
            nums[correctIndex] = tmp;
        } else {
            i++;
        }
    }
}
```

**Go**
```go
func cyclicSort(nums []int) {
	i := 0
	for i < len(nums) {
		correctIndex := nums[i] - 1
		if nums[i] != nums[correctIndex] {
			nums[i], nums[correctIndex] = nums[correctIndex], nums[i]
		} else {
			i++
		}
	}
}
```

---

## Complexity, derived

The outer `while i < n` loop advances `i` at most `n` times — that part is trivially `O(n)`. The subtlety is the inner swap: at first glance it looks like each of the `n` outer positions could trigger up to `n` swaps, suggesting `O(n^2)`. But every single swap places one specific value into its permanently correct home index, and once a value is at its correct index it is never moved again (the `else` branch that advances `i` is the only way to "leave" a position, and it only fires when the value there is already correct). Since there are only `n` values and each can be placed in its final position at most once, the total number of swaps across the *entire* execution — not per index, but summed over the whole algorithm — is bounded by `n`. Total work is therefore `O(n)` outer advances plus `O(n)` total swaps: **O(n) time, O(1) extra space** (the swaps happen in place; no auxiliary array). This is strictly better than a comparison sort's `O(n log n)` and matches a hash-set approach's `O(n)` time while eliminating its `O(n)` space cost.

---

## The 5 variants interviewers actually ask

1. **Cyclic Sort (base).** Array contains exactly the values `1..n` (or `0..n-1`), no duplicates, no missing. Place each value at its home index via the swap loop above.
2. **Missing Number (LC268).** Array of `n` distinct values from `0..n`, exactly one missing. Modification: home index for value `v` is `v` itself (0-indexed range), and the loop must guard against `nums[i] == n` (out of the valid swap-target range for this specific problem's indexing) before attempting a swap. After the pass, scan for the index `i` where `nums[i] != i`; that `i` is the missing number (or `n` if every index `0..n-1` is correctly filled).
3. **Find All Numbers Disappeared in an Array (LC448) — negative-marking variant.** Array of `n` values in `[1,n]`, duplicates and gaps both possible, no swapping needed since we only care about existence. For each value `v` in the array, negate `nums[abs(v) - 1]` (using `abs` because a slot may already have been negated by an earlier duplicate). A second pass collects every index `i` where `nums[i]` is still positive — those `i+1` values never appeared.
4. **Find All Duplicates in an Array (LC442) — the mirror of variant 3.** Same negative-marking pass, but instead of collecting indices that stayed positive, collect indices where `nums[abs(v)-1]` was *already negative* at the moment you were about to negate it — that means this value has been seen before, i.e., it's a duplicate.
5. **First Missing Positive (LC41) — the hardest composition.** Array of arbitrary integers (not constrained to `[1,n]` at all — negatives, zeros, and values `> n` are all possible). Modification: during the placement pass, only attempt to place a value if it's in the valid range `1..n` (`1 <= nums[i] <= n`) *and* it doesn't already sit at its home; ignore out-of-range values entirely (they can never be "the missing positive," so leave them where they are). After placement, scan for the first index `i` where `nums[i] != i + 1`; that index's `i + 1` is the answer, or `n + 1` if every slot `1..n` is correctly filled.

---

## Common bugs

- **Advancing `i` on every iteration regardless of whether a swap happened.** This is the single most common bug — it breaks the entire correctness argument, because you'd move past index `i` before the value now sitting there has been checked for its own correctness. `i` only advances when the value already at `i` is confirmed home.
- **Infinite loop from an incorrect swap condition.** If duplicates are present and you swap unconditionally without checking `nums[i] != nums[correctIndex]` first, you can swap the same pair back and forth forever. The guard clause is not optional.
- **Off-by-one between a `[1,n]`-range problem (home index is `value - 1`) and a `[0,n-1]`-range problem (home index is `value` itself).** Mixing these up either index-shifts every placement by one or throws an out-of-bounds error.
- **Forgetting `abs()` when reading an index in the negative-marking variant**, once some values in the array have already been flipped negative by earlier iterations — reading `nums[v - 1]` instead of `nums[abs(v) - 1]` on a value that itself got negated earlier produces a nonsensical negative index.
- **Not filtering out-of-range values before attempting a swap in First Missing Positive.** A value like `-5` or `n + 100` has no valid home index in `0..n-1`; attempting `nums[value - 1]` on it either crashes or corrupts an unrelated slot. These values must be explicitly skipped, not swapped.
- **Language-specific tuple-swap evaluation order gotchas.** In Python, `nums[i], nums[correct] = nums[correct], nums[i]` evaluates the right-hand side fully before assigning, so it's safe; but a hand-rolled swap using a temp variable in the wrong order (e.g., overwriting `nums[i]` before reading `nums[correctIndex]` to compute the *next* correct index) is a frequent off-by-one source in Java/Go implementations written under time pressure.

---

## Interview questions

### Q1 — Sort an array containing 1 to n
**Testing:** the base mechanism and whether you can justify O(n) despite the nested-looking loop.
**Answer:** Swap-until-home loop; `i` advances only when `nums[i]` is already correctly placed. O(n) time, O(1) space.
**Follow-up trap:** *"That inner swap looks like it could run n times per index — why isn't this O(n^2)?"* — because each swap seats one value permanently into its final home and a placed value is never revisited; total swaps across the whole run are bounded by `n`, not `n` per index.

### Q2 — Missing Number (LC268)
**Testing:** adapting the home-index formula to a `[0,n]` range instead of `[1,n]`.
**Answer:** Home index for value `v` is `v` itself; guard `nums[i] < n` before swapping (value `n` has no valid slot in a length-`n` array); scan afterward for the first `i` where `nums[i] != i`.
**Follow-up trap:** *"Solve it without modifying the array, using O(1) space."* — sum formula: `n*(n+1)/2 - actual_sum`, or XOR every index and every value together (all pairs cancel except the missing one); both avoid mutation, though the sum formula risks overflow for very large `n` in fixed-width integer languages, which XOR does not.

### Q3 — Find All Numbers Disappeared in an Array (LC448)
**Testing:** the negative-marking variant for existence-only checks, not full placement.
**Answer:** For each value `v`, negate `nums[abs(v)-1]`; afterward, every index still positive represents a missing value (`index + 1`). O(n) time, O(1) extra space (output array doesn't count).
**Follow-up trap:** *"Why do you need abs() when indexing, if you're about to negate the value there?"* — because an earlier duplicate may have already negated that slot; reading `nums[v-1]` without `abs()` once `v` itself has been negated produces an invalid negative array index.

### Q4 — Find All Duplicates in an Array (LC442)
**Testing:** recognizing this as the mirror image of LC448 using the same negative-marking mechanism.
**Answer:** Same negation pass; if `nums[abs(v)-1]` is *already negative* when you're about to mark it, `abs(v)` is a duplicate — collect it before negating (again).
**Follow-up trap:** *"Can you solve both LC448 and LC442 in a single pass over the array?"* — yes: during the one negation pass, whenever you find the target slot already negative, record the duplicate; a second pass then only needs to scan for still-positive slots to get the missing numbers, so the two problems share the same first pass entirely.

### Q5 — Find the Duplicate Number (LC287), cyclic-sort approach
**Testing:** whether you notice this problem can be solved by direct placement (mutating the array) as an alternative to Floyd's cycle detection.
**Answer:** Attempt to place each value at its home index (`value - 1`); the first time a swap would place a value on top of an index that already holds that same value, you've found the duplicate (two values competing for the same home).
**Follow-up trap:** *"The problem says you cannot modify the input array — does your solution still work?"* — no; cyclic sort and negative marking both require mutating the array. If mutation is disallowed, use Floyd's tortoise-and-hare treating `nums[i]` as an implicit linked-list pointer (see `T02-p03-fast-slow`), which needs no mutation, or binary search over the value range counting how many elements are `<=` mid, both O(n) or O(n log n) without touching the array.

### Q6 — Set Mismatch (LC645)
**Testing:** composing "find the duplicate" and "find the missing" into one pass, the natural next step after LC448/LC442.
**Answer:** Run the placement/negative-marking pass once; the duplicate is the value that collides with its own home slot already being occupied by itself, and the missing value is the home index that never gets correctly filled (or never gets negated).
**Follow-up trap:** *"Can the duplicate and the missing number be computed with a single arithmetic pass instead, without any array mutation?"* — yes: `sum(nums) - sum(1..n) = duplicate - missing`, and `sum(nums^2) - sum((1..n)^2) = (duplicate^2 - missing^2) = (duplicate-missing)(duplicate+missing)`; two equations, two unknowns, solvable without touching the array — but be ready to discuss overflow risk on the squared-sum for large `n`.

### Q7 — First Missing Positive (LC41)
**Testing:** the hardest composition — handling an unconstrained input range while still hitting O(1) space.
**Answer:** During placement, only swap a value into its home if it's in `[1,n]` and not already correctly placed; ignore negatives, zero, and values `> n` entirely. Afterward, the first index `i` where `nums[i] != i+1` gives the answer `i+1`; if all slots are correct, the answer is `n+1`.
**Follow-up trap:** *"Walk through why ignoring out-of-range values doesn't break correctness."* — any value outside `[1,n]` can never be "the first missing positive" for an array of length `n` (the answer is always in `[1, n+1]` by pigeonhole — there are only `n` slots, so if all of `1..n` are present the answer must be `n+1`), so those values are irrelevant noise that would otherwise cause an out-of-bounds swap target.

### Q8 — Kth Missing Positive Number (LC1060)
**Testing:** whether you can recognize when cyclic sort is *not* actually the efficient tool, despite surface similarity.
**Answer:** If the input is already sorted, binary search directly for the index where `arr[i] - (i+1) >= k` (counting how many positive numbers are missing before each element) beats an O(n) cyclic-sort-style pass with an O(log n) solution.
**Follow-up trap:** *"Isn't this the same family as Find All Missing Numbers?"* — conceptually related (missing-positive-numbers), but the sorted-input precondition changes the optimal tool from a linear placement pass to binary search; naming the right tool for the given precondition (sorted vs unsorted, range-bounded vs not) is exactly what's being tested.

### Q9 — Array Nesting (LC565)
**Testing:** recognizing a cyclic-sort-adjacent "value as index" structure that's actually a cycle-length problem, not a placement problem.
**Answer:** Each index `i` with `nums[i]` forms an implicit functional graph (`next(i) = nums[i]`); the answer is the length of the longest cycle reachable from any starting index. Traverse each unvisited index, marking visited (e.g., setting seen values to a sentinel or using a separate visited array), counting cycle length, and tracking the max.
**Follow-up trap:** *"Is this cyclic sort?"* — no, despite the superficial resemblance (values used as indices); cyclic sort places values at their homes to detect a single missing/duplicate, while this problem is asking about cycle *structure and length* in the implicit permutation graph, which is closer to the fast/slow-pointer family's "array as linked list" trick than to placement-based cyclic sort.

### Q10 — Couples Holding Hands (LC765), contrast question
**Testing:** whether you can articulate when cyclic sort's precondition does *not* hold, even though the problem "smells" similar (array of paired small integers).
**Answer:** This is a Union-Find / greedy-swap minimum-adjacent-swap problem, not cyclic sort — the array represents seating positions with paired values, and the objective (minimum swaps to pair adjacent seats) doesn't reduce to "place each value at index value-1."
**Follow-up trap:** *"What's the actual giveaway that cyclic sort doesn't apply here?"* — cyclic sort requires a single value to have a single well-defined home index derived directly from its own value; here, correctness depends on *pairs* of adjacent positions and partner relationships, not a per-value home index, so the precondition simply isn't present.

### Q11 — Corrupt array with two swapped values you must find and fix in-place
**Testing:** whether you can generalize the placement-collision idea to a slightly different framing (detect a swap error rather than duplicate/missing).
**Answer:** Run the placement pass; the two indices where a collision occurs during placement (a value trying to occupy a slot already correctly filled with something else, and vice versa) are exactly the swapped pair; swap them back to restore the array to `1..n` order.
**Follow-up trap:** *"How do you distinguish this from Set Mismatch (LC645)?"* — Set Mismatch has one value appearing twice and one missing (not a clean swap); a true "two values swapped" corruption has no missing value at all — every value `1..n` is still present, just two of them occupy each other's home slots. Confirming which scenario you're in (via a quick presence check) before choosing the fix avoids misapplying the wrong repair logic.

---

## Red flags that fail you

- Advancing the index pointer on every loop iteration regardless of whether the swap actually placed a value correctly, breaking the whole invariant.
- Claiming the algorithm is O(n^2) because of the nested while loop, without being able to derive the amortized O(n) bound from "each swap places one value permanently."
- Swapping unconditionally without checking whether the value is already home, causing an infinite loop on duplicate-containing input.
- Attempting a swap on a value outside the valid range in First Missing Positive, causing an out-of-bounds error instead of skipping it.
- Not noticing "you cannot modify the input array" rules out cyclic sort and negative marking entirely, and reaching for them anyway.
- Confusing the `[1,n]` home-index formula (`value - 1`) with the `[0,n-1]`/`[0,n]` formula (`value` itself), producing consistently off-by-one-wrong placements.

---

## Cheat card

```
PRECONDITION    array of n values in a KNOWN range tied to n: [1,n], [0,n-1], or [0,n]
HOME INDEX      [1,n] range: value - 1     |     [0,n-1]/[0,n] range: value itself
LOOP RULE       advance i ONLY when nums[i] is already at its home index
SWAP GUARD      check nums[i] != nums[home] BEFORE swapping, or duplicates infinite-loop you
COMPLEXITY      looks O(n^2), IS O(n): each swap seats one value permanently, total swaps <= n
MISSING (LC268) home = value; guard value < n before swap; scan for first nums[i] != i
NEG. MARKING    for existence-only checks: negate nums[abs(v)-1]; use abs() -- slots may already be negative
MISSING SET     (LC448) collect indices still positive after marking pass = missing values
DUP SET         (LC442) collect abs(v) where nums[abs(v)-1] was ALREADY negative = duplicates
FIRST MISS POS  (LC41) ignore/skip any value outside [1,n] during placement; answer in [1, n+1]
CANNOT MUTATE   input immutable -> cyclic sort is OFF THE TABLE; use Floyd's (fast/slow) or binary search
NOT THIS        Array Nesting / Couples Holding Hands look similar but need cycle-length or graph tools
```

## Sources
- [Missing Number — LeetCode](https://leetcode.com/problems/missing-number/) — accessed 2026-07-27
- [Find All Numbers Disappeared in an Array — LeetCode](https://leetcode.com/problems/find-all-numbers-disappeared-in-an-array/) — accessed 2026-07-27
- [Find All Duplicates in an Array — LeetCode](https://leetcode.com/problems/find-all-duplicates-in-an-array/) — accessed 2026-07-27
- [First Missing Positive — LeetCode](https://leetcode.com/problems/first-missing-positive/) — accessed 2026-07-27
- [Set Mismatch — LeetCode](https://leetcode.com/problems/set-mismatch/) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
