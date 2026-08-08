# Cloud Run, Cloud Functions, App Engine, Eventarc

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.0h · **Prereqs:** `C-GCP-iam` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-serverless` · **Tags:** serverless

## The 30-second version

Cloud Run is a request-triggered container runtime that **scales to zero and bills per 100ms of actual CPU/memory consumption** — the default "CPU only allocated during request processing" mode means an idle instance costs nothing and the platform genuinely stops billing between requests, which is the single biggest structural difference from AWS Fargate. Fargate has no first-class scale-to-zero: you pay per-second for every provisioned task whether or not it's handling traffic, and while you *can* configure Application Auto Scaling down to zero tasks, nothing wakes it back up on an incoming request the way Cloud Run's front-end does — you need an external trigger, and the cold start back from zero (ENI provisioning, image pull) runs tens of seconds to minutes, not Cloud Run's sub-second-to-few-seconds. **Cloud Functions (now branded "Cloud Run functions")** is Cloud Run under the hood for 2nd gen: same scaling engine, same Eventarc trigger plumbing, just a thinner deployment model (one function, no Dockerfile) with a 1st-gen legacy tier that's structurally different (1-request-per-instance, no concurrency, separate pricing) and worth explicitly distinguishing from 2nd gen in an interview. **Eventarc** is the unified event router — nearly 200 first-party Google Cloud event sources plus arbitrary Pub/Sub and Cloud Audit Log-derived events — that feeds both Cloud Run services and Cloud Run functions from the same trigger model, replacing what used to be per-product bespoke trigger configuration.

## Why this gets asked

The interviewer has personally sized a Fargate service for a spiky, low-traffic workload and watched the bill stay flat regardless of traffic because Fargate doesn't know how to go to zero on its own, and has separately debugged a Cloud Run service where CPU throttling between requests silently broke a background thread the developer assumed was still running. They want to know you understand *why* Cloud Run's billing model changes the cost-shape of a system, not just that it "is serverless."

---

## Lineage: past → present → future

**What came before.** App Engine (2008) was Google's first serverless compute product — Standard environment ran your code in a sandboxed, language-specific runtime with true scale-to-zero and per-request billing, which was genuinely ahead of its time, but the sandbox constrained you to specific language versions and a limited set of allowed libraries/APIs, and Flexible environment (VM-backed, more general) gave up the fast scale-to-zero to get generality. The pain that followed App Engine for a decade: teams wanted App Engine's operational simplicity without its runtime lock-in, and Kubernetes (2014) proved containers were the right general-purpose unit of deployment but brought enormous operational surface area (cluster upgrades, node pools, autoscaler tuning) that most teams running a handful of stateless services didn't want to own.

**Where it stands now.** Cloud Run (GA 2019) is Google's answer: take Knative's container-as-a-service model, strip out the Kubernetes control plane the developer has to manage, and bill per-request/per-100ms rather than per-provisioned-capacity. Cloud Functions 2nd gen (GA 2022) then **rebuilt itself on top of Cloud Run and Eventarc** rather than maintaining a separate execution engine, which is why 2nd gen functions support concurrency (multiple requests per instance) and longer timeouts that 1st gen never could — 1st gen predates Cloud Run and hard-codes one request per instance. As of 2025-2026 Google has formally rebranded the product **"Cloud Run functions"**, with 1st gen kept alive under a distinct legacy pricing page rather than folded in, signaling Google itself treats 1st gen as a separate, aging product line. [Cloud Run functions pricing overview — Google Cloud docs](https://cloud.google.com/functions/pricing-overview) — accessed 2026-08-08. The live disagreement in the ecosystem is Cloud Run vs GKE Autopilot for "I don't want to manage nodes": Cloud Run wins on simplicity and true scale-to-zero for stateless HTTP/event workloads; GKE Autopilot wins once you need sidecars, StatefulSets, custom scheduling, or non-HTTP protocols Cloud Run doesn't support natively (arbitrary TCP, for instance).

**Where it's heading.** Cloud Run's **worker pools** and background/non-HTTP workload support (GA-adjacent through 2025-2026) is closing the historical gap where Cloud Run could only really do request/response HTTP or Pub/Sub-push-triggered work — moderate-to-high confidence this keeps expanding, since it directly answers "why would I ever use GKE for a simple background worker." Eventarc Advanced (newer tier with format conversion, private connectivity, more enterprise routing controls) is Google's direction for event infrastructure that outgrows the original Eventarc's simpler model — moderate confidence, still maturing. App Engine itself is in maintenance mode in all but messaging — Google doesn't recommend it for new projects, and Cloud Run is the explicit successor; treating App Engine as a live recommendation in an interview is a mild red flag.

---

## Mental model

```
CLOUD RUN REQUEST LIFECYCLE (default: CPU only allocated during request)
  no traffic ──▶ ZERO instances, ZERO cost
       │
       ▼ request arrives
  cold start (pull image if needed, start container, run init code)
       │
       ▼
  instance handles up to `concurrency` simultaneous requests (default 80,
  configurable up to 1000/instance) — CPU is throttled to near-zero the
  instant there's no in-flight request on that instance UNLESS you set
  "CPU always allocated" (then it behaves like a normal always-on box,
  billed continuously, background threads/timers actually keep running)
       │
       ▼ no more requests for up to 15 min (10 min for GPU instances)
  instance goes idle, then is torn down → back to zero
       [Cloud Run docs — About instance autoscaling — accessed 2026-08-08]

