# Window Functions, Recursive CTEs, Lateral Joins, Gaps-and-Islands + 40-Question SQL Bank

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 3h · **Prereqs:** `T17-query-planner`, `T17-index-design` · **Updated:** 2026-08-02
> **Module id:** `T17-sql-mastery` · **Tags:** sql
> **Practice:** the Problems tab in the app — 30 curated LeetCode SQL problems (joins, aggregation, subqueries, window functions, gaps-and-islands, Nth-highest, recursive/hierarchy queries)

## The 30-second version

Roughly seven recurring shapes cover the overwhelming majority of SQL asked in real interviews: filter-and-aggregate, conditional joins, top-N-per-group, period-over-period change (LAG/LEAD), gap-and-island sessionization, deduplication keeping the latest record, and hierarchy traversal via recursive CTE or self-join. Master the mechanics of window functions (the `OVER (PARTITION BY ... ORDER BY ...)` frame, and the distinction between `ROW_NUMBER`/`RANK`/`DENSE_RANK`), recursive CTEs (anchor member, recursive member, `UNION ALL`, and the termination condition that isn't optional), `LATERAL`/`CROSS APPLY` (a subquery that can reference columns from the row currently being processed, which a plain correlated subquery in `WHERE` cannot do as flexibly for row-producing logic), and gaps-and-islands (the `row_number() - row_number()` trick that turns "find consecutive runs" into a groupable constant), and you can derive a correct answer to nearly anything asked live, even a shape you haven't memorized. The senior signal isn't syntax recall — it's reading `EXPLAIN ANALYZE`, knowing which of two logically-equivalent queries the planner will execute faster and why, and catching a subtly wrong `GROUP BY` or window frame before it ships a silent data bug.

## Why this gets asked

Because SQL is the one skill almost every engineering role still requires at some depth, and it's uniquely easy to fake at a shallow level — anyone can write a `JOIN` and a `WHERE` clause. The interviewer wants to know if you can reach for window functions instead of a self-join-and-group-by contortion, whether you understand *why* a recursive CTE needs an explicit termination condition (they've debugged a runaway recursive query that ate a connection pool), and whether you can read a query plan and explain in plain language why a seemingly reasonable query is doing a sequential scan when it should be using an index. At staff level, they're also testing whether you can spot a subtly incorrect aggregation — a `COUNT(DISTINCT x)` that silently changed the semantics of a report — because that's the failure mode that doesn't throw an error, it just quietly produces the wrong number that someone makes a business decision on.

---

## Lineage: past → present → future

**What came before.** Before window functions were standardized in SQL:2003 (and before that, uniquely available in Oracle from the mid-1990s and standardized industry-wide only over the following decade as other engines caught up), computing something like "rank within each group" or "running total" required self-joins against aggregated subqueries, or correlated subqueries executed once per row — both correct but painfully slow and hard to read, because the engine had no native concept of "compute this value with visibility into a window of related rows without collapsing them into groups." The specific pain: a report needing "each customer's rank by spend within their region" required joining the table against a pre-aggregated ranking subquery, which meant maintaining two logical passes over the data by hand, in SQL text, when the actual computation is naturally a single pass with a sliding window — this mismatch between what the query needed to express and what the language could express directly is exactly what window functions were introduced to close.

**Where it stands now.** Window functions, recursive CTEs, and `LATERAL`/`CROSS APPLY` are now broadly supported across PostgreSQL, MySQL (8.0+), SQL Server, Oracle, and most modern analytical engines (Snowflake, BigQuery, ClickHouse) — the syntax has largely converged, though real differences remain (MySQL's `LATERAL` support and recursive CTE performance historically lagged Postgres and SQL Server; ClickHouse's window function support is real but its optimizer handles some patterns differently given its column-store, MergeTree-oriented execution model). The live disagreement in practice isn't about the SQL standard itself but about *where the logic should live* — whether transformations belong in SQL (in the warehouse, via dbt-style modeling) or in application/orchestration code upstream of the database. The dbt-driven "SQL as the transformation layer" movement (roughly 2018 onward, now thoroughly mainstream in data engineering) pushed hard toward doing more in SQL, precisely because window functions and CTEs made complex transformations expressible and testable directly in the query layer rather than in brittle procedural ETL code.

**Where it's heading.** Two real, current threads: first, LLM-assisted SQL generation (text-to-SQL) has gotten good enough that a growing share of *first-draft* analytical queries are AI-generated, which shifts the human skill demand toward *reading and verifying* a generated query's correctness (catching a wrong join cardinality, a silently incorrect window frame) rather than writing from a blank page — this is a genuine, ongoing shift in what "SQL skill" means day to day, though hand-writing complex CTEs and window logic remains the interview bar because it's the only reliable way to test whether a candidate can catch what an LLM got wrong. Second, semantic/metrics layers (dbt's semantic layer, Cube, and similar) are increasingly interposed between raw SQL and consumption, aiming to define a metric once and generate consistent SQL from it — treat this as a maturing but not yet universal practice; most interview-relevant SQL is still hand-written against raw or lightly-modeled tables.

---

## Mental model

Window functions execute in a specific, fixed logical order relative to the rest of the query — getting this order wrong is the single most common source of "why can't I filter on this window function result" confusion:

