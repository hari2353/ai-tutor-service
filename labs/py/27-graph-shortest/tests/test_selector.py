"""Lab 27 tests. No sleeps; wall-clock numbers get huge margins (or are
replaced by op-count assertions) so nothing flakes on a slow machine.

Hand-verified fixtures (worked out on paper before baking -- don't trust,
verify):

    GRAPH (all weights positive, DIRECTED):
        edges: A->B 4, A->C 1, B->C 2, B->D 5, C->B 2, C->D 3
        NOTE: no edge points INTO A, and D has no outgoing edges.

        From A:  A=0, C=1 (direct), B=3 (A-C-B beats the direct 4),
                 D=4 (A-C-D; A-C-B-D would be 3+5=8)
        From D:  D=0, everything else inf.
        FW pairs: B-A = inf  (no edge into A -- trap for undirected thinking)
                  D-A = D-C = inf   (D has no outgoing edges)
                  B-D = 5 (direct ties B-C-D = 2+3), C-D = 3, diagonal = 0

    NEG_GRAPH (one negative edge, no cycle -- legal only for BF/FW):
        A-B = 4, A-C = 1, C-B = 2, B-D = -3, C-D = 3
        From A:  B = 3 (A-C-B), C = 1, D = 0 (A-C-B-D = 1+2-3)

    NEG_CYCLE: A->B 1, B->C -2, C->B -1  (B<->C sums to -3, reachable from A)
"""
import math
import random

import pytest

GRAPH = {
    "A": [("B", 4), ("C", 1)],
    "B": [("C", 2), ("D", 5)],
    "C": [("B", 2), ("D", 3)],
}
NEG_GRAPH = {
    "A": [("B", 4), ("C", 1)],
    "B": [("D", -3)],
    "C": [("B", 2), ("D", 3)],
}
NEG_CYCLE = {
    "A": [("B", 1)],
    "B": [("C", -2)],
    "C": [("B", -1)],
}


# =============================================================== dijkstra
def test_dijkstra_hand_verified_distances(S):
    assert S.dijkstra(GRAPH, "A") == {"A": 0, "B": 3, "C": 1, "D": 4}


def test_dijkstra_rejects_negative_edge_loudly(S):
    """Feeding Dijkstra a negative graph must raise -- the silent wrong
    answer is the actual production hazard."""
    with pytest.raises(ValueError):
        S.dijkstra(NEG_GRAPH, "A")


def test_dijkstra_unreachable_nodes_are_inf(S):
    assert S.dijkstra(GRAPH, "D") == {"A": math.inf, "B": math.inf,
                                      "C": math.inf, "D": 0}


# =========================================================== bellman-ford
def test_bellman_ford_negative_edge_no_cycle(S):
    dist, neg = S.bellman_ford(NEG_GRAPH, "A")
    assert neg is False
    assert dist == {"A": 0, "B": 3, "C": 1, "D": 0}


def test_bellman_ford_detects_reachable_negative_cycle(S):
    _, neg = S.bellman_ford(NEG_CYCLE, "A")
    assert neg is True


def test_bellman_ford_ignores_unreachable_negative_cycle(S):
    g = {"A": [("B", 1)], "X": [("Y", -1)], "Y": [("X", -1)]}
    dist, neg = S.bellman_ford(g, "A")
    assert neg is False
    assert dist["B"] == 1 and dist["X"] == math.inf


def test_bellman_ford_agrees_with_dijkstra_on_positive_graphs(S):
    d, neg = S.bellman_ford(GRAPH, "A")
    assert neg is False
    assert d == S.dijkstra(GRAPH, "A")


# =========================================================== floyd-warshall
def test_floyd_warshall_hand_verified_pairs(S):
    d = S.floyd_warshall(GRAPH)
    assert d["A"]["B"] == 3 and d["A"]["C"] == 1 and d["A"]["D"] == 4
    assert d["B"]["A"] == math.inf    # no edge into A -- directed-graph trap
    assert d["D"]["A"] == math.inf
    assert d["D"]["C"] == math.inf    # D has no outgoing edges
    assert d["B"]["D"] == 5 and d["C"]["D"] == 3
    assert all(d[x][x] == 0 for x in "ABCD")


