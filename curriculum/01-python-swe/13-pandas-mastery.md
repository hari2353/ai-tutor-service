# Pandas: Vectorisation, groupby/agg, merge, Reshaping, Date Range → Month Rows

> **Track:** T01 Python & SWE Craft · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T01-pandas-mastery` · **Tags:** data,critical

## The 30-second version

Every pandas operation you write should be vectorised — pushed down into NumPy's compiled C loops over whole columns — because `.apply()` and `.iterrows()` fall back to a Python-level loop with per-element function-call overhead: on a few hundred thousand rows, vectorised code finishes in single-digit milliseconds while `.apply()` takes tens to hundreds of milliseconds and `.iterrows()` is slower still, routinely 100-700x slower than the vectorised equivalent. `groupby` splits, `agg` reduces each group to a scalar, `transform` returns a result the same shape as the input (broadcasting the group result back to every row), and `filter` keeps or drops whole groups based on a predicate — conflating these is the most common groupby mistake. As of pandas 3.0 (January 2026), Copy-on-Write is the only mode: chained assignment now raises instead of silently working or not working, which retires the `SettingWithCopyWarning` era entirely. And the interview-favorite "expand a date range into one row per month" problem is a `pd.date_range` per row plus `explode`, which is the pandas-native way to do what SQL does with a calendar table or `generate_series`.

## Why this gets asked

Because pandas is the interface between "I can write Python" and "I can actually move data at the volumes a production ETL or feature pipeline deals with," and almost every candidate has used `.apply()` without knowing why it's slow, or been bitten by `SettingWithCopyWarning` without understanding what it's actually warning about. The interviewer has personally watched a job that should take 30 seconds take 20 minutes because someone wrote a `for` loop with `.iloc[i]` instead of a vectorised operation, or shipped a silent data-corruption bug because a chained assignment didn't do what it looked like it did.

---

## Lineage: past → present → future

**What came before.** Before pandas (2008, Wes McKinney at AQR), the standard tools for tabular data in Python were raw NumPy arrays (fast, but no labeled axes, no heterogeneous columns, no missing-data handling) or hand-rolled `csv` module loops (correct but slow and verbose). Pandas's core insight was borrowing R's `data.frame` model — labeled rows and columns, heterogeneous column types, built-in missing-data (`NaN`) semantics — and backing it with NumPy arrays for speed, giving Python a genuinely competitive data-manipulation story for the first time. The `.apply()`/`.iterrows()` anti-patterns this module warns about exist precisely because pandas *looks* like it should support arbitrary row-wise Python logic efficiently, and it doesn't — that gap between the API surface and the performance model is the single biggest thing new users misjudge.

**Where it stands now.** Pandas 3.0 shipped January 21, 2026, and made two changes load-bearing for this module: Copy-on-Write became the *only* mode (no opt-out, no `pd.options.mode.copy_on_write` toggle needed — every returned object behaves as an independent copy for correctness, while the implementation defers the actual memory copy until a write happens), and chained assignment (`df[mask]['col'] = x`) now raises an error rather than silently sometimes-working. The old `SettingWithCopyWarning`, and the ritual of sprinkling defensive `.copy()` calls to silence it, is gone because there's no longer ambiguity about whether an operation returns a view or a copy — everything *behaves* like a copy. [Pandas 3.0 Released!](https://pandas.pydata.org/community/blog/pandas-3.0.html) — accessed 2026-08-01. [What's new in 3.0.0 — pandas documentation](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) — accessed 2026-08-01. The live disagreement in the ecosystem is scale, not correctness: pandas remains the right default under roughly 1GB / a few hundred million cells on a single machine, but Polars (multi-threaded by default, lazy query optimization) is now the well-established choice above that, and DuckDB has become the standard tool for SQL-shaped aggregation directly over files larger than RAM without a separate data warehouse.

**Where it's heading.** Pandas 3.0 also made PyArrow-backed string dtype the default for text columns (replacing the old NumPy `object` dtype for strings), which materially changes the memory/downcasting numbers this module quotes for `category` versus plain string columns — Arrow-backed strings are already far more memory-efficient than the historical `object` dtype, narrowing (but not eliminating) the gap that `category` used to close. [Pandas 3.0 Introduces Default String Dtype — InfoQ](https://www.infoq.com/news/2026/02/pandas-library/) — accessed 2026-08-01. The broader direction is convergence with the Arrow ecosystem (zero-copy interop with Polars, DuckDB, and Spark via Arrow), which is well underway, not speculative.

---

## Mental model

```
VECTORISED             .apply()                .iterrows()
─────────────         ──────────               ────────────
one NumPy C loop        Python loop calling      Python loop constructing a
over the whole           your function per        Series object per row (!),
column/array             row/element              then calling your code
(fast: SIMD, no          (medium: one Python      (slowest: full Series
per-element Python        call + result             construction overhead
object overhead)          collection per row)       PER ROW, plus the loop)
```

```
groupby(key)
     │
     ▼
  SPLIT into groups by key
     │
     ├── .agg(fn)        one row per group   (reduce: group -> scalar)
     ├── .transform(fn)  SAME shape as input  (broadcast: group -> per-row result)
     └── .filter(fn)     subset of ORIGINAL rows  (keep/drop whole groups by predicate)
