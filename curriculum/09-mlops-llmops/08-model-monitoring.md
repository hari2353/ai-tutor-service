# Model Monitoring in Production: What to Log, Alert Thresholds, Dashboards

> **Track:** T09 MLOps / LLMOps · **Time:** 2.5h · **Prereqs:** T08 · **Updated:** 2026-08-01
> **Module id:** `T09-model-monitoring` · **Tags:** production,critical

## The 30-second version

Model monitoring has four layers, and each catches a different class of failure: infra (latency, error rate, saturation — catches the system falling over), data (schema, nulls, ranges, cardinality — catches upstream pipelines breaking silently), model (prediction distribution, confidence, feature-importance shift — catches the model degrading before you have labels), and business (the metric that actually pays the bills — catches everything else lying to you). The hard part isn't instrumentation, it's that ground truth is delayed by days to months in almost every real system, so you monitor proxies (prediction drift, confidence, agreement with a shadow model) while waiting for labels to arrive, and you design alerts on rate-of-change and seasonality-aware baselines rather than static thresholds, because a static threshold either pages you every Monday morning traffic spike or misses a real 3am regression entirely. For LLM systems the same four layers apply, but you add token cost per request, refusal rate, and judge-score drift, because "the model returned a response" no longer means "the model did its job."

## Why this gets asked

The interviewer has been paged at 3am for a threshold that was miscalibrated against last Tuesday's traffic, and separately has shipped a model regression that nobody noticed for three weeks because the only thing being watched was uptime. They want to know if you understand that **monitoring infrastructure health and monitoring model health are different problems with different tooling and different time constants**, and whether you've internalized that the absence of ground truth is the default state in production, not an edge case. At staff/principal level they're probing whether you can design an alerting system that a human being can actually live with — not one that is theoretically complete and practically ignored.

---

## Lineage: past → present → future

**What came before.** Classical ML monitoring inherited wholesale from software APM (Application Performance Monitoring) — Nagios, then Datadog/New Relic — which watches CPU, memory, latency, and error rate. That's necessary but answers a different question than "is the model still right." Through the mid-2010s, most ML teams had *no* model-layer monitoring at all: a model shipped, and the first signal anyone got that it had degraded was a product metric moving weeks later, or a customer complaint. The pain that killed this approach was concrete and recurring: silent feature pipeline breakage. A schema change three services upstream nulls out a feature, the serving pipeline defaults it to zero instead of failing loudly, and the model keeps returning confident predictions on garbage inputs for weeks because nothing was watching the *input distribution*, only the *system's uptime*.

**Where it stands now.** The current stack has genuinely separated into two disciplines that talk to each other: ML observability platforms (Evidently AI, Arize/Arize Phoenix, WhyLabs, Fiddler, Superwise) that compute distributional statistics over predictions and features, and classic observability (Prometheus/Grafana, Datadog, OpenTelemetry — see `T08-otel-genai`) for infra and traces. The live disagreement is over **how much of drift detection is actually worth automating versus reviewing manually**: PSI/KS dashboards produce a lot of statistically "significant" noise at high sample sizes (see `T09-data-drift`), and several practitioners now argue that continuous automated drift alerting without a downstream performance or business-metric gate produces more pager fatigue than value. What's actually deployed at scale is usually a hybrid: automated data-quality checks (schema, null rate, range) that page immediately because they're unambiguous, and prediction/feature drift that feeds a dashboard reviewed on a cadence (daily/weekly) rather than an alert that pages a human. For LLM-specific systems, monitoring has moved fastest: LLM observability platforms (Arize Phoenix, Langfuse, Galileo, WhyLabs LangKit, LangSmith) now ship hallucination-proxy scoring, judge-based quality scoring, and cost-per-request tracking as first-class primitives — LLM apps made this urgent because the failure mode (confidently wrong text) doesn't show up as an infra metric or a schema violation at all [Top LLM Observability Tools in 2026 — Confident AI](https://www.confident-ai.com/knowledge-base/compare/10-llm-observability-tools-to-evaluate-and-monitor-ai-2026) — accessed 2026-08-01.

