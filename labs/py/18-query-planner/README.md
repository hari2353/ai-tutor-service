# Lab 18: A Cost-Based Join Planner From Scratch

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2h · **XP:** 50
**Module:** `T17-query-planner`

**You will build:** a Selinger-flavored toy optimizer — statistics in, EXPLAIN-style plan out. Page math, three join algorithms costed on *estimated* rows, and a left-deep join-order search that is fully deterministic.

**You will be able to answer:** *"How does the planner decide between nested loop, hash, and merge join — and why can a stale row estimate flip its choice?"*

## Setup

```bash
cd labs/py/18-query-planner
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The cost model (memorize these — they are the whole lab)

```
PAGE_SIZE 8192 bytes

pages(r, w)      = ceil(r*w / 8192)                       # 0 rows => 0 pages
seq_scan         = pages(rel.est_rows, rel.row_width)
index_scan(sel)  = idx_height + rel.est_rows*sel * (rows/idx_keys)
nested_loop      = pages(outer) + outer_rows * pages(inner)
hash_join        = pages(build) + pages(probe) + 25.0 + 0.02*build_rows   # build = smaller side
sort(n, w)       = 2.5 * max(pages(n,w),1) * log2(max(pages(n,w),2))
merge_join       = 0.01*(a_rows+b_rows) [+ sort(a), + sort(b) for each UNSORTED input]

join est_rows    = ra * rb * join_sel                     # independence assumption
composite sel    = product of every edge into the new relation (else DEFAULT_JOIN_SEL=0.01)

tie-break        = lower ALGORITHM_RANK (nested_loop < hash_join < merge_join),
                   then lexicographic relation-name order — always deterministic
sortedness       = only merge joins keep their output sorted; Relation.sorted_key
                   marks an input that arrives pre-sorted (e.g. from an index scan)
```

## The spec

1. **`Relation(name, rows, row_width)`** carries the stats; optional `predicates` are `Predicate(column, selectivity)` factors that multiply under the independence assumption into `.selectivity` / `.est_rows`. `Relation.sorted_key` marks inputs already sorted on the join key.
2. **Scan costing** — `pages()` is the floor of everything; `seq_scan_cost` reads each page once; `index_scan_cost(rel, selectivity, idx_height, idx_keys)` descends the tree then pays a `rows/idx_keys` clustering penalty per matched row. Pass selectivity in; the planner never sees data.
3. **Join algorithms on ESTIMATED output rows** — nested loop re-reads the inner's pages once per outer row (small outer wins); hash join reads both sides once plus a small per-build-row overhead (build = smaller side); merge join walks two sorted streams near-linearly but must add an O(n log n) `Sort` per unsorted input.
4. **`plan_join(rel_a, rel_b, join_sel, algorithms_available)`** costs every available strategy and returns the cheapest-looking `Plan(algorithm, est_rows = ra·rb·join_sel exactly, cost, steps)`.
5. **`best_order(rels, join_sels)`** — left-deep-only search over up to 6 relations: DP over prefixes with greedy beam pruning (`beam_width=None` ⇒ exhaustive; `brute_force_best_order` is the no-pruning reference). Ties break by algorithm rank then name order.
6. **`explain(plan)`** — aligned text table: `ALGORITHM | EST_ROWS | COST | OPERATION`, one row per step, works on scan-only plans too.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Bushy trees** — extend the DP to composite × composite pairs (full Selinger) and construct the query where a bushy shape beats every left-deep order. *(Interview: "when does the planner consider cartesian products?")*
2. **EXPLAIN ANALYZE diff** — add an `actual_rows` field, re-run `plan_join` with actuals, and report per-node estimate/actual divergence ratios like Postgres does.
3. **Adaptive execution** — after the first join completes with real cardinality, re-run `best_order` for the remaining relations and report how often the plan shape changes.
4. **GEQO-lite** — go beyond 6 relations with random restarts + swap mutation; compare hit-rate against brute force on 7–8 relations.
5. **Correlated columns** — let two predicates share a correlation factor and show how it bends the winner selection versus naive multiplication.
