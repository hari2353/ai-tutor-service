# Shortest Paths, Deep Dive: Johnson's Algorithm and the Full Decision Framework

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** T02-adv-graphs, T02-graph-core
> **Module id:** `T02-graph-shortest` · **Tags:** graphs, critical, shortest-path

## The 30-second version

`T02-adv-graphs` covers the four workhorse algorithms and the basic decision rule; this module goes one level deeper on the two things that actually separate a strong answer from a memorized one: precisely *why* Dijkstra's greedy invariant is destroyed by a single negative edge (not just "it doesn't work," but the exact point in the correctness proof that fails), and Johnson's algorithm — the correct tool for all-pairs shortest paths on a sparse graph with possibly-negative edges, which almost nobody derives correctly live because it requires composing two algorithms via a non-obvious reweighting trick. Johnson's algorithm adds a virtual source connected to every vertex with 0-weight edges, runs Bellman-Ford once from it to get a potential `h(v)` for every vertex, reweights every edge as `w'(u,v) = w(u,v) + h(u) - h(v)` (provably non-negative if no negative cycle exists), then runs Dijkstra from every vertex on the reweighted graph and converts distances back with `dist(u,v) = dist'(u,v) - h(u) + h(v)`. Total cost: `O(VE + V^2 log V)`, strictly better than Floyd-Warshall's `O(V^3)` the moment the graph is sparse (`E` closer to `V` than `V^2`), which is most real graphs. The decision framework in one sentence: non-negative + single source → Dijkstra; negative edges + single source → Bellman-Ford; all-pairs + dense or negative-tolerant + simple code → Floyd-Warshall; all-pairs + sparse + negative edges possible → Johnson's; single source, single target, heuristic available → A*.

## Why this gets asked

This is the question that catches candidates who know *that* Johnson's algorithm exists (a name-drop) but can't derive *why* the reweighting is valid — and that derivation is exactly the kind of "one level below where most people stop" reasoning that separates senior from staff-level answers. The production motivation is real: routing and logistics platforms that need all-pairs distance matrices (delivery time estimates between every pair of warehouses, or every pair of microservices in a latency-aware service mesh) on graphs with tens of thousands of sparse nodes cannot afford Floyd-Warshall's cubic cost, and reaching for "just run Dijkstra from every node" fails the instant a single negative-cost edge appears (a rebate, a cached/precomputed shortcut represented as negative cost, a synthetic edge in a reduction from another problem). Interviewers who've had to explain to a team why an O(V^3) all-pairs job that used to finish in minutes now takes hours after the graph grew 10x are the ones asking this, because they've lived the exact moment a sparse-graph assumption stopped being an implementation detail and became a production incident.

---

## Lineage: past → present → future

**What came before.** Before Johnson's algorithm (Donald Johnson, 1977, "Efficient Algorithms for Shortest Paths in Sparse Networks"), the only correct general-purpose all-pairs shortest path algorithm tolerant of negative edges was Floyd-Warshall at `O(V^3)`, or running Bellman-Ford from every vertex at `O(V^2 E)` — both ignore or overpay for sparsity. The specific pain Johnson's algorithm killed: a sparse graph with `E ~ V` makes Floyd-Warshall's `O(V^3)` and repeated-Bellman-Ford's `O(V^2 E) = O(V^3)` both needlessly expensive compared to what should be achievable by combining Dijkstra's speed on non-negative graphs with a one-time preprocessing cost to eliminate negative edges. The reweighting trick itself — using vertex potentials to transform edge weights without changing which paths are shortest — has roots in the broader concept of a "potential function" from network flow theory and physics-inspired optimization (the idea that adding a value that telescopes to zero along any path doesn't change relative path costs is the same principle behind potential energy differences being path-independent).

