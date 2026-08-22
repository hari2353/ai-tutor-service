# Metadata & Filtering: Schema Design, Pre vs Post Filter, Cardinality

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.0h · **Prereqs:** 03-vector-index-internals · **Updated:** 2026-08-01
> **Module id:** `T06-metadata-design` · **Tags:** ingest,critical

## The 30-second version

Every production vector query is really "nearest neighbors WHERE some filter holds" — tenant_id, ACL, status, date range — and every ANN index (HNSW, IVF) was designed assuming any indexed vector is a valid target, so bolting a filter on after the fact breaks in one of two specific, opposite ways: pre-filtering restricts the search to a subset with no index built over that subset specifically, degenerating toward brute force as selectivity drops; post-filtering runs the unfiltered ANN search first and discards non-matching results, which can silently return fewer than k results, or zero, when the filter is selective enough that the unfiltered top-k happens to contain no matches even though hundreds exist elsewhere in the corpus. Schema design determines which failure mode you hit and how badly: high-cardinality, high-selectivity filters (a specific tenant_id among a million) are the expensive case because they shrink the effective search space the most and stress filtered-ANN machinery the hardest, while low-cardinality filters (a boolean flag) are cheap because most of the index still qualifies. ACL enforcement has an extra, non-negotiable constraint on top of the performance question: an access-control filter must be applied *in* the retrieval query itself, never as a post-hoc check on returned results, because "search everything, then discard what you shouldn't have seen" means the vector index, cache, or logs may have already leaked the existence or content of documents the user has no right to see.

## Why this gets asked

The interviewer has been paged twice for the same underlying bug wearing two different costumes: once because a metadata filter that used to return instantly started brute-force-scanning the whole corpus after a selective new tenant onboarded, and once because a filter that was supposed to enforce access control was implemented as a post-retrieval check, and a penetration test (or worse, a real incident) found that a user's query results briefly included a document from a different, unauthorized tenant before the filter removed it — by which point it may have already been logged, cached, or returned via a race condition. They want to know if you understand metadata design as a joint performance-and-security problem, not a "just add a WHERE clause" afterthought.

---

## Lineage: past → present → future

**What came before.** Early vector search deployments largely ignored filtering because early use cases (semantic search over one shared corpus, no tenancy) didn't need it — a query was purely "find the k nearest vectors," full stop. As RAG moved into multi-tenant SaaS products and enterprise deployments with document-level access control, the pain surfaced immediately and specifically: HNSW and IVF indexes have no native concept of "some subset of vectors are ineligible for this query," because they were built assuming the entire indexed set is fair game. The first production answers were the two naive strategies — pre-filter (search only the eligible subset) and post-filter (search everything, discard ineligible results after) — and both had well-understood, opposite failure modes from the moment they were tried at scale (see `03-vector-index-internals` for the graph-connectivity mechanics of why).

**Where it stands now.** Filter-aware retrieval is now the accepted requirement for any production RAG system with real access-control or multi-tenancy needs, but there is no single settled implementation: Weaviate's ACORN does multi-hop graph expansion and, as of v1.34, automatically switches between multi-hop exploration, relaxed broader traversal, or flat brute-force scan based on filter selectivity; Qdrant ships a filterable HNSW with its own adaptive query planner; Pinecone defaults to post-filtering with a merged metadata/vector index, which is faster on average but carries the classic under-return risk on highly selective filters unless you compensate by oversampling. Weaviate's native multi-tenancy (per-tenant physical index/shard, not just a metadata field) is the industry's answer to the security half of this problem for SaaS products — sidestepping the filtered-ANN problem entirely for the tenant boundary specifically, at real per-tenant operational cost. The live disagreement is less "should filters be index-aware" (settled: yes) and more where the tenant/security boundary should live physically — metadata field vs. separate collection/shard vs. separate database — a decision that trades isolation guarantees against operational cost in ways specific to each product's tenant-size distribution.

**Where it's heading.** Adaptive, selectivity-aware query planning (choosing pre-filter, post-filter-with-oversampling, or graph-aware traversal per query based on measured or estimated filter selectivity, the way Weaviate v1.34 already does) is becoming the expected default in mature vector databases rather than a single fixed strategy — high confidence, already shipping. Database-level row-security integration (Postgres RLS combined with pgvector, so the filter is enforced by the database's own access-control layer rather than solely by application code) is a growing pattern for teams that want defense-in-depth on the ACL requirement specifically — real and in use, moderate confidence it becomes as standard as application-layer filtering is today.

