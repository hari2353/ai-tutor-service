"""Lab 19 — union-find. Reference solution."""
from __future__ import annotations

from typing import List, Sequence, Tuple


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n
        self.sz = [1] * n
        self._count = n

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:              # compress
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: int, y: int) -> bool:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        self.sz[rx] += self.sz[ry]
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        self._count -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)

    @property
    def count(self) -> int:
        return self._count

    def size(self, x: int) -> int:
        return self.sz[self.find(x)]


def connected_components(n: int, edges: Sequence[Sequence[int]]) -> int:
    uf = UnionFind(n)
    for a, b in edges:
        uf.union(a, b)
    return uf.count


def redundant_connection(edges: Sequence[Sequence[int]]) -> Sequence[int]:
    n = len(edges)
    uf = UnionFind(n)                             # nodes are 1..n → store n+1? use max node
    nodes = {v for e in edges for v in e}
    uf = UnionFind(max(nodes) + 1)
    for a, b in edges:
        if not uf.union(a, b):
            return [a, b]
    return []


def accounts_merge(accounts: Sequence[Sequence[str]]) -> List[List[str]]:
    uf = UnionFind(len(accounts))
    owner: dict = {}                               # email -> account index
    for i, acc in enumerate(accounts):
        for email in acc[1:]:
            if email in owner:
                uf.union(i, owner[email])
            else:
                owner[email] = i
    groups: dict = {}                              # root -> set of emails
    for i, acc in enumerate(accounts):
        root = uf.find(i)
        groups.setdefault(root, set()).update(acc[1:])
    out = []
    for root, emails in groups.items():
        name = accounts[root][0]
        out.append([name] + sorted(emails))
    out.sort(key=lambda g: (g[0], g[1]))
    return out


def number_of_islands_ii(m: int, n: int,
                         positions: Sequence[Sequence[int]]) -> List[int]:
    uf = UnionFind(m * n)
    land: set = set()
    counts: List[int] = []
    current = 0

    def idx(r, c):
        return r * n + c

    for r, c in positions:
        key = idx(r, c)
        if key in land:
            counts.append(current)
            continue
        land.add(key)
        current += 1
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < m and 0 <= nc < n and idx(nr, nc) in land:
                if uf.union(key, idx(nr, nc)):
                    current -= 1
        counts.append(current)
    return counts


def kruskal_mst(n: int,
                edges: Sequence[Tuple[int, int, int]]) -> Tuple[int, List[Tuple[int, int, int]]]:
    uf = UnionFind(n)
    total = 0
    accepted: List[Tuple[int, int, int]] = []
    for w, a, b in sorted(edges):
        if uf.union(a, b):
            total += w
            accepted.append((w, a, b))
            if len(accepted) == n - 1:
                break
    return total, accepted


def minimum_spanning_cost(n: int, edges: Sequence[Tuple[int, int, int]]) -> int:
    return kruskal_mst(n, edges)[0]
