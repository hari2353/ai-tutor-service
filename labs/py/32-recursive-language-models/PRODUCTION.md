# Production notes - recursive context controllers

The lab uses deterministic fake child calls. A production RLM adds a real model adapter, bounded scheduling, cancellation, tracing, versioned caches, and a capability policy around the external context environment.

| Lab | Production addition |
|---|---|
| `ContextStore` | object storage/database range reads, ACL checks, source versions, immutable IDs |
| `Budget` | token/cost accounting from provider usage, wall deadline, concurrency semaphore, kill switch |
| `run_children` | bounded worker pool, retries classified by error, cancellation propagation, backpressure |
| `ChildResult` | model/provider/prompt version, citations, confidence, trace/span IDs, raw error class |
| `reduce_results` | typed schema validation, conflict policy, partial-answer policy, audit record |

The common incidents are fan-out explosions, detached children continuing after the parent times out, stale cache results after a source update, and document text acquiring execution authority. Keep document content untrusted, expose read-only tools first, sandbox any code execution, deny arbitrary egress, and enforce limits below the model. Evaluate against direct long-context, compaction, retrieval, and RLM paths using the same corpus and task set; include total calls, tokens, cost, p95/p99 latency, partial results, and evidence coverage.
