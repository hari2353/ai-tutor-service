# Semantic Caching: Exact + Semantic + Prefix Layers, vCache, Hit-Rate Tuning

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.5h · **Prereqs:** 03-vector-index-internals, 14-metadata-design · **Updated:** 2026-08-01
> **Module id:** `T06-semantic-caching` · **Tags:** production,critical
> **Lab:** `labs/py/15-semantic-cache/`

## The 30-second version

A production LLM caching stack is three layers, not one: exact-match caching catches byte-identical repeats (idempotent retries, identical system calls), prefix/prompt caching reuses the transformer's KV cache for a shared prompt prefix regardless of what comes after it, and true semantic caching embeds the query and serves a stored response for anything that lands within a similarity threshold of a past query — the only layer of the three that can serve a *paraphrase* it has never seen verbatim. That threshold is the entire ballgame: set it too low and you serve confidently wrong answers for queries that are topically adjacent but materially different (a false hit — "refund policy for annual plans" matching "refund policy for monthly plans" at 0.95+ cosine similarity despite opposite answers), set it too high and the cache's hit rate collapses toward zero because almost nothing clears the bar. Static, hand-tuned thresholds are fragile because the right threshold varies by query type and drifts as traffic shifts, which is why adaptive, per-item verified thresholds (vCache, Feb 2025) that give a formal error-rate guarantee are now demonstrably better than any fixed number, reporting up to 12.5x higher hit rate at the same error budget in published benchmarks. Get the boring parts wrong and semantic caching does real damage: no invalidation path when the underlying corpus changes serves stale answers indefinitely, and no tenant isolation in the cache key turns it into a data leak between customers. It is also frequently the wrong tool entirely — personalized, time-sensitive, or high-stakes queries should not be served from a similarity match at all.

## Why this gets asked

The interviewer has shipped a semantic cache that looked like a free 40% cost reduction in the dashboard, then watched a support ticket come in from a customer who got a materially wrong answer because their query happened to embed close enough to someone else's cached question. They want to know whether you treat the similarity threshold as a tunable performance knob (wrong) or as a correctness/safety boundary that has to be set with the same rigor as a filter selectivity decision (right), and whether you know the specific ways a cache silently goes stale or silently leaks across tenants.

---

## Lineage: past → present → future

**What came before.** Early LLM-serving stacks either cached nothing (every request hit the model) or reused classical web-caching patterns wholesale: hash the exact request bytes (model, parameters, full prompt string) and look up an exact match, the same approach HTTP caching has used for decades. The pain was structural, not a tuning problem: LLM queries carry enormous latent redundancy in *intent* — thousands of users asking "how do I reset my password" in dozens of phrasings — but almost none of that redundancy is byte-identical, so an exact-match cache measured hit rates near zero on real production traffic despite the obvious repetition a human skimming the logs could see immediately. A second, separate pain showed up specifically in multi-turn and RAG workloads: re-sending a long, unchanged system prompt or retrieved-context block on every turn re-paid the full prefill cost of that prefix every single call, even though nothing about it had changed since the previous turn.

**Where it stands now.** The two pains got two different fixes that are often confused for the same thing. Prompt/prefix caching (Anthropic's `cache_control` breakpoints, shipped August 2024; OpenAI's automatic prefix caching, shipped October 2024) solves the second pain by reusing the transformer's KV cache for a prefix that matches byte-for-byte up to a cache breakpoint — it is not semantic at all, it is an exact-prefix optimization, and it only helps when the *shared* portion of the prompt is unchanged, not when the whole query is a paraphrase. Semantic caching (GPTCache, 2023, and its descendants) solves the first pain by embedding the query and matching against past queries by cosine similarity above a threshold, which is the only mechanism of the three that generalizes across phrasing. Both are now standard, deployed in production LLM gateways side by side, and treated as complementary layers rather than alternatives. The live disagreement in semantic caching specifically is the threshold: static, globally-tuned thresholds (0.85–0.97 depending on how conservative the deployment needs to be) are still the majority default in production because they're simple to reason about, but published research (vCache, arXiv:2502.03771, Feb 2025) demonstrates that a single static threshold is provably suboptimal — it either over-serves false hits on some query clusters or under-serves valid hits on others, because the right similarity cutoff genuinely differs by query and topic, not just by deployment.

**Where it's heading.** Per-item, formally-verified adaptive thresholds (vCache's approach: an online-learned threshold per cached entry with a user-specified error-rate bound) are real, published, and outperforming static and fine-tuned-embedding baselines on the reported benchmarks — moderate-to-high confidence this becomes standard in mature semantic-caching products over the next few years, low confidence it's already the default in most production deployments today, since static thresholds remain far more common in current tooling (GPTCache, most vendor semantic-cache offerings) as of 2026. A second, more speculative direction: using a cheap LLM-judge call to verify a candidate cache hit before serving it (trading a small verification cost for much higher confidence than similarity alone provides) — this shows up in research and in a few production gateways but is not yet a settled pattern, and it reintroduces some of the latency the cache exists to remove, so its net value is workload-dependent rather than a clear win.

