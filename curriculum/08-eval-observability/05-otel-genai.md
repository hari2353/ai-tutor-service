# OpenTelemetry GenAI Semantic Conventions + Agent Span Design

> **Track:** T08 Eval & Observability · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T08-otel-genai` · **Tags:** observability,critical

## The 30-second version

OpenTelemetry gives you a vendor-neutral trace model — a span tree connected by W3C context propagation, each span carrying attributes, events, and links — and the GenAI semantic conventions define a standard vocabulary (`gen_ai.system`, `gen_ai.usage.input_tokens`, span names like `chat anthropic`, agent operations `create_agent`/`invoke_agent`/`execute_tool`) so that instrumentation from any framework lands in any backend without custom glue. As of the version this module describes — main `semantic-conventions` repo v1.42.0 (12 June 2026), which moved all `gen_ai.*` content into a dedicated `semantic-conventions-genai` repository — every GenAI span, attribute, and metric is still marked **Development status**, not Stable, meaning names can and do change without a major version bump; there is no 1.0 yet. Agent span design means modeling a run as a run span containing step spans, each step containing tool-call and model-call child spans, with reasoning captured as span events (never full prompts as attributes, which are indexed, size-limited, and a PII leak by default) — content capture is off unless you explicitly opt in. The discipline that makes any of this pay off in an incident is sampling on outcome, not on a coin flip up front: keep 100% of errors and 100% of traces over a cost threshold, sample the routine successful traffic at 5-20%, because the trace you need during an incident is exactly the rare expensive one a probabilistic sampler would have thrown away.

## Why this gets asked

The interviewer has been on call for an agent that did something visibly wrong in production — refunded the wrong amount, looped for two minutes, burned $4 on one request — and had either no trace at all or a trace with three spans and no way to see which tool call or which model turn caused it. They want to know whether you'll build a trace that actually answers "why did it do that," whether you know the GenAI conventions are still moving (so hardcoding assumptions about attribute names is a maintenance trap), and whether you understand that dumping full prompts into every span attribute is both a compliance problem and a cost problem, not a debugging convenience.

---

## Lineage: past → present → future

**What came before.** Before any standard existed, every LLM framework and observability vendor invented its own span shape — LangSmith's internal run schema, Helicone's request logs, early homegrown `print`-statement-to-Datadog pipelines — none of which spoke to each other. Teams using two tools (say, a framework's built-in tracer plus a general APM) got two disconnected views of the same request, and switching observability vendors meant re-instrumenting from scratch. The pain was structurally identical to the pre-OpenTelemetry state of general distributed tracing: OpenTelemetry itself formed in 2019 from the merger of OpenTracing and OpenCensus specifically to kill this fragmentation for HTTP/RPC spans, and by 2023-2024 the same fragmentation had reappeared one layer up, for LLM calls specifically — community projects like Traceloop's OpenLLMetry began emitting a proposed `gen_ai.*` vocabulary that later fed directly into OpenTelemetry's official GenAI working group.

**Where it stands now.** The GenAI semantic conventions remain explicitly **Development status** — as of 17 July 2026, no GenAI-specific span, event, metric, or attribute is marked Stable [The state of the OpenTelemetry GenAI semantic conventions (July 2026) — John Hodge](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/) — accessed 2026-08-01. A structural change landed in the same window: the main `open-telemetry/semantic-conventions` repository's **v1.42.0 release (12 June 2026)** deprecated and moved every `gen_ai.*` attribute, span, and metric out into a new dedicated repository, `open-telemetry/semantic-conventions-genai`, and the very next release (v1.43.0, 3 July 2026) of the main repo ships none of that content at all — it now lives and versions independently [Releases · open-telemetry/semantic-conventions](https://github.com/open-telemetry/semantic-conventions/releases) — accessed 2026-08-01. The stated reason is giving fast-moving GenAI work its own release cadence, separate from the slower, stability-bound core HTTP/RPC conventions. Despite the instability, adoption is real: Datadog added native `gen_ai.*` support starting with OTel v1.37, and Grafana has begun collecting LLM traces into Loki using the same vocabulary [OpenTelemetry GenAI Semantic Conventions — The Standard for LLM Observability](https://dev.to/x4nent/opentelemetry-genai-semantic-conventions-the-standard-for-llm-observability-1o2a) — accessed 2026-08-01. The live disagreement is exactly what you'd expect from a pre-1.0 spec with vendor buy-in already: some teams wait for stabilization to avoid migration churn, but the practitioner consensus in 2026 leans toward instrumenting now and accepting that attribute names may need a mechanical rename later, because the alternative — no vendor-neutral telemetry at all, or a proprietary schema you'll migrate away from anyway — is the worse trade.

**Where it's heading.** Agent-specific span vocabulary (`create_agent`, `invoke_agent`, `execute_tool`) and reasoning-token accounting are actively being fleshed out in the dedicated repo, alongside MCP (Model Context Protocol) tool-call conventions being defined in the same place — this is real, in-progress work, moderate-to-high confidence it continues. Expect continued attribute churn through 2026-2027 before anything resembling a 1.0; more speculative is standardized cross-agent handoff span conventions (for multi-agent systems passing control between agents) and any consensus on baking cost directly into span attributes rather than computing it downstream — neither is settled as of this writing.

---

## Mental model

```
                              ONE TRACE = ONE AGENT RUN
   ┌──────────────────────────────────────────────────────────────────────┐
   │  RUN SPAN  (invoke_agent)  trace_id = X, links to eval result + $    │
   │  ┌────────────────────────┐  ┌────────────────────────┐             │
   │  │   STEP SPAN (turn 1)    │  │   STEP SPAN (turn 2)    │   ...       │
   │  │  event: "reasoning: ..." │  │  event: "reasoning: ..." │             │
   │  │  ┌──────────────────┐   │  │  ┌──────────────────┐   │             │
   │  │  │ MODEL SPAN        │   │  │  │ MODEL SPAN        │   │             │
   │  │  │ name: "chat        │   │  │  │ name: "chat        │   │             │
   │  │  │  anthropic"        │   │  │  │  openai"           │   │             │
   │  │  │ gen_ai.usage.*     │   │  │  │ gen_ai.usage.*     │   │             │
   │  │  │ tokens (attrs)     │   │  │  │ tokens (attrs)     │   │             │
   │  │  │ event: prompt/     │   │  │  │ event: prompt/     │   │             │
   │  │  │  completion (OFF   │   │  │  │  completion (OFF   │   │             │
   │  │  │  by default)       │   │  │  │  by default)       │   │             │
   │  │  └──────────────────┘   │  │  └──────────────────┘   │             │
   │  │  ┌──────────────────┐   │  │                          │             │
   │  │  │ TOOL SPAN          │   │  │        (no tool call    │             │
   │  │  │ name: execute_tool │   │  │         this turn)      │             │
   │  │  │ event: args/result │   │  │                          │             │
   │  │  │  (OFF by default)  │   │  │                          │             │
   │  │  └──────────────────┘   │  │                          │             │
   │  └────────────────────────┘  └────────────────────────┘             │
   └──────────────────────────────────────────────────────────────────────┘
         W3C traceparent propagates trace_id across every hop, every service

   A trace that only has start/end timestamps on the run span can tell you
   THAT it failed. Only step-level reasoning events and tool-arg events can
   tell you WHY.
