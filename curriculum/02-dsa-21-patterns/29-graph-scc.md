# Strong Connectivity: Tarjan, Kosaraju, Bridges, Articulation Points, 2-SAT

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** T02-graph-core, T02-p17-topological-sort
> **Module id:** `T02-graph-scc` · **Tags:** graphs, connectivity, advanced
> **Lab:** `labs/py/29-graph-scc/`

## The 30-second version

Four related structural-graph problems all come from asking "what happens if I remove this node or edge, or what groups of nodes can all reach each other." A strongly connected component (SCC) is a maximal set of vertices in a *directed* graph where every vertex can reach every other vertex in the set — Tarjan's algorithm finds all SCCs in a single DFS pass using a low-link value and a stack, O(V+E); Kosaraju's algorithm finds them with two DFS passes (one on the graph, one on its transpose), also O(V+E) but conceptually simpler to explain even though it touches the graph twice. A bridge is an *undirected* edge whose removal increases the number of connected components (a single point of failure in network terms); an articulation point (cut vertex) is a *vertex* whose removal does the same. Both are found with a single DFS using discovery time and low-link values — genuinely the same low-link machinery Tarjan's SCC algorithm uses, applied to a different question (reachability back to an ancestor via a non-tree edge, rather than reachability that stays within a candidate SCC). 2-SAT (2-satisfiability) is a boolean satisfiability problem restricted to clauses with exactly two literals each, solved by building an implication graph (each clause `(a OR b)` becomes two directed edges `NOT a -> b` and `NOT b -> a`) and checking that no variable and its negation land in the same SCC — a direct, elegant application of SCC decomposition to a problem that looks like pure logic but is actually a graph-connectivity question in disguise.

## Why this gets asked

This module tests whether you can extend the DFS discovery-time/low-link machinery beyond the basic traversal you'd use for connected components — it's the clearest signal of whether a candidate actually understands DFS's structural theory (the parenthesis theorem, back edges, the meaning of low-link) versus having memorized "DFS visits nodes." The production motivation is concrete: circuit/dependency analysis (finding groups of mutually-dependent modules that must be compiled or deployed together, which is exactly SCC decomposition on a module-dependency graph), network reliability analysis (bridges and articulation points are literally the single points of failure in a physical or logical network topology — the exact question an SRE asks when designing for redundancy), and constraint satisfaction in scheduling/configuration systems (2-SAT shows up disguised as "assign one of two options to each of N items subject to pairwise constraints," a real shape in feature-flag conflict resolution and resource allocation with binary choices). Interviewers who've debugged a real production outage caused by a single non-redundant link (a bridge) or a single non-redundant node (an articulation point) ask this precisely because "just add more graph theory" turned out to be the exact analysis their infrastructure needed and nobody on the team knew how to run it.

---

## Lineage: past → present → future

**What came before.** Before Tarjan's 1972 paper ("Depth-First Search and Linear Graph Algorithms") formalized the discovery-time/low-link technique, connectivity analysis on directed graphs required either repeated reachability checks between every pair of vertices (O(V^2) or worse, checking "can u reach v AND can v reach u" for every pair) or ad hoc problem-specific methods — there was no general linear-time technique for decomposing a directed graph into its maximal mutually-reachable groups. Kosaraju's algorithm (attributed to S. Rao Kosaraju, circulated around 1978 though not formally published by him at the time; also independently discovered by Sharir in 1981) offered a conceptually simpler two-pass alternative once the transpose-graph trick was recognized, trading a second full graph traversal for easier-to-explain correctness (SCCs of a graph and its transpose are identical, and processing vertices in decreasing finish-time order from the first pass guarantees the second pass's DFS trees are exactly the SCCs). Boolean 2-SAT's polynomial-time solvability (as opposed to general k-SAT for k>=3, which is NP-complete) was established by Aspvall, Plass, and Tarjan in 1979, specifically by reducing it to exactly this SCC machinery — a striking early example of a "hard-looking" logic problem turning out to be a graph-connectivity problem in disguise.

**Where it stands now.** Tarjan's single-pass algorithm is the standard production and competitive-programming choice (one DFS instead of two, and it naturally produces SCCs in reverse topological order as a side effect, useful for condensation-graph construction); Kosaraju's remains the standard *teaching* algorithm because its correctness argument (SCC(G) = SCC(G^T), and finish-time ordering) is more directly provable without needing to reason carefully about the low-link invariant during a single pass. Bridges and articulation points via low-link DFS are settled, textbook material with no live methodological disagreement; the main practical subtlety that still trips up implementations is handling the DFS root vertex's articulation-point condition correctly (the root is an articulation point specifically if it has more than one DFS-tree child, a special case distinct from every other vertex's condition). 2-SAT's SCC-based solution is the standard approach; the live boundary that matters in practice is that this technique is specific to *2*-SAT — general k-SAT for k>=3 has no known polynomial algorithm (it's the canonical NP-complete problem), so recognizing exactly when a constraint problem is expressible with only two-literal clauses is the actual skill, not just knowing the SCC recipe once that's established.