```

---

## How it actually works

### Vectorisation vs `apply` vs `iterrows` — measured

| Approach | ~100k rows | ~1M rows | Mechanism |
|---|---|---|---|
| Vectorised (`df.a + df.b`) | single-digit ms | tens of ms | One compiled NumPy loop over contiguous memory, no Python-level per-element calls |
| `.apply(func, axis=1)` | tens of ms | ~1-10s | Python function called once per row; pandas still has to construct/pass a Series-like object per call |
| `.iterrows()` | ~100ms+ | tens of seconds+ | Constructs an actual `Series` object for every single row (with its own dtype-mixing and index overhead) before your loop body even runs |

Vectorisation is commonly measured at 100-700x faster than `iterrows()` and 50-100x faster than `.apply()` at six-figure row counts, and the gap widens, not narrows, as row count grows, because the per-row Python overhead is constant per row while the vectorised path benefits from cache-friendly contiguous memory access. [Efficient Pandas: Apply vs Vectorized Operations — Towards Data Science](https://towardsdatascience.com/efficient-pandas-apply-vs-vectorized-operations-91ca17669e84/) — accessed 2026-08-01.

```python
import pandas as pd, numpy as np

df = pd.DataFrame({"a": np.random.rand(1_000_000), "b": np.random.rand(1_000_000)})

# BAD: iterrows -- constructs a Series per row
total = sum(row.a + row.b for _, row in df.iterrows())

# BETTER: apply -- one Python call per row, no per-row Series construction cost
df["sum_apply"] = df.apply(lambda r: r.a + r.b, axis=1)

# BEST: vectorised -- one NumPy loop, no Python call per element
df["sum_vec"] = df.a + df.b
```

`.apply(axis=1)` is *never* the fast path — it exists for logic that genuinely can't be vectorised (complex conditional branching referencing many columns with no clean NumPy equivalent), not as a default row-processing tool.

### dtypes and memory — `category`, downcasting, and the NaN-promotion trap

```python
df["status"].memory_usage(deep=True)                 # object dtype: full string storage per cell
df["status"] = df["status"].astype("category")
df["status"].memory_usage(deep=True)                  # category: strings stored ONCE, rows store small int codes
```
A `category` column stores each unique value once and represents every row as a small integer code into that lookup table — for a column with low cardinality relative to row count (a status flag, a country code, a log level), this is a large memory win; for a column of mostly-unique values (a UUID, a free-text comment), `category` buys nothing and adds overhead.

```python
s = pd.Series([1, 2, 3], dtype="int64")
s.memory_usage()                     # 8 bytes/value
s_small = pd.to_numeric(s, downcast="integer")
s_small.dtype                        # int8, if values fit in [-128, 127] -- 1 byte/value, an 8x reduction
```
[Pandas Memory Optimization — Python Data Bench](https://pythondatabench.com/article/pandas-memory-optimization-reduce-dataframe-memory-usage) — accessed 2026-08-01 reports downcasting a `user_id` column from int64 to uint32 for a 50% reduction, and an `age`-like bounded column from int64 to uint8 for an 87.5% reduction — both real, measured examples of the same mechanism.

**The NaN-promotion trap:**
```python
s = pd.Series([1, 2, None, 4])
s.dtype        # float64 -- NOT int64!
```
NumPy's `int64` has no representation for missing values, so as soon as a single `NaN`/`None` appears in an otherwise-integer column, pandas silently upcasts the *entire column* to `float64` to accommodate it — every value becomes a float, `1` becomes `1.0`, and any code downstream assuming integer dtype (bitwise ops, certain groupby key behavior, memory footprint assumptions) breaks or silently produces subtly different results. **Fix:** pandas's nullable integer dtype, `Int64` (capital I, distinct from plain `int64`), which supports `pd.NA` without forcing a float upcast:
```python
s = pd.Series([1, 2, None, 4], dtype="Int64")   # stays integer, with proper NA support
```

### `groupby` + `agg`/`transform`/`filter` — precisely distinguished

```python
df = pd.DataFrame({"team": ["A","A","B","B"], "score": [10, 20, 5, 15]})

df.groupby("team")["score"].agg("mean")
# team
# A    15.0
# B    10.0
# -> ONE ROW PER GROUP (reduction)

df.groupby("team")["score"].transform("mean")
# 0    15.0
# 1    15.0
# 2    10.0
# 3    10.0
# -> SAME SHAPE as input (each row gets its group's mean, broadcast back)