---

## Mental model

Two failure modes, drawn as opposite ends of one dial (filter selectivity), with the danger zone being wherever your actual traffic sits without you having checked:

```
  BROAD FILTER (low selectivity, most vectors qualify)
       │
       │   post-filter is fine here: unfiltered top-k is
       │   almost entirely filter-valid anyway
       │
       ├──────────────────────────────────────────────┤
       │
       │   SELECTIVE FILTER (high selectivity, few vectors qualify)
       │
       │   post-filter breaks: unfiltered top-k may contain
       │   ZERO filter-valid results even though hundreds exist
       │   elsewhere in the graph — the greedy search never
       │   routed toward them
       │
       │   pre-filter breaks the OTHER way: no index exists over
       │   just the filtered subset, so it degenerates to a brute-
       │   force scan over however many documents match the filter
       │
  UNKNOWN FILTER (you didn't test your actual production
  filter-selectivity distribution before launch)
       │
       └── this is where the incident happens
```

The fix in both directions is the same idea: don't let the graph's traversal be blind to the filter. Either expand the search radius intelligently when the filter is narrow (ACORN-style multi-hop) or physically isolate the eligible subset ahead of time (per-tenant sharding) so there's no filter to reconcile against the graph at query time at all.

---

## How it actually works

### Schema design for filterable fields

Decide, per field, whether it needs to be a **filter** (hard constraint, must match) or a **boost** (soft preference, affects ranking but doesn't exclude), since these have different cost profiles and different failure modes if confused. Typical filterable fields in a RAG system: `tenant_id` / `org_id` (near-universal, usually the highest-cardinality, most-selective filter in the system), `acl` / `visible_to` (a list-valued field, often the trickiest to index efficiently since membership tests on list fields don't map cleanly onto simple equality indexes), `document_type`, `status` (active/archived/draft), `created_at`/`updated_at` (range filters, different index structure than equality filters), `language`/`locale` (see `12-multilingual`), and `source_system` (for provenance and routing).

Denormalize metadata onto the chunk record itself rather than requiring a join back to a source-of-truth table at query time — vector databases generally don't support efficient joins, and a per-query round-trip to a separate permissions or metadata store adds real latency to every retrieval call. The tradeoff: denormalized metadata can drift out of sync with the source of truth (a document's ACL changes, but the chunk's stored copy of that ACL is stale until the next reindex/sync), which is exactly the problem the next section addresses.

### Pre-filter vs. post-filter — the failure modes precisely

**Pre-filtering** applies the filter first (e.g. a metadata index narrows candidates to `tenant_id = X`), then searches only within that subset. The failure: there is typically no ANN index built over an arbitrary filtered subset specifically — the HNSW graph or IVF partition was built over the *whole* corpus — so searching "only vectors where tenant_id = X" either requires a separate per-value index (expensive to maintain per distinct filter value) or falls back to scanning the filtered subset with brute-force distance computation, losing the ANN speedup entirely. Cost scales with how many documents match the filter, not with total corpus size, which sounds fine until a filter matches a large fraction of a large corpus.

**Post-filtering** runs the unfiltered ANN search first, retrieves the top-k by pure similarity, then discards results that fail the filter. The failure is subtler and more dangerous because it fails silently: if the filter is selective (say it matches 1% of the corpus) and the unfiltered unfiltered unfiltered top-k search happens not to surface enough filter-valid candidates within its beam, you can get back far fewer than k results — even zero — despite hundreds of valid matches existing elsewhere in the corpus, because the greedy graph search had no reason to route toward the filter-valid region. Concretely: with a filter matching roughly 10% of rows and a default HNSW `ef_search` around 40, a naive post-filter search retrieves on the order of only ~4 filter-valid rows on average from that beam — well short of a `k=10` request — which is the exact mechanism, not just the general shape, of the under-return failure.

**The deeper reason, from the index's perspective**: HNSW's greedy descent stays within "good" recall territory by hopping through the nearest *unfiltered* neighbors at each step. Restricting which nodes count as valid after the fact can strand the search in a region of the graph with no efficient path to any filter-valid node, especially under low selectivity, because the graph's edges were never built with that restriction in mind (`03-vector-index-internals` covers this at the index-internals level).

### What the vector databases actually do about it

