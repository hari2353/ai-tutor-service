# Elasticsearch: Inverted Index, Segments, Refresh/Flush/Merge, Scoring

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T17-elasticsearch` · **Tags:** search

## The 30-second version

Elasticsearch is Lucene's inverted index (term → sorted list of document IDs, "posting lists") wrapped in a distributed, JSON-native, horizontally-sharded service. The write path is the mechanical core of almost every operational question: a document lands in an in-memory buffer and the translog simultaneously, becomes searchable only after a **refresh** (default every 1 second) turns the buffer into a new immutable Lucene segment, becomes crash-durable only after a **flush** commits segments and clears the translog, and segment count is kept bounded by background **merges** — so "why isn't my just-indexed document showing up in search" is answered by refresh timing, and "why did indexing get slow" is very often answered by refresh interval or merge pressure. Scoring defaults to **BM25** (replacing classic TF-IDF as Lucene's and Elasticsearch's default since ~2016), which adds term-frequency saturation and document-length normalization that plain TF-IDF lacks. The single most common self-inflicted wound is a mapping mistake: a `text` field gets analyzed (tokenized, lowercased) at index time, so an exact-match query (`term` query, aggregation) against it silently returns nothing because the query string never matches a token the way the raw value would — the fix is a `keyword` sub-field, which is why Elasticsearch's dynamic mapping gives you both by default. Oversharding (too many small shards, each carrying real per-shard memory and cluster-state overhead) is the classic capacity-planning failure, with 10-50GB as the commonly recommended per-shard size band.

## Why this gets asked

The interviewer has been on the other end of a search index that returned zero results for a query that "should obviously match" (the text/keyword mapping trap), or has watched cluster health go yellow/red and node heap climb because someone provisioned a thousand tiny shards for a dataset that needed ten. They want to know if you understand the refresh/flush/merge pipeline well enough to explain near-real-time search's actual latency floor, and whether you know the difference between a query (contributes to score, not cached the same way) and a filter (boolean yes/no, cacheable) well enough to design an efficient request.

---

## Lineage: past → present → future

**What came before.** Before inverted-index search engines, "search" over unstructured text in a database meant `LIKE '%term%'` scans or, at best, a database's built-in full-text index bolted onto a system designed for structured row lookups — both scale badly because they either scan every row or maintain an index poorly suited to ranked relevance rather than exact/prefix match. Apache Lucene (Doug Cutting, 1999) established the inverted index plus TF-IDF scoring as the standard toolkit for text search, but it was a Java library, not a service — every team wanting search had to build the sharding, replication, and API layer themselves. The pain that created Elasticsearch (Shay Banon, 2010, building on Lucene) and its contemporary Solr: teams kept re-solving "how do I run Lucene as a horizontally scalable, JSON-native, RESTful service with replication and near-real-time visibility" from scratch.

**Where it stands now.** Elasticsearch (and its OpenSearch fork, created in 2021 after Elastic's license change to SSPL/Elastic License, itself later partially reversed with AGPL as a further option) is the default choice for log/observability search, e-commerce/site search, and increasingly hybrid lexical+vector retrieval. BM25 has been the default similarity since Lucene 6 / Elasticsearch 5 (2016), with classic TF-IDF still available but not the default anywhere current. The live disagreement is over how far to push Elasticsearch into the vector-search space: it added `dense_vector` fields and HNSW-based approximate kNN (and reciprocal-rank-fusion hybrid queries), which is enough for teams that already run Elasticsearch and want "good enough" vector search without adding infrastructure, but dedicated vector databases still lead on pure ANN recall/latency tradeoffs at very large scale and on vector-specific operational features. What's actually deployed at scale: Elasticsearch/OpenSearch clusters for logs and text search almost universally use `keyword`+`text` multi-fields, ILM (index lifecycle management) for time-series log rollover, and increasingly `search_after` instead of `from`/`size` for any pagination beyond the first page or two.

**Where it's heading.** Elastic's continued investment in native vector/hybrid search (RRF as a first-class fusion method, ELSER for sparse learned retrieval) signals a bet that "one engine for lexical, sparse, and dense retrieval" wins over stitching together separate systems for teams whose scale doesn't demand a dedicated vector database; confidence is moderate to high given the pace of shipped features. More speculative: whether serverless Elasticsearch (Elastic Cloud Serverless, abstracting away shard/node management entirely) becomes the default operational model is still playing out — it directly targets the oversharding and capacity-planning failure modes this module covers by removing the decision from the user, but it's new enough that "how it's done in production" for most existing large deployments still means hand-managed shard counts and ILM policies.

---

## Mental model

```
INVERTED INDEX (the whole point)

  doc1: "the quick brown fox"        term      -> posting list (doc ids, positions)
  doc2: "the lazy fox sleeps"        ─────────────────────────────────────────
                                     "fox"    -> [doc1, doc2]
  Forward index (what a row store    "quick"  -> [doc1]
  has): doc -> terms.                "lazy"   -> [doc2]
  Inverted index: term -> docs.      "the"    -> [doc1, doc2]
  Query "fox" = one posting-list
  lookup, not a scan of every doc.


