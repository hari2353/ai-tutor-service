#!/usr/bin/env python3
"""Build app/data/*.json from the compact curriculum spec.

Run:  python app/build_data.py
Used by the /tutor-add skill to regenerate the app index after new content lands.
Zero dependencies. Python 3.9+.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"

# ---------------------------------------------------------------------------
# SPEC: track -> (id, title, icon, hours, phase, prereqs, [modules])
# A module is "slug | Title | hours | tags"
# Phase A = interview sprint (weeks 1-8). Phase B = mastery (weeks 9-26).
# ---------------------------------------------------------------------------
TRACKS = [
    dict(id="T07", dir="07-agentic-ai", title="Agentic AI", icon="🤖", phase="A", prereqs=[], modules=[
        "agent-loop-from-scratch | The Agent Loop From Scratch (no framework) | 3 | core,loop",
        "react-pattern-raw | ReAct Implemented Raw + Plan-Execute + Reflexion | 2.5 | core,reasoning",
        "tool-engineering | Tool Engineering: Schemas, Errors, Idempotency, Sandboxing | 2.5 | core,tools",
        "mcp-deep-dive | MCP Deep Dive + FastMCP Server & Client From Scratch | 3 | protocol,mcp",
        "a2a-protocol | A2A Protocol: Agent Cards, Task Lifecycle, vs MCP | 1.5 | protocol",
        "langgraph-core | LangGraph I: StateGraph, Reducers, Conditional Edges, Send | 3 | framework,langgraph",
        "langgraph-durable | LangGraph II: Checkpointers, interrupt()/HITL, Durable Resume | 3 | framework,langgraph",
        "react-agent-internals | create_react_agent Internals, Line by Line | 1.5 | framework,langgraph",
        "framework-matrix | Framework Matrix: LangGraph vs ADK vs OpenAI SDK vs CrewAI vs AutoGen | 2 | framework,tradeoffs",
        "agent-memory | Agent Memory: Working, Episodic, Semantic, Procedural | 3 | memory",
        "context-engineering | Context Engineering: Budgets, Compaction, Context Editing, Subagents | 3 | memory,context",
        "multi-agent-topologies | Multi-Agent Topologies (and When NOT To) | 2.5 | architecture",
        "production-agent-loops | Production Loops: Budgets, Resume, Kill Switches, Streaming | 3 | production",
        "agent-safety | Prompt Injection, OWASP LLM Top 10, Tool Permissions, Guardrails | 2.5 | security",
        "agent-cost-routing | Prompt Caching, Model Routing, Fallback Chains, Cost Governance | 1.5 | production,cost",
        "structured-output | Structured Output: JSON Schema, Constrained Decoding, Repair Loops | 2 | production,critical",
        "prompting-techniques | Zero-Shot, Few-Shot, CoT, Self-Consistency: What Actually Moves Accuracy | 2 | prompting,critical",
        "prompt-versioning | Prompt Versioning, Registries, A/B Rollout, Auto-Revert on Regression | 2 | production,critical",
        "guardrails | Guardrails In/Out: Guardrails AI, NeMo, Validation Layers, PII, Toxicity | 2.5 | security,critical",
        "explainability | Explainability & Attribution: Citations, Traces, SHAP/LIME, Model Cards | 2 | trust,critical",
        "trust-calibration | Trust Calibration: Confidence, Abstention, Saying I Don't Know | 2.5 | trust,critical",
        "attribution | Attribution & Grounding: Citations That Hold Up, Faithfulness vs Plausibility | 2.5 | trust,critical",
        "hallucination | Hallucination: Taxonomy, Detection, and What Actually Reduces It | 2.5 | trust,critical",
        "human-oversight | Human Oversight Design: Approval Gates, Escalation, Accountability | 2 | trust,critical",
        "agent-testing | Testing Agents: Unit, Integration, Regression, Golden Trajectories, CI Gates | 3 | testing,critical",
        "harness-engineering | Harness Engineering: The 15-Component Model, Everything Except the Model | 3.5 | harness,critical",
        "loop-engineering | Loop Engineering: The Canonical Loop, Budgets, Compaction Triggers, Stop Conditions | 3 | harness,critical",
        "risk-taxonomy | Risk Taxonomy & Permission Resolution: read_only → financial → destructive | 2.5 | harness,critical",
        "harness-evals | Evaluating the Harness Itself: Injection Resistance, Timeouts, Over-Tooling | 2.5 | harness,critical",
        "agent-zero-to-prod | Zero → Production: The Complete Multi-Agent System, End to End | 4 | capstone,critical",
    ]),
    dict(id="T21", dir="21-architecture-principles", title="Architecture & Design Principles", icon="🏛️", phase="A", prereqs=[], modules=[
        "solid | SOLID: Violations, Refactors, and the Counter-Arguments | 2 | principles",
        "grasp-dry-kiss | GRASP, DRY/KISS/YAGNI, Demeter, Composition over Inheritance | 1 | principles",
        "gof-creational | GoF Creational Patterns in Python/Java/Go | 1.5 | patterns",
        "gof-structural | GoF Structural Patterns in Python/Java/Go | 1.5 | patterns",
        "gof-behavioral | GoF Behavioral Patterns in Python/Java/Go | 2 | patterns",
        "resilience-catalogue | Resilience Catalogue: Timeout, Retry+Jitter, Circuit Breaker, Bulkhead | 3 | resilience,critical",
        "resilience-advanced | Load Shedding, Backpressure, Hedged Requests, Idempotency Keys, DLQ | 2 | resilience",
        "outbox-saga-cqrs | Outbox, Inbox, Saga, CQRS, Event Sourcing | 2 | patterns,distributed",
        "architecture-styles | Layered, Hexagonal, Onion, Clean, Modular Monolith, Microservices | 2 | architecture",
        "ddd | DDD: Aggregates, Bounded Contexts, Context Mapping, Event Storming | 2 | architecture",
        "anti-patterns | Anti-Patterns: Distributed Monolith, Dual Writes, Shared DB, God Object | 1 | architecture",
    ]),
    dict(id="T06", dir="06-rag", title="RAG", icon="📚", phase="A", prereqs=[], modules=[
        "chunking | Chunking: Fixed, Recursive, Semantic, Contextual, Late | 2 | ingest",
        "embeddings-choice | Embedding Models: Dimensions, Matryoshka, Multilingual, Cost | 1.5 | ingest",
        "vector-index-internals | Vector Index Internals: HNSW, IVF-PQ, ScaNN, DiskANN | 3 | retrieval,critical",
        "hybrid-search | Hybrid Search: BM25 + Dense, RRF, ColBERT Late Interaction | 2 | retrieval",
        "reranking | Rerankers: Cross-Encoder Economics, Cascades, BGE Tuning | 1.5 | retrieval",
        "query-transformation | HyDE, Multi-Query, Decomposition, Step-Back, Routing | 2 | retrieval",
        "advanced-rag | CRAG, Self-RAG, GraphRAG, Parent-Doc, Multi-Hop, Agentic RAG | 3 | advanced",
        "long-context-vs-rag | Long Context vs RAG, Lost in the Middle, Cost Curves | 1.5 | tradeoffs",
        "rag-production | Multi-Tenant, ACL-Aware Retrieval, PII, Zero-Downtime Reindex | 3 | production,critical",
        "rag-eval | RAGAS Decomposed, Golden Sets, Synthetic Questions, Retrieval@k | 2 | eval",
        "semantic-search | Semantic Search: Lexical → Vector → Hybrid → Learned Ranking | 2.5 | retrieval,critical",
        "multilingual | Multilingual Embeddings, Cross-Lingual Retrieval, 22-Locale Reality | 2 | retrieval,critical",
        "accuracy-tuning | Squeezing Accuracy: Recall@k → MRR → nDCG, Error Analysis Loop | 2.5 | eval,critical",
        "metadata-design | Metadata & Filtering: Schema Design, Pre vs Post Filter, Cardinality | 2 | ingest,critical",
        "latency-accuracy | The Latency/Accuracy/Cost Triangle: Where to Spend, What to Cut | 2 | tradeoffs,critical",
        "semantic-caching | Semantic Caching: Exact + Semantic + Prefix Layers, vCache, Hit-Rate Tuning | 2.5 | production,critical",
        "data-structuring | Structuring Source Data: Tables, Code, PDFs, Hierarchies, Knowledge Graphs | 2.5 | ingest",
        "text-preprocessing | Tokenization vs Stemming vs Lemmatization, Stopwords, Normalization, TF-IDF | 2 | ingest,critical",
    ]),
    dict(id="T10", dir="10-system-design", title="System Design", icon="🏗️", phase="A", prereqs=[], modules=[
        "distributed-fundamentals | CAP/PACELC, Consistency Models, Replication, Partitioning | 3 | fundamentals,critical",
        "consensus-ordering | Consensus (Raft), Leader Election, Lamport/Vector/HLC Clocks | 2 | fundamentals",
        "messaging | Kafka Semantics, Exactly-Once Illusions, CDC, Stream Processing | 2.5 | fundamentals",
        "caching-ratelimiting | Caching Layers, Invalidation, Rate Limiting Algorithms | 2 | fundamentals",
        "classic-designs | 25 Classic Designs (shortener → Google Docs) | 6 | practice",
        "ml-designs | 15 ML System Designs (feed ranking, ads CTR, fraud) | 4 | practice",
        "genai-designs | 20 GenAI/Agent Designs (RAG@10M, LLM gateway, agent platform) | 5 | practice,critical",
        "principal-layer | Multi-Tenancy, Cost Modeling, Migration Strategy, RFC Writing | 2 | principal",
        "resume-systems | Your 4 Flagship Systems as Formal Design Docs | 3 | principal,critical",
        "estimation | Back-of-Envelope: Guesstimates, Latency/Throughput/Storage Math, Sanity Checks | 2.5 | craft,critical",
        "diagramming | How to DRAW a System: C4 Model, Sequence, Dataflow, Deployment — Live on a Whiteboard | 2.5 | craft,critical",
        "design-method | Designing From Scratch: Requirements → Constraints → API → Data → Scale → Failure | 3 | craft,critical",
        "tech-selection | Choosing the Right System: Decision Frameworks, Scorecards, Reversible vs One-Way Doors | 2.5 | craft,critical",
        "poc-to-prod | POC → Prototype → MVP → Production: What Changes at Each Gate | 2.5 | delivery,critical",
        "case-studies | Real Case Studies: Outages, Migrations, and Architectures That Shipped | 3 | practice,critical",
    ]),
    dict(id="T17", dir="17-databases", title="Databases: SQL, NoSQL, Vector", icon="🗄️", phase="A", prereqs=[], modules=[
        "storage-engines | B+Tree vs LSM-Tree: Compaction, Write/Read/Space Amplification | 2.5 | internals,critical",
        "wal-recovery | WAL, ARIES Recovery, Checkpoints, Durability | 1.5 | internals",
        "mvcc-isolation | MVCC vs Locking, Isolation Levels, Every Anomaly, Write Skew | 3 | internals,critical",
        "query-planner | Parse→Plan→Cost→Execute, Join Algorithms, EXPLAIN ANALYZE | 2.5 | internals,critical",
        "index-design | Composite Order, Covering, Partial, GIN/GiST/BRIN, When Indexes Hurt | 2 | internals",
        "postgres | PostgreSQL: VACUUM, Bloat, XID Wraparound, TOAST, HOT, pgvector | 3 | postgres",
        "sqlserver | SQL Server: Clustered vs Nonclustered, Parameter Sniffing, Columnstore | 2 | sqlserver",
        "mongodb | MongoDB: WiredTiger, Replica Sets, Concerns, Sharding, Race Conditions | 3 | mongodb,critical",
        "wide-column-kv | Cassandra/DynamoDB: Partition Keys, Hot Partitions, Single-Table Design | 2 | nosql",
        "redis | Redis: Structures, Persistence, Cluster, Eviction, Distributed Locks | 1.5 | nosql",
        "clickhouse | ClickHouse: MergeTree, Parts, Sparse Index, Why It's Fast | 2 | olap",
        "elasticsearch | Elasticsearch: Inverted Index, Segments, Refresh/Flush/Merge, Scoring | 1.5 | search",
        "vector-db-compare | Weaviate/Qdrant/Milvus/pgvector/FAISS — and When Vectors Are Wrong | 2 | vector,critical",
        "knowledge-graphs | Knowledge Graphs: RDF vs Property Graph, ArangoDB vs Neptune vs Neo4j, GraphRAG | 2.5 | graph,critical",
        "sql-mastery | Window Functions, Recursive CTEs, Lateral, Gaps-and-Islands + 60 Problems | 3 | sql",
        "oltp-vs-olap | OLTP vs OLAP vs HTAP: Row vs Column, Latency Budgets, Why You Can't Have Both | 2 | fundamentals,critical",
        "normalization | 1NF → 2NF → 3NF → BCNF → 4NF, and When to Denormalize On Purpose | 2 | modeling,critical",
        "dimensional-modeling | Star vs Snowflake Schema, Facts & Dimensions, SCD Types 0-6, Grain | 2.5 | modeling,critical",
    ]),
    dict(id="T08", dir="08-eval-observability", title="Eval & Observability", icon="🔬", phase="A", prereqs=[], modules=[
        "eval-harness | Eval Harness Design, Golden Datasets, Task Rubrics | 2 | eval",
        "llm-as-judge | LLM-as-Judge and Its Failure Modes; Judge Calibration | 2 | eval,critical",
        "ragas-deepeval | RAGAS + DeepEval Internals, Promptfoo, LangSmith Evals | 2 | eval",
        "agent-eval | Trajectory Eval, Tool-Call Accuracy, Task Completion, Cost/Step | 2 | eval,agents",
        "otel-genai | OpenTelemetry GenAI Semantic Conventions + Agent Span Design | 2.5 | observability,critical",
        "obs-platforms | LangSmith / Langfuse / Phoenix / Laminar Compared | 1 | observability",
        "classic-obs | RED/USE, SLO/SLI/Error Budgets, Prometheus/Grafana, Alert Design | 2.5 | observability",
    ]),
    dict(id="T14", dir="14-behavioral-principal", title="Behavioral & Principal", icon="🎯", phase="A", prereqs=[], modules=[
        "star-bank | 30-Story STAR Bank Mined From Your Resume | 3 | behavioral,critical",
        "principal-competencies | Scope, Ambiguity, Influence Without Authority, Tech Strategy | 2 | behavioral",
        "design-communication | The 45-Minute System Design Communication Framework | 1.5 | behavioral,critical",
        "company-specific | Amazon LPs, Google, Meta, Microsoft, Netflix, AI Startups | 1.5 | behavioral",
        "negotiation | Compensation Negotiation & Offer Evaluation | 1 | career",
    ]),
    dict(id="T15", dir="15-interview-simulator", title="Interview Simulator", icon="⚔️", phase="A", prereqs=[], modules=[
        "round-coding | Boss: Coding Round (45 min, 2 problems) | 1 | boss",
        "round-ml | Boss: ML/DL Depth Round | 1 | boss",
        "round-genai | Boss: GenAI/Agentic Depth Round | 1 | boss",
        "round-design | Boss: System Design Round | 1 | boss",
        "round-behavioral | Boss: Behavioral / Leadership Round | 1 | boss",
        "round-hm | Boss: Hiring Manager Resume Grill | 1 | boss",
        "round-full-loop | Boss: Full Onsite Loop (5 rounds) | 4 | boss,final",
    ]),
    dict(id="T02", dir="02-dsa-21-patterns", title="DSA: 21 Patterns", icon="🧩", phase="A", prereqs=[], modules=[
        "p01-two-pointers | Two Pointers | 2 | pattern",
        "p02-sliding-window | Sliding Window | 2 | pattern",
        "p03-fast-slow | Fast & Slow Pointers | 1.5 | pattern",
        "p04-merge-intervals | Merge Intervals | 1.5 | pattern",
        "p05-cyclic-sort | Cyclic Sort | 1 | pattern",
        "p06-ll-reversal | In-Place Linked List Reversal | 1.5 | pattern",
        "p07-bfs | Tree/Graph BFS | 2 | pattern",
        "p08-dfs | Tree/Graph DFS | 2 | pattern",
        "p09-two-heaps | Two Heaps | 1.5 | pattern",
        "p10-subsets | Subsets / Combinatorics | 2 | pattern",
        "p11-binary-search | Modified Binary Search | 2 | pattern",
        "p12-bitwise-xor | Bitwise XOR | 1 | pattern",
        "p13-top-k | Top-K Elements | 1.5 | pattern",
        "p14-k-way-merge | K-Way Merge | 1.5 | pattern",
        "p15-knapsack-01 | 0/1 Knapsack DP | 2.5 | pattern",
        "p16-knapsack-unbounded | Unbounded Knapsack DP | 2 | pattern",
        "p17-topological-sort | Topological Sort | 2 | pattern",
        "p18-trie | Trie | 2 | pattern",
        "p19-union-find | Union-Find | 2 | pattern",
        "p20-monotonic-stack | Monotonic Stack | 2 | pattern",
        "p21-backtracking | Backtracking | 2.5 | pattern",
        "adv-graphs | Dijkstra, A*, Bellman-Ford, Floyd-Warshall | 2.5 | advanced",
        "adv-trees | Segment Tree, Fenwick/BIT | 2 | advanced",
        "adv-strings | KMP, Z-Algorithm, Rolling Hash | 2 | advanced",
        "adv-greedy | Greedy + Exchange Argument Proofs | 1.5 | advanced",
        "graph-core | Graph Representations, Traversal Invariants, Cycle & Bipartite Detection | 2 | graphs,critical",
        "graph-shortest | Dijkstra, Bellman-Ford, Floyd-Warshall, A*, Johnson — and Which When | 2.5 | graphs,critical",
        "graph-mst-flow | MST (Kruskal/Prim), Max-Flow/Min-Cut, Bipartite Matching | 2.5 | graphs",
        "graph-scc | SCC (Tarjan/Kosaraju), Bridges, Articulation Points, 2-SAT | 2 | graphs",
        "graph-applied | Graphs in the Wild: Dependency Resolution, GraphRAG, Embeddings, PageRank | 2 | graphs",
    ]),
    dict(id="T05", dir="05-llm-internals", title="LLM Internals", icon="🧠", phase="A", prereqs=[], modules=[
        "autoregression | Autoregression: Next-Token Prediction, Teacher Forcing, Exposure Bias | 2 | internals,critical",
        "tokenization | Tokenization: Implement BPE End-to-End | 2 | internals",
        "attention | Attention: QKV, √dk, MHA→MQA→GQA→MLA, FlashAttention | 3 | internals,critical",
        "positional | Positional Encoding: Sinusoidal, RoPE, ALiBi, YaRN | 2 | internals",
        "architecture-blocks | Pre/Post-Norm, RMSNorm, SwiGLU, MoE Routing | 2 | internals",
        "build-nanogpt | Build & Train a nanoGPT-Class Model From Scratch | 4 | lab,critical",
        "pretraining | Data Curation, Dedup, Scaling Laws, Curriculum | 2 | training",
        "sampling | Temperature, Top-k/p, Min-p, Beam, Speculative Decoding | 2 | inference",
        "inference-serving | KV Cache Math, PagedAttention, Continuous Batching, vLLM/SGLang | 3 | inference,critical",
        "alignment | SFT → RLHF/PPO → DPO/ORPO/KTO → GRPO & RL Reasoning | 3 | training",
        "finetuning | LoRA/QLoRA/DoRA + the RAG-vs-FT-vs-Prompt Decision Tree | 3 | training,critical",
        "quantization | GPTQ/AWQ/GGUF/FP8/INT4 and Quality-vs-Cost Curves | 2 | inference",
        "embeddings-training | Contrastive Training, Matryoshka, Domain Adaptation, Rerankers | 2 | internals",
        "multimodal | ViT, CLIP, Whisper, VLM Architectures | 2 | internals",
        "bert-encoders | Encoder Models: BERT, Bi-Encoders vs Cross-Encoders, When an Encoder Beats an LLM | 2 | internals,critical",
        "transfer-distillation | Transfer Learning & Distillation: Feature Extraction, Full FT, Teacher-Student | 2 | training,critical",
    ]),
    dict(id="T01", dir="01-python-swe", title="Python & SWE Craft", icon="🐍", phase="B", prereqs=[], modules=[
        "data-model | CPython Data Model, Dunder, Descriptors, Metaclasses, MRO | 2.5 | language",
        "typing | Typing, Protocols, Generics, Pydantic v2 | 2 | language",
        "asyncio | Asyncio Deep: Event Loop, TaskGroups, Cancellation, Backpressure | 3.5 | concurrency,critical",
        "gil-parallelism | GIL, Free-Threaded 3.13/3.14, Multiprocessing | 2 | concurrency",
        "memory-oom | Memory & OOM Forensics: GC, tracemalloc, memray, Fragmentation | 3 | performance,critical",
        "tooling | uv, ruff, mypy strict, pre-commit, Packaging | 1.5 | tooling",
        "testing | pytest, Hypothesis Property Tests, Mutation Testing | 2 | testing",
        "profiling | py-spy, cProfile, Flamegraphs, Performance Method | 1.5 | performance",
        "iterators-generators | Iterators vs Generators, yield, Lazy Pipelines, itertools | 2 | language,critical",
        "decorators | Decorators: Function, Class, functools.wraps, Parametrised, Real Uses | 2 | language,critical",
        "scoping-closures | LEGB Scoping, Closures, Late Binding, global/nonlocal | 1.5 | language",
        "copy-semantics | Mutability, Shallow vs Deep Copy, and the Aliasing Bugs They Cause | 1.5 | language",
        "pandas-mastery | Pandas: Vectorisation, groupby/agg, merge, Reshaping, Date Range → Month Rows | 2.5 | data,critical",
    ]),
    dict(id="T16", dir="16-computer-systems", title="Computer Systems: Transistor → Runtime", icon="⚙️", phase="B", prereqs=[], modules=[
        "cpu-microarch | Gates → ALU → Pipelining, Hazards, Branch Prediction, OoO, SIMD | 2.5 | hardware",
        "memory-hierarchy | Caches, Lines, Associativity, False Sharing, TLB, NUMA, MESI | 2.5 | hardware,critical",
        "assembly | x86-64 & ARM64: Registers, ABI, Stack Frames, Reading objdump | 2.5 | assembly",
        "compilers | Lex→Parse→IR→Optimize→Codegen, SSA, Inlining, Vectorization, LLVM | 2.5 | compilers",
        "cpython-runtime | CPython: Bytecode, Eval Loop, PyObject, Refcounts, Adaptive Interpreter | 2 | runtime",
        "jvm-runtime | JVM: Class Loading, C1/C2 JIT, Escape Analysis, GC Algorithms | 2 | runtime",
        "go-v8-runtime | Go G-M-P Scheduler, Stack Growth; V8 Ignition/TurboFan | 1.5 | runtime",
        "os-internals | Processes/Threads, Context Switch Cost, Virtual Memory, Syscalls | 2.5 | os",
        "io-models | epoll, io_uring, mmap, Zero-Copy, File Descriptors | 2 | os,critical",
        "containers-low-level | cgroups + namespaces: What Docker Actually Is | 1.5 | os",
        "networking-stack | NIC→Kernel→Socket, TCP, TLS, HTTP/1.1 vs 2 vs 3/QUIC, DNS | 2.5 | networking",
        "numerics | IEEE-754, Float Pitfalls, bf16/fp16/fp8 in ML | 1.5 | numerics",
        "gpu-arch | SMs, Warps, Occupancy, Kernel Launch Overhead, Why Batching Wins | 2 | hardware",
    ]),
    dict(id="T03", dir="03-classical-ml", title="Classical ML", icon="📈", phase="B", prereqs=[], modules=[
        "linear-models | Linear/Logistic From Scratch, GD Variants Derived | 2 | fundamentals",
        "regularization | Regularization, Bias-Variance, Learning Curves | 1.5 | fundamentals",
        "trees-boosting | Trees → RF → XGBoost/LightGBM/CatBoost Internals | 3 | models,critical",
        "classic-models | SVM/Kernels, kNN, Naive Bayes, Clustering, PCA/SVD/UMAP | 2.5 | models",
        "metrics-calibration | Calibration, Imbalance, Metric Selection, Why AUC Lies | 2 | evaluation,critical",
        "feature-eng | Feature Engineering, Leakage, CV Strategies | 2 | practice",
        "recsys | CF, MF/ALS, Two-Tower, LTR, Cold Start, Ranking Funnel | 3 | recsys,critical",
        "bandits | ε-Greedy, UCB, Thompson, LinUCB, CMAB (your PySpark bullet) | 2 | rl,critical",
        "feature-selection | Feature Selection: Filter, Wrapper, Embedded, SHAP-Based, Why More Features Hurt | 2 | practice,critical",
        "missing-data | Missing & Corrupt Data: MCAR/MAR/MNAR, Imputation Strategies, When to Drop | 2 | practice,critical",
        "eda | EDA: Distributions, Correlation Heatmaps, Outliers, the Questions to Ask First | 2 | practice,critical",
        "statistics-inference | Hypothesis Testing: Null Hypothesis, p-value, t-test, ANOVA, Chi-Square, Power | 2.5 | fundamentals,critical",
        "anomaly-detection | Anomaly Detection: Statistical, Isolation Forest, Autoencoder, and the Pipeline | 2.5 | models,critical",
    ]),
    dict(id="T04", dir="04-deep-learning", title="Deep Learning", icon="🔥", phase="B", prereqs=["T03"], modules=[
        "neural-net-math | The Neuron → Forward Propagation → Loss → Backpropagation, By Hand | 3 | fundamentals,critical",
        "backprop-derivation | Backprop Derived: Chain Rule, Jacobians, Vanishing/Exploding Gradients | 2.5 | fundamentals,critical",
        "autograd | Autograd From Scratch: micrograd → Tensor Engine | 3 | fundamentals,critical",
        "architectures | MLP/CNN/RNN/LSTM Raw → PyTorch → Keras 3 | 3 | fundamentals",
        "optimization | Init, Norms, Adam/AdamW/Lion/Muon, LR Schedules | 2.5 | training",
        "training-engineering | AMP, Grad Accum/Clipping, Checkpointing, NaN Debugging | 2.5 | training,critical",
        "distributed-training | DDP, FSDP, DeepSpeed ZeRO, Tensor/Pipeline Parallel | 3 | scaling,critical",
        "compile-cuda | torch.compile, Dynamo/Inductor, CUDA Model, Triton Intro | 2.5 | performance",
        "export-optimize | ONNX, TensorRT, PTQ/QAT, Pruning, Distillation | 2.5 | deployment",
        "tensorflow | TF/Keras 3 Parity + TF Serving | 2 | frameworks",
        "activations | Activations: Sigmoid, Tanh, ReLU vs Leaky/GELU/SwiGLU, and Sigmoid vs Softmax | 2 | fundamentals,critical",
        "computer-vision | Computer Vision: CNN → ResNet → ViT, Detection, Segmentation | 2.5 | models,critical",
        "sequence-models | CNN vs RNN vs LSTM vs Transformer: What Each Is Actually For | 2 | models,critical",
    ]),
    dict(id="T11", dir="11-polyglot-backend", title="Polyglot Backend", icon="🌐", phase="B", prereqs=[], modules=[
        "java-modern | Java 21/25: Records, Sealed, Pattern Matching, Virtual Threads | 2.5 | java",
        "jvm-tuning | JVM Memory Model, G1/ZGC, JIT Tiers, async-profiler/JFR | 2.5 | java,critical",
        "spring-boot | Spring Boot 3: DI Internals, WebFlux, Data, Security, Spring AI | 3 | java",
        "resilience4j | Resilience4j: Circuit Breaker, Bulkhead, Retry in Practice | 1.5 | java,resilience",
        "quarkus | Quarkus: Build-Time DI, GraalVM Native, Panache, Mutiny | 2 | java",
        "go-core | Go: Goroutines, Channels, Context, Generics, Memory Model, pprof | 3 | go",
        "go-services | Go: Worker Pools, gRPC, a Fast Vector-Search Microservice | 2.5 | go",
        "fastapi-to-go | Porting FastAPI → Go: The Rewrite, Benchmarked, and When It's Wrong | 3 | go,critical",
        "monolith-vs-micro | Monolith vs Modular Monolith vs Microservices vs Monorepo | 2.5 | architecture,critical",
        "node-ts | Node/TS: Event Loop, Streams, NestJS/Fastify, Vercel AI SDK | 2.5 | node",
        "react | React: Hooks Deep, RSC/Next.js, Perf, Streaming Agent UIs | 3 | frontend",
        "api-design | REST/gRPC/GraphQL, Versioning, OpenAPI-First, SSE/WebSocket | 2 | api,critical",
        "fastapi-deep | FastAPI Deep: Pydantic Validation, DI, Exception Handlers, BackgroundTasks | 2.5 | python,critical",
    ]),
    dict(id="T12", dir="12-devops-infra-security", title="DevOps, Infra & Security", icon="🛡️", phase="B", prereqs=[], modules=[
        "docker | Docker: Layers, Multi-Stage, Distroless, BuildKit, Scanning | 1.5 | containers",
        "k8s-objects | K8s Objects: Pod → Deployment → StatefulSet → DaemonSet → Job, and YAML That Works | 2.5 | k8s,critical",
        "k8s-core | Kubernetes: Control Plane, etcd, Scheduler, Reconcile Loop, Writing an Operator | 3 | k8s,critical",
        "k8s-networking | K8s Networking: Service Types, kube-proxy, Ingress, CNI, DNS, Network Policy | 3 | k8s,critical",
        "k8s-storage-config | PV/PVC/StorageClass, ConfigMaps, Secrets, ServiceAccounts, RBAC | 2 | k8s",
        "k8s-scaling | HPA/VPA/KEDA, Cluster Autoscaler, GPU Scheduling & Node Pools, Mesh | 2.5 | k8s",
        "k8s-troubleshooting | Debugging K8s: CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending, Evicted | 3 | k8s,critical",
        "k8s-production | Production K8s: Probes, PDBs, Requests/Limits, Rollouts, Multi-Tenancy, Cost | 2.5 | k8s,critical",
        "terraform | Terraform: Modules, State, Workspaces, Drift, terraform test | 3 | iac,critical",
        "cicd | GitHub Actions, ArgoCD/GitOps, Progressive Delivery | 2 | cicd",
        "jenkins | Jenkins From Scratch: Declarative Pipelines, Shared Libraries, Agents, Best Practices | 3 | cicd,critical",
        "artifact-registries | ECR vs Artifactory vs Nexus vs GHCR: Promotion, Retention, Signing, SBOM | 1.5 | cicd",
        "eks-ecs-ecr | EKS vs ECS vs Fargate vs ECR — the Decision Matrix | 2 | k8s,critical",
        "ssm-config | SSM Parameter Store vs Secrets Manager vs AppConfig; Config Hierarchies | 1.5 | security,critical",
        "local-cloud-parity | Local ↔ Cloud Parity: LocalStack, Testcontainers, devcontainers, Ollama | 2 | tooling,critical",
        "secrets | Secret Management & Rotation, JWT TTL Caching | 1.5 | security",
        "owasp | OWASP Top 10 + OWASP LLM Top 10, SQL Injection Deep | 2.5 | security,critical",
        "authz | RBAC/ABAC/ReBAC, Multi-Tenant Isolation, Zero Trust | 2 | security",
    ]),
    dict(id="T09", dir="09-mlops-llmops", title="MLOps / LLMOps", icon="🔁", phase="B", prereqs=["T08"], modules=[
        "tracking-registry | MLflow/W&B, Model + Prompt Registries, DVC/LakeFS | 2 | platform",
        "model-cicd | CI/CD for Models & Prompts, Shadow/Canary, Rollback | 2 | platform,critical",
        "feature-stores | Feature Stores, Training-Serving Skew | 1.5 | platform",
        "orchestration | Airflow / Dagster / Prefect | 1.5 | platform",
        "spark | Spark/PySpark Tuning: Shuffle, Skew, AQE, Broadcast, EMR Packaging | 3 | data,critical",
        "serving | SageMaker, Bedrock, Vertex, KServe, Ray Serve, BentoML | 2 | serving",
        "gpu-cost | GPU Capacity & Cost Engineering, Autoscaling, Spot | 2 | cost",
        "model-monitoring | Model Monitoring in Production: What to Log, Alert Thresholds, Dashboards | 2.5 | production,critical",
        "data-drift | Data & Concept Drift: PSI/KS/KL Detection, Shift Types, Retraining Triggers | 2.5 | production,critical",
        "huggingface-ecosystem | Hugging Face + LangChain: transformers, datasets, PEFT, and Where Each Belongs | 2 | platform",
        "bedrock-vs-sagemaker | Bedrock vs SageMaker vs Self-Hosted: The Honest Selection Matrix | 2 | serving,critical",
    ]),
    dict(id="T13", dir="13-sde-craft-vibe-coding", title="SDE Craft & Vibe Coding", icon="✨", phase="B", prereqs=[], modules=[
        "git-advanced | Git: Rebase, Bisect, Worktrees, Trunk-Based Dev | 1 | craft",
        "code-review | Principal-Level Code Review, Giving and Receiving | 1 | craft",
        "testing-practice | TDD, Testing Pyramid, Contract Tests, Testcontainers, Chaos | 2 | testing",
        "refactoring | Refactoring Catalogue, Strangler Fig, Legacy Migration | 2 | craft,critical",
        "technical-writing | ADRs, RFCs, Design Docs | 1.5 | craft",
        "incidents | Incident Response, Blameless Postmortems, On-Call | 1 | craft",
        "vibe-coding | AI-Assisted Coding: CLAUDE.md, Skills, Subagents, Spec-Driven Dev | 2.5 | ai-craft,critical",
    ]),

    # ---------------------------------------------------------------- v0.3 additions
    dict(id="T18", dir="18-data-engineering", title="Data Engineering & Warehousing", icon="🏭", phase="A", prereqs=[], modules=[
        "pyspark-scratch | PySpark From Scratch: RDD → DataFrame → Catalyst → Tungsten | 3 | spark,critical",
        "pyspark-advanced | Shuffle, Skew, AQE, Broadcast, Partitioning, Caching, UDF Costs | 3 | spark,critical",
        "spark-streaming | Structured Streaming: Watermarks, Triggers, Exactly-Once Sinks | 2 | spark",
        "databricks | Databricks: Delta Lake, Unity Catalog, Photon, DLT, Workflows | 3 | platform,critical",
        "snowflake | Snowflake: Micro-Partitions, Virtual Warehouses, Time Travel, Zero-Copy Clone | 3 | platform,critical",
        "databricks-vs-snowflake | Databricks vs Snowflake vs BigQuery vs Redshift — the Honest Matrix | 2.5 | tradeoffs,critical",
        "bigquery | BigQuery: Slots, Partitioning, Clustering, Cost Control + 40 SQL Questions | 3 | platform,critical",
        "lakehouse | Lakehouse: Iceberg vs Delta vs Hudi, Table Formats, Catalog Evolution | 2.5 | architecture",
        "ingestion | Batch vs Stream Ingestion, CDC, Idempotent Loads, Backfills, Late Data | 2.5 | pipelines",
        "airflow | Airflow From Scratch: DAGs, Operators, Sensors, XCom, Deferrable, Best Practices | 3 | orchestration,critical",
        "data-quality | Contracts, Great Expectations, Freshness/Volume/Schema SLAs, Lineage | 2 | quality",
        "data-modeling-e2e | Source → Bronze → Silver → Gold: Modeling a Warehouse End to End | 3 | modeling,critical",
        "emr | EMR Deep: Clusters vs Serverless, Steps API, Bootstrap, Packaging, Spot Strategy | 3 | aws,critical",
        "scheduling-triggering | Scheduling & Auto-Triggering: Cron vs Event vs Sensor, EventBridge, Step Functions, S3 Events | 2.5 | orchestration,critical",
        "backfill-replay | Backfills, Replays, Idempotent Reruns, Late Data, and Not Corrupting the Warehouse | 2.5 | pipelines,critical",
    ]),
    dict(id="T19", dir="19-testing-quality", title="Testing & Quality Engineering", icon="🧪", phase="A", prereqs=[], modules=[
        "test-strategy | Test Strategy: Pyramid vs Trophy, What to Test, What Never To | 2 | strategy,critical",
        "unit-testing | Unit Testing Done Right: Doubles, Fixtures, Parametrize, Property-Based | 2.5 | unit",
        "integration-testing | Integration Tests: Testcontainers, Real DBs, Seeding, Isolation | 2.5 | integration,critical",
        "contract-testing | Consumer-Driven Contracts (Pact), Schema Compat, Breaking-Change Gates | 2 | integration",
        "regression-testing | Regression Suites, Golden Baselines, Snapshot Testing, Flake Management | 2.5 | regression,critical",
        "e2e-testing | E2E: Playwright, Test Data, Environments, Why E2E Suites Rot | 2 | e2e",
        "load-testing | Load & Stress: JMeter, Locust, k6, Gatling — Modelling Real Traffic | 3 | performance,critical",
        "perf-methodology | Perf Testing Method: Baseline, Soak, Spike, Breakpoint; Reading Results | 2 | performance",
        "chaos-testing | Chaos & Fault Injection: Toxiproxy, Litmus, Game Days | 2 | resilience",
        "ml-testing | Testing ML: Data Tests, Model Tests, Behavioural Tests, Metamorphic | 2.5 | ml,critical",
        "llm-testing | Testing LLM Systems: Non-Determinism, Golden Trajectories, Judge Drift | 2.5 | llm,critical",
        "coverage-mutation | Coverage Lies; Mutation Testing Tells the Truth | 1.5 | quality",
    ]),
    dict(id="T27", dir="27-tooling-debugging", title="Tooling, Docker & Debugging Mastery", icon="🔧", phase="A", prereqs=[], modules=[
        "docker-essentials | Docker Essentials: Images, Layers, Volumes, Networks — Every Command | 2.5 | docker,critical",
        "docker-mastery | Dockerfile Mastery: Multi-Stage, Cache, Distroless, Non-Root, Size & Speed | 2.5 | docker,critical",
        "docker-compose | Compose for Local Stacks: Depends-On, Healthchecks, Profiles, Overrides | 1.5 | docker",
        "docker-debug | Debugging Containers: exec, logs, inspect, nsenter, dive, OOMKilled, Exit Codes | 2 | docker,critical",
        "git-mastery | Git Deep: Objects, Refs, Rebase, Bisect, Reflog, Worktrees, Recovering Anything | 2.5 | git,critical",
        "pr-review | PR Review at Speed: What to Look For, In What Order, and What to Ignore | 2 | review,critical",
        "reviewing-ai-code | Reviewing AI-Written Code: Where LLMs Fail, the 10-Point Checklist | 2 | review,critical",
        "debug-methodology | Debugging as a Discipline: Bisect the Space, Not the Code | 2 | debugging,critical",
        "debug-any-language | Debuggers Everywhere: pdb, delve, jdb/IntelliJ, node --inspect, rust-gdb | 2.5 | debugging,critical",
        "prod-debugging | Production Debugging: Core Dumps, Thread Dumps, Heap Dumps, Live Profiling | 2.5 | debugging,critical",
        "observability-debug | Debugging From Traces & Logs Alone (When You Can't Attach) | 2 | debugging",
    ]),
    dict(id="T28", dir="28-ai-assisted-architecture", title="AI-Assisted Architecture (Claude)", icon="🧭", phase="A", prereqs=[], modules=[
        "claude-code-model | How Claude Code Works: Context, Tools, the Agent Loop You're Driving | 2 | foundations,critical",
        "context-files | CLAUDE.md / AGENTS.md: Designing the Context an Agent Actually Reads | 2 | foundations,critical",
        "skills-design | Skills: Writing, Scoping, Triggering, Testing, and Versioning Them | 2.5 | skills,critical",
        "subagent-architecture | Subagents & Isolation: Delegation Boundaries, Distilled Returns | 2 | architecture,critical",
        "spec-driven-dev | Spec-Driven Development: Plan → Approve → Build → Verify | 2 | workflow,critical",
        "agentic-refactor | Large-Scale Refactors With Agents: Guardrails, Checkpoints, Rollback | 2.5 | workflow",
        "mcp-authoring | Authoring MCP Servers for Your Own Codebase & Tools | 2.5 | mcp",
        "ai-arch-review | Using Agents for Architecture Review, ADRs, and Design Docs | 2 | architecture",
        "claude-architect | The Claude Architect Model: Operating as the Architect, Not the Typist | 3 | architecture,critical",
        "agent-skills-arch | Skill-Mediated Agents: Architectural Patterns & Reference Architecture | 2.5 | skills",
        "harness-comparison | Harness Comparison: Claude Code vs Agent Framework vs Codex vs Cursor | 2 | tradeoffs,critical",
        "when-not-to | When NOT to Let an Agent Write It: The Failure Taxonomy | 1.5 | judgment,critical",
    ]),
    dict(id="T29", dir="29-networking", title="Networking & Protocols", icon="🌐", phase="A", prereqs=[], modules=[
        "osi-tcpip | OSI vs TCP/IP Model: What Each Layer Actually Does, and Where Bugs Live | 2 | fundamentals,critical",
        "ip-layer | IP: Addressing, Subnets/CIDR, Routing, Fragmentation, NAT, IPv4 vs IPv6 | 2.5 | fundamentals,critical",
        "tcp-deep | TCP Deep: Handshake, Session Lifecycle, State Machine, TIME_WAIT, Sequence Numbers | 3 | tcp,critical",
        "tcp-performance | Congestion Control, Window Scaling, Nagle, Keepalive, Backlog, SO_REUSEADDR | 2.5 | tcp,critical",
        "tcp-vs-udp-vs-ip | TCP vs UDP vs raw IP vs QUIC — What Each Guarantees and Costs | 2 | fundamentals,critical",
        "tls | TLS 1.3: Handshake, Certificates, SNI, ALPN, mTLS, Cipher Suites, Debugging with openssl | 2.5 | security,critical",
        "http-semantics | HTTP Semantics: Why GET vs POST vs PUT vs PATCH, Idempotency, Safety, Caching, Status Codes | 2.5 | http,critical",
        "http-versions | HTTP/1.1 vs HTTP/2 vs HTTP/3: Multiplexing, Head-of-Line Blocking, Server Push's Death | 2 | http",
        "curl-mastery | curl Mastery: Every Flag That Matters, Debugging APIs From the Terminal | 2 | tools,critical",
        "grpc | gRPC Deep: Protobuf, HTTP/2 Framing, 4 RPC Types, Deadlines, Interceptors, Streaming | 3 | rpc,critical",
        "protocol-selection | REST vs gRPC vs GraphQL vs WebSocket vs SSE vs Webhooks — the Decision Matrix | 2.5 | tradeoffs,critical",
        "dns-lb | DNS Resolution, Load Balancer Internals (L4 vs L7), Proxies, CDN, Anycast | 2.5 | infra",
        "net-debugging | Network Debugging: tcpdump, Wireshark, ss/netstat, dig, traceroute, mtr, curl -v | 3 | debugging,critical",
        "net-failures | Network Failure Modes: Partitions, Timeouts vs Resets, Retries, Split Brain, MTU Blackholes | 2.5 | resilience,critical",
    ]),
    dict(id="T30", dir="30-auth-security", title="Auth & Application Security", icon="🔐", phase="A", prereqs=[], modules=[
        "authn-vs-authz | Authentication vs Authorization vs Accounting — and Why Conflating Them Breaks Systems | 1.5 | fundamentals,critical",
        "sessions-vs-tokens | Sessions vs Tokens: Stateful vs Stateless, and the Honest Tradeoff | 2 | fundamentals,critical",
        "jwt-deep | JWT Deep: Header/Payload/Signature, HS vs RS vs ES, JWKS, kid, Claims, Clock Skew | 3 | jwt,critical",
        "jwt-security | JWT Attacks: alg=none, Key Confusion, Weak Secrets, Replay, and the Revocation Problem | 3 | jwt,critical",
        "token-lifecycle | Access vs Refresh Tokens, Rotation, Revocation Lists, TTL Caching, Where to Store Them | 2.5 | jwt,critical",
        "oauth-oidc | OAuth 2.0 + OIDC: Auth Code + PKCE, Client Credentials, Device Flow, and the Dead Ones | 3 | oauth,critical",
        "sso-federation | SSO, SAML, Federation, Workload Identity, Service-to-Service Auth, mTLS | 2.5 | enterprise",
        "web-attacks | XSS, CSRF, CORS, Clickjacking, SSRF — Mechanism, Exploit, and Fix | 3 | appsec,critical",
        "injection | SQL Injection & Friends: Parameterization, ORMs, and Why Escaping Fails | 2.5 | appsec,critical",
        "api-security | API Security: Rate Limiting, Enumeration, BOLA/IDOR, Mass Assignment, OWASP API Top 10 | 2.5 | appsec,critical",
        "crypto-practice | Applied Crypto: Hashing vs Encryption vs Encoding, bcrypt/argon2, AES-GCM, Key Rotation | 2.5 | crypto,critical",
        "threat-modeling | Threat Modeling: STRIDE, Attack Trees, Trust Boundaries, Doing It in 45 Minutes | 2 | process",
    ]),
    dict(id="T31", dir="31-reinforcement-learning", title="Reinforcement Learning", icon="🎮", phase="B", prereqs=[], modules=[
        "rl-framing | The RL Problem: Agent, Environment, Reward, and Why It Isn't Supervised Learning | 2 | fundamentals,critical",
        "mdp | MDPs: States, Actions, Transitions, Discounting, Bellman Equations Derived | 3 | fundamentals,critical",
        "dynamic-programming | Policy Evaluation, Policy Iteration, Value Iteration — Coded From Scratch | 2.5 | tabular,critical",
        "monte-carlo-td | Monte Carlo vs Temporal Difference, TD(λ), Eligibility Traces | 2.5 | tabular",
        "q-learning-sarsa | Q-Learning vs SARSA: Off-Policy vs On-Policy, Implemented on Gridworld | 2.5 | tabular,critical",
        "exploration | Exploration vs Exploitation: ε-Greedy, UCB, Thompson, Intrinsic Motivation | 2 | fundamentals,critical",
        "dqn | Deep Q-Networks: Replay Buffers, Target Nets, Double/Dueling/Rainbow — Built From Scratch | 3 | deep-rl,critical",
        "policy-gradient | Policy Gradients: REINFORCE Derived, Baselines, Variance Reduction, Actor-Critic | 3 | deep-rl,critical",
        "ppo | PPO & TRPO: Trust Regions, Clipped Objectives, GAE — the Workhorse of RLHF | 3 | deep-rl,critical",
        "continuous-control | Continuous Actions: DDPG, TD3, SAC, and Where Each Breaks | 2.5 | deep-rl",
        "model-based | Model-Based RL, Dyna, MCTS, AlphaZero-Style Planning | 2.5 | advanced",
        "offline-rl | Offline RL, Distribution Shift, Conservative Q-Learning, Imitation & Inverse RL | 2.5 | advanced",
        "rl-for-llms | RL for LLMs: RLHF → DPO → GRPO, Reward Hacking, and Why It's Different | 3 | llm,critical",
        "rl-in-production | RL in Production: Sim-to-Real, Reward Design, Safety, and Why Most RL Projects Fail | 2.5 | production,critical",
    ]),
    dict(id="T20", dir="20-rust", title="Rust", icon="🦀", phase="B", prereqs=[], modules=[
        "rust-ownership | Ownership, Borrowing, Lifetimes — the Mental Model That Unlocks Rust | 3 | core,critical",
        "rust-types | Traits, Generics, Enums, Pattern Matching, Error Handling (Result/?) | 2.5 | core",
        "rust-memory | Box/Rc/Arc/RefCell, Interior Mutability, Send + Sync, Unsafe | 2.5 | core,critical",
        "rust-async | async/await, Futures, Tokio, Channels, Cancellation | 2.5 | async",
        "rust-perf | Zero-Cost Abstractions, SIMD, Benchmarking with Criterion, Profiling | 2 | performance",
        "rust-services | Building a Service: axum, sqlx, tracing, Docker, and Deploying It | 2.5 | services",
        "rust-for-ai | Rust in the AI Stack: tokenizers, candle, PyO3 Bindings, Why It's Everywhere | 2 | ai,critical",
        "rust-vs-go | Rust vs Go vs Python: The Honest Selection Criteria | 1.5 | tradeoffs,critical",
    ]),
    dict(id="T26", dir="26-frontier-ai", title="Frontier AI: World Models, Voice, Robotics", icon="🛸", phase="B", prereqs=["T05"], modules=[
        "world-models | World Models: What They Are, Why They Matter, the Core Idea | 2.5 | world-models,critical",
        "jepa | LeCun's JEPA & V-JEPA 2: Prediction in Latent Space, Not Pixels | 2.5 | world-models,critical",
        "nvidia-cosmos | NVIDIA Cosmos & Physical AI: World Foundation Models, Isaac Sim | 2.5 | robotics,critical",
        "vla-robotics | Vision-Language-Action Models: GR00T, RT-2, π0, and Embodied Agents | 2.5 | robotics",
        "imagebind-multimodal | ImageBind & Joint Embedding Spaces Across 6 Modalities | 2 | multimodal",
        "voice-models | Voice: Whisper, TTS, Realtime Speech-to-Speech, Latency Budgets, VAD | 2.5 | voice,critical",
        "speech-processing | Speech Processing: MFCC → Kaldi → Wav2Vec2 → Whisper, ASR Pipelines, Diarization | 2.5 | voice,critical",
        "video-generation | Video & Diffusion: DiT, Flow Matching, Consistency Models | 2.5 | generative",
        "reasoning-models | Reasoning Models: Test-Time Compute, RL on Chains, What Actually Changed | 2.5 | reasoning,critical",
        "frontier-landscape | The Frontier Landscape: Labs, Model Families, and Reading a Model Card | 1.5 | landscape",
    ]),
    dict(id="T22", dir="22-blockchain", title="Blockchain & Smart Contracts", icon="⛓️", phase="B", prereqs=[], modules=[
        "crypto-primitives | Hashes, Merkle Trees, Digital Signatures, ECDSA — Build Them | 2.5 | fundamentals,critical",
        "blockchain-scratch | Build a Blockchain From Scratch: Blocks, Chain, Validation, Forks | 3 | fundamentals,critical",
        "consensus | PoW → PoS → BFT: Nakamoto, Finality, Slashing, the Trilemma | 2.5 | consensus,critical",
        "bitcoin-ethereum | Bitcoin UTXO vs Ethereum Accounts, EVM, Gas, State Trie | 2.5 | platforms",
        "smart-contracts | Solidity From Scratch: Storage, Calls, Events, Upgradeability | 3 | contracts,critical",
        "contract-security | Reentrancy, Overflow, Oracle Manipulation, Front-Running, Audits | 2.5 | security,critical",
        "scaling | Rollups (Optimistic vs ZK), Data Availability, Bridges and Their Failures | 2.5 | scaling",
        "enterprise-blockchain | When Blockchain Is the Wrong Answer (Usually) — and When It Isn't | 1.5 | judgment,critical",
    ]),
    dict(id="T23", dir="23-quantum", title="Quantum Computing", icon="⚛️", phase="B", prereqs=[], modules=[
        "qubits | Qubits, Superposition, Entanglement, the Bloch Sphere — With the Linear Algebra | 2.5 | fundamentals,critical",
        "gates-circuits | Gates & Circuits: X/H/CNOT/Toffoli, Universality, Reading a Circuit Diagram | 2.5 | fundamentals",
        "algorithms | Deutsch-Jozsa → Grover → Shor: What the Speedup Actually Is | 3 | algorithms,critical",
        "qiskit | Hands-On: Qiskit/Cirq Simulators, Running a Circuit, Reading Results | 2.5 | practice",
        "error-correction | Noise, Decoherence, NISQ, Surface Codes, Logical vs Physical Qubits | 2 | hardware,critical",
        "quantum-ml | Quantum ML, VQE, QAOA — Genuine Promise vs Hype | 2 | ml",
        "post-quantum | Post-Quantum Cryptography: What Breaks, When, and Migration Plans | 2 | security,critical",
    ]),
    dict(id="T24", dir="24-finance-quant", title="Financial Engineering, Time Series & Banking", icon="📊", phase="B", prereqs=["T03"], modules=[
        "time-series-core | Stationarity, ACF/PACF, ARIMA/SARIMA, Decomposition — From Scratch | 3 | timeseries,critical",
        "time-series-modern | Prophet, GARCH, State Space, and Deep Forecasters (N-BEATS, TFT, TimesFM) | 3 | timeseries,critical",
        "ts-validation | Backtesting Without Lying to Yourself: Walk-Forward, Purging, Embargo | 2.5 | timeseries,critical",
        "market-microstructure | Order Books, Liquidity, Slippage, Execution — How Markets Actually Work | 2.5 | markets",
        "derivatives | Options, Black-Scholes Derived, the Greeks, Monte Carlo Pricing | 3 | quant,critical",
        "portfolio | Modern Portfolio Theory, CAPM, Factor Models, Risk Parity | 2.5 | quant",
        "risk-metrics | VaR, CVaR/Expected Shortfall, Stress Testing, Backtesting Risk Models | 2.5 | risk,critical",
        "basel | Basel I → II → III → IV: Capital, RWA, LCR/NSFR, What Each Fixed | 2.5 | banking,critical",
        "mrm | Model Risk Management: SR 11-7, Validation, Governance, the MRM Role | 2.5 | banking,critical",
        "ai-in-finance | AI in Finance: Fraud, Credit, AML, Explainability & Fair-Lending Constraints | 2.5 | ai,critical",
    ]),
    dict(id="T25", dir="25-product-business", title="Product Thinking & Business (MBA)", icon="💼", phase="B", prereqs=[], modules=[
        "product-thinking | Product Thinking for Engineers: Problem → Outcome → Solution | 2 | product,critical",
        "discovery | Discovery: JTBD, User Interviews, Opportunity Trees, Killing Your Idea Early | 2 | product",
        "metrics | North Star, AARRR, Leading vs Lagging, Guardrail Metrics, Goodhart's Law | 2 | product,critical",
        "experimentation | A/B Testing: Power, MDE, Sequential Testing, Novelty, Common Traps | 2.5 | product,critical",
        "strategy | Strategy: Porter, Moats, Build-vs-Buy, Platform vs Product, Wardley Maps | 2 | strategy",
        "unit-economics | Unit Economics, CAC/LTV, Margins, and the Cost of an AI Feature | 2 | finance,critical",
        "ai-product | Pricing & Positioning AI Products; Why Most AI Features Don't Ship | 2 | product,critical",
        "influence | Writing the One-Pager, the Business Case, and Getting Funded | 2 | leadership,critical",
    ]),
    # ---------------------------------------------------------------- JD-driven (Expedia Marketing Content ML)
    dict(id="T32", dir="32-applied-nlp-marketing-ml", title="Applied NLP & Marketing ML", icon="📣", phase="A", prereqs=["T03"], modules=[
        "nlp-classical | Classical NLP: Tokenization, Stemming, TF-IDF, n-grams, POS, Dependency Parsing | 2.5 | nlp,critical",
        "word-embeddings | Word2Vec Derived (CBOW/Skip-gram), GloVe, fastText — and Why Contextual Won | 2.5 | nlp,critical",
        "ner | Named Entity Recognition: CRF, BiLSTM-CRF, Transformer NER, Custom Entities, Eval | 2.5 | nlp,critical",
        "topic-modeling | Latent Dirichlet Allocation Derived, NMF, BERTopic, Coherence — and When LDA Still Wins | 3 | nlp,critical",
        "text-classification | Text Classification: Naive Bayes → Linear → Fine-Tuned Transformers, Multi-Label, Imbalance | 2.5 | nlp",
        "bayesian-methods | Bayesian Inference: Priors, Conjugates, Hierarchical Models, MCMC, Bayesian A/B | 3 | stats,critical",
        "experiment-design | Factorial Design, Multivariate Testing, Stratified Sampling, Blocking, Power Analysis | 3 | stats,critical",
        "causal-inference | Uplift/CATE Modeling, Diff-in-Diff, Propensity Scores, IV, Synthetic Control | 3 | stats,critical",
        "personalization | Personalization Systems: Segmentation, Contextual Bandits for Content, Cold Start | 2.5 | marketing,critical",
        "content-generation-ml | LLM Content Generation at Scale: Brand Voice, Quality Gates, Human Review, Multilingual | 3 | marketing,critical",
        "creative-optimization | Creative Testing & Dynamic Creative Optimization: Text + Image, Bandits for Creatives | 2.5 | marketing",
        "marketing-measurement | Marketing Mix Modeling, Attribution, Incrementality Testing, Holdouts | 2.5 | marketing,critical",
        "exec-communication | Presenting ML to Executives: Translating Model Metrics into Business Value | 2 | communication,critical",
    ]),
    dict(id="T33", dir="33-frontend-ui", title="Frontend & UI Engineering", icon="🖥️", phase="A", prereqs=[], modules=[
        "browser-rendering | The Browser: Parse → DOM/CSSOM → Layout → Paint → Composite, and the Critical Path | 2.5 | fundamentals,critical",
        "js-deep | JavaScript Deep: Event Loop, Microtasks, Closures, Prototypes, `this`, Modules | 3 | language,critical",
        "typescript | TypeScript: Structural Typing, Generics, Narrowing, Utility Types, and Where It Lies to You | 2.5 | language",
        "css-layout | CSS That Holds Up: Box Model, Flexbox, Grid, Stacking Contexts, Container Queries | 2.5 | fundamentals",
        "react-core | React Core: Reconciliation, Keys, Hooks Rules, Effects, and Why Your Component Re-Renders | 3 | react,critical",
        "react-advanced | RSC, Suspense, Server Actions, Next.js App Router, Hydration and Its Failure Modes | 3 | react,critical",
        "state-management | State: Local vs Server vs URL vs Global; TanStack Query, Zustand, Redux, and When None | 2.5 | react,critical",
        "streaming-ai-ui | Streaming Agent UIs: SSE vs WebSocket, Token Streaming, Optimistic Tool-Call Rendering | 3 | ai,critical",
        "web-performance | Core Web Vitals, Bundle Budgets, Code Splitting, Images, and Measuring Before Optimising | 3 | performance,critical",
        "accessibility | Accessibility: Semantics, ARIA, Keyboard, Focus Management, Screen Readers, WCAG | 2.5 | quality,critical",
        "frontend-security | Frontend Security: XSS Sinks, CSP, CORS, Token Storage, Supply-Chain Risk in npm | 2.5 | security,critical",
        "frontend-testing | Testing UI: RTL, Playwright, Visual Regression, and Why E2E Suites Rot | 2.5 | testing",
        "design-systems | Design Systems & Component Architecture: Composition, Variants, Tokens, Versioning | 2.5 | architecture",
        "build-tooling | Build Tooling: Vite, esbuild/SWC, Module Resolution, Tree Shaking, Source Maps | 2 | tooling",
    ]),
]

CLOUDS = [
    dict(id="C-AWS", dir="aws", title="AWS Atlas", icon="🟧", phase="A", modules=[
        "iam | IAM Deep: Policy Evaluation Logic, AssumeRole/STS, Boundaries, SCPs | 3 | security,critical",
        "lambda | Lambda Deep: Execution Model, Cold Starts, SnapStart, Concurrency, VPC | 2.5 | serverless,critical",
        "compute | Compute & Containers: EC2, ECS, EKS, Fargate, Batch | 2 | compute",
        "storage | Storage: S3 (classes, consistency, events), EBS, EFS, FSx | 2 | storage",
        "databases | Databases: RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune | 2.5 | database",
        "networking | Networking: VPC, Subnets, SG vs NACL, ALB/NLB, PrivateLink, Route53 | 2.5 | networking,critical",
        "data-analytics | Data: Glue, EMR, Athena, Redshift, Kinesis, MSK, OpenSearch | 2 | data",
        "ai-ml | AI/ML: SageMaker, Bedrock, AgentCore, Kendra, Comprehend, Textract | 2.5 | ai,critical",
        "integration | Integration: SQS, SNS, EventBridge, Step Functions, API Gateway | 2 | integration",
        "observability-cost | CloudWatch, X-Ray, CloudTrail, Cost Explorer, Well-Architected | 1.5 | ops",
    ]),
    dict(id="C-AZ", dir="azure", title="Azure Atlas", icon="🟦", phase="B", modules=[
        "identity | Entra ID, RBAC, Managed Identities, Conditional Access | 2.5 | security,critical",
        "functions | Azure Functions: Plans, Durable Functions, Bindings, Cold Starts | 2 | serverless",
        "compute | Compute: VMs, VMSS, App Service, Container Apps, AKS | 2 | compute",
        "storage-db | Blob/Files/Queues, Cosmos DB, Azure SQL, PostgreSQL Flexible | 2.5 | storage",
        "networking | VNet, NSG, App Gateway, Front Door, Private Link | 2 | networking",
        "data | Synapse, Data Factory, Databricks, Event Hubs, Fabric | 2 | data",
        "ai | Azure AI Foundry, Azure OpenAI, AI Search, ML Studio | 2.5 | ai,critical",
        "ops | Monitor, Log Analytics, App Insights, Cost Management | 1.5 | ops",
    ]),
    dict(id="C-GCP", dir="gcp", title="Google Cloud Atlas", icon="🟨", phase="B", modules=[
        "iam | GCP IAM: Roles, Service Accounts, Workload Identity Federation, Org Policy | 2.5 | security,critical",
        "serverless | Cloud Run, Cloud Functions, App Engine, Eventarc | 2 | serverless",
        "compute | Compute Engine, GKE, Autopilot, Batch | 2 | compute",
        "storage-db | GCS, Cloud SQL, Spanner, Bigtable, Firestore, AlloyDB | 2.5 | storage,critical",
        "networking | VPC, Shared VPC, Cloud Load Balancing, Cloud Armor, Interconnect | 2 | networking",
        "data | BigQuery, Dataflow, Dataproc, Pub/Sub, Looker | 2.5 | data,critical",
        "ai | Vertex AI, Agent Builder/ADK, Gemini API, Vector Search | 2.5 | ai,critical",
        "ops | Cloud Logging/Monitoring/Trace, FinOps | 1.5 | ops",
    ]),
]

# ---------------------------------------------------------------------------
# SPRINT SET — the ~8-weekend subset that actually decides interview outcomes.
# Phase A is now large enough that "Phase A" alone is not a plan. These module
# ids get tagged `sprint` and are ranked above everything else by the app.
# Keep this list under ~95 hours or it stops being a sprint.
# ---------------------------------------------------------------------------
SPRINT_WEEKENDS = {
    1: ["T07-agent-loop-from-scratch", "T07-react-pattern-raw", "T21-resilience-catalogue"],
    2: ["T07-langgraph-core", "T07-langgraph-durable", "T07-tool-engineering"],
    3: ["T06-chunking", "T06-vector-index-internals", "T06-hybrid-search", "T06-latency-accuracy"],
    4: ["T07-context-engineering", "T07-agent-memory", "T07-multi-agent-topologies"],
    5: ["T05-attention", "T05-inference-serving", "T10-distributed-fundamentals"],
    # design CRAFT before design PRACTICE — doing 20 system designs before
    # learning how to drive a design session is backwards
    6: ["T10-design-method", "T10-estimation", "T10-diagramming"],
    7: ["T08-llm-as-judge", "T08-agent-eval", "T17-mvcc-isolation", "T17-query-planner"],
    8: ["T10-resume-systems", "T14-star-bank", "T14-design-communication", "T14-company-specific"],
    9: ["T07-agent-zero-to-prod", "T10-genai-designs"],
    # harness/loop engineering is the organising frame for everything in W1-W9 —
    # it lands last on purpose, once you have the parts it names
    10: ["T07-harness-engineering", "T07-loop-engineering", "T28-claude-architect"],
}
# flat, in roadmap order — the quest generator follows this sequence exactly
SPRINT = [mid for we in sorted(SPRINT_WEEKENDS) for mid in SPRINT_WEEKENDS[we]]
SPRINT_WEEK = {mid: we for we, ids in SPRINT_WEEKENDS.items() for mid in ids}

LEVELS = [
    (0, "Initiate"), (500, "Apprentice"), (1200, "Practitioner"), (2200, "Engineer"),
    (3600, "Senior"), (5500, "Specialist"), (8000, "Staff"), (11000, "Architect"),
    (15000, "Distinguished"), (20000, "Principal Architect"),
]

XP = dict(deepdive=10, lab=50, drill=5, problem=15, problem_first_try=25,
          flashcard=3, design_doc=75, boss=200)

BADGES = [
    ("first-blood", "First Blood", "Complete your first module", "🩸"),
    ("tokenizer-smith", "Tokenizer Smith", "Implement BPE from scratch", "🔤"),
    ("attention-wrote", "Attention Is All You Wrote", "Build a transformer from scratch", "🧠"),
    ("loop-master", "Loop Master", "Write an agent loop with no framework", "♾️"),
    ("checkpoint-survivor", "Checkpoint Survivor", "Ship a durable LangGraph agent that resumes after a kill", "💾"),
    ("injection-immune", "Injection Immune", "Pass the prompt-injection red-team lab", "🧪"),
    ("half-open", "Half-Open", "Implement a circuit breaker with all three states", "⚡"),
    ("bulkheaded", "Bulkheaded", "Implement bulkhead isolation in 2 languages", "🚢"),
    ("vacuum-sealed", "Vacuum Sealed", "Diagnose and fix Postgres bloat + xid wraparound", "🧹"),
    ("mvcc-mind", "MVCC Mind", "Explain every isolation anomaly with a repro", "🔀"),
    ("hnsw-tuner", "HNSW Tuner", "Tune M/efConstruction/efSearch against a recall target", "🕸️"),
    ("cache-coherent", "Cache Coherent", "Demonstrate false sharing and fix it", "🧊"),
    ("assembler", "Down to the Metal", "Read and explain compiler assembly output", "🔩"),
    ("oom-slayer", "OOM Slayer", "Find and fix a real memory leak with memray", "💀"),
    ("monotonic", "Monotonic", "Solve 10 monotonic stack problems", "📉"),
    ("pattern-complete", "Pattern Complete", "Finish all 21 DSA patterns", "🧩"),
    ("polyglot", "Polyglot", "Ship the same service in Python, Java, and Go", "🗣️"),
    ("three-cloud", "Three-Cloud", "Complete IAM deep dives on AWS, Azure, and GCP", "☁️"),
    ("solid-ground", "Solid Ground", "Refactor a violation of each SOLID principle", "🏛️"),
    ("judge-of-judges", "Judge of Judges", "Calibrate an LLM judge against human labels", "⚖️"),
    ("traced", "Fully Traced", "Instrument an agent with OTel GenAI conventions", "🔭"),
    ("zero-downtime", "Zero Downtime", "Migrate a vector index with no downtime", "🚦"),
    ("boss-slayer", "Boss Slayer", "Pass 3 boss battles", "🗡️"),
    ("full-loop", "Full Loop", "Pass the 5-round onsite simulation", "🏆"),
    ("streak-4", "Consistent", "4-weekend streak", "🔥"),
    ("streak-12", "Relentless", "12-weekend streak", "🌋"),
    # v0.3
    ("backprop-by-hand", "Chain Rule", "Derive and hand-compute backprop for a 2-layer net", "🔗"),
    ("shuffle-slayer", "Shuffle Slayer", "Diagnose and fix a Spark skew/shuffle bottleneck", "⚡"),
    ("third-normal", "Third Normal", "Normalize to BCNF, then justify a deliberate denormalization", "🗃️"),
    ("cache-hit", "Cache Hit", "Ship a 3-layer cache (exact + semantic + prefix) with measured hit rates", "🎯"),
    ("schema-locked", "Schema Locked", "Get 100% valid structured output under adversarial inputs", "🔒"),
    ("red-green", "Red, Green, Refactor", "Complete a lab strictly test-first", "♻️"),
    ("load-bearing", "Load Bearing", "Find a breakpoint with Locust or k6 and fix the bottleneck", "📈"),
    ("borrow-checker", "Borrow Checker Whisperer", "Ship a Rust service with zero unsafe", "🦀"),
    ("go-faster", "Go Faster", "Port a FastAPI service to Go and benchmark both honestly", "🏎️"),
    ("contract-safe", "Contract Safe", "Find a reentrancy bug in a smart contract", "⛓️"),
    ("superposition", "Superposition", "Implement Grover's algorithm in a simulator", "⚛️"),
    ("basel-compliant", "Basel Compliant", "Explain RWA, LCR and NSFR without notes", "🏦"),
    ("walk-forward", "Walk Forward", "Backtest a model with purging and embargo, no leakage", "📉"),
    ("world-model", "World Model", "Explain JEPA vs generative world models and the tradeoff", "🛸"),
    ("shipped-it", "Shipped It", "Take one system from scratch to production-ready", "🚢"),
    ("offer-in-hand", "Offer In Hand", "Log a real offer in the debrief", "🏅"),
]


def parse_module(raw: str, track_id: str, order: int) -> dict:
    slug, title, hours, tags = [p.strip() for p in raw.split("|")]
    return dict(
        id=f"{track_id}-{slug}",
        slug=slug,
        title=title,
        hours=float(hours),
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        order=order,
        status="todo",
    )


def build() -> dict:
    tracks = []
    sprint = set(SPRINT)
    for t in TRACKS:
        mods = [parse_module(m, t["id"], i) for i, m in enumerate(t["modules"])]
        tracks.append(dict(
            id=t["id"], kind="track", dir=f"curriculum/{t['dir']}", title=t["title"],
            icon=t["icon"], phase=t["phase"], prereqs=t.get("prereqs", []),
            hours=round(sum(m["hours"] for m in mods), 1), modules=mods,
        ))
    for c in CLOUDS:
        mods = [parse_module(m, c["id"], i) for i, m in enumerate(c["modules"])]
        tracks.append(dict(
            id=c["id"], kind="cloud", dir=f"clouds/{c['dir']}", title=c["title"],
            icon=c["icon"], phase=c["phase"], prereqs=[],
            hours=round(sum(m["hours"] for m in mods), 1), modules=mods,
        ))
    # tag the sprint set and verify every id resolves (a typo here silently
    # drops a module from the sprint, which you would not notice for weeks)
    seen = set()
    for t in tracks:
        for m in t["modules"]:
            if m["id"] in sprint:
                seen.add(m["id"])
                if "sprint" not in m["tags"]:
                    m["tags"].insert(0, "sprint")
                m["sprint_order"] = SPRINT.index(m["id"])
                m["sprint_week"] = SPRINT_WEEK[m["id"]]
    missing = sprint - seen
    if missing:
        raise SystemExit(f"SPRINT references unknown module ids: {sorted(missing)}")

    sprint_hours = round(sum(m["hours"] for t in tracks for m in t["modules"]
                             if "sprint" in m["tags"]), 1)
    by_week = {}
    for t in tracks:
        for m in t["modules"]:
            if "sprint" in m["tags"]:
                by_week[m["sprint_week"]] = round(
                    by_week.get(m["sprint_week"], 0) + m["hours"], 1)
    # a weekend is ~9h; warn loudly rather than silently shipping an impossible plan
    over = {w: h for w, h in by_week.items() if h > 10.5}
    if over:
        print(f"WARN  sprint weekends over 10.5h: {over}")

    return dict(
        version="0.3",
        generated_for="Hari Siva Rami Dwarampudi",
        sprint=dict(modules=len(seen), hours=sprint_hours,
                    weekends=len(SPRINT_WEEKENDS), by_week=by_week),
        levels=[dict(xp=x, name=n) for x, n in LEVELS],
        xp_table=XP,
        badges=[dict(id=i, name=n, desc=d, icon=ic) for i, n, d, ic in BADGES],
        tracks=tracks,
        totals=dict(
            tracks=len(tracks),
            modules=sum(len(t["modules"]) for t in tracks),
            hours=round(sum(t["hours"] for t in tracks), 1),
        ),
    )


VARS = {"curriculum": "CURRICULUM", "flashcards": "FLASHCARDS",
        "drills": "DRILLS", "problems": "PROBLEMS"}


def emit(name: str, payload: dict) -> None:
    """Write both .json (source of truth) and .js (loadable from file:// without a server)."""
    (DATA / f"{name}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    js = f"window.{VARS[name]} = {json.dumps(payload)};\n"
    (DATA / f"{name}.js").write_text(js, encoding="utf-8")


def write_status(data: dict) -> None:
    """Emit CONTENT-STATUS.md — an explicit burn-down of written vs scoped modules.
    'What's pending' should be a list you can work through, not a vague feeling."""
    import glob
    rows, written_total = [], 0
    for t in data["tracks"]:
        files = {pathlib.Path(p).stem for p in glob.glob(str(ROOT / t["dir"] / "*.md"))}
        # a module counts as written if any .md in the track dir ends with its slug.
        # NOTE: use .stem, never .rstrip(".md") - rstrip strips a character SET,
        # so "10-design-method" would become "10-design-metho" and never match.
        w = sum(1 for m in t["modules"]
                if any(f.endswith(m["slug"]) for f in files))
        written_total += w
        rows.append((t, w))

    lines = [
        "# Content status",
        "",
        f"> Auto-generated by `app/build_data.py` · {data['totals']['modules']} modules scoped",
        "",
        f"**{written_total} / {data['totals']['modules']} modules written "
        f"({written_total / data['totals']['modules'] * 100:.1f}%)**",
        "",
        "Sprint weekends are the burn-down order that matters. Everything else is a",
        "reference library — pull on it when a topic comes up, or when a debrief promotes it.",
        "",
        "## Sprint (write these first, in this order)",
        "",
        "| WE | Module | h | written |",
        "|---|---|---|---|",
    ]
    sprint_mods = sorted(
        (m for t in data["tracks"] for m in t["modules"] if "sprint" in m["tags"]),
        key=lambda m: m["sprint_order"])
    for m in sprint_mods:
        trk = next(t for t in data["tracks"] for x in t["modules"] if x["id"] == m["id"])
        files = {pathlib.Path(p).stem for p in glob.glob(str(ROOT / trk["dir"] / "*.md"))}
        done = any(f.endswith(m["slug"]) for f in files)
        lines.append(f"| {m['sprint_week']} | {m['title']} | {m['hours']} | "
                     f"{'✅' if done else '—'} |")

    lines += ["", "## All tracks", "", "| Track | written | scoped | hours | phase |", "|---|---|---|---|---|"]
    for t, w in sorted(rows, key=lambda r: (-r[1], r[0]["id"])):
        lines.append(f"| {t['icon']} {t['title']} | {w} | {len(t['modules'])} | "
                     f"{t['hours']} | {t['phase']} |")

    lines += ["", "## How to burn this down", "",
              "- `/tutor-deepdive <module>` writes one module properly.",
              "- Say **\"write weekend N\"** to get a whole weekend's modules plus labs.",
              "- A scheduled weekly task can do this unattended — ask Claude to set it up.",
              "- Re-run `python app/build_data.py` to refresh this file.", ""]
    (ROOT / "CONTENT-STATUS.md").write_text("\n".join(lines), encoding="utf-8")
    return written_total


# module authors write one fragment per module (app/data/cards/<module-id>.json)
# so concurrent agents never clobber a shared file. FRAGMENTS says which
# aggregate each fragment directory folds into.
FRAGMENTS = {"flashcards": "cards", "drills": "drillsets", "problems": "problemsets"}


def merge_fragments(name: str, payload: dict) -> tuple[int, int]:
    """Fold app/data/<subdir>/*.json into the aggregate, keyed by item id.

    Returns (added, updated). Idempotent: an id already present is replaced, so
    re-running after editing a fragment picks up the correction rather than
    duplicating the card. Without this step a fragment is written to disk and
    never seen by the app - which is exactly what had happened to 12 modules.
    """
    d = DATA / FRAGMENTS[name]
    if not d.is_dir():
        return 0, 0
    items = payload.setdefault(name, [])
    idx = {it["id"]: i for i, it in enumerate(items) if "id" in it}
    added = updated = 0
    for frag in sorted(d.glob("*.json")):
        try:
            rows = json.loads(frag.read_text(encoding="utf-8")).get(name, [])
        except json.JSONDecodeError as e:
            raise SystemExit(f"bad JSON in {frag}: {e}")
        for row in rows:
            rid = row.get("id")
            if not rid:
                raise SystemExit(f"{frag}: every {name} row needs an 'id'")
            # the fragment filename IS the module id, so an author who omits the
            # field still gets a row the app can group and filter
            row.setdefault("module", frag.stem)
            if rid in idx:
                if items[idx[rid]] != row:
                    items[idx[rid]] = row
                    updated += 1
            else:
                idx[rid] = len(items)
                items.append(row)
                added += 1
    return added, updated


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    emit("curriculum", build())
    merged = []
    for name in ("flashcards", "drills", "problems"):
        p = DATA / f"{name}.json"
        payload = (json.loads(p.read_text(encoding="utf-8"))
                   if p.exists() else {"version": "0.2", name: []})
        added, updated = merge_fragments(name, payload)
        if added or updated:
            merged.append(f"{name} +{added}~{updated}")
        emit(name, payload)
    data = json.loads((DATA / "curriculum.json").read_text(encoding="utf-8"))
    t = data["totals"]
    written = write_status(data)
    print(f"OK  tracks={t['tracks']}  modules={t['modules']}  hours={t['hours']}  "
          f"written={written}  (json + js + CONTENT-STATUS.md)")
    if merged:
        print("    merged fragments: " + "  ".join(merged))


if __name__ == "__main__":
    main()
