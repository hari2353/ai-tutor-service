"""Lab 27 -- which shortest-path algorithm when. Fill in every TODO. Tests define done.

You re-implement the three classics compactly (Lab 22 let you build them
from scratch; here they are tools), then build the part interviewers actually
probe: the op-count model and the SELECTION logic.

Graph format: adjacency dict {node: [(neighbor, weight), ...]}.
Nodes that appear only as neighbors are still part of the graph.
"""
import heapq
import math
import time


def dijkstra(graph, src):
    """Single-source shortest paths, non-negative weights only.

    Returns {node: dist}. Raises ValueError on a negative edge -- feeding
    Dijkstra a graph it cannot handle must fail loud, never silent.
    Heap with lazy deletion: push duplicates, skip stale pops.
    """
    raise NotImplementedError


def bellman_ford(graph, src):
    """Relax every edge n-1 times. Returns (dist, has_negative_cycle).

    has_negative_cycle is True iff a negative cycle is REACHABLE from src
    (detected by a successful relaxation on pass n).
    """
    raise NotImplementedError


def floyd_warshall(graph):
    """All-pairs shortest paths. Returns dict-of-dicts dist[u][v];
    unreachable pairs are math.inf, the diagonal is 0.

    Handles negative edges (absent negative cycles) -- one more thing
    Dijkstra cannot do.
    """
    raise NotImplementedError


def estimate_ops(algorithm, n, e):
    """Estimated operation count -- the model behind every choice:

        dijkstra / a-star  ~ E*log2(V)   (for a-star, Dijkstra is the upper
                                          bound: an admissible heuristic only
                                          shrinks the search)
        bellman-ford       ~ V*E
        floyd-warshall     = V^3         (edge count is irrelevant)
        johnson            ~ V*E + V*(E*log2(V))   (one BF reweight pass
                                                    + V Dijkstra runs)

    Raises ValueError for any other algorithm name.
    log2(V) is taken as log2(max(n, 2)) so tiny graphs stay well-defined.
    """
    raise NotImplementedError


def choose_algorithm(negative_weights=False, all_pairs=False, dense=False,
                     n=1000, heuristic_available=False):
    """Which algorithm to reach for. First matching rule wins:

    1. negative_weights and all_pairs        -> "johnson"        (BF reweight + Dijkstra per node)
    2. negative_weights (single-source)      -> "bellman-ford"   (correct with negatives + detects cycles)
    3. all_pairs and n <= 500                 -> "floyd-warshall" (V^3 but heapless and dead simple)
    4. all_pairs and n > 500                  -> "johnson"       (V*E*log V beats V^3 on sparse)
    5. heuristic_available (single-source)    -> "a-star"         (Dijkstra + admissible heuristic)
    6. otherwise                              -> "dijkstra"      (E*log V -- the default)

    `dense` never changes the choice, on purpose: density moves the
    op-count comparison (floyd-warshall gets relatively better as E
    approaches V^2), but the rules above already encode everything
    density can tell you.
    """
    raise NotImplementedError


def compare_algorithms(graphs):
    """Compare the candidates on real graphs.

    graphs: {name: adjacency dict}. Returns {name: {
        "n":   node count,
        "e":   edge count,
        "ops": estimated op counts for the all-pairs workload, one entry per
               algorithm in ("dijkstra", "bellman-ford", "floyd-warshall",
               "a-star", "johnson"):
                 dijkstra / a-star  -> V runs of the single-source bound
                 bellman-ford       -> V runs of V*E
                 floyd-warshall     -> one call, V^3
                 johnson            -> one BF reweight + V Dijkstras
        "ms":  measured seconds via time.perf_counter around REAL runs of
              the algorithms implemented in this lab -- dijkstra and
              bellman-ford once per source, floyd_warshall once.
              No sleeping, no faking: the implementations do the work.
    }}
    """
    raise NotImplementedError
