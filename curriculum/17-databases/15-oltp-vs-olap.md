# OLTP vs OLAP vs HTAP: Row vs Column, Latency Budgets, Why You Can't Have Both

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2h · **Prereqs:** `T17-storage-engines` · **Updated:** 2026-07-26
> **Module id:** `T17-oltp-vs-olap` · **Tags:** fundamentals, critical

## The 30-second version

OLTP and OLAP optimize for opposite access patterns and that opposition is physical, not a tooling limitation: OLTP touches a few full rows at a time (fetch this order, update that balance) so row-oriented storage — all of a row's columns physically adjacent — minimizes the I/O for that access pattern, while OLAP touches a few columns across millions of rows (sum this column, group by that one) so columnar storage — all of one column's values physically adjacent — minimizes I/O for that pattern by letting the engine skip every column the query doesn't need and compress each column far better since it holds one data type with low entropy. Columnar engines pair this with vectorised execution — operating on batches of thousands of values per CPU instruction (SIMD) instead of row-at-a-time interpretation — which is where most of the 10-100x OLAP query speedup actually comes from, not just the I/O savings. Compression ratios of 5-20x are routine on columnar data (dictionary encoding, run-length encoding, delta encoding all work far better within a single column's homogeneous values than across a heterogeneous row). HTAP systems (TiDB, SingleStore, Postgres+columnar extensions) promise both from one system, and the honest limit is that the two workloads compete for the same CPU, memory, and I/O on shared hardware — HTAP works by physically separating engines internally (TiDB replicates from a row store to a column store) or by architectural compromises that cap one side's throughput (Snowflake's Unistore hybrid tables sustain roughly 1,000 ops/sec, far below a dedicated OLTP engine). The decision of which store a workload belongs in comes down to one question asked first: does a single request touch one entity or millions of them?

## Why this gets asked

Because "just use Postgres for everything" and "just use Snowflake for everything" are both wrong in ways that only show up under load, and the interviewer wants to know if you can predict *where* a design will break before it does. They've watched an analytics query with a dozen aggregate functions run against a row-store OLTP replica and take down the primary's I/O budget, or watched a team adopt an HTAP database expecting it to remove the tradeoff entirely and get surprised when the analytical side's resource contention degraded their transactional p99 during the nightly batch job. The follow-up is whether you understand this as a physical resource-contention problem, not a marketing feature gap that a big-enough box fixes.

---

## Lineage: past → present → future

**What came before.** For decades there was effectively one design: a single relational database, row-oriented, served both the application's transactional traffic and its reporting queries directly, because data volumes and reporting demands were modest enough that this worked. As data volumes grew through the 1990s-2000s, running heavy analytical queries against the same row store that served live transactions caused a specific, well-documented pain: a multi-minute aggregate scan would hold locks and consume buffer pool/cache space that transactional queries needed, degrading OLTP latency unpredictably whenever a report ran — the classic "the nightly report is slow *and* it's slowing down checkout" incident. The industry's answer was ETL-and-separate-warehouse: nightly batch jobs extracted data out of the OLTP system into a dedicated data warehouse (Teradata, Oracle Exadata, and later columnar-native systems), physically isolating the two workloads onto separate hardware so neither could starve the other, at the cost of data in the warehouse being hours or a full day stale by the time anyone queried it.

**Where it stands now.** The current consensus splits cleanly by data freshness requirement. For anything tolerating hours of staleness, ETL/ELT into a dedicated columnar warehouse (Snowflake, BigQuery, Redshift, ClickHouse — see `T17-clickhouse`) remains the dominant, well-understood architecture, and columnar-plus-vectorised execution is now table stakes for that category, not a differentiator. The live disagreement is over the middle ground: workloads that need analytical queries over data that's only seconds to minutes old (real-time dashboards over live operational data, fraud-scoring queries needing current-second transaction context). Change Data Capture pipelines (Debezium reading a database's WAL/binlog and streaming changes into a columnar store within seconds) are now a mature, widely-deployed answer to that middle ground, and many teams consider CDC-into-a-columnar-store the pragmatic default over adopting a true HTAP database, because it keeps the operational and analytical engines physically separate (preserving the isolation that solved the original OLTP-starves-under-reporting-load problem) while cutting staleness from a day to seconds. True HTAP systems (TiDB with TiFlash, SingleStore's unified engine, Postgres with a columnar extension bolted on) are real, in production, and growing, but the honest assessment is that they manage the resource-contention problem rather than eliminate it — TiDB does this by literally running two storage engines (TiKV row store, TiFlash column store) and replicating between them, which is architecturally closer to "CDC inside one product" than to "one engine serving both perfectly."

**Where it's heading.** Cloud-native separation of storage and compute (Snowflake's original architecture, and now widely copied) is the clearest real trend, since it lets analytical compute scale independently of the data's storage tier and of any OLTP compute entirely — this is mature and shipping broadly, not speculative. More at the frontier: **lakehouse architectures** (Delta Lake, Iceberg, Hudi table formats over object storage) are pushing toward "one copy of data, multiple engines query it directly," which if it matures fully would reduce (not eliminate) the ETL-duplication cost between OLTP-adjacent and OLAP systems — but query latency and transactional guarantees on lakehouse table formats are still materially weaker than a purpose-built OLTP engine's, and treating a lakehouse as an OLTP replacement today would be a real mistake, not a forward-looking one. Confidence: cloud-native storage/compute separation, high; lakehouse formats fully closing the gap with dedicated OLTP engines, low/speculative — flag that distinction explicitly if asked where this is heading.

