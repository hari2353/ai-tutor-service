# Lab 30: Graphs in the Wild — Resolvers, GraphRAG, PageRank, Build Pipelines

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-graph-applied`

**You will build:** a mini pip-style package resolver with version constraints, a GraphRAG two-hop query engine, PageRank power iteration, and a Bazel-style critical-path analysis of a build DAG — all in one `applied.py`, pure stdlib.

**You will be able to answer:** *"A package manager resolves 'build order' with topological sort and 'which versions' with constraint solving — implement the first and a single-level slice of the second. Then: why does GraphRAG traverse when vector recall can't, why does PageRank's damping factor make power iteration converge, and why does Bazel report the critical path of your build?"*

## Setup

```bash
cd labs/py/30-graph-applied
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

1. **`resolve_packages(requests, available, available_deps=None) -> dict | None`** — a single-level package resolver. `available` maps `{name: [versions]}`, versions sorted ascending like `["1.0", "1.2", "2.0"]`. `requests` is a list of `(name, spec)` where spec is exact `"1.2"` or floor `">=1.0"`. `available_deps` maps `{(name, version): [(dep, dep_spec), ...]}` for the *chosen* version only. Topological processing (Kahn-style work queue): pick the **highest** installable version of each package satisfying **every** constraint accumulated so far (direct requests + every chosen dependent's requirement), add that version's own deps to the constraints, and return `None` if any package has no satisfying version. A request for a package not in `available`, or a dep naming an unknown package, is also a conflict (`None`). Any other operator (`<`, `<=`, `!=`, `~=`) must raise `ValueError` — unimplemented constraints are a bug, not a silent `None`. *Simplification to document: no backtracking (the version chosen is never revised) and single-level shared constraints — real pip/Cargo resolution is NP-hard in general.*
2. **`graph_rag_answer(entity_graph, query_path) -> list[str] | None`** — `entity_graph` is `{entity: [(related_entity, relation), ...]}`; `query_path` is an ordered entity list, e.g. `["python", "guido", "microsoft"]`. Walk it hop by hop: each consecutive pair must have a direct edge in that direction, and the answer is the chain of relations traversed, e.g. `["created_by", "works_at"]`. Any missing hop (or a `query_path` shorter than 2) returns `None` — this is exactly the "connect the dots across documents" query flat vector recall cannot answer.
3. **`pagerank(graph, damping=0.85, tol=1e-6, max_iter=100) -> dict[node, float]`** — power iteration on a directed adjacency dict `{u: [v, ...]}`. All nodes appearing as keys **or** targets get scores; every score starts at `1/N`. Each round: `new[p] = (1-d)/N + d·(Σ PR[q]/outdeg[q] over q→p) + d·(dangling_mass/N)`. Dangling nodes (outdeg 0) redistribute their mass uniformly to everyone. Stop after `max_iter` rounds or when `Σ|new - old| < tol`; scores sum to ≈ 1.
4. **`critical_path_dag(nodes, durations, deps) -> (list, int | float)`** — the longest node-weighted path in a DAG. `durations` is `{node: weight}`, `deps` a list of `(before, after)` meaning *before must finish before after starts*. Topological order (Kahn), then a longest-to-here DP with parent pointers; reconstruct the actual path (list of nodes, start→end order) and return `(path, total_length)`. Nodes not on the path never appear in it (a disconnected island cannot win unless it alone is longest). A cycle must raise `ValueError`.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Backtracking resolver** — when a later constraint invalidates an already-chosen version, un-chosen it and try the next highest instead of returning `None`. Find a fixture where the lab resolver says `None` but backtracking finds a plan. *(Interview: "why is real package resolution NP-hard and what does PubGrub/Resolvelib do about it?")*
2. **Personalized PageRank** — replace the uniform `(1-d)/N` jump with a jump distribution concentrated on one seed node; verify it ranks the seed's neighborhood highest. *(Interview: "design 'people you may know' with PageRank")*
3. **k-hop GraphRAG with relevance pruning** — expand to *any* path of ≤ k hops between two entities, keep only the N most relevant relations, and cap total expansion — then explain what breaks without the cap. *(Interview: "your multi-hop retrieval pulls in garbage — diagnose it")*
4. **Cycle reporting** — make `critical_path_dag` report *which* nodes form the cycle (three-color DFS on the leftover subgraph), not just raise. *(Interview: "report the actual cycle, not 'a cycle exists'")*
