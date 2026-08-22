# Weaviate/Qdrant/Milvus/pgvector/FAISS — and When Vectors Are Wrong

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-vector-db-compare` · **Tags:** vector,critical

## The 30-second version

There is no single best vector database, only a best fit for a specific corpus size, filter shape, and operational budget, and the interview signal is whether you can name the actual axes instead of a vendor's marketing page. Weaviate and Qdrant are full-featured vector databases with native multi-tenancy, hybrid search, and horizontal scaling built in; Milvus is the most distributed-systems-heavy of the group, separating storage from compute Kubernetes-natively for billion-scale workloads at real operational cost; pgvector is Postgres with a vector type and HNSW/IVFFlat indexes bolted on, the right call whenever your vectors already live next to relational data and your corpus is in the low tens of millions, not a compromise you apologize for. FAISS is not a database at all — it is Meta's C++/Python library of ANN algorithms with no persistence, no server, no metadata filtering, and no replication, and it is exactly the right tool the moment you want to own that infrastructure yourself or embed search directly in a process. Memory is the number that actually decides most of these arguments: a naive HNSW index costs roughly `1.1 * (4*dim + 8*M)` bytes per vector before you've stored a single byte of metadata, which is 69 GB of RAM for 10M vectors at 1536 dimensions and M=16, and every "why is this so expensive" production incident traces back to someone not doing that arithmetic before choosing a corpus size and a dimension. The other real failure mode nobody budgets time for is a confidently wrong top result from cosine similarity — usually an embedding-model mismatch between index time and query time, a missing normalization step, or a stale index — which looks like a relevance bug and is actually a plumbing bug.

## Why this gets asked

The interviewer has watched a RAG system either overpay for infrastructure it never needed (a dedicated vector database and a Kubernetes cluster for 200K product descriptions that would have been fine as a Postgres column) or underpay for infrastructure it desperately needed (a single-node pgvector instance choking under a multi-tenant filter workload it was never designed for). They want to know if you reason about vector database choice as a real systems tradeoff — memory, filtering cost, operational burden, consistency model — or if you reach for whichever one was trending on a blog post. If you've actually run Weaviate, ClickHouse HNSW, and pgvector in production, this is the module where that experience either shows or doesn't: can you give the specific number that made you pick one over another, not just the name of the tool you used.

---

## Lineage: past → present → future

**What came before.** Before purpose-built vector databases existed as a product category, embedding-based retrieval either lived inside application code calling FAISS or Annoy directly (Spotify's 2015 library, tree-based, immutable indexes rebuilt in batch) with no server, no persistence layer beyond a file dump, and no query language, or it was bolted onto a general-purpose search engine (Elasticsearch's early `dense_vector` field, brute-force only until version 7.x-era approximate support matured) that treated vectors as a second-class citizen behind a text-search-first architecture. The pain that killed both approaches as production-grade retrieval scaled up: FAISS-in-process gave you no metadata filtering, no multi-tenant isolation, and no operational story beyond "someone owns the rebuild job," while text-search-engines-with-vectors-bolted-on inherited an indexing and query architecture that was never designed around the actual cost model of ANN search (see `T06-vector-index-internals` for why filtering specifically breaks graph-based indexes).

**Where it stands now.** Weaviate, Qdrant, Milvus, and pgvector each answer the same underlying question — "give me a database, not just an index" — from different starting points and with different opinions about what a vector database owes you beyond nearest-neighbor search. Weaviate and Qdrant converged on similar feature sets (native multi-tenancy, hybrid search, filter-aware HNSW) from a vector-database-first design; Milvus converged from a distributed-systems-first design (Kubernetes-native, storage/compute separation, built by Zilliz specifically for billion-scale workloads); pgvector converged from the opposite direction entirely — an extension bolted onto a mature relational database, trading some peak vector-search performance for the entire existing operational, transactional, and query-planning machinery Postgres already has. The live disagreement isn't which one is "best" — it's genuinely workload-dependent and every serious practitioner says so — but where the pgvector-vs-dedicated crossover point actually sits: some production writeups put it as high as 50-100M vectors before HNSW rebuild time and index-build memory become the binding constraint, others draw the line much earlier once filtered multi-tenant query latency is the actual requirement, not raw vector count [pgvector as a Vector Database: Production 2026](https://devstarsj.github.io/2026/06/22/pgvector-postgres-vector-database-production-2026/) — accessed 2026-08-01. What's actually deployed at scale: a genuinely large fraction of production RAG systems run pgvector because the team was already on Postgres and never had a specific, named reason to leave; teams that do reach for Weaviate or Qdrant usually have an actual multi-tenancy or hybrid-search requirement driving it, not corpus size alone.

**Where it's heading.** High confidence: filter-aware ANN (Weaviate's ACORN, Qdrant's filterable HNSW, `T06-metadata-design`) keeps maturing as the default rather than an opt-in, because every production vector query is really a filtered query and vendors that don't solve this lose deals. High confidence: pgvector keeps closing the peak-performance gap (pgvectorscale's StreamingDiskANN, iterative index scans for filtered queries) specifically to push the crossover point further out, because "just use Postgres" is a strong enough default preference that every incremental performance win directly converts teams who'd otherwise have reached for a dedicated store. More speculative: ClickHouse's and other OLAP engines' native vector-search additions (in-house HNSW) competing for the "I already run this system for something else, I get vectors for free" niche the way pgvector does for Postgres-shops — real and shipping, but whether it becomes a genuine third leg of this comparison or stays a minor feature is unsettled as of 2026.

---

## Mental model

```
THE ACTUAL DECISION TREE (not "which one is popular")

  Are vectors ALREADY living next to relational data you query jointly?
        │
        YES ──▶ pgvector, until you can name the SPECIFIC bottleneck
        │        forcing a move (filtered p99 SLA, build-time SLA, >50-100M
        │        vectors) — not "might need to scale later"
        │
        NO
        │
  Do you need a genuine multi-tenant SaaS boundary + hybrid search
  as a first-class, built-in feature?
        │
        YES ──▶ Weaviate (native multi-tenancy, ACORN) or
        │        Qdrant (filterable HNSW, lean ops, strong default for
        │        low-latency filtered RAG)
        │
        NO
        │
  Is the corpus headed toward billion-scale with a team that can run
  Kubernetes-native distributed infra?
        │
        YES ──▶ Milvus / Zilliz Cloud — most scaling headroom, most
        │        operational complexity
        │
        NO
        │
  Do you want to own the infrastructure yourself, embed search directly
  in a process, or need maximum algorithm control (GPU indexes, custom
  quantization)?
        │
        YES ──▶ FAISS — but you are now building the database, not buying one:
                 no persistence, no server, no metadata filter, no
                 replication. Budget for that.