---

## Mental model

```
ROW STORAGE (OLTP)                        COLUMNAR STORAGE (OLAP)

Physical layout on disk:                  Physical layout on disk:
  Row 1: [id][name][age][city][salary]      Column id:     [1][2][3][4][5]...
  Row 2: [id][name][age][city][salary]      Column name:   [Al][Bo][Cy][Di]...
  Row 3: [id][name][age][city][salary]      Column age:    [34][51][22][45]...
  Row 4: [id][name][age][city][salary]      Column city:   [NY][SF][NY][LA]...
                                             Column salary: [90k][110k][75k]...

Query: "get order #4821, all fields"       Query: "avg(salary) WHERE city='NY'"

Row store: ONE seek, read one contiguous   Row store: must read EVERY row fully
  block containing the whole row.           (all columns) just to touch city+salary
  Fast: single I/O gets everything needed.   -- wastes I/O on name, age, id per row.

Column store: must touch EVERY column's    Column store: read ONLY the city and
  file/segment to reassemble one row --      salary columns, entirely skip name/age/id.
  wasteful for a single-row fetch.           Read far less data; each column is one
                                              data type -> compresses 5-20x; SIMD
                                              vectorised ops process 1000s of values
                                              per instruction instead of row-at-a-time.
```

**The physical law underneath both:** I/O bandwidth and cache locality are finite, and the layout that's optimal for "narrow set of rows, all columns" is the layout that's worst for "narrow set of columns, all rows" — this is not a software limitation either engine family could just fix, it's what physically adjacent-on-disk means for two opposite access patterns.

---

## How it actually works

### Row vs columnar storage, mechanically

A row store (Postgres heap, InnoDB clustered index) packs an entire row's bytes together in one page. Fetching `SELECT * FROM orders WHERE id = 4821` costs roughly one page read (the row and its neighbors are already together) — the ideal case for OLTP's point-lookup-and-update pattern.

A columnar store (Parquet files, ClickHouse's MergeTree, Redshift, BigQuery's native storage) writes each column's values into their own contiguous run, often further divided into row groups/chunks with per-chunk statistics (min/max, null counts) that let the engine skip entire chunks without reading them (**predicate pushdown / chunk skipping**). `SELECT avg(salary) FROM employees WHERE city = 'NY'` in a columnar store reads only the `city` and `salary` columns' bytes — if the table has 50 columns, that's roughly a 1/25th slice of the table's total bytes before compression is even considered, and the query never touches `name`, `age`, or any other column at all.

### Compression: why columnar compresses 5-20x better

Compression algorithms exploit redundancy, and a single column is far more redundant than a row:

- **Dictionary encoding** — a `country` column with 200 distinct values across 100M rows stores each value once in a dictionary and replaces the column's data with small integer codes; this alone can be a 10x+ reduction for low-cardinality string columns, and it doesn't work nearly as well across a whole heterogeneous row.
- **Run-length encoding (RLE)** — a column sorted or clustered by a repeating value (`status` mostly "completed" for long stretches) stores `(value, run-length)` pairs instead of every repeated value.
- **Delta encoding** — a monotonically increasing column (timestamps, auto-increment IDs) stores the difference from the previous value, which is small and compresses extremely well, versus storing full absolute values.
- Applied together on real analytical datasets, **5-20x compression is routine**, sometimes higher on low-cardinality columns; this directly cuts I/O (the dominant cost for large scans) proportionally.