def test_floyd_warshall_handles_negative_edges_without_a_cycle(S):
    """Negative weights, no negative cycle -- FW is correct where Dijkstra
    refuses to run at all."""
    d = S.floyd_warshall(NEG_GRAPH)
    assert d["A"]["B"] == 3 and d["A"]["D"] == 0 and d["A"]["C"] == 1


# =========================================================== estimate_ops
def test_estimate_ops_formulas(S):
    log2_1000 = math.log2(1000)
    assert S.estimate_ops("dijkstra", 1000, 3000) == pytest.approx(3000 * log2_1000)
    assert S.estimate_ops("a-star", 1000, 3000) == pytest.approx(3000 * log2_1000)
    assert S.estimate_ops("bellman-ford", 1000, 3000) == 1000 * 3000
    assert S.estimate_ops("floyd-warshall", 1000, 3000) == 1000 ** 3
    assert S.estimate_ops("johnson", 1000, 3000) == pytest.approx(
        1000 * 3000 + 1000 * 3000 * log2_1000)


def test_estimate_ops_rejects_unknown_algorithm(S):
    with pytest.raises(ValueError):
        S.estimate_ops("sort", 10, 20)


def test_estimate_ops_orders_a_sparse_world_correctly(S):
    """n=10_000, e=20_000 (E ~ 2V, the classic sparse case). The estimates
    must rank exactly as the theory says -- this is the interview story:
        dijkstra ~ E*log V          ~ 2.7e5   (single source)
        bellman-ford ~ V*E          ~ 2e8     (single source)
        johnson ~ V*E + V*E*log V  ~ 2.9e9   (all pairs)
        floyd-warshall = V^3        ~ 1e12    (all pairs)
    """
    n, e = 10_000, 20_000
    assert S.estimate_ops("dijkstra", n, e) < S.estimate_ops("bellman-ford", n, e)
    assert S.estimate_ops("bellman-ford", n, e) < S.estimate_ops("johnson", n, e)
    assert S.estimate_ops("johnson", n, e) < S.estimate_ops("floyd-warshall", n, e)
    # and Johnson beats FW only because this graph is sparse; on a dense
    # graph (E ~ V^2/2) even Johnson's V Dijkstra runs lose to plain FW
    assert S.estimate_ops("johnson", 1000, 2000) < S.estimate_ops("floyd-warshall", 1000, 2000)
    assert S.estimate_ops("johnson", 1000, 500_000) > S.estimate_ops("floyd-warshall", 1000, 500_000)


# ========================================================= choose_algorithm
def test_choose_dijkstra_is_the_default(S):
    assert S.choose_algorithm() == "dijkstra"
    assert S.choose_algorithm(n=10_000) == "dijkstra"


def test_choose_negative_weights_rules(S):
    """Negative weights outrank everything -- correctness first -- and the
    all-pairs variant jumps straight to Johnson."""
    assert S.choose_algorithm(negative_weights=True) == "bellman-ford"
    assert S.choose_algorithm(negative_weights=True, all_pairs=True) == "johnson"
    # negative beats a heuristic...
    assert S.choose_algorithm(negative_weights=True,
                              heuristic_available=True) == "bellman-ford"
    # ...and beats small-n all-pairs too
    assert S.choose_algorithm(negative_weights=True, all_pairs=True,
                              n=50) == "johnson"


def test_choose_all_pairs_boundary_is_500(S):
    """n=500: V^3 = 1.25e8, heapless, five lines -- FW earns its keep.
    n=501: Johnson's V*E*log V takes over on anything sparse."""
    assert S.choose_algorithm(all_pairs=True, n=500) == "floyd-warshall"
    assert S.choose_algorithm(all_pairs=True, n=501) == "johnson"
    assert S.choose_algorithm(all_pairs=True, n=100_000) == "johnson"


def test_choose_heuristic_flips_dijkstra_to_a_star(S):
    """The ONE knob that changes a single-source non-negative decision."""
    assert S.choose_algorithm(heuristic_available=True) == "a-star"
    assert S.choose_algorithm(heuristic_available=False) == "dijkstra"
    # an all-pairs workload ignores the heuristic -- rules fire in order
    assert S.choose_algorithm(all_pairs=True, n=100,
                              heuristic_available=True) == "floyd-warshall"


