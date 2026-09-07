"""Lab 28 solution — MST, max-flow, min-cut, bipartite matching."""
import heapq
from collections import deque


class UnionFind:
    """Disjoint-set with path compression + union by rank."""

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
        if self.rank[ra] < self.rank[rb]:          # union by rank
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True

    def connected(self, a, b):
        return self.find(a) == self.find(b)


def kruskal_mst(n, edges):
    mst, total = [], 0
    uf = UnionFind(n)
    for w, u, v in sorted(edges, key=lambda e: e[0]):
        if uf.union(u, v):        # not a cycle -> safe by the cut property
            mst.append((w, u, v))
            total += w
    return mst, total


def prim_mst(n, edges, start=0):
    adj = [[] for _ in range(n)]
    for w, u, v in edges:
        adj[u].append((w, v))
        adj[v].append((w, u))
    seen = [False] * n
    heap = [(0, start, -1)]       # (weight, vertex, the tree vertex it came from)
    mst, total = [], 0
    while heap:
        w, u, prev = heapq.heappop(heap)
        if seen[u]:
            continue              # stale heap entry
        seen[u] = True
        if prev != -1:
            mst.append((w, prev, u))
            total += w
        for wv, v in adj[u]:
            if not seen[v]:
                heapq.heappush(heap, (wv, v, u))
    return mst, total


def edmonds_karp(n, capacity, s, t):
    cap = [row[:] for row in capacity]          # residual graph, input untouched
    flow = [[0] * n for _ in range(n)]
    total = 0
    while True:
        # BFS for the SHORTEST augmenting path (that's what makes it EK)
        parent = [-1] * n
        parent[s] = s
        q = deque([s])
        while q and parent[t] == -1:
            u = q.popleft()
            for v in range(n):
                if parent[v] == -1 and cap[u][v] > 0:
                    parent[v] = u
                    q.append(v)
        if parent[t] == -1:
            break                               # no augmenting path: optimal
        bottleneck = float("inf")
        v = t
        while v != s:
            u = parent[v]
            bottleneck = min(bottleneck, cap[u][v])
            v = u
        v = t
        while v != s:
            u = parent[v]
            cap[u][v] -= bottleneck             # forward residual
            cap[v][u] += bottleneck             # reverse residual ("undo")
            flow[u][v] += bottleneck
            flow[v][u] -= bottleneck
            v = u
        total += bottleneck
    return total, flow


def min_cut(n, capacity, s, t):
    total, _flow = edmonds_karp(n, capacity, s, t)
    # one more pass over the FINAL residual graph: reachable-from-s set
    cap = [row[:] for row in capacity]
    flow = [[0] * n for _ in range(n)]
    while True:
        parent = [-1] * n
        parent[s] = s
        q = deque([s])
        while q and parent[t] == -1:
            u = q.popleft()
            for v in range(n):
                if parent[v] == -1 and cap[u][v] > 0:
                    parent[v] = u
                    q.append(v)
        if parent[t] == -1:
            break
        bottleneck = float("inf")
        v = t
        while v != s:
            u = parent[v]
            bottleneck = min(bottleneck, cap[u][v])
            v = u
        v = t
        while v != s:
            u = parent[v]
            cap[u][v] -= bottleneck
            cap[v][u] += bottleneck
            flow[u][v] += bottleneck
            flow[v][u] -= bottleneck
            v = u
    seen = [False] * n
    seen[s] = True
    q = deque([s])
    while q:
        u = q.popleft()
        for v in range(n):
            if not seen[v] and cap[u][v] > 0:
                seen[v] = True
                q.append(v)
    return total, {i for i in range(n) if seen[i]}


def bipartite_matching(n_left, n_right, edges):
    n = 2 + n_left + n_right                    # source | left | right | sink
    cap = [[0] * n for _ in range(n)]
    for l in range(n_left):
        cap[0][1 + l] = 1                      # source -> left, cap 1
    for l, r in edges:
        cap[1 + l][1 + n_left + r] = 1         # left -> right, cap 1
    for r in range(n_right):
        cap[1 + n_left + r][n - 1] = 1         # right -> sink, cap 1
    value, _flows = edmonds_karp(n, cap, 0, n - 1)
    return value
