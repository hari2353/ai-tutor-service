# Lab 19: Union-Find (Disjoint Set)

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p19-union-find`

**You will build:** a union-find with path compression + union by rank from scratch, then the five problems it unlocks: connected components, redundant edge in a graph (cycle detection), accounts merge, dynamic island counting, and Kruskal's MST as the flagship application.

**You will be able to answer:** *"Why does union-find with both optimizations make n operations run in almost-constant amortized time — and why is that the algorithm inside every MST, network, and merge tool?"*

## Setup

```bash
cd labs/py/19-union-find
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`UnionFind`** — `find(x)` with **path compression** (recursive or iterative: point every visited node straight at the root), `union(x, y)` with **union by rank** (smaller tree under the bigger). `union` returns True if a merge happened, False if already connected. Also expose: `connected`, `count` (number of disjoint sets), and `size(x)` (elements in x's set). Elements are `0..n-1`.
2. **`connected_components(n, edges)`** — return the number of components of an undirected graph on `n` nodes. Isolated nodes count.
3. **`redundant_connection(edges)`** — a graph with n nodes and n edges where exactly one extra edge makes a cycle: return **the last edge** in the input that can be removed to make a tree. (Process edges in order; the first edge that connects two already-connected nodes is it.)
4. **`accounts_merge(accounts)`** — `accounts = [name, email1, email2, ...]`; merge accounts that share any email; return merged groups as `[name, sorted emails...]` with groups sorted by name, then first email. Same person can appear multiple times with different names — the *emails* define identity.
5. **`number_of_islands_ii(m, n, positions)`** — dynamic land creation on an m×n grid; after each position is turned to land, report the island count. Repeated positions report the same count as before (no double-count). Return the full list of counts.
6. **`kruskal_mst(n, edges)`** — edges `(w, a, b)`; return (total_weight, mst_edge_list) using union-find cycle rejection; skip until n-1 edges accepted. If the graph is disconnected, return the weight of the *minimum spanning forest* and all accepted edges.
7. **`minimum_spanning_cost(n, edges)`** — just the total weight of the Kruskal forest covering all nodes.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Union by size vs rank** — implement both and articulate why size is what most libraries use (sz keeps subtree size = useful for `size(x)` queries).
2. **Weighted union-find (spanning forest with weights)** — maintain max-edge-on-path queries (the bottleneck-spanning-tree trick used in "minimax path" problems).
3. **Rollback union-find** — keep a stack of changes to support undo (offline dynamic connectivity).
4. **Bench against naive** — quadratic find (walk to root each time, no compression) vs yours at n=100k random unions; plot the gap.
