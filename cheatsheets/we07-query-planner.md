# Parse→Plan→Cost→Execute, Join Algorithms, EXPLAIN ANALYZE

> Sprint weekend 7 · source: `curriculum/17-databases/04-query-planner.md`

```
PIPELINE     parse (AST) -> rewrite (expand views, flatten subqueries) ->
             plan enumeration (access methods, join algo, join order) ->
             cost estimation (stats-driven, NOT real data) -> execute

COST CONSTS  (Postgres defaults) seq_page_cost 1.0 · random_page_cost 4.0
             (lower to ~1.1-2.0 on SSD) · cpu_tuple_cost 0.01 ·
             cpu_operator_cost 0.0025

STATS        MCV list + histogram (equal-depth buckets) + null fraction +
             n_distinct, per column, refreshed by ANALYZE/autovacuum
             INDEPENDENCE ASSUMPTION: multiplies per-predicate selectivity ->
             wrong on correlated columns -> fix w/ CREATE STATISTICS (dependencies)

JOINS        nested loop:  O(N*M) or O(N log M) w/ index -> tiny/indexed inner
             hash join:    O(N+M), build hash on smaller side -> large unsorted
             merge join:   O(N+M) if pre-sorted, else + sort cost -> both sides
                           already sorted on join key (e.g. from index scans)

EXPLAIN ANALYZE  runs the query for REAL (DML side effects! wrap in txn+rollback
             to test safely) · reports ACTUAL rows/time next to ESTIMATED
             #1 SIGNAL: estimated vs actual rows diverge 10x+ at a node ->
             every decision ABOVE that node was made on a false premise
             Batches>1 on hash join = build side spilled to disk (check if
             the estimate predicted that or not)

GEQO         Postgres switches from exhaustive DP enumeration to a genetic
             algorithm past geqo_threshold (default 12 tables) -> no longer
             guaranteed optimal join order

FIX ORDER    1. EXPLAIN ANALYZE first, always
             2. estimate wrong? -> ANALYZE / extended stats / raise STATISTICS
                target on that column -- fix stats before adding indexes
             3. estimate right but no good access path? -> THEN add the index
             4. still slow? -> look at query shape (function-wrapped predicate
                defeating index use, unnecessary correlated subquery, SELECT *)
```
