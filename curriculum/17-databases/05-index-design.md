# Composite Order, Covering, Partial, GIN/GiST/BRIN, When Indexes Hurt

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2h · **Prereqs:** `T17-storage-engines`, `T17-query-planner` · **Updated:** 2026-07-26
> **Module id:** `T17-index-design` · **Tags:** internals

## The 30-second version

An index is a bet: you pay on every write (extra I/O to keep it current) so that a specific class of read gets cheap. Composite index column order matters because a B-Tree index is sorted left-to-right — put the equality-filtered, high-selectivity column first and the range-filtered or low-selectivity column last, because everything after the first range/inequality predicate in the key can no longer be used to narrow the scan, only to filter it. A covering index (or index-only scan in Postgres) answers a query entirely from the index's own leaf pages, skipping the heap/table fetch entirely, which is the single biggest win available to a read-heavy query once the WHERE clause is already using an index. Partial indexes (index only rows matching a condition) and expression indexes (index a computed value, not a raw column) exist because most tables have a hot subset or a derived predicate that a full-column index wastes space and write cost indexing for. Postgres ships five index types — B-tree (default, equality/range/sort), GIN (multi-valued: arrays, JSONB, full-text), GiST (geometric, ranges, nearest-neighbor, extensible), BRIN (huge naturally-ordered tables, tiny footprint), Hash (equality only, rarely the right choice over B-tree) — and picking wrong is a common, expensive mistake. Every index adds write cost to every INSERT/UPDATE/DELETE that touches an indexed column, and past some ratio of writes to reads, or once a table has enough marginal, overlapping, or never-used indexes, adding one more index makes the system slower, not faster — the senior skill is recognizing that boundary, not reflexively indexing every WHERE clause.

## Why this gets asked

Because "add an index" is the single most common wrong answer a junior engineer gives to "the query is slow," and the interviewer wants to know whether you understand indexes as a cost/benefit tradeoff rather than a free lunch. They've watched a well-intentioned index get added to fix one slow report query and then quietly double write latency on the hot path table it lived on, or watched a composite index with columns in the wrong order sit there completely unused while the planner does a sequential scan anyway. The follow-up they're listening for is whether you'd check `pg_stat_user_indexes` for unused indexes before adding a new one, and whether you know when an index actively makes the planner's job worse.

---

## Lineage: past → present → future

**What came before.** Early relational systems offered only a single, general-purpose index structure (typically a B-Tree/ISAM variant) applicable to any column, and the query optimizer had comparatively little to reason about: an index either existed on a column or it didn't, and it was usable for equality and range predicates only. This was adequate while data was overwhelmingly scalar (integers, short strings, dates), but it broke down as applications started storing data types a single B-Tree fundamentally cannot index well: free text (a B-Tree can't do "contains this word" efficiently), geometric/spatial data (a B-Tree's total ordering doesn't capture 2D proximity), arrays and semi-structured JSON (a B-Tree indexes a whole value, not "any element of this array equals X"), and huge append-mostly time-ordered tables where a full B-Tree's per-row overhead was disproportionate to the actual selectivity benefit. The pain that forced diversification: teams either denormalized into separate specialized systems (a search engine bolted on next to the relational database) or lived with full scans for entire classes of query, both expensive compromises.

**Where it stands now.** Postgres's answer — a pluggable index access method interface supporting B-tree, Hash, GiST, SP-GiST, GIN, and BRIN as of Postgres 18 — is the current reference design for "one database, several index structures matched to data shape," and it's now genuinely mainstream rather than a research curiosity: GIN-backed JSONB and full-text search, GiST-backed PostGIS spatial indexing, and BRIN-backed time-series tables are all common in production, not edge cases. The live disagreement is over **how far to push "one database, many index types" versus reaching for a dedicated system**: full-text search via Postgres GIN plus `tsvector` is genuinely good for moderate scale and avoids an extra moving part, but teams doing serious relevance-tuned search still reach for Elasticsearch/OpenSearch because GIN's text search is functionally more limited (no BM25 tuning, weaker fuzzy matching) — see `T17-elasticsearch`. Similarly, pgvector (HNSW/IVFFlat indexes for vector similarity, effectively a specialized GiST/access-method-style extension) competes directly with dedicated vector databases, and the honest answer is "it depends on scale and recall requirements," not a blanket recommendation either way. What's actually deployed at scale: covering indexes and index-only scans as a default optimization once a hot query is identified, partial indexes as the standard answer for "we always filter on `status = 'active'` and 95% of rows are not," and BRIN as an underused but high-leverage option for append-only, naturally-ordered tables that people reach for a B-Tree on by habit.

