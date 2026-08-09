# Pattern: 0/1 Knapsack DP

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** arrays, recursion, T02-p10-subsets
> **Module id:** `T02-p15-knapsack-01` · **Tags:** pattern, dp
> **Practice:** the Problems tab in the app — this pattern has curated LeetCode problems rather than a lab

## The 30-second version

0/1 knapsack is the pattern for "choose a subset of items, each usable at most once, to optimize a value subject to a capacity constraint." The recurrence is `dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]] + val[i])` if `wt[i] <= w`, else `dp[i][w] = dp[i-1][w]` — at every item you either skip it or take it, and "take it" reaches back into the *previous* item's row so nothing gets used twice. It runs in O(n·W) time and the 2D table collapses to a 1D array of size W by iterating the capacity dimension **backward** (high to low) on each item — backward is what preserves the once-only guarantee, because it stops the update for a smaller capacity from reading a value this same item already wrote. That single direction question — "why backward, and what breaks if you go forward" — is the most common trap in DP interviews, because forward iteration silently turns 0/1 knapsack into unbounded knapsack. Recognize it whenever a problem gives you weight/value pairs, a hard capacity, and the phrase "each item once," or its disguised forms: subset sum, equal-subset partition, and target-sum assignment.

## Why this gets asked

It tests two things simultaneously: can you build a DP recurrence from the recursive choice (include vs exclude) instead of pattern-matching to a memorized table, and do you actually understand *why* the space optimization works instead of reciting it. Interviewers who have done capacity planning — bin-packing GPU memory across jobs, allocating an ad budget across campaigns, fitting a release train into a fixed deploy window — have lived through the real failure: get the iteration direction wrong in a hand-rolled optimizer and items get "reused," silently inflating an achievable value past what the constraint actually allows. It also probes whether you know the problem is NP-complete in general but the DP is only pseudo-polynomial, which matters the moment capacity is a large number instead of a small bounded one.

---

## Lineage: past → present → future

**What came before.** The original approach is brute-force subset enumeration: try all 2^n subsets, check capacity, keep the best value. That's fine to about n=20–25 before it becomes unusable. Meet-in-the-middle — split items into two halves, enumerate 2^(n/2) subsets of each, sort one half and binary-search or two-pointer against the other — pushes brute force out to roughly n=40, still exponential but with a much better constant. Dynamic programming replaced both once Richard Bellman formalized the "principle of optimality" in his 1957 book *Dynamic Programming*, using resource-allocation problems structurally identical to knapsack as the motivating examples. The pain the DP killed: exponential blowup for the sizes that show up in real allocation problems (hundreds to low thousands of items), where W is small enough that O(n·W) is actually tractable.

**Where it stands now.** Closed, settled math — no live methodological disagreement about the algorithm itself. The one thing worth stating out loud in an interview: 0/1 knapsack's *decision version* ("can we hit value V within capacity W?") is NP-complete, and the DP solving it in O(n·W) is **pseudo-polynomial** — polynomial in the *numeric value* of W, not in the number of bits needed to represent W. That's why the DP looks like it "solves an NP-complete problem in polynomial time" without actually violating P ≠ NP: if W is 10^9, O(n·W) is not remotely fast. The remaining debate in interviews is presentational — whether to lead with recursion+memo, bottom-up 2D, or straight to the 1D optimization — and interviewers vary on which one they want to see derived live.

**Where it's heading.** Nothing changes for the interview version; this is 65-year-old math. Where it's actually used at scale: real resource-allocation systems with large capacities (cloud instance bin-packing, portfolio selection under a budget, ad-slot allocation) reach for greedy fractional relaxation, LP/ILP solvers (OR-Tools, CBC, Gurobi), or FPTAS (fully polynomial-time approximation schemes) instead of exact DP, because W in production is rarely small enough for O(n·W) to be practical. Saying "exact DP only works because W is bounded here; at scale I'd relax to an LP or use OR-Tools" is the senior answer.

---

## Mental model

Build a table row by row, one item at a time. Row `i` answers: "using only items `1..i`, what's the best value achievable at every capacity `0..W`?"

