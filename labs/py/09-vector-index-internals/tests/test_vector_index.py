"""Lab 09 tests. Everything is seeded and deterministic — no flakes.

Recall numbers are printed so both pytest modes show measured evidence.
"""
import sys

import numpy as np
import pytest

N_CLUSTERS, PER_CLUSTER, DIM = 5, 100, 32          # 500 vectors, dim 32


def _V():
    return sys.modules["vector_index"]             # registered by conftest


@pytest.fixture(scope="module")
def corpus():
    return _V().make_clusters(N_CLUSTERS, PER_CLUSTER, DIM, seed=7)


@pytest.fixture(scope="module")
def queries():
    return _V().make_clusters(N_CLUSTERS, PER_CLUSTER, DIM, seed=101)[:50]


# ------------------------------------------------------------------ brute force
def test_bruteforce_topk_matches_naive_recompute(V, corpus, queries):
    unit = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    bf = V.BruteForce(corpus)
    for q in queries[:5]:
        qn = q / np.linalg.norm(q)
        scores = unit @ qn
        expect = np.argsort(-scores, kind="stable")[:10]
        got = bf.search(q, 10)
        assert [i for i, _ in got] == [int(i) for i in expect]
        assert np.allclose([s for _, s in got], scores[expect])


def test_bruteforce_scores_are_true_cosines(V):
    bf = V.BruteForce([[1.0, 0.0], [0.0, 1.0], [-2.0, 0.0]])
    got = bf.search([3.0, 0.0], 3)
    assert [i for i, _ in got] == [0, 1, 2]
    assert got[0][1] == pytest.approx(1.0)      # parallel
    assert got[1][1] == pytest.approx(0.0)      # orthogonal
    assert got[2][1] == pytest.approx(-1.0)     # anti-parallel


def test_bruteforce_returns_at_most_n_results(V, corpus):
    got = V.BruteForce(corpus).search(corpus[0], 10_000)
    assert len(got) == len(corpus)


def test_bruteforce_rejects_empty_corpus_and_bad_k(V):
    with pytest.raises(ValueError):
        V.BruteForce(np.empty((0, 4)))
    bf = V.BruteForce([[1.0, 0.0], [0.0, 1.0]])
    with pytest.raises(ValueError):
        bf.search([1.0, 0.0], 0)


def test_bruteforce_dimension_mismatch_raises(V, corpus):
    bf = V.BruteForce(corpus)
    with pytest.raises(ValueError):
        bf.search(np.ones(DIM + 5), 3)
    with pytest.raises(ValueError):              # non-1-D "query"
        bf.search(np.ones((2, DIM)), 3)


# ------------------------------------------------------------------ IVF quality
def test_ivf_recall10_clustered_nprobe4_at_least_08(V, corpus, queries):
    recalls = V.recall_harness(corpus, queries, k=10, nlist=16,
                               nprobes=(4,), seed=0)
    r4 = recalls[4]
    print(f"\n[recall] IVF vs brute force, 500x32 clustered, nlist=16: "
          f"recall@10 @nprobe=4 = {r4:.3f}")
    assert r4 >= 0.8


def test_ivf_monotonic_nprobe1_lower_than_nprobe8(V, corpus, queries):
    recalls = V.recall_harness(corpus, queries, k=10, nlist=16,
                               nprobes=(1, 8), seed=0)
    print(f"\n[recall] recall@10 @nprobe=1 = {recalls[1]:.3f}  "
          f"@nprobe=8 = {recalls[8]:.3f}")
    assert recalls[1] < recalls[8]


def test_ivf_full_probe_is_exactly_brute_force(V, corpus, queries):
    exact = V.BruteForce(corpus)
    ivf = V.IVF(16, 16, iters=8, seed=0).build(corpus)
    for q in queries[:20]:
        assert [i for i, _ in ivf.search(q, 10)] == \
               [i for i, _ in exact.search(q, 10)]


# ------------------------------------------------------------------ IVF mechanics
def test_ivf_probes_only_nprobe_cells(V, corpus):
    ivf = V.IVF(16, 3, iters=8, seed=0).build(corpus)
    for row in corpus[:5]:
        ivf.search(row, 5)
    assert ivf.stats["probes_last"] == 3
    assert 0 < ivf.stats["candidates_last"] < len(corpus)   # real pruning happened
    print(f"\n[ivf] probed 3/16 cells -> scored only "
          f"{ivf.stats['candidates_last']}/{len(corpus)} candidates")


def test_ivf_results_ranked_by_cosine(V, corpus, queries):
    unit = corpus / np.linalg.norm(corpus, axis=1, keepdims=True)
    ivf = V.IVF(16, 4, iters=8, seed=0).build(corpus)
    got = ivf.search(queries[0], 10)
    scores = [s for _, s in got]
    assert scores == sorted(scores, reverse=True)
    for idx, s in got:
        v = unit[idx]
        qn = queries[0] / np.linalg.norm(queries[0])
        assert s == pytest.approx(float(v @ qn))


