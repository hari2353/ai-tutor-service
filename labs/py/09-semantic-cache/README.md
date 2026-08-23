# Lab 09: A Three-Layer Semantic Cache

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.5h · **XP:** 50
**Module:** `T06-semantic-caching`

**You will build:** exact-match, prefix-match, and cosine-similarity semantic-match
caching layers, orchestrated in priority order, and measure -- with real numbers,
not a claim -- what happens to hit rate and wrong-answer rate as you tune the
semantic layer's similarity threshold.

**You will be able to answer:** *"You shipped a semantic cache and the hit rate
looked like free money. How do you know it isn't quietly serving wrong answers,
and where exactly is that failure mode controlled?"*

## Setup

```bash
cd labs/py/09-semantic-cache
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                          # only dependencies
```

## The spec

1. **`ExactCache`** -- byte-identical match after normalization (lowercase,
   trimmed, whitespace-collapsed). Catches idempotent retries and duplicate
   requests. No similarity involved -- either it's the same query or it isn't.
2. **`PrefixCache`** -- serves a cached response when the query starts with a
   previously cached prefix at least `min_prefix_len` characters long. When more
   than one stored prefix matches, the **longest** one wins (most specific, safest).
3. **`SemanticCache`** -- nearest-neighbor cosine similarity search over cached
   query vectors. Serves the closest entry's response **only if** its similarity
   clears `threshold`; otherwise it's a miss, even though a "closest" entry
   technically exists. Query vectors are given to you as fixed fixtures -- there
   is no embedding model in this lab, just like a real cache is handed a vector by
   whatever embedding service already ran.
4. **`LayeredCache`** -- orchestrates all three: exact, then prefix, then semantic,
   in that order (cheapest and highest-confidence first). Returns a `CacheResult`
   telling you which layer served the hit (or that it was a miss).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

The centerpiece test, `test_lowering_threshold_raises_hit_rate_and_wrong_answer_rate`,
sweeps the semantic threshold across four settings (0.90 → 0.80 → 0.70 → 0.60) on a
fixed 14-query, relevance-judged set -- 6 true paraphrases that should always match
correctly, and 8 "confusable" queries engineered to resemble the **wrong** cached
topic at a specific, known similarity. It asserts hit rate *and* wrong-answer rate
both rise, strictly, at every step. That's the whole point of this lab: the
tradeoff isn't a sentence in a doc, it's a number you can watch move.

## Stretch goals

1. **Per-item adaptive thresholds (vCache-style)** -- instead of one global
   threshold, learn a per-cached-entry threshold online from observed hit/miss
   outcomes, targeting a fixed error-rate budget. Show it beats the best single
   global threshold on the same 14-query set.
2. **Tenant isolation** -- add a `tenant_id` to every cache key/vector lookup and
   write a test proving one tenant's query can never be served from another
   tenant's cached entry, even at similarity 1.0.
3. **Cache invalidation** -- add a `invalidate(topic_id)` that removes a semantic
   entry (simulating "the underlying answer changed"), and a test proving a query
   that used to hit that entry now correctly misses instead of serving stale data.
4. **LLM-judge verification** -- sketch (pseudocode is fine) a fourth check that
   runs *after* a semantic hit clears threshold: a cheap verifier call that
   confirms the cached response actually answers the new query before serving it.
   What does this cost in latency, and when is it worth paying?
