# Airflow From Scratch: DAGs, Operators, Sensors, XCom, Deferrable, Best Practices

> **Track:** T18 Data Engineering & Warehousing · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-airflow` · **Tags:** orchestration, critical

## The 30-second version

Airflow is a scheduler, a triggerer, an executor with workers, and a metadata database, and almost every production incident maps cleanly onto one of those four failing. A DAG run isn't identified by when it executes, it's identified by the data interval it covers — `logical_date` is the start of that interval, so a run "for August 1st" doesn't actually start until August 2nd, once the interval has fully elapsed. Any top-level code in a DAG file runs on every scheduler parse cycle, not once, which is the classic scaling bug; sensors that block a worker for hours starve the whole pool, which deferrable operators and the triggerer exist specifically to fix. XCom is for small control-plane values, not data — pass a reference, never a payload. In Airflow 3.0, SLAs were removed for Deadline Alerts and workers stopped touching the metadata database directly, talking only through the Task Execution API.

## Why this gets asked

Because Airflow is the orchestrator almost everyone has touched and almost nobody has read the scheduler internals of. The interviewer has been the one paged at 3am because a DAG file had a top-level `requests.get()` call that hit an API on every 30-second parse cycle, or because a sensor held a worker slot for six hours and starved every other DAG in the pool. They want to know if you understand the **architecture** well enough to diagnose a stuck DAG from symptoms alone, and whether you know the difference between `schedule` and `data_interval` — the single most confusing concept in the tool, and the fastest way to separate "has used Airflow" from "understands Airflow."

---

## Lineage: past → present → future

**What came before.** Cron plus a pile of shell scripts was the default orchestrator for most of the 2000s and early 2010s: reliable for a single job, unmanageable past a handful of interdependent jobs because cron has no concept of dependencies, retries, backfills, or visibility into what actually ran. Oozie (2011, Hadoop-native, XML workflow definitions) and Luigi (2012, Spotify, Python-based) were the first real attempts at dependency-aware orchestration, but Oozie's XML was painful to author and debug, and Luigi's pull-based "does my output already exist" model made backfills and dynamic workflows awkward. Airbnb built Airflow in 2014 specifically to solve this: DAGs as Python code (not XML/config), a rich UI for visibility, and a scheduler that understood time-based dependencies natively. It became an Apache Software Foundation top-level project in 2019.

**Where it stands now.** Airflow is the dominant general-purpose batch orchestrator; Dagster and Prefect compete on developer ergonomics and asset-centric modeling, but Airflow's ecosystem of providers (AWS, GCP, Databricks, Snowflake, dbt) and sheer install base keep it the default answer in most job postings. **Airflow 3.0 (2026)** is a genuinely major architectural release, not an incremental bump: it removed direct metadata-database access from worker nodes entirely, routing all task-worker interaction (state transitions, XCom, heartbeats, connection/variable fetching) through a new **Task Execution API**, which improves security and language-portability (a task can now, in principle, run in a non-Python runtime). **Datasets were renamed and expanded into Assets**, formalizing data-aware scheduling as a first-class citizen rather than a bolt-on. The live disagreement in the field is whether Airflow's DAG-as-Python-code model still makes sense for teams that increasingly think in terms of *data assets* rather than *task graphs* — Dagster's software-defined-assets model was built around that idea from day one, and Airflow 3's Assets feature is a direct response to that competitive pressure.

**Where it's heading.** Event-driven, asset-triggered scheduling (Airflow Assets, formerly Datasets) replacing pure time-based cron scheduling for an increasing share of production DAGs is a real, current trend — see `T18-scheduling-triggering` for the mechanics. Deferrable operators and the triggerer, which decouple "waiting" from "occupying a worker slot," are becoming the default for any I/O-bound wait rather than an advanced/opt-in feature. More speculative: tighter LLM-assisted DAG authoring and anomaly detection on DAG run patterns exist in early vendor tooling (Astronomer's Astro Observe, for instance) but treat "AI writes your DAGs" as a productivity aid to review carefully, not a replacement for understanding the scheduler.

---

## Mental model

```
                         ┌────────────────────┐
                         │   METADATA DB       │◀── source of truth for DAG
                         │  (Postgres/MySQL)   │    state, task instances,
                         └─────────▲──────────┘    connections, variables
                                   │  (Airflow 3: ONLY scheduler/
                                   │   triggerer/webserver touch this
                                   │   directly — workers go through
                                   │   the Task Execution API)
              ┌────────────────────┼────────────────────┐
              │                    │                    │
      ┌───────▼──────┐    ┌────────▼───────┐    ┌───────▼────────┐
      │  SCHEDULER    │    │   TRIGGERER    │    │   WEBSERVER     │
      │ parses DAGs,  │    │ runs async     │    │  UI, REST API   │
      │ decides what  │    │ event loops    │    │                 │
      │ runs when     │    │ for deferred   │    └────────────────┘
      └───────┬──────┘    │ tasks (1000s   │
              │            │ per instance)  │
              │            └────────────────┘
      ┌───────▼──────────────────────┐
      │        EXECUTOR               │  hands tasks to...
      │ (Local/Celery/Kubernetes/     │
      │  CeleryKubernetes)             │
      └───────┬──────────────────────┘
              │
      ┌───────▼──────┐
      │   WORKERS     │  actually execute task code
      └──────────────┘
