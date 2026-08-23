"""Lab 04 tests. numpy only, fixed seeds throughout -- fully deterministic."""
import numpy as np
import pytest

N, DIM, M, EF_CONSTRUCTION, SEED = 250, 10, 8, 100, 7
K = 10


def _dataset(seed=SEED, n=N, dim=DIM):
    rng = np.random.RandomState(seed)
    data = {i: rng.randn(dim) for i in range(n)}
    return data, rng


def _build_index(H, data, seed=SEED, M=M, ef_construction=EF_CONSTRUCTION):
    idx = H.HNSW(dim=DIM, M=M, ef_construction=ef_construction, seed=seed)
    for i, v in data.items():
        idx.insert(i, v)
    return idx


@pytest.fixture
def dataset():
    return _dataset()


@pytest.fixture
def index(H, dataset):
    data, _ = dataset
    return _build_index(H, data)


# ------------------------------------------------------------------ brute force baseline
def test_brute_force_returns_k_nearest_by_distance(H):
    data = {0: np.array([0.0, 0.0]), 1: np.array([1.0, 0.0]),
            2: np.array([5.0, 5.0]), 3: np.array([0.1, 0.1])}
    result = H.brute_force_knn(data, np.array([0.0, 0.0]), k=2)
    assert result == [0, 3]


# ------------------------------------------------------------------ recall vs exact search
def test_recall_against_brute_force_is_high(H, dataset, index):
    data, rng = dataset
    queries = [rng.randn(DIM) for _ in range(20)]
    recalls = []
    for q in queries:
        exact = set(H.brute_force_knn(data, q, K))
        approx = set(index.search(q, K, ef_search=80))
        recalls.append(len(exact & approx) / K)
    assert float(np.mean(recalls)) >= 0.9, "recall too low at generous ef_search"


def test_ef_search_monotonically_improves_recall(H, dataset, index):
    data, rng = dataset
    queries = [rng.randn(DIM) for _ in range(20)]

    def recall_at(ef):
        hits = 0
        for q in queries:
            exact = set(H.brute_force_knn(data, q, K))
            approx = set(index.search(q, K, ef_search=ef))
            hits += len(exact & approx)
        return hits / (K * len(queries))

    ef_values = [1, 5, 10, 30, 80]
    recalls = [recall_at(ef) for ef in ef_values]

    for a, b in zip(recalls, recalls[1:]):
        assert b >= a - 1e-9, f"recall regressed when raising ef_search: {recalls}"
    assert recalls[-1] > recalls[0], "raising ef_search never improved recall at all"


# ------------------------------------------------------------------ connectivity
def test_graph_stays_connected(index):
    assert index.is_connected()


def test_graph_stays_connected_across_seeds(H):
    for seed in [0, 1, 2, 3, 4]:
        data, _ = _dataset(seed=seed, n=150, dim=8)
        idx = _build_index(H, data, seed=seed, M=8, ef_construction=80)
        assert idx.is_connected(), f"disconnected at seed={seed}"


# ------------------------------------------------------------------ neighbour selection with M
def test_layer0_degree_never_exceeds_M_max0(index):
    for node, neighbors in index.graph[0].items():
        assert len(neighbors) <= index.M_max0


def test_upper_layer_degree_never_exceeds_M(index):
    for layer in range(1, len(index.graph)):
        for node, neighbors in index.graph[layer].items():
            assert len(neighbors) <= index.M


def test_every_node_present_in_layer0(H, dataset, index):
    data, _ = dataset
    assert set(index.graph[0].keys()) == set(data.keys())


# ------------------------------------------------------------------ search correctness
def test_search_returns_k_results(index):
    q = np.random.RandomState(99).randn(DIM)
    assert len(index.search(q, k=5, ef_search=50)) == 5


def test_search_clips_k_to_dataset_size(H, dataset):
    data, _ = dataset
    small = {i: data[i] for i in list(data)[:5]}
    idx = _build_index(H, small)
    result = idx.search(np.random.RandomState(1).randn(DIM), k=50, ef_search=50)
    assert len(result) == 5


def test_exact_self_match_has_zero_distance(H, dataset, index):
    data, _ = dataset
    qid = 42
    q = data[qid]
    result = index.search(q, k=1, ef_search=50)
    assert result[0] == qid


def test_search_on_empty_index_returns_empty(H):
    idx = H.HNSW(dim=4, M=4, ef_construction=20, seed=0)
    assert idx.search(np.zeros(4), k=5) == []


# ------------------------------------------------------------------ determinism
def test_build_is_deterministic_with_same_seed(H, dataset):
    data, _ = dataset
    idx1 = _build_index(H, data, seed=11)
    idx2 = _build_index(H, data, seed=11)
    assert idx1.graph[0] == idx2.graph[0]
    assert idx1.entry_point == idx2.entry_point
    assert idx1.max_level == idx2.max_level