```
  LOGICAL QUERY EXECUTION ORDER (not the order you TYPE the clauses in)

  1. FROM / JOIN        — build the working row set
  2. WHERE               — filter rows (window functions NOT yet computed, can't reference them)
  3. GROUP BY            — aggregate into groups
  4. HAVING              — filter groups
  5. WINDOW FUNCTIONS     — computed here, AFTER grouping, using each row's frame
  6. SELECT               — pick/compute final columns
  7. DISTINCT             — dedupe
  8. ORDER BY              — sort (CAN reference window function results/aliases)
  9. LIMIT / OFFSET        — page

  → to filter on a window function's result, you MUST wrap it: use a CTE or
    subquery, then filter in an outer WHERE — you cannot use it directly in
    the same query's WHERE or HAVING, because at that point it doesn't exist yet.
```

This single ordering fact explains why `WHERE row_num = 1` fails right after computing `ROW_NUMBER() OVER (...)` in the same `SELECT`, and why the fix is always "wrap it in a CTE and filter the CTE's output."

---

## How it actually works

### 1. Window functions — the frame is the whole story

```sql
SELECT
  customer_id,
  order_date,
  amount,
  SUM(amount) OVER (
    PARTITION BY customer_id
    ORDER BY order_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total,
  RANK() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS spend_rank
FROM orders;
```

`PARTITION BY` resets the window per group (like a `GROUP BY` that doesn't collapse rows). `ORDER BY` inside `OVER` defines the row's position for ranking/offset functions and the default frame. The **frame clause** (`ROWS BETWEEN ... AND ...`) controls exactly which rows are visible to the aggregate at each row — omit it and the default is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` when an `ORDER BY` is present, which is a common silent-bug source: `RANGE` groups peer rows with equal `ORDER BY` values together (all rows sharing the same date get the same running total, which is usually *not* what "running total" is supposed to mean) while `ROWS` strictly counts physical rows regardless of ties. **Always use `ROWS` explicitly for running totals unless you specifically want tie-peer grouping.**

`ROW_NUMBER()` vs `RANK()` vs `DENSE_RANK()` — the interview staple: given ties (two rows with amount=100 both ranked #1), `ROW_NUMBER()` arbitrarily breaks the tie and assigns 1, 2 (never ties, not deterministic without a fully-specifying `ORDER BY`), `RANK()` assigns 1, 1, then skips to 3 for the next distinct value, `DENSE_RANK()` assigns 1, 1, then 2 with no gap. Getting these backwards is the single most common SQL-interview mistake.

### 2. Recursive CTEs — anchor, recurse, terminate

```sql
WITH RECURSIVE org_chart AS (
  -- anchor member: the base case, runs once
  SELECT employee_id, manager_id, name, 1 AS depth
  FROM employees
  WHERE manager_id IS NULL          -- the root(s)

  UNION ALL

  -- recursive member: joins back to the CTE's own (growing) result set
  SELECT e.employee_id, e.manager_id, e.name, oc.depth + 1
  FROM employees e
  JOIN org_chart oc ON e.manager_id = oc.employee_id
  WHERE oc.depth < 50                -- explicit safety cap — NOT optional in production
)
SELECT * FROM org_chart ORDER BY depth, employee_id;
```

Execution model: the anchor runs once, producing the initial working set; the recursive member then runs repeatedly, each iteration joining against *only the rows produced by the previous iteration* (not the whole accumulated result), appending new rows to the final output, until an iteration produces zero new rows — that's the natural termination. **The termination condition isn't automatic if your data has a cycle** (a corrupted `manager_id` pointing in a loop) — without an explicit depth cap or a cycle-detection clause (`UNION` instead of `UNION ALL` deduplicates but doesn't prevent infinite recursion on a true cycle in most engines; PostgreSQL 14+ has explicit `CYCLE` clause support), a cyclic graph produces an infinite loop that will eventually hit `max_recursion` limits (SQL Server defaults to 100, configurable) or exhaust memory/time in engines without a hard default. Always cap depth explicitly in production recursive CTEs regardless of whether you believe the data is acyclic.

### 3. LATERAL / CROSS APPLY — a subquery with access to the current row

```sql
-- Top 3 most recent orders PER customer — a correlated "top-N per group" that
-- a plain JOIN + window function can also solve, but LATERAL is often clearer
-- and, in some engines, lets the planner push the LIMIT down per-group.
SELECT c.customer_id, c.name, o.order_id, o.order_date, o.amount
FROM customers c
CROSS JOIN LATERAL (
  SELECT order_id, order_date, amount
  FROM orders o
  WHERE o.customer_id = c.customer_id      -- references the OUTER row — this is
  ORDER BY order_date DESC                  -- exactly what a plain subquery in
  LIMIT 3                                    -- FROM cannot do
) o;
-- SQL Server / older MySQL: CROSS APPLY instead of CROSS JOIN LATERAL
```

The defining feature: a `LATERAL` subquery (or `CROSS APPLY`) can reference columns from tables that appear *earlier in the same FROM clause* — a plain subquery in `FROM` is evaluated once, independent of any other table, and cannot see `c.customer_id`. This is precisely the "top-N per group" pattern and is frequently cleaner than the window-function-plus-outer-filter alternative, especially when N>1 rows per group are needed with additional per-row logic beyond a simple rank filter.

### 4. Gaps-and-islands — the row-number-minus-row-number trick

```sql
-- Find consecutive-day login streaks per user
WITH numbered AS (
  SELECT user_id, login_date,
         ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date) AS rn
  FROM (SELECT DISTINCT user_id, login_date FROM logins) d
),
islands AS (
  SELECT user_id, login_date,
         login_date - (rn * INTERVAL '1 day') AS island_key   -- constant WITHIN a streak
  FROM numbered
)
SELECT user_id, MIN(login_date) AS streak_start, MAX(login_date) AS streak_end,
       COUNT(*) AS streak_length
