# Semantic Search: Lexical → Vector → Hybrid → Learned Ranking

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.5h · **Prereqs:** 04-hybrid-search, 05-reranking · **Updated:** 2026-08-01
> **Module id:** `T06-semantic-search` · **Tags:** retrieval,critical

## The 30-second version

Search has moved through four eras, each one solving the previous era's specific, named failure without fully replacing it: boolean retrieval (exact match, no ranking) gave way to TF-IDF/BM25 (ranked by term statistics, but blind to vocabulary mismatch — "car" never matches "automobile"), which gave way to dense bi-encoder retrieval (DPR, 2020 — solves vocabulary mismatch via learned semantic vectors, but blurs exact identifiers, SKUs, and rare tokens it barely saw in training), which gave way to hybrid retrieval (run both, fuse with RRF — see `04-hybrid-search`) because the two failure modes are complementary and hybrid measurably beats either alone (roughly 91% recall@10 for hybrid vs. 78% dense-only vs. 65% sparse-only in typical production benchmarks). None of that is the end state: production search systems add a **learned ranking** layer on top that incorporates signals no text-similarity method can see at all — click-through rate, recency, price, personalization, inventory — because the question "which candidate is most textually relevant" and "which candidate should rank first for this business" are different questions. Hybrid retrieval plus a cross-encoder reranker is the correct default for the vast majority of RAG systems; a full learned-to-rank layer with business features is what an e-commerce or ads-adjacent search system needs on top, and it's overkill (and prone to overfitting) without real interaction data to train on.

## Why this gets asked

The interviewer has watched a team ship "semantic search" as a single bi-encoder call, get burned when a customer searched for an exact order number or SKU and got nothing, and then watched the fix get bolted on badly — a keyword fallback with no principled fusion. They also want to know whether you think retrieval ends at "return the top-k most similar chunks," or whether you understand that production ranking systems layer a business-aware ranking stage on top of pure relevance, which is where most candidates' mental model stops short.

---

## Lineage: past → present → future

**What came before.** Boolean retrieval — `AND`/`OR`/`NOT` over an inverted index — was the only practical large-scale search method through the 1960s-80s. It has no ranking model at all: a document either matches the boolean expression or it doesn't, and matching documents are typically ordered by date or document ID, not relevance. The pain was structural, not incidental: users had to hand-craft precise boolean queries to avoid either zero results (over-constrained) or an unranked flood (under-constrained), and there was no way to express "somewhat relevant." TF-IDF, and its refinement BM25 (Robertson & Spärck Jones, formalized in the Okapi system through the 1990s), fixed this by scoring documents on a continuous relevance scale using term frequency and inverse document frequency — see `18-text-preprocessing` for the TF-IDF derivation and `04-hybrid-search` for BM25's exact formula. BM25's own pain, understood for decades before embeddings existed, was vocabulary mismatch: a query for "car" cannot match a document that only ever says "automobile," no matter how relevant, because BM25 operates purely on shared tokens.

**Where it stands now.** Dense bi-encoder retrieval (Dense Passage Retrieval, Karpukhin et al. 2020) fixed vocabulary mismatch by learning representations where semantically related text lands close in vector space regardless of shared tokens — but it traded away BM25's precision on exact, rare tokens, because an embedding model compresses text into a fixed-size vector that structurally blurs low-frequency identifiers (error codes, SKUs, case numbers) it saw few or no times in training. Hybrid search (BM25 + dense, fused with Reciprocal Rank Fusion) is now the accepted production default specifically because these two failure modes are complementary rather than overlapping — this is settled, not a live debate. What's less settled, and what separates a mid-level from a senior answer, is what sits *above* retrieval: a cross-encoder reranker (`05-reranking`) improves precision on text relevance alone, but real production ranking — e-commerce search, ads, feed ranking, and any search product with a monetization or engagement objective — needs a **learned ranking** layer that combines relevance with business signals (click-through rate, conversion, recency, price, inventory, personalization) that no text-similarity method, however sophisticated, can see. Gradient-boosted tree rankers (LambdaMART) trained on click/relevance-labeled features have been the industry workhorse since the mid-2000s and remain deployed at scale; the live disagreement is how much of that role LLM-based listwise rerankers (prompting a model with the whole candidate list and business context) should take over versus a dedicated, cheaper, more predictable GBDT model.

