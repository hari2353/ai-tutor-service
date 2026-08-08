# MST and Max-Flow: Kruskal, Prim, Ford-Fulkerson/Edmonds-Karp, Bipartite Matching

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** T02-p19-union-find, T02-graph-core
> **Module id:** `T02-graph-mst-flow` · **Tags:** graphs, mst, flow, matching
> **Lab:** `labs/py/28-graph-mst-flow/`

## The 30-second version

Minimum spanning tree (MST) and max-flow are two different optimization shapes over the same weighted-graph substrate, and each has a small number of correct algorithms with distinct tradeoffs. Kruskal's algorithm sorts all edges by weight and greedily adds each one unless it would form a cycle (checked via Union-Find), giving O(E log E) — the right default when the edge list is already available or the graph is sparse. Prim's algorithm grows a single tree from an arbitrary start, always adding the cheapest edge that connects the tree to a new vertex (via a min-heap), giving O(E log V) — the right default when the graph is dense or given as an adjacency matrix, since Prim's heap-based frontier naturally suits that access pattern. Both are provably correct via the same underlying principle, the **cut property**: for any partition of vertices into two non-empty sets, the minimum-weight edge crossing that cut is in *some* MST — Kruskal and Prim just apply this cut property in different orders. Max-flow/min-cut is a different problem (maximum total flow from source to sink under edge capacities) solved by repeatedly finding augmenting paths in the residual graph — Ford-Fulkerson is the general method (correctness for any augmenting-path-finding strategy, but complexity depends on capacity values if paths aren't chosen carefully), Edmonds-Karp is the concrete O(VE^2) instantiation that always picks the *shortest* augmenting path (via BFS), guaranteeing polynomial time independent of capacity magnitudes. Bipartite matching is a special case of max-flow (unit-capacity edges from a virtual source through left vertices, matching edges, through right vertices, to a virtual sink) — max-flow equals maximum matching size by the max-flow min-cut theorem, which is why the Hopcroft-Karp algorithm (a matching-specific speedup) exists as a faster alternative to running generic max-flow on the same reduction.

## Why this gets asked

MST tests whether you understand a second application of the exchange-argument/cut-property proof style beyond simple greedy problems — a strong signal of whether "greedy correctness" is a memorized fact or a transferable proof technique. Max-flow tests something different and more consequential in practice: whether you can recognize that a huge class of seemingly unrelated problems (bipartite matching, project selection, image segmentation, network reliability, scheduling with capacity constraints) all reduce to the same max-flow formulation — the reduction itself is usually the hard part, not implementing Ford-Fulkerson once you see it. Interviewers who've built resource allocation systems, ad-matching platforms, or network capacity planning tools have lived the moment a "simple assignment problem" turned out to be maximum bipartite matching in disguise, and reaching for a greedy or brute-force approach instead of recognizing the flow reduction produces an algorithm that's either wrong or exponentially slower than necessary.

---

## Lineage: past → present → future

**What came before.** Before Kruskal (1956) and Prim (1957, though Jarník had described the same core idea in 1930, largely unrecognized until later credit was restored — it's sometimes called the Jarník-Prim algorithm for this reason) formalized MST construction, the only general approach was brute-force enumeration of spanning trees, intractable beyond tiny graphs (the number of spanning trees of a complete graph on `n` vertices is `n^(n-2)` by Cayley's formula, astronomically large even for modest `n`). Max-flow's foundational result, the max-flow min-cut theorem, was proven by Ford and Fulkerson in 1956, motivated directly by Cold War logistics research (the original application was modeling Soviet rail network capacity, funded by the RAND Corporation) — before this, there was no general polynomial-style method for capacity-constrained routing optimization, only problem-specific heuristics.

**Where it stands now.** Kruskal's and Prim's algorithms are both textbook-standard and equally "correct" defaults; the practical choice between them is almost entirely about graph density and input format, not correctness. Ford-Fulkerson as originally stated is a *method*, not a fully specified algorithm — its complexity depends on how augmenting paths are chosen, and with arbitrary (e.g., DFS-found) augmenting paths and integer capacities, it can take a number of iterations proportional to the *capacity values themselves*, not the graph size, a real pathological case; Edmonds-Karp (1972) fixes this by always choosing the shortest augmenting path via BFS, guaranteeing O(VE^2) independent of capacity magnitude, and is the version actually expected in interviews. For matching specifically, Hopcroft-Karp (1973) achieves O(E√V) by finding *multiple* augmenting paths per phase instead of one at a time, and is meaningfully faster than generic max-flow reductions at scale — a distinction candidates who've only memorized "matching = max-flow" often miss.

