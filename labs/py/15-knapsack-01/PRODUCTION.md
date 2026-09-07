# Production notes — 0/1 knapsack DP

## Where this DP ships

- **Resource allocation** — cloud bin-packing / scheduling: which tasks fit on which machines under CPU/RAM budgets; the DP variant appears as "marginal value per unit capacity" in steady-state allocators.
- **Budget & capacity planning** — ad-slot allocation (which creatives to place under spend caps and impression inventory), portfolio selection under risk budgets.
- **Feature selection** — the exact-cover knapsack shows up in model/feature selection under cost constraints (feature acquisition budgets).
- **Caching policies** — "which k items to cache under capacity C to maximize hit value" is 0/1 knapsack; production caches approximate it with greedy/LRU because the exact DP is offline-only.
- **Data skip-plans** — query engines pick which indexes/materialized views to consult under a time budget: the same recurrence.

The honest production note: exact knapsack is **NP-hard** and pseudo-polynomial — O(n·W) explodes with big capacities, so real systems either (a) keep n and W small, (b) go greedy/FPTAS-approximate, or (c) solve the LP relaxation (fractional knapsack is greedy-optimal).

## Complexity table

| Variant | Time | Space | Notes |
|---|---|---|---|
| 2D table | O(n·W) | O(n·W) | easy to backtrack items |
| 1D rolling array | O(n·W) | **O(W)** | loop must go **down**; going up solves the *unbounded* problem instead |
| subset-sum (feasibility) | O(n·T) | O(T) bitset | bitset trick: O(n·T/64) |
| partition | O(n·S) | O(S) | subset-sum with T=S/2 |
| target-count | O(n·T) | O(T) | counting needs the +, not max |
| Brute force | O(2ⁿ) | O(n) | only viable for n ≤ ~25 (or 2n via meet-in-middle) |

## The 3 questions an interviewer asks

1. *"Why backwards in the 1D version?"* — ascending reads `dp[cap-w]` already updated *this round*, letting the same item be taken twice; descending guarantees each item is used at most once. This is exactly the lab 15 → lab 16 transition.
2. *"Capacity is 10⁹ — now what?"* — pseudo-polynomial blows up: switch to branch-and-bound, FPTAS approximation (within (1-ε) of optimal), or meet-in-the-middle at n ≤ 40.
3. *"What does the greedy value/weight heuristic give you?"* — a fast, usually-decent, no-guarantee answer; good for warm starts and pruning in exact solvers, wrong as "the solution".
