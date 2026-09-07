"""Lab 26 tests — graph representations & traversal invariants.

THE fixture (one fixed graph reused across tests), n=9, undirected:

    Component A: 4-cycle 0-1-2-3-0 with a tail 1-4      bipartite
    Component B: triangle 5-6-7                         odd cycle
    Vertex 8:   isolated

        0 ──── 3
        │      │
        1 ──── 2
        │
        4           5
                    │ \\
                    6 ─ 7

        8   (isolated)

    edges = [(0,1), (1,2), (2,3), (3,0), (1,4), (5,6), (6,7), (7,5)]

Exact orders below are hand-derived and pinned — they only hold because
neighbor buckets are in insertion order, which test 1 pins first.
"""
import random

import pytest

# The ONE fixed graph, as an edge list. Hand-derived expectations everywhere.
FIXED_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (1, 4), (5, 6), (6, 7), (7, 5)]
N = 9
# what to_adjacency_list MUST produce from FIXED_EDGES (insertion order pinned)
FIXED_ADJ = [
    [1, 3],        # 0
    [0, 2, 4],     # 1
    [1, 3],        # 2
    [2, 0],        # 3
    [1],           # 4
    [6, 7],        # 5
    [5, 7],        # 6
    [6, 5],        # 7
    [],            # 8
]


def _recursive_preorder(graph, src):
    """Reference: recursive DFS preorder. dfs_order must match this exactly."""
    visited = [False] * len(graph)
    order = []

    def go(u):
        visited[u] = True
        order.append(u)
        for v in graph[u]:
            if not visited[v]:
                go(v)

    go(src)
    return order


# --------------------------------------------------------------- representations
def test_adjacency_list_undirected_buckets(G):
    assert G.to_adjacency_list(N, FIXED_EDGES) == FIXED_ADJ
    assert G.to_adjacency_list(0, []) == []


def test_adjacency_list_directed_and_self_loop(G):
    d = G.to_adjacency_list(3, [(0, 1), (1, 2)], directed=True)
    assert d == [[1], [2], []]                    # NOT mirrored
    assert G.to_adjacency_list(2, [(1, 1)]) == [[], [1, 1]]   # loop x2


def test_adjacency_matrix_unweighted(G):
    m = G.to_adjacency_matrix(4, [(0, 1), (1, 2), (2, 3), (3, 0)])
    assert m == [[0, 1, 0, 1],
                 [1, 0, 1, 0],
                 [0, 1, 0, 1],
                 [1, 0, 1, 0]]
    assert all(m[i][i] == 0 for i in range(4))


def test_adjacency_matrix_weighted_and_directed(G):
    w = G.to_adjacency_matrix(3, [(0, 1, 7), (1, 2, 3), (0, 2, 2)])
    assert w == [[0, 7, 2], [7, 0, 3], [2, 3, 0]]        # weight, not 1
    d = G.to_adjacency_matrix(3, [(0, 1, 7), (1, 2, 3), (2, 0, 5)], directed=True)
    assert d == [[0, 7, 0], [0, 0, 3], [5, 0, 0]]        # asymmetric


def test_edge_list_canonical_order(G):
    m = G.to_adjacency_matrix(N, FIXED_EDGES)
    # undirected: upper triangle, row-major, diagonal kept for self-loops
    assert G.to_edge_list(m) == [(0, 1), (0, 3), (1, 2), (1, 4),
                                 (2, 3), (5, 6), (5, 7), (6, 7)]
    # directed: every non-zero cell, full row-major scan
    d = [[0, 7, 0], [0, 0, 3], [5, 0, 0]]
    assert G.to_edge_list(d, directed=True) == [(0, 1), (1, 2), (2, 0)]
    assert G.to_edge_list(d, directed=True, weighted=True) == \
        [(0, 1, 7), (1, 2, 3), (2, 0, 5)]
    # a self-loop on the diagonal survives the undirected scan
    assert G.to_edge_list([[0, 0], [0, 1]]) == [(1, 1)]


def test_conversions_round_trip(G):
    m = G.to_adjacency_matrix(N, FIXED_EDGES)
    el = G.to_edge_list(m)
    assert G.to_adjacency_matrix(N, el) == m            # edges -> matrix stable
    # weighted round trip preserves weights
    w = [[0, 7, 2], [7, 0, 3], [2, 3, 0]]
    assert G.to_edge_list(w, weighted=True) == [(0, 1, 7), (0, 2, 2), (1, 2, 3)]
    assert G.to_adjacency_matrix(3, G.to_edge_list(w, weighted=True)) == w
    # self-loop round trip
    loop = [[0, 0], [0, 1]]
    assert G.to_adjacency_matrix(2, G.to_edge_list(loop)) == loop


