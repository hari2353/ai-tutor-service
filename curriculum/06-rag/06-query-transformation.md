# Query Transformation: HyDE, Multi-Query, Decomposition, Step-Back, Routing

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **Prereqs:** 03-vector-index-internals, 04-hybrid-search, 05-reranking · **Updated:** 2026-07-27
> **Module id:** `T06-query-transformation` · **Tags:** retrieval

## The 30-second version

The user's literal query is frequently the worst possible string to embed and search with: it's short, ambiguous, uses different vocabulary than the corpus, or bundles multiple sub-questions into one sentence. Query transformation is the umbrella term for rewriting the query before it hits the index — HyDE generates a fake answer and embeds that instead of the question, multi-query/RAG-Fusion generates several paraphrases and fuses their result sets with Reciprocal Rank Fusion, decomposition splits a compound question into independently-retrievable sub-questions, step-back prompting asks a more general question first to surface background context, and routing decides which index or retrieval strategy a query should even go to. None of these are free: every one adds at least one LLM call before retrieval even starts, so the real skill isn't knowing the techniques, it's knowing which one earns its latency and cost on a given failure mode, and defaulting to none of them when a plain query embeds fine. In production, one extra LLM call for query rewriting plus a reranker pass is the common ceiling; stacking HyDE, multi-query, and decomposition together is a research-paper pipeline, not a p50-latency-budget-respecting one.

## Why this gets asked

The interviewer has watched a RAG system's retrieval quality look fine in a demo with clean, well-formed test queries and then fall apart on real user queries — typos, vague pronouns, multi-part questions, jargon mismatches between how a user asks and how the corpus is written. They want to know if you reach for query transformation as a targeted fix for a diagnosed retrieval failure mode, or as a reflexive "add more LLM calls" instinct that doubles latency and cost without anyone checking whether it moved recall at all.

---

## Lineage: past → present → future

**What came before.** Early RAG systems (2020-2022, following the original RAG paper by Lewis et al.) embedded the user's query verbatim and did a single dense retrieval pass. This works when queries resemble the corpus's own language — well-formed factual questions against Wikipedia-style text — and fails visibly on short, underspecified, or vocabulary-mismatched queries, because a dense embedding of "how do I fix this" carries almost no retrievable signal. The first fix was classical query expansion from IR (pseudo-relevance feedback, Rocchio, the 1970s-80s lineage), which expanded a query with terms from an initial retrieval pass — the core idea query transformation reuses, just with an LLM doing the expansion instead of term-frequency statistics.

**Where it stands now.** HyDE (Gao et al., "Precise Zero-Shot Dense Retrieval without Relevance Labels," 2022) showed that having an LLM hallucinate a plausible answer and embedding *that* often retrieves better than embedding the question, because the hypothetical answer's embedding lands closer to real answer documents in vector space than the question's embedding does. RAG-Fusion (Raudaschl, 2023) and LangChain's MultiQueryRetriever popularized generating several paraphrased queries and merging result sets with Reciprocal Rank Fusion (RRF), reusing the same fusion math that made hybrid BM25+dense search work. Step-back prompting (Zheng et al., Google DeepMind, "Take a Step Back," 2023) showed asking a more abstract question first — "what are the general principles of X" before "what specifically happens when X and Y" — improves multi-hop and reasoning-heavy retrieval by surfacing background the specific question alone wouldn't retrieve. Query decomposition (splitting a compound question into independent sub-questions, each retrieved and answered separately, then composed) is now standard in agentic RAG stacks. The live disagreement is not whether these techniques work — each has published wins on its target failure mode — but whether they're worth the latency and cost in a p50/p99-constrained production system, given that every one adds an LLM round-trip before retrieval even starts. The 2026 production consensus, per multiple RAG architecture retrospectives, is that most shipped systems use one or two of these techniques (typically query rewriting plus reranking), rarely the full stack.

**Where it's heading.** Caching transformed queries (so decomposition or HyDE cost is paid once per distinct query pattern, not per request) is becoming standard practice — moderate-to-high confidence, already visible in production write-ups. Routing is converging toward hybrid logical+semantic approaches, using a cheap classifier or small model rather than a full LLM call, to keep the added latency in single-digit milliseconds — moderate confidence. More speculative: fully agentic query planning where the retrieval strategy itself is chosen and adjusted mid-conversation by the agent rather than fixed at request time, and learned query rewriters (small fine-tuned models replacing prompted LLM calls) to cut the per-request cost of transformation to near-zero — both are appearing in papers and some agentic RAG demos but are not yet the default production pattern.

