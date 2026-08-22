# Source → Bronze → Silver → Gold: Modeling a Warehouse End to End

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** `T17-dimensional-modeling`, `T17-normalization` · **Updated:** 2026-08-01
> **Module id:** `T18-data-modeling-e2e` · **Tags:** modeling, critical

## The 30-second version

A warehouse is built in three layers with three distinct contracts: bronze is a raw, immutable, append-only copy of the source with zero business logic; silver cleans, deduplicates, and conforms entities into one consistent shape with surrogate keys and SCD applied; gold declares an explicit grain and turns that into business-grained, denormalized star schemas where every metric is defined exactly once. Skipping a layer's contract — querying bronze directly for a BI dashboard, say — is how two gold marts end up disagreeing about what "revenue" means. Kimball, Inmon, and Data Vault aren't rival answers for the whole warehouse, they're answers to different layers' constraints: Data Vault or Inmon-style discipline for a governed integration core, Kimball for the consumption-facing marts, chosen per layer based on governance load and rate of source-system change. Grain is the first decision made, before a single dimension or measure, because every join and SCD choice downstream assumes it's fixed, and getting it wrong later is closer to a rebuild than a migration.

## Why this gets asked

Because "we built a medallion architecture" is a phrase everyone can say and almost nobody can defend layer by layer. The interviewer wants to know whether you can state, precisely, what transformation is allowed in bronze versus silver versus gold, and whether you've actually made the grain decision under pressure rather than copied a diagram. They've also watched a team pick Kimball, Inmon, or Data Vault by whichever blog post they read most recently rather than by what their actual constraints (governance load, number of source systems, rate of business change) demanded — and they want to hear you reason from constraints, not from fashion. This module assumes `T17-dimensional-modeling` (star/snowflake, SCD types, grain, conformed dimensions) and `T17-normalization` as prerequisites and builds the end-to-end pipeline architecture on top of them; if SCD Type 2 mechanics are unfamiliar, read that module first.

---

## Lineage: past → present → future

**What came before.** Before the medallion pattern had a name, warehouses were built as one undifferentiated transformation layer: raw extracts were cleaned, joined, and aggregated in a single pass, often inside opaque stored procedures or a monolithic ETL tool's proprietary format. The pain: when a business rule changed (a new way of calculating "active customer"), there was no clean layer boundary to patch — the fix had to be threaded through a tangle of interdependent transforms, and debugging "why is this number wrong" meant re-deriving the entire pipeline's logic from scratch because there was no intermediate, inspectable checkpoint between raw and final. Kimball's dimensional modeling (1996) solved the *final* layer's shape (star schemas, conformed dimensions) but didn't by itself prescribe how to get from ungoverned raw data to that final shape safely.