```

**What each failure looks like:**
- **Scheduler down/lagging** — no new DAG runs get created, task state doesn't advance even though workers are idle; UI shows tasks stuck in `scheduled` state indefinitely.
- **Triggerer down** — deferred tasks never resume; they sit in `deferred` state forever, workers are otherwise fine.
- **Executor/worker starved** — tasks queue up in `queued` state; pool or `parallelism` limits are usually the cause, not a crash.
- **Metadata DB overloaded** — everything gets slow simultaneously (UI, scheduler heartbeats, task state writes); this is the "Airflow is down" symptom that's actually a database problem.

---

## How it actually works

### DAG parsing — the classic performance bug

The scheduler's **DAG File Processor** re-parses every `.py` file in the DAGs folder on a fixed interval (`min_file_process_interval`, default a few seconds; the full folder scan interval is `dag_dir_list_interval`, default 300s) to detect new DAGs and structural changes. **Any top-level code in a DAG file — not inside a task, at module scope — executes on every single parse**, not once at DAG authoring time. A DAG file with `variable = Variable.get("config")` or `df = pd.read_csv(...)` at the top level makes a database call or a disk read every few seconds, for every scheduler parse cycle, multiplied across every DAG file in the folder.

**The observable symptom**: scheduler CPU and metadata-database load climb steadily as the number of DAG files grows, DAG parse time (visible in the UI under "DAG Import Errors" / scheduler logs as `dag_processing.total_parse_time`) creeps past a few seconds per file, and eventually new DAG runs stop being created promptly because the scheduler is spending its time re-parsing rather than scheduling. Teams commonly discover this only after DAG count crosses a few hundred files and scheduler lag becomes visible as tasks starting minutes late with no other explanation.

```python
# Bad: top-level Variable.get() and an API call — executed on EVERY scheduler parse
from airflow import DAG
from airflow.models import Variable

config = Variable.get("my_config")          # DB hit every parse cycle
api_response = requests.get("https://api.example.com/schema")  # network call every parse cycle

with DAG("bad_dag", schedule="@daily") as dag:
    ...

# Good: defer both to task execution time, inside the task callable
def my_task(**context):
    config = Variable.get("my_config")      # only runs when the task actually executes
    api_response = requests.get("https://api.example.com/schema")
    ...

with DAG("good_dag", schedule="@daily") as dag:
    PythonOperator(task_id="run", python_callable=my_task)
```

### `schedule` vs `data_interval` and the logical-date model

This is the concept that confuses almost everyone who hasn't been burned by it. A DAG run is not identified by "when it ran" — it's identified by the **data interval** it's responsible for, expressed as `[data_interval_start, data_interval_end)`. The **logical date** (formerly `execution_date`, removed as a context variable name in Airflow 3) equals `data_interval_start` — it is the *beginning* of the period the run covers, not the wall-clock time the run actually executed.

**The rule that trips people up**: a run for interval `[2026-08-01, 2026-08-02)` does not start until `2026-08-02` has begun, because the scheduler can only be sure it has all of August 1st's data once August 1st is over. So a DAG scheduled `@daily` that "runs for August 1st" actually kicks off shortly after midnight on August 2nd, and `logical_date` for that run is `2026-08-01`, not `2026-08-02`.

```python
# The most common real bug: using logical_date (ds) when you mean data_interval_end
@task
def extract(**context):
    # WRONG if you want "the end of the period" — ds is the START of the interval
    as_of = context["ds"]

    # RIGHT for "data through the end of this interval"
    as_of = context["data_interval_end"]
```

Manually triggering a DAG run (outside its schedule) sets `logical_date` to the trigger time by default, which is *not* the start of any real data interval — this is a frequent source of confusion when someone manually re-runs a DAG and gets unexpected date-partition behavior downstream.

### Operators, TaskFlow API, sensors

An **operator** is a class representing one unit of work (`BashOperator`, `PythonOperator`, provider-specific ones like `S3ToRedshiftOperator`). The **TaskFlow API** (`@task` decorator, Airflow 2.0+) wraps Python callables as tasks and handles XCom passing implicitly via function return values and arguments, removing a lot of the `PythonOperator` + manual `xcom_pull`/`xcom_push` boilerplate:

```python
from airflow.decorators import dag, task
from datetime import datetime

@dag(schedule="@daily", start_date=datetime(2026, 1, 1), catchup=False)
def taskflow_example():
    @task
    def extract() -> dict:
        return {"rows": 1000}

    @task
    def load(data: dict) -> None:
        print(f"loading {data['rows']} rows")

    load(extract())   # dependency + XCom passing inferred from the call graph

