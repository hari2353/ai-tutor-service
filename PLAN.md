# AI TUTOR SERVICE — Master Plan v0.3

**Student:** Hari Siva Rami Dwarampudi — Principal AI Engineer, 7+ yrs (Cornerstone OnDemand)
**Mode:** 🔴 **ACTIVELY INTERVIEWING** · target: anything better than Cornerstone
**Cadence:** weekends (~9h) + optional 20-min weekday drills
**Constraints:** fully local / free tier · local GPU + Colab · zero cloud spend
**Scale:** **34 tracks · 390 modules · 891 hours** — of which a **29-module, 79-hour, 9-weekend sprint** is what actually decides your next loop.

---

## 0. The three-tier structure

The curriculum got large enough that "study everything" stopped being a plan. So there are now three tiers, and the app enforces them:

| Tier | Size | What it is |
|---|---|---|
| **SPRINT** | 29 modules · 79h · **9 weekends** | The set that decides interview outcomes. Ordered by weekend, and the quest generator follows that order exactly. Bypasses all prerequisite gating. |
| **PHASE A — core** | ~220 modules | Everything else you'd be embarrassed not to know for these roles. |
| **PHASE B — mastery** | ~140 modules | Depth that makes the sprint knowledge permanent rather than crammed: computer systems, RL, Rust, quant finance, blockchain, quantum, frontier AI. |

**Open `app/index.html` and the top card tells you exactly which weekend you're on and how many hours remain.**

---

## 1. What changed in v0.3

Everything you flagged, plus the gaps I found reviewing it back.

**Ten new tracks:**

| Track | Why |
|---|---|
| **T18 Data Engineering & Warehousing** | PySpark from scratch → Catalyst/Tungsten, shuffle/skew/AQE · Databricks vs Snowflake vs BigQuery vs Redshift (honest matrix) · lakehouse/Iceberg · Airflow from scratch · bronze/silver/gold modeling |
| **T19 Testing & Quality Engineering** | Unit, integration (Testcontainers), contract, regression/golden baselines, E2E · **JMeter, Locust, k6, Gatling** · chaos · **testing ML and testing LLM systems** (non-determinism, judge drift) · mutation testing |
| **T27 Tooling, Docker & Debugging Mastery** | Docker essentials → every command → Dockerfile mastery → debugging containers (OOMKilled, exit codes, nsenter, dive) · Git internals · **PR review at speed** · **reviewing AI-written code** · debuggers in every language · production debugging (core/thread/heap dumps) |
| **T28 AI-Assisted Architecture (Claude)** | How Claude Code actually works · CLAUDE.md design · authoring skills · subagent isolation · spec-driven development · agentic refactors with guardrails · **when NOT to let an agent write it** |
| **T20 Rust** | Ownership/borrowing/lifetimes · async/Tokio · axum services · **Rust in the AI stack** (tokenizers, candle, PyO3) · Rust vs Go vs Python selection criteria |
| **T26 Frontier AI** | **World models** · **LeCun's JEPA / V-JEPA 2** · **NVIDIA Cosmos & Isaac Sim** · **VLA robotics (GR00T)** · ImageBind · voice/realtime speech · video diffusion · reasoning models |
| **T22 Blockchain & Smart Contracts** | Crypto primitives → build a blockchain from scratch → consensus → EVM → **Solidity** → contract security (reentrancy, oracle manipulation) → rollups → *when blockchain is the wrong answer* |
| **T23 Quantum Computing** | Qubits with the actual linear algebra → gates/circuits → Deutsch-Jozsa/Grover/Shor → Qiskit hands-on → error correction/NISQ → **post-quantum cryptography** |
| **T24 Financial Engineering & Banking** | **Time series from scratch** (stationarity, ARIMA, GARCH, TFT/TimesFM) · backtesting without leakage (purging/embargo) · market microstructure · **Black-Scholes derived**, Greeks · VaR/CVaR · **Basel I→IV** · **Model Risk Management / SR 11-7** |
| **T25 Product Thinking & Business (MBA)** | JTBD, discovery, north-star metrics, **A/B testing done properly**, strategy/moats/Wardley, unit economics & the cost of an AI feature, writing the business case |

