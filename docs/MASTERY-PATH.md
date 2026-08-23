# The Mastery Path — reverse-engineered

> Complements `ROADMAP.md` (interview sprint) and `LEARNING-PATH.md` (prereq order). This file answers: what does 20-year mastery actually consist of, and what's the fastest honest route there on zero budget?

---

## 0. What seniority actually is (the parts courses never teach)

Courses transfer knowledge. Seniority is six **compounding assets** — none of them purchasable, all of them farmable. The curriculum here (`app/data/curriculum.json`: 36 tracks / 456 modules, sprint tier = 32 modules / 10 weekends) supplies knowledge; these assets decide whether you're senior or principal.

| # | Asset | What it actually is | How it forms (the honest way) | Fake-the-loop until it forms |
|---|---|---|---|---|
| 1 | **War-story pattern library** | ~50 reusable situation→constraint→decision templates you pattern-match live in interviews and reviews | Surviving incidents, migrations, launches — then *extracting* the template | Mine your resume into `T14-star-bank` (30 stories). Force every past project through: situation → constraint → options considered → option rejected + why → outcome number. If a story lacks a rejected alternative, it's not done |
| 2 | **Failure-mode reflexes** | You hear a design and the top-3 ways it dies appear unbidden | On-call scar tissue; seeing the same 10 failures in 10 systems | Pre-mortem drill: before reading any module/design, write its top-5 failure modes; grade yourself against the material after. Run chaos labs (`T19-chaos-testing`, `labs/py/01-circuit-breaker`). Read Jepsen weekly until predictions precede conclusions |
| 3 | **Estimation muscle** | Fermi answers for QPS/GB/$/latency within 3× , instantly | Years of capacity plans corrected by reality | Daily 5-min guesstimate from `T10-estimation`; log guess → look up real number → note the miss factor. Never leave a design without a cost column. Re-do Weekend math from ROADMAP with different scale assumptions |
| 4 | **Taste (rejection lists)** | Knowing what NOT to build; opinions with receipts | Reviewing hundreds of designs/PRs and watching which decisions aged badly | Keep a rejection ledger: every decision gets ≥1 named alternative + kill reason (`T10-tech-selection`, `T13-technical-writing` ADR format). Review one OSS PR/day (`T27-pr-review`) and predict maintainer verdict first |
| 5 | **Communication ladders** | Same idea at 3 altitudes: 1-line exec / 1-page peer / 45-min deep dive | Being forced to brief VPs, then defend to ICs, repeatedly | Teach-backs (§3d). Rewrite your flagship design at 3 altitudes monthly (`T14-design-communication`). Record a mock HM grill; cut every sentence that starts with "so basically" |
| 6 | **Ownership scar tissue** | You've carried something through launch AND the pager AND the deprecation | End-to-end responsibility incl. aftermath | Own one public artifact completely (§4 capstone): ship it, break it, postmortem it publicly, deprecate v1. Run a personal game-day quarterly and write the blameless retro (`T13-incidents`) |

**The compounding rule:** each asset multiplies the others. War stories feed communication ladders; estimation makes taste falsifiable; ownership generates war stories. Ten years of this ≈ 20-year mastery, because most people get the experiences without running the extraction loop above.

---

## 1. Reverse-engineered ladder per cluster

Format per cluster: **(a)** mental models separating senior from staff+ · **(b)** canonical scars everyone eventually gets · **(c)** judgment calls juniors get wrong · **(d)** the 20% of depth giving 80% of interview signal.

### 1.1 Agentic/LLM systems (`T07`, `T05`)
| Lens | Content |
|---|---|
| (a) Mental models | The harness IS the product ("everything except the model"); reliability compounds multiplicatively (0.85^20 steps ≈ 4%); context is a budgeted resource, not a transcript; durable execution > smarter prompts |
| (b) Canonical scars | Un-checkpointed long runs dying at step 18/20; retry storms doubling provider bill; prompt regression shipped silently; injection via retrieved content; subagent context explosion |
| (c) Junior errors | Multi-agents everywhere (see `T07-multi-agent-topologies` "when NOT to"); trusting `InMemorySaver`; no kill switch/budget caps; conflating eval score with production quality |
| (d) 80% signal | Agent loop from scratch, checkpoint/resume economics, KV-cache + batching math, context-engineering moves with numbers, the RAG-vs-FT-vs-prompt tree |

