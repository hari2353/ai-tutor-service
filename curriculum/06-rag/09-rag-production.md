# Multi-Tenant, ACL-Aware Retrieval, PII, Zero-Downtime Reindex

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 3h · **Prereqs:** 03-vector-index-internals, 04-hybrid-search, 15-latency-accuracy · **Updated:** 2026-07-28
> **Module id:** `T06-rag-production` · **Tags:** production, critical

## The 30-second version

The hard part of production RAG is never the retrieval algorithm, it's making sure a query only ever sees the documents its caller is authorized to see, at index-query latency, with zero staleness window between a permission being revoked and that revocation taking effect in retrieval. Filtering has to happen at the database layer as a mandatory predicate on every query, never as a post-hoc check in application code, because a single missed filter is a data breach, not a bug ticket. PII has to be handled at ingestion, not at generation, since anything that reaches the vector store is a candidate for retrieval and eventual model output, and redaction after the fact can't un-embed a vector that already encodes the sensitive text. Incremental indexing exists because full reindexing an entire corpus for every new or changed document doesn't scale past a few thousand documents, and it has real failure modes around embedding-model drift between old and new vectors. Zero-downtime migration is the discipline of building the new index in parallel, validating it against a golden query set, and atomically swapping traffic via an alias, never mutating a live index in place. Cost per query is the number that turns "does this architecture work" into "can we afford to run it," and it's dominated by reranker and generation-model tokens, not by the vector search itself, which is usually the cheapest hop in the pipeline.

## Why this gets asked

The interviewer has either shipped a RAG system that leaked tenant B's documents into tenant A's answer because a metadata filter was applied after retrieval instead of during it, or they've watched an embedding-model upgrade go sideways because half the corpus was on the old model's vectors and half on the new one, and cosine similarity between them was meaningless. They want to know whether you think about RAG as a demo (stuff some docs in a vector store, query it) or as a system with security boundaries, staleness guarantees, and an operational migration story — because the demo version of RAG is roughly a day of work, and every company that hires a principal engineer for this already has the demo and is drowning in the parts the demo skipped.

---

## Lineage: past → present → future