### Vectorised execution

Traditional row-at-a-time (Volcano/iterator model) query execution calls a `next()` function per row, with per-row branching and function-call overhead that dominates CPU time for simple operations at scale. **Vectorised execution** processes a batch (e.g., 1,024 or 4,096 values) per operator call, operating on tight, type-specialized loops that the CPU can auto-vectorize into SIMD instructions (processing multiple values per instruction cycle) and that keep data in L1/L2 cache far more effectively than row-at-a-time interpretation. This is where a large fraction of OLAP engines' 10-100x speedup over naive row-at-a-time scanning comes from — it's not just "less I/O because of columnar layout," it's also "far fewer CPU cycles per value processed," and the two effects compound.

### Latency budgets and access patterns

| | OLTP | OLAP |
|---|---|---|
| Typical single-query latency budget | Single-digit to low tens of ms (p99 often <50-100ms) | Seconds to tens of seconds acceptable; some ad hoc queries minutes |
| Rows touched per query | 1 to a few hundred | Thousands to billions |
| Columns touched per query | Most/all of a row | A handful out of dozens/hundreds |
| Concurrency | Thousands of small concurrent transactions | Fewer, much larger queries; concurrency measured in tens, not thousands |
| Write pattern | Frequent, small, transactional (ACID) | Bulk load / append-mostly, often batch or streaming ingest |
| Index strategy | B-tree point/range lookups (see `05-index-design.md`) | Column pruning + chunk/partition skipping, less reliance on traditional indexes |

The latency-budget mismatch is the practical reason you cannot serve both well from the same physical resources under load: an OLAP query holding a CPU core busy for 10 seconds doing a vectorised scan is *by design* consuming resources at a rate and duration that would blow an OLTP p99 budget by 100-1000x if a transactional query got stuck behind it.

### HTAP and its honest limits

HTAP (Hybrid Transactional/Analytical Processing) systems try to serve both from one product. The two dominant architectural approaches:

