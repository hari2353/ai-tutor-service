# Greedy Algorithms and the Exchange Argument

> **Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **Prereqs:** T02-p04-merge-intervals, T02-p15-knapsack-01
> **Module id:** `T02-adv-greedy` · **Tags:** advanced, greedy, proofs

## The 30-second version

A greedy algorithm makes a locally optimal choice at each step and never reconsiders it, which is either correct or a subtle trap depending entirely on whether the problem has two structural properties: **optimal substructure** (an optimal solution to the whole problem contains optimal solutions to its subproblems) and the **greedy-choice property** (a locally optimal first choice can always be extended to a globally optimal solution). Having optimal substructure alone is not enough — 0/1 knapsack has optimal substructure but greedy-by-value-density fails on it, which is exactly why it needs DP instead. The way you *prove* a greedy choice is safe, rather than just hoping it is, is the **exchange argument**: assume an optimal solution `OPT` that disagrees with your greedy choice at the first point of difference, show you can swap/exchange that piece of `OPT` for your greedy choice without making the solution worse, and conclude by induction that greedy is at least as good as any optimal solution, hence itself optimal. The decision rule in an interview: if you can't complete an exchange argument in two or three sentences, don't submit a greedy solution — fall back to DP, because greedy that "seems to work" on examples but has no proof is the single most common way candidates fail silently on the hidden test cases.

## Why this gets asked

It separates candidates who can recognize a pattern from candidates who understand why the pattern is valid. Interviewers who have shipped scheduling systems, ad auction pacing, or resource-allocation logic have personally been burned by a greedy heuristic that worked on every case the team tested and then failed in production on a distribution of inputs nobody anticipated — because nobody proved it, they just observed it worked and shipped it. The exchange argument is the tool that turns "seems to work" into "provably works," and asking a candidate to produce one on the spot tests real algorithmic maturity rather than pattern memorization. It also tests whether you know the canonical *failure* cases (0/1 knapsack, and coin systems with non-canonical denominations) cold enough to catch yourself before reaching for greedy where it doesn't apply.

---

## Lineage: past → present → future

**What came before.** Before greedy algorithms were formalized as a distinct design paradigm, most optimization problems were approached either by brute-force enumeration (exponential, intractable beyond tiny inputs) or by dynamic programming once Bellman formalized it in the 1950s — DP is strictly more powerful (it can solve everything greedy can, plus much more, at the cost of higher time/space complexity) but is harder to reason about and slower to run. The pain greedy solves: many real scheduling, interval, and resource-allocation problems have DP solutions that are polynomial but needlessly expensive (O(n^2) or worse) when a correctly-proven greedy choice collapses the same problem to O(n log n), typically dominated by a single sort.

**Where it stands now.** Matroid theory (from combinatorial optimization, formalized by Whitney in 1935 and connected to greedy algorithms by Edmonds and Rado in the 1960s-70s) gives the general mathematical characterization of *exactly* which optimization problems greedy solves correctly: a problem is greedy-solvable if and only if its feasible solutions form a matroid (or an extension like a matroid intersection for some richer problems). Interviews almost never ask you to invoke matroid theory by name, but the exchange argument you're expected to produce live is precisely the proof technique matroid theory generalizes — knowing the connection exists (even without using the vocabulary) signals real depth. In practice, production systems mix the two: greedy is used as a fast heuristic where an approximation is acceptable (bin-packing heuristics, job-scheduling approximations, network routing with greedy shortest-first strategies) and DP or ILP (integer linear programming) is used where exactness is required and the problem size allows it.

**Where it's heading.** No new foundational theory is expected — matroid-based greedy characterization is a closed, mature area of combinatorial optimization. The applied direction is learned/adaptive greedy heuristics (using ML to prioritize which greedy choice to make first in NP-hard scheduling and bin-packing problems, common in modern job schedulers and cloud resource allocators) which trade provable optimality for empirically-good-enough performance at scale — flag this as a real production pattern (heuristic-guided greedy) but not something that changes the classic proof technique itself, which remains the interview standard.

---

## Mental model

Think of the exchange argument as a duel between your greedy choice and whatever the "best possible" solution supposedly did instead. If you can always win that duel (or at least tie) at the very first point of disagreement, you've shown greedy could have been the optimal solution all along — it just never needed to lose an argument with anything better.

