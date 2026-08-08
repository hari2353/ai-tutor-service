# Advanced Shortest Paths: Dijkstra, Bellman-Ford, Floyd-Warshall, A*

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** T02-p07-bfs, T02-p17-topological-sort
> **Module id:** `T02-adv-graphs` · **Tags:** advanced, graphs, shortest-path
> **Lab:** `labs/py/22-adv-graphs/`

## The 30-second version

Four algorithms answer four different questions and the decision is mechanical, not a matter of taste. Non-negative edge weights, single source, want the fastest correct answer: Dijkstra with a binary heap, O((V+E) log V). Negative edges present, single source, and you need to know if a negative cycle exists: Bellman-Ford, O(VE), which works by relaxing every edge V-1 times and catching a negative cycle on the Vth pass. All-pairs shortest paths on a dense graph: Floyd-Warshall, O(V^3), a three-line DP that also tolerates negative edges (not negative cycles). A single source, single destination, with a heuristic that estimates remaining distance: A*, which is Dijkstra with the priority reordered by `g(n) + h(n)` instead of `g(n)` alone, and is only optimal if `h` is admissible (never overestimates). The one-line decision rule: negative edges rule out Dijkstra and A* outright; all-pairs on a sparse graph should use Johnson's algorithm instead of Floyd-Warshall; a heuristic is the only reason to prefer A* over Dijkstra, and a bad heuristic makes A* both wrong and slow.

## Why this gets asked

It tests whether you actually understand *why* Dijkstra's greedy strategy works, not just that you memorized the heap-and-relax code. The failure mode interviewers have lived through is a routing or pricing system where someone dropped Dijkstra onto a graph that later grew a negative edge (a discount, a rebate, a synthetic arbitrage edge, a "refund" cost) and got silently wrong answers with no exception thrown — Dijkstra doesn't crash on negative edges, it just returns a value that's wrong, which is worse than crashing. It also tests whether you can reach for the right complexity class: using Floyd-Warshall's O(V^3) on a sparse million-node graph when Johnson's O(VE + V^2 log V) would run in a fraction of the time is a real production mistake, not just an academic one, because V^3 on V=10^4 is 10^12 operations.

---

## Lineage: past → present → future

**What came before.** Edsger Dijkstra designed his algorithm in 1956 (published 1959) to demonstrate shortest paths between 64 cities on the Dutch rail network for a magazine article, and it implicitly assumed non-negative distances because physical distances can't be negative — the algorithm was never designed to handle negative weights and its greedy correctness proof depends on that assumption. Bellman and Ford independently formalized the relaxation-based approach around 1956-1958, motivated by routing problems where edges could represent costs with rebates or penalties (negative contributions), and it became the basis of the RIP (Routing Information Protocol) distance-vector algorithm used in early internet routing. Before both, the only correct general approach was brute-force enumeration of paths or repeated BFS layer-by-layer, which is exponential the moment weights are involved and only tractable for unweighted graphs. Floyd-Warshall (Floyd, 1962) is a weighted adaptation of Stephen Warshall's 1962 transitive-closure algorithm and Kleene's earlier algorithm for converting finite automata to regular expressions — the same "route through an intermediate node k, increasing k from 1 to V" recurrence shows up in all three, which is why the DP derivation feels almost too simple once you see it.

