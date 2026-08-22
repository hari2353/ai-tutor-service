# SQL Server: Clustered vs Nonclustered, Parameter Sniffing, Columnstore

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-sqlserver` · **Tags:** sqlserver

## The 30-second version

A SQL Server clustered index *is* the table: the leaf level of its B-tree stores the actual row data in key order, so a table has at most one, and every nonclustered index's leaf level stores the clustering key (not a physical row pointer) as its row locator, which means a narrow, stable clustering key keeps every nonclustered index smaller and cheaper to maintain. Parameter sniffing is the optimizer compiling and caching a plan shaped for whatever parameter value happened to run first, then reusing that plan for every subsequent call with different parameters, including ones with wildly different selectivity, until it silently becomes wrong for most of the traffic; the tell is a stored procedure that has been fast for months and is suddenly slow for no code change, with `sys.dm_exec_query_stats` showing one cached plan whose estimated rows are far from actual rows for the current call. The fixes trade specificity for CPU: `OPTION (RECOMPILE)` gets a fresh, correct plan every call at the cost of compiling every call; `OPTIMIZE FOR UNKNOWN` gets one average-case plan that's mediocre for everyone instead of great-then-terrible; SQL Server 2022's Parameter Sensitive Plan optimization keeps several plans keyed to parameter-value buckets automatically. Columnstore indexes store data column-wise and compressed, execute in batch mode (roughly 900 rows at a time instead of one), and skip whole rowgroups via min/max segment metadata, which is why a columnstore-backed fact table scans and aggregates orders of magnitude faster than the same table in a rowstore B-tree, at the cost of being a poor fit for singleton point lookups and small, frequent updates.

## Why this gets asked

The interviewer has been paged for a stored procedure that ran in 50ms for six months and then took 30 seconds after a completely unrelated deploy, and they want to know if you'd reach for "restart the server" or actually diagnose a stale, badly-sniffed plan from `sys.dm_exec_query_stats` and `sys.dm_exec_query_plan`. They've also watched someone add a nonclustered index on every column "just in case" and wondered whether the candidate understands that every nonclustered index carries the full clustering key as baggage, and they've watched a reporting team migrate a fact table to a clustered columnstore index and cut a multi-minute aggregation to sub-second, and want to know if you understand why, not just that it happened.

---

## Lineage: past → present → future

**What came before.** SQL Server's storage engine has always been a row-store B+-tree by default; the original design assumed OLTP workloads where a small number of rows are read or written per statement, and a clustered index (row data ordered by key at the leaf level, inherited from Sybase's architecture that SQL Server forked from in the early 1990s) was the natural fit. Cardinality estimation used a single, largely unchanged model from SQL Server 7.0 (1998) through SQL Server 2012, which worked adequately for the query shapes of that era but produced increasingly bad row-count estimates as query patterns grew more complex (multi-predicate correlated filters, wide joins) — bad estimates meant bad plan choices (hash join when a merge join was cheaper, or a table scan when a seek would have won), and DBAs learned to distrust the optimizer's row estimates as a first debugging move. Analytical workloads on the same engine were the real pain: aggregating millions of rows in a row-store means reading every column of every row from disk even when the query only needs three columns, and pre-columnstore SQL Server had no answer to this other than heavier indexing or moving the workload to a separate warehouse.

**Where it stands now.** Columnstore indexes (introduced as a read-only, non-clustered option in SQL Server 2012, made updatable and clusterable in SQL Server 2014) are now the standard answer for the OLTP/OLAP-mixed reality most production databases actually have: keep the row-store clustered index for point lookups and transactional writes, and add a nonclustered columnstore index (NCCI) alongside it so analytical queries hit compressed, batch-mode-executed columnar storage without needing a separate warehouse or ETL pipeline — this hybrid pattern (Microsoft calls it "operational analytics") is genuinely deployed at scale, not just a marketing slide. The live disagreement is cardinality estimation: Microsoft shipped a new CE model in SQL Server 2014 (activated by database compatibility level ≥120) that fixed many systematic biases of the legacy model but also changed plan shapes for existing, tuned workloads, so upgrading compatibility level on a large inherited database is a real, feared risk — many shops stay on an old compatibility level specifically to keep the legacy CE and avoid plan regressions, trading known mediocre estimates for unknown new ones. Parameter sniffing itself is not "solved": `OPTION(RECOMPILE)`, `OPTIMIZE FOR`, and Parameter Sensitive Plan (PSP) optimization (SQL Server 2022, compatibility level 160) are all still workarounds for the same underlying tension — one cached plan versus one execution's actual parameter values — not a fix that makes the tradeoff disappear.

**Where it's heading.** Intelligent Query Processing (the umbrella Microsoft uses for CE feedback, memory grant feedback, and PSP optimization, shipped incrementally 2017–2022 and continuing to expand) is the clear direction: let the engine observe actual runtime behavior across executions and adapt cached plans or memory grants without a DBA hand-tuning hints. PSP optimization specifically — caching multiple plans per query bucketed by parameter-value skew rather than one plan per query text — is a real, shipping answer to a specific slice of the parameter-sniffing problem (equality predicates with skewed cardinality) and is confidence-high as the direction future compatibility levels keep pushing. What's more speculative: whether IQP features can be trusted to auto-tune away parameter sniffing for arbitrary query shapes (range predicates, multi-parameter interactions) without any hinting is still an open question in practice — most senior engineers still keep `OPTION(RECOMPILE)` and plan-guide knowledge in their toolkit rather than assuming the engine will always self-correct.

---

## Mental model

```
CLUSTERED INDEX = THE TABLE                 NONCLUSTERED INDEX (leaf = clustering key)

  B-tree leaf level                          B-tree leaf level
  ┌─────────────────────────┐                ┌─────────────────────────┐
  │ id=1  name=Alice  ...   │  <- actual      │ email='a@x.com' -> id=1 │ <- row locator
  │ id=2  name=Bob    ...   │     row data    │ email='b@x.com' -> id=2 │    is the
  │ id=3  name=Carl   ...   │     lives here  │ email='c@x.com' -> id=3 │    CLUSTERING
  └─────────────────────────┘                └─────────────────────────┘    KEY, not a
       ordered by clustering key                  ordered by (email)        physical RID

  Lookup by email -> seek nonclustered index (fast) -> get id -> "KEY LOOKUP":
  seek the CLUSTERED index AGAIN by id to fetch the rest of the row.
  Wide/volatile clustering key => every nonclustered index carries that
  baggage on every row, and every insert into the middle of clustering-key
  order can cause a page split.