```
items: (wt=2,val=3), (wt=3,val=4), (wt=4,val=5)   W=5

           w=0  1  2  3  4  5
dp[0][.]    0   0  0  0  0  0     <- no items yet
dp[1][.]    0   0  3  3  3  3     <- item1 (wt2,val3): available from w=2 on
dp[2][.]    0   0  3  4  4  7     <- item2 (wt3,val4): 7 = 3(item1) + 4(item2) at w=5
dp[3][.]    0   0  3  4  5  7     <- item3 (wt4,val5): doesn't beat 7 at w=5
```

Each cell only ever looks **up** (previous row) — that's the whole basis for collapsing to 1D, and the reason the collapse must walk capacity backward: overwrite cells right-to-left so that when you read `dp[w-wt]` you're still reading last item's value, not this item's just-written one.

---

## Recognition heuristics

- **"Each item can be used at most once"** paired with a weight/capacity constraint and a value to maximize — the textbook signature.
- **"Does a subset sum to exactly X?"** — subset sum is 0/1 knapsack where weight equals value and you're checking reachability instead of maximizing.
- **"Partition into two subsets with minimum difference"** or **"...with equal sum"** — reduce to subset sum against `total/2`.
- **"Assign + and − signs to reach a target sum"** (Target Sum) — algebraic reduction collapses this to subset sum too; recognizing the reduction *is* the interview.
- **"Count the number of subsets that sum to a target"** — same table, sum instead of max/OR at the transition.
- **Two independent budget dimensions** ("at most m zeros and n ones") — 2D 0/1 knapsack, one extra table axis, same once-only backward-iteration logic per axis.
- **A qualifier like "solve this in O(W) space"** attached to a table that looks 2D — that's the interviewer explicitly asking for the space-optimized 1D form.

If the problem instead says an item can be reused arbitrarily many times, this is **not** this pattern — that's unbounded knapsack (`T02-p16-knapsack-unbounded`), and the space-optimization direction flips.

---

## How it actually works — deriving the recurrence and the space optimization

**The recurrence.** Define `dp[i][w]` = max value achievable using only the first `i` items with total weight at most `w`. Each item is either skipped or taken — there's no third option, so the recurrence is a two-way max:

```
dp[0][w] = 0                                            for all w   (no items -> no value)
dp[i][w] = dp[i-1][w]                                    if wt[i] > w   (can't fit; forced skip)
dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]] + val[i])    if wt[i] <= w  (best of skip vs take)
```

`dp[i-1][w-wt[i]]` is the key move: "if I commit `wt[i]` capacity to this item, what's the best I could already do with the *remaining* capacity using only items before this one." Because it always reaches into row `i-1`, item `i` can never see itself — that's what "used at most once" means mechanically.

Answer is `dp[n][W]`. Time and space for the 2D table are both O(n·W).

**Why the 1D collapse needs backward iteration.** Since `dp[i][*]` only ever reads `dp[i-1][*]`, you don't need to keep every row — one array `dp[w]` updated in place, item by item, is enough, *provided* the update for capacity `w` still reads the old (previous-item) value at `w - wt[i]` and not a value item `i` already wrote earlier in the same pass.

If you iterate `w` from `wt[i]` up to `W` (ascending), by the time you compute `dp[w]` you may have already overwritten `dp[w-wt[i]]` earlier in this same loop — with a version that *already includes item i*. Then `dp[w] = max(dp[w], dp[w-wt[i]] + val[i])` would let item `i` contribute twice: once to build the `w-wt[i]` cell, again added on top for the `w` cell. That's exactly unbounded knapsack's recurrence (deliberately, see `T02-p16-knapsack-unbounded`) — ascending iteration silently permits unlimited reuse of the current item within one pass.

Iterating `w` from `W` down to `wt[i]` (descending) guarantees that when you read `dp[w-wt[i]]`, that cell is smaller-indexed and **hasn't been touched yet this item**, so it still holds the previous item's row — the correct "before this item" state. That's the entire mechanism; no other magic is involved.

```
1D update per item (0/1, must go backward):
for w in range(W, wt[i]-1, -1):
    dp[w] = max(dp[w], dp[w-wt[i]] + val[i])
```

For subset-sum-style boolean variants, the same backward pass applies to a boolean array: `dp[w] = dp[w] or dp[w-wt[i]]`.

---

## Template code (Python, Java, Go)