**Where it's heading.** Postgres 18 (released September 2025, current through 2026) added **skip scan** for multicolumn B-Tree indexes — allowing the planner to use an index efficiently even when the query omits an equality condition on a leading column, which historically forced a full index scan or sequential scan when only a later composite-index column was filtered. This directly softens (without eliminating) the long-standing "leading column must be in your WHERE clause" rule, and it's real and shipping, not speculative. More speculative: adaptive/self-tuning index advisors (automatically proposing or even creating/dropping indexes based on observed workload, as some managed cloud database services already do to varying degrees) are an active area, but "the database chooses your indexes for you reliably" is not yet something to assume works without verification across all workloads — treat autonomous index management as promising but unproven as a full replacement for a human doing `EXPLAIN ANALYZE`-driven tuning.

---

## Mental model

```
COMPOSITE INDEX (a, b, c) — sorted lexicographically by (a, b, c)

  a=1,b=1,c=1
  a=1,b=1,c=2
  a=1,b=2,c=1        <- within a=1, sorted by b, then c
  a=1,b=2,c=2
  a=2,b=1,c=1        <- a changes -> whole ordering "restarts"
  a=2,b=1,c=2
  ...

WHERE a=1 AND b=2            -> narrows to a contiguous slice: FAST, uses index fully
WHERE a=1 AND b>2             -> narrows on a, then a range scan on b: FAST, c UNUSABLE
                                 for narrowing (only for filtering within the b-range)
WHERE b=2                    -> a is not filtered -> index can't narrow at all
                                 (pre-PG18: full index scan or seq scan;
                                  PG18 skip scan: can now probe each a-value's b=2
                                  slice individually — real but not free, still costs
                                  one probe per distinct value of a)
WHERE a=1 AND c=1            -> narrows on a, but c is NOT adjacent to a in the sort
                                 order once b is unconstrained -> c can only FILTER,
                                 not narrow, within the a=1 slice
```

**The rule in one line:** everything in a composite index key before the first range/inequality predicate can narrow the scan; everything after it can only filter rows already found, at the cost of having still fetched and checked them.

---

## How it actually works

### Composite index column order

Given `CREATE INDEX ON orders (customer_id, status, created_at)`:

- `WHERE customer_id = 5 AND status = 'shipped'` — both are equalities, both narrow the scan to a tight, contiguous B-Tree range. Excellent.
- `WHERE customer_id = 5 AND created_at > '2026-01-01'` — `customer_id` narrows; `created_at` is a range on the *third* key column but `status` is unconstrained in between, so Postgres can still narrow reasonably well here because there's no gap in usable prefix — actually the real trap is when you skip a column: `WHERE customer_id = 5 AND created_at > X` with an index on `(customer_id, status, created_at)` **cannot use `created_at` to narrow at all** unless `status` is also constrained, because the key ordering only groups by `created_at` *within* a fixed `status` — this is the single most common composite-index mistake: assuming any subset of key columns is usable when in fact only a **left-anchored prefix, ending at the first range predicate,** is usable for narrowing.

The design rule: **put equality-filtered columns first (in any order relative to each other — cardinality/selectivity ordering barely matters for pure equalities since they all narrow to a point), put the single range-filtered column last**, and never expect a column after a range predicate to help narrow the scan — it only filters what's already been found, still paying the cost of reading each candidate row (or index entry) to check it.

### Covering indexes and index-only scans

A **covering index** includes every column a query needs — either as key columns or, in Postgres, as `INCLUDE`d payload columns that ride along in the leaf page without participating in the sort order:

```sql
-- key columns for the WHERE/ORDER BY, INCLUDE for SELECT-only columns
CREATE INDEX idx_orders_covering
  ON orders (customer_id, status)
  INCLUDE (total_amount, created_at);
```

