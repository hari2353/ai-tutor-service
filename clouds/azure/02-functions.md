# Azure Functions: Plans, Durable Functions, Bindings, Cold Starts

> **Track:** C-AZ Azure Atlas · **Time:** 2.0h · **Prereqs:** `C-AZ-identity` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-functions` · **Tags:** serverless

## The 30-second version

Azure Functions ships three hosting plans that trade cost against cold-start control: **Consumption** (true scale-to-zero, pay-per-execution, no VNet integration, 10-minute default timeout, the legacy default), **Premium** (always-ready/pre-warmed instances eliminate cold starts entirely, VNet integration, up to 60-minute timeout, billed even when idle), and **Flex Consumption** (GA 2024, now Microsoft's recommended default for new workloads) which keeps Consumption's scale-to-zero economics while adding optional always-ready instances and native VNet support — it closes the two gaps that used to force teams onto the pricier Premium plan just for networking or warm instances. Cold starts on Consumption for .NET isolated commonly land 2-7 seconds, worse with heavy DI or large deployment packages; Flex Consumption's always-ready instances and faster placement model meaningfully cut that without Premium's always-on cost. Bindings are Azure's signature differentiator from AWS Lambda: instead of writing SDK calls to read a Cosmos DB document or write a queue message, you declare input/output bindings in configuration and the runtime wires the data in and out — a push-oriented declarative model versus Lambda's mostly pull-based event source mappings, at the cost of bindings not covering AWS's ~200-source integration breadth. Durable Functions is code-first stateful orchestration (functions written as ordinary-looking async code that the runtime replays deterministically from an append-only history to resume after a crash), the direct alternative to AWS Step Functions' state-machine-first (JSON/ASL) approach — the durability comes from event sourcing, and orchestrator code must be strictly deterministic (no `DateTime.Now`, no random, no direct I/O) or replay silently produces wrong results.

## Why this gets asked

The interviewer has shipped a Consumption-plan function that looked fine in testing and then produced multi-second p99 latency spikes in production traffic with irregular request patterns, has debugged an orchestrator function that "randomly" reran a side effect twice because someone called `Guid.NewGuid()` inside orchestrator code instead of using the durable-safe equivalent, and has had to explain to a team why moving to VNet integration silently forced a plan upgrade that changed their entire cost model. They want to know you understand the plan tradeoffs as actual architecture decisions, not a pricing-page comparison, and that you know deterministic replay is a hard constraint, not a suggestion.

---

## Lineage: past → present → future

**What came before.** Azure Functions launched in 2016 as Azure's answer to AWS Lambda (2014) and Google Cloud Functions (2016 beta), arriving into a market where Lambda had already established the FaaS pattern — event trigger, ephemeral execution, pay-per-invocation. Before Functions, Azure's serverless-adjacent offering was WebJobs running inside App Service, which required a provisioned, always-on App Service Plan underneath — no real scale-to-zero, no pure consumption billing. The pain Functions solved was the same Lambda solved: stop paying for idle compute, stop managing servers for event-driven, bursty workloads. Early Consumption-plan cold starts (often 3-10+ seconds for .NET, worse for larger dependency trees) were a persistent complaint that pushed teams either to accept the latency or pay for an always-on Premium/Dedicated plan just to avoid it.

**Where it stands now.** **Flex Consumption**, generally available in 2024 and matured through 2025-2026, is Microsoft's current answer to "why do I have to choose between cold starts and networking versus cost" — it merges Consumption's scale-to-zero billing with Premium-like capabilities (VNet integration, optional always-ready instances) that previously required the full Premium plan's always-on cost floor. Microsoft's own guidance now steers new projects toward Flex Consumption by default. [Azure Functions Flex Consumption — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan) — accessed 2026-08-08. The live disagreement in the ecosystem is less "which plan" and more "Functions vs. containers (Container Apps/AKS) for the same workload" — as cold-start-sensitive teams increasingly reach for Container Apps' scale-to-zero with more control over the runtime, the FaaS-vs-serverless-container line has blurred, and a meaningful minority of architects now default to Container Apps for anything beyond simple event-glue code.

**Where it's heading.** Expect Flex Consumption to keep absorbing Premium's remaining differentiators over time (higher max instance memory tiers, more networking parity), narrowing Premium's justification down mostly to workloads needing guaranteed zero cold starts at sustained high concurrency or VNet features Flex hasn't yet matched — moderate confidence, since Microsoft's own docs already frame Flex as the default and Premium as the "you specifically need X" tier. Durable Functions' direction is deeper integration with the cross-language Durable Task Framework (Python, Java, JS, .NET, PowerShell orchestrators sharing one underlying engine and, increasingly, one durable-task-scheduler backend rather than each language stack maintaining separate storage-provider code) — this is actively shipping, not speculative, but the exact timeline for full parity across all supported languages is worth re-checking near an interview date.

---

## Mental model

```
TRIGGER (the "what wakes this function up")
  HTTP, Timer, Queue, Blob, Cosmos DB change feed, Event Grid, Service Bus...
        │
        ▼