**Where it's heading.** LLM-based rerankers that reason over natural-language business context alongside relevance (rather than requiring hand-engineered numeric features) are shipping in a growing number of production search stacks — moderate confidence this becomes a standard *additional* stage, low confidence it fully replaces GBDT-based LTR given the latter's predictability and much lower cost per query. Query understanding is absorbing more of an LLM's reasoning ability — decomposition, routing between structured and unstructured retrieval, clarification — which is real and shipping in 2026 production RAG stacks, though naive LLM-driven query rewriting (adding keywords, generating hypothetical answers) has a documented failure mode of *hurting* retrieval by distorting intent, so this is a technique that requires its own evaluation discipline, not a blind win.

---

## Mental model

Each era adds a layer rather than fully replacing the one below it — a production system today runs all of them at once, stacked:

```
                    ┌─────────────────────────────┐
  business-aware     │   LEARNED RANKING (LTR)      │  CTR, recency, price,
  layer               │   GBDT / LambdaMART / LLM    │  personalization, inventory
                    └──────────────┬──────────────┘
                                   │ reorders
                    ┌──────────────┴──────────────┐
  precision layer    │   RERANKING (cross-encoder)  │  text relevance only,
                    │   see 05-reranking            │  see 05-reranking
                    └──────────────┬──────────────┘
                                   │ shortlist
                    ┌──────────────┴──────────────┐
  recall layer       │   HYBRID (BM25 + dense, RRF) │  fixes vocabulary mismatch
                    │   see 04-hybrid-search        │  AND exact-token precision
                    └──────┬────────────────┬──────┘
                           │                │
                  ┌────────┴───┐   ┌────────┴────────┐
  foundation       │ BM25/TF-IDF │   │ dense bi-encoder │
                  │ (exact terms)│   │ (semantic space) │
                  └─────────────┘   └─────────────────┘
```

Boolean retrieval sits below all of this as the degenerate case (an exact-match filter, still used as a hard prefilter — "must be in stock," "must match tenant_id" — rather than a ranking method). Nothing in this stack is obsolete; each layer is added because the layer below it answers a narrower question than production needs answered.

---

## How it actually works

### The precise failure that motivated each step

- **Boolean → TF-IDF/BM25**: boolean has no relevance ranking at all — the pain is binary match/no-match with no notion of "more" or "less" relevant, forcing users into brittle exact query construction.
- **BM25 → dense**: vocabulary mismatch — zero token overlap means zero score, regardless of meaning. A query "how do I cancel my membership" scores nothing against a document that only says "terminate your subscription," even though they mean the same thing.
- **Dense → hybrid**: dense retrieval's own blind spot — rare, low-frequency tokens (error codes like `0x80070005`, SKUs like `INV-2024-00847`, case numbers, uncommon proper nouns) get weakly differentiated embeddings because the model saw few or no training examples anchoring their exact meaning. The embedding model finds documents about error codes *in general* and misses the literal string.
- **Hybrid + reranking → learned ranking**: even a perfect relevance ranking doesn't answer "which result should actually be shown first" once there's a business objective — two equally relevant products differ in margin, inventory, and personalized affinity, and none of that is expressible as a function of query-document text similarity.

### Where BM25 still beats embeddings, concretely

Three cases where a senior candidate should reach for lexical search first, not as a hybrid afterthought:

1. **Exact identifiers.** Error codes, order numbers, SKUs, legal citations, case numbers. These are rare tokens by construction — an embedding model has no principled way to distinguish `INV-2024-00847` from `INV-2024-00848`, since both are equally "out of distribution," while BM25's IDF weighting finds the literal string immediately.
2. **Rare technical terms.** Domain jargon that appears a handful of times in a general-purpose embedding model's pretraining data gets a noisy, weakly-anchored vector; the same term is a strong, unambiguous signal to a lexical index regardless of how rare it is.
3. **Code search.** Identifiers in code (`computeUserRiskScore`, `MAX_RETRY_COUNT`) are precise, structured tokens where an exact or near-exact match is almost always what the user wants — searching for a specific function name and getting back "semantically similar" functions with different names is a worse experience than exact lexical matching with light tokenization awareness (splitting `camelCase`/`snake_case` into constituent words). Dense embedding models trained primarily on natural language routinely underperform a well-tuned lexical index (or a code-specific dense model, which is a different mitigation entirely) on exact symbol lookup.

### Learned ranking: features beyond text similarity

