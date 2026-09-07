# Lab 16: Unbounded Knapsack

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p16-knapsack-unbounded`

**You will build:** the unbounded (items reusable) knapsack family — the DP where the inner loop runs **forward**: unbounded knapsack max-value, coin change (min coins), coin change II (count ways), rod cutting, and integer break — plus one test that proves ascending-vs-descending is the entire difference between lab 15 and lab 16.

**You will be able to answer:** *"0/1 vs unbounded knapsack — one loop direction is the entire difference. Which, why, and what problem does each model?"*

## Setup

```bash
cd labs/py/16-knapsack-unbounded
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`unbounded_knapsack(weights, values, capacity)`** — max value when each item may be taken any number of times. 1D DP, inner loop **ascending** (that's what makes reuse possible).
2. **`coin_change(coins, amount)`** — fewest coins summing to amount; `-1` if impossible. Empty coins and amount 0 → 0; empty coins and amount > 0 → -1.
3. **`coin_change_ii(coins, amount)`** — number of **combinations** (order-independent; `[1,2]` and `[2,1]` are the same way). Coin value ≤ 0 is ignored. `coin_change_ii([], 0) == 1` (the empty multiset).
4. **`rod_cutting(prices, length)`** — `prices[i]` is the value of a piece of length i+1 (1-indexed by piece length); maximize the value of a rod of `length`. `rod_cutting([anything], 0) == 0`.
5. **`integer_break(n)`** — split n (n ≥ 2) into ≥2 positive integers maximizing the product: `integer_break(10) == 36` (3+3+4). Classic answer: all 3s, with a 2 or 4 at the end.
6. **Direction witness** — the test suite includes a direct demonstration: running the *0/1* backwards algorithm on unbounded input gives a different (wrong) answer than the forwards one. Both modules in the test compare against each other through the public functions of this module only.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Coin recovery** — return the actual multiset of coins (not just the count); canonical coin systems make the greedy work — find the smallest non-canonical system.
2. **Word break** — `word_break(s, dictionary)` is unbounded knapsack over substrings; port it and spot the recurrence.
3. **Bounded knapsack** — items with counts (0/many between): binary-split each item into powers-of-two bundles and reduce to 0/1.
4. **Revenue tables** — rod cutting with per-cut cost k; articulate the peak-pricing analogy in your own words.