---

## Mental model

Three layers, ordered by how much paraphrase-tolerance they buy you and how much risk that tolerance costs:

```
  EXACT MATCH             hash(model + params + full prompt bytes) -> O(1) lookup
  (narrowest hit rate,    catches: literal retries, idempotent repeated calls
   zero correctness risk)  misses: any paraphrase, any changed whitespace/casing

              │ doesn't hit → fall through
              ▼
  PREFIX / PROMPT CACHE   reuse the transformer's KV cache for a prefix that
  (medium hit rate,       matches byte-for-byte up to a cache breakpoint
   zero correctness risk,  catches: same system prompt / retrieved context,
   NOT semantic)            different final turn
                           misses: anything where the SHARED prefix itself changed

              │ doesn't hit → fall through
              ▼
  SEMANTIC CACHE           embed the query, ANN lookup against past
  (broadest hit rate,      (query embedding, response) pairs, serve if
   REAL correctness risk)  cosine similarity > threshold
                           catches: paraphrases, near-duplicate intent
                           risk: FALSE HIT if threshold too loose -- serves a
                                 confidently wrong answer for a materially
                                 different query that merely embeds close
```

The first two layers are free lunches: a hit is always correct because the match is exact (identical bytes, or an identical shared prefix). The third layer is the only one that can be *wrong on a hit* — similarity is a proxy for "should share an answer," not a guarantee of it, and the threshold is where you decide how much of that proxy error you're willing to eat in exchange for a hit rate an exact-match layer could never reach.

---

## How it actually works

### Layer 1: exact-match caching

Hash the fully normalized request — model id, all sampling parameters, and the complete prompt text (including system prompt and any injected context) — and look up a dictionary/KV store entry. Zero correctness risk because a hit means byte-identical input, which by construction should produce the same output for temperature-0 or otherwise deterministic settings. Real-world hit rate on raw production traffic is typically low, because most repeated *intent* isn't repeated *bytes* — but it's the cheapest layer to implement and should always run first, since it's strictly free of the correctness risk the other layers carry.

### Layer 2: prefix / prompt caching (KV cache reuse)

This is not semantic caching, and conflating the two is a common mistake. A transformer's attention computation over a prompt prefix produces key/value tensors that are identical every time that exact prefix is processed; prefix caching stores those KV tensors and reuses them for any subsequent request sharing the same prefix up to a marked breakpoint, skipping the prefill compute for that portion entirely.

**Anthropic** (`cache_control` breakpoints, shipped August 2024): a cache write costs 1.25x the base input rate for a 5-minute TTL, or 2.0x for a 1-hour TTL; a cache read costs 0.1x the base input rate — a 90% discount. Accessing a cached block resets its TTL, so high-frequency traffic against a stable system prompt or retrieved-context block rarely pays the write cost more than once per warm-up.

**OpenAI** (automatic prefix caching, shipped October 2024, no code changes required): only caches prefixes of at least 1,024 tokens — shorter prompts never hit this layer at all. Cache retention defaults to 24 hours. Cache reads on current-generation models get up to a 90% discount; cache writes carry no separate fee on most model families, though newer families have begun introducing a 1.25x write premium mirroring Anthropic's model.

Because this layer requires byte-identical prefix match, it does nothing for a paraphrased query — it only helps when the *unchanged* part of the prompt (system instructions, a retrieved document block, conversation history up to the current turn) is being resent as-is, which is extremely common in RAG and multi-turn chat but orthogonal to the semantic-caching problem.

### Layer 3: true semantic caching

Embed the incoming query, run an ANN lookup (`03-vector-index-internals`) against a store of past `(query embedding, response)` pairs, and serve the stored response if similarity exceeds a threshold. GPTCache's reference architecture names the moving parts explicitly: an embedding generator, a vector store for the ANN lookup, a **similarity evaluator** (GPTCache supports exact match, embedding-distance, or an ONNX model as the evaluator — the evaluator is a separate, swappable decision function from the raw similarity score itself), and an eviction policy (LRU or FIFO by cache count, plus TTL).

**The threshold is the whole ballgame.** Reported production guidance clusters around: start at 0.92, monitor the false-positive rate (cache hits that return a wrong answer) for 48 hours, and adjust in small increments; 0.92–0.95 is typical for English FAQ-style traffic; 0.97 is the conservative choice for a first deployment (low hit rate, roughly 5–10%, but false-positive rate under 0.5%). None of these numbers are universal — they are starting points to validate against your own traffic and error tolerance, exactly like chunk size in `01-chunking` or the pre/post-filter choice in `14-metadata-design`.