**Where it stands now.** Johnson's algorithm is the textbook-correct answer for sparse all-pairs shortest paths with possible negative edges, and it's covered in every serious algorithms course, but it's underused *in practice* relative to how often the sparse-negative-edge combination actually occurs — many engineers default to Floyd-Warshall out of familiarity even when the graph is sparse enough that Johnson's would be meaningfully faster, or default to "just don't allow negative edges" by construction (reformulating the problem to avoid them) rather than handling them generally. There is a live, practical disagreement about whether it's worth implementing Johnson's algorithm at all versus simply guaranteeing non-negative weights by problem design — many production routing systems simply never allow negative edge costs to exist in the first place (costs are physical distances or non-negative latencies), sidestepping the need for Johnson's algorithm entirely rather than solving the general case.

**Where it's heading.** No new foundational shortest-path algorithm is expected. The applied direction is precomputed, index-heavy structures for near-real-time all-pairs-style queries at massive scale — contraction hierarchies and hub labeling (used in production route planners like OSRM) precompute a much richer structure than Johnson's algorithm produces, trading a heavier one-time preprocessing cost for near-instant point-to-point queries afterward, which is a different tradeoff point on the same spectrum (preprocessing cost vs. query cost) that Johnson's algorithm occupies at the "moderate preprocessing, moderate query" end.

---

## Mental model

Johnson's algorithm is "borrow a fair global handicap from Bellman-Ford, apply it to every edge so nothing is negative anymore, then let Dijkstra do the fast part, and finally undo the handicap."

```
Original graph (has a negative edge):
S --1--> A --(-5)--> B

Add virtual source Q with 0-weight edges to every vertex, run Bellman-Ford
from Q to get potential h(v) for every v (h(v) = shortest distance from Q).

Reweight every edge: w'(u,v) = w(u,v) + h(u) - h(v)
This is provably >= 0 for every edge, as long as there's no negative cycle,
because h(v) <= h(u) + w(u,v) is exactly the Bellman-Ford shortest-path
inequality (the triangle inequality that Bellman-Ford's relaxation enforces).

Run Dijkstra from every vertex on the reweighted (now non-negative) graph.
Convert back: dist(u,v) = dist'(u,v) - h(u) + h(v)
The h(u) and h(v) terms telescope out along any path, so relative shortest
paths are unchanged -- only the absolute edge weights were shifted.
```

Think of `h(v)` as "altitude" — reweighting subtracts the altitude change along every edge, flattening the landscape into something with no downhill (negative) edges, without changing which route between two fixed points is actually the shortest, because the total altitude change from start to end is the same regardless of which path you take between those two fixed endpoints.

---

## Recognition heuristics

- **"All pairs shortest paths"** stated explicitly, with graph size large enough that `V^3` is a red flag (`V` in the thousands or more) and the graph is sparse (`E` roughly linear in `V`) → Johnson's algorithm is the expected escalation past Floyd-Warshall.
- **"All pairs" on a small or dense graph** (`V` in the low hundreds, or `E` close to `V^2`) → Floyd-Warshall remains correct and is simpler to implement; naming Johnson's and explaining why it isn't worth it here is itself a strong answer.
- **"Negative edges might exist, but you need every pair's shortest distance"** → this is precisely Johnson's algorithm's target case; if the interviewer also says "sparse," that's a second confirming signal.
- **"Reweight the graph" or "add a virtual node"** appearing anywhere in a hint or follow-up → a direct signal Johnson's algorithm (or a closely related potential-function trick) is expected.
- **"You need point-to-point queries repeatedly, after some preprocessing, on a graph that doesn't change"** → this is a tell that a heavier precomputed structure (contraction hierarchies, hub labeling) might be the "real" production answer beyond what's expected in an interview, worth naming as a follow-up escalation.
- **"Single query, single source and target, with a natural heuristic"** → not this module's territory at all; that's A*, a fundamentally different tool (see `T02-adv-graphs`).

---

## How it actually works — the reweighting proof, in full

**Step 1: Add a virtual source.** Create a new vertex `Q` with a 0-weight directed edge to every vertex in the graph (not from — this ensures `Q` can reach everything without creating new negative cycles or changing existing shortest-path structure among the original vertices).

