# Debugging From Traces & Logs Alone (When You Can't Attach)

> **Track:** T27 Tooling & Debugging · **Time:** 2.0h · **Prereqs:** T27-prod-debugging, T08-classic-obs · **Updated:** 2026-08-05
> **Module id:** `T27-observability-debug` · **Tags:** debugging, observability, tracing, sampling, profiling

## The 30-second version

The previous module assumed you could reach the process. This one assumes you cannot: the pod is gone, the request was two hours ago, the customer is on a single-tenant VPC you have no shell into, and all you have is a trace, a log line, and a metric. The method is fixed and runs in one direction: bound the problem with unsampled aggregate metrics first (which service, which route, which hosts, since when), then jump from the *bad bucket* of a latency histogram to a specific trace via a Prometheus exemplar rather than opening a random trace, then read the waterfall for the critical path and name the one span that owns the time, then join that span to logs and to a profile on `trace_id` and the span's exact time window. Everything in that chain is a design decision you made months earlier: head-based sampling at 1% throws away the trace you will need, `trace_id` in a Loki label instead of the log body kills your log store, and a metric with no exemplar leaves you scrolling traces by hand. The failure signatures are learnable and small in number: retries look like 3 sibling spans of identical duration pinned to a timeout, pool exhaustion looks like a gap between a span's start and its first child, a GC pause looks like every unrelated span on one pod lengthening by the same absolute amount at the same instant, and an N+1 across a service boundary looks like a staircase of 200 near-identical 8ms spans that no single service's profiler will ever show you.

## Why this gets asked

Because a Principal-level candidate who can only debug with a debugger is a candidate who cannot debug the systems this job actually has. The interviewer has lived the specific failure: a Sev-2 at 2am, a customer trace ID in hand, and the trace shows four spans because the tracer was only instrumented at the ingress; or worse, the trace ID returns nothing at all because head-based sampling at 1% discarded it, and the one thing everyone agrees on in the postmortem is "we need better observability" with no one able to say which specific knob would have made that request retrievable. They are probing three things: whether you read a waterfall for the *critical path* rather than for the widest bar, whether you know what sampling actually costs you and where the decision is made, and whether you treat "I'd add a log line and redeploy" as an acceptable answer (it is not, when the bug happens once a week and the deploy takes 40 minutes). At staff and principal level they will also push on the inverse question: not "how would you debug this" but "what would you have had to instrument six months ago for this to be debuggable at all."

---

## Lineage: past → present → future

**What came before.** Single-process debugging worked because one machine held the whole story: attach `gdb`, set a breakpoint, step. That model died with the service split, and the first replacement was grep. Teams shipped unstructured text logs to a central store (syslog, then Splunk from 2003, then the ELK stack from around 2012) and reconstructed a request's path by eyeballing timestamps across five services' log files, which fails for a reason that is arithmetic rather than aesthetic: with 200 requests per second in flight, timestamp proximity carries essentially zero information about which log lines belong to the same request, and clock skew between hosts of even 50ms makes ordering unreliable. Google's **Dapper** paper (2010) named the fix — propagate an identifier through every hop, model each unit of work as a span with a parent, and sample aggressively because the full firehose is unaffordable — and Dapper explicitly reported running at a uniform sampling probability as low as 1/1024 for high-throughput services, which is the origin of both distributed tracing and its oldest unsolved complaint. Twitter's Zipkin (2012) and Uber's Jaeger (2017) open-sourced the model; OpenTracing and OpenCensus split the API surface in two and then merged into **OpenTelemetry** in 2019 specifically to end that fragmentation. Meanwhile the metrics side went its own way: Prometheus (2012, from SoundCloud) made pull-based dimensional metrics standard, and by construction those metrics were aggregate and anonymous, which is exactly why the metric that tells you "p99 doubled" cannot tell you *which request*.