If every column the query needs is present in the index, Postgres can perform an **index-only scan**: answer the query entirely from the index's leaf pages without touching the heap (the actual table storage) at all — provided the **visibility map** confirms the relevant heap pages have no dead/invisible tuples that need an MVCC check against the heap (see `03-mvcc-isolation.md`). This is the single biggest lever available for a hot read query once an index already exists: turning a normal index scan (one heap fetch per matching row, often a random I/O each) into an index-only scan (zero heap fetches) can be a **5-10x+ latency improvement** on a table where the heap doesn't fit in cache. `EXPLAIN ANALYZE` shows this directly: "Index Only Scan" plus "Heap Fetches: 0" is the target; a nonzero heap-fetch count under an index-only scan plan means the visibility map is stale (run `VACUUM`).

### Partial and expression indexes

A **partial index** indexes only rows matching a predicate:

```sql
-- 95% of rows are 'completed'; only 'pending' rows are ever queried by this path
CREATE INDEX idx_orders_pending ON orders (created_at) WHERE status = 'pending';
```

This index is a fraction of the size of a full-column index, costs write overhead only on rows matching the predicate (an UPDATE that keeps a row outside `WHERE status = 'pending'` never touches this index), and the planner will use it automatically for queries whose WHERE clause **implies** the partial index's condition — it does not require the query to literally repeat the predicate verbatim, but the planner's ability to prove implication is limited to fairly direct cases, so matching the predicate closely is the safe default.

An **expression index** indexes a computed value:

```sql
CREATE INDEX idx_users_lower_email ON users (lower(email));
-- now this can use the index:
SELECT * FROM users WHERE lower(email) = 'a@b.com';
```

Without the expression index, `WHERE lower(email) = ...` cannot use a plain index on `email` at all — the planner cannot infer that `lower(email) = X` implies anything about the raw, unindexed `email` values, so it falls back to a sequential scan regardless of an index existing on the underlying column.

### Postgres index types and when each applies

| Type | Structure | Use for | Notes |
|---|---|---|---|
| **B-tree** | Balanced tree, totally ordered | Equality, range, sort, the default for almost everything scalar | Supports skip scan (PG 18+) for some non-leading-column usage |
| **GIN** (Generalized Inverted Index) | Inverted index: value → list of row locations | Multi-valued columns: arrays (`@>`, `&&`), JSONB (`@>`, `?`), full-text (`tsvector @@ tsquery`) | Fast lookups (~3x faster than GiST) but ~3x slower to build and **high write overhead** — every INSERT can touch many inverted entries. Best for read-heavy, write-light data. `fastupdate` batches inserts into a pending list to soften this. |
| **GiST** (Generalized Search Tree) | Balanced tree, extensible via custom operator classes | Geometric/spatial (PostGIS), range types (`&&` overlap), nearest-neighbor (`<->`), full-text (alternative to GIN, faster to update, slower to query) | **Lossy**: can produce false-positive candidates the executor must recheck against the actual row. Faster to update than GIN, better for write-heavy dynamic data. |
| **BRIN** (Block Range Index) | Stores min/max (or similar summary) per physical block range, not per row | Huge tables physically correlated with the indexed column — e.g., a `created_at` column on an append-only, insert-ordered table | Tiny (megabytes, not gigabytes, for a huge table) and cheap to maintain, but **useless if the data isn't physically ordered** — a BRIN index on a column with random physical layout provides no pruning benefit at all |
| **Hash** | Hash table | Pure equality only, no range/sort | Rarely the right choice: B-tree handles equality just as well and additionally supports range/sort; Hash indexes became WAL-logged and crash-safe in Postgres 10+, removing their historical reliability disadvantage, but they still offer no real upside over B-tree for the vast majority of cases |

### Index write cost

Every index on a table adds overhead to every `INSERT`, and to every `UPDATE`/`DELETE` that touches an indexed column:

- Each index entry itself must be inserted/updated, which is its own B-Tree (or GIN/GiST/BRIN) write, with its own page-split and WAL-record cost (see `01-storage-engines.md`, `02-wal-recovery.md`).
- In Postgres specifically, an `UPDATE` that changes **any** indexed column disables **HOT (Heap-Only Tuple) optimization** for that update, forcing a full index update on every index on the table, not just the one covering the changed column — this is a specific, easy-to-miss multiplier: a table with 6 indexes and an UPDATE that touches one indexed column pays index-maintenance cost on all 6 if HOT can't apply (see `06-postgres.md` for HOT mechanics in depth).
- GIN indexes are the most expensive to maintain per write among Postgres's index types, since a single row can fan out into many inverted-index entries (one array with 20 elements touches ~20 entries).

Rule of thumb for whether an index is worth it: if a table sees far more writes than the query the index would serve, or if the query the index targets runs rarely and cheaply-enough via a sequential scan already (small table, or infrequent batch job), the write cost of maintaining the index across every write can exceed the aggregate read benefit.

### When an index makes things worse

- **Redundant/overlapping indexes.** An index on `(a, b)` already serves any query that only needs `a` — a separate index on just `(a)` is often pure write overhead with no read benefit, since the planner can use the leading-column prefix of the wider index. `pg_stat_user_indexes.idx_scan = 0` over a representative time window is the tell.
- **Too many indexes on a hot-write table.** Beyond some point, the planner also has more options to consider during planning (a real, if usually small, CPU cost), and every additional index compounds the write-amplification cost from the previous point.
- **An index the planner won't actually use.** Low-selectivity columns (a boolean, a status column with 3 values on a 10M-row table) rarely benefit from a B-Tree index at all — the planner correctly prefers a sequential scan once the estimated selectivity crosses roughly single-digit percent of the table, because random-access index-then-heap-fetch reads for that many rows cost more than one sequential pass. Building an index that the query planner then ignores is pure write cost for zero read benefit.
- **A composite index with the wrong leading column** for the actual query patterns in production — it exists, costs writes, and never gets used, which is worse than not existing, because at least a nonexistent index costs nothing.
- **Bloated indexes from update-heavy tables without adequate vacuuming** — an index can develop its own version of table bloat, growing in size without a proportional growth in useful entries, degrading both read and write performance until `REINDEX` or routine vacuum keeps it in check.

---

## Build it from scratch

A minimal demonstration of the composite-index-order mechanics using SQLite (small enough to reason about, same underlying B-Tree principle as Postgres):

```python
# untested sketch — illustrates composite index prefix usability, not production code
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("""
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        status TEXT,
        created_at TEXT
    )
""")
conn.execute("CREATE INDEX idx_composite ON orders (customer_id, status, created_at)")

# Populate with enough rows that SQLite's planner actually considers the index
import random
statuses = ["pending", "shipped", "completed"]
rows = [(i, random.randint(1, 1000), random.choice(statuses), f"2026-{(i%12)+1:02d}-01")
        for i in range(200_000)]
conn.executemany("INSERT INTO orders (id, customer_id, status, created_at) VALUES (?, ?, ?, ?)", rows)
conn.commit()

def explain(sql, params=()):
    plan = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    print(sql, "->", plan)

# Uses the full composite key: both customer_id and status narrow the scan
explain("SELECT * FROM orders WHERE customer_id = ? AND status = ?", (5, "pending"))

# customer_id narrows; created_at CANNOT narrow further because status is
# unconstrained in between — SQLite will use the index for customer_id only
explain("SELECT * FROM orders WHERE customer_id = ? AND created_at > ?", (5, "2026-06-01"))

# status alone: leading column customer_id is unconstrained, index is far less useful
explain("SELECT * FROM orders WHERE status = ?", ("pending",))
```

Running this and reading the `EXPLAIN QUERY PLAN` output for each case is the fastest way to build real intuition for prefix usability — the third query in particular usually falls back to a full index or table scan, visibly confirming the "leading column must be constrained" rule. Full version comparing Postgres `EXPLAIN ANALYZE` output (with buffer/timing) across B-tree, GIN, GiST, and BRIN on the same dataset: **`labs/py/05-index-lab/`**.

---

## How it's done in production

