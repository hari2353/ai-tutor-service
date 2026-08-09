# AI/ML: SageMaker, Bedrock, AgentCore, Kendra, Comprehend, Textract

> **Track:** C-AWS AWS Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-ai-ml` · **Tags:** ai, critical

## The 30-second version

"SageMaker" is not one product — Studio (the IDE), Training Jobs, four distinct inference modes (real-time endpoints, Serverless Inference, Async Inference, Batch Transform), Pipelines, JumpStart, Model Registry, and Feature Store are separate services sharing a console, and when someone says "we deployed on SageMaker" you need to ask which piece before agreeing it's the right tool. Bedrock gives API access to foundation models with two billing modes — on-demand per-token, or provisioned throughput at a flat hourly rate per model unit — plus managed Knowledge Bases (RAG), Guardrails (policy/safety), and now AgentCore for production agent infrastructure. The honest build-vs-buy line is arithmetic, not preference: Bedrock/managed APIs win by default because the self-hosting break-even for open-weight models is commonly cited around 100-500 million tokens/month sustained, and only crosses in your favor once GPU utilization is consistently high and DevOps overhead is already amortized. Kendra, OpenSearch, and Bedrock Knowledge Bases solve retrieval at three different levels of managed-ness — Kendra for turnkey enterprise search with built-in relevance tuning, OpenSearch for full control at scale, Bedrock Knowledge Bases for the zero-ops RAG pipeline — and Comprehend/Textract/Transcribe/Rekognition beat hosting your own model whenever the task is a well-defined, high-volume, narrow extraction problem rather than something requiring your own fine-tuning or domain adaptation.

## Why this gets asked

Because "SageMaker vs Bedrock vs self-host" is the single most consequential infra decision an AI engineer makes on AWS, and it's usually made by whoever read a blog post most recently rather than by anyone who did the arithmetic. The interviewer has watched a team either overpay for Bedrock provisioned throughput sitting idle, or underestimate the DevOps hours a self-hosted vLLM fleet actually costs, or reach for SageMaker real-time endpoints for a batch workload that Batch Transform would have run for a fraction of the price. They want evidence of the arithmetic, not brand loyalty to one service.

---

## Lineage: past → present → future

**What came before.** Before SageMaker (launched 2017), ML on AWS meant hand-provisioning EC2 GPU instances, writing your own training loops and checkpointing, and building bespoke serving infrastructure — every team reinvented the same undifferentiated plumbing (distributed training orchestration, endpoint autoscaling, model versioning) with no shared tooling. SageMaker's original pitch was consolidating that plumbing into managed primitives. Bedrock (GA 2023) answered a different, later problem: foundation models got good enough that most teams no longer wanted to train or even fine-tune from scratch, they wanted API access to someone else's frontier model with enterprise guardrails around it — a fundamentally different value proposition from SageMaker's "manage my own training/serving infrastructure" model.

**Where it stands now.** The two platforms have genuinely different jobs and the industry still conflates them in interviews: SageMaker is the right layer when you're training, fine-tuning, or serving a model you control (your own architecture, a fine-tuned open-weight model, a classical ML model); Bedrock is the right layer when you want a frontier or curated foundation model behind an API with minimal operational surface. The live disagreement is where the crossover point sits for **self-hosting vLLM on EC2/EKS** versus either managed option — cost analyses cited in 2026 place the self-hosting break-even anywhere from roughly 11 billion tokens/month at the aggressive end down to 100-256 million tokens/month against frontier-model pricing at the conservative end, and the honest answer is "it depends heavily on your utilization assumption and whether you're counting engineer-hours," not a single number [Self-Hosted LLM vs API — Braincuber](https://www.braincuber.com/blog/self-hosted-llms-vs-api-based-llms-cost-performance-analysis) — accessed 2026-08-01, [Managed vs Self-Hosted AI — Inworld](https://inworld.ai/resources/managed-vs-self-hosted-ai) — accessed 2026-08-01. AgentCore (GA June 2026) is AWS's answer to the fact that Bedrock Agents alone weren't enough production infrastructure for real agentic workloads — it adds runtime isolation (microVM per session), identity, memory, and observability as first-class primitives rather than something every team bolts on themselves [AgentCore new features — AWS](https://aws.amazon.com/about-aws/whats-new/2026/04/agentcore-new-features-to-build-agents-faster/) — accessed 2026-08-01.

**Where it's heading.** This is the most volatile module in this batch and every specific number here should be treated as a snapshot, not a constant. Directionally, with moderate-to-high confidence: managed agent infrastructure (AgentCore, and its equivalents on other clouds) is absorbing more of what used to be bespoke LangGraph/custom-orchestration code, and provisioned-throughput and reserved-capacity pricing models are proliferating as usage matures past pure experimentation. With lower confidence: the self-hosting break-even point is likely to keep shifting downward as open-weight model quality closes the gap with frontier APIs and inference-optimized hardware (Inferentia/Trainium, and cheaper H100/H200/B200 access) gets cheaper per token — but this is a moving target that should be re-verified at time of interview, not assumed from this module.

---

## Mental model

```
                          "SageMaker" is EIGHT+ different products
  ┌──────────────────────────────────────────────────────────────────┐
  │  Studio        the IDE / notebook environment                    │
  │  Training Jobs managed distributed training, you control the code│
  │  Pipelines     orchestrates the above into a repeatable DAG      │
  │  Model Registry versioned model artifacts + approval workflow    │
  │  Feature Store  online/offline feature serving                   │
  │  JumpStart     pre-trained model zoo, one-click fine-tune/deploy │
  │  ── inference: pick ONE based on latency + traffic shape ──      │
  │  Real-time Endpoint    persistent, <100ms-class, pay per instance-hr
  │  Serverless Inference  scales to zero, cold start, pay per invoke
  │  Async Inference       queued, up to 1GB payload, up to 1hr runtime
  │  Batch Transform       offline, whole dataset, no endpoint at all
  └──────────────────────────────────────────────────────────────────┘

                    BEDROCK = API access, not infrastructure you run
  ┌──────────────────────────────────────────────────────────────────┐
  │  Model access (Claude, Nova, Llama, Mistral, ...) on-demand/token │
  │  Provisioned Throughput  flat $/hr per model unit, for sustained  │
  │                          volume where on-demand token cost > flat│
  │  Knowledge Bases  managed RAG (chunk, embed, retrieve, cite)      │
  │  Guardrails       content filters, denied topics, PII, grounding │
  │  Agents / AgentCore  orchestration + production runtime/identity │
  └──────────────────────────────────────────────────────────────────┘

  BUILD VS BUY, roughly:
  low/spiky volume ──▶ Bedrock on-demand (simplest, no idle cost)
  medium, steady volume ──▶ SageMaker endpoint (autoscaling, own model) OR
                             Bedrock provisioned throughput (own commitment math)
  very high sustained volume, GPU util >60% ──▶ self-hosted vLLM on EC2/EKS
