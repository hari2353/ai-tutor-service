# Azure Functions Deep: Plans, Cold Starts, Durable Functions, Bindings

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-functions` · **Tags:** serverless,critical

## The 30-second version

Azure Functions has five hosting plans and picking wrong costs either latency or money: the legacy Consumption plan (scale to zero but slow scaling, ~1.5 GB instances, 200-instance ceiling, 10-minute hard timeout) is being replaced by **Flex Consumption** — GA November 2024, Linux-only, per-instance concurrency you configure yourself, per-function scaling groups, VNet integration, up to 1000 instances, and always-ready instances that eliminate cold starts at a flat cost. Durable Functions is the differentiator versus AWS Lambda: orchestrator code replays deterministically so multi-step workflows survive process death, which makes Functions viable for long-running business processes rather than just glue code. The mechanical facts interviewers probe: the ~230-second HTTP response ceiling from the load balancer regardless of your configured timeout, why orchestrators must be deterministic because they replay, and why a queue-triggered function's `MaxDequeueCount` of 5 poisons messages silently if nobody wired a poison-queue handler.

## Why this gets asked

Because Functions is where Azure teams feel platform decisions physically: someone picks Consumption for an internal API, discovers VNet integration isn't possible there, migrates to Premium, and doubles the bill overnight; someone writes an orchestrator that calls `DateTime.Now` and watches workflows corrupt after scale-out; someone's queue consumer falls behind because they assumed each message gets its own instance when the real knob is per-instance concurrency. Interviewers have debugged at least one of these. What separates candidates is knowing the *plan matrix* cold (which features exist where), the *execution lifecycle* (host startup, worker startup, replay), and the honest cold-start economics compared to Lambda — including that Microsoft itself now labels Consumption "legacy" and steers new apps to Flex.

---

## Lineage: past → present → future

**What came before.** Azure WebJobs (2014) ran background code inside App Service sites with a trigger SDK but no independent scaling or per-execution billing; jobs lived and died with the website. Functions launched in 2016 against AWS Lambda's model: Consumption plan, scale-to-zero, per-execution pricing, built on App Service infrastructure but with a scale controller watching event sources. The pain WebJobs couldn't fix — a burst of queue messages did nothing until someone manually scaled the site — drove the design. Durable Functions arrived in 2018 out of the Durable Task Framework to solve the other gap: stateless execution made multi-step workflows an exercise in hand-managed checkpoint tables, so Microsoft embedded a replay-based orchestrator directly into the programming model.

**Where it stands now.** The plan matrix reorganized around Flex Consumption (GA November 2024): it takes what Consumption had (scale to zero, execution billing) and adds what forced people onto Premium — VNet integration, fast scale-out (hundreds of instances per minute), configurable per-instance concurrency, multiple memory sizes (~512 MB / 2048 MB / 4096 MB), per-function scaling groups, and always-ready instances for a zero-cold-start baseline. Microsoft's own docs now label the original Consumption plan "legacy": Linux Consumption stopped getting new features and language versions, and Windows Consumption retires September 30, 2028 — a rare, explicit deprecation clock on the most widely taught plan. Premium (EP series) remains for Windows workloads and cases needing deployment slots; Container Apps hosting covers container-first teams. Durable Functions gained a managed high-throughput backend, the Durable Task Scheduler, superseding both the Azure Storage provider's throughput ceiling and the Netherite experiment. The live disagreement: whether Functions should host APIs at all, or only events — the ~230-second HTTP response limit and concurrency defaults keep pushing latency-sensitive synchronous APIs toward Container Apps/App Service.

**Where it's heading.** High confidence: Flex becomes the default answer and the Consumption plan sunsets quietly by its 2028 date; concurrency-driven scaling (the KEDA mental model) replaces the old "one event = one instance" intuition everywhere; OpenTelemetry output becomes the standard telemetry path. Medium confidence: deeper integration between durable execution and agent orchestration — the replay model maps cleanly onto multi-step LLM agents, and Microsoft explicitly courts that use case. Speculative: snapshot-assisted cold starts across more runtimes on Flex, and end-to-end TLS between platform front ends and workers graduating from preview. Don't build interview answers on the speculative items.

---

## Mental model

One function app instance is a pipeline of three processes, and the plan decides how many pipelines exist:

```
                    +----------------------------------------------+
 EVENT SOURCE       | INSTANCE (a worker sandbox)                  |
 (queue/http/grid)  |                                              |
      |             |  HOST (Functions runtime, gRPC dispatcher)   |
      v             |    |                                         |
 SCALE CONTROLLER --+--->v                                         |
 watches event      |  WORKER (your language process: Python,      |
 depth & lag        |   Node, .NET isolated...) loads functions    |
                    |    |                                         |
 adds instances     |    v                                         |
 when lag > target  |  BINDINGS: trigger in -> your fn -> outputs  |
                    |   (declarative I/O declared per function)    |
                    +----------------------------------------------+

 CONSUMPTION/FLEX/PREMIUM differ in:
   instance size · max instances · concurrent invocations per instance ·
   VNet support · slots · billing model