| Strategy | Behavior | Where |
|---|---|---|
| Iterative/expanding scan | Continue traversing further into the graph (deeper beam, more candidates) until enough filter-valid results are found or a scan-depth limit is hit | pgvector's `hnsw.iterative_scan`, moderate filters |
| Multi-hop graph expansion | On a selective filter, expand the search radius via multi-hop traversal specifically to reach filter-valid regions the greedy search would otherwise miss | Weaviate ACORN |
| Adaptive strategy selection | Estimate filter selectivity at query time and choose pre-filter, relaxed traversal, or flat brute-force scan accordingly, rather than one fixed strategy always | Weaviate v1.34+ (automatic), Qdrant's query planner |
| Merged index, default post-filter | Metadata and vector index merged into one structure; fast on average, accepts the under-return risk on highly selective filters unless the caller oversamples | Pinecone (default behavior) |
| Physical isolation | Separate index/shard per tenant — no filter-vs-graph reconciliation needed because ineligible vectors were never in the index being searched | Weaviate native multi-tenancy |

**Practical mitigation when you don't control the index internals**: oversample before filtering (request `k * factor` candidates, e.g. `k=10` requested as `k1=50-100`, then filter down), which reduces but does not eliminate the under-return risk on very selective filters, and costs proportionally more compute per query.

### Cardinality, selectivity, and why a high-cardinality filter is the expensive case

**Cardinality** is the number of distinct values a field can take; **selectivity** is what fraction of the corpus a specific filter value matches. A boolean `is_archived` field has low cardinality (2 values) and, if most documents are active, low selectivity when filtering for `is_archived = false` (most of the corpus still qualifies) — cheap in both pre- and post-filter strategies, since the filtered subset is nearly the whole index either way. A `tenant_id` field with a million distinct values and roughly even distribution has extremely high cardinality and, for any single tenant, extremely high selectivity (a tiny fraction of the corpus matches) — this is the expensive case in both directions: pre-filtering degenerates to scanning a small-but-unindexed subset per tenant, and post-filtering is exactly where the under-return failure mode above is most severe, because the unfiltered top-k is least likely to contain enough of that tenant's documents by chance.

The practical rule: know your actual filter cardinality/selectivity distribution before launch, not after. A filter that matches 50% of the corpus behaves completely differently from one that matches 0.1%, and which naive strategy your database defaults to determines which specific failure you'll hit — this needs measurement against real data, not an assumption carried over from a different product's filter shape.

### Multi-tenancy: metadata field vs. separate collections

**Shared index with a `tenant_id` metadata field**: simplest to operate (one index, one schema, one thing to monitor and reindex), but inherits every pre/post-filter tradeoff above, scaled by however skewed your tenant-size distribution is — a shared index serving both a 100-document tenant and a 5-million-document tenant behind the same filter strategy rarely serves both well.

**Separate collection/index per tenant**: isolates each tenant's query performance and data completely — no filter-vs-graph reconciliation needed, since ineligible vectors were literally never indexed alongside eligible ones — at the cost of N indexes to build, warm, monitor, and reindex, which multiplies operational surface area linearly with tenant count. Weaviate's native multi-tenancy is explicitly designed to make this cheaper than naively creating N full collections (shared underlying resources, lighter per-tenant overhead), but the fundamental N-things-to-manage tradeoff doesn't disappear, it's just cheaper per unit.

**The size-skew problem**: a tenant-size distribution spanning several orders of magnitude (100 to 5 million vectors, a common real shape) usually means no single strategy is right for every tenant — the smallest tenants may be faster and simpler served by brute-force scan or even in-memory linear search (trivial at that size, sidesteps the whole filtered-ANN problem), while the largest tenants justify physical per-tenant index isolation, and a shared filtered index is the reasonable middle tier. State this explicitly rather than picking one architecture for all tenants.

### ACL-aware filtering: the security requirement that it be enforced in the query

The performance discussion above applies equally to an access-control filter, but ACL enforcement has a strict correctness requirement layered on top that a pure performance filter doesn't: **the filter must be applied as part of the retrieval query itself, never as a post-retrieval check on already-returned results.** If a query retrieves documents the user isn't authorized to see and only discards them afterward in application code, several things can already have gone wrong before the discard: the unauthorized document's existence or snippet may have been logged, cached, included in a response payload briefly visible to a client before filtering, or exposed through a timing/count side-channel (a user can infer a document exists in a restricted set by noticing result counts change). This is a strictly stronger requirement than "eventually filter correctly" — it's "never let the ineligible data leave the boundary in the first place."

