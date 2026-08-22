# Pattern: Unbounded Knapsack DP

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** arrays, T02-p15-knapsack-01
> **Module id:** `T02-p16-knapsack-unbounded` · **Tags:** pattern, dp
> **Lab:** `labs/py/16-knapsack-unbounded/`

## The 30-second version

Unbounded knapsack is 0/1 knapsack's twin for "each item can be used any number of times" — coin change, rod cutting, and combination-sum-with-repetition all share one recurrence: `dp[w] = max(dp[w], dp[w-wt[i]] + val[i])`, and the only mechanical difference from 0/1 knapsack is that the 1D capacity loop iterates **forward** (low to high) instead of backward. Forward iteration lets `dp[w-wt[i]]` already reflect an update made earlier in the *same* item's pass, which is exactly what you want here — it lets the same item feed into itself arbitrarily many times within one sweep, which is unlimited reuse by construction, not a bug. That single direction flip, and being able to say precisely why it flips, is the entire interview. Recognize it whenever a problem says "unlimited supply," "as many times as needed," or gives you a fixed set of denominations/lengths/pieces you can reuse freely against a target.

## Why this gets asked

It's the natural follow-up to 0/1 knapsack and tests whether the candidate actually derived the backward-iteration argument there or just memorized "iterate backward for knapsack" as a blanket rule. Interviewers who've built billing/pricing engines (making change, SKU-bundling with unlimited stock), or capacity planners that repeatedly draw from a renewable resource pool (autoscaling instance types, repeatable batch job templates), have hit the real version of this: treating a resource as reusable when it should have been scarce, or vice versa, produces answers that are either impossible to fulfill or double-counted. It also checks whether you can hold two closely related recurrences in your head at once without conflating them under pressure.

---

## Lineage: past → present → future

**What came before.** The classical motivating case is the **coin change / making change problem** and **rod cutting**, both catalogued in Cormen/Leiserson/Rivest/Stein's *Introduction to Algorithms* as canonical DP examples, tracing back to the same Bellman-era (1950s) resource-allocation DP formalization as 0/1 knapsack. Before DP, the only options were brute-force recursive enumeration of every combination of denominations/cuts (exponential, since each position has "reuse this item again" as an extra branch on top of 0/1's binary choice) or greedy (works only for canonical coin systems like US currency, provably fails for arbitrary denominations — e.g., greedy fails for coins `{1, 3, 4}` and target `6`, giving 4+1+1 instead of the optimal 3+3).

**Where it stands now.** Settled, closed math, same status as 0/1 knapsack. The one place people still get tripped up in interviews is exactly the forward/backward direction question, and a smaller but real trap: whether the problem wants the **minimum number of items** (coin change minimum coins, LC 322), the **number of distinct combinations** (Coin Change II, LC 518), or the **number of distinct permutations/orderings** (Combination Sum IV, LC 377) — these look identical at the recurrence level but require swapping which loop is outer (items vs capacity) to get combinations versus permutations right, which is a second, subtler direction question layered on top of the first.

**Where it's heading.** No change expected for interviews. In production, unbounded-resource allocation at scale (bin-packing with unlimited SKU stock, cutting-stock optimization in manufacturing) is handled the same way as bounded knapsack at scale: column-generation / LP relaxation for the cutting-stock problem (the classical Gilmore-Gomory approach from the 1960s) rather than a hand-rolled DP once item/target sizes get large. Knowing that the DP is a small-scale exact tool and column generation is the production-scale answer is the senior signal here too.

---

## Mental model

Same table shape as 0/1 knapsack, but now each row lets an item "restock" itself as many times as capacity allows.

```
coin denominations: 1, 3, 4          target = 6

0/1 knapsack intuition: each coin usable once -> can't reach 6 with just one of each unless sum allows.
Unbounded: coin 3 can be used twice (3+3=6) -> this is the whole point of allowing reuse.

dp[w] = min coins to make w:
  w:    0  1  2  3  4  5  6
  dp:   0  1  2  1  1  2  2    <- dp[6]=2 via 3+3, not dp[6]=3 via 1+1+4-ish forcing more coins
```