```

Durable Functions overlays a second axis:

```
 Orchestrator (deterministic, REPLAYS)     Activity (does real work)
   code runs many times,                     runs once per unit,
   must produce same calls                   scales horizontally,
   on every replay                           any language
        |                                            |
        +----------- task hub (queues + history store) -+
```

**The one-liner that matters:** the scale controller reads *event lag*, not CPU; and an orchestrator is a state machine wearing a for-loop costume — every await boundary is both a checkpoint and a replay point.

---

## How it actually works

### Plan matrix — the numbers that decide designs

| | Consumption (legacy) | Flex Consumption | Premium (EP) | Dedicated | Container Apps |
|---|---|---|---|---|---|
| Scale to zero | Yes | Yes | No (~1 warm min) | No | Yes |
| Max instances | 200 | 1000 (default cap 100) | plan burst, EP-tier ~20-100 | ~20-30 typical | up to ~1000 replicas |
| Memory/instance | ~1.5 GB fixed | ~512 MB / 2048 MB / 4096 MB | 3.5-14 GB | varies | varies |
| Timeout default/max | 5 / 10 min | 30 min / unbounded* | 30 min / unbounded* | 30 / unbounded (Always On) | 30 min / unbounded |
| Per-instance concurrency | ~1 (language-dependent) | user-configured | varies | varies | KEDA rules |
| VNet integration | No | Yes | Yes | Yes | Yes |
| Deployment slots | Limited (2) | No (update strategies instead) | Yes (up to ~20) | Yes | revisions |
| Billing | executions + GB-s | execution time + always-ready memory | core-seconds, no exec charge | App Service plan | per-app |

\* "Unbounded" still means: ~60-minute grace during scale-in, ~10-minute grace during platform updates, and idle workers stop after 60 minutes with no executions.

Three ceilings override everything above for HTTP workloads:

1. **~230 seconds** maximum for an HTTP-triggered function to respond — the Azure Load Balancer idle timeout. A 10-minute `functionTimeout` does not help an HTTP caller waiting past 230 s; use the Durable async pattern (return 202 + status URL) or defer work and return immediately.
2. **60 seconds** for the language worker process to start inside a fresh instance — not configurable; dependency trees exceeding this fail health checks permanently.
3. On Flex, a **30-second** host initialization timeout — apps doing heavy startup log gRPC-related `System.TimeoutException` noise.

### Cold starts, honestly

Consumption-plan cold starts are real and runtime-dependent: ballpark figures are roughly ~0.5-2 s for lean Node/.NET-isolated apps and ~2-5+ s for Python or dependency-heavy apps on a fresh instance, worst right after deploys and traffic gaps — measure your own; these move with every runtime release. Mitigations ladder: keep packages small, avoid heavy module-scope work, use Premium's prewarmed instance (always at least one allocated, billed continuously), or Flex's always-ready instances (billed as provisioned memory whether hit or not). The structural difference from AWS Lambda: Azure has not shipped a SnapStart-equivalent snapshot restore across runtimes for Functions, so JVM-heavy apps remain a reason teams pick Container Apps instead.

### Concurrency — where Azure diverges from Lambda's mental model

On legacy Consumption most triggers effectively process one event per instance (Python historically enforced concurrency 1), so scaling math is "events divided by 1." Flex flips this: **you set per-instance concurrency**, and desired instances equal `events / concurrency`, bounded by a scale curve (fast at low instance counts, deliberately throttled burst batches at high counts) and your maximum instance count applied per function group. Default HTTP concurrency by instance size: 4 at 512 MB, 16 at 2048 MB, 32 at 4096 MB — except Python, which defaults to 1 until you opt in. This changes downstream sizing arithmetic: N instances at concurrency C need up to N x C database connections; forgetting the multiplication is the classic outage after migrating Consumption → Flex. Non-HTTP triggers follow target-based scaling with their own per-trigger concurrency knobs (`MaxConcurrentCalls` for Service Bus, partition count for Event Hubs).

### Bindings and triggers

Bindings are declarative I/O contracts (attributes in code, historically `function.json`): a trigger starts execution, input bindings fetch data, output bindings write results, delivered by extension bundles (`[4.0.0, 5.0.0)` currently for non-.NET on Flex). Two operational truths:

- **Polling triggers carry hidden storage costs.** The legacy Blob trigger polls a container-metadata structure, adding up-to-10-minute latency and real storage-transaction charges on churny containers. The Event Grid-based blob trigger is near-instant — and on Flex it is the only supported blob source.
- **Queue semantics:** Storage Queue triggers dequeue in batches, extend visibility locks while work continues, and move messages to `<queue>-poison` after `MaxDequeueCount` (default 5) failed attempts. Nothing alerts you about poison messages unless you build that handler — silent data loss is the default outcome.

### Durable Functions mechanics

Orchestrator code is not executed once — it **replays**: each time the orchestration resumes after an activity completes, the orchestrator re-runs from the start, skipping completed work using recorded history. Therefore orchestrators must be deterministic: no direct I/O, no `random`, no wall-clock reads (use the orchestration context's current-time property), no threading. Activity functions do actual work as ordinary stateless functions. Entity functions serialize access per entity (single-threaded per actor) and batch operations — batch cap 50 on Consumption, 5000 elsewhere.

State lives in a **task hub**: on the Azure Storage provider that means queues + tables + blobs, whose throughput ceiling becomes your workflow ceiling. For heavier loads, the **Durable Task Scheduler** (managed backend, Event Hubs-partitioned) removes that ceiling; on Flex, Azure Storage and DTS are the only supported providers. Fan-out/fan-in stresses providers hardest: thousands of parallel activities converge through a single orchestrator instance at fan-in, so extended sessions (`extendedSessionIdleTimeoutInSeconds`) keep mid-flight orchestrators warm in memory to cut replay overhead.

```python
# untested sketch — canonical chain with retry, showing replay-safe style
import azure.durable_functions as df

