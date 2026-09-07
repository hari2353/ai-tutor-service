# Lab 21: BI Filter Context From Scratch (DAX semantics in miniature)

**Track:** T18 Data Engineering & Warehousing · **Time:** 2h · **XP:** 50
**Module:** `T18-bi-tooling`

**You will build:** the semantic model Power BI actually evaluates measures
against: a star schema (fact + dimensions, one-to-many), filter propagation
through relationships, a measure evaluated under filter context,
`CALCULATE` as the only context modifier (`ALL`/`REMOVEFILTERS` clear,
filter args replace), calculated-column-vs-measure semantics, and
Tableau-style `FIXED` LOD contrast — the two-sentence core of the module:
*a measure is evaluated in filter context at query time; a calculated
column is computed at refresh and stored.*

**You will be able to answer:** *"Why does my measure show the same number
in every row of this table visual — and what does CALCULATE actually do
about it?"*

## Setup

```bash
cd labs/py/21-bi-filter-context
pip install pytest                                # only dependency
```

## The spec

1. **`Model(relations)`** — a star schema: `relations` is a list of
   `(dimension_table_name, dimension_key, fact_table_name, fact_key)`
   one-to-many edges. `Model` holds the tables (dicts of `name -> rows`,
   each row a dict) and provides `filter_graph(dimension_filters)`:
   given `{dim_name: {key: [allowed values]}}`, return the set of fact-row
   indices surviving propagation through the relationships (filters fan
   from dimension to fact across the star's edges).
2. **`evaluate(model, fact, measure_fn, filter_ctx)`** — the measure
   engine. `filter_ctx` is `{dim: set(values)}`; resolve it to surviving
   fact rows via the model, then run `measure_fn(surviving_rows)`.
   Empty context = all rows. A measure NEVER sees filters on columns of
   OTHER dimensions it didn't ask for — the star's edges do the routing.
3. **`calculate(model, fact, measure_fn, filter_ctx, *modifiers)`** — the
   context TRANSITION: start from `filter_ctx`, apply each modifier in
   order, then evaluate. A modifier is one of:
   - `("filter", dim, {values})` — replace that dimension's filter,
   - `("all", dim)` — clear that dimension's filter entirely,
   - `("removefilters", dim)` — alias of `all` (DAX's newer spelling),
   - `("all_all", None)` — clear EVERYTHING (`ALL(...)` with no args).
   Modifiers are applied in order; the LAST one touching a dimension wins
   on that dimension. `("filter", ...)` on a dimension NOT in the context
   ADDS it (CALCULATE can introduce filters the visual never set — the
   whole point).
4. **`calculated_column(model, fact, name, row_fn)`** — the anti-measure:
   run `row_fn(row)` per fact row AT REFRESH, store the result on the row
   under `name`, return the new column values. Then prove the contrast:
   a measure `[Total]` slicing by a stored column respects filters; the
   same total as a MEASURE over a COLUMN VALUE the slicer set is identical
   only when the column exists — the model caps what's computable.
5. **`fixed_lod(model, fact, group_dim, agg_fn, filter_ctx)`** — Tableau's
   `{FIXED [dim]: SUM(x)}`: group ALL fact rows by `group_dim` (via its
   relationship), aggregate with `agg_fn` per group, and return the
   group->value dict — **ignoring `filter_ctx` on the grouping dimension**
   while still respecting context on OTHER dimensions. The disagreement
   with a context-respecting percent-of-total is the lesson.
6. **`percent_of_total(model, fact, measure_fn, filter_ctx, denom_ctx)`**
   — numerator under `filter_ctx`, denominator under `denom_ctx` (typically
   the empty context), ratio as a percentage. Tableau's table-calc flavor
   respects the context; FIXED doesn't — the lab's closing comparison.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Time intelligence** — add a Date dimension with `sameperiodlastyear(ctx)`
   as a modifier; the marked-date-table prerequisite becomes a validation.
2. **RLS** — role predicates on dimensions; prove the effective access is
   the intersection of role memberships and that they apply to READERS.
3. **Row-level context** — `SUMX`-style iterators that wrap each fact row
   in a one-row context transition; the deep-end DAX concept.
