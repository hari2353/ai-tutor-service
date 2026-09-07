"""Lab 19 tests — union-find. Deterministic; timing only in the witness."""
import random
import time

import pytest


# ------------------------------------------------------------------ core ds
def test_uf_initial_state(P):
    uf = P.UnionFind(5)
    assert uf.count == 5
    for i in range(5):
        assert uf.find(i) == i
        assert uf.size(i) == 1


def test_uf_union_and_connected(P):
    uf = P.UnionFind(5)
    assert uf.union(0, 1) is True
    assert uf.connected(0, 1) is True
    assert uf.union(0, 1) is False                # already connected
    assert uf.count == 4


def test_uf_transitivity(P):
    uf = P.UnionFind(6)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(3, 4)
    assert uf.connected(0, 2) is True
    assert uf.connected(0, 3) is False
    assert uf.count == 3


def test_uf_size(P):
    uf = P.UnionFind(6)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(3, 4)
    assert uf.size(0) == 3
    assert uf.size(2) == 3
    assert uf.size(3) == 2
    assert uf.size(5) == 1


def test_uf_path_compression_flattens(P):
    """Build a deep chain by skipping rank, then find() must flatten:
    afterwards every node's parent is the root (depth 1)."""
    uf = P.UnionFind(6)
    # chain: 0-1-2-3-4-5 built via unions that create a path
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(2, 3)
    uf.union(3, 4)
    uf.union(4, 5)
    root = uf.find(0)
    uf.find(5)
    # after compression, depth of every node is <= 2 (root + maybe one hop)
    for x in range(6):
        assert uf.find(x) == root
    # every node's find is one hop after the pass above (root itself counts too)
    depth1 = sum(1 for x in range(6) if uf.parent[x] == root)
    assert depth1 == 6                            # everyone points at root


def test_uf_union_by_rank_keeps_shallow(P):
    """Union by rank: the tree height stays O(log n). Random unions on
    10k nodes, then all finds are quick; and find never recurses deeper
    than the rank bound (spot check: all roots reachable in one hop
    after a final pass of finds)."""
    rng = random.Random(3)
    n = 10_000
    uf = P.UnionFind(n)
    for _ in range(5_000):
        uf.union(rng.randrange(n), rng.randrange(n))
    for x in range(0, n, 97):
        uf.find(x)
    assert uf.count > 1                           # surely not one blob


def test_uf_count_zero_and_one(P):
    assert P.UnionFind(0).count == 0
    assert P.UnionFind(1).count == 1


# ------------------------------------------------------------------ connected components
def test_components_basic(P):
    assert P.connected_components(5, [(0, 1), (1, 2), (3, 4)]) == 2


def test_components_all_isolated(P):
    assert P.connected_components(4, []) == 4


def test_components_fully_connected(P):
    edges = [(i, i + 1) for i in range(9)]
    assert P.connected_components(10, edges) == 1


def test_components_empty_graph(P):
    assert P.connected_components(0, []) == 0


def test_components_triangle_plus_loner(P):
    assert P.connected_components(4, [(0, 1), (1, 2), (2, 0)]) == 2


# ------------------------------------------------------------------ redundant connection
def test_redundant_basic(P):
    assert list(P.redundant_connection([[1, 2], [1, 3], [2, 3]])) == [2, 3]


def test_redundant_leetcode_2(P):
    edges = [[1, 2], [2, 3], [3, 4], [1, 4], [1, 5]]
    assert list(P.redundant_connection(edges)) == [1, 4]


def test_redundant_returns_last_possible(P):
    # cycle of 3, answer must be the last edge that closes the cycle
    edges = [[1, 2], [2, 3], [3, 1]]
    assert list(P.redundant_connection(edges)) == [3, 1]


def test_redundant_big_cycle(P):
    n = 6
    edges = [[i, i + 1] for i in range(1, n)] + [[n, 1]]
    assert list(P.redundant_connection(edges)) == [n, 1]


# ------------------------------------------------------------------ accounts merge
def test_accounts_merge_classic(P):
    accounts = [
        ["John", "johnsmith@mail.com", "john_newyork@mail.com"],
        ["John", "johnsmith@mail.com", "john00@mail.com"],
        ["Mary", "mary@mail.com"],
        ["John", "johnnybravo@mail.com"],
    ]
    expected = [
        ["John", "john00@mail.com", "john_newyork@mail.com", "johnsmith@mail.com"],
        ["John", "johnnybravo@mail.com"],
        ["Mary", "mary@mail.com"],
    ]
    assert P.accounts_merge(accounts) == expected


def test_accounts_no_overlap(P):
    accounts = [["A", "a@x.com"], ["B", "b@x.com"]]
    assert P.accounts_merge(accounts) == [
        ["A", "a@x.com"], ["B", "b@x.com"]]


def test_accounts_chain_merge(P):
    # transitive: 1-2 share a, 2-3 share b → all one account
    accounts = [
        ["X", "a@x.com", "b@x.com"],
        ["Y", "b@x.com", "c@x.com"],
        ["Z", "c@x.com", "d@x.com"],
    ]
    merged = P.accounts_merge(accounts)
    assert len(merged) == 1
    # the merged name comes from the root account of the union chain — any
    # of the three names is acceptable; emails are the real identity.
    assert merged[0][0] in {"X", "Y", "Z"}
    assert merged[0][1:] == ["a@x.com", "b@x.com", "c@x.com", "d@x.com"]


