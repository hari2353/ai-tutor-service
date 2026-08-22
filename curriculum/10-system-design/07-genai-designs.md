# GenAI and Agent System Designs

> **Track:** T10 System Design · **Time:** 5h · **Prereqs:** `T10-distributed-fundamentals`, `T06-hybrid-search`, `T06-vector-index-internals`, `T07-agent-loop-from-scratch`, `T07-harness-engineering` · **Updated:** 2026-07-26
> **Module id:** `T10-genai-designs` · **Tags:** sprint, practice, critical

## The 30-second version

GenAI system design is ordinary distributed system design with three additions that change every answer: the core component is **probabilistic**, so correctness is a distribution you must measure rather than a property you can assert; it is **expensive per request** at roughly $0.01 to $0.30 against $0.0001 for a normal API call, so the cost model is a first-class part of the design rather than a footnote; and it is **slow**, at 1 to 10 seconds against 50 ms, so streaming, caching, and step reduction move from optimisations to architecture. The consequence is that every GenAI design answer needs four artifacts a conventional one does not: a **cost per request** with the arithmetic shown, an **eval strategy** that says how you know it works, a **failure mode for silent wrongness** (the system returns 200 OK with a confidently incorrect answer), and a **trust boundary** where untrusted content is labelled and privileged actions are authorised by code that does not consult the model. This module drills twelve designs against one repeated six-slot template, because the value is the pattern, not the individual system: interviewers are comparing your second design against your first, and consistency of method reads as seniority far more than depth on any single box.

## Why this gets asked

Because the GenAI design round is the fastest way to find out whether someone has operated one of these or has only read about them. Everyone can draw the RAG diagram: retriever, vector DB, LLM. The signal is entirely in the second layer. Does the candidate ask what "10 million documents" means in chunks and bytes before drawing anything? Do they know that a 10M-vector index and a 500M-vector index are different architectures rather than the same one scaled? Do they produce a cost per request unprompted? Do they have an answer for "the model returns a confident wrong answer and returns 200," which is the failure mode with no analogue in conventional systems? The interviewer has personally lived the specific version of this: a RAG system that passed every latency and availability SLO while giving wrong answers for two months because nobody built an eval; a gateway that fell over when one tenant's batch job consumed the shared provider quota; or a bill that went from $8k to $50k a month with nobody able to say which change caused it. The 2026 interview mix for AI engineering roles is roughly 40% RAG/evals/agents, 30% production systems, 20% model internals, and 10% behavioural, which means this round is often the one that decides the level you are offered.

---

## Lineage: past → present → future

**What came before.** The 2023 GenAI design interview was "draw RAG," and it was a bad interview because the answer was three boxes and everyone had memorised them. The architectures being drawn were genuinely simpler then: one embedding model, one flat vector index, top-k of 4, one prompt, one provider, and no eval. What killed that era was not intellectual dissatisfaction but a wave of production failures with a consistent shape. **Semantic-only retrieval failed on exact-match queries**, so a support bot could not find the article about error code `E-4021` because the embedding of a product code is meaningless; the fix was hybrid retrieval with BM25 and reciprocal rank fusion, and that is now table stakes. **Naive chunking destroyed tables and cross-page context**, so financial and legal RAG returned fragments that were individually fluent and jointly wrong. **Nobody could attribute a regression**, because prompt, model, chunker, embedding model, and top-k were all unversioned. And **costs were unmodelled**: the invoice arrived and nobody could decompose it. Every 2026 architecture pattern is a scar from one of those four.

**Where it stands now.** The reference architectures have converged enough that an interviewer expects specific components by name. **Retrieval** is hybrid (dense plus lexical) with a cross-encoder reranker over 50-200 candidates, filtered by metadata with tenant and ACL predicates pushed into the index rather than applied after. **Serving** is behind a gateway that owns routing, failover, spend, and caching, because the enforcement boundary has to be one the application cannot bypass. **Agents** are one agent with good tools inside a durable graph, checkpointed, with human approval on consequential actions. **Quality** is trajectory-level evals in CI, not vibes, and the sharpest number in the space is that agents evaluated only on final output pass 20-40% more test cases than trajectory evaluation reveals. **Observability** is OpenTelemetry with the `gen_ai.*` conventions, which as of the v1.42.0 release on 2026-06-12 live in a dedicated repository and are still Development status, so you pin the instrumentation and say so. The live disagreements worth naming rather than resolving: **vector database versus Postgres with pgvector**, where the honest boundary is that under roughly 5-10 million vectors pgvector on infrastructure you already run is usually correct and past that a dedicated engine earns its operational cost; **pipeline versus end-to-end VLM document parsing**, where cascades allow per-stage optimisation but suffer error propagation while single-pass VLMs avoid propagation and are harder to debug; and **how much of the platform to buy**, where the defensible line is that the golden dataset and the rubrics are your asset and the eval tool is not.

**Where it's heading.** **High confidence: cost becomes an SLO with an enforcement boundary rather than a monthly report.** Pre-call budget enforcement, per-tenant ledgers, and paged cost spikes are moving from bespoke to expected, and the framing that a 3 AM cost spike is an incident whether or not your runbook says so is now mainstream. **High confidence: prompts, harness config, and model pins become versioned artifacts with CI gates and pointer-flip rollback.** **Medium confidence: retrieval collapses into the agent** as tool-based iterative search with a code-graph or filesystem interface displaces one-shot top-k for the harder query classes; the reported evidence is real (a Tree-sitter knowledge graph over 31 repositories cutting agent token use ~10× and tool calls ~2.1×) but it is a different cost curve rather than a strict win. **Medium confidence: architectural injection defences** (CaMeL-style provenance-tracking interpreters, dual-LLM quarantine) reach mainstream harnesses; today they are the only defences with a real security argument and no mainstream harness ships them. **Low confidence, speculative: long-context models eating RAG.** They have not, cost scales with context, and "lost in the middle" is unsolved, so treat confident versions of this claim as fashion.

---

## Mental model

Every design in this module uses the same six slots, in the same order. Internalise the template, not the twelve instances, because in the room you will be asked about a thirteenth.

```
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ 1. CLARIFY      what does the number mean · read:write · latency contract │
  │                 who is the tenant · what is "correct" · blast radius      │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ 2. ARCHITECT    write path / read path drawn separately. Boxes with names. │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ 3. DECIDE       3-5 forks, each as "X over Y because Z, at the cost of W"  │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ 4. SIZE         QPS · bytes · tokens → cost/request → cost/month          │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ 5. BREAK        failure mode → OBSERVABLE SYMPTOM → mitigation            │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ 6. DEFEND       the 3 hardest follow-ups, answered before they're asked   │
  └───────────────────────────────────────────────────────────────────────────┘
```

A 45-minute round, allocated: **6 min clarify, 10 min architecture, 12 min the two or three decisions they care about, 6 min sizing and cost, 6 min failure modes, 5 min the follow-up they were always going to ask.** Two failure modes at either extreme: spending 20 minutes on requirements (looks like stalling) or drawing for 25 minutes before the first number (looks like a diagram enthusiast). And the GenAI-specific move that separates candidates: **produce cost per request without being asked.** In a conventional design nobody asks. Here it is half the design.

The three additions to remember as a triple:

```
PROBABILISTIC  → correctness is a measured distribution → EVAL is a component, not a phase
EXPENSIVE      → $0.01-0.30/req vs $0.0001 → COST MODEL is part of the architecture
SLOW           → 1-10 s vs 50 ms → streaming, caching, step reduction are ARCHITECTURE
```

---

## How it actually works

### Design 1 — Enterprise RAG over 10 million documents

**Clarify.** "10 million documents" is meaningless until converted: at ~6 pages and ~10 chunks of 400 tokens per document that is **~100M chunks, ~40B tokens**. Then: read-heavy or write-heavy (here 200k queries/day against ~30k new/changed docs/day)? Latency contract (p95 900 ms to first token, retrieval budget 350 ms)? Per-document ACLs, or is corpus access uniform? Freshness requirement (a new document searchable in under 5 minutes)? How many tenants, and is the index shared or per-tenant? What does "correct" mean, and is there any labelled data?

```
WRITE PATH                                        READ PATH
 sources (SharePoint, S3, Confluence, DB)          query
   │  CDC + scheduled crawl                          │
   ▼                                                 ▼
 dedupe (simhash) ─▶ parse/layout ─▶ chunk        query rewrite (HyDE opt) + ACL resolve
   │                                  │              │
   ▼                                  ▼              ├────────────┬──────────────┐
 doc registry (Postgres)          embed (BGE-M3,     ▼            ▼              ▼
 doc_id, acl, version, hash        self-hosted)   ANN dense    BM25 lexical   metadata
   │                                  │           (binary q.)  (OpenSearch)   prefilter
   ▼                                  ▼              └──────┬─────┘  tenant+acl pushed IN
 chunk store (Postgres, source of truth) ◀────────────┐     ▼
   │                                                   │  RRF fuse → top 150
   ▼                                                   │     ▼
 vector index (Qdrant, 8 shards x 3 replicas)          │  rescore full-precision vectors
   binary-quantized in RAM + int8 on disk              │     ▼
   │                                                   │  cross-encoder rerank (BGE-v2-m3)
   └──▶ nightly full rebuild to a shadow collection    │     ▼  top 8
        + alias swap (versioned index, not in-place)   └── prompt assembly (cited chunks)
                                                             ▼
                                                        LLM (streamed) ─▶ citation verifier
```

**Decisions.**
- **Dedicated vector engine over pgvector**, because 100M chunks is an order of magnitude past the point where pgvector on shared Postgres is comfortable; the usual boundary is ~5-10M vectors, and below it pgvector on infrastructure you already run is the correct answer. Cost: another stateful system to operate.
- **Binary quantization for the first stage, full precision for rescoring.** 1024-dim fp16 is 2 KB/vector, so 100M vectors is 200 GB before graph overhead, which does not fit in reasonable RAM. Binary at 1 bit/dim is 128 bytes/vector, so ~12.8 GB fits comfortably; retrieve 1,000 candidates on binary, rescore with full vectors from disk, then rerank. Cost: a recall hit at the first stage, which you must measure rather than assume, and a two-stage system to tune.
- **Hybrid over dense-only**, because product codes, error codes, and exact names are where dense-only humiliates you: the embedding of `E-4021` carries no signal. RRF fusion with k=60 is the boring correct default. Cost: a second index to operate and keep in sync.
- **ACLs pushed into the index as filter predicates, never applied post-retrieval**, because post-filtering top-k means a user with narrow permissions gets an empty result set from a system that found 10 perfectly relevant documents they cannot see. Cost: filtered ANN is slower and the filter cardinality distribution now matters to your p99.
- **Versioned index with alias swap over in-place updates**, because reindexing after an embedding-model change is a routine event, and in-place mutation makes it a multi-day migration with no rollback. Cost: 2× index storage during a swap.

**Scale and cost.**
```
INGEST (one-time backfill)
  100M chunks x 400 tok = 40B tokens embedded
  BGE-M3 self-hosted on A10G ~1.2k chunks/s → 8 GPUs x ~3 h ≈ 24 GPU-h ≈ $25-30
  (a commercial embedding API at $0.02/M tok would be ~$800: the self-host case is
   strongest exactly here, at backfill scale)
  parse/OCR: dominated by the doc pipeline, see Design 9
STEADY STATE
  30k docs/day changed → 300k chunks/day embed → trivial (<1 GPU-h/day)
  index: ~13 GB RAM (binary) + ~100 GB SSD (int8) + 3 replicas
QUERY (200k/day, peak ~12 qps)
  ANN binary 1000 cand  35 ms │ rescore 25 ms │ BM25 20 ms (parallel) │ RRF 2 ms
  cross-encoder 150→8   85 ms on a shared T4  │ total retrieval p95 ~190 ms
  LLM: 6.5k input (8 chunks x ~600 tok + prompt), 400 output
    = 6.5k x $3/M + 0.4k x $15/M = $0.0195 + $0.0060 = $0.0255/query
  200k x $0.0255 = $5,100/day = ~$153k/month. Say that number out loud: it is the
  moment routing stops being an optimisation and becomes the budget. See Design 12.
    with 55% of queries to a small model at 1/12 the price → ~$0.0128 avg → $77k/month
    with prompt caching on the frozen instruction prefix (~1.2k tok) → ~$74k/month
  infra: vector cluster ~$2.4k/mo, OpenSearch ~$1.1k/mo, rerank GPU ~$0.6k/mo
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Post-retrieval ACL filtering | Users with narrow scopes get "no results found" at a rate 5-10× the average; `results_after_filter=0` while `results_before_filter=10` in traces | Push tenant and ACL predicates into the ANN filter |
| Embedding-model change without reindex | Recall@10 drops 20-40 points overnight with no code change in the retriever; queries embedded with model B searched against an index built with model A | Model id is part of the index name; refuse to query on mismatch |
| Chunk boundary splits a table | Answers cite a row without its header, so the number is right and the label is wrong. Shows up as high judge scores and angry users | Layout-aware chunking, tables kept whole up to a hard cap, header propagation |
| Stale corpus | Answers cite a policy revoked last month. `chunk.indexed_at` p95 age climbing | Freshness SLO with a metric and an alert, not just a pipeline |
| Hot shard | One shard's p99 3× others; a tenant with 40% of the corpus | Shard by hash of `chunk_id`, not by tenant, and route tenant-filtered queries with a bloom-style shard hint |

**Three hardest follow-ups.** (1) *"500M chunks instead of 100M?"* Different architecture, not the same one scaled: binary index no longer fits one node's RAM, so you go multi-node with a scatter-gather coordinator and accept that p99 is now the slowest shard, plus tiered storage where cold tenants live on object-backed vectors. AWS's own worked example prices 500M vectors with 10M queries/month at ~$1,320/month against $11.38 for 10M vectors and 1M queries, which is a useful anchor and comes with a latency caveat: object-backed vector storage trades hundreds of milliseconds for that price. (2) *"How do you know retrieval is the problem and not the model?"* Separate the metrics. Recall@k and nDCG on a labelled retrieval set measure retrieval; answer-level judge scores measure generation; the diagnostic is answer quality conditioned on a known-good retrieval set. If quality is good with oracle context and bad with retrieved context, it is retrieval, and 80% of the time it is. (3) *"A document is deleted for legal reasons. What happens?"* Deletion has to propagate to the chunk store, both indexes, the semantic cache, any conversation transcripts that quoted it, and the eval fixtures. Tombstone in the registry, filter at query time immediately, and reconcile the indexes asynchronously, because ANN deletes are usually a soft-delete plus compaction rather than an immediate removal. If you cannot answer this you have never operated a RAG system under a legal team.

---

### Design 2 — Multi-tenant LLM gateway

**Clarify.** How many tenants and what is the fairness requirement (are they internal teams or paying customers with contractual quotas)? Is the quota in dollars or tokens, because that changes the design materially? What added latency is acceptable? Does it need to be in the request path for streaming, or can it be a sidecar? Who owns provider credentials after this exists, and is direct provider access blocked at the network level? Is the gateway a single point of failure you are allowed to create?

```
                 apps · agents · notebooks   (NO provider credentials anywhere)
                            │  virtual key (tenant, team, env, scopes)
                            ▼
   ┌──────────────────── GATEWAY (stateless, N replicas) ────────────────────┐
   │ authn/authz ─▶ admission: RPM/TPM/$ buckets ─▶ router ─▶ cache ─▶ proxy  │
   │      │              │ local token bucket             │        │          │
   │      │              │ + Redis Lua for global         │        │          │
   │      ▼              ▼                                ▼        ▼          │
   │  audit log     pre-call ESTIMATE debit          semantic  provider client │
   │                (reconciled post-call)            cache    circuit breaker │
   │                                                          + failover chain │
   └──────┬─────────────────────┬──────────────────────────────┬──────────────┘
          │                     │                              │
          ▼                     ▼                              ▼
     Redis (buckets,        Postgres (ledger,           providers: Anthropic ·
     idem keys, cache)      virtual keys, policy)       Bedrock · OpenAI · self-host vLLM
          │
          └──▶ OTel → cost ledger (ClickHouse) → per-tenant dashboards + nightly reconcile
