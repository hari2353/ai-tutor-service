# Excel for Data Analysts: LET, LAMBDA, Dynamic Arrays, XLOOKUP, the 15 Modern Formulas

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-09-04
> **Module id:** `T18-excel-analyst` · **Tags:** excel,critical

## The 30-second version

Modern Excel is a functional programming environment wearing a spreadsheet's clothes. Since 2019–2020 it has dynamic arrays that spill (`FILTER`, `SORT`, `UNIQUE`, `SEQUENCE`), `XLOOKUP` that replaces `VLOOKUP` and looks left, `LET` for named intermediates, and `LAMBDA` — custom named functions with no VBA — plus array-helpers `BYROW`/`BYCOL`/`SCAN`/`REDUCE`. The interview-relevant divide is between people who still build workbooks out of nested IFs, helper columns and Ctrl+Shift+Enter arrays, and people who can collapse that scaffolding into a few live formulas that update themselves. A pass sounds like "I'd replace that Remove-Duplicates + helper-column setup with `UNIQUE(FILTER(...))` in one cell"; a fail sounds like defending `VLOOKUP` because "it's what the team knows." The honest caveat: only Microsoft 365 / Excel 2021+ has the dynamic array engine, and finance/consulting shops on Excel 2016 still exist — know which world you're in before prescribing.

## Why this gets asked