FROM islands
GROUP BY user_id, island_key
ORDER BY user_id, streak_start;
```

The mechanism: within any unbroken run of consecutive dates, `login_date - rn` (subtracting the row's sequential position, scaled to the same unit) produces the *same constant value* for every row in that run — because both `login_date` and `rn` increase by exactly 1 per row within a consecutive run, their difference is invariant. The moment there's a gap, `rn` still increments by 1 but `login_date` jumps by more than 1 day, so the difference changes, creating a new group. `GROUP BY` on that constant then cleanly separates each island. This same trick generalizes beyond dates to any ordered numeric sequence (finding runs of consecutive IDs, consecutive integers in a sequence with missing values, etc.) — the ordering column and the "step size" are the only things that change.

### 5. Deduplication keeping the latest record

```sql
-- Keep only the most recent row per (customer_id, email) — a very common
-- real-world cleanup after an upsert bug or a slowly-changing-dimension load
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY customer_id, email ORDER BY updated_at DESC, id DESC
  ) AS rn
  FROM customer_records
)
DELETE FROM customer_records
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
```

The `id DESC` tiebreaker in `ORDER BY` matters and is a common interview gotcha: without a fully-deterministic ordering, ties on `updated_at` mean `ROW_NUMBER()` picks an arbitrary row, and re-running the query can (in principle, engine-dependent) keep a *different* row each time — always add a tiebreaker column (a monotonic ID, typically) to make dedup logic deterministic and idempotent.

### 6. Period-over-period change — LAG/LEAD

```sql
SELECT
  product_id, month,
  revenue,
  LAG(revenue) OVER (PARTITION BY product_id ORDER BY month) AS prev_month_revenue,
  revenue - LAG(revenue) OVER (PARTITION BY product_id ORDER BY month) AS mom_change,
  ROUND(
    100.0 * (revenue - LAG(revenue) OVER (PARTITION BY product_id ORDER BY month))
    / NULLIF(LAG(revenue) OVER (PARTITION BY product_id ORDER BY month), 0), 1
  ) AS mom_pct_change
FROM monthly_revenue;
```

`LAG`/`LEAD` fetch a value from N rows before/after the current row within the same partition/order — the classic pitfall is dividing by a `LAG` value that's zero or `NULL` (a product with no revenue the prior month), which is why `NULLIF(..., 0)` guards the division rather than letting it throw or silently produce `NULL`/error depending on engine.

---

## Build it from scratch

A worked, non-trivial combination — sessionize page-view events into sessions with a 30-minute inactivity gap, then rank sessions per user by duration — chains several of the patterns above and is a realistic "prove you can compose these" interview task:

```sql
WITH events AS (
  SELECT user_id, event_time,
         LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) AS prev_time
  FROM page_views
),
session_starts AS (
  SELECT *,
    CASE WHEN prev_time IS NULL
              OR event_time - prev_time > INTERVAL '30 minutes'
         THEN 1 ELSE 0 END AS is_new_session
  FROM events
),
sessions AS (
  SELECT *,
    SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY event_time
                               ROWS UNBOUNDED PRECEDING) AS session_id
  FROM session_starts
),
session_summary AS (
  SELECT user_id, session_id,
         MIN(event_time) AS session_start, MAX(event_time) AS session_end,
         COUNT(*) AS events_in_session,
         MAX(event_time) - MIN(event_time) AS duration
  FROM sessions
  GROUP BY user_id, session_id
)
SELECT *,
  RANK() OVER (PARTITION BY user_id ORDER BY duration DESC) AS session_rank
