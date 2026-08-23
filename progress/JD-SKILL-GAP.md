# JD–Skill Gap Analysis

Generated: 2026-08-23 · Sources: `interview_prep_queue.json` (20 entries → **17 unique roles**), `resume1.txt`, `app/data/curriculum.json` (v0.3, 36 tracks, 452 modules) + `curriculum/**/*.md` + `clouds/**/*.md` filenames.
Module ids cited exactly as in `curriculum.json`. No curriculum/app files were modified.

---

## 1. JD digest — one row per unique role

| # | Company | Title | Score | Market | Top 8 demanded skills (from jd_snippet) |
|---|---------|-------|-------|--------|------------------------------------------|
| 1 | Siemens (Brightly) | Senior Machine Learning Engineer | **88** | India | RAG pipelines · prompt orchestration · tools/agents + guardrails · eval harnesses + latency/cost instrumentation · LoRA/QLoRA fine-tuning lifecycle · AWS prod (EKS/ECS/Lambda, SageMaker, Bedrock, EMR, MSK, Step Functions) · MLOps CI/CD (MLflow/Kedro/SageMaker Pipelines), registries, lineage, eval gates · CloudWatch/OpenTelemetry observability + cost controls |
| 2 | Regilient | Senior AI Lead Engineer | **88** | India | Agentic platform architecture · autonomous regulation monitoring · supplier-engagement agents · compliance data processing → declaration generation · AI standards/culture ownership · team leadership (1 jr eng + 4 interns) · CTO-level roadmap partnership |
| 3 | Google | Software Engineering Manager, Applied AI Industry Verticals | 78 | India | LLM applications · prompt engineering · RAG pipelines · autonomous agent architectures · MCP/open protocols integration · A2UI / AI-native front-ends · ML infra ownership (deployment, eval, fine-tuning) · highly reliable prod systems w/ eval frameworks |
| 4 | Unilever | GDT Data Solution Architect | 78 | India | Data platforms · BI · data lakes · data warehousing · analytics products with P&L impact · data democratization/governance · cross-functional architecture leadership |
| 5 | Epicor Software | AI Enablement Architect, Senior | 78 | India | Reusable AI reference architectures · responsible-AI governance · open-source LLM guidance · evaluation + monitoring + observability · cost awareness/tracking · integration patterns · enablement/workshops · success metrics for AI initiatives |
| 6 | ZF | Technical Lead — AI/ML, Generative AI & Agentic AI | 78 | India | Python production deployments · Azure ML · Databricks · GenAI frameworks · agentic AI hands-on · data pipelines (structured + unstructured/embeddings) · Agile delivery · Azure/Databricks certifications |
| 7 | Intuit | Staff Software Engineer (Foresight) | 78 | India | AI-native/fullstack LLM apps · common frameworks/components/models · ML pipelines E2E · Python · PyTorch · NumPy/Pandas/TensorFlow · supervised/unsupervised/RL fundamentals · precision/recall on prod models + PoC leadership |
| 8 | Intuit | Senior Software Engineer (Foresight) | 78 | India | Same core set as Staff role minus lead-years: Python · PyTorch · NumPy/Pandas · TensorFlow · ML fundamentals incl. RL · production-grade models · rapid prototyping |
| 9 | Microsoft | Senior Applied Scientist (Teams D&AS) | 78 | India | Recommender systems · GenAI applications · LLM evaluation · NLP · information retrieval · mining massive datasets · A/B experiments + quality metrics · scalable distributed code + MLOps |
| 10 | Citi | Senior Gen AI Engineer — Vice President | 78 | India | GenAI engineering leadership in a banking environment (snippet truncated before detail list; expect RAG/agentic + governance) |
| 11 | Microsoft | ML — Principal Software Engineer | 78 | India | AI-on-Windows product ML engineering (snippet truncated early) |
| 12 | D. E. Shaw | Principal, Tech (GAITech "Strike") | 78 | India | Generative AI infrastructure & applications · firm-scale GAI platform building (snippet truncated early) |
| 13 | SAP | AI Architect | 78 | Dubai | AI-native enterprise architecture · integration layers + event-driven systems · model integration: batch + real-time inference · feature/data pipelines · vector search · LLM orchestration · agent frameworks · evaluation services + responsible-AI controls |
| 14 | Siemens Energy | Senior AI / GenAI Expert with Leadership | 78 | India | Grounding assistants in enterprise knowledge · prompt iteration · failure-case inspection + eval-set sharpening · retrieval design reviews · agent orchestration reviews · guardrails aligned with security/data-privacy · business→AI translation · mentoring |
| 15 | (unnamed) | Generative and Agentic AI Engineer | 78 | India | RAG end-to-end (ingest/chunk/embed/index/rerank/eval) · multi-tool/multi-agent architectures · function calling · caching/retry/token-cost controls · fine-tuning, LoRA/adapters, distillation · FAISS + Pinecone · LangChain + LlamaIndex · streaming + guardrails + monitoring · AWS + Azure deployment |
| 16 | Amazon | Sr SDE, Selection Monitoring | 78 | India | Large-scale distributed systems · IR systems (web mining → structured entities from unstructured data) · parallel processing · AI/GenAI/ML/DL applied at catalog scale · big data · SOA · end-to-end design-to-deploy ownership |
| 17 | Optum | VP AI ML Engineering | 78 | India | Enterprise AI strategy/architecture · reusable AI platforms · governance + responsible AI · org building/leadership · adoption & measurable business value |

