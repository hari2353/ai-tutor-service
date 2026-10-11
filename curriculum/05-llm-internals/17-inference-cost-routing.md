# Inference Cost Routing: Quality Tiers, Budgets, Batch, and Break-Even Math

> **Track:** T05 LLM Internals · **Time:** 2.5h · **Prereqs:** T05-inference-serving, T05-quantization · **Updated:** 2026-10-11
> **Module id:** `T05-inference-cost-routing` · **Tags:** inference, cost, critical
> **Lab:** `labs/py/33-selective-orchestration/` (routing reference) 

## The 30-second version
Inference routing is a policy decision over quality, latency, capacity, privacy, and cost, not a switch statement on model names. Classify requests by required capability and risk, select the cheapest model that clears the quality bar, and keep a bounded fallback chain. Separate interactive traffic from batch traffic, because batch can tolerate delay and should not contend with the interactive serving pool. Measure cost per successful task, not only dollars per token: retries, cache misses, long prompts, and failed outputs are all part of the unit economics.

## Why this gets asked
Hiring packs repeatedly ask for model selection, latency, cost controls, batch inference, and production routing. The interviewer wants to know whether you can turn “use a smaller model” into a defensible operating policy. They will probe what happens when the router is confidently wrong, when every executor retries at once, or when a cheaper answer causes downstream rework.

## Lineage: past -> present -> future
**What came before.** Teams sent every request to one frontier model because it simplified integration. The pain was predictable: simple classification paid for reasoning capacity, batch work competed with users, and a provider price or quota change became a production incident. Self-hosted single-model endpoints had the opposite pain: one capacity pool and one quality point could not fit every workload.

**Where it stands now.** A gateway commonly combines policy routing, provider adapters, retries, caching, quotas, and usage accounting. AWS Bedrock batch inference accepts JSONL in S3 and writes asynchronous results to S3; its documentation explicitly notes that batch does not support tool calling or structured output. That makes it a workload-specific path, not a universal fallback for interactive agents. [Corpus evidence] in the STAR bank describes vLLM for concurrent online requests and Bedrock batch for latency-indifferent offline generation; the personal throughput and cost numbers remain `[CONFIRM]` and are not invented here.

**Where it is heading.** High confidence: routers will include quality gates and per-tenant budgets rather than only provider health. Medium confidence: adaptive routing will use live queue and KV-cache pressure. Speculative: an autonomous router will infer business value reliably enough to allocate spend without explicit policy; keep an owner-approved budget and a safe default.

## Mental model
```text
request -> policy/risk -> candidate set -> quality gate -> cheapest viable model
                                      | failure
                                      v
                             bounded fallback / abstain
```
Every attempt is charged before execution and recorded. A fallback that returns success but doubles spend is still an incident if the budget policy was violated.

## How it actually works
Define a request class: interactive or batch, capability, max latency, risk, tenant, and expected input/output tokens. For provider `i`, estimate:
`cost_i = input_tokens * input_price_i + output_tokens * output_price_i + fixed_infra_share`.
For self-hosting, a simple unit cost is `GPU_dollars_per_hour / (tokens_per_second * 3600) * 1,000,000`. Add utilization, idle replicas, storage, engineering, and retry waste before using it in a business decision.

The route should be bounded. Rank at most `k=3` candidates, require confidence above a policy threshold, and abstain if no candidate covers the capability. A failed provider can trigger one alternate candidate, not an unbounded loop. Do not fallback from a policy refusal to a more permissive provider.

Batch and online paths differ mechanically. Interactive requests need TTFT and TPOT SLOs, admission control, and streaming. Batch can queue, process JSONL asynchronously, retry records, and write results to object storage. Batch output may not support tool calling or structured output, so validate the target contract before choosing it.

