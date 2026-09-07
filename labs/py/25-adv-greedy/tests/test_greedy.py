"""Lab 25 tests — greedy + exchange arguments.

20 tests. Every fixture expectation was hand-verified against an independent
brute force (subset enumeration / BFS / try-every-start / LP extreme points /
closed form) before being baked in. No sleeps, no wall clock, pure stdlib.
"""
import random
from collections import Counter, deque

import pytest

FIXTURE_50 = [(10, 60), (20, 100), (30, 120)]       # THE greedy-vs-DP fixture
FIXTURE_10 = [(6, 12), (5, 9), (5, 9)]              # the CLRS-style counterexample


# ------------------------------------------------------------------ helpers (brute forces)
def _brute_interval(intervals):
    """Max compatible subset by full enumeration (half-open semantics)."""
    n = len(intervals)
    best = 0
    for mask in range(1 << n):
        sel = [intervals[i] for i in range(n) if mask >> i & 1]
        ok = all(sel[a][1] <= sel[b][0] or sel[b][1] <= sel[a][0]
                 for a in range(len(sel)) for b in range(a + 1, len(sel)))
        if ok:
            best = max(best, len(sel))
    return best


def _brute_jump_min(nums):
    """True BFS over jump edges."""
    n = len(nums)
    if n <= 1:
        return 0
    dist = {0: 0}
    q = deque([0])
    while q:
        i = q.popleft()
        for j in range(i + 1, min(i + nums[i], n - 1) + 1):
            if j not in dist:
                dist[j] = dist[i] + 1
                q.append(j)
    return dist.get(n - 1, -1)


def _brute_gas(gas, cost):
    """Try every starting station."""
    n = len(gas)
    for s in range(n):
        tank = 0
        for k in range(n):
            i = (s + k) % n
            tank += gas[i] - cost[i]
            if tank < 0:
                break
        else:
            return s
    return -1


def _formula_tasks(tasks, n):
    """The LC 621 closed form the simulation must agree with."""
    if not tasks:
        return 0
    counts = Counter(tasks)
    maxf = max(counts.values())
    cnt = sum(1 for v in counts.values() if v == maxf)
    return max(len(tasks), (maxf - 1) * (n + 1) + cnt)


def _brute_frac(capacity, items):
    """Fractional-knapsack optimum by LP extreme-point enumeration:
    a full subset plus at most one partially-taken item."""
    n = len(items)
    best = 0.0
    for mask in range(1 << n):
        w = sum(items[i][0] for i in range(n) if mask >> i & 1)
        if w > capacity:
            continue
        v = sum(items[i][1] for i in range(n) if mask >> i & 1)
        best = max(best, float(v))
        for p in range(n):
            if mask >> p & 1:
                continue
            iw, iv = items[p]
            take = capacity - w
            if take <= 0 or take >= iw:
                continue
            best = max(best, v + iv * take / iw)
    return best


def _brute_01(capacity, items):
    """0/1 optimum by full subset enumeration."""
    n = len(items)
    best = 0
    for mask in range(1 << n):
        w = sum(items[i][0] for i in range(n) if mask >> i & 1)
        if w > capacity:
            continue
        v = sum(items[i][1] for i in range(n) if mask >> i & 1)
        best = max(best, v)
    return best


# ------------------------------------------------------------------ interval scheduling
def test_interval_classic(G):
    assert G.interval_schedule([(1, 3), (2, 4), (3, 5)]) == 2
    assert G.interval_schedule([(1, 2), (2, 3), (3, 4), (1, 3)]) == 3


def test_interval_edge_cases(G):
    assert G.interval_schedule([]) == 0                                    # empty
    assert G.interval_schedule([(5, 7)]) == 1                             # single
    assert G.interval_schedule([(1, 2), (2, 3)]) == 2                     # touching: half-open
    assert G.interval_schedule([(7, 7), (3, 7)]) == 2                      # zero-length tie


def test_interval_long_first_trap(G):
    """A long early interval blocks; the greedy must reject it. This is the
    counterexample to sorting by start time."""
    assert G.interval_schedule([(0, 100), (1, 10), (11, 20), (21, 30)]) == 3


def test_interval_matches_bruteforce_randomized(G):
    rng = random.Random(42)
    for _ in range(150):
        n = rng.randrange(0, 9)
        ivs = []
        for _ in range(n):
            s = rng.randrange(0, 12)
            ivs.append((s, s + rng.randrange(0, 9)))
        assert G.interval_schedule(ivs) == _brute_interval(ivs)


# ------------------------------------------------------------------ jump game
def test_jump_game_reachability(G):
    assert G.jump_game([2, 3, 1, 1, 4]) is True
    assert G.jump_game([3, 2, 1, 0, 4]) is False


def test_jump_game_edge_cases(G):
    assert G.jump_game([0]) is True            # single element: already there
    assert G.jump_game([]) is True             # empty: vacuously reachable
    assert G.jump_game([0, 1]) is False        # stuck at index 0
    assert G.jump_game([1, 0, 2]) is False     # mid-array zero


def test_jump_min_classic(G):
    assert G.jump_game_min([2, 3, 1, 1, 4]) == 2
    assert G.jump_game_min([1, 1, 1, 1]) == 3
    assert G.jump_game_min([2, 0, 1]) == 1
    assert G.jump_game_min([1, 2, 0, 1]) == 2


def test_jump_min_edge_cases(G):
    assert G.jump_game_min([0]) == 0                       # no jump needed
    assert G.jump_game_min([3, 2, 1, 0, 4]) == -1          # unreachable
    assert G.jump_game_min([0, 1]) == -1                   # stuck at index 0