df.groupby("team").filter(lambda g: g["score"].sum() > 20)
# keeps every row belonging to a group whose predicate is True
# -> A SUBSET OF ORIGINAL ROWS, group-wise, not row-wise
```

`transform` is what you want for "add a column showing each row's deviation from its group's mean" (`df["score"] - df.groupby("team")["score"].transform("mean")`) — a pattern that appears constantly in feature engineering and is impossible to express cleanly with `agg` alone, since `agg` collapses the group and you'd need a separate `merge` back onto the original frame to get the row-aligned result `transform` gives you directly.

### `merge` — types and cardinality validation

```python
orders = pd.DataFrame({"order_id": [1, 2, 3], "customer_id": [10, 10, 20]})
customers = pd.DataFrame({"customer_id": [10, 20], "name": ["Alice", "Bob"]})

merged = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
```

| `how` | Keeps |
|---|---|
| `inner` | Only keys present in both frames |
| `left` | All left rows; unmatched right columns become NaN |
| `right` | All right rows; unmatched left columns become NaN |
| `outer` | Union of keys from both; unmatched columns become NaN on whichever side is missing |
| `cross` | Every combination of left × right rows (no `on` key) |

`validate` raises `MergeError` immediately if the assumed cardinality is wrong, *before* the merge silently fans out or drops rows: `"one_to_one"` requires unique keys on both sides, `"one_to_many"` requires unique keys on the left, `"many_to_one"` requires unique keys on the right, `"many_to_many"` allows duplicates on both (and provides essentially no protection). [Pandas merge() Validate Parameter — CyberAngles](https://www.cyberangles.org/blog/validate-in-merge-function-pandas/) — accessed 2026-08-01. **This is a real production bug category**: a merge you believed was one-to-one silently becomes one-to-many the moment upstream data grows a duplicate key, multiplying row counts downstream (a customer table gaining a duplicate `customer_id` turns every order for that customer into two rows) with no error, only a row count that's subtly wrong — `validate` turns that into an immediate, loud failure at the merge itself.

### `SettingWithCopyWarning` — what caused it, and what changed in pandas 3.0

```python
# Pre-3.0 behaviour (illustrative — CoW is now the ONLY mode, this ambiguity no longer exists):
sub = df[df.score > 10]        # MIGHT be a view, MIGHT be a copy -- undocumented, layout-dependent
sub["flag"] = True             # SettingWithCopyWarning: might silently mutate df, might not
```
The warning existed because whether `df[mask]` returned a view (sharing memory with `df`) or a copy was an internal implementation detail that depended on the DataFrame's memory layout, not something the API contract specified — so the *same-looking code* could correctly update the original frame in one case and silently do nothing in another, and there was no way to tell without knowing pandas internals.

**Pandas 3.0 removes the ambiguity, not just the warning**: Copy-on-Write is the only mode, so `df[mask]` always *behaves* as an independent object — mutating `sub` after that never touches `df`, guaranteed. Chained assignment written the old way (`df[df.score > 10]["flag"] = True` in one expression) now raises directly, because pandas can detect it's about to write to a temporary that no longer exists by the time the second `[]` executes. [Pandas 3.0's Biggest Shift: Copy-on-Write Becomes the Only Mode — Medium](https://medium.com/@sathishdba/pandas-3-0s-biggest-shift-copy-on-write-becomes-the-only-mode-87a1870a144f) — accessed 2026-08-01. **The fix, in any pandas version, is the same and was always correct**: don't chain — assign in one step.
```python
df.loc[df.score > 10, "flag"] = True     # correct: single, explicit, in-place-labeled assignment
```

### `pivot` / `melt` / `stack` / `unstack`

```python
long = pd.DataFrame({
    "date": ["2026-01", "2026-01", "2026-02", "2026-02"],
    "metric": ["revenue", "cost", "revenue", "cost"],
    "value": [100, 40, 120, 45],
})

wide = long.pivot(index="date", columns="metric", values="value")
#          cost  revenue
# date
# 2026-01    40      100
# 2026-02    45      120

back_to_long = wide.reset_index().melt(id_vars="date", var_name="metric", value_name="value")
# undoes the pivot -- back to the original long shape
```
`pivot` reshapes long → wide (one column per unique value of `columns`); `melt` reshapes wide → long (unpivot). `stack`/`unstack` do the equivalent operation on a `MultiIndex` directly (`stack` moves a column level into the row index, making the frame taller/narrower; `unstack` is its inverse), which is the tool of choice when you're already working with hierarchical indices rather than plain columns.

### The date-range-to-month-rows problem

**The ask:** given a table of rows each with a `start_date` and `end_date`, produce one output row per (original row, month) for every month the range spans.

```python
import pandas as pd

df = pd.DataFrame({
    "contract_id": [1, 2],
    "start_date": pd.to_datetime(["2026-01-15", "2026-03-01"]),
    "end_date": pd.to_datetime(["2026-03-20", "2026-03-31"]),
})