```

Everything hangs off one rule: attributes are for structured, low-cardinality facts you'd want to filter or aggregate on (model name, token counts, tool name); events are for the free-text, potentially-large, potentially-sensitive payload (the actual prompt, the actual tool arguments) that you only want to pay for and expose when you've explicitly opted in.

---

## How it actually works

### The OTel model, refresher

A **trace** is a directed tree of **spans**, each span representing one unit of work with a start/end time, a name, a set of key-value **attributes**, timestamped **events** within the span's lifetime, and **links** to other spans (used for cross-trace references — a batched sub-agent call, an async retry that isn't a direct parent-child relationship). **Context propagation** carries the trace ID and parent span ID across process/service boundaries via the W3C `traceparent` HTTP header, which is what lets a single trace span a router service, an agent orchestrator, and a model API call as one connected tree instead of three disconnected logs. **Resource attributes** (`service.name`, deployment environment) identify which process emitted a span, separate from the span's own attributes.

### The GenAI vocabulary, concretely

- **`gen_ai.system`** — the provider, e.g. `"anthropic"`, `"openai"`.
- **`gen_ai.request.model`** / **`gen_ai.response.model`** — requested vs. actually-served model (these can differ on provider-side routing/fallback).
- **`gen_ai.usage.input_tokens`** — total input token count, cached plus uncached combined per the convention's definition (a documented source of double-counting bugs when a backend also separately reports cache tokens — see the failure table below).
- **`gen_ai.usage.output_tokens`** — completion token count.
- **Span naming pattern**: `{gen_ai.operation.name} {gen_ai.system}` — e.g. a chat completion call against Anthropic is named `chat anthropic` [Inside the LLM Call: GenAI Observability with OpenTelemetry](https://opentelemetry.io/blog/2026/genai-observability/) — accessed 2026-08-01.
- **Agent operation spans**: `create_agent`, `invoke_agent` (the run-level span), `execute_tool` (a tool-call child span) — the highest-signal span types specifically for agent lifecycles [OpenTelemetry GenAI Agent SemConv Cheat Sheet [2026]](https://techbytes.app/posts/opentelemetry-genai-agent-semconv-cheat-sheet-2026/) — accessed 2026-08-01.
- **Metrics**: `gen_ai.client.operation.duration` (histogram, the required latency metric) and `gen_ai.client.token.usage` (histogram, recommended) — these are metric-layer, not span-layer, so they aggregate across requests for dashboards without carrying per-request identity (see the cardinality section below).

### Content capture: off by default, and why

By default, no prompt text, completion text, or tool arguments are captured — only metadata (model name, token counts, duration, finish reason). Capturing full message content is opt-in, controlled by the `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` environment variable, `false` by default [How to Monitor LLM Applications with OpenTelemetry GenAI Semantic Conventions](https://oneuptime.com/blog/post/2026-02-06-monitor-llm-opentelemetry-genai-semantic-conventions/view) — accessed 2026-08-01. When enabled, content goes into **span events**, never span attributes — attributes are indexed by most backends (expensive at scale), size-limited (a full conversation history routinely exceeds typical attribute size caps), and a direct PII/secrets leak into your observability backend's retention policy, which is usually looser than your primary data store's. The convention documents three patterns: don't record content at all, record it directly as span events (accepting the cost/exposure), or store it externally (a blob store with its own retention and access control) and record only a reference/pointer in the span. The third pattern is the right one for anything regulated — it keeps the trace backend from becoming an unaudited copy of your most sensitive data.

### Agent span design: making a trace answer "why did it do that"

The layering that works in practice: **run span** (`invoke_agent`, one per user-facing task) contains **step spans** (one per agent-loop iteration/turn), each of which contains **model spans** (the `chat {provider}` calls) and **tool spans** (`execute_tool`) as children. The part that's easy to skip and shouldn't be: attach a short reasoning summary as a **span event** on the step span, even a single sentence extracted from the model's own chain-of-thought or a structured "plan" field if your agent emits one. A trace with only start/end timestamps and token counts tells you the run took 8 steps and cost $0.40; it cannot tell you why the agent picked the tool it picked on step 4, which is exactly the question that comes up during an incident review. For multi-agent systems, add explicit handoff spans/events at the point control passes from one agent to another, since a supervisor summarizing a sub-agent's uncertain result into a falsely confident final answer (a real failure mode from `T08-agent-eval`) is invisible in a trace that doesn't capture what the sub-agent actually said before the summary was written.

### Debugging a real failure from a trace, worked example

**Symptom:** p95 latency and per-request cost both spike for a subset of requests, support tickets mention "the assistant took forever." **Trace investigation:** pull a slow trace, see the run span has 14 step spans instead of the typical 3-4; each step span's `execute_tool` child span for `lookup_order_status` returns the same malformed-JSON error event; the model span on each subsequent step shows it retrying the same tool call with slightly reworded arguments instead of surfacing the error to the user or escalating. **Root cause, visible only because tool-call events were captured:** the tool's error response format changed upstream (a field renamed) and the agent's error-handling prompt wasn't written to recognize the new shape, so it kept guessing. **Without the tool-arg/result events enabled**, this trace would show 14 identical-looking `execute_tool` spans with no visible reason for the retries, and the on-call engineer would be debugging blind, reduced to guessing between "model is looping for no reason" and "tool is flaky" with no way to distinguish them.

### Sampling: outcome-based, not upfront-probabilistic

Head-based (probabilistic, decided at trace start) sampling is the wrong default for GenAI traces specifically because the traces worth keeping are rare and expensive — errors, cost outliers, long-running loops — and a flat 5% upfront sample rate throws most of them away by construction. The production pattern is **tail-based sampling**: the retain/drop decision happens after the full trace completes, keeping 100% of traces containing an error, 100% of traces over a defined cost threshold (a commonly cited example is $0.50/request), and 5-20% of everything else [Observability for LLM Systems — Rost Glukhov](https://www.glukhov.org/observability/observability-for-llm-systems/) — accessed 2026-08-01. This biases your trace store toward exactly the cases an incident review needs, at a fraction of the storage/ingestion cost of keeping everything.

### The cardinality trap, specific to GenAI

Never put `prompt_id`, `conversation_id`, `request_id`, or any per-request unbounded value as a **metric label** (as opposed to a trace/span attribute, where it's fine). An unbounded label value creates a new time series per unique value in most metrics backends, and prompt text, response text, and per-request IDs are exactly the "cardinality traps to ban early" in GenAI telemetry — putting even one of them on a metric turns a bounded dashboard query into an unbounded, ever-growing index that quietly inflates the observability bill and can degrade query performance across the whole backend, not just for that one metric [AI Workloads & Observability Cost (2026)](https://codingprotocols.com/blog/ai-workloads-observability-cost) — accessed 2026-08-01. Keep per-request identity in traces (linked via exemplars, if your backend supports them) and keep metrics aggregated with only bounded dimensions (model name, provider, environment).

### Linking a trace to an eval result and a cost figure

Use the `trace_id` as the join key: an eval harness (`T08-eval-harness`) or an online evaluator (`T08-ragas-deepeval`'s LangSmith section) that scores a production trace should store its result keyed by that trace's ID, not by a separate request log that has to be manually correlated. Cost should generally **not** be baked into the app as a hardcoded per-token price at emission time — prices change, and a price hardcoded at instrumentation time silently goes stale. Emit raw `gen_ai.usage.input_tokens`/`output_tokens`, and compute cost downstream (in the collector or the observability backend) against a versioned, updatable price table, so a price change doesn't require redeploying every instrumented service.

---

## Build it from scratch

Manual span creation following the run → step → tool/model hierarchy, with content capture gated by an env var — the shape an interviewer may ask you to sketch on a whiteboard:

```python
# untested sketch -- illustrates the span hierarchy and gating, not a
# drop-in replacement for a maintained auto-instrumentation library
import os
from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("agent.runtime")
CAPTURE_CONTENT = os.environ.get("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false") == "true"

