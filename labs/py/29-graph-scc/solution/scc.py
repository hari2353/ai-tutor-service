"""Lab 29 solution — SCC, bridges, articulation points, 2-SAT.

All traversals are ITERATIVE (explicit stacks): recursive DFS dies at
~1000 frames on deep graphs, and these are exactly the algorithms that
get run on million-edge dependency graphs. Pure stdlib.
"""


def tarjan_scc(graph):
    """Iterative Tarjan: ONE DFS pass, discovery times + low-links + a
    component stack.

    Invariant: low[v] = smallest discovery time reachable from v's
    subtree using at most one back edge into an OPEN component. When a
    vertex finishes with low[v] == disc[v], nothing above v on the
    component stack can reach anything earlier — v roots a complete,
    maximal SCC.

    Returns list of SCCs, each sorted ascending, list sorted -> the
    canonical deterministic form (identical to kosaraju_scc's output).
    """
    n = len(graph)
    disc = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    comp_stack = []
    sccs = []
    timer = 0

    for root in range(n):
        if disc[root] != -1:
            continue
        disc[root] = low[root] = timer
        timer += 1
        comp_stack.append(root)
        on_stack[root] = True
        frames = [(root, 0)]                 # (vertex, next neighbor idx)
        while frames:
            v, i = frames[-1]
            if i < len(graph[v]):
                frames[-1] = (v, i + 1)
                w = graph[v][i]
                if disc[w] == -1:            # tree edge: descend
                    disc[w] = low[w] = timer
                    timer += 1
                    comp_stack.append(w)
                    on_stack[w] = True
                    frames.append((w, 0))
                elif on_stack[w]:            # edge into an open component
                    low[v] = min(low[v], disc[w])
            else:                            # v finished
                frames.pop()
                if frames:                   # propagate low to parent
                    p, _ = frames[-1]
                    low[p] = min(low[p], low[v])
                if low[v] == disc[v]:        # v roots an SCC
                    comp = []
                    while True:
                        w = comp_stack.pop()
                        on_stack[w] = False
                        comp.append(w)
                        if w == v:
                            break
                    sccs.append(sorted(comp))
    return sorted(sccs)


def kosaraju_scc(graph):
    """Two passes: DFS on G recording finish order, then DFS on the
    transpose in DECREASING finish order — each second-pass tree is
    exactly one SCC. Returns the same canonical form as tarjan_scc.
    """
    n = len(graph)

    def _postorder(adj):
        """Iterative DFS postorder (= finish order), mark on entry."""
        seen = [False] * n
        post = []
        for s in range(n):
            if seen[s]:
                continue
            seen[s] = True
            frames = [(s, 0)]
            while frames:
                v, i = frames[-1]
                if i < len(adj[v]):
                    frames[-1] = (v, i + 1)
                    w = adj[v][i]
                    if not seen[w]:
                        seen[w] = True
                        frames.append((w, 0))
                else:
                    frames.pop()
                    post.append(v)
        return post

    post = _postorder(graph)

    transpose = [[] for _ in range(n)]
    for u in range(n):
        for w in graph[u]:
            transpose[w].append(u)

    seen = [False] * n
    sccs = []
    for s in reversed(post):                 # decreasing finish time
        if seen[s]:
            continue
        seen[s] = True
        comp = [s]
        frames = [(s, 0)]
        while frames:
            v, i = frames[-1]
            if i < len(transpose[v]):
                frames[-1] = (v, i + 1)
                w = transpose[v][i]
                if not seen[w]:
                    seen[w] = True
                    comp.append(w)
                    frames.append((w, 0))
            else:
                frames.pop()
        sccs.append(sorted(comp))
    return sorted(sccs)


