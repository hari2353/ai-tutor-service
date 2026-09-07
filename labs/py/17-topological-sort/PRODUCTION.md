# Production notes — topological sort

## Where toposort ships

- **Package managers** — pip/cargo/npm resolve dependency graphs to install order. Modern resolvers (PubGrub) run toposort-equivalent scheduling; unsatisfiable cycles are the daily bug report.
- **Build systems** — make/Bazel/Buck: the target graph is toposorted into an execution plan; Bazel uses the lexicographically-smallest order for reproducibility (your stretch goal). Kahn's enables *parallel* levels — exactly `min_semesters` — which is how build systems compute critical-path parallelism.
- **DB migrations** — Flyway/Liquibase/Alembic order migrations by dependencies; cycle = two migrations that need each other's tables.
- **Spreadsheets** — cell evaluation order is a toposort of the formula DAG; circular references are detected by the same three-colour DFS you wrote.
- **Type checking / dataflow** — SSA variable ordering in compilers, Apache Airflow/Dagster/Prefect task scheduling — all Kahn's with a scheduler behind it.

## Complexity table

| Algorithm | Time | Space | Buys you |
|---|---|---|---|
| Kahn's (BFS) | O(V+E) | O(V+E) | natural parallel levels (min_semesters), streaming cycle check |
| DFS postorder | O(V+E) | O(V) recursion | cycle *reporting* (the GRAY stack is the cycle), single-pass |
| Lexicographic variant | O((V+E) log V) | O(V) + heap | deterministic builds — what Bazel guarantees |
| Incremental edge add | O(V+E) worst | — | often O(path) in practice; build systems batch edges instead |

## The 3 questions an interviewer asks

1. *"Cycle — do you detect it before or during the sort?"* — Kahn's detects it implicitly (unprocessed nodes remain); DFS detects it the moment it re-enters a GRAY node and the stack *is* the cycle, which is why real tools use DFS for diagnostics and Kahn's for scheduling.
2. *"How do you maximize build parallelism?"* — level-by-level Kahn's (your `min_semesters`); the true critical path needs longest-path DP over the DAG instead.
3. *"Alien dictionary — why can't you just compare first characters?"* — first characters only order those specific letters; each adjacent word pair contributes at most one edge (the first differing position), and the rest of the constraints come from other pairs.
