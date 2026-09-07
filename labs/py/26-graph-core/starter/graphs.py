"""Lab 26 — graph representations & traversal invariants. Fill in every TODO.

Rules:
  * Pure functions only — never mutate the input graph/edges/matrix.
  * "graph" = adjacency list list[list[int]] in INSERTION order.
  * Handle disconnected graphs and self-loops everywhere.
  * dfs_order uses an explicit stack, NO recursion.
"""
from __future__ import annotations

from collections import deque
from typing import Optional


# ------------------------------------------------------------------ representations
def to_adjacency_list(n: int, edges: list, directed: bool = False) -> list[list[int]]:
    """n buckets, 0-indexed. Undirected default: each edge in both buckets.
    A self-loop (u, u) appears TWICE in its own bucket."""
    raise NotImplementedError


def to_adjacency_matrix(n: int, edges: list, directed: bool = False) -> list[list[int]]:
    """n x n; cell = weight w from (u, v, w), or 1 from (u, v) — not always 1."""
    raise NotImplementedError


def to_edge_list(matrix: list[list[int]], directed: bool = False,
                 weighted: bool = False) -> list:
    """Skip zero cells. Undirected: upper triangle INCLUDING the diagonal,
    row-major. Directed: every cell. weighted=True -> (i, j, w) triples."""
    raise NotImplementedError


# ------------------------------------------------------------------ traversals
def bfs_order(graph: list[list[int]], src: int) -> list[int]:
    """FIFO; mark on ENQUEUE; expand neighbors in insertion order."""
    raise NotImplementedError


def dfs_order(graph: list[list[int]], src: int) -> list[int]:
    """Explicit stack, no recursion; mark on POP (skip re-popped nodes);
    push neighbors in REVERSE insertion order so the visit order equals
    recursive preorder."""
    raise NotImplementedError


# ------------------------------------------------------------------ structure
def connected_components(graph: list[list[int]]) -> list[list[int]]:
    """Every component sorted ascending; the list of components sorted too."""
    raise NotImplementedError


def has_cycle_undirected(graph: list[list[int]]) -> bool:
    """DFS with parent tracking. Visited neighbor != parent -> cycle.
    Self-loops and parallel edges are cycles."""
    raise NotImplementedError


def has_cycle_directed(graph: list[list[int]]) -> bool:
    """Three-color DFS (white/gray/black). Edge to GRAY = cycle.
    Edge to BLACK (e.g. a diamond DAG convergence) is fine."""
    raise NotImplementedError


def is_bipartite(graph: list[list[int]]) -> tuple[bool, Optional[dict]]:
    """BFS 2-coloring with the outer loop over components.
    Returns (True, {node: 0/1}) — first vertex of each component is 0 —
    or (False, None) on a color conflict (odd cycle)."""
    raise NotImplementedError


def degree_sum(graph: list[list[int]]) -> int:
    """Sum of bucket lengths (a self-loop counts 2)."""
    raise NotImplementedError