## Build it from scratch
Use the existing selective-orchestration lab as a routing shape: candidates carry skills, cost, and latency; the router bounds the candidate set, computes confidence, abstains, and charges attempts. For a small implementation, use a `dict` policy table and deterministic token-cost arithmetic. The new resume lab is intentionally separate; do not hide cost decisions inside a prompt.

```python
def choose(candidates, required, max_latency, max_cost):
    viable = [c for c in candidates if required <= c.skills
              and c.latency_ms <= max_latency and c.cost <= max_cost]
    return min(viable, key=lambda c: (c.cost, c.latency_ms)) if viable else None
```

## How it's done in production
Use a gateway or internal library for authentication, provider adapters, quotas, retries, tracing, and spend attribution. Keep business policy close to the caller because only it knows whether a fallback answer is acceptable. Use prompt caching only when prefix identity and invalidation are understood. Route high-risk or write-capable tasks to an approved model set; route deterministic extraction to a constrained or smaller model; route offline bulk generation to batch.

| Symptom | Cause | Fix |
|---|---|---|
| Cost spikes while request count is flat | Prompt growth, retries, or cache misses | Attribute input/output tokens, retry count, and cache hit by tenant |
| Cheap model passes offline but fails live | Offline set omits long-tail or high-risk slices | Gate each route on representative live-like slices |
| Fallback storm during provider outage | Every request tries every provider | Global attempt/cost budget, circuit breaker, bounded candidate set |
| Interactive p99 rises during nightly generation | Batch shares the online pool | Separate capacity and queue batch work |
| Router picks a plausible but wrong specialist | Keyword confidence is not calibrated | Golden route set, abstention, route accuracy, human-safe default |
| Batch output cannot be consumed | Tool calls/structured output unsupported in batch path | Validate capability before routing; use online path when contract requires it |

## Tradeoffs & when NOT to use it
- Do not add a router for one stable model and one low-volume caller; policy complexity can exceed savings.
- Do not route solely on price. A failed cheap answer can cost more through retries, human review, or incorrect downstream actions.
- Do not use batch for interactive tool-calling or strict structured-output workflows when the provider contract excludes them.
- Do not self-host for spiky, low-volume traffic unless data residency or control dominates; idle GPU cost and on-call are real.
- Do not fallback across authorization boundaries. A more capable provider is not allowed to receive data merely because the first provider is down.

## Interview questions
### Q1 - How would you route requests across three models?
**Testing:** Policy decomposition.
**Answer:** Classify capability, risk, latency, tenant, and token budget; filter unsafe/infeasible candidates; rank by measured quality per cost; choose the cheapest candidate clearing the slice-specific quality gate; abstain or use a bounded fallback.
**Follow-up trap:** *What if the cheapest model is 2% worse overall?* Check the affected slice and cost per successful task, not just aggregate quality.

### Q2 - How do you calculate self-hosted cost per million tokens?
**Testing:** Unit economics.
**Answer:** `hourly GPU cost / (aggregate tokens/sec * 3600) * 1e6`, then add replica idle time, storage, operations, and failed/retried work. Benchmark at the target concurrency and p99, not single-stream speed.
**Follow-up trap:** *Does increasing batch always lower cost?* Only until KV capacity or memory bandwidth saturates; preemption and latency can make effective cost rise.

### Q3 - Online endpoint or batch inference?
**Testing:** Workload segmentation.
**Answer:** Online for user-blocking, streaming, tool-calling, and strict latency. Batch for large independent JSONL work where delay is acceptable and object-storage results are fine. AWS Bedrock batch does not support tool calling or `response_format` structured output.
**Follow-up trap:** *Can you use batch as an agent fallback?* Not when the agent needs interaction or structured/tool-call semantics; select a compatible online path.

### Q4 - What stops fallback from becoming a retry storm?
**Testing:** Reliability and cost.
**Answer:** Candidate set cap, one logical fallback policy, attempt and dollar budgets, provider circuit breakers, and per-attempt accounting. Stop on permanent errors and policy refusals.
**Follow-up trap:** *How do you enforce a budget across 500 pods?* Use a gateway/shared quota or an explicitly conservative per-instance budget; local limits alone do not bound fleet spend.