**Where it stands now.** The correlation problem is considered structurally solved and operationally half-done. Structurally: W3C Trace Context (`traceparent`, a W3C Recommendation) gives every signal one join key, OpenTelemetry's log data model injects `trace_id`/`span_id`/`trace_flags` into log records emitted inside an active span, and Prometheus **exemplars** attach a `trace_id` to a specific histogram bucket sample so you can jump from an aggregate to a concrete slow request without ever putting an unbounded value in a metric label. Grafana wires this into a click path (Tempo trace → Loki logs → Pyroscope profile), Datadog and Honeycomb ship the equivalent. Operationally it is half-done because the plumbing breaks in mundane, extremely common ways: context does not survive a thread-pool handoff or a background task, so half your log lines carry a null `trace_id`; exemplars require both `--enable-feature=exemplar-storage` on the Prometheus server and an OpenMetrics scrape format, so most deployments have the feature available and switched off. The live disagreements are two. First, **head versus tail sampling**: tail-based sampling in the Collector genuinely solves "keep every error and every slow trace," but it requires buffering every in-flight trace in Collector memory for `decision_wait` (default **30s**) and requires that every span of a trace reach the *same* Collector instance, which means a trace-ID-aware load-balancing layer that a large fraction of deployments do not have and do not know they need. The pragmatic consensus that has emerged is layered rather than either/or: a head-based pre-filter to cut volume, tail rules for errors and latency, and 100% on a small set of critical routes [How to Choose Between Head-Based and Tail-Based Sampling in OpenTelemetry](https://oneuptime.com/blog/post/2026-02-06-head-based-vs-tail-based-sampling-opentelemetry/view) — accessed 2026-08-05. Second, **where instrumentation comes from**: eBPF zero-code instrumentation (Grafana's Beyla, donated to OpenTelemetry and now shipping as OpenTelemetry eBPF Instrumentation, **v0.8.0 on 16 April 2026** with 1.0 GA planned for late 2026) gets you spans across a polyglot fleet with no code change, but it sees sockets and syscalls, not your business semantics, so the honest position — and the one Grafana itself argues — is that eBPF and SDK instrumentation are complementary, not substitutes [Introducing OpenTelemetry eBPF Instrumentation: Why we donated Grafana Beyla to OpenTelemetry — Grafana Labs](https://grafana.com/blog/opentelemetry-ebpf-instrumentation-beyla-donation/) — accessed 2026-08-05.

**Where it's heading.** High confidence: **profiles as a first-class, correlated signal**. OpenTelemetry's profiles signal entered public alpha in March 2026; OTLP Profiles round-trips losslessly with pprof and cuts wire size roughly 40% via a shared string dictionary, and Collector v0.148.0 added a pprof receiver — but the SIG explicitly advises against critical production workloads and production-ready backends have not landed, so 2026 is an evaluation window, not a migration window [OpenTelemetry Profiles Enters Public Alpha — OpenTelemetry](https://opentelemetry.io/blog/2026/profiles-alpha/) — accessed 2026-08-05. Moderate confidence: **span-scoped profiles become the default drill-down** — Grafana already links a span to the exact profile samples collected during it and embeds the flame graph inside the span detail pane, which closes the last gap in the trace→logs→profile chain, though it currently requires a per-language span-profiling bridge package and without that package traces and profiles remain unlinked signals [Traces to profiles — Grafana Pyroscope documentation](https://grafana.com/docs/pyroscope/latest/view-and-analyze-profile-data/traces-to-profiles/) — accessed 2026-08-05. Speculative, and worth flagging as such: LLM-driven root-cause narration over the three signals is a heavy vendor investment right now, and the metric that will decide whether anyone trusts it is false-positive rate under incident conditions, which no vendor currently publishes. Treat it as an investigation aid, not a diagnosis.

---

## Mental model

The whole discipline is one funnel, run in one direction, and every step must be answerable from data you already collected:

```
  UNSAMPLED AGGREGATE          "is it real, where, since when"
  ┌───────────────────────────────────────────────────────────┐
  │ METRIC  p99 by (service, route, pod)   ← 100% of requests │
  │         cheap, complete, anonymous — cannot name a request│
  └───────────────────────────┬───────────────────────────────┘
                              │  EXEMPLAR (trace_id attached to the
                              │  SLOW BUCKET — not a random trace)
                              ▼
  ┌───────────────────────────────────────────────────────────┐
  │ TRACE   waterfall → CRITICAL PATH → the span that OWNS it │
  │         sampled, incomplete — must have survived sampling │
  └──────────┬─────────────────────────────┬──────────────────┘
             │ trace_id + span time window │ span time window + host
             ▼                             ▼
  ┌────────────────────────┐   ┌──────────────────────────────┐
  │ LOGS  what the code    │   │ PROFILE  where CPU/alloc went│
  │ DECIDED and why        │   │ inside a self-time-heavy span│
  └────────────────────────┘   └──────────────────────────────┘

  Going the other direction (open a random trace, hope it's the bad one)
  is the single most common way engineers waste an hour in an incident.
```

And the four shapes you are reading the waterfall for. Almost every latency
bug is one of these:

```
 (1) ONE FAT SPAN                (2) STAIRCASE  (N+1 / chatty)
 parent ###################      parent ###################
   child ################          c1   ##
                                   c2     ##
 time is INSIDE that service       c3       ##
 → self time, go to profile        ...     (× 200)
                                 time is in ROUND TRIPS, not work
                                 → batch; no profiler will show this

 (3) GAP BEFORE FIRST CHILD      (4) UNIFORM SIBLINGS, LAST ONE ERRORS
 parent #########################   parent ####################
   (nothing)........child ###         a1  ######## (err, 2000ms)
                                      a2   ######## (err, 2000ms)
 dead time = pool acquire,            a3    ######## (2000ms)
 queue wait, GC, scheduling        durations PINNED to a timeout value
 → not your code, your capacity    → retry storm; parent ≈ n × timeout
```

---

## How it actually works

### 1. Reading a waterfall: critical path, self time, and the two numbers that matter

A waterfall renders every span as a bar. The instinct is to look for the widest bar. That instinct is wrong twice over.

**Wrong once: width is not ownership.** A span running in parallel with its siblings contributes nothing to total duration. The **critical path** is the chain you get by starting at the root and, at every level, descending into the child that *finishes last* — that chain, and only that chain, determines the request's total time. If you speed up a 900ms span that is not on the critical path, the request gets exactly 0ms faster. Interviewers ask about this specifically because the wrong answer looks confident.

**Wrong twice: total duration is not work done.** The number you actually want per span is **self time**: the span's duration minus the *wall-clock union* of its children's intervals (union, not sum, so parallel children count once). Self time answers "how much of this span's duration is unaccounted for by anything I instrumented," and it is the number that tells you whether to go to a profiler or to keep descending the trace.

```
self_time(span) = span.duration - union_of_child_intervals(span)
```

Three readings of self time, and each sends you somewhere different:

| Self time | Has children? | Read as | Next move |
|---|---|---|---|
| ~100% | no | Leaf work: DB query, HTTP call, compute | Is it the DB's time or the network's? Check `db.*` attributes and the peer's own span |
| >50% | yes | Uninstrumented in-process time: serialization, a regex, a sync block, a pool wait | Span → profile for that exact window on that pod |
| <10% | yes | Pure fan-out: this service is a router | Descend into the critical-path child; the problem is downstream |

**Where the gap sits matters.** Self time concentrated *before* the first child is a wait: a connection-pool acquire, a queue, a scheduler, a stop-the-world pause. Self time concentrated *after* the last child ends is response construction: serializing 40MB of JSON, computing a signature, an unbatched write on the way out. A waterfall renderer will not tell you which; the arithmetic will.

**Clock skew is real and you will see it.** Spans carry timestamps from the host that emitted them. With NTP drift of even 20-50ms between nodes, a child span can appear to start *before* its parent, or to end after it, and some UIs render this as a negative-duration bar or silently clamp it. Never draw a conclusion from a sub-100ms cross-host timing difference. Within one process, span timings are reliable; across processes, treat anything under ~100ms as noise.

### 2. The signature catalogue

These are the shapes. Learn them as shapes, not as descriptions, because in an incident you have 30 seconds to pattern-match a waterfall.

**Retry storm.** Two to four sibling spans, identical operation name, identical peer, durations *uniform to within a few percent* and clustered at a suspiciously round number (2000ms, 5000ms, 30000ms). The uniformity is the tell: real work has variable duration, a timeout does not. All but the last are errors. The gaps between them grow (exponential backoff) and are jittered. Parent duration ≈ n × timeout + Σ backoff. If you see this two layers deep — a retrying service calling a retrying service — you are looking at 9 attempts for one logical call, which is the classic mesh-plus-application-retry misconfiguration (see `T21-resilience-catalogue`).

**Connection-pool exhaustion.** A gap between the parent span's start and its first database child, where the query itself is 2-6ms and the gap is 200-900ms. The diagnostic asymmetry is the whole point: **the query duration stays flat while the wait time climbs**, which is how you distinguish it from a genuinely slow database (where the query duration itself grows). The confirming metric is pool state: `db.client.connection.count{state="used"}` at max, `state="idle"` at zero, and pending-requests non-zero. The strongest instrumentation move here is to stamp pool state as attributes on every DB span, so a single trace answers the question without a second query. And the terminal case: if a trace has a pool-wait gap followed by *no* DB span at all, the checkout timed out and the query never ran [How to Trace Database Connection Pool Exhaustion with OpenTelemetry Metrics](https://oneuptime.com/blog/post/2026-02-06-trace-database-connection-pool-exhaustion-opentelemetry-metrics/view) — accessed 2026-08-05.

**GC pause / stop-the-world.** The signature is not in any one trace, which is exactly why people miss it. It is: *every* span in flight on one pod lengthens by *the same absolute amount* at the same instant, regardless of what those spans were doing. A 4ms cache read becomes 204ms; a 300ms DB call becomes 500ms. The endpoint is different every time. There is no downstream span to blame and there never will be, because the JVM/CLR/Go runtime does not emit a span for its own pause. Correlate by `host`/`pod`, not by route: if you group p99 by pod and one pod is periodically spiking while its neighbours are flat, and the spike affects all routes equally, stop looking at the trace and look at `jvm.gc.duration` or `go_gc_pause_seconds` on that pod.

**Slow downstream masked by a cache.** p50 flat, p99 doubled. The downstream span appears in ~2% of traces because 98% of requests hit the cache and never make the call. This is the signature that head-based sampling destroys: at 1% head sampling, a span present in 2% of requests appears in 0.02% of your stored traces, and you will scroll for a very long time before you find one. The fix is not "sample more"; it is to make the *selection* outcome-aware — a tail-sampling latency policy, or an exemplar pulled from the top histogram bucket, which by construction points at a slow request.

**N+1 across a service boundary.** A staircase of 50-500 near-identical short spans, serial, each 5-20ms, all to the same peer. Within one service this is the classic ORM N+1 and a DB profiler catches it. Across a service boundary it is worse and nearly invisible to every single-service tool: each downstream call is genuinely fast (8ms, entirely reasonable), the downstream service's own p99 looks perfect, its CPU profile shows nothing, and the 1.6 seconds only exists in the *caller's* round-trip accounting. Distributed tracing is the only tool that shows it, which is the strongest one-sentence argument for tracing you can give an interviewer.

**Cache stampede / thundering herd.** Many *different* traces, each containing an identical expensive span, all starting within the same few milliseconds. Visible only in an aggregate trace view (Honeycomb heatmap, Tempo/TraceQL aggregate, or a span-metrics count grouped by operation) — never in a single trace. A TTL that expired for all keys simultaneously.

**Fan-out where the parent does not wait.** Child spans that end *after* their parent, or that appear detached. This is correct behaviour for a fire-and-forget publish and is modelled with span **links** rather than parent-child, but if you see it where you expected a synchronous call, someone dropped an `await` and the request is returning before its work completes.

### 3. Sampling: head vs tail, and precisely what each one costs you

**Head-based** decides at trace start, before anything interesting has happened, and propagates the decision in the `sampled` flag of the `traceparent` header so every downstream service makes the same call. The `traceparent` value is `00-<32 hex trace id>-<16 hex span id>-<2 hex flags>`. Head sampling is cheap, stateless, constant-memory, and needs no special infrastructure. What you lose is stated precisely: **you lose every rare event**. A failure mode affecting 1 in 10,000 requests, at 1% sampling, produces one stored trace per million requests. And it biases everything derived from traces: 1% of errors survive, so error traces are as rare in your store as they are in production, which is the opposite of what you want.

**Tail-based** runs in the Collector: it buffers all spans for a trace, waits `decision_wait` (**default 30s**), then evaluates policies against the complete trace. Policy types include `always_sample`, `status_code`, `latency`, `numeric_attribute`, `string_attribute`, `boolean_attribute`, `rate_limiting`, `probabilistic`, `span_count`, `and`, and `composite`; policies are evaluated in order and a trace needs to match only one. `num_traces` (traces held in memory) defaults to **50,000** [tailsamplingprocessor README — opentelemetry-collector-contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md) — accessed 2026-08-05.

What tail-based costs you, in order of how often it bites people:

1. **All spans of a trace must reach the same Collector instance.** If you run three Collector replicas behind a round-robin service, each replica sees a fraction of each trace and makes its decision on a partial trace. The symptom is maddening: traces that exist but are missing their most interesting spans, inconsistently. The fix is a trace-ID-aware routing layer (the `loadbalancingexporter` with `routing_key: traceID`) in a two-tier Collector deployment. This is the number-one tail-sampling deployment error and a very common interview follow-up.
2. **Memory scales with in-flight traces × spans per trace × decision_wait.** 10,000 traces/sec × 30s × 20 spans is 6M spans resident. Sizing this is real capacity work, not a config toggle.
3. **Traces longer than `decision_wait` are truncated or split.** A 90-second batch job or a multi-minute agent run exceeds a 30s window; late spans arrive after the decision and are handled separately or dropped. Long-running work needs a longer window (with the memory cost that implies) or a different strategy entirely.
4. **Aggregates computed from sampled traces are wrong unless you carry the adjusted count.** If you sampled at probability *p* and count stored spans without multiplying by 1/*p*, your rate is off by 100×. This is why span-derived RED metrics should be generated *before* the sampler in the pipeline (spanmetrics connector upstream of the tail sampler), not after. The OTel spanmetrics *processor* is deprecated in favour of the spanmetrics *connector*; Tempo's metrics-generator does the equivalent server-side [Use the span metrics processor — Grafana Tempo](https://grafana.com/docs/tempo/latest/metrics-from-traces/span-metrics/span-metrics-metrics-generator/) — accessed 2026-08-05.

**Vendor-side, the same idea appears with different names and this trips people up.** In Datadog, *ingestion controls* govern what the Agent sends to Datadog at all, while *retention filters* govern which spans get indexed and searchable for 15 days, with an Intelligent Retention Filter auto-indexing a representative selection. They are two independent knobs, and "we set sampling to 100% but still can't find the trace" almost always means ingestion was fine and retention dropped it [Trace Retention — Datadog docs](https://docs.datadoghq.com/tracing/trace_pipeline/trace_retention/) — accessed 2026-08-05.

**The layered configuration most mature teams actually run:** head-based probabilistic pre-filter to cut raw volume, then tail policies keeping 100% of `status_code = ERROR`, 100% over a latency threshold, 100% of a named critical route, and a small probabilistic slice of everything else so you retain a baseline to compare against. That last clause matters more than it sounds: if you keep only errors and slow requests, you have no healthy trace to diff against, and "what does a normal one look like" becomes unanswerable at exactly the wrong moment.

### 4. Log cardinality and structured logging

The rule is one sentence: **high-cardinality values go in the log body or structured attributes, never in the index labels.**

Loki indexes *label sets*; each unique combination of labels is a stream, and streams are the unit of cost. Putting `trace_id` in a label creates one stream per request, each producing a tiny short-lived chunk flushed to object storage, and the index grows without bound. Loki's defaults are explicitly built to stop you: a limit of **15 index labels**, max label name length **1024**, max label value length **2048**, and per-tenant stream limits of **10,000** (per-ingester) and **50,000** (global). Grafana's own guidance is blunt: keep labels to tens of values, prefer long-lived values, and put ephemeral values like a trace ID or an order ID in the line content, then use filter expressions to brute-force them — which is fast, because Loki is designed for exactly that [Cardinality — Grafana Loki documentation](https://grafana.com/docs/loki/latest/get-started/labels/cardinality/) and [Label best practices — Grafana Loki](https://grafana.com/docs/loki/latest/get-started/labels/bp-labels/) — both accessed 2026-08-05.

So the query you actually run in an incident is:

```logql
{service="checkout", env="prod"} | json | trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
```

Three low-cardinality labels for stream selection, then a structured filter on the high-cardinality join key. This works and is cheap. `{trace_id="..."}` would be catastrophic.

**What "structured" buys you beyond aesthetics.** A log line is a `print` you cannot delete and cannot change without a deploy, so it has to be queryable by dimension you did not think of in advance. That means: one JSON object per event, stable key names across services, severity with consistent semantics, and `trace_id`/`span_id` injected automatically from the active context rather than passed by hand. OpenTelemetry's log data model makes those trace identifiers part of the record, which is what turns a log store into a drill-down target rather than a separate universe.

**The log-correlation failure you will actually hit** is null `trace_id` on a fraction of lines, and it is almost never a logging-config problem. It is context loss: the log was emitted from a thread-pool worker, an `asyncio` task created without copying context, a callback, a `@Async` Spring method, or a background consumer — anywhere the active span context did not propagate across the boundary. The observable symptom is that correlation works perfectly for the synchronous request path and fails for exactly the code that runs after a handoff, which is also where the interesting bugs live.

**What to log so the logs are usable without a debugger.** Log the *decision and its inputs*, not the data. `chose_route=fallback reason=primary_breaker_open primary_p99_ms=812 tenant=acme` reconstructs a decision six weeks later; `INFO: processing request` reconstructs nothing and costs the same per byte. Every error log must carry the `trace_id` and the identifiers needed to reproduce the state, because the process that could have told you is gone.

### 5. Correlating trace id → log → metric, and why exemplars exist

`T08-classic-obs` covers why an unbounded label destroys Prometheus. The consequence here is specific: since you cannot put `trace_id` in a metric label, an aggregate metric is structurally incapable of naming a request. **Exemplars** are the escape hatch — an out-of-band pointer attached to an individual sample, carrying `trace_id` and `span_id`, that does not multiply time series at all.

The mechanics you need to state correctly:

- The OTel SDK's exemplar filter (`TraceBased`) attaches trace context to any measurement recorded while a span is active. Measurements outside a span get no exemplar.
- Exemplars ride the **OpenMetrics** exposition format, not the older Prometheus text format. If your scrape config uses the classic format, exemplars are silently dropped.
- The Prometheus server needs `--enable-feature=exemplar-storage`. It is off by default.
- An exemplar is stored per bucket. That is the entire trick: the exemplar attached to the *top* latency bucket is, by construction, a slow request. You click it and land in a trace that is guaranteed interesting, instead of opening a random trace and finding a healthy one.

[Prometheus Metric Exemplars with OpenTelemetry Tracing — Google Cloud OpenTelemetry docs](https://google-cloud-opentelemetry.readthedocs.io/en/latest/examples/prometheus_exemplars/README.html) — accessed 2026-08-05.

The other two hops:

- **Trace → logs.** Grafana's Tempo data source has an explicit trace-to-logs configuration that builds a Loki query from the span's `trace_id` and time range. Both sides must be configured; `trace_id` has to actually reach Loki from the app through the Collector, which is the same context-propagation problem as above [Configure trace to logs correlation — Grafana](https://grafana.com/docs/grafana/latest/datasources/tempo/configure-tempo-data-source/configure-trace-to-logs/) — accessed 2026-08-05.
- **Trace → profile.** Pyroscope's traces-to-profiles integration opens a flame graph scoped to the span's time range and service, and embeds it in the span detail pane. It requires a per-language span-profiling bridge package; without it, traces and profiles are unlinked signals.

One operational note that dates fast: Promtail was marked end-of-life on **2 March 2026**; new Loki deployments should use Grafana Alloy.

### 6. Diagnosing from p99 alone

Often the metric is all you get, and there are four things to know cold.

**You cannot average percentiles.** `avg(p99)` across 20 pods is not the fleet p99 and has no statistical meaning. If one pod is melting and nineteen are fine, the average of the twenty p99 values hides it entirely. The correct operation is to sum the histogram buckets and compute the quantile from the summed histogram: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`. This is one of the most reliable ways to catch a candidate who has used Grafana without understanding it.

**Your p99 is only as precise as your buckets.** The Prometheus Go client's default buckets are `.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10` seconds. Everything above 10s lands in `+Inf`, and `histogram_quantile` interpolates within a bucket, so a p99 that reads *exactly* 10s usually means "at least 10s, we cannot tell you more." Likewise a p99 of 5.2s on default buckets is an interpolation between the 5s and 10s boundaries, not a measurement. Native histograms (`T08-classic-obs`) fix this with dynamic exponential resolution.

**The shape of the divergence names the cause.** This is the highest-value table in the module:

| p50 | p99 | p99.9 | Most likely cause |
|---|---|---|---|
| flat | up | up | A minority path got slower: cache miss, cold shard, one bad host, GC, a slow tenant |
| up | up proportionally | up | Everything got slower: capacity, a shared dependency, a hot-path code change |
| flat | up | flat | A *bounded* set of slow requests: one tenant, one shard, one region. Group by those dimensions |
| flat | flat | up | Rare pathological input, or a periodic job stealing resources |
| up | flat | flat | Almost always a measurement change, not a system change: new instrumentation, a routing change, or a shift in traffic mix |

**Percentiles describe samples, not users.** A user whose page load fires 100 backend requests has a `1 - 0.99^100 = 63.4%` chance of hitting at least one p99-latency request. At 10 requests it is 9.6%. "Only 1% of requests are slow" is therefore a much weaker statement than it sounds, and saying this number out loud is a strong senior signal.

**And your p99 may be a lie by construction.** Gil Tene's *coordinated omission*: a closed-loop load generator that waits for each response before issuing the next one stops issuing requests exactly when the server stalls, so the stall never gets measured. The published gap is large — one reported case had a load test showing p99 = 47ms against a production p99 of 1.8s for the same release, a 38× miss. The fix is a constant-arrival-rate (open-loop) workload model that records the intended send time, not the actual one [Coordinated Omission: Why Your Latency Numbers Lie — idle-ti.me](https://idle-ti.me/blog/coordinated-omission/) — accessed 2026-08-05. The production analogue: a server-side histogram measures from "request accepted by the handler," which excludes time spent queued in the load balancer or in the kernel accept queue. Flat server-side p99 plus real user complaints means you are measuring in the wrong place.

### 7. Reading a flame graph you did not capture

Continuous profiling (covered mechanically in `T27-prod-debugging`) means the profile for last Tuesday 03:47 already exists. Reading it is a separate skill.

- **Width = samples = time. The x-axis is not time.** Frames are merged and sorted alphabetically so that identical stacks combine. You cannot read chronology off a flame graph, only proportion.
- **Look for plateaus, not for depth.** A wide, flat frame near the top is where the CPU actually is. A deep narrow tower is recursion or a framework's call chain and usually costs nothing.
- **The differential flame graph is the incident tool.** Baseline window versus incident window, coloured by delta. A single flame graph tells you where time goes; a diff tells you what *changed*, which is the actual question during a regression.
- **The trap: a CPU flame graph cannot see off-CPU time.** A thread blocked on a socket, a lock, or a pool acquire consumes zero CPU samples and is invisible. So "the flame graph looks completely normal" is not evidence of health when the service is 95% waiting — it is the *expected* result. You need wall-clock/off-CPU profiling (`py-spy --idle`, async-profiler's wall mode, off-CPU eBPF profiling) to see waits. Candidates who do not know this stare at a flat profile for twenty minutes.
- **Span profiles narrow the window for you.** Instead of profiling a service for 30 seconds and hoping the slow request is in there, a span profile is scoped to one span's time range and service, so the flame graph you get is the flame graph *of that request*.

---

## Build it from scratch

The one tool worth writing yourself: a trace reader that computes the critical path and self time and pattern-matches the signatures. Writing it is how the arithmetic stops being abstract, and it is a plausible 30-minute pairing exercise.

```python
"""waterfall.py — read a trace, find who actually owns the latency.
Spans: {"id", "parent", "name", "start" (ms), "dur" (ms), "peer", "error"}."""
import json, sys
from collections import defaultdict

def union_len(intervals):
    """Wall-clock covered by a set of [start,end) intervals. Parallel work counts ONCE.
    Using sum() here instead of a union is the classic bug: it makes a fan-out
    of 10 parallel 100ms calls look like 1000ms of latency it never cost."""
    if not intervals:
        return 0.0
    iv = sorted(intervals)
    total, cs, ce = 0.0, iv[0][0], iv[0][1]
    for s, e in iv[1:]:
        if s > ce:
            total += ce - cs
            cs, ce = s, e
        else:
            ce = max(ce, e)
    return total + (ce - cs)

def index(spans):
    by_id = {s["id"]: s for s in spans}
    kids, roots = defaultdict(list), []
    for s in spans:
        (kids[s.get("parent")].append(s) if s.get("parent") in by_id else roots.append(s))
    for v in kids.values():
        v.sort(key=lambda c: c["start"])
    return by_id, kids, roots

def self_time(s, kids):
    iv = [(c["start"], c["start"] + c["dur"]) for c in kids[s["id"]]]
    return s["dur"] - union_len(iv)

def critical_path(root, kids):
    """At each level descend into the child that FINISHES LAST. That chain, and
    only that chain, determines total duration."""
    path, cur = [root], root
    while kids[cur["id"]]:
        cur = max(kids[cur["id"]], key=lambda c: c["start"] + c["dur"])
        path.append(cur)
    return path

def findings(spans, kids):
    out = []
    for s in spans:
        ch = kids[s["id"]]
        if ch:                                    # dead time before any child started
            gap = ch[0]["start"] - s["start"]
            if gap > 50 and gap > 0.20 * s["dur"]:
                out.append(f"GAP      {gap:7.0f}ms dead time inside '{s['name']}' before its first "
                           f"child ({gap/s['dur']*100:.0f}%). Pool acquire / queue / GC / scheduling.")
        groups = defaultdict(list)
        for c in ch:
            groups[(c["name"], c.get("peer", ""))].append(c)
        for (name, peer), g in groups.items():
            if len(g) < 2:
                continue
            span_sum = sum(c["dur"] for c in g)
            serial = union_len([(c["start"], c["start"]+c["dur"]) for c in g]) > 0.85 * span_sum
            durs = [c["dur"] for c in g]
            uniform = (max(durs) - min(durs)) <= 0.15 * max(durs)   # pinned to a timeout
            errs = sum(1 for c in g if c.get("error"))
            if uniform and errs >= len(g) - 1 and len(g) <= 6:
                out.append(f"RETRY    {len(g)}x '{name}' -> {peer}, durations {durs}ms (uniform = "
                           f"pinned to a timeout), {errs} errored. {span_sum:.0f}ms of the parent.")
            elif len(g) >= 5 and serial:
                out.append(f"N+1      {len(g)}x serial '{name}' -> {peer}, {span_sum:.0f}ms total "
                           f"({span_sum/len(g):.0f}ms each). Batch it: one round trip, not {len(g)}.")
        st = self_time(s, kids)
        if s["dur"] >= 100 and ch and st > 0.5 * s["dur"]:
            out.append(f"SELFTIME {st:7.0f}ms unaccounted inside '{s['name']}' "
                       f"({st/s['dur']*100:.0f}%). Not in any child: go to the profile.")
    return out
```

Run against a synthetic trace containing all three defects (a pool-wait gap, an N+1
staircase across a service boundary, and a 3-attempt retry storm), the output is:

```
trace_id=4bf92f3577b34da6a3ce929d0e0e4736  total=4200ms

* GET /checkout                  0+4200   self=  140 |#####################################...
    orders.reserve              10+1000   self=  986 |#########
      SELECT items             820+6      self=    6 |        #
      UPDATE stock             830+8      self=    8 |        #
    GET /price                1050+80     self=   80 |          ##
    GET /price                1135+80     self=   80 |            ##
    ... 9 identical rows elided ...
    GET /price                1985+80     self=   80 |                        ##
    POST /charge              2100+700    self=  700 |                          ########
    POST /charge              2830+700    self=  700 |                                 ########
*   POST /charge              3560+700    self=  700 |                                        ########

(* = critical path: the chain that owns total duration)

N+1      12x serial 'GET /price' -> pricing, 960ms total (80ms each). Batch it: one round trip, not 12.
RETRY    3x 'POST /charge' -> payments, durations [700, 700, 700]ms (uniform = pinned to a timeout), 2 errored. 2100ms of the parent.
GAP          810ms dead time inside 'orders.reserve' before its first child (81%). Pool acquire / queue / GC / scheduling.
SELFTIME     986ms unaccounted inside 'orders.reserve' (99%). Not in any child: go to the profile.
```

Note what the critical path marker says: only the *last* retry attempt is on it, because the first two finished earlier. And note the honest limit of the tool — it flags `orders.reserve` twice, as both GAP and SELFTIME, because they are the same 810ms seen two ways. Real detectors need to dedupe. Full version with OTLP JSON ingestion, span links, and clock-skew guards: **`(lab pending)`**.

---

## How it's done in production

The stacks, briefly. **Grafana OSS**: Tempo for traces (2.9's support window runs to 31 December 2026, with 2.10/3.0 the recommended upgrades), Loki for logs, Mimir/Prometheus for metrics, Pyroscope for profiles, Alloy as the collector (Promtail EOL 2 March 2026), and the whole value proposition is the pre-wired click path between them. **Datadog**: one agent, one UI, ingestion controls separate from retention filters, tail sampling delegated to an OTel Collector if you need policies richer than the built-ins. **Honeycomb**: the outlier here, built around high-cardinality wide events and BubbleUp, which diffs the attribute distribution of slow requests against fast ones and tells you *which attribute value* correlates with the outliers. That is a genuinely different debugging motion — you do not read one trace, you ask which dimension explains the tail — and it is worth naming in an interview because it shows you know the trace-waterfall model is not the only one.

### Symptom → cause → fix

| Symptom | Cause | Fix |
|---|---|---|
| Trace exists but has 4 spans and stops at the ingress | Context not propagated past the first hop, or downstream services uninstrumented | Verify `traceparent` is forwarded by the HTTP client (not just the server); add SDK or eBPF instrumentation downstream |
| Customer gives you a trace ID and the backend returns nothing | Head-based sampling dropped it, or Datadog-style retention (not ingestion) discarded it | Tail sampling with `status_code`/`latency` policies; 100% on critical routes; check retention filters separately from ingestion |
| Traces are present but inconsistently missing their most interesting spans | Tail sampling behind a round-robin Collector service: each replica decides on a partial trace | Two-tier Collector with `loadbalancingexporter`, `routing_key: traceID`, so all spans of a trace land on one instance |
| 3-4 sibling spans, same peer, durations identical to within 2%, all but the last errored | Retry storm; durations pinned to the client timeout | Retry budget, circuit breaker, disable retries at one of the two layers (`T21-resilience-catalogue`) |
| Gap of 200-900ms before the first DB span; the query itself is 4ms | Connection-pool exhaustion. Wait time climbs, query duration stays flat | Stamp pool state on DB spans; size by Little's Law; find the queries holding connections too long |
| Gap before first DB span, then no DB span at all | Pool checkout timed out; the query never ran | Same as above, plus check checkout-timeout config and leak detection |
| Every span on one pod lengthens by the same absolute amount, all routes equally | Stop-the-world GC pause. No span exists for it and none ever will | Group p99 by pod, not by route; confirm against `jvm.gc.duration` / `go_gc_pause_seconds`; heap tuning |
| p99 doubled, p50 flat, and the slow downstream call appears in 2% of traces | Cache hit rate masking a degraded dependency | Exemplar from the top histogram bucket, or a tail latency policy — outcome-aware selection, not more sampling |
| Staircase of 200 serial 8ms spans to the same peer; downstream service's own p99 is perfect | N+1 across a service boundary. No single-service profiler can see it | Batch endpoint, or DataLoader-style coalescing at the caller |
| Half the log lines have a null `trace_id` | Context lost at a thread-pool, async-task, callback, or background-consumer boundary | Propagate context explicitly across the handoff (`contextvars` copy, `Context.current()` capture, instrumented executor) |
| Loki ingestion failing, index enormous, tiny chunks flushing constantly | An ephemeral value (`trace_id`, `order_id`, `user_id`) used as an index label | Move it into the log body / structured metadata; query with `| json | trace_id="..."`; keep to a handful of low-cardinality labels |
| Metric-to-trace jump is missing in Grafana | Exemplars not enabled: needs `--enable-feature=exemplar-storage` **and** OpenMetrics scrape format **and** an SDK exemplar filter | Enable all three; verify the metric is recorded inside an active span |
| Fleet p99 on the dashboard looks fine while users complain | `avg(p99)` across pods, or the histogram is measured after the queue | `histogram_quantile(0.99, sum(rate(..._bucket[5m])) by (le))`; add an edge/LB-side measurement |
| p99 reads exactly 10.0s and never moves | Everything above the top default bucket is in `+Inf`; the quantile is clamped | Add buckets above your SLO, or move to native histograms |
| Continuous profile for the incident window shows nothing unusual | CPU flame graph cannot see off-CPU time; the service was waiting, not computing | Wall-clock/off-CPU profiling (`py-spy --idle`, async-profiler wall mode) |
| Child span appears to start before its parent | Clock skew between hosts (NTP drift) | Ignore sub-100ms cross-host timing; trust in-process timings only |

---

## Tradeoffs & when NOT to use it

- **Do not reach for a trace when a metric answers the question.** "Is this happening, where, and since when" is an aggregate question, and traces are sampled and therefore a biased sample. Starting in the trace UI means you are inspecting an anecdote before you have established the phenomenon. Metric first, always.
- **Do not deploy tail-based sampling without solving trace-ID-aware routing first.** Tail sampling behind a plain round-robin Collector service is worse than head sampling, because head sampling gives you complete traces of a subset while broken tail sampling gives you incomplete traces of the subset you care about, and the incompleteness is silent.
- **Do not treat 100% sampling as the safe default at scale.** At 10k requests/sec × 20 spans × ~500 bytes that is ~100 MB/s of span data before compression. The cost is real and it buys you very little over well-chosen tail policies, because you will never look at 99.99% of it. The exception is genuinely low-volume, high-value traffic (a payments path at 20 rps), where 100% is cheap and correct.
- **Do not instrument for the sake of coverage.** A span per function call produces traces with 4,000 spans that no human can read and that blow past `num_traces` memory budgets. Span at boundaries — network calls, queue operations, DB queries, and the handful of in-process operations you have actually been burned by — and let a profiler cover the inside of a service.
- **Do not use a CPU flame graph to diagnose a hang.** It is structurally blind to blocked threads. This is the observability-side restatement of `T27-prod-debugging`'s rule about matching the tool to the symptom, and it is the single most common wasted twenty minutes in profiling.
- **eBPF auto-instrumentation is not a substitute for SDK instrumentation.** OBI/Beyla will give you spans across a polyglot fleet with zero code change, which is excellent for coverage of services nobody will re-deploy. It will not give you `tenant_id`, `model_version`, `cache_hit`, or any other attribute that encodes what your system actually does — and those attributes are what makes the difference between "a span was slow" and "requests for tenant X on shard 3 are slow."
- **If you can reproduce it locally, do that instead.** This entire module is a set of techniques for the case where you cannot. A `pdb` breakpoint on a local repro is faster and more certain than the best trace, and a candidate who reaches for distributed tracing on a deterministically reproducible bug is signalling the wrong instinct.

---

## Interview questions

### Q1 — You're given a trace waterfall for a 4.2s request. Walk me through how you find the culprit.
**Testing:** whether you read for the critical path or for the biggest bar.
**Answer:** Start at the root and descend into whichever child *finishes last* at each level; that chain is the critical path and it is the only thing that determines total duration. Then for each span on that chain compute self time — duration minus the wall-clock union of its children. High self time with no children is leaf work. High self time *with* children means uninstrumented in-process time and I go to a profile for that window. Low self time means the service is a router and I keep descending. Where the self time sits matters too: before the first child it is a wait (pool acquire, queue, GC); after the last child it is response construction.
**Follow-up trap:** *"There's a 900ms span. Do you optimise it?"* — not until I know it is on the critical path. If it ran in parallel with a 1.4s sibling, making it instant saves exactly 0ms. The widest bar and the responsible bar are different bars, and confusing them is how teams optimise something and ship no improvement.

### Q2 — Head-based vs tail-based sampling. What do you lose with each?
**Testing:** whether you know where the decision is made and what it costs.
**Answer:** Head-based decides at trace start and propagates the flag in `traceparent`, so every service agrees. It is stateless, constant-memory, needs no infrastructure — and it decides before anything interesting has happened, so you lose rare events. At 1% sampling, a failure affecting 1 in 10,000 requests yields one stored trace per million. Tail-based buffers the whole trace in the Collector, waits `decision_wait` (default 30s), then applies policies against the completed trace, so you can keep 100% of errors and 100% of slow traces. The costs are memory proportional to in-flight traces × spans × window, traces longer than the window being truncated, and the requirement that every span of a trace reach the same Collector instance.
**Follow-up trap:** *"So just use tail sampling everywhere?"* — not before you have trace-ID-aware routing. With three Collector replicas behind round-robin, each replica decides on a partial trace, and the symptom is traces that exist but are silently missing spans. You need a two-tier Collector with `loadbalancingexporter` and `routing_key: traceID`. Most teams that "turned on tail sampling" and got worse data hit exactly this.

### Q3 — A customer gives you a trace ID. The backend returns nothing. What are the possibilities, in order?
**Testing:** whether you understand the pipeline has multiple independent drop points.
**Answer:** In order of likelihood: the trace was never sampled (head-based decision at the root said no); it was sampled and ingested but not *retained* — in Datadog, ingestion controls and retention filters are separate knobs, and spans are indexed for 15 days only if a retention filter matched; the trace fell outside the retention window entirely; or the ID came from a system that mints its own correlation ID and is not a W3C trace ID at all. Only after those do I suspect a real pipeline failure.
**Follow-up trap:** *"We set sampling to 100%. So it must be a bug, right?"* — no, that is the classic confusion. 100% ingestion with a restrictive retention filter still leaves you with nothing searchable. Ingestion controls what the agent sends; retention controls what gets indexed. Two knobs, two configs, and people routinely check one.

### Q4 — Why can't you just put the trace ID in a Prometheus label so you can jump from a metric to a trace?
**Testing:** cardinality, and knowledge of the actual solution.
**Answer:** Every unique metric-name-plus-label-set is one time series, so a per-request label creates unbounded series and kills the server. The purpose-built answer is exemplars: an out-of-band `trace_id`/`span_id` attached to an individual sample, stored per histogram bucket, contributing zero additional series. The elegance is that the exemplar on the *top* latency bucket is by construction a slow request, so you land in an interesting trace rather than a random one.
**Follow-up trap:** *"You enabled exemplars in the SDK and Grafana still shows no jump link."* — three independent things must all be true: the SDK's exemplar filter must be `TraceBased` and the measurement must be recorded inside an active span; the scrape must use OpenMetrics format, since the classic Prometheus text format cannot carry exemplars; and the Prometheus server must run with `--enable-feature=exemplar-storage`, which is off by default. Missing any one produces exactly this symptom.

### Q5 — Half your log lines have a null trace_id. Diagnose.
**Testing:** whether you know this is a context-propagation bug, not a logging-config bug.
**Answer:** Almost always context loss at a concurrency boundary: a thread-pool handoff, an `asyncio` task created without copying the current context, a callback, a Spring `@Async` method, a background consumer pulling off a queue. The diagnostic signature is that correlation works perfectly on the synchronous request path and fails for exactly the code that runs after a handoff. Fix by propagating context explicitly across the boundary — copy `contextvars`, capture `Context.current()` before the submit, or use an instrumented executor wrapper.
**Follow-up trap:** *"Which half of your logs is it, and why does that make it worse?"* — it is the async half: retries, background writes, queue consumers, cleanup. That is disproportionately where the hard bugs live, so the correlation gap is concentrated in exactly the code you most need it for. It also biases your mental model — the parts of the system that look well-correlated look that way because they are the simple parts.

### Q6 — p99 doubled, p50 is flat. Give me three ranked hypotheses and the cheapest check for each.
**Testing:** hypothesis-first debugging on aggregate data.
**Answer:** (1) One bad host or pod — cheapest check is to group p99 by pod; if one pod diverges and all its routes are equally affected, it is host-local (GC, a noisy neighbour, a degraded disk). (2) A minority code path got slower — check whether the divergence is concentrated in one route, one tenant, or one shard by grouping on those dimensions; a cache hit-rate drop is the classic instance, since the 2% of requests that miss now pay a degraded downstream. (3) A resource with a queue — check saturation and queue depth; a pool or a scheduler produces exactly this shape, because most requests find capacity and a minority wait. In all three cases the confirming artifact is an exemplar trace from the top histogram bucket, not a random trace.
**Follow-up trap:** *"p99 is up but p99.9 is flat. Does that change anything?"* — yes, substantially. It means the slow set is *bounded* rather than a heavy tail, which points at a specific finite population: one tenant, one shard, one region, one pod. A genuine capacity or dependency problem drags p99.9 up too. This is one of the highest-information single observations available from metrics alone.

### Q7 — Describe what a retry storm looks like in a waterfall, precisely.
**Testing:** signature recognition with actual detail.
**Answer:** Two to four sibling spans with identical operation name and identical peer, durations uniform to within a few percent and pinned at a round number like 2000ms or 5000ms, all but the last carrying an error status, with growing and jittered gaps between them. The uniformity is the diagnostic: real work varies in duration, a timeout does not. Parent duration is approximately n × timeout plus the backoff sum.
**Follow-up trap:** *"You see three attempts at one layer, and the downstream trace also shows three attempts. What's the real amplification?"* — nine attempts for one logical call, and it is the single most common service-mesh misconfiguration: the mesh retries and the application retries and nobody disabled one. Pick one layer to retry at and explicitly turn it off at the other.

### Q8 — A waterfall shows 200 serial 8ms spans to the same downstream service. That service's own p99 looks perfect. What's going on?
**Testing:** N+1 across a service boundary, and why it is invisible to everything except tracing.
**Answer:** N+1 at the service boundary. Each individual call is genuinely fast and the downstream service is genuinely healthy — 8ms is a fine number. The 1.6 seconds exists only in the caller's round-trip accounting, and no downstream metric, log, or CPU profile will ever show it, because from the downstream's perspective nothing is wrong. Fix is a batch endpoint or DataLoader-style coalescing at the caller.
**Follow-up trap:** *"The downstream team says their SLO is green, so it's not their problem. Respond."* — they are correct and it is still a shared problem. Their per-call SLO is a fine SLI for their service and a bad proxy for user experience, and this is precisely the case for tracing over per-service metrics: the latency is an emergent property of the interaction, owned by neither service's dashboard. The fix (a batch endpoint) is downstream work justified by upstream data.

### Q9 — How do you tell connection-pool exhaustion from a slow database, using trace data alone?
**Testing:** the diagnostic asymmetry.
**Answer:** A slow database means the query span's own duration grows. Pool exhaustion means the query duration stays flat at its usual 4ms while a *gap* opens between the parent span's start and the first query span — the checkout wait. So: query duration flat plus growing pre-query gap equals pool exhaustion; query duration growing equals the database. The confirming metric is pool state, used at max and idle at zero with non-zero pending requests. The instrumentation that makes this a one-trace answer instead of a two-query investigation is stamping pool state as attributes on every DB span.
**Follow-up trap:** *"The trace has the gap and then no DB span at all. What happened?"* — the checkout timed out before a connection was ever acquired, so the query never ran. That distinguishes "saturated but coping" from "saturated and shedding," and it also means any error log downstream of that point is a symptom, not a cause.

### Q10 — There's no span for a GC pause. How do you see one in your telemetry?
**Testing:** whether you can diagnose something that emits no span at all.
**Answer:** By its correlation structure rather than by any single span. Every span in flight on that pod lengthens by the same *absolute* amount at the same instant, regardless of what it was doing — a 4ms cache read becomes 204ms alongside a 300ms DB call becoming 500ms. The affected endpoint differs every time and there is never a downstream span to blame. So you group latency by pod rather than by route: if one pod spikes periodically and the spike hits all routes equally, stop reading traces and check `jvm.gc.duration` or `go_gc_pause_seconds` on that pod.
**Follow-up trap:** *"Your continuous CPU profile for that window looks completely normal. Does that rule out GC?"* — no. A CPU flame graph of application code will not show a stop-the-world pause as application work, and it is structurally blind to off-CPU time in general. You want GC-specific runtime metrics or allocation profiling, not a CPU profile. "The flame graph looked fine" is not evidence about anything the process was waiting on.

### Q11 — A downstream dependency degraded, but a 98% cache hit rate hides it. Why does 1% head sampling miss it, and what do you change?
**Testing:** the interaction of sampling with rare-but-important paths.
**Answer:** The span only exists in the 2% of requests that miss cache. At 1% head sampling it appears in 0.02% of stored traces, so finding one by browsing is hopeless. The fix is not more sampling, it is outcome-aware selection: a tail-sampling latency policy that keeps 100% of traces above a duration threshold, or an exemplar pulled from the top histogram bucket, which by construction points at a slow request. Either way you stop sampling on a coin flip and start sampling on the outcome.
**Follow-up trap:** *"You now keep only errors and slow traces. What did you break?"* — your baseline. Without a probabilistic slice of healthy traffic you have nothing to diff against, and "what does a normal one look like here" becomes unanswerable at the exact moment you need it. Every tail-sampling config needs a small always-on probabilistic policy alongside the outcome policies.

### Q12 — Your dashboard shows the fleet p99 by averaging each pod's p99. What's wrong?
**Testing:** percentile arithmetic, a very reliable filter.
**Answer:** Percentiles do not average. If one pod out of twenty is at 8s and nineteen are at 100ms, the mean of the twenty p99 values is under 500ms and the incident is invisible. The correct computation sums the histogram buckets across pods first and takes the quantile from the summed histogram: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`.
**Follow-up trap:** *"Fine, we fixed the query and p99 now reads exactly 10.000s and never moves. What now?"* — everything above your top bucket is in `+Inf` and the quantile is clamped at the last finite boundary. The Go client's default buckets top out at 10s. Add buckets above your SLO, or move to native histograms, which use dynamic exponential resolution rather than fixed boundaries.

### Q13 — Your load test says p99 is 47ms. Production says 1.8s for the same build. Explain.
**Testing:** coordinated omission.
**Answer:** Almost certainly coordinated omission. A closed-loop load generator waits for each response before sending the next request, so when the server stalls the generator stops sending — the requests that would have been slow are never issued and never measured. The stall self-censors from the results, and the distortion is concentrated precisely in p99 and beyond, which is the region you are trying to measure. The fix is an open-loop, constant-arrival-rate workload that records intended send time rather than actual send time, so queueing delay is included.
**Follow-up trap:** *"Production server-side p99 also looks fine, but users complain. Same cause?"* — related but distinct: it is a measurement-point problem rather than a workload-model one. A server-side histogram starts timing when the handler accepts the request, so time spent in the load balancer, the kernel accept queue, or TLS handshake is excluded. Measure at the edge, or at the client, to capture what the user experiences.

### Q14 — You have an always-on continuous profile for the incident window and it looks completely normal. What does that tell you?
**Testing:** the off-CPU blind spot.
**Answer:** With a CPU profile, "normal" is exactly what you expect from a service that was *waiting*. Blocked threads consume no CPU samples, so time spent on a socket read, a lock, a pool acquire, or a disk wait is structurally invisible. A flat CPU profile alongside high latency is positive evidence for a wait-bound problem, not evidence of health. Switch to wall-clock or off-CPU profiling — `py-spy --idle`, async-profiler wall mode, off-CPU eBPF — or go back to the trace, where a wait shows up as a gap.
**Follow-up trap:** *"How would you narrow the profile to the slow requests rather than profiling the whole service for 30 seconds?"* — span profiles. Grafana's traces-to-profiles integration scopes the flame graph to one span's time range and service, and embeds it in the span detail pane, so you get the profile *of that request* rather than of every request in a 30-second window. It needs a per-language span-profiling bridge package; without it, traces and profiles remain unlinked signals.

### Q15 — The trace's total is 4.2s but the sum of all child spans is 1.1s. Where's the other 3.1s?
**Testing:** whether you can reason about time that no span accounts for.
**Answer:** Uninstrumented in-process time, and *where* it sits names the cause. Before the first child: a wait — pool acquire, a queue, a scheduler, a stop-the-world pause, or the framework's own middleware chain. Between children: sequential in-process computation, or lock contention. After the last child: response construction — serializing a large payload, compression, signing. The move is to check the parent's self time per interval, then take a span-scoped profile for that window. A useful sanity check first: confirm the child spans really are the children you think, because a missing instrumentation library (an uninstrumented HTTP client, a driver without an OTel plug-in) produces exactly this shape and is far more common than mysterious compute.
**Follow-up trap:** *"How do you tell 'uninstrumented network call' from 'genuinely slow local compute' without adding instrumentation?"* — the profile. Slow local compute shows up as a CPU plateau in a span-scoped flame graph; an uninstrumented network call shows nothing on CPU at all, because the thread is blocked. That is the same off-CPU asymmetry as Q14, used constructively: the *absence* of CPU samples during a 3-second gap is the positive signal that you were waiting on something external.

### Q16 — What would you have had to instrument six months ago for this incident to be debuggable at all? Give me the minimum set.
**Testing:** the principal-level inversion. This is the question the whole module is for.
**Answer:** Six things, in cost order. (1) W3C context propagation across every hop *including* async handoffs, because without a join key nothing else composes. (2) Structured logs with `trace_id` and `span_id` injected from the active context, and the high-cardinality identifiers in the body rather than in index labels. (3) Latency histograms with buckets that straddle the SLO, plus exemplars enabled end to end, so an aggregate can name a request. (4) Tail sampling keeping 100% of errors and 100% over a latency threshold, plus a small probabilistic baseline, with trace-ID-aware Collector routing so the traces are complete. (5) Spans at boundaries with the business attributes that actually partition your traffic — `tenant_id`, `shard`, `model_version`, `cache_hit` — because "a span was slow" is not actionable and "tenant X on shard 3 is slow" is. (6) Continuous profiling running always-on so the profile for the window already exists. Notice that five of the six are configuration and one is a habit, and the habit — attributes that encode what your system actually does — is the one that costs real design effort.
**Follow-up trap:** *"Budget cuts. You get two of the six. Which?"* — context propagation and structured logs with trace IDs, because they are the substrate everything else assumes: exemplars point at traces that must exist, tail sampling operates on traces that must be complete, and profiles need a time window you get from a trace. Without a join key you have three disconnected data sets and are back to correlating by timestamp, which is the 2010 failure mode. Sampling policy can be changed in an afternoon; retrofitting context propagation through an async codebase cannot.

---

## Red flags that fail you

- Reading a waterfall for the widest bar instead of the critical path, and optimising a span that runs in parallel.
- Not knowing where the sampling decision is made, or claiming tail sampling is strictly better without naming its memory cost and its routing requirement.
- Proposing `trace_id` as a Prometheus label or a Loki label. Both are catastrophic and both are common.
- Not knowing exemplars exist, or knowing the term but not that they need OpenMetrics format *and* a server feature flag.
- Averaging percentiles across pods, or computing p99 from anything other than summed histogram buckets.
- Blaming a logging library for null `trace_id` when the cause is context loss at an async boundary.
- Treating a flat CPU flame graph as evidence of health for a latency problem, with no mention of off-CPU time.
- Answering "I'd add a log line and redeploy" for a bug that fires once a week in production.
- Concluding from a single trace. One trace is an anecdote; confirm the shape on a second before you commit to a cause.
- Reading meaning into a 30ms cross-host timing difference with no mention of clock skew.

## Cheat card

```
METHOD (one direction, never backwards):
  METRIC (unsampled, aggregate) -> is it real / where / since when
    -> EXEMPLAR from the TOP latency bucket -> a guaranteed-slow trace
      -> WATERFALL -> critical path -> the span that owns the time
        -> LOGS by trace_id  |  PROFILE by span time window + pod
  Confirm on a SECOND trace before believing it.

WATERFALL ARITHMETIC
  critical path = at each level, descend into the child that FINISHES LAST
  self_time     = duration - UNION of child intervals (union, not sum)
  self ~100%, no children  -> leaf work
  self >50%, has children  -> uninstrumented in-process time -> profile
  self <10%                -> pure router -> descend
  gap BEFORE first child   -> wait (pool / queue / GC / scheduler)
  gap AFTER last child     -> response construction / serialization
  cross-host timing <100ms -> noise (clock skew). in-process is reliable.

SIGNATURES
  RETRY STORM   2-4 siblings, same peer, durations UNIFORM at a round number
                (2000/5000ms), all but last errored, jittered growing gaps.
                uniformity = pinned to a timeout. 2 layers retrying = 9 attempts.
  POOL EXHAUST  gap 200-900ms before first DB span; QUERY DURATION FLAT at 4ms.
                slow DB = query duration GROWS. gap + no DB span = checkout timeout.
  GC PAUSE      every span on ONE POD +same ABSOLUTE ms at same instant, all
                routes equally. no span exists for it. group by pod, not route.
  CACHED-SLOW   p50 flat, p99 up, culprit span in 2% of traces. 1% head sampling
                -> 0.02% of stored traces. fix = outcome-aware selection.
  N+1 CROSS-SVC 50-500 serial identical 5-20ms spans. downstream p99 PERFECT.
                invisible to every single-service tool. batch / DataLoader.
  STAMPEDE      many DIFFERENT traces, identical span, same millisecond.
                aggregate view only.

SAMPLING
  head  decision at root, rides traceparent sampled flag. stateless, O(1) mem.
        traceparent = 00-<32hex trace>-<16hex span>-<2hex flags>
        LOSES rare events: 1-in-10k bug @1% = 1 trace per 1M requests
  tail  Collector buffers trace, decision_wait DEFAULT 30s, num_traces 50,000
        policies: always_sample status_code latency numeric/string/boolean_
        attribute rate_limiting probabilistic span_count and composite
        #1 DEPLOY BUG: all spans must hit the SAME collector ->
          two-tier + loadbalancingexporter routing_key: traceID
        also: traces > decision_wait truncated; aggregates need 1/p adjustment
        -> generate span metrics BEFORE the sampler (spanmetrics CONNECTOR;
           the spanmetrics processor is deprecated)
  layered = head pre-filter + 100% errors + 100% over latency + 100% critical
            route + small probabilistic BASELINE (or you have nothing to diff)
  Datadog: ingestion controls != retention filters (indexed 15d). two knobs.

LOGS
  RULE: high-cardinality -> log BODY. low-cardinality -> index labels.
  Loki defaults: 15 index labels, 10k streams/tenant, 50k global,
    label name 1024 chars, label value 2048. NEVER trace_id as a label.
  query: {service="x",env="prod"} | json | trace_id="4bf92f35..."
  null trace_id on half the lines = CONTEXT LOST at thread-pool / asyncio task /
    callback / @Async / queue consumer. not a logging config bug.
  log the DECISION + its inputs, not "processing request".
  Promtail EOL 2 Mar 2026 -> Grafana Alloy.

EXEMPLARS (metric -> trace, without cardinality)
  needs ALL THREE: SDK exemplar filter TraceBased (inside an active span)
                 + OpenMetrics scrape format (classic format drops them)
                 + prometheus --enable-feature=exemplar-storage (off by default)
  stored per BUCKET -> top-bucket exemplar is a slow request BY CONSTRUCTION

p99
  avg(p99) across pods is MEANINGLESS. sum buckets, then quantile:
    histogram_quantile(0.99, sum(rate(x_bucket[5m])) by (le))
  Go client default buckets .005 .01 .025 .05 .1 .25 .5 1 2.5 5 10 s
    p99 reading EXACTLY 10.0s = clamped at +Inf, add buckets / native histograms
  p50 flat + p99 up            -> minority path (cache miss, bad host, GC, tenant)
  p50 up + p99 up proportional -> everything (capacity / shared dep / hot path)
  p99 up + p99.9 FLAT          -> BOUNDED slow set: one tenant/shard/region
  p50 up + p99 flat            -> measurement change, not a system change
  user with 100 reqs/page: 1 - 0.99^100 = 63.4% chance of hitting a p99 request
  coordinated omission: closed-loop load gen stops sending when server stalls.
    reported 47ms test p99 vs 1.8s prod = 38x. fix = constant arrival rate.
  server-side histogram excludes LB + accept-queue time. measure at the edge.

FLAME GRAPHS
  width = samples = time. x-axis is NOT time (stacks merged, sorted alpha).
  look for PLATEAUS (wide flat frames), not depth. deep+narrow = recursion.
  DIFF flame graph (baseline vs incident window) is the incident tool.
  CPU profile CANNOT SEE OFF-CPU TIME. flat profile + high latency =
    positive evidence of a WAIT. use py-spy --idle / async-profiler wall mode.
  span profiles = flame graph scoped to ONE span's window+service.
    needs a per-language span-profiling bridge package.
  OTel profiles signal: PUBLIC ALPHA Mar 2026. OTLP<->pprof lossless, ~40%
    smaller wire. Collector v0.148.0 pprof receiver. SIG says NOT for critical
    prod yet. 2026 = evaluation window.

eBPF (OBI, ex-Grafana Beyla): v0.8.0 16 Apr 2026, 1.0 GA planned late 2026.
  zero-code spans across a polyglot fleet, but sees SOCKETS not SEMANTICS.
  no tenant_id / cache_hit / model_version. complement to SDKs, not a substitute.
```

## Sources

- [How to Choose Between Head-Based and Tail-Based Sampling in OpenTelemetry — OneUptime](https://oneuptime.com/blog/post/2026-02-06-head-based-vs-tail-based-sampling-opentelemetry/view) — accessed 2026-08-05
- [tailsamplingprocessor README — open-telemetry/opentelemetry-collector-contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md) — accessed 2026-08-05
- [Tail Sampling with OpenTelemetry: Why it's useful, how to do it, and what to consider — OpenTelemetry](https://opentelemetry.io/blog/2022/tail-sampling/) — accessed 2026-08-05
- [Trace Retention — Datadog documentation](https://docs.datadoghq.com/tracing/trace_pipeline/trace_retention/) — accessed 2026-08-05
- [Ingestion Controls — Datadog documentation](https://docs.datadoghq.com/tracing/trace_pipeline/ingestion_controls/) — accessed 2026-08-05
- [Cardinality — Grafana Loki documentation](https://grafana.com/docs/loki/latest/get-started/labels/cardinality/) — accessed 2026-08-05
- [Label best practices — Grafana Loki documentation](https://grafana.com/docs/loki/latest/get-started/labels/bp-labels/) — accessed 2026-08-05
- [Configure trace to logs correlation — Grafana documentation](https://grafana.com/docs/grafana/latest/datasources/tempo/configure-tempo-data-source/configure-trace-to-logs/) — accessed 2026-08-05
- [Traces to profiles — Grafana Pyroscope documentation](https://grafana.com/docs/pyroscope/latest/view-and-analyze-profile-data/traces-to-profiles/) — accessed 2026-08-05
- [Prometheus Metric Exemplars with OpenTelemetry Tracing — Google Cloud OpenTelemetry documentation](https://google-cloud-opentelemetry.readthedocs.io/en/latest/examples/prometheus_exemplars/README.html) — accessed 2026-08-05
- [Correlate metrics and traces by using exemplars — Google Cloud Observability](https://docs.cloud.google.com/stackdriver/docs/instrumentation/advanced-topics/exemplars) — accessed 2026-08-05
- [OpenTelemetry Profiles Enters Public Alpha — OpenTelemetry](https://opentelemetry.io/blog/2026/profiles-alpha/) — accessed 2026-08-05
- [Introducing OpenTelemetry eBPF Instrumentation: Why we donated Grafana Beyla to OpenTelemetry — Grafana Labs](https://grafana.com/blog/opentelemetry-ebpf-instrumentation-beyla-donation/) — accessed 2026-08-05
- [Why OpenTelemetry instrumentation needs both eBPF and SDKs — Grafana Labs](https://grafana.com/blog/why-opentelemetry-instrumentation-needs-both-ebpf-and-sdks/) — accessed 2026-08-05
- [Use the span metrics processor — Grafana Tempo documentation](https://grafana.com/docs/tempo/latest/metrics-from-traces/span-metrics/span-metrics-metrics-generator/) — accessed 2026-08-05
- [Version 2.9 release notes — Grafana Tempo documentation](https://grafana.com/docs/tempo/latest/release-notes/version-2/v2-9/) — accessed 2026-08-05
- [How to Trace Database Connection Pool Exhaustion with OpenTelemetry Metrics — OneUptime](https://oneuptime.com/blog/post/2026-02-06-trace-database-connection-pool-exhaustion-opentelemetry-metrics/view) — accessed 2026-08-05
- [Coordinated Omission: Why Your Latency Numbers Lie — idle-ti.me](https://idle-ti.me/blog/coordinated-omission/) — accessed 2026-08-05
- [Debugging Microservices in Production with Distributed Tracing — Uptrace](https://uptrace.dev/blog/debugging-microservices) — accessed 2026-08-05
- [OpenTelemetry Logging specification — OpenTelemetry](https://opentelemetry.io/docs/specs/otel/logs/) — accessed 2026-08-05
- [How to Fix Logs Not Correlating with Traces in Grafana Loki Because trace_id Is Missing — OneUptime](https://oneuptime.com/blog/post/2026-02-06-fix-logs-not-correlating-traces-grafana-loki-trace-id/view) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