```

**Decisions.**
- **In-path proxy over a sidecar/SDK**, because budget and quota enforcement that an application can bypass is advisory. The gateway plus a `NetworkPolicy` denying direct provider egress is the enforcement boundary. Cost: you have created a critical path component, so it needs its own SLO, multi-AZ, and a break-glass path.
- **Two-tier rate limiting: local token bucket plus Redis for the global view.** A pure Redis check adds a round trip to every request and makes Redis a hard dependency; local-only permits N× overshoot with N replicas. Admit locally against a leased share of the global budget, refresh the lease every 200 ms. Cost: bounded overshoot during a lease window, which you should state as a number rather than hide.
- **Pre-call estimate, post-call reconcile**, because token counts before completion are estimates and only the response carries true output tokens. Debit an estimate at admission, true it up on response, and let a tenant go slightly over rather than blocking on exact accounting. Cost: a reconciliation job and a drift metric; over 3% drift is a bug.
- **Tokens and dollars as separate quota axes.** LiteLLM's built-in budgets are dollar-based, so if you sell token quotas you need a shim converting tokens to a dollar estimate before the internal check. Say this explicitly; it is a real integration detail that signals you have deployed one.
- **Failover chain, not retry-in-place.** A provider 429 retried against the same provider amplifies the incident. Route to the next provider in the chain with a circuit breaker, and be explicit that cross-provider failover means the response distribution changes mid-incident, which your evals must cover.

**Scale and cost.**
```
500 tenants · 40M requests/month · peak 900 rps · p50 request 4.5k in / 300 out
GATEWAY BUDGET
  added latency p99 <= 15 ms (auth 1 · buckets 2 local / 4 with Redis lease refresh
  · routing 1 · logging async) — guardrails are NOT in this budget, see Design 8
  streaming: must not buffer; account tokens on stream close, and handle client
  disconnect (partial cost still billed by the provider — a real revenue leak)
SIZING  900 rps at ~2k rps/replica (I/O bound, 2 vCPU) → 6 replicas + 50% headroom = 9
  Redis: ~900 rps x 2 ops = 1.8k ops/s, trivial; size for the cache, not the buckets
COST OF THE GATEWAY ITSELF
  9 x 2 vCPU pods ~$450/mo · Redis ~$300/mo · ClickHouse ledger ~$600/mo ≈ $1.4k/mo
  against a $150k/mo provider spend → 0.9% overhead. This ratio is the whole business case.
SAVINGS IT UNLOCKS   routing 40-85% (Design 12) · semantic cache 20-45% hit (Design 7)
  · prompt caching on frozen prefixes 30-40% of input cost
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Noisy neighbour | One tenant's batch job at 3 AM; every other tenant's p99 triples and provider 429s spike | Per-tenant RPM/TPM buckets plus a global reserve pool no single tenant can exceed |
| Gateway becomes the outage | All AI features down, gateway 5xx, providers healthy | Multi-AZ, no shared-fate Redis, and a documented break-glass direct-provider path with audited credentials |
| Retry amplification | Provider 429 rate climbing superlinearly with your own retries; total requests 3× intended | Circuit breaker plus failover chain, exponential backoff with jitter, and retry budgets |
| Streaming cost leak | Ledger under-reports 5-15% versus the provider invoice | Account on stream close AND on client disconnect; reconcile nightly, alert at 3% drift |
| Quota bypass | A team's spend appears in the invoice but not the ledger | Network-level egress denial; audit for any pod holding a provider key |

**Three hardest follow-ups.** (1) *"A tenant needs a dedicated capacity guarantee."* Reserved capacity is a different product from fair sharing: provisioned throughput at the provider (or a dedicated vLLM pool) mapped to a tenant-specific route, with the shared pool as overflow and an explicit policy on whether overflow is allowed. Do not try to express a hard guarantee with a soft rate limiter. (2) *"How do you roll out a model change across 500 tenants?"* Not at once. The gateway is the natural canary point: per-tenant model pins, a default that moves in waves, and quality scored per wave. Tenants on contractual model commitments never move without notice, which means the gateway needs a model-pin-per-tenant concept from day one and retrofitting it is painful. (3) *"Attribute cost to a feature, not just a tenant."* Requires a propagated context tag (`tenant`, `team`, `feature`, `run_id`) set at the caller and carried on every span and ledger row. Bolt this on later and you will have six months of unattributable spend, which is the single most common regret reported by teams who built a gateway.

---

### Design 3 — Agent orchestration platform

**Clarify.** How many distinct agents, owned by how many teams? Are runs seconds, minutes, or hours, because that is three different schedulers? Does any agent execute code, which decides whether you need a sandbox tier? Is human approval required, and what is the maximum wait? Who is responsible when an agent misbehaves, the platform or the agent owner? Self-serve or curated onboarding?

```
   CONTROL PLANE                                  DATA PLANE
 ┌────────────────────────────┐        ┌──────────────────────────────────────┐
 │ agent registry (versioned  │        │ scheduler / queue (per-tenant, per-  │
 │  manifest: tools, model,   │───────▶│  priority; KEDA scales consumers)    │
 │  budget, perms, evals)     │        │            │                         │
 │ policy service (perm rules)│        │            ▼                         │
 │ prompt registry            │        │  ┌── RUNNER POOL (CPU, no GPU) ────┐ │
 │ approval service           │◀───────┤  │ durable graph + checkpointer    │ │
 │ eval service (gate on      │        │  │ tool contract · budget · traces  │ │
 │  register + on deploy)     │        │  └──────┬──────────────┬───────────┘ │
 │ quota/budget service       │        │         │              │             │
 └────────────┬───────────────┘        │         ▼              ▼             │
              │                        │  SANDBOX POOL     LLM GATEWAY        │
              ▼                        │  (gVisor/Firecracker, no egress)     │
   Postgres: manifests, checkpoints,   └──────────────────────────────────────┘
   approvals, ledger, audit                        │
                                                   ▼
                              OTel → traces + trajectory store (ClickHouse)
                                                   │
                                    ┌──────────────┴──────────────┐
                                    ▼                             ▼
                          eval sampling into goldens      cost + SLO dashboards
```

**Decisions.**
- **Control plane / data plane split**, because the properties differ: the control plane is low-QPS, strongly consistent, and must be available for anything to start; the data plane is high-throughput and can be regional and eventually consistent. Cost: two things to operate, and a hard dependency of the second on the first.
- **A registry with a manifest, and registration gated by evals.** An agent is a versioned artifact declaring its tools, model pin, budget ceiling, permission scopes, and eval suite. You cannot deploy an agent without an eval suite. Cost: friction on onboarding, which is the point; without it you become a hosting provider for other people's incidents.
- **Durable execution over in-process loops**, non-negotiably, because human approval measured in days and runs measured in hours both require the state to outlive the process. Choose LangGraph-plus-checkpointer if agent primitives dominate, or Temporal/Restate if durability guarantees and timers dominate; the common 2026 shape is the pair pattern, a framework engineers write inside an engine the platform team operates.
- **Separate sandbox tier for code execution**, isolated at the kernel boundary (gVisor or Firecracker) with no network egress, because the alternative is model-directed code running next to your credentials. Cost: a second pool, cold-start latency, and an artifact-passing protocol.
- **Platform owns boundaries, teams own behaviour.** Budgets, permissions, egress, traces, and the eval gate are platform-enforced. Prompts, tools, and topology are the team's. Stating this split is the answer to "who is on call," which is the question behind the question.

**Scale and cost.**
```
40 agent definitions · 300 teams · 2M runs/month (~0.8 rps mean, ~6 rps peak)
run duration: p50 12 s · p95 45 s · p99.9 6 h (a few batch agents)
RUNNERS  6 rps x 45 s = 270 concurrent at peak; 50 concurrent/pod → 6 pods + headroom = 10
  terminationGracePeriodSeconds 600, preStop drain, KEDA on queue depth
CHECKPOINTS  2M runs x ~5 x 40 KB = 400 GB/month → partition daily, retain 30/7 days
COST  runs avg $0.09 (4 calls) → $180k/month provider spend
  platform infra: runners $700 · sandboxes $1.2k · Postgres $900 · ClickHouse $1.1k
  · gateway $1.4k ≈ $5.3k/month, ~3% of spend
  the platform's business case is NOT infra savings, it is the eval gate and the
  budget boundary: two prevented cost incidents pay for a year
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| One agent starves the pool | Queue age climbing for all tenants while one agent holds 80% of runner slots | Per-tenant concurrency caps and priority queues; a runaway agent hits its own ceiling |
| Long-running runs killed by deploys | Failure rate spikes for exactly the duration of a rollout; p99.9-duration agents fail preferentially | Checkpointing plus drain plus grace period above p99.9 duration; separate rollout policy for runners |
| Control-plane outage stops everything | No runs start; runners idle and healthy | Cache manifests and policy in the runner with a TTL, fail-closed on permissions but fail-open on manifest fetch |
| Sandbox escape or egress | Outbound connections from the sandbox CIDR to anything | Kernel-level isolation, zero-egress NetworkPolicy, alert on any egress attempt as a security event |
| Trajectory store cost | Observability bill exceeding the model bill | Sample: 100% of failures and approvals, 5-10% of successes, aggressive TTL on span payloads |

**Three hardest follow-ups.** (1) *"Team A's agent calls Team B's agent. What breaks?"* Identity propagation and budget accounting. Whose permissions apply to the nested call, and whose budget is debited? Answer: the *originating* principal's permissions with the callee's scopes intersected, never unioned, and a hierarchical budget where the child's spend counts against the parent's ceiling. Without this you get privilege escalation by composition, which is the enterprise MCP identity-propagation gap in a different costume. (2) *"An agent's quality regresses in production. Who finds out, and how?"* The platform, from live-sampled evals per agent version, not the team from a complaint. Which means the platform owns the trajectory store, the sampling, and the per-agent scoreboard, and the team owns the fix. If your answer is "the team monitors it" you have built hosting, not a platform. (3) *"Do you let teams bring their own framework?"* Pragmatically yes for the reasoning layer, no for the boundaries. Enforce the interface: the runner injects the gateway endpoint, the checkpointer handle, the permission client, and the tracer, and refuses to run anything that reaches around them. Trying to standardise the framework loses; standardising the boundaries wins.

---

### Design 4 — Agent memory service

**Clarify.** What kind of memory: session continuity, user preferences, or organisational knowledge? These are three products. Is a wrong memory a bug or a catastrophe (support agent versus medical)? What is the read latency budget as a share of the agent's total? Retention and right-to-erasure requirements? Who writes, the agent autonomously or an extraction pipeline? Multi-agent shared memory or per-agent?

```
 WRITE (async, off the critical path)          READ (sync, on the critical path)
  session end / turn boundary                  agent turn start
        │                                            │  (user_id, query, agent_id)
        ▼                                            ▼
   extraction worker                            retrieval: hybrid
   LLM extracts typed facts:                     ├─ vector top-k over facts (pgvector)
    entity · preference · decision · task        ├─ recency + importance decay
   NEVER free-text "notes"                       └─ graph 1-2 hop expansion (optional)
        │                                            │
        ▼                                            ▼
   conflict resolution                          rerank + budget: <= 1.5k tokens injected
    (supersede by recency + source rank,             │
     keep BOTH with valid_from/valid_to for          ▼
     temporal facts)                            labelled block in the prompt:
        │                                       <memory confidence="0.8" source="...">
        ▼
   store: Postgres (facts, provenance, embeddings via pgvector)
          + optional graph edges
        │
        └──▶ audit log · per-user purge endpoint · TTL job
```

**Decisions.**
- **Typed facts over free-text notes.** A free-text memory store is an unauditable, unpurgeable, un-diffable blob that poisons every future session. Typed rows have provenance, confidence, a valid-time interval, and a delete path. Cost: extraction is lossy and needs its own eval.
- **Write asynchronously, read synchronously.** Extraction is an LLM call you cannot afford in the turn latency budget. Cost: a memory written at the end of turn N may not be visible at the start of turn N+1, so session-scoped state stays in the checkpoint, not in memory.
- **Bi-temporal facts over overwrite.** "Prefers email" superseded by "prefers Slack" is not a correction, it is a change over time, and collapsing the two loses the ability to answer "what did they prefer in March." Zep/Graphiti's whole design bet is on this. Cost: query complexity, and graph traversal at ~50-150 ms against ~10-50 ms for vector-only.
- **A hard token budget on injected memory.** 1.5k tokens, ranked. Unbounded memory injection is how you get quadratic cost growth and "lost in the middle" degradation simultaneously. Cost: a ranking function you have to tune, which is a retrieval problem inside your memory service.
- **Ship without cross-session memory first.** This is the senior position and it is worth stating as a decision: a wrong fact in memory is a bug that reproduces forever and is invisible in single-session tests. Measure how often the agent re-derives the same conclusion, then add memory against that number.

**Scale and cost.**
```
5M users · 40M sessions/month · ~4 facts extracted per session → 160M facts/month
  with dedupe/supersede, steady state ~200M live facts (heavy churn)
READ  p95 60 ms budget: pgvector HNSW over a user-partitioned index 15-25 ms
      + rerank 10 ms + assembly 5 ms.  Partition by user_id: per-user candidate
      sets are tiny (hundreds), which is why this is cheap and why a global index
      would be the wrong design.
WRITE  40M extractions/month x ~1.2k in / 200 out on a small model
       = 40M x ($0.0004 + $0.0003) ≈ $28k/month  ← extraction, not storage, is the cost
       mitigations: extract only on session end (not per turn), batch, skip sessions
       under 3 turns (~40% of traffic), and a cheap classifier gate before the extractor