**Where it stands now.** The medallion architecture (bronze/silver/gold — the term and its adoption are closely associated with Databricks' Delta Lake documentation, though the underlying staged-transformation idea predates the naming) is now the dominant practical pattern for organizing transformation layers in a lakehouse or warehouse: **bronze** is raw, immutable, append-only data landed as close to source format as possible; **silver** is cleaned, conformed, deduplicated, and joined into a consistent shape; **gold** is business-grained, aggregated marts ready for BI/ML consumption, typically Kimball-shaped (star schemas). This is now largely uncontested as an organizing pattern — the live disagreement has moved up a level, to which *methodology* governs the silver/gold boundary: Kimball dimensional marts directly, an Inmon-style normalized integration layer feeding marts, or a Data Vault hub/link/satellite layer as the historized integration point before Kimball marts downstream. Most serious 2026-era teams don't pick one methodology for the whole warehouse; they pick per layer — Data Vault or Inmon-style discipline for the governed integration core, Kimball for the consumption-facing marts, because each methodology solves the specific constraints that layer actually has to live with. What's actually deployed at scale, versus merely written about, skews heavily toward this hybrid pattern at any organization with more than a handful of source systems; a pure single-methodology warehouse is more common in blog posts than in production.

**Where it's heading.** dbt's layer-conventions (staging → intermediate → marts, mapping closely onto bronze/silver/gold) have made the medallion pattern something enforced by tooling and folder structure rather than tribal knowledge, which is a real, current, and largely settled trend. The **grain-and-SCD discipline from Kimball is being pushed into declarative, version-controlled config** (`dbt snapshot` for Type 2, contracts for grain-level guarantees) rather than bespoke ETL scripts, also a mainstream and settled direction. More speculative: automated grain inference and mart generation assisted by LLMs reading source schemas and sample queries exists in early vendor tooling, but the central claim of this module — that grain is a business-process decision requiring human judgment about what the business actually needs to ask later — means treat these tools as scaffolding to review, not a replacement for a human confirming the grain against real requirements.

---

## Mental model

```
  SOURCE SYSTEMS          BRONZE               SILVER                GOLD
  (OLTP DBs, APIs,     ┌───────────┐      ┌──────────────┐      ┌──────────────┐
   event streams)  ──▶ │ raw copy, │ ───▶ │ cleaned,     │ ───▶ │ business-    │
                       │ IMMUTABLE,│      │ deduped,     │      │ grained,     │
                       │ APPEND-   │      │ conformed,   │      │ aggregated   │
                       │ ONLY      │      │ TYPED,       │      │ marts        │
                       │           │      │ joined       │      │ (star schema)│
                       │ same shape│      │              │      │              │
                       │ as source,│      │ business     │      │ ready for    │
                       │ minimal   │      │ keys resolved│      │ BI / ML      │
                       │ transform │      │ to surrogate │      │ direct       │
                       └───────────┘      │ keys, SCD    │      │ consumption  │
                                          │ applied      │      └──────────────┘
                                          └──────────────┘

  Each arrow is a ONE-WAY transformation. Never write gold logic that reads
  bronze directly, skipping silver's cleaning/conforming — that's how two
  gold marts end up disagreeing about what "an active customer" means.
```

**The rule that makes this work**: each layer has an explicit contract for what it guarantees, and every layer downstream can *trust* that contract without re-deriving it. Bronze guarantees "this is what the source actually sent, unmodified, forever queryable as of any point in time." Silver guarantees "this is clean, deduplicated, and every key means one consistent thing." Gold guarantees "this number is the answer to a specific, named business question." Skipping a layer's contract (querying bronze directly for a BI dashboard) reintroduces exactly the tangled, un-debuggable pipeline the layering was invented to prevent.

---

## How it actually works

### What belongs in each layer, precisely

**Bronze — raw, immutable, append-only.** Load exactly what the source sent, in as close to its native shape as practical (a `VARIANT`/JSON column for semi-structured payloads is fine here — see the schema-drift discussion in `T18-ingestion`). No business logic, no joins, no deduplication. Append-only means you never `UPDATE` or `DELETE` a bronze row; a CDC update event becomes a *new* bronze row with its own event timestamp, preserving the full history of every change exactly as it arrived. This is deliberate: bronze is your only recovery path if a bug is discovered three months later in the silver transformation logic — you can always rebuild silver and gold from bronze, but you can never reconstruct bronze from a downstream layer that already discarded detail. **The most common bronze mistake**: applying "just a little" cleaning at this layer (trimming whitespace, casting a type) because it seems harmless — the moment bronze isn't a faithful, complete copy of what the source sent, you've lost your ability to answer "was this a source bug or a transformation bug" during an incident.

**Silver — cleaned, conformed, deduplicated.** This is where types are enforced, natural keys are resolved to surrogate keys, duplicate records (from at-least-once delivery, see `T18-ingestion`) are collapsed, business entities from multiple source systems are conformed to one consistent definition (the `customer` in the CRM and the `customer` in the billing system become one `dim_customer`-ready entity), and SCD Type 2 history is applied where the business needs point-in-time correctness. Referential integrity is enforced here (an order line referencing a nonexistent product is either fixed, quarantined, or explicitly flagged — not silently passed through). Silver is typically still close to source-system grain (one row per order line, not yet aggregated), just cleaned and joined.

**Gold — business-grained, aggregated marts.** This is where the grain decision (see below) is made explicit and dimensional modeling (`T17-dimensional-modeling`) is applied in full: fact tables at a stated grain, conformed dimensions, measures classified as additive/semi-additive/non-additive. Gold is intentionally denormalized for query performance and is where deliberate business logic lives — "revenue" is defined exactly once, here, and every consumer of "revenue" reads this definition rather than re-deriving it. Aggregation, business-rule application, and denormalization all belong here, not upstream.

### Grain — the first modeling decision, stated explicitly

Before a single dimension or measure is added to a gold fact table, state the grain as a business-process sentence: not "one row per record" but "one row per line item on a customer order" or "one row per daily snapshot of an account balance." This is covered in depth in `T17-dimensional-modeling`; the operational discipline that matters for an end-to-end pipeline is that **the grain decision has to be made before silver-to-gold transformation logic is written**, because every join, every aggregation, and every SCD choice downstream assumes a fixed grain, and discovering the grain was wrong after gold marts are already built by several consuming teams is closer to a rebuild than a migration.

### Kimball vs Inmon vs Data Vault — honestly compared

| | Kimball (dimensional) | Inmon (normalized EDW) | Data Vault 2.0 |
|---|---|---|---|
| Core unit | Star schema data marts, built bottom-up per business process | A single normalized, integrated enterprise warehouse, marts derived downstream | Hubs (business keys), links (relationships), satellites (attributes + history) |
| Optimized for | Query performance, ease of use for BI/analysts | Data integration, consistency, single source of truth | Auditability, agility to new sources, full history capture |
| Time to first value | Fast — build one mart for one business process, ship it | Slow — the integrated EDW has to be substantially built before marts derive value from it | Moderate — hubs/links are quick to add, but consumption requires a mart layer on top regardless |
| Handling new sources | Can require rework of existing marts if a new source changes a conformed dimension's meaning | Requires updating the central integrated model, which is more governed but slower | Designed for this — new sources add new satellites/links without altering existing structures |
| Consumption-readiness | Directly BI-ready | Not directly BI-ready; still needs a mart layer | Not directly BI-ready; explicitly requires a Kimball-style mart layer downstream |
| Where it's the honest recommendation | Small-to-mid orgs, few source systems, need fast time-to-value, or as the consumption layer regardless of what feeds it | Large, governance-heavy enterprises with many domains and regulatory pressure needing one authoritative model | Fast-changing businesses adding/replacing source systems frequently, or heavy audit/compliance requirements on data lineage and historization |

The honest, current synthesis (and the strongest interview answer): **these are not mutually exclusive choices for a whole warehouse — they solve problems at different layers.** A Data-Vault-modeled or Inmon-style normalized integration core, feeding Kimball-shaped marts as the consumption layer, is a common and defensible hybrid: the core gets historization/governance/audit benefits, the marts get query performance and BI ergonomics. Picking pure Kimball end-to-end is right when there's no governance mandate forcing an integration layer and time-to-value matters most. Picking pure Inmon or Data Vault with no Kimball mart layer on top usually means analysts end up hand-writing complex joins against a normalized or vaulted structure that was never meant to be queried directly — a real, recurring complaint in Inmon and Data Vault shops that skip the mart layer.

### A full worked example: source tables to a gold mart

Source system: an e-commerce OLTP database with `orders`, `order_items`, `customers`, `products` tables, plus a separate marketing system tracking `campaign_touches`.

1. **Bronze**: `bronze.orders_raw`, `bronze.order_items_raw`, `bronze.customers_raw`, `bronze.products_raw`, `bronze.campaign_touches_raw` — each append-only, one partition per ingestion batch, columns matching source shape plus `_ingested_at` and `_source_batch_id` metadata columns.

2. **Silver**: `silver.orders` (deduplicated on `order_id`, latest version per natural key via the pattern in `T18-ingestion`), `silver.customers` (conformed — the marketing system's `lead_id` and the OLTP system's `customer_id` resolved to one `dim_customer`-ready natural key via a mapping table, with SCD Type 2 applied to `address` and `segment` since historical reporting needs point-in-time correctness on both). Referential checks: every `order_items.product_id` must resolve to a `silver.products` row, or the row is quarantined (see `T18-data-quality`).

3. **Gold**: grain declared as "one row per order line item." `fact_order_lines` (transaction fact, grain: order line item; measures: `quantity`, `unit_price`, `discount_amount`, `line_revenue` — all additive) joins to `dim_customer` (Type 2, surrogate key, conformed across this mart and any future marketing-attribution mart), `dim_product` (Type 1 for most attributes, Type 2 for `category` since re-categorization matters for historical revenue-by-category reporting), `dim_date`. A second gold fact, `fact_customer_daily_snapshot` (periodic snapshot, grain: one row per customer per day), carries semi-additive measures like `lifetime_value_to_date` that must never be summed across the date dimension.

This worked example demonstrates the load-bearing pattern: **the same natural key (`customer_id`) resolves to different surrogate keys over time in silver's Type 2 table, and every gold fact row references the surrogate key version that was correct at the time the fact occurred** — exactly the mechanic detailed in `T17-dimensional-modeling`.

### Surrogate vs natural keys across layers

Bronze and silver still reference natural/source keys (you need them to join and dedupe against the source's own identity). The surrogate key is introduced specifically at the silver-to-gold boundary, for dimension tables that need SCD Type 2 — this is a deliberate, late introduction, not something bronze needs to worry about. A common mistake is generating surrogate keys too early (in bronze) before deduplication and conforming have happened, which produces surrogate keys for what turn out to be duplicate or since-merged entities.

### Late-arriving dimensions

A late-arriving dimension is a fact event that references a dimension entity (a customer, a product) that hasn't been loaded into the dimension table yet — common when fact and dimension data arrive on different pipelines with different latencies. The standard fix is an **inferred member**: insert a placeholder dimension row with just the natural key and surrogate key populated, unknown/null for other attributes, so the fact table's foreign key reference is never left dangling; when the real dimension data arrives later, the placeholder row is updated in place (a Type 1 correction, since the row never represented real history yet). Failing to handle this either drops the fact row (data loss) or leaves a broken foreign key (breaks every downstream join).

### Deliberate denormalization and its justification

Gold marts denormalize on purpose: a wide `dim_customer` table repeating `segment_name` and `region_name` as flat text columns rather than normalizing them into separate lookup tables trades some update cost (changing "segment_name" for a segment means updating it everywhere it's flattened, if not using a proper dimension table with a foreign key) for query simplicity (no extra joins for a BI tool or analyst writing ad hoc SQL). This is justified specifically because gold is the read-heavy, write-rare consumption layer — the update cost that denormalization would be dangerous for in an OLTP table (see `T17-normalization`) is a non-issue in a layer that's bulk-rebuilt or incrementally merged on a schedule, not point-updated by application code.

---

## Build it from scratch

A minimal three-layer pipeline showing the contract boundary between layers — not a full Spark/dbt implementation, but the shape of the logic each layer is responsible for.

```python
# untested sketch — illustrates layer boundaries and responsibilities, not a
# runnable Spark/dbt pipeline
from dataclasses import dataclass
from datetime import date

# ---------- BRONZE: append-only, no business logic ----------
def land_bronze(raw_batch: list[dict], source_table: str, batch_id: str) -> None:
    for row in raw_batch:
        row["_ingested_at"] = now()
        row["_source_batch_id"] = batch_id
    append_only_write(f"bronze.{source_table}_raw", raw_batch)   # never UPDATE/DELETE

# ---------- SILVER: clean, dedupe, conform, apply SCD ----------
@dataclass
class ConformedCustomer:
    surrogate_key: int
    natural_key: str        # resolved across CRM + billing systems
    segment: str
    valid_from: date
    valid_to: date
    is_current: bool

def build_silver_customers(bronze_rows: list[dict], key_mapping: dict[str, str]) -> list[ConformedCustomer]:
    deduped = dedupe_latest_per_natural_key(bronze_rows, key_fn=lambda r: key_mapping[r["source_id"]])
    return apply_type2_scd(deduped, tracked_columns=["segment"])   # see T17-dimensional-modeling

# ---------- GOLD: grain-explicit fact + conformed dimension join ----------
def build_fact_order_lines(silver_order_items: list[dict], silver_customers: list[ConformedCustomer]):
    """Grain: one row per order line item. Measures are additive (revenue, quantity)."""
    rows = []
    for item in silver_order_items:
        customer_key = resolve_surrogate_key_as_of(
            silver_customers, natural_key=item["customer_natural_key"], as_of=item["order_date"],
        )  # point-in-time correct join — the whole reason surrogate keys exist
        rows.append({
            "customer_key": customer_key,
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "line_revenue": item["quantity"] * item["unit_price"] - item["discount_amount"],
        })
    return rows
```

The line worth defending in an interview: `resolve_surrogate_key_as_of(..., as_of=item["order_date"])` — this is what makes a historical fact join to the dimension version that was true *at the time*, not the dimension's current state, and it's the single most common thing a naive gold-layer join gets wrong (joining on the natural key directly against a Type 2 table without an as-of filter returns every historical version, silently fanning out the fact table). Full runnable version with dbt models per layer: `labs/py/18-medallion-lab/`.

---

## How it's done in production

**Lakehouse table formats** (Delta Lake, Iceberg — see `T18-lakehouse`) implement bronze as append-only Delta/Iceberg tables with time-travel query support, which gives bronze's "queryable as of any point in time" guarantee natively rather than requiring bespoke versioning logic. **dbt** implements the silver and gold layers as SQL models organized by convention (`staging/` roughly maps to silver's cleaning step, `intermediate/` and `marts/` map to gold), with `dbt snapshot` automating Type 2 SCD mechanics and `dbt test`/contracts enforcing the layer boundaries described above. **Orchestration** (Airflow, see `T18-airflow`) sequences bronze → silver → gold as dependent DAGs or tasks, often with Airflow Assets/Datasets making the dependency data-aware (gold rebuilds when silver's relevant table actually updates, not on a blind fixed schedule — see `T18-scheduling-triggering`).

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| An incident can't determine if a wrong number is a source bug or a transformation bug | Bronze applied "light" cleaning instead of staying a faithful raw copy | Rebuild bronze as truly raw/immutable; move all cleaning to silver |
| Two gold marts disagree on "active customer" | A gold mart queried bronze/silver directly and re-derived its own definition instead of using the conformed silver entity or a shared gold dimension | Enforce that gold only reads from silver's conformed tables (or from other gold facts/dims), never from bronze |
| A fact table silently fans out (row counts inflate after a dimension update) | Gold join against a Type 2 silver dimension with no as-of filter, matching every historical version | Join with an explicit `as_of` / effective-date range filter, or join against the correct historical surrogate key already resolved in silver |
| A fact row is missing entirely after a load | A late-arriving dimension with no inferred-member handling caused the row to be dropped rather than pointed at a placeholder | Insert inferred-member placeholder rows for not-yet-seen dimension keys, update them in place (Type 1) when real data arrives |
| Rebuilding gold from silver takes hours because bronze can't reproduce a historical state | Bronze isn't actually append-only/immutable (something upstream mutated or deleted old batches) | Enforce append-only writes at the storage layer (object lock, Delta/Iceberg's native immutability) |
| A business rule change requires touching a dozen scattered SQL files | Business logic (aggregation, definitions) leaked into silver instead of being isolated to gold | Move all business-rule/aggregation logic to gold; silver stays purely about cleaning and conforming |
| Surrogate keys generated in bronze turn out to represent duplicate entities | Surrogate key assignment happened before deduplication/conforming | Move surrogate key generation to the silver-to-gold boundary, after dedup/conforming is complete |

---

## Tradeoffs & when NOT to use it

- **Do not apply business logic or aggregation in bronze or early silver.** It's tempting to "just filter out the obviously bad rows" at ingest, but every ad hoc filter applied before silver's formal cleaning step is undocumented business logic scattered across layers, and it's exactly what makes a future incident hard to trace.
- **Do not skip a mart layer on top of Inmon or Data Vault.** Both are explicitly integration-layer methodologies; querying a normalized EDW or a Data Vault hub/link/satellite structure directly for BI is painful (many joins, no denormalization for read performance) and defeats the purpose of separating integration from consumption.
- **Do not adopt the full medallion architecture for a small warehouse with one source system and three tables.** Three layers of transformation for a dataset that could be cleaned and aggregated in one pass is process overhead without payoff; the medallion pattern earns its complexity when there are multiple sources needing conforming, or when the audit/rebuild-from-raw guarantee genuinely matters.
- **Do not pick Data Vault for a small, stable business with one or two source systems that rarely change.** Data Vault's flexibility for adding new sources and historizing everything comes at real modeling and query overhead that isn't justified when the thing it protects against (frequent new sources, frequent schema churn) isn't actually happening.
- **Do not generate surrogate keys before deduplication and conforming are complete** — see the failure-mode table above; this is a common, costly-to-fix mistake specifically because surrogate keys propagate into every downstream fact table's foreign keys.

---

## Interview questions

### Q1 — State precisely what transformation is and isn't allowed in each medallion layer.
**Testing:** whether "medallion architecture" is a real mental model or a buzzword.
**Answer:** Bronze: no business logic, no joins, no deduplication — raw, immutable, append-only, as close to source shape as practical. Silver: cleaning, type enforcement, deduplication, conforming entities across sources, surrogate key assignment, SCD application, referential integrity checks — still near source grain. Gold: grain declared explicitly, dimensional modeling applied, aggregation, business-rule definitions (this is where "revenue" is defined exactly once), deliberate denormalization for query performance.
**Follow-up trap:** *"What if a business rule needs data from two different bronze sources before it can even be cleaned?"* — that's exactly what silver's conforming step is for: joining and reconciling across sources happens in silver, before gold's business-rule/aggregation logic runs, not by reaching back into bronze from gold to do the join inline.

### Q2 — Why must bronze be immutable and append-only, even when it costs more storage?
**Answer:** Bronze is the only layer that can reconstruct history if a bug is discovered in silver or gold transformation logic months later — you can always rebuild downstream layers from bronze, but you can never reconstruct bronze from a layer that already discarded raw detail through cleaning or aggregation. A CDC update event becomes a *new* bronze row with its own timestamp rather than overwriting the old one, preserving the complete change history exactly as it arrived.
**Follow-up trap:** *"Isn't that a lot of storage for data you might never need again?"* — storage is comparably cheap versus the alternative: an unrecoverable historical bug where the only fix is documenting a permanent gap (see `T18-backfill-replay`'s discussion of "sometimes the answer is documenting a gap"), which is a much worse outcome than paying for redundant bronze storage on the off chance it's needed.

### Q3 — Walk through Kimball vs Inmon vs Data Vault and give an honest recommendation for a fast-growing startup with three source systems versus a regulated bank integrating twenty.
**Answer:** Kimball dimensional marts built bottom-up, directly, is the right call for the startup — few sources, fast time-to-value matters most, and there's no governance mandate demanding a separate integration layer. The regulated bank with twenty source systems and audit/compliance pressure benefits from a Data Vault (or Inmon-style normalized) integration core specifically for its historization and auditability, with Kimball-shaped marts built on top of that core for actual BI consumption — the bank needs both the governance layer's guarantees and the marts' query ergonomics, which is why the honest answer for a large, regulated org is usually hybrid, not pure-Inmon or pure-Vault with no mart layer.
**Follow-up trap:** *"Isn't picking 'hybrid' just avoiding the question?"* — no, because the hybrid answer specifies *which methodology governs which layer* and *why* (integration core needs Vault/Inmon's historization/governance; consumption layer needs Kimball's query ergonomics) — that's a stronger, more specific answer than picking one methodology for the whole warehouse, which is what candidates who haven't actually built one of these tend to do.

### Q4 — What is a late-arriving dimension, and how does the inferred-member pattern fix it?
**Answer:** A fact event references a dimension entity (a customer, product) that hasn't been loaded into the dimension table yet, typically because fact and dimension pipelines run at different latencies. The inferred-member pattern inserts a placeholder dimension row immediately — natural key and a new surrogate key populated, other attributes null/unknown — so the fact table's foreign key is never left dangling. When the real dimension data arrives, the placeholder is updated in place as a Type 1 correction, since the row never represented real historical state to begin with.
**Follow-up trap:** *"What if the fact table has already been queried with the placeholder's unknown attributes before the real data arrives?"* — that's an accepted, temporary limitation of the pattern: a report run in that window shows "unknown" for that dimension's attributes, which is preferable to either dropping the fact row (silent data loss) or leaving a broken foreign key (breaks every downstream join); the tradeoff is explicit incompleteness now versus data loss or breakage.

### Q5 — Why is deliberate denormalization justified in gold but dangerous in an OLTP schema?
**Answer:** Denormalization trades update cost (changing a value that's repeated across many rows) for read/query simplicity (fewer joins). In an OLTP system, application code point-updates individual rows constantly, so update anomalies from denormalization are a real, frequent correctness risk (see `T17-normalization`). Gold marts are read-heavy and rebuilt/merged on a schedule rather than point-updated by application code, so the update-cost side of the tradeoff is a non-issue in practice, while the read-simplicity benefit (a BI tool or analyst not needing to write a dozen joins) is a real, constant win.
**Follow-up trap:** *"So denormalization is always fine in gold?"* — not unconditionally: if a gold mart is denormalized so aggressively that a single attribute change (a customer's segment) requires rewriting it across millions of flattened rows on every update, that's a real operational cost even in a rebuild/merge-based pipeline, especially at high update frequency — the justification holds for read-mostly, infrequently-changing attributes, less so for a rapidly, frequently mutating one.

### Q6 — A gold fact table's row count unexpectedly triples after a routine dimension refresh. Diagnose it.
**Testing:** the specific fan-out failure mode named in this module.
**Answer:** The gold join almost certainly matches a Type 2 dimension on the natural key with no as-of/effective-date filter, so a fact row is joining against every historical version of that dimension entity instead of the one version correct at the time the fact occurred — three historical versions of a customer's address produce three times the expected join rows. Fix: join with an explicit effective-date range filter (`fact.order_date BETWEEN dim.valid_from AND dim.valid_to`), or resolve the correct surrogate key in silver before the gold join happens at all, which is the safer pattern since it removes the as-of logic from every gold query that touches that dimension.
**Follow-up trap:** *"Why would you resolve it in silver rather than just always remembering the as-of filter in every gold query?"* — because "remembering" is exactly the kind of institutional-knowledge dependency that caused the bug in the first place; resolving the surrogate key once, correctly, at the silver-to-gold boundary means every downstream gold query is structurally safe by construction rather than safe only if every author remembers the filter.

### Q7 — Why must surrogate key generation happen after deduplication, not in bronze?
**Answer:** Bronze can contain multiple raw representations of what turns out to be the same logical entity (duplicate CDC events, or two source systems' records for the same customer before conforming resolves them to one identity). Generating a surrogate key before that resolution happens produces distinct surrogate keys for what should be one entity, and once fact tables reference those surrogate keys, the mistake propagates downstream and is expensive to unwind — every dependent fact row's foreign key needs remapping.
**Follow-up trap:** *"What if a source system's own primary key is already guaranteed unique — can you skip surrogate keys and use it directly in gold?"* — you can for a single-source, single-identity dimension with no Type 2 history need, but the moment you need to conform across multiple source systems (a customer existing in both a CRM and a billing system with different native keys) or need Type 2 SCD (a natural key can't represent multiple valid versions over time, per `T17-dimensional-modeling`), a surrogate key layer becomes structurally necessary, not optional.

### Q8 — Design the bronze/silver/gold layers for a company that just acquired a competitor and needs to merge two separate customer databases into one warehouse.
**Testing:** applying conforming, key-mapping, and grain decisions to a realistic scenario.
**Answer:** Bronze lands both companies' raw customer tables unmodified, side by side, with a `_source_system` tag. Silver builds a conformed `dim_customer`-ready entity: a key-mapping/entity-resolution step (matching on email, phone, or a fuzzy-match process where no shared identifier exists) resolves records from both source systems to one natural key, with SCD Type 2 applied so historical facts from before the merger still join correctly to the pre-merger version of each conformed customer. Gold's fact tables reference the conformed surrogate key uniformly, so a revenue mart built after the merger doesn't need to know which legacy system a given historical order came from.
**Follow-up trap:** *"What happens to facts from before the merger that reference the old, now-superseded natural keys?"* — they don't get rewritten; the silver conforming/mapping table (natural key from each legacy system → the new conformed natural key → surrogate key history) is the permanent translation layer, and old fact rows keep referencing whatever surrogate key was correct in their own source system's timeline, resolved through that mapping at query/gold-build time rather than by mutating historical fact data.

### Q9 — What's the argument for building Kimball marts even on top of a Data Vault integration layer, rather than letting analysts query the Vault directly?
**Answer:** A Data Vault's hub/link/satellite structure is optimized for auditability, historization, and ease of adding new sources — not for query ergonomics. Querying it directly for BI requires an analyst to understand and join across potentially many satellite tables per business entity, reconstructing what a dimension "currently looks like" or "looked like as of a date" by hand on every query. A Kimball mart built on top does that reconstruction once, centrally, and exposes a denormalized, BI-tool-friendly star schema — the Vault protects the integration layer's flexibility, the mart protects the analyst's sanity.
**Follow-up trap:** *"Doesn't that mean you're duplicating data (once in the Vault, again in the mart)?"* — yes, deliberately: the mart is a derived, rebuildable projection of the Vault, not a second source of truth. The Vault remains authoritative; the mart can be dropped and rebuilt from it at any time, which is the same "can always rebuild downstream from the more raw/complete upstream layer" principle that justifies bronze's immutability.

### Q10 — Your gold layer has been queried directly for months to answer ad hoc questions, bypassing the usual dbt-managed marts. A stakeholder asks why two "revenue" numbers from different dashboards disagree. Diagnose and fix.
**Answer:** This is the conformed-definition failure mode: once ad hoc queries against gold (or worse, against silver/bronze directly) start re-deriving "revenue" with slightly different filters or join logic instead of reading a single governed gold fact/metric, disagreement is inevitable — there's no single place "revenue" is defined once, everyone who wrote their own query has effectively created their own private definition. Fix: consolidate revenue's definition into one gold table or a semantic-layer metric (see `T17-dimensional-modeling`'s discussion of semantic layers), and treat any dashboard bypassing it as itself the bug, not the differing numbers.
**Follow-up trap:** *"What's stopping this from happening again after you fix it once?"* — governance, not just a one-time fix: restrict direct query access to bronze/silver for anything feeding an externally-visible number, and route ad hoc analysis through the semantic layer or governed gold tables so "revenue" always means one thing regardless of who's asking the question.

---

## Red flags that fail you

- Describing bronze/silver/gold without being able to say precisely what transformation is or isn't allowed in each.
- Applying business logic or filtering in bronze "because it seemed harmless."
- Picking Kimball, Inmon, or Data Vault as a single answer for an entire warehouse with no discussion of layering them.
- Not knowing what a late-arriving dimension is or how the inferred-member pattern handles it.
- Joining a fact table against a Type 2 dimension with no as-of filter and not recognizing the fan-out risk.
- Generating surrogate keys before deduplication/conforming.
- Claiming denormalization is unconditionally safe in gold with no caveat about update frequency.

---

## Cheat card

```
BRONZE   raw, IMMUTABLE, append-only, near-source shape, NO business logic,
         NO joins, NO dedup. CDC update = new row with its own timestamp.
         Only layer that can reconstruct history if silver/gold has a bug.

SILVER   clean, type-enforce, DEDUPE, CONFORM entities across sources,
         assign SURROGATE KEYS (after dedup, not before), apply SCD Type 2,
         enforce referential integrity. Still near source grain.

GOLD     GRAIN declared explicitly first. Dimensional model applied
         (star schema, T17-dimensional-modeling). Aggregation + business
         rules live HERE ONLY ("revenue" defined exactly once). Deliberate
         denormalization justified because read-heavy, rebuilt on schedule.

RULE     each layer's contract is trusted by the layer below it. Gold
         reading bronze directly (skipping silver) = two marts disagreeing
         on "active customer."

KIMBALL     star schemas, bottom-up, fast time-to-value, BI-ready directly.
INMON       normalized EDW first, marts derived downstream. Governance-heavy,
            slow to first value, needs a mart layer on top.
DATA VAULT  hub/link/satellite. Best for frequent new-source addition +
            audit/compliance. Needs a Kimball mart layer on top too.
HONEST ANSWER: hybrid by layer — Vault/Inmon for the governed integration
            core, Kimball for the consumption-facing marts. Not one
            methodology for the whole warehouse.

LATE-ARRIVING DIM   fact references a not-yet-loaded dimension entity.
            Fix: inferred-member placeholder row (natural+surrogate key,
            null attrs), update in place (Type 1) when real data lands.
            Prevents dropped facts AND broken foreign keys.

FAN-OUT BUG   join against Type 2 dim on natural key with NO as-of filter
            -> fact row matches every historical version, inflates counts.
            Fix: as-of/effective-date filter, or resolve surrogate key
            in silver before the gold join.

SURROGATE KEY TIMING   assign at silver-to-gold boundary, AFTER dedup/
            conform — assigning in bronze produces duplicate-entity keys
            that propagate into every downstream fact FK.

CROSS-REF   grain + SCD mechanics -> T17-dimensional-modeling
            OLTP normalization -> T17-normalization
            table formats (Delta/Iceberg) -> T18-lakehouse
            what triggers a rebuild -> T18-scheduling-triggering
```

## Sources

- [Kimball vs Inmon vs Data Vault 2.0: Data Warehouse Architecture Guide — TalkingSchema](https://talkingschema.ai/blog/compare-inmon-kimball-datavault) — accessed 2026-08-01
- [Difference Between Data Vault, Inmon and Kimball Approach — Scalefree](https://www.scalefree.com/knowledge/solutions/difference-between-data-vault-inmon-and-kimball-approach/) — accessed 2026-08-01
- [Enterprise Data Modelling Methodologies: A Comparative Analysis of Inmon, Kimball, and Data Vault (arXiv 2606.29355)](https://arxiv.org/pdf/2606.29355) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
