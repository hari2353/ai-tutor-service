# Lab 27: Which Shortest-Path Algorithm When

**Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **XP:** 50
**Module:** `T02-graph-shortest`

**You will build:** the SELECTION logic — re-implement Dijkstra, Bellman-Ford and Floyd-Warshall compactly, then build an op-count model (`estimate_ops`) and a decision function (`choose_algorithm`) that encodes when each of the five candidates (Dijkstra, Bellman-Ford, Floyd-Warshall, A*, Johnson) is the right answer, plus a `compare_algorithms` harness that measures real runs with `time.perf_counter` (no sleeping — the implementations do actual work).

**You will be able to answer:** *"Negative weights — which algorithm, and why? All-pairs on 10⁵ nodes — why not Floyd-Warshall? Why does graph density change the op-count comparison but never your algorithm choice?"*

## Setup

```bash
cd labs/py/27-graph-shortest
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

1. **`dijkstra(graph, src)`** — single-source, non-negative weights. Returns `{node: dist}`. Must raise `ValueError` on a negative edge — never return silently-wrong distances.
2. **`bellman_ford(graph, src)`** — relax all edges `n-1` times. Returns `(dist, has_negative_cycle)`; the flag is True only for a cycle *reachable from src*.
3. **`floyd_warshall(graph)`** — all-pairs. Returns dict-of-dicts `dist[u][v]`; unreachable = `inf`, diagonal = 0. Handles negative edges (no negative cycle).
4. **`estimate_ops(algorithm, n, e)`** — the model behind every choice:
   | algorithm | ~ ops |
   |---|---|
   | dijkstra / a-star | `E·log₂(V)` |
   | bellman-ford | `V·E` |
   | floyd-warshall | `V³` |
   | johnson | `V·E + V·(E·log₂(V))` (BF reweight + Dijkstra per node) |
5. **`choose_algorithm(negative_weights, all_pairs, dense, n, heuristic_available)`** — decision rules, in order:
   1. negative + all-pairs → **johnson**
   2. negative, single-source → **bellman-ford** (Dijkstra is *wrong* on negatives, not slow)
   3. all-pairs, n ≤ 500 → **floyd-warshall** (V³ but heapless, five lines, done)
   4. all-pairs, n > 500 → **johnson** (V·E·log V beats V³ on sparse)
   5. single-source, non-negative, heuristic available → **a-star** (Dijkstra's bound, only shrunk)
   6. else → **dijkstra**

   `dense` **never changes the choice** — density moves the op-count comparison (FW looks better as E → V²) but not the decision. Say that sentence in an interview.
6. **`compare_algorithms(graphs)`** — for each named graph: `n`, `e`, estimated ops for the all-pairs workload for all five algorithms, and *measured* seconds (`time.perf_counter` around real runs: every source for the single-source ones, once for FW). No sleep, no faking.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Implement Johnson for real** — BF reweight with `h(v)` potentials, then Dijkstra per node; verify it matches FW on a 40-node negative-edge graph. *(Interview: "why is the reweighted graph non-negative?")*
2. **Bidirectional Dijkstra** — meet in the middle; halve the frontier. When does it *not* help? (Answer: when the heuristic already collapses it.)
3. **Empirical crossover finder** — binary-search the n where Johnson's estimate overtakes FW's on `E = 2V` vs `E = V²/2` graphs; check whether the measured times agree with the estimates in Python (spoiler: constant factors are unkind to FW here).