**Where it's heading.** High confidence: judge-based and reference-free quality scoring (LLM-as-judge running continuously in production, not just at eval time) becomes a standard monitoring signal alongside latency and error rate, because ground truth for generative tasks essentially never arrives (see `T08-llm-as-judge`). Medium confidence: monitoring and eval converge into one system — the same rubric that gates a deploy in CI (`T09-model-cicd`) becomes the thing sampled continuously in prod. Speculative: automated root-cause attribution (a monitoring system that doesn't just say "prediction mean shifted" but "feature X's shift explains 80% of it, and it correlates with a deploy of upstream service Y") is an active area (Arize, WhyLabs, and several startups are building this) but is not yet reliable enough to act on without a human in the loop.

---

## Mental model

Four layers, each catching what the layer below it cannot see, and each with a different natural time constant:

```
 BUSINESS   revenue/user, conversion, task success rate     days–weeks
     ▲      (the metric that actually pays; often the LAST thing to move
     │       and the FIRST thing anyone actually cares about)
     │
 MODEL      pred. distribution, confidence, calibration,    minutes–hours
     ▲      feature-importance shift, judge scores (LLM)
     │      (catches "the model is behaving differently"
     │       BEFORE you have ground truth)
     │
 DATA       schema, null rate, range, cardinality,          seconds–minutes
     ▲      type drift, freshness
     │      (catches "the input is not what training assumed")
     │
 INFRA      latency (p50/p95/p99), error rate, GPU/CPU      seconds
            saturation, queue depth, OOM
            (catches "the system is falling over")
```

The critical property: **each layer can be green while the layer above it is on fire.** Infra can be perfectly healthy — 50ms p99, 0% error rate — while data has drifted, the model's predictions are garbage, and the business metric is bleeding. This is the single most common monitoring gap in production ML: teams instrument infra thoroughly (because SRE tooling makes it easy) and stop there.

---

## How it actually works

### Layer 1: Infra — the part everyone already does

Standard APM: latency percentiles (p50/p95/p99, not average — average hides the tail that actually causes complaints), error rate by type (4xx vs 5xx vs timeout), GPU/CPU/memory saturation, queue depth, and autoscaling lag. For LLM serving specifically, add: time-to-first-token (TTFT), inter-token latency, KV cache utilization, and request queue depth on the serving engine (see `T05-inference-serving` for vLLM's continuous batching internals — a saturated KV cache shows up here before it shows up as a raw latency number). Nothing here is ML-specific; it's the same discipline as any distributed service.

### Layer 2: Data — the layer that catches silent pipeline breakage

What to check per feature, per request or on a sample:

- **Schema**: type didn't change, no new/missing columns.
- **Nulls**: null rate per feature, compared against a rolling baseline, not zero.
- **Range**: min/max/percentile bounds — a `total_purchases` feature that starts returning negative numbers has a bug upstream, not a business insight.
- **Cardinality**: a categorical feature that suddenly has 10x the distinct values usually means an ID leaked into a category column.
- **Freshness**: time since the feature was last updated — a feature store serving 6-hour-stale data (see `T09-feature-stores`) can be schema-valid and range-valid and still be wrong.

This layer is checked with libraries like Great Expectations, Deequ (Spark-native, relevant given PySpark/EMR pipelines), or Evidently's data-quality report, and it's the layer that should page immediately because violations are unambiguous — a null rate spiking from 0.1% to 40% is not a judgment call.

### Layer 3: Model — catching degradation before ground truth exists

This is the layer people under-invest in because it requires holding a reference distribution and running statistical tests (full mechanics in `T09-data-drift`: PSI, KS, KL/JS divergence). What to track:

- **Prediction distribution**: mean, variance, and the full histogram of the model's output, compared to a training/reference window.
- **Confidence / calibration**: mean predicted probability for classifiers, logprob-derived confidence for generative models. A confidence distribution that shifts without an accuracy signal moving is often the earliest warning you get.
- **Feature importance shift**: recompute SHAP/permutation importance periodically on production data; if the top features change, the model is now relying on something different than what was validated.
- **Prediction-input agreement**: for models with a fast, cheap fallback (a simple heuristic or an older model version), running both and tracking their disagreement rate is a robust drift proxy that doesn't require labels at all.

### Layer 4: Business — the metric that actually pays

Click-through rate, conversion, task completion rate, revenue per session, support-ticket rate. This is downstream of everything else and lags by days to weeks, which is exactly why layers 2 and 3 exist: **by the time the business metric moves, you've already lost the window to catch it cheaply.** The business metric is also the final arbiter — a drift alert that never shows up in a business metric might be real drift that doesn't matter, and that distinction matters when you're deciding whether to retrain (`T09-data-drift`'s retraining-trigger section).

### Ground truth delay, and what you monitor while you wait

