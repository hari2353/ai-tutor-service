# Production notes — which shortest-path algorithm when

## The real decision table

| Situation | What production systems actually call |
|---|---|
| Road routing (OSRM, Valhalla, Google Maps) | Contraction hierarchies / Hub Labelling — precomputed shortcuts; plain Dijkstra hasn't been "it" at scale for a decade. A* only at the query layer. |
| Network routing protocols | Distance-vector protocols (RIP) literally are distributed Bellman-Ford — that's where the "count to infinity" problem comes from. OSPF/IS-IS use Dijkstra (link-state, weights are admin costs ≥ 0). BGP is path-vector, a BF cousin that carries full paths to kill loops. |
| Arbitrage detection in finance | Bellman-Ford on `-log(rate)` edge weights. A negative cycle **is** an arbitrage. Same math for detecting profitable FX cycles — the extra relaxation pass is the entire product feature. |
| Small all-pairs (n ≤ 500): dependency analysis, network simulation, transitive closure | Floyd-Warshall. Dead simple, dense-matrix friendly, V³ at n=500 is ~1.25e8 inner steps — fine in C, and even in Python for one-off batch jobs. |
| All-pairs on big sparse graphs | Johnson (BF reweight + Dijkstra per node), or just V parallel Dijkstra runs and move on with your day. |
| Game pathfinding / robotics | A* (often with jump-point search on uniform grids), or Dijkstra/LPA* when there's no good heuristic. |

## When production just calls Dijkstra and eats the constraints

The most common real-world answer. Road networks are *made* non-negative (negative edge weights in routing are usually a modeling bug), so the negative-weight branch of the decision tree simply never fires in that domain. Dijkstra with a binary heap is ~40 lines, has 60 years of battle-testing, every graph library has it tuned — so engineers spend their complexity budget elsewhere (preprocessing, contraction hierarchies) rather than on the base algorithm. **The lesson:** the algorithm-choice interview question is really asking *do you know which constraints you can assume away in your domain*.

## What the real ones add over yours

- **Fibonacci heaps / pairing heaps** — the textbook O(E + V·log V) Dijkstra. In practice binary heaps win on constants; nobody ships Fibonacci heaps.
- **Contraction hierarchies (CH)** — preprocess road networks for hours, answer queries in microseconds. The speedup is 3-4 orders of magnitude over plain Dijkstra; this is what "Google Maps is fast" actually is.
- **Dial's algorithm** — bucket queues for small integer weights: O(E) Dijkstra, used in real routers.
- **Delta-stepping** — parallel Dijkstra for GPUs; the graph-parallel variant that actually parallelizes.

## What breaks

| Symptom | Cause | Fix |
|---|---|---|
| Dijkstra returns wrong distances silently | A negative edge got in (a "discount" or "credit" edge in the domain model) | Validate weights at entry (raise, like your lab does) or model with BF/JSPF |
| Bellman-Ford "too slow" on huge graphs | O(V·E) is inherent | SPFA/queue-based variant helps in practice (not worst case); or reweight once with one BF pass + Dijkstra per node = Johnson |
| Floyd-Warshall OOMs | V² doubles/floats: 10⁵ nodes = 10¹⁰ cells | That's the n ≤ 500 rule doing its job — switch to Johnson or V Dijkstras |
| A* slower than Dijkstra | Heuristic is ~0 (uniform-cost in disguise) or the priority-queue churn dominates | Stronger admissible heuristic; or just use Dijkstra |
| A* returns suboptimal paths | Heuristic not admissible (overestimates) | Prove admissibility (Manhattan on 4-grids is) or knowingly accept weighted A* |

## The 3 questions an interviewer asks after you describe this

1. *"Why is Dijkstra *wrong* and not just slow on negative edges?"* — greedy finalization: once a node pops with min distance it is never revisited, but a later negative edge could improve it. BF fixes this by never finalizing until all passes complete.
2. *"All-pairs on 10⁵ nodes — Floyd-Warshall?"* — V³ = 10¹⁵ ops and V² = 10¹⁰ cells of memory: no. Johnson (sparse) or V Dijkstras; on road networks, precomputed hierarchies.
3. *"You have a grid, why A* and not Dijkstra?"* — an admissible heuristic only prunes Dijkstra's search, never worsens it; Manhattan on a 4-connected grid collapses the frontier from O(V) to O(path length). But with no heuristic domain knowledge, Dijkstra is A* with h ≡ 0 — same code.