PARAMETER SNIFFING TIMELINE

  Day 1:  EXEC GetOrders @CustomerId = 5        (5 has 3 orders)
          optimizer compiles plan shaped for "few rows" -> NESTED LOOP, cached
  Day 2-180: every call reuses that cached plan, mostly fine (most customers: few orders)
  Day 181: EXEC GetOrders @CustomerId = 1       (customer 1 has 2M orders, VIP account)
          SAME cached nested-loop plan runs -> 2M single-row index seeks
          instead of a hash join or scan -> query that should take 200ms takes 45s
  No code changed. No data corruption. Just: the ONE cached plan met a parameter
  value it was never shaped for.
```

---

## How it actually works

### Clustered vs nonclustered, and the key lookup

A SQL Server table with a clustered index stores its rows physically sorted by the clustering key at the B-tree leaf level — there is no separate "heap" data structure the clustered index points to, the index leaf *is* the row storage (a table with no clustered index is a heap, storing rows in no particular physical order, referenced by an 8-byte RID). Every nonclustered index leaf entry stores the clustering key value(s) as its row locator instead of a physical pointer, which is a deliberate design choice: it means clustered-index page splits (which move rows physically) never invalidate nonclustered index entries, at the cost that every nonclustered index duplicates the clustering key on every one of its rows. A wide clustering key (a GUID, a multi-column composite, a long string) is therefore a compounding cost: it bloats every nonclustered index on the table, not just the clustered one — this is the concrete reason `IDENTITY`/`BIGINT` surrogate keys are the default recommendation over natural or GUID keys for the clustering key specifically, independent of whether they're also the primary key.

When a query seeks a nonclustered index but needs columns beyond what the index carries, SQL Server issues a **key lookup**: a second seek into the clustered index, keyed by the locator value found in step one, to fetch the remaining columns — one extra random I/O per matching row. `EXPLAIN`-equivalent (`SET STATISTICS IO ON` / the graphical execution plan) shows this as a separate "Key Lookup" operator joined back to the index seek via a nested loop. Past some estimated row count (the optimizer's own cost-based threshold, not a fixed constant, but observably somewhere in the low hundreds to low thousands of rows depending on table/row width), the optimizer decides that paying one key lookup per row is more expensive than a full clustered index/table scan and flips the plan to a scan — this is why an index that works great for a narrow query starts producing scans once the predicate's estimated selectivity gets even moderately wide, and why covering the query (adding an `INCLUDE` column, exactly as in Postgres, see `T17-index-design`) is the standard fix: it eliminates the key lookup entirely.

### Parameter sniffing: mechanism, symptom, fixes

SQL Server caches execution plans for parameterized queries and stored procedures keyed by query text/plan handle, not by parameter value. The **first** execution of a given plan (after cache eviction, a schema change, a stats update, or server restart) compiles the plan using that call's actual parameter values to estimate cardinality via the histogram — this is "sniffing" the parameter. Every subsequent call reuses that cached plan regardless of its own parameter values, which is correct and beneficial *when* the data underlying different parameter values is roughly uniform, and actively wrong when the table has skewed distributions (a customer with 2M orders vs one with 3, a status column that's 95% `'completed'` and 5% `'pending'`).

**Observable symptom:** a query or stored procedure runs fine, sometimes for months, then suddenly performs badly for a specific parameter value with zero code or schema changes. `sys.dm_exec_query_stats` joined to `sys.dm_exec_query_plan` for the offending plan handle typically shows a large gap between `estimated_rows` in the cached plan and the actual row count for the current call — the classic tell in the graphical plan is estimated vs actual rows off by orders of magnitude on one operator, usually right after the first predicate on the sniffed parameter.

**Fixes, and their costs:**

```sql
-- Fix 1: OPTION (RECOMPILE) — fresh plan EVERY execution, using this call's real values
SELECT * FROM Orders WHERE CustomerId = @CustomerId
OPTION (RECOMPILE);
-- Cost: pays full compilation cost on every single call. Fine for infrequent,
-- expensive queries; wrong for a query executed thousands of times/sec.