def test_jump_min_matches_bfs_randomized(G):
    rng = random.Random(7)
    for _ in range(150):
        n = rng.randrange(1, 9)
        nums = [rng.randrange(0, 5) for _ in range(n)]
        assert G.jump_game_min(nums) == _brute_jump_min(nums)
        assert G.jump_game(nums) == (_brute_jump_min(nums) != -1)


# ------------------------------------------------------------------ gas station
def test_gas_classic(G):
    assert G.gas_station([1, 2, 3, 4, 5], [3, 4, 5, 1, 2]) == 3
    assert G.gas_station([3, 1, 1], [1, 2, 2]) == 0


def test_gas_edge_cases(G):
    assert G.gas_station([5], [5]) == 0                     # single, break-even
    assert G.gas_station([1], [2]) == -1                    # single, impossible
    assert G.gas_station([2, 3, 4], [3, 4, 3]) == -1        # impossible: deficit
    assert G.gas_station([1, 5, 1], [2, 3, 2]) == 1         # reset skips dead range


def test_gas_matches_try_every_start_randomized(G):
    rng = random.Random(11)
    for _ in range(150):
        n = rng.randrange(1, 7)
        gas = [rng.randrange(0, 6) for _ in range(n)]
        cost = [rng.randrange(0, 6) for _ in range(n)]
        assert G.gas_station(gas, cost) == _brute_gas(gas, cost)


# ------------------------------------------------------------------ task scheduler
def test_task_classic(G):
    assert G.task_scheduler(list("AAABBB"), 2) == 8
    assert G.task_scheduler(list("AAAAAABCDEFG"), 2) == 16


def test_task_edge_cases(G):
    assert G.task_scheduler(list("AAABBB"), 0) == 6         # cooldown zero
    assert G.task_scheduler(list("ABCDE"), 2) == 5         # all distinct
    assert G.task_scheduler(list("AAA"), 2) == 7           # one type
    assert G.task_scheduler(["A"], 5) == 1                 # single task
    assert G.task_scheduler([], 2) == 0                    # empty
    assert G.task_scheduler(list("AA"), 0) == 2           # cooldown-zero pair


def test_task_agrees_with_formula_randomized(G):
    """THE cross-check: the simulation must equal the closed form always."""
    rng = random.Random(13)
    for _ in range(150):
        tasks = []
        for ch in "ABCD":
            tasks += [ch] * rng.randrange(0, 5)
        rng.shuffle(tasks)
        n = rng.randrange(0, 4)
        assert G.task_scheduler(tasks, n) == _formula_tasks(tasks, n)


# ------------------------------------------------------------------ knapsack: THE contrast
def test_greedy_vs_dp_contrast_on_one_fixture(G):
    """The whole lab in one test: capacity 50, items [(10,60),(20,100),(30,120)].
    0/1 greedy-by-ratio takes (10,60)+(20,100)=160; DP finds (20,100)+(30,120)=220;
    fractional takes all three = 240. Same fixture, three algorithms, three
    answers — greedy's exchange argument breaks exactly where divisibility does."""
    assert G.greedy_knapsack_01(50, FIXTURE_50) == 160
    assert G.knapsack_01(50, FIXTURE_50) == 220
    assert G.fractional_knapsack(50, FIXTURE_50) == pytest.approx(240.0)
    assert G.greedy_knapsack_01(50, FIXTURE_50) < G.knapsack_01(50, FIXTURE_50)
    assert G.knapsack_01(50, FIXTURE_50) < G.fractional_knapsack(50, FIXTURE_50)


def test_greedy_fails_on_clrs_counterexample(G):
    """The classic: capacity 10, greedy locks in (6,12), optimal is 5+5=18.
    Fractional on the same fixture takes both 5s whole plus half the 20."""
    assert G.greedy_knapsack_01(10, FIXTURE_10) == 12
    assert G.knapsack_01(10, FIXTURE_10) == 18
    assert G.fractional_knapsack(10, FIXTURE_10) == pytest.approx(19.2)


# ------------------------------------------------------------------ fractional knapsack
def test_fractional_classic_and_edges(G):
    assert G.fractional_knapsack(10, [(5, 10), (5, 20)]) == pytest.approx(30.0)   # full fit
    assert G.fractional_knapsack(10, [(20, 100)]) == pytest.approx(50.0)           # half of one
    assert G.fractional_knapsack(5, [(10, 10)]) == pytest.approx(5.0)              # oversize item
    assert G.fractional_knapsack(0, [(5, 10)]) == pytest.approx(0.0)              # zero capacity
    assert G.fractional_knapsack(10, []) == pytest.approx(0.0)                     # empty items


def test_fractional_matches_bruteforce_randomized(G):
    rng = random.Random(17)
    for _ in range(120):
        n = rng.randrange(0, 9)
        items = [(rng.randrange(1, 15), rng.randrange(1, 30)) for _ in range(n)]
        cap = rng.randrange(0, 41)
        assert G.fractional_knapsack(cap, items) == pytest.approx(_brute_frac(cap, items))


# ------------------------------------------------------------------ 0/1 knapsack
def test_knapsack_01_classic_and_edges(G):
    assert G.knapsack_01(6, [(1, 10), (2, 20), (3, 30)]) == 60        # exact fit, all items
    assert G.knapsack_01(10, []) == 0                                 # empty items
    assert G.knapsack_01(0, FIXTURE_10) == 0                          # zero capacity
    rng = random.Random(19)
    for _ in range(120):
        n = rng.randrange(0, 11)
        items = [(rng.randrange(1, 12), rng.randrange(1, 25)) for _ in range(n)]
        cap = rng.randrange(0, 31)
        assert G.knapsack_01(cap, items) == _brute_01(cap, items)