A learned-to-rank (LTR) model takes a feature vector per query-candidate pair and outputs a score used to reorder the shortlist that retrieval + reranking already produced. Typical feature groups:

| Feature group | Examples |
|---|---|
| Text relevance | BM25 score, dense cosine similarity, cross-encoder score — the *inputs* from everything above this layer |
| Popularity / engagement | Click-through rate, conversion rate, dwell time, historical CTR at this position |
| Freshness | Document age, last-updated timestamp, decay function over recency |
| Business | Price, margin, inventory level, sponsored/boosted flag |
| Personalization | User's past interactions, affinity score to category/author, geographic distance |

**LambdaMART** (Burges et al., building on RankNet and LambdaRank, formalized around 2010) — a gradient-boosted decision tree model trained directly to optimize a ranking metric like nDCG rather than pointwise regression — won the 2010 Yahoo! Learning to Rank Challenge and remains a common production baseline because GBDTs handle heterogeneous, non-linear feature interactions (a price feature interacting with a personalization feature in a way neither alone predicts) well, train fast, and are cheap and predictable to serve compared to a neural ranker.

**The cascade architecture** used at large-scale e-commerce and ad search systems runs four progressively more expensive stages: **matching** (cheap candidate generation — inverted index, ANN — casting a wide net over millions of items), **pre-ranking** (a lightweight model narrows millions to thousands using cheap features), **ranking** (the full LTR/LambdaMART or neural model scores thousands down to tens using the full feature set), and **mix-ranking** (final business-rule adjustments — diversity constraints, ad interleaving, deduplication) before serving. This is structurally the same cascade pattern as retrieve→rerank (`05-reranking`), just with more stages and business features added at the top.

### The click-data bias trap

Training an LTR model directly on raw click logs bakes in **position bias**: users click higher-ranked results more often regardless of true relevance, because they rarely scroll past the top few results to evaluate lower ones fairly. A naive LTR model trained on raw clicks learns to reinforce whatever the previous ranking already put on top, rather than learning true relevance — a well-documented failure (Joachims et al., early 2000s eye-tracking studies on search behavior) that is still the first thing to check when an LTR model's offline metrics look great but online engagement doesn't move. Mitigations: inverse propensity scoring (weight each click by the inverse probability it would have been seen at that position) or randomized result interleaving to collect unbiased position-independent labels.

### Query understanding, and where it backfires

Before retrieval ever runs, production systems apply query understanding: spell correction, intent classification (navigational vs. informational vs. transactional), entity extraction, and query rewriting (reformulating the query for better retrieval, e.g. resolving "it" from conversation history, or expanding "ML" to "machine learning"). This is one of the highest-leverage layers in production RAG and one of the most under-invested in early-stage deployments. But it is not a free win: retrieval-oriented rewrites like generating a hypothetical answer document (HyDE) or expanding a query with a keyword list can *hurt* retrieval by distorting the original intent or overamplifying rare terms the user never actually cared about — this needs the same eval discipline (`13-accuracy-tuning`) as any other pipeline change, not blind adoption because a paper reported gains on a different corpus.

---

## Build it from scratch

```python
# untested sketch — minimal boolean/TF-IDF baseline plus a toy LTR reranker,
# illustrating the lineage mechanically rather than production-hardened
import math
from collections import Counter, defaultdict

def boolean_search(query_terms: set[str], inverted_index: dict[str, set[str]]) -> set[str]:
    """AND semantics only — the degenerate, pre-ranking case."""
    if not query_terms:
        return set()
    result = inverted_index.get(next(iter(query_terms)), set()).copy()
    for term in query_terms:
        result &= inverted_index.get(term, set())
    return result


def tfidf_score(query_terms: list[str], doc_terms: list[str], df: dict[str, int], n_docs: int) -> float:
    tf = Counter(doc_terms)
    score = 0.0
    for term in query_terms:
        if tf[term] == 0:
            continue
        idf = math.log(n_docs / (1 + df.get(term, 0)))
        score += tf[term] * idf
    return score


def toy_ltr_score(features: dict[str, float], weights: dict[str, float]) -> float:
    """A linear stand-in for LambdaMART: real GBDTs learn nonlinear interactions,
    but the feature-combination *idea* is the same — text relevance is just one input."""
    return sum(weights.get(k, 0.0) * v for k, v in features.items())


def rerank_with_business_features(candidates: list[dict], weights: dict[str, float]) -> list[dict]:
    """candidates: [{'id':..., 'bm25': ..., 'dense_sim': ..., 'ctr': ..., 'price': ..., 'recency_days': ...}]"""
    scored = [(c, toy_ltr_score(c, weights)) for c in candidates]
    return [c for c, _ in sorted(scored, key=lambda x: -x[1])]
```

