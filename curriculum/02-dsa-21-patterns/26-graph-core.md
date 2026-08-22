# Graph Core: Representations, Traversal Invariants, Cycle & Bipartite Detection

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** T02-p07-bfs, T02-p08-dfs
> **Module id:** `T02-graph-core` · **Tags:** graphs, critical, fundamentals
> **Lab:** `labs/py/26-graph-core/`

## The 30-second version

Every graph problem starts with two choices that determine everything downstream: how you represent the graph, and which traversal invariant you can actually trust. Adjacency list — O(V+E) space, O(1) to iterate a node's neighbors, O(degree) to check a specific edge — is the default for anything sparse (`E` closer to `V` than `V^2`), which is almost every real-world and interview graph. Adjacency matrix — O(V^2) space, O(1) edge-existence check, but O(V) just to list a node's neighbors — is only correct to reach for when the graph is dense or you need frequent O(1) edge-existence checks (Floyd-Warshall's DP, for instance, is naturally matrix-shaped). BFS gives you the *shortest path in edge count* on an unweighted graph and processes nodes in strict, non-decreasing distance layers — that layer invariant is what everything built on top of BFS (multi-source BFS, 0-1 BFS) depends on. DFS gives you a full exploration order encoded in **three-color state** (white/unvisited, gray/on the current recursion stack, black/fully finished) — and that gray state is the entire mechanism behind cycle detection in a directed graph, which is why undirected and directed cycle detection are genuinely different algorithms, not the same one with a flag flipped. Bipartite checking is 2-coloring during BFS/DFS: a graph is bipartite if and only if it contains no odd-length cycle, and the coloring attempt itself is the proof — if two adjacent nodes are ever forced to the same color, you've found an odd cycle.

## Why this gets asked

This is the module that catches candidates who've memorized "BFS finds shortest path, DFS finds cycles" without understanding *why*, and it's asked because that gap shows up immediately the moment a graph problem deviates even slightly from the textbook shape (weighted edges, a directed instead of undirected graph, multiple components). Interviewers who've built dependency resolvers, build systems, or workflow engines have personally hit the directed-vs-undirected cycle detection distinction in production — a "gray node" (currently being processed, on the call stack) revisited in a directed graph means a real cycle (a genuine circular dependency), while in an undirected graph you must additionally exclude the trivial "cycle" of immediately walking back along the edge you just came from, which is a different bug class entirely (forgetting to track the parent edge). Getting this wrong in an undirected-graph cycle check produces false positives on every single edge, which is the kind of bug that passes a trivial test and fails immediately on the first real input.

---

## Lineage: past → present → future

**What came before.** Before graphs were treated as a first-class object with standardized representations, most traversal problems were solved ad hoc with explicit recursive functions over problem-specific structures (trees, grids) without a general adjacency abstraction; BFS traces to Moore's 1959 maze-solving algorithm and Lee's 1961 routing algorithm for circuit design (both independently discovered the same layer-by-layer shortest-path idea for unweighted graphs), while DFS's formalization as a general graph algorithm with the three-color scheme is usually attributed to Tarjan's foundational 1970s work connecting it to strong connectivity, biconnectivity, and planarity testing — DFS existed informally long before, but Tarjan's papers are what turned "just recurse into neighbors" into an algorithm with provable structural guarantees (discovery/finish times, the parenthesis theorem, edge classification).

**Where it stands now.** Adjacency list with an array/hashmap-of-neighbor-lists is the overwhelming default in production systems (dependency graphs, social graphs, routing tables) because almost every real graph is sparse; adjacency matrices survive specifically in dense-graph algorithms (Floyd-Warshall) and in small, fixed-size problems (grid graphs where the matrix *is* naturally the representation, like a maze). The union of BFS/DFS with edge classification (tree edges, back edges, forward edges, cross edges — the last two only meaningful in directed graphs) is settled, closed theory; the live practical question is representation choice at scale (adjacency list with hashmap neighbor lookup vs. sorted arrays vs. compressed sparse row (CSR) format used in graph databases and large-scale graph processing frameworks like Pregel/GraphX, where CSR's cache-friendly flat-array layout matters more than the asymptotic complexity class once graphs reach billions of edges).

**Where it's heading.** No new foundational traversal algorithm is expected. The applied direction is representation engineering for scale — CSR and other flat, cache-friendly layouts for graph databases and GNN (graph neural network) input pipelines, and incremental/streaming graph algorithms (maintaining cycle-detection or connectivity invariants as edges are added/removed in real time, relevant to build systems and dependency resolvers that must react to a changing dependency graph without a full re-scan). Treat streaming graph maintenance as a real, occasionally-asked staff-level extension, not speculative trivia.

---

## Mental model

Adjacency list: an array (or map) of buckets, one per vertex, each bucket holding that vertex's neighbors — think of it as a phone book where each entry lists only who that person actually calls.

```
adj[0] = [1, 2]
adj[1] = [0, 3]
adj[2] = [0]
adj[3] = [1]
       0
      / \
     1   2
     |
     3
```

Adjacency matrix: a full V×V grid where `matrix[i][j] = 1` (or weight) if an edge exists — think of it as a spreadsheet where every possible pair gets a cell, even the overwhelming majority that will be empty in a sparse graph.

BFS's invariant is layers: everything at distance `d` from the source is fully processed before anything at distance `d+1` is even discovered, which is exactly why the first time you reach a node is the shortest path to it (unweighted).

```
Source S, BFS layers:
Layer 0: [S]
Layer 1: [A, B]        <- all neighbors of S
Layer 2: [C, D, E]     <- all neighbors of A,B not already seen
The queue enforces this: everything enqueued in layer d is dequeued and
fully expanded before anything from layer d+1 is dequeued.
```

DFS's invariant is the three-color recursion-stack state: a node is **white** before you visit it, **gray** while it's on the current DFS path (an active ancestor in the recursion), and **black** once you've fully finished exploring everything reachable from it.

```
DFS descent:              DFS backtrack:
S (gray)                  S (black)  <- fully done
 \                          \
  A (gray)                   A (black)
   \                          \
    B (gray, currently here)   B (black)

A back edge — an edge to a GRAY node — is the signature of a cycle in a
directed graph, because it means you've looped back to something still
on your current path, not just something you've seen before.
```

---

## Recognition heuristics

- **"Number of connections is much smaller than V^2"** (most interview and real-world graphs) → adjacency list, O(V+E) space.
- **"Need O(1) edge-existence check" or "the algorithm is naturally matrix-shaped" (Floyd-Warshall, dense flow networks)** → adjacency matrix.
- **"Shortest path, unweighted"** → BFS, and the answer falls directly out of the layer at which the target is first discovered.
- **"Explore/enumerate all paths, connected components, or a DFS-based structural property (topological order, cycle, bridges, articulation points, SCC)"** → DFS, and the three-color state is the mechanism behind almost all of these.
- **"Detect a cycle"** — the tell for *which* cycle detection algorithm is whether the graph is directed or undirected; conflating the two is the single most common bug in this whole area (see below).
- **"Can this be split into two groups such that no edge exists within a group"**, **"is this graph 2-colorable"**, **"assign people to two teams so that no pair of rivals ends up on the same team"** → bipartite check via BFS/DFS 2-coloring.
- **"Multiple disconnected components, process each"** → wrap traversal in an outer loop over all vertices, only starting a new BFS/DFS from any vertex not yet visited — a step candidates forget when a graph isn't guaranteed connected.
- **"0/1 weighted edges (only two possible weights)"** → 0-1 BFS using a deque (push 0-weight edges to the front, 1-weight edges to the back) instead of full Dijkstra, a strictly faster specialization worth naming.

---

## How it actually works — cycle detection, directed vs undirected, derived precisely

**Undirected cycle detection via DFS.** A cycle exists if, during DFS, you encounter an edge to an already-visited vertex that is *not* the parent you just came from. The parent exclusion is essential: every undirected edge `(u,v)` is traversed from both directions in an adjacency-list representation, so without excluding the parent, every single edge looks like a "cycle" (you'd immediately re-see `u` from `v`). This is why undirected cycle detection needs to track "the edge I arrived from," not just "the set of visited nodes."

```python
def has_cycle_undirected(n, adj):
    visited = [False] * n
    def dfs(u, parent):
        visited[u] = True
        for v in adj[u]:
            if not visited[v]:
                if dfs(v, u):
                    return True
            elif v != parent:  # visited AND not where we came from -> cycle
                return True
        return False
    return any(not visited[i] and dfs(i, -1) for i in range(n))
```

**Directed cycle detection via DFS three-coloring.** A cycle exists if and only if DFS ever encounters an edge to a **gray** node (a node currently on the active recursion stack, i.e., an ancestor in the current DFS path) — this is called a **back edge**, and it's the unique signature of a cycle in a directed graph. Encountering an edge to a **black** node (fully finished, not an ancestor) is completely fine in a directed graph — it's a "cross edge" or "forward edge," representing a legitimate DAG-shaped convergence, not a cycle. This is the core reason directed and undirected cycle detection are different algorithms: undirected only needs a binary visited/unvisited distinction (plus the parent exclusion); directed needs the three-way white/gray/black distinction, because "already visited" alone can't distinguish "still an active ancestor" from "a completed, unrelated branch."

```python
def has_cycle_directed(n, adj):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n
    def dfs(u):
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return True          # back edge -> real cycle
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False
    return any(color[i] == WHITE and dfs(i) for i in range(n))
```

**Bipartite checking is 2-coloring, and its correctness is exactly "no odd cycle."** Assign the source color 0, and every neighbor the opposite color of its parent, via BFS or DFS. If you ever try to color a node that's already colored and the forced color conflicts with its existing color, the graph is not bipartite — and that specific conflict, traced back, identifies an odd-length cycle. This is a real theorem, not a heuristic: a graph is bipartite **if and only if** it has no odd-length cycle, so the greedy 2-coloring attempt is a complete decision procedure, not an approximation.

---

## Template code (Python, Java, Go)

```python
from collections import deque

# Adjacency list representation
def build_adj_list(n: int, edges: list[tuple[int, int]], directed: bool = False):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        if not directed:
            adj[v].append(u)
    return adj

# BFS — shortest path in edge count, unweighted
def bfs_shortest(n: int, adj: list[list[int]], src: int) -> list[int]:
    dist = [-1] * n
    dist[src] = 0
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist

# Undirected cycle detection — must track parent, not just visited
def has_cycle_undirected(n: int, adj: list[list[int]]) -> bool:
    visited = [False] * n
    def dfs(u, parent):
        visited[u] = True
        for v in adj[u]:
            if not visited[v]:
                if dfs(v, u):
                    return True
            elif v != parent:
                return True
        return False
    return any(not visited[i] and dfs(i, -1) for i in range(n))

# Directed cycle detection — three-color, back edge = gray revisit
def has_cycle_directed(n: int, adj: list[list[int]]) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n
    def dfs(u):
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False
    return any(color[i] == WHITE and dfs(i) for i in range(n))

# Bipartite check — 2-coloring via BFS
def is_bipartite(n: int, adj: list[list[int]]) -> bool:
    color = [-1] * n
    for start in range(n):
        if color[start] != -1:
            continue
        color[start] = 0
        q = deque([start])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if color[v] == -1:
                    color[v] = 1 - color[u]
                    q.append(v)
                elif color[v] == color[u]:
                    return False
    return True
```

```java
import java.util.*;

public class GraphCore {

    // BFS
    static int[] bfsShortest(int n, List<List<Integer>> adj, int src) {
        int[] dist = new int[n];
        Arrays.fill(dist, -1);
        dist[src] = 0;
        Deque<Integer> q = new ArrayDeque<>();
        q.add(src);
        while (!q.isEmpty()) {
            int u = q.poll();
            for (int v : adj.get(u)) {
                if (dist[v] == -1) {
                    dist[v] = dist[u] + 1;
                    q.add(v);
                }
            }
        }
        return dist;
    }

    // Undirected cycle detection
    static boolean hasCycleUndirected(int n, List<List<Integer>> adj) {
        boolean[] visited = new boolean[n];
        for (int i = 0; i < n; i++) {
            if (!visited[i] && dfsUndirected(i, -1, adj, visited)) return true;
        }
        return false;
    }
    static boolean dfsUndirected(int u, int parent, List<List<Integer>> adj, boolean[] visited) {
        visited[u] = true;
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                if (dfsUndirected(v, u, adj, visited)) return true;
            } else if (v != parent) {
                return true;
            }
        }
        return false;
    }

    // Directed cycle detection — three-color
    static final int WHITE = 0, GRAY = 1, BLACK = 2;
    static boolean hasCycleDirected(int n, List<List<Integer>> adj) {
        int[] color = new int[n];
        for (int i = 0; i < n; i++) {
            if (color[i] == WHITE && dfsDirected(i, adj, color)) return true;
        }
        return false;
    }
    static boolean dfsDirected(int u, List<List<Integer>> adj, int[] color) {
        color[u] = GRAY;
        for (int v : adj.get(u)) {
            if (color[v] == GRAY) return true;
            if (color[v] == WHITE && dfsDirected(v, adj, color)) return true;
        }
        color[u] = BLACK;
        return false;
    }

    // Bipartite check
    static boolean isBipartite(int n, List<List<Integer>> adj) {
        int[] color = new int[n];
        Arrays.fill(color, -1);
        for (int start = 0; start < n; start++) {
            if (color[start] != -1) continue;
            color[start] = 0;
            Deque<Integer> q = new ArrayDeque<>();
            q.add(start);
            while (!q.isEmpty()) {
                int u = q.poll();
                for (int v : adj.get(u)) {
                    if (color[v] == -1) {
                        color[v] = 1 - color[u];
                        q.add(v);
                    } else if (color[v] == color[u]) {
                        return false;
                    }
                }
            }
        }
        return true;
    }
}
```

```go
package main

// BFS
func bfsShortest(n int, adj [][]int, src int) []int {
    dist := make([]int, n)
    for i := range dist {
        dist[i] = -1
    }
    dist[src] = 0
    queue := []int{src}
    for len(queue) > 0 {
        u := queue[0]
        queue = queue[1:]
        for _, v := range adj[u] {
            if dist[v] == -1 {
                dist[v] = dist[u] + 1
                queue = append(queue, v)
            }
        }
    }
    return dist
}

// Undirected cycle detection
func hasCycleUndirected(n int, adj [][]int) bool {
    visited := make([]bool, n)
    var dfs func(u, parent int) bool
    dfs = func(u, parent int) bool {
        visited[u] = true
        for _, v := range adj[u] {
            if !visited[v] {
                if dfs(v, u) {
                    return true
                }
            } else if v != parent {
                return true
            }
        }
        return false
    }
    for i := 0; i < n; i++ {
        if !visited[i] && dfs(i, -1) {
            return true
        }
    }
    return false
}

// Directed cycle detection — three-color
const (
    white = 0
    gray  = 1
    black = 2
)

func hasCycleDirected(n int, adj [][]int) bool {
    color := make([]int, n)
    var dfs func(u int) bool
    dfs = func(u int) bool {
        color[u] = gray
        for _, v := range adj[u] {
            if color[v] == gray {
                return true
            }
            if color[v] == white && dfs(v) {
                return true
            }
        }
        color[u] = black
        return false
    }
    for i := 0; i < n; i++ {
        if color[i] == white && dfs(i) {
            return true
        }
    }
    return false
}

// Bipartite check
func isBipartite(n int, adj [][]int) bool {
    color := make([]int, n)
    for i := range color {
        color[i] = -1
    }
    for start := 0; start < n; start++ {
        if color[start] != -1 {
            continue
        }
        color[start] = 0
        queue := []int{start}
        for len(queue) > 0 {
            u := queue[0]
            queue = queue[1:]
            for _, v := range adj[u] {
                if color[v] == -1 {
                    color[v] = 1 - color[u]
                    queue = append(queue, v)
                } else if color[v] == color[u] {
                    return false
                }
            }
        }
    }
    return true
}
```

## Complexity — derived, not asserted

**Adjacency list vs matrix, space:** list is `O(V+E)` — one slot per vertex plus one entry per edge (two for undirected, stored twice); matrix is `O(V^2)` regardless of how many edges actually exist. At `V=10,000` with a sparse graph (`E ~ 20,000`), a list needs on the order of `30,000` total entries while a matrix needs `10^8` cells — a four-order-of-magnitude difference that makes matrix representation actively wrong at that scale unless the graph really is dense.

**BFS/DFS traversal:** both are `O(V+E)` — every vertex is dequeued/visited exactly once (`O(V)`), and every edge is examined exactly once (twice for undirected, once per direction) during the scan of each vertex's neighbor list (`O(E)`), so the two terms sum linearly rather than multiply.

**Cycle detection (both directed and undirected):** `O(V+E)`, since it's a single DFS pass with O(1) extra work per edge (a color/parent check).

**Bipartite check:** `O(V+E)`, a single BFS/DFS pass with O(1) coloring work per edge, plus the outer loop over disconnected components which doesn't change the asymptotic bound since every vertex and edge is still visited exactly once in total across all components.

---

## The 5 variants interviewers actually ask

1. **Course Schedule (LC 207/210): can all courses be finished given prerequisites?** Directed cycle detection — a prerequisite graph is a DAG if and only if it has no cycle; the three-color DFS (or Kahn's BFS-based topological sort, cross-referenced in `T02-p17-topological-sort`) both work.
2. **Is Graph Bipartite? (LC 785).** Direct 2-coloring application, including the outer loop over disconnected components that many candidates forget.
3. **Number of Connected Components / Number of Provinces (LC 547).** Plain traversal (BFS or DFS or Union-Find) with the "for every unvisited vertex, start a new traversal" outer loop — a baseline check on whether you handle disconnected graphs correctly by default rather than assuming connectivity.
4. **Detect Cycle in an Undirected Graph, given as an edge list (not adjacency list).** Tests whether you build the adjacency representation correctly first (undirected edges must be added both ways) and whether you remember the parent-exclusion rule; also frequently framed as a Union-Find problem (an edge connecting two already-same-component nodes is a cycle) as an alternative to DFS.
5. **Possible Bipartition (LC 886): given "dislike" pairs, can people be split into two groups with no disliking pair in the same group?** Bipartite check in a real-world-flavored disguise — the tell is "split into two groups such that no [constraint] pair ends up together," which is 2-coloring regardless of the story wrapped around it.

---

## Common bugs and how this gets written wrong under pressure

- **Forgetting the parent exclusion in undirected cycle detection.** Without it, every single edge looks like a cycle (walking from `u` to `v` and then immediately re-examining the edge back to `u`, which is trivially "visited"), and the function returns `true` on any graph with at least one edge — a bug that looks like a cycle-detector but is actually just an edge-existence detector.
- **Using binary visited/unvisited instead of three-color state for directed cycle detection.** A directed graph can legitimately have an edge to an already-fully-processed (black) node without that being a cycle — it's a valid DAG convergence; treating "visited" as sufficient produces false positives on any DAG with a diamond shape (two paths converging on the same downstream node).
- **Forgetting the outer loop over all vertices to handle disconnected components.** A single BFS/DFS from one starting vertex silently misses every other component, which passes small hand-checked examples (often accidentally fully connected) and fails the moment a real graph has more than one component.
- **Choosing an adjacency matrix by default without checking density.** This produces a working-but-wildly-inefficient solution that times out on large sparse inputs — not a correctness bug, but a complexity-class bug that's just as disqualifying in an interview.
- **Adding a directed edge both ways when building the adjacency list for a directed graph** (copy-pasting the undirected-graph construction code) — silently turns a DAG into a graph with trivial 2-cycles everywhere, breaking every downstream directed-graph algorithm (topological sort, directed cycle detection) in a way that's easy to miss because the resulting structure still "looks like a graph."
- **In bipartite checking, coloring a node and immediately assuming success without checking for a color conflict on an already-colored neighbor.** Skipping the `elif color[v] == color[u]: return False` branch silently accepts non-bipartite graphs as bipartite, because the algorithm degenerates into "just assign colors" without ever validating the assignment.

---

## Interview questions

### Q1 — Course Schedule (LC 207): can you finish all courses given prerequisite pairs?
**Testing:** directed cycle detection, correctly distinguishing it from the undirected case.
**Answer:** Build a directed graph from prerequisites, run three-color DFS (or Kahn's algorithm); a cycle means an impossible schedule.
**Follow-up trap:** *"Why can't you just check 'visited' like you would for an undirected graph?"* — because a directed graph can have a valid edge into an already-fully-processed node (a DAG convergence) that isn't a cycle at all; only an edge into a *currently active* (gray) ancestor is a real cycle.

### Q2 — Is Graph Bipartite? (LC 785).
**Testing:** direct 2-coloring, plus disconnected-component handling.
**Answer:** BFS/DFS 2-coloring; a conflict (adjacent nodes forced to the same color) means not bipartite. Loop over all vertices to catch every component.
**Follow-up trap:** *"What's the exact mathematical condition for a graph to be bipartite?"* — no odd-length cycle; the 2-coloring attempt is a complete decision procedure for exactly this property, not a heuristic approximation.

### Q3 — Detect a cycle in an undirected graph.
**Testing:** the parent-exclusion mechanism.
**Answer:** DFS tracking the parent; a visited neighbor that isn't the parent means a cycle.
**Follow-up trap:** *"Why does this fail if you forget to exclude the parent?"* — every edge is stored both ways in an undirected adjacency list, so without excluding the parent, walking from `u` to `v` and then seeing `u` again from `v` looks identical to a real cycle, producing a false positive on every edge in the graph.

### Q4 — Number of Provinces (LC 547): count connected components.
**Testing:** whether you handle multiple components by default.
**Answer:** For every unvisited vertex, start a new BFS/DFS/Union-Find, incrementing a component counter; total traversal work is still O(V+E) across all components combined.
**Follow-up trap:** *"When would Union-Find be preferable to BFS/DFS here?"* — when edges arrive incrementally (online/streaming) and you need the component count updated after each edge, Union-Find with path compression and union by rank gives near-O(1) amortized updates per edge, which a from-scratch BFS/DFS re-run would not.

### Q5 — Possible Bipartition (LC 886): split people into two groups given "dislike" pairs.
**Testing:** recognizing bipartite checking under an unfamiliar problem framing.
**Answer:** Build a graph from dislike pairs, run the same 2-coloring bipartite check.
**Follow-up trap:** *"What if some people have no listed dislikes at all?"* — they form isolated components (or isolated vertices); the outer loop over unvisited vertices handles them automatically, and an isolated vertex is trivially bipartite (no constraint to violate).

### Q6 — Given V=100,000 and E=150,000, would you use an adjacency list or matrix, and why?
**Testing:** recognizing sparse vs dense and its real complexity impact, not just a memorized rule.
**Answer:** Adjacency list — the graph is sparse (E close to V, not V^2), and a matrix would require 10^10 cells, computationally and memory-wise infeasible, versus a list's roughly 250,000-ish total entries.
**Follow-up trap:** *"When would you actually choose a matrix at this scale?"* — essentially never at this scale unless the algorithm itself is fundamentally matrix-shaped (Floyd-Warshall) and V is small enough (a few hundred to low thousands) that V^2 remains tractable; density and algorithm shape both have to justify it.

### Q7 — Multi-source BFS: given several starting points simultaneously (e.g., "rotten oranges spread to adjacent fresh ones each minute"), find the time for the effect to reach everywhere.
**Testing:** extending the BFS layer invariant to multiple sources at once.
**Answer:** Initialize the BFS queue with all source nodes at distance 0 simultaneously, then run standard BFS; the layer invariant still holds because "distance from the nearest source" is exactly what a multi-source BFS computes when all sources start in the queue together.
**Follow-up trap:** *"Why is this different from running BFS once per source and taking the minimum?"* — running BFS once per source and taking the minimum costs O(k*(V+E)) for k sources; multi-source BFS in one pass costs O(V+E) total, because the queue already interleaves all sources' frontiers correctly without needing separate full traversals.

### Q8 — 0-1 BFS: edges have weight either 0 or 1. Find shortest path faster than Dijkstra.
**Testing:** knowing a real Dijkstra specialization exists and when to use it.
**Answer:** Use a deque instead of a priority queue: push 0-weight edges to the front (they don't increase the "layer"), push 1-weight edges to the back; this maintains a sorted-by-distance invariant without needing a full O(log V) heap operation per edge.
**Follow-up trap:** *"What's the complexity gain over Dijkstra here?"* — 0-1 BFS is O(V+E) versus Dijkstra's O((V+E) log V); the log factor disappears because the deque, not a heap, is sufficient to maintain sorted order when only two distinct weights exist.

### Q9 — Explain DFS edge classification (tree, back, forward, cross edges) and which ones are only meaningful in directed graphs.
**Testing:** depth on the DFS structural theory beyond "it visits nodes."
**Answer:** Tree edges are edges actually used to first discover a new (white) vertex. Back edges go to an ancestor (gray) — the cycle signature. Forward edges go to an already-finished (black) descendant in the same DFS tree — only possible in directed graphs. Cross edges go to an already-finished (black) vertex in a different DFS tree or subtree, with no ancestor-descendant relationship — also only meaningful in directed graphs, since in an undirected graph every non-tree edge is provably a back edge (there's no way to reach an already-fully-explored subtree via a "new" edge without it having been a back edge from that subtree's perspective first).
**Follow-up trap:** *"Why can't undirected graphs have cross edges?"* — because DFS in an undirected graph, by the time it finishes exploring a subtree, has already examined every edge leaving that subtree (since edges are bidirectional in the representation), so any edge to a fully-finished undirected component must have already been classified as a back edge during that component's own exploration.

### Q10 — Design a streaming cycle-detection system for a build/dependency graph where edges (dependencies) are added one at a time, and you must reject any edge that would create a cycle.
**Testing:** staff-level extension — incremental maintenance instead of a full re-scan per edge.
**Answer:** Union-Find (disjoint set union) with path compression and union by rank detects cycles in undirected graphs incrementally in near-O(1) amortized per edge (if the two endpoints are already in the same set, adding the edge creates a cycle). For directed graphs (the actual dependency-resolution case), Union-Find alone isn't sufficient since directed cycles aren't the same as "same connected component" — you'd maintain a topological order incrementally (e.g., via the PK algorithm for online topological sorting) or simply re-run a bounded local DFS from the new edge's target to check if it can reach the new edge's source.
**Follow-up trap:** *"Why doesn't plain Union-Find work for the real (directed) dependency case?"* — Union-Find only tracks undirected connectivity; two nodes being "in the same component" doesn't tell you whether a directed path exists in a specific direction, which is exactly what matters for detecting a circular *dependency* (A depends on B depends on A) as opposed to just "A and B are connected somehow."

---

## Red flags that fail you

- Forgetting the parent-exclusion check in undirected cycle detection and reporting a cycle on every edge.
- Using binary visited/unvisited state for directed cycle detection instead of three-color, producing false positives on valid DAGs.
- Not looping over all vertices to handle disconnected components, silently missing entire subgraphs.
- Defaulting to an adjacency matrix on a large sparse graph without justifying the space cost.
- Adding directed edges both ways by habit from undirected-graph code, corrupting every downstream directed algorithm.
- Not knowing that bipartite-ness is exactly "no odd cycle," treating the 2-coloring check as a heuristic instead of a complete decision procedure.

---

## Cheat card

```
ADJ LIST       O(V+E) space, O(deg) neighbor iteration -- default for sparse
ADJ MATRIX     O(V^2) space, O(1) edge check -- only for dense graphs or
               matrix-shaped algorithms (Floyd-Warshall)
BFS            O(V+E), layer invariant, shortest path in EDGE COUNT
               (unweighted only); multi-source: seed queue with all sources
DFS            O(V+E), three-color: WHITE (unvisited) / GRAY (on stack,
               active ancestor) / BLACK (fully finished)
UNDIRECTED     cycle = visited neighbor != parent (must exclude parent edge)
CYCLE
DIRECTED       cycle = edge to a GRAY node (back edge); edge to BLACK is
CYCLE          fine (forward/cross edge, valid DAG convergence)
BIPARTITE      2-color via BFS/DFS; conflict = not bipartite
CHECK          THEOREM: bipartite <=> no odd-length cycle
0-1 BFS        deque instead of heap when weights in {0,1}: O(V+E) vs
               Dijkstra's O((V+E) log V)
WATCH          parent exclusion (undirected); 2-color vs 3-color mixup;
               disconnected components; matrix on sparse V^2 blowup
```

## Sources

- Cormen, Leiserson, Rivest, Stein. *Introduction to Algorithms* (CLRS), Chapter 22: Elementary Graph Algorithms.
- Tarjan, R. (1972). "Depth-First Search and Linear Graph Algorithms." SIAM Journal on Computing, 1(2), 146-160.
- Moore, E.F. (1959). "The Shortest Path Through a Maze." Proceedings of the International Symposium on the Theory of Switching.
- [Course Schedule — LeetCode](https://leetcode.com/problems/course-schedule/) — accessed 2026-07-26
- [Is Graph Bipartite? — LeetCode](https://leetcode.com/problems/is-graph-bipartite/) — accessed 2026-07-26
- [Number of Provinces — LeetCode](https://leetcode.com/problems/number-of-provinces/) — accessed 2026-07-26
- [Possible Bipartition — LeetCode](https://leetcode.com/problems/possible-bipartition/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
