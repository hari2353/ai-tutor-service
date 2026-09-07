# Production notes — hybrid search

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Lexical | OpenSearch / Elasticsearch BM25 | Your 100-line BM25 becomes Lucene's, with analyzers per language |
| Dense vectors | pgvector / a vector DB (Qdrant, Weaviate) | HNSW index — lab 04 builds it from scratch |
| Fusion | RRF (built-in in most engines) | k=60 works embarrassingly well; tune only with an eval set |
| Semantic caching | Redis / GCS with embedding similarity | Same query intent → same answer, bypassing retrieval |

## What production adds over yours

- **Learned sparse** (SPLADE-style) sits between BM25 and dense: lexical-shaped, learned weights — often the best single tower in production RAG.
- **Language analyzers**: your 3-gram shingles approximate a stemmer; production uses per-language analyzers (22 locales means 22 analyzers, or multilingual embeddings).
- **Metadata filtering first**: vector search is filtered by tenant/date/ACL before ranking — unfiltered hybrid is a compliance bug, not a perf bug.
- **Cross-encoders rerank top-k**: fusion's top-50 gets a reranker's top-10; two cheap stages beat one expensive one.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Exact-id query misses | No lexical channel — dense only | Hybrid exists for this; BM25 catches the identifiers |
| Recency ignored | Static corpus scoring | Time-decay boost or filtered reindex cadence |
| Multilingual queries miss | One embedding model for all locales | Multilingual embeddings (bge-m3 family) or per-locale indexes |
| RRF "tuned" worse than k=60 | Optimised on vibes | Tune only against Recall@k / MRR with a labelled eval set |

## The one-liner to remember

Lexical catches what it is called, dense catches what it means, and
reciprocal-rank fusion gets you ~90% of the value of anything fancier —
ship hybrid, then earn the complexity.
