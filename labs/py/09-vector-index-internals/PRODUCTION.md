# Production notes — vector indexes

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| In-memory ANN | `hnswlib` / Faiss `IndexHNSWFlat` | default answer when the graph fits in RAM |
| Memory-constrained | Faiss `IndexIVFPQ` / `IVFScalarQuantizer` | recall ceiling = quantization error, not `nprobe` |
| Postgres-native | pgvector `hnsw` / `ivfflat` | `ivfflat` needs `ANALYZE` + reindex as data drifts |
| Billion-scale / SSD | DiskANN (Vamana) | compressed sketch in RAM, graph + vectors on SSD |

## What the real ones add over yours

- **SIMD everything** — distance computation dominates; real libraries hand-tune AVX/NEON kernels. Your numpy matmul is fine at lab scale and hopeless at 100M.
- **Training hygiene** — Faiss recommends ~`39 * nlist` training vectors for coarse quantizer k-means; under-train and your cells are garbage no matter what `nprobe` says.
- **ADC lookup tables** — PQ scoring compares the raw query to per-subspace LUTs, never reconstructing full vectors.
- **Residual encoding** — IVF-PQ encodes `v - centroid`, not `v`; the residual is far smaller than the raw offset from origin.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Recall plateaus below target however high `nprobe` goes | PQ quantization error is a storage ceiling, not a search knob | reduce compression (more subspaces/bits), rerank with exact distances, or drop PQ |
| Recall dropped after 10x data growth, params unchanged | search-time budget now covers a smaller fraction of the corpus | re-tune `nprobe`/`efSearch` against a fresh eval at the new scale |
| IVF lists wildly unbalanced, latency p99 spikes | k-means trained on a stale/unrepresentative sample | retrain on current data; monitor per-list sizes |
| Build OOMs or takes hours | training sample too big for RAM; k-means is the expensive part | train on a sampled subset — assignment can stream |
| Filtered query slow or silently under-returns | pre-filter degrades to brute force; post-filter misses valid hits | filter-aware traversal (ACORN-style) or oversample-then-rerank |

## The 3 questions an interviewer asks after you describe this

1. *"Recall is low — raise `nprobe` or fix PQ?"* — first check whether the loss is search-breadth (fixable with `nprobe`) or storage precision (`nprobe`-proof). If recall plateaus, it's the latter.
2. *"Why is `nlist ≈ sqrt(N)` only a starting point?"* — it balances list length vs cell count on paper; real tuning watches the measured recall–latency curve on your data.
3. *"Your IVF index serves stale results after heavy churn."* — postings were frozen at build time. Periodic retrain + rebuild, or an index that supports streaming inserts.