### 1.2 RAG/search (`T06`, parts `T17`)
| Lens | Content |
|---|---|
| (a) Mental models | Retrieval quality dominates generation quality; recall@k → precision tradeoff is THE dial; hybrid lexical+dense because vocab mismatch never dies; reranking buys accuracy with latency you must justify |
| (b) Scars | Silent index drift after re-embedding; ACL leak via shared index; chunking strategy breaking on tables/code; pgvector bloat at 10M docs; semantic cache returning stale/wrong tenant hits |
| (c) Junior errors | Cosine similarity as religion; pre-filter vs post-filter confusion; evaluating with synthetic questions only; ignoring the latency/accuracy/cost triangle (`T06-latency-accuracy`) |
| (d) 80% signal | HNSW params (ef/M) vs recall@k; BM25+dense+RRF pipeline; error-analysis loop (queries where it fails and WHY); when a vector DB is the wrong answer |

### 1.3 Data engineering & warehouses (`T18`, `T17` OLAP half)
| Lens | Content |
|---|---|
| (a) Mental models | Storage layout determines query fate (row vs column, micro-partitions); idempotency is the load primitive; contracts make pipelines composable; bronze/silver/gold is dependency management for truth |
| (b) Scars | Skew melting one reducer; backfill corrupting gold for 3 days undetected; late-arriving data double-counted; schema change breaking 14 downstream dashboards; warehouse bill shock |
| (c) Junior errors | Treating Spark like pandas; no watermark on streams; testing only happy path; denormalizing "because warehouse"; ignoring partition pruning |
| (d) 80% signal | Shuffle/skew/AQE story; batch vs stream + CDC tradeoffs; star schema grain discipline; "walk me through a backfill without lying to finance" |

### 1.4 Classical ML → Recsys (`T03`, `T09`)
| Lens | Content |
|---|---|
| (a) Mental models | Leakage is the default state, not the exception; offline metric ≠ online value; ranking is a funnel (retrieval → filter → rank), optimize the biggest leak first; bandits when feedback loops matter |
| (b) Scars | Training-serving skew silently halving AUC; imbalanced labels making 99% accuracy worthless; cold-start killing new items; bandit exploiting one noisy arm |
| (c) Junior errors | AUC worship (`T03-metrics-calibration`); CV before time-split; more features "just in case"; ignoring calibration for downstream thresholds |
| (d) 80% signal | Boosted-tree internals (regularization, split finding); two-tower + MF retrieval; CMAB for personalization; how you'd detect skew in prod |

### 1.5 Distributed systems / storage (`T10`, `T17` engines, `T21`, `T29` failures)
| Lens | Content |
|---|---|
| (a) Mental models | Partitions are scheduled maintenance; CAP/PACELC forces paying either latency or consistency NOW; B+Tree vs LSM = read vs write amplification; consensus is expensive, buy it once at the base; exactly-once is an illusion assembled from at-least-once + dedupe |
| (b) Scars | Split brain after network blip; WAL fsync lies under load; MVCC write-skew bug found by accountants; thundering-herd cache expiry; xid wraparound freeze |
| (c) Junior errors | Retries without jitter/idempotency keys; "we'll add consistency later"; timeouts everywhere equal; sharding before measuring hot partitions |
| (d) 80% signal | Isolation anomalies by example; Raft vs gossip vs 2PC; LSM compaction tuning; design a rate limiter / URL shortener / feed with failure modes enumerated |