df["month"] = df.apply(
    lambda r: pd.date_range(r.start_date, r.end_date, freq="MS").tolist()
              or [r.start_date.replace(day=1)],   # guard: range spanning <1 month boundary
    axis=1,
)
result = df.explode("month").reset_index(drop=True)
result["month"] = result["month"].dt.to_period("M")
print(result[["contract_id", "month"]])
#    contract_id    month
# 0            1  2026-01
# 1            1  2026-02
# 2            1  2026-03
# 3            2  2026-03
```
`freq="MS"` (month start) generates one timestamp per calendar month boundary between `start_date` and `end_date`; `explode` then turns each row's *list* of months into that many separate rows, duplicating every other column. The `or [...]` guard handles the edge case where a contract starts and ends within the same month, so `date_range` with `MS` produces zero month-start boundaries strictly between the two dates — without the guard, that contract would silently vanish from the output via `explode` on an empty list.

**Caveat on `.apply(axis=1)` here**: this specific problem is a legitimate, common exception to "never use apply" — `pd.date_range` per row doesn't have a clean single vectorised equivalent in plain pandas, because each row produces a *different-length* list of months. For large row counts (millions of contracts), the better-performing approach is to compute month boundaries via integer arithmetic on year*12+month rather than calling `date_range` per row, or push the expansion into SQL/DuckDB instead.

**The SQL equivalent**, using a calendar table (or `generate_series` in Postgres/DuckDB):
```sql
-- Postgres / DuckDB: generate_series produces one row per month directly, no calendar table needed
SELECT c.contract_id, gs.month
FROM contracts c
CROSS JOIN LATERAL generate_series(
    date_trunc('month', c.start_date),
    date_trunc('month', c.end_date),
    interval '1 month'
) AS gs(month);

-- Calendar-table style (portable to engines without generate_series, e.g. older SQL Server):
SELECT c.contract_id, cal.month
FROM contracts c
JOIN calendar cal
  ON cal.month BETWEEN date_trunc('month', c.start_date) AND date_trunc('month', c.end_date);
```
The calendar-table join is the more portable pattern (works on any SQL engine with a pre-populated date dimension table, common in warehouses), while `generate_series` is terser and avoids maintaining a physical calendar table at all, at the cost of being engine-specific.

### Time-series resample and rolling

```python
ts = pd.Series(range(100), index=pd.date_range("2026-01-01", periods=100, freq="D"))

ts.resample("W").sum()      # downsample: group by calendar week, sum within each week
ts.rolling(window=7).mean() # sliding 7-day mean, one output per input row (NaN for the first 6)
ts.resample("D").ffill()    # upsample: fill gaps in a lower-frequency series forward
```
`resample` changes the *frequency* of the index (fewer or more rows than the input, aligned to calendar boundaries); `rolling` keeps the same number of rows and computes a sliding-window statistic over each — conflating the two is a common mistake (`rolling(7)` on daily data means "the last 7 calendar rows," which is only the same as "the last 7 days" if the index has no gaps).

---

## Build it from scratch

The vectorisation gap, made concrete with a timed comparison you could run in an interview:

```python
import pandas as pd
import numpy as np
import time

n = 200_000
df = pd.DataFrame({"a": np.random.rand(n), "b": np.random.rand(n)})

def time_it(label, fn):
    start = time.perf_counter()
    fn()
    print(f"{label}: {(time.perf_counter() - start) * 1000:.1f}ms")

time_it("iterrows", lambda: [r.a + r.b for _, r in df.iterrows()])
time_it("apply",    lambda: df.apply(lambda r: r.a + r.b, axis=1))
time_it("vectorised", lambda: df.a + df.b)
# Typical relative ordering on this shape of data: iterrows slowest by 1-2 orders of
# magnitude vs apply, and apply slower than vectorised by another 1-2 orders of magnitude.
```

A from-scratch `groupby`-`transform` (to show the mechanism, not to replace real pandas):

```python
def manual_group_mean_transform(df, key_col, value_col):
    means = df.groupby(key_col)[value_col].mean()   # one mean per group
    return df[key_col].map(means)                    # broadcast back to every row via the key

df = pd.DataFrame({"team": ["A","A","B"], "score": [10, 20, 5]})
assert (manual_group_mean_transform(df, "team", "score")
        == df.groupby("team")["score"].transform("mean")).all()
```
This is exactly what `transform` does under the hood conceptually: compute the reduced value per group, then re-align it back to the original row index via the grouping key. Lab: `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A pipeline step that was fast on a sample dataset takes minutes in production | `.apply(axis=1)` or `.iterrows()` used for logic that has a vectorised equivalent | Rewrite as column-wise arithmetic/boolean masks/`np.where`; reserve `.apply` for genuinely unvectorisable branching |
| A DataFrame consumes far more memory than the data seems to warrant | Low-cardinality string columns stored as `object`, integer columns not downcast, or NaN silently promoting an int column to float64 | `.astype("category")` for repeated string values, `pd.to_numeric(..., downcast=...)`, `Int64` nullable dtype for integer columns that may contain missing values |
| Row counts after a merge are higher (or lower) than expected, with no error | Assumed one-to-one or many-to-one merge is actually many-to-many because of a duplicate key introduced upstream | Add `validate="one_to_one"`/`"many_to_one"`/`"one_to_many"` to the merge call so a cardinality violation raises immediately instead of silently fanning out rows |
| (Pre-3.0) `SettingWithCopyWarning`, or a downstream frame mysteriously not updated after an assignment | Chained assignment on an ambiguous view-or-copy intermediate | Use `.loc[row_mask, "col"] = value` in one step; on pandas 3.0+, chained assignment raises outright rather than warning |
| `explode` on the month-expansion pattern silently drops a row entirely | The per-row list (e.g. from `date_range`) was empty for that row (a range not spanning a full month boundary) | Guard with a fallback single-element list for that edge case before exploding |
| `rolling(7)` on a datetime-indexed series gives wrong-looking results after a data gap | `rolling` counts rows, not calendar time, by default — a gap in the index means "7 rows" spans more than 7 calendar days | Use a time-based rolling window (`rolling("7D")`) instead of a row-count window, or reindex to a complete calendar range first |
| A groupby aggregation is much slower than expected on a huge dataset | Grouping key is a high-cardinality `object` string column instead of `category`, or the aggregation function is a custom Python callable instead of a named/vectorised one | Convert group keys to `category`; use built-in string names (`"mean"`, `"sum"`) or NumPy ufuncs, which pandas can execute without a Python callback per group |

