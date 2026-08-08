# Contracts, Great Expectations, Freshness/Volume/Schema SLAs, Lineage

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-data-quality` · **Tags:** quality

## The 30-second version

Data quality means checking four dimensions — freshness, volume, schema, distribution — at explicit gates, not hoping a green pipeline run implies correct data. A data contract has to be enforced in the producer's CI before a breaking change ships; catching it downstream after the data already landed is too late by definition. dbt tests, Great Expectations, and Soda aren't competitors, they cover three different moments: dbt tests at build time next to the model, Great Expectations for raw-ingestion validation dbt can't reach, Soda for continuous scheduled monitoring with anomaly detection. Fail-fast beats fail-quiet because the cost of a bad row grows with every downstream hop it travels before being caught. And the fastest way to kill a quality system is paging on-call for every failure regardless of impact — that's exactly how the one alert that matters ends up firing into a muted channel.

## Why this gets asked

Because every data engineer has shipped a pipeline that "worked" — no errors, green DAG, on schedule — and produced silently wrong numbers for weeks. The interviewer has lived through the incident where a dashboard was wrong for a full quarter because nothing was actually checking correctness, only checking "did the job finish." They want to know if you think about data quality as a *system* (contracts, enforcement points, alerting discipline) rather than "we added some dbt tests," and whether you've seen alert fatigue kill a monitoring system from the inside — a team that mutes Slack after the fortieth false-positive freshness alert has a quality system in name only.

---

## Lineage: past → present → future

**What came before.** Early data warehouses had no systematic quality layer at all: correctness was whatever the ETL developer's manual spot-checks caught, and the first anyone heard of a broken pipeline was usually a business stakeholder noticing a number looked wrong in a monthly report, weeks after the underlying bug shipped. The pain was structural, not a tooling gap: nobody owned "is this data correct" as a first-class deliverable the way "did the job run" was owned by the orchestrator. dbt's built-in tests (2018 onward — `unique`, `not_null`, `relationships`, `accepted_values`) were the first widely-adopted attempt to make assertions about data a normal part of the transformation codebase rather than a separate, often-skipped QA phase.

**Where it stands now.** Three tool families have settled into complementary rather than competing roles. **dbt tests** live next to the models they check, version-controlled with the transformation logic, and are the natural default for anything expressible as SQL assertions during a build. **Great Expectations (GX)**, rebuilt around **GX Core** as a Python-native library, is the choice when validation logic needs to be more expressive than SQL allows or needs to run at points a dbt build doesn't touch (raw ingestion, before anything is even a dbt model). **Soda** (SodaCL, YAML-based checks) differentiates on continuous *observability* — scheduled checks against production tables with native trailing-window anomaly detection, positioning it closer to a monitoring product than a build-time test suite. The live disagreement isn't which tool wins; it's **where in the pipeline validation should live at all** — "shift left" advocates for validating at ingestion so bad data never reaches the warehouse, while "validate where you use it" advocates argue duplicate validation logic across every ingestion point doesn't scale and centralizing checks at the semantic/BI layer is more maintainable. Most mature teams end up doing both at different tiers, which is itself the practical answer.

**Where it's heading.** **Data contracts** — a machine-readable schema-plus-semantics agreement between a data producer and consumer, enforced before data crosses the boundary — are moving from "advanced practice at a handful of companies" (this pattern is closely associated with how Airbnb, GoCardless, and Convoy formalized producer/consumer boundaries publicly) toward mainstream expectation for any team with more than a couple of downstream data consumers, though tooling maturity (schema registries with semantic versioning, breaking-change detection in CI) still varies widely. **Column-level, automatically-captured lineage** (OpenLineage, now integrated across Spark, Airflow, and dbt) is real and shipping, shrinking incident diagnosis time from "grep every pipeline that might touch this table" to "query the lineage graph." More speculative: LLM-assisted anomaly triage (a model reading an alert plus recent lineage and proposing a root cause) exists in early vendor form but should be treated as a first-pass filter for a human, not a substitute for the human confirming causation.

---

## Mental model

```
                     PRODUCER                                    CONSUMER
                 ┌──────────────┐                            ┌──────────────┐
                 │ source system│                            │ dashboard /  │
                 │ / upstream   │                            │ ML feature / │
                 │ pipeline     │                            │ downstream   │
                 └──────┬───────┘                            └──────▲───────┘
                        │                                           │
              ┌─────────▼─────────┐   DATA CONTRACT   ┌─────────────┴──────┐
              │  validate at      │◀── (schema +      │  validate in-       │
              │  INGEST           │     semantics,     │  warehouse before   │
              │  (fail-fast:      │     enforced       │  it reaches a       │
              │   reject before   │     before it      │  consumer           │
              │   it lands)       │     crosses)        │  (dbt test, GX      │
              └───────────────────┘                     │  checkpoint)        │
                                                          └─────────────────────┘
        Four dimension groups checked at EVERY gate:
        FRESHNESS (is it recent enough?)  VOLUME (row count in range?)
        SCHEMA (shape/types as expected?)  DISTRIBUTION (values plausible?)
