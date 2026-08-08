# BigQuery: Slots, Partitioning, Clustering, Cost Control + 40 SQL Questions

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-bigquery` · **Tags:** platform,critical

## Why this gets asked

Somebody on the interview panel has seen a `SELECT *` on a multi-terabyte table land as a four-figure line item on a single afternoon, with no cluster to blame and no admin who approved it — because BigQuery makes it structurally easy to spend money by accident. The SQL-heavy half of this module gets asked because BigQuery interviews, more than any other warehouse's, tend to be pure SQL screens: window functions, arrays, and date logic under time pressure, because the platform's whole pitch is "you don't manage infrastructure, you write SQL," so that's what they test.

---

## Lineage: past → present → future

**What came before.** Google's internal Dremel system (2006, published 2010) solved interactive SQL over petabyte-scale columnar data without MapReduce's batch latency, using a distributed execution tree that fans a query out across thousands of leaf workers in parallel. Before Dremel-style engines, ad-hoc SQL at that scale meant waiting minutes-to-hours for a MapReduce or Hive job; Dremel's tree architecture returned interactive results in seconds. BigQuery (GA 2011) is Dremel exposed as a public, fully-managed product — no cluster to provision, ever, which was the genuinely novel part at the time.

**Where it stands now.** The core execution model hasn't fundamentally changed, but the pricing and control-plane story has matured a lot: **slots** (BigQuery's unit of query execution capacity) can be bought via **on-demand** (pay per byte scanned, no capacity commitment) or **capacity/reservations** (pay per slot-hour, predictable cost, workload isolation) [[Understand slots — BigQuery docs]](https://docs.cloud.google.com/bigquery/docs/slots). The live disagreement in practice is when to switch from on-demand to capacity — the commonly cited break-even is around **467 TiB scanned per month**, but that's a rule of thumb, not a law, and depends heavily on query patterns (bursty vs. steady). The **Storage Write API** has displaced the legacy streaming-insert API as the recommended ingestion path for high-throughput writes, offering exactly-once semantics and materially lower cost.

**Where it's heading.** Google keeps pushing more of the cost-control burden into the platform itself — BI Engine acceleration, materialized views that transparently rewrite queries, autoscaling reservations — rather than relying on engineers to hand-tune. Expect continued blurring between "warehouse" and "lakehouse" as BigQuery's BigLake layer extends native query support over externally-managed Iceberg tables on GCS, following the same catalog-interoperability trend as Databricks and Snowflake. Treat exact pricing figures in this module as a snapshot — Google revises BigQuery pricing more often than most vendors publicize clearly, so re-verify before quoting a number to a stakeholder.

---

## Mental model

```
   query submitted
         │
         ▼
   ┌──────────────┐        Dremel-style execution tree:
   │  MIXER nodes  │  ◀──  query plan fanned out across levels
   └──────────────┘
         │
         ▼
   ┌──────────────┐
   │ SHUFFLE nodes │  ◀──  intermediate results redistributed
   └──────────────┘
         │
         ▼
   ┌──────────────┐
   │  LEAF workers │  ◀──  read columnar storage (Capacitor format),
   │ (thousands)   │       each processes a slice in parallel
   └──────────────┘
         │
         ▼
   results aggregate back up the tree

   SLOTS = units of CPU/memory capacity consumed by leaf/mixer work.
   More slots = more of this tree runs in parallel = faster, not cheaper per se.
