# Star vs Snowflake Schema, Facts & Dimensions, SCD Types 0-6, Grain

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.5h · **Prereqs:** `T17-normalization`, `T17-oltp-vs-olap` · **Updated:** 2026-07-26
> **Module id:** `T17-dimensional-modeling` · **Tags:** modeling, critical

## The 30-second version

Dimensional modeling deliberately denormalizes a schema for analytical query performance: a **fact table** holds numeric measurements at a precisely defined grain (one row per what, exactly — the single most consequential decision in the whole design, because it cannot be cleanly fixed after the fact without rebuilding history), and **dimension tables** hold the descriptive context (who, what, where, when) joined to it by surrogate keys. A **star schema** flattens every dimension into one wide, denormalized table per dimension (fast, fewer joins); a **snowflake schema** normalizes dimensions into sub-tables (smaller, more joins, easier to maintain hierarchies) — the star is the default recommendation almost everywhere today because storage is cheap and join count dominates query latency more than storage dominates cost. Measures are additive (sum across any dimension safely, like revenue), semi-additive (sum across some dimensions but not others, like account balance — summable across accounts, not across time), or non-additive (never sum, like a ratio or a rate) and mismodeling this class is a silent correctness bug, not a performance one. Slowly Changing Dimensions (SCD) handle the fact that dimension attributes change over time — Type 0 never changes, Type 1 overwrites (loses history), Type 2 adds a new versioned row with effective dates (preserves full history, the most common production choice), Type 3 adds a "previous value" column (limited, one-level history), Type 6 hybridizes 1+2+3 for both point-in-time and current-value reporting in one row. Surrogate keys (meaningless, database-generated, e.g. an auto-increment or hash) decouple the warehouse from the source system's natural keys, which is what makes Type 2 history and conformed dimensions across multiple fact tables possible at all.

## Why this gets asked

Because a resume claiming "built a data warehouse" or "designed the analytics schema" is easy to say and the grain question exposes whether you actually made the hard call or copied a pattern. The interviewer has watched a warehouse get rebuilt from scratch because the original team picked "one row per order" as the grain when the business later needed "one row per order line item," and every downstream report, every SCD Type 2 history table, and every aggregate built on top of the wrong grain had to be redone. They're also listening for whether you know the difference between additive and semi-additive measures, because summing an account balance across months to get a "total balance" is the single most common silent correctness bug in dimensional models — the query runs, returns a number, and the number is simply wrong.

---

## Lineage: past → present → future

**What came before.** Early decision-support systems ran directly against normalized OLTP-shaped schemas or ad hoc denormalized extracts with no consistent modeling discipline — every report team built its own flattened table for its own query, with no shared vocabulary for what a "customer" or a "sale" meant across reports, and no reusable structure. The pain: reports disagreed with each other because two teams' extracts defined "active customer" or "revenue" slightly differently, normalized joins across many tables made ad hoc analytical queries slow and hard for business analysts (not just engineers) to write, and there was no principled way to reuse a "customer" dimension across a sales fact and a support-tickets fact consistently.

**Where it stands now.** Ralph Kimball's dimensional modeling methodology (*The Data Warehouse Toolkit*, first edition 1996, still actively updated and taught) is the dominant practical framework: star schemas with conformed dimensions (the same `dim_customer` reused, with consistent keys and attributes, across every fact table that references a customer) as the standard unit of warehouse design. The competing school, Bill Inmon's top-down "Corporate Information Factory" (a fully normalized enterprise data warehouse, with dimensional marts built as denormalized extracts downstream of it), still has real adherents, particularly in large, governance-heavy enterprises, but the live consensus for most teams building analytics today is Kimball-style dimensional marts, often built directly on modern cloud columnar warehouses (see `15-oltp-vs-olap.md`) rather than a separate normalized EDW layer first. The genuinely live disagreement in 2026 is star vs. wide/one-big-table (OBT): modern columnar engines' compression and vectorised execution have made some practitioners argue that flattening everything into one enormous denormalized table (skipping the star's joins entirely) performs just as well or better on Snowflake/BigQuery/ClickHouse-class engines, at the cost of losing the star's reusability (conformed dimensions shared across facts) and update ergonomics (updating a dimension attribute in one wide table means rewriting it everywhere it's embedded, rather than once in a small dimension table). This is a real, ongoing debate, not settled.