The parts a real LTR system adds that this sketch skips entirely: a gradient-boosted tree model (LightGBM/XGBoost with a ranking objective like `lambdarank`) that learns nonlinear feature interactions instead of a fixed linear weight vector, propensity-weighted training labels to correct for position bias, and an offline nDCG/MAP evaluation gate before any model reaches production traffic.

---

## How it's done in production

**Retrieval + fusion + reranking**: Elasticsearch/OpenSearch, Weaviate, Qdrant for hybrid (`04-hybrid-search`); Cohere/Voyage/BGE cross-encoders for reranking (`05-reranking`). **Learned ranking**: Elasticsearch's Learning to Rank plugin, LightGBM/XGBoost with `lambdarank`/`rank_xendcg` objectives, feature stores (Feast, Tecton) to serve consistent features at train and inference time. **Query understanding**: spell-correction and intent-classification models as a pre-retrieval stage, LLM-based query rewriting/decomposition gated by its own eval. **At scale**: multi-stage cascades (matching → pre-ranking → ranking → mix-ranking) as used across large e-commerce and ads search systems, where each stage narrows the candidate set and hands off to a costlier, more accurate model.

| Symptom | Cause | Fix |
|---|---|---|
| Exact order-number or SKU searches return nothing | Pure dense retrieval with no lexical leg | Add BM25/lexical retrieval and fuse (`04-hybrid-search`); never rely on embeddings alone for identifier-heavy queries |
| Code search returns "similar" functions instead of the exact one searched for | Natural-language embedding model applied to code identifiers without exact/token-aware matching | Add lexical matching on tokenized identifiers (split `camelCase`/`snake_case`), or use a code-specific embedding model |
| LTR model's offline nDCG improves but online engagement doesn't move, or gets worse | Training on raw click logs bakes in position bias — the model learned to reinforce the existing ranking, not true relevance | Apply inverse propensity scoring or collect labels via randomized result interleaving before retraining |
| Query rewriting/expansion improves some queries but silently tanks others | HyDE-style or keyword-expansion rewrites distort intent or overamplify rare terms for a subset of query types | Evaluate query rewriting per query-type slice, not one blended metric; gate behind the same recall@k discipline as any retrieval change |
| A new LTR model looks great in offline evaluation and collapses in production | Feature skew between training-time and serving-time feature computation (e.g. a feature computed from a batch job at training time vs. real-time at serving time) | Use a feature store to guarantee train/serve feature parity; log serving-time features and diff against training data |
| Cascade pipeline's early stage silently drops the eventual best result | Pre-ranking stage's cheap model doesn't correlate well enough with the final ranking model's judgment | Measure recall@k of the pre-ranking stage against the final ranking model's top choices, not just against ground truth, to catch stage misalignment |

---

## Tradeoffs & when NOT to use it

- **Don't build a full LTR layer without real interaction data.** A gradient-boosted ranker trained on sparse or synthetic labels will overfit noise or simply reproduce whatever heuristic generated the labels; a small catalog with low traffic (tens of thousands of items, limited click history) is usually better served by hand-tuned boosting rules (Elasticsearch function scoring, a simple weighted combination of BM25 + recency + popularity) that are transparent and easy to debug, not a model destined to overfit.
- **Don't apply LLM query rewriting unconditionally.** It measurably helps some query types (conversational follow-ups, typo-heavy input) and measurably hurts others (adding keywords that dilute a precise query); ship it behind its own per-query-type eval, not as a blanket preprocessing step.
- **Don't skip the lexical leg because "embeddings are semantic and better."** Any corpus with exact identifiers, codes, or a code-search use case needs BM25 or an equivalent lexical/token-exact mechanism; pure dense retrieval fails silently here, and the failure only shows up when a real user searches for something specific.
- **Don't train an LTR model on raw click data without correcting for position bias.** It is one of the most common and hardest-to-detect production bugs in ranking systems: the model looks like it's learning, offline metrics improve, and online performance simply reflects the ranker's own past decisions back at it.
- **Reranking is not a substitute for retrieval quality, and LTR is not a substitute for reranking quality.** Each layer in the stack can only reorder what the layer below it already surfaced; a business-aware LTR model cannot promote a genuinely relevant item that hybrid retrieval never put in the candidate set to begin with.

