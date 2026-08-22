# Vector Index Internals: HNSW, IVF-PQ, ScaNN, DiskANN

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 3h · **Prereqs:** 01-chunking, basic linear algebra (dot product, L2 distance) · **Updated:** 2026-07-26
> **Module id:** `T06-vector-index-internals` · **Tags:** sprint, retrieval, critical

## The 30-second version

Exact k-NN is O(N) per query and doesn't survive past a few hundred thousand vectors at interactive latency, so every production vector store trades recall for speed with an approximate index. HNSW builds a multi-layer graph of shortcuts — sparse "express lanes" on top, dense connectivity at the bottom — and searches by greedily descending layers; its three knobs (`M`, `efConstruction`, `efSearch`) each trade recall against memory, build time, or query latency in a different place. IVF-PQ instead clusters the space into `nlist` cells and compresses vectors with product quantization, trading a real, measurable amount of recall for an order-of-magnitude memory reduction, which is why it's the answer when the index doesn't fit in RAM. ScaNN and DiskANN are the two specialized answers to "HNSW doesn't fit my constraints" — ScaNN when you need better recall-per-byte via anisotropic quantization tuned for MIPS, DiskANN when the corpus is too big for RAM at all and needs to live on SSD. Filtered search is the problem everyone underestimates: none of these indexes were built with metadata filtering in mind, and bolting a filter on after the fact either degrades to brute force (pre-filter) or silently under-returns results (naive post-filter) — real systems need filter-aware graph traversal to avoid both.

## Why this gets asked

The interviewer has been paged because p99 latency doubled after the index grew from 1M to 10M vectors, or because recall silently dropped after someone "optimized" `efSearch` down for cost without re-running an eval, or because a metadata filter that used to return instantly now scans the whole corpus. They want to know whether you understand these systems well enough to reason about a regression from first principles — the graph topology, the quantization error, the memory layout — rather than just knowing which library to import.

---

## Lineage: past → present → future

**What came before.** Exact nearest neighbor search — brute-force distance computation against every vector, or classical space-partitioning trees (KD-trees, ball trees) — worked fine in the low-dimensional era of computer vision features (SIFT, 128-D) but collapses in high dimensions: KD-trees degrade toward brute force once dimensionality exceeds roughly 20, a phenomenon informally called the curse of dimensionality, because in high-D space every partition boundary ends up close to every point. Locality-Sensitive Hashing (LSH, Indyk & Motwani, 1998) was the first widely-deployed approximate answer, hashing similar vectors into the same buckets probabilistically, but it needed many hash tables to reach good recall and its memory cost grew accordingly. The real inflection point was graph-based ANN: NSW (Navigable Small World, Malkov et al., 2014) showed you could build a graph where greedy routing reliably finds near-neighbors in logarithmic hops, and HNSW (Malkov & Yashunin, 2016/2018) added the hierarchical layering that made both build and search practical at scale.

**Where it stands now.** HNSW is the default in-memory index across nearly every vector database (pgvector, Weaviate, Qdrant, Milvus, hnswlib) because it gives excellent recall-per-latency when the graph fits in RAM. Where it doesn't fit — corpora past roughly 50–100M vectors at typical embedding dimensions — IVF-PQ (Faiss) and its descendants trade recall for an order of magnitude less memory via product quantization, and DiskANN (Microsoft, NeurIPS 2019) goes further, keeping only a compressed sketch in RAM and the full graph plus vectors on SSD, reaching billion-scale on a single machine. ScaNN (Google Research, 2020) occupies a middle position: better recall-per-byte than naive PQ via anisotropic quantization tuned for the actual downstream similarity metric, used heavily inside Google's own Vertex AI Vector Search. The live disagreement is less about which algorithm wins in isolation and more about **filtered search**: HNSW, IVF, and DiskANN were all designed assuming every indexed vector is a valid search target, and production systems almost always need "search these vectors AND tenant_id = X," which none of these algorithms handle natively. Weaviate's ACORN, Qdrant's filterable HNSW, and Pinecone's merged index each answer this differently, and there is no settled consensus on the right general solution.

**Where it's heading.** Filter-aware graph construction (ACORN-style multi-hop expansion, built into Weaviate as the default filter strategy since v1.34) is real and shipping, and more vector databases are expected to adopt some variant — moderate-to-high confidence. Disk-based and RAM-compressed indexes (DiskANN-style) are becoming the default answer for cost-sensitive billion-scale deployments as embedding corpora keep growing faster than RAM budgets — high confidence, already the pattern at that scale. More speculative: hardware-aware indexes co-designed with GPU memory hierarchies (rather than ported from CPU-era designs) and learned indexes that replace hand-designed graph/quantization structures with small trained models — both exist in research prototypes but neither is a settled production pattern as of mid-2026.