FARGATE FOR COMPARISON — no native "wake on request"
  ECS service desired-count=0 (if you configure Auto Scaling to allow it)
       │
       ▼ requires an EXTERNAL trigger (CloudWatch alarm, scheduled scale-up,
       │  an ALB target group healthy-count driven scaling policy — nothing
       │  built-in listens on the network path the way Cloud Run's front
       │  door does)
  new task: ENI attachment + image pull + container start
       = tens of seconds to low minutes, not "next request, few hundred ms"

EVENTARC — one trigger model feeding Cloud Run services AND functions
  ~200 first-party GCP event sources  ─┐
  Pub/Sub topics                      ─┼──▶ EVENTARC TRIGGER ──▶ Cloud Run
  Cloud Audit Log events (any API     ─┘         service or
    call, any resource)                          Cloud Run function
```

---

## How it actually works

### Cloud Run billing: the mechanic that actually matters

Two CPU allocation modes, and picking the wrong one is the most common Cloud Run cost/correctness mistake:

- **CPU only allocated during request processing** (default): CPU is throttled to near-zero the instant an instance has no in-flight request. This is what makes scale-to-zero cheap, but it also means any background work you kick off inside a request handler and expect to keep running *after* you return the response (a detached async task, a timer, a background thread flushing a queue) gets starved mid-flight. This is the single most common "why did my background job silently stop" Cloud Run incident.
- **CPU always allocated**: the instance behaves like a normal always-on box between requests — background threads actually keep running, but you're billed continuously for that instance's lifetime, closer to Fargate's cost shape.

Billing granularity is per-100-millisecond increments of vCPU-time and memory-time actually consumed, plus a flat per-request charge — the practical effect is that a service handling bursty, idle-heavy traffic can cost a small fraction of an equivalently-sized Fargate service that's provisioned (and billed) continuously regardless of load. **Concurrency** defaults to 80 simultaneous requests per instance and can be raised up to **1,000** — raising it doesn't add cost by itself, but it changes how many instances you need for a given load (fewer, busier instances vs more, idler ones), which matters for both cost and blast-radius-per-instance-failure reasoning.

```yaml
# untested sketch — Cloud Run service.yaml relevant knobs
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: order-api
  annotations:
    run.googleapis.com/cpu-throttling: "false"   # "CPU always allocated"
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"      # avoid cold starts, costs $$
        autoscaling.knative.dev/maxScale: "100"
    spec:
      containerConcurrency: 80
      containers:
      - image: gcr.io/my-project/order-api
        resources:
          limits:
            cpu: "2"
            memory: "1Gi"
