# Selective Multi-Agent Orchestration: Routing, Abstention, and Fallbacks

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-multi-agent-topologies`, `T07-agent-cost-routing`, `T07-harness-evals` · **Updated:** 2026-10-03
> **Module id:** `T07-selective-orchestration` · **Tags:** architecture, production, critical
> **Lab:** `labs/py/33-selective-orchestration/`

## The 30-second version

Selective orchestration is not "put an LLM in front of a pile of agents." It is a bounded classification boundary with an explicit abstain path. First narrow the catalog to a small candidate set using deterministic metadata or retrieval. Then score candidates against the request, require calibrated confidence, and refuse to guess when the top candidate is not clearly good enough. Only after that decision do you invoke a worker. If the chosen worker is unavailable, try a bounded, pre-ranked fallback and charge the failed attempt for its actual cost and latency. Keep routing, fallback, and authorization separate: routing predicts the right capability; fallback handles availability; policy decides what the selected worker may do. The senior answer is a measurable component: route accuracy, candidate-set recall, abstention quality, fallback rate, and total cost/latency against a single-agent baseline.

## Why this gets asked

Because "design a multi-agent system" often hides a routing problem. An interviewer wants to know whether you will draw a supervisor with fifteen specialists, or ask what justifies a boundary, how many choices the router sees, and what happens when it is unsure. The failure is usually silent: the wrong specialist returns a plausible answer, the system spends another model call correcting the mistake, and nobody can tell whether the problem was selection, handoff, worker quality, or verification. A selective router makes those seams explicit and gives each one an evaluation surface.

The source material in this curriculum already establishes the default: one agent with good tools beats a poorly decomposed system almost always, and the MAST work found design and inter-agent misalignment among the dominant failure categories. The same material also establishes when decomposition is justified: parallel read-heavy work, context isolation, permission/trust boundaries, model or latency tiers, independent ownership, and untrusted-content quarantine. This module turns that architectural judgment into a small, testable routing contract.

**Discovery note.** Instagram-derived material was used only as a discovery signal for this gap. It is not evidence for the claims below and is not a source. The technical claims are grounded in the cited curriculum evidence and the primary sources listed at the end.

---

## Lineage: past → present → future

**What came before.** Distributed systems have long separated orchestration from choreography. Workflow engines used explicit state machines and DAGs; microservice platforms used service discovery, health checks, retries, circuit breakers, and load balancing. AI systems initially hid the same decisions inside prompts: a manager agent was asked to "choose the best expert," and a group chat was allowed to continue until somebody said it was done. The early demos made the topology visible but left the selection boundary implicit. The production pain was predictable: too many choices, opaque handoffs, no hard termination, and a bill that depended on model mood.

**Where it stands now.** The useful split is between **candidate generation**, **route selection**, and **execution policy**. Candidate generation keeps a large catalog out of the model context by metadata filters or retrieval-gated tool/agent descriptions. Route selection chooses from that bounded set using a rule, classifier, or small model calibrated against labeled traffic. Execution policy handles permissions, budgets, timeouts, and provider failure below the model. `T07-multi-agent-topologies` supplies the architectural default and the evidence that orchestration-plus-distilled read-only subagents is the shape that usually wins. `T07-agent-cost-routing` supplies the distinction between predictive routing and reactive fallback. `T07-harness-evals` supplies the harness-level measurement discipline: test over-tooling, budget enforcement, and permission boundaries separately from task capability.

**Where it's heading.** High confidence: routing will be treated as a versioned production component with its own calibration set, route-distribution dashboard, and rollback path. High confidence: catalogs will be retrieval-gated or partitioned into small capability domains rather than placed wholesale in context. Medium confidence: learned routers will replace some hand-written rules where enough labeled traffic exists, but a rule-based router remains the right first implementation. Speculative: provider-side routing will expose quality/cost objectives directly. None of these removes the need to abstain, because a model upgrade changes the quality gap and therefore changes the meaning of a confidence score.

---

## Mental model

Treat routing as a funnel, not a second unconstrained agent:

```text
 request + required capabilities
                |
                v
      candidate generation / retrieval
      bounded to k candidates
                |
                v
      score coverage + separation
                |
        confidence >= threshold?
          /                 \
        no                   yes
        |                     |
   ABSTAIN              attempt primary
  no worker call       charge cost/latency
                              |
                       unavailable?
                         /       \
                       yes        no
                       |           |
             bounded fallback    return
             charge again       structured result