### The false-hit failure mode, concretely

Embedding-close is not meaning-equal, and the failure has a specific, reproducible shape: two queries that differ in exactly the dimension that matters for the answer — a time period, a plan tier, a polarity — routinely land above 0.90 cosine similarity because everything *else* about the sentence is identical.

```
Cached query:    "What is your refund policy for annual plans?"
                  → cached answer: "Annual plans are refundable within 30 days."

New query:       "What is your refund policy for monthly plans?"
                  → cosine similarity to cached query: ~0.95+ (differs by one word)
                  → served the SAME cached answer: "Annual plans are refundable
                    within 30 days." — WRONG if monthly plans are non-refundable.
```

The observable symptom in production is not a crash or an error log — it's a confidently wrong answer delivered at cache-hit speed, which is worse for user trust than a slow correct answer, and it will not show up in latency or cost dashboards at all, only in complaint volume or a downstream accuracy eval. The reported "dangerous zone" for this failure in practice is roughly 0.88–0.94 cosine similarity: topically related, differing in exactly the token that changes the answer, often just clearing a loosely-set threshold. Time-period swaps ("MAU in Q1 2024" vs. "MAU in Q1 2025"), polarity swaps ("revenue growth" vs. "revenue decline"), and tier/plan swaps are the recurring shapes of this bug across reported production incidents.

### Adaptive and verified thresholds: why static thresholds are fragile

A single global threshold assumes one number is right for every query cluster in the corpus, which is false in two specific ways: some clusters (rigid FAQ phrasing, narrow domain) tolerate a looser threshold safely because near-paraphrases genuinely share an answer there, while others (anything with an embedded parameter — a date, a plan name, a quantity) need a much tighter threshold because the embedding space doesn't cleanly separate "same intent" from "same intent, different parameter." A static threshold tuned as a compromise across both cases either serves false hits on the fragile clusters or throws away valid hits on the safe ones.

**vCache** (Verified Semantic Prompt Caching, arXiv:2502.03771, Feb 2025) is the first system to give a formal, user-specified error-rate guarantee per cached entry rather than a single global cutoff: it runs an online learning algorithm that estimates an optimal similarity threshold *per cached prompt*, using observed outcomes to calibrate confidence rather than trusting the raw cosine score at a fixed cutoff. Reported results: up to 12.5x higher cache hit rate and 26x lower error rate than static-threshold and fine-tuned-embedding baselines at a matched error budget — the gain comes specifically from not forcing every query cluster through the same threshold.

### Invalidation when the corpus changes

A semantic cache entry is a frozen answer to a past query, and if the underlying RAG corpus changes — a document is updated, a policy changes, a price changes — every cache entry whose answer depended on the old version is now silently wrong, with no natural expiry unless one is built in. Three practical strategies, in increasing order of correctness and operational cost:

- **TTL-only.** Simplest: every entry expires after a fixed window regardless of whether the source changed. Cheap to implement, but serves stale answers for the entire TTL after a real change, and evicts perfectly valid entries early when nothing changed — a blunt instrument in both directions.
- **Event-driven invalidation.** Tie cache entries to the specific document/chunk IDs that fed their answer (tracked as metadata on the cache entry, mirroring the provenance metadata discussed in `17-data-structuring`), and invalidate specifically the entries touched by a reindex or document update event. More precise, requires the ingestion pipeline to emit invalidation events the cache layer can consume.
- **Versioned cache namespaces.** Key the entire cache by a corpus/index version identifier, so a reindex effectively creates a fresh cache namespace and the old one ages out naturally without needing per-entry dependency tracking. Simple to reason about, but a full reindex means starting the cache cold rather than surgically invalidating only what changed.

### Hit-rate measurement and the cost/latency arithmetic

Report at least two numbers, not one: **hit rate** (fraction of queries served from cache) and **positive hit rate** or false-positive rate (fraction of *those hits* that were actually correct) — a high hit rate with an unmeasured false-positive rate tells you nothing about whether the cache is helping or quietly damaging answer quality. Published semantic-cache systems report both: one representative system reports cache hit rates of 61.6%–68.8% depending on query category, with a positive-hit-rate (correctness-of-hits) figure above 97%, which is the number that actually matters for whether the hit rate is trustworthy.

**Worked example.** Assume an LLM call costs $0.003 and takes 800ms p50 end-to-end; a semantic-cache hit costs one embedding call plus a vector lookup, roughly $0.0001 and 20ms. At 1,000,000 queries/day and a measured 40% hit rate:

