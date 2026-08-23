# Airflow / Dagster / Prefect

> **Track:** T09 MLOps / LLMOps · **Time:** 2.5h · **Prereqs:** none
> **Module id:** `T09-orchestration` · **Tags:** mlops,orchestration,airflow,dagster,prefect,critical

## The 30-second version

Airflow, Dagster, and Prefect encode three different mental models of what you're orchestrating, and that difference — not raw feature count — is what should drive the choice. Airflow (Airbnb, 2015, the default since) orchestrates **tasks in a DAG**: you define a graph of operators and Airflow schedules and runs them, with backfill historically treated as a second-class, CLI-driven operation until Airflow 3 (GA 2025) finally moved backfills into the scheduler itself for real scalability and diagnostics, and added DAG versioning so an in-flight run completes against the DAG version it started with even if a new version is deployed mid-run. Dagster orchestrates **software-defined assets** — the object produced (a table, a file, a model) is the primary abstraction, not the task that produced it — which gives it a structural advantage classic Airflow doesn't have natively: because the system understands data lineage between assets, it can skip re-materializing a downstream asset if nothing upstream actually changed, and it ships native time-partitioned assets with one-click backfills as a first-class UI operation, not a CLI escape hatch. Prefect orchestrates **flows** — plain Python functions decorated into a DAG implicitly at runtime rather than declared upfront — favoring dynamic, code-first pipelines (conditional branching, loops, runtime-determined task counts) over Airflow's more rigid, statically-declared-DAG model, with a hybrid execution architecture (Prefect Cloud/server for orchestration metadata, your own infrastructure actually running the work) that's become one of its more distinct positioning points against Airflow's traditionally more monolithic deployment model. The honest recommendation: pick Airflow when you already have platform engineering capacity and need the widest operator ecosystem and battle-tested maturity; pick Dagster when asset lineage and selective re-materialization are central to how your pipelines actually behave (heavy dbt integration, ML feature pipelines); pick Prefect when your pipelines are genuinely dynamic/Python-native and a rigid upfront DAG declaration is fighting your actual control flow.

## Why this gets asked

The interviewer has run a nightly ETL or training pipeline that failed at 3am, and the recovery experience — how easy backfilling a specific date range was, whether retries preserved partial progress, whether the failure was diagnosable from the UI or required digging through worker logs — is exactly what separates orchestrators in practice, far more than a feature-matrix comparison would suggest. They want to know whether you've actually operated one of these at nontrivial scale (hundreds of DAGs, real backfill pain, a scheduler that occasionally falls behind under load) rather than just used one in a tutorial, and whether you can reason about *why* a given orchestrator's core abstraction (task, asset, or flow) shapes what's easy and what's painful, rather than reciting a feature list.

---

## Lineage: past → present → future

**What came before.** Before dedicated workflow orchestrators, scheduled data/ML pipelines ran as cron jobs chaining shell scripts, with no shared understanding of task dependencies, no automatic retry logic, no central visibility into what ran, what failed, or why, and manual, error-prone re-running of failed steps — a specific, common pain being a multi-step pipeline where step 4 failing meant manually figuring out which of steps 1-3 needed to be re-run and in what order, entirely from memory or scattered logs. Airbnb built and open-sourced Airflow in 2015 specifically to solve this: a DAG-based scheduler with a UI showing task status, dependency graphs, and retry state, becoming the default choice essentially by being first, most documented, and most battle-tested at scale.

**Where it stands now.** Airflow remains the most deployed and most operationally proven option, with the widest ecosystem of pre-built operators (integrations for essentially every cloud service and data tool) and the deepest bench of engineers who already know it — a real, non-trivial advantage when hiring and onboarding matter. Airflow 3 (GA 2025) was described by the Airflow project itself as the biggest release in the project's history, finally addressing two long-standing, widely-requested gaps: **backfills moved into the scheduler** itself (rather than remaining a CLI-only, second-class operation), giving real scalability and diagnostics for a long-standing pain point especially relevant to ML/ETL re-processing use cases, and **DAG versioning**, where an in-flight DAG run completes against the exact DAG version (code, task structure, logs) it started with even if a newer version gets deployed mid-run — closing a real correctness gap where a mid-flight deploy could previously cause a running pipeline to behave inconsistently [Apache Airflow 3 is Generally Available — Airflow blog](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/) — accessed 2026-08-03. Dagster's asset-centric model (software-defined assets as the primary abstraction, not tasks) is its clearest structural differentiator: because the system natively understands the lineage between assets, it can skip re-materializing a downstream asset when nothing upstream has actually changed — a capability classic Airflow doesn't have built into its core task-DAG model — and Dagster treats dbt models as first-class assets sharing one lineage graph with Python-based pipelines, a genuinely different integration depth than treating dbt as just another operator to invoke. Prefect's differentiation is code-first dynamism (flows are plain Python functions, with the DAG structure emerging implicitly at runtime rather than declared upfront) and a hybrid execution architecture separating orchestration metadata (Prefect Cloud/server) from where the work actually executes (your own infrastructure, polled by workers) — a meaningfully different operational model from Airflow's traditionally more monolithic scheduler-plus-workers deployment. The live, genuinely unresolved disagreement across all three: how much of "the scheduler is falling behind" or "backfills are painful" is a fixable operational maturity problem (correct sizing, correct DAG design) versus an inherent architectural limitation of a given orchestrator — practitioners in each camp will defend their tool's scalability with real production examples, and the honest answer is that scale problems in all three are more often caused by poor DAG/pipeline design (too many tiny tasks, unbounded fan-out, tasks that should be sub-tasks of a single larger unit of work) than by a fundamental ceiling in the orchestrator itself.