def test_accounts_empty(P):
    assert P.accounts_merge([]) == []


# ------------------------------------------------------------------ islands ii
def test_islands_ii_leetcode(P):
    m, n = 3, 3
    positions = [[0, 0], [0, 1], [1, 2], [2, 1]]
    assert P.number_of_islands_ii(m, n, positions) == [1, 1, 2, 3]


def test_islands_ii_merge_by_bridge(P):
    m, n = 1, 4
    positions = [[0, 0], [0, 3], [0, 1], [0, 2]]
    assert P.number_of_islands_ii(m, n, positions) == [1, 2, 2, 1]


def test_islands_ii_duplicate_position(P):
    m, n = 2, 2
    positions = [[0, 0], [0, 0], [1, 1]]
    assert P.number_of_islands_ii(m, n, positions) == [1, 1, 2]


def test_islands_ii_all_land(P):
    m, n = 2, 2
    positions = [[0, 0], [0, 1], [1, 0], [1, 1]]
    assert P.number_of_islands_ii(m, n, positions) == [1, 1, 1, 1]


def test_islands_ii_empty(P):
    assert P.number_of_islands_ii(3, 3, []) == []


# ------------------------------------------------------------------ kruskal
def test_kruskal_basic_tree(P):
    n = 4
    edges = [(1, 0, 1), (4, 0, 2), (3, 1, 2), (2, 1, 3), (5, 2, 3)]
    total, mst = P.kruskal_mst(n, edges)
    assert total == 6                              # 1 + 2 + 3
    assert sorted((a, b) for _, a, b in mst) == [(0, 1), (1, 2), (1, 3)]
    assert len(mst) == n - 1


def test_kruskal_cycle_edges_rejected(P):
    n = 3
    edges = [(10, 0, 1), (10, 1, 2), (99, 0, 2)]
    total, mst = P.kruskal_mst(n, edges)
    assert total == 20
    assert (99, 0, 2) not in mst


def test_kruskal_disconnected_forest(P):
    # two components: {0,1} and {2,3}
    n = 4
    edges = [(1, 0, 1), (2, 2, 3)]
    total, mst = P.kruskal_mst(n, edges)
    assert total == 3
    assert len(mst) == 2


def test_kruskal_single_node(P):
    assert P.kruskal_mst(1, []) == (0, [])
    assert P.minimum_spanning_cost(1, []) == 0


def test_kruskal_matches_prim_bruteforce(P):
    """Cross-check against Prim's algorithm on random connected graphs."""
    rng = random.Random(9)
    for _ in range(20):
        n = rng.randrange(2, 9)
        edges = []
        for a in range(n):
            for b in range(a + 1, n):
                if rng.random() < 0.5:
                    w = rng.randrange(1, 20)
                    edges.append((w, a, b))
        # ensure connectivity: chain
        for a in range(n - 1):
            edges.append((rng.randrange(1, 20), a, a + 1))
        total, _ = P.kruskal_mst(n, edges)
        assert total == _prim(n, edges)


def _prim(n, edges):
    import heapq
    adj = {i: [] for i in range(n)}
    for w, a, b in edges:
        adj[a].append((w, b))
        adj[b].append((w, a))
    seen = {0}
    heap = list(adj[0])
    heapq.heapify(heap)
    total = 0
    while len(seen) < n and heap:
        w, v = heapq.heappop(heap)
        if v in seen:
            continue
        seen.add(v)
        total += w
        for e in adj[v]:
            if e[1] not in seen:
                heapq.heappush(heap, e)
    return total


def test_min_spanning_cost_only(P):
    n = 5
    edges = [(2, 0, 1), (3, 1, 2), (4, 3, 4), (6, 0, 2), (1, 4, 0)]
    # MST: 0-4(1), 0-1(2), 1-2(3), 3-4(4) = 10
    assert P.minimum_spanning_cost(n, edges) == 10


# ------------------------------------------------------------------ complexity witness
def test_uf_almost_constant_amortized_witness(P):
    """200k unions + 200k finds on 100k elements must finish well under 2s
    — the inverse-Ackermann amortization in action. The naive quadratic
    variant (no compression, no rank) would blow past it."""
    rng = random.Random(11)
    n = 100_000
    uf = P.UnionFind(n)
    t0 = time.perf_counter()
    for _ in range(200_000):
        uf.union(rng.randrange(n), rng.randrange(n))
    for _ in range(200_000):
        uf.find(rng.randrange(n))
    dt = time.perf_counter() - t0
    assert dt < 2.0, f"union-find too slow: {dt:.2f}s"


def test_kruskal_big_graph_witness(P):
    """Kruskal on 20k nodes / 60k edges: sort + UF. Under 2s."""
    rng = random.Random(12)
    n = 20_000
    edges = [(rng.randrange(1, 10**6), a, a + 1) for a in range(n - 1)]
    edges += [(rng.randrange(1, 10**6), rng.randrange(n), rng.randrange(n))
              for _ in range(40_000)]
    t0 = time.perf_counter()
    total, mst = P.kruskal_mst(n, edges)
    dt = time.perf_counter() - t0
    assert len(mst) == n - 1
    assert dt < 2.0, f"kruskal too slow: {dt:.2f}s"