def test_ivf_invalid_params_raise(V, corpus):
    with pytest.raises(ValueError):
        V.IVF(16, 0)
    with pytest.raises(ValueError):
        V.IVF(16, 17)                       # nprobe > nlist
    with pytest.raises(ValueError):
        V.IVF(0, 1)
    with pytest.raises(ValueError):
        V.IVF(501, 4).build(corpus)         # more cells than vectors
    with pytest.raises(RuntimeError):
        V.IVF(16, 4).search(np.ones(DIM), 3)  # search before build


def test_ivf_dimension_mismatch_raises(V, corpus):
    ivf = V.IVF(16, 4, iters=8, seed=0).build(corpus)
    with pytest.raises(ValueError):
        ivf.search(np.ones(DIM - 1), 3)
    with pytest.raises(ValueError):
        ivf.search([], 3)


# ------------------------------------------------------------------ determinism
def test_determinism_under_fixed_seed(V, corpus, queries):
    a = V.IVF(16, 4, iters=8, seed=42).build(corpus)
    b = V.IVF(16, 4, iters=8, seed=42).build(corpus)
    assert np.array_equal(a.centroids, b.centroids)
    for q in queries[:10]:
        assert a.search(q, 10) == b.search(q, 10)

    h1 = V.recall_harness(corpus, queries, nprobes=(4,), seed=7)
    h2 = V.recall_harness(corpus, queries, nprobes=(4,), seed=7)
    assert h1 == h2


def test_make_clusters_shape_and_seeded(V):
    c1 = V.make_clusters(N_CLUSTERS, PER_CLUSTER, DIM, seed=7)
    c2 = V.make_clusters(N_CLUSTERS, PER_CLUSTER, DIM, seed=7)
    c3 = V.make_clusters(N_CLUSTERS, PER_CLUSTER, DIM, seed=8)
    assert c1.shape == (N_CLUSTERS * PER_CLUSTER, DIM)
    assert np.array_equal(c1, c2)
    assert not np.array_equal(c1, c3)


def test_recall_metric_semantics(V):
    assert V.recall_at_k([1, 2, 3, 4], [2, 3, 9]) == pytest.approx(0.5)
    assert V.recall_at_k([1, 1], [1]) == pytest.approx(1.0)   # sets, not lists
    assert V.recall_at_k([1, 2], []) == 0.0
    with pytest.raises(ValueError):
        V.recall_at_k([], [1])


# ------------------------------------------------------------------ toy PQ
def test_pq_distortion_decreases_with_more_iterations(V, corpus):
    d1 = V.pq_quantize(corpus, m=8, k_sub=16, iters=1, seed=0).distortion
    d12 = V.pq_quantize(corpus, m=8, k_sub=16, iters=12, seed=0).distortion
    print(f"\n[pq] distortion iters=1: {d1:.5f}  iters=12: {d12:.5f}")
    assert d12 < d1
    assert d12 > 0.0                              # lossy by construction


def test_pq_structures_reconstruct_and_distortion_agree(V, corpus):
    res = V.pq_quantize(corpus, m=8, k_sub=16, iters=8, seed=0)
    assert res.codes.shape == (len(corpus), 8)
    assert res.codebooks.shape == (8, 16, DIM // 8)
    recon = res.reconstruct()
    manual = ((corpus - recon) ** 2).sum(axis=1).mean()
    assert res.distortion == pytest.approx(manual)
    for j in range(8):                            # codes point at valid centroids
        assert res.codes[:, j].min() >= 0 and res.codes[:, j].max() < 16


def test_pq_recall_drop_vs_exact_measured(V, corpus, queries):
    res = V.pq_quantize(corpus, m=8, k_sub=64, iters=10, seed=0)
    exact = V.BruteForce(corpus)
    lossy = V.BruteForce(res.reconstruct())
    rs = [V.recall_at_k([i for i, _ in exact.search(q, 10)],
                        [i for i, _ in lossy.search(q, 10)]) for q in queries]
    r = sum(rs) / len(rs)
    print(f"\n[pq] recall@10 exact=1.000  after-PQ={r:.3f}  "
          f"drop={1 - r:.3f}  distortion={res.distortion:.5f}")
    assert 0.3 <= r < 1.0                         # measurable drop, not collapse


def test_pq_dim_not_divisible_raises(V, corpus):
    with pytest.raises(ValueError):
        V.pq_quantize(corpus, m=5)                # 32 % 5 != 0
    with pytest.raises(ValueError):
        V.pq_quantize(corpus, m=0)
    with pytest.raises(ValueError):
        V.pq_quantize(corpus, m=64)               # more subspaces than dims


def test_pq_empty_corpus_raises(V):
    with pytest.raises(ValueError):
        V.pq_quantize(np.empty((0, 8)), m=2)


# ------------------------------------------------------------------ guards
def test_empty_query_guards(V, corpus):
    bf = V.BruteForce(corpus)
    ivf = V.IVF(16, 4, iters=8, seed=0).build(corpus)
    for bad in ([], np.array([])):
        with pytest.raises(ValueError):
            bf.search(bad, 3)
        with pytest.raises(ValueError):
            ivf.search(bad, 3)
