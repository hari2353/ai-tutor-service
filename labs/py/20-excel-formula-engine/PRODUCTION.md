# Production notes — Excel's dynamic-array engine

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| The real engine | Microsoft 365 Excel / Excel 2021+ | The dynamic-array tier does not exist in Excel 2016/2019 perpetual |
| Formula library automation | `openpyxl` (write), `xlwings` (drive a live Excel) | openpyxl CANNOT evaluate formulas; xlwings round-trips through a running Excel |
| Headless evaluation | formulas, pycel (open-source formula engines) | Both struggle with post-2019 dynamic arrays — spills are exactly where they rot |
| Table-shaped data work | pandas → export | For analysis, not for formula semantics |

## What the real engine adds over yours

- **Lazy dependency graph**: formulas pull, not push; a spill recomputes its dependents via a dependency DAG your dict-of-cells doesn't model.
- **Volatile scheduling**: `TODAY`/`INDIRECT`/`RAND` mark the graph dirty on every edit — the recalc-storm mechanism the module names.
- **Query folding into Power Query / the model**: the formula tier is the middle of three tiers; production moves ETL upstream.
- **Full error algebra**: `#SPILL!`, `#N/A`, `#NAME?`, `#REF!` propagate through arithmetic and comparisons; stretch goal 3 models the start of it.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| `#SPILL!` appears after data was "always there" | Someone inserted a row/column into the claimed range | Move the blocker or the anchor; spills refuse to overwrite by design |
| Formulas silently return wrong columns | `VLOOKUP` col_index after an insert | `XLOOKUP` — lookup and return arrays are independent |
| Workbook slow on every keystroke | Volatile functions (`INDIRECT`/`OFFSET`/`TODAY`) in thousands of cells | Structured references + `LET`-cached values |
| Opens with `@` prefixes everywhere | Pre-2019 file pasted into a dynamic-array build — implicit intersection shims each spill | Accept the `@` or re-author the formulas |

## The one-liner to remember

One formula owns a live range; `#SPILL!` is the engine refusing to destroy
data — a safety property, not an error.