**Diagnosing index usage.** `pg_stat_user_indexes` (`idx_scan`, `idx_tup_read`, `idx_tup_fetch`) shows which indexes are actually being used; an index with `idx_scan = 0` after a representative production time window (a full week to capture batch jobs, not just an hour) is a strong candidate for removal. `pg_stat_statements` (see `06-postgres.md`) combined with `EXPLAIN ANALYZE` on the actual slow queries is the standard loop: identify the slow query, check if an index could serve it, check if one already exists but isn't being chosen (stale statistics — run `ANALYZE`), and only then consider adding a new one.

**Building indexes on production tables.** `CREATE INDEX CONCURRENTLY` builds an index without holding the exclusive lock that a plain `CREATE INDEX` takes for the whole build — critical on any table receiving concurrent writes, at the cost of a slower build (two full table scans instead of one) and the possibility of leaving behind an invalid, unusable index if the build is interrupted (which must then be manually dropped and retried).

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Query plan uses sequential scan despite a "matching" index existing | Composite index's leading column not constrained in the query, or stale statistics making the planner underestimate index benefit | Check prefix usability against actual WHERE clause; `ANALYZE` the table; verify with `EXPLAIN ANALYZE` estimated vs actual rows |
| Index-only scan plan still shows nonzero "Heap Fetches" | Visibility map stale — recently updated/inserted rows not yet marked all-visible | `VACUUM` the table; ensure autovacuum is keeping up (see `06-postgres.md`) |
| Write latency degrades after adding a new index to a hot-write table | New index adds per-write maintenance cost; if it disqualifies HOT updates, ALL indexes on the table now pay full maintenance cost per update | Verify whether the updated columns are indexed at all; consider whether the index needs to include that column, or restructure the update to avoid touching indexed columns unnecessarily |
| GIN index build or update is slow and CPU-heavy | Each row fans out into many inverted-index entries (large arrays/JSONB documents) | Enable `fastupdate` for a pending-list buffer on writes; batch bulk loads and build the index after loading rather than incrementally during load |
| BRIN index provides no speedup at all | Underlying data isn't physically correlated with the indexed column (e.g., random UUIDs, or a table that's been reorganized/vacuumed such that insertion order no longer matches the column's logical order) | Verify physical correlation (`pg_stats.correlation`); BRIN is only useful when correlation is high — otherwise use B-tree or accept a sequential scan |
| An index nobody remembers adding is never used but still costs write overhead | Query patterns changed after the index was added, or it was added speculatively "just in case" | Check `pg_stat_user_indexes.idx_scan` over a full representative period; drop with `DROP INDEX CONCURRENTLY` if genuinely unused |

---

## Tradeoffs & when NOT to use it

- **Do not add an index for a query that runs once a day against a small or already-fast-enough table.** The write-cost multiplier on every other write to that table is a permanent cost for an infrequent, already-acceptable read.
- **Do not index low-selectivity columns in isolation** (a boolean flag, a 3-value status column on a large table) — the planner will usually ignore a B-Tree index once selectivity is too weak to beat a sequential scan, making the index pure write overhead. A partial index on the *rare* value of that column is often the right shape instead.
- **Do not assume GIN is always right for JSONB.** GIN is expensive to maintain on write-heavy JSONB columns; if the workload is write-heavy and only a few known keys are ever queried, a set of targeted expression indexes on specific JSONB paths (`(data->>'status')`) can be cheaper than a single all-encompassing GIN index.
- **Do not use BRIN on data that isn't physically ordered.** It provides zero benefit and a false sense of having "an index" on the column.
- **Do not add a covering index with a wide `INCLUDE` list reflexively.** Every included column still needs to be kept current on every insert/update, and a covering index with many included columns can approach the size (and write cost) of a second copy of the table.
- **Composite index order should follow the actual, measured query patterns** (from `pg_stat_statements`), not a theoretical "most selective column first" rule applied without checking what the production WHERE clauses actually look like — the theory is a starting point, the query log is the ground truth.

---

## Interview questions

### Q1 — Why does composite index column order matter?
**Testing:** baseline.
**Answer:** A B-Tree composite index is sorted lexicographically by its key columns in order. Only a left-anchored prefix, ending at (and including) the first range/inequality predicate, can be used to narrow the scan; anything after that point can only filter already-found rows. Put equality-filtered columns first, the range-filtered column last.
**Follow-up trap:** *"Does it matter which order you put two equality columns in?"* — usually not for correctness or narrowing (both fully narrow to a point), but it can matter slightly for index size/compression and for whether the index can also serve queries filtering on only the first of the two columns — so put the column more likely to be queried alone first.

