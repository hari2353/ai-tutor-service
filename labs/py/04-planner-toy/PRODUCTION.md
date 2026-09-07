# Production notes — query planners

## What you'd actually use

| Your piece | Real thing | What it adds over yours |
|---|---|---|
| `Table` + fake column stats | Postgres `pg_statistic` (MCV lists, equal-depth histograms, null fraction, `n_distinct`), refreshed by `ANALYZE`/autovacuum | real histograms skew-aware; MCV lists capture hot values your 1/ndistinct can't |
| `estimate_selectivity` (1/ndistinct, linear range) | Postgres `eqsel`/`selectivity` functions over histograms | handles skewed distributions, correlated MCVs; *wrong* on correlated columns until you create extended statistics |
| Plan dataclasses + render() | Postgres `EXPLAIN` plan trees; Spark Catalyst `LogicalPlan`/`PhysicalPlan` with `treeString` | costs, actual rows, buffers, loops per node; Spark's trees carry estimated stats *inside* the nodes |
| Rule-based `optimize()` | Postgres: bottom-up DP (Selinger 1979) + rewrite rules; **Catalyst** (the module's canonical rule-engine): pattern-match batch rewrites over immutable trees until fixpoint | enumerates join *orders*, not just algorithms; costs everything with one number |
| Index selection < 0.1 selectivity | Postgres index path costing (`random_page_cost` vs `seq_page_cost`) | it's a cost comparison, not a threshold — the threshold version is the teaching simplification |
| HashJoin vs NLJ on a budget flip | Postgres `work_mem` (default 4 MB): hash batches spill to disk (`Batches>1` in EXPLAIN) | multi-batch graceful spilling, not a binary choice; merge join as the third option |
| `execute()` proving row-equality | `EXPLAIN ANALYZE` — runs it, reports estimated vs actual per node | the estimated-vs-actual gap is the #1 diagnostic number in the whole discipline |

The systems to name in interviews: **Postgres planner** (Selinger-style cost-based DP up to `geqo_threshold`=12 tables, then a genetic algorithm — GEQO), **Spark Catalyst** (rule + cost-based optimization over immutable logical trees, plus adaptive execution), **Oracle/SQL Server** (mature cost-based optimizers with adaptive plans), **MySQL** (historically weaker, hence the hint culture: `USE INDEX`, `STRAIGHT_JOIN`).

## What the real ones add over yours

- **Join order search, not just join algorithm.** Your planner keeps the join order it's given; real planners enumerate all orders via dynamic programming, reusing partial-plan costs — the factorial-in-tables blowup is the whole reason GEQO exists.
- **One cost number, not rules.** "Selectivity < 0.1 → index" and "budget → hash" are two separate heuristics; production collapses *everything* (access method, join algo, memory, I/O pattern) into a single cost estimate per candidate plan and picks the min. Rules can contradict each other; a cost model arbitrates.
- **Estimates come from real data.** Your stats are hand-declared; production builds histograms from actual row samples, keeps them fresh (autovacuum ANALYZE), and reads the *estimated-vs-actual* gap to detect staleness — the `EXPLAIN ANALYZE` skill this lab's executor hints at.
- **Adaptive re-optimization.** Spark AQE / Snowflake re-plan mid-query when actual shuffle sizes differ from estimates — impossible in your one-shot optimizer, and the live answer to "stale statistics" in distributed engines.
- **Correlated columns.** `WHERE city='Boston' AND state='MA'` multiplies selectivities assuming independence; production (Postgres 10+) takes explicit `CREATE STATISTICS (dependencies)` — you declare the correlation, the planner doesn't discover it.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Actual rows 10x+ off from estimated at a scan node | stale stats, or correlated columns estimated as independent | `ANALYZE`; extended statistics; raise per-column `STATISTICS` target on the volatile column |
| Hash join turned catastrophic nested loop after data grew | underestimated filtered-side cardinality made NLJ look cheap | refresh stats; verify the *plan shape* changed on the second `EXPLAIN ANALYZE` |
| Hash join slow despite being chosen | build side spilled to disk (`Batches>1`) — estimate said it would fit | raise `work_mem` for the session, or fix the estimate that picked the build side |
| 15-table query plans slowly, picks a bad order | past `geqo_threshold` (12): genetic search, not exhaustive DP | restructure to reduce the effective table count; raise threshold for rare-but-critical queries |
| Plan flips unpredictably between runs | autovacuum refreshed stats, cost tie broke differently | raise statistics resolution on the volatile column; plan-stability tools as a last resort |
| Planner never uses your new index | its selectivity estimate says seq scan is cheaper — maybe *correctly* (low selectivity = index loses) | verify the estimate first; an index matching many rows is genuinely worse than a seq scan |

## The 3 questions an interviewer asks after you describe this

1. *"Why did the planner pick the wrong plan — isn't it the database's job to be right?"* — it picks the cheapest-*looking* plan from statistics that can be stale or structurally wrong (independence assumption on correlated columns). The plan is a bet on cardinalities; `EXPLAIN ANALYZE` is how you audit the bet.
2. *"When does nested loop beat hash join?"* — small outer side, or a selective index on the inner side: 5 rows × 50M-row indexed table beats building any hash table. Hash wins large-unsorted-equal-joins; merge wins when both sides arrive pre-sorted (skip the build entirely).
3. *"EXPLAIN ANALYZE on an UPDATE — safe?"* — NO: it *executes* the statement, side effects and all. Wrap in `BEGIN; EXPLAIN ANALYZE UPDATE ...; ROLLBACK;` — forgetting this is a real production incident.
