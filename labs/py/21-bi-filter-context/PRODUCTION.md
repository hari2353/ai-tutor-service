# Production notes — BI filter context

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| The real engine | Power BI (DAX) / Tableau (LOD) | Your 100-line model is their semantic layer, minus 10 years of edge cases |
| Star schemas | dbt + warehouse | Dimensional modelling as code; the model IS the contract |
| Governed measures | Power BI semantic model / LookML | One definition of "revenue" — the whole reason the layer exists |
| Analysis-as-code | DAX Studio / tabular editor | Measure debugging leaves the UI within a week of real use |

## What production adds over yours

- **Many-to-many + row-level security**: real models add bridge tables and per-user predicates; your star assumes clean one-to-many edges — the moment it isn't, the filter graph gains cycles.
- **Vertipaq/extract engines**: calculated columns materialise into compressed stores; the measure-vs-column choice is a storage decision, not just a semantic one.
- **Time intelligence**: DAX's `SAMEPERIODLASTYEAR` family is calendar-aware with a marked date table — the #1 source of silent wrongness when the table isn't marked.
- **Query folding**: visuals push filters down to SQL where possible; when the measure can't fold, the model evaluates in-memory — the performance cliff.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Same measure, different number per visual | Implicit filter contexts differ (visual/page/report) | Check "show items as related" — filter propagation is the model |
| Totals don't sum the rows | The measure re-evaluates under the total's context | Iterator measures (`SUMX`) or `HASONEVALUE` branches |
| FIXED disagrees with the slicer | By definition it does | That's the lesson — choose LOD or table-calc deliberately |
| Report slow after "one more column" | Calculated column materialised at refresh | Convert to measure; push transforms upstream to Power Query |

## The one-liner to remember

A measure is evaluated in filter context at query time; a calculated
column is computed at refresh and stored — CALCULATE is the only verb
that changes the context.
