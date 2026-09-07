"""Lab 26 — reference solution."""
from __future__ import annotations

from collections import deque
from typing import Optional


# ------------------------------------------------------------------ representations
def to_adjacency_list(n: int, edges: list, directed: bool = False) -> list[list[int]]:
    adj = [[] for _ in range(n)]
    for e in edges:
        u, v = e[0], e[1]
        adj[u].append(v)
        if not directed:
            adj[v].append(u)
    return adj


def to_adjacency_matrix(n: int, edges: list, directed: bool = False) -> list[list[int]]:
    m = [[0] * n for _ in range(n)]
    for e in edges:
        u, v = e[0], e[1]
        w = e[2] if len(e) == 3 else 1
        m[u][v] = w
        if not directed:
            m[v][u] = w
    return m


def to_edge_list(matrix: list[list[int]], directed: bool = False,
                 weighted: bool = False) -> list:
    n = len(matrix)
    edges = []
    for i in range(n):
        # undirected: upper triangle INCLUDING the diagonal (self-loops
        # live on the diagonal and must survive); directed: the full row
        for j in range(0 if directed else i, n):
            w = matrix[i][j]
            if w == 0:
                continue
            edges.append((i, j, w) if weighted else (i, j))
    return edges


# ------------------------------------------------------------------ traversals
def bfs_order(graph: list[list[int]], src: int) -> list[int]:
    visited = [False] * len(graph)
    visited[src] = True
    q = deque([src])
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph[u]:
            if not visited[v]:
                visited[v] = True
                q.append(v)
    return order


def dfs_order(graph: list[list[int]], src: int) -> list[int]:
    n = len(graph)
    visited = [False] * n
    stack = [src]
    order = []
    while stack:
        u = stack.pop()
        if visited[u]:                 # re-popped after a sibling marked it
            continue
        visited[u] = True
        order.append(u)
        for v in reversed(graph[u]):   # reverse push == recursive preorder
            if not visited[v]:
                stack.append(v)
    return order


# ------------------------------------------------------------------ structure
def connected_components(graph: list[list[int]]) -> list[list[int]]:
    n = len(graph)
    seen = [False] * n
    comps = []
    for s in range(n):                 # outer loop: disconnected graphs
        if seen[s]:
            continue
        seen[s] = True
        comp = []
        q = deque([s])
        while q:
            u = q.popleft()
            comp.append(u)
            for v in graph[u]:
                if not seen[v]:
                    seen[v] = True
                    q.append(v)
        comps.append(sorted(comp))
    comps.sort()
    return comps


def has_cycle_undirected(graph: list[list[int]]) -> bool:
    n = len(graph)
    visited = [False] * n

    def dfs(u: int, parent: int) -> bool:
        visited[u] = True
        for v in graph[u]:
            if not visited[v]:
                if dfs(v, u):
                    return True
            elif v != parent:          # visited and not where we came from
                return True
        return False

    return any(not visited[i] and dfs(i, -1) for i in range(n))


def has_cycle_directed(graph: list[list[int]]) -> bool:
    WHITE, GRAY, BLACK = 0, 1, 2
    n = len(graph)
    color = [WHITE] * n

    def dfs(u: int) -> bool:
        color[u] = GRAY
        for v in graph[u]:
            if color[v] == GRAY:       # back edge to an active ancestor
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    return any(color[i] == WHITE and dfs(i) for i in range(n))


def is_bipartite(graph: list[list[int]]) -> tuple[bool, Optional[dict]]:
    n = len(graph)
    color: dict[int, int] = {}
    for start in range(n):             # outer loop: disconnected graphs
        if start in color:
            continue
        color[start] = 0
        q = deque([start])
        while q:
            u = q.popleft()
            for v in graph[u]:
                if v not in color:
                    color[v] = 1 - color[u]
                    q.append(v)
                elif color[v] == color[u]:
                    return False, None  # odd cycle forced a conflict
    return True, color


def degree_sum(graph: list[list[int]]) -> int:
    return sum(len(bucket) for bucket in graph)