taskflow_example()
```

A **sensor** (`S3KeySensor`, `ExternalTaskSensor`, `SqlSensor`) polls for a condition and blocks until it's true or times out. The problem: a classic (non-deferrable) sensor in `poke` mode occupies a worker slot for its *entire* wait duration — a sensor waiting up to 6 hours for a file to land holds a worker the whole time, and if you have 50 such sensors running concurrently against a worker pool sized for 20, the other 30 queue behind them. This is **worker-slot starvation**, and it's one of the most common Airflow production incidents: DAGs across the whole cluster start running late not because anything crashed, but because every worker slot is tied up in `poke` loops.

**Deferrable operators and the triggerer are the fix.** A deferrable sensor (`S3KeySensorAsync`, or any operator implementing `execute()` → `self.defer(...)`) suspends itself entirely, releasing the worker slot, and hands the wait condition to the **triggerer** — a single lightweight async event loop process that can hold thousands of concurrent waits (an async `asyncio` loop polling many conditions concurrently costs a fraction of what thousands of blocked worker threads would). When the condition is met, the triggerer signals the scheduler to resume the task on a worker, only for the (usually brief) remainder of the task's actual work.

```python
# Deferrable-friendly sensor mode — worker slot released while waiting
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

wait_for_file = S3KeySensor(
    task_id="wait_for_file",
    bucket_name="my-bucket",
    bucket_key="daily/{{ ds }}/data.parquet",
    deferrable=True,       # hands off to the triggerer instead of polling on a worker
    poke_interval=60,
    timeout=6 * 60 * 60,
)
```

**Airflow 3.2+ adds a further refinement**: an operator can set `start_from_trigger = True` to defer to the triggerer *immediately* without ever occupying a worker slot even for its initial setup, and workers can run `async def` task callables natively via the `@task` decorator or `PythonOperator`, narrowing the gap between "deferrable operator" and "just write async code."

### XCom — what it's for and what it isn't

XCom (cross-communication) lets tasks pass small values to each other via the metadata database by default (the `BaseXCom` backend). **It is explicitly not for data** — the size limit is bounded by whatever the metadata database column allows (practically a few KB to low MB depending on the DB, and Airflow's UI/DB performance degrades well before you hit a hard limit), so passing a DataFrame or a list of file paths numbering in the thousands through XCom is a design smell, not a feature. The correct pattern is to pass a *reference* (an S3 URI, a table name, a small manifest) through XCom and let the task read the actual data from durable storage.

```python
# Bad: passing a DataFrame through XCom
@task
def extract() -> "pd.DataFrame":
    return pd.read_sql("SELECT * FROM orders", conn)   # serialized into the metadata DB

# Good: pass a reference, not the data
@task
def extract() -> str:
    df = pd.read_sql("SELECT * FROM orders", conn)
    path = f"s3://bucket/staging/orders_{ds}.parquet"
    df.to_parquet(path)
    return path   # small string, safe for XCom
```

For genuinely large intermediate objects that still need to flow through XCom's interface, Airflow supports a **custom/object-storage XCom backend** (`XComObjectStorageBackend`, configurable with `xcom_objectstorage_threshold`) that transparently spills values above a size threshold to S3/GCS instead of the metadata DB — but the underlying advice (don't route bulk data through the orchestrator's control plane) still holds; use this for occasional oversized values, not as a substitute for a proper data-passing pattern.

### Pools, priority, concurrency knobs

| Knob | Scope | What it controls |
|---|---|---|
| `parallelism` | Airflow instance-wide | Max concurrently running task instances across all DAGs |
| `dag_concurrency` / `max_active_tasks` | Per DAG | Max concurrently running tasks within one DAG |
| `max_active_runs` | Per DAG | Max concurrent DAG runs (matters a lot for backfills — see `T18-backfill-replay`) |
| `pool` | Named resource group | Caps concurrent tasks against a shared bottleneck resource (e.g. a `pool="database_conn"` capped at 10, so no more than 10 tasks hit that DB at once regardless of how many DAGs reference it) |
| `priority_weight` | Per task | Breaks ties when multiple tasks compete for the same pool/worker slots — higher runs first |

Pools are the mechanism for protecting a shared downstream resource (a database, an API with a rate limit) from being hammered by many DAGs that don't know about each other; without one, 20 independent DAGs each opening 5 connections to the same Postgres instance can exhaust its connection limit with no single DAG being individually at fault.

### Retries, callbacks, dynamic task mapping

Standard retry config (`retries`, `retry_delay`, `retry_exponential_backoff=True`) applies per task, same principles as the retry catalogue in `T21-resilience-catalogue` — exponential backoff with jitter is supported natively via `retry_exponential_backoff`.

**SLAs were removed in Airflow 3.0** and replaced by **Deadline Alerts** (fully available from 3.1/3.2): the old SLA mechanism waited for the whole DAG to finish before evaluating whether it missed its deadline, which meant you found out about a blown SLA only after the fact; Deadline Alerts evaluate and fire "immediately" (within one scheduler heartbeat of the calculated deadline) rather than waiting for DAG completion, which is a meaningfully faster detection story for anything paging on-call.

**Dynamic task mapping** (`@task.expand`, AIP-42, Airflow 2.3+) generates N task instances at *runtime* from an upstream value, rather than requiring the DAG author to know N at authoring time:

```python
@task
def get_files() -> list[str]:
    return ["a.csv", "b.csv", "c.csv"]   # length only known at runtime

