# Bedrock vs SageMaker vs Self-Hosted: The Honest Selection Matrix

> **Track:** T09 MLOps / LLMOps · **Time:** 2.0h · **Prereqs:** T08 · **Updated:** 2026-08-01
> **Module id:** `T09-bedrock-vs-sagemaker` · **Tags:** serving,critical

## The 30-second version

Bedrock, SageMaker, and self-hosted vLLM are not three points on one spectrum, they answer three different questions. Bedrock answers "give me an API for a foundation model with zero infrastructure," priced per-token, with the ceiling being whatever models AWS has onboarded and whatever quota they'll grant you. SageMaker isn't one thing — "SageMaker" in an interview almost always means Real-Time Endpoints (always-on, sub-second latency, billed per instance-hour regardless of utilization), but it also covers Serverless Inference (scale-to-zero, cold starts, billed per invocation), Async Inference (queued, up to 1GB payload and an hour of processing, scales to zero), and Batch Transform (offline, no persistent endpoint) — and which one someone means changes the entire cost and latency conversation. Self-hosting vLLM on EC2/EKS wins on raw per-token cost once request volume is high and steady enough to keep GPUs busy, because you're paying for idle capacity either way — the question is whether your utilization is high enough that idle capacity is cheap relative to Bedrock's per-token markup. The honest crossover, deployment-dependent but directionally real: below roughly 10-20K requests/day or a few thousand dollars a month in API spend, Bedrock's zero-infrastructure-overhead is very hard to beat on total cost of ownership once you count the engineer-hours of running GPU infrastructure; above that, and especially with steady, predictable traffic that lets you keep utilization high, self-hosting starts winning on unit economics, and by the time you're spending tens of thousands a month on a hosted API for a workload with stable traffic, running your own vLLM fleet is very likely cheaper, at the cost of owning capacity planning, scaling, and on-call.

## Why this gets asked

The interviewer has either been on the team that shipped a Bedrock integration and then got a $40K/month bill six months later because nobody ran the arithmetic on request volume, or has been on the team that spent two quarters building SageMaker infrastructure for a workload that would have fit in Bedrock's on-demand tier for a fraction of the engineering cost. They want to know if you can reason about the actual axes — not "which is more scalable" as an abstract claim, but latency, quota, data residency, cost model, and lock-in as concrete tradeoffs with numbers attached. At staff/principal level, they're testing whether you'll say "self-host" or "use the managed service" as a reflex, versus doing the arithmetic for the specific workload in front of you.

---

## Lineage: past → present → future

**What came before.** Before managed LLM APIs, "deploying a model" meant provisioning your own GPU instances, writing your own serving loop, and hand-rolling batching — which is exactly what SageMaker's Real-Time Endpoints (GA 2017, well before the LLM era) were built to abstract for classical ML: pick an instance type, point at a model artifact in S3, get an autoscaling HTTPS endpoint. This solved the "I don't want to manage raw EC2 and a load balancer" problem for structured/tabular and small deep-learning models years before anyone needed to serve a 70B-parameter transformer. Bedrock (GA 2023) arrived to solve a different, newer problem: teams didn't want to manage *model weights* at all, let alone infrastructure — they wanted foundation-model capability as an API call, the way they'd consume any other cloud service, without picking an instance type or thinking about batching, quantization, or KV cache sizing.

