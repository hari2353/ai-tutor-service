# GraphRAG: Knowledge Graphs, Community Summaries, Global vs Local Queries

> **Track:** T06 RAG · **Time:** 2.5h · **Prereqs:** 07-advanced-rag, 14-metadata-design · **Updated:** 2026-10-31
> **Module id:** `T06-graph-rag` · **Tags:** advanced, retrieval

## The 30-second version

Standard RAG retrieves chunks by vector similarity — great for "what does document X say about Y" but useless for "what are the main themes across this entire corpus" or "how do entity A and entity B connect." GraphRAG (Microsoft, 2024) builds an explicit knowledge graph (entities + relationships extracted by an LLM), clusters it into hierarchical communities via the Leiden algorithm, and pre-summarizes each community. At query time, **global queries** ("summarize the themes") run MapReduce over community summaries; **local queries** ("what is entity X connected to") traverse the graph from seed entities. The cost is real: indexing runs ~$20-40 per million tokens with GPT-4o-class models vs ~$0.50 for flat RAG. The 2026 practitioner consensus: GraphRAG is justified only when (a) queries genuinely need cross-document or global reasoning at meaningful volume, and (b) you've verified the simpler ladder (hybrid search + reranking + parent-document retrieval + corrective grading) doesn't already solve it. Most RAG traffic doesn't.

## Why this gets asked

Because it's the most expensive RAG pattern and the most oversold. Interviewers probe: "when would you actually build a knowledge graph for retrieval?" The wrong answer is "for any corpus where entities matter" — that's most corpora, and GraphRAG on a simple Q&A corpus is a waste of money. The right answer names the specific query patterns that justify it (global/theme queries, multi-hop entity connections) and the cost gate (indexing cost vs. query volume). Also probed: the difference between GraphRAG (LLM-extracted graph + community summaries) and a plain knowledge-graph DB (Neo4j with manual schema) — the former is LLM-driven and fuzzy, the latter is structured and precise, and they serve different query types.

## Lineage: past → present → future

**What came before.** Knowledge graphs for search existed long before LLMs — Google's Knowledge Graph (2012), enterprise graph DBs (Neo4j, Neptune). The pain: building and maintaining a graph schema was manual, expensive, and brittle. LLMs changed the economics: you can now extract entities and relationships from unstructured text automatically, at the cost of LLM calls. Microsoft's GraphRAG (2024) systematized this: LLM extracts (entity, relationship, description) triples, clusters them into communities, and generates community summaries. This turned "build a knowledge graph" from a 6-month engineering project into a pipeline you can run in a day — but the LLM cost is the new bottleneck.

**Where it stands now.** GraphRAG (Microsoft, 20k+ GitHub stars) is the reference implementation. LightRAG (2024) is a cheaper alternative (~$0.50/M tokens) that skips community summaries and uses a simpler graph traversal. The 2026 landscape: GraphRAG is used in production by teams with genuine global-query workloads (legal discovery, research synthesis, compliance audits). For most RAG traffic, the "boring middle" (hybrid search + reranking + parent-document retrieval) delivers 90% of the value at 1% of the cost. The live disagreement is cost-justification: GraphRAG's indexing cost is only worth it when query volume × value-per-query exceeds the indexing investment.

**Where it's heading.** High confidence: lighter alternatives (LightRAG, HippoRAG) will capture most use cases that don't need full community summaries. Medium confidence: incremental indexing (adding new documents without rebuilding the whole graph) will become standard — currently the biggest operational pain point. Speculative: LLM-extracted graphs will improve as extraction models get cheaper and more structured-output-reliable, reducing the hallucination rate in entity extraction.

## Mental model

```
CORPUS ──► LLM extracts (entity, relationship, description) triples
               │
               ▼
         KNOWLEDGE GRAPH (nodes = entities, edges = relationships)
               │
               ▼
         LEIDEN CLUSTERING → hierarchical communities
               │
               ▼
         COMMUNITY SUMMARIES (LLM-generated per community)
               │
               ▼
   ┌───────────────────────────────────────────────┐
   │ GLOBAL QUERY: "main themes in corpus"         │
   │   → MapReduce over community summaries        │
   │   → final synthesized answer                  │
   ├───────────────────────────────────────────────┤
   │ LOCAL QUERY: "what is X connected to?"       │
   │   → seed entities from query                  │
   │   → traverse graph N hops                     │
   │   → retrieve source text chunks               │
   │   → generate answer                          │
   └───────────────────────────────────────────────┘
```

## Recognition heuristics

