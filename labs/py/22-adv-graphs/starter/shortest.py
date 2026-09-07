"""Shortest-path algorithms from scratch: Dijkstra, Bellman-Ford, Floyd-Warshall, A*.

Graph format: adjacency dict {node: [(neighbor, weight), ...]}.
Grid format: list of lists of 0/1 (1 = wall); moves are 4-directional, cost 1.
"""
import heapq


def dijkstra(graph, src):
    """Single-source shortest paths, non-negative weights.

    Returns {node: dist}. Raises ValueError if any edge weight is negative.
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
    """All-pairs shortest paths. graph: {node: [(nbr, w), ...]}.

    Returns a dict-of-dicts dist[u][v]; unreachable pairs are math.inf,
    the diagonal is 0.
    """
    raise NotImplementedError


def a_star(grid, start, goal, heuristic):
    """Shortest path on a 2D grid (list of lists, 1 = wall), 4-directional.

    heuristic(a, b) -> estimated cost. Optimal if admissible.
    Returns (path, cost): path is the list of (row, col) cells including
    start and goal, cost is the number of steps. Returns (None, inf) if
    unreachable.
    """
    raise NotImplementedError