MEMORY IS THE HONEST TIEBREAKER when features look equivalent on paper:
  bytes/vector ≈ 1.1 * (4*dim + 8*M)   [HNSW, raw float32, no quantization]
  10M @ 1536-dim, M=16  →  6,899 B/vec  →  69.0 GB RAM just for the graph
  Every dedicated vector DB pays this. pgvector pays it too — it's algorithm
  math, not a vendor-specific cost. Quantization (PQ, scalar, binary) is
  the lever that actually changes the number, not which product you pick.
```

---

## How it actually works

### The comparison matrix, with real numbers

| Axis | Weaviate | Qdrant | Milvus | pgvector | FAISS |
|---|---|---|---|---|---|
| **What it is** | Purpose-built vector DB, Go | Purpose-built vector DB, Rust | Distributed vector DB, Kubernetes-native, Go/C++ | Postgres extension | C++/Python **library**, not a DB |
| **Index types** | HNSW (default), flat, PQ/BQ compression | HNSW, with on-disk/mmap option | HNSW, IVF-family, DiskANN, ScaNN-style — multiple per collection | HNSW, IVFFlat | IVF, PQ, HNSW (via `IndexHNSWFlat`), OPQ, composite indexes, GPU variants |
| **Filtering** | ACORN multi-hop graph expansion; adaptive strategy selection since v1.34 (`T06-metadata-design`) | Filterable HNSW with adaptive query planner, filters run inside traversal | Filter expression pushed into search; per-collection index choice affects filter cost | `hnsw.iterative_scan`, partial indexes, partitioning for selective filters | None natively — filtering is entirely the caller's problem (pre-select ids, post-filter results) |
| **Hybrid search (dense + sparse/BM25)** | Native, first-class (built-in vectorizers + BM25 fusion) | Native (sparse vector support + fusion) | Supported via multiple index types in one collection | Requires pairing with Postgres full-text search (`tsvector`) manually, real but bolted-on | None — you build fusion yourself |
| **Horizontal scaling** | Yes, clustered mode, single-node also fine | Yes, scales out when needed, comfortable single-node | Most aggressive: compute/storage separation, independently scalable query/data nodes | Vertical only (Postgres read replicas help reads, not a sharded write path) | None — you build sharding yourself |
| **Multi-tenancy** | Native, first-class (explicit per-tenant collections, designed for it) | Payload-field filtering on a tenant key, filter runs inside HNSW | Partition-based tenancy, real but more manual | Row-level (`tenant_id` column) + optional Postgres RLS for defense-in-depth (`T06-metadata-design`) | None — build it yourself |
| **Operational burden** | Moderate — one more stateful service to run, upgrade, back up | Moderate, generally regarded as lean to operate | High — Kubernetes-native, real distributed-systems ops overhead | Low if you already run Postgres — no new service | Zero server ops, but you own persistence, durability, and recovery entirely in application code |
| **Persistence / backup** | Built-in snapshotting | Built-in snapshotting | Built-in, tied to the underlying object storage layer | Postgres's own WAL/backup story — mature, well-understood (`T17-postgres`) | None — you serialize the index yourself, no WAL, no crash recovery |
| **Consistency model** | Eventually consistent across replicas by default | Tunable consistency per query | Tunable, replica-lag-aware reads available | Postgres MVCC — real transactional consistency (`T17-mvcc-isolation`) | N/A — single-process, whatever consistency your own code provides |
| **Lock-in** | Moderate — proprietary query API and schema | Moderate — proprietary API | Higher — more moving parts to migrate off of | Low — it's a Postgres table and a `vector` column, portable SQL | None — it's your code, but you own everything the vendor would have given you |

### Memory math, worked, because this is the number that actually decides budgets

The formula (from `T06-vector-index-internals`, restated because it's the deciding number in most of these tradeoffs): `bytes_per_vector ≈ 1.1 * (4 * dim + 8 * M)`. `4 * dim` is the raw float32 vector; `8 * M` is the HNSW graph edges; `1.1` is structural overhead.

| Corpus | dim | M | bytes/vector | Total (raw, no metadata) |
|---|---|---|---|---|
| 1M | 768 | 16 | 3,520 B | 3.5 GB |
| 10M | 768 | 16 | 3,520 B | 35.2 GB |
| 10M | 1536 | 16 | 6,899 B | 69.0 GB |
| 100M | 1536 | 16 | 6,899 B | 690 GB |

This is not a Weaviate number or a Qdrant number — it's what HNSW costs, full stop, and every vendor pays it unless you apply quantization (scalar quantization roughly halves it, binary quantization or PQ can cut it by 10-30x at a real, measurable recall cost, per `03-vector-index-internals`). The practical consequence: at 100M vectors and 1536 dimensions, uncompressed HNSW wants 690 GB of RAM on one box, which is the point where DiskANN-style disk-resident indexes (Milvus supports this; pgvector does not natively) or aggressive quantization stop being optional.

### pgvector's real case, with the actual reasoning

The honest argument for pgvector is not "it's free" or "it's simpler," it's a specific chain of reasoning: if your vectors already live next to relational data you need to join against in the same query (a product's embedding next to its price, inventory, and category), every dedicated vector database forces you to either duplicate that relational data into the vector store's metadata (denormalization + staleness risk, `T06-metadata-design`) or do an application-side join across two systems (extra round-trip, extra failure mode, extra consistency question). pgvector eliminates that entirely — one query, one transaction, one consistency model, Postgres's actual query planner (`T17-query-planner`) reasoning about the whole thing including the vector predicate.

The crossover reasoning, stated as arithmetic rather than a vibe: HNSW build time and build-memory scale with corpus size regardless of which database wraps the algorithm (`maintenance_work_mem` for pgvector, an equivalent setting everywhere else), so the actual forcing function to leave pgvector is never "vector count" in the abstract, it's one of three concrete, measurable things — (1) index build time exceeding your acceptable maintenance window as the corpus grows (a full rebuild on a large pgvector HNSW index is a real operational event, not a background non-event the way some dedicated stores' incremental builds are), (2) filtered-query p99 latency missing an SLA that a purpose-built filter-aware index (ACORN, filterable HNSW) solves and pgvector's `iterative_scan` doesn't solve well enough at your selectivity, or (3) needing horizontal write scaling pgvector's single-primary architecture doesn't provide. Recent production write-ups put pgvector as viable well past 10M vectors — some report comfortably to 50M+ [PostgreSQL as a Vector Database — pgvector in Production 2026](https://devstarsj.github.io/2026/06/22/pgvector-postgres-vector-database-production-2026/) — accessed 2026-08-01 — which is higher than the older rule-of-thumb "under 10M" some teams still repeat from earlier pgvector versions; the honest position in an interview is to give the *reasoning* (name the three forcing functions above) rather than a single memorized number, because the real threshold moved as pgvector's HNSW implementation, iterative scan, and extensions like pgvectorscale matured, and it will keep moving.

### FAISS is a library, not a database — say so, and say when that's exactly what you want

FAISS gives you index algorithms (Flat, IVF, PQ, HNSW, OPQ, and composites of these, plus GPU-accelerated variants) and nothing else: no server process, no network API, no persistence beyond `faiss.write_index()` dumping a file, no metadata filtering (you filter candidate ids yourself before or after search), no replication, no access control, no multi-tenancy, no crash recovery beyond whatever you build. This is not a limitation to apologize for — it's the correct tool exactly when you want to **own** that infrastructure: embedding ANN search directly inside a single process with no network hop (a recommendation service that needs sub-millisecond in-process lookups), a batch offline pipeline that builds an index once and serves it read-only, a research or benchmarking context where you need to swap index algorithms freely, or a system where you're already building the surrounding database/service layer yourself and just need the ANN kernel. Using FAISS as if it were a database — expecting it to handle concurrent writes, multi-tenant isolation, or durability — is a real, common mistake; the fix is either to reach for a real vector database, or to consciously build (and own) the missing pieces (a write-ahead log, a filtering layer, a replication story) around it.

### Hybrid search: what "hybrid" actually means and why it matters

Hybrid search combines dense vector similarity with sparse lexical matching (BM25 or a learned sparse method like SPLADE), because dense embeddings are weak at exact-match cases pure semantic similarity gets wrong — a product SKU, an error code, a person's name, an acronym — where lexical overlap is a stronger signal than embedding proximity. Weaviate and Qdrant ship fusion (commonly Reciprocal Rank Fusion, RRF) as a native, single-query feature; Milvus supports it via multiple index types in one collection; pgvector requires manually pairing `tsvector`/`tsquery` full-text search with the vector column and fusing scores in application code or a SQL query — real and workable, but it's your fusion logic to write and tune, not a built-in.

### Multi-tenancy: the architectural choice, not just a feature checkbox

Weaviate's native multi-tenancy physically isolates each tenant (a dedicated shard/collection per tenant under a shared management layer), sidestepping the filtered-ANN problem for the tenant boundary entirely — no graph traversal ever has to reconcile "nearest neighbor" against "but only within this tenant's subset" because ineligible vectors were never in the searched index at all. Qdrant and Milvus's payload/partition-based tenancy filters within a shared index, inheriting the pre-filter/post-filter cost tradeoffs `T06-metadata-design` covers in depth. pgvector's tenancy is just a `WHERE tenant_id = ?` predicate on an ordinary column, optionally hardened with Postgres row-level security — cheap to reason about, but subject to the same iterative-scan-or-brute-force tradeoff as any other selective filter on an HNSW index. None of these are strictly "more secure" in the abstract; they're different points on the isolation-vs-operational-cost curve, and the right one depends on your actual tenant-size distribution (`T06-metadata-design` covers the size-skew problem in depth).

### When vectors are the wrong answer entirely

Vector search is a hammer, and not every retrieval problem is a nail:

- **Exact lookup.** "Find the order with this exact ID" or "find the user with this exact email" is a B-tree index lookup, not a nearest-neighbor search — embedding an exact-match field and searching it semantically adds latency, cost, and a category of near-miss bugs (two similar-but-different IDs scoring high similarity) for zero benefit over `WHERE id = ?`.
- **Structured filters as the primary query.** "All orders over $500 placed in the last 7 days by tier-2 customers" is a relational query with no semantic component at all; running it as a heavily-filtered vector search (even a filter-aware one) is strictly worse than a normal indexed SQL query, because you're paying ANN overhead for zero relevance benefit.
- **Small corpora where BM25 wins outright.** Below roughly a few thousand to low tens of thousands of documents, classical lexical search (BM25, Postgres/Elasticsearch full-text) is frequently both faster to stand up and more accurate for keyword-heavy queries than an embedding pipeline, because there's no long-tail semantic-matching benefit to unlock at that scale, and you avoid the entire embedding-model-versioning and index-freshness problem class below.
- **Explainability requirements.** A regulated domain requiring "explain exactly why this result was returned" is poorly served by a 1536-dimension embedding's cosine score, which has no human-readable decomposition; a rules-based or lexical system with traceable match reasons, or a hybrid system where the lexical component carries the explainability burden, is usually the actual answer.

### The failure: cosine similarity returns a confidently wrong top result

This is the vector-search-specific production incident that doesn't look like an infrastructure problem at first — the system is up, latency is fine, and the top result is just wrong, with high confidence. The causes, in the order to check them:

1. **Embedding model mismatch between index time and query time.** The single most common real cause: the corpus was embedded with model version A (or model A entirely), and queries are being embedded with model version B — different models (or even different versions of the same model family) produce vector spaces that are not comparable, so cosine similarity between a query-B vector and a corpus-A vector is measuring nothing meaningful, even though every individual score looks like a plausible float between -1 and 1. This happens silently after a provider deprecates or auto-upgrades a model version, or after a re-embedding migration only partially completes.
2. **Missing or inconsistent normalization.** Cosine similarity is only mathematically equivalent to normalized dot product if both vectors are actually unit-normalized; some embedding models return already-normalized vectors, others don't, and mixing a normalization assumption (using inner-product distance on non-normalized vectors, or applying cosine to vectors that already got L2-normalized once upstream and then again downstream) produces a metric that no longer measures what you think it measures.
3. **Distance-metric mismatch with what the model was trained for.** A model trained and evaluated with cosine/dot-product objectives (contrastive or triplet-loss training that assumes unit-normalized embeddings) can genuinely underperform under L2 distance, and vice versa — the model's training objective and the index's configured distance metric have to match, and this is a configuration setting (per-collection metric choice) that's easy to leave at a database's default without checking it against the actual embedding model's documented metric.
4. **Stale index.** The underlying documents changed, but the index wasn't rebuilt or the relevant vectors weren't re-embedded and re-upserted — the top result is confidently wrong because it's confidently describing content that no longer exists in that form.

**The diagnostic, concretely**: take a handful of query/expected-top-result pairs you know should score highly, embed both with the exact pipeline used at index time (same model, same version, same normalization step), and check the raw cosine score directly — if it isn't close to what you'd expect for genuinely similar content (a sanity check often stated as: embed the same text twice through the identical pipeline and confirm the two embeddings are ~1.0 similar to each other, ruling out nondeterminism or pipeline drift first), the fault is in the embedding pipeline, not the vector database or the ANN algorithm. If that sanity check passes, check the model-version metadata stored alongside the index (you should be storing which embedding model and version produced each vector, specifically to make this diagnosis possible) against the model currently used for queries.

---

## Build it from scratch

A minimal harness that makes the mismatch failure mode concrete and testable — the shape of what you'd actually reach for in an incident.

```python
# untested sketch
import numpy as np

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def diagnose_top_result_mismatch(embed_fn, corpus_text: str, corpus_vector: np.ndarray,
                                   expected_metric: str = "cosine") -> dict:
    """Re-embeds a known corpus item with the CURRENT embedding pipeline and
    compares against the STORED vector for that same item -- if they've
    drifted apart, the index is stale or the embedding pipeline changed
    underneath it, which is the #1 real-world cause of this failure."""
    fresh_vector = embed_fn(corpus_text)
    self_similarity = cosine_sim(fresh_vector, corpus_vector)
    result = {"self_similarity": self_similarity, "verdict": None}
    if self_similarity < 0.98:
        result["verdict"] = (
            "STALE OR MISMATCHED PIPELINE: re-embedding the same source text "
            "no longer produces a near-identical vector to what's stored. "
            "Check embedding model version, normalization step, and whether "
            "this document was re-indexed after a content change."
        )
    else:
        result["verdict"] = "Embedding pipeline is consistent; look elsewhere (distance metric config, filter logic)."
    return result