```

---

## How it actually works

### SageMaker's inference modes, precisely

| Mode | Payload limit | Max processing time | Scales to zero | Use when |
|---|---|---|---|---|
| Real-time endpoint | 25 MB | 60s (regular), up to 8 min (streaming) | No — persistent instance, billed per instance-hour | Steady traffic, low-latency requirement, need to keep GPU warm |
| Serverless Inference | 4 MB | 60s | Yes | Intermittent/unpredictable traffic, tolerant of cold start |
| Async Inference | 1 GB | Up to 1 hour | Yes (scales down to zero when queue empty) | Large payloads (documents, video, batched requests), no strict latency SLA |
| Batch Transform | No endpoint at all — processes a dataset directly from S3 | Bounded by job, not per-request | N/A — provisions and tears down for the job | Offline scoring over a whole dataset, no online serving need |

[SageMaker inference options — AWS docs](https://docs.aws.amazon.com/sagemaker/latest/dg/deploy-model-options.html) — accessed 2026-08-01. The mistake this table exists to prevent: standing up a real-time endpoint (paying per instance-hour, 24/7) for a workload that's actually a nightly batch job, or reaching for Async Inference when payloads are small and latency actually matters (Async's queuing model adds latency real-time doesn't have). When someone says "we're serving with SageMaker," the first question is which of these four they mean — the cost and latency characteristics are not interchangeable.

**Model Registry, Pipelines, Feature Store, JumpStart** round out the platform: Model Registry versions trained artifacts with an approval workflow before promotion to an endpoint; Pipelines is SageMaker's own DAG orchestrator for chaining preprocessing → training → evaluation → registration steps reproducibly; Feature Store gives you an online (low-latency lookup) and offline (bulk training-time) store for the same feature definitions, solving the classic training/serving skew problem; JumpStart is a curated model zoo (Llama, Mistral, and others) with one-click fine-tune-and-deploy onto any of the four inference modes above.

### Bedrock: on-demand vs provisioned throughput

On-demand pricing is pure pay-per-token, no commitment, and ranges widely by model tier — cited 2026 figures span roughly $0.035/million input tokens for the smallest models up to double-digit dollars per million for frontier-tier models, with mid-tier models commonly in the low single digits per million input tokens [Amazon Bedrock pricing 2026 — CloudZero](https://www.cloudzero.com/blog/amazon-bedrock-pricing/) — accessed 2026-08-01. **Provisioned Throughput** commits to a flat hourly rate per **model unit** (a fixed amount of tokens/second capacity), cited in the roughly $20-50/hour range per unit for a one-month commitment depending on model, and running that unit 24/7 for a month is a five-figure-plus commitment regardless of whether it's fully utilized [Bedrock Pricing Explained — nOps](https://www.nops.io/blog/amazon-bedrock-pricing/) — accessed 2026-08-01. The decision rule is genuinely simple arithmetic: estimate sustained tokens/second, compute the on-demand cost at that sustained rate, and compare to the flat provisioned-throughput hourly rate — **provisioned wins only when sustained throughput cost under on-demand would exceed the flat rate**, which in practice means high, steady, predictable traffic. Bursty or low-volume traffic loses under provisioned because idle model-unit-hours still bill in full.

Provisioned throughput is also **required**, not optional, for invoking a custom fine-tuned model on Bedrock — you cannot serve a fine-tuned model on-demand.

### AgentCore

AgentCore (GA June 2026) is AWS's production runtime for agents, separate from the earlier low-code Bedrock Agents builder — it provides session-isolated microVMs, filesystem persistence so an agent can suspend mid-task and resume exactly where it left off, identity/auth wiring for tool access, memory, and an evaluation/observability layer, plus a "managed harness" preview mode where you specify a model, system prompt, and tools and AgentCore runs the full reasoning-tool-selection-action loop without you writing orchestration code [Get to your first working agent — AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/get-to-your-first-working-agent-in-minutes-announcing-new-features-in-amazon-bedrock-agentcore/) — accessed 2026-08-01. As of mid-2026, default runtime quotas support up to 5,000 concurrent sessions in us-east-1/us-west-2 (2,500 elsewhere), 200 agent interactions/second, and 25 new sessions/second [AgentCore runtime quota limits — AWS](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-bedrock-agentcore-increases-default-runtime-quota-limits/) — accessed 2026-08-01. The deep comparison of AgentCore against a self-built LangGraph-on-EKS or custom orchestration stack — where AgentCore's managed isolation genuinely earns its complexity versus where it's overhead for a simpler agent — is in `T09-bedrock-vs-sagemaker`; treat this module as the atlas-level orientation, not the full build-vs-buy breakdown.

### The honest build-vs-buy arithmetic: Bedrock vs SageMaker endpoint vs self-hosted vLLM

Three cost structures, not three quality tiers — the model quality question (frontier API vs open-weight) is separate from the hosting question and gets conflated constantly:

- **Bedrock (managed API)**: pay per token, zero infrastructure ops, model selection limited to what's offered. Wins at low-to-medium, spiky volume where idle capacity would otherwise be wasted, and whenever engineering time is the scarcer resource.
- **SageMaker real-time endpoint (self-managed model, managed infra)**: pay per instance-hour for GPU capacity you size and autoscale yourself, running your own (often open-weight, possibly fine-tuned) model with something like vLLM as the serving engine on the instance. A concrete cited comparison: at roughly 40M tokens/day against a frontier API (~$3/M input tokens), the API bill runs about $12,000/month, versus roughly $2,200/month for two `ml.g5.2xlarge` instances running an equivalent open-weight model — a real gap, but one that assumes the open-weight model is actually good enough for the task and that the team can operate vLLM-on-SageMaker reliably [LLM inference deployment cost comparison — Medium](https://medium.com/@yashwanths_29644/llm-series-06-aws-bedrock-vs-3bb3a8aa2af8) — accessed 2026-08-01.
- **Self-hosted vLLM on raw EC2/EKS**: lowest marginal per-token cost at true scale, but the full cost stack includes 24/7 GPU instance cost regardless of utilization, and a widely-cited estimate of 10-20 engineer-hours/month minimum for maintenance, monitoring, and incident response at $75-150/hour — an additional $750-3,000/month in labor before counting any incident [LLM Hosting Cost 2026 — AI Superior](https://aisuperior.com/llm-hosting-cost/) — accessed 2026-08-01. This is the line item that "self-hosting is cheaper" analyses done purely on GPU-hour arithmetic routinely omit.

The arithmetic in one line: **estimate your actual sustained tokens/month, price it under Bedrock on-demand, price it under a right-sized SageMaker/EC2 GPU fleet including a realistic ops-labor line item, and compare.** Cited break-even ranges for self-hosting vary by an order of magnitude across sources (roughly 100M to 11B tokens/month) depending on what's included in the comparison and which frontier model is the baseline — this is exactly the kind of number to re-verify at interview time rather than quote from memory, and exactly why this module defers the full framework to `T09-bedrock-vs-sagemaker`.

### Kendra vs OpenSearch vs Bedrock Knowledge Bases for retrieval

| | Kendra (GenAI Enterprise Edition) | OpenSearch | Bedrock Knowledge Bases |
|---|---|---|---|
| Managed-ness | Turnkey — built-in NLU ranking, hybrid keyword+semantic, reranking | You own index design, sharding, tuning | Fully managed — chunking, embedding, sync, retrieval handled for you |
| Pricing shape | ~$0.32/hour base unit (1 storage + 1 query unit), covering up to 20,000 docs / 200MB extracted text and ~0.1 QPS; connectors add ~$30/connected index/month with up to 500 sync hours [Kendra GenAI Enterprise pricing — Oreate AI](https://www.oreateai.com/blog/demystifying-amazon-kendra-pricing-what-you-need-to-know/5af6ad622c3dae60baa737dd780ff6ec) — accessed 2026-08-01 | Cluster/OCU-hour based, scales with data and query volume | Backend-dependent (pay for whichever vector store it uses underneath — OpenSearch Serverless, Aurora pgvector, S3 Vectors, or supported third parties) |
| Best fit | Standalone enterprise search UX, rich pre-built connectors (SharePoint, Confluence, S3, etc.), fine-grained access control out of the box | Production RAG needing custom index configuration, hybrid search, or horizontal scale control; also doubles as your logs/search infra | Zero-ops teams who want the RAG pipeline (chunk/embed/retrieve/cite) without owning index infrastructure at all |

[Comparing RAG on AWS — Abhishek Reddy](https://abhishek-reddy.medium.com/comparison-of-rag-implementations-on-aws-bedrock-knowledge-bases-vs-19c2995dc12d) — accessed 2026-08-01. Choose Kendra when the actual product is a search experience for humans with access control and connector needs; choose Bedrock Knowledge Bases when the goal is "feed an LLM good context with minimal ops"; choose direct OpenSearch when you need retrieval-quality control (custom chunking strategy, hybrid scoring tuning, reranking model choice) that the managed options abstract away.

### Comprehend, Textract, Transcribe, Rekognition — when the managed API wins

Rekognition: ~$0.001/image for basic label detection. Transcribe: ~$0.024/minute of audio. Textract's pricing swings enormously by API called on the *same page* — raw text detection is roughly $1.50/1,000 pages, `AnalyzeExpense` (invoices) roughly $10/1,000 pages, and full forms+tables+queries analysis roughly $70/1,000 pages — a 47x spread depending on which call you make on identical input [AWS Textract Pricing 2026 — Braincuber](https://www.braincuber.com/blog/aws-textract-pricing-what-ocr-actually-costs) — accessed 2026-08-01. Comprehend covers sentiment, entity recognition, key-phrase extraction, PII detection/redaction, and topic modeling, with custom classification available for domain-specific categories without training your own model from scratch.

The honest "managed API beats self-hosting" line: for narrow, well-defined extraction tasks (OCR, transcription, standard entity/sentiment classification, standard object/face detection) at moderate volume, the managed API almost always wins — no training data collection, no model maintenance, no drift monitoring, and the per-call cost is trivial relative to engineering time until volume gets very large. It loses when the task needs **domain-specific accuracy a generic model can't hit** (specialized medical/legal document layouts Textract's generic forms model handles poorly, industry-specific entity types Comprehend's standard entity list doesn't cover), where a fine-tuned model or Comprehend Custom/Textract Custom Queries closes some but not all of that gap, or at the very high end where sustained volume shifts the arithmetic the same way it does for LLM hosting.

**Azure/GCP equivalent.** SageMaker → Azure ML (roughly comparable breadth) / Vertex AI (GCP, similarly broad). Bedrock → Azure OpenAI / AI Foundry / Vertex AI-Gemini API. Bedrock Agents/AgentCore → AI Foundry Agents (Azure) / Agent Builder/ADK (GCP). Bedrock Knowledge Bases/Kendra → AI Search + Foundry (Azure) / Vertex AI Search (GCP). Textract → Document Intelligence (Azure) / Document AI (GCP). Transcribe → Azure Speech / Speech-to-Text (GCP). See `clouds/CROSS-CLOUD-MAP.md`.

---

## Build it from scratch

Minimal Bedrock on-demand vs provisioned-throughput break-even calculation — the arithmetic to do out loud when this question comes up:

```python
# untested sketch
def bedrock_cost_comparison(
    tokens_per_month: float,
    on_demand_price_per_million: float,   # e.g. 3.0 for $3/M input tokens
    provisioned_hourly_rate: float,       # e.g. 30.0 per model unit-hour
    hours_per_month: float = 730,
) -> dict:
    on_demand_cost = (tokens_per_month / 1_000_000) * on_demand_price_per_million
    provisioned_cost = provisioned_hourly_rate * hours_per_month
    return {
        "on_demand_monthly": round(on_demand_cost, 2),
        "provisioned_monthly": round(provisioned_cost, 2),
        "provisioned_wins": provisioned_cost < on_demand_cost,
    }