The mechanical picture: in the 1D array, when you're filling in `dp[6]` using coin `3`, you want `dp[3]` to already reflect "coin 3 was used to build this," so that adding another `3` on top is legal. That "already reflects an update from *this* item" is precisely what backward iteration prevents and forward iteration allows.

---

## Recognition heuristics

- **"Unlimited supply," "as many times as you like," "any number of coins/pieces."** The most direct tell.
- **Coin change framing** — minimum coins to make a target, or number of ways to make a target from denominations you can reuse.
- **Rod cutting / cutting stock** — a rod of length `n`, prices per cut length, cut into any number of pieces of any allowed lengths to maximize total price.
- **Combination Sum (LC 39, LC 377)** — "numbers may be reused unlimited times" is stated explicitly in the prompt.
- **Perfect Squares (LC 279)** — "unlimited" is implicit: every perfect square number is available as many times as needed to sum to `n`.
- **A qualifier distinguishing "combinations" vs "permutations"** — if order matters (1+3 and 3+1 count separately), that's a nested-loop-order question layered on top of the reuse question; if order doesn't matter, items are the outer loop.

If instead the problem caps how many times each item can be used to some finite count greater than one, that's **bounded knapsack** — a middle case handled by binary/power-of-two item decomposition into a 0/1 problem (see `T02-p15-knapsack-01`, Q10), not plain unbounded knapsack.

---

## How it actually works — deriving the recurrence and the forward-iteration argument

**The recurrence.** Unbounded knapsack's 2D form looks almost identical to 0/1 knapsack's, with one crucial change: taking item `i` reaches back into **the same row `i`**, not row `i-1`, because item `i` remains available after being used:

```
dp[i][w] = dp[i-1][w]                                    if wt[i] > w
dp[i][w] = max(dp[i-1][w], dp[i][w-wt[i]] + val[i])       if wt[i] <= w   <- note: dp[i], not dp[i-1]
```

That single index change (`dp[i][w-wt[i]]` instead of `dp[i-1][w-wt[i]]`) is the entire mathematical difference from 0/1 knapsack. It says: "after committing capacity `wt[i]` to one copy of item `i`, you're still allowed to use item `i` again in the remaining capacity" — which is exactly unlimited reuse.

**Collapsing to 1D — why forward now.** In 0/1 knapsack, we argued backward iteration was necessary specifically so `dp[w-wt[i]]` would *not* yet include this item's contribution. Here, we want the opposite: `dp[w-wt[i]]` reading a value that *already* includes item `i` is exactly correct, since the 2D recurrence explicitly reads from row `i`, not row `i-1`. Iterating capacity **forward** (low to high) on a single 1D array naturally produces this: by the time you compute `dp[w]`, `dp[w-wt[i]]` (a smaller index processed earlier in this same pass) may already have been updated with item `i`'s contribution — and that's desired, not a bug.

```
1D update per item (unbounded, must go forward):
for w in range(wt[i], W + 1):
    dp[w] = max(dp[w], dp[w - wt[i]] + val[i])
```

This is the mirror image of 0/1 knapsack's backward rule, and the two rules are provably necessary-and-sufficient for their respective semantics — there is no third option that gives you "reuse up to k times" without either decomposing the item (bounded knapsack) or adding an explicit count dimension to the state.

**Combinations vs permutations — the second direction question.** For "number of ways to make target using unlimited coins," loop order determines what you're counting:
- **Items outer, capacity inner** → counts each **combination** once regardless of order (1+3 and 3+1 are the same way). This is Coin Change II (LC 518).
- **Capacity outer, items inner** → counts each **ordered sequence** as distinct (1+3 and 3+1 counted separately). This is Combination Sum IV (LC 377), despite its name — it's really "permutations that sum to target."

This is easy to get backward under pressure because both loops "look the same" superficially; the only way to get it right on demand is to trace through a 2-coin example by hand and see which loop order double-counts orderings.

---

## Template code (Python, Java, Go)