### Q2 — What is an index-only scan and what has to be true for Postgres to use one?
**Answer:** A scan that answers the query entirely from the index's own pages, with zero heap fetches — possible only if every column the query needs is in the index (key or INCLUDE) and the visibility map confirms the relevant heap pages have no rows needing an MVCC visibility check against the actual heap.
**Follow-up trap:** *"EXPLAIN ANALYZE shows 'Index Only Scan' but 'Heap Fetches: 4500' — is that actually an index-only scan?"* — technically the plan node is index-only, but a nonzero heap-fetch count means the visibility map was stale for many rows, so in practice it degraded toward a normal index scan for those rows; the fix is `VACUUM` and checking why autovacuum isn't keeping the visibility map current.

### Q3 — When is a partial index the right choice over a full index?
**Answer:** When queries consistently filter on a predicate matching a minority subset of the table's rows — index only that subset, getting a much smaller index (less disk, less write overhead, since rows outside the predicate never touch it) while still fully serving the queries that need it.
**Follow-up trap:** *"Does the query have to use the exact same predicate as the partial index for the planner to use it?"* — the planner needs to prove the query's WHERE clause implies the partial index's condition, which works reliably for exact or trivially-implied matches but is not a general theorem prover — writing the query's predicate to closely match the index's is the safe default rather than relying on the planner to infer non-obvious implications.

### Q4 — Compare GIN and GiST for indexing JSONB or full-text data.
**Answer:** GIN lookups are roughly 3x faster than GiST but take roughly 3x longer to build and have materially higher write overhead, since a single row can fan out into many inverted entries. GiST is lossy (can return false-positive candidates the executor must recheck) but faster to update, making it better for write-heavy, frequently-changing data; GIN is better for read-heavy, relatively static data.
**Follow-up trap:** *"What's `fastupdate` and why would you turn it off?"* — it's a GIN option that buffers new entries in a pending list rather than updating the main index structure immediately, trading some read overhead (checking the pending list too) for much cheaper writes; you'd disable it if read latency predictability matters more than write throughput, since pending-list checks add variance to read latency until the list is flushed.

### Q5 — What does BRIN buy you, and what's the one condition that makes it useless?
**Answer:** BRIN stores a summary (e.g., min/max) per physical block range rather than per row, giving a tiny index (megabytes vs gigabytes for a huge table) that can prune entire block ranges cheaply. It's useless if the data isn't physically correlated with the indexed column — if row order on disk doesn't track the column's logical order, the min/max per block range covers the whole value distribution and provides no pruning at all.
**Follow-up trap:** *"How do you check correlation before deciding?"* — `pg_stats.correlation` for the column, which ranges from -1 to 1; values near ±1 indicate strong physical ordering (good for BRIN), values near 0 mean BRIN won't help and a B-tree (or accepting a sequential scan on a truly huge table) is the real choice.

### Q6 — An UPDATE on a table with 6 indexes is slower than expected even though it only changes one indexed column. Why?
**Answer:** In Postgres, updating any indexed column disables HOT (Heap-Only Tuple) optimization for that row's update, which means the new row version needs a fresh entry in every index on the table, not just the one covering the changed column — so a single-column update pays the write cost of all 6 indexes, not 1.
**Follow-up trap:** *"How would you fix this without dropping indexes you need?"* — if the frequently-updated column doesn't need to be indexed at all, remove that specific index; if it does, consider whether the update pattern can be restructured (e.g., avoid touching that column on the hot path, or batch the updates) — there's no way to selectively update "only the relevant index" since HOT eligibility is per-row, not per-index.

### Q7 — How do you decide whether an existing index is safe to drop?
**Answer:** Check `pg_stat_user_indexes.idx_scan` over a representative time window long enough to capture periodic jobs (a week, not an hour) — an index with zero scans across that window is a strong candidate. Also check for redundancy: an index on `(a)` is often superseded by an index on `(a, b)`, since the planner can use the wider index's leading-column prefix.
**Follow-up trap:** *"What if a batch job runs quarterly and needs it?"* — this is exactly why a short observation window is dangerous; the real answer requires knowing the business's query cadence, not just a fixed lookback period, and when in doubt, `DROP INDEX CONCURRENTLY` combined with monitoring (not an irreversible drop with no rollback plan) is the safer operational move.

