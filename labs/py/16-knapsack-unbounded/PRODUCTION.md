# Production notes — unbounded knapsack

## Where unbounded DP ships

- **Pricing engines** — "how many of each SKU at what price to maximize revenue under demand elasticity" is unbounded knapsack's cousin; vending/bundling optimizers use exactly this recurrence.
- **Making change in payment systems** — cash-drawer dispensing (ATMs, self-checkout) is min-coin-change on canonical coin systems; the DP is the fallback when the greedy provably fails (non-canonical sets like [1,3,4]).
- **Caching vs compute tradeoffs** — "how many cache tiers of each size to buy under a budget" — each tier repeatable, value = saved latency.
- **Ribbon/stock cutting** — paper, steel, fabric: cut-stock optimizers in manufacturing run rod-cutting DP at industrial scale (with width discretization to keep W sane).
- **Portfolio rebalancing with lot sizes** — integer-break style maximization under lot granularity constraints.

## Complexity table

| Problem | Recurrence | Time | Space |
|---|---|---|---|
| unbounded knapsack | `dp[w] = max(dp[w], dp[w-wi]+vi)` forwards | O(n·W) | O(W) |
| coin change (min) | `dp[a] = 1 + min(dp[a-c])` | O(n·A) | O(A) |
| coin change II (count) | coins outer, amounts inner | O(n·A) | O(A) |
| rod cutting | `dp[l] = max(prices[i] + dp[l-i])` | O(L²) (O(L·n) with piece cap) | O(L) |
| integer break | `dp[i] = max(j·(i−j), j·dp[i−j])` | O(n²) | O(n) |

**The one-sentence difference from 0/1:** backwards loops make each item usable once; forwards loops make it usable any number of times. Same table, opposite direction, different problem.

## The 3 questions an interviewer asks

1. *"Why does coin-change-ii need coins as the OUTER loop?"* — inner-amounts-outer-coins counts ordered permutations (that's 'climbing stairs' / composition counting); coins-outer counts multisets.
2. *"When is greedy coin change safe?"* — canonical coin systems (prove with the greedy-vs-DP exchange argument); most real systems are canonical by design, [1,3,4] is the classic counterexample.
3. *"Unbounded knapsack with W = 10⁹?"* — same pseudo-polynomial blowup as 0/1: switch to LP relaxation, FPTAS, or reduce W by GCD of the weights first.