1. **Dual-engine internal replication** (TiDB: TiKV row store + TiFlash columnar store, replicated via Raft in near-real-time). This genuinely isolates the physical resource contention — TiFlash can be scaled and even placed on separate nodes from TiKV — but it is architecturally closer to "CDC replication packaged inside one product" than to a single engine magically serving both patterns from the same bytes. The benefit over external CDC-to-a-warehouse is operational simplicity (one system, one deployment) and lower replication lag (subsecond to low-seconds, versus typical CDC pipeline lag of seconds to tens of seconds); the cost is that you're still running two storage engines under the hood, with the operational complexity that implies.
2. **Unified single-engine hybrid storage** (SingleStore: an in-memory rowstore plus a columnstore in one engine; Snowflake's Unistore hybrid tables). This avoids replication lag entirely by keeping one copy of data, but pays for it in hard ceilings: **Snowflake's Unistore hybrid tables are documented at roughly 1,000 operations/second with active data around 500 GB** — workable for many applications, but far below what a dedicated OLTP engine sustains (tens of thousands to more ops/sec is routine for Postgres/MySQL on modest hardware), and that ceiling is a direct, honest consequence of the same storage layer having to satisfy both access patterns' constraints simultaneously.

The fundamental, physically-grounded limitation stated plainly: **the same CPU, memory, and I/O bandwidth serve both workloads on one machine (or cluster), and a zero-sum resource allocation problem doesn't disappear because a vendor's marketing page says "HTAP."** A heavy analytical query and a burst of transactional writes are still competing for the same finite resources even inside a genuinely well-engineered HTAP system; the engineering achievement is managing and bounding that contention (via separate engines, resource governors, or workload isolation), not eliminating it.

### How to decide which store a workload belongs in

Ask, in order:
1. **Does a single request touch one entity (a row, a small related set) or millions of rows?** One entity → OLTP shape. Millions → OLAP shape. This single question resolves ~80% of cases immediately.
2. **What's the acceptable staleness for the analytical side?** Sub-second → look hard at whether you actually need it real-time (usually you don't, and the honest cost/complexity of true HTAP or streaming isn't worth it) versus seconds-to-minutes (CDC into a columnar store is mature and sufficient) versus hours (batch ETL is simpler and cheaper, still the right default for most reporting).
3. **What's the write pattern?** High-frequency small transactional writes needing ACID guarantees on a single/few rows → OLTP engine, full stop. Bulk/streaming append with rare updates → columnar/OLAP-native ingest path.
4. **Is the actual pain "reporting is slow" or "reporting slows down the transactional system"?** If it's the latter specifically, even a modest CDC replica or read-replica-for-reporting fixes the resource-contention problem without needing a columnar engine at all — don't reach for OLAP tooling to solve an isolation problem that a read replica already solves.

---

## Build it from scratch

A minimal illustration of row-store vs columnar-store I/O cost, to make the tradeoff concrete rather than assert it:

```python
# untested sketch — illustrates the physical I/O difference, not a real engine
import time, random

N = 500_000
columns = {
    "id": list(range(N)),
    "name": [f"user_{i}" for i in range(N)],
    "age": [random.randint(18, 80) for _ in range(N)],
    "city": [random.choice(["NY", "SF", "LA", "CHI"]) for _ in range(N)],
    "salary": [random.randint(40_000, 200_000) for _ in range(N)],
}

# ROW STORE simulation: rows stored as tuples, must deserialize every column
row_store = list(zip(*columns.values()))

def row_store_avg_salary_where_city(city):
    total, count = 0, 0
    for row in row_store:                    # touches ALL 5 fields per row
        _id, name, age, c, salary = row       # deserialize every column even though
        if c == city:                         # only city and salary are needed
            total += salary
            count += 1
    return total / count if count else 0

# COLUMNAR STORE simulation: each column is its own contiguous array
def columnar_avg_salary_where_city(city):
    total, count = 0, 0
    city_col, salary_col = columns["city"], columns["salary"]
    for c, salary in zip(city_col, salary_col):   # touches ONLY 2 of 5 columns
        if c == city:
            total += salary
            count += 1
    return total / count if count else 0

t0 = time.perf_counter(); row_store_avg_salary_where_city("NY"); t_row = time.perf_counter() - t0
t0 = time.perf_counter(); columnar_avg_salary_where_city("NY"); t_col = time.perf_counter() - t0
print(f"row-store-shaped: {t_row:.4f}s   columnar-shaped: {t_col:.4f}s")
# Even in pure Python (no real vectorisation), touching 2/5 columns instead of
# deserializing all 5 shows a measurable gap — a real columnar engine widens
# this further with compression and SIMD vectorised batch processing.
```

This toy makes the "columns not touched are never read" idea concrete even without real compression or SIMD. Full version comparing an actual row-oriented SQLite table against a Parquet/DuckDB columnar equivalent on the same dataset, with real I/O and compression measurements: **`(lab pending)`**.

---

## How it's done in production

**OLTP-to-OLAP pipelines.** Change Data Capture (Debezium reading Postgres's logical replication stream or MySQL's binlog) streaming into Kafka, landing in a columnar store (ClickHouse, BigQuery, Snowflake via a loader) is the standard mature pattern for near-real-time analytics without touching the OLTP system's resources for analytical queries at all. Typical end-to-end lag: seconds to low tens of seconds under normal load.

**Columnar engines in practice.** ClickHouse (see `T17-clickhouse`) and DuckDB (increasingly popular for embedded/single-node analytics) both implement columnar storage plus vectorised execution as their core design, not an add-on. Snowflake and BigQuery add cloud-native separated storage/compute on top of the same columnar-plus-vectorised foundation, letting analytical compute scale independently and on-demand.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Nightly report degrades checkout/transactional p99 | Analytical query running directly against the OLTP primary or a shared replica, consuming buffer pool/cache and I/O the transactional workload needs | Route analytical queries to a dedicated read replica, or better, a CDC-fed columnar store entirely separate from OLTP compute |
| Columnar warehouse query scans far more data than expected, costs spike (cloud pay-per-scan pricing) | Missing partition/chunk pruning — query doesn't filter on the physically-clustered/partitioned column, forcing a full-table scan of all chunks | Partition/cluster the table on the column most queries filter by; verify predicate pushdown is actually eliminating chunks via the query engine's explain plan |
| HTAP system's transactional latency degrades during analytical batch windows | Resource contention between the row-store and column-store engines (or unified engine) sharing CPU/memory/I/O | Check whether the HTAP product supports physical node separation between the transactional and analytical paths (e.g., TiFlash on separate nodes from TiKV); if using a unified single-engine HTAP product, verify its documented throughput ceiling against your actual OLTP requirement before adopting it |
| Row store degrades noticeably as an analytical workload (large aggregate scans) grows | Fundamental mismatch — row store forces reading every column of every row even when only 2 of 50 are needed | This isn't a tuning problem; the workload has outgrown the storage layout and needs a columnar engine or CDC pipeline, not more indexes or bigger hardware alone |
| CDC pipeline lag grows unboundedly under load | Downstream columnar store's ingest can't keep up with the source's write rate, or a consumer (Kafka connector) falls behind | Scale ingest parallelism on the columnar side; batch/buffer writes more aggressively; monitor consumer lag as a first-class metric, same discipline as WAL replication-slot lag (see `02-wal-recovery.md`) |

---

## Tradeoffs & when NOT to use it

- **Do not run heavy analytical queries directly against your OLTP primary "just this once."** This is one of the most common, entirely predictable production incidents in the catalogue — a single ad hoc report can starve transactional latency for the query's full duration.
- **Do not adopt a true HTAP database expecting it to remove the OLTP-vs-OLAP resource tradeoff entirely.** It manages contention (via dual engines or a documented throughput ceiling), it does not eliminate the underlying physical zero-sum resource problem — verify the specific product's documented limits (e.g., Unistore's ~1,000 ops/sec ceiling) against your actual OLTP requirement before committing.
- **Do not use a columnar/OLAP engine for a workload dominated by single-row point lookups and frequent small updates.** Columnar storage's cost of reassembling a full row from many separate column files, and its poor fit for high-frequency row-level updates (usually requiring append-and-compact patterns rather than in-place update), make it a poor OLTP substitute.
- **Do not reach for real-time streaming/HTAP to solve a staleness requirement nobody actually asked for.** Confirm the business genuinely needs sub-second freshness before paying the architectural complexity cost; most "real-time dashboard" requirements are satisfied by seconds-to-minutes CDC lag, which is dramatically simpler to build and operate.
- **A read replica is often the right, much simpler fix** when the actual complaint is "reporting slows down the transactional system," rather than reaching for a dedicated OLAP engine or HTAP product when the real requirement is just workload isolation, not columnar performance characteristics.