**Where it's heading.** No new foundational algorithm is expected in this closed area of DFS-based structural graph theory. The applied direction is incremental/dynamic maintenance of these structures — maintaining SCC membership, bridges, or articulation points as edges are added or removed in real time (relevant to network topology monitoring and build-system dependency graphs that change as code changes), which is algorithmically harder than the static one-shot versions covered here and remains an active research area for fully dynamic graph algorithms, worth naming as a staff-level extension rather than something with a single settled textbook answer.

---

## Mental model

Low-link value is "the earliest (lowest discovery-time) vertex I can reach by using at most one non-tree edge from anywhere in my DFS subtree" — it's the mechanism that answers "can I get back to an ancestor without just retracing my own tree path."

```
DFS discovery order:  A(disc=0) -> B(disc=1) -> C(disc=2)
                                          \_______back edge to A_______/

low[C] = min(disc[C], disc[A]) = 0   (C can reach A directly, a back edge)
low[B] = min(disc[B], low[C])  = 0   (B inherits C's ability to reach A)
low[A] = min(disc[A], low[B])  = 0

If low[B] < disc[A]: B's subtree can escape past A -> A is NOT a bridge/
cut point on the A-B edge/vertex boundary.
If low[child] >= disc[current]: the child's subtree CANNOT escape without
going through 'current' -> current is an articulation point (or the A-B
edge is a bridge, depending on which exact condition is checked).
```

For SCCs specifically, Tarjan's algorithm keeps a stack of "vertices currently being considered for the SCC in progress," and a vertex is the *root* of a complete SCC exactly when `low[v] == disc[v]` — meaning nothing in its subtree can reach further back than `v` itself, so `v` and everything above it on the stack (down to `v`) form one finished, maximal SCC.

```
2-SAT implication graph for clause (a OR b):
NOT a --> b       (if a is false, b must be true to satisfy the clause)
NOT b --> a       (if b is false, a must be true)

If x and NOT x end up in the same SCC, both "x implies NOT x" and
"NOT x implies x" hold simultaneously -- a direct logical contradiction,
so the formula is unsatisfiable.
```

---

## Recognition heuristics

- **"Group vertices such that every vertex in a group can reach every other vertex in that group, directed graph"** — SCC decomposition, Tarjan's or Kosaraju's.
- **"Find single points of failure in a network"**, **"critical connections whose removal disconnects part of the network"** (Critical Connections in a Network, LC 1192) — bridges.
- **"Find nodes whose removal disconnects the graph"**, **"critical servers/routers"** — articulation points.
- **"Condense a directed graph into a DAG of its strongly connected components"** — SCC decomposition followed by building a condensation graph (each SCC collapses to a single node; edges between different SCCs are preserved) — a common two-step combination in staff-level problems (compute SCCs, then run topological sort or shortest path on the condensation).
- **"Each item must be assigned exactly one of two states, subject to pairwise implication/exclusion constraints"** — 2-SAT, build the implication graph, check `x` and `NOT x` never share an SCC.
- **"Is there a way to satisfy all these either-or constraints"** where each constraint involves exactly two boolean variables — the direct tell for 2-SAT versus general SAT (which would involve three or more variables per clause and is NP-complete, not solvable by this technique).
- **A qualifier like "in one DFS pass" attached to an SCC problem** — a hint that Tarjan's (single-pass) rather than Kosaraju's (two-pass) is expected, though both are O(V+E) and either is usually acceptable unless explicitly constrained.

---

## How it actually works — low-link value derivation, and the root-articulation-point special case

The **low-link value** `low[u]` is defined as the minimum of: `disc[u]` itself, `low[v]` for every DFS-tree child `v` of `u`, and `disc[w]` for every back edge `(u, w)` to an ancestor `w`. This single recursive definition is the mechanism behind all three structural checks:

**Bridge condition:** edge `(u, v)` where `v` is a DFS-tree child of `u` is a bridge if and only if `low[v] > disc[u]` — strictly greater, meaning `v`'s entire subtree has no way back to `u` or any ancestor of `u` except through this specific edge; removing it genuinely disconnects `v`'s subtree from the rest of the graph.

**Articulation point condition (non-root case):** vertex `u` (not the DFS root) is an articulation point if it has some DFS-tree child `v` with `low[v] >= disc[u]` — note the non-strict `>=` here, unlike the bridge condition's strict `>`, because even if `v`'s subtree can reach back to exactly `u` itself (but no further ancestor), removing `u` still disconnects that subtree from the rest of the graph above `u`.

**Articulation point condition (root case, the special exception):** the DFS root is an articulation point if and only if it has **more than one DFS-tree child** — because with only one child, the root has nothing else to disconnect (there's no "rest of the graph above it" for a root), but with two or more children, removing the root severs the only connection between those separate subtrees, which otherwise have no other path between them (if they did, DFS would have already discovered one from the other via a back/cross edge, making them part of the same single subtree instead of two separate root-children).

**Tarjan's SCC root condition:** a vertex `v` is the root of a completed SCC exactly when `low[v] == disc[v]` — meaning no vertex in `v`'s subtree (including itself) can reach any ancestor earlier than `v`, so the set of vertices from `v` up to the top of the stack (all pushed during this subtree's exploration and not yet popped into an earlier-finished SCC) forms one complete, maximal strongly connected component; popping them off the stack down to and including `v` finalizes that SCC.

---

## Template code (Python, Java, Go)

```python
import sys
sys.setrecursionlimit(20000)

# Tarjan's SCC — single DFS pass, low-link + stack
def tarjan_scc(n: int, adj: list[list[int]]) -> list[list[int]]:
    disc = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    stack = []
    timer = [0]
    sccs = []

    def dfs(u):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        stack.append(u)
        on_stack[u] = True
        for v in adj[u]:
            if disc[v] == -1:
                dfs(v)
                low[u] = min(low[u], low[v])
            elif on_stack[v]:
                low[u] = min(low[u], disc[v])
        if low[u] == disc[u]:
            component = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                component.append(w)
                if w == u:
                    break
            sccs.append(component)

    for i in range(n):
        if disc[i] == -1:
            dfs(i)
    return sccs

# Bridges and articulation points — single DFS, low-link
def bridges_and_articulation_points(n: int, adj: list[list[int]]):
    disc = [-1] * n
    low = [0] * n
    timer = [0]
    bridges = []
    articulation = [False] * n

    def dfs(u, parent):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        children = 0
        for v in adj[u]:
            if v == parent:
                continue
            if disc[v] == -1:
                children += 1
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.append((u, v))
                if parent != -1 and low[v] >= disc[u]:
                    articulation[u] = True
            else:
                low[u] = min(low[u], disc[v])
        if parent == -1 and children > 1:  # root special case
            articulation[u] = True

    for i in range(n):
        if disc[i] == -1:
            dfs(i, -1)
    return bridges, [i for i, is_ap in enumerate(articulation) if is_ap]

# 2-SAT via SCC — variables 0..n-1, literal x -> 2x, NOT x -> 2x+1
def solve_2sat(n: int, clauses: list[tuple[int, bool, int, bool]]):
    # clause: (var_a, is_a_positive, var_b, is_b_positive) meaning (a OR b)
    def node(var, positive):
        return 2 * var + (0 if positive else 1)
    def neg(lit):
        return lit ^ 1

    adj = [[] for _ in range(2 * n)]
    for a, pa, b, pb in clauses:
        la, lb = node(a, pa), node(b, pb)
        adj[neg(la)].append(lb)  # NOT a -> b
        adj[neg(lb)].append(la)  # NOT b -> a

    sccs = tarjan_scc(2 * n, adj)
    comp_id = [0] * (2 * n)
    for idx, comp in enumerate(sccs):
        for v in comp:
            comp_id[v] = idx
    # Tarjan produces SCCs in reverse topological order; comp with lower idx
    # is later in topological order, so we use idx directly for comparison

    assignment = [None] * n
    for var in range(n):
        pos, negv = node(var, True), node(var, False)
        if comp_id[pos] == comp_id[negv]:
            return None  # unsatisfiable
        # earlier SCC index (found first by Tarjan) = later in topological order
        assignment[var] = comp_id[pos] > comp_id[negv]
    return assignment
```

```java
import java.util.*;

public class Connectivity {
    static int[] disc, low;
    static boolean[] onStack;
    static Deque<Integer> stack = new ArrayDeque<>();
    static int timer = 0;
    static List<List<Integer>> sccs = new ArrayList<>();

    static void tarjanDFS(int u, List<List<Integer>> adj) {
        disc[u] = low[u] = timer++;
        stack.push(u);
        onStack[u] = true;
        for (int v : adj.get(u)) {
            if (disc[v] == -1) {
                tarjanDFS(v, adj);
                low[u] = Math.min(low[u], low[v]);
            } else if (onStack[v]) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
        if (low[u] == disc[u]) {
            List<Integer> component = new ArrayList<>();
            int w;
            do {
                w = stack.pop();
                onStack[w] = false;
                component.add(w);
            } while (w != u);
            sccs.add(component);
        }
    }

    static List<List<Integer>> tarjanSCC(int n, List<List<Integer>> adj) {
        disc = new int[n]; low = new int[n]; onStack = new boolean[n];
        Arrays.fill(disc, -1);
        sccs.clear();
        for (int i = 0; i < n; i++) {
            if (disc[i] == -1) tarjanDFS(i, adj);
        }
        return sccs;
    }

    // Bridges and articulation points
    static int[] bDisc, bLow;
    static boolean[] articulation;
    static int bTimer = 0;
    static List<int[]> bridges = new ArrayList<>();

    static void bridgeDFS(int u, int parent, List<List<Integer>> adj) {
        bDisc[u] = bLow[u] = bTimer++;
        int children = 0;
        for (int v : adj.get(u)) {
            if (v == parent) continue;
            if (bDisc[v] == -1) {
                children++;
                bridgeDFS(v, u, adj);
                bLow[u] = Math.min(bLow[u], bLow[v]);
                if (bLow[v] > bDisc[u]) bridges.add(new int[]{u, v});
                if (parent != -1 && bLow[v] >= bDisc[u]) articulation[u] = true;
            } else {
                bLow[u] = Math.min(bLow[u], bDisc[v]);
            }
        }
        if (parent == -1 && children > 1) articulation[u] = true;
    }

    static void bridgesAndArticulationPoints(int n, List<List<Integer>> adj) {
        bDisc = new int[n]; bLow = new int[n]; articulation = new boolean[n];
        Arrays.fill(bDisc, -1);
        for (int i = 0; i < n; i++) {
            if (bDisc[i] == -1) bridgeDFS(i, -1, adj);
        }
    }
}
```

```go
package main

// Tarjan's SCC
type TarjanState struct {
    disc, low  []int
    onStack    []bool
    stack      []int
    timer      int
    sccs       [][]int
    adj        [][]int
}

func (s *TarjanState) dfs(u int) {
    s.disc[u] = s.timer
    s.low[u] = s.timer
    s.timer++
    s.stack = append(s.stack, u)
    s.onStack[u] = true
    for _, v := range s.adj[u] {
        if s.disc[v] == -1 {
            s.dfs(v)
            if s.low[v] < s.low[u] {
                s.low[u] = s.low[v]
            }
        } else if s.onStack[v] {
            if s.disc[v] < s.low[u] {
                s.low[u] = s.disc[v]
            }
        }
    }
    if s.low[u] == s.disc[u] {
        var component []int
        for {
            w := s.stack[len(s.stack)-1]
            s.stack = s.stack[:len(s.stack)-1]
            s.onStack[w] = false
            component = append(component, w)
            if w == u {
                break
            }
        }
        s.sccs = append(s.sccs, component)
    }
}

func tarjanSCC(n int, adj [][]int) [][]int {
    s := &TarjanState{
        disc: make([]int, n), low: make([]int, n),
        onStack: make([]bool, n), adj: adj,
    }
    for i := range s.disc {
        s.disc[i] = -1
    }
    for i := 0; i < n; i++ {
        if s.disc[i] == -1 {
            s.dfs(i)
        }
    }
    return s.sccs
}

// Bridges and articulation points
type BridgeState struct {
    disc, low     []int
    timer         int
    bridges       [][2]int
    articulation  []bool
    adj           [][]int
}

func (s *BridgeState) dfs(u, parent int) {
    s.disc[u] = s.timer
    s.low[u] = s.timer
    s.timer++
    children := 0
    for _, v := range s.adj[u] {
        if v == parent {
            continue
        }
        if s.disc[v] == -1 {
            children++
            s.dfs(v, u)
            if s.low[v] < s.low[u] {
                s.low[u] = s.low[v]
            }
            if s.low[v] > s.disc[u] {
                s.bridges = append(s.bridges, [2]int{u, v})
            }
            if parent != -1 && s.low[v] >= s.disc[u] {
                s.articulation[u] = true
            }
        } else {
            if s.disc[v] < s.low[u] {
                s.low[u] = s.disc[v]
            }
        }
    }
    if parent == -1 && children > 1 {
        s.articulation[u] = true
    }
}

func bridgesAndArticulationPoints(n int, adj [][]int) ([][2]int, []bool) {
    s := &BridgeState{
        disc: make([]int, n), low: make([]int, n),
        articulation: make([]bool, n), adj: adj,
    }
    for i := range s.disc {
        s.disc[i] = -1
    }
    for i := 0; i < n; i++ {
        if s.disc[i] == -1 {
            s.dfs(i, -1)
        }
    }
    return s.bridges, s.articulation
}
```

## Complexity — derived, not asserted

**Tarjan's SCC:** a single DFS, `O(V+E)` — each vertex is discovered once and each edge examined once; the stack push/pop operations are each amortized O(1) per vertex since every vertex is pushed exactly once and popped exactly once across the whole algorithm.

**Kosaraju's SCC:** two full DFS passes plus building the transpose graph, still `O(V+E)` overall (each pass is linear, and building the transpose is `O(V+E)`), just with a larger constant factor than Tarjan's single pass.

**Bridges and articulation points:** a single DFS with O(1) extra work per edge (a low-link comparison), `O(V+E)`.

**2-SAT:** building the implication graph is `O(clauses)` (each clause contributes exactly 2 directed edges), and solving via SCC decomposition is `O(V+E)` where `V = 2 * num_variables` and `E = 2 * num_clauses` — so overall `O(variables + clauses)`, linear in the input size, which is the specific reason 2-SAT is tractable while general 3-SAT (no such reduction to a linear-time-solvable structure exists) is NP-complete.

---

## The 5 variants interviewers actually ask

1. **Critical Connections in a Network (LC 1192).** Direct bridge-finding — the answer set is exactly the bridges found by the low-link DFS.
2. **Strongly Connected Components, condensed into a DAG, then answer a reachability or shortest-path query on the condensation.** SCC decomposition followed by building the condensation graph (collapse each SCC to one node, keep inter-SCC edges), then running standard DAG algorithms (topological sort, DAG shortest path) on the much smaller condensed structure — a common two-stage staff-level combination.
3. **Number of servers whose failure would partition the network / find all critical (single-point-of-failure) routers.** Direct articulation-point finding, including correctly handling the root special case (more than one DFS-tree child).
4. **Boolean constraint satisfaction with binary either-or choices per item and pairwise implications** (e.g., "if feature A is enabled, feature B must be disabled," phrased as a real configuration/scheduling constraint rather than explicit boolean notation). 2-SAT via implication graph and SCC — the tell is recognizing a real-world constraint problem reduces to two-literal clauses.
5. **Account Merging / building equivalence classes from pairwise "same as" relationships** (LC 721-style). Usually solvable more simply with Union-Find rather than full SCC machinery, but worth distinguishing explicitly: this is an *undirected* equivalence-class problem (symmetric "same as" relation), not a directed strongly-connected-components problem — using Tarjan's or Kosaraju's here is over-engineering; recognizing when Union-Find suffices instead of reaching for SCC out of pattern-matching is itself the tested judgment.

---

## Common bugs and how this gets written wrong under pressure

- **Forgetting the DFS root's special articulation-point condition.** Using the same `low[v] >= disc[u]` check for the root as for every other vertex incorrectly marks the root as an articulation point even when it has only one child (where removing it can't actually disconnect anything, since there's nothing else attached above it) — the root-specific "more than one child" check is a distinct, separate condition that's easy to omit under pressure.
- **Using `>=` for the bridge condition instead of the strict `>` it requires.** Bridges require `low[v] > disc[u]` (strict); using `>=` incorrectly flags edges as bridges when the child's subtree can actually reach back to exactly `u` (which means removing the edge doesn't disconnect anything, since the subtree remains connected to `u` via a different path) — this is the inverse of the articulation-point condition's non-strict `>=`, and swapping the two conditions between bridge-finding and articulation-point-finding is a very common under-pressure mixup.
- **Not excluding the parent edge when checking for back edges in the low-link update**, in an undirected graph — without this exclusion, every tree edge looks like it has a back edge to its immediate parent (since undirected edges are stored both ways), corrupting every low-link value and producing wildly wrong bridge/articulation-point results. Note this is conceptually the same parent-exclusion bug as in basic undirected cycle detection, resurfacing here in a more consequential way since it corrupts the whole low-link computation, not just a single yes/no answer.
- **Confusing Tarjan's stack-based "on_stack" check with a plain "visited" check.** A vertex can be `disc[v] != -1` (visited) but no longer `on_stack` (already popped into a previously-finished SCC) — treating it as still part of the current SCC-in-progress if you only check "visited" instead of "on_stack" incorrectly merges separate SCCs together.
- **In 2-SAT, forgetting to add both implication edges per clause.** Clause `(a OR b)` requires *both* `NOT a -> b` and `NOT b -> a`; adding only one direction produces an implication graph that doesn't actually enforce the OR constraint bidirectionally, silently accepting assignments that violate the original clause.
- **In 2-SAT, getting the variable-assignment rule backward.** After computing SCCs, the correct rule is: a variable is assigned `true` if its "positive" literal's SCC comes *later* in topological order than its "negative" literal's SCC (equivalently, using Tarjan's convention where earlier-found SCCs are later in topological order, the positive literal's component index must be *greater than* the negative literal's) — flipping this comparison produces an assignment that's the exact opposite of a valid satisfying assignment, and it won't necessarily crash, since a flipped-but-internally-consistent assignment can still look plausible without being checked against the original clauses.

---

## Interview questions

### Q1 — Find all bridges in an undirected network (Critical Connections in a Network, LC 1192).
**Testing:** the exact low-link bridge condition, including the parent-exclusion detail.
**Answer:** Single DFS tracking discovery time and low-link value; edge `(u,v)` (tree edge, `v` a child of `u`) is a bridge iff `low[v] > disc[u]`, excluding the parent when checking for back edges.
**Follow-up trap:** *"Why strict `>` and not `>=`?"* — `low[v] == disc[u]` means `v`'s subtree can reach back to exactly `u` (not further), so `u` and `v` remain connected via some other path even without this specific edge — it's not a bridge; only when `v`'s subtree has *no* way back to `u` or beyond (`low[v] > disc[u]`) does removing the edge actually disconnect it.

### Q2 — Find all articulation points in the same kind of network.
**Testing:** the non-root condition plus the critical root special case.
**Answer:** Non-root vertex `u` is an articulation point if some child `v` has `low[v] >= disc[u]`. The DFS root is a special case: it's an articulation point iff it has more than one DFS-tree child.
**Follow-up trap:** *"Why does the root need a different rule entirely?"* — the general condition relies on `u` having a parent/ancestor that a child's subtree might or might not be able to reach around; the root has no parent, so the condition degenerates to "does removing the root separate its children's subtrees from each other," which is exactly "does it have more than one child" since DFS would have merged them into one subtree if any alternate connection existed.

### Q3 — Find all strongly connected components of a directed graph.
**Testing:** correct implementation of Tarjan's or Kosaraju's, and understanding why they're both O(V+E) despite different structures.
**Answer:** Tarjan's: single DFS with low-link and an explicit stack, SCC root exactly when `low[v] == disc[v]`. Kosaraju's: DFS on the graph recording finish order, then DFS on the transpose graph processing vertices in decreasing finish-time order, each resulting tree is one SCC.
**Follow-up trap:** *"Why does processing vertices in decreasing finish-time order on the transpose graph correctly recover SCCs?"* — the vertex that finishes last in the first pass is guaranteed to be in a "source" SCC of the condensation DAG (an SCC with no incoming edges from other SCCs in that DAG); starting the transpose-graph DFS there confines that pass to exactly that one SCC, since transpose edges only lead further "downstream" in the original condensation order, never back out.

### Q4 — Given a directed graph, build the condensation graph (each SCC collapsed to one node) and check if it has a valid topological order allowing a specific reachability query.
**Testing:** combining SCC decomposition with downstream DAG algorithms, a common staff-level composition.
**Answer:** Compute SCCs (Tarjan's or Kosaraju's), map every vertex to its SCC id, then build edges between distinct SCC ids wherever an inter-SCC edge existed in the original graph (deduplicating parallel condensation edges); the condensation graph is guaranteed to be a DAG (a cycle between two different SCCs would mean they should have been merged into one SCC in the first place), so any DAG algorithm applies directly afterward.
**Follow-up trap:** *"Why is the condensation graph guaranteed to be acyclic?"* — if there were a cycle among distinct SCCs in the condensation, every vertex in every SCC on that cycle could reach every other vertex in every other SCC on that cycle (by chaining through the cycle), which would mean they were all mutually reachable and should have been one single SCC to begin with — a direct proof by contradiction against the maximality of SCC decomposition.

### Q5 — 2-SAT: given clauses each with exactly two literals, determine if the formula is satisfiable, and if so, find an assignment.
**Testing:** the implication-graph construction and the SCC-based satisfiability check.
**Answer:** For each clause `(a OR b)`, add edges `NOT a -> b` and `NOT b -> a`. Compute SCCs of the implication graph; the formula is unsatisfiable iff some variable and its negation are in the same SCC. Otherwise, assign each variable `true` if its positive literal's SCC is later in topological order than its negative literal's.
**Follow-up trap:** *"Why does 'same SCC as its negation' mean unsatisfiable?"* — being in the same SCC means `x` implies `NOT x` and `NOT x` implies `x` simultaneously (mutual reachability in the implication graph), which is a direct logical contradiction — no consistent truth value can satisfy both implications at once.

### Q6 — Why is 2-SAT polynomial-time solvable while 3-SAT is NP-complete?
**Testing:** understanding exactly what breaks about the reduction for three-or-more-literal clauses.
**Answer:** A two-literal clause `(a OR b)` translates cleanly into exactly two directed implications, giving a graph whose size is linear in the input; a three-literal clause `(a OR b OR c)` has no equivalent two-implication-edge representation (falsifying any two literals must force the third true, which isn't expressible as a single directed edge relationship the way a two-literal clause is), so the same linear-time SCC-based technique simply doesn't apply, and no other polynomial reduction is known — this is the actual boundary of tractability, not an arbitrary rule.
**Follow-up trap:** *"Could you reduce 3-SAT to 2-SAT somehow?"* — not in general without exponential blowup (this would imply P=NP, since 3-SAT is NP-complete and 2-SAT is in P); auxiliary-variable tricks can convert some restricted clause structures but not general 3-SAT into 2-SAT while staying polynomial.

### Q7 — Given a graph representing "same person" pairwise relations from different account records, merge accounts belonging to the same person (Account Merging, LC 721).
**Testing:** recognizing when SCC/Tarjan's machinery is overkill and Union-Find is the right, simpler tool.
**Answer:** Union-Find over accounts sharing any email, then group by root — an undirected equivalence-class problem, not a directed strongly-connected-components problem.
**Follow-up trap:** *"Why not use Tarjan's SCC algorithm here since it also finds 'groups of mutually related items'?"* — Tarjan's answers a fundamentally directed-reachability question; the "same person" relation here is symmetric/undirected by nature (if A and B share an email, the relationship holds both ways trivially, not as a directed implication), so Union-Find is both simpler and the conceptually correct match for the actual relation being modeled — reaching for SCC machinery here is a sign of pattern-matching without understanding what SCC actually measures.

### Q8 — Design a system that flags a service architecture's single points of failure (both critical links and critical nodes) from its dependency/connectivity graph.
**Testing:** combining bridge-finding and articulation-point-finding into a coherent system design, a common applied framing.
**Answer:** Model the network as an undirected graph (or reduce a directed dependency graph to its undirected connectivity skeleton if only physical reachability matters), run a single low-link DFS computing both bridges and articulation points simultaneously (the two conditions are checked from the same disc/low values in one pass), and report both as distinct categories of risk since a bridge and an articulation point represent different failure modes (a link failure vs. a node failure) that may need different mitigation (adding redundant links vs. adding redundant nodes).
**Follow-up trap:** *"Is every endpoint of a bridge automatically an articulation point?"* — not necessarily; a bridge's endpoint is an articulation point only if it has additional subtrees/neighbors that would also be disconnected — a bridge connecting two otherwise-isolated single vertices makes both endpoints articulation points trivially (each has "nothing else" to lose, but removing either still disconnects the other), while in a more complex graph a bridge endpoint might have other independent connections that keep it non-critical from the *vertex-removal* perspective even though the *specific edge* is still critical.

### Q9 — Staff-level: your build system needs to detect groups of mutually-dependent modules that must be compiled together (circular dependencies that aren't necessarily a hard error, just a scheduling constraint), then order the resulting groups for a build pipeline.
**Testing:** the two-stage SCC-then-condensation-then-topological-sort composition in a realistic systems framing.
**Answer:** Model modules and their dependency edges as a directed graph, compute SCCs (each SCC is a maximal group of modules that must be built as one unit since they mutually depend on each other), condense into a DAG, then topologically sort the condensation to get a valid build order for the groups.
**Follow-up trap:** *"What if a single module has a self-loop dependency (depends on itself, perhaps a build-tool artifact)?"* — a self-loop doesn't create a multi-vertex SCC by itself (a single vertex is trivially its own SCC regardless of self-loops) but does need to be filtered out or specially handled before running the actual build step for that module, since attempting to build a module strictly after itself is a separate, degenerate case that SCC decomposition alone doesn't resolve — worth flagging as an edge case the interviewer may be probing for.

### Q10 — Why does Tarjan's algorithm produce SCCs already in reverse topological order of the condensation graph, and why is that useful?
**Testing:** a subtle but genuinely useful structural fact many candidates don't know even after implementing Tarjan's correctly.
**Answer:** Because an SCC is finalized (popped off the stack) only after every vertex reachable from it (in later-processed subtrees) has already been finalized, the order SCCs are *completed* in is naturally a reverse topological order of the condensation DAG — no separate topological sort pass is needed if you already need the condensation in build/dependency order, you can just reverse the list of completed SCCs.
**Follow-up trap:** *"Does Kosaraju's algorithm have the same property?"* — yes, in fact Kosaraju's construction actively depends on a very similar finish-time-order fact from its first DFS pass to make the second pass correct at all, so both algorithms are intimately connected to topological-order reasoning, not just coincidentally similar in output.

---

## Red flags that fail you

- Applying the same articulation-point condition to the DFS root as to every other vertex, missing the "more than one child" special case.
- Swapping the strict `>` (bridge) and non-strict `>=` (articulation point) conditions.
- Forgetting to exclude the parent edge when updating low-link values in an undirected graph, corrupting every result.
- Confusing "visited" with "on stack" in Tarjan's algorithm, merging separate SCCs.
- Adding only one directed implication edge per 2-SAT clause instead of both.
- Reaching for Tarjan's/Kosaraju's SCC machinery on a fundamentally undirected equivalence-class problem where Union-Find is the right, simpler tool.

---

## Cheat card

```
LOW-LINK       low[u] = min(disc[u], low[child] for tree children,
               disc[ancestor] for back edges) -- the core mechanism
TARJAN SCC     single DFS + stack; SCC root iff low[v] == disc[v];
               O(V+E); produces SCCs in REVERSE topological order free
KOSARAJU SCC   DFS for finish order -> DFS on transpose in decreasing
               finish-time order; O(V+E), 2 passes, easier proof
BRIDGE         tree edge (u,v): bridge iff low[v] > disc[u]  (STRICT)
ARTICULATION   non-root u: articulation iff some child low[v] >= disc[u]
POINT          root u: articulation iff MORE THAN ONE DFS-tree child
2-SAT          clause (a OR b) -> edges NOT a->b, NOT b->a
               UNSAT iff x and NOT x share an SCC
               assign true if pos-literal SCC is LATER in topo order
COMPLEXITY     all of the above: O(V+E); 2-SAT: O(vars + clauses)
2-SAT vs 3SAT  2-SAT in P (this reduction); 3-SAT NP-complete, no
               equivalent 2-edge-per-clause reduction exists
WATCH          root special case; strict vs non-strict bridge/AP mixup;
               parent-exclusion in low-link; visited vs on-stack; Union-
               Find suffices for undirected equivalence, don't over-reach
```

## Sources

- Tarjan, R. (1972). "Depth-First Search and Linear Graph Algorithms." SIAM Journal on Computing, 1(2), 146-160.
- Sharir, M. (1981). "A Strong-Connectivity Algorithm and its Applications in Data Flow Analysis." Computers & Mathematics with Applications, 7(1), 67-72. (Independent rediscovery closely related to Kosaraju's approach.)
- Aspvall, B., Plass, M.F., Tarjan, R.E. (1979). "A Linear-Time Algorithm for Testing the Truth of Certain Quantified Boolean Formulas." Information Processing Letters, 8(3), 121-123.
- [Critical Connections in a Network — LeetCode](https://leetcode.com/problems/critical-connections-in-a-network/) — accessed 2026-07-26
- [Strongly Connected Components — CP-Algorithms](https://cp-algorithms.com/graph/strongly-connected-components.html) — accessed 2026-07-26
- [2-SAT — CP-Algorithms](https://cp-algorithms.com/graph/2SAT.html) — accessed 2026-07-26
- [Account Merging — LeetCode](https://leetcode.com/problems/accounts-merge/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
