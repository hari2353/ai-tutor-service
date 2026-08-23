# Vector Index Internals: HNSW, IVF-PQ, ScaNN, DiskANN

> Sprint weekend 3 · source: `curriculum/06-rag/03-vector-index-internals.md`

```
HNSW    layers: sparse-top → dense-bottom skip-list-like graph
        M (edges/node): recall+memory+build/search cost. Layer0 uses 2*M.
        efConstruction: recall at BUILD time only (no query cost)
        efSearch: recall at QUERY time (~linear latency cost), must be >= k
        defaults: pgvector m=16/ef_construction=64/ef_search=40
                  Weaviate maxConnections=32/efConstruction=128/dynamic ef (100-500, factor 8)
        prod starting point (1536-dim): m=16, ef_construction=128-200
        MEMORY: bytes/vector ≈ 1.1*(4*dim + 8*M)
          10M @ 768d,M=16  → 3,520 B/vec  → 35.2 GB
          10M @ 1536d,M=16 → 6,899 B/vec  → 69.0 GB
        no clean delete: tombstone only, rebuild to reclaim quality

IVF-PQ  nlist ≈ sqrt(N) centroids (coarse k-means, Voronoi cells)
        nprobe: cells searched per query. Start 8-16 @ 1-10M vectors, tune to recall plateau
        PQ: split vector into m subspaces, 256 centroids/subspace (nbits=8)
            768d @ m=96 → 96 bytes/vec (~32x compression vs 3072B raw)
        PQ accuracy ceiling: quantization error is baked in at index time — nprobe can't fix it

ScaNN   anisotropic quantization: penalizes error PARALLEL to vector (not uniform reconstruction
        error) — better recall/byte for MIPS. Google/Vertex AI ecosystem.

DiskANN Vamana graph (single-layer, alpha-pruned ~1.2), PQ-compressed vectors cached in RAM,
        full vectors + graph on SSD. SIFT1B: 5000+ QPS, <3ms mean, 95%+ recall@1, 16-core/64GB RAM.

FILTERED SEARCH   pre-filter → degenerates to brute force on filtered subset (no subset index)
                  post-filter → under-returns on selective filters (search never routed there)
                  fix: filter-aware traversal (Weaviate ACORN 2-hop, Qdrant filterable HNSW)

PICK    fits in RAM + need recall → HNSW · memory-constrained, some recall loss OK → IVF-PQ
        billion-scale, RAM << corpus → DiskANN · MIPS + Google stack → ScaNN
```