**Where it's heading.** High confidence: DAG-versioning-style correctness guarantees (an in-flight run isn't silently affected by a mid-run deploy) become expected baseline behavior across all three orchestrators, not just Airflow's differentiator, as the industry converges on treating this as an obvious correctness requirement once named clearly. Medium confidence: asset-centric, lineage-aware execution (Dagster's core bet) keeps gaining ground as data lineage and selective re-computation become more valuable with growing pipeline complexity and cost-consciousness around unnecessary recomputation — this is a real, current trend, though Airflow's dataset-aware scheduling (a lighter-weight, bolted-on approximation of asset awareness) is a partial response rather than a full architectural shift to asset-centricity. Speculative: tighter native integration between orchestration and the LLM/agentic pipeline space (orchestrating multi-step LLM workflows, evaluation pipelines, and RAG ingestion pipelines with the same rigor as classical ETL) is an emerging use case for all three tools, but no orchestrator has yet established a clearly dominant, purpose-built position specifically for LLM pipeline orchestration as of 2026.

---

## Mental model

```
THREE ABSTRACTIONS FOR THE "SAME" PROBLEM

  AIRFLOW: task-centric, DAG declared upfront
    task_A --> task_B --> task_C
    (operators, explicit dependency edges, DAG structure fixed at
     definition time -- even "dynamic task mapping" expands a
     KNOWN structure, it doesn't emerge from arbitrary runtime logic)

  DAGSTER: asset-centric, the OBJECT is primary, not the step
    [raw_table] --> [cleaned_table] --> [feature_table] --> [model]
    (each node is a MATERIALIZED ASSET with known lineage; if
     [raw_table] hasn't changed, [cleaned_table] can be SKIPPED --
     selective re-materialization Airflow's task model doesn't have
     natively)

  PREFECT: flow-centric, plain Python, structure emerges at RUNTIME
    @flow
    def my_pipeline():
        for item in dynamic_list():      # <- list length unknown until runtime
            if condition(item):           # <- branching decided at runtime
                process(item)
    (DAG structure is implicit, discovered as the function actually
     executes -- genuinely dynamic control flow Airflow's static
     DAG declaration fights against)

BACKFILL, THE REAL DIFFERENTIATOR IN PRACTICE
  Airflow (pre-3.0): CLI-only, second-class, no scheduler integration
  Airflow 3 (2025+): backfills run WITHIN the scheduler -- real
    scalability + diagnostics, no more separate backfill DAG hacks
  Dagster: native time-partitioned assets, ONE-CLICK backfill in the UI
  Prefect: parametrized/tagged re-runs via deployments, less of a
    first-class "backfill a date range" primitive than Dagster's

DAG VERSIONING (Airflow 3): an in-flight run completes against the
  DAG version it STARTED with, even if a new version deploys mid-run --
  closes a real correctness gap (previously: a mid-flight deploy could
  make a running pipeline behave inconsistently against mixed code).
```

---

## How it actually works

### Airflow: scheduler internals, and what changed in Airflow 3

Airflow's scheduler parses DAG files (Python) on a polling interval, computes which task instances are eligible to run based on the DAG's declared dependencies and any external triggers (a `Dataset`/data-aware trigger, a sensor, a deferrable task waiting on an external condition), and hands eligible tasks to an executor (Celery, Kubernetes, or local) for actual execution. DAG parsing itself is a real, sometimes-underestimated operational cost: a large number of DAG files, or DAGs with heavy top-level imports/logic executed at parse time (not inside task functions), directly slows down how quickly the scheduler can determine what's eligible to run — a common, checkable performance mistake is putting expensive computation at DAG-file module level instead of inside a task's callable, which re-executes on every scheduler parse cycle, not just at actual task run time.

**Backfill, historically Airflow's weakest point**: prior to Airflow 3, backfilling a historical date range meant either a separate CLI invocation (`airflow dags backfill`) disconnected from the scheduler's normal operation, or hand-rolled patterns (a separate "backfill DAG" duplicating logic) — genuinely painful for ML/ETL use cases needing to reprocess a range after a bug fix or schema change. Airflow 3 (GA 2025) moved backfills to run **within the scheduler itself**, giving proper scalability and diagnostics rather than treating backfill as a bolted-on CLI operation [Apache Airflow 3 is Generally Available — Airflow blog](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/) — accessed 2026-08-03.