-- Fix 2: OPTIMIZE FOR UNKNOWN — compile using average density statistics,
-- not this call's actual value
SELECT * FROM Orders WHERE CustomerId = @CustomerId
OPTION (OPTIMIZE FOR UNKNOWN);
-- Cost: one plan, cached once — but it's a "good enough for the average case"
-- plan, actively suboptimal for both the very sparse and very dense ends.

-- Fix 3: local variable assignment — defeats sniffing implicitly, same effect
-- as OPTIMIZE FOR UNKNOWN but without the hint (older technique, same idea)
CREATE PROCEDURE GetOrders @CustomerId INT AS
BEGIN
    DECLARE @Local INT = @CustomerId;
    SELECT * FROM Orders WHERE CustomerId = @Local;
END
-- Cost: identical tradeoff to OPTIMIZE FOR UNKNOWN, just less explicit/discoverable
-- in code review — mildly discouraged versus the hint for that reason.

-- Fix 4: plan guide — attach a hint to a query you cannot modify (vendor code,
-- generated SQL)
EXEC sp_create_plan_guide
  @name = N'FixOrdersSniffing',
  @stmt = N'SELECT * FROM Orders WHERE CustomerId = @CustomerId',
  @type = N'OBJECT', @module_or_batch = N'GetOrders',
  @params = NULL, @hints = N'OPTION (OPTIMIZE FOR UNKNOWN)';
-- Cost: operationally invisible in the source code, which is exactly the point
-- and exactly the risk — the next engineer reading the procedure has no idea
-- a plan guide is silently reshaping its plan.
```

SQL Server 2022's **Parameter Sensitive Plan (PSP) optimization** (requires database compatibility level 160, on by default at that level) takes a different approach: for a query with an equality predicate the optimizer suspects has skewed cardinality, it keeps *multiple* cached plans bucketed by which cardinality range the sniffed parameter falls into, and picks the right bucket's plan per call — genuinely solving the specific "one parameter value is rare, another is common" case without `RECOMPILE`'s per-call compilation cost. It does not help range-predicate or multi-parameter interactions, and it increases plan cache memory footprint since multiple plans now live for one query text.

### Statistics and cardinality estimation

The optimizer's row estimates come from **statistics**: a histogram (up to 200 steps) plus density information maintained per index and per column, auto-created and auto-updated by default (`AUTO_CREATE_STATISTICS`, `AUTO_UPDATE_STATISTICS`) when roughly 20% of a table's rows have changed since the last update (modified further by a dynamic threshold on larger tables, `AUTO_UPDATE_STATISTICS_ASYNC` controlling whether the query that triggers the update waits for it). Stale statistics — a large bulk load or delete that hasn't triggered an auto-update yet — is one of the most common root causes misdiagnosed as "parameter sniffing," which is why `UPDATE STATISTICS` is a standard first troubleshooting step, not just adding a hint.

SQL Server shipped a genuinely new cardinality estimator in SQL Server 2014, tied to database **compatibility level ≥ 120**; the legacy CE (compatibility level ≤ 110, or forced via `TRACEFLAG 9481` / the `LEGACY_CARDINALITY_ESTIMATION` query hint) uses different, generally more pessimistic assumptions about correlation between predicates on the same table. Upgrading compatibility level on an old, heavily-tuned database is a real risk precisely because it can silently reshape plans across the entire workload at once — the standard mitigation is to upgrade compatibility level in a lower environment first and diff plan choices on the actual production query mix, not to trust that "newer is strictly better" holds for a specific inherited schema.

### Isolation levels: READ COMMITTED locking vs RCSI

SQL Server's default isolation level is **READ COMMITTED**, but unlike Postgres, SQL Server's default *implementation* of READ COMMITTED is lock-based, not MVCC: a `SELECT` takes a shared lock on each row/page it reads and releases it as soon as the read moves past that row (not held until end of transaction), while an `UPDATE`/`DELETE`/`INSERT` takes an exclusive lock held until commit. This means readers and writers **do** block each other under SQL Server's default configuration — a long-running report query can block a concurrent `UPDATE` on rows it's currently scanning, and vice versa, which is a genuinely different default behavior from Postgres/Oracle's snapshot-based READ COMMITTED and a frequent surprise for engineers moving between the two.

**READ COMMITTED SNAPSHOT ISOLATION (RCSI)**, an opt-in database setting (`ALTER DATABASE ... SET READ_COMMITTED_SNAPSHOT ON`), changes READ COMMITTED to use row versioning instead of locks: readers see the last-committed version of a row as of the start of their statement and never block on, or get blocked by, a writer. This is the single most common fix teams apply to eliminate blocking chains without rewriting application code, because it changes engine behavior, not query text. The cost: every versioned row's old version gets copied into the **version store in tempdb**, so a workload with high write volume and long-running readers can drive substantial tempdb growth and I/O — "RCSI fixed my blocking but now tempdb is a bottleneck" is a real, common second-order failure, and tempdb should be pre-sized, striped across multiple equally-sized data files, and placed on fast storage before RCSI is enabled on a high-write production database, not as an afterthought once contention appears.

### Columnstore indexes, batch mode, segment elimination

A **columnstore index** stores each column's values together, compressed, in units called **rowgroups** (up to roughly 1,048,576 rows per rowgroup) which are themselves broken into **segments** per column; each segment stores a compressed value stream plus min/max metadata. A query filtering on a column can use that metadata to skip entire segments whose min/max range can't satisfy the predicate — **segment elimination** — without decompressing or reading the segment's actual data at all. Columnstore query execution uses **batch mode**: operators process roughly 900 rows at a time as a vectorized batch instead of the traditional row-mode "one row through the whole operator tree," which amortizes per-row CPU overhead and is typically cited as a 2-4x throughput improvement on top of the columnar storage and compression wins themselves.

A **clustered columnstore index (CCI)** replaces the table's row storage entirely (no separate rowstore clustered index coexists); a **nonclustered columnstore index (NCCI)** adds columnar storage alongside an existing rowstore clustered index, letting OLTP point lookups keep using the B-tree while analytical aggregations hit the columnstore — this is the "operational analytics" hybrid pattern and the common production shape for a table that serves both transactional and reporting traffic. Segment elimination works best when data is physically ordered relative to the filtered column (directly analogous to ClickHouse's `ORDER BY`/BRIN correlation requirement, see `T17-clickhouse`); an unordered columnstore on a randomly-inserted timestamp column gets far less benefit from segment elimination than one built with `MAXDOP = 1` in a single ordered pass, or periodically rebuilt/reorganized to restore ordering after heavy fragmenting DML.

---

## Build it from scratch

Minimal, runnable illustration of the key-lookup cost and segment elimination concept against a real SQL Server instance:

```sql
-- untested sketch — illustrative, requires a running SQL Server instance
CREATE TABLE Orders (
    Id BIGINT IDENTITY PRIMARY KEY CLUSTERED,
    CustomerId INT NOT NULL,
    Status VARCHAR(20) NOT NULL,
    CreatedAt DATETIME2 NOT NULL,
    TotalAmount DECIMAL(10,2) NOT NULL
);

