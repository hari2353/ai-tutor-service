# Production notes — Oracle SQL semantics

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Run real Oracle locally | Oracle Database Free (23ai) in a container | `docker run -d gvenzl/oracle-free`; the honest way to check dialect claims |
| Run Oracle without installing Oracle | Oracle Live SQL (livesql.oracle.com) | Browser-based; the fastest way to verify `'' IS NULL` on a real engine |
| Embedded mini-SQL in tests | sqlite3 via `sqlite3` module | But sqlite3 does NOT have Oracle semantics — `'' IS NULL` is FALSE there. That difference is why this lab exists. |

## What the real engine adds over yours

- **Cost-based optimization**: the 12c+ optimizer recognizes `ROW_NUMBER() <= n` and Top-N patterns and short-circuits the sort (stop-after-n). Your `top_n_analytic` sorts everything.
- **Rowid, partition pruning, hash joins**: the execution machinery under the semantics; irrelevant to correctness of the dialect traps.
- **Session/instance-level NLS parameters**: sort order for strings is locale-dependent (`NLS_SORT=BINARY` vs linguistic). Your lab assumes total ordering of comparable values.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Top-N returns wrong rows only sometimes | ROWNUM + ORDER BY in the same query level — input order dependent, so it "works" in dev data and fails in prod | Subquery wrap or FETCH FIRST |
| `WHERE col <> ''` matches nothing after data migration | MySQL/CSV empty strings became NULL in Oracle — predicate can never be true | Fix the data or the predicate: `WHERE col IS NOT NULL` |
| DESC report shows NULL rows first | Oracle NULL-high default | `NULLS LAST` |
| MERGE upsert throws ORA-30926 | Staging has multiple rows per target key | Dedupe staging (ROW_NUMBER() = 1) before MERGE |
| Pagination skips/duplicates rows | OFFSET pagination over data that changes between pages | Keyset pagination (`WHERE (salary, id) < (:last_salary, :last_id) ORDER BY ...`) |

## The one-liner to remember

ROWNUM is assigned **before** ORDER BY executes — every Top-N question is a
question about WHERE in the pipeline the limit fires.