```

**The mental model that matters**: quality is not one check at the end, it's the same four dimension groups evaluated at multiple gates, and *where* you fail (reject at the door vs. quarantine and continue vs. let it through and alert) is a deliberate choice per gate, not a default.

---

## How it actually works

### Data contracts — where they're enforced

A **data contract** specifies, for a dataset a producer emits, the schema (field names, types, nullability), semantic guarantees (this column is the primary key, this enum's valid values are exactly these five), and SLAs (freshness, expected volume range) — agreed between producer and consumer, versioned, and checked in CI on the producer's side before a breaking change can ship. The enforcement point is deliberately upstream of the warehouse: a contract check that runs *after* a breaking change has already landed in the warehouse and broken three downstream dashboards has already failed at its one job. Practically, this means schema-registry-style validation on the producer's CI/CD pipeline (a schema-incompatible change to an event payload fails the producer's build, not the consumer's pipeline three hops downstream), or a dbt-defined contract (`config: {contract: {enforced: true}}`) that fails a model's build if its output doesn't match the declared column types.

### The four dimension groups, with real thresholds

| Dimension | What it checks | Example SLA |
|---|---|---|
| **Freshness** | Is the data as recent as it claims/needs to be? | `orders` table must have a row with `updated_at` within the last 90 minutes; alert if max `updated_at` age exceeds 2 hours |
| **Volume** | Is the row count/size plausible? | Daily load should land 800k-1.2M rows (±20% of a 7-day trailing average); alert if outside that band, page if under 50% (likely a broken extract) |
| **Schema** | Does the shape match what's expected? | Exactly 14 columns, `customer_id` is non-null `bigint`, `status` is one of 6 known enum values |
| **Distribution** | Are the values themselves plausible? | `discount_amount` should never exceed `order_total`; `email` column null rate should stay under 0.5%; a categorical column's distribution shouldn't shift more than N standard deviations from its 30-day baseline |

Freshness and volume are the two checks that catch the largest fraction of real incidents in practice, because they detect "the pipeline silently stopped or partially ran" without needing to know anything about the business semantics of the data — which is also why they're the cheapest checks to write and should be the first ones any team adds.

### Great Expectations, Soda, dbt tests — what each is actually good for

- **dbt tests** — `unique`, `not_null`, `relationships`, `accepted_values`, plus custom singular/generic SQL tests, run as part of `dbt build`. Best for: assertions naturally expressed as SQL, checked at build time, living next to the model definition so a broken assumption fails the build immediately. Weak for: continuous/scheduled monitoring outside a build run, and for validation that needs Python-level expressiveness (statistical distribution checks, cross-system comparisons).
- **Great Expectations (GX Core)** — Python library; you define **Expectation Suites** (collections of declarative expectations like `expect_column_values_to_be_between`) and run them via a **Checkpoint** against a **Data Context**. Best for: validating raw/ingested data before it becomes a dbt model (a layer dbt tests structurally can't reach, since dbt only tests things it has already built), expressive custom validation logic, and generating human-readable data docs automatically. Weak for: being the primary continuous-monitoring layer — GX is triggered by a pipeline step, not natively scheduled/observability-first the way Soda is.
- **Soda (SodaCL)** — YAML-first declarative checks (`checks for orders: - row_count > 0 - missing_count(customer_id) = 0 - anomaly score for row_count`), designed to run on a schedule against production tables independent of any specific pipeline run, with native trailing-window anomaly detection built in rather than requiring custom statistical code. Best for: continuous observability and anomaly detection on tables already in production; weakest at build-time, model-adjacent testing, where dbt tests fit more naturally.

The common production pattern, and a strong senior answer: **dbt tests during transformation, Great Expectations for rigorous validation of raw data at ingestion or on business-critical assets, Soda for continuous monitoring and anomaly alerting on warehouse tables in production.** Not one tool "winning" — three tools solving three different validation moments.

### Validating at ingest vs in-warehouse — fail-fast beats fail-quiet

Validating at ingest means bad data never lands; the pipeline rejects or quarantines it before it's queryable by anyone. Validating in-warehouse (a dbt test that fails after the model has already run) means bad data *did* land, possibly got queried by a dashboard before the test caught it, and now requires cleanup in addition to a fix. **Fail-fast beats fail-quiet** because the cost of a bad row grows with every hop downstream it travels — a bad row caught at ingestion costs one quarantine record; the same bad row caught three joins and a materialized dashboard later costs a data cleanup, a stakeholder apology, and possibly a compliance question about whether the number was ever reported externally.

The two operational responses to a validation failure are structurally different and the choice matters:
- **Circuit-breaking the pipeline** — stop the entire run, page someone, nothing downstream updates until it's fixed. Right for anything where partially-wrong data is worse than stale-but-correct data (financial reporting, anything feeding a regulatory filing).
- **Quarantining bad rows** — let the good rows through, route the bad ones to a dead-letter/quarantine table, and continue. Right for high-volume pipelines where a small bad-row rate is expected and acceptable, and where blocking the entire pipeline over a known, bounded failure mode causes more harm (stale data for everyone) than it prevents.

### Lineage — the incident it shortens

**OpenLineage** is an open standard (integrated with Spark, Airflow, dbt) for emitting structured events describing what ran, what it read, and what it wrote; **Marquez** is the reference implementation that ingests those events into a queryable lineage graph. **Column-level lineage** (supported for Spark, Airflow, and dbt integrations) goes further: not just "table A feeds table B" but "column `revenue` in the gold mart is derived from columns `unit_price` and `quantity` in the silver table, via this specific transformation." The incident this shortens: a stakeholder reports a wrong number in a dashboard, and instead of manually tracing through dbt DAGs, Airflow DAGs, and Spark jobs by hand (which, at a company with a few hundred models, can take hours and depends on someone who remembers the pipeline history), a lineage query answers "which upstream table changed, and did anything change in the last 24 hours that could explain this" directly, often in minutes rather than hours.

### The anti-pattern of alerting on everything

Alert fatigue is the single most common way a data-quality system dies. A team that wires every dbt test failure, every freshness check, and every schema-drift detection to page the on-call engineer discovers within a few weeks that most of those alerts are noise (a known, benign one-hour freshness delay from a slow upstream vendor, a schema check flagging an intentional, already-approved new column) — and the response is not "fix every alert," it's "mute the channel." Once a channel is muted, **the alert that actually mattered fires into silence**, and the quality system has negative value: it created the appearance of coverage while providing none. The fix is tiering: page only on checks tied to genuine business impact (a circuit-breaking freshness SLA on a revenue table), route everything else to a daily digest or dashboard a human reviews on their own schedule, and periodically prune checks that have never once indicated a real problem.

---

## Build it from scratch

A minimal freshness + volume + schema check runner, the shape of what a Great Expectations Checkpoint or a hand-rolled quality gate does conceptually.

```python
# untested sketch — illustrates the four-dimension check pattern, not a GX/Soda replacement
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

