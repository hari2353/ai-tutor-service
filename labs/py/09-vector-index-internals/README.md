# Lab 09: Vector Index Internals — Brute Force, IVF, Product Quantization

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-vector-index-internals`

**You will build:** exact brute-force cosine search as the recall baseline, an IVF index with a seeded k-means-lite coarse quantizer and `nprobe`-cell pruning, a recall@k harness that measures what IVF trades away, and a toy product quantizer whose distortion you measure instead of assume.

**You will be able to answer:** *"Why does raising `nprobe` recover IVF recall but never PQ recall — and what does each cost?"*

## Setup

```bash
cd labs/py/09-vector-index-internals
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                          # only dependencies
```

## The spec

All vectors are float; cosine similarity throughout (row-normalise once, score with dot products). Everything is seeded — same inputs + same seed → same centroids, same ranking, same recall numbers.

1. **`BruteForce(vecs)`** — exact top-k cosine. `.search(q, k)` returns `[(id, cosine), ...]` best-first, ties broken by lower id. Guards: empty corpus, empty query, dimension mismatch, `k < 1` → `ValueError`.
2. **`IVF(nlist, nprobe, iters=8, seed=0)`** — `.build(vecs)` runs k-means-lite (few Lloyd iterations from sampled init points) on the unit-normalised corpus into `nlist` centroids, assigns vectors to posting lists. `.search(q, k)` scores the query against all centroids, opens only the `nprobe` closest cells, ranks the union of their postings by exact cosine, returns the top-k in `BruteForce` format. Track work done in `.stats["probes_last"]` / `.stats["candidates_last"]`.
3. **Harness** — `make_clusters(n_clusters, per_cluster, dim, seed)`: Gaussian blobs around uniform(-1,1) centres, shuffled. `recall_at_k(true_ids, approx_ids)`: |exact ∩ approx| / |exact|. `recall_harness(vecs, queries, k=10, nlist=16, nprobes=(1,2,4,8,16))`: mean IVF-vs-brute-force recall@k per `nprobe` setting.
4. **`pq_quantize(vecs, m, k_sub=16, iters=8, seed=0)`** — toy product quantizer: split dims into `m` equal subspaces (`dim % m != 0` → `ValueError`), k-means-lite per subspace against `k_sub` centroids, store only the winning codebook index. Returns `PQResult(codes, codebooks, distortion)` where `distortion` is the mean squared reconstruction error; `.reconstruct()` rebuilds the lossy approximation so you can measure the recall drop vs exact search yourself.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference (recall numbers print with `-s`): `pytest tests/ -v -s --solution`

## Stretch goals

1. **ADC distances** — score candidates against PQ codes directly via per-subspace lookup tables (asymmetric distance computation) instead of reconstructing full vectors. Compare recall-per-byte.
2. **Recall–latency curve** — sweep `nprobe` 1..nlist on a bigger synthetic corpus and find the knee. *(Interview: "where do you stop tuning?")*
3. **HNSW-lite** — replace IVF's posting lists with a single-layer greedy graph; compare recall at equal candidate budgets.
4. **Anisotropic loss** — retrain one codebook penalising error parallel to the vector more heavily (ScaNN's idea); does ranking survive better than plain reconstruction error?