STORAGE  200M facts x ~1.5 KB row + 768-dim int8 vector (768 B) ≈ 450 GB
VENDOR ANCHORS (all self-reported, different benchmarks, do not compare directly)
  Mem0: 92.5% LoCoMo, 94.4% LongMemEval, <7k tokens/retrieval, 91% lower p95 (1.44 s
        vs 17.12 s) vs full-context
  Zep/Graphiti: 63.8% LongMemEval vs Mem0's 49.0% in their head-to-head
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Wrong fact persisted | The same wrong answer across sessions, reproducing after a restart; user complaints that "it keeps thinking I'm on the enterprise plan" | Confidence thresholds on write, provenance on every fact, a user-visible memory view, and a purge endpoint |
| Memory poisoning via injection | A fact whose provenance is a retrieved document rather than a user statement | Never extract facts from untrusted content; source rank in the conflict resolver; refuse writes from tool observations |
| Cost dominated by extraction | Memory service spend exceeds the agent's own model spend | Extract at session end only, gate on session length, use a small model, batch |
| Unbounded injection | Input tokens per turn climbing linearly with account age | Hard token cap plus ranking; alert on injected-memory p99 tokens |
| Cross-tenant leak | A fact retrieved for user A sourced from user B's session | Partition by user, enforce the predicate in the query layer, and add a test that asserts it |

**Three hardest follow-ups.** (1) *"GDPR erasure request."* Deletion must reach the fact rows, the embeddings, the graph edges, the extraction job logs, the trace payloads, any downstream caches, and the eval fixtures if a real user's data leaked into them. That is a data-lineage problem, not a `DELETE` statement, and the answer is a per-user partition key propagated everywhere plus a documented, tested erasure job with a completion report. (2) *"Two agents disagree about the same fact."* Facts need a source rank and a scope: user-asserted beats agent-inferred, and organisational facts are a separate namespace from personal ones. Shared mutable memory across agents is a distributed-consistency problem you should decline by default; give each agent a read view of a shared, curated namespace and a private write namespace. (3) *"Prove memory helps."* An A/B on task success with memory on and off, plus a "re-derivation rate" metric (how often the agent recomputes something already in memory). If you cannot show a lift, you have added a persistent-bug surface for nothing, and the honest answer includes that this experiment often comes back flat for the first iteration.

---

### Design 5 — Eval platform

**Clarify.** Are we evaluating models, prompts, retrieval, or agent trajectories, because trajectories are architecturally a different problem? Is this a CI gate, an offline research tool, or production monitoring, and ideally all three sharing one dataset store? Who writes the datasets, engineers or domain experts? Is human labelling in scope? Do we need to evaluate on production data, and what does that mean for PII?

```
  DATASETS                       EXECUTION                      SCORING
 ┌───────────────┐          ┌───────────────────┐        ┌────────────────────┐
 │ dataset store │          │ runner (parallel, │        │ deterministic      │
 │ versioned,    │─────────▶│ sandboxed, seeded)│───────▶│  schema · regex ·  │
 │ immutable     │          │ N seeds, T=0      │        │  tool-order · cost │
 │ + fixtures    │          │ replays fixtures  │        ├────────────────────┤
 └───────┬───────┘          └─────────┬─────────┘        │ trajectory         │
         │                            │                  │  must_call, order, │
         │  live-traffic sampler      │                  │  must_not, F1      │
         │  (10 cases/wk, human       ▼                  ├────────────────────┤
         │   reviewed, PII scrubbed)  results store      │ LLM-as-judge       │
         │                            (ClickHouse)       │  pinned model +    │
         ▼                            │                  │  calibration set   │
   annotation UI ◀───────────────────┘                  ├────────────────────┤
   (domain experts label,                                │ human review queue │
    disagreement → rubric fix)                           └─────────┬──────────┘
                                                                   ▼
   CI GATE: PR touching prompts/tools/graph/model-pin → run suite → block or pass
   PROD MONITOR: same scorers on sampled live traffic → weekly scoreboard
```

**Decisions.**
- **One dataset store shared by CI and production monitoring**, because a divergent set means your gate and your monitor disagree and you trust neither. Cost: the store needs versioning, PII handling, and access control from day one.
- **Deterministic scorers first, judges last.** Schema validity, citation resolution, tool-order assertions, cost adherence: cheap, unambiguous, and they catch most regressions. Judges only where no computational check exists. Cost: writing deterministic scorers is real work that people skip because judges feel faster.
- **Trajectory scoring as a first-class scorer type**, not an afterthought, because outcome-only evaluation of agents passes 20-40% more cases than trajectory-level evaluation reveals. Cost: your dataset format now includes an expected path, which is more expensive to author and to maintain as the agent legitimately changes.
- **Pinned judge model plus a human-labelled calibration set.** A judge is a model, so it drifts, and an ungated judge upgrade silently rebaselines your entire history. 40 calibration cases and an agreement metric. Cost: recalibration work on every judge change.
- **Multiple seeds with the median, not single-run pass/fail**, because a stochastic system's single run is noise. 3 seeds at temperature 0 is the cheap default; report variance, not just the point estimate.

**Scale and cost.**
```
400 suites · avg 90 cases · 12k CI runs/month → ~1.1M case executions/month
per case: ~1 agent run ($0.05) + judge ($0.004) ≈ $0.054 → ~$60k/month
  ← this is the number that surprises people: the eval platform's model spend is
    a material fraction of production spend, and it is the first thing finance cuts
CONTROLS  cache case results keyed by (dataset_ver, prompt_hash, model, seed, code_sha):
  typical 60-70% hit rate on a PR that touched one prompt → ~$20k/month
  tiered suites: smoke 20 cases (~2 min, every push) · full 140 (~11 min, on PR)
  · nightly 400+ · weekly regression across all model candidates
LATENCY  wall clock is the adoption gate. Above ~15 min, engineers stop waiting and
  start merging around it. Parallelism 8-16, per-case timeout, fail fast on the
  critical-safety subset.
STORAGE  1.1M executions x ~30 KB trace = 33 GB/month; keep failures 90 d, passes 14 d
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Golden set drift | Gate green for months while production quality complaints rise | Continuous live sampling into the set, human reviewed; track set age and coverage by intent |
| Judge drift | Historical scores shift after a judge upgrade; the same case scores 3.8 then 4.3 | Pin the judge, gate its upgrade on the calibration set, store the judge version with every score |
| Gate too slow | Merges with `[skip-evals]`; gate effectively off | Tiered suites, result caching, and an alert on skip-rate |
| Flaky cases erode trust | Same case passes and fails across seeds; engineers learn to re-run until green | Quarantine flaky cases automatically at >20% variance across seeds; fix or delete, never ignore |
| Overfitting to the set | Eval scores climb, production quality flat | Hold out 20% never used for iteration; rotate; track the correlation between eval delta and production metric delta |

**Three hardest follow-ups.** (1) *"Your eval scores went up and production got worse."* Overfitting, or the eval set does not represent traffic. The check is a correlation metric between eval-score delta and production-metric delta over the last N releases; if it is weak, your gate is decorative and the fix is a holdout plus traffic-representative sampling. Being able to say "my gate has a measured correlation of X" is a level marker. (2) *"Who owns the datasets?"* Domain experts author cases, engineers author scorers, and the platform owns the format and the gate. Engineer-authored datasets encode what engineers think matters, which is where "we tested the happy path" comes from. This is an organisational answer to a technical question and it is the correct one. (3) *"How do you evaluate something with no ground truth, like a summary?"* Decompose into checkable properties rather than reaching for a judge on overall quality: factual consistency against the source (entailment-checkable), coverage of required elements (checkable against a rubric checklist), absence of content not in the source, and length and format compliance. Then a judge on the residual, with pairwise comparison against a reference rather than absolute scoring, because pairwise is far more stable.

---

### Design 6 — Prompt management and versioning

**Clarify.** How many prompts, and are they authored by engineers or by non-engineers (that decides whether git is sufficient)? Do prompts need to change without a deploy, and is that a feature or a hazard? Do you need per-tenant prompt variants? Is there a compliance requirement to reproduce exactly what was sent for a given past request?

```
  AUTHOR                    REGISTRY                        RUNTIME
 ┌──────────┐          ┌────────────────────────┐      ┌───────────────────────┐
 │ git PR   │─────────▶│ immutable versions,    │      │ app resolves          │
 │ (source  │          │ content-addressed      │◀─────│  name@semver → hash   │
 │  of      │  CI:     │  prompt_id@1.14.0      │      │ verifies hash         │
 │  truth)  │  eval    │  = sha256(template)    │      │ local cache + TTL     │
 └──────────┘  gate    ├────────────────────────┤      │ FAIL CLOSED to the    │
      ▲        (block) │ deployment pointers:   │      │  last known good      │
      │                │  prod → 1.13.2         │      └──────────┬────────────┘
 ┌──────────┐          │  canary(5%) → 1.14.0   │                 │
 │ web UI   │─────────▶│  staging → 1.14.0      │                 ▼
 │ (non-eng │  same    │ per-tenant overrides   │      every request logs
 │  authors)│  gate    └───────────┬────────────┘      prompt_id + version + HASH
 └──────────┘                      │                             │
                                   ▼                             ▼
                        rollback = POINTER FLIP (seconds)   traces + eval linkage
```

**Decisions.**
- **Git as the source of truth, registry as the distribution mechanism.** Prompts are code: they change behaviour, they need review, they need diffs. A UI-only registry with no git backing produces prompts nobody reviewed. But git alone cannot flip a pointer in seconds during an incident, hence both. Cost: the sync between them is a real system with a real failure mode.
- **Immutable, content-addressed versions.** `prompt@1.14.0` resolves to a hash and the hash is on every trace. Editing in place is the single most common cause of "it was better last week" being unanswerable. Cost: no hotfix-by-edit, which is the intended constraint.
- **Deployment pointers separate from versions**, so rollback is a pointer flip and not a build. If rolling back a prompt requires CI, your MTTR is a CI run.
- **Fail closed to the last known good on registry unavailability.** A prompt registry that can take down every AI feature is a bad trade; cache locally with a TTL and serve stale rather than erroring. Cost: a stale prompt can persist through an incident, so alert on cache age.
- **The eval gate applies identically to UI-authored and git-authored changes.** The moment non-engineers can ship a prompt without the gate, the gate is theatre. Cost: friction for the exact people who wanted the UI, and you should say that out loud rather than pretend it is free.

**Scale and cost.**
```
2,000 prompts · ~40 changes/week · 500 rps of resolution traffic
RESOLUTION  local LRU cache, TTL 60 s → registry sees ~2k QPS/60 ≈ 35 rps. Trivial;
  the registry is not a scaling problem, it is an availability and correctness problem.
STORAGE  negligible (2k prompts x ~50 versions x ~8 KB ≈ 800 MB)
COST OF THE PIPELINE  the eval gate, not the registry: 40 changes/week x ~$9/run
  = ~$1.5k/month, plus the canary's quality-scoring judge calls
CANARY WINDOW ARITHMETIC (the number people miss)
  to detect a 3 pp judge-score delta at ~95% confidence you need n ≈ 400 scored
  sessions. At 5% canary on 8k sessions/day that is 400/day → a ONE-DAY floor on
  detection, regardless of tooling. Want faster? Raise the canary share and accept
  more exposure. That is the actual tradeoff.
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Prompt edited in place | Two requests in the same minute behave differently with the same version string; the hash differs | Immutability enforced at write; reject a version whose hash already exists with different content |
| Registry outage | Every AI feature erroring on prompt resolution | Local cache, fail closed to last known good, alert on cache-age p99 |
| Silent drift via templating | Prompt version identical, behaviour changed; the rendered prompt hash differs because an interpolated variable changed shape | Hash the *rendered* prefix, not just the template, and log both |
| Multi-change canary | Regression detected, cause ambiguous, bisect takes a week | One change per canary. The canonical case is Anthropic's April 2026 postmortem: three independent harness changes, no model change, a week of diagnosis |
| Per-tenant sprawl | 200 tenant-specific variants, none evaluated | Cap variants, require an eval suite per variant, expire unused overrides |

**Three hardest follow-ups.** (1) *"Reproduce exactly what was sent for a request from six months ago."* You need the rendered prompt hash plus enough to reconstruct it: prompt version, template hash, variable values (or a hash of them plus retention of the inputs), model version, tool-registry hash, and sampling parameters, all on the trace. Retaining the full rendered prompt is the simple answer and it is a PII liability, so the usual compromise is hash-plus-inputs with a short retention window on the raw text. Say the tradeoff. (2) *"Non-engineers want to ship prompts on Friday afternoon."* The honest answer is a policy answer: the gate applies, the canary applies, and the canary window has a one-day floor, so Friday afternoon changes go out Monday. If the business needs same-day prompt changes, they are buying a higher exposure canary and you should price it as such rather than removing the gate. (3) *"Are prompts config or code?"* Code, and the reason is that they change behaviour without changing the type system, which makes them more dangerous than config, not less. So they get review, tests, versioning, canaries, and rollback. The counter-argument (that treating them as code slows iteration to a crawl) is real, and the resolution is tiered risk: a copy tweak in a non-critical surface can ship on a fast path with deterministic-only gating, while a system prompt on the agent path cannot.

---

### Design 7 — Semantic cache

**Clarify.** What fraction of traffic is genuinely repeated, because a cache on a low-repetition workload is negative value? Is a near-miss answer acceptable, and who bears the cost when it is wrong? Is the corpus behind the answer static or changing, because staleness in a cached RAG answer is a correctness bug? Per-tenant isolation required? Are we caching the final answer or intermediate retrievals?

```
   query ──▶ normalize (lowercase, strip, canonicalize entities)
              │
              ├──▶ EXACT/PREFIX CACHE (hash) ──── hit ──▶ return   (always safe)
              │        miss
              ▼
        embed query (small model, ~8 ms)
              │
              ▼
   ANN over cached-query vectors, scoped to (tenant, corpus_version, model, prompt_hash)
              │
        sim >= threshold?  ── no ──▶ MISS ──▶ LLM ──▶ write-back (with TTL)
              │ yes                                        │
              ▼                                            │
        VALIDATE the hit:                                   │
          corpus_version match · not TTL-expired            │
          · optional cheap entailment check                 │
              │ pass                     │ fail            │
              ▼                          └──▶ treat as MISS ┘
          return cached answer  (log as semantic_hit for audit)
```