**Where it's heading.** dbt (data build tool) and the broader "analytics engineering" movement have made dimensional modeling patterns (especially SCD Type 2, implemented via `dbt snapshot`) a codified, version-controlled, testable part of the transformation layer rather than a bespoke ETL script per warehouse — this is real and now mainstream practice, not speculative. Semantic layers (dbt's metrics layer, Cube, LookML-style definitions) are pushing measure definitions (additive vs. semi-additive handling, standard aggregation rules) into a shared, declarative layer above the physical schema, which is a genuine, maturing trend toward "define the measure's aggregation behavior once, enforce it everywhere" rather than trusting every analyst to remember not to `SUM()` an account balance across time. More speculative: fully automated grain/schema design assistants (an LLM or heuristic tool proposing a star schema from a source OLTP schema and sample queries) exist in early form in some vendor tooling, but the grain decision specifically remains something that requires understanding the actual business process being modeled, not just the data's shape — treat automated dimensional-model generation as assistive at best today, not a substitute for a human confirming the grain against real business requirements.

---

## Mental model

```
STAR SCHEMA

                    dim_date
                        │
    dim_customer ───────┼─────── dim_product
           \            │            /
            \           │           /
             \          ▼          /
              \    fact_sales    /
               \  (grain: one   /
                \  row per     /
                 \ order line) /
                  \___________/
                        │
                    dim_store

  fact_sales columns: date_key, customer_key, product_key, store_key,
                       quantity, unit_price, discount_amount, revenue
  — foreign keys to dimensions (surrogate keys), plus the MEASURES.

SNOWFLAKE SCHEMA (dim_product normalized further)

  dim_product ──▶ dim_category ──▶ dim_department
  (product_key,     (category_key,    (department_key,
   name, category_key) name, dept_key)  name)

  Same information, more joins, smaller per-table storage,
  easier to update "category name" in exactly one place.
```

**The grain is the contract.** Every measure in the fact table, every SCD decision on every dimension, and every aggregate built downstream assumes the grain is fixed and known. Changing it later (order-level to order-line-level) isn't a migration, it's closer to a rebuild, because every existing aggregate implicitly assumed the old grain's meaning.

---

## How it actually works

### Choosing the grain — the most consequential decision

**Grain** = the precise definition of what a single row in the fact table represents, stated as a business-process-level sentence, not a technical one: not "one row per record" but "one row per line item on a customer order" or "one row per daily snapshot of an account balance." The discipline (from Kimball) is to declare the grain explicitly and in writing before adding a single dimension or measure, because:

- **Too coarse a grain loses information you cannot recover later.** If you pick "one row per order" but the business later asks "which products drove this month's revenue," and you never stored line-item detail, there is no way to answer that from the fact table — you'd need to re-extract from the source system's history, which may no longer exist in the same form (source systems purge, schemas change).
- **Too fine a grain is always safe, just costs more storage/compute** — you can always aggregate up from a fine grain to a coarse one in a query or a derived aggregate table, but you can never disaggregate a coarse grain back down. This asymmetry is why "grain as fine as the business process actually generates" is the standard guidance, not "grain as coarse as today's known reports need."
- **Mixed grain in one fact table is a correctness bug waiting to happen** — a fact table with some rows at order-level and others at line-item-level (common when someone adds a "shipping fee" row per order alongside per-line-item rows) makes every naive `SUM()` silently double-count or miscount unless every query remembers to filter by row type first.

### Fact and dimension tables

A **fact table** is mostly foreign keys (to dimensions) plus numeric measures, and is typically the largest table in the warehouse by row count (one row per grain-defined event), narrow in column count. A **dimension table** is mostly descriptive text attributes, wide in column count, small in row count relative to the fact table, and is what business users actually filter and group by (`WHERE dim_customer.segment = 'Enterprise' GROUP BY dim_date.month`).

Three common fact table types:
- **Transaction fact** — one row per discrete business event (an order line, a click). Most common, most granular.
- **Periodic snapshot fact** — one row per entity per fixed time interval regardless of activity (end-of-day account balance for every account, every day, even unchanged accounts). Needed for semi-additive measures like balances.
- **Accumulating snapshot fact** — one row per process instance, updated in place as the process moves through stages (an order row with columns for `order_date`, `ship_date`, `delivery_date`, each filled in as it happens) — useful for pipeline/funnel analysis, but the "update in place" nature is a deliberate exception to the append-mostly norm of most fact tables.

### Additive, semi-additive, non-additive measures