---

## Mental model

Every technique below intercepts the query *before* it reaches the vector/BM25 index, and each one trades one or more extra LLM calls for a specific retrieval failure mode it fixes:

```
User query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                  QUERY TRANSFORMATION LAYER              │
│                                                            │
│  ROUTING        — which index/strategy handles this query? │
│  STEP-BACK      — ask a more general question first        │
│  DECOMPOSITION  — split into independent sub-questions      │
│  HyDE           — generate a fake answer, embed THAT        │
│  MULTI-QUERY    — generate N paraphrases, fuse results (RRF)│
└─────────────────────────────────────────────────────────┘
    │
    ▼
Retrieval (BM25 + dense + rerank, per 04/05)
```

Each box costs at minimum one LLM call (except rule-based routing) added *serially* before retrieval starts — this is why stacking more than one or two is a latency decision, not a free accuracy win.

---

## How it actually works

### HyDE: embed the answer, not the question

**Mechanism.** Prompt an LLM: "Write a passage that answers this question: {query}." Embed the generated passage (not the original query) and use that embedding to search the index. The generated passage is very likely to contain factual errors — HyDE doesn't care, because it isn't returned to the user. What matters is that the hypothetical passage's *semantic structure* — vocabulary, phrasing, the shape of what an answer looks like — sits closer in embedding space to real answer documents than the bare question does.

**Why it works mechanically.** Dense embedding models are trained largely on document-to-document or query-to-passage-with-answer-shape similarity, not question-to-question similarity. A four-word question embeds far from a three-paragraph technical answer even when the question is exactly answered by that paragraph. A hallucinated three-paragraph answer, even if factually wrong, embeds close to the real answer because both share paragraph-length technical prose structure and overlapping vocabulary.

**Cost.** One LLM generation call (typically 100-300 generated tokens, a few hundred milliseconds on a fast model) added serially before the embedding call. No extra cost at the index side — it's a single embedding, single search, same as baseline.

**When it helps most.** Short, vague, or jargon-poor queries against a corpus with long-form technical answers — the exact case where question-embedding fails hardest. It helps least on queries that are already well-formed technical statements close to the corpus's own phrasing, where HyDE just adds latency for no retrieval gain.

### Multi-query / RAG-Fusion: paraphrase and fuse

**Mechanism.** Prompt an LLM to generate N (typically 3-5) paraphrases or reformulations of the query, retrieve independently for each, then merge the N ranked result lists with Reciprocal Rank Fusion:

```
RRF(d) = Σ_r  1 / (k + rank_r(d))
```

