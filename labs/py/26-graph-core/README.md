# Lab 26: Graph Representations, Traversals, Cycles, Bipartiteness

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-graph-core`

**You will build:** conversions between the three graph representations, BFS and DFS with exact visit-order guarantees, connected components, undirected (parent-tracking) and directed (three-color) cycle detection, bipartite 2-coloring, and the handshake-lemma degree check — all as pure functions over adjacency lists.

**You will be able to answer:** *"Walk me through BFS and DFS on this graph and give me the exact visit order — and why are undirected and directed cycle detection genuinely different algorithms?"*

## Setup

```bash
cd labs/py/26-graph-core
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

`graph` always means an adjacency list `list[list[int]]` where **bucket order is insertion order** (it matters — the tests pin it). `edges` are 2-tuples `(u, v)` or weighted 3-tuples `(u, v, w)`; `matrix` is `list[list[int]]`. All functions are pure — never mutate the input. Everything must handle disconnected graphs and self-loops.

1. **`to_adjacency_list(n, edges, directed=False)`** — 0-indexed buckets; undirected by default, so each edge lands in both buckets in input order (a self-loop `(u, u)` therefore appears **twice** in its own bucket). `to_adjacency_matrix(n, edges, directed=False)` — the cell holds the **weight** (`w` from a 3-tuple, `1` from a 2-tuple), not always 1. `to_edge_list(matrix, directed=False, weighted=False)` — skip zero cells; undirected scans the upper triangle **including the diagonal** (self-loops survive) in row-major order; directed scans every cell; `weighted=True` yields `(i, j, w)` triples. The three conversions round-trip: edges → matrix → edge list → matrix is the identity.
2. **`bfs_order(graph, src)`** — FIFO queue; mark a node **when you enqueue it** (never twice); expand neighbors in insertion order. Returns the exact visit list — only `src`'s component appears.
3. **`dfs_order(graph, src)`** — explicit stack, **no recursion**; mark a node **when you pop it**; if a popped node is already marked, skip it. Push neighbors in **reverse** insertion order so the visit order equals **recursive preorder** — that equality is the invariant, and the tests check it against a recursive reference.
4. **`connected_components(graph)`** — outer loop over every vertex, one BFS/DFS per unvisited vertex; each component returned **sorted ascending**, and the list of components sorted too.
5. **`has_cycle_undirected(graph)`** — DFS tracking the parent: a visited neighbor that is **not the vertex you came from** is a cycle. Outer loop over all vertices. Self-loops and parallel edges are cycles.
6. **`has_cycle_directed(graph)`** — three-color DFS (white unvisited / gray on the current path / black finished). An edge to a **gray** node (back edge, active ancestor) is a cycle; an edge to a **black** node (finished branch, DAG convergence like a diamond) is fine. Outer loop over all vertices.
7. **`is_bipartite(graph)`** — BFS 2-coloring with the outer loop; returns `(True, coloring)` where `coloring` maps node → 0/1 (the first vertex of each component gets 0), or `(False, None)` on a color conflict. Isolated vertices are trivially colorable. Odd cycle ⇒ False, even cycle ⇒ True.
8. **`degree_sum(graph)`** — sum of bucket lengths. Handshake lemma: for any undirected graph this equals **2 × the edge count** (a self-loop contributes 2).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **BFS layers** — return `dist[]` next to the order; every node's first discovery is its shortest unweighted distance. *(Interview: "shortest path in an unweighted graph — why not Dijkstra?")*
2. **Name the cycle** — the three-color DFS naturally identifies the back edge; return the nodes of the cycle, not just True. *(Interview: "your build failed with a circular dependency — which modules are in it?")*
3. **Multi-source BFS** — seed the queue with all sources at distance 0 and prove one pass beats k per-source passes. *(Interview: LC "rotting oranges" — where does the layer invariant still hold?)*
4. **CSR representation** — flat arrays (`offsets[] + neighbors[]`) instead of list-of-lists; bench iteration at n=200k. *(Interview: "how do graph databases store billions of edges?")*
