# Integration: SQS, SNS, EventBridge, Step Functions, API Gateway

> **Track:** C-AWS AWS Atlas · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-integration` · **Tags:** integration

## The 30-second version

SQS is a mailbox (one message, one eventual consumer), SNS is a megaphone (one message, every subscriber), and EventBridge is a switchboard (content-based routing to whichever target a rule matches) — most "which one" questions resolve to whether you need fan-out, ordering, or routing logic. SQS FIFO trades throughput (300 TPS unbatched, 3,000 batched, up to 30,000 in high-throughput mode with relaxed per-group ordering) for exactly-once-within-5-minutes deduplication and strict per-group ordering that Standard queues don't offer; visibility timeout set below actual handler runtime is the single most common cause of duplicate processing, because the message becomes visible to a second consumer while the first is still working it. Step Functions Standard bills per state transition and supports year-long durable workflows with exactly-once semantics; Express bills per request-plus-duration and is 40x+ cheaper at volume but caps at 5 minutes with at-least-once (async) or at-most-once (sync) semantics — picking wrong is a correctness bug, not just a cost one. API Gateway HTTP APIs are the default at roughly 3.5x cheaper than REST APIs for the 90% of cases that don't need REST-only features (usage plans, request/response transformation, native WAF); a Fargate service behind an ALB routinely undercuts either at meaningfully high request volume once you're past the free tier. Idempotency — a dedup key checked atomically before any side effect — is the one concern that cuts across every service in this module, because at-least-once delivery is the default guarantee almost everywhere here.

## Why this gets asked

Because the interviewer has debugged a duplicate-charge or duplicate-email incident caused by a visibility timeout shorter than the actual processing time, or watched a team build EventBridge-shaped routing logic manually on top of SNS because nobody knew EventBridge existed, or paid for a Standard Step Functions workflow that should have been Express and cost 40x more for the same volume. They want to know you reach for the right primitive by default, and that you treat "at-least-once delivery" as a design constraint you build idempotency around, not an edge case you'll handle later.

---

## Lineage: past → present → future

**What came before.** Before managed queueing, decoupling producers from consumers meant either a self-hosted message broker (early-2000s JMS brokers, then RabbitMQ) or tight synchronous coupling with retry logic bolted on at each call site. SQS (2006, one of AWS's very first services) was the original managed answer — a durable queue with at-least-once delivery and no broker to run. SNS (2010) added the pub/sub half of the picture. For years, the standard AWS integration pattern was "SNS fans out to multiple SQS queues," because neither service alone did content-based routing — every subscriber got every message and had to filter client-side, or you built your own routing logic. EventBridge (2019, evolved from CloudWatch Events) closed that gap by adding rule-based content filtering natively at the bus.

**Where it stands now.** The current default pattern for most new event-driven builds is "SNS + SQS for simple fan-out, EventBridge once routing logic gets non-trivial or you're integrating multiple SaaS/AWS-native event sources" — and increasingly, EventBridge is the first reach for greenfield event-driven architectures specifically because of its native schema registry, content-based filtering, and archive/replay support, none of which SNS+SQS give you without extra plumbing. Step Functions Standard vs Express is a live, frequently-mishandled decision: Standard's per-state-transition pricing model makes a workflow with many rapid transitions unexpectedly expensive at volume (documented example: 10 million executions of a 5-state workflow costs roughly $1,250 under Standard versus roughly $31 under Express), and Express's at-most-once semantics for synchronous workflows is a correctness constraint many teams don't realize they've accepted until a mid-execution failure loses work. API Gateway's HTTP API type (GA 2020) is now the default recommendation over REST APIs for new builds, with REST reserved for the minority of cases needing usage plans, request validation, or native WAF integration that HTTP APIs still don't fully match.

**Where it's heading.** The live disagreement worth naming: as request volumes grow, more teams are questioning whether API Gateway is worth its per-request cost at all versus an ALB in front of Fargate/EKS, especially for internal or high-volume services where API Gateway's request-based pricing scales linearly with no cap the way a fixed-capacity ALB+compute cost doesn't — this is a genuine, actively-debated tradeoff, not a settled one. EventBridge's schema-and-routing model is extending further into SaaS integration (EventBridge's growing library of native SaaS event sources) as the preferred way to ingest third-party events without hand-building webhooks-plus-queues for each vendor. Idempotency infrastructure (Lambda's own idempotency utilities, DynamoDB conditional writes as a dedup pattern) is increasingly treated as a first-class architectural concern baked into scaffolding/templates rather than something each team reinvents per project — a moderate-confidence direction, since it still isn't universal practice.

---

## Mental model

```
   SQS = MAILBOX               SNS = MEGAPHONE           EVENTBRIDGE = SWITCHBOARD
  ┌─────────────┐             ┌─────────────┐            ┌──────────────────────┐
  │  producer   │             │  producer   │            │  producer / SaaS /   │
  └──────┬──────┘             └──────┬──────┘            │  AWS service event   │
         │  1 message                │  1 message        └───────────┬──────────┘
         ▼                    ┌──────┼──────┐                        ▼
  ┌─────────────┐             ▼      ▼      ▼                 ┌────────────┐
  │   queue     │        ┌────────┐┌────────┐┌────────┐       │    BUS     │
  │ (buffered)  │        │consumer││consumer││consumer│       │  + RULES   │
  └──────┬──────┘        │   A    ││   B    ││   C    │       │ (content-  │
         │                └────────┘└────────┘└────────┘      │  based     │
         ▼                    ALL subscribers get it           │  filter)   │
  ┌─────────────┐             (fan-out, optional filter        └─────┬──────┘
  │  ONE        │              policy per subscription)              │
  │  consumer   │                                          matched rules route to:
  │  (eventual, │                                        SQS / Lambda / Step Fn /
  │  at-least-  │                                        API destination / more buses
  │  once)      │                                        + optional ARCHIVE for replay
  └─────────────┘

  STEP FUNCTIONS: orchestrates state across calls to any of the above
    STANDARD: $/1000 state transitions, up to 1yr runtime, exactly-once,
              full history/visual debugging
    EXPRESS:  $/request + duration, max 5 min, at-least-once (async) or
              at-most-once (sync), 40x+ cheaper at high volume

  API GATEWAY: the front door translating HTTP <-> the above
    REST: full feature set (usage plans, validation, native WAF), $3.50/1M
    HTTP: 90% of use cases, $1.00/1M (this is why it's the default choice)
    WebSocket: persistent connections, billed by connection-minutes + messages
```

---

## How it actually works

### SQS: Standard vs FIFO, and the visibility timeout bug

Standard queues support a nearly unlimited API call rate per action, deliver **at-least-once** (occasional duplicates are possible even without any bug), and provide **best-effort ordering** only. FIFO queues guarantee strict ordering within a message group and **exactly-once processing within a 5-minute deduplication window** — either content-based (SQS hashes the body) or via an explicit `MessageDeduplicationId`. Throughput: FIFO without batching caps at 300 API calls/second per method; with batching, up to 3,000 messages/second per method; with **high-throughput mode** enabled, up to 30,000 transactions/second, at the cost of relaxed ordering guarantees across (not within) message groups [SQS Standard vs FIFO — jayendrapatil](https://jayendrapatil.com/aws-sqs-standard-vs-fifo/) — accessed 2026-08-01, [FIFO queue delivery logic — AWS docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-understanding-logic.html) — accessed 2026-08-01.

**The visibility timeout bug, precisely.** When a consumer receives a message, it becomes invisible to other consumers for the **visibility timeout** duration (default 30 seconds, configurable 0 seconds to 12 hours) — this is SQS's mechanism for "nobody else works on this while you have it." If the consumer's actual processing time exceeds the visibility timeout, the message becomes visible again *while the original consumer is still working on it*, a second consumer picks it up, and now two consumers are processing the same message concurrently — for a non-idempotent handler (sending an email, charging a card, writing a non-conditional DB update), that's a duplicate side effect, not just wasted compute. The fix is either setting the visibility timeout comfortably above your p99 processing time, or calling `ChangeMessageVisibility` to extend it dynamically for handlers with unpredictable runtime — and either way, building idempotency into the handler as a second line of defense, because at-least-once delivery means duplicates are possible even with a correctly-tuned timeout (network retries, consumer crashes after processing but before deleting the message).

**DLQs and redrive.** A dead-letter queue receives messages that exceed `maxReceiveCount` (the number of times a message can be received without being deleted) — this catches poison-pill messages that would otherwise loop forever, and DLQ redrive lets you replay them back to the source queue after fixing whatever caused the failures, without losing the messages.

### SNS: fan-out and filtering

SNS delivers a published message to every current subscriber (SQS queues, Lambda, HTTP/S endpoints, email, SMS, mobile push) — this is the "megaphone" half of pub/sub. **Message filtering** lets each subscription declare a filter policy (matching on message attributes) so a subscriber only receives the subset of messages relevant to it, without every consumer having to filter client-side — this is the feature that makes "SNS fan-out with filtering" a viable alternative to EventBridge for simpler routing needs, though it's attribute-matching on a single topic rather than the richer content-based, multi-source routing EventBridge does.

### EventBridge vs SNS vs SQS

| | SQS | SNS | EventBridge |
|---|---|---|---|
| Model | Queue (buffer, one consumer per message) | Pub/sub (fan-out, every subscriber) | Event bus (content-based routing via rules) |
| Routing logic | None — first-come consumer | Attribute-based filter policy per subscription | Full event-pattern matching (JSON structure, values), multiple rules per event |
| Native SaaS sources | No | No | Yes — a growing catalog of third-party SaaS event sources |
| Schema registry | No | No | Yes — infers and versions event schemas |
| Archive & replay | No (built manually via a DLQ or separate storage) | No | **Yes, natively** — archive events matching a pattern, replay them into the bus later for a specified time window |
| Best for | Decoupling producer from consumer, buffering, retry via visibility timeout | Broadcasting one event to many known subscribers | Routing many event types from many sources to many targets by content, especially heterogeneous/evolving event shapes |

The practical decision tree: need simple point-to-point decoupling with buffering → SQS. Need to broadcast one event to a fixed, known set of subscribers → SNS (optionally with SQS behind each subscriber for durability — the classic "SNS fans out to per-consumer SQS queues" pattern gives you both broadcast and per-consumer buffering/retry). Need routing logic based on event content, multiple heterogeneous sources, schema evolution, or the ability to replay a window of history after finding a bug in a downstream consumer → EventBridge. Most production systems end up using two or three of these together, not picking one exclusively — EventBridge routing to an SQS queue for buffered, retryable delivery to a specific consumer is a very common combination.

### Step Functions: Standard vs Express, and error/retry/catch semantics

| | Standard | Express |
|---|---|---|
| Pricing | $0.025 per 1,000 state transitions | ~$1.00 per million requests, plus duration/memory |
| Max duration | Up to 1 year | 5 minutes |
| Semantics | Exactly-once | At-least-once (async) or at-most-once (sync) |
| Execution history | Full, visually inspectable in the console | Sent to CloudWatch Logs only, not the visual history view |
| Use for | Long-running, must-not-lose-work orchestration (order fulfillment, human-in-the-loop approval, long ML pipelines) | High-volume, short-lived, latency-sensitive orchestration (streaming data transformation, IoT event processing) |

[Step Functions pricing 2026 — Oreate AI](https://www.oreateai.com/blog/demystifying-aws-step-functions-pricing-standard-vs-express-workflows/8a708291c920da86b15b18ea6492b032) — accessed 2026-08-01. The cited cost delta at real volume: a 5-state workflow run 10 million times costs roughly $1,250/month under Standard versus roughly $31/month under Express [Step Functions cost comparison — same source] — accessed 2026-08-01. This is not a rounding difference; picking Standard by default "because it has the nicer visual debugger" for a high-volume, short-duration workflow is a real, compounding cost mistake. Conversely, picking Express for a workflow that genuinely needs exactly-once guarantees or can run longer than 5 minutes is a correctness bug, not a cost optimization.

**State machine error/retry/catch model.** Every state can define a `Retry` field (with `ErrorEquals`, `IntervalSeconds`, `MaxAttempts`, `BackoffRate`) for transient failures, and a `Catch` field (matching specific error types to a fallback state) for handling failures gracefully rather than failing the whole execution. This is Step Functions' built-in equivalent of the resilience-catalogue retry/circuit-breaker patterns, expressed declaratively in the state machine definition rather than in application code — worth naming explicitly if asked to compare it against hand-rolled retry logic.

### API Gateway: REST vs HTTP vs WebSocket, throttling, and the honest ALB comparison

**REST APIs** ($3.50 per million requests) support the full feature set: usage plans (per-API-key rate limits and quotas), request/response transformation and validation, native AWS WAF integration, and custom authorizers with the richest configuration surface. **HTTP APIs** ($1.00 per million requests, roughly 70% cheaper) cover the majority of proxy-to-Lambda/HTTP-backend use cases with simpler configuration, and are the default recommendation for new builds unless a specific REST-only feature is actually needed [API Gateway pricing 2026 — CloudZero](https://www.cloudzero.com/blog/aws-api-gateway-pricing/) — accessed 2026-08-01. **WebSocket APIs** bill by connection-minutes plus message count, and for genuinely real-time bidirectional use cases (chat, live dashboards) this is typically far cheaper than the equivalent traffic implemented as HTTP polling, because polling pays per-request regardless of whether anything changed.

**Throttling** applies at two levels: account-level defaults (commonly cited around 10,000 RPS burst / 5,000 RPS steady-state per region) and per-stage or per-method limits you configure, with **usage plans** (REST only) letting different API key holders get different rate limits and quotas — the mechanism for tiered API monetization or partner access control.

**The honest ALB+Fargate comparison.** API Gateway's fully-managed, pay-per-request model has no idle cost and zero infrastructure to run, which wins decisively at low-to-moderate, spiky traffic. At sustained high volume, a fixed-capacity architecture (ALB + Fargate) can undercut it because ALB+Fargate cost is roughly capped by provisioned capacity rather than scaling linearly per request — a commonly-cited estimate puts a modest ALB+Fargate setup around $40-90/month in fixed cost regardless of request volume within that capacity, versus API Gateway's cost climbing linearly forever as request volume grows [API Gateway vs ALB costs — Vairix](https://www.vairix.com/tech-blog/api-gateway-versus-alb-in-term-of-costs) — accessed 2026-08-01. The corollary worth stating explicitly: a Fargate service behind an ALB doesn't cold-start per request the way some serverless compute does, so for latency-sensitive, sustained-traffic user-facing APIs, the ALB path can win on both cost *and* latency consistency at scale — but it requires actually operating a service (deploys, autoscaling policy, capacity planning) that API Gateway + Lambda abstracts away entirely.

### Idempotency, across all of them

Every service in this module defaults to at-least-once delivery somewhere in its model (SQS Standard explicitly, SQS FIFO's 5-minute dedup window is bounded not absolute, SNS delivery retries, EventBridge target invocation retries, Step Functions Express async mode). The universal fix: an **idempotency key** — a client-generated or content-derived identifier — checked atomically before any side effect, typically via a conditional write (`INSERT ... ON CONFLICT DO NOTHING` or a DynamoDB conditional `PutItem` with `attribute_not_exists`) against a dedup store, never a read-then-write, which races under concurrent duplicate delivery. This is the same idempotency-key pattern covered in depth in the resilience catalogue (`21-architecture-principles/06-resilience-catalogue.md`); the point specific to this module is that it's not optional here — at-least-once is the default, not an edge case, across this entire service list.

**Azure/GCP equivalent.** SQS → Service Bus/Storage Queue (Azure) / Pub/Sub pull (GCP, which unifies queue and pub/sub into one service — a real architectural difference from AWS's SQS/SNS split). SNS → Event Grid (Azure) / Pub/Sub (GCP). EventBridge → Event Grid (Azure, though Event Grid's model differs meaningfully from EventBridge's rule-and-bus structure) / Eventarc (GCP). Step Functions → Durable Functions (Azure, code-first rather than state-machine-first — a genuine paradigm difference) / Workflows (GCP). API Gateway → API Management (Azure) / API Gateway or Apigee (GCP). See `clouds/CROSS-CLOUD-MAP.md`.

---

## Build it from scratch

Minimal idempotent SQS consumer pattern with visibility-timeout awareness — the shape most likely to come up as "find the bug" in an interview:

```python
# untested sketch
import boto3
import hashlib

sqs = boto3.client("sqs")
dedup_table = boto3.resource("dynamodb").Table("processed-messages")

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/orders"
VISIBILITY_TIMEOUT_S = 120  # must exceed p99 handler runtime, not the average

def poll_and_process():
    resp = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=10,
        VisibilityTimeout=VISIBILITY_TIMEOUT_S,
        WaitTimeSeconds=20,  # long polling, avoids empty-receive cost/latency
    )
    for msg in resp.get("Messages", []):
        dedup_key = hashlib.sha256(msg["Body"].encode()).hexdigest()
        try:
            # Conditional write -- atomic dedup check, NOT read-then-write
            dedup_table.put_item(
                Item={"key": dedup_key, "status": "processing"},
                ConditionExpression="attribute_not_exists(#k)",
                ExpressionAttributeNames={"#k": "key"},
            )
        except dedup_table.meta.client.exceptions.ConditionalCheckFailedException:
            # already processed or in flight -- delete and skip, don't reprocess
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
            continue

        handle_order(msg["Body"])  # the actual side effect
        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])

