# Pattern: Topological Sort

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** T02-p07-bfs, T02-p08-dfs, graphs
> **Module id:** `T02-p17-topological-sort` · **Tags:** pattern, graph

## The 30-second version

Topological sort produces a linear ordering of a directed acyclic graph's (DAG's) nodes such that every edge `u -> v` places `u` before `v` — it's the pattern for "these tasks have dependencies, give me a valid execution order," and it only exists at all if the graph has no cycle. There are two standard implementations: **Kahn's algorithm** (BFS, repeatedly peel off nodes with in-degree zero) and **DFS-based** (postorder, then reverse). Both are O(V+E). The single most useful side effect is free cycle detection: if Kahn's algorithm processes fewer than `V` nodes before its queue empties, or DFS-based sort finds a back-edge (a node still "in progress" on the recursion stack being revisited), the graph has a cycle and no valid ordering exists — which is precisely how build systems, package managers, and course-prerequisite checkers detect an impossible dependency graph. Recognize it whenever a problem gives you "must happen before" pairs, prerequisite lists, or build/task dependencies and asks for a valid order, whether one exists, or all possible orders.

## Why this gets asked

It tests whether you can model a "must come before" relationship as a directed graph rather than trying to sort or greedily schedule your way through it, and whether you know that cycle detection is a byproduct of the same traversal rather than a separate algorithm bolted on. Interviewers who've maintained build systems (Bazel/Buck target graphs), package managers (npm/pip resolving a dependency DAG), workflow orchestrators (Airflow DAGs, CI pipeline stages), or migration ordering (schema migrations, deploy ordering across microservices) have personally debugged the production failure this models directly: a circular dependency that deadlocks a build or creates an unresolvable install order, and the fix in every one of those systems is exactly "run topological sort, and if it can't complete, report the cycle."

---

## Lineage: past → present → future

**What came before.** Before it had a name in CS curricula, this is literally how PERT/CPM (Program Evaluation and Review Technique / Critical Path Method) scheduled construction and manufacturing projects starting in the late 1950s — activities with prerequisites, laid out as a dependency network, ordered so no task starts before its predecessors finish. Kahn's algorithm (Arthur Kahn, 1962) formalized the in-degree-peeling approach specifically for this scheduling context. Before dependency-DAG thinking was standard, build tools scheduled compilation in a fixed or manually-specified order, which broke the moment a codebase's module dependencies didn't match that fixed order — the pain that motivated tools like `make` to build an explicit dependency graph and topologically order recompilation instead of trusting a hardcoded sequence.

**Where it stands now.** Fully settled: Kahn's (BFS/in-degree) and DFS-postorder-reversed are both textbook-standard, run in O(V+E), and produce different-but-equally-valid orderings when multiple valid orders exist (topological order is generally not unique unless the DAG happens to be a total order already). The live "disagreement," such as it is, is purely a style/tooling choice: Kahn's is usually preferred in interviews and in production schedulers because it naturally exposes cycle detection via a simple count comparison and doesn't need recursion depth management; DFS-based is preferred when you're already doing a DFS pass for something else and want the ordering as a side effect.

**Where it's heading.** No open research question at the interview level — this is closed 60-year-old graph theory. Where it's actively evolving: large-scale build systems (Bazel, Buck2, Nx) and workflow orchestrators (Airflow, Dagster, Temporal) run topological scheduling over DAGs with tens of thousands of nodes and need it combined with **parallel** scheduling (not just *an* order, but the maximum-parallelism layering — nodes with no dependency on each other run concurrently, which is "level-order" topological sort, processing entire in-degree-zero frontiers per BFS layer rather than one node at a time) and with **incremental** re-computation (only re-topo-sort the affected subgraph when the DAG changes slightly, rather than recomputing the whole order from scratch). Those are systems-engineering extensions of the same core algorithm, not new algorithms.

---

## Mental model

Peel the graph like an onion: repeatedly remove every node that currently has no unsatisfied dependency (in-degree zero), record it, then update the remaining graph and repeat.