---

## Mental model

HNSW as a layered skip list over a similarity graph — sparse express lanes on top, dense local connectivity at the bottom:

```
Layer 2:        A ─────────────────────── F              (few nodes, long hops)
                 │                         │
Layer 1:        A ──── C ──── D ────────── F              (more nodes, medium hops)
                 │      │      │            │
Layer 0:  A─B─C─D─E─F─G─H─I─J─K─L─M─N─O─P─Q─R    (ALL nodes, dense local edges)

  search: start at entry point (top layer) → greedily move to the neighbor
  closest to the query at each layer → drop down a layer when no closer
  neighbor exists at the current one → at layer 0, expand a beam of
  width efSearch before returning the top-k
```

Every node exists at layer 0. A node's probability of also appearing at higher layers decays exponentially (`level ~ floor(-ln(uniform()) * 1/ln(M))`), so higher layers are a sparse "highway system" that gets you close to the target region in few hops, and layer 0 is the dense "surface streets" that refine the answer.

IVF-PQ as a filing-cabinet analogy: `nlist` centroids are the drawers (coarse partition via k-means), `nprobe` is how many drawers you actually open per query, and product quantization is compressing each folder's contents into a short compressed code so more folders fit in the cabinet — at the cost of not being able to read the exact original document, only an approximation reconstructed from the code.

---

## How it actually works

### HNSW: layers, M, efConstruction, efSearch

**Construction.** For each incoming vector, sample an insertion level via `level = floor(-ln(U(0,1)) * mL)` where `mL = 1/ln(M)` — this is what makes higher layers exponentially sparser. At each layer from the sampled level down to 0, run a greedy search from the current entry point using a candidate list of size `efConstruction`, then connect the new node to its `M` nearest found neighbors (layer 0 uses `2*M` connections, since it carries all search traffic and benefits from denser local connectivity).

**Search.** Start at the top layer's single entry point, greedily move to whichever neighbor is closest to the query, drop a layer whenever no neighbor is closer than the current node, and at layer 0 expand a beam of `efSearch` candidates before returning the top-`k` by distance.

**What each knob trades:**

| Knob | Effect of increasing it | Cost |
|---|---|---|
| `M` (max connections per node) | Higher recall, better graph connectivity | More memory (each edge stored per node), slower build, marginally slower search (more distance computations per hop) |
| `efConstruction` (candidate list size at build time) | Higher recall (fewer greedy local optima baked into the graph) | Slower index build only — no query-time cost |
| `efSearch` (beam width at query time) | Higher recall, monotonically, until it saturates near-exact | Query latency increases roughly linearly with `efSearch`; must be `>= k` |

Defaults actually shipped: pgvector's HNSW defaults are `m=16`, `ef_construction=64`, `hnsw.ef_search=40`. Weaviate's compiled defaults are `DefaultMaxConnections=32` (lowered from an earlier default of 64), `DefaultEFConstruction=128`, and a **dynamic** search-time `ef` by default (`ef=-1` meaning "let Weaviate pick," computed from `dynamicEfMin=100`, `dynamicEfMax=500`, `dynamicEfFactor=8` — the effective ef is `query_limit * dynamicEfFactor`, clamped to `[dynamicEfMin, dynamicEfMax]`). The community-converged production starting point for 1536-dimension embeddings is `m=16`, `ef_construction=128–200`, tuned further against a recall@k eval.

