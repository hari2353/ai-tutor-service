# Weekend 3 — RAG: Chunking, Vector Indexes, Hybrid Search, the Latency Triangle

This weekend decides interviews because RAG questions are where candidates either show they've built a retrieval pipeline against real numbers or reveal they've only called an embeddings API once — every recall/precision/latency claim here has to be backed by a formula or a measured default, not a vibe.

## Chunking: Fixed, Recursive, Semantic, Contextual, Late

**30-sec:** Chunking is the highest-leverage RAG decision because it happens before retrieval and generation — every downstream metric is bounded by whether the boundary preserved the answer. Recursive structure-aware splitting is the default starting point for almost everything. Semantic chunking earns its extra embedding calls only when topical boundaries genuinely vary within a doc. Contextual retrieval (Anthropic) fixes decontextualization cheaply via prompt caching; late chunking fixes the same problem with zero LLM calls, but needs a long-context embedding model. Pick chunk size empirically against a recall@k eval on your own corpus, not a blog-post default.

**Recursive split defaults:** separators `["\n\n","\n"," ",""]`; LangChain base: chunk_size 4000 chars, overlap 200 (most teams override to token counts).

**Contextual retrieval** (Anthropic, Sept 2024): prepend 50–100 token LLM-generated context before embedding + BM25. Failure rate 5.7%→2.9% (+BM25, 49% cut)→1.9% (+rerank, 67% cut). Cost with prompt caching: $1.02/million doc tokens (Claude 3 Haiku).

**Late chunking** (Jina AI): embed the whole document first with a long-context model, then mean-pool per chunk span. No LLM call, but requires a long-context embedder (jina-v2/v3, nomic-embed-text-v1).

**Chunk size by domain:** FAQ/support 200–500 tok · narrative/legal 800–1000 tok · code = one function/class, never char-count split. Overlap 10–20% of chunk size. RAG not needed under ~200k tokens (~500 pages) — just cache the whole thing in the prompt.

## Vector Index Internals: HNSW, IVF-PQ, ScaNN, DiskANN

**30-sec:** Exact k-NN is O(N) and doesn't survive past a few hundred thousand vectors at interactive latency, so production indexes trade recall for speed. HNSW builds a multi-layer graph of shortcuts; its three knobs (M, efConstruction, efSearch) each trade recall against memory, build time, or query latency differently. IVF-PQ clusters into cells and compresses with product quantization, trading real recall for an order-of-magnitude memory cut — the answer when the index doesn't fit in RAM. ScaNN wins recall-per-byte for MIPS; DiskANN answers "corpus too big for RAM at all." Filtered search is underestimated: naive pre-filter degenerates to brute force, naive post-filter under-returns — real systems need filter-aware graph traversal.

**HNSW memory:** bytes/vector ≈ 1.1×(4×dim + 8×M). 10M @ 768d, M=16 → 35.2 GB. 10M @ 1536d, M=16 → 69.0 GB. No clean delete — tombstone only, rebuild to reclaim quality.

**IVF-PQ:** nlist ≈ √N centroids. nprobe start 8–16 at 1–10M vectors. PQ: 768d @ m=96 subspaces → 96 bytes/vec (~32× compression). Quantization error is baked in at index time — nprobe can't fix it.

**DiskANN:** Vamana graph, PQ-compressed vectors in RAM, full vectors + graph on SSD. SIFT1B: 5000+ QPS, <3ms mean, 95%+ recall@1.

**Pick:** fits in RAM + need recall → HNSW. Memory-constrained, some recall loss OK → IVF-PQ. Billion-scale, RAM ≪ corpus → DiskANN. MIPS + Google stack → ScaNN.

## Hybrid Search: BM25 + Dense, RRF, ColBERT

