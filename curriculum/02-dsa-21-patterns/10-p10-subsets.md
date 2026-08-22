# Subsets / Combinatorics

> **Track:** T02 DSA: 21 Patterns · **Time:** 2h · **Prereqs:** T02-p08-dfs · **Updated:** 2026-07-27
> **Module id:** `T02-p10-subsets` · **Tags:** pattern, backtracking, combinatorics

## The 30-second version

Subsets/Combinatorics generates every subset, permutation, or combination of a collection using a DFS/backtracking tree in which each node is a partial choice sequence and each level down the tree represents one more decision — include or exclude an element, or "which unused element comes next." The exponential (or factorial) blowup here is not a complexity bug to optimize away, it's the actual size of the answer: there really are `2^n` subsets, `n!` permutations, and `C(n,k)` combinations, so the best possible total runtime is bounded below by the output size itself; the engineering work is generating each valid result exactly once, correctly skipping duplicates when the input has repeated elements, and pruning dead branches as early as possible rather than discovering their invalidity after fully constructing them. Recognize this from "generate all subsets/permutations/combinations," "print all possible ...," and distinguish it sharply from a *counting* question ("how many subsets satisfy X"), which can sometimes be answered in polynomial time via a formula or DP without ever enumerating anything. The three building blocks every variant is built from are: the include/exclude branch (subsets), the choose-next-unused-element branch (permutations), and the start-index branch that prevents reordered duplicates (combinations).

## Why this gets asked

The interviewer is testing whether the backtracking template — choose, recurse, un-choose — is truly internalized rather than pattern-matched from memory, because the moment duplicates enter the input or reuse rules change (can the same element be picked twice? must results respect original order?), a memorized-but-not-understood implementation breaks in ways that are hard to debug live. This connects to real system-design-adjacent thinking: generating all valid configurations of a constrained system (feature flag combinations, test-case generation, config validation) is exactly this combinatorial-enumeration problem, and knowing when *not* to enumerate — because the count alone is answerable in polynomial time, or because the true requirement is "does at least one valid configuration exist" rather than "list them all" — is the more senior signal. The sharper follow-up that separates levels is duplicate handling: Subsets II and Permutations II both require skipping duplicates, but the correct skip condition is subtly different between the two (compare siblings at the same recursion level for subsets; check a `used[]` flag alongside the equality check for permutations), and getting this wrong either silently produces duplicate output or silently drops valid results.

---

## Lineage: past → present → future

**What came before.** Enumerating permutations systematically predates computing: English "change ringing" (bell-ringing) methods from the 17th century are early documented algorithms for generating all permutations of a set of bells via minimal adjacent swaps, and the Steinhaus–Johnson–Trotter algorithm (formalized 1962–1963) gives a systematic minimal-change ordering for generating all permutations one adjacent transposition at a time. Subset generation via binary counting (treating each subset as an n-bit number where bit `i` means "include element `i`") is a direct, older application of binary representation to combinatorics, predating its interview framing by decades. Before backtracking was standardized as the general interview template, ad hoc nested-loop code for small fixed `n` (three or four nested loops for triples/quadruples) was common, which simply doesn't generalize to arbitrary `n`.

**Where it stands now.** DFS/backtracking (choose, recurse, un-choose) is the general-purpose, universally expected tool for generating subsets, permutations, and combinations of arbitrary size; there's no disagreement about the core technique. Iterative bitmask enumeration (looping `mask` from `0` to `2^n - 1`, checking each bit to decide inclusion) remains a valid, sometimes-preferred alternative specifically for subset generation when `n` is small and a non-recursive implementation is wanted, but it doesn't generalize cleanly to permutations or constrained combinations the way backtracking does. What separates fluency levels in practice is correct duplicate handling (the sort-then-skip-same-level-siblings discipline) and recognizing when a *counting* question doesn't require enumeration at all — e.g., counting subsets summing to a target is a 0/1 knapsack-style DP problem in pseudo-polynomial time, not a backtracking-and-count problem, once you only need the count and not the actual subsets.

**Where it's heading.** The core generation techniques are closed, classical results with essentially no room to change. What's shifting is emphasis toward "generate the k-th permutation/combination directly, without generating all the preceding ones" (Permutation Sequence, and the broader combinatorial/factorial number system) as the higher-signal follow-up question, because it tests whether you understand the *counting structure* underlying the enumeration well enough to jump directly to a specific index, rather than brute-force generating and discarding — a meaningfully different skill from just being able to produce the full list.

---

## Mental model