Duplicate queue entries collapsed: Siemens Brightly ×2 (jobspy_c7171a5d7cb395, jobspy_02537eecb869ce), Unilever ×3 (jobspy_120af56c2cb113, jobspy_a3c0503c1793ca, jobspy_3db677c3c1f0ba).

---

## 2. Skill demand frequency across all JDs

Count = **unique roles** demanding the skill (of 17). Several LinkedIn snippets are truncated mid-detail; counts marked "+" are conservative floors.

| Skill / theme | # JDs | Which roles |
|---|---|---|
| Agentic AI / autonomous & multi-agent systems | 7 | Siemens, Regilient, Google, ZF, nan-JD, SAP, Siemens Energy (+ thin: DES, MS-Principal) |
| Responsible AI / guardrails / safety governance | 7 | Siemens, Epicor, nan-JD, SAP, Siemens Energy, Optum, Regilient |
| People/tech leadership (lead, mentor, own standards) | 6 | Google, Optum, Regilient, Citi, Siemens Energy, Epicor |
| Evaluation harnesses / LLM evals / quality gates | 6 | Siemens, MS-Teams, Epicor, nan-JD, SAP, Siemens Energy |
| Python (production services) | 5 | ZF, Intuit×2, nan-JD, Amazon |
| RAG / retrieval-grounded applications | 4+ | Siemens, Google, nan-JD, Siemens Energy (+ likely Citi, SAP) |
| MLOps: CI/CD for models, registries, lineage, gates | 4 | Siemens, Epicor, MS-Teams ("ML operations"), Optum |
| Observability (OTel/CloudWatch/monitoring) | 4 | Siemens, Epicor, nan-JD, MS-Teams |
| Vector search / embeddings infra | 4 | nan-JD (FAISS, Pinecone), SAP, Siemens, Siemens Energy |
| Governance/compliance framing of AI | 5 | Optum, Epicor, Citi, Regilient, SAP |
| AWS platform | 4+ | Siemens ×1 role, nan-JD, Amazon (native), Google (implied) |
| Distributed systems at scale | 3+ | Amazon, MS-Teams, DES |
| IR / web-scale extraction of structured data | 3 | Amazon, MS-Teams, Siemens (search/recs) |
| ML fundamentals (sup/unsup/RL) + PyTorch/TF stack | 3 | Intuit×2, MS-Teams |
| Feature engineering / data pipelines | 3 | Siemens, SAP, ZF |
| Fine-tuning LoRA/QLoRA / distillation | 3 | Siemens, Google, nan-JD |
| EDA / data-quality discipline | 3 | Siemens, ZF, Unilever |
| Cost control / token optimization / caching-retries | 3+ | Siemens, Epicor, nan-JD |
| A/B testing / experimentation | 2+ | Siemens, MS-Teams (+ Intuit culture) |
| Recommender systems | 2 | MS-Teams, Siemens (recommendations domain) |
| Kubernetes / EKS / ECS | 2 | Siemens, Amazon |
| Azure stack | 2+ | ZF, nan-JD (+ probable at Citi/Unilever) |
| Databricks | 1+ | ZF (+ likely Unilever/Citi in truncated text) |
| LangChain / GenAI frameworks | 2+ | nan-JD (LangChain, LlamaIndex), ZF |
| Kafka / MSK / streaming | 1+ | Siemens (MSK); workflow/event-driven adds SAP, nan-JD |
| Step Functions / workflow orchestration | 3 | Siemens, nan-JD, SAP (event-driven) |
| SageMaker + Bedrock | 1+ | Siemens (explicit pair) |
| Open-source LLM hosting | 2 | Epicor, nan-JD (HF ecosystem) |
| MCP / open agent protocols | 1 | Google |
| A2UI / AI-native front-ends | 1 | Google |
| BI / lakes / warehousing platforms | 1 | Unilever |
| Streaming responses | 1 | nan-JD |
| Batch + real-time inference patterns | 1 | SAP |
| Multimodal / vision models | 1+ | Google (+ MS-Principal truncated) |

