"""Lab 28 starter — MST, max-flow, min-cut, bipartite matching.

Pure stdlib. Implement every function; the tests run against this file
by default (pass --solution to check the reference).
"""
import heapq
from collections import deque


class UnionFind:
    """Disjoint-set with path compression + union by rank.

    find/union are near O(1) amortized (inverse Ackermann).
    """

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        """Return the root of x's set; compress the path on the way up."""
        raise NotImplementedError

    def union(self, a, b):
        """Merge a's and b's sets. Return True if merged, False if already same."""
        raise NotImplementedError

    def connected(self, a, b):
        """True if a and b are in the same set."""
        raise NotImplementedError


def kruskal_mst(n, edges):
    """Minimum spanning FOREST via global sort + Union-Find cycle check.

    edges: list of (w, u, v). Returns (mst_edges, total_weight) where
    mst_edges is the list of (w, u, v) kept, in sorted order. A
    disconnected graph yields the spanning forest of all components.
    """
    raise NotImplementedError


def prim_mst(n, edges, start=0):
    """MST of start's component, grown one cheapest crossing edge at a time.

    edges: list of (w, u, v), undirected. Heap-based. Returns
    (mst_edges, total_weight) covering ONLY the component containing
    `start` (unreachable vertices contribute nothing).
    """
    raise NotImplementedError


def edmonds_karp(n, capacity, s, t):
    """Max flow via BFS-found shortest augmenting paths (Edmonds-Karp).

    capacity: n x n matrix (NOT mutated). Returns (max_flow_value, flows)
    where flows[u][v] is the net flow u->v (negative on reverse edges).
    """
    raise NotImplementedError


def min_cut(n, capacity, s, t):
    """Minimum s-t cut via max-flow. Returns (cut_value, source_side) where
    source_side is the set of vertices reachable from s in the FINAL
    residual graph. cut_value == max_flow (max-flow min-cut theorem).
    """
    raise NotImplementedError


def bipartite_matching(n_left, n_right, edges):
    """Maximum bipartite matching size, via reduction to max-flow.

    edges: list of (left, right) pairs. Build source -> left (cap 1),
    left -> right (cap 1), right -> sink (cap 1), then run edmonds_karp.
    """
    raise NotImplementedError
