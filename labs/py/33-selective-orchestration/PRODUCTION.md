# Production notes - selective orchestration

The lab models the routing boundary with deterministic skills and an injected call function. Production adds calibrated classifiers, live health state, provider adapters, policy enforcement, and trace correlation. The lab's bounded candidate set is the important invariant: a fallback may improve availability, but it must not become an unbounded retry loop.

| Lab concept | Production addition |
|---|---|
| `Candidate.skills` | Versioned capability registry with ownership, permission tier, model/provider identity, and explicit use/do-not-use descriptions |
| `rank()` | A calibrated classifier or retrieval-gated catalog, evaluated on representative labeled traffic and held-out data |
| `confidence` and abstention | A threshold chosen from quality, cost, and false-route loss; an abstention path to a human, one safe default, or a single-agent baseline |
| `CandidateUnavailable` | Error taxonomy distinguishing retryable 429/5xx, provider refusal, invalid request, timeout, and permanent policy failure |
| fallback loop | Hard attempt, token, cost, and wall-clock budgets; backoff for same-provider retry; circuit breakers and provider health signals |
| cost and latency fields | Provider usage records, cache-hit attribution, p50/p95/p99 dashboards, per-tenant and per-feature budgets, and an immutable trace/span record |
| deterministic tests | Replayable golden routes, route accuracy, abstention precision/recall, fallback rate, quality by route, and canary comparison against a single-agent baseline |

## Failure modes

1. **The router is confident and wrong.** A keyword or embedding match can select a plausible specialist with the wrong scope. Keep a golden route set, log the selected candidate and reason, and measure route accuracy rather than relying on user complaints.
2. **Abstention is treated as an error.** A low-confidence request is useful information. Route it to an explicit safe path and measure abstention quality; do not silently pick the first worker in the registry.
3. **Fallback hides a primary outage.** Track fallback rate by candidate and provider. A successful response can still be an availability incident if the primary is failing.
4. **Fallback becomes cost or latency multiplication.** Charge every attempt before execution and enforce a hard per-request budget outside provider retry wrappers. A fallback that is invisible in accounting will eventually surprise the bill.
5. **The candidate catalog drifts.** New skills, overlapping descriptions, or a model upgrade can change the score distribution. Version the catalog and recalibrate confidence after model, prompt, or candidate changes.
6. **The bounded set is too small.** A top-k gate can miss the only capable worker. Measure recall of the correct candidate at each k before tightening the bound; compare against a full-catalog baseline.
7. **A remote agent is trusted because it was selected.** Routing is not authorization. Treat remote-agent output as untrusted content, enforce permissions below the model, and keep write tools behind a separate policy and approval boundary.

## Evaluation contract

Run the same labeled task set through a single-agent baseline and the selective router. Report success/quality, route accuracy, abstention rate and precision, fallback rate, total tokens, cost, p50/p95/p99 latency, and the percentage of requests whose correct candidate was inside the bounded set. Break results down by task type. A lower cost number without quality and abstention numbers is not evidence that routing helped.