Takeaway: the market is converging on **agentic + RAG + evals + guardrails + cost/observability + MLOps governance** — which is exactly T06/T07/T08/T09's center of mass. The scarce-in-curriculum items are niche tools (Kedro, Trino, LlamaIndex, Pinecone-as-product) and depth areas (Azure ML, BI tooling, web-scale extraction).

---

## 3. Coverage matrix

Legend: COVERED = module(s) in curriculum cover it · PARTIAL = present but thin (thinness described) · MISSING = nothing in curriculum or clouds files.

### 3a. Every skill line from the resume

| Skill (resume line) | Status | Evidence / gap note |
|---|---|---|
| Python | COVERED | T01-data-model, T01-typing, T01-asyncio, T01-gil-parallelism, T01-memory-oom, T01-tooling, T01-testing, T01-profiling, T01-iterators-generators, T01-decorators, T01-scoping-closures, T01-copy-semantics, T01-pandas-mastery, T11-fastapi-deep |
| Java | COVERED | T11-java-modern, T11-jvm-tuning, T11-spring-boot, T11-resilience4j, T11-quarkus |
| SQL | COVERED | T17-sql-mastery, T17-normalization, T18-bigquery |
| Scala | MISSING | Not in any curriculum/cloud title. Only demanded indirectly (big-data shops); low priority. |
| Solidity | COVERED | T22-smart-contracts, T22-contract-security |
| Agentic AI | COVERED | Entire T07 track (30 modules): T07-agent-loop-from-scratch … T07-agent-zero-to-prod |
| A2A (Agent-to-Agent) | COVERED | T07-a2a-protocol |
| RAG | COVERED | T06 track (18 modules): T06-chunking … T06-text-preprocessing; plus T10-genai-designs |
| FastMCP / MCP | COVERED | T07-mcp-deep-dive, T28-mcp-authoring |
| Prompt Engineering | COVERED | T07-prompting-techniques, T07-prompt-versioning, T07-context-engineering |
| Fine-tuning (PEFT) | COVERED | T05-finetuning (LoRA/QLoRA/DoRA + decision tree), T05-alignment, T09-huggingface-ecosystem (PEFT lib) — *hands-on run still pending, see §4* |
| vLLM | COVERED | T05-inference-serving (KV cache math, PagedAttention, continuous batching, vLLM/SGLang) |
| Amazon Bedrock | COVERED | C-AWS-ai-ml, T09-bedrock-vs-sagemaker |
| AWS SageMaker | COVERED | C-AWS-ai-ml, T09-serving, T09-bedrock-vs-sagemaker (SageMaker *Pipelines* tracked separately below) |
| Phi-4 / LLaMA-3 / GPT-4 / Mistral (model families) | COVERED | T26-frontier-landscape (model families, model cards), T05-quantization (open-weight serving economics) |
| BERT / T5 | COVERED | T05-bert-encoders, T05-transfer-distillation |
| LangChain | COVERED | T09-huggingface-ecosystem, T07-framework-matrix |
| LangGraph | COVERED | T07-langgraph-core, T07-langgraph-durable, T07-react-agent-internals |
| ReAct Agents | COVERED | T07-react-pattern-raw, T07-react-agent-internals |
| Google ADK | COVERED | T07-framework-matrix (LangGraph vs ADK vs OpenAI SDK vs CrewAI vs AutoGen), C-GCP-ai (Agent Builder/ADK) |
| RAGAS | COVERED | T08-ragas-deepeval, T06-rag-eval |
| DeepEval | COVERED | T08-ragas-deepeval |
| Reinforcement Learning (CMAB) | COVERED | T03-bandits (ε-greedy…CMAB, "your PySpark bullet"), full T31 track, T31-rl-for-llms |
| Recommendation systems (CF/content/hybrid) | COVERED | T03-recsys, T10-ml-designs, T32-personalization |
| Scikit-learn | COVERED | T03-linear-models, T03-trees-boosting, T03-classic-models — from-scratch derivations exceed sklearn usage |
| PyTorch | COVERED | T04-autograd, T04-architectures, T04-training-engineering, T04-distributed-training, T05-build-nanogpt |
| TensorFlow | COVERED | T04-tensorflow |
| XGBoost | COVERED | T03-trees-boosting (XGBoost/LightGBM/CatBoost internals) |
| Sentence-Transformers / MiniLM | COVERED | T06-embeddings-choice, T05-embeddings-training |
| BGE-Reranker-Large | COVERED | T06-reranking (cross-encoder economics, BGE tuning) |
| Amazon Titan Embed v2 | COVERED | T06-embeddings-choice (managed embedding dimensions/cost/multilingual selection) |
| FAISS | COVERED | T17-vector-db-compare |
| Whisper | COVERED | T05-multimodal, T26-voice-models, T26-speech-processing |
| NER | COVERED | T32-ner |
| Text Classification | COVERED | T32-text-classification |
| Embeddings (general) | COVERED | T06-embeddings-choice, T05-embeddings-training |
| Weaviate | COVERED | T17-vector-db-compare |
| ClickHouse | COVERED | T17-clickhouse |
| PostgreSQL (+pgvector) | COVERED | T17-postgres |
| MongoDB | COVERED | T17-mongodb |
| Redis | COVERED | T17-redis |
| Apache Spark (PySpark) | COVERED | T18-pyspark-scratch, T18-pyspark-advanced, T18-spark-streaming, T09-spark |
| Trino | MISSING | No Trino/Presto anywhere in curriculum or clouds. Resume-headline tech (Query Crafter) with zero curriculum backing — HM-grill risk. |
| BigQuery | COVERED | T18-bigquery (+40 SQL questions) |
| Apache Airflow | COVERED | T18-airflow, T09-orchestration |
| Elasticsearch | COVERED | T17-elasticsearch (OpenSearch kin covered in C-AWS-data-analytics) |
| ArangoDB | COVERED | T17-knowledge-graphs (ArangoDB vs Neptune vs Neo4j) |
| Kubernetes (EKS) | COVERED | T12-k8s-objects, T12-k8s-core, T12-k8s-networking, T12-k8s-storage-config, T12-k8s-scaling, T12-k8s-troubleshooting, T12-k8s-production, T12-eks-ecs-ecr, C-AWS-compute |
| Docker | COVERED | T12-docker, T27-docker-essentials, T27-docker-mastery, T27-docker-compose, T27-docker-debug, T16-containers-low-level |
| AWS: S3, EC2, Lambda, ECR, EMR, SSM, Secrets Manager | COVERED | C-AWS-storage, C-AWS-compute, C-AWS-lambda, T18-emr, T12-ssm-config, T12-secrets, T12-artifact-registries |
| GCP Vertex AI | COVERED | C-GCP-ai, T09-serving |
| Azure ML | PARTIAL | C-AZ-ai surveys Foundry/Azure OpenAI/AI Search/ML Studio in 2.5h — no workspace/pipeline/endpoint/registry depth, no cert-style drills (ZF explicitly values certs) |
| FastAPI | COVERED | T11-fastapi-deep, T11-fastapi-to-go |
| Jenkins | COVERED | T12-jenkins |
| Bitbucket CI/CD | PARTIAL | CI/CD concepts fully covered (T12-cicd GitHub Actions/ArgoCD, T12-jenkins) but Bitbucket Pipelines YAML specifically absent |

