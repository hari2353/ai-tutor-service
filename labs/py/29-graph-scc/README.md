# Lab 29: SCC, Bridges, Articulation Points, 2-SAT

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-graph-scc`

**You will build:** Tarjan's and Kosaraju's SCC decomposition, bridges and articulation points via low-link DFS, and 2-SAT via the implication-graph + SCC condensation — all in one `scc.py`, pure stdlib, iterative DFS only.

**You will be able to answer:** *"Implement Tarjan and tell me exactly what the low-link value means — then why does the same low-link machinery find bridges and cut vertices, and how does 2-SAT turn out to be an SCC problem in disguise?"*

## Setup

```bash
cd labs/py/29-graph-scc
python -m venv .venv && .venv\Scripts\activate    # or: uv venv
pip install pytest
```

## The spec

`graph` means an adjacency list `list[list[int]]`. Directed for the SCC functions (bucket order is the out-edge order — the tests pin it); UNDIRECTED for `bridges`/`articulation_points`: every edge appears in BOTH endpoints' buckets, a self-loop twice in its own. All functions handle disconnected inputs and isolated vertices. Never mutate the input.

1. **`tarjan_scc(graph)`** — ONE DFS pass with discovery times, low-links, and a component stack of "open" vertices. A vertex is the root of a complete SCC exactly when `low[v] == disc[v]`. Returns list of SCCs, each sorted ascending, the list itself sorted — deterministic, and byte-identical to `kosaraju_scc`'s output.
2. **`kosaraju_scc(graph)`** — TWO passes: DFS on `G` recording finish order, then DFS on the transpose visiting roots in DECREASING finish order; each second-pass tree is one SCC. Same canonical return form as (1).
3. **`bridges(graph)`** — low-link DFS over the undirected graph. Tree edge `(p, v)` is a bridge iff `low[v] > disc[p]`. Skip the tree edge to your parent exactly ONCE (a parallel duplicate of it is a real back edge — a doubled edge is never a bridge); ignore self-loops. Returns sorted `(min(u, v), max(u, v))` tuples.
4. **`articulation_points(graph)`** — same DFS, different test: root of the DFS tree is a cut vertex iff it has **≥ 2 tree children**; any other vertex `p` is a cut vertex iff some child `v` has `low[v] >= disc[p]`. The root's rule is genuinely different — know both. Returns a sorted list.
5. **`two_sat(clauses, n_vars)`** — clauses are `(a, b)` pairs of NONZERO ints (`|a| <= n_vars`, negative = negation, variable x is `1..n_vars`). Build the implication graph: each clause adds edges `(not-a -> b)` and `(not-b -> a)` over `2*n_vars` literal-nodes. **Unsatisfiable iff some x and -x share an SCC** → return `(False, None)`. Otherwise assign from the condensation's topological order: x is True iff `comp(x)` comes strictly AFTER `comp(-x)` — every edge out of a true literal then ends at a true literal, which is exactly what "all clauses satisfied" means. Returns `(satisfiable, assignment)` with `assignment[i]` = value of variable `i+1`.
6. **Iterative DFS everywhere.** Recursive Tarjan dies at Python's ~1000-frame recursion limit on graphs a few thousand nodes deep — the tests include a 5000-node path, and that is a feature, not harassment.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Condensation topological order for free** — Tarjan emits SCCs in reverse topological order of the condensation; exploit it to skip the Kahn pass in `two_sat` and argue why the "later component wins" assignment still works. *(Interview: "why does component order give a valid assignment at all?")*
2. **Online bridges** — recompute bridges after each of a sequence of edge insertions; find the case where one insertion kills many bridges at once. *(Interview: "static one-shot vs dynamic connectivity — what actually changes?")*
3. **2-SAT with implications across variables** — model a real constraint shape (e.g. feature-flag conflict resolution or round-robin scheduling "each team plays Saturday OR Sunday") and name which literals the constraints become. *(Interview: "when is a constraint problem secretly 2-SAT, and when is it 3-SAT and therefore hopeless?")*
4. **Gabow's algorithm** — a less-known single-pass SCC alternative with a simpler stack invariant; verify it matches Tarjan everywhere. *(Interview: "name a Tarjan alternative and its advantage.")*
