"""Lab 25 — greedy + exchange arguments. Fill in every TODO. Tests define done.

Rules:
  * interval_schedule: sort by FINISH time. Sorting by start is the classic trap.
  * jump_game_min: -1 when unreachable, 0 for len <= 1.
  * gas_station: one pass, no nested loop over start candidates.
  * task_scheduler: SIMULATION (one tick at a time), not the closed formula —
    though the result must agree with the formula.
  * fractional_knapsack may use float division; everything else stays integer.
  * Edge cases are part of the contract: empty inputs, single elements,
    unreachable jumps, impossible circuits, cooldown 0, capacity 0.
"""
from __future__ import annotations

from typing import List, Tuple


def interval_schedule(intervals: List[Tuple[int, int]]) -> int:
    """Maximum number of non-overlapping intervals (half-open [s, e)).

    EXCHANGE ARGUMENT: sort by finish time and take the earliest-finishing
    compatible interval first. Suppose OPT's first pick finishes later than
    greedy's (which finishes earliest of all). Swap OPT's pick for greedy's:
    the swap stays feasible (greedy's interval ends no later, so it conflicts
    with nothing OPT's pick didn't already leave room for) and the count is
    unchanged. Induct on the remaining timeline: an optimal solution exists
    that agrees with greedy everywhere, so greedy IS optimal.
    """
    raise NotImplementedError


def jump_game(nums: List[int]) -> bool:
    """True iff the last index is reachable. Empty / single element -> True.

    EXCHANGE ARGUMENT (safety of never over-jumping): reachability only ever
    grows — index j is reachable iff some reachable i < j has i + nums[i] >= j.
    So the single invariant "farthest reachable so far" is lossless: no choice
    was ever made, nothing to exchange. If the scan position passes farthest,
    no later index can become reachable and False is immediate.
    """
    raise NotImplementedError


def jump_game_min(nums: List[int]) -> int:
    """Minimum jumps to the last index; -1 if unreachable; 0 if len <= 1.

    EXCHANGE ARGUMENT: any optimal route's k-th jump lands somewhere within the
    greedy's k-th level (the set reachable in k jumps). Landing anywhere in
    the level leaves remaining reach at least as large as greedy's farthest
    frontier — so advancing level-by-level never forecloses an optimal route,
    and counting one jump per level is optimal.
    """
    raise NotImplementedError


def gas_station(gas: List[int], cost: List[int]) -> int:
    """Starting index completing the circuit, or -1 if none exists.

    EXCHANGE ARGUMENT (why skipping i..j is safe): if the tank starting at i
    goes negative first at j, then every start k in (i, j] arrives at j with
    <= the fuel starting-from-i had there — i accumulated non-negative surplus
    up to k, so dropping that surplus cannot help. Hence no station in i..j
    can complete the circuit; jump the candidate to j+1. If total gas >=
    total cost, this one pass always finds a valid start.
    """
    raise NotImplementedError


def task_scheduler(tasks: List[str], n: int) -> int:
    """Minimum intervals to run all tasks; identical tasks >= n apart.

    SIMULATION, not the formula: each tick, among tasks whose cooldown has
    expired, run the one with the largest remaining count (deterministic tie
    break: alphabetically first); idle if nothing is available.

    EXCHANGE ARGUMENT: if an optimal schedule runs some other available task
    where greedy runs the most-remaining task A, swap that slot's A-free
    window with a later A slot: feasibility is preserved (both tasks keep
    their cooldown gaps) and the makespan cannot grow — deferring the most
    frequent task is what forces idle tail slots, so running it first can only
    push the finish earlier or leave it unchanged.
    """
    raise NotImplementedError


def fractional_knapsack(capacity: float, items: List[Tuple[float, float]]) -> float:
    """Max value taking items (weight, value) whole or in fractions.

    EXCHANGE ARGUMENT: sort by value/weight ratio, take best-ratio weight
    first. Suppose OPT fills some capacity with lower-ratio material while a
    higher-ratio item has weight left. Swap one unit of OPT's material for
    one unit of the higher-ratio item: still feasible (same total weight),
    value strictly not worse. Induct: no optimal solution leaves a better
    ratio untaken — greedy is optimal. Divisibility is what lets the swap be
    measured in units; that is exactly what breaks in the 0/1 case.
    """
    raise NotImplementedError


def knapsack_01(capacity: int, items: List[Tuple[int, int]]) -> int:
    """Max value with indivisible items. DP — greedy FAILS here.

    WHY NO EXCHANGE ARGUMENT: items are atomic, so the fractional swap above
    cannot be performed "in units" — swapping one whole item for a fraction
    of another is infeasible, and swapping whole-for-whole can violate the
    capacity. A locally-best ratio can lock in a combination that cannot be
    repaired without dropping a whole item. See greedy_knapsack_01 below for
    the failure witness; DP explores both branches (take / skip) per item.
    """
    raise NotImplementedError


def greedy_knapsack_01(capacity: int, items: List[Tuple[int, int]]) -> int:
    """Ratio-greedy 0/1 knapsack — DELIBERATELY WRONG, kept as the witness.

    On capacity=50, items=[(10,60),(20,100),(30,120)]: ratios 6.0, 5.0, 4.0 —
    it takes (10,60)+(20,100)=160 and cannot fit (30,120), while the optimum
    is (20,100)+(30,120)=220. The exchange argument fails on the very first
    fixture the tests feed it. Its only job is to lose, provably.
    """
    raise NotImplementedError