# --------------------------------------------------------------------- traversals
def test_bfs_exact_order_fixture(G):
    """FIFO, mark-on-enqueue, neighbors in insertion order:
    from 0 we enqueue 1 then 3, so 3 is VISITED before 2 (its other neighbor)."""
    g = G.to_adjacency_list(N, FIXED_EDGES)
    assert G.bfs_order(g, 0) == [0, 1, 3, 2, 4]
    assert G.bfs_order(g, 5) == [5, 6, 7]     # neighbors in insertion order
    assert G.bfs_order(g, 8) == [8]            # trivial but must not crash


def test_bfs_stays_in_source_component(G):
    g = G.to_adjacency_list(N, FIXED_EDGES)
    groups = [{0, 1, 2, 3, 4}, {5, 6, 7}, {8}]
    for src in range(N):
        got = G.bfs_order(g, src)
        assert len(got) == len(set(got))               # nobody twice
        assert src in got                             # source always visited
        assert set(got) in groups                     # exactly one component


def test_dfs_exact_order_fixture(G):
    """Stack DFS == recursive preorder: from 0, walk 0-1-2-3 around the ring,
    only then the tail 4 — the mirror image of BFS above."""
    g = G.to_adjacency_list(N, FIXED_EDGES)
    assert G.dfs_order(g, 0) == [0, 1, 2, 3, 4]
    assert G.dfs_order(g, 5) == [5, 6, 7]
    assert G.dfs_order(g, 8) == [8]


def test_dfs_stack_equals_recursive_preorder(G):
    """THE invariant: the explicit-stack dfs_order must produce exactly
    recursive preorder on every graph, from every source."""
    rng = random.Random(1234)
    cases = [
        G.to_adjacency_list(N, FIXED_EDGES),
        G.to_adjacency_list(5, [(0, 1), (0, 2), (0, 3), (0, 4)]),       # star
        G.to_adjacency_list(6, [(0, 1), (0, 2), (1, 3), (2, 3),
                                (3, 4), (2, 5)]),                        # converge
        G.to_adjacency_list(4, [(0, 1), (0, 2), (1, 3), (2, 3)],
                            directed=True),                              # diamond
        G.to_adjacency_list(5, [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)],
                            directed=True),                              # +skip
    ]
    for _ in range(200):      # random directed graphs, dup edges and loops ok
        n = rng.randrange(1, 8)
        edges = [(rng.randrange(n), rng.randrange(n))
                 for _ in range(rng.randrange(0, n * n + 1))]
        cases.append(G.to_adjacency_list(n, edges, directed=True))
        cases.append(G.to_adjacency_list(n, edges))
    for g in cases:
        for src in range(len(g)):
            assert G.dfs_order(g, src) == _recursive_preorder(g, src), \
                f"stack != recursive preorder on {g} from {src}"


# ---------------------------------------------------------------------- structure
def test_connected_components_fixture(G):
    g = G.to_adjacency_list(N, FIXED_EDGES)
    assert G.connected_components(g) == [[0, 1, 2, 3, 4], [5, 6, 7], [8]]


def test_connected_components_edge_cases(G):
    assert G.connected_components([]) == []
    assert G.connected_components([[], [], []]) == [[0], [1], [2]]
    chain = G.to_adjacency_list(4, [(0, 1), (1, 2), (2, 3)])
    assert G.connected_components(chain) == [[0, 1, 2, 3]]


# ---------------------------------------------------------------------- cycles
def test_undirected_cycle_trees_vs_cycles(G):
    assert G.has_cycle_undirected(G.to_adjacency_list(2, [(0, 1)])) is False
    assert G.has_cycle_undirected(
        G.to_adjacency_list(4, [(0, 1), (1, 2), (2, 3)])) is False   # path
    assert G.has_cycle_undirected(
        G.to_adjacency_list(5, [(0, 1), (0, 2), (0, 3), (0, 4)])) is False  # star
    assert G.has_cycle_undirected(
        G.to_adjacency_list(3, [(0, 1), (1, 2), (2, 0)])) is True   # triangle
    assert G.has_cycle_undirected(
        G.to_adjacency_list(N, FIXED_EDGES)) is True                # fixture