### Q5 - How do you evaluate a router?
**Testing:** Measurement.
**Answer:** Compare against a single-model baseline on route accuracy, abstention precision, task success, cost per success, p50/p95/p99 latency, fallback rate, and tokens. Break down by task type and risk slice.
**Follow-up trap:** *What if cost falls but task success also falls?* It is not an optimization until the business loss and quality floor are explicitly accepted.

### Q6 - How does prompt caching change routing?
**Testing:** Cache economics.
**Answer:** It lowers input-token work when stable prefixes repeat, but only exact/policy-safe prefixes should be reused and cache hit quality must be measured. Routing can prefer a model with a high hit rate only if cache keys and invalidation are equivalent.
**Follow-up trap:** *Why did semantic caching hurt quality?* The similarity threshold returned an answer to a nearby but non-equivalent request.

### Q7 - What is the difference between provider failover and model routing?
**Testing:** Conceptual precision.
**Answer:** Failover preserves a chosen policy when infrastructure fails; routing chooses among capability/cost options even when all providers are healthy. Failover needs health and circuit state; routing needs quality evidence and authorization policy.
**Follow-up trap:** *Can failover violate data residency?* Yes. The fallback registry must encode residency and data-class constraints before health is considered.

### Q8 - How do you route high-risk tasks?
**Testing:** Safety boundary.
**Answer:** Explicit risk classification, allowlisted models/tools, mandatory structured output validation, human approval for side effects, audit logging, and no automatic downgrade to an unapproved provider.
**Follow-up trap:** *What if the approved model is unavailable?* Abstain or use a human/manual path; availability does not override authorization.

### Q9 - Why can a smaller model be more expensive in practice?
**Testing:** Systems thinking.
**Answer:** Lower token price can be offset by lower success rate, extra retries, longer prompts, repair calls, human review, or higher latency that requires more replicas. Measure cost per successful outcome.
**Follow-up trap:** *How do you prove it?* Replay representative cases and attribute every attempt, output token, latency, and downstream correction.

### Q10 - What numbers would you demand before shipping a router?
**Testing:** Principal judgment.
**Answer:** Baseline and candidate quality by slice, p95/p99 latency, throughput, cost per success, cache-hit rate, fallback rate, abstention rate, quota headroom, and maximum spend under outage. No single average is sufficient.
**Follow-up trap:** *Which number is the kill switch?* A hard per-request and per-tenant spend/attempt budget, because it bounds the worst failure even when quality telemetry is delayed.

## Red flags that fail you
- “Always use the cheapest model.”
- A fallback chain with no attempt or cost cap.
- Treating batch inference as equivalent to interactive tool calling.
- Quoting a vendor price without utilization and retry assumptions.
- Routing around a safety or data-residency policy during an outage.

## Cheat card
```text
Route on capability + risk + latency + tenant policy + token budget.
Choose cheapest model that clears measured quality by slice.
Bound candidates (often <=3); abstain instead of guessing.
Cost/success > cost/token: include retries, repairs, cache misses, review.
Self-host unit cost = GPU $/hr / (tok/s * 3600) * 1e6.
Benchmark at target concurrency and p99, not one request.
Online = streaming/tool calls/latency; batch = async independent JSONL.
Bedrock batch: S3 input/output; no tool calling or structured response_format.
Every attempt is charged and traced before execution.
Fallback cannot override auth, residency, or risk policy.
Hard request/tenant budgets are the outer safety bulkhead.
``` 