@task
def process(file: str):
    ...

process.expand(file=get_files())   # generates one mapped task instance per file
```

Guardrails matter here: `max_map_length` (default 1024) caps how many mapped instances a single `.expand()` call can generate, and an ungated upstream returning 50,000 items can otherwise flood the scheduler with that many task instances in one run. `partial()` carries the arguments that stay constant across every mapped instance (`task_id`, `pool`, `queue` and most other `BaseOperator` args are not mappable and must go through `partial()`), while `expand()`/`expand_kwargs()` carries what varies.

### Testing DAGs

- **Unit-test task logic directly** as plain Python functions where possible — decoupling business logic from the Airflow-specific glue (`@task` wrapper, context access) is what makes it testable without spinning up a scheduler.
- **DAG-level validation**: import every DAG file in CI and assert no import errors, no cycles, and reasonable task counts — catches the "someone put an unhandled exception at module scope" class of bug before it reaches production and breaks parsing for every other DAG in the folder in a shared parsing process.
- **`airflow dags test`** runs a single DAG run end-to-end without needing the scheduler, useful for local iteration but not a substitute for CI import checks.

---

## Build it from scratch

A minimal DAG demonstrating the concepts above together: TaskFlow API, a deferrable-friendly sensor pattern (simplified to a plain callable check, since a real deferrable sensor needs a registered trigger class), dynamic mapping, and correct `data_interval_end` usage.

```python
# untested sketch — illustrates the concepts; a real deferrable sensor needs a
# proper Trigger subclass registered with the triggerer, omitted here for brevity
from airflow.decorators import dag, task
from airflow.sensors.base import PokeReturnValue
from datetime import datetime

@dag(
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,          # backfills of this DAG run one interval at a time
    default_args={"retries": 2, "retry_exponential_backoff": True},
)
def warehouse_load():

    @task.sensor(poke_interval=60, timeout=3600, mode="reschedule")
    def wait_for_upstream(**context) -> PokeReturnValue:
        # mode="reschedule" releases the worker slot between pokes —
        # cheaper than mode="poke" (holds the slot the whole time), though
        # a true deferrable sensor via the triggerer is cheaper still
        ready = check_upstream_landed(context["data_interval_end"])
        return PokeReturnValue(is_done=ready)

    @task
    def list_partitions(**context) -> list[str]:
        # length only known at runtime — feeds dynamic mapping below
        return discover_partitions(as_of=context["data_interval_end"])

    @task
    def load_partition(partition: str, **context):
        merge_partition_idempotent(partition, as_of=context["data_interval_end"])

    wait_for_upstream() >> load_partition.expand(partition=list_partitions())