def run_agent(user_task: str):
    with tracer.start_as_current_span("invoke_agent", kind=SpanKind.INTERNAL) as run_span:
        run_span.set_attribute("gen_ai.agent.name", "support-agent")
        for step_idx, step in enumerate(agent_loop(user_task)):
            with tracer.start_as_current_span(f"step_{step_idx}") as step_span:
                step_span.add_event("reasoning", {"summary": step.reasoning_summary})  # short, not full CoT

                with tracer.start_as_current_span(f"chat {step.model_provider}") as model_span:
                    model_span.set_attribute("gen_ai.system", step.model_provider)
                    model_span.set_attribute("gen_ai.request.model", step.model_name)
                    model_span.set_attribute("gen_ai.usage.input_tokens", step.input_tokens)
                    model_span.set_attribute("gen_ai.usage.output_tokens", step.output_tokens)
                    if CAPTURE_CONTENT:
                        model_span.add_event("gen_ai.content.prompt", {"content": step.prompt})
                        model_span.add_event("gen_ai.content.completion", {"content": step.completion})

                if step.tool_call:
                    with tracer.start_as_current_span("execute_tool") as tool_span:
                        tool_span.set_attribute("gen_ai.tool.name", step.tool_call.name)
                        if CAPTURE_CONTENT:
                            tool_span.add_event("tool.arguments", {"args": step.tool_call.args})
                            tool_span.add_event("tool.result", {"result": step.tool_call.result})
                        if step.tool_call.error:
                            tool_span.set_status(trace.Status(trace.StatusCode.ERROR, step.tool_call.error))

        run_span.set_attribute("gen_ai.usage.total_cost_estimate_pending", True)  # computed downstream, not here