class Severity(Enum):
    PAGE = "page"        # circuit-break the pipeline, alert on-call now
    DIGEST = "digest"     # log, roll into a daily summary, no immediate alert

@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: Severity
    detail: str

def check_freshness(max_updated_at: datetime, max_age: timedelta, severity: Severity) -> CheckResult:
    age = datetime.utcnow() - max_updated_at
    return CheckResult(
        name="freshness", passed=age <= max_age, severity=severity,
        detail=f"max age {age}, threshold {max_age}",
    )

def check_volume(row_count: int, expected_low: int, expected_high: int, severity: Severity) -> CheckResult:
    ok = expected_low <= row_count <= expected_high
    return CheckResult(
        name="volume", passed=ok, severity=severity,
        detail=f"{row_count} rows, expected [{expected_low}, {expected_high}]",
    )

def check_schema(actual_columns: set[str], expected_columns: set[str], severity: Severity) -> CheckResult:
    missing = expected_columns - actual_columns
    return CheckResult(
        name="schema", passed=not missing, severity=severity,
        detail=f"missing columns: {missing}" if missing else "ok",
    )

def run_gate(results: list[CheckResult]) -> None:
    failures = [r for r in results if not r.passed]
    blocking = [r for r in failures if r.severity is Severity.PAGE]
    if blocking:
        # circuit-break: raise, stop the pipeline, page on-call
        raise RuntimeError(f"blocking quality failures: {[r.detail for r in blocking]}")
    for r in failures:
        # non-blocking: log for the daily digest, do not page
        log_to_digest(r)