```
Subsets of {1, 2, 3} via include/exclude DFS:

                         []
                /                    \
            include 1              exclude 1
              [1]                     []
           /       \                /      \
      incl 2      excl 2        incl 2    excl 2
       [1,2]       [1]          [2]         []
       /    \      /   \        /   \       /  \
  incl3 excl3  incl3 excl3   incl3 excl3  incl3 excl3
 [1,2,3][1,2] [1,3]  [1]    [2,3]  [2]    [3]    []

8 leaves = 2^3 subsets. Each leaf is a distinct subset; the path from root
to leaf encodes the include/exclude decision made at each of the 3 elements.


Permutations of {1, 2, 3} via choose-next-unused DFS:

                    []
        /            |            \
      [1]           [2]           [3]        <- 3 choices at level 1
     /    \         /    \        /    \
  [1,2] [1,3]    [2,1] [2,3]   [3,1] [3,2]    <- 2 remaining choices at level 2
    |     |         |     |       |     |
 [1,2,3][1,3,2]  [2,1,3][2,3,1] [3,1,2][3,2,1] <- 1 choice left, 6 = 3! leaves
```

The backtracking template underlying both: **choose** an option (append to the current path, mark used if needed), **explore** (recurse one level deeper), **un-choose** (pop from the path, unmark used) before trying the next sibling option. The "un-choose" step is what lets one shared, mutated path structure correctly represent every branch without leaking state between siblings.

---

## Recognition heuristics