```python
# Python — 0/1 Knapsack: 2D tabulation (clearest derivation)
def knapsack_2d(weights: list[int], values: list[int], W: int) -> int:
    n = len(weights)
    dp = [[0] * (W + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wt, val = weights[i - 1], values[i - 1]
        for w in range(W + 1):
            dp[i][w] = dp[i - 1][w]
            if wt <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - wt] + val)
    return dp[n][W]

# Space-optimized 1D — MUST iterate capacity backward (0/1 semantics)
def knapsack_1d(weights: list[int], values: list[int], W: int) -> int:
    dp = [0] * (W + 1)
    for wt, val in zip(weights, values):
        for w in range(W, wt - 1, -1):        # backward: high to low
            dp[w] = max(dp[w], dp[w - wt] + val)
    return dp[W]

# Partition Equal Subset Sum (LC 416) — boolean subset-sum knapsack
def can_partition(nums: list[int]) -> bool:
    total = sum(nums)
    if total % 2:
        return False
    target = total // 2
    dp = [False] * (target + 1)
    dp[0] = True
    for n in nums:
        for w in range(target, n - 1, -1):    # backward: each num used once
            dp[w] = dp[w] or dp[w - n]
    return dp[target]

# Target Sum (LC 494) — reduces to subset sum: let P = positive subset,
# P - (sum-P) = target  =>  P = (sum+target)/2, then count subsets summing to P.
def find_target_sum_ways(nums: list[int], target: int) -> int:
    total = sum(nums)
    if (total + target) % 2 != 0 or total < abs(target):
        return 0
    P = (total + target) // 2
    dp = [0] * (P + 1)
    dp[0] = 1
    for n in nums:
        for w in range(P, n - 1, -1):
            dp[w] += dp[w - n]
    return dp[P]
```

```java
// Java — 0/1 Knapsack: space-optimized 1D
public int knapsack(int[] weights, int[] values, int W) {
    int[] dp = new int[W + 1];
    for (int i = 0; i < weights.length; i++) {
        int wt = weights[i], val = values[i];
        for (int w = W; w >= wt; w--) {              // backward
            dp[w] = Math.max(dp[w], dp[w - wt] + val);
        }
    }
    return dp[W];
}

// Partition Equal Subset Sum (LC 416)
public boolean canPartition(int[] nums) {
    int total = 0;
    for (int n : nums) total += n;
    if (total % 2 != 0) return false;
    int target = total / 2;
    boolean[] dp = new boolean[target + 1];
    dp[0] = true;
    for (int n : nums) {
        for (int w = target; w >= n; w--) {
            dp[w] = dp[w] || dp[w - n];
        }
    }
    return dp[target];
}
```

```go
// Go — 0/1 Knapsack: space-optimized 1D
func knapsack(weights, values []int, W int) int {
    dp := make([]int, W+1)
    for i := range weights {
        wt, val := weights[i], values[i]
        for w := W; w >= wt; w-- { // backward
            if dp[w-wt]+val > dp[w] {
                dp[w] = dp[w-wt] + val
            }
        }
    }
    return dp[W]
}

// Partition Equal Subset Sum (LC 416)
func canPartition(nums []int) bool {
    total := 0
    for _, n := range nums {
        total += n
    }
    if total%2 != 0 {
        return false
    }
    target := total / 2
    dp := make([]bool, target+1)
    dp[0] = true
    for _, n := range nums {
        for w := target; w >= n; w-- {
            dp[w] = dp[w] || dp[w-n]
        }
    }
    return dp[target]
}
```

## Complexity, derived

The 2D table has `(n+1)*(W+1)` cells, each computed in O(1), so **time is O(n·W)** for every variant above (subset sum, target sum, count-subsets all reuse the identical shape). **2D space is O(n·W)**; the backward-iteration 1D collapse drops that to **O(W)** since only one row is ever live. This is **pseudo-polynomial**: the runtime is polynomial in the numeric value of `W`, not in `log W` (its bit-length) — encode `W` in binary and the same problem instance takes exponentially longer to solve exactly as `W` grows, which is exactly why the decision problem remains NP-complete despite this "efficient-looking" DP. Reconstruction of the actual chosen subset (not just the optimal value) requires walking back through a full 2D table or recomputing rows, since the 1D form has discarded the per-item history — an O(n·W) time, O(n·W) space bookkeeping cost you only pay if the problem asks for the subset itself, not just its value.

