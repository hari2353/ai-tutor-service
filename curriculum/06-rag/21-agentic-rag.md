# Agentic RAG: Agent Loops, Query Planning, Self-Correction, Multi-Hop

> **Track:** T06 RAG · **Time:** 2.5h · **Prereqs:** 07-advanced-rag, 06-query-transformation · **Updated:** 2026-10-31
> **Module id:** `T06-agentic-rag` · **Tags:** advanced, retrieval

## The 30-second version

Naive RAG is a single shot: embed, retrieve, generate. Agentic RAG turns retrieval into a loop — the agent plans the query, retrieves, evaluates the result, and can reformulate, expand scope, or switch strategies based on what it learns. The key patterns: **query planning** (decompose a complex question into sub-queries, execute them, synthesize), **self-correction** (grade the retrieval; if weak, rewrite the query and retry with a termination condition), **multi-hop** (each retrieval's result informs the next query), and **adaptive strategy selection** (vector search for factual, keyword for exact match, graph traversal for connections). Production systems (healthcare, legal search) run agentic RAG with CRAG-style grading, Self-RAG-style reflection, and multi-hop decomposition. The critical engineering discipline: define the termination condition upfront (max iterations, confidence threshold, or "no new information" detection) — without it, the agent loops indefinitely on a bad retrieval.

## Why this gets asked

Because "agentic RAG" is the 2026 buzzword and interviewers want to know if you can distinguish a genuine agent loop from a single-shot RAG with extra steps. They probe: "your RAG returns a wrong answer — what happens next?" The wrong answer is "we improve the prompt." The right answer is "the agent grades the retrieval, and if it's weak, it reformulates the query (HyDE, multi-query, decomposition) and retries, with a hard iteration cap." Also probed: the difference between agentic RAG (agent decides when/how to retrieve) and a fixed pipeline (always retrieve once). The principal-level probe: "how do you prevent the agent from looping forever on a bad retrieval?"

## Lineage: past → present → future

**What came before.** Naive RAG (2020-2023): embed, retrieve top-k, generate. No feedback loop — if retrieval was bad, the answer was bad, and nobody knew until a user complained. The pain: silent failures. The first fix was query transformation (HyDE, multi-query, decomposition) — still single-shot, but smarter queries. Then CRAG added a grading step (correct/ambiguous/incorrect) with fallback. Then Self-RAG added reflection tokens. Agentic RAG is the natural evolution: instead of fixed steps, an agent loop that decides what to do based on intermediate results.

**Where it stands now.** LangGraph and LlamaIndex are the two dominant frameworks for agentic RAG. Production write-ups (healthcare, legal, enterprise search) describe systems with 3-5 retrieval steps, query reformulation, and confidence-based termination. The 2026 consensus: agentic RAG is genuinely deployed but only for complex queries (multi-hop, ambiguous, or cross-document). For simple factual lookups, single-shot RAG with hybrid search + reranking is faster and cheaper. The live disagreement: how much autonomy to give the agent (free-form planning vs. structured steps) and how to handle the "no good answer" case (abstain vs. best-effort).

**Where it's heading.** High confidence: agentic RAG becomes the default for complex queries as models get better at self-evaluation. Medium confidence: the frameworks converge on a small set of canonical patterns (plan → retrieve → grade → reformulate → synthesize) with configurable termination. Speculative: agents that can dynamically choose between RAG, web search, and tool use within a single query — "universal retrieval" — but this requires robust routing and is still fragile.

## Mental model

```
USER QUERY
    │
    ▼
QUERY PLANNER ──► sub-queries (decomposition)
    │
    ▼
┌─────────────────────────────────────────┐
│  AGENT LOOP (max N iterations)          │
│  ┌─────────────────────────────────┐    │
│  │ RETRIEVE (vector/keyword/graph)  │    │
│  │     │                           │    │
│  │     ▼                           │    │
│  │ GRADE (relevant? sufficient?)    │    │
│  │     │                           │    │
│  │  ┌──┴──┐                        │    │
│  │  │     │                        │    │
│  │  ▼     ▼                        │    │
│  │ HIT   MISS → reformulate query  │    │
│  │  │     │   (HyDE/multi-query)   │    │
│  │  │     └──────► loop           │    │
│  │  ▼                             │    │
│  │ SYNTHESIZE (combine sub-answers)│    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
    │
    ▼
FINAL ANSWER + citations + confidence
```

## Recognition heuristics

- **"How do you handle a query that needs info from 3 different documents?"** → multi-hop agentic RAG with query decomposition.
- **"Your RAG returns a wrong answer — what happens next?"** → self-correction: grade retrieval, reformulate, retry with termination condition.
- **"How do you prevent infinite loops in agentic RAG?"** → hard iteration cap + "no new information" detection + confidence threshold.
- **"Agentic RAG vs single-shot RAG?"** → agentic for complex/ambiguous queries; single-shot for simple factual lookups (cheaper, faster).

## Common bugs and how these get shipped wrong

- **No termination condition.** The agent loops forever on a bad retrieval. Fix: max iterations (3-5) + "no new information" check.
- **No confidence threshold for abstention.** The agent always generates an answer, even when retrieval is garbage. Fix: if max similarity < threshold, abstain ("I don't have enough information").
- **Query reformulation that makes things worse.** HyDE can hallucinate a plausible but wrong hypothetical document, leading to worse retrieval. Fix: compare reformulated vs. original query results; use whichever retrieves better.
- **Not tracking intermediate results.** The agent loses context between hops. Fix: accumulate retrieved chunks in a shared state; pass the full context to the final synthesis step.
- **Over-engineering simple queries.** Running an agent loop for "what is the return policy?" wastes 3 LLM calls. Fix: route simple queries to single-shot RAG; agent loop only for complex/ambiguous queries.

## Interview questions

1. **"Design a RAG system for legal document search."** Answer: agentic RAG with query decomposition (break complex legal questions into sub-queries), multi-hop retrieval (connect related clauses), self-correction (grade retrieval quality), and a hard iteration cap. Abstain when confidence is low.
2. **"How do you prevent infinite loops in agentic RAG?"** Answer: max iterations (3-5), "no new information" detection (if the latest retrieval adds nothing new, stop), confidence threshold (if max similarity < 0.5, abstain).
3. **"Agentic RAG vs CRAG vs Self-RAG?"** Answer: CRAG is a fixed corrective step (grade → fallback). Self-RAG is a trained model with reflection tokens. Agentic RAG is a flexible agent loop that can plan, retrieve, grade, and reformulate dynamically. Agentic RAG subsumes CRAG and Self-RAG patterns but adds planning and strategy selection.

## Red flags that fail you

- Building an agent loop without a termination condition.
- Not abstaining when retrieval is weak — always generating an answer.
- Running agentic RAG for simple queries (waste of LLM calls).
- Not tracking intermediate results between hops.
- Confusing agentic RAG with a single-shot RAG that has query transformation.

## Cheat card

- Agentic RAG = agent loop: plan → retrieve → grade → reformulate → synthesize.
- Termination: max iterations (3-5) + "no new info" + confidence threshold.
- Abstain when max similarity < threshold.
- Use for complex/multi-hop/ambiguous queries only; single-shot for simple factual lookups.
- Frameworks: LangGraph, LlamaIndex. CRAG and Self-RAG are building blocks within the loop.

## Sources

- [CRAG: Corrective Retrieval Augmented Generation (arXiv:2401.15884)](https://arxiv.org/abs/2401.15884) — accessed 2026-10-31
- [Self-RAG: Learning to Retrieve, Generate, and Critique (arXiv:2310.11511)](https://arxiv.org/abs/2310.11511) — accessed 2026-10-31
- [LangGraph Agentic RAG Tutorial](https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_agentic_rag/) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Agentic RAG identified as a gap (no dedicated module; only incidental mentions in advanced-rag).