### 1.6 Cloud (multi) (`C-AWS`, `C-AZ`, `C-GCP`)
| Lens | Content |
|---|---|
| (a) Mental models | IAM is the real product surface; managed services trade control for 3am freedom; egress + idle GPUs dominate bills; the cloud atlas is one map with dialects (`clouds/CROSS-CLOUD-MAP.md`) |
| (b) Scars | Public S3 bucket via one wildcard; Lambda VPC cold-start surprise; NAT-gateway bill exceeding compute; Bedrock/SageMaker lock-in regret |
| (c) Junior errors | Region-pinning then complaining about latency; SG vs NACL confusion; assuming identical SLAs across providers; no cost alarms |
| (d) 80% signal | Policy evaluation logic walkthrough; serverless vs containers decision; multi-cloud honestly = data plane portability (Iceberg/ONNX/OAuth) |

### 1.7 K8s / platform (`T12` k8s half, `T16` containers)
| Lens | Content |
|---|---|
| (a) Mental models | Reconcile loops everywhere (declarative desired state); the scheduler is a bin-packer with opinions; requests/limits are a contract with the kernel; platform = paved road, not gate |
| (b) Scars | OOMKill from limits=requests cargo cult; node pressure evicting the monitoring stack first; etcd quorum lost during "routine" upgrade; GPU node pool idle at $8/hr |
| (c) Junior errors | Latest tag + no probes; liveness=readiness; YAML sprawl without GitOps; treating CrashLoopBackOff as mystery instead of checklist (`T12-k8s-troubleshooting`) |
| (d) 80% signal | Pod lifecycle + scheduling deep-dive; HPA/KEDA for LLM traffic; what happens pod→Service DNS→kube-proxy→container; write-a-controller intuition |

### 1.8 Observability / eval (`T08`, `T19` perf half)
| Lens | Content |
|---|---|
| (a) Mental models | Instrument the trajectory, not just the endpoint; evals are unit tests for nondeterminism; SLOs convert opinion to arithmetic; traces are the debugger of last resort |
| (b) Scars | Judge drift approving regressions for weeks; cardinality explosion killing Prometheus; alert fatigue hiding the real page; golden dataset rotting vs product |
| (c) Junior errors | Logging tokens/cost as afterthought; single aggregate metric (avg latency lies); evals only pre-launch; no span for tool calls |
| (d) 80% signal | Design an agent eval harness (`T08-eval-harness`, `T08-agent-eval`); LLM-as-judge failure modes + calibration; SLO/error-budget arithmetic; RED/USE on an LLM gateway |

### 1.9 Security / auth (`T30`, `T12` sec half, `T07` safety)
| Lens | Content |
|---|---|
| (a) Mental models | AuthN ≠ AuthZ ≠ Accounting; the token is a capability document; threat-model the trust boundaries, not the features; for agents, tools ARE the attack surface; secrets have lifetimes, not homes |
| (b) Scars | alg=none JWT acceptance; SSRF via webhook feature; refresh token never rotated; prompt-injected agent exfiltrating via tool args; kid-confusion key swap |
| (c) Junior errors | JWT for sessions + no revocation story; CORS `*` "temporarily"; permission checks in frontend only; OWASP LLM Top 10 treated as compliance checkbox |
| (d) 80% signal | OAuth code+PKCE flow drawn cold; session-vs-token honest tradeoff; STRIDE in 45 min; injection defense-in-depth for an agent (`T07-agent-safety`, `T07-risk-taxonomy`) |

### 1.10 Frontend-for-AI-UIs (`T33`, `T11` streaming half)
| Lens | Content |
|---|---|
| (a) Mental models | Streaming UX is a state machine (pending/tool-call/error/abort/resume); perceived latency beats p99; the browser main thread is a single-lane road; rendered model output is untrusted HTML |
| (b) Scars | WebSocket reconnect replaying entire history; token firehose freezing React; XSS via model-generated markdown; optimistic tool-call UI stuck forever on dropped stream |
| (c) Junior errors | Polling instead of SSE; storing stream state in global store; no abort controller; hydration mismatches blamed on "React weirdness" |
| (d) 80% signal | SSE vs WS tradeoffs + backpressure; reconciliation/keys mental model; streaming chat architecture sketch with abort/resume; CSP for LLM output |

---

## 2. Fast track on free/low-cost resources ONLY