**Where it's heading.** No new foundational MST or max-flow algorithm is imminent — MST is essentially fully understood (even faster theoretical algorithms exist, like Chazelle's near-linear-time MST algorithm using soft heaps, but they're not practically used and not interview material), and max-flow research has moved toward near-linear-time algorithms for the general problem (a landmark 2022 result by Chen, Kyng, Liu, Peng, Probst Gutenberg, and Sachdeva achieved almost-linear-time max-flow, a major theoretical breakthrough) that are not yet standard production tools due to implementation complexity, but signal where the field is heading over the next decade. Practically, production systems needing large-scale flow/matching (ad auction allocation, ride-hailing driver-rider matching) increasingly favor approximate or online variants over exact classical algorithms, since exact max-flow doesn't naturally handle a matching problem that must be solved incrementally as new demand arrives in real time.

---

## Mental model

MST-via-cut-property: imagine any way of splitting the graph's vertices into two groups; the single cheapest edge crossing that split *must* belong to some minimum spanning tree, because if it didn't, you could always swap in that cheaper crossing edge for whatever more expensive edge the "MST" used to cross the same split, strictly improving it.

```
Cut: {A, B} | {C, D}
Edges crossing the cut: A-C (weight 5), B-D (weight 2), A-D (weight 9)
Cheapest crossing edge: B-D (weight 2) -- guaranteed to be in some MST.
Kruskal exploits this globally (sort all edges, greedily respect cuts).
Prim exploits this locally (always grow via the cheapest edge crossing
the current tree-vs-rest cut).
```

Max-flow is water pushed through pipes with capacity limits; an augmenting path is any route from source to sink with spare capacity remaining, and you keep finding new routes (potentially "undoing" some previously assigned flow via a reverse residual edge) until no more augmenting paths exist.

```
S --10--> A --5--> T        Residual graph after pushing 5 units S->A->T:
                             S --5--> A --0--> T   (forward capacity used up)
                             S <--5-- A <--5-- T   (reverse residual edges,
                                                     representing "undo" capacity)
Max-flow-min-cut theorem: the maximum flow value EQUALS the minimum total
capacity of any cut separating S from T -- flow can never exceed the
tightest bottleneck, and a correct algorithm always finds a flow that
exactly saturates some minimum cut.
```

---

## Recognition heuristics

- **"Connect all nodes with minimum total edge weight"**, **"minimum cost to connect all cities/computers/pipes"** — MST, Kruskal if edge list given or graph sparse, Prim if adjacency matrix or dense.
- **"Maximum flow from source to sink given capacities"** — Ford-Fulkerson/Edmonds-Karp directly.
- **"Assign workers to jobs" / "match students to schools" / "pair up two disjoint groups optimally"** — bipartite matching, reducible to max-flow with unit-capacity edges; Hopcroft-Karp if speed at scale matters and the reduction is recognized as pure matching (no weighted variant needed).
- **"Minimum number of edges to remove to disconnect source from sink"**, **"bottleneck capacity of a network"** — this is literally the min-cut side of max-flow-min-cut; solving max-flow *is* solving this, since the theorem guarantees their values are equal.
- **"Can every item in set A be uniquely assigned to a distinct item in set B satisfying some pairwise compatibility"** — bipartite matching in disguise; the tell is a pairwise compatibility/eligibility relation between two distinct groups with a uniqueness/assignment requirement.
- **A weighted variant of matching** ("maximize total assignment value, not just count") — this needs a different algorithm (the Hungarian algorithm / min-cost max-flow), not plain Ford-Fulkerson or Hopcroft-Karp, both of which assume unweighted (unit-value) matching.
- **"Redundant network design" / "critical edges whose removal disconnects the graph"** — adjacent territory (bridges/articulation points, covered in `T02-graph-scc`), not MST or flow directly, but often confused with min-cut in casual problem phrasing — check whether capacities/weights or pure connectivity is the actual question.

---

## How it actually works — the cut property proof, and why BFS-based augmenting paths fix Ford-Fulkerson's pathological case