warehouse_load()
```

Two details worth calling out to an interviewer reading this: `mode="reschedule"` is the cheap middle ground between a blocking `poke` sensor and a fully deferrable one (it releases the worker between pokes but still uses a worker to run each poke, rather than the triggerer's async loop), and `max_active_runs=1` is a deliberate backfill-safety choice discussed further in `T18-backfill-replay`. Full runnable version with a registered custom trigger class: `labs/py/18-airflow-lab/`.

---

## How it's done in production

**Managed Airflow** — Astronomer (Astro), AWS MWAA, GCP Cloud Composer, all run the open-source scheduler/webserver/triggerer/executor components for you, differing mainly in executor choice (MWAA and Composer both default to Celery/Kubernetes-based executors), provider package management, and observability tooling layered on top (Astronomer's Astro Observe adds DAG-level anomaly detection and lineage on top of open-source Airflow).

**Executors** — `LocalExecutor` for single-machine dev, `CeleryExecutor` for a fixed worker pool with message-queue-based task distribution, `KubernetesExecutor` for per-task pod isolation (each task gets its own pod, clean resource isolation, higher per-task startup latency), `CeleryKubernetesExecutor` for a hybrid where most tasks use Celery workers and specific ones route to dedicated pods. The KubernetesExecutor is increasingly the default recommendation for heterogeneous workloads (some tasks need a GPU, most don't) because per-task pod specs let you right-size resources per task rather than provisioning a worker fleet for the heaviest task.

**Airflow 3's Task Execution API** — this is the most consequential recent architectural change: workers no longer connect directly to the metadata database, all state transitions and XCom traffic route through a REST API layer. This closes off an entire class of security issue (a compromised task can no longer directly query/modify arbitrary metadata-DB tables) and is a prerequisite for eventually running tasks in non-Python runtimes.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Tasks starting minutes late, scheduler CPU climbing as DAG count grows | Top-level code (DB/API calls) in a DAG file, executed on every parse cycle | Move all I/O into task callables; keep DAG-file top level to pure DAG/task structure definition |
| Whole cluster's DAGs running late, no crashes anywhere | Worker-slot starvation from non-deferrable `poke`-mode sensors holding slots for hours | Switch to `deferrable=True` sensors (triggerer) or `mode="reschedule"` |
| Deferred tasks stuck in `deferred` state forever, workers otherwise idle | Triggerer process down or crashed | Restart/monitor the triggerer as its own critical process, not just scheduler/workers |
| Downstream task processes the wrong day's data after a manual trigger | Confusing `logical_date`/`ds` (start of interval) with `data_interval_end`, or manually triggering sets `logical_date` to trigger time, not a real interval start | Use `data_interval_end` explicitly for "data through now"; understand manual triggers don't represent a real scheduled interval |
| One DAG's bug (unhandled exception at DAG-file module scope) breaks parsing for unrelated DAGs | Shared DAG-file processing; an import error in one file can affect processor throughput broadly | CI import-check every DAG file before merge; isolate risky top-level logic |
| A shared database gets overwhelmed by many unrelated DAGs simultaneously | No pool configured for the shared resource | Create a named pool capped at a safe concurrency, assign every task touching that resource to it |
| A single mapped task explodes into tens of thousands of instances, scheduler grinds to a halt | Ungated dynamic task mapping (`.expand()`) on an unbounded upstream list | Set/respect `max_map_length`, validate upstream list size before mapping, chunk into batches |
| SLA-based alerting arrives long after a DAG should have paged | Old SLA mechanism waits for DAG completion before evaluating (pre-3.0 behavior) | Migrate to Deadline Alerts (3.1+), which evaluate near-immediately at the calculated deadline |

---

## Tradeoffs & when NOT to use it

- **Airflow is the wrong tool for sub-second or genuinely real-time processing.** It's a batch/scheduled-workflow orchestrator; the scheduler's own loop and DAG-parsing overhead put a practical floor on how tight a schedule is worth running (sub-minute schedules are possible but fight the tool's design center). Use Flink/Spark Structured Streaming or a message-queue-based architecture for continuous processing.
- **Do not use XCom for anything resembling "data."** It's a control-plane mechanism sized for small values (config, a file path, a row count), not a data bus. Passing DataFrames or large lists through it degrades metadata-DB performance for the whole instance, not just your DAG.
- **Do not put business logic that needs independent unit testing directly inside operator/task glue with heavy Airflow context coupling.** Extract it into plain functions/classes Airflow calls into; the DAG file should be nearly all structure, minimal logic.
- **Classic `poke`-mode sensors for long waits are close to always the wrong choice now that deferrable operators exist.** There's essentially no reason to burn a worker slot for hours when the triggerer exists specifically to avoid it — a candidate defaulting to `poke` mode without considering `deferrable=True` is a real signal of stale knowledge.
- **For workflows that are fundamentally about "what data is now available" rather than "run this task graph on this schedule," consider whether an asset-centric tool (Airflow's own Assets feature, or Dagster) fits the mental model better** than force-fitting it into pure time-based DAG scheduling — see `T18-scheduling-triggering`.

---

## Interview questions

### Q1 — Explain the difference between `logical_date` and `data_interval_end`, and why a `@daily` DAG for "August 1st" doesn't run until August 2nd.
**Testing:** the concept most candidates get wrong in practice, not just definition recall.
**Answer:** `logical_date` (formerly `execution_date`) equals `data_interval_start` — the beginning of the period a run covers. The scheduler waits until the interval has fully elapsed before running, because it can't guarantee it has complete data for August 1st until August 1st is over; so the run "for August 1st" (`logical_date = 2026-08-01`) actually executes shortly after midnight on August 2nd. `data_interval_end` is what you want when you mean "data through the end of this period," which is a different value than `logical_date`/`ds`.
**Follow-up trap:** *"What does `logical_date` mean for a manually triggered run?"* — it's set to the trigger time, which does not correspond to any real scheduled data interval; date-partition logic downstream that assumes `logical_date` always represents a clean interval boundary can misbehave on manual triggers, which is a frequent source of "why did my manual rerun write to the wrong partition" bugs.

### Q2 — What's the performance bug with top-level code in a DAG file, and how would you detect it in a real cluster?
**Answer:** The scheduler's DAG File Processor re-parses every `.py` file on a fixed interval (`min_file_process_interval`), and any code at module scope (not inside a task callable) executes on every parse — a top-level `Variable.get()` or API call runs every few seconds indefinitely, not once. Detect it via scheduler logs/metrics on DAG parse time per file (`dag_processing.total_parse_time`), or by noticing metadata-DB load or scheduler CPU creeping up as DAG count grows with no corresponding increase in actual task volume.
**Follow-up trap:** *"How would you fix it without breaking DAGs that legitimately need dynamic structure (e.g., task count depends on a config)?"* — for structure that's genuinely dynamic but doesn't need to hit an external system every parse, cache the config with a longer TTL or bake it into a lighter-weight local file/variable read; for anything requiring true runtime-dependent fan-out, dynamic task mapping (`.expand()`) is the correct mechanism, since it defers the actual value lookup to task execution rather than DAG parse time.

### Q3 — Walk through what worker-slot starvation looks like and how deferrable operators fix it.
**Answer:** A non-deferrable sensor in `poke` mode blocks a worker for its entire wait duration; with enough long-running sensors relative to worker pool size, other unrelated tasks queue up waiting for a slot, and the whole cluster's DAGs appear to run late with no crash anywhere. Deferrable operators call `self.defer()` to suspend the task entirely, releasing the worker slot, and hand the wait condition to the triggerer — a single lightweight async process that can hold thousands of concurrent waits cheaply — resuming the task on a worker only once the condition is actually met.
**Follow-up trap:** *"Is `mode='reschedule'` the same thing?"* — no, it's a middle ground: it releases the worker *between* pokes rather than holding it continuously, but each poke still consumes a worker slot briefly, whereas a truly deferrable operator via the triggerer never touches a worker at all while waiting. Reschedule mode is cheaper than `poke` but more expensive than a real deferrable operator.

### Q4 — Why is XCom explicitly not meant for passing data, and what's the correct pattern?
**Answer:** XCom's default backend stores values in the metadata database, sized for small control-plane values (a count, a status, a file path); its practical size limit is bounded by what the metadata DB column and the UI can handle performantly, not a generous data-transfer limit. The correct pattern is passing a *reference* — an S3 URI, a table name — through XCom, with the task reading the actual data from durable storage using that reference.
**Follow-up trap:** *"Airflow has an object-storage XCom backend now — doesn't that solve it?"* — it spills large values to S3/GCS above a configurable threshold (`xcom_objectstorage_threshold`), which helps with occasional oversized values, but it doesn't change the underlying architectural point: XCom is still the orchestrator's control plane, and routing your primary data flow through it (even transparently spilled to object storage) usually means the DAG's task boundaries are drawn in the wrong place.

### Q5 — Your DAG has a mapped task that expanded to 40,000 instances overnight, and the scheduler has been unresponsive since. What happened and how do you prevent it?
**Answer:** An unbounded upstream value fed into `.expand()` — likely a list-returning task whose size wasn't validated — generated one task instance per element, and 40,000 task instances is enough to overwhelm scheduler processing and the metadata DB simultaneously. Prevent it with `max_map_length` (default 1024, can be tightened further) and validating/capping the upstream list size explicitly before mapping, or chunking the work into batches of a bounded size mapped instead of the raw items.
**Follow-up trap:** *"What's actually expensive about a large number of mapped tasks — is it just scheduler CPU?"* — it's the metadata database too: every mapped task instance is a row (or several) in task_instance-related tables, and the scheduler's per-heartbeat work scales with active task instance count; a runaway `.expand()` degrades both the scheduler loop and DB write throughput for every other DAG sharing that metadata database.

### Q6 — How do pools solve a problem that per-DAG concurrency limits (`max_active_tasks`) don't?
**Answer:** `max_active_tasks` caps concurrency *within one DAG*, but a shared downstream resource (a database, a rate-limited API) can be hammered by many *different* DAGs that have no visibility into each other's concurrency. A named pool caps concurrent tasks against that resource across every DAG that assigns tasks to it — 20 independent DAGs each capped individually at 5 concurrent tasks can still collectively open 100 connections to the same database with no per-DAG limit catching it; a pool sized at, say, 10 for that resource catches it regardless of which DAG the task belongs to.
**Follow-up trap:** *"What if two critical DAGs both need that pool and one is starving the other?"* — `priority_weight` breaks ties for pool/worker-slot contention; assign a higher weight to the DAG whose SLA matters more, so it's scheduled ahead of lower-priority competitors for the same constrained pool.

### Q7 — What replaced Airflow's SLA feature in 3.x, and what's the actual behavioral difference, not just the name change?
**Answer:** Deadline Alerts (available from Airflow 3.1/3.2). The old SLA mechanism evaluated whether a DAG missed its deadline only after the DAG run finished, meaning you found out about a blown SLA well after the fact if the DAG ran long. Deadline Alerts evaluate at the calculated deadline itself and fire "immediately" — within roughly one scheduler heartbeat interval — rather than waiting for completion, which is materially faster detection for anything paging on-call about a missed freshness target.
**Follow-up trap:** *"Does this mean SLA-based DAGs from Airflow 2.x migrate automatically?"* — no, they need manual migration; Airflow's own migration guide points to using something like `DeadlineReference.DAGRUN_LOGICAL_DATE` as the direct replacement pattern, but existing SLA-callback code has to be rewritten against the new API.

### Q8 — Describe the change in Airflow 3.0's architecture around worker access to the metadata database, and why it matters.
**Answer:** In Airflow 2.x, worker task code could (and sometimes did) query the metadata database directly via SQLAlchemy. Airflow 3.0 removed this entirely: all runtime interactions — state transitions, XCom read/write, connection and variable fetching, heartbeats — now go through a dedicated Task Execution API (a REST layer), and workers no longer hold direct DB credentials at all. This closes a security surface (a compromised or buggy task can no longer read/write arbitrary metadata tables) and is a structural prerequisite for eventually supporting task execution in non-Python runtimes, since the API contract doesn't assume a Python SQLAlchemy client.
**Follow-up trap:** *"Does this affect custom operators that used to query the metadata DB directly for a clever trick (e.g., checking another DAG's state via raw SQL)?"* — yes, that pattern breaks under Airflow 3 and must be rewritten against the Task Execution API or a supported mechanism (like `ExternalTaskSensor` for cross-DAG state), which is a real, common migration pain point teams hit upgrading from 2.x.

### Q9 — What are Airflow Assets (formerly Datasets), and how do they change the scheduling model?
**Answer:** An Asset represents a logical piece of data (e.g., a specific table or file path) that a task can declare it produces; downstream DAGs can be scheduled to trigger the moment an upstream task updates an Asset they depend on, rather than on a fixed time schedule. This shifts the mental model from "which DAG triggers which" (pure task-graph thinking) to "what data is now available" (asset-centric thinking), reducing the number of brittle time-based-guess schedules and cross-DAG sensors used purely to approximate "has the upstream data landed yet."
**Follow-up trap:** *"Isn't this just what `ExternalTaskSensor` already did?"* — `ExternalTaskSensor` polls for another DAG's *task* to reach a certain state, which is a task-graph-shaped solution to what's fundamentally a data-availability question, and it still occupies a sensor (worker or triggerer) doing the polling. Asset-based scheduling is push-based and data-centric: the producing task declares the Asset updated, and the scheduler reacts, no polling involved.

### Q10 — When would you choose the KubernetesExecutor over CeleryExecutor, and what's the cost?
**Answer:** KubernetesExecutor gives each task its own pod with its own resource spec — the right choice when workloads are heterogeneous (some tasks need a GPU or 32GB RAM, most need almost nothing) since you can right-size per task rather than provisioning a fixed Celery worker fleet for the heaviest case. The cost is per-task pod startup latency (seconds, sometimes tens of seconds, versus a warm Celery worker picking up a task near-instantly), which matters for DAGs with many short, frequent tasks where scheduling overhead can dominate actual work time.
**Follow-up trap:** *"Can you mix both?"* — yes, `CeleryKubernetesExecutor` routes most tasks to a Celery worker pool and specific tasks (tagged with a special queue) to dedicated Kubernetes pods, giving you the low-latency default plus per-task isolation where it's actually needed, without paying pod-startup cost on every task.

### Q11 — How do you unit test Airflow DAGs without spinning up a full scheduler?
**Answer:** Two layers: extract business logic out of operator/task glue into plain, Airflow-independent functions and unit-test those directly with normal pytest — this is what makes most of the actual logic testable cheaply. Separately, a CI step imports every DAG file and asserts no import errors, no cycles, and sane task counts, which catches the "unhandled exception at DAG-file module scope breaks parsing" class of bug before merge. `airflow dags test <dag_id> <date>` runs one full DAG execution locally without the scheduler for integration-style local iteration, but it's slower and not typically run in CI for every DAG on every PR.
**Follow-up trap:** *"What does the DAG-import CI check actually catch that a code reviewer wouldn't?"* — it catches runtime import errors from things a reviewer can't easily spot by reading, like a provider package version mismatch, a missing environment variable a top-level `Variable.get()` depends on, or a typo in a dynamically constructed task ID — failures that only surface when the file is actually executed, not from static reading.

### Q12 — Design the pools, priority, and concurrency settings for a cluster where one DAG does a nightly full-warehouse rebuild (expensive, must finish by 6am) alongside 40 small hourly DAGs hitting the same Postgres metadata replica for lookups.
**Testing:** synthesizing pools + priority + concurrency into one operational design.
**Answer:** Put every task from any DAG that queries the shared Postgres replica into one named pool sized below the replica's safe connection limit (e.g., pool size 15 if the replica comfortably handles 20 concurrent connections, leaving headroom). Give the nightly rebuild's tasks a higher `priority_weight` so, when contention for that pool occurs near 6am, the deadline-critical DAG wins scheduling over the hourly DAGs. Cap `max_active_runs=1` on the rebuild DAG so an accidental overlapping run (e.g., a manual trigger during the scheduled run) can't double the load on the same resource at once.
**Follow-up trap:** *"What if the hourly DAGs start missing their own deadlines because the nightly job is starving them via priority?"* — that's the real tradeoff being made explicit rather than left implicit; if the hourly DAGs have their own hard SLA, the fix isn't more priority tuning, it's giving the nightly rebuild its own dedicated resource (a separate read replica) so the two workloads stop competing for the same constrained pool at all.

---

## Red flags that fail you

- Not knowing the difference between `logical_date` and `data_interval_end`, or asserting a `@daily` DAG "runs on the day it covers."
- Putting real I/O (API calls, DB queries) at DAG-file top level and not recognizing it as a per-parse-cycle cost.
- Recommending a `poke`-mode sensor for a multi-hour wait without mentioning deferrable operators.
- Suggesting XCom for passing a DataFrame or any bulk data.
- Naming SLAs as the current Airflow 3.x mechanism (removed, replaced by Deadline Alerts).
- Not knowing pools exist, or not distinguishing them from per-DAG concurrency limits.
- Treating dynamic task mapping as safe by default with no mention of `max_map_length` or upstream size validation.

---

## Cheat card

```
ARCHITECTURE   Scheduler (parses DAGs, decides what runs) · Triggerer (async
               loop, 1000s of deferred waits per instance) · Executor+Workers
               (run task code) · Metadata DB (source of truth)
               Airflow 3: workers talk ONLY via Task Execution API, no direct DB

