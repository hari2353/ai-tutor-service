"""Lab 27 -- which shortest-path algorithm when. Reference implementation.

Graph format: adjacency dict {node: [(neighbor, weight), ...]}.
"""
import heapq
import math
import time


# --------------------------------------------------------------------- helpers
def _nodes_and_edges(graph):
    nodes = set(graph)
    edges = []
    for u in graph:
        for v, w in graph[u]:
            nodes.add(v)
            edges.append((u, v, w))
    return nodes, edges


# ------------------------------------------------------------------ algorithms
def dijkstra(graph, src):
    """Single-source, non-negative weights. {node: dist}; ValueError on negatives."""
    for u in graph:
        for v, w in graph[u]:
            if w < 0:
                raise ValueError(f"negative edge {u}->{v} ({w})")
    nodes, _ = _nodes_and_edges(graph)
    nodes.add(src)
    dist = {n: math.inf for n in nodes}
    dist[src] = 0
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in graph.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


def bellman_ford(graph, src):
    """Relax all edges n-1 times. Returns (dist, has_negative_cycle_reachable)."""
    nodes, edges = _nodes_and_edges(graph)
    nodes.add(src)
    dist = {n: math.inf for n in nodes}
    dist[src] = 0
    for _ in range(max(0, len(nodes) - 1)):
        changed = False
        for u, v, w in edges:
            if dist[u] != math.inf and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                changed = True
        if not changed:
            break
    has_neg = any(dist[u] != math.inf and dist[u] + w < dist[v]
                  for u, v, w in edges)
    return dist, has_neg


def floyd_warshall(graph):
    """All-pairs. dict-of-dicts; unreachable = inf, diagonal = 0. Handles negative edges."""
    nodes, _ = _nodes_and_edges(graph)
    nodes = sorted(nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    dist = [[math.inf] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for u, nbrs in graph.items():
        for v, w in nbrs:
            dist[idx[u]][idx[v]] = min(dist[idx[u]][idx[v]], w)
    for k in range(n):
        dk = dist[k]
        for i in range(n):
            dik = dist[i][k]
            if dik == math.inf:
                continue
            di = dist[i]
            for j in range(n):
                alt = dik + dk[j]
                if alt < di[j]:
                    di[j] = alt
    return {nodes[i]: {nodes[j]: dist[i][j] for j in range(n)} for i in range(n)}


# ----------------------------------------------------------------- the model
def estimate_ops(algorithm, n, e):
    """Estimated op count. n = nodes, e = edges (e >= n-1 assumed for the
    heap-based bounds, so the log factor never bottoms out at a tiny V)."""
    n = max(n, 1)
    e = max(e, n - 1, 0)
    if algorithm == "dijkstra" or algorithm == "a-star":
        return e * math.log2(max(n, 2))
    if algorithm == "bellman-ford":
        return n * e
    if algorithm == "floyd-warshall":
        return n ** 3
    if algorithm == "johnson":
        return n * e + n * (e * math.log2(max(n, 2)))
    raise ValueError(f"unknown algorithm: {algorithm}")


# ---------------------------------------------------------------- the choice
def choose_algorithm(negative_weights=False, all_pairs=False, dense=False,
                     n=1000, heuristic_available=False):
    """Which algorithm when. Rules, in order (first match wins):

    1. negative_weights and all_pairs -> "johnson"
       One BF reweight + Dijkstra per node: V*E*log V, vs Floyd-Warshall's
       V^3. On anything sparse, Johnson wins; FW has no negative-edge story
       at scale anyway.
    2. negative_weights, single-source -> "bellman-ford"
       Dijkstra is wrong (not slow -- wrong) on negatives, and you get
       negative-cycle detection for free: the arbitrage/currency signal.
    3. all_pairs, n <= 500 -> "floyd-warshall"
       V^3 with dense matrices at 500 is ~1.25e8 -- done in well under a
       second, and the code is five lines with no heap. Simplicity wins
       at small n.
    4. all_pairs, n > 500 -> "johnson"
       Past ~500, V^3 stops being cute on sparse graphs. The n<=500 rule
       fires first, so large-n all-pairs lands here.
    5. heuristic_available, single-source, non-negative -> "a-star"
       An admissible heuristic only prunes Dijkstra's search -- it can
       never make it slower, and collapses the frontier on grids.
    6. otherwise -> "dijkstra"
       E*log V, the default when nothing special is going on.

    `dense` is deliberately not consulted: density changes the op-count
    comparison (FW looks better as E -> V^2) but never the choice. If it
    did, rule 3's threshold would just move -- it's the same information.
    """
    if negative_weights:
        return "johnson" if all_pairs else "bellman-ford"
    if all_pairs:
        return "floyd-warshall" if n <= 500 else "johnson"
    if heuristic_available:
        return "a-star"
    return "dijkstra"


# -------------------------------------------------------------- measurement
def compare_algorithms(graphs):
    """For each graph: node/edge counts, all-pairs op estimates for every
    candidate, and real measured seconds (time.perf_counter around actual
    runs -- every source for the single-source ones, once for FW)."""
    out = {}
    for name, g in graphs.items():
        nodes, edges = _nodes_and_edges(g)
        n, e = len(nodes), len(edges)
        ops = {
            "dijkstra": n * estimate_ops("dijkstra", n, e),
            "bellman-ford": n * estimate_ops("bellman-ford", n, e),
            "floyd-warshall": estimate_ops("floyd-warshall", n, e),
            "a-star": n * estimate_ops("a-star", n, e),
            "johnson": estimate_ops("johnson", n, e),
        }
        t0 = time.perf_counter()
        for s in nodes:
            dijkstra(g, s)
        t1 = time.perf_counter()
        for s in nodes:
            bellman_ford(g, s)
        t2 = time.perf_counter()
        floyd_warshall(g)
        t3 = time.perf_counter()
        out[name] = {
            "n": n,
            "e": e,
            "ops": ops,
            "ms": {
                "dijkstra": t1 - t0,
                "bellman-ford": t2 - t1,
                "floyd-warshall": t3 - t2,
            },
        }
    return out