```

The billing model is orthogonal to this diagram: **on-demand** bills for bytes read off columnar storage regardless of how many slots that took; **capacity** bills for slot-hours regardless of bytes scanned. This is why partitioning/clustering (which reduce bytes scanned) save money under on-demand but save *time*, not directly money, under a fixed capacity reservation — a distinction interviewers specifically probe.

## How it actually works

### Slots, reservations, and the two pricing models

A **slot** is BigQuery's unit of query execution capacity (roughly, one worker's CPU+memory allocation). **On-demand pricing** charges **$6.25 per TiB scanned** (US regions), with the **first 1 TiB per month free**; you get no control over workload isolation, and busy periods pull from a shared, unpredictable slot pool. **Capacity pricing** charges **$0.04/slot-hour (Standard edition)** or **$0.06/slot-hour (Enterprise edition)**, giving predictable cost and, on Enterprise, **idle slot sharing** so unused reserved capacity is available to other workloads in the org rather than sitting wasted [[BigQuery pricing]](https://cloud.google.com/bigquery/pricing). The commonly cited break-even between the two models is around **467 TiB scanned per month** — below that, on-demand is typically cheaper; above it, reservations usually win, though bursty vs. steady query patterns shift this in practice.

### Partitioning and clustering — the cost math, with real numbers

Partitioning (commonly by `DATE`/`TIMESTAMP` column, or ingestion time) lets BigQuery skip entire partitions that can't match a query's date filter, exactly analogous to Snowflake's micro-partition pruning but at a coarser, user-defined granularity. Clustering (up to 4 columns) sorts data within each partition so range/equality filters on clustered columns skip blocks within the partition too.

The numbers make the case better than the theory: a `SELECT *` scanning an entire **500GB** partitioned table costs about **$3.13**; scanning only the 3 needed columns from that same table (roughly 30GB) costs about **$0.19** — columns you don't select are never billed under BigQuery's columnar storage model, so column pruning alone is a **~16x** cost reduction here [[BigQuery cost optimization]](https://medium.com/@cocamatias/bigquery-cost-optimization-the-complete-guide-for-growing-companies-9951bd46a64c). More dramatically, a naive `SELECT *` on a **10TB** unpartitioned table costs **$62.50** in one query [[LeanOps: One BigQuery SELECT * Cost $62.50]](https://leanopstech.com/blog/google-bigquery-pricing-2026/). Combining partitioning and clustering on a well-targeted query typically reduces bytes scanned by **90-99%** versus a full scan — on a 1TB table, a well-targeted query might scan 1-10GB instead of the full terabyte.

The single most common interview-relevant mistake: `SELECT *` is expensive specifically because BigQuery is columnar — every column you name gets read and billed, so `SELECT *` bills for every column in the table regardless of how many you'll actually use downstream.

### Storage pricing and the long-term discount

Active storage (any table/partition modified in the last 90 days) costs **$0.02/GB/month**. A table or partition **untouched for 90+ consecutive days** automatically drops to **$0.01/GB/month** — a **50% discount**, applied with zero configuration required. Critically, this is evaluated **per partition**, not per table: a partitioned table with old, cold partitions and a hot current-month partition gets the discount on the cold partitions individually while the hot one stays at full price. Any write to a partition resets its 90-day clock back to zero [[BigQuery storage pricing]](https://www.revefi.com/blog/google-bigquery-cost-optimization).

### Materialized views and BI Engine

**Materialized views** precompute and store the result of a defined aggregation/query; when a subsequent query can be served (fully or partially) from the materialized view, BigQuery bills only for the bytes in the materialized view, not the full underlying source table — often an order-of-magnitude cost reduction for frequently-repeated aggregation queries. They're not instantaneously consistent with streaming writes to the base table, but BigQuery transparently merges the materialized view's precomputed portion with a small delta read from the base table to keep results correct.

**BI Engine** is an in-memory acceleration layer for dashboards (Looker Studio, Looker, custom BI tools) that caches hot data for sub-second interactive queries, reducing both latency and the marginal cost of repeated dashboard queries hitting the same data.

### Streaming inserts vs. the Storage Write API

The legacy streaming-insert API is still available but the **Storage Write API** is the recommended path for anything beyond trivial volume: it offers **exactly-once semantics** when using stream offsets (the legacy API only offers at-least-once, requiring manual dedup), better throughput, and lower cost — **$0.025/GB** for committed throughput, with the **first 2 TiB/month free** [[BigQuery Storage Write API]](https://oneuptime.com/blog/post/2026-02-17-how-to-stream-data-into-bigquery-using-the-storage-write-api/view). The observable failure mode of sticking with the legacy API at scale: duplicate rows downstream from at-least-once delivery, silently inflating aggregates until someone notices totals don't reconcile.

---

## Build it from scratch

A cost-estimator, the mental model an interviewer might ask you to reason through live:

```python
# untested sketch
def estimate_query_cost(table_size_gb, columns_selected, total_columns,
                         partitions_total, partitions_matched, on_demand=True):
    """Rough BigQuery on-demand cost model: partition pruning first,
    then column pruning within the columnar format."""
    column_fraction = columns_selected / total_columns
    partition_fraction = partitions_matched / partitions_total if partitions_total else 1.0
    bytes_scanned_gb = table_size_gb * column_fraction * partition_fraction
    tib_scanned = bytes_scanned_gb / 1024
    free_tib = 1.0  # first 1 TiB/month free, ignored here for a single-query estimate
    rate_per_tib = 6.25
    return round(tib_scanned * rate_per_tib, 2)