Practically, this means the ACL condition needs to be a genuine query-time filter (not a downstream check), ideally enforced at a layer that's hard to bypass by a future code change — database row-level security (Postgres RLS with pgvector) is a defense-in-depth pattern precisely because it moves the enforcement into the data layer itself, rather than trusting every application code path to remember to apply the filter. RBAC (role-based access control — permissions attached to roles, roles attached to users) is simpler to reason about and audit but coarse-grained; ABAC (attribute-based access control — permissions computed from attributes of the user, resource, and context, e.g. "user's department matches document's department AND user's clearance level >= document's sensitivity") is the pattern production systems increasingly move toward when access rules depend on more than a fixed role, at the cost of more complex policy evaluation at query time.

### Schema evolution without a full reindex

Adding a new filterable field to existing chunks (e.g. introducing a `sensitivity_level` field after launch) generally requires a metadata backfill (writing the new field's value onto every existing chunk record) but not necessarily re-embedding, since the vector itself is unaffected — this is far cheaper than a full reindex and should be the default expectation for additive metadata changes. Changing an existing field's *type* or *semantics* (e.g. `status` changing from a boolean to an enum with new states) is riskier: any code or index structure that assumed the old type/range needs auditing, and a partial rollout (some chunks migrated, some not) can produce silently inconsistent filtering behavior mid-migration — treat this class of change as a real migration with a validation pass, not a quick field rename.

---

## Build it from scratch

```python
# untested sketch — illustrates the pre-filter/post-filter/oversample tradeoff
# and the query-time (not post-hoc) ACL enforcement requirement
def search_pre_filter(index, query_vec, tenant_id: str, k: int):
    """Only correct/fast if the index has a genuine per-tenant sub-index or
    partition -- otherwise this degenerates to a brute-force scan over
    whatever matches tenant_id, which is the pre-filter failure mode."""
    eligible_ids = index.metadata_lookup(tenant_id=tenant_id)   # could be huge and unindexed
    return index.ann_search_within(query_vec, candidate_ids=eligible_ids, k=k)


def search_post_filter_with_oversample(index, query_vec, tenant_id: str, k: int, oversample_factor: int = 10):
    """Mitigates, but does not eliminate, post-filter under-return on
    selective filters. Tune oversample_factor against measured selectivity."""
    candidates = index.ann_search(query_vec, k=k * oversample_factor)
    filtered = [c for c in candidates if c.metadata["tenant_id"] == tenant_id]
    if len(filtered) < k:
        # WRONG to silently return fewer than k without signaling this happened --
        # log it, since it's evidence the oversample factor or filter selectivity
        # needs attention, not a normal empty-result case
        log_under_return(tenant_id=tenant_id, requested_k=k, found=len(filtered))
    return filtered[:k]


def search_with_acl_enforced_in_query(index, query_vec, user_id: str, k: int):
    """ACL MUST be part of the query condition, never a post-hoc filter applied
    to already-materialized results -- this is a correctness/security
    requirement, not a performance optimization choice like the two above."""
    acl_condition = build_acl_predicate(user_id)   # e.g. "acl_list CONTAINS user_id OR user_role IN (...)"
    return index.ann_search(query_vec, filter=acl_condition, k=k)
    # NEVER: results = index.ann_search(query_vec, k=k); return [r for r in results if user_can_see(r)]
```

---

## How it's done in production

**Filter-aware ANN**: Weaviate (ACORN multi-hop + adaptive strategy selection since v1.34), Qdrant (filterable HNSW with adaptive planner), pgvector (`hnsw.iterative_scan`/`ivfflat.iterative_scan` for moderate filters, partial indexes/partitioning for very selective ones). **Multi-tenancy**: Weaviate native per-tenant collections, Pinecone namespaces, Postgres row-level security combined with pgvector for defense-in-depth ACL enforcement. **Schema/metadata pipelines**: denormalize permissions and filterable attributes onto chunk records at ingest time, with an explicit sync/backfill job (and staleness monitoring) against the source-of-truth permission system.

| Symptom | Cause | Fix |
|---|---|---|
| A specific tenant's queries suddenly return far fewer results than `k`, or none | Post-filter under-return on a selective filter — unfiltered top-k didn't happen to contain enough (or any) of that tenant's documents | Oversample before filtering, or move to a filter-aware index (ACORN, filterable HNSW); log under-return events instead of silently returning short |
| A filtered query that used to be instant now scans the whole corpus | Filter selectivity changed (a new, much larger or much smaller tenant onboarded) shifting which naive strategy the database defaults to | Re-profile filter selectivity distribution after significant data growth; move the affected tenant to a dedicated index/shard if it's now an outlier |
| A security audit finds a brief window where unauthorized documents appear in raw retrieval results before being filtered | ACL enforced as a post-retrieval application-layer check instead of a query-time filter | Move the ACL condition into the retrieval query itself; add database-level row-level security as defense-in-depth |
| New metadata field rollout causes inconsistent filtering results mid-migration | Some chunks backfilled with the new field, others not, with filter logic that doesn't account for the transitional state | Add an explicit "unmigrated" sentinel state handled deliberately in filter logic during rollout, and validate 100% backfill completion before removing the transitional handling |
| Multi-tenant shared index performs well for most tenants but badly for a few very large or very small ones | One filter strategy applied uniformly across a tenant-size distribution spanning orders of magnitude | Tier tenants by size: brute-force/small in-memory search for tiny tenants, shared filtered index for mid-size, dedicated physical index for the largest |
| Denormalized ACL metadata on chunks is out of sync with the source permission system | No reliable sync/backfill mechanism, or a sync job with unmonitored lag | Build explicit staleness monitoring on the sync pipeline; treat ACL staleness beyond a defined SLA as a security incident, not a data-quality nice-to-have |

---

## Tradeoffs & when NOT to use it

- **Don't assume any vector database's default filter behavior is safe for your selectivity distribution without testing it.** Pinecone's default post-filtering is fast on average but wrong for highly selective filters unless you oversample; pgvector's plain HNSW-then-filter has the same issue without `iterative_scan` or partitioning. Test with your actual filter distribution, not a generic assumption.
- **Don't put ACL enforcement anywhere except the query itself.** Any design that retrieves first and checks authorization second has already created a window where unauthorized data can leak via logs, caches, timing, or a future code change that forgets the check — this is a correctness requirement, not a performance preference, and there is no acceptable "usually filters correctly" version of it.
- **Don't default to per-tenant physical index isolation for every product.** It's the right call for large, security-sensitive tenants but pure operational overhead — N times the indexes to build, monitor, and reindex — for a product with many small, low-risk tenants that a shared filtered index (or even brute-force per-tenant search) serves perfectly well.
- **Don't treat a high-cardinality filter as "just another field" in schema design.** It is measurably the expensive case for both pre- and post-filter strategies, and deserves explicit selectivity testing and a filter-aware index strategy before launch, not after the first incident.
- **Don't skip staleness monitoring on denormalized metadata**, especially ACL fields. Denormalization is the right call for query latency, but a stale ACL copy that lags the source of truth is a silent security gap, not merely a data-freshness inconvenience — the monitoring is not optional the way it might be for, say, a stale "popularity" ranking signal.

---

## Interview questions

### Q1 — Why does applying a metadata filter to a vector search break both the naive strategies people try first?
**Testing:** baseline understanding of why this is a real engineering problem, not a trivial WHERE clause.
**Answer:** Every ANN index (HNSW, IVF) is built assuming any indexed vector is a valid search target. Pre-filtering restricts the search to a subset with no ANN index built specifically over that subset, degenerating toward brute force. Post-filtering runs the unfiltered search first and discards non-matching results, which can silently return far fewer than k results when the filter is selective, since the greedy search never had a reason to route toward the filter-valid region of the graph.
**Follow-up trap:** *"Isn't post-filtering always safe since it's at least correct, just maybe slow?"* — no, it isn't just slow, it can be wrong: it can under-return results (including returning zero) even when hundreds of valid matches exist elsewhere in the corpus — this is a correctness/completeness failure, not merely a performance one.

### Q2 — Walk through the mechanism of post-filter under-return with a concrete number.
**Answer:** With a filter matching roughly 10% of the corpus and a default beam width like `ef_search=40`, an unfiltered top-40 search retrieves on average only about 4 filter-valid candidates by chance — well short of a `k=10` request, even though far more than 10 valid matches likely exist in the full filtered subset elsewhere in the graph. The greedy search never routed toward those, because it was never told the filter existed until after the fact.
**Follow-up trap:** *"Wouldn't raising ef_search fix this?"* — it helps somewhat (searching more of the graph increases the chance of hitting filter-valid regions) but doesn't fix the structural problem that the search still isn't routing *toward* the filter-valid region deliberately; it's a partial mitigation, not the fix, and costs latency proportionally.

### Q3 — Define cardinality and selectivity, and explain why a high-cardinality filter is the expensive case.
**Answer:** Cardinality is the number of distinct values a field can take; selectivity is what fraction of the corpus a specific value matches. A high-cardinality field like `tenant_id` with a million distinct values typically produces high selectivity per value (a tiny fraction of the corpus matches any one tenant), which is the worst case for both strategies: pre-filtering scans a small, unindexed-per-value subset, and post-filtering is exactly where under-return is most severe, since the unfiltered top-k is unlikely to contain many of that specific tenant's documents.
**Follow-up trap:** *"Is a low-cardinality field always cheap, then?"* — usually, but not if its distribution is skewed — a boolean field where 99% of documents are one value and 1% the other has low cardinality but the rare value has high selectivity, inheriting the same expensive-case behavior for that value specifically.

### Q4 — Why must ACL filtering be enforced in the query itself, not as a post-retrieval check?
**Answer:** If a query retrieves documents the user isn't authorized to see and filters them out afterward in application code, the unauthorized document's existence, snippet, or metadata may already have been logged, cached, briefly present in a response payload, or exposed via a timing/count side channel — before the discard step ever runs. This is a security correctness requirement: the ineligible data must never leave the boundary, not merely be removed before the user notices.
**Follow-up trap:** *"What if the post-hoc filter runs in milliseconds, so the exposure window is tiny?"* — the exposure isn't about human-visible timing, it's about anything downstream of retrieval (logging, caching, a bug in the filter logic, a future code change) that can capture the unfiltered result before the filter runs; a "small window" framing misses that the real risk is any code path that reads results before the check, not the check's latency.

### Q5 — Compare RBAC and ABAC in the context of retrieval filtering, and why do production systems move toward ABAC?
**Answer:** RBAC attaches permissions to roles and roles to users — simple to reason about and audit, but coarse-grained. ABAC computes permissions from attributes of the user, resource, and context (e.g. department match, clearance level vs. sensitivity level), supporting finer-grained and more dynamic access rules. Production systems move toward ABAC as access requirements grow more contextual (e.g. "user can see this document if in the same department AND clearance is sufficient," which RBAC's fixed roles express awkwardly), accepting more complex policy evaluation at query time as the cost.
**Follow-up trap:** *"Does ABAC replace RBAC entirely?"* — no, many production systems layer them — RBAC for coarse role-based gates, ABAC for finer contextual rules on top — rather than treating it as an either/or choice.

### Q6 — Design the metadata schema and multi-tenancy strategy for a SaaS RAG product with tenants ranging from 100 to 5 million documents.
**Testing:** synthesis of schema design, filter cost, and tenant-size skew.
**Answer:** Denormalize `tenant_id`, ACL, and other filterable fields directly onto chunk records to avoid query-time joins. Given the four-order-of-magnitude size skew, don't apply one strategy uniformly: smallest tenants (low hundreds to low thousands of documents) can use brute-force or in-memory search, trivially fast and sidestepping the filtered-ANN problem entirely; mid-size tenants share a filtered index with a filter-aware strategy (ACORN-style or iterative scan); the largest tenants get dedicated physical index isolation, since at that size the operational cost of a separate index is justified by both performance and blast-radius isolation. ACL is enforced as a query-time filter in all three tiers, never as a post-retrieval check, regardless of which tier's performance strategy is in play.
**Follow-up trap:** *"What's the operational cost of this tiered approach compared to one uniform strategy?"* — real: three different code paths to maintain and monitor instead of one, and a tenant-size-classification step that itself needs to be kept current as tenants grow; the honest answer names this cost rather than presenting tiering as a free win.

### Q7 — What's the tradeoff between denormalizing metadata onto chunks versus looking it up at query time from a source-of-truth table?
**Answer:** Denormalization avoids a per-query join/round-trip to a separate store, which matters because vector databases generally don't support efficient joins and an extra network round-trip adds real latency to every retrieval call. The cost is staleness risk: the denormalized copy can drift out of sync with the source of truth (e.g. an ACL change) until the next sync/backfill runs.
**Follow-up trap:** *"How would you bound the staleness risk for something security-sensitive like ACLs?"* — explicit staleness monitoring and an SLA on sync lag, with staleness beyond that SLA treated as a security incident rather than a routine data-quality issue, since ACL staleness specifically has security implications a stale popularity score doesn't.

### Q8 — A pgvector-backed filtered query that used to return in milliseconds now takes seconds. What's your diagnostic path?
**Answer:** Check whether filter selectivity changed — a new tenant or a data-growth event can shift what fraction of the corpus a given filter value now matches, pushing the query from a cheap, high-selectivity case (post-filter mostly fine) into an expensive one requiring `hnsw.iterative_scan` or a partial index/partition that wasn't previously necessary. Confirm by measuring current selectivity for the affected filter value directly rather than assuming.
**Follow-up trap:** *"What if selectivity hasn't changed, and it's something else?"* — check for a build-memory or index-bloat issue (deletions on an HNSW index tombstone rather than truly remove, degrading graph quality over time per `03-vector-index-internals`) or concurrent write contention as alternate causes before concluding it's purely a filter-selectivity problem.

### Q9 — Why is schema evolution (adding a new filterable field) usually cheap, but changing an existing field's type or semantics is not?
**Answer:** Adding a new field is typically a metadata backfill only — writing a value onto existing chunk records — since the vector itself doesn't need to change, no re-embedding required. Changing an existing field's type or meaning (boolean to enum, redefining what a status value means) requires auditing every code path and index assumption tied to the old semantics, and a partial rollout where some chunks are migrated and others aren't can produce silently inconsistent filtering behavior for the duration of the migration.
**Follow-up trap:** *"How would you safely roll out a field-semantics change without a full reindex?"* — introduce an explicit transitional/sentinel state that filter logic handles deliberately during the migration window, and gate removal of that transitional handling on verified 100% backfill completion, not an assumed completion time.

### Q10 — Your team wants to switch from a shared index with metadata filtering to per-tenant physical sharding for security reasons. What's the migration risk?
**Answer:** The migration itself is a window where two enforcement mechanisms coexist — some tenants on the old shared-index-plus-filter model, some already moved to isolated shards — and any code path that assumes one model uniformly (a query router, a monitoring dashboard, an ACL-check helper) can silently misbehave for tenants in the transitional state. There's also a real operational cost step-change: moving from one shared index to N physical shards multiplies build/monitor/reindex work by tenant count, which needs capacity planning before the migration starts, not discovered during it.
**Follow-up trap:** *"Is per-tenant sharding strictly more secure, justifying the cost regardless?"* — it removes one class of risk (filter-vs-graph reconciliation bugs) but doesn't replace the ACL-in-query requirement within each shard, and introduces new operational failure modes (a misconfigured shard router sending a tenant's query to the wrong shard) that a single well-audited shared-index-plus-filter system doesn't have — it's a different risk profile, not an unambiguous security upgrade.

### Q11 — Why is oversampling before post-filtering only a mitigation, not a fix?
**Answer:** Oversampling (requesting `k * factor` candidates before filtering) increases the chance enough filter-valid results appear in the larger candidate set, reducing under-return frequency, but doesn't change the underlying mechanism — the search still isn't routing toward the filter-valid region deliberately, so a filter selective enough (or an oversample factor small enough) can still under-return. It also costs proportionally more compute per query as the factor grows.
**Follow-up trap:** *"How would you choose the oversample factor?"* — measure empirically against your actual filter-selectivity distribution and required `k`, and treat under-return events (even after oversampling) as a monitored metric, not something to tune once and forget, since selectivity can shift over time as data grows.

### Q12 — Staff-level: a customer reports that after a routine ingest pipeline update, some of their search results started including documents from a different customer's tenant. Walk through your incident response and root-cause process.
**Testing:** synthesis under a security-incident framing.
**Answer:** Treat this as a security incident first, correctness investigation second — determine immediately whether the ACL/tenant filter is being applied as a query-time condition or a post-retrieval check; if it's post-retrieval, that's very likely the root cause on its own, since any bug or ordering issue in application code can leak results before the check runs. Check the recent ingest pipeline change specifically for whether it altered how `tenant_id`/ACL metadata gets denormalized onto chunks (a sync bug writing the wrong tenant_id, or a race condition during backfill). Audit logs and caches for whether the leaked cross-tenant data was already exposed downstream of the query, not just whether it's currently visible. Only after containment and root-cause confirmation would remediation include moving enforcement to a query-time filter if it wasn't already, and adding database-level row-level security as defense-in-depth against a recurrence from a different code path.
**Follow-up trap:** *"What if the filter was already correctly enforced in the query, and this was a data-pipeline bug instead?"* — then the incident is about denormalized metadata correctness, not enforcement architecture — trace the ingest pipeline's tenant_id assignment logic specifically for the change that shipped, and add validation (e.g. a post-ingest consistency check comparing chunk tenant_id against source document tenant_id) to catch this class of bug before it reaches production next time.

---

## Red flags that fail you

- Treating a metadata filter as "just a WHERE clause" with no awareness of pre/post-filter failure modes.
- Not knowing that post-filtering can silently return fewer than k results, including zero.
- Implementing ACL as a post-retrieval check rather than a query-time filter.
- Not distinguishing cardinality from selectivity, or not knowing why high-cardinality filters are the expensive case.
- Applying one multi-tenancy strategy uniformly across a tenant base with wildly different sizes.
- Assuming denormalized metadata staleness is a minor data-quality issue when it involves ACLs.
- Believing a full reindex is always required to add a new filterable field.

---

## Cheat card

```
EVERY VECTOR QUERY IS   nearest-neighbors WHERE filter holds. No mainstream ANN
    index (HNSW/IVF) was built with filtering in mind.

PRE-FILTER    filter first, search filtered subset -- no index over that subset
              -> degenerates toward brute force as selectivity narrows.
POST-FILTER   search first (unfiltered), discard non-matches after -- can
              SILENTLY under-return (even zero) on selective filters, because
              greedy graph search never routed toward the filter-valid region.
              Concrete: 10% selectivity + ef_search=40 -> ~4 valid results avg,
              even if k=10 requested and hundreds of valid docs exist elsewhere.

CARDINALITY   # distinct values a field can take.
SELECTIVITY   fraction of corpus one value matches.
    High-cardinality (tenant_id, millions of values) = high selectivity per
    value = the EXPENSIVE case for BOTH pre- and post-filter.

FIXES   iterative scan (pgvector hnsw.iterative_scan) · multi-hop expansion
        (Weaviate ACORN, auto-selects strategy since v1.34) · filterable HNSW +
        adaptive planner (Qdrant) · oversample k*factor before filtering
        (mitigates, doesn't eliminate) · physical per-tenant isolation
        (sidesteps the problem entirely, costs N indexes to manage)

ACL RULE (non-negotiable)   filter MUST be in the query itself. NEVER retrieve
    then discard in app code -- unfiltered data can leak via logs/cache/
    timing/future-code-change before the post-hoc check runs.

RBAC   permissions on roles -- simple, coarse.
ABAC   permissions from user+resource+context attributes -- finer-grained,
       more complex to evaluate. Prod systems layer both, not either/or.

MULTI-TENANCY   shared index+filter (simple, inherits pre/post-filter cost) vs
    per-tenant physical shard (isolated, N-times ops cost). Size-skewed tenant
    bases (100 to 5M docs) usually need TIERED strategy, not one for all.

DENORMALIZE metadata onto chunks (avoid query-time joins) BUT monitor staleness
    explicitly -- stale ACL copy = security gap, not just a freshness nit.

SCHEMA EVOLUTION   new field = metadata backfill only, no reindex/re-embed
    needed. Changing a field's TYPE/semantics = real migration, needs a
    transitional sentinel state + validated 100% backfill before cutover.
```

## Sources

- [How we speed up filtered vector search with ACORN — Weaviate](https://weaviate.io/blog/speed-up-filtered-vector-search) — accessed 2026-08-01
- [The Achilles Heel of Vector Search: Filters — Bits & Backprops](https://yudhiesh.github.io/2025/05/09/the-achilles-heel-of-vector-search-filters/) — accessed 2026-08-01
- [pgvector Limitations — ParadeDB](https://www.paradedb.com/learn/postgresql/pgvector-limitations) — accessed 2026-08-01
- [HNSW index bypassed when LIMIT or filter selectivity exceeds threshold — pgvector/pgvector Issue #721](https://github.com/pgvector/pgvector/issues/721) — accessed 2026-08-01
- [Attribute Filtering in Approximate Nearest Neighbor Search: An In-depth Experimental Study (arXiv:2508.16263)](https://arxiv.org/pdf/2508.16263) — accessed 2026-08-01
- [Rethinking Vector Search at Scale: Weaviate's Native, Efficient and Optimized Multi-Tenancy](https://weaviate.io/blog/weaviate-multi-tenancy-architecture-explained) — accessed 2026-08-01
- [Curator: Efficient Indexing for Multi-Tenant Vector Databases (arXiv:2401.07119)](https://arxiv.org/pdf/2401.07119) — accessed 2026-08-01
- [Select & configure vector indexes — Weaviate Documentation](https://docs.weaviate.io/weaviate/tutorials/vector-indexing-deep-dive) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
