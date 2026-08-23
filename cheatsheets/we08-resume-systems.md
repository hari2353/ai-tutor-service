# Your 4 Flagship Systems as Formal Design Docs

> Sprint weekend 8 · source: `curriculum/10-system-design/09-resume-systems.md`

```
DOC SHAPE   context → requirements (+NON-GOALS) → architecture → decisions
            (chose X over Y because Z, accepted cost C) → data model →
            scale numbers → failure modes (SYMPTOM first) → what I'd change

DIAGRAM     ≤9 boxes · 90 seconds · left-to-right data flow
            drill-down target in the middle with space around it
            never mix deployment topology with data flow

S1 SKILLS   54,486 skills · 22 locales · 1.2M+ rows · Titan v2 512-dim
            ClickHouse HNSW (filtered ANN, tenant+locale in ORDER BY prefix)
            BGE-Reranker-Large cross-encoder · tiers custom→external→master
            vectors ≈ 1.2M × 512 × 4B ≈ 2.5 GB float32
            OOM: exit 137, no traceback → paginate + gc.collect at page bounds

S2 RECS     8 services · 307 commits · 178K+ LOC · 2M+ users · ~25% uplift
            boundary criterion = independent SCALING + FAILURE, not entities
            CMAB not supervised (logged policy starves new content)
            Redis multi-get for 100+ content IDs · Java 3,447 → Python 812
            gaps: no off-policy eval (IPS), merge ≥2 services

S3 AGENTS   3 agents over A2A · shared capabilities as FastMCP servers
            MCP = versioned TOOL CONTRACT · A2A = inter-agent MESSAGING
            step cap + token budget OUTSIDE agent logic
            reliability: 0.95³≈86% · 0.95¹⁰≈60% · 0.85¹⁰≈20% → CHECKPOINT

S4 SERVING  vLLM: continuous batching + PagedAttention (KV in blocks)
            concurrency limited by KV CACHE not FLOPs
            8B fp16 ≈ 16 GB weights; 24 GB card → ~6-7 GB KV → tens of seqs
            size for KV not weights · split queue_time from latency
            Bedrock batch offline (no capacity coupling) · vLLM online
            rate limit: bound CONCURRENCY, don't retry; per-executor × N!

S5 QUERY    RAG over schema+glossary+PRIOR QUERIES → GPT-4 → guardrail → Trino
            ALWAYS show the SQL · read-only + scan/row/time limits
            50% turnaround = removed a QUEUE, not faster queries
            gap: correctness never measured, only adoption

DO FIRST    the ~25% measurement method · fix SageMaker instance names
            p99s for S1 and S2 · reranker top-k · resume-or-restart for S3
            global vs per-executor LLM rate budget

KILL SWITCH no alternative rejected · invented number · 25-box diagram
            "we" with no personal decision · no non-goals · cause-first failures
```
