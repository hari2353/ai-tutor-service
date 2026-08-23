# Hybrid Search: BM25 + Dense, RRF, ColBERT Late Interaction

> Sprint weekend 3 · source: `curriculum/06-rag/04-hybrid-search.md`

```
BM25       score = Σ IDF(qi) · f(qi,D)·(k1+1) / [f(qi,D) + k1·(1-b+b·|D|/avgdl)]
           k1 = 1.2 (term-freq saturation)  ·  b = 0.75 (length norm)  — Lucene/ES defaults
           dense retrieval loses exact IDs/codes/rare terms — BM25 loses paraphrases (no overlap)

RRF        score(d) = Σ_retrievers 1/(k + rank_r(d))  ·  k = 60 (empirical, Cormack et al. 2009)
           k in [40,80] performs comparably — not a precisely tuned optimum
           beats score fusion: ranks are scale-free; raw scores (cosine 0.85 vs BM25 12.4) aren't

WEIGHTED   fused = α·normalize(dense) + (1-α)·normalize(bm25)
FUSION     preserves magnitude info RRF discards; brittle — BM25 stats shift on reindex, α goes stale

COLBERT    per-token doc embeddings (128-dim typical), MaxSim: Σ_qtok max_dtok (q·d)
           storage: ~200 tok/doc, 128d, f32 → 1M docs ≈ 102 GB (~34x a 768d bi-encoder's ~3GB)
           ColBERTv2 residual/2-bit compression → ~6 GB (~2x bi-encoder)
           PLAID: centroid-based pruning before full MaxSim, for serving at scale

PRODUCTION Elasticsearch/OpenSearch (native hybrid + RRF) · Weaviate (alpha or RRF) · Qdrant
           (sparse+dense) · Vespa (native multi-vector/ColBERT tensors) · Milvus

RULE       retrieval (BM25+dense) fixes RECALL · reranker fixes PRECISION — neither substitutes
           for the other. Hybrid ≠ optional if corpus has both exact IDs and paraphrase-heavy queries.
```