---

## The 5 variants interviewers actually ask

1. **Classic 0/1 Knapsack (max value under weight capacity).** Direct template application: `dp[w] = max(dp[w], dp[w-wt]+val)`, backward capacity loop.
2. **Partition Equal Subset Sum (LC 416).** Boolean subset-sum against `target = total/2`; recognizing that "partition into two equal-sum subsets" *is* subset sum is the actual test.
3. **Target Sum (LC 494).** Algebraic reduction: assigning `+`/`-` to reach a target reduces to counting subsets summing to `(total+target)/2`; the reduction itself, not the DP, is what separates candidates.
4. **Last Stone Weight II / minimum subset-sum difference (LC 1049).** Maximize the achievable subset sum `s <= total/2`; the answer is `total - 2*s`. Tests whether you can go from "can I reach exactly X" to "what's the closest I can get to X."
5. **Ones and Zeroes (LC 474), 2D 0/1 knapsack.** Two independent capacity axes (`m` zeros, `n` ones budget) instead of one; the recurrence and the backward-iteration argument both generalize per axis — `dp[w0][w1] = max(dp[w0][w1], dp[w0-c0][w1-c1] + 1)`, iterate both axes backward.

---

## Common bugs

- **Forward capacity iteration in the 1D form.** Silently converts 0/1 knapsack into unbounded knapsack — the single most common mistake, and the one interviewers probe for directly by asking "what if you looped the other way?"
- **Off-by-one on the capacity array size.** The array must be `W+1` long (indices `0..W` inclusive); sizing it `W` and indexing `dp[W]` overflows.
- **Mixing boolean and numeric base cases.** Subset-sum variants need `dp[0] = True`/`1` as the identity, not `dp[0] = 0`, which is correct for max-value knapsack but wrong for reachability/counting.
- **Getting the loop nesting backwards for the wrong reason.** Items must be the outer loop and capacity the inner loop for 0/1 knapsack's backward trick to be meaningful per item; swapping them (capacity outer, items inner) breaks the "one item, one full backward sweep" invariant the correctness argument depends on.
- **Overflowing counts in "count the subsets" variants** without checking whether the interviewer wants modulo arithmetic — real constraints (LC uses `10^9+7`) matter if the count can be astronomically large.
- **Forgetting the reduction step in Target Sum.** Running DP directly on positive/negative deltas instead of reducing to subset sum first leads to a much messier (and usually wrong under time pressure) state definition.

---

## Interview questions

### Q1 — Classic 0/1 Knapsack: maximize value under a weight capacity, each item once.
**Testing:** whether you can derive the recurrence from the include/exclude choice rather than reciting it.
**Answer:** `dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]]+val[i])` if it fits, else `dp[i-1][w]`. O(n·W) time and space; collapses to O(W) space.
**Follow-up trap:** *"Collapse it to 1D. Which direction do you iterate capacity, and why?"* — backward, high to low; forward lets an item feed into its own already-updated cell, turning it into unbounded knapsack.

### Q2 — Why does iterating capacity forward in the 1D array break 0/1 semantics?
**Testing:** the mechanical understanding behind the space optimization, not just the rule.
**Answer:** Forward iteration means `dp[w-wt]` may already have been overwritten earlier in the same item's pass with a value that already includes this item, so `dp[w] = max(dp[w], dp[w-wt]+val)` lets the item contribute twice.
**Follow-up trap:** *"So how does unbounded knapsack use this exact bug on purpose?"* — unbounded knapsack wants unlimited reuse of the same item, so it deliberately iterates forward; see `T02-p16-knapsack-unbounded`.

### Q3 — Partition Equal Subset Sum (LC 416): can an array be split into two subsets with equal sum?
**Testing:** recognizing a disguised subset-sum problem.
**Answer:** If total is odd, impossible. Otherwise, boolean subset-sum DP against `target = total/2`; backward capacity loop, one pass per number.
**Follow-up trap:** *"What if you need the actual two subsets, not just yes/no?"* — you need to retain enough table history (2D, or track parent choices) to backtrack a valid combination; the 1D boolean form alone can't reconstruct it.