**MST cut property proof.** For any cut (partition of vertices into two non-empty sets), let `e` be the minimum-weight edge crossing it. Suppose some MST `T` doesn't contain `e`. Adding `e` to `T` creates exactly one cycle (since `T` is a tree, any additional edge creates exactly one cycle); that cycle must contain at least one other edge `e'` that also crosses the same cut (because the cycle must cross the cut an even number of times, at least twice, to return to its starting side). Since `e` is the minimum-weight crossing edge, `weight(e) <= weight(e')`. Swap `e'` out for `e`: the result is still a spanning tree (removing `e'` breaks the cycle back into a tree, adding `e` reconnects it) with total weight no greater than `T`'s. This is a direct exchange argument, identical in spirit to the ones in `T02-adv-greedy`, applied to a different combinatorial structure (spanning trees instead of a simple selection sequence).

**Kruskal applies this by processing edges in global sorted order** and using Union-Find to check "would this edge's two endpoints already be connected in the tree built so far" — if not, adding it is safe by the cut property applied to the current forest's connected components as the cut. **Prim applies this by maintaining one growing tree** and using a min-heap keyed on "cheapest edge from the current tree to any vertex outside it" — that's the cut between "in the tree" and "not yet in the tree," and the cheapest crossing edge is always safe to add by the same property.

**Why Ford-Fulkerson's complexity depends on the augmenting-path strategy.** The Ford-Fulkerson *method* only guarantees termination and correctness (it stops when no augmenting path exists, and by the max-flow-min-cut theorem, that's exactly when the flow is maximum) — it says nothing about *how fast*. If augmenting paths are found via DFS without regard to path length, and capacities are large integers, each augmentation might only increase total flow by 1 unit even though the maximum flow value is large, requiring a number of iterations proportional to the capacity value itself, not the graph's size — a real pathological case with specific adversarial graphs (two paths of capacity `N` and `1` alternately chosen by an unlucky DFS can force `2N` iterations for a max flow of `2N`, when a smarter path choice would finish in 2 iterations). **Edmonds-Karp fixes this by specifically using BFS** to always find the *shortest* (fewest-edges) augmenting path; this guarantees that the number of phases (where the shortest augmenting path length can increase) is bounded by O(V), and within each length-class at most O(E) augmentations saturate an edge, giving the O(VE^2) bound — a genuinely different complexity class from the unbounded-by-capacity pathological case, achieved purely by changing *which* augmenting path is picked, not the fundamental algorithm.

---

## Template code (Python, Java, Go)

```python
from heapq import heappush, heappop
from collections import deque

# Union-Find for Kruskal
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True

# Kruskal — MST via global sort + Union-Find cycle check
def kruskal(n: int, edges: list[tuple[int, int, int]]) -> int:
    edges = sorted(edges, key=lambda e: e[2])  # sort by weight
    uf = UnionFind(n)
    total = 0
    for u, v, w in edges:
        if uf.union(u, v):
            total += w
    return total

# Prim — MST via growing frontier + min-heap
def prim(n: int, adj: list[list[tuple[int, int]]]) -> int:
    visited = [False] * n
    pq = [(0, 0)]  # (weight, vertex)
    total = 0
    while pq:
        w, u = heappop(pq)
        if visited[u]:
            continue
        visited[u] = True
        total += w
        for v, weight in adj[u]:
            if not visited[v]:
                heappush(pq, (weight, v))
    return total

# Edmonds-Karp — max-flow via BFS-found shortest augmenting paths
def edmonds_karp(n: int, capacity: list[list[int]], s: int, t: int) -> int:
    max_flow = 0
    while True:
        parent = [-1] * n
        parent[s] = s
        q = deque([s])
        while q and parent[t] == -1:
            u = q.popleft()
            for v in range(n):
                if parent[v] == -1 and capacity[u][v] > 0:
                    parent[v] = u
                    q.append(v)
        if parent[t] == -1:
            break  # no augmenting path left
        # find bottleneck capacity along the found path
        path_flow = float('inf')
        v = t
        while v != s:
            u = parent[v]
            path_flow = min(path_flow, capacity[u][v])
            v = u
        # update residual capacities
        v = t
        while v != s:
            u = parent[v]
            capacity[u][v] -= path_flow
            capacity[v][u] += path_flow  # reverse residual edge
            v = u
        max_flow += path_flow
    return max_flow

# Bipartite matching — Kuhn's algorithm (augmenting path per left vertex)
def max_bipartite_matching(left_n: int, right_n: int, adj: list[list[int]]) -> int:
    match_right = [-1] * right_n
    def try_augment(u, visited):
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True
                if match_right[v] == -1 or try_augment(match_right[v], visited):
                    match_right[v] = u
                    return True
        return False
    matching = 0
    for u in range(left_n):
        visited = [False] * right_n
        if try_augment(u, visited):
            matching += 1
    return matching
```