```python
# Python — Unbounded Knapsack: max value, unlimited reuse per item
def unbounded_knapsack(weights: list[int], values: list[int], W: int) -> int:
    dp = [0] * (W + 1)
    for wt, val in zip(weights, values):
        for w in range(wt, W + 1):            # forward: low to high
            dp[w] = max(dp[w], dp[w - wt] + val)
    return dp[W]

# Coin Change (LC 322) — minimum coins to make amount; unlimited supply
def coin_change(coins: list[int], amount: int) -> int:
    INF = float("inf")
    dp = [0] + [INF] * amount
    for coin in coins:
        for w in range(coin, amount + 1):      # forward
            dp[w] = min(dp[w], dp[w - coin] + 1)
    return dp[amount] if dp[amount] != INF else -1

# Coin Change II (LC 518) — number of COMBINATIONS (order doesn't matter)
def change(amount: int, coins: list[int]) -> int:
    dp = [1] + [0] * amount
    for coin in coins:                          # coins OUTER -> combinations
        for w in range(coin, amount + 1):
            dp[w] += dp[w - coin]
    return dp[amount]

# Combination Sum IV (LC 377) — number of PERMUTATIONS (order matters)
def combination_sum4(nums: list[int], target: int) -> int:
    dp = [1] + [0] * target
    for w in range(1, target + 1):               # capacity OUTER -> permutations
        for n in nums:
            if n <= w:
                dp[w] += dp[w - n]
    return dp[target]
```

```java
// Java — Unbounded Knapsack
public int unboundedKnapsack(int[] weights, int[] values, int W) {
    int[] dp = new int[W + 1];
    for (int i = 0; i < weights.length; i++) {
        int wt = weights[i], val = values[i];
        for (int w = wt; w <= W; w++) {          // forward
            dp[w] = Math.max(dp[w], dp[w - wt] + val);
        }
    }
    return dp[W];
}

// Coin Change (LC 322)
public int coinChange(int[] coins, int amount) {
    int[] dp = new int[amount + 1];
    Arrays.fill(dp, Integer.MAX_VALUE - 1);
    dp[0] = 0;
    for (int coin : coins) {
        for (int w = coin; w <= amount; w++) {
            dp[w] = Math.min(dp[w], dp[w - coin] + 1);
        }
    }
    return dp[amount] >= Integer.MAX_VALUE - 1 ? -1 : dp[amount];
}

// Coin Change II (LC 518) — combinations
public int change(int amount, int[] coins) {
    int[] dp = new int[amount + 1];
    dp[0] = 1;
    for (int coin : coins) {                      // coins outer
        for (int w = coin; w <= amount; w++) {
            dp[w] += dp[w - coin];
        }
    }
    return dp[amount];
}
```

```go
// Go — Unbounded Knapsack
func unboundedKnapsack(weights, values []int, W int) int {
    dp := make([]int, W+1)
    for i := range weights {
        wt, val := weights[i], values[i]
        for w := wt; w <= W; w++ { // forward
            if dp[w-wt]+val > dp[w] {
                dp[w] = dp[w-wt] + val
            }
        }
    }
    return dp[W]
}

// Coin Change (LC 322)
func coinChange(coins []int, amount int) int {
    const inf = 1 << 30
    dp := make([]int, amount+1)
    for w := 1; w <= amount; w++ {
        dp[w] = inf
    }
    for _, coin := range coins {
        for w := coin; w <= amount; w++ {
            if dp[w-coin]+1 < dp[w] {
                dp[w] = dp[w-coin] + 1
            }
        }
    }
    if dp[amount] == inf {
        return -1
    }
    return dp[amount]
}

// Coin Change II (LC 518) — combinations
func change(amount int, coins []int) int {
    dp := make([]int, amount+1)
    dp[0] = 1
    for _, coin := range coins { // coins outer
        for w := coin; w <= amount; w++ {
            dp[w] += dp[w-coin]
        }
    }
    return dp[amount]
}
```

## Complexity, derived

Every variant walks an `(items) x (capacity)` grid once, each cell O(1) work, so **time is O(n·W)** just like 0/1 knapsack — the forward/backward direction change doesn't affect asymptotic complexity, only correctness. **Space is O(W)** with the 1D array, same as 0/1 knapsack's optimized form; the 2D table (O(n·W)) is never actually necessary for unbounded knapsack in practice, unlike 0/1 knapsack where reconstruction sometimes forces you back to 2D — because unbounded knapsack's recurrence deliberately allows same-row self-reference, the 1D forward form *is* the natural formulation, not an optimization bolted on afterward. Same pseudo-polynomial caveat as 0/1 knapsack applies: O(n·W) is polynomial in the numeric value of the target/capacity, not its bit-length, so a target like `10^9` still makes this approach impractical.