```

A real deployment should use a maintained auto-instrumentation library (OpenLLMetry/Traceloop's SDK instrumentations for OpenAI/Anthropic/etc.) rather than hand-rolling every span, precisely because those libraries track the semantic conventions' attribute-name churn for you.

---

## How it's done in production

**Instrumentation:** OpenLLMetry (Traceloop) — auto-instruments OpenAI/Anthropic/major provider SDKs to emit `gen_ai.*` spans without manual span code; this is the library most teams reach for first. **OpenInference** (Arize) — a parallel, largely overlapping semantic convention predating full OTel GenAI adoption, used natively by Arize Phoenix; expect some attribute-name friction translating between OpenInference and OTel GenAI conventions on the same trace. **Backends:** Datadog (native `gen_ai.*` support since OTel v1.37), Grafana (LLM traces into Loki), Honeycomb, or a self-hosted OTel Collector feeding Jaeger/Tempo for a fully vendor-neutral stack (cross-reference `T08-obs-platforms` for the full platform comparison).

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Dashboards break or attributes silently disappear after upgrading an instrumentation library | GenAI semconv is Development status; attribute names changed without a major version bump | Pin instrumentation library versions explicitly; diff the emitted attribute schema before upgrading in production |
| Full prompts/PII show up in the trace backend | Content-capture flag left enabled in production, or an auto-instrumentation default changed on upgrade | Default content capture off; if enabled, route through a redaction processor in the OTel Collector before export, or use the store-externally-and-reference pattern |
| Observability bill spikes after an agent feature ships | `conversation_id`/`request_id`/prompt text placed on a **metric** label, creating unbounded time series | Keep per-request identity in trace attributes only; metrics carry bounded dimensions (model, provider, environment) |
| Token usage numbers don't match the provider's invoice | `gen_ai.usage.input_tokens` double-counts cached tokens against a separately-reported cache-token metric | Check whether the convention's definition (cached+uncached combined) matches how your backend's cost calculation expects the split; reconcile against the provider's own usage API, not just the OTel span |
| On-call can see a run failed but not why | No step-level reasoning event, no tool-arg/result events captured | Add a short reasoning-summary event per step span at minimum; enable full content capture for a redacted subset or a feature-flagged debug window during an active incident |
| Trace store is enormous and still doesn't have the trace you needed during an incident | Head-based (probabilistic) sampling applied uniformly, dropping rare expensive/error traces at the same rate as routine ones | Switch to tail-based sampling: 100% of errors, 100% over a cost threshold, sample the rest |

---

## Tradeoffs & when NOT to use it

- **Don't invent your own parallel `genai.*` naming scheme if you intend to use any off-the-shelf backend or dashboard.** You'll translate forever; adopt the OTel GenAI vocabulary even at Development status and budget for a rename migration later — that cost is smaller than permanent vendor lock-in to a bespoke schema.
- **Don't turn on full content capture in production by default.** It's a compliance and cost problem simultaneously (PII exposure, indexed-attribute cost, payload size). Reserve it for a redacted subset, a feature-flagged debug window, or route through the store-externally-with-reference pattern for anything regulated.
- **Don't rely on head-based sampling alone for GenAI traces.** The traces that matter during an incident are the rare, expensive, or erroring ones, which a flat probabilistic sample systematically underrepresents; use tail-based sampling.
- **Don't build the full run/step/tool/model span hierarchy for a single-call, no-loop LLM feature** (one prompt in, one completion out, no tools). A single span with `gen_ai.*` attributes is sufficient; the multi-layer design earns its complexity only once there's an actual agent loop to make legible.
- **Don't wait for the GenAI semantic conventions to reach 1.0 before instrumenting anything.** Given the pace of change described above, that could be a multi-year wait, during which you'd have shipped with no standardized telemetry at all — instrument now against the Development-status spec and accept a migration script may be needed later.
- **Don't bake a hardcoded per-token price into span emission code.** Prices change; compute cost downstream from raw token-count attributes against a table you can update without redeploying instrumented services.

---

## Interview questions

### Q1 — What's the current stability status of the OpenTelemetry GenAI semantic conventions, and why does that matter practically?
**Testing:** whether the candidate actually checked, rather than assuming a mature standard exists.
**Answer:** As of mid-2026 (v1.42.0 of the main repo, 12 June 2026, moved all `gen_ai.*` content into a dedicated `semantic-conventions-genai` repository), every GenAI span, attribute, and metric remains Development status, not Stable — there's no 1.0. Practically: attribute names can and do change without a major version bump, so pinning instrumentation library versions and diffing schemas on upgrade is a real operational discipline, not paranoia.
**Follow-up trap:** *"So should we wait for it to stabilize before instrumenting?"* — no; the practitioner consensus is to instrument now against the moving spec and budget for a rename migration later, because shipping with zero standardized telemetry while waiting is the worse trade.

### Q2 — Design the span hierarchy for a multi-step agent that calls two tools before answering.
**Answer:** A run span (`invoke_agent`) at the top, containing one step span per loop iteration, each step span containing a model span (`chat {provider}`) and, where applicable, a tool span (`execute_tool`) as children. Reasoning is attached as a span event on the step span, not baked into the span name or a bare attribute.
**Follow-up trap:** *"Why not just one flat span per tool call with no step-level grouping?"* — you lose the ability to see which reasoning turn produced which tool call, which is exactly the information needed to answer "why did it call that tool" during a review; flattening the hierarchy trades debuggability for slightly less span-creation code.

### Q3 — Why does the convention put prompt and completion content in span events instead of span attributes?
**Answer:** Attributes are indexed by most backends (expensive at scale), have practical size limits that a full conversation history routinely exceeds, and are exposed by default in a backend whose retention policy is usually looser than your primary data store's — a direct PII/compliance risk. Events carry the same information without those constraints and are opt-in.
**Follow-up trap:** *"Your compliance team says even opt-in event capture is too risky for a regulated workload. What's the alternative?"* — the store-externally-and-reference pattern: content lives in a separate blob store with its own access control and retention policy, and the span carries only a pointer/reference to it.

### Q4 — What's the difference between head-based and tail-based sampling, and which is right for GenAI traces?
**Answer:** Head-based sampling decides whether to keep a trace probabilistically at the start, before anything is known about the outcome. Tail-based sampling waits until the trace completes and decides based on outcome — keep all errors, keep all cost outliers (e.g. traces over $0.50), sample the rest at a low rate (5-20%). GenAI traces need tail-based because the traces worth keeping are rare and expensive, and a flat upfront sample rate throws most of them away.
**Follow-up trap:** *"Doesn't tail-based sampling require buffering every trace until it completes, which costs more upfront?"* — yes, there's a real cost/complexity tradeoff (buffering infrastructure, delayed export), which is exactly why it's usually implemented at the collector level rather than in-process, and why some teams run a hybrid — a moderate head-based rate for routine traffic, with a tail-based override rule for anything crossing an error or cost threshold.

### Q5 — Why is putting `conversation_id` on a metric label a mistake, even though it's fine on a span attribute?
**Answer:** Metric backends create a new time series per unique label value combination; an unbounded value like a conversation ID creates unbounded time series, which is the classic cardinality-explosion failure (see `T08-classic-obs`) — it inflates cost and can degrade query performance across the whole metrics backend. Span/trace attributes don't have this problem the same way because traces aren't pre-aggregated into per-dimension time series.
**Follow-up trap:** *"How would you still correlate a slow metric spike back to specific requests without high-cardinality metric labels?"* — use exemplars where the backend supports them (a metric data point carrying a pointer to a specific trace ID that contributed to it), which gives you the drill-down path without making the ID part of the metric's dimensionality.

### Q6 — A trace shows an agent made 14 tool calls in a loop before failing. What do you need in the trace to diagnose it, and what would be missing if only default (no-content-capture) instrumentation were in place?
**Answer:** You need the tool call arguments and results (or at least error messages) per iteration to see whether the agent was retrying the same failing call, escalating arguments, or genuinely exploring different approaches. With content capture off by default, you'd only see 14 identically-shaped `execute_tool` spans with timing and a tool name, no way to distinguish "looping on the same error" from "legitimately iterating," and you'd have to guess or reproduce the issue manually.
**Follow-up trap:** *"You can't enable full content capture retroactively on a trace that already happened. What do you do for this specific incident?"* — reproduce with content capture enabled in a staging/redacted environment if the failure is reproducible, or fall back to whatever partial signal is available (error status codes on the tool spans, response finish reasons on the model spans) while treating the gap itself as the lesson to fix before the next incident.

### Q7 — How do you link an eval result to the specific production trace it was scored against?
**Answer:** Use the trace ID as the join key — an online evaluator (see `T08-ragas-deepeval`, LangSmith section) or a batch eval job scoring sampled production traces should store its result keyed by that trace's ID, so a regression investigation can pull the exact trace behind a bad score directly, rather than trying to correlate a separate eval log against request logs by timestamp.
**Follow-up trap:** *"Your eval pipeline runs asynchronously, hours after the original trace. Does the trace ID join still work?"* — yes, as long as the trace ID is durably retained and referenced by the eval job at scoring time; the join doesn't require the eval to run inline with the request, only that the ID is captured and threaded through whatever async pipeline does the scoring.

### Q8 — Why shouldn't you hardcode a per-token dollar price into your span-emission code?
**Answer:** Provider prices change over time, and a hardcoded price baked in at instrumentation time silently goes stale — every span emitted after a price change reports a cost figure that's simply wrong, with nothing flagging it. Emit the raw token counts (`gen_ai.usage.input_tokens`/`output_tokens`) and compute cost downstream against a versioned, updatable price table in the collector or backend.
**Follow-up trap:** *"Your finance team wants historical cost trends to reflect the price that was actually in effect at the time, not today's price. How does computing cost downstream handle that?"* — the price table needs to be versioned with effective-date ranges, and the downstream cost computation looks up the price in effect at each span's timestamp, not just the current price — this is exactly why baking a single hardcoded price into emission-time code is doubly wrong, since it also can't represent price history correctly even before it goes stale.

### Q9 — What's the risk of running OpenInference-instrumented code (Arize's convention) alongside OTel-GenAI-instrumented code in the same trace?
**Answer:** The two conventions largely overlap in intent but don't use identical attribute names, so a trace with spans from both risks a fragmented view where the same underlying concept (e.g. token usage) is reported under two different attribute keys depending on which library produced which span, breaking any dashboard or query written against only one convention.
**Follow-up trap:** *"How would you unify them without rewriting one of the instrumentation libraries?"* — a normalization step in the OTel Collector (an attribute-processor rule mapping OpenInference keys to OTel GenAI keys, or vice versa) applied at ingestion, so downstream dashboards only ever see one consistent vocabulary regardless of which library produced the raw span.

### Q10 — Your `gen_ai.usage.input_tokens` numbers don't match the provider's billing dashboard. Debug it.
**Answer:** Check whether the discrepancy lines up with cached-token usage — the convention defines input tokens as cached plus uncached combined, which is a documented source of double-counting if your cost pipeline also separately adds a cache-token line item on top of the span's already-combined total. Reconcile against the provider's own usage/billing API directly rather than assuming the span attribute alone is the full picture.
**Follow-up trap:** *"The provider's API and the span both report the same combined number, but your bill is still higher. What else could explain it?"* — check for retried requests that succeeded on a later attempt but still consumed tokens on earlier failed attempts (each retry is a full token-consuming call even if only the last one appears as the "successful" model span your dashboard highlights), and confirm your span-to-cost pipeline is summing every model span in a trace, not just the last one per step.

### Q11 — When would the full run/step/tool/model span hierarchy be overkill?
**Testing:** the "when not to use it" signal.
**Answer:** For a single-call feature — one prompt in, one completion out, no tool loop, no multi-turn reasoning — a single span carrying `gen_ai.*` attributes is the whole story; building a run/step/tool hierarchy with no actual steps or tools to nest adds spans and code complexity with nothing structural to represent.
**Follow-up trap:** *"That single-call feature just got a tool added to it. When do you refactor to the full hierarchy?"* — the moment there's a second decision point or a tool call that could itself fail or branch, since that's exactly when "why did it do that" becomes a real question a flat single span can't answer; don't wait for a second and third tool before adding the structure.

### Q12 — Explain the three content-handling patterns the GenAI conventions document, and when you'd use the strictest one.
**Answer:** Don't record content at all (default, safest, least debuggable), record it directly as span events (opt-in via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`, useful for debugging but exposes payloads to the trace backend's retention policy), or store it externally with only a reference in the span (most auditable, adds infrastructure). The strictest pattern belongs to anything regulated — healthcare, finance, or any workload where the trace backend's own retention/access-control posture wouldn't pass the same compliance bar as your primary data store.
**Follow-up trap:** *"Storing externally with a reference adds a whole extra system. Is it worth it for a startup with no compliance requirement yet?"* — no, that's exactly the case for the middle pattern (opt-in span events) or even the default (no capture) with a feature-flagged debug window; match the pattern to the actual compliance bar you're under today, and revisit when regulatory requirements or customer contracts change it.