---

## Interview questions

### Q1 — Why does row storage suit OLTP and columnar storage suit OLAP?
**Testing:** baseline.
**Answer:** OLTP touches a few full rows (fetch/update one entity) — row storage keeps all of a row's fields physically adjacent, so one I/O gets everything needed. OLAP touches a few columns across millions of rows (aggregate a couple of fields) — columnar storage keeps each column's values adjacent, so the engine reads and skips exactly the columns it needs, and each column compresses far better since it holds one data type.
**Follow-up trap:** *"Could you just add more indexes to a row store to fix OLAP performance?"* — indexes help find specific rows faster, but an aggregate over millions of rows still ends up reading full rows (all columns) via those indexes unless it's a covering index for exactly that query; it doesn't fix the fundamental "reading unneeded columns" cost the way columnar layout does, and building enough covering indexes to approximate columnar behavior across every possible aggregate query is impractical.

### Q2 — Where does most of a columnar engine's speedup over a row store actually come from — I/O savings or something else?
**Answer:** Both, and they compound. I/O savings come from reading only needed columns plus 5-20x compression from within-column redundancy. But a large fraction of the 10-100x speedup also comes from vectorised execution — processing batches of values per operator call instead of row-at-a-time, which lets the CPU use SIMD instructions and keeps data in cache far better than the traditional iterator/Volcano model's per-row function-call overhead.
**Follow-up trap:** *"So if you just converted the storage to columnar but kept row-at-a-time execution, would you get the full speedup?"* — no, you'd get the I/O and compression benefit but miss most of the CPU-efficiency benefit; several early columnar systems learned this the hard way and vectorised execution had to be built as a first-class part of the engine, not bolted onto an existing row-at-a-time executor.

### Q3 — Explain dictionary encoding, run-length encoding, and delta encoding, and why each works better on columns than rows.
**Answer:** Dictionary encoding replaces repeated values (a `country` column with 200 distinct values) with small integer codes referencing a shared dictionary. Run-length encoding stores `(value, count)` pairs for consecutive repeats (works well on sorted/clustered low-cardinality columns). Delta encoding stores the difference from the previous value for monotonic columns (timestamps, IDs). All three exploit redundancy that exists *within* a single column's homogeneous values — a row mixes an ID, a name, an age, and a salary, which have nothing in common to compress against each other.
**Follow-up trap:** *"Does compression ever hurt query performance?"* — decompression is CPU cost paid at query time, and for some codecs (heavier general-purpose compression like Zstd/Gzip vs light schemes like RLE/dictionary) that cost can be non-trivial; most OLAP engines choose lightweight, fast-to-decompress encodings by default and use heavier compression only for cold/rarely-scanned data, precisely to avoid trading I/O savings for CPU cost at read time.

