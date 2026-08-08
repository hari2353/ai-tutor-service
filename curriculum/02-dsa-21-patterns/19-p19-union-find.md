# Pattern: Union-Find (Disjoint Set Union)

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** arrays, T02-p17-topological-sort, graphs
> **Module id:** `T02-p19-union-find` · **Tags:** pattern, graph
> **Lab:** `labs/py/19-union-find/`

## The 30-second version

Union-Find (Disjoint Set Union, DSU) maintains a collection of disjoint sets under two operations — `find(x)` (which set does x belong to) and `union(x, y)` (merge x's and y's sets) — and it's the pattern for "are these two things connected/in the same group," "how many groups are there," and "does adding this edge create a cycle," all without rebuilding a full graph traversal from scratch on every query. Naive implementations can degenerate to O(n) per `find` on a skewed tree; two independent optimizations fix that: **union by rank/size** (always attach the smaller tree under the bigger tree's root, keeping the structure shallow) and **path compression** (during `find`, rewire every visited node to point directly at the root, flattening future lookups). Applied together, amortized complexity per operation is **O(α(n))**, where α is the inverse Ackermann function — for any practically conceivable n, α(n) ≤ 4, so this is "effectively constant time" without literally being O(1). Recognize it whenever a problem asks about connectivity, grouping, or cycle detection in an **undirected** graph, especially when edges/queries arrive incrementally over time rather than as one static graph to traverse once.

## Why this gets asked

It tests whether you know two specific, named optimizations (not just "union-find exists") and can state precisely what breaks without each one — a DSU with only union-by-rank and no path compression is fine but not optimal; one with only path compression and no union-by-rank still works but can be provably worse in adversarial union orders. Interviewers who've built network partition detection, social-graph "are these accounts connected" queries, image-processing connected-component labeling, or Kruskal's MST implementations in a scheduling/clustering system have hit the real failure this models: a naive union-by-arbitrary-attachment DSU degrading to a linked list under a bad insertion order, turning what should be near-constant-time connectivity queries into O(n) each, which silently kills throughput on exactly the kind of incremental, high-volume connectivity check DSU exists to make fast.

---

## Lineage: past → present → future

**What came before.** Before union-find had a name, connectivity queries were answered by re-running BFS/DFS from scratch on every query — fine for a single static "is the whole graph connected" check but O(V+E) *per query* if you need to repeatedly ask "are x and y connected" as edges are added incrementally, which is wasteful when you could instead maintain state across queries. The core union-find idea (represent each set as a tree, union by attaching one root under another) dates to the 1960s; the union-by-rank/size and path-compression optimizations were analyzed and popularized through the 1970s, with Robert Tarjan's 1975 analysis proving the tight inverse-Ackermann bound that makes this pattern's complexity claim precise rather than hand-wavy ("nearly constant"). The pain the combined optimizations killed: unbounded per-query degradation from naive tree-based DSU implementations under adversarial union sequences.

**Where it stands now.** Fully settled: union by rank (or the equivalent union by size) plus path compression together give the proven O(α(n)) amortized bound, and this is universally taught as the standard implementation — there's no live methodological disagreement about the algorithm itself. The only real interview-relevant nuance still worth stating precisely: path compression alone (without union by rank) already gives an excellent amortized bound (O(log n) amortized) and union by rank alone (without path compression) gives O(log n) worst case per operation — it's the *combination* that reaches the tighter inverse-Ackermann bound, and conflating "either one alone" with "both together" is a common overstatement.

**Where it's heading.** No open research question for the classic version at interview scope. Where DSU is actively extended in practice: **weighted/union-find with relations** (Evaluate Division — track a ratio/offset between each node and its parent, not just membership, so you can answer "what's the relationship between x and y," not just "are they connected"), and **persistent/rollback DSU** (support undoing a union, needed in some offline/divide-and-conquer-over-time graph algorithms and in incremental connectivity problems where edges can also be removed, which plain union-find with path compression cannot support efficiently since compression destroys the information needed to undo a union cleanly).

---

## Mental model

Each set is a tree; the root is that set's canonical representative. `find(x)` walks up parent pointers to the root; `union(x, y)` finds both roots and links one under the other.