### 3b. Every distinct technology named in any JD snippet

| JD-named skill | Status | Evidence / gap note |
|---|---|---|
| MCP / open protocols (Google) | COVERED | T07-mcp-deep-dive, T28-mcp-authoring |
| A2UI / AI-native front-ends (Google) | PARTIAL | T33-streaming-ai-ui + T11-react cover streaming agent UIs; A2UI spec vocabulary & agentic-UX patterns beyond chat absent |
| Multimodal / Large Vision Models (Google) | COVERED | T05-multimodal, T04-computer-vision, T26-imagebind-multimodal |
| Guardrails (Guardrails AI, NeMo) (Siemens, nan-JD) | COVERED | T07-guardrails (Guardrails AI, NeMo, PII, toxicity), T07-agent-safety |
| Eval harnesses (Siemens, MS, Epicor…) | COVERED | T08-eval-harness, T07-agent-testing, T07-harness-engineering, T19-llm-testing |
| Latency/cost/quality instrumentation (Siemens) | COVERED | T06-latency-accuracy, T07-agent-cost-routing, T08-otel-genai |
| EKS / ECS / Lambda (Siemens) | COVERED | T12-eks-ecs-ecr, C-AWS-compute, C-AWS-lambda |
| MSK / Kafka semantics (Siemens) | COVERED | T10-messaging, C-AWS-data-analytics |
| Step Functions (Siemens) | COVERED | C-AWS-integration, T18-scheduling-triggering |
| CloudWatch / OpenTelemetry (Siemens) | COVERED | C-AWS-observability-cost, T08-otel-genai, T08-classic-obs |
| MLflow / W&B (Siemens) | COVERED | T09-tracking-registry |
| Kedro (Siemens) | MISSING | Named verbatim in the top-scored JD; nearest neighbors T09-orchestration (Airflow/Dagster/Prefect) don't mention it |
| SageMaker Pipelines (Siemens) | PARTIAL | Registry + model CI/CD concepts solid (T09-tracking-registry, T09-model-cicd); SM Pipelines primitives (Processing/Training/Tuning steps, properties, callback token) not drilled |
| Data & prompt lineage (Siemens) | COVERED | T18-data-quality (lineage SLAs), T07-prompt-versioning (prompt lineage/registries) |
| Responsible-AI controls (SAP, Optum, Epicor…) | COVERED | T07-agent-safety, T07-human-oversight, T07-trust-calibration, T07-explainability |
| EDA (Siemens) | COVERED | T03-eda, T03-missing-data, T03-statistics-inference |
| Feature engineering (Siemens, SAP, ZF) | COVERED | T03-feature-eng, T03-feature-selection, T09-feature-stores |
| A/B testing (Siemens, MS-Teams) | COVERED | T25-experimentation, T32-experiment-design |
| Azure ML (ZF) | PARTIAL | See 3a — survey-depth only |
| Databricks (ZF) | COVERED | T18-databricks (Delta, Unity Catalog, Photon, DLT, Workflows), C-AZ-data |
| Data lakes / warehousing (Unilever) | COVERED | T18-lakehouse, T18-data-modeling-e2e, T17-dimensional-modeling, T17-oltp-vs-olap |
| BI tooling (Unilever) | PARTIAL | Looker appears once (C-GCP-data); no Power BI/Tableau/semantic-layer hands-on |
| Open-source LLM models guidance (Epicor) | COVERED | T05-inference-serving, T05-quantization (GGUF/GPTQ/AWQ), T09-bedrock-vs-sagemaker |
| NumPy (Intuit) | PARTIAL | No dedicated module; fluency assumed inside T04-autograd tensor engine + T01-pandas-mastery |
| Pandas (Intuit) | COVERED | T01-pandas-mastery |
| TensorFlow (Intuit) | COVERED | T04-tensorflow |
| Sup/unsup/RL fundamentals (Intuit, MS) | COVERED | T03 track, T04-neural-net-math, T31 track |
| Precision/recall on prod models (Intuit) | COVERED | T03-metrics-calibration |
| Recommender systems (MS-Teams, Siemens) | COVERED | T03-recsys, T10-ml-designs |
| LLM evaluation (MS-Teams) | COVERED | T08-eval-harness, T08-llm-as-judge, T08-ragas-deepeval, T08-agent-eval |
| Information retrieval (MS-Teams, Amazon) | COVERED | T06-semantic-search, T06-hybrid-search, T06-accuracy-tuning (recall@k→MRR→nDCG) |
| Web mining / entity extraction at scale (Amazon) | PARTIAL | T06-data-structuring + T32-ner cover document parsing/extraction; crawling + extraction pipeline at catalog scale (100M sources) absent |
| Large-scale distributed systems (Amazon, DES) | COVERED | T10-distributed-fundamentals, T10-consensus-ordering, T16-io-models |
| Parallel processing (Amazon) | COVERED | T01-gil-parallelism, T18-pyspark-* |
| Vector search (SAP) | COVERED | T06-vector-index-internals (HNSW/IVF-PQ/ScaNN/DiskANN), T17-vector-db-compare |
| LLM orchestration / agent frameworks (SAP) | COVERED | T07-framework-matrix, T07-langgraph-core/durable |
| Event-driven systems (SAP) | COVERED | T21-outbox-saga-cqrs, C-AWS-integration, T18-scheduling-triggering |
| Batch + real-time inference (SAP) | COVERED | T09-serving, T05-inference-serving, T18-spark-streaming |
| Function calling / tool usage (nan-JD) | COVERED | T07-tool-engineering |
| Caching / retries / token optimization (nan-JD) | COVERED | T06-semantic-caching, T21-resilience-catalogue, T21-resilience-advanced, T07-agent-cost-routing |
| Multi-agent architectures (nan-JD, Regilient) | COVERED | T07-multi-agent-topologies, T07-agent-zero-to-prod |
| Model distillation (nan-JD) | COVERED | T05-transfer-distillation, T04-export-optimize |
| Streaming responses (nan-JD) | COVERED | T33-streaming-ai-ui (SSE vs WebSocket, token streaming), T07-production-agent-loops |
| FAISS (nan-JD) | COVERED | T17-vector-db-compare |
| Pinecone (nan-JD) | PARTIAL | Category covered in T17-vector-db-compare; Pinecone serverless mechanics/namespaces not |
| LlamaIndex (nan-JD) | MISSING | Never named in curriculum/clouds |
| Hugging Face ecosystem / Transformers (nan-JD) | COVERED | T09-huggingface-ecosystem, T05 track |
| Grounded assistants / failure-case review / eval sets (Siemens Energy) | COVERED | T07-attribution, T07-hallucination, T06-accuracy-tuning, T08-eval-harness |
| Cross-industry AI governance/compliance (Optum, Epicor, Citi, Regilient) | PARTIAL | Banking MRM strong (T24-basel, T24-mrm, T24-risk-metrics); EU AI Act / ISO 42001 / regulatory-intelligence workflows absent |
| Enterprise AI strategy & reusable platforms (Optum) | COVERED | T10-principal-layer, T25-strategy, T25-unit-economics, T14-principal-competencies |
| People/team leadership (Google, Optum, Regilient…) | COVERED | T14-star-bank, T14-principal-competencies, T14-company-specific — flagged for deepening in §4 |
| Agile/Scrum (ZF) | MISSING | No curriculum home; soft-skill, near-zero standalone interview weight → no-action |

