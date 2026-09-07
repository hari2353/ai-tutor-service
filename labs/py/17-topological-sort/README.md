# Lab 17: Topological Sort

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p17-topological-sort`

**You will build:** both toposort algorithms — Kahn's (BFS, in-degree counting) and DFS postorder with cycle detection — plus the five problems that are secretly toposort: course schedule (feasibility + order), build order from dependency pairs, the alien dictionary, and minimum semesters with parallel scheduling.

**You will be able to answer:** *"Your build tool must schedule 500 targets with dependencies — walk me through toposort, cycle detection, and what BFS vs DFS toposort buys you."*

## Setup

```bash
cd labs/py/17-topological-sort
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`kahns_toposort(n, edges)`** — nodes `0..n-1`, edges `(a, b)` meaning a→b (a before b). Return a valid order, or `None` on a cycle. Deterministic: when several nodes have in-degree 0, pop the **smallest id first** (use a sorted structure, not a set).
2. **`dfs_toposort(n, edges)`** — DFS postorder reversed; must detect cycles (three-colour marking) and return `None` on a cycle. Same determinism contract.
3. **`course_schedule(n, prerequisites)`** — `prerequisites` are `[b, a]` pairs (to take b you need a first): return the valid order or `None`.
4. **`build_order(projects, dependencies)`** — projects by name, dependencies `(before, after)`; return names in build order or `None`. Unknown project in a dependency → `ValueError`.
5. **`alien_dictionary(words)`** — sorted words imply a character order; extract it via toposort. Return `""` when the order is undecidable (contradiction like ["abc","ab"] prefix violation, or no unique first-chars information). All characters in the result must appear; the result must be consistent with every adjacent word pair.
6. **`min_semesters(n, relations)`** — courses 1..n, `relations` `(prev, next)`; take any number of parallel-safe courses per semester → minimum number of semesters (level-by-level Kahn's). Cycle → `None`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Lexicographically smallest toposort** — pop a real priority queue instead of FIFO; articulate where build systems do exactly this (alphabetical determinism in Bazel).
2. **All topological orders** — count them with DP over bitmask (n ≤ 20); which real system enumerates orders and why (build-system reproducibility audits)?
3. **Cycle reporting** — return one concrete cycle (not just `None`) using the DFS stack; this is what `cargo` and `pip` actually print.
4. **Incremental re-ordering** — add an edge without a full re-sort; when is the incremental check O(1) vs O(V+E)?