### When to leave pandas for Polars/DuckDB/Spark

| Situation | Tool | Why |
|---|---|---|
| Data fits comfortably in memory, under roughly **1GB / a few hundred million cells** on a single machine | Pandas | Simplest API, best ecosystem integration (matplotlib, scikit-learn) for the final analysis/modeling step |
| **Above ~1-5GB**, or you need multi-core execution without hand-rolling multiprocessing | Polars | Multi-threaded by default, lazy query optimization; benchmarked as the faster engine on essentially every operation above roughly 1GB, and a `groupby` over 100M rows that takes 100+ seconds (or exhausts memory) in pandas often finishes in well under 30 seconds in Polars |
| SQL-shaped aggregation over files (Parquet/CSV) larger than RAM, without standing up a warehouse | DuckDB | Analytical engine embedded in-process, spills to disk transparently, can query files directly without a separate load step |
| **Multi-machine**, data genuinely exceeds what a single node can hold (roughly 10B+ rows / 10+ TB, joins across a cluster) | PySpark | The community-validated threshold where distributed computing's coordination overhead is finally worth paying for |

[Pandas vs Polars vs DuckDB: What Data Scientists Should Use in 2026 — Analytics Insight](https://www.analyticsinsight.net/programming/pandas-vs-polars-vs-duckdb-what-data-scientists-should-use-in-2026) — accessed 2026-08-01.

---

## Tradeoffs & when NOT to use it

- **Don't reach for `category` on high-cardinality columns.** A column of mostly-unique values (UUIDs, free-text) gains nothing from `category` and adds the overhead of maintaining a codes-plus-categories structure for little to no memory benefit.
- **Don't use `.apply(axis=1)` as a default — reserve it for logic that genuinely can't be vectorised**, and even then, benchmark against a manual loop with `itertuples()` (faster than `iterrows()` because it avoids constructing a full `Series` per row) if `.apply` itself turns out to be the bottleneck.
- **Don't skip `validate=` on merges in a production pipeline** just because it "usually works" — the entire value of `validate` is catching the one time upstream data quality silently changes, and it costs nothing at query-planning time to include.
- **`deepcopy`-style full-frame copies "just to be safe" are unnecessary under pandas 3.0's CoW model** — the correctness guarantee is already there; copying defensively on top of CoW just pays the same cost pandas would have deferred anyway, for no additional safety.
- **Pandas is the wrong tool once data stops fitting comfortably in memory on one machine** — reaching for chunked reading (`chunksize=`) or manual memory tricks to keep using pandas past that point is usually more engineering effort than moving the same job to Polars or DuckDB, which solve the memory problem natively.
- **`resample`/`rolling` assume a clean, mostly-regular datetime index** — on genuinely irregular event data (sparse, bursty timestamps), naive row-count-based `rolling` windows silently mean something different from what you likely intend; use time-based windows (`rolling("1h")`) explicitly.

---

## Interview questions

### Q1 — Why is `.apply(axis=1)` slow, and what's actually happening under the hood?
**Testing:** baseline understanding of vectorisation, not just "it's slower, use vectorised code."
**Answer:** `.apply(axis=1)` calls your Python function once per row, and for each call pandas has to assemble the row's values into a Series-like object to pass to your function — this happens in the Python interpreter, one row at a time, completely bypassing NumPy's compiled, columnar C loops. Vectorised code (`df.a + df.b`) instead runs a single compiled loop over contiguous memory for the whole column, with no per-row Python function call overhead at all.
**Follow-up trap:** *"Is apply ever the right choice?"* — yes, for logic that genuinely can't be expressed as column-wise operations (complex multi-column conditional branching with no clean `np.select`/`np.where` equivalent) — but it should be the fallback after confirming vectorisation isn't feasible, not the default.

### Q2 — Rank `iterrows()`, `.apply(axis=1)`, and vectorised operations by speed, with rough numbers.
**Answer:** Vectorised fastest (single-digit to tens of milliseconds on hundreds of thousands to a million rows); `.apply` next, typically 50-100x slower than vectorised at that scale; `iterrows()` slowest, commonly 100-700x slower than vectorised, because it constructs a full `Series` object per row before your loop body even executes.
**Follow-up trap:** *"Why is `itertuples()` faster than `iterrows()` even though both are still row-wise Python loops?"* — `itertuples()` yields namedtuples instead of constructing a full `Series` per row, which is much cheaper to build (no index alignment, no dtype coercion across mixed-type row values) — still far slower than vectorisation, but a real improvement over `iterrows()` when a genuine row-wise Python loop is unavoidable.

### Q3 — Why does a Series of integers with one missing value become `float64` instead of staying `int64`?
**Testing:** the NaN-promotion trap, a common source of silent dtype bugs.
**Answer:** NumPy's native `int64` dtype has no bit pattern reserved to represent "missing," so pandas can't hold `NaN` in an int64 column — as soon as any value is missing, pandas upcasts the *entire column* to `float64`, which does have a NaN representation, silently converting every integer value to its float equivalent.
**Follow-up trap:** *"How do you avoid the upcast if you need to preserve integer semantics with missing values?"* — use pandas's nullable `Int64` dtype (capital I), which represents missing values via `pd.NA` internally without requiring a float upcast, keeping the column genuinely integer-typed.

### Q4 — Difference between `groupby(...).agg()`, `.transform()`, and `.filter()`?
**Testing:** the most common groupby confusion, always worth a direct question.
**Answer:** `agg` reduces each group to a scalar (or a small summary), producing one output row per group. `transform` also computes a per-group result but broadcasts it back to the *original* shape, giving every row in a group the same computed value (useful for "row minus its group's mean" style features). `filter` evaluates a group-level predicate and keeps or drops *all rows* belonging to groups that pass or fail it, returning a subset of the original rows, not an aggregated summary.
**Follow-up trap:** *"How would you compute, for each row, its deviation from its group's mean, using only `agg`?"* — you can't directly; you'd need to `agg` to get per-group means, then `merge` that back onto the original frame on the grouping key to re-align it row-wise — exactly the two-step process `transform` collapses into one call.

### Q5 — What does `validate="one_to_many"` do in `pd.merge`, and what real bug does it catch?
**Answer:** It checks, before performing the merge, that keys are unique on the left side (matching the "one" side of the relationship) — if the left side actually has duplicate keys, it raises `MergeError` immediately instead of silently proceeding. This catches the class of bug where an assumed cardinality (e.g., one row per customer) is violated by unexpected duplicate keys introduced upstream, which would otherwise silently multiply row counts in the merged output with no error, only a row count that's subtly wrong downstream.
**Follow-up trap:** *"What does `validate='many_to_many'` actually protect against?"* — almost nothing; it allows duplicate keys on both sides, so it only catches the case where you expected unique keys somewhere and there genuinely are none anywhere, which is a much weaker guarantee than the other three options.

### Q6 — What caused `SettingWithCopyWarning`, and what actually changed about this in pandas 3.0?
**Testing:** whether the candidate has checked recent, version-dependent pandas changes rather than reciting outdated advice.
**Answer:** Whether `df[mask]` returned a view (sharing memory with the original) or a copy was an internal, undocumented implementation detail depending on memory layout — so code like `df[mask]['col'] = value` could correctly mutate the original in one case and silently do nothing in another, identical-looking case. Pandas 3.0 (January 2026) made Copy-on-Write the only mode: every operation now behaves as an independent copy by contract (the implementation still defers the actual memory copy for performance, copying only when a write actually happens), and chained assignment written the old ambiguous way now raises an explicit error instead of warning.
**Follow-up trap:** *"So does that mean `.copy()` calls are now unnecessary everywhere?"* — the *defensive* copies people added purely to silence the warning are unnecessary now, since the correctness guarantee is built in; you'd still explicitly `.copy()` when you specifically want to break the CoW-managed sharing early for some other reason (e.g., you know you're about to do many small in-place mutations and want to avoid repeated internal copy-on-first-write overhead).