---

## Red flags that fail you

- Claiming the OTel GenAI semantic conventions are a finished, stable 1.0 standard.
- Putting full prompt/completion text on span attributes instead of events, with no mention of the indexing/size/PII issue.
- Not knowing that content capture is opt-in and off by default.
- Recommending head-based-only sampling for GenAI traces with no mention of tail-based sampling for errors/cost outliers.
- Suggesting `conversation_id` or `request_id` as a metric label without recognizing the cardinality-explosion risk.
- Hardcoding a token price into instrumentation code and treating that as a permanent cost figure.
- Describing agent observability as "just add tracing" with no mention of the run/step/tool/model hierarchy or why flat spans don't answer "why."

---

## Cheat card

```
OTEL CORE      trace = span tree, W3C traceparent propagates trace/span ID
               attributes = structured, bounded, filterable/aggregatable
               events = timestamped, free-text, potentially large/sensitive
               links = cross-trace refs (async retry, batched sub-agent call)

SEMCONV STATE  main repo v1.42.0 (12 Jun 2026) moved ALL gen_ai.* to dedicated
               repo (semantic-conventions-genai). v1.43.0 (3 Jul) ships none.
               STATUS: Development, not Stable, no 1.0 as of 17 Jul 2026.
               names CAN change without a major bump -> pin instr. lib version

KEY ATTRS      gen_ai.system (provider) · gen_ai.request.model /
               gen_ai.response.model · gen_ai.usage.input_tokens (cached+
               uncached) · gen_ai.usage.output_tokens
               span name = "{operation} {system}" e.g. "chat anthropic"

AGENT SPANS    invoke_agent (run) -> step spans -> execute_tool / chat {sys}
               (model). reasoning -> SPAN EVENT on step span, not attribute.

METRICS        gen_ai.client.operation.duration (histogram, required)
               gen_ai.client.token.usage (histogram, recommended)

CONTENT        default: NO content captured. opt-in via
CAPTURE        OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true
               3 patterns: don't record / record as span event / store
               externally + reference. strictest for regulated workloads.

SAMPLING       head-based (upfront %) = wrong default, drops rare/expensive
               tail-based = decide after trace completes:
                 100% errors, 100% over cost threshold (~$0.50), 5-20% rest

CARDINALITY    NEVER put conversation_id/request_id/prompt text on a METRIC
TRAP           label -> unbounded time series. Fine on a span/trace attribute.

COST           don't hardcode $/token in emission code (goes stale, no
               history). emit raw tokens, compute cost downstream vs a
               versioned price table.

DEBUG PATTERN  trace_id = join key to eval result + cost figure.
               "why did it do that" needs: step reasoning events + tool
               arg/result events -- timestamps alone only show THAT it failed
```