In almost every production system, labels don't exist in real time:

- **Fraud**: chargebacks take 30-90 days to arrive.
- **Recommendations/ranking**: "was this actually good" requires downstream conversion, which can take weeks.
- **Content moderation / LLM safety**: there may never be ground truth at all, only sampled human review.
- **Credit risk**: default labels take up to years.

Proxies used in the interim, roughly in order of how much they actually correlate with real degradation:
1. **Shadow/champion-challenger agreement** — run the new model and old model side by side, alert on disagreement rate rising (`T09-model-cicd` covers the deployment mechanics).
2. **Prediction and confidence drift** (layer 3 above) — doesn't require labels, catches distributional shift.
3. **Proxy labels** — a cheaper, faster-arriving signal that correlates with the real outcome (e.g., "did the user click" as a proxy for "was the recommendation relevant" while waiting for purchase data).
4. **Human-in-the-loop sampling** — route 1-5% of predictions to human review, which gives you a small but real ground-truth stream faster than the natural label latency.
5. **LLM-as-judge scoring** — for generative systems, a judge model scores a sample of outputs continuously; not ground truth, but far better than nothing (`T08-llm-as-judge`).

### Alert thresholds: why static ones page you at 3am for nothing

The naive approach — "page if latency p99 > 500ms" or "page if PSI > 0.25" — fails in both directions:

- **False positives**: a static latency threshold pages every Black Friday, every Monday-morning traffic ramp, every time a batch job runs concurrently. A static PSI threshold pages on every genuine but harmless seasonal shift (weekday vs weekend traffic mix).
- **False negatives**: a static threshold tuned loose enough to survive the noise above misses a real regression that happens to occur during a normally-quiet period, because the absolute threshold was calibrated to the noisy period.

What actually works:

1. **Seasonality-aware baselines.** Compare against the same hour/day-of-week last week, not a fixed number. A latency p99 of 400ms might be completely normal at 2pm Tuesday and a genuine incident at 3am Sunday.
2. **Rate-of-change over absolute value.** "PSI increased by 0.15 in the last hour" is a more honest signal than "PSI is currently 0.22," because it's insensitive to a baseline that was already elevated for a known, accepted reason.
3. **Multi-signal correlation before paging.** Page on infra alone; require data + model layers to agree (e.g., "null rate up AND prediction mean shifted") before paging on model-layer signals, since either alone has a high false-positive rate.
4. **Burn-rate style alerting** (borrowed from SRE error-budget practice): alert faster on a fast, large deviation and slower on a slow, small one, rather than one fixed threshold for both.
5. **Business-metric gate for retraining triggers**, not drift alone — see `T09-data-drift`. Drift is a necessary but not sufficient condition to act.

A concrete example of the failure this avoids: a team sets `PSI > 0.25 → page`. Every Sunday, weekend traffic mix shifts a categorical feature's distribution enough to cross 0.25. After three weekends of 3am pages for nothing, the on-call engineer silences the alert. Two months later a real data pipeline bug produces the same PSI value and nobody looks at it for five days, because the alert channel has been muted since week one. This is not a hypothetical; it is the standard lifecycle of a poorly-calibrated static threshold, and interviewers who've lived it will probe for whether you know the failure mode, not just the fix.

### Logging design: what to log, sampling, PII, and cost

**Per-request, log at minimum:** request id, timestamp, model version/hash, input feature vector (or a hash/summary of it if large), raw prediction, confidence/logprobs, latency breakdown (queue time, inference time, post-processing), and any fallback/error path taken. For LLM requests specifically: prompt template id and version, token counts (input/output), model/deployment id, and (sampled) the actual prompt and completion text.

**Sampling strategy.** Full-fidelity logging of every request — especially prompt/completion text for an LLM system — is expensive at scale and often unnecessary: at 1M requests/day with a 500-token average round trip, full-fidelity text logging alone can run into hundreds of GB/month before considering retention, and the marginal value of request #999,999 versus a well-designed sample of it is close to zero for drift detection. Common strategy: log 100% of structured metadata (ids, latencies, token counts, confidence) cheaply, and sample 1-10% of full request/response payloads, with **oversampling on the tail** — always log requests with unusually high latency, low confidence, an error, or a flagged safety response, since those are disproportionately the ones you'll need later.