def handle_order(body: str) -> None:
    ...  # untested sketch
```

The line that matters: the DynamoDB `ConditionExpression="attribute_not_exists(#k)"` is atomic at the database layer, so two consumers racing on a duplicate delivery (visibility timeout expired mid-processing, or SQS's own at-least-once retry) can't both pass the check — exactly the property a read-then-write dedup check would lack.

---

## How it's done in production

| Concern | Tool | What it adds |
|---|---|---|
| Buffered point-to-point decoupling | SQS (Standard or FIFO) | Durability, retry via visibility timeout, DLQ for poison messages |
| Broadcast to known subscribers | SNS, often fanning out to per-subscriber SQS queues | Pub/sub plus per-consumer durability and independent retry |
| Content-based routing, SaaS ingestion, replay | EventBridge | Schema registry, event-pattern rules, native archive/replay |
| Durable multi-step orchestration | Step Functions Standard | Exactly-once, up to 1-year runtime, visual execution history, declarative retry/catch |
| High-volume short-lived orchestration | Step Functions Express | 40x+ cheaper at volume, sub-5-minute workflows |
| HTTP front door for Lambda/backend services | API Gateway (HTTP API by default, REST when a specific feature demands it) | Managed auth, throttling, no infrastructure to run |
| Sustained high-volume HTTP front door | ALB + Fargate/EKS | Fixed capacity cost instead of linear per-request cost at scale, no per-request cold-start behavior |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Duplicate side effects (double charge, double email) under normal load | Visibility timeout shorter than actual handler p99 processing time | Raise visibility timeout above p99, or call `ChangeMessageVisibility` dynamically; add idempotency key as defense-in-depth |
| FIFO queue throughput ceiling hit unexpectedly | Using strict per-message-group ordering when high-throughput mode with relaxed cross-group ordering would suffice | Enable FIFO high-throughput mode if strict cross-group ordering isn't actually required |
| A subscriber receives every SNS message and filters client-side, wasting compute | No filter policy configured on the subscription | Add a message-attribute filter policy on the SNS subscription |
| EventBridge rule silently not matching expected events | Event pattern JSON structure doesn't match the actual event shape (common after a producer schema change) | Use EventBridge's schema registry/discovery to validate the pattern against real event samples, not assumed structure |
| Step Functions Standard workflow costs far more than budgeted at scale | High-frequency, short-duration workflow billed per state transition | Migrate to Express if exactly-once/long-duration isn't actually required |
| Step Functions Express workflow silently loses partial work on failure | At-most-once (sync) or at-least-once (async) semantics misunderstood as exactly-once | Use Standard if the workflow cannot tolerate any lost or duplicated work |
| API Gateway bill grows faster than expected as traffic scales | Linear per-request pricing model at a traffic level where fixed-capacity compute would be cheaper | Model the crossover point against an ALB+Fargate/EKS alternative at your actual sustained volume |
| Two consumers process the "same" SQS FIFO message | Deduplication ID reused unintentionally, or content-based dedup hash collision across genuinely different logical messages, or the 5-minute dedup window elapsed between genuine retries | Use explicit, well-scoped `MessageDeduplicationId` values rather than relying on content-based dedup for messages that could legitimately repeat with different meaning |

---

## Tradeoffs & when NOT to use it

- **Don't set a visibility timeout to the "default 30 seconds" without checking your actual handler's p99 runtime.** This single misconfiguration is the most common cause of duplicate-processing incidents in this entire service list.
- **Don't build content-based routing logic manually on top of SNS filter policies once it gets past simple attribute matching.** EventBridge's event-pattern matching, schema registry, and native archive/replay solve a problem SNS filtering wasn't designed for; reinventing it on SNS is avoidable complexity.
- **Don't default to Step Functions Standard "for the nice visual debugger" on a high-volume, short-duration workflow.** At real volume the per-state-transition pricing model is a genuine, compounding cost, not a rounding error — the cited 40x+ delta at 10 million executions is representative, not exaggerated.
- **Don't use Express Step Functions for anything that cannot tolerate lost or duplicated work.** At-least-once (async) and at-most-once (sync) are real correctness constraints, not implementation details — a financial transaction workflow belongs on Standard.
- **Don't reach for REST API Gateway by default.** Unless you specifically need usage plans, request validation, or native WAF, HTTP APIs cover the same ground at roughly a third of the cost.
- **Don't assume API Gateway is always cheaper than running your own compute behind an ALB.** At sustained high request volume, a fixed-capacity Fargate/EKS service behind an ALB can be both cheaper and more latency-consistent — the crossover is a real calculation, not a foregone conclusion in either direction.
- **Don't treat idempotency as an edge case to handle "if we see duplicates in production."** At-least-once delivery is the default guarantee across SQS, SNS, EventBridge targets, and Step Functions Express — build the dedup key and atomic conditional write in from the start.

---

## Interview questions

### Q1 — A payment-processing consumer is occasionally double-charging customers. Walk through the likely cause and the fix.
**Testing:** the single highest-signal bug in this module.
**Answer:** Most likely the SQS visibility timeout is shorter than the actual p99 processing time of the charge handler — the message becomes visible again while the first consumer is still mid-charge, a second consumer picks it up, and both complete the charge. Fix: raise the visibility timeout comfortably above p99 (or extend it dynamically via `ChangeMessageVisibility` for variable-runtime handlers), and add an idempotency key checked via an atomic conditional write before the charge executes, as defense-in-depth against the timeout alone not being sufficient (SQS is at-least-once regardless of timeout tuning).
**Follow-up trap:** *"You raised the timeout and it still happens occasionally."* — that's expected, not a bug: SQS guarantees at-least-once delivery unconditionally, independent of visibility timeout tuning (consumer crash after processing but before deleting the message is one legitimate cause). The idempotency key is not optional defense-in-depth here, it's the actual correctness guarantee; the timeout tuning only reduces frequency.

### Q2 — SQS Standard or FIFO for an order-processing pipeline where orders for the same customer must be processed in submission order?
**Answer:** FIFO, using the customer ID as the message group ID — this guarantees strict ordering within each customer's group while still allowing parallelism across different customers' groups. Standard gives no ordering guarantee at all, so out-of-order processing (a cancellation processed before its original order) becomes possible.
**Follow-up trap:** *"Throughput requirements later grow past FIFO's per-group limits. What do you do?"* — enable FIFO high-throughput mode, which raises the ceiling to up to 30,000 TPS by relaxing ordering guarantees *across* message groups while preserving it *within* each group — since the requirement was per-customer ordering, not global ordering, this is very likely still correct for the stated requirement.

### Q3 — When would you use EventBridge instead of SNS+SQS for a new event-driven system?
**Answer:** Once routing needs content-based logic beyond simple attribute filtering, when ingesting events from multiple heterogeneous sources (including AWS-native service events or third-party SaaS), or when you need schema evolution tracking and the ability to replay a window of historical events into the bus after fixing a downstream bug — none of which SNS+SQS provide natively.
**Follow-up trap:** *"Can you get archive/replay with SNS+SQS instead?"* — not natively; you'd have to build it yourself (a separate durable log of published messages, replayed manually), which is exactly the kind of undifferentiated plumbing EventBridge's native archive feature exists to remove.

### Q4 — Standard or Express Step Functions for a workflow processing 5 million IoT sensor events per day, each taking under 2 seconds, where losing an occasional event on failure is acceptable?
**Answer:** Express — the volume and short duration make Standard's per-state-transition pricing dramatically more expensive (the cited comparison shows roughly a 40x cost difference at 10 million executions), the sub-5-minute cap isn't a constraint at 2 seconds per execution, and the stated tolerance for occasionally losing an event on failure matches Express's at-least-once (async) or at-most-once (sync) semantics rather than requiring Standard's exactly-once guarantee.
**Follow-up trap:** *"The requirement changes: no event may ever be lost, even on failure."* — that changes the answer to Standard, or to Express with the workflow itself explicitly writing to a durable, idempotent sink as its first step so that even an at-least-once retry doesn't lose data — the semantics gap between Express and Standard is a correctness decision, not a performance tuning knob.

### Q5 — REST or HTTP API Gateway for a new internal microservice API with no partner-facing rate-limit tiers?
**Answer:** HTTP API — at roughly a third of REST's per-request cost and covering the same core proxy-to-backend functionality, REST's extra features (usage plans for differentiated API-key tiers, request/response transformation, native WAF) aren't needed for an internal service with no external partner tiering requirement.
**Follow-up trap:** *"Six months later, a partner integration needs a rate-limited API key with a monthly quota. Do you migrate the whole API to REST?"* — usage plans are REST-only, so if that specific feature becomes a hard requirement, either migrate the specific partner-facing routes to a REST API Gateway while keeping internal routes on HTTP API, or implement rate limiting/quota enforcement in application code (e.g. via a shared cache-backed limiter) rather than migrating the whole surface.

### Q6 — At what point does an ALB+Fargate service become cheaper than API Gateway + Lambda for the same traffic?
**Answer:** There's no universal number — it's a function of sustained request volume against API Gateway's linear per-request pricing versus ALB+Fargate's roughly fixed capacity cost within a given provisioned size. At low-to-moderate, spiky traffic, API Gateway + Lambda wins on zero idle cost. At sustained high volume, the linear-vs-fixed cost curves cross, and cited estimates put a modest ALB+Fargate baseline around $40-90/month regardless of request volume within its capacity — the actual crossover point needs to be computed against real traffic, not assumed.
**Follow-up trap:** *"Cost aside, is there a latency argument either way?"* — yes: a Fargate service behind an ALB doesn't cold-start per request and gives more consistent latency at sustained volume, while Lambda behind API Gateway can show cold-start variance for infrequently-invoked functions — for a latency-consistency-critical, high-and-steady-traffic service, ALB+Fargate can win on both cost and latency simultaneously at the right volume.

### Q7 — Explain the difference between Step Functions' at-least-once and at-most-once semantics in Express workflows, concretely.
**Answer:** Asynchronous Express executions are at-least-once — if the execution's start request is retried (e.g. due to a network issue on the caller's side, or an internal retry), the workflow could run twice. Synchronous Express executions are at-most-once — if something fails partway through, the workflow doesn't automatically retry the whole execution, so partial work can be lost rather than duplicated. Standard workflows are exactly-once regardless of sync/async invocation.
**Follow-up trap:** *"Which failure mode is worse for a workflow that sends a customer-facing notification?"* — depends on the business impact: at-least-once risks a duplicate notification (usually an annoyance, sometimes fixable with an idempotency key on the notification send itself), at-most-once risks a notification never being sent at all (often the worse failure for anything customer-expectation-critical) — the "worse" answer isn't universal, it's a judgment call based on which failure the business tolerates less.

### Q8 — Design idempotent processing for an SQS consumer where the message body legitimately can repeat with different meaning (e.g. "user clicked button" events that are genuinely identical in content across different real clicks).
**Answer:** Content-based deduplication (hashing the message body) is wrong here because it can't distinguish two genuinely distinct events with identical content — use an explicit, unique `MessageDeduplicationId` generated at the producer (e.g. combining a request ID or timestamp with enough precision to be unique per real event) rather than relying on the message body itself as the dedup signal, whether using SQS FIFO's built-in dedup window or your own DynamoDB-backed dedup table.
**Follow-up trap:** *"What if the producer can't reliably generate a unique ID (e.g. it's a dumb client replaying identical payloads)?"* — then dedup has to happen based on some other signal available at ingestion (a client-side sequence number, a server-assigned request ID stamped at the edge before the message enters the queue) — pure content-based dedup structurally cannot solve this case, which is worth saying explicitly rather than pretending a hash-based fix would work.

### Q9 — Your EventBridge rule stopped matching events after a producer team changed their event schema. How do you prevent this class of bug going forward?
**Answer:** Use EventBridge's schema registry to track and version the actual event shapes flowing through the bus, and treat a producer's schema change as a breaking-change conversation (versioned event types, or an explicit migration window) rather than a silent deploy — the registry gives you a place to detect the drift before it causes a silent rule-matching failure in production.
**Follow-up trap:** *"The schema registry shows the drift, but the rule pattern still needs updating manually. Isn't this the same problem with extra steps?"* — the registry doesn't eliminate the coordination need, but it converts a silent failure (a rule quietly stops matching, an unknown fraction of events, discovered only when someone notices missing downstream processing) into a visible, versioned diff you can review before deploying against — visibility, not automation, is the actual value being asked about here.

### Q10 — A workflow needs to wait for a human approval step that could take anywhere from minutes to several days. Standard or Express Step Functions?
**Answer:** Standard — Express's 5-minute maximum duration makes it structurally incapable of representing a wait step that could last days; Standard supports up to a year and has a native "wait for callback" pattern (`waitForTaskToken`) specifically designed for human-in-the-loop or other long-running external approval steps.
**Follow-up trap:** *"Could you work around Express's 5-minute limit by polling an external approval status from outside the workflow?"* — technically yes (have an external process invoke a new Express execution once approval lands), but that's reimplementing what Standard's callback pattern already does natively, with more moving parts and more places for the "did the approval actually get picked up" bug to hide — there's no real advantage over just using Standard for this shape of workflow.

### Q11 — What's the practical difference between SNS message filtering and EventBridge event patterns?
**Answer:** SNS filter policies match on message *attributes* (key-value metadata attached to the publish call) for subscriptions to a single topic. EventBridge event patterns match on the actual JSON *structure and values* of the event body itself, across events from many different sources landing on the same bus, with support for more expressive matching (prefix, numeric ranges, exists/doesn't-exist) and a schema registry to track what shapes are actually flowing through.
**Follow-up trap:** *"If SNS filtering is 'good enough' for your current single-source use case, is there still a reason to prefer EventBridge?"* — if you're confident the system will stay single-source with simple attribute-based routing, SNS+SQS is legitimately simpler and cheaper; the reason to prefer EventBridge anyway is forward-looking — schema drift detection and native archive/replay are valuable even in a simple system, and retrofitting them later after adopting SNS is more work than starting with EventBridge.

### Q12 — Design the integration layer for a system ingesting webhooks from 6 different third-party SaaS vendors, each with different event shapes, requiring different downstream processing per vendor, with the ability to replay the last 24 hours of events if a downstream consumer bug is discovered.
**Answer:** EventBridge as the ingestion bus — receive each vendor's webhook via API Gateway routing into EventBridge (or via EventBridge's native SaaS partner event sources where the vendor is supported), define per-vendor event patterns as rules, route each to its own downstream target (Lambda, SQS, Step Functions) for vendor-specific processing, and enable an EventBridge archive on the bus scoped to a 24+ hour retention window for the stated replay requirement. This is close to the canonical use case EventBridge's archive/replay feature was built for.
**Follow-up trap:** *"One vendor sends events at a sustained 500/second, far higher than the others. Does that change the design?"* — not fundamentally; EventBridge scales independently per rule/target, but you'd want that specific rule's target to be something that can absorb bursty high volume gracefully (an SQS queue as a buffer in front of the actual processing Lambda, rather than invoking Lambda directly from the rule) to avoid downstream throttling on that one vendor's traffic spilling into processing delays for the others.

---

## Red flags that fail you

- Not immediately naming the visibility timeout as the cause of a duplicate-processing bug.
- Treating SQS, SNS, and EventBridge as interchangeable "just pick one" options without naming what each is actually for.
- Recommending Standard Step Functions by default without considering per-state-transition cost at volume.
- Not knowing Express Step Functions has a 5-minute cap and non-exactly-once semantics.
- Assuming REST API Gateway is the default without asking whether usage plans/WAF/validation are actually needed.
- Claiming API Gateway is always cheaper (or always more expensive) than ALB+Fargate without acknowledging it's volume-dependent.
- Treating idempotency as optional or as something to add later "if duplicates become a problem."

---

## Cheat card

```
SQS STANDARD  ~unlimited TPS, at-least-once, best-effort ordering
SQS FIFO      300 TPS unbatched / 3,000 batched / 30,000 high-throughput
              (relaxed cross-group order) -- exactly-once w/in 5-min dedup window
