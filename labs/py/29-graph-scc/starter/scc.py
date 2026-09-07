"""Lab 29 starter — SCC, bridges, articulation points, 2-SAT.

Pure stdlib. Implement every function; the tests run against this file
by default (pass --solution to check the reference).

`graph` means an adjacency list `list[list[int]]`. For the SCC
functions it is DIRECTED (bucket order is the out-edge order, and the
tests pin it). For bridges/articulation_points it is UNDIRECTED: every
edge must appear in BOTH endpoints' buckets — a self-loop appears twice
in its own bucket. All functions must handle disconnected inputs and
isolated vertices.

Prefer ITERATIVE DFS (explicit stacks). Recursive Tarjan dies at
Python's ~1000-frame recursion limit on graphs a few thousand nodes
deep — a classic production footgun the tests for Lab 26 already
warned about.
"""


def tarjan_scc(graph):
    """All SCCs of a directed graph in ONE DFS pass.

    Maintains discovery times, low-link values and a component stack of
    "open" vertices. A vertex finishes as the ROOT of an SCC exactly
    when low[v] == disc[v].

    Returns list of SCCs, each sorted ascending, the list itself sorted
    — deterministic, and IDENTICAL to kosaraju_scc's output.
    """
    raise NotImplementedError


def kosaraju_scc(graph):
    """All SCCs of a directed graph in TWO passes.

    Pass 1: DFS over G recording postorder (finish times). Pass 2:
    DFS over the TRANSPOSE, visiting roots in DECREASING finish order —
    each second-pass tree is exactly one SCC.

    Returns list of SCCs, each sorted ascending, the list itself sorted
    — deterministic, and IDENTICAL to tarjan_scc's output.
    """
    raise NotImplementedError


def bridges(graph):
    """Bridges (cut edges) of an UNDIRECTED graph via low-link DFS.

    Tree edge (p, v) is a bridge iff low[v] > disc[p]: v's subtree has
    no way back except through that edge. Skip the tree edge to your
    parent exactly ONCE (a parallel duplicate of it is a real back
    edge); ignore self-loops.

    Returns sorted list of normalized (min(u, v), max(u, v)) tuples.
    """
    raise NotImplementedError


def articulation_points(graph):
    """Cut vertices of an UNDIRECTED graph via low-link DFS.

    DFS root: cut vertex iff it has >= 2 tree children. Every other
    vertex p: cut vertex iff some DFS child v has low[v] >= disc[p].
    The root's rule is genuinely different — know both.

    Returns a sorted list of vertices.
    """
    raise NotImplementedError


def two_sat(clauses, n_vars):
    """2-SAT via implication graph + SCC condensation.

    clauses: list of (a, b) pairs of NONZERO ints; a negative literal
    means negation; variable x is numbered 1..n_vars. Each clause
    (a OR b) adds directed edges (not-a -> b) and (not-b -> a) to the
    implication graph over 2*n_vars literal-nodes.

    UNSAT iff some x and -x land in the same SCC -> (False, None).
    Otherwise assign from component order: x is True iff comp(x) comes
    strictly after comp(-x) in the condensation's topological order —
    then every edge out of a true literal ends at a true literal, which
    is exactly what "every clause satisfied" means on this graph.

    Returns (satisfiable: bool, assignment: list[bool] | None) where
    assignment[i] is the value of variable i+1.
    """
    raise NotImplementedError