---

## The 5 variants interviewers actually ask

1. **Coin Change (LC 322) — minimum number of coins to make an amount.** Template: `dp[w] = min(dp[w], dp[w-coin]+1)`, forward capacity loop, `dp[0]=0`, rest initialized to infinity.
2. **Coin Change II (LC 518) — number of combinations to make an amount.** Template: `dp[w] += dp[w-coin]`, coins as the **outer** loop to avoid counting orderings separately.
3. **Combination Sum IV (LC 377) — number of ordered sequences (permutations) summing to target.** Same recurrence, but capacity as the **outer** loop and items inner, which double-counts different orders of the same multiset on purpose.
4. **Perfect Squares (LC 279) — minimum number of perfect squares summing to n.** Items are implicit: every `k^2 <= n`; otherwise identical to Coin Change's minimum-count template.
5. **Rod Cutting (classic, not on LC directly) — maximize total value cutting a rod of length n into pieces of any allowed lengths, each length reusable without limit.** Direct application of the max-value unbounded knapsack template with rod segment lengths as "weights" and their prices as "values."

---

## Common bugs

- **Iterating capacity backward out of habit from 0/1 knapsack.** This silently caps each coin/item at effectively one use per capacity level in ways that produce wrong (usually too-large) minimum-coin counts or undercounted combination totals — the mirror image of 0/1 knapsack's forward-iteration bug.
- **Swapping combinations and permutations by getting the outer/inner loop order backward.** Produces a count that's either too small (missing valid orderings) or too large (double-counting the same multiset in every order) depending on which direction you got wrong.
- **Not initializing the "impossible" sentinel correctly in minimum-coin variants.** Using `0` instead of infinity for unreached capacities makes `min(dp[w], ...)` silently accept an invalid 0-coin solution for nonzero amounts.
- **Greedy substitution.** Assuming the largest denomination first always gives the optimal minimum-coin count; this is false for non-canonical coin systems (e.g., `{1,3,4}` targeting `6`: greedy gives 4+1+1=3 coins, optimal is 3+3=2 coins). Only proven-canonical systems (like most real currencies) let greedy substitute for DP, and you should not assume that without being told.
- **Confusing bounded and unbounded knapsack.** Applying the unlimited-reuse forward-iteration template to a problem where each item actually has a finite cap silently overcounts; bounded knapsack needs power-of-two item decomposition into a 0/1 subproblem instead.

---

## Interview questions

### Q1 — Coin Change (LC 322): fewest coins to make an amount, unlimited supply of each denomination.
**Testing:** the base unbounded-reuse recurrence and forward iteration.
**Answer:** `dp[w] = min(dp[w], dp[w-coin]+1)` for each coin, capacity iterated forward from `coin` to `amount`; `dp[0]=0`, rest initialized to infinity, return `-1` if unreached.
**Follow-up trap:** *"Why forward here when 0/1 knapsack needed backward?"* — forward lets `dp[w-coin]` already reflect this coin's use earlier in the same pass, which is exactly the unlimited-reuse behavior wanted; backward would prevent that reuse.

