# Parse→Plan→Cost→Execute, Join Algorithms, EXPLAIN ANALYZE

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.5h · **Prereqs:** `T17-mvcc-isolation`
> **Module id:** `T17-query-planner` · **Tags:** sprint, internals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A SQL query goes through parse (syntax → abstract tree), rewrite (expand views, apply rules), plan enumeration (generate candidate physical execution strategies), cost estimation (assign each candidate a number using table statistics), and only then execution — and the entire quality of the result depends on step four, because the planner picks the cheapest-*looking* plan, not the actually-cheapest one, and it's only as good as its statistics. The three join algorithms — nested loop, hash join, merge join — have different complexities and different sweet spots: nested loop wins when one side is tiny or well-indexed, hash join wins on large unsorted equi-joins, merge join wins when both sides are already sorted on the join key. `EXPLAIN ANALYZE` is how you catch the planner being wrong: it shows estimated rows next to actual rows at every node, and when those diverge by an order of magnitude or more, everything above that node in the plan tree is operating on wrong assumptions and the plan shape itself is usually wrong, not just its cost number.

## Why this gets asked

Because "the query is slow" is the single most common real-world debugging task a backend/database engineer faces, and most candidates can recite "add an index" without being able to read the one artifact — `EXPLAIN ANALYZE` output — that tells you whether an index would even help. The interviewer has spent hours staring at a plan where a hash join was silently downgraded to a catastrophic nested loop because a row estimate was off by 1000x, and wants to know if you'd notice the estimated-vs-actual gap before reaching for "just add an index" as a reflex.

---

## Lineage: past → present → future

**What came before.** Early database systems (System R, IBM, late 1970s) had to solve the problem of executing declarative SQL at all — the innovation wasn't just parsing, it was Selinger et al.'s 1979 cost-based optimizer, which introduced the idea that a query has *many* valid physical execution plans and the system should pick among them using an estimated cost model rather than executing the first plan a naive translation produces, or worse, forcing the programmer to specify the physical access path (as pre-relational systems required). Before cost-based optimization, "how do I get my data" was largely the programmer's job, embedded procedurally; the pain that killed this was that a schema or data-distribution change silently broke hand-tuned access paths, and it didn't scale to ad hoc queries nobody had hand-optimized in advance.