```

An idle instance is kept warm for **up to 15 minutes** (10 minutes for GPU-backed instances) after its last request before Cloud Run tears it down, which is why `minScale: 1` (or higher) is the standard fix for latency-sensitive services that can't tolerate the occasional cold start. [About instance autoscaling in Cloud Run services — Google Cloud docs](https://docs.cloud.google.com/run/docs/about-instance-autoscaling) — accessed 2026-08-08.

### Cloud Functions 1st gen vs 2nd gen ("Cloud Run functions")

| | 1st gen | 2nd gen (Cloud Run functions) |
|---|---|---|
| Execution engine | Bespoke, pre-Cloud-Run | Cloud Run under the hood |
| Concurrency per instance | 1 request | Up to 1,000 (configurable) |
| Max request timeout | 9 minutes | Up to 60 minutes (HTTP), matching Cloud Run |
| Trigger model | Bespoke per-product | Eventarc (unified) |
| Deployment unit | Single function, runtime-managed | Function *or* full container image |
| Cold start behavior | Generally worse — no shared warm pool logic with Cloud Run | Benefits from Cloud Run's scaling engine improvements |

The practical interview-relevant takeaway: if someone describes "Cloud Functions" without specifying generation, ask — 1st gen's one-request-per-instance model means concurrency and cost-per-load behave completely differently than 2nd gen's Cloud-Run-backed model.

### Eventarc — trigger sourcing and the latency trap

Eventarc triggers come from three lanes: **direct events** (first-party events emitted natively by ~100+ Google Cloud services — Cloud Storage object finalize, Firestore document writes, Cloud Pub/Sub messages), **Cloud Audit Log-derived events** (any API call against any resource that emits an audit log — much broader coverage since it covers services without native direct-event support, but sourced from audit logs rather than a dedicated event stream, so it can lag a real-time direct event by seconds where a direct event source exists), and plain **Pub/Sub** triggers (you publish, Eventarc delivers to the target). The trap: choosing an audit-log-derived trigger for a source that also offers a direct event, purely out of habit, gives up the lower-latency, purpose-built delivery path for no benefit.

---

## Build it from scratch

Minimal event-driven pipeline: a file lands in Cloud Storage, Eventarc fires a Cloud Run function.

```python
# untested sketch — Cloud Run function (2nd gen), Eventarc CloudEvents handler
import functions_framework

@functions_framework.cloud_event
def process_upload(cloud_event):
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]
    # ... process the object ...
    print(f"processed gs://{bucket}/{name}")
```

```bash
# untested sketch
gcloud functions deploy process-upload \
  --gen2 \
  --runtime=python312 \
  --trigger-bucket=my-uploads-bucket \
  --entry-point=process_upload \
  --memory=512Mi \
  --timeout=300s \
  --max-instances=50
