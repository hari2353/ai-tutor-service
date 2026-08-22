# ROADMAP

> Mode: 🔴 actively interviewing · weekends primary (~9h) + optional 20-min weekday drills
> Phase A = pass loops now · Phase B = become the expert

---

## PHASE A — INTERVIEW SPRINT (weekends 1–8)

**Rule for this phase:** if you are interviewing *this week*, drop that weekend's breadth work and do the boss battle plus the weak-topic repair instead. Loops are the forcing function; the schedule serves them, not the other way round.

Each weekend ≈ 9h: **3h AI depth · 2h design/principles · 2h DSA · 1.5h databases/cloud · 0.5h review.**

---

### Weekend 1 — Agent fundamentals + resilience
| Block | Work |
|---|---|
| AI depth | `T07 agent-loop-from-scratch` · `T07 react-pattern-raw` · `T07 tool-engineering` |
| Principles | **`T21 resilience-catalogue`** ✅ *written* + lab `labs/py/01-circuit-breaker` · `T21 solid` |
| DSA | Two Pointers · Sliding Window · Fast & Slow |
| DB/Cloud | `T17 storage-engines` (B+Tree vs LSM) |
| Review | 28 resilience flashcards ✅ *seeded* |

**Why first:** the agent loop is the single most-asked topic for the roles you're targeting, and resilience patterns are the thing you flagged as missing — they also show up in *every* system design round regardless of company.

---

### Weekend 2 — LangGraph + durable execution · **BOSS: Coding**
| Block | Work |
|---|---|
| AI depth | `T07 langgraph-core` · `T07 langgraph-durable` (checkpointers, `interrupt()`, resume) · `T07 react-agent-internals` |
| Principles | `T21 outbox-saga-cqrs` · `T21 architecture-styles` |
| DSA | BFS · DFS · Top-K |
| DB/Cloud | `T17 mvcc-isolation` |
| ⚔️ | **`/tutor-mock coding`** — 45 min, 2 problems |

**The line that wins interviews here:** *"InMemorySaver doesn't survive a deploy. At ten tool-call steps with 85% per-step reliability, an un-checkpointed run completes ~20% of the time — better models don't fix network failures, checkpointing and resume do."*

---

### Weekend 3 — RAG end to end
| Block | Work |
|---|---|
| AI depth | `T06 chunking` · `T06 vector-index-internals` (HNSW params) · `T06 hybrid-search` (BM25+dense, RRF) · `T06 reranking` |
| Design | `T10 genai-designs` — enterprise RAG at 10M docs |
| DSA | Modified Binary Search · Two Heaps · Merge Intervals |
| DB/Cloud | `T17 vector-db-compare` — and when a vector DB is the wrong answer |
| Review | RAG cheat sheet |

---

### Weekend 4 — Context engineering + multi-agent · **BOSS: GenAI depth**
| Block | Work |
|---|---|
| AI depth | `T07 agent-memory` · `T07 context-engineering` (compaction, context editing, subagents) · `T07 multi-agent-topologies` |
| Design | `T10 genai-designs` — agent orchestration platform, agent memory service |
| DSA | 0/1 Knapsack · Unbounded Knapsack |
| DB/Cloud | `T17 postgres` (VACUUM, bloat, xid wraparound, pgvector) |
| ⚔️ | **`/tutor-mock genai`** |

**Know cold:** subagents with isolated context return 1–2k token summaries while spending tens of thousands internally; context editing alone gave a 29% lift in Anthropic's evals, and cut token use 84% over a 100-turn task. And the trap — *when NOT to go multi-agent*.

---

### Weekend 5 — LLM internals + distributed fundamentals
| Block | Work |
|---|---|
| AI depth | `T05 attention` · `T05 inference-serving` (KV cache math, PagedAttention, continuous batching) · `T05 finetuning` (the RAG-vs-FT-vs-prompt decision tree) |
| Design | `T10 distributed-fundamentals` (CAP/PACELC, replication, partitioning) · `T10 messaging` (Kafka semantics, exactly-once illusions) |
| DSA | Topological Sort · Union-Find · Graphs (Dijkstra) |
| DB/Cloud | `T17 mongodb` (replica sets, concerns, race conditions — your bullet) |

---

### Weekend 6 — Eval, observability, cloud · **BOSS: System design**
| Block | Work |
|---|---|
| AI depth | `T08 llm-as-judge` · `T08 agent-eval` · `T08 otel-genai` (GenAI semantic conventions) |
| Cloud | `C-AWS iam` · `C-AWS lambda` · `C-AWS ai-ml` (Bedrock/AgentCore) + skim `CROSS-CLOUD-MAP.md` |
| DSA | Trie · Monotonic Stack · Backtracking |
| DB/Cloud | `T17 query-planner` (EXPLAIN ANALYZE, join algorithms) |
| ⚔️ | **`/tutor-mock design`** |

---

### Weekend 7 — Resume defense · **BOSS: Behavioral + HM grill**
| Block | Work |
|---|---|
| Core | `T10 resume-systems` — write formal design docs for your 4 flagship systems: the 8-service recsys platform · the A2A + FastMCP system · Query Crafter · the Skillmaster pipeline |
| Behavioral | `T14 star-bank` (30 stories) · `T14 design-communication` · `T14 company-specific` |
| DSA | Timed mixed sets |
| ⚔️ | **`/tutor-mock behavioral`** then **`/tutor-mock hm`** |