```
cost without cache:   1,000,000 * $0.003                         = $3,000/day
cost with cache:      400,000 * $0.0001 + 600,000 * $0.003        = $40 + $1,800 = $1,840/day
savings:              $3,000 - $1,840 = $1,160/day (~39% reduction)

latency, blended p50: 0.4 * 20ms + 0.6 * 800ms = 8 + 480 = 488ms
                       (vs. 800ms with no cache -- a ~39% reduction, tracking the hit rate directly)
```

The savings percentage tracks the hit rate almost exactly here because the cache-hit cost/latency is close to negligible relative to a full LLM call — this is why hit rate is the headline metric, but it is meaningless without the accompanying false-positive rate, since a 40% hit rate built on a threshold loose enough to also produce a 5% false-hit rate is not a win, it's 20,000 wrong answers a day served with false confidence.

### Per-tenant isolation as a security requirement

A shared semantic cache across tenants is a data-leak channel, not merely a correctness risk: if tenant A's query embeds close enough to a cached response generated for tenant B, tenant A can receive an answer built from tenant B's private data. This is the same principle as ACL-aware filtering in `14-metadata-design` — the isolation boundary must be enforced as a **hard filter in the cache lookup itself**, not as a post-hoc check on a returned cache entry: cache keys/namespaces should include tenant_id (and, where relevant, locale, model version, and any safety/compliance flag) as a non-negotiable component of the lookup, never as an afterthought applied to whatever the similarity search happened to return. Never share one global semantic cache across different organizations or privilege levels; this is explicitly called out as a real attack surface (semantic cache poisoning and cross-tenant leakage) in current caching-security writeups, not a theoretical concern.

---

## Build it from scratch

```python
# untested sketch — illustrates the three-layer fallthrough and a simplified
# vCache-style per-item adaptive threshold; not a production cache
import hashlib
import time
import numpy as np


def exact_key(model: str, params: dict, prompt: str) -> str:
    normalized = f"{model}|{sorted(params.items())}|{prompt.strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


class SemanticCache:
    """Naive static-threshold semantic cache — always tenant-scoped."""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.entries: list[dict] = []  # {tenant_id, embedding, query, response, ts, ttl}

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def get(self, tenant_id: str, query_embedding: np.ndarray, now: float):
        # tenant_id filters the candidate set FIRST — never a post-hoc check,
        # mirroring the ACL-in-query rule from 14-metadata-design
        candidates = [e for e in self.entries if e["tenant_id"] == tenant_id and e["ts"] + e["ttl"] > now]
        if not candidates:
            return None
        best = max(candidates, key=lambda e: self._cosine(e["embedding"], query_embedding))
        sim = self._cosine(best["embedding"], query_embedding)
        return best["response"] if sim >= self.threshold else None

    def put(self, tenant_id: str, query: str, query_embedding: np.ndarray, response: str, ttl: float = 3600):
        self.entries.append({
            "tenant_id": tenant_id, "query": query, "embedding": query_embedding,
            "response": response, "ts": time.time(), "ttl": ttl,
        })


class AdaptiveThresholdEntry:
    """Simplified vCache-style idea: learn a per-entry threshold from observed
    correct/incorrect outcomes rather than trusting one global cutoff."""

    def __init__(self, initial_threshold: float = 0.9, error_rate_target: float = 0.02):
        self.threshold = initial_threshold
        self.error_rate_target = error_rate_target
        self.outcomes: list[bool] = []  # True = hit was correct, False = false hit

    def record_outcome(self, was_correct: bool):
        self.outcomes.append(was_correct)
        recent = self.outcomes[-50:]
        observed_error_rate = 1 - (sum(recent) / len(recent))
        # tighten the threshold if observed error exceeds target; relax if well under it
        if observed_error_rate > self.error_rate_target:
            self.threshold = min(0.999, self.threshold + 0.01)
        elif observed_error_rate < self.error_rate_target / 2:
            self.threshold = max(0.5, self.threshold - 0.005)
```

The parts a real system adds that this sketch skips: GPTCache's pluggable similarity evaluators (embedding distance is only one option; an ONNX cross-encoder-style evaluator can double-check a candidate hit more precisely than raw cosine similarity), vCache's actual statistical estimator (a proper online confidence-bound method, not the crude moving-error-rate heuristic above), and event-driven invalidation wired to the ingestion pipeline rather than TTL alone.

---

## How it's done in production

**Semantic cache libraries**: GPTCache (Zilliz, open-source, modular embedding/vector-store/evaluator/eviction components, integrates with LangChain and LlamaIndex). **Managed/infra-level**: Redis semantic caching (RedisVL) combining vector similarity with hard metadata filters (tenant, locale, model version) enforced in the query, reporting tens-of-milliseconds cache-hit latency versus multi-second LLM round trips and 30%+ token-spend reduction on workloads with repeated query patterns. **Prefix/prompt caching**: Anthropic `cache_control` breakpoints, OpenAI automatic prefix caching — both operate below the application layer and require no similarity logic at all. **Research/adaptive**: vCache (arXiv:2502.03771) as the reference implementation for verified, per-item adaptive thresholds, with released benchmarks.

