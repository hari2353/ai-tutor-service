# Backfills, Replays, Idempotent Reruns, Late Data, and Not Corrupting the Warehouse

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-backfill-replay` · **Tags:** pipelines, critical

## The 30-second version

A backfill or replay runs today's code and today's reference data against a historical date, and that's the entire risk in one sentence — the result can reflect the present instead of the past that actually happened. Backfills fill a genuine gap and carry a bounded downside; replays recompute history that's already in use downstream, so a bug in a replay actively corrupts data that was previously correct, which makes replay strictly riskier. The only thing that makes either survivable is idempotency at the range level — partition overwrite or merge-on-natural-key, plus a deterministic transform with no wall-clock dependency baked into the business logic — combined with bounded concurrency so a year of backfilled partitions doesn't saturate the warehouse. And sometimes the right answer is not to backfill at all: if the source data no longer exists, or the "bug" is actually a legitimate historical fact, a documented gap beats a confidently wrong rerun.

## Why this gets asked

Because a backfill is the single most dangerous routine operation in data engineering — it looks like "just rerun the job for some old dates," and it silently runs against **today's code and today's reference data**, not the historical versions that were true when the original run should have happened. The interviewer has watched a well-intentioned backfill apply this month's currency conversion rates to six months of historical revenue, or run an un-throttled backfill that saturated the warehouse and took down every other team's queries for an afternoon. They want to know if you treat a backfill as a controlled, audited operation with its own blast-radius planning, not a for-loop over dates.

---

## Lineage: past → present → future

**What came before.** Early ETL pipelines had no formal concept of "rerun this range safely" — recovering from a missed or broken run meant a manual, one-off script written under pressure during an incident, often by whoever was on call, with no consistent guarantee that the manual fix used the same logic as the original pipeline. The pain: manual backfills routinely diverged from the pipeline's actual transformation logic (a hand-written SQL patch that approximated but didn't exactly replicate what the real job would have done), and there was no audit trail proving what a rerun actually changed, which made post-incident reconciliation and compliance sign-off painful or impossible.

**Where it stands now.** The consensus is that backfills should run the *exact same code path* as normal execution, parameterized by date/partition, rather than a bespoke recovery script — this is precisely what Airflow's `catchup` and manual "clear and rerun" mechanics, and dbt's incremental model `--full-refresh` flag, are built around. The live disagreement is less about mechanics and more about **risk tolerance for using current code against historical data**: some teams treat this as an accepted, unavoidable tradeoff of continuously-evolving pipelines (the code changes, backfills of old data necessarily reflect new logic), while others maintain versioned/pinned transformation logic specifically so a backfill of Q1 data uses Q1's code, accepting the real maintenance cost of keeping old logic runnable. Most teams land somewhere in between: pin external reference data (exchange rates, tax tables) that's known to have genuinely changed over time, while accepting that bug fixes in transformation logic legitimately should apply retroactively when backfilling.

**Where it's heading.** **Durable execution engines** (Temporal, Dagster's asset-based rematerialization, Airflow's own backfill tooling maturing) are moving toward treating "rerun this range" as a first-class, structured operation with built-in concurrency limits and partition-level tracking, rather than a manually-scripted loop — a real, current trend. **Lakehouse table formats' time-travel** (Delta Lake, Iceberg) are making "what did this table look like before the backfill" a queryable, verifiable fact rather than something you have to reconstruct from backups, which directly strengthens the audit-trail story discussed below. More speculative: automated blast-radius estimation (a tool that, before you run a backfill, predicts how many downstream tables/dashboards it will touch and flags any that lack a rollback path) exists in early lineage-tooling form but isn't yet a mainstream, load-bearing safety mechanism.

---

## Mental model

```
  BACKFILL                                    REPLAY
  "fill in MISSING history"                   "RECOMPUTE existing history"
  ┌─────────────────────────┐                ┌─────────────────────────┐
  │ Jan  Feb  Mar  [ ]  May │                │ Jan  Feb  Mar  Apr  May │
  │                    ↑    │                │  ↑    ↑    ↑    ↑    ↑  │
  │              never ran  │                │  already ran, now      │
  │              — fill it  │                │  recomputing on top    │
  │                         │                │  of what's ALREADY     │
  │                         │                │  there — can corrupt   │
  │                         │                │  correct data if the   │
  │                         │                │  rerun isn't clean     │
  └─────────────────────────┘                └─────────────────────────┘
         LOWER RISK                                  HIGHER RISK
   (nothing to overwrite,                    (must not leave the range
    just add what's missing)                  in a half-old-half-new
                                               state — partition overwrite,
                                               not blind append)

  Both run against TODAY'S code and TODAY'S reference data — NOT the
  historical version that was true in January. This is the central risk
  of BOTH operations, not just one of them.
```

---

## How it actually works

### Why backfills are dangerous — the central risk stated precisely

A backfill (or replay) executes the pipeline's *current* code against a *historical* date/partition parameter. This means:

- **Code drift**: if the transformation logic has changed since the original period (a bug fix, a new business rule, a schema change), the backfilled data reflects *today's* logic, not what would have run at the time — which may be exactly what you want (retroactively applying a bug fix) or exactly what you don't want (retroactively applying a business-rule change that shouldn't apply to historical periods, like a new discount policy that took effect only from a specific date forward).
- **Reference data drift**: exchange rates, tax tables, product catalogs, and any other slowly-changing external reference data used in the transform may have different values today than they did during the historical period. A currency conversion backfill using today's exchange rate for a transaction from six months ago produces a plausible-looking but factually wrong historical revenue number — and because SCD Type 2 dimensions exist specifically to prevent this class of bug (`T17-dimensional-modeling`), a backfill that bypasses point-in-time-correct dimension lookups and just joins to "current" reference data is reintroducing the exact bug dimensional modeling was built to prevent.
- **This risk applies to both backfills and replays equally** — it is not specific to "new" history versus "recomputed" history, which is a common misconception; the danger is in using present-day code/data against a past period, regardless of whether that period previously had any data at all.

### Idempotent reruns — partition-overwrite, merge keys, deterministic transforms

The mechanical safety net that makes any backfill/replay survivable is the same idempotency discipline from `T18-ingestion`, applied at the level of a whole date range rather than a single row:

- **Partition overwrite** — rerunning the pipeline for a given date/partition completely replaces that partition's data (`INSERT OVERWRITE PARTITION`, or a full delete-then-insert scoped to exactly that partition's key range) rather than appending on top of what's already there. This is the single most important mechanical guarantee: a backfill run twice for the same date must produce the same result the second time as the first, not double the rows.
- **Merge keys** — for cases where partition overwrite isn't clean (a fact table not naturally partitioned by the backfilled dimension), a merge/upsert keyed on the natural key, same mechanism as `T18-ingestion`'s idempotent load pattern, ensures a rerun converges to the same state rather than duplicating.
- **Deterministic transforms** — the transformation logic itself must be a pure function of its inputs: no `NOW()`, no random ordering-dependent aggregation, no reliance on the wall-clock time the backfill happens to run. A transform that embeds `CURRENT_TIMESTAMP` into a computed column produces a different result every time it's rerun, which makes idempotency impossible to verify (every rerun looks "different" even when the underlying logic hasn't changed) and makes debugging a discrepancy between two runs much harder.

```sql
-- Bad: appends every time, backfilling the same date twice doubles the data
INSERT INTO fact_sales
SELECT * FROM staging_sales WHERE sale_date = '2026-03-15';

-- Good: idempotent partition overwrite — rerunning is a safe no-op on the data
INSERT OVERWRITE TABLE fact_sales
PARTITION (sale_date = '2026-03-15')
SELECT * FROM staging_sales WHERE sale_date = '2026-03-15';
```

### Ordering and concurrency limits — not saturating the cluster or the warehouse

A backfill spanning a year of daily partitions, launched naively, can fire 365 concurrent jobs against the same warehouse compute and the same source systems simultaneously — this is functionally a self-inflicted denial-of-service against your own infrastructure. Concrete controls:

- **`max_active_runs`** (Airflow, see `T18-airflow`) caps how many DAG runs (backfilled dates) execute concurrently, letting a year-long backfill proceed as, say, 5 concurrent date-partitions rather than 365.
- **Rate-limiting against source systems** specifically — a backfill re-extracting a year of data from an OLTP source needs the same read-load discipline as normal incremental extraction (see `T18-ingestion`), since a backfill hitting the source at 50x normal query volume can degrade the production database backing a live application.
- **Warehouse compute budgeting** — a large backfill can consume a disproportionate share of shared warehouse compute (Snowflake credits, BigQuery slots, a shared Spark cluster's executors); scheduling backfills during low-traffic windows, or on dedicated/isolated compute, prevents it from starving concurrent production workloads.
- **Ordering matters when later partitions depend on earlier ones** — a backfill of a cumulative/running-total metric must process partitions in chronological order (parallelizing it would compute each day's cumulative value against a stale or missing prior-day base), whereas a backfill of independent, non-cumulative daily aggregates can safely parallelize.

### Late data and reprocessing windows

Late-arriving data (covered in ingestion terms in `T18-ingestion`) intersects with backfill/replay here: a defined reprocessing window (e.g., "revenue for a given day is considered final after 3 days, to accommodate typically-late payment reconciliation records") means a *planned*, small-scope replay of the last 3 days runs automatically as part of normal operations, distinct from an *unplanned* backfill/replay triggered by discovering a bug or a gap. Conflating these two is a common design mistake: a system built only around "run once, trust the result" has no clean mechanism for the routine, expected case of "this day's numbers get one automatic correction pass 3 days later," and ends up hand-rolling ad hoc reprocessing logic for what should be a first-class, scheduled part of the pipeline.

### Backfill vs replay — and why replay is riskier

- **Backfill**: fill in history that never ran — a gap. There is nothing at that partition to accidentally corrupt; worst case, the backfill itself has a bug and the newly-filled data is wrong, which is bad but bounded and detectable by comparing against expectations for a period that was previously simply empty.
- **Replay**: recompute history that already ran and is already being used — recomputing an existing, "correct" (or previously-believed-correct) partition. This is strictly riskier because a replay that goes wrong doesn't just fail to fill a gap, it **actively overwrites data that downstream consumers, dashboards, and possibly external reports have already relied on**, and if the replay logic has a subtle new bug, you've now corrupted something that was previously fine. A replay's blast radius includes everything already built on top of the data being replayed; a backfill's blast radius is bounded by "nothing was there before, so nothing built on top of it yet either" (assuming the gap was genuinely never populated, which needs verifying — a gap that some downstream consumer already worked around with their own patch is a more complicated case).

### Audit trail — proving what a rerun changed

Any backfill/replay run against production data needs a durable record answering: what was rerun (exact date/partition range), when, by whom, what code version, and — critically — **what did the data look like before and after**. Practical mechanisms: lakehouse time-travel (Delta Lake/Iceberg snapshot versions, see `T18-lakehouse`) let you diff the table's state immediately before and after the operation without needing a separate backup process; a dedicated backfill-log table recording the parameters of every backfill run (date range, triggering user/reason, code commit hash) turns "did anyone backfill this table last month" from an oral-history question into a query. Without this, diagnosing "why did this number change" after a backfill requires reconstructing what happened from memory or scattered Slack messages, which is exactly the failure mode formal audit trails exist to prevent.

### The observable symptom of a partially-applied backfill

A backfill that fails partway through (a job dies after processing 40 of 100 date partitions) leaves the table in a mixed state: some partitions reflect the new/corrected logic, others still reflect the old data. **The observable symptom**: a time-series chart of a metric over the backfilled range shows a discontinuity or a step-change exactly at the boundary between reprocessed and not-yet-reprocessed partitions, with no underlying business reason for the jump — a classic "why does this chart have a weird kink right at March 15th" support ticket. This is diagnosed by checking the backfill's own run log/audit trail for where it actually stopped, and it's why `max_active_runs`-style controls plus resumable, partition-level tracking (so a restarted backfill picks up from where it failed rather than restarting from the beginning or, worse, silently skipping the unprocessed remainder) matter operationally, not just for throttling.

### When NOT to backfill

Sometimes the correct answer is to **not** backfill and instead **document the gap**. This applies when:
- The source data needed to backfill correctly no longer exists (the source system has purged history, or the API/vendor doesn't retain data that far back) — attempting to backfill anyway with an approximation (interpolation, a rough estimate) risks presenting fabricated-looking data as if it were real historical fact, which is worse than an honestly documented gap.
- The cost/risk of the backfill (warehouse compute, engineering time, risk of a replay corrupting adjacent correct data) exceeds the value of the missing data, especially for a low-traffic historical period nobody is actively querying.
- The bug being "fixed" by the backfill is actually a legitimate historical fact (the business logic really was different then, and applying today's logic retroactively would misrepresent what genuinely happened) — in this case, backfilling isn't a fix, it's rewriting history incorrectly.

A documented gap (a note in the table's metadata, a known-issues log, or simply leaving the partition empty with a comment) is an honest, low-risk answer; a poorly-executed backfill that introduces a subtle new error is a worse outcome than admitting the data doesn't exist for that period.

---

## Build it from scratch

A minimal, idempotent, concurrency-limited backfill runner demonstrating partition-overwrite, resumability, and an audit log — the shape of what a production backfill tool actually needs beyond "loop over dates."

```python
# untested sketch — illustrates the safety mechanics, not a production backfill tool
from dataclasses import dataclass
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class BackfillRun:
    partition_date: date
    status: str            # "pending" | "success" | "failed"
    code_version: str
    triggered_by: str

def log_backfill_attempt(run: BackfillRun, audit_log) -> None:
    # durable record: WHAT was rerun, WHEN, BY WHOM, WHAT CODE VERSION —
    # this is what makes "what did this rerun change" answerable later
    audit_log.record(run)

def process_partition_idempotent(partition_date: date, code_version: str) -> None:
    """Must be a pure function of (partition_date, code_version, reference
    data as of NOW) — no NOW()/random ordering inside the transform itself,
    and it must OVERWRITE the partition, never append."""
    data = extract_source_data(partition_date)
    transformed = apply_business_logic(data)          # deterministic given inputs
    overwrite_partition(table="fact_sales", partition_date=partition_date, rows=transformed)

def run_backfill(
    start: date, end: date, code_version: str, triggered_by: str,
    audit_log, max_concurrency: int = 5,
) -> list[BackfillRun]:
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    results = []

    def _do(d: date) -> BackfillRun:
        run = BackfillRun(d, "pending", code_version, triggered_by)
        log_backfill_attempt(run, audit_log)
        try:
            process_partition_idempotent(d, code_version)
            run.status = "success"
        except Exception:
            run.status = "failed"
            raise
        finally:
            log_backfill_attempt(run, audit_log)   # log BOTH start and terminal state
        return run

    # bounded concurrency — this is the "don't saturate the cluster" control;
    # a real implementation also needs to detect cumulative-metric dependencies
    # and force sequential ordering when partitions aren't independent
    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        futures = {pool.submit(_do, d): d for d in dates}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                # a partial failure here is exactly the "partially-applied
                # backfill" scenario — the audit log already recorded which
                # dates succeeded, so a resumed run can skip them
                pass
    return results
```

The three details that separate this from a naive `for date in dates: run(date)` loop: partition overwrite (not append) inside `process_partition_idempotent`, an audit log recording both the attempt and the terminal state of every partition (making a partial failure resumable and diagnosable), and bounded concurrency rather than firing every date at once. Full version with cumulative-metric dependency detection and a real time-travel diff: `(lab pending)`.

---

## How it's done in production

**Airflow** — `airflow dags backfill` (or the UI's "clear" + rerun mechanics) reruns a DAG for a date range using the exact same task code as normal scheduled execution, respecting `max_active_runs` to bound concurrency; this is the concrete implementation of "backfills should run the same code path as normal execution," not a separate script.

**dbt** — incremental models support `dbt run --full-refresh`, which drops and rebuilds the entire incremental table from scratch (a full replay), versus a scoped backfill achieved by manually adjusting the model's date-filtering variables for a specific range and rerunning just that range; `dbt snapshot`'s Type 2 SCD mechanics (see `T17-dimensional-modeling`) mean a naive full-refresh of a snapshot can be particularly dangerous, since it can disrupt carefully-built historical versioning if not handled with care.

**Lakehouse time-travel** (Delta Lake `VERSION AS OF`/`TIMESTAMP AS OF`, Iceberg snapshots, see `T18-lakehouse`) provides the audit-trail mechanism natively: query the table as it existed immediately before a backfill/replay to diff against the post-backfill state, without needing a separate backup step.

**Cumulative/dependent-partition backfills** (running totals, retention cohorts) typically run through the orchestrator with an enforced sequential dependency (each date's task depends on the prior date's task completing, not just being scheduled), explicitly sacrificing the parallelism a naive backfill would otherwise use, because correctness requires strict ordering here.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| A time-series chart shows a sudden, unexplained step-change on a specific date | A backfill failed partway through, leaving the range in a mixed old-data/new-data state | Check the backfill audit log for where it actually stopped; resume from the last successful partition, don't restart from scratch |
| Historical revenue numbers shift after an "unrelated" backfill of a different table | The backfill joined against a "current" reference table (exchange rates, tax tables) instead of the point-in-time-correct historical version | Use SCD Type 2 dimension lookups with an as-of filter (see `T18-data-modeling-e2e`) inside the backfill logic, not a join to the dimension's current state |
| A backfill run twice for the same date produces double the rows | Backfill appends instead of overwriting the partition | Switch to `INSERT OVERWRITE PARTITION` or a merge/upsert keyed on the natural key |
| A large backfill takes down or severely degrades an unrelated team's warehouse queries | No concurrency limit or compute budgeting on the backfill | Bound concurrency (`max_active_runs`), schedule during low-traffic windows, or use isolated/dedicated compute for large backfills |
| A parallelized backfill of a cumulative metric produces wrong running totals | Partitions processed out of order or concurrently when later ones depend on earlier ones | Enforce strict sequential processing for dependent partitions; only parallelize genuinely independent ones |
| Nobody can explain why a table's historical data changed last quarter | No audit trail recording what was backfilled, when, by whom, and with what code version | Log every backfill/replay's parameters and outcome to a durable, queryable audit table |
| A backfill "fixes" a number that turns out to have been historically accurate | The old business logic was genuinely correct for that period, and today's logic doesn't apply retroactively | Verify whether a discrepancy is a bug or a legitimate historical difference before backfilling; when in doubt, don't backfill, document the difference instead |

---

## Tradeoffs & when NOT to use it

- **Do not run a replay without first confirming the discrepancy is actually a bug, not a legitimate historical fact.** Replaying a period whose old logic was correct at the time overwrites accurate history with a today's-logic approximation that misrepresents what genuinely happened.
- **Do not backfill using "current" reference data for a transform that has time-sensitive external inputs** (exchange rates, tax rates, pricing tiers) — this reintroduces exactly the point-in-time-correctness bug that SCD Type 2 dimensional modeling exists to prevent.
- **Do not launch an unthrottled backfill against shared warehouse compute or a live production source system.** A backfill is a large, bursty workload; treat its concurrency and scheduling with the same care as any other capacity-planning decision, not as a fire-and-forget script.
- **Do not backfill when the source data needed to do it correctly no longer exists.** An approximation dressed up as real historical data is worse than an honestly documented gap — this is the concrete "when NOT to backfill" case, not a hypothetical.
- **Do not treat backfill and replay as the same risk level.** A backfill fills a genuine gap (bounded downside: worst case, the fill is wrong, but nothing correct gets overwritten). A replay recomputes and overwrites data already in use by downstream consumers (unbounded downside if the new logic has a bug: you've now broken something that was previously fine). Apply proportionally more caution, review, and staging/validation to replays.

---

## Interview questions

### Q1 — Explain precisely why backfills are dangerous, beyond "it's a lot of data to process."
**Testing:** whether the core mechanism (code/reference-data drift) is understood, not just "backfills are risky" as a slogan.
**Answer:** A backfill runs today's code and today's reference data against a historical date parameter. If the transformation logic or any time-sensitive reference data (exchange rates, tax tables, pricing) has changed since that historical period, the backfilled result reflects the present, not the past that actually occurred — which can be desirable (retroactively applying a genuine bug fix) or actively wrong (retroactively applying a business rule that legitimately didn't exist at the time), and there's no automatic way to tell which case you're in without deliberately checking.
**Follow-up trap:** *"How would you actually check which case you're in before running a backfill?"* — trace whether the discrepancy driving the backfill is a code bug (safe/desirable to apply retroactively) or a legitimate difference in business rules or external reference values over time (not safe to apply retroactively); if it's the latter, use point-in-time-correct historical reference data (SCD Type 2 dimension lookups as-of the historical date) inside the backfill logic rather than joining to current reference tables.

### Q2 — What's the difference between a backfill and a replay, and why is a replay riskier?
**Answer:** A backfill fills in history that never ran — a genuine gap with nothing there to corrupt; worst case, the new fill is wrong, which is bad but bounded. A replay recomputes history that already ran and is already in use — dashboards, reports, and downstream tables may already be built on top of the data being replayed, so a replay with a subtle new bug doesn't just fail to fill a gap, it actively overwrites and potentially corrupts data that was previously correct and already relied upon.
**Follow-up trap:** *"Is a backfill ever as risky as a replay?"* — yes, when a downstream consumer has already independently worked around a known gap (built their own patch or manual adjustment assuming the data would stay missing); filling the gap now conflicts with that workaround, which is functionally similar to a replay's risk profile even though it's technically "filling a gap." The label (backfill vs replay) is a useful heuristic for risk, not a guarantee.

### Q3 — Design the safety controls for a year-long backfill of a daily fact table on a shared Snowflake warehouse.
**Testing:** synthesizing idempotency, concurrency limits, and compute budgeting into one operational plan.
**Answer:** Idempotent partition overwrite per day (`INSERT OVERWRITE PARTITION` or an equivalent merge, never append) so a retried or resumed date is a safe no-op. Bounded concurrency (e.g., `max_active_runs=5` in Airflow) so 365 days don't fire simultaneously against the shared warehouse. Scheduling during a low-traffic window, or on a dedicated virtual warehouse/compute pool isolated from production query traffic, so the backfill doesn't starve concurrent workloads. An audit log recording each date's attempt and outcome so a partial failure can resume from where it stopped rather than restarting or silently leaving a gap.
**Follow-up trap:** *"What if this fact table includes a cumulative running-total column?"* — that specific column's computation must process partitions strictly in chronological order, since a concurrent or out-of-order run would compute each day's cumulative value against a stale or missing prior-day base; the concurrency bound above needs to become full sequential ordering for that dependency, even though the rest of the table's columns might tolerate parallel backfilling.

### Q4 — What's the observable symptom of a partially-applied backfill, and how do you diagnose it?
**Answer:** A time-series chart of a metric over the backfilled range shows a sudden step-change or discontinuity exactly at the boundary between partitions that were reprocessed and partitions that weren't, with no underlying business explanation for the jump — a "why is there a weird kink on March 15th" support ticket is the classic presentation. Diagnose it by checking the backfill's own audit/run log for exactly which partitions succeeded before the job failed or was interrupted.
**Follow-up trap:** *"What operational feature prevents this from turning into a manual investigation every time?"* — resumable, partition-level tracking: a backfill tool that records success/failure per partition (not just overall job success/failure) lets a restarted backfill pick up exactly where it left off rather than either restarting everything from scratch (wasteful) or silently leaving the unprocessed remainder in its old state (the actual bug), and it makes the diagnosis itself a log query instead of a chart-staring exercise.

### Q5 — When would you deliberately choose NOT to backfill, even though you've identified a real gap in the data?
**Answer:** Three concrete cases: the source data needed to backfill correctly no longer exists (source system purged it, vendor doesn't retain history that far back) — an approximation risks presenting fabricated data as real; the cost/risk of the backfill (compute, engineering time, risk of a replay corrupting adjacent correct data) exceeds the value of the missing data, especially for a rarely-queried historical period; or the "gap" turns out to be a legitimate historical fact rather than a bug — the old logic was genuinely correct for that period, and applying today's logic retroactively would misrepresent history rather than fix it.
**Follow-up trap:** *"Isn't 'don't backfill' just avoiding the work?"* — no, documenting a gap explicitly (a note in the table's metadata or a known-issues log) is itself a deliverable and arguably the more honest, more senior choice than a poorly-executed backfill that introduces a subtle new error while looking superficially complete; the wrong answer is silently leaving the gap undocumented, not choosing not to backfill.

### Q6 — Why must the transformation logic used in a backfill be deterministic, and give an example of a common violation?
**Answer:** A backfill/replay's idempotency (rerunning produces the same result) can only be verified and trusted if the transform is a pure function of its inputs — the historical date, the source data as it existed, and any explicitly point-in-time-correct reference data. A common violation: embedding `CURRENT_TIMESTAMP` or `NOW()` into a computed column (e.g., an "as-of" or "processed-at" audit column mixed into business logic rather than kept as pure metadata), which makes every rerun of the same partition produce a superficially different result even when nothing about the underlying logic changed, making it impossible to tell a genuine discrepancy from expected non-determinism.
**Follow-up trap:** *"Isn't a 'processed_at' audit column useful and legitimate to include?"* — yes, but it must be kept structurally separate from the business-logic columns that idempotency and correctness checks care about; a metadata column recording when a row was last processed is fine, but if the backfill's actual business calculations (a computed price, a status derived from "time since X") depend on wall-clock time at the moment of the rerun rather than the historical date being processed, that's the non-determinism that breaks idempotency guarantees.

### Q7 — A backfill needs to correct a currency-conversion bug affecting six months of revenue data. Walk through what would go wrong with a naive implementation, and the correct approach.
**Answer:** A naive implementation joins historical transactions to a "current" exchange-rate table, applying today's rates to transactions from six months ago — producing plausible-looking but factually wrong historical revenue, since exchange rates fluctuate daily and today's rate is not what was actually in effect for those transactions. The correct approach uses a point-in-time-correct exchange-rate dimension (SCD Type 2, as covered in `T17-dimensional-modeling` and `T18-data-modeling-e2e`) joined with an as-of filter matching each transaction's actual date, so the backfill applies the rate that was genuinely in effect at the time, correcting only the intended bug (the conversion logic itself) without introducing a second, new error (wrong historical rates).
**Follow-up trap:** *"What if the exchange-rate history itself wasn't captured with point-in-time versioning before now?"* — this is a real, common gap: if the reference data was only ever stored as "current value, overwritten daily" with no history retained, the point-in-time-correct rate for six months ago may be permanently unrecoverable, which is itself a case for documenting a known limitation on the backfill's accuracy rather than pretending precision that doesn't exist, or sourcing the missing historical rates from an external archive if one exists.

### Q8 — How does lakehouse time-travel (Delta Lake, Iceberg) improve the audit-trail story for backfills compared to relying on periodic backups?
**Answer:** Time-travel lets you query the exact state of a table at any prior snapshot/version directly, so diffing "what did this table look like immediately before the backfill" against "what does it look like now" is a query, not a restore-from-backup operation that requires provisioning separate infrastructure and time to execute. This makes verifying exactly what a backfill changed (and catching an unintended side effect on rows outside the intended date range, for instance) fast enough to do routinely, rather than only during a post-incident investigation when a backup restore is justified.
**Follow-up trap:** *"Does time-travel eliminate the need for a separate backfill audit log?"* — no, it answers "what changed" at the data level but not "who ran this, when, why, and with what code version" — the operational/governance metadata a backfill-log table captures. Time-travel and an audit log are complementary: one proves the data-level diff, the other proves the human/process context around why that diff happened.

### Q9 — Your team wants to make backfills "self-service" so any engineer can trigger one without going through a data platform team review. What's the argument against this, and what would you require instead?
**Answer:** Backfills carry real risk (code/reference-data drift, warehouse saturation, replay corruption of already-relied-upon data) that a self-service, unreviewed trigger makes easy to invoke without necessarily understanding — the operation looks superficially simple ("just rerun for these dates") while carrying the compounding risks discussed throughout this module. A middle ground: self-service is fine for well-understood, low-risk cases (genuine gaps in a low-traffic table, using a tool that enforces idempotent partition overwrite and concurrency limits automatically), while anything touching a business-critical or externally-reported table, or any operation classified as a replay rather than a backfill, requires review specifically because the blast radius is larger and less obviously bounded.
**Follow-up trap:** *"Isn't requiring review just slow bureaucracy that discourages fixing real bugs?"* — the review doesn't need to be slow if it's scoped correctly: a lightweight check specifically for "is this a backfill or replay, does it touch reference data that's changed over time, and what's the concurrency/compute plan" catches the actual risk categories in this module without requiring a full committee process, and self-service tooling can enforce the mechanical safety nets (idempotent overwrite, bounded concurrency, mandatory audit logging) automatically so review focuses on the judgment calls (is this discrepancy a bug or history) rather than re-litigating mechanics every time.

### Q10 — What's the relationship between a "reprocessing window" for late-arriving data and backfills — are they the same operation?
**Answer:** A reprocessing window is a planned, small-scope, automatic replay built into normal pipeline operation (e.g., "this day's numbers get one automatic correction pass 3 days later to catch late-arriving records") — it's a first-class, scheduled part of the pipeline, not an unplanned recovery operation. A backfill or ad hoc replay is triggered by discovering an unplanned gap or bug, is typically manually initiated, and often has a much larger or less predictable scope. They share the same underlying mechanical requirements (idempotent partition overwrite, deterministic transforms), but conflating them operationally is a design mistake — a system with no first-class reprocessing-window mechanism ends up hand-rolling ad hoc backfill-style logic for what should be routine, expected, low-drama reprocessing.
**Follow-up trap:** *"If reprocessing windows use the same mechanics as backfills, why do they deserve different operational treatment?"* — because a reprocessing window is bounded, expected, and scoped by design (always exactly the last N days, always automatic, never touching arbitrary historical ranges), so it doesn't need the same case-by-case risk review a backfill does; treating every reprocessing-window run as a full manual backfill review would be needless overhead for an operation whose blast radius is already deliberately constrained.

---

## Red flags that fail you

- Describing a backfill as "just rerun the job for those dates" with no mention of code/reference-data drift.
- Not distinguishing backfill risk from replay risk, or treating them as identically safe.
- Proposing an append-only rerun instead of partition overwrite or a merge/upsert.
- Launching a backfill with no concurrency limit or compute-budgeting consideration.
- Not having an audit-trail answer for "how would you prove what this backfill changed."
- Treating "we should backfill this" as always correct with no consideration of "when NOT to."
- Not knowing that a non-deterministic transform (embedding `NOW()` in business logic) breaks idempotency guarantees.

---

## Cheat card

```
CORE RISK   backfill/replay runs TODAY'S code + TODAY'S reference data
            against a HISTORICAL date. Code drift (bug fix, new business
            rule) + reference-data drift (exchange rates, tax tables) both
            apply — this is the central danger, not "it's a lot of data."

BACKFILL vs REPLAY
   backfill: fill a GAP that never ran. Bounded downside — nothing correct
             to overwrite (unless a downstream consumer already patched
             around the gap).
   replay:   RECOMPUTE existing history already in use downstream.
             Unbounded downside — a new bug corrupts data that was
             previously fine and already relied upon. STRICTLY RISKIER.

IDEMPOTENT RERUN   partition OVERWRITE (INSERT OVERWRITE PARTITION), not
            append. Merge/upsert on natural key when overwrite isn't clean.
            Transform must be DETERMINISTIC — no NOW()/random ordering
            inside business logic, or idempotency can't be verified.

CONCURRENCY/BLAST RADIUS   max_active_runs caps concurrent date-partitions
            (don't fire 365 jobs at once). Rate-limit source re-extraction.
            Budget/isolate warehouse compute (don't starve prod queries).
            Cumulative/dependent metrics (running totals) MUST process
            partitions in strict chronological order — no parallelizing.

LATE DATA / REPROCESSING WINDOW   planned, small, AUTOMATIC replay built
            into normal ops (e.g. "final after 3 days") — different from
            an unplanned, manually-triggered backfill. Don't conflate them
            operationally; reprocessing windows don't need full backfill review.

PARTIAL-BACKFILL SYMPTOM   time-series shows a sudden step-change/kink at
            the exact boundary between reprocessed and not-yet-reprocessed
            partitions, no business reason. Diagnose via the backfill's own
            audit log for where it stopped; needs resumable, partition-level
            tracking to fix without restarting from scratch.

AUDIT TRAIL   log WHAT range, WHEN, BY WHOM, WHAT CODE VERSION, per
            partition (start + terminal state). Lakehouse time-travel
            (Delta/Iceberg snapshots) diffs before/after state as a query,
            not a backup restore — complementary to, not a replacement
            for, the audit log's process/governance metadata.

WHEN NOT TO BACKFILL   source data no longer exists (don't fabricate) ·
            cost/risk exceeds the value of a rarely-queried gap ·
            the "bug" is actually a legitimate historical fact (old logic
            was correct then — backfilling would misrepresent history).
            A documented gap beats a subtly-wrong backfill.

CROSS-REF   idempotent load mechanics -> T18-ingestion
            point-in-time-correct dimension joins -> T18-data-modeling-e2e,
              T17-dimensional-modeling
            what triggers a rerun -> T18-scheduling-triggering
            concurrency controls in the orchestrator -> T18-airflow
```

## Sources

- [Backfilling Historical Data With Idempotent Data Pipelines — ml4devs](https://www.ml4devs.com/what-is/backfilling-data/) — accessed 2026-08-01
- [Idempotent Pipelines: Build Once, Run Safely Forever — DEV Community](https://dev.to/alexmercedcoder/idempotent-pipelines-build-once-run-safely-forever-2o2o) — accessed 2026-08-01
- [Backfill — MotherDuck Glossary](https://motherduck.com/glossary/backfill/) — accessed 2026-08-01
- [Data Pipeline Backfills Without Breaking Production](https://codewithfimi.com/data-pipeline-backfills-without-breaking-production/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