**Memory math — know this cold.** The standard estimate (used by OpenSearch, and structurally the same one pgvector's own memory-estimation issue threads converge on) is:

```
bytes_per_vector ≈ 1.1 * (4 * dim + 8 * M)
```

`4 * dim` is the raw float32 vector storage; `8 * M` is the graph edges (8 bytes per neighbor pointer, `M` of them, as an amortized average across layers); `1.1` is a ~10% structural overhead factor.

Worked example, **10 million vectors**:

| dim | M | bytes/vector | Total |
|---|---|---|---|
| 768 (e.g. BGE-base) | 16 | 1.1 × (3072 + 128) = 3,520 | 35.2 GB |
| 1536 (e.g. OpenAI text-embedding-3-large, Voyage) | 16 | 1.1 × (6144 + 128) = 6,899 | 69.0 GB |

This is why a 10M-vector, 1536-dim HNSW index needs roughly 64–70 GB of RAM to build without spilling to disk — and why `maintenance_work_mem` (pgvector) or the equivalent build-memory setting matters: build the graph outside RAM and it runs 10–50x slower.

### IVF-PQ: nlist, nprobe, product quantization

**Coarse quantization (IVF).** Run k-means over a training sample to produce `nlist` centroids, partitioning the space into Voronoi cells. Each vector is assigned to its nearest centroid's inverted list. Rule of thumb: `nlist ≈ sqrt(N)`; too small and every probe touches too many vectors (slow), too large and clusters become sparse and k-means training noisier.

**Search.** Compute distance from the query to all `nlist` centroids, then only search inside the `nprobe` closest cells. Higher `nprobe` → strictly more recall, strictly more latency, since it's a direct control over how much of the corpus you actually inspect. Rule of thumb starting point: `nprobe = 8–16` for 1–10M vectors, then increase until recall plateaus on your eval.

**Product quantization (the "PQ" in IVF-PQ).** Split each vector into `m` sub-vectors, and quantize each sub-vector independently against its own codebook of `2^nbits` centroids (typically `nbits=8`, i.e. 256 centroids per subspace, trained via k-means on that subspace alone). Store only the codebook index per subspace — `m` bytes total per vector, instead of `4 * dim` bytes for the raw float32 vector. Example: a 768-dim vector at `m=96` subquantizers compresses from 3,072 bytes to 96 bytes, roughly **32x compression**; product quantization overall is commonly cited as compressing vectors by around 97%.

**The accuracy cost.** PQ approximates each sub-vector by its nearest codebook centroid, so every stored vector is lossy from the moment it's indexed — distance computations at search time (asymmetric distance computation, comparing the raw query against precomputed per-subspace lookup tables) are themselves approximate. This quantization error is a hard ceiling: no amount of `nprobe` tuning recovers accuracy lost to PQ, because the error is baked into storage, not search breadth. Composite IVF+PQ indexes report roughly 16.5x additional speedup from PQ's cheaper distance computation on top of IVF's pruning, for a combined ~92x speedup over flat search — the price is exactly this quantization error, which is why IVF-PQ is the wrong choice whenever you need very high recall and can afford flat or HNSW instead.

### ScaNN: anisotropic vector quantization

Google's ScaNN (Guo et al., 2020) improves on plain PQ by changing *what the quantization loss function optimizes for*. Standard PQ minimizes reconstruction error uniformly in all directions, which is the wrong objective for downstream similarity search (dot product / MIPS) — it wastes quantization precision on components of the error that don't affect ranking. Anisotropic quantization instead penalizes error *parallel* to the database vector more heavily than error orthogonal to it, because parallel error is what actually shifts a vector's rank relative to a query. Architecturally, ScaNN runs three stages: partitioning (coarse, IVF-like), score-aware quantization (the anisotropic step), and a final rerank pass over a small candidate set using exact distances. This gives PQ's memory and speed advantages without PQ's characteristic accuracy ceiling on ranking-sensitive tasks.

### DiskANN: Vamana graph on SSD

DiskANN (Subramanya et al., NeurIPS 2019) targets the case IVF-PQ and HNSW both fail: a corpus too large for either RAM-resident vectors or a RAM-resident graph. It introduces **Vamana**, a single-layer (not hierarchical, unlike HNSW) directed graph built via a randomized initial graph plus two-pass "robust pruning" that keeps the graph sparse while still well-connected, using a pruning parameter α (typically ~1.2) that controls the tradeoff between graph diameter and edge count.

**Layout.** PQ-compressed vectors are cached in RAM for fast approximate first-pass distance estimates that guide the greedy search; the full-precision vectors and the Vamana graph adjacency both live on SSD, laid out so a single disk read for a node returns both its vector and its neighbor list together. On the billion-point SIFT1B benchmark, DiskANN reports serving over 5,000 queries/second at under 3ms mean latency with 95%+ recall@1 on a 16-core machine with 64GB of RAM — a corpus that would need roughly 4–5x that RAM as a pure in-memory HNSW index at typical embedding dimensions.

### The filtered-search problem

Every one of the above indexes assumes any indexed vector is a valid answer. Production queries are almost always "nearest neighbors WHERE tenant_id = X AND status = 'active'," and this breaks both naive strategies:

- **Pre-filtering** (apply the filter first, then search only the matching subset) has no index over the filtered subset specifically, so it typically degenerates into a brute-force scan — you lose the ANN speedup entirely, and the cost scales with how many documents match the filter, not with corpus size.
- **Post-filtering** (run the ANN search first, then discard results that fail the filter) is fast but can silently under-return: if the filter is selective (say 1% of the corpus matches) and you retrieve the unfiltered top-`k`, you may get zero to a handful of results that pass the filter, even though hundreds of valid matches exist elsewhere in the corpus — the greedy graph search has no way to know it should route toward filter-valid regions.

The deeper reason this is hard: HNSW's greedy descent stays inside "good" recall territory by hopping through the *nearest unfiltered* neighbors at each step. Restricting which nodes count as valid can strand the search in a region of the graph with no direct path to any filter-valid node, especially under low selectivity, because the graph's edges were never built with the filter in mind.

Real fixes are filter-aware traversal, not a filter bolted on after search: Weaviate's **ACORN** does two-hop graph expansion so the search radius covers enough of the graph to find filter-valid neighbors regardless of selectivity, and — as of Weaviate v1.34 — automatically chooses between multi-hop exploration (selective filters), a relaxed broader traversal (broad filters), or a flat brute-force scan (tiny result sets) at query time. Qdrant ships a filterable HNSW with its own adaptive query planner. Pinecone merges the metadata and vector indexes into one structure and defaults to post-filtering, which is faster on average but carries the under-return risk on highly selective filters described above.

---

## Build it from scratch

A minimal, single-layer greedy-graph search — enough to see the mechanics; production HNSW needs the multi-layer structure and proper insertion/pruning logic (`hnswlib` is the reference implementation to read next).

```python
# untested sketch — single-layer approximation of HNSW's search step
import heapq
import numpy as np

class TinyGraphIndex:
    def __init__(self, m: int = 16):
        self.m = m
        self.vectors: dict[int, np.ndarray] = {}
        self.edges: dict[int, list[int]] = {}
        self.entry_point: int | None = None

    def _dist(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b))

    def insert(self, node_id: int, vec: np.ndarray, ef_construction: int = 64):
        self.vectors[node_id] = vec
        if self.entry_point is None:
            self.entry_point = node_id
            self.edges[node_id] = []
            return
        candidates = self._search(vec, ef_construction)
        neighbors = [nid for nid, _ in sorted(candidates, key=lambda x: x[1])[: self.m]]
        self.edges[node_id] = neighbors
        for nid in neighbors:
            self.edges.setdefault(nid, []).append(node_id)
            # in real HNSW: re-prune nid's edge list back down to M if it now exceeds it

    def _search(self, query: np.ndarray, ef: int) -> list[tuple[int, float]]:
        visited = {self.entry_point}
        candidates = [(self._dist(query, self.vectors[self.entry_point]), self.entry_point)]
        heapq.heapify(candidates)
        results = list(candidates)
        while candidates:
            dist, node = heapq.heappop(candidates)
            if len(results) >= ef and dist > max(d for d, _ in results):
                break
            for neighbor in self.edges.get(node, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                d = self._dist(query, self.vectors[neighbor])
                heapq.heappush(candidates, (d, neighbor))
                results.append((d, neighbor))
        return [(nid, d) for d, nid in results]

    def search(self, query: np.ndarray, k: int, ef_search: int = 40) -> list[int]:
        results = self._search(query, max(ef_search, k))
        return [nid for nid, _ in sorted(results, key=lambda x: x[1])[:k]]
```

The three things a real implementation adds that this sketch skips: the hierarchical layer structure (so search doesn't start from an arbitrary point in a huge flat graph), edge pruning when a node's neighbor list exceeds `M` (heuristic pruning that keeps diverse rather than merely close neighbors), and layer-0's `2*M` connection budget.

---

## How it's done in production

**Faiss** (Meta) — the reference library for IVF, PQ, and their composites; most other systems either wrap it or reimplement its algorithms. **hnswlib** — the reference standalone HNSW implementation most vector databases build on or benchmark against. **pgvector** — HNSW and IVFFlat inside Postgres; simplest to operate if you're already on Postgres, at the cost of being slower to build than a dedicated vector database at very large scale. **Weaviate** — HNSW with ACORN filtered search, PQ/BQ compression options. **Qdrant** — filterable HNSW with an adaptive planner. **Milvus** — supports HNSW, IVF-PQ, DiskANN, and ScaNN-style indexes behind one interface, letting you pick per-collection. **DiskANN** — used inside Microsoft's own Vespa/Azure offerings for billion-scale, disk-resident search. **ScaNN** — Google-maintained, powers Vertex AI Vector Search.

| Symptom | Cause | Fix |
|---|---|---|
| Recall drops from ~95% to ~60% after 10x data growth with unchanged `efSearch`/`nprobe` | Search-time parameter didn't scale with corpus size — same beam width now covers a proportionally smaller fraction of the graph/index | Re-tune `efSearch`/`nprobe` against a fresh eval at the new scale; don't assume old settings still hold |
| HNSW index build takes hours or OOMs | Build-time memory setting too low (pgvector's `maintenance_work_mem` defaults to 64MB), forcing a disk-based build | Raise the build-memory setting to fit the whole graph, per the memory math above |
| Filtered query returns far fewer than `k` results despite many matches existing | Naive post-filtering: unfiltered top-k retrieved first, then filtered down, under-fetching on selective filters | Oversample before filtering, or move to a filter-aware index (ACORN, filterable HNSW) |
| p99 latency spikes under concurrent writes | HNSW graph mutation requires locking during insert/prune, contending with concurrent reads | Batch inserts, use read replicas, or switch to an index better suited to high write throughput (IVF, LSM-based approaches) |
| Index footprint 3-4x larger than expected | Storing raw float32 vectors with no quantization when the memory budget assumed PQ/scalar quantization | Apply product or scalar quantization; verify actual bytes/vector against the formula above |
| IVF-PQ recall plateaus well below the target no matter how high `nprobe` goes | Quantization error is the ceiling, not search breadth — `nprobe` only controls how much of the (already lossy) index you search | Reduce PQ's compression ratio (more subspaces / more bits), or drop PQ and use HNSW/flat if recall requirement is strict |

---

## Tradeoffs & when NOT to use it

- **HNSW is the wrong choice for extremely write-heavy or streaming corpora.** Graph mutation under concurrent insert/delete contends for locks, and HNSW has no true delete — deleted vectors are typically tombstoned, not removed, degrading the graph over time until a rebuild. High-churn workloads are often better served by IVF or an LSM-tree-style approach with periodic compaction.
- **IVF-PQ is the wrong choice when you need high recall and the raw data fits in RAM anyway.** The quantization error is a hard ceiling on accuracy that no amount of tuning removes; if you can afford flat or HNSW, don't pay PQ's accuracy cost for a memory savings you didn't need.
- **DiskANN is the wrong choice for small corpora.** Its disk-layout and PQ-cache machinery carries real overhead that isn't worth paying under roughly a million vectors — a plain in-memory HNSW index is both simpler and faster there.
- **ScaNN is the wrong choice outside a Google-ecosystem investment.** It's the right algorithm on paper for MIPS-heavy workloads, but the surrounding tooling and community are thinner than Faiss/HNSW, so operational cost is higher unless you're already on Vertex AI.
- **Never assume any ANN index handles low-selectivity metadata filters well by default.** Test with your actual filter distribution before launch — a filter that matches 50% of the corpus behaves very differently from one that matches 0.1%, and the failure mode (brute-force scan vs. silent under-return) depends on which naive strategy your database defaults to.

---

## Interview questions

### Q1 — Why can't you just do exact k-NN at scale?
**Testing:** baseline motivation for approximate indexes.
**Answer:** Exact k-NN is O(N·dim) per query — every query touches every vector. Past a few hundred thousand vectors, this blows interactive latency budgets even with vectorized distance computation, and it gets strictly worse as the corpus grows. Approximate indexes trade a controlled, measurable amount of recall for sublinear (HNSW: roughly logarithmic hop count) or heavily pruned (IVF: only `nprobe` of `nlist` cells) search.
**Follow-up trap:** *"At what scale does exact search stop being viable?"* — there's no universal number; it depends on dimension, hardware, and latency budget. A defensible answer names the tradeoff and says you'd measure it, not quote a memorized threshold.

### Q2 — Explain HNSW's layer structure and why it's hierarchical.
**Answer:** Every vector exists at layer 0; a node's presence at higher layers is sampled with exponentially decaying probability (`level ~ floor(-ln(U)) * 1/ln(M)`), so higher layers are sparse. Search starts at the top layer's entry point and greedily descends, using higher layers to travel long distances in few hops and layer 0 for fine-grained local refinement — this is what gives HNSW its near-logarithmic search behavior instead of a flat linear scan of one giant graph.
**Follow-up trap:** *"Is search actually O(log N)?"* — it's empirically close to logarithmic in practice, but it's a graph-routing heuristic, not a proven worst-case bound the way a balanced tree's height is; don't overclaim it as a guaranteed complexity.

### Q3 — What do `M`, `efConstruction`, and `efSearch` each control, and what does raising each one cost?
**Answer:** `M` is the max edges per node — higher improves recall and connectivity but costs memory (roughly `8*M` bytes/vector in the graph) and build/search time. `efConstruction` is the candidate list size during graph building — higher improves recall by avoiding local optima baked into the graph, costing only build time, not query latency. `efSearch` is the query-time beam width — higher improves recall roughly monotonically at a roughly linear query-latency cost, and must be at least `k`.
**Follow-up trap:** *"Which one would you tune first in production if recall dropped?"* — `efSearch`, because it's a runtime knob with no rebuild required; `M` and `efConstruction` require reindexing to change.

### Q4 — Walk me through the memory math for a 10M-vector HNSW index at 768 dimensions with M=16.
**Answer:** `bytes_per_vector ≈ 1.1 * (4*768 + 8*16) = 1.1 * (3072 + 128) = 3,520 bytes`. At 10M vectors, that's 35.2 GB. Doubling the dimension to 1536 nearly doubles the total to about 69 GB, because vector storage dominates the formula — the graph edges (`8*M`) are a small fraction of the total at typical `M` values.
**Follow-up trap:** *"Does raising M matter much for memory at that scale?"* — not proportionally as much as you'd think, since `4*dim` usually dwarfs `8*M` for common embedding dimensions (768–1536) and reasonable `M` (8–48); the bigger memory lever is the embedding dimension itself, or applying quantization.

### Q5 — Explain IVF-PQ: what do `nlist` and `nprobe` do, and how does product quantization work?
**Answer:** `nlist` is the number of k-means centroids partitioning the space into cells (inverted lists); `nprobe` is how many of those cells you actually search per query, directly trading recall for latency. Product quantization splits each vector into `m` sub-vectors and quantizes each against its own small codebook (typically 256 centroids, `nbits=8`), storing only the codebook index per subspace — this shrinks a vector from `4*dim` bytes to `m` bytes, often 20-30x compression.
**Follow-up trap:** *"If recall is too low, do you raise nprobe or the PQ parameters?"* — depends on the cause: if recall plateaus well below target regardless of `nprobe`, the ceiling is quantization error, and you need to reduce PQ's compression (more subspaces/bits), not raise `nprobe` further.

### Q6 — What's the accuracy cost of product quantization, specifically?
**Answer:** Every stored vector is replaced by the nearest centroid in each subspace's codebook, so the stored representation is lossy from the moment of indexing — this is a fixed quantization error baked into the data, independent of how thoroughly you search. Distance computations at query time are themselves approximate, using precomputed per-subspace lookup tables (asymmetric distance computation) rather than exact float distances.
**Follow-up trap:** *"Can you eliminate this error by increasing nprobe?"* — no, `nprobe` controls how much of the (already-quantized) index you search, not the precision of what's stored; conflating the two is a common mistake interviewers listen for.

### Q7 — What does ScaNN do differently from plain PQ?
**Answer:** ScaNN uses anisotropic vector quantization: instead of minimizing uniform reconstruction error, it penalizes quantization error that's parallel to the database vector more heavily than error orthogonal to it, because parallel error is what actually shifts a vector's rank under the downstream similarity metric (particularly MIPS/dot product). This gives better recall-per-byte than standard PQ for ranking-sensitive tasks.
**Follow-up trap:** *"Would you recommend ScaNN outside Google's stack?"* — only if the operational cost of a less mature ecosystem (compared to Faiss/HNSW) is worth the recall-per-byte gain for your specific workload; otherwise say plainly that Faiss/HNSW's tooling maturity usually wins.

### Q8 — How does DiskANN achieve billion-scale search on a single machine with limited RAM?
**Answer:** It builds a single-layer Vamana graph (not hierarchical like HNSW) via randomized initialization plus two-pass robust pruning, keeps only PQ-compressed vectors in RAM for fast approximate first-pass distance estimates, and stores the full-precision vectors plus the graph adjacency together on SSD so a single disk read per hop returns both. On SIFT1B it reports 5,000+ QPS at under 3ms mean latency with 95%+ recall@1 on a 16-core, 64GB-RAM machine — a corpus that would need far more RAM as pure in-memory HNSW.
**Follow-up trap:** *"When would you NOT use DiskANN?"* — small corpora (well under a million vectors), where its disk-layout overhead isn't justified and in-memory HNSW is both simpler and faster.

### Q9 — Why is filtered vector search "genuinely hard" rather than a simple engineering detail?
**Answer:** Every ANN index (HNSW's graph, IVF's inverted lists) is built assuming any indexed vector is a valid target. A metadata filter restricts which nodes count as valid at query time, but the index's connectivity or partitioning was never built with that restriction in mind. Pre-filtering falls back to brute force over the filtered subset (losing the index's speedup entirely); naive post-filtering retrieves the unfiltered top-k and then filters, which under selective filters can return far fewer than `k` valid results even when plenty exist elsewhere in the corpus, because the search never routed toward filter-valid regions.
**Follow-up trap:** *"How would you fix it?"* — filter-aware traversal, not a bolt-on filter: Weaviate's ACORN does two-hop graph expansion so the search radius covers enough of the graph regardless of filter selectivity, automatically choosing between multi-hop exploration, broader relaxed traversal, or flat scan depending on filter selectivity and result-set size.

### Q10 — Pre-filter vs. post-filter: what specifically breaks with each, and when would you pick one over the other?
**Answer:** Pre-filter breaks on low-selectivity filters (few matches) by degenerating to brute force over a potentially large filtered subset if there's no index over that subset. Post-filter breaks on high-selectivity filters (rare matches) by under-returning, since the unfiltered ANN search may not surface enough filter-valid candidates in its top-k. Post-filter is fine when the filter is broad (most vectors pass); pre-filter (or a proper filter-aware index) is needed when the filter is narrow.
**Follow-up trap:** *"What does Pinecone do by default, and is that always right?"* — Pinecone defaults to post-filtering with a merged metadata/vector index for speed; that's the wrong default for highly selective filters, and you should say so rather than assume the vendor default is universally correct.

### Q11 — How would you choose between HNSW, IVF-PQ, and DiskANN for a given deployment?
**Answer:** If the graph fits comfortably in RAM and recall is the priority, HNSW. If the corpus is large enough that memory is the binding constraint but some recall loss is acceptable, IVF-PQ. If the corpus is too large for RAM even with compression — billions of vectors — DiskANN's disk-resident design. The decision is really a memory-budget-vs-recall-target tradeoff, sized against the actual corpus, not a fixed rule of thumb.
**Follow-up trap:** *"What about ScaNN?"* — a specialized answer when you're already invested in the Google/Vertex AI ecosystem and need better recall-per-byte than PQ for MIPS-style similarity; not a general-purpose default.

### Q12 — Can you delete a vector from an HNSW index?
**Answer:** Not cleanly. Most implementations tombstone deleted vectors (mark them as deleted, exclude them from results) rather than physically removing them and their edges, because removing a node requires re-linking its neighbors, which is expensive to do correctly online. Over time, heavy delete/update churn degrades graph quality until a rebuild is needed.
**Follow-up trap:** *"How would you handle a high-churn corpus, then?"* — either periodic full rebuilds, or switch to an index structure better suited to churn (IVF with periodic re-clustering, or an LSM-style layered approach with compaction).

### Q13 — Your team wants 99%+ recall from an IVF-PQ index and it's not achievable no matter how you tune `nprobe`. What do you tell them?
**Answer:** That the ceiling is quantization error, not search breadth, and no `nprobe` setting fixes a lossy stored representation — the fix is reducing PQ's compression (more subspaces or bits, trading back some of the memory savings) or abandoning PQ for flat/HNSW if the recall requirement is truly non-negotiable and the memory budget can absorb it.
**Follow-up trap:** *"Is there a middle ground?"* — yes: IVF with a milder PQ configuration, or IVF combined with a small exact-rerank pass over the top candidates from the coarse+PQ search, recovering some accuracy at a bounded extra cost.

### Q14 — How would you diagnose a sudden latency spike in a production vector search service?
**Answer:** First check whether corpus size grew without a corresponding re-tune of `efSearch`/`nprobe` — the most common silent cause. Then check for concurrent write contention against the index (HNSW graph locking). Then check whether a metadata filter's selectivity changed (new tenant with a much smaller or larger dataset shifting from post-filter-friendly to pre-filter-forced brute force). Only after ruling those out would I suspect infrastructure (disk I/O for DiskANN-style indexes, network for a remote vector database).
**Follow-up trap:** *"What's the first metric you'd pull, concretely?"* — recall alongside latency, not latency alone; a latency spike with unchanged recall points to infrastructure, while a latency spike with dropped recall points to a parameter or filter-selectivity change.

### Q15 — Design the vector index strategy for a multi-tenant SaaS product where each tenant has a private, filtered subset of a shared 50M-vector corpus, and tenant sizes range from 100 to 5 million vectors.
**Testing:** synthesis, and awareness that "one strategy for all tenants" is usually wrong.
**Answer:** This is the filtered-search problem at its worst, because selectivity varies by four orders of magnitude across tenants. A filter-aware index (ACORN-style multi-hop, or Qdrant's filterable HNSW) is close to mandatory rather than optional here, since neither pure pre-filter nor pure post-filter serves both a 100-vector tenant and a 5M-vector tenant well. For the smallest tenants, per-tenant physical partitioning (a separate small index or even a flat scan) may outperform a shared filtered index, since brute force over a few hundred vectors is trivially fast and avoids the shared-index overhead entirely. For the largest tenants, per-tenant HNSW indexes (physical isolation instead of a metadata filter) sidesteps the filtered-search problem altogether at the cost of more indexes to manage. State that "adaptive strategy per tenant size, informed by a query-time selectivity check" is the honest answer, not a single index configuration for everyone.
**Follow-up trap:** *"What's the operational cost of per-tenant physical indexes?"* — many more indexes to build, monitor, and keep warm in memory; this is a real ops tradeoff against the filtered-search complexity you're avoiding, and a senior answer names both sides.

---

## Red flags that fail you

- Claiming HNSW search is a guaranteed O(log N) rather than an empirically near-logarithmic heuristic.
- Not knowing that `efSearch` is a runtime knob and `M`/`efConstruction` require a rebuild.
- Believing raising `nprobe` fixes recall loss caused by product quantization error.
- Treating pre-filtering and post-filtering as equally safe defaults regardless of filter selectivity.
- Not knowing HNSW has no clean delete.
- Recommending ScaNN or DiskANN without naming the specific constraint (recall-per-byte, RAM budget) that justifies the extra operational complexity.
- Sizing an index's memory footprint without doing the arithmetic.

---

## Cheat card

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

## Sources

- [pgvector HNSW indexing — Crunchy Data Blog](https://www.crunchydata.com/blog/hnsw-indexes-with-postgres-and-pgvector) — accessed 2026-07-26
- [pgvector, a guide for DBA — Part 2: Indexes (update March 2026)](https://www.dbi-services.com/blog/pgvector-a-guide-for-dba-part-2-indexes-update-march-2026/) — accessed 2026-07-26
- [Weaviate HNSW `hnsw` package defaults — pkg.go.dev](https://pkg.go.dev/github.com/weaviate/weaviate/entities/vectorindex/hnsw) — accessed 2026-07-26
- [Select & configure vector indexes — Weaviate Documentation](https://docs.weaviate.io/weaviate/tutorials/vector-indexing-deep-dive) — accessed 2026-07-26
- [Guidelines to choose an index — facebookresearch/faiss Wiki](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index) — accessed 2026-07-26
- [Product Quantization: Compressing high-dimensional vectors by 97% — Pinecone](https://www.pinecone.io/learn/series/faiss/product-quantization/) — accessed 2026-07-26
- [Accelerating Large-Scale Inference with Anisotropic Vector Quantization (ScaNN) — alphaXiv](https://www.alphaxiv.org/overview/1908.10396v5) — accessed 2026-07-26
- [DiskANN: A Disk-based ANNS Solution with High Recall and High QPS on Billion-scale Dataset — Zilliz Blog](https://zilliz.com/blog/diskann-a-disk-based-anns-solution-with-high-recall-and-high-qps-on-billion-scale-dataset) — accessed 2026-07-26
- [How we speed up filtered vector search with ACORN — Weaviate](https://weaviate.io/blog/speed-up-filtered-vector-search) — accessed 2026-07-26
- [The Achilles Heel of Vector Search: Filters — Bits & Backprops](https://yudhiesh.github.io/2025/05/09/the-achilles-heel-of-vector-search-filters/) — accessed 2026-07-26
- [Memory-optimized vectors — OpenSearch Documentation](https://docs.opensearch.org/latest/mappings/supported-field-types/knn-memory-optimized/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