**This is the highest-ROI weekend in the whole plan.** Every bullet on your resume is an invitation. The OOM fix, the OWASP remediation, the Java→Python migration, the 22-locale hardening, the 89% ETL latency cut, the MongoDB race conditions — each needs a 45-minute-defensible story with numbers, the alternative you rejected, and what you'd do differently.

---

### Weekend 8 — Repair · **BOSS: Full loop**
| Block | Work |
|---|---|
| All | Weak-spot repair driven entirely by your mock scores. `/tutor-progress` picks the targets. |
| ⚔️ | **`/tutor-mock full-loop`** — 5 rounds, scored as a real onsite |

**Bar:** 70 = passes a senior loop · 80 = staff · 88 = principal.

---

### Weekends 9–10 — Sprint close-out

The quest generator follows `SPRINT_WEEKENDS` in `app/build_data.py`, which now runs
ten weekends; these two were added after this file was first written and land last
on purpose — harness engineering names the parts you'll have built across W1–W9.

| WE | Block | Work |
|---|---|---|
| 9 | Capstone | `T07 agent-zero-to-prod` — the complete multi-agent system, end to end · `T10 genai-designs` (20 GenAI/agent designs) |
| 10 | Harness | `T07 harness-engineering` · `T07 loop-engineering` · `T28 claude-architect` |

---

## PHASE B — MASTERY

Starts once the sprint closes. The table below keeps its original numbering;
the app sequences everything by sprint order first.

Sequenced so each weekend still lands one thing you could be asked about, while building the foundation that makes the sprint knowledge permanent rather than crammed.

| WE | Depth | Breadth | DSA / Design |
|---|---|---|---|
| 9 | `T05 tokenization` + implement BPE · `T05 positional` | `T16 memory-hierarchy` (caches, false sharing, MESI) | Segment tree/BIT · vector DB design |
| 10 | `T05 build-nanogpt` — build and train it | `T16 cpu-microarch` · `T16 assembly` | Strings: KMP/Z/rolling hash |
| 11 | `T05 alignment` (SFT→DPO→GRPO) · `T05 quantization` | `T16 compilers` · `T16 cpython-runtime` | Greedy + exchange proofs |
| 12 | `T06 advanced-rag` (CRAG/Self-RAG/GraphRAG) · `T06 rag-production` | `T17 sqlserver` · `T17 clickhouse` | **BOSS: ML depth** |
| 13 | `T04 autograd` from scratch · `T04 architectures` | `T16 os-internals` · `T16 io-models` (epoll, io_uring) | Classic designs ×5 |
| 14 | `T04 training-engineering` · `T04 distributed-training` (DDP/FSDP/ZeRO) | `T16 networking-stack` · `T16 numerics` | Classic designs ×5 |
| 15 | `T03 trees-boosting` (XGBoost/LightGBM internals) · `T03 metrics-calibration` | `T11 java-modern` · `T11 jvm-tuning` | ML designs ×5 |
| 16 | `T03 recsys` · `T03 bandits` (CMAB — your bullet) | `T11 spring-boot` · `T11 resilience4j` | **BOSS: ML system design** |
| 17 | `T01 asyncio` · `T01 memory-oom` (your ClickHouse fix, rebuilt) | `T11 go-core` · `T11 go-services` | ML designs ×5 |
| 18 | `T05 embeddings-training` · `T05 multimodal` | `T11 node-ts` · `T11 react` (streaming agent UIs) | Classic designs ×5 |
| 19 | `T09 spark` (shuffle, skew, AQE) · `T09 model-cicd` | `T12 k8s-core` · `T12 k8s-scaling` (GPU scheduling) | GenAI designs ×5 |
| 20 | `T08 ragas-deepeval` · `T08 classic-obs` (SLO/error budgets) | `T12 terraform` · `T12 cicd` | **BOSS: full loop #2** |
| 21 | `T07 agent-safety` (injection, OWASP LLM Top 10) | `T12 owasp` · `T12 authz` · `T12 secrets` | GenAI designs ×5 |
| 22 | `T07 production-agent-loops` · `T07 agent-cost-routing` | `C-AZ identity` · `C-AZ ai` · `C-AZ functions` | Design: multi-tenant LLM gateway |
| 23 | `T06 rag-eval` · `T08 eval-harness` | `C-GCP iam` · `C-GCP ai` · `C-GCP data` (BigQuery) | Design: eval platform |
| 24 | `T04 compile-cuda` · `T04 export-optimize` · `T16 gpu-arch` | `T09 gpu-cost` · `T09 serving` | **BOSS: GenAI depth #2** |
| 25 | **Capstone**: production agent platform — LangGraph + Postgres checkpointer + MCP tools + memory service + OTel + eval gate + HITL + budget caps, on local K8s | `T13 vibe-coding` · `T13 refactoring` | Capstone design doc |
| 26 | `T21 gof-*` (all 23 patterns × 3 languages) · `T21 ddd` | `T17 sql-mastery` (60 SQL problems) · `T16 containers-low-level` | **BOSS: full loop #3** |

---

## Weekday micro-sessions (20 min, optional)

One flashcard set from the app. That's it. It keeps the "no-zero" streak alive and — more importantly — it's what makes a weekend-only cadence actually stick. Two weeks between touching a topic is enough to lose it without review.

---

## Rules

1. **Interviewing this week beats the schedule.** Swap in the relevant boss battle and repair.
2. **A module isn't done until its lab tests pass.** Reading is not learning.
3. **Log every mock score.** `/tutor-progress` is only honest if you feed it.
4. **Say "update" every couple of weeks** so the cloud atlas and agent-stack content don't rot.
5. **When a module feels easy, it's a flashcard, not a study session.** Move on.
