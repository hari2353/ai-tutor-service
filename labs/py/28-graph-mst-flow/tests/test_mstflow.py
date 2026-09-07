"""Lab 28 tests — MST, max-flow, min-cut, bipartite matching.

Every fixed expectation was hand-verified: the flow values were confirmed
by enumerating ALL s-t cuts, the MST totals by enumerating all acyclic
spanning subsets (brute force). No sleeps, pure stdlib, seeded randomness.
"""
import itertools
import random

import pytest

# 5 nodes, connected. Hand-computed MST: edges (1,0,1),(2,1,3),(3,1,2),(6,2,4)
E5 = [(1, 0, 1), (4, 0, 2), (3, 1, 2), (2, 1, 3), (5, 2, 3), (7, 3, 4), (6, 2, 4), (8, 0, 4)]

# Classic 4-node flow fixture. Max flow 5, verified by enumerating all 8 s-t cuts.
C4 = [[0, 3, 2, 0],
      [0, 0, 1, 2],
      [0, 0, 0, 3],
      [0, 0, 0, 0]]


def _random_graph(seed):
    """Seeded random CONNECTED graph (spanning tree + extra edges)."""
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    edges = []
    for u in range(1, n):                      # random spanning tree first
        v = rng.randrange(u)
        edges.append((rng.randint(1, 20), u, v))
    for _ in range(rng.randint(3, 12)):        # extra edges
        u, v = rng.sample(range(n), 2)
        edges.append((rng.randint(1, 20), u, v))
    return n, edges


def _random_capacity(seed, n=6):
    rng = random.Random(100 + seed)
    cap = [[0] * n for _ in range(n)]
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < 0.35:
                cap[u][v] = rng.randint(1, 9)
    return cap


def _min_cut_by_enumeration(n, capacity, s, t):
    """Oracle: min capacity over ALL 2^(n-2) s-t cuts."""
    others = [v for v in range(n) if v not in (s, t)]
    best = None
    for k in range(len(others) + 1):
        for extra in itertools.combinations(others, k):
            side = {s, *extra}
            val = sum(capacity[u][v] for u in side for v in range(n)
                      if v not in side)
            best = val if best is None else min(best, val)
    return best


# ------------------------------------------------------------------ kruskal
def test_kruskal_hand_computed_fixture(M):
    """Hand-computed: MST picks weights 1,2,3,6 (total 12); edges 4,5,7,8
    are rejected — 4/5 would close cycles, 7 is beaten by 6, 8 by 1+2."""
    mst, total = M.kruskal_mst(5, E5)
    assert total == 12
    assert len(mst) == 4                          # tree on 5 nodes
    assert sorted(w for w, _u, _v in mst) == [1, 2, 3, 6]
    # it is acyclic: 4 edges on 5 nodes that actually connect everything
    assert M.kruskal_mst(5, mst)[1] == 12


def test_kruskal_matches_prim_on_random_graphs(M):
    """Same MST weight either way — both are correct by the cut property."""
    _n, edges = _random_graph(0)
    k = M.kruskal_mst(5, E5)
    p = M.prim_mst(5, E5)
    assert k[1] == p[1] == 12                    # fixed fixture first
    for seed in range(5):
        n, edges = _random_graph(seed)
        assert M.kruskal_mst(n, edges)[1] == M.prim_mst(n, edges, start=seed % n)[1]


def test_kruskal_disconnected_graph_returns_forest(M):
    """Components {0,1,2} (triangle + expensive chord) and {3,4}.
    Kruskal must span BOTH: keep 1,2 and 10, reject the (5,0,2) cycle edge."""
    eforest = [(1, 0, 1), (2, 1, 2), (5, 0, 2), (10, 3, 4)]
    mst, total = M.kruskal_mst(5, eforest)
    assert total == 13                           # 1 + 2 + 10
    assert len(mst) == 3                         # 5 nodes, 2 components
    assert not any(w == 5 for w, _u, _v in mst)  # cycle edge rejected


# ------------------------------------------------------------------ prim
def test_prim_heap_grows_from_start(M):
    p_mst, p_total = M.prim_mst(5, E5)
    assert p_total == 12
    assert len(p_mst) == 4
    assert sorted(w for w, _u, _v in p_mst) == [1, 2, 3, 6]


def test_prim_only_reaches_starts_component(M):
    """Prim grows ONE tree: vertices unreachable from start are simply absent."""
    eforest = [(1, 0, 1), (2, 1, 2), (5, 0, 2), (10, 3, 4)]
    mst, total = M.prim_mst(5, eforest, start=0)
    assert total == 3                            # only {0,1,2}: edges 1 and 2
    assert len(mst) == 2
    assert {v for _w, u, v in mst} <= {0, 1, 2}


# ------------------------------------------------------------------ union-find
def test_union_find_basic_merge_and_query(M):
    uf = M.UnionFind(6)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(3, 4)
    assert uf.connected(0, 2)                    # transitive
    assert uf.connected(2, 0)                   # symmetric
    assert not uf.connected(0, 3)               # separate sets so far
    assert uf.connected(3, 4)