### Q4 — Target Sum (LC 494): count ways to assign +/- to reach a target.
**Testing:** whether you can algebraically reduce a signed-assignment problem to subset sum.
**Answer:** Let `P` be the positive-sign subset sum; `P - (total-P) = target` gives `P = (total+target)/2`. Count subsets summing to `P` via the standard count-variant DP (`dp[w] += dp[w-n]`).
**Follow-up trap:** *"What if `(total+target)` is odd, or `abs(target) > total`?"* — both mean zero valid assignments; check and early-return before running the DP.

### Q5 — Last Stone Weight II (LC 1049): minimize the difference between two partitions.
**Testing:** going from "reachability" to "closest achievable value."
**Answer:** Maximize `s <= total/2` reachable via subset-sum DP; answer is `total - 2*s` since the other partition is `total - s` and the difference is minimized when `s` is as close to `total/2` as possible.
**Follow-up trap:** *"Why does maximizing s toward total/2 minimize the difference, formally?"* — difference is `|total - 2s|`; since `s <= total/2` by construction, this simplifies to `total - 2s`, which decreases monotonically as `s` increases, so the largest reachable `s` gives the minimum difference.

### Q6 — Ones and Zeroes (LC 474): pick the max number of strings using at most `m` zeros and `n` ones total.
**Testing:** generalizing the single-capacity recurrence to two independent budgets.
**Answer:** `dp[i][j] = max(dp[i][j], dp[i-cost0][j-cost1]+1)` for each string's (zeros, ones) cost; 2D capacity array, both axes iterated backward per string.
**Follow-up trap:** *"What's the time complexity now?"* — O(strings · m · n); each string does O(m·n) work, still pseudo-polynomial in both capacity dimensions.

### Q7 — Reconstruct which items were actually chosen, not just the optimal value.
**Testing:** whether you understand that 1D space optimization is lossy for anything beyond the final number.
**Answer:** Keep the full 2D table (or store a separate "chosen" boolean/parent table), then walk backward from `dp[n][W]`: if `dp[i][w] != dp[i-1][w]`, item `i` was taken — move to `dp[i-1][w-wt[i]]`; otherwise move to `dp[i-1][w]`.
**Follow-up trap:** *"Can you do this with O(W) space instead of O(n·W)?"* — only with extra engineering (e.g., Hirschberg-style divide-and-conquer reconstruction, or storing per-item bitsets); plainly say the naive 1D form has thrown away what's needed and there's a real space/reconstruction tradeoff.

### Q8 — What if item values or weights can be negative?
**Testing:** whether you blindly apply the template or check its assumptions.
**Answer:** Negative weights break the "capacity only shrinks" assumption the DP table indexing relies on; negative values break the max-based pruning assumption in some variants. Real problems rarely allow this without restating constraints; flag it rather than silently forcing the template.
**Follow-up trap:** *"What would you actually do if weights could be negative?"* — reframe: if it's really "weights >= 0, values can be negative," the DP still works since you're maximizing over the same reachable-capacity space; if weights can be negative, the state space (capacity) is no longer monotonic and you likely need a different formulation (e.g., shift/offset indexing or a graph-shortest-path reframing).

### Q9 — Why is 0/1 knapsack NP-complete but this DP looks like it solves it efficiently?
**Testing:** the pseudo-polynomial distinction, a real senior-level gotcha.
**Answer:** O(n·W) is polynomial in the *value* of W, not in the number of bits used to encode W (`log W`). For W represented in binary, the runtime is exponential in the input's actual encoded size once W is large, which is consistent with NP-completeness.
**Follow-up trap:** *"Given W = 10^9, is this DP usable?"* — no; O(n·10^9) is impractical regardless of n. Switch to greedy fractional relaxation, meet-in-the-middle for small n, or an ILP solver (OR-Tools/CBC) for an exact-enough answer at that scale.

### Q10 — Bounded knapsack: each item has a limited count `c[i]` (not 1, not infinite).
**Testing:** whether you can extend the pattern rather than treat it as a brand-new problem.
**Answer:** Binary/power-of-two decomposition — split each item of count `c` into `O(log c)` "meta-items" of sizes `1, 2, 4, ..., c - (2^k - 1)`, each usable once, then run plain 0/1 knapsack over the expanded item list. Time becomes O(n·W·log(max c)) instead of the naive O(n·W·max c).
**Follow-up trap:** *"Why does the power-of-two split still let you represent every count from 0 to c?"* — because binary representation lets any integer up to `2^k - 1` be built from powers of two up to `2^(k-1)`, and the remainder term closes the gap up to exactly `c`; it's the same trick as binary lifting / sparse tables.