**Where it stands now.** The three options now map cleanly to three different organizational postures, and the live disagreement is really about where the line sits, not whether the categories are real. Bedrock: no model customization beyond prompting, RAG, and (increasingly) fine-tuning of a limited set of models; pricing per-token on-demand, with provisioned throughput as an option once volume or latency guarantees justify a commitment; tiered service levels (Standard, Priority for lower latency at a premium, Flex for discounted-but-delayed processing) as of 2026 [Amazon Bedrock Service Tiers](https://aws.amazon.com/bedrock/service-tiers/) — accessed 2026-08-01. SageMaker: full control over the model artifact and serving stack (including self-managed open-weight models via vLLM/TGI containers on SageMaker endpoints, or JumpStart's pre-packaged model zoo), at the cost of owning instance selection, autoscaling policy, and patching. Self-hosted (EC2/EKS running vLLM directly, no SageMaker layer at all): maximum control and, at sufficient scale, the best unit economics, at the cost of owning everything SageMaker would otherwise manage — health checks, autoscaling, deployment orchestration — yourself. The genuinely live disagreement in the field is exactly where the crossover point sits, because it depends heavily on token-length distribution, latency SLA, and whether traffic is steady enough to keep self-hosted GPUs busy; vendors publish comparisons that favor whichever side they're selling, and independent, apples-to-apples benchmarks are scarce.

**Where it's heading.** High confidence: Bedrock's provisioned-throughput and tiered-pricing options keep expanding, because AWS's own incentive is to capture workloads that would otherwise churn to self-hosting once they hit meaningful scale — Priority/Flex tiers are a direct response to "we need Bedrock's convenience but our traffic has different latency tolerance at different times." Medium confidence: the self-hosting arithmetic keeps improving in favor of self-hosting as open-weight model quality closes the gap with frontier hosted models and as serving engines (vLLM, SGLang) continue to push GPU utilization higher — the crossover point trends downward (self-hosting becomes attractive at lower volumes) as long as this trend continues. Speculative: unified abstraction layers (Bedrock's own multi-model routing, or third-party gateways like LiteLLM) that let a team defer the Bedrock-vs-self-hosted decision by routing dynamically based on cost/latency/load, treating it as a runtime decision rather than an architectural commitment made once at design time.

---

## Mental model

```
                     BEDROCK              SAGEMAKER               SELF-HOSTED
                                          (Real-Time Endpoint)    (EC2/EKS + vLLM)
 ─────────────────────────────────────────────────────────────────────────────────
 You manage         nothing              instance type,          everything:
                     (prompt only)        autoscaling policy,     provisioning,
                                          container image          autoscaling,
                                                                   health checks,
                                                                   upgrades, on-call

 Model choice        AWS's onboarded      any model you can       any open-weight
                     model catalog        package into a          model you can
                                          container                run

 Pricing unit        per input/output     per instance-hour       per instance-hour
                     token                (endpoint always on,    (yours, no AWS
                                          regardless of load)     markup, but idle
                                                                   time is still paid)

 Cold start          none (always warm    none for real-time;     none if kept warm;
                     behind the API)      serverless variant      yours to manage
                                          has 1-5s cold starts

 Customization       prompting, RAG,      full fine-tuning,       full fine-tuning,
                     limited fine-tune    custom architectures,   custom architectures,
                     on some models       arbitrary containers    arbitrary containers,
                                                                   arbitrary serving
                                                                   engine/config

 Lock-in             high (AWS's model    medium (AWS's infra,    low (portable
                     catalog + API)       your model/container)   containers, but
                                                                   ops burden is yours)
```

The one-sentence framing that survives an interview: **Bedrock buys you zero ops at the cost of per-token markup and a fixed model catalog; SageMaker buys you AWS-managed infrastructure around a model you fully control; self-hosting buys you the best unit economics at real scale, in exchange for owning every operational concern SageMaker or Bedrock would otherwise absorb.**

---

## How it actually works

### SageMaker is four different products wearing one name

This is the single most common confusion in interviews — "SageMaker" said without qualification usually means Real-Time Endpoints, but the platform actually spans four distinct inference products with very different cost and latency profiles:

| Product | Latency | Billing | Best for |
|---|---|---|---|
| **Real-Time Endpoints** | Sub-second, always warm | Per instance-hour, regardless of utilization | Steady, latency-sensitive traffic |
| **Serverless Inference** | 1-5s cold start when scaling from zero, sub-second warm | Per invocation + compute duration, scales to zero | Intermittent/unpredictable traffic, dev/test, low-volume production endpoints |
| **Async Inference** | Near-real-time, queued (not synchronous) | Per instance-hour while processing, scales to zero when idle | Large payloads (up to 1GB) or long processing times (up to one hour) that don't fit a synchronous request/response model |
| **Batch Transform** | Offline, no live endpoint at all | Per instance-hour for the duration of the job | Large, scheduled, non-interactive scoring jobs (a nightly re-scoring of a full customer base) |

**JumpStart** is not a fifth inference product; it's a model zoo/deployment accelerator that pre-packages open models (Llama, Mistral, and others) for one-click or one-API-call deployment onto one of the four options above — "I'll use JumpStart" means "I'm deploying a pre-packaged model," not a distinct serving mode. Knowing this distinction cold, and using it precisely, is a real interview signal because so many candidates conflate "SageMaker" with just the first row.

### Bedrock: on-demand, provisioned throughput, and service tiers

**On-demand** is pay-per-token with no commitment. As of Bedrock's public pricing page, Claude Sonnet 5's promotional launch pricing is $2/$10 per million input/output tokens through August 31, 2026, reverting to standard $3/$15 per million tokens after that date; Claude 3.5 Sonnet (now under "Public Extended Access" as older models roll to a legacy tier) is priced at $6/$30 per million input/output tokens [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) — accessed 2026-08-01. **Batch inference** on Bedrock gets a 50% discount versus on-demand for the same model, for workloads that can tolerate asynchronous, non-interactive processing — directly analogous to SageMaker Batch Transform's economics, but for foundation models via the Bedrock API.

**Provisioned throughput** reserves dedicated capacity (measured in "model units") for a 1-month or 6-month commitment, trading a fixed hourly cost for guaranteed throughput independent of Bedrock's shared on-demand capacity pool. AWS does not publish provisioned-throughput rates on the standard public pricing page for most models — the page directs enterprise customers to their account team for a quote — so treat any specific per-model-unit dollar figure you see quoted (blog posts commonly cite a $21-63/hour range) as a secondary-source estimate, not an AWS-published number, and always confirm current rates directly with AWS or your account team before using a specific figure in a real cost model.

**Service tiers**, layered on top of either pricing model: **Standard** (baseline, consistent performance), **Priority** (up to ~25% better output-tokens-per-second latency, at a rate premium over Standard, for latency-sensitive workloads), **Flex** (discounted vs Standard rate, for workloads that can tolerate being queued behind Standard-tier traffic during high load, aimed at batch-like or non-urgent multi-step workflows) [Amazon Bedrock Service Tiers](https://aws.amazon.com/bedrock/service-tiers/) — accessed 2026-08-01.

**Quotas** are enforced per model, typically as requests-per-minute and tokens-per-minute limits on the on-demand tier, with increases available via a support-ticket request subject to AWS capacity — this is a real operational constraint: a traffic spike that exceeds your provisioned quota on Bedrock fails closed (throttled requests) rather than autoscaling the way a self-managed fleet with headroom would, unless you've proactively requested and been granted a higher quota.

### The arithmetic: self-hosting vLLM, worked through

The comparison is not "token price vs GPU price" in isolation, it's **utilization-adjusted cost per token** versus **Bedrock's fully-loaded per-token price** (which already has AWS's margin and shared-fleet efficiency baked in).

Concrete EC2 reference points, current on-demand hourly rates: `g5.2xlarge` (1x A10G, 24GB) around $1.21/hr, `p4d.24xlarge` (8x A100 40GB) around $32.77/hr, `p5.48xlarge` (8x H100) around $98.32/hr [g5.2xlarge — Vantage](https://instances.vantage.sh/aws/ec2/g5.2xlarge) — accessed 2026-08-01. Running vLLM on a single `g5.2xlarge` serving a Llama-class 8B model at, say, 40 requests/minute sustained with continuous batching, the instance cost is fixed at ~$1.21/hr regardless of whether you're using 10% or 95% of its throughput capacity — which is exactly the point: **self-hosted cost is a step function in capacity, Bedrock's cost is linear in actual usage.** At low, spiky utilization, you're paying for idle GPU time and losing to Bedrock's linear per-token model. At high, steady utilization approaching the instance's real throughput ceiling, the effective cost per token drops well below Bedrock's on-demand rate because you're amortizing that fixed hourly cost over far more tokens.

**The honest crossover statement:** published estimates place the point where self-hosting starts winning somewhere in the range of 10,000-20,000 requests/day, or equivalently a few thousand dollars a month in hosted-API spend, though this is workload-dependent (heavily influenced by average token length, latency SLA tightness, and how steady versus spiky the traffic is) and should be treated as a directional estimate from industry commentary rather than a number you should quote as precise in front of an interviewer without caveating it as such [AWS Bedrock Pricing vs Self-Hosted LLMs — Spheron](https://www.spheron.network/blog/aws-bedrock-pricing-2026-managed-api-cost/) — accessed 2026-08-01. What is not in dispute: below that range, the engineering time to build and operate GPU serving infrastructure (capacity planning, autoscaling, health checks, model updates, on-call) is itself a real cost that a small workload's savings won't cover; above it, and especially with steady traffic, the unit economics tilt hard toward self-hosting, and by the time monthly hosted-API spend reaches the tens of thousands of dollars for a workload with predictable, steady traffic, a self-hosted fleet sized to that steady-state load is very likely both cheaper and gives you latency control Bedrock's shared capacity pool can't offer.

**What the arithmetic leaves out, and shouldn't:** the fully-loaded cost of self-hosting isn't just the EC2 bill — it's engineer time for capacity planning and on-call, the cost of maintaining vLLM version upgrades and CUDA/driver compatibility, the cost of your own autoscaling logic (or EKS/Karpenter configuration) reacting more slowly to a spike than Bedrock's shared fleet would, and the opportunity cost of the team's attention. A workload that "wins" on raw GPU-hour arithmetic can still be the wrong call for a team without the operational maturity to run GPU fleets reliably — this is the same judgment call as the resilience-catalogue's "not every pattern is worth its implementation cost" (`T21-resilience-catalogue`).

### Data residency and privacy posture

Bedrock and SageMaker both run inside your AWS account's chosen region, and AWS's stated policy is that customer data (prompts, completions, fine-tuning data) is not used to train the underlying foundation models and does not leave the selected region for either service — an important distinction from some third-party hosted APIs. The practical difference between them on this axis is narrower than people expect: Bedrock's isolation properties (no cross-tenant data leakage, regional data residency) generally match SageMaker's, since both are AWS-operated within the customer's account boundary. Self-hosting inside your own VPC is the strictest option operationally, since you additionally control the exact hardware and network path and there's no reliance on AWS's model-hosting layer at all — this matters concretely for regulated workloads (healthcare, finance) where an auditor wants to see the full data path, not just AWS's compliance attestation.

### Operational burden and lock-in, side by side

- **Bedrock**: near-zero operational burden; lock-in is real and specific — your prompts, evaluation harness, and any fine-tuning are built against AWS's model catalog and API surface, and migrating to a different provider means re-validating behavior against a different model family entirely, not just changing an endpoint URL.
- **SageMaker**: moderate operational burden (you own the container and autoscaling config, AWS owns the underlying infrastructure); lock-in is AWS-infrastructure-specific but your model artifact itself is portable — a vLLM container running on a SageMaker endpoint can, with modest effort, run on plain EKS or EC2 instead, because the model and serving engine aren't AWS-proprietary.
- **Self-hosted**: full operational burden; lowest lock-in by far, since the same container and model run on any cloud or on-prem, but "low lock-in" doesn't mean "low cost to move" — it means the *technical* dependency is minimal even though the *organizational* investment in your own ops tooling is real.

---

## Build it from scratch

A minimal cost-comparison calculator — the kind of back-of-envelope arithmetic you should be able to produce live in an interview when asked "would you self-host this."

```python
# untested sketch
def compare_costs(
    requests_per_day: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    bedrock_input_price_per_million: float = 3.0,   # e.g. Claude Sonnet 5 standard rate
    bedrock_output_price_per_million: float = 15.0,
    ec2_hourly_rate: float = 1.21,                    # e.g. g5.2xlarge on-demand
    self_hosted_requests_per_hour_capacity: int = 2400,  # engine- and model-dependent
) -> dict:
    daily_input_tokens = requests_per_day * avg_input_tokens
    daily_output_tokens = requests_per_day * avg_output_tokens

    bedrock_daily_cost = (
        daily_input_tokens / 1_000_000 * bedrock_input_price_per_million
        + daily_output_tokens / 1_000_000 * bedrock_output_price_per_million
    )

    # self-hosted: you pay for instance-hours needed to cover peak-ish sustained
    # throughput, NOT per-token -- this is the step-function vs linear distinction
    hours_needed = max(1, requests_per_day / self_hosted_requests_per_hour_capacity)
    # round up to whole instance-hours across a day; real capacity planning also
    # needs headroom for peak vs average, which this sketch ignores
    self_hosted_daily_cost = min(24, hours_needed) * ec2_hourly_rate * 24 / 24
    self_hosted_daily_cost = 24 * ec2_hourly_rate  # simplification: one instance, always on

    return {
        "bedrock_daily_cost_usd": round(bedrock_daily_cost, 2),
        "self_hosted_daily_cost_usd": round(self_hosted_daily_cost, 2),
        "self_hosted_wins": self_hosted_daily_cost < bedrock_daily_cost,
        "note": "excludes engineer-hours, autoscaling headroom, and multi-instance "
                "capacity planning -- treat as directional only",
    }
```

The value of writing this by hand in an interview isn't the code, it's demonstrating you know the two cost models are structurally different (linear-in-usage vs step-function-in-capacity) before you plug in a single number.

---

## How it's done in production

| Concern | What a real deployment adds over the sketch above |
|---|---|
| **Traffic shape** | Real capacity planning uses peak-to-average ratio, not average requests/day — a workload with a 10x daily peak needs capacity sized to the peak (or autoscaling fast enough to react), which changes the self-hosted cost dramatically versus a flat-average calculation |
| **Multi-model routing** | Gateways (LiteLLM, or Bedrock's own model routing) let you send easy/cheap queries to a smaller self-hosted or cheaper hosted model and hard queries to a frontier hosted model, rather than a single binary choice |
| **Autoscaling on self-hosted** | Karpenter/Cluster Autoscaler on EKS, or SageMaker's built-in autoscaling on Real-Time Endpoints, reacting to queue depth or GPU utilization rather than a fixed instance count |
| **Spot instances** | Self-hosted inference on spot EC2 (or SageMaker with managed spot for training/batch) can cut compute cost substantially versus on-demand, at the cost of interruption handling — check current spot pricing and interruption frequency for your instance type/region before committing capacity planning to it |
| **Provisioned throughput on Bedrock** | Once volume and latency guarantees justify a commitment, provisioned throughput removes on-demand quota risk and can reduce effective per-token cost at sufficient scale, at the cost of a 1- or 6-month commitment |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Bedrock bill grows 5x with no traffic increase | Prompt template regression added context tokens, or a fallback silently upgraded to a pricier model tier (see `T09-model-monitoring`'s cost-per-request tracking) | Monitor token cost per request per prompt-template version; alert on cost drift, not just total spend |
| SageMaker real-time endpoint bill is high despite low traffic | Endpoint billed per instance-hour regardless of utilization; over-provisioned instance count/type for actual load | Right-size instance count/type to observed utilization, or switch to Serverless Inference for intermittent traffic |
| Self-hosted fleet falls over during a traffic spike | Fixed instance count with no autoscaling, or autoscaling reacting slower than the spike | Add queue-depth-based autoscaling with adequate headroom; consider Bedrock/SageMaker Serverless as an overflow path for spikes above self-hosted capacity |
| Bedrock requests throttled during a launch/spike | Default on-demand quota (requests/min or tokens/min) exceeded | Request a quota increase proactively before a known traffic event; quota increases are not instant and depend on AWS capacity |
| Production behavior shifts with no deploy on your side | Pointed at a Bedrock model alias that AWS updated, or a JumpStart model version that rolled forward | Pin explicit model versions where the provider allows it; monitor refusal rate/behavior as a first-class signal (`T09-model-monitoring`) |
| "We're using SageMaker" but nobody can say which product | Real-Time Endpoints, Serverless, Async, and Batch Transform conflated as one thing during planning | Name the specific product explicitly in any design doc or cost estimate; each has a materially different cost and latency profile |
| Self-hosted GPU cost estimate way off from actuals | Calculation used average request rate, ignored peak-to-average ratio and required autoscaling headroom | Recompute against peak sustained load, not daily average, and include headroom margin |

---

## Tradeoffs & when NOT to use it

- **Don't self-host for a low-volume or spiky workload.** Below the volume where GPU utilization stays reasonably high, you're paying for idle capacity that Bedrock's per-token model would have charged you nothing for. The engineering cost of building and operating the fleet often exceeds the savings at this scale.
- **Don't use Bedrock (or any hosted API) for a workload with hard data-residency requirements that specifically prohibit any third-party-operated inference layer, even within your own cloud account** — verify the actual compliance requirement rather than assuming AWS's general attestation satisfies it; some regulated environments require the literal serving process to run on infrastructure the organization directly controls.
- **Don't reach for SageMaker Real-Time Endpoints for a workload that's genuinely intermittent** — you'll pay for an always-on instance serving occasional traffic; Serverless Inference or Async Inference fit that shape far better.
- **Don't commit to Bedrock Provisioned Throughput before validating your traffic pattern on-demand first** — a 1- or 6-month commitment against a workload whose volume assumptions turn out wrong is an expensive mistake; prove out on-demand, then commit once the volume is proven and steady.
- **Don't assume the self-hosting crossover point transfers between workloads.** A crossover computed for one model/token-length/latency-SLA combination doesn't generalize to a different one; redo the arithmetic per workload rather than applying a rule of thumb from a different project.
- **SageMaker is the wrong layer if you don't need AWS-managed infrastructure at all** — if you're already running EKS and comfortable with vLLM directly, SageMaker's abstraction (a container behind an AWS-managed endpoint) adds a layer of AWS-specific configuration and cost without adding capability you don't already have from your own Kubernetes tooling.

---

## Interview questions

### Q1 — Someone says "we're using SageMaker for inference." What do you ask next?
**Testing:** whether the candidate knows SageMaker isn't one product.
**Answer:** Which inference option specifically — Real-Time Endpoints, Serverless Inference, Async Inference, or Batch Transform — because each has a completely different cost model (per instance-hour always-on vs per-invocation vs per-instance-hour-while-processing vs per-job) and latency profile (sub-second always-warm vs cold-start-capable vs queued-near-real-time vs fully offline).
**Follow-up trap:** *"They say 'the real-time one.' Now what?"* — ask about traffic shape (steady or spiky) and current utilization, because Real-Time Endpoints bill per instance-hour regardless of load — a low-utilization Real-Time Endpoint is a strong candidate for switching to Serverless Inference instead.

### Q2 — Walk through the cost-model difference between Bedrock on-demand and self-hosting.
**Answer:** Bedrock on-demand is linear in actual token usage — you pay only for tokens processed, at a fixed per-million-token rate. Self-hosting is a step function in provisioned capacity — you pay for GPU instance-hours regardless of whether you're using 10% or 95% of that capacity's throughput. Below the point where you can keep self-hosted GPUs consistently busy, the linear model wins; above it, the step-function model's effective per-token cost drops below the linear rate.
**Follow-up trap:** *"Give me a specific crossover number."* — there isn't one universal number; direction-of-travel estimates put it around 10-20K requests/day or a few thousand dollars/month in API spend, but it's workload-dependent on token length, latency SLA, and traffic steadiness — state the caveat explicitly rather than quoting a false-precision figure.

### Q3 — What's the difference between Bedrock's Standard, Priority, and Flex service tiers?
**Answer:** Standard is baseline pricing and performance. Priority costs a premium over Standard for preferential queue treatment, delivering up to roughly 25% better output-tokens-per-second latency — for real-time, latency-sensitive workloads. Flex is discounted versus Standard for workloads that can tolerate being queued behind Standard-tier traffic during high load, aimed at batch-like or non-urgent multi-step work.
**Follow-up trap:** *"When would Flex be a bad choice even for a batch-like workload?"* — if the batch job has a hard deadline that could be missed if it gets queued behind heavy Standard-tier traffic during a busy period; Flex trades latency predictability for cost, and a workload with a hard SLA despite being "batch-shaped" shouldn't use it.

### Q4 — Design the inference architecture for a workload doing 500K requests/day with steady, predictable traffic and an internal-only latency SLA of 2 seconds.
**Testing:** whether the candidate does the arithmetic rather than pattern-matching to a reflexive answer.
**Answer:** 500K requests/day with steady traffic is well above typical self-hosting crossover estimates, and a 2-second SLA is loose enough that self-hosted vLLM easily meets it. This is a strong self-hosting candidate: size an EC2/EKS vLLM fleet to steady-state throughput with modest autoscaling headroom for variance, and the unit economics should beat Bedrock on-demand substantially at this volume. Validate with the actual token-length distribution before committing capacity.
**Follow-up trap:** *"What would change your answer?"* — if the traffic were spiky rather than steady (10x peak-to-average), the self-hosted fleet would need to provision for the peak or accept slower autoscaling reaction, eroding the cost advantage; spiky traffic at the same daily total favors a hosted service or a hybrid (self-hosted base load + Bedrock/Serverless overflow).

### Q5 — Your team is on Bedrock and the monthly bill just tripled with no traffic increase. Diagnose it.
**Answer:** Check token counts per request first, not overall spend — a prompt template regression (added context, a RAG pipeline retrieving more/longer chunks) can silently triple average token count with zero change in request volume. Also check whether a fallback path silently upgraded requests to a pricier model tier, and check whether Priority-tier usage crept in without an explicit decision to pay the premium.
**Follow-up trap:** *"Assume token counts are stable. What else?"* — check for a model version change if pointed at an alias rather than a pinned version; some providers price newer model versions differently, and an unpinned alias can silently move you to a pricier model. This connects directly to the model-monitoring cost-per-request-by-template tracking in `T09-model-monitoring`.

### Q6 — When is SageMaker the right choice over both Bedrock and plain self-hosted EC2/EKS?
**Answer:** When you need full control over the model artifact and serving container (a fine-tuned open-weight model, a custom architecture, or a model Bedrock doesn't offer) but don't want to own the underlying infrastructure orchestration (instance provisioning, health checks, autoscaling wiring) that plain EC2/EKS would require you to build yourself. It's the middle ground: your model, AWS's infrastructure management.
**Follow-up trap:** *"Your team already runs EKS comfortably for other services. Does that change the answer?"* — yes; if the team already has mature Kubernetes tooling and on-call practices, SageMaker's abstraction adds AWS-specific configuration surface without adding capability the team doesn't already have, and running the same vLLM container directly on the existing EKS cluster is likely simpler to operate than a second, SageMaker-specific deployment paradigm.

### Q7 — What does "data residency" actually mean differently across these three options?
**Answer:** Bedrock and SageMaker both keep customer data (prompts, completions, fine-tuning data) within the selected AWS region and, per AWS's stated policy, don't use it to train underlying foundation models — the isolation properties are broadly similar between the two since both are AWS-operated within the customer's account boundary. Self-hosting is stricter in a way that matters for some regulated environments: the literal serving process runs on infrastructure the organization directly controls end-to-end, which some compliance regimes require as a hard line rather than accepting a vendor's attestation about a managed service.
**Follow-up trap:** *"A compliance team says 'no third-party processes our data.' Does Bedrock satisfy that?"* — depends entirely on how that requirement is worded and audited; if it means "no vendor-operated compute touches the data even within our own account boundary," Bedrock and SageMaker's managed inference both fail that literal bar and only genuinely self-hosted infrastructure satisfies it. Get the actual compliance requirement in writing before assuming either managed service clears it.

### Q8 — What's Bedrock Provisioned Throughput, and when would you commit to it?
**Answer:** Reserved dedicated capacity (in "model units") for a 1- or 6-month term, guaranteeing throughput independent of the shared on-demand capacity pool, at a fixed hourly rate quoted per model (AWS generally routes enterprise customers to their account team for exact rates rather than publishing them broadly). Commit once you have validated, steady volume and a latency/throughput guarantee that on-demand's shared pool and quota limits can't reliably meet.
**Follow-up trap:** *"Your traffic has grown 3x since you signed a 6-month provisioned throughput commitment, and you're now hitting the ceiling. What do you do?"* — provisioned throughput isn't automatically elastic; you'd need to either purchase additional model units (a new commitment) or overflow excess traffic to on-demand as a burst valve, and should design for that overflow path from the start rather than assuming provisioned capacity alone will scale with growth.

### Q9 — Explain why "self-hosting is always cheaper at scale" is an oversimplification.
**Answer:** The GPU-hour arithmetic alone favors self-hosting at high, steady utilization, but the fully-loaded cost includes engineer time for capacity planning and on-call, the ongoing cost of tracking vLLM/CUDA/driver upgrades, the cost of building autoscaling that reacts as fast as a hosted provider's shared fleet, and the opportunity cost of the team's attention being spent on infrastructure instead of product work. A workload that "wins" on raw compute-hour math can still be the wrong call for a team without the operational maturity to run GPU fleets reliably.
**Follow-up trap:** *"How would you quantify the engineer-time cost to make a fair comparison?"* — estimate ongoing on-call/maintenance burden in engineer-hours/month at a loaded hourly cost and add it to the self-hosted side of the comparison; if that pushes the crossover point higher than the raw GPU-hour math suggested, the workload may not clear the bar after all, and that's a legitimate outcome of doing the full accounting rather than a reason to skip it.

### Q10 — A workload needs a model not available on Bedrock, has high steady volume, and the team has strong Kubernetes experience. Design the serving path and justify skipping both Bedrock and SageMaker.
**Answer:** Self-hosted vLLM on EKS. Bedrock is disqualified outright — the model isn't in its catalog. SageMaker would add an AWS-managed abstraction layer on top of the model's container, but the team's existing Kubernetes maturity means that abstraction isn't buying anything they don't already have; running the same container directly on their existing EKS cluster, with their existing autoscaling/observability tooling, is simpler to operate and avoids introducing a second, SageMaker-specific operational paradigm alongside their existing stack. High steady volume also means the unit economics favor self-hosting over any managed alternative that could serve the model.
**Follow-up trap:** *"What's the one thing you lose by skipping SageMaker here?"* — SageMaker's built-in model-registry and endpoint-versioning/rollback tooling, and its native integration with SageMaker Model Monitor; going fully self-hosted means you need to build or adopt equivalent model-registry (`T09-tracking-registry`) and deployment-rollback (`T09-model-cicd`) tooling yourself rather than getting it for free from the platform.

### Q11 — At staff/principal level: leadership asks whether to migrate an existing Bedrock-based product to self-hosted to cut costs. How do you structure the decision?
**Answer:** Start with actual usage data, not the cost-comparison arithmetic in the abstract: current requests/day, token-length distribution, traffic steadiness (peak-to-average ratio), and current monthly Bedrock spend. Run the utilization-adjusted cost comparison against realistic self-hosted instance sizing including headroom for peaks. Add the fully-loaded operational cost (engineer-hours for on-call, capacity planning, upgrade maintenance) to the self-hosted side. Separately assess migration risk: re-validating model behavior on a different model family (if moving off a proprietary Bedrock model to an open-weight self-hosted one) is a real evaluation project, not just an infrastructure change, and that risk/cost belongs in the decision even when the steady-state economics favor migrating.
**Follow-up trap:** *"Leadership wants a one-page recommendation, not a spreadsheet. What's the headline?"* — state the crossover-relative-to-current-scale finding plainly ("we're at Nx the estimated crossover volume, self-hosting likely saves $Y/month net of ops cost, but requires re-validating model quality against an open-weight alternative, estimated at Z weeks") — the senior signal is being willing to give a plain, numbers-backed recommendation rather than hedging behind "it depends" with no stated conclusion.

### Q12 — What changes about this whole analysis if the "model" in question is proprietary (only available via Bedrock) versus open-weight?
**Answer:** If the model is proprietary and only available via a hosted API, self-hosting isn't on the table at all regardless of the cost arithmetic — the comparison collapses to on-demand vs provisioned throughput vs a different provider entirely. Self-hosting only becomes a real option once an open-weight model of acceptable quality exists for the task, which reframes the decision from "which serving layer" to "is there an open-weight model good enough to replace this proprietary one," a model-quality question that has to be answered before the cost arithmetic in this module is even relevant.
**Follow-up trap:** *"The team is set on self-hosting for cost reasons but the task needs frontier-model reasoning quality no open-weight model currently matches. What do you tell them?"* — the cost analysis is moot if quality requirements can't be met by any self-hostable model; recommend staying on the hosted API and revisit self-hosting as open-weight quality improves, rather than degrading product quality to chase infrastructure savings.

---

## Red flags that fail you

- Saying "SageMaker" without being able to name which of the four inference products is meant.
- Claiming self-hosting is always cheaper at scale with no mention of operational cost or utilization.
- Quoting a specific crossover number (e.g., "10,000 requests/day") as a hard fact rather than a workload-dependent, caveated estimate.
- Treating Bedrock and SageMaker as identical on data residency/privacy with no distinction from self-hosting.
- Not knowing that Real-Time Endpoints bill per instance-hour regardless of utilization.
- Reciting pricing numbers from memory with no acknowledgment that AI/cloud pricing changes and should be verified against current sources.
- No mention of quota limits as a real constraint on Bedrock on-demand usage.
- Recommending a migration to self-hosting without addressing model-quality re-validation risk when models differ.

---

## Cheat card

```
SAGEMAKER IS 4 PRODUCTS, NOT 1
  Real-Time Endpoint   always-on, sub-sec, $/instance-hr regardless of load
  Serverless Inference scale-to-zero, 1-5s cold start, $/invocation
  Async Inference      queued, up to 1GB payload / 1hr processing, scales to zero
  Batch Transform      offline job, no live endpoint, $/instance-hr for job duration
  JumpStart = model zoo/deploy accelerator, NOT a 5th inference product

BEDROCK PRICING (verify current — changes often)
  on-demand: per-token, e.g. Claude Sonnet 5 promo $2/$10 per 1M in/out
             thru Aug 31 2026, then $3/$15 standard (per AWS pricing page)
  batch: ~50% discount vs on-demand for async-tolerant workloads
  provisioned throughput: $/model-unit/hr, 1mo or 6mo commit, rates often
             quote-only via account team — don't cite a figure from memory
  tiers: Standard (baseline) / Priority (~25% better OTPS, premium)
         / Flex (discounted, queued behind Standard under load)
  quotas: RPM/TPM per model, on-demand; increase = support ticket, not instant

SELF-HOSTED ARITHMETIC
  cost model: LINEAR (Bedrock, per token) vs STEP FUNCTION (self-host, per instance-hr)
  EC2 refs (verify current): g5.2xlarge ~$1.21/hr · p4d.24xlarge ~$32.77/hr
             p5.48xlarge ~$98.32/hr (on-demand)
  crossover: directional estimate ~10-20K req/day or ~$mid-4-figures/mo spend
             — workload-dependent, caveat explicitly, don't quote as precise
  fully-loaded self-host cost = GPU-hours + eng on-call/upgrade time,
             NOT just the EC2 bill

DATA RESIDENCY   Bedrock ≈ SageMaker (both AWS-managed, in-region, no training
             on customer data per AWS policy) · self-host = strictest,
             only option if "no vendor compute touches data" is a hard requirement

LOCK-IN      Bedrock: high (model catalog + API) · SageMaker: medium (AWS infra,
             portable container) · self-host: low technical, high ops investment

DECISION RULE   model only on Bedrock → Bedrock, no choice
             low/spiky volume → Bedrock on-demand
             need custom model + want AWS-managed ops → SageMaker
             high steady volume + team has K8s maturity → self-host
             always re-run the arithmetic per workload, never reuse a prior crossover
```

## Sources
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) — accessed 2026-08-01
- [Amazon Bedrock Service Tiers](https://aws.amazon.com/bedrock/service-tiers/) — accessed 2026-08-01
- [g5.2xlarge pricing and specs — Vantage](https://instances.vantage.sh/aws/ec2/g5.2xlarge) — accessed 2026-08-01
- [AWS Bedrock Pricing vs Self-Hosted LLMs (2026) — Spheron](https://www.spheron.network/blog/aws-bedrock-pricing-2026-managed-api-cost/) — accessed 2026-08-01
- [SageMaker Inference Modes Compared — Business Compass LLC](https://knowledge.businesscompassllc.com/sagemaker-inference-modes-compared-real-time-batch-transform-serverless-asynchronous/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
