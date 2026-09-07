# Lab 20: Modern Excel's Formula Engine From Scratch

**Track:** T18 Data Engineering & Warehousing · **Time:** 2h · **XP:** 50
**Module:** `T18-excel-analyst`

**You will build:** the semantics of the 2019–2021 dynamic-array Excel — spill
ranges that claim cells and refuse to overwrite (`#SPILL!`), the `#` operator
referencing a whole spill, `LET` as bind-once-compute-once local variables,
`LAMBDA` as first-class saved functions, `IFS` as a flat condition ladder, and
`XLOOKUP` with exact-match default and multi-column return — the engine
mechanics beneath the module's 15-formula canon.

**You will be able to answer:** *"What actually happens when a FILTER spills
over an occupied cell — and why is that a safety property, not a bug?"*

## Setup

```bash
cd labs/py/20-excel-formula-engine
pip install pytest                                # only dependency
```

## The spec

A worksheet is a `dict` mapping `"A1"`-style refs to values. `Sheet` (given in
the starter as a pre-built helper) parses refs and exposes `set/get`. You build:

1. **`ref_to_xy / xy_to_ref`** — `"B3" <-> (col=1, row=2)` zero-based. The
   plumbing every formula function leans on. Reject malformed refs with
   `ValueError`.
2. **`spill(sheet, anchor, values)`** — write `values` (a 2D list) starting
   at `anchor`, claiming a rectangular range. If ANY cell in the claimed
   range (other than anchor cells it already owns from a previous spill of
   the same anchor) is occupied by a non-spill value, write **`#SPILL!`** at
   the anchor and claim nothing. Spills never overwrite — that refusal is
   the safety property. Return the claimed ref-range `(top_left, bottom_right)`.
3. **`spill_ref(sheet, anchor)`** — the `#` operator: the whole range a
   spill at `anchor` currently owns, as a list of row-lists.
4. **`let(bindings, body_fn)`** — `bindings` is an ordered list of
   `(name, value)` pairs (values may reference earlier names); `body_fn`
   receives a name->value dict. **Bind-once-compute-once**: an expensive
   binding (a function with a side-effect counter, provided by tests) must be
   evaluated exactly ONCE per `let` call even if the body uses the name three
   times. That single evaluation is the performance primitive the module
   teaches.
5. **`lambda_fn(params, body_fn)`** — returns a callable; calling it binds
   params positionally and runs `body_fn(**params_dict)`. Lambdas compose:
   a saved lambda can be called from within another lambda's body.
6. **`ifs(pairs, default=None)`** — flat ladder of `(condition, result)`
   evaluated top-down; first truthy wins; the caller passes a `TRUE` pair
   as its own catch-all (Excel's idiom — the engine does not add one).
7. **`xlookup(sheet, lookup_value, lookup_col, return_cols)`** — exact match
   by default (the VLOOKUP-approximate-match fix); returns a list — one
   value per return column (the multi-column spill return). No match ->
   `#N/A` unless `if_not_found` is given.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **`@` implicit intersection** — a `spill_ref` used where a scalar is
   wanted resolves to the value in the same row; the compatibility shim.
2. **Volatile cells** — mark `RANDARRAY`-style anchors volatile and
   recompute the transitive dependents on any write; then show a
   `TODAY()`-in-a-thousand-cells recalc storm in miniature.
3. **Error values as first-class** — `#SPILL!`, `#N/A`, `#NAME?` propagate
   through arithmetic like Excel's errors (any cell referencing an error
   becomes that error).
