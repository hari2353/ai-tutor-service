"""Lab 17 — topological sort. Reference solution."""
from __future__ import annotations

import heapq
from typing import List, Optional, Sequence, Tuple


def _adj(n, edges):
    g = [[] for _ in range(n)]
    for a, b in edges:
        g[a].append(b)
    return g


def kahns_toposort(n: int, edges: Sequence[Tuple[int, int]]) -> Optional[List[int]]:
    g = _adj(n, edges)
    for out in g:
        out.sort()
    indeg = [0] * n
    for a, b in edges:
        indeg[b] += 1
    ready = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(ready)
    order: List[int] = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in g[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, v)
    return order if len(order) == n else None


def dfs_toposort(n: int, edges: Sequence[Tuple[int, int]]) -> Optional[List[int]]:
    g = _adj(n, edges)
    for out in g:
        out.sort()
    WHITE, GRAY, BLACK = 0, 1, 2
    colour = [WHITE] * n
    order: List[int] = []

    def visit(u: int) -> bool:
        colour[u] = GRAY
        for v in g[u]:
            if colour[v] == GRAY:
                return False
            if colour[v] == WHITE and not visit(v):
                return False
        colour[u] = BLACK
        order.append(u)
        return True

    for u in range(n):
        if colour[u] == WHITE and not visit(u):
            return None
    order.reverse()
    return order


def course_schedule(n: int, prerequisites: Sequence[Sequence[int]]) -> Optional[List[int]]:
    # [course, prereq] means edge prereq -> course
    edges = [(p, c) for c, p in prerequisites]
    return kahns_toposort(n, edges)


def build_order(projects: Sequence[str],
                dependencies: Sequence[Tuple[str, str]]) -> Optional[List[str]]:
    names = sorted(set(projects))
    for a, b in dependencies:
        if a not in set(projects) or b not in set(projects):
            raise ValueError(f"unknown project in dependency: {a!r} -> {b!r}")
    idx = {p: i for i, p in enumerate(names)}
    edges = [(idx[a], idx[b]) for a, b in dependencies]
    order = kahns_toposort(len(names), edges)
    return [names[i] for i in order] if order is not None else None


def alien_dictionary(words: Sequence[str]) -> str:
    if len(words) == 0:
        return ""
    # prefix violation: longer word before its own prefix
    for w1, w2 in zip(words, words[1:]):
        if len(w1) > len(w2) and w1.startswith(w2):
            return ""
    chars = set("".join(words))
    edges: List[Tuple[str, str]] = []
    for w1, w2 in zip(words, words[1:]):
        for c1, c2 in zip(w1, w2):
            if c1 != c2:
                edges.append((c1, c2))
                break
    order = build_order(sorted(chars), edges)
    if order is None:
        return ""
    return "".join(order)


def min_semesters(n: int, relations: Sequence[Tuple[int, int]]) -> Optional[int]:
    g = [[] for _ in range(n + 1)]
    indeg = [0] * (n + 1)
    indeg[0] = -1                                # node 0 unused
    for a, b in relations:
        g[a].append(b)
        indeg[b] += 1
    current = [c for c in range(1, n + 1) if indeg[c] == 0]
    done = 0
    semesters = 0
    while current:
        nxt: List[int] = []
        for u in current:
            done += 1
            for v in g[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    nxt.append(v)
        current = nxt
        semesters += 1
    return semesters if done == n else None
