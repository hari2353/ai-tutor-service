"""Lab 09 — vector index internals: brute force, IVF (k-means-lite), toy PQ.

Everything is seeded and deterministic: same inputs + same seed → same index,
same ranking, same recall numbers. Cosine similarity throughout; vectors are
row-normalised once at build time so search is a dot product.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------- validation
def _as_matrix(obj, what: str = "vectors") -> np.ndarray:
    arr = np.asarray(obj, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(f"{what} must be 2-D (n, dim), got {arr.ndim}-D")
    if arr.shape[0] == 0:
        raise ValueError(f"{what} must contain at least one vector")
    return arr


def _as_query(q, dim: int) -> np.ndarray:
    arr = np.asarray(q, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"query must be a 1-D vector, got {arr.ndim}-D")
    if arr.size == 0:
        raise ValueError("query must not be empty")
    if arr.size != dim:
        raise ValueError(
            f"dimension mismatch: query has {arr.size} dims, "
            f"index was built with {dim}"
        )
    return arr


# ---------------------------------------------------------------- math core
def l2_normalize_rows(x: np.ndarray) -> np.ndarray:
    """Row-normalise; zero rows stay zero (their cosine with anything is 0)."""
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(norms == 0.0, 1.0, norms)


def kmeans_lite(x: np.ndarray, k: int, iters: int,
                rng: np.random.Generator) -> np.ndarray:
    """Few-iteration Lloyd k-means — the "coarse quantizer" workhorse.

    Init: k distinct sampled points from x. Each iteration assigns to the
    nearest centroid (L2) then recomputes means; empty clusters re-seed to a
    random point. Deterministic given the seeded rng.
    """
    n = x.shape[0]
    if not 1 <= k <= n:
        raise ValueError(f"k={k} out of range for {n} training points")
    if iters < 1:
        raise ValueError("iters must be >= 1")
    centroids = x[rng.choice(n, size=k, replace=False)].copy()
    x_sq = (x * x).sum(axis=1)[:, None]
    for _ in range(iters):
        d2 = x_sq - 2.0 * (x @ centroids.T) \
            + (centroids * centroids).sum(axis=1)[None, :]
        assign = d2.argmin(axis=1)
        for j in range(k):
            members = x[assign == j]
            centroids[j] = members.mean(axis=0) if len(members) else x[rng.integers(n)]
    return centroids


# ---------------------------------------------------------------- brute force
class BruteForce:
    """Exact top-k cosine over every stored vector. The recall baseline."""

    def __init__(self, vecs) -> None:
        arr = _as_matrix(vecs)
        self.dim = arr.shape[1]
        self.unit = l2_normalize_rows(arr)

    def search(self, q, k: int) -> list[tuple[int, float]]:
        """Return [(id, cosine), ...] best-first, ties broken by lower id."""
        if not isinstance(k, (int, np.integer)) or k < 1:
            raise ValueError("k must be an integer >= 1")
        qn = l2_normalize_rows(_as_query(q, self.dim))
        scores = self.unit @ qn
        order = np.argsort(-scores, kind="stable")[: min(k, self.unit.shape[0])]
        return [(int(i), float(scores[i])) for i in order]


# ---------------------------------------------------------------- IVF
class IVF:
    """Inverted-file index.

    Build: run k-means-lite into `nlist` coarse centroids, assign each vector
    to its nearest centroid's posting list.
    Search: score the query against all nlist centroids, open only the
    `nprobe` closest cells, rank the union of their postings by exact cosine.
    """

    def __init__(self, nlist: int, nprobe: int, iters: int = 8, seed: int = 0) -> None:
        if nlist < 1:
            raise ValueError("nlist must be >= 1")
        if not 1 <= nprobe <= nlist:
            raise ValueError(f"nprobe must satisfy 1 <= nprobe <= nlist={nlist}")
        if iters < 1:
            raise ValueError("iters must be >= 1")
        self.nlist = nlist
        self.nprobe = nprobe
        self.iters = iters
        self.seed = seed
        self.stats: dict[str, int] = {"probes_last": 0, "candidates_last": 0}

    def build(self, vecs) -> "IVF":
        arr = _as_matrix(vecs)
        if arr.shape[0] < self.nlist:
            raise ValueError(
                f"nlist={self.nlist} exceeds corpus size {arr.shape[0]}"
            )
        self.dim = arr.shape[1]
        self.unit = l2_normalize_rows(arr)
        rng = np.random.default_rng(self.seed)
        # cluster on unit sphere: nearest centroid under L2 ≡ highest cosine
        self.centroids = l2_normalize_rows(
            kmeans_lite(self.unit, self.nlist, self.iters, rng))
        cell_of = (self.unit @ self.centroids.T).argmax(axis=1)
        self.lists: list[np.ndarray] = [
            np.flatnonzero(cell_of == j).astype(np.int64) for j in range(self.nlist)]
        return self

    def search(self, q, k: int) -> list[tuple[int, float]]:
        """Top-k by cosine among candidates from the probed cells only."""
        if not hasattr(self, "unit"):
            raise RuntimeError("IVF.search() called before .build(vecs)")
        if not isinstance(k, (int, np.integer)) or k < 1:
            raise ValueError("k must be an integer >= 1")
        qn = l2_normalize_rows(_as_query(q, self.dim))
        cell_scores = self.centroids @ qn
        probed = np.argsort(-cell_scores, kind="stable")[: self.nprobe]
        cand = np.concatenate([self.lists[j] for j in probed])
        self.stats["probes_last"] = int(len(probed))
        self.stats["candidates_last"] = int(cand.size)
        if cand.size == 0:
            return []
        cand = np.sort(cand)                      # id order → stable tie-break
        scores = self.unit[cand] @ qn
        top = np.argsort(-scores, kind="stable")[: min(k, cand.size)]
        return [(int(cand[i]), float(scores[i])) for i in top]


# ---------------------------------------------------------------- toy PQ
@dataclass
class PQResult:
    codes: np.ndarray       # (n, m) codebook indices, one per subspace
    codebooks: np.ndarray   # (m, k_sub, sub_dim) trained per-subspace centroids
    distortion: float       # mean squared reconstruction error per vector

    def reconstruct(self) -> np.ndarray:
        """Lossy approximation of the originals: centroid lookup per subspace."""
        n, m = self.codes.shape
        sub = self.codebooks.shape[2]
        out = np.empty((n, m * sub), dtype=np.float64)
        for j in range(m):
            out[:, j * sub:(j + 1) * sub] = self.codebooks[j][self.codes[:, j]]
        return out


def pq_quantize(vecs, m: int, k_sub: int = 16, iters: int = 8,
                seed: int = 0) -> PQResult:
    """Toy product quantiser: split dims into m equal subspaces, k-means-lite
    each against k_sub centroids, store only the winning codebook index.

    Distortion (mean squared reconstruction error) is what PQ buys its ~30x
    memory compression with — measure it, never assume it away.
    """
    arr = _as_matrix(vecs)
    n, d = arr.shape
    if m < 1:
        raise ValueError("m must be >= 1")
    if d % m != 0:
        raise ValueError(f"dim {d} does not divide evenly into m={m} subspaces")
    if not 1 <= k_sub <= n:
        raise ValueError(f"k_sub={k_sub} out of range for {n} vectors")
    sub = d // m
    codes = np.zeros((n, m), dtype=np.int64)
    codebooks = np.zeros((m, k_sub, sub), dtype=np.float64)
    recon = np.empty_like(arr)
    for j in range(m):
        sub_x = arr[:, j * sub:(j + 1) * sub]
        book = kmeans_lite(sub_x, k_sub, iters, np.random.default_rng([seed, j]))
        d2 = (sub_x * sub_x).sum(1)[:, None] - 2.0 * (sub_x @ book.T) \
            + (book * book).sum(1)[None, :]
        assign = d2.argmin(axis=1)
        codes[:, j] = assign
        codebooks[j] = book
        recon[:, j * sub:(j + 1) * sub] = book[assign]
    sq_err = ((arr - recon) ** 2).sum(axis=1)
    return PQResult(codes=codes, codebooks=codebooks, distortion=float(sq_err.mean()))


# ---------------------------------------------------------------- harness
def make_clusters(n_clusters: int, per_cluster: int, dim: int, seed: int,
                  spread: float = 0.35) -> np.ndarray:
    """Synthetic corpus: Gaussian blobs around uniform(-1,1) centres, shuffled."""
    rng = np.random.default_rng(seed)
    centers = rng.uniform(-1.0, 1.0, size=(n_clusters, dim))
    noise = rng.normal(0.0, spread, size=(n_clusters * per_cluster, dim))
    pts = np.repeat(centers, per_cluster, axis=0) + noise
    rng.shuffle(pts)
    return pts


def recall_at_k(true_ids, approx_ids) -> float:
    """|exact ∩ approx| / |exact| — ground truth comes from exact search."""
    truth = set(true_ids)
    if not truth:
        raise ValueError("ground-truth id list must not be empty")
    return len(truth & set(approx_ids)) / len(truth)


def recall_harness(vecs, queries, k: int = 10, nlist: int = 16,
                   nprobes=(1, 2, 4, 8, 16), iters: int = 8,
                   seed: int = 0) -> dict[int, float]:
    """Mean IVF-vs-brute-force recall@k for each nprobe setting."""
    exact = BruteForce(vecs)
    truths = [[i for i, _ in exact.search(q, k)] for q in queries]
    out: dict[int, float] = {}
    for nprobe in nprobes:
        index = IVF(nlist, nprobe, iters=iters, seed=seed).build(vecs)
        recalls = [recall_at_k(t, [i for i, _ in index.search(q, k)])
                   for t, q in zip(truths, queries)]
        out[nprobe] = sum(recalls) / len(recalls)
    return out