**Step 2: Run Bellman-Ford from `Q`.** This computes `h(v)` = shortest distance from `Q` to every vertex `v`. Because every original vertex is reachable from `Q` in exactly one 0-weight hop, `h(v)` is well-defined for every vertex, and Bellman-Ford's negative-cycle check (the extra relaxation pass) confirms whether the *original* graph has a negative cycle — Johnson's algorithm is undefined (shortest paths aren't well-defined at all) if a negative cycle exists, so this check is not optional.

**Step 3: Reweight every edge.** `w'(u,v) = w(u,v) + h(u) - h(v)`. The claim that this is always `>= 0` (given no negative cycle) follows directly from the Bellman-Ford shortest-path property: for every edge `(u,v)`, `h(v) <= h(u) + w(u,v)` (this is exactly the relaxation inequality that Bellman-Ford guarantees holds for every edge once it has converged — if it didn't hold for some edge, that edge would still be relaxable, meaning Bellman-Ford hasn't actually converged). Rearranging, `w(u,v) + h(u) - h(v) >= 0`, which is precisely `w'(u,v) >= 0`.

**Step 4: Run Dijkstra from every vertex on the reweighted graph.** Since every reweighted edge is now non-negative, Dijkstra's correctness proof (the cut property) holds again, giving `dist'(u,v)` for every pair in `O((V+E) log V)` per source, `O(V(V+E) log V) = O(VE + V^2 log V)` total.

**Step 5: Convert back.** For any path from `u` to `v`, the sum of reweighted edge costs along it is `sum(w(x,y) + h(x) - h(y))` over the path's edges, which telescopes: every intermediate `h` term appears once as `+h(x)` and once as `-h(y)` for adjacent edges, canceling all but the endpoints, leaving `sum(w(x,y)) + h(u) - h(v)`. So `dist'(u,v) = dist(u,v) + h(u) - h(v)`, and rearranging gives the real distance: `dist(u,v) = dist'(u,v) - h(u) + h(v)`. Because this telescoping holds identically for *every* path between `u` and `v`, the path that's shortest under the reweighted costs is also the path that's shortest under the real costs — reweighting doesn't change which path wins, only shifts every path's total by the same amount `h(u) - h(v)`.

This is precisely the "borrow a global handicap" mental model: every path between a fixed `u` and `v` gets shifted by the identical constant, so their *relative order* — which one is shortest — is completely unaffected.

---

## Template code (Python, Java, Go)

```python
from heapq import heappush, heappop

def johnsons_algorithm(n: int, edges: list[tuple[int, int, int]]):
    # Step 1-2: virtual source + Bellman-Ford for potentials h(v)
    INF = float('inf')
    h = [0] * n  # virtual source has 0-weight edges to all n vertices
    for _ in range(n):  # n rounds suffice: virtual source adds one hop
        updated = False
        for u, v, w in edges:
            if h[u] + w < h[v]:
                h[v] = h[u] + w
                updated = True
        if not updated:
            break
    else:
        # one more pass to confirm no negative cycle among original edges
        for u, v, w in edges:
            if h[u] + w < h[v]:
                raise ValueError("negative cycle detected")

    # Step 3: reweight edges, guaranteed non-negative
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        w_reweighted = w + h[u] - h[v]
        assert w_reweighted >= 0
        adj[u].append((v, w_reweighted))

    # Step 4: Dijkstra from every vertex on the reweighted graph
    def dijkstra(src):
        dist = [INF] * n
        dist[src] = 0
        pq = [(0, src)]
        while pq:
            d, u = heappop(pq)
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heappush(pq, (nd, v))
        return dist

    # Step 5: convert back to real distances
    result = [[INF] * n for _ in range(n)]
    for u in range(n):
        dprime = dijkstra(u)
        for v in range(n):
            if dprime[v] < INF:
                result[u][v] = dprime[v] - h[u] + h[v]
    return result
```

```java
import java.util.*;

public class Johnsons {

    static double[][] johnsonsAlgorithm(int n, int[][] edges) {
        double INF = Double.POSITIVE_INFINITY;
        double[] h = new double[n];  // potentials, virtual source implicit at 0 for all

        // Bellman-Ford for potentials
        for (int i = 0; i < n; i++) {
            boolean updated = false;
            for (int[] e : edges) {
                int u = e[0], v = e[1], w = e[2];
                if (h[u] + w < h[v]) {
                    h[v] = h[u] + w;
                    updated = true;
                }
            }
            if (!updated) break;
            if (i == n - 1) {
                for (int[] e : edges) {
                    int u = e[0], v = e[1], w = e[2];
                    if (h[u] + w < h[v]) throw new RuntimeException("negative cycle detected");
                }
            }
        }

        // Reweight
        List<List<double[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) {
            int u = e[0], v = e[1], w = e[2];
            double wPrime = w + h[u] - h[v];
            adj.get(u).add(new double[]{v, wPrime});
        }

        double[][] result = new double[n][n];
        for (double[] row : result) Arrays.fill(row, INF);

        for (int src = 0; src < n; src++) {
            double[] dPrime = new double[n];
            Arrays.fill(dPrime, INF);
            dPrime[src] = 0;
            PriorityQueue<double[]> pq = new PriorityQueue<>((a, b) -> Double.compare(a[0], b[0]));
            pq.add(new double[]{0, src});
            while (!pq.isEmpty()) {
                double[] top = pq.poll();
                double d = top[0]; int u = (int) top[1];
                if (d > dPrime[u]) continue;
                for (double[] edge : adj.get(u)) {
                    int v = (int) edge[0]; double w = edge[1];
                    double nd = d + w;
                    if (nd < dPrime[v]) {
                        dPrime[v] = nd;
                        pq.add(new double[]{nd, v});
                    }
                }
            }
            for (int v = 0; v < n; v++) {
                if (dPrime[v] < INF) result[src][v] = dPrime[v] - h[src] + h[v];
            }
        }
        return result;
    }
}
```

```go
package main

import "container/heap"

type JItem struct {
    dist float64
    node int
}
type JPQ []JItem

func (pq JPQ) Len() int           { return len(pq) }
func (pq JPQ) Less(i, j int) bool  { return pq[i].dist < pq[j].dist }
func (pq JPQ) Swap(i, j int)       { pq[i], pq[j] = pq[j], pq[i] }
func (pq *JPQ) Push(x interface{}) { *pq = append(*pq, x.(JItem)) }
func (pq *JPQ) Pop() interface{} {
    old := *pq
    n := len(old)
    item := old[n-1]
    *pq = old[:n-1]
    return item
}

const JINF = 1e18

func johnsonsAlgorithm(n int, edges [][3]int) [][]float64 {
    h := make([]float64, n)
    for iter := 0; iter < n; iter++ {
        updated := false
        for _, e := range edges {
            u, v, w := e[0], e[1], e[2]
            if h[u]+float64(w) < h[v] {
                h[v] = h[u] + float64(w)
                updated = true
            }
        }
        if !updated {
            break
        }
    }
    // negative cycle check (one more pass)
    for _, e := range edges {
        u, v, w := e[0], e[1], e[2]
        if h[u]+float64(w) < h[v] {
            panic("negative cycle detected")
        }
    }

    type edge struct {
        to int
        w  float64
    }
    adj := make([][]edge, n)
    for _, e := range edges {
        u, v, w := e[0], e[1], e[2]
        wPrime := float64(w) + h[u] - h[v]
        adj[u] = append(adj[u], edge{v, wPrime})
    }

    result := make([][]float64, n)
    for i := range result {
        result[i] = make([]float64, n)
        for j := range result[i] {
            result[i][j] = JINF
        }
    }

    for src := 0; src < n; src++ {
        dPrime := make([]float64, n)
        for i := range dPrime {
            dPrime[i] = JINF
        }
        dPrime[src] = 0
        pq := &JPQ{{0, src}}
        for pq.Len() > 0 {
            top := heap.Pop(pq).(JItem)
            d, u := top.dist, top.node
            if d > dPrime[u] {
                continue
            }
            for _, e := range adj[u] {
                nd := d + e.w
                if nd < dPrime[e.to] {
                    dPrime[e.to] = nd
                    heap.Push(pq, JItem{nd, e.to})
                }
            }
        }
        for v := 0; v < n; v++ {
            if dPrime[v] < JINF {
                result[src][v] = dPrime[v] - h[src] + h[v]
            }
        }
    }
    return result
}
```

## Complexity — derived, not asserted

**Johnson's algorithm total cost:** one Bellman-Ford pass from the virtual source, `O(VE)`; then `V` runs of Dijkstra on the reweighted graph, each `O((V+E) log V)`, totaling `O(V^2 log V + VE log V)`. Since the `O(VE)` Bellman-Ford term is dominated by the Dijkstra terms for any reasonable graph, the commonly quoted bound is `O(VE + V^2 log V)`. Compare directly against Floyd-Warshall's `O(V^3)`: at `V = 10,000` and a sparse `E = 30,000`, Johnson's gives roughly `VE + V^2 log V ≈ 3*10^8 + 10^8*13 ≈ 1.3*10^9`, while Floyd-Warshall gives `V^3 = 10^12` — three orders of magnitude worse, which is the concrete number that justifies choosing Johnson's over Floyd-Warshall on sparse graphs at scale.

**Why the reweighting doesn't change asymptotic complexity of the Dijkstra phase:** the reweighted graph has exactly the same number of vertices and edges as the original — reweighting only changes numeric edge labels, not graph structure — so Dijkstra's `O((V+E) log V)` bound applies unchanged to the transformed graph.

**Space:** `O(V^2)` to store the final all-pairs distance matrix (unavoidable, since the output itself has `V^2` entries), plus `O(V+E)` for the graph representation and the per-source Dijkstra working state, which doesn't need to be retained across sources.

---

## The 5 variants interviewers actually ask

1. **All-pairs shortest paths on a sparse graph that may have negative edges (the canonical Johnson's algorithm problem).** Directly as described above; the interviewer is checking whether you can derive the reweighting proof, not just name-drop the algorithm.
2. **Detect whether the whole graph (not just from one source) contains any negative cycle.** Johnson's algorithm's own precondition check — the virtual-source Bellman-Ford pass with the extra relaxation-pass check — answers this directly as a side effect of setup, worth mentioning even if the actual question only asks for shortest paths.
3. **Currency arbitrage across all currency pairs simultaneously (not just checking one starting currency).** A direct application: build the `-log(rate)` graph, and Johnson's algorithm's negative-cycle precondition check (during the potential computation) tells you if *any* arbitrage cycle exists anywhere in the whole graph, not just reachable from one chosen starting currency.
4. **"Reformulate this problem so Dijkstra can be used" when negative edges appear only in a structural, predictable way** (e.g., a fixed bonus/penalty applied uniformly at certain node types). This tests whether you can construct a problem-specific potential function directly, bypassing the need for a full Bellman-Ford pass, when the negative-edge structure is simple enough to reason about by hand — a strong signal of understanding the reweighting principle itself rather than just the algorithm's steps.
5. **All-pairs shortest paths where you additionally need to reconstruct the actual paths, not just distances.** Extends Johnson's algorithm with parent-pointer tracking during each Dijkstra run — the reweighting doesn't affect which edges are on the shortest path (only the total cost accounting), so path reconstruction works identically to standard Dijkstra path reconstruction on the reweighted graph.

---

## Common bugs and how this gets written wrong under pressure

- **Forgetting the negative-cycle check after the potential-computing Bellman-Ford pass.** If the original graph has a negative cycle, shortest paths are undefined (you can loop the cycle forever, decreasing cost each time), and Johnson's algorithm's whole premise (that reweighting produces a valid non-negative graph) breaks down; skipping this check silently produces a reweighted graph that isn't actually all non-negative, and Dijkstra on it produces wrong answers without any error.
- **Adding the virtual source's edges in the wrong direction.** The virtual source must have edges *to* every vertex (so Bellman-Ford can compute a potential *for* every vertex), not edges *from* every vertex to it; getting this backward either leaves some vertices with an undefined/infinite potential or introduces a spurious cycle through the virtual source.
- **Using the wrong sign in the reweighting formula.** `w'(u,v) = w(u,v) + h(u) - h(v)` is the correct form; swapping to `w(u,v) + h(v) - h(u)` produces a graph that can still have negative edges (the inequality direction that guarantees non-negativity is `h(v) <= h(u) + w(u,v)`, which only cancels correctly with the `+h(u) - h(v)` ordering).
- **Forgetting to convert distances back after running Dijkstra on the reweighted graph.** Reporting `dist'(u,v)` directly as the answer instead of `dist'(u,v) - h(u) + h(v)` gives a number that's numerically wrong for every pair except where `h(u) = h(v)` — this is an easy mistake because the reweighted distances still "look like" plausible numbers.
- **Re-running the potential-computing Bellman-Ford pass separately for every source vertex**, instead of once globally from the virtual source — this is a fundamental misunderstanding of the algorithm's structure (there's exactly one Bellman-Ford pass total, followed by `V` Dijkstra runs, not `V` Bellman-Ford passes) and destroys the entire complexity advantage over simply running Bellman-Ford from every vertex directly.
- **Choosing Johnson's algorithm on a dense graph out of habit** ("it's the fancy algorithm, so it must be better") — on a dense graph (`E ~ V^2`), Johnson's `O(VE + V^2 log V)` approaches `O(V^3 + V^2 log V)`, no better than Floyd-Warshall's `O(V^3)` and with considerably more implementation complexity for no real gain; naming this boundary case correctly is itself part of the expected answer.