WRITE PATH: buffer -> refresh -> segment -> flush -> merge

  index request
       │
       ▼
  [in-memory buffer]  +  [translog, fsync'd -- crash recovery record]
       │
       │  REFRESH (default every 1s, or on demand)
       ▼
  [new Lucene SEGMENT, immutable, now SEARCHABLE]  <── "near-real-time": ~1s lag
       │
       │  FLUSH (translog full, or periodic, or on shard close)
       ▼
  [segments fsync'd to disk, translog cleared]      <── now durable across crash
       │
       │  MERGE (background, ongoing)
       ▼
  [fewer, larger segments -- fewer files to check per query, deleted docs reclaimed]

  refresh = visibility (search can see it)
  flush   = durability (survives a crash without translog replay)
  merge   = efficiency (fewer segments to search, deleted docs actually removed)
  THESE ARE THREE DIFFERENT GUARANTEES -- don't conflate them.
```

---

## How it actually works

### Inverted index, posting lists, and analysis

A term's posting list is a sorted list of document IDs (plus term frequency and position data for phrase queries), which is why "find documents containing X" is a direct lookup rather than a scan — the cost is proportional to the posting list length and query complexity, not the corpus size. Getting text into that index correctly is the job of the **analyzer**: a tokenizer (split into terms, typically on whitespace/punctuation) plus a chain of token filters (lowercase, stemming, stop-word removal, synonyms). The analyzer used at index time and the analyzer used at query time both matter and can silently diverge if not configured deliberately — a query analyzer that doesn't lowercase against an index analyzer that does will never match.

**The mapping mistake that makes a field unsearchable for exact match:** a `text` field is analyzed — `"Redis Cluster"` gets tokenized and lowercased into `["redis", "cluster"]` as separate terms in the posting lists. A `term` query or a `terms` aggregation against a `text` field compares the *raw input string* against those individual tokens, so `term: {field: "Redis Cluster"}` matches nothing (no single token equals the whole phrase), while `match: {field: "redis cluster"}` (which itself gets analyzed before matching) works fine. The fix is a `keyword` field — unanalyzed, indexed as the exact raw string — either as the field's own type for anything needing exact match/sort/aggregation (tags, IDs, status enums) or as a `.keyword` multi-field alongside the analyzed `text` version, which is exactly why Elasticsearch's dynamic string mapping creates both by default.

### The Lucene write path: buffer, refresh, translog, flush, merge

This is the mechanical core interviewers actually probe, because it explains almost every "why is my data not showing up" or "why is indexing slow" question:

1. **In-memory buffer + translog.** An index request adds the document to an in-memory indexing buffer and appends it to the shard's **translog** (a write-ahead log, fsync'd per request or per `index.translog.durability` setting — `request` is the safer default, fsyncing every request; `async` batches fsyncs for higher throughput at the cost of a small durability window). The document is not searchable yet.
2. **Refresh** (default `index.refresh_interval: 1s`) closes the current in-memory buffer and opens it as a new, immutable Lucene **segment**, making its documents searchable. This is what "near-real-time" means precisely: a document is typically searchable ~1 second after being indexed, not instantly — genuinely real-time visibility would require refreshing on every single write, which craters indexing throughput because every refresh creates a new segment file and new segments cost merge overhead later.
3. **Flush** writes segments to disk with an fsync and clears the translog once its content is safely captured in committed segments (triggered by translog size threshold, default `512mb`, or time-based). This is the durability boundary: if the node crashes between refresh and flush, the translog is replayed on recovery to reconstruct anything not yet flushed — refresh alone does not protect against data loss on crash.
4. **Merge** runs continuously in the background, combining smaller segments into fewer, larger ones. This matters for two reasons: query cost scales with the number of segments a shard must check (each segment is queried independently and results merged), and merges are also when deleted/updated documents (Lucene never updates in place — an update is a delete-marked old doc plus a new doc) are actually physically reclaimed.

**The first knob under heavy indexing load:** raise `refresh_interval` (to 30s, 60s, or `-1` to disable entirely during a bulk load) — fewer, larger segments get created per unit time, which reduces merge pressure and indexing overhead at the direct cost of increasing search-visibility latency. This is the standard bulk-ingest playbook: disable refresh, bulk load, re-enable and force a refresh when done.

### Shards, replicas, routing, and the oversharding failure

An index is split into **primary shards** (fixed at index creation in older versions; some flexibility via `_split`/`_shrink` APIs exists but resharding is not a casual live operation), each of which is a complete, independent Lucene index — replicas are copies of primary shards for both availability and read throughput (a search request round-robins across a primary and its replicas). Routing determines which shard a document lands on (by default, a hash of its `_id`), which is why custom routing can co-locate related documents in one shard (analogous in spirit to Redis's hash tags) at the cost of potentially uneven shard sizes if routing keys aren't balanced.

**Oversharding**, the classic capacity-planning failure: too many small shards means the cluster carries real per-shard overhead (each shard has its own Lucene segment files, in-memory data structures, and contributes cluster-state metadata that every node must track), so a cluster with thousands of shards for a dataset that would comfortably fit in dozens spends memory and CPU on bookkeeping rather than serving queries — the **observable symptom** is climbing heap usage and degrading query/indexing latency that doesn't correlate with actual data volume growth, plus slow cluster state updates (mapping changes, index creation) as the cluster struggles to propagate state across so many shards. The commonly cited target is **10-50GB per shard** and keeping shard count proportional to actual data volume and node count, not defaulting to a fixed shard count per index regardless of size.

### Scoring: TF-IDF vs BM25, and explain

**TF-IDF** (the historical Lucene/Elasticsearch default before 2016) scores a term's contribution to a document as raw term frequency times inverse document frequency, with no cap on how much repeating a term helps and length normalization that doesn't saturate. **BM25** (the default since Lucene 6 / Elasticsearch 5) fixes both: term-frequency contribution **saturates** (the 5th occurrence of a word helps far less than the 2nd, via the `k1` parameter, default 1.2), and document-length normalization (`b`, default 0.75) accounts for the fact that a term appearing once in a 20-word document is more significant than once in a 2,000-word document, without over-penalizing long documents that are long because they're genuinely comprehensive rather than padded. The `_explain` API (or `explain: true` on a search request) returns the exact per-term, per-factor breakdown of how a document's score was computed — the concrete tool for "why did document A outrank document B" rather than guessing.

### Queries vs filters and the filter cache

A **query** clause contributes to relevance scoring (how well does this match, ranked). A **filter** clause is a yes/no boolean check with no scoring contribution — `bool.filter` and `bool.must_not` are filter context, `bool.must`/`bool.should` (outside a filter context) are query context. Filters are cacheable (Elasticsearch's filter cache can reuse a filter's bitset across repeated queries using the same filter, since the answer doesn't depend on scoring computation) and generally cheaper — the practical rule is push anything that's a hard yes/no condition (date range, status = "active", tenant_id = X) into `filter`, and reserve scored `must`/`should` clauses for the actual relevance-ranked text matching.

### Aggregations and their memory cost

Aggregations (terms, histograms, cardinality, etc.) execute per-shard and merge results at the coordinating node, which means a `terms` aggregation on a high-cardinality field builds a bucket per distinct value per shard before merging — directly analogous to a ClickHouse high-cardinality `GROUP BY`'s memory cost, and the reason `cardinality` aggregations use the approximate HyperLogLog++ algorithm rather than an exact distinct count by default (trading precision for bounded memory, configurable via `precision_threshold`). Deep or unbounded terms aggregations on genuinely high-cardinality fields (user IDs, full URLs) are the aggregation-side analog of the ClickHouse OOM failure mode.

### Deep pagination and search_after

`from`/`size` pagination requires each shard to compute and return `from + size` results, sort them, and have the coordinating node merge and re-sort across shards — cost grows with page depth, and Elasticsearch enforces a hard `index.max_result_window` (default 10,000) past which `from`/`size` throws an error rather than let a wildly deep page request degrade the cluster. `search_after` avoids this: it uses the sort values of the last document on the previous page as a cursor to fetch the next page directly, with cost independent of how deep into the result set you are, at the cost of not supporting arbitrary random-access jumps to page N (only sequential forward paging from a known cursor).

### Vector search in modern Elasticsearch

`dense_vector` fields support HNSW-based approximate kNN search natively (`knn` query clause), plus exact brute-force search when the field is configured without an HNSW index. Elasticsearch also supports hybrid retrieval combining lexical (BM25) and vector similarity scores via **Reciprocal Rank Fusion (RRF)** as a first-class fusion method, letting one request blend a `match` query and a `knn` clause into a single ranked result. This is covered in depth, including the HNSW mechanics themselves, in `T06-vector-index-internals`; the Elasticsearch-specific question is when to use it here versus a dedicated vector store, covered in `T17-vector-db-compare`.

---

## Build it from scratch

A minimal inverted index and BM25 scorer, the shape an interviewer may ask you to reason through or implement live:

```python
# untested sketch
import math
from collections import defaultdict, Counter

class MiniInvertedIndex:
    def __init__(self, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.postings: dict[str, dict[int, int]] = defaultdict(dict)  # term -> {doc_id: tf}
        self.doc_lengths: dict[int, int] = {}
        self.doc_count = 0

    def index(self, doc_id: int, text: str):
        terms = text.lower().split()  # toy tokenizer/analyzer
        self.doc_lengths[doc_id] = len(terms)
        self.doc_count += 1
        for term, tf in Counter(terms).items():
            self.postings[term][doc_id] = tf

    def _avg_doc_length(self) -> float:
        return sum(self.doc_lengths.values()) / max(1, len(self.doc_lengths))

    def _idf(self, term: str) -> float:
        df = len(self.postings.get(term, {}))
        # BM25 idf: near zero for terms in almost every doc, grows for rare terms
        return math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))

    def score(self, query: str, doc_id: int) -> float:
        avgdl = self._avg_doc_length()
        dl = self.doc_lengths[doc_id]
        total = 0.0
        for term in query.lower().split():
            tf = self.postings.get(term, {}).get(doc_id, 0)
            if tf == 0:
                continue
            idf = self._idf(term)
            # BM25 term-frequency saturation + length normalization
            num = tf * (self.k1 + 1)
            den = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
            total += idf * (num / den)
        return total

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        candidates = set()
        for term in query.lower().split():
            candidates.update(self.postings.get(term, {}).keys())
        scored = [(d, self.score(query, d)) for d in candidates]
        return sorted(scored, key=lambda x: -x[1])[:top_k]
```

This omits phrase queries (position data in postings), field-length norms per field, and any distributed/sharding concerns — it demonstrates the actual arithmetic of BM25's saturation (`k1`) and length normalization (`b`) terms, which is the part people can describe in words but rarely have implemented. Full lab with segment-merge simulation and a toy refresh/flush pipeline: `(lab pending)`.

---

## How it's done in production

Managed/self-managed Elasticsearch and OpenSearch clusters use **ILM (Index Lifecycle Management)** to roll over time-series indices (logs/metrics) by age or size, moving older indices to cheaper storage tiers (hot/warm/cold/frozen) and eventually deleting them, rather than one ever-growing index. Ingest pipelines and the `_bulk` API are the standard high-throughput write path (batched requests, same batching logic as any other system with a per-request overhead). Cross-cluster replication and snapshots (to object storage) handle DR.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| A `term` query or aggregation on a text field returns zero/wrong results despite obviously-present data | Field is mapped as `text` (analyzed), and the query is comparing against raw tokens incorrectly, or vice versa | Use the `.keyword` sub-field for exact match/aggregation/sort; use `match` (which analyzes the query) against the `text` field for full-text search |
| Newly indexed documents don't appear in search for up to ~1 second | Expected near-real-time behavior; refresh hasn't run yet | Nothing to fix under normal load; call `_refresh` explicitly only when a test or workflow genuinely needs synchronous visibility, not as a routine post-index step |
| Indexing throughput craters under heavy bulk load | Default 1s refresh interval creating many small segments, heavy merge pressure | Raise `refresh_interval` (or set to `-1`) during bulk loads; re-enable and force a refresh afterward |
| Cluster heap usage climbs and query/indexing latency degrades independent of actual data volume | Oversharding — too many small shards, each carrying per-shard memory and cluster-state overhead | Consolidate via reindexing into fewer, larger shards (target ~10-50GB/shard); use `_shrink`/`_split` where applicable; fix the sharding strategy going forward, not just this index |
| `from`/`size` pagination throws past 10,000 results, or is simply very slow near that limit | Deep pagination requires each shard to compute and sort `from + size` results before merging | Use `search_after` with a stable sort (commonly `_id` or a tiebreaker) for sequential deep paging instead |
| A `cardinality` aggregation gives an approximate, slightly-off distinct count | HyperLogLog++ under the hood by default, trading exactness for bounded memory on high-cardinality fields | Raise `precision_threshold` for better accuracy at higher memory cost, or accept the ~single-digit-percent error as by design |
| A node OOMs or gets very slow during a large `terms` aggregation | High-cardinality bucket aggregation building per-shard buckets that don't collapse until the coordinating node merges them | Set a reasonable `size`/`shard_size` on the aggregation, use `composite` aggregations for paging through high-cardinality buckets instead of one giant terms agg |

---

## Tradeoffs & when NOT to use it

- **Don't treat Elasticsearch as a system of record.** It has no multi-document ACID transactions, and while the translog provides crash recovery for the *search index itself*, using it as your only copy of business-critical data is a well-known anti-pattern; keep a durable primary store and index into Elasticsearch as a derived, rebuildable copy.
- **Don't use `from`/`size` for deep pagination.** It's fine for the first page or two of typical UI pagination; beyond that it costs real memory/CPU per shard and hits a hard ceiling (`max_result_window`, default 10,000) — use `search_after` for anything genuinely paging deep, or `point in time` + `search_after` for a consistent view across pages.
- **Don't default to `text` for every string field.** If a field is ever going to be used for exact match, sorting, or aggregation, it needs a `keyword` mapping (or sub-field); getting this wrong after documents are already indexed generally requires a reindex, not a mapping update, since analyzed tokens for existing documents don't retroactively change.
- **Don't create a fixed number of shards per index regardless of data size.** Oversharding is the single most common Elasticsearch capacity mistake; size shards to the data (roughly 10-50GB each) and node capacity, not to a habit.
- **For structured, relational queries with real joins and multi-row transactional consistency**, Elasticsearch is the wrong tool — it has no genuine join (only weaker approximations like `nested`/`has_child` queries with real limitations), and denormalizing everything into documents to work around that is a sign the data actually belongs in a relational store.
- **For pure vector similarity search at very large scale with heavy filtering and multi-tenancy needs**, a dedicated vector database can out-perform Elasticsearch's `dense_vector`/HNSW implementation on pure ANN recall/latency tradeoffs — Elasticsearch's vector search is the right call when you already run it for lexical search and want "good enough" hybrid retrieval without new infrastructure, not automatically the right call for a green-field, vector-only, massive-scale system (see `T17-vector-db-compare` for the detailed comparison).

---

## Interview questions

### Q1 — Walk through what happens between indexing a document and it becoming searchable.
**Testing:** the write path, the mechanical core of this module.
**Answer:** The document is added to an in-memory buffer and appended to the shard's translog. It is not searchable at this point. A refresh (default every 1 second) closes the buffer and opens it as a new immutable Lucene segment, at which point it becomes searchable — this is what "near-real-time" means. Separately, a flush later commits segments to disk with an fsync and clears the translog, which is the durability boundary, not the visibility boundary.
**Follow-up trap:** "So does refresh make it durable too?" — no; refresh only affects visibility to search. If the node crashes after a refresh but before a flush, the translog is replayed on recovery — the data survives because of the translog, not because a refresh happened.

### Q2 — Why does `refresh_interval` matter for bulk indexing performance, and what's the standard mitigation?
**Answer:** Every refresh creates a new segment, and more frequent refreshes under heavy write load means more, smaller segments created per unit time, which increases merge pressure later and directly costs indexing throughput. The standard bulk-load playbook: raise `refresh_interval` (or set `-1` to disable it) during the bulk load, then re-enable and optionally force a refresh once done.
**Follow-up trap:** "Does disabling refresh mean documents are lost until you re-enable it?" — no, they're still safely in the translog (and eventually flushed); they're just not searchable yet. Nothing about disabling refresh affects durability, only visibility latency.

### Q3 — A `term` query for `"Redis Cluster"` against a mapped-as-`text` field returns nothing, even though a document contains exactly that string. Why?
**Testing:** the single most common real-world mapping mistake.
**Answer:** The `text` field is analyzed at index time — `"Redis Cluster"` becomes separate lowercased tokens (`"redis"`, `"cluster"`) in the posting lists, not the original phrase. A `term` query compares the raw, unanalyzed input string against the index's tokens directly, so it never matches a multi-token phrase against individually-stored tokens.
**Follow-up trap:** "How do you fix it without changing the query type?" — you can't fully fix it by only changing the query for exact whole-string matching; you need a `keyword` field (its own field or a `.keyword` multi-field) which stores the raw unanalyzed string, and query that field with `term` instead. Switching the query to `match` instead would work but changes the semantics to analyzed partial matching, not exact matching.

### Q4 — Explain BM25's two key parameters and what problem each one solves relative to plain TF-IDF.
**Answer:** `k1` (default 1.2) controls term-frequency saturation — repeated occurrences of a term contribute diminishing returns to the score rather than scaling linearly forever, which TF-IDF doesn't cap. `b` (default 0.75) controls document-length normalization — it discounts term frequency relative to how long the document is compared to the average, so a term appearing once in a short document scores higher than once in a long one, without over-penalizing long documents that are long because they're comprehensive.
**Follow-up trap:** "What happens if you set b to 0?" — length normalization is disabled entirely; long and short documents are scored as if length didn't matter, which usually hurts relevance for corpora with widely varying document lengths, but can be appropriate for corpora where length genuinely carries no relevance signal (e.g., short, uniform-length fields like titles).

### Q5 — What's the difference between a query and a filter, and why does it matter for performance?
**Answer:** A query clause contributes to the relevance score; a filter clause (`bool.filter`, `bool.must_not`) is a yes/no boolean check with no scoring contribution. Filters are cacheable — Elasticsearch can reuse the computed bitset for a filter across repeated requests using the same filter, since the result doesn't depend on any per-query scoring math — and are generally cheaper to execute.
**Follow-up trap:** "So should everything go in a filter?" — no, only clauses that are genuinely binary yes/no conditions (date ranges, exact-match status fields, tenant scoping); anything contributing to how well a document matches a search intent (actual text relevance) needs to be in query context to affect ranking, or you lose the relevance signal entirely.

### Q6 — What causes oversharding, and what's the observable symptom in production?
**Answer:** Provisioning far more shards than the data volume and node count justify — each shard carries real per-shard memory overhead and contributes cluster-state metadata every node must track, so a cluster with thousands of small shards spends resources on bookkeeping instead of serving queries. Observable symptom: climbing heap usage and degrading query/indexing latency that doesn't correlate with actual data growth, plus slow cluster-state operations (mapping updates, new index creation) as state propagation struggles across too many shards.
**Follow-up trap:** "What's the fix once you're already oversharded?" — reindexing into fewer, larger shards (targeting roughly 10-50GB each) using `_reindex`, or `_shrink` for read-only indices; there's no live in-place way to simply reduce a primary shard count on an existing index without moving the data.

### Q7 — Why does `from`/`size` pagination get slow and eventually error out past 10,000 results, and what replaces it?
**Answer:** Each shard must compute and sort `from + size` results before the coordinating node merges and re-sorts across shards, so cost grows with page depth even though you only want a small slice — Elasticsearch enforces `index.max_result_window` (default 10,000) as a hard ceiling to prevent this from degrading the cluster. `search_after` replaces it for deep paging: it uses the sort values of the last document on the current page as a cursor to fetch the next page directly, with cost independent of depth, at the cost of only supporting sequential forward paging from a known cursor rather than random-access jumps to an arbitrary page.
**Follow-up trap:** "Can you jump straight to page 500 with search_after?" — no, you need the cursor value from page 499, which means true random-access deep pagination isn't supported by either mechanism cheaply; if that's a real product requirement, it usually means the UI pattern itself needs to change (e.g., to infinite scroll or filtering instead of numbered deep pages).

### Q8 — Why is a `cardinality` aggregation approximate by default, and what's the actual mechanism?
**Answer:** It uses the HyperLogLog++ algorithm under the hood, trading exactness for bounded memory — an exact distinct count on a high-cardinality field would require holding proportionally large per-shard state, similar to a hash-table-per-distinct-value approach. `precision_threshold` lets you trade more memory for tighter accuracy up to a configurable cardinality, beyond which the approximation error grows.
**Follow-up trap:** "When would you need exact counts instead?" — for anything with legal/billing/compliance implications (exact unique-user counts for invoicing), where the approximate error is unacceptable — in that case you need a different mechanism entirely (e.g., a `terms` aggregation with exact bucket counting on a bounded cardinality field, or computing the exact count outside Elasticsearch).

### Q9 — When would you use Elasticsearch's native vector search instead of a dedicated vector database?
**Testing:** whether they can reason about this rather than defaulting to "always use a dedicated vector DB."
**Answer:** When you already run Elasticsearch for lexical/log/document search and want to add semantic or hybrid retrieval without introducing new infrastructure, especially when hybrid lexical+vector queries (via RRF) on the same documents matter more than squeezing out the absolute best ANN recall/latency numbers. A dedicated vector database is the better call at very large vector-only scale, with heavy filtering/multi-tenancy requirements that push past what Elasticsearch's filtering-plus-HNSW implementation handles well.
**Follow-up trap:** "What's the actual tradeoff you're making by choosing Elasticsearch's vector search?" — you get one engine and one operational surface for both lexical and vector needs, at the cost of not having the most specialized, highest-throughput ANN implementation available; that's a real engineering tradeoff, not a free lunch, and the right answer depends on whether vector search is a core, scale-critical capability or a complement to existing text search.

### Q10 — Design a sharding strategy for a new time-series log index expected to ingest 500GB/day, retained for 30 days.
**Testing:** applying oversharding, ILM, and shard sizing together.
**Answer:** Use ILM to create daily (or size-based) rolling indices rather than one giant index, sized so each index's primary shards land in the ~10-50GB target range — at 500GB/day that likely means several primary shards per daily index, sized by testing actual segment sizes rather than guessing. Configure ILM to age indices from hot (fast storage, actively written) to warm/cold tiers as they age past the active-write window, and delete automatically past the 30-day retention. Avoid a fixed shard count per index chosen without reference to this math.
**Follow-up trap:** "What if actual daily volume varies 5x day to day?" — this is exactly why size-based rollover (roll to a new index once the current one hits a target size) is often preferable to purely time-based rollover for volume-variable workloads — it keeps shard sizes in the target band regardless of day-to-day volume swings, at the cost of index boundaries no longer aligning cleanly with calendar days.

### Q11 — What's the difference between the translog and the segments on disk, in terms of what each protects?
**Answer:** The translog is a write-ahead log of raw index operations, fsync'd (per-request by default) as a crash-recovery mechanism — on unclean shutdown, unflushed operations are replayed from it. Segments are the actual searchable, immutable Lucene data structures (inverted index, doc values, etc.) — durable once flushed to disk, but not the primary durability mechanism for data between flushes; that's the translog's job.
**Follow-up trap:** "If flush already writes segments to disk, why keep the translog around at all after a flush?" — a new translog generation starts fresh after each flush to protect exactly the operations that happen *after* that flush and before the next one; it's continuously protecting whatever hasn't yet been captured in a committed segment, not a one-time artifact.

### Q12 — Staff-level: your search relevance quality is reported as "wrong" by users for certain queries. How do you actually investigate, mechanically?
**Testing:** synthesis — scoring internals plus a real debugging workflow.
**Answer:** Run the query with `explain: true` (or the `_explain` API against a specific document) to get the exact BM25 breakdown — term frequency, inverse document frequency, and length normalization contributions per matching term — rather than guessing at relevance tuning blind. Check whether the mapping matches intent (is a field being matched as analyzed text when it should be exact keyword, or vice versa, which would explain systematically wrong result sets rather than just wrong ranking). Check query-vs-filter placement, since a clause incorrectly placed in query context when it should be a hard filter can distort scoring by contributing to relevance when it should just be an eligibility gate.
**Follow-up trap:** "What if `explain` shows the scoring math is working as designed, but users still think it's wrong?" — that's a relevance-tuning problem, not a bug: it means the scoring function itself (BM25's default weighting of term frequency and length) doesn't match this specific domain's notion of relevance, which calls for query-time boosting, custom similarity parameters, function score adjustments, or a learning-to-rank layer, not a mechanical fix.

---

## Red flags that fail you

- Not knowing that `refresh_interval` (default 1s) is why "near-real-time" is not "real-time," or conflating refresh with flush.
- Recommending `term`/`terms` queries against a `text` field without recognizing the mapping mismatch.
- Not knowing the default scoring function is BM25, or being unable to name what `k1`/`b` do.
- Treating query and filter context as interchangeable, missing the caching/scoring distinction.
- Not knowing `from`/`size` has a hard depth ceiling (`max_result_window`, default 10,000) or what replaces it.
- Recommending "just add more shards" without recognizing oversharding's own real cost.
- Treating Elasticsearch as a system of record with no durable primary store behind it.

---

## Cheat card

```
INVERTED INDEX   term -> sorted posting list of doc IDs (+tf, positions)
                 analyzer = tokenizer + filters (lowercase, stem, stopwords)
                 index-time and query-time analyzer MUST agree or matches silently fail

MAPPING TRAP     text = analyzed (tokenized) -> term/terms query on it fails for
                 whole-string exact match. keyword = unanalyzed, exact.
                 FIX: use .keyword sub-field for exact match/sort/agg

WRITE PATH       buffer+translog -> REFRESH (default 1s) -> new SEARCHABLE segment
                          -> FLUSH (translog full/periodic) -> fsync'd, DURABLE
                          -> MERGE (background) -> fewer/larger segments, reclaims deletes
                 refresh=visibility, flush=durability, merge=efficiency -- 3 different things
                 heavy bulk load: raise refresh_interval or -1, re-enable after

SCORING          BM25 default since Lucene 6 / ES 5 (2016), replaced TF-IDF
                 k1 (default 1.2) = term-frequency saturation
                 b  (default 0.75) = document-length normalization
                 _explain / explain:true = exact per-term score breakdown

QUERY vs FILTER  query = scored, contributes to ranking
                 filter (bool.filter/must_not) = yes/no, CACHEABLE, cheaper
                 push hard conditions (date range, tenant, status) into filter

SHARDS           target 10-50GB/shard; oversharding symptom = heap climbs +
                 latency degrades with NO data-volume correlation + slow cluster
                 state updates. Fix = reindex into fewer/larger shards, not "add more"

PAGINATION       from/size: cost grows with depth, hard ceiling
                 index.max_result_window default 10,000
                 search_after: cursor from last doc's sort values, depth-independent,
                 sequential only (no random page jumps)

AGGS             terms/cardinality build per-shard buckets before merge --
                 high-cardinality = memory risk, same shape as OOM'ing GROUP BY
                 cardinality agg = approximate (HyperLogLog++) by default

VECTOR SEARCH    dense_vector + HNSW-based knn query; RRF = default hybrid fusion
                 method for lexical+vector. Good when already on ES; dedicated
                 vector DB wins at very large pure-vector scale + heavy filtering
```

## Sources

- [Elasticsearch index.refresh_interval: Defaults, Tuning, and Tradeoffs — Pulse](https://pulse.support/kb/elasticsearch-index-refresh-interval) — accessed 2026-08-01
- [Elasticsearch scoring and Explain API — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/elasticsearch-scoring-and-explain-api) — accessed 2026-08-01
- [Practical BM25 - Part 2: The BM25 Algorithm and its Variables — Elastic Blog](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables) — accessed 2026-08-01
- [Size your shards — Elastic Docs](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/size-shards) — accessed 2026-08-01
- [Elasticsearch Oversharding — Opster](https://opster.com/guides/elasticsearch/capacity-planning/elasticsearch-oversharding/) — accessed 2026-08-01
- [Paginate search results — Elasticsearch Reference](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results) — accessed 2026-08-01
- [Elasticsearch: Text vs. Keyword — Medium (Sajal Agarwal)](https://medium.com/@sajalgrwl91/elasticsearch-text-vs-keyword-5790a62ac36b) — accessed 2026-08-01
- [kNN search in Elasticsearch — Elastic Docs](https://www.elastic.co/docs/solutions/search/vector/knn) — accessed 2026-08-01
- [Elasticsearch hybrid search: Overview & hybrid search queries — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/hybrid-search-elasticsearch) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