```

There are three different questions:

1. **Can this candidate do the task?** A capability/quality question measured by route labels and task outcomes.
2. **Is this candidate available now?** An operational question answered by provider health, timeout, 429, 5xx, or refusal classification.
3. **May this candidate perform this action?** An authorization question enforced in code against the actual call and parameters.

Combining these into one "agent confidence" number is a design error. A high-quality worker can be unavailable. An available worker can be unauthorized. A confident route can still be wrong.

---

## How it actually works

### 1. Bound the candidate set before scoring

A router that sees every agent, tool, or provider has inherited the over-tooling problem. `T07-harness-evals` records the operational pattern: selection is roughly stable at small catalogs, degrades as the catalog grows, and can fall sharply at larger sizes. Splitting the catalog into agents does not automatically solve selection; it can replace tool selection with agent routing plus context handoff.

Candidate generation should be cheap and deterministic where possible:

```python
def candidates(request, catalog, k=4):
    required = set(request.required_skills)
    matches = [agent for agent in catalog
               if required & agent.skills]
    return sorted(matches,
                  key=lambda agent: (-len(required & agent.skills), agent.name))[:k]
```

The important properties are a hard `k`, deterministic tie-breaking, a versioned catalog, and a metric for **candidate-set recall**: how often the correct worker appears in the set at all. If recall is low, confidence threshold tuning cannot save the design.

### 2. Score coverage and separation

Coverage asks how much of the requested capability the top candidate covers. Separation asks whether the top candidate is distinguishable from the runner-up. One simple deterministic score for the lab is:

```text
coverage   = top_overlap / required_skill_count
separation = (top_overlap - second_overlap) / top_overlap
confidence = coverage × separation
```

With no runner-up, separation is 1.0. With no overlap, confidence is 0.0. This is not a universal probabilistic calibration; it is a deliberately inspectable heuristic. In production, fit or calibrate a classifier on representative labeled traffic and validate it on held-out traffic. The threshold must be re-evaluated when candidate descriptions, prompts, traffic, or model versions change.

Do not call the worker before the threshold decision. An abstention should be cheap, visible, and actionable: ask the user to clarify, route to a safe single-agent baseline, queue for human review, or return a bounded "no capable route" result. Silently selecting the first candidate converts uncertainty into a confident failure.

### 3. Make fallback reactive and bounded

Predictive routing says "the request belongs with candidate A." Fallback says "A could not serve it, so candidate B may serve it." The trigger must be an availability-class error such as a timeout, 429, 5xx, overload, or provider refusal. Invalid input, a policy denial, and a worker contract bug should not be hidden by trying a different worker.

Every attempt is part of the accounting:

```text
total_cost    = token_count × sum(attempted candidate prices)
total_latency = sum(attempted candidate latencies)
```

This is intentionally conservative. A failed primary attempt has consumed resources. A fallback chain that is not charged this way will look like a cheap route in dashboards while producing the latency and spend of two or three routes. Put the hard budget outside provider retry wrappers; otherwise a single logical attempt can hide multiple billable calls.

### 4. Return a traceable result

A route result should contain at least:

```text
selected candidate, confidence, candidate set, attempts,
abstained/failed/success status, fallback_used,
output, token/cost accounting, latency accounting, catalog version
```

The route decision and the handoff payload belong in the same trace as the worker span. `T07-multi-agent-topologies` calls out route distribution, route accuracy, and handoff count as multi-agent-specific observability. Add candidate-set recall, abstention rate, fallback rate, quality by route, and cost/latency by route. A successful response is not evidence that selection was correct; it may be a plausible answer from the wrong specialist.

### 5. Keep authorization below the route

The selected candidate is not automatically entitled to every action it advertises. A route can select a refund-capable worker, but the tool-execution layer still enforces amount limits, identity, approval gates, and idempotency. `T07-harness-evals` is explicit that permission must be checked against actual tool parameters below the model, not merely stated in a system prompt. Treat a remote agent's output as untrusted content; selection is not a trust grant.

---

## Build it from scratch

The lab implements a pure Python `Candidate`, `RouteResult`, and `SelectiveRouter`. Each candidate has a name, skill set, token price, and fixed latency. The router ranks a bounded set, computes the confidence score above, abstains before calling on no match or low confidence, and invokes an injected callable only after selection.

The test suite deliberately proves the seams rather than mocking an LLM:

1. Ranking is deterministic and never exceeds the candidate bound.
2. An ambiguous request abstains without invoking a worker or spending money.
3. A confident request selects the primary worker and accounts for cost and latency.
4. A typed availability failure invokes only the next bounded candidate.
5. An unexpected exception propagates instead of being misclassified as availability.
6. If every bounded candidate is unavailable, the result is failed and all attempts are charged.

The fake call function is the model/provider boundary. Replacing it with an SDK call should not change the routing contract; it should only add provider usage, timeout, retry classification, and tracing data.

---

## How it's done in production

Start with a single-agent baseline using the union of the tools. The baseline is the control group required by `T07-multi-agent-topologies`; without it, a multi-agent improvement may simply be a larger token budget. Then add selective routing only for a task shape or boundary that justifies it.

**Candidate generation:** use explicit capability metadata for a small stable catalog. For larger catalogs, retrieve the top few descriptions, but evaluate retrieval recall and keep permission tiers separate. Do not let a semantic retriever surface a destructive worker merely because its description is lexically relevant.

**Calibration:** collect real representative requests, label the correct route and the acceptable quality of each candidate, choose a threshold for the cost of false routes and false abstentions, and validate on a held-out set. Recalibrate after model, prompt, candidate, or traffic-distribution changes.

**Fallback:** classify errors before retrying. Same-provider transient retry, cross-provider fallback, policy refusal, invalid request, and timeout should have distinct budgets and metrics. Use circuit breakers and health signals so a known-dead primary does not consume the full timeout on every request. Keep fallback width small and bounded.

**Safety:** separate read-only research workers from write-capable workers. Apply tool policy below the model, require approval for high-impact actions, and quarantine untrusted documents in a tool-less context when needed. A route should carry capability and policy metadata, not just a name.

**Evaluation:** report task quality, route accuracy, candidate-set recall, abstention precision/recall, fallback rate, total tokens, cost, p50/p95/p99 latency, and partial/failure rate. Compare selective orchestration with a single agent at the same budget. Run harness tests for over-tooling, budget enforcement, and permission bypass separately from capability tests, as `T07-harness-evals` recommends.

## How it's done in production

Production starts with a single-agent baseline and adds routing only where a measured boundary earns its complexity. Version the candidate catalog, router logic, model or classifier, prompts, policy, and threshold together so a route decision can be reproduced after a deployment. Use labeled traffic to calibrate confidence and candidate-set recall, then canary route changes against the baseline while tracking quality, abstention, fallback, cost, and p99 latency by route.

### Production failure table

| Symptom | Likely cause | Fix |
|---|---|---|
| The wrong specialist returns a plausible answer | Route threshold was not calibrated, or candidate descriptions overlap | Label representative traffic, measure route accuracy, remove overlap, and add a visible abstain path |
| The correct worker is never selected | Candidate generation recall is low, or `k` is too small | Measure correct-candidate-in-top-k recall; improve retrieval/metadata before lowering the threshold |
| The router spends nothing but quality collapses | Confidence is being treated as correctness, or the threshold is too high | Evaluate abstention precision and task completion; provide a safe fallback or clarification path |
| p99 latency is roughly twice normal during healthy traffic | Cheap-first escalation is implemented as an unmeasured fallback | Treat it as routing, measure escalation rate, and include failed-attempt latency in the SLO |
| Cost dashboards show only the successful model | Failed calls or SDK retries are outside the accounting boundary | Charge before dispatch, propagate provider usage, and put the budget outside retry wrappers |
| A provider outage becomes a cascade of slow requests | No circuit breaker or health-aware candidate ordering | Open the circuit after classified failures, use bounded deadlines, and expose partial failure |
| A model upgrade changes route distribution | The old confidence threshold and labels no longer describe the new quality gap | Recalibrate and canary the router; version model, prompt, catalog, and policy |
| A remote specialist's output triggers a forbidden tool call | Routing was confused with authorization and output trust | Treat output as untrusted, validate actions below the model, and enforce capability scopes |
| Engineers cannot explain why a request took two routes | No cross-agent trace or attempt record | Log the candidate set, score, reason, attempts, error class, cost, latency, and catalog version |
| A large catalog causes route quality to degrade | Over-tooling / over-choice attention dilution | Retrieval-gate or partition the catalog; compare against the single-agent and full-catalog baselines |

---

## Tradeoffs & when NOT to use it

- **Do not route just because the system has many agents.** A large catalog is a signal to improve descriptions, grouping, retrieval, or workflow design, not proof that a probabilistic router is needed.
- **Do not use confidence as a substitute for calibration.** A score is only useful if its relationship to correctness is measured on representative data.
- **Do not make abstention invisible.** An abstain is a product and operations path; silently defaulting to the first worker creates false confidence.
- **Do not use fallback as a cost optimizer by accident.** Cheap-first escalation can be valid, but it is a router with extra latency and must be evaluated on quality, escalation rate, and total cost.
- **Do not catch every exception and try the next worker.** Availability failures are not the same as invalid requests, policy denials, or implementation bugs. Broad catching masks defects and can multiply side effects.
- **Do not let fallback bypass permissions.** Every candidate must be checked against the same request policy; the fallback is not an authorization escape hatch.
- **Do not set `k` without measuring recall.** A smaller candidate set reduces choice overload but can exclude the correct route.
- **Do not skip the single-agent comparison.** If one agent with better tools, more context budget, or a verifier wins at equal spend, orchestration added seams without earning them.
- **Do use selective orchestration for real boundaries.** It earns complexity when task branches are independent and read-heavy, contexts must be isolated, permission or trust tiers differ, model/latency tiers differ, deployment ownership is independent, or untrusted content must be quarantined.

---

## Interview questions

### Q1 — What is selective orchestration?

**Testing:** whether the candidate distinguishes bounded routing from a free-form manager agent.

**Answer:** It is a bounded routing layer: generate a small candidate set, score candidates against the requested capabilities, require a calibrated confidence threshold, abstain when uncertain, and only then invoke a worker. Availability fallback is a separate bounded path after a classified failure. The output includes the route decision and all accounting so selection is measurable.

**Follow-up trap:** *"Why not ask a strong model to pick from every agent?"* — because the full catalog recreates over-tooling and makes selection harder to evaluate. It also hides candidate-generation recall, encourages confident prose instead of a typed decision, and turns every uncertain request into a billable call. Bound the choice set first.

### Q2 — How do you choose the candidate-set size?

**Testing:** whether the candidate understands the accuracy/choice-size tradeoff.

**Answer:** Start with a small operational bound, then measure two curves on labeled traffic: correct-candidate recall at `k`, and downstream quality/cost/latency at `k`. Increase `k` until recall is acceptable or partition the catalog. The number is workload-specific; choosing it from intuition is not enough.

**Follow-up trap:** *"If recall is low, should you lower the confidence threshold?"* — no. A threshold can only choose among candidates that were surfaced. Improve candidate generation or catalog metadata first; otherwise you trade abstentions for confidently wrong routes.

### Q3 — Define route confidence and calibration.

**Answer:** Confidence is a score representing how likely the selected route is to satisfy the task, based on features such as capability coverage and separation from the runner-up. Calibration tests whether requests scored 0.8 are actually correct about 80% of the time, within a tolerance and segment. A raw score is not a probability just because it has a decimal point.

**Follow-up trap:** *"The score is deterministic, so why does it need calibration?"* — deterministic repeatability is not correctness. A fixed skill-overlap score can be systematically overconfident for ambiguous tasks or underconfident for tasks whose capability labels are incomplete.

### Q4 — What should happen when confidence is below threshold?

**Answer:** Abstain before invoking a worker. Return a typed result with the candidate set, score, and explicit status, then route to a safe path: ask for clarification, use a single-agent baseline, queue for human review, or explain that no capable route was identified. No worker call means no hidden model cost.

**Follow-up trap:** *"Isn't abstention bad UX?"* — silent confident wrongness is worse. Measure abstention precision and recovery success. If abstentions are excessive, improve candidate metadata or calibration; do not hide them by guessing.

### Q5 — Routing versus fallback: what is the difference?

**Answer:** Routing is predictive selection based on task difficulty or capability. Fallback is reactive availability handling after a timeout, 429, 5xx, overload, or refusal. Routing should be judged by quality/cost at its threshold; fallback should be judged by availability, escalation rate, and added latency. Calling cheap-first escalation "fallback" does not make its latency or calibration costs disappear.

**Follow-up trap:** *"Can cheap-first escalation ever be reasonable?"* — yes, if the quality and escalation boundary is measured, the extra round trip fits the SLO, and total cost includes both attempts. It is a deliberate two-stage router, not a free availability feature.

### Q6 — Which errors should trigger fallback?

**Answer:** Only classified availability failures: transient 429/5xx, timeout, overload, or a provider refusal when the fallback has a meaningfully different acceptance profile. Invalid input, policy denial, malformed output caused by a contract bug, and unexpected exceptions should surface or go through their own repair path. Catching `Exception` and trying another agent masks bugs and can repeat unsafe side effects.

**Follow-up trap:** *"What about a low-quality answer?"* — quality escalation is a separate verifier or quality gate, and it needs its own budget and eval. Do not silently turn every subjective quality concern into an unbounded fallback loop.

### Q7 — How do you account for fallback cost and latency?

**Answer:** Charge each attempted candidate before dispatch. For fixed candidate economics, cost is token count times each attempted candidate's price, summed across attempts; latency is the sum of attempted round trips, plus any measured queue/retry overhead in production. A failed primary still consumed resources, so it remains in the total.

**Follow-up trap:** *"The SDK retries inside one call. Is that one attempt?"* — it is one logical route attempt but multiple billable operations. Put accounting and hard budgets outside the SDK retry wrapper, or propagate provider usage for every retry. Otherwise the budget counter undercounts.

### Q8 — How do you prove the router is better than one agent?

**Answer:** Run the same golden task set through a single-agent baseline and the selective system. Hold tools, task distribution, and budget comparable. Report quality/success, route accuracy, candidate recall, abstention and fallback rates, tokens, p50/p95/p99 latency, and cost. Also compare against the single agent with the same extra budget; otherwise a gain may just be spending more.

**Follow-up trap:** *"The multi-agent version has higher quality. Is that enough?"* — not if it costs 15x and misses the latency SLO. The value depends on the task and unit economics. `T07-multi-agent-topologies` explicitly frames reported quality gains alongside their token multiplier and warns that MAST finds design failures dominate.

### Q9 — How do you debug a silent misroute?

**Answer:** Correlate one trace across candidate generation, route decision, worker invocation, fallback, and synthesis. Log catalog version, candidate set, scores, selected name, structured reason, attempts, error class, output contract, tokens, cost, and latency. Compare the selected route with an offline label or accepted-route set. Track route distribution and route accuracy, not just final task success.

**Follow-up trap:** *"The final answer is correct, so why care?"* — a correct answer can be accidental and the route can still be expensive, unauthorized, or fragile. Silent misroutes often appear first as route drift, fallback spikes, or a worker saying "not my area," before final quality drops.

### Q10 — How does over-tooling relate to orchestration?

**Answer:** A large choice catalog dilutes selection accuracy and consumes context. Retrieval-gating or partitioning can reduce the choice set, but splitting into agents is not the first fix because it replaces tool selection with agent routing and a handoff. Use better descriptions, remove overlap, group tools, and retrieve a small relevant set before introducing more agents.

**Follow-up trap:** *"When does the catalog justify a split?"* — when the boundary is structural: different permission/trust tiers, context isolation, model/latency tiers, independent ownership, untrusted-content quarantine, or genuinely parallel read-heavy work. Split on blast radius and task shape, not a round number of tools.

### Q11 — How do confidence and authorization interact?

**Answer:** They do not replace each other. Confidence says the candidate is likely capable; authorization says it may perform this action under this principal, tenant, resource, and amount. Authorization runs in the harness against the actual tool call and parameters below the model. A high-confidence route must still be denied or escalated if policy rejects it.

**Follow-up trap:** *"Could a privileged fallback be used if the normal worker is unavailable?"* — only through an explicit policy and approval path. Availability cannot silently expand authority. A fallback with more privilege is a different security boundary, not just another provider.

### Q12 — How do you choose a rule-based router versus a learned router?

**Answer:** Start with the simplest mechanism that achieves the measured quality/cost bar. Rules based on explicit task type or capability metadata are cheap to inspect and maintain. A learned router can use richer features when enough representative labels exist, but it adds training, drift detection, calibration, and re-fitting after model changes. Both require held-out evaluation.

**Follow-up trap:** *"A learned router sounds more accurate. What can still go wrong?"* — distribution shift, stale labels, leakage from the answer into routing features, overconfident probabilities, and candidate catalogs that changed after training. The router is production ML infrastructure, not a one-time model choice.

### Q13 — What is the right response to a low-confidence request with no safe specialist?

**Answer:** Return an explicit abstention and preserve the evidence needed for recovery: required skills, candidates considered, confidence, catalog version, and policy context. Then ask a clarifying question, escalate to a human, or use a constrained baseline if its risk is acceptable. Do not manufacture a route merely to keep the UI green.

**Follow-up trap:** *"Does that mean the system needs a human for every ambiguity?"* — no. Define safe defaults for low-impact tasks, but make them explicit and bounded. The key is that the product owner chooses the abstention policy rather than the router silently choosing one.

### Q14 — How does the Instagram discovery signal affect your evidence standard?

**Answer:** It does not establish a technical claim. It can reveal that a topic is missing from a learning plan, but the curriculum must ground claims in primary papers, official framework documentation, and existing cited evidence. In this slice, Instagram is discovery-only; the architectural and evaluation claims are connected to the cited multi-agent-topologies, agent-cost-routing, and harness-evals modules and their sources.

**Follow-up trap:** *"If a popular post says the pattern works, why not cite it?"* — popularity is not evidence of mechanism, scope, or production behavior. Use it to find a claim worth checking, then replace it with a source that exposes the method and limitations.

---

## Red flags that fail you

- Asking an LLM to choose from an unbounded catalog of agents.
- Treating a deterministic score as calibrated probability without held-out evaluation.
- Calling a worker before deciding whether confidence clears the threshold.
- Silently defaulting to the first candidate instead of abstaining.
- Retrying every exception through a different specialist.
- Treating fallback as a free cost optimization and omitting failed-attempt accounting.
- Increasing `k` or lowering the threshold without measuring candidate recall and route quality.
- Confusing route capability with authorization or trust.
- Claiming a multi-agent win without a single-agent baseline at the same budget.
- Tracking final success but not route distribution, fallback rate, abstention quality, cost, and latency.
- Splitting because there are many tools rather than because there is a permission, context, ownership, model-tier, or task-shape boundary.
- Citing Instagram-derived material as technical evidence instead of discovery-only context.

---

## Cheat card

```text
SELECTIVE ROUTING = bounded candidate generation -> score -> threshold -> execute