**Gaps I filled inside existing tracks:**

- **RAG (T06) +7 modules** — semantic search (lexical→vector→hybrid→learned), **multilingual embeddings** (your 22-locale reality), accuracy tuning (Recall@k→MRR→nDCG + the error-analysis loop), **metadata & filtering design**, **the latency/accuracy/cost triangle**, **semantic caching** (exact + semantic + prefix layers, vCache), structuring source data
- **Agentic (T07) +6** — **structured output** (JSON schema, constrained decoding, repair loops), **prompt versioning** (registries, A/B rollout, auto-revert on regression), **guardrails** in/out, **explainability & attribution**, **testing agents** (golden trajectories, CI gates), **zero → production capstone**
- **Databases (T17) +3** — **OLTP vs OLAP vs HTAP**, **1NF→BCNF→4NF and deliberate denormalization**, **star vs snowflake schema, SCD types 0-6, grain**
- **DSA (T02) +5 graph modules** — representations & invariants, shortest paths (Dijkstra/Bellman-Ford/Floyd/A*/Johnson), MST & max-flow/min-cut, SCC/bridges/2-SAT, **graphs in the wild** (dependency resolution, GraphRAG, PageRank)
- **Deep Learning (T04) +2** — **the neuron → forward propagation → loss → backpropagation by hand**, then **backprop derived** (chain rule, Jacobians, vanishing/exploding). You were right that this was buried inside "autograd"; it's now explicit and first.
- **LLM (T05) +1** — **autoregression**: next-token prediction, teacher forcing, exposure bias
- **Backend (T11) +2** — **porting FastAPI → Go, benchmarked, and when it's wrong** · **monolith vs modular monolith vs microservices vs monorepo**
- **DevOps (T12) +5** — **Jenkins from scratch** (declarative pipelines, shared libraries, agents) · **ECR vs Artifactory vs Nexus vs GHCR** · **EKS vs ECS vs Fargate decision matrix** · **SSM Parameter Store vs Secrets Manager vs AppConfig** · **local↔cloud parity** (LocalStack, Testcontainers, devcontainers, Ollama)