```
OPT:     [choice_1] [choice_2*] [choice_3] ...   (* = first place OPT differs from greedy)
GREEDY:  [choice_1] [greedy_2]  [??]        ...

Exchange step: swap OPT's choice_2* for greedy's greedy_2.
Show: the swapped solution is still feasible, and its value is >= OPT's value.
Conclude: an optimal solution exists that agrees with greedy up to step 2.
Repeat inductively -> an optimal solution exists that agrees with greedy
everywhere -> greedy IS an optimal solution.
```

For interval scheduling (the classic "maximum number of non-overlapping intervals"), the mental picture is even more concrete: picking the interval that finishes earliest always leaves the most room for everything after it, because no other valid first choice can free up more of the timeline than the earliest-finishing one.

---

## Recognition heuristics

- **"Maximum number of non-overlapping intervals"** or **"minimum number of meeting rooms"** — sort by finish time (or start time for room-counting), classic exchange-argument-provable greedy.
- **"Minimum number of coins to make change"** with an *arbitrary* denomination set (not stated as canonical like US currency) — greedy-by-largest-coin is a trap; this needs DP. The tell is the problem *not* guaranteeing the coin system is canonical.
- **"Fractional knapsack"** (items can be split) — greedy by value/weight ratio is provably optimal via exchange argument. **"0/1 knapsack"** (items are indivisible) — the same greedy fails; this needs DP, and knowing exactly why the exchange argument breaks (an indivisible item can't be partially swapped) is the litmus test.
- **"Assign tasks to minimize total waiting time / minimize maximum lateness"** — sort by shortest processing time or earliest deadline, both provable via exchange argument (different sort keys for different objective functions — know which sort key proves which objective).
- **"Huffman coding" / "minimum cost to merge k sorted lists/files"** — greedy: always merge the two smallest, provable via an exchange argument on the structure of an optimal merge tree.
- **A qualifier like "prove your greedy choice is optimal" or "why does this work"** stated explicitly in the prompt — a direct signal the interviewer wants the exchange argument, not just working code.
- **Problems that "smell greedy" but involve a global constraint interacting with local choices** (e.g., job scheduling with dependencies, resource allocation with capacity limits) — a strong signal that naive greedy fails and either a smarter greedy invariant or DP/flow is required; don't assume greedy just because the problem is about picking things one at a time.

---

## How it actually works — writing an exchange argument, and where it fails

The general shape of an exchange argument has four moves: **(1) Assume optimality of an alternative.** Let `OPT` be some optimal solution, and suppose it differs from your greedy solution `G` at the earliest point of disagreement. **(2) Perform the exchange.** Show a way to modify `OPT` — swapping out its choice at that point for greedy's choice — that produces a new solution `OPT'`. **(3) Show `OPT'` is still feasible.** The exchanged solution must still satisfy every problem constraint. **(4) Show `OPT'` is no worse.** `value(OPT') >= value(OPT)` (for maximization; reverse the inequality for minimization). Since `OPT` was assumed optimal and `OPT'` is at least as good, `OPT'` is also optimal, and it now agrees with `G` on one more choice than `OPT` did. Repeating this argument inductively across the whole solution shows an optimal solution exists that agrees with `G` everywhere, i.e., `G` itself is optimal.

**Concretely, for interval scheduling** (maximize count of non-overlapping intervals): sort by finish time, greedily take an interval whenever it doesn't overlap the last one taken. Exchange argument: suppose `OPT`'s first interval `I_opt` finishes later than greedy's first pick `I_greedy` (which finishes earliest among all intervals by construction). Swap `I_opt` for `I_greedy` in `OPT`. Feasibility holds because `I_greedy` finishes no later than `I_opt`, so it can't conflict with anything `I_opt` didn't already conflict with. The count is unchanged (one-for-one swap), so `OPT'` is still optimal and now agrees with greedy on the first choice. Induct on the rest of the timeline.

**Where it breaks: 0/1 knapsack.** The greedy-by-value-density heuristic (take items in decreasing order of value/weight until the capacity is full) fails because the exchange argument's step 2 (perform the exchange) doesn't go through: you can't partially swap an indivisible item the way you can freely re-slice a fractional item. Concrete counterexample: capacity 10, item A (weight 6, value 12, ratio 2.0), item B (weight 5, value 9, ratio 1.8), item C (weight 5, value 9, ratio 1.8). Greedy takes A (ratio 2.0 highest) leaving capacity 4, can't fit B or C, total value 12. Optimal is B+C, total value 18. The ratio-based local choice locks in a decision that can't be un-made without literally removing a whole item, and no exchange restores feasibility without losing value — DP (0/1 knapsack) is required because it explores both "take" and "don't take" branches for every item rather than committing greedily.

**Where it breaks: non-canonical coin systems.** With denominations {1, 3, 4}, making 6 cents greedily (largest first) gives 4+1+1 = three coins; the optimal is 3+3 = two coins. The exchange argument fails here because swapping a greedy coin for a smaller-denomination combination doesn't preserve the "no worse" property uniformly across all denomination sets — it only happens to work for canonical systems (like US currency) where every denomination is a "good multiple" of the smaller ones, a property that must be checked, not assumed.

---

## Template code (Python, Java, Go)

```python
# Interval Scheduling — maximum non-overlapping intervals, sort by finish time
def max_non_overlapping(intervals: list[tuple[int, int]]) -> int:
    intervals = sorted(intervals, key=lambda iv: iv[1])  # sort by finish time
    count = 0
    last_finish = float('-inf')
    for start, finish in intervals:
        if start >= last_finish:
            count += 1
            last_finish = finish
    return count

# Fractional Knapsack — greedy by value/weight ratio, PROVABLY optimal
def fractional_knapsack(capacity: float, items: list[tuple[float, float]]) -> float:
    # items: list of (weight, value)
    items = sorted(items, key=lambda it: it[1] / it[0], reverse=True)
    total_value = 0.0
    remaining = capacity
    for weight, value in items:
        if remaining <= 0:
            break
        take = min(weight, remaining)
        total_value += value * (take / weight)
        remaining -= take
    return total_value

# 0/1 Knapsack — greedy FAILS here; DP required (shown for contrast)
def knapsack_01(capacity: int, items: list[tuple[int, int]]) -> int:
    dp = [0] * (capacity + 1)
    for weight, value in items:
        for cap in range(capacity, weight - 1, -1):
            dp[cap] = max(dp[cap], dp[cap - weight] + value)
    return dp[capacity]

# Minimum coins — greedy only correct for canonical systems; DP is general
def min_coins_dp(coins: list[int], amount: int) -> int:
    INF = float('inf')
    dp = [0] + [INF] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return dp[amount] if dp[amount] != INF else -1
```

```java
import java.util.*;

public class Greedy {

    // Interval Scheduling
    static int maxNonOverlapping(int[][] intervals) {
        Arrays.sort(intervals, Comparator.comparingInt(iv -> iv[1]));
        int count = 0;
        int lastFinish = Integer.MIN_VALUE;
        for (int[] iv : intervals) {
            if (iv[0] >= lastFinish) {
                count++;
                lastFinish = iv[1];
            }
        }
        return count;
    }

    // Fractional Knapsack
    static double fractionalKnapsack(double capacity, double[][] items) {
        // items: {weight, value}
        Arrays.sort(items, (a, b) -> Double.compare(b[1] / b[0], a[1] / a[0]));
        double totalValue = 0, remaining = capacity;
        for (double[] item : items) {
            if (remaining <= 0) break;
            double weight = item[0], value = item[1];
            double take = Math.min(weight, remaining);
            totalValue += value * (take / weight);
            remaining -= take;
        }
        return totalValue;
    }

    // 0/1 Knapsack — DP, greedy fails
    static int knapsack01(int capacity, int[][] items) {
        int[] dp = new int[capacity + 1];
        for (int[] item : items) {
            int weight = item[0], value = item[1];
            for (int cap = capacity; cap >= weight; cap--) {
                dp[cap] = Math.max(dp[cap], dp[cap - weight] + value);
            }
        }
        return dp[capacity];
    }

    // Minimum coins — DP, general (correct for non-canonical systems too)
    static int minCoins(int[] coins, int amount) {
        int[] dp = new int[amount + 1];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int a = 1; a <= amount; a++) {
            for (int c : coins) {
                if (c <= a && dp[a - c] != Integer.MAX_VALUE) {
                    dp[a] = Math.min(dp[a], dp[a - c] + 1);
                }
            }
        }
        return dp[amount] == Integer.MAX_VALUE ? -1 : dp[amount];
    }
}
```

```go
package main

import "sort"

// Interval Scheduling
func maxNonOverlapping(intervals [][2]int) int {
    sort.Slice(intervals, func(i, j int) bool { return intervals[i][1] < intervals[j][1] })
    count := 0
    lastFinish := -1 << 62
    for _, iv := range intervals {
        if iv[0] >= lastFinish {
            count++
            lastFinish = iv[1]
        }
    }
    return count
}

// Fractional Knapsack
type Item struct{ weight, value float64 }

func fractionalKnapsack(capacity float64, items []Item) float64 {
    sort.Slice(items, func(i, j int) bool {
        return items[i].value/items[i].weight > items[j].value/items[j].weight
    })
    totalValue, remaining := 0.0, capacity
    for _, it := range items {
        if remaining <= 0 {
            break
        }
        take := it.weight
        if remaining < take {
            take = remaining
        }
        totalValue += it.value * (take / it.weight)
        remaining -= take
    }
    return totalValue
}

// 0/1 Knapsack — DP, greedy fails
func knapsack01(capacity int, weights, values []int) int {
    dp := make([]int, capacity+1)
    for i := range weights {
        w, v := weights[i], values[i]
        for cap := capacity; cap >= w; cap-- {
            if dp[cap-w]+v > dp[cap] {
                dp[cap] = dp[cap-w] + v
            }
        }
    }
    return dp[capacity]
}

// Minimum coins — DP, general
func minCoins(coins []int, amount int) int {
    const INF = 1 << 30
    dp := make([]int, amount+1)
    for i := 1; i <= amount; i++ {
        dp[i] = INF
    }
    for a := 1; a <= amount; a++ {
        for _, c := range coins {
            if c <= a && dp[a-c] != INF && dp[a-c]+1 < dp[a] {
                dp[a] = dp[a-c] + 1
            }
        }
    }
    if dp[amount] == INF {
        return -1
    }
    return dp[amount]
}
```

## Complexity — derived, not asserted

**Interval scheduling:** O(n log n), dominated entirely by the sort; the greedy scan afterward is a single O(n) pass. This is the whole value proposition versus a DP formulation of the same problem, which would cost at least O(n log n) for the sort plus O(n) or O(n^2) depending on formulation — greedy doesn't beat DP's asymptotic class here so much as it avoids DP's higher implementation and reasoning overhead entirely.

**Fractional knapsack:** O(n log n) for the sort by ratio, O(n) for the greedy fill — strictly better than 0/1 knapsack's DP, which is O(n * capacity) (pseudo-polynomial, not truly polynomial in the input *size*, since `capacity` can be exponentially large relative to the number of bits needed to represent it).

**0/1 knapsack DP:** O(n * capacity) time and O(capacity) space with the rolling-array optimization shown above (iterating `cap` downward reuses the same array in place instead of needing a full 2D table). This is why "capacity" being huge (say, 10^9) makes even the "efficient" DP infeasible — a case where neither greedy nor the standard DP works, and you'd need branch-and-bound or an FPTAS (fully polynomial-time approximation scheme) instead, worth naming as a staff-level escalation.

**Minimum coins DP:** O(amount * len(coins)) time, O(amount) space — necessary in general because, unlike canonical coin systems, there's no way to prove a greedy largest-coin-first choice is safe without checking the specific denomination set's structure.

---

## The 5 variants interviewers actually ask

1. **Non-overlapping Intervals / Maximum Meetings in One Room (LC 435, LC 452-style).** Sort by finish time, greedy count — the textbook exchange-argument problem.
2. **Minimum Number of Arrows to Burst Balloons (LC 452).** Same interval-scheduling greedy in disguise: sort by end coordinate, greedily place an arrow at the earliest-ending balloon's end point, skip every balloon that arrow already covers.
3. **Jump Game II (LC 45): minimum jumps to reach the end of an array.** Greedy BFS-like layer expansion: at each "level," track the farthest reachable index, incrementing jumps only when you must cross into a new level — provable via an exchange argument that shows never overshooting the current level's farthest reach can't be suboptimal, since you always have the same or more remaining reach when you do jump.
4. **Task Scheduler (LC 621): minimum time to schedule tasks with a cooldown between identical tasks.** Greedy: always schedule the most frequent remaining task first, using a max-heap; the exchange argument here is subtler and often skipped, replaced with a direct formula (`max(len(tasks), (max_freq-1)*(n+1) + count_of_tasks_with_max_freq)`) that a strong candidate should be able to justify combinatorially.
5. **Gas Station (LC 134): can you complete a circular route given gas and cost arrays?** Greedy: if the total gas >= total cost, a valid starting point exists; walk once, resetting the candidate start whenever the running tank goes negative. The exchange argument here is a clever one: if you run out of gas at station `j` starting from `i`, no station between `i` and `j` can be a valid start either, because they'd have arrived at station `j` with an even smaller (or equal) tank than starting from `i` did.

---

## Common bugs and how greedy gets shipped wrong under pressure

- **Applying a greedy heuristic without an exchange argument, based only on passing the given examples.** This is the single most common way greedy gets shipped incorrectly — a candidate reasons "picking the biggest/smallest/earliest thing seems right" and the visible test cases happen not to contain a counterexample.
- **Reaching for greedy-by-ratio on 0/1 knapsack out of pattern-matching with fractional knapsack**, without checking whether items are actually divisible — the two problems look nearly identical in the prompt and have completely different correct algorithms.
- **Assuming a coin system is canonical without checking.** Greedy largest-coin-first is only provably correct for specific denomination sets (like standard currency); applying it to an arbitrary or adversarially-chosen coin set silently produces a suboptimal (not just "different but valid") answer.
- **Sorting by the wrong key.** Interval scheduling problems that look similar can require sorting by start time, finish time, or a computed value depending on the exact objective (maximize count vs. minimize rooms vs. minimize total lateness) — using finish-time-sort logic on a minimum-rooms problem (which actually needs a sweep over both start and finish events, or a min-heap of active end times) is a common under-pressure conflation.
- **Forgetting to handle ties in the sort key.** Many exchange arguments implicitly assume a strict tie-breaking rule (e.g., "earliest finish, and among ties, arbitrary is fine because the argument doesn't depend on tie order") — but some problems (Task Scheduler, Huffman coding) do depend on a specific tie-breaking rule, and getting it wrong produces a technically-different-but-still-optimal answer in some cases and a wrong one in others depending on the exact problem.
- **Not recognizing when a problem needs the greedy choice to be re-validated at every step (a local invariant), versus a one-time sort-then-scan.** Jump Game II and Gas Station both require maintaining a running invariant across the scan, not just sorting once; treating them as simple sort-and-greedy problems misses the actual mechanism.

---

## Interview questions

### Q1 — Maximum number of non-overlapping intervals. Prove your greedy choice is optimal.
**Testing:** can you produce a real exchange argument, not just working code.
**Answer:** Sort by finish time, greedily take any interval that doesn't overlap the last taken one. Exchange argument: if `OPT`'s first interval finishes later than greedy's first pick (which finishes earliest by construction), swap it in — feasibility holds since greedy's pick finishes no later, so it can't conflict with anything the swapped-out interval didn't already conflict with; the count is unchanged. Induct on the remainder.
**Follow-up trap:** *"Would sorting by start time instead of finish time also work?"* — no; a counterexample is easy to construct (a long interval starting first that blocks two short ones that start later but finish earlier) — sorting by start time doesn't have the same "frees up maximum remaining room" property that finish-time sort provably has.

### Q2 — Fractional Knapsack vs 0/1 Knapsack: why does greedy work for one and not the other?
**Testing:** the exact structural reason the exchange argument breaks.
**Answer:** In fractional knapsack you can always re-slice any item, so exchanging a lower-ratio item's weight for a higher-ratio item's weight strictly never decreases total value — the exchange step of the proof goes through cleanly. In 0/1 knapsack, items are atomic; you can't partially swap one item for a fraction of another, so a locally-optimal ratio-based choice can lock in a decision that can't be corrected without literally removing a whole item and potentially losing value in the process.
**Follow-up trap:** *"Give a concrete counterexample for 0/1 knapsack."* — capacity 10, items (weight 6, value 12), (weight 5, value 9), (weight 5, value 9); greedy-by-ratio takes the first item (ratio 2.0) and can't fit either remaining item, total 12; optimal takes the two weight-5 items, total 18.

### Q3 — Minimum coins to make change: when does greedy (largest denomination first) work, and when does it fail?
**Testing:** knowing greedy correctness for coin change is denomination-set-dependent, not universal.
**Answer:** Greedy works for canonical coin systems (like standard currency denominations) where every denomination is structured so a greedy choice never forecloses a better combination. It fails for arbitrary sets.
**Follow-up trap:** *"Give a coin system where greedy fails, and the correct answer."* — denominations {1, 3, 4}, amount 6: greedy gives 4+1+1 (three coins); optimal is 3+3 (two coins).

### Q4 — Minimum Number of Arrows to Burst Balloons (LC 452).
**Testing:** recognizing interval scheduling in a different costume.
**Answer:** Sort balloons by end coordinate; greedily shoot an arrow at the current balloon's end, and skip every subsequent balloon whose start is within that arrow's position.
**Follow-up trap:** *"Why sort by end coordinate and not start?"* — the same exchange argument as Q1: the earliest-ending balloon constrains the arrow position that covers the maximum number of balloons that must overlap it, exactly mirroring the interval-scheduling proof.

### Q5 — Task Scheduler (LC 621): minimum intervals needed given a cooldown between identical tasks.
**Testing:** whether you can justify a greedy formula combinatorially, not just recite it.
**Answer:** The answer is `max(len(tasks), (max_freq - 1) * (n + 1) + count_of_tasks_at_max_freq)`, derived by picturing the most frequent task as "anchors" spaced `n+1` apart with every other task (including idle slots) filling the gaps.
**Follow-up trap:** *"What if idle slots aren't allowed and you must reorder tasks instead?"* — a fundamentally different problem (rearrangement under adjacency constraints, closer to "reorganize string" LC 767) that needs a max-heap-based interleaving construction, not the same closed-form formula.

### Q6 — Gas Station (LC 134): find a starting index to complete a circular route, or determine none exists.
**Testing:** a non-obvious greedy invariant plus its proof.
**Answer:** If total gas >= total cost, a valid start exists. Scan once: if the running tank goes negative starting from candidate `i`, no station between `i` and the failure point `j` can be a valid start either, so jump the candidate directly to `j+1`.
**Follow-up trap:** *"Prove why skipping all of i..j is safe."* — any station `k` between `i` and `j` would arrive at `j` with a tank level less than or equal to what starting from `i` produced (since starting from `i` accumulated the most net gas possible up to that point among stations in that range), so if `i` fails at `j`, every station in between fails at `j` too.

### Q7 — Job Sequencing to minimize total lateness, one job at a time, single machine.
**Testing:** matching sort key to objective function.
**Answer:** Sort by earliest deadline first (EDF); this provably minimizes maximum lateness via an exchange argument showing any inversion (a later-deadline job scheduled before an earlier-deadline one) can be swapped without increasing maximum lateness.
**Follow-up trap:** *"Does this also minimize total (sum) lateness, or just maximum lateness?"* — EDF minimizes *maximum* lateness; minimizing *total* completion time (not lateness) uses a different greedy (shortest processing time first), and minimizing total *weighted* completion time needs yet another sort key (ratio of processing time to weight) — conflating these objectives is a common and costly mistake.

### Q8 — Huffman coding: build an optimal prefix-free binary code given symbol frequencies.
**Testing:** the exchange argument behind "always merge the two least-frequent nodes."
**Answer:** Repeatedly merge the two lowest-frequency nodes into a new node with their combined frequency, using a min-heap; the exchange argument shows that in any optimal code tree, the two least-frequent symbols can always be placed as siblings at the deepest level without increasing total weighted code length.
**Follow-up trap:** *"What if two different merge orders produce different but equally optimal trees?"* — that's expected and fine; Huffman coding doesn't guarantee a unique optimal tree, only an optimal *total weighted length*, and interviewers sometimes probe whether you conflate "the algorithm's specific output" with "the only possible optimal answer."

### Q9 — Prove that 0/1 knapsack cannot be solved by any greedy rule based purely on a per-item score (value, weight, ratio, or any combination), in general.
**Testing:** whether you understand the failure is structural, not a matter of finding the right score function.
**Answer:** Construct two instances where the same score-based ordering leads to a correct answer in one and a wrong answer in the other for *every* possible fixed scoring function — since capacity constraints interact combinatorially with which subset of items fits, no single per-item score can capture the necessary global reasoning about combinations, which is exactly what DP explores exhaustively (in polynomial pseudo-time) and greedy cannot.
**Follow-up trap:** *"Is there any special case of 0/1 knapsack where greedy does work?"* — yes: if all items have the same weight, greedy-by-value trivially works (it reduces to plain sorting by value since capacity constraints no longer interact combinatorially); this is worth naming as the boundary condition that clarifies exactly what breaks in the general case.

### Q10 — Design an exchange argument for "always pick the meeting room requiring the earliest reuse" in the minimum-meeting-rooms problem.
**Testing:** applying the exchange-argument technique to a problem that isn't simple interval scheduling (it's a resource-count problem, not a count-of-selections problem).
**Answer:** This problem is usually solved differently — with a sweep over start/end events (or a min-heap of currently-occupied rooms' end times) rather than a single greedy choice with a clean one-line exchange argument; a strong candidate should recognize that "minimum rooms" is fundamentally a *maximum overlap* computation, not a selection-maximization problem, and the correct approach counts concurrent intervals rather than making sequential accept/reject choices.
**Follow-up trap:** *"Why doesn't the interval-scheduling exchange argument transfer here?"* — because minimum-rooms needs to account for *every* interval simultaneously (nothing is ever rejected, only assigned to a room), whereas interval scheduling explicitly rejects some intervals to maximize a count — they're different objective functions wearing similar-looking problem statements.

### Q11 — When would you choose an approximation algorithm over an exact greedy/DP solution for an optimization problem?
**Testing:** staff-level judgment about when provable optimality isn't worth its cost.
**Answer:** When the exact algorithm's complexity class is infeasible at production scale (e.g., 0/1 knapsack with a capacity in the billions, making the pseudo-polynomial DP intractable) — an FPTAS or a well-tested greedy heuristic with a bounded approximation ratio (e.g., the classic 2-approximation for bin packing via first-fit-decreasing) trades a small, bounded loss of optimality for tractability.
**Follow-up trap:** *"How do you communicate this tradeoff to a non-technical stakeholder?"* — frame it in terms of the bound itself ("this heuristic is guaranteed to use no more than 11/9 times the optimal number of bins, provably, not just empirically") rather than "it's usually good enough," which is the senior distinction between an approximation algorithm and an unproven heuristic.

---

## Red flags that fail you

- Proposing a greedy solution with no exchange argument, justified only by "it passed the examples I tried."
- Applying fractional-knapsack-style ratio greedy to a 0/1 knapsack problem without noticing items are indivisible.
- Assuming any coin denomination set is greedy-safe without checking it's canonical.
- Confusing objective functions (maximize count vs. minimize lateness vs. minimize total completion time) and using the wrong sort key as a result.
- Not being able to state, precisely, what "optimal substructure" and "greedy-choice property" each mean and why both are needed.
- Treating minimum-rooms / maximum-overlap problems as if they were interval-scheduling selection problems.

---

## Cheat card

```
GREEDY WORKS IF   optimal substructure AND greedy-choice property both hold
                  (optimal substructure alone is NOT sufficient -- see knapsack)
EXCHANGE ARG      1. assume OPT disagrees with greedy at first choice
                  2. swap OPT's choice for greedy's
                  3. show still feasible
                  4. show value(OPT') >= value(OPT)
                  5. induct -> greedy is optimal
INTERVAL SCHED    sort by FINISH time, O(n log n) -- provable via exchange
FRACTIONAL KNAP   sort by value/weight ratio -- provable, items divisible
0/1 KNAPSACK      greedy FAILS (indivisible items break exchange step) -- DP,
                  O(n * capacity), pseudo-polynomial
COIN CHANGE       greedy only safe for CANONICAL denomination sets; general
                  case needs DP, O(amount * len(coins))
JUMP GAME II      greedy layer-expansion (BFS-like), track farthest reach
GAS STATION       greedy reset-on-negative-tank; total gas>=cost => feasible
HUFFMAN           always merge two least-frequent nodes (min-heap)
WATCH             wrong sort key for the actual objective; assuming canonical
                  coins; conflating selection-maximization vs overlap-counting
```

## Sources

- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), Chapter 16: Greedy Algorithms.
- Edmonds, J. (1971). "Matroids and the Greedy Algorithm." Mathematical Programming, 1(1), 127-136.
- [Non-overlapping Intervals — LeetCode](https://leetcode.com/problems/non-overlapping-intervals/) — accessed 2026-07-26
- [Minimum Number of Arrows to Burst Balloons — LeetCode](https://leetcode.com/problems/minimum-number-of-arrows-to-burst-balloons/) — accessed 2026-07-26
- [Jump Game II — LeetCode](https://leetcode.com/problems/jump-game-ii/) — accessed 2026-07-26
- [Gas Station — LeetCode](https://leetcode.com/problems/gas-station/) — accessed 2026-07-26
- [Task Scheduler — LeetCode](https://leetcode.com/problems/task-scheduler/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
