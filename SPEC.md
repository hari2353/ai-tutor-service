# Spec: AI Tutor Service — Curriculum & Labs

## Objective
Comprehensive AI/ML engineering curriculum (483 modules, 36 tracks, 1113.5h) with
test-driven labs, mined from 895 Instagram saved posts + fanout.sh + LinkedIn.

## IG-Mined Topic Coverage (cross-pollination source)
Topics extracted from Instagram saved posts, LinkedIn, and fanout.sh — all mapped
to curriculum modules. See `mining/posts/2026-10-31-ig-batch2-extracts.md` for
full extraction record.

### Core AI/ML Topics
- LLM Internals: Attention, QKV, FlashAttention, RoPE, MoE, KV Cache, PagedAttention,
  Continuous Batching, Quantization, Speculative Decoding, vLLM/SGLang
- RAG: Chunking, Hybrid Search, Reranking, Query Transformation, CRAG, Self-RAG,
  GraphRAG, Agentic RAG, Multimodal RAG, Semantic Caching, Poisoned RAG Defense
- Agentic AI: Agent Loop, ReAct, Tool Engineering, MCP, Multi-Agent Topologies,
  Context Engineering, Agent Memory, Agent Safety, Red-Teaming, Harness Engineering
- Alignment: RLHF, DPO, Constitutional AI, RLAIF, GRPO, Synthetic Data
- Evaluation: LLM-as-Judge, Trajectory Eval, RAGAS, Guardrails, Prompt Regression
- MLOps: Tracking, Model CI/CD, Feature Stores, Serving, GPU Cost, Drift Detection
- System Design: CAP/PACELC, Consensus, Messaging, Caching, Classic Designs, ML Designs
- Security: OWASP Top 10, OWASP LLM Top 10, Prompt Injection, Auth, RBAC/ABAC
- Privacy: Differential Privacy, Federated Learning, On-Device AI

### Interview Prep
- DSA: 21 Patterns (Two Pointers, Sliding Window, Binary Search, BFS/DFS, DP, etc.)
- 105 RAG Interview Questions (meghana.ai carousel)
- 223 Agentic AI Interview Questions (bhavs.ai carousel)
- 200+ Google SDE Questions (codebuilderhq deck)
- 50 Coding Patterns (codedsoul_05 handbook)
- 55 Python Questions (datasciencebrain deck)
- Quant Trading Interviews (Jane Street/Citadel/HRT)

### Build Projects
- 15 AI builds + 10 coding warmups + 5 failure-mode projects
- LRU/LFU cache lab, semantic cache, RAG pipeline, agent loop, etc.

### Career & Craft
- Resume/ATS evidence, STAR bank, behavioral (Amazon LPs, Google, Meta, etc.)
- Vibe coding, technical writing, PR review, incident response

## Tech Stack
- Python, Markdown, JSON, JavaScript (app)
- Build: `python app/build_data.py` → 482 modules
- Tests: DOM (26), SM-2 (10), link_check (103 labs)
- Labs: py, go, java, rust, ts (test-driven, starter fails → solution passes)

## Commands
```bash
python app/build_data.py          # rebuild curriculum data
node app/tests/dom.test.js .     # DOM tests
node app/tests/sm2.test.js .     # SM-2 tests
python app/tests/link_check.py   # link integrity
pytest labs/py/37-lru-cache/tests/ -v --solution  # lab tests
```

## Cross-Repo References
- job-hunt-ai: uses resume/base_resume.pdf, shares skill taxonomy
- BitNet: local LLM inference (T05-quantization, T26-frontier-ai)
- codebase-memory-mcp: MCP tooling (T07-mcp-deep-dive)
- stair-vs-rag: RAG evaluation (T06-rag-eval)
