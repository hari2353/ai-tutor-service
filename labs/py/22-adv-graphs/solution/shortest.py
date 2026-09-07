"""Shortest-path algorithms from scratch: Dijkstra, Bellman-Ford, Floyd-Warshall, A*."""
import heapq
import math


def dijkstra(graph, src):
    for u in graph:
        for v, w in graph[u]:
            if w < 0:
                raise ValueError(f"negative edge {u}->{v} ({w})")
    # include nodes that appear only as neighbors
    nodes = set(graph)
    for u in graph:
        for v, _ in graph[u]:
            nodes.add(v)
    nodes.add(src)
    dist = {n: math.inf for n in nodes}
    dist[src] = 0
    heap = [(0, src)]
    done = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in done or d > dist[u]:
            continue
        done.add(u)
        for v, w in graph.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


def bellman_ford(graph, src):
    nodes = set(graph)
    edges = []
    for u in graph:
        for v, w in graph[u]:
            nodes.add(v)
            edges.append((u, v, w))
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
    has_neg = False
    for u, v, w in edges:
        if dist[u] != math.inf and dist[u] + w < dist[v]:
            has_neg = True
            break
    return dist, has_neg


def floyd_warshall(graph):
    nodes = set(graph)
    for u in graph:
        for v, _ in graph[u]:
            nodes.add(v)
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


def a_star(grid, start, goal, heuristic):
    rows, cols = len(grid), len(grid[0])

    def nbrs(cell):
        r, c = cell
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0:
                yield (nr, nc)

    g = {start: 0}
    f = {start: heuristic(start, goal)}
    heap = [(f[start], 0, start)]
    came = {}
    done = set()
    while heap:
        _, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == goal:
            path = [u]
            while u in came:
                u = came[u]
                path.append(u)
            return path[::-1], g[goal]
        for v in nbrs(u):
            ng = g[u] + 1
            if ng < g.get(v, math.inf):
                g[v] = ng
                came[v] = u
                heapq.heappush(heap, (ng + heuristic(v, goal), ng, v))
    return None, math.inf