### Q7 — Walk through expanding a table of (start_date, end_date) rows into one row per month, and give the SQL equivalent.
**Testing:** the specific interview-favorite this module names explicitly.
**Answer:** In pandas: for each row, generate the list of month-start timestamps between `start_date` and `end_date` with `pd.date_range(start, end, freq="MS")`, store that list in a new column, then call `df.explode("month_col")` to turn each row's list into that many separate output rows, duplicating the other columns. Guard against ranges that don't span a full month-start boundary (start and end in the same month), which otherwise produce an empty list and silently vanish under `explode`. In SQL: either `generate_series(date_trunc('month', start), date_trunc('month', end), interval '1 month')` (Postgres/DuckDB, no auxiliary table needed) or a join against a pre-populated calendar/date-dimension table filtered with `BETWEEN`, which is the more portable pattern across engines lacking `generate_series`.
**Follow-up trap:** *"This uses `.apply(axis=1)` — doesn't that contradict 'never use apply'?"* — this is a legitimate exception: each row produces a variable-length list of months, which has no clean single-shot vectorised equivalent in plain pandas; at very large row counts, the better fix is integer arithmetic on `year*12+month` computed vectorised across the whole column, or pushing the expansion into SQL/DuckDB entirely rather than fighting pandas's row-wise limitation here.