Because "Advanced Excel" is on every data-analyst resume and interviews for analyst roles (especially in India's services sector, banks, and consulting) probe it directly: "XLOOKUP vs VLOOKUP", "how would you do a running total without dragging", "calculated column vs measure" adjacency, and the classic "here's a messy workbook, what formula collapses it?" Interviewers ask it because the formula engine's modern tier is only five years old and self-taught analysts' knowledge froze at whatever year they learned — a candidate who volunteers `LET` unprompted signals they kept current; a candidate who narrates nested-IF heroics signals the opposite. It's also the cheapest possible probe of analytical thinking: given a table of 5 rows, what formula does the candidate reach for first?

---

## Lineage

**What came before.** Lotus 1-2-3 defined the formula-grid paradigm in 1983; Excel shipped for Mac in 1985 and Windows in 1987 with a function library built for accounting: `SUM`, `IF`, `VLOOKUP` (1985-era thinking: lookup the first column, return to the right, exact-match as an opt-in argument that most people forgot). Array formulas existed but required Ctrl+Shift+Enter and existed in one cell at a time — arrays as an incantation, not a data type. Everything that "advanced Excel" meant for 30 years — helper columns, nested IF pyramids, `$`-anchored ranges dragged down 10,000 rows — was a workaround for the engine's lack of first-class arrays.

**Where it stands now.** In 2019–2020 Microsoft shipped the biggest change in the product's history: the dynamic array engine and the `#` spill operator, with six flagship functions (`FILTER`, `SORT`, `SORTBY`, `UNIQUE`, `SEQUENCE`, `RANDARRAY`), then `XLOOKUP`/`XMATCH`, then `LET` (2019), then `LAMBDA` and its recursion (2020–2021), plus the `MAP`/`REDUCE`/`SCAN`/`BYROW`/`BYCOL`/`MAKEARRAY` family. Formulas became lazy, cached, nameable programs; the Name Manager became a function library; and the Microsoft 365 subscription model meant the engine updates continuously — "Excel" is no longer one product across the market. Power Query (2016, built into the product) took ETL out of the formula layer, and Power Pivot/DAX took modeling out of it — the formula engine is now deliberately the middle tier of a three-tier tool.

**Where it's heading.** Three directions. First, Python-in-Excel (2023, Anaconda-backed, `py()` cells) is production reality on 365 and points at a hybrid future where the formula tier hands off to pandas for the heavy math. Second, Copilot/copyless AI formula generation is changing the skill being tested from "recall syntax" toward "recognize the right structure and audit what was generated" — interviews are starting to probe judgment about generated formulas. Third, the collaborative/online tier (Excel for the web, linked data types) keeps making the single-user-workbook world smaller. Flagged as direction, not certainty: Excel 2016-era shops are still real, so "which world are we in?" remains the correct first question in any workbook discussion.

---

## Mental model

```
        ┌─ Power Query  (ETL: clean/shape/merge — data BEFORE the grid)
source ─┤
        ├─ Data Model  (Power Pivot: star schema, measures, DAX)
        │
        └─ FORMULA TIER (this module — the live calculation surface)
              ├─ classic:  IF/VLOOKUP/SUMIF — one cell, one value, dragged
              └─ modern:   dynamic arrays SPILL from one anchor cell
                           LET  = local variables
                           LAMBDA = user-defined functions (Name Manager)
                           BYROW/SCAN/MAP = functional combinators
```

The two sentences that unlock everything: a **spill range** is a live array output from ONE formula cell (resize happens automatically; the `#` operator references it whole, e.g. `SUM(E2#)`), and **`@`-implicit-intersection is the compatibility shim** that silences a spill when a modern formula is opened in a legacy file context. If you understand that one formula now OWNS a range, every downstream difference (sort-on-edit, spill-block errors `#SPILL!`, blue borders) follows logically.

---

## How it actually works

### 1. The dynamic array engine, mechanically

Type `=UNIQUE(B2:B100)` into an empty cell. The engine computes a 1×N array, writes it starting at that cell, and marks the whole output as a spill range with a blue border. Two consequences interviewers probe: (a) if anything occupies a cell the spill needs, the formula returns `#SPILL!` instead of overwriting — spills never destroy data; (b) editing any source value re-runs the whole formula and re-sizes the spill, which is why "no helper columns" is now literally true. The `#` operator (`E2#`) refers to the entire spill from its anchor, so aggregations track the spill's current size without `$` ranges. Legacy one-cell behavior is recovered with `@` (implicit intersection) — the tell that a workbook predates 2019 or was pasted into one.

### 2. The lookup rewrite: XLOOKUP and XMATCH

`XLOOKUP(lookup, lookup_array, return_array, [if_not_found], [match_mode], [search_mode])` fixes the four VLOOKUP defects in one signature: it looks any direction (return array is independent of lookup array — insert-column breakage ends), exact match is the default (VLOOKUP's silent approximate-match default is the single most damaging Excel bug in the wild), `if_not_found` replaces `IFERROR` wrapping, and `search_mode=-1` searches last-to-first for the most-recent match. `XLOOKUP` also accepts a multi-column return array and spills all of it: `=XLOOKUP("Sarah", A2:A6, B2:D6)` returns Dept, Sales AND Region from one formula. `XMATCH` adds wildcard `match_mode=2` and reverse search to position-lookup.

### 3. LET: local variables, one calculation

`=LET(total, SUM(C2:C6), avg, AVERAGE(C2:C6), total - avg)` binds each name once, computes it once, reuses the name. Beyond readability, it is a performance primitive: Excel evaluates each named value exactly once, so `SUM` over a 500k-row range referenced three times in a formula costs one pass, not three. The interview version: "LET turns a formula into a scoped program; the reason it's faster is call-by-need with caching of the bound values."

### 4. LAMBDA: functions without VBA

`=LAMBDA(price, tax, price * (1 + tax))` is a value; saved in Name Manager as `CalcTotal`, it becomes `=CalcTotal(150, 0.08)`. Recursion works — a LAMBDA can call itself by its own saved name (the classic factorial/Fibonacci demo), which makes Excel accidentally Turing-complete without macros, and `MAP`/`REDUCE`/`SCAN` take LAMBDAs as combinators over arrays: `=SCAN(0, C2:C6, LAMBDA(acc, val, acc + val))` emits a running-total column from ONE formula — replacing the dragged `=SUM($C$2:C2)` pattern entirely. `BYROW(range, LAMBDA(r, SUM(r)))` computes per-row aggregates without the helper column.

### 5. The collapse-the-workbook canon (the 15)

The modern formulas ranked by what they replace: `LET` ← repeated sub-expressions; `LAMBDA` ← VBA UDFs; `FILTER` ← AutoFilter + helper columns + CSE arrays; `SEQUENCE` ← fill-handle numbering; `SORTBY` ← sort by a hidden column; `UNIQUE` ← Remove Duplicates + half of PivotTable usage; `TEXTSPLIT` ← Text-to-Columns; `TEXTBEFORE`/`TEXTAFTER` ← the LEFT/FIND/MID nested combo; `IFS` ← nested IF pyramids (with `TRUE` as the catch-all else); `XLOOKUP` ← VLOOKUP + INDEX/MATCH; `TAKE`/`DROP` ← manual slicing (and `TAKE(SORTBY(...), 3)` is a live top-3); `XMATCH` ← MATCH with modes; `BYROW`/`BYCOL` ← dragged row formulas; `SCAN` ← dragged running totals; `RANDARRAY` ← RANDBETWEEN copy-paste.

### 6. The supporting classics that still get asked

`SUMIFS`/`COUNTIFS` (multi-criteria aggregation — still the workhorse and fair game in every screen), `IFERROR` (error hygiene), `TEXT(date, "dd-mmm-yyyy")` and date arithmetic (`YEAR`/`MONTH`/`DATEDIF`/`NETWORKDAYS` — `NETWORKDAYS` for working-day math), `INDEX`+`MATCH` (still asked as "how did you do lookups before XLOOKUP" — and still needed in 2016 shops), `TRIM`/`CLEAN`/`SUBSTITUTE`/`VALUE` (the data-cleaning quartet that pairs with Power Query, not replaces it), Tables (`Ctrl+T`: structured references auto-expand, which is what makes dynamic-array workbooks survive data growth), and pivot-table fundamentals (the drag-and-drop tier that the formula tier complements).

---

## Practical exercise

Take a 5-column sales table (Name, Dept, Sales, Region, Email) and rebuild it three ways, timing each: (1) classic: extract domain from email with `MID(A2, FIND("@",A2)+1, 50)` dragged down, a helper column for "Sales>90k", `Remove Duplicates` for dept list, `VLOOKUP` for region; (2) dynamic arrays: `=TEXTAFTER(Email, "@")`, `=FILTER(names, sales>90000)`, `=UNIQUE(depts)`, `=XLOOKUP(name, names, region)`; (3) functional: `=BYROW(C2:E6, LAMBDA(r, MAX(r)))` per-row max, `=SCAN(0, sales, LAMBDA(a,v,a+v))` running total, `=LET(big, FILTER(...), TAKE(SORTBY(big, 2, -1), 3))` as a saved LAMBDA named `Top3`. Then break each on purpose: insert a column (watch method 1's VLOOKUP return wrong data silently — the exact-match default's revenge), add rows (watch non-Table ranges strand the dragged formulas), and sort the source (watch `#SPILL!` teach you which cells the formulas own). The exercise's point: you should be able to LOOK at a legacy workbook and name which of the 15 collapses each scaffold section.

---

## How it's done in production

In real analyst workflows the formula tier is the middle of three tiers, and mature shops enforce the boundaries: Power Query owns extraction and cleaning (refreshable, inspectable steps — a formula that cleans data hides its logic in a cell; a PQ step shows it in a pane), the Data Model owns cross-table relationships and time intelligence (DAX measures, not mega-formulas), and the formula tier owns ad-hoc analysis and self-updating report blocks. The recurring production failures are all boundary violations: 40-tab workbooks where the formula tier is doing ETL (rebuild in PQ), volatile-heavy sheets (`INDIRECT`, `OFFSET`, `TODAY` in thousands of cells — recalc storms; replace with structured references and LET-cached values), and the "one person's workbook" problem (undocumented LAMBDA libraries — production shops keep LAMBDA definitions in a documented names sheet, because a custom function nobody can discover is a bus-factor of one). Version discipline matters too: a workbook using `FILTER` saved for a 2016 shop breaks on open, so the metadata question "what Excel builds does the team run?" is a real production question, not small talk.

---

## Tradeoffs

**Modern formulas vs helper columns.** Dynamic arrays trade inspectability for live-updating compactness: a helper column shows its work row-by-row (auditors and non-analyst stakeholders can follow it), while a spilled `SCAN` is one formula whose per-row logic requires reading a LAMBDA. Rule of thumb from practice, not law: collaboration-heavy sheets bias toward helper columns; refresh-automation sheets bias toward spills.

**LET everywhere vs readability.** LET adds a binding layer someone must parse; for two-term formulas the classic version is genuinely simpler. The honest cut: use LET when a sub-expression repeats (the perf win is real) or when a formula exceeds one screen — not as reflex.

**LAMBDA vs Power Query.** LAMBDA puts logic in the workbook's function namespace — versioned by "did anyone save a new copy," invisible to diffs; PQ puts it in an inspectable, step-by-step query. When the same transform is needed by multiple workbooks, PQ (or actual code) wins; LAMBDA is for the in-workbook math vocabulary, not ETL.

**XLOOKUP vs INDEX/MATCH.** XLOOKUP is strictly more capable in 365, but INDEX/MATCH remains the lingua franca of 2016 shops and every tutorial cohort trained before 2020. In interviews: volunteer XLOOKUP, be able to write INDEX/MATCH fluently, and know the exact-match default difference by heart.

**Excel vs pandas/SQL.** Excel's real edge is the last mile — a stakeholder can touch the intermediate values, and that interactivity is a feature, not a weakness. Above ~1M rows or ~50 workbooks of duplicated logic, the analysis belongs in a notebook/warehouse; the production analyst's skill is recognizing that boundary when the workbook starts exceeding its mandate, not defending either side of it.

---

## Interview questions

**Q1 — What's the difference between VLOOKUP and XLOOKUP, and when would you still use VLOOKUP?**
- **Strong:** Names the four fixes (direction-independence so inserts don't break, exact-match default, built-in if-not-found, reverse/last-match search) plus the multi-column return spill; "still use VLOOKUP" gets the honest answer — only in a pre-2021 Excel build or a legacy team's convention, and even then I'd write INDEX/MATCH to get exact-match safety.
- **Weak:** "XLOOKUP is newer and better" with no named difference; or claims VLOOKUP is "faster" (it isn't materially).
- **Follow-up trap:** *"Why is VLOOKUP's approximate-match default dangerous?"* Wants the ascending-sort assumption explained: unsorted data returns a silently WRONG value, not an error — the failure is invisible, which is the whole point.

**Q2 — You have a helper-column-heavy workbook. How do you modernize it?**
- **Strong:** Walks a concrete example (running total → `SCAN`; dragged row-total → `BYROW`; Remove-Duplicates → `UNIQUE`) and names the precondition check first: what Excel builds does the team run — if 2016, none of this ships and the answer is Power Query + INDEX/MATCH instead.
- **Weak:** "I'd rewrite it with modern formulas" with no examples and no version check.
- **Follow-up trap:** *"What breaks when you save that for a colleague on Excel 2016?"* Wants: `#NAME?` errors on the new functions, `@`-implicit-intersection mangles spills, and the realization that the version question should have preceded the rewrite.

**Q3 — Explain LET. Why does it exist?**
- **Strong:** Local named bindings computed once and reused — for readability when a sub-expression repeats, and for performance because Excel caches each bound value (a thrice-repeated `SUM` over 500k rows computes once, not three times).
- **Weak:** "It lets you name things" with no compute-once point.
- **Follow-up trap:** *"When would you NOT use LET?"* Two-term formulas where a binding layer costs more readability than it buys; reflexive LET is a smell, not a virtue.

**Q4 — What is a spill range? What is `#SPILL!`?**
- **Strong:** One formula owns a live output range, auto-resized on recalc, referenced whole via `E2#`; `#SPILL!` means the range is blocked by existing content — spills refuse to overwrite, by design a safety property, not a bug.
- **Weak:** "The formula fills multiple cells" without the ownership/refusal mechanism.
- **Follow-up trap:** *"Your spill worked yesterday and shows #SPILL! today. Diagnose."* Wants: someone inserted a row/column putting content inside the spill's claimed range — and the fix is clearing the blocker, not re-typing the formula.

**Q5 — How do you do a running total without dragging a formula down?**
- **Strong:** `=SCAN(0, C2:C6, LAMBDA(acc, v, acc + v))` — one formula, the whole column spills, and generalizes to any accumulating logic (running max, running concatenation) by changing the LAMBDA body. Mentions the legacy answer (`=SUM($C$2:C2)` dragged) as the 2016 fallback.
- **Weak:** "I'd drag a SUM down" — the exact pattern the question says not to use.
- **Follow-up trap:** *"Top-3 by sales, live, no pivot?"* `TAKE(SORTBY(names, sales, -1), 3)` — tests whether TAKE/SORTBY composition came along with SCAN.

**Q6 — Calculated column vs measure (Power Pivot adjacency).**
- **Strong:** Column = row-context, computed at refresh, stored, takes model space, slices/filters by its values; measure = filter-context, computed at query time, not stored, for aggregations/KPIs. "Sales in the table as a column; Total Sales := SUM as a measure; never store what you can compute at query time."
- **Weak:** "A measure is like a formula but in DAX."
- **Follow-up trap:** *"Why not make every column a measure?"* Row-level values must be columns — measures can't exist per-row; the boundary is a data-modeling question, not a preference.

**Q7 — How would you clean this 10k-row text column (trimming, splitting, casing)?**
- **Strong:** Power Query for the durable version (steps are inspectable and refreshable); formula-tier for the ad-hoc pass (`TRIM`/`CLEAN`, `TEXTSPLIT` or `TEXTBEFORE`/`TEXTAFTER` for delimiter work, `PROPER` for casing) — and says which tier wins for a one-off vs a weekly refresh.
- **Weak:** Reaches for Find & Replace and hand-deletes.
- **Follow-up trap:** *"Why Power Query over formulas for the weekly version?"* Steps are documented, reusable on refresh, and testable — a formula's cleaning logic is invisible inside cells.

**Q8 — Your SUMIFS across 400k rows is slow. What do you do?**
- **Strong:** First diagnosis, not prescription: check the file tier (`.xlsx` vs `.xlsb` — binary is smaller/faster), volatile functions (`INDIRECT`/`OFFSET`/`TODAY` chains force full recalcs), and whole-column references; then structural moves: aggregate in PQ/the model instead of the grid, LET-cache repeated sub-ranges, or admit it's warehouse work ("at this size it's a SQL question wearing Excel clothes").
- **Weak:** "Excel is slow, I'd use Python" — skips the two cheap fixes that usually solve it.
- **Follow-up trap:** *"Which functions force recalculation storms?"* Volatility list from memory: `INDIRECT`, `OFFSET`, `TODAY`, `NOW`, `RAND` (and `RANDARRAY` — though it only recalcs on edit, the point is knowing the volatility concept at all).

**Q9 — Excel vs pandas for this analysis — how do you choose?**
- **Strong:** Three checks: row count (Excel hard-caps ~1.05M), reproducibility (a notebook is diffable; a workbook is binary), and audience (stakeholders who need to touch intermediate values get Excel; automation gets pandas). Notes Python-in-Excel as the bridge for 365 shops.
- **Weak:** Sectarian answer either way ("Excel is for noobs" / "pandas is overkill").
- **Follow-up trap:** *"Stakeholder needs the intermediate values AND it's 3M rows."* Wants the two-tier answer: compute in pandas/warehouse, deliver an Excel front-end of the result — not a 3M-row Excel file.

**Q10 — What are Tables (Ctrl+T) and why do they matter with dynamic arrays?**
- **Strong:** Structured references (`Sales[Amount]`) that auto-expand, formulas that track the table's growth without `$`-range surgery, and the reason spill-based reports survive new data — the two features are designed together.
- **Weak:** "It's a styled range."
- **Follow-up trap:** *"Your UNIQUE over a Table returned stale results after rows were added — why?"* Data-type mismatch (added rows came in as text-typed numbers) or the range left as a plain range during an edit — the answer shows they've actually bled on this, not just read about it.

---

## Red flags

- **Volunteers VLOOKUP as their primary lookup in 2026** — knowledge frozen pre-2019; not disqualifying alone, but paired with no XLOOKUP awareness it dates the whole skillset.
- **"I'd write a macro for that"** for anything the formula tier does natively (running totals, custom functions) — VBA reflex for LAMBDA problems.
- **No version awareness** — prescribing `FILTER` for a 2016 shop; production empathy starts with the build question.
- **Helper-column maximalism or spill maximalism** — both extremes read as ideology; the mature answer is tier-appropriate.
- **Can't write INDEX/MATCH** — the XLOOKUP-only analyst who fails the legacy-team interview question.

## Cheat card

- **XLOOKUP:** any direction, exact by default, `if_not_found` built in, `return_array` can spill multi-column.
- **Spills:** one formula owns the range, `#` references it, `#SPILL!` = blocked (never overwrites).
- **LET:** bind once, compute once — perf + readability; **LAMBDA:** saved function in Name Manager, recursion legal.
- **`SCAN(0, rng, LAMBDA(a,v,a+v))`** = running total; **`TAKE(SORTBY(x, y, -1), 3)`** = live top-3; **`BYROW`** = no helper column.
- **UNIQUE ← Remove Duplicates; FILTER ← helper cols; TEXTSPLIT ← Text-to-Columns; IFS ← nested IF; SEQUENCE ← fill handle.**
- **`@`** = implicit intersection (legacy shim); **`#`** = spill operator (modern whole-range).
- **Volatile: `INDIRECT`, `OFFSET`, `TODAY`, `NOW`, `RAND`** — recalc storms live here.
- **Tables auto-expand structured refs; Ctrl+T before anything serious.**
- **Row cap ~1,048,576**; beyond that it's warehouse work.
- **Tiers: Power Query (ETL) → Data Model (DAX) → formulas (live analysis)** — keep each in its lane.

## Sources

- The 15-formula modernization canon: the corpus's top Excel cluster (×1,216 crowd-weight, "15 Excel Formulas That Surprise 5+ Year Users", OCR-verified full slide deck, mining/posts/DcOEXEik4vt/), cross-checked against the formula cheat-sheet cluster (mining/posts/DbqF2ABCV0S/), accessed 2026-09-04.
- Dynamic array engine, spill operator, LAMBDA/LET semantics: Microsoft 365 Excel documentation ("Dynamic array formulas and spilled array behavior", "LET function", "LAMBDA function"); release timing 2019–2021 per Microsoft's function-release notes.
- VLOOKUP approximate-match hazard and INDEX/MATCH as lingua franca: long-standing practitioner consensus, covered in every serious Excel reference since 2010s.
- Row limit 1,048,576 and `.xlsb` performance: Microsoft specifications documentation.
- The three-tier production boundary (PQ/model/formulas): Microsoft's own Power Platform positioning plus practitioner inference; flagged where inferential.

## Changelog

- 2026-09-04: First version. Built from the mined 15-formula deck as the spine, extended with the engine mechanics, the three-tier production framing, and the classic-companion canon (SUMIFS/date/TEXT/cleaning) that screens still test.