### Q4 — What's the honest limitation of HTAP systems, stated precisely?
**Answer:** The same CPU, memory, and I/O bandwidth ultimately serve both workloads, whether via two internally-replicated engines (TiDB) or one unified engine (SingleStore, Snowflake Unistore) — this is a zero-sum resource allocation problem that architecture can manage and bound but not eliminate. Concretely, Snowflake's Unistore hybrid tables are documented at roughly 1,000 ops/sec with ~500GB active data, far below a dedicated OLTP engine's throughput, which is a direct, honest consequence of one storage layer satisfying both access patterns' constraints.
**Follow-up trap:** *"Doesn't TiDB solve this by having two separate engines?"* — it manages the contention better by physically separating TiFlash (columnar) from TiKV (row store), which can even run on separate nodes, but this makes TiDB architecturally closer to "CDC replication packaged inside one product" than to a single engine truly serving both patterns without any resource tradeoff; you're still running two storage engines and paying replication lag and operational complexity for it.

### Q5 — When would you choose CDC-into-a-columnar-store over adopting an HTAP database?
**Answer:** When you want workload isolation between OLTP and OLAP without adopting a new, more operationally complex database product — CDC (Debezium reading a WAL/binlog into Kafka, landing in ClickHouse/BigQuery/Snowflake) is mature, keeps the two engines fully separate (preserving the original isolation that solved OLTP-starves-under-reporting), and typically achieves seconds-to-tens-of-seconds freshness, which satisfies the large majority of "near real-time" business requirements without HTAP's added complexity.
**Follow-up trap:** *"What if the business genuinely needs sub-second consistency between the transactional and analytical views?"* — that's the case where true HTAP earns its complexity; but push back hard on whether "sub-second" is a real, validated requirement versus an assumed one — most stated real-time requirements, when questioned, turn out to tolerate seconds of staleness just fine, and building for a requirement nobody validated is a common, expensive mistake.

### Q6 — A nightly analytics report is degrading checkout latency. What's the fix, and why is reaching for a columnar engine not necessarily the first move?
**Answer:** First diagnose whether the actual problem is resource contention (the report is consuming I/O/cache the transactional workload needs) versus the report genuinely being too slow on its own terms. If it's contention, routing the report to a dedicated read replica is a simpler, faster fix than adopting a columnar engine, and directly solves the isolation problem. If the report itself is fundamentally slow because it's aggregating over millions of rows and touching a handful of columns out of dozens, that's when a columnar store (via CDC or batch ETL) becomes the right tool — but that's a different problem than the immediate incident, and conflating them leads to over-engineering a fix for an isolation problem.
**Follow-up trap:** *"What if the read replica itself starts falling behind (replication lag) under the report's load?"* — that's a sign the report's I/O demand is now large enough that even a dedicated replica's resources are contended, which is the actual signal that it's time to move to a purpose-built OLAP store rather than adding more replicas.

### Q7 — Derive, roughly, how much less data a columnar query reads compared to a row-store query, for a table with 50 columns where only 2 are needed.
**Answer:** Ignoring compression, a row-store scan reads all 50 columns' bytes per row (it has no choice — the row is one physical unit), while a columnar scan reads only the 2 needed columns' bytes — roughly a 25x reduction in bytes read before compression is even applied. With typical 5-20x columnar compression on top (compounding, not additive, since compression applies per-column to only the data actually read), the total I/O reduction for this shape of query is very large, easily 100x+ in a realistic case, which is why analytical queries against properly columnar-stored data routinely run in seconds against billions of rows where a row-store equivalent could take much longer.
**Follow-up trap:** *"Does this scale linearly as columns needed increase?"* — no — as the fraction of columns needed approaches the whole row, the columnar advantage shrinks toward parity (and columnar can even lose, due to the overhead of reassembling many separate column files into a row), which is exactly why "does the query need most/all columns of few rows, or few columns of most/all rows" is the right diagnostic question, not "is this an analytical-sounding query."