| Symptom | Cause | Fix |
|---|---|---|
| A user gets a confidently wrong answer that reads like it's about a *related but different* topic | False hit — similarity threshold too loose for a query pair differing in exactly the parameter that changes the answer (date, tier, polarity) | Tighten the threshold for that query cluster, add a cheap verification step (structured entity/parameter match on top of similarity), or move to an adaptive per-item threshold (vCache-style) |
| Cache hit rate looks great but a downstream accuracy eval quietly drops | Hit rate was measured without a paired false-positive/positive-hit-rate metric | Always report positive hit rate alongside raw hit rate; sample and manually verify a slice of hits, not just misses |
| A tenant occasionally receives data or answers that reference another tenant's content | Semantic cache shared across tenants with no hard tenant filter in the lookup itself | Make tenant_id (and locale/model version) a mandatory component of the cache key/namespace, enforced in the lookup query, never as a post-retrieval check |
| Answers stay wrong for hours/days after a source document was corrected | No invalidation path tied to corpus changes — TTL alone, or no TTL at all | Wire event-driven invalidation to the ingestion/reindex pipeline, or version the cache namespace by corpus/index version |
| Prompt caching (Anthropic/OpenAI) shows near-zero hit rate despite a large, mostly-stable system prompt | Prefix changes slightly between requests (a timestamp, a per-request UUID, reordered fields) before the cache breakpoint, or the prompt is under OpenAI's 1,024-token minimum | Keep everything before the cache breakpoint byte-identical across requests; move volatile content (timestamps, session IDs) after the breakpoint or out of the cached prefix entirely |
| Cache hit rate degrades gradually over weeks with no code change | Traffic distribution drifted (new query types, new product features) away from what the static threshold was tuned against | Re-validate the threshold against current traffic periodically, the same discipline as re-running a recall@k eval after corpus or query-distribution shifts (`13-accuracy-tuning`) |

---

## Tradeoffs & when NOT to use it

- **Don't use semantic caching for personalized answers.** "What's my account balance" or "what did I order last week" have the same surface phrasing for every user but a different correct answer per user — a cache keyed on query similarity alone will confidently serve the wrong person's answer unless the user/account identity is a hard component of the cache key, and even then the value proposition mostly disappears since each user's query is now effectively unique.
- **Don't use it for time-sensitive information.** Stock prices, "what time is it," live inventory, breaking news — the correct answer changes independent of the query text, so any cache TTL longer than the information's actual freshness window serves a wrong answer by construction, and a TTL short enough to be safe often isn't long enough to be worth caching at all.
- **Don't use it for high-stakes, low-tolerance-for-error responses** — medical, legal, or financial advice where a false hit isn't merely annoying but has real consequences. The threshold-tuning problem doesn't disappear at any threshold setting; it only gets more expensive to accept the residual error rate.
- **Don't treat a high hit rate as success on its own.** A cache tuned loose enough to hit 60% of traffic but wrong on 5% of those hits is actively worse than no cache at all for user trust, even though every cost dashboard will show it as a win. Always pair hit rate with a measured or sampled correctness rate.
- **Don't skip invalidation planning because it's not needed on day one.** A cache with no path from "the corpus changed" to "affected entries are gone" accumulates silently stale answers from the first real content update onward, and the failure is invisible until someone notices an answer contradicts the current source document.

---

## Interview questions