def log_to_digest(result: CheckResult) -> None:
    ...
```

The design choice worth defending out loud: `Severity` is attached per-check, not globally, because a freshness miss on a revenue table and a freshness miss on a nice-to-have internal metrics table deserve different responses, and hardcoding "every failure pages" is exactly the alert-fatigue anti-pattern. Full version wired to a real GX Checkpoint and a Soda scan: `labs/py/18-data-quality-lab/`.

---

## How it's done in production

**Great Expectations (GX Core)** — define an Expectation Suite against a Data Context, run it via a Checkpoint at a pipeline step (commonly an Airflow task right after ingestion, before the raw data is exposed to any downstream model). GX Core is Python-native and free/open source; Expectation Suites and validation results are typically version-controlled alongside the pipeline code, and GX auto-generates human-readable "Data Docs" from suite results, which is a real, underrated win for onboarding new team members onto what a dataset's guarantees actually are.

**Soda Core / Soda Cloud** — SodaCL YAML checks run on a schedule (independent of any specific ingestion job), commonly against tables already in the warehouse; Soda Cloud layers a dashboard and alerting/anomaly UI on top of the open-source scan engine. This is the layer most naturally suited to "did this table that's usually stable suddenly look different," using its native trailing-window anomaly detection rather than hand-rolled statistical thresholds.

**dbt tests** — run as part of `dbt build`/`dbt test`, failing the build on violation; CI-integrated so a PR that breaks a model's `not_null` or `relationships` test fails before merge, not after a scheduled production run.

**Alerting integration** — quality-check results should route through the same on-call/paging infrastructure as any other production incident (PagerDuty, Opsgenie), with the tiering discussed above (page vs. digest) as a first-class configuration, not an afterthought bolted on once alert fatigue has already set in.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| A dashboard number is wrong for weeks before anyone notices | No freshness/volume check on the table at all, only "did the job finish" monitoring | Add freshness + volume checks as the first, cheapest quality gate on every production table |
| On-call mutes the data-quality Slack channel | Every check failure pages regardless of business impact (alert fatigue) | Tier alerts: page only on checks tied to real business impact, route the rest to a digest |
| A schema change breaks three downstream dashboards simultaneously | No data contract; producer shipped a breaking change with no consumer-side check in CI | Enforce a data contract in the producer's CI; fail the producer's build, not the consumer's pipeline |
| A quality check catches a bad row, but the row already fed a materialized dashboard | Validation happens in-warehouse, after the bad row has already propagated (fail-quiet) | Move validation earlier — at ingestion — for anything where propagation cost is high |
| Diagnosing a wrong number takes a full afternoon of manually tracing DAGs | No lineage tooling; tracing dependencies is manual and depends on institutional memory | Instrument OpenLineage across Spark/Airflow/dbt, query the lineage graph instead of grepping pipeline code |
| A quarantine table grows unboundedly with nobody looking at it | Bad rows are quarantined but nothing alerts on quarantine volume | Alert on quarantine-table volume crossing a threshold, treat sustained growth as its own incident |
| A "new column added" schema-drift alert fires every time a legitimate, already-approved change ships | Schema checks can't distinguish expected evolution from a real problem | Version the contract; approved additive changes bump a documented schema version instead of tripping a generic drift alert |

---

## Tradeoffs & when NOT to use it

- **Do not validate everything at every layer.** Duplicating the same check in ingestion, in a dbt model, and in a BI semantic layer triples the maintenance burden for no additional protection once the earliest gate already catches the case; decide deliberately which gate owns which check.
- **Do not circuit-break a pipeline for a check that doesn't actually justify blocking everyone.** A minor, cosmetic schema drift on a rarely-used column shouldn't halt a revenue-critical pipeline; reserve circuit-breaking for failures where partially-wrong data is genuinely worse than stale data.
- **Do not adopt Great Expectations as your only tool if continuous production monitoring is the actual need.** GX is triggered by a pipeline run; if nothing runs, nothing checks. A table that stops being updated entirely needs a scheduled, standalone observability tool (Soda, or a simple freshness cron) that checks independent of any pipeline execution.
- **Do not build a data contract enforcement system before you have more than one or two real downstream consumers of a dataset.** The overhead of schema registries and CI-gated breaking-change detection is worth it once a schema change can quietly break someone else's pipeline; for a single-consumer internal table, it's process overhead with no payoff yet.
- **Do not treat 100% test coverage of every column as the goal.** Freshness and volume checks catch the majority of real incidents at a fraction of the cost of exhaustive per-column distribution checks; prioritize coverage on business-critical tables and the cheap, high-signal dimension groups first.

---

## Interview questions

### Q1 — What are the four dimension groups of data quality, and which two catch the most real incidents?
**Testing:** baseline, but the "which catch the most" part filters for practical experience.
**Answer:** Freshness (is it recent enough), volume (is the row count/size plausible), schema (does the shape match), distribution (are the values themselves plausible). Freshness and volume catch the largest share of real incidents in practice because they detect "the pipeline silently stopped or partially ran" without needing any business-semantic knowledge of the data, which also makes them the cheapest checks to write.
**Follow-up trap:** *"If those two are cheapest and catch the most, why bother with schema and distribution checks at all?"* — freshness/volume catch *availability* failures (the pipeline broke), but a pipeline can run perfectly on schedule with a fully plausible row count while still producing semantically wrong values (a currency conversion bug, a join fan-out inflating revenue) — schema and distribution checks are what catch correctness failures that don't manifest as an obvious availability problem.

### Q2 — Where should a data contract be enforced, and why does enforcing it downstream fail at its purpose?
**Answer:** In the producer's CI/CD pipeline, before a breaking change can ship — a schema-registry-style check that fails the producer's build if a proposed change breaks the agreed contract. Enforcing it downstream (a consumer-side check that catches the break after the producer already shipped) means the breaking change has already landed and potentially already affected every consumer who processes data faster than the check runs; the contract's entire value is preventing the break, not detecting it after the fact.
**Follow-up trap:** *"What if the producer team doesn't want to run consumer-defined checks in their own CI?"* — this is the actual organizational hard part of data contracts, and it's why the pattern requires either strong internal platform mandates or the producer team owning the contract definition themselves (with consumer input on what they depend on) rather than consumers unilaterally imposing checks on a team that has no incentive to run them.

### Q3 — Compare dbt tests, Great Expectations, and Soda. When would you use each, concretely?
**Answer:** dbt tests live next to models and run at build time — best for SQL-expressible assertions checked as part of a `dbt build`, weak for anything outside a build run or requiring Python-level expressiveness. Great Expectations validates data at points dbt can't reach (raw ingestion, before anything is a dbt model), with more expressive Python-based checks and human-readable data docs, but it's triggered by a pipeline step, not continuously scheduled on its own. Soda runs scheduled, standalone checks against production tables with native trailing-window anomaly detection, best for continuous observability independent of any specific pipeline run.
**Follow-up trap:** *"Could you just use one of these for everything and simplify the stack?"* — technically yes, but you'd be fighting each tool's design center: forcing continuous monitoring through dbt tests means wiring your own scheduler around `dbt build` runs, and forcing build-time model validation through Soda means duplicating logic dbt already expresses more naturally in SQL next to the model. The three-tool pattern (dbt for build-time, GX for ingestion/critical-asset validation, Soda for continuous monitoring) reflects three genuinely different validation moments, not redundant overlap.

### Q4 — Explain "fail-fast beats fail-quiet" with a concrete cost argument.
**Answer:** The cost of a bad row grows with every downstream hop it travels before being caught. Caught at ingestion, it's one quarantined record with no cleanup needed elsewhere. Caught three joins and a materialized dashboard later, it requires identifying every downstream artifact the bad row touched, correcting or invalidating each one, and possibly explaining to a stakeholder why a number they already reported externally was wrong. Fail-fast (reject or quarantine at the earliest gate) trades a small, bounded, immediate cost for avoiding an unbounded, delayed one.
**Follow-up trap:** *"Isn't circuit-breaking at ingestion riskier — now the whole pipeline is down instead of just one bad row?"* — that's exactly why circuit-breaking and quarantining are different tools for different situations: circuit-break when partially-wrong data is worse than stale-but-correct data (financial reporting), quarantine when a small bad-row rate is expected and blocking the whole pipeline over it causes more harm than letting good rows through while isolating the bad ones.

### Q5 — Your team pages on-call for every dbt test failure. Diagnose the eventual failure mode and fix it.
**Testing:** the anti-pattern named explicitly in this module.
**Answer:** Alert fatigue: most test failures are low-impact or already-understood (a benign known delay, an approved schema change tripping a generic drift check), and paging on all of them regardless of severity trains on-call to eventually mute the channel. Once muted, the one alert that represents a real incident fires into silence, and the quality system provides the appearance of coverage with none of the actual protection. Fix: tier alerts explicitly — page only on checks tied to genuine business impact, route everything else to a digest a human reviews on their own schedule, and periodically prune checks that have never once caught a real problem.
**Follow-up trap:** *"How do you decide what counts as 'genuine business impact' without just re-creating the same problem with extra steps?"* — tie severity to the downstream consumer, not the check itself: a freshness check on a table feeding a regulatory filing or revenue dashboard pages; the same check on an internal experimentation table doesn't. The tiering decision belongs to whoever owns the downstream consequence, reviewed periodically, not left as a one-time default at check-creation time.

### Q6 — What incident does column-level lineage specifically shorten, versus table-level lineage?
**Answer:** Table-level lineage tells you table A feeds table B; it doesn't tell you *which columns* in B actually depend on which columns in A, so a stakeholder reporting "the revenue number looks wrong" still requires manually reading transformation logic to find which specific upstream fields matter. Column-level lineage answers that directly — "gold.revenue derives from silver.unit_price and silver.quantity via this transformation" — letting you jump straight to checking whether either of those specific upstream columns changed recently, cutting diagnosis from potentially hours of code reading to a lineage-graph query.
**Follow-up trap:** *"Is column-level lineage available everywhere, or does it depend on the engine?"* — it depends on integration maturity; OpenLineage's column-level support is solid for Spark (on by default), and extends to Airflow and dbt integrations, but coverage isn't uniform across every possible engine/connector, so a real answer includes checking whether your specific stack's OpenLineage integration actually emits column-level events before relying on it during an incident.

### Q7 — Design the quality gates for a pipeline that loads third-party vendor data feeding a public-facing revenue dashboard.
**Testing:** synthesizing contract, dimension checks, and severity tiering into one design.
**Answer:** At ingestion: schema check (reject if the vendor's feed doesn't match the agreed contract shape) and freshness/volume checks (page if the feed is more than, say, 2 hours late or row count is outside a ±20% band of trailing average) — this is a circuit-breaking gate given the public-facing revenue impact. In-warehouse: a distribution check on the transformed data (e.g., total revenue shouldn't deviate more than a few standard deviations from a 30-day baseline without a known cause) routed to a digest unless it crosses a much larger threshold that would itself page. Lineage instrumented end to end so any future incident can be traced to the specific upstream field in minutes.
**Follow-up trap:** *"What if the vendor's feed is late by exactly the SLA threshold once a month due to a known billing cycle?"* — a static threshold alone produces a false-positive page every month; the fix is either encoding the known cyclical exception explicitly (don't page for this specific, documented pattern) or using an anomaly-detection check (Soda's trailing-window anomaly score) that learns the cyclical pattern rather than a fixed threshold that can't distinguish "known monthly pattern" from "genuinely broken."

### Q8 — What's the actual difference between circuit-breaking a pipeline and quarantining bad rows, and how do you decide which a given check should do?
**Answer:** Circuit-breaking stops the entire run; nothing downstream updates until the failure is resolved — appropriate when partially-wrong or stale-but-untouched data is safer than partially-updated data (financial close, regulatory reporting). Quarantining routes only the specific bad rows to a dead-letter table and lets the rest of the pipeline complete — appropriate for high-volume pipelines with an expected, bounded bad-row rate where blocking everyone over a known failure mode causes more harm (stale data cluster-wide) than isolating the bad rows and moving on. The decision is made per check based on the blast radius and business cost of each failure mode, not as a single global policy.
**Follow-up trap:** *"What happens if the quarantine table itself is never reviewed?"* — it becomes a second, silent incident: bad data accumulates unnoticed, and if the quarantine rate creeps up over time (a slowly worsening upstream bug), nobody catches it because "quarantine, not fail" was treated as the end of the story rather than requiring its own volume-based alert.

### Q9 — A dbt model's `not_null` test starts failing after a source system migration. Walk through your triage.
**Answer:** First check whether this is a real data problem or a contract violation from the producer's migration (did the source schema actually change, e.g. a column that used to be always-populated is now nullable post-migration). If it's the latter, this is exactly what a data contract enforced in the producer's CI should have caught before the migration shipped — its absence is the root cause, not just the null values themselves. Immediate triage: quantify the null rate (is it 0.1% or 40%) to decide urgency, check lineage/recent changes on the source table, and decide circuit-break vs. quarantine based on how the nulls propagate downstream.
**Follow-up trap:** *"The source team says it's an intentional change and 'not our problem.'* — this is the organizational failure a data contract is meant to prevent: if there's no agreed contract, "intentional" from the producer's side and "breaking" from the consumer's side are both true simultaneously with no shared source of truth to resolve it. The fix going forward is establishing the contract (and its enforcement point) retroactively, not just patching this one test.

### Q10 — Why do "shift validation left" and "validate where you use it" represent a genuine, live disagreement rather than one being simply correct?
**Answer:** Shift-left (validate at ingestion) minimizes the blast radius of bad data by catching it before it's queryable anywhere, but duplicating the same validation logic at every ingestion point across many sources doesn't scale organizationally — every team maintains its own copy of similar checks. Validate-where-you-use-it (centralize checks at the semantic/BI layer or key transformation points) reduces duplication and keeps checks close to where business logic is defined, but means bad data can sit in raw/staging tables for a while before anything catches it, and multiple consumers might independently discover the same upstream problem before it's fixed centrally. Most mature teams do both at different tiers: cheap, universal checks (freshness, basic schema) at ingestion; deeper, business-semantic checks centralized further downstream.
**Follow-up trap:** *"So is there a wrong answer here?"* — the wrong answer is doing neither, or doing all validation in exactly one place regardless of which trade-off actually fits a given check's cost and blast radius; there's a real, unresolved tension here, not a settled best practice, and naming that instead of picking a side unprompted is the stronger interview answer.

---

## Red flags that fail you

- Describing data quality as "we added some dbt tests" with no mention of enforcement point, severity tiering, or continuous monitoring.
- Proposing to page on-call for every check failure with no tiering.
- Not knowing the difference between circuit-breaking and quarantining, or applying one universally.
- Treating data contracts as a downstream/consumer-side concern rather than a producer-CI enforcement point.
- Claiming 100% column-level test coverage is the goal rather than prioritizing freshness/volume first.
- Not recognizing alert fatigue as a real, common failure mode of quality systems, only as a hypothetical.

---

## Cheat card

```
FOUR DIMENSIONS   freshness (recent enough?) · volume (row count in range?)
                  schema (shape/types as expected?) · distribution (values
                  plausible?). Freshness+volume catch MOST real incidents,
                  cheapest to write, need no business-semantic knowledge.

