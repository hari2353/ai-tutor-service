# Lab 15: 0/1 Knapsack

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p15-knapsack-01`

**You will build:** the 0/1 knapsack family — classic value-maximizing DP in both the 2D table and the 1D rolling-array form — plus the three problems that are secretly the same DP: subset-sum (feasibility), partition-equal-subset-sum (target = sum/2), and target-count paths (counting variants of the recursion).

**You will be able to answer:** *"Why does the 1D knapsack loop go backwards — and what breaks if it doesn't?"*

## Setup

```bash
cd labs/py/15-knapsack-01
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`knapsack_2d(weights, values, capacity)`** — maximum value achievable with each item used at most once. 2D DP `dp[i][w]` = best using the first i items under capacity w. Returns 0 for empty items or 0 capacity.
2. **`knapsack_1d(weights, values, capacity)`** — same answer, 1D array, inner loop descending from capacity to weight. **Backwards is load-bearing**: ascending lets an item be taken twice (that's unbounded knapsack, lab 16).
3. **`subset_sum(nums, target)`** — True iff some subset sums to target (weights = values = nums). Must handle negatives-in-target cases sensibly: target < 0 → False.
4. **`partition_equal_subset_sum(nums)`** — True iff nums can be split into two subsets with equal sums. Odd total → False immediately; empty list → True (two empty halves).
5. **`target_count(nums, target)`** — count subsets summing exactly to target (the counting variant). Zero-items edge: `target_count([], 0) == 1` (the empty subset), `target_count([], 5) == 0`.
6. **Cross-consistency** — `knapsack_2d` and `knapsack_1d` must agree on every input; the 1D form must not allocate an O(n·W) table (spot-checked by behaviour: a large capacity that would blow memory as 2D still returns quickly in 1D).
7. **Determinism** — no sorting of inputs, no floating point. All inputs are non-negative ints (except target edges covered above).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Item recovery** — extend `knapsack_2d` to return *which* items were taken (backtrack through the table). *(Interview: "I don't want the value, I want the shopping list.")*
2. **Space-hardening** — capacity 10⁹ with tiny item counts → meet-in-the-middle over item subsets.
3. **Multi-constraint** — two capacities (weight and volume): 3D DP; note the state-space blowup.
4. **Greedy fails** — write a value/weight greedy and find the smallest counterexample; be ready to show it in an interview when asked "why DP instead of greedy?"
