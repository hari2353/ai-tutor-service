# Lab 25: Greedy + Exchange Arguments

**Track:** T02 DSA: 21 Patterns · **Time:** 1.5h · **XP:** 50
**Module:** `T02-adv-greedy`

**You will build:** the six canonical greedy problems — interval scheduling, both jump games, gas station, task scheduler with cooldown, and fractional vs 0/1 knapsack — where each function's docstring must state the exchange argument that proves its local choice globally optimal (or, for 0/1 knapsack, exactly why the exchange argument *fails* and DP is required).

**You will be able to answer:** *"Why is your greedy algorithm correct — prove it, don't just show it passes the examples."*

## Setup

```bash
cd labs/py/25-adv-greedy
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`interval_schedule(intervals)`** — maximum number of non-overlapping intervals (half-open `[s, e)` semantics: `s >= last_end` means compatible). Sort by **finish time**, scan, count. Intervals that merely touch — `(1,2)` and `(2,3)` — do NOT overlap.
2. **`jump_game(nums)`** — `True` iff the last index is reachable. Track the farthest reachable index; bail out `False` the moment the scan position passes it. Empty list and single-element list → `True`.
3. **`jump_game_min(nums)`** — minimum jumps to the last index, `-1` if unreachable. Greedy layer expansion (BFS-like): walk the current level, track farthest reach, one jump per level. `[0]` → 0; `[0,1]` → -1.
4. **`gas_station(gas, cost)`** — starting index that completes the circuit, or -1. One pass: running tank, reset candidate to `i+1` whenever the tank goes negative; total gas < total cost → -1. Single station that exactly breaks even → 0.
5. **`task_scheduler(tasks, n)`** — minimum intervals to run all tasks, identical tasks separated by at least `n` cooldown slots. **Simulation**, not the formula: each tick, among *available* tasks (cooldown expired) run the one with the largest remaining count; idle otherwise. Must agree with the closed form `max(len(tasks), (max_freq-1)*(n+1) + count_of_max_freq_tasks)` on every input.
6. **`fractional_knapsack(capacity, items)`** — max value taking items (weight, value) whole or in fractions; greedy by value/weight ratio, provably optimal. Returns a float; `pytest.approx` in tests.
7. **`knapsack_01(capacity, items)`** — max value with indivisible items; DP required. Plus **`greedy_knapsack_01(capacity, items)`** — the ratio greedy, deliberately kept, as the failure witness.
8. **The contrast test is the point of the lab** — on the fixture `capacity=50, items=[(10,60),(20,100),(30,120)]`: greedy-by-ratio takes `(10,60)+(20,100)` = 160, DP finds the optimum 220 (`(20,100)+(30,120)` fit exactly), while **fractional** knapsack takes all three optimally (240.0). One identical fixture, three algorithms, three answers — that is the whole greedy-vs-DP story in one test.
9. **Edge cases are part of the contract**: empty intervals/tasks/items, single interval/task, unreachable jumps, impossible gas station, cooldown zero, zero capacity.
10. **No floats in 0/1 paths, no sorting inputs you shouldn't** — fractional knapsack is the only place a ratio (and hence float division) is legitimate. All integer functions stay integer.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Return the intervals, not the count** — extend `interval_schedule` to return the actual selected list; `pytest.approx` your way through ties. *(Interview: "I don't want the count, I want the calendar.")*
2. **Min arrows to burst balloons (LC 452)** — the same finish-time greedy in disguise; note what changes with closed vs half-open interval semantics.
3. **Huffman coding** — always merge the two least-frequent nodes via `heapq`; write the exchange argument for why the two rarest symbols can sit as deepest siblings in some optimal tree.
4. **Coin change taxonomy** — implement greedy-largest-coin and DP coin change; find the smallest denomination set where greedy fails ({1,3,4} at 6 is the classic). *(Interview: "when is greedy coin change safe?")*