```
initial: everyone is their own root
1  2  3  4  5

union(1,2): attach smaller/lower-rank tree under the other's root
   1        (root)
   |
   2

union(3,4):
   3
   |
   4

union(2,3): attach root(2..)'s tree under root(3..)'s tree (by rank/size)
      1
      |
      2
      |
      3
      |
      4

find(4) without compression: 4 -> 3 -> 2 -> 1   (walks the whole chain, O(depth))
find(4) WITH compression:    4 -> 1 directly, and 3, 2 also repointed straight to 1
                              (every node touched during this find now costs O(1) next time)
```

Path compression is what turns "a chain you have to walk every time" into "a flat fan pointing straight at the root after the first walk" — the tree only ever gets shallower, never deeper, from compression.

---

## Recognition heuristics

- **"Are these two nodes/accounts/cells connected?"** on an **undirected** graph, especially with many repeated queries as edges accumulate over time.
- **"How many connected components/provinces/groups are there?"** — count distinct roots after processing all unions.
- **"Does adding this edge create a cycle?"** in an undirected graph — if `find(u) == find(v)` before you union them, the edge you're about to add closes a cycle; this is exactly Kruskal's MST cycle check and Redundant Connection's core logic.
- **"Merge these groups/accounts that share some identifying attribute"** (Accounts Merge) — union accounts sharing any element, then group by final root.
- **Incremental/streaming edge additions** where you need an up-to-date connectivity answer after each addition, rather than one static graph to traverse once — DSU amortizes across the whole sequence; re-running BFS/DFS per edge would be far more expensive.
- **"Smallest string after swaps at given index pairs"** (Smallest String With Swaps) — index pairs that can be freely swapped form connectivity groups; within each group, characters can be rearranged into any order, so sort each group's characters independently.

If the graph is **directed**, or the relationship isn't symmetric, this pattern doesn't apply as-is — reach for topological sort (`T02-p17-topological-sort`) or plain DFS/BFS (`T02-p07-bfs`, `T02-p08-dfs`) instead.

---

## How it actually works — path compression, union by rank, and why α(n)

**find(x) with path compression.** Walk up the parent chain from `x` to the root. Then, either recursively or in a second pass, repoint every node visited along that path directly to the root. This means the *next* `find` call on any of those nodes is O(1) — the path only ever gets flatter, and it never gets deeper as a result of compression.

```python
def find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])   # recursive: repoint x straight to the root
    return parent[x]
```