VISIBILITY TIMEOUT  default 30s, 0s-12hr range
  BUG: timeout < handler p99 -> msg reappears mid-processing -> DUPLICATE side effect
  fix: timeout > p99, or ChangeMessageVisibility, PLUS idempotency key regardless
DLQ           maxReceiveCount exceeded -> DLQ; redrive to replay after fix

SNS           fan-out to ALL subscribers; filter policy = attribute match per sub
EVENTBRIDGE   content-based rules (JSON pattern match), schema registry,
              native ARCHIVE + REPLAY, best for multi-source/SaaS ingestion
  SQS=mailbox(1 consumer) / SNS=megaphone(all subs) / EventBridge=switchboard(routed)

STEP FN STANDARD  $0.025/1000 transitions, up to 1yr, EXACTLY-ONCE, visual history
STEP FN EXPRESS   ~$1/1M requests+duration, max 5 MIN, at-least-once(async)/
                  at-most-once(sync) -- 40x+ cheaper at volume, NOT a free lunch
  10M execs of 5-state workflow: Standard ~$1,250 vs Express ~$31
  Retry{ErrorEquals,IntervalSeconds,MaxAttempts,BackoffRate} + Catch per state

API GW REST   $3.50/1M -- usage plans, validation, native WAF, custom authorizers
API GW HTTP   $1.00/1M (~70% cheaper) -- DEFAULT choice, covers 90% of cases
API GW WS     billed by connection-minutes + messages
THROTTLE      account default ~10k RPS burst / 5k steady (region), + per-stage
ALB+FARGATE   ~fixed cost regardless of volume -- wins over API GW at sustained
              high request volume; no per-request cold start