- **Additive** — safe to sum across *every* dimension. Revenue, units sold, cost. The default, easiest case.
- **Semi-additive** — safe to sum across *some* dimensions, not others. **Account balance** is the canonical example: summing balances across accounts at the same point in time is valid ("total deposits across all accounts today"), but summing balances across time for the same account is meaningless ("balance on Monday plus balance on Tuesday" is not a real quantity — you want the balance on the *latest* day, or an average, not a sum). Inventory levels, headcount, and any point-in-time snapshot measure share this property.
- **Non-additive** — never safe to sum, under any dimension. Ratios, percentages, unit prices, rates. `avg(unit_price)` computed by summing unit prices and dividing by row count is also wrong if row counts vary per group — the correct aggregation is usually a weighted average or must be recomputed from the underlying additive components (`sum(revenue) / sum(quantity)`, not `avg(unit_price)`).

**This classification must be documented per measure, ideally enforced in a semantic layer**, because the failure mode is silent: the query executes, returns a plausible-looking number, and the number is simply wrong — there's no error, no exception, just a wrong dashboard that someone eventually notices (or worse, doesn't) diverges from a source-of-truth reconciliation.

### Slowly Changing Dimensions — Types 0 through 6

| Type | Mechanism | History preserved | When to use |
|---|---|---|---|
| **0** | Never update the attribute once set | N/A — it's fixed by definition | Attributes that genuinely never change (date of birth, original signup cohort) |
| **1** | Overwrite in place | None — old value is gone | Attribute where history genuinely doesn't matter (correcting a typo, a phone number format normalization) |
| **2** | Insert a new row with a new surrogate key, effective-date range (`valid_from`, `valid_to`, `is_current` flag) | Full history, one row per version | The default, most common choice for analytically significant attributes (address, job title, price tier) — this is what "slowly changing dimension" means when unqualified |
| **3** | Add a `previous_X` column alongside `current_X` | One prior value only | Rare — useful for "compare current vs. immediately-prior" reporting without needing full history, but loses anything beyond one step back |
| **4** | Split into a current table and a separate full history table | Full history, in a separate table | When the dimension changes so frequently that Type 2's row explosion in the main dimension table becomes a performance problem for current-state queries |
| **6** | Hybrid: Type 1 overwrite of a "current" column + Type 2 new row + Type 3 previous-value column, combined (1+2+3=6) | Both point-in-time and always-current views, in one row | When downstream reports need both "what did this look like at the time of the transaction" (Type 2 columns) and "what does this look like right now" (Type 1 current column) without a second join |

**Type 2 mechanics, concretely:**
```sql
-- Original row
customer_key | customer_id | address        | valid_from | valid_to   | is_current
     101     |    C500     | 123 Elm St     | 2024-01-01 | 2026-03-15 |   false
     205     |    C500     | 456 Oak Ave    | 2026-03-15 | 9999-12-31 |   true
```
The `customer_key` (surrogate) differs between versions; the `customer_id` (natural/business key) stays the same. Every fact row references the surrogate key that was current *at the time the fact occurred*, which is exactly what makes historical reporting correct — a sales fact from January 2025 joins to the `123 Elm St` version, correctly attributing that historical sale to the customer's address at the time, not their current one.