DAG PARSING    top-level code in a DAG file runs EVERY parse cycle
               (min_file_process_interval, ~secs; folder scan ~300s default)
               symptom: scheduler CPU/DB load climbs as DAG count grows,
               tasks start late with no crash

LOGICAL DATE   logical_date == data_interval_start (period BEGIN, not when
               it runs). Run for interval [T, T+1) starts AFTER T+1 begins.
               Use data_interval_end for "data through now", not ds/logical_date.
               Manual trigger: logical_date = trigger time, NOT a real interval.

SENSORS        poke mode: blocks a worker for the FULL wait — starves the pool
               reschedule mode: releases worker BETWEEN pokes, still uses one per poke
               deferrable=True: hands wait to TRIGGERER, worker slot fully freed
               start_from_trigger=True (3.2+): never touches a worker while waiting

XCOM           NOT for data. Default backend = metadata DB, size bounded by
               DB/UI perf, not a generous limit. Pass a REFERENCE (S3 URI),
               not the payload. Object-storage XCom backend spills above a
               threshold but doesn't change the underlying advice.

POOLS          cap concurrency against a SHARED resource across ALL DAGs
               (unlike max_active_tasks, which is per-DAG only)
priority_weight  breaks ties for pool/worker contention
max_active_runs  caps concurrent DAG RUNS — critical for safe backfills