def check_normalization(vectors: np.ndarray) -> bool:
    """A model that's SUPPOSED to emit unit-normalized vectors should have
    norms all ~1.0. If they're not, either the model doesn't normalize
    (and cosine similarity computed via raw dot product will be wrong) or
    something downstream double-normalized / corrupted the vectors."""
    norms = np.linalg.norm(vectors, axis=1)
    return bool(np.allclose(norms, 1.0, atol=1e-3))
```

This is deliberately small — the real fix is process, not code: version-stamp every stored vector with the embedding model and version that produced it, refuse to compare vectors across model versions silently, and treat a re-embedding migration as a real migration with a validation pass (per the schema-evolution discipline in `T06-metadata-design`), not a background job you fire and forget.

---

## How it's done in production

**Faiss** underlies or is directly wrapped by most other systems' IVF/PQ implementations — it's the reference library, not a competitor to the databases above so much as a substrate several of them build on. **Weaviate** and **Qdrant** are typically deployed as managed cloud offerings or self-hosted Kubernetes/Docker services fronting application code via gRPC/REST. **Milvus** is almost always run via Zilliz Cloud (managed) or a dedicated platform team owning the Kubernetes deployment, given its operational weight. **pgvector** rides entirely on however Postgres itself is operated — RDS/Aurora, Cloud SQL, or self-managed — inheriting that database's existing backup, replication, and monitoring story with zero new infrastructure.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Vector search index build/rebuild takes hours and blocks other Postgres maintenance | pgvector build-time memory (`maintenance_work_mem`) too low, or corpus has grown past the size where a full HNSW rebuild fits your maintenance window | Raise `maintenance_work_mem` to fit the graph (memory math above); if rebuild time keeps growing, that's one of the real forcing functions to consider a dedicated store |
| A dedicated vector database costs far more than expected at a modest corpus size | Chose Weaviate/Qdrant/Milvus for a corpus and query pattern pgvector would have served fine, paying for infrastructure headroom never actually used | Re-run the crossover reasoning: is there a *named*, *measured* bottleneck (filtered p99, build time, horizontal write scaling) or was this precautionary over-provisioning |
| Milvus cluster is a constant operational burden for a team without dedicated platform capacity | Picked the most distributed-systems-heavy option without the team to run it | Move to Qdrant/Weaviate (moderate ops) or pgvector (near-zero new ops) unless billion-scale genuinely requires Milvus's architecture |
| FAISS-based service loses its index on a process restart or crash | FAISS has no persistence layer built in — someone assumed database-like durability from a library | Add explicit `write_index`/`read_index` checkpointing on a schedule, or move to a real vector database if durability requirements were understated |
| Top search result is confidently wrong, latency and infra look fine | Embedding model/version mismatch between index and query time, missing normalization, distance-metric mismatch, or stale index | Run the self-similarity diagnostic (re-embed a known item, compare to stored vector); version-stamp vectors with embedding model+version at write time |
| Multi-tenant shared index performs well for most tenants, badly for a few very large or very small ones | One filtering/tenancy strategy applied uniformly across a skewed tenant-size distribution | Tier the strategy by tenant size (`T06-metadata-design`); don't assume one architecture serves a 100-vector tenant and a 5M-vector tenant equally well |
| Hybrid search on pgvector produces poor relevance compared to a dedicated store's out-of-box hybrid | Manual BM25+vector fusion logic is under-tuned (naive score averaging instead of RRF or a learned fusion weight) | Implement Reciprocal Rank Fusion explicitly rather than raw score blending; tune fusion weights against a real eval set, not defaults |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a dedicated vector database as a default.** If you can't name the specific bottleneck (filtered p99 SLA, build-time SLA, tens-of-millions-plus corpus, need for horizontal write scaling) pgvector doesn't solve, you're paying operational cost for headroom you haven't proven you need.
- **Don't run Milvus without a team that can own Kubernetes-native distributed infrastructure.** Its scaling ceiling is the highest of the group and its operational floor is also the highest — a mismatch between team size and Milvus's operational demands is a common, avoidable source of pain.
- **Don't use FAISS expecting database behavior.** No persistence, no filtering, no replication, no multi-tenancy — every one of those is your code to write if you reach for FAISS; that's correct when you want that control, wrong when you assumed you were getting a database and got a library.
- **Don't trust a vendor's default distance metric without checking it against your embedding model's actual training objective.** A silent metric mismatch (L2 configured, model trained for cosine, or vice versa) produces plausible-looking but degraded relevance with no error thrown anywhere.
- **Don't skip version-stamping vectors with the embedding model that produced them.** Without it, diagnosing "why is the top result suddenly wrong" after a model upgrade or partial re-index becomes far harder than it needs to be — this is cheap to add up front and expensive to reconstruct after the fact.
- **For a corpus under a few thousand to low tens of thousands of documents with keyword-heavy queries, don't default to vector search at all.** BM25/full-text is frequently both simpler and more accurate at that scale, and skips the entire embedding-pipeline-versioning problem class.

---

## Interview questions

### Q1 — Is FAISS a vector database?
**Testing:** baseline distinction, a very common trap.
**Answer:** No — it's a C++/Python library of ANN algorithms (IVF, PQ, HNSW, and composites, with GPU variants) with no server process, no persistence beyond manually serializing an index file, no metadata filtering, no replication, and no multi-tenancy. It's the right tool when you want to own that surrounding infrastructure yourself — an in-process recommendation service, a read-only batch-built index, a research context needing algorithm flexibility — not when you need database-like durability and access control out of the box.
**Follow-up trap:** *"So when would you actually choose FAISS over a real vector database?"* — when you're already building the service layer around it yourself (a single-process system with no need for a network hop), need GPU-accelerated indexes a managed vector DB doesn't expose, or are doing offline/batch index construction where durability and concurrent-write support are simply not requirements.

### Q2 — Walk through the memory math for a 10M-vector, 1536-dimension HNSW index. Does the vendor matter?
**Answer:** `bytes_per_vector ≈ 1.1 * (4*1536 + 8*16) = 6,899 bytes`, so 10M vectors is about 69 GB of RAM for the raw graph, before metadata. This is algorithm math, not a vendor-specific number — Weaviate, Qdrant, Milvus, and pgvector all pay it for uncompressed HNSW. The lever that actually changes the number is quantization (scalar, PQ, binary), not which database you pick.
**Follow-up trap:** *"Does switching from Weaviate to pgvector save memory here?"* — no, not meaningfully for the index itself; both are running essentially the same HNSW algorithm with the same asymptotic memory cost. Any savings would come from choosing a different index type (IVF-PQ) or quantization, which is an algorithm decision available in most of these systems, not a vendor-loyalty decision.

### Q3 — Give the honest reasoning for choosing pgvector over a dedicated vector database, not just "it's simpler."
**Answer:** If vectors already live next to relational data you need to join against in the same query, pgvector eliminates denormalization risk and application-side joins entirely — one transaction, one consistency model, one query planner reasoning about the whole predicate. The crossover to leave it isn't a raw vector count, it's one of three concrete forcing functions: index build/rebuild time exceeding your maintenance window, filtered-query p99 missing an SLA that a filter-aware index would solve, or needing horizontal write scaling pgvector's single-primary architecture doesn't provide.
**Follow-up trap:** *"What vector count would you quote as the crossover?"* — refuse to give a single memorized number; recent production reports put pgvector as viable well past 10M, some to 50M+, and the real threshold has moved as pgvector's HNSW, iterative scan, and extensions like pgvectorscale matured — give the reasoning (the three forcing functions), not a stale rule of thumb.

### Q4 — Compare Weaviate, Qdrant, and Milvus on multi-tenancy specifically.
**Answer:** Weaviate has native multi-tenancy — physically isolated per-tenant collections under a shared management layer, sidestepping the filtered-ANN problem for the tenant boundary entirely. Qdrant filters on an indexed tenant payload field, with the filter running inside HNSW traversal via its adaptive planner. Milvus uses partition-based tenancy, real but more manual to operate than Weaviate's built-in model. None of these is universally "more secure" — they trade isolation strength against operational cost differently, and the right choice depends on your tenant-size distribution.
**Follow-up trap:** *"Which would you pick for a SaaS product with tenants ranging from 100 to 5 million documents?"* — name that a single strategy rarely serves both ends of that skew well (`T06-metadata-design`); Weaviate's native per-tenant isolation is attractive for the largest tenants specifically, but the smallest tenants may be served just as well, more cheaply, by brute-force search within a shared index — a tiered answer, not a single-product answer.

### Q5 — Why does a hybrid dense+sparse search matter, and how does implementing it differ across these systems?
**Answer:** Dense embeddings are weak on exact-match cases — SKUs, error codes, names, acronyms — where lexical overlap is the stronger signal; hybrid search fuses dense similarity with BM25/sparse matching (commonly via Reciprocal Rank Fusion) to cover both. Weaviate and Qdrant ship this as a native, single-query feature; Milvus supports it via multiple index types per collection; pgvector requires manually pairing Postgres full-text search (`tsvector`) with the vector column and fusing scores yourself.
**Follow-up trap:** *"If pgvector requires manual fusion, is that a real disadvantage?"* — yes, concretely: it's more code to write and tune (RRF weighting, not just picking a checkbox), but it's not a capability gap — the fusion logic is well-understood and portable; the cost is engineering time, not a missing feature you can't build.

### Q6 — Your team is running a 200K-document internal search tool and reaches for Milvus. What's your pushback?
**Testing:** the "when NOT to use it" instinct, applied concretely.
**Answer:** At 200K documents, none of Milvus's actual differentiators — Kubernetes-native compute/storage separation, billion-scale headroom — are being used, and the team is paying its full operational cost (a distributed system to run, monitor, and upgrade) for a corpus that would fit comfortably and cheaply in pgvector or even a well-tuned FAISS-backed service. Push back toward naming the actual requirement driving the choice; if there isn't one beyond "vector databases are what people use," that's precautionary over-engineering.
**Follow-up trap:** *"What if they say 'we expect to grow to 50M documents in two years'?"* — ask whether that growth is committed roadmap or aspiration; if it's real and near-term, evaluate whether pgvector (which now handles well past 10M, often 50M+, per current production reports) still covers it before assuming Milvus is required — "might scale later" is not the same evidence bar as "here's the current bottleneck."

### Q7 — A RAG system's top retrieval result is confidently wrong — high similarity score, clearly irrelevant content. Walk through your diagnostic process.
**Testing:** the production failure mode this module centers on.
**Answer:** Check, in order: (1) embedding model/version mismatch between index time and query time — the most common real cause; (2) missing or inconsistent normalization, since cosine similarity assumes unit-normalized vectors; (3) distance-metric mismatch against what the model was actually trained for (cosine/dot-product-trained model queried under L2, or vice versa); (4) a stale index where the underlying document changed but wasn't re-embedded. The concrete diagnostic: re-embed a known corpus item with the current pipeline and compare against the stored vector — if self-similarity isn't near 1.0, the pipeline has drifted, and that's the fault, not the vector database or ANN algorithm.
**Follow-up trap:** *"The self-similarity check passes — the stored and freshly-embedded vectors match closely. Now what?"* — check the index's configured distance metric against the embedding model's documented training objective, and check whether vectors are actually normalized when the metric assumes they are; a metric mismatch produces plausible-but-wrong scores with the pipeline itself completely healthy.

### Q8 — Why is a high-cardinality tenant filter the expensive case across every one of these systems, not just one vendor's implementation detail?
**Answer:** Every HNSW-based system's greedy graph search routes through the nearest *unfiltered* neighbors at each hop; restricting eligibility after the fact (post-filter) can strand the search away from any path to a filter-valid node, and restricting before search (pre-filter) has no index built over an arbitrary filtered subset, degenerating toward brute force. A high-cardinality filter like `tenant_id` makes both failure modes worse because it shrinks the effective valid subset the most (`T06-metadata-design` covers the mechanics in depth) — this is a structural property of graph-based ANN, not something any one vendor implemented poorly.
**Follow-up trap:** *"Does a filter-aware index like ACORN fully solve this?"* — it substantially mitigates it via multi-hop expansion toward filter-valid regions, but doesn't eliminate the underlying tension; extremely selective filters on very large corpora still cost more than an unfiltered search, and physical isolation (per-tenant sharding) remains the only strategy that sidesteps the reconciliation problem entirely, at its own operational cost.

### Q9 — Staff-level: design the vector storage strategy for a platform that starts on pgvector at 500K vectors and is expected to reach 80M vectors with multi-tenant access-control requirements within 18 months.
**Testing:** synthesis across memory math, crossover reasoning, and multi-tenancy design.
**Answer:** Start on pgvector — vectors likely already sit next to relational tenant/ACL data, and 500K is trivially served with room to grow. Instrument, from day one, the three real forcing functions: HNSW rebuild time trend, filtered-query p99 by tenant size, and write throughput ceiling — don't wait for a crisis to start measuring. As the corpus approaches the tens-of-millions range, re-evaluate against actual measured numbers, not the original 80M estimate, since pgvector's viable ceiling has been moving upward with pgvectorscale and iterative-scan improvements. If the ACL requirement is genuinely fine-grained and per-tenant isolation becomes the dominant cost driver rather than raw scale, that argues for Weaviate's native multi-tenancy specifically (isolation as the primary requirement) over Milvus (scale as the primary requirement) — name which axis is actually driving the eventual migration, because they point to different destinations.
**Follow-up trap:** *"What's the risk of waiting for measured bottlenecks instead of pre-migrating early?"* — a late migration under production load pressure is riskier and more rushed than a planned one; the mitigation isn't "migrate early anyway," it's instrumenting the three forcing-function metrics early enough that the migration, when it comes, is planned against real trend lines with lead time, not triggered by an incident.

### Q10 — When is vector search the wrong tool entirely, regardless of which database you'd pick?
**Testing:** the required "when NOT to use it," applied at the retrieval-strategy level, not just the vendor level.
**Answer:** Exact lookups (an order ID, an email address) belong on a B-tree, not embedded and searched semantically. Purely structured, filter-driven queries with no semantic component ("orders over $500 in the last week") are relational queries, and running them as a heavily-filtered vector search adds ANN overhead for zero relevance benefit. Small corpora (low thousands to low tens of thousands of documents) with keyword-heavy queries are frequently served better and more simply by BM25/full-text search. Domains requiring literal explainability of why a result matched are poorly served by an opaque cosine score with no human-readable decomposition.
**Follow-up trap:** *"Isn't hybrid search the answer to all of these — just add BM25 on top?"* — hybrid search helps with the exact-match-inside-a-semantic-corpus case, but it doesn't fix the structured-filter case (that's just SQL) or the explainability case (a fused score is still not a traceable reason) — naming hybrid search as a universal patch instead of recognizing which specific problem it does and doesn't solve is itself a red flag.

---

## Red flags that fail you

- Calling FAISS a "vector database" without qualification.
- Quoting a single memorized pgvector-vs-dedicated crossover number with no reasoning behind it.
- Recommending Milvus for a small corpus without naming the actual scale/distribution requirement that justifies its operational cost.
- Treating "add BM25" as a universal fix for retrieval relevance problems that aren't actually lexical-matching problems.
- Diagnosing a wrong top result as a "bad embedding model" without checking model-version mismatch, normalization, and distance-metric configuration first.
- Not doing the memory-math arithmetic when asked to size an index, or treating it as vendor-specific rather than algorithmic.
- Presenting multi-tenancy strategies as interchangeable regardless of tenant-size distribution.

## Cheat card

```
FAISS           LIBRARY, not a DB: no persistence, no filter, no replication,
                no multi-tenancy. IVF/PQ/HNSW/GPU algorithms only. Right
                choice when you own the surrounding infra yourself.