### Q8 — What's the latency-budget argument for why you cannot serve OLTP and OLAP well from the same physical resources under load, independent of storage layout?
**Answer:** OLTP's p99 budget is typically single-digit to low tens of milliseconds; a vectorised OLAP scan can legitimately hold a CPU core busy for seconds by design, because it's processing a proportionally enormous amount of data per query. If a transactional query gets scheduled behind (or contends for cache/I/O bandwidth with) that OLAP query even occasionally, its latency blows its budget by orders of magnitude — this is a scheduling/contention argument, independent of whether the underlying storage is row or columnar, and it's why even a well-isolated storage layout doesn't fully solve the problem without also isolating compute resources.
**Follow-up trap:** *"So does storage layout even matter if you isolate compute anyway?"* — yes, independently: even on fully separate hardware, a row store answering an OLAP-shaped query still reads unnecessary columns and gets none of the compression/vectorisation benefit, so isolation and storage-layout choice are two separate, both-necessary levers, not substitutes for each other.

### Q9 — Design the data architecture for a fraud-detection system that needs both live transactional writes and near-real-time aggregate risk scores per user.
**Testing:** applying the framework to a realistic system-design scenario.
**Answer:** OLTP engine (Postgres/MySQL) handles the transactional writes with full ACID guarantees. CDC (Debezium off the WAL) streams changes into a columnar/streaming aggregation layer (ClickHouse, or a stream processor like Flink maintaining rolling aggregates) that computes the per-user risk features with seconds-level freshness. The fraud-scoring service reads current-transaction context directly from the OLTP path (or a very fast in-memory cache) and reads the aggregate risk features from the CDC-fed analytical layer — deliberately not trying to compute million-row aggregates synchronously in the OLTP path itself.
**Follow-up trap:** *"What if fraud decisions need the aggregate feature to reflect the transaction happening right now, not seconds ago?"* — that's a genuine sub-second-freshness requirement, and it pushes toward computing that specific feature in-line (in the OLTP transaction path itself, denormalized/maintained incrementally) rather than trying to make the whole analytical pipeline sub-second — isolate the one feature that truly needs zero staleness rather than making the entire architecture pay for real-time freshness everywhere.

### Q10 — Why did the classic ETL-into-a-separate-warehouse pattern emerge, and what specific pain did it solve that a single shared database couldn't?
**Answer:** Running heavy analytical queries directly against the same row store serving live transactions caused multi-minute scans to hold locks and consume buffer pool/cache space transactional queries needed, degrading OLTP latency unpredictably whenever a report ran. Physically separating the two workloads onto separate hardware (via nightly batch ETL into a dedicated warehouse) eliminated that resource contention entirely, at the acknowledged cost of the warehouse data being hours to a day stale.
**Follow-up trap:** *"Isn't that staleness a dealbreaker today?"* — for many use cases yes, which is exactly why CDC-based near-real-time pipelines displaced pure nightly-batch ETL as the default for anything needing fresher data — but nightly batch ETL is still the right, simplest choice for genuinely batch-oriented reporting (financial close processes, daily executive dashboards) where the staleness was never actually a problem, and defaulting to real-time infrastructure for a batch-shaped requirement is over-engineering.

### Q11 — What specifically does "chunk skipping" or "predicate pushdown" mean in a columnar engine, and why does it matter for cost as much as speed?
**Answer:** Columnar files are divided into row groups/chunks, each with stored statistics (min/max, sometimes null counts or bloom filters) for its columns. A query's WHERE clause can be checked against a chunk's stats before reading any of the chunk's actual data — if the predicate can't possibly match anything in that chunk's value range, the whole chunk is skipped, unread. This matters for speed (less I/O) and, in cloud pay-per-scan pricing models (BigQuery, Snowflake, Athena), directly for cost, since you're billed for bytes scanned — a query missing effective chunk skipping can cost 10-100x more than the same query well-partitioned.
**Follow-up trap:** *"What breaks chunk skipping even when the table is technically partitioned?"* — filtering on a column that isn't the physical partition/clustering key, or applying a function to the filtered column (`WHERE DATE(created_at) = X` instead of a sargable range predicate) that prevents the engine from comparing it against chunk statistics — this is directly analogous to the expression-index problem in `05-index-design.md`: the predicate must be in a form the engine's pruning logic can actually evaluate against stored statistics.