### Q8 — What's the difference between `pivot`/`melt` and `stack`/`unstack`, and when would you reach for the index-based pair instead of the column-based pair?
**Answer:** `pivot` (long→wide) and `melt` (wide→long) operate on plain columns, specifying `index`/`columns`/`values` explicitly. `stack`/`unstack` do the equivalent reshape on a `MultiIndex` directly — `stack` moves an index or column level down into the row index (making the frame taller, narrower), `unstack` is its inverse. Reach for `stack`/`unstack` when you're already working with hierarchical indices (e.g., the output of a multi-key `groupby`), since converting to plain columns first just to `pivot`/`melt` and then back is unnecessary extra work.
**Follow-up trap:** *"Can `pivot` handle duplicate index/column combinations?"* — no, `pivot` raises `ValueError: Index contains duplicate entries` if the (index, columns) pair isn't unique — for that case you need `pivot_table`, which accepts an aggregation function (default mean) to resolve duplicates instead of erroring.

### Q9 — Difference between `resample` and `rolling`, and a case where confusing them produces a subtly wrong result?
**Answer:** `resample` changes the index's frequency — it can produce fewer rows (downsampling, e.g. daily → weekly sums) or more (upsampling with a fill method), aligned to calendar boundaries. `rolling` keeps the same number of rows as the input and computes a sliding-window statistic over a fixed window of *rows* (by default) ending at each point. The subtle bug: `rolling(window=7)` on a daily-indexed series with a gap (a missing day) means "the last 7 rows," which is no longer the same as "the last 7 calendar days" once there's a gap — the window silently reaches further back in time than intended.
**Follow-up trap:** *"How do you fix `rolling` for irregular timestamps?"* — pass a time-based window string (`rolling("7D")`) instead of an integer row count; pandas then windows by actual elapsed time using the datetime index, correctly handling gaps.

### Q10 — At what point does it stop making sense to use pandas, and what would you switch to?
**Testing:** the "when NOT to use it" the checklist demands — a senior signal because juniors keep pushing pandas past its comfort zone with `chunksize` hacks instead of switching tools.
**Answer:** Roughly above 1GB or a few hundred million cells on a single machine, pandas starts to struggle (single-threaded execution, eager evaluation with no query optimizer, and memory overhead per cell that's higher than a columnar engine's). Above that on one machine, Polars (multi-threaded, lazy evaluation) is the modern default; for SQL-shaped aggregation directly over files larger than RAM, DuckDB; once data genuinely exceeds a single machine's capacity (roughly 10B+ rows / 10+ TB with cross-node joins), PySpark is the community-validated threshold where distributed coordination overhead finally pays for itself.
**Follow-up trap:** *"If you're already deep into a pandas-based pipeline and hit this wall, do you rewrite in Polars immediately?"* — not necessarily; Polars and DuckDB both interoperate with pandas via Arrow with minimal copying, so a common pragmatic path is pushing just the expensive aggregation/join step into DuckDB or Polars and keeping the rest of the pipeline (visualization, model fitting) in pandas, rather than a full rewrite.

### Q11 — What's the actual mechanism behind `category` dtype's memory savings, and when does it not help?
**Answer:** A `category` column stores the set of unique values once (the "categories") and represents every row as a small integer code pointing into that lookup — so for a column with low cardinality relative to row count (a status enum, a country code), memory drops from "one full string per row" to "one small integer per row plus one copy of each unique string." It doesn't help — and can add overhead — on high-cardinality columns (mostly-unique values like UUIDs or free text), where the codes array approaches the same size as just storing the values directly, with the added cost of maintaining the category mapping.
**Follow-up trap:** *"Does pandas 3.0's new PyArrow-backed default string dtype change this calculus?"* — yes, partially: Arrow-backed strings are already meaningfully more memory-efficient than the old NumPy `object` dtype pandas used to default to for strings, so the memory gap `category` used to close is narrower than it was pre-3.0, though `category` still wins decisively for genuinely low-cardinality columns because it avoids storing the repeated string content at all, not just storing it more efficiently.

### Q12 — You have a merge that should be one-to-one but you didn't add `validate`. Production data silently doubled downstream row counts last quarter. Diagnose and prevent recurrence.
**Testing:** staff-level, ties a specific pandas feature to an actual incident narrative.
**Answer:** Diagnosis: an upstream table that was supposed to have unique keys picked up a duplicate (a dedup step broke, or two records with the same natural key were both loaded), and a plain `merge(..., on=key)` with no `how`/`validate` guard silently fanned out — each row on the "one" side matched twice, doubling the output row count with no error surfaced anywhere in the pipeline, only a downstream metric that looked wrong. Prevention: add `validate="one_to_one"` (or whichever cardinality is actually intended) to every merge in the pipeline where cardinality is a correctness assumption, so any future violation raises `MergeError` at the merge itself instead of propagating silently; pair this with a row-count assertion immediately after each merge (`assert len(merged) == len(left)`) as a second, cheap layer of defense.
**Follow-up trap:** *"Why not just always use `validate='many_to_many'` to be safe?"* — `many_to_many` provides essentially no protection, since it permits duplicates on both sides; using it everywhere "to avoid errors" defeats the entire purpose of the parameter, which is to make a specific cardinality *assumption* explicit and enforced, not to silence a class of check you're worried about failing.

