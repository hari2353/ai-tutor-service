"""Lab 19 — union-find. Fill in every TODO. Tests define done.

Rules:
  * find: path compression (every visited node points at the root).
  * union: by rank — never hang the taller tree under the shorter one.
  * All amortized-almost-O(1) per op (inverse-Ackermann).
  * Pure stdlib. No network. No sleeps.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple


class UnionFind:
    """Disjoint sets over 0..n-1 with path compression + union by rank."""

    def __init__(self, n: int) -> None:
        raise NotImplementedError

    def find(self, x: int) -> int:
        """Root of x's set, compressing the path along the way."""
        raise NotImplementedError

    def union(self, x: int, y: int) -> bool:
        """Merge sets if separate. True if a merge happened, False if already connected."""
        raise NotImplementedError

    def connected(self, x: int, y: int) -> bool:
        raise NotImplementedError

    @property
    def count(self) -> int:
        """Number of disjoint sets."""
        raise NotImplementedError

    def size(self, x: int) -> int:
        """Number of elements in x's set."""
        raise NotImplementedError


def connected_components(n: int, edges: Sequence[Sequence[int]]) -> int:
    """Number of connected components on nodes 0..n-1."""
    raise NotImplementedError


def redundant_connection(edges: Sequence[Sequence[int]]) -> Sequence[int]:
    """One extra edge creates a cycle; return the last input edge whose
    removal leaves a tree (1-indexed nodes)."""
    raise NotImplementedError


def accounts_merge(accounts: Sequence[Sequence[str]]) -> List[List[str]]:
    """Merge accounts sharing any email. Output: [name, sorted emails...],
    groups ordered by (name, first email)."""
    raise NotImplementedError


def number_of_islands_ii(m: int, n: int,
                         positions: Sequence[Sequence[int]]) -> List[int]:
    """Flip cells to land one at a time; return the island count after each flip."""
    raise NotImplementedError


def kruskal_mst(n: int,
                edges: Sequence[Tuple[int, int, int]]) -> Tuple[int, List[Tuple[int, int, int]]]:
    """edges are (weight, a, b). Return (total_weight, accepted_edges) of the
    minimum spanning forest (all n-1 edges if connected)."""
    raise NotImplementedError


def minimum_spanning_cost(n: int, edges: Sequence[Tuple[int, int, int]]) -> int:
    """Total weight of the minimum spanning forest covering all nodes."""
    raise NotImplementedError