### Q12 — A team wants to add a columnar read-replica specifically to speed up a handful of dashboard queries, but is worried about consistency between the OLTP source and the columnar copy. How do you reason about this?
**Answer:** This is precisely the CDC replication-lag tradeoff: the columnar copy will always be at least slightly stale (seconds to tens of seconds is typical), and the right question is whether the dashboard's actual business use tolerates that lag — almost all dashboards do. Treat consistency here the same way you'd treat a read replica's replication lag: monitor it, expose it if relevant to end users ("data as of HH:MM"), and don't try to force strong consistency onto a system that exists specifically to be a separate, isolated copy for a workload that doesn't need transactional guarantees.
**Follow-up trap:** *"What if one specific number on the dashboard (e.g., 'account balance right now') genuinely needs to be live and consistent?"* — serve that one field directly from the OLTP system (or a tightly-consistent cache) rather than the CDC-fed columnar layer, and compute the rest of the dashboard's aggregate/historical numbers from the columnar copy — mixing sourcing per-field based on actual freshness need is normal and often the right answer, not an architectural compromise to be embarrassed about.

---

## Red flags that fail you

- Saying "just use a bigger box" as the answer to OLTP-vs-OLAP resource contention.
- Claiming HTAP eliminates the tradeoff rather than manages/bounds it.
- Not knowing that vectorised execution, not just columnar storage, drives much of OLAP speedup.
- Recommending a columnar engine as an OLTP replacement for point-lookup/high-write workloads.
- Assuming CDC pipelines are instantaneous/synchronous rather than seconds-to-minutes lagged.
- Not being able to state the single diagnostic question (rows-touched vs columns-touched) that resolves most OLTP-vs-OLAP design decisions quickly.

---

## Cheat card

```
ROW STORE (OLTP)      all of a row's columns physically adjacent. 1 I/O gets a
                       whole entity. Ideal: fetch/update few full rows.
COLUMNAR (OLAP)        all of one column's values physically adjacent. Reads only
                       needed columns, skips rest entirely. Ideal: aggregate few
                       columns across millions of rows.

WHY COLUMNAR IS FAST   (1) I/O: reads only needed columns.
                       (2) compression 5-20x: dictionary/RLE/delta encoding exploit
                           within-column redundancy (works poorly across a row).
                       (3) vectorised execution: batches of 1000s of values/op,
                           SIMD-friendly, cache-friendly — NOT just an I/O story,
                           a large fraction of the 10-100x speedup is CPU efficiency.

LATENCY BUDGETS        OLTP: p99 single-digit-low-tens ms, 1-few hundred rows/query,
                         thousands of concurrent small txns.
                       OLAP: seconds-minutes acceptable, millions-billions rows/query,
                         tens of concurrent large queries.

CHUNK SKIPPING         columnar files split into row-group chunks w/ min/max stats;
                       predicate checked vs stats BEFORE reading chunk data. Breaks if
                       filter isn't on the partition/cluster key or wraps col in a
                       function (same problem as expression-index sargability).

HTAP HONEST LIMIT      same CPU/memory/I/O serves both -> zero-sum contention, managed
                       not eliminated. TiDB: TiKV(row)+TiFlash(col), Raft-replicated —
                       really "CDC inside one product." SingleStore/Snowflake Unistore:
                       unified engine, hard throughput ceiling (Unistore ~1000 ops/sec
                       @ ~500GB active data) vs dedicated OLTP engine's much higher rate.

DECISION QUESTION #1   single request touches ONE entity, or MILLIONS of rows?
                       -> resolves ~80% of OLTP-vs-OLAP placement decisions immediately.

PRAGMATIC DEFAULT      CDC (Debezium off WAL/binlog) -> Kafka -> columnar store
                       (ClickHouse/BigQuery/Snowflake). Seconds-to-tens-of-seconds
                       lag. Simpler + more mature than adopting full HTAP for most
                       "near real-time" requirements — validate the requirement first.

CLASSIC INCIDENT       heavy report query run against OLTP primary/shared replica
                       starves transactional p99 for the query's whole duration.
                       Fix: dedicated read replica or CDC pipeline, not "run it at 2am
                       and hope."
```

## Sources

- [Best HTAP Databases in 2026 — TiDB](https://www.pingcap.com/compare/htap-database/) — accessed 2026-07-26
- [Real-World HTAP: TiDB and SingleStore Architectures — PingCAP](https://www.pingcap.com/blog/real-world-htap-a-look-at-tidb-and-singlestore-and-their-architectures/) — accessed 2026-07-26
- [OLTP vs OLAP in 2026: How Real-Time Analytics Blurs the Line](https://bigdataboutique.com/blog/oltp-vs-olap-2026) — accessed 2026-07-26
- [HTAP Databases: A Survey (arXiv 2404.15670)](https://arxiv.org/pdf/2404.15670) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