---

## Interview questions

### Q1 — Derive Johnson's algorithm from scratch: why does reweighting with `h(u) - h(v)` preserve shortest paths?
**Testing:** the core telescoping proof, not just the algorithm's steps.
**Answer:** For any path from `u` to `v`, summing `w(x,y) + h(x) - h(y)` over every edge telescopes to `sum(w(x,y)) + h(u) - h(v)` since every intermediate `h` term cancels; the same constant `h(u) - h(v)` is added to every path's real cost, so relative ordering (which path is shortest) is unaffected.
**Follow-up trap:** *"Why must `h(v)` come specifically from Bellman-Ford, not any arbitrary function?"* — the non-negativity of every reweighted edge depends on `h(v) <= h(u) + w(u,v)` holding for *every* edge, which is exactly the Bellman-Ford shortest-path invariant from a common source; an arbitrary potential function wouldn't guarantee this for every edge.

### Q2 — When is Johnson's algorithm strictly better than Floyd-Warshall, and when is it not worth it?
**Testing:** the concrete complexity comparison, with real numbers.
**Answer:** Better when the graph is sparse (`E` closer to `V` than `V^2`) — e.g., `V=10,000, E=30,000` gives Johnson's roughly `10^9` operations versus Floyd-Warshall's `10^12`. Not worth it on dense graphs (`E ~ V^2`), where Johnson's approaches the same `V^3` order with more implementation complexity.
**Follow-up trap:** *"What if V is small, like 200?"* — Floyd-Warshall's `V^3 = 8*10^6` is trivially fast and much simpler to implement correctly; Johnson's added complexity buys nothing at this scale regardless of density.

