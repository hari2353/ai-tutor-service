"""Lab 09 — vector index internals. Fill in every TODO. Tests define done.

Rules:
  * Everything seeded: same inputs + seed → same centroids, codes, recalls.
  * Cosine similarity throughout — normalise rows once, score with dot products.
  * Guards everywhere: bad dims / empty queries / invalid params raise ValueError.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------- validation
def _as_matrix(obj, what: str = "vectors") -> np.ndarray:
    """Coerce to float64 2-D; reject non-matrices and empty corpora."""
    # TODO(step 0a): np.asarray(...); ValueError unless ndim == 2 and shape[0] > 0
    raise NotImplementedError


def _as_query(q, dim: int) -> np.ndarray:
    """Coerce to float64 1-D; reject non-vectors, EMPTY queries, wrong dim."""
    # TODO(step 0b): ValueError unless ndim == 1, size > 0, size == dim
    raise NotImplementedError


# ---------------------------------------------------------------- math core
def l2_normalize_rows(x: np.ndarray) -> np.ndarray:
    """Row-normalise; zero rows stay zero (their cosine with anything is 0)."""
    # TODO(step 1): divide by norms, substituting 1 where norm == 0
    raise NotImplementedError


def kmeans_lite(x: np.ndarray, k: int, iters: int,
                rng: np.random.Generator) -> np.ndarray:
    """Few-iteration Lloyd k-means. Init: k distinct sampled points.

    Each iter: assign to nearest centroid (L2), recompute means; an empty
    cluster re-seeds to a random point. Deterministic given the seeded rng.
    """
    # TODO(step 2): validate 1 <= k <= n and iters >= 1, then loop iters times
    raise NotImplementedError


# ---------------------------------------------------------------- brute force
class BruteForce:
    """Exact top-k cosine over every stored vector. The recall baseline."""

    def __init__(self, vecs) -> None:
        # TODO(step 3a): _as_matrix, store dim, store row-normalised copy
        raise NotImplementedError

    def search(self, q, k: int) -> list[tuple[int, float]]:
        """Return [(id, cosine), ...] best-first, ties broken by lower id."""
        # TODO(step 3b): validate k, normalise query, scores = unit @ qn,
        #                stable argsort of -scores, top min(k, N)
        raise NotImplementedError


# ---------------------------------------------------------------- IVF
class IVF:
    """Inverted-file index: nlist coarse centroids, probe nprobe closest cells.

    Build: k-means-lite on the unit-normalised corpus (nearest centroid under
    L2 ≡ highest cosine), assign vectors to posting lists.
    Search: query→centroid scores, open nprobe cells, rank their union by
    exact cosine. Track probes/candidates in self.stats.
    """

    def __init__(self, nlist: int, nprobe: int, iters: int = 8, seed: int = 0) -> None:
        # TODO(step 4a): validate nlist >= 1, 1 <= nprobe <= nlist, iters >= 1
        raise NotImplementedError

    def build(self, vecs) -> "IVF":
        # TODO(step 4b): _as_matrix (nlist <= n!), kmeans_lite(seed-derived rng),
        #                argmax assignment, one posting list per cell; return self
        raise NotImplementedError

    def search(self, q, k: int) -> list[tuple[int, float]]:
        # TODO(step 4c): RuntimeError if unbuilt; validate k; probe nprobe best
        #                cells, concat lists (sorted by id → stable tie-break),
        #                rank by cosine, record stats, return top-k
        raise NotImplementedError


# ---------------------------------------------------------------- toy PQ
@dataclass
class PQResult:
    codes: np.ndarray       # (n, m) codebook indices, one per subspace
    codebooks: np.ndarray   # (m, k_sub, sub_dim) trained per-subspace centroids
    distortion: float       # mean squared reconstruction error per vector

    def reconstruct(self) -> np.ndarray:
        """Lossy approximation: centroid lookup per subspace."""
        # TODO(step 5d)
        raise NotImplementedError


def pq_quantize(vecs, m: int, k_sub: int = 16, iters: int = 8,
                seed: int = 0) -> PQResult:
    """Toy product quantiser: split dims into m equal subspaces, k-means-lite
    each against k_sub centroids, keep only the winning codebook index.
    """
    # TODO(step 5a): _as_matrix; ValueError if m < 1 or dim % m != 0 or k_sub out of range
    # TODO(step 5b): per subspace j: kmeans_lite(sub_x, k_sub, iters,
    #                np.random.default_rng([seed, j])), nearest-centroid codes
    # TODO(step 5c): recon from codes; distortion = mean ||v - recon||^2
    raise NotImplementedError


# ---------------------------------------------------------------- harness
def make_clusters(n_clusters: int, per_cluster: int, dim: int, seed: int,
                  spread: float = 0.35) -> np.ndarray:
    """Synthetic corpus: Gaussian blobs around uniform(-1,1) centres, shuffled."""
    # TODO(step 6a): seeded rng; uniform centres, normal noise, repeat+add, shuffle
    raise NotImplementedError


def recall_at_k(true_ids, approx_ids) -> float:
    """|exact ∩ approx| / |exact| — ground truth comes from exact search."""
    # TODO(step 6b): ValueError on empty truth (as a set); intersection over
    #                len(set(truth))
    raise NotImplementedError


def recall_harness(vecs, queries, k: int = 10, nlist: int = 16,
                   nprobes=(1, 2, 4, 8, 16), iters: int = 8,
                   seed: int = 0) -> dict[int, float]:
    """Mean IVF-vs-brute-force recall@k for each nprobe setting."""
    # TODO(step 6c): brute-force truths once, then mean recall_at_k per nprobe
    raise NotImplementedError