---

## Interview questions

### Q1 — Why doesn't boolean retrieval count as "ranking" at all?
**Testing:** baseline understanding of the earliest era.
**Answer:** Boolean retrieval evaluates a match/no-match expression (AND/OR/NOT over an inverted index) with no relevance scale — documents either satisfy the boolean expression or don't, and matching results are typically ordered by date or ID, not relevance. There's no way to express "somewhat relevant."
**Follow-up trap:** *"Isn't boolean logic still used today?"* — yes, as a hard prefilter (must match tenant_id, must be in stock), not as the ranking mechanism; conflating a filter with a ranker is the trap.

### Q2 — Explain vocabulary mismatch precisely, with an example.
**Answer:** BM25 and TF-IDF score purely on shared tokens; a query for "car" produces zero score against a document that only ever says "automobile," regardless of semantic relevance, because there's no shared term to weight. Dense embeddings fix this by mapping both words to nearby points in a learned vector space.
**Follow-up trap:** *"So dense retrieval strictly solves this?"* — it solves vocabulary mismatch but introduces its own blind spot on rare/exact tokens — trading one failure mode for a different one, not eliminating failure.

### Q3 — Give three concrete cases where BM25 still beats embeddings today, and explain the mechanism in each.
**Answer:** (1) Exact identifiers — SKUs, error codes, case numbers — which are rare tokens an embedding model never anchored well in training, while BM25's IDF weighting finds the literal string directly. (2) Rare technical/domain jargon, for the same reason. (3) Code search, where identifiers are precise structured tokens and users want exact or near-exact symbol matches, not "semantically similar" code.
**Follow-up trap:** *"Could a domain-tuned embedding model fix all three?"* — fine-tuning helps but doesn't remove the structural advantage of exact lexical matching for identifier-style tokens; it's a harder, more expensive path to a guarantee BM25 gives for free.

### Q4 — What is learned-to-rank, and how is it different from a cross-encoder reranker?
**Answer:** A cross-encoder reranker (`05-reranking`) scores query-document *text relevance* only, via joint attention over the pair. Learned-to-rank takes a feature vector per query-candidate pair — which can include the cross-encoder's own score as one input — plus business signals (CTR, recency, price, personalization, inventory) that no text-similarity model can see, and trains a model (commonly a gradient-boosted tree like LambdaMART) to optimize a ranking metric like nDCG over that combined feature set.
**Follow-up trap:** *"Isn't reranking just LTR with fewer features?"* — architecturally similar (both reorder a shortlist), but the point is that text relevance and business objective are different targets; a system optimizing purely for relevance can rank an item first that a business-aware model would rank fifth because it's out of stock or unprofitable.

### Q5 — What is LambdaMART and why has it remained a production standard for so long?
**Answer:** A gradient-boosted decision tree ranking model (building on RankNet/LambdaRank, formalized around 2010) trained to directly optimize a ranking metric like nDCG rather than pointwise regression. It won the 2010 Yahoo! Learning to Rank Challenge and remains widely deployed because GBDTs handle heterogeneous, nonlinear feature interactions well, train quickly, and are cheap and predictable to serve compared to a neural ranker — properties that matter enormously at web-search or e-commerce query volumes.
**Follow-up trap:** *"Why not just use a neural ranker or an LLM instead?"* — neural/LLM rankers can outperform on complex reasoning but cost more per query and are harder to debug/audit; the honest answer names the cost/latency tradeoff rather than assuming newer is strictly better.

### Q6 — Describe the four-stage cascade architecture used in large-scale search/ads ranking.
**Answer:** **Matching** — cheap, high-recall candidate generation over the full corpus (inverted index, ANN). **Pre-ranking** — a lightweight model narrows millions of candidates to thousands using cheap features. **Ranking** — the full LTR/neural model scores thousands down to tens using the complete feature set. **Mix-ranking** — final business-rule adjustments (diversity, ad interleaving, deduplication) before serving. Each stage hands off to a progressively more expensive, more accurate model that could never run over the full candidate set.
**Follow-up trap:** *"How is this different from retrieve-then-rerank?"* — it's the same underlying pattern (narrow, then spend more compute on what's left) with more stages and business features layered on top; recognizing this as one repeating idea, not four unrelated systems, is the senior signal.