- **"Generate all subsets" / "power set"** — DFS include/exclude at each index (or iterative bitmask `0` to `2^n - 1` for a non-recursive alternative).
- **"Generate all permutations" / "all possible orderings"** — DFS choosing the next unused element at each level; implementations either track a `used[]` boolean array or, for in-place variants, swap the chosen element to the current position and swap back afterward.
- **"Generate all combinations of size k"** — DFS with a `start` index parameter that only allows choosing from `start` onward as you recurse, which is exactly what prevents generating the same combination in multiple reordered forms (unlike permutations, order doesn't matter for combinations, so this start-index discipline is required, not optional).
- **Input has duplicate values and the problem says "no duplicate subsets/permutations in the output"** — sort the input first, then at each branching point skip a sibling option if it's equal to the immediately preceding sibling *already tried at this exact recursion level* — not equal to any earlier element anywhere in the array, and not (for permutations specifically) simply "equal to the previous array element" without an additional `used[]` check.
- **"How many subsets/combinations satisfy property X"** without needing the actual list — check whether this reduces to a counting/DP formulation (e.g., subset-sum counting is a knapsack-style DP) before reaching for backtracking-with-a-counter, since enumerating everything just to count it throws away a potentially much cheaper polynomial-time counting approach.
- **"Elements can be reused" vs. "each element used at most once"** — reuse-allowed problems (Combination Sum) recurse with the *same* start index (`i`, not `i+1`) after choosing an element, since it remains eligible to be chosen again; no-reuse problems (Combination Sum II) advance to `i+1`.

**Anti-signal:** if the question only asks for the *count* of valid configurations and a closed-form or DP recurrence exists (e.g., `C(n,k)` computed directly, or a knapsack-style subset-sum count), generating and counting every configuration is strictly worse than the direct formula/DP — don't default to backtracking just because the word "combinations" appears.

---

## Template code (Python, Java, Go)

Subset generation (include/exclude) and permutation generation (choose-next-unused) — the two foundational skeletons:

**Python**
```python
def subsets(nums: list[int]) -> list[list[int]]:
    """All subsets (the power set). O(2^n * n) time/space."""
    result = []
    path = []

    def backtrack(start: int) -> None:
        result.append(path[:])              # record a COPY, not the live list
        for i in range(start, len(nums)):
            path.append(nums[i])            # choose
            backtrack(i + 1)                # explore
            path.pop()                      # un-choose

    backtrack(0)
    return result

def permutations(nums: list[int]) -> list[list[int]]:
    """All permutations. O(n! * n) time/space."""
    result = []
    path = []
    used = [False] * len(nums)

    def backtrack() -> None:
        if len(path) == len(nums):
            result.append(path[:])
            return
        for i in range(len(nums)):
            if used[i]:
                continue
            used[i] = True                  # choose
            path.append(nums[i])
            backtrack()                     # explore
            path.pop()                      # un-choose
            used[i] = False

    backtrack()
    return result
```

**Java**
```java
public List<List<Integer>> subsets(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrackSubsets(nums, 0, new ArrayList<>(), result);
    return result;
}
private void backtrackSubsets(int[] nums, int start, List<Integer> path, List<List<Integer>> result) {
    result.add(new ArrayList<>(path));   // record a copy
    for (int i = start; i < nums.length; i++) {
        path.add(nums[i]);
        backtrackSubsets(nums, i + 1, path, result);
        path.remove(path.size() - 1);
    }
}

public List<List<Integer>> permute(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrackPermute(nums, new boolean[nums.length], new ArrayList<>(), result);
    return result;
}
private void backtrackPermute(int[] nums, boolean[] used, List<Integer> path, List<List<Integer>> result) {
    if (path.size() == nums.length) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        used[i] = true;
        path.add(nums[i]);
        backtrackPermute(nums, used, path, result);
        path.remove(path.size() - 1);
        used[i] = false;
    }
}
```

**Go**
```go
func subsets(nums []int) [][]int {
	var result [][]int
	var path []int
	var backtrack func(start int)
	backtrack = func(start int) {
		snapshot := append([]int(nil), path...) // copy
		result = append(result, snapshot)
		for i := start; i < len(nums); i++ {
			path = append(path, nums[i])
			backtrack(i + 1)
			path = path[:len(path)-1]
		}
	}
	backtrack(0)
	return result
}

func permute(nums []int) [][]int {
	var result [][]int
	var path []int
	used := make([]bool, len(nums))
	var backtrack func()
	backtrack = func() {
		if len(path) == len(nums) {
			snapshot := append([]int(nil), path...)
			result = append(result, snapshot)
			return
		}
		for i := 0; i < len(nums); i++ {
			if used[i] {
				continue
			}
			used[i] = true
			path = append(path, nums[i])
			backtrack()
			path = path[:len(path)-1]
			used[i] = false
		}
	}
	backtrack()
	return result
}
```

---

## Complexity, derived

For subsets: the recursion tree has exactly `2^n` leaves (each of the `n` elements is independently included or excluded), and building/copying each resulting subset costs up to `O(n)`, so total time is **O(2^n * n)**, and space for the output alone is the same. For permutations: the tree has `n` choices at the first level, `n-1` at the second, down to `1` at the last, giving exactly `n!` leaves, each requiring `O(n)` to copy into the result, so total time is **O(n! * n)**. For combinations of size `k` chosen from `n`: exactly `C(n,k) = n! / (k! * (n-k)!)` leaves, each costing `O(k)` to build, giving **O(C(n,k) * k)**. In every case, this is the *minimum possible* runtime for true enumeration — you cannot list `2^n` (or `n!`, or `C(n,k)`) results any faster than `O(output size)`, so the only real complexity lever available is pruning: cutting off a branch before fully descending it once you can prove it can't produce a valid result (e.g., in combinations of size `k`, stopping early if fewer than `k - len(path)` elements remain to choose from, since that branch mathematically cannot reach the required size).

---

## The 5 variants interviewers actually ask

1. **Subsets (LC78).** The base include/exclude DFS, no duplicates in input.
2. **Subsets II (LC90) — input contains duplicates, no duplicate subsets allowed in output.** Modification: sort the input first; at each level of the `for` loop, skip an index `i` (where `i > start`) if `nums[i] == nums[i-1]` — this compares only *siblings already tried at the current branching point*, which correctly allows the same value to appear at different depths in different branches while preventing the same branching point from producing the same subset twice.
3. **Permutations (LC46).** The base choose-next-unused DFS using a `used[]` array (or an in-place swap variant), no duplicates.
4. **Permutations II (LC47) — input contains duplicates, no duplicate permutations allowed.** Modification: sort first; at each level, skip choosing `nums[i]` if `nums[i] == nums[i-1]` **and** `used[i-1]` is `False` — the `used[i-1] == False` condition specifically means "the identical previous value was already un-chosen (backtracked out of) at this same level in an earlier sibling branch," which is the subtly different condition from Subsets II's simpler "already tried at this level" check, because permutations revisit the full unused set at every level rather than only looking forward from a `start` index.
5. **Combination Sum (LC39) — elements may be reused unlimited times, must sum exactly to a target.** Modification: after choosing `nums[i]`, recurse with `start = i` (not `i + 1`), since `nums[i]` remains eligible to be chosen again; prune any branch where the running sum exceeds the target.

---

## Common bugs

- **Recording a reference to the live `path` list instead of a copy at each valid result.** Because `path` continues being mutated (appended and popped) throughout the rest of the traversal, every recorded result ends up reflecting whatever `path` looks like at the very end unless a snapshot (`path[:]` in Python, `new ArrayList<>(path)` in Java, a freshly-allocated slice copy in Go) is taken at the moment of recording.
- **Forgetting the un-choose (pop/unmark) step after the recursive call returns.** This leaks state from one branch into its siblings — a corrupted `path` or `used[]` array causes subsequent branches to behave as if earlier, already-explored choices are still active.
- **Using the wrong duplicate-skip condition for Subsets II vs. Permutations II.** Subsets II only needs to compare adjacent siblings at the current branching point (`i > start` in the same `for` loop); Permutations II needs the additional `used[i-1] == False` check specifically because permutations reconsider the *entire* remaining set at every recursion level, not just a forward-moving `start` window — using Subsets II's simpler condition on a permutations problem either misses valid permutations or leaves duplicates, depending on which way the condition is inverted.
- **Confusing `start = i` (reuse allowed, Combination Sum) with `start = i + 1` (no reuse, Combination Sum II).** Swapping these breaks the reuse semantics entirely — using `i` when reuse isn't allowed produces combinations with repeated elements that shouldn't exist; using `i + 1` when reuse is required silently makes some valid combinations unreachable.
- **Not pruning branches that mathematically cannot succeed.** In fixed-size-`k` combinations, failing to check whether enough elements remain (`len(nums) - start >= k - len(path)`) before recursing wastes time descending into branches that can never reach the required length — correct but needlessly slow.
- **Conflating a counting question with an enumeration question.** Backtracking-with-a-counter to answer "how many subsets sum to target" works but is exponential; if only the count is needed, a DP formulation (subset-sum counting, `O(n * target)`) is usually available and is the answer a senior interviewer is actually listening for.

---

## Interview questions

### Q1 — Subsets (LC78)
**Testing:** the base include/exclude backtracking template.
**Answer:** DFS with a `start` index; record the current path at every node (not just leaves — every prefix is itself a valid subset); recurse forward from `start`, popping after each recursive call. O(2^n * n).
**Follow-up trap:** *"Do it iteratively instead."* — either bitmask enumeration (loop `mask` from `0` to `2^n - 1`, include `nums[i]` if bit `i` of `mask` is set) or the "double the result list" technique (for each new element, take every existing subset and add a copy with the new element appended) both work; be ready to produce either without defaulting only to recursion.

### Q2 — Subsets II (LC90)
**Testing:** the correct duplicate-skip condition for subset generation specifically.
**Answer:** Sort first; in the `for` loop, skip index `i` (where `i > start`) if `nums[i] == nums[i-1]`, preventing the same branching point from producing the same subset via two equal sibling choices.
**Follow-up trap:** *"Why does the condition check `i > start` and not just `i > 0`?"* — `i > 0` would also compare against elements from an *earlier* recursion level (already consumed into the current path), which is a completely different and unrelated comparison; the skip must only ever compare against a sibling already tried at the *current* branching point, which is exactly what `i > start` (not `i > 0`) restricts to.

### Q3 — Permutations (LC46)
**Testing:** the base choose-next-unused template, and whether an in-place swap alternative is also known.
**Answer:** `used[]` array tracking which elements are already placed, or an in-place swap-and-swap-back variant that avoids the extra boolean array by physically swapping the chosen element into the current position.
**Follow-up trap:** *"What's the tradeoff between the `used[]` array approach and the in-place swap approach?"* — the swap approach avoids an extra `O(n)` auxiliary array and can be marginally faster in practice, but it mutates the input array during the traversal (restored by swapping back after each recursive call), which is a problem if the caller needs the original array left untouched mid-traversal or if the traversal needs to be interrupted safely.

### Q4 — Permutations II (LC47)
**Testing:** the subtler duplicate-skip condition unique to permutations.
**Answer:** Sort first; skip choosing `nums[i]` if `nums[i] == nums[i-1]` and `used[i-1]` is `False`.
**Follow-up trap:** *"What if you used `used[i-1] == True` instead of `False` — what breaks?"* — flipping the condition either produces duplicate output (if the check becomes too permissive) or silently drops valid permutations (if it becomes too restrictive); the `False` condition specifically identifies "the previous identical value was already tried and fully backtracked out of at this same level," which is the one specific situation duplication would otherwise occur in — walking through a concrete 3-element duplicate case (e.g., `[1,1,2]`) live is the fastest way to verify which direction is correct under pressure.

### Q5 — Combinations (LC77)
**Testing:** the start-index discipline that prevents reordered duplicates for a fixed-size-k result.
**Answer:** DFS with a `start` parameter, recursing forward only; stop recording once the path reaches length `k`.
**Follow-up trap:** *"Add a pruning condition that measurably speeds this up for large n and small k."* — check `len(nums) - start + 1 >= k - len(path)` (enough elements remain to complete the combination) before entering the loop body for that branch at all; without it, the algorithm still produces correct output but wastes time descending into branches that can never reach length `k`.

### Q6 — Combination Sum (LC39)
**Testing:** correctly implementing unlimited reuse of a chosen element.
**Answer:** After choosing `nums[i]`, recurse with `start = i` (not `i + 1`), since `nums[i]` is still eligible to be chosen again; prune whenever the running sum exceeds the target.
**Follow-up trap:** *"The input can include duplicate values themselves (not asking about reusing an element, but the input array having repeats) — does that require extra handling?"* — Combination Sum's own constraints typically guarantee distinct input values; if duplicates were present in the input alongside reuse being allowed, you'd need the same sort-and-skip-siblings discipline from Subsets II layered on top of the reuse logic, since both concerns (input duplicates vs. intentional reuse) are independent and can co-occur.

### Q7 — Combination Sum II (LC40)
**Testing:** the no-reuse, duplicates-in-input variant — combining two distinct constraints correctly.
**Answer:** Sort first; recurse with `start = i + 1` (no reuse); skip index `i` (where `i > start`) if `nums[i] == nums[i-1]`, exactly the Subsets II duplicate-skip condition, applied here on top of the sum-target pruning.
**Follow-up trap:** *"How is this different from Combination Sum in exactly one line of code, and why does that one line matter so much?"* — the only structural difference is `start = i` vs. `start = i + 1` in the recursive call; that single character changes the entire semantics from "elements may repeat" to "each input position used at most once," which is exactly why interviewers use this pair to test precise understanding rather than memorized templates.

### Q8 — Letter Combinations of a Phone Number (LC17)
**Testing:** recognizing a Cartesian-product-style backtracking shape distinct from include/exclude or choose-next-unused.
**Answer:** DFS building a string of a fixed target length (equal to the number of input digits); at each position, iterate over the small fixed set of letters mapped to that digit, appending one and recursing to the next position.
**Follow-up trap:** *"Is this fundamentally different from generating subsets or permutations?"* — yes: there's no "used" tracking and no include/exclude choice; every position in the output *must* be filled from a small, position-specific set of options, making this closer to a nested-loop Cartesian product than to subset/permutation generation, even though it uses the identical choose/explore/un-choose backtracking skeleton.

### Q9 — Permutation Sequence (LC60)
**Testing:** whether you can skip enumeration entirely once only a specific index is needed.
**Answer:** Use the factorial number system: at each position, the number of remaining permutations per choice of the next digit is `(remaining count - 1)!`; divide the target index by that factorial to determine which of the remaining digits goes next, then reduce the index modulo that factorial and repeat for the next position — no generation of any permutation other than the target one.
**Follow-up trap:** *"What's the complexity of your approach versus generating all `n!` permutations and indexing into the list?"* — the factorial-number-system approach is `O(n^2)` (or `O(n log n)` with a Fenwick-tree-backed "remove the k-th remaining element" step), decisively better than `O(n!)` to generate every permutation just to discard all but one; this is precisely the kind of "understand the counting structure, skip the enumeration" question interviewers increasingly favor over plain generation.

### Q10 — Palindrome Partitioning (LC131)
**Testing:** backtracking with an additional per-branch validity constraint layered on top of the base subset/substring-splitting skeleton.
**Answer:** DFS choosing where to "cut" the string next; at each candidate cut, only recurse into it if the substring formed since the last cut is itself a palindrome (checked directly, or precomputed via a palindrome DP table for repeated substring checks); record the full partition when the end of the string is reached.
**Follow-up trap:** *"How would you avoid re-checking whether the same substring is a palindrome multiple times across different branches?"* — precompute an `O(n^2)` DP table (`is_palindrome[i][j]`) once up front via the standard "expand from center" or bottom-up length-increasing DP, turning every palindrome check inside the backtracking into an O(1) lookup instead of an O(n) re-scan each time.

### Q11 — Count the number of subsets that sum to a target, without listing them
**Testing:** whether you reach for backtracking-with-a-counter out of habit, or recognize the polynomial-time DP alternative.
**Answer:** This reduces to a 0/1-knapsack-style counting DP: `dp[s]` = number of subsets seen so far summing to `s`, updated for each element by iterating `s` from `target` down to the element's value and adding `dp[s - element]` into `dp[s]`. `O(n * target)` time, pseudo-polynomial.
**Follow-up trap:** *"Why is backtracking-with-a-counter still exponential here, even though you're not printing anything?"* — the counter approach still visits every one of the up to `2^n` subset branches to check whether it sums to the target; the DP approach never enumerates subsets at all, it only tracks *how many ways* each intermediate sum can be reached, collapsing an exponential search into a polynomial one because it reuses shared sub-computation across many different subsets that happen to reach the same partial sum.

### Q12 — Beautiful Arrangement / N-Queens as a contrast question
**Testing:** whether you can distinguish plain subset/permutation generation from constraint-heavy backtracking that needs aggressive pruning to be tractable.
**Answer:** Both are still built on the same choose/explore/un-choose skeleton as permutations, but each candidate choice must additionally satisfy a validity check *before* recursing deeper (an arrangement's divisibility condition; a queen's non-attack condition against all previously placed queens) — without early pruning on an invalid partial state, the search would still terminate correctly but would waste enormous time fully descending into branches doomed from the very first invalid placement.
**Follow-up trap:** *"Is N-Queens the same pattern as this module, or does it belong somewhere else?"* — it's the same underlying DFS/backtracking skeleton, but the emphasis shifts entirely to constraint validation and pruning rather than the enumeration structure itself, which is why it's treated as the flagship example of the dedicated Backtracking pattern (`T02-p21-backtracking`) rather than this module — this module is about generating the *raw* combinatorial structures; that module is about pruning a *constrained* search space built on top of them.

---

## Red flags that fail you

- Recording a live reference to the mutable path instead of a snapshot copy at each result.
- Forgetting to un-choose (pop/unmark) after a recursive call returns, leaking state between sibling branches.
- Using the wrong duplicate-skip condition — Subsets II's simple sibling check where Permutations II's `used[i-1] == False` check is actually required, or vice versa.
- Confusing `start = i` (reuse allowed) with `start = i + 1` (no reuse), inverting the intended semantics.
- Reaching for exhaustive backtracking-and-count when only a count is needed and a polynomial-time DP formulation exists.
- Not recognizing when a problem needs the k-th result directly (factorial/combinatorial number system) rather than full enumeration.

---

## Cheat card

```
TEMPLATE        choose -> explore (recurse) -> un-choose (backtrack) -- always in that order
SUBSETS         include/exclude each index; record path at EVERY node, not just leaves; 2^n leaves
PERMUTATIONS    choose next UNUSED element each level; used[] array or in-place swap; n! leaves
COMBINATIONS(k) start-index DFS, forward-only; C(n,k) leaves; prune if remaining < k - len(path)
COMPLEXITY      always >= output size: O(2^n * n), O(n! * n), O(C(n,k) * k) -- can't beat this
DEDUP SUBSETS   sort; skip i>start where nums[i]==nums[i-1]  (compare SIBLINGS at this level only)
DEDUP PERMS     sort; skip if nums[i]==nums[i-1] AND used[i-1]==False (subtly different condition!)
REUSE ALLOWED   recurse with start=i   (Combination Sum)
NO REUSE        recurse with start=i+1  (Combination Sum II, Subsets, Combinations)
RECORD RESULT   ALWAYS copy the path (path[:], new ArrayList<>(path)) -- never store the live reference
COUNT != LIST   "how many subsets sum to X" -> knapsack-style DP O(n*target), NOT backtracking+counter
KTH DIRECTLY    Permutation Sequence: factorial number system, O(n^2), skip full enumeration entirely
NOT THIS        heavy per-choice CONSTRAINT validation (N-Queens) -> see T02-p21-backtracking instead
```

## Sources
- [Subsets — LeetCode](https://leetcode.com/problems/subsets/) — accessed 2026-07-27
- [Subsets II — LeetCode](https://leetcode.com/problems/subsets-ii/) — accessed 2026-07-27
- [Permutations II — LeetCode](https://leetcode.com/problems/permutations-ii/) — accessed 2026-07-27
- [Combination Sum — LeetCode](https://leetcode.com/problems/combination-sum/) — accessed 2026-07-27
- [Permutation Sequence — LeetCode](https://leetcode.com/problems/permutation-sequence/) — accessed 2026-07-27
- [Palindrome Partitioning — LeetCode](https://leetcode.com/problems/palindrome-partitioning/) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