PGVECTOR        Postgres + vector column + HNSW/IVFFlat. Right when vectors
                live next to relational data. Crossover to leave = a NAMED
                bottleneck (build-time SLA, filtered p99 SLA, horizontal
                write scaling), NOT a raw vector count. Recent reports:
                viable well past 10M, often 50M+.

WEAVIATE        Native multi-tenancy (physical per-tenant isolation), ACORN
                filter-aware HNSW, built-in hybrid search (BM25 fusion).

QDRANT          Filterable HNSW w/ adaptive planner, lean ops, strong
                default for low-latency filtered RAG, native hybrid.

MILVUS          Most distributed: K8s-native, compute/storage separated,
                billion-scale headroom. Highest ops burden of the group.

MEMORY MATH     bytes/vec ~= 1.1*(4*dim + 8*M)  [HNSW, uncompressed]
                10M @ 1536d, M=16 -> 6,899 B/vec -> 69 GB RAM (graph only)
                ALGORITHM math, not vendor-specific. Quantization (scalar/
                PQ/binary) is the real lever, not which product you pick.

WRONG FOR       exact lookup (B-tree, not ANN) · pure structured filters
                (SQL, not ANN) · small keyword-heavy corpora (BM25 wins) ·
                hard explainability requirements (opaque cosine score)

