# Production notes — graph core

## Where this actually ships

- **Dependency graphs** — package managers (pip's resolver, cargo, go mod), build systems (Bazel/Buck2 target graphs), CI/CD pipelines. The graph is *directed* (A depends on B), and circular dependency = build failure. `has_cycle_directed`'s three-color scheme is exactly what a resolver runs before it starts installing; the gray set is "currently being resolved" — a back edge to a gray node is the circular-import error you've seen in Python: `ImportError: cannot import name X (most likely due to a circular import)`.
- **Network topology** — adjacency choice is the whole design. Routing tables and link-state protocols (OSPF) keep adjacency lists because a datacenter graph is sparse: ~10k switches, each with ~32-64 links. A matrix would be 10^8 cells to represent 300k real edges. Reachability in these fabrics is exactly `connected_components` with the outer-loop over the wiring graph.
- **Bipartite matching in ad allocation** — advertisers on one side, impressions/slots on the other; an "advertiser is eligible for impression" edge. The graph is bipartite *by construction*, and maximum bipartite matching (Hopcroft-Karp, built on your BFS layers) decides who wins each slot. `is_bipartite` is also the first move in timetable scheduling, volunteer shift assignment, and stable-matching problems.

## Why representation choice dominates performance at scale

| | adjacency list | adjacency matrix | CSR (flat arrays) |
|---|---|---|---|
| Space | O(V+E) | O(V^2) always | O(V+E), no pointers |
| Edge check | O(deg) | **O(1)** | O(log deg) binary search |
| Iterate neighbors | O(deg) | O(V) — mostly zeros | O(deg), **cache-friendly** |
| Build from edge list | O(E) | O(V^2) zero-fill | O(E) after counting sort |

Real graphs are sparse (E ≈ kV, k ≪ V): a social graph with 3B users averaging 300 connections has E ~ 10^12 — a matrix never enters the conversation. Matrix only wins when the *algorithm itself* is matrix-shaped: Floyd-Warshall's DP (V^2 state cells, O(1) edge check per relaxation) or dense flow networks — and only up to V in the low thousands before V^2 memory and O(V) neighbor scans lose. Past ~10^8 edges, pointer-chasing list-of-lists dies on cache misses: compressed sparse row (two flat arrays — offsets, then sorted neighbors) is what graph databases (Neo4j's fixed-width records, TigerGraph, GraphX/Pregel) and GNN input pipelines actually store.

## What the real libraries add over yours

- **CSR + relabeling** — order vertices by degree/partition so neighbor arrays share cache lines; NetworkX `G_adj = nx.to_scipy_sparse_array(G)` gets you there in two lines.
- **Incremental maintenance** — you rebuild the whole traversal per query; streaming systems (build graphs reacting to each new dependency edge) maintain the invariant instead. Union-Find (Lab 19) does connectivity incrementally; online topological order (Pearce-Kelly) does directed acyclicity.
- **Parallel traversal** — Frontier BFS (level-synchronous): all of layer d expands in parallel across cores, a synchronization point per layer. This is the Pregel/GraphX "think like a vertex" model.
- **Cycle reconstruction** — production needs the *path*, not the boolean: which modules form the circular dependency. The gray stack at the moment you find the back edge is the cycle.

## The 3 questions an interviewer asks after you describe this

1. *"100k vertices, 150k edges — list or matrix?"* — list. Sparse: matrix = 10^10 cells vs ~250k list entries. Matrix only re-enters if V is small (≤ a few hundred) AND you need O(1) edge checks or a matrix-shaped algorithm.
2. *"Why can't you use your undirected cycle detector on the dependency graph?"* — dependency graphs are directed. Undirected detection excludes the parent, which is wrong in a directed graph where A→B and B→A is a genuine 2-cycle; and binary visited flags a DAG's diamond convergence as a phantom cycle. Gray ≠ visited — that's the whole point of three colors.
3. *"Your build system must reject dependency edges that would create a cycle, one at a time. Re-run DFS per edge?"* — O(E) per insert, O(E^2) total. Options: Union-Find (undirected case, near-O(1) amortized — but it can't see direction), or incremental topological order (Pearce-Kelly), or a bounded reachability check DFS from the new edge's target back to its source.