summed over each result list `r` the document `d` appears in, with `k=60` as the near-universal default (empirically stable across BEIR-style benchmarks; large enough that the exact top-1 rank in any single list doesn't dominate the score, so a document that ranks consistently well across several paraphrases beats one that's #1 in only one list and absent from the rest).

**Cost.** One LLM call to generate N paraphrases, then N separate retrieval passes (N embedding calls if dense, N BM25 queries if lexical) run in parallel, followed by the RRF merge (cheap, O(N·k) list processing). Latency is roughly `generation_latency + max(retrieval_latency across N parallel calls)` if retrievals are parallelized, or `generation_latency + N * retrieval_latency` if not — parallelizing the N retrieval calls is not optional in a latency-sensitive system.

**Why it helps.** Any single phrasing of a query might miss a corpus's specific vocabulary; averaging across several phrasings recovers documents that would only surface under one specific wording. This is the same mechanism that makes hybrid BM25+dense search (04-hybrid-search) work, applied to query variants instead of retrieval methods.

### Decomposition: split compound questions

**Mechanism.** An LLM call detects whether a query bundles multiple independently-answerable sub-questions ("compare X's approach to Y's approach and explain which failed in production and why") and splits it into separate sub-queries, each retrieved and (often) answered independently, then composed into a final answer.

**Cost — the number to know.** A 2026 study on question decomposition for RAG reports roughly **16.7 seconds/query** of added overhead from the extra LLM inference needed to generate sub-queries, rising to about **18.9 seconds/query** when combined with reranking. This is an order of magnitude more expensive than HyDE or multi-query, because decomposition typically requires a larger/slower model to reliably identify sub-question boundaries, and each sub-question then triggers its own retrieval-and-rerank pass. The mitigating factor: once a query pattern is decomposed, the sub-queries can be cached, so *repeated* instances of a similar compound query pay this cost once, not per request.

**When it helps.** Genuinely compound or multi-hop questions where a single retrieval pass structurally cannot surface documents relevant to all parts of the question at once. It's the wrong tool for single-fact questions — the decomposition LLM call adds nothing and just burns the 16-19 second latency budget for zero retrieval gain.

### Step-back prompting: ask the general question first

**Mechanism.** Rather than retrieving directly for the specific query, an LLM first rewrites it into a more abstract/general question ("what are the underlying principles of X" instead of "what happens when X does Y in edge case Z"), retrieves for *that*, and uses the retrieved background alongside a second retrieval pass (or the same pass) for the specific question.

**Why it helps.** Specific, deeply-nested technical questions often have no single document that directly answers them, but the general principle needed to reason to the answer is well-represented in the corpus. Step-back retrieval surfaces that background even when no document matches the specific phrasing. Reported gains are concentrated in multi-hop reasoning and STEM/knowledge-heavy QA benchmarks; it does little for queries that are already well-answered by a single specific document.

**Cost.** One extra LLM call (the step-back rewrite) plus, in most implementations, a second retrieval pass (general + specific), so cost is similar in shape to multi-query but with only two queries instead of N.

### Routing: choosing the index or strategy first

**Mechanism.** Before any retrieval happens, decide *which* index, retrieval strategy, or downstream tool a query should go to — e.g., route factual lookups to a vector index, route "how many" / aggregate questions to a SQL/analytics backend, route code questions to a code-specific embedding index.

**Logical (LLM-based) routing.** An LLM call classifies the query into one of a fixed set of route labels, passed in the prompt, and the output label drives an if/else branch. More accurate on ambiguous or context-dependent queries, at the cost of a full LLM round-trip — reported latency around **~800ms** for LLM-based routing in practical guidance write-ups.

**Semantic (embedding-based) routing.** Embed the query and the route descriptions, pick the route whose description embedding is closest. Much cheaper — reported around **~100ms** for typical embedding-similarity routing setups — but can misroute complex, context-dependent queries that don't reduce cleanly to nearest-description-match.

**Rule-based / classifier routing.** Regex, keyword rules, or a small trained classifier. High-performance implementations add on the order of **10-50 microseconds**; simple Python-based rule routers add roughly **3-5ms** — both negligible against typical 500-2000ms end-to-end LLM inference latency, which is why rule-based routing is the default whenever the routing decision can be expressed as a fixed, learnable classification.

**Choosing among them.** Fixed, well-separated query types favor semantic or rule-based routing (fast, cheap, good enough). Multi-domain, ambiguous, or context-dependent routing decisions favor logical (LLM) routing despite the latency, because misrouting costs more (wrong index entirely, zero relevant results) than the extra few hundred milliseconds.

---

## Build it from scratch

```python
# untested sketch — HyDE + multi-query with RRF fusion, no framework
from openai import OpenAI
import numpy as np

client = OpenAI()

def hyde_embed(query: str, embed_fn) -> np.ndarray:
    """Generate a hypothetical answer, embed that instead of the query."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"Write a short passage that directly answers this question:\n{query}",
        }],
        max_tokens=200,
    )
    hypothetical = resp.choices[0].message.content
    return embed_fn(hypothetical)

def generate_paraphrases(query: str, n: int = 4) -> list[str]:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"Generate {n} different phrasings of this search query, "
                f"one per line, no numbering:\n{query}"
            ),
        }],
        max_tokens=200,
    )
    return [line.strip() for line in resp.choices[0].message.content.split("\n") if line.strip()]

def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Standard RRF: score = sum(1 / (k + rank)) across all lists a doc appears in."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def multi_query_retrieve(query: str, retrieve_fn, n: int = 4) -> list[tuple[str, float]]:
    paraphrases = generate_paraphrases(query, n)
    ranked_lists = [retrieve_fn(p) for p in [query] + paraphrases]  # include original
    return reciprocal_rank_fusion(ranked_lists)
```

The three things a real implementation adds that this sketch skips: caching the LLM-generated paraphrases/hypothetical docs keyed on a normalized query (avoids paying the transformation cost twice for near-duplicate queries), parallelizing the N retrieval calls in multi-query (this sketch runs them serially in the list comprehension), and a fallback path that skips transformation entirely when a cheap classifier decides the raw query is already well-formed.

---

## How it's done in production

**LangChain** ships `MultiQueryRetriever` (LLM-generated paraphrases + dedup) and a `HyDE`-style chain out of the box; both are thin wrappers around the patterns above. **LlamaIndex** provides query transformation modules including step-back and sub-question decomposition (`SubQuestionQueryEngine`), which explicitly builds a query plan against multiple tools/indexes. **Aurelio Labs' `semantic-router`** is the reference standalone library for embedding-based routing when you don't want a full LLM call per request. Most production agentic-RAG stacks combine at most two or three of these techniques — commonly query rewriting (a lightweight paraphrase/normalization step, not full HyDE) plus a reranker pass — rather than the full five-technique stack, because each additional technique is a serial LLM call on the critical path.

| Symptom | Cause | Fix |
|---|---|---|
| Retrieval quality fine in eval, poor on real traffic | Eval queries are well-formed; real queries are short/vague/typo-laden | Add HyDE or query rewriting targeted at the specific query shapes failing, verified against a held-out real-query eval, not the original golden set |
| p50 latency doubled after adding query transformation | Serial LLM call added before every retrieval, on every request, regardless of whether the query needed it | Route: only invoke transformation when a cheap classifier/heuristic flags the query as short/ambiguous; cache transformed queries for repeat patterns |
| Multi-query retrieval returns near-duplicate results across paraphrases | Paraphrases too similar (LLM under-diversifies), so RRF fusion adds no coverage gain over a single query | Explicitly prompt for lexically diverse phrasings, or fall back to a single well-formed query if diversity check fails |
| Decomposition sub-questions retrieve irrelevant documents | Query wasn't actually compound; decomposition invented spurious sub-questions | Gate decomposition behind a cheap "is this compound" classifier before invoking the (expensive, ~17s) decomposition LLM call |
| Routing sends queries to the wrong index/tool under ambiguous phrasing | Semantic routing's nearest-description-match failed on a context-dependent query that doesn't reduce to embedding similarity | Escalate ambiguous-confidence routes to LLM-based (logical) routing instead of accepting the semantic router's low-confidence match |
| HyDE retrieval gets worse, not better, after adding it | Corpus already closely matches query phrasing (e.g., FAQ-style corpus), so the hallucinated passage's vocabulary drift actively hurts rather than helps | A/B test HyDE against baseline on your actual corpus before shipping it; don't assume the technique transfers from its original benchmark domain |

---

## Tradeoffs & when NOT to use it

- **Never add query transformation without first diagnosing which failure mode you're fixing.** Each technique targets a specific, named retrieval failure — HyDE for vocabulary mismatch, decomposition for compound questions, step-back for missing background, multi-query for phrasing coverage. Adding one because it's "best practice" without a diagnosed symptom is pure latency cost with unverified benefit.
- **Decomposition is usually the wrong default.** At 16-19 seconds/query, it's the most expensive technique in this module by an order of magnitude. Gate it behind a cheap classifier that detects genuinely compound queries; never run it unconditionally.
- **HyDE is the wrong choice for well-formed, corpus-matching queries.** If your users already phrase questions close to how the corpus is written (common in FAQ-style or documentation-search corpora), HyDE's hallucinated passage can introduce vocabulary drift that hurts rather than helps — verify with an A/B test, don't assume the published gains transfer.
- **Multi-query/RAG-Fusion is wasted cost if your paraphrases aren't actually diverse.** An LLM asked for "different phrasings" often produces near-synonymous variants that retrieve the same documents; RRF fusion over near-duplicate lists buys nothing for the extra retrieval calls it costs.
- **LLM-based routing is the wrong choice when routes are fixed and well-separated.** Paying an ~800ms LLM call to pick between two clearly distinguishable route types (e.g., "code question" vs "policy question") when a rule-based classifier would resolve it in microseconds is a latency budget mistake, not a quality win.
- **Never stack all five techniques in one request path.** Each is a serial LLM call; stacking HyDE + multi-query + decomposition + step-back + LLM routing in one request can add several seconds of latency before retrieval even completes. Production systems pick one or two, matched to the corpus's actual failure modes.

---

## Interview questions

### Q1 — What problem does HyDE solve, and why does embedding a hallucinated answer work better than embedding the question?
**Testing:** whether the candidate understands the embedding-space mechanism, not just the recipe.
**Answer:** Dense embedding models are trained on passage-to-passage-style similarity; a short question and a long technical answer that directly answers it can sit far apart in embedding space despite being semantically linked. A hallucinated answer, even if factually wrong, shares the vocabulary and paragraph-length structure of a real answer, so its embedding lands closer to real answer documents than the bare question's embedding does.
**Follow-up trap:** *"Doesn't a factually wrong hypothetical document risk retrieving the wrong documents?"* — the risk is real but bounded: HyDE's hypothetical document is never shown to the user or used for generation, only for retrieval, and its value comes from semantic/structural similarity, not factual correctness. If the corpus vocabulary already closely matches user queries, though, HyDE can actively hurt — say so rather than presenting it as risk-free.

### Q2 — Walk through Reciprocal Rank Fusion. Why `k=60`, and what does the formula actually optimize for?
**Answer:** `RRF(d) = Σ_r 1/(k + rank_r(d))`, summed across every ranked list a document appears in. `k=60` is an empirically stable default across benchmark studies; it's large enough that a document's exact top rank in any single list doesn't dominate its score, so RRF rewards documents that appear consistently across multiple lists over one that's #1 in a single list but absent elsewhere — consensus over outliers.
**Follow-up trap:** *"What happens if you set k=1?"* — the formula becomes far more sensitive to top-1 rank in each list, effectively behaving closer to a max-rank vote; you lose the consensus-favoring property that makes RRF robust, and a single list's #1 pick can dominate the fused ranking disproportionately.

### Q3 — What's the actual latency/cost overhead of question decomposition, and when is it worth it?
**Answer:** A 2026 study measured roughly 16.7 seconds/query overhead from decomposition alone, rising to about 18.9 seconds/query combined with reranking — an order of magnitude more expensive than HyDE or multi-query, because reliably splitting compound questions typically needs a larger/slower model, and each sub-question then triggers its own retrieval pass. It's worth it only for genuinely compound or multi-hop questions where a single retrieval pass structurally can't cover all parts of the question; caching decomposed sub-queries for repeated query patterns amortizes the cost.
**Follow-up trap:** *"How would you avoid paying this on every request?"* — gate decomposition behind a cheap classifier that first decides whether the query is actually compound, and cache the decomposition output keyed on normalized query text.

### Q4 — Explain step-back prompting and name a case where it helps that multi-query wouldn't.
**Answer:** Step-back rewrites a specific query into a more general/abstract one, retrieves for that to surface background context, then combines it with the specific retrieval. It helps on deeply specific technical or multi-hop questions where no single document directly answers the specific phrasing, but the general principle needed to reason toward the answer is well-represented in the corpus. Multi-query wouldn't help there because paraphrasing the *same* specific question doesn't surface documents about the underlying general principle — it only recovers phrasing variants of the same specific ask.
**Follow-up trap:** *"Would step-back help on a simple factual lookup?"* — no, and it would add latency for nothing; step-back's gains concentrate in multi-hop/reasoning-heavy retrieval, not single-fact lookups that a direct query already answers.

### Q5 — Compare logical, semantic, and rule-based routing on latency and when you'd pick each.
**Answer:** Rule-based/classifier routing adds roughly 10-50 microseconds (compiled) to a few milliseconds (simple Python), negligible against typical LLM inference latency — use it whenever routes are fixed and separable by simple features. Semantic (embedding) routing costs roughly 100ms and handles fuzzier route boundaries via nearest-description-match, but can misroute context-dependent queries that don't reduce cleanly to embedding similarity. Logical (LLM) routing costs roughly 800ms but handles ambiguous, context-dependent routing decisions most reliably — use it when misrouting cost (wrong index, zero relevant results) exceeds the latency cost of an LLM call.
**Follow-up trap:** *"Could you combine them?"* — yes, and it's the common production pattern: rule-based routing for the obvious cases, escalating to semantic or logical routing only for queries the rule-based layer can't confidently classify.

### Q6 — A user's query returns zero relevant results, and you suspect a vocabulary mismatch between the query and the corpus. Which technique do you reach for first, and why not the others?
**Answer:** HyDE, because vocabulary mismatch is exactly its target failure mode — it substitutes the question's embedding with a hypothetical answer's embedding, which shares the corpus's answer-shaped vocabulary. Multi-query wouldn't reliably fix pure vocabulary mismatch since paraphrasing the same underlying concept in the user's vocabulary doesn't guarantee landing on the corpus's vocabulary. Decomposition and step-back target compound questions and missing background respectively, not vocabulary drift, so they wouldn't address this specific symptom.
**Follow-up trap:** *"What if HyDE doesn't fix it either?"* — check whether the mismatch is actually a chunking or embedding-model problem (wrong domain-specific embedding model, or chunks that fragment the answer) rather than a query-side problem; query transformation can't fix a retrieval failure whose root cause is on the ingestion side.

### Q7 — Why is running all five query transformation techniques together usually a mistake?
**Answer:** Every technique here (except rule-based routing) adds at least one serial LLM call before retrieval starts. Stacking HyDE, multi-query, decomposition, step-back, and LLM routing in one request path can add several seconds of latency before a single retrieval call even completes, for accuracy gains that are rarely additive — each technique targets a distinct failure mode, and a query usually only exhibits one or two of those failure modes at a time.
**Follow-up trap:** *"How would you decide which one or two to keep?"* — profile actual production query failures (zero-result queries, low-relevance-score queries, user reformulation patterns) to identify which specific failure mode dominates, then apply only the technique(s) that target it, verified with an A/B test against the added latency cost.

### Q8 — Design the query pipeline for a support-ticket RAG system where users often paste multi-paragraph problem descriptions bundling several distinct issues.
**Testing:** synthesis and judgment about which techniques compose, not a checklist recitation.
**Answer:** This is a decomposition-shaped problem — compound, multi-issue queries are exactly its target case — but running the full ~17-19 second decomposition path on every ticket is too slow for an interactive support flow. Gate decomposition behind a cheap heuristic (ticket length, presence of multiple question marks or discourse markers like "also" / "additionally") that flags likely-compound tickets, and only invoke full decomposition for those; short single-issue tickets skip straight to standard hybrid retrieval. Cache decomposition output per ticket since re-answering the same ticket shouldn't re-pay the cost.
**Follow-up trap:** *"What if the heuristic misses a compound ticket?"* — accept some false negatives; the fallback is a lower-quality but fast single-pass retrieval, and a wrong "skip decomposition" call is recoverable (user can ask a follow-up), whereas paying full decomposition latency on every ticket is not.

### Q9 — Your team wants to add HyDE to improve retrieval, but an A/B test shows retrieval quality got slightly worse after shipping it. What do you check first?
**Answer:** Whether the corpus already closely matches user query phrasing (FAQ-style, documentation-search corpora commonly do) — in that case HyDE's hallucinated-answer vocabulary drift can hurt more than help, since the baseline question embedding was already landing close to the right documents. Check per-query-type breakdowns rather than the aggregate metric; HyDE may help vague queries while hurting well-formed ones, and the aggregate can mask that split.
**Follow-up trap:** *"So would you just revert it?"* — better: route HyDE conditionally, applying it only to queries a cheap classifier flags as short/vague, and skip it for queries already well-formed relative to the corpus — this is the same "diagnose before applying" discipline as with decomposition.

### Q10 — How would you evaluate whether a query transformation technique is actually helping, beyond "it feels better in a demo"?
**Answer:** Run retrieval@k (and downstream answer-quality metrics) on a held-out eval set with and without the transformation, broken down by query type/length/ambiguity, not just in aggregate — a technique can help one query segment and hurt another while looking neutral overall. Also measure the added latency and LLM cost per request, and weigh the metric delta against that cost explicitly rather than shipping any accuracy gain regardless of cost.
**Follow-up trap:** *"What if your golden eval set doesn't contain the query shapes the technique targets?"* — then the eval is measuring the wrong thing; you need real production query logs (or synthetic queries deliberately shaped to mimic the failure mode, e.g., short/vague queries for HyDE) in the eval set, not just the original well-formed golden questions.

### Q11 — Multi-query retrieval with RRF fusion sometimes returns worse results than a single well-formed query. Why?
**Answer:** If the LLM-generated paraphrases aren't lexically or semantically diverse — often producing near-synonymous variants — RRF fuses several nearly-identical ranked lists, which doesn't add coverage and just adds retrieval latency for the extra parallel calls. It can also dilute a strong single-list top result if weaker documents accumulate small RRF scores across multiple near-duplicate lists.
**Follow-up trap:** *"How would you detect this before it reaches production?"* — measure paraphrase diversity (e.g., lexical overlap or embedding distance between generated paraphrases) as part of the eval, and fall back to single-query retrieval when diversity falls below a threshold rather than always running the full multi-query path.

### Q12 — Is HNSW/vector index choice affected by query transformation, or are they orthogonal concerns?
**Answer:** Orthogonal in principle — the index doesn't know or care whether the vector it's searching came from a raw query or a HyDE-generated passage — but query transformation changes the *distribution* of vectors hitting the index (a HyDE embedding is a full-passage embedding, not a short-query embedding), which can matter if the index or embedding model behaves differently across text lengths. Always confirm the same embedding model handles both query-length and passage-length inputs consistently, since a mismatch there is a subtler failure mode than the index parameters themselves.
**Follow-up trap:** *"Would you need a different `efSearch` for HyDE-transformed queries?"* — no, `efSearch` governs search breadth, unrelated to what generated the query vector; don't conflate query transformation concerns with index-tuning concerns just because both touch the same request path.

### Q13 — When would you choose rule-based routing over semantic routing even though semantic routing is more flexible?
**Answer:** When the routing decision reduces to a small number of well-separated, learnable features (file type, explicit keyword, query length, presence of a code block) — rule-based routing resolves these in microseconds to a few milliseconds versus ~100ms for embedding similarity, and at that decision complexity the flexibility of semantic routing buys nothing, since the rule-based classifier already gets it right.
**Follow-up trap:** *"What's the risk of over-relying on rule-based routing?"* — brittleness on inputs that don't match the anticipated rule patterns; a rule-based router silently misroutes novel phrasings that a semantic or logical router would have caught, so it needs a fallback path (semantic or logical routing) for low-confidence or unmatched cases, not a hard-coded default.

### Q14 — How does step-back prompting interact with a corpus that has no "general principles" documents, only narrow how-to articles?
**Answer:** Step-back's benefit depends on the corpus actually containing the general background the step-back query would surface; if the corpus is exclusively narrow how-to content with no conceptual/overview documents, the step-back retrieval pass returns nothing useful, and you've paid an extra LLM call and retrieval pass for no gain. This is a corpus-shape precondition worth checking before adopting step-back, not something to assume works universally.
**Follow-up trap:** *"How would you verify this before shipping?"* — spot-check whether step-back's general-question retrieval actually surfaces distinct, useful documents from the specific-question retrieval on a sample of real multi-hop queries; if the two retrieval passes return near-identical result sets, step-back isn't adding value on this corpus.

### Q15 — Design query routing for a system with three backends: a vector index for unstructured docs, a SQL warehouse for structured metrics, and a code-search index. Real user queries mix all three intents.
**Testing:** synthesis; awareness that a single routing strategy for all three isn't right.
**Answer:** Start with a cheap rule-based/keyword layer to catch unambiguous cases (explicit SQL-shaped questions like "how many," code syntax in the query) at microsecond cost. Escalate anything the rule layer doesn't confidently classify to semantic routing against short route descriptions of each backend (~100ms). Reserve LLM-based logical routing for queries that remain ambiguous after both — genuinely mixed-intent queries ("show me the error rate for this function and the code that handles it") that may need to route to *more than one* backend and have results composed, which neither rule-based nor semantic routing can decide alone. Log routing decisions and misroute reports to retrain/tune the cheaper layers over time, since the goal is pushing as much traffic as possible to the cheapest layer that still routes correctly.
**Follow-up trap:** *"What happens when a query genuinely needs two backends?"* — that's a decomposition-plus-routing problem: split the query into its structured and unstructured parts first, route each independently, then compose. Say this explicitly rather than treating routing as a single-destination decision when the input can legitimately be compound.

---

## Red flags that fail you

- Recommending HyDE, multi-query, decomposition, or step-back without naming the specific retrieval failure mode each one targets.
- Not knowing that every one of these techniques (except rule-based routing) adds a serial LLM call before retrieval starts.
- Quoting decomposition as a cheap technique — it's the most expensive in this module by an order of magnitude (~17-19s/query).
- Treating RRF's `k=60` as an arbitrary magic number rather than explaining what it controls (consensus vs. outlier sensitivity).
- Assuming HyDE always helps — it can hurt on corpora whose vocabulary already matches user queries.
- Recommending the full five-technique stack as a default pipeline rather than a diagnosed, targeted subset.
- Confusing query transformation concerns with index-tuning concerns (e.g., claiming HyDE requires different `efSearch`).

---

## Cheat card

```
HyDE            embed a hallucinated ANSWER, not the question. Fixes vocabulary mismatch.
                Cost: 1 LLM call (~100-300 tok). Hurts if corpus already matches query phrasing.

MULTI-QUERY     LLM generates N (3-5) paraphrases → retrieve each → fuse with RRF.
RAG-FUSION      RRF(d) = Σ 1/(k + rank_r(d)), k=60 (consensus > outlier). Parallelize N retrievals.
                Wasted if paraphrases aren't lexically diverse.

DECOMPOSITION   split compound query into sub-questions, retrieve+answer each independently.
                COST: ~16.7s/query alone, ~18.9s/query w/ reranking — most expensive technique.
                Gate behind a cheap "is this compound" classifier. Cache decomposed sub-queries.

STEP-BACK       ask a more GENERAL question first to surface background, then the specific one.
                Helps multi-hop/reasoning; needs corpus to actually contain general/overview docs.

ROUTING         rule-based: ~10-50us (compiled) to ~3-5ms (Python) — use for fixed, separable routes
                semantic:   ~100ms embedding-similarity — fixed query types, fuzzy boundaries OK
                logical(LLM): ~800ms — ambiguous/context-dependent, misroute cost > latency cost

PRODUCTION      most shipped systems use 1-2 of these (commonly: query rewrite + reranker),
                not the full stack. Every technique = 1+ serial LLM call before retrieval.
                Always diagnose the failure mode BEFORE picking the technique.
```

## Sources

- [HyDE: Hypothetical Document Embeddings — EmergentMind](https://www.emergentmind.com/topics/hypothetical-document-embeddings-hyde) — accessed 2026-07-27
- [Better RAG with HyDE — Zilliz Learn](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings) — accessed 2026-07-27
- [A Survey of Query Optimization in Large Language Models](https://arxiv.org/pdf/2412.17558) — accessed 2026-07-27
- [Question Decomposition for Retrieval-Augmented Generation](https://arxiv.org/pdf/2507.00355) — accessed 2026-07-27
- [RAG-Fusion — Raudaschl/rag-fusion GitHub](https://github.com/Raudaschl/rag-fusion) — accessed 2026-07-27
- [Reciprocal Rank Fusion (RRF) explained — Deval Shah, Medium](https://medium.com/@devalshah1619/mathematical-intuition-behind-reciprocal-rank-fusion-rrf-explained-in-2-mins-002df0cc5e2a) — accessed 2026-07-27
- [Advanced RAG — Understanding Reciprocal Rank Fusion in Hybrid Search — Guillaume Laforge](https://glaforge.dev/posts/2026/02/10/advanced-rag-understanding-reciprocal-rank-fusion-in-hybrid-search/) — accessed 2026-07-27
- [Routing in RAG-Driven Applications — Sami Maameri, Towards Data Science](https://towardsdatascience.com/routing-in-rag-driven-applications-a685460a7220/) — accessed 2026-07-27
- [RAG Query Routing in Practice — BetterLink Blog](https://eastondev.com/blog/en/posts/ai/20260513-rag-query-routing/) — accessed 2026-07-27
- [RAG Is Not Dead: Advanced Retrieval Patterns That Actually Work in 2026 — DEV Community](https://dev.to/young_gao/rag-is-not-dead-advanced-retrieval-patterns-that-actually-work-in-2026-2gbo) — accessed 2026-07-27
- [The Query Rewriting Layer Your RAG Pipeline Skipped — TianPan.co](https://tianpan.co/blog/2026-04-26-query-rewriting-rag-retrieval-shape) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