THREE QUESTIONS
  capable?       route quality / calibration
  available?     timeout, 429, 5xx, refusal -> bounded fallback
  authorized?    policy check below the model, on actual parameters

BOUND THE CHOICE
  measure correct-candidate recall at k
  deterministic tie-breaks; version the catalog
  large catalog: better descriptions -> remove overlap -> group -> retrieve
  NOT: split just because tool/agent count is large

LAB CONFIDENCE
  coverage   = top overlap / required skills
  separation = (top - runner-up overlap) / top overlap
  confidence = coverage * separation
  no match or below threshold -> ABSTAIN BEFORE A WORKER CALL

FALLBACK
  availability failure only; unexpected bugs propagate
  bounded candidates; no unbounded retry loop
  failed primary still costs money and latency
  total cost = tokens * sum(price of attempts)
  total latency = sum(latency of attempts)

OBSERVABILITY
  one trace id; candidate set, scores, reason, selected route, attempts
  route accuracy · candidate recall · abstention quality · fallback rate
  quality/cost/latency by route · catalog/model/prompt/policy versions

ARCHITECTURE DEFAULT
  one agent with good tools first
  split only for parallel breadth, isolation, permission/trust, model tier,
  independent ownership, or untrusted-content quarantine
  prove it against a single-agent baseline at equal budget

