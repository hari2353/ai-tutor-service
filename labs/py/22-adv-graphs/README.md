# Lab 22: Shortest-Path Algorithms From Scratch

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-adv-graphs`

**You will build:** Dijkstra, Bellman-Ford, Floyd-Warshall, and A* — four shortest-path algorithms, each with the property that makes it the right choice somewhere.

**You will be able to answer:** *"Negative weights — why does Dijkstra break, what does Bellman-Ford actually do about it, and when is Floyd-Warshall the right answer despite O(n³)?"*

## Setup

```bash
cd labs/py/22-adv-graphs
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

1. **`dijkstra(graph, src)`** — single-source shortest paths, non-negative weights only. Returns `{node: dist}`. Use a heap with lazy deletion (push duplicates, skip stale). Must raise `ValueError` on a negative edge.
2. **`bellman_ford(graph, src)`** — relax all edges `n-1` times. Returns `(dist, has_negative_cycle)` — one extra relaxation pass detects a reachable negative cycle.
3. **`floyd_warshall(graph)`** — all-pairs. Input is the full node set + weighted adjacency. Returns a matrix (list of lists) of `dist[i][j]`; unreachable = `float('inf')`, diagonal = 0.
4. **`a_star(grid, start, goal, heuristic)`** — shortest path on a 2D grid of 0/1 (1 = wall), 4-directional moves, heuristic injected (tests use Manhattan). Returns `(path, cost)` where path is the list of cells. Must be optimal given an admissible heuristic.

## Run the tests

```bash
pytest tests/ -v          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Bidirectional Dijkstra** — meet in the middle; halve the frontier. *(Interview: "when does bidirectional search not help?")*
2. **Johnson's algorithm** — BF to reweight + Dijkstra per node = all-pairs on sparse graphs faster than FW. *(Interview: "all-pairs on 10⁵ nodes?")*
3. **A* with a weighted heuristic** — show it loses optimality and gains speed; measure node expansions.