### Q8 — Design the indexing strategy for a `users` table queried both by exact email match and by `LOWER(email)` for case-insensitive login.
**Answer:** An expression index on `lower(email)` — a plain index on `email` cannot serve `WHERE lower(email) = X` because the planner can't infer that constraint implies anything about the raw column's sorted values. If exact-case lookups also happen, you may need both a plain index on `email` and an expression index on `lower(email)`, or normalize to always store/query the lowercase form and drop the plain index if exact-case lookups never actually occur in practice.
**Follow-up trap:** *"Isn't a citext column simpler?"* — yes, `citext` (case-insensitive text type) avoids needing an expression index at all by making equality inherently case-insensitive at the type level, but it changes comparison semantics for every query against that column, including ones that might have relied on case sensitivity, so it's a schema-level decision with broader blast radius than adding one expression index.

### Q9 — When does adding an index make a query planner's decisions worse, not just add write overhead?
**Answer:** Rarely, but it can happen when the planner has many similarly-costed index options and picks a suboptimal one due to imprecise statistics, especially on complex multi-join queries where more index choices expand the plan search space; this is uncommon compared to the dominant cost (write overhead and unused indexes) but real at high index counts on frequently-joined tables.
**Follow-up trap:** *"Isn't more planner choice always at least neutral?"* — not quite: on very large joins, Postgres's planner switches from exhaustive enumeration to a heuristic/genetic search past a threshold (`geqo_threshold`, default 12 relations), and a larger candidate index set can push cost estimation error into a worse-chosen heuristic plan more often than a smaller, well-curated index set would; this is a second-order effect, worth mentioning but not the primary reason to avoid over-indexing.

### Q10 — A table has an index on `(customer_id, status, created_at)`, and a common query is `WHERE created_at > X ORDER BY created_at`. Does the index help?
**Answer:** Barely, if at all — `customer_id` is unconstrained, so the composite index's ordering doesn't group rows usefully for this query; Postgres would need to scan the entire index (in `(customer_id, status, created_at)` order, which is not `created_at` order across different `customer_id`/`status` values) to find matching rows, which is generally worse than a sequential scan. A separate index on `(created_at)` alone would actually serve this query.
**Follow-up trap:** *"Postgres 18 has skip scan now — does that change the answer?"* — skip scan helps when a query omits an equality condition on a leading column but still filters on later columns; it doesn't help this specific case well, because the query isn't filtering on `customer_id` or `status` at all (not even an implicit "any value" probe pattern) — skip scan is most valuable when the leading column has low cardinality and you're willing to pay one probe per distinct leading value, not when the leading column is entirely absent from the query's intent.

### Q11 — Design the index strategy for a multi-tenant SaaS table where >99% of queries filter by `tenant_id` plus one other varying column.
**Testing:** applying composite-order theory to a realistic, resume-relevant scenario.
**Answer:** `tenant_id` as the leading column on every relevant composite index, since it's present in nearly every query and typically has decent cardinality across tenants, followed by the second most common filter column per query shape — likely several composite indexes, one per common `(tenant_id, X)` access pattern, rather than one giant index trying to serve all of them. Consider whether `tenant_id` should also be the physical clustering key (`CLUSTER` in Postgres, or physical partitioning by tenant) if cross-tenant scans never happen, which would let BRIN or partition pruning do even more of the work than a B-tree alone.
**Follow-up trap:** *"What if one tenant is 1000x larger than the others (a noisy-neighbor skew)?"* — a single shared `tenant_id`-leading index still works correctness-wise, but that tenant's queries dominate cache residency and I/O; at that point partitioning by tenant_id (or at least the largest tenants) turns a shared-index skew problem into physically isolated, independently-sized data structures, which is a bigger architectural decision than indexing alone can solve.