```
courses: 0 <- 1 <- 3        (arrow means "must take before")
         0 <- 2 <- 3
edges: 1->0, 2->0, 3->1, 3->2   (u->v means u is prereq of v... here read as "take u, then v")

in-degree:  0:2   1:1   2:1   3:0

round 1: in-degree 0 -> node 3.  remove 3, decrement 1 and 2's in-degree -> 1:0, 2:0
round 2: in-degree 0 -> nodes 1,2 (either order valid).  remove both, decrement 0's in-degree -> 0:0
round 3: in-degree 0 -> node 0.

valid order: 3, 1, 2, 0   (or 3, 2, 1, 0 — both are correct topological orders)
```

If at any point no node has in-degree zero but nodes remain unprocessed, there's a cycle among them — that's the entire cycle-detection mechanism, no separate pass needed.

---

## Recognition heuristics

- **"Course A requires course B first"** / **prerequisite lists** — the canonical framing (Course Schedule, LC 207/210).
- **"Build order," "task dependencies," "compile in an order that respects dependencies"** — build-system framing.
- **"Is there a valid order at all?"** — cycle detection is the actual ask, ordering is secondary.
- **"Alphabet order from a sorted list of words in an unknown language"** — Alien Dictionary; derive edges from adjacent-word comparisons, then topo-sort the derived graph. This is the variant most likely to be missed because the graph isn't handed to you — you build it from indirect evidence first.
- **"Minimum height trees" / "find all possible roots that minimize depth"** — a topological-sort-adjacent peeling technique (repeatedly strip leaves) rather than dependency ordering, but uses the identical in-degree-peeling mechanics.
- **A DAG with an explicit "no valid order may exist" possibility** stated in the prompt — that's the interviewer flagging that cycle detection, not just ordering, is part of the expected answer.

If the graph is undirected, or edges don't represent a "must come before" relationship, this pattern doesn't apply — reach for plain BFS/DFS (`T02-p07-bfs`, `T02-p08-dfs`) or union-find (`T02-p19-union-find`) instead.

---

## How it actually works

**Kahn's algorithm (BFS-based).**
1. Compute in-degree (number of incoming edges) for every node.
2. Push every node with in-degree 0 into a queue.
3. Pop a node, append it to the result order, and for every neighbor, decrement its in-degree; if a neighbor's in-degree hits 0, push it.
4. Repeat until the queue is empty.
5. If the result order's length equals `V`, it's a valid topological order. If it's shorter, the unprocessed nodes are all part of one or more cycles.

**DFS-based (postorder, then reverse).**
1. Run DFS from every unvisited node, tracking three states per node: unvisited, in-progress (on the current recursion stack), visited (fully processed).
2. When DFS finishes exploring all of a node's neighbors, push that node onto a stack (this is postorder — a node is only finalized after everything reachable from it is finalized).
3. If DFS ever revisits a node that's currently in-progress (still on the stack, not yet finalized), that's a **back edge**, meaning a cycle exists.
4. Once all nodes are processed, popping the stack top-to-bottom gives a valid topological order — reversal is necessary because postorder finalizes a node's *dependents* before the node itself when traversing forward, so the raw postorder sequence is backward relative to the dependency direction.

Both run in **O(V+E)**: Kahn's does O(V) queue operations and O(E) total in-degree decrements across all nodes; DFS-based visits every node and edge exactly once.

---

## Template code (Python, Java, Go)

```python
# Python — Kahn's algorithm (BFS), returns [] if a cycle exists
from collections import deque

def topo_sort_kahn(n: int, edges: list[tuple[int, int]]) -> list[int]:
    graph = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:            # u must come before v
        graph[u].append(v)
        indeg[v] += 1

    queue = deque(i for i in range(n) if indeg[i] == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in graph[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    return order if len(order) == n else []   # shorter than n -> cycle

# DFS-based, three-color cycle detection + postorder reversal
def topo_sort_dfs(n: int, edges: list[tuple[int, int]]) -> list[int]:
    graph = [[] for _ in range(n)]
    for u, v in edges:
        graph[u].append(v)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * n
    order = []
    has_cycle = False

    def dfs(node: int):
        nonlocal has_cycle
        color[node] = GRAY
        for nxt in graph[node]:
            if color[nxt] == GRAY:
                has_cycle = True
                return
            if color[nxt] == WHITE:
                dfs(nxt)
        color[node] = BLACK
        order.append(node)

    for i in range(n):
        if color[i] == WHITE:
            dfs(i)
    return [] if has_cycle else order[::-1]
```