### Q3 — What happens if you run Johnson's algorithm on a graph with a negative cycle, and you skip the negative-cycle check?
**Testing:** understanding the precondition, not just the happy-path algorithm.
**Answer:** Shortest paths are undefined in the presence of a negative cycle (cost can be driven arbitrarily low by looping); skipping the check means the potentials `h(v)` computed by Bellman-Ford haven't actually converged correctly, so the reweighted edges aren't guaranteed non-negative, and the subsequent Dijkstra runs silently produce wrong distances with no error raised.
**Follow-up trap:** *"How exactly does the check work?"* — run one additional relaxation pass beyond the `V-1` (or `V`, accounting for the virtual source) needed for convergence; if any edge still relaxes, a negative cycle is reachable from the virtual source, which — since the virtual source reaches every vertex — means a negative cycle exists somewhere in the original graph.

### Q4 — Currency arbitrage: determine if *any* arbitrage cycle exists among all currency pairs, not starting from a specific currency.
**Testing:** recognizing Johnson's negative-cycle precondition check directly answers a "does a negative cycle exist anywhere" question.
**Answer:** Build the `-log(rate)` graph, add a virtual source connected to all currencies, run Bellman-Ford; the extra relaxation pass reveals whether any negative cycle (arbitrage loop) exists anywhere reachable from the virtual source, which covers the whole graph since the virtual source connects to everything.
**Follow-up trap:** *"Why not just run Bellman-Ford from an arbitrary real currency node instead of adding a virtual source?"* — a real node might not reach every other node (the currency graph could be disconnected or have one-way convertibility), so an arbitrage cycle unreachable from that specific starting node would be silently missed; the virtual source guarantees full reachability by construction.

