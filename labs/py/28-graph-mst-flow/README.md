# Lab 28: MST, Max-Flow, Min-Cut, Matching

**Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **XP:** 50
**Module:** `T02-graph-mst-flow`

**You will build:** Kruskal's and Prim's MST, Edmonds-Karp max-flow with residual graphs, min-cut reconstruction, and bipartite matching as a max-flow reduction — all in one `mstflow.py`, pure stdlib.

**You will be able to answer:** *"Kruskal or Prim — and why? Then implement max-flow and tell me why BFS for augmenting paths and reverse residual edges are both non-negotiable. Why is bipartite matching 'just' max-flow?"*

## Setup

```bash
cd labs/py/28-graph-mst-flow
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

1. **`UnionFind(n)`** — find with path compression, union by rank. `.union(a, b)` returns `True` if merged, `False` if already same set; `.connected(a, b)` queries.
2. **`kruskal_mst(n, edges)`** — sort all `(w, u, v)` edges, greedily keep each unless Union-Find says cycle. Returns `(mst_edges, total_weight)`. Disconnected input → the spanning **forest** of every component.
3. **`prim_mst(n, edges, start=0)`** — grow one tree from `start` via a min-heap of crossing edges. Returns `(mst_edges, total_weight)` covering only `start`'s component.
4. **`edmonds_karp(n, capacity, s, t)`** — BFS shortest augmenting paths on the residual graph; update forward **and reverse** edges every augmentation. Must not mutate `capacity`. Returns `(max_flow_value, flows)` with `flows[u][v]` = net flow (negative on reverse).
5. **`min_cut(n, capacity, s, t)`** — run max-flow, then one more traversal from `s` over the final residual graph. Returns `(cut_value, source_side)`; `cut_value == max_flow` by the theorem, and `source_side`'s crossing capacity in the *original* matrix equals it.
6. **`bipartite_matching(n_left, n_right, edges)`** — build `source → left → right → sink` with all capacities 1 and call `edmonds_karp`. Returns the matching size.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Kahn-free cycle rejection?** Prove from the cut property why Kruskal's greedy is safe at the moment it accepts an edge — what exactly is the cut, and what is the exchange argument? *(Interview: "prove Kruskal correct")*
2. **Dinic's algorithm** — layered BFS + blocking flow; verify it returns the same values as Edmonds-Karp on all fixtures and random matrices. *(Interview: "what does production actually use instead of Edmonds-Karp?")*
3. **Hopcroft-Karp** — replace the flow reduction with per-phase vertex-disjoint shortest augmenting paths; check it matches `bipartite_matching` everywhere and name its bound. *(Interview: "how do you speed matching up at scale?")*
4. **Push-relabel** — highest-label with gap heuristic; the answer when capacities are huge and BFS phases become the bottleneck. *(Interview: "why is O(VE²) the wrong tool for big dense graphs?")*
