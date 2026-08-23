# Google Cloud Serverless Deep: Cloud Run, Cloud Run Functions, App Engine, Eventarc

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2h · **Prereqs:** C-GCP-iam · **Updated:** 2026-08-23
> **Module id:** `C-GCP-serverless` · **Tags:** serverless

## The 30-second version

GCP's serverless story has converged on one substrate: everything is a Cloud Run container. Cloud Run itself is Knative-derived request-driven compute where the defining knob is *concurrency* — up to 1000 simultaneous requests packed onto one instance against a default of 80 (80×vCPU for new CLI/Terraform deploys) — which is why its economics differ fundamentally from Lambda's one-invocation-per-instance model. "Cloud Functions" no longer exists as separate infrastructure: 2nd gen became **Cloud Run functions** in August 2024, a function-shaped UX over Cloud Run plus Eventarc, which delivers CloudEvents from 90+ sources through Pub/Sub-backed triggers. Cold starts are managed with `min-instances` and startup CPU boost, not hoped away; background work dies unless you switch CPU allocation to always-on because the default throttles CPU the moment a response is sent. App Engine survives as the legacy option for old standard-environment apps and should be nobody's new-project answer.

## Why this gets asked

Because every failure mode here has a precise observable symptom interviewers have seen in production dashboards: p99 spiking to exactly the cold-start duration at 8am when the overnight-idle service gets its first request; HTTP 429s under a traffic spike because `max-instances` was left at the default 100; a background goroutine that silently stops running mid-task because the response was sent and CPU got throttled; an Eventarc trigger that deploys green and never fires because the target's service account lacks `run.invoker`. The probe underneath: do you understand request-driven compute as a capacity-and-concurrency system you must tune (instances ≈ concurrent requests ÷ concurrency), or as magic that scales? Staff-level follow-ups go straight at the economics — when does min-instances cost more than the GKE deployment you were trying to avoid?

---

## Lineage: past → present → future

**What came before.** App Engine launched in 2008 and invented much of this space — autoscaling to zero, versioned deploys with traffic splitting — but locked code into sandboxed, proprietary language runtimes with API-level access restrictions, so applications became unportable by construction. AWS Lambda (2014) then defined the modern pay-per-invocation market but hard-coded the one-concurrent-request-per-instance model. Google's own response was two-track: Cloud Functions (2017) copied Lambda's shape including its concurrency-1 limitation, while internally Google built Knative (announced 2018 with Pivotal/Red Hat/IBM) to extract the serving primitives it already ran — request-driven autoscaling, revisions, traffic splitting — into open Kubernetes building blocks. The pain that killed the old models: App Engine's lockout from normal tooling, and Lambda's economics collapsing under I/O-bound workloads where instances sit idle waiting on databases.