def orchestrator(context):
    # deterministic: read time ONLY from context; never datetime.now()
    order = yield context.call_activity("ValidateOrder", context.input)
    payment = yield context.call_activity_with_retry(
        "ChargeCard", df.RetryOptions(5000, 3), order["id"])
    yield context.call_activity("ShipOrder", {"order": order, "payment": payment})
    return "done"

main = df.Orchestrator.create(orchestrator)
```

### Pricing mechanics worth quoting

Consumption bills ~$0.20 per million executions plus ~$0.000016 per GB-second with monthly free grants. Flex bills execution time with a 1000 ms minimum billable execution rounding up per 100 ms afterward, plus flat-charged always-ready instance memory. Premium bills pure core-seconds with no per-execution charge and a floor of one always-billed instance — which is exactly why "we moved everything to Premium to kill cold starts" can multiply costs for spiky traffic: you pay continuous compute to simulate always-on capacity.

---

## Build it from scratch

A queue processor demonstrating concurrency accounting and poison handling — the parts everyone gets wrong:

```python
# untested sketch — local simulation of Functions' queue-loop semantics
import json, time
from collections import deque

class FakeQueue:
    def __init__(self): self.messages = deque(); self.poison = deque()
    def enqueue(self, body): self.messages.append({"body": body, "dequeues": 0})