Budget rule: **$0 unless a book is irreplaceable.** Allowed books (the only three): ① *Designing Data-Intensive Applications* (Kleppmann) ② *Designing Machine Learning Systems* (Huyen) ③ *AI Engineering* (Huyen, 2025). Everything else below is free. (Google SRE books are free online — they don't consume slots.)

### 2.1 Agentic/LLM systems → `T07-agent-loop-from-scratch` … `T07-agent-zero-to-prod`, `T05-*`
1. Anthropic *Building Effective Agents* + *Effective context engineering* (blog) → `T07-agent-loop-from-scratch`, `T07-context-engineering`
2. ReAct [2210.03629] · Reflexion [2303.11366] → `T07-react-pattern-raw`
3. Toolformer [2302.04761] + MCP spec/modelcontextprotocol.io → `T07-tool-engineering`
4. LangGraph docs + clone **langgraph**: corrupt a SqliteSaver blob mid-run, resume, explain semantics → `T07-langgraph-core`, `T07-langgraph-durable`
5. Attention [1706.03762] + Karpathy *Let's build GPT* (YT) + **nanoGPT** repo → `T05-build-nanogpt`; Stanford **CS336** lectures/assignments (GitHub, free) as the spine
6. FlashAttention [2205.14135] · GQA [2305.13245] · MQA [1911.02150] · RoPE [2104.09864] → `T05-attention`, `T05-positional`
7. Chinchilla [2203.02155] → `T05-pretraining`; Lost in the Middle [2307.03172] → `T07-context-engineering`
8. vLLM/PagedAttention [2309.06180] + clone **vllm**: force `gpu_memory_utilization=0.3`, observe preemption/recompute → `T05-inference-serving`
9. DPO [2305.18290] · GRPO via DeepSeekMath [2402.03300] · R1 [2501.12948] → `T05-alignment`, `T31-rl-for-llms`
10. LoRA [2106.09685] · QLoRA [2305.14314]; speculative decoding [2211.17192] → `T05-finetuning`, `T05-sampling`
11. SWE-bench [2310.06770]; τ-bench [2406.12045] → `T07-agent-testing`

### 2.2 RAG/search → `T06-chunking` … `T06-semantic-caching`
1. RAG [2005.11401] · DPR [2004.04906] → `T06-chunking`, `T06-embeddings-choice`
2. HNSW [1603.09320] + clone **hnswlib**: sweep ef/M, plot recall@10 vs latency → `T06-vector-index-internals`
3. ColBERT [2004.12832] · ColBERTv2 [2112.01488] → `T06-hybrid-search`, `T06-reranking`
4. **rank_bm25** repo + Elasticsearch similarity docs (BM25 params) → `T06-text-preprocessing`
5. HyDE [2212.10496] → `T06-query-transformation`; CRAG [2401.15884] · Self-RAG [2310.11511] · GraphRAG [2404.16130] → `T06-advanced-rag`
6. MTEB [2210.07316] · BGE-M3 [2402.03216] → `T06-embeddings-choice`, `T06-multilingual`
7. RAGAS [2309.15217] + clone **ragas**: break judge with adversarial contexts → `T06-rag-eval`
8. Clone **qdrant** or **pgvector**: load 1M chunks, tune filters pre/post, measure → `T06-metadata-design`, `T17-vector-db-compare`, `T06-latency-accuracy`

### 2.3 Data engineering & warehouses → `T18-*`
1. RDD paper (NSDI'12, free) + Spark SQL (SIGMOD'15, free) → `T18-pyspark-scratch`, `T18-pyspark-advanced`
2. Snowflake paper (SIGMOD'16, free) → `T18-snowflake`; Dremel (VLDB'10, free) → `T18-bigquery`
3. Delta Lake VLDB paper + Apache Iceberg docs → `T18-lakehouse`, `T18-databricks-vs-snowflake`
4. Airflow docs + Astronomer guides (free) → `T18-airflow`, `T18-scheduling-triggering`
5. Kimball Group free articles (dimensional techniques) → `T17-dimensional-modeling`, `T18-data-modeling-e2e`
6. DuckDB docs (OLAP intuition on a laptop) → `T17-oltp-vs-olap`; Great Expectations docs → `T18-data-quality`
7. Clone-and-break **pyspark** locally: inject skew, watch AQE kick in → `T18-pyspark-advanced`; double-trigger an Airflow DAG, prove idempotency → `T18-backfill-replay`

### 2.4 Classical ML → Recsys → `T03-*`
1. Stanford **CS229** notes + lectures (free) → `T03-linear-models`, `T03-regularization`
2. XGBoost [1603.02754] · CatBoost [1706.09516] → `T03-trees-boosting`; calibration [1706.04599] → `T03-metrics-calibration`
3. YouTube DNN [1606.07792] · Airbnb embeddings [1810.09959] · DLRM [1906.00091] → `T03-recsys`
4. LinUCB [1003.0146] → `T03-bandits`; StatQuest (YT) for anything rusty → any `T03`
5. scikit-learn user guide as lab manual; Feast docs → `T09-feature-stores`
6. Exercise: MovieLens MF vs two-tower, cold-start ablation; plant leakage in a Kaggle set, then find it → `T03-feature-eng`

### 2.5 Distributed systems / storage → `T10-distributed-fundamentals`, `T17-storage-engines` …
1. MIT **6.5840** (was 6.824): lectures on YT + Raft/KV labs (Go) → `T10-consensus-ordering`, `T10-distributed-fundamentals`
2. Raft paper (raft.github.io) + **etcd/raft** source skim → `T10-consensus-ordering`
3. Canon papers (all free): Dynamo (SOSP'07), GFS, Bigtable, Spanner (OSDI'12) → storage ladder inside `T17-storage-engines`, `T17-wide-column-kv`
4. CMU **15-445** (Pavlo, YT + projects): B+Tree/LSM/MVCC/projects → `T17-storage-engines`, `T17-mvcc-isolation`, `T17-query-planner`
5. Book ① DDIA ch. 3–9 as the connective tissue for this whole cluster
6. Jepsen.io analyses (free) weekly → `T29-net-failures`, `T10-messaging`; Kafka NetDB'11 paper + docs on EOS → `T10-messaging`
7. FoundationDB simulation lectures (free) → testing mindset for `T17-wal-recovery`
8. Build a bitcask-style KV; `kill -9` mid-write, recover, explain torn writes → `T17-storage-engines`, `T17-wal-recovery`

### 2.6 Cloud (multi) → `C-AWS-*`, `C-AZ-*`, `C-GCP-*`
1. AWS Well-Architected whitepapers + IAM policy-eval docs → `C-AWS-iam`; Lambda docs (cold starts, SnapStart) → `C-AWS-lambda`
2. Microsoft Learn paths (free) → `C-AZ-identity`, `C-AZ-data`; GCP docs + free-tier sandbox → `C-GCP-data`, `C-GCP-ai`
3. FinOps Framework (free) → `C-AWS-observability-cost`, `T09-gpu-cost`
4. LocalStack (free tier) + Testcontainers → `T12-local-cloud-parity`
5. Exercise: deploy the same LLM gateway on Lambda vs Cloud Run vs Container Apps; plot cold-start + $/1k-req curves; write the selection matrix → feeds `T09-bedrock-vs-sagemaker`

### 2.7 K8s / platform → `T12-k8s-*`
1. **Kubernetes The Hard Way** (GitHub, free) once, slowly → `T12-k8s-core`
2. kubernetes.io task pages (Services/DNS, PVs, RBAC) → `T12-k8s-networking`, `T12-k8s-storage-config`
3. NVIDIA device-plugin + GPU scheduling docs → `T12-k8s-scaling`; Kubebuilder book → write a toy operator → `T12-k8s-production`
4. Terraform tutorials (free) → `T12-terraform`; GitHub Actions docs → `T12-cicd`
5. Clone-and-break a **kind** cluster: kill an etcd member (quorum), delete CoreDNS, ship a bad probe → `T12-k8s-troubleshooting`

### 2.8 Observability / eval → `T08-*`
1. Google SRE book + Workbook (free at sre.google/books) → `T08-classic-obs`
2. OTel GenAI semantic-conventions spec (free) → `T08-otel-genai`; Prometheus docs/alert design → `T08-classic-obs`
3. Judging LLM-as-a-Judge [2306.05685] · G-Eval [2303.16634] → `T08-llm-as-judge`
4. Self-host **langfuse**, run **promptfoo** in CI → `T08-obs-platforms`, `T08-ragas-deepeval`, `T08-eval-harness`
5. Exercise: instrument your capstone with OTel agent spans; inject judge drift on purpose; prove your CI gate catches it → `T08-agent-eval`, `T19-llm-testing`

### 2.9 Security / auth → `T30-*`, `T07-agent-safety`
1. OWASP Top 10 + API Top 10 + LLM Top 10 (free) → `T12-owasp`, `T30-api-security`, `T07-agent-safety`
2. PortSwigger Web Security Academy (fully free labs) → `T30-web-attacks`, `T30-injection`
3. RFC 6749 + RFC 9700 (OAuth BCP) + *OAuth 2.0 Simplified* (free) + Auth0 JWT handbook (free ebook) → `T30-oauth-oidc`, `T30-jwt-deep`, `T30-jwt-security`
4. Cryptopals challenges (free) → `T30-crypto-practice`; NIST SP 800-207 (zero trust) → `T12-authz`
5. Clone-and-break **OWASP Juice Shop**: exploit, then patch at the framework layer → `T30-web-attacks`; STRIDE your capstone → `T30-threat-modeling`

### 2.10 Frontend-for-AI-UIs → `T33-*`
1. react.dev docs (excellent, free) → `T33-react-core`, `T33-react-advanced`; MDN SSE/WebSocket/Streams → `T33-streaming-ai-ui`
2. web.dev vitals guides → `T33-web-performance`; MDN CSP → `T33-frontend-security`
3. Clone **vercel/ai-sdk**: break the stream (abort mid-token, resume, throttle), study their state machine → `T33-streaming-ai-ui`, `T33-state-management`
4. Exercise: streaming chat UI with optimistic tool-call rendering + abort/resume; render model markdown under a strict CSP; measure INP during a token firehose → `T33-browser-rendering`, `T33-web-performance`

---

## 3. Deliberate-practice loops (self-learning engine)

This is what makes the plan SELF-PACED: fixed loops, variable speed. Miss a weekend, resume the loop — never restart the plan.

### 3.1 Weekly loop (weekends-only compatible)
| Slot | Duration | Activity | Feeds |
|---|---|---|---|
| Depth block ×2 | 2 × 90 min | One module + its lab, tests passing (`ROADMAP.md` rule 2) | Cluster depth (§1) |
| Build/break block | 90 min | §2 clone-and-break exercise OR capstone work | Portfolio artifacts (§4) |
| Mock-or-drill | 45–60 min | Alternate: `/tutor-mock {coding,design,genai,behavioral}` ↔ timed drill (`drills/`) | Score log → repair queue |
| Recall | 2 × 30 min | Due flashcards only (app decks); weekday 20-min sessions keep this alive | Retention |

### 3.2 Monthly teach-back (the extraction engine)
1. Pick the month's deepest topic. Write the cheatsheet **from memory first** into `cheatsheets/`.
2. Compare against module + sources; log deltas (what you got wrong ≠ what you forgot ≠ what the field changed).
3. Deltas become next week's flashcards and the next mock's grilling topics.
4. Every third teach-back: say it aloud as if to a VP (altitude 1) and as if to an IC (altitude 3).

### 3.3 Self-assessment rubric (score 0–5 per axis, per cluster)
Axes: **explain-cold** (teach it, no notes) · **build-from-scratch** (working core in a day) · **debug-warstory** (real incident told with numbers + lesson) · **tradeoff-defense** (reject ≥2 alternatives with reasons) · **estimate-live** (Fermi QPS/$/GB within 3×).

| Level | Band | Promotion criteria |
|---|---|---|
| Novice | 0–1 | → Proficient: pass explain-cold at 2 on all five axes after one teach-back cycle |
| Proficient | 2–3 | → Strong: build-from-scratch ≥3 with tests passing; one debug-warstory written up; estimate-live practiced 10× |
| Strong | 4 | → Principal-signal: hold 4+ on four axes simultaneously; survive a hostile mock (`T15-round-design`) at ≥80; tradeoff-defense includes a reversal you argue credibly |
| Principal-signal | 5 | Maintain: re-score after a 2-week gap (spaced check); a 5 that decays to 3 was never a 5 |

Log scores in `progress/` monthly; `/tutor-progress` turns gaps into the repair queue (Weekend-8 style).

---

## 4. The 12-month shape

Assumes: weekends (~9h) + optional weekday 20-min recall. Interviewing this week always overrides (ROADMAP rule 1). Bars: 70 senior-pass · 80 staff · 88 principal.

| Month | Focus | Concrete output | Exit gate |
|---|---|---|---|
| 1 | Sprint W1–4: agent loop → RAG → context/multi-agent | `labs/py/01-circuit-breaker` green; RAG cheatsheet | Bosses: coding + genai attempted |
| 2 | Sprint W5–8: LLM internals, distributed, eval, resume defense | 4 flagship design docs (`T10-resume-systems`); 30-star bank | Bosses: design + behavioral/HM |
| 3 | Sprint W9–10 close-out → **CONFIRM fill**: weakest 2 clusters from mock data get repair weekends | Full-loop logged; repair plan | `/tutor-mock full-loop` ≥ 70 |
| 4 | Phase B P0: `T05-build-nanogpt`, `T05-inference-serving`, `T06-advanced-rag`/`T06-rag-production` | **Artifact 1: mini-langgraph** (checkpoint/resume + interrupt, public repo) | Resume-checkpoint test survives `kill -9` |
| 5 | P0 cont.: `T07-production-agent-loops`, `T07-context-engineering`, `T05-alignment` | mini-langgraph README + bench numbers + design doc | Teach-back: durable execution, from memory |
| 6 | P1: `T17-storage-engines`, `T17-mvcc-isolation`, 6.5840 Raft lab, `T18-pyspark-advanced` | **Artifact 2: mini-vLLM** (paged-KV sim + continuous batching, throughput bench) | Explains PagedAttention math cold; rubric ≥4 on agentic axes |
| 7 | P1 cont.: `T08-*` full track, `T08-otel-genai`, `T19-load-testing` | **Artifact 3: eval harness** (golden sets + judge calibration + OTel spans + CI gate) | Injected judge drift caught by gate |
| 8 | Breadth: `T12-k8s-*`, `T12-terraform`, `T30-jwt-deep`/`T30-oauth-oidc`, cloud atlases | Capstone deployed on local k8s behind OAuth; game-day + postmortem | CrashLoopBackOff drill < 10 min to root cause |
| 9 | P2: `T03-trees-boosting`, `T03-recsys`, `T03-bandits`, `T33-streaming-ai-ui` | Streaming UI on capstone; ML design reps ×5 | Biweekly mocks; `/tutor-mock full-loop` ≥ 80 |
| 10 | **Capstone integration**: agent platform = LangGraph + Postgres checkpointer + MCP tools + eval gate + budget caps + HITL (ROADMAP WE-25) | Public repo: README, architecture doc, cost/latency bench | Threat-modeled (STRIDE); OTel traces complete |
| 11 | Portfolio hardening: 3 artifacts + capstone each get: 1-page doc, 5-min talk, failure-mode list | Personal "system tour" deck | Every artifact defensible 45 min (`T14-design-communication`) |
| 12 | Loop season: weekly full loops, repair from scores, negotiation prep | Offer-ready | `/tutor-mock full-loop` ≥ 88; rubric shows ≥4×four-axes on 6+ clusters |

**Priority order if time compresses:** P0 = Agentic/LLM + RAG (your interview targets) · P1 = Distributed/storage + Obs/eval (every loop touches them) · P2 = Data + K8s/cloud + Security · P3 = ML/recsys + Frontend. Artifacts 1–3 are chosen because each is *interview-provable*: an interviewer can ask "why?" five times and the code answers.