**Where it stands now.** Every mainstream relational database (Postgres, MySQL, Oracle, SQL Server) uses cost-based optimization built on table/column statistics (histograms, most-common-value lists, cardinality estimates), and the current consensus is that this works well for the common case but degrades predictably and badly when statistics are stale, when correlated columns are estimated as if independent (the classic "assume independence" flaw baked into most cost models), or when a query crosses a complexity threshold where the planner switches from exhaustive plan enumeration to heuristic/greedy search (Postgres's `join_collapse_limit`/`geqo_threshold`, default around 12 tables, beyond which it uses a genetic algorithm instead of exhaustive dynamic programming). The live disagreement is over how much manual intervention is acceptable: some teams treat query hints (forcing a specific join method or index) as a last resort that fights the optimizer and rots when data distributions shift; others (especially at very large scale, or on databases with historically weaker optimizers like early MySQL) treat explicit hints as a normal, necessary tool. What's actually deployed at scale: `ANALYZE`/statistics-refresh automation (autovacuum's analyze component in Postgres, `information_schema` stats jobs elsewhere) running continuously, extended statistics on correlated columns added explicitly where the independence assumption is known to be wrong, and `EXPLAIN ANALYZE`-driven tuning as the standard diagnostic loop rather than blind indexing.

**Where it's heading.** Learned cost models (using ML to predict cardinality/cost instead of histogram-based formulas) are an active research area with real prototypes (e.g., learned cardinality estimators outperforming classical histograms on correlated-column workloads in published benchmarks) but not yet the default in any mainstream production database — confidence: real research direction, low confidence on near-term default adoption given the operational risk of a black-box cost model you can't easily debug with `EXPLAIN`. Adaptive query execution (re-optimizing a plan mid-execution based on actual observed cardinalities rather than committing to the pre-computed plan for the whole query, as Spark SQL's AQE and some cloud warehouses do) is real and shipping in analytical/distributed systems, and is the most likely direction for traditional OLTP planners to eventually adopt in some form. Treat learned cost models as speculative and adaptive execution as a real, spreading pattern outside classic single-node OLTP planners specifically.

---

## Mental model

```
   SQL text
      │
      ▼
   ┌─────────┐   syntax check, build an
   │  PARSE  │   abstract syntax tree
   └────┬────┘
        ▼
   ┌─────────┐   expand views, apply rewrite
   │ REWRITE │   rules (e.g. flatten subqueries,
   └────┬────┘   substitute rule-defined views)
        ▼
   ┌───────────────────┐   enumerate candidate PHYSICAL
   │  PLAN ENUMERATION │   plans: which index? which join
   └─────────┬─────────┘   algorithm? which join order?
             ▼
   ┌───────────────────┐   assign each candidate a COST using
   │  COST ESTIMATION   │   table/column statistics (histograms,
   └─────────┬─────────┘   MCVs, row counts) -- NOT actual data
             ▼
       pick the plan with
       the LOWEST ESTIMATED cost
             │
             ▼
   ┌─────────┐   run the chosen plan against
   │ EXECUTE │   the REAL data
   └─────────┘

   EXPLAIN shows steps 3-4's OUTPUT (the chosen plan + its cost estimate).
   EXPLAIN ANALYZE additionally RUNS it and shows step 5's ACTUAL rows/time
   next to step 4's ESTIMATED rows -- the single most important diagnostic
   number in this whole pipeline is the ESTIMATED vs ACTUAL gap at each node.
```

---

## How it actually works

### The pipeline: parse, rewrite, plan enumeration, cost estimation, execution

1. **Parse.** The SQL text is tokenized and turned into an abstract syntax tree; this stage only checks syntax, not whether tables/columns exist or whether the query is semantically sensible.
2. **Rewrite (a.k.a. the rule-based/logical-rewrite stage).** Views get expanded inline, some subqueries get flattened into joins (a subquery in a `WHERE ... IN (SELECT ...)` can often be rewritten as a semi-join), and rule-defined transformations get applied. This stage is about producing an equivalent, simpler logical query, not yet choosing physical execution details.
3. **Plan enumeration.** The optimizer generates candidate physical plans: for each table, which access method (sequential scan vs. index scan vs. index-only scan), for each join, which algorithm (nested loop, hash, merge) and which order to join tables in. For N tables joined together, the number of possible join orders grows combinatorially (roughly factorial in the naive case), which is why every real planner uses dynamic programming to reuse partial-plan costs (Selinger-style) up to some table-count threshold, then falls back to heuristics/genetic search beyond it — Postgres's `geqo_threshold` defaults to 12 tables, beyond which it stops doing exhaustive dynamic-programming enumeration and switches to a genetic algorithm that doesn't guarantee finding the true optimum.
4. **Cost estimation.** Every candidate plan is assigned a cost using a model built from constants (Postgres defaults: `seq_page_cost = 1.0`, `random_page_cost = 4.0` — meaning a non-sequential page fetch is modeled as 4x more expensive than a sequential one, a ratio inherited from spinning-disk assumptions and worth lowering on SSD-backed storage; `cpu_tuple_cost = 0.01` per row processed) combined with cardinality estimates derived from table statistics. The plan with the lowest total estimated cost is chosen — critically, this is an *estimate*, computed without running the query, and its accuracy is entirely bounded by how good the underlying statistics are.
5. **Execution.** The chosen plan runs against the real data. Only at this point do actual row counts and actual timings exist — which is exactly what `EXPLAIN ANALYZE` captures by executing the query for real and reporting them alongside the original estimates.

### Statistics, histograms, and why bad estimates cause bad plans

The optimizer needs to estimate **selectivity** — what fraction of rows will match a predicate — for every filter and join condition, without actually scanning the table. It does this using statistics maintained per column (Postgres: `pg_statistic`, refreshed by `ANALYZE`, normally run automatically by autovacuum): a **most-common-values (MCV) list** with their frequencies, a **histogram** of the remaining value distribution (equal-depth buckets, so each bucket represents roughly the same number of rows), a **null fraction**, and a **distinct-value estimate** (`n_distinct`).

Two independent estimation failures cause most bad plans:

- **Stale statistics.** If a table has grown or its data distribution has shifted significantly since the last `ANALYZE` and autovacuum hasn't caught up, every selectivity estimate derived from it is wrong, sometimes by orders of magnitude, and the planner picks a plan that was reasonable for the old data shape and terrible for the current one.
- **The independence assumption.** Classic cost models estimate the selectivity of `WHERE city = 'Boston' AND state = 'MA'` by multiplying the individual selectivities of each predicate as if they were statistically independent — but they're strongly correlated (every Boston row is also an MA row), so the combined estimate is far too low, often by an order of magnitude, because the model double-counts the filtering effect. Postgres addresses this with **extended statistics** (`CREATE STATISTICS ... (dependencies, ndistinct) ON (col1, col2) FROM table`), which must be created explicitly — the planner does not detect correlated columns automatically.

The consequence chain is direct: bad selectivity estimate → bad cardinality estimate (predicted row count) → bad cost estimate for every plan built on top of that number → the optimizer picks a plan that would be correct for the *predicted* row count and is wrong for the *actual* one. This is why `EXPLAIN ANALYZE`'s estimated-vs-actual comparison is the single most diagnostic number in the whole system: a 10x+ divergence at a plan node means the planner's decision *above* that node was made on false premises, independent of what the cost numbers claim.

### The three join algorithms

| Algorithm | Mechanics | Complexity | Wins when |
|---|---|---|---|
| **Nested loop** | For each row in the outer table, scan (or index-probe) the inner table for matches | `O(N·M)` naive; `O(N log M)` if the inner side has a usable index on the join key | One side is small, or the inner side has a selective index on the join key — e.g. joining 5 rows against a 50-million-row indexed table is cheaper via nested loop + index probe than building any hash table |
| **Hash join** | Build a hash table on the smaller ("build") side keyed by the join column, then probe it with each row of the larger ("probe") side | `O(N + M)` (build + probe), plus the memory cost of holding the build side (or spilling to disk in batches if it doesn't fit in `work_mem`) | Neither side is pre-sorted, both are large, and it's an equality join — the default choice for large unsorted joins |
| **Merge join** | Both inputs must be sorted on the join key (via an index that provides that order, or an explicit sort step); walk both sorted streams in lockstep, advancing whichever side is behind | `O(N + M)` if both already sorted; `O(N log N + M log M)` if a sort must be added first | Both sides come out of index scans already producing rows in join-key order — skips the hash-table build entirely; the natural choice for two large pre-sorted streams, and for merging results that need to stay in sorted order for something downstream (e.g. a subsequent `ORDER BY` on the same key, or a merge-append across partitions) |

The planner picks among these per join in the plan, and cost estimation is exactly what decides — a hash join's estimated cost depends heavily on whether the build side is predicted to fit in `work_mem` (Postgres) without spilling, which in turn depends on the same cardinality estimate that can be wrong.

### Reading `EXPLAIN ANALYZE`, node by node

```
EXPLAIN (ANALYZE, BUFFERS) 
SELECT o.id, c.name
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending';

Hash Join  (cost=15.50..1245.32 rows=48 width=40) (actual time=0.312..18.902 rows=6104 loops=1)
  Hash Cond: (o.customer_id = c.id)
  ->  Seq Scan on orders o  (cost=0.00..1180.00 rows=48 width=12)
                            (actual time=0.021..14.223 rows=6104 loops=1)
        Filter: (status = 'pending'::text)
        Rows Removed by Filter: 43896
  ->  Hash  (cost=10.00..10.00 rows=440 width=36) (actual time=0.264..0.265 rows=440 loops=1)
        Buckets: 1024  Batches: 1  Memory Usage: 45kB
        ->  Seq Scan on customers c  (cost=0.00..10.00 rows=440 width=36)
                                     (actual time=0.008..0.112 rows=440 loops=1)
Planning Time: 0.412 ms
Execution Time: 19.501 ms
```

Reading this node by node, inside-out:

- `Seq Scan on orders o`: **estimated 48 rows, actual 6104 rows** — a ~127x underestimate. This is the root cause of everything above it. The planner filtered `status = 'pending'` and badly misjudged how selective that filter is, most likely stale statistics or an MCV list that doesn't reflect the current distribution of `status` values (e.g., a recent bulk status change that autovacuum's analyze hasn't caught up to yet).
- Because the planner believed only 48 rows would come out of that scan, it chose a **Hash Join** with `orders` as the *build* side — reasonable if 48 rows is correct (a tiny hash table), bad if the real number is 6104 (a much bigger hash table, though in this specific example still within `work_mem` since `Batches: 1` shows no disk spill occurred — a worse version of this same misestimate easily pushes `Batches` above 1, spilling the hash table to disk and adding real I/O the estimate never accounted for).
- The **top-level total estimated cost was 1245.32**, but actual execution time was 19.5ms for this specific data volume — the point isn't that this particular query is slow (it finished fine here), it's that the *estimate the optimizer used to choose this plan* was wrong by two orders of magnitude, and on a larger table or under different join partners, that same wrong estimate would have led the optimizer to choose nested loop instead of hash join, or the wrong join order entirely, with a much worse real outcome.
- `Rows Removed by Filter: 43896` confirms the underlying issue directly: the sequential scan read ~50,000 rows and threw away all but 6104 — the filter is far less selective than the planner assumed.

**The fix here is almost always statistics, not indexing**: run `ANALYZE orders`, and if `status` is a low-cardinality column whose distribution shifts over time (a queue-like table where most rows quickly move out of `pending`), increase the statistics target on that column (`ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;` then re-`ANALYZE`) so the MCV list tracks the real distribution more precisely, or consider a partial index (`CREATE INDEX ON orders (customer_id) WHERE status = 'pending'`) if pending orders are consistently a small, hot subset — but the size of that subset needs to be verified against actual data first, not assumed from the plan's original (wrong) estimate.

### Worked "why is this query slow" walkthrough

**Symptom:** a query that joins a large `events` table to a small `users` table by `user_id`, filtered on `events.created_at > now() - interval '7 days'`, took 200ms last month and now takes 8 seconds, with no code change.

**Step 1 — run `EXPLAIN (ANALYZE, BUFFERS)`, don't guess.** The plan shows a Nested Loop with `events` as the outer side, estimated 200 rows, actual 2.1 million rows.

**Step 2 — diagnose the estimate gap.** A 10,000x underestimate on the `created_at > ...` filter is the signal. Likely cause: the table has grown substantially (more rows now fall in "last 7 days" as write volume increased) and/or autovacuum's analyze hasn't run recently enough on this fast-growing table for the histogram to reflect current data density — check `pg_stat_user_tables.last_autoanalyze`.

**Step 3 — understand why the WRONG PLAN SHAPE resulted, not just that it's slow.** Because the planner believed only 200 rows would pass the filter, a nested loop (probe `users` per outer row) looked cheap. At the real 2.1 million rows, the nested loop is now doing 2.1 million probes into `users` — even with an index, that's 2.1 million index lookups instead of one hash-table build-and-probe over both sides. This is the mechanical reason a stale estimate causes an actually-different, much worse plan, not merely a "slightly off" cost number for the same plan.

**Step 4 — fix the root cause, verify with a second `EXPLAIN ANALYZE`.** Run `ANALYZE events` manually (don't wait for autovacuum's schedule), re-run `EXPLAIN ANALYZE` on the same query, confirm the planner now estimates a cardinality close to 2.1 million and switches to a Hash Join. If the table's growth is fast enough that stats go stale between autovacuum runs, lower `autovacuum_analyze_scale_factor` for this specific table so analyze triggers more frequently relative to its size, rather than accepting periodic multi-second query regressions as normal.

**Step 5 — confirm the actual fix, not just a plausible one.** Re-time the query. If it's still slow after the plan shape corrects, look for missing indexes on `created_at` or `user_id` next — but only after the statistics are current, because tuning indexes against a plan built on bad estimates optimizes for the wrong problem.

---

## Build it from scratch

A minimal cost-based join-order chooser between two join algorithms, demonstrating exactly how a cardinality misestimate flips the chosen plan — the shape of what an interviewer may ask you to reason through or sketch.

```python
# untested sketch
from dataclasses import dataclass

SEQ_PAGE_COST = 1.0
CPU_TUPLE_COST = 0.01
HASH_BUILD_COST_PER_ROW = 0.02   # simplified

@dataclass
class TableEstimate:
    name: str
    estimated_rows: int
    actual_rows: int   # only known at execution time; the planner never sees this

def nested_loop_cost(outer_rows: int, inner_rows: int, inner_indexed: bool) -> float:
    if inner_indexed:
        # O(N log M): outer rows times a cheap indexed probe
        import math
        return outer_rows * (CPU_TUPLE_COST + math.log2(max(inner_rows, 2)) * 0.005)
    return outer_rows * inner_rows * CPU_TUPLE_COST   # O(N*M), no index

def hash_join_cost(build_rows: int, probe_rows: int) -> float:
    build_cost = build_rows * HASH_BUILD_COST_PER_ROW
    probe_cost = probe_rows * CPU_TUPLE_COST
    return build_cost + probe_cost   # O(N+M)

def choose_plan(outer: TableEstimate, inner: TableEstimate, inner_indexed: bool):
    """Uses ESTIMATED rows, exactly like a real optimizer -- this is the
    mechanism by which a bad estimate produces a bad plan CHOICE, not just
    a wrong cost NUMBER for the same plan."""
    nl_cost = nested_loop_cost(outer.estimated_rows, inner.estimated_rows, inner_indexed)
    hj_cost = hash_join_cost(min(outer.estimated_rows, inner.estimated_rows),
                              max(outer.estimated_rows, inner.estimated_rows))
    chosen = "nested_loop" if nl_cost < hj_cost else "hash_join"

    # What ACTUALLY happens once real data flows through the chosen plan:
    if chosen == "nested_loop":
        real_cost = nested_loop_cost(outer.actual_rows, inner.actual_rows, inner_indexed)
    else:
        real_cost = hash_join_cost(min(outer.actual_rows, inner.actual_rows),
                                     max(outer.actual_rows, inner.actual_rows))

    return {
        "chosen_plan": chosen,
        "estimated_cost": min(nl_cost, hj_cost),
        "actual_cost_of_chosen_plan": real_cost,
    }

# Demonstration: planner thinks 200 rows pass a filter, reality is 2.1M --
# choose_plan(TableEstimate("events", estimated_rows=200, actual_rows=2_100_000),
#             TableEstimate("users", estimated_rows=440, actual_rows=440),
#             inner_indexed=True)
# picks nested_loop based on the 200-row estimate; actual_cost_of_chosen_plan
# reflects what 2.1M real nested-loop probes actually cost -- the same
# mechanical failure as the worked walkthrough above.
```

Full version wired to real Postgres `pg_stats`, merge-join cost modeling, and a side-by-side `EXPLAIN`-vs-actual diff tool: **`labs/py/04-planner-toy/`**.

---

## How it's done in production

**Postgres** — Selinger-style dynamic-programming plan enumeration up to `join_collapse_limit`/`geqo_threshold` (default 12 tables), beyond which it switches to a genetic algorithm (GEQO) that trades optimality for tractable planning time on very wide joins. Cost constants (`seq_page_cost`, `random_page_cost`, `cpu_tuple_cost`, `cpu_operator_cost`) are tunable per-deployment — lowering `random_page_cost` toward 1.0-1.5 on all-SSD storage is a common, real-world tuning step since the default 4.0 assumes spinning-disk-era random I/O penalties. **MySQL** — historically a weaker cost-based optimizer than Postgres's, with a longer history of needing explicit index hints (`USE INDEX`, `FORCE INDEX`) and `STRAIGHT_JOIN` to force join order in cases where the optimizer's estimate was known-wrong; has closed much of this gap in recent versions with a proper cost model and histogram support, but hint usage remains more common in MySQL shops than Postgres shops as a cultural/historical artifact. **Oracle / SQL Server** — both have mature cost-based optimizers with adaptive plan features (Oracle's Adaptive Query Optimization can actually change join method mid-execution if runtime statistics diverge sharply from the plan's assumptions, an early form of adaptive execution outside pure analytical engines). **Analytical/distributed engines** (Spark SQL, Snowflake, BigQuery) increasingly use **adaptive query execution** — re-optimizing shuffle/join strategy mid-query based on actual observed partition sizes rather than committing fully to the pre-execution estimate, directly addressing the estimate staleness problem this module is built around, at the cost of some re-planning overhead.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| `EXPLAIN ANALYZE` shows actual rows 10x+ higher (or lower) than estimated at a scan node | Stale statistics, or the independence assumption breaking down on correlated columns | Run `ANALYZE` on the table; for correlated columns, create extended statistics (`CREATE STATISTICS ... (dependencies) ON (colA, colB) FROM table`) |
| A join that used to be a hash join is now a catastrophic nested loop after data grew | Underestimated cardinality on the filtered side led the planner to (wrongly) believe a nested loop's outer side would be tiny | Refresh statistics; increase `default_statistics_target` or per-column `SET STATISTICS` on high-churn columns; verify with a second `EXPLAIN ANALYZE` |
| Hash join is slow despite `EXPLAIN` showing it as chosen | Build side spilled to disk (`Batches` > 1 in the plan output) because it didn't fit in `work_mem` — usually because the cardinality estimate for the build side was too low | Raise `work_mem` for the session/query, or fix the underlying cardinality estimate so the planner picks the smaller side as build correctly |
| Query plan changes unpredictably between otherwise-identical runs, or after a routine deploy with no query change | Autovacuum ran and updated statistics, shifting estimates just enough to flip the chosen plan across a cost tie; or a genuinely bimodal data distribution the histogram can't represent well | Increase statistics resolution (`STATISTICS` target) on the volatile column; consider a plan-stability tool (Oracle SQL Plan Baselines, or pg_hint_plan) only as a last resort |
| Merge join chosen but plan shows an explicit `Sort` node feeding it, and it's slower than a hash join would have been | Neither input was actually pre-sorted, so the planner paid `O(N log N)` to sort just to get merge join's `O(N+M)` merge step — sometimes still cheaper than hash join's memory cost, sometimes not, and a bad cardinality estimate on the sort input misjudges which | Verify the estimate feeding the sort-cost calculation; if sort cost was underestimated, this is the same root cause as the general estimate problem, not a merge-join-specific bug |
| A query with 15+ joined tables takes a surprisingly long time just to *plan*, or picks an obviously suboptimal join order | GEQO/genetic plan search engaged (Postgres default threshold: 12 tables) — no longer doing exhaustive dynamic programming | Consider `join_collapse_limit`/restructuring the query to reduce the effective join count, or explicitly hint join order for the specific known-good path if the genetic search consistently underperforms |

---

## Tradeoffs & when NOT to use it

- **Don't add an index as the first move on a slow query without running `EXPLAIN ANALYZE` first.** If the root cause is a stale-statistics-driven bad plan *shape* (wrong join algorithm, wrong join order), a new index can mask the symptom for a while and leave the actual fragility (stats going stale again) unaddressed, or simply not help at all if the planner doesn't choose to use it under its current (wrong) cost estimate.
- **Don't reach for query hints as a first resort.** Hints fight the optimizer permanently — they encode today's data distribution as a fixed decision that will silently become wrong as the data changes, with no mechanism to notice. Prefer fixing the underlying statistics/estimate problem; reserve hints for the rare case where the cost model itself has a known structural blind spot the specific query hits repeatedly.
- **Don't blanket-increase `default_statistics_target` cluster-wide as a reflex fix.** More histogram buckets means more work for `ANALYZE` and a larger `pg_statistic` for the planner to consult on every plan — tune it per-column where you've actually diagnosed an estimate problem, not everywhere.
- **Merge join is the wrong choice when neither input is naturally sorted and the data doesn't fit comfortably in memory for the sort** — paying an explicit sort just to enable a merge is often a worse deal than a hash join's build cost, and the planner's own cost comparison should already reflect this if statistics are accurate; if you're manually forcing merge join via a hint against the optimizer's choice, verify with `EXPLAIN ANALYZE` that it's actually faster, don't assume.
- **GEQO's genetic search past the table-count threshold trades correctness/optimality for planning speed** — for a very wide join query that runs rarely, it may be worth raising the threshold and paying more planning time for a better plan; for a query that runs constantly, the faster (possibly suboptimal) plan search may be the right tradeoff. This is a real, situational decision, not a universal default.
- **For a query executed once or rarely** (an ad hoc analytics query, a one-off migration script), spending effort tuning statistics or adding extended stats for it specifically is usually not worth it — accept a suboptimal plan for a one-time cost rather than optimizing a query that won't run again.

---

## Interview questions

### Q1 — Walk through the full pipeline a SQL query goes through before it executes.
**Testing:** baseline structural understanding.
**Answer:** Parse (syntax into an AST), rewrite (expand views, flatten subqueries, apply logical rewrite rules), plan enumeration (generate candidate physical plans — access methods, join algorithms, join order), cost estimation (assign each candidate a cost using table/column statistics), then execution of the chosen lowest-estimated-cost plan against real data.
**Follow-up trap:** *"At which stage does the optimizer actually look at real data?"* — none of the planning stages do; cost estimation uses statistics collected in advance (by `ANALYZE`), not the live table. Only execution touches real data, which is exactly why a stale-statistics estimate can be wrong without the planner ever "seeing" it's wrong until you run `EXPLAIN ANALYZE`.

### Q2 — Why does the planner sometimes pick a plan that's actually much worse than an alternative it considered and rejected?
**Answer:** Because it picks the plan with the lowest *estimated* cost, and that estimate is built from statistics that can be stale or structurally wrong (e.g., assuming independence between correlated columns). If the estimate underlying a candidate plan is significantly off, the optimizer is comparing wrong numbers and can easily choose the plan that looks cheaper on paper but is far more expensive in reality.
**Follow-up trap:** *"How do you find out this happened after the fact?"* — `EXPLAIN ANALYZE`, specifically comparing estimated rows to actual rows at each node; a large divergence at a node means the cost decisions built on top of that node's estimate were made on false premises.

### Q3 — Give the three join algorithms, their complexities, and when each wins.
**Answer:** Nested loop: `O(N·M)` naive or `O(N log M)` with an index on the inner side — wins when one side is small or well-indexed. Hash join: `O(N+M)` — build a hash table on the smaller side, probe with the larger; wins on large, unsorted equality joins. Merge join: `O(N+M)` if both sides are already sorted on the join key (else pay a sort first) — wins when both inputs come out of index scans already in join-key order, skipping the hash build entirely.
**Follow-up trap:** *"Both inputs to a merge join need an explicit sort added — is it still worth it over hash join?"* — depends on the cardinality estimate feeding both cost calculations; sometimes yes (if the sorted result is also useful for a subsequent `ORDER BY` or merge-append, amortizing the sort cost across more than just this join), sometimes no (if it's a one-off join with no other use for sortedness, hash join's `O(N+M)` with no sort step usually wins) — this is exactly the kind of decision a correct cost estimate should make automatically, and a wrong one gets wrong.

### Q4 — What statistics does the planner maintain per column, and how are they used?
**Answer:** A most-common-values (MCV) list with frequencies, a histogram of the remaining value distribution (equal-depth buckets), a null fraction, and a distinct-value count estimate. These feed selectivity estimation for filters and join conditions — the fraction of rows a predicate is expected to match — which in turn drives cardinality estimates for every plan node built on top of that predicate.
**Follow-up trap:** *"Your WHERE clause filters on two correlated columns and the estimate is way off — why?"* — classic cost models multiply each predicate's individual selectivity assuming independence; correlated columns (e.g. city and state) violate that assumption and the combined estimate ends up far too low. Fix with extended statistics (`CREATE STATISTICS ... (dependencies) ON (col1, col2)`) which the planner does not create automatically — you have to identify and declare the correlation yourself.

### Q5 — What's the single most important thing to look at in `EXPLAIN ANALYZE` output, and why?
**Testing:** the core diagnostic skill this module is built around.
**Answer:** The estimated-vs-actual row count at each plan node. A large divergence (commonly used rule of thumb: 10x or more) at any node means the plan decisions made above that node in the tree were based on a wrong premise, and that's usually a more direct explanation for why a query is slow than any individual cost number, because it tells you the plan *shape itself* is likely wrong, not just mis-costed.
**Follow-up trap:** *"You find a 5x divergence, not 10x — do you ignore it?"* — no fixed threshold is a hard rule; the right question is whether that divergence, propagated up through the rest of the plan, changed a plan choice (e.g. tipped a hash-vs-nested-loop decision) — check whether nodes above it also show large actual-time contributions, not just whether the ratio crosses an arbitrary cutoff.

### Q6 — A query's plan uses a nested loop join and it's extremely slow on a large table. What's your diagnostic process?
**Answer:** Run `EXPLAIN (ANALYZE, BUFFERS)`, check the estimated vs. actual rows on the outer side of the nested loop specifically — if actual rows are far higher than the planner assumed, that's why it chose nested loop (looked cheap for a small outer side) when a hash join would have been better for the real cardinality. Fix the root cause: refresh statistics (`ANALYZE`), check for correlated-column misestimation, verify autovacuum is keeping up with the table's write rate. Re-run `EXPLAIN ANALYZE` to confirm the plan shape actually changes, don't just add an index and hope.
**Follow-up trap:** *"You ran ANALYZE and the estimate is still wrong. What next?"* — check `default_statistics_target`/per-column `STATISTICS` setting (too few histogram buckets for a column with a genuinely complex distribution), check for column correlation needing extended statistics, and check whether the predicate itself is something the planner fundamentally can't estimate well (a function call on the column, e.g. `WHERE lower(email) = ...`, which defeats normal column statistics unless you create an expression index/statistics on that exact expression).

### Q7 — Why does Postgres's `random_page_cost` default to 4.0, and when should you change it?
**Answer:** It models a non-sequential (random) disk page fetch as 4x more expensive than a sequential one — a ratio appropriate for spinning-disk hardware where seek time dominates. On all-SSD storage, random and sequential access costs are much closer together, so a lower value (commonly 1.1-2.0) better reflects reality and makes the planner more willing to choose index scans (which rely on random access) over sequential scans where appropriate.
**Follow-up trap:** *"You lower random_page_cost and query plans across the whole database change. Is that always an improvement?"* — not automatically; it's a global tuning knob, so verify with `EXPLAIN ANALYZE` on representative queries that plans actually improved rather than assuming the theoretical hardware justification translates directly — a workload with a lot of full-table scans on genuinely large tables can still prefer sequential access regardless of the per-page cost ratio.

### Q8 — What is GEQO (or equivalent) and why does the planner need it?
**Answer:** For queries joining many tables, the number of possible join orders grows combinatorially, and exhaustive dynamic-programming plan enumeration (Selinger-style) becomes too expensive to run for every query. Postgres's `geqo_threshold` (default 12 tables) switches to a genetic algorithm beyond that point, trading a guarantee of finding the optimal join order for tractable planning time.
**Follow-up trap:** *"Does this mean wide-join queries always get a worse plan?"* — not necessarily worse in absolute terms, but no longer guaranteed optimal — for a frequently-run wide-join query, it can be worth restructuring the query (reducing the effective table count via subqueries/CTEs materialized separately) or raising the threshold and accepting slower planning for a better plan, depending on whether the query runs often enough that plan quality matters more than planning latency.

### Q9 — Explain hash join's "build" and "probe" sides and what happens when the build side doesn't fit in memory.
**Answer:** The build side (normally the smaller estimated input) is loaded into an in-memory hash table keyed on the join column; the probe side is then streamed through, looking up matches in that hash table. If the build side's actual size exceeds `work_mem`, Postgres splits both sides into multiple batches and processes them incrementally, spilling to disk — visible in `EXPLAIN ANALYZE` output as `Batches > 1`, which adds real I/O cost the original single-batch cost estimate didn't anticipate if the batching wasn't predicted.
**Follow-up trap:** *"EXPLAIN shows Batches: 4 — is that automatically a problem?"* — not automatically; if the estimate correctly predicted the batching need and costed it in, this can still be the cheapest available plan (better than nested loop or paying to sort both sides for a merge join). It's a problem specifically when the *estimate* assumed 1 batch and reality needed 4+ — that gap, not the batching itself, is the actionable signal.

### Q10 — How would you decide whether a slow query needs a new index, updated statistics, or a rewritten query?
**Testing:** synthesizing the whole diagnostic workflow, not just one technique.
**Answer:** Always start with `EXPLAIN ANALYZE`. If estimated vs. actual rows diverge sharply at a scan/filter node, fix statistics first (ANALYZE, extended stats, higher statistics target) — an index added on top of a bad estimate may not even get chosen, or may mask rather than fix the underlying fragility. If statistics are accurate and the plan is still slow because a needed access path genuinely doesn't exist (no index supports an efficient scan on the filtered/joined column), add the index — then re-run `EXPLAIN ANALYZE` to confirm the planner actually adopted it and the estimate/actual gap is now small. If both are fine and it's still slow, look at the query shape itself (an unnecessary correlated subquery re-executed per row, a function wrapped around an indexed column defeating index usage, an unnecessarily wide `SELECT *` forcing a heap fetch when an index-only scan was possible).
**Follow-up trap:** *"You add the 'obviously correct' index and the planner doesn't use it. Why?"* — check the cost estimate again: if the planner still believes (correctly or not) that a sequential scan is cheaper for the current selectivity estimate on that column, it won't switch, especially at low selectivity (a filter matching a large fraction of rows almost always costs more via an index scan's random I/O than a sequential scan, regardless of index availability) — verify the estimate justifies the index before assuming the planner is simply being obtuse.

### Q11 — What's the difference between `EXPLAIN` and `EXPLAIN ANALYZE`, and why is the difference itself important to understand, not just the syntax?
**Answer:** `EXPLAIN` alone shows the planner's chosen plan and its cost *estimates* without running the query. `EXPLAIN ANALYZE` actually executes the query (with real side effects for DML — a real operational hazard) and reports actual row counts and actual timing alongside the original estimates at every node, which is what makes the estimated-vs-actual comparison possible at all.
**Follow-up trap:** *"You want to check a slow UPDATE's plan without actually running the update against production. What do you do?"* — wrap it in a transaction and roll back (`BEGIN; EXPLAIN ANALYZE UPDATE ...; ROLLBACK;`), or test against a representative non-production copy — `EXPLAIN ANALYZE` on a DML statement genuinely executes it, and forgetting that is a real, embarrassing production incident waiting to happen.

### Q12 — A cloud data warehouse (Spark SQL / Snowflake / BigQuery) re-optimizes a query plan mid-execution. What problem is that solving, relative to a traditional single-node OLTP planner?
**Testing:** whether the candidate can connect the module's core problem (stale/wrong pre-execution estimates) to a different but related architectural answer.
**Answer:** Adaptive query execution directly targets the estimate-staleness problem this whole module is about: instead of committing fully to a plan chosen from pre-execution estimates and living with the consequences if those estimates are wrong, the engine observes actual intermediate result sizes (e.g., actual shuffle partition sizes after the first join stage) and can re-optimize the remaining query — switching join strategy, repartitioning, or changing join order for the stages not yet executed — based on ground truth rather than a stale guess.
**Follow-up trap:** *"Why hasn't this become standard in traditional single-node OLTP planners like Postgres?"* — OLTP queries are typically short, high-frequency, and latency-sensitive at the millisecond level, where the overhead of runtime re-planning is proportionally much more expensive relative to total query cost than in a long-running analytical query processing terabytes across a distributed cluster; the cost/benefit of adaptive execution is much more favorable for long analytical queries than short transactional ones, which is why it emerged there first.

---

## Red flags that fail you

- Adding an index as the first response to "the query is slow" without looking at `EXPLAIN ANALYZE` first.
- Not knowing the difference between `EXPLAIN` and `EXPLAIN ANALYZE`, or not knowing `EXPLAIN ANALYZE` actually executes the query.
- Being unable to state a complexity for any of the three join algorithms.
- Assuming statistics update automatically and instantly on every write, rather than via `ANALYZE`/autovacuum on a schedule.
- Not knowing that column correlation breaks the independence assumption cost models rely on.
- Reaching for query hints before checking whether the underlying statistics are simply stale.
- Treating a plan's estimated cost number as if it were a measured, real cost.

---

## Cheat card

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

## Sources

- [PostgreSQL: Documentation: 14.1. Using EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) — accessed 2026-07-26
- [PostgreSQL: Documentation: How the Planner Uses Statistics](https://www.postgresql.org/docs/current/planner-stats-details.html) — accessed 2026-07-26
- [The Basics of Postgres Query Planning — pganalyze](https://pganalyze.com/docs/explain/basics-of-postgres-query-planning) — accessed 2026-07-26
- [Tuning random_page_cost and how index correlation affects query plans — pganalyze](https://pganalyze.com/blog/5mins-postgres-tuning-random-page-cost) — accessed 2026-07-26
- [PostgreSQL EXPLAIN – What Are the Query Costs? — DZone](https://dzone.com/articles/postgresql-explain-what-are-the-query-costs) — accessed 2026-07-26
- [JOIN Algorithms — Arpit Bhayani](https://arpitbhayani.me/blogs/join-algorithms/) — accessed 2026-07-26
- [PostgreSQL Join Optimization: Nested Loop, Hash, and Merge — Philip McClarence](https://medium.com/@philmcc/postgresql-join-optimization-nested-loop-hash-and-merge-c87b86373908) — accessed 2026-07-26
- [PostgreSQL 17 Performance Tuning: Understanding Estimates vs. Actuals in Query Plans — Jeyaram Ayyalusamy](https://medium.com/@jramcloud1/29-postgresql-17-performance-tuning-understanding-estimates-vs-actuals-in-query-plans-91e7eccbc51a) — accessed 2026-07-26
- [Debug PostgreSQL query latency faster with EXPLAIN ANALYZE — Datadog](https://www.datadoghq.com/blog/database-monitoring-explain-analyze/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
