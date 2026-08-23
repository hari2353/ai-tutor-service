# Production notes -- the semantic cache

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Exact-match store | Python dict | Redis/Memcached, TTL'd |
| Prefix match | linear scan over a list | a trie, or rely on the transformer's own KV cache (Anthropic `cache_control`, OpenAI automatic prefix caching) instead of re-serving a stored response at all |
| Semantic match | linear scan over cached vectors | a real ANN index (FAISS/HNSW/pgvector/Qdrant) once the cache holds more than a few thousand entries |
| Query embeddings | given as fixed test fixtures | a real embedding model call, ideally the *same* model used for the corpus, cached itself |
| Threshold | a single global constant | per-item adaptive thresholds with a formal error-rate bound (vCache, Feb 2025) or at minimum per-query-type tuned constants |
| Invalidation | none (out of scope for this lab) | TTLs plus explicit invalidation hooked to the source-of-truth changing |
| Multi-tenant isolation | none (out of scope for this lab) | tenant id baked into every cache key and every similarity search's candidate set, never a global similarity search across tenants |

## What the real ones add over yours

- **Adaptive, per-item thresholds, not one global number.** This lab's centerpiece
  test proves a single threshold forces a hit-rate/wrong-answer tradeoff. The
  reason production systems increasingly move to per-item adaptive thresholds
  (vCache, arXiv:2502.03771) is that the *right* cutoff genuinely differs by query
  cluster -- a threshold tuned for "what's your refund policy" (where a false hit
  is a real, visible failure) is not the right threshold for "what's the capital of
  France" (where near-neighbors are essentially always correct). A single static
  number either over-serves false hits on the first cluster or under-serves valid
  hits on the second; there is no single value that's simultaneously right for both.
- **A real embedding model, not a fixture.** The threshold tradeoff this lab
  demonstrates is about the CACHE LOGIC, not embedding quality -- but in
  production, embedding quality *sets the ceiling* on how good any threshold can
  be. A model that embeds "cancel my subscription" and "cancel my subscription
  renewal" close together but doesn't reliably separate "monthly plan" from
  "annual plan" queries makes the false-hit problem worse no matter where you set
  the knob.
- **Invalidation wired to the source of truth.** This lab's cache never goes
  stale because nothing in it ever changes. A real cache sits in front of content
  that changes -- pricing pages, policies, docs -- and a cached response with no
  invalidation path serves confidently wrong (but no-longer-true) answers
  indefinitely. The fix is boring and mandatory: TTLs as a floor, explicit
  invalidation hooks as the real mechanism.
- **Tenant isolation baked into the search, not bolted on.** A semantic cache
  shared across tenants without a tenant filter in the similarity search itself
  is a data leak: tenant A's cached response can be served to tenant B's
  semantically-similar query. This has to be structural (filter the candidate set
  before or during the ANN search), not a post-hoc check after retrieval.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| A support ticket: customer got a wrong answer that "sounded right" | Semantic threshold set too low for a query cluster where near-neighbors have materially different correct answers | Treat the threshold as a correctness/safety boundary, not a performance knob -- validate it against a labeled (query, correct-answer) set like this lab's 14-query fixture, per query type |
| Cache hit rate silently drops after a product/pricing change | No invalidation path; stale entries linger and now correctly miss on new phrasing but the STALE ones that still "match" old phrasing serve outdated answers | Invalidate on source-of-truth change, not just on TTL expiry |
| Semantic search gets slower every week | Linear scan over a growing cache (same failure mode as unindexed dense retrieval) | Move to a real ANN index before it's the bottleneck |
| Tenant A sees tenant B's cached answer | No tenant filter in the similarity search's candidate set | Partition the index by tenant, or filter candidates before scoring, never after |
| Hit rate looks great in the dashboard, users complain anyway | Hit rate alone doesn't measure correctness -- it's silent on whether hits were RIGHT | Track wrong-answer rate (or a proxy: user correction rate, thumbs-down rate on cache-served responses) as a first-class metric next to hit rate, always |
| Threshold that worked at launch degrades over months | Traffic mix drifts -- new query types arrive that the original threshold was never validated against | Re-validate the threshold (or re-learn it, if adaptive) periodically against fresh labeled samples, not just once at launch |

## Cost & latency

Exact-match and prefix-match layers are essentially free -- a dict lookup or a
short linear scan, microseconds. Semantic match's cost is dominated by the query
embedding call (one per cache-miss-candidate request, cents or less, tens of
milliseconds) plus the similarity search itself (milliseconds with a proper ANN
index, worse with a linear scan past a few thousand entries). The payoff is the
downstream LLM call it prevents -- often hundreds of milliseconds to seconds and a
real per-token cost -- so even an imperfect semantic cache is usually a large net
win *if* the wrong-answer rate is controlled. An uncontrolled one isn't a cost
optimization, it's a correctness bug that happens to also save money most of the
time.

## The 3 questions an interviewer asks after you describe this

1. *"Your dashboard shows 40% hit rate on the semantic layer. What's your
   wrong-answer rate?"* -- if the honest answer is "we don't measure that," that's
   the whole interview. Hit rate without a paired correctness metric is a vanity
   number; this lab's test file is built specifically so you can't get away with
   reporting one without the other.
2. *"Why not just set the threshold very high and eliminate false hits
   entirely?"* -- because hit rate collapses toward zero and the cache stops
   paying for itself; the tradeoff is real and directional, not something you can
   engineer away with a single "safe" constant -- see the centerpiece test's own
   numbers.
3. *"What happens when the underlying answer changes -- say, a pricing update --
   and the cache doesn't know?"* -- this is the invalidation question, and "we
   have a TTL" is a partial answer at best; the real answer needs an explicit path
   from "source of truth changed" to "cached entries invalidated," not just time
   decay.