```java
import java.util.*;

public class MSTAndFlow {

    // Union-Find
    static int[] parent, rank_;
    static int find(int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }
    static boolean union(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra == rb) return false;
        if (rank_[ra] < rank_[rb]) { int tmp = ra; ra = rb; rb = tmp; }
        parent[rb] = ra;
        if (rank_[ra] == rank_[rb]) rank_[ra]++;
        return true;
    }

    // Kruskal
    static int kruskal(int n, int[][] edges) {
        parent = new int[n]; rank_ = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        Arrays.sort(edges, Comparator.comparingInt(e -> e[2]));
        int total = 0;
        for (int[] e : edges) {
            if (union(e[0], e[1])) total += e[2];
        }
        return total;
    }

    // Prim
    static int prim(int n, List<List<int[]>> adj) {
        boolean[] visited = new boolean[n];
        PriorityQueue<int[]> pq = new PriorityQueue<>(Comparator.comparingInt(a -> a[0]));
        pq.add(new int[]{0, 0});
        int total = 0;
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            int w = top[0], u = top[1];
            if (visited[u]) continue;
            visited[u] = true;
            total += w;
            for (int[] edge : adj.get(u)) {
                int v = edge[0], weight = edge[1];
                if (!visited[v]) pq.add(new int[]{weight, v});
            }
        }
        return total;
    }

    // Edmonds-Karp
    static int edmondsKarp(int n, int[][] capacity, int s, int t) {
        int maxFlow = 0;
        while (true) {
            int[] parentArr = new int[n];
            Arrays.fill(parentArr, -1);
            parentArr[s] = s;
            Deque<Integer> q = new ArrayDeque<>();
            q.add(s);
            while (!q.isEmpty() && parentArr[t] == -1) {
                int u = q.poll();
                for (int v = 0; v < n; v++) {
                    if (parentArr[v] == -1 && capacity[u][v] > 0) {
                        parentArr[v] = u;
                        q.add(v);
                    }
                }
            }
            if (parentArr[t] == -1) break;
            int pathFlow = Integer.MAX_VALUE;
            for (int v = t; v != s; v = parentArr[v]) {
                pathFlow = Math.min(pathFlow, capacity[parentArr[v]][v]);
            }
            for (int v = t; v != s; v = parentArr[v]) {
                capacity[parentArr[v]][v] -= pathFlow;
                capacity[v][parentArr[v]] += pathFlow;
            }
            maxFlow += pathFlow;
        }
        return maxFlow;
    }

    // Bipartite matching — Kuhn's algorithm
    static int maxBipartiteMatching(int leftN, int rightN, List<List<Integer>> adj) {
        int[] matchRight = new int[rightN];
        Arrays.fill(matchRight, -1);
        int matching = 0;
        for (int u = 0; u < leftN; u++) {
            boolean[] visited = new boolean[rightN];
            if (tryAugment(u, adj, visited, matchRight)) matching++;
        }
        return matching;
    }
    static boolean tryAugment(int u, List<List<Integer>> adj, boolean[] visited, int[] matchRight) {
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                visited[v] = true;
                if (matchRight[v] == -1 || tryAugment(matchRight[v], adj, visited, matchRight)) {
                    matchRight[v] = u;
                    return true;
                }
            }
        }
        return false;
    }
}
```

```go
package main

import "sort"

// Union-Find
type UnionFind struct {
    parent, rank []int
}

func NewUnionFind(n int) *UnionFind {
    uf := &UnionFind{parent: make([]int, n), rank: make([]int, n)}
    for i := range uf.parent {
        uf.parent[i] = i
    }
    return uf
}

func (uf *UnionFind) Find(x int) int {
    for uf.parent[x] != x {
        uf.parent[x] = uf.parent[uf.parent[x]]
        x = uf.parent[x]
    }
    return x
}

func (uf *UnionFind) Union(a, b int) bool {
    ra, rb := uf.Find(a), uf.Find(b)
    if ra == rb {
        return false
    }
    if uf.rank[ra] < uf.rank[rb] {
        ra, rb = rb, ra
    }
    uf.parent[rb] = ra
    if uf.rank[ra] == uf.rank[rb] {
        uf.rank[ra]++
    }
    return true
}

// Kruskal
func kruskal(n int, edges [][3]int) int {
    sort.Slice(edges, func(i, j int) bool { return edges[i][2] < edges[j][2] })
    uf := NewUnionFind(n)
    total := 0
    for _, e := range edges {
        if uf.Union(e[0], e[1]) {
            total += e[2]
        }
    }
    return total
}

// Edmonds-Karp
func edmondsKarp(n int, capacity [][]int, s, t int) int {
    maxFlow := 0
    for {
        parent := make([]int, n)
        for i := range parent {
            parent[i] = -1
        }
        parent[s] = s
        queue := []int{s}
        for len(queue) > 0 && parent[t] == -1 {
            u := queue[0]
            queue = queue[1:]
            for v := 0; v < n; v++ {
                if parent[v] == -1 && capacity[u][v] > 0 {
                    parent[v] = u
                    queue = append(queue, v)
                }
            }
        }
        if parent[t] == -1 {
            break
        }
        pathFlow := 1 << 30
        for v := t; v != s; v = parent[v] {
            u := parent[v]
            if capacity[u][v] < pathFlow {
                pathFlow = capacity[u][v]
            }
        }
        for v := t; v != s; v = parent[v] {
            u := parent[v]
            capacity[u][v] -= pathFlow
            capacity[v][u] += pathFlow
        }
        maxFlow += pathFlow
    }
    return maxFlow
}

// Bipartite matching — Kuhn's algorithm
func maxBipartiteMatching(leftN, rightN int, adj [][]int) int {
    matchRight := make([]int, rightN)
    for i := range matchRight {
        matchRight[i] = -1
    }
    var tryAugment func(u int, visited []bool) bool
    tryAugment = func(u int, visited []bool) bool {
        for _, v := range adj[u] {
            if !visited[v] {
                visited[v] = true
                if matchRight[v] == -1 || tryAugment(matchRight[v], visited) {
                    matchRight[v] = u
                    return true
                }
            }
        }
        return false
    }
    matching := 0
    for u := 0; u < leftN; u++ {
        visited := make([]bool, rightN)
        if tryAugment(u, visited) {
            matching++
        }
    }
    return matching
}
```

