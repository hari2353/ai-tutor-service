# Production notes — shortest-path algorithms

## Where these actually run

| Algorithm | Real system |
|---|---|
| Dijkstra (+ A*, contraction hierarchies) | Road routing: OSRM, Google Maps preprocessing |
| Bellman-Ford variant (distance-vector) | BGP/OSPF route propagation semantics (RIP literally is distributed BF) |
| Floyd-Warshall | Small all-pairs: network simulation, transitive closure, dependency analysis |
| A* | Game pathfinding, robot motion planning, puzzle solvers |

## The interview selection matrix

| Situation | Choice |
|---|---|
| Non-negative weights, single source, sparse | Dijkstra, O(E log V) |
| Negative edges (currency arbitrage, toll credits) | Bellman-Ford, O(VE) |
| Negative cycle detection | BF's extra pass — also the arbitrage detection trick |
| All pairs, ≤ ~500 nodes | Floyd-Warshall, O(V³), dead simple |
| All pairs, sparse, large | Johnson (BF reweight + Dijkstra per node) |
| Grid/waypoint with admissible heuristic | A* |

## What breaks

| Symptom | Cause | Fix |
|---|---|---|
| Dijkstra silently returns wrong dists | Negative edge slipped in | Validate at entry; BF for negative graphs |
| A* returns suboptimal path | Heuristic not admissible (overestimates) | Prove admissibility or switch to weighted A* knowingly |
| A* expands the whole grid | Heuristic too weak (near 0) | Better heuristic; jump-point search on uniform grids |
| BF slow on big graphs | O(VE) inherent | SPFA queue-based variant helps in practice, worst case unchanged |
