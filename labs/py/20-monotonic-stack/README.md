# Lab 20: Monotonic Stack

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p20-monotonic-stack`

**You will build:** the monotonic-stack family — next/previous greater element both directions, daily temperatures, largest rectangle in a histogram, maximal square and maximal rectangle in a binary matrix, and stock span — the "first thing to the left/right that beats me" pattern.

**You will be able to answer:** *"Give me an O(n) algorithm for 'next greater element' — and why does a monotonic stack give O(n) when the data has quadratic comparisons?"*

## Setup

```bash
cd labs/py/20-monotonic-stack
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`next_greater_element(nums)`** — for each index, the first value to the **right** that is strictly greater, else `-1`. Descending stack of indices; each element pushed and popped at most once.
2. **`previous_greater_element(nums)`** — first strictly greater to the **left**, else `-1`.
3. **`daily_temperatures(temps)`** — for each day, how many days until a strictly warmer day, else 0. O(n) via the same stack.
4. **`largest_rectangle_in_histogram(heights)`** — max rectangle area under the histogram. Sentinel push (append a 0) to flush the stack at the end. O(n).
5. **`maximal_square(matrix)`** — largest all-1s **square** in a binary matrix (rows of "0"/"1" strings or 0/1 ints — accept both): return its area. Classic DP `dp[i][j] = min(up, left, diag) + 1`.
6. **`maximal_rectangle(matrix)`** — largest all-1s **rectangle**: compress rows into histograms and apply (4) per row. Return area.
7. **`stock_span(prices)`** — for each day, the number of **consecutive** preceding days (including today) with price ≤ today's. O(n) via a stack of (price, span) pairs.
8. **The stack invariant is the contract** — every test can be reasoned about via "elements enter once, leave once": the witness test proves O(n) against the brute-force O(n²).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Sliding-window maximum** — the deque cousin: monotonic *queue*, same invariant, different structure; ship it and articulate when deque beats stack.
2. **Buildings with an ocean view** — prefix problems that reduce to "is there anything taller to the right": solve it with and without a stack; compare.
3. **132 pattern** — detect the `i<j<k, a[i]<a[k]<a[j]` pattern with a monotonic stack; the canonical "stack problem that isn't obviously a stack problem".
4. **Constrained watermark alerting** — your daily-temperatures code, but over a stream: process one price at a time and emit alerts on N-day highs; note what becomes O(1) amortized.