## Complexity — derived, not asserted

**Kruskal:** dominated by the sort, `O(E log E)` (equivalently `O(E log V)` since `E <= V^2` implies `log E = O(log V)`); Union-Find operations with path compression and union by rank are effectively `O(alpha(V))` per operation (inverse Ackermann, practically constant), contributing negligibly.

**Prim (heap-based):** each of `V` vertices is extracted from the heap once (`O(log V)` each), and each of `E` edges can trigger one heap insertion (`O(log V)` each), giving `O(E log V)` total — asymptotically the same class as Kruskal, so the practical choice is about data format (adjacency list/edge list favors Kruskal, adjacency matrix/dense favors Prim's array-based variant which can achieve `O(V^2)` without a heap at all, beating Kruskal's `O(E log E)` when `E` is close to `V^2`).

**Edmonds-Karp:** `O(VE^2)`. Derivation sketch: the length of the shortest augmenting path is non-decreasing across iterations and takes at most `O(V)` distinct values; for a fixed path-length value, at most `O(E)` augmentations can occur before some edge on every shortest path of that length becomes saturated (forcing the shortest-path length to increase), and each augmentation (a BFS) costs `O(E)`; multiplying `O(V)` length-classes by `O(E)` augmentations per class by `O(E)` cost per augmentation gives `O(VE^2)`.