EVIDENCE STANDARD
  Instagram = discovery only, never technical evidence
  use cited modules, primary papers, and official framework documentation
```

## Sources

- [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) — Cemri et al.; MAST taxonomy and trace evidence, cited by `T07-multi-agent-topologies`; accessed 2026-10-03
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — orchestrator/subagent task-shape evidence, cited by `T07-multi-agent-topologies`; accessed 2026-10-03
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — distilled subagent returns and tool-set guidance, cited by `T07-multi-agent-topologies`; accessed 2026-10-03
- [LMSYS — RouteLLM](https://www.lmsys.org/blog/2024-07-01-routellm/) — empirical model-routing methodology, cited by `T07-agent-cost-routing`; accessed 2026-10-03
- [OpenAI Agents SDK — Handoffs](https://openai.github.io/openai-agents-python/handoffs/) — handoff semantics, cited by `T07-multi-agent-topologies`; accessed 2026-10-03
- [LangGraph Supervisor reference](https://reference.langchain.com/python/langgraph-supervisor/) — explicit supervisor mechanics, cited by `T07-multi-agent-topologies`; accessed 2026-10-03
- [AgentDojo](https://agentdojo.spylab.ai/) — harness robustness benchmark context, cited by `T07-harness-evals`; accessed 2026-10-03

## Changelog

- 2026-10-03 — created; added selective candidate routing, confidence-based abstention, bounded availability fallback, and deterministic cost/latency accounting