def _undirected_lowlink(graph, collect):
    """Shared iterative low-link DFS over an undirected bucket graph.

    Each edge must appear in BOTH endpoints' buckets. Only the ONE tree
    edge back to the parent is skipped, so a parallel copy of the parent
    edge correctly counts as a back edge (a doubled edge is never a
    bridge, and never makes the parent a cut vertex through that
    child). Self-loops are skipped: never bridges, no low effect.

    collect(parent, child, low_child, child_is_last_of_root) is called
    when a child frame finishes; `collect` decides bridges vs APs.
    """
    n = len(graph)
    disc = [-1] * n
    low = [0] * n
    children = [0] * n
    timer = 0

    for root in range(n):
        if disc[root] != -1:
            continue
        disc[root] = low[root] = timer
        timer += 1
        # frame: [v, parent, next neighbor idx, parent-skip-used]
        frames = [[root, -1, 0, False]]
        while frames:
            f = frames[-1]
            v, parent, i, skipped = f
            if i < len(graph[v]):
                f[2] += 1
                w = graph[v][i]
                if w == v:
                    continue                  # self-loop: ignore
                if w == parent and not skipped:
                    f[3] = True               # skip the tree edge ONCE
                    continue
                if disc[w] == -1:
                    disc[w] = low[w] = timer
                    timer += 1
                    children[v] += 1
                    frames.append([w, v, 0, False])
                else:
                    # back edge to an ancestor (a visited descendant has
                    # disc[w] > disc[v] >= low[v], so this min is a no-op)
                    low[v] = min(low[v], disc[w])
            else:
                frames.pop()
                if frames:
                    p = frames[-1][0]
                    collect(p, v, low[v], children, disc, root)
                    low[p] = min(low[p], low[v])
    return disc, low


def bridges(graph):
    """Bridges of an undirected graph (adjacency buckets, each edge in
    both buckets).

    Tree edge (p, v) is a bridge iff low[v] > disc[p]: v's subtree
    cannot reach p or above except through that edge. Returns sorted
    list of normalized (min(u, v), max(u, v)) tuples.
    """
    found = []

    def collect(p, v, low_v, children, disc, root):
        if low_v > disc[p]:
            found.append((min(p, v), max(p, v)))

    _undirected_lowlink(graph, collect)
    return sorted(found)


def articulation_points(graph):
    """Cut vertices of an undirected graph (adjacency buckets).

    Root of a DFS tree: cut vertex iff >= 2 tree children. Any other
    vertex p: cut vertex iff some child v has low[v] >= disc[p]. Returns
    a sorted list.
    """
    cuts = set()

    def collect(p, v, low_v, children, disc, root):
        if p == root:
            if children[root] >= 2:
                cuts.add(root)
        elif low_v >= disc[p]:
            cuts.add(p)

    _undirected_lowlink(graph, collect)
    return sorted(cuts)


def two_sat(clauses, n_vars):
    """2-SAT via implication graph + SCC condensation.

    clauses: list of (a, b) pairs of NONZERO ints, |a| <= n_vars;
    negative means negated; variable x is 1..n_vars. Each clause
    (a OR b) contributes edges (not-a -> b) and (not-b -> a).

    Unsatisfiable iff some x and -x share an SCC -> returns
    (False, None). Otherwise the assignment comes from the
    condensation's topological order: x is True iff comp(x) comes
    strictly after comp(-x) — then every edge out of a true literal
    ends at a true literal, which satisfies every clause.
    """
    def node(lit):
        return lit - 1 if lit > 0 else n_vars - lit - 1

    n = 2 * n_vars
    imp = [[] for _ in range(n)]
    for a, b in clauses:
        imp[node(-a)].append(node(b))
        imp[node(-b)].append(node(a))

    sccs = tarjan_scc(imp)
    comp_of = {}
    for cid, comp in enumerate(sccs):
        for v in comp:
            comp_of[v] = cid

    for x in range(1, n_vars + 1):
        if comp_of[node(x)] == comp_of[node(-x)]:
            return False, None               # x <-> not-x: contradiction

    # condensation: unique edges between distinct components
    cond = {cid: set() for cid in range(len(sccs))}
    for u in range(n):
        for w in imp[u]:
            cu, cw = comp_of[u], comp_of[w]
            if cu != cw:
                cond[cu].add(cw)

    # Kahn topological order over the condensation DAG
    from collections import deque
    indeg = {cid: 0 for cid in cond}
    for cu in cond:
        for cw in cond[cu]:
            indeg[cw] += 1
    rank = {}
    queue = deque(sorted(cid for cid in indeg if indeg[cid] == 0))
    order = 0
    while queue:
        cid = queue.popleft()
        rank[cid] = order
        order += 1
        for cw in sorted(cond[cid]):
            indeg[cw] -= 1
            if indeg[cw] == 0:
                queue.append(cw)

    assignment = [rank[comp_of[node(x)]] > rank[comp_of[node(-x)]]
                  for x in range(1, n_vars + 1)]
    return True, assignment