**What came before.** Early RAG deployments (2022-2023) were largely single-tenant proofs of concept: one corpus, one vector index, no notion of "whose documents are these." The first production multi-tenant systems bolted access control on as an application-layer filter — retrieve top-k, then discard results the caller isn't allowed to see — which worked at demo scale and broke in exactly two ways once real customers arrived: post-filtering under-returns when a tenant's allowed subset is small relative to the corpus (the same top-k-then-filter problem covered in `T06-vector-index-internals`' filtered-search section, but with security stakes instead of just recall stakes), and worse, any code path that skipped the filter — a new endpoint, a debug script, an agent tool with slightly different plumbing — leaked another tenant's data outright. PII handling followed a similarly naive path: teams ingested raw documents wholesale, reasoning that "the LLM won't repeat it unless asked," which is false — retrieval surfaces the literal chunk containing the PII to the generation step, and the model can and does reproduce it in the response.

**Where it stands now.** The 2026 consensus, converged on independently by security-conscious vector database vendors and practitioner writeups, is that authorization must be enforced as a deterministic, mandatory predicate at the database retrieval layer — filtering happens *during* the ANN search or as a hard pre-filter, never as an optional post-retrieval step in application code. Two architectural patterns dominate: Pinecone-style logical namespace isolation (cheap, flexible, but explicitly a *logical*, not cryptographic, boundary — a misconfigured query can still cross it) and Weaviate-style physical per-tenant sharding (one HNSW graph per tenant, stronger isolation, cold-storable for inactive tenants to control cost, at the price of more index objects to manage and, at the low end, per-shard overhead that makes very small tenants inefficient). Attribute-based access control (ABAC) — filtering on tenant_id plus finer attributes like department or classification level, mirrored into chunk metadata at ingestion and refreshed on permission-change events — has generally superseded simple RBAC as the expressive baseline, because real enterprise permission models are rarely as simple as "user belongs to tenant." PII handling has moved to ingestion-time detection and redaction/tokenization (via tools like Microsoft Presidio or commercial PII scanners) before anything is embedded, on the reasoning that you cannot un-embed a vector once sensitive text is baked into it. Incremental indexing and zero-downtime reindexing (blue-green: build the new index fully in parallel, validate against a benchmark query set, atomically swap an alias) are now treated as required infrastructure, not nice-to-haves, once a corpus is large enough that a full rebuild takes hours.

**Where it's heading.** Real-time permission propagation — closing the window between a permission revocation in the source system (e.g., someone loses access to a Google Drive folder) and that revocation taking effect in the RAG index — is an active area of engineering investment, moving from batch/polling-based ACL sync toward webhook-driven, near-real-time metadata updates; moderate confidence this becomes the default within a couple of years, since the staleness window is a genuine, reported production incident category. Cryptographic tenant isolation inside shared vector indexes (rather than logical namespace or physical shard isolation) is discussed but not a mainstream shipped pattern as of mid-2026 — speculative. Dual-write, dual-embed migration patterns for embedding-model upgrades (maintaining both old and new embedding columns during a transition window, background re-embedding, then cutover) are converging toward a standard playbook across teams independently arriving at the same shape, which is itself informative — high confidence this becomes documented best practice rather than remaining tribal knowledge.

---

## Mental model

Two failure axes, and production RAG has to solve both at once:

```
                    AUTHORIZATION AXIS                    STALENESS AXIS
   ┌─────────────────────────────────────┐   ┌──────────────────────────────────┐
   │ query ──> [MANDATORY tenant/ACL      │   │ permission revoked in source     │
   │            filter, enforced in DB]   │   │ system (t=0)                     │
   │           │                          │   │       │                          │
   │           v                          │   │       v  (propagation delay)     │
   │    only filter-valid vectors         │   │ RAG index still serves old       │
   │    even CONSIDERED by ANN search     │   │ ACL metadata until sync catches  │
   │           │                          │   │ up -- this window is the risk    │
   │           v                          │   │       │                          │
   │    retrieved chunks -> generation    │   │       v                          │
   └─────────────────────────────────────┘   │ webhook/poll updates chunk ACL    │
                                              │ metadata -> window closes        │
                                              └──────────────────────────────────┘

  Get axis 1 wrong: tenant A sees tenant B's data on day one.
  Get axis 2 wrong: a fired employee's RAG access outlives their actual permissions
  by however long your sync lag is.
```

PII sits upstream of both axes — it's a decision made once, at ingestion, about what's even allowed to become a retrievable vector in the first place, independent of who later queries it.

---

## How it actually works

### ACL-aware retrieval: where the filter must live

The wrong architecture retrieves top-k unfiltered, then discards results the caller can't see. This is broken for two independent reasons: it under-returns (per the pre-filter/post-filter analysis in `T06-vector-index-internals` — a highly selective ACL, like "only 3 of 50,000 chunks belong to this tenant," can return zero results after post-filtering even though matches exist), and any code path that forgets to apply the discard step leaks data outright, which is a much worse failure than under-returning.

The correct architecture makes the ACL predicate part of the retrieval query itself, enforced by the storage layer:

- **Metadata-filtered ANN, mandatory.** Every chunk stores `tenant_id` and any finer ABAC attributes (department, classification, document owner) at ingestion time, mirrored from the source system's actual permission model. Every retrieval query includes these as a hard filter passed to the vector database's native filtered search (Weaviate's ACORN-style filter-aware traversal, Qdrant's filterable HNSW, pgvector combined with Postgres row-level security), not as an application-layer discard step.
- **Postgres row-level security (RLS) as a defense-in-depth layer when using pgvector.** `ALTER TABLE documents ENABLE ROW LEVEL SECURITY` plus `FORCE ROW LEVEL SECURITY` means even a buggy application query that forgets to add a `WHERE tenant_id = ...` clause still can't see another tenant's rows, because the database itself enforces the policy regardless of the query shape. This is the single highest-leverage mitigation against the "someone wrote a new code path and forgot the filter" failure mode.
- **Physical isolation (per-tenant shard/index) for the highest-sensitivity tenants or the largest tenants.** Weaviate's multi-tenancy model gives each tenant its own HNSW shard — data literally isn't co-located with another tenant's data in the same graph, which removes an entire class of cross-tenant leak risk at the cost of one more index object per tenant to manage, and per-shard overhead that makes it wasteful for tenants with only a handful of documents. Weaviate mitigates the cost side with cold storage for inactive tenant shards, paging them back in on access rather than keeping every tenant's index warm in memory.
- **Logical namespace isolation (Pinecone-style) as the cheaper default for large tenant counts.** Namespaces are a query-time partition, not a cryptographic boundary — Pinecone documents this explicitly. It scales cheaply to very large tenant counts (100,000+ namespaces on standard plans) but a misconfigured query that omits the namespace parameter, or a query that spans namespaces incorrectly, is a real risk surface that physical sharding doesn't have.

**Noisy-neighbor risk** is the operational side of multi-tenancy that's easy to miss in a security review: without proper isolation, one tenant's heavy query volume or huge corpus can degrade retrieval latency for every other tenant sharing the same underlying shard or index. Physical per-tenant sharding solves this incidentally; shared-index logical partitioning does not, and needs separate rate-limiting or resource-quota work to prevent it.

### PII: detection, timing, and the irreversibility problem

The core fact that makes PII handling different from a typical data-governance problem: once sensitive text is embedded into a vector and indexed, you cannot selectively "un-embed" it. The vector is a lossy but real encoding of that text, and it will be retrieved and handed to a generation model whenever a query is semantically close enough, regardless of any downstream redaction policy applied to the *generated output*. This makes ingestion-time detection and redaction/tokenization the only reliable control point — output-time filtering (scanning the model's response for PII patterns before returning it to the user) is a useful last line of defense but does nothing to prevent the PII from having been retrieved and fed into the model's context in the first place, where it could influence the response even if the literal string gets scrubbed afterward.

Production pattern: run a PII detection pass (Microsoft Presidio or a commercial equivalent — named-entity recognition plus regex/pattern matchers for structured PII like SSNs, credit cards, emails) over every document *before* chunking and embedding. Detected spans are either redacted (replaced with a placeholder token, e.g., `[REDACTED_SSN]`) or tokenized (replaced with a reversible token mapped in a separate, access-controlled store, for cases where an authorized downstream process legitimately needs the real value back). Chunk-level metadata should record whether PII was detected and what category, so retrieval-time policy can additionally restrict PII-containing chunks to a narrower set of authorized callers even beyond the base tenant/ACL filter.

The failure mode to name explicitly: **PII detectors have real, measurable false-negative rates**, especially on less-common PII formats (non-US ID formats, informally-written addresses, PII embedded in unstructured prose rather than structured fields). Treat PII redaction as risk reduction, not a hard guarantee, and combine it with output-time scanning and monitoring rather than relying on ingestion-time redaction alone.

### Incremental indexing

Full reindexing an entire corpus for every document add/update/delete is O(corpus size) work per change and stops scaling once a corpus reaches even moderate size — a few hours of reindex time for a few tens of thousands of documents is common, which is unworkable if documents change continuously. Incremental indexing instead handles each change as a bounded, local operation:

- **Adds.** Embed the new document, insert into the existing index. HNSW supports this natively (each insert runs the same greedy-search-then-connect procedure as initial construction); IVF-PQ needs the new vector assigned to its nearest existing centroid without necessarily re-running k-means (centroids drift stale over time and need periodic, not per-insert, retraining).
- **Updates.** Typically implemented as delete-plus-add rather than in-place vector mutation, since most ANN structures don't support efficient in-place updates.
- **Deletes.** As covered in `T06-vector-index-internals`, most ANN indexes (HNSW in particular) don't support clean deletes — deleted vectors are tombstoned (marked invalid, excluded from results) rather than physically removed, because removing a node and correctly re-linking its neighbors online is expensive. Tombstone accumulation degrades graph quality and search latency over time (search has to walk through and discard tombstoned nodes), which is why periodic compaction or full rebuilds are still necessary on a schedule, just far less frequently than per-change.

**The embedding-model-drift failure mode** is specific to incremental indexing and easy to miss: if you swap embedding models mid-corpus-lifecycle without re-embedding the existing corpus, new documents get vectors from the new model while old documents keep vectors from the old model, and cosine/dot-product similarity between vectors from *different* embedding models is not meaningful — they don't share a geometry. The symptom is silent: retrieval quality degrades gradually and unevenly (queries that should match older documents start missing them, or match them with garbled relevance scores) rather than failing loudly, which makes it easy to ship and only notice weeks later via a slow decline in answer quality metrics.

### Zero-downtime index migration

The unsafe pattern is mutating a live index in place — changing embedding models, chunking strategy, or index parameters (M, efConstruction) by rewriting the existing index while it's still serving traffic. This risks serving partial or inconsistent results mid-migration, and gives no clean rollback path if the new configuration turns out worse.

The safe pattern is blue-green, alias-based:

1. Build the new index (new embedding model, new chunking, new parameters — whatever changed) completely, in parallel, against the *current* corpus snapshot, while the old index keeps serving all live traffic.
2. Validate the new index against a golden query set (a benchmark of representative queries with known-good expected results, ideally covering the accuracy metrics from `T06-rag-eval` and `T06-accuracy-tuning`) before any traffic touches it.
3. Backfill any documents added/changed during the build window (a dual-write period where new documents go to both old and new indexes) so the new index isn't stale relative to the old one at cutover time.
4. Atomically swap an alias or connection string so all queries move from old to new in one step — no query ever sees a partially-built index, and rollback is instant (swap the alias back) if validation in production surfaces a regression the golden set missed.
5. Retain the old index for a bounded rollback window (commonly on the order of 24 hours in reported production practice) before decommissioning it, in case a regression only surfaces under real traffic patterns the golden set didn't cover.

**The dual-column pattern for embedding-model migrations specifically**: rather than a full separate index, some teams maintain both `embedding_v1` and `embedding_v2` columns on the same row during a transition window, background-reembedding the corpus into `embedding_v2` while queries continue against `embedding_v1`, then cutting the query path over once background reembedding completes and validates — functionally the same blue-green discipline, applied at the column level instead of the whole-index level, useful when the underlying storage engine (e.g., pgvector inside an existing Postgres table) makes a fully separate parallel index awkward to stand up.

### Cost per query, decomposed

A representative production RAG query touches, in order: embedding the query (near-negligible cost, a single small embedding call), the vector search itself (fast and cheap — milliseconds, effectively free per query at typical scale), an optional reranking pass over the retrieved candidates (a cross-encoder call over, say, 20-50 candidates — meaningfully more expensive per query than the vector search but still usually a small fraction of a cent), and the generation call (dominant cost — retrieved context tokens plus the question plus the generated answer, at whatever the generation model's per-token price is). For a typical setup retrieving 4-8K tokens of context and generating a few hundred tokens of answer at a mid-tier model's pricing, total cost per query commonly lands in the range of fractions of a cent to a couple of cents — reported real-world budgets for production RAG systems often target sub-$0.01-$0.02 per query, with generation tokens responsible for the large majority of that cost, not retrieval. The practical implication: cost optimization effort belongs on the generation and reranking stages (smaller/cheaper models where accuracy allows, tighter context windows via better retrieval precision so fewer tokens need to be sent to generation) far more than on the vector search infrastructure itself, which is rarely the cost bottleneck it's often assumed to be.

---

## Build it from scratch

A minimal ACL-aware retrieval wrapper, enforcing tenant/ABAC filtering as a mandatory predicate rather than a post-hoc discard step, plus the PII-detection-before-embedding ordering.

```python
# untested sketch -- illustrates ordering and mandatory-filter discipline, not a full pipeline
from dataclasses import dataclass

@dataclass
class Caller:
    tenant_id: str
    allowed_classifications: set[str]  # e.g. {"public", "internal"}

@dataclass
class Chunk:
    text: str
    tenant_id: str
    classification: str
    contains_pii: bool

def ingest(document_text: str, tenant_id: str, classification: str, pii_detector, embedder, vector_store):
    # PII handling happens BEFORE embedding -- this is the only point that matters.
    spans = pii_detector.detect(document_text)
    redacted_text, contains_pii = pii_detector.redact(document_text, spans)
    chunks = chunk_text(redacted_text)  # see 01-chunking
    for chunk_text_ in chunks:
        vec = embedder.embed(chunk_text_)
        vector_store.insert(
            vector=vec,
            text=chunk_text_,
            metadata={
                "tenant_id": tenant_id,
                "classification": classification,
                "contains_pii": contains_pii,
            },
        )

def retrieve(query: str, caller: Caller, embedder, vector_store, k: int = 8):
    query_vec = embedder.embed(query)
    # the filter is passed INTO the ANN search, not applied after -- mandatory, not optional
    mandatory_filter = {
        "tenant_id": caller.tenant_id,
        "classification": {"$in": list(caller.allowed_classifications)},
    }
    return vector_store.filtered_search(query_vec, k=k, filter=mandatory_filter)
    # NOTE: no code path in this system should ever call vector_store.search()
    # (unfiltered) directly -- that function should not exist in the client surface
    # at all, to make the "someone forgot the filter" failure mode structurally impossible.
```

The one-line lesson this sketch is trying to make structural, not just procedural: don't expose an unfiltered search function in your retrieval client at all if you can help it — a missing filter should be a compile-time-shaped impossibility, not a code-review-catchable mistake.

---

## How it's done in production

**Weaviate** — native per-tenant sharding via `multiTenancyConfig`, cold-storage for inactive tenant shards, ACORN filter-aware traversal for shared-index ABAC cases. **Pinecone** — namespaces for cheap logical multi-tenancy at very large tenant counts, explicitly documented as a logical not cryptographic boundary. **pgvector + Postgres RLS** — the highest defense-in-depth option when already on Postgres, since RLS is enforced by the database regardless of application query shape. **Microsoft Presidio** — the most commonly cited open-source PII detection/anonymization toolkit for the ingestion-time redaction stage. **Elasticsearch/OpenSearch** — mature blue-green/alias-swap reindexing tooling, often the reference pattern other vector databases' migration guides borrow from.

| Symptom | Cause | Fix |
|---|---|---|
| Tenant A's data appears in tenant B's retrieved results | Filter applied as a post-retrieval application-layer discard instead of a database-enforced predicate; a code path skipped the filter | Move the filter into the ANN query itself (filtered search) and add Postgres RLS or equivalent as a defense-in-depth layer that can't be bypassed by a missing `WHERE` clause |
| Retrieval quality degrades slowly and unevenly after an embedding model upgrade | Old and new documents' vectors come from different embedding models sharing an index; distances between them aren't meaningful | Re-embed the full corpus into the new model via a dual-write/dual-column migration before cutting query traffic over; never mix embedding-model vectors in one similarity comparison |
| A revoked user's queries still surface documents they should no longer see | ACL metadata sync from the source system lags the actual permission change (batch/poll-based sync, not real-time) | Move to webhook-driven, near-real-time ACL metadata updates; bound and monitor the sync lag explicitly as an SLO |
| PII shows up in a generated answer despite an output-time redaction filter | The PII was retrieved and placed in the model's context before generation; output scanning can't undo influence on the response, and can miss reworded PII | Detect and redact/tokenize PII at ingestion, before chunking and embedding, not only at output time |
| Reindex after a chunking-strategy change causes a multi-hour outage | Live index mutated in place instead of building the new index in parallel | Blue-green: build fully in parallel, validate against a golden query set, atomically swap an alias, retain the old index for a bounded rollback window |
| A highly selective ACL filter (small tenant on a large shared index) returns few or zero results despite matching documents existing | Post-filtering after an unfiltered top-k ANN search, or a non-filter-aware index under-searching for a narrow filter | Use filter-aware traversal (ACORN-style) or physical per-tenant sharding so the search itself is scoped, not merely the post-hoc result set |
| Per-query cost is far higher than expected | Assuming the vector search is the cost driver when it's actually reranking and generation-model tokens | Break down cost per query by stage; optimize context size (retrieval precision) and generation model choice before touching vector search infrastructure |

---

## Tradeoffs & when NOT to use it

- **Don't use logical namespace isolation (Pinecone-style) for the most security-sensitive tenants without additional controls.** It's cheap and scales to huge tenant counts, but it's explicitly a query-time logical partition, not a cryptographic boundary — a misconfigured query is a real risk. Pair it with strict client-side guardrails (no unfiltered search function exposed) or move the highest-sensitivity tenants to physical isolation.
- **Don't use per-tenant physical sharding (Weaviate-style) for a product with millions of very small tenants without cold storage.** Per-shard overhead makes tiny tenants inefficient to keep warm; this is exactly why Weaviate's cold-storage-for-inactive-tenants feature exists, and skipping it at scale means paying real infrastructure cost for shards serving a handful of documents each.
- **Don't rely on output-time PII scanning as your only control.** It can't prevent PII from having been retrieved into the model's context in the first place, and reworded or paraphrased PII in a generated answer can slip past a pattern-matching output filter even when the literal source string would have been caught at ingestion.
- **Don't reindex in place for any change that alters vector geometry (embedding model, dimension, distance metric).** There's no safe in-place path for this; it requires either a parallel index build or a dual-column migration, full stop.
- **Don't treat ACL sync lag as acceptable-by-default.** A batch/nightly sync between a source permission system and RAG index metadata is a real, exploitable staleness window for anything handling access-sensitive data (internal wikis, HR documents, customer data) — the acceptable lag is workload-specific, but "we sync once a day" is rarely defensible for anything with real access control requirements.

---

## Interview questions

### Q1 — Why is applying an ACL filter after retrieval (post-filtering) a security problem, not just a recall problem?
**Testing:** whether the candidate treats this as a functional correctness issue only, or recognizes the security stakes.
**Answer:** Post-filtering that discards unauthorized results in application code has two failure modes: it under-returns when the caller's allowed subset is a small fraction of the corpus (a recall problem), and worse, any code path — a new endpoint, a debug tool, an agent — that skips the discard step leaks another tenant's data directly, which is a data breach, not a quality bug.
**Follow-up trap:** *"How would you make this structurally hard to get wrong, not just documented?"* — don't expose an unfiltered search function in the retrieval client at all; make the filter a mandatory parameter of the only search function that exists, and add database-level enforcement (Postgres RLS) as defense in depth against application-layer mistakes.

### Q2 — Compare Pinecone namespaces and Weaviate per-tenant shards as multi-tenancy strategies.
**Answer:** Pinecone namespaces are a cheap, logical query-time partition that scales to very large tenant counts (100,000+ on standard plans) but are explicitly documented as not a cryptographic boundary — a misconfigured query can cross it. Weaviate gives each tenant a physically separate HNSW shard, stronger isolation with no cross-tenant data co-location, at the cost of per-shard overhead that's wasteful for very small tenants unless mitigated with cold storage for inactive shards.
**Follow-up trap:** *"Which would you pick for a product with a mix of enterprise customers and thousands of free-tier users?"* — likely a hybrid: physical isolation for high-sensitivity/high-value tenants, logical namespace partitioning for the long tail, rather than one strategy for every tenant.

### Q3 — Why can't you fix a PII leak by filtering the model's output after generation?
**Answer:** By the time generation runs, the PII has already been retrieved and placed in the model's context — output-time filtering can catch and redact the literal string in some cases, but it can't undo the PII's influence on the generated response, and paraphrased or reworded PII in the output can slip past a pattern-matching filter even when ingestion-time redaction would have caught the original text.
**Follow-up trap:** *"So is output-time scanning useless?"* — no, it's a legitimate last line of defense, just not sufficient alone; the primary control has to be ingestion-time detection and redaction, before chunking and embedding.

### Q4 — What specifically breaks if you index new documents with a new embedding model without re-embedding the existing corpus?
**Answer:** Vectors from different embedding models don't share a geometry — cosine or dot-product similarity between an old-model vector and a new-model vector is not meaningful. The failure is silent and gradual: retrieval quality for queries that should match older documents degrades unevenly rather than failing loudly, making it easy to ship and notice only weeks later.
**Follow-up trap:** *"How would you detect this had already happened in a live system?"* — segment retrieval-quality metrics (recall@k against a golden set) by document age/embedding-model version; a quality gap correlated with document vintage is the signature.

### Q5 — Walk through a zero-downtime index migration for switching embedding models.
**Answer:** Build the new index fully in parallel against a corpus snapshot while the old index keeps serving traffic; dual-write new/changed documents to both indexes during the build window so the new index isn't stale at cutover; validate the new index against a golden query set; atomically swap an alias so all traffic moves in one step with instant rollback available; retain the old index for a bounded window (commonly ~24 hours) before decommissioning.
**Follow-up trap:** *"What if the golden query set doesn't catch a regression that only shows up under real traffic?"* — that's exactly why the old index is retained for a rollback window and the alias swap is instant and reversible; a golden set reduces but never eliminates this risk.

### Q6 — Why doesn't HNSW support clean deletes, and how does that affect incremental indexing?
**Answer:** Removing a node cleanly requires re-linking its neighbors, which is expensive to do correctly online, so most implementations tombstone deleted vectors (mark invalid, excluded from results) instead. Under high delete/update churn, tombstone accumulation degrades search quality and latency over time, since search still has to traverse and discard tombstoned nodes — periodic compaction or full rebuild is still needed on a schedule, just far less often than per-change.
**Follow-up trap:** *"How would you decide how often to compact?"* — monitor tombstone ratio and query latency/recall over time; compact when either crosses a threshold you've validated against a golden set, not on a fixed arbitrary schedule.

### Q7 — Break down where the cost actually goes in a production RAG query.
**Answer:** Query embedding is near-negligible; vector search itself is fast and cheap (milliseconds, a small fraction of total cost); reranking (a cross-encoder pass over retrieved candidates) is more expensive per query but still usually small; generation — retrieved context tokens plus the question plus the answer, at the generation model's per-token price — dominates total cost. Optimization effort belongs on generation model choice and retrieval precision (fewer, better-targeted tokens sent to generation), not on vector search infrastructure.
**Follow-up trap:** *"So would you ever optimize the vector search layer for cost?"* — yes, but usually for latency or memory footprint at very large scale, not because it's the dominant cost driver; conflating "the retrieval system is complex" with "the retrieval system is expensive" is a common mistake.

### Q8 — What's the risk of relying on a nightly batch sync between a source permission system (e.g., Google Drive ACLs) and your RAG index's metadata?
**Answer:** A window exists between a permission being revoked in the source system and that revocation taking effect in retrieval — up to the length of the sync interval, during which a user who's lost access can still retrieve documents they should no longer see. For access-sensitive corpora (HR, legal, customer data) this staleness window is a real, exploitable risk, not a theoretical one.
**Follow-up trap:** *"How would you close this window without polling constantly?"* — webhook-driven, event-based ACL updates from the source system, propagating permission changes to chunk metadata near-real-time instead of on a fixed poll interval.

### Q9 — Design the multi-tenant retrieval architecture for a SaaS product where tenant sizes range from a handful of documents to millions.
**Answer:** A single strategy poorly serves both ends. Small tenants are cheap to isolate physically (a tiny shard, or even a flat scan, is trivially fast) or can share a logically-partitioned index without meaningful noisy-neighbor risk given their low query volume. Large tenants benefit from physical isolation to avoid noisy-neighbor effects and to sidestep the filtered-search recall problem entirely at high query volume. An adaptive strategy — physical shards for tenants above a size/volume threshold, shared logical partitioning below it — is the honest answer, not one configuration for everyone.
**Follow-up trap:** *"What's the operational cost of that adaptive strategy?"* — you now run two isolation mechanisms and need a migration path for a tenant that grows past the threshold, which is real added complexity you should name explicitly rather than presenting the adaptive approach as free.

### Q10 — A candidate says "we redact PII by having the LLM refuse to repeat it if asked." Why is this wrong?
**Testing:** whether the candidate understands the ingestion-vs-generation timing issue.
**Answer:** Relying on the generation model's own judgment to withhold PII it has already been given in context is unreliable — models can be prompted around such instructions, can leak PII incidentally while answering an unrelated part of the question, and this approach does nothing to prevent the PII from having entered the model's context and potentially influencing outputs in subtler ways than verbatim repetition. PII handling needs to happen at ingestion, before the sensitive text is ever embedded or retrievable.
**Follow-up trap:** *"Isn't ingestion-time redaction going to miss things too?"* — yes, PII detectors have real false-negative rates, especially on unstructured or non-standard-format PII; the honest answer combines ingestion-time redaction with output-time scanning and ongoing monitoring, not either alone.

### Q11 — What's the difference between RBAC and ABAC in the context of retrieval filtering, and why did production systems move toward ABAC?
**Answer:** RBAC filters on coarse roles (tenant membership, a fixed role like "admin"/"member"); ABAC filters on finer, often combinatorial attributes (department, classification level, document owner, project membership) that map more directly to how real enterprise permission systems actually grant access. Production systems moved to ABAC because RBAC alone is too coarse to express "this document is visible to Legal and Finance but not Engineering," a routine real-world requirement.
**Follow-up trap:** *"Does ABAC filtering cost more at query time than RBAC?"* — yes, more filter predicates generally mean the underlying index has to do more filter-aware work (see the filtered-search cost analysis in `T06-vector-index-internals`), so ABAC's expressiveness is a real latency/complexity tradeoff, not a free upgrade.

### Q12 — How would you diagnose whether a slow production RAG query is a retrieval problem or a generation problem?
**Answer:** Instrument and log per-stage latency and cost (embedding, filtered vector search, reranking, generation) separately. If vector search is fast but overall latency is high, look at reranking candidate count or generation context size/model choice; if vector search itself is slow, that points back to the index-tuning failure modes in `T06-vector-index-internals` (unscaled efSearch/nprobe, filter selectivity issues, write contention).
**Follow-up trap:** *"What's the first thing you'd check before touching any configuration?"* — whether corpus size or tenant count changed recently without a corresponding re-tune of retrieval or filter strategy — the most common silent cause of a regression that looks like "the system got slow for no reason."

### Q13 — Your team wants to migrate from a shared index with metadata filtering to per-tenant physical sharding for security reasons. What's the migration risk?
**Answer:** This is a structural migration, not a parameter change — every tenant's data needs to move to a new physical shard, which is its own zero-downtime migration problem (build new shards in parallel, validate, cut over per-tenant or in batches, retain rollback capability). Doing this for all tenants simultaneously multiplies the blast radius of any single mistake; a staged, per-tenant-cohort rollout with validation at each stage is safer than a big-bang cutover.
**Follow-up trap:** *"How would you validate a single tenant's migrated shard before cutting their traffic over?"* — replay a sample of that tenant's real recent queries against both the old and new shard and diff the results, in addition to any golden query set, since a golden set built for the whole corpus may not represent one tenant's specific query patterns well.

### Q14 — What would make you choose Postgres row-level security over relying purely on application-layer filtering, given both require writing the filter logic somewhere?
**Answer:** RLS is enforced by the database regardless of the query shape issued by the application — a query that forgets the `WHERE tenant_id = ...` clause still can't see other tenants' rows, because Postgres itself blocks it. Application-layer filtering only works if every single code path correctly includes the filter, which is a much larger and more fragile surface to guarantee correct, especially as the codebase grows and more code paths (new features, internal tools, agents) are added over time.
**Follow-up trap:** *"Does RLS have a performance cost?"* — yes, it adds a predicate to every query plan, and with complex ABAC policies it can interact poorly with index selection; it's worth measuring, but the security guarantee is usually worth the overhead for access-sensitive workloads.

### Q15 — Design an incremental indexing strategy for a corpus that changes continuously — thousands of document updates per hour — with a requirement that new/changed documents are searchable within 5 minutes.
**Answer:** A pure batch reindex can't meet a 5-minute SLA at that update volume; the design needs a streaming ingestion path (embed and insert/tombstone-and-reinsert individual documents as changes arrive) directly into the live index, since HNSW supports incremental insert natively. Deletes and updates get tombstoned rather than cleanly removed, so a periodic (not per-change) compaction/rebuild job is still needed to control tombstone accumulation and its effect on latency/recall over time — schedule that job based on monitored tombstone ratio and query-quality metrics, not a fixed interval.
**Follow-up trap:** *"What happens to recall during the window between an update and the next compaction?"* — the old version is tombstoned (excluded) as soon as the update is processed, so recall for the *updated* content is generally fine immediately; the risk is graph-quality degradation and latency creep from accumulated tombstones over many changes, not stale results from a single update.

---

## Red flags that fail you

- Describing ACL enforcement as "we filter the results after we get them back from the vector search."
- Treating PII redaction as something you can do at the output/generation stage instead of at ingestion.
- Not knowing that Pinecone namespaces are a logical, not cryptographic, isolation boundary.
- Proposing an in-place index mutation for an embedding-model or chunking-strategy change instead of a parallel-build-and-swap migration.
- Assuming vector search is the dominant cost driver in a RAG query instead of generation/reranking tokens.
- Not naming the ACL-sync staleness window as a real risk in a multi-tenant design.
- Claiming a single multi-tenancy strategy (all-logical or all-physical) is correct regardless of tenant size distribution.

---

## Cheat card

```
ACL-AWARE RETRIEVAL
  filter enforced at DB/ANN layer, NEVER as app-layer post-retrieval discard
  Pinecone namespaces: logical partition, NOT cryptographic, scales to 100K+ tenants
  Weaviate: physical per-tenant HNSW shard, cold-storable when inactive, stronger isolation
  pgvector + Postgres RLS: defense-in-depth, DB blocks queries missing the filter clause
  RBAC -> too coarse for real enterprise perms; ABAC (tenant+dept+classification) is baseline
  noisy neighbor: shared logical index has no isolation from another tenant's query load
    by default; physical sharding solves this incidentally

PII
  detect + redact/tokenize at INGESTION, before chunk/embed -- you cannot un-embed a vector
  output-time scanning = last line of defense only, doesn't stop retrieval-time exposure
  detectors have real false-negative rates -- treat as risk reduction, not a guarantee
  tools: Microsoft Presidio (common open-source baseline)

INCREMENTAL INDEXING
  HNSW: native incremental insert. No clean delete -- tombstone, periodic compaction/rebuild.
  IVF: centroids drift stale over time, need periodic (not per-insert) re-training.
  embedding-model drift: mixing old/new model vectors in one index = meaningless similarity.
    symptom: silent, gradual, uneven retrieval quality decline -- segment metrics by doc age.

ZERO-DOWNTIME MIGRATION (blue-green)
  1. build new index fully in parallel  2. dual-write during build window
  3. validate vs golden query set  4. atomic alias swap  5. retain old index (~24h) for rollback
  dual-column pattern (embedding_v1/v2) = same discipline at column level, for pgvector-in-place

COST PER QUERY (typical breakdown, cheapest to most expensive)
  query embedding: negligible | vector search: ms, tiny fraction of cost
  reranking: moderate (cross-encoder over ~20-50 candidates)
  generation: DOMINANT cost -- context + question + answer tokens
  reported production target: often sub-$0.01-$0.02/query
  optimize generation model + retrieval precision FIRST, not vector infra
```

## Sources
- [Securing and Governing Vector Databases in 2026 — Blockchain Council](https://www.blockchain-council.org/ai/securing-and-governing-vector-databases-privacy-prompt-injection-multi-tenant-access-control/) — accessed 2026-07-28
- [Multi-Tenant RAG Data Isolation: The 2026 Enterprise Architecture Guide — Truto](https://truto.one/blog/how-to-architect-strict-data-isolation-in-multi-tenant-rag-pipelines/) — accessed 2026-07-28
- [Secure RAG: Authorisation-Aware Retrieval and Row-Level Security — Medium](https://photokheecher.medium.com/secure-rag-authorisation-aware-retrieval-and-row-level-security-c6542500ec21) — accessed 2026-07-28
- [Multi-tenancy operations — Weaviate Documentation](https://weaviate.io/developers/weaviate/manage-data/multi-tenancy) — accessed 2026-07-28
- [Rethinking Vector Search at Scale: Weaviate's Native, Efficient and Optimized Multi-Tenancy — Weaviate](https://weaviate.io/blog/weaviate-multi-tenancy-architecture-explained) — accessed 2026-07-28
- [Implement multitenancy — Pinecone Documentation](https://docs.pinecone.io/guides/index-data/implement-multitenancy) — accessed 2026-07-28
- [Multi-Tenancy in Vector Databases — Pinecone](https://www.pinecone.io/learn/series/vector-databases-in-production-for-busy-engineers/vector-database-multi-tenancy/) — accessed 2026-07-28
- [Migrating vector embeddings in production without downtime — Google Cloud Community / Medium](https://medium.com/google-cloud/migrating-vector-embeddings-in-production-without-downtime-8a0464af6f55) — accessed 2026-07-28
- [Blue-Green Deployment in Elasticsearch: Safe Reindexing and Zero-Downtime Upgrades](https://widhianbramantya.com/elasticsearch/blue-green-deployment-in-elasticsearch-safe-reindexing-and-zero-downtime-upgrades/) — accessed 2026-07-28
- [What Matters in Production RAG — Arpit Bhayani](https://arpitbhayani.me/blogs/rag-production/) — accessed 2026-07-28
- [Design an ML search system with RAG — OpenAI interview question writeup](https://prachub.com/interview-questions/design-an-ml-search-system-with-rag) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