**Where it stands now.** Binary-heap Dijkstra is the default in almost every production router, game engine, and interview answer; Fibonacci-heap Dijkstra achieves the theoretically better O(E + V log V) but is essentially never implemented in practice because its constant factors and implementation complexity lose to a binary heap for realistic V and E. A* dominates whenever a decent admissible heuristic exists — every modern GPS/mapping engine (OSRM, Google Maps' internal routing) uses A*-family algorithms with precomputed heuristics (contraction hierarchies, landmark-based A* / ALT) layered on top of the basic idea. For all-pairs shortest paths, Johnson's algorithm (reweight edges with a Bellman-Ford potential to eliminate negatives, then run Dijkstra from every vertex) is the correct answer for sparse graphs and is underused in interviews relative to how often it's the right production choice. There is a live, real disagreement about SPFA (Shortest Path Faster Algorithm), a queue-based optimization of Bellman-Ford popular in competitive programming: it's fast on average but its worst case is exponential on adversarial graphs, and several competitive-programming communities have formally recommended against using it in contests with adversarial test data for that reason.

**Where it's heading.** No new foundational shortest-path algorithm is expected — this is 1960s-complete mathematics with a stable proof structure. The active direction is in two places: incremental/dynamic shortest-path maintenance (D* Lite, Lifelong Planning A*) for graphs that change after the search has started, used in real-time robotics path replanning; and learned heuristics for A* (neural network-estimated remaining cost/ETA, as in production mapping-ETA models), which speeds up search without changing correctness as long as the learned heuristic is treated as inadmissible and the algorithm is allowed to re-expand nodes, or is calibrated to stay admissible. Treat the learned-heuristic direction as applied trivia for interviews (know it exists, know the admissibility tradeoff), not something you'll be asked to derive.

---

## Mental model

Dijkstra is water flooding outward from the source, always filling the currently-lowest basin next; once a node is "dry" (popped), its distance is final because everything still in the queue is at least as far.

```
Dijkstra frontier (non-negative weights):

        (5)---(9)
       /         \
   [S]             (D)
       \         /
        (2)---(4)

pop order by distance from S: S(0) -> left-2(2) -> left-4(6) -> D(via 4+4=10) or (via 9 path)
Once a node is popped its distance is final -- no edge can ever improve it,
because every remaining edge weight is >= 0, so no future relaxation can
produce a smaller number than what's already in the queue.
```

A* is the same flood, but biased: instead of ranking the queue by `g(n)` (distance so far), it ranks by `f(n) = g(n) + h(n)` where `h(n)` estimates the remaining distance to the goal. A perfect heuristic turns the search into a straight line to the goal; `h(n) = 0` for every node degenerates A* back into plain Dijkstra.

```
A* with straight-line heuristic on a grid, goal at bottom-right:
Dijkstra explores a circle around S.
A* explores an ellipse stretched toward the goal -- it wastes far less
time exploring nodes that are near S but far from the goal.
```

Bellman-Ford is the opposite of greedy: it doesn't trust any distance until it has relaxed every edge V-1 times, because with negative edges a "final" distance can still improve on pass 3, pass 4, etc. Floyd-Warshall is a three-nested-loop DP: `dist[i][j]` gets progressively refined by asking "is it shorter to go through intermediate vertex k?" for every k from 1 to V, in that specific outer-loop order.

---

## Recognition heuristics

- **"Shortest path from a single source, all weights positive"** → Dijkstra. This is the default; reach for it unless something below applies.
- **"Weights can be negative"** or **"detect if a negative cycle exists"** → Bellman-Ford (single source) or Floyd-Warshall/Johnson (all pairs). Dijkstra is disqualified the instant a negative edge is possible, even if none appears in the specific test case — the algorithm's correctness proof requires it globally.
- **"All pairs" / "shortest path between every pair of vertices"** on a small-to-medium dense graph (V ≤ ~500) → Floyd-Warshall, O(V^3), three lines of code, no data structure needed.
- **"All pairs" on a large sparse graph** → Johnson's algorithm, not Floyd-Warshall (see `T02-graph-shortest` for the reweighting derivation).
- **A known target, a grid or map, and a natural distance estimate available** (Euclidean, Manhattan, straight-line) → A*. The tell is a coordinate system or geometric layout in the problem, because that's what makes a heuristic possible.
- **"At most K edges/stops"** → this isn't plain Dijkstra even with non-negative weights; the state space needs `(node, stops_used)`, solved with a bounded/layered Bellman-Ford-style relaxation or BFS+DP (LC 787, Cheapest Flights Within K Stops).
- **"Currency arbitrage" / "is there a profitable cycle"** → Bellman-Ford on `-log(exchange_rate)` edges; a negative cycle in log-space is a multiplicative cycle greater than 1, i.e., an arbitrage opportunity.
- **Shortest path in a DAG** → neither Dijkstra nor Bellman-Ford is the fastest correct tool; topological sort + single relaxation pass is O(V+E), strictly faster, and handles negative weights for free since a DAG cannot have cycles at all.

---

## How it actually works — the correctness argument and why negative edges break it

Dijkstra's correctness rests on the **cut property**: when you pop the minimum-distance node `u` from the frontier, claim `dist[u]` is final. Proof sketch: any other path to `u` must at some point cross from the "settled" set to the "unsettled" set via some edge `(x, y)` with `y` unsettled; since all edge weights are non-negative, `dist[x] + w(x,y) >= dist[x] >= dist[u]` (because `u` was chosen as the minimum among unsettled nodes, and `x` is either settled with `dist[x] >= dist[u]`, or itself unsettled with `dist[x] >= dist[u]` by minimality). So no alternate path can beat `dist[u]`. The instant one edge weight can be negative, `dist[x] + w(x,y)` can be *less* than `dist[u]`, and the whole proof collapses — a path through a not-yet-relaxed negative edge can retroactively beat an already-popped "final" distance, and Dijkstra has already moved on and will never revisit it.

```
Counter-example: Dijkstra popped B with dist=2, called it final.
S --1--> A --(-5)--> B   (path S->A->B = 1-5 = -4)
S --2--> B                (Dijkstra takes this first: dist[B]=2, pop, done)
Real shortest path to B is -4, but Dijkstra already finalized dist[B]=2
and never looks at the S->A->B path again after popping B.
```

Bellman-Ford has no such shortcut: relax every edge `(u,v,w)` — `if dist[u] + w < dist[v]: dist[v] = dist[u] + w` — exactly `V-1` times. Why `V-1`? Because the shortest simple path between any two vertices has at most `V-1` edges (a simple path can't repeat a vertex), so after `V-1` full rounds of relaxing every edge, every shortest path has been fully propagated regardless of which order the edges happened to be processed in. Run one more (the `V`th) round: if any edge still relaxes, that improvement can only come from a negative cycle, since a real shortest simple path is already fully found.

Floyd-Warshall's recurrence is `dist[k][i][j] = min(dist[k-1][i][j], dist[k-1][i][k] + dist[k-1][k][j])` — "the shortest path from i to j using only intermediate vertices {1..k} is either the best path not using k at all, or the best path that goes through k." The loop order **must** be `k` outermost, then `i`, then `j` — swapping `k` inward breaks the DP because `dist[i][k]` and `dist[k][j]` on the right-hand side must already reflect all intermediates up to `k-1`, which is only guaranteed if the `k` loop has fully completed for all smaller values before `k` is used as an intermediate.

---

## Template code (Python, Java, Go)

```python
import heapq

# Dijkstra — non-negative weights, single source
def dijkstra(n: int, adj: list[list[tuple[int, int]]], src: int) -> list[float]:
    dist = [float('inf')] * n
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue  # stale entry, lazy deletion
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist

# Bellman-Ford — handles negative edges, detects negative cycles
def bellman_ford(n: int, edges: list[tuple[int, int, int]], src: int):
    dist = [float('inf')] * n
    dist[src] = 0
    for _ in range(n - 1):
        for u, v, w in edges:
            if dist[u] != float('inf') and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    for u, v, w in edges:  # Vth pass: detect negative cycle
        if dist[u] != float('inf') and dist[u] + w < dist[v]:
            return None, True  # negative cycle reachable from src
    return dist, False

# Floyd-Warshall — all-pairs, tolerates negative edges (no negative cycles)
def floyd_warshall(n: int, dist: list[list[float]]) -> list[list[float]]:
    for k in range(n):
        for i in range(n):
            if dist[i][k] == float('inf'):
                continue
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
    return dist

# A* — Dijkstra + admissible heuristic toward a known goal
def a_star(n: int, adj: list[list[tuple[int, int]]], src: int, goal: int, h) -> float:
    g = [float('inf')] * n
    g[src] = 0
    pq = [(h(src), src)]
    visited = set()
    while pq:
        f, u = heapq.heappop(pq)
        if u == goal:
            return g[u]
        if u in visited:
            continue
        visited.add(u)
        for v, w in adj[u]:
            ng = g[u] + w
            if ng < g[v]:
                g[v] = ng
                heapq.heappush(pq, (ng + h(v), v))
    return float('inf')
```

```java
import java.util.*;

public class ShortestPaths {

    // Dijkstra
    static double[] dijkstra(int n, List<List<int[]>> adj, int src) {
        double[] dist = new double[n];
        Arrays.fill(dist, Double.POSITIVE_INFINITY);
        dist[src] = 0;
        PriorityQueue<double[]> pq = new PriorityQueue<>((a, b) -> Double.compare(a[0], b[0]));
        pq.add(new double[]{0, src});
        while (!pq.isEmpty()) {
            double[] top = pq.poll();
            double d = top[0]; int u = (int) top[1];
            if (d > dist[u]) continue;
            for (int[] edge : adj.get(u)) {
                int v = edge[0], w = edge[1];
                double nd = d + w;
                if (nd < dist[v]) {
                    dist[v] = nd;
                    pq.add(new double[]{nd, v});
                }
            }
        }
        return dist;
    }

    // Bellman-Ford
    static double[] bellmanFord(int n, int[][] edges, int src, boolean[] hasNegCycle) {
        double[] dist = new double[n];
        Arrays.fill(dist, Double.POSITIVE_INFINITY);
        dist[src] = 0;
        for (int i = 0; i < n - 1; i++) {
            for (int[] e : edges) {
                int u = e[0], v = e[1], w = e[2];
                if (dist[u] != Double.POSITIVE_INFINITY && dist[u] + w < dist[v]) {
                    dist[v] = dist[u] + w;
                }
            }
        }
        hasNegCycle[0] = false;
        for (int[] e : edges) {
            int u = e[0], v = e[1], w = e[2];
            if (dist[u] != Double.POSITIVE_INFINITY && dist[u] + w < dist[v]) {
                hasNegCycle[0] = true;
                break;
            }
        }
        return dist;
    }

    // Floyd-Warshall
    static void floydWarshall(int n, double[][] dist) {
        for (int k = 0; k < n; k++) {
            for (int i = 0; i < n; i++) {
                if (dist[i][k] == Double.POSITIVE_INFINITY) continue;
                for (int j = 0; j < n; j++) {
                    if (dist[i][k] + dist[k][j] < dist[i][j]) {
                        dist[i][j] = dist[i][k] + dist[k][j];
                    }
                }
            }
        }
    }
}
```

```go
package main

import "container/heap"

type Item struct {
    dist float64
    node int
}
type PQ []Item

func (pq PQ) Len() int            { return len(pq) }
func (pq PQ) Less(i, j int) bool   { return pq[i].dist < pq[j].dist }
func (pq PQ) Swap(i, j int)        { pq[i], pq[j] = pq[j], pq[i] }
func (pq *PQ) Push(x interface{})  { *pq = append(*pq, x.(Item)) }
func (pq *PQ) Pop() interface{} {
    old := *pq
    n := len(old)
    item := old[n-1]
    *pq = old[:n-1]
    return item
}

const INF = 1e18

// Dijkstra
func dijkstra(n int, adj [][][2]int, src int) []float64 {
    dist := make([]float64, n)
    for i := range dist {
        dist[i] = INF
    }
    dist[src] = 0
    pq := &PQ{{0, src}}
    for pq.Len() > 0 {
        top := heap.Pop(pq).(Item)
        d, u := top.dist, top.node
        if d > dist[u] {
            continue
        }
        for _, e := range adj[u] {
            v, w := e[0], e[1]
            nd := d + float64(w)
            if nd < dist[v] {
                dist[v] = nd
                heap.Push(pq, Item{nd, v})
            }
        }
    }
    return dist
}

// Bellman-Ford
func bellmanFord(n int, edges [][3]int, src int) ([]float64, bool) {
    dist := make([]float64, n)
    for i := range dist {
        dist[i] = INF
    }
    dist[src] = 0
    for i := 0; i < n-1; i++ {
        for _, e := range edges {
            u, v, w := e[0], e[1], e[2]
            if dist[u] != INF && dist[u]+float64(w) < dist[v] {
                dist[v] = dist[u] + float64(w)
            }
        }
    }
    negCycle := false
    for _, e := range edges {
        u, v, w := e[0], e[1], e[2]
        if dist[u] != INF && dist[u]+float64(w) < dist[v] {
            negCycle = true
            break
        }
    }
    return dist, negCycle
}

// Floyd-Warshall
func floydWarshall(n int, dist [][]float64) {
    for k := 0; k < n; k++ {
        for i := 0; i < n; i++ {
            if dist[i][k] == INF {
                continue
            }
            for j := 0; j < n; j++ {
                if dist[i][k]+dist[k][j] < dist[i][j] {
                    dist[i][j] = dist[i][k] + dist[k][j]
                }
            }
        }
    }
}
```

## Complexity — derived, not asserted

**Dijkstra with a binary heap:** each of the `E` edges can trigger one `heappush` (O(log V)), and each of up to `E` heap entries can be popped once, so total work is `O((V + E) log V)`. The `dist[v] != inf` / stale-entry check (`if d > dist[u]: continue`) is what keeps this bound honest — without it, stale duplicate entries in the heap don't break correctness but do inflate the constant factor. A Fibonacci heap drops this to `O(E + V log V)` by making decrease-key O(1) amortized instead of O(log V), which matters asymptotically only when `E` is close to `V^2`; the implementation complexity is why almost nobody ships it.

**Bellman-Ford:** `V-1` full passes over all `E` edges, `O(VE)`. On a dense graph (`E ~ V^2`) this is `O(V^3)`, worse than Dijkstra by a full factor of `V` for the same graph — the price for tolerating negative edges.

**Floyd-Warshall:** three nested loops over `V`, `O(V^3)`, independent of `E` (it treats the graph as a dense adjacency matrix regardless of actual sparsity). This is why it's wrong for a sparse graph with large `V`: at `V = 10,000`, `V^3 = 10^12`, while Johnson's `O(VE + V^2 log V)` on a sparse graph (`E ~ V`) is closer to `10^8`, four orders of magnitude faster.

**A*:** worst case identical to Dijkstra, `O((V+E) log V)`, achieved when `h(n) = 0` everywhere (degenerates to Dijkstra) or the heuristic is uninformative. With a good admissible heuristic the number of nodes actually expanded can be dramatically smaller — the complexity bound doesn't capture the practical speedup, which is graph- and heuristic-dependent and not expressible as a clean asymptotic improvement.

---

## The 5 variants interviewers actually ask

1. **Network Delay Time (LC 743).** Plain single-source Dijkstra, non-negative weights, answer is the max over all `dist[v]` (or -1 if any node unreachable). The baseline check that you can write Dijkstra correctly from scratch.
2. **Cheapest Flights Within K Stops (LC 787).** Looks like Dijkstra but isn't — the state isn't just "node," it's "(node, stops used)," because a longer path with more stops can be cheaper and must still be considered even after a cheaper-but-more-hops path to the same node is known. Solve with a bounded Bellman-Ford (relax at most `K+1` times, using a snapshot of distances from the previous round so you don't use an edge relaxed earlier in the *same* round) or BFS with a priority queue keyed on `(cost, stops)`.
3. **Currency Arbitrage / Evaluate Division with a profit cycle.** Transform each edge weight `rate(u,v)` into `-log(rate(u,v))`; a negative cycle in this transformed graph means the product of rates around the cycle exceeds 1, i.e., a profitable arbitrage loop. Run Bellman-Ford and check the extra relaxation pass.
4. **All-Pairs Shortest Paths on a small dense graph (city-distance matrix, ≤ a few hundred nodes).** Floyd-Warshall, three lines, and be ready to explain why you didn't choose Johnson's (answer: graph is dense/small enough that `V^3` is fine and Johnson's added complexity buys nothing).
5. **Grid pathfinding with obstacles, known start and goal (Shortest Path in Binary Matrix / robot navigation).** A* with Manhattan or Euclidean distance as `h`, or Dijkstra if no natural heuristic is stated. Common follow-up: prove the Manhattan-distance heuristic is admissible for 4-directional movement (it never overestimates because every step changes exactly one coordinate by 1, so Manhattan distance is a lower bound on steps needed) but is *not* automatically admissible for 8-directional or weighted diagonal movement without rescaling (Chebyshev or octile distance instead).

---

## Common bugs and how this gets written wrong under pressure

- **Running Dijkstra on a graph that "probably" has no negative edges.** The correctness proof requires non-negative weights as a hard precondition, not a property of the specific test case; if the problem statement doesn't guarantee non-negative weights, Dijkstra is the wrong algorithm even if it happens to produce the right answer on the sample input.
- **Off-by-one in Bellman-Ford's pass count.** Relaxing `V` times instead of `V-1` before checking for a negative cycle silently masks the detection (the check itself needs to be the *extra*, distinguishable pass) — or relaxing only `V-2` times under-propagates and returns wrong distances on a legitimately negative-edge (but cycle-free) graph.
- **Floyd-Warshall with the loop order wrong.** Putting `i` or `j` as the outermost loop instead of `k` produces a plausible-looking but incorrect DP, because it uses `dist[i][k]` or `dist[k][j]` values that haven't been fully updated for all intermediates less than `k` yet. This is the single most common Floyd-Warshall bug and it doesn't crash — it just returns numbers that are wrong for graphs where the correct path actually needs multiple intermediate hops.
- **Forgetting the stale-entry check in heap-based Dijkstra.** Without `if d > dist[u]: continue`, the algorithm still terminates with the correct answer (because relaxation is monotonic), but it does redundant work reprocessing every stale heap entry, which matters when graders time the solution.
- **Using an inadmissible heuristic in A* and still claiming optimality.** If `h(n)` ever overestimates the true remaining distance for any node, A* can return a suboptimal path; a heuristic that's admissible but not *consistent* (monotonic) can still be optimal but may require reopening already-visited nodes, which many textbook A* implementations silently omit.
- **Integer/float overflow in `INF` arithmetic.** Using `sys.maxsize` or `Integer.MAX_VALUE` as infinity and then adding an edge weight to it overflows into a negative or wrapped value in fixed-width languages (Java/Go `int`), producing a smaller-than-real "distance" that then wins comparisons it shouldn't. Guard every relaxation with an explicit "is this endpoint still unreached" check before adding, as the templates above do.

---

## Interview questions

### Q1 — Network Delay Time (LC 743): find the time for a signal to reach all nodes from a source.
**Testing:** can you write correct Dijkstra from scratch, including the answer being the max finite distance or -1.
**Answer:** Standard Dijkstra with a min-heap; the answer is `max(dist)` if all nodes are reachable, else -1.
**Follow-up trap:** *"What if some edge weights could be negative?"* — Dijkstra is no longer valid; you'd need Bellman-Ford, accepting the O(VE) cost.

### Q2 — Cheapest Flights Within K Stops (LC 787).
**Testing:** recognizing that the state space is bigger than "node" alone.
**Answer:** Bounded Bellman-Ford: relax all edges at most `K+1` times using distances frozen from the start of the round (a copy), since using an edge already relaxed in the same round would let a path silently exceed the stop limit.
**Follow-up trap:** *"Why can't you just run Dijkstra and stop early once you've used K edges?"* — because a cheaper-but-more-hops path to an intermediate node might be pruned by Dijkstra's greedy finalization before you realize it leads to a cheaper overall path within the stop budget; the stop count is part of the state, not a side constraint you can bolt onto vanilla Dijkstra.

### Q3 — Construct a graph where Dijkstra gives the wrong answer.
**Testing:** do you actually understand the cut-property proof, not just the code.
**Answer:** `S->B` weight 2, `S->A` weight 1, `A->B` weight -5. Dijkstra pops B at distance 2 (finalizing it) before relaxing the `S->A->B` path, which totals -4.
**Follow-up trap:** *"What's the minimum change to the algorithm that would fix this specific case?"* — there isn't a cheap patch; you need a fundamentally different algorithm (Bellman-Ford) because the greedy finalization step itself is the flaw, not a bug in the relaxation code.

### Q4 — Detect whether a negative cycle exists in a weighted directed graph.
**Testing:** the extra-pass technique and why V-1 passes alone aren't the detector.
**Answer:** Run Bellman-Ford for V-1 passes, then run one more pass; if any edge still relaxes, a negative cycle is reachable from the source.
**Follow-up trap:** *"What if the negative cycle isn't reachable from your chosen source?"* — you won't detect it; you'd need to run from every unvisited component or add a virtual source connected to all nodes with 0-weight edges to guarantee reachability.

### Q5 — Currency Arbitrage: given exchange rates between currencies, is there a sequence of trades that yields free profit?
**Testing:** the log-transform trick and mapping "arbitrage" to "negative cycle."
**Answer:** Build edges with weight `-log(rate(u,v))`; a negative cycle means the product of rates around the loop exceeds 1. Run Bellman-Ford and check the extra pass.
**Follow-up trap:** *"Why not just multiply rates directly and check for a product > 1?"* — multiplying accumulates floating-point error across many edges and doesn't compose additively, so it can't reuse the standard shortest-path relaxation machinery; the log transform turns a multiplicative problem into an additive one that Bellman-Ford already solves.

### Q6 — All-pairs shortest paths on a graph with a few hundred nodes.
**Testing:** knowing Floyd-Warshall as the default answer at this scale, and being able to justify the choice against alternatives.
**Answer:** Floyd-Warshall, O(V^3), three nested loops with `k` outermost.
**Follow-up trap:** *"What if V were 50,000 and the graph sparse?"* — Floyd-Warshall's O(V^3) becomes computationally infeasible; switch to Johnson's algorithm, O(VE + V^2 log V), which reweights edges via one Bellman-Ford pass to remove negatives, then runs Dijkstra from every vertex.

### Q7 — Implement A* for grid pathfinding with a known goal.
**Testing:** whether you understand `f = g + h` and can justify heuristic choice.
**Answer:** Priority queue keyed on `g(n) + h(n)`; for 4-directional grid movement, Manhattan distance is a valid admissible heuristic.
**Follow-up trap:** *"Is Manhattan distance still admissible if diagonal movement is allowed?"* — no, it can overestimate along diagonals; use Chebyshev or octile distance instead, which correctly account for the cheaper diagonal step.

### Q8 — Shortest path using at most K edges (not necessarily fewer stops than optimal).
**Testing:** the same bounded-relaxation idea as Q2 in a more general form.
**Answer:** Run Bellman-Ford-style relaxation for exactly `K` rounds using a frozen copy of distances from the prior round, tracking the best distance found within the budget.
**Follow-up trap:** *"Can this ever be worse than running unrestricted Bellman-Ford?"* — no in terms of answer correctness (it's a strict subproblem), but it's a different problem: the unrestricted shortest path might use fewer than K edges anyway, so the K-bounded run must still consider all path lengths up to K, not exactly K.

### Q9 — Single-source shortest path in a DAG.
**Testing:** whether you reach for the fastest correct tool instead of defaulting to Dijkstra out of habit.
**Answer:** Topological sort, then relax edges in topological order in a single pass, O(V+E). This works even with negative edges because a DAG has no cycles to worry about, so there's no analogue of Dijkstra's greedy-finalization flaw.
**Follow-up trap:** *"Why is this strictly better than Dijkstra here?"* — Dijkstra pays O((V+E) log V) for a heap it doesn't need; the DAG's topological order already guarantees that every predecessor of a node is fully processed before the node itself, making the heap redundant.

### Q10 — Why is Fibonacci-heap Dijkstra almost never used despite the better asymptotic bound?
**Testing:** whether you understand the gap between asymptotic and practical performance.
**Answer:** Fibonacci heaps have poor constant factors and complex, error-prone implementations (lazy consolidation, cascading cuts); the `O(E + V log V)` bound only wins over binary-heap's `O((V+E) log V)` when `E` approaches `V^2` (dense graphs), and most real-world graphs are sparse, where the difference is negligible in practice while the implementation risk is not.
**Follow-up trap:** *"Name a real system where the Fibonacci-heap version would actually matter."* — extremely dense flow networks or certain academic benchmark instances; in practice, most engineers should never reach for it.

### Q11 — What's SPFA and why do many competitive programmers avoid it?
**Testing:** awareness of the queue-based Bellman-Ford variant and its risk profile.
**Answer:** SPFA only re-relaxes edges from nodes whose distance actually changed, using a queue instead of blindly looping over all edges V-1 times; average case is much faster than classic Bellman-Ford.
**Follow-up trap:** *"What's its worst case?"* — it degrades to the same O(VE) as classic Bellman-Ford, and specific adversarial graph constructions (well known in competitive programming, notably from Chinese OI communities) can force that worst case deliberately, so contest judges with adversarial data can make SPFA time out where classic Bellman-Ford would not.

### Q12 — Difference between an admissible and a consistent (monotonic) heuristic in A*, and why it matters.
**Testing:** depth beyond "just don't overestimate."
**Answer:** Admissible means `h(n)` never overestimates the true cost to the goal. Consistent (monotonic) means `h(n) <= cost(n, n') + h(n')` for every edge — a stronger, triangle-inequality-like condition. Consistency guarantees that once a node is popped from the priority queue its `g` value is already optimal, so A* never needs to reopen a node, behaving exactly like Dijkstra's finalization guarantee. Admissible-but-inconsistent heuristics can still find the optimal path but may require reopening nodes already marked visited, which many naive implementations forget to allow.
**Follow-up trap:** *"Give a heuristic that's admissible but not consistent."* — a heuristic with a sudden large drop between two adjacent nodes that's still individually below the true remaining distance from each node satisfies admissibility per-node but violates the edge-wise triangle inequality; concretely, a heuristic table with `h(A)=10, h(B)=1` connected by an edge of weight 2 is admissible at both nodes individually (if true remaining costs are ≥10 and ≥1) but inconsistent since `h(A) > cost(A,B) + h(B)` (10 > 2+1).

---

## Red flags that fail you

- Running Dijkstra on a graph without checking (or asking) whether negative edges are possible.
- Not knowing that Bellman-Ford's negative-cycle detection requires an *extra* relaxation pass beyond the V-1 needed for correctness.
- Getting Floyd-Warshall's loop order wrong (`k` must be outermost) and not noticing the DP is broken.
- Claiming A* is "just faster Dijkstra" without mentioning the heuristic must be admissible for optimality to hold.
- Defaulting to Floyd-Warshall for all-pairs on a large sparse graph instead of Johnson's algorithm.
- Not knowing why a DAG shortest path doesn't need Dijkstra or Bellman-Ford at all.

---

## Cheat card

```
DIJKSTRA       non-neg weights, single source, O((V+E) log V) binary heap
               fails on negative edges -- greedy finalization proof breaks
BELLMAN-FORD   handles negative edges, O(VE), relax V-1 times + 1 extra pass
               to detect a negative cycle
FLOYD-WARSHALL all-pairs, O(V^3), k MUST be outermost loop, tolerates
               negative edges (not negative cycles)
JOHNSON'S      all-pairs on sparse graphs, O(VE + V^2 log V), reweight via
               Bellman-Ford potential then Dijkstra from every vertex
A*             Dijkstra + heuristic, f(n) = g(n) + h(n), optimal iff h
               admissible (never overestimates); consistent h avoids reopening
DAG SSSP       topo sort + one relax pass, O(V+E), beats both above on a DAG
ARBITRAGE      edge weight = -log(rate); negative cycle = profitable loop
K-STOPS        state = (node, stops used); bounded relax with frozen snapshot
WATCH          stale heap entries (check d > dist[u]); INF + w overflow;
               inadmissible heuristic silently breaks A* optimality
```

## Sources

- [Dijkstra's Algorithm — CLRS-style reference, GeeksforGeeks](https://www.geeksforgeeks.org/dsa/dijkstras-shortest-path-algorithm-greedy-algo-7/) — accessed 2026-07-26
- [Bellman-Ford Algorithm](https://www.geeksforgeeks.org/dsa/bellman-ford-algorithm-dp-23/) — accessed 2026-07-26
- [Floyd-Warshall Algorithm](https://www.geeksforgeeks.org/dsa/floyd-warshall-algorithm-dp-16/) — accessed 2026-07-26
- [A* Search Algorithm](https://www.geeksforgeeks.org/dsa/a-search-algorithm/) — accessed 2026-07-26
- [Network Delay Time — LeetCode](https://leetcode.com/problems/network-delay-time/) — accessed 2026-07-26
- [Cheapest Flights Within K Stops — LeetCode](https://leetcode.com/problems/cheapest-flights-within-k-stops/) — accessed 2026-07-26
- Hart, Nilsson, Raphael, "A Formal Basis for the Heuristic Determination of Minimum Cost Paths," IEEE Transactions on Systems Science and Cybernetics, 1968 (original A* paper)

## Changelog
- 2026-07-26 — created