```java
// Java — Kahn's algorithm
public int[] topoSortKahn(int n, int[][] edges) {
    List<List<Integer>> graph = new ArrayList<>();
    for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
    int[] indeg = new int[n];
    for (int[] e : edges) {
        graph.get(e[0]).add(e[1]);
        indeg[e[1]]++;
    }

    Deque<Integer> queue = new ArrayDeque<>();
    for (int i = 0; i < n; i++) if (indeg[i] == 0) queue.add(i);

    int[] order = new int[n];
    int idx = 0;
    while (!queue.isEmpty()) {
        int node = queue.poll();
        order[idx++] = node;
        for (int nxt : graph.get(node)) {
            if (--indeg[nxt] == 0) queue.add(nxt);
        }
    }
    return idx == n ? order : new int[0];   // shorter than n -> cycle
}
```

```go
// Go — Kahn's algorithm
func topoSortKahn(n int, edges [][2]int) []int {
    graph := make([][]int, n)
    indeg := make([]int, n)
    for _, e := range edges {
        u, v := e[0], e[1]
        graph[u] = append(graph[u], v)
        indeg[v]++
    }

    queue := []int{}
    for i := 0; i < n; i++ {
        if indeg[i] == 0 {
            queue = append(queue, i)
        }
    }

    order := make([]int, 0, n)
    for len(queue) > 0 {
        node := queue[0]
        queue = queue[1:]
        order = append(order, node)
        for _, nxt := range graph[node] {
            indeg[nxt]--
            if indeg[nxt] == 0 {
                queue = append(queue, nxt)
            }
        }
    }

    if len(order) != n {
        return []int{} // cycle
    }
    return order
}
```

## Complexity, derived

Both algorithms touch every vertex exactly once and every edge exactly once: Kahn's decrements each edge's target in-degree once total across the whole run and enqueues/dequeues each vertex once, giving **O(V+E) time**; DFS-based visits each vertex once (color transitions WHITE→GRAY→BLACK, each vertex changes color a constant number of times) and each edge once during neighbor exploration, also **O(V+E)**. Space is **O(V+E)** for the adjacency list plus **O(V)** for the in-degree array / color array / queue or recursion stack. Cycle detection is free in both: Kahn's compares the final order length to `V` (O(1) check after the O(V+E) run); DFS-based checks for a GRAY-to-GRAY edge during the same traversal, adding no extra asymptotic cost.

---

## The 5 variants interviewers actually ask

