# Production notes — cost-based planning

## What you'd actually use

| System | Optimizer | Search cap | Escape hatch |
|---|---|---|---|
| PostgreSQL | Selinger DP over statistics | `geqo_threshold` (default 12) → genetic search | `pg_hint_plan`, `STRAIGHT_JOIN`-style hints via extensions |
| MySQL | Cost-based + histograms (8.0+) | weaker for years; hints culturally common | `USE INDEX` / `FORCE INDEX` |
| SQL Server / Oracle | mature CBOs with adaptive plan switching | — | plan guides / SQL Plan Baselines |
| Spark SQL, Snowflake, BigQuery | adaptive: re-optimize mid-flight from actual partition sizes | — | AQE is the pattern to watch |

**Do not hand-tune plans before checking statistics.** The fix order is EXPLAIN ANALYZE → ANALYZE/extended stats → new index → rewrite. Hints come last and rot.

## What the real ones add over yours

- **Real cardinality estimation** — MCV lists, equal-depth histograms, null fractions, `n_distinct`; yours just multiplies selectivities (independence assumption).
- **Extended statistics** (`CREATE STATISTICS ... (dependencies)`) for correlated columns your model cannot see.
- **Memory awareness** — hash joins spill to disk in batches when the build side exceeds `work_mem` (`Batches > 1` in EXPLAIN ANALYZE); your model has no memory concept.
- **Index integration** — an index scan both changes the scan cost AND delivers rows pre-sorted, enabling merge join for free. Your toy fakes that with `Relation.sorted_key`.
- **Parallelism & I/O weights** — `seq_page_cost=1.0` vs `random_page_cost=4.0` (lower to ~1.1–2.0 on SSD), per-tuple CPU costs.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Actual rows 10x+ off the estimate | stale statistics or correlated columns under independence | `ANALYZE`; extended statistics on the correlated pair |
| Hash join downgraded to catastrophic nested loop after data grew | underestimated filtered side made NL look cheap | refresh stats; verify with a second EXPLAIN ANALYZE before adding indexes |
| Merge join chosen but a Sort node feeds it | sort-to-enable costed cheaper than hash build — sometimes right, often a misestimate behind it | check the estimate feeding the Sort; compare against forced hash join |
| Plan flips between deploys without query changes | autovacuum refreshed stats and crossed a cost tie | raise stats resolution on volatile columns; plan baselines if stability matters |
| Planning itself takes seconds on 15+ tables | GEQO/genetic search engaged past the threshold | restructure the query, or raise the threshold and pay planning time |

## The 3 questions an interviewer asks after you sketch this

1. *"Where does the optimizer touch real data?"* — nowhere until execution; every number above EXECUTE is an estimate built from `ANALYZE`-maintained statistics.
2. *"Estimated rows are off by 100x at one node — what do you do?"* — read upward from it: every decision above that node was made on false premises; fix the estimate source first.
3. *"Why does your planner only consider left-deep orders?"* — search-space control: left-deep keeps DP polynomial-ish and matches pipelined execution; Postgres goes bushy up to ~12 tables, then trades optimality for tractability with GEQO.
