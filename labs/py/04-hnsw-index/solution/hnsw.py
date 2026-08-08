"""Lab 04 -- a small HNSW (Hierarchical Navigable Small World) index, numpy only.

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
    """Exact k-NN by full scan. This is the ground truth recall is measured against."""
    dists = [(float(np.linalg.norm(query - v)), vid) for vid, v in vectors.items()]
    dists.sort(key=lambda x: x[0])
    return [vid for _, vid in dists[:k]]


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
        return int(-math.log(self.rng.random()) * self.mL)

    # ------------------------------------------------------------------ insert
    def insert(self, vec_id: int, vector: np.ndarray) -> None:
        vector = np.asarray(vector, dtype=np.float64)
        level = self._random_level()
        self.vectors[vec_id] = vector
        self.levels[vec_id] = level

        while len(self.graph) <= level:
            self.graph.append({})
        for l in range(level + 1):
            self.graph[l][vec_id] = set()

        if self.entry_point is None:
            self.entry_point = vec_id
            self.max_level = level
            return

        ep = self.entry_point
        for l in range(self.max_level, level, -1):
            ep = self._greedy_closest(vector, ep, l)

        for l in range(min(level, self.max_level), -1, -1):
            candidates = self._search_layer(vector, ep, self.ef_construction, l)
            M_l = self.M_max0 if l == 0 else self.M
            neighbors = self._select_neighbors(candidates, M_l)
            for n in neighbors:
                self.graph[l][vec_id].add(n)
                self.graph[l][n].add(vec_id)
                if len(self.graph[l][n]) > M_l:
                    self._prune(n, l, M_l)
            if neighbors:
                ep = neighbors[0]

        if level > self.max_level:
            self.max_level = level
            self.entry_point = vec_id

    def _greedy_closest(self, vector: np.ndarray, ep: int, layer: int) -> int:
        """Single-best greedy descent -- used on upper layers where a full
        beam search would be wasted work; the point is just to get close
        before the real (ef-width) search starts at the target layer."""
        current = ep
        current_dist = self._distance(vector, self.vectors[current])
        improved = True
        while improved:
            improved = False
            for neighbor in self.graph[layer].get(current, ()):
                d = self._distance(vector, self.vectors[neighbor])
                if d < current_dist:
                    current_dist = d
                    current = neighbor
                    improved = True
        return current

    def _search_layer(self, vector: np.ndarray, ep: int, ef: int, layer: int) -> list[tuple[float, int]]:
        """Beam search of width `ef` on one layer. Returns up to `ef`
        (distance, id) pairs, best-first."""
        visited = {ep}
        d0 = self._distance(vector, self.vectors[ep])
        candidates = [(d0, ep)]          # min-heap: explore closest-first
        heapq.heapify(candidates)
        results = [(-d0, ep)]            # max-heap (negated): worst-of-the-best at top
        heapq.heapify(results)

        while candidates:
            d, c = heapq.heappop(candidates)
            worst_kept = -results[0][0]
            if d > worst_kept and len(results) >= ef:
                break
            for neighbor in self.graph[layer].get(c, ()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                dn = self._distance(vector, self.vectors[neighbor])
                worst_kept = -results[0][0]
                if len(results) < ef or dn < worst_kept:
                    heapq.heappush(candidates, (dn, neighbor))
                    heapq.heappush(results, (-dn, neighbor))
                    if len(results) > ef:
                        heapq.heappop(results)
        return sorted(((-d, n) for d, n in results), key=lambda x: x[0])

    def _select_neighbors(self, candidates: list[tuple[float, int]], M: int) -> list[int]:
        """Simple neighbour selection: the M closest candidates. (Real HNSW
        offers a diversity heuristic too; this is the simple, correct baseline.)"""
        return [n for _, n in sorted(candidates, key=lambda x: x[0])[:M]]

    def _prune(self, node: int, layer: int, M: int) -> None:
        node_vec = self.vectors[node]
        neighbors = self.graph[layer][node]
        ranked = sorted(((self._distance(node_vec, self.vectors[n]), n) for n in neighbors),
                         key=lambda x: x[0])
        keep = {n for _, n in ranked[:M]}
        dropped = [n for _, n in ranked[M:]]
        for n in dropped:
            if len(self.graph[layer][n]) <= 1:
                # n has no other connection at this layer -- dropping this
                # edge would strand it as an isolated node. Keep it (a small,
                # rare overshoot of M) rather than fragment the graph: staying
                # connected matters more than a hard cap on one node's degree.
                keep.add(n)
                continue
            self.graph[layer][n].discard(node)
        self.graph[layer][node] = keep

    # ------------------------------------------------------------------ search
    def search(self, query: np.ndarray, k: int, ef_search: int | None = None) -> list[int]:
        if self.entry_point is None:
            return []
        query = np.asarray(query, dtype=np.float64)
        ef_search = max(k, 1) if ef_search is None else max(ef_search, k)

        ep = self.entry_point
        for l in range(self.max_level, 0, -1):
            ep = self._greedy_closest(query, ep, l)

        results = self._search_layer(query, ep, ef_search, 0)
        return [nid for _, nid in results[:k]]

    # ------------------------------------------------------------------ diagnostics
    def is_connected(self) -> bool:
        """Whether layer 0 (which contains every inserted node) is a single
        connected component."""
        if not self.vectors:
            return True
        nodes = set(self.vectors)
        start = next(iter(nodes))
        seen = {start}
        stack = [start]
        layer0 = self.graph[0]
        while stack:
            n = stack.pop()
            for neighbor in layer0.get(n, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        return seen == nodes