DATA CONTRACT     schema + semantics + SLA agreement, producer<->consumer.
                  ENFORCE in producer's CI, before ship — enforcing
                  downstream means the break already landed.

TOOLS   dbt tests: build-time, SQL-expressible, next to the model
        Great Expectations (GX Core): Python-native, validates raw/ingest
          data dbt can't reach, expressive custom checks, triggered by a
          pipeline step (not self-scheduled)
        Soda (SodaCL): YAML, SCHEDULED continuous observability, native
          trailing-window anomaly detection
        PATTERN: dbt for transform, GX for ingest/critical assets,
          Soda for continuous prod monitoring — not one tool wins

FAIL-FAST > FAIL-QUIET   cost of a bad row grows with every downstream hop.
        Caught at ingest = 1 quarantine record. Caught after a materialized
        dashboard = cleanup + stakeholder apology + compliance question.

CIRCUIT-BREAK vs QUARANTINE
        circuit-break: stop everything, page — when wrong data > stale data
          (financial close, regulatory)
        quarantine: isolate bad rows, let good ones through — high-volume,
          expected bounded bad-rate, blocking everyone costs more
        ALERT on quarantine VOLUME crossing a threshold — an unreviewed
          quarantine table is a second silent incident.

LINEAGE   OpenLineage (open standard, Spark/Airflow/dbt) + Marquez
          (reference impl). Column-level lineage: table A feeds B ->
          "gold.revenue derives from silver.unit_price, silver.qty".
          Shortens diagnosis from hours of code-reading to a graph query.