### Q1 — Name the three caching layers in a production LLM stack and what each one catches.
**Testing:** baseline structural understanding, not just "there's a cache."
**Answer:** Exact-match (hash the full normalized request, catches byte-identical repeats, zero correctness risk), prefix/prompt caching (reuses the transformer's KV cache for a byte-identical shared prefix up to a cache breakpoint, zero correctness risk, not semantic), and true semantic caching (embeds the query, serves a stored response above a similarity threshold, the only layer that generalizes across paraphrasing — and the only one carrying real correctness risk).
**Follow-up trap:** *"Isn't prompt caching just a form of semantic caching?"* — no, prompt caching requires byte-identical prefix match; it does nothing for a paraphrased query and carries no similarity-threshold risk at all, which is the opposite failure profile from semantic caching.

### Q2 — Give a concrete example of a semantic-cache false hit and explain why it happens.
**Answer:** "What is your refund policy for annual plans?" and "...for monthly plans?" can embed above 0.95 cosine similarity since they differ by one word, but the correct answers may be opposite (30-day refund vs. non-refundable). It happens because embedding-space closeness reflects overall topical/lexical similarity, not whether the specific token that changes the answer was preserved.
**Follow-up trap:** *"Wouldn't a higher threshold fix this specific case?"* — only if the threshold is pushed high enough to exceed this pair's similarity, which also collapses hit rate on legitimately safe paraphrases elsewhere in the traffic; a single static threshold can't be simultaneously loose enough to be useful and tight enough to catch every parameter-swap case.

### Q3 — Why are static similarity thresholds fragile, and what does vCache do differently?
**Answer:** A single global threshold assumes one cutoff is correct for every query cluster, but some clusters tolerate looser matching safely (rigid FAQ phrasing) while others need much tighter matching (queries with an embedded date, tier, or quantity). vCache learns a threshold per cached entry online, with a formally specified error-rate target, rather than trusting one fixed cosine cutoff — reported results show up to 12.5x higher hit rate and 26x lower error rate than static-threshold baselines at a matched error budget.
**Follow-up trap:** *"Does an adaptive threshold eliminate false hits entirely?"* — no, it targets a *specified, bounded* error rate, not zero error; the guarantee is calibration to a chosen tolerance, not perfection, and the tolerance itself is a product decision.

### Q4 — What's the difference between hit rate and positive hit rate, and why do you need both?
**Answer:** Hit rate is the fraction of queries served from cache at all. Positive hit rate (or its complement, false-positive rate) is the fraction of *those hits* that were actually correct. A high hit rate with an unmeasured or unreported false-positive rate tells you nothing about whether the cache is net-helping — a loose threshold can produce an impressive hit rate built partly on wrong answers.
**Follow-up trap:** *"How would you measure positive hit rate in production without ground truth for every query?"* — sample a slice of hits for human or LLM-judge verification rather than checking every one; treat it like the error-analysis sampling discipline in `13-accuracy-tuning`, not an exhaustive audit.

### Q5 — Walk through the cost/latency arithmetic for a semantic cache at 40% hit rate, 1M queries/day, $0.003/query LLM cost, 800ms p50 latency.
**Answer:** Cost without cache: 1,000,000 × $0.003 = $3,000/day. With a ~$0.0001 cache-hit cost: 400,000 × $0.0001 + 600,000 × $0.003 ≈ $1,840/day, roughly a 39% reduction, tracking the hit rate closely since the hit cost is near-negligible. Blended p50 latency similarly drops from 800ms to about 488ms (0.4×20ms + 0.6×800ms).
**Follow-up trap:** *"Does the savings percentage always equal the hit rate?"* — only approximately, and only when cache-hit cost/latency is small relative to a full LLM call; if the embedding/ANN lookup cost or latency isn't negligible (e.g. a very large cache, an expensive embedding model), the savings percentage falls measurably short of the raw hit rate.

### Q6 — Why is per-tenant isolation a security requirement for semantic caches, not just a correctness nicety?
**Answer:** If tenant A's query embeds close enough to a cached response built from tenant B's data, tenant A can receive an answer derived from tenant B's private content — a genuine cross-tenant data leak, not merely a wrong-answer bug. The fix mirrors ACL-aware filtering (`14-metadata-design`): tenant_id must be a hard filter in the cache lookup query itself, never a property checked after a candidate is already retrieved.
**Follow-up trap:** *"Is namespacing by tenant_id sufficient on its own?"* — it's necessary but should extend to any other hard boundary that changes correctness (locale, model version, safety/compliance flags); a cache correct for one tenant across all locales isn't automatically correct across model versions if outputs differ by model.

### Q7 — How does prompt/prefix caching actually work mechanically, and why does it require byte-identical input?
**Answer:** A transformer computes key/value attention tensors for a prompt prefix; if a subsequent request shares that exact prefix up to a marked breakpoint, the KV tensors are reused and the prefill compute for that portion is skipped entirely. Because the KV tensors are a deterministic function of the exact token sequence, any change to the prefix — even a single character, a reordered field, or an injected timestamp — invalidates the match; there's no approximate or semantic version of this mechanism.
**Follow-up trap:** *"Why does OpenAI require at least 1,024 tokens for this to kick in?"* — below that length the prefill compute being saved is small enough that the caching machinery's overhead isn't worth it; this is a practical engineering cutoff, not a fundamental limit of the technique.

### Q8 — Design an invalidation strategy for a RAG semantic cache where the underlying document corpus updates daily.
**Answer:** Prefer event-driven invalidation: tag each cache entry with the document/chunk IDs that fed its answer (provenance metadata, `17-data-structuring`), and have the ingestion pipeline emit invalidation events for exactly the entries touched by a reindex or document update, rather than relying on TTL alone, which either serves stale answers for the whole TTL window or evicts unaffected entries too early. If per-entry dependency tracking is too costly to build initially, version the cache namespace by corpus/index version as a coarser but simpler fallback.
**Follow-up trap:** *"What if you can't cheaply determine which cache entries a given document update affects?"* — fall back to versioned namespaces (accept starting cold on every reindex) rather than shipping no invalidation at all; a cold cache after a real update is a performance cost, but stale answers indefinitely is a correctness cost, and the two aren't equally bad.

### Q9 — When is semantic caching actively the wrong choice?
**Answer:** Personalized answers (same phrasing, different correct answer per user), time-sensitive information (stock prices, live inventory, "what time is it") where correctness decays faster than any safe TTL, and high-stakes domains (medical/legal/financial advice) where the residual false-hit rate at any threshold setting carries real consequences rather than mild annoyance.
**Follow-up trap:** *"Could you cache personalized queries by including the user ID in the cache key?"* — technically yes, but then each user's queries are effectively unique, collapsing the cross-user hit rate that made caching valuable in the first place; you'd only gain from a single user re-asking the same question, a much smaller win.

### Q10 — A stakeholder wants "as high a cache hit rate as possible." How do you respond?
**Answer:** Hit rate alone isn't the objective — it's a tradeoff against false-hit rate, and pushing hit rate up by loosening the threshold directly increases the chance of confidently wrong answers. State the tradeoff explicitly, propose a target false-positive rate the business can tolerate (e.g. under 0.5% for a regulated product, more permissive for a low-stakes FAQ bot), and tune hit rate as high as possible *subject to* that error bound, ideally via an adaptive method rather than a single guessed threshold.
**Follow-up trap:** *"What if the stakeholder insists there's no error tolerance at all?"* — then semantic caching (the similarity-threshold layer specifically) may not be appropriate for that use case at all; exact-match and prefix caching still apply since they carry zero correctness risk, but the paraphrase-tolerant layer is exactly what a zero-error-tolerance requirement rules out.

### Q11 — What's the relationship between a cache's similarity evaluator and its raw embedding similarity score?
**Answer:** The similarity score (e.g. cosine similarity) is one input; the evaluator is the decision function that decides whether that score constitutes a hit. GPTCache treats these as separable — supporting exact-match, embedding-distance, or a trained ONNX model as the evaluator — because a more sophisticated evaluator (e.g. a small cross-encoder-style model) can catch cases where raw cosine similarity is misleadingly high despite a materially different query, at the cost of extra compute per lookup.
**Follow-up trap:** *"Doesn't adding an evaluator model defeat the latency purpose of caching?"* — it adds some latency versus a raw vector lookup, but that latency is still far below a full LLM call in almost all cases, so it's a legitimate way to trade a small amount of the cache's speed advantage for a large reduction in false-hit rate — a tradeoff worth making when false hits are costly.

### Q12 — Staff-level: design the caching architecture for a multi-tenant RAG customer-support product with 22 locales, where support policies vary by locale and change monthly.
**Testing:** synthesis of tenant isolation, locale-awareness, invalidation, and threshold discipline together.
**Answer:** Layer all three caches. Exact-match and prefix caching run first, keyed on the full normalized request including tenant_id and locale, carrying zero correctness risk regardless of scale. Semantic caching is namespaced by `(tenant_id, locale)` as a hard filter in the lookup query, never a post-hoc check, since both tenant leakage and cross-locale answer leakage (a French policy answer served for a German query that happens to embed close) are real risks here. Given monthly policy changes, use event-driven invalidation tied to the policy-document ingestion pipeline, scoped per locale, so an update to French policy documents invalidates only French-locale cache entries. Set the similarity threshold conservatively per locale rather than globally, ideally with an adaptive per-item approach, because query phrasing patterns and paraphrase risk differ by language (`12-multilingual`) and a single global threshold tuned on one locale's traffic characteristics won't transfer cleanly to another. Measure hit rate and positive-hit-rate per locale, not blended, mirroring the per-locale evaluation discipline this system needs everywhere else.
**Follow-up trap:** *"Isn't per-locale threshold tuning and per-locale invalidation a lot of operational surface area for a caching layer?"* — yes, and that's the honest tradeoff; a single global cache configuration is simpler to operate but structurally can't serve both the isolation and correctness requirements this specific product shape has, so the added complexity is justified by the stated constraints, not added for its own sake.

---

## Red flags that fail you

- Treating prompt/prefix caching and semantic caching as the same mechanism.
- Believing a higher cache hit rate is unambiguously better without mentioning false-positive rate.
- Proposing a single global similarity threshold with no plan to validate or adapt it against real traffic.
- Not knowing that a shared semantic cache across tenants is a data-leak vector, not just a correctness risk.
- Recommending semantic caching for personalized, time-sensitive, or high-stakes queries without flagging the mismatch.
- Shipping a semantic cache with no invalidation path tied to corpus changes.
- Not knowing that `efSearch`/ANN internals (`03-vector-index-internals`) apply to the semantic cache's own vector lookup just as much as to primary retrieval.

---

## Cheat card

```
THREE LAYERS   exact-match (hash full request, 0 risk) -> prefix/prompt cache
   (byte-identical prefix, KV reuse, 0 risk, NOT semantic) -> semantic cache
   (embedding similarity threshold, REAL correctness risk, only layer that
   generalizes across paraphrasing)

PROMPT CACHING   Anthropic (Aug 2024): write 1.25x (5min TTL) / 2.0x (1hr TTL),
   read 0.1x (90% off), TTL resets on access.
   OpenAI (Oct 2024, automatic): min 1024 tokens to cache, 24hr retention,
   up to 90% read discount on current models.

THRESHOLD   start 0.92, monitor false-positive rate 48h, adjust in 0.01 steps.
   0.92-0.95 typical FAQ. 0.97 = conservative first deploy (~5-10% hit rate,
   <0.5% false-positive). DANGER ZONE ~0.88-0.94: topically close, differs in
   the ONE token that changes the answer (date/tier/polarity swaps).

FALSE HIT EXAMPLE   "refund policy annual plans" vs "...monthly plans" ->
   ~0.95+ cosine sim, opposite correct answers.

vCACHE (arXiv:2502.03771, Feb 2025)   per-entry ONLINE-LEARNED threshold with
   a formal error-rate guarantee, not one global cutoff. Up to 12.5x higher
   hit rate, 26x lower error rate vs static-threshold baselines.

METRICS   hit rate (% served from cache) AND positive-hit-rate/false-positive
   rate (% of hits that were correct) -- report BOTH, always.
   Reference numbers: 61.6-68.8% hit rate, >97% positive-hit-rate (published
   semantic-cache system).

COST MATH (1M q/day, 40% hit, $0.003/query LLM, $0.0001/hit)
   no cache: $3,000/day. with cache: ~$1,840/day (~39% reduction, tracks hit
   rate since hit cost ~negligible). Latency 800ms -> ~488ms blended p50.

INVALIDATION   TTL-only (simple, serves stale + evicts early) < event-driven
   (tag entries with source doc/chunk IDs, invalidate on reindex) <
   versioned namespace (reindex = fresh namespace, simplest correctness).

TENANT ISOLATION   tenant_id (+locale+model version) MUST be a hard filter
   IN the cache lookup query -- never post-hoc. Shared cache across tenants
   = a real data-leak vector, not just a correctness bug.

WHEN NOT TO USE   personalized answers (same text, different truth per user)
   · time-sensitive info (price/inventory/"what time is it") · high-stakes
   domains (medical/legal/financial) where any false-hit rate is unacceptable
```

## Sources

- [vCache: Verified Semantic Prompt Caching (arXiv:2502.03771)](https://arxiv.org/abs/2502.03771) — accessed 2026-08-01
- [GPTCache: An Open-Source Semantic Cache for LLM Applications](https://github.com/zilliztech/gptcache) — accessed 2026-08-01
- [GPT Semantic Cache: Reducing LLM Costs and Latency via Semantic Embedding Caching (arXiv:2411.05276)](https://arxiv.org/abs/2411.05276) — accessed 2026-08-01
- [MeanCache: User-Centric Semantic Caching for LLM Web Services (arXiv:2403.02694)](https://arxiv.org/abs/2403.02694) — accessed 2026-08-01
- [Redis semantic cache — Redis Documentation](https://redis.io/docs/latest/develop/use-cases/semantic-cache/) — accessed 2026-08-01
- [Semantic Cache Poisoning: Corrupting the "Fast Path" — InstaTunnel](https://medium.com/@instatunnel/semantic-cache-poisoning-corrupting-the-fast-path-e14b7a6cbc1f) — accessed 2026-08-01
- [Anthropic API Pricing in 2026: Complete Guide — Finout](https://www.finout.io/blog/anthropic-api-pricing) — accessed 2026-08-01
- [Prompt caching — OpenAI API Documentation](https://developers.openai.com/api/docs/guides/prompt-caching) — accessed 2026-08-01
- [Semantic Cache for LLMs: When to Ship, When to Skip (2026) — Respan](https://www.respan.ai/articles/semantic-cache-llm) — accessed 2026-08-01
- [LLM Semantic Caching: The 95% Hit Rate Myth — DEV Community](https://dev.to/gauravdagde/llm-semantic-caching-the-95-hit-rate-myth-and-what-production-data-actually-shows-8ga) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
