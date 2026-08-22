# Rerankers: Cross-Encoder Economics, Cascades, BGE Tuning

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 1.5h · **Prereqs:** 02-embeddings-choice, 03-vector-index-internals, 04-hybrid-search · **Updated:** 2026-07-27
> **Module id:** `T06-reranking` · **Tags:** retrieval

## The 30-second version

A bi-encoder embeds query and document independently and compares vectors, which is fast enough to search millions of documents but structurally can't model query-document token interactions — a cross-encoder reranker feeds the query and each candidate document together through one transformer and scores the pair directly, which is far more accurate but scales linearly with the number of candidates, so it's only ever run over a small shortlist, never the whole corpus. The economics are what make this a design decision rather than a free upgrade: Cohere's rerank-3.5 costs $2 per 1,000 searches with roughly 80-150ms added p50 latency per call, while a self-hosted BGE-reranker-v2-m3 (a 278M/568M-parameter cross-encoder) runs 50-100ms on GPU or roughly 130ms per 16-pair batch on CPU, trading API cost for GPU ops burden. A cascade — cheap-and-fast first stage (BM25 or bi-encoder ANN) retrieves 100-500 candidates, a cross-encoder reranks the top 20-50 of those, and optionally an even more expensive stage (LLM-as-judge or ColBERT late interaction) re-ranks the final top 5-10 — is the standard production pattern because it spends the expensive model's compute only where it changes the outcome. The two failure modes to know cold: reranking too few candidates from a weak first-stage retriever (garbage in, garbage reranked) and reranking too many candidates for the latency budget (the reranker call itself becomes the bottleneck, not retrieval).

## Why this gets asked

The interviewer has shipped a RAG system where a reranker was bolted onto the retrieval pipeline as a checkbox improvement, and either the p99 latency budget blew up because someone reranked 200 candidates synchronously in the request path, or the accuracy gain didn't materialize because the first-stage retriever wasn't surfacing the right candidates in its top-k to begin with. They want to know whether you understand reranking as a cascade-design and latency-budget problem, not a drop-in model call — and whether you can reason about when the cross-encoder's extra accuracy is actually worth its cost per query.

---

## Lineage: past → present → future

