"""Lab 30 solution — resolvers, GraphRAG, PageRank, critical path."""
from collections import defaultdict, deque


def _version_key(version):
    return tuple(int(p) for p in version.split("."))


def _satisfies(version, spec):
    if spec.startswith(">="):
        return _version_key(version) >= _version_key(spec[2:])
    if any(ch in spec for ch in "<>=!~^*"):
        raise ValueError(f"unsupported spec: {spec!r}")
    return _version_key(version) == _version_key(spec)


def resolve_packages(requests, available, available_deps=None):
    available_deps = available_deps or {}
    constraints = defaultdict(list)          # every spec each package must satisfy
    for name, spec in requests:
        constraints[name].append(spec)

    plan = {}
    queued = set()
    work = deque()
    for name, _ in requests:               # requested packages first
        if name not in queued:
            queued.add(name)
            work.append(name)

    while work:
        name = work.popleft()
        cands = [v for v in available.get(name, [])
                 if all(_satisfies(v, s) for s in constraints[name])]
        if not cands:
            return None                     # unknown name, or no version fits
        version = max(cands, key=_version_key)     # HIGHEST installable
        plan[name] = version
        for dep, spec in available_deps.get((name, version), []):
            constraints[dep].append(spec)
            if dep in plan:                 # chosen earlier — re-check
                if not _satisfies(plan[dep], spec):
                    return None
            elif dep not in queued:
                queued.add(dep)
                work.append(dep)
    return plan


def graph_rag_answer(entity_graph, query_path):
    if len(query_path) < 2:
        return None
    rels = []
    for cur, nxt in zip(query_path, query_path[1:]):
        rel = next((r for t, r in entity_graph.get(cur, []) if t == nxt), None)
        if rel is None:
            return None                     # broken hop — the chain doesn't exist
        rels.append(rel)
    return rels


def pagerank(graph, damping=0.85, tol=1e-6, max_iter=100):
    adj = {u: list(graph[u]) for u in graph}
    nodes = set(adj)
    for u in adj:
        nodes.update(adj[u])
    n = len(nodes)
    if n == 0:
        return {}

    out = {u: len(adj.get(u, [])) for u in nodes}
    pr = {u: 1.0 / n for u in nodes}
    for _ in range(max_iter):
        # dangling mass, spread uniformly — a sink must not swallow the graph
        dangling = sum(pr[u] for u in nodes if out[u] == 0)
        base = (1.0 - damping) / n + damping * dangling / n
        new = {u: base for u in nodes}
        for u in nodes:
            if out[u]:
                share = damping * pr[u] / out[u]
                for v in adj[u]:
                    new[v] += share
        diff = sum(abs(new[u] - pr[u]) for u in nodes)
        pr = new
        if diff < tol:
            break
    return pr


def critical_path_dag(nodes, durations, deps):
    nodes = list(nodes)
    if not nodes:
        return [], 0
    succ = {u: [] for u in nodes}
    indeg = {u: 0 for u in nodes}
    for before, after in deps:
        succ[before].append(after)
        indeg[after] += 1

    q = deque(u for u in nodes if indeg[u] == 0)
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(nodes):
        raise ValueError("cycle detected — not a DAG")

    best = {u: durations[u] for u in nodes}     # longest-to-here
    parent = {u: None for u in nodes}
    for u in order:                             # topo order => deps final
        for v in succ[u]:
            cand = best[u] + durations[v]
            if cand > best[v]:
                best[v] = cand
                parent[v] = u

    end = max(nodes, key=lambda u: best[u])
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path, best[end]