### Q7 — What is position bias in learned-to-rank training data, and how do you correct for it?
**Answer:** Users click higher-ranked results more often regardless of true relevance, because they rarely scroll down to evaluate lower-ranked results fairly. Training an LTR model directly on raw click logs teaches it to reinforce whatever ranking already existed rather than learning true relevance. Corrections: inverse propensity scoring (weight clicks by the inverse of their probability of being seen at that position) or randomized result interleaving to collect position-independent labels.
**Follow-up trap:** *"How would you notice this in production without knowing to look for it?"* — offline ranking metrics (nDCG on click-derived labels) improve steadily while online engagement metrics stay flat or regress; that divergence is the signature symptom.

### Q8 — Why can query rewriting hurt retrieval instead of helping it?
**Answer:** Rewrites like HyDE (generating a hypothetical answer document to embed) or keyword expansion can distort the original query's intent or overamplify rare terms the user never actually cared about, shifting retrieval toward a subtly different question than the one asked. This isn't hypothetical — it's a documented failure mode, not just a theoretical risk.
**Follow-up trap:** *"So should you avoid query rewriting?"* — no, but ship it behind a per-query-type eval (`13-accuracy-tuning`), since it measurably helps some query types (conversational follow-ups) and measurably hurts others; a blanket policy in either direction is wrong.

### Q9 — When is a full LTR layer the wrong investment?
**Answer:** When there isn't enough real interaction/click data to train on — small catalogs, low-traffic products, or a cold-start system with no click history. A GBDT ranker trained on sparse or synthetic labels overfits noise or reproduces whatever heuristic generated the labels; hand-tuned boosting (weighted combination of BM25 + recency + popularity in something like Elasticsearch function scoring) is more transparent and just as effective at that scale.
**Follow-up trap:** *"At what traffic level does LTR start paying off?"* — there's no universal number; the real gate is having enough labeled or click-derived training examples per query-candidate feature combination to avoid overfitting, which you'd verify empirically (holdout performance, not training-set fit) before investing in the infrastructure.

### Q10 — A stakeholder says "we added semantic search, why does it still fail on order-number lookups?" How do you respond?
**Answer:** "Semantic search" as pure dense retrieval structurally can't guarantee exact-token recall — the embedding model has no principled way to prioritize an exact rare-string match over a topically-similar one. The fix is hybrid retrieval (BM25 + dense, fused), not a better embedding model; embeddings alone will never close this gap because the failure is architectural, not a matter of model quality.
**Follow-up trap:** *"What if we just fine-tune the embedding model on our order-number data?"* — that can narrow the gap for the specific identifiers seen in training, but doesn't generalize to future or unseen identifiers the way exact lexical matching does natively; it's a strictly harder, more fragile path to the same guarantee.

### Q11 — What's the honest, default answer to "which retrieval architecture should we ship first"?
**Answer:** Hybrid retrieval (BM25 + dense, RRF-fused) plus a cross-encoder reranker over the fused shortlist, validated against a recall@k/nDCG eval built from real queries. That's the right default for the large majority of RAG and search products. A full learned-ranking layer with business features is additional investment justified specifically when there's a business objective beyond pure relevance (e-commerce, ads, feeds) and enough interaction data to train on — not a default everyone needs.
**Follow-up trap:** *"Isn't that underselling what a sophisticated search team should build?"* — no; naming the point at which additional complexity stops being justified by measured gain is exactly the senior signal interviewers are listening for, not maximal architecture.