# 200M tokens/month at $3/M on-demand vs one model unit at $30/hr:
print(bedrock_cost_comparison(200_000_000, 3.0, 30.0))
# on_demand: $600.00, provisioned: $21,900.00 -> on-demand wins hard at this volume
# Provisioned only makes sense once sustained throughput needs FAR more than
# one model unit's capacity can serve on-demand-equivalently -- this is a
# capacity-planning decision as much as a cost one, not pure arbitrage.
```

Minimal SageMaker inference-mode selector, the kind of decision function worth sketching on a whiteboard:

```python
# untested sketch
def choose_inference_mode(payload_mb: float, p99_latency_budget_s: float,
                           traffic_pattern: str, max_runtime_s: float) -> str:
    if traffic_pattern == "batch_offline":
        return "Batch Transform"
    if payload_mb > 4 or max_runtime_s > 60:
        return "Async Inference"
    if traffic_pattern == "intermittent" and p99_latency_budget_s > 5:
        return "Serverless Inference"   # accepts cold-start risk
    return "Real-time Endpoint"
```

---

## How it's done in production

| Concern | Tool | What it adds |
|---|---|---|
| Fine-tuning + serving your own model | SageMaker (Training Jobs + JumpStart + real-time endpoint) | Full control over model, framework, and serving engine (e.g. vLLM on the endpoint container) |
| API access to frontier/curated models | Bedrock on-demand or provisioned throughput | Zero infra ops, model selection across providers, built-in Guardrails |
| Production agent runtime | Bedrock AgentCore | Session isolation (microVM), identity, memory, observability, without building it yourself |
| RAG with minimal ops | Bedrock Knowledge Bases | Managed chunk/embed/retrieve/cite pipeline over a chosen vector backend |
| RAG with retrieval-quality control | Direct OpenSearch (or Aurora pgvector) behind your own retrieval code | Custom chunking, hybrid scoring, reranking model choice |
| High-volume narrow extraction | Comprehend / Textract / Transcribe / Rekognition | No training data, no model maintenance, pay-per-call |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| SageMaker real-time endpoint costs far more than expected for a low-traffic workload | Endpoint provisioned 24/7 for traffic that's actually intermittent/bursty | Switch to Serverless Inference (scales to zero) if cold start is tolerable, or right-size/autoscale the real-time fleet |
| Bedrock provisioned throughput bill is high with low utilization in CloudWatch | Committed to a model unit sized for peak, not sustained, load | Re-run the on-demand-vs-provisioned arithmetic against actual sustained (not peak) throughput; consider on-demand with a caching layer for peak absorption |
| Async Inference job "succeeds" with no output and no visible error | Payload exceeded a limit silently, or the invocation failed inside the container without surfacing to the async completion topic | Check the configured SNS/S3 output path and CloudWatch Logs for the endpoint directly, not just the async API response |
| Self-hosted vLLM fleet cost analysis "proves" it's cheaper, but the migration stalls for months | Ops-labor cost (monitoring, patching, incident response, model updates) wasn't included in the original comparison | Redo the cost model with a realistic engineer-hours line item before committing to the migration |
| Textract output is wildly inaccurate on a specific document type | Wrong API called for the document type (e.g. `DetectDocumentText` on a structured invoice instead of `AnalyzeExpense`, or generic forms analysis on a domain-specific layout) | Match the Textract API to the actual document structure; consider Textract Custom Queries for a recurring specific layout |
| Kendra query relevance is worse than expected despite GenAI Enterprise Edition | Connector sync not covering the right document set, or document metadata/access-control tags not configured to support the relevance signals Kendra uses | Audit connector sync coverage and metadata boosting configuration before assuming the model is the problem |
| AgentCore session unexpectedly loses state mid-task | Filesystem persistence not enabled/configured, or the session hit a concurrency or rate quota and was throttled/evicted | Enable filesystem persistence for resumability; check account-level AgentCore quota against actual concurrent session count |

---

## Tradeoffs & when NOT to use it

- **Don't say "we're using SageMaker" as if it answers the question.** It's eight-plus distinct products; a real-time endpoint, Batch Transform, and a Pipeline are entirely different cost and latency profiles wearing the same brand name.
- **Don't default to Bedrock provisioned throughput "for reliability."** It bills in full whether utilized or not; it only wins the arithmetic at genuinely high, steady, predictable volume — for anything spiky, on-demand with a retry/backoff strategy is usually both cheaper and simpler.
- **Don't self-host an LLM to save money without pricing in engineer-hours.** The commonly-omitted line item (10-20 hours/month minimum for a production self-hosted fleet, at $75-150/hour) routinely erases the naive GPU-hour cost advantage at low-to-medium volume.
- **Don't reach for Kendra when the real need is "feed an LLM context," not "build a search UI for humans."** Bedrock Knowledge Bases is less operational surface for that specific job; Kendra's value is the standalone search experience and connector ecosystem.
- **Don't use a generic Comprehend/Textract call on a domain-specific document or entity set and expect fine-tuned-model accuracy.** The managed APIs are trained on broad, general data; a genuinely specialized extraction task (unusual medical forms, industry-specific entity taxonomies) may need Custom Queries/Custom Classification or, at the extreme, a fine-tuned model.
- **Don't build a custom agent orchestration stack from scratch by default in 2026 if AgentCore's managed runtime covers the actual requirement.** Session isolation, identity, and observability are exactly the undifferentiated infrastructure a managed harness is designed to remove from your plate — but do check whether AgentCore's opinions (microVM-per-session, its specific memory/identity model) actually fit your architecture before committing, since this is genuinely new (GA mid-2026) and the ecosystem is still forming.

---

## Interview questions

### Q1 — Someone says "we deployed our model on SageMaker." What do you ask next, and why does it matter?
**Testing:** whether SageMaker's product sprawl is actually understood.
**Answer:** Which inference mode — real-time endpoint, Serverless, Async, or Batch Transform — because they have completely different cost models (per instance-hour vs per-invocation vs offline job) and latency/payload characteristics (25MB/60s real-time vs 1GB/1hr async). "SageMaker" alone tells you nothing about whether this is a low-latency production path or an overnight batch job.
**Follow-up trap:** *"What if they say 'real-time endpoint' — are you done?"* — no, next question is what's actually running in the container (their own model? a JumpStart model? vLLM serving an open-weight model?) and how it's autoscaled, because "real-time endpoint" still spans a huge range of cost and performance depending on instance type and autoscaling policy.

### Q2 — Walk through the arithmetic for Bedrock on-demand vs provisioned throughput.
**Answer:** Estimate sustained tokens/second (not peak), compute the on-demand monthly cost at the per-million-token rate for that sustained volume, and compare to the flat hourly provisioned-throughput rate times hours in the month. Provisioned wins only when the on-demand cost at sustained volume exceeds the flat rate — which requires genuinely high, steady traffic, because idle provisioned-throughput hours bill in full regardless of use.
**Follow-up trap:** *"Your team's traffic has a predictable daily peak and a quiet overnight period. Does provisioned throughput make sense?"* — probably not for the whole day; a common pattern is on-demand as the default with provisioned throughput reserved only if the daily peak alone is sustained and large enough on its own to individually justify a model unit, or accepting on-demand for the full cycle and optimizing latency with caching/batching instead.

### Q3 — Give the honest build-vs-buy arithmetic for Bedrock vs a self-hosted vLLM fleet.
**Answer:** Self-hosting wins on pure per-token marginal cost only at high, sustained volume with good GPU utilization — cited break-even points in 2026 analyses range roughly from 100M to several billion tokens/month depending on the comparison's assumptions, which is itself the point: this isn't a fixed number, it's a calculation you redo with your actual traffic. Critically, the self-hosting side of the comparison needs a realistic ops-labor line item (commonly cited at 10-20 engineer-hours/month minimum, $750-3,000/month) or it understates true cost.
**Follow-up trap:** *"Your CFO asks for one number. What do you tell them?"* — you tell them there isn't one universal number and you'd need their actual projected token volume, target model, and whether they're staffed to operate GPU infrastructure before giving a real answer — reciting a memorized break-even figure without re-deriving it for the specific case is exactly the mistake this question is designed to catch.

### Q4 — When would you choose SageMaker over Bedrock for serving an LLM?
**Answer:** When you need a specific open-weight or fine-tuned model Bedrock doesn't offer, need control over the serving engine (running vLLM yourself with specific batching/quantization settings), or the workload characteristics (payload size, latency SLA, batch vs real-time) map better to a specific SageMaker inference mode than to Bedrock's API-only model. Bedrock is the right default when the model catalog it offers already covers your need and you want zero infrastructure ownership.
**Follow-up trap:** *"What if you need a fine-tuned Claude/Nova model?"* — Bedrock does support fine-tuning certain models, but invoking a fine-tuned model on Bedrock requires provisioned throughput, not on-demand — so the cost model changes even though you're still technically "using Bedrock."

### Q5 — Explain AgentCore and what specific problem it solves that a hand-rolled LangGraph deployment on EKS doesn't solve for free.
**Answer:** Production agent infrastructure that most hand-rolled deployments end up building themselves anyway: per-session isolation (a microVM per session, so one agent's misbehavior or resource exhaustion can't affect another), identity/auth wiring for tool access enforced at the infrastructure layer rather than in application code, persistent filesystem/memory so an agent can suspend and resume a long-running task, and built-in observability/evaluation. A hand-rolled stack can do all of this, but it's the same undifferentiated infrastructure work every team rebuilds.
**Follow-up trap:** *"Is AgentCore always the right choice over a custom stack, then?"* — no; it's new (GA mid-2026), opinionated about its execution model (session-per-microVM, its specific memory abstraction), and a team with an existing, working LangGraph/custom orchestration investment shouldn't necessarily migrate just because a managed alternative exists — evaluate the actual gap it closes for your specific requirements. This is exactly the deeper comparison `T09-bedrock-vs-sagemaker` covers.

### Q6 — Kendra, OpenSearch, or Bedrock Knowledge Bases for a new internal RAG system with no existing search infrastructure?
**Answer:** Depends on what "the product" actually is. If it's a search UX for employees with access control and pre-built connectors (SharePoint, Confluence, etc.) as a first-class requirement, Kendra. If it's purely "feed an LLM good context" with a team that doesn't want to own index infrastructure, Bedrock Knowledge Bases. If retrieval quality needs custom tuning (specific chunking strategy, hybrid BM25+vector scoring, a specific reranker), direct OpenSearch gives the control the managed options abstract away.
**Follow-up trap:** *"The team already runs OpenSearch for application logs. Does that change the answer?"* — yes, meaningfully — adding vector search to existing OpenSearch infrastructure is incremental operational cost on something already staffed and running, which tips the calculus toward direct OpenSearch even if Knowledge Bases would otherwise have been the lower-ops default for a team starting from zero.

### Q7 — Textract cost varies by roughly 47x on the identical page depending on which API you call. Explain why, and how you'd avoid a 47x-inflated bill by accident.
**Answer:** Textract charges per API called, not per page in the abstract — `DetectDocumentText` (raw OCR) is far cheaper than `AnalyzeExpense` or full forms+tables+queries analysis because the latter run substantially more processing (structured field extraction, table detection, query-based extraction). The accidental-inflation risk is calling the expensive general-purpose forms+tables+queries API on documents that only need raw text extraction, often because it was the default example in someone's starter code.
**Follow-up trap:** *"Your bill is dominated by AnalyzeExpense calls on documents that turn out to be plain text memos, not invoices."* — that's exactly the failure mode: audit what API is actually being invoked against what document type, and route by document classification (even a cheap Comprehend custom classifier) before calling the expensive Textract API, rather than calling the most feature-rich API unconditionally.

### Q8 — When does a managed Comprehend/Textract/Transcribe/Rekognition API lose to hosting your own fine-tuned model?
**Answer:** When the task requires domain-specific accuracy the generic model doesn't hit — specialized document layouts, industry-specific entity taxonomies, accented/technical-vocabulary-heavy audio — and volume is high enough to justify the fine-tuning and hosting investment. Custom Queries (Textract) and Custom Classification (Comprehend) close part of this gap without leaving the managed service, which is usually worth trying before committing to a fully self-hosted model.
**Follow-up trap:** *"Give a concrete signal that you've hit this ceiling."* — sustained, unresolvable accuracy issues on a specific, recurring input pattern that Custom Queries/Custom Classification configuration doesn't fix, combined with volume high enough that the fine-tuning and hosting cost is smaller than the cost of the errors (manual review, bad downstream decisions) the generic model is causing.

### Q9 — What's the actual difference between Bedrock Agents and Bedrock AgentCore, and why does AWS have both?
**Answer:** Bedrock Agents is the earlier, lower-code agent-assembly tool — attach a model, a Knowledge Base, an action group backed by Lambda, and a Guardrail, and get an orchestrated agent with relatively little custom code. AgentCore (GA mid-2026) is a separate, more production-oriented runtime layer — session isolation, identity, persistent memory, observability — that can sit underneath agents built with any framework (not just Bedrock Agents), addressing the operational gap between "an agent that works in a demo" and "an agent running in production with real isolation and observability guarantees."
**Follow-up trap:** *"Can you use Bedrock Agents and AgentCore together?"* — the framing AWS uses is that AgentCore is framework-agnostic infrastructure that agents (including ones built with Bedrock Agents, LangGraph, or custom code) can run on top of, rather than Agents and AgentCore being mutually exclusive choices at the same layer.

### Q10 — Design the inference architecture for a document-processing pipeline: PDFs up to 200 pages arrive in bursts, need OCR plus a summarization LLM call, with a same-business-day (not real-time) SLA.
**Answer:** Textract for OCR (matching the API to the actual document structure — likely `AnalyzeDocument` with forms/tables if the PDFs are structured, or plain `DetectDocumentText` if not), landing extracted text in S3, then either SageMaker Async Inference (if using a self-hosted summarization model, given the large payload and no strict latency SLA) or Bedrock on-demand (if using a foundation model for summarization) invoked from a queue-driven worker. Given the "same-business-day" SLA and bursty arrival, no component needs to be provisioned for peak — Async Inference and Bedrock on-demand both handle bursty, non-latency-critical load without paying for idle real-time capacity.
**Follow-up trap:** *"Why not SageMaker real-time endpoint for the summarization step, for simplicity?"* — a real-time endpoint bills per instance-hour whether or not it's processing a document, which is the wrong cost shape for bursty, non-latency-critical traffic; Async Inference or Bedrock on-demand both avoid paying for idle capacity between bursts.

### Q11 — A team's SageMaker Serverless Inference endpoint has unpredictable latency spikes. Diagnose.
**Answer:** Cold starts — Serverless Inference scales to zero when idle, and the next invocation after idle time pays a cold-start penalty to provision capacity before serving, which shows up as latency spikes correlated with traffic gaps rather than with request complexity. If the traffic pattern has enough baseline volume that cold starts are frequent and costly to the user experience, a real-time endpoint (accepting the always-on cost) or Provisioned Concurrency for Serverless Inference (if available for the use case) removes the cold-start variance at the cost of paying for warm capacity.
**Follow-up trap:** *"The traffic is genuinely sparse — a few requests per hour. Is a warm real-time endpoint the right fix?"* — not necessarily; at genuinely sparse volume, paying for a 24/7 real-time endpoint to eliminate occasional cold starts may cost far more than the cold starts themselves are worth in user experience — the right fix depends on how latency-sensitive those sparse requests actually are, not on eliminating cold starts unconditionally.

### Q12 — Why is this module explicitly the most volatile in the AWS Atlas, and what does that mean for how you should use it in an actual interview?
**Testing:** whether the student treats specific numbers as constants or as snapshots.
**Answer:** Foundation model pricing, provisioned-throughput rates, AgentCore's feature set and quotas, and even which models are "frontier" versus "commodity" all change on a timescale of months, not years, in this space — faster than almost anything else in the AWS catalog. The practical implication: use this module for the *mental models* (build-vs-buy arithmetic, the four SageMaker inference modes, the retrieval-tool decision tree) and re-verify any specific number (a price, a quota, a model unit rate) against current docs before quoting it as a hard fact in an interview, rather than memorizing today's snapshot as permanent truth.
**Follow-up trap:** *"So none of the numbers in this module are worth remembering?"* — the *relationships* between numbers are durable (provisioned throughput is a flat rate that beats on-demand only above a sustained-volume threshold; self-hosting has a real, often-omitted labor cost; payload/latency limits differ sharply across SageMaker's four inference modes) even when the specific dollar figures drift — that structural knowledge is what's being tested, not recall of a price that will be stale in six months.

---

## Red flags that fail you

- Treating "SageMaker" as a single product with one cost/latency profile.
- Recommending Bedrock provisioned throughput without doing the sustained-volume-vs-flat-rate arithmetic.
- Citing a self-hosting break-even number with false precision, with no caveat that it depends heavily on utilization and labor assumptions.
- Not knowing that invoking a fine-tuned model on Bedrock requires provisioned throughput.
- Recommending Kendra as the default RAG retrieval layer without asking whether the actual need is a search UX or just LLM context.
- Calling the most feature-rich Textract API unconditionally rather than matching the API to the document structure.
- Presenting AgentCore or any AI/ML pricing/feature claim as a permanent fact rather than a snapshot that needs re-verification.

---

## Cheat card

```
SAGEMAKER = 8+ PRODUCTS, not one thing:
  Studio (IDE) / Training Jobs / Pipelines (DAG) / Model Registry /
  Feature Store (online+offline) / JumpStart (model zoo)
  INFERENCE (pick one):
    Real-time endpoint   25MB payload, 60s (8min streaming), no scale-to-zero
    Serverless Inference 4MB payload, 60s, scales to zero, cold start risk
    Async Inference      1GB payload, up to 1hr, scales to zero, queued
    Batch Transform      no endpoint, offline dataset scoring