## Operating numbers in practice
- Keep the candidate set bounded at `3` models or fewer for one request.
- Set an explicit maximum of `2` attempts for a normal request and `1` fallback for an outage.
- Track `5` outcome dimensions: quality, cost, latency, authorization, and capacity.
- Use at least `4` concurrency points in a serving benchmark: `1`, `8`, `32`, and `64`.
- Report at least `6` route metrics: success, cost, input tokens, output tokens, p95 latency, and fallback rate.
- Keep separate budgets for request, tenant, and fleet; a practical starting point is `1`, `3`, and `10` cost units per decision window.
- Require a minimum of `20` cases before tuning a route threshold, and use `100` or more for a high-risk slice.
- Treat `2` consecutive provider failures as a circuit-breaker signal only when the error class is retryable and the window is explicit.
- Compare at least `2` windows, such as `5` minutes and `1` hour, before declaring a spend spike.
- Charge every attempt, including repairs and fallbacks; a successful answer after `3` attempts is not a one-attempt success.

## Sources
- [Amazon Bedrock batch inference](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html) - official capability and limitation documentation; accessed 2026-10-11
- [vLLM documentation](https://docs.vllm.ai/en/latest/) - official serving documentation; accessed 2026-10-11
- [Selective orchestration production notes](../../labs/py/33-selective-orchestration/PRODUCTION.md) - internal routing contract and failure modes; accessed 2026-10-11
- [30-Story STAR Bank](../14-behavioral-principal/01-star-bank.md) - internal corpus evidence for vLLM/Bedrock workload split; accessed 2026-10-11
- [Nexperia job prep pack](../../mocks/company/inbox/jobspy_079ec3cf8fc417.md) - internal job-hunt corpus evidence for routing, latency, cost, and observability topics; accessed 2026-10-11

## Changelog
- 2026-10-11 - created

## Operating numbers to carry into the loop
- Keep the candidate set bounded at `3` models or fewer for one request.
- Set an explicit maximum of `2` attempts for a normal request and `1` fallback for an outage.
- Track `5` outcome dimensions: quality, cost, latency, authorization, and capacity.
- Use at least `4` concurrency points in a serving benchmark: `1`, `8`, `32`, and `64`.
- Report at least `6` route metrics: success, cost, input tokens, output tokens, p95 latency, and fallback rate.
- Keep separate budgets for request, tenant, and fleet; a practical starting point is `1`, `3`, and `10` cost units per decision window.
- Require a minimum of `20` cases before tuning a route threshold, and use `100` or more for a high-risk slice.
- Treat `2` consecutive provider failures as a circuit-breaker signal only when the error class is retryable and the window is explicit.
- Compare at least `2` windows, such as `5` minutes and `1` hour, before declaring a spend spike.
- Charge every attempt, including repairs and fallbacks; a successful answer after `3` attempts is not a one-attempt success.

## Lineage detail: from one model to policy-controlled fleets
**What came before.** The first production LLM integrations commonly had 1 endpoint, 1 API key, 1 timeout, and 1 retry loop. That was attractive when traffic was below 10 requests per minute and prompts were under 2,000 tokens. It failed when a product combined 50-token classifications, 4,000-token RAG answers, and 30,000-token batch jobs behind the same endpoint. A single queue made the largest job the scheduling policy for every user.

**Where it stands now.** Mature gateways separate at least 4 concerns: authorization, route selection, execution, and accounting. A route can be selected from 3 candidate models, but it should be rejected if the candidate violates data residency, risk class, tool capability, or latency budget. Online and batch pools are normally separated. The online pool targets TTFT and TPOT; the batch pool targets tokens per dollar and can accept minutes or hours of delay. A route report should include request count, input tokens, output tokens, retries, cache hits, fallback count, p50, p95, p99, and cost per successful task.

**Where it's heading.** High-confidence systems will route using live capacity and tenant budgets, not only static keyword rules. Medium-confidence systems will use learned quality predictors, but they still need an abstain path. Speculative autonomous budget allocation is unsafe for write-capable or regulated workflows. A human-approved policy table remains the source of truth for residency, authorization, and high-risk actions.

## Budget math and operational examples
Suppose a hosted model costs 1 unit for input and 4 units for output, while a smaller model costs 0.25 and 1.2 units. A 2,000-token input and 300-token output costs 2,000x1 + 300x4 in the first unit convention, while the smaller route costs 2,000x0.25 + 300x1.2. The exact currency is provider-specific, but the comparison must use the same token accounting and include 2 retries if the smaller model fails validation. A 20% cheaper request that retries 3 times is not cheaper.

For self-hosting, assume a GPU costs `$2.40/hour`, aggregate throughput is `8,000 tokens/second`, and utilization is `65%`. The raw million-token cost is `2.40 / (8000 * 3600) * 1,000,000`, then divided by 0.65 to include idle capacity. Add replica minimums, storage, engineering, and failed work. Benchmark at concurrency `1`, `8`, `32`, and `64`; single-stream throughput is not the production number.

Keep at least 3 budget boundaries: request budget, tenant budget, and fleet budget. A request may permit 2 attempts or `$0.10`; a tenant may permit `$50/hour`; the fleet may permit `$500/hour`. Local pod counters cannot enforce a fleet budget across 20 pods. Use a shared gateway, quota store, or conservative per-pod allocation with a reconciliation loop.

For a concrete route table, classify 6 request fields: capability, risk, latency, tenant, residency, and workload shape. A simple policy can expose 4 routes: interactive-small, interactive-frontier, batch-cheap, and human-review. Give each route 3 hard limits: maximum attempts, maximum cost, and maximum latency. If a route has a p95 target of 800 ms, a tenant budget of `$50/hour`, and a fleet budget of `$500/hour`, the router must reject or degrade before any limit is exceeded. A route with 95% success but 3 retries on failures may have worse cost per success than a route with 90% success and no repair call. These are decision examples, not provider promises.

## Additional interview drills
### Q11 - A cheap model costs less but has an 8-point lower task-success rate. What do you do?
**Testing:** Unit economics.
**Answer:** Measure cost per successful task, downstream repair, human review, and the affected slice. Keep the cheap route only where its quality clears the task-specific floor. Route high-risk or high-repair slices elsewhere.
**Follow-up trap:** *What if the average score is acceptable?* Averages can hide the exact regulated or revenue-critical slice; gate per slice.

### Q12 - How do you stop 20 pods from multiplying a provider outage?
**Testing:** Distributed budget control.
**Answer:** Circuit-break the provider globally, cap attempts at the gateway, use a shared budget, and fail fast on retryable saturation after the policy limit. Per-pod retry limits alone multiply by pod count.
**Follow-up trap:** *What happens to user traffic?* Return a typed degraded response, queue only work that is safe to delay, or abstain. Do not silently switch to an unauthorized provider.

### Q13 - Why is latency part of cost?
**Testing:** Systems economics.
**Answer:** Higher latency requires more concurrent capacity to maintain throughput and may require more replicas. It also increases abandonment and retry rates. Cost per successful task includes the infrastructure and product effects of delay.
**Follow-up trap:** *Can batching always fix it?* Batching improves utilization until KV pressure, queueing, or p99 SLOs become the constraint.

### Q14 - When is a router the wrong abstraction?
**Testing:** Simplicity judgment.
**Answer:** One stable model, one caller, low volume, and no policy split do not justify a gateway with complex routing. Add the policy seam when a second capability, provider, risk class, or workload shape creates a real decision.
**Follow-up trap:** *How do you know it is time?* Measure duplicate retry logic, spend variance, capacity contention, or repeated model-selection decisions before abstracting.

### Q15 - What is the safest fallback for a write-capable agent?
**Testing:** Safety boundary.
**Answer:** An approved model with the same authorization and residency constraints, or human/manual handling. If neither is available, abstain. Availability never overrides permission.
**Follow-up trap:** *Can a read-only fallback prepare the action?* Only if the result is clearly non-executable and a human approval boundary remains before side effects.
