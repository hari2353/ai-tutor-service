"""Lab 29 tests — SCC, bridges, articulation points, 2-SAT.

Every fixed expectation was hand-verified before baking: the SCC
decompositions by brute-force reachability closure (BFS from every
node; u,v same SCC iff mutual reach) cross-checked against independent
recursive Tarjan and Kosaraju; bridges/articulation points by removing
the edge/vertex and counting components; 2-SAT by full 2^n enumeration.
No sleeps, pure stdlib, seeded randomness, iterative DFS only.
"""
import random

import pytest


# Classic CLRS 8-node example (Fig 22.9): s,z,t,x,y,u,v,w -> 0..7.
# Ground truth (verified by reachability closure + recursive refs):
# SCCs {0}, {1,3,4,7}, {2}, {5,6}. Note z,y,x,w form one 4-node SCC and
# {u,v} a 2-node one -- a component of size 4, 2, and singletons all
# in one fixture.
CLRS = [[1, 7],       # s -> z, w
        [4, 7],       # z -> y, w
        [3, 4, 1],    # t -> x, y, z
        [1],          # x -> z
        [3],          # y -> x
        [2, 6],       # u -> t, v
        [0, 7, 3, 5], # v -> s, w, x, u
        [3]]          # w -> x
CLRS_SCCS = [[0], [1, 3, 4, 7], [2], [5, 6]]

G2 = [[1],       # 0 -> 1
      [2, 5],    # 1 -> 2, 5
      [0, 3],    # 2 -> 0, 3
      [4],       # 3 -> 4
      [3],       # 4 -> 3
      [5]]       # 5 -> 5 (self-loop)
G2_SCCS = [[0, 1, 2], [3, 4], [5]]

DAG = [[1, 2], [3], [3], [4], []]
RING = [[1], [2], [3], [4], [0]]

# two triangles 0-1-2 and 3-4-5 joined by edge 2-3 (undirected)
TRI2 = [[1, 2], [0, 2, 3], [1, 0, 3], [2, 4, 5], [3, 5], [4, 3]]

# bowtie: two triangles sharing vertex 2 (undirected)
BOWTIE = [[1], [0, 2], [1, 0, 3, 4], [2, 4], [3, 2]]

# 5-cycle: 2-edge-connected, no cut vertices
CYCLE5 = [[1, 4], [0, 2], [1, 3], [2, 4], [3, 0]]


def _random_digraph(seed):
    """Seeded random digraph, nodes 5-9, each edge present w.p. ~0.3."""
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    return [[v for v in range(n) if v != u and rng.random() < 0.3]
            for u in range(n)]


# ------------------------------------------------------------------ tarjan
def test_tarjan_clrs_example(S):
    assert S.tarjan_scc(CLRS) == CLRS_SCCS


def test_tarjan_second_fixture(S):
    """Cycle 0->1->2->0, 2-cycle 3<->4, and 5 self-looping alone."""
    assert S.tarjan_scc(G2) == G2_SCCS


def test_tarjan_canonical_sorted_output(S):
    """Each SCC sorted ascending, list-of-SCCs sorted: the pinned,
    deterministic canonical form (must equal kosaraju's)."""
    out = S.tarjan_scc(CLRS)
    assert all(c == sorted(c) for c in out)
    assert out == sorted(out)


def test_tarjan_empty_and_isolated(S):
    assert S.tarjan_scc([]) == []
    assert S.tarjan_scc([[], [], []]) == [[0], [1], [2]]


def test_tarjan_deep_path_no_recursion_limit(S):
    """A 5000-node path would blow Python's ~1000-frame recursion limit
    under naive recursive DFS. Iterative is a requirement, not a nicety."""
    n = 5000
    path = [[i + 1] for i in range(n)] + [[]]
    assert S.tarjan_scc(path) == [[i] for i in range(n + 1)]


# ------------------------------------------------------------------ kosaraju
def test_kosaraju_clrs_example(S):
    assert S.kosaraju_scc(CLRS) == CLRS_SCCS


def test_kosaraju_second_fixture(S):
    assert S.kosaraju_scc(G2) == G2_SCCS


def test_tarjan_equals_kosaraju_on_random_digraphs(S):
    """Both decompose identically; only the canonical output form makes
    the equality check trivial. 10 seeded digraphs."""
    for seed in range(10):
        g = _random_digraph(seed)
        assert S.tarjan_scc(g) == S.kosaraju_scc(g), f"seed {seed}: {g}"


def test_kosaraju_deep_path_no_recursion_limit(S):
    n = 5000
    ring = [[(i + 1) % n] for i in range(n)]
    assert S.kosaraju_scc(ring) == [list(range(n))]
    path = [[i + 1] for i in range(n)] + [[]]
    assert S.kosaraju_scc(path) == [[i] for i in range(n + 1)]


# ------------------------------------------------------------------ extremes
def test_dag_every_node_own_scc(S):
    """No cycles -> the SCC decomposition is all singletons (both
    algorithms). Every DAG is its own condensation."""
    expected = [[0], [1], [2], [3], [4]]
    assert S.tarjan_scc(DAG) == expected
    assert S.kosaraju_scc(DAG) == expected


def test_ring_one_scc(S):
    """Fully cyclic: every node reaches every other -> one component."""
    expected = [[0, 1, 2, 3, 4]]
    assert S.tarjan_scc(RING) == expected
    assert S.kosaraju_scc(RING) == expected


# ------------------------------------------------------------------ bridges
def test_bridges_two_triangles_joined_by_one_edge(S):
    """Edge (2, 3) is the only connection between the triangles: the
    only bridge. Every triangle edge has a bypass; verified by removal."""
    assert S.bridges(TRI2) == [(2, 3)]