### Q12 — Staff-level: design the ranking stack for a marketplace search product (natural-language queries, exact SKU lookups, and a monetization objective from sponsored listings).
**Testing:** synthesis of the whole lineage under a realistic, multi-objective constraint.
**Answer:** Retrieval: hybrid (BM25 handles exact SKU/brand-name lookups; dense handles paraphrased natural-language queries), fused with RRF given the corpus reindexes frequently enough that a tuned weighted-fusion alpha would go stale (`04-hybrid-search`). Precision: cross-encoder reranks the fused top-100 to a top-20-40 shortlist. Business ranking: an LTR model (LambdaMART baseline, since traffic likely supports real click data) reorders that shortlist using relevance score, CTR, conversion rate, price, inventory, and personalization features, trained with propensity-corrected labels to avoid baking in position bias. Sponsored listings are interleaved as a distinct mix-ranking step after organic ranking, not blended into the same LTR score, so ranking transparency and auditability are preserved. Query understanding (intent classification, spell correction) runs before retrieval; any LLM-based query rewriting is evaluated per query-type slice before being trusted in the default path.
**Follow-up trap:** *"Would you train one unified model instead of these separate stages?"* — a single end-to-end model is tempting but sacrifices debuggability and the ability to independently improve/audit each stage (e.g., proving sponsored placement doesn't bias organic relevance); staged systems remain the practical default at this level of business complexity specifically because of that auditability requirement.

---

## Red flags that fail you

- Believing "semantic search" means dense-only, with no lexical leg.
- Treating vocabulary mismatch and rare-token blurring as the same failure mode rather than opposite, complementary ones.
- Assuming reranking (text relevance) and learned ranking (business objective) are the same thing.
- Not knowing what LambdaMART is or why GBDTs remain a strong production baseline.
- Training or trusting an LTR model on raw click data without mentioning position bias.
- Assuming query rewriting is a strict improvement with no failure mode.
- Recommending a full LTR build-out for a small-catalog, low-traffic product with no interaction data.

---

## Cheat card

```
LINEAGE   boolean (no ranking) -> TF-IDF/BM25 (vocabulary mismatch) -> dense bi-encoder
          (blurs rare/exact tokens) -> hybrid (fuse both) -> learned ranking (adds
          business signals text similarity can't see)

HYBRID WINS   ~91% recall@10 hybrid vs ~78% dense-only vs ~65% sparse-only (typical prod benchmark)

BM25 STILL WINS ON   exact identifiers (SKUs, error codes) · rare technical terms
                     · code search (identifier-exact matching)

LTR FEATURES   text relevance (BM25/dense/cross-encoder score) + CTR + recency + price
               + inventory + personalization -- business objective, not just relevance

LAMBDAMART   GBDT trained to optimize nDCG directly (not pointwise regression).
             Won 2010 Yahoo! LTR Challenge. Still a standard production baseline:
             fast train, cheap/predictable serve, handles nonlinear feature interactions.

CASCADE   matching (cheap, corpus-scale) -> pre-ranking (thousands) -> ranking
          (full LTR, tens) -> mix-ranking (business rules, ads interleave)

POSITION BIAS   raw click logs reward whatever was already ranked #1 -- LTR trained on
                them reinforces the existing order, not true relevance.
                Fix: inverse propensity scoring or randomized interleaving.

QUERY REWRITING   can help (conversational follow-ups) OR hurt (HyDE/expansion distorts
                  intent, overamplifies rare terms) -- eval per query-type, never blanket-apply

DEFAULT   hybrid + cross-encoder rerank is right for most RAG. Full LTR layer only
          when there's a business objective beyond relevance AND real interaction data.

WHEN NOT TO BUILD LTR   small catalog, low traffic, no click history -- hand-tuned
                        boosting (BM25 + recency + popularity) beats an overfit model
```

## Sources

- [Hybrid Search: BM25, Vector & Reranking Reference 2026](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026) — accessed 2026-08-01
- [BM25 vs Dense Retrieval for RAG: What Actually Breaks in Production](https://ranjankumar.in/bm25-vs-dense-retrieval-for-rag-engineers) — accessed 2026-08-01
- [Learning Cascade Ranking as One Network (arXiv:2503.09492)](https://arxiv.org/html/2503.09492v3) — accessed 2026-08-01
- [Cascade Ranking for Operational E-commerce Search (arXiv:1706.02093)](https://arxiv.org/pdf/1706.02093) — accessed 2026-08-01
- [The ABCs of Learning to Rank — Lucidworks](https://lucidworks.com/blog/abcs-learning-to-rank) — accessed 2026-08-01
- [When Query Expansion Hurts RAG — Thinking Loop](https://medium.com/@ThinkingLoop/when-query-expansion-hurts-rag-23139f06d8d4) — accessed 2026-08-01
- [RAG in Production 2026: GraphRAG, Hybrid Retrieval, and Evals](https://ailearningguides.com/rag-production-patterns-2026/) — accessed 2026-08-01
- [Introducing Contextual Retrieval — Anthropic](https://www.anthropic.com/engineering/contextual-retrieval) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