# SELECT * on unpartitioned 500GB table, all columns, no partition pruning
print(estimate_query_cost(500, 20, 20, 1, 1))       # ~$3.13-ish scale
# 3 of 20 columns, partitioned table hitting 1 of 30 daily partitions
print(estimate_query_cost(500, 3, 20, 30, 1))       # a small fraction of a cent
```

---

## How it's done in production

BigQuery is fully managed — there's no self-hosted alternative to compare, which changes the "production" lens to cost governance and query-pattern discipline rather than infrastructure operations.

| Symptom | Cause | Fix |
|---|---|---|
| Single query costs tens of dollars unexpectedly | `SELECT *` on a large unpartitioned/unclustered table | Enforce column selection discipline; add partitioning/clustering on large tables; use dry-run cost estimates in CI |
| Monthly bill wildly unpredictable month to month | On-demand pricing with growing/bursty scan volume | Evaluate capacity/reservation pricing once consistently near or above the ~467 TiB/month break-even |
| Streaming pipeline shows inflated aggregate totals | Legacy streaming-insert API's at-least-once delivery producing duplicates | Migrate to Storage Write API with stream offsets for exactly-once semantics |
| Dashboard query cost stays high despite no data growth | Repeated identical aggregation queries hitting the base table every time | Add a materialized view for the aggregation; enable BI Engine for the dashboard's hot tables |
| Storage cost doesn't drop for supposedly "cold" data | Table (not partition-level) is being touched by routine jobs (e.g., a metadata `UPDATE` on the whole table) resetting the 90-day clock | Ensure updates are scoped to specific partitions; verify via `INFORMATION_SCHEMA.PARTITIONS` last-modified time |
| Query plan shows "shuffle" as the dominant cost/time | Large join or `GROUP BY` redistributing more data across the network than necessary | Filter/aggregate earlier in the query; check join order and whether a broadcast-style join applies |
| Capacity reservation queries queue during peak hours | Reservation sized below actual peak concurrent slot demand, no autoscaling configured | Enable reservation autoscaling, or size baseline slots to typical (not just average) peak |

---

## Tradeoffs & when NOT to use it

- **BigQuery is usually the wrong choice when you need fine-grained compute isolation between tenants/workloads on the default on-demand model** — a noisy, expensive ad-hoc query can, in principle, compete with others on the shared on-demand slot pool; reservations mitigate this but add back the capacity-planning burden BigQuery was chosen to avoid in the first place.
- **Do not use on-demand pricing blind at meaningful scale.** Past the ~467 TiB/month rough break-even, capacity pricing is very likely cheaper — teams that never revisit this after initial adoption systematically overpay.
- **Materialized views are the wrong tool for highly ad-hoc, unpredictable query shapes** — they only help when a specific aggregation pattern repeats; investing in one for a one-off report is wasted engineering.
- **Not on GCP, or need multi-cloud?** BigQuery is a GCP product; there's no serious on-prem or other-cloud deployment story, unlike Databricks and Snowflake which run on all three major clouds.
- **Nested/repeated fields (`ARRAY`/`STRUCT`) are powerful but a real complexity cost** — over-nesting data that's frequently joined flat elsewhere in the stack creates a modeling mismatch; know when to normalize into separate tables instead of nesting everything because "BigQuery supports it."

---

## Interview questions

The first section covers architecture and cost; the SQL bank that follows is the bulk of what actually gets asked in a BigQuery-specific screen, escalating from warmup through staff.

### Q1 — Explain the two BigQuery pricing models and how you'd decide between them for a real team.
**Testing:** baseline cost-model literacy.
**Answer:** On-demand bills $6.25/TiB scanned with no capacity commitment and no workload isolation; capacity/reservations bill $0.04-0.06/slot-hour with predictable cost and isolation between workloads. The rough break-even is around 467 TiB scanned/month; below that on-demand tends to be cheaper, above it reservations usually win, though bursty workloads can favor on-demand even above that threshold since you're not paying for idle reserved slots during quiet periods.
**Follow-up trap:** *"Your team scans 600 TiB/month but it's all concentrated in a 2-hour nightly batch window. Do you still recommend reservations?"* — maybe not a fixed baseline reservation; autoscaling reservations that spin up only during that window, or a flex-slot commitment, capture the capacity-pricing benefit without paying for 22 idle hours a day — a fixed-size reservation sized for that peak would be wasteful the rest of the day.

### Q2 — Why does `SELECT *` cost more than `SELECT col1, col2, col3`, mechanically?
**Answer:** BigQuery stores data in a columnar format (Capacitor); a query only reads and bills for the columns actually referenced. `SELECT *` forces every column to be read regardless of downstream use. On real numbers, this is the difference between a 500GB table costing $3.13 to fully scan versus $0.19 for a 3-column subset — roughly a 16x difference from column selection alone, before any partition pruning.
**Follow-up trap:** *"Does `LIMIT 10` reduce the cost of a `SELECT *`?"* — no. `LIMIT` reduces rows *returned*, not bytes *scanned*; BigQuery still reads all matching columns across all matching partitions before applying the limit, so a `SELECT * ... LIMIT 10` on a 10TB table still costs the full scan.

### Q3 — What's the practical difference between partitioning and clustering, and can you use both?
**Answer:** Partitioning splits a table into physically separate segments (commonly by date), letting BigQuery skip entire partitions outright based on a filter. Clustering sorts rows within each partition by up to 4 columns, letting BigQuery skip blocks *within* a partition for range/equality filters on those columns. Yes, and it's the recommended combination for large tables — partition first for coarse pruning, cluster for finer-grained skipping within the relevant partitions, typically reducing bytes scanned by 90-99% for well-targeted queries versus a full scan.
**Follow-up trap:** *"Your partitioned+clustered table's query still scans 80% of the table. What's wrong?"* — the query's filter predicate probably doesn't align with the partition/cluster columns (e.g., filtering on a different date field than the partitioning column, or filtering on a column that isn't among the clustered ones), so pruning can't engage. Check `EXPLAIN`/the query execution details for the actual bytes-processed breakdown before assuming clustering is broken.

---

### SQL question bank (warmup → staff, ~40 questions)

#### Warmup

**Q4 — Rank the last 5 transactions per customer by timestamp.**
**Testing:** basic window function fluency.
**Answer:** `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY txn_ts DESC)` filtered to `<= 5`, typically via `QUALIFY` to avoid a wrapping subquery: `SELECT * FROM txns QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY txn_ts DESC) <= 5`.
**Follow-up trap:** *"What if two transactions have the exact same timestamp?"* — `ROW_NUMBER()` breaks ties arbitrarily (order not guaranteed without a tiebreaker); add a secondary `ORDER BY` key (e.g., transaction ID) for deterministic results, or use `RANK()`/`DENSE_RANK()` if ties should be treated as the same rank.

**Q5 — What does `QUALIFY` do and why is it useful over a subquery?**
**Answer:** `QUALIFY` filters rows based on window function results directly, the way `HAVING` filters based on aggregates, avoiding a wrapping `SELECT ... FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn) WHERE rn = 1` pattern.
**Follow-up trap:** *"Can you use `QUALIFY` without a `WHERE` clause present?"* — yes, `QUALIFY` doesn't depend on `WHERE` being present; it's evaluated after window functions regardless.

**Q6 — Deduplicate a table keeping only the most recent row per `id`.**
**Answer:** `SELECT * EXCEPT(rn) FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) AS rn FROM t) WHERE rn = 1` or the `QUALIFY` equivalent.
**Follow-up trap:** *"What if `updated_at` can be NULL?"* — `ORDER BY updated_at DESC` puts `NULL`s first in BigQuery's default null ordering for descending sort in some engines — always check/explicit with `NULLS LAST` if recency logic depends on it, since silent NULL-ordering bugs are a common source of "wrong row survived dedup."

**Q7 — Write a query to get the first and last event per session using window functions.**
**Answer:** `FIRST_VALUE(event) OVER (PARTITION BY session_id ORDER BY ts) AS first_event, LAST_VALUE(event) OVER (PARTITION BY session_id ORDER BY ts RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_event`.
**Follow-up trap:** *"Why did `LAST_VALUE` return the current row instead of the actual last row?"* — the default window frame is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, so without explicitly extending the frame to `UNBOUNDED FOLLOWING`, `LAST_VALUE` just returns the current row every time. This is one of the most common silent bugs in window-function SQL.

**Q8 — Extract year, month, and day-of-week from a `TIMESTAMP` column.**
**Answer:** `EXTRACT(YEAR FROM ts)`, `EXTRACT(MONTH FROM ts)`, `EXTRACT(DAYOFWEEK FROM ts)` (1=Sunday through 7=Saturday in BigQuery's convention).
**Follow-up trap:** *"Your day-of-week logic is off by one compared to Python's `datetime.weekday()`. Why?"* — BigQuery's `DAYOFWEEK` is 1-indexed starting Sunday; Python's `weekday()` is 0-indexed starting Monday. Mismatched conventions between the warehouse and the application layer are a classic off-by-one source.

**Q9 — Compute a running total of daily revenue.**
**Answer:** `SUM(revenue) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`.
**Follow-up trap:** *"Would `RANGE` instead of `ROWS` change the result if there are duplicate `day` values?"* — yes: `RANGE` includes all peer rows with the same `ORDER BY` value in the frame, so duplicate days would each see the full sum of all rows sharing that day, not a strict row-by-row running total. `ROWS` is the correct choice for a true row-by-row running total.

**Q10 — Flatten an `ARRAY<STRUCT<...>>` column into one row per array element.**
**Answer:** `SELECT t.id, item.sku, item.qty FROM orders t, UNNEST(t.line_items) AS item`.
**Follow-up trap:** *"What happens to rows where `line_items` is an empty array?"* — a plain (inner) `UNNEST` via comma-join drops those rows entirely, since an empty array produces zero output rows. Use `LEFT JOIN UNNEST(...)` to preserve the parent row with `NULL`s when the array is empty.

**Q11 — Write a query to count distinct users per day.**
**Answer:** `SELECT day, COUNT(DISTINCT user_id) FROM events GROUP BY day`.
**Follow-up trap:** *"This is slow on a huge table. What's the approximate alternative and the tradeoff?"* — `APPROX_COUNT_DISTINCT(user_id)`, using HyperLogLog++ under the hood, trades exact precision for dramatically less compute/memory on very high-cardinality columns — appropriate for dashboards, not for a billing reconciliation report.

**Q12 — Find all rows where a column value changed from the previous row per `id`, ordered by time.**
**Answer:** `LAG(status) OVER (PARTITION BY id ORDER BY ts) AS prev_status`, then filter `WHERE status != prev_status OR prev_status IS NULL`.
**Follow-up trap:** *"You get spurious 'changes' at the very first row per `id`. Why, and is that correct?"* — the first row per partition has `prev_status = NULL`, so `status != prev_status` is `NULL` (not `TRUE`) in three-valued SQL logic, meaning it's silently excluded rather than included unless you explicitly add `OR prev_status IS NULL` — a real, easy-to-miss NULL-comparison trap.

**Q13 — Convert a `STRING` column of comma-separated values into an array and count elements.**
**Answer:** `SELECT id, ARRAY_LENGTH(SPLIT(tags, ',')) FROM t`.
**Follow-up trap:** *"An empty string in `tags` gives a count of 1, not 0. Why?"* — `SPLIT('', ',')` returns an array with one empty-string element, not an empty array; you need an explicit case for empty/NULL input if zero-tags rows must report 0.

#### Mid

**Q14 — Sessionize events: group events into sessions where a gap of more than 30 minutes starts a new session.**
**Testing:** the classic sessionization pattern, gaps-and-islands' sibling problem.
**Answer:** Compute the time since the previous event per user with `LAG`, flag a new session when the gap exceeds 30 minutes, then use a running `SUM` of that flag as the session ID: `WITH gaps AS (SELECT *, TIMESTAMP_DIFF(ts, LAG(ts) OVER (PARTITION BY user_id ORDER BY ts), MINUTE) AS gap_min FROM events) SELECT *, SUM(CASE WHEN gap_min IS NULL OR gap_min > 30 THEN 1 ELSE 0 END) OVER (PARTITION BY user_id ORDER BY ts) AS session_id FROM gaps`.
**Follow-up trap:** *"Sessions computed this way don't match what the product team reports. Why?"* — check whether their definition uses a *sliding* 30-minute inactivity window (this pattern) versus a *fixed* session length cap, or whether they also cap maximum session duration regardless of activity — sessionization definitions vary and silently disagreeing on the definition, not the SQL, is usually the real bug.

**Q15 — Classic gaps-and-islands: find consecutive date ranges of active subscription per user.**
**Answer:** Assign a group number by subtracting a row number (ordered by date) from the date itself — `DATE_SUB(active_date, INTERVAL ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY active_date) DAY)` produces a constant value for each consecutive run of dates; group by that constant to collapse each island into one row with `MIN(active_date)` and `MAX(active_date)`.
**Follow-up trap:** *"This breaks if a user has duplicate `active_date` rows. Why, and how do you fix it?"* — duplicate dates throw off the row-number-to-date offset alignment, producing incorrect groupings. Deduplicate `active_date` per user first (e.g., `SELECT DISTINCT`) before applying the row-number trick.

**Q16 — Pivot a long table (`user_id, month, revenue`) into wide format (one column per month).**
**Answer:** `SELECT user_id, SUM(IF(month = 'Jan', revenue, 0)) AS jan, SUM(IF(month = 'Feb', revenue, 0)) AS feb, ... FROM t GROUP BY user_id`, or BigQuery's native `PIVOT` operator: `SELECT * FROM t PIVOT (SUM(revenue) FOR month IN ('Jan', 'Feb', ...))`.
**Follow-up trap:** *"The month list isn't known ahead of time — how do you pivot dynamically?"* — BigQuery's `PIVOT` requires a static, known list of values at query-write time; true dynamic pivoting needs a generated/scripted query (build the SQL string with the distinct month list first, then execute it), since BigQuery SQL alone can't pivot on values unknown until runtime.

**Q17 — Unpivot a wide table (columns `jan, feb, mar`) back into long format.**
**Answer:** `SELECT user_id, month, revenue FROM t UNPIVOT (revenue FOR month IN (jan, feb, mar))`.
**Follow-up trap:** *"What happens to rows where a given month's value is NULL?"* — `UNPIVOT` by default excludes NULL values from the output (no row produced for that month); use `UNPIVOT INCLUDE NULLS` if you need explicit NULL rows preserved for that user/month combination.

**Q18 — Generate a row for every date in a range, even dates with no data, to fill gaps in a daily metric.**
**Testing:** the date-range-expansion problem named explicitly in the spec.
**Answer:** `SELECT day FROM UNNEST(GENERATE_DATE_ARRAY('2026-01-01', '2026-01-31')) AS day` as a spine, then `LEFT JOIN` your actual metric table on date, coalescing missing values to 0.
**Follow-up trap:** *"Your report shows a discontinuity at month boundaries when you union monthly spines from different queries. Why?"* — likely an off-by-one at the boundary (inclusive/exclusive end date mismatch between two `GENERATE_DATE_ARRAY` calls) or a timezone mismatch between the stored `TIMESTAMP` and the `DATE` spine — always confirm whether the underlying event timestamps are in UTC before truncating to `DATE`.

**Q19 — Expand a table of `(user_id, start_date, end_date)` subscription intervals into one row per active day per user.**
**Answer:** Cross join each row against `GENERATE_DATE_ARRAY(start_date, end_date)` via `UNNEST`: `SELECT user_id, day FROM subs, UNNEST(GENERATE_DATE_ARRAY(start_date, end_date)) AS day`.
**Follow-up trap:** *"This query is extremely slow and expensive on a large subscriptions table. Why, and what's the fix?"* — expanding wide date ranges (e.g., a multi-year subscription) into per-day rows can blow up row counts enormously before any filtering happens; if you only need aggregated metrics (active-user-count per month), aggregate via interval-overlap logic instead of materializing every day, or bound the expansion to a much narrower window with an early filter.

**Q20 — Compute a 7-day moving average of daily revenue.**
**Answer:** `AVG(revenue) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)`.
**Follow-up trap:** *"Day 1-6 of the dataset show artificially low averages. Is that a bug?"* — no, it's expected: at the start of the window there aren't 6 prior rows yet, so the frame silently uses however many rows exist. Whether that's acceptable depends on the use case — for a genuinely comparable 7-day average, you may need to explicitly exclude rows until a full 7-day window exists.

**Q21 — Find users who purchased in January but not in February (classic "existed, then churned" pattern).**
**Answer:** `SELECT jan.user_id FROM (SELECT DISTINCT user_id FROM orders WHERE month = 'Jan') jan LEFT JOIN (SELECT DISTINCT user_id FROM orders WHERE month = 'Feb') feb ON jan.user_id = feb.user_id WHERE feb.user_id IS NULL`.
**Follow-up trap:** *"Would `NOT IN` work the same way here?"* — only if the February subquery's `user_id` column can never contain `NULL`; if it can, `NOT IN` against a list containing even one `NULL` makes the whole condition evaluate to unknown for every row, silently returning zero rows. The anti-join (`LEFT JOIN ... IS NULL`) pattern above is safer specifically because it avoids that NULL trap.

**Q22 — Compute the percentile rank of each customer's total spend.**
**Answer:** `PERCENT_RANK() OVER (ORDER BY total_spend)` for a 0-to-1 rank, or `NTILE(100) OVER (ORDER BY total_spend)` for discrete percentile buckets.
**Follow-up trap:** *"`PERCENT_RANK` and `NTILE(100)` give different-looking results for the same data. Why?"* — `PERCENT_RANK` computes `(rank - 1) / (total_rows - 1)`, a continuous value based on rank, while `NTILE` divides rows into exactly N buckets by count, which handles ties and uneven group sizes differently — they answer related but distinct questions ("what fraction of rows rank below me" vs. "which bucket of N equal-size groups am I in").

**Q23 — Aggregate an array column: sum all quantities across all `line_items` per order without unnesting into separate rows.**
**Answer:** `SELECT id, (SELECT SUM(item.qty) FROM UNNEST(line_items) AS item) AS total_qty FROM orders` — a correlated subquery with `UNNEST`, keeping one output row per order.
**Follow-up trap:** *"Why not just `UNNEST` in the `FROM` clause and `GROUP BY` order id?"* — that works too, but requires a `GROUP BY` and re-aggregating every other order-level column; the correlated-subquery form is often cleaner when you only need the one aggregate and want to keep all other order columns un-grouped.

**Q24 — Find the second-highest purchase per customer, handling ties correctly.**
**Answer:** `DENSE_RANK() OVER (PARTITION BY customer_id ORDER BY amount DESC)` filtered to rank `= 2`, using `QUALIFY`.
**Follow-up trap:** *"Why `DENSE_RANK` instead of `ROW_NUMBER` here?"* — if two purchases tie for the highest amount, `ROW_NUMBER` arbitrarily assigns one of them rank 2 (calling a tied-for-first purchase "second highest," which is wrong); `DENSE_RANK` correctly assigns both a rank of 1 and moves the next distinct amount to rank 2.

**Q25 — Write a query using a `STRUCT` to return a nested object per row instead of flat columns.**
**Answer:** `SELECT id, STRUCT(name, email AS contact_email) AS customer_info FROM customers` — produces a nested field accessible as `customer_info.name` downstream.
**Follow-up trap:** *"When would you actually want this over flat columns?"* — when the output feeds an application that consumes nested JSON directly (an API response, an event payload) rather than another flat SQL query — nesting for its own sake inside a purely relational pipeline just adds `UNNEST` overhead later for no benefit.

#### Staff

**Q26 — Design a query to compute month-over-month cohort retention (percentage of users active in signup month N who are still active in month N+k).**
**Testing:** multi-step analytical SQL under a real business framing.
**Answer:** Build a cohort table (`user_id`, `cohort_month` = signup month), join to an activity table on `user_id`, compute `DATE_DIFF(activity_month, cohort_month, MONTH)` as the offset `k`, then `COUNT(DISTINCT user_id)` per `(cohort_month, k)` divided by the cohort's total size at `k=0`.
**Follow-up trap:** *"Retention numbers look impossibly high for large `k`. What's the likely bug?"* — often a fan-out from joining activity events (many rows per user per month) without deduplicating to one row per `(user_id, month)` before counting, or forgetting to filter `k >= 0` and picking up pre-signup "activity" from backfilled data.

**Q27 — Rewrite a query that currently uses a correlated subquery per row as a window function for performance, and explain why the rewrite helps.**
**Answer:** A correlated subquery (e.g., `SELECT id, (SELECT MAX(amount) FROM orders o2 WHERE o2.customer_id = o1.customer_id) FROM orders o1`) re-scans/re-aggregates per outer row; the window-function equivalent, `MAX(amount) OVER (PARTITION BY customer_id)`, computes the aggregate once per partition in a single pass. On a large table this is the difference between roughly quadratic-feeling work and a single sorted/partitioned scan.
**Follow-up trap:** *"BigQuery's optimizer is supposed to handle this automatically — does the rewrite still matter?"* — modern query optimizers can sometimes flatten simple correlated subqueries into equivalent joins, but this isn't guaranteed for all patterns, and relying on optimizer magic instead of writing the efficient form directly is a fragile assumption to build a cost-sensitive pipeline on — check the actual query execution plan rather than assuming.

**Q28 — A query's execution details show most of the time in "repartition"/shuffle stages. Diagnose and fix.**
**Answer:** A large `JOIN` or `GROUP BY` is redistributing a large volume of data across workers because the join/group keys have high cardinality or skew, or because a large table is being joined without any filtering applied first. Fix by filtering/aggregating as early as possible before the join, checking for a heavily skewed key (one value dominating the distribution, causing one worker to do disproportionate work), and confirming smaller dimension tables are actually small enough to broadcast rather than shuffle.
**Follow-up trap:** *"One specific key value is responsible for 90% of the shuffle volume. What do you do?"* — this is join-key skew; consider salting the skewed key (splitting it into sub-keys to spread the work) or handling that one hot value with a separate, simpler code path rather than forcing the general join to absorb the skew.

**Q29 — Design a schema decision: nested `ARRAY<STRUCT>` line items inside an `orders` table, versus a separate flat `order_items` table. When does each win?**
**Answer:** Nested wins when line items are almost always read together with their parent order and rarely joined against other tables independently — it avoids a join and keeps related data physically co-located, which BigQuery's columnar+nested storage handles natively and efficiently. A flat table wins when line items need independent, frequent joins to other dimension tables (product catalog, inventory), need independent partitioning/clustering, or are updated/appended at a very different cadence than the parent order.
**Follow-up trap:** *"Your nested-array design needs frequent `UPDATE`s to individual line items. What's the problem?"* — updating a single element inside a repeated/nested field in BigQuery effectively requires rewriting the whole row (and often the whole affected partition depending on the mutation), which is far more expensive than updating a row in a flat table with a normal `UPDATE ... WHERE`. High-mutation-rate nested fields are a real anti-pattern.

**Q30 — Explain how you'd detect and prevent a `SELECT *` regression from reaching production, at the CI/pipeline level, not just via code review.**
**Answer:** Use `--dry_run` (or the equivalent API `dryRun` flag) in CI to get BigQuery's estimated bytes-to-be-processed for any new/changed query before it merges, and fail the build if a query's estimated cost exceeds a threshold or if it references `SELECT *` on a table above a configured size threshold via a linter rule on the SQL text itself.
**Follow-up trap:** *"A dry-run estimate says a query is cheap, but production cost is 50x higher. Why might dry-run mislead you?"* — dry-run estimates are computed against the table as it exists *now*; if the table grows substantially, or if the query has a parameter/predicate that changes which partitions are touched at runtime (e.g., a date range parameter defaulting differently in production), the dry-run estimate at CI time can diverge meaningfully from actual production cost.

**Q31 — Compute, per user, the longest streak of consecutive days with at least one purchase.**
**Answer:** Combine gaps-and-islands with an aggregation: get distinct purchase dates per user, compute the island-grouping key (`DATE_SUB(purchase_date, INTERVAL ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY purchase_date) DAY)`), group by `(user_id, island_key)` to get each streak's length via `COUNT(*)`, then take `MAX(streak_length)` per user.
**Follow-up trap:** *"A user who purchases twice on the same day gets an inflated streak count. Why?"* — the row-number-based island trick assumes one row per distinct day; duplicate same-day purchase rows break the row-number-to-date alignment used for grouping. Deduplicate to distinct `(user_id, purchase_date)` pairs before applying the pattern, same failure mode as Q15.

**Q32 — Design a query that computes a funnel conversion rate (viewed → added to cart → purchased) per day, where a user must complete steps in order within the same session.**
**Answer:** For each session, find the earliest timestamp of each funnel step, then only count a later step as valid if its timestamp is greater than the previous step's timestamp for that same session: conditionally aggregate with `MIN(CASE WHEN event = 'view' THEN ts END)`, etc., per session, then compare timestamps to enforce ordering before counting a session as having completed each stage.
**Follow-up trap:** *"Your funnel shows more 'purchases' than 'add to carts' for some days. What went wrong?"* — likely the ordering constraint (purchase timestamp after add-to-cart timestamp within the same session) isn't actually being enforced in the SQL — a purchase happening in a session with no add-to-cart event at all (skip-the-cart checkout flow) is being miscounted as a valid funnel completion when it shouldn't be, or session boundaries don't match between the two event types.

**Q33 — A recursive CTE is needed to expand a manager-hierarchy table into full reporting chains. Does BigQuery support this, and what's the catch?**
**Answer:** Yes, BigQuery supports recursive CTEs (`WITH RECURSIVE`) as of relatively recent GA. The catch: recursive CTEs in BigQuery have a bounded maximum number of iterations and can be expensive on deep or wide hierarchies, since each iteration effectively reprocesses the accumulated result set; verify current iteration limits before relying on this for very deep organizational structures.
**Follow-up trap:** *"When would you avoid the recursive CTE and denormalize instead?"* — if the hierarchy is read far more often than it changes (org charts change rarely, get read constantly), precomputing and materializing the full ancestor/descendant paths (a closure table) on write is usually cheaper at query time than recomputing a recursive traversal on every read.

**Q34 — Explain `ARRAY_AGG` with `ORDER BY` and `LIMIT` inside the aggregate, and a case where it beats a window function.**
**Answer:** `ARRAY_AGG(event ORDER BY ts DESC LIMIT 3)` collects the top-3 most recent events per group into a single array value in one row per group — useful when you want "the last 3 events" as a single nested value per entity (e.g., for an API response) rather than 3 separate rows, which is what a `ROW_NUMBER() <= 3` window-function approach would give you.
**Follow-up trap:** *"Can you `ORDER BY` and `LIMIT` inside every aggregate function, or just `ARRAY_AGG`?"* — this ordered-limit syntax is specific to `ARRAY_AGG` (and a few others like `STRING_AGG`); it's not general syntax available on `SUM`/`COUNT`/etc., which don't have a notion of "ordering within the aggregate" to limit against.

**Q35 — Design the query-cost governance for a 200-analyst org where anyone can run ad-hoc queries against production data.**
**Testing:** platform-level judgment, not just SQL.
**Answer:** Per-user or per-project custom quotas (`maximum bytes billed` set at the query or project level) as a hard ceiling against runaway queries, combined with a capacity reservation for the analyst workload isolated from production pipelines, mandatory dry-run cost estimates surfaced in whatever query tool analysts use, and scheduled cost/usage reports by user so outliers get caught within days, not at month-end billing.
**Follow-up trap:** *"An analyst's query is correctly filtered and still expensive because the underlying table itself is poorly designed. Is that the analyst's fault?"* — no — this is a signal to invest in a curated, partitioned/clustered gold-layer table for common analyst access patterns rather than relying on every analyst to write perfectly optimized SQL against a raw or poorly-modeled table; governance should include making the cheap path also the easy path.

**Q36 — Explain the difference between `TIMESTAMP`, `DATETIME`, and `DATE` types in BigQuery and a bug caused by conflating them.**
**Answer:** `TIMESTAMP` is timezone-aware (stored in UTC, always absolute), `DATETIME` is a civil date-time with no timezone attached, and `DATE` is calendar-date only. A common bug: truncating a `TIMESTAMP` to `DATE` using `DATE(ts)` without specifying a timezone truncates in UTC by default, which can shift the reported "day" of an event by one calendar day for users in timezones far from UTC (a purchase at 11pm Pacific on the 14th can be reported as the 15th).
**Follow-up trap:** *"Your daily active user counts spike suspiciously right at UTC midnight in the raw data but the product team reports activity peaking mid-evening local time. What's happening?"* — the day boundary being used for aggregation is UTC-based, not aligned to the business's operating timezone, so daily rollups are silently misaligned with how the business actually thinks about "a day." Use `DATE(ts, 'America/Los_Angeles')` (explicit timezone argument) rather than the naive default.

**Q37 — Compute the median (not average) order value per category, and explain why `AVG` and median diverge.**
**Answer:** `APPROX_QUANTILES(order_value, 2)[OFFSET(1)]` for an approximate median, or `PERCENTILE_CONT(order_value, 0.5) OVER (PARTITION BY category)` for an exact analytic-function version. `AVG` is sensitive to outliers (a handful of very large orders pull the mean up); median is robust to that skew, which is why revenue/spend distributions (typically right-skewed) are often better summarized by median for a "typical" order.
**Follow-up trap:** *"`APPROX_QUANTILES` and `PERCENTILE_CONT` give slightly different answers on the same data. Why?"* — `APPROX_QUANTILES` is an approximate algorithm (again HyperLogLog-family / quantile-sketch based) traded for speed on huge datasets, while `PERCENTILE_CONT` computes an exact interpolated value; they're expected to diverge slightly, and the choice is a precision-vs-cost tradeoff, not a bug in either.

**Q38 — Two tables need a fuzzy date-range join (find the campaign active on the date of each transaction, where campaigns don't align to a join key but a date range). Write and cost-reason about it.**
**Answer:** `SELECT t.*, c.campaign_name FROM transactions t JOIN campaigns c ON t.txn_date BETWEEN c.start_date AND c.end_date` — a range join, not an equality join. Cost-wise, this can't use a simple hash-join-on-equality plan as cheaply as a keyed join; if `campaigns` is small, ensure it's small enough to broadcast (avoiding a shuffle of the much larger `transactions` table), and consider partitioning `transactions` by date to at least bound which partitions need to be scanned per campaign's active range.
**Follow-up trap:** *"This range join is timing out / running very slow at scale. What's the fix?"* — if campaigns don't overlap and are relatively few, precompute a `campaign_id` column onto the transaction rows via a cheaper batch process (or a scheduled query) rather than paying the range-join cost on every ad-hoc query; range joins scale poorly and are a common place where "the SQL is correct but the architecture is wrong" applies.

**Q39 — Given a `BIGNUMERIC`/`NUMERIC` cost column that occasionally has precision-related discrepancies with a downstream finance system, diagnose.**
**Answer:** BigQuery's `NUMERIC` type has fixed precision (38 digits, 9 decimal places); `BIGNUMERIC` extends that further. Discrepancies with a downstream system usually come from implicit casts to `FLOAT64` somewhere in the pipeline (floating-point rounding is not the same as fixed-point decimal arithmetic), or from a currency-rounding step applied at a different point in the pipeline (e.g., rounding per-line-item versus rounding only the final total).
**Follow-up trap:** *"Someone suggests just using `FLOAT64` everywhere for simplicity since 'the difference is tiny.'* Response?" — reject it for anything financial: floating-point representation error compounds across aggregations and can produce cent-level discrepancies that fail reconciliation with a finance system expecting exact decimal arithmetic — `NUMERIC`/`BIGNUMERIC` exist specifically to avoid this class of bug, and "tiny" errors are exactly what breaks an audit.

**Q40 — Design a slot-usage monitoring query using `INFORMATION_SCHEMA` to find the top 10 most expensive queries by bytes processed in the last 7 days, grouped by the user who ran them.**
**Answer:** Query `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` (or `JOBS_BY_ORGANIZATION` with appropriate permissions), filtering `creation_time` to the last 7 days and job `state = 'DONE'`, aggregating `SUM(total_bytes_processed)` grouped by `user_email`, ordered descending, limited to 10.
**Follow-up trap:** *"Your top-10 list is dominated by one service account, not a human analyst. Is that actually the problem?"* — not necessarily a "problem" on its face; the next question is whether that service account's queries are themselves optimized (partition/cluster-aware) or whether it's running a scheduled job that's grown expensive as source data volume increased — a scheduled, unmonitored job silently growing in cost over months is a very common real incident pattern this query is designed to catch early.

---

## Red flags that fail you

- Not knowing `SELECT *` costs more than selecting needed columns, mechanically (columnar storage).
- Recommending on-demand pricing at massive, sustained scale with no mention of the capacity/reservation break-even.
- Using `NOT IN` against a subquery that could contain NULLs without flagging the risk.
- Forgetting the default window frame issue with `LAST_VALUE` (returns current row, not the true last row, without an explicit frame).
- Treating `LIMIT` as a cost-reduction technique (it reduces rows returned, not bytes scanned).
- Not knowing the difference between `TIMESTAMP` (UTC, absolute) and `DATETIME`/`DATE` (civil, no timezone).
- Recommending `FLOAT64` for financial calculations.

---

## Cheat card

```
SLOTS/PRICING     on-demand: $6.25/TiB scanned, first 1 TiB/month free
                   capacity: $0.04/slot-hr (Standard) · $0.06/slot-hr (Enterprise)
                   break-even ≈ 467 TiB scanned/month (rule of thumb, not law)

