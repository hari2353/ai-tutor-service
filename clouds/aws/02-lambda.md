# Lambda Deep: Execution Model, Cold Starts, SnapStart, Concurrency, VPC

> **Track:** C-AWS AWS Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-lambda` · **Tags:** serverless,critical

## Why this gets asked

The interviewer has shipped a Lambda-based system that either fell over under a traffic spike because of a concurrency limit nobody budgeted for, or got expensive because someone treated it like a general-purpose compute platform for a steady 24/7 workload. Lambda's pricing and execution model reward bursty, short, stateless work and punish everything else, and a candidate who can only recite "it's serverless, it auto-scales" has never operated one past a toy demo. The real test is whether you can reason about the execution lifecycle precisely enough to explain *why* a cold start happens, what specifically fixes it, and — the higher-signal question — when Lambda is architecturally the wrong tool even though it would technically work.

---

## Lineage: past → present → future

**What came before.** Before Lambda (launched 2014), "serverless" for event-driven glue meant a permanently-running EC2 instance or worker fleet polling a queue, paying for idle capacity between events, and owning patching, scaling, and capacity planning for something that might run for 50ms a few times a minute. Lambda's pitch was directly against that waste: pay per invocation, scale to the event rate automatically, no server to patch. The pain it killed was operational — teams were running fleets sized for peak load that sat at 5% utilization the rest of the time.

**Where it stands now.** Lambda is the default choice for event-driven glue (S3 triggers, API Gateway backends under moderate load, stream processors) and increasingly for lightweight synchronous APIs, but the industry has learned its limits the hard way: 15-minute max duration, cold starts under specific runtime/traffic patterns, and a pricing curve that inverts against containers once concurrency and duration both climb. SnapStart (Java 2023, Python/.NET GA 2024–2025) addressed the worst cold-start offender — the JVM — by snapshotting a fully-initialized execution environment rather than re-running init from scratch. The live disagreement is where the line sits between "use Lambda" and "use Fargate/ECS": there's no universal answer, and reasonable engineers land differently based on traffic shape, team Kubernetes fluency, and how much the workload's dependencies weigh.

**Where it's heading.** Direction of travel: shrinking the cold-start gap between Lambda and always-on compute for more runtimes (SnapStart's expansion), and continued growth of Lambda as the execution substrate *inside* agentic AI systems for short tool calls, while AWS pushes long-running or GPU-bound inference toward SageMaker, Fargate, or Bedrock instead — treat "Lambda for LLM inference" as a documented anti-pattern, not a coming trend. Confidence: high that the 15-minute ceiling stays a hard architectural boundary rather than being lifted, because it's core to how Lambda multiplexes capacity across tenants.

---

## Mental model

One execution environment goes through three phases, and only one of them is billed the way people assume:

```
COLD START                                        WARM PATH
┌─────────────┐   ┌─────────────┐   ┌──────────┐  ┌──────────┐
│ Download    │──▶│ INIT        │──▶│ INVOKE   │─▶│ FREEZE   │
│ code/image, │   │ (runtime    │   │ (handler │  │ (paused, │
│ start       │   │ bootstrap + │   │ runs)    │  │ reused   │
│ execution   │   │ global-scope│   │          │  │ for next │
│ environment │   │ code runs   │   │          │  │ invoke)  │
└─────────────┘   └─────────────┘   └──────────┘  └──────────┘
      ▲                                                 │
      │                                                 ▼
      └──────────────── THAW (skips INIT) ◀── next invocation arrives before freeze times out
```

**What "warm" actually means:** the execution environment (a microVM, via Firecracker) persists between invocations for some AWS-controlled window (typically tens of minutes of inactivity, not officially guaranteed). A warm invocation skips download and INIT entirely and jumps straight to INVOKE — this is why anything you put at module/global scope (DB connections, SDK clients, loaded ML weights) only pays its cost once per environment lifetime, not once per invocation. Global-scope code is the single highest-leverage cold-start lever most people ignore.

---

## How it actually works

### Cold start numbers, by runtime — know these cold

| Runtime | Typical p50 cold start | Notes |
|---|---|---|
| Python (no SnapStart) | ~200–400ms | Depends heavily on package size and imports |
| Node.js (no SnapStart) | ~200–350ms | Similar profile to Python |
| Java, no SnapStart | 5–15s+ | JVM startup + class loading dominates |
| Java, with SnapStart | 90–140ms | Snapshot-restore instead of cold JVM boot |
| Python/Node on arm64 (Graviton) | under 200ms | 15–40% faster than x86 across the board |

[AWS Lambda Cold Start Optimization in 2026 — SnapStart, Graviton](https://viprasol.com/blog/aws-lambda-cold-start-optimization/) — accessed 2026-08-01. AWS's own published data: under 1% of invocations experience a cold start in typical production traffic patterns, concentrated in low-traffic functions and the first invocation after a deploy.

### SnapStart — what it actually does and its current scope

SnapStart takes a snapshot of memory and disk state *after* your init code has already run once, caches it, and on subsequent cold starts restores from that snapshot instead of re-executing init from zero. This is why Java goes from 5s+ to 90–140ms: the JVM has already warmed up, classes are already loaded, and the snapshot resumes mid-flight.

**Current runtime support (verify before an interview, this expands):** Java 11+, and as of the Python/.NET GA announcement, **Python 3.12+** and **.NET 8+**, with C#, F#, and PowerShell also covered under the .NET GA. [SnapStart for Python and .NET GA](https://aws.amazon.com/blogs/aws/aws-lambda-snapstart-for-python-and-net-functions-is-now-generally-available/) — accessed 2026-08-01. Regional rollout matters: it launched in a subset of regions and expanded to **23 additional regions** for Python/.NET as of mid-2025 — check current region coverage before assuming it's available everywhere.

**The catch that trips people up:** SnapStart snapshots include things like random seeds, cached credentials, and unique identifiers generated during init, all of which would be *identical* across every cold start restored from the same snapshot unless you explicitly re-randomize/re-fetch them in a runtime hook (`beforeCheckpoint`/`afterRestore` for Java). Skipping this produces subtle bugs: every "cold-started" invocation getting the same random UUID, or a credential that was fresh at snapshot time now being stale.

### The VPC cold-start penalty — mostly fixed, know the history

Before September 2019, attaching a Lambda function to a VPC meant creating and attaching an ENI *per execution environment*, which took 10–15 seconds and was the single biggest cold-start complaint about Lambda. The **Hyperplane** networking change moved to a model where ENIs are pre-created per subnet+security-group combination and shared across many execution environments, collapsing that per-invocation cost to milliseconds. [Improved VPC networking for Lambda](https://aws.amazon.com/blogs/compute/announcing-improved-vpc-networking-for-aws-lambda-functions/) — accessed 2026-08-01. **Current state: VPC attachment adds well under 50ms to cold start and is no longer a meaningful factor** — if an interviewer or a candidate still cites "VPC = 10 second cold start," that's a stale 2018-era answer. What VPC *does* still cost you: a NAT Gateway (or NAT instance) if the function needs internet egress from inside the VPC, at both a per-hour and per-GB-processed charge, and the operational overhead of subnet IP exhaustion at scale if you under-provision the subnet.

### Concurrency model

- Every simultaneous invocation of any function in a region draws from one **account-level concurrency pool**, default limit is a soft quota, historically 1000 concurrent executions per region, adjustable via a support ticket — new accounts sometimes start with a *lower* default (seen as low as 10) until AWS auto-raises it based on usage history. [Lambda concurrency limits](https://repost.aws/questions/QUCK1Z9TPkSzKgyUC0xnx9Dw/how-to-set-a-lambda-quote-template-to-the-previous-default-of-1000) — accessed 2026-08-01. Verify your account's actual current quota before assuming 1000.
- **Reserved concurrency** sets both a floor and a ceiling for one function: it guarantees that capacity is always available to it and simultaneously caps it from consuming more, protecting other functions in the account from being starved.
- **Provisioned concurrency** pre-initializes N environments so they're always warm, eliminating cold starts for that slice of traffic at a continuous hourly cost regardless of invocation volume — you can configure up to (account concurrency minus 100 reserved for other functions) as provisioned concurrency for one function.
- Exceeding available concurrency produces **throttling** (`429 TooManyRequestsException` for sync invokes), not a queue — the caller must handle retry/backoff itself for synchronous paths.

### Event source mappings, batching, partial failures

Lambda polls certain sources (SQS, Kinesis, DynamoDB Streams, MSK) on your behalf via an **event source mapping (ESM)** rather than those sources invoking Lambda directly. Default batch size is **10 for SQS**, **100 for DynamoDB Streams, Kinesis, and MQ/MSK**. Without partial-batch-failure handling, a single failed message in a batch causes the *entire batch* to be retried (or become visible again in the queue), reprocessing already-succeeded messages. **`ReportBatchItemFailures`** on the ESM configuration fixes this: your handler catches per-item errors and returns a `batchItemFailures` array of failed item identifiers; only those get retried. For Kinesis/DynamoDB Streams specifically, if multiple failures are reported, Lambda checkpoints at the *lowest* sequence number among them and retries everything from there forward — so reporting an item as failed near the front of a batch effectively retries the whole tail too.

```python
# untested sketch — SQS partial batch failure handler
def handler(event, context):
    failures = []
    for record in event["Records"]:
        try:
            process(record["body"])
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
```

### Sync vs async invoke — retry and DLQ semantics differ completely

| | Synchronous (API Gateway, ALB, SDK `Invoke`) | Asynchronous (S3, SNS, EventBridge) |
|---|---|---|
| Caller waits for response | Yes | No — Lambda queues internally and returns immediately |
| Retry on failure | Caller's responsibility; Lambda does not retry | Lambda retries automatically, **2 additional attempts** by default, with delays between |
| Dead-letter handling | None built in — caller must implement | Configure a DLQ (SQS/SNS) or, preferably, an **on-failure destination** (newer, richer payload with error context) after retries exhaust |
| Throttling behavior | Immediate `429` to caller | Re-queued internally and retried later, invisible to the original invoker |

Async's "invisible to the caller" retry is a common source of duplicate side effects — if your handler isn't idempotent, an async invoke that appears to fail (timeout, throttle) but actually partially completed will run again automatically.

### Lambda in a VPC and NAT cost

A Lambda function needs VPC attachment only if it must reach a resource with no public endpoint (RDS in a private subnet, an internal ElastiCache cluster). If it also needs to reach the public internet or other AWS service endpoints from inside that VPC, it needs a route to a NAT Gateway (billed hourly plus per-GB processed) or VPC endpoints for AWS services it calls (S3, DynamoDB, Secrets Manager gateway/interface endpoints avoid the NAT charge entirely for those specific services). Forgetting this is a recurring cost surprise: a VPC-attached function calling out to a public API racks up NAT data-processing charges nobody budgeted for.

### Memory as the CPU dial

Lambda doesn't let you set vCPU directly — CPU is allocated proportionally to configured memory. **At 1,769 MB you get the equivalent of one full vCPU**; at the maximum **10,240 MB you get roughly 6 vCPUs**. Memory is configurable in 1 MB increments from 128 MB to 10,240 MB. [Lambda memory/CPU allocation](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html) — accessed 2026-08-01.

**The cost-optimum curve is often non-obvious:** a CPU-bound function given more memory can finish faster, and because Lambda bills duration × memory, a higher memory setting sometimes costs *less* overall if it cuts duration by more than proportionally — e.g., doubling memory that halves duration is cost-neutral, but doubling memory that cuts duration by more than half is a net win. Never guess; use AWS Lambda Power Tuning (the open-source state-machine tool) to sweep memory settings against real payloads and find the actual minimum-cost point.

### The 15-minute limit and what to use instead

Maximum execution timeout is a hard **900 seconds (15 minutes)**, non-negotiable, by design — it bounds how long any one tenant can occupy a shared execution slot. For anything longer: **Step Functions** orchestrating multiple Lambda invocations with state passed between them, **Fargate/ECS tasks** for long-running single processes, or **AWS Batch** for long batch/array jobs. Trying to "extend" Lambda past 15 minutes by chaining self-invocations or long-polling is a documented anti-pattern that produces exactly-once semantics you don't actually have and orphaned partial work on timeout.

### When Lambda is the wrong answer

- **Steady high throughput.** A service handling constant, predictable load 24/7 is cheaper on always-on compute (Fargate, EC2 with Savings Plans) once utilization is high enough that per-invocation pricing exceeds a provisioned-capacity model — the crossover is workload-specific but is a real, computable break-even, not a vibe.
- **Long jobs.** Anything routinely brushing the 15-minute ceiling should not be shoehorned into Lambda; the failure mode is truncated work with no clean resumption.
- **Heavy dependencies / large packages.** A 250MB deployment package with a large ML framework increases cold-start download time and INIT duration regardless of runtime; container image support (up to 10GB) helps packaging but doesn't eliminate the init-time cost of loading a large model into memory on every cold start.
- **GPU work.** Lambda has no GPU support at all. Any inference workload needing a GPU belongs on SageMaker endpoints, EC2 GPU instances, or ECS/EKS with GPU node groups.
- **Very chatty, low-latency-sensitive internal service-to-service calls at high fan-out.** The per-invocation overhead and cold-start tail latency, even reduced, can dominate a call chain that a persistent connection pool on always-on compute would avoid.

---

## Build it from scratch

The part of Lambda's execution model most worth internalizing hands-on is global-scope reuse across invocations — the pattern below is the actual mechanism, not a simplification:

```python
# untested sketch — demonstrates INIT-vs-INVOKE cost separation
import time
import boto3

# Runs ONCE per execution environment (during INIT), not per invocation.
_init_start = time.monotonic()
_dynamodb_client = boto3.client("dynamodb")   # connection setup paid once
_init_cost_ms = None

def handler(event, context):
    global _init_cost_ms
    if _init_cost_ms is None:
        _init_cost_ms = (time.monotonic() - _init_start) * 1000
        print(f"COLD START — init cost {_init_cost_ms:.1f}ms")
    else:
        print("WARM START — init skipped")

    # per-invocation work only, reusing the already-initialized client
    return _dynamodb_client.describe_table(TableName=event["table"])
```

Deploying this twice back-to-back (one cold, one immediately after while still warm) and diffing the logged cost is the fastest way to make the INIT/INVOKE split concrete rather than theoretical.

---

## How it's done in production

Production Lambda systems typically layer: **provisioned concurrency** on the specific functions in a synchronous, latency-sensitive path (API Gateway → Lambda → user-facing response), **SnapStart** on Java/Python functions where provisioned concurrency's continuous cost isn't justified by traffic pattern, **Powertools for AWS Lambda** (structured logging, tracing, idempotency helpers) rather than hand-rolled cross-cutting concerns, **Lambda Power Tuning** run once per function to pick the memory setting, and **ARM64/Graviton** as the default architecture unless a native dependency forces x86.

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency spikes only on the first request after a deploy | Cold start on the newly deployed version, all traffic briefly cold | Provisioned concurrency, or a warm-up invocation as part of the deploy pipeline before shifting traffic |
| Intermittent `429 TooManyRequestsException` under load | Account or function-level concurrency limit exceeded | Raise the account limit via support ticket, set reserved concurrency floor for the critical function, add client-side backoff |
| SQS messages reprocessed multiple times, side effects duplicated | No `ReportBatchItemFailures`, one bad message fails the whole batch | Enable partial batch response, make handler idempotent regardless |
| Function works standalone, times out when calling an internal RDS instance | VPC attachment missing or NAT/route misconfigured | Verify subnet route tables, security groups, and that VPC endpoints exist for any AWS service also called |
| Java function averages 6s response time in production despite fast local testing | No SnapStart, cold JVM boot dominating under low-traffic conditions | Enable SnapStart, verify runtime hooks re-randomize any snapshot-frozen state |
| Costs increased after "optimizing" by raising memory | CPU-bound assumption was wrong; function was I/O-bound and duration didn't improve, so cost rose with memory alone | Run Lambda Power Tuning against real payloads instead of guessing |
| Function silently reruns duplicate work with no visible error | Async invoke retried automatically after a timeout or throttle the caller never saw | Design handler idempotently; configure an on-failure destination to see what's actually retrying |

---

## Tradeoffs & when NOT to use it

- **Not for steady, predictable, high-throughput workloads** — the economics favor provisioned always-on compute past a real, calculable utilization threshold; don't treat "serverless" as free of a cost-crossover analysis.
- **Not for anything that needs more than 15 minutes** — no amount of tuning changes this; redesign into Step Functions, Fargate, or Batch.
- **Not for GPU-bound inference** — zero GPU support, full stop; that's SageMaker/EC2/ECS-EKS territory.
- **Not for workloads with large, slow-to-load dependencies invoked infrequently** — cold-start-sensitive traffic patterns amplify exactly the packages Lambda handles worst; either shrink the package, use SnapStart if the runtime supports it, or move the workload off Lambda.
- **Be honest about provisioned concurrency's cost model** — it converts Lambda's "pay only for what you use" pitch into a continuous hourly charge, similar to always-on compute, for the slice of traffic it protects; it's a mitigation, not a free win.

---

## Interview questions

### Q1 — Walk me through what happens on a cold start, phase by phase.
**Testing:** whether the execution model is understood mechanically, not just as a buzzword.
**Answer:** Lambda provisions a new execution environment (a Firecracker microVM), downloads the deployment package or pulls the container image, boots the runtime, and runs any code at module/global scope (the INIT phase) exactly once for that environment's lifetime. Then INVOKE runs your handler against the event. After the invocation, the environment freezes rather than terminating, and if another invocation arrives before AWS reclaims it, it thaws and skips straight to INVOKE — that's a warm start.
**Follow-up trap:** *"Is the freeze window guaranteed?"* — no, AWS doesn't publish a guaranteed warm-window duration; it's commonly tens of minutes of inactivity in practice but is not a contractual SLA, so never architect correctness around an assumed warm lifetime.

### Q2 — Java cold starts used to be 5+ seconds. What changed, and by how much?
**Testing:** currency on SnapStart, not just "it exists."
**Answer:** SnapStart snapshots memory and disk state after init has already run once and restores from that snapshot on subsequent cold starts instead of re-booting the JVM and reloading classes from zero. This takes Java from 5–15+ seconds down to roughly 90–140ms. It's since expanded to Python 3.12+ and .NET 8+ as of the late-2024/2025 GA.
**Follow-up trap:** *"Does SnapStart have any correctness gotchas?"* — yes: anything generated during init (random seeds, cached credentials, unique IDs) gets frozen into the snapshot and would be identical across every cold start restored from it unless you explicitly re-randomize/refresh in a `beforeCheckpoint`/`afterRestore` hook.

### Q3 — Is VPC attachment still a cold-start problem in 2026?
**Testing:** whether the candidate has a stale 2018-era answer memorized.
**Answer:** No, largely fixed since 2019's Hyperplane networking change, which moved from per-execution-environment ENI creation (10–15 seconds) to pre-created, shared ENIs per subnet+security-group. VPC attachment today adds well under 50ms and is not a meaningful cold-start factor. What VPC attachment still costs is a NAT Gateway for internet egress (hourly plus per-GB), not latency.
**Follow-up trap:** *"So there's no reason to avoid VPC-attaching a function anymore?"* — cold start isn't the reason, but subnet IP exhaustion at high concurrency is a real operational risk if the subnet is under-provisioned, since every concurrent execution environment needs an ENI from the pool.

### Q4 — Your function is being throttled with 429s under a traffic spike, even though the function itself isn't slow. Diagnose it.
**Testing:** concurrency model understanding versus assuming it's a performance problem.
**Answer:** Concurrent executions across the whole account (or that function's reserved concurrency ceiling, if set) are being exceeded — throttling is a capacity/quota issue, not a latency issue. Check CloudWatch's `Throttles` metric and the account's current concurrent-execution quota (which can start as low as 10 on some new accounts before AWS auto-raises it). Fix: request a quota increase, set a reserved concurrency floor for this function so other functions can't starve it, and add client-side retry with backoff for the synchronous callers hitting 429.
**Follow-up trap:** *"Would provisioned concurrency fix the throttling?"* — provisioned concurrency addresses cold starts within an allocated capacity slice, not the account-level ceiling; you can still be throttled beyond your provisioned amount if total concurrent demand exceeds the account/function's concurrency limit.

### Q5 — Explain `ReportBatchItemFailures` and why its absence is dangerous with SQS.
**Testing:** whether they've actually operated an ESM-backed consumer, not just described SQS generically.
**Answer:** Without it, if your handler throws while processing any message in a batch, the *entire batch* becomes visible again in the queue and is retried, including messages that already succeeded — meaning side effects for those succeeded messages can run twice. Enabling `ReportBatchItemFailures` on the event source mapping lets the handler return only the specific failed message IDs, so only those get retried.
**Follow-up trap:** *"Does this fully solve duplicate processing?"* — no, SQS is already at-least-once delivery regardless, so the handler still needs to be idempotent; partial batch failure just narrows the blast radius of retries, it doesn't eliminate the need for idempotency.

### Q6 — Synchronous vs asynchronous Lambda invocation: what's actually different about failure handling?
**Testing:** the retry/DLQ semantics split, a common gap.
**Answer:** Synchronous invokes (API Gateway, direct SDK `Invoke`) put retry entirely on the caller — Lambda itself does not retry a failed sync invocation. Asynchronous invokes (S3 events, SNS, EventBridge) are queued internally by Lambda and retried automatically, by default up to 2 additional attempts with delay between them, invisible to whatever triggered it, and after retries exhaust you need a configured DLQ or an on-failure destination to see what actually failed.
**Follow-up trap:** *"If an async invocation appears to complete but partially failed, what happens?"* — Lambda has no way to know your handler "partially" failed unless it throws; a handler that swallows an exception after doing half its work will report success and never retry, silently leaving inconsistent state — this is a design bug in the handler, not a Lambda limitation.

### Q7 — How does memory relate to CPU in Lambda, and how do you find the actual cost-optimal setting?
**Testing:** the non-obvious cost curve, not just "more memory = more CPU."
**Answer:** CPU is allocated proportionally to configured memory; 1,769 MB is the point at which a function gets one full vCPU, scaling up toward roughly 6 vCPUs at the 10,240 MB maximum. Because billing is duration × memory, increasing memory on a CPU-bound function can lower total cost if the resulting duration drop is more than proportional — but guessing is wrong often enough that the correct method is running AWS Lambda Power Tuning against real payloads to sweep memory settings and measure the actual cost/latency curve.
**Follow-up trap:** *"What if the function is I/O-bound, waiting on a downstream API?"* — more memory won't help duration at all in that case since CPU isn't the bottleneck; raising memory there only raises cost with no latency benefit, which is exactly the mistake Power Tuning catches and intuition doesn't.

### Q8 — A batch ETL job needs 40 minutes to run. Why not just chain Lambda invocations to get around the 15-minute limit?
**Testing:** the "when Lambda is the wrong answer" judgment.
**Answer:** The 15-minute ceiling is a deliberate architectural boundary, not a soft default, and chaining self-invocations to extend it produces fragile, effectively-manual orchestration: no clean way to resume from a partial failure, no built-in state tracking between chained invocations, and a real risk of runaway recursive invocation costs if the chaining logic has a bug. The correct tools for genuinely long or multi-step work are Step Functions (for orchestrating multiple bounded steps with tracked state) or Fargate/Batch for a single long-running process.
**Follow-up trap:** *"What if each 'step' is naturally under 15 minutes and there are just many of them?"* — that's exactly Step Functions' use case: model it as a state machine with retry/catch per step rather than hand-rolled self-invocation, which gives you visibility, replay, and per-step timeout independently.

### Q9 — Design the Lambda configuration for an image-processing pipeline behind API Gateway that needs consistently low p99 latency.
**Testing:** synthesizing cold-start mitigations into a coherent design rather than listing them.
**Answer:** Provisioned concurrency sized to expected steady-state concurrent load (since this is a latency-sensitive synchronous path where even rare cold starts are unacceptable), ARM64/Graviton for the ~15-40% baseline speed improvement, memory tuned via Power Tuning against a real image payload rather than guessed, and if the runtime is Java or another SnapStart-eligible language, SnapStart layered in as well since it reduces the *residual* cold-start cost for any traffic that exceeds provisioned capacity and falls back to on-demand scaling.
**Follow-up trap:** *"Provisioned concurrency costs money even when idle — how do you size it without overpaying?"* — track actual concurrent-invocation patterns over time (CloudWatch `ConcurrentExecutions`) and set provisioned concurrency to cover the typical baseline, letting on-demand scaling (with its cold-start cost) absorb rare spikes above that baseline, rather than provisioning for peak.

### Q10 — When would you actively recommend against Lambda for a new service, even though it would technically work?
**Testing:** the real "when NOT to use it" section, staff-level judgment.
**Answer:** Steady, high, predictable throughput where the per-invocation pricing model loses to provisioned always-on compute past a computable utilization threshold; anything needing more than 15 minutes per unit of work; any GPU-dependent inference; and workloads with large, slow-initializing dependencies (big ML frameworks, large models loaded into memory) invoked infrequently enough that cold starts dominate user-perceived latency and provisioned concurrency's continuous cost isn't justified by the traffic volume.
**Follow-up trap:** *"Isn't 'steady high throughput' exactly what Fargate is for, so is this circular?"* — no, it's a genuine crossover point worth calculating rather than assuming: at low-to-moderate steady throughput Lambda can still win on total cost and zero ops burden; the recommendation to move off Lambda should be backed by an actual cost/utilization calculation, not a reflexive "Lambda doesn't scale" claim, which is false.

### Q11 — An agentic AI system calls five different Lambda-backed tools per turn. What Lambda-specific failure mode should you design around that a monolithic service wouldn't have?
**Testing:** applying the module to the candidate's actual domain (agentic AI, per the student profile).
**Answer:** Cold-start tail latency compounds per tool call in a synchronous chain — five sequential Lambda invocations each with even a 5% cold-start chance means a meaningfully higher chance that *some* step in the chain hits a cold start, and unlike a warm connection-pooled service, each Lambda's INIT cost (SDK client setup, credential fetch) is paid independently per function rather than shared. Provisioned concurrency on the tools in the critical synchronous path, and keeping each tool's package small and dependency-light, both reduce this; but the deeper design fix is bounding total per-turn latency budget and deciding upfront which tool calls can be async/fire-and-forget versus must be synchronous.
**Follow-up trap:** *"Would you ever use Lambda for the LLM inference call itself?"* — no; Lambda's 15-minute ceiling, lack of GPU support, and cold-start-unfriendly footprint for loading model weights make it the wrong compute layer for inference — that call belongs on a SageMaker endpoint, vLLM-serving cluster, or a managed model API, with Lambda used only for the orchestration/tool-calling glue around it.

### Q12 — What's the difference between reserved and provisioned concurrency, and why would you ever use both on the same function?
**Testing:** distinguishing a capacity guarantee from a warm-start guarantee.
**Answer:** Reserved concurrency sets a hard floor-and-ceiling on how much of the account's total concurrency pool this function can consume — it guarantees availability and isolates it from other functions, but every execution within that reserved capacity can still be a cold start. Provisioned concurrency pre-initializes a specific number of warm environments, eliminating cold starts for invocations within that count, at a continuous cost. Using both together reserves guaranteed capacity for the function and keeps a portion of that reserved capacity pre-warmed, giving both isolation and low-latency guarantees simultaneously.
**Follow-up trap:** *"If provisioned concurrency already guarantees warm environments, why add reserved concurrency too?"* — without reserved concurrency, a burst of demand from other functions in the account could still consume the shared pool and throttle this function's *on-demand* scaling beyond its provisioned baseline; reserved concurrency protects the ceiling this function can ever reach, provisioned concurrency protects the warm-start latency within that ceiling.

---

## Red flags that fail you

- Saying VPC attachment causes multi-second cold starts — that was fixed in 2019 and is a stale answer.
- Not knowing SnapStart exists or claiming it's Java-only when Python and .NET have GA support.
- Describing async invoke as "fire and forget with no retry" — Lambda retries async invocations automatically by default.
- Recommending Lambda for a GPU inference workload.
- Claiming Lambda "can't fail" or omitting throttling as a real, common production failure mode.
- Not knowing the 15-minute limit is fixed and cannot be worked around by self-chaining without real architectural cost.
- Treating "more memory always makes it faster and cheaper" without acknowledging I/O-bound workloads don't benefit.
- Never having heard of `ReportBatchItemFailures` when discussing SQS/Kinesis consumers.

---

## Cheat card

```
LIFECYCLE: download/pull -> INIT (global scope, once per env) -> INVOKE (per call) -> FREEZE -> (THAW skips INIT)
  warm window: not a guaranteed SLA, don't design correctness around it

COLD START p50 (verify before interview, changes):
  Python/Node, no SnapStart      ~200-400ms
  Java, no SnapStart             5-15s+
  Java, WITH SnapStart           90-140ms
  Python/Node on Graviton(arm64) <200ms, 15-40% faster than x86
  <1% of prod invocations hit a cold start (AWS's own data)

SnapStart: snapshot AFTER init runs once, restore on cold start instead of re-running init.
  Supported: Java 11+, Python 3.12+, .NET 8+ (GA 2024-2025) -- verify current region list
  GOTCHA: random seeds/creds/UUIDs generated at init freeze into the snapshot;
          use beforeCheckpoint/afterRestore hooks to re-randomize

VPC: Hyperplane (2019) fixed ENI-per-env cold start (was 10-15s, now <50ms).
  Remaining VPC cost = NAT Gateway $/hr + $/GB for internet egress, not latency.

CONCURRENCY: account pool default ~1000/region (soft limit, some new accounts start at 10)
  Reserved concurrency  = floor+ceiling for one function (isolation, not warmth)
  Provisioned concurrency = pre-warmed envs (removes cold start, continuous $ cost)
  Exceed limit -> 429 TooManyRequestsException, NOT a queue

EVENT SOURCE MAPPING: default batch = 10 (SQS), 100 (DynamoDB Streams/Kinesis/MQ/MSK)
  No ReportBatchItemFailures -> whole batch retried on any single item failure
  With it: return {"batchItemFailures":[{"itemIdentifier": id}, ...]}
  Kinesis/DDB streams: checkpoints at LOWEST failed sequence number, retries tail too

SYNC invoke: caller retries, Lambda does not. 429 on throttle, immediate.
ASYNC invoke: Lambda retries automatically (~2 extra attempts), invisible to caller.
  DLQ or on-failure destination needed to see exhausted failures.

MEMORY = CPU DIAL: 1769MB = 1 vCPU, 10240MB (max) ~= 6 vCPU. 128MB-10240MB, 1MB increments.
  Billing = duration x memory -> use AWS Lambda Power Tuning, never guess.

LIMIT: 900s (15 min) hard max, by design. Longer -> Step Functions / Fargate / Batch.

WRONG FOR: steady high throughput, >15min jobs, GPU inference, huge slow-init deps at low traffic.
```

## Sources

- [AWS Lambda Cold Start Optimization in 2026 — SnapStart, Graviton](https://viprasol.com/blog/aws-lambda-cold-start-optimization/) — accessed 2026-08-01
- [AWS Lambda SnapStart for Python and .NET GA announcement](https://aws.amazon.com/blogs/aws/aws-lambda-snapstart-for-python-and-net-functions-is-now-generally-available/) — accessed 2026-08-01
- [SnapStart 23 additional regions](https://aws.amazon.com/about-aws/whats-new/2025/06/aws-lambda-snapstart-python-net-functions-23-regions) — accessed 2026-08-01
- [Improving startup performance with Lambda SnapStart — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html) — accessed 2026-08-01
- [Announcing improved VPC networking for AWS Lambda — AWS Compute Blog](https://aws.amazon.com/blogs/compute/announcing-improved-vpc-networking-for-aws-lambda-functions/) — accessed 2026-08-01
- [Understanding Lambda function scaling — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html) — accessed 2026-08-01
- [Configuring provisioned concurrency — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html) — accessed 2026-08-01
- [Handling errors for an SQS event source in Lambda — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html) — accessed 2026-08-01
- [Configuring partial batch response with Kinesis — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/services-kinesis-batchfailurereporting.html) — accessed 2026-08-01
- [Configure Lambda function memory — AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Lambda's execution model is INIT-once, INVOKE-many: an environment's global scope runs once per cold start and every warm invocation after that skips straight to the handler, which is why connection setup belongs at module scope, not inside the handler. Cold starts are runtime-dependent — Python and Node sit around 200-400ms, unoptimized Java is 5-15+ seconds, and SnapStart (now GA for Java, Python 3.12+, and .NET 8+) collapses Java to 90-140ms by restoring a post-init snapshot instead of rebooting. VPC attachment stopped being a cold-start problem in 2019 when Hyperplane replaced per-invocation ENI creation with shared, pre-created ENIs; today VPC's real cost is a NAT Gateway bill, not latency. Concurrency is capped at the account level with reserved concurrency providing isolation and provisioned concurrency providing pre-warmed capacity at a continuous cost, and exceeding it throttles rather than queues. Lambda is the wrong choice for steady high-throughput services, anything over 15 minutes, GPU inference, and dependency-heavy workloads invoked too rarely to justify provisioned concurrency.