def run_worker(q: FakeQueue, handler, max_dequeue_count: int = 5,
               concurrency: int = 4):
    """Mirrors host behavior: bounded concurrent processing,
    retry-on-failure, poison after MaxDequeueCount attempts."""
    attempts = {}
    while q.messages:
        batch = [q.messages.popleft() for _ in range(min(concurrency, len(q.messages)))]
        for msg in batch:
            attempts[msg["body"]] = attempts.get(msg["body"], 0) + 1
            try:
                handler(msg["body"])
            except Exception:
                if attempts[msg["body"]] >= max_dequeue_count:
                    q.poison.append(msg)          # SILENT unless monitored
                else:
                    q.messages.append(msg)        # visible again after lock expiry

if __name__ == "__main__":
    q = FakeQueue()
    for i in range(10):
        q.enqueue(json.dumps({"n": i}))

    def flaky(body):
        if json.loads(body)["n"] == 3:
            raise RuntimeError("transient")
    run_worker(q, flaky)
    print("poisoned:", [m["body"] for m in q.poison])   # n=3 lands here after 5 tries
```

Deploying the real equivalent (Function App + Storage Queue) and watching the `-poison` queue fill is the fastest way to internalize why alerting on it is non-negotiable.

## How it's done in production

Standard stack: Flex Consumption for new event-driven and HTTP services (VNet-integrated through subnets delegated to `Microsoft.App/environments`), Premium EP-series where Windows in-process .NET or deployment slots are required, Durable Functions on the Durable Task Scheduler for multi-step workflows, Application Insights via the OpenTelemetry path for tracing, zip deploy/remote build through CI with federated credentials. Guardrails that matter: set `maximumInstanceCount` below what downstream infrastructure absorbs (instances x concurrency connections); configure per-trigger concurrency deliberately rather than accepting defaults; alert on queue depth AND poison-queue depth; pin extension bundle versions; and treat deployment-slot-free Flex deploys with canary traffic strategies (traffic-weighted site update) since rollback is a redeploy.

| Symptom | Cause | Fix |
|---|---|---|
| p99 spikes only right after each deploy | All traffic lands on cold instances of the new revision | Always-ready instances on Flex sized to baseline; warm-up invocation in the pipeline |
| Queue lag grows despite "scaling" working | Concurrency raised but downstream DB connection pool exhausted (instances x concurrency) | Lower concurrency or cap `maximumInstanceCount`; pool per instance sized to C |
| Messages vanish with no errors logged | Poison queue after 5 failed dequeues, nobody watching | Alert on `<queue>-poison` depth; add a poison handler with dead-letter persistence |
| Orchestrations corrupt or duplicate side effects after scale-out | Non-deterministic orchestrator (`datetime.now()`, random, direct I/O) inside replayed code | Move all I/O to activities; use orchestration context time; version orchestrators safely |
| HTTP calls fail at exactly ~4 minutes under load | ~230 s LB idle timeout exceeded by slow function | Return 202 + Durable status URL; make work async instead of extending timeout |
| Bill tripled after migrating off Consumption | Premium floor: minimum one always-billed instance per plan, no execution charge model mismatch | Right-size EP SKU; move spiky low-traffic apps back to Flex; keep Premium only where slots/Windows needed |
| Blob-triggered functions delayed up to 10 minutes | Legacy polling blob trigger on a churny container | Switch to Event Grid-based blob trigger (mandatory on Flex) |
| gRPC `System.TimeoutException` noise on startup | Flex host init exceeds its 30-second budget | Trim heavy startup work; move initialization into first execution or background init |

---

## Tradeoffs & when NOT to use it

- **Not for latency-critical synchronous APIs without mitigation.** Cold starts plus front-end queuing make p99 unpredictable; if you need single-digit-ms tails, Container Apps/App Service with min-replica floors beat any Functions plan.
- **Not for GPU inference or huge models.** No GPU plans; loading multi-GB weights per cold instance is an anti-pattern — use AKS/Container Apps with GPU nodes or managed AI endpoints.
- **Durable Functions is not Step Functions.** It is code-first and lives inside your deploy unit, which is great for versioning logic with tests, but it couples workflow state to your storage account/scheduler capacity and makes cross-team workflow visibility harder than a standalone orchestrator product. If workflows are owned by multiple teams or need audit-grade visualization, that's a real argument for a dedicated orchestration tier.
- **Flex's Linux-only constraint is a hard blocker** for Windows-dependent .NET (in-process, COM interop); those stay on Premium/Dedicated regardless of Flex advantages.
- **Don't use Consumption for anything needing VNet-private egress.** No VNet support means public endpoints for every dependency; if compliance requires private connectivity, the plan decision is already made for you.
- **Be honest about always-ready/prewarmed costs:** they convert serverless back into reserved capacity for whatever fraction you provision. Provisioning peak "just in case" erases the economic reason you chose Functions.

---

## Interview questions

### Q1 — Compare the hosting plans and name the one you'd pick for a new event-driven service in 2026.
**Testing:** currency (Consumption is legacy) plus feature-matrix fluency.
**Answer:** Flex Consumption: GA November 2024, scale-to-zero with fast concurrency-driven scaling, per-function scaling groups, VNet integration, up to 1000 instances (default cap 100), instance sizes around 512 MB/2048 MB/4096 MB, always-ready instances for cold-start elimination. Legacy Consumption is explicitly deprecated-track (Windows retires Sep 30, 2028); Premium for Windows/.NET-in-process or slots; Dedicated for App Service-plan consolidation; Container Apps hosting when the team ships containers.
**Follow-up trap:** *"What do you give up choosing Flex?"* — Windows runtimes, deployment slots (traffic-strategy replaces them), PowerShell managed dependencies, and non-Event-Grid blob triggers; also one app per plan.

### Q2 — Explain what happens mechanically on a cold start and what actually shortens it.
**Testing:** lifecycle understanding beyond buzzwords.
**Answer:** Platform allocates a sandbox from pre-warmed pools, pulls your deployment content, starts the Functions host (~30 s budget on Flex), starts the language worker (60 s hard limit), loads your bindings/extensions, then invokes. What shortens it: smaller dependency footprint, deferring module-scope work, always-ready/prewarmed instances (Premium/Flex), and staying on lean runtimes. There is no SnapStart-style snapshot restore for Azure Functions today.
**Follow-up trap:** *"Why not just set a timer ping to keep it warm?"* — warm-up pings fight the platform: they cost executions, don't survive scale-out events (new instances are still cold), violate no-guarantee-warm semantics, and always-ready instances exist precisely because self-pinging is unreliable.

### Q3 — Your orchestrator produced duplicate charges after a scale-out event. Diagnose.
**Testing:** replay semantics internalized, not memorized.
**Answer:** Something non-deterministic ran inside orchestrator code — wall-clock reads, GUID generation, direct HTTP — so different replays took different paths and the history log diverged from actual activity calls, causing re-execution of steps believed incomplete. Or: activities weren't idempotent and a retry after a timeout re-charged. Both fixes: strict determinism discipline in orchestrators (context-provided time, no I/O), idempotency keys on payment-touching activities.
**Follow-up trap:** *"How do you fix existing corrupted instances?"* — you can't rewrite history in place; terminate and restart with a new orchestrator version (versioning matters), then reconcile externally via the idempotency ledger rather than trusting the framework to unwind charges.

### Q4 — Walk through queue message lifecycle including failure. Where does data get lost?
**Testing:** poison semantics and observability gaps.
**Answer:** Dequeued (often batched), visibility lock held and extended during processing; success removes the message; failure increments dequeue count and requeues after lock expiry; after MaxDequeueCount (default 5) the message moves to `<queue>-poison`. Loss point: everything in the poison queue that nobody consumes — plus messages whose processing succeeded but acknowledgment failed, producing duplicates (at-least-once). So handlers must be idempotent AND poison queues monitored.
**Follow-up trap:** *"Does increasing visibility timeout help?"* — only for genuinely long processing exceeding the lock; the host auto-renews locks while making progress, so mis-sized timeouts mostly matter when the process dies mid-message — then the wait-to-retry equals remaining lock time.

### Q5 — Why is there a ~230-second ceiling on HTTP responses and how do you design around it?
**Testing:** platform-boundary awareness versus config-only thinking.
**Answer:** The Azure Load Balancer idle timeout terminates inbound HTTP flows around 230 seconds regardless of function timeout settings. Design: return immediately (202 Accepted) with a status endpoint — the Durable Functions async HTTP API pattern does this natively — or push work to a queue and let clients poll/webhook. Raising `functionTimeout` never lifts this; it only bounds execution, not response.
**Follow-up trap:** *"Does this apply behind Front Door/Application Gateway too?"* — those add their own shorter timeouts (App Gateway default ~4 min configurable; FD default ~100 s request timeout), so the outermost edge usually dominates; design to the smallest timeout in the chain.

### Q6 — Consumption vs Premium vs Flex cold-start economics: when is paying Premium actually cheaper?
**Testing:** real cost modeling, not plan-marketing.
**Answer:** Premium charges continuous core-seconds (min one instance) but zero per-execution; Consumption/Flex charge per execution-time with free allowances. For steady high invocation rates, per-execution+duration pricing can exceed a small always-on EP1; for bursty-low traffic, always-on floor wastes money. Flex adds a middle path: zero baseline unless you buy always-ready memory. Do the multiplication with your own traces: avg duration x monthly invocations vs plan hourly rate.
**Follow-up trap:** *"Where do people forget a cost line?"* — always-ready/provisioned memory billed 24/7 whether invoked, storage transactions from polling triggers, and bandwidth/NAT when VNet-integrated.

### Q7 — How does per-instance concurrency change your architecture when migrating Consumption → Flex?
**Testing:** the multiplication everyone misses.
**Answer:** Instance count drops roughly by factor C (concurrency), so downstream connections become N x C instead of N x 1 — databases, HTTP pools, and rate-limited APIs feel the same aggregate load but concentrated differently; Python apps default to C=1 until configured, so naive migration leaves throughput unchanged while billing shifts. Also scaling decisions now derive from events-per-concurrency against a scale curve, so burst behavior differs from old depth-threshold triggers.
**Follow-up trap:** *"Which trigger resists concurrency increases?"* — Event Hubs: partition count caps parallelism per consumer group; extra concurrency slots idle. Raise partitions (premium/dedicated tiers allow post-create changes) before raising C.

### Q8 — When would you choose Durable Functions over a workflow engine like Temporal or Logic Apps?
**Testing:** honest ecosystem judgment.
**Answer:** Durable wins when workflows are code-owned, versioned with the service, low-operational-overhead matters, and volumes fit provider limits — it's already in your Function App with no extra control plane. Temporal wins on cross-service durability guarantees, richer retry/versioning semantics, language SDK parity, and very high throughput histories. Logic Apps wins for citizen-developer integration catalogs, not engineering-owned flows. Durable's weak points: task-hub storage ceilings on the Azure Storage provider (mitigate with DTS), fan-in bottleneck through one orchestrator, and coupling workflow state to your app's deploy unit.
**Follow-up trap:** *"What's your escape hatch if outgrowing it?"* — keep activities as plain functions callable anywhere, treat orchestrator definitions as disposable state machines, export history periodically; the activity layer ports to Temporal workers nearly 1:1.

### Q9 — Design a nightly report pipeline: fetch 50k rows, transform, email per tenant. Functions-appropriate?
**Testing:** matching workload shape to platform limits.
**Answer:** Yes with Durable fan-out/fan-in: one starter gets total count, orchestrator chunks into batches (e.g., 500-row activities), fan-out transforms in parallel, fan-in aggregates, per-tenant emails as final activities with retry policies. Watch: fan-in memory (aggregate incrementally via entity), task-hub throughput (DTS if >few hundred ops/s sustained), and total runtime well under timeouts since orchestrator checkpoints persist across instances anyway. Alternative honesty: a plain container job might be simpler if this is strictly batch with no event triggers.
**Follow-up trap:** *"Why chunk rather than one 50k-row activity?"* — checkpoint granularity: one giant activity restarts from zero on any failure and risks the 10-minute consumption ceiling; 500-row units bound rework and enable parallelism.

### Q10 — Someone proposes running an LLM agent loop (multi-step tool calling, minutes-long turns) in a plain HTTP-triggered Function. Critique.
**Testing:** applying durable-execution concepts to his agentic-AI domain.
**Answer:** Wrong shape twice over: synchronous HTTP hits both the ~230 s response ceiling and cold-start tail latency mid-loop; and a crash at step 7 of 10 loses all progress because nothing checkpoints. Right shape: Durable orchestrator per agent turn (each tool call an activity, LLM calls activities with retries), client polls status URL; or dedicated agent frameworks on Container Apps with externalized state. Cost note: token spend makes retries expensive, so activity-level idempotency plus conservative retry budgets matter more than in typical integrations.
**Follow-up trap:** *"Why not just raise timeouts and accept it?"* — you can't raise past ~230 s for the response, and even server-side completion becomes unobservable to the caller; plus a mid-loop crash still discards paid-for LLM output, which is the expensive part.

### Q11 — What monitoring exists for scale behavior, and what would you alert on?
**Testing:** operational maturity.
**Answer:** Azure Monitor metrics: `FunctionExecutionCount`, `FunctionExecutionUnits`, `Concurrency` (per-function on Flex), plus plan-level instance counts; Application Insights gives per-invocation durations, failures, dependency calls; scale controller logs (infrastructure-level) show scale decisions. Alerts: queue depth trend, poison-queue depth >0, throttle/429 responses, host health monitor restarts, and downstream saturation signals since Functions will happily overload dependencies within its own limits.
**Follow-up trap:** *"Why can't you see scale controller decisions in App Insights?"* — scaling telemetry is infrastructure-plane, emitted to specific categories/log streams rather than application telemetry; teams routinely miss that split and conclude "it didn't scale" when evidence lives elsewhere.

### Q12 — Rank these Functions risks by real-world incident frequency and justify: cold starts, poison queues, non-deterministic orchestrators, downstream connection exhaustion.
**Testing:** prioritization judgment.
**Answer:** 1) Downstream connection exhaustion — silent until outage, triggered by ordinary growth, amplified by concurrency changes. 2) Poison queues — constant low-grade data loss because defaults hide them. 3) Non-deterministic orchestrators — rarer but catastrophic and hard to untangle. 4) Cold starts — annoying, usually absorbed, rarely incidents once mitigations applied. Ranking inverts marketing attention: cold starts get blog posts; connection math causes outages.
**Follow-up trap:** *"What single guardrail prevents most of #1?"* — enforce `maximumInstanceCount` x concurrency below the dependency's connection/throughput budget in IaC review — a two-line policy check that catches the whole class before deploy.

---

## Red flags that fail you

- Recommending legacy Consumption plan for new workloads in 2026, or not knowing it's on a deprecation track (Windows: Sep 30, 2028).
- Claiming Functions has SnapStart-equivalent JVM snapshotting.
- Saying "raise the timeout" to fix slow HTTP responses (the ~230 s LB limit).
- Writing orchestrator examples containing `datetime.now()` or direct I/O.
- Not knowing poison queues exist or claiming Storage Queues are exactly-once.
- Assuming one message always equals one instance (ignores concurrency knobs).
- Migrating to Flex unaware it's Linux-only with no slots.
- Pricing answers that ignore always-ready/prewarmed continuous costs.

---

## Cheat card

```
PLANS (2026): Flex Consumption = default new choice (GA Nov 2024, Linux ONLY, 1 app/plan)
  legacy Consumption: Windows retires 2028-09-30 · Linux frozen · max 200 inst · ~1.5 GB
  Premium EP1-3: 3.5-14 GB · >=1 always-billed inst · no exec charge · slots
  Dedicated = App Service plan · Container Apps hosting = KEDA + revisions