**Bipartite matching (Kuhn's algorithm, as shown):** `O(V*E)` in the straightforward form (one augmenting-path DFS attempt per left vertex, each DFS potentially touching all edges) — this is a special case of the max-flow reduction bound. Hopcroft-Karp improves this to `O(E * sqrt(V))` by finding a maximal set of *vertex-disjoint* shortest augmenting paths per phase (via one combined BFS+DFS phase) instead of one path at a time, reducing the number of phases needed to `O(sqrt(V))` — a meaningfully better bound at scale that a from-scratch interview answer isn't usually expected to derive but should be named as the production-grade escalation.

---

## The 5 variants interviewers actually ask

1. **Min Cost to Connect All Points (LC 1584).** Direct MST — build a complete graph with Manhattan-distance edge weights, run Kruskal or Prim; Prim's dense variant (`O(V^2)`) is actually the better asymptotic choice here since the graph is complete (`E = V^2`).
2. **Maximum flow between two nodes in a network with capacities.** Direct Edmonds-Karp application; the interviewer is checking correct residual-graph bookkeeping (including reverse residual edges, which many candidates forget, silently breaking correctness on graphs where "undoing" a flow assignment is necessary to reach the true maximum).
3. **Maximum bipartite matching (assign N workers to M jobs, each worker only qualified for some jobs, maximize total assignments).** Kuhn's algorithm or the max-flow reduction; a strong follow-up is naming Hopcroft-Karp as the faster production alternative.
4. **Minimum number of edges to remove so that source and sink are disconnected (min-cut).** Solve via max-flow (Edmonds-Karp), then the min cut's edges are exactly the saturated edges reachable from the source in the final residual graph — the max-flow-min-cut theorem guarantees the numeric answer equals the max-flow value, and reconstructing the actual cut edges requires one more BFS/DFS from the source over the residual graph after the algorithm terminates.
5. **Critical connections / redundant connections in a network (find edges whose removal disconnects the graph, or find the one edge causing a cycle in a near-tree).** This is adjacent territory — bridges (covered in `T02-graph-scc`) for "removal disconnects," or Union-Find cycle detection (Kruskal's own cycle-check mechanism, repurposed) for "find the redundant edge that created a cycle in a graph built one edge at a time" (LC 684, Redundant Connection) — worth distinguishing clearly from MST/max-flow proper.

---

## Common bugs and how this gets written wrong under pressure

- **Forgetting reverse residual edges in max-flow.** Without adding capacity back on the reverse edge after pushing flow forward, the algorithm can't "undo" a suboptimal earlier choice, and can terminate with a flow value strictly less than the true maximum — this is the single most common max-flow bug, and it doesn't crash, it just silently under-reports.
- **Using DFS instead of BFS for Ford-Fulkerson's augmenting-path search without acknowledging the complexity tradeoff.** DFS-found augmenting paths are still *correct* (Ford-Fulkerson's method guarantees correctness regardless of path-finding strategy) but can be pathologically slow on adversarial capacity graphs; presenting a DFS-based implementation as "Edmonds-Karp" is a factual error, since Edmonds-Karp is specifically defined by its BFS shortest-path strategy.
- **Applying Kruskal's Union-Find cycle check without path compression or union by rank.** This doesn't break correctness but degrades the near-constant `alpha(V)` per-operation cost toward `O(log V)` or worse in adversarial insertion orders, a complexity regression that matters at scale even though small test cases won't reveal it.
- **Building the bipartite matching reduction with capacities other than 1 on the source/sink edges.** Bipartite matching specifically requires unit capacities on the source-to-left and right-to-sink edges (each worker matches at most one job and vice versa); using a different capacity silently changes the problem into a different flow question (e.g., allowing one worker to be "used" multiple times).
- **Confusing "minimum spanning tree" with "shortest path tree."** These are different objectives (MST minimizes total edge weight across the whole tree; a shortest-path tree from Dijkstra minimizes distance *from a specific source* to every other vertex) that can produce genuinely different trees on the same weighted graph — conflating them is a conceptual error, not just an implementation slip.
- **Not reconstructing min-cut edges correctly after max-flow terminates.** The min cut is *not* simply "the edges with the smallest capacities" — it's specifically the set of edges from a reachable-from-source vertex (in the final residual graph) to an unreachable one; skipping the final residual-graph BFS/DFS and guessing at the cut edges from capacity values alone produces a wrong answer that happens to have the right numeric total in some cases by coincidence.

---

## Interview questions

### Q1 — Min Cost to Connect All Points (LC 1584): connect all points with minimum total Manhattan distance.
**Testing:** recognizing a geometric problem as plain MST.
**Answer:** Build a complete graph with Manhattan-distance weights, run Prim's dense O(V^2) variant (since the graph is complete, `E=V^2`, making Prim's array-based version asymptotically better than Kruskal's `O(E log E) = O(V^2 log V)`).
**Follow-up trap:** *"Why not Kruskal here?"* — Kruskal would need to sort `O(V^2)` edges, `O(V^2 log V)`, strictly worse than Prim's dense `O(V^2)` on a complete graph; Kruskal remains the better choice only when the edge list is naturally sparse or already given.

### Q2 — Prove the cut property: the minimum-weight edge crossing any cut is in some MST.
**Testing:** the actual exchange-argument proof, not just the statement.
**Answer:** If an MST `T` doesn't contain the minimum crossing edge `e`, adding `e` to `T` creates exactly one cycle, which must cross the same cut at least one more time via some other edge `e'`; since `e` is minimum-weight among crossing edges, `weight(e) <= weight(e')`. Swapping `e'` for `e` keeps `T` a spanning tree with no greater total weight.
**Follow-up trap:** *"How does Prim's algorithm use this property differently from Kruskal's?"* — Prim applies it repeatedly to the specific cut between "vertices already in the tree" and "vertices not yet in the tree"; Kruskal applies it implicitly to the cut between each edge's two Union-Find components at the moment that edge is considered, in global sorted order.

### Q3 — Implement max-flow between a source and sink with given edge capacities.
**Testing:** correct residual-graph bookkeeping, specifically reverse edges.
**Answer:** Edmonds-Karp: repeatedly BFS for the shortest augmenting path in the residual graph, push the bottleneck capacity along it, and update both forward (decrease) and reverse (increase) residual capacities.
**Follow-up trap:** *"What breaks if you forget the reverse residual edges?"* — the algorithm loses the ability to "undo" an earlier flow assignment that turns out to block a better overall solution, and can terminate with a suboptimal total flow — a concrete small example (two paths sharing one edge in opposite logical directions) demonstrates this concretely if pressed.

### Q4 — Why is Edmonds-Karp's complexity O(VE^2) and not dependent on the actual capacity values, unlike naive Ford-Fulkerson?
**Testing:** the phase-based complexity derivation.
**Answer:** The shortest augmenting path length is non-decreasing and takes at most O(V) distinct values; within each length-value, at most O(E) augmentations occur before an edge on every such path saturates, forcing the length to increase; O(V) length-classes times O(E) augmentations times O(E) BFS cost per augmentation gives O(VE^2).
**Follow-up trap:** *"Construct a graph where naive DFS-based Ford-Fulkerson is pathologically slow."* — two source-to-sink paths, one via a shared edge of capacity 1 and the other two edges of capacity N; an unlucky DFS alternates between augmenting 1 unit via the capacity-1 edge (using its reverse residual to "cancel" the other path's use) for up to 2N total iterations, when BFS would find the two large-capacity paths directly in 2 iterations.

### Q5 — Maximum bipartite matching: assign workers to jobs, each worker qualified for a subset of jobs, maximize total assignments.
**Testing:** the flow reduction, and awareness of the matching-specific speedup.
**Answer:** Model as max-flow: source to every worker (capacity 1), worker to qualified jobs (capacity 1), every job to sink (capacity 1); max-flow value equals maximum matching size. Kuhn's algorithm (repeated augmenting-path search per left vertex) computes this directly in O(V*E).
**Follow-up trap:** *"How would you speed this up at scale?"* — Hopcroft-Karp, O(E*sqrt(V)), by finding a maximal set of vertex-disjoint shortest augmenting paths per phase instead of one at a time, reducing the total number of phases needed to O(sqrt(V)).

### Q6 — Find the minimum number of edges whose removal disconnects source from sink.
**Testing:** recognizing this as literally the min-cut side of max-flow-min-cut.
**Answer:** Run Edmonds-Karp; the max-flow value equals the minimum cut's total capacity by the max-flow-min-cut theorem. If all capacities are 1 (edge-disjoint-paths framing), the numeric answer is exactly the number of edges to remove.
**Follow-up trap:** *"How do you find the actual set of edges in the minimum cut, not just its size?"* — after max-flow terminates, do one more BFS/DFS from the source over the final residual graph; the min-cut edges are exactly the original edges going from a reachable vertex to an unreachable vertex in that final residual traversal.

### Q7 — Redundant Connection (LC 684): given a graph built one edge at a time that becomes a tree plus one extra edge, find the extra edge.
**Testing:** recognizing Union-Find's cycle-check mechanism (from Kruskal) applies directly, without needing MST or flow at all.
**Answer:** Process edges in given order with Union-Find; the first edge whose two endpoints are already in the same component is the redundant one.
**Follow-up trap:** *"Is this related to MST or max-flow?"* — not directly; it repurposes the same Union-Find cycle-detection primitive Kruskal uses internally, but the problem itself isn't an MST or flow problem — recognizing which specific sub-tool transfers, rather than forcing the whole algorithm, is the actual signal.

### Q8 — Given a weighted bipartite matching problem (maximize total *value* of assignments, not just count), can you still use Kuhn's algorithm or Hopcroft-Karp directly?
**Testing:** knowing the boundary of unweighted matching algorithms.
**Answer:** No — both assume unit-value (unweighted) matching; a weighted variant needs the Hungarian algorithm (Kuhn-Munkres) or min-cost max-flow, which explicitly account for assignment values/costs rather than just maximizing the count of matched pairs.
**Follow-up trap:** *"What's the complexity of the Hungarian algorithm?"* — O(V^3) in its classic form, a meaningfully higher cost than unweighted matching, which is exactly why recognizing the weighted-vs-unweighted distinction matters before reaching for the faster but inapplicable unweighted algorithms.

### Q9 — MST vs. shortest-path tree from Dijkstra: are they ever the same tree?
**Testing:** whether the two are conflated as "the same kind of tree over a weighted graph."
**Answer:** They can coincide in specific graphs but are different objectives in general — MST minimizes total tree weight with no reference to any particular source, while a shortest-path tree minimizes distance *from one designated source* to every other vertex, which can require using a locally more expensive edge if it shortens the source-specific path.
**Follow-up trap:** *"Construct a graph where they differ."* — a triangle with weights 1, 2, 3: the MST uses the two smallest edges (1 and 2, total 3); a shortest-path tree from the vertex opposite the weight-3 edge might directly use the weight-3 edge if the alternative two-hop path via weights 1+2 is not actually shorter from that specific source's perspective in a directed or asymmetric variant — even in the undirected symmetric case, the shortest-path tree and MST coincide here, but small asymmetric or four-node examples separate them clearly.

### Q10 — Staff-level: your production ride-hailing platform needs driver-rider matching in real time as both driver and rider pools change continuously. Why isn't a straight Hopcroft-Karp/max-flow reduction the right production architecture?
**Testing:** judgment about the gap between a clean textbook reduction and a real online system.
**Answer:** Hopcroft-Karp and generic max-flow assume a static bipartite graph solved once; a real matching platform needs online/incremental matching as new drivers and riders arrive and existing ones become unavailable, which classic offline matching algorithms don't natively support — production systems instead use online bipartite matching heuristics (with competitive-ratio guarantees against the offline optimum) or periodically re-batch and re-solve over short time windows, explicitly trading exact optimality for responsiveness.
**Follow-up trap:** *"Would you ever re-run full batch matching at all in such a system?"* — yes, often on a fixed interval (e.g., every few seconds) over the currently-available pool as a hybrid approach, combining fast online greedy assignment for immediate requests with periodic batch re-optimization to correct accumulated inefficiency — naming this hybrid pattern explicitly is the senior signal.

---

## Red flags that fail you

- Forgetting reverse residual edges in max-flow, silently under-reporting the true maximum.
- Calling a DFS-based augmenting-path implementation "Edmonds-Karp" without the BFS shortest-path requirement that actually defines it.
- Not knowing Ford-Fulkerson's complexity can depend on capacity magnitudes when augmenting paths aren't chosen via BFS.
- Confusing MST with a shortest-path tree, or assuming they're always the same structure.
- Applying Kuhn's algorithm/Hopcroft-Karp to a weighted matching problem without recognizing they only handle the unweighted case.
- Guessing at min-cut edges from capacity values instead of doing the final residual-graph reachability check.

---

## Cheat card

```
KRUSKAL        MST, O(E log E), sort edges + Union-Find cycle check
               best for sparse graphs / edge-list input
PRIM           MST, O(E log V) heap-based, O(V^2) dense array-based
               best for dense graphs / adjacency-matrix input
CUT PROPERTY   min-weight edge crossing ANY cut is in SOME MST (exchange
               argument: swap it in, cycle argument shows no-worse result)
FORD-FULKERSON method: any augmenting path works, correctness guaranteed by
               max-flow-min-cut; complexity can depend on capacity VALUES
               if path choice is naive (DFS) -- pathological slow case exists
EDMONDS-KARP   Ford-Fulkerson + BFS shortest augmenting path -> O(VE^2),
               independent of capacity magnitude
MAX-FLOW       max flow value == min cut capacity (THEOREM)
MIN-CUT        reconstruct cut: BFS/DFS from source in FINAL residual graph;
               cut edges = reachable -> unreachable in original graph
BIPARTITE      unit-capacity source->left->right->sink reduction; Kuhn's
MATCHING       O(V*E); Hopcroft-Karp O(E*sqrt(V)) for unweighted speedup
WEIGHTED       needs Hungarian algorithm / min-cost max-flow, NOT Kuhn's/
MATCHING       Hopcroft-Karp (those assume unweighted/unit-value matching)
WATCH          missing reverse residual edges; DFS mislabeled as Edmonds-
               Karp; MST vs shortest-path-tree conflation; guessing min-cut
```

## Sources

- Kruskal, J. (1956). "On the Shortest Spanning Subtree of a Graph and the Traveling Salesman Problem." Proceedings of the American Mathematical Society, 7(1), 48-50.
- Ford, L.R., Fulkerson, D.R. (1956). "Maximal Flow Through a Network." Canadian Journal of Mathematics, 8, 399-404.
- Edmonds, J., Karp, R.M. (1972). "Theoretical Improvements in Algorithmic Efficiency for Network Flow Problems." Journal of the ACM, 19(2), 248-264.
- Hopcroft, J., Karp, R. (1973). "An n^5/2 Algorithm for Maximum Matchings in Bipartite Graphs." SIAM Journal on Computing, 2(4), 225-231.
- [Min Cost to Connect All Points — LeetCode](https://leetcode.com/problems/min-cost-to-connect-all-points/) — accessed 2026-07-26
- [Redundant Connection — LeetCode](https://leetcode.com/problems/redundant-connection/) — accessed 2026-07-26
- [Max Flow / Min Cut — CP-Algorithms](https://cp-algorithms.com/graph/edmonds_karp.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