### Q5 — What's the space cost of Johnson's algorithm's output, and is it avoidable?
**Testing:** whether you recognize an inherent lower bound versus an implementation inefficiency.
**Answer:** `O(V^2)` to store the full all-pairs distance matrix — this is inherent to the problem (the output itself has `V^2` entries) and not avoidable by a better algorithm, unlike the `O(V^3)` time cost of Floyd-Warshall, which genuinely is avoidable with a better algorithm.
**Follow-up trap:** *"What if you only need shortest paths for a specific subset of k source vertices, not all V?"* — run only `k` Dijkstra passes instead of `V` after the single shared potential-computation step, reducing the total cost to `O(VE + kV log V)` and the output space to `O(kV)` — a real, common optimization when the "all-pairs" framing is broader than what's actually needed.

### Q6 — Compare Johnson's algorithm to simply running Bellman-Ford from every vertex directly (skipping the reweighting step entirely).
**Testing:** understanding exactly what the reweighting buys you.
**Answer:** Bellman-Ford from every vertex costs `O(V * VE) = O(V^2 E)`; Johnson's algorithm reduces this to `O(VE + V^2 log V)` specifically because reweighting lets you substitute `V` cheap Dijkstra runs for `V` expensive Bellman-Ford runs, paying the Bellman-Ford cost only once (for the potentials) instead of `V` times.
**Follow-up trap:** *"At what graph density does this advantage disappear?"* — as `E` approaches `V^2` (dense graphs), `V^2 E` and `VE + V^2 log V` both approach cubic order, and the practical advantage shrinks to a modest constant-factor difference rather than a genuine complexity-class win.