---

## Red flags that fail you

- Recommending `.apply(axis=1)` as a default without mentioning vectorisation first.
- Not knowing why an integer column with one NaN becomes float64.
- Confusing `agg`, `transform`, and `filter`.
- Not knowing what `validate=` on `merge` does or why it matters.
- Describing `SettingWithCopyWarning` from memory as still-current pandas behavior without checking the pandas 3.0 change.
- Claiming pandas scales fine to arbitrary data sizes "if you just optimize the code."
- Not knowing the difference between `resample` and `rolling`.

---

## Cheat card

```
SPEED         vectorised < .apply(axis=1) < .iterrows() ; vectorised often 50-700x faster than
              the other two at 100k-1M rows; itertuples() > iterrows() when a loop is unavoidable
NaN PROMOTION  int64 column + 1 missing value -> silently upcast to float64 (no NA bit pattern in int64)
              fix: nullable "Int64" dtype (capital I) preserves int semantics w/ pd.NA
CATEGORY      stores unique values once + small int codes per row; wins on LOW cardinality columns;
              no benefit (adds overhead) on high-cardinality/mostly-unique columns
DOWNCAST      pd.to_numeric(s, downcast="integer"/"unsigned"/"float"); int64->int8 example = 8x smaller
groupby       agg -> ONE ROW PER GROUP (reduce) | transform -> SAME SHAPE (broadcast back)
              filter -> SUBSET OF ORIGINAL ROWS (keep/drop whole groups by predicate)
MERGE how     inner/left/right/outer/cross
MERGE validate  "one_to_one"/"one_to_many"/"many_to_one"/"many_to_many" -> raises MergeError
                BEFORE silently fanning out rows on a cardinality violation
COW (pandas 3.0, Jan 2026)  Copy-on-Write is the ONLY mode; SettingWithCopyWarning REMOVED;
              chained assignment df[mask]['col']=x now RAISES; fix: df.loc[mask, 'col'] = x (one step)
RESHAPE       pivot (long->wide, cols) / melt (wide->long, cols) / stack+unstack (same, on MultiIndex)
              pivot raises on duplicate (index,columns) pairs -> use pivot_table (aggregates) instead
DATE->MONTH ROWS   per-row pd.date_range(start, end, freq="MS").tolist() -> df.explode(col)
                   guard empty-list rows (same-month range) before exploding or they vanish
                   SQL: generate_series(...) (Postgres/DuckDB) or JOIN calendar table BETWEEN dates
TIME SERIES   resample = changes ROW COUNT/frequency, calendar-aligned; rolling = SAME row count,
              sliding window (by ROW COUNT by default -- use rolling("7D") for calendar-time windows)
SCALE THRESHOLDS   pandas: comfortably under ~1GB/few hundred M cells, single machine
              Polars: >1-5GB, need multi-core, lazy optimization
              DuckDB: SQL-shaped agg over files > RAM, no warehouse
              PySpark: ~10B+ rows / 10+TB, genuinely multi-machine
```

## Sources

- [Pandas 3.0 Released! — pandas community blog](https://pandas.pydata.org/community/blog/pandas-3.0.html) — accessed 2026-08-01
- [What's new in 3.0.0 (January 21, 2026) — pandas documentation](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) — accessed 2026-08-01
- [Pandas 3.0 Introduces Default String Dtype and Copy-on-Write Semantics — InfoQ](https://www.infoq.com/news/2026/02/pandas-library/) — accessed 2026-08-01
- [Pandas 3.0's Biggest Shift: Copy-on-Write Becomes the Only Mode — Medium](https://medium.com/@sathishdba/pandas-3-0s-biggest-shift-copy-on-write-becomes-the-only-mode-87a1870a144f) — accessed 2026-08-01
- [Pandas merge() Validate Parameter: A Complete Guide — CyberAngles](https://www.cyberangles.org/blog/validate-in-merge-function-pandas/) — accessed 2026-08-01
- [Efficient Pandas: Apply vs Vectorized Operations — Towards Data Science](https://towardsdatascience.com/efficient-pandas-apply-vs-vectorized-operations-91ca17669e84/) — accessed 2026-08-01
- [Pandas Memory Optimization: Reduce DataFrame Memory Usage — Python Data Bench](https://pythondatabench.com/article/pandas-memory-optimization-reduce-dataframe-memory-usage) — accessed 2026-08-01
- [Pandas vs Polars vs DuckDB: What Data Scientists Should Use in 2026 — Analytics Insight](https://www.analyticsinsight.net/programming/pandas-vs-polars-vs-duckdb-what-data-scientists-should-use-in-2026) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