FROM session_summary
ORDER BY user_id, session_rank;
```

This is gaps-and-islands (session boundary detection via a running sum flag) composed with a running window (`SUM ... ROWS UNBOUNDED PRECEDING` as a cumulative session counter) composed with top-N-per-group (`RANK` in the final `SELECT`) — three of the seven canonical patterns in one query, which is exactly the kind of composition a staff-level SQL round tests.

---

## How it's done in production

**Reading `EXPLAIN ANALYZE`** is the production skill underneath all of this — a logically correct query can still be catastrophically slow, and the interview (and the job) rewards being able to say why. Key things to check, PostgreSQL terms (concepts transfer, syntax varies): `Seq Scan` on a large table where an index should apply (missing or unused index — check if a function wraps the column, defeating a plain index), `Nested Loop` with a high row-count inner side (should usually be a `Hash Join` for large-large joins — a bad row-count estimate from stale statistics is the usual cause), a large gap between `estimated rows` and `actual rows` (stale statistics; `ANALYZE` the table), and a `Sort` step consuming significant time before a window function (add an index matching the `PARTITION BY`/`ORDER BY` to let the engine avoid an explicit sort).

**Window function performance:** an index on `(partition_columns..., order_column)` lets the engine compute the window using the index's existing order instead of an explicit sort step — for a large table with a hot window-function query, this is frequently the single highest-leverage index to add, more impactful than indexing individual filter columns.

**Recursive CTE performance in production:** deep or wide hierarchies (a 20-level org chart with thousands of nodes per level) can be slow because each iteration typically can't leverage an index as effectively as a flat join — for genuinely large, frequently-queried hierarchies, materialized closure tables (precomputed ancestor-descendant pairs, refreshed on write) or nested-set/path-enumeration models often outperform a live recursive CTE at read time, trading write-time complexity for read-time speed. Know this tradeoff by name even if the interview only asks for the recursive CTE itself.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `column "row_num" does not exist` or similar when filtering on a window function result | Window functions compute after `WHERE`/`HAVING` in logical execution order | Wrap in a CTE/subquery, filter in the outer query |
| Running total repeats the same value across several rows sharing a date | Default frame is `RANGE`, which groups ORDER BY peers together | Use explicit `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` |
| Dedup query keeps a different "latest" row on every run | `ORDER BY` in the window has no deterministic tiebreaker | Add a monotonic tiebreaker column (id DESC) after the primary sort key |
| Recursive CTE runs forever / hits an engine's recursion limit | Cyclic data (corrupted parent reference) with no depth cap | Add an explicit `WHERE depth < N` guard in the recursive member |
| Query plan shows `Seq Scan` despite an index existing on the filtered column | A function wraps the column in the predicate (`WHERE lower(email) = ...`), defeating a plain btree index | Functional index matching the exact expression, or rewrite the predicate |
| Window function query is slow at scale despite correct logic | No index matching `PARTITION BY`/`ORDER BY`, forcing an explicit sort per partition | Add a composite index on `(partition_cols, order_col)` |
| `GROUP BY` query silently drops rows compared to expected count | An inner `JOIN` instead of `LEFT JOIN` silently excludes rows with no match | Use `LEFT JOIN` when the "zero matches" case should still appear, verify row counts before/after |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a recursive CTE for a shallow, bounded hierarchy** (a fixed 3-level category tree) — a handful of explicit self-joins is often more readable and lets the planner optimize each join independently, whereas a recursive CTE's iterative execution model can be harder for the optimizer to reason about for small, fixed depths.
- **LATERAL/CROSS APPLY isn't always faster than a window-function-plus-filter approach** — for simple top-1-per-group (not top-N with N>1), `ROW_NUMBER() OVER (...) = 1` in a CTE is often just as fast and more idiomatic; reach for `LATERAL` specifically when you need N>1 rows per group or per-row logic a window function alone can't express (e.g., a correlated aggregate that itself needs a `LIMIT`).
- **Gaps-and-islands via `row_number() - row_number()` assumes no duplicate rows in the ordering column** for a given partition — deduplicate first (as shown in pattern 5) or the row-number arithmetic silently produces wrong groupings.
- **Don't do heavy multi-stage transformation logic in a single monolithic query "because it's more efficient."** A single 200-line query with eight nested CTEs is often less maintainable and no faster than the equivalent broken into a few well-named views or staged tables (a materialized intermediate step), especially once several people need to debug or modify it — readability and testability are real engineering costs, not just style preferences.
- **Recursive CTEs and deep window-function queries can both be genuinely wrong choices at very large scale** where a purpose-built graph database (for hierarchy/path-finding at scale) or a precomputed materialized structure outperforms recomputing the traversal or the window on every query — know when "just write better SQL" stops being the right lever and a different storage model is warranted.

---

## Interview questions

### Q1 — Write a query to find each employee's rank by salary within their department, handling ties correctly.
**Testing:** RANK vs DENSE_RANK vs ROW_NUMBER, and whether they ask which tie-handling is wanted rather than assuming.
**Answer:** `SELECT *, RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS dept_rank FROM employees;` — `RANK()` if ties should share a rank and skip the next number (1,1,3), `DENSE_RANK()` if ties should share a rank with no gap (1,1,2), `ROW_NUMBER()` if every row needs a unique, arbitrarily tie-broken number (1,2,3). State explicitly which the business question implies before picking one.
**Follow-up trap:** *"Now filter to only the top earner per department."* — this requires wrapping in a CTE, since the window function result can't be filtered in the same query's WHERE: `WITH ranked AS (...) SELECT * FROM ranked WHERE dept_rank = 1;`

### Q2 — Explain why `WHERE row_number() OVER (...) = 1` fails, and how you'd fix it.
**Testing:** logical execution order.
**Answer:** Window functions are computed after `WHERE` and `GROUP BY`/`HAVING` in SQL's logical execution order, so at the point `WHERE` is evaluated, the window function's result doesn't exist yet to filter on. Fix: compute the window function in a CTE or subquery, then filter on it in the outer query's `WHERE`.
**Follow-up trap:** *"Could you use HAVING instead?"* — no, `HAVING` filters after `GROUP BY` but still before window functions are computed in the standard logical order; the same wrap-in-a-CTE fix applies regardless of which clause you'd otherwise try to use.

### Q3 — Write a recursive CTE to find all descendants of a given employee in an org chart, and explain how you'd prevent infinite recursion on bad data.
**Testing:** the anchor/recurse/terminate mechanics plus production safety awareness.
**Answer:** Anchor selects the given employee; recursive member joins `employees e ON e.manager_id = cte.employee_id` to walk downward, `UNION ALL`-ing each new level. To prevent infinite recursion on a cyclic `manager_id` reference (corrupted data), add an explicit `WHERE depth < N` guard in the recursive member, or in PostgreSQL 14+, use the standard `CYCLE` clause to detect and stop on a repeated node.
**Follow-up trap:** *"Your recursive CTE is slow on a 10,000-node, 20-level-deep hierarchy queried frequently. What do you do?"* — a live recursive CTE recomputes the traversal every query; for a large, frequently-read hierarchy, a materialized closure table (precomputed ancestor-descendant pairs, refreshed on write) trades write-time complexity for much faster reads, since it turns the query into a simple indexed lookup instead of iterative recursion.

### Q4 — What's the difference between `ROWS BETWEEN` and `RANGE BETWEEN` in a window frame, and why does it matter for a running total?
**Testing:** the specific, commonly-missed frame-default bug.
**Answer:** `ROWS` counts physical rows regardless of value ties; `RANGE` groups rows with equal `ORDER BY` values together as peers, computing the same result for all of them. The default frame when `ORDER BY` is present but no frame is specified is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — for a running total by date, this means every row sharing the same date gets the *same* cumulative total (including that date's full sum), not a true row-by-row running total, which is a silent correctness bug most people don't notice until numbers don't add up downstream.
**Follow-up trap:** *"Give an example where you'd actually want RANGE instead of ROWS."* — a "cumulative distinct dates seen so far" style calculation where you specifically want all same-day events treated as one step rather than N separate steps — RANGE is correct when peer rows genuinely represent the same logical position, not distinct sequential positions.

### Q5 — Write a query to find the 3 most recent orders for every customer.
**Testing:** top-N-per-group, and whether they reach for LATERAL or a window function appropriately.
**Answer:** Two valid approaches: `LATERAL`/`CROSS APPLY` (`SELECT c.*, o.* FROM customers c CROSS JOIN LATERAL (SELECT * FROM orders WHERE customer_id = c.customer_id ORDER BY order_date DESC LIMIT 3) o`), or a window function wrapped in a CTE (`WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) rn FROM orders) SELECT * FROM ranked WHERE rn <= 3`). Both are correct; `LATERAL` can let some optimizers push the `LIMIT` down per customer group rather than ranking the entire table first, which can matter at scale.
**Follow-up trap:** *"Which one would you actually check the query plan for before deciding?"* — always the window-function version on a very large table, since `ROW_NUMBER()` over the whole table before filtering can be more work than a `LATERAL` subquery that limits per-group early — say you'd verify with `EXPLAIN ANALYZE` rather than assuming one is always faster, since it's genuinely engine- and data-distribution-dependent.

### Q6 — Solve gaps-and-islands: find the longest streak of consecutive days each user was active.
**Testing:** the row_number-minus-row_number trick, mechanically.
**Answer:** `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY activity_date)` gives each row a sequential position; `activity_date - (row_number * INTERVAL '1 day')` is constant within any unbroken consecutive run (both increase by 1 per row within a run) and changes at every gap. `GROUP BY user_id, that_constant` isolates each island; `COUNT(*)` per group gives streak length, then rank/order to find the longest.
**Follow-up trap:** *"What breaks this if there are duplicate activity_date rows per user?"* — the row-number arithmetic assumes exactly one row per date per user; duplicates throw off the sequential numbering and produce wrong island boundaries. Deduplicate (`SELECT DISTINCT user_id, activity_date` first) before applying the technique.

### Q7 — Deduplicate a table keeping only the most recently updated row per natural key, and explain the tiebreaker gotcha.
**Testing:** deterministic ordering awareness.
**Answer:** `WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY natural_key ORDER BY updated_at DESC, id DESC) rn FROM t) DELETE FROM t WHERE id IN (SELECT id FROM ranked WHERE rn > 1)`. The `id DESC` tiebreaker matters because if two rows share the exact same `updated_at`, `ROW_NUMBER()` without a fully deterministic ordering can pick an arbitrary one, and — in principle, engine-dependent — a different one on a re-run, making the dedup non-idempotent.
**Follow-up trap:** *"Your table has 500M rows and this DELETE times out. What's your production approach?"* — batch the delete (delete in chunks by a range of ids or a `LIMIT` inside a loop, committing between batches) to avoid a single massive transaction holding locks and bloating the WAL/undo log, and consider running it during low-traffic windows with monitoring on replication lag if there are replicas.

### Q8 — Write a query showing month-over-month revenue percent change per product, handling the divide-by-zero/NULL case.
**Testing:** LAG mechanics plus the NULLIF guard.
**Answer:** `LAG(revenue) OVER (PARTITION BY product_id ORDER BY month)` fetches the prior month's value; percent change is `100.0 * (revenue - prev) / NULLIF(prev, 0)`, where `NULLIF(prev, 0)` converts a zero denominator to `NULL` rather than raising a division error or (in some engines) silently returning infinity/error — `NULL` propagates cleanly as "change is undefined" rather than crashing the query or producing a nonsensical number.
**Follow-up trap:** *"What if the previous month simply doesn't exist in the table (no row at all, not zero revenue)?"* — `LAG` naturally returns `NULL` when there's no prior row within the partition (not an error), which then also makes the percent-change expression `NULL` — behaviorally correct already, but worth stating explicitly that "no row" and "row with zero revenue" both need to resolve to a sensible non-crashing result, and they do, for different reasons (no row → LAG returns NULL; zero revenue → NULLIF converts it).

### Q9 — Write an UPSERT that's safe under concurrent inserts for the same natural key, and explain what happens without the right isolation handling.
**Testing:** whether the candidate knows `INSERT ... ON CONFLICT` isn't just syntax sugar but a real atomicity fix for a race a naive check-then-insert has.
**Answer:** `INSERT INTO accounts (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET balance = accounts.balance + EXCLUDED.balance;` — this is atomic at the database level: the conflict check and the resulting insert-or-update happen as one indivisible operation under the row's own lock, so two concurrent transactions targeting the same `user_id` serialize correctly with no lost update. The naive alternative — `SELECT` to check existence, then `INSERT` or `UPDATE` based on the result, in application code — has a real race window: two concurrent transactions can both see "no row exists" during their `SELECT`, both attempt an `INSERT`, and one fails on the unique constraint (or worse, without a unique constraint at all, both succeed and you get a silent duplicate).
**Follow-up trap:** *"Does `ON CONFLICT DO UPDATE` fully eliminate the possibility of a lost update under concurrent access?"* — it eliminates the *insert* race specifically, but if the update logic reads other application state outside the statement (e.g., computing the new balance in application code from a previously-fetched value rather than `accounts.balance + EXCLUDED.balance` computed in-database), that external read can still be stale — the safe pattern always computes the new value from the *current* row value referenced inside the same statement, not from a value fetched earlier in application code.

### Q10 — A query that ran in 50ms for months suddenly takes 8 seconds after a data migration added 10x more rows to one of the joined tables, with no schema or query change. Walk through your diagnosis.
**Testing:** `EXPLAIN ANALYZE` literacy and cardinality-estimate reasoning, not just "add an index" as a reflexive answer.
**Answer:** Run `EXPLAIN (ANALYZE, BUFFERS)` and compare the plan's chosen join strategy and scan types against what ran before — the most common cause of this exact symptom is the query planner's cost-based optimizer switching strategies once table statistics reflect the new row count: a nested-loop join that was cheap when the inner table was small becomes catastrophically expensive once it's 10x larger, and the planner may not have picked up the new cardinality if `ANALYZE` hasn't run since the migration (stale statistics is the single most common root cause of this symptom, checked first before touching indexes). If statistics are current and the plan still picks a suboptimal strategy, check whether a needed index exists on the new, larger table's join/filter columns — a sequential scan that was tolerable at the old row count is not at 10x.
**Follow-up trap:** *"You confirm statistics are fresh and an index exists, but the planner still isn't using it. Now what?"* — check the query's selectivity assumption versus reality: if the filter matches a large fraction of rows (low selectivity), a sequential scan can genuinely be cheaper than an index scan despite the index existing, and the planner is making the correct cost-based call — the fix in that case isn't forcing index usage, it's reconsidering the query's filter conditions or considering a covering/partial index specifically shaped for the actual selective subset the query needs, rather than fighting the planner's correct cost estimate.

---

## SQL Practice Bank (40 questions, by pattern)

Each entry: problem, then a compact, correct solution sketch. Assume standard PostgreSQL-flavored SQL unless noted; syntax differences called out where they commonly trip people up.

**Filter & aggregate (Q1-6)**

1. *Total revenue per region, regions with >$1M only.* `SELECT region, SUM(amount) FROM orders GROUP BY region HAVING SUM(amount) > 1000000;`
2. *Average order value excluding refunded orders.* `SELECT AVG(amount) FROM orders WHERE status != 'refunded';`
3. *Count of distinct customers who ordered in both January and February.* `SELECT COUNT(*) FROM (SELECT customer_id FROM orders WHERE month=1 INTERSECT SELECT customer_id FROM orders WHERE month=2) t;`
4. *Products with zero orders in the last 90 days.* `SELECT p.id FROM products p LEFT JOIN orders o ON o.product_id=p.id AND o.order_date > now() - INTERVAL '90 days' WHERE o.id IS NULL;`
5. *Customers whose total spend is above the overall average.* `SELECT customer_id, SUM(amount) s FROM orders GROUP BY customer_id HAVING SUM(amount) > (SELECT AVG(amount) FROM orders);` (note: compares customer totals to per-order average — clarify the metric with the interviewer; a correct alternative compares to average *customer total*.)
6. *Percentage of orders that were cancelled, per month.* `SELECT month, 100.0*SUM((status='cancelled')::int)/COUNT(*) FROM orders GROUP BY month;`

**Conditional joins (Q7-11)**

7. *Employees with no assigned manager.* `SELECT * FROM employees WHERE manager_id IS NULL;`
8. *Customers who never made a purchase.* `SELECT c.* FROM customers c LEFT JOIN orders o ON o.customer_id=c.id WHERE o.id IS NULL;`
9. *Orders where the shipping address differs from the billing address.* `SELECT * FROM orders WHERE shipping_address_id != billing_address_id;`
10. *Self-join: pairs of employees in the same department earning the same salary.* `SELECT a.id, b.id FROM employees a JOIN employees b ON a.department_id=b.department_id AND a.salary=b.salary AND a.id < b.id;`
11. *Products ordered together with product X (market-basket, single join).* `SELECT DISTINCT o2.product_id FROM orders o1 JOIN orders o2 ON o1.order_id=o2.order_id AND o1.product_id != o2.product_id WHERE o1.product_id='X';`

**Top-N per group (Q12-17)**

12. *Highest-paid employee per department.* `WITH r AS (SELECT *, RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) rk FROM employees) SELECT * FROM r WHERE rk=1;`
13. *Second-highest salary overall (no window function allowed — classic constraint).* `SELECT MAX(salary) FROM employees WHERE salary < (SELECT MAX(salary) FROM employees);`
14. *Top 5 products by revenue per category.* `WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) rn FROM product_revenue) SELECT * FROM r WHERE rn<=5;`
15. *Most recent login per user.* `WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_time DESC) rn FROM logins) SELECT * FROM r WHERE rn=1;`
16. *Cheapest supplier per part (ties included).* `WITH r AS (SELECT *, RANK() OVER (PARTITION BY part_id ORDER BY price ASC) rk FROM supplier_prices) SELECT * FROM r WHERE rk=1;`
17. *Bottom 10% of students by score, per class.* `WITH r AS (SELECT *, PERCENT_RANK() OVER (PARTITION BY class_id ORDER BY score) pr FROM scores) SELECT * FROM r WHERE pr <= 0.10;`

**Period-over-period / LAG-LEAD (Q18-23)**

18. *Month-over-month revenue change per product.* (see worked example above)
19. *Days since a customer's previous order.* `SELECT *, order_date - LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date) AS days_since_prev FROM orders;`
20. *First order date and most recent order date per customer, alongside every row.* `SELECT *, FIRST_VALUE(order_date) OVER (PARTITION BY customer_id ORDER BY order_date) AS first_order, LAST_VALUE(order_date) OVER (PARTITION BY customer_id ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_order FROM orders;` (note: `LAST_VALUE` needs the full-frame override — default frame stops at current row.)
21. *Year-over-year growth per region.* Self-join on `year = year-1` or `LAG(revenue, 12)` if data is monthly and gapless; state the assumption about gaplessness explicitly.
22. *Detect a customer whose spend dropped more than 50% month over month.* `WITH c AS (SELECT *, LAG(revenue) OVER (PARTITION BY customer_id ORDER BY month) prev FROM monthly_spend) SELECT * FROM c WHERE revenue < 0.5*prev;`
23. *Next scheduled maintenance date per machine, from a maintenance log.* `SELECT *, LEAD(scheduled_date) OVER (PARTITION BY machine_id ORDER BY scheduled_date) AS next_date FROM maintenance;`

**Gaps and islands / sessionization (Q24-28)**

24. *Consecutive login streaks per user.* (see worked example above)
25. *Find gaps in a sequential ID column (missing invoice numbers).* `WITH n AS (SELECT id, LEAD(id) OVER (ORDER BY id) next_id FROM invoices) SELECT id+1 AS gap_start, next_id-1 AS gap_end FROM n WHERE next_id - id > 1;`
26. *Sessionize clickstream events with a 30-minute inactivity cutoff.* (see the "Build it from scratch" worked example)
27. *Longest streak of profitable days per stock ticker.* Same island technique as Q24, partitioned by ticker, filtered to `is_profitable=true` rows before numbering.
28. *Merge overlapping date ranges (e.g., overlapping employee leave requests) into consolidated intervals.* Sort by start date; flag a new group whenever `start_date > MAX(end_date) so far` (running max via window function), then group by that flag's cumulative sum, same mechanism as sessionization.

**Deduplication (Q29-32)**

29. *Remove exact duplicate rows, keeping one.* `DELETE FROM t WHERE ctid NOT IN (SELECT MIN(ctid) FROM t GROUP BY col1, col2, col3);` (Postgres-specific `ctid`; portable version uses a surrogate key with `ROW_NUMBER()`.)
30. *Keep only the latest record per natural key.* (see worked example above)
31. *Identify (not delete) duplicate email addresses across customer records.* `SELECT email, COUNT(*) FROM customers GROUP BY email HAVING COUNT(*) > 1;`
32. *Deduplicate while preserving the row with the most non-null fields (a common real-world "best record" merge).* Rank by a computed non-null-count column descending, then keep `rn=1`, same pattern as Q30 with a different ORDER BY expression.

**Hierarchy / recursive CTE (Q33-36)**

33. *All descendants of a given category in a category tree.* (see worked example above, walking downward)
34. *All ancestors of a given node (path to root).* Same recursive shape, reversed join direction: recursive member joins `employees e ON e.employee_id = cte.manager_id`.
35. *Total depth of an org chart, and the deepest path.* Recursive CTE tracking `depth`, then `SELECT MAX(depth) FROM org_chart;` plus a path-string accumulator (`path || ' > ' || name`) for the deepest path's readable trace.
36. *Bill-of-materials explosion: total component count for a manufactured assembly, including sub-assemblies.* Recursive CTE multiplying quantities down each level (`quantity * parent_multiplier`), summing leaf-level (non-assembly) components at the end.

**Lateral / cross apply (Q37-38)**

37. *For each store, the 2 best-selling products and their rank.* `SELECT s.store_id, p.* FROM stores s CROSS JOIN LATERAL (SELECT product_id, units_sold, RANK() OVER (ORDER BY units_sold DESC) rk FROM sales WHERE store_id=s.store_id ORDER BY units_sold DESC LIMIT 2) p;`
38. *For each user, their most recent order plus a flag for whether they have any open support ticket (two correlated lookups combined).* Two `LATERAL` joins in the same `FROM`, one for `orders ORDER BY date DESC LIMIT 1`, one for `EXISTS`-style ticket check.

**Mixed / staff-level composition (Q39-40)**

39. *Cohort retention: of users who signed up in each month, what percent were still active 1/2/3 months later?* Join `signups` to `activity` on a month-offset, `COUNT(DISTINCT active users) / COUNT(DISTINCT cohort users)` per offset, grouped by cohort month — combines a self-referencing date-offset join with aggregate ratios.
40. *Detect fraud pattern: users who made 3+ orders from 3+ different shipping addresses within a 1-hour window.* Window function counting distinct addresses within a time-bounded frame (`COUNT(DISTINCT address_id) OVER (PARTITION BY user_id ORDER BY order_time RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW)` — note `COUNT(DISTINCT ...)` as a window function isn't supported in every engine; Postgres supports it, some engines require a subquery-based rewrite instead.

---

## Red flags that fail you

- Confusing `RANK()`, `DENSE_RANK()`, and `ROW_NUMBER()` under pressure, or not asking which tie-behavior the business question actually wants.
- Trying to filter a window function's result in the same query's `WHERE`/`HAVING` instead of wrapping in a CTE.
- Writing a running total with an implicit `RANGE` frame and not knowing it silently groups tied `ORDER BY` values.
- Writing a recursive CTE with no depth cap or cycle guard "because the data shouldn't have cycles."
- Deduplication logic with no deterministic tiebreaker, making the result non-reproducible.
- Not being able to read a basic `EXPLAIN` output — no idea what a sequential scan versus an index scan implies.
- Treating every top-N-per-group problem as requiring `LATERAL` when a simple window function is equally correct and sometimes clearer.

---

## Cheat card

```
EXECUTION ORDER   FROM/JOIN → WHERE → GROUP BY → HAVING → WINDOW FNS → SELECT
                   → DISTINCT → ORDER BY → LIMIT
                   (can't filter a window fn result without wrapping in CTE)

RANK FAMILY        ROW_NUMBER: 1,2,3 (arbitrary tiebreak, always unique)
                    RANK:       1,1,3 (ties share rank, gap after)
                    DENSE_RANK: 1,1,2 (ties share rank, no gap)

FRAME               ROWS = physical rows, ties don't matter
                     RANGE = groups ORDER BY peers (DEFAULT when ORDER BY present!)
                     → always specify ROWS explicitly for running totals

RECURSIVE CTE       anchor UNION ALL recursive-member-joining-own-output
                     ALWAYS cap depth (WHERE depth < N) — data cycles are not rare
                     large/hot hierarchy → materialized closure table beats live recursion

LATERAL/APPLY        subquery can reference EARLIER columns in same FROM
                     use for top-N-per-group (N>1) or per-row correlated logic
                     CROSS APPLY = SQL Server/older MySQL syntax equivalent

GAPS & ISLANDS       row_number() - row_number() (scaled to unit) = constant WITHIN a run
                     dedupe input first — duplicate ordering values break the arithmetic

DEDUP                ROW_NUMBER() OVER (PARTITION BY key ORDER BY ts DESC, id DESC) = 1
                     ALWAYS add a tiebreaker column — else non-deterministic/non-idempotent

LAG/LEAD             NULLIF(denominator, 0) guards percent-change division
                     LAG returns NULL naturally when no prior row exists — don't special-case it

EXPLAIN checklist    Seq Scan on filtered large table → missing/defeated index
                     Nested Loop w/ big inner side → check stats, maybe should be Hash Join
                     estimated rows far off actual → stale statistics, run ANALYZE
                     Sort before window fn → composite index on (partition_cols, order_col)
```

## Sources

- [80 SQL Interview Questions for Data Engineers (Real Asks, 2026) — datavidhya.com](https://datavidhya.com/blog/sql-data-engineering-interview-questions/) — accessed 2026-08-02
- [SQL Window Functions, CTEs & Advanced Queries for Data Analysts (2026) — SharpSkill](https://sharpskill.dev/en/blog/data-analytics/sql-window-functions-ctes-advanced-queries) — accessed 2026-08-02
- [The Gaps and Islands Problem: SQL Interview Practice — Medium](https://medium.com/@keshavkhandelwal142/the-gaps-and-islands-problem-sql-interview-practice-8c087a511cd1) — accessed 2026-08-02
- [SQL Interview Questions 2026: 200+ Problems by Topic & Company — sql-practice.online](https://www.sql-practice.online/learn/sql-interview-questions-guide) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