**30-sec:** Dense and lexical (BM25) retrieval fail in complementary ways — dense finds paraphrases but blurs exact IDs and rare terms; BM25 nails exact terms but misses zero-overlap paraphrases. RRF fuses rank positions (not raw scores), which makes it robust to incompatible scales (cosine 0.85 vs BM25 12.4). Weighted score fusion needs careful, corpus-specific normalization or one retriever dominates. ColBERT/late-interaction models keep per-token embeddings and score with MaxSim, recovering term-level matching a pooled vector loses — at 20–35× the storage of a single-vector index.

**BM25:** k1 = 1.2 (term-freq saturation), b = 0.75 (length norm) — Lucene/ES defaults.

**RRF:** `score(d) = Σ 1/(k + rank_r(d))`, k = 60 by convention (empirical, Cormack 2009; k∈[40,80] performs comparably).

**ColBERT storage:** ~200 tok/doc × 128d × f32 → 1M docs ≈ 102 GB (~34× a 768d bi-encoder's ~3 GB); ColBERTv2 compression brings it to ~6 GB (~2×).

**Rule:** retrieval (BM25+dense) fixes recall; the reranker fixes precision. Neither substitutes for the other.

## The Latency/Accuracy/Cost Triangle

**30-sec:** End-to-end latency is spent, in order, on generation > reranking > ANN search > query embedding — the stage everyone tunes obsessively (the index) is usually not where the time goes. The standard pattern is a cascade: cheap wide retrieval (top 50–150, optimized for recall) → expensive narrow rerank (top 3–20, optimized for precision). Extra recall past what the reranker/generator can use is close to worthless, and stacking retrieval techniques gives diminishing, sub-additive accuracy while latency stays additive. Decide every tradeoff from a measured online metric, not opinion.

**2s budget worked example:** embed ~75ms · ANN ~100ms · rerank ~250ms (top ~100) · buffer ~75ms → generation gets ~1500ms (~75% of total) — dominant and least controllable.

**Cut reranking when:** stage-1 recall already sufficient (eval-verified), budget <500ms end-to-end, or corpus is small/low-noise.

## If you remember nothing else

1. Chunking is upstream of every RAG metric — recursive structure-aware split is the right default; validate chunk size against recall@k on your own corpus, never a blog default.
2. Contextual retrieval cuts failure rate 5.7%→1.9% with BM25+rerank stacked; it's cheap because of prompt caching.
3. HNSW memory ≈ 1.1×(4×dim + 8×M) bytes/vector — do this arithmetic out loud when asked about scale.
4. RRF fuses ranks, not scores (k=60) — this is why it's robust when retrievers live on incompatible score scales.
5. Retrieval fixes recall, reranking fixes precision — never claim one substitutes for the other.
6. Generation dominates end-to-end latency (~75% of a 2s budget), not the vector index — don't over-tune the wrong stage.
7. Extra retrieved candidates cost linearly in reranker latency and context tokens, and too many can hurt via "lost in the middle."
8. Filtered vector search naively degrades to brute force (pre-filter) or under-returns (post-filter) — needs filter-aware traversal.

## Numbers table

| Fact | Value |
|---|---|
| RAG not needed under | ~200k tokens (~500 pages) — cache in prompt instead |
| Contextual retrieval failure rate | 5.7% → 2.9% (+BM25) → 1.9% (+rerank) |
| Contextual retrieval cost | $1.02 / million doc tokens (cached, Haiku) |
| HNSW memory, 10M @ 768d/1536d | 35.2 GB / 69.0 GB |
| IVF-PQ nlist | √N centroids |
| PQ compression example | 768d, m=96 → 96 bytes/vec (~32×) |
| DiskANN SIFT1B | 5000+ QPS, <3ms mean, 95%+ recall@1 |
| BM25 k1 / b | 1.2 / 0.75 |
| RRF k | 60 (range 40–80 comparable) |
| ColBERT storage vs bi-encoder | ~34× raw, ~2× after v2 compression |
| Rerank latency (Cohere API) | 100–300ms |
| Rerank latency (self-hosted BGE-v2-m3, GPU) | ~50ms/pair |
| 2s latency budget split | embed 75ms / ANN 100ms / rerank 250ms / gen ~1500ms |