**Decisions.**
- **Exact and prefix caching first, semantic last.** Exact-match and provider-side prompt caching are correctness-preserving and give you most of the money; semantic caching trades correctness for cost. Order matters and getting it backwards is a common mistake.
- **The cache key includes far more than the query.** Tenant, corpus version, model version, prompt hash, and any user-specific context. A cache keyed on query alone will serve tenant A's answer to tenant B, which is the worst bug in this design and it is easy to ship.
- **Threshold set by measurement, per embedding model.** Reported optima are model-specific: ~0.83 for MPNet and ~0.78 for Albert; GPTCache's own suggested 0.7 is too loose in practice and the safer procedure is to start near 0.92, watch false positives for 48 hours, and tune down in 0.01 steps. Cost: a labelled near-miss set, which nobody wants to build and which is the whole safety argument.
- **Validate the hit, do not just return it.** At minimum a corpus-version and TTL check; optionally a cheap entailment check that the cached answer still addresses the query. Cost: latency on the hit path, which erodes the benefit, so measure the net.
- **Never cache anything user-specific or authorisation-dependent.** If the answer depends on who is asking, semantic caching is the wrong tool and a per-user cache is the right one.

**Scale and cost.**
```
1M queries/day · $0.026/query uncached → $26k/day baseline ($780k/mo) for a large RAG
HONEST HIT RATES  20-45% for most workloads; 30-70% on FAQ-shaped traffic.
  Vendor claims of 90%+ come from datasets constructed with heavy repetition.
  One documented production case: $47k → $12.7k/month with hit rate 18% → 67%,
  which is real and also a workload with unusually high repetition.
AT 30% HIT RATE
  savings 0.30 x $780k = $234k/month gross
  cost of the cache: embed 1M/day at ~$0.00002 = $20/day · vector store ~$400/mo
  · Redis ~$300/mo → ~$1.3k/month.  Net strongly positive AT THAT HIT RATE.
AT 8% HIT RATE (a low-repetition workload)
  savings $62k/month, still positive on cost, but you have added a correctness
  risk surface for an 8% discount. This is the case where you should decline.
LATENCY  hit: ~15 ms (embed 8 + ANN 5 + validate 2) vs 2,400 ms miss → the latency
  win is often the better argument than the cost win, and it is the one to lead with
  for user-facing surfaces.
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Near-miss served | User asks about product X, gets the answer for product Y. Aggregate quality metrics flat, individual complaints specific and confident | Raise the threshold, add entity-match validation, audit a sample of hits weekly with a human |
| Cross-tenant serve | A tenant sees another's data in an answer. Catastrophic, and silent | Tenant in the cache key and in the ANN filter; a test that asserts it; namespace-per-tenant if the blast radius warrants |
| Stale answer after a corpus update | Answers cite a document that changed yesterday; `corpus_version` on the hit is behind | Corpus version in the key; invalidate by version bump rather than by TTL alone |
| Cache poisoning | An adversarial query-answer pair written to the cache and served to others | Only cache responses that passed output guardrails; never cache a response from a run with untrusted content in context |
| Hit rate looks great, quality dropped | Hit rate 70% after a threshold change, judge scores down 4 points | Track hit rate and hit *quality* as two metrics; a hit-rate improvement with no quality audit is not an improvement |

**Three hardest follow-ups.** (1) *"How do you audit hit quality?"* Sample hits, re-run the miss path in shadow, and compare with the judge. A 2-5% shadow sample gives you a continuous false-positive estimate for a small cost, and it is the only way to know your threshold is still right after an embedding-model change. Teams that skip this discover their threshold went stale when a customer escalates. (2) *"Cache the retrieval instead of the answer?"* Often better. Caching retrieved chunks keyed on the normalised query is far safer because the LLM still runs and can decline, so a near-miss degrades to slightly worse context rather than a wrong answer, and you still save the (expensive) reranker while paying the (cheaper) generation. Lower savings, much lower risk, and this is the answer that shows judgement. (3) *"Would you put this in front of an agent?"* Cautiously and not on tool calls. Caching a tool result across sessions is a correctness bug when the tool reads mutable state, and caching an agent's intermediate reasoning defeats the point of the loop. The defensible use is caching the first retrieval turn of a session on a static corpus.

---

### Design 8 — Guardrail service

**Clarify.** What are we actually preventing: harmful output, PII egress, prompt injection, off-topic use, or policy violation? Each has a different detector and a different cost. Is this advisory (log and alert) or blocking? What latency can the product absorb, and is it in the streaming path? What is the acceptable false-positive rate, because a 2% false-block on a support product is a visible outage to real users? Who tunes policy, engineering or trust-and-safety?

```
  INPUT RAIL (parallel with retrieval, so it is often free on the wall clock)
   user input ──┬──▶ PII detect/redact (regex + NER)      ~8 ms
                ├──▶ injection classifier (small model)   ~25 ms   ┐ run
                ├──▶ jailbreak/topic classifier           ~25 ms   ┤ concurrently
                └──▶ policy rules (deny patterns, tenant) ~1 ms    ┘
                        │ aggregate: block | redact | flag | allow
                        ▼
                     [ AGENT / LLM ]  ← untrusted content wrapped + labelled here
                        │
  OUTPUT RAIL (streaming-aware, this is the hard one)
                        ├──▶ buffer-and-scan windows (N tokens) ~15 ms/window
                        ├──▶ PII egress · secret patterns
                        ├──▶ citation/grounding check (deterministic)
                        └──▶ policy classifier on the full response
                        │
                        ▼  allow | rewrite | block-and-substitute | escalate-to-human
                     client
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ NOT PART OF THIS SERVICE, and this is the point: the permission engine   │
  │ and network egress policy. Guardrails are FILTERS. Those are BOUNDARIES. │
  └──────────────────────────────────────────────────────────────────────────┘
```

**Decisions.**
- **Parallel detectors, not a chain**, because latency is additive in a chain and the checks are independent. Aggregate with a policy over the results. Cost: you pay for every detector on every request even when the first would have blocked.
- **Input rail runs concurrently with retrieval**, which makes it nearly free on the wall clock. This is the single best latency trick in the design and candidates rarely mention it. Cost: you do retrieval work you may discard.
- **Streaming output rails scan windows, and accept that a blocked response may be partially delivered.** The alternative is buffering the whole response, which destroys time-to-first-token. Decide and state it: for a support product, window scanning with a visible retraction is usually better than a 4-second blank screen. Cost: a partially-delivered violation is possible, which is a product decision, not an engineering one.
- **Deterministic checks before classifiers.** Regex for secrets and card numbers, citation resolution for grounding, schema validation for structure. Cheap, exact, and they are the ones you can defend in an audit. Classifiers handle the residual. Cost: nothing, which is why the ordering is not really a tradeoff and skipping it is just a mistake.
- **Be explicit that this service is not a security boundary.** Guardrails reduce probability. The permission engine and egress policy bound damage. A candidate who conflates the two is the red flag in this design.

**Scale and cost.**
```
900 rps · p99 added latency budget 60 ms input / 25 ms per output window
  NeMo Guardrails reports sub-50 ms per programmable check on GPU; a small
  BERT-class injection classifier is ~15-30 ms on CPU at batch 1, ~8 ms batched on GPU
SIZING  900 rps x 3 model detectors = 2,700 inferences/s
  on GPU with dynamic batching (batch 32, ~8 ms) → ~4k inf/s per T4 → 1 GPU + 1 for HA
  on CPU → ~40 cores for the same, which is usually more expensive: this is one of the
  few places in a GenAI stack where the GPU is in YOUR service, not behind the gateway
COST  2 x T4 ~$550/mo + serving pods ~$300/mo ≈ $850/mo at 900 rps = $0.00004/request
  against a $0.026 LLM call → 0.15%. Guardrails are cheap; the expensive thing is the
  FALSE POSITIVE RATE.
FALSE POSITIVES  at 900 rps, a 1% false-block rate = 9 blocked legitimate requests/s
  = 780k/day. State the FP budget as a number in the design (target <0.2%) or you
  will ship an outage that looks like a safety feature.
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Guardrail becomes the latency story | p95 rose 400 ms after launch; the guardrail span dominates the trace | Parallelise, run input rails concurrently with retrieval, batch on GPU, and put the latency in an SLO |
| False-positive storm | Block rate jumps 10× after a classifier update; support tickets about "it won't answer" | Shadow mode for every policy change, block-rate alerting by tenant and intent, instant policy rollback |
| Fail-open on detector timeout | Block rate drops to zero during a detector outage and nobody notices | Explicit fail-open/fail-closed policy per rail (PII egress fails closed, topic classifier fails open), and alert on a zero block rate |
| Injection bypass | A successful injection with a clean classifier score | Assume it: the boundary is the permission engine plus egress policy. Alert on permission-deny spikes as the detection signal |
| Policy drift | Two tenants with contradictory rules; behaviour depends on evaluation order | Versioned policy per tenant, deterministic ordering, and a policy test suite |

**Three hardest follow-ups.** (1) *"Buy or build?"* Buy the classifiers, build the policy engine and the integration. Open-weight models (Llama Guard, Prompt Guard 2) give you the detector but not the per-tenant config surface, the audit trail, the streaming-aware decision loop, or the shadow-mode tooling. Commercial products wrap the classifier with exactly that surface, which is where most of the engineering actually is. (2) *"How do you evaluate a guardrail?"* As a classifier, with a real confusion matrix on a labelled adversarial set, reported as precision/recall at your operating threshold, plus a red-team set that is refreshed because attacks evolve (Google reported a 32% rise in injection attempts between November 2025 and February 2026). "We added guardrails" without a false-positive number is not an answer. (3) *"A guardrail blocks a legitimate high-value request. What's the escalation path?"* This is a product question and the good answer treats it as one: a block returns a reference id, a human review queue with an SLA, and a standing-exception mechanism scoped per tenant and per rule with an expiry. A guardrail with no appeal path gets disabled by the business within a quarter, which is worse than a tuned one.

---

### Design 9 — Document-processing pipeline

**Clarify.** What document classes and what mix (native PDF versus scanned versus images versus office formats)? What is the extraction target: text for RAG, or structured fields for a database? What accuracy is required, and is there a human-in-the-loop for low-confidence pages? Batch or near-real-time? Throughput and burst shape? Is reprocessing after a parser upgrade a requirement, because that decides whether you keep the originals and the intermediate artifacts?

```
  ingest (S3 event / crawler)
     │
     ▼
  classify + route per page  ◀── the highest-leverage decision in the whole design
     │  signals: text-layer density, scan quality, table presence, language
     ├── native text layer, clean ──▶ fast path: direct extract        ~$0.0002/pg
     ├── scanned, simple ───────────▶ OCR (Tesseract/managed)          ~$0.0015/pg
     └── complex (tables, forms,
         multi-column, handwriting) ─▶ VLM parse (single pass)         ~$0.006/pg
     │
     ▼
  layout structure (blocks, reading order, tables, figures)
     │
     ▼
  normalize → markdown/JSON + provenance (page, bbox) per block
     │
     ├──▶ validation: schema, checksums, arithmetic on extracted totals
     │      confidence < threshold ──▶ HUMAN REVIEW QUEUE ──▶ corrections
     │                                        │
     │                                        └──▶ labelled data back into routing eval
     ▼
  chunk (layout-aware: tables whole, headers propagated, ~400 tok target,
         1,200 tok hard cap for tables, 5% overlap, drop chunks <30 tok)
     │
     ▼
  embed → index (Design 1)     +     artifact store: ORIGINAL + parsed IR + version
                                      (so a parser upgrade is a replay, not a re-crawl)
```

**Decisions.**
- **Adaptive per-page routing over one uniform parser.** A uniform VLM pass on 4M pages/day is a very large bill for pages that have a perfectly good text layer. Route on text density, scan quality, and table presence. Cost: a router to build and evaluate, and a new failure mode where the router misroutes.
- **Pipeline (cascade) over end-to-end VLM for the complex path, with eyes open.** Cascades allow per-stage optimisation and per-stage debugging but propagate errors and lose information between modules; single-pass VLMs avoid propagation and are harder to debug and to attribute. The pragmatic 2026 answer is a cascade for the majority and a VLM for the complex tail, which is also why the router matters more than either.
- **Keep the original and the intermediate representation, versioned.** A parser upgrade should be a replay over stored artifacts, not a re-crawl of source systems that may have changed or may rate-limit you. Cost: storage, which is cheap, against re-crawl, which is not.
- **Layout-aware chunking with tables kept whole.** Splitting a table from its header is the failure that produces answers where the number is right and the label is wrong, and it is invisible to every aggregate metric. Cost: variable chunk sizes and a hard cap you must enforce.
- **Confidence-gated human review, with corrections fed back.** The review queue is not a cost centre, it is your labelled data source for the router and the validators. Cost: an operational process, and the discipline to actually use the labels.

