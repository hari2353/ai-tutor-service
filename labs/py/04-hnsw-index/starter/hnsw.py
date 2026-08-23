"""Lab 04 -- a small HNSW (Hierarchical Navigable Small World) index, numpy only.
Fill in every TODO. Tests define done.

Layered graph + greedy search descent from the top layer down to a beam search
(width `ef`) at layer 0, with neighbour selection capped at `M` per node.
"""
from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field

import numpy as np


def brute_force_knn(vectors: dict[int, np.ndarray], query: np.ndarray, k: int) -> list[int]:
    """Exact k-NN by full scan. This is the ground truth recall is measured against.
    TODO(step 0): sort every (vec_id, vector) by distance to `query`, return the
    first k ids."""
    raise NotImplementedError


class HNSW:
    def __init__(self, dim: int, M: int = 16, ef_construction: int = 200, seed: int = 0) -> None:
        self.dim = dim
        self.M = M
        self.M_max0 = M * 2          # layer 0 gets a denser cap, standard HNSW practice
        self.ef_construction = ef_construction
        self.mL = 1.0 / math.log(M)
        self.rng = random.Random(seed)

        self.vectors: dict[int, np.ndarray] = {}
        self.levels: dict[int, int] = {}
        self.graph: list[dict[int, set[int]]] = []   # graph[layer][node_id] -> neighbour ids
        self.entry_point: int | None = None
        self.max_level = -1

    # ------------------------------------------------------------------ distance
    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b))

    def _random_level(self) -> int:
        """TODO(step 1): standard HNSW level sampling --
        int(-log(uniform_random()) * self.mL). Use self.rng, not the global
        random module -- that's what makes .rng seeded and builds reproducible."""
        raise NotImplementedError

    # ------------------------------------------------------------------ insert
    def insert(self, vec_id: int, vector: np.ndarray) -> None:
        """TODO(step 5): the full insert algorithm --
          1. sample a level for this node (_random_level); store the vector
          2. grow self.graph with empty layers up to `level` if needed, and
             give vec_id an empty neighbour set at every layer 0..level
          3. if this is the very first node inserted, it becomes the entry
             point and there's nothing else to connect -- return
          4. otherwise: starting from the current entry point, descend with
             _greedy_closest() through every layer ABOVE `level` (and above
             the graph's current max level) to find a good starting point
          5. from min(level, max_level) down to 0: run _search_layer to find
             candidates at that layer, pick neighbours with _select_neighbors
             (M_max0 at layer 0, M everywhere else), add bidirectional edges,
             and _prune() any neighbour whose degree cap got exceeded
          6. if `level` is a new max_level, this node becomes the new entry point
        """
        raise NotImplementedError

    def _greedy_closest(self, vector: np.ndarray, ep: int, layer: int) -> int:
        """Single-best greedy descent -- used on upper layers where a full
        beam search would be wasted work; the point is just to get close
        before the real (ef-width) search starts at the target layer.

        TODO(step 2): starting at `ep`, repeatedly move to whichever neighbour
        (at this layer) is closer to `vector` than the current node, until no
        neighbour improves on it. Return the final node."""
        raise NotImplementedError

    def _search_layer(self, vector: np.ndarray, ep: int, ef: int, layer: int) -> list[tuple[float, int]]:
        """Beam search of width `ef` on one layer. Returns up to `ef`
        (distance, id) pairs, best-first.

        TODO(step 3): classic HNSW search-layer --
          - maintain a min-heap of candidates to explore (closest-first) and a
            bounded max-heap of the best `ef` results found so far
          - pop the closest unexplored candidate; if it's farther than the
            current worst kept result AND you already have `ef` results, stop
          - otherwise expand its neighbours: any unvisited neighbour becomes a
            new candidate, and updates the results heap (evicting the worst
            entry if you're over `ef`)
          - return the results, sorted best-first
        """
        raise NotImplementedError

    def _select_neighbors(self, candidates: list[tuple[float, int]], M: int) -> list[int]:
        """Simple neighbour selection: the M closest candidates. (Real HNSW
        offers a diversity heuristic too; this is the simple, correct baseline.)
        TODO(step 4a)"""
        raise NotImplementedError

    def _prune(self, node: int, layer: int, M: int) -> None:
        """Cap `node`'s neighbour list at this layer down to its M closest.
        TODO(step 4b): rank node's current neighbours by distance to node,
        keep the closest M, and remove the reverse edge for everyone dropped
        -- EXCEPT: if a dropped neighbour would be left with zero remaining
        edges at this layer, keep the edge instead (staying connected matters
        more than a hard degree cap for one rare node)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ search
    def search(self, query: np.ndarray, k: int, ef_search: int | None = None) -> list[int]:
        """TODO(step 6): the public search entrypoint --
          - if the index is empty, return []
          - descend greedily from the entry point through every layer above 0
          - run _search_layer at layer 0 with width max(ef_search, k)
            (default ef_search to k if not given)
          - return the k closest ids
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ diagnostics
    def is_connected(self) -> bool:
        """Whether layer 0 (which contains every inserted node) is a single
        connected component. TODO(step 7): BFS/DFS from any one node over
        graph[0] and check every inserted id was reached."""
        raise NotImplementedError