### Counts

| Metric | Count |
|---|---|
| Skills checked (resume lines + distinct JD technologies) | **100** |
| COVERED | **86** |
| PARTIAL | **9** (Azure ML · Bitbucket CI/CD · A2UI · SageMaker Pipelines · BI tooling · NumPy · web-mining/entity-extraction · Pinecone · cross-industry AI governance) |
| MISSING | **5** (Scala · Trino · Kedro · LlamaIndex · Agile/Scrum) |

Verification method: every status above was checked against `curriculum.json` titles/slugs AND `curriculum/**/*.md` + `clouds/**/*.md` filenames; cloud-service claims cross-checked against `clouds/aws/*.md`, `clouds/azure/*.md`, `clouds/gcp/*.md`.

---

## 4. Top 10 highest-leverage gaps

Ranked by (JD demand × interview weight − existing coverage).

| # | Gap | Why it scores high | Recommended action |
|---|-----|--------------------|--------------------|
| 1 | **Fine-tuning lifecycle as a hands-on story** (LoRA/QLoRA → eval gate → registry → deploy) | Demanded by the top-scored JD (Siemens, 88), plus Google + nan-JD; senior-MLE differentiator; curriculum is concept-complete (T05-finetuning) but you have no rehearsed run to narrate | **deepen-existing(T05-finetuning) + hands-on-lab**: run one QLoRA job on a small open model, push adapter to a registry, wire an eval gate; narrate against your real vLLM/Bedrock experience |
| 2 | **Model CI/CD orchestration tooling — SageMaker Pipelines + Kedro** | Siemens names both verbatim; Epicor/Optum want governance-grade pipelines; coverage partial (T09-orchestration lacks Kedro; SM Pipelines undrilled) — Kedro is one of only two JD-named MISSING tools that matter | **deepen-existing(T09-orchestration) + hands-on-lab**: add a Kedro repo skeleton + one SageMaker Pipelines DAG (Processing→Training→Eval→Condition step→Registry); map onto T09-model-cicd gates |
| 3 | **LLM latency/cost/quality instrumentation war story** | Asked for verbatim by Siemens ("instrument for latency, cost, and quality") and Epicor ("track AI usage, cost"); theory covered (T08-otel-genai, T07-agent-cost-routing) but no produced artifact | **hands-on-lab**: extend the OTel lab into a live dashboard (tokens/cost/latency p95 per span) + one slide-ready screenshot with numbers |
| 4 | **Azure ML working depth (+ cert posture)** | Hard requirement at ZF, probable at Unilever/Citi, second-cloud at nan-JD; current coverage is survey-only (C-AZ-ai) while AWS-side is deep — an asymmetry interviewers will poke | **deepen-existing(C-AZ-ai)**: add workspace/compute/pipeline/endpoints + Azure OpenAI PTU-vs-paygo cost drill; optionally one AZ-102-style practice test |
| 5 | **Trino refresh** | Zero curriculum coverage of a resume-headline technology (Query Crafter: "RAG + GPT-4 + Trino"); guaranteed probing in any HM grill (T15-round-hm) even though JD demand is indirect (Unilever data-federation flavor) | **cheat-sheet-only**: 1-page connector/federation/gotchas sheet + 10 mock Q&A logged against T15-round-hm |
| 6 | **Cross-industry AI governance pack (EU AI Act, ISO 42001, audit trails, declaration workflows)** | 5 JDs frame AI through governance/responsible-AI (Citi VP, Optum VP, Regilient regulatory-compliance platform, Epicor architect, SAP); banking MRM (T24-basel/T24-mrm) covers only the finance slice | **deepen-existing(T24-mrm) + cheat-sheet-only**: add EU AI Act risk-tier mapping + ISO 42001 skeleton; rehearse translating guardrail work into compliance language |
| 7 | **Web-scale IR / entity-extraction mini-pipeline** | Amazon loop (IR systems mining unstructured web data) + MS-Teams IR + Siemens search; document extraction covered (T06-data-structuring, T32-ner) but scale-story missing | **hands-on-lab**: crawl(ish) → extract → dedupe → index 100k docs; report recall/precision + throughput; pairs with T02-graph-applied |
| 8 | **A2UI / agentic-UX vocabulary** | Explicit preferred qual at Google; you already hold the substance (A2A/FastMCP + T33-streaming-ai-ui) but lack the term-mapping, and Google panels reward speaking their protocol language | **cheat-sheet-only**: 1 page mapping T33-streaming-ai-ui + T28-subagent-architecture + T07-human-oversight onto A2UI generative-UI concepts |
| 9 | **LlamaIndex + Pinecone parity pass** | Named together in nan-JD; category knowledge exists (T17-vector-db-compare, T06 labs) so a module would be over-investment — but a fumbled "have you used LlamaIndex?" costs points in Indian GenAI screens | **cheat-sheet-only**: after finishing T06 chunking/retrieval labs, do a 2-hour port of one retrieval lab to LlamaIndex + Pinecone; note deltas only |
| 10 | **People-leadership STAR expansion for manager/VP loops** | 6 of 17 JDs are leadership-weighted (Google SEM wants people-management years; Optum is a VP org-build; Regilient is a founding lead of 5); T14-star-bank is IC-flavored today | **deepen-existing(T14-star-bank)**: add 6 stories (hiring, underperformance, intern coaching, standard-setting, stakeholder conflict, roadmap tradeoff); rehearse inside T15-round-behavioral |