**What came before.** Early retrieval systems used a single-stage ranking function — TF-IDF or BM25 scores directly determined result order, with no second pass. As dense retrieval matured, the same single-stage pattern carried over: embed everything with a bi-encoder, rank by cosine similarity, return the top-k. This worked well enough for coarse relevance but consistently missed subtle query-document relationships — negation, numerical comparison, multi-hop entity relationships — because a bi-encoder compresses each document into one fixed vector *before* seeing the query, so it can never attend across the query and document jointly. The pain that motivated cross-encoders (first applied to reranking search results by Nogueira & Cho's "Passage Re-ranking with BERT," 2019) was measurable: BERT-based cross-encoders beat bi-encoder-only pipelines by significant margins on MS MARCO passage ranking, precisely because joint attention lets the model check "does this specific document actually answer this specific question" rather than "is this document generally topically similar."

**Where it stands now.** The retrieve-then-rerank cascade is the default production architecture for any RAG system that cares about top-of-list precision: a cheap, high-recall first stage (BM25, bi-encoder ANN, or hybrid — see `04-hybrid-search.md`) surfaces a candidate set, and a cross-encoder reranks it. Commercial rerank APIs (Cohere rerank-3.5 at $2/1K searches, Voyage rerank-2, Jina reranker) compete directly with strong open-weight cross-encoders (BGE-reranker-v2-m3, a 278M-to-568M-parameter multilingual model scoring roughly 51.8 nDCG@10 on BEIR) — the live disagreement is almost entirely about self-host-vs-API economics and latency, not whether reranking helps (it consistently does, when the first stage has reasonable recall). ColBERT-style late interaction (see `04-hybrid-search.md`) occupies a middle ground some teams use instead of a full cross-encoder cascade — token-level embeddings with a MaxSim aggregation give much of the cross-encoder's precision at closer to bi-encoder speed, at the cost of larger index storage (one vector per token instead of one per document).

**Where it's heading.** Cascade depth is increasing rather than staying at two stages — production systems now commonly run three: cheap lexical/dense retrieval, a mid-cost cross-encoder over the top 50-100, and in high-value queries (customer support escalations, legal search) an LLM-as-judge pass over the final top 5-10 — moderate-to-high confidence, already deployed at several vendors as an optional pipeline stage. Distilled, smaller cross-encoders trained specifically to match a larger reranker's outputs (reranker distillation) are shipping to cut the latency/cost of the reranking stage itself without losing much accuracy — high confidence, an active area. More speculative: rerankers that jointly optimize for downstream generation quality rather than pure relevance (since the "most relevant" chunk by human judgment isn't always the chunk that most helps an LLM answer correctly) are a research direction without a settled production pattern as of mid-2026.

---

## Mental model

```
                     BI-ENCODER                       CROSS-ENCODER
   query  ──►[Encoder]──► q_vec                query+doc ──►[Encoder]──► score
   doc    ──►[Encoder]──► d_vec  (separately,           (jointly, one forward
                                   offline, once)         pass per candidate)
              score = cosine(q_vec, d_vec)

   Bi-encoder: doc vectors precomputed -> O(1) per query after ANN lookup.
   Cross-encoder: no precomputation possible -> O(candidates) forward passes.

CASCADE:

   [ full corpus: 10M docs ]
          │  BM25 / bi-encoder ANN (cheap, fast, high recall, low precision)
          ▼
   [ top 100-500 candidates ]
          │  cross-encoder rerank (expensive, slow, high precision)
          ▼
   [ top 5-10 final results ]
          │  optional: LLM-as-judge or ColBERT late interaction
          ▼
   [ context sent to generator ]

  Each stage narrows the candidate set and hands off to a more expensive,
  more accurate model that could never have scanned the full corpus itself.
```

---

## How it actually works

### Why cross-encoders are more accurate — and why they can't replace first-stage retrieval

A cross-encoder concatenates the query and a candidate document (typically `[CLS] query [SEP] document [SEP]`) and passes the pair through a single transformer, using self-attention across both texts jointly before a final classification/regression head outputs a relevance score. This lets the model directly attend from query tokens to document tokens and back — it can notice that the document negates the claim in the query, or that a number in the document doesn't match a number the query asks about, signals a bi-encoder's independently-computed, fixed-size vectors structurally cannot represent.

The cost is architectural: nothing about a cross-encoder score can be precomputed, because the score is a function of the *pair*, not of the document alone. Scoring N candidates requires N full forward passes at query time. Scoring an entire 10M-document corpus this way would mean 10M forward passes per query — computationally impossible at interactive latency, which is exactly why cross-encoders are reserved for reranking a first-stage shortlist rather than searching the corpus directly.

### Latency and throughput numbers — know these cold

**Cohere rerank-3.5 (API):** $2.00 per 1,000 searches (equivalently ~$2/1M tokens of search input). Reported p50 added latency is roughly 80-150ms on typical chunk sizes; real-world end-to-end latency including network round-trip commonly lands higher, around 600ms average in some deployments, so budget for network variance, not just the model's compute time.

**BGE-reranker-v2-m3 (open weights, self-hosted):** A 278M-to-568M-parameter multilingual cross-encoder built on the BGE-M3 foundation with LoRA fine-tuning, supporting 100+ languages, scoring roughly 51.8 nDCG@10 on BEIR. On GPU, latency is roughly 50-100ms for a batch of candidates; on CPU, roughly 130ms per 16-pair batch, meaning CPU deployment becomes latency-limiting once you rerank much past 50 candidates in the request path.

**What this means for cascade sizing:** rerank 20 candidates on GPU and you're adding roughly 50-100ms total; rerank 200 candidates and you're either batching heavily (throughput-bound, still adds real latency) or you've made the reranker, not retrieval, your dominant cost center. The number of candidates handed to the reranker is the single biggest latency lever in the whole pipeline — tune it explicitly against your p99 budget, don't default to "rerank everything the first stage returned."

### Cascade design — choosing shortlist size and stage count

The standard shape is: first-stage retrieval returns `k1` candidates (typically 100-500, chosen for high recall — you want the true positives *somewhere* in this set, precision doesn't matter yet), the cross-encoder reranks all `k1` and you keep the top `k2` (typically 5-20, whatever fits your generation context budget), and optionally a third stage (ColBERT late interaction, or an LLM-as-judge call) refines the final top handful further for the highest-value queries only.

```python
# untested sketch — two-stage retrieve-then-rerank cascade
def retrieve_and_rerank(query: str, k1: int = 150, k2: int = 8):
    # stage 1: cheap, high-recall, corpus-scale
    candidates = hybrid_search(query, top_k=k1)          # BM25 + bi-encoder ANN + RRF
    # stage 2: expensive, high-precision, shortlist-scale
    pairs = [(query, c.text) for c in candidates]
    scores = cross_encoder.predict(pairs)                # one forward pass per pair
    reranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return [c for c, _ in reranked[:k2]]
```

`k1` is the most consequential tuning knob and the one teams get wrong most often: too small and the reranker can only ever reorder a candidate set that already excludes the true best answer (a first-stage recall problem masquerading as a reranking problem); too large and you pay for cross-encoder forward passes on documents the first stage was never going to surface as relevant anyway, inflating latency for no accuracy gain. Tune `k1` empirically against recall@k1 of the *first stage alone* (see `13-accuracy-tuning.md`) — if recall@100 from the first stage is already 95%+, reranking 500 candidates instead of 150 buys you almost nothing.

### Score calibration and score fusion

Cross-encoder scores are typically raw logits or sigmoid-squashed relevance scores, not directly comparable across different query-document pairs in absolute terms — they're only meaningful as a *relative ranking within one query's candidate set*. This matters when you try to set an absolute relevance threshold ("only pass chunks scoring above 0.7 to the generator") — the right threshold is corpus- and query-type-dependent and needs its own calibration pass against labeled data, not a number copied from a vendor's demo.

---

## Build it from scratch

A minimal cross-encoder reranker using an open-weight model, showing the pairwise scoring mechanics a vendor API abstracts away:

```python
# untested sketch — minimal cross-encoder rerank using a HuggingFace model
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)

def rerank(query: str, candidates: list[str], top_k: int = 8) -> list[tuple[str, float]]:
    pairs = [[query, c] for c in candidates]
    scores = reranker.predict(pairs)  # one joint forward pass per pair, batched internally
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])
    return ranked[:top_k]
```

The parts a production system adds that this sketch skips: batching pairs to saturate GPU throughput rather than scoring one at a time, truncating documents to the model's max sequence length *before* concatenation (silent truncation mid-document is a common accuracy bug), and a fallback path if the reranker service is slow or down (serve the first-stage ranking unranked rather than blocking the whole request). See `(lab pending)` for a runnable cascade with latency instrumentation.

---

## How it's done in production

**Cohere Rerank** (`rerank-3.5`) — simplest to integrate, no GPU ops burden, $2/1K searches, competitive accuracy; the default choice when you don't want to operate reranking infrastructure yourself. **Voyage rerank-2** — comparable positioning to Cohere, often benchmarked closely against it on retrieval-heavy technical domains. **BGE-reranker-v2-m3** (open weights) — the default self-hosted choice, multilingual, Apache 2.0 licensed, runs well on a single GPU for moderate throughput. **Jina Reranker** — another open/API hybrid option, competitive on latency-sensitive deployments. **ColBERT / SPLATE late-interaction rerankers** — used as a cheaper alternative or complementary third stage rather than a full cross-encoder replacement, trading some precision for much lower per-query compute than a full cross-encoder pass over the same candidate count.

| Symptom | Cause | Fix |
|---|---|---|
| Reranking adds accuracy in offline eval but p99 latency blows the SLA in production | Reranking too many candidates (`k1` too large) synchronously in the request path | Reduce `k1` to the smallest value where first-stage recall@k1 plateaus; batch reranker calls; consider async/streaming UX for the reranking step |
| Reranker doesn't improve answer quality despite adding latency | First-stage retriever isn't surfacing true positives in its top-`k1` at all — reranking a bad candidate set just reorders garbage | Measure first-stage recall@k1 in isolation before blaming the reranker; fix retrieval (hybrid search, better embeddings) first |
| Cross-encoder scores look inconsistent across different query types | Comparing raw scores as if they're an absolute relevance threshold rather than a per-query relative ranking | Use scores only for within-query ranking; calibrate any absolute cutoff against labeled data specific to your corpus |
| Self-hosted reranker OOMs or times out under traffic spikes | No batching/backpressure; every request path scoring pairs one at a time or all candidates in one oversized batch | Add request batching with a max batch size and a queue; autoscale GPU replicas on reranker-specific latency/queue-depth metrics, not generic CPU utilization |
| Long documents silently truncated mid-sentence before reranking, hurting accuracy on those chunks | Cross-encoder's max sequence length (often 512 tokens) truncates the concatenated query+document pair without warning | Chunk documents to fit comfortably under the reranker's max length before the rerank stage, and log/monitor truncation rate |
| Reranking cost scales unexpectedly with traffic growth | Linear cost model (`$ per candidate reranked`) not accounted for in cost projections as query volume or `k1` grows | Model reranking cost as `queries/sec * k1 * cost_per_candidate`, not as a fixed line item, when projecting budget |

---

## Tradeoffs & when NOT to use it

- **Don't rerank if your first-stage retriever already has near-perfect precision at the k you need** (small, homogeneous corpora, exact-match-dominant queries) — the added latency and cost buys nothing when there's no ranking error left to correct.
- **Don't rerank hundreds of candidates synchronously in a latency-sensitive request path.** If the use case genuinely needs a large shortlist reranked, consider async processing, pre-computation for common queries, or a cheaper late-interaction stage instead of a full cross-encoder over the whole set.
- **Don't treat reranking as a substitute for fixing first-stage recall.** A reranker can only reorder what's already in the candidate set; if the true best chunk isn't in the top-`k1`, no reranker recovers it — diagnose which stage is actually failing before adding cost to the wrong one.
- **Don't self-host a reranker without a batching and backpressure strategy** — an unbounded per-request cross-encoder call is a straightforward way to OOM a GPU under moderate concurrent load.
- **Don't skip a third-stage LLM-judge pass reflexively for every query** — it's justified for high-value or high-ambiguity queries (legal, medical, escalated support) where the extra cost and latency are worth it, and a poor default everywhere else given its cost per call is typically far higher than a cross-encoder pass.

---

## Interview questions

### Q1 — Why can't a cross-encoder search a 10M-document corpus directly?
**Testing:** basic architectural understanding of why reranking is a second stage, not a replacement for retrieval.
**Answer:** A cross-encoder score is a function of the query-document pair jointly — nothing about it can be precomputed, so scoring the whole corpus would require 10M forward passes per query, computationally infeasible at interactive latency. Bi-encoders precompute document vectors once, offline, making corpus-scale search possible; cross-encoders trade that away for accuracy and can only be run over a small shortlist.
**Follow-up trap:** *"Could you make a cross-encoder faster with a smaller model?"* — yes, distillation helps, but the fundamental scaling (linear in candidates, no precomputation) doesn't change; it's still reserved for a shortlist, just a slightly larger one.

### Q2 — Give real numbers: what does Cohere rerank-3.5 cost and how much latency does it add?
**Answer:** $2.00 per 1,000 searches, roughly 80-150ms added p50 latency per call on typical chunk sizes, though real-world end-to-end latency including network round-trip is commonly higher (reported around 600ms average in some deployments).
**Follow-up trap:** *"How does that compare to self-hosting BGE-reranker-v2-m3?"* — BGE-reranker-v2-m3 runs roughly 50-100ms on GPU (or ~130ms per 16-pair batch on CPU) with no per-call API cost, but adds GPU serving/ops burden — the tradeoff is cost-per-call vs. infrastructure ownership, not a strict win for either side.

### Q3 — What's the single most consequential tuning knob in a retrieve-then-rerank cascade?
**Answer:** `k1`, the number of candidates the first stage hands to the reranker. Too small and you cap the reranker's ceiling at whatever the first stage already got right (a first-stage recall problem, not a reranking problem); too large and you pay cross-encoder compute on documents that were never going to be relevant, inflating latency for no accuracy gain.
**Follow-up trap:** *"How would you actually choose k1?"* — measure recall@k1 of the first stage in isolation; pick the smallest k1 where that recall plateaus, not an arbitrary round number.

### Q4 — A reranker was added to a pipeline and offline eval improved, but production p99 latency blew the SLA. What happened?
**Answer:** Almost certainly reranking too many candidates synchronously in the request path — the cross-encoder's cost scales linearly with candidate count, and a shortlist sized for offline eval convenience (or copied from a demo) is often far larger than the p99 budget tolerates.
**Follow-up trap:** *"How would you fix it without losing the accuracy gain?"* — reduce k1 to the recall-plateau point (usually smaller than assumed), batch reranker calls to saturate GPU throughput, and consider whether the very top of the candidate list can be reranked while lower-ranked candidates are served unranked, rather than reranking everything at the same cost.

### Q5 — Why does a reranker sometimes fail to improve answer quality even though it's working correctly?
**Answer:** If the first-stage retriever never surfaced the true best chunk in its top-`k1`, the reranker can only reorder a candidate set that's already missing the right answer — it has nothing to promote. This is a first-stage recall failure being misdiagnosed as a reranking failure.
**Follow-up trap:** *"How do you tell the difference in practice?"* — measure recall@k1 of the first stage alone against a labeled eval set; if the gold chunk isn't even in the candidate set, the reranker is blameless and the fix is in retrieval, not reranking.

### Q6 — Can you treat a cross-encoder's raw score as an absolute relevance threshold across different queries?
**Answer:** No — cross-encoder scores are only reliably meaningful as a relative ranking within one query's candidate set; comparing raw scores across different queries or setting a single absolute cutoff for "relevant enough" needs its own calibration against labeled data specific to your corpus and query distribution.
**Follow-up trap:** *"What happens if you set a naive fixed threshold anyway?"* — you'll either drop legitimately relevant chunks for query types the model scores conservatively, or pass through irrelevant chunks for query types it scores generously — a silent quality bug that looks like noise rather than a clear failure.

### Q7 — What's a documented failure mode from truncation when reranking long documents?
**Answer:** Cross-encoders have a max sequence length (often 512 tokens) for the concatenated query+document pair; if a document chunk exceeds what's left after the query, it's silently truncated mid-sentence before scoring, degrading accuracy on exactly the chunks that needed the most context to score correctly.
**Follow-up trap:** *"How would you catch this in production?"* — monitor the truncation rate at the reranker input stage as an explicit metric, not just overall accuracy; a silent truncation bug won't show up as an obvious error, only as unexplained quality variance on longer chunks.

### Q8 — Explain ColBERT-style late interaction as an alternative to a full cross-encoder rerank stage.
**Answer:** Late interaction keeps token-level embeddings for both query and document (rather than compressing each to one vector) and aggregates similarity via MaxSim (each query token attends to its best-matching document token, summed across query tokens), giving much of a cross-encoder's precision without requiring a joint forward pass per candidate at query time — document token embeddings can be precomputed, unlike cross-encoder scores.
**Follow-up trap:** *"What does this cost instead?"* — storage: one vector per token instead of one per document, a substantial index size increase, and additional query-time compute for the MaxSim aggregation over many token vectors compared to a single dot product.

### Q9 — How would you design a three-stage retrieval cascade for a high-value use case like legal document search?
**Answer:** Stage one: hybrid search (BM25 + bi-encoder ANN with RRF fusion) over the full corpus for high recall, returning 150-300 candidates. Stage two: a cross-encoder (BGE-reranker-v2-m3 or Cohere rerank-3.5) reranks those down to the top 10-20. Stage three, reserved for the highest-stakes queries only given its cost: an LLM-as-judge pass evaluates the final handful against the specific legal question, since precision at this level often matters more than the added latency and per-query cost.
**Follow-up trap:** *"Would you run stage three on every query?"* — no; its cost per call is typically far higher than a cross-encoder pass, so it should be gated to high-value or high-ambiguity queries specifically, not applied as a blanket default.

### Q10 — Your reranking self-hosted service starts OOMing under a traffic spike. What's the likely cause and fix?
**Answer:** Likely no batching or backpressure — requests scoring candidate pairs one at a time, or an unbounded batch size scaling with traffic, exhausting GPU memory under concurrent load.
**Follow-up trap:** *"How do you autoscale this correctly?"* — scale on reranker-specific latency or request-queue-depth metrics, not generic CPU utilization, since the bottleneck is GPU memory/compute for batched inference, which generic infra metrics don't directly reflect.

### Q11 — When would reranking be the wrong choice entirely?
**Answer:** When the first-stage retriever already achieves near-perfect precision at the required k — small, homogeneous corpora or exact-match-dominant queries where there's no meaningful ranking error left for a cross-encoder to correct — the added latency and cost buys nothing.
**Follow-up trap:** *"How would you verify this before deciding not to rerank?"* — measure precision@k of the first stage alone against a labeled eval set; don't assume based on corpus size alone, verify with the actual metric.

### Q12 — Design the reranking strategy for a multi-tenant SaaS product where tenant corpora range from a few hundred to millions of documents, under a shared latency SLA.
**Testing:** synthesis across cascade design, cost modeling, and heterogeneous scale.
**Answer:** For small tenants, first-stage retrieval alone (or even brute-force scoring) may already meet accuracy targets without a reranking stage at all, since there's little ranking error to correct in a corpus of a few hundred documents — reranking here is pure added latency. For large tenants, run the standard two-stage cascade (hybrid retrieval → cross-encoder rerank) with `k1` tuned against that tenant's own recall@k1 curve, since a fixed k1 across four orders of magnitude of corpus size is unlikely to be right for all of them. Model reranking cost per tenant as `queries/sec * k1 * cost_per_candidate` explicitly in the cost projection, since it scales with both traffic and shortlist size, not as a flat per-tenant line item.
**Follow-up trap:** *"What if the shared SLA is tight and large tenants need a bigger k1 for recall?"* — this is a real tension; the honest answer is either tenant-tiered SLAs, or moving the reranking step off the synchronous request path for large tenants (pre-rerank common queries, or accept slightly higher latency for large-tenant traffic specifically) rather than pretending one k1/latency budget serves everyone.

---

## Red flags that fail you

- Claiming a cross-encoder can search a large corpus directly instead of only reranking a shortlist.
- Not knowing that `k1` (shortlist size) is a tunable, measurable parameter rather than a fixed default.
- Blaming the reranker for poor answer quality without first checking first-stage recall@k1.
- Treating cross-encoder scores as an absolute, cross-query-comparable relevance threshold.
- Reranking hundreds of candidates synchronously without considering the latency budget.
- Not knowing any real pricing/latency numbers for at least one API and one self-hosted reranker.

---

## Cheat card

```
BI-ENCODER  q_vec, d_vec computed independently -> precomputable, corpus-scale (fast)
CROSS-ENCODER  query+doc jointly through one model -> NOT precomputable, O(candidates)
               (accurate, but shortlist-only)

CASCADE  corpus (10M) --[BM25/bi-encoder ANN, k1=100-500]--> shortlist
         --[cross-encoder rerank]--> top k2=5-20
         --[optional: LLM-judge or ColBERT]--> final top 5-10

COHERE rerank-3.5   $2/1K searches (~$2/1M tok). p50 +80-150ms; real e2e ~600ms w/ network
BGE-reranker-v2-m3  278M-568M params, open (Apache 2.0), 100+ langs, ~51.8 nDCG@10 BEIR
                    GPU: 50-100ms · CPU: ~130ms/16-pair batch

MOST CONSEQUENTIAL KNOB  k1 (shortlist size): tune to where first-stage
    recall@k1 PLATEAUS. Too small = caps reranker ceiling. Too large = wasted latency/$.

SCORE CALIBRATION  cross-encoder scores are relative WITHIN one query's candidates,
    not an absolute cross-query threshold -- calibrate any cutoff on labeled data

TRUNCATION BUG  max seq len (~512 tok) silently truncates long query+doc pairs
    -- monitor truncation rate as its own metric

COST MODEL  reranking cost = queries/sec * k1 * cost_per_candidate (scales w/ traffic AND k1)

WHEN NOT TO RERANK  first-stage already near-perfect precision@k (small/homogeneous
    corpus, exact-match-dominant queries) -- no ranking error left to fix

ALTERNATIVE  ColBERT/SPLATE late interaction: token-level MaxSim, precomputable doc
    vectors, cheaper than full cross-encoder, costs index storage (1 vec/token)
```

## Sources

- [Cohere API Pricing 2026 — AI Pricing Guru](https://www.aipricing.guru/cohere-pricing/) — accessed 2026-07-27
- [Rerank v3.5 — API Pricing & Providers — OpenRouter](https://openrouter.ai/cohere/rerank-v3.5) — accessed 2026-07-27
- [Reranker Models Compared: Cohere vs Voyage vs Jina vs BGE — Particula](https://particula.tech/blog/reranker-models-compared-cohere-voyage-jina-bge-latency-ndcg) — accessed 2026-07-27
- [Best Rerankers for RAG in 2026: 7 Models Compared — FutureAGI](https://futureagi.com/blog/best-rerankers-for-rag-2026/) — accessed 2026-07-27
- [BAAI/BGE Reranker v2 M3 — Reranker Details & Performance — Agentset](https://agentset.ai/rerankers/baaibge-reranker-v2-m3) — accessed 2026-07-27
- [Best Reranker Models for RAG: Open-Source vs API Comparison (2026) — BSWEN](https://docs.bswen.com/blog/2026-02-25-best-reranker-models/) — accessed 2026-07-27
- Passage Re-ranking with BERT, Nogueira & Cho, 2019 (arXiv:1901.04085)

## Changelog
- 2026-07-27 — created