- **"Summarize the main themes across this entire corpus"** → global query → GraphRAG community summaries. Standard RAG can't do this (no single chunk captures "themes").
- **"How does entity A connect to entity B?"** → local query → graph traversal. Standard RAG needs both entities in the same chunk.
- **"What changed between version X and version Y of this policy?"** → could be GraphRAG (entity diff) or just structured extraction. Try structured extraction first.
- **Cost gate**: if indexing cost > expected query value over 6 months, don't build GraphRAG. Use hybrid search + reranking + parent-document retrieval instead.

## How it actually works

**Indexing pipeline:**
1. **Chunking**: split corpus into text units (paragraphs or sections).
2. **Entity extraction**: LLM extracts entities (name, type, description) and relationships (source, target, description) from each chunk. This is the expensive step — one LLM call per chunk.
3. **Graph construction**: deduplicate entities (by name + type), merge relationships, build the graph.
4. **Community detection**: Leiden algorithm clusters entities into hierarchical communities (coarse → fine).
5. **Community summarization**: LLM generates a summary per community. This is the second expensive step.
6. **Storage**: graph (Neo4j or in-memory), community summaries (vector store for global query matching).

**Query pipeline:**
- **Global**: embed the query → match against community summaries → MapReduce (map: answer partial from each summary; reduce: synthesize) → final answer.
- **Local**: extract seed entities from query → traverse graph (1-2 hops) → collect source chunks → generate answer.

**Cost estimate**: 1M tokens corpus → ~$20-40 indexing (GPT-4o) vs ~$0.50 (flat RAG). Query cost: global ~$0.10-0.50/query (MapReduce over many summaries), local ~$0.01-0.05/query.

## Common bugs and how these get shipped wrong

- **Building GraphRAG when hybrid search + reranking would suffice.** The most common mistake. GraphRAG's value is in global/cross-document queries; if 90% of your traffic is single-document lookups, you've spent 40x for nothing.
- **Not deduplicating entities.** "Apple" and "Apple Inc." and "AAPL" become three separate nodes, fragmenting the graph and making traversal useless. Requires fuzzy matching + LLM-based canonicalization.
- **Community summaries too vague.** If the summary says "this community discusses various topics," it's useless for global queries. The summarization prompt must enforce specificity.
- **Ignoring incremental indexing.** Adding new documents requires re-running the entire pipeline (or at least re-clustering). Plan for this upfront.
- **Using GraphRAG for real-time queries.** Global queries are MapReduce over many summaries — slow. Cache community summaries or use a lighter alternative (LightRAG) for latency-sensitive paths.

## Interview questions

1. **"When would you build a knowledge graph for retrieval?"** Answer: when queries genuinely need cross-document reasoning or global themes, and after verifying the simpler ladder doesn't solve it. Name the cost gate.
2. **"GraphRAG vs a plain Neo4j knowledge graph?"** Answer: GraphRAG is LLM-extracted (fuzzy, auto-generated, entity relationships from text); Neo4j is structured (precise, manual schema, exact queries). Different tools for different query types.
3. **"How do you handle entity deduplication?"** Answer: fuzzy string matching + LLM-based canonicalization + type disambiguation. This is the hardest part of indexing.
4. **"What's the indexing cost and how do you justify it?"** Answer: ~$20-40/M tokens (GPT-4o). Justified when global-query volume × value-per-query exceeds indexing cost over 6 months.

## Red flags that fail you

- Building GraphRAG without first trying hybrid search + reranking + parent-document retrieval.
- Claiming GraphRAG is "just a knowledge graph" — it's LLM-extracted + community-summarized, which is fundamentally different from a structured graph DB.
- Ignoring the indexing cost — "it's just a pipeline" is wrong; it's an LLM-heavy pipeline with real per-token costs.
- Not handling entity deduplication — the graph becomes a mess of near-duplicate nodes.

## Cheat card

- GraphRAG = LLM-extracted knowledge graph + Leiden clustering + community summaries.
- Global queries = MapReduce over community summaries. Local queries = graph traversal.
- Cost: ~$20-40/M tokens (GPT-4o) vs ~$0.50/M (flat RAG). Justify with query patterns.
- Lighter alternative: LightRAG (~$0.50/M tokens, no community summaries).
- Decision gate: try hybrid search + reranking + parent-doc first. GraphRAG only if global/cross-doc queries dominate.

## Sources

- [Microsoft GraphRAG (GitHub, 20k+ stars)](https://github.com/microsoft/graphrag) — accessed 2026-10-31
- [LightRAG: Simple and Fast Retrieval-Augmented Generation](https://github.com/HKUDS/LightRAG) — accessed 2026-10-31
- [HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs](https://github.com/OSU-NLP-Group/HippoRAG) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Graph RAG identified as a gap in the RAG track (no dedicated module existed; only incidental mentions).