**New in the house format — "Lineage: past → present → future".** Every deep dive now opens with what the technology replaced and why, where the consensus actually sits today (and what's merely published versus deployed), and where it's heading with the uncertainty flagged. This is what makes an answer sound like judgment rather than recall, and it's what an interviewer is testing with "where do you see this going?"

**Two new skills** — `/tutor-company` and `/tutor-debrief` (see §4).

---

## 1b. What changed in v0.4

**Three more tracks:**

| Track | Why |
|---|---|
| **T29 Networking & Protocols** (14 modules) | OSI vs TCP/IP · IP addressing/CIDR/NAT · **TCP deep: handshake, session lifecycle, the state machine, TIME_WAIT** · congestion control, Nagle, keepalive, backlog · **TCP vs UDP vs raw IP vs QUIC** · TLS 1.3 + mTLS · **why GET vs POST vs PUT vs PATCH** (idempotency, safety, caching) · HTTP/1.1 vs 2 vs 3 · **curl mastery** · **gRPC deep** (protobuf, HTTP/2 framing, 4 RPC types, deadlines, streaming) · **REST vs gRPC vs GraphQL vs WebSocket vs SSE decision matrix** · DNS & load balancer internals · **network debugging** (tcpdump, Wireshark, ss, dig, mtr) · network failure modes |
| **T30 Auth & Application Security** (12 modules) | authn vs authz · sessions vs tokens · **JWT deep** (header/payload/signature, HS vs RS vs ES, JWKS, kid, clock skew) · **JWT attacks** (alg=none, key confusion, replay, the revocation problem) · access vs refresh tokens, rotation, where to store them · **OAuth 2.0 + OIDC** (auth code + PKCE, client credentials, device flow) · SSO/SAML/federation/mTLS · **XSS, CSRF, CORS, SSRF** · **SQL injection** (you published a paper on it — now weaponized) · API security & OWASP API Top 10 · applied crypto (bcrypt/argon2, AES-GCM) · threat modeling |
| **T31 Reinforcement Learning** (14 modules) | The RL problem framing · **MDPs and Bellman derived** · policy/value iteration from scratch · MC vs TD · **Q-learning vs SARSA** · exploration · **DQN built from scratch** (replay, target nets, Double/Dueling/Rainbow) · **policy gradients** (REINFORCE derived, baselines, actor-critic) · **PPO & TRPO** (the workhorse of RLHF) · continuous control (DDPG/TD3/SAC) · model-based & MCTS/AlphaZero · offline RL · **RL for LLMs** (RLHF→DPO→GRPO, reward hacking) · **why most RL projects fail** |

**Kubernetes went from 2 modules to 7** — objects (Pod→Deployment→StatefulSet→DaemonSet→Job), control plane/etcd/scheduler/operators, **networking** (service types, kube-proxy, Ingress, CNI, DNS, NetworkPolicy), storage & RBAC, scaling (HPA/VPA/KEDA/cluster autoscaler), **troubleshooting** (CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending, Evicted), and production concerns (probes, PDBs, requests/limits, multi-tenancy, cost).

**System Design gained the craft layer (+6):** back-of-envelope **estimation and guesstimates** · **how to draw a system** (C4, sequence, dataflow, deployment — live) · **designing from scratch** as a repeatable method · **how to choose between systems** (decision frameworks, scorecards, reversible vs one-way doors) · **POC → prototype → MVP → production** and what changes at each gate · **real case studies** (outages, migrations, architectures that shipped).

**Data engineering gained (+3):** **EMR deep** (clusters vs serverless, Steps API, bootstrap, packaging, spot strategy) · **scheduling & auto-triggering** (cron vs event vs sensor, EventBridge, Step Functions, S3 events) · **backfills, replays, idempotent reruns**.

---

## 2. All 31 tracks

**Sprint-bearing (the 8 weekends):** T07 Agentic AI · T21 Architecture & Design Principles · T06 RAG · T05 LLM Internals · T10 System Design · T17 Databases · T08 Eval & Observability · T14 Behavioral & Principal

**Phase A — core:** T02 DSA (21 patterns + 5 graph modules) · T18 Data Engineering · T19 Testing · T27 Tooling & Debugging · T28 AI-Assisted Architecture · T15 Interview Simulator · C-AWS Atlas

**Phase B — mastery:** T01 Python & SWE Craft · T03 Classical ML · T04 Deep Learning · T09 MLOps/LLMOps · T11 Polyglot Backend · T12 DevOps & Security · T13 SDE Craft · T16 Computer Systems (transistor→runtime) · T20 Rust · T22 Blockchain · T23 Quantum · T24 Finance & Banking · T25 Product/MBA · T26 Frontier AI · C-Azure · C-GCP

Full module lists live in `app/build_data.py` (the spec) and render in the app's Tracks tab.

---

## 3. The 9-weekend sprint

| WE | Modules | h |
|---|---|---|
| **1** | Agent loop from scratch · ReAct raw · **Resilience catalogue** | 8.5 |
| **2** | LangGraph I (StateGraph/Send) · LangGraph II (checkpointers, HITL, durable resume) · Tool engineering | 8.5 |
| **3** | Chunking · **Vector index internals (HNSW)** · Hybrid search + RRF · **Latency/accuracy/cost triangle** | 9.0 |
| **4** | **Context engineering** (compaction, subagents) · Agent memory · Multi-agent topologies *(and when not to)* | 8.5 |
| **5** | Attention (MHA→GQA→MLA, FlashAttention) · **Inference serving** (KV cache, PagedAttention, vLLM) · Distributed fundamentals | 9.0 |
| **6** | **Designing from scratch** (requirements→constraints→API→data→scale→failure) · **Back-of-envelope estimation** · **How to actually draw a system** (C4, sequence, dataflow, live on a whiteboard) | 8.0 |
| **7** | LLM-as-judge + failure modes · Agent eval · **MVCC & isolation** · **Query planner** | 9.5 |
| **8** | **Your 4 flagship systems as design docs** · **30-story STAR bank** · Design communication · Company-specific | 9.0 |
| **9** | **Zero → production multi-agent capstone** · 20 GenAI system designs | 9.0 |

**Weekend 6 is new and it moved deliberately.** The old plan had you do 20 system designs before ever learning how to run a design session — backwards. Design *craft* (method, estimation, diagramming, tech selection) now comes before design *practice*.

Boss battles slot in at weekends 2, 4, 7, 8, and a full 5-round loop at 9.

**If you get a real loop before weekend 9, jump to weekend 8 first.** Resume defense is the highest-ROI block in the entire plan — every bullet is an invitation, and you should be able to hold 45 minutes on any of them.

---

## 4. Skills (12, saved to your account — work in any session)

| Skill | What it does |
|---|---|
| `/tutor-start` | Today's quest, due cards, where you left off |
| `/tutor-deepdive` | New module in house format, now including lineage |
| `/tutor-lab` | From-scratch, test-driven lab |
| `/tutor-drill` | Socratic quiz, graded, weak spots queued |
| `/tutor-mock` | Scored mock round against a real rubric |
| `/tutor-review` | Principal-level code review |
| `/tutor-cheatsheet` | One-pager + flashcards |
| `/tutor-progress` | Honest read on where you stand |
| `/tutor-update` | **Delta** from AWS/Azure/GCP feeds + AI stack since last run |
| `/tutor-add` | Append content, reindex |
| **`/tutor-company`** | **Paste a JD → researched prep pack (their stack, loop structure, honest fit table, 25 likely questions, your gaps) → then role-plays as that company's interviewer** |
| **`/tutor-debrief`** | **After a real interview: logs the questions, diagnoses whether it was knowledge/structure/nerves, queues the gaps, and auto-promotes any topic seen in 2+ interviews into the sprint. Builds `mocks/PATTERNS.md` — the highest-signal study list you'll have.** |

The last two close the loop: prep against a real JD → interview → debrief → the curriculum re-prioritises itself from real evidence.

---

## 5. Build phases

| Phase | Deliverable | Status |
|---|---|---|
| **P0** Foundation | Scaffold, app, 12 skills, cross-cloud map, exemplar deep dive + lab + 28 flashcards | ✅ done |
| **P1** Sprint content | All 26 sprint modules written, with labs | ← next |
| **P2** Cloud atlas | AWS/Azure/GCP service catalogs, IAM/serverless/GenAI deep dives |
| **P3** DSA + LLM | 21 patterns + 5 graph modules × 3 languages, 250 problems; T05 complete |
| **P4** Data + Testing + Tooling | T18, T19, T27, T28 |
| **P5** Systems + breadth | T16, T01, T03, T04, T09, T11, T12, T13, T20 |
| **P6** Specialist | T22 blockchain, T23 quantum, T24 finance, T25 product, T26 frontier AI |

Re-orderable at any point. Nothing is coupled.

---

## 6. Known tensions (stated, not hidden)

- **891 hours is well over two years of weekends.** That's fine — it's a reference library with a sprint on top, not a queue to drain. The sprint is the plan; the rest is depth you pull on when a topic comes up.
- **T22/T23/T24 won't help your next interview.** Blockchain, quantum, and quant finance are Phase B for a reason. They're in because you asked and because they're genuinely interesting, not because they move your loop odds.
- **RL is Phase B too, and that's a real call.** Reinforcement learning matters enormously for understanding RLHF/PPO/GRPO — but for the roles you're targeting, being able to *explain* the RLHF→DPO→GRPO progression (which is in T05, weekend 5 territory) matters far more than being able to implement DQN. T31 is for genuine depth, not for the loop.
- **Breadth has a cost.** 34 tracks risks a mile wide and an inch deep. The sprint tier and the `critical` tag exist specifically to counteract that. If you feel scattered, do only sprint modules until weekend 9.
- **Nothing outside the exemplar is written yet.** 390 modules are *scoped*, one is *written*. That's deliberate — you approve the bar before mass production — but don't mistake the index for the content.