### Q7 — Your production routing system's edges are guaranteed non-negative by design (they're physical travel times). Would you ever still reach for Johnson's algorithm?
**Testing:** judgment about over-engineering.
**Answer:** No — if negative edges are structurally impossible, running `V` Dijkstra runs directly (without any reweighting) already achieves the same complexity with far less implementation risk; Johnson's reweighting step exists specifically to handle negative edges, and applying it when there are none is unnecessary complexity for zero benefit.
**Follow-up trap:** *"What if a future feature might introduce negative-cost edges (e.g., promotional routing discounts)?"* — this is a legitimate reason to build the reweighting infrastructure proactively, but it's a product/architecture decision to flag explicitly (with the added complexity and testing cost named), not something to add silently "just in case."

### Q8 — How would you reconstruct the actual shortest path (not just its length) using Johnson's algorithm?
**Testing:** extending the algorithm correctly, checking you understand what reweighting does and doesn't change.
**Answer:** Track parent pointers during each per-source Dijkstra run exactly as you would in standard Dijkstra; the reweighted graph has identical structure (same vertices, same edges, only relabeled weights) and identical shortest-path *edges* as the original — reweighting changes total cost accounting via the telescoping `h(u)-h(v)` term, not which specific path is shortest — so path reconstruction is unaffected by the transformation.
**Follow-up trap:** *"Does the reweighted path length equal the real path length?"* — no; you must still convert with `dist(u,v) = dist'(u,v) - h(u) + h(v)` to get the real total cost, even though the *sequence of edges* on the shortest path is identical between the reweighted and original graphs.