TIMEOUTS: default 30 min (Flex/Prem/Dedicated/CA) · Consumption 5 default / 10 max
  unbounded plans still bounded: ~60 min scale-in grace, ~10 min platform-update grace
  HTTP RESPONSE CEILING ~230 s (Azure LB idle) -> return 202 + poll, don't raise timeout
  worker start 60 s hard · Flex host init 30 s

FLEX NUMBERS: max instances 1000 (default cap 100) · sizes ~512 MB/2048 MB/4096 MB
  HTTP concurrency defaults: 4 / 16 / 32 by size (Python = 1 until set)
  per-FUNCTION scaling groups (HTTP together, Durable together, others independent)
  always-ready instances = flat-billed warm capacity · min billable exec 1000 ms, rounds 100 ms

BINDINGS: extension bundle [4.0.0,5.0.0) on Flex · Blob trigger MUST be Event Grid-sourced there
  legacy polling blob trigger: up to ~10 min delay + storage tx costs
  Storage Queue: MaxDequeueCount 5 -> <queue>-poison SILENTLY · at-least-once => idempotency

DURABLE: orchestrator REPLAYS -> deterministic only (no I/O/random/wall-clock; ctx time)
  activity = real work · entity = single-threaded actor, op batch 50 (Consumption) / 5000 else
  task hub providers: Azure Storage (queues+tables+blobs, throughput ceiling)
    vs Durable Task Scheduler (managed, Event Hubs-backed) — only these two ON FLEX
  fan-in funnels through ONE orchestrator instance · extended sessions cut replay cost

PRICING ~: Consumption $0.20/M exec + $0.000016 GB-s · Flex = exec time + always-ready mem
  Premium = core-seconds floor (min 1 inst) — can COST MORE than consumption at high volume

PICK ELSEWHERE WHEN: p99-critical API, GPU inference, huge model loads, Windows-only deps
ALERT ON: poison depth > 0 · queue lag · 429s · instances x concurrency vs DB budget
```

## Sources

- [Azure Functions Flex Consumption plan hosting — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan); accessed 2026-08-23
- [Azure Functions scale and hosting options — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale); accessed 2026-08-23
- [Azure Functions Flex Consumption is now generally available — Microsoft Tech Community](https://techcommunity.microsoft.com/blog/appsonazureblog/azure-functions-flex-consumption-is-now-generally-available/4298778); accessed 2026-08-23
- [Azure Functions Premium plan — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/functions-premium-plan); accessed 2026-08-23
- [Event-driven scaling in Azure Functions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/event-driven-scaling); accessed 2026-08-23
- [Concurrency in Azure Functions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/functions-concurrency); accessed 2026-08-23
- [Performance and scale in Durable Functions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-functions/durable-functions/durable-functions-perf-and-scale); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