ALERT FATIGUE   page-everything -> most alerts are noise -> channel gets
        muted -> the ONE real alert fires into silence -> quality system
        has negative value (appearance of coverage, none of the protection)
        FIX: tier by business impact of the DOWNSTREAM CONSUMER, page rarely,
        digest the rest, prune checks that never caught anything real.

WHEN NOT TO   don't duplicate the same check at every layer · don't
        circuit-break for cosmetic drift · GX alone != continuous
        monitoring (needs a trigger) · don't build contract enforcement
        for a single-consumer internal table
```

## Sources

- [Great Expectations: Data Testing Framework — Conduktor](https://www.conduktor.io/glossary/great-expectations-data-testing-framework) — accessed 2026-08-01
- [GX Core overview — Great Expectations](https://docs.greatexpectations.io/docs/core/introduction/gx_overview/) — accessed 2026-08-01
- [Data Quality Frameworks: Great Expectations vs dbt Tests vs Soda Core — PipeCode](https://pipecode.ai/blogs/data-quality-frameworks-great-expectations-vs-dbt-tests-vs-soda-core) — accessed 2026-08-01
- [Trying Out the New Column Lineage Feature — Marquez Project](https://marquezproject.ai/blog/column-lineage-demo/) — accessed 2026-08-01
- [GitHub - OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