def test_choose_dense_never_changes_the_choice(S):
    """Density moves the op-count comparison, not the decision -- a rule
    that secretly consults `dense` is a wrong rule."""
    for dense in (False, True):
        assert S.choose_algorithm(dense=dense) == "dijkstra"
        assert S.choose_algorithm(negative_weights=True, dense=dense) == "bellman-ford"
        assert S.choose_algorithm(negative_weights=True, all_pairs=True,
                                  dense=dense) == "johnson"
        assert S.choose_algorithm(all_pairs=True, n=100, dense=dense) == "floyd-warshall"
        assert S.choose_algorithm(all_pairs=True, n=10_000, dense=dense) == "johnson"
        assert S.choose_algorithm(heuristic_available=True, dense=dense) == "a-star"


# ======================================================== compare_algorithms
def _random_graph(n, deg, rng):
    """Weighted, connected, non-negative (so all algorithms can run)."""
    g = {i: [] for i in range(n)}
    for i in range(1, n):                      # spanning chain first: connected
        g[i - 1].append((i, rng.randint(1, 10)))
    for u in g:                                 # then random extras
        for _ in range(rng.randint(0, deg - 1)):
            g[u].append((rng.randrange(n), rng.randint(1, 10)))
    return g


def test_compare_algorithms_reports_counts_and_estimates(S):
    r = S.compare_algorithms({"fixture": GRAPH})
    entry = r["fixture"]
    assert entry["n"] == 4 and entry["e"] == 6
    ops = entry["ops"]
    # the all-pairs workload: single-source bounds get run V times
    assert ops["dijkstra"] == pytest.approx(4 * 6 * math.log2(4))
    assert ops["a-star"] == pytest.approx(4 * 6 * math.log2(4))
    assert ops["bellman-ford"] == pytest.approx(4 * 4 * 6)
    # johnson and FW are already all-pairs -- no V multiplier
    assert ops["johnson"] == pytest.approx(4 * 6 + 4 * (6 * math.log2(4)))
    assert ops["floyd-warshall"] == 4 ** 3
    assert set(ops) == {"dijkstra", "bellman-ford", "floyd-warshall",
                        "a-star", "johnson"}


def test_compare_algorithms_measures_real_runs(S):
    """perf_counter around REAL runs of the real implementations -- no
    sleeping, no faking. Sanity on the tiny fixture first."""
    r = S.compare_algorithms({"fixture": GRAPH})
    ms = r["fixture"]["ms"]
    assert set(ms) == {"dijkstra", "bellman-ford", "floyd-warshall"}
    for v in ms.values():
        assert isinstance(v, float) and v >= 0.0
    assert ms["dijkstra"] < 5.0     # 4 sources x 6 edges: absurdly generous


def test_compare_algorithms_fw_competitive_only_when_dense(S):
    """THE measurement test: 60-node sparse vs dense. On the SPARSE graph,
    V Dijkstra runs beat FW's V^3 (op-count assertion -- deterministic, no
    wall-clock flakiness); on the DENSE one FW is competitive (ratio <= 2)
    and the sparse/dense ratio ordering must flip. Wall-clock checks get
    margins so big they can only catch catastrophic breakage."""
    rng = random.Random(27)
    sparse = _random_graph(60, 2, rng)     # ~1.5V edges
    dense = _random_graph(60, 59, rng)     # ~30V edges, near V^2/2

    r = S.compare_algorithms({"sparse": sparse, "dense": dense})
    s_ops, d_ops = r["sparse"]["ops"], r["dense"]["ops"]

    # op-count story (deterministic):
    assert s_ops["dijkstra"] < s_ops["floyd-warshall"]
    ratio_sparse = s_ops["floyd-warshall"] / s_ops["dijkstra"]
    ratio_dense = d_ops["floyd-warshall"] / d_ops["dijkstra"]
    assert ratio_dense <= 2.0                 # FW is competitive when dense
    assert ratio_dense < ratio_sparse          # and the gap closed, monotonically

    # measured story (generous margins -- catches breakage, not benchmarks):
    for name in ("sparse", "dense"):
        ms = r[name]["ms"]
        assert ms["dijkstra"] < 10.0           # ~1200 runs of a 60-node graph
        assert ms["floyd-warshall"] < 10.0     # 60^3 = 216k inner steps
        assert ms["bellman-ford"] < 10.0
