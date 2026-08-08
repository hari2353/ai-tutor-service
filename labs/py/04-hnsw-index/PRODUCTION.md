# Production notes -- vector index internals

## What you'd actually use

| Concern | This lab | Production |
|---|---|---|
| Implementation | Pure Python + numpy, one process | `hnswlib` / `faiss` (C++), or a managed index (pgvector, Qdrant, Weaviate, Pinecone) |
| Scale | Hundreds of vectors, fits trivially in memory | Millions-to-billions; memory layout and SIMD matter enormously |
| Deletes | Not supported | Tombstoning + periodic rebuild, or a delete-aware structure |
| Filtering | Not supported | Filter-aware graph traversal (Weaviate ACORN, Qdrant filterable HNSW) |
| Persistence | In-memory only | Snapshotted to disk, often memory-mapped for fast cold start |
| Distance metric | Euclidean only | Cosine, dot product (MIPS), each needs different quantization math for IVF-PQ |

## What the real ones add over yours

- **SIMD-vectorized distance computation.** This lab computes one distance at a
  time via `np.linalg.norm`. Production implementations batch distance
  computation across many candidates at once with SIMD intrinsics -- often the
  single biggest constant-factor speedup in the whole system.
- **Memory layout.** `hnswlib` stores vectors and graph adjacency in flat
  contiguous arrays, not Python dicts of numpy arrays and sets of ints. A dict of
  sets has significant per-node overhead; at 10M vectors that overhead alone can
  exceed the vectors' own memory footprint.
- **The neighbour diversity heuristic.** This lab's `_select_neighbors` keeps the
  `M` closest candidates -- simple and correct, but it can cluster neighbours in
  one direction and leave a node under-connected to the rest of the space. Real
  HNSW's heuristic explicitly favors neighbours that aren't already well-covered
  by an existing neighbour's neighbours, improving long-range navigability.
- **Filter-aware traversal.** None of the base algorithms (HNSW, IVF, DiskANN)
  were designed with "search these vectors AND tenant_id = X" in mind. Naive
  pre-filtering degrades to brute force; naive post-filtering silently
  under-returns when a filter is very selective. Production systems need the
  filter integrated into the graph traversal itself.
- **Disk-backed indexes at billion scale.** DiskANN keeps a compressed sketch in
  RAM and the full graph plus vectors on SSD, because a billion 768-dim float32
  vectors alone is ~3TB -- nobody keeps that entirely in RAM.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency doubles as the corpus grows from 1M to 10M | Graph traversal length grows with corpus size, and lower layers get denser | Raise `M` and `efConstruction` at build time, or move to a disk-backed index (DiskANN) past the point HNSW fits comfortably in RAM |
| Recall silently drops after someone "optimizes" `efSearch` down for latency/cost | `efSearch` was lowered without re-running an eval | Recall vs. `efSearch` needs to be a monitored curve, not a one-time tuning decision |
| A metadata filter that used to return instantly now scans the whole corpus | Naive pre-filtering degrades to brute force as filter selectivity increases | Filter-aware graph traversal, or a separate filtered index per common predicate |
| Memory usage far exceeds `N × dim × 4 bytes` | Graph adjacency overhead from Python-object-heavy structures (as in this lab) | Flat/packed adjacency arrays; this is exactly what `hnswlib`/`faiss` optimize |
| A node becomes unreachable after many inserts/deletes | Naive neighbour pruning strands a low-degree node (the exact bug this lab's `_prune` explicitly guards against) | Never let pruning drop a node to zero remaining edges at a layer; periodically audit connectivity |
| Index doesn't fit in RAM at all | Corpus grew past what HNSW's full in-memory graph can hold (typically 50-100M vectors at common embedding dims) | IVF-PQ (Faiss) trades recall for an order-of-magnitude memory reduction via product quantization; DiskANN goes further onto SSD |

## Cost & latency

HNSW's whole value proposition is trading a small, bounded recall loss for
logarithmic-ish query time instead of linear brute force. At 10M vectors, brute
force is tens of milliseconds per query; a tuned HNSW index is typically
sub-millisecond to a few milliseconds at 90%+ recall. The build cost (memory +
`ef_construction` time) is the price paid up front for that query-time win --
which is why build parameters, not just search parameters, belong in a capacity
plan.

## The 3 questions an interviewer asks after you describe this

1. *"Your `_select_neighbors` just picks the M closest. What goes wrong with
   that, and what's the fix?"* -- it can under-connect a node to the broader
   graph even when it's locally well-connected, hurting long-range search
   quality; the fix is a diversity-aware heuristic that also considers whether a
   candidate is already reachable via an existing neighbour.
2. *"You have 200 endpoints... no wait, wrong lab -- you have a corpus that just
   crossed 80M vectors and doesn't fit in RAM anymore. What do you do?"* -- don't
   keep forcing HNSW; move to IVF-PQ for the memory reduction (accepting a real
   recall trade) or DiskANN if you need to stay closer to HNSW's recall while
   living on SSD.
3. *"How do you delete a vector from an HNSW index?"* -- you don't, natively.
   Tombstone it (mark deleted, filter it out of search results) and periodically
   rebuild the index to actually reclaim the graph structure and memory.