COSINE-WRONG    top result confidently wrong -> check IN ORDER:
                1) embed MODEL/VERSION mismatch index vs query time (most common)
                2) missing/inconsistent NORMALIZATION (cosine needs unit vectors)
                3) DISTANCE-METRIC mismatch vs model's training objective
                4) STALE index (doc changed, vector never re-embedded)
                DIAGNOSE: re-embed a known item fresh, compare to stored
                vector -- self-similarity should be ~1.0 or the pipeline drifted

HYBRID SEARCH   dense+sparse (BM25/SPLADE) fusion via RRF. Native in
                Weaviate/Qdrant/Milvus. Manual (tsvector + app-side fusion)
                in pgvector -- real work, not a missing capability.
```

## Sources

- [pgvector as a Vector Database: pgvector in Production 2026](https://devstarsj.github.io/2026/06/22/pgvector-postgres-vector-database-production-2026/) — accessed 2026-08-01
- [PostgreSQL Vector Search in 2026: pgvector vs pgvectorscale — Building Production RAG Systems](https://devstarsj.github.io/2026/04/04/postgresql-pgvector-pgvectorscale-rag-production-guide-2026/) — accessed 2026-08-01
- [pgvector vs Pinecone vs Qdrant vs Weaviate (2026): Which We Actually Use in Production](https://www.kalviumlabs.ai/blog/vector-databases-compared-pgvector-pinecone-qdrant-weaviate/) — accessed 2026-08-01
- [Qdrant vs Milvus vs Weaviate vs LanceDB: Vector DB Comparison](https://builderai.tools/blog/vector-database-benchmarks-qdrant-milvus-weaviate-lancedb) — accessed 2026-08-01
- [Top 15 vector databases in 2026: A production decision guide from 100+ enterprise deployments](https://medium.com/@pratik-rupareliya/top-15-vector-databases-in-2026-a-production-decision-guide-from-100-enterprise-deployments-dd58a04f51a5) — accessed 2026-08-01
- [In Defense of Cosine Similarity: Normalization Eliminates the Gauge Freedom (arXiv:2602.19393)](https://arxiv.org/pdf/2602.19393) — accessed 2026-08-01
- [Is Cosine-Similarity of Embeddings Really About Similarity? (Steck et al., arXiv:2403.05440)](https://arxiv.org/pdf/2403.05440v1) — accessed 2026-08-01
- `curriculum/06-rag/03-vector-index-internals.md` (`T06-vector-index-internals`) — HNSW/IVF-PQ/ScaNN/DiskANN mechanics and memory-math derivation this module reuses
- `curriculum/06-rag/14-metadata-design.md` (`T06-metadata-design`) — pre/post-filter failure mechanics, multi-tenancy size-skew problem, ACL-in-query requirement

## Changelog
- 2026-08-01 — created