COLUMN COST       columnar storage: SELECT * bills EVERY column, not just used ones
                   500GB table: SELECT * ≈ $3.13 · 3-of-20 cols ≈ $0.19  (~16x)
                   10TB table: naive SELECT * ≈ $62.50 in ONE query
                   LIMIT reduces rows RETURNED, not bytes SCANNED — no cost savings

PARTITION/CLUSTER partition = skip whole segments (commonly by date)
                   cluster (≤4 cols) = skip blocks WITHIN a partition
                   combined: typically 90-99% bytes-scanned reduction on targeted queries

STORAGE           active (touched <90 days): $0.02/GB/mo
                   long-term (untouched 90+ days): $0.01/GB/mo, AUTOMATIC, PER PARTITION
                   any write resets that partition's 90-day clock to zero

STREAMING         legacy streaming insert: at-least-once, needs manual dedup
                   Storage Write API (recommended): exactly-once w/ offsets, $0.025/GB,
                   first 2 TiB/month free

MAT. VIEWS/BI ENG materialized view: billed only for MV bytes, not full source table
                   BI Engine: in-memory acceleration for dashboards

SQL TRAPS         QUALIFY > wrapping subquery for window-function filters
                   LAST_VALUE needs explicit ROWS/RANGE ...UNBOUNDED FOLLOWING frame
                   NOT IN + possible NULLs in subquery = silently zero rows
                   DATE(ts) truncates in UTC by default — pass explicit timezone
                   UNNEST (inner) drops empty-array rows — use LEFT JOIN UNNEST to keep them
                   gaps-and-islands: row_number() - date trick breaks on duplicate dates
                   NUMERIC/BIGNUMERIC for money — never FLOAT64