Type 7 (not in the requested range but worth knowing exists, per Kimball's own later documentation) combines a Type 2 durable surrogate key with an additional durable natural-key-plus-current-flag row specifically to support both "as-was" and "as-is" reporting simultaneously without a Type 6's column-level hybridization — mentioned here only because interviewers occasionally ask "is there a Type 7" and the honest answer is yes, it exists, and it's a variant solving the same as-was/as-is problem Type 6 solves via a different mechanism.

### Surrogate keys

A **surrogate key** is a meaningless, database-generated identifier (auto-increment integer, or a hash) for each dimension row, distinct from the **natural key** (the business/source-system identifier, like a customer ID from the OLTP system). Surrogate keys are what make Type 2 SCD possible at all — the natural key `C500` needs to map to *two different* surrogate keys over time (101 for the old address, 205 for the new one), which a natural-key-only design cannot represent. Surrogate keys also insulate the warehouse from source-system key reuse or format changes (a source system migrating from integer IDs to UUIDs doesn't require rebuilding warehouse history if the warehouse never depended on the natural key format directly), and they're typically smaller, fixed-width integers that join faster than wide natural keys (a real, if secondary, performance benefit).

### Conformed dimensions

A **conformed dimension** is a dimension built once, with consistent keys, definitions, and granularity, then reused across multiple fact tables — `dim_customer` referenced identically by `fact_sales`, `fact_support_tickets`, and `fact_marketing_touches`. This is what makes **drill-across** queries possible (comparing sales and support-ticket volume by the same customer segment definition) without every fact table needing its own redundant, potentially inconsistent copy of customer attributes. Kimball's "bus matrix" (a grid of business processes/fact tables against shared dimensions) is the standard planning artifact for identifying which dimensions must conform across which facts before building them independently and discovering later that two teams built incompatible `dim_customer` variants.

---

## Build it from scratch

A minimal Type 2 SCD implementation, showing the mechanics of versioning a dimension row on change:

```python
# untested sketch — illustrates Type 2 SCD mechanics, not a full ETL pipeline
from dataclasses import dataclass
from datetime import date

@dataclass
class DimCustomerRow:
    surrogate_key: int
    customer_id: str          # natural key, stable across versions
    address: str
    valid_from: date
    valid_to: date
    is_current: bool

class Type2Dimension:
    def __init__(self):
        self.rows: list[DimCustomerRow] = []
        self._next_key = 1

    def upsert(self, customer_id: str, new_address: str, as_of: date):
        current = next((r for r in self.rows
                         if r.customer_id == customer_id and r.is_current), None)

        if current is None:
            # brand-new customer: insert first version
            self.rows.append(DimCustomerRow(
                self._next_key, customer_id, new_address,
                as_of, date(9999, 12, 31), True))
            self._next_key += 1
            return

        if current.address == new_address:
            return  # no change — Type 1/Type 2 hybrid logic could go here for other attrs

        # Type 2: close out the old version, insert a new one
        current.valid_to = as_of
        current.is_current = False
        self.rows.append(DimCustomerRow(
            self._next_key, customer_id, new_address,
            as_of, date(9999, 12, 31), True))
        self._next_key += 1

dim = Type2Dimension()
dim.upsert("C500", "123 Elm St", date(2024, 1, 1))
dim.upsert("C500", "456 Oak Ave", date(2026, 3, 15))   # triggers a new version

for r in dim.rows:
    print(r)
# DimCustomerRow(surrogate_key=1, customer_id='C500', address='123 Elm St',
#                valid_from=2024-01-01, valid_to=2026-03-15, is_current=False)
# DimCustomerRow(surrogate_key=2, customer_id='C500', address='456 Oak Ave',
#                valid_from=2026-03-15, valid_to=9999-12-31, is_current=True)
```

This is the exact mechanic `dbt snapshot` automates in production (comparing incoming source rows against the current snapshot state, closing out changed rows, inserting new versions) — understanding this loop by hand is what makes reading a `dbt snapshot` config or debugging its output tractable. Full version with a fact table joining against point-in-time-correct dimension versions, plus a worked semi-additive-measure query: **`(lab pending)`**.

---

## How it's done in production

**dbt.** `dbt snapshot` implements Type 2 SCD as a declarative config (specify the unique key, the strategy — `timestamp` or `check` — and which columns to track) rather than hand-written upsert logic; it's now the standard tool for this in most modern cloud-warehouse stacks. Semantic layers (dbt Semantic Layer/MetricFlow, Cube, LookML) let teams declare a measure's aggregation type (sum, average, or a custom formula) once, centrally, so a semi-additive measure like balance can be configured to always resolve to "latest value" rather than trusting every analyst writing ad hoc SQL to remember not to sum it.

**Cloud columnar warehouses.** Snowflake, BigQuery, and ClickHouse (see `T17-clickhouse`) are where star schemas are typically physically implemented today, leveraging columnar compression and vectorised execution (see `15-oltp-vs-olap.md`) to make even fact tables with billions of rows and several dimension joins perform acceptably for BI/dashboard workloads — this is a meaningfully different cost profile than running the same star schema on a row-store OLTP engine, where the joins would be far more expensive.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| A "total balance" or "total headcount" dashboard number is implausibly large | Semi-additive measure summed across time (or another invalid dimension) instead of taking the latest/average value | Reclassify the measure explicitly, fix the aggregation logic (usually to "latest snapshot" or a properly weighted calculation), enforce via a semantic layer going forward |
| Historical reports change retroactively when a customer's current attribute changes | Dimension implemented as Type 1 (overwrite) when the business actually needs point-in-time history — a sales report from last year now shows this year's customer segment | Convert to Type 2, backfilling historical versions if any source history is recoverable (if not, this is a real, sometimes unrecoverable data-loss incident) |
| A fact table's row count doesn't match what any query expects, aggregates are inconsistently off | Mixed grain in one fact table (some rows at one grain, others at a finer or coarser grain) | Split into separate fact tables per grain, or add and enforce a `grain_type` discriminator column with query-level discipline (fragile; separate tables are more robust) |
| Two departments' reports on "the same" metric disagree | Non-conformed dimensions — two teams built separate `dim_customer`-equivalent tables with different filtering/definitions | Consolidate into a single conformed dimension, referenced identically by both fact tables; use a bus matrix to plan shared dimensions before building new fact tables |
| Adding a new source-system field requires rebuilding the whole dimension table | Dimension built directly on the source system's natural key with no surrogate key layer, making schema evolution and Type 2 versioning awkward | Introduce a surrogate key layer if not already present; this is a bigger migration after the fact than designing it in from the start |
| One-big-table (OBT) denormalized model becomes hard to maintain as more source attributes are added | Wide-table approach traded conformed-dimension reusability for query simplicity, and now every new attribute must be threaded through every downstream wide table that embeds it | Accept the tradeoff was made deliberately (fine) or migrate the affected attributes back into a proper conformed dimension if update frequency/reuse need has grown past what OBT comfortably supports |

---

## Tradeoffs & when NOT to use it

- **Snowflake schemas are worth the extra joins only when a dimension's hierarchy changes independently and frequently enough that updating it in one normalized sub-table meaningfully beats updating a flattened, denormalized column across a huge dimension table.** For most dimensions, the star's flat, denormalized form is the right default — the join savings and query simplicity outweigh the storage/update-locality argument for snowflaking, especially on modern columnar engines.
- **Type 2 SCD is overkill for attributes nobody will ever query historically.** Blindly Type-2-ing every dimension attribute creates enormous, mostly-useless row bloat; reserve Type 2 for attributes with real analytical significance to history (address, tier, assigned rep) and Type 1 for the rest (typo corrections, formatting normalization).
- **Do not pick the grain based on today's known reports alone.** Grain should follow the actual business process's natural granularity; picking a coarser grain to save storage is a false economy the first time a new, more granular question gets asked, because you cannot disaggregate history you never captured.
- **One-big-table (wide, fully denormalized) approaches are a legitimate, debated alternative on modern columnar engines**, but they sacrifice conformed-dimension reuse and make updating a shared attribute (a customer's segment) a multi-table rewrite instead of a single small dimension-table update — appropriate for narrower, single-purpose marts, riskier for a warehouse serving many fact tables that should share dimensions.
- **Dimensional modeling is the wrong tool for the OLTP system itself** — this is a read-optimized, deliberately denormalized analytical pattern; applying star-schema thinking to your transactional application database reintroduces exactly the update anomalies normalization (see `16-normalization.md`) exists to prevent.

---

## Interview questions

### Q1 — What is "grain" and why is it the most consequential decision in a dimensional model?
**Testing:** baseline, but "why most consequential" filters for actual understanding.
**Answer:** Grain is the precise definition of what one fact-table row represents, stated as a business-process sentence (e.g., "one row per order line item"). It's most consequential because every measure, every SCD choice, and every downstream aggregate assumes the grain; picking too coarse a grain loses information that cannot be recovered later (you can always aggregate up from fine to coarse, never disaggregate coarse back to fine), so grain mistakes require rebuilding rather than migrating.
**Follow-up trap:** *"Isn't storage cheap now, so why not always pick the finest possible grain?"* — finer grain is generally the safer default, but it's not free: it increases fact-table size, ETL cost, and query cost for aggregate-level questions unless supported by pre-aggregated derived tables; the real answer is "as fine as the business process actually generates, informed by cost tradeoffs," not "infinitely fine because storage is cheap."

### Q2 — Star vs snowflake: what's the actual tradeoff, and which is the default recommendation?
**Answer:** Star schema flattens each dimension into one wide, denormalized table — fewer joins, faster typical BI queries, some storage/update-locality cost for large slowly-changing hierarchies. Snowflake normalizes dimension hierarchies into sub-tables — smaller storage, easier single-point updates for hierarchy attributes, but more joins per query. Star is the default recommendation today because storage is comparatively cheap and query performance (dominated by join count on most engines) usually matters more.
**Follow-up trap:** *"When would you actually choose snowflake?"* — when a dimension's hierarchy attribute changes independently and frequently enough (e.g., a product category renamed centrally) that updating one normalized row beats rewriting a denormalized column across millions of fact-adjacent dimension rows, or when a strict governance/reuse requirement makes the hierarchy's sub-tables independently valuable to other parts of the model.

### Q3 — Explain additive, semi-additive, and non-additive measures with an example of getting each wrong.
**Answer:** Additive measures (revenue, units) sum safely across any dimension. Semi-additive measures (account balance, inventory level) sum safely across some dimensions (accounts, at a fixed point in time) but not others (time itself) — summing a balance across days produces a meaningless number. Non-additive measures (ratios, unit prices) should never be summed directly — an average unit price must be recomputed from underlying additive components (`sum(revenue)/sum(quantity)`), not averaged naively, since naive averaging ignores differing row weights per group.
**Follow-up trap:** *"How would you catch this kind of bug before it reaches a dashboard?"* — classify every measure's additivity explicitly in documentation or a semantic layer (dbt MetricFlow, Cube) that encodes the correct aggregation rule once and enforces it everywhere queries reference that measure, rather than relying on every analyst remembering the rule when writing ad hoc SQL — this is exactly the kind of bug that produces a plausible, wrong number with no error to catch it.

### Q4 — Walk through SCD Type 2 mechanics precisely, including why it needs a surrogate key.
**Answer:** On a change to a tracked attribute, the current row is closed out (`valid_to` set to the change date, `is_current` flipped false) and a new row is inserted with a new surrogate key, the new attribute value, and an open-ended `valid_to`. The natural key stays the same across versions, but the surrogate key differs — this is what lets a single business entity map to multiple distinct dimension rows over time, and it's what lets historical fact rows join to the version of the dimension that was correct *at the time the fact occurred*.
**Follow-up trap:** *"What happens to historical fact rows that already reference the old surrogate key when you create the new version?"* — nothing, and that's the entire point: those historical rows keep referencing the old (now `is_current=false`) surrogate key, which is exactly what makes the historical report correctly reflect the customer's attributes at the time of that historical transaction, rather than retroactively changing when the dimension changes.

### Q5 — Compare SCD Types 1, 2, 3, and 6 and give a scenario where each is the right choice.
**Answer:** Type 1 (overwrite, no history) — fixing a typo in a customer's name, where history has no analytical value. Type 2 (new versioned row) — a customer's address or sales-rep assignment, where historical reports need to reflect what was true at the time. Type 3 (previous-value column) — tracking only "current vs. immediately prior" sales territory for a specific comparison report, where full history isn't needed. Type 6 (hybrid 1+2+3) — when downstream BI tools need both a point-in-time-correct join (Type 2 columns) and an always-current value in the same row (Type 1 current column) without a second join back to the latest version.
**Follow-up trap:** *"Why not just always use Type 6 since it covers everything?"* — Type 6 costs more storage and ETL complexity (maintaining three mechanisms at once) than the simpler types, and if downstream consumers never actually need the "current value on a historical row" capability, it's unnecessary complexity — match the type to the actual reporting requirement, don't default to the most powerful option reflexively.

### Q6 — What is a conformed dimension and why does it matter for drill-across queries?
**Answer:** A dimension built once with consistent surrogate keys, attribute definitions, and grain, then reused identically across every fact table that references that kind of entity. It matters because comparing metrics across fact tables (sales volume vs. support-ticket volume by the same customer segment) requires both fact tables to agree on what "customer segment" means and how customers map to segments — without a conformed dimension, two teams' independently-built customer tables can define "Enterprise" differently, making cross-fact comparisons meaningless even though the query runs and returns a number.
**Follow-up trap:** *"How do you plan for conformed dimensions across a large warehouse with many teams?"* — Kimball's bus matrix: a grid of business processes/fact tables against shared candidate dimensions, built and agreed on before teams independently build fact tables, specifically to catch "these two teams are about to build incompatible dim_customer variants" before it happens rather than reconciling it after the fact.

### Q7 — Why are surrogate keys necessary for Type 2 SCD, beyond just "best practice"?
**Answer:** A natural key alone cannot represent one business entity having multiple valid attribute-versions over time in a relational sense — you'd need the natural key to be non-unique in the dimension table, breaking primary-key semantics and making it ambiguous which version a foreign key reference means. A surrogate key gives each version its own unique identity, so a fact table's foreign key unambiguously points to one specific version of the dimension row, which is structurally what makes point-in-time-correct historical joins possible at all.
**Follow-up trap:** *"Is there any performance benefit to surrogate keys beyond enabling Type 2?"* — yes, secondarily: surrogate keys are typically small, fixed-width integers, which join faster and index more compactly than wide or variable-length natural keys (UUIDs, composite business keys), and they insulate the warehouse from source-system key format changes or key reuse across systems.

### Q8 — A fact table mixes order-level summary rows (shipping fee, one per order) with order-line-level rows (one per product). What's wrong, and how do you fix it?
**Answer:** This is a mixed-grain fact table — a correctness bug, not a performance one, because any naive `SUM(amount)` across the table double-counts or miscounts unless every query remembers to filter by row type first, which is fragile and easy to forget. Fix by splitting into two fact tables at their own consistent grains (an order-level fact for order-wide charges like shipping, and a line-item fact for per-product amounts), or by relocating the shipping fee into the line-item grain (e.g., allocated proportionally across lines) if a single fact table is truly required.
**Follow-up trap:** *"Isn't adding a `row_type` discriminator column and teaching everyone to filter on it good enough?"* — it technically works but is fragile: every future query author (including ones unfamiliar with this table's history) must remember the discipline, and BI tools building automatic aggregates often won't apply a bespoke filter by default — separate fact tables at consistent grains remove the failure mode structurally rather than relying on institutional memory.

### Q9 — What is the one-big-table (OBT) debate in dimensional modeling, and where does it genuinely make sense?
**Answer:** Modern columnar engines' compression and vectorised execution make some practitioners argue that flattening facts and all dimension attributes into one wide denormalized table performs as well as or better than a star schema's joins, at the cost of losing conformed-dimension reuse (the same customer attributes now live redundantly in every wide table that includes them) and update ergonomics (changing a customer's segment means rewriting it everywhere it's embedded, not once in a dimension table). It makes sense for narrower, single-purpose analytical marts serving one or a few closely related reports where the reuse and update-locality benefits of a proper star schema are genuinely not needed.
**Follow-up trap:** *"So is star schema modeling becoming obsolete?"* — no, this is a live, debated tradeoff, not a settled replacement; for warehouses serving many fact tables that need to share dimension definitions consistently (the conformed-dimension use case), star schemas remain the more maintainable choice, and OBT's advantages are most clearly real for narrower, self-contained marts rather than as a wholesale warehouse architecture.

### Q10 — Design a dimensional model for a subscription business needing both "MRR as of any historical month" and "current subscription tier per customer" reporting.
**Testing:** applying grain, fact-table-type, and SCD choices together on a realistic scenario.
**Answer:** A periodic snapshot fact table (`fact_subscription_snapshot`, grain: one row per subscription per month) captures MRR and status at each month-end — semi-additive by nature (summable across subscriptions at a point in time, not across months). `dim_customer` and `dim_plan` use SCD Type 2 so each snapshot row joins to the plan/tier that was actually active in that month, correctly attributing historical MRR to the tier that generated it. For "current subscription tier" reporting without an extra join to find the latest dimension version, Type 6 on `dim_plan` (combining a Type 1 "current tier" column with the Type 2 versioned columns) lets both point-in-time and always-current queries run off the same table.
**Follow-up trap:** *"Why a periodic snapshot instead of a transaction fact recording only plan-change events?"* — a transaction fact (one row per upgrade/downgrade/cancellation event) is more storage-efficient but makes "MRR as of any given month" a derived, stateful computation (replaying events forward to reconstruct any historical month's state) rather than a direct query; a periodic snapshot trades storage for making every historical month directly queryable without replay logic, which is usually the right trade for a metric queried as often and as variably (any historical month, not just the latest) as MRR typically is.

### Q11 — Why is "you can always aggregate up but never disaggregate down" the central argument for choosing a finer grain, and when does that argument not apply?
**Answer:** A fact table at line-item grain can always produce an order-level total via `SUM()`, but a fact table stored only at order-level can never recover which products contributed to that total once the finer-grained source detail is gone. The argument doesn't apply (or applies less forcefully) when the source system itself never captures finer-grained detail at all — you can't extract line-item detail from a source that only ever recorded order totals — in which case the achievable grain is bounded by the source, not a free choice.
**Follow-up trap:** *"What if capturing the finer grain would 100x the fact table's size for a business need that may never materialize?"* — this is a real, legitimate cost/risk tradeoff, not a settled rule; the Kimball guidance to default toward finer grain assumes the finer detail is available and the storage/compute cost is acceptable, and a deliberate, documented decision to start coarser (with the explicit acknowledgment that finer-grained history won't be recoverable later) is sometimes the right call under genuine cost constraints — the failure mode is making that tradeoff silently rather than as a stated decision.

### Q12 — How does a semantic layer (dbt MetricFlow, Cube, LookML) change how measure additivity is handled in production, versus relying on analysts writing raw SQL?
**Answer:** A semantic layer lets you declare a measure's correct aggregation behavior once — e.g., "account_balance resolves to latest-value-per-group, never SUM across time" — and every downstream query, dashboard, or ad hoc tool built against that semantic layer inherits the correct behavior automatically, rather than depending on every analyst independently knowing and remembering the semi-additive rule when writing raw SQL against the physical tables.
**Follow-up trap:** *"Does this eliminate the need to classify measures correctly in the first place?"* — no, it just moves where the classification decision lives and how consistently it's enforced; someone still has to correctly identify that a measure is semi-additive and configure the semantic layer's aggregation rule accordingly — the tooling prevents inconsistent *application* of the rule across many consumers, it doesn't replace the analytical judgment of identifying the rule correctly to begin with.

---

## Red flags that fail you

- Not being able to state a fact table's grain as a business-process sentence, only as "the main table."
- Summing a semi-additive measure (balance, inventory) across time without flagging it as wrong.
- Confusing star and snowflake, or not knowing why star is usually the default recommendation.
- Not knowing why Type 2 SCD requires a surrogate key.
- Claiming you can always fix a too-coarse grain later without qualification.
- Mixing grains in one fact table without recognizing it as a correctness bug.
- Treating conformed dimensions as a nice-to-have rather than what makes cross-fact comparison meaningful at all.

---

## Cheat card

```
GRAIN     precise definition of ONE fact row, as a business-process sentence.
          MOST consequential decision — can aggregate fine->coarse, NEVER
          disaggregate coarse->fine. Mixed grain in one fact table = correctness
          bug (naive SUM double-counts/miscounts).

STAR      each dimension flattened, denormalized, ONE table. Fewer joins.
          DEFAULT recommendation today (storage cheap, joins dominate latency).
SNOWFLAKE  dimension hierarchy normalized into sub-tables. Smaller, easier
          single-point hierarchy updates, MORE joins. Use when a hierarchy
          attribute changes independently/frequently at scale.
OBT (one-big-table)  fully denormalized, no separate dims. Real, debated
          alternative on columnar engines — loses conformed-dim reuse +
          update locality. Fine for narrow single-purpose marts.

MEASURES  additive: sum across ANY dimension (revenue, units).
          semi-additive: sum across SOME dims not others (balance: sum across
            accounts OK, sum across TIME wrong — use latest/avg instead).
          non-additive: NEVER sum directly (ratios, unit price — recompute
            from additive components: sum(revenue)/sum(qty), not avg(price)).
          Wrong classification = SILENT correctness bug, no error thrown.

SCD TYPES  0: never changes.
           1: overwrite, NO history.
           2: new row + surrogate key + valid_from/valid_to/is_current.
              DEFAULT for analytically significant attrs. Needs surrogate key.
           3: add previous_X column — ONE prior value only.
           4: current table + separate full-history table (perf escape valve).
           6: hybrid 1+2+3 — current col (T1) + versioned rows (T2) +
              previous col (T3) — point-in-time AND always-current in one row.
           7: (bonus) durable surrogate key + durable natural key/current flag —
              alt mechanism for same as-was/as-is goal as Type 6.

SURROGATE KEY   meaningless, DB-generated (auto-inc/hash). Required for T2 —
                natural key alone can't represent multiple valid versions.
                Also: smaller/faster joins, insulates from source key changes.

FACT TABLE TYPES   transaction (one row/event, most common)
                   periodic snapshot (one row/entity/interval — needed for
                     semi-additive measures like balance)
                   accumulating snapshot (one row/process instance, updated
                     in place as it progresses — funnel/pipeline analysis)

CONFORMED DIMENSION   same dim (keys+defs+grain) reused across multiple facts.
                      Enables drill-across queries. Plan via Kimball bus matrix
                      BEFORE teams build incompatible versions independently.

TOOLING    dbt snapshot = Type 2 SCD as declarative config, not hand ETL.
           Semantic layers (MetricFlow/Cube/LookML) = declare aggregation
           rule (additive/semi/non) ONCE, enforce everywhere.
```

## Sources

- [Slowly Changing Dimensions (2026): SCD Types 1-6 Explained — DataDriven](https://datadriven.io/data-modeling/slowly-changing-dimensions) — accessed 2026-07-26
- [Type 7: Dual Type 1 and Type 2 Dimensions — Kimball Group](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-7/) — accessed 2026-07-26
- [Slowly changing dimension — Wikipedia](https://en.wikipedia.org/wiki/Slowly_changing_dimension) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
