# Lab 04: A Toy Query Planner

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.5h · **XP:** 50
**Module:** `T17-query-planner`

**You will build:** a rule-based optimizer over in-memory tables with fake statistics: `Table` (rows + column stats: ndistinct, min/max), an index catalog, logical plan nodes as dataclasses (`SeqScan`, `IndexScan`, `Filter`, `Project`, `HashJoin`, `NestedLoopJoin`, `Limit`), and the rules that rewrite the plan: **predicate pushdown** (Filter below Project), **index selection** (`IndexScan` when estimated selectivity < 0.1, using ndistinct), **join algorithm choice** (HashJoin when the build side fits the memory budget, else NestedLoopJoin), **limit pushdown** (where legal). Plus an executor that proves the optimized plan returns the same rows as the naive one.

**You will be able to answer:** *"The query is slow — walk me through how you'd read the plan, and how does the optimizer decide between index scan, hash join, and nested loop?"*

## Setup

```bash
cd labs/py/04-planner-toy
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Table(name, rows, column_stats)`** — `rows` is a list of dicts; `column_stats` is `{column: {ndistinct, min, max}}`. `Catalog` holds tables plus indexes: `add_index(table, column)` records an index on one column.
2. **Plan nodes as dataclasses** — `SeqScan(table)`, `IndexScan(table, column, key)`, `Filter(child, predicate)` (predicate: `(column, op, value)` with ops `"="`, `">"`, `"<"`), `Project(child, columns)`, `HashJoin(left, right, left_key, right_key)`, `NestedLoopJoin(same fields)`, `Limit(child, n)`. Every node has `render()` producing one-line strings; a plan renders bottom-up like `SeqScan(users)->Filter(age>30)->Project(name)`.
3. **`estimate_selectivity(table, column, op, value)`** — equality: `1/ndistinct`; range (`>` / `<`): linear interpolation over `[min, max]` (clamped to 0..1). This is the fake `pg_stats`.
4. **`estimate_rows(node, catalog)`** — bottom-up row estimates: SeqScan → `len(table.rows)`; IndexScan → `selectivity × table rows`; Filter → child × selectivity; Project → child rows; Join → `outer × inner / max(ndistinct(join key), 1)` (uniformity assumption); Limit → `min(n, child)`.
5. **`Planner(catalog).optimize(plan)`** — applies the rules, each independently testable:
   - **Index selection**: a `Filter(col op value)` directly above a `SeqScan`, with an index on `col` and `selectivity < 0.1` (strictly below the threshold), becomes `IndexScan(table, col, value)` with the filter fused in. At or above 0.1 → keep the SeqScan.
   - **Predicate pushdown**: `Project(Filter(scan))` → `Filter(Project(scan))`? No — the *useful* direction is pushing the Filter *below* the Project toward the scan: `Project(Filter(X))` becomes `Filter(Project(X))` only when the projected columns still include the filter column; simpler and truer to real planners: a `Filter` above *any* node gets pushed as close to the scan as legal (never below a `Limit` it didn't originate above — pushing a Filter below a Limit changes semantics).
   - **Join algorithm**: for each join node, if the estimated build-side rows (the *smaller* estimated input) fit `memory_budget_rows`, choose `HashJoin`, else `NestedLoopJoin`.
   - **Limit pushdown**: `Limit(Project(Filter(Scan)))` → push the Limit *below* the Project (legal: projection is row-wise, order-preserving) so it reads `Filter(Project(Limit(Scan)))`-style shapes — but a Limit may **never** be pushed below a Filter it didn't start below (the filter might remove rows the limit needs to skip).
6. **`execute(plan)`** — the naive executor: runs any plan tree against the real rows (SeqScan materializes, IndexScan filters by key equality — the "index" is a groupby over the column, Filter evaluates the predicate, Project selects columns, HashJoin/NestedLoopJoin both produce inner-join semantics on the keys, Limit truncates). The optimizer changes the *shape*, never the *answer*: `execute(optimize(p)) == execute(p)` for every plan — sorted for comparison.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Cost model with page costs** — Postgres's `seq_page_cost=1.0`, `random_page_cost=4.0` (lower it to ~1.1-2.0 on SSD), `cpu_tuple_cost=0.01`. Turn "which join" into a single cost number instead of a budget flip.
2. **Estimated vs actual** — run `execute` and record actual rows per node next to the estimate; build the `EXPLAIN ANALYZE` view and write the test that detects a 10x+ divergence.
3. **Join order enumeration** — Selinger dynamic programming: for 3+ tables, cost all join *orders* not just both algorithms. Where does the factorial blow up (Postgres `geqo_threshold` = 12 tables)?
4. **Merge join** — both inputs pre-sorted on the key. When does it beat hash (sortedness you'd otherwise pay for)?