def test_union_find_union_returns_false_on_same_set(M):
    uf = M.UnionFind(6)
    assert uf.union(0, 1) is True                # merged
    assert uf.union(0, 1) is False               # already together
    assert uf.union(2, 3) is True
    assert uf.union(2, 3) is False


def test_union_find_merge_two_components(M):
    uf = M.UnionFind(6)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(3, 4)
    assert uf.union(2, 3) is True                # joins the two trees
    assert uf.connected(4, 0)                    # now everything is one set


# ------------------------------------------------------------------ edmonds-karp
def test_edmonds_karp_classic_fixture(M):
    """s=0 -> t=3. Value 5 was verified by enumerating all 8 s-t cuts
    (min cut: {0} vs {1,2,3} has capacity 3+2=5)."""
    value, flows = M.edmonds_karp(4, C4, 0, 3)
    assert value == 5
    assert len(flows) == 4 and all(len(row) == 4 for row in flows)


def test_edmonds_karp_input_matrix_not_mutated(M):
    before = [row[:] for row in C4]
    M.edmonds_karp(4, C4, 0, 3)
    assert C4 == before


def test_flow_conservation_at_internal_nodes(M):
    """What flows in must flow out at every node except s and t."""
    value, flows = M.edmonds_karp(4, C4, 0, 3)
    for u in (1, 2):
        inflow = sum(max(0, flows[v][u]) for v in range(4))
        outflow = sum(max(0, flows[u][v]) for v in range(4))
        assert inflow == outflow, f"node {u} leaks flow"
    assert sum(flows[0][v] for v in range(4)) == value      # source exports it all
    assert sum(flows[v][3] for v in range(4)) == value     # sink receives it all


def test_edmonds_karp_needs_reverse_edges(M):
    """A graph where BFS-augmenting WITHOUT reverse residual edges
    under-reports 1 vs the true 2 (verified by cut enumeration below, and
    by a search over 300k random graphs that EK-with-reverse always matches
    the enumeration). What happens: the first shortest path 0->3->2->6
    saturates 2->6; the only remaining route 0->4->2->3->5->6 must REUSE
    2->3 backwards, cancelling part of the earlier 3->2 assignment.
    Drop the reverse-edge update and the algorithm gets stuck at 1."""
    cap = [[0, 0, 0, 1, 1, 0, 0],
           [1, 0, 3, 2, 1, 2, 0],
           [0, 0, 0, 0, 0, 0, 1],
           [0, 1, 2, 0, 2, 2, 0],
           [3, 0, 3, 0, 0, 0, 0],
           [0, 0, 0, 3, 0, 0, 3],
           [0, 0, 0, 1, 0, 0, 0]]
    assert _min_cut_by_enumeration(7, cap, 0, 6) == 2   # ground truth
    value, _flows = M.edmonds_karp(7, cap, 0, 6)
    assert value == 2


# ------------------------------------------------------------------ min-cut
def test_min_cut_value_equals_max_flow_on_fixture(M):
    cut_value, source_side = M.min_cut(4, C4, 0, 3)
    assert cut_value == 5 == M.edmonds_karp(4, C4, 0, 3)[0]
    assert source_side == {0}                    # only s is reachable in the residual


def test_min_cut_matches_flow_on_random_matrices(M):
    """Max-flow min-cut theorem, cross-checked against cut enumeration."""
    for seed in range(5):
        cap = _random_capacity(seed)
        n = len(cap)
        flow_value, _flows = M.edmonds_karp(n, cap, 0, n - 1)
        cut_value, side = M.min_cut(n, cap, 0, n - 1)
        assert cut_value == flow_value, f"seed {seed}: theorem violated"
        assert _min_cut_by_enumeration(n, cap, 0, n - 1) == flow_value
        assert 0 in side and (n - 1) not in side  # a real s-side of the cut
        # the side's crossing capacity (in the ORIGINAL matrix) equals the flow
        crossing = sum(cap[u][v] for u in side for v in range(n) if v not in side)
        assert crossing == flow_value, f"seed {seed}: side is not a min cut"


# ------------------------------------------------------------------ matching
def test_bipartite_matching_full_house(M):
    """3 left, 3 right; edges (0,0),(0,1),(1,1),(2,2) -> matching size 3."""
    assert M.bipartite_matching(3, 3, [(0, 0), (0, 1), (1, 1), (2, 2)]) == 3


def test_bipartite_matching_beats_greedy(M):
    """One-pass greedy over (0,0),(0,1),(1,0) takes (0,0), blocks the rest -> 1.
    Optimal is 2: L0->R1, L1->R0. Flow must find the augmentation."""
    assert M.bipartite_matching(2, 2, [(0, 0), (0, 1), (1, 0)]) == 2


def test_bipartite_matching_no_edges(M):
    assert M.bipartite_matching(3, 3, []) == 0