BEDROCK
  on-demand: pay per token, no commitment, wins at low/spiky volume
  provisioned throughput: flat $/hr per "model unit", wins only when
    sustained on-demand cost > flat rate -- REQUIRED for fine-tuned models
  Knowledge Bases = managed RAG (chunk/embed/retrieve/cite)
  Guardrails = content filters + denied topics + PII + grounding checks
  AgentCore (GA mid-2026): microVM/session, identity, memory, observability

BUILD VS BUY (verify current numbers before quoting):
  low/spiky volume        -> Bedrock on-demand
  medium/steady, own model -> SageMaker endpoint or Bedrock provisioned
  very high sustained + high GPU util -> self-host vLLM (EC2/EKS)
  SELF-HOST HIDDEN COST: ~10-20 eng-hrs/month ops labor, often omitted

RETRIEVAL
  Kendra: turnkey enterprise search UX, connectors, access control
  OpenSearch: full control, hybrid BM25+vector, horizontal scale
  Bedrock KB: zero-ops managed RAG pipeline over a chosen vector backend

MANAGED APIs
  Rekognition ~$0.001/image · Transcribe ~$0.024/min
  Textract: SAME PAGE, 47x price spread by API called
    (raw text ~$1.5/1k pages -> forms+tables+queries ~$70/1k pages)
  win when: narrow, high-volume, well-defined extraction, no fine-tune need
  lose when: domain-specific accuracy generic model can't hit