def test_undirected_cycle_self_loop_and_parallel(G):
    assert G.has_cycle_undirected(G.to_adjacency_list(1, [(0, 0)])) is True
    assert G.has_cycle_undirected(
        G.to_adjacency_list(2, [(0, 1), (0, 1)])) is True            # parallel
    # a self-loop counts 2 toward degree_sum: 2 edges -> sum 4 (handshake)
    assert G.degree_sum(G.to_adjacency_list(2, [(0, 0), (0, 1)])) == 4


def test_directed_cycle_diamond_is_fine(G):
    """THE test for three-color: a diamond DAG converges on 3 via two paths.
    Binary visited/unvisited reports a phantom cycle here; only GRAY counts."""
    diamond = G.to_adjacency_list(4, [(0, 1), (0, 2), (1, 3), (2, 3)],
                                  directed=True)
    assert G.has_cycle_directed(diamond) is False
    dag = G.to_adjacency_list(6, [(0, 1), (0, 2), (1, 3), (2, 3),
                                  (3, 4), (0, 5), (5, 4)], directed=True)
    assert G.has_cycle_directed(dag) is False


def test_directed_cycle_finds_back_edges(G):
    tri = G.to_adjacency_list(3, [(0, 1), (1, 2), (2, 0)], directed=True)
    assert G.has_cycle_directed(tri) is True
    two = G.to_adjacency_list(2, [(0, 1), (1, 0)], directed=True)
    assert G.has_cycle_directed(two) is True
    loop = G.to_adjacency_list(3, [(2, 2)], directed=True)
    assert G.has_cycle_directed(loop) is True


# ------------------------------------------------------------------ bipartite
def test_bipartite_even_cycles_exact_coloring(G):
    ok, color = G.is_bipartite(G.to_adjacency_list(4, [(0, 1), (1, 2),
                                                       (2, 3), (3, 0)]))
    assert ok is True
    assert color == {0: 0, 1: 1, 2: 0, 3: 1}
    ok6, color6 = G.is_bipartite(G.to_adjacency_list(
        6, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]))
    assert ok6 is True
    assert color6 == {0: 0, 1: 1, 2: 0, 3: 1, 4: 0, 5: 1}


def test_bipartite_odd_cycle_conflict(G):
    ok, color = G.is_bipartite(G.to_adjacency_list(3, [(0, 1), (1, 2), (2, 0)]))
    assert ok is False and color is None
    ok, color = G.is_bipartite(G.to_adjacency_list(N, FIXED_EDGES))
    assert ok is False and color is None            # triangle 5-6-7 inside


def test_bipartite_disconnected_and_isolated(G):
    g = G.to_adjacency_list(6, [(0, 1), (1, 2), (2, 3), (3, 0), (1, 4)])  # +5
    ok, color = G.is_bipartite(g)
    assert ok is True
    # component A colored from 0; isolated 5 starts its own component at 0
    assert color == {0: 0, 1: 1, 2: 0, 3: 1, 4: 0, 5: 0}
    assert G.is_bipartite([]) == (True, {})


# ------------------------------------------------------------------ handshake
def test_handshake_lemma_random_graphs(G):
    """sum(deg) == 2E on the fixture and on seeded random graphs."""
    g = G.to_adjacency_list(N, FIXED_EDGES)
    m = G.to_adjacency_matrix(N, FIXED_EDGES)
    assert G.degree_sum(g) == 16 == 2 * len(G.to_edge_list(m))

    for seed in (7, 42, 2026):
        rng = random.Random(seed)
        n, target = 12, 20
        edges, seen = [], set()
        while len(edges) < target:
            u, v = rng.randrange(n), rng.randrange(n)
            if u == v:
                continue
            key = (min(u, v), max(u, v))
            if key in seen:
                continue
            seen.add(key)
            edges.append(key)
        gr = G.to_adjacency_list(n, edges)
        assert G.degree_sum(gr) == 2 * len(edges)
        comps = G.connected_components(gr)
        # components partition the vertex set
        assert sorted(v for c in comps for v in c) == list(range(n))
        # every edge's endpoints share a component
        where = {v: i for i, c in enumerate(comps) for v in c}
        assert all(where[u] == where[v] for u, v in edges)
        # BFS from any component's first node visits exactly that component
        for c in comps:
            assert set(G.bfs_order(gr, c[0])) == set(c)