**union(x, y) with union by rank.** `rank[x]` approximates the height of the tree rooted at `x` (it's an upper bound, not an exact height once path compression starts flattening things). When merging two trees, always attach the shorter tree under the taller tree's root — this keeps the resulting tree's height bounded by the taller of the two inputs, rather than letting a long chain form by attaching arbitrarily. If ranks are equal, attach either way and increment the surviving root's rank by 1.

```python
def union(x, y):
    rx, ry = find(x), find(y)
    if rx == ry:
        return False          # already in the same set — this edge would create a cycle
    if rank[rx] < rank[ry]:
        rx, ry = ry, rx
    parent[ry] = rx
    if rank[rx] == rank[ry]:
        rank[rx] += 1
    return True
```

**Why the combination gives O(α(n)), not just "roughly O(1)."** Union by rank alone bounds tree height to O(log n), giving O(log n) per `find` even without compression. Path compression alone (with arbitrary, non-rank-based unions) gives an amortized O(log n) per operation over a sequence, proven via a potential-function/amortized argument. Tarjan's 1975 analysis shows that using **both together**, a sequence of `m` operations on `n` elements takes **O(m · α(n))** total, where α is the inverse of the extremely fast-growing Ackermann function — meaning α(n) is at most 4 for any n you could ever construct in the physical universe (it only exceeds 4 for inputs vastly larger than the number of atoms in the observable universe). "Effectively constant" is the honest way to describe this: it is a real, proven, slowly-growing function, not a literal constant, but no realistic input will ever push it past single digits.

---

## Template code (Python, Java, Go)

```python
# Python — Union-Find with path compression + union by rank
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n            # number of distinct components

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])   # path compression
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False                                  # would create a cycle
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx                               # union by rank
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        self.count -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)


# Redundant Connection (LC 684) — first edge whose union fails (cycle) is the answer
def find_redundant_connection(edges: list[list[int]]) -> list[int]:
    n = len(edges)
    uf = UnionFind(n + 1)
    for u, v in edges:
        if not uf.union(u, v):
            return [u, v]
    return []
```

```java
// Java — Union-Find with path compression + union by rank
class UnionFind {
    int[] parent, rank;
    int count;

    UnionFind(int n) {
        parent = new int[n];
        rank = new int[n];
        count = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }

    int find(int x) {
        if (parent[x] != x) {
            parent[x] = find(parent[x]);   // path compression
        }
        return parent[x];
    }

    boolean union(int x, int y) {
        int rx = find(x), ry = find(y);
        if (rx == ry) return false;         // would create a cycle
        if (rank[rx] < rank[ry]) { int tmp = rx; rx = ry; ry = tmp; }
        parent[ry] = rx;                    // union by rank
        if (rank[rx] == rank[ry]) rank[rx]++;
        count--;
        return true;
    }
}
```

```go
// Go — Union-Find with path compression + union by rank
type UnionFind struct {
    parent, rank []int
    count        int
}

func NewUnionFind(n int) *UnionFind {
    uf := &UnionFind{parent: make([]int, n), rank: make([]int, n), count: n}
    for i := range uf.parent {
        uf.parent[i] = i
    }
    return uf
}

func (uf *UnionFind) Find(x int) int {
    if uf.parent[x] != x {
        uf.parent[x] = uf.Find(uf.parent[x]) // path compression
    }
    return uf.parent[x]
}

func (uf *UnionFind) Union(x, y int) bool {
    rx, ry := uf.Find(x), uf.Find(y)
    if rx == ry {
        return false // would create a cycle
    }
    if uf.rank[rx] < uf.rank[ry] {
        rx, ry = ry, rx
    }
    uf.parent[ry] = rx // union by rank
    if uf.rank[rx] == uf.rank[ry] {
        uf.rank[rx]++
    }
    uf.count--
    return true
}
```

## Complexity, derived

With **both** path compression and union by rank: a sequence of `m` `find`/`union` operations over `n` elements runs in **O(m · α(n))** total (Tarjan, 1975), where α is the inverse Ackermann function — for all practical `n` (up to and vastly beyond any real dataset size), α(n) ≤ 4, so each operation is "effectively O(1)" though not a literal constant in the strict theoretical sense. **With union by rank alone** (no compression), height stays O(log n), so `find` is O(log n) per call, worst case, no amortization needed. **With path compression alone** (arbitrary, non-rank union), a classical amortized argument gives O(log n) amortized per operation over a sequence. **Space is O(n)** for the parent and rank arrays. Without *either* optimization (arbitrary parent attachment, no compression), a specifically adversarial union order can produce a pure linked-list-shaped tree, making a single `find` cost O(n) — the exact production failure mode this pattern exists to prevent.

---

## The 5 variants interviewers actually ask

1. **Number of Provinces (LC 547) — count connected components given an adjacency matrix.** Union every connected pair, then count distinct roots (or track a running `count` decremented on every successful union, as in the template above).
2. **Redundant Connection (LC 684) — find the one edge that, if removed, turns the graph back into a tree.** Process edges in order; the first edge whose `union` call returns false (both endpoints already share a root) is the answer, since it's the edge that closes the cycle.
3. **Accounts Merge (LC 721) — merge accounts that share any common email.** Union accounts (or, more precisely, union the emails and use a representative email per account), then group all emails by their final root and reconstruct merged account lists.
4. **Satisfiability of Equality Equations (LC 990) — given `a==b` and `a!=b` constraints, determine if they're all simultaneously satisfiable.** Union all `==` pairs first (they must be in the same set), then check every `!=` pair does *not* share a root — if any `!=` pair ends up connected via the `==` unions, it's unsatisfiable.
5. **Smallest String With Swaps (LC 1202) — given index pairs that can be freely swapped any number of times, find the lexicographically smallest resulting string.** Union all index pairs into connectivity groups; within each group, any permutation of characters is achievable, so collect each group's characters, sort them, and place them back at the group's sorted index positions.

---

## Common bugs

- **Implementing `union` without `find`'s path compression, or without ever compressing paths, then being surprised by O(n) `find` calls under an adversarial sequence** — the linked-list-degeneration failure mode this whole pattern exists to prevent.
- **Attaching roots arbitrarily instead of by rank/size.** Works correctly but loses the worst-case height guarantee; a long sequence of unions in a bad order can still build a deep chain.
- **Off-by-one in rank increment logic.** Only incrementing rank when the two merged trees have *equal* rank; incrementing on every union inflates rank past a true height bound and can subtly break the height-bound argument (it still works in practice for most implementations, but sloppy rank bookkeeping is a common tell of not actually understanding why the increment condition exists).
- **Confusing "connected" with "equal," and forgetting that `union` should return whether the merge actually happened** — many cycle-detection and Kruskal's-MST-style problems need that boolean (did the two nodes already share a root, meaning this edge is redundant) as the core signal, not a side effect.
- **Using union-find on a directed graph or an inherently asymmetric relationship** — union-find models *symmetric* connectivity; a directed "reachability" question needs a different structure (topological sort, or reachability-specific algorithms), not DSU.
- **Forgetting path compression breaks the ability to "undo" a union.** Once path compression rewires ancestry, there's no way to cleanly reverse a specific union later; if a problem needs rollback/offline deletions, plain path-compressed DSU is the wrong tool without an explicit rollback-DSU variant (union by rank only, no compression, plus an undo stack).

---

## Interview questions

### Q1 — Implement Union-Find with path compression and union by rank; explain both optimizations.
**Testing:** whether both mechanisms are understood individually, not just "union find is fast."
**Answer:** Path compression rewires every node visited during `find` to point directly at the root, flattening future lookups. Union by rank always attaches the shorter tree under the taller tree's root, bounding height growth. Together they give O(α(n)) amortized per operation.
**Follow-up trap:** *"What if you only implement one of the two?"* — union by rank alone gives O(log n) worst case per `find`; path compression alone (arbitrary unions) gives O(log n) amortized; only the combination reaches the tighter inverse-Ackermann bound.

### Q2 — What exactly is α(n), and why is "basically O(1)" an honest description?
**Testing:** whether the candidate actually knows what the bound means instead of reciting "inverse Ackermann" as a buzzword.
**Answer:** α(n) is the inverse of the Ackermann function, one of the fastest-growing functions in mathematics; its inverse grows so slowly that α(n) ≤ 4 for any n up to and vastly beyond the number of atoms in the observable universe. It's a real, proven, non-constant function — but no realistic input will ever push it past single digits, which is why "effectively constant" is the correct informal description.
**Follow-up trap:** *"Is it ever actually O(1) in the strict theoretical sense?"* — no; α(n) does grow (extremely slowly) with n, so the tight statement is O(m·α(n)) for m operations, not O(m). Conflating "effectively constant in practice" with "literally constant" is the overstatement to avoid.

### Q3 — Number of Provinces (LC 547): count the number of connected components in an adjacency-matrix graph.
**Testing:** base union-find application plus component counting.
**Answer:** Union every pair with a matrix entry of 1; maintain a running `count` initialized to `n` and decremented on every successful (non-redundant) union; the final `count` is the number of provinces.
**Follow-up trap:** *"Could you solve this with BFS/DFS instead — when would you prefer union-find?"* — BFS/DFS works fine for a single static count; union-find is preferable when connectivity queries or edge additions happen incrementally over time, since it avoids re-traversing the whole graph on every update.

### Q4 — Redundant Connection (LC 684): find the edge that, if removed, turns the graph back into a tree.
**Testing:** using union-find's cycle-detection signal directly.
**Answer:** Process edges in input order; call `union` on each; the first edge whose `union` call returns false (both endpoints already share a root before this edge) is the one closing a cycle, and removing it restores a tree.
**Follow-up trap:** *"What if there are multiple redundant edges?"* — the problem guarantees exactly one removable edge restores a valid tree, and it's specifically the last redundant edge encountered in input order per the problem's stated tie-breaking rule; processing in order and returning the first `union` failure already respects that.

### Q5 — Accounts Merge (LC 721): merge accounts sharing any common email address.
**Testing:** applying union-find to a non-obvious "graph" built from shared attributes rather than explicit edges.
**Answer:** For each account, union all its emails together (or union against a representative email); after processing every account, group all emails by their final root, then reconstruct merged account entries (name plus sorted emails) per group.
**Follow-up trap:** *"What's the complexity, accounting for the string operations?"* — union-find operations themselves are near-O(1) amortized, but grouping and sorting emails afterward costs O(E log E) where E is the total number of emails, which typically dominates the union-find cost itself.

### Q6 — Satisfiability of Equality Equations (LC 990): given `==` and `!=` constraints, are they all simultaneously satisfiable?
**Testing:** two-pass reasoning with union-find rather than a single pass.
**Answer:** First union every `==` pair. Then, for every `!=` pair, check that they do *not* share a root; if any `!=` pair ends up connected, the constraints are contradictory.
**Follow-up trap:** *"Why must you process all `==` constraints before checking any `!=` constraint?"* — processing order matters because a `!=` check needs the *final* connectivity state; checking it before all unions are applied could miss a connection established by a later `==` constraint.

### Q7 — Smallest String With Swaps (LC 1202): given swappable index pairs, find the lexicographically smallest achievable string.
**Testing:** recognizing connectivity groups as "freely permutable" sets.
**Answer:** Union every given index pair; each resulting connected component's characters can be rearranged into any order using a sequence of pairwise swaps within that component. Collect each component's characters, sort them, and reassign them back to that component's sorted index positions.
**Follow-up trap:** *"Why does connectivity via pairwise swaps imply full permutability within a component, not just adjacent-position swaps?"* — because any permutation can be decomposed into a sequence of transpositions (pairwise swaps), and if every pair of indices you need to swap is reachable via a path of allowed swaps within the same connected component, you can realize any permutation of that component's positions, not merely the originally given swap pairs.

### Q8 — How would you extend union-find to answer "what is the ratio between x and y" rather than just "are x and y connected" (Evaluate Division, LC 399)?
**Testing:** the weighted-union-find generalization.
**Answer:** Store, alongside each parent pointer, a weight representing the ratio to that parent; `find` accumulates (multiplies) weights along the path during compression so each node ends up with a direct weight relative to the root; `union` combines two components' known ratios using the equation linking them.
**Follow-up trap:** *"Is this always solvable with union-find, or does it sometimes need a different approach?"* — union-find works well when relationships are given as pairwise ratios/equations with no additional per-query variables (as in LC 399); for arbitrary linear systems with many query patterns or missing intermediate relationships, a graph BFS with edge-weight multiplication per query is an equally valid and sometimes simpler alternative.

### Q9 — Can you undo a `union` operation? What does that require compared to the standard implementation?
**Testing:** understanding a real limitation of path compression, not just its benefits.
**Answer:** Standard path-compressed union-find cannot cleanly undo a union, because compression permanently rewires ancestry information that a rollback would need to restore. Supporting rollback requires disabling path compression (relying on union by rank/size alone for the O(log n) bound) and maintaining an explicit undo stack recording exactly what changed on each union, so an undo can restore prior parent/rank values precisely.
**Follow-up trap:** *"What's the complexity cost of giving up path compression to support rollback?"* — you fall back to O(log n) per operation (union by rank alone) instead of O(α(n)); this is the real, stated tradeoff for offline/divide-and-conquer-over-time algorithms that need to add and remove edges.

### Q10 — Would you use union-find for a directed graph's reachability queries?
**Testing:** boundary awareness of when the pattern doesn't apply.
**Answer:** No — union-find models symmetric, undirected connectivity; a directed edge `u -> v` doesn't imply `v -> u` is reachable, which breaks the fundamental assumption behind merging two nodes into one set. Directed reachability needs a different approach (e.g., BFS/DFS per query, transitive closure precomputation, or SCC decomposition via Tarjan's/Kosaraju's algorithm if you specifically need "which nodes are mutually reachable").
**Follow-up trap:** *"What if the graph has strongly connected components you want to treat as a single unit?"* — that's exactly the use case for SCC algorithms (Tarjan's or Kosaraju's), which identify sets of *mutually* reachable nodes in a directed graph; once condensed into a DAG of SCCs, union-find-style grouping becomes meaningful again, but the SCC-finding step itself is a distinct algorithm, not union-find.

### Q11 — At what input scale does the constant-factor overhead of union-find's recursive `find` become a real production concern, and how would you address it?
**Testing:** production-level implementation judgment beyond textbook correctness.
**Answer:** Recursive path compression risks stack depth issues on very large, adversarially deep trees before the first compression flattens them (millions of elements with a bad initial union order); an iterative two-pass `find` (first walk to the root without recursion, then a second pass repointing every visited node) avoids recursion-depth risk entirely while preserving the same amortized bound.
**Follow-up trap:** *"Does the iterative version change the complexity bound?"* — no, it's the same O(α(n)) amortized bound; only the implementation mechanics change (iterative vs recursive), trading a small constant-factor difference for removing recursion-depth risk.

---

## Red flags that fail you

- Implementing union-find with neither path compression nor union by rank, and not recognizing the resulting O(n)-per-find degeneration risk.
- Claiming O(1) per operation without the α(n) / amortized qualifier.
- Not knowing that `union`'s boolean return (did this edge already connect two same-root nodes) is the direct mechanism for cycle detection.
- Applying union-find to a directed graph or an asymmetric relationship.
- Not knowing path compression makes rollback/undo impossible without disabling it.
- Confusing SCC (strongly connected components, directed) with plain connected components (undirected, union-find's actual domain).

---

## Cheat card

```
OPERATIONS     find(x) -> root of x's set;  union(x,y) -> merge x's and y's sets
PATH COMPRESS  during find, repoint every visited node straight to the root
UNION BY RANK  attach shorter tree under taller tree's root; equal rank -> increment survivor's rank
BOTH TOGETHER  O(alpha(n)) amortized per op (Tarjan 1975); alpha(n)<=4 for any realistic n
RANK ONLY      O(log n) worst case per find (no compression)
COMPRESS ONLY  O(log n) amortized per op (arbitrary union order)
NEITHER        adversarial union order -> linked-list tree -> O(n) per find
CYCLE CHECK    union(u,v) returns False  <=>  find(u)==find(v) already  <=>  edge closes a cycle
COMPONENTS     count = n initially, decrement on every successful union
PROVINCES      LC547: union matrix pairs, count distinct roots
REDUNDANT CONN LC684: first edge whose union() fails is the answer
ACCOUNTS MERGE LC721: union shared emails, group final roots, sort+rebuild
EQUALITY EQNS  LC990: union all == first, THEN check no != pair shares a root
SWAP GROUPS    LC1202: union swap pairs; sort each component's chars independently
WEIGHTED DSU   Evaluate Division (LC399): store ratio-to-parent, multiply along path on find
LIMITATION     path compression breaks union rollback; need union-by-rank-only + undo stack for that
DOMAIN         undirected / symmetric connectivity ONLY — not directed reachability (use SCC instead)
```

## Sources

- [Number of Provinces — LeetCode](https://leetcode.com/problems/number-of-provinces/) — accessed 2026-07-26
- [Redundant Connection — LeetCode](https://leetcode.com/problems/redundant-connection/) — accessed 2026-07-26
- [Accounts Merge — LeetCode](https://leetcode.com/problems/accounts-merge/) — accessed 2026-07-26
- [Satisfiability of Equality Equations — LeetCode](https://leetcode.com/problems/satisfiability-of-equality-equations/) — accessed 2026-07-26
- [Smallest String With Swaps — LeetCode](https://leetcode.com/problems/smallest-string-with-swaps/) — accessed 2026-07-26
- [Evaluate Division — LeetCode](https://leetcode.com/problems/evaluate-division/) — accessed 2026-07-26
- [Disjoint-set data structure — Wikipedia](https://en.wikipedia.org/wiki/Disjoint-set_data_structure) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