IDEMPOTENCY   at-least-once is the DEFAULT here, everywhere. dedup key +
              ATOMIC conditional write (not read-then-write) before any side effect
```

## Sources

- [SQS Standard vs FIFO — jayendrapatil](https://jayendrapatil.com/aws-sqs-standard-vs-fifo/) — accessed 2026-08-01
- [FIFO queue delivery logic — AWS docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-understanding-logic.html) — accessed 2026-08-01
- [Amazon SQS visibility timeout — AWS docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html) — accessed 2026-08-01
- [AWS SQS vs SNS vs EventBridge: When to Use Each — nOps](https://www.nops.io/blog/aws-sqs-vs-sns-vs-eventbridge/) — accessed 2026-08-01
- [Demystifying AWS Step Functions Pricing — Oreate AI](https://www.oreateai.com/blog/demystifying-aws-step-functions-pricing-standard-vs-express-workflows/8a708291c920da86b15b18ea6492b032) — accessed 2026-08-01
- [AWS API Gateway Pricing Simplified — CloudZero](https://www.cloudzero.com/blog/aws-api-gateway-pricing/) — accessed 2026-08-01
- [API Gateway versus ALB in terms of costs — Vairix](https://www.vairix.com/tech-blog/api-gateway-versus-alb-in-term-of-costs) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