```

---

## How it's done in production

A typical production serverless layer: Cloud Run for anything with an HTTP surface or that benefits from full container control (custom base images, multiple processes, non-Python/Node runtimes with specific native dependencies), Cloud Run functions (2nd gen) for small, single-purpose event handlers where a Dockerfile is overhead, `minScale >= 1` on latency-sensitive user-facing services to avoid cold starts on the request path, `minScale: 0` freely on internal/batch-adjacent/webhook-style services where an occasional cold start is invisible, and Eventarc direct-event triggers preferred over audit-log-derived triggers whenever a direct source exists for the same event.

| Symptom | Cause | Fix |
|---|---|---|
| A background task started inside a request handler silently stops partway through | Default "CPU only allocated during request processing" throttles CPU to near-zero once the response is returned, starving any detached work | Either await the work before returning the response, move it to a real queue-consumed task (Cloud Tasks, Pub/Sub push to another handler), or explicitly enable "CPU always allocated" if the cost tradeoff is acceptable |
| p99 latency has periodic spikes correlated with low-traffic periods | Cold starts from `minScale: 0` — instances torn down after 15 minutes idle, next request pays full cold-start cost | Set `minScale >= 1` (or higher for HA) on the affected service; accept the always-on cost for that specific service |
| Fargate service costs stay flat even though traffic dropped to near-zero overnight | Fargate has no built-in wake-on-request scale-to-zero; provisioned task count doesn't self-adjust to zero without external Auto Scaling configuration, and even then nothing "wakes" it on the next request without an explicit trigger | Either accept the always-provisioned cost model as the tradeoff for Fargate's simplicity, or migrate the workload to Cloud Run if genuine scale-to-zero with request-triggered wake is the actual requirement |
| Cloud Run function using an audit-log-derived Eventarc trigger reacts to events later than expected | Audit-log-sourced events aren't a dedicated real-time stream; delivery can lag behind a direct event source for the same underlying action | Switch to a direct event trigger if the source service offers one for that event type; reserve audit-log triggers for sources with no native direct-event support |
| A 1st-gen Cloud Function is expensive and slow under moderate concurrent load | 1st gen allows exactly one request per instance — every concurrent request spins up a separate instance, unlike 2nd gen's shared-instance concurrency | Migrate to 2nd gen (Cloud Run functions) to get concurrency, or move the workload to Cloud Run directly for more control |
| Cloud Run service throttles unexpectedly under a request that legitimately needs sustained background CPU after responding | Same "CPU only allocated" default throttling issue, misdiagnosed as a Cloud Run outage | Confirm CPU allocation mode before escalating; this is a configuration choice, not a platform bug |

---

## Tradeoffs & when NOT to use it

- **Don't use Cloud Run for workloads needing arbitrary long-lived TCP connections, stateful in-memory session affinity beyond what its session-affinity feature offers, or non-HTTP-shaped protocols** it doesn't support natively — GKE (Standard or Autopilot) is the right tool once the workload stops looking like request/response or short event handling.
- **Don't default to "CPU always allocated" just to avoid the background-task-throttling trap.** That gives up the scale-to-zero cost advantage entirely for the whole service; the better fix is almost always to make background work synchronous-to-the-response or queue-based, not to pay for always-on CPU.
- **Don't treat App Engine as a live recommendation for new projects.** It's functionally superseded by Cloud Run for nearly every use case Standard environment used to serve, and proposing it in a design interview without qualification reads as dated.
- **Don't use 1st-gen Cloud Functions for anything new.** 2nd gen (Cloud Run functions) is strictly more capable (concurrency, longer timeouts, Eventarc) with no real downside except a very marginal cold-start difference in some cases; 1st gen exists for legacy compatibility only.
- **Don't reach for audit-log-derived Eventarc triggers when a direct event source exists for the same action.** It's strictly worse latency and coverage for no benefit — the only reason to use audit-log triggers is when the source service has no native direct-event support.
- **Don't assume Fargate's lack of true scale-to-zero is a bug to route around with aggressive Auto Scaling min=0 configurations for latency-sensitive services.** The cold-start cost from zero on Fargate (ENI + image pull, tens of seconds to minutes) is often worse than just paying for a small always-on baseline — evaluate the actual cost/latency tradeoff rather than chasing zero cost reflexively.

---

## Interview questions

### Q1 — Explain precisely why Cloud Run "scales to zero" in a way Fargate doesn't, mechanically.
**Testing:** whether the candidate understands the architectural reason, not just the marketing line from the cross-cloud map.
**Answer:** Cloud Run's front door is itself a managed, always-available request router that can hold/queue an incoming request while spinning up a fresh instance on demand — the "wake on request" capability is a first-class part of the platform. Fargate has no equivalent always-on request-routing layer that triggers task launches; ECS/Fargate services maintain a desired task count that Auto Scaling can adjust based on metrics (CPU, queue depth, custom CloudWatch metrics), but there's no built-in mechanism that holds an inbound request and launches a task specifically in response to it hitting zero capacity. Reaching zero tasks with Fargate requires configuring Auto Scaling's minimum to zero explicitly, and getting back from zero requires some other trigger (a scheduled job, an alarm-driven scale-out, a load balancer health-check-driven policy) — not the request itself.
**Follow-up trap:** *"So Fargate literally cannot scale to zero at all?"* — it can be configured to scale down to zero tasks via Application Auto Scaling, but doing so removes the always-available request-serving capability entirely until something external triggers scale-out, and that cold path (ENI provisioning, image pull, health checks) typically takes tens of seconds to a couple of minutes — categorically different from Cloud Run's per-request wake latency.

### Q2 — A team enables "CPU only allocated during request processing" (the default) and then reports their background job that kicks off after returning an HTTP 200 keeps silently stopping partway through. Diagnose.
**Testing:** the single most commonly-hit Cloud Run production gotcha.
**Answer:** With the default CPU allocation mode, Cloud Run throttles the instance's CPU to near-zero the moment there's no in-flight request being served. A detached background task started inside the handler and left running after the response is returned gets starved — it doesn't error, it just stops making progress, which is why it's a silent failure rather than a loud one. Fix: either await the work synchronously before returning the response, offload it to a properly queue-consumed task (Cloud Tasks, or publish to Pub/Sub and let a separate handler process it), or explicitly switch that service to "CPU always allocated" if the cost tradeoff of always-on billing is acceptable for that specific service.
**Follow-up trap:** *"Doesn't `min-instances=1` fix this too, since the instance never goes cold?"* — no; `min-instances` keeps an instance warm and avoids cold starts, but CPU throttling under the default allocation mode still applies to a warm, idle instance the moment it has no in-flight request — the two settings solve different problems and neither substitutes for the other.

### Q3 — Compare Cloud Functions 1st gen and 2nd gen concurrency models and explain the cost/performance consequence.
**Testing:** currency on the actual architectural difference, plus quantified reasoning.
**Answer:** 1st gen allows exactly one request per instance — every concurrent request, even to an idle-CPU-fast function, spins up (or queues for) a separate instance. 2nd gen (Cloud Run functions) is built on Cloud Run and supports genuine per-instance concurrency, configurable up to 1,000 simultaneous requests per instance for workloads that are I/O-bound rather than CPU-bound. The consequence: a bursty workload with many short, I/O-heavy requests can run on a small number of 2nd-gen instances handling many requests each, versus 1st gen needing an instance per concurrent request — materially different cost and cold-start-exposure profiles under load.
**Follow-up trap:** *"Is 2nd gen concurrency free — should you always max it out to 1,000?"* — no; concurrency only helps if the workload isn't CPU-bound per request, and cranking it too high on CPU-bound work causes requests to contend for the same instance's CPU allocation, degrading per-request latency even though instance count (and cost) looks lower. It needs to be tuned to the workload's actual CPU/IO shape, not maximized blindly.

### Q4 — When would you choose GKE Autopilot over Cloud Run for a workload that's still "mostly stateless services"?
**Testing:** the real "when NOT to use Cloud Run" judgment.
**Answer:** Once the workload needs things Cloud Run doesn't support natively — arbitrary long-lived non-HTTP TCP protocols, sidecar containers beyond Cloud Run's limited multi-container support, StatefulSet-style stable network identity and persistent per-pod storage, fine-grained custom scheduling/affinity rules, or a service mesh with capabilities beyond what Cloud Run's simpler traffic-splitting offers — GKE Autopilot keeps the "don't manage nodes" simplicity while giving up none of Kubernetes's generality.
**Follow-up trap:** *"Doesn't Cloud Run's newer worker-pool support close most of that gap now?"* — it closes the "I just need a non-HTTP background worker" gap significantly, but it doesn't add StatefulSet-style identity, custom scheduling, or full sidecar generality — verify against current Cloud Run docs before claiming full parity, since this is one of the faster-moving parts of the platform.

### Q5 — Explain the difference between a direct Eventarc event and an audit-log-derived Eventarc event, and why the distinction matters operationally.
**Testing:** whether the candidate has actually configured Eventarc triggers, not just used the word.
**Answer:** A direct event is emitted natively by the source service (Cloud Storage object finalize, Firestore writes, Pub/Sub messages) through a purpose-built event stream. An audit-log-derived event is sourced from Cloud Audit Logs — any API call against any resource that produces an audit log entry can become a trigger, which gives far broader coverage (any service, not just ones with native direct-event support) but at the cost of being sourced from a logging pipeline rather than a dedicated real-time event stream, which can introduce more delivery lag than a direct event for the same underlying action.
**Follow-up trap:** *"If a source offers both, is there ever a reason to prefer the audit-log-derived trigger anyway?"* — rarely; the honest answer is direct events should be preferred whenever available. A defensible edge case is needing to trigger on an action pattern only expressible via the audit log's richer method/permission-level filtering rather than the direct event's narrower schema, but this is uncommon enough that defaulting to audit-log triggers without a specific reason is a design smell.

### Q6 — Design the Cloud Run configuration for a payment-processing API that cannot tolerate cold starts, versus an internal webhook receiver that can.
**Testing:** applying `minScale`, concurrency, and CPU allocation together to two different SLA shapes.
**Answer:** Payment API: `minScale >= 2` (avoid both cold starts and single-instance risk), moderate concurrency tuned to the actual per-request CPU cost (likely lower, since payment logic often does meaningful per-request work), and "CPU always allocated" only if there's genuine background work per request that must survive past the response — otherwise the default throttled mode is fine since the instance stays warm via `minScale` anyway. Internal webhook receiver: `minScale: 0` is fine, higher concurrency (I/O-bound, cheap per request), default CPU allocation mode, since occasional cold starts on an internal, non-user-facing path are invisible to end users.
**Follow-up trap:** *"Does `minScale >= 2` guarantee zero cold starts under all traffic patterns?"* — no; it guarantees at least 2 warm instances are always available, but a sudden traffic spike beyond what those instances can handle at the configured concurrency still triggers new cold-start instances to handle the overflow — `minScale` reduces cold-start *frequency* for baseline traffic, it doesn't eliminate cold starts during scale-out events.

### Q7 — A candidate says "Cloud Run functions and Cloud Run services are basically the same thing now." Is that accurate?
**Testing:** precision about what "built on Cloud Run" actually means versus full equivalence.
**Answer:** It's directionally correct but imprecise. 2nd-gen Cloud Run functions run on the same underlying scaling and request-routing engine as Cloud Run services and share the Eventarc trigger model, so the *runtime mechanics* (scale-to-zero, concurrency, CPU allocation modes) are genuinely shared. They're not identical products, though: Cloud Run functions offer a thinner, function-first deployment experience (no Dockerfile required, runtime-managed dependency installation) aimed at single-purpose handlers, while Cloud Run services expect a full container image and support arbitrary multi-process, multi-language, custom-base-image workloads. Cloud Run functions can be deployed either as a managed function *or* as a full container image, blurring the line further.
**Follow-up trap:** *"Does that mean I should always just use Cloud Run services and skip functions entirely?"* — not necessarily; for a genuinely single-purpose event handler with no custom runtime dependencies, the functions deployment path removes Dockerfile/build-pipeline overhead that adds no value for that use case — the choice is about deployment ergonomics for the specific workload shape, not a strict technical superiority of one over the other.

### Q8 — How would you estimate whether a spiky, low-average-traffic internal service is cheaper on Cloud Run or Fargate?
**Testing:** applied cost-model reasoning, a common system-design/cost-estimation probe.
**Answer:** Model actual traffic shape: total request count, average CPU/memory-seconds consumed per request, and the fraction of time the service genuinely has zero in-flight traffic. Cloud Run's cost is roughly (vCPU-seconds actually consumed × per-second rate) + (memory-seconds actually consumed × per-second rate) + (per-request charge), billed in 100ms increments, with **zero cost during idle windows** under the default CPU allocation mode. Fargate's cost is (provisioned vCPU × hours running × per-vCPU-hour rate) + (provisioned memory × hours running × per-GB-hour rate), billed continuously for however many tasks are provisioned, regardless of whether they're handling traffic — the idle windows cost the same as the busy windows unless Auto Scaling actively reduces task count, and even then reaching zero gives up availability during the cold-start-back-up window. For a workload with long idle stretches and short traffic bursts, Cloud Run is very likely cheaper; for a workload with consistently high, steady utilization, the two converge and Fargate's simpler, more predictable operational model can win on other grounds even if raw cost is comparable.
**Follow-up trap:** *"Does higher concurrency always reduce Cloud Run cost for the same total traffic?"* — only up to the point where the workload's per-request CPU/memory needs don't force contention; beyond that, increasing concurrency without enough allocated CPU just degrades latency without reducing total vCPU-seconds billed, since you're still doing the same total amount of work, just packed differently onto instances.

### Q9 — Why did Google rebuild Cloud Functions 2nd gen on top of Cloud Run rather than maintaining a separate execution engine?
**Testing:** lineage/architecture reasoning, tests whether the candidate understands *why*, not just *that*.
**Answer:** Maintaining two separate serverless execution engines (1st-gen Functions' bespoke one-request-per-instance model, and Cloud Run's more general concurrent-container model) meant duplicating scaling logic, cold-start optimization work, and trigger infrastructure, while giving Functions users a strictly worse concurrency and timeout story for no architectural reason. Building 2nd gen on Cloud Run let Google converge the two products' underlying mechanics — every scaling and cold-start improvement made to Cloud Run automatically benefits Cloud Run functions — while keeping the lighter-weight, function-first deployment experience as the product-level differentiator rather than a runtime-level one.
**Follow-up trap:** *"If they share the same runtime, why does 1st gen still exist at all instead of being migrated automatically?"* — 1st gen has behavioral differences (strict one-request-per-instance execution semantics some existing code implicitly depends on, different IAM/trigger configuration surface) that make automatic migration unsafe for existing production functions; it remains available for backward compatibility, with Google's explicit guidance being to use 2nd gen for anything new rather than to expect 1st gen's imminent removal.

### Q10 — Design an event-driven pipeline: a user uploads a large file to Cloud Storage, which must trigger virus scanning, then thumbnail generation, then a database update, with each stage independently scalable and retryable.
**Testing:** staff-level synthesis of Eventarc, Cloud Run/functions, and failure-isolation design.
**Answer:** Cloud Storage object-finalize emits a direct Eventarc event to a first Cloud Run function (virus scan) rather than chaining stages via direct function-to-function calls, so each stage is independently retryable and observable. On success, the scan stage publishes a Pub/Sub message (not a direct HTTP call) to decouple it from the next stage's availability, which an Eventarc Pub/Sub trigger delivers to a thumbnail-generation Cloud Run service (likely a service rather than a lightweight function here, since image processing can be CPU-heavy and benefit from Cloud Run's fuller resource/concurrency control). That stage publishes its own completion event, triggering a final lightweight function that updates the database. Each stage gets its own retry policy, dead-letter topic, and independent `maxScale`/concurrency tuning appropriate to its resource profile, and a failure in thumbnail generation doesn't cascade into re-running virus scanning.
**Follow-up trap:** *"Why not just chain synchronous HTTP calls between the three stages instead of Pub/Sub hops?"* — synchronous chaining couples the stages' availability and scaling directly (a slow thumbnail stage blocks the calling stage's Cloud Run instance, consuming its concurrency budget), and loses the built-in retry/dead-letter semantics Pub/Sub-backed Eventarc triggers provide for free; the extra hop's added latency is usually an acceptable tradeoff for the isolation and retry guarantees gained.

---

## Red flags that fail you

- Recommending App Engine as a first choice for a new project without qualification.
- Not knowing that Fargate lacks a native wake-on-request scale-to-zero mechanism.
- Describing "Cloud Functions" without distinguishing 1st gen from 2nd gen when the distinction changes the answer.
- Not knowing that the default Cloud Run CPU allocation mode throttles CPU between requests, and its consequence for background work.
- Recommending audit-log-derived Eventarc triggers over a direct event source with no justification.
- Claiming Cloud Run has zero cold starts with `min-instances` set, ignoring scale-out cold starts beyond warm capacity.

---

## Cheat card

```
CLOUD RUN: request-triggered, scales to ZERO. Two CPU modes: "only during
  request" (default, throttles CPU between requests -- background work after
  response silently stalls) vs "always allocated" (billed continuously, like
  Fargate's cost shape). Billed per 100ms of vCPU/memory actually consumed +
  per-request charge. Idle instance kept warm up to 15 min (10 min GPU) before
  teardown.
CONCURRENCY: default 80/instance, configurable up to 1,000/instance.
  minScale >= 1 = avoid baseline cold starts (costs $$, doesn't eliminate
  scale-out cold starts beyond warm capacity).
FARGATE COMPARISON: no built-in wake-on-request. Billed continuously per
  provisioned vCPU/memory-hour regardless of traffic. Scaling to 0 tasks
  requires explicit Auto Scaling config + an external trigger to scale back
  up; cold path (ENI + image pull) = tens of sec to minutes, not sub-second.
CLOUD FUNCTIONS 1ST GEN vs 2ND GEN ("Cloud Run functions"):
  1st gen: 1 request/instance, max 9-min timeout, bespoke engine, legacy.
  2nd gen: built on Cloud Run, concurrency up to 1,000, up to 60-min timeout,
  Eventarc triggers. Use 2nd gen for anything new.
EVENTARC: unifies triggers for Cloud Run services + functions. DIRECT events
  (~100+ native GCP sources, low latency) preferred over AUDIT-LOG-DERIVED
  events (broader coverage, any API call, but sourced from logging pipeline
  = more lag) whenever a direct source exists for the same action.
WHEN NOT TO USE CLOUD RUN: arbitrary long-lived non-HTTP TCP, StatefulSet-
  style identity, complex sidecars/scheduling -> GKE Autopilot instead.
CROSS-CLOUD: Cloud Run ~= Fargate/App Runner/Container Apps, but scales to
  zero + request-billed (the #1 differentiator). Cloud Functions ~= Lambda/
  Azure Functions. Eventarc ~= EventBridge/Event Grid.
```

## Sources

- [About instance autoscaling in Cloud Run services — Google Cloud docs](https://docs.cloud.google.com/run/docs/about-instance-autoscaling) — accessed 2026-08-08
- [Cloud Run functions pricing overview — Google Cloud docs](https://cloud.google.com/functions/pricing-overview) — accessed 2026-08-08
- [Cloud Run product overview — Google Cloud](https://cloud.google.com/run) — accessed 2026-08-08
- [Eventarc overview — Google Cloud docs](https://cloud.google.com/eventarc/docs) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