**PII handling.** Prompt/completion text for consumer-facing LLM products routinely contains PII. Options, roughly in order of increasing operational cost and decreasing risk: (a) don't log raw text at all, only derived features (token counts, embeddings, judge scores); (b) log with a PII redaction/scrubbing pass (regex + NER-based) before storage; (c) log raw but with strict access control and a short retention window; (d) log to a separate, more tightly access-controlled store than your general observability stack. The choice interacts directly with data residency and compliance posture (GDPR, HIPAA if applicable) — see `T09-bedrock-vs-sagemaker` for how this affects the managed-vs-self-hosted decision.

**Cost of full-fidelity logging at scale.** Three separate costs compound: storage (raw text and embeddings are large — a single request's embedding at 1536 dimensions in float32 is ~6KB before any indexing overhead), the observability platform's per-event or per-GB pricing (several LLM observability vendors price on trace volume, which scales linearly with traffic and can become a material line item at high QPS), and the compute cost of running LLM-as-judge scoring on a sample (judge calls are themselves LLM calls with their own token cost — judging 5% of a 10M-request/month system with a cheap judge model is a real, budgeted expense, not a rounding error).

### Dashboards that get looked at vs dashboards that exist

The uncomfortable truth: most ML monitoring dashboards are built once, demoed once, and never opened again. What makes a dashboard actually get used:

- **It answers a specific question someone asks routinely** ("is the model I shipped yesterday behaving differently from the one it replaced") rather than displaying everything measurable.
- **It's the thing referenced in the on-call runbook**, not a separate artifact from the alert. If an alert fires and the runbook doesn't link straight to the dashboard state that caused it, the dashboard exists but doesn't get looked at during the one moment it matters.
- **It shows a baseline/comparison, not just a current value.** "PSI = 0.18" is meaningless without last week's PSI = 0.05 next to it.
- **Fewer, denser panels beat comprehensive coverage.** A single "model health" panel per model (prediction mean/variance trend, confidence trend, top-3 drifted features, business metric) that a human can scan in 30 seconds beats twenty tabs of every statistic computed.

### Monitoring LLM systems specifically

Everything above applies, plus signals that don't exist for classical ML:

- **Token cost per request** — track input/output tokens and $ cost per request, per model, per prompt template. This is a business-critical number that can silently regress (a prompt template change that adds 40% more context tokens is invisible in latency but doubles cost) and it's one of the five concrete numbers this module commits to: a prompt-length regression from 800 to 1,400 average input tokens at $3/1M input tokens and 2M requests/month is roughly $1,800/month in pure cost drift with zero user-visible symptom.
- **Hallucination proxies** — you rarely have ground truth for factuality in production. Proxies: retrieval-groundedness score for RAG (does the answer's claims trace back to retrieved context — see `T06-rag-production`), self-consistency across repeated sampling, and LLM-as-judge factuality scoring on a sample.
- **Refusal rate** — the fraction of requests where the model declines to answer. A refusal rate that jumps after a model version bump (a common side effect of provider-side safety-tuning updates you don't control on a hosted model) is a real production incident that looks nothing like a classical ML failure — see `T09-bedrock-vs-sagemaker` on the version-pinning implications of not controlling the model artifact.
- **Judge scores and their drift** — run the same judge rubric continuously on a sample, and monitor the *judge score distribution* the same way you'd monitor a classifier's prediction distribution. Judge models themselves drift when the provider updates them silently (see `T08-llm-as-judge` for why judge-model pinning matters).
- **Per-tool/per-step metrics for agentic systems** — for a multi-step agent, aggregate metrics hide which step is failing; log success/failure and latency per tool call, not just end-to-end (ties to `T09-otel-genai`/`T08-otel-genai` span-level tracing).

### A named failure mode: silent truncation, invisible in accuracy

**Symptom:** an upstream ETL job starts truncating a feature pipeline (say, a user-history feature capped at 50 events instead of the intended 500 due to a config regression during a deploy). The observable signature: prediction *mean* shifts as a step function at the deploy timestamp, feature-level null rate stays at 0% (the field is still populated, just with less history), and infra metrics stay completely flat — no errors, no latency change. **Accuracy metrics stay flat for two weeks** because labels for this system lag 14 days, so nothing in the label-based dashboard moves at all during the window that matters. The only signal available in real time is layer 3: the prediction-distribution monitor catching a step change in the mean, correlated in time with a deploy event. Teams without layer-3 monitoring — running only infra + eventual accuracy — discover this exactly two weeks later when the accuracy dashboard finally drops, at which point two weeks of degraded predictions have already shipped.

---

## Build it from scratch

A minimal prediction-distribution monitor — the kind of thing you'd be asked to sketch on a whiteboard. Detects a step-change in prediction mean using a simple rolling z-score, which is the mechanism behind the failure mode above.

```python
# untested sketch
from collections import deque
from dataclasses import dataclass, field
import statistics

@dataclass
class PredictionMonitor:
    window: int = 500          # reference window size
    alert_z: float = 4.0       # z-score threshold; tune against false-positive budget
    _reference: deque = field(default_factory=lambda: deque(maxlen=500))
    _recent: deque = field(default_factory=lambda: deque(maxlen=50))

    def observe(self, prediction: float) -> dict | None:
        self._recent.append(prediction)
        if len(self._reference) < self.window:
            self._reference.append(prediction)
            return None

        ref_mean = statistics.mean(self._reference)
        ref_std = statistics.pstdev(self._reference) or 1e-6
        if len(self._recent) < self._recent.maxlen:
            self._reference.append(prediction)  # still building recent window
            return None

        recent_mean = statistics.mean(self._recent)
        z = (recent_mean - ref_mean) / (ref_std / (len(self._recent) ** 0.5))

        # slide the reference window forward so slow drift doesn't get stuck
        # comparing against an increasingly stale baseline
        self._reference.append(prediction)

        if abs(z) >= self.alert_z:
            return {
                "alert": "prediction_mean_shift",
                "z_score": round(z, 2),
                "reference_mean": round(ref_mean, 4),
                "recent_mean": round(recent_mean, 4),
            }
        return None
```

Three things a real version needs that this sketch skips: a *frozen* reference window (this sliding version will eventually absorb the drift into its own baseline and stop alerting — see `T09-data-drift`'s reference-window section for why that's a real bug, not a simplification), multivariate correlation with feature-level nulls/ranges before paging, and persistence so the monitor survives a restart.

---

## How it's done in production

Managed/framework layer and what it adds over the sketch above:

| Tool | What it adds |
|---|---|
| **Evidently AI** | Pre-built drift/data-quality reports (PSI, KS, several others), dashboarding, works offline over batches or as a service |
| **Arize / Arize Phoenix** | Full observability platform; OpenTelemetry-based tracing for LLM/agent apps, embedding drift visualization, hallucination and retrieval-relevance scoring built in |
| **WhyLabs** | `whylogs` for lightweight statistical profiling at the edge (compute the profile where the data lives, ship only the summary), LangKit for LLM-specific metrics |
| **Fiddler** | Enterprise-focused, strong on explainability (SHAP-based) tied into monitoring, model-risk/compliance workflows |
| **Prometheus + Grafana** | Infra layer; also used for model-layer metrics if you export them as custom gauges/histograms, but you're building the statistical layer yourself |
| **Langfuse / LangSmith / Galileo** | LLM-specific: trace-level cost tracking, prompt-version comparison, judge-score dashboards, session replay |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Prediction mean steps abruptly, accuracy flat | Upstream feature pipeline silently truncated/nulled a field; labels haven't arrived yet | Layer-3 prediction/feature monitoring with alerting independent of label latency |
| Alert channel muted by on-call | Static threshold triggers on routine seasonality (weekly/daily cycle) | Seasonality-aware baseline, rate-of-change alerting, multi-signal correlation before paging |
| Model looks fine, business metric bleeding for weeks | No business-layer monitoring, or business metric reviewed only monthly | Wire a leading proxy metric (CTR, engagement) reviewed daily, not just the lagging metric |
| Confidence distribution shifts, no accuracy signal moves | Ground truth delayed; confidence drift is the earliest available proxy | Treat confidence/calibration drift as an actionable signal on its own, don't wait for labels |
| LLM cost triples with no traffic change | Prompt template regression added context tokens, or a fallback path silently upgraded to a pricier model | Log token counts and $ cost per request per prompt-template version; alert on cost/request, not just total spend |
| Refusal rate jumps after no code change on your side | Managed model provider silently updated safety tuning on the model alias you're pointing at | Pin exact model version where the provider allows it; monitor refusal rate as a first-class metric |
| Judge scores drift downward over a month with no model change | Judge model itself was silently updated by the provider | Pin judge model version; periodically validate judge against a small human-labeled set |
| Dashboard exists, nobody opens it during an incident | Built once, not linked from the alert/runbook, too many panels | Link dashboard state directly from the alert payload; cut to one "model health" panel per model |

---

## Tradeoffs & when NOT to use it

- **Don't build a full four-layer monitoring stack for a low-stakes, low-traffic model.** A weekly-batch model with 200 predictions/day serving an internal dashboard does not need PSI dashboards and judge-score tracking; a spreadsheet someone eyeballs monthly is the correctly-sized solution, and over-instrumenting it is wasted engineering time better spent elsewhere.
- **Don't page a human on model-layer drift signals alone.** Drift is not "the model broke," it's "the input population changed" — sometimes for a good reason (a new market segment, a legitimate seasonal shift). Route drift to a reviewed dashboard, and reserve paging for infra and unambiguous data-quality violations.
- **Don't rely on accuracy-based monitoring as your only signal when label latency exceeds your acceptable time-to-detect.** If labels take two weeks and your tolerance for a bad model in production is two days, accuracy monitoring alone cannot meet that SLA by construction — you need proxy-based layer-3 monitoring regardless of how good your eventual accuracy metric is.
- **Don't log full-fidelity prompt/completion text for every request in a consumer LLM product without a PII plan.** The legal and security exposure of raw-text logs at scale usually costs more than the sampling discipline required to avoid it.
- **Full-fidelity logging on cost grounds**: for very high QPS systems, decide the sampling rate *before* the storage bill forces the decision. Retrofitting sampling after a compliance or cost incident is far more painful than designing it in from the start.

---

## Interview questions

### Q1 — What are the four layers of ML monitoring and what does each catch?
**Testing:** baseline vocabulary and whether the candidate treats this as one problem or four.
**Answer:** Infra (latency, error rate, saturation — the system falling over), data (schema, nulls, range, cardinality — the input no longer matching what training assumed), model (prediction distribution, confidence, feature-importance shift — the model behaving differently before you have labels), business (the metric that actually pays — the final arbiter, but slow to move).
**Follow-up trap:** *"Which layer would you cut if you could only keep two?"* — infra and data, because they're the cheapest to instrument, catch the most common real incidents (pipeline breakage, service degradation), and don't require a reference distribution or statistical machinery. Model-layer monitoring is higher-value per-incident but more expensive to build correctly.

### Q2 — Why is ground truth usually unavailable in production, and what do you do about it?
**Testing:** whether the candidate has actually operated a model in prod versus only trained one.
**Answer:** Labels lag by the natural delay of the outcome — fraud chargebacks take 30-90 days, recommendation conversion takes weeks, content moderation may never get ground truth at all. In the interim you monitor proxies: shadow/challenger agreement, prediction and confidence drift, cheaper proxy labels, sampled human review, and for LLMs, continuous judge scoring.
**Follow-up trap:** *"How do you know your proxy is actually correlated with the real outcome?"* — validate it retrospectively once labels do arrive: check that periods of high proxy-signal (e.g., prediction drift) actually correlate with periods of low eventual accuracy. If they don't correlate, the proxy is theater, not monitoring.

### Q3 — Design an alerting scheme that won't page someone at 3am for nothing.
**Testing:** operational maturity, not statistics.
**Answer:** Reject static absolute thresholds. Use seasonality-aware baselines (compare to the same hour last week), rate-of-change over absolute value, and require multi-signal correlation (e.g., data AND model layer agreeing) before paging on anything but infra and unambiguous data-quality violations. Business-metric or downstream-performance gates before triggering anything as heavyweight as a retrain.
**Follow-up trap:** *"Give me the failure mode of a static threshold specifically."* — walk through the named failure mode: a static PSI threshold trips every weekend on routine traffic-mix seasonality, on-call mutes the channel after three false pages, and the real incident two months later goes unnoticed for five days because the channel is dead.

### Q4 — What's the difference between monitoring accuracy and monitoring drift, and why do you need both?
**Answer:** Accuracy requires labels and therefore lags by the label-latency window; drift requires no labels and is available immediately but doesn't directly tell you the model got worse (a benign distribution shift can happen with no accuracy impact). You need both because drift gives you early warning with false-positive risk, and accuracy gives you ground truth with a latency cost you often can't afford.
**Follow-up trap:** *"Can you have drift with zero accuracy impact?"* — yes, routinely: covariate shift (P(X) changes) without concept drift (P(Y|X) changes) can leave the model just as accurate on the new distribution. This is exactly why drift alone shouldn't auto-trigger retraining; see `T09-data-drift`.

### Q5 — Walk me through the silently-truncated-feature failure mode.
**Testing:** whether the candidate can reason about an incident end-to-end, not just recite terms.
**Answer:** An upstream ETL/config regression truncates a feature (e.g., history window capped at 50 events instead of 500). Observable: prediction mean steps at the deploy timestamp, feature null rate stays 0% (masking it from schema checks), infra stays flat, and accuracy — if labels lag two weeks — stays flat through the entire window that matters. Only layer-3 prediction-distribution monitoring, correlated with deploy timestamps, catches it in real time.
**Follow-up trap:** *"Why didn't the null-rate check catch it?"* — because truncation isn't nullification; the field is populated, just with less data than intended. This is why range/cardinality checks matter alongside null checks — a shortened history changes the *distribution* of downstream aggregate features even though no individual field is null.

### Q6 — How do you decide what to log per request, and at what sampling rate?
**Answer:** Log 100% of cheap structured metadata (ids, latency breakdown, token counts, confidence, model version) always. Sample full-fidelity payloads (raw prompt/completion, full feature vector) at 1-10% depending on volume and cost, with mandatory oversampling of the tail — always log errors, low-confidence predictions, and flagged/unusual outputs, since those are disproportionately what you need during an incident.
**Follow-up trap:** *"What if the incident you need to debug happened in the 90% you didn't sample?"* — this is why tail-oversampling matters more than raw sampling rate; most incidents concentrate in the tail (errors, latency spikes, low confidence), which is exactly the slice you should never sample down.

### Q7 — What do you log differently for an LLM system versus a classical model?
**Answer:** Add prompt template id/version, input/output token counts and derived $ cost, judge/quality scores on a sample, refusal flag, and (for RAG) retrieved-context ids for groundedness checks later. Classical logging (features, prediction, confidence, latency) still applies but "prediction" is now a variable-length text blob, which changes both storage cost and PII exposure.
**Follow-up trap:** *"Your cost per request tripled with no traffic increase — where do you look first?"* — token counts per prompt-template version, before assuming a pricing change; a context-length regression in a prompt template is a common, invisible-in-latency cause, and it's a real number: going from 800 to 1,400 average input tokens at $3/1M tokens and 2M requests/month is roughly $1,800/month in pure drift with no other symptom.

### Q8 — How do you monitor hallucination in production without ground truth?
**Answer:** Proxies, not detection: retrieval-groundedness scoring for RAG (does the claim trace back to retrieved context), self-consistency across repeated sampling of the same prompt, and LLM-as-judge factuality scoring on a sample against a rubric. None of these are ground truth; all of them are directionally useful and should be tracked as trends, not absolute pass/fail.
**Follow-up trap:** *"What happens when the judge model itself is updated by the provider?"* — your judge-score trend can shift for reasons that have nothing to do with your system's actual quality. Pin the judge model version explicitly, and periodically validate it against a small human-labeled sample so you can tell judge drift from real drift.

### Q9 — A model's refusal rate jumps 15% overnight with no deploy on your side. Diagnose it.
**Answer:** If you're on a managed/hosted model (Bedrock, OpenAI, etc.) pointed at a model alias rather than a pinned version, the provider likely updated the underlying model's safety tuning. Check the model version/alias first, before assuming a prompt or data issue on your end.
**Follow-up trap:** *"How do you prevent this going forward?"* — pin to an explicit model version where the provider supports it, and treat refusal rate as a first-class monitored metric with its own alert, not something you only notice from user complaints. See `T09-bedrock-vs-sagemaker` for exactly which providers let you pin versus force you onto a rolling alias.

### Q10 — Why do dashboards get built and then ignored?
**Answer:** Usually because they were built as a demo artifact rather than tied to an operational workflow — not linked from the alert that fires, not showing a comparison baseline, and covering too many metrics for a human to scan during an incident. A dashboard earns its keep by being the first thing a runbook points you to, showing "now vs last week" rather than a bare current value, and being small enough to read in 30 seconds.
**Follow-up trap:** *"How would you measure whether your own dashboards are actually used?"* — track dashboard view events correlated with incident timestamps; a dashboard with zero views outside of the week it was built is a signal to delete it, not to add more panels to it.

### Q11 — Design the monitoring plan for a fraud model where labels (chargebacks) take 60-90 days.
**Testing:** applying the framework to a genuinely hard case.
**Answer:** Layer 3 carries almost the entire real-time burden here: prediction-score distribution, confidence, and feature-importance shift, watched continuously. Add a fast proxy label — manual review outcomes on a sampled subset, or a faster-arriving weak signal like customer-reported disputes (days, not months) — to get a partial ground-truth stream well before the 60-90 day chargeback window closes. Business-layer monitoring (chargeback rate, false-positive rate on blocked transactions) still runs, but it's explicitly a lagging confirmation signal, not the primary detection mechanism.
**Follow-up trap:** *"Your proxy signal and your eventual chargeback labels disagree once they arrive — now what?"* — that disagreement is itself valuable data: recalibrate the proxy's correlation with the real label going forward, and treat any period where they disagreed as needing manual review rather than trusting either blindly.

### Q12 — At staff/principal level: how do you decide the ROI of adding a new monitoring signal?
**Answer:** Weigh the cost (engineering time to build/maintain, ongoing compute/storage cost, alert-fatigue risk if it's noisy) against the cost of the incident it would have caught, multiplied by how often that incident class actually recurs. A signal that would have caught one incident in company history, at high build cost, is a worse investment than a cheap signal (like a null-rate check) that catches the most common failure mode repeatedly. This is the same cost-to-implement-vs-risk-prevented reasoning used in resilience engineering (see `T21-resilience-catalogue`).
**Follow-up trap:** *"Your team wants to add judge-score monitoring to every one of forty prompt templates. Do you approve it?"* — no, not uniformly; prioritize by request volume and business criticality of each template, because judge calls have real per-call cost, and monitoring a low-traffic internal tool with the same rigor as a customer-facing flow is misallocated spend.

---

## Red flags that fail you

- Describing monitoring as "check the accuracy" with no mention of label latency.
- Proposing a single static threshold for an alert without discussing seasonality or noise.
- Not distinguishing infra monitoring from model-layer monitoring — treating "the endpoint is up" as sufficient.
- No answer for what to do when ground truth is delayed or absent.
- For an LLM system, no mention of token cost or refusal rate as monitored signals.
- Proposing to log 100% of raw prompt/completion text with no PII discussion.
- Treating drift detection as automatically sufficient justification to retrain.
- Building a dashboard answer with no mention of how/when a human actually looks at it.

---

## Cheat card

```
4 LAYERS   infra (secs) → data (secs-min) → model (min-hrs) → business (days-wks)
           each can be green while the layer above is on fire

GROUND TRUTH DELAY   fraud 30-90d · recs weeks · content-mod maybe never
PROXIES (no labels needed)   shadow/challenger agreement > pred/confidence drift
           > cheap proxy label > human sample review > LLM-judge score

ALERT DESIGN   static threshold = pages on seasonality, misses real regression
           fix: seasonality baseline (vs same hour last wk) + rate-of-change
           + multi-signal correlation before paging + burn-rate style urgency

LOGGING    100% cheap metadata (ids, latency, tokens, confidence, version)
           1-10% full payload sample, ALWAYS oversample tail (errors, low-conf)
           PII: redact or don't log raw text; separate tightly-scoped store

LLM-SPECIFIC   token cost/request · refusal rate · hallucination proxies
           (groundedness, self-consistency, judge score) · judge-model pinning

NAMED FAILURE   silent feature truncation → step change in pred. mean,
           null rate stays 0%, infra flat, accuracy flat for label-lag window
           → only layer-3 drift monitoring catches it in real time

DASHBOARD RULE   linked from alert/runbook + shows baseline comparison +
           one screen per model, or it doesn't get looked at

COST EXAMPLE   800→1400 avg input tokens, $3/1M in, 2M req/mo
           = ~$1,800/mo cost drift, invisible in latency
```

## Sources
- [Top LLM Observability Tools in 2026 — Confident AI](https://www.confident-ai.com/knowledge-base/compare/10-llm-observability-tools-to-evaluate-and-monitor-ai-2026) — accessed 2026-08-01
- [15 AI Agent Observability Tools in 2026 — aimultiple](https://aimultiple.com/agentic-monitoring) — accessed 2026-08-01
- [AI LLM Observability & AI Monitoring Complete Guide 2026 — AIpedia](https://en.ai-pedias.com/blog/ai-llm-observability-monitoring-2026) — accessed 2026-08-01
- [Amazon Bedrock service tiers (Standard/Priority/Flex)](https://aws.amazon.com/bedrock/service-tiers/) — accessed 2026-08-01 (used for the version-pinning / refusal-rate discussion of managed model behavior)

## Changelog
- 2026-08-01 — created