1. **Course Schedule (LC 207) — does a valid order exist at all?** Pure cycle detection: run Kahn's or DFS-based topo sort, return whether all nodes were processed / no back-edge was found.
2. **Course Schedule II (LC 210) — return one valid order, or empty if impossible.** Direct application of either template; the interview usually wants Kahn's first (simpler to reason about) with DFS-based as the follow-up alternative.
3. **Alien Dictionary (LC 269, premium) — derive edge constraints from adjacent words in a sorted word list, then topo-sort the derived alphabet graph.** The hard part is edge derivation (compare consecutive word pairs, find the first differing character, add one edge `earlier -> later`) and correctly handling the invalid case where a shorter word appears *after* a longer word that shares its full prefix (impossible in a truly sorted order — that's itself a cycle-equivalent contradiction to detect).
4. **Minimum Height Trees (LC 310) — find all roots that minimize the tree's height.** Not dependency ordering, but the same in-degree-peeling mechanic applied to an undirected tree: repeatedly strip current leaves (degree-1 nodes) layer by layer; the last one or two nodes remaining are the centroid(s) that minimize height.
5. **Parallel Courses (LC 1136) — minimum number of "semesters" (rounds) to complete all courses given prerequisites, where any number of courses with satisfied prerequisites can be taken simultaneously.** Level-order (layered) Kahn's algorithm: process an entire in-degree-zero frontier as one round instead of one node at a time; the number of rounds until the queue empties is the answer, and an incomplete traversal again signals a cycle.

---

## Common bugs

- **Forgetting the cycle check.** Returning whatever partial order Kahn's algorithm produced without verifying its length equals `V` silently returns an incomplete, invalid order when a cycle exists instead of correctly reporting "impossible."
- **Direction confusion in edge construction.** Building the graph backward (`v -> u` instead of `u -> v` for "u must come before v") produces a valid-looking but completely reversed order; always fix a concrete convention ("edge points from prerequisite to dependent") and verify it against one example before coding.
- **DFS-based cycle detection using only a visited/unvisited boolean instead of three states.** A plain visited-set can't distinguish "currently on the recursion stack" (a real back-edge, cycle) from "already fully processed in an earlier, unrelated branch" (a forward/cross edge, not a cycle) — this is the single most common DFS-topo-sort bug and silently either misses real cycles or falsely reports cycles that aren't there.
- **Off-by-one in in-degree bookkeeping** when edges are given as pairs in an ambiguous order (some LeetCode prompts give `[a, b]` meaning "b is a prerequisite of a," which is the opposite of the intuitive reading) — always re-derive the direction from the problem's stated semantics rather than assuming.
- **Assuming topological order is unique.** Multiple valid orders usually exist when the DAG isn't a total order; if a problem says "return any valid order," don't over-engineer to match a specific expected output.
- **Recursion depth blowup in DFS-based sort on deep/skewed graphs** (a long dependency chain) — for very large inputs this can hit language recursion limits (Python's default ~1000) where Kahn's iterative BFS approach doesn't have that risk at all.

---

## Interview questions

### Q1 — Course Schedule (LC 207): given prerequisite pairs, can all courses be finished?
**Testing:** the base cycle-detection framing.
**Answer:** Model as a directed graph (prerequisite → dependent), run Kahn's algorithm; if the processed-node count equals the total number of courses, yes — otherwise a cycle blocks some subset.
**Follow-up trap:** *"What if there are courses not mentioned in any prerequisite pair?"* — they start with in-degree 0 and are trivially included in any valid order; make sure the in-degree array covers all `n` courses, not just ones that appear in the edge list.

### Q2 — Course Schedule II (LC 210): return one valid completion order, or an empty list if impossible.
**Testing:** producing the order itself, not just a yes/no.
**Answer:** Same Kahn's algorithm, but record the pop order into a result list; return it if its length equals `n`, else return empty.
**Follow-up trap:** *"Give me a topological order using DFS instead."* — three-color DFS, push each node onto a stack on postorder completion, detect a GRAY-revisit as a cycle, reverse the stack at the end for the final order.

### Q3 — Why does DFS-based topological sort need to reverse the postorder, not just return it directly?
**Testing:** understanding *why* the algorithm works, not just memorizing "reverse it."
**Answer:** Postorder finalizes a node only after everything reachable from it is finalized, so a node's dependents get pushed onto the stack before the node itself; reversing puts prerequisites first, matching the required "before" ordering.
**Follow-up trap:** *"Give a concrete 3-node example where forgetting to reverse produces a visibly wrong order."* — for edges `1->2, 2->3` (1 before 2 before 3), DFS from 1 finalizes 3 first, then 2, then 1, giving postorder `[3,2,1]` — exactly backward; reversing gives the correct `[1,2,3]`.

### Q4 — Alien Dictionary (LC 269): given words sorted according to an unknown alien alphabet's order, reconstruct a valid ordering of the alphabet.
**Testing:** whether you can derive graph edges from indirect evidence before applying the standard algorithm.
**Answer:** Compare each pair of adjacent words, find the first differing character, and add a directed edge from the earlier alphabet's character to the later one; then run topological sort over the resulting character graph.
**Follow-up trap:** *"What if word[i] is a longer string that has word[i+1] as its full prefix?"* — that's invalid input (e.g., "abc" before "ab" can't happen in any valid sort order), and must be detected explicitly as a special case — it does not produce a graph cycle on its own, so cycle detection alone won't catch it.

### Q5 — Minimum Height Trees (LC 310): find all nodes that, if chosen as root, minimize the tree's height.
**Testing:** recognizing a peeling-mechanic problem that isn't literally about dependencies.
**Answer:** Repeatedly strip all current leaves (degree-1 nodes) layer by layer, the same in-degree-zero-peeling idea as Kahn's algorithm; the node(s) remaining when 1 or 2 nodes are left are the answer, since a tree has at most 2 centroids.
**Follow-up trap:** *"Why can there be at most 2 such roots?"* — because a tree's diameter path has a unique middle point (1 node) or middle edge (2 nodes), and the centroid(s) minimizing eccentricity always sit at that midpoint.

### Q6 — Parallel Courses (LC 1136): minimum number of semesters needed if any number of courses can be taken per semester as long as prerequisites are satisfied.
**Testing:** level-order (layered) topological sort, not just node-by-node ordering.
**Answer:** Kahn's algorithm processed by whole frontiers: each BFS "layer" (all currently in-degree-zero nodes) is one semester; count layers until the queue empties; if not all courses were processed, return -1 for an impossible cycle.
**Follow-up trap:** *"How is this different from plain Course Schedule II?"* — Course Schedule II wants any single valid sequential order; this wants the *minimum number of rounds* assuming maximal parallelism, which requires tracking layer boundaries rather than a flat list.

### Q7 — Sequence Reconstruction: given a list of sequences, determine if they uniquely determine one specific topological order (not just any valid one).
**Testing:** the uniqueness condition on top of basic ordering.
**Answer:** Build the graph from all pairwise adjacency constraints implied by the sequences; the order is unique if and only if, at every step of Kahn's algorithm, the in-degree-zero queue contains exactly one node (never more than one candidate to pick from).
**Follow-up trap:** *"What does it mean if the queue ever has 2+ eligible nodes at once?"* — it means the given constraints don't fully determine a single order (multiple valid topological orders exist), so the answer is "not uniquely reconstructible," independent of whether a valid order exists at all.

### Q8 — Find Eventual Safe States (LC 802): find nodes from which every possible path eventually leads to a terminal node (no path gets stuck in a cycle).
**Testing:** applying topological/cycle-detection logic to nodes rather than to "can we finish everything."
**Answer:** Reverse the graph and run Kahn's-style peeling from terminal (out-degree-0-in-original, i.e., in-degree-0-in-reversed) nodes inward; alternatively, three-color DFS from each node and mark it "safe" only if none of its paths hit a GRAY (in-progress) node.
**Follow-up trap:** *"Why does reversing the graph make this a standard topological-sort-shaped problem?"* — "eventually safe" is exactly "not part of, and doesn't lead into, any cycle," which reversed becomes "reachable via peeling from the sinks inward," turning it into the same in-degree-zero-frontier mechanic as Kahn's algorithm.

### Q9 — What happens if the input graph is guaranteed to be a DAG (no possibility of a cycle) — does anything simplify?
**Testing:** whether you over-engineer defensive cycle checks when the problem guarantees they're unnecessary.
**Answer:** You can skip the final length-check / GRAY-revisit check for correctness purposes, but it's usually still worth keeping as a cheap assertion in production code, since "guaranteed" inputs are exactly the ones that eventually violate the guarantee in a live system.
**Follow-up trap:** *"Would you actually remove the check in a real dependency-resolution service?"* — no; production build/package systems keep the cycle check permanently because upstream guarantees erode over time (a new dependency introduces an accidental cycle) and a silent wrong-order result is far more expensive to debug than a fast, explicit cycle error.

### Q10 — Multiple valid topological orders exist for a DAG. How would you return the lexicographically smallest one?
**Testing:** adapting the standard algorithm with a small but real modification.
**Answer:** Replace Kahn's plain queue with a min-heap keyed on node value; at each step, always pop the smallest available in-degree-zero node. This still runs in O(V log V + E) instead of O(V+E) due to the heap operations.
**Follow-up trap:** *"Why can't you just topo-sort normally and then sort the result?"* — sorting the final order afterward doesn't respect the dependency constraints; only greedily picking the smallest *eligible* node at each step, among currently-unblocked candidates, guarantees both validity and lexicographic minimality simultaneously.

### Q11 — How would you detect a cycle in a graph with millions of nodes without blowing the recursion stack?
**Testing:** production-scale awareness of implementation choice, not just correctness.
**Answer:** Use Kahn's algorithm (iterative, BFS-based, no recursion) instead of DFS-based topological sort, since DFS-based cycle detection needs recursion depth proportional to the longest dependency chain, which can exceed language stack limits on deep or adversarially-skewed graphs.
**Follow-up trap:** *"Can DFS-based detection be made iterative to avoid this?"* — yes, with an explicit stack data structure simulating the recursion and tracking each frame's iteration state manually; it's strictly more bookkeeping than Kahn's for no correctness benefit, so Kahn's is the practical default at scale.

---

## Red flags that fail you

- Returning a partial Kahn's-algorithm order without checking it covers all nodes, silently ignoring a cycle.
- Using a single visited/unvisited boolean for DFS-based cycle detection instead of three states (unvisited/in-progress/visited).
- Not knowing why the DFS postorder needs to be reversed to become a valid topological order.
- Treating "topological order" as unique when the interviewer asked for "any valid order."
- Missing that Alien Dictionary's edges must be derived from word comparisons before any topo-sort logic applies.
- Recommending recursive DFS-based cycle detection for a graph with potentially millions of nodes without flagging the stack-depth risk.

---

## Cheat card

```
DEFINITION     linear order of DAG nodes s.t. every edge u->v has u before v
EXISTS IFF     no cycle (DAG only)
KAHN'S (BFS)   in-degree=0 queue -> pop, append, decrement neighbors' in-degree, enqueue new zeros
KAHN CYCLE     result length < V  =>  cycle among unprocessed nodes
DFS-BASED      3-color (white/gray/black); postorder push on finish; GRAY-revisit = cycle (back edge)
DFS ORDER      reverse the postorder stack to get valid topological order
COMPLEXITY     O(V+E) time, O(V+E) space, both algorithms
COURSE SCHED   LC207 exists?, LC210 return order — direct Kahn's/DFS application
ALIEN DICT     derive edges from adjacent word comparisons FIRST, then topo-sort (LC 269)
MIN HEIGHT TREE  peel leaves layer by layer; last 1-2 nodes = centroid(s)                (LC 310)
PARALLEL COURSES  Kahn's by FULL FRONTIER (layer) = one "round"; #layers = answer       (LC 1136)
LEX SMALLEST   swap queue for a min-heap; O((V+E) log V)
PICK WHEN      "must happen before" / prerequisite / build-order framing; DAG only
```

## Sources

- [Course Schedule — LeetCode](https://leetcode.com/problems/course-schedule/) — accessed 2026-07-26
- [Course Schedule II — LeetCode](https://leetcode.com/problems/course-schedule-ii/) — accessed 2026-07-26
- [Alien Dictionary — LeetCode](https://leetcode.com/problems/alien-dictionary/) — accessed 2026-07-26
- [Minimum Height Trees — LeetCode](https://leetcode.com/problems/minimum-height-trees/) — accessed 2026-07-26
- [Parallel Courses — LeetCode](https://leetcode.com/problems/parallel-courses/) — accessed 2026-07-26
- [Find Eventual Safe States — LeetCode](https://leetcode.com/problems/find-eventual-safe-states/) — accessed 2026-07-26
- [Topological sorting — Wikipedia](https://en.wikipedia.org/wiki/Topological_sorting) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