VOLATILITY WARNING: every $ figure here is a 2026 snapshot -- re-verify
  before quoting in an interview. The RELATIONSHIPS are durable, the
  NUMBERS are not.
```

## Sources

- [Inference options in Amazon SageMaker AI — AWS docs](https://docs.aws.amazon.com/sagemaker/latest/dg/deploy-model-options.html) — accessed 2026-08-01
- [Choosing between SageMaker AI Inference and Endpoint Type Options — Caylent](https://caylent.com/blog/sagemaker-inference-types) — accessed 2026-08-01
- [Amazon Bedrock pricing in 2026 — CloudZero](https://www.cloudzero.com/blog/amazon-bedrock-pricing/) — accessed 2026-08-01
- [Amazon Bedrock Pricing Explained 2026 — nOps](https://www.nops.io/blog/amazon-bedrock-pricing/) — accessed 2026-08-01
- [Amazon Bedrock AgentCore new features — AWS](https://aws.amazon.com/about-aws/whats-new/2026/04/agentcore-new-features-to-build-agents-faster/) — accessed 2026-08-01
- [Amazon Bedrock AgentCore increases default runtime quota limits — AWS](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-bedrock-agentcore-increases-default-runtime-quota-limits/) — accessed 2026-08-01
- [Get to your first working agent — AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/get-to-your-first-working-agent-in-minutes-announcing-new-features-in-amazon-bedrock-agentcore/) — accessed 2026-08-01
- [Comparison of RAG Implementations on AWS — Abhishek Reddy](https://abhishek-reddy.medium.com/comparison-of-rag-implementations-on-aws-bedrock-knowledge-bases-vs-19c2995dc12d) — accessed 2026-08-01
- [Amazon Kendra Pricing — Oreate AI](https://www.oreateai.com/blog/demystifying-amazon-kendra-pricing-what-you-need-to-know/5af6ad622c3dae60baa737dd780ff6ec) — accessed 2026-08-01
- [AWS Textract Pricing 2026 — Braincuber](https://www.braincuber.com/blog/aws-textract-pricing-what-ocr-actually-costs) — accessed 2026-08-01
- [LLM Series 06: Bedrock vs SageMaker vs EC2 Cost Analysis — Medium](https://medium.com/@yashwanths_29644/llm-series-06-aws-bedrock-vs-3bb3a8aa2af8) — accessed 2026-08-01
- [Self-Hosted LLM vs API: Cost & Performance Analysis — Braincuber](https://www.braincuber.com/blog/self-hosted-llms-vs-api-based-llms-cost-performance-analysis) — accessed 2026-08-01
- [LLM Hosting Cost 2026 — AI Superior](https://aisuperior.com/llm-hosting-cost/) — accessed 2026-08-01

## Unverifiable / needs re-verification at interview time
- Exact Bedrock on-demand/provisioned-throughput dollar figures and specific model names (e.g. "Claude Opus 4.8") are 2026 search-result snapshots that could not be cross-checked against an official, dated AWS pricing page in this pass — treat as illustrative, not authoritative.
- The self-hosting-vs-API break-even token volume varies by roughly an order of magnitude across sources depending on assumptions; no single authoritative figure exists.
- AgentCore feature set and quotas are current as of the cited 2026 AWS "what's new" posts but this is an actively-shipping product; re-check before an interview.

## Changelog
- 2026-08-01 — created
- 2026-08-09 — Claude Opus 5 added to Amazon Bedrock, positioned for stronger agentic-coding and cybersecurity workloads ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-july-27-2026/))
- 2026-08-09 — Amazon Bedrock ships Web Search as a built-in server-side tool for OpenAI models (GPT-5.4/5.5/5.6), grounding responses with zero data egress from the customer's AWS environment — no external search API or vendor review needed ([src](https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-bedrock-web/))
- 2026-08-09 — Amazon Bedrock cuts on-demand GPT-5.6 pricing effective July 30: Luna down 80% (to $0.20/M input, $1.20/M output tokens), Terra down 20% — reshapes the cost-comparison math in any Bedrock-vs-self-host answer ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-price-reduction-of-gpt-models-in-bedrock-cloudwatch-managed-collectors-for-prometheus-metrics-and-more-august-3-2026/))