### Q2 — Prove that greedy (always take the largest coin that fits) fails for Coin Change in general.
**Testing:** whether you can produce a concrete counterexample instead of asserting DP is "just safer."
**Answer:** Coins `{1,3,4}`, target `6`: greedy takes 4, then 1, then 1 → 3 coins. Optimal is 3+3 → 2 coins. Greedy only works for canonical coin systems (proven for US currency); DP handles arbitrary denominations correctly.
**Follow-up trap:** *"How would you prove a given coin system IS canonical, so greedy is safe?"* — this requires a case analysis / exhaustive check specific to the denomination set (there's a known algorithmic test for canonicity but no simple closed-form check); the practical answer in an interview is "I wouldn't assume it without verification — I'd default to DP."

### Q3 — Coin Change II (LC 518): count the number of distinct combinations that make an amount.
**Testing:** the combinations-vs-permutations loop-order distinction.
**Answer:** `dp[w] += dp[w-coin]`, coins as the **outer** loop, capacity inner; `dp[0]=1`. Outer-coins ensures each combination (unordered multiset) is counted exactly once.
**Follow-up trap:** *"What happens if you swap the loop order?"* — you get Combination Sum IV instead: the same recurrence now counts ordered sequences, over-counting combinations that can be arranged in multiple orders.

### Q4 — Combination Sum IV (LC 377): count ordered sequences summing to target, unlimited reuse.
**Testing:** recognizing that "combination" in the problem name is misleading; it's actually permutations.
**Answer:** `dp[w] += dp[w-n]` for every number at every capacity, capacity as the **outer** loop, items inner; this deliberately lets `1+3` and `3+1` count as two different sequences.
**Follow-up trap:** *"Rewrite this to count unordered combinations instead."* — swap the loop nesting to items-outer, capacity-inner (Coin Change II's structure); verify by hand-tracing a 2-item example that reordering no longer produces a second count.

### Q5 — Perfect Squares (LC 279): minimum number of perfect squares summing to n.
**Testing:** whether you can generate the "item list" implicitly rather than needing it handed to you.
**Answer:** Items are every `k^2 <= n`; run the Coin-Change-style minimum-count template over that implicit list. O(n·sqrt(n)) since there are `sqrt(n)` perfect squares up to `n`.
**Follow-up trap:** *"Can you do better than DP here?"* — yes: Lagrange's four-square theorem guarantees every natural number is a sum of at most 4 perfect squares, and there's a direct O(sqrt(n)) check for whether 1, 2, 3, or 4 squares suffice using number-theoretic conditions (Legendre's three-square theorem) — DP is the general-purpose answer, but for this *specific* problem there's a closed-form shortcut worth naming.

### Q6 — Rod Cutting: given a rod of length n and prices per cut length, maximize total value from any set of cuts.
**Testing:** applying the max-value unbounded template outside the coin-change framing.
**Answer:** Treat cut lengths as "weights" and their prices as "values" in the unbounded max-value template: `dp[w] = max(dp[w], dp[w-len]+price)`, forward capacity iteration, `dp[0]=0`.
**Follow-up trap:** *"What if cutting itself costs something (a fixed cost per cut)?"* — subtract the cut cost from each transition's contribution; this changes the per-step gain but not the overall DP shape or the forward-iteration argument.

### Q7 — Bounded variant: each coin/item can only be used up to k times, not unlimited. How does the DP change?
**Testing:** whether unbounded and 0/1 knapsack can be composed to handle the in-between case.
**Answer:** This is bounded knapsack: decompose each item into `O(log k)` power-of-two meta-items (see `T02-p15-knapsack-01` Q10) and run 0/1 knapsack (backward iteration) on the expanded list — do not use the plain unbounded forward-iteration template, which would allow more than k uses.
**Follow-up trap:** *"What if k is different per item?"* — decompose each item independently using its own `k`; the resulting meta-item list is just longer, complexity becomes O(n·W·log(max k)).

### Q8 — What's the complexity difference between the naive recursive solution and the DP, for Coin Change?
**Testing:** whether you can quantify the actual speedup, not just say "DP is faster."
**Answer:** Naive recursion without memoization branches on every coin at every remaining amount, giving exponential time in the worst case (roughly `O(coins^amount)` without pruning); the DP is O(coins · amount), a reduction from exponential to pseudo-polynomial.
**Follow-up trap:** *"Is O(coins*amount) always fast enough?"* — no; if `amount` is very large (say 10^9), this is still impractical despite being "polynomial" — same pseudo-polynomial caveat as 0/1 knapsack.

### Q9 — How would you modify Coin Change to also return one valid set of coins achieving the minimum, not just the count?
**Testing:** reconstruction on top of the 1D optimized table.
**Answer:** Track a parallel `choice[w]` array recording which coin achieved the minimum at each `w` during the forward pass; walk backward from `amount` using `choice` to list the coins used.
**Follow-up trap:** *"Does this reconstruction still work with the 1D forward-iteration table, unlike 0/1 knapsack's reconstruction problem?"* — yes, because unbounded knapsack's 1D table already represents the "final" state per capacity as computed (no information about item multiplicity is lost the way 0/1's per-item history is), so a single parallel choice array suffices without needing the full 2D table.

### Q10 — Combination Sum (LC 39): return all actual combinations (not just a count) summing to a target, unlimited reuse per number.
**Testing:** recognizing when the ask shifts from "count/optimize" (DP) to "enumerate" (backtracking).
**Answer:** This isn't a DP counting problem anymore — it wants the actual combinations, so switch to backtracking: choose a number, recurse with the remaining target (allowing the same index again since reuse is unlimited), backtrack, and prune when the remaining target goes negative.
**Follow-up trap:** *"Why not adapt the DP table to store all combinations directly?"* — storing every combination in a DP table is exponential in the output size itself (there can be exponentially many combinations), defeating the point of DP's polynomial state space; DP is for counting or optimizing, not for enumerating when the enumeration itself is combinatorially large.

### Q11 — Would coin change at real-world payment-processing scale (e.g., register change-making with a huge inventory of denominations, high transaction volume) actually run this DP per transaction?
**Testing:** production judgment about when the classic DP is the wrong tool.
**Answer:** For a small, fixed, canonical currency system, real registers use precomputed greedy tables (safe because standard currency denominations are provably canonical), not per-transaction DP; DP earns its keep only for arbitrary/non-canonical denomination sets or when correctness for non-canonical systems must be guaranteed exactly.
**Follow-up trap:** *"What if the denomination set changes dynamically (e.g., loyalty-point 'coins' added/removed)?"* — re-verify canonicity or fall back to DP whenever the set isn't provably canonical; caching/memoizing per denomination-set-and-amount pair is a reasonable production optimization if amounts repeat often.

---

## Red flags that fail you

- Iterating the capacity loop backward for unbounded knapsack (0/1 knapsack habit bleeding over) and not being able to explain why that's wrong here.
- Confusing combinations and permutations, or not knowing which loop order produces which.
- Asserting greedy always finds the minimum number of coins, without a counterexample check.
- Applying the plain unbounded template to a problem where items actually have a finite cap.
- Reaching for a DP table to enumerate all combinations instead of switching to backtracking when the ask is "list them," not "count/optimize."

---

## Cheat card

```
STATE          dp[w] = best value/count/min-count reachable at capacity w, items reusable
RECURRENCE     dp[w] = max/min/sum(dp[w], dp[w-wt]+val)   (same-row self reference vs 0/1's prior row)
1D DIRECTION   FORWARD (wt -> W). Lets dp[w-wt] already include this item -> intended reuse.
CONTRAST 0/1   0/1 needs BACKWARD to prevent reuse; unbounded needs FORWARD to allow it.
MIN COINS      dp[w]=min(dp[w], dp[w-coin]+1); dp[0]=0, rest=inf                  (LC 322)
COMBINATIONS   dp[w]+=dp[w-coin]; COINS OUTER loop, capacity inner                (LC 518)
PERMUTATIONS   dp[w]+=dp[w-n];     CAPACITY OUTER loop, items inner               (LC 377)
PERFECT SQR    implicit item list = every k^2<=n; else same as min-coins template (LC 279)
GREEDY TRAP    fails for non-canonical coin sets, e.g. {1,3,4} target 6: greedy=3 coins, opt=2
BOUNDED CASE   cap of k uses/item -> binary/power-of-two split into 0/1 knapsack, not this template
COMPLEXITY     O(n*W) time, O(W) space; still pseudo-polynomial in the value of W/target
ENUMERATE ASK  "list all combinations" -> backtracking, not DP (output can be exponential)
```

## Sources

- [Coin Change — LeetCode](https://leetcode.com/problems/coin-change/) — accessed 2026-07-26
- [Coin Change II — LeetCode](https://leetcode.com/problems/coin-change-ii/) — accessed 2026-07-26
- [Combination Sum IV — LeetCode](https://leetcode.com/problems/combination-sum-iv/) — accessed 2026-07-26
- [Combination Sum — LeetCode](https://leetcode.com/problems/combination-sum/) — accessed 2026-07-26
- [Perfect Squares — LeetCode](https://leetcode.com/problems/perfect-squares/) — accessed 2026-07-26
- [Knapsack problem — Wikipedia](https://en.wikipedia.org/wiki/Knapsack_problem) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