-- Narrow nonclustered index: seeks fast, but needs a key lookup for TotalAmount
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId ON Orders (CustomerId);

-- Populate with skewed data: most customers have few orders, one has millions
-- (a lightweight way to reproduce parameter-sniffing-shaped skew locally)
;WITH Numbers AS (
    SELECT TOP (2000000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
)
INSERT INTO Orders (CustomerId, Status, CreatedAt, TotalAmount)
SELECT CASE WHEN n <= 1900000 THEN 1 ELSE (n % 50000) + 2 END,
       CASE WHEN n % 20 = 0 THEN 'pending' ELSE 'completed' END,
       DATEADD(SECOND, n, '2024-01-01'), (n % 500) + 9.99
FROM Numbers;

-- Key lookup demonstration: this needs TotalAmount, which isn't in the index
SELECT CustomerId, TotalAmount FROM Orders WHERE CustomerId = 42;
-- SET STATISTICS IO ON shows a Key Lookup operator; fix by covering:
CREATE NONCLUSTERED INDEX IX_Orders_CustomerId_Covering
  ON Orders (CustomerId) INCLUDE (TotalAmount);

-- Parameter sniffing repro: compile against the SPARSE customer (id=2), then
-- call with the DENSE customer (id=1) using the same cached plan
CREATE PROCEDURE GetOrdersByCustomer @CustomerId INT AS
    SELECT * FROM Orders WHERE CustomerId = @CustomerId;
GO
EXEC GetOrdersByCustomer @CustomerId = 2;   -- compiles a nested-loop-shaped plan
EXEC GetOrdersByCustomer @CustomerId = 1;   -- 1.9M rows through the SAME plan shape
-- sys.dm_exec_query_stats.last_elapsed_time will show the second call's cost;
-- compare against: EXEC GetOrdersByCustomer @CustomerId = 1 WITH RECOMPILE;
```

Reading `SET STATISTICS IO, TIME ON` output and the graphical execution plan (particularly estimated vs. actual row counts on each operator) for these three queries is the fastest way to build real intuition. Full lab with a columnstore comparison against the same table: **`(lab pending)`**.

---

## How it's done in production

**Diagnosing parameter sniffing.** `sys.dm_exec_query_stats` (min/max/last elapsed time and worker time per cached plan) joined to `sys.dm_exec_query_plan` and `sys.dm_exec_sql_text` is the standard loop: find a plan with high variance between min and max elapsed time for the same query text, then compare the cached plan's estimated row counts to actual (Query Store, if enabled, keeps this history across plan evictions and server restarts, which `sys.dm_exec_query_stats` alone does not). **Query Store** (on by default for new databases since SQL Server 2016, and the standard tool since) additionally lets you force a specific known-good historical plan (`sp_query_store_force_plan`) as an immediate mitigation while a permanent fix is developed.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Stored procedure fast for months, suddenly slow for one specific input, no code change | Cached plan sniffed a non-representative parameter value; skewed data distribution now hits the wrong plan shape | `OPTION (RECOMPILE)` for infrequent/expensive queries, `OPTIMIZE FOR UNKNOWN` for high-frequency ones, or PSP optimization (compat level 160+) |
| A query that used a good index yesterday now does a full scan | Statistics went stale after bulk load/delete before auto-update triggered, or the optimizer's scan-vs-seek cost crossover was crossed by a data volume change | `UPDATE STATISTICS` manually after large batch operations; check `sys.dm_db_stats_properties` for last-updated and modification counters |
| Long-running SELECT blocks a concurrent UPDATE on rows it's scanning (and vice versa) | Default lock-based READ COMMITTED: shared locks held during the scan conflict with exclusive locks from writers | Enable RCSI (`READ_COMMITTED_SNAPSHOT ON`) to move to row-versioning instead of locking for reads |
| tempdb becomes an I/O and contention bottleneck after enabling RCSI | Every old row version touched by a versioned read gets copied into the tempdb version store | Pre-size and pre-stripe tempdb across multiple equally-sized files before enabling RCSI on a high-write database, not after |
| Analytical aggregation over a fact table is orders of magnitude slower than expected despite indexes | Rowstore B-tree reads every column of every row from disk even when only 3 columns are needed | Add a nonclustered columnstore index for the analytical access pattern (operational analytics), or migrate the fact table to a clustered columnstore |
| Columnstore query shows little to no segment elimination benefit despite filtering | Rowgroups aren't physically ordered relative to the filtered column (random insert order) | Rebuild with `MAXDOP = 1` for an ordered build, or periodically `ALTER INDEX ... REORGANIZE` to restore ordering after heavy DML fragmentation |
| Upgrading database compatibility level regresses a previously-fast query | New cardinality estimator (compat level ≥120) makes different correlation assumptions than legacy CE, reshaping the plan | Test compat-level upgrades against the real production query mix in a lower environment first; use `LEGACY_CARDINALITY_ESTIMATION` hint or trace flag 9481 as a scoped, temporary escape hatch, not a permanent policy |

---

## Tradeoffs & when NOT to use it

- **Don't default every table's clustering key to a wide or volatile natural key.** Every nonclustered index inherits that key as its row locator; a `BIGINT IDENTITY` (or sequential surrogate) keeps every other index on the table smaller and avoids page splits from out-of-order inserts.
- **Don't reach for `OPTION (RECOMPILE)` on a query executed thousands of times per second.** The per-call compilation cost that fixes a rarely-run report query will visibly raise CPU on a hot OLTP path; `OPTIMIZE FOR UNKNOWN` or PSP optimization are the right tools there.
- **Don't enable RCSI on a write-heavy database without sizing tempdb first.** The version-store cost is real and moves the bottleneck rather than eliminating it if tempdb isn't provisioned for it.
- **Don't use a clustered columnstore index for a table that needs frequent singleton point lookups or small, frequent updates.** Columnstore's unit of work is the rowgroup and segment; single-row point queries against a CCI are markedly worse than against a rowstore B-tree with a good index, and the delta-store mechanism that absorbs small inserts before they're compressed into a rowgroup adds its own overhead under high-frequency small writes. Operational analytics (NCCI alongside the existing rowstore clustered index) is the answer when both access patterns coexist, not converting the whole table.
- **Don't upgrade database compatibility level on a large inherited database as a routine maintenance step.** The new cardinality estimator can silently reshape plans across the whole workload; treat it as a change requiring its own testing pass against real production queries.
- **Don't add a plan guide as a permanent fix.** It's invisible in the source code and the next engineer debugging the same procedure has no way to discover it without knowing to check `sys.plan_guides`; prefer a query hint in the code itself, or PSP optimization, wherever the source is actually modifiable.

---

## Interview questions

### Q1 — Why does "the clustered index is the table" matter for how you design nonclustered indexes?
**Testing:** baseline architecture understanding.
**Answer:** Every nonclustered index leaf stores the clustering key as its row locator, not a physical pointer, so a wide or volatile clustering key bloats every nonclustered index on the table and increases the cost of any operation that touches them, not just the clustered index itself.
**Follow-up trap:** *"So should every table have a narrow surrogate integer key?"* — usually yes for the clustering key specifically, but that's independent of the primary/business key: you can have a `BIGINT IDENTITY` clustering key with a separate unique nonclustered index enforcing the natural key's uniqueness, getting both a narrow clustering key and correct business-key constraints.

### Q2 — What is a key lookup, and when does the optimizer stop using an index because of it?
**Answer:** A key lookup is a second seek into the clustered index to fetch columns a nonclustered index doesn't carry, once the nonclustered index has located a matching row via its locator (the clustering key). Past an estimated row count where the aggregate cost of one key lookup per row exceeds a scan's cost, the optimizer switches the plan to a scan instead of a seek-plus-lookup.
**Follow-up trap:** *"How do you eliminate the key lookup without changing the query?"* — add the needed columns to the nonclustered index as `INCLUDE` columns, turning it into a covering index; this doesn't change the query text at all, only the index definition.

### Q3 — Explain parameter sniffing precisely, including why it isn't a bug.
**Testing:** the core mechanism, not just the symptom.
**Answer:** The first execution of a parameterized query or procedure (after any cache invalidation) compiles a plan using that call's actual parameter values via the column histogram; every later call reuses the cached plan by query text regardless of its own parameter values. This is correct, beneficial behavior when the underlying data is roughly uniform across parameter values — it only becomes a problem when the data is skewed enough that different parameter values warrant genuinely different plan shapes.
**Follow-up trap:** *"If it's not a bug, why does Microsoft keep adding features to work around it?"* — because the cost/benefit of one-cached-plan-per-query-text is workload-dependent, and no single default can be right for both uniform and heavily skewed distributions; PSP optimization is Microsoft narrowing the cases where the tradeoff has to be made manually, not eliminating the tradeoff.

### Q4 — A stored procedure has been fast for six months and is suddenly slow for one customer, no code changes. Walk through your diagnosis.
**Answer:** Check `sys.dm_exec_query_stats` for the procedure's cached plan(s), looking at the spread between min and max elapsed/worker time for the same plan; pull the plan via `sys.dm_exec_query_plan` and compare estimated vs actual row counts per operator for the current slow execution (Query Store if available gives historical plan changes too). A large estimated/actual gap right after the predicate on the sniffed parameter confirms parameter sniffing; if the gap is present for all parameter values equally, suspect stale statistics instead.
**Follow-up trap:** *"How do you distinguish sniffing from stale statistics as the root cause?"* — stale statistics produce bad estimates for every parameter value uniformly (recent bulk load/delete not yet reflected); sniffing produces good estimates for the value that was sniffed and bad estimates specifically for other, differently-distributed values. Check `sys.dm_db_stats_properties` for last-updated time and modification counters to rule out staleness first, since `UPDATE STATISTICS` is a strictly cheaper fix to try than plan hints.

### Q5 — Compare `OPTION (RECOMPILE)`, `OPTIMIZE FOR UNKNOWN`, and PSP optimization as fixes for parameter sniffing.
**Answer:** `RECOMPILE` gets a fresh, always-correct plan per call at the cost of compiling on every single execution — right for infrequent, expensive queries, wrong at high QPS. `OPTIMIZE FOR UNKNOWN` compiles once using average density statistics instead of the sniffed value, producing one mediocre-for-everyone plan cached and reused cheaply — right when no single plan shape is a clear winner and compile cost matters more than peak-case optimality. PSP optimization (SQL Server 2022, compat level 160) keeps multiple plans bucketed by the sniffed parameter's cardinality range for equality predicates specifically, getting close to per-value-optimal plans without RECOMPILE's per-call cost, but only for the equality-predicate skew case it targets.
**Follow-up trap:** *"Which one would you reach for on a query with a range predicate (`WHERE CreatedAt > @Date`), not equality?"* — PSP optimization does not target range predicates; you're back to `RECOMPILE` or `OPTIMIZE FOR UNKNOWN` (or a manual plan-guide-based fix) for that shape.

### Q6 — What is RCSI and what specific production problem does it solve?
**Answer:** READ COMMITTED SNAPSHOT ISOLATION switches SQL Server's default READ COMMITTED from lock-based (shared locks on reads, blocking against writers) to row-versioning (readers see the last-committed version as of statement start, never blocking or being blocked by writers). It's the standard fix for blocking chains between long-running reads and concurrent writes without touching application code.
**Follow-up trap:** *"What's the hidden cost people forget to plan for?"* — tempdb growth and I/O from the version store holding old row versions for in-flight readers; enabling RCSI on a high-write database without first sizing and striping tempdb across multiple files just moves the bottleneck rather than removing it.

### Q7 — How is SQL Server's default READ COMMITTED different from Postgres's, and why does it matter operationally?
**Answer:** SQL Server's default READ COMMITTED is lock-based: a SELECT takes and releases shared locks row-by-row as it scans, an UPDATE/DELETE holds exclusive locks until commit, so readers and writers can block each other. Postgres's READ COMMITTED is MVCC-based from the start (new snapshot per statement, no locks for plain reads), so readers never block writers there by default. An engineer moving from Postgres to SQL Server who doesn't know this will be surprised the first time a report query blocks production writes.
**Follow-up trap:** *"Does enabling RCSI make SQL Server behave exactly like Postgres's READ COMMITTED?"* — very close in spirit (row versioning, no reader-writer blocking) but not identical in every anomaly guarantee or implementation detail; verify specific isolation-level behavior per database rather than assuming full equivalence once RCSI is on (see `T17-mvcc-isolation` for the general MVCC vs locking framework).

### Q8 — What does a columnstore index actually store differently from a rowstore B-tree, and why is that faster for aggregation?
**Answer:** Columnstore stores each column's values together, compressed, in per-column segments within rowgroups (up to ~1,048,576 rows), instead of storing full rows together. An aggregation touching 3 of a table's 40 columns only reads those 3 columns' compressed segments, versus a rowstore scan reading every column of every row regardless of which are needed; batch-mode execution (~900 rows processed per operator call instead of one row at a time) further amortizes CPU overhead on top of the storage-layout and compression wins.
**Follow-up trap:** *"So why not make every table a clustered columnstore index?"* — columnstore's unit of work (rowgroup/segment) is a poor fit for single-row point lookups and small frequent updates, which go through a delta-store buffering mechanism with its own overhead; a table serving heavy OLTP point traffic alongside analytics is better served by keeping the rowstore clustered index and adding a nonclustered columnstore index for the analytical path (operational analytics), not converting the whole table.

### Q9 — What is segment elimination and what has to be true for it to actually help?
**Answer:** Each columnstore segment carries min/max metadata per column; a query filtering on that column can skip segments whose min/max range can't satisfy the predicate without decompressing or reading them. It only helps when the data is physically ordered (or at least correlated) relative to the filtered column — a randomly-inserted timestamp gives every segment a similar min/max spread, so no segment can be safely skipped.
**Follow-up trap:** *"How would you fix a columnstore index that shows poor segment elimination?"* — rebuild it with `MAXDOP = 1` for a single ordered build pass, or periodically `REORGANIZE`/rebuild after DML has fragmented rowgroup ordering; this is the direct SQL Server analogue of ClickHouse needing physical correlation for BRIN-style pruning (see `T17-clickhouse`).

### Q10 — Explain the legacy vs new cardinality estimator distinction and why it's an interview-relevant gotcha.
**Answer:** SQL Server 2014 shipped a materially different CE model (activated at database compatibility level ≥120) with different assumptions about cross-predicate correlation than the legacy CE (compat level ≤110, or forced via trace flag 9481 / the `LEGACY_CARDINALITY_ESTIMATION` hint). Upgrading compatibility level on an old database can silently reshape plans across the whole workload, because the row estimates feeding every plan decision changed at once.
**Follow-up trap:** *"If the new CE is generally better, why would anyone stay on the old one?"* — "generally better" is an aggregate claim; a specific inherited, heavily-tuned database can have plans that were implicitly tuned around the legacy CE's specific biases, and a blanket upgrade can regress some of them even while improving others on average — the safe move is testing the real production query mix in a lower environment before flipping compatibility level, not trusting the aggregate claim for a specific workload.

### Q11 — Design the indexing and isolation strategy for an order-management system with heavy read reporting and a real-time write path, both against the same tables.
**Testing:** synthesizing several of the module's concepts into one design.
**Answer:** Keep the transactional path on the existing rowstore clustered index (narrow surrogate clustering key) with targeted covering nonclustered indexes for the hot OLTP queries; add a nonclustered columnstore index on the same table for the reporting/aggregation access pattern so it gets batch-mode execution and segment elimination without a separate ETL pipeline; enable RCSI (with tempdb properly sized) so long-running report queries against the columnstore or rowstore don't block the write path, and vice versa.
**Follow-up trap:** *"What happens to the NCCI's freshness relative to the OLTP writes?"* — an NCCI updates incrementally as the base table is written to (new rows go through a delta store before being compressed into the columnstore), so it stays transactionally consistent, but a very high insert rate against the NCCI's delta store can itself become a bottleneck worth monitoring, distinct from the rowstore write path's own cost.

### Q12 — A columnstore-backed fact table's insert rate has degraded over time. What do you check?
**Answer:** Whether the delta store (the row-store buffer that absorbs new inserts before they're compressed into a compressed rowgroup) has accumulated too many open/closed-but-unmerged rowgroups because background compression (the tuple mover) isn't keeping up with insert volume — directly analogous in shape to ClickHouse's "too many parts" failure (see `T17-clickhouse`), where writes are outpacing background consolidation.
**Follow-up trap:** *"How would you fix it operationally?"* — batch inserts into larger, less frequent operations where possible to reduce delta-store churn, or manually trigger `ALTER INDEX ... REORGANIZE` to force the tuple mover to catch up, rather than only waiting on the automatic background process.

---

## Red flags that fail you

- Saying "add an index" without knowing whether it needs to cover the query or will trigger key lookups.
- Believing parameter sniffing is a bug to "turn off" rather than a tradeoff with several named, cost-differentiated fixes.
- Not knowing that SQL Server's default READ COMMITTED is lock-based, unlike Postgres.
- Recommending RCSI without mentioning the tempdb version-store cost.
- Assuming a clustered columnstore index is a strict upgrade over a rowstore clustered index for any table.
- Not knowing that a GUID/wide clustering key bloats every nonclustered index on the table, not just itself.
- Treating "upgrade compatibility level" as a routine, risk-free maintenance action.

---

## Cheat card

```
CLUSTERED           leaf = actual row data, at most 1 per table, table w/o one = heap.
NONCLUSTERED         leaf stores CLUSTERING KEY as locator (not physical pointer) ->
                     wide/volatile clustering key bloats every nonclustered index.
KEY LOOKUP           2nd seek into clustered index for columns not in the nonclustered
                     index; past a row-count threshold, optimizer flips to a scan.
                     Fix: INCLUDE the needed columns (covering index).

PARAM SNIFFING       1 cached plan per query TEXT, shaped by FIRST call's parameter
                     value via histogram. Symptom: fast for months, suddenly slow for
                     ONE value, no code change. Diagnose: sys.dm_exec_query_stats +
                     estimated vs actual rows in the plan.
FIXES                OPTION(RECOMPILE)        - fresh plan/call, costs compile/call
                     OPTIMIZE FOR UNKNOWN     - 1 avg-case plan, cheap, mediocre both ends
                     local var assignment     - same effect as OPTIMIZE FOR UNKNOWN
                     plan guide               - hints code you can't edit; invisible risk
                     PSP optimization (2022, compat 160+) - multi-plan by param bucket,
                       EQUALITY predicates only

STATS                Histogram (200 steps) + density, auto-updates ~20% rows changed.
                     Stale stats = uniform bad estimates (vs sniffing = value-specific).
CE                   Legacy CE (compat <=110) vs new CE (compat >=120, SQL2014+).
                     Compat-level upgrade can silently reshape ALL plans -> test first.

ISOLATION            SQL Server default READ COMMITTED = LOCK-BASED (shared/exclusive),
                     readers/writers DO block each other -- unlike Postgres MVCC default.
RCSI                 READ_COMMITTED_SNAPSHOT ON -> row versioning, no reader/writer block.
                     Cost: old versions copied to TEMPDB version store -> size/stripe
                     tempdb FIRST.

COLUMNSTORE          Column-wise, compressed, rowgroups (~1,048,576 rows), per-column
                     SEGMENTS w/ min/max metadata -> SEGMENT ELIMINATION (skip segments).
                     BATCH MODE: ~900 rows/operator-call vs 1 row (row mode) -> 2-4x.
                     CCI replaces rowstore entirely; NCCI adds columnar alongside rowstore
                     (operational analytics: OLTP on rowstore, analytics on NCCI).
                     Segment elimination needs physical ORDER correlation (MAXDOP=1 build
                     or REORGANIZE) -- same requirement as ClickHouse BRIN-style pruning.
                     Bad fit: point lookups, small frequent updates (delta-store overhead).
```

## Sources

- [SQL Server Parameter Sniffing: What It Is and How to Fix It — Simple Talk](https://www.red-gate.com/simple-talk/databases/sql-server/t-sql-programming-sql-server/parameter-sniffing/) — accessed 2026-08-01
- [Parameter Sensitive Plan Optimization — Microsoft Learn](https://learn.microsoft.com/en-us/sql/relational-databases/performance/parameter-sensitive-plan-optimization?view=sql-server-ver17) — accessed 2026-08-01
- [Cardinality Estimation (SQL Server) — Microsoft Learn](https://learn.microsoft.com/en-us/sql/relational-databases/performance/cardinality-estimation-sql-server?view=sql-server-ver17) — accessed 2026-08-01
- [PSPO: How SQL Server 2022 Tries to Fix Parameter Sniffing — Brent Ozar Unlimited](https://www.brentozar.com/archive/2022/08/pspo-how-sql-server-2022-tries-to-fix-parameter-sniffing/) — accessed 2026-08-01
- [Snapshot Isolation in SQL Server — Microsoft Learn](https://learn.microsoft.com/en-us/dotnet/framework/data/adonet/sql/snapshot-isolation-in-sql-server) — accessed 2026-08-01
- [Use RCSI to tackle most locking and blocking issues in SQL Server — Michael J. Swart](https://michaeljswart.com/2022/11/use-rcsi-to-tackle-most-locking-and-blocking-issues-in-sql-server/) — accessed 2026-08-01
- [Columnstore indexes: Overview — Microsoft Learn](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/columnstore-indexes-overview?view=sql-server-ver17) — accessed 2026-08-01
- [Stairway to Columnstore Indexes Level 9: Batch Mode Execution — SQLServerCentral](https://www.sqlservercentral.com/steps/stairway-to-columnstore-indexes-level-9-batch-mode-execution) — accessed 2026-08-01
- [ColumnStore Segment Elimination — SQLpassion](https://www.sqlpassion.at/archive/2017/01/30/columnstore-segment-elimination/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
