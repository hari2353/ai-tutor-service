# Production notes — MST, max-flow, min-cut, matching

## What you'd actually use

| Language | Graphs / flow | Matching |
|---|---|---|
| Python | `networkx` (`minimum_spanning_tree`, `maximum_flow`, `minimum_cut`) | `scipy.sparse.csgraph.maximum_bipartite_matching` / `networkx.bipartite.hopcroft_karp_matching` |
| Java | JGraphT (`EdmondsKarpMaximumFlow`, `PushRelabel`, `DinicMaximumFlow`) | JGraphT `HopcroftKarpMaximumBipartiteMatching` |
| C++ | Boost Graph Library (`boykov_kolmogorov_max_flow`, `push_relabel_max_flow`) | Boost `hopcroft_karp_matching`? — no, BGL's `max_cardinality_matching` |
| Research | Near-linear max-flow (Chen et al. 2022) | not yet shipped in any mainstream library |

**Do not hand-roll Edmonds-Karp for production.** It is the interview answer, not the systems answer. Naming it as your production plan for a 10⁶-edge graph is a red flag; the follow-up "and then what?" must be Dinic or push-relabel.

## Real systems built on exactly these four algorithms

- **Network cable cost** — MST is literally the problem: connect all sites, minimize total cable. Prim's dense O(V²) variant when the sites are points in space (complete graph: E = V², and Kruskal's sort of V² edges at O(V² log V) loses to O(V²)).
- **Image segmentation (graph cut)** — Boykov-Kolmogorov min-cut: pixels are nodes, edges to "foreground"/"background" terminals with learned capacities, min cut = optimal segmentation. The BK algorithm inside is a max-flow variant tuned for this exact shape.
- **Ad allocation** — bipartite matching: advertisers on one side, impressions on the other; a real system runs it batched per time window and approximate in between (see below).
- **Logistics flow** — capacity-constrained routing was Ford-Fulkerson's original application (Soviet rail network, RAND Corporation, 1956). Today: freight, bandwidth planning, and evacuation modeling.

## What production adds over yours

- **Dinic's / Dinitz' algorithm** — O(V²E) general, and O(E√V) on unit-capacity graphs (which bipartite matching is). The default "real" answer when Edmonds-Karp's O(VE²) is too slow.
- **Push-relabel (highest-label, gap heuristic)** — often the fastest in practice on dense graphs; no repeated full-graph BFS from scratch, excess flows around locally instead.
- **Incremental / online matching** — real ride-hailing and ad platforms cannot re-solve a static graph per request. They run online heuristics with competitive-ratio guarantees, plus periodic batch re-optimization to correct accumulated drift — the hybrid is the senior-signal answer.
- **Near-linear max-flow (2022)** — theoretical frontier, not yet in production libraries; know it exists, don't claim to use it.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Edmonds-Karp "hangs" on 100k edges | O(VE²) BFS-per-augmentation | Dinic's layered graph, or push-relabel |
| Matching is too slow at scale | generic flow on the bipartite reduction | Hopcroft-Karp, or the online/batch hybrid |
| Min-cut side looks wrong | guessed from capacities, no final residual BFS | one reachability pass over the final residual graph — always |
| MST on points-in-space is slow | Kruskal on a complete graph | Prim dense O(V²), or Euclidean MST heuristics |
| Flow values huge (10⁹+) | integer-capacity phase-by-phase augmentation | scaling max-flow, or cost scaling for min-cost flow |

## Cost & latency

All four algorithms here are offline and exact. That is precisely what production *doesn't* run per-request: a matching decision in an ad auction has a sub-millisecond budget, so the flow/matching problem is solved approximately online and re-optimized in batches. The exactness you just built is the batch layer.

## The 3 questions an interviewer asks after you describe this

1. *"Why BFS? What breaks with DFS?"* — correctness holds either way (Ford-Fulkerson is a method), but DFS complexity depends on capacity *values*: the pathological case forces 2N augmentations for a max flow of 2N. BFS gives O(VE²) independent of magnitude. That bound is what "Edmonds-Karp" means.
2. *"Forget the reverse edges — what happens?"* — nothing crashes; the flow silently under-reports. The algorithm loses the ability to undo a suboptimal early assignment. It is the single most common max-flow bug because it doesn't fail loudly.
3. *"Matching at ride-hailing scale — Hopcroft-Karp?"* — no. Static offline exactness is the wrong shape for continuous arrivals; online matching with competitive ratios plus periodic batch re-solving is the architecture. Naming the hybrid is the signal.