**DAG versioning (Airflow 3)**: a DAG run now executes to completion against the exact DAG version (code, task structure) it started with, even if a new version gets uploaded while that run is in flight — the Airflow UI associates every DAG run with its specific version, including task structure, code, and logs [Airflow 3.0: DAG versioning, multi-language support and native AI/ML workflows — The Data Canal](https://thedatacanal.substack.com/p/airflow-30-dag-versioning-multi-language) — accessed 2026-08-03. This closes a real correctness gap: previously, a mid-flight deploy while a long-running DAG was executing could cause inconsistent behavior as the scheduler picked up new task definitions partway through an already-running instance.

**A concrete measured performance improvement**: rendered task instance field cleanup for DAGs with many mapped tasks is roughly 42x faster in recent Airflow releases — a specific, non-trivial number worth knowing if asked about dynamic task mapping at scale [Release Notes — Airflow 3.3.0](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html) — accessed 2026-08-03.

```python
# untested sketch — Airflow 3-style DAG with dataset-aware scheduling and dynamic task mapping
from airflow.sdk import dag, task, Asset

raw_data = Asset("s3://bucket/raw/orders")

@dag(schedule=[raw_data], catchup=False)
def process_orders():
    @task
    def list_partitions() -> list[str]:
        return get_unprocessed_partitions()   # length known only at runtime

    @task
    def process_partition(partition: str) -> dict:
        return run_etl(partition)

    process_partition.expand(partition=list_partitions())   # dynamic task mapping,
    # expands to N task instances at RUN time based on the list's actual length --
    # still a STATICALLY DECLARED structure (an "expand" operation), not arbitrary
    # runtime control flow the way a Prefect flow's plain Python loop would be

process_orders()
```

### Dagster: assets as the primary abstraction, and why selective re-materialization matters

Dagster's central bet is that **the artifact produced** (a table, file, ML feature set, model) should be the unit orchestration reasons about, not the step that produces it — a `@asset`-decorated function declares what it produces and what upstream assets it depends on, and Dagster builds the full lineage graph across all declared assets automatically. The concrete payoff: because Dagster knows the lineage graph and can track whether an upstream asset's data has actually changed since a downstream asset was last materialized, it can **skip re-materializing a downstream asset entirely** when nothing upstream changed — a capability that requires bolting on custom logic in Airflow's task-centric model (checking upstream state manually inside a task) but is native to Dagster's asset model [Comparing Workflow Architectures: Prefect vs. Dagster vs. Airflow — ThinhDA](https://thinhdanggroup.github.io/airflow-prefect-dagster/) — accessed 2026-08-03.

```python
# untested sketch — Dagster asset lineage with native backfill support
from dagster import asset, DailyPartitionsDefinition

daily_partitions = DailyPartitionsDefinition(start_date="2026-01-01")

@asset(partitions_def=daily_partitions)
def raw_orders(context) -> None:
    load_raw_orders_for_date(context.partition_key)

@asset(partitions_def=daily_partitions)
def cleaned_orders(context, raw_orders) -> None:
    # Dagster tracks that this depends on raw_orders for the SAME partition;
    # if raw_orders for a given date hasn't changed, this can be skipped
    clean_and_write(context.partition_key)

@asset(partitions_def=daily_partitions)
def order_features(context, cleaned_orders) -> None:
    compute_features(context.partition_key)

# backfilling a date range: select the partition range in the Dagster UI,
# click "materialize" -- native, one-click, no separate CLI invocation
# or hand-rolled backfill DAG required
```

Dagster's dbt integration treats dbt models as first-class software-defined assets sharing the same lineage graph as Python-based assets — a meaningfully deeper integration than invoking `dbt run` as an opaque operator step the way Airflow typically would, because Dagster can reason about dependencies *between* individual dbt models and Python-computed assets in one unified graph, not two separate systems bridged by a single task boundary.

### Prefect: dynamic flows, and the hybrid execution model

Prefect's flows are plain Python functions decorated with `@flow`, and tasks within them are plain functions decorated with `@task` — the actual DAG structure is discovered as the function executes, not declared upfront as a fixed graph. This matters concretely for genuinely dynamic pipelines: a loop whose iteration count depends on a runtime API call's result, conditional branching based on a value only known at execution time, or recursive/nested flow calls are all natural in Prefect's model and require workarounds (dynamic task mapping with `expand()`, or splitting into multiple DAGs triggered conditionally) in Airflow's more statically-declared model.

```python
# untested sketch — genuinely dynamic control flow, natural in Prefect
from prefect import flow, task

@task
def fetch_batch_list() -> list[str]:
    return call_external_api_for_batches()   # length unknown until this RUNS

@task
def process_batch(batch_id: str) -> dict:
    return run_processing(batch_id)

@flow
def dynamic_pipeline():
    batches = fetch_batch_list()
    results = []
    for batch_id in batches:            # plain Python loop, real runtime branching
        if should_process(batch_id):     # a runtime decision, not a pre-declared edge
            results.append(process_batch(batch_id))
    return results
```

**Hybrid execution**: Prefect Cloud (or a self-hosted Prefect server) holds orchestration state and scheduling metadata, while the actual work executes on infrastructure you control, with workers polling for scheduled work — a meaningfully different operational split from Airflow's traditionally more monolithic scheduler-plus-worker-fleet deployment model, and one Prefect has leaned into as a distinct selling point (orchestration-as-a-service without giving up control of where code actually runs, or where sensitive data is actually processed).

### Failure and retry semantics across the three

All three support per-task retry with configurable backoff, but the granularity and default behavior differ in ways worth knowing precisely: Airflow's retry is task-instance-scoped with configurable `retries`/`retry_delay`, and a failed task's *downstream* tasks are held (not run) until the failed task either succeeds on retry or is manually marked as a different terminal state — the DAG run as a whole reflects the failure until resolved. Dagster's asset-based retry can be scoped at the asset level, and because assets carry explicit data lineage, a retry of a failed asset materialization can be reasoned about in terms of exactly which downstream assets become stale and need re-materialization as a consequence, not just which tasks are blocked. Prefect's flow/task retries are configured similarly to Airflow's per-task model, but because flow structure is dynamic, a retry of a sub-flow or task within a larger dynamically-structured flow needs the flow's own state-tracking to correctly resume only the failed portion rather than restarting the entire dynamic flow from scratch — Prefect's persistent flow run state is what makes this resumability practical rather than accidental.

### Kedro and SageMaker Pipelines: the two the JDs actually name

Two more names show up repeatedly in MLOps job descriptions, and neither is trying to be a general-purpose scheduler — which is exactly why they confuse Airflow-vs-Dagster-style comparisons if you force them onto that axis.

**Kedro** (QuantumBlack/McKinsey, open-sourced 2020) is a data-engineering-first *pipeline framework*, not an orchestrator: you decompose work into pure Python functions called **nodes**, wire them into a **pipeline** whose dependency graph Kedro resolves and executes in order, and declare every input/output in a **Data Catalog** — a YAML-configured registry mapping names to datasets (a Parquet file on S3, a SQL table, an MLflow artifact) so pipeline code never hardcodes paths or credentials, and swapping a local CSV for a partitioned warehouse table is a config change, not a refactor. **Modular pipelines** namespace a subgraph's inputs and outputs so the same cleaning pipeline can be instantiated many times against different sources. Data teams adopt Kedro over "Airflow for everything" because Airflow answers *when does this run and did it fail*, while Kedro answers *how is this code structured, decoupled from I/O, and testable* — unit-testing a Kedro node is calling a function with fixture data; exercising an Airflow task realistically means running it inside Airflow. The dominant production pattern composes them: Kedro owns structure, an orchestrator (Airflow, Prefect, Kubeflow) triggers `kedro run` per stage — layers owning different concerns, not competitors.

**SageMaker Pipelines** is the managed-AWS answer: pipelines are declared in SageMaker's own JSON DSL — a directed graph of steps (`TrainingStep`, `ProcessingStep`, `ConditionStep`, `CallbackStep`) wired through property references so one step's output feeds another's input — executed on SageMaker infrastructure, with first-class **model registry** integration so a registered `ModelPackage` version and its approval status flow directly into deployment automation, and condition steps implement branch-on-metric gates (deploy only if accuracy clears the threshold) without leaving the service. The lock-in is structural, not contractual: the definition is SageMaker's schema and execution is SageMaker's infra, so nothing ports to an Airflow or Kedro setup elsewhere — acceptable in an AWS-end-to-end shop, a real liability under multi-cloud or on-prem constraints. Decision guidance: a JD saying "SageMaker" expects SageMaker Pipelines fluency; one saying "data platform" expects the Kedro/Dagster asset-and-catalog framing; this module's Airflow/Dagster/Prefect decision rule sits on top either way.

---

## Build it from scratch

A minimal illustration of the *same* daily ETL pipeline expressed in each of the three mental models, to make the abstraction difference concrete rather than abstract:

```python
# untested sketch — AIRFLOW: task-centric, DAG structure declared upfront
from airflow.sdk import dag, task

@dag(schedule="@daily", catchup=True)   # catchup=True: Airflow WILL backfill
def daily_etl():                          # missed scheduled runs automatically
    @task
    def extract(): return load_raw_data()

    @task
    def transform(data): return clean(data)

    @task
    def load(data): write_to_warehouse(data)

    load(transform(extract()))

daily_etl()
```

```python
# untested sketch — DAGSTER: asset-centric, lineage-aware
from dagster import asset, DailyPartitionsDefinition

partitions = DailyPartitionsDefinition(start_date="2026-01-01")

@asset(partitions_def=partitions)
def raw_data(context): return load_raw_data(context.partition_key)

@asset(partitions_def=partitions)
def cleaned_data(context, raw_data): return clean(raw_data)
# Dagster can SKIP this materialization if raw_data for this partition is unchanged

@asset(partitions_def=partitions)
def warehouse_table(context, cleaned_data): write_to_warehouse(cleaned_data)
```

```python
# untested sketch — PREFECT: flow-centric, dynamic
from prefect import flow, task
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule

@task
def extract(): return load_raw_data()

@task
def transform(data): return clean(data)

@task
def load(data): write_to_warehouse(data)

@flow
def daily_etl():
    data = extract()
    cleaned = transform(data)
    load(cleaned)

# scheduling attached to a DEPLOYMENT, separate from the flow definition itself --
# reflects Prefect's split between "what the flow does" and "when/where it runs"
```

The line worth internalizing: Airflow's version needs the *DAG structure itself* to be fixed at definition time (even dynamic task mapping expands a known operation); Dagster's version is written in terms of *what gets produced*, with lineage and skip-if-unchanged behavior implied by the asset graph; Prefect's version is the least structurally different from writing a plain Python script, with orchestration concerns (scheduling, retries) layered on via decorators rather than requiring a fundamentally different way of expressing the pipeline's logic.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Airflow scheduler falls further behind as DAG count grows, task pickup latency increases | DAG parsing cost scaling with DAG file count/complexity, especially expensive top-level (module-level) code executed on every scheduler parse cycle, not just at task run time | Move expensive logic inside task callables, not DAG-file module level; consider splitting an overloaded scheduler across multiple parsing processes; audit DAG file count/complexity as a first-class operational metric |
| Backfilling a historical date range after a bug fix takes disproportionate manual effort on Airflow | Pre-Airflow-3 backfill was CLI-only, disconnected from normal scheduler operation, or required a hand-rolled separate "backfill DAG" | Upgrade to Airflow 3+ for scheduler-integrated backfills, or in the interim, design DAGs with idempotent, partition-parameterized tasks that a CLI backfill invocation can safely re-run |
| A running Airflow DAG behaves inconsistently mid-execution after a deploy | Pre-Airflow-3, a mid-flight code deploy could affect an in-progress DAG run's behavior since there was no DAG versioning tying a run to the exact code version it started with | Upgrade to Airflow 3+ for DAG versioning, which pins an in-flight run to its starting version through completion |
| A Dagster pipeline re-materializes a downstream asset unnecessarily, wasting compute | Asset dependency declared too coarsely (depends on the whole upstream asset rather than the specific partition/slice actually needed), or the freshness/staleness policy isn't configured to actually skip when unchanged | Scope asset dependencies to the correct partition granularity; configure declarative automation/freshness policies explicitly rather than assuming skip-if-unchanged is automatic with no configuration |
| A Prefect flow with deeply nested dynamic loops becomes hard to debug when a failure occurs deep inside runtime-determined control flow | Dynamic, code-first flexibility traded away the static, visualizable DAG structure that makes failure location obvious at a glance in Airflow/Dagster's UI | Add explicit task-level naming/tagging and rely on Prefect's flow run state/logs rather than expecting a static graph visualization to make the failure location obvious; consider whether the dynamism is actually necessary or whether a more structured (less dynamic) flow would be easier to operate |
| A cross-team platform mandate picks one orchestrator for every team's pipeline, and a heavily dbt-centric analytics team is unhappy with the fit | Standardizing on Airflow (task-centric) for a team whose actual workload is asset/lineage-centric (dbt models) loses Dagster's native first-class dbt-asset integration | Evaluate per-workload fit rather than a blanket mandate; a shared platform standard can still allow a documented exception for workloads structurally better suited to a different tool, with the tradeoff made explicit |
| Team is unsure whether a scaling problem is the orchestrator's ceiling or their own DAG/pipeline design | Conflating "this orchestrator can't scale" with "our specific pipeline design (too many tiny tasks, unbounded fan-out) doesn't scale well on any orchestrator" | Audit task granularity and fan-out patterns before concluding the orchestrator itself is the bottleneck; all three tools have real production deployments at far larger scale than most teams' actual workload, so a scaling ceiling is more often a design problem than a tool limitation |

---

## Tradeoffs & when NOT to use it

- **Don't pick Airflow for a genuinely dynamic, code-first pipeline where the task graph structure isn't knowable until runtime.** Forcing Airflow's statically-declared DAG model onto real runtime dynamism means fighting the tool with dynamic task mapping workarounds or splitting logic across multiple conditionally-triggered DAGs — Prefect's model fits this shape more naturally.
- **Don't pick Dagster if your pipelines aren't meaningfully asset/lineage-shaped.** If your workload is genuinely a sequence of arbitrary operational tasks with no natural "artifact produced" framing, Dagster's asset-centric abstraction adds conceptual overhead without the selective-re-materialization payoff that justifies it.
- **Don't pick Prefect if you need the widest possible pre-built integration ecosystem and maximum hiring-pool familiarity.** Airflow's operator ecosystem and battle-tested maturity at scale remain real, non-trivial advantages that a smaller, newer platform's cleaner abstractions don't automatically outweigh, especially for a team needing to hire and onboard quickly.
- **Don't assume upgrading to Airflow 3 alone fixes a poorly-designed DAG's scaling problems.** Scheduler-integrated backfills and DAG versioning are real, meaningful improvements, but they don't fix a DAG with too many tiny tasks or unbounded dynamic fan-out — that's a design problem no orchestrator version bump solves.
- **Don't mandate one orchestrator platform-wide without accounting for genuinely different-shaped workloads across teams.** A heavily dbt-centric analytics team and a genuinely dynamic ML pipeline team may be legitimately better served by different tools; a blanket standardization mandate should make that tradeoff explicit rather than silently accepting a worse fit for the sake of uniformity.
- **Don't treat any of these three as solving orchestration problems that are actually data-quality or pipeline-design problems.** An orchestrator schedules and tracks execution; it doesn't fix a pipeline whose actual logic is fragile, non-idempotent, or poorly partitioned — those are the real root causes behind a large share of "the orchestrator can't handle our scale" complaints.

---

## Interview questions

### Q1 — What's the fundamental abstraction difference between Airflow, Dagster, and Prefect?
**Testing:** whether the candidate understands the conceptual difference, not just a feature list.
**Answer:** Airflow orchestrates tasks in a DAG declared upfront (even dynamic task mapping expands a known, statically-declared operation). Dagster orchestrates software-defined assets — the artifact produced (a table, file, model) is the primary unit, with lineage between assets tracked natively. Prefect orchestrates flows — plain Python functions where the DAG structure is discovered implicitly at runtime, supporting genuinely dynamic control flow (runtime-determined loops, conditional branching) that Airflow's static declaration model resists.
**Follow-up trap:** *"Could you build something resembling asset-aware skip-if-unchanged behavior in Airflow?"* — yes, by manually checking upstream state inside a task (querying a metadata table, comparing timestamps) before deciding whether to actually do work, but this is custom logic you build and maintain yourself, not a capability native to Airflow's task-DAG model the way it is to Dagster's asset graph.

### Q2 — Why was backfill historically Airflow's weakest point, and what changed in Airflow 3?
**Testing:** specific, current knowledge of a real, well-known pain point and its actual fix.
**Answer:** Pre-Airflow-3, backfilling a historical date range meant a CLI-only invocation (`airflow dags backfill`) disconnected from the scheduler's normal operation, or a hand-rolled separate "backfill DAG" duplicating logic — genuinely painful for ML/ETL re-processing after a bug fix. Airflow 3 (GA 2025) moved backfills to run within the scheduler itself, giving proper scalability and diagnostics as a first-class capability rather than a bolted-on CLI operation.
**Follow-up trap:** *"Does that make Airflow's backfill as good as Dagster's native one-click partition backfill?"* — closer, but Dagster's asset-partition model gives backfill a more natural, first-class UI experience tied directly to the asset lineage graph (select a partition range, materialize); Airflow's improvement is a major operational upgrade over its prior CLI-only state, but the two aren't identical in UX maturity even post-Airflow-3.

### Q3 — Explain DAG versioning in Airflow 3 and the specific correctness problem it solves.
**Testing:** whether the candidate can name the exact failure mode this feature fixes.
**Answer:** Prior to DAG versioning, a mid-flight code deploy while a DAG run was already in progress could cause the running instance to pick up new task definitions partway through, producing inconsistent behavior mixing old and new code within a single run. Airflow 3 pins a DAG run to the exact version (code, task structure) it started with, so it completes to completion against that version regardless of any deploy that happens while it's running, and the UI associates every run with its specific version for auditing.
**Follow-up trap:** *"What's the tradeoff of this pinning behavior?"* — a long-running DAG instance won't benefit from a bug fix deployed mid-run even if that fix would have helped it; the correctness guarantee (consistent behavior throughout a single run) is prioritized over the ability to hot-patch an in-flight run, which is the right tradeoff for reproducibility but worth naming explicitly as a real tradeoff, not a free win.

### Q4 — What specifically enables Dagster to skip re-materializing a downstream asset, and why can't classic Airflow do this natively?
**Testing:** the actual mechanism behind a headline Dagster feature.
**Answer:** Dagster's asset graph explicitly tracks lineage (which assets depend on which) and, with the right freshness/staleness policy configured, can determine whether an upstream asset's data has changed since a downstream asset was last materialized — skipping the downstream materialization entirely if nothing relevant changed. Airflow's task-centric model has no built-in concept of "the artifact this task produces" as a trackable, lineage-aware entity — a task either runs or doesn't based on scheduling/dependency logic, with no native mechanism for the scheduler itself to reason about whether the task's *output* actually needs to change.
**Follow-up trap:** *"Is this skip-if-unchanged behavior automatic just by using Dagster's asset decorator?"* — no, it requires explicitly configuring a freshness or staleness policy (or partition-based logic) — declaring an asset alone gives you the lineage graph, but the actual skip behavior needs to be configured, not assumed to happen by default.

### Q5 — When would Prefect's dynamic, code-first flow model be a liability rather than an advantage?
**Testing:** genuine "when NOT to use it" reasoning about Prefect specifically.
**Answer:** When operational debuggability matters more than expressive flexibility — a deeply nested, dynamically-branching flow trades away the static, at-a-glance-visualizable DAG structure that makes failure location obvious in Airflow's or Dagster's UI. A team that needs to hand off on-call debugging to engineers unfamiliar with a specific pipeline's runtime logic benefits from a more structured, statically-declared DAG they can visually trace, even at the cost of some pipeline flexibility.
**Follow-up trap:** *"Doesn't Prefect's UI show a visual graph too?"* — yes, but for a genuinely dynamic flow, that visualization reflects a specific past *execution's* discovered structure, not a fixed structure you can reason about ahead of time the way a statically-declared Airflow DAG or Dagster asset graph can be inspected before any run ever happens — the debugging experience differs meaningfully even with a visual UI present in all three.

### Q6 — A team's Airflow scheduler is falling increasingly behind as DAG count grows. Walk through your diagnosis before concluding "we need to migrate off Airflow."
**Testing:** whether the candidate defaults to blaming the tool versus auditing design first.
**Answer:** First check DAG parsing cost — whether expensive computation sits at DAG-file module level (re-executed on every scheduler parse cycle) rather than inside task callables (executed only at actual task run time), which is a common, fixable, non-architectural cause of scheduler slowdown. Then audit task granularity and fan-out patterns — an excessive number of very small tasks or unbounded dynamic fan-out can overwhelm any orchestrator's scheduling overhead regardless of which tool it is. Only after ruling out these design-level causes would a genuine architectural ceiling in Airflow itself be the remaining explanation, and even then, scaling the scheduler (multiple parsing processes, executor tuning) is a real lever before concluding a full migration is necessary.
**Follow-up trap:** *"Assume you've ruled out all of that and it's still falling behind at genuinely large scale. Does that change your orchestrator recommendation?"* — at that point, yes, it's reasonable to evaluate whether Dagster's asset-based selective re-materialization would reduce actual computed work (not just scheduling overhead) for a workload with significant redundant recomputation, or whether splitting DAG parsing/scheduling across dedicated infrastructure per team/domain would relieve the bottleneck without a full tool migration — a full migration is a large, risky undertaking that should be the last resort, not the first response to a scaling symptom.

### Q7 — Design a pipeline that needs to reprocess the last 90 days of data after discovering a transformation bug. Compare how this plays out in Airflow 3, Dagster, and Prefect.
**Testing:** applying the backfill mechanics concretely across all three.
**Answer:** Airflow 3: trigger a scheduler-managed backfill for the affected DAG across the 90-day date range, relying on idempotent, partition-parameterized tasks so each day's reprocessing is safe to re-run. Dagster: select the 90-day partition range for the affected asset(s) in the UI and materialize — native, one-click, with lineage ensuring any downstream assets depending on the corrected data are also flagged as needing re-materialization. Prefect: re-trigger the flow's deployment with the appropriate date-range parameters for each affected day (or a single parametrized run covering the range internally), relying on the flow's own logic to handle the range rather than a first-class "backfill" UI primitive as native as Dagster's.
**Follow-up trap:** *"Which of the three makes it easiest to confirm which downstream artifacts also need reprocessing as a consequence of the bug fix?"* — Dagster, specifically because of its native lineage graph — asset dependencies make it explicit and automatically traceable which downstream assets consumed the buggy data and therefore need re-materialization; Airflow and Prefect require the team to manually reason about (or separately track) which downstream DAGs/flows consumed the affected data, since neither has an equivalent built-in asset lineage graph.

### Q8 — Explain the retry/failure semantics difference between Airflow's task-level retries and Dagster's asset-level retries.
**Testing:** precise understanding of what "retry" means in each model.
**Answer:** Airflow retries a specific task instance according to its configured `retries`/`retry_delay`, and downstream tasks are held (not executed) until the failed task resolves — the failure's scope is the task, and its implication for the rest of the DAG is "blocked until fixed." Dagster's asset-level retry can be reasoned about in terms of exactly which downstream assets become stale as a consequence of a failed or retried materialization, because the lineage graph makes that dependency explicit rather than implicit in task-ordering alone.
**Follow-up trap:** *"Does that mean Dagster's retries are strictly better?"* — not strictly; Airflow's task-blocking model is simple and predictable, which has its own operational value (a human debugging a stuck DAG run sees exactly which task is blocking, with no need to reason about a separate lineage/staleness model) — the tradeoff is explicit lineage-awareness (Dagster) versus simpler, more directly task-state-legible blocking behavior (Airflow), not a strict quality ordering.

### Q9 — Your team is heavily invested in dbt for transformation logic. How does that change the orchestrator recommendation?
**Testing:** whether the candidate connects a specific real-world tooling dependency to the orchestrator choice concretely.
**Answer:** Dagster treats dbt models as first-class software-defined assets sharing one lineage graph with Python-based assets — meaningfully deeper integration than Airflow's typical pattern of invoking `dbt run` as an opaque task step, where Airflow has no native visibility into individual dbt model-level dependencies, only the coarse "the dbt run task succeeded or failed" boundary. For a dbt-centric analytics team, this argues concretely for Dagster over Airflow, all else equal.
**Follow-up trap:** *"The team also has significant existing Airflow infrastructure and expertise elsewhere in the org. Does that change your recommendation?"* — it's a genuine, weighable cost — introducing a second orchestrator has real operational overhead (a second platform to run, monitor, and staff expertise for), and the right call depends on how large and central the dbt-specific workload is relative to the rest of the org's pipelines; a small dbt workload might reasonably stay on Airflow despite the integration friction, while a dbt-centric analytics platform that's a large, growing share of the org's data work justifies the cost of adopting Dagster specifically for that domain.

### Q10 — At staff level: a platform team wants to mandate a single orchestrator company-wide for "consistency." What's your position, and how do you frame the tradeoff to leadership?
**Testing:** whether the candidate can push back on a reflexive standardization mandate with the actual reasoning from this module.
**Answer:** Consistency has real value (shared expertise, simpler on-call rotation, one platform to operate and secure), but Airflow, Dagster, and Prefect encode genuinely different mental models suited to genuinely different workload shapes — a blanket mandate risks forcing a poor fit onto teams whose actual pipelines (dynamic, code-first ML workflows; asset/lineage-centric dbt-heavy analytics) are structurally better served by a different tool, and that poor fit shows up later as elevated maintenance cost, workarounds, and slower delivery for those teams. The honest framing to leadership: recommend a default/primary orchestrator for the common case, with a documented, narrow exception process for workloads that demonstrably don't fit that default well, rather than either a rigid single-tool mandate or an ungoverned free-for-all.
**Follow-up trap:** *"How would you evaluate whether a team's request for an exception is legitimate rather than just a preference?"* — ask them to articulate the specific structural mismatch (not just "we prefer X") — genuine cases look like "our pipelines are dbt-asset-centric and need native lineage" or "our workflows have runtime-determined branching that fights a static DAG model" — a request justified only by developer preference without a structural workload-shape argument doesn't clear the bar for an exception to the platform default.

---

## Red flags that fail you

- Describing Airflow, Dagster, and Prefect as interchangeable "workflow schedulers" without naming the actual abstraction difference (task vs asset vs flow).
- Not knowing Airflow's backfill was historically CLI-only/second-class, or that Airflow 3 (2025) moved it into the scheduler.
- Claiming Dagster's skip-if-unchanged asset re-materialization happens automatically with no configuration required.
- Recommending a migration off an orchestrator as the first response to a scaling symptom, without first auditing DAG/pipeline design (task granularity, fan-out, parse-time cost).
- Not knowing what DAG versioning in Airflow 3 actually fixes (a mid-flight deploy affecting an in-progress run).
- Treating Prefect's dynamic flow model as a strictly superior feature with no debuggability tradeoff against a statically-declared DAG.
- Recommending a single orchestrator platform-wide without acknowledging that genuinely different workload shapes (asset-centric, dynamic, static-DAG-friendly) can legitimately be better served by different tools.
- Not being able to name a concrete production symptom (scheduler falling behind, backfill pain, mid-run inconsistency) tied to a specific mechanical cause.

---

## Cheat card

```
THREE ABSTRACTIONS, SAME "PROBLEM"
  Airflow:  TASK-centric, DAG structure declared UPFRONT (Airbnb, 2015)
  Dagster:  ASSET-centric, the OBJECT PRODUCED is primary, lineage-aware
  Prefect:  FLOW-centric, plain Python, DAG structure emerges at RUNTIME

AIRFLOW 3 (GA 2025) -- biggest release in project history
  Backfill: moved INTO the scheduler (was CLI-only/second-class before) --
    real scalability + diagnostics for ML/ETL reprocessing
  DAG versioning: an in-flight run completes against the VERSION it
    STARTED with, even if a new version deploys mid-run -- closes a
    real correctness gap (mixed old/new code in one run, pre-3.0)
  ~42x faster rendered task-instance-field cleanup for mapped-task DAGs

DAGSTER: skip-if-unchanged downstream re-materialization -- NATIVE to
  the asset-lineage model, requires configuring a freshness/staleness
  policy (not automatic just from the @asset decorator). Native
  time-partitioned assets = ONE-CLICK backfill in the UI. dbt models =
  first-class assets, ONE shared lineage graph with Python assets
  (deeper than Airflow's "dbt run as opaque task" integration).

PREFECT: flows = plain Python functions, tasks discovered at runtime --
  genuine runtime branching/dynamic loops Airflow's static DAG fights.
  HYBRID execution: Prefect Cloud/server holds orchestration metadata,
  YOUR infra actually runs the work (workers poll). Deployments hold
  scheduling, separate from flow definition.

SCALING PROBLEM DIAGNOSIS ORDER (before blaming the tool):
  1. DAG parse cost -- expensive logic at MODULE level vs inside task
     callables (module-level re-executes every scheduler parse cycle)
  2. task granularity / fan-out -- too many tiny tasks, unbounded
     dynamic expansion overwhelms ANY orchestrator's scheduling overhead
  3. only THEN consider an architectural ceiling in the tool itself

DECISION RULE
  widest ecosystem + battle-tested + platform team already exists -> Airflow
  asset/lineage central, heavy dbt -> Dagster
  genuinely dynamic, code-first, runtime-determined structure -> Prefect
  never mandate ONE tool org-wide without a documented exception path
  for workloads with a genuine structural mismatch
```

## Sources
- [Apache Airflow 3 is Generally Available — Airflow blog](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/) — accessed 2026-08-03
- [Release Notes — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html) — accessed 2026-08-03
- [Backfill — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html) — accessed 2026-08-03
- [Airflow 3.0: DAG versioning, multi-language support and native AI/ML workflows — The Data Canal](https://thedatacanal.substack.com/p/airflow-30-dag-versioning-multi-language) — accessed 2026-08-03
- [Comparing Workflow Architectures: Prefect vs. Dagster vs. Airflow — ThinhDA](https://thinhdanggroup.github.io/airflow-prefect-dagster/) — accessed 2026-08-03
- [Airflow vs Prefect vs Dagster: Picking the Right Orchestrator in 2026 — DEV Community](https://dev.to/datastackx/airflow-vs-prefect-vs-dagster-picking-the-right-orchestrator-in-2026-1ifb) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