FUNCTION (your code) ◀──── INPUT BINDINGS (declarative reads:
        │                    "give me this Cosmos doc by ID from the
        │                     trigger payload" — no SDK call written)
        ▼
   OUTPUT BINDINGS (declarative writes: "whatever this function
                     returns, put it on this queue / write it to
                     this table" — no SDK call written)

HOSTING PLAN = where the above actually runs and how it's billed:

Consumption          Premium              Flex Consumption
scale to 0            always >=1 warm      scale to 0
pay per exec+GB-s      pay always (even     pay per exec+GB-s,
cold start: seconds     idle)                OPTIONAL always-ready
no VNet                 no cold start        instances (pay for those)
10 min timeout           VNet native          VNet native
200 instance cap          60 min timeout        1000 instance cap
                                                 Microsoft's default pick

DURABLE FUNCTIONS = stateful orchestration ON TOP of any plan above:
  Orchestrator function's code IS the workflow definition (code-first),
  vs AWS Step Functions where the state machine (JSON/ASL) IS the
  workflow definition and Lambda functions are just the task bodies.
```

---

## How it actually works

### The three plans, with real numbers

| | Consumption | Premium | Flex Consumption |
|---|---|---|---|
| Scale to zero | Yes | No (always ≥1 instance) | Yes |
| Cold start | Seconds (2-7s .NET isolated typical, 10s+ with heavy DI) | None (pre-warmed) | Reduced vs Consumption; near-zero with always-ready instances configured |
| VNet integration | No | Yes | Yes (native) |
| Max execution timeout | 10 min (default), 5 min hard floor recommendation for reliability | 60 min | 60 min (configurable, check current docs) |
| Instance memory | Fixed, small | Configurable, larger (up to several GB) | 512 MB / 2,048 MB (default) / 4,096 MB |
| Max instance scale-out | 200 | 100 (varies by SKU) | 1,000 |
| Billing model | Per-execution + GB-s of actual execution | Per-second of provisioned instance regardless of load | Per-execution + GB-s (on-demand); idle baseline + execution rate if always-ready configured |
| Microsoft's 2026 default recommendation | Legacy — still fine for simple, latency-insensitive triggers | When you need guaranteed zero cold start, VNet, and long timeouts and are willing to pay for always-on | **Recommended default for new workloads** |

Flex Consumption pricing specifics: **$0.000026/GB-s and $0.40 per million executions** for on-demand instances (with a monthly free grant of 100,000 GB-s and 250,000 executions), and for **always-ready** instances an additional idle-baseline rate of **$0.000004/GB-s** plus a lower execution rate of **$0.000016/GB-s** — the always-ready tier trades a small continuous idle cost for consistently fast response on the first request into an instance. [Azure Functions pricing](https://azure.microsoft.com/en-us/pricing/details/functions/) — accessed 2026-08-08.

### Why Consumption cold starts happen and what actually helps

A cold start on Consumption is the time to: allocate a new sandbox, pull the deployment package, start the language worker process, run any static initialization / dependency-injection container setup, and only then execute the trigger handler. **.NET isolated worker cold starts commonly land in the 2-7 second range**, and heavy dependency-injection graphs or large deployment packages can push this past 10 seconds. [Cold start comparison — DEV Community](https://dev.to/martin_oehlert/scaling-azure-functions-consumption-vs-premium-vs-dedicated-2gm) — accessed 2026-08-08. Practical levers that actually move this number: trimming deployment package size (fewer, smaller dependencies), avoiding synchronous startup work in `Program.cs`/`Startup`, choosing a lighter language runtime (Node/Python typically cold-start faster than .NET or Java for equivalent trivial handlers), and — the structural fix rather than a micro-optimization — moving to Flex Consumption with always-ready instances or to Premium if the workload genuinely cannot tolerate any cold-start variance (a synchronous customer-facing API path being the classic case).

### Bindings — the actual differentiator from Lambda

A **trigger** is the one thing that invokes the function and always carries the triggering payload. **Input bindings** declaratively fetch additional data before your code runs (a Cosmos DB document by ID extracted from the trigger payload, a blob by path). **Output bindings** declaratively write your return value (or an explicit output parameter) to a destination (a queue message, a table row, another Cosmos document) without you writing SDK calls for the plumbing.

```python
# untested sketch — Python v2 programming model
import azure.functions as func
import json

app = func.FunctionApp()

@app.function_name("order-processor")
@app.route(route="orders", methods=["POST"])
@app.cosmos_db_output(
    arg_name="outputDoc",
    database_name="orders_db",
    container_name="orders",
    connection="CosmosDBConnection",
)
@app.queue_output(arg_name="outputQueue", queue_name="fulfillment", connection="StorageConnection")
def process_order(req: func.HttpRequest, outputDoc: func.Out[func.Document], outputQueue: func.Out[str]) -> func.HttpResponse:
    order = req.get_json()
    outputDoc.set(func.Document.from_dict(order))       # writes to Cosmos, no SDK call
    outputQueue.set(json.dumps({"orderId": order["id"]}))  # writes to Storage Queue, no SDK call
    return func.HttpResponse(status_code=202)
```

AWS Lambda's equivalent requires explicit SDK calls (`boto3` PutItem, `sqs.send_message`) inside the handler for the same effect — more code, but also more explicit control and no binding-specific configuration DSL to learn. Lambda's breadth advantage is real: **roughly 200+ native event source integrations** versus Azure's smaller but deeper (within the Microsoft stack) binding catalog, and Lambda's model for streaming sources (DynamoDB Streams, Kinesis) is a genuine **pull** model with configurable batch size and parallelization factor, while Azure's binding-based triggers for equivalent sources (Cosmos DB change feed, Event Hubs) are more of a **push**-oriented abstraction from the developer's point of view even though the underlying mechanics still poll. [Bindings vs event source mapping comparison](https://lumigo.io/learn/lambda-events-and-event-source-mapping-a-practical-guide/) — accessed 2026-08-08.

### Durable Functions — orchestration by replay

The core mechanism: an **orchestrator function** is ordinary-looking code (`async`/`await` in .NET/Python/JS) that calls **activity functions** for actual work. The Durable Task Framework persists every scheduled task and its result as an **append-only history**. Whenever the orchestrator needs to resume (after an activity completes, after a timer fires, after an external event arrives), the framework **replays the orchestrator function from the very beginning**, but instead of re-executing already-completed activity calls, it short-circuits them by returning the recorded result from history instantly — only genuinely new work actually executes. [Durable orchestrations overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-orchestrations) — accessed 2026-08-08.

```python
# untested sketch — Durable Functions Python orchestrator
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    # DETERMINISM RULE: never call datetime.now(), random, or do direct I/O here.
    # Use context.current_utc_datetime instead — it's replay-safe (recorded in history).
    order = context.get_input()

    payment_result = yield context.call_activity("charge_payment", order)
    if not payment_result["success"]:
        return {"status": "failed", "reason": "payment_declined"}

    # fan-out/fan-in pattern
    tasks = [context.call_activity("reserve_item", item) for item in order["items"]]
    reservation_results = yield context.task_all(tasks)

    yield context.call_activity("ship_order", order)
    return {"status": "completed"}

main = df.Orchestrator.create(orchestrator_function)
```

**Why determinism is a hard constraint, not a style guideline:** if the orchestrator called `datetime.now()` directly, the replayed execution (potentially minutes, hours, or days after the original call, on a possibly different worker instance) would compute a *different* value than the original run, and the framework's history-matching logic (which correlates recorded task results to the sequence of calls the orchestrator code makes) can desynchronize — this manifests as `NonDeterministicOrchestrationException`-style errors or, worse, silently wrong behavior where a side effect that should have been skipped (already recorded as complete) re-executes. This is the single most-cited Durable Functions production bug pattern.

### Orchestration versioning

Because in-flight orchestration instances rely on their history matching the *current* orchestrator code's execution path, deploying a code change to an orchestrator function while instances are still running is dangerous — a changed branch of logic can desync an in-flight instance's replay from its recorded history. **Orchestration versioning** (a more recent, actively-evolving feature) lets you tag orchestrator code with a version and route in-flight instances to the version they started on while new instances pick up the latest, avoiding the older workaround pattern of never changing orchestrator code shape and only ever adding new orchestrator function names for breaking changes. [Orchestration versioning — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-orchestration-versioning) — accessed 2026-08-08.

### The canonical Durable Functions patterns

| Pattern | What it does | Analogy |
|---|---|---|
| Function chaining | Sequential activity calls, each depending on the previous result | Basic pipeline |
| Fan-out/fan-in | Dispatch N activities in parallel, wait for all, aggregate | Map-reduce |
| Async HTTP API | Long-running operation returns a status-check URL immediately | Step Functions + API Gateway polling pattern |
| Monitor | Recurring check with a timer-based loop until a condition or timeout | Cron + state machine |
| Human interaction | `wait_for_external_event` pauses until a signal (approval, webhook) arrives, often combined with a timeout | Step Functions callback pattern (`waitForTaskToken`) |

### Cross-cloud mapping

| AWS | Azure | Watch out |
|---|---|---|
| Lambda | Azure Functions | Trigger/binding push model vs Lambda's SDK-call/event-source-mapping pull model |
| Step Functions | Durable Functions | Step Functions is state-machine-first (declarative ASL); Durable Functions is code-first (the orchestrator's code *is* the workflow) |
| Lambda cold start (~100ms-1s typical for small runtimes, more for JVM) | Functions cold start (2-7s+ .NET isolated on Consumption) | Azure Consumption cold starts are generally worse than Lambda's for comparable runtimes; Flex/Premium close this gap at a cost |
| Provisioned Concurrency | Premium plan / Flex always-ready instances | Same purpose (avoid cold start), different billing shape |
| EventBridge/SQS/SNS event sources | Triggers + bindings | Lambda has broader native source count; Azure's bindings are more declarative for the sources it does support |

---

## Build it from scratch

A minimal timer-triggered function demonstrating the binding model end to end, matching the shape in `labs/python/02-functions/`:

```python
# untested sketch — Python v2 programming model, Consumption or Flex plan
import azure.functions as func
import logging

app = func.FunctionApp()

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
@app.blob_output(arg_name="outputBlob", path="reports/{DateTime}.json", connection="StorageConnection")
def generate_report(timer: func.TimerRequest, outputBlob: func.Out[str]) -> None:
    if timer.past_due:
        logging.warning("Timer trigger is past due — likely a cold-start or scaling delay")
    outputBlob.set('{"status": "generated"}')  # output binding writes the blob, no SDK call
```

---

## How it's done in production

A typical production Functions deployment: **Flex Consumption** as the default plan for new event-driven services, with **always-ready instances configured specifically for any function on a customer-facing synchronous path** (an HTTP-triggered API a frontend calls directly) while purely async/queue-triggered functions stay on pure on-demand scaling to save cost. **Premium** is reserved for workloads needing VNet features Flex hasn't yet matched, or genuinely zero-tolerance cold-start requirements at high sustained concurrency. **Durable Functions** orchestrates multi-step business processes (order fulfillment, approval workflows, long-running data pipelines) with activity functions doing the actual I/O-heavy work, deployed with strict discipline around never changing an orchestrator's call sequence without using orchestration versioning or a new function name. **Application Insights** (see `C-AZ-ops`) is wired in from day one since cold-start and durable-replay issues are close to undiagnosable without distributed tracing across the trigger → orchestrator → activity chain.

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency spikes of several seconds on an HTTP-triggered function despite low overall traffic | Consumption plan cold start hitting a request after a scale-to-zero idle period | Move to Flex Consumption with always-ready instances configured, or Premium if zero-tolerance is required |
| `NonDeterministicOrchestrationException` or an activity silently re-executing | Orchestrator code used `datetime.now()`, random, or direct I/O instead of the durable-safe context APIs | Replace with `context.current_utc_datetime`, durable-safe random/GUID helpers, and move all real I/O into activity functions |
| In-flight orchestration instance fails after a deployment | Orchestrator code's call sequence changed while instances mid-flight relied on the old history shape | Use orchestration versioning, or avoid changing an orchestrator's logic shape — add a new function/version instead |
| VNet integration suddenly forces a much higher bill | Team added VNet requirements to a Consumption-plan app and had to move to Premium (pre-Flex) or misconfigured Flex without realizing on-demand vs always-ready cost implications | Confirm Flex Consumption (not Premium) covers the VNet need; only add always-ready instances where cold start genuinely matters |
| Fan-out/fan-in orchestration times out at scale | Too many parallel activity calls scheduled at once, overwhelming the underlying queue/storage provider or hitting per-orchestration history size limits | Batch the fan-out into smaller waves, or use sub-orchestrations to shard a very large fan-out |
| Durable Functions storage costs unexpectedly high | Every orchestration history event is persisted (Azure Storage or the newer Durable Task Scheduler backend); very chatty orchestrators with huge history logs accumulate storage cost and slow replay | Reduce history chattiness (fewer, coarser activity calls), consider the newer Durable Task Scheduler backend, and set appropriate history retention/purge policies |

---

## Tradeoffs & when NOT to use it

- **Don't default to Premium just to avoid cold starts if Flex Consumption's always-ready instances would solve it more cheaply.** Premium's always-on billing floor is a real ongoing cost most workloads don't need to pay.
- **Don't put genuinely long-running, latency-critical synchronous work in Consumption-plan functions.** The 10-minute default timeout and cold-start variance make it wrong for anything beyond quick event-glue or async processing; a container-based service (Container Apps, AKS) or Premium plan is a better fit for sustained, predictable-latency workloads.
- **Don't write orchestrator code as if it's just normal application code.** The determinism constraint is absolute — any team new to Durable Functions needs explicit training on what's forbidden (wall-clock time, randomness, direct I/O, non-durable async calls) before writing production orchestrators.
- **Don't use Durable Functions for simple, single-step processing that doesn't need multi-step state or long-running coordination.** A plain triggered function with bindings is simpler to reason about, debug, and bill for.
- **Don't ignore the binding model's coupling risk.** Heavy reliance on bindings can make a function's actual data flow hard to see without reading configuration alongside code — for complex integration logic, explicit SDK calls (bypassing bindings) sometimes produce more maintainable, testable code despite the extra boilerplate.
- **Don't assume all Durable Functions language SDKs have identical feature parity.** The underlying Durable Task Framework is shared, but specific features (certain patterns, versioning support maturity) can lag between .NET, Python, JS, and Java — verify feature availability for the specific language before committing to a design.

---

## Interview questions

### Q1 — Walk through the three Azure Functions hosting plans and when each is the right call.
**Testing:** whether the tradeoffs are understood as architecture decisions, not memorized pricing tiers.
**Answer:** Consumption scales to zero and is pure pay-per-execution but has no VNet integration and multi-second cold starts, fine for latency-insensitive, low-traffic event processing. Premium eliminates cold starts entirely via always-warm instances and adds VNet integration and longer timeouts, at the cost of paying for provisioned capacity even when idle — right for consistently-loaded, latency-sensitive, or networking-constrained workloads. Flex Consumption (Microsoft's current default recommendation) combines Consumption's scale-to-zero economics with native VNet support and optional always-ready instances configured per-function, closing the gap that used to force teams onto Premium just for networking.
**Follow-up trap:** *"If Flex Consumption can do everything Premium does, why does Premium still exist?"* — Flex hasn't fully closed every gap (certain higher-memory SKUs, some networking edge cases, and guaranteed zero cold start at very high sustained concurrency still favor Premium); the honest answer is "check current docs for the specific capability you need" rather than claiming full parity.

### Q2 — Why do Consumption-plan .NET isolated functions commonly see 2-7 second cold starts, and what actually reduces that number?
**Testing:** mechanical understanding of what a cold start actually is, plus real mitigations vs folklore.
**Answer:** A cold start includes sandbox allocation, pulling the deployment package, starting the language worker process, and running static/DI initialization before the trigger handler runs at all — heavy dependency-injection graphs or large packages push this past 10 seconds. Real levers: trimming package size and dependency count, avoiding synchronous startup work, choosing a lighter runtime for latency-critical paths, and — the structural fix — moving to Flex Consumption with always-ready instances or Premium rather than micro-optimizing Consumption cold starts indefinitely.
**Follow-up trap:** *"Does choosing Python over .NET always fix cold starts?"* — generally Node/Python cold-start faster for trivial handlers, but a Python function with a large dependency tree (heavy ML libraries, for instance) can cold-start just as slowly; runtime choice is a factor, not a guarantee.

### Q3 — Explain Durable Functions' replay mechanism and why orchestrator code must be deterministic.
**Testing:** the core mechanical understanding that separates "used Durable Functions" from "understands Durable Functions."
**Answer:** Every scheduled activity call and its result is persisted as an append-only history. Whenever the orchestrator resumes (an activity completes, a timer fires, an external event arrives), the framework replays the orchestrator function from the start, but short-circuits already-recorded calls by instantly returning their historical result instead of re-executing them — only genuinely new work runs. If the orchestrator's code isn't deterministic (calls `datetime.now()`, generates random values, does direct I/O), a replayed execution can compute different values or take a different code path than the original run, desynchronizing the history match and causing errors or silently wrong behavior, including duplicate side-effect execution.
**Follow-up trap:** *"What's the fix if you genuinely need the current time inside orchestrator logic?"* — use the framework's durable-safe equivalent (`context.current_utc_datetime` / `context.CurrentUtcDateTime`), which is recorded in history on the original execution and returns the same recorded value on every replay, rather than recomputing wall-clock time.

### Q4 — Compare Durable Functions to AWS Step Functions architecturally.
**Testing:** the code-first vs state-machine-first distinction, a common cross-cloud interview probe.
**Answer:** Step Functions is state-machine-first: the workflow is a declarative JSON/Amazon States Language document, with Lambda functions (or other AWS service integrations) as task bodies invoked by the state machine's defined transitions. Durable Functions is code-first: the orchestrator function's actual code — its control flow, branching, loops — *is* the workflow definition, executed via the deterministic-replay mechanism rather than being interpreted from a separate declarative document.
**Follow-up trap:** *"Which is easier to visualize/audit for a compliance team that wants to see the workflow without reading code?"* — Step Functions' declarative ASL is more directly visualizable/diffable as a document; Durable Functions' code-first model requires either reading the orchestrator source or using tooling (like the Durable Functions monitoring extension) to reconstruct the execution graph, a real tradeoff for teams prioritizing auditability over developer ergonomics.

### Q5 — What's the difference between a trigger and a binding, and how does that push-oriented model compare to Lambda's approach?
**Testing:** the specific terminology and mechanical distinction, not just "they're both event stuff."
**Answer:** A trigger is the single event source that invokes the function and always carries the payload; input/output bindings are declarative additional reads/writes configured alongside the trigger — read a Cosmos document by an ID from the trigger payload, write the return value to a queue — without writing SDK calls for that plumbing. Lambda has no equivalent declarative binding layer; equivalent read/write operations require explicit SDK calls (`boto3`, AWS SDK) inside the handler. Azure's model reduces boilerplate for common data-flow shapes at the cost of some data flow being invisible without reading the function's configuration/decorators alongside its code.
**Follow-up trap:** *"Does the binding model reduce Azure's testability compared to Lambda's explicit SDK calls?"* — a legitimate concern: bindings can make unit testing harder since the actual data-access behavior is partly configuration-driven rather than fully visible in code; teams often mitigate this by keeping bindings for simple I/O and using explicit SDK calls for anything with complex conditional logic that needs thorough unit test coverage.

### Q6 — Design an order-fulfillment workflow (charge payment, reserve inventory for N items in parallel, ship, with a human-approval step for high-value orders) using Durable Functions patterns.
**Testing:** synthesizing the canonical patterns into a coherent design.
**Answer:** Function chaining for the payment charge (sequential, must happen first and gate everything else); fan-out/fan-in for parallel inventory reservation across N items, waiting for all reservations before proceeding; the human-interaction pattern (`wait_for_external_event` with a timeout) gating a manual approval step for orders above a value threshold before the final shipping activity call; the async-HTTP-API pattern wrapping the whole thing so the caller gets an immediate status-check URL rather than blocking on the full multi-step process.
**Follow-up trap:** *"What happens if the approval event never arrives?"* — the `wait_for_external_event` call must be paired with a timeout (typically via `task_any` racing the event against a durable timer) or the orchestration instance waits indefinitely, silently consuming storage for its history and never completing — always design an explicit timeout/escalation path for human-interaction patterns.

### Q7 — A team deploys a code change to a Durable Functions orchestrator while there are thousands of in-flight instances. What breaks, and how do you prevent it?
**Testing:** the versioning/in-flight-instance risk, a real production incident pattern.
**Answer:** In-flight instances replay against their recorded history using the *currently deployed* orchestrator code; if the new code changes the call sequence or branching logic an in-flight instance's history doesn't match, the replay can desynchronize, producing errors or, worse, orchestrations silently taking a different path than intended for that instance. Prevention: use orchestration versioning to pin in-flight instances to the code version they started with while new instances pick up the latest, or the older, blunter workaround of never changing an orchestrator's call shape and instead deploying breaking changes as a new function name/version.
**Follow-up trap:** *"Is orchestration versioning available and equally mature across all supported languages?"* — verify current language-specific maturity before promising it in a design; this is exactly the kind of fast-moving feature-parity fact worth a fresh check near an interview date rather than assuming uniform support.

### Q8 — Why does Lambda have a much broader native event-source count than Azure Functions bindings, and does that matter in practice?
**Testing:** honest assessment of the tradeoff rather than reflexive "Azure is deeper, AWS is broader" repetition without substance.
**Answer:** AWS's roughly 200+ native Lambda event source integrations reflect its far larger and older service catalog and Lambda's role as the connective tissue across nearly all of AWS; Azure's binding catalog is narrower but deeper specifically within the Microsoft ecosystem (Cosmos DB, Storage, Service Bus, Event Grid, Event Hubs) with a genuinely different, more declarative developer experience for the sources it covers. In practice it matters most for teams integrating many disparate third-party or less-common AWS services directly via Lambda triggers — Azure teams more often reach for Logic Apps or explicit SDK calls to bridge gaps bindings don't cover.
**Follow-up trap:** *"Can you write a custom binding for a source Azure doesn't natively support?"* — yes, Azure Functions supports open binding extensions that the community and Microsoft partners build, but adopting a third-party binding extension is a real dependency-risk decision, not free — weigh it against just writing an explicit SDK call in the function body.

### Q9 — A fan-out/fan-in Durable Functions orchestration times out when processing 50,000 items in parallel. Diagnose and fix.
**Testing:** the practical scaling limit of the fan-out pattern and the sharding mitigation.
**Answer:** Scheduling 50,000 parallel activity calls from a single orchestrator at once can overwhelm the underlying storage/queue provider backing the Durable Task Framework and can bloat the orchestration's history size, slowing every subsequent replay since the whole history must be walked (even with short-circuiting) on each resume. Fix: shard the work using sub-orchestrations (each handling a smaller batch, e.g., 500-1,000 items), fanning out to sub-orchestrations rather than directly to 50,000 activities, keeping any single orchestration's history to a manageable size.
**Follow-up trap:** *"Does sub-orchestration change the atomicity guarantees of the overall workflow?"* — no inherent change to atomicity, but it does change failure-handling granularity: a failed sub-orchestration needs its own retry/compensation logic rather than relying on the parent orchestrator's error handling to see every individual item-level failure directly.

### Q10 — Your customer-facing HTTP API is built on Azure Functions and product wants sub-200ms p99 latency guaranteed. What plan and configuration do you choose, and what do you tell them about the cost tradeoff?
**Testing:** synthesizing plan choice with a concrete latency SLA and being honest about cost.
**Answer:** Flex Consumption with always-ready instances configured for that specific function (paying the idle-baseline rate to guarantee warm capacity), or Premium if the workload additionally needs VNet integration or has consistently high, predictable load where Premium's always-on cost is justified by simplicity. Pure on-demand Consumption cannot realistically guarantee sub-200ms p99 given multi-second cold-start risk on any scale-to-zero gap; the honest tradeoff to communicate is that guaranteeing no cold start means paying for continuously-provisioned capacity in some form, there's no way to get true scale-to-zero economics and a hard latency SLA simultaneously.
**Follow-up trap:** *"Could autoscaling always-ready instance count based on traffic patterns close this gap cheaply?"* — always-ready instance count can be tuned, but it's a configured floor, not a fully elastic zero-to-N range with zero latency risk at the boundary; a sudden traffic spike beyond the always-ready floor still risks cold starts for the overflow instances until the platform scales further.

---

## Red flags that fail you

- Recommending Consumption plan for a latency-sensitive synchronous customer-facing API without flagging the cold-start risk.
- Not knowing that orchestrator code must be deterministic, or not naming at least one concrete forbidden operation (`DateTime.Now`, random, direct I/O).
- Confusing bindings (declarative I/O plumbing) with triggers (the thing that invokes the function).
- Describing Durable Functions as "just Step Functions but on Azure" without naming the code-first vs state-machine-first distinction.
- Not knowing Flex Consumption is Microsoft's current default recommendation, or recommending Premium reflexively "for production" without justifying why Flex wouldn't suffice.
- Assuming a code change to an orchestrator function is always safe to deploy while instances are in-flight.

---

## Cheat card

```
PLANS:
  Consumption: scale-to-zero, pay/exec+GB-s, NO VNet, 10min default timeout,
    cold start 2-7s+ (.NET isolated), legacy default.
  Premium: always-warm (no cold start), VNet, 60min timeout, pay always (idle too).
  Flex Consumption: scale-to-zero + optional always-ready instances, native VNet,
    1000 instance max scale-out. MICROSOFT'S 2026 DEFAULT RECOMMENDATION.
  Flex pricing: on-demand $0.000026/GB-s + $0.40/M exec (100K GB-s + 250K exec free/mo).
    Always-ready: $0.000004/GB-s idle baseline + $0.000016/GB-s execution.
  Flex instance memory: 512MB / 2048MB (default) / 4096MB.

COLD START FIX LEVERS: trim package size, avoid sync startup/DI work, lighter runtime,
  OR structurally: Flex always-ready instances / Premium.

BINDINGS vs TRIGGERS: trigger = the one thing that invokes + carries payload.
  Input/output bindings = declarative I/O (no SDK calls) configured alongside trigger.
  Lambda equivalent = explicit SDK calls in handler; Lambda has ~200+ native sources
  (broader), Azure bindings are deeper within MS stack (narrower).

DURABLE FUNCTIONS: code-first orchestration (orchestrator code IS the workflow) vs
  AWS Step Functions state-machine-first (declarative ASL, Lambda = task bodies).
  MECHANISM: append-only history + replay. On resume, orchestrator function reruns
  from scratch; already-recorded calls short-circuit to their historical result.

DETERMINISM RULE (hard constraint): NO datetime.now()/random/direct I/O in orchestrator
  code. Use context.current_utc_datetime and durable-safe helpers instead. Violation
  = NonDeterministicOrchestrationException or silently duplicated side effects.

PATTERNS: chaining, fan-out/fan-in, async HTTP API, monitor (timer loop),
  human interaction (wait_for_external_event + timeout via task_any).

VERSIONING: in-flight instances replay against CURRENT deployed code -- changing an
  orchestrator's call sequence mid-flight desyncs history. Use orchestration
  versioning or ship breaking changes as a new function name.

FAN-OUT SCALE LIMIT: very large fan-out (10K+) bloats history + storage provider load
  -- shard via sub-orchestrations into smaller batches instead of one giant fan-out.
```

## Sources

- [Azure Functions Flex Consumption plan hosting — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan) — accessed 2026-08-08
- [Azure Functions Premium plan — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan) — accessed 2026-08-08
- [Pricing — Azure Functions](https://azure.microsoft.com/en-us/pricing/details/functions/) — accessed 2026-08-08
- [Scaling Azure Functions: Consumption vs Premium vs Dedicated — DEV Community](https://dev.to/martin_oehlert/scaling-azure-functions-consumption-vs-premium-vs-dedicated-2gm) — accessed 2026-08-08
- [Durable orchestrations overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-orchestrations) — accessed 2026-08-08
- [Durable orchestrator code constraints — Microsoft Learn](https://learn.microsoft.com/en-us/azure/durable-task/common/durable-task-code-constraints) — accessed 2026-08-08
- [Orchestration versioning in Durable Functions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-orchestration-versioning) — accessed 2026-08-08
- [Lambda Events and Event Source Mapping — Lumigo](https://lumigo.io/learn/lambda-events-and-event-source-mapping-a-practical-guide/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