DYNAMIC MAPPING  .expand()/.expand_kwargs() — runtime-determined fan-out
                 partial() carries constants (task_id, pool, queue)
                 max_map_length default 1024 — GUARD unbounded upstreams

SLA -> DEADLINE ALERTS (3.1+)  SLA removed in 3.0. Old SLA evaluated only
               after DAG finished. Deadline Alerts fire near-immediately at
               the calculated deadline (~1 scheduler heartbeat).

ASSETS (was Datasets, 3.0+)  data-aware scheduling: downstream triggers on
               upstream Asset update, not polling. Push, not poll.

EXECUTORS   Local (dev) · Celery (fixed worker pool) · Kubernetes (per-task
            pod, resource isolation, slower cold start) · CeleryKubernetes (hybrid)

TESTING     unit-test extracted plain functions, not operator glue
            CI: import every DAG file, assert no errors/cycles
            airflow dags test <id> <date> — local full run, not for CI-per-PR
```

## Sources

- [Deferrable Operators & Triggers — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html) — accessed 2026-08-01
- [Apache Airflow 2 vs 3: A Deep Technical Comparison for Data Engineers](https://dev.to/de_clerke/apache-airflow-2-vs-3-a-deep-technical-comparison-for-data-engineers-2on5) — accessed 2026-08-01
- [Migrating from SLA to Deadline Alerts — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/howto/sla-to-deadlines.html) — accessed 2026-08-01
- [Dynamic Task Mapping — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/dynamic-task-mapping.html) — accessed 2026-08-01
- [Object Storage XCom Backend — apache-airflow-providers-common-io Documentation](https://airflow.apache.org/docs/apache-airflow-providers-common-io/stable/xcom_backend.html) — accessed 2026-08-01
- [Airflow Data Intervals: A Deep Dive — Towards Data Science](https://towardsdatascience.com/airflow-data-intervals-a-deep-dive-15d0ccfb0661/) — accessed 2026-08-01
- [Release Notes — Airflow 3.3.0 Documentation](https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