## Sources

- [The state of the OpenTelemetry GenAI semantic conventions (July 2026) — John Hodge](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/) — accessed 2026-08-01
- [Releases · open-telemetry/semantic-conventions](https://github.com/open-telemetry/semantic-conventions/releases) — accessed 2026-08-01
- [Inside the LLM Call: GenAI Observability with OpenTelemetry — opentelemetry.io](https://opentelemetry.io/blog/2026/genai-observability/) — accessed 2026-08-01
- [OpenTelemetry GenAI Semantic Conventions — The Standard for LLM Observability — DEV Community](https://dev.to/x4nent/opentelemetry-genai-semantic-conventions-the-standard-for-llm-observability-1o2a) — accessed 2026-08-01
- [OpenTelemetry GenAI Agent SemConv Cheat Sheet [2026]](https://techbytes.app/posts/opentelemetry-genai-agent-semconv-cheat-sheet-2026/) — accessed 2026-08-01
- [How to Monitor LLM Applications with OpenTelemetry GenAI Semantic Conventions — OneUptime](https://oneuptime.com/blog/post/2026-02-06-monitor-llm-opentelemetry-genai-semantic-conventions/view) — accessed 2026-08-01
- [Observability for LLM Systems: Metrics, Traces, Logs, and Testing in Production — Rost Glukhov](https://www.glukhov.org/observability/observability-for-llm-systems/) — accessed 2026-08-01
- [AI Workloads & Observability Cost (2026): Why It Explodes, How to Cap It — Coding Protocols](https://codingprotocols.com/blog/ai-workloads-observability-cost) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