```

## Sources

- [Understand slots — BigQuery docs](https://docs.cloud.google.com/bigquery/docs/slots) — accessed 2026-08-01
- [BigQuery pricing — Google Cloud](https://cloud.google.com/bigquery/pricing) — accessed 2026-08-01
- [Comparing BigQuery Pricing Models: On-demand vs Capacity-based Reservations — FollowRabbit](https://followrabbit.ai/blog/comparing-bigquery-pricing-models-on-demand-vs-capacity-based) — accessed 2026-08-01
- [BigQuery Cost Optimization: The Complete Guide for Growing Companies — Medium](https://medium.com/@cocamatias/bigquery-cost-optimization-the-complete-guide-for-growing-companies-9951bd46a64c) — accessed 2026-08-01
- [One BigQuery SELECT * Cost $62.50 (Prevent It) — LeanOps](https://leanopstech.com/blog/google-bigquery-pricing-2026/) — accessed 2026-08-01
- [Google BigQuery Cost Optimization 2026 — Revefi](https://www.revefi.com/blog/google-bigquery-cost-optimization) — accessed 2026-08-01
- [How to Stream Data into BigQuery Using the Storage Write API — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-stream-data-into-bigquery-using-the-storage-write-api/view) — accessed 2026-08-01
- [The Gaps and Islands Problem: SQL Interview Practice — Medium](https://medium.com/@keshavkhandelwal142/the-gaps-and-islands-problem-sql-interview-practice-8c087a511cd1) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

BigQuery is Dremel exposed as a serverless product — no cluster to size, ever — with two orthogonal cost axes: on-demand bills per byte scanned ($6.25/TiB), capacity bills per slot-hour ($0.04-0.06), and the break-even sits around 467 TiB scanned/month. Because storage is columnar, `SELECT *` bills every column regardless of use, which is why a naive full scan on a 10TB table can cost $62.50 in one query while column pruning alone can cut that by 16x; partitioning and clustering on top of that routinely get well-targeted queries down to 1-10% of a table's total bytes. The SQL interview is where this module earns its keep: window functions, `QUALIFY`, `UNNEST`, gaps-and-islands, and date-range expansion via `GENERATE_DATE_ARRAY` show up constantly, and most of the traps are NULL-handling, default-window-frame, and UTC-truncation bugs rather than syntax you don't know.