**Where it stands now.** The consolidation is complete and documented. Cloud Run went GA in 2019 as hosted Knative-serving-subset, grew always-on CPU, min/max instances, WebSockets/gRPC streaming, jobs, sidecars (multi-container GA 2023–2024), GPU support for inference, direct VPC egress, and Cloud Storage volume mounts. In August 2024 Google renamed Cloud Functions (2nd gen) — which had already been deploying as Cloud Run services since 2021 — to **Cloud Run functions**, making the convergence official: one execution platform, two packaging UXes (container versus function-with-buildpacks), Eventarc as the single event bus in front. [Cloud Functions is now Cloud Run functions](https://cloud.google.com/blog/products/serverless/google-cloud-functions-is-now-cloud-run-functions); accessed 2026-08-23. First-gen functions still run (9-minute cap, concurrency 1, `cloudfunctions.net` URLs) but are a migration candidate, not a choice. The live disagreement is about cold-start strategy: min-instances (pay for warmth) versus startup CPU boost (free-ish, on by default, temporarily doubles vCPU for startup plus ~10 seconds) versus accepting latency — teams genuinely split based on traffic shape, and the honest answer is measured, not ideological.

**Where it's heading.** High confidence: further absorption of adjacent services into Cloud Run semantics — scheduled jobs (Cloud Run jobs + Scheduler), worker pools, and function-style source deploys all moving into the same control plane; expect "Cloud Run" answers to remain correct for longer than any specific sibling product name. Medium confidence: serverless GPU inference becoming a mainstream Cloud Run workload (GPU attached per-instance, pay-per-second) as LLM serving moves down-market. Speculative: durable-execution-style stateful workflows converging on Workflows + Eventarc rather than a Temporal-class engine shipping natively — treat any claim that "Cloud Run has durable functions" as marketing until there's a checkpointed-state primitive.

---

## Mental model

One picture explains both the scaling behavior and the bill:

```
                        requests in flight: 170
                                 │
          ┌──────────────────────┴───────────────────────┐
          │  Cloud Run router (global LB → regional GFE) │
          └──────────────────────┬───────────────────────┘
              concurrency = 80   │   (max 1000, per instance)
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   ┌───────────┐            ┌───────────┐           ┌───────────┐
   │ instance 1│ 80 slots   │ instance 2│ 80 slots  │ instance 3│ 10 used
   │ (warm)    │            │ (warm)    │           │ (scaling…)│
   └───────────┘            └───────────┘           └───────────┘
   instances ≈ ceil(in-flight / concurrency) = ceil(170/80) = 3
   all slots busy AND at max-instances? → queue briefly → HTTP 429
```

Contrast with Lambda: concurrency 1 means 170 in-flight requests = 170 sandboxes = 170 cold-start risks and 170 sets of DB connections. On Cloud Run the same load is 3 containers. That ratio is the entire economic argument, and also the entire danger: 3 containers × 20 pooled connections each can saturate a database sized for 60 connections even though "the platform auto-scales."

The event path is a second mini-pipeline worth memorizing:

```
source (GCS object finalized / Audit Log entry / custom app publishes)
   → Eventarc TRIGGER (type + attribute filters, optional path pattern)
      → Pub/Sub topic (at-least-once transport)
         → HTTPS push to Cloud Run/function endpoint, OIDC-signed
```

## How it actually works

### Autoscaling arithmetic

Instance count tracks in-flight requests divided by concurrency, with hysteresis and a queue in front. Practical consequences worth stating precisely:

- At concurrency 80, a service doing 400 rps with 100ms average latency holds `400 × 0.1 = 40` in-flight requests — one instance. The same service at 2s latency needs 800 in flight → 10 instances. Latency, not rps, drives your bill.
- When every live instance is saturated, new requests queue at the router while a new instance starts (seconds). If the queue times out or you're at `max-instances`, callers get **429** — this is the classic "works in staging, fails on launch day" symptom.
- Scale-to-zero is default (`min-instances=0`); first request after idle pays full cold start.

### Concurrency tuning by workload

| Workload | Starting concurrency | Rationale |
|---|---|---|
| I/O-bound API (DB/HTTP waits) | 80 (default) | Overlap waits; CPU mostly idle |
| CPU-bound (image resize, ML pre/post) | 1–8 | Contention destroys p99 faster than instance count hurts cost |
| Static-ish serving | 80–100+ | Trivial per-request cost |
| WebSocket/streaming | high, but watch memory per conn | Connections are cheap, state isn't |

Tune empirically: raise until p99 degrades, back off ~20%. The metric pair that decides it is `container/cpu/utilizations` alongside `request_latencies`.

### CPU allocation, boost, and cold starts

Two independent mechanisms people conflate:

1. **CPU allocation mode.** Default is CPU only while a request is in flight (throttled otherwise). Any background thread, cache warmer, polling loop, or graceful-drain logic requires `--no-cpu-throttling` (always allocated), billed continuously per instance.
2. **Startup CPU boost** (on by default for new services): temporary extra vCPU (up to 2×) during startup plus roughly the first 10 seconds, to cut initialization time. It affects cold starts only; it does nothing for between-request work.

Cold start anatomy: schedule instance → pull image → start container → runtime/handler init. Measured orders of magnitude: warm request ~tens of ms; cold start historically ~1 second for small images (a widely cited 2020 benchmark measured ~1090ms cold vs ~32ms warm) and multiple seconds for heavyweight frameworks or large images. Mitigations in order of effectiveness: smaller image + lazy init, min-instances ≥ 1 for user-facing paths, CPU boost (already on).

### Limits that decide designs

- Request timeout: 300s default, up to 3600s (60 min) configurable for HTTP; Eventarc-triggered functions cap at 9 minutes.
- Instance size: up to 8 vCPU / 32 GiB (more on some tiers with GPUs for inference).
- Default revision max-instances 100 — raisable to thousands; treat it as downstream protection (what can your DB absorb?), not just cost cap.
- Jobs (batch) run to exit without serving HTTP; services serve requests. Use jobs for anything cron-shaped longer than a request.

### Cloud Run functions specifics

A Cloud Run function is a Cloud Run service whose container is built by buildpacks from source, exposing a function-signature handler; it uses `run.app` URLs and supports traffic splitting like any service. Key deltas from 1st gen: concurrency up to 1000 per instance (vs 1), HTTP timeout up to 60 minutes (vs 9), 16 GiB / 4 vCPU function shapes (vs 8 GiB / 2), 90+ event sources through Eventarc (vs 7 direct triggers), CloudEvents envelopes everywhere. [Compare versions — Cloud Run functions docs](https://docs.cloud.google.com/functions/docs/release-notes); accessed 2026-08-23. If you need custom binaries, sidecars, or nonstandard runtimes, drop the function pretense and deploy a plain Cloud Run service — same infrastructure.

### Eventarc mechanics

Triggers filter on event type plus attributes; two source families:

- **Direct events**: structured events emitted by partner-integrated services (Pub/Sub messages, GCS object changes, Firestore, Scheduler). Filterable by bucket/type, but not by object prefix on direct GCS events.
- **Cloud Audit Logs events**: nearly any service that writes audit entries becomes a source (`google.cloud.audit.log.v1.written` with serviceName/methodName filters and `resourceName` **path patterns** — this is how you get prefix filtering, e.g., only `objects/incoming/*`).

Delivery is Pub/Sub-backed: **at-least-once**, so handlers must be idempotent; retry policies are configurable (default up to 5 retries over hours, ~) with dead-letter topics for poison events. Two permission wires people miss: the trigger's service account needs `roles/run.invoker` on the target (else the trigger creates fine and never delivers — the silent failure), and consumers of audit-log sources need `roles/eventarc.eventReceiver`. Trigger and target must be region-aligned (with explicit global/multi-region exceptions).

### App Engine: what it is now

Standard environment: sandboxed language runtimes (Python 3, Node, Java, Go, PHP, Ruby in modern form), scale to zero, minute-level scaling granularity, cheap — but no arbitrary binaries and legacy-isms (its own dispatch rules, split health checks heritage). Flexible: GCE VMs under the hood, dockerized, never scales to zero. Every greenfield reason to pick App Engine (versioned deploys, traffic splitting, managed TLS) is now a Cloud Run feature; App Engine's remaining pull is existing estates and its bundled services (task queues heritage → Cloud Tasks). In an interview, "App Engine" as your default serverless answer reads as stale by roughly a decade.

## Build it from scratch

The autoscaler decision is simple enough to hold in your head once you've written it:

```python
# untested sketch — request-driven instance math
import math, time

class Autoscaler:
    def __init__(self, concurrency=80, min_instances=0, max_instances=100):
        self.concurrency = concurrency
        self.min_instances = max(min_instances, 0)
        self.max_instances = max_instances

    def decide(self, in_flight: int) -> dict:
        want = max(math.ceil(in_flight / self.concurrency), self.min_instances)
        want = min(want, self.max_instances)
        return {"instances": want,
                "admit": True if want < self.max_instances or
                                 in_flight <= want * self.concurrency else False}

# Little's Law drives the bill:
#   in_flight = rps * avg_latency
#   monthly_vcpu_seconds = instances * vcpu * seconds_running
rps, lat = 400, 2.0                      # 2s latency doubles vs 100ms case
print(Autoscaler().decide(math.ceil(rps * lat)))   # 10 instances at c=80
```

Deploy the real thing with every knob that matters on one command line:

```bash
gcloud run deploy api --image=us-docker.pkg.dev/proj/repo/api@sha256:... \
  --region=europe-west3 --concurrency=40 --min-instances=2 --max-instances=50 \
  --cpu=2 --memory=2Gi --cpu-boost --timeout=300 \
  --no-allow-unauthenticated --service-account=api@proj.iam.gserviceaccount.com
```

Pin digests, not tags. The event side, end to end:

```bash
gcloud eventarc triggers create incoming-files \
  --location=europe-west3 --destination-run-service=processor \
  --destination-run-path=/ --event-filters="type=google.cloud.audit.log.v1.written" \
  --event-filters="serviceName=storage.googleapis.com" \
  --event-filters="methodName=storage.objects.create" \
  --event-filters-path-pattern="resourceName=/projects/_/buckets/incoming/objects/*.csv" \
  --service-account=trigger-sa@proj.iam.gserviceaccount.com
```

That trigger fires only for CSVs under `incoming/` — prefix filtering via audit-log path patterns, which direct GCS events cannot express.

## How it's done in production

Standard shape: Terraform-managed services pinned by digest; revisions used as release units — deploy, smoke-test the revision URL, shift traffic 5% → 50% → 100%, instant rollback to the prior revision on regression; `max-instances` set from downstream capacity math (DB connection budget ÷ per-instance pool); min-instances only on user-facing paths after measuring `container/startup_latency`; always-on CPU only where background work genuinely exists. Networking: Direct VPC egress when private IPs or egress control are required (otherwise serverless NAT is the older tax); ingress restricted to internal-and-load-balancer behind a global LB + Cloud Armor for public surfaces.

| Symptom | Cause | Fix |
|---|---|---|
| p99 spikes exactly at morning peak first hit | Scale-to-zero cold start | min-instances ≥1, CPU boost, smaller image/lazy init |
| HTTP 429 under burst | At max-instances with full queues | Raise cap only after checking downstream headroom; pre-warm before known spikes |
| Background threads/goroutines die mid-work | Default CPU throttling after response sent | `--no-cpu-throttling` (always allocated); bill impact reviewed |
| Trigger deploys but never fires | Target SA missing `run.invoker`, or region mismatch | Grant invoker to trigger SA; align trigger/target regions |
| Same object processed twice | At-least-once Pub/Sub delivery redelivers | Idempotency keys / dedup on CloudEvent id |
| DB connections exhausted during scale-out | Each instance pools independently; instances ≈ load/concurrency | Lower concurrency? No — raise it or use a proxy (PgBouncer/Cloud SQL connector); cap max-instances to conn budget |
| Latency rises steadily all afternoon | Concurrency too high for CPU-bound handler | Drop concurrency until p99 flattens; add vCPU |

## Tradeoffs & when NOT to use it

- **Sustained flat high load breaks even fast against GKE.** Rough arithmetic: one always-running 2vCPU/4GiB service at ~$70–90/month-equivalent of steady Cloud Run usage (~) versus a similar footprint on committed-use GKE nodes doing triple duty. Request-driven pricing wins on spiky/idle-heavy shapes and loses on flat ones. Do the multiplication before "serverless everything."
- **Don't put long stateful sessions on plain services** without thinking: WebSockets work, but instance churn plus session affinity being best-effort means reconnect logic is mandatory.
- **Tasks over 60 minutes don't fit services** — that's Cloud Run jobs, Batch, or Workflows territory, not a bigger timeout.
- **Min-instances economics vs Lambda-style models:** keeping N warm instances costs N × instance-rate continuously; if your traffic is truly sporadic (a few requests/hour), paying for warmth can exceed simply eating cold starts. If it's human-facing, warmth usually wins. Measure startup latency first.
- **Strict static egress IPs, custom kernel modules, GPU training, >32GiB-per-request memory:** wrong platform — GKE/Compute/Batch.
- **App Engine specifically:** choose it only because it already exists in your estate. New projects gain nothing over Cloud Run and inherit a legacy runtime model.

---

## Interview questions

### Q1 — How does Cloud Run decide how many instances to run, and what does the caller see at the ceiling?
**Testing:** whether autoscaling is arithmetic or magic to them.
**Answer:** Instances track in-flight requests divided by configured concurrency (default 80, max 1000; new CLI/Terraform services default 80×vCPU): instances ≈ ceil(in-flight/concurrency), floored by min-instances, capped by max-instances. At the cap with all slots busy, requests queue briefly and then get HTTP 429. In-flight itself follows Little's Law: rps × average latency.
**Follow-up trap:** *"Your traffic tripled but instance count stayed flat — why?"* — latency also matters: if a slow dependency doubled response time, in-flight grows even at flat rps. Check request_latencies next to instance count before blaming the autoscaler.

### Q2 — Cold starts are hurting your p99. Walk me through everything you'd actually do.
**Testing:** ordered, measured mitigation rather than "add min instances."
**Answer:** Measure first (`container/startup_latency`). Then in order: shrink image and lazy-initialize heavy deps (framework import cost dominates); confirm startup CPU boost is on (default for new services — temporary ~2× vCPU during startup plus ~10s); set min-instances ≥1 on user-facing paths only after costing it; consider keeping concurrency lower so fewer cold instances are needed per unit load. A widely cited benchmark put small-image cold starts near ~1.1s vs ~32ms warm; heavyweight frameworks run multiples of that.
**Follow-up trap:** *"Min-instances=10 everywhere, done?"* — you just added continuous cost for capacity that may sit idle; warm instances bill continuously (especially under always-on CPU). Warm only the baseline traffic level, not peak.

### Q3 — Your function's background cleanup thread stops running randomly. Explain.
**Testing:** the CPU allocation model, which most candidates don't know.
**Answer:** Default Cloud Run allocates CPU to an instance only while a request is in flight; once responses are sent, CPU is throttled and background threads effectively freeze or die mid-work. Fix: switch the service to always-allocated CPU (`--no-cpu-throttling`), which bills continuously while instances live — pair with min-instances deliberately because now idle time has real cost.
**Follow-up trap:** *"So why not always-on everywhere?"* — for pure request/response services it's strictly more expensive: default mode bills meaningfully only around actual work. Always-on is for work between requests, not a safety blanket.

### Q4 — Cloud Run vs Lambda: where does each genuinely win?
**Testing:** cross-cloud precision and honesty about tradeoffs.
**Answer:** Cloud Run packs up to 1000 concurrent requests per instance (default 80), so I/O-bound load runs on far fewer sandboxes — fewer cold starts, fewer connection pools, materially cheaper for bursty-but-concurrent HTTP. Lambda wins on per-invocation granularity for spiky event handlers, its ecosystem (event sources, tooling), and 15-minute cap fitting batch jobs; its concurrency-1 model means DB connection exhaustion at scale needs provisioned concurrency or a proxy. GCP's answer to long tasks is 60-minute HTTP timeouts plus jobs/Batch.
**Follow-up trap:** *"Cloud Run function vs Lambda cold starts?"* — same physics (image/runtime init), different mitigation surface: Cloud Run gives min-instances + startup CPU boost + concurrency packing so one warm instance absorbs bursts; Lambda historically needed provisioned concurrency for the same effect, which is pricier per unit of warmth.

### Q5 — Design an image-processing pipeline triggered by uploads to `gs://incoming`, processed within minutes, no polling.
**Testing:** Eventarc fluency including the filtering subtlety.
**Answer:** Eventarc trigger with audit-log source (`google.cloud.audit.log.v1.written`, serviceName=storage.googleapis.com, methodName=storage.objects.create) and a path pattern restricting to `/buckets/incoming/objects/*` → push to a Cloud Run service (or Cloud Run function) that resizes/stores output. Delivery is Pub/Sub-backed and at-least-once: dedup on CloudEvent id or object generation. If only direct events are used, note you can't prefix-filter `object.v1.finalized` — that constraint is exactly why audit-log triggers exist.
**Follow-up trap:** *"Trigger created fine but never fires."* — check the trigger SA has `run.invoker` on the target service (silent failure otherwise) and that trigger region matches the bucket's region for direct events / target region generally. Audit logs also need to be enabled for the source service.

### Q6 — What delivery guarantees does Eventarc give, and what must your handler do?
**Testing:** whether they know it rides Pub/Sub semantics.
**Answer:** At-least-once, ordered only if you deliberately route through ordering keys/queues (not by default); retries configurable with exponential backoff over hours (~) and dead-letter topics for poison messages. Handlers must be idempotent, return success quickly and process async if work is long (or hand off to jobs), because redelivery plus slow processing multiplies duplicates; monitor DLQ as a first-class signal.
**Follow-up trap:** *"Is it exactly-once if I enable everything?"* — no. Exactly-once is an application-level construction (idempotency keys/dedup store); Pub/Sub's exactly-once delivery feature exists in specific configurations but designing handlers as if duplicates will arrive is the robust posture.

### Q7 — When is Cloud Run the wrong choice even though "serverless" sounds right?
**Testing:** the senior judgment section of this module.
**Answer:** Flat sustained load (always-on pricing approaches or exceeds small committed-use clusters doing multiple workloads); >60-minute or very memory-hungry single requests (Batch/jobs/GKE instead); strict static egress IP without Direct VPC egress/NAT planning; deep GPU training; stateful protocols needing hard session pinning; org constraints requiring nodes inside a specific compliance boundary. Also latency-critical paths where any scale-from-zero risk is unacceptable and you'd pay min-instance costs equal to a VM anyway.
**Follow-up trap:** *"So GKE for anything serious?"* — no: the crossover is workload-shaped. Spiky consumer APIs stay dramatically cheaper on Cloud Run; steady internal platforms consolidate better on Autopilot. Compute monthly vCPU-seconds both ways from real traffic before deciding.

### Q8 — Explain revisions and how you'd run a canary with instant rollback.
**Testing:** whether they use the platform's release machinery or bolt on external tools.
**Answer:** Every deploy creates an immutable revision (image digest, env, scaling config). Traffic splitting is per-revision percentages on the service: send 5% to the new revision, watch error rate/latency per revision in monitoring, promote to 100% or roll back by pointing 100% at the previous revision tag — no rebuild, seconds. Revision URLs let you smoke-test new revisions privately before any split.
**Follow-up trap:** *"Config changed but traffic didn't shift — why?"* — scaling/env changes create a new revision only when applied via a deploy; some edits (like min-instances) apply within existing revision templates while others force new revisions. Also confirm you're not editing a different service than the one behind your domain map.

### Q9 — A Cloud Run service must call an internal API on a private VPC and reach the internet through a fixed IP. Design it.
**Testing:** networking integration knowledge that separates real deployments from demos.
**Answer:** Direct VPC egress on the service routes outbound traffic through a chosen VPC subnet — private IPs reachable, and pair with Cloud NAT on that subnet for the fixed external IP. Alternative legacy path: Serverless VPC Access connector (slower, billed, capacity-limited). Inbound stays locked with `ingress=internal-and-cloud-load-balancing` so the service is only reachable via internal LB/IAP or the global LB.
**Follow-up trap:** *"Why not just a connector?"* — connectors add a hop with throughput ceilings and their own billing; Direct VPC egress uses the subnet directly with higher throughput and simpler ops. Connectors remain for cases/regions without support (~).

### Q10 — What does "Cloud Functions" mean in 2026? Answer precisely.
**Testing:** currency check — naming drift trips people.
**Answer:** Since August 2024 there is one product family: **Cloud Run functions**. The former 2nd gen deploys as Cloud Run services (run.app URLs, concurrency to 1000, 60-min HTTP timeouts, 90+ Eventarc sources, CloudEvents). Former 1st gen is now "Cloud Run functions (1st gen)" — concurrency 1, 9-minute cap, cloudfunctions.net URLs, still supported but not for new work. Function packaging = buildpacks building a container from source; underneath it's all Cloud Run.
**Follow-up trap:** *"So my gen-1 functions are deprecated?"* — not deprecated, just frozen in capability; Google recommends migration. The honest plan is porting triggers to Eventarc and redeploying as gen2 services, which usually requires only signature/format adjustments to CloudEvents.

### Q11 — Your team set concurrency=1 "for safety." What did that actually do?
**Testing:** whether the concurrency knob's economics are understood.
**Answer:** It turned Cloud Run into Lambda-mode: every simultaneous request gets its own instance — instance count, cold-start surface, DB connection count all multiply by peak concurrency; cost scales linearly with rps instead of amortizing across slots. For I/O-bound services this buys nothing (the default 80 exists precisely because waits overlap); for CPU-bound handlers it may be right, but that's a measured decision, not a reflex.
**Follow-up trap:** *"How do you find the right number?"* — load-test: raise concurrency until p99 degrades or CPU saturates, back off ~20%. Watch container CPU utilization alongside latency; the breaking point differs by workload class.

### Q12 — Where do App Engine standard and Cloud Run actually differ today?
**Testing:** prevents stale-model answers.
**Answer:** Standard env runs sandboxed managed runtimes with scale-to-zero and its own idioms (app.yaml, dispatch rules, warmup requests); Cloud Run runs arbitrary containers with Knative-derived revisions, finer scaling control (per-request concurrency), WebSockets/gRPC, sidecars, jobs, and direct VPC egress. Feature-wise Cloud Run is a superset for new development; App Engine's remaining value is existing estates and bundled legacy services.
**Follow-up trap:** *"Is App Engine being killed?"* — no shutdown announced, but Google's investment clearly flows to Cloud Run (functions literally became Cloud Run). Betting new architecture on App Engine means inheriting a platform whose roadmap momentum lives elsewhere.

---

## Red flags that fail you

- Describing Cloud Run as "Google's Lambda" without mentioning per-instance concurrency — the models differ fundamentally.
- Not knowing default concurrency (~80) and its max (1000), or claiming instances scale on CPU usage rather than request concurrency.
- Proposing background work on default-throttled CPU.
- Saying "Cloud Functions" without knowing the August 2024 Cloud Run functions convergence.
- Treating Eventarc delivery as exactly-once.
- Reaching for Serverless VPC Access connectors by reflex when Direct VPC egress is the current answer.
- Recommending App Engine for greenfield work in 2026.

## Cheat card

```
CLOUD RUN (the substrate): request-driven containers, Knative-derived, GA 2019
  concurrency: default 80 (new deploys: 80 x vCPU), MAX 1000/instance
  instances ~= ceil(in_flight / concurrency); in_flight = rps x latency
  timeout: 300s default -> 3600s max (HTTP) | event-driven functions: 9 min
  size: up to 8 vCPU / 32 GiB (+GPU options for inference)
  scaling: min-instances (warmth $) / max-instances (downstream protection!)
           default max 100/revision; ceiling reached -> queue -> HTTP 429
  CPU: throttled-by-default (only during request!) vs --no-cpu-throttling
       startup CPU boost: ~2x vCPU at start + ~10s, on by default
  cold start ~1.1s small image (2020 bench) vs ~32ms warm
  pricing: ~$0.000024/vCPU-s + ~$0.0000025/GiB-s + $0.40/M req (2M free)

CLOUD RUN FUNCTIONS = ex Cloud Functions 2nd gen (renamed Aug 2024):
  buildpacks from source -> it IS a Cloud Run service (run.app URL)
  gen1 legacy: conc 1, 9-min cap, cloudfunctions.net

EVENTARC: trigger filters -> Pub/Sub (AT-LEAST-ONCE) -> OIDC push to target
  direct events (pubsub/gcs/firestore...) vs audit-log events (90+ sources)
  prefix filtering => audit-log + resourceName path patterns
  silent failure #1: trigger SA lacks run.invoker on target
  handler must dedup (CloudEvent id) + DLQ monitoring

APP ENGINE: standard=sandbox runtimes scale-to-zero; flexible=VMs never zero
  greenfield answer is Cloud Run; AE = estates only

RELEASES: revisions immutable; traffic split %; revision URLs for canary;
  rollback = point 100% at old revision tag. Direct VPC egress > connector.
```

## Sources

- [Cloud Functions is now Cloud Run functions — Google Cloud blog](https://cloud.google.com/blog/products/serverless/google-cloud-functions-is-now-cloud-run-functions); accessed 2026-08-23
- [Maximum concurrent requests per instance — Cloud Run docs](https://docs.cloud.google.com/run/docs/about-concurrency); accessed 2026-08-23
- [Cloud Run functions release notes — Google Cloud](https://docs.cloud.google.com/functions/docs/release-notes); accessed 2026-08-23
- [Google Cloud Platform performance and limits reference — CompareEdge](https://comparedge.com/tools/google-cloud/performance); accessed 2026-08-23
- [Fixing Cloud Run concurrency throttling and queue-timeout errors](https://github.com/OneUptime/blog/blob/master/posts/2026-02-17-how-to-fix-cloud-run-concurrent-request-throttling-and-request-queue-timeout-errors/README.md); accessed 2026-08-23
- [Configuring always-on CPU allocation for background workloads](https://oneuptime.com/blog/post/2026-02-17-how-to-configure-cloud-run-cpu-allocation-to-always-on-for-background-processing-workloads/view); accessed 2026-08-23
- [Cloud Run scaling behaviour: cold starts, min/max instances, concurrency](https://cloudwebschool.com/docs/gcp/compute/cloud-run-scaling-behaviour/); accessed 2026-08-23
- [Triggering Cloud Functions by Storage upload events with Eventarc](https://nakamasato.medium.com/cloud-functions-series1-trigger-cloud-functions-by-cloud-storage-upload-events-2nd-gen-e9f983619edc); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
