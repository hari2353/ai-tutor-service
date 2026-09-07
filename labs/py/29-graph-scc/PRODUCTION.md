# Production notes — SCC, bridges, articulation points, 2-SAT

## What you'd actually use

| Language | SCC / bridges / cut vertices | 2-SAT |
|---|---|---|
| Python | `networkx.strongly_connected_components`, `networkx.bridges`, `networkx.articulation_points` | `networkx` implication-graph recipe; `python-sat` (SAT solvers) for anything beyond 2-SAT |
| Java | JGraphT `KosarajuStrongConnectivityInspector` / `TarjanStrongConnectivityInspector` | JGraphT or a SAT4J wrapper |
| C++ | Boost Graph Library `strong_components` (Tarjan/Pearce), custom low-link for bridges | custom implication graph + SCC |
| Systems | SCC-based dependency analysis is built into build systems, linkers, deadlock detectors | small embedded 2-SAT solvers in schedulers and config validators |

**Do not hand-roll SCC for production graph analysis.** It is the interview answer. In a codebase that already pulls in `networkx` or BGL, use theirs — yours exists so you can explain theirs.

## Real systems built on exactly these four algorithms

- **Compiler optimization passes** — SCCs of the call graph or data-dependence graph are the unit of "things that must be processed together": cycle detection drives loop detection, recursion detection, and which functions get inlined or merged. The condensation DAG (dependencies between SCCs) is literally the build order.
- **Deadlock detection in task graphs** — a wait-for graph (transaction A waits on B, B on C, C on A) is cyclic exactly when those nodes share an SCC; database engines and OS deadlock detectors run cycle/SCC analysis on it. Bridges then mark the single points whose failure splits the task graph.
- **2-SAT in scheduling and config** — "each class goes in slot i OR slot j", "flag A on implies flag B off": pairwise constraints over booleans are 2-SAT, and feature-flag validators, timetabling tools and hardware EDA tools solve them by the millions. satisfiable = proceed; the SCC assignment even tells you a valid configuration.
- **Social network community detection** — SCCs (directed follow graphs) and biconnected components (undirected friendship graphs) are the "mutual" cores; bridges and articulation points are the single weak links whose removal fragments the network — the same analysis an SRE runs on the actual network topology.

## What production adds over yours

- **Recursion that does not exist** — every real implementation is iterative (explicit stacks) exactly like yours; the recursive textbook form is a teaching artifact that segfaults on deep graphs. Some (Boost, `networkx` via iterative helpers) also cap path lengths defensively.
- **Incremental / dynamic maintenance** — production dependency graphs change edge-by-edge (a commit adds an import). Fully dynamic SCC/bridges maintenance is an active research area; in practice systems re-run the static algorithm on a subgraph or tolerate stale answers with periodic full recomputes.
- **Parallel SCC** — large-scale SCC (web graphs) runs multi-pass, partition-parallel variants (e.g. the Forward-Backward algorithm of Fleischer et al.) across a cluster, because one sequential DFS cannot visit 50 billion nodes.
- **2-SAT vs real SAT** — a constraint system that grows one 3-literal clause is no longer 2-SAT and jumps from linear time to NP-complete. Production config/scheduling engines either keep the constraint shape 2-SAT as a hard invariant or pull in a DPLL/CDCL SAT solver where the SCC trick is just one propagation technique among many.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| `RecursionError` on deep chains | textbook recursive Tarjan | iterative DFS (the exact thing this lab forced) |
| SCC "result" changes run to run | unordered component output, callers relying on order | canonical sorted form, like this lab pins |
| A bridge failure splits prod traffic | nobody ran the analysis on the topology graph | run bridges/articulation points on the dependency/network graph; alert on new ones |
| 2-SAT solver suddenly explodes | one 3-literal clause crept in | keep the two-literal invariant, or switch to a real SAT solver consciously |
| Kosaraju "hangs" on huge graphs | two full passes + transpose build doubles memory | Tarjan single-pass, or parallel multi-pass SCC for cluster scale |

## Cost & latency

All four are O(V+E) — linear, off the hot path, run as analysis jobs (build time, deploy time, weekly topology audits), not per-request. The expensive part in production is never the algorithm; it is keeping the graph representation current (CSR-style flat arrays at millions of edges, not list-of-lists) and scheduling the recomputation.

## The 3 questions an interviewer asks after you describe this

1. *"Why does low[v] == disc[v] name an SCC root?"* — because everything v's subtree pushed above v on the component stack can reach v and be reached back; nothing can reach an earlier vertex, or low[v] would have dropped below disc[v].
2. *"Tarjan vs Kosaraju — which and why?"* — Tarjan: one pass, no transpose, and it emits SCCs in reverse topological order of the condensation for free (which 2-SAT exploits). Kosaraju: easier to prove and to remember under pressure. Both O(V+E); the honest answer is "Tarjan in code, Kosaraju on the whiteboard when correctness needs to be obvious".
3. *"Why is 2-SAT polynomial but 3-SAT not?"* — the implication graph's symmetry (a→b comes with not-b→not-a) is what makes "x and not-x in one SCC" a complete characterization of unsatisfiability. Three-literal clauses break the edge symmetry, and with it the whole reduction.