Explicit no-actions (covered well enough, do NOT invest): RAG depth, agentic frameworks, vector indexes, Kafka/MSK, Docker/K8s/EKS, Terraform/GitHub Actions/Jenkins, MLflow/W&B, Airflow, Spark/EMR, Databricks, Snowflake/Redshift/BigQuery, DynamoDB/Cassandra, Neo4j/knowledge graphs, prompt injection/OWASP LLM, LangSmith/Langfuse/Phoenix, vLLM, DeepSpeed/PEFT, GGUF/quantization, Whisper/voice stack, MCP/A2A.

---

## 5. JD-specific prep notes — top-2 scored roles (both 88)

### 5a. Siemens Brightly — Senior Machine Learning Engineer (jobspy_c7171a5d7cb395)

What the wording signals their loop will probe:
1. **"RAG pipelines, prompt orchestration, tools/agents, safety/guardrails, evaluation harnesses"** — expect a whiteboard: "design the copilot/search for asset-management data." They will push on eval gates and what you instrument. Your Cornerstone multi-tier skill-resolution + reranking story maps directly.
2. **"Own the ML lifecycle … training/fine-tuning (LoRA/QLoRA)"** — they will ask for an actual FT decision you made: why FT vs RAG vs better prompting, dataset curation, how you validated. Gap #1 above exists precisely here.
3. **"Productionize on AWS: EKS/ECS/Lambda, SageMaker, Bedrock, EMR, MSK, Step Functions … CloudWatch/OpenTelemetry, cost controls"** — service-selection drills ("Bedrock vs self-hosted?" is literally your resume: Bedrock batch inference + self-hosted vLLM on SageMaker). Expect an MSK/Step Functions orchestration question since it's named.
4. **"CI/CD for models (MLflow/Kedro/SageMaker Pipelines), registries, lineage, evaluation gates, responsible-AI"** — governance round: draw the promotion path prompt→model→prod with rollback. Kedro/SM-Pipelines are your thinnest named tools (Gap #2).
5. **"EDA on structured, semi-structured, unstructured"** — warm-up screen on data-quality instincts; T03-eda + T03-missing-data suffice.
6. **Brightly context = asset management (buildings/infrastructure SaaS)** — prepare the "translate asset-management use case into ML solution" product question (T25-product-thinking + T25-ai-product angle).

Rehearsal order (modules/labs):
1. `T10-resume-systems` — reframe 4 flagship systems toward asset-management analogues (work orders, IoT telemetry, maintenance docs).
2. `T06-rag-production` → `T06-latency-accuracy` → `T06-semantic-caching` — the copilot/search core.
3. `T07-agent-zero-to-prod` → `T07-production-agent-loops` → `T07-agent-cost-routing` — workflow automation + cost story.
4. `T09-bedrock-vs-sagemaker` → `T09-serving` — your strongest authentic material; rehearse aloud.
5. `T08-otel-genai` → `T08-classic-obs` → `T09-model-monitoring` — the instrumentation answer (feed from Gap #3 lab).
6. `T09-tracking-registry` → `T09-model-cicd` → `T18-scheduling-triggering` — MLOps governance round incl. Step Functions.
7. `T05-finetuning` + Gap #1 lab — the LoRA/QLoRA narrative.
8. Boss rounds: `T15-round-genai` → `T15-round-design` → `T15-round-hm` (they will grill the 8-service platform commit history).
9. Behavioral: `T14-star-bank` (partner-across-Brightly stories), `T14-design-communication`.

### 5b. Regilient — Senior AI Lead Engineer (linkedin_4444361265)

What the wording signals their loop will probe:
1. **"Agentic regulatory compliance platform … autonomously monitors regulations, engages suppliers, processes compliance data, generates declarations without manual intervention"** — this is T07-agent-zero-to-prod as a literal job spec. Expect: "architect the ingestion→extraction→generation agent system." Long-document handling (regulations) pushes context engineering + memory.
2. **"Without manual intervention"** — the trust question: how do you prevent wrong declarations shipping? They want guardrails, confidence/abstention (`T07-trust-calibration`), HITL escape hatches (`T07-human-oversight`) — and the judgment to know when autonomy is unsafe (`T07-multi-agent-topologies` "and When NOT To").
3. **"Set the architecture, standards, and culture … founding AI role"** — principal-level: how you'd run evals in CI, golden baselines (your 2,000-row regression baseline story!), prompt versioning, injection resistance. `T07-agent-testing`, `T19-llm-testing`, `T07-harness-evals`.
4. **"Lead 1 junior engineer + 4 interns, work with CTO on roadmap"** — mentoring + delegation stories; expect "how do you review an intern's agent code" (`T27-reviewing-ai-code`, `T13-code-review`) and roadmap-prioritization talk with a startup budget lens (`T25-unit-economics`, `T07-agent-cost-routing`).
5. **Compliance domain** — regulatory change monitoring implies retrieval over legal text + freshness; lean on `T06-chunking` (long structured docs), `T06-metadata-design` (jurisdiction/version metadata), and Gap #6 governance pack (EU AI Act adjacent).
6. **Model choice at startup scale** — open-weight vs API cost/quality tradeoffs (`T09-bedrock-vs-sagemaker`, `T05-quantization`): they'll care about unit cost per declaration.

Rehearsal order (modules/labs):
1. `T07-agent-zero-to-prod` — rebuild the capstone verbally as "RegulationWatch": monitors → extractors → supplier-engagement agents → declaration generator.
2. `T07-context-engineering` → `T07-agent-memory` — 200-page regulation docs, jurisdiction-scoped memory.
3. `T07-risk-taxonomy` → `T07-agent-safety` → `T07-guardrails` — permission tiers for autonomous supplier outreach; PII/toxicity walls.
4. `T07-trust-calibration` → `T07-human-oversight` — abstention thresholds before a declaration ships.
5. `T07-agent-testing` → `T19-llm-testing` → `T07-harness-evals` — CI gates + golden trajectories; cite your Cornerstone regression-baseline numbers.
6. `T07-multi-agent-topologies` — defend supervisor-vs-pipeline choice; name when you'd NOT use agents.
7. `T25-unit-economics` → `T07-agent-cost-routing` — cost-per-declaration model, routing small→large models.
8. `T14-principal-competencies` → `T14-star-bank` (leadership additions from Gap #10) → `T27-reviewing-ai-code`.
9. Capstone boss: `T15-round-full-loop` with this JD substituted as the design prompt.