### Q9 — Why does the virtual source need 0-weight edges specifically, rather than some other weight?
**Testing:** precision about the construction, not just pattern-matching the recipe.
**Answer:** A 0-weight edge from the virtual source to every vertex ensures `h(v) <= 0 + w(source,v) = w(source,v)`, i.e., every vertex gets a well-defined finite potential in exactly one hop, without artificially inflating or deflating any vertex's potential relative to others — any nonzero uniform weight would just shift every `h(v)` by the same constant and wouldn't change the reweighting's correctness, but zero is the simplest choice and avoids any risk of misapplying an arbitrary constant inconsistently.
**Follow-up trap:** *"Would using a very large weight instead of 0 break anything?"* — not necessarily break correctness (a uniform shift cancels in the same telescoping way), but it needlessly complicates reasoning and implementation for zero benefit — there's no reason to deviate from 0.

### Q10 — Staff-level: your all-pairs shortest path job on a 500,000-node sparse graph needs to answer repeated point-to-point queries after a one-time preprocessing step, and even Johnson's O(V^2) output storage is too much memory. What do you do?
**Testing:** knowing the escalation beyond Johnson's algorithm exists.
**Answer:** Don't materialize the full O(V^2) matrix at all; use a structure designed for point-to-point queries after heavier preprocessing, like contraction hierarchies or hub labeling, which answer individual shortest-path queries in near-constant to logarithmic time without ever storing all pairs explicitly, trading a more complex one-time build for both faster queries and dramatically less storage than a full distance matrix.
**Follow-up trap:** *"Is this something you'd implement from scratch in an interview?"* — no, and saying so is the correct answer; naming it as the production-grade escalation while acknowledging it's out of scope for a from-scratch interview implementation is exactly the senior signal being tested.

---

## Red flags that fail you

- Naming Johnson's algorithm without being able to derive why the reweighting preserves shortest paths.
- Forgetting the negative-cycle check after the potential-computing Bellman-Ford pass.
- Getting the reweighting formula's sign backward (`h(v) - h(u)` instead of `h(u) - h(v)`).
- Forgetting to convert reweighted distances back to real distances after running Dijkstra.
- Re-running Bellman-Ford once per source instead of once globally from a virtual source, destroying the algorithm's complexity advantage.
- Reaching for Johnson's algorithm on a dense graph where it offers no real benefit over Floyd-Warshall.

---

## Cheat card

```
JOHNSON'S      all-pairs, sparse graph, tolerates negative edges (not cycles)
               O(VE + V^2 log V), beats Floyd-Warshall's O(V^3) when sparse
STEPS          1. virtual source Q, 0-weight edges TO every vertex
               2. ONE Bellman-Ford pass from Q -> potentials h(v)
               3. check negative cycle (extra relax pass) -- else undefined
               4. reweight: w'(u,v) = w(u,v) + h(u) - h(v)  [always >= 0]
               5. Dijkstra from EVERY vertex on reweighted graph
               6. convert back: dist(u,v) = dist'(u,v) - h(u) + h(v)
PROOF CORE     h(v) <= h(u)+w(u,v) is the Bellman-Ford invariant -> w'>=0
               path cost telescopes: same h(u)-h(v) shift on every path
               between fixed u,v -> relative shortest-path order unchanged
NUMBERS        V=10k, E=30k: Johnson's ~1.3*10^9 vs Floyd-Warshall ~10^12
WHEN NOT       dense graph (E~V^2) -> Johnson's ~ same order as V^3, not
               worth the complexity; small V -> Floyd-Warshall simpler
BEYOND         contraction hierarchies / hub labeling for repeated point-
               to-point queries at massive scale, not full-matrix storage
WATCH          skipping negative-cycle check; wrong reweight sign; forgetting
               the back-conversion; re-deriving potentials per source
```

## Sources

- Johnson, D.B. (1977). "Efficient Algorithms for Shortest Paths in Sparse Networks." Journal of the ACM, 24(1), 1-13.
- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), Chapter 25: All-Pairs Shortest Paths.
- [Johnson's Algorithm — CP-Algorithms / GeeksforGeeks](https://www.geeksforgeeks.org/dsa/johnsons-algorithm/) — accessed 2026-07-26
- [Contraction Hierarchies — OSRM Project Documentation](https://github.com/Project-OSRM/osrm-backend/wiki/Contraction-Hierarchies) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
