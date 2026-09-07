# Lab 19: Oracle SQL Semantics From Scratch

**Track:** T18 Data Engineering & Warehousing · **Time:** 2h · **XP:** 50
**Module:** `T18-oracle-sql`

**You will build:** a miniature Oracle-semantics query engine — `ROWNUM` assigned
before `ORDER BY`, `FETCH FIRST/WITH TIES/OFFSET`, Oracle's empty-string-as-NULL,
NULL-high default ordering with `NULLS FIRST/LAST` overrides, `NVL`/`NVL2`/`DECODE`,
and Top-N via analytic `RANK`/`DENSE_RANK`/`ROW_NUMBER` — the six dialect traps
every Oracle interview probes.

**You will be able to answer:** *"Why does `WHERE ROWNUM <= 5 ORDER BY salary DESC`
return the wrong five rows — and write me the three correct forms."*

## Setup

```bash
cd labs/py/19-oracle-sql-semantics
pip install pytest                                # only dependency
```

## The spec

1. **`oracle_string(value)`** — Oracle's `VARCHAR2` coercion: `''` (empty string)
   becomes `None`. The rest passes through. This one function is why
   `WHERE email <> ''` matches nothing in Oracle.
2. **`oracle_compare(a, b)`** — NULL-aware comparison: anything vs `None` is
   `None` (unknown), never `True`/`False`. Non-null values compare normally.
3. **`apply_rownum(rows, predicate, order_by=None)`** — the engine's heart.
   `ROWNUM` is assigned **as rows enter the result set, before any ORDER BY
   executes**: with an ORDER BY present the limit applies to the *pre-sort*
   intermediate, so you must sort in a subquery, filter ROWNUM outside.
   `rownum = 1` works; `rownum = 2` can never be satisfied (row 2 can only be
   numbered after row 1 exists).
4. **`fetch_first(rows, n, order_by=None, ties=False, offset=0)`** — the 12c
   row-limiting clause: sort first, then `OFFSET m ROWS FETCH NEXT n ROWS ONLY`,
   and `WITH TIES` includes boundary-ranked equals (needs `order_by`).
5. **`order_oracle(rows, key, desc=False, nulls=None)`** — Oracle sorts NULLs
   as **higher than any value**: ASC puts them last, DESC puts them first.
   `nulls="first"|"last"` overrides per-clause. Returns a NEW list.
6. **`nvl(expr, sub)`, `nvl2(expr, a, b)`, `decode(expr, *args)`** — the
   pre-COALESCE generation. `nvl` evaluates BOTH arguments (eager — the eager
   evaluation is the documented behavior the module flags); `decode` pairs
   `(match, result)` with an optional trailing default, and — the semantic
   difference worth the module — **`DECODE(NULL, NULL, x)` MATCHES** while
   `NULL = NULL` is unknown.
7. **`top_n_analytic(rows, n, key, desc=True, func="rank")`** — the modern
   Top-N: window function over the whole set, then filter. `rank` skips after
   ties (1,1,3), `dense_rank` doesn't (1,1,2), `row_number` is unique (1,2,3).
   `rank` with ties-included semantics matches `FETCH FIRST n ROWS WITH TIES`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Pagination both ways** — offset-pagination via nested ROWNUM filters
   (`rn > 5 AND rn <= 10`) versus `OFFSET/FETCH`; prove they agree.
2. **Date-carrying TIME** — model Oracle DATE (always carries time-of-day) so
   `TRUNC`-style day-boundary predicates stop missing last night's rows.
3. **DECODE eager evaluation** — count evaluations with a side-effecting probe
   and prove all branches evaluate (the cost `CASE` avoids).