### Q11 — Count the number of distinct subsets that sum to a target (not just whether one exists).
**Testing:** the max/OR → sum transition at the recurrence level.
**Answer:** Same shape, different combine operator: `dp[w] += dp[w-n]` instead of `max`/`or`; base case `dp[0] = 1`. Backward capacity loop is still required to keep each number used at most once.
**Follow-up trap:** *"What if duplicate numbers should only be counted as one subset, not per-occurrence?"* — that changes the problem to counting *distinct value combinations*, which typically needs sorting + skipping duplicate values at the same recursion depth (closer to the subsets/combinatorics pattern, `T02-p10-subsets`) rather than plain knapsack counting.

### Q12 — Would you use this DP in a real resource-allocation system with a large budget?
**Testing:** production judgment, not just correctness.
**Answer:** Only if the capacity is genuinely small/bounded (say, low thousands); otherwise no — use LP relaxation with a rounding scheme, or an ILP solver (OR-Tools, CBC, Gurobi) which handles multi-dimensional constraints and scales far better in practice than a hand-rolled pseudo-polynomial DP.
**Follow-up trap:** *"What do you lose by switching to LP relaxation?"* — exactness; fractional relaxation can overshoot the true integer optimum, so you need a rounding/greedy repair step and to accept a bounded approximation ratio instead of an exact answer.

---

## Red flags that fail you

- Iterating the 1D capacity loop forward and not noticing (or not being able to explain) why that's wrong.
- Reciting "backward iteration" as a rule without being able to derive *why* forward breaks it.
- Not recognizing subset sum, partition, and target sum as the same table with a different combine operator.
- Claiming this DP "solves an NP-complete problem in polynomial time" without the pseudo-polynomial caveat.
- Reaching for full O(n·W) 2D reconstruction machinery when only the optimal *value* was asked for.
- Suggesting this DP as-is for a real system with a capacity in the billions.

---

## Cheat card

```
STATE          dp[i][w] = best value using first i items, capacity w
RECURRENCE     dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt]+val)  if wt<=w, else dp[i-1][w]
2D COST        O(n*W) time, O(n*W) space
1D COLLAPSE    keep one row; iterate capacity BACKWARD (W -> wt) per item
WHY BACKWARD   forward lets dp[w-wt] already include this item -> double use -> becomes unbounded knapsack
SUBSET SUM     boolean variant: dp[w] = dp[w] or dp[w-n]; dp[0]=True         (LC 416)
TARGET SUM     reduce to subset sum: P=(total+target)/2, count subsets = P  (LC 494)
MIN DIFF       maximize s<=total/2 reachable; answer = total-2s             (LC 1049)
2 BUDGETS      Ones and Zeroes: dp[i][j], both axes backward                (LC 474)
BOUNDED COUNT  binary/power-of-two split into O(log c) 0/1 meta-items
COMPLEXITY     pseudo-polynomial: O(n*W) poly in VALUE of W, not in log W (bits) -> NP-complete stands
RECONSTRUCT    needs full 2D table or parent pointers; 1D form can't recover chosen items
AT SCALE       large W -> LP relaxation / ILP solver (OR-Tools), not exact DP
```

## Sources

- [Partition Equal Subset Sum — LeetCode](https://leetcode.com/problems/partition-equal-subset-sum/) — accessed 2026-07-26
- [Target Sum — LeetCode](https://leetcode.com/problems/target-sum/) — accessed 2026-07-26
- [Last Stone Weight II — LeetCode](https://leetcode.com/problems/last-stone-weight-ii/) — accessed 2026-07-26
- [Ones and Zeroes — LeetCode](https://leetcode.com/problems/ones-and-zeroes/) — accessed 2026-07-26
- [Knapsack problem — Wikipedia](https://en.wikipedia.org/wiki/Knapsack_problem) — accessed 2026-07-26
- [Pseudo-polynomial time — Wikipedia](https://en.wikipedia.org/wiki/Pseudo-polynomial_time) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