**Scale and cost.**
```
4M pages/day · mix 60% fast / 30% OCR / 10% VLM
  0.6 x 4M x $0.0002 =   $480
  0.3 x 4M x $0.0015 =  $1,800
  0.1 x 4M x $0.0060 =  $2,400
                        ------
              per day  ≈ $4,680  → ~$140k/month
  UNIFORM VLM instead: 4M x $0.006 = $24k/day = $720k/month. The router is a
  5x saving, which is why it is the first decision, not an optimisation.
THROUGHPUT  4M pages/day = 46 pages/s mean, plan for 3x burst = 140 pages/s
  VLM path 14 pages/s at ~1.5 s/page → ~21 concurrent VLM slots
EMBEDDING  4M pages → ~7M chunks/day x 400 tok = 2.8B tok/day
  self-hosted BGE-M3 at 1.2k chunks/s → ~1.6 GPU-days/day → 2 GPUs steady
STORAGE  originals 4M x 200 KB = 800 GB/day (lifecycle to cold at 30 d)
  parsed IR ~40 KB/page = 160 GB/day (keep hot, it is the replay substrate)
QUEUE  the burst shape decides the design: SQS/Kafka with per-class partitions so a
  flood of scanned invoices cannot starve the fast path
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Router misclassifies a class | One document type's downstream answer quality is poor while overall metrics are fine; `route=fast` on pages whose text layer is a garbled OCR artifact from the source | Route-level quality metrics, not just aggregate; a labelled routing eval set per class |
| Table split across a chunk boundary | Answers cite a value with the wrong label; judge scores high, users report wrong numbers | Tables as atomic chunks up to a cap; header propagation; a table-specific eval slice |
| Silent OCR degradation | Extraction confidence p50 drifting down over weeks after an upstream scanner change | Confidence as a tracked metric with an alert, not just a review gate |
| Poison-pill document | The pipeline stalls; one partition's lag grows while others are fine; a 4,000-page PDF or a malformed file | Per-document timeout, page-count cap with split-and-fan-out, and a dead-letter queue with alerting |
| Reprocessing impossible | A parser upgrade requires re-crawling source systems that have changed | Store originals plus versioned IR; make replay a first-class job |

**Three hardest follow-ups.** (1) *"A table spans three pages."* Page-by-page processing loses it, which is exactly the documented weakness of naive pipelines. You need cross-page stitching: detect continuation by header repetition and column-signature match, merge before chunking, and keep the merged table as one chunk even if it breaks your size target. This is the answer that shows you have actually processed industrial documents. (2) *"The parser upgrade improves 90% of documents and regresses 10%."* Do not ship it blind. Shadow-parse a stratified sample, diff structured extractions per class, and ship per class rather than globally, keeping the old parser routed for the regressed classes until fixed. Which requires that your router can dispatch by parser version, so build that seam early. (3) *"How does document-level ACL survive chunking?"* ACL lives on the document in the registry and is denormalised onto every chunk at index time, with a re-denormalisation job when the ACL changes. The trap is that ACL changes are far more frequent than content changes, so a design that requires reindexing on an ACL change will fall behind; keep the ACL in a mutable field the index can filter on rather than in the embedded payload.

---

### Design 10 — Customer-support agent with escalation

**Clarify.** What channels, and is the conversation synchronous (chat) or asynchronous (email, tickets)? What is the current human baseline: volume, cost per contact, CSAT, first-contact-resolution? What can the agent *do* versus only answer, because a read-only agent and a refund-issuing agent are different systems? What are the hard "always escalate" categories (legal, safety, churn risk, VIP)? What is the tolerance for a wrong answer, in dollars?

```
  channel (chat · email · in-app)
     │
     ▼
  intent + risk classifier  ──▶ hard-escalate categories bypass the agent entirely
     │                          (legal, safety, cancellation, VIP tier)
     ▼
  session state (checkpointed) + customer context (entitlements, recent tickets, plan)
     │
     ▼
  ┌── AGENT (one agent, phase-scoped tools) ─────────────────────────────────┐
  │  retrieve: kb_search · account_lookup · order_status · past_tickets       │
  │  act:      reset_password · resend_receipt · update_address              │
  │            [ approval-gated: issue_credit · cancel_order ]               │
  │  verify:   grounded? cited? policy-compliant? confidence?                │
  └──────────────────────────┬───────────────────────────────────────────────┘
                             │
     ┌───────────────────────┼────────────────────────────┐
     ▼                       ▼                            ▼
  ANSWER (cited)      ESCALATE to human            APPROVAL queue
  + CSAT prompt        with a STRUCTURED handoff:   (write actions)
                        summary · attempted steps ·
                        customer sentiment · the
                        specific blocker · full transcript
                             │
                             ▼
                      agent console (human sees agent's draft + context)
                             │
                             └──▶ resolution labelled → weekly eval set + KB gap report
```

**Decisions.**
- **Escalate early and structurally, on explicit triggers**, not when the model gives up. Triggers: low retrieval confidence, three turns without progress, detected frustration, a hard category, or any action outside the allow-list. Cost: a lower deflection rate, which you should defend as correct rather than apologise for.
- **Structured handoff over transcript dumping.** The measurable harm in bad escalation is context loss: the human restarts from zero and the customer repeats themselves, which is worse than never having used the agent. A handoff payload with the summary, attempted steps, and the specific blocker is the design. Cost: a schema and a console integration.
- **Read-only autonomously, writes approval-gated by value.** Password reset and receipt resend are reversible and cheap, so autonomous. A credit above a threshold is approval-gated with revalidation at execute time. Cost: approval latency, and the risk of approval fatigue if the gate fires too often.
- **KB gap reporting as a first-class output.** Every escalation caused by missing content becomes a KB ticket. The single strongest determinant of whether these programmes succeed is knowledge-base quality, and the agent is the best KB-gap detector you will ever have. Cost: an editorial process that must actually exist.
- **Deflection is never the primary metric.** Pair it with re-contact rate, CSAT delta, and hallucinated-policy rate, because deflection alone rises when the agent stops escalating things it should escalate.

**Scale and cost.**
```
120k conversations/day · 41% deflected (2026 median tier-1 is 41.2%, top quartile 58.7%)
  intent mix matters enormously: password reset and refunds deflect >70%,
  nuanced complaints rarely break 25%. A headline deflection number moves with
  MIX, not with quality, which is why you report it sliced.
COST PER CONVERSATION
  agent-handled: ~5 model calls, 9k in / 500 out avg = 5 x ($0.027 + $0.0075) ≈ $0.17
    + guardrails/embed/rerank $0.02 → ~$0.19
  escalated (22% escalation rate is a typical blended assumption): agent cost
    $0.09 (partial) + human $4.80 → $4.89
  blended: 0.41 x $0.19 + 0.59 x $4.89 = $0.08 + $2.88 = $2.96
  human-only baseline: $4.80 → ~38% cost reduction, i.e. real but not the 80% in the deck
MODEL SPEND  120k x 0.78 (agent touches) x $0.19 ≈ $17.8k/day = $530k/month
  ← at this volume routing and caching are not optimisations, they are the budget
QUALITY  pure-AI CSAT lands around 4.1/5 vs 4.3/5 human; hybrid escalation flows
  narrow that to ~0.05 points, which is the argument for investing in the HANDOFF
  rather than in raising deflection
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Hallucinated policy | The agent states a refund window that does not exist. Deflection looks great; chargebacks and re-contacts rise 3 weeks later | Grounding requirement with citation verification; policy answers only from a curated policy corpus; a `hallucinated_policy_rate` metric on a sampled audit |
| Escalation context loss | Re-contact rate high on escalated conversations; customers repeat themselves; agent handle time on escalated tickets *higher* than baseline | Structured handoff payload; measure agent handle time on escalated versus cold tickets as the KPI |
| Deflection gaming | Deflection up, CSAT and re-contact worse | Never optimise deflection alone; pair it, and alert on the pair diverging |
| Doom loop | Same clarifying question three times; conversation length p99 climbing | No-progress detector on `(tool, args)` and on question similarity; hard escalate at 3 |
| Approval fatigue on credits | Approve rate 98%, median review 6 s | Raise the auto-approve threshold with a value cap, and audit a sample instead of gating everything |

**Three hardest follow-ups.** (1) *"Deflection is 55% and the business is unhappy. Why?"* Because deflection is a leading indicator that is uninterpretable alone. Either the mix shifted toward easy intents, or the agent stopped escalating things it should, in which case re-contact rate and CSAT fall while the dashboard improves. The diagnosis is a slice by intent plus the re-contact pair, and the fix is often to *lower* deflection deliberately. (2) *"The agent gave a wrong answer that cost the company $40k."* Post-incident: was it grounded and cited (a retrieval or KB problem), or ungrounded (a guardrail and prompt problem)? Then the structural fix, which is that high-value assertions must come from a curated policy corpus with citation verification, and any action above a dollar threshold must be approval-gated. And the honest part: at 120k conversations/day a nonzero wrong-answer rate is a design parameter, so the question is what rate you accepted and whether you wrote it down. (3) *"How do you handle a customer who is clearly furious?"* Sentiment as an explicit hard-escalate trigger, not something the model weighs against resolving the ticket. Detect, escalate immediately with the full context, and never attempt a retention offer autonomously. This is the question that checks whether you think of escalation as failure or as a designed path.

---

### Design 11 — Code assistant

**Clarify.** Repository scale in files and LOC, and is it a monorepo? How many engineers and what is the request shape (inline completion versus chat versus agentic multi-file edit), because those are three latency contracts: ~200 ms, ~2 s, and minutes. Is code allowed to leave the network? Index freshness requirement against a repo with hundreds of commits a day? Do we need to run tests, which means a build environment as part of the design?

```
  INDEX PIPELINE (per repo, incremental)          REQUEST PATH
   git webhook / commit
        │                                    ┌── inline completion (p95 200 ms) ──┐
        ▼                                    │  local context only: open buffer,  │
   changed files only                        │  imports, recent edits. NO index   │
        │                                    │  round trip. Small model, cached.   │
        ├─▶ tree-sitter parse ──▶ symbol     └─────────────────────────────────────┘
        │    graph: defs, refs, callers,
        │    imports, tests-for-symbol      ┌── chat / agentic edit (p95 2-60 s) ──┐
        │                                    │ 1. resolve symbols in the query     │
        ├─▶ chunk by SYNTAX (function/       │ 2. GRAPH expand: def → callers →    │
        │    class), not by line count       │    tests → types  (structure)        │
        │                                    │ 3. vector search (semantic residual) │
        └─▶ embed ──▶ vector index           │ 4. rerank + assemble under a token   │
             (per-repo namespace)            │    budget, with file paths + line #s │
        │                                    │ 5. agent loop: read · grep · edit ·  │
        ▼                                    │    RUN TESTS ← the verifier          │
   index registry: repo, commit sha,         └──────────────────────────────────────┘
   parser version, freshness metric                     │
                                                        ▼
                                              sandbox: repo checkout + toolchain,
                                              no network egress, per-user isolation
```

**Decisions.**
- **Hybrid: code graph plus vector, not vector alone.** Pure RAG over code chunks has no concept of a dependency graph, so it retrieves things that look similar rather than things that are actually involved. The reported evidence is strong: a Tree-sitter knowledge graph exposed via MCP cut agent token use ~10× and tool calls ~2.1× across 31 repositories. Cost: a per-language parser investment and a graph to keep fresh.
- **Chunk by syntax, never by line count.** A function split in half is useless, and a chunk without its enclosing class or file path is unattributable. Cost: variable chunk sizes and per-language chunkers.
- **Three separate latency tiers with three separate context strategies.** Inline completion must not touch the index (200 ms leaves no room for a network round trip plus rerank); chat can; agentic edit uses tools iteratively rather than one-shot retrieval. Conflating these is the most common design error here. Cost: three code paths.
- **Tests are the verifier, and they are the whole reliability story.** An agent that says "fixed" with a red suite is the canonical failure. Run the suite in the sandbox and gate acceptance on the exit code. Cost: a build environment per repo, which is often the hardest operational part of the entire design.
- **Incremental indexing on commit, with freshness as an SLO.** A stale index is worse than no index because it confidently returns the previous API. Cost: webhook plumbing and a reconciliation crawl for missed events.

**Scale and cost.**
```
8k engineers · monorepo 40M LOC · 180k files · ~600 commits/day
INDEX  40M LOC → ~1.2M syntax chunks (avg ~33 LOC) → 1.2M vectors (768-dim int8, 768 B)
  ≈ 0.9 GB, trivially in RAM. Code indexes are SMALL; the graph is the expensive part.
  symbol graph: ~4M nodes, ~20M edges → ~2 GB in a graph store or Postgres with
  recursive CTEs (adequate at this scale and one fewer system to run)
  incremental: 600 commits/day x ~8 files = 4.8k files/day reparse → minutes of CPU
  full rebuild: ~6 h on 16 cores; keep it as a weekly consistency job, not the path
REQUESTS
  inline: 8k engineers x ~400 completions/day = 3.2M/day = 37 rps mean, 150 rps peak
    small model, ~600 in / 40 out = ~$0.0004 → $1.3k/day = $38k/month
    ← inline dominates VOLUME; a cache and a small model are the entire cost strategy
  chat: 8k x 12/day = 96k/day, ~14k in / 700 out = $0.052 → $5k/day = $150k/month
  agentic edit: 8k x 1.5/day = 12k/day, ~14 calls avg = $0.60/task → $7.2k/day = $216k/mo
  TOTAL ≈ $400k/month at 8k engineers = $50/engineer/month, against a fully loaded
  cost of ~$15k/engineer/month. The ROI argument is easy; the FRESHNESS and the
  TEST-VERIFIER are what decide whether anyone uses it.
SANDBOXES  12k agentic tasks/day x ~4 min = 33 concurrent; pooled warm checkouts,
  because a cold monorepo clone plus dependency install is minutes and kills the UX
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Stale index | Suggestions use an API refactored yesterday; `index.commit_sha` lagging `HEAD` by hours | Freshness SLO and metric; degrade explicitly (tell the user the index is stale) rather than answering confidently |
| Agent claims success, tests red | PR opened with a failing suite; "I've fixed it" in the transcript | Run the suite in the sandbox; gate acceptance on exit code; require a test that fails before and passes after |
| Cross-repo or cross-tenant leak | Code from repo A in a completion for repo B | Per-repo index namespaces, enforced in the query layer, plus a test asserting it |
| Sandbox cold start | p95 for agentic tasks dominated by setup, not by the model | Warm pooled checkouts per repo, cached dependency layers |
| Inline latency regression | Completion acceptance rate falls as p95 crosses ~300 ms | Keep inline off the index; measure acceptance rate as the real quality metric, not judge scores |

**Three hardest follow-ups.** (1) *"A 40M-LOC monorepo does not fit in context. What actually goes in the prompt?"* A budgeted assembly, in priority order: the exact symbols named in the query with their definitions, their direct callers and callees one hop out, the relevant type definitions, the tests for those symbols, and only then semantic vector hits for the residual, each with the file path and line numbers so the model can cite and edit precisely. The graph does the selection; the vector index handles what the graph cannot name. (2) *"How do you evaluate this?"* Three tiers with different signals. Inline: acceptance rate and edit-distance-after-acceptance, measured live, which is a real product metric and better than any offline score. Chat: a golden set with rubrics. Agentic: task success gated on the test suite plus trajectory assertions, which is the only tier where you can be objective. Reporting only offline benchmark numbers for a tool whose value is inline acceptance is a red flag. (3) *"Code cannot leave the network."* Self-hosted model on your own GPUs behind the gateway, which changes the cost model completely: you now pay for idle capacity rather than per token, so utilisation becomes the metric and batching and quantisation become the levers. It also changes the model-quality ceiling, so be explicit about the tradeoff rather than pretending self-hosting is free.

---

### Design 12 — LLM cost optimiser and router

**Clarify.** What is the current spend and its decomposition by feature, model, and tenant, because a router on an unmeasured bill is guesswork? What quality regression is acceptable, expressed as a number? Is latency also a target, because the cheap model is usually also the fast one? Is there a hard requirement for a specific model on any path (compliance, contractual)? Who owns the decision when the router is wrong?

```
  request + context tags (tenant, feature, run_id)
     │
     ▼
  ┌── ROUTER (inside the gateway, Design 2) ────────────────────────────────┐
  │                                                                         │
  │  L0  POLICY  hard pins: compliance paths, contractual models  (0 ms)     │
  │       │ no pin                                                          │
  │  L1  RULES   by feature/intent/prompt-length/tenant tier      (<1 ms)    │
  │       │ no rule                                                         │
  │  L2  CLASSIFIER  small model or matrix-factorisation router    (8-25 ms) │
  │       predicts: does this need the strong model?                        │
  │       │                                                                 │
  │  L3  CASCADE  cheap model first → confidence/verifier check →           │
  │       escalate to strong on failure     (accurate, adds latency on      │
  │                                          the escalated fraction)        │
  │  L4  POST-RESPONSE RETRY  output guard fails → rerun on strong (safety net)│
  └────────────────────────┬────────────────────────────────────────────────┘
                           ▼
      small model · mid model · frontier model · self-hosted vLLM
                           │
                           ▼
   ledger + per-route quality scoring ──▶ weekly: route quality vs cost scatter
                           │
                           └──▶ retrain/retune the L2 classifier on labelled outcomes
```

**Decisions.**
- **Tiered router, cheapest decision first.** Policy pins, then rules, then a classifier, then a cascade, then post-response retry. Rules cover a surprising fraction of traffic for zero latency, and a design that starts with the classifier is over-engineered. Cost: five layers to reason about, so keep the observability per layer.
- **Cascade only where verification is cheap.** A cascade is the most accurate mechanism and it costs you the cheap call plus the expensive one on the escalated fraction, so it only pays when the cheap model succeeds often and failure is cheaply detectable (schema invalid, no citation, low logprob, verifier fails). Cost: worse p95 latency on escalated requests, which you must show in the SLO.
- **Prompt caching before routing.** Caching on a frozen prefix is correctness-preserving and often 30-40% of input cost; routing changes the model and therefore the output distribution. Do the safe thing first. Cost: none, which is why the ordering is not a real tradeoff.
- **Quality measured per route, continuously.** A router without per-route quality scoring is a cost-reduction machine with no brakes. Sample and score every route weekly and plot quality against cost. Cost: judge spend, which you should budget explicitly.
- **Self-hosting is a utilisation bet, not a price bet.** A self-hosted model is cheaper per token only above a utilisation threshold; below it you pay for idle GPUs. Compute the breakeven and state it rather than asserting self-hosting is cheaper.

**Scale and cost.**
```
BASELINE  40M requests/month, all on a frontier model, 4.5k in / 300 out
  = 40M x ($0.0135 + $0.0045) = $720k/month
LEVERS, applied in order (multiplicative on what remains, not additive)
  1. prompt caching on frozen prefixes (2.2k of the 4.5k input cached at 1/10 price)
       input cost 4.5k → effective 2.5k → saves ~22% of total → $562k
  2. rules + classifier routing: 58% of traffic to a model at ~1/12 the price
       0.58 x (1/12) + 0.42 x 1 = 0.468 → $263k
  3. cascade on the structured-output paths (18% of traffic, 80% resolved cheap)
       → ~$243k
  4. semantic cache at 25% hit (Design 7) → ~$182k
  TOTAL ~75% reduction, which is at the top of the published range and requires
  ALL FOUR. A single lever gets you 20-40%.
PUBLISHED ANCHORS  RouteLLM: 95% of GPT-4 quality with 26% strong-model calls,
  ~48% cheaper than random routing; with judge-augmented training data, 95% quality
  at 14% strong calls (~75% reduction). Production teams report 40-85% bill reduction.
  Treat 40-50% as the credible planning number and 85% as a best case with a
  favourable traffic mix.
ROUTER OVERHEAD  L2 classifier 8-25 ms; at 900 rps that is 1-2 small GPUs or a
  distilled CPU model. ~$600/month against a $500k+ saving.
SELF-HOST BREAKEVEN  an 8B model on 2xA10G ≈ $1.5k/month, serving ~600 tok/s sustained
  ≈ 1.5B tok/month at full utilisation → $0.001/1k tok. A commercial small model at
  $0.25/M input is $0.00025/1k. So self-hosting an 8B model BEATS a commercial small
  model only above roughly 40-50% sustained utilisation, and loses badly below it.
  This arithmetic is the answer to "should we self-host to save money."
```

**Failure modes.**

| Failure | Observable symptom | Mitigation |
|---|---|---|
| Silent quality erosion | Cost down 45%, aggregate judge score flat, but one intent's score down 12 points | Per-route quality scoring, sliced by intent and tenant; alert on route-level regression, never on the aggregate |
| Classifier drift | Strong-model share creeping from 26% to 45% over two months with no code change; traffic mix moved | Monitor route distribution as a metric; retrain on labelled outcomes; alert on distribution shift |
| Cascade latency blowup | p95 fine, p99 doubled; the escalated fraction pays both calls | Cap the cascade to one escalation; skip the cascade on latency-sensitive routes; report p99 by route |
| Provider price change | Your routing policy is now wrong and nobody notices | Prices in config, not code; a job that re-derives the routing thresholds when prices change |
| Cheap model can't use the tools | Tool-call malformation rate 8× on the cheap route; the agent loops and costs MORE than the frontier model would have | Route on capability, not just difficulty: tool-heavy paths pin to a model with proven tool-calling; measure malformation rate per route |

**Three hardest follow-ups.** (1) *"Prove the router did not hurt quality."* An A/B with quality as the primary metric, not a before/after on cost. Random assignment, per-intent slices, a judge with a calibration set, and enough n to detect the delta you care about (roughly 400 scored samples per arm for 3 pp). And publish the intents where quality did drop, because there will be some and hiding them is how the router gets ripped out later. (2) *"The cheap model is cheaper per token but takes more steps in the agent loop."* Then it is not cheaper, and this is the most important trap in the design. Cost must be measured per *completed task*, not per token. A weaker model that malforms tool calls and loops three extra times costs more than the frontier model and is slower. Route agent paths on measured task-completion cost, and expect some paths to route *up*. (3) *"How much of the 85% headline is real for us?"* Depends almost entirely on traffic mix: high-repetition, short, classification-shaped traffic gets the top of the range, while long-context reasoning-heavy traffic gets little. The honest answer decomposes your own bill first and projects per lever, which is why the first deliverable in this project is attribution, not a router.

---

## Build it from scratch

The lab at `(lab pending)` is a practice harness, not a build. Three modes:

1. **Timed drill.** Pick one of the twelve, set a 45-minute timer, and produce all six slots in a text file: clarifying questions, ASCII architecture, 3-5 decisions in "X over Y because Z at the cost of W" form, a cost model with the arithmetic shown, a failure table with observable symptoms, and the three follow-ups. Then diff against the module. The gap is almost never the architecture; it is the cost arithmetic and the observable symptoms.
2. **Cost-model reps.** Given only a scale statement, produce cost per request and cost per month in under five minutes, from memory of the token prices. Do this until it is reflexive, because the moment in the interview where you write `40M x ($0.0135 + $0.0045) = $720k/month` on the board without hesitating is worth more than any diagram.
3. **Mutation drills.** Take a completed design and apply one perturbation: 50× the scale, 10× tighter latency, a hard on-prem requirement, a new regulatory constraint, or a 70% cost cut mandate. Say what changes architecturally and what stays. This is the actual interview, because the interviewer's job is to perturb your design until it breaks and watch how you respond.

A useful self-check after each drill: could a reader tell from your notes what you would *not* build, and why? A design with no rejected alternatives reads as a recitation.

---

## How it's done in production

**The comparison table across all twelve, which is the real deliverable of this module.** Read it down the columns, not across the rows.

| # | Design | The one decision that matters most | Dominant cost | The failure that is silent |
|---|---|---|---|---|
| 1 | Enterprise RAG 10M docs | Quantized first stage + full-precision rescore; ACLs pushed into the index | LLM generation, not the vector DB | Chunk boundary splitting a table |
| 2 | Multi-tenant gateway | In-path proxy plus network-level egress denial | Provider spend it governs (gateway itself is ~1%) | Streaming cost leak on client disconnect |
| 3 | Agent orchestration | Control/data plane split; eval-gated registration | Provider spend; platform infra ~3% | An agent regressing with no per-agent scoreboard |
| 4 | Agent memory | Typed facts, bi-temporal, async write | Extraction LLM calls, not storage | A wrong fact reproducing across sessions |
| 5 | Eval platform | One dataset store for CI and prod; deterministic before judges | Eval model spend (can be 20-40% of prod spend) | Golden-set drift: gate green, users unhappy |
| 6 | Prompt management | Immutable content-addressed versions; pointer-flip rollback | The eval gate, not the registry | Silent drift via a changed interpolated variable |
| 7 | Semantic cache | The key is (query, tenant, corpus_ver, model, prompt_hash) | Nothing; the risk is the cost | Near-miss served as a hit |
| 8 | Guardrail service | Parallel detectors; input rail concurrent with retrieval | False-positive rate, not compute | Fail-open on detector timeout, block rate → 0 |
| 9 | Document pipeline | Adaptive per-page routing (5× saving) | VLM path; router decides the bill | Silent OCR degradation after an upstream change |
| 10 | Support agent | Escalate on explicit triggers with a structured handoff | Human escalations, not the model | Hallucinated policy, visible 3 weeks later |
| 11 | Code assistant | Code graph plus vector; tests as the verifier | Agentic edit tasks; inline dominates volume | Stale index answering confidently |
| 12 | Cost router | Tiered router; measure cost per completed TASK | The bill it is optimising | Per-intent quality erosion hidden by a flat aggregate |

**The seven patterns that recur across all twelve.** If you learn nothing else, learn these, because they are what makes the thirteenth design answerable.

1. **Separate the write path from the read path and draw them separately.** Every one of these twelve has an asymmetric, differently-scaled ingestion and serving side.
2. **Two-stage retrieval is universal.** Cheap recall over many candidates, then expensive precision over few. Vector then reranker; binary then full precision; graph then vector; cheap model then strong model. It is the same shape every time.
3. **The enforcement boundary must be one the application cannot bypass.** Gateway plus network policy for spend; permission engine for actions; index-level predicates for ACLs. Anything enforced in application code is advisory.
4. **Version everything that changes behaviour, and put the version on the trace.** Prompt, model, embedding model, parser, chunker, tool registry, policy, dataset. The absence of this is why regressions take a week.
5. **Cost per request, computed out loud.** Then per month. Then the lever ordering. Unprompted.
6. **Every failure mode needs an observable symptom.** "It could hallucinate" is not a failure mode. "Unresolved-citation rate above 2% while judge scores stay flat" is.
7. **Name what is a filter and what is a boundary.** Classifiers, labels, and prompts reduce probability. Permission engines, network policy, and sandboxes bound damage. Conflating them is the fastest way to fail a GenAI design round.

**Cross-design failure-mode table** (the ones that appear in more than one design and are therefore worth memorising):

| Symptom | Cause | Fix |
|---|---|---|
| Aggregate metrics flat, specific users furious | You are averaging over intents/tenants; the regression is in one slice | Slice every quality metric by intent and tenant; alert on slices, not aggregates |
| Cost 3× the estimate in week one | Estimate was per model call; production is per session with multi-turn context re-send | Model cost per session at realistic turn counts before committing |
| `cached_input_tokens` ≈ 0 | A timestamp or non-deterministic ordering mutates the stable prefix | Freeze the prefix; snapshot-test byte stability; put the prefix hash on every span |
| Regression cause untraceable for a week | Multiple versioned things changed together, none on the trace | One change per canary; every version on every trace |
| Gate green, production worse | Golden set drifted, or the provider moved a floating alias | Live sampling into the set; pinned model versions; a measured eval-to-production correlation |
| Retrieval returns nothing for some users | ACLs applied after retrieval | Push predicates into the index |
| The system is up, the answers are wrong | You have SLOs on availability and latency and none on quality | Quality SLO with a sampled eval and a weekly scoreboard |

---

## Tradeoffs & when NOT to use it

**When these designs are the wrong answer, stated specifically because this is where the senior signal is.**

- **RAG, when the corpus is small enough to fit in context.** Under roughly 50-100k tokens of stable, relevant content, putting it all in a cached prefix is simpler, more accurate, and often cheaper than a retrieval pipeline. You have removed a chunker, an embedder, two indexes, a reranker, and five failure modes. Building RAG over a 40-page policy document is a real and common mistake.
- **A dedicated vector database, under ~5-10M vectors.** pgvector on the Postgres you already operate is the correct answer below that line, and reaching for a new stateful system earlier is an operational cost with no benefit you can measure.
- **A gateway, below roughly $10-20k/month of spend or a handful of consumers.** Its value is governance and it costs you a critical-path component with its own SLO. Two services and one provider do not need one.
- **An agent orchestration platform, below roughly 5-10 agents.** Platforms are amortisation plays. Three agents means three well-built services, and building a platform for three is the most expensive way to have three agents.
- **Cross-session memory, in the first version of anything.** A wrong persisted fact is a bug that reproduces forever and is invisible in single-session tests. Earn it with a measured re-derivation rate.
- **Semantic caching, on low-repetition traffic or authorisation-dependent answers.** At an 8% hit rate you have taken on a correctness risk for a small discount. And if the answer depends on who asks, this is simply the wrong tool.
- **A guardrail service, as your security story.** It is a filter with a false-negative rate. If the design's security argument rests on it, the design has no security argument.
- **Self-hosting to save money, below the utilisation breakeven.** Roughly 40-50% sustained utilisation for a small model against a commercial small model. Below that you are paying for idle GPUs and calling it savings.
- **A router, before you have attributed your bill.** The first deliverable is decomposition by feature, model, and tenant. Routing an unmeasured bill is guessing, and it is guessing with a quality risk attached.

**The genuine disagreements, stated as disagreements rather than resolved.** Pipeline versus end-to-end VLM document parsing: error propagation against debuggability, and both camps have production systems. Graph-based versus vector-only memory: bi-temporal correctness against 50-150 ms of traversal latency. Buying versus building the eval platform: the datasets and rubrics are unambiguously your asset, the runner and the UI are unambiguously not, and the scorers are genuinely contested. Long-context versus retrieval: cost scales with context and "lost in the middle" is unsolved, so the honest position is that context length changes the boundary of where RAG is worth it rather than eliminating RAG.

---

## Interview questions

### Q1 — Design enterprise RAG over 10 million documents.
**Testing:** whether you convert the requirement into numbers before drawing.
**Answer:** First convert: ~6 pages and ~10 chunks per document is ~100M chunks and ~40B tokens, which is a different architecture from 10M vectors. Then the shape: hybrid retrieval (dense plus BM25, RRF fused) over a binary-quantized first stage with full-precision rescoring and a cross-encoder reranker on 150 candidates down to 8, with tenant and ACL predicates pushed into the index, a versioned index with alias swap, and citation verification on the output. Retrieval p95 ~190 ms of a 900 ms budget. Cost ~$0.0255 per query dominated by generation, which at 200k queries/day is $153k/month, which is the number that forces routing.
**Follow-up trap:** *"What if it's 500 million chunks?"* A different architecture, not the same one scaled. The binary index stops fitting one node's RAM, so multi-node scatter-gather with p99 set by the slowest shard, plus tiered storage for cold tenants. AWS's worked example prices 500M vectors and 10M queries at ~$1,320/month against $11.38 for 10M and 1M, with a latency caveat of hundreds of milliseconds for object-backed vectors. The candidates who fail this say "add more shards" without noting that scatter-gather changes the tail-latency model.

### Q2 — Design a multi-tenant LLM gateway.
**Testing:** whether you know why it exists rather than what it contains.
**Answer:** It exists to be an enforcement boundary the application cannot bypass: virtual keys, per-tenant RPM/TPM and dollar budgets checked *before* the provider call, routing and failover, caching, and a cost ledger, with a NetworkPolicy denying direct provider egress so no worker holds a provider credential. Two-tier rate limiting (local token bucket against a leased share of a global budget refreshed every 200 ms) so Redis is not on every request. Pre-call estimate, post-call reconcile, because only the response has true output tokens. p99 added latency under 15 ms, and the gateway itself is ~1% of the spend it governs.
**Follow-up trap:** *"Now it's a single point of failure for every AI feature."* Correct, and that is the cost of the boundary. Mitigations: stateless multi-AZ replicas, no shared-fate Redis (buckets degrade to local-only rather than failing), and a documented break-glass direct-provider path with audited credentials and an expiry. What you do not do is make it bypassable by default, because then it is not a boundary. Also worth volunteering: propagate a `(tenant, team, feature, run_id)` tag from day one, because retrofitting attribution leaves you with six months of unattributable spend.

### Q3 — Design an agent orchestration platform for 300 teams.
**Testing:** whether you can separate platform responsibility from team responsibility.
**Answer:** Control plane (agent registry with versioned manifests, policy, prompt registry, approval service, eval service, quota service) separated from data plane (queue, CPU runner pool with a durable graph and checkpointer, sandbox pool, gateway). An agent is a versioned artifact declaring tools, model pin, budget ceiling, permission scopes, and its eval suite, and you cannot register one without a suite. Platform owns boundaries: budgets, permissions, egress, traces, the eval gate. Teams own prompts, tools, topology. 2M runs/month is only ~6 rps peak, so this is not a throughput problem, it is a governance and durability problem.
**Follow-up trap:** *"Team A's agent calls Team B's agent."* Identity propagation and hierarchical budgets, which is the enterprise MCP identity gap in a different costume. The originating principal's permissions intersected with the callee's scopes, never unioned, or you get privilege escalation by composition. And the child's spend counts against the parent's ceiling, or a nested call is an unbounded budget hole. If a candidate says "the callee's permissions apply," they have just designed a confused-deputy vulnerability.

### Q4 — Design an agent memory service.
**Testing:** whether you know that memory is usually a liability first.
**Answer:** Typed facts, never free-text notes, extracted asynchronously at session end and stored bi-temporally with provenance and confidence, partitioned by user, retrieved synchronously in a 60 ms budget under a hard 1.5k-token injection cap. Extraction is the cost, not storage: 40M sessions/month at ~$0.0007 each is ~$28k/month, mitigated by gating on session length and using a small model. And the decision I would lead with: ship without cross-session memory, measure the re-derivation rate, and add memory against that number, because a wrong fact reproduces forever and is invisible in single-session tests.
**Follow-up trap:** *"GDPR erasure."* Not a `DELETE`. It has to reach fact rows, embeddings, graph edges, extraction job logs, trace payloads, downstream caches, and eval fixtures if real user data leaked into them. That is a data-lineage requirement, which means a per-user partition key propagated everywhere plus a tested erasure job with a completion report. Candidates who answer "delete from the memory table" have never shipped this under a privacy review.

### Q5 — Design an eval platform.
**Testing:** whether you treat evals as infrastructure.
**Answer:** One versioned dataset store shared by the CI gate and production monitoring, a seeded parallel runner that replays fixtures, and three scorer tiers: deterministic first (schema, citations, tool order, cost), trajectory scoring as a first-class type, and pinned LLM-as-judge with a 40-case human calibration set last. Tiered suites so the gate stays under ~15 minutes, result caching keyed on `(dataset_ver, prompt_hash, model, seed, code_sha)` for a 60-70% hit rate, and continuous live sampling into the golden set. The number that justifies trajectory scoring: agents evaluated only on final output pass 20-40% more cases than trajectory evaluation reveals.
**Follow-up trap:** *"Your eval scores went up and production got worse."* Overfitting to the set, or the set does not represent traffic. The answer is a measured correlation between eval-score delta and production-metric delta over the last N releases, plus a 20% holdout never used for iteration. Being able to say "my gate has a measured correlation of 0.6 with the production metric" is a level marker; "we have 400 evals" is not.

### Q6 — Design prompt management and versioning.
**Testing:** whether you understand prompts as behaviour-changing artifacts.
**Answer:** Git as source of truth, a registry as distribution. Immutable content-addressed versions, deployment pointers separate from versions so rollback is a pointer flip in seconds rather than a CI run, local caching with fail-closed-to-last-known-good on registry unavailability, the same eval gate for UI-authored and git-authored changes, and the rendered prefix hash on every trace. Resolution traffic is trivial after caching; this is an availability and correctness system, not a scaling one.
**Follow-up trap:** *"Ship the prompt change and the model upgrade together to save a week."* No, one change per canary, and the canonical case is Anthropic's April 2026 postmortem where a Claude Code quality regression traced to three independent harness-level changes shipped near each other with no model change at all, costing a week of bisecting. Then the arithmetic that makes it concrete: detecting a 3 pp judge delta needs ~400 scored sessions, so at a 5% canary on 8k sessions/day there is a one-day detection floor. Faster detection means a larger canary and more exposure. That is the real tradeoff, and stating it as arithmetic rather than principle is what lands.

### Q7 — Design a semantic cache. Then tell me when not to build one.
**Testing:** whether you will trade correctness for cost without noticing.
**Answer:** Exact and prefix caching first because they are correctness-preserving, then semantic as a distinct tier. The key is `(normalized_query, tenant, corpus_version, model, prompt_hash)`, never the query alone. Threshold measured per embedding model, and reported optima are model-specific (~0.83 MPNet, ~0.78 Albert) with GPTCache's suggested 0.7 too loose in practice; start near 0.92 and tune down. Validate every hit against corpus version and TTL. Honest hit rates are 20-45%, 30-70% on FAQ traffic, and the 90%+ claims come from datasets built with heavy repetition. Do not build it when repetition is low (at 8% hit rate you have taken correctness risk for a small discount) or when the answer depends on who is asking.
**Follow-up trap:** *"Hit rate went from 30% to 70% after you lowered the threshold. Ship it?"* Not without a hit-quality audit, because that is exactly the shape of a false-positive increase. Shadow-sample 2-5% of hits through the miss path and compare with the judge to get a continuous false-positive estimate. And the better design if you have the option: cache the *retrieval* rather than the answer, so a near-miss degrades to slightly worse context that the LLM can still decline, instead of a confidently wrong cached answer.

### Q8 — Design a guardrail service.
**Testing:** whether you know it is a filter and not a boundary.
**Answer:** Parallel detectors rather than a chain, with the input rail running concurrently with retrieval so it is nearly free on the wall clock, and deterministic checks (secret regexes, citation resolution, schema) before classifiers. Streaming output rails scan token windows, which means accepting that a blocked response may be partially delivered, and that is a product decision to state rather than hide. At 900 rps, three detectors is ~2,700 inferences/s, which batches onto one or two T4s for ~$850/month, or ~0.15% of the LLM cost. And the framing: this reduces probability. The permission engine and network egress policy bound damage. They are different things.
**Follow-up trap:** *"What's your false-positive budget?"* This is the question that catches people, because the compute cost is trivial and the false-positive cost is the whole story: at 900 rps a 1% false-block rate is 780k blocked legitimate requests a day, which is an outage that looks like a safety feature. Target under 0.2%, ship every policy change in shadow mode first, alert on block rate by tenant and intent, and have an appeal path with a review queue and scoped standing exceptions. A guardrail with no appeal path gets disabled by the business within a quarter.

### Q9 — Design a document-processing pipeline for 4 million pages a day.
**Testing:** whether you find the cost lever.
**Answer:** Adaptive per-page routing is the whole design: classify on text-layer density, scan quality, and table presence, then route to a fast text-layer path (~$0.0002/page), an OCR path (~$0.0015), or a VLM path (~$0.006). At a 60/30/10 mix that is ~$4.7k/day against $24k/day for a uniform VLM pass, a 5× saving, so the router is the first decision and not an optimisation. Then layout-aware chunking with tables kept whole up to a 1,200-token cap and header propagation, confidence-gated human review whose corrections feed back as labels, and stored originals plus versioned intermediate representation so a parser upgrade is a replay rather than a re-crawl.
**Follow-up trap:** *"A table spans three pages."* Page-by-page processing loses it, and this is the documented weakness of naive pipelines. Detect continuation by repeated headers and column-signature match, merge before chunking, and keep the merged table as one chunk even if it breaks the size target. The related trap is ACLs: they change far more often than content, so denormalise the ACL onto chunks as a mutable filterable field rather than embedding it, or an ACL change becomes a reindex you cannot keep up with.

### Q10 — Design a customer-support agent with escalation.
**Testing:** whether you treat escalation as a designed path or as failure.
**Answer:** Intent and risk classification first, with hard-escalate categories (legal, safety, cancellation, VIP) bypassing the agent entirely. Then one agent with phase-scoped tools: read-only tools autonomous, low-value reversible writes autonomous, high-value writes approval-gated with revalidation. Explicit escalation triggers rather than the model giving up: low retrieval confidence, three turns without progress, detected frustration, or any action outside the allow-list. And the piece that determines whether the programme succeeds, the structured handoff: summary, attempted steps, sentiment, and the specific blocker, because context loss on escalation makes the escalated ticket *worse* than a cold one. Blended cost ~$2.96 per conversation against a ~$4.80 human baseline at 41% deflection, so ~38% savings, which is real and not the 80% in the deck.
**Follow-up trap:** *"Push deflection from 41% to 60%."* Only with the pair. 2026 medians are 41.2% with a top quartile at 58.7%, but the number moves with intent mix (password resets deflect over 70%, nuanced complaints rarely break 25%), so the honest first move is to slice by intent and grow the easy intents rather than force the hard ones. And deflection must be reported with re-contact rate and CSAT delta, because deflection rises when the agent stops escalating things it should, which improves the dashboard and damages the business.

### Q11 — Design a code assistant for 8,000 engineers on a 40M-LOC monorepo.
**Testing:** whether you recognise three latency contracts rather than one.
**Answer:** Three request classes with three context strategies: inline completion at p95 200 ms using only local buffer context with no index round trip; chat at p95 2 s using graph-plus-vector retrieval; agentic multi-file edit over minutes using tools iteratively with a test suite as the verifier. Index: tree-sitter symbol graph (defs, refs, callers, tests-for-symbol) plus syntax-chunked vectors, incremental on commit with freshness as an SLO. The code index is small (1.2M chunks ≈ 0.9 GB); the graph is the expensive part. The reported payoff for the graph is large: ~10× fewer tokens and ~2.1× fewer tool calls across 31 repositories. Cost ≈ $50/engineer/month against a ~$15k fully loaded cost, so the ROI argument is trivial and freshness plus the verifier decide adoption.
**Follow-up trap:** *"How do you know a fix is actually a fix?"* Run the suite in the sandbox and gate acceptance on the exit code, and for a bug fix require a test that fails before and passes after. The agent saying "I've fixed it" is the canonical `fail-plausible` failure and the reason the verifier is the whole reliability story. Second trap: evaluate the three tiers differently, and for inline the honest metric is live acceptance rate and post-acceptance edit distance, not an offline benchmark. Reporting only benchmark numbers for a tool whose value is inline acceptance is a red flag.

### Q12 — We spend $720k a month on LLM calls. Cut it 70%.
**Testing:** whether you sequence levers and know the traps.
**Answer:** First, attribution: decompose by feature, model, and tenant, because routing an unmeasured bill is guessing. Then four levers multiplicatively, safest first. Prompt caching on a frozen prefix (~22% off, correctness-preserving). Rules plus a classifier router sending ~58% to a model at ~1/12 the price (down to ~$263k); RouteLLM's peer-reviewed result is 95% of GPT-4 quality at 26% strong-model calls and ~48% cheaper than random, and up to 75% with judge-augmented training. A cascade on the structured-output paths where failure is cheaply detectable. A semantic cache at ~25% hit. That gets ~75% and requires all four; any single lever is 20-40%.
**Follow-up trap:** *"The cheap model is cheaper per token but the agent takes more steps."* Then it is not cheaper, and this is the trap that matters most. Cost must be per *completed task*, not per token: a weaker model that malforms tool calls and loops three extra times costs more than the frontier model and is slower. So route on capability and not only difficulty, pin tool-heavy paths to a model with a measured low malformation rate, and expect some routes to move *up*. Second trap: self-hosting. An 8B model on 2×A10G at ~$1.5k/month beats a commercial small model only above roughly 40-50% sustained utilisation, so compute the breakeven rather than asserting that self-hosting is cheaper.

### Q13 — What's different about a GenAI design interview versus a normal one?
**Testing:** whether you have a method or are pattern-matching.
**Answer:** Three properties change every answer. The core component is probabilistic, so correctness is a measured distribution and an eval strategy is a component rather than a phase. It is expensive per request, $0.01-0.30 against $0.0001, so cost per request belongs on the whiteboard unprompted. And it is slow, 1-10 s against 50 ms, so streaming, caching, and step reduction are architecture rather than optimisation. The practical consequence is four artifacts a conventional design does not need: a cost model with the arithmetic, an eval strategy, a named failure mode for silent wrongness, and a trust boundary separating what filters from what bounds damage.
**Follow-up trap:** *"So what stays the same?"* Almost everything, and saying this protects you from the opposite error. It is still capacity planning, still queues and backpressure, still idempotency, still sharding and hot partitions, still multi-tenancy and noisy neighbours, still versioned schemas and migrations, still SLOs and error budgets. Candidates who treat GenAI as an entirely new discipline forget backpressure and hot shards, which is how the vector index falls over. The GenAI parts are additions to conventional design, not replacements for it.

### Q14 — Pick any two of these designs and tell me what they share.
**Testing:** whether you have abstracted the pattern or memorised twelve answers.
**Answer:** Take the RAG system and the cost router. Both are two-stage: cheap recall over many candidates then expensive precision over few, which is the same shape as binary-then-full-precision, vector-then-reranker, graph-then-vector, and cheap-model-then-strong-model. Both fail the same way, with a per-slice regression hidden by a flat aggregate. Both require versioning everything that changes behaviour and putting it on the trace. And both have the property that the enforcement or selection decision must live somewhere the caller cannot bypass. That two-stage shape plus per-slice metrics plus versioned-and-traced plus a real enforcement boundary is most of what you need for a design you have never seen.
**Follow-up trap:** *"Design something not on your list: a multimodal video search system."* Same six slots. Clarify (hours of video, frames per second sampled, is audio in scope, latency, tenancy). Write path: decode, sample keyframes, caption or embed frames, transcribe audio, align on timecode, index both modalities. Read path: two-stage, cheap ANN over frame and transcript embeddings then a VLM rerank on the top candidates, returning timecoded segments. Decisions: sampling rate against recall, per-frame embedding against per-shot, unified against per-modality index. Cost: frames per hour times embedding cost dominates the write path, VLM rerank dominates the read path. Failure: sampling misses a short event, and the observable symptom is recall collapsing on queries about brief actions. The method transfers; that is the point of drilling it.

---

## Red flags that fail you

- Drawing boxes for 20 minutes without a single number.
- No cost per request. In a GenAI design this is half the answer and its absence is disqualifying at senior level.
- Not converting "10 million documents" into chunks, tokens, and bytes before choosing an index.
- Treating a 10M-vector and a 500M-vector system as the same architecture at different scale.
- Applying ACLs after retrieval.
- Reaching for a dedicated vector database at 2 million vectors, or for a platform at three agents.
- Presenting a guardrail service or a classifier as the security boundary.
- Quoting an 85% routing saving or a 95% cache hit rate as a plan rather than a best case.
- Optimising deflection without re-contact rate and CSAT.
- Measuring router savings per token rather than per completed task.
- Failure modes with no observable symptom. "It might hallucinate" is not a failure mode.
- No eval strategy, or evals described as a phase rather than a component.
- Forgetting the conventional parts: backpressure, hot shards, idempotency, migrations, noisy neighbours.
- No rejected alternatives. A design with no "X over Y because Z" reads as recitation.

## Cheat card

```
THE SIX SLOTS (every design, every time)
  1 CLARIFY (6 min)  what the number MEANS · read:write · latency · tenant · "correct"
  2 ARCHITECT (10)   write path and read path drawn SEPARATELY
  3 DECIDE (12)      3-5 forks as "X over Y because Z, at the cost of W"
  4 SIZE (6)         QPS · bytes · tokens → $/request → $/month.  UNPROMPTED.
  5 BREAK (6)        failure → OBSERVABLE SYMPTOM → mitigation
  6 DEFEND (5)       the 3 hardest follow-ups, answered first

WHAT MAKES GENAI DIFFERENT (and what doesn't)
  PROBABILISTIC → eval is a COMPONENT · EXPENSIVE $0.01-0.30/req → cost model is
  ARCHITECTURE · SLOW 1-10 s → streaming/caching/step-reduction are architecture
  UNCHANGED: backpressure · hot shards · idempotency · migrations · noisy neighbours

7 RECURRING PATTERNS
  1 write path != read path        2 TWO-STAGE retrieval is universal
    (binary→full · vector→reranker · graph→vector · cheap model→strong)
  3 enforcement boundary must be UNBYPASSABLE (gateway+netpol, perms engine, index predicates)
  4 version everything behaviour-changing, put it ON THE TRACE
  5 $/request out loud, then $/month, then lever ordering
  6 every failure needs an OBSERVABLE symptom
  7 FILTER (classifier, label, prompt) vs BOUNDARY (perms, netpol, sandbox). Never conflate.

KEY NUMBERS
  pgvector vs dedicated engine boundary          ~5-10M vectors
  1024-dim: fp16 2 KB · int8 1 KB · binary 128 B → 100M vectors = 200 GB / 100 GB / 12.8 GB
  AWS S3 Vectors: 10M vec + 1M q/mo = $11.38 · 500M + 10M = ~$1,320 (100s of ms latency)
  RRF fusion default k=60 · rerank 150→8 ~85 ms on a shared T4
  semantic cache HONEST hit rate 20-45% (30-70% FAQ); threshold ~0.83 MPNet / ~0.78 Albert;
    GPTCache default 0.7 is TOO LOOSE; start 0.92 and tune down 0.01/step
  RouteLLM 95% of GPT-4 quality @ 26% strong calls, ~48% cheaper than random;
    75% cut with judge-augmented data; prod reports 40-85% (plan for 40-50%)
  outcome-only evals pass 20-40% MORE cases than trajectory evals → they overstate readiness
  gen_ai.* OTel conventions: own repo since v1.42.0 (2026-06-12), still DEVELOPMENT → pin
  support deflection: 2026 median 41.2%, top quartile 58.7%; resets >70%, complaints <25%
    pure-AI CSAT 4.1/5 vs human 4.3/5; hybrid handoff narrows to ~0.05
  doc pipeline per page: text layer $0.0002 · OCR $0.0015 · VLM $0.006 → router = 5x saving
  code index: 40M LOC → ~1.2M chunks ≈ 0.9 GB (small!). Graph is the expensive part.
    tree-sitter graph over 31 repos: ~10x fewer tokens, ~2.1x fewer tool calls
  self-host breakeven: 8B on 2xA10G ~$1.5k/mo beats a commercial small model only
    above ~40-50% SUSTAINED utilisation
  canary detection floor: 3 pp judge delta needs n≈400 scored → 5% of 8k/day = ONE DAY
  guardrail FP budget: at 900 rps, 1% false-block = 780k legit requests/day. Target <0.2%.

THE 12, BY THEIR ONE DECISION
  1 RAG 10M    quantized 1st stage + rescore; ACLs INTO the index
  2 gateway    in-path proxy + network egress denial (~1% of spend it governs)
  3 orch       control/data plane split; eval-gated registration; hierarchical budgets
  4 memory     typed bi-temporal facts, async write; EXTRACTION is the cost (~$28k/mo)
  5 eval       one dataset store for CI + prod; deterministic before judges
  6 prompts    immutable content-addressed; rollback = POINTER FLIP
  7 cache      key = (query, tenant, corpus_ver, model, prompt_hash). Cache RETRIEVAL if unsure.
  8 guardrail  parallel detectors; input rail CONCURRENT with retrieval; FP rate is the cost
  9 docs       adaptive per-page routing (5x); tables ATOMIC; keep originals + versioned IR
 10 support    explicit escalation triggers + STRUCTURED handoff; never optimise deflection alone
 11 code       3 latency tiers, 3 context strategies; TESTS are the verifier
 12 router     tiered L0-L4; measure $/COMPLETED TASK, not per token

WHEN NOT TO
  RAG under ~50-100k tokens of stable content → cached prefix
  dedicated vector DB under ~5-10M vectors → pgvector
  gateway under ~$10-20k/mo → not yet
  platform under 5-10 agents → build 3 good services
  cross-session memory in v1 → earn it with a re-derivation rate
  semantic cache on low-repetition or auth-dependent answers → decline
  guardrails AS the security story → it's a filter with a false-negative rate
  router before bill attribution → you're guessing, with quality risk attached
```

## Sources

- [Generative AI System Design Interview: 2026 Guide](https://www.systemdesignhandbook.com/guides/generative-ai-system-design-interview/) — the probabilistic/expensive/slow framing and what interviewers probe; accessed 2026-07-26
- [GenAI System Design Interview — Worked Examples & Framework (2026)](https://myengineeringpath.dev/genai-engineer/system-design-interview/) — round structure and worked examples; accessed 2026-07-26
- [Every AI Engineer Interview Question You Need to Know in 2026 (from 100+ real interviews)](https://adilshamim8.medium.com/every-ai-engineer-interview-question-you-need-to-know-in-2026-from-100-real-interviews-b5b7ae4b961a) — the reported 40/30/20/10 topic mix; accessed 2026-07-26
- [Real-World GenAI Interview Questions I Faced](https://medium.com/@neodey/real-world-genai-interview-questions-i-faced-llms-security-compliance-scale-c696285b2b58) — reported questions on security, compliance and scale; accessed 2026-07-26
- [S3 Vectors for Enterprise RAG: Cost Math and Latency Limits](https://www.exploreagentic.ai/insights/s3-vectors-enterprise-rag/) — 10M vectors + 1M queries at $11.38/month, 500M + 10M at ~$1,320, and the latency caveat; accessed 2026-07-26
- [Vector Databases & RAG: Infrastructure-First Architecture](https://www.rack2cloud.com/vector-database-rag-strategy-guide/) — the ~5-10M vector pgvector boundary, sharding and replication as ordinary distributed-systems problems; accessed 2026-07-26
- [Enterprise RAG System Cost Guide for 2026](https://www.ment.tech/blog/cost-to-build-rag-system-enterprise-ai-2026/) — enterprise build-cost bands and the multi-source/compliance requirements; accessed 2026-07-26
- [Multi-Tenant LLM Serving: Per-Customer Isolation, Token Quotas, Production SaaS Architecture (2026)](https://www.spheron.network/blog/multi-tenant-llm-serving-gpu-cloud/) — per-tenant quota and isolation patterns; accessed 2026-07-26
- [Per-Tenant LLM Cost Attribution for Multi-Tenant SaaS](https://particula.tech/blog/per-tenant-llm-cost-attribution-multi-tenant-saas) — LiteLLM budgets are dollar-based not token-based; pre-call estimate vs post-call reconciliation; accessed 2026-07-26
- [Rate Limiting in AI Gateway: The Ultimate Guide](https://www.truefoundry.com/blog/rate-limiting-in-llm-gateway) — per-team TPM/RPM/budget enforcement at a unified gateway; accessed 2026-07-26
- [AI Agent Workflow Orchestration: Temporal, Inngest, Restate (2026)](https://www.spheron.network/blog/ai-agent-workflow-orchestration-temporal-inngest-restate-gpu-cloud/) — the pair pattern, framework inside engine; accessed 2026-07-26
- [Building an Agentic-Ready Kubernetes Platform in 2026](https://simplyblock.io/blog/building-an-agentic-ready-kubernetes-platform-in-2026/) — independently scalable but policy-coordinated planes; accessed 2026-07-26
- [Design Patterns for Deploying AI Agents with Model Context Protocol](https://arxiv.org/abs/2603.13417) — the identity-propagation, tool-budgeting and error-semantics gaps; accessed 2026-07-26
- [Agent Memory at Scale 2026: Letta, Zep, Mem0, LangMem compared](https://agentmarketcap.ai/blog/2026/04/10/agent-memory-vendor-landscape-2026-letta-zep-mem0-langmem) — Zep 63.8% vs Mem0 49.0% LongMemEval, graph traversal 50-150 ms vs 10-50 ms vector-only; accessed 2026-07-26
- [AI Agent Memory 2026: Progress Benchmark Report](https://mem0.ai/blog/state-of-ai-agent-memory-2026) — Mem0 92.5% LoCoMo, 94.4% LongMemEval, <7k tokens/retrieval, 91% lower p95 (vendor-reported); accessed 2026-07-26
- [AI Agent Trajectory Testing 2026: LangSmith vs Braintrust vs Phoenix vs Galileo](https://genai.qa/ai-agent-trajectory-testing-2026/) — outcome-only evals pass 20-40% more cases than trajectory evals; accessed 2026-07-26
- [Best AI governance platforms for LLM applications (2026)](https://www.braintrust.dev/articles/best-ai-governance-platforms-llm-applications-2026) — eval-time gating, golden datasets, CI release gates; accessed 2026-07-26
- [Prompt Release Workflow: shipping LLM prompt changes without breaking production](https://pub.towardsai.net/prompt-release-workflow-how-to-ship-llm-prompt-changes-without-breaking-production-ab6795272027) — 5-10% canary slice and eval-scored canaries; accessed 2026-07-26
- [Prompt Versioning and Change Management in Production AI Systems](https://tianpan.co/blog/2026-03-13-prompt-versioning-change-management-production) — immutable versioned artifacts in a registry, PR review plus automated eval as a required check; accessed 2026-07-26
- [An Update on Recent Claude Code Quality Reports](https://www.anthropic.com/engineering/april-23-postmortem) — three simultaneous harness changes, no model change; accessed 2026-07-26
- [LLM Semantic Caching: the 95% hit-rate myth](https://dev.to/gauravdagde/llm-semantic-caching-the-95-hit-rate-myth-and-what-production-data-actually-shows-8ga) — honest 20-45% range; the $47k → $12.7k case; accessed 2026-07-26
- [Semantic Caching for LLM Inference: GPTCache, Redis Vector Cache, Prompt Cache (2026)](https://www.spheron.network/blog/semantic-cache-llm-inference-gpu-cloud/) — threshold 0.92 start with 48-hour false-positive monitoring; MPNet 0.83 / Albert 0.78 optima; accessed 2026-07-26
- [NVIDIA NeMo Guardrails on GPU Cloud (2026)](https://www.spheron.network/blog/nemo-guardrails-production-deployment-llm-gpu-cloud/) — Colang 2.0 sub-50 ms per check on GPU; input/output/dialog/tool rails; accessed 2026-07-26
- [LLM Guardrails: Production Safety Layers Reference 2026](https://www.digitalapplied.com/blog/llm-guardrails-production-safety-layers-reference-2026) — unbudgeted guardrail latency; open-weight classifier vs commercial policy surface; accessed 2026-07-26
- [LlamaFirewall: an open-source guardrail system for secure AI agents](https://arxiv.org/pdf/2505.03574) — layered detector architecture; accessed 2026-07-26
- [The Lethal Trifecta: A 2026 Defence Architecture for AI Agents](https://thebrightbyte.com/playbook/expertise/lethal-trifecta-ai-agent-defense-architecture-2026) — no execution path holds all three legs; accessed 2026-07-26
- [Design Patterns for Securing LLM Agents against Prompt Injections](https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/) — the six patterns, dual-LLM, CaMeL; accessed 2026-07-26
- [MultiDocFusion: Hierarchical and Multimodal Chunking for RAG on Long Industrial Documents](https://arxiv.org/pdf/2604.12352) — 1,000-token target with a 1,200-token table cap, 5% overlap, 30-token minimum; accessed 2026-07-26
- [MinerU2.5-Pro: data-centric document parsing at scale](https://arxiv.org/pdf/2604.04771) — pipeline-vs-end-to-end tradeoff, error propagation against debuggability; accessed 2026-07-26
- [Document Parsing for RAG: A Complete Guide for 2026](https://www.omdena.com/blog/document-parsing-for-rag) — staged pipeline and adaptive per-page routing; accessed 2026-07-26
- [AI Customer Support Metrics: Deflection + CSAT Framework (2026)](https://www.digitalapplied.com/blog/ai-customer-support-metrics-deflection-csat-framework-2026) — median 41.2% / top quartile 58.7% deflection, 22% escalation assumption, CSAT 4.1 vs 4.3, deflection needs pairing with re-contact; accessed 2026-07-26
- [Code Intelligence & Code-Graph Indexing for AI Agents](https://anthonywest.co.uk/research/code-intelligence-indexing-2026-openai) — tree-sitter knowledge graph over 31 repos: ~10× fewer tokens, ~2.1× fewer tool calls; accessed 2026-07-26
- [AI Coding Assistants for Large Codebases: Architecture, Evaluation, Best Practices (2026)](https://blog.kilo.ai/p/ai-coding-assistants-for-large-codebases) — hybrid AST/code-graph plus vector indexing; accessed 2026-07-26
- [LLM Model Routing in 2026: Cost-Quality Optimization](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide) — RouteLLM 95% quality at 26% strong calls, ~48% cheaper than random, 75% with judge-augmented data; 40-85% production range; pre-request rules vs at-inference cascades vs post-response retry; accessed 2026-07-26
- [The state of the OpenTelemetry GenAI semantic conventions (July 2026)](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/) — `gen_ai.*` moved to a dedicated repo at v1.42.0 on 2026-06-12, still Development status; accessed 2026-07-26
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — why long context does not eliminate retrieval; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