def test_bridges_2_edge_connected_graph_has_none(S):
    """A cycle is 2-edge-connected: every edge has a backup path."""
    assert S.bridges(CYCLE5) == []
    assert S.bridges(BOWTIE) == []


def test_bridges_path_every_edge_is_one(S):
    path = [[1], [0, 2], [1, 3], [2]]
    assert S.bridges(path) == [(0, 1), (1, 2), (2, 3)]


def test_bridges_normalized_undirected_order_and_disconnected(S):
    """Undirected edge may sit in buckets as (v, u) with u < v; output
    is the normalized (min, max) form, sorted. Disconnected input: two
    separate edges 0-1 (stored 1->0) and 2-3 (stored 2->3) — both are
    bridges (verified by removal: each deletion bumps 2 comps to 3)."""
    swapped = [[1], [0], [3], [2]]
    assert S.bridges(swapped) == [(0, 1), (2, 3)]


# -------------------------------------------------------- articulation points
def test_articulation_points_joining_vertices(S):
    """TRI2: removing 2 splits {0,1} | {3,4,5}; removing 3 splits
    {0,1,2} | {4,5}. Both ends of the joining edge are cut vertices
    (verified by removal + component counting)."""
    assert S.articulation_points(TRI2) == [2, 3]


def test_articulation_points_shared_vertex_bowtie(S):
    """Bowtie centre 2: only node touching both triangles."""
    assert S.articulation_points(BOWTIE) == [2]


def test_articulation_points_cycle_has_none(S):
    """No cut vertices in a 2-vertex-connected cycle."""
    assert S.articulation_points(CYCLE5) == []


def test_articulation_points_root_special_case(S):
    """The root's rule is genuinely different: root = AP iff >= 2 tree
    children, NOT the low-link test. 4-cycle 0-1-2-3-0: DFS at 0 gets
    2 tree children (1 and 3), but the cycle edge 2-3 lets them
    bypass behind 0 -> 0 is NOT a cut vertex. Both verified by removal."""
    cycle = [[1, 3], [0, 2], [1, 3], [2, 0]]
    assert S.articulation_points(cycle) == []
    # triangle 0-1-2 with pendant 3 on 0: root 0 has 2 children AND the
    # pendant 3 has no bypass -> 0 IS a cut vertex (the only one).
    pendant = [[1, 2, 3], [0, 2], [1, 0], [0]]
    assert S.articulation_points(pendant) == [0]


# ------------------------------------------------------------------ 2-SAT
SAT1 = [(1, 2), (-1, 3), (-2, -3), (1, -3)]
UNIT = [(1, 1), (-1, -1)]
CHAIN = [(1, 2), (-1, 2), (1, -2), (-1, -2)]


def test_two_sat_satisfiable_fixture(S):
    """(x1 OR x2) AND (NOT x1 OR x3) AND (NOT x2 OR NOT x3)
    AND (x1 OR NOT x3). SAT (verified by 2^3 enumeration). The test
    asserts satisfiability and re-checks the returned assignment
    against ALL clauses -- it does NOT pin one specific assignment."""
    sat, assignment = S.two_sat(SAT1, 3)
    assert sat is True
    assert assignment is not None and len(assignment) == 3
    for a, b in SAT1:
        va = assignment[a - 1] if a > 0 else not assignment[-a - 1]
        vb = assignment[b - 1] if b > 0 else not assignment[-b - 1]
        assert va or vb, f"clause ({a}, {b}) violated by {assignment}"


def test_two_sat_unsat_unit_pair(S):
    """(x1) AND (NOT x1): x and -x in one SCC -- the textbook UNSAT."""
    sat, assignment = S.two_sat(UNIT, 1)
    assert sat is False
    assert assignment is None


def test_two_sat_unsat_implication_chain(S):
    """All four combinations of x1, x2 as clauses: (x1 OR x2),
    (NOT x1 OR x2), (x1 OR NOT x2), (NOT x1 OR NOT x2) -- every
    assignment falsifies one. Verified by enumeration: UNSAT."""
    sat, assignment = S.two_sat(CHAIN, 2)
    assert sat is False
    assert assignment is None


def test_two_sat_cross_checked_against_enumeration(S):
    """Differential: SCC-based decision must agree with full 2^n
    enumeration, and any witness it returns must satisfy all clauses.
    30 seeded random instances."""
    for seed in range(30):
        rng = random.Random(100 + seed)
        nv = rng.randint(3, 4)
        clauses = []
        for _ in range(rng.randint(4, 10)):
            a = rng.randint(1, nv) * rng.choice([1, -1])
            b = rng.randint(1, nv) * rng.choice([1, -1])
            clauses.append((a, b))
        # brute-force truth
        truth = False
        outer = None
        for bits in itertools_product(nv):
            if all(((bits[abs(a) - 1] if a > 0 else not bits[abs(a) - 1]) or
                    (bits[abs(b) - 1] if b > 0 else not bits[abs(b) - 1]))
                   for a, b in clauses):
                truth, outer = True, bits
                break
        sat, assignment = S.two_sat(clauses, nv)
        assert sat is truth, f"seed {seed}: {clauses}"
        if sat:
            for a, b in clauses:
                va = assignment[abs(a) - 1] if a > 0 else not assignment[abs(a) - 1]
                vb = assignment[abs(b) - 1] if b > 0 else not assignment[abs(b) - 1]
                assert va or vb, f"seed {seed}: witness violates ({a}, {b})"


def itertools_product(nv):
    """2^nv boolean tuples via integers (avoids importing itertools
    just for the enumeration oracle in the test above)."""
    for mask in range(1 << nv):
        yield [bool(mask >> i & 1) for i in range(nv)]
