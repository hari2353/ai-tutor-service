import math

import pytest


# Hand-verified fixture:        A
#                             / \
#                            4   1
#                           /     \
#                          B --2-- C
#                           \     /
#                            5   3
#                             \ /
#                              D
GRAPH = {
    "A": [("B", 4), ("C", 1)],
    "B": [("C", 2), ("D", 5)],
    "C": [("B", 2), ("D", 3)],
}
# Dijkstra A: B=3 (A-C-B), C=1, D=4 (A-C-D)
EXPECTED = {"A": 0, "B": 3, "C": 1, "D": 4}

NEG_GRAPH = {
    "A": [("B", 4), ("C", 1)],
    "B": [("D", -3)],   # negative edge, no cycle anywhere
    "C": [("B", 2), ("D", 3)],
}
# A-B = 4, A-C = 1, A-C-B = 3 (better), A-C-D = 4 (better than A-B-D = 1?) see test
NEG_CYCLE = {
    "A": [("B", 1)],
    "B": [("C", -2)],
    "C": [("B", -1)],   # B<->C sums to -3: negative cycle
}


def test_dijkstra_basic(S):
    assert S.dijkstra(GRAPH, "A") == EXPECTED


def test_dijkstra_from_other_source(S):
    assert S.dijkstra(GRAPH, "D") == {"A": math.inf, "B": math.inf,
                                      "C": math.inf, "D": 0}


def test_dijkstra_rejects_negative(S):
    with pytest.raises(ValueError):
        S.dijkstra(NEG_GRAPH, "A")


def test_dijkstra_single_node(S):
    assert S.dijkstra({"X": []}, "X") == {"X": 0}


def test_dijkstra_lazy_deletion_correct_on_push_heavy_graph(S):
    # complete-ish graph where many stale heap entries accumulate
    g = {i: [(j, abs(i - j) + 1) for j in range(10) if j != i] for i in range(10)}
    d = S.dijkstra(g, 0)
    assert d[5] == 6  # 0->1->2->3->4->5 each cost 1... actually edge i->j costs |i-j|+1
    # direct 0->5 costs 6; via chain 0->1(2)->2(2)->3(2)->4(2)->5(2) costs 10
    assert all(d[j] == min(abs(j) + 1, *(abs(j - k) + 1 + abs(k) + 1 for k in range(10) if k not in (0, j))) for j in range(1, 10))


def test_bellman_ford_negative_edge(S):
    dist, neg = S.bellman_ford(NEG_GRAPH, "A")
    assert neg is False
    # A-C = 1, A-C-B = 3, A-B-D = 1, but A-C-B-D = 1+2-3 = 0 (best)
    assert dist["B"] == 3
    assert dist["C"] == 1
    assert dist["D"] == 0


def test_bellman_ford_detects_negative_cycle(S):
    dist, neg = S.bellman_ford(NEG_CYCLE, "A")
    assert neg is True


def test_bellman_ford_unreachable_negative_cycle_not_flagged(S):
    # negative cycle exists but not reachable from src
    g = {"A": [("B", 1)], "X": [("Y", -1)], "Y": [("X", -1)]}
    dist, neg = S.bellman_ford(g, "A")
    assert neg is False
    assert dist["B"] == 1


def test_bellman_ford_matches_dijkstra_on_positive(S):
    d1, neg = S.bellman_ford(GRAPH, "A")
    assert neg is False
    assert d1 == EXPECTED


def test_floyd_warshall_all_pairs(S):
    d = S.floyd_warshall(GRAPH)
    assert d["A"]["D"] == 4
    assert d["D"]["A"] == math.inf
    assert d["A"]["A"] == 0
    assert d["B"]["D"] == 5  # B-D direct = 5; B-C-D = 2+3 = 5 too
    assert d["A"]["B"] == 3  # A-C-B = 1+2


def test_floyd_warshall_uses_best_intermediate(S):
    g = {"A": [("B", 10), ("C", 25)], "B": [("C", 10)], "C": []}
    d = S.floyd_warshall(g)
    assert d["A"]["C"] == 20  # via B beats the direct 25


def test_a_star_straight_line(S):
    grid = [[0] * 5 for _ in range(5)]
    manhattan = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    path, cost = S.a_star(grid, (0, 0), (4, 4), manhattan)
    assert cost == 8
    assert path[0] == (0, 0) and path[-1] == (4, 4)
    # optimal on open grid: every step moves closer
    assert all(abs(path[i + 1][0] - path[i][0]) + abs(path[i + 1][1] - path[i][1]) == 1
               for i in range(len(path) - 1))


def test_a_star_routes_around_wall(S):
    grid = [
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 1],
        [0, 0, 0, 0, 0],
    ]
    manhattan = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    path, cost = S.a_star(grid, (0, 0), (4, 4), manhattan)
    assert cost == 16  # forced through the two gaps (BFS-verified optimum)
    for (r, c) in path:
        assert grid[r][c] == 0


def test_a_star_unreachable(S):
    grid = [
        [0, 1],
        [1, 0],
    ]
    manhattan = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    path, cost = S.a_star(grid, (0, 0), (1, 1), manhattan)
    assert path is None
    assert cost == math.inf


def test_a_star_start_is_goal(S):
    grid = [[0]]
    path, cost = S.a_star(grid, (0, 0), (0, 0), lambda a, b: 0)
    assert path == [(0, 0)]
    assert cost == 0


def test_algorithms_agree_on_positive_graph(S):
    g = GRAPH
    d = S.dijkstra(g, "A")
    bf, _ = S.bellman_ford(g, "A")
    fw = S.floyd_warshall(g)
    for node in d:
        assert d[node] == bf[node] == fw["A"][node]