### Q12 — What's the single biggest performance lever available on a query that already uses an index efficiently, and why?
**Answer:** Making it an index-only scan via a covering index — this eliminates the per-row heap fetch entirely, which is often the dominant cost (a random I/O per matching row) even when the index scan itself was already narrow and efficient. On a table where the heap doesn't fit in cache, this can be a 5-10x+ latency improvement for no algorithmic change to the query itself.
**Follow-up trap:** *"So should every index just include every column, to maximize index-only-scan coverage?"* — no; every included column adds write-maintenance cost on every insert/update, and a covering index with a wide INCLUDE list starts to approximate a second full copy of the table's write cost. The right INCLUDE list is the minimal set of columns the specific hot query needs beyond the key columns, not "everything, just in case."

---

## Red flags that fail you

- Reaching for "add an index" as a reflex for any slow query without checking `EXPLAIN ANALYZE` first.
- Not knowing that a composite index's usable prefix stops at the first range predicate.
- Believing an index is always free once created — no mention of write cost.
- Confusing GIN and GiST, or not knowing GiST is lossy.
- Recommending BRIN without checking physical correlation.
- Not knowing what an index-only scan requires (visibility map, covering columns).
- Claiming HOT updates are unaffected by which column changed.

---

## Cheat card

```
COMPOSITE ORDER    equality columns first (any relative order), ONE range column last.
                   usable prefix = left-anchored, stops at first range/inequality predicate.
                   columns after that point only FILTER, never narrow.

COVERING/INDEX-ONLY   INCLUDE (col1, col2) rides in leaf pages, not in sort key.
                      needs: all needed cols present + visibility map current (VACUUM).
                      "Index Only Scan" + "Heap Fetches: 0" in EXPLAIN ANALYZE = the win.
                      can be 5-10x+ faster than normal index scan when heap doesn't fit cache.

PARTIAL INDEX      CREATE INDEX ... WHERE cond — indexes only matching rows.
                   tiny footprint + zero write cost for non-matching rows.
                   planner must PROVE query implies the WHERE cond — match it closely.

EXPRESSION INDEX   CREATE INDEX ... (lower(email)) — needed whenever query filters on
                   a FUNCTION of a column; plain column index cannot serve it.

PG INDEX TYPES     B-tree: default, equality/range/sort. Skip scan (PG18+) helps some
                     non-leading-column cases.
                   GIN: arrays, JSONB, full-text. ~3x faster lookup than GiST, ~3x
                     slower build, HIGH write overhead (many entries/row). fastupdate
                     buffers writes into a pending list.
                   GiST: geometric, ranges, KNN (<->), extensible. LOSSY (rechecks
                     candidates). Cheaper to update than GIN.
                   BRIN: min/max per BLOCK RANGE. Tiny. USELESS if data not physically
                     correlated with column (check pg_stats.correlation).
                   Hash: equality only, WAL-safe since PG10, rarely beats B-tree.

WRITE COST         every index = extra write per INSERT/UPDATE(indexed col)/DELETE.
                   Postgres HOT: updating ANY indexed column disables HOT for that row
                     -> ALL indexes on the table get maintained, not just the changed one.
                   GIN = most expensive per-write index type (fan-out per row).

WHEN INDEX HURTS   idx_scan = 0 in pg_stat_user_indexes over a full representative
                     window -> candidate for removal.
                   redundant index: (a) is subsumed by (a,b) via prefix usability.
                   low-selectivity column (few distinct values, large table) -> planner
                     ignores the index anyway; pure write cost, zero read benefit.
                   BRIN on uncorrelated data -> zero pruning benefit.

BUILD SAFELY       CREATE INDEX CONCURRENTLY — no exclusive lock, 2 table scans instead
                     of 1, can leave an INVALID index if interrupted (drop + retry).
```

## Sources

- [PostgreSQL 18 Documentation: Index Types](https://www.postgresql.org/docs/current/indexes-types.html) — accessed 2026-07-26
- [PostgreSQL Index Types: B-tree vs BRIN vs GIN — BSWEN](https://docs.bswen.com/blog/2026-04-20-postgresql-index-types-guide/) — accessed 2026-07-26
- [Understanding Postgres GIN Indexes: The Good and the Bad — pganalyze](https://pganalyze.com/blog/gin-index) — accessed 2026-07-26
- [PostgreSQL 18 Release Notes — Skip Scan](https://www.postgresql.org/docs/18/release-18.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
